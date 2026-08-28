from fastapi.testclient import TestClient

from sanolifood.database.base import Base
from sanolifood.database.session import engine


def test_liveness_returns_version_and_correlation_id(client: TestClient) -> None:
    response = client.get("/health/live", headers={"X-Correlation-ID": "test-run-001"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["version"] == "0.7.0"
    assert response.headers["X-Correlation-ID"] == "test-run-001"


def test_security_headers_are_applied(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_static_assets_disable_browser_cache_in_test(client: TestClient) -> None:
    response = client.get("/static/css/app.css")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert ".auth-shell" in response.text


def test_readiness_fails_when_required_schema_is_missing(client: TestClient) -> None:
    Base.metadata.drop_all(engine)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["detail"]["reason"] == "database_schema_incomplete"
    Base.metadata.create_all(engine)


def test_suite_uses_isolated_sqlite_database() -> None:
    assert engine.url.get_backend_name() == "sqlite"
