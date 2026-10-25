"""
app/modules/user/models.py
SQLModel tables and enums for User & Profile, Chat Sessions, and Messages.
Compatible with SQLModel 0.0.22 + SQLAlchemy 2.0 + Python 3.13.

NOTE: Do NOT add `from __future__ import annotations` to this file.
SQLModel 0.0.22 evaluates relationship annotations eagerly, so PEP 563
postponed evaluation breaks relationship resolution.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlmodel import Field, Relationship, SQLModel


# ── Enums ─────────────────────────────────────────────────────────────────────


class Sex(str, Enum):
    male = "male"
    female = "female"


class ExperienceLevel(str, Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"


class Somatotype(str, Enum):
    ectomorph = "ectomorph"
    mesomorph = "mesomorph"
    endomorph = "endomorph"
    unknown = "unknown"


class Goal(str, Enum):
    hypertrophy = "hypertrophy"
    fat_loss = "fat_loss"
    strength = "strength"
    athletic_performance = "athletic_performance"


class ActivityLevel(str, Enum):
    sedentary = "sedentary"
    light = "light"
    moderate = "moderate"
    very_active = "very_active"
    extreme = "extreme"


class UnitSystem(str, Enum):
    metric = "metric"
    imperial = "imperial"


# ── UserProfile ───────────────────────────────────────────────────────────────


class UserProfile(SQLModel, table=True):
    """A single local user profile (id=1, created on first read)."""

    __tablename__ = "user_profile"

    id: Optional[int] = Field(default=None, primary_key=True)
    age: int = Field(default=25, ge=14, le=100)
    sex: Sex = Field(default=Sex.male)
    height_cm: float = Field(default=175.0, ge=120.0, le=230.0)
    weight_kg: float = Field(default=75.0, ge=30.0, le=300.0)
    body_fat_pct: Optional[float] = Field(default=None, ge=3.0, le=60.0)
    experience_level: ExperienceLevel = Field(default=ExperienceLevel.beginner)
    somatotype: Somatotype = Field(default=Somatotype.unknown)
    goal: Goal = Field(default=Goal.hypertrophy)
    activity_level: ActivityLevel = Field(default=ActivityLevel.moderate)
    unit_system: UnitSystem = Field(default=UnitSystem.metric)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    sessions: List["ChatSession"] = Relationship(back_populates="user")


# ── ChatSession ───────────────────────────────────────────────────────────────


class ChatSession(SQLModel, table=True):
    """A named chat conversation belonging to the local user."""

    __tablename__ = "chat_session"

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
    )
    user_id: int = Field(foreign_key="user_profile.id")
    title: str = Field(default="New conversation")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    user: Optional["UserProfile"] = Relationship(back_populates="sessions")
    messages: List["ChatMessage"] = Relationship(back_populates="session")


# ── ChatMessage ───────────────────────────────────────────────────────────────


class ChatMessage(SQLModel, table=True):
    """A single message within a chat session."""

    __tablename__ = "chat_message"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="chat_session.id")
    role: str = Field(default="user")  # "user" | "assistant"
    content: str = Field(default="")
    sources: Optional[str] = Field(default=None)  # JSON-encoded list
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    session: Optional["ChatSession"] = Relationship(back_populates="messages")


# ── Pydantic request/response schemas ─────────────────────────────────────────


class UserProfileUpdate(SQLModel):
    """Partial update schema — all fields optional."""

    age: Optional[int] = Field(default=None, ge=14, le=100)
    sex: Optional[Sex] = None
    height_cm: Optional[float] = Field(default=None, ge=120.0, le=230.0)
    weight_kg: Optional[float] = Field(default=None, ge=30.0, le=300.0)
    body_fat_pct: Optional[float] = Field(default=None, ge=3.0, le=60.0)
    experience_level: Optional[ExperienceLevel] = None
    somatotype: Optional[Somatotype] = None
    goal: Optional[Goal] = None
    activity_level: Optional[ActivityLevel] = None
    unit_system: Optional[UnitSystem] = None


class SessionSummary(SQLModel):
    """Session list item — id, title, timestamps."""

    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class MessageRead(SQLModel):
    """Public representation of a chat message."""

    id: Optional[int] = None
    session_id: str
    role: str
    content: str
    sources: Optional[str] = None
    created_at: datetime


# ── Somatotype Quiz Schemas ───────────────────────────────────────────────────

class SomatotypeQuestionOption(SQLModel):
    value: str
    label: str
    detail: str
    archetype: Somatotype


class SomatotypeQuestion(SQLModel):
    id: str
    title: str
    question: str
    options: List[SomatotypeQuestionOption]


class SomatotypeQuizRequest(SQLModel):
    wrist_structure: str = Field(description="Answer value for wrist structure question")
    body_frame: str = Field(description="Answer value for body frame question")
    weight_tendency: str = Field(description="Answer value for weight tendency question")
    muscle_definition: str = Field(description="Answer value for muscle definition question")
    carb_response: str = Field(description="Answer value for carb response question")
    auto_apply: bool = Field(default=False, description="Automatically update user profile with predicted somatotype")


class SomatotypeQuizResponse(SQLModel):
    predicted_somatotype: Somatotype
    confidence: str
    secondary_traits: Optional[str] = None
    traits_summary: str
    training_focus: str
    nutrition_focus: str
    macro_shift_note: str
    profile_updated: bool = False


# ── Athlete Blueprint & Profile Audit Schemas ────────────────────────────────

class VolumeLandmarks(SQLModel):
    mev_sets_per_week: str = Field(description="Minimum Effective Volume (sets/muscle group/week)")
    mrv_sets_per_week: str = Field(description="Maximum Recoverable Volume (sets/muscle group/week)")
    recommended_frequency: str = Field(description="Optimal training frequency per muscle group")
    recovery_capacity: str = Field(description="High | Moderate | Sensitive")


class TimelineProjection(SQLModel):
    rate_of_change: str = Field(description="Projected monthly change rate")
    milestone_12_weeks: str = Field(description="Expected 12-week adaptation")
    milestone_24_weeks: str = Field(description="Expected 24-week transformation")


class AthleteBlueprintRequest(SQLModel):
    age: Optional[int] = Field(default=None, ge=14, le=100)
    sex: Optional[Sex] = None
    height_cm: Optional[float] = Field(default=None, ge=120.0, le=230.0)
    weight_kg: Optional[float] = Field(default=None, ge=30.0, le=300.0)
    body_fat_pct: Optional[float] = Field(default=None, ge=3.0, le=60.0)
    somatotype: Optional[Somatotype] = None
    experience_level: Optional[ExperienceLevel] = None
    goal: Optional[Goal] = None
    activity_level: Optional[ActivityLevel] = None


class AthleteBlueprintResponse(SQLModel):
    athlete_archetype: str
    executive_summary: str
    physiological_strengths: List[str]
    blindspots_and_risks: List[str]
    volume_landmarks: VolumeLandmarks
    timeline_projection: TimelineProjection
    key_coaching_directives: List[str]
    calculated_metrics: Dict[str, Any] = Field(default_factory=dict)
    sources: List[Dict[str, Any]] = Field(default_factory=list)


