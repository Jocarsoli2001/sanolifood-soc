import uuid
from collections import Counter
from datetime import datetime, timezone
import ipaddress
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from sanolifood.soar.adapters import AdapterError, ResponseExecutor
from sanolifood.soar.catalog import PlaybookCatalog
from sanolifood.soar.config import SoarSettings
from sanolifood.soar.models import Incident, OrchestrationError, ResponseAction, SoarAudit
from sanolifood.soar.schemas import DecisionRequest, NormalizedAlert, OrchestrationErrorRequest


USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,49}$")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalized_datetime(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    return normalized_datetime(value).astimezone(timezone.utc).isoformat()


class SoarService:
    def __init__(
        self,
        db: Session,
        catalog: PlaybookCatalog,
        settings: SoarSettings,
        executor: ResponseExecutor | None = None,
    ):
        self.db = db
        self.catalog = catalog
        self.settings = settings
        self.executor = executor or ResponseExecutor(settings)

    def audit(
        self,
        event_type: str,
        *,
        actor_type: str,
        actor: str,
        incident_id: str | None = None,
        action_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.db.add(
            SoarAudit(
                event_type=event_type,
                actor_type=actor_type,
                actor=actor,
                incident_id=incident_id,
                action_id=action_id,
                details=details or {},
            )
        )

    def create_incident(self, payload: NormalizedAlert) -> tuple[Incident, bool]:
        playbook = self.catalog.for_rule(payload.rule_id)
        if payload.playbook_id != playbook.id or payload.priority != playbook.priority:
            raise ValueError("n8n triage does not match the versioned playbook catalog")

        existing = self.db.scalar(
            select(Incident)
            .options(selectinload(Incident.actions))
            .where(Incident.dedup_key == payload.dedup_key)
        )
        if existing is not None:
            self.audit(
                "incident.duplicate_ignored",
                actor_type="system",
                actor="soar-controller",
                incident_id=existing.id,
                details={"dedup_key": payload.dedup_key},
            )
            return existing, False

        now = utcnow()
        incident = Incident(
            id=str(uuid.uuid4()),
            dedup_key=payload.dedup_key,
            source_alert_id=payload.source_alert_id,
            rule_id=payload.rule_id,
            rule_level=payload.rule_level,
            rule_description=payload.rule_description,
            priority=payload.priority,
            playbook_id=payload.playbook_id,
            status="triaged",
            agent_id=payload.agent_id,
            agent_name=payload.agent_name,
            source_ip=payload.source_ip,
            actor_username=payload.actor_username,
            resource_path=payload.resource_path,
            detected_at=normalized_datetime(payload.detected_at),
            received_at=normalized_datetime(payload.received_at),
            triaged_at=now,
            raw_alert=payload.raw_alert,
        )
        self.db.add(incident)
        self.db.flush()

        for definition in playbook.actions:
            target: str | None = definition.target_value
            if definition.target_field:
                target = getattr(payload, definition.target_field, None)
            status = "pending" if definition.automatic else "pending_approval"
            result: dict[str, Any] = {}
            if not target and definition.type != "collect_evidence":
                status = "not_applicable"
                result = {"reason": "target_not_available"}
            elif target and definition.type != "collect_evidence":
                policy_error = self._target_policy_error(definition.type, target)
                if policy_error:
                    status = "blocked_by_policy"
                    result = {"reason": policy_error}
            action = ResponseAction(
                id=str(uuid.uuid4()),
                incident_id=incident.id,
                action_type=definition.type,
                target=target,
                automatic=definition.automatic,
                optional=definition.optional,
                reversible=definition.reversible,
                ttl_seconds=definition.ttl_seconds,
                status=status,
                result=result,
                parameters={
                    "target_field": definition.target_field,
                    "target_value": definition.target_value,
                },
            )
            self.db.add(action)
        self.db.flush()
        self.db.refresh(incident)
        incident.status = self._status_for(incident)
        self.audit(
            "incident.created",
            actor_type="integration",
            actor="n8n-intake",
            incident_id=incident.id,
            details={
                "rule_id": incident.rule_id,
                "priority": incident.priority,
                "playbook_id": incident.playbook_id,
            },
        )
        return incident, True

    def decide(self, incident_id: str, payload: DecisionRequest) -> Incident:
        decision = payload.decision.strip().lower()
        if decision not in {"approve", "reject"}:
            raise ValueError("Decision must be approve or reject")
        incident = self._incident_for_update(incident_id)
        if incident.decision:
            if incident.decision == decision and incident.analyst == payload.analyst:
                return incident
            raise ValueError("Incident already has a different analyst decision")
        if not any(action.status == "pending_approval" for action in incident.actions):
            raise ValueError("Incident has no response actions awaiting approval")

        now = utcnow()
        incident.decision = decision
        incident.analyst = payload.analyst.strip()
        incident.decision_reason = payload.reason.strip()
        incident.decided_at = now
        for action in incident.actions:
            if action.status == "pending_approval":
                if decision == "approve":
                    action.status = "approved"
                    action.approved_at = now
                else:
                    action.status = "skipped"
                    action.result = {"reason": "analyst_rejected"}
        incident.status = "approved" if decision == "approve" else "rejected"
        self.audit(
            f"incident.{decision}d" if decision == "approve" else "incident.rejected",
            actor_type="analyst",
            actor=incident.analyst,
            incident_id=incident.id,
            details={"reason": incident.decision_reason, "nonce": payload.nonce},
        )
        return incident

    def dispatch(self, incident_id: str, scope: str) -> Incident:
        if scope not in {"automatic", "approved"}:
            raise ValueError("Dispatch scope must be automatic or approved")
        incident = self._incident_for_update(incident_id)
        expected_status = "pending" if scope == "automatic" else "approved"
        candidates = [
            action
            for action in incident.actions
            if action.status == expected_status
            and ((scope == "automatic" and action.automatic) or (scope == "approved" and not action.automatic))
        ]
        if scope == "approved" and incident.decision == "reject":
            return incident

        for action in candidates:
            self._execute_action(action, incident, actor="n8n-dispatch")
        incident.status = self._status_for(incident)
        return incident

    def retry_action(self, action_id: str, *, actor: str) -> ResponseAction:
        action = self.db.scalar(
            select(ResponseAction)
            .options(selectinload(ResponseAction.incident))
            .where(ResponseAction.id == action_id)
            .with_for_update()
        )
        if action is None:
            raise LookupError("Response action not found")
        if action.status != "failed":
            raise ValueError(f"Response action cannot be retried from state {action.status}")
        if action.attempt_count >= 5:
            raise ValueError("Response action reached the maximum of five attempts")
        if not action.automatic and action.incident.decision != "approve":
            raise ValueError("Containment retry requires an approved incident")
        self.audit(
            "action.retry_requested",
            actor_type="analyst",
            actor=actor,
            incident_id=action.incident_id,
            action_id=action.id,
            details={"attempt_count": action.attempt_count},
        )
        self._execute_action(action, action.incident, actor=actor)
        action.incident.status = self._status_for(action.incident)
        return action

    def rollback_action(self, action_id: str, *, actor: str) -> ResponseAction:
        action = self.db.scalar(
            select(ResponseAction)
            .options(selectinload(ResponseAction.incident))
            .where(ResponseAction.id == action_id)
            .with_for_update()
        )
        if action is None:
            raise LookupError("Response action not found")
        if not action.reversible:
            raise ValueError("Response action is not reversible")
        if action.status == "rolled_back":
            return action
        if action.status != "applied":
            raise ValueError(f"Response action cannot be rolled back from state {action.status}")
        result = self.executor.rollback(action)
        now = utcnow()
        action.status = "rolled_back"
        action.rolled_back_at = now
        action.result = {**(action.result or {}), "rollback": result}
        incident = action.incident
        if not any(item.status == "applied" for item in incident.actions if item.id != action.id):
            incident.status = "closed"
            incident.rolled_back_at = now
        self.audit(
            "action.rolled_back",
            actor_type="analyst" if actor != "n8n-expiration" else "orchestrator",
            actor=actor,
            incident_id=incident.id,
            action_id=action.id,
            details={"action_type": action.action_type, "target": action.target},
        )
        return action

    def expire_actions(self) -> list[ResponseAction]:
        now = utcnow()
        actions = self.db.scalars(
            select(ResponseAction)
            .where(
                ResponseAction.status == "applied",
                ResponseAction.reversible.is_(True),
                ResponseAction.expires_at.is_not(None),
                ResponseAction.expires_at <= now,
            )
            .order_by(ResponseAction.expires_at)
        ).all()
        rolled_back: list[ResponseAction] = []
        for action in actions:
            try:
                rolled_back.append(self.rollback_action(action.id, actor="n8n-expiration"))
            except (AdapterError, OSError, ValueError) as exc:
                action.result = {**(action.result or {}), "rollback_error": str(exc)}
                self.audit(
                    "action.rollback_failed",
                    actor_type="orchestrator",
                    actor="n8n-expiration",
                    incident_id=action.incident_id,
                    action_id=action.id,
                    details={"error": str(exc)},
                )
        return rolled_back

    def list_incidents(self, *, status: str | None = None, limit: int = 100) -> list[Incident]:
        query = (
            select(Incident)
            .options(selectinload(Incident.actions))
            .order_by(Incident.received_at.desc())
            .limit(max(1, min(limit, 500)))
        )
        if status:
            query = query.where(Incident.status == status)
        return list(self.db.scalars(query).all())

    def get_incident(self, incident_id: str) -> Incident:
        incident = self.db.scalar(
            select(Incident)
            .options(selectinload(Incident.actions))
            .where(Incident.id == incident_id)
        )
        if incident is None:
            raise LookupError("Incident not found")
        return incident

    def get_incident_by_dedup(self, dedup_key: str) -> Incident | None:
        return self.db.scalar(
            select(Incident)
            .options(selectinload(Incident.actions))
            .where(Incident.dedup_key == dedup_key)
        )

    def metrics(self) -> dict[str, Any]:
        incidents = self.list_incidents(limit=500)
        status_counts = Counter(incident.status for incident in incidents)
        priority_counts = Counter(incident.priority for incident in incidents)
        action_counts = Counter(action.status for incident in incidents for action in incident.actions)

        def average_seconds(values: list[float]) -> float | None:
            return round(sum(values) / len(values), 3) if values else None

        mttd = [
            (normalized_datetime(item.received_at) - normalized_datetime(item.detected_at)).total_seconds()
            for item in incidents
            if item.received_at and item.detected_at
        ]
        mtta = [
            (normalized_datetime(item.decided_at) - normalized_datetime(item.received_at)).total_seconds()
            for item in incidents
            if item.decided_at
        ]
        mttr = [
            (normalized_datetime(item.response_started_at) - normalized_datetime(item.received_at)).total_seconds()
            for item in incidents
            if item.response_started_at
        ]
        return {
            "generated_at": utcnow().isoformat(),
            "response_mode": self.settings.response_mode,
            "incident_count": len(incidents),
            "incidents_by_status": dict(sorted(status_counts.items())),
            "incidents_by_priority": dict(sorted(priority_counts.items())),
            "actions_by_status": dict(sorted(action_counts.items())),
            "mttd_seconds_average": average_seconds(mttd),
            "mtta_seconds_average": average_seconds(mtta),
            "response_start_seconds_average": average_seconds(mttr),
        }

    def record_orchestration_error(self, payload: OrchestrationErrorRequest) -> OrchestrationError:
        error = OrchestrationError(
            workflow_id=payload.workflow_id,
            workflow_name=payload.workflow_name,
            execution_id=payload.execution_id,
            error_message=payload.error_message,
            details=payload.details,
        )
        self.db.add(error)
        self.audit(
            "orchestration.error",
            actor_type="orchestrator",
            actor=payload.workflow_name or "n8n",
            details={"execution_id": payload.execution_id, "error": payload.error_message},
        )
        return error

    def serialize_incident(self, incident: Incident) -> dict[str, Any]:
        return {
            "id": incident.id,
            "dedup_key": incident.dedup_key,
            "source_alert_id": incident.source_alert_id,
            "rule_id": incident.rule_id,
            "rule_level": incident.rule_level,
            "rule_description": incident.rule_description,
            "priority": incident.priority,
            "playbook_id": incident.playbook_id,
            "status": incident.status,
            "agent_id": incident.agent_id,
            "agent_name": incident.agent_name,
            "source_ip": incident.source_ip,
            "actor_username": incident.actor_username,
            "resource_path": incident.resource_path,
            "detected_at": isoformat(incident.detected_at),
            "received_at": isoformat(incident.received_at),
            "triaged_at": isoformat(incident.triaged_at),
            "decided_at": isoformat(incident.decided_at),
            "response_started_at": isoformat(incident.response_started_at),
            "contained_at": isoformat(incident.contained_at),
            "rolled_back_at": isoformat(incident.rolled_back_at),
            "decision": incident.decision,
            "analyst": incident.analyst,
            "decision_reason": incident.decision_reason,
            "actions": [self.serialize_action(action) for action in incident.actions],
        }

    @staticmethod
    def serialize_action(action: ResponseAction) -> dict[str, Any]:
        return {
            "id": action.id,
            "incident_id": action.incident_id,
            "action_type": action.action_type,
            "target": action.target,
            "automatic": action.automatic,
            "optional": action.optional,
            "reversible": action.reversible,
            "ttl_seconds": action.ttl_seconds,
            "status": action.status,
            "attempt_count": action.attempt_count,
            "result": action.result,
            "approved_at": isoformat(action.approved_at),
            "executed_at": isoformat(action.executed_at),
            "expires_at": isoformat(action.expires_at),
            "rolled_back_at": isoformat(action.rolled_back_at),
        }

    def _incident_for_update(self, incident_id: str) -> Incident:
        incident = self.db.scalar(
            select(Incident)
            .options(selectinload(Incident.actions))
            .where(Incident.id == incident_id)
            .with_for_update()
        )
        if incident is None:
            raise LookupError("Incident not found")
        return incident

    def _execute_action(
        self,
        action: ResponseAction,
        incident: Incident,
        *,
        actor: str,
    ) -> None:
        now = utcnow()
        if not action.automatic and incident.response_started_at is None:
            incident.response_started_at = now
        action.attempt_count += 1
        try:
            status, result, expires_at = self.executor.execute(action, incident)
            action.status = status
            action.result = result
            action.executed_at = now
            action.expires_at = expires_at
            if status == "applied" and incident.contained_at is None:
                incident.contained_at = now
            self.audit(
                f"action.{status}",
                actor_type="orchestrator" if actor.startswith("n8n-") else "analyst",
                actor=actor,
                incident_id=incident.id,
                action_id=action.id,
                details={
                    "action_type": action.action_type,
                    "target": action.target,
                    "attempt_count": action.attempt_count,
                },
            )

        except (AdapterError, OSError, ValueError) as exc:
            action.status = "failed"
            action.executed_at = now
            action.result = {"error": str(exc)}
            self.audit(
                "action.failed",
                actor_type="orchestrator" if actor.startswith("n8n-") else "analyst",
                actor=actor,
                incident_id=incident.id,
                action_id=action.id,
                details={
                    "action_type": action.action_type,
                    "error": str(exc),
                    "attempt_count": action.attempt_count,
                },
            )

    def _target_policy_error(self, action_type: str, target: str) -> str | None:
        if action_type == "app_ip_block":
            try:
                address = ipaddress.ip_address(target)
            except ValueError:
                return "invalid_ip_address"
            if (
                address.version != 4
                or address.is_loopback
                or address.is_multicast
                or address.is_unspecified
            ):
                return "unsupported_ip_address"
            if str(address) in self.settings.protected_ips:
                return "protected_ip_address"
            if not any(
                address in network for network in self.settings.allowed_containment_networks
            ):
                return "ip_outside_allowed_cidrs"
        elif action_type == "app_account_lock":
            username = target.strip().lower()
            if not USERNAME_PATTERN.fullmatch(username):
                return "invalid_account_name"
            if username in self.settings.protected_users:
                return "protected_account"
        elif action_type == "quality_guard" and target != "quality-release":
            return "unsupported_quality_guard_target"
        return None

    @staticmethod
    def _status_for(incident: Incident) -> str:
        statuses = {action.status for action in incident.actions}
        if "failed" in statuses:
            return "failed"
        if incident.decision == "reject":
            return "rejected"
        if "pending_approval" in statuses:
            return "pending_approval"
        if "approved" in statuses:
            return "approved"
        if "applied" in statuses:
            return "contained"
        if "simulated" in statuses:
            return "simulated"
        if "pending" in statuses:
            return "triaged"
        return "closed"
