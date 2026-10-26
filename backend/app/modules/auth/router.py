"""
app/modules/auth/router.py
HTTP layer for authentication: register, login, current account, password, deletion.
"""


from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlmodel import Session

from app.core.database import get_session
from app.core.rate_limit import limiter
from app.modules.auth import service
from app.modules.auth.dependencies import CurrentUser
from app.modules.auth.models import (
    AccountUpdate,
    ChangePasswordRequest,
    DeleteAccountRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserRead,
)

SessionDep = Annotated[Session, Depends(get_session)]

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def register(request: Request, data: RegisterRequest, session: SessionDep):
    """Create an account and return an access token (the user is logged in immediately)."""
    user = service.register_user(session, data)
    return service.issue_token(user)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, data: LoginRequest, session: SessionDep):
    """Exchange email + password for a JWT access token."""
    user = service.authenticate(session, data.email, data.password)
    return service.issue_token(user)


@router.get("/me", response_model=UserRead)
def read_me(user: CurrentUser):
    """Return the authenticated account."""
    return user


@router.put("/me", response_model=UserRead)
def update_me(data: AccountUpdate, user: CurrentUser, session: SessionDep):
    """Update the account's display name."""
    return service.update_account(session, user, data)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
def change_password(request: Request, data: ChangePasswordRequest, user: CurrentUser, session: SessionDep):
    """Change the password after re-checking the current one."""
    service.change_password(session, user, data)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(data: DeleteAccountRequest, user: CurrentUser, session: SessionDep):
    """Permanently delete the account and all associated personal data."""
    service.delete_account(session, user, data.password)
