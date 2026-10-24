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
    LLM_MODEL: str = "gemini-2.5-flash"
    LLM_API_KEY: str = ""


    # ── Embedding model ────────────────────────────────────────────────────────
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ── CORS ───────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] | str = ["http://localhost:5173"]

    # ── Misc ───────────────────────────────────────────────────────────────────
    DEBUG: bool = False

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
