"""
app/modules/exercises/models.py
Saved training routine table (previously kept in the browser's localStorage).

NOTE: Do NOT add `from __future__ import annotations` to this file
(SQLModel 0.0.22 evaluates table annotations eagerly).
"""

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class SavedRoutine(SQLModel, table=True):
    """The routine a user is currently following (one per user)."""

    __tablename__ = "saved_routines"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True, index=True)
    split: str = Field(default="push_pull_legs", max_length=40)
    days_per_week: int = Field(default=4, ge=1, le=7)
    routine: Dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SavedRoutineWrite(SQLModel):
    split: str = Field(min_length=1, max_length=40)
    days_per_week: int = Field(ge=1, le=7)
    routine: Dict[str, Any]


class SavedRoutineRead(SQLModel):
    split: str
    days_per_week: int
    routine: Dict[str, Any]
    updated_at: datetime


class ExerciseRecommendation(SQLModel, table=True):
    """An actual displayed alternative and its optional explicit user feedback."""

    __tablename__ = "exercise_recommendations"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    source_exercise_id: str = Field(max_length=100)
    exercise_id: str = Field(max_length=100)
    similarity: float
    features: Dict[str, float] = Field(sa_column=Column(JSON, nullable=False))
    feedback: Optional[str] = Field(default=None, max_length=20)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    feedback_at: Optional[datetime] = None


class ExercisePreferenceModel(SQLModel, table=True):
    """Per-account logistic regression parameters, stored as JSON rather than pickle."""

    __tablename__ = "exercise_preference_models"

    user_id: int = Field(foreign_key="users.id", primary_key=True)
    parameters: Dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    metrics: Dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    trained_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
