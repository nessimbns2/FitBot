"""
app/core/config.py
Pydantic-settings configuration for Fitness Coach.
All values are read from environment variables or a .env file.
"""
from __future__ import annotations

from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ───────────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./fitness.db"

    # ── Directories ────────────────────────────────────────────────────────────
    DOCS_DIR: str = "backend/docs"
    VECTORSTORE_DIR: str = "backend/vectorstore"

    # ── LLM settings ──────────────────────────────────────────────────────────
    LLM_PROVIDER: str = "gemini"
    LLM_MODEL: str = "gemini-3.5-flash-lite"
    LLM_API_KEY: str = ""
    LLM_TIMEOUT_SECONDS: float = 30.0

    # ── Authentication (JWT) ───────────────────────────────────────────────────
    # Override JWT_SECRET_KEY in .env — the default is only safe for local tests.
    JWT_SECRET_KEY: str = "dev-only-insecure-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24

    # ── Embedding model ────────────────────────────────────────────────────────
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ── CORS ───────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] | str = ["http://localhost:5173"]
    # Also accept any local dev port (Vite moves to 5174, 5175… when 5173 is taken).
    CORS_ORIGIN_REGEX: str = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"

    # ── Misc ───────────────────────────────────────────────────────────────────
    DEBUG: bool = False

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def use_psycopg3_driver(cls, v: str) -> str:
        """Route plain postgres URLs to the installed psycopg (v3) driver."""
        for prefix in ("postgresql://", "postgres://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Allow CORS_ORIGINS to be a comma-separated string in .env."""
        if isinstance(v, str):
            # If string is json formatted list like '["http://localhost"]'
            if v.strip().startswith("[") and v.strip().endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


    @field_validator("DOCS_DIR", "VECTORSTORE_DIR", mode="after")
    @classmethod
    def resolve_directory(cls, v: str) -> str:
        from pathlib import Path
        p = Path(v)
        if not p.exists():
            # If running from backend/, try without leading 'backend/'
            if v.startswith("backend/") and Path(v[8:]).exists():
                return v[8:]
            # Or if running from backend/, and relative to backend/
            if (Path(__file__).resolve().parent.parent.parent / v.removeprefix("backend/")).exists():
                return str(Path(__file__).resolve().parent.parent.parent / v.removeprefix("backend/"))
        return v


# Singleton — import this everywhere instead of re-instantiating.
settings = Settings()
