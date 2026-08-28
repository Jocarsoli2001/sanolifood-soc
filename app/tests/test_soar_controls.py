import re
from collections.abc import Callable

from fastapi.testclient import TestClient


TOKEN = "test-soar-internal-token-with-more-than-thirty-two-characters"
AUTHORIZATION = {"Authorization": f"Bearer {TOKEN}"}


def csrf_from(response_text: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', response_text)
    assert match
    return match.group(1)


def control_payload(
    *,
    action_id: str = "11111111-1111-4111-8111-111111111111",
    control_type: str = "app_ip_block",
    target: str = "10.20.0.50",
) -> dict:
    return {
        "action_id": action_id,
        "incident_id": "22222222-2222-4222-8222-222222222222",
        "control_type": control_type,
        "target": target,
        "ttl_seconds": 600,
        "reason": "Contención temporal aprobada durante una validación controlada.",
        "details": {"rule_id": 110130},
    }


def test_internal_soar_api_requires_bearer_token(client: TestClient) -> None:
    assert client.get("/internal/soar/status").status_code == 401
    response = client.get("/internal/soar/status", headers=AUTHORIZATION)
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "active_controls": 0, "schema_version": 1}


def test_ip_control_is_idempotent_enforced_and_reversible(client: TestClient) -> None:
    first = client.post(
        "/internal/soar/controls", headers=AUTHORIZATION, json=control_payload()
    )
    assert first.status_code == 200
    assert first.json()["created"] is True

    duplicate = client.post(
        "/internal/soar/controls", headers=AUTHORIZATION, json=control_payload()
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["created"] is False

    blocked = client.get("/", headers={"X-Real-IP": "10.20.0.50"})
    assert blocked.status_code == 403

    rollback = client.post(
        "/internal/soar/controls/11111111-1111-4111-8111-111111111111/rollback",
        headers=AUTHORIZATION,
    )
    assert rollback.status_code == 200
    assert rollback.json()["changed"] is True

    restored = client.get("/", headers={"X-Real-IP": "10.20.0.50"})
    assert restored.status_code != 403


def test_protected_or_out_of_scope_addresses_are_rejected(client: TestClient) -> None:
    protected = client.post(
        "/internal/soar/controls",
        headers=AUTHORIZATION,
        json=control_payload(target="10.20.0.10"),
    )
    assert protected.status_code == 422
    assert "protegido" in protected.json()["detail"]

    outside = client.post(
        "/internal/soar/controls",
        headers=AUTHORIZATION,
        json=control_payload(target="192.0.2.25"),
    )
    assert outside.status_code == 422
    assert "fuera" in outside.json()["detail"]


def test_account_control_temporarily_blocks_login(
    client: TestClient,
    user_factory: Callable,
) -> None:
    user_factory(username="quality.operator", role="quality", full_name="Operador Calidad")
    response = client.post(
        "/internal/soar/controls",
        headers=AUTHORIZATION,
        json=control_payload(
            action_id="33333333-3333-4333-8333-333333333333",
            control_type="app_account_lock",
            target="quality.operator",
        ),
    )
    assert response.status_code == 200

    page = client.get("/auth/login")
    login = client.post(
        "/auth/login",
        data={
            "username": "quality.operator",
            "password": "SanoliFood!2026",
            "csrf_token": csrf_from(page.text),
        },
    )
    assert login.status_code == 423
    assert "temporalmente bloqueada" in login.text
