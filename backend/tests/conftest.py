"""
backend/tests/conftest.py
Shared pytest fixtures for Fitness Coach tests.

The in-memory SQLite engine overrides get_session so every test is isolated.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.database import get_session
from main_v2 import app


# ── In-memory test engine ─────────────────────────────────────────────────────


@pytest.fixture(name="engine", scope="function")
def engine_fixture():
    """Fresh in-memory SQLite engine per test — fully isolated."""
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    yield test_engine
    SQLModel.metadata.drop_all(test_engine)


@pytest.fixture(name="session", scope="function")
def session_fixture(engine) -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client", scope="function")
def client_fixture(engine) -> Generator[TestClient, None, None]:
    """TestClient with get_session overridden to use the in-memory engine."""

    def get_session_override() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
