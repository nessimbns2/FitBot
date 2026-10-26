"""
app/modules/nutrition/food_log_service.py
Business logic for the food log CRUD. No HTTP code here: the router translates
FoodLogNotFound to 404 and ValueError to 422.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlmodel import Session, select

from app.modules.nutrition import service as nutrition_svc
from app.modules.nutrition.models import (
    DailySummary,
    FoodLogCreate,
    FoodLogEntry,
    FoodLogUpdate,
    MacroPercent,
    MacroTotals,
    MealSlotName,
)


_SLOT_ORDER = {
    MealSlotName.breakfast: 0,
    MealSlotName.lunch: 1,
    MealSlotName.dinner: 2,
    MealSlotName.post_workout: 3,
    MealSlotName.snack: 4,
}


class FoodLogNotFound(LookupError):
    """Raised when an entry id does not exist (or belongs to another user)."""


# ── Create ────────────────────────────────────────────────────────────────────


def create_entry(session: Session, data: FoodLogCreate, *, user_id: int) -> FoodLogEntry:
    entry = FoodLogEntry(
        user_id=user_id,
        log_date=data.log_date or date.today(),
        meal_slot=data.meal_slot,
        name=data.name,
        calories=data.calories,
        protein_g=data.protein_g,
        carbs_g=data.carbs_g,
        fat_g=data.fat_g,
        source=data.source,
        notes=data.notes,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


# ── Read ──────────────────────────────────────────────────────────────────────


def get_entry(session: Session, entry_id: int, *, user_id: int) -> FoodLogEntry:
    entry = session.get(FoodLogEntry, entry_id)
    if entry is None or entry.user_id != user_id:
        raise FoodLogNotFound(f"Food log entry {entry_id} not found")
    return entry


def list_entries(session: Session, log_date: Optional[date] = None, *, user_id: int) -> list[FoodLogEntry]:
    """Entries for one day (default: today), ordered breakfast to snack, then oldest first."""
    target = log_date or date.today()
    statement = select(FoodLogEntry).where(
        FoodLogEntry.user_id == user_id,
        FoodLogEntry.log_date == target,
    )
    entries = list(session.exec(statement).all())
    entries.sort(key=lambda e: (_SLOT_ORDER[e.meal_slot], e.created_at, e.id or 0))
    return entries


# ── Update ────────────────────────────────────────────────────────────────────


def update_entry(session: Session, entry_id: int, data: FoodLogUpdate, *, user_id: int) -> FoodLogEntry:
    changes = data.model_dump(exclude_unset=True)
    # A field explicitly sent as null is only allowed for notes (to clear them).
    changes = {k: v for k, v in changes.items() if v is not None or k == "notes"}
    if not changes:
        raise ValueError("No fields to update")

    entry = get_entry(session, entry_id, user_id=user_id)
    for field, value in changes.items():
        setattr(entry, field, value)
    entry.updated_at = datetime.now(timezone.utc)

    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


# ── Delete ────────────────────────────────────────────────────────────────────


def delete_entry(session: Session, entry_id: int, *, user_id: int) -> None:
    entry = get_entry(session, entry_id, user_id=user_id)
    session.delete(entry)
    session.commit()


# ── Daily summary (eaten so far vs targets) ───────────────────────────────────


def sum_entries(entries: list[FoodLogEntry]) -> MacroTotals:
    """Add up calories and macros of the given entries."""
    return MacroTotals(
        calories=round(sum(e.calories for e in entries), 1),
        protein_g=round(sum(e.protein_g for e in entries), 1),
        carbs_g=round(sum(e.carbs_g for e in entries), 1),
        fat_g=round(sum(e.fat_g for e in entries), 1),
    )


def _remaining(targets: MacroTotals, consumed: MacroTotals) -> MacroTotals:
    return MacroTotals(
        calories=round(targets.calories - consumed.calories, 1),
        protein_g=round(targets.protein_g - consumed.protein_g, 1),
        carbs_g=round(targets.carbs_g - consumed.carbs_g, 1),
        fat_g=round(targets.fat_g - consumed.fat_g, 1),
    )


def _pct(consumed: float, target: float) -> Optional[float]:
    if target <= 0:
        return None
    return round(consumed / target * 100, 1)


def build_summary(
    log_date: date,
    entries: list[FoodLogEntry],
    targets: MacroTotals,
    floor_applied: bool = False,
    warnings: Optional[list[str]] = None,
) -> DailySummary:
    """Pure function: compare the day's entries with the given targets."""
    consumed = sum_entries(entries)
    return DailySummary(
        log_date=log_date,
        entry_count=len(entries),
        consumed=consumed,
        targets=targets,
        remaining=_remaining(targets, consumed),
        percent_of_target=MacroPercent(
            calories=_pct(consumed.calories, targets.calories),
            protein_g=_pct(consumed.protein_g, targets.protein_g),
            carbs_g=_pct(consumed.carbs_g, targets.carbs_g),
            fat_g=_pct(consumed.fat_g, targets.fat_g),
        ),
        floor_applied=floor_applied,
        warnings=list(warnings or []),
    )


def daily_summary(session: Session, log_date: Optional[date] = None, *, user_id: int) -> DailySummary:
    """Totals for one day (default: today) against the user's calculated targets."""
    target_day = log_date or date.today()
    entries = list_entries(session, target_day, user_id=user_id)
    macros = nutrition_svc.calculate_macros(nutrition_svc.MacroRequest(), session, user_id)
    targets = MacroTotals(
        calories=macros.target_kcal,
        protein_g=macros.protein_g,
        carbs_g=macros.carbs_g,
        fat_g=macros.fat_g,
    )
    return build_summary(
        target_day, entries, targets, macros.floor_applied, macros.warnings
    )
