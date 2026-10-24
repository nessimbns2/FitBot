"""
app/modules/nutrition/router.py
HTTP layer for the Nutrition module: macro calculation, meal planning, and retrieval-backed nutrition guidance.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from sqlmodel import Session

from app.core.database import get_session
from app.modules.nutrition import service as svc
from app.modules.nutrition.calculator import MacroResult
from app.modules.nutrition.service import MacroRequest, MealPlanResult
from app.modules.rag_core.engine import (
    SearchResult,
    build_prompt,
    get_llm_client,
    get_vector_store,
)
from app.modules.user.service import get_or_create_default_profile

SessionDep = Annotated[Session, Depends(get_session)]

router = APIRouter(
    prefix="/api/nutrition",
    tags=["nutrition"],
)


# ── Request / Response Bodies ─────────────────────────────────────────────────

class MacroRequestBody(BaseModel):
    sex: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=14, le=100)
    height_cm: Optional[float] = Field(default=None, ge=120.0, le=230.0)
    weight_kg: Optional[float] = Field(default=None, ge=30.0, le=300.0)
    body_fat_pct: Optional[float] = Field(default=None, ge=3.0, le=60.0)
    activity_level: Optional[str] = None
    goal: Optional[str] = None
    somatotype: Optional[str] = None
    unit_system: Optional[str] = None
    weight_unit: Optional[str] = None


class MealPlanRequestBody(MacroRequestBody):
    meals_per_day: int = Field(default=4, ge=3, le=6)
    training_time: Optional[str] = None  # e.g. "08:00"
    include_guidance: Optional[bool] = False


class NutritionAskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None


class NutritionAskResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/calculate-macros")
def calculate_macros(body: MacroRequestBody, session: SessionDep) -> dict:
    """Calculate TDEE and macro targets, merging overrides with the stored profile."""
    request = MacroRequest(**body.model_dump())
    result = svc.calculate_macros(request, session)
    return {
        "bmr": result.bmr,
        "bmr_formula": result.bmr_formula,
        "tdee": result.tdee,
        "target_kcal": result.target_kcal,
        "protein_g": result.protein_g,
        "carbs_g": result.carbs_g,
        "fat_g": result.fat_g,
        "floor_applied": result.floor_applied,
        "warnings": result.warnings,
    }


@router.post("/plan")
def meal_plan(
    body: MealPlanRequestBody,
    session: SessionDep,
    include_guidance: Optional[bool] = Query(None),
) -> dict:
    """Calculate macros and split them across meal slots, optionally adding retrieved guidance."""
    req_dict = body.model_dump()
    should_include_guidance = (
        include_guidance if include_guidance is not None else body.include_guidance or False
    )

    clean_dict = {
        k: v for k, v in req_dict.items()
        if k not in ("meals_per_day", "training_time", "include_guidance")
    }
    request = MacroRequest(**clean_dict)
    macros = svc.calculate_macros(request, session)

    profile = get_or_create_default_profile(session)
    weight_kg = body.weight_kg or profile.weight_kg
    goal = body.goal or profile.goal.value

    plan = svc.build_meal_plan(
        macros=macros,
        meals_per_day=body.meals_per_day,
        training_time=body.training_time,
        goal=goal,
        weight_kg=weight_kg,
    )

    response_data: dict[str, Any] = {
        "macros": {
            "bmr": macros.bmr,
            "bmr_formula": macros.bmr_formula,
            "tdee": macros.tdee,
            "target_kcal": macros.target_kcal,
            "protein_g": macros.protein_g,
            "carbs_g": macros.carbs_g,
            "fat_g": macros.fat_g,
            "floor_applied": macros.floor_applied,
            "warnings": macros.warnings,
        },
        "meals": [
            {
                "label": m.label,
                "time_hint": m.time_hint,
                "protein_g": m.protein_g,
                "carbs_g": m.carbs_g,
                "fat_g": m.fat_g,
                "kcal": m.kcal,
            }
            for m in plan.meals
        ],
        "hydration_ml": plan.hydration_ml,
    }

    if should_include_guidance:
        store = get_vector_store()
        guidance: dict[str, Any] = {}
        try:
            timing_passages = store.search("nutrient timing pre post workout carbohydrate", category="nutrition", k=2)
            hydration_passages = store.search("hydration fluid intake daily water water per kilogram", category="nutrition", k=2)
            supps_passages = store.search("dietary supplements whey creatine vitamins", category="nutrition", k=2)

            llm = get_llm_client()
            if timing_passages:
                timing_text = llm.complete(
                    messages=[{"role": "user", "content": "Summarize meal timing around training in 2 sentences."}],
                    system=f"Passages:\n" + "\n".join(p.text for p in timing_passages),
                )
                guidance["meal_timing"] = {
                    "text": timing_text,
                    "sources": [{"source": p.source, "page": p.page} for p in timing_passages],
                }

            if hydration_passages:
                hydration_text = llm.complete(
                    messages=[{"role": "user", "content": "Summarize daily hydration guidance in 2 sentences."}],
                    system=f"Passages:\n" + "\n".join(p.text for p in hydration_passages),
                )
                guidance["hydration"] = {
                    "text": hydration_text,
                    "sources": [{"source": p.source, "page": p.page} for p in hydration_passages],
                }

            if supps_passages:
                supps_text = llm.complete(
                    messages=[{"role": "user", "content": "Summarize core evidence-based supplements in 2 sentences."}],
                    system=f"Passages:\n" + "\n".join(p.text for p in supps_passages),
                )
                guidance["supplements"] = {
                    "text": supps_text,
                    "sources": [{"source": p.source, "page": p.page} for p in supps_passages],
                }

        except Exception:
            pass

        response_data["guidance"] = guidance

    return response_data


@router.post("/ask", response_model=NutritionAskResponse, summary="Ask nutrition-specific question")
async def ask_nutrition(
    req: NutritionAskRequest,
    session: SessionDep,
    stream: bool = Query(False),
):
    """Retrieve ONLY from category 'nutrition' and answer nutrition question."""
    store = get_vector_store()

    try:
        passages = store.search(req.question, category="nutrition", k=5)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector index for category 'nutrition' not found. Please run the ingestion command: python -m app.modules.rag_core.ingest",
        )

    # Calculate exact numbers to inject
    profile = get_or_create_default_profile(session)
    macros = svc.calculate_macros(MacroRequest(), session)
    facts = f"Age: {profile.age}, Sex: {profile.sex.value}, Weight: {profile.weight_kg} kg, Goal: {profile.goal.value}"
    numbers = (
        f"Target Calories: {macros.target_kcal:.0f} kcal, "
        f"Protein: {macros.protein_g:.1f}g, Carbs: {macros.carbs_g:.1f}g, Fat: {macros.fat_g:.1f}g"
    )

    system_prompt, history = build_prompt(
        intent="nutrition",
        facts=facts,
        numbers=numbers,
        passages=passages,
        history=[{"role": "user", "content": req.question}],
    )

    sources_data = [
        {"source": p.source, "page": p.page, "score": round(p.score, 4)}
        for p in passages
    ]

    llm = get_llm_client()

    if stream:
        async def event_generator() -> AsyncIterator[Dict[str, str]]:
            try:
                yield {
                    "event": "meta",
                    "data": json.dumps({"intent": "nutrition"}),
                }
                yield {
                    "event": "sources",
                    "data": json.dumps(sources_data),
                }
                async for token in llm.stream(
                    messages=[{"role": "user", "content": req.question}],
                    system=system_prompt,
                ):
                    yield {
                        "event": "token",
                        "data": json.dumps({"token": token}),
                    }
                yield {
                    "event": "done",
                    "data": json.dumps({"status": "complete"}),
                }
            except Exception:
                yield {
                    "event": "error",
                    "data": json.dumps({"error": "Failed during streaming response."}),
                }

        return EventSourceResponse(event_generator())

    answer = llm.complete(
        messages=[{"role": "user", "content": req.question}],
        system=system_prompt,
    )

    return NutritionAskResponse(answer=answer, sources=sources_data)
