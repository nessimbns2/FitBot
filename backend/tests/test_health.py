"""
backend/tests/test_health.py
Phase 0 smoke test — verifies the app boots and the health endpoint responds.
"""


def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_method_not_allowed(client):
    """POST to the health endpoint must be rejected."""
    response = client.post("/api/health")
    assert response.status_code == 405


def test_health_has_health_route(client):
    """The OpenAPI schema must include the health endpoint."""
    schema = client.get("/openapi.json").json()
    paths = schema.get("paths", {})
    assert "/api/health" in paths
