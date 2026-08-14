from fastapi.testclient import TestClient

from sanolifood.main import app


client = TestClient(app)


def test_liveness_returns_version_and_correlation_id() -> None:
    response = client.get("/health/live", headers={"X-Correlation-ID": "test-run-001"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["version"] == "0.1.0"
    assert response.headers["X-Correlation-ID"] == "test-run-001"


def test_security_headers_are_applied() -> None:
    response = client.get("/health/live")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"

