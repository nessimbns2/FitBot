"""
Phase 9.2: Safety and Guardrails Test Suite.
Tests crash diets, steroids/PED refusal rules, injury/pain disclaimers, and rate limiting.
"""

import pytest
from fastapi.testclient import TestClient
from main_v2 import app
from app.modules.nutrition.calculator import calculate
from app.modules.rag_core.engine import (
    FakeEmbedder,
    FakeLLMClient,
    SearchResult,
    VectorStore,
    build_prompt,
    SAFETY_DISCLAIMER,
    set_llm_client,
    set_vector_store,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_guardrail_crash_diet_floor_enforcement():
    """Crash diets below physiological safety floors must be clamped with explicit warnings."""
    # Extreme female restriction
    res_female = calculate(
        sex="female",
        weight_kg=42.0,
        height_cm=150.0,
        age=30,
        activity_level="sedentary",
        goal="fat_loss",
        somatotype="mesomorph",
    )
    assert res_female.target_kcal == 1200.0
    assert res_female.floor_applied is True
    assert any("below the minimum" in w for w in res_female.warnings)

    # Extreme male restriction
    res_male = calculate(
        sex="male",
        weight_kg=52.0,
        height_cm=160.0,
        age=35,
        activity_level="sedentary",
        goal="fat_loss",
        somatotype="mesomorph",
    )
    assert res_male.target_kcal == 1500.0
    assert res_male.floor_applied is True
    assert any("below the minimum" in w for w in res_male.warnings)


def test_guardrail_prompt_includes_safety_disclaimer():
    """Every generated prompt must embed the mandatory medical disclaimer."""
    system_prompt, _ = build_prompt(
        intent="general",
        facts="weight: 80kg",
        numbers="calories: 2500",
        passages=[
            SearchResult(
                text="Focus on progressive tension overload.",
                source="guide.pdf",
                page=1,
                category="exercise",
                score=0.85,
            )
        ],
        history=[],
    )
    assert SAFETY_DISCLAIMER in system_prompt
    assert "medical or diagnostic advice" in system_prompt


def test_guardrail_steroid_and_ped_refusal_rules():
    """Verify that all relevant prompt templates explicitly instruct the LLM to refuse PEDs and anabolic steroids."""
    for intent in ["nutrition", "exercise_technique", "general"]:
        system_prompt, _ = build_prompt(
            intent=intent,
            facts="goal: hypertrophy",
            numbers="none",
            passages=[],
            history=[],
        )
        assert ("anabolic steroids" in system_prompt.lower() or "ped" in system_prompt.lower())


def test_guardrail_exercise_form_cues_pain_warning(client, tmp_path):
    """Calling form-cue endpoint with pain/injury question must return medical caution in extra_guidance."""
    mock_store = VectorStore(vectorstore_dir=tmp_path, embedder=FakeEmbedder())
    set_vector_store(mock_store)
    set_llm_client(FakeLLMClient("Guidance response."))

    res = client.post(
        "/api/exercises/form-cue",
        json={
            "exercise_id": "barbell-back-squat",
            "question": "I feel sharp knee pain at the bottom of the squat",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["extra_guidance"] is not None
    assert "physical therapist" in data["extra_guidance"].lower()


def test_guardrail_rate_limiter_registered():
    """Verify SlowAPI rate limiter is attached to app state."""
    assert hasattr(app.state, "limiter")
    assert app.state.limiter is not None
