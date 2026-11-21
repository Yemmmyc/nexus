"""Tests for the /api/v1/health endpoint and structured error handling."""

from fastapi.testclient import TestClient


def test_health_endpoint_returns_ok(client: TestClient) -> None:
    """GET /api/v1/health should return 200 OK with expected status fields."""
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "NEXUS"
    assert body["db_connected"] is True
    assert body["ai_mode"] in ("auto", "llm", "deterministic")
    assert isinstance(body["llm_configured"], bool)
    assert isinstance(body["simulator_running"], bool)
    assert "timestamp" in body


def test_unknown_route_returns_structured_404(client: TestClient) -> None:
    """Unknown API routes should return a structured 404 JSON error response."""
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "http_error"
    assert body["path"] == "/api/v1/does-not-exist"
    assert "detail" in body
    assert "timestamp" in body

