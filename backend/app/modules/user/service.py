"""
app/modules/user/service.py
Business logic for User & Profile and Chat Sessions.
No HTTP concerns — all functions accept a SQLModel Session argument.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.modules.user.models import (
    ChatMessage,
    ChatSession,
    MessageRead,
    SessionSummary,
    UserProfile,
    UserProfileUpdate,
)

# ── Single local user ─────────────────────────────────────────────────────────

DEFAULT_USER_ID = 1


def get_or_create_default_profile(session: Session) -> UserProfile:
    """Return the single local user profile, creating it on first call."""
    profile = session.get(UserProfile, DEFAULT_USER_ID)
    if profile is None:
        profile = UserProfile(id=DEFAULT_USER_ID)
        session.add(profile)
        session.commit()
        session.refresh(profile)
    return profile


def update_profile(session: Session, data: UserProfileUpdate) -> UserProfile:
    """Apply a partial update to the user profile."""
    profile = get_or_create_default_profile(session)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)
    profile.updated_at = datetime.now(timezone.utc)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


# ── Chat Sessions ─────────────────────────────────────────────────────────────


def create_session(session: Session, title: str = "New conversation") -> ChatSession:
    """Create a new chat session for the default user."""
    profile = get_or_create_default_profile(session)
    chat_session = ChatSession(user_id=profile.id, title=title)
    session.add(chat_session)
    session.commit()
    session.refresh(chat_session)
    return chat_session


def list_sessions(session: Session) -> list[SessionSummary]:
    """Return all sessions newest first."""
    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == DEFAULT_USER_ID)
        .order_by(ChatSession.updated_at.desc())  # type: ignore[arg-type]
    )
    sessions = session.exec(stmt).all()
    return [
        SessionSummary(
            id=s.id,
            title=s.title,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]


def get_session_or_404(session: Session, session_id: str) -> ChatSession:
    chat_session = session.get(ChatSession, session_id)
    if chat_session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return chat_session


def get_session_messages(session: Session, session_id: str) -> list[MessageRead]:
    """Return all messages for a session in chronological order."""
    get_session_or_404(session, session_id)
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)  # type: ignore[arg-type]
    )
    messages = session.exec(stmt).all()
    return [MessageRead.model_validate(m, from_attributes=True) for m in messages]


def append_message(
    session: Session,
    session_id: str,
    role: str,
    content: str,
    sources: list | None = None,
) -> ChatMessage:
    """Add a message to a session and update the session's updated_at."""
    chat_session = get_session_or_404(session, session_id)
    msg = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        sources=json.dumps(sources) if sources else None,
    )
    session.add(msg)
    chat_session.updated_at = datetime.now(timezone.utc)
    session.add(chat_session)
    session.commit()
    session.refresh(msg)
    return msg


def delete_session(session: Session, session_id: str) -> None:
    """Delete a session and all its messages (cascade)."""
    chat_session = get_session_or_404(session, session_id)
    # Delete messages first
    stmt = select(ChatMessage).where(ChatMessage.session_id == session_id)
    for msg in session.exec(stmt).all():
        session.delete(msg)
    session.delete(chat_session)
    session.commit()
