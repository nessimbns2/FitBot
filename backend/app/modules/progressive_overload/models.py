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
