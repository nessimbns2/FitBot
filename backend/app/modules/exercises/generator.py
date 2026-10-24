"""
app/modules/exercises/generator.py
Pure, deterministic routine generator.
No database, no FastAPI, no LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.modules.exercises.catalog import (
    Equipment,
    Exercise,
    MovementPattern,
    MuscleGroup,
    get_catalog,
)
from app.modules.user.models import ExperienceLevel, Goal


# ── Editable Constants ────────────────────────────────────────────────────────

REP_RANGES = {
    Goal.strength: {"compound": "3-6", "isolation": "6-8"},
    Goal.hypertrophy: {"compound": "6-12", "isolation": "10-15"},
    Goal.fat_loss: {"compound": "8-12", "isolation": "12-15"},
    Goal.athletic_performance: {"compound": "4-8", "isolation": "8-10"},
}

REST_SECONDS = {
    Goal.strength: {"compound": 180, "isolation": 90},
    Goal.hypertrophy: {"compound": 90, "isolation": 60},
    Goal.fat_loss: {"compound": 60, "isolation": 45},
    Goal.athletic_performance: {"compound": 120, "isolation": 60},
}

TARGET_WEEKLY_SETS_PER_MUSCLE = {
    # (min_sets, max_sets)
    ExperienceLevel.beginner: (6, 12),
    Goal.hypertrophy: (10, 20),
    Goal.strength: (8, 15),
    Goal.fat_loss: (8, 14),
    Goal.athletic_performance: (8, 15),
}


class SplitType(str, Enum):
    PUSH_PULL_LEGS = "push_pull_legs"
    UPPER_LOWER = "upper_lower"
    FULL_BODY = "full_body"


class RoutineExerciseItem(BaseModel):
    exercise_id: str
    name: str
    sets: int
    rep_range: str
    rest_seconds: int
    movement_pattern: MovementPattern
    primary_muscle: MuscleGroup


class RoutineDay(BaseModel):
    name: str
    focus: str
    exercises: List[RoutineExerciseItem] = Field(default_factory=list)


class RoutineResult(BaseModel):
    split: SplitType
    days_per_week: int
    days: List[RoutineDay]
    weekly_sets_per_muscle: Dict[str, int]
    warnings: List[str] = Field(default_factory=list)


def _get_target_volume_range(level: ExperienceLevel, goal: Goal) -> tuple[int, int]:
    if level == ExperienceLevel.beginner:
        return TARGET_WEEKLY_SETS_PER_MUSCLE[ExperienceLevel.beginner]
    return TARGET_WEEKLY_SETS_PER_MUSCLE.get(goal, (10, 20))


def _filter_available_exercises(available_equipment: List[Equipment]) -> List[Exercise]:
    catalog = get_catalog()
    allowed_eq = set(available_equipment)
    # Deterministic sort by id
    filtered = [ex for ex in catalog.values() if ex.equipment in allowed_eq]
    filtered.sort(key=lambda x: x.id)
    return filtered


def generate_routine(
    split: SplitType,
    days_per_week: int,
    experience_level: ExperienceLevel,
    goal: Goal,
    available_equipment: List[Equipment],
) -> RoutineResult:
    """Generate a deterministic training routine based on split, frequency, and available equipment."""
    if not (2 <= days_per_week <= 6):
        raise ValueError(f"days_per_week must be between 2 and 6, got {days_per_week}")

    warnings: List[str] = []
    available_exercises = _filter_available_exercises(available_equipment)

    if not available_exercises:
        warnings.append("No exercises found matching available equipment.")
        return RoutineResult(
            split=split,
            days_per_week=days_per_week,
            days=[],
            weekly_sets_per_muscle={},
            warnings=warnings,
        )

    # Muscle groupings per day based on split
    # PPL: Push (chest, delts, arms), Pull (back, delts, arms, core), Legs (quads, hamstrings, core)
    # Upper/Lower: Upper (chest, back, delts, arms), Lower (quads, hamstrings, core)
    # Full Body: all
    days: List[RoutineDay] = []

    def get_ex(muscle: MuscleGroup, compound: bool, used_ids: set[str]) -> Optional[Exercise]:
        for ex in available_exercises:
            if ex.id not in used_ids and ex.primary_muscle == muscle and ex.is_compound == compound:
                return ex
        # fallback to any equipment-valid exercise for this muscle
        for ex in available_exercises:
            if ex.id not in used_ids and ex.primary_muscle == muscle:
                return ex
        # fallback allowing reuse
        for ex in available_exercises:
            if ex.primary_muscle == muscle and ex.is_compound == compound:
                return ex
        for ex in available_exercises:
            if ex.primary_muscle == muscle:
                return ex
        return None

    rep_cfg = REP_RANGES.get(goal, REP_RANGES[Goal.hypertrophy])
    rest_cfg = REST_SECONDS.get(goal, REST_SECONDS[Goal.hypertrophy])

    # Sets per exercise: usually 3 sets
    sets_per_exercise = 3

    if split == SplitType.PUSH_PULL_LEGS:
        # Templates: Push, Pull, Legs (repeated or scheduled for days_per_week)
        day_templates = [
            ("Push A", "Chest, Shoulders & Triceps", [(MuscleGroup.CHEST, True), (MuscleGroup.DELTS, True), (MuscleGroup.CHEST, False), (MuscleGroup.DELTS, False), (MuscleGroup.ARMS, False)]),
            ("Pull A", "Back, Rear Delts & Biceps", [(MuscleGroup.BACK, True), (MuscleGroup.BACK, True), (MuscleGroup.DELTS, False), (MuscleGroup.ARMS, False), (MuscleGroup.CORE, False)]),
            ("Legs A", "Quads, Hamstrings & Calves/Core", [(MuscleGroup.QUADS, True), (MuscleGroup.HAMSTRINGS, True), (MuscleGroup.QUADS, False), (MuscleGroup.HAMSTRINGS, False), (MuscleGroup.CORE, False)]),
            ("Push B", "Chest, Shoulders & Triceps", [(MuscleGroup.CHEST, True), (MuscleGroup.DELTS, False), (MuscleGroup.CHEST, False), (MuscleGroup.ARMS, True), (MuscleGroup.ARMS, False)]),
            ("Pull B", "Back, Rear Delts & Biceps", [(MuscleGroup.BACK, True), (MuscleGroup.BACK, False), (MuscleGroup.DELTS, True), (MuscleGroup.ARMS, False), (MuscleGroup.CORE, False)]),
            ("Legs B", "Quads, Hamstrings & Calves/Core", [(MuscleGroup.QUADS, True), (MuscleGroup.HAMSTRINGS, True), (MuscleGroup.QUADS, True), (MuscleGroup.HAMSTRINGS, False), (MuscleGroup.CORE, False)]),
        ]
        chosen_templates = day_templates[:days_per_week]

    elif split == SplitType.UPPER_LOWER:
        day_templates = [
            ("Upper A", "Chest, Back, Shoulders & Arms", [(MuscleGroup.CHEST, True), (MuscleGroup.BACK, True), (MuscleGroup.DELTS, False), (MuscleGroup.BACK, False), (MuscleGroup.ARMS, False)]),
            ("Lower A", "Quads, Hamstrings & Core", [(MuscleGroup.QUADS, True), (MuscleGroup.HAMSTRINGS, True), (MuscleGroup.QUADS, False), (MuscleGroup.HAMSTRINGS, False), (MuscleGroup.CORE, False)]),
            ("Upper B", "Chest, Back, Shoulders & Arms", [(MuscleGroup.BACK, True), (MuscleGroup.CHEST, True), (MuscleGroup.DELTS, True), (MuscleGroup.ARMS, False), (MuscleGroup.ARMS, False)]),
            ("Lower B", "Quads, Hamstrings & Core", [(MuscleGroup.HAMSTRINGS, True), (MuscleGroup.QUADS, True), (MuscleGroup.QUADS, False), (MuscleGroup.HAMSTRINGS, False), (MuscleGroup.CORE, False)]),
            ("Upper C", "Upper Body Hypertrophy", [(MuscleGroup.CHEST, True), (MuscleGroup.BACK, True), (MuscleGroup.DELTS, False), (MuscleGroup.ARMS, False), (MuscleGroup.CORE, False)]),
            ("Lower C", "Lower Body Hypertrophy", [(MuscleGroup.QUADS, True), (MuscleGroup.HAMSTRINGS, True), (MuscleGroup.QUADS, False), (MuscleGroup.HAMSTRINGS, False), (MuscleGroup.CORE, False)]),
        ]
        chosen_templates = day_templates[:days_per_week]

    else:  # FULL_BODY
        day_templates = [
            ("Full Body A", "Full Body Compound Focus", [(MuscleGroup.QUADS, True), (MuscleGroup.CHEST, True), (MuscleGroup.BACK, True), (MuscleGroup.HAMSTRINGS, False), (MuscleGroup.DELTS, False), (MuscleGroup.CORE, False)]),
            ("Full Body B", "Full Body Strength & Pull", [(MuscleGroup.BACK, True), (MuscleGroup.HAMSTRINGS, True), (MuscleGroup.CHEST, False), (MuscleGroup.QUADS, False), (MuscleGroup.ARMS, False), (MuscleGroup.CORE, False)]),
            ("Full Body C", "Full Body Balance", [(MuscleGroup.QUADS, True), (MuscleGroup.CHEST, True), (MuscleGroup.BACK, False), (MuscleGroup.DELTS, True), (MuscleGroup.HAMSTRINGS, False), (MuscleGroup.CORE, False)]),
            ("Full Body D", "Full Body Hypertrophy", [(MuscleGroup.HAMSTRINGS, True), (MuscleGroup.BACK, True), (MuscleGroup.CHEST, False), (MuscleGroup.QUADS, False), (MuscleGroup.ARMS, False), (MuscleGroup.CORE, False)]),
            ("Full Body E", "Full Body Conditioning", [(MuscleGroup.QUADS, True), (MuscleGroup.CHEST, True), (MuscleGroup.BACK, True), (MuscleGroup.DELTS, False), (MuscleGroup.ARMS, False), (MuscleGroup.CORE, False)]),
            ("Full Body F", "Full Body Volume", [(MuscleGroup.BACK, True), (MuscleGroup.QUADS, True), (MuscleGroup.HAMSTRINGS, True), (MuscleGroup.CHEST, False), (MuscleGroup.DELTS, False), (MuscleGroup.CORE, False)]),
        ]
        chosen_templates = day_templates[:days_per_week]

    weekly_sets: Dict[str, int] = {m.value: 0 for m in MuscleGroup}

    for day_name, focus, slot_specs in chosen_templates:
        day_exercises: List[RoutineExerciseItem] = []
        used_ids_in_day: set[str] = set()

        for muscle, is_comp in slot_specs:
            ex = get_ex(muscle, is_comp, used_ids_in_day)
            if not ex:
                continue

            used_ids_in_day.add(ex.id)
            is_compound = ex.is_compound
            rep_range = rep_cfg["compound"] if is_compound else rep_cfg["isolation"]
            rest_s = rest_cfg["compound"] if is_compound else rest_cfg["isolation"]

            day_exercises.append(
                RoutineExerciseItem(
                    exercise_id=ex.id,
                    name=ex.name,
                    sets=sets_per_exercise,
                    rep_range=rep_range,
                    rest_seconds=rest_s,
                    movement_pattern=ex.movement_pattern,
                    primary_muscle=ex.primary_muscle,
                )
            )
            weekly_sets[ex.primary_muscle.value] += sets_per_exercise

        days.append(RoutineDay(name=day_name, focus=focus, exercises=day_exercises))

    # Evaluate weekly volume targets
    min_vol, max_vol = _get_target_volume_range(experience_level, goal)
    for muscle_str, sets_count in weekly_sets.items():
        if sets_count < min_vol:
            warnings.append(
                f"Muscle '{muscle_str}' has {sets_count} weekly sets, below recommended minimum of {min_vol} sets."
            )
        elif sets_count > max_vol:
            warnings.append(
                f"Muscle '{muscle_str}' has {sets_count} weekly sets, above recommended maximum of {max_vol} sets."
            )

    return RoutineResult(
        split=split,
        days_per_week=days_per_week,
        days=days,
        weekly_sets_per_muscle=weekly_sets,
        warnings=warnings,
    )
