#!/usr/bin/env python3
"""Run and measure attributable SanoliFood v0.8 laboratory scenarios."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import hmac
import json
import math
import re
import statistics
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import ProxyHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "evaluation" / "config" / "scenarios.json"
RESULTS_DIR = ROOT / "evaluation" / "results"
RUNS_DIR = RESULTS_DIR / "runs"
SOAR_ENV = ROOT / "n8n" / "runtime" / ".env"
INTEGRATION_STATE = ROOT / "n8n" / "runtime" / "integration.state"
RUN_ID_RE = re.compile(r"^SF-EVAL-SCN-\d{3}-\d{8}T\d{6}Z-[0-9a-f]{8}$")
KALI_SSH_RE = re.compile(r"^[A-Za-z0-9._-]+@10\.20\.0\.30$")
WINDOWS_SSH_RE = re.compile(r"^[A-Za-z0-9._-]+@10\.20\.0\.20$")


class EvaluationError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def seconds_between(later: str | None, earlier: str | None) -> float | None:
    later_dt = parse_time(later)
    earlier_dt = parse_time(earlier)
    if later_dt is None or earlier_dt is None:
        return None
    return round(max(0.0, (later_dt - earlier_dt).total_seconds()), 3)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise EvaluationError(f"runtime configuration not found: {path}")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key] = value.strip().strip('"').strip("'")
    return values


def catalog() -> dict[str, Any]:
    return read_json(CATALOG_PATH)


def scenario_by_id(scenario_id: str) -> dict[str, Any]:
    for scenario in catalog()["scenarios"]:
        if scenario["id"] == scenario_id:
            return scenario
    raise EvaluationError(f"unknown scenario: {scenario_id}")


def make_run_id(scenario_id: str) -> str:
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    return f"SF-EVAL-{scenario_id}-{stamp}-{uuid.uuid4().hex[:8]}"


def run_dir(run_id: str) -> Path:
    if not RUN_ID_RE.fullmatch(run_id):
        raise EvaluationError("invalid evaluation run identifier")
    return RUNS_DIR / run_id


def command(
    argv: list[str],
    *,
    timeout: int = 180,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            argv,
            cwd=ROOT,
            input=input_text,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EvaluationError(f"command failed to start: {argv[0]}: {exc}") from exc
    if check and completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()[-4000:]
        raise EvaluationError(f"{argv[0]} exited with {completed.returncode}: {detail}")
    return completed


class SoarClient:
    def __init__(self, env: dict[str, str]):
        self.env = env
        self.controller = f"http://127.0.0.1:{env.get('SOAR_CONTROLLER_PORT', '5680')}"
        self.n8n = f"http://127.0.0.1:{env.get('SOAR_PUBLIC_PORT', '5678')}"
        self.token = self.required("SOAR_INTERNAL_TOKEN")
        self.opener = build_opener(ProxyHandler({}))

    def required(self, key: str) -> str:
        value = self.env.get(key, "")
        if not value:
            raise EvaluationError(f"missing {key} in {SOAR_ENV}")
        return value

    @staticmethod
    def canonical(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def request(
        self,
        method: str,
        url: str,
        *,
        payload: dict[str, Any] | None = None,
        internal: bool = False,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        request_headers = {"Accept": "application/json", **(headers or {})}
        if internal:
            request_headers["Authorization"] = f"Bearer {self.token}"
        data = None
        if payload is not None:
            data = self.canonical(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=request_headers, method=method)
        try:
            with self.opener.open(request, timeout=20) as response:
                body = response.read(4_194_304)
        except HTTPError as exc:
            detail = exc.read(16_384).decode("utf-8", errors="replace")
            raise EvaluationError(f"HTTP {exc.code} from SOAR: {detail}") from exc
        except (URLError, TimeoutError) as exc:
            raise EvaluationError(f"SOAR endpoint unavailable: {exc}") from exc
        try:
            return json.loads(body.decode("utf-8")) if body else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EvaluationError("SOAR returned invalid JSON") from exc

    def incidents(self, limit: int = 500) -> list[dict[str, Any]]:
        payload = self.request(
            "GET",
            f"{self.controller}/api/v1/incidents?{urlencode({'limit': limit})}",
            internal=True,
        )
        return payload.get("items", [])

    def incident(self, incident_id: str) -> dict[str, Any]:
        payload = self.request(
            "GET",
            f"{self.controller}/api/v1/incidents/{quote(incident_id)}",
            internal=True,
        )
        return payload["incident"]

    def decide(self, incident_id: str, decision: str, analyst: str, reason: str) -> dict[str, Any]:
        envelope = {
            "schema_version": 1,
            "requested_at": iso(utc_now()),
            "nonce": str(uuid.uuid4()),
            "incident_id": incident_id,
            "decision": decision,
            "analyst": analyst,
            "reason": reason,
        }
        timestamp = str(int(time.time()))
        message = f"{timestamp}.{self.canonical(envelope)}".encode("utf-8")
        signature = "sha256=" + hmac.new(
            self.required("SOAR_ANALYST_SECRET").encode("utf-8"),
            message,
            hashlib.sha256,
        ).hexdigest()
        return self.request(
            "POST",
            f"{self.n8n}/webhook/sanolifood/analyst-decision",
            payload=envelope,
            headers={
                "X-SanoliFood-Timestamp": timestamp,
                "X-SanoliFood-Signature": signature,
            },
        )

    def rollback(self, action_id: str, analyst: str) -> dict[str, Any]:
        return self.request(
            "POST",
            f"{self.controller}/api/v1/actions/{quote(action_id)}/rollback?actor={quote(analyst)}",
            internal=True,
        )


def response_mode(env: dict[str, str]) -> str:
    mode = env.get("SOAR_RESPONSE_MODE", "")
    if mode not in {"dry-run", "live"}:
        raise EvaluationError(f"unsupported SOAR response mode: {mode or 'missing'}")
    return mode


def verify_integration() -> None:
    if not INTEGRATION_STATE.is_file() or INTEGRATION_STATE.read_text(encoding="utf-8").strip() != "enabled":
        raise EvaluationError("Wazuh forwarding is disabled; run make soar-install-workflows")


def save_resource_snapshot(destination: Path) -> None:
    completed = command(
        ["docker", "stats", "--no-stream", "--format", "{{json .}}"],
        timeout=30,
        check=False,
    )
    destination.write_text(completed.stdout + completed.stderr, encoding="utf-8")


def dispatch(
    scenario: dict[str, Any],
    run_id: str,
    marker: str,
    *,
    kali_ssh: str,
    windows_ssh: str,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    source = scenario["source"]
    stimulus = scenario["stimulus"]
    if source == "kali":
        if not KALI_SSH_RE.fullmatch(kali_ssh):
            raise EvaluationError("KALI_SSH must be usuario@10.20.0.30")
        script = (ROOT / "scenarios" / "kali" / "sanolifood_lab.py").read_text(
            encoding="utf-8"
        )
        return command(
            [
                "ssh",
                "-o",
                "ConnectTimeout=8",
                kali_ssh,
                "python3",
                "-",
                stimulus,
                run_id,
                marker,
            ],
            timeout=timeout,
            input_text=script,
        )
    if source == "business":
        return command(
            [sys.executable, str(ROOT / "scenarios" / "business" / "sanolifood_business.py"), stimulus, run_id],
            timeout=timeout,
        )
    if source == "linux_endpoint":
        return command(
            ["sudo", str(ROOT / "endpoints" / "scripts" / "validate-linux.sh"), "--run-id", run_id],
            timeout=timeout,
        )
    if source == "windows_endpoint":
        if not WINDOWS_SSH_RE.fullmatch(windows_ssh):
            raise EvaluationError("WINDOWS_SSH must be usuario@10.20.0.20")
        powershell = (
            "$p = Join-Path $env:USERPROFILE 'SanoliFood-Endpoint\\Test-SanoliFoodEndpoint.ps1'; "
            f"if (-not (Test-Path -LiteralPath $p)) {{ throw 'Endpoint script not staged' }}; & $p -RunId '{run_id}'"
        )
        encoded = base64.b64encode(powershell.encode("utf-16le")).decode("ascii")
        return command(
            [
                "ssh",
                "-o",
                "ConnectTimeout=8",
                windows_ssh,
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                encoded,
            ],
            timeout=timeout,
        )
    raise EvaluationError(f"unsupported scenario source: {source}")


def recent_wazuh_alerts() -> list[dict[str, Any]]:
    completed = command(
        [
            "docker",
            "compose",
            "--env-file",
            "wazuh/runtime/.env",
            "-f",
            "wazuh/compose.yaml",
            "exec",
            "-T",
            "wazuh.manager",
            "tail",
            "-n",
            "5000",
            "/var/ossec/logs/alerts/alerts.json",
        ],
        timeout=30,
    )
    alerts: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            alerts.append(item)
    return alerts


def find_alert(
    scenario: dict[str, Any], marker: str, started: datetime
) -> dict[str, Any] | None:
    expected_rule = str(scenario["expected_rule_id"])
    earliest = started - timedelta(seconds=5)
    for alert in reversed(recent_wazuh_alerts()):
        if str(alert.get("rule", {}).get("id")) != expected_rule:
            continue
        alert_time = parse_time(alert.get("timestamp"))
        if alert_time is None or alert_time < earliest:
            continue
        if marker not in json.dumps(alert, ensure_ascii=False, sort_keys=True):
            continue
        expected_agent = scenario.get("expected_agent_name")
        if expected_agent and alert.get("agent", {}).get("name") != expected_agent:
            continue
        return alert
    return None


def poll_alert(
    scenario: dict[str, Any], marker: str, started: datetime, timeout: int
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            alert = find_alert(scenario, marker, started)
            if alert is not None:
                return alert
        except EvaluationError as exc:
            last_error = exc
        time.sleep(2)
    detail = f"; last collector error: {last_error}" if last_error else ""
    raise EvaluationError(
        f"rule {scenario['expected_rule_id']} with the current marker was not observed{detail}"
    )


def poll_incident(client: SoarClient, source_alert_id: str, timeout: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for item in client.incidents():
            if str(item.get("source_alert_id")) == source_alert_id:
                incident = client.incident(item["id"])
                evidence = [
                    action
                    for action in incident.get("actions", [])
                    if action.get("action_type") == "collect_evidence"
                ]
                if evidence and evidence[0].get("status") == "completed":
                    return incident
        time.sleep(2)
    raise EvaluationError("n8n did not create and enrich the attributable incident")


def metrics(result: dict[str, Any], incident: dict[str, Any]) -> dict[str, float | None]:
    values: dict[str, float | None] = {
        "stimulus_to_wazuh_seconds": seconds_between(
            result.get("wazuh_detected_at"), result.get("stimulus_started_at")
        ),
        "wazuh_to_soar_seconds": seconds_between(
            incident.get("received_at"), result.get("wazuh_detected_at")
        ),
        "soar_triage_seconds": seconds_between(
            incident.get("triaged_at"), incident.get("received_at")
        ),
        "end_to_end_triage_seconds": seconds_between(
            incident.get("triaged_at"), result.get("stimulus_started_at")
        ),
        "analyst_decision_seconds": seconds_between(
            incident.get("decided_at"), incident.get("triaged_at")
        ),
        "decision_to_response_seconds": seconds_between(
            incident.get("response_started_at"), incident.get("decided_at")
        ),
        "decision_to_containment_seconds": seconds_between(
            incident.get("contained_at"), incident.get("decided_at")
        ),
        "containment_to_rollback_seconds": seconds_between(
            incident.get("rolled_back_at"), incident.get("contained_at")
        ),
    }
    return values


def validate_incident(
    scenario: dict[str, Any], incident: dict[str, Any], *, final: bool
) -> list[str]:
    checks: list[str] = []
    if incident.get("rule_id") != scenario["expected_rule_id"]:
        raise EvaluationError("SOAR incident rule does not match the scenario")
    checks.append("rule_id")
    if incident.get("playbook_id") != scenario["expected_playbook_id"]:
        raise EvaluationError("SOAR selected an unexpected playbook")
    checks.append("playbook_id")
    actions = {action.get("action_type"): action for action in incident.get("actions", [])}
    missing = set(scenario["expected_actions"]) - set(actions)
    if missing:
        raise EvaluationError(f"SOAR actions missing: {', '.join(sorted(missing))}")
    checks.append("action_catalog")
    if actions["collect_evidence"].get("status") != "completed":
        raise EvaluationError("automatic evidence collection did not complete")
    checks.append("automatic_evidence")
    expected_policy = scenario.get("expected_policy_status")
    if expected_policy:
        non_evidence = [action for key, action in actions.items() if key != "collect_evidence"]
        if not non_evidence or any(action.get("status") != expected_policy for action in non_evidence):
            raise EvaluationError(f"expected policy state {expected_policy} was not enforced")
        checks.append("protected_target_policy")
    if final and scenario.get("requires_decision") and not incident.get("decision"):
        raise EvaluationError("scenario still requires an analyst decision")
    return checks


def save_incident(destination: Path, incident: dict[str, Any]) -> None:
    write_json(destination / "soar-incident.json", incident)


def update_result(
    destination: Path,
    result: dict[str, Any],
    incident: dict[str, Any],
    scenario: dict[str, Any],
    *,
    final: bool,
) -> dict[str, Any]:
    result["incident_id"] = incident["id"]
    result["incident_status"] = incident.get("status")
    result["decision"] = incident.get("decision")
    result["actions"] = [
        {
            "id": item.get("id"),
            "action_type": item.get("action_type"),
            "status": item.get("status"),
            "reversible": item.get("reversible"),
        }
        for item in incident.get("actions", [])
    ]
    result["validations"] = validate_incident(scenario, incident, final=final)
    result["metrics"] = metrics(result, incident)
    if final or not scenario.get("requires_decision"):
        result["status"] = "PASS"
    else:
        result["status"] = "PASS_PENDING_DECISION"
    result["updated_at"] = iso(utc_now())
    save_incident(destination, incident)
    write_json(destination / "result.json", result)
    return result


def run_scenario(args: argparse.Namespace) -> int:
    scenario = scenario_by_id(args.scenario)
    policy = catalog()["lab_policy"]
    timeout = args.timeout or int(policy["default_timeout_seconds"])
    if not 30 <= timeout <= 600:
        raise EvaluationError("timeout must be between 30 and 600 seconds")
    env = load_env(SOAR_ENV)
    mode = response_mode(env)
    if mode == "live" and not args.allow_live:
        raise EvaluationError("SOAR is live; use --allow-live only for a supervised run")
    verify_integration()

    run_id = make_run_id(scenario["id"])
    marker = f"eval.{run_id[-8:]}" if scenario["id"] == "SCN-002" else run_id
    destination = run_dir(run_id)
    destination.mkdir(parents=True, exist_ok=False)
    started = utc_now()
    result: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "scenario_id": scenario["id"],
        "scenario_name": scenario["name"],
        "source": scenario["source"],
        "stimulus": scenario["stimulus"],
        "marker": marker,
        "response_mode": mode,
        "status": "RUNNING",
        "stimulus_started_at": iso(started),
    }
    write_json(destination / "scenario.json", scenario)
    write_json(destination / "result.json", result)
    save_resource_snapshot(destination / "resources-before.jsonl")
    try:
        completed = dispatch(
            scenario,
            run_id,
            marker,
            kali_ssh=args.kali_ssh or "",
            windows_ssh=args.windows_ssh or "",
            timeout=timeout,
        )
        (destination / "stimulus.txt").write_text(
            completed.stdout + completed.stderr, encoding="utf-8"
        )
        result["stimulus_completed_at"] = iso(utc_now())
        receipt = None
        for line in reversed(completed.stdout.splitlines()):
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                receipt = candidate
                break
        if receipt is not None:
            write_json(destination / "stimulus-receipt.json", receipt)
            if receipt.get("request_count", 0) > scenario["request_budget"]:
                raise EvaluationError("stimulus exceeded its catalog request budget")

        alert = poll_alert(scenario, marker, started, timeout)
        write_json(destination / "wazuh-alert.json", alert)
        result["wazuh_alert_id"] = str(alert.get("id", ""))
        result["wazuh_detected_at"] = alert.get("timestamp")
        if not result["wazuh_alert_id"]:
            raise EvaluationError("Wazuh alert did not contain an identifier")

        client = SoarClient(env)
        incident = poll_incident(client, result["wazuh_alert_id"], timeout)
        update_result(destination, result, incident, scenario, final=False)
        save_resource_snapshot(destination / "resources-after.jsonl")
    except Exception as exc:
        result["status"] = "FAIL"
        result["error"] = str(exc)
        result["updated_at"] = iso(utc_now())
        write_json(destination / "result.json", result)
        save_resource_snapshot(destination / "resources-after.jsonl")
        if isinstance(exc, EvaluationError):
            raise
        raise EvaluationError(str(exc)) from exc

    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] == "PASS_PENDING_DECISION":
        print(
            "\nNext: make eval-decide "
            f"RUN_ID={run_id} DECISION=approve ANALYST=your.name "
            "REASON='Documented laboratory decision'"
        )
    return 0


def locate_result(run_id: str) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    destination = run_dir(run_id)
    result_path = destination / "result.json"
    if not result_path.is_file():
        raise EvaluationError(f"run not found: {run_id}")
    result = read_json(result_path)
    return destination, result, scenario_by_id(result["scenario_id"])


def decide_run(args: argparse.Namespace) -> int:
    if not re.fullmatch(r"[A-Za-z0-9._-]{3,80}", args.analyst):
        raise EvaluationError("analyst name must be 3-80 safe characters")
    if not 12 <= len(args.reason.strip()) <= 500:
        raise EvaluationError("decision reason must be 12-500 characters")
    destination, result, scenario = locate_result(args.run_id)
    if not scenario.get("requires_decision"):
        raise EvaluationError("this scenario has no pending analyst decision")
    env = load_env(SOAR_ENV)
    mode = response_mode(env)
    if result.get("response_mode") != mode:
        raise EvaluationError(
            "SOAR response mode changed after the stimulus; restore the original mode or rerun the scenario"
        )
    if mode == "live" and not args.allow_live:
        raise EvaluationError("SOAR is live; repeat with explicit live confirmation")
    client = SoarClient(env)
    decision_error: EvaluationError | None = None
    try:
        client.decide(result["incident_id"], args.decision, args.analyst, args.reason.strip())
    except EvaluationError as exc:
        decision_error = exc
    incident = client.incident(result["incident_id"])
    rollback_receipts: list[dict[str, Any]] = []
    rollback_errors: list[str] = []
    if mode == "live" and args.decision == "approve":
        for action in incident.get("actions", []):
            if action.get("reversible") and action.get("status") == "applied":
                try:
                    rollback_receipts.append(client.rollback(action["id"], args.analyst))
                except EvaluationError as exc:
                    rollback_errors.append(f"{action['id']}: {exc}")
        incident = client.incident(result["incident_id"])
    if rollback_receipts:
        write_json(destination / "rollback-receipts.json", rollback_receipts)
    if rollback_errors:
        write_json(destination / "rollback-errors.json", rollback_errors)
    save_incident(destination, incident)
    if decision_error is not None:
        raise decision_error
    if rollback_errors:
        raise EvaluationError(
            "one or more live controls could not be rolled back immediately; "
            "inspect rollback-errors.json and use make soar-rollback"
        )
    response_actions = [
        action
        for action in incident.get("actions", [])
        if not action.get("automatic") and action.get("status") != "blocked_by_policy"
    ]
    if args.decision == "reject" and any(
        action.get("status") != "skipped" for action in response_actions
    ):
        raise EvaluationError("rejected actions did not enter the skipped state")
    if args.decision == "approve" and mode == "dry-run" and any(
        action.get("status") != "simulated" for action in response_actions
    ):
        raise EvaluationError("approved dry-run actions were not simulated")
    if args.decision == "approve" and mode == "live" and any(
        action.get("reversible") and action.get("status") != "rolled_back"
        for action in response_actions
    ):
        raise EvaluationError("an approved live action was not rolled back")
    update_result(destination, result, incident, scenario, final=True)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def refresh_run(args: argparse.Namespace) -> int:
    destination, result, scenario = locate_result(args.run_id)
    client = SoarClient(load_env(SOAR_ENV))
    incident = client.incident(result["incident_id"])
    final = bool(incident.get("decision")) or not scenario.get("requires_decision")
    update_result(destination, result, incident, scenario, final=final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def percentile(values: list[float], percent: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percent * len(ordered)) - 1)
    return round(ordered[index], 3)


def build_summary() -> dict[str, Any]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    metric_names = [
        "stimulus_to_wazuh_seconds",
        "wazuh_to_soar_seconds",
        "soar_triage_seconds",
        "end_to_end_triage_seconds",
        "analyst_decision_seconds",
        "decision_to_response_seconds",
        "decision_to_containment_seconds",
        "containment_to_rollback_seconds",
    ]
    for result_path in sorted(RUNS_DIR.glob("*/result.json")):
        item = read_json(result_path)
        row = {
            "run_id": item.get("run_id"),
            "scenario_id": item.get("scenario_id"),
            "status": item.get("status"),
            "response_mode": item.get("response_mode"),
            "wazuh_alert_id": item.get("wazuh_alert_id"),
            "incident_id": item.get("incident_id"),
            "incident_status": item.get("incident_status"),
            "decision": item.get("decision"),
            "simulated_actions": sum(
                1 for action in item.get("actions", []) if action.get("status") == "simulated"
            ),
            "rolled_back_actions": sum(
                1 for action in item.get("actions", []) if action.get("status") == "rolled_back"
            ),
        }
        for name in metric_names:
            row[name] = item.get("metrics", {}).get(name)
        rows.append(row)

    columns = [
        "run_id",
        "scenario_id",
        "status",
        "response_mode",
        "wazuh_alert_id",
        "incident_id",
        "incident_status",
        "decision",
        "simulated_actions",
        "rolled_back_actions",
        *metric_names,
    ]
    with (RESULTS_DIR / "results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    metric_summary: dict[str, dict[str, float | int | None]] = {}
    for name in metric_names:
        values = [float(row[name]) for row in rows if isinstance(row.get(name), (int, float))]
        metric_summary[name] = {
            "samples": len(values),
            "mean": round(statistics.fmean(values), 3) if values else None,
            "median": round(statistics.median(values), 3) if values else None,
            "p95": percentile(values, 0.95),
        }
    complete_scenarios = sorted(
        {row["scenario_id"] for row in rows if row["status"] == "PASS"}
    )
    catalog_count = len(catalog()["scenarios"])
    completed_techniques = sorted(
        {
            technique
            for scenario in catalog()["scenarios"]
            if scenario["id"] in complete_scenarios
            for technique in scenario.get("mitre", [])
        }
    )
    summary = {
        "generated_at": iso(utc_now()),
        "catalog_scenario_count": catalog_count,
        "run_count": len(rows),
        "pass_count": sum(1 for row in rows if row["status"] == "PASS"),
        "pending_decision_count": sum(
            1 for row in rows if row["status"] == "PASS_PENDING_DECISION"
        ),
        "fail_count": sum(1 for row in rows if row["status"] == "FAIL"),
        "complete_scenarios": complete_scenarios,
        "complete_scenario_count": len(complete_scenarios),
        "scenario_coverage_percent": round(
            (len(complete_scenarios) / catalog_count) * 100, 1
        ),
        "simulated_action_count": sum(int(row["simulated_actions"]) for row in rows),
        "live_rollback_count": sum(int(row["rolled_back_actions"]) for row in rows),
        "mitre_techniques_observed": completed_techniques,
        "metrics": metric_summary,
    }
    write_json(RESULTS_DIR / "summary.json", summary)
    lines = [
        "# Resumen de evaluación SanoliFood SOC",
        "",
        f"Generado: `{summary['generated_at']}`",
        "",
        f"- Ejecuciones: {summary['run_count']}",
        f"- Aprobadas: {summary['pass_count']}",
        f"- Pendientes de decisión: {summary['pending_decision_count']}",
        f"- Fallidas: {summary['fail_count']}",
        f"- Escenarios completos: {', '.join(summary['complete_scenarios']) or 'ninguno'}",
        f"- Cobertura del catálogo: {summary['scenario_coverage_percent']}%",
        f"- Acciones reales revertidas: {summary['live_rollback_count']}",
        "",
        "| Métrica | n | Media (s) | Mediana (s) | p95 (s) |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, values in metric_summary.items():
        lines.append(
            f"| {name} | {values['samples']} | {values['mean']} | "
            f"{values['median']} | {values['p95']} |"
        )
    (RESULTS_DIR / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def preflight(args: argparse.Namespace) -> int:
    command([sys.executable, str(ROOT / "evaluation" / "scripts" / "validate-static.py")])
    command(["make", "soc-health"], timeout=240)
    env = load_env(SOAR_ENV)
    verify_integration()
    checks = [
        "catalog=valid",
        "soc=healthy",
        f"response_mode={response_mode(env)}",
        "wazuh_forwarding=enabled",
    ]
    if args.kali_ssh:
        if not KALI_SSH_RE.fullmatch(args.kali_ssh):
            raise EvaluationError("KALI_SSH must be usuario@10.20.0.30")
        probe = """set -eu
ip -j -4 address
printf '\nSF_EPOCH='
date +%s
python3 - <<'PY'
import urllib.request
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open('http://10.20.0.10:8080/health/ready', timeout=8) as response:
    print('SF_HEALTH=' + response.read(4096).decode('utf-8'))
PY
"""
        remote = command(
            [
                "ssh",
                "-o",
                "ConnectTimeout=8",
                args.kali_ssh,
                "sh",
                "-s",
            ],
            timeout=20,
            input_text=probe,
        )
        if "10.20.0.30" not in remote.stdout:
            raise EvaluationError("Kali does not own 10.20.0.30")
        if 'SF_HEALTH={"status":"ready"' not in remote.stdout:
            raise EvaluationError("Kali cannot reach the application health endpoint")
        epoch_match = re.search(r"SF_EPOCH=(\d+)", remote.stdout)
        if not epoch_match or abs(int(time.time()) - int(epoch_match.group(1))) > 10:
            raise EvaluationError("Kali UTC clock differs by more than 10 seconds")
        checks.extend(("kali=10.20.0.30", "kali_to_app=ready", "clock_skew<=10s"))
    print("PASS evaluation preflight: " + ", ".join(checks))
    return 0


def list_scenarios() -> int:
    print(f"{'ID':7}  {'SOURCE':16}  {'RULE':6}  {'DECISION':8}  NAME")
    for item in catalog()["scenarios"]:
        print(
            f"{item['id']:7}  {item['source']:16}  {item['expected_rule_id']:<6}  "
            f"{str(item['requires_decision']).lower():8}  {item['name']}"
        )
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    preflight_parser = sub.add_parser("preflight")
    preflight_parser.add_argument("--kali-ssh", default="")

    run_parser = sub.add_parser("run")
    run_parser.add_argument("--scenario", required=True)
    run_parser.add_argument("--kali-ssh", default="")
    run_parser.add_argument("--windows-ssh", default="")
    run_parser.add_argument("--timeout", type=int)
    run_parser.add_argument("--allow-live", action="store_true")

    decision_parser = sub.add_parser("decide")
    decision_parser.add_argument("--run-id", required=True)
    decision_parser.add_argument("--decision", choices=("approve", "reject"), required=True)
    decision_parser.add_argument("--analyst", required=True)
    decision_parser.add_argument("--reason", required=True)
    decision_parser.add_argument("--allow-live", action="store_true")

    refresh_parser = sub.add_parser("refresh")
    refresh_parser.add_argument("--run-id", required=True)
    sub.add_parser("summary")
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "list":
            return list_scenarios()
        if args.command == "preflight":
            return preflight(args)
        if args.command == "run":
            return run_scenario(args)
        if args.command == "decide":
            return decide_run(args)
        if args.command == "refresh":
            return refresh_run(args)
        if args.command == "summary":
            print(json.dumps(build_summary(), indent=2, sort_keys=True))
            return 0
        raise EvaluationError("unsupported command")
    except EvaluationError as exc:
        print(f"Evaluation error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
