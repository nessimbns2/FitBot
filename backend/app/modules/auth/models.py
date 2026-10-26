"""
app/modules/auth/models.py
User account table and the request/response schemas of the auth API.

NOTE: Do NOT add `from __future__ import annotations` to this file
(SQLModel 0.0.22 evaluates table annotations eagerly).
"""

import re
from datetime import datetime, timezone
from typing import Optional

from pydantic import EmailStr, field_validator
from sqlmodel import Field, SQLModel

PASSWORD_MIN_LENGTH = 8
# bcrypt only uses the first 72 bytes of a password; reject longer ones explicitly.
PASSWORD_MAX_BYTES = 72


def _validate_password_strength(value: str) -> str:
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters long.")
    if len(value.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise ValueError(f"Password must be at most {PASSWORD_MAX_BYTES} bytes long.")
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("Password must contain at least one letter and one digit.")
    return value


# ── Table ─────────────────────────────────────────────────────────────────────


class User(SQLModel, table=True):
    """An authenticated FitBot account. Owns one profile and all personal data."""

    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True, max_length=255)
    full_name: str = Field(max_length=120)
    password_hash: str = Field(max_length=255)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login_at: Optional[datetime] = Field(default=None)


# ── Schemas ───────────────────────────────────────────────────────────────────


class RegisterRequest(SQLModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < 2:
            raise ValueError("Full name must contain at least 2 characters.")
        return v

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return _validate_password_strength(v)


class LoginRequest(SQLModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class UserRead(SQLModel):
    id: int
    email: str
    full_name: str
    created_at: datetime
    last_login_at: Optional[datetime] = None


class TokenResponse(SQLModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


class AccountUpdate(SQLModel):
    full_name: str = Field(min_length=2, max_length=120)

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < 2:
            raise ValueError("Full name must contain at least 2 characters.")
        return v


class ChangePasswordRequest(SQLModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return _validate_password_strength(v)


class DeleteAccountRequest(SQLModel):
    password: str = Field(min_length=1, max_length=256)
