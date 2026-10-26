"""
backend/tests/test_overload_router.py
HTTP API endpoint tests for plateau diagnosis and deload management:
1. POST /api/overload/diagnosis never writes to the database
2. POST /api/overload/apply-deload ignores client-sent numbers
3. POST /api/overload/cancel-deload returns 409 on inactive deload
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.modules.progressive_overload.models import DeloadRecord, WorkoutSet


def _seed_fatigue(session: Session, exercise_id: str = "barbell-bench-press"):
    now = datetime.now(timezone.utc)
    offsets = [-21, -14, -7, 0]
    rpes = [7.0, 7.8, 8.5, 9.2]
    reps_list = [[8, 8, 8], [8, 8, 7], [8, 7, 6], [8, 7, 5]]

    for day_off, rpe, reps in zip(offsets, rpes, reps_list):
        sess_dt = now + timedelta(days=day_off)
        for set_num, r in enumerate(reps, start=1):
            session.add(WorkoutSet(
                user_id=1,
                exercise_id=exercise_id,
                performed_at=sess_dt,
                set_number=set_num,
                reps=r,
                weight_kg=80.0,
                rpe=rpe,
            ))
    session.commit()


def test_router_diagnosis_never_writes_to_db(client: TestClient, session: Session):
    """POST /api/overload/diagnosis is strictly read-only and never creates database rows."""
    _seed_fatigue(session)

    res = client.post("/api/overload/diagnosis", json={"exercise_id": "barbell-bench-press"})
    assert res.status_code == 200
    data = res.json()

    assert "diagnosis" in data
    assert "explanation" in data
    assert "approved_strategies" in data
    assert data["diagnosis"]["plateau_detected"] is True

    # Prove database is untouched
    records = session.exec(select(DeloadRecord)).all()
    assert len(records) == 0


def test_router_apply_deload_ignores_client_numbers(client: TestClient, session: Session):
    """POST /api/overload/apply-deload recomputes all numbers server-side; client numbers are ignored."""
    _seed_fatigue(session)

    tampered_payload = {
        "exercise_id": "barbell-bench-press",
        "target_weight_kg": 999.0,
        "target_sets": 100,
    }
    res = client.post("/api/overload/apply-deload", json=tampered_payload)
    assert res.status_code == 201
    data = res.json()

    # The persisted deload has deterministic numbers from Python
    assert data["target_weight_kg"] < 80.0
    assert data["target_weight_kg"] != 999.0
    assert data["target_sets"] != 100
    assert data["is_active"] is True

    # Deload record in DB also reflects server-calculated values
    db_rec = session.get(DeloadRecord, data["id"])
    assert db_rec is not None
    assert db_rec.target_weight_kg < 80.0


def test_router_apply_deload_rejects_unapproved_strategy(client: TestClient, session: Session):
    """POST /api/overload/apply-deload rejects any strategy not in approved set with 400."""
    _seed_fatigue(session)

    res = client.post(
        "/api/overload/apply-deload",
        json={"exercise_id": "barbell-bench-press", "strategy": "progress_load"},
    )
    assert res.status_code == 400
    assert "not allowed for root cause" in res.json()["detail"]


def test_router_cancel_deload_409_on_inactive(client: TestClient, session: Session):
    """POST /api/overload/cancel-deload marks record cancelled, and subsequent cancel returns 409."""
    _seed_fatigue(session)

    # 1. Apply deload
    apply_res = client.post("/api/overload/apply-deload", json={"exercise_id": "barbell-bench-press"})
    assert apply_res.status_code == 201
    rec_id = apply_res.json()["id"]

    # 2. Cancel deload -> 200 OK
    cancel_res1 = client.post(
        "/api/overload/cancel-deload",
        json={"deload_record_id": rec_id, "reason": "Feeling recovered"},
    )
    assert cancel_res1.status_code == 200
    assert cancel_res1.json()["is_active"] is False

    # 3. Second cancel -> 409 Conflict
    cancel_res2 = client.post(
        "/api/overload/cancel-deload",
        json={"deload_record_id": rec_id, "reason": "Already cancelled"},
    )
    assert cancel_res2.status_code == 409
    assert "already inactive" in cancel_res2.json()["detail"]


def test_router_apply_deload_duplicate_returns_409(client: TestClient, session: Session):
    """POST /api/overload/apply-deload returns 409 when an active deload already exists."""
    _seed_fatigue(session)

    res1 = client.post("/api/overload/apply-deload", json={"exercise_id": "barbell-bench-press"})
    assert res1.status_code == 201

    # Second apply while first is active -> 409 Conflict
    res2 = client.post("/api/overload/apply-deload", json={"exercise_id": "barbell-bench-press"})
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]
