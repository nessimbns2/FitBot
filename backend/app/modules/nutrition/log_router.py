"""
app/modules/nutrition/log_router.py
HTTP layer for the food log CRUD. Attached to the nutrition router, so every
path below is served under /api/nutrition.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlmodel import Session

from app.core.database import get_session
from app.modules.nutrition import food_log_service as svc
from app.modules.nutrition import suggestion_service as suggest_svc
from app.modules.nutrition.models import (
    DailySummary,
    FoodLogCreate,
    FoodLogRead,
    FoodLogUpdate,
    MealSuggestionResponse,
    SuggestMealRequest,
)
from app.modules.rag_core.engine import get_llm_client

SessionDep = Annotated[Session, Depends(get_session)]

router = APIRouter(tags=["nutrition"])


@router.post(
    "/log",
    response_model=FoodLogRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a food log entry",
)
def create_log_entry(body: FoodLogCreate, session: SessionDep) -> FoodLogRead:
    return svc.create_entry(session, body)


@router.get(
    "/log",
    response_model=list[FoodLogRead],
    summary="List the food log entries of one day (default: today)",
)
def list_log_entries(
    session: SessionDep,
    log_date: Optional[date] = Query(None, alias="date", description="YYYY-MM-DD"),
) -> list[FoodLogRead]:
    return svc.list_entries(session, log_date)


# NOTE: must be declared before /log/{entry_id}, otherwise "summary" would be
# read as an entry id.
@router.get(
    "/log/summary",
    response_model=DailySummary,
    summary="Eaten so far vs daily targets (default: today)",
)
def get_daily_summary(
    session: SessionDep,
    log_date: Optional[date] = Query(None, alias="date", description="YYYY-MM-DD"),
) -> DailySummary:
    return svc.daily_summary(session, log_date)


@router.get(
    "/log/{entry_id}",
    response_model=FoodLogRead,
    summary="Get one food log entry",
)
def get_log_entry(entry_id: int, session: SessionDep) -> FoodLogRead:
    try:
        return svc.get_entry(session, entry_id)
    except svc.FoodLogNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put(
    "/log/{entry_id}",
    response_model=FoodLogRead,
    summary="Edit a food log entry (only the fields sent are changed)",
)
def update_log_entry(
    entry_id: int, body: FoodLogUpdate, session: SessionDep
) -> FoodLogRead:
    try:
        return svc.update_entry(session, entry_id, body)
    except svc.FoodLogNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )


@router.delete(
    "/log/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a food log entry",
)
def delete_log_entry(entry_id: int, session: SessionDep) -> Response:
    try:
        svc.delete_entry(session, entry_id)
    except svc.FoodLogNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/suggest-meal",
    response_model=MealSuggestionResponse,
    summary="Suggest meals that fit what is left of today's targets",
)
def suggest_meal(body: SuggestMealRequest, session: SessionDep) -> MealSuggestionResponse:
    try:
        return suggest_svc.suggest_meals(session, get_llm_client(), body)
    except suggest_svc.AINotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except suggest_svc.AIUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
