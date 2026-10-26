"""
app/modules/progressive_overload/router.py
HTTP endpoints for workout set logging, history, progression recommendations, and volume.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Dict, List, Optional, Union
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlmodel import Session

from app.core.database import get_session
from app.modules.auth.dependencies import CurrentUser
from app.modules.progressive_overload.algorithms import Recommendation
from app.modules.progressive_overload.models import (
    SessionGroup,
    WorkoutSetCreate,
    WorkoutSetRead,
)
from app.modules.progressive_overload.service import (
    get_history,
    get_recommendation,
    get_weekly_volume_summary,
    log_set,
    log_sets_bulk,
)

router = APIRouter(
    prefix="/api/overload",
    tags=["progressive_overload"],
)


class RecommendationResponse(BaseModel):
    weight_kg: float
    rep_target: str
    alternative: Optional[str]
    reason: str
    plateau_flag: bool
    deload_suggested: bool


@router.post(
    "/log-set",
    response_model=Union[WorkoutSetRead, List[WorkoutSetRead]],
    status_code=status.HTTP_201_CREATED,
    summary="Log one workout set or bulk sets",
)
def create_set_or_sets(
    payload: Union[WorkoutSetCreate, List[WorkoutSetCreate]],
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
) -> Union[WorkoutSetRead, List[WorkoutSetRead]]:
    """Log one set or a list of sets for a workout session with automatic unit conversion and RPE/RIR derivation."""
    if isinstance(payload, list):
        sets = log_sets_bulk(session, payload, user_id=user.id)
        return [
            WorkoutSetRead(
                id=s.id,
                user_id=s.user_id,
                exercise_id=s.exercise_id,
                performed_at=s.performed_at,
                session_label=s.session_label,
                set_number=s.set_number,
                reps=s.reps,
                weight_kg=s.weight_kg,
                rpe=s.rpe,
                rir=s.rir,
                notes=s.notes,
            )
            for s in sets
        ]
    else:
        s = log_set(session, payload, user_id=user.id)
        return WorkoutSetRead(
            id=s.id,
            user_id=s.user_id,
            exercise_id=s.exercise_id,
            performed_at=s.performed_at,
            session_label=s.session_label,
            set_number=s.set_number,
            reps=s.reps,
            weight_kg=s.weight_kg,
            rpe=s.rpe,
            rir=s.rir,
            notes=s.notes,
        )


@router.get(
    "/history/{exercise_id}",
    response_model=List[SessionGroup],
    summary="Get workout set history grouped by session date",
)
def get_exercise_history(
    exercise_id: str,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
    limit: int = Query(50, ge=1, le=200),
    since: Optional[datetime] = Query(None),
) -> List[SessionGroup]:
    """Retrieve logged sets for an exercise grouped by date (newest first)."""
    return get_history(session, exercise_id=exercise_id, user_id=user.id, limit=limit, since=since)


@router.get(
    "/recommendation/{exercise_id}",
    response_model=RecommendationResponse,
    summary="Get next session progressive overload recommendation",
)
def get_next_recommendation(
    exercise_id: str,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
    algorithm: str = Query("double", pattern="^(double|linear)$"),
) -> RecommendationResponse:
    """Calculate next workout target (weight, reps, alternative) based on logged history and exercise type."""
    rec = get_recommendation(session, exercise_id=exercise_id, algorithm=algorithm, user_id=user.id)
    return RecommendationResponse(
        weight_kg=rec.weight_kg,
        rep_target=rec.rep_target,
        alternative=rec.alternative,
        reason=rec.reason,
        plateau_flag=rec.plateau_flag,
        deload_suggested=rec.deload_suggested,
    )


@router.get(
    "/volume",
    response_model=Dict[str, Any],
    summary="Get effective weekly volume per muscle group",
)
def get_volume(
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
    week_start: Optional[date] = Query(None, description="Start date of the week (YYYY-MM-DD, defaults to Monday)"),
) -> Dict[str, Any]:
    """Calculate effective weekly sets (RPE >= 6.0) per muscle group with in_range status."""
    return get_weekly_volume_summary(session, week_start=week_start, user_id=user.id)
