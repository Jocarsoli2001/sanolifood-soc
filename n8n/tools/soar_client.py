#!/usr/bin/env python3
"""Operator CLI for the local SanoliFood SOAR control plane."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


PROJECT_DIR = Path(__file__).resolve().parents[2]
RUNTIME_ENV = PROJECT_DIR / "n8n" / "runtime" / ".env"


class ClientError(RuntimeError):
    pass


def load_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise ClientError(f"Runtime configuration not found: {path}")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key] = value.strip().strip('"').strip("'")
    return values


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class SoarClient:
    def __init__(self, env: dict[str, str]):
        self.env = env
        self.controller_url = f"http://127.0.0.1:{env.get('SOAR_CONTROLLER_PORT', '5680')}"
        self.n8n_url = f"http://127.0.0.1:{env.get('SOAR_PUBLIC_PORT', '5678')}"
        self.internal_token = self.required("SOAR_INTERNAL_TOKEN")

    def required(self, key: str) -> str:
        value = self.env.get(key, "")
        if not value:
            raise ClientError(f"Missing {key} in {RUNTIME_ENV}")
        return value

    def request(
        self,
        method: str,
        url: str,
        *,
        payload: dict[str, Any] | None = None,
        internal_auth: bool = False,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        request_headers = {"Accept": "application/json", **(headers or {})}
        if internal_auth:
            request_headers["Authorization"] = f"Bearer {self.internal_token}"
        data = None
        if payload is not None:
            data = canonical_json(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=request_headers, method=method)
        try:
            with urlopen(request, timeout=20) as response:
                body = response.read(4_194_304)
        except HTTPError as exc:
            error_body = exc.read(16_384).decode("utf-8", errors="replace")
            raise ClientError(f"HTTP {exc.code} from {url}: {error_body}") from exc
        except (URLError, TimeoutError) as exc:
            raise ClientError(f"Unable to reach {url}: {exc}") from exc
        try:
            return json.loads(body.decode("utf-8")) if body else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ClientError(f"Invalid JSON response from {url}") from exc

    def signed_webhook(self, path: str, payload: dict[str, Any], secret_key: str) -> dict[str, Any]:
        timestamp = str(int(time.time()))
        secret = self.required(secret_key).encode("utf-8")
        signature = "sha256=" + hmac.new(
            secret,
            f"{timestamp}.{canonical_json(payload)}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return self.request(
            "POST",
            f"{self.n8n_url}/webhook/{path}",
            payload=payload,
            headers={
                "X-SanoliFood-Timestamp": timestamp,
                "X-SanoliFood-Signature": signature,
            },
        )

    def list_incidents(self, status: str | None = None, limit: int = 100) -> dict[str, Any]:
        query = {"limit": str(limit)}
        if status:
            query["status"] = status
        return self.request(
            "GET",
            f"{self.controller_url}/api/v1/incidents?{urlencode(query)}",
            internal_auth=True,
        )

    def get_incident(self, incident_id: str) -> dict[str, Any]:
        return self.request(
            "GET",
            f"{self.controller_url}/api/v1/incidents/{quote(incident_id)}",
            internal_auth=True,
        )["incident"]

    def decide(self, incident_id: str, decision: str, analyst: str, reason: str) -> dict[str, Any]:
        envelope = {
            "schema_version": 1,
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "nonce": str(uuid.uuid4()),
            "incident_id": incident_id,
            "decision": decision,
            "analyst": analyst,
            "reason": reason,
        }
        return self.signed_webhook(
            "sanolifood/analyst-decision", envelope, "SOAR_ANALYST_SECRET"
        )

    def rollback(self, action_id: str, analyst: str) -> dict[str, Any]:
        return self.request(
            "POST",
            f"{self.controller_url}/api/v1/actions/{quote(action_id)}/rollback?actor={quote(analyst)}",
            internal_auth=True,
        )

    def retry(self, action_id: str, analyst: str) -> dict[str, Any]:
        return self.request(
            "POST",
            f"{self.controller_url}/api/v1/actions/{quote(action_id)}/retry?actor={quote(analyst)}",
            internal_auth=True,
        )

    def validate(self) -> dict[str, Any]:
        validation_id = str(uuid.uuid4())
        alert = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "id": f"soar-validation-{validation_id}",
            "rule": {"id": "110130", "level": 12, "description": "SanoliFood controlled SQLi validation"},
            "agent": {"id": "000", "name": "soc-validation"},
            "data": {"src_ip": "10.20.0.50", "http": {"url": "/validation?id=1%27"}},
            "location": "suricata",
        }
        envelope = {
            "schema_version": 1,
            "integration": "sanolifood-wazuh",
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "nonce": str(uuid.uuid4()),
            "alert_json": canonical_json(alert),
        }
        intake = self.signed_webhook(
            "sanolifood/wazuh-alert", envelope, "SOAR_WEBHOOK_SECRET"
        )
        incident = intake.get("incident") or {}
        incident_id = incident.get("id")
        if not incident_id:
            raise ClientError("The intake workflow did not return an incident identifier")
        evidence_actions = [a for a in incident.get("actions", []) if a["action_type"] == "collect_evidence"]
        if not evidence_actions or evidence_actions[0]["status"] != "completed":
            raise ClientError("Automatic evidence collection did not complete")

        decision_result = self.decide(
            incident_id,
            "approve",
            "soc.validation",
            "Controlled end-to-end validation of the SOAR response path",
        )
        decided = decision_result.get("incident") or self.get_incident(incident_id)
        containment = [a for a in decided.get("actions", []) if a["action_type"] == "app_ip_block"]
        if not containment:
            raise ClientError("The SQLi playbook did not create an IP containment action")
        expected_status = "applied" if self.env.get("SOAR_RESPONSE_MODE") == "live" else "simulated"
        if containment[0]["status"] != expected_status:
            raise ClientError(
                f"Containment status is {containment[0]['status']}; expected {expected_status}"
            )
        rollback_result = None
        if expected_status == "applied":
            rollback_result = self.rollback(containment[0]["id"], "soc.validation")
            if rollback_result.get("action", {}).get("status") != "rolled_back":
                raise ClientError("Live containment rollback did not complete")
        return {
            "status": "PASS",
            "incident_id": incident_id,
            "response_mode": self.env.get("SOAR_RESPONSE_MODE", "dry-run"),
            "evidence_status": evidence_actions[0]["status"],
            "containment_status": containment[0]["status"],
            "rollback_status": rollback_result.get("action", {}).get("status") if rollback_result else "not-required",
        }


def print_incidents(payload: dict[str, Any]) -> None:
    items = payload.get("items", [])
    if not items:
        print("No SOAR incidents found.")
        return
    print(f"{'INCIDENT':36}  {'RULE':6}  {'PRIORITY':8}  {'STATUS':18}  PLAYBOOK")
    for item in items:
        print(
            f"{item['id']:36}  {item['rule_id']:<6}  {item['priority']:<8}  "
            f"{item['status']:<18}  {item['playbook_id']}"
        )


def export_evidence(client: SoarClient, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    documents = {
        "incidents.json": client.list_incidents(limit=500),
        "metrics-summary.json": client.request(
            "GET", f"{client.controller_url}/api/v1/metrics/summary", internal_auth=True
        ),
        "capabilities.json": client.request(
            "GET", f"{client.controller_url}/api/v1/capabilities", internal_auth=True
        ),
        "audit-log.json": client.request(
            "GET", f"{client.controller_url}/api/v1/audit?limit=1000", internal_auth=True
        ),
        "orchestration-errors.json": client.request(
            "GET", f"{client.controller_url}/api/v1/orchestration-errors?limit=500", internal_auth=True
        ),
    }
    for filename, payload in documents.items():
        path = destination / filename
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(f"SOAR API evidence exported to {destination}")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    subparsers = root.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--status")
    list_parser.add_argument("--limit", type=int, default=100)

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("incident_id")

    for decision in ("approve", "reject"):
        decision_parser = subparsers.add_parser(decision)
        decision_parser.add_argument("incident_id")
        decision_parser.add_argument("--analyst", required=True)
        decision_parser.add_argument("--reason", required=True)

    rollback_parser = subparsers.add_parser("rollback")
    rollback_parser.add_argument("action_id")
    rollback_parser.add_argument("--analyst", required=True)

    retry_parser = subparsers.add_parser("retry")
    retry_parser.add_argument("action_id")
    retry_parser.add_argument("--analyst", required=True)

    subparsers.add_parser("metrics")
    subparsers.add_parser("capabilities")
    subparsers.add_parser("validate")

    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("destination", type=Path)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        client = SoarClient(load_env(RUNTIME_ENV))
        if args.command == "list":
            print_incidents(client.list_incidents(args.status, args.limit))
        elif args.command == "show":
            print(json.dumps(client.get_incident(args.incident_id), indent=2, sort_keys=True))
        elif args.command in {"approve", "reject"}:
            result = client.decide(args.incident_id, args.command, args.analyst, args.reason)
            print(json.dumps(result, indent=2, sort_keys=True))
        elif args.command == "rollback":
            print(json.dumps(client.rollback(args.action_id, args.analyst), indent=2, sort_keys=True))
        elif args.command == "retry":
            print(json.dumps(client.retry(args.action_id, args.analyst), indent=2, sort_keys=True))
        elif args.command == "metrics":
            print(
                json.dumps(
                    client.request(
                        "GET", f"{client.controller_url}/api/v1/metrics/summary", internal_auth=True
                    ),
                    indent=2,
                    sort_keys=True,
                )
            )
        elif args.command == "capabilities":
            print(
                json.dumps(
                    client.request(
                        "GET", f"{client.controller_url}/api/v1/capabilities", internal_auth=True
                    ),
                    indent=2,
                    sort_keys=True,
                )
            )
        elif args.command == "validate":
            print(json.dumps(client.validate(), indent=2, sort_keys=True))
        elif args.command == "export":
            export_evidence(client, args.destination)
        return 0
    except ClientError as exc:
        print(f"SOAR client error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
