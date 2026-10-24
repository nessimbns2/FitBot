"""
app/core/database.py
SQLModel engine, session dependency, and database initialisation.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

# ── Engine ────────────────────────────────────────────────────────────────────

connect_args: dict = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DEBUG,
)


# ── Session dependency ────────────────────────────────────────────────────────


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session per request."""
    with Session(engine) as session:
        yield session


SessionDep = None  # populated below after import cycle is safe
# Use `Annotated[Session, Depends(get_session)]` at call sites.


# ── Initialisation ────────────────────────────────────────────────────────────


def init_db() -> None:
    """Create all tables defined in SQLModel metadata.

    Called once at application startup via the lifespan handler.
    Phase 9 will replace this with Alembic `upgrade head`.
    """
    SQLModel.metadata.create_all(engine)
