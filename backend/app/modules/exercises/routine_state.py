"""Canonical routine facts for persistence, UI volume and AI suggestions."""
from copy import deepcopy
import re

from app.modules.exercises.catalog import Equipment, get_catalog
from app.modules.exercises.training_rules import eligible, fits_day, primary_volume, volume_target
from app.modules.user.models import ExperienceLevel, Goal


def canonical_routine(raw: dict, level: ExperienceLevel, goal: Goal, equipment=None, *, strict=True) -> dict:
    result = deepcopy(raw)
    days = result.get("days")
    if not isinstance(days, list) or len(days) > 7:
        raise ValueError("Routine must contain a list of at most seven days.")
    available = list(dict.fromkeys(Equipment(item) for item in (
        equipment if equipment is not None else result.get("available_equipment", list(Equipment))
    )))
    catalog = get_catalog()
    # Rebuild current warnings so corrected exercises do not retain stale notices.
    warnings = []
    if result.get("split", result.get("split_type")) == "push_pull_legs" and len(days) in (4, 5):
        warnings.append("A four/five-day PPL week has unequal Push/Pull/Legs frequency. Review the distribution or choose Upper/Lower.")
    for index, day in enumerate(days, 1):
        if not isinstance(day, dict) or not isinstance(day.get("exercises", []), list) or len(day.get("exercises", [])) > 20:
            raise ValueError("Each day must contain a list of at most 20 exercises.")
        day.setdefault("exercises", [])
        seen = set()
        for item in day["exercises"]:
            if not isinstance(item, dict): raise ValueError("Each exercise must be an object.")
            exercise = catalog.get(item.get("exercise_id", ""))
            if exercise is None:
                if strict: raise ValueError("Routine contains an unknown exercise ID.")
                warnings.append(f"Day {index}: an exercise is no longer in the catalog; review this entry.")
                continue
            sets = item.get("sets", 3)
            if type(sets) is not int or not 1 <= sets <= 12:
                raise ValueError("Sets must be an integer between 1 and 12.")
            reps = str(item.get("rep_range", "8-12"))
            if not re.fullmatch(r"\d{1,2}(?:-\d{1,2})?", reps): raise ValueError("Invalid repetition range.")
            low, _, high = reps.partition("-")
            if int(low) < 1 or int(high or low) < int(low): raise ValueError("Repetition ranges must be positive and ordered.")
            item.update(name=exercise.name, exercise_name=exercise.name, primary_muscle=exercise.primary_muscle.value,
                        movement_pattern=exercise.movement_pattern.value, sets=sets, rep_range=reps)
            if exercise.id in seen: warnings.append(f"Day {index}: {exercise.name} appears more than once.")
            seen.add(exercise.id)
            if not eligible(exercise, available, level):
                warnings.append(f"Day {index}: {exercise.name} does not match the selected equipment or experience; review it with Swap.")
            if not fits_day(exercise, day.get("name", ""), day.get("focus", "")):
                warnings.append(f"Day {index}: {exercise.name} does not match this session's movement focus.")
    totals = primary_volume(days, catalog)
    target = volume_target(level, goal)
    for muscle, count in totals.items():
        if count < target["minimum"]: warnings.append(f"Muscle '{muscle}' has {count} planned sets, below the configured range {target['minimum']}–{target['maximum']}.")
        elif count > target["maximum"]: warnings.append(f"Muscle '{muscle}' has {count} planned sets, above the configured range {target['minimum']}–{target['maximum']}.")
    result.pop("weekly_volume_per_muscle", None)
    result["weekly_sets_per_muscle"] = totals
    result["volume_target"] = target
    result["available_equipment"] = [eq.value for eq in available]
    result["warnings"] = list(dict.fromkeys(warnings))
    return result
