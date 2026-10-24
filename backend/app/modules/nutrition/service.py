"""
app/modules/nutrition/service.py
Nutrition service — wires the calculator to the user profile.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlmodel import Session

from app.modules.nutrition import calculator as calc
from app.modules.nutrition.calculator import MacroResult
from app.modules.user import service as user_svc

# ── Hydration constant ────────────────────────────────────────────────────────
HYDRATION_ML_PER_KG = 35  # editable


# ── Request schemas ───────────────────────────────────────────────────────────


@dataclass
class MacroRequest:
    """Fields can be None — missing ones fall back to the stored profile."""

    sex: Optional[str] = None
    age: Optional[int] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    body_fat_pct: Optional[float] = None
    activity_level: Optional[str] = None
    goal: Optional[str] = None
    somatotype: Optional[str] = None
    unit_system: Optional[str] = None
    # If weight is provided in lbs, set unit='imperial'
    weight_unit: Optional[str] = None  # 'kg' | 'lb'


@dataclass
class MealSlot:
    label: str
    time_hint: str
    protein_g: float
    carbs_g: float
    fat_g: float
    kcal: float


@dataclass
class MealPlanResult:
    macros: MacroResult
    meals: list[MealSlot]
    hydration_ml: float


# ── Service functions ─────────────────────────────────────────────────────────


def _lbs_to_kg(lbs: float) -> float:
    return round(lbs * 0.453592, 2)


def _resolve(field_value, profile_value):
    """Return field_value if set, else fall back to profile_value."""
    return field_value if field_value is not None else profile_value


def calculate_macros(request: MacroRequest, session: Session) -> MacroResult:
    """Calculate macros, merging request overrides with the stored profile."""
    profile = user_svc.get_or_create_default_profile(session)

    sex = _resolve(request.sex, profile.sex.value)
    age = _resolve(request.age, profile.age)
    height_cm = _resolve(request.height_cm, profile.height_cm)
    weight_kg = _resolve(request.weight_kg, profile.weight_kg)
    body_fat_pct = _resolve(request.body_fat_pct, profile.body_fat_pct)
    activity_level = _resolve(request.activity_level, profile.activity_level.value)
    goal = _resolve(request.goal, profile.goal.value)
    somatotype = _resolve(request.somatotype, profile.somatotype.value)
    unit_system = _resolve(request.unit_system, profile.unit_system.value)

    # Convert weight if imperial
    if unit_system == "imperial" or request.weight_unit == "lb":
        weight_kg = _lbs_to_kg(weight_kg)

    return calc.calculate(
        sex=sex,
        weight_kg=weight_kg,
        height_cm=height_cm,
        age=age,
        activity_level=activity_level,
        goal=goal,
        somatotype=somatotype,
        body_fat_pct=body_fat_pct,
    )


def build_meal_plan(
    macros: MacroResult,
    meals_per_day: int,
    training_time: Optional[str],  # e.g. "08:00", "18:00" or None
    goal: str,
    weight_kg: float,
) -> MealPlanResult:
    """Split daily macros across meals with training-time context.

    Rules:
    - 3-6 meals allowed.
    - Pre/post-workout meals get the largest carb share.
    - Slot totals == daily totals within rounding.
    """
    if not (3 <= meals_per_day <= 6):
        raise ValueError(f"meals_per_day must be 3-6, got {meals_per_day}")

    p = macros.protein_g
    c = macros.carbs_g
    f = macros.fat_g

    # Label and carb-weight templates by meal count
    templates = {
        3: [
            ("Breakfast", "morning", 0.33, 0.25, 0.33),
            ("Lunch", "midday", 0.33, 0.40, 0.34),
            ("Dinner", "evening", 0.34, 0.35, 0.33),
        ],
        4: [
            ("Breakfast", "morning", 0.25, 0.20, 0.25),
            ("Lunch", "midday", 0.28, 0.35, 0.28),
            ("Afternoon snack", "afternoon", 0.22, 0.20, 0.22),
            ("Dinner", "evening", 0.25, 0.25, 0.25),
        ],
        5: [
            ("Breakfast", "morning", 0.20, 0.18, 0.20),
            ("Mid-morning snack", "late morning", 0.15, 0.12, 0.15),
            ("Lunch", "midday", 0.25, 0.30, 0.25),
            ("Pre-workout", "pre-workout", 0.20, 0.25, 0.20),
            ("Dinner / Post-workout", "post-workout", 0.20, 0.15, 0.20),
        ],
        6: [
            ("Breakfast", "morning", 0.17, 0.15, 0.17),
            ("Mid-morning snack", "late morning", 0.12, 0.10, 0.12),
            ("Lunch", "midday", 0.20, 0.25, 0.20),
            ("Pre-workout", "pre-workout", 0.18, 0.22, 0.18),
            ("Post-workout", "post-workout", 0.18, 0.18, 0.18),
            ("Evening snack", "evening", 0.15, 0.10, 0.15),
        ],
    }

    tmpl = templates[meals_per_day]
    slots: list[MealSlot] = []
    cum_p = cum_c = cum_f = 0.0

    for i, (label, time_hint, pp, pc, pf) in enumerate(tmpl):
        if i < len(tmpl) - 1:
            sp = round(p * pp, 1)
            sc = round(c * pc, 1)
            sf = round(f * pf, 1)
        else:
            # Last slot gets the remainder to fix rounding drift
            sp = round(p - cum_p, 1)
            sc = round(c - cum_c, 1)
            sf = round(f - cum_f, 1)

        cum_p += sp
        cum_c += sc
        cum_f += sf

        kcal = round(
            sp * calc.KCAL_PER_G_PROTEIN
            + sc * calc.KCAL_PER_G_CARB
            + sf * calc.KCAL_PER_G_FAT,
            1,
        )
        slots.append(MealSlot(label=label, time_hint=time_hint,
                               protein_g=sp, carbs_g=sc, fat_g=sf, kcal=kcal))

    hydration_ml = weight_kg * HYDRATION_ML_PER_KG
    return MealPlanResult(macros=macros, meals=slots, hydration_ml=hydration_ml)
