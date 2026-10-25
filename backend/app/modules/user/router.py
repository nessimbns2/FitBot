"""
app/modules/user/router.py
HTTP layer for the User & Profile module.
All business logic is delegated to service.py.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.database import get_session
from app.modules.user import models, service

SessionDep = Annotated[Session, Depends(get_session)]

router = APIRouter(
    prefix="/api/user",
    tags=["user"],
)


# ── Profile ───────────────────────────────────────────────────────────────────


@router.get("/profile", response_model=models.UserProfile)
def get_profile(session: SessionDep):
    """Return the local user profile, creating defaults on first call."""
    return service.get_or_create_default_profile(session)


@router.put("/profile", response_model=models.UserProfile)
def update_profile(data: models.UserProfileUpdate, session: SessionDep):
    """Partially update the user profile."""
    return service.update_profile(session, data)


# ── Chat Sessions ─────────────────────────────────────────────────────────────


@router.get("/sessions", response_model=list[models.SessionSummary])
def list_sessions(session: SessionDep):
    """List all chat sessions, newest first."""
    return service.list_sessions(session)


@router.get("/sessions/{session_id}/messages", response_model=list[models.MessageRead])
def get_session_messages(session_id: str, session: SessionDep):
    """Return all messages in a session in chronological order."""
    return service.get_session_messages(session, session_id)


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, session: SessionDep):
    """Delete a session and all its messages."""
    service.delete_session(session, session_id)


# ── Somatotype Assessment ─────────────────────────────────────────────────────


@router.get("/somatotype-questions")
def get_somatotype_questions():
    """Return the official 5 diagnostic questions for somatotype prediction."""
    return service.get_somatotype_questions()


@router.post("/predict-somatotype", response_model=models.SomatotypeQuizResponse)
def predict_somatotype(req: models.SomatotypeQuizRequest, session: SessionDep):
    """Analyze assessment answers and return the predicted somatotype with training/nutrition advice."""
    return service.predict_somatotype(session, req)


# ── Athlete Blueprint & Profile Audit ─────────────────────────────────────────


@router.post("/blueprint", response_model=models.AthleteBlueprintResponse)
def get_athlete_blueprint(
    session: SessionDep,
    req: models.AthleteBlueprintRequest = None,
):
    """Generate a scientific Athlete AI Blueprint and physiological profile audit."""
    return service.generate_athlete_blueprint(session, req)

