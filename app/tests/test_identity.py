import re
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sanolifood.database.session import engine
from sanolifood.models import AuditEvent, User


def csrf_from(response_text: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', response_text)
    assert match
    return match.group(1)


def login(client: TestClient, username: str, password: str) -> None:
    page = client.get("/auth/login")
    response = client.post(
        "/auth/login",
        data={"username": username, "password": password, "csrf_token": csrf_from(page.text)},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_login_uses_versioned_corporate_styles(client: TestClient) -> None:
    response = client.get("/auth/login")
    assert response.status_code == 200
    assert "app.css?v=0.7.0" in response.text
    assert 'class="auth-shell"' in response.text


def test_successful_login_creates_audit_event(client: TestClient, user_factory: Callable) -> None:
    user_factory()
    login(client, "admin.sanolifood", "SanoliFood!2026")
    with Session(engine) as db:
        event = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "auth.login.succeeded"))
        assert event is not None
        assert event.actor_username == "admin.sanolifood"
        assert event.outcome == "success"


def test_failed_logins_lock_account(client: TestClient, user_factory: Callable) -> None:
    user_factory()
    page = client.get("/auth/login")
    token = csrf_from(page.text)
    for _ in range(5):
        response = client.post(
            "/auth/login",
            data={"username": "admin.sanolifood", "password": "incorrecta", "csrf_token": token},
        )
        assert response.status_code == 401
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.username == "admin.sanolifood"))
        assert user is not None and user.locked_until is not None
        locked_events = db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == "auth.account.locked"))
        assert locked_events == 1


def test_role_blocks_user_administration(client: TestClient, user_factory: Callable) -> None:
    user_factory(username="quality.operator", role="quality", full_name="Operador Calidad")
    login(client, "quality.operator", "SanoliFood!2026")
    response = client.get("/users")
    assert response.status_code == 403


def test_admin_can_create_user(client: TestClient, user_factory: Callable) -> None:
    user_factory()
    login(client, "admin.sanolifood", "SanoliFood!2026")
    page = client.get("/users")
    response = client.post(
        "/users",
        data={
            "username": "quality.operator",
            "email": "quality.operator@sanolifood.local",
            "full_name": "Operador Calidad",
            "role": "quality",
            "password": "Quality!2026Demo",
            "csrf_token": csrf_from(page.text),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    with Session(engine) as db:
        created = db.scalar(select(User).where(User.username == "quality.operator"))
        assert created is not None and created.role == "quality"


def test_admin_can_view_audit_events(client: TestClient, user_factory: Callable) -> None:
    user_factory()
    login(client, "admin.sanolifood", "SanoliFood!2026")
    response = client.get("/audit")
    assert response.status_code == 200
    assert "Registro de auditoría" in response.text
    assert "auth.login.succeeded" in response.text
