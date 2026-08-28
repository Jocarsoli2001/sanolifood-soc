from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from sanolifood.soar.adapters import AdapterError
from sanolifood.soar.catalog import get_catalog
from sanolifood.soar.config import SoarSettings
from sanolifood.soar.controller import app as controller_app
from sanolifood.soar.database import soar_engine
from sanolifood.soar.schemas import DecisionRequest, NormalizedAlert
from sanolifood.soar.service import SoarService


TOKEN = "test-soar-internal-token-with-more-than-thirty-two-characters"
AUTHORIZATION = {"Authorization": f"Bearer {TOKEN}"}


def alert_payload(*, dedup_key: str = "a" * 64, rule_id: int = 110130) -> dict:
    policy = get_catalog().for_rule(rule_id)
    now = datetime.now(timezone.utc)
    return {
        "schema_version": 1,
        "workflow_version": "0.7.0",
        "dedup_key": dedup_key,
        "source_alert_id": f"test-{dedup_key[:8]}",
        "rule_id": rule_id,
        "rule_level": 12,
        "rule_description": "Controlled SanoliFood SOAR validation",
        "priority": policy.priority,
        "playbook_id": policy.id,
        "agent_id": "000",
        "agent_name": "soc-validation",
        "source_ip": "10.20.0.50",
        "actor_username": "quality.operator",
        "resource_path": "/controlled/validation",
        "detected_at": (now - timedelta(seconds=2)).isoformat(),
        "received_at": now.isoformat(),
        "raw_alert": {"rule": {"id": str(rule_id)}, "validation": True},
    }


def test_controller_creates_deduplicates_approves_and_simulates() -> None:
    with TestClient(controller_app) as client:
        first = client.post(
            "/api/v1/incidents", headers=AUTHORIZATION, json=alert_payload()
        )
        assert first.status_code == 202
        assert first.json()["created"] is True
        incident_id = first.json()["incident"]["id"]

        duplicate = client.post(
            "/api/v1/incidents", headers=AUTHORIZATION, json=alert_payload()
        )
        assert duplicate.status_code == 202
        assert duplicate.json()["created"] is False
        assert duplicate.json()["incident"]["id"] == incident_id

        automatic = client.post(
            f"/api/v1/incidents/{incident_id}/dispatch?scope=automatic",
            headers=AUTHORIZATION,
        )
        assert automatic.status_code == 200
        evidence = [
            item
            for item in automatic.json()["incident"]["actions"]
            if item["action_type"] == "collect_evidence"
        ][0]
        assert evidence["status"] == "completed"
        assert evidence["attempt_count"] == 1

        decision = client.post(
            f"/api/v1/incidents/{incident_id}/decision",
            headers=AUTHORIZATION,
            json={
                "decision": "approve",
                "analyst": "soc.validation",
                "reason": "Validación controlada de aprobación y contención reversible.",
                "nonce": "decision-validation-001",
                "requested_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        assert decision.status_code == 200

        dispatched = client.post(
            f"/api/v1/incidents/{incident_id}/dispatch?scope=approved",
            headers=AUTHORIZATION,
        )
        assert dispatched.status_code == 200
        containment = [
            item
            for item in dispatched.json()["incident"]["actions"]
            if item["action_type"] == "app_ip_block"
        ][0]
        assert containment["status"] == "simulated"
        assert containment["attempt_count"] == 1
        assert dispatched.json()["incident"]["status"] == "simulated"

        repeated = client.post(
            f"/api/v1/incidents/{incident_id}/dispatch?scope=approved",
            headers=AUTHORIZATION,
        )
        repeated_containment = [
            item
            for item in repeated.json()["incident"]["actions"]
            if item["action_type"] == "app_ip_block"
        ][0]
        assert repeated_containment["attempt_count"] == 1


def test_controller_rejects_triage_that_differs_from_catalog() -> None:
    payload = alert_payload(dedup_key="b" * 64)
    payload["priority"] = "low"
    with TestClient(controller_app) as client:
        response = client.post(
            "/api/v1/incidents", headers=AUTHORIZATION, json=payload
        )
    assert response.status_code == 422
    assert "catalog" in response.json()["detail"]


class FlakyExecutor:
    def __init__(self):
        self.calls = 0

    def execute(self, action, incident):
        self.calls += 1
        if self.calls == 1:
            raise AdapterError("temporary validation failure")
        return "completed", {"recovered": True}, None

    def rollback(self, action):
        return {"changed": True}


class ExpiringExecutor:
    def execute(self, action, incident):
        if action.action_type == "collect_evidence":
            return "completed", {"collected": True}, None
        return "applied", {"applied": True}, datetime.now(timezone.utc) - timedelta(seconds=1)

    def rollback(self, action):
        return {"changed": True, "reason": "ttl_expired"}


def test_failed_action_can_be_retried_with_audited_attempt_count(tmp_path: Path) -> None:
    settings = SoarSettings(
        soar_database_url="sqlite+pysqlite:///:memory:",
        soar_internal_token=TOKEN,
        soar_response_mode="dry-run",
        soar_evidence_dir=str(tmp_path),
    )
    executor = FlakyExecutor()
    with Session(soar_engine, expire_on_commit=False) as db:
        service = SoarService(db, get_catalog(), settings, executor=executor)
        incident, _ = service.create_incident(
            NormalizedAlert.model_validate(alert_payload(dedup_key="c" * 64, rule_id=110040))
        )
        service.dispatch(incident.id, "automatic")
        action = incident.actions[0]
        assert action.status == "failed"
        assert action.attempt_count == 1

        service.retry_action(action.id, actor="soc.validation")
        assert action.status == "completed"
        assert action.attempt_count == 2
        assert action.result == {"recovered": True}


def test_metrics_include_detection_and_approval_times() -> None:
    with Session(soar_engine, expire_on_commit=False) as db:
        service = SoarService(db, get_catalog(), SoarSettings(soar_internal_token=TOKEN))
        incident, _ = service.create_incident(
            NormalizedAlert.model_validate(alert_payload(dedup_key="d" * 64))
        )
        service.decide(
            incident.id,
            DecisionRequest(
                decision="reject",
                analyst="soc.validation",
                reason="La alerta pertenece a una validación controlada.",
                nonce="metrics-validation-001",
                requested_at=datetime.now(timezone.utc),
            ),
        )
        metrics = service.metrics()
        assert metrics["incident_count"] == 1
        assert metrics["mttd_seconds_average"] is not None
        assert metrics["mtta_seconds_average"] is not None
        assert metrics["incidents_by_status"] == {"rejected": 1}


def test_expired_live_action_is_rolled_back_automatically() -> None:
    settings = SoarSettings(soar_internal_token=TOKEN, soar_response_mode="live")
    with Session(soar_engine, expire_on_commit=False) as db:
        service = SoarService(db, get_catalog(), settings, executor=ExpiringExecutor())
        incident, _ = service.create_incident(
            NormalizedAlert.model_validate(alert_payload(dedup_key="e" * 64))
        )
        service.dispatch(incident.id, "automatic")
        service.decide(
            incident.id,
            DecisionRequest(
                decision="approve",
                analyst="soc.validation",
                reason="Validación controlada de caducidad y reversión automática.",
                nonce="expiration-validation-001",
                requested_at=datetime.now(timezone.utc),
            ),
        )
        service.dispatch(incident.id, "approved")

        rolled_back = service.expire_actions()
        containment = [
            action for action in incident.actions if action.action_type == "app_ip_block"
        ][0]
        assert [action.id for action in rolled_back] == [containment.id]
        assert containment.status == "rolled_back"
        assert containment.result["rollback"]["reason"] == "ttl_expired"
        assert incident.status == "closed"


def test_controller_never_proposes_containment_for_a_protected_asset() -> None:
    payload = alert_payload(dedup_key="f" * 64)
    payload["source_ip"] = "10.20.0.10"
    with Session(soar_engine, expire_on_commit=False) as db:
        service = SoarService(db, get_catalog(), SoarSettings(soar_internal_token=TOKEN))
        incident, _ = service.create_incident(NormalizedAlert.model_validate(payload))
        containment = [
            action for action in incident.actions if action.action_type == "app_ip_block"
        ][0]
        assert containment.status == "blocked_by_policy"
        assert containment.result == {"reason": "protected_ip_address"}
        assert not any(action.status == "pending_approval" for action in incident.actions)
