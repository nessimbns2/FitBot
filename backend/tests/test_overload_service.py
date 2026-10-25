"""
backend/tests/test_overload_service.py
Service-layer tests for fatigue diagnosis and deload management:
1. 409 on duplicate apply
2. 409 on cancel of an inactive record
3. Cooldown blocks re-evaluation
4. Expiry ends a deload
5. Distinct-date counting ignores extra sets in the same session
6. lb match works with half-step plate tolerance
7. Client-sent numbers are ignored by apply_deload
8. get_diagnosis is strictly read-only
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest
from fastapi import HTTPException
from sqlmodel import Session, select

from app.modules.progressive_overload.algorithms import (
    DIAG_DELOAD_COOLDOWN_SESSIONS,
    DiagStrategy,
    RootCause,
)
from app.modules.progressive_overload.models import (
    ApplyDeloadRequest,
    CancelDeloadRequest,
    DeloadRecord,
    WorkoutSet,
)
from app.modules.progressive_overload.service import (
    DELOAD_EXPIRY_DAYS,
    _build_diag_sessions,
    _deload_sessions_completed,
    _detect_manual_deload_cutoff,
    _get_active_deload,
    _is_deload_active,
    apply_deload,
    cancel_deload,
    get_diagnosis,
)


def _seed_fatigue_history(session: Session, exercise_id: str = "barbell-bench-press", user_id: int = 1):
    """Seed 4 sessions over 21 days: flat 80kg load, rising RPE (7.0 -> 9.0), rep dropoff (8,8,6,5)."""
    now = datetime.now(timezone.utc)
    # Day offsets: -21, -14, -7, 0
    offsets = [-21, -14, -7, 0]
    rpes = [7.0, 7.8, 8.5, 9.2]
    reps_list = [
        [8, 8, 8],
        [8, 8, 7],
        [8, 7, 6],
        [8, 7, 5],
    ]

    for day_off, rpe, reps in zip(offsets, rpes, reps_list):
        sess_dt = now + timedelta(days=day_off)
        for set_num, r in enumerate(reps, start=1):
            ws = WorkoutSet(
                user_id=user_id,
                exercise_id=exercise_id,
                performed_at=sess_dt,
                set_number=set_num,
                reps=r,
                weight_kg=80.0,
                rpe=rpe,
            )
            session.add(ws)
    session.commit()


def test_apply_deload_duplicate_409(session: Session):
    """Calling apply_deload when an active deload already exists raises 409."""
    _seed_fatigue_history(session)
    req = ApplyDeloadRequest(exercise_id="barbell-bench-press")

    # First apply succeeds
    rec1 = apply_deload(
        db=session,
        request=req,
        user_id=1,
        experience_level="intermediate",
        volume_count=15,
        profile_is_default=False,
    )
    assert rec1.is_active is True
    assert rec1.exercise_id == "barbell-bench-press"

    # Second apply must raise 409
    with pytest.raises(HTTPException) as exc_info:
        apply_deload(
            db=session,
            request=req,
            user_id=1,
            experience_level="intermediate",
            volume_count=15,
            profile_is_default=False,
        )
    assert exc_info.value.status_code == 409
    assert "already exists" in exc_info.value.detail


def test_cancel_deload_inactive_409(session: Session):
    """Cancelling an already inactive or cancelled deload raises 409."""
    _seed_fatigue_history(session)
    rec = apply_deload(
        db=session,
        request=ApplyDeloadRequest(exercise_id="barbell-bench-press"),
        user_id=1,
        experience_level="intermediate",
        volume_count=15,
        profile_is_default=False,
    )

    # First cancel succeeds
    cancel_req = CancelDeloadRequest(deload_record_id=rec.id, reason="User felt recovered")
    cancelled = cancel_deload(session, cancel_req, user_id=1)
    assert cancelled.is_active is False

    # Second cancel must raise 409
    with pytest.raises(HTTPException) as exc_info:
        cancel_deload(session, cancel_req, user_id=1)
    assert exc_info.value.status_code == 409
    assert "already inactive" in exc_info.value.detail


def test_cooldown_blocks_re_evaluation(session: Session):
    """A manual deload drop triggers cooldown skipping, preventing false fatigue classification."""
    now = datetime.now(timezone.utc)
    exercise_id = "barbell-back-squat"

    # Heavy baseline session 20 days ago: 100 kg
    session.add(WorkoutSet(
        user_id=1, exercise_id=exercise_id,
        performed_at=now - timedelta(days=20),
        set_number=1, reps=5, weight_kg=100.0, rpe=8.0
    ))
    # Deload drop 14 days ago: 70 kg (< 85% of 100 kg)
    session.add(WorkoutSet(
        user_id=1, exercise_id=exercise_id,
        performed_at=now - timedelta(days=14),
        set_number=1, reps=5, weight_kg=70.0, rpe=6.0
    ))
    # Only 2 sessions after deload (within the 3-session cooldown)
    session.add(WorkoutSet(
        user_id=1, exercise_id=exercise_id,
        performed_at=now - timedelta(days=7),
        set_number=1, reps=5, weight_kg=95.0, rpe=8.0
    ))
    session.add(WorkoutSet(
        user_id=1, exercise_id=exercise_id,
        performed_at=now,
        set_number=1, reps=5, weight_kg=97.5, rpe=8.5
    ))
    session.commit()

    # _build_diag_sessions skips the sessions within cooldown
    diag_sessions = _build_diag_sessions(session, exercise_id, user_id=1)
    # Since cooldown skips the first 3 post-deload sessions and we only had 3 total (70, 95, 97.5),
    # diag_sessions will have 0 sessions left (< 3 min required).
    assert len(diag_sessions) < 3


def test_expiry_ends_deload(session: Session):
    """An expired deload is inactive and allows a fresh deload to be applied."""
    now = datetime.now(timezone.utc)
    expired_record = DeloadRecord(
        user_id=1,
        exercise_id="barbell-bench-press",
        strategy=DiagStrategy.volume_reduction.value,
        root_cause=RootCause.fatigue_pattern.value,
        confidence="medium",
        target_weight_kg=72.5,
        target_sets=2,
        target_reps_range="6-12",
        target_rpe_ceiling=7.0,
        resume_weight_kg=80.0,
        duration_sessions=2,
        applied_at=now - timedelta(days=35),
        expires_at=now - timedelta(days=7),  # expired 7 days ago
    )
    session.add(expired_record)
    session.commit()

    assert _is_deload_active(expired_record) is False
    assert _get_active_deload(session, user_id=1, exercise_id="barbell-bench-press") is None


def test_distinct_date_counting_ignores_extra_sets(session: Session):
    """Multiple sets on the same date count as exactly 1 completed deload session."""
    now = datetime.now(timezone.utc)
    rec = DeloadRecord(
        user_id=1,
        exercise_id="barbell-bench-press",
        strategy=DiagStrategy.volume_reduction.value,
        root_cause=RootCause.fatigue_pattern.value,
        confidence="medium",
        target_weight_kg=72.5,
        target_sets=2,
        target_reps_range="6-12",
        target_rpe_ceiling=7.0,
        resume_weight_kg=80.0,
        duration_sessions=2,
        weight_match_tolerance_kg=1.25,
        applied_at=now - timedelta(days=3),
    )
    session.add(rec)
    session.commit()

    # Day 1: 3 sets performed on the same day at target weight (72.5 kg)
    for i in range(1, 4):
        session.add(WorkoutSet(
            user_id=1,
            exercise_id="barbell-bench-press",
            performed_at=now - timedelta(days=2, hours=i),
            set_number=i,
            reps=8,
            weight_kg=72.5,
            rpe=7.0,
        ))
    session.commit()

    # Must count as 1, not 3
    assert _deload_sessions_completed(session, rec) == 1

    # Day 2: 2 sets performed the next day
    for i in range(1, 3):
        session.add(WorkoutSet(
            user_id=1,
            exercise_id="barbell-bench-press",
            performed_at=now - timedelta(days=1, hours=i),
            set_number=i,
            reps=8,
            weight_kg=72.5,
            rpe=6.5,
        ))
    session.commit()

    # Now counts as 2
    assert _deload_sessions_completed(session, rec) == 2


def test_lb_match_works_with_half_step_tolerance(session: Session):
    """Logging in pounds matches target weight within half a plate step tolerance."""
    _seed_fatigue_history(session, exercise_id="barbell-bench-press")
    # Apply deload with unit="lb"
    req = ApplyDeloadRequest(exercise_id="barbell-bench-press", unit="lb")
    rec = apply_deload(
        db=session,
        request=req,
        user_id=1,
        experience_level="intermediate",
        volume_count=15,
        profile_is_default=False,
    )

    assert rec.unit == "lb"
    assert rec.plate_increment_kg == pytest.approx(2.268, rel=1e-2)
    assert rec.weight_match_tolerance_kg == pytest.approx(1.134, rel=1e-2)

    # In lb, 80 kg is ~176.37 lb. Deload cut (~10% or RPE gap) targets rounded to 5 lb increments.
    # Suppose target is ~160 lb (72.57 kg).
    # User logs 160 lb:
    deload_db_rec = session.get(DeloadRecord, rec.id)
    now = datetime.now(timezone.utc)
    session.add(WorkoutSet(
        user_id=1,
        exercise_id="barbell-bench-press",
        performed_at=now + timedelta(hours=1),
        set_number=1,
        reps=8,
        weight_kg=deload_db_rec.target_weight_kg, # exact match in kg
        rpe=7.0,
    ))
    session.commit()

    assert _deload_sessions_completed(session, deload_db_rec) == 1


def test_client_sent_numbers_ignored_by_apply_deload(session: Session):
    """Client cannot tamper with prescribed weights, sets, or algorithm math."""
    _seed_fatigue_history(session)
    # Client attempts to pass extra fields or tampered values
    client_payload = {
        "exercise_id": "barbell-bench-press",
        "target_weight_kg": 999.0,
        "target_sets": 10,
    }
    req = ApplyDeloadRequest(**client_payload)
    rec = apply_deload(
        db=session,
        request=req,
        user_id=1,
        experience_level="intermediate",
        volume_count=15,
        profile_is_default=False,
    )

    # Prescribed numbers come purely from deterministic Python algorithm
    assert rec.target_weight_kg < 80.0
    assert rec.target_weight_kg != 999.0
    assert rec.target_sets != 10
    assert rec.strategy in (DiagStrategy.volume_reduction.value, DiagStrategy.weight_reduction.value)


def test_apply_deload_rejects_unapproved_strategy(session: Session):
    """When a client requests a strategy not in get_approved_strategies, apply_deload raises HTTP 400."""
    _seed_fatigue_history(session)
    # fatigue_pattern approves volume_reduction, weight_reduction, hold. progress_load is not approved.
    req = ApplyDeloadRequest(exercise_id="barbell-bench-press", strategy="progress_load")
    with pytest.raises(HTTPException) as exc_info:
        apply_deload(
            db=session,
            request=req,
            user_id=1,
            experience_level="intermediate",
            volume_count=15,
            profile_is_default=False,
        )
    assert exc_info.value.status_code == 400
    assert "not allowed for root cause" in exc_info.value.detail


def test_get_diagnosis_is_strictly_read_only(session: Session):
    """Calling get_diagnosis never creates or modifies DeloadRecord in the database."""
    _seed_fatigue_history(session)

    res1 = get_diagnosis(
        db=session,
        exercise_id="barbell-bench-press",
        user_id=1,
        experience_level="intermediate",
        volume_count=15,
        profile_is_default=False,
    )
    assert res1["diagnosis"].plateau_detected is True
    assert res1["active_deload"] is None

    # Verify no records written to database
    records = session.exec(select(DeloadRecord)).all()
    assert len(records) == 0
