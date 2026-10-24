"""
app/modules/exercises/catalog.py
Exercise catalog models, enums, and JSON loader.
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field


class MuscleGroup(str, Enum):
    CHEST = "chest"
    BACK = "back"
    QUADS = "quads"
    HAMSTRINGS = "hamstrings"
    DELTS = "delts"
    ARMS = "arms"
    CORE = "core"


class Equipment(str, Enum):
    BARBELL = "barbell"
    DUMBBELL = "dumbbell"
    CABLES = "cables"
    BODYWEIGHT = "bodyweight"


class MovementPattern(str, Enum):
    HORIZONTAL_PUSH = "horizontal_push"
    VERTICAL_PUSH = "vertical_push"
    HORIZONTAL_PULL = "horizontal_pull"
    VERTICAL_PULL = "vertical_pull"
    SQUAT = "squat"
    HINGE = "hinge"
    LUNGE = "lunge"
    ISOLATION = "isolation"
    CORE = "core"


class Difficulty(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class Exercise(BaseModel):
    id: str
    name: str
    primary_muscle: MuscleGroup
    secondary_muscles: List[MuscleGroup] = Field(default_factory=list)
    equipment: Equipment
    movement_pattern: MovementPattern
    is_compound: bool
    difficulty: Difficulty
    setup: List[str]
    form_cues: List[str]
    common_mistakes: List[str]
    injury_prevention: List[str]


_CATALOG: dict[str, Exercise] = {}
_INITIALIZED: bool = False


def get_data_path() -> Path:
    return Path(__file__).parent / "data" / "exercises.json"


def load_catalog(json_path: Optional[Path] = None) -> dict[str, Exercise]:
    """Load and validate the exercise catalog JSON once.
    Fails loudly on duplicate IDs or schema validation errors.
    """
    global _CATALOG, _INITIALIZED
    path = json_path or get_data_path()
    if not path.exists():
        raise FileNotFoundError(f"Exercise data file not found at {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw_items = json.load(f)

    catalog: dict[str, Exercise] = {}
    for item in raw_items:
        exercise = Exercise.model_validate(item)
        if exercise.id in catalog:
            raise ValueError(f"Duplicate exercise ID found in catalog: '{exercise.id}'")
        catalog[exercise.id] = exercise

    _CATALOG = catalog
    _INITIALIZED = True
    return _CATALOG


def get_catalog() -> dict[str, Exercise]:
    """Return the global cached catalog, initializing if necessary."""
    global _CATALOG, _INITIALIZED
    if not _INITIALIZED:
        load_catalog()
    return _CATALOG
