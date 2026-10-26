"""
app/modules/auth/service.py
Business logic for accounts: registration, login, profile of the account, deletion.
No HTTP concerns besides raising HTTPException for client errors.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlmodel import Session, delete, select

from app.modules.auth.models import (
    AccountUpdate,
    ChangePasswordRequest,
    RegisterRequest,
    TokenResponse,
    User,
    UserRead,
)
from app.modules.auth.security import create_access_token, hash_password, verify_password

# A valid bcrypt hash used to keep login timing constant when the email is unknown.
_DUMMY_HASH = hash_password("timing-equalizer-0")


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.exec(select(User).where(User.email == email.strip().lower())).first()


def issue_token(user: User) -> TokenResponse:
    token, expires_in = create_access_token(user.id)  # type: ignore[arg-type]
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserRead.model_validate(user, from_attributes=True),
    )


def register_user(session: Session, data: RegisterRequest) -> User:
    """Create a new account and its default fitness profile."""
    from app.modules.user.service import get_or_create_profile

    if get_user_by_email(session, data.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    user = User(
        email=data.email,
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        last_login_at=datetime.now(timezone.utc),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    get_or_create_profile(session, user.id)  # type: ignore[arg-type]
    return user


def authenticate(session: Session, email: str, password: str) -> User:
    """Return the user if the credentials are valid, else raise a generic 401."""
    user = get_user_by_email(session, email)
    password_ok = verify_password(password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not password_ok or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    user.last_login_at = datetime.now(timezone.utc)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def update_account(session: Session, user: User, data: AccountUpdate) -> User:
    user.full_name = data.full_name
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def change_password(session: Session, user: User, data: ChangePasswordRequest) -> None:
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    if data.current_password == data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The new password must be different from the current one.",
        )
    user.password_hash = hash_password(data.new_password)
    session.add(user)
    session.commit()


def delete_account(session: Session, user: User, password: str) -> None:
    """Permanently delete the account and every row of personal data it owns."""
    from app.modules.exercises.models import SavedRoutine
    from app.modules.nutrition.models import MealLog
    from app.modules.progressive_overload.models import WorkoutSet
    from app.modules.user.models import ChatMessage, ChatSession, UserProfile

    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is incorrect.",
        )
    session_ids = select(ChatSession.id).where(ChatSession.user_id == user.id)
    session.exec(delete(ChatMessage).where(ChatMessage.session_id.in_(session_ids)))  # type: ignore[attr-defined]
    session.exec(delete(ChatSession).where(ChatSession.user_id == user.id))  # type: ignore[arg-type]
    session.exec(delete(WorkoutSet).where(WorkoutSet.user_id == user.id))  # type: ignore[arg-type]
    session.exec(delete(MealLog).where(MealLog.user_id == user.id))  # type: ignore[arg-type]
    session.exec(delete(SavedRoutine).where(SavedRoutine.user_id == user.id))  # type: ignore[arg-type]
    session.exec(delete(UserProfile).where(UserProfile.user_id == user.id))  # type: ignore[arg-type]
    session.delete(user)
    session.commit()
