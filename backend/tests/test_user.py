"""
tests/test_user.py
Phase 1 tests: profile defaults, validation, partial update, sessions.
"""

from __future__ import annotations


# ── Profile ───────────────────────────────────────────────────────────────────


def test_get_profile_creates_defaults(client):
    resp = client.get("/api/user/profile")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 1
    assert data["age"] == 25
    assert data["goal"] == "hypertrophy"


def test_get_profile_idempotent(client):
    """Second call returns the same profile, not a duplicate."""
    r1 = client.get("/api/user/profile")
    r2 = client.get("/api/user/profile")
    assert r1.json()["id"] == r2.json()["id"] == 1


def test_update_profile_partial(client):
    """Partial PUT only changes the supplied fields."""
    resp = client.put("/api/user/profile", json={"age": 30, "goal": "fat_loss"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["age"] == 30
    assert data["goal"] == "fat_loss"
    # untouched field kept default
    assert data["sex"] == "male"


def test_update_profile_validation_age_too_young(client):
    resp = client.put("/api/user/profile", json={"age": 5})
    assert resp.status_code == 422


def test_update_profile_validation_weight_too_low(client):
    resp = client.put("/api/user/profile", json={"weight_kg": 10.0})
    assert resp.status_code == 422


def test_update_profile_validation_body_fat_too_high(client):
    resp = client.put("/api/user/profile", json={"body_fat_pct": 99.0})
    assert resp.status_code == 422


def test_update_profile_imperial_unit_system(client):
    resp = client.put("/api/user/profile", json={"unit_system": "imperial"})
    assert resp.status_code == 200
    assert resp.json()["unit_system"] == "imperial"


# ── Chat Sessions ─────────────────────────────────────────────────────────────


def test_list_sessions_empty(client):
    resp = client.get("/api/user/sessions")
    assert resp.status_code == 200
    assert resp.json() == []


def test_session_messages_404_on_unknown(client):
    resp = client.get("/api/user/sessions/nonexistent/messages")
    assert resp.status_code == 404


def test_delete_session_404_on_unknown(client):
    resp = client.delete("/api/user/sessions/nonexistent")
    assert resp.status_code == 404


def test_session_create_list_delete(client, session):
    """Create a session via service, list it, then delete it."""
    from app.modules.user.service import create_session, delete_session, list_sessions, get_or_create_default_profile

    get_or_create_default_profile(session)
    s = create_session(session, title="Test session")
    sessions = list_sessions(session)
    assert len(sessions) == 1
    assert sessions[0].title == "Test session"

    delete_session(session, s.id)
    assert list_sessions(session) == []


def test_session_delete_cascades_messages(client, session):
    """Deleting a session must also delete its messages."""
    from app.modules.user.service import (
        append_message,
        create_session,
        delete_session,
        get_or_create_default_profile,
        get_session_messages,
    )

    get_or_create_default_profile(session)
    s = create_session(session, "Cascade test")
    append_message(session, s.id, "user", "hello")
    append_message(session, s.id, "assistant", "world")
    assert len(get_session_messages(session, s.id)) == 2

    delete_session(session, s.id)
    # session is gone — further lookups should 404 via HTTPException
    import pytest
    with pytest.raises(Exception):
        get_session_messages(session, s.id)


def test_get_somatotype_questions(client: TestClient):
    """Test retrieving the 5 somatotype diagnostic assessment questions."""
    resp = client.get("/api/user/somatotype-questions")
    assert resp.status_code == 200
    questions = resp.json()
    assert len(questions) == 5
    for q in questions:
        assert "id" in q
        assert "question" in q
        assert len(q["options"]) == 3
        for opt in q["options"]:
            assert "value" in opt
            assert "archetype" in opt


def test_predict_somatotype_and_auto_apply(client: TestClient, session: Session):
    """Test predicting somatotype from answers and auto-applying to user profile."""
    payload = {
        "wrist_structure": "fingers_overlap",
        "body_frame": "narrow_linear",
        "weight_tendency": "hardgainer",
        "muscle_definition": "lean_low_muscle",
        "carb_response": "high_energy",
        "auto_apply": True,
    }
    resp = client.post("/api/user/predict-somatotype", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["predicted_somatotype"] == "ectomorph"
    assert data["profile_updated"] is True
    assert "carbohydrate" in data["traits_summary"].lower() or "slender" in data["traits_summary"].lower()
    assert "training_focus" in data
    assert "nutrition_focus" in data
    assert "macro_shift_note" in data

    # Verify database profile was updated
    prof_resp = client.get("/api/user/profile")
    assert prof_resp.status_code == 200
    assert prof_resp.json()["somatotype"] == "ectomorph"


def test_generate_athlete_blueprint_defaults(client: TestClient, session: Session):
    """Test generating athlete blueprint with existing profile defaults."""
    resp = client.post("/api/user/blueprint", json={})
    assert resp.status_code == 200
    data = resp.json()

    assert "athlete_archetype" in data
    assert "executive_summary" in data
    assert len(data["physiological_strengths"]) >= 1
    assert len(data["blindspots_and_risks"]) >= 1
    assert "volume_landmarks" in data
    assert "mev_sets_per_week" in data["volume_landmarks"]
    assert "mrv_sets_per_week" in data["volume_landmarks"]
    assert "recovery_capacity" in data["volume_landmarks"]
    assert "timeline_projection" in data
    assert "rate_of_change" in data["timeline_projection"]
    assert len(data["key_coaching_directives"]) >= 1
    assert "calculated_metrics" in data
    assert data["calculated_metrics"]["bmi"] > 10


def test_generate_athlete_blueprint_with_overrides(client: TestClient, session: Session):
    """Test generating athlete blueprint with explicit biometric overrides."""
    payload = {
        "age": 28,
        "sex": "female",
        "height_cm": 168.0,
        "weight_kg": 62.0,
        "body_fat_pct": 21.5,
        "somatotype": "mesomorph",
        "goal": "fat_loss",
        "experience_level": "intermediate",
        "activity_level": "very_active",
    }
    resp = client.post("/api/user/blueprint", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["calculated_metrics"]["somatotype"] == "mesomorph"
    assert data["calculated_metrics"]["goal"] == "fat_loss"
    assert data["calculated_metrics"]["experience_level"] == "intermediate"
    assert data["calculated_metrics"]["lean_mass_kg"] is not None
    assert "fat loss" in data["timeline_projection"]["rate_of_change"].lower() or "kg" in data["timeline_projection"]["rate_of_change"].lower()


