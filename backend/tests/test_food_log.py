"""
tests/test_food_log.py
Food log CRUD: service functions and HTTP endpoints.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.modules.nutrition import food_log_service as svc
from app.modules.nutrition.models import (
    FoodLogCreate,
    FoodLogEntry,
    FoodLogUpdate,
    LogSource,
    MealSlotName,
)

@pytest.fixture(autouse=True)
def _reset_rate_limit():
    """The app allows 60 requests/minute per client; tests share one in-memory
    counter, so start every test with a clean one."""
    from main_v2 import limiter

    limiter.reset()
    yield


URL = "/api/nutrition/log"
TODAY = date.today().isoformat()


def _payload(**overrides) -> dict:
    body = {
        "log_date": "2026-10-25",
        "meal_slot": "lunch",
        "name": "Chicken and rice",
        "calories": 650,
        "protein_g": 48,
        "carbs_g": 70,
        "fat_g": 14,
    }
    body.update(overrides)
    return body


# ── Create ────────────────────────────────────────────────────────────────────


def test_create_entry_returns_201_and_saved_fields(client):
    res = client.post(URL, json=_payload(notes="meal prep"))
    assert res.status_code == 201
    data = res.json()
    assert data["id"] >= 1
    assert data["name"] == "Chicken and rice"
    assert data["meal_slot"] == "lunch"
    assert data["calories"] == 650
    assert data["protein_g"] == 48
    assert data["log_date"] == "2026-10-25"
    assert data["source"] == "manual"
    assert data["notes"] == "meal prep"


def test_create_defaults_to_today_snack_and_zero_macros(client):
    res = client.post(URL, json={"name": "Apple", "calories": 95})
    assert res.status_code == 201
    data = res.json()
    assert data["log_date"] == TODAY
    assert data["meal_slot"] == "snack"
    assert data["protein_g"] == 0
    assert data["carbs_g"] == 0
    assert data["fat_g"] == 0


def test_create_strips_name_whitespace(client):
    res = client.post(URL, json=_payload(name="  Oats  "))
    assert res.json()["name"] == "Oats"


def test_create_accepts_photo_scan_source(client):
    res = client.post(URL, json=_payload(source="photo_scan"))
    assert res.status_code == 201
    assert res.json()["source"] == "photo_scan"


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"name": "   "},
        {"name": "x" * 121},
        {"calories": -1},
        {"calories": 5001},
        {"protein_g": -5},
        {"carbs_g": 501},
        {"fat_g": -0.1},
        {"meal_slot": "brunch"},
        {"source": "magic"},
        {"log_date": "not-a-date"},
        {"notes": "n" * 501},
    ],
)
def test_create_rejects_invalid_input(client, overrides):
    res = client.post(URL, json=_payload(**overrides))
    assert res.status_code == 422


def test_create_requires_name_and_calories(client):
    assert client.post(URL, json={"calories": 100}).status_code == 422
    assert client.post(URL, json={"name": "Apple"}).status_code == 422


# ── Read ──────────────────────────────────────────────────────────────────────


def test_list_returns_only_the_requested_day(client):
    client.post(URL, json=_payload(log_date="2026-10-24", name="Yesterday"))
    client.post(URL, json=_payload(log_date="2026-10-25", name="Today"))

    res = client.get(URL, params={"date": "2026-10-25"})
    assert res.status_code == 200
    assert [e["name"] for e in res.json()] == ["Today"]


def test_list_defaults_to_today(client):
    client.post(URL, json=_payload(log_date=TODAY, name="Now"))
    client.post(URL, json=_payload(log_date="2020-01-01", name="Old"))

    res = client.get(URL)
    assert [e["name"] for e in res.json()] == ["Now"]


def test_list_empty_day_returns_empty_list(client):
    res = client.get(URL, params={"date": "2030-01-01"})
    assert res.status_code == 200
    assert res.json() == []


def test_list_orders_by_meal_slot_then_creation(client):
    client.post(URL, json=_payload(meal_slot="snack", name="Nuts"))
    client.post(URL, json=_payload(meal_slot="dinner", name="Pasta"))
    client.post(URL, json=_payload(meal_slot="breakfast", name="Eggs"))
    client.post(URL, json=_payload(meal_slot="breakfast", name="Toast"))

    res = client.get(URL, params={"date": "2026-10-25"})
    assert [e["name"] for e in res.json()] == ["Eggs", "Toast", "Pasta", "Nuts"]


def test_list_rejects_bad_date(client):
    assert client.get(URL, params={"date": "nope"}).status_code == 422


def test_get_one_entry(client):
    entry_id = client.post(URL, json=_payload()).json()["id"]
    res = client.get(f"{URL}/{entry_id}")
    assert res.status_code == 200
    assert res.json()["id"] == entry_id


def test_get_missing_entry_returns_404(client):
    assert client.get(f"{URL}/9999").status_code == 404


def test_get_non_integer_id_returns_422(client):
    assert client.get(f"{URL}/abc").status_code == 422


# ── Update ────────────────────────────────────────────────────────────────────


def test_update_changes_only_sent_fields(client):
    entry_id = client.post(URL, json=_payload()).json()["id"]

    res = client.put(f"{URL}/{entry_id}", json={"calories": 800, "name": "Big lunch"})
    assert res.status_code == 200
    data = res.json()
    assert data["calories"] == 800
    assert data["name"] == "Big lunch"
    assert data["protein_g"] == 48        # untouched
    assert data["meal_slot"] == "lunch"   # untouched


def test_update_is_persisted(client):
    entry_id = client.post(URL, json=_payload()).json()["id"]
    client.put(f"{URL}/{entry_id}", json={"carbs_g": 10})
    assert client.get(f"{URL}/{entry_id}").json()["carbs_g"] == 10


def test_update_can_move_entry_to_another_day_and_slot(client):
    entry_id = client.post(URL, json=_payload()).json()["id"]
    client.put(f"{URL}/{entry_id}", json={"log_date": "2026-10-26", "meal_slot": "dinner"})

    assert client.get(URL, params={"date": "2026-10-25"}).json() == []
    moved = client.get(URL, params={"date": "2026-10-26"}).json()
    assert moved[0]["meal_slot"] == "dinner"


def test_update_refreshes_updated_at(client):
    created = client.post(URL, json=_payload()).json()
    updated = client.put(f"{URL}/{created['id']}", json={"calories": 700}).json()
    assert datetime.fromisoformat(updated["updated_at"]) > datetime.fromisoformat(
        created["created_at"]
    )
    assert updated["created_at"] == created["created_at"]


def test_update_can_clear_notes_with_null(client):
    entry_id = client.post(URL, json=_payload(notes="hello")).json()["id"]
    res = client.put(f"{URL}/{entry_id}", json={"notes": None})
    assert res.status_code == 200
    assert res.json()["notes"] is None


def test_update_null_does_not_erase_required_fields(client):
    entry_id = client.post(URL, json=_payload()).json()["id"]
    res = client.put(f"{URL}/{entry_id}", json={"calories": None, "protein_g": 50})
    assert res.status_code == 200
    assert res.json()["calories"] == 650
    assert res.json()["protein_g"] == 50


def test_update_with_empty_body_returns_422(client):
    entry_id = client.post(URL, json=_payload()).json()["id"]
    assert client.put(f"{URL}/{entry_id}", json={}).status_code == 422


@pytest.mark.parametrize(
    "body",
    [{"calories": -5}, {"calories": 9999}, {"name": "  "}, {"meal_slot": "brunch"}],
)
def test_update_rejects_invalid_values(client, body):
    entry_id = client.post(URL, json=_payload()).json()["id"]
    assert client.put(f"{URL}/{entry_id}", json=body).status_code == 422


def test_update_missing_entry_returns_404(client):
    assert client.put(f"{URL}/9999", json={"calories": 100}).status_code == 404


# ── Delete ────────────────────────────────────────────────────────────────────


def test_delete_removes_entry(client):
    entry_id = client.post(URL, json=_payload()).json()["id"]

    res = client.delete(f"{URL}/{entry_id}")
    assert res.status_code == 204
    assert res.content == b""
    assert client.get(f"{URL}/{entry_id}").status_code == 404
    assert client.get(URL, params={"date": "2026-10-25"}).json() == []


def test_delete_only_removes_the_targeted_entry(client):
    keep = client.post(URL, json=_payload(name="Keep")).json()["id"]
    drop = client.post(URL, json=_payload(name="Drop")).json()["id"]
    client.delete(f"{URL}/{drop}")
    assert client.get(f"{URL}/{keep}").status_code == 200


def test_delete_missing_entry_returns_404(client):
    assert client.delete(f"{URL}/9999").status_code == 404


def test_delete_twice_returns_404_the_second_time(client):
    entry_id = client.post(URL, json=_payload()).json()["id"]
    assert client.delete(f"{URL}/{entry_id}").status_code == 204
    assert client.delete(f"{URL}/{entry_id}").status_code == 404


# ── Service layer (no HTTP) ───────────────────────────────────────────────────


def test_service_create_and_get(session):
    created = svc.create_entry(
        session,
        FoodLogCreate(name="Banana", calories=105, carbs_g=27, meal_slot=MealSlotName.snack),
    )
    fetched = svc.get_entry(session, created.id)
    assert fetched.name == "Banana"
    assert fetched.log_date == date.today()
    assert fetched.source == LogSource.manual


def test_service_get_missing_raises(session):
    with pytest.raises(svc.FoodLogNotFound):
        svc.get_entry(session, 123)


def test_service_other_users_entry_is_not_visible(session):
    other = FoodLogEntry(
        user_id=2, log_date=date.today(), name="Secret", calories=100
    )
    session.add(other)
    session.commit()
    session.refresh(other)

    with pytest.raises(svc.FoodLogNotFound):
        svc.get_entry(session, other.id)
    assert svc.list_entries(session) == []


def test_service_update_without_fields_raises_value_error(session):
    created = svc.create_entry(session, FoodLogCreate(name="Rice", calories=200))
    with pytest.raises(ValueError):
        svc.update_entry(session, created.id, FoodLogUpdate())


def test_service_delete_missing_raises(session):
    with pytest.raises(svc.FoodLogNotFound):
        svc.delete_entry(session, 42)


def test_service_list_defaults_to_today(session):
    svc.create_entry(session, FoodLogCreate(name="Today item", calories=50))
    svc.create_entry(
        session,
        FoodLogCreate(
            name="Last week", calories=50, log_date=date.today() - timedelta(days=7)
        ),
    )
    assert [e.name for e in svc.list_entries(session)] == ["Today item"]


# ── Daily summary: pure math ──────────────────────────────────────────────────

from app.modules.nutrition.models import MacroTotals  # noqa: E402

_TARGETS = MacroTotals(calories=2500, protein_g=160, carbs_g=300, fat_g=70)


def _entry(**kw) -> FoodLogEntry:
    base = dict(user_id=1, log_date=date(2026, 10, 25), name="x", calories=0)
    base.update(kw)
    return FoodLogEntry(**base)


def test_build_summary_adds_up_entries():
    entries = [
        _entry(calories=500, protein_g=30, carbs_g=60, fat_g=10),
        _entry(calories=700, protein_g=45.5, carbs_g=80, fat_g=20.25),
    ]
    s = svc.build_summary(date(2026, 10, 25), entries, _TARGETS)
    assert s.entry_count == 2
    assert s.consumed.calories == 1200
    assert s.consumed.protein_g == 75.5
    assert s.consumed.carbs_g == 140
    assert s.consumed.fat_g == 30.2  # 30.25 rounded to 1 decimal


def test_build_summary_remaining_is_target_minus_consumed():
    entries = [_entry(calories=1000, protein_g=40, carbs_g=100, fat_g=25)]
    s = svc.build_summary(date(2026, 10, 25), entries, _TARGETS)
    assert s.remaining.calories == 1500
    assert s.remaining.protein_g == 120
    assert s.remaining.carbs_g == 200
    assert s.remaining.fat_g == 45


def test_build_summary_percent_of_target():
    entries = [_entry(calories=1250, protein_g=80, carbs_g=75, fat_g=70)]
    s = svc.build_summary(date(2026, 10, 25), entries, _TARGETS)
    assert s.percent_of_target.calories == 50.0
    assert s.percent_of_target.protein_g == 50.0
    assert s.percent_of_target.carbs_g == 25.0
    assert s.percent_of_target.fat_g == 100.0


def test_build_summary_over_target_gives_negative_remaining_and_over_100_percent():
    entries = [_entry(calories=3000, protein_g=160, carbs_g=300, fat_g=70)]
    s = svc.build_summary(date(2026, 10, 25), entries, _TARGETS)
    assert s.remaining.calories == -500
    assert s.percent_of_target.calories == 120.0


def test_build_summary_with_no_entries():
    s = svc.build_summary(date(2026, 10, 25), [], _TARGETS)
    assert s.entry_count == 0
    assert s.consumed.calories == 0
    assert s.remaining == _TARGETS
    assert s.percent_of_target.calories == 0.0


def test_build_summary_zero_target_gives_no_percent():
    zero = MacroTotals(calories=2000, protein_g=0, carbs_g=250, fat_g=60)
    s = svc.build_summary(date(2026, 10, 25), [_entry(calories=100, protein_g=5)], zero)
    assert s.percent_of_target.protein_g is None
    assert s.percent_of_target.calories == 5.0


def test_build_summary_passes_through_floor_info():
    s = svc.build_summary(
        date(2026, 10, 25), [], _TARGETS, floor_applied=True, warnings=["floor"]
    )
    assert s.floor_applied is True
    assert s.warnings == ["floor"]


# ── Daily summary: endpoint ───────────────────────────────────────────────────

SUMMARY = "/api/nutrition/log/summary"


def test_summary_empty_day_equals_targets(client):
    res = client.get(SUMMARY, params={"date": "2030-01-01"})
    assert res.status_code == 200
    data = res.json()
    assert data["entry_count"] == 0
    assert data["consumed"]["calories"] == 0
    assert data["remaining"] == data["targets"]


def test_summary_targets_match_macro_calculator(client):
    macros = client.post("/api/nutrition/calculate-macros", json={}).json()
    targets = client.get(SUMMARY).json()["targets"]
    assert targets["calories"] == macros["target_kcal"]
    assert targets["protein_g"] == macros["protein_g"]
    assert targets["carbs_g"] == macros["carbs_g"]
    assert targets["fat_g"] == macros["fat_g"]


def test_summary_adds_entries_of_that_day_only(client):
    client.post(URL, json=_payload(log_date="2026-10-25", calories=500, protein_g=30))
    client.post(URL, json=_payload(log_date="2026-10-25", calories=300, protein_g=20))
    client.post(URL, json=_payload(log_date="2026-10-24", calories=4999, protein_g=99))

    data = client.get(SUMMARY, params={"date": "2026-10-25"}).json()
    assert data["entry_count"] == 2
    assert data["consumed"]["calories"] == 800
    assert data["consumed"]["protein_g"] == 50
    assert data["log_date"] == "2026-10-25"


def test_summary_remaining_is_consistent_with_targets(client):
    client.post(URL, json=_payload(calories=1000))
    data = client.get(SUMMARY, params={"date": "2026-10-25"}).json()
    assert data["remaining"]["calories"] == round(
        data["targets"]["calories"] - 1000, 1
    )


def test_summary_defaults_to_today(client):
    client.post(URL, json=_payload(log_date=TODAY, calories=400))
    data = client.get(SUMMARY).json()
    assert data["log_date"] == TODAY
    assert data["consumed"]["calories"] == 400


def test_summary_updates_after_edit_and_delete(client):
    entry_id = client.post(URL, json=_payload(calories=600)).json()["id"]
    params = {"date": "2026-10-25"}
    assert client.get(SUMMARY, params=params).json()["consumed"]["calories"] == 600

    client.put(f"{URL}/{entry_id}", json={"calories": 900})
    assert client.get(SUMMARY, params=params).json()["consumed"]["calories"] == 900

    client.delete(f"{URL}/{entry_id}")
    assert client.get(SUMMARY, params=params).json()["consumed"]["calories"] == 0


def test_summary_route_is_not_mistaken_for_an_entry_id(client):
    # "/log/summary" must reach the summary handler, not "/log/{entry_id}" (422/404)
    assert client.get(SUMMARY).status_code == 200


def test_summary_rejects_bad_date(client):
    assert client.get(SUMMARY, params={"date": "2026/10/25"}).status_code == 422


# ── post_workout slot and ai_suggestion source ────────────────────────────────


def test_post_workout_slot_is_accepted_and_sorted_before_snack(client):
    client.post(URL, json=_payload(meal_slot="snack", name="Nuts"))
    client.post(URL, json=_payload(meal_slot="post_workout", name="Shake"))
    client.post(URL, json=_payload(meal_slot="dinner", name="Pasta"))

    res = client.get(URL, params={"date": "2026-10-25"})
    assert [e["name"] for e in res.json()] == ["Pasta", "Shake", "Nuts"]
    assert res.json()[1]["meal_slot"] == "post_workout"


def test_ai_suggestion_source_is_accepted(client):
    res = client.post(URL, json=_payload(source="ai_suggestion"))
    assert res.status_code == 201
    assert res.json()["source"] == "ai_suggestion"
