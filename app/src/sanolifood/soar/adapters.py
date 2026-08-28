import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sanolifood.soar.config import SoarSettings
from sanolifood.soar.models import Incident, ResponseAction


class AdapterError(RuntimeError):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def request_json(
    method: str,
    url: str,
    *,
    token: str,
    payload: dict[str, Any] | None,
    timeout: int,
) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    if payload is not None:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            response_body = response.read(1_048_576)
    except HTTPError as exc:
        error_body = exc.read(4096).decode("utf-8", errors="replace")
        raise AdapterError(f"Business control API returned HTTP {exc.code}: {error_body}") from exc
    except (URLError, TimeoutError) as exc:
        raise AdapterError(f"Business control API is unavailable: {exc}") from exc
    try:
        return json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdapterError("Business control API returned an invalid JSON response") from exc


class ResponseExecutor:
    def __init__(self, settings: SoarSettings):
        self.settings = settings

    def execute(self, action: ResponseAction, incident: Incident) -> tuple[str, dict[str, Any], datetime | None]:
        if action.action_type == "collect_evidence":
            result = self._collect_evidence(action, incident)
            return "completed", result, None

        if not action.target:
            return "not_applicable", {"reason": "target_not_available"}, None

        if self.settings.response_mode == "dry-run":
            return (
                "simulated",
                {
                    "mode": "dry-run",
                    "would_apply": action.action_type,
                    "target": action.target,
                    "ttl_seconds": action.ttl_seconds,
                },
                None,
            )

        expires_at = utcnow() + timedelta(seconds=int(action.ttl_seconds or 0))
        payload = {
            "action_id": action.id,
            "incident_id": incident.id,
            "control_type": action.action_type,
            "target": action.target,
            "ttl_seconds": action.ttl_seconds,
            "reason": f"SOAR playbook {incident.playbook_id}: {incident.rule_description}"[:500],
            "details": {
                "rule_id": incident.rule_id,
                "priority": incident.priority,
                "agent_name": incident.agent_name,
            },
        }
        result = request_json(
            "POST",
            f"{self.settings.soar_app_url.rstrip('/')}/internal/soar/controls",
            token=self.settings.soar_internal_token.get_secret_value(),
            payload=payload,
            timeout=self.settings.soar_http_timeout_seconds,
        )
        control = result.get("control", {})
        if control.get("expires_at"):
            expires_at = datetime.fromisoformat(control["expires_at"])
        return "applied", {"mode": "live", "business_control": result}, expires_at

    def rollback(self, action: ResponseAction) -> dict[str, Any]:
        if action.status != "applied":
            return {"changed": False, "reason": f"action_status_{action.status}"}
        return request_json(
            "POST",
            f"{self.settings.soar_app_url.rstrip('/')}/internal/soar/controls/{action.id}/rollback",
            token=self.settings.soar_internal_token.get_secret_value(),
            payload=None,
            timeout=self.settings.soar_http_timeout_seconds,
        )

    def _collect_evidence(self, action: ResponseAction, incident: Incident) -> dict[str, Any]:
        evidence_root = Path(self.settings.soar_evidence_dir)
        incident_dir = evidence_root / "incidents" / incident.id
        incident_dir.mkdir(parents=True, exist_ok=True, mode=0o750)
        evidence_path = incident_dir / f"{action.id}.json"
        evidence = {
            "schema_version": 1,
            "collected_at": utcnow().isoformat(),
            "incident": {
                "id": incident.id,
                "dedup_key": incident.dedup_key,
                "rule_id": incident.rule_id,
                "rule_level": incident.rule_level,
                "rule_description": incident.rule_description,
                "priority": incident.priority,
                "playbook_id": incident.playbook_id,
                "agent_id": incident.agent_id,
                "agent_name": incident.agent_name,
                "source_ip": incident.source_ip,
                "actor_username": incident.actor_username,
                "resource_path": incident.resource_path,
                "detected_at": incident.detected_at.isoformat(),
                "received_at": incident.received_at.isoformat(),
            },
            "raw_alert": incident.raw_alert,
        }
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=incident_dir, delete=False, prefix=".evidence-"
        ) as temporary_file:
            json.dump(evidence, temporary_file, sort_keys=True, indent=2)
            temporary_file.write("\n")
            temporary_path = Path(temporary_file.name)
        os.chmod(temporary_path, 0o640)
        os.replace(temporary_path, evidence_path)
        return {"evidence_path": str(evidence_path), "bytes": evidence_path.stat().st_size}
