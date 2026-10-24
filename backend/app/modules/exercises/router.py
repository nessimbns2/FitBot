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
