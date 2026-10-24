"""
tests/test_nutrition.py
Phase 2 tests: calculator pure functions + API endpoints.
"""

from __future__ import annotations

import pytest

from app.modules.nutrition.calculator import (
    MacroResult,
    bmr_katch_mcardle,
    bmr_mifflin_st_jeor,
    calculate,
    macro_targets,
    target_calories,
    tdee,
    CALORIE_FLOOR_FEMALE,
    CALORIE_FLOOR_MALE,
    KCAL_PER_G_CARB,
    KCAL_PER_G_FAT,
    KCAL_PER_G_PROTEIN,
)


# ── BMR tests ─────────────────────────────────────────────────────────────────

def test_bmr_mifflin_male():
    # 80 kg, 180 cm, 30 yo male → 10*80 + 6.25*180 - 5*30 + 5 = 1780
    result = bmr_mifflin_st_jeor("male", 80.0, 180.0, 30)
    assert abs(result - 1780.0) < 0.5


def test_bmr_mifflin_female():
    # 60 kg, 165 cm, 25 yo female → 10*60 + 6.25*165 - 5*25 - 161 = 1345.25
    result = bmr_mifflin_st_jeor("female", 60.0, 165.0, 25)
    assert abs(result - 1345.25) < 0.5


def test_bmr_katch_mcardle():
    # 80 kg, 15% bf → lean=68kg → 370 + 21.6*68 = 1838.8
    result = bmr_katch_mcardle(80.0, 15.0)
    assert abs(result - 1838.8) < 0.5


def test_bmr_mifflin_invalid_weight():
    with pytest.raises(ValueError, match="weight_kg"):
        bmr_mifflin_st_jeor("male", -10.0, 175.0, 25)


def test_bmr_katch_invalid_body_fat():
    with pytest.raises(ValueError, match="body_fat_pct"):
        bmr_katch_mcardle(80.0, 99.0)


# ── TDEE tests ────────────────────────────────────────────────────────────────

def test_tdee_all_activity_levels():
    bmr = 1800.0
    expected = {
        "sedentary": 1800 * 1.2,
        "light": 1800 * 1.375,
        "moderate": 1800 * 1.55,
        "very_active": 1800 * 1.725,
        "extreme": 1800 * 1.9,
    }
    for level, exp in expected.items():
        assert abs(tdee(bmr, level) - exp) < 0.1


def test_tdee_invalid_activity():
    with pytest.raises(ValueError):
        tdee(1800.0, "ultramarathon")


# ── Target calories tests ─────────────────────────────────────────────────────

def test_target_calories_hypertrophy():
    val, floor, warns = target_calories(2000.0, "hypertrophy", "male")
    assert abs(val - 2200.0) < 0.1
    assert not floor

def test_target_calories_fat_loss():
    val, floor, warns = target_calories(2000.0, "fat_loss", "male")
    assert abs(val - 1600.0) < 0.1

def test_calorie_floor_male():
    val, floor, warns = target_calories(1000.0, "fat_loss", "male")
    assert val == CALORIE_FLOOR_MALE
    assert floor
    assert len(warns) > 0

def test_calorie_floor_female():
    val, floor, warns = target_calories(800.0, "fat_loss", "female")
    assert val == CALORIE_FLOOR_FEMALE
    assert floor


# ── Macros tests ──────────────────────────────────────────────────────────────

def test_macros_sum_to_target():
    """Protein + carbs + fat kcal must be within 2 kcal of target."""
    result = calculate(
        sex="male", weight_kg=80.0, height_cm=180.0, age=30,
        activity_level="moderate", goal="hypertrophy", somatotype="mesomorph"
    )
    actual_kcal = (
        result.protein_g * KCAL_PER_G_PROTEIN
        + result.carbs_g * KCAL_PER_G_CARB
        + result.fat_g * KCAL_PER_G_FAT
    )
    assert abs(actual_kcal - result.target_kcal) < 2.0


def test_macros_fat_loss_higher_protein():
    fat_loss = calculate(
        sex="male", weight_kg=80.0, height_cm=180.0, age=30,
        activity_level="moderate", goal="fat_loss", somatotype="mesomorph"
    )
    hypertrophy = calculate(
        sex="male", weight_kg=80.0, height_cm=180.0, age=30,
        activity_level="moderate", goal="hypertrophy", somatotype="mesomorph"
    )
    assert fat_loss.protein_g > hypertrophy.protein_g


# ── End-to-end API tests ──────────────────────────────────────────────────────

def test_calculate_macros_endpoint_defaults(client):
    resp = client.post("/api/nutrition/calculate-macros", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert "bmr" in data
    assert "target_kcal" in data
    assert data["bmr"] > 0


def test_calculate_macros_endpoint_overrides(client):
    resp = client.post("/api/nutrition/calculate-macros", json={
        "sex": "female", "age": 28, "weight_kg": 60.0,
        "height_cm": 165.0, "activity_level": "moderate",
        "goal": "fat_loss", "somatotype": "mesomorph"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["bmr_formula"] == "Mifflin-St Jeor"


def test_meal_plan_endpoint_slot_totals_match_daily(client):
    """Sum of slot macros must equal daily totals within rounding (2 g)."""
    resp = client.post("/api/nutrition/plan", json={
        "sex": "male", "age": 30, "weight_kg": 80.0,
        "height_cm": 180.0, "activity_level": "moderate",
        "goal": "hypertrophy", "somatotype": "mesomorph",
        "meals_per_day": 4
    })
    assert resp.status_code == 200
    data = resp.json()
    meals = data["meals"]
    total_p = sum(m["protein_g"] for m in meals)
    total_c = sum(m["carbs_g"] for m in meals)
    total_f = sum(m["fat_g"] for m in meals)
    assert abs(total_p - data["macros"]["protein_g"]) <= 2.0
    assert abs(total_c - data["macros"]["carbs_g"]) <= 2.0
    assert abs(total_f - data["macros"]["fat_g"]) <= 2.0


def test_meal_plan_invalid_meals_per_day(client):
    resp = client.post("/api/nutrition/plan", json={"meals_per_day": 10})
    assert resp.status_code == 422


def test_scan_meal_invalid_base64(client):
    resp = client.post("/api/nutrition/scan-meal", json={"image_base64": "invalid_not_base64!!!"})
    assert resp.status_code == 400


def test_scan_meal_valid_payload(client):
    import base64
    # Create 120-byte valid base64 dummy image
    dummy_bytes = b"GIF89a" + b"\x00" * 150
    dummy_b64 = base64.b64encode(dummy_bytes).decode("utf-8")

    resp = client.post("/api/nutrition/scan-meal", json={
        "image_base64": f"data:image/jpeg;base64,{dummy_b64}",
        "mime_type": "image/jpeg",
        "meal_slot": "Post-Workout Lunch",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "meal_name" in data
    assert "total_calories" in data
    assert data["total_calories"] > 0
    assert "food_items" in data
    assert len(data["food_items"]) >= 1
