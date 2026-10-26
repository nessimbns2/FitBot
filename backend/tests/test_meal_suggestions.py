"""
tests/test_meal_suggestions.py
"What should I eat to finish today?": Python computes the numbers, a stand-in
replaces the AI, and a missing or broken AI must never produce fake suggestions.
"""

from __future__ import annotations

import json

import pytest

from app.core.config import settings
from app.modules.nutrition import suggestion_service as svc
from app.modules.rag_core.engine import FakeLLMClient

@pytest.fixture(autouse=True)
def _reset_rate_limit():
    """The app allows 60 requests/minute per client; tests share one in-memory
    counter, so start every test with a clean one."""
    from main_v2 import limiter

    limiter.reset()
    yield


URL = "/api/nutrition/suggest-meal"
LOG = "/api/nutrition/log"
SUMMARY = "/api/nutrition/log/summary"
LOG_ROUTER = "app.modules.nutrition.log_router"


class StubLLM:
    """Records every call and returns a fixed answer (or raises)."""

    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def complete(self, messages, system):
        self.calls.append({"messages": messages, "system": system})
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def _ai(text_or_obj):
    return text_or_obj if isinstance(text_or_obj, str) else json.dumps(text_or_obj)


def _item(name="Greek yogurt bowl", calories=350, protein=30, carbs=40, fat=8, **extra):
    base = {"name": name, "description": "Quick and filling.", "portion": "250 g yogurt",
            "calories": calories, "protein_g": protein, "carbs_g": carbs, "fat_g": fat}
    base.update(extra)
    return base


@pytest.fixture
def use_ai(monkeypatch):
    """Configure a key and install a stub AI. Returns a function: use_ai(answer) -> stub."""
    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")

    def install(answer):
        stub = StubLLM(_ai(answer) if not isinstance(answer, Exception) else answer)
        monkeypatch.setattr(f"{LOG_ROUTER}.get_llm_client", lambda: stub)
        return stub

    return install


# ── Parsing and fit checks (pure functions) ───────────────────────────────────


def test_parse_marks_what_fits_and_puts_it_first():
    raw = _ai({"suggestions": [_item("Big", calories=900), _item("Small", calories=300)]})
    result = svc.parse_suggestions(raw, calories_left=500)
    assert [s.name for s in result] == ["Small", "Big"]
    assert [s.fits_remaining for s in result] == [True, False]


def test_parse_accepts_text_around_the_json():
    raw = "Sure!\n```json\n" + _ai({"suggestions": [_item()]}) + "\n```\nEnjoy."
    assert len(svc.parse_suggestions(raw, 800)) == 1


def test_parse_keeps_at_most_three():
    raw = _ai({"suggestions": [_item(f"Meal {i}") for i in range(6)]})
    assert len(svc.parse_suggestions(raw, 800)) == 3


def test_parse_drops_invalid_items_but_keeps_valid_ones():
    raw = _ai({"suggestions": [
        _item("Negative", calories=-50),
        {"calories": 200, "protein_g": 10, "carbs_g": 10, "fat_g": 5},          # no name
        _item("Text number", calories="a lot"),
        _item("Boolean", calories=True),
        _item("Absurd", calories=9000),
        "not an object",
        _item("Valid", calories=400),
    ]})
    result = svc.parse_suggestions(raw, 800)
    assert [s.name for s in result] == ["Valid"]


def test_parse_rounds_numbers_and_trims_text():
    raw = _ai({"suggestions": [_item("  Oats  ", calories=351.26, protein=12.34)]})
    s = svc.parse_suggestions(raw, 800)[0]
    assert s.name == "Oats"
    assert s.calories == 351.3
    assert s.protein_g == 12.3


@pytest.mark.parametrize(
    "raw",
    ["", "No JSON here", "{broken", "[1,2]", _ai({"suggestions": "nope"}),
     _ai({"other": []}), _ai({"suggestions": []}), _ai({"suggestions": [_item(calories=-1)]})],
)
def test_parse_raises_when_nothing_usable(raw):
    with pytest.raises(svc.AIUnavailable):
        svc.parse_suggestions(raw, 800)


# ── Endpoint: happy path ──────────────────────────────────────────────────────


def test_suggestions_are_returned_with_python_computed_remaining(client, use_ai):
    stub = use_ai({"suggestions": [_item("Fits", calories=300), _item("Too big", calories=5000 - 2500)]})
    expected = client.get(SUMMARY).json()["remaining"]

    res = client.post(URL, json={})
    assert res.status_code == 200
    data = res.json()
    assert data["ai_used"] is True
    assert data["remaining"] == expected          # not taken from the AI
    assert [s["name"] for s in data["suggestions"]][0] == "Fits"
    assert len(stub.calls) == 1


def test_prompt_contains_the_exact_remaining_numbers(client, use_ai):
    stub = use_ai({"suggestions": [_item()]})
    remaining = client.get(SUMMARY).json()["remaining"]
    client.post(URL, json={})
    user_msg = stub.calls[0]["messages"][0]["content"]
    assert f"{remaining['calories']:g} kcal" in user_msg
    assert f"{remaining['protein_g']:g} g" in user_msg


def test_remaining_shrinks_after_logging_food(client, use_ai):
    use_ai({"suggestions": [_item()]})
    before = client.post(URL, json={}).json()["remaining"]["calories"]
    client.post(LOG, json={"name": "Lunch", "calories": 800})
    after = client.post(URL, json={}).json()["remaining"]["calories"]
    assert round(before - after, 1) == 800


def test_meal_slot_and_preferences_reach_the_prompt(client, use_ai):
    stub = use_ai({"suggestions": [_item()]})
    client.post(URL, json={"meal_slot": "post_workout", "preferences": "vegetarian, no nuts"})
    user_msg = stub.calls[0]["messages"][0]["content"]
    assert "post-workout" in user_msg
    assert "vegetarian, no nuts" in user_msg


def test_system_prompt_forbids_changing_numbers_and_supplements(client, use_ai):
    stub = use_ai({"suggestions": [_item()]})
    client.post(URL, json={})
    system = stub.calls[0]["system"]
    assert "Never recalculate" in system
    assert "supplements" in system


# ── Endpoint: nothing to suggest ──────────────────────────────────────────────


def test_over_target_needs_no_ai_and_no_key(client, monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    client.post(LOG, json={"name": "Feast 1", "calories": 5000})
    client.post(LOG, json={"name": "Feast 2", "calories": 5000})
    res = client.post(URL, json={})
    assert res.status_code == 200
    data = res.json()
    assert data["ai_used"] is False
    assert data["suggestions"] == []
    assert "reached your calorie target" in data["message"]
    assert data["remaining"]["calories"] < 0


def test_almost_at_target_gives_a_message_not_a_suggestion(client, use_ai):
    stub = use_ai({"suggestions": [_item()]})
    left = client.get(SUMMARY).json()["remaining"]["calories"]
    # leave exactly 100 kcal (below the 150 kcal minimum)
    to_eat = left - 100
    while to_eat > 0:
        part = min(to_eat, 5000)
        client.post(LOG, json={"name": "Food", "calories": part})
        to_eat -= part
    data = client.post(URL, json={}).json()
    assert data["ai_used"] is False
    assert data["remaining"]["calories"] == 100
    assert "too little" in data["message"]
    assert stub.calls == []


# ── Endpoint: AI missing or broken ────────────────────────────────────────────


def test_no_key_returns_503_and_no_suggestions(client, monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    stub = StubLLM(_ai({"suggestions": [_item()]}))
    monkeypatch.setattr(f"{LOG_ROUTER}.get_llm_client", lambda: stub)
    res = client.post(URL, json={})
    assert res.status_code == 503
    assert "LLM_API_KEY" in res.json()["detail"]
    assert stub.calls == []


def test_fake_llm_client_counts_as_not_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(f"{LOG_ROUTER}.get_llm_client", lambda: FakeLLMClient())
    assert client.post(URL, json={}).status_code == 503


def test_ai_exception_returns_502(client, use_ai):
    use_ai(RuntimeError("quota exceeded"))
    res = client.post(URL, json={})
    assert res.status_code == 502
    assert "suggestions" not in res.json()


def test_canned_text_instead_of_json_returns_502(client, use_ai):
    # What GeminiLLMClient returns when every model fails: a coaching paragraph.
    use_ai("I'm here as your FitBot evidence-based coach! Aim for 1.6-2.2g of protein per kg.")
    assert client.post(URL, json={}).status_code == 502


def test_all_items_invalid_returns_502(client, use_ai):
    use_ai({"suggestions": [_item(calories=-10)]})
    assert client.post(URL, json={}).status_code == 502


# ── Endpoint: input validation ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "body",
    [{"preferences": "x" * 201}, {"meal_slot": "brunch"}, {"log_date": "2026/10/25"}],
)
def test_bad_request_returns_422(client, use_ai, body):
    use_ai({"suggestions": [_item()]})
    assert client.post(URL, json=body).status_code == 422
