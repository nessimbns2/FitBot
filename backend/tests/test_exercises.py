"""
backend/tests/test_exercises.py
Tests for Module 3: Exercise Catalog and Routine Generator.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from app.modules.exercises.catalog import (
    Equipment,
    Exercise,
    MovementPattern,
    MuscleGroup,
    get_catalog,
    load_catalog,
)
from app.modules.exercises.generator import (
    RoutineResult,
    SplitType,
    generate_routine,
)
from app.modules.exercises.service import get_exercise, list_exercises
from app.modules.user.models import ExperienceLevel, Goal


# ── Catalog Data & Validation Tests ───────────────────────────────────────────

def test_catalog_seed_file_validates():
    """Verify exercises.json contains valid Exercise objects with no duplicate IDs."""
    data_path = Path(__file__).resolve().parent.parent / "app" / "modules" / "exercises" / "data" / "exercises.json"
    assert data_path.exists()
    catalog = load_catalog(data_path)
    assert len(catalog) >= 56


def test_every_muscle_group_has_at_least_8_exercises():
    """Verify that every muscle group has at least 8 exercises."""
    catalog = get_catalog()
    counts = {m: 0 for m in MuscleGroup}
    for ex in catalog.values():
        counts[ex.primary_muscle] += 1

    for muscle, count in counts.items():
        assert count >= 8, f"Muscle {muscle} only has {count} exercises (expected >= 8)"


def test_exercises_cover_all_equipment_types():
    """Ensure catalog covers all 4 equipment types: barbell, dumbbell, cables, bodyweight."""
    catalog = get_catalog()
    eqs = {ex.equipment for ex in catalog.values()}
    for eq in Equipment:
        assert eq in eqs, f"Equipment type {eq} not found in catalog"


def test_exercise_has_required_cues_and_steps():
    """Each exercise must have setup steps, >=3 form cues, >=2 common mistakes, >=1 injury prevention."""
    catalog = get_catalog()
    for ex in catalog.values():
        assert len(ex.setup) >= 1, f"{ex.id} missing setup"
        assert len(ex.form_cues) >= 3, f"{ex.id} has fewer than 3 form cues"
        assert len(ex.common_mistakes) >= 2, f"{ex.id} has fewer than 2 common mistakes"
        assert len(ex.injury_prevention) >= 1, f"{ex.id} has fewer than 1 injury prevention cue"


# ── Service & Filters Tests ───────────────────────────────────────────────────

def test_service_get_exercise():
    ex = get_exercise("barbell-bench-press")
    assert ex is not None
    assert ex.name == "Barbell Bench Press"
    assert ex.primary_muscle == MuscleGroup.CHEST

    none_ex = get_exercise("non-existent-exercise-slug")
    assert none_ex is None


def test_service_filters_combine_correctly():
    # Filter by muscle=chest, equipment=barbell
    chest_barbell = list_exercises(muscle=MuscleGroup.CHEST, equipment=Equipment.BARBELL)
    assert len(chest_barbell) >= 2
    for ex in chest_barbell:
        assert ex.primary_muscle == MuscleGroup.CHEST or MuscleGroup.CHEST in ex.secondary_muscles
        assert ex.equipment == Equipment.BARBELL

    # Add search query
    bench_only = list_exercises(muscle=MuscleGroup.CHEST, equipment=Equipment.BARBELL, q="bench")
    assert len(bench_only) >= 1
    for ex in bench_only:
        assert "bench" in ex.name.lower() or "bench" in ex.id.lower()


# ── Routine Generator Tests ───────────────────────────────────────────────────

def test_routine_generator_splits_day_structures():
    """Test push_pull_legs, upper_lower, full_body structures."""
    for split, days_count in [
        (SplitType.PUSH_PULL_LEGS, 3),
        (SplitType.PUSH_PULL_LEGS, 6),
        (SplitType.UPPER_LOWER, 4),
        (SplitType.FULL_BODY, 3),
    ]:
        result = generate_routine(
            split=split,
            days_per_week=days_count,
            experience_level=ExperienceLevel.intermediate,
            goal=Goal.hypertrophy,
            available_equipment=list(Equipment),
        )
        assert len(result.days) == days_count
        for day in result.days:
            assert len(day.exercises) >= 4
            # First exercise should be compound
            assert day.exercises[0].movement_pattern != MovementPattern.ISOLATION


def test_routine_generator_is_strictly_deterministic():
    """Identical inputs must always give identical routine outputs."""
    res1 = generate_routine(
        split=SplitType.PUSH_PULL_LEGS,
        days_per_week=4,
        experience_level=ExperienceLevel.beginner,
        goal=Goal.strength,
        available_equipment=[Equipment.BARBELL, Equipment.DUMBBELL],
    )
    res2 = generate_routine(
        split=SplitType.PUSH_PULL_LEGS,
        days_per_week=4,
        experience_level=ExperienceLevel.beginner,
        goal=Goal.strength,
        available_equipment=[Equipment.BARBELL, Equipment.DUMBBELL],
    )
    assert res1.model_dump() == res2.model_dump()


def test_routine_generator_equipment_filtering():
    """Verify only available equipment is selected."""
    result = generate_routine(
        split=SplitType.FULL_BODY,
        days_per_week=3,
        experience_level=ExperienceLevel.beginner,
        goal=Goal.hypertrophy,
        available_equipment=[Equipment.BODYWEIGHT],
    )
    catalog = get_catalog()
    for day in result.days:
        for ex_item in day.exercises:
            ex = catalog[ex_item.exercise_id]
            assert ex.equipment == Equipment.BODYWEIGHT


def test_routine_generator_invalid_days():
    with pytest.raises(ValueError):
        generate_routine(
            split=SplitType.FULL_BODY,
            days_per_week=1,
            experience_level=ExperienceLevel.beginner,
            goal=Goal.hypertrophy,
            available_equipment=list(Equipment),
        )
    with pytest.raises(ValueError):
        generate_routine(
            split=SplitType.FULL_BODY,
            days_per_week=7,
            experience_level=ExperienceLevel.beginner,
            goal=Goal.hypertrophy,
            available_equipment=list(Equipment),
        )


# ── HTTP Router Tests ─────────────────────────────────────────────────────────

def test_api_catalog_list_and_search(client):
    res = client.get("/api/exercises/catalog?muscle=chest")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 8

    res_q = client.get("/api/exercises/catalog?q=squat")
    assert res_q.status_code == 200
    squats = res_q.json()
    assert len(squats) >= 1
    assert any("squat" in item["id"].lower() for item in squats)


def test_api_catalog_single_exercise(client):
    res = client.get("/api/exercises/catalog/barbell-bench-press")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "barbell-bench-press"
    assert len(data["form_cues"]) >= 3


def test_api_catalog_unknown_404(client):
    res = client.get("/api/exercises/catalog/does-not-exist-xyz")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_api_generate_routine_with_profile_fallback(client):
    res = client.post("/api/exercises/generate-routine", json={})
    assert res.status_code == 200
    data = res.json()
    assert "days" in data
    assert len(data["days"]) == 4
    assert "weekly_sets_per_muscle" in data
