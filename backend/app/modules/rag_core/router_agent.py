"""
app/modules/rag_core/router_agent.py
Intent router, exercise entity extractor, context enricher, and workout logging parser.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.modules.exercises.catalog import get_catalog
from app.modules.nutrition.calculator import MacroResult
from app.modules.nutrition.service import calculate_macros
from app.modules.progressive_overload.service import get_history, get_recommendation
from app.modules.rag_core.engine import LLMClient, get_llm_client
from app.modules.user.service import get_or_create_profile


# ── Intents & Patterns ────────────────────────────────────────────────────────

INTENTS = [
    "nutrition",
    "exercise_technique",
    "workout_logging",
    "overload_advice",
    "general",
]

NUTRITION_KEYWORDS = [
    "calorie", "calories", "tdee", "bmr", "macro", "macros", "protein", "carb",
    "carbs", "carbohydrate", "fat", "fats", "diet", "meal", "food", "nutrition",
    "eat", "eating", "hydration", "water", "deficit", "surplus", "cutting", "bulking",
]

OVERLOAD_KEYWORDS = [
    "plateau", "stuck", "progression", "double progression", "linear progression",
    "overload", "increase weight", "next session", "how much weight", "add weight",
    "deload", "1rm", "one rep max",
]

TECHNIQUE_KEYWORDS = [
    "form", "technique", "how to perform", "how to do", "cues", "mistake", "mistakes",
    "setup", "injury", "pain", "hurts", "elbow flare", "arch", "grip", "stance",
]

EXERCISE_ALIASES: Dict[str, str] = {
    "bench press": "barbell-bench-press",
    "bench": "barbell-bench-press",
    "incline bench": "incline-dumbbell-press",
    "incline press": "incline-dumbbell-press",
    "push up": "push-up",
    "pushup": "push-up",
    "dip": "dips-chest-focus",
    "dips": "dips-chest-focus",
    "fly": "cable-chest-fly",
    "cable fly": "cable-chest-fly",
    "squat": "barbell-back-squat",
    "back squat": "barbell-back-squat",
    "front squat": "barbell-front-squat",
    "goblet squat": "goblet-squat",
    "lunge": "dumbbell-walking-lunge",
    "split squat": "bulgarian-split-squat-bodyweight",
    "bulgarian": "bulgarian-split-squat-bodyweight",
    "deadlift": "barbell-deadlift",
    "rdl": "barbell-romanian-deadlift",
    "romanian deadlift": "barbell-romanian-deadlift",
    "row": "barbell-bent-over-row",
    "bent over row": "barbell-bent-over-row",
    "lat pulldown": "lat-pulldown",
    "pulldown": "lat-pulldown",
    "pull up": "pull-up",
    "pullup": "pull-up",
    "chin up": "chin-up-bicep-focus",
    "overhead press": "overhead-barbell-press",
    "ohp": "overhead-barbell-press",
    "shoulder press": "seated-dumbbell-shoulder-press",
    "lateral raise": "dumbbell-lateral-raise",
    "side raise": "dumbbell-lateral-raise",
    "face pull": "cable-face-pull",
    "bicep curl": "barbell-bicep-curl",
    "curl": "barbell-bicep-curl",
    "hammer curl": "dumbbell-hammer-curl",
    "tricep pushdown": "cable-tricep-pushdown",
    "pushdown": "cable-tricep-pushdown",
    "plank": "plank",
    "hanging leg raise": "hanging-leg-raise",
    "leg raise": "hanging-leg-raise",
}


@dataclass
class IntentResult:
    name: str
    confidence: float


@dataclass
class EnrichedContext:
    intent: str
    user_facts: str
    numbers: str
    retrieval_category: str  # "nutrition", "exercise", or "both"
    mentioned_exercises: List[str]


class PendingSet(BaseModel):
    exercise_id: str
    exercise_name: str
    weight: float
    unit: str = "kg"
    reps: int
    set_number: int = 1
    rpe: Optional[float] = None
    rir: Optional[int] = None


class PendingAction(BaseModel):
    action_type: str = "log_workout"
    sets: List[PendingSet] = Field(default_factory=list)


def classify_intent(
    message: str,
    recent_messages: Optional[List[Dict[str, str]]] = None,
    llm_client: Optional[LLMClient] = None,
) -> IntentResult:
    """Classify the user intent using fast heuristic rules first, falling back to a short LLM classification."""
    msg = message.lower().strip()

    # Rule 1: Workout logging detection (e.g. "bench 80kg 3x8", "logged 3 sets of 100 kg 5 reps", "80kg x 8 reps")
    log_pattern = re.search(
        r"(\d+(\.\d+)?\s*(kg|lbs?|lb))|(\d+\s*x\s*\d+)|(\d+\s*sets?\s*(of\s*)?\d+\s*reps?)",
        msg,
    )
    if log_pattern and any(alias in msg for alias in EXERCISE_ALIASES):
        return IntentResult(name="workout_logging", confidence=0.95)

    # Rule 2: Overload advice
    if any(k in msg for k in OVERLOAD_KEYWORDS):
        return IntentResult(name="overload_advice", confidence=0.90)

    # Rule 3: Nutrition
    if any(k in msg for k in NUTRITION_KEYWORDS):
        return IntentResult(name="nutrition", confidence=0.90)

    # Rule 4: Exercise technique
    if any(k in msg for k in TECHNIQUE_KEYWORDS) or any(alias in msg for alias in EXERCISE_ALIASES):
        return IntentResult(name="exercise_technique", confidence=0.85)

    # Fallback to LLM if confidence is low
    client = llm_client or get_llm_client()
    try:
        sys = (
            "You are an intent classifier. Given the user message, respond with EXACTLY ONE of: "
            "nutrition, exercise_technique, workout_logging, overload_advice, general."
        )
        resp = client.complete([{"role": "user", "content": message}], system=sys).strip().lower()
        for valid_intent in INTENTS:
            if valid_intent in resp:
                return IntentResult(name=valid_intent, confidence=0.75)
    except Exception:
        pass

    return IntentResult(name="general", confidence=0.50)


def extract_exercises(message: str) -> List[str]:
    """Find all exercise slugs mentioned in the message by name or alias."""
    msg = message.lower()
    catalog = get_catalog()
    matched_ids: List[str] = []

    # Check aliases first (sorted longest alias first to match 'incline bench press' before 'bench')
    sorted_aliases = sorted(EXERCISE_ALIASES.keys(), key=len, reverse=True)
    for alias in sorted_aliases:
        pattern = r"\b" + re.escape(alias) + r"\b"
        if re.search(pattern, msg):
            slug = EXERCISE_ALIASES[alias]
            if slug not in matched_ids:
                matched_ids.append(slug)

    # Also match exact exercise names from catalog
    for ex_id, ex in catalog.items():
        if ex.name.lower() in msg and ex_id not in matched_ids:
            matched_ids.append(ex_id)

    return matched_ids


def enrich(
    intent: str,
    message: str,
    session: Session,
    user_id: int,
) -> EnrichedContext:
    """Enrich context with user facts, deterministic math numbers, and appropriate category."""
    profile = get_or_create_profile(session, user_id)
    user_facts = (
        f"Age: {profile.age}, Sex: {profile.sex.value}, Height: {profile.height_cm} cm, "
        f"Weight: {profile.weight_kg} kg, Body Fat: {profile.body_fat_pct or 'N/A'}%, "
        f"Experience: {profile.experience_level.value}, Goal: {profile.goal.value}, "
        f"Somatotype: {profile.somatotype.value}, Activity Level: {profile.activity_level.value}"
    )

    numbers = ""
    retrieval_category = "both"
    mentioned = extract_exercises(message)

    if intent == "nutrition":
        retrieval_category = "nutrition"
        from app.modules.nutrition.service import MacroRequest
        macro_res = calculate_macros(MacroRequest(), session, user_id)
        floor_note = f" (Floor applied: {macro_res.floor_applied})" if macro_res.floor_applied else ""
        numbers = (
            f"BMR: {macro_res.bmr:.0f} kcal ({macro_res.bmr_formula}), "
            f"TDEE: {macro_res.tdee:.0f} kcal, "
            f"Target Calories: {macro_res.target_kcal:.0f} kcal{floor_note}, "
            f"Protein: {macro_res.protein_g:.1f}g, Carbs: {macro_res.carbs_g:.1f}g, Fat: {macro_res.fat_g:.1f}g"
        )

    elif intent in ("exercise_technique", "overload_advice"):
        retrieval_category = "exercise"
        if intent == "overload_advice":
            target_slugs = mentioned if mentioned else ["barbell-bench-press"]
            recs_summary: List[str] = []
            for slug in target_slugs:
                rec = get_recommendation(session, exercise_id=slug, algorithm="double", user_id=user_id)
                alt_txt = f" (Alternative: {rec.alternative})" if rec.alternative else ""
                recs_summary.append(
                    f"{slug}: Target {rec.weight_kg} kg for {rec.rep_target}{alt_txt}. Reason: {rec.reason}"
                )
            numbers = "\n".join(recs_summary)

    else:
        retrieval_category = "both"

    return EnrichedContext(
        intent=intent,
        user_facts=user_facts,
        numbers=numbers,
        retrieval_category=retrieval_category,
        mentioned_exercises=mentioned,
    )


def parse_logged_sets(
    message: str,
    llm_client: Optional[LLMClient] = None,
) -> Optional[PendingAction]:
    """Parse workout logging information into structured pending sets for confirmation.
    Does NOT write to the database!
    """
    catalog = get_catalog()
    exercises = extract_exercises(message)
    if not exercises:
        exercises = ["barbell-bench-press"]

    ex_id = exercises[0]
    ex_obj = catalog.get(ex_id)
    ex_name = ex_obj.name if ex_obj else ex_id

    # Heuristic regex parse for weight and reps
    weight = 80.0
    unit = "kg"
    reps = 8
    num_sets = 3
    rpe = 8.0

    # Weight match
    wt_match = re.search(r"(\d+(\.\d+)?)\s*(kg|lbs?|lb)", message, re.IGNORECASE)
    if wt_match:
        weight = float(wt_match.group(1))
        unit = "lb" if "lb" in wt_match.group(3).lower() else "kg"
    else:
        # Check bare number
        bare_wt = re.search(r"\b(\d{2,3}(\.\d+)?)\b", message)
        if bare_wt:
            weight = float(bare_wt.group(1))

    # Sets x reps match
    sxr = re.search(r"(\d+)\s*x\s*(\d+)", message)
    if sxr:
        num_sets = int(sxr.group(1))
        reps = int(sxr.group(2))
    else:
        rep_m = re.search(r"(\d+)\s*reps?", message, re.IGNORECASE)
        if rep_m:
            reps = int(rep_m.group(1))
        set_m = re.search(r"(\d+)\s*sets?", message, re.IGNORECASE)
        if set_m:
            num_sets = int(set_m.group(1))

    # RPE match
    rpe_m = re.search(r"rpe\s*(\d+(\.\d+)?)", message, re.IGNORECASE)
    if rpe_m:
        rpe = float(rpe_m.group(1))

    pending_sets = [
        PendingSet(
            exercise_id=ex_id,
            exercise_name=ex_name,
            weight=weight,
            unit=unit,
            reps=reps,
            set_number=i + 1,
            rpe=rpe,
            rir=round(10.0 - rpe) if rpe else None,
        )
        for i in range(num_sets)
    ]

    return PendingAction(action_type="log_workout", sets=pending_sets)
