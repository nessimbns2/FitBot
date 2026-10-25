"""
app/modules/user/service.py
Business logic for User & Profile and Chat Sessions.
No HTTP concerns — all functions accept a SQLModel Session argument.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.modules.user.models import (
    AthleteBlueprintRequest,
    AthleteBlueprintResponse,
    ChatMessage,
    ChatSession,
    MessageRead,
    SessionSummary,
    Somatotype,
    SomatotypeQuizRequest,
    SomatotypeQuizResponse,
    TimelineProjection,
    UserProfile,
    UserProfileUpdate,
    VolumeLandmarks,
)
from app.modules.nutrition.calculator import calculate
from app.modules.rag_core.engine import get_llm_client, get_vector_store
from app.prompts import (
    ATHLETE_BLUEPRINT_SYSTEM_PROMPT,
    ATHLETE_BLUEPRINT_USER_TEMPLATE,
    SOMATOTYPE_PREDICTION_SYSTEM_PROMPT,
    SOMATOTYPE_PREDICTION_USER_TEMPLATE,
    SOMATOTYPE_QUESTIONS,
)

# ── Single local user ─────────────────────────────────────────────────────────

DEFAULT_USER_ID = 1


def get_or_create_default_profile(session: Session) -> UserProfile:
    """Return the single local user profile, creating it on first call."""
    profile = session.get(UserProfile, DEFAULT_USER_ID)
    if profile is None:
        profile = UserProfile(id=DEFAULT_USER_ID)
        session.add(profile)
        session.commit()
        session.refresh(profile)
    return profile


def update_profile(session: Session, data: UserProfileUpdate) -> UserProfile:
    """Apply a partial update to the user profile."""
    profile = get_or_create_default_profile(session)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)
    profile.updated_at = datetime.now(timezone.utc)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


# ── Chat Sessions ─────────────────────────────────────────────────────────────


def create_session(session: Session, title: str = "New conversation") -> ChatSession:
    """Create a new chat session for the default user."""
    profile = get_or_create_default_profile(session)
    chat_session = ChatSession(user_id=profile.id, title=title)
    session.add(chat_session)
    session.commit()
    session.refresh(chat_session)
    return chat_session


def list_sessions(session: Session) -> list[SessionSummary]:
    """Return all sessions newest first."""
    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == DEFAULT_USER_ID)
        .order_by(ChatSession.updated_at.desc())  # type: ignore[arg-type]
    )
    sessions = session.exec(stmt).all()
    return [
        SessionSummary(
            id=s.id,
            title=s.title,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]


def get_session_or_404(session: Session, session_id: str) -> ChatSession:
    chat_session = session.get(ChatSession, session_id)
    if chat_session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return chat_session


def get_session_messages(session: Session, session_id: str) -> list[MessageRead]:
    """Return all messages for a session in chronological order."""
    get_session_or_404(session, session_id)
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)  # type: ignore[arg-type]
    )
    messages = session.exec(stmt).all()
    return [MessageRead.model_validate(m, from_attributes=True) for m in messages]


def append_message(
    session: Session,
    session_id: str,
    role: str,
    content: str,
    sources: list | None = None,
) -> ChatMessage:
    """Add a message to a session and update the session's updated_at."""
    chat_session = get_session_or_404(session, session_id)
    msg = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        sources=json.dumps(sources) if sources else None,
    )
    session.add(msg)
    chat_session.updated_at = datetime.now(timezone.utc)
    session.add(chat_session)
    session.commit()
    session.refresh(msg)
    return msg


def delete_session(session: Session, session_id: str) -> None:
    """Delete a session and all its messages (cascade)."""
    chat_session = get_session_or_404(session, session_id)
    # Delete messages first
    stmt = select(ChatMessage).where(ChatMessage.session_id == session_id)
    for msg in session.exec(stmt).all():
        session.delete(msg)
    session.delete(chat_session)
    session.commit()


# ── Somatotype Diagnostic Assessment ─────────────────────────────────────────


def get_somatotype_questions() -> list[dict]:
    """Return the official 5-question anthropometric somatotype assessment."""
    return SOMATOTYPE_QUESTIONS


def predict_somatotype(session: Session, req: SomatotypeQuizRequest) -> SomatotypeQuizResponse:
    """Predict physiological somatotype using deterministic vote scoring and LLM synthesis."""
    q_lookup = {q["id"]: {opt["value"]: opt for opt in q["options"]} for q in SOMATOTYPE_QUESTIONS}

    votes = {"ectomorph": 0, "mesomorph": 0, "endomorph": 0}
    human_labels = {}

    answers = {
        "wrist_structure": req.wrist_structure,
        "body_frame": req.body_frame,
        "weight_tendency": req.weight_tendency,
        "muscle_definition": req.muscle_definition,
        "carb_response": req.carb_response,
    }

    for q_id, val in answers.items():
        opt = q_lookup.get(q_id, {}).get(val)
        if opt:
            arch = opt["archetype"]
            votes[arch] = votes.get(arch, 0) + 1
            human_labels[q_id] = f"{opt['label']} ({opt['detail']})"
        else:
            human_labels[q_id] = val

    # Deterministic scoring
    sorted_votes = sorted(votes.items(), key=lambda x: x[1], reverse=True)
    det_winner = sorted_votes[0][0]
    is_hybrid = len(sorted_votes) > 1 and sorted_votes[0][1] == sorted_votes[1][1]

    confidence = "high" if sorted_votes[0][1] >= 4 else ("medium" if sorted_votes[0][1] == 3 else "moderate")
    secondary = f"{sorted_votes[0][0].capitalize()}-{sorted_votes[1][0].capitalize()}" if (is_hybrid or sorted_votes[1][1] >= 2) else None

    defaults = {
        "ectomorph": {
            "summary": "Fast metabolic rate with naturally slender bone structure and high carbohydrate tolerance.",
            "training": "Prioritize heavy compound movements (squat, bench, deadlift) with 2-3 minute rest intervals and moderate volume to stimulate mass gains without excessive caloric burn.",
            "nutrition": "High carbohydrate tolerance. Caloric surplus is essential with 50-55% carbs and higher caloric density.",
            "macro_shift": "Shifts 5% of dietary fat calories into carbohydrates to fuel intense training.",
        },
        "mesomorph": {
            "summary": "Athletic, muscular bone structure with efficient glycogen storage and rapid recovery from resistance training.",
            "training": "Thrives on classic progressive overload and balanced hypertrophy splits (10-20 sets per muscle group weekly across moderate-to-high intensity).",
            "nutrition": "Balanced carbohydrate and dietary fat distribution with high protein (1.8-2.2g/kg) to maximize muscle protein synthesis.",
            "macro_shift": "Maintains standard balanced macronutrient partition for optimal strength and body composition.",
        },
        "endomorph": {
            "summary": "Sturdy, thick bone structure with higher carbohydrate sensitivity and an efficient fat-storing metabolism.",
            "training": "Benefit from higher training density, supersets, and dedicated conditioning/cardio to elevate daily energy expenditure.",
            "nutrition": "Benefit from lower carbohydrate intake with higher healthy fats and lean protein to stabilize insulin and support fat loss.",
            "macro_shift": "Shifts 5% of carbohydrate calories into healthy dietary fats to stabilize insulin and satiety.",
        },
    }

    predicted = det_winner
    summary = defaults[det_winner]["summary"]
    training = defaults[det_winner]["training"]
    nutrition = defaults[det_winner]["nutrition"]
    macro_shift = defaults[det_winner]["macro_shift"]

    # LLM Contextual Enhancement
    try:
        user_prompt = SOMATOTYPE_PREDICTION_USER_TEMPLATE.format(
            wrist_structure=human_labels.get("wrist_structure", ""),
            body_frame=human_labels.get("body_frame", ""),
            weight_tendency=human_labels.get("weight_tendency", ""),
            muscle_definition=human_labels.get("muscle_definition", ""),
            carb_response=human_labels.get("carb_response", ""),
        )
        llm = get_llm_client()
        raw_res = llm.complete(
            messages=[{"role": "user", "content": user_prompt}],
            system=SOMATOTYPE_PREDICTION_SYSTEM_PROMPT,
        )
        cleaned = raw_res.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        parsed = json.loads(cleaned.strip())

        pred_val = str(parsed.get("predicted_somatotype", "")).lower().strip()
        if pred_val in ("ectomorph", "mesomorph", "endomorph"):
            predicted = pred_val
            summary = parsed.get("traits_summary") or summary
            training = parsed.get("training_focus") or training
            nutrition = parsed.get("nutrition_focus") or nutrition
            confidence = parsed.get("confidence") or confidence
            secondary = parsed.get("secondary_traits") or secondary
            macro_shift = defaults[predicted]["macro_shift"]
    except Exception:
        pass

    profile_updated = False
    if req.auto_apply:
        profile = get_or_create_default_profile(session)
        profile.somatotype = Somatotype(predicted)
        profile.updated_at = datetime.now(timezone.utc)
        session.add(profile)
        session.commit()
        session.refresh(profile)
        profile_updated = True

    return SomatotypeQuizResponse(
        predicted_somatotype=Somatotype(predicted),
        confidence=confidence,
        secondary_traits=secondary,
        traits_summary=summary,
        training_focus=training,
        nutrition_focus=nutrition,
        macro_shift_note=macro_shift,
        profile_updated=profile_updated,
    )


# ── AI Athlete Blueprint & Profile Audit ─────────────────────────────────────

def generate_athlete_blueprint(
    session: Session,
    req: Optional[AthleteBlueprintRequest] = None,
) -> AthleteBlueprintResponse:
    """Generate an evidence-backed Athlete AI Blueprint & Profile Audit."""
    profile = get_or_create_default_profile(session)

    # Resolve active values (overrides take precedence if supplied)
    age = req.age if req and req.age is not None else profile.age
    sex = req.sex.value if req and req.sex is not None else profile.sex.value
    height_cm = req.height_cm if req and req.height_cm is not None else profile.height_cm
    weight_kg = req.weight_kg if req and req.weight_kg is not None else profile.weight_kg
    body_fat_pct = req.body_fat_pct if req and req.body_fat_pct is not None else profile.body_fat_pct
    somatotype = req.somatotype.value if req and req.somatotype is not None else profile.somatotype.value
    experience_level = req.experience_level.value if req and req.experience_level is not None else profile.experience_level.value
    goal = req.goal.value if req and req.goal is not None else profile.goal.value
    activity_level = req.activity_level.value if req and req.activity_level is not None else profile.activity_level.value

    # Compute BMI
    height_m = max(1.2, height_cm / 100.0)
    bmi = weight_kg / (height_m ** 2)

    # Compute deterministic nutrition & macro benchmarks
    macro_res = calculate(
        sex=sex,
        weight_kg=weight_kg,
        height_cm=height_cm,
        age=age,
        activity_level=activity_level,
        goal=goal,
        somatotype=somatotype if somatotype != "unknown" else "mesomorph",
        body_fat_pct=body_fat_pct,
    )

    # Lean body mass estimate
    lean_mass_kg = round(weight_kg * (1 - (body_fat_pct / 100.0)), 1) if body_fat_pct else None

    # Retrieve context from vector store
    sources: list[dict] = []
    context_str = ""
    try:
        store = get_vector_store()
        query = f"{somatotype} {goal} hypertrophy volume progressive overload recovery"
        passages = store.search_all(query, k=3, min_score=0.25)
        if passages:
            sources = [{"source": p.source, "page": p.page, "score": round(p.score, 4)} for p in passages]
            context_str = "\n".join(f"[{i+1}] {p.text}" for i, p in enumerate(passages))
    except Exception:
        pass

    if not context_str:
        context_str = (
            "Evidence Guidelines: Hypertrophy responds best to 10-20 working sets per muscle group weekly. "
            "Progressive overload via weight or reps is primary driver."
        )

    # Build prompt
    body_fat_str = f"{body_fat_pct:.1f}% (Est. Lean Mass: {lean_mass_kg} kg)" if body_fat_pct else "Not specified"
    user_prompt = ATHLETE_BLUEPRINT_USER_TEMPLATE.format(
        age=age,
        sex=sex.capitalize(),
        height_cm=height_cm,
        weight_kg=weight_kg,
        bmi=bmi,
        body_fat_pct=body_fat_str,
        somatotype=somatotype.capitalize() if somatotype != "unknown" else "General Athlete",
        experience_level=experience_level.capitalize(),
        goal=goal.replace("_", " ").capitalize(),
        activity_level=activity_level.replace("_", " ").capitalize(),
        target_kcal=round(macro_res.target_kcal),
        bmr=round(macro_res.bmr),
        tdee=round(macro_res.tdee),
        protein_g=round(macro_res.protein_g),
        carbs_g=round(macro_res.carbs_g),
        fat_g=round(macro_res.fat_g),
        context=context_str,
    )

    # Deterministic evidence-based defaults
    archetype_map = {
        "ectomorph": "Ectomorphic High-Metabolism Hypertrophy Protocol",
        "mesomorph": "Athletic Mesomorphic Progressive Overload Blueprint",
        "endomorph": "Endomorphic Metabolic Conditioning & Lean Mass Protocol",
        "unknown": "Evidence-Based Periodization Athlete Blueprint",
    }
    default_archetype = archetype_map.get(somatotype, "Evidence-Based Athlete Blueprint")

    default_strengths = [
        f"Calibrated daily energy baseline at {round(macro_res.target_kcal)} kcal with optimal {round(macro_res.protein_g)}g protein for muscle protein synthesis.",
        f"Solid training foundation with {experience_level.capitalize()} experience level geared toward {goal.replace('_', ' ')}.",
        f"Physiological Somatotype alignment ({somatotype.capitalize()}) optimizing fuel partitioning and recovery.",
    ]

    default_risks = [
        "Jumping volume too quickly above recovery limits (risk of excessive joint and CNS fatigue).",
        "Inadequate sleep (<7 hrs) impairing hormonal recovery and muscle repair.",
    ]

    mev = (
        "8-10 sets/muscle/week"
        if experience_level == "beginner"
        else ("10-12 sets/muscle/week" if experience_level == "intermediate" else "12-16 sets/muscle/week")
    )
    mrv = (
        "14-16 sets/muscle/week"
        if experience_level == "beginner"
        else ("18-20 sets/muscle/week" if experience_level == "intermediate" else "22-26 sets/muscle/week")
    )
    recovery_cap = (
        "High"
        if somatotype == "mesomorph" and age < 35
        else ("Moderate" if somatotype == "endomorph" or age < 45 else "Sensitive")
    )

    volume_landmarks = VolumeLandmarks(
        mev_sets_per_week=mev,
        mrv_sets_per_week=mrv,
        recommended_frequency="2x - 3x per muscle group weekly",
        recovery_capacity=recovery_cap,
    )

    rate_str = (
        "+0.3 kg to +0.5 kg lean mass / month"
        if goal == "hypertrophy"
        else ("-0.5 kg to -0.8 kg fat loss / week" if goal == "fat_loss" else "Progressive 1RM force output gains")
    )
    timeline_proj = TimelineProjection(
        rate_of_change=rate_str,
        milestone_12_weeks="Noticeable mechanical tension adaptations with measurable increases in multi-joint compound lift loads.",
        milestone_24_weeks="Significant body recomposition with peak neurological motor unit recruitment and consolidated lean mass.",
    )

    directives = [
        f"Lock in {round(macro_res.protein_g)}g daily protein divided across 3-5 feedings.",
        "Track progressive overload using double progression (hit top of rep range before increasing load).",
        "Implement a planned deload every 6-8 weeks when volume approaches MRV.",
    ]

    summary = (
        f"Athlete profile calibrated for {goal.replace('_', ' ')} with a daily fuel target of {round(macro_res.target_kcal)} kcal. "
        f"With an experience level of {experience_level.capitalize()} and a {somatotype.capitalize()} archetype, "
        "the optimal stimulus path prioritizes progressive tension overload within the 10-20 weekly set window."
    )

    # LLM Enhancement
    try:
        llm = get_llm_client()
        raw_res = llm.complete(
            messages=[{"role": "user", "content": user_prompt}],
            system=ATHLETE_BLUEPRINT_SYSTEM_PROMPT,
        )
        cleaned = raw_res.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        parsed = json.loads(cleaned.strip())

        if parsed.get("athlete_archetype"):
            default_archetype = str(parsed["athlete_archetype"]).strip()
        if parsed.get("executive_summary"):
            summary = str(parsed["executive_summary"]).strip()
        if parsed.get("physiological_strengths") and isinstance(parsed["physiological_strengths"], list):
            default_strengths = [str(s) for s in parsed["physiological_strengths"] if s]
        if parsed.get("blindspots_and_risks") and isinstance(parsed["blindspots_and_risks"], list):
            default_risks = [str(r) for r in parsed["blindspots_and_risks"] if r]
        if parsed.get("volume_landmarks") and isinstance(parsed["volume_landmarks"], dict):
            vl = parsed["volume_landmarks"]
            volume_landmarks = VolumeLandmarks(
                mev_sets_per_week=vl.get("mev_sets_per_week", mev),
                mrv_sets_per_week=vl.get("mrv_sets_per_week", mrv),
                recommended_frequency=vl.get("recommended_frequency", "2x - 3x per muscle group weekly"),
                recovery_capacity=vl.get("recovery_capacity", recovery_cap),
            )
        if parsed.get("timeline_projection") and isinstance(parsed["timeline_projection"], dict):
            tp = parsed["timeline_projection"]
            timeline_proj = TimelineProjection(
                rate_of_change=tp.get("rate_of_change", rate_str),
                milestone_12_weeks=tp.get("milestone_12_weeks", timeline_proj.milestone_12_weeks),
                milestone_24_weeks=tp.get("milestone_24_weeks", timeline_proj.milestone_24_weeks),
            )
        if parsed.get("key_coaching_directives") and isinstance(parsed["key_coaching_directives"], list):
            directives = [str(d) for d in parsed["key_coaching_directives"] if d]
    except Exception:
        pass

    calculated_metrics = {
        "bmi": round(bmi, 1),
        "bmr": round(macro_res.bmr),
        "tdee": round(macro_res.tdee),
        "target_kcal": round(macro_res.target_kcal),
        "protein_g": round(macro_res.protein_g),
        "carbs_g": round(macro_res.carbs_g),
        "fat_g": round(macro_res.fat_g),
        "lean_mass_kg": lean_mass_kg,
        "somatotype": somatotype,
        "goal": goal,
        "experience_level": experience_level,
    }

    return AthleteBlueprintResponse(
        athlete_archetype=default_archetype,
        executive_summary=summary,
        physiological_strengths=default_strengths,
        blindspots_and_risks=default_risks,
        volume_landmarks=volume_landmarks,
        timeline_projection=timeline_proj,
        key_coaching_directives=directives,
        calculated_metrics=calculated_metrics,
        sources=sources,
    )


