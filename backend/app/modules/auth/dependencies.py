"""
app/modules/auth/dependencies.py
FastAPI dependency resolving the authenticated user from the `Authorization: Bearer` header.
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.core.database import get_session
from app.modules.auth.models import User
from app.modules.auth.security import decode_access_token

_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated. Please log in.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    session: Annotated[Session, Depends(get_session)],
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer)],
) -> User:
    """Return the active user owning the bearer token, or raise 401."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _UNAUTHORIZED
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise _UNAUTHORIZED
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise _UNAUTHORIZED
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
