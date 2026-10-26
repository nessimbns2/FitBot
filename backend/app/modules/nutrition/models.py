"""
app/modules/nutrition/models.py
Meal diary table (previously kept in the browser's localStorage) and its schemas.

NOTE: Do NOT add `from __future__ import annotations` to this file
(SQLModel 0.0.22 evaluates table annotations eagerly).
"""

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class MealLog(SQLModel, table=True):
    """One meal entry in a user's nutrition diary."""

    __tablename__ = "meal_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    logged_on: date = Field(default_factory=lambda: datetime.now(timezone.utc).date(), index=True)
    slot: str = Field(default="Snack", max_length=40)
    meal_name: str = Field(max_length=200)
    calories: int = Field(default=0, ge=0, le=10000)
    protein_g: float = Field(default=0.0, ge=0.0, le=1000.0)
    carbs_g: float = Field(default=0.0, ge=0.0, le=1000.0)
    fat_g: float = Field(default=0.0, ge=0.0, le=1000.0)
    food_items: Optional[List[Dict[str, Any]]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FoodItemEntry(SQLModel):
    name: str = Field(max_length=200)
    portion_est: str = Field(default="", max_length=100)
    calories: int = Field(default=0, ge=0, le=10000)


class MealLogCreate(SQLModel):
    slot: str = Field(default="Snack", min_length=1, max_length=40)
    meal_name: str = Field(min_length=1, max_length=200)
    calories: int = Field(ge=0, le=10000)
    protein_g: float = Field(default=0.0, ge=0.0, le=1000.0)
    carbs_g: float = Field(default=0.0, ge=0.0, le=1000.0)
    fat_g: float = Field(default=0.0, ge=0.0, le=1000.0)
    food_items: Optional[List[FoodItemEntry]] = None
    logged_on: Optional[date] = None


class MealLogRead(SQLModel):
    id: int
    logged_on: date
    slot: str
    meal_name: str
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    food_items: Optional[List[Dict[str, Any]]] = None
    created_at: datetime
