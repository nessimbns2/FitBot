"""
backend/tests/conftest.py
Shared pytest fixtures for Fitness Coach tests.

The in-memory SQLite engine overrides get_session so every test is isolated.
`client` is authenticated as a freshly registered test user; `anon_client` is not.
"""

from __future__ import annotations

import os

# Tests never touch the real PostgreSQL database nor call the real LLM provider.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["LLM_API_KEY"] = ""

from collections.abc import Generator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402
from sqlmodel.pool import StaticPool  # noqa: E402

from app.core.database import get_session, import_all_models  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.modules.auth.models import RegisterRequest, User  # noqa: E402
from app.modules.auth.security import create_access_token  # noqa: E402
from app.modules.auth.service import register_user  # noqa: E402
from main_v2 import app  # noqa: E402

import_all_models()
# Rate limits are covered by a dedicated test; keep them off for the functional suite.
limiter.enabled = False

TEST_EMAIL = "athlete@example.com"
TEST_PASSWORD = "Strong-pass-123"


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


@pytest.fixture(name="test_user")
def test_user_fixture(session: Session) -> User:
    """A registered account (with its default profile) in the test database."""
    return register_user(
        session,
        RegisterRequest(full_name="Test Athlete", email=TEST_EMAIL, password=TEST_PASSWORD),
    )


@pytest.fixture(name="auth_headers")
def auth_headers_fixture(test_user: User) -> dict[str, str]:
    token, _ = create_access_token(test_user.id)  # type: ignore[arg-type]
    return {"Authorization": f"Bearer {token}"}


def _override_session(engine):
    def get_session_override() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_session_override


@pytest.fixture(name="anon_client", scope="function")
def anon_client_fixture(engine) -> Generator[TestClient, None, None]:
    """Unauthenticated TestClient bound to the in-memory engine."""
    _override_session(engine)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(name="client", scope="function")
def client_fixture(engine, auth_headers) -> Generator[TestClient, None, None]:
    """TestClient authenticated as `test_user`, bound to the in-memory engine."""
    _override_session(engine)
    with TestClient(app) as c:
        c.headers.update(auth_headers)
        yield c
    app.dependency_overrides.clear()
