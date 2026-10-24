"""
app/modules/progressive_overload/service.py
Service layer for workout set logging, history retrieval, progression recommendations, and volume.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlmodel import Session, col, desc, select

from app.modules.exercises.catalog import get_catalog
from app.modules.exercises.service import get_exercise
from app.modules.progressive_overload.algorithms import (
    Recommendation,
    detect_plateau,
    double_progression,
    get_default_increment,
    linear_progression,
    weekly_volume,
)
from app.modules.progressive_overload.models import (
    SessionGroup,
    UnitType,
    WorkoutSet,
    WorkoutSetCreate,
    WorkoutSetRead,
)

LB_TO_KG_FACTOR = 0.45359237


def _convert_weight_to_kg(weight: float, unit: UnitType) -> float:
    if unit == UnitType.LB:
        return round(weight * LB_TO_KG_FACTOR, 2)
    return round(weight, 2)


def log_set(session: Session, data: WorkoutSetCreate, user_id: int = 1) -> WorkoutSet:
    """Validate exercise and log a single workout set in kg."""
    exercise = get_exercise(data.exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exercise '{data.exercise_id}' not found in catalog",
        )

    weight_kg = _convert_weight_to_kg(data.weight, data.unit)
    performed_at = data.performed_at or datetime.now(timezone.utc)

    workout_set = WorkoutSet(
        user_id=user_id,
        exercise_id=data.exercise_id,
        performed_at=performed_at,
        session_label=data.session_label,
        set_number=data.set_number,
        reps=data.reps,
        weight_kg=weight_kg,
        rpe=data.rpe,
        rir=data.rir,
        notes=data.notes,
    )
    session.add(workout_set)
    session.commit()
    session.refresh(workout_set)
    return workout_set


def log_sets_bulk(session: Session, items: List[WorkoutSetCreate], user_id: int = 1) -> List[WorkoutSet]:
    """Validate and log multiple workout sets in a single transaction."""
    results: List[WorkoutSet] = []
    for item in items:
        exercise = get_exercise(item.exercise_id)
        if not exercise:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Exercise '{item.exercise_id}' not found in catalog",
            )
        weight_kg = _convert_weight_to_kg(item.weight, item.unit)
        performed_at = item.performed_at or datetime.now(timezone.utc)

        workout_set = WorkoutSet(
            user_id=user_id,
            exercise_id=item.exercise_id,
            performed_at=performed_at,
            session_label=item.session_label,
            set_number=item.set_number,
            reps=item.reps,
            weight_kg=weight_kg,
            rpe=item.rpe,
            rir=item.rir,
            notes=item.notes,
        )
        session.add(workout_set)
        results.append(workout_set)

    session.commit()
    for ws in results:
        session.refresh(ws)
    return results


def get_history(
    session: Session,
    exercise_id: str,
    user_id: int = 1,
    limit: int = 50,
    since: Optional[datetime] = None,
) -> List[SessionGroup]:
    """Get history for an exercise grouped by session date, newest first."""
    query = select(WorkoutSet).where(
        WorkoutSet.user_id == user_id,
        WorkoutSet.exercise_id == exercise_id,
    )
    if since:
        query = query.where(WorkoutSet.performed_at >= since)

    query = query.order_by(desc(WorkoutSet.performed_at), WorkoutSet.set_number).limit(limit)
    records = session.exec(query).all()

    # Group sets by session date
    grouped: Dict[str, List[WorkoutSetRead]] = {}
    labels: Dict[str, Optional[str]] = {}

    for ws in records:
        date_str = ws.performed_at.strftime("%Y-%m-%d")
        if date_str not in grouped:
            grouped[date_str] = []
            labels[date_str] = ws.session_label
        grouped[date_str].append(
            WorkoutSetRead(
                id=ws.id,
                user_id=ws.user_id,
                exercise_id=ws.exercise_id,
                performed_at=ws.performed_at,
                session_label=ws.session_label,
                set_number=ws.set_number,
                reps=ws.reps,
                weight_kg=ws.weight_kg,
                rpe=ws.rpe,
                rir=ws.rir,
                notes=ws.notes,
            )
        )

    return [
        SessionGroup(date=d, session_label=labels[d], sets=s_list)
        for d, s_list in grouped.items()
    ]


def get_recommendation(
    session: Session,
    exercise_id: str,
    algorithm: str = "double",
    user_id: int = 1,
) -> Recommendation:
    """Compute progressive overload recommendation for the next session."""
    exercise = get_exercise(exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exercise '{exercise_id}' not found in catalog",
        )

    history = get_history(session, exercise_id, user_id=user_id, limit=20)
    if not history:
        return Recommendation(
            weight_kg=20.0,
            rep_target="3x8",
            alternative=None,
            reason="No history yet for this exercise. Start with a manageable warm-up weight.",
            plateau_flag=False,
            deload_suggested=False,
        )

    last_session_sets = history[0].sets
    # Prepare session list for plateau detection: list of list of sets (newest first)
    sessions_sets = [group.sets for group in history]
    plateau_flag, deload_suggested = detect_plateau(sessions_sets, window=3)

    increment = get_default_increment(exercise)

    if algorithm.lower() == "linear":
        return linear_progression(
            last_session_sets=last_session_sets,
            weekly_increment_kg=increment,
            prescribed_reps=5,
            plateau_flag=plateau_flag,
            deload_suggested=deload_suggested,
        )
    else:
        rep_range = "6-12" if exercise.is_compound else "10-15"
        return double_progression(
            last_session_sets=last_session_sets,
            rep_range=rep_range,
            increment_kg=increment,
            plateau_flag=plateau_flag,
            deload_suggested=deload_suggested,
        )


def get_weekly_volume_summary(
    session: Session,
    week_start: Optional[date] = None,
    user_id: int = 1,
) -> Dict[str, Any]:
    """Calculate effective weekly sets per muscle group for the specified or current week (Monday start)."""
    if week_start is None:
        today = date.today()
        # Monday of current week
        week_start = today - timedelta(days=today.weekday())

    catalog = get_catalog()
    week_end = week_start + timedelta(days=7)

    query = select(WorkoutSet).where(
        WorkoutSet.user_id == user_id,
        WorkoutSet.performed_at >= datetime.combine(week_start, datetime.min.time(), tzinfo=timezone.utc),
        WorkoutSet.performed_at < datetime.combine(week_end, datetime.min.time(), tzinfo=timezone.utc),
    )
    sets = session.exec(query).all()

    volume_data = weekly_volume(sets, catalog, week_start)
    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "muscles": volume_data,
    }
