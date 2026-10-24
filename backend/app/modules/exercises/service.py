"""
app/modules/exercises/service.py
Service layer for exercise catalog queries and lookups.
"""

from __future__ import annotations

from typing import List, Optional
from app.modules.exercises.catalog import (
    Exercise,
    Equipment,
    MovementPattern,
    MuscleGroup,
    get_catalog,
)


def list_exercises(
    muscle: Optional[MuscleGroup] = None,
    equipment: Optional[Equipment] = None,
    pattern: Optional[MovementPattern] = None,
    q: Optional[str] = None,
) -> List[Exercise]:
    """Filter exercises by muscle group, equipment, movement pattern, or search term (name/slug)."""
    catalog = get_catalog()
    results: List[Exercise] = []

    query_str = q.strip().lower() if q else None

    for exercise in catalog.values():
        if muscle is not None:
            if exercise.primary_muscle != muscle and muscle not in exercise.secondary_muscles:
                continue

        if equipment is not None:
            if exercise.equipment != equipment:
                continue

        if pattern is not None:
            if exercise.movement_pattern != pattern:
                continue

        if query_str:
            if query_str not in exercise.name.lower() and query_str not in exercise.id.lower():
                continue

        results.append(exercise)

    return results


def get_exercise(exercise_id: str) -> Optional[Exercise]:
    """Retrieve an exercise by ID, or None if not found."""
    catalog = get_catalog()
    return catalog.get(exercise_id)
