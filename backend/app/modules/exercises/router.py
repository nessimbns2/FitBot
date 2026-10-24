"""
app/modules/exercises/router.py
HTTP endpoints for Exercise catalog, routine generation, and retrieval-backed form cues & body-type guidance.
"""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlmodel import Session

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
)
from app.modules.exercises.service import get_exercise, list_exercises
from app.modules.rag_core.engine import get_llm_client, get_vector_store
from app.modules.user.models import ExperienceLevel, Goal
from app.modules.user.service import get_or_create_default_profile

router = APIRouter(
    prefix="/api/exercises",
    tags=["exercises"],
)


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


class AISuggestExerciseRequest(BaseModel):
    routine: Dict[str, Any]
    goal: Optional[str] = "hypertrophy"
    experience_level: Optional[str] = "intermediate"


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
    session: Annotated[Session, Depends(get_session)],
) -> RoutineResult:
    """Generate a workout routine based on parameters, falling back to user profile defaults."""
    profile = get_or_create_default_profile(session)

    split = request.split or SplitType.PUSH_PULL_LEGS
    days_per_week = request.days_per_week or 4
    experience_level = request.experience_level or profile.experience_level
    goal = request.goal or profile.goal
    available_equipment = (
        request.available_equipment
        if request.available_equipment is not None
        else list(Equipment)
    )

    return generate_routine(
        split=split,
        days_per_week=days_per_week,
        experience_level=experience_level,
        goal=goal,
        available_equipment=available_equipment,
    )


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
            guidance_text = llm.complete(
                messages=[{"role": "user", "content": req.question or f"How to optimize form for {exercise.name}?"}],
                system=sys,
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
    session: Annotated[Session, Depends(get_session)],
) -> BodyTypeGuidanceResponse:
    """Retrieve exercise-category guidance tailored to user profile somatotype."""
    profile = get_or_create_default_profile(session)
    somatotype = profile.somatotype.value

    guidance = f"Guidance for {somatotype}: prioritize progressive compound movements and adequate recovery."
    sources: List[Dict[str, Any]] = []

    try:
        store = get_vector_store()
        passages = store.search(f"{somatotype} body type training and workout guidelines", category="exercise", k=3)
        if passages:
            sources = [{"source": p.source, "page": p.page, "score": round(p.score, 4)} for p in passages]
            llm = get_llm_client()
            context_str = "\n".join(f"[{i+1}] {p.text}" for i, p in enumerate(passages))
            guidance = llm.complete(
                messages=[{"role": "user", "content": f"Summarize key training advice for an {somatotype}."}],
                system=f"Context:\n{context_str}",
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
def ai_suggest_exercise(
    req: AISuggestExerciseRequest,
) -> AISuggestExerciseResponse:
    """Analyze current routine volume, muscle balance, and suggest an exercise to add or confirm all is good."""
    days = req.routine.get("days", [])
    if not days:
        return AISuggestExerciseResponse(
            is_all_good=False,
            message="No workout days found in your routine to analyze. Generate or add workout days first.",
            volume_analysis={},
        )

    catalog = get_catalog()
    weekly_sets: Dict[str, int] = {}
    existing_exercise_ids: set[str] = set()

    for day in days:
        for ex in day.get("exercises", []):
            ex_id = ex.get("exercise_id") or ex.get("id") or ""
            if ex_id:
                existing_exercise_ids.add(ex_id)

            cat_ex = catalog.get(ex_id)
            muscle = ex.get("primary_muscle") or (cat_ex.primary_muscle.value if cat_ex else "other")
            try:
                num_sets = int(ex.get("sets", 3))
            except (ValueError, TypeError):
                num_sets = 3
            weekly_sets[muscle] = weekly_sets.get(muscle, 0) + num_sets

    # Define evidence-based hypertrophy volume targets (10-20 sets)
    thresholds = {
        "chest": 10,
        "back": 10,
        "quads": 10,
        "hamstrings": 8,
        "delts": 10,
        "arms": 8,
        "core": 6,
    }

    if req.experience_level == "beginner":
        thresholds = {k: max(6, v - 3) for k, v in thresholds.items()}
    elif req.goal == "strength":
        thresholds = {"chest": 8, "back": 8, "quads": 8, "hamstrings": 6, "delts": 8, "arms": 6, "core": 6}

    # Find deficits
    deficits: List[tuple[str, int, int, int]] = []
    for muscle, target in thresholds.items():
        current = weekly_sets.get(muscle, 0)
        if current < target:
            deficits.append((muscle, target - current, current, target))

    # Sort largest deficit first
    deficits.sort(key=lambda x: x[1], reverse=True)

    # Check if balanced
    if not deficits:
        return AISuggestExerciseResponse(
            is_all_good=True,
            message="It's all good! Your routine is well-balanced across all major muscle groups and meets the 10–20 weekly set hypertrophy target. No additional exercise is needed.",
            suggested_exercise=None,
            volume_analysis={
                "weekly_sets": weekly_sets,
                "status": "optimal",
                "summary": "All muscle groups hit their target weekly volume.",
            },
        )

    # Pick candidate from catalog
    chosen_ex: Optional[Exercise] = None
    target_muscle = deficits[0][0]
    current_sets = deficits[0][2]
    target_sets = deficits[0][3]

    for m_def, _, cur, tgt in deficits:
        candidates = [
            ex for ex in catalog.values()
            if (ex.primary_muscle.value == m_def or m_def in [m.value for m in ex.secondary_muscles])
            and ex.id not in existing_exercise_ids
        ]
        if candidates:
            # Prefer compound exercises matching the primary muscle
            candidates.sort(key=lambda x: (x.primary_muscle.value == m_def, x.is_compound), reverse=True)
            chosen_ex = candidates[0]
            target_muscle = m_def
            current_sets = cur
            target_sets = tgt
            break

    if not chosen_ex:
        return AISuggestExerciseResponse(
            is_all_good=True,
            message="It's all good! Your routine covers all primary movement patterns available in the catalog. No further exercises needed.",
            suggested_exercise=None,
            volume_analysis={"weekly_sets": weekly_sets, "status": "sufficient"},
        )

    # Determine optimal day to add
    keywords_map = {
        "chest": ["push", "chest", "upper"],
        "delts": ["push", "shoulder", "delt", "upper"],
        "arms": ["push", "pull", "arm", "upper"],
        "back": ["pull", "back", "upper"],
        "quads": ["leg", "lower", "quad"],
        "hamstrings": ["leg", "lower", "posterior", "hamstring"],
        "core": ["core", "abs", "full", "lower"],
    }
    keywords = keywords_map.get(target_muscle, [])
    target_day_index = 0
    target_day_name = days[0].get("name", "Day 1")
    matched = False

    for idx, d in enumerate(days):
        d_text = f"{d.get('name', '')} {d.get('focus', '')}".lower()
        if any(kw in d_text for kw in keywords):
            target_day_index = idx
            target_day_name = d.get("name", f"Day {idx + 1}")
            matched = True
            break

    if not matched:
        fewest_idx = min(range(len(days)), key=lambda i: len(days[i].get("exercises", [])))
        target_day_index = fewest_idx
        target_day_name = days[fewest_idx].get("name", f"Day {fewest_idx + 1}")

    rep_range = "8-12" if req.goal == "hypertrophy" else "6-8"
    default_reason = (
        f"{target_muscle.capitalize()} currently has only {current_sets} weekly sets (target is {target_sets}–20 sets). "
        f"Adding {chosen_ex.name} to {target_day_name} delivers 3 high-stimulus sets to bridge your volume gap without overloading recovery."
    )

    reason = default_reason
    try:
        llm = get_llm_client()
        sys_prompt = "You are an elite evidence-based fitness coach. Provide a concise 1-2 sentence rationale for adding an exercise to a routine."
        user_msg = (
            f"The user's routine currently has only {current_sets} weekly sets for {target_muscle} (target is {target_sets}-20 sets). "
            f"Why is adding {chosen_ex.name} (3 sets of {rep_range}) to {target_day_name} the ideal addition for their {req.goal} goal?"
        )
        ai_resp = llm.complete(messages=[{"role": "user", "content": user_msg}], system=sys_prompt)
        if ai_resp and len(ai_resp.strip()) > 10:
            reason = ai_resp.strip()
    except Exception:
        pass

    return AISuggestExerciseResponse(
        is_all_good=False,
        message=f"We found an opportunity to balance your {target_muscle} volume.",
        suggested_exercise=ExerciseSuggestionItem(
            exercise_id=chosen_ex.id,
            name=chosen_ex.name,
            primary_muscle=chosen_ex.primary_muscle.value,
            equipment=chosen_ex.equipment.value,
            day_index=target_day_index,
            day_name=target_day_name,
            sets=3,
            rep_range=rep_range,
            reason=reason,
        ),
        volume_analysis={
            "weekly_sets": weekly_sets,
            "target_muscle": target_muscle,
            "current_sets": current_sets,
            "target_sets": target_sets,
        },
    )
