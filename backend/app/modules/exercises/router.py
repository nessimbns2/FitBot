"""
app/modules/exercises/router.py
HTTP endpoints for Exercise catalog, routine generation, and retrieval-backed form cues & body-type guidance.
"""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.core.database import get_session
from app.modules.exercises.catalog import (
    Equipment,
    Exercise,
    MovementPattern,
    MuscleGroup,
    get_catalog,
)
from app.modules.exercises.generator import (
    RoutineResult,
    SplitType,
    generate_routine,
    REP_RANGES, REST_SECONDS,
)
from app.modules.exercises.service import get_exercise, list_exercises
from app.modules.rag_core.engine import get_llm_client, get_vector_store
from app.modules.user.models import ExperienceLevel, Goal
from app.core.privacy import redact_pii, validate_llm_output
from app.modules.auth.dependencies import CurrentUser
from app.modules.exercises.models import ExerciseRecommendation, SavedRoutine, SavedRoutineRead, SavedRoutineWrite
from app.modules.exercises.planner_router import router as planner_router
from app.modules.user.service import get_or_create_profile
from app.modules.exercises.routine_state import canonical_routine
from app.modules.exercises.training_rules import eligible, fits_day, volume_target

router = APIRouter(
    prefix="/api/exercises",
    tags=["exercises"],
)

router.include_router(planner_router)


class GenerateRoutineRequest(BaseModel):
    split: Optional[SplitType] = None
    days_per_week: Optional[int] = Field(None, ge=2, le=6)
    experience_level: Optional[ExperienceLevel] = None
    goal: Optional[Goal] = None
    available_equipment: Optional[List[Equipment]] = None


class FormCueRequest(BaseModel):
    exercise_id: str
    question: Optional[str] = None


class FormCueResponse(BaseModel):
    exercise_id: str
    name: str
    setup: List[str]
    form_cues: List[str]
    common_mistakes: List[str]
    injury_prevention: List[str]
    extra_guidance: Optional[str] = None
    sources: List[Dict[str, Any]] = Field(default_factory=list)


class BodyTypeGuidanceResponse(BaseModel):
    somatotype: str
    guidance: str
    sources: List[Dict[str, Any]] = Field(default_factory=list)


class ExerciseSuggestionItem(BaseModel):
    exercise_id: str
    name: str
    primary_muscle: str
    equipment: str
    day_index: int
    day_name: str
    sets: int = 3
    rep_range: str = "8-12"
    reason: str
    rest_seconds: int = 90


class AISuggestExerciseRequest(BaseModel):
    routine: Dict[str, Any]
    goal: Optional[Goal] = None
    experience_level: Optional[ExperienceLevel] = None
    available_equipment: Optional[List[Equipment]] = None


class AISuggestExerciseResponse(BaseModel):
    is_all_good: bool
    message: str
    suggested_exercise: Optional[ExerciseSuggestionItem] = None
    volume_analysis: Dict[str, Any] = Field(default_factory=dict)


@router.get(
    "/catalog",
    response_model=List[Exercise],
    summary="List and filter exercises in the catalog",
)
def get_catalog_exercises(
    muscle: Optional[MuscleGroup] = Query(None, description="Filter by muscle group"),
    equipment: Optional[Equipment] = Query(None, description="Filter by equipment type"),
    pattern: Optional[MovementPattern] = Query(None, description="Filter by movement pattern"),
    q: Optional[str] = Query(None, description="Search query by exercise name or id"),
) -> List[Exercise]:
    """List catalog exercises with optional multi-attribute filters."""
    return list_exercises(muscle=muscle, equipment=equipment, pattern=pattern, q=q)


@router.get(
    "/catalog/{exercise_id}",
    response_model=Exercise,
    summary="Get single exercise by ID",
)
def get_single_exercise(exercise_id: str) -> Exercise:
    """Retrieve full exercise details, setup steps, cues, and mistakes."""
    exercise = get_exercise(exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exercise '{exercise_id}' not found in catalog",
        )
    return exercise


@router.post(
    "/generate-routine",
    response_model=RoutineResult,
    summary="Generate a deterministic routine",
)
def create_routine(
    request: GenerateRoutineRequest,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
) -> RoutineResult:
    """Generate a workout routine based on parameters, falling back to user profile defaults."""
    profile = get_or_create_profile(session, user.id)

    split = request.split or SplitType.PUSH_PULL_LEGS
    days_per_week = request.days_per_week or 4
    experience_level = request.experience_level or profile.experience_level
    goal = request.goal or profile.goal
    available_equipment = (
        request.available_equipment
        if request.available_equipment is not None
        else list(Equipment)
    )

    try:
        return generate_routine(
            split=split, days_per_week=days_per_week, experience_level=experience_level,
            goal=goal, available_equipment=available_equipment,
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error



@router.post(
    "/form-cue",
    response_model=FormCueResponse,
    summary="Get exercise form cues and retrieval-augmented guidance",
)
def get_form_cues(
    req: FormCueRequest,
) -> FormCueResponse:
    """Return stored setup, form cues, common mistakes, and injury prevention from catalog,
    plus extra guidance from exercise guides if available.
    """
    exercise = get_exercise(req.exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exercise '{req.exercise_id}' not found in catalog",
        )

    extra_guidance: Optional[str] = None
    sources: List[Dict[str, Any]] = []

    # Check for pain or injury note
    pain_warning = ""
    if req.question and any(w in req.question.lower() for w in ["pain", "hurt", "injury", "ache", "strain", "tear"]):
        pain_warning = (
            "NOTICE: If you are experiencing sharp or persistent pain, discontinue this movement "
            "and see a qualified physical therapist or sports medicine professional before continuing. "
            "Do not attempt to push through injury.\n\n"
        )

    # Retrieval from category='exercise'
    try:
        store = get_vector_store()
        query = exercise.name
        if req.question:
            query = f"{exercise.name} {req.question}"

        passages = store.search(query, category="exercise", k=4)
        if passages:
            sources = [{"source": p.source, "page": p.page, "score": round(p.score, 4)} for p in passages]
            llm = get_llm_client()
            context_str = "\n".join(f"[{i+1}] {p.text}" for i, p in enumerate(passages))
            sys = (
                f"You are an expert exercise coach. Provide 2-3 focused coaching tips for {exercise.name}. "
                f"Reference context: {context_str}"
            )
            question = redact_pii(req.question) if req.question else f"How to optimize form for {exercise.name}?"
            guidance_text = validate_llm_output(
                llm.complete(messages=[{"role": "user", "content": question}], system=sys)
            )
            extra_guidance = f"{pain_warning}{guidance_text}".strip()
        elif pain_warning:
            extra_guidance = pain_warning.strip()

    except Exception:
        # Graceful fallback: return catalog data with extra_guidance as pain warning or None
        extra_guidance = pain_warning.strip() if pain_warning else None

    return FormCueResponse(
        exercise_id=exercise.id,
        name=exercise.name,
        setup=exercise.setup,
        form_cues=exercise.form_cues,
        common_mistakes=exercise.common_mistakes,
        injury_prevention=exercise.injury_prevention,
        extra_guidance=extra_guidance,
        sources=sources,
    )


@router.get(
    "/body-type-guidance",
    response_model=BodyTypeGuidanceResponse,
    summary="Get body-type training guidance from guides",
)
def get_body_type_guidance(
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
) -> BodyTypeGuidanceResponse:
    """Retrieve exercise-category guidance tailored to user profile somatotype."""
    profile = get_or_create_profile(session, user.id)
    somatotype = profile.somatotype.value

    guidance = f"Guidance for {somatotype}: prioritize progressive compound movements and adequate recovery."
    sources: List[Dict[str, Any]] = []

    try:
        store = get_vector_store()
        passages = store.search(f"{somatotype} body type training and workout guidelines", category="exercise", k=3)
        if passages:
            sources = [{"source": p.source, "page": p.page, "score": round(p.score, 4)} for p in passages]
            llm = get_llm_client()
            from app.prompts import SOMATOTYPE_EXERCISE_USER_TEMPLATE
            context_str = "\n".join(f"[{i+1}] {p.text}" for i, p in enumerate(passages))
            guidance = validate_llm_output(
                llm.complete(
                    messages=[{"role": "user", "content": SOMATOTYPE_EXERCISE_USER_TEMPLATE.format(somatotype=somatotype)}],
                    system=f"Context:\n{context_str}",
                ),
                fallback=guidance,
            )
    except Exception:
        pass

    return BodyTypeGuidanceResponse(
        somatotype=somatotype,
        guidance=guidance,
        sources=sources,
    )


@router.post(
    "/ai-suggest-exercise",
    response_model=AISuggestExerciseResponse,
    summary="AI analysis of routine balance and exercise suggestion",
)
def ai_suggest_exercise(req: AISuggestExerciseRequest, user: CurrentUser, session: Annotated[Session, Depends(get_session)]) -> AISuggestExerciseResponse:
    """Suggest only additions compatible with the same level, equipment and session rules as generation."""
    profile = get_or_create_profile(session, user.id)
    level, goal = req.experience_level or profile.experience_level, req.goal or profile.goal
    try:
        routine = canonical_routine(req.routine, level, goal, req.available_equipment)
    except (ValueError, TypeError) as error:
        raise HTTPException(422, str(error)) from error
    days = routine["days"]
    if not days:
        return AISuggestExerciseResponse(is_all_good=False, message="No workout days found. Generate a routine first.")
    weekly_sets = routine["weekly_sets_per_muscle"]
    bounds = routine["volume_target"]
    analysis = {"weekly_sets": weekly_sets, "target": bounds, "counting": "primary_muscle_only"}
    if any(count > bounds["maximum"] for count in weekly_sets.values()):
        return AISuggestExerciseResponse(is_all_good=False, message="Some muscles exceed the configured planning range. Review the sets before adding exercises.", volume_analysis=analysis)
    deficits = sorted(((muscle, bounds["minimum"] - count) for muscle, count in weekly_sets.items() if count < bounds["minimum"]), key=lambda item: (-item[1], item[0]))
    if not deficits:
        return AISuggestExerciseResponse(is_all_good=True, message="All good: primary-muscle volume is within the configured planning range. This does not assess technique, recovery or medical suitability.", volume_analysis=analysis)
    catalog = get_catalog()
    equipment = [Equipment(value) for value in routine["available_equipment"]]
    existing = {item["exercise_id"] for day in days for item in day["exercises"]}
    choice = None
    for muscle, deficit in deficits:
        candidates = sorted((ex for ex in catalog.values() if ex.primary_muscle.value == muscle and ex.id not in existing and eligible(ex, equipment, level)), key=lambda ex: (not ex.is_compound, ex.id))
        for exercise in candidates:
            possible_days = [(index, day) for index, day in enumerate(days) if len(day["exercises"]) < 20 and fits_day(exercise, day.get("name", ""), day.get("focus", ""))]
            if possible_days:
                index, day = min(possible_days, key=lambda item: (sum(ex["sets"] for ex in item[1]["exercises"]), item[0]))
                choice = (exercise, index, day, min(3, deficit, bounds["maximum"] - weekly_sets[muscle]))
                break
        if choice: break
    if not choice:
        return AISuggestExerciseResponse(is_all_good=False, message="Volume gaps remain, but no additional exercise matches the equipment, experience and existing session focus. Review sets, available equipment or the split.", volume_analysis=analysis)
    exercise, index, day, sets = choice
    kind = "compound" if exercise.is_compound else "isolation"
    rep_range, rest_seconds = REP_RANGES[goal][kind], REST_SECONDS[goal][kind]
    muscle = exercise.primary_muscle.value
    reason = f"{muscle.capitalize()} has {weekly_sets[muscle]} planned sets (configured range {bounds['minimum']}–{bounds['maximum']}). Adding {sets} sets of {exercise.name} fits your equipment, experience and this session's focus."
    try:
        from app.prompts import ROUTINE_SUGGESTION_SYSTEM_PROMPT, ROUTINE_SUGGESTION_USER_TEMPLATE
        user_msg = ROUTINE_SUGGESTION_USER_TEMPLATE.format(
            current_sets=weekly_sets[muscle], target_muscle=muscle, target_sets=bounds["minimum"],
            maximum_sets=bounds["maximum"], exercise_name=exercise.name, rep_range=rep_range,
            target_day_name=f"Day {index + 1}", goal=goal.value, sets=sets,
        )
        answer = get_llm_client().complete(messages=[{"role": "user", "content": user_msg}], system=ROUTINE_SUGGESTION_SYSTEM_PROMPT)
        # Keep computed constraints as the authoritative rationale, with prose clearly additional.
        answer = validate_llm_output(answer)
        if answer: reason += " Coach note: " + answer
    except Exception:
        pass
    return AISuggestExerciseResponse(
        is_all_good=False, message="An eligible addition is available for a volume gap.",
        suggested_exercise=ExerciseSuggestionItem(exercise_id=exercise.id, name=exercise.name,
            primary_muscle=muscle, equipment=exercise.equipment.value, day_index=index,
            day_name=day.get("name", f"Day {index + 1}"), sets=sets, rep_range=rep_range,
            rest_seconds=rest_seconds, reason=reason), volume_analysis=analysis,
    )


# ── Saved routine (stored in the database, per user) ──────────────────────────


@router.get("/routine", response_model=Optional[SavedRoutineRead], summary="Get the user's saved routine")
def get_saved_routine(user: CurrentUser, session: Annotated[Session, Depends(get_session)]):
    """Return the routine the user is following, or null if none was saved yet."""
    saved = session.exec(select(SavedRoutine).where(SavedRoutine.user_id == user.id)).first()
    if saved is None: return None
    profile = get_or_create_profile(session, user.id)
    routine = canonical_routine(saved.routine, profile.experience_level, profile.goal, strict=False)
    return SavedRoutineRead(split=saved.split, days_per_week=saved.days_per_week, routine=routine, updated_at=saved.updated_at)


@router.put("/routine", response_model=SavedRoutineRead, summary="Save (replace) the user's routine")
def save_routine(
    data: SavedRoutineWrite,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
):
    if not isinstance(data.routine.get("days"), list):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Routine must contain a 'days' list.")
    profile = get_or_create_profile(session, user.id)
    try:
        data.routine = canonical_routine(data.routine, profile.experience_level, profile.goal)
    except (ValueError, TypeError) as error:
        raise HTTPException(422, str(error)) from error
    saved = session.exec(select(SavedRoutine).where(SavedRoutine.user_id == user.id)).first()
    if saved is None:
        saved = SavedRoutine(user_id=user.id, split=data.split, days_per_week=data.days_per_week, routine=data.routine)  # type: ignore[arg-type]
    else:
        previous_ids = {ex.get("exercise_id") for day in saved.routine.get("days", []) for ex in day.get("exercises", [])}
        next_ids = {ex.get("exercise_id") for day in data.routine.get("days", []) if isinstance(day, dict)
                    for ex in day.get("exercises", []) if isinstance(ex, dict)}
        removed = previous_ids - next_ids
        if removed:
            # Only previously accepted suggestions become replacement feedback.
            # Other unselected or merely viewed exercises are never labelled.
            accepted = session.exec(select(ExerciseRecommendation).where(
                ExerciseRecommendation.user_id == user.id,
                ExerciseRecommendation.exercise_id.in_(removed),
                ExerciseRecommendation.feedback == "accepted",
            )).all()
            for recommendation in accepted:
                recommendation.feedback = "replaced"
                recommendation.feedback_at = datetime.now(timezone.utc)
                session.add(recommendation)
        saved.split = data.split
        saved.days_per_week = data.days_per_week
        saved.routine = data.routine
        saved.updated_at = datetime.now(timezone.utc)
    session.add(saved)
    session.commit()
    session.refresh(saved)
    return saved


@router.delete("/routine", status_code=status.HTTP_204_NO_CONTENT, summary="Forget the user's saved routine")
def delete_saved_routine(user: CurrentUser, session: Annotated[Session, Depends(get_session)]):
    saved = session.exec(select(SavedRoutine).where(SavedRoutine.user_id == user.id)).first()
    if saved is not None:
        session.delete(saved)
        session.commit()
