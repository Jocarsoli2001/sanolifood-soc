import re
from collections.abc import Callable

from fastapi.testclient import TestClient


def csrf_from(response_text: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', response_text)
    assert match
    return match.group(1)


def test_dashboard_requires_authentication(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login"


def test_authenticated_dashboard_has_corporate_identity(
    client: TestClient, user_factory: Callable
) -> None:
    user_factory()
    login_page = client.get("/auth/login")
    response = client.post(
        "/auth/login",
        data={"username": "admin.sanolifood", "password": "SanoliFood!2026", "csrf_token": csrf_from(login_page.text)},
        follow_redirects=True,
    )
    response = client.get("/")
    assert response.status_code == 200
    assert "SanoliFood SA" in response.text
    assert "Centro de operaciones" in response.text
    assert "Administrador SanoliFood" in response.text
