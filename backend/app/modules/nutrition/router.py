"""
app/modules/nutrition/router.py
HTTP layer for the Nutrition module: macro calculation, meal planning, and retrieval-backed nutrition guidance.
"""

from __future__ import annotations

import base64
import json
import re
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

# Food log CRUD (POST/GET/PUT/DELETE /api/nutrition/log)
from app.modules.nutrition.log_router import router as food_log_router  # noqa: E402

router.include_router(food_log_router)


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


class FoodItemAnalysis(BaseModel):
    name: str
    portion_est: str
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float


class MealScanRequest(BaseModel):
    image_base64: str
    mime_type: Optional[str] = "image/jpeg"
    meal_slot: Optional[str] = None  # e.g., "Breakfast", "Lunch", "Dinner", "Snack"


class MealScanResponse(BaseModel):
    meal_name: str
    confidence: str
    total_calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    food_items: List[FoodItemAnalysis] = Field(default_factory=list)
    coaching_tip: Optional[str] = None


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


@router.post(
    "/scan-meal",
    response_model=MealScanResponse,
    summary="Scan meal photo using Gemini Vision to extract foods, portions, and macros",
)
def scan_meal(
    req: MealScanRequest,
) -> MealScanResponse:
    """Analyze a food/meal photo and return estimated calories, macronutrients, and food item breakdown."""
    # 1. Clean base64 input if data URL prefix is attached
    raw_b64 = req.image_base64
    if "," in raw_b64:
        raw_b64 = raw_b64.split(",", 1)[1]

    try:
        image_bytes = base64.b64decode(raw_b64)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64 encoded image data.",
        )

    if len(image_bytes) < 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image data is too small or empty.",
        )

    mime_type = req.mime_type or "image/jpeg"
    meal_slot_context = f" (Tagged as: {req.meal_slot})" if req.meal_slot else ""

    # 2. Vision prompt enforcing strictly structured JSON
    from app.prompts import MEAL_SCAN_VISION_PROMPT

    prompt = MEAL_SCAN_VISION_PROMPT.format(meal_slot_context=meal_slot_context)

    # 3. Check that the AI is configured: never invent a result.
    from app.core.config import settings

    if not settings.LLM_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Meal scanning needs an AI key. Set LLM_API_KEY in the backend .env file.",
        )

    # 4. Call Gemini Vision
    try:
        response_text = _call_vision_model(image_bytes, mime_type, prompt)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI vision service could not be reached. Please try again.",
        )

    # 5. Read the answer. If it is unusable, say so instead of showing made-up numbers.
    try:
        return MealScanResponse(**_parse_scan_json(response_text))
    except (ValueError, TypeError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI returned an answer that could not be read. Try a clearer photo.",
        )


def _call_vision_model(image_bytes: bytes, mime_type: str, prompt: str) -> str:
    """Send the photo to Gemini and return its raw text answer.

    Kept separate so tests can replace it without any network access.
    """
    import google.generativeai as genai
    from app.core.config import settings

    genai.configure(api_key=settings.LLM_API_KEY)
    vision_model_name = getattr(settings, "LLM_MODEL", "gemini-3.5-flash-lite")
    if vision_model_name in ("gemini-2.0-flash", "gemini-2.5-flash"):
        vision_model_name = "gemini-3.5-flash-lite"
    model = genai.GenerativeModel(vision_model_name)
    response = model.generate_content([{"mime_type": mime_type, "data": image_bytes}, prompt])
    return response.text.strip()


def _parse_scan_json(text: str) -> dict:
    """Extract the JSON object from the AI text (it may be wrapped in code fences)."""
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        raise ValueError("no JSON object in AI answer")
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("AI answer is not a JSON object")

    # The AI sometimes sends decimals for calories; the schema wants whole numbers.
    if isinstance(data.get("total_calories"), float):
        data["total_calories"] = round(data["total_calories"])
    for item in data.get("food_items") or []:
        if isinstance(item, dict) and isinstance(item.get("calories"), float):
            item["calories"] = round(item["calories"])
    return data
