"""
app/modules/nutrition/models.py
SQLModel table and Pydantic schemas for the food log (daily meal diary).
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel


# ── Enums ─────────────────────────────────────────────────────────────────────


class MealSlotName(str, Enum):
    breakfast = "breakfast"
    lunch = "lunch"
    dinner = "dinner"
    post_workout = "post_workout"
    snack = "snack"


class LogSource(str, Enum):
    """How the entry was created."""

    manual = "manual"            # typed in by the user
    photo_scan = "photo_scan"    # estimated by the AI meal scanner, confirmed by the user
    ai_text = "ai_text"          # estimated by AI from a text description
    ai_suggestion = "ai_suggestion"  # a meal suggested by the AI, confirmed by the user


# ── Table ─────────────────────────────────────────────────────────────────────


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FoodLogEntry(SQLModel, table=True):
    """One food or meal the user ate on a given day."""

    __tablename__ = "food_log_entries"

    id: Optional[int] = SQLField(default=None, primary_key=True)
    user_id: int = SQLField(default=1, index=True)
    log_date: date_type = SQLField(index=True)
    meal_slot: MealSlotName = SQLField(default=MealSlotName.snack)
    name: str
    calories: float = SQLField(ge=0.0)
    protein_g: float = SQLField(default=0.0, ge=0.0)
    carbs_g: float = SQLField(default=0.0, ge=0.0)
    fat_g: float = SQLField(default=0.0, ge=0.0)
    source: LogSource = SQLField(default=LogSource.manual)
    notes: Optional[str] = SQLField(default=None)
    created_at: datetime = SQLField(default_factory=_utcnow)
    updated_at: datetime = SQLField(default_factory=_utcnow)


# ── Schemas ───────────────────────────────────────────────────────────────────

MAX_CALORIES = 5000.0   # per single entry; guards against typos like 50000
MAX_MACRO_G = 500.0


def _clean_name(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("name must not be blank")
    return cleaned


class FoodLogCreate(BaseModel):
    """Body of POST /api/nutrition/log."""

    log_date: Optional[date_type] = None  # defaults to today (server side)
    meal_slot: MealSlotName = MealSlotName.snack
    name: str = Field(min_length=1, max_length=120)
    calories: float = Field(ge=0.0, le=MAX_CALORIES)
    protein_g: float = Field(default=0.0, ge=0.0, le=MAX_MACRO_G)
    carbs_g: float = Field(default=0.0, ge=0.0, le=MAX_MACRO_G)
    fat_g: float = Field(default=0.0, ge=0.0, le=MAX_MACRO_G)
    source: LogSource = LogSource.manual
    notes: Optional[str] = Field(default=None, max_length=500)

    _strip_name = field_validator("name")(_clean_name)


class FoodLogUpdate(BaseModel):
    """Body of PUT /api/nutrition/log/{id}. Only the fields sent are changed."""

    log_date: Optional[date_type] = None
    meal_slot: Optional[MealSlotName] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    calories: Optional[float] = Field(default=None, ge=0.0, le=MAX_CALORIES)
    protein_g: Optional[float] = Field(default=None, ge=0.0, le=MAX_MACRO_G)
    carbs_g: Optional[float] = Field(default=None, ge=0.0, le=MAX_MACRO_G)
    fat_g: Optional[float] = Field(default=None, ge=0.0, le=MAX_MACRO_G)
    source: Optional[LogSource] = None
    notes: Optional[str] = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: Optional[str]) -> Optional[str]:
        return None if value is None else _clean_name(value)


class FoodLogRead(BaseModel):
    """What the API returns for one entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    log_date: date_type
    meal_slot: MealSlotName
    name: str
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    source: LogSource
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ── Daily summary schemas ─────────────────────────────────────────────────────


class MacroTotals(BaseModel):
    """Calories and macros, used for consumed, target and remaining amounts."""

    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float


class MacroPercent(BaseModel):
    """Share of the daily target reached. Above 100 means over target.
    None when the target for that value is zero."""

    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None


class DailySummary(BaseModel):
    """What was eaten on one day compared with the day's targets."""

    log_date: date_type
    entry_count: int
    consumed: MacroTotals
    targets: MacroTotals
    remaining: MacroTotals  # target - consumed; negative means over target
    percent_of_target: MacroPercent
    floor_applied: bool = False
    warnings: list[str] = Field(default_factory=list)


# ── Meal suggestion schemas ───────────────────────────────────────────────────


class SuggestMealRequest(BaseModel):
    """Body of POST /api/nutrition/suggest-meal."""

    log_date: Optional[date_type] = None  # defaults to today
    meal_slot: Optional[MealSlotName] = None
    preferences: Optional[str] = Field(default=None, max_length=200)


class MealSuggestion(BaseModel):
    """One AI-suggested meal. The numbers are the AI's rough estimates."""

    name: str
    description: str = ""
    portion: str = ""
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fits_remaining: bool  # computed in Python: calories <= calories left today


class MealSuggestionResponse(BaseModel):
    log_date: date_type
    meal_slot: Optional[MealSlotName] = None
    remaining: MacroTotals  # computed in Python, never by the AI
    suggestions: list[MealSuggestion] = Field(default_factory=list)
    ai_used: bool
    message: Optional[str] = None
