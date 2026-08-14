from fastapi.testclient import TestClient

from sanolifood.main import app


client = TestClient(app)


def test_dashboard_has_corporate_identity() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "SanoliFood SA" in response.text
    assert "Centro de operaciones" in response.text
    assert "Telemetría activa" in response.text

