"""
app/modules/progressive_overload/models.py
SQLModel table for WorkoutSet and Pydantic schemas.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator
from sqlmodel import Field as SQLField, SQLModel


class UnitType(str, Enum):
    KG = "kg"
    LB = "lb"


class WorkoutSet(SQLModel, table=True):
    """Logs individual performed sets for progressive overload tracking."""

    __tablename__ = "workout_sets"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    user_id: int = SQLField(foreign_key="users.id", index=True)
    exercise_id: str = SQLField(index=True)
    performed_at: datetime = SQLField(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )
    session_label: Optional[str] = SQLField(default=None)
    set_number: int = SQLField(default=1)
    reps: int = SQLField(ge=1, le=100)
    weight_kg: float = SQLField(ge=0.0, le=500.0)
    rpe: Optional[float] = SQLField(default=None)
    rir: Optional[int] = SQLField(default=None)
    notes: Optional[str] = SQLField(default=None)


class WorkoutSetCreate(BaseModel):
    exercise_id: str
    performed_at: Optional[datetime] = None
    session_label: Optional[str] = None
    set_number: int = Field(default=1, ge=1)
    reps: int = Field(ge=1, le=100)
    weight: float = Field(ge=0.0, le=1100.0)
    unit: UnitType = Field(default=UnitType.KG)
    rpe: Optional[float] = Field(None, ge=1.0, le=10.0)
    rir: Optional[int] = Field(None, ge=0, le=5)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_and_reconcile_rpe_rir(self) -> "WorkoutSetCreate":
        rpe = self.rpe
        rir = self.rir

        if rpe is not None and rir is not None:
            # Check for conflict: abs((10 - rir) - rpe) > 1
            expected_rpe = 10.0 - float(rir)
            if abs(expected_rpe - rpe) > 1.0:
                raise ValueError(
                    f"RPE ({rpe}) and RIR ({rir}) conflict by more than 1 point (expected ~{expected_rpe})"
                )
        elif rir is not None and rpe is None:
            self.rpe = float(10 - rir)
        elif rpe is not None and rir is None:
            self.rir = max(0, min(5, round(10.0 - rpe)))

        return self


class WorkoutSetRead(BaseModel):
    id: int
    user_id: int
    exercise_id: str
    performed_at: datetime
    session_label: Optional[str]
    set_number: int
    reps: int
    weight_kg: float
    rpe: Optional[float]
    rir: Optional[int]
    notes: Optional[str]


class SessionGroup(BaseModel):
    date: str
    session_label: Optional[str]
    sets: List[WorkoutSetRead]


# ── Deload Record ──────────────────────────────────────────────────────────────

class DeloadRecord(SQLModel, table=True):
    """One active or historical deload prescription for a user + exercise pair.

    Design decisions (v1.1):
    - sessions_completed is NOT stored; it is derived at query time by counting
      distinct-date WorkoutSet rows where weight_kg ≈ target_weight_kg (±plate tol).
      This avoids dual-write bugs and keeps the source of truth in workout_sets.
    - resume_weight_kg IS stored at apply time so it survives any future weight
      changes to workout_sets.
    - cancelled_at + cancel_reason support the /cancel-deload endpoint.
    - expires_at lets the service expire a deload that was never logged
      (e.g. user ignores the prescription for >4 weeks).
    - profile_is_default is a first-class column so the service can pass it
      directly to diagnose_fatigue without inferring from user settings each call.
    """

    __tablename__ = "deload_records"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    user_id: int = SQLField(foreign_key="users.id", index=True)
    exercise_id: str = SQLField(index=True)

    # Prescription values (set at apply time, server-side)
    strategy: str = SQLField()                        # DiagStrategy.value
    root_cause: str = SQLField()                      # RootCause.value
    confidence: str = SQLField()                      # DiagConfidence.value
    target_weight_kg: float = SQLField(ge=0.0)
    target_sets: int = SQLField(ge=1)
    target_reps_range: str = SQLField()
    target_rpe_ceiling: float = SQLField(ge=0.0, le=10.0)
    resume_weight_kg: float = SQLField(ge=0.0)        # pre-deload weight
    duration_sessions: int = SQLField(ge=1)
    constants_version: str = SQLField(default="v1.1") # algorithms.CONSTANTS_VERSION at apply time

    # Plate-increment and matching tolerance (half a plate step)
    unit: str = SQLField(default="kg")
    plate_increment_kg: float = SQLField(default=2.5)
    weight_match_tolerance_kg: float = SQLField(default=1.25)

    # Profile flag passed to diagnose_fatigue
    profile_is_default: bool = SQLField(default=False)

    # Lifecycle timestamps
    applied_at: datetime = SQLField(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )
    expires_at: Optional[datetime] = SQLField(default=None)  # service sets 28d from applied_at
    cancelled_at: Optional[datetime] = SQLField(default=None)
    cancel_reason: Optional[str] = SQLField(default=None)
    completed_at: Optional[datetime] = SQLField(default=None)

    # Feedback loop (v1.2): athlete rating after deload is complete
    # "positive" = recovered / felt better, "negative" = still struggling, None = not yet rated
    feedback: Optional[str] = SQLField(default=None)


class DeloadRecordCreate(BaseModel):
    """Internal schema — populated server-side from diagnose_fatigue output.
    The client only calls POST /apply-deload with an exercise_id;
    all prescription values are recomputed server-side.
    """
    exercise_id: str
    strategy: str
    root_cause: str
    confidence: str
    target_weight_kg: float
    target_sets: int
    target_reps_range: str
    target_rpe_ceiling: float
    resume_weight_kg: float
    duration_sessions: int
    unit: str = "kg"
    plate_increment_kg: float = 2.5
    weight_match_tolerance_kg: float = 1.25
    profile_is_default: bool = False


class DeloadRecordRead(BaseModel):
    """Public response schema for /diagnosis and /apply-deload."""
    id: int
    exercise_id: str
    strategy: str
    root_cause: str
    confidence: str
    target_weight_kg: float
    target_sets: int
    target_reps_range: str
    target_rpe_ceiling: float
    resume_weight_kg: float
    duration_sessions: int
    sessions_completed: int     # derived at read time, NOT stored
    is_active: bool             # True when not cancelled, not completed, not expired
    applied_at: datetime
    expires_at: Optional[datetime]
    constants_version: str
    unit: str = "kg"
    plate_increment_kg: float = 2.5
    weight_match_tolerance_kg: float = 1.25
    feedback: Optional[str] = None  # "positive" | "negative" | None


class DiagnosisRequest(BaseModel):
    """POST /diagnosis body."""
    exercise_id: str
    unit: Optional[str] = None
    experience_level: Optional[str] = None
    volume_count: Optional[int] = None


class ApplyDeloadRequest(BaseModel):
    """POST /apply-deload body — exercise_id and optional bounded strategy choice.
    All numeric prescription values are recomputed server-side from current history.
    """
    model_config = {"extra": "ignore"}

    exercise_id: str
    unit: Optional[str] = None
    strategy: Optional[str] = None


class CancelDeloadRequest(BaseModel):
    """POST /cancel-deload body."""
    deload_record_id: int
    reason: Optional[str] = None


class DeloadFeedbackRequest(BaseModel):
    """POST /deload-feedback body."""
    deload_record_id: int
    feedback: str  # "positive" or "negative"

    @property
    def is_valid(self) -> bool:
        return self.feedback in ("positive", "negative")


class StrategyOutcome(BaseModel):
    """Aggregated success rate for a (root_cause, strategy) pair."""
    root_cause: str
    strategy: str
    total_rated: int
    positive_count: int
    negative_count: int
    success_rate: float   # positive / total_rated, -1.0 if no data
