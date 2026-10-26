"""
app/modules/nutrition/router.py
HTTP layer for the Nutrition module: macro calculation, meal planning, and retrieval-backed nutrition guidance.
"""


import base64
import json
import re
from collections.abc import AsyncIterator
from datetime import date, datetime, timezone
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.rate_limit import limiter
from app.modules.nutrition import service as svc
from app.modules.nutrition.calculator import MacroResult
from app.modules.nutrition.service import MacroRequest, MealPlanResult
from app.core.privacy import redact_pii, validate_llm_output
from app.modules.rag_core.engine import (
    LLMUnavailableError,
    SearchResult,
    classify_llm_error,
    build_prompt,
    degraded_answer,
    get_llm_client,
    get_vector_store,
)
from app.modules.auth.dependencies import CurrentUser
from app.modules.nutrition.models import MealLog, MealLogCreate, MealLogRead
from app.modules.user.service import get_or_create_profile

SessionDep = Annotated[Session, Depends(get_session)]

MAX_SCAN_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_SCAN_MIME_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}

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
    ai_status: str = "ok"


class FoodItemAnalysis(BaseModel):
    name: str = Field(max_length=200)
    portion_est: str = Field(default="", max_length=100)
    calories: int = Field(ge=0, le=5000)
    protein_g: float = Field(ge=0, le=500)
    carbs_g: float = Field(ge=0, le=500)
    fat_g: float = Field(ge=0, le=500)


class MealScanRequest(BaseModel):
    image_base64: str
    mime_type: Optional[str] = "image/jpeg"
    meal_slot: Optional[str] = None  # e.g., "Breakfast", "Lunch", "Dinner", "Snack"


class MealScanResponse(BaseModel):
    meal_name: str = Field(max_length=200)
    confidence: str = Field(max_length=20)
    total_calories: int = Field(ge=0, le=10000)
    protein_g: float = Field(ge=0, le=1000)
    carbs_g: float = Field(ge=0, le=1000)
    fat_g: float = Field(ge=0, le=1000)
    food_items: List[FoodItemAnalysis] = Field(default_factory=list)
    coaching_tip: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/calculate-macros")
def calculate_macros(body: MacroRequestBody, user: CurrentUser, session: SessionDep) -> dict:
    """Calculate TDEE and macro targets, merging overrides with the stored profile."""
    request = MacroRequest(**body.model_dump())
    result = svc.calculate_macros(request, session, user.id)
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
    user: CurrentUser,
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
    macros = svc.calculate_macros(request, session, user.id)

    profile = get_or_create_profile(session, user.id)
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
    user: CurrentUser,
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
    profile = get_or_create_profile(session, user.id)
    macros = svc.calculate_macros(MacroRequest(), session, user.id)
    # Never forward raw personal data to the LLM (emails, phone numbers, the user's name…).
    question = redact_pii(req.question, known_names=[user.full_name])
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
        history=[{"role": "user", "content": question}],
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
                    messages=[{"role": "user", "content": question}],
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
            except LLMUnavailableError as err:
                yield {
                    "event": "token",
                    "data": json.dumps({"token": degraded_answer(err, passages)}),
                }
                yield {
                    "event": "done",
                    "data": json.dumps({"status": "complete", "ai_status": err.reason}),
                }
            except Exception:
                yield {
                    "event": "error",
                    "data": json.dumps({"error": "Failed during streaming response."}),
                }

        return EventSourceResponse(event_generator())

    try:
        answer = validate_llm_output(
            llm.complete(messages=[{"role": "user", "content": question}], system=system_prompt)
        )
        if not answer:
            raise LLMUnavailableError("blocked")
        ai_status = "ok"
    except LLMUnavailableError as err:
        answer = degraded_answer(err, passages)
        ai_status = err.reason

    return NutritionAskResponse(answer=answer, sources=sources_data, ai_status=ai_status)


@router.post(
    "/scan-meal",
    response_model=MealScanResponse,
    summary="Scan meal photo using Gemini Vision to extract foods, portions, and macros",
)
@limiter.limit("10/minute")
def scan_meal(
    request: Request,
    req: MealScanRequest,
    user: CurrentUser,
) -> MealScanResponse:
    """Analyze a food/meal photo and return estimated calories, macronutrients, and food item breakdown.

    The image is sent to the vision model only; it is never stored. The model output is parsed
    as JSON and validated (types and plausible ranges) before being returned.
    """
    # 1. Clean base64 input if data URL prefix is attached
    raw_b64 = req.image_base64
    if "," in raw_b64:
        raw_b64 = raw_b64.split(",", 1)[1]

    try:
        image_bytes = base64.b64decode(raw_b64, validate=True)
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
    if len(image_bytes) > MAX_SCAN_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image is too large (max 8 MB).",
        )

    mime_type = req.mime_type or "image/jpeg"
    if mime_type not in ALLOWED_SCAN_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPEG, PNG and WEBP images are supported.",
        )
    meal_slot_context = f" (Tagged as: {req.meal_slot})" if req.meal_slot else ""

    # 2. Vision prompt enforcing strictly structured JSON
    from app.prompts import MEAL_SCAN_VISION_PROMPT

    prompt = MEAL_SCAN_VISION_PROMPT.format(meal_slot_context=meal_slot_context)

    # 3. Call Gemini Vision (typed errors: missing key, quota, timeout…)
    from app.core.config import settings

    if not settings.LLM_API_KEY.strip():
        err = LLMUnavailableError("missing_api_key")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=err.user_message.split(".")[0] + ".")

    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.LLM_API_KEY)
        vision_model_name = settings.LLM_MODEL or "gemini-3.5-flash-lite"
        if vision_model_name in ("gemini-2.0-flash", "gemini-2.5-flash"):
            vision_model_name = "gemini-3.5-flash-lite"
        model = genai.GenerativeModel(vision_model_name)
        response = model.generate_content(
            [{"mime_type": mime_type, "data": image_bytes}, prompt],
            request_options={"timeout": settings.LLM_TIMEOUT_SECONDS},
        )
        response_text = (response.text or "").strip()
    except Exception as exc:  # noqa: BLE001 — classified into a user-facing reason
        err = classify_llm_error(exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=err.user_message.split(".")[0] + ". Please try again later.",
        )

    # 4. Validate the model output before it reaches the UI
    try:
        match = re.search(r"\{.*\}", response_text, re.DOTALL)
        data = json.loads(match.group(0) if match else response_text)
        return MealScanResponse(**data)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI returned an unreadable analysis. Please try a clearer photo.",
        )


# ── Meal diary (stored in the database, per user) ─────────────────────────────


@router.get("/meals", response_model=List[MealLogRead], summary="List logged meals for a day")
def list_meals(
    user: CurrentUser,
    session: SessionDep,
    day: Optional[date] = Query(None, description="YYYY-MM-DD, defaults to today (UTC)"),
):
    target = day or datetime.now(timezone.utc).date()
    stmt = (
        select(MealLog)
        .where(MealLog.user_id == user.id, MealLog.logged_on == target)
        .order_by(MealLog.created_at.desc())  # type: ignore[union-attr]
    )
    return session.exec(stmt).all()


@router.post("/meals", response_model=MealLogRead, status_code=status.HTTP_201_CREATED, summary="Log a meal")
def create_meal(data: MealLogCreate, user: CurrentUser, session: SessionDep):
    meal = MealLog(
        user_id=user.id,  # type: ignore[arg-type]
        logged_on=data.logged_on or datetime.now(timezone.utc).date(),
        slot=data.slot,
        meal_name=data.meal_name,
        calories=data.calories,
        protein_g=data.protein_g,
        carbs_g=data.carbs_g,
        fat_g=data.fat_g,
        food_items=[f.model_dump() for f in data.food_items] if data.food_items else None,
    )
    session.add(meal)
    session.commit()
    session.refresh(meal)
    return meal


@router.delete("/meals/{meal_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a logged meal")
def delete_meal(meal_id: int, user: CurrentUser, session: SessionDep):
    meal = session.get(MealLog, meal_id)
    if meal is None or meal.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found.")
    session.delete(meal)
    session.commit()
