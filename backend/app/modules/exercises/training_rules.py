"""Shared catalog eligibility, session roles and primary-muscle volume rules."""
from app.modules.exercises.catalog import Equipment, Exercise, MovementPattern, MuscleGroup
from app.modules.user.models import ExperienceLevel, Goal

LEVEL = {"beginner": 0, "intermediate": 1, "advanced": 2}
PULL_ARMS = {"barbell-bicep-curl", "dumbbell-incline-curl", "dumbbell-hammer-curl", "chin-up-bicep-focus"}
PUSH_ARMS = {"cable-tricep-pushdown", "cable-overhead-tricep-extension", "barbell-close-grip-bench-press", "tricep-bench-dips"}
REAR_DELTS = {"cable-face-pull", "dumbbell-rear-delt-fly"}


def eligible(exercise: Exercise, equipment: list[Equipment], level: ExperienceLevel) -> bool:
    return exercise.equipment in equipment and LEVEL[exercise.difficulty.value] <= LEVEL[level.value]


def session_role(exercise: Exercise) -> str:
    if exercise.primary_muscle == MuscleGroup.ARMS:
        if exercise.id in PULL_ARMS: return "pull"
        if exercise.id in PUSH_ARMS: return "push"
        return "unknown"
    if exercise.primary_muscle == MuscleGroup.DELTS:
        if exercise.id in REAR_DELTS: return "pull"
        if exercise.movement_pattern == MovementPattern.VERTICAL_PULL: return "pull"
        return "push"
    if exercise.movement_pattern in (MovementPattern.HORIZONTAL_PUSH, MovementPattern.VERTICAL_PUSH): return "push"
    if exercise.movement_pattern in (MovementPattern.HORIZONTAL_PULL, MovementPattern.VERTICAL_PULL): return "pull"
    return "other"


def fits_day(exercise: Exercise, day_name: str, focus: str = "") -> bool:
    text = f"{day_name} {focus}".lower()
    if "upper" in text or "full" in text: return True
    if "push" in text:
        return exercise.primary_muscle in (MuscleGroup.CHEST, MuscleGroup.DELTS, MuscleGroup.ARMS) and session_role(exercise) == "push"
    if "pull" in text:
        if exercise.primary_muscle == MuscleGroup.DELTS:
            return exercise.id in REAR_DELTS
        return exercise.primary_muscle == MuscleGroup.CORE or session_role(exercise) == "pull"
    if "leg" in text or "lower" in text:
        return exercise.primary_muscle in (MuscleGroup.QUADS, MuscleGroup.HAMSTRINGS, MuscleGroup.CORE)
    return True  # Unlabelled/custom days carry no inferred movement restriction.


def replacement_role_matches(source: Exercise, candidate: Exercise) -> bool:
    if source.primary_muscle in (MuscleGroup.ARMS, MuscleGroup.DELTS):
        return session_role(source) == session_role(candidate)
    return True


def volume_target(level: ExperienceLevel, goal: Goal) -> dict[str, int]:
    if level == ExperienceLevel.beginner:
        return {"minimum": 6, "maximum": 12}
    bounds = {Goal.hypertrophy: (10, 20), Goal.strength: (8, 15), Goal.fat_loss: (8, 14), Goal.athletic_performance: (8, 15)}
    low, high = bounds[goal]
    return {"minimum": low, "maximum": high}


def primary_volume(days: list[dict], catalog: dict[str, Exercise]) -> dict[str, int]:
    totals = {muscle.value: 0 for muscle in MuscleGroup}
    for day in days:
        for item in day.get("exercises", []):
            exercise = catalog.get(item.get("exercise_id", ""))
            if exercise:
                totals[exercise.primary_muscle.value] += int(item.get("sets", 3))
    return totals
