"""
app/core/database.py
SQLModel engine, session dependency, and database initialisation.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent

# ── Engine ────────────────────────────────────────────────────────────────────

connect_args: dict = {}
engine_kwargs: dict = {}
if settings.is_sqlite:
    connect_args["check_same_thread"] = False
else:
    # PostgreSQL: keep a small healthy pool and drop dead connections transparently.
    engine_kwargs.update(pool_pre_ping=True, pool_size=5, max_overflow=10)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DEBUG,
    **engine_kwargs,
)


# ── Session dependency ────────────────────────────────────────────────────────


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session per request."""
    with Session(engine) as session:
        yield session


# ── Initialisation ────────────────────────────────────────────────────────────


def import_all_models() -> None:
    """Register every table on SQLModel.metadata (needed by create_all and Alembic)."""
    import app.modules.auth.models  # noqa: F401
    import app.modules.exercises.models  # noqa: F401
    import app.modules.nutrition.models  # noqa: F401
    import app.modules.progressive_overload.models  # noqa: F401
    import app.modules.user.models  # noqa: F401


def init_db() -> None:
    """Bring the schema up to date at application startup.

    * PostgreSQL (the real database): run Alembic migrations up to `head`.
    * SQLite (tests / quick local runs): create the tables directly from the models.
    """
    import_all_models()
    if settings.is_sqlite:
        SQLModel.metadata.create_all(engine)
        return

    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(cfg, "head")
