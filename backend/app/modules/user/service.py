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
    ChatMessage,
    ChatSession,
    MessageRead,
    SessionSummary,
    Somatotype,
    SomatotypeQuizRequest,
    SomatotypeQuizResponse,
    UserProfile,
    UserProfileUpdate,
)
from app.modules.rag_core.engine import get_llm_client
from app.prompts import (
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

