"""
app/modules/nutrition/calculator.py
Pure deterministic functions for TDEE, BMR, calorie targets and macros.
No database, no FastAPI, no LLM — just maths with unit tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# ── Editable constants ────────────────────────────────────────────────────────

# Activity multipliers
ACTIVITY_MULTIPLIERS: dict[str, float] = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "very_active": 1.725,
    "extreme": 1.9,
}

# Goal calorie adjustment (fraction of TDEE)
GOAL_ADJUSTMENTS: dict[str, float] = {
    "fat_loss": -0.20,
    "hypertrophy": +0.10,
    "strength": +0.05,
    "athletic_performance": 0.0,
}

# Calorie floors by sex
CALORIE_FLOOR_MALE = 1500
CALORIE_FLOOR_FEMALE = 1200

# Protein targets g/kg
PROTEIN_G_PER_KG_DEFAULT = 2.0
PROTEIN_G_PER_KG_FAT_LOSS = 2.2

# Minimum fat g/kg and as fraction of calories
MIN_FAT_G_PER_KG = 0.8
MIN_FAT_FRACTION = 0.20

# Calories per gram
KCAL_PER_G_PROTEIN = 4.0
KCAL_PER_G_CARB = 4.0
KCAL_PER_G_FAT = 9.0

# Somatotype carb<->fat shift (fraction of target calories)
SOMATOTYPE_SHIFT = 0.05


# ── Return type ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MacroResult:
    """All calculated nutrition values for a single day."""

    bmr: float
    bmr_formula: str
    tdee: float
    target_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    floor_applied: bool
    warnings: list[str] = field(default_factory=list)


# ── BMR formulas ──────────────────────────────────────────────────────────────


def bmr_mifflin_st_jeor(
    sex: str,
    weight_kg: float,
    height_cm: float,
    age: int,
) -> float:
    """Mifflin-St Jeor equation."""
    if weight_kg <= 0:
        raise ValueError(f"weight_kg must be positive, got {weight_kg}")
    if height_cm <= 0:
        raise ValueError(f"height_cm must be positive, got {height_cm}")
    if age <= 0:
        raise ValueError(f"age must be positive, got {age}")
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if sex == "male" else base - 161


def bmr_katch_mcardle(weight_kg: float, body_fat_pct: float) -> float:
    """Katch-McArdle equation — requires body fat percentage."""
    if weight_kg <= 0:
        raise ValueError(f"weight_kg must be positive, got {weight_kg}")
    if not (3.0 <= body_fat_pct <= 60.0):
        raise ValueError(f"body_fat_pct must be 3-60, got {body_fat_pct}")
    lean_mass_kg = weight_kg * (1 - body_fat_pct / 100)
    return 370 + 21.6 * lean_mass_kg


def choose_bmr(
    sex: str,
    weight_kg: float,
    height_cm: float,
    age: int,
    body_fat_pct: Optional[float] = None,
) -> tuple[float, str]:
    """Pick the best BMR formula given available data.

    Returns (bmr_value, formula_name).
    """
    if body_fat_pct is not None:
        return bmr_katch_mcardle(weight_kg, body_fat_pct), "Katch-McArdle"
    return bmr_mifflin_st_jeor(sex, weight_kg, height_cm, age), "Mifflin-St Jeor"


# ── TDEE ──────────────────────────────────────────────────────────────────────


def tdee(bmr: float, activity_level: str) -> float:
    """Total Daily Energy Expenditure."""
    try:
        multiplier = ACTIVITY_MULTIPLIERS[activity_level]
    except KeyError:
        raise ValueError(
            f"Unknown activity_level '{activity_level}'. "
            f"Valid options: {list(ACTIVITY_MULTIPLIERS)}"
        )
    return bmr * multiplier


# ── Target calories ───────────────────────────────────────────────────────────


def target_calories(
    tdee_value: float,
    goal: str,
    sex: str,
) -> tuple[float, bool, list[str]]:
    """Apply goal adjustment and enforce calorie floor.

    Returns (target_kcal, floor_applied, warnings).
    """
    try:
        adjustment = GOAL_ADJUSTMENTS[goal]
    except KeyError:
        raise ValueError(
            f"Unknown goal '{goal}'. Valid options: {list(GOAL_ADJUSTMENTS)}"
        )

    target = tdee_value * (1 + adjustment)
    floor = CALORIE_FLOOR_MALE if sex == "male" else CALORIE_FLOOR_FEMALE
    floor_applied = False
    warnings: list[str] = []

    if target < floor:
        warnings.append(
            f"Calculated target of {target:.0f} kcal is below the minimum "
            f"of {floor} kcal for {sex}. Floor applied."
        )
        target = float(floor)
        floor_applied = True

    return target, floor_applied, warnings


# ── Macros ────────────────────────────────────────────────────────────────────


def macro_targets(
    target_kcal: float,
    weight_kg: float,
    goal: str,
    somatotype: str,
) -> tuple[float, float, float]:
    """Calculate protein, carbs, fat in grams.

    Returns (protein_g, carbs_g, fat_g).
    """
    # Protein
    prot_per_kg = PROTEIN_G_PER_KG_FAT_LOSS if goal == "fat_loss" else PROTEIN_G_PER_KG_DEFAULT
    protein_g = weight_kg * prot_per_kg
    protein_kcal = protein_g * KCAL_PER_G_PROTEIN

    # Minimum fat
    min_fat_by_weight = weight_kg * MIN_FAT_G_PER_KG
    min_fat_by_fraction = (target_kcal * MIN_FAT_FRACTION) / KCAL_PER_G_FAT
    base_fat_g = max(min_fat_by_weight, min_fat_by_fraction)

    # Somatotype shift before carb calculation
    shift_kcal = target_kcal * SOMATOTYPE_SHIFT
    if somatotype == "endomorph":
        # Move 5 % of calories from carbs to fat
        extra_fat_g = shift_kcal / KCAL_PER_G_FAT
        fat_g = base_fat_g + extra_fat_g
    elif somatotype == "ectomorph":
        # Move 5 % of calories from fat to carbs (never below fat floor)
        reduced_fat_g = base_fat_g - shift_kcal / KCAL_PER_G_FAT
        fat_g = max(reduced_fat_g, min_fat_by_weight, min_fat_by_fraction)
    else:
        fat_g = base_fat_g

    fat_kcal = fat_g * KCAL_PER_G_FAT
    remaining_kcal = target_kcal - protein_kcal - fat_kcal
    carbs_g = max(0.0, remaining_kcal / KCAL_PER_G_CARB)

    return round(protein_g, 1), round(carbs_g, 1), round(fat_g, 1)


# ── Main entry point ──────────────────────────────────────────────────────────


def calculate(
    sex: str,
    weight_kg: float,
    height_cm: float,
    age: int,
    activity_level: str,
    goal: str,
    somatotype: str,
    body_fat_pct: Optional[float] = None,
) -> MacroResult:
    """End-to-end nutrition calculation returning a frozen MacroResult."""
    bmr_value, bmr_formula = choose_bmr(sex, weight_kg, height_cm, age, body_fat_pct)
    tdee_value = tdee(bmr_value, activity_level)
    target, floor_applied, warnings = target_calories(tdee_value, goal, sex)
    protein_g, carbs_g, fat_g = macro_targets(target, weight_kg, goal, somatotype)

    return MacroResult(
        bmr=round(bmr_value, 1),
        bmr_formula=bmr_formula,
        tdee=round(tdee_value, 1),
        target_kcal=round(target, 1),
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        floor_applied=floor_applied,
        warnings=warnings,
    )
