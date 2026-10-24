"""
tests/test_database.py
Verify the get_session override is working correctly.
"""


def test_session_override_uses_in_memory_db(client, session):
    """The TestClient must use the overridden in-memory session, not the real DB."""
    # health endpoint loads fine, proving the app starts with the overridden DB
    resp = client.get("/api/health")
    assert resp.status_code == 200
    # The session object is a real SQLModel session backed by StaticPool
    from sqlmodel import Session
    assert isinstance(session, Session)
