"""
Tests for system health and diagnostics endpoints.
"""

from fastapi.testclient import TestClient


def test_health_endpoint_returns_200(client: TestClient):
    """Verify that GET /api/health responds with HTTP 200 and expected schema fields."""
    response = client.get("/api/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert "app_name" in data
    assert "version" in data
    assert "environment" in data
    assert "database" in data
    assert "timestamp" in data
    assert "data_notice" in data

    # Check database status structure
    db_info = data["database"]
    assert "status" in db_info
    assert "dialect" in db_info
    assert "connected" in db_info


def test_root_endpoint_returns_200(client: TestClient):
    """Verify that root GET / responds with basic status and documentation link."""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "running"
    assert data["docs"] == "/docs"
    assert data["health"] == "/api/health"
