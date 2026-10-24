"""
backend/tests/test_overload.py
Comprehensive tests for Module 4: Progressive Overload logging, algorithms, and endpoints.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import pytest

from app.modules.exercises.catalog import get_catalog
from app.modules.progressive_overload.algorithms import (
    DEFAULT_INCREMENT_UPPER_COMPOUND,
    Recommendation,
    detect_plateau,
    double_progression,
    epley_1rm,
    linear_progression,
    parse_rep_range,
    weekly_volume,
)
from app.modules.progressive_overload.models import UnitType, WorkoutSetCreate


# ── Algorithms Unit Tests ─────────────────────────────────────────────────────

def test_epley_formula():
    """Verify Epley 1RM formula: weight * (1 + reps / 30)."""
    assert epley_1rm(100.0, 1) == 100.0
    # 100 kg for 10 reps -> 100 * (1 + 10/30) = 133.333...
    assert abs(epley_1rm(100.0, 10) - 133.33) < 0.05
    assert epley_1rm(0, 10) == 0.0
    assert epley_1rm(100, 0) == 0.0


def test_parse_rep_range():
    assert parse_rep_range("6-12") == (6, 12)
    assert parse_rep_range((8, 12)) == (8, 12)
    assert parse_rep_range("5") == (5, 5)


def test_double_progression_exact_prompt_example():
    """Exact example from prompt:
    'Last session: 80 kg for 3x8 at RPE 8. Target: 80 kg for 3x9, or 82.5 kg for 3x6.'
    """
    last_session_sets = [
        {"reps": 8, "weight_kg": 80.0, "rpe": 8.0},
        {"reps": 8, "weight_kg": 80.0, "rpe": 8.0},
        {"reps": 8, "weight_kg": 80.0, "rpe": 8.0},
    ]
    rec = double_progression(
        last_session_sets=last_session_sets,
        rep_range="6-12",
        increment_kg=2.5,
    )
    assert rec.weight_kg == 80.0
    assert rec.rep_target == "3x9"
    assert "82.5" in rec.alternative
    assert "82.5 kg for 3x6" in rec.alternative
    assert "80" in rec.reason


def test_double_progression_advance_weight_at_top_of_range():
    """When all sets hit 12 reps at RPE <= 8.5, advance weight by 2.5 kg to 82.5 kg for 3x6."""
    last_session_sets = [
        {"reps": 12, "weight_kg": 80.0, "rpe": 8.0},
        {"reps": 12, "weight_kg": 80.0, "rpe": 8.5},
        {"reps": 12, "weight_kg": 80.0, "rpe": 7.5},
    ]
    rec = double_progression(
        last_session_sets=last_session_sets,
        rep_range="6-12",
        increment_kg=2.5,
    )
    assert rec.weight_kg == 82.5
    assert rec.rep_target == "3x6"
    assert rec.alternative is None


def test_linear_progression_success_and_hold():
    # Success: all 3 sets hit 5 reps -> advance by 2.5 kg
    sets_ok = [
        {"reps": 5, "weight_kg": 100.0},
        {"reps": 5, "weight_kg": 100.0},
        {"reps": 5, "weight_kg": 100.0},
    ]
    rec_ok = linear_progression(sets_ok, weekly_increment_kg=2.5, prescribed_reps=5)
    assert rec_ok.weight_kg == 102.5
    assert rec_ok.rep_target == "3x5"

    # Miss: set 3 only got 4 reps -> hold weight at 100 kg
    sets_miss = [
        {"reps": 5, "weight_kg": 100.0},
        {"reps": 5, "weight_kg": 100.0},
        {"reps": 4, "weight_kg": 100.0},
    ]
    rec_miss = linear_progression(sets_miss, weekly_increment_kg=2.5, prescribed_reps=5)
    assert rec_miss.weight_kg == 100.0
    assert "Hold weight" in rec_miss.reason


def test_plateau_detection():
    # Flat series (sessions are newest first: s1, s2, s3)
    # Session 1: 100kg x 5 (1RM ~116.6)
    # Session 2: 100kg x 5 (1RM ~116.6)
    # Session 3: 100kg x 5 (1RM ~116.6)
    flat_series = [
        [{"weight_kg": 100.0, "reps": 5, "rpe": 9.5}],
        [{"weight_kg": 100.0, "reps": 5, "rpe": 9.0}],
        [{"weight_kg": 100.0, "reps": 5, "rpe": 8.0}],
    ]
    is_plat, deload = detect_plateau(flat_series, window=3)
    assert is_plat is True
    assert deload is True  # RPE was trending up (9.5 vs 8.0)

    # Rising series (Session 1 > Session 3)
    rising_series = [
        [{"weight_kg": 105.0, "reps": 5, "rpe": 8.0}],
        [{"weight_kg": 102.5, "reps": 5, "rpe": 8.0}],
        [{"weight_kg": 100.0, "reps": 5, "rpe": 8.0}],
    ]
    is_plat_rising, deload_rising = detect_plateau(rising_series, window=3)
    assert is_plat_rising is False
    assert deload_rising is False


def test_weekly_volume_bucketing():
    catalog = get_catalog()
    monday = date(2026, 10, 19)

    sets = [
        # Inside the week: bench press (chest) with RPE 8 -> counted
        {
            "exercise_id": "barbell-bench-press",
            "performed_at": datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc),
            "rpe": 8.0,
        },
        # Inside the week: warm-up set with RPE 5 -> NOT counted (< 6.0)
        {
            "exercise_id": "barbell-bench-press",
            "performed_at": datetime(2026, 10, 20, 10, 5, tzinfo=timezone.utc),
            "rpe": 5.0,
        },
        # Outside the week (previous week) -> NOT counted
        {
            "exercise_id": "barbell-bench-press",
            "performed_at": datetime(2026, 10, 15, 10, 0, tzinfo=timezone.utc),
            "rpe": 8.0,
        },
        # Inside the week: squat (quads) with RPE 9 -> counted
        {
            "exercise_id": "barbell-back-squat",
            "performed_at": datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc),
            "rpe": 9.0,
        },
    ]

    vol = weekly_volume(sets, catalog, monday)
    assert vol["chest"]["count"] == 1
    assert vol["quads"]["count"] == 1
    assert vol["chest"]["status"] == "below"  # < 10


# ── HTTP Router & Integration Tests ───────────────────────────────────────────

def test_api_log_set_single_and_unit_conversion(client):
    # Log 176.37 lb (~80.0 kg)
    payload = {
        "exercise_id": "barbell-bench-press",
        "set_number": 1,
        "reps": 8,
        "weight": 176.37,
        "unit": "lb",
        "rpe": 8.0,
    }
    res = client.post("/api/overload/log-set", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert abs(data["weight_kg"] - 80.0) < 0.1
    # RIR should be auto-derived to 10 - 8 = 2
    assert data["rir"] == 2


def test_api_log_set_rpe_rir_conflict(client):
    # RPE 8 and RIR 4 conflict: 10 - 4 = 6 != 8 (diff is 2 > 1)
    payload = {
        "exercise_id": "barbell-bench-press",
        "set_number": 1,
        "reps": 8,
        "weight": 80.0,
        "unit": "kg",
        "rpe": 8.0,
        "rir": 4,
    }
    res = client.post("/api/overload/log-set", json=payload)
    assert res.status_code == 422


def test_api_log_set_unknown_exercise_404(client):
    payload = {
        "exercise_id": "non-existent-exercise",
        "set_number": 1,
        "reps": 8,
        "weight": 80.0,
    }
    res = client.post("/api/overload/log-set", json=payload)
    assert res.status_code == 404


def test_api_log_sets_bulk_and_history_grouping(client):
    now = datetime.now(timezone.utc)
    bulk_payload = [
        {
            "exercise_id": "barbell-back-squat",
            "session_label": "Legs A",
            "performed_at": now.isoformat(),
            "set_number": 1,
            "reps": 5,
            "weight": 100.0,
            "unit": "kg",
            "rpe": 8.0,
        },
        {
            "exercise_id": "barbell-back-squat",
            "session_label": "Legs A",
            "performed_at": now.isoformat(),
            "set_number": 2,
            "reps": 5,
            "weight": 100.0,
            "unit": "kg",
            "rpe": 8.5,
        },
    ]
    res = client.post("/api/overload/log-set", json=bulk_payload)
    assert res.status_code == 201
    assert len(res.json()) == 2

    # Query history
    hist_res = client.get("/api/overload/history/barbell-back-squat")
    assert hist_res.status_code == 200
    groups = hist_res.json()
    assert len(groups) >= 1
    assert len(groups[0]["sets"]) == 2
    assert groups[0]["session_label"] == "Legs A"


def test_api_recommendation_no_history_and_with_history(client):
    # No history case for deadlift
    res_empty = client.get("/api/overload/recommendation/barbell-deadlift")
    assert res_empty.status_code == 200
    data_empty = res_empty.json()
    assert "No history" in data_empty["reason"]

    # Log 3 sets of bench press at 80 kg for 8 reps
    now = datetime.now(timezone.utc)
    sets_data = [
        {
            "exercise_id": "incline-dumbbell-press",
            "performed_at": now.isoformat(),
            "set_number": i,
            "reps": 8,
            "weight": 30.0,
            "unit": "kg",
            "rpe": 8.0,
        }
        for i in range(1, 4)
    ]
    client.post("/api/overload/log-set", json=sets_data)

    res_rec = client.get("/api/overload/recommendation/incline-dumbbell-press")
    assert res_rec.status_code == 200
    rec = res_rec.json()
    assert rec["weight_kg"] == 30.0
    assert rec["rep_target"] == "3x9"


def test_api_weekly_volume_summary(client):
    res = client.get("/api/overload/volume")
    assert res.status_code == 200
    data = res.json()
    assert "week_start" in data
    assert "muscles" in data
    assert "chest" in data["muscles"]
