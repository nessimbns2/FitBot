"""
Phase 9.1: Architectural isolation, contract verification, and math edge cases.
"""

import inspect
import pytest
from app.modules.nutrition.calculator import (
    bmr_mifflin_st_jeor,
    bmr_katch_mcardle,
    choose_bmr,
    tdee,
    target_calories,
    macro_targets,
    calculate,
)
from app.modules.user.models import Sex, ActivityLevel, Goal, ExperienceLevel
from app.modules.exercises.generator import generate_routine, SplitType
from app.modules.exercises.catalog import Equipment, get_catalog
from app.modules.progressive_overload.algorithms import (
    double_progression,
    linear_progression,
    epley_1rm,
    detect_plateau,
    weekly_volume,
)
from app.modules.progressive_overload.models import WorkoutSetRead
from datetime import datetime, timezone


def test_bmr_edge_validations():
    with pytest.raises(ValueError, match="weight_kg must be positive"):
        bmr_mifflin_st_jeor("male", 0, 180, 25)
    with pytest.raises(ValueError, match="height_cm must be positive"):
        bmr_mifflin_st_jeor("male", 80, 0, 25)
    with pytest.raises(ValueError, match="age must be positive"):
        bmr_mifflin_st_jeor("male", 80, 180, 0)
    with pytest.raises(ValueError, match="weight_kg must be positive"):
        bmr_katch_mcardle(0, 15.0)
    with pytest.raises(ValueError, match="body_fat_pct must be 3-60"):
        bmr_katch_mcardle(80, 1.0)


def test_tdee_and_target_invalid_keys():
    with pytest.raises(ValueError, match="Unknown activity_level"):
        tdee(1800, "invalid_activity")
    with pytest.raises(ValueError, match="Unknown goal"):
        target_calories(2000, "invalid_goal", "male")


def test_somatotype_macro_shifts():
    """Verify ectomorph and endomorph macro adjustments."""
    endo = calculate(
        sex="male",
        weight_kg=80.0,
        height_cm=180.0,
        age=25,
        activity_level="moderate",
        goal="hypertrophy",
        somatotype="endomorph",
    )
    ecto = calculate(
        sex="male",
        weight_kg=80.0,
        height_cm=180.0,
        age=25,
        activity_level="moderate",
        goal="hypertrophy",
        somatotype="ectomorph",
    )
    meso = calculate(
        sex="male",
        weight_kg=80.0,
        height_cm=180.0,
        age=25,
        activity_level="moderate",
        goal="hypertrophy",
        somatotype="mesomorph",
    )

    # Endomorph has higher fat than mesomorph
    assert endo.fat_g > meso.fat_g
    # Ectomorph has higher carbs than endomorph
    assert ecto.carbs_g > endo.carbs_g


def test_safety_caloric_floors():
    """Under extreme deficit, floor must prevent dangerously low calories."""
    res_female = calculate(
        sex="female",
        weight_kg=40.0,
        height_cm=150.0,
        age=40,
        activity_level="sedentary",
        goal="fat_loss",
        somatotype="mesomorph",
    )
    assert res_female.target_kcal >= 1200
    assert res_female.floor_applied is True
    assert len(res_female.warnings) > 0

    res_male = calculate(
        sex="male",
        weight_kg=45.0,
        height_cm=155.0,
        age=40,
        activity_level="sedentary",
        goal="fat_loss",
        somatotype="mesomorph",
    )
    assert res_male.target_kcal >= 1500
    assert res_male.floor_applied is True
    assert len(res_male.warnings) > 0


def test_generate_routine_splits():
    """Verify routine generator for full_body, upper_lower, and ppl."""
    # Full body 3 days
    fb = generate_routine(
        split=SplitType.FULL_BODY,
        days_per_week=3,
        experience_level=ExperienceLevel.beginner,
        goal=Goal.strength,
        available_equipment=[Equipment.BARBELL, Equipment.DUMBBELL, Equipment.BODYWEIGHT],
    )
    assert len(fb.days) == 3
    assert fb.days[0].name == "Full Body A"
    assert len(fb.days[0].exercises) >= 4

    # Upper Lower 4 days
    ul = generate_routine(
        split=SplitType.UPPER_LOWER,
        days_per_week=4,
        experience_level=ExperienceLevel.intermediate,
        goal=Goal.hypertrophy,
        available_equipment=[Equipment.BARBELL, Equipment.DUMBBELL, Equipment.CABLES],
    )
    assert len(ul.days) == 4
    assert "Upper" in ul.days[0].name
    assert "Lower" in ul.days[1].name

    # PPL 6 days
    ppl = generate_routine(
        split=SplitType.PUSH_PULL_LEGS,
        days_per_week=6,
        experience_level=ExperienceLevel.advanced,
        goal=Goal.hypertrophy,
        available_equipment=[Equipment.BARBELL, Equipment.DUMBBELL, Equipment.CABLES],
    )
    assert len(ppl.days) == 6

    # Empty equipment edge case
    empty_res = generate_routine(
        split=SplitType.PUSH_PULL_LEGS,
        days_per_week=3,
        experience_level=ExperienceLevel.beginner,
        goal=Goal.strength,
        available_equipment=[],
    )
    assert len(empty_res.days) == 0
    assert len(empty_res.warnings) > 0


def test_overload_edge_cases():
    # Empty sets
    rec_empty = double_progression(
        last_session_sets=[],
        rep_range="8-12",
        increment_kg=2.5,
    )
    assert "No history found" in rec_empty.reason

    # Epley 0 or negative reps
    assert epley_1rm(100.0, 0) == 0.0
    assert epley_1rm(100.0, 1) == 100.0
    assert epley_1rm(100.0, 10) > 130.0

    # Plateau with fewer than 3 sessions
    sets = [
        {
            "id": 1,
            "user_id": 1,
            "exercise_id": "barbell-bench-press",
            "weight_kg": 100.0,
            "reps": 5,
            "set_number": 1,
            "performed_at": datetime.now(timezone.utc),
            "rpe": 8.0,
        }
    ]
    is_plat, deload = detect_plateau(sets)
    assert is_plat is False
    assert deload is False

    # Volume test
    catalog = get_catalog()
    today = datetime.now(timezone.utc).date()
    vol = weekly_volume(sets, catalog, today)
    assert "chest" in vol
    assert vol["chest"]["count"] == 1
    assert vol["chest"]["status"] == "below"


def test_architectural_isolation():
    """
    Architectural boundary rule:
    Routers should not contain raw SQL statements or bypass the service/calculation layer.
    """
    from app.modules.nutrition import router as nutrition_router
    from app.modules.exercises import router as exercise_router
    from app.modules.progressive_overload import router as overload_router

    for router_mod in [nutrition_router, exercise_router, overload_router]:
        source = inspect.getsource(router_mod)
        # Routers shouldn't execute raw sql strings
        assert "SELECT " not in source.upper()
        assert "INSERT INTO " not in source.upper()
        assert "DROP TABLE " not in source.upper()
