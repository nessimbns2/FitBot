"""
tests/test_scan_meal.py
Photo meal scanner: the AI call is replaced, and a failure must never produce
made-up numbers.
"""

from __future__ import annotations

import base64
import json

import pytest

from app.core.config import settings

URL = "/api/nutrition/scan-meal"
ROUTER = "app.modules.nutrition.router"

_GOOD_AI_ANSWER = {
    "meal_name": "Chicken and rice",
    "confidence": "high",
    "total_calories": 640,
    "protein_g": 45.0,
    "carbs_g": 70.0,
    "fat_g": 14.0,
    "food_items": [
        {"name": "Chicken breast", "portion_est": "180 g", "calories": 300,
         "protein_g": 40.0, "carbs_g": 0.0, "fat_g": 7.0},
        {"name": "White rice", "portion_est": "200 g", "calories": 340,
         "protein_g": 5.0, "carbs_g": 70.0, "fat_g": 7.0},
    ],
    "coaching_tip": "Add vegetables for fibre.",
}


def _payload(**overrides) -> dict:
    image = base64.b64encode(b"GIF89a" + b"\x00" * 150).decode()
    body = {"image_base64": f"data:image/jpeg;base64,{image}", "mime_type": "image/jpeg"}
    body.update(overrides)
    return body


@pytest.fixture
def ai_key(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")


def _fake_vision(monkeypatch, answer):
    """Replace the Gemini call. `answer` is a string, or an Exception to raise."""
    calls = []

    def fake(image_bytes, mime_type, prompt):
        calls.append((image_bytes, mime_type, prompt))
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(f"{ROUTER}._call_vision_model", fake)
    return calls


def test_scan_returns_the_ai_result(client, ai_key, monkeypatch):
    _fake_vision(monkeypatch, json.dumps(_GOOD_AI_ANSWER))
    res = client.post(URL, json=_payload(meal_slot="Lunch"))
    assert res.status_code == 200
    data = res.json()
    assert data["meal_name"] == "Chicken and rice"
    assert data["total_calories"] == 640
    assert len(data["food_items"]) == 2


def test_scan_accepts_answer_wrapped_in_code_fences(client, ai_key, monkeypatch):
    _fake_vision(monkeypatch, "```json\n" + json.dumps(_GOOD_AI_ANSWER) + "\n```")
    assert client.post(URL, json=_payload()).status_code == 200


def test_scan_rounds_decimal_calories(client, ai_key, monkeypatch):
    answer = dict(_GOOD_AI_ANSWER, total_calories=520.6)
    answer["food_items"] = [dict(_GOOD_AI_ANSWER["food_items"][0], calories=300.4)]
    _fake_vision(monkeypatch, json.dumps(answer))
    data = client.post(URL, json=_payload()).json()
    assert data["total_calories"] == 521
    assert data["food_items"][0]["calories"] == 300


def test_scan_sends_image_and_slot_to_the_ai(client, ai_key, monkeypatch):
    calls = _fake_vision(monkeypatch, json.dumps(_GOOD_AI_ANSWER))
    client.post(URL, json=_payload(meal_slot="Dinner"))
    image_bytes, mime_type, prompt = calls[0]
    assert image_bytes.startswith(b"GIF89a")
    assert mime_type == "image/jpeg"
    assert "Dinner" in prompt


def test_scan_without_ai_key_returns_503_and_no_fake_meal(client, monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    calls = _fake_vision(monkeypatch, json.dumps(_GOOD_AI_ANSWER))
    res = client.post(URL, json=_payload())
    assert res.status_code == 503
    assert "LLM_API_KEY" in res.json()["detail"]
    assert "meal_name" not in res.json()
    assert calls == []  # the AI was never called


def test_scan_ai_failure_returns_503_not_a_fake_meal(client, ai_key, monkeypatch):
    _fake_vision(monkeypatch, RuntimeError("quota exceeded"))
    res = client.post(URL, json=_payload())
    assert res.status_code == 503
    assert "meal_name" not in res.json()
    assert "520" not in res.text


@pytest.mark.parametrize(
    "answer",
    [
        "Sorry, I cannot analyse this image.",
        "{not valid json}",
        "[1, 2, 3]",
        json.dumps({"meal_name": "Only a name"}),
        json.dumps(dict(_GOOD_AI_ANSWER, total_calories="lots")),
    ],
)
def test_scan_unreadable_answer_returns_502(client, ai_key, monkeypatch, answer):
    _fake_vision(monkeypatch, answer)
    res = client.post(URL, json=_payload())
    assert res.status_code == 502
    assert "meal_name" not in res.json()


def test_scan_still_validates_the_image_first(client, ai_key, monkeypatch):
    calls = _fake_vision(monkeypatch, json.dumps(_GOOD_AI_ANSWER))
    assert client.post(URL, json={"image_base64": "not base64!!!"}).status_code == 400
    tiny = base64.b64encode(b"abc").decode()
    assert client.post(URL, json={"image_base64": tiny}).status_code == 400
    assert calls == []
