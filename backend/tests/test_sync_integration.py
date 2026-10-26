"""Regression checks for merging upstream features with authenticated accounts."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import select

from app.modules.nutrition.models import FoodLogEntry
from app.modules.progressive_overload.models import DeloadRecord
from app.modules.rag_core.engine import FakeLLMClient, GeminiLLMClient
from app.modules.user.models import UserProfile


@pytest.fixture
def accounts(anon_client):
    headers = []
    ids = []
    for name in ("alice", "bob"):
        response = anon_client.post("/api/auth/register", json={
            "full_name": name.title(), "email": f"{name}@example.com", "password": "Merge-test-123",
        })
        assert response.status_code == 201
        ids.append(response.json()["user"]["id"])
        headers.append({"Authorization": "Bearer " + response.json()["access_token"]})
    return headers[0], headers[1], ids


@pytest.mark.parametrize("method,path", [
    ("get", "/api/nutrition/log"),
    ("get", "/api/nutrition/log/summary"),
    ("post", "/api/nutrition/suggest-meal"),
    ("post", "/api/user/blueprint"),
    ("post", "/api/overload/diagnosis"),
    ("post", "/api/overload/apply-deload"),
    ("post", "/api/overload/cancel-deload"),
])
def test_new_upstream_endpoints_require_login(anon_client, method, path):
    assert getattr(anon_client, method)(path).status_code == 401


def test_food_diary_crud_and_summary_are_per_account(anon_client, accounts):
    a, b, ids = accounts
    created = anon_client.post("/api/nutrition/log", headers=a, json={
        "name": "Lunch", "calories": 640, "protein_g": 40, "user_id": ids[1],
    })
    assert created.status_code == 201
    entry_id = created.json()["id"]
    assert len(anon_client.get("/api/nutrition/log", headers=a).json()) == 1
    assert anon_client.get("/api/nutrition/log", headers=b).json() == []
    assert anon_client.get("/api/nutrition/log/summary", headers=a).json()["consumed"]["calories"] == 640
    assert anon_client.get("/api/nutrition/log/summary", headers=b).json()["consumed"]["calories"] == 0
    assert anon_client.get(f"/api/nutrition/log/{entry_id}", headers=b).status_code == 404
    assert anon_client.put(f"/api/nutrition/log/{entry_id}", headers=b, json={"calories": 1}).status_code == 404
    assert anon_client.delete(f"/api/nutrition/log/{entry_id}", headers=b).status_code == 404
    assert anon_client.put(f"/api/nutrition/log/{entry_id}", headers=a, json={"calories": 700}).json()["calories"] == 700
    assert anon_client.delete(f"/api/nutrition/log/{entry_id}", headers=a).status_code == 204


def test_blueprint_uses_owner_profile_when_profile_id_differs(anon_client, accounts, session, monkeypatch):
    from app.modules.user import service

    a, b, ids = accounts
    monkeypatch.setattr(service, "get_llm_client", lambda: FakeLLMClient("{}"))
    profile = session.exec(select(UserProfile).where(UserProfile.user_id == ids[0])).one()
    profile.id = 100
    session.add(profile)
    session.commit()
    anon_client.put("/api/user/profile", headers=a, json={"weight_kg": 95, "goal": "strength"})
    anon_client.put("/api/user/profile", headers=b, json={"weight_kg": 50, "goal": "fat_loss"})
    first = anon_client.post("/api/user/blueprint", headers=a, json={})
    second = anon_client.post("/api/user/blueprint", headers=b, json={})
    assert first.status_code == second.status_code == 200
    assert first.json()["calculated_metrics"]["goal"] == "strength"
    assert second.json()["calculated_metrics"]["goal"] == "fat_loss"
    assert first.json()["calculated_metrics"]["protein_g"] > second.json()["calculated_metrics"]["protein_g"]


def test_deload_ownership_and_account_deletion(anon_client, accounts, session, monkeypatch):
    from app.modules.progressive_overload import service

    a, b, ids = accounts
    monkeypatch.setattr(service, "generate_diagnosis_explanation", lambda result, **kw: (
        service.render_fallback(result), result.deload_target.strategy, [],
    ))
    # The profile primary key is deliberately different from its owner's account ID.
    profile = session.exec(select(UserProfile).where(UserProfile.user_id == ids[0])).one()
    profile.id = 100
    profile.unit_system = "imperial"
    session.add(profile)
    session.commit()
    now = datetime.now(timezone.utc)
    for week, rpe in enumerate((7, 7.8, 8.5, 9.2)):
        for number, reps in enumerate((8, 7, 5), 1):
            response = anon_client.post("/api/overload/log-set", headers=a, json={
                "exercise_id": "barbell-bench-press", "weight": 80, "unit": "kg",
                "reps": reps, "set_number": number, "rpe": rpe,
                "performed_at": (now - timedelta(days=21 - week * 7)).isoformat(),
            })
            assert response.status_code == 201
    response = anon_client.post("/api/overload/apply-deload", headers=a, json={"exercise_id": "barbell-bench-press"})
    assert response.status_code == 201, response.text
    assert response.json()["unit"] == "lb"
    record_id = response.json()["id"]
    assert anon_client.post("/api/overload/cancel-deload", headers=b, json={"deload_record_id": record_id}).status_code == 404
    diagnosis = anon_client.post("/api/overload/diagnosis", headers=b, json={"exercise_id": "barbell-bench-press"})
    assert diagnosis.status_code == 200
    assert diagnosis.json()["active_deload"] is None
    anon_client.post("/api/nutrition/log", headers=a, json={"name": "Rice", "calories": 200})
    assert anon_client.request("DELETE", "/api/auth/me", headers=a, json={"password": "Merge-test-123"}).status_code == 204
    assert session.exec(select(DeloadRecord).where(DeloadRecord.user_id == ids[0])).all() == []
    assert session.exec(select(FoodLogEntry).where(FoodLogEntry.user_id == ids[0])).all() == []


def test_plateau_temperature_is_forwarded_without_losing_timeout(monkeypatch):
    captured = {}

    class Model:
        def generate_content(self, prompt, **kwargs):
            captured.update(kwargs)
            return type("Response", (), {"text": "Safe explanation"})()

    client = GeminiLLMClient(api_key="test-key")
    monkeypatch.setattr(client, "_get_client", lambda model=None: Model())
    assert client.complete([], "system", temperature=0.3) == "Safe explanation"
    assert captured["generation_config"]["temperature"] == 0.3
    assert 0 < captured["request_options"]["timeout"] <= client.timeout


def test_migration_preserves_existing_meals_and_ownership():
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, text
    from app.modules.auth.models import User
    from app.modules.nutrition.models import MealLog

    path = Path(__file__).resolve().parents[1] / "alembic/versions/e3c2b8d5f0a1_integrate_food_log_and_deload.py"
    spec = importlib.util.spec_from_file_location("food_log_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        User.__table__.create(connection)
        MealLog.__table__.create(connection)
        connection.execute(User.__table__.insert().values(id=42, email="owner@example.com", full_name="Owner", password_hash="test"))
        connection.execute(MealLog.__table__.insert().values(
            user_id=42, slot="Post-Workout", meal_name="Rice & chicken", calories=640,
            protein_g=40, carbs_g=70, fat_g=20, food_items=[{"name": "Chicken"}],
        ))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        row = connection.execute(text("SELECT * FROM food_log_entries")).mappings().one()
        assert row["user_id"] == 42
        assert row["meal_slot"] == "post_workout"
        assert row["name"] == "Rice & chicken"
        assert row["notes"] == "Chicken"
        assert row["calories"] == 640
        assert connection.execute(text("SELECT count(*) FROM meal_logs")).scalar() == 1
    engine.dispose()
