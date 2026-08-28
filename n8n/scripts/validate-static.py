#!/usr/bin/env python3
"""Validate the versioned SanoliFood SOAR artifacts without starting containers."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


SOAR_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = SOAR_DIR.parent
WORKFLOW_DIR = SOAR_DIR / "workflows"
ERROR_WORKFLOW_ID = "SfSoarError0701"
EXPECTED_WORKFLOWS = {
    "00-error-handler.json": "SfSoarError0701",
    "01-alert-intake.json": "SfSoarIntake071",
    "02-analyst-decision.json": "SfSoarDecision1",
    "03-expiration-rollback.json": "SfSoarExpiry071",
    "04-health-metrics.json": "SfSoarHealth071",
}


class ValidationError(RuntimeError):
    pass


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"Invalid JSON artifact {path}: {exc}") from exc


def validate_catalog() -> tuple[dict[str, Any], dict[int, tuple[str, str]]]:
    controller_path = PROJECT_DIR / "app/src/sanolifood/soar/playbooks.json"
    n8n_path = SOAR_DIR / "config/playbooks.json"
    controller_catalog = load_json(controller_path)
    n8n_catalog = load_json(n8n_path)
    if controller_catalog != n8n_catalog:
        raise ValidationError("The controller and n8n playbook catalogs differ")
    if controller_catalog.get("schema_version") != 1:
        raise ValidationError("Unsupported playbook catalog schema")

    routing: dict[int, tuple[str, str]] = {}
    for playbook in controller_catalog.get("playbooks", []):
        playbook_id = playbook.get("id")
        priority = playbook.get("priority")
        actions = playbook.get("actions", [])
        if not any(action.get("type") == "collect_evidence" for action in actions):
            raise ValidationError(f"{playbook_id} does not preserve evidence")
        for action in actions:
            if action.get("type") == "collect_evidence":
                if not action.get("automatic") or action.get("reversible"):
                    raise ValidationError(f"{playbook_id} has an unsafe evidence action")
                continue
            ttl = action.get("ttl_seconds")
            if action.get("automatic") or not action.get("reversible"):
                raise ValidationError(f"{playbook_id} has containment without approval or rollback")
            if not isinstance(ttl, int) or not 60 <= ttl <= 1800:
                raise ValidationError(f"{playbook_id} has containment outside the TTL policy")
        for rule_id in playbook.get("rule_ids", []):
            if rule_id in routing:
                raise ValidationError(f"Wazuh rule {rule_id} is routed more than once")
            routing[rule_id] = (playbook_id, priority)
    if not routing:
        raise ValidationError("The playbook catalog does not route any Wazuh rule")
    return controller_catalog, routing


def validate_workflows(routing: dict[int, tuple[str, str]]) -> None:
    seen_ids: set[str] = set()
    intake_code = ""
    for filename, expected_id in EXPECTED_WORKFLOWS.items():
        path = WORKFLOW_DIR / filename
        workflow = load_json(path)
        workflow_id = workflow.get("id")
        if workflow_id != expected_id or workflow_id in seen_ids:
            raise ValidationError(f"Invalid or duplicate workflow ID in {filename}")
        seen_ids.add(workflow_id)
        if workflow.get("active") is not False:
            raise ValidationError(f"{filename} must be imported inactive and published explicitly")
        if workflow.get("settings", {}).get("executionOrder") != "v1":
            raise ValidationError(f"{filename} does not pin n8n execution order v1")
        if filename != "00-error-handler.json" and workflow.get("settings", {}).get(
            "errorWorkflow"
        ) != ERROR_WORKFLOW_ID:
            raise ValidationError(f"{filename} is not connected to the error workflow")

        nodes = workflow.get("nodes", [])
        node_names = {node.get("name") for node in nodes}
        if len(node_names) != len(nodes) or None in node_names:
            raise ValidationError(f"{filename} contains invalid or duplicate node names")
        for source, outputs in workflow.get("connections", {}).items():
            if source not in node_names:
                raise ValidationError(f"{filename} references missing source node {source}")
            for channel in outputs.values():
                for branch in channel:
                    for target in branch:
                        if target.get("node") not in node_names:
                            raise ValidationError(
                                f"{filename} references missing target node {target.get('node')}"
                            )
        for node in nodes:
            if node.get("type") == "n8n-nodes-base.httpRequest":
                url = str(node.get("parameters", {}).get("url", "")).lstrip("=")
                if not url.startswith("http://soar-controller:5680/"):
                    raise ValidationError(f"{filename} contains a non-internal controller URL")
                if not node.get("retryOnFail") or int(node.get("maxTries", 0)) < 3:
                    raise ValidationError(f"{filename} HTTP node lacks bounded retries")
            if filename == "01-alert-intake.json" and node.get("type") == "n8n-nodes-base.code":
                intake_code = node.get("parameters", {}).get("jsCode", "")

    if "envelope.nonce].map" in intake_code:
        raise ValidationError("The intake deduplication key incorrectly depends on the delivery nonce")
    if "typeof envelope.alert_json !== 'string'" not in intake_code:
        raise ValidationError("The intake workflow does not verify the exact canonical alert string")
    triage_pairs = {
        int(rule_id): (playbook_id, priority)
        for rule_id, playbook_id, priority in re.findall(
            r"'(110\d{3})': \['([^']+)', '([^']+)'\]", intake_code
        )
    }
    if triage_pairs != routing:
        raise ValidationError("The n8n triage table differs from the playbook catalog")


def validate_wazuh_routing(expected_rules: set[int]) -> None:
    integration_text = (SOAR_DIR / "integrations/custom-sanolifood-soar").read_text(
        encoding="utf-8"
    )
    allowlist_match = re.search(
        r"ALLOWED_RULE_IDS\s*=\s*frozenset\(\s*\{(.*?)\}\s*\)",
        integration_text,
        re.DOTALL,
    )
    if not allowlist_match:
        raise ValidationError("Wazuh integration rule allowlist was not found")
    integration_rules = {int(value) for value in re.findall(r'"(110\d{3})"', allowlist_match.group(1))}

    entrypoint_text = (
        PROJECT_DIR / "wazuh/config/manager/entrypoint/20-sanolifood-soar.sh"
    ).read_text(encoding="utf-8")
    rule_match = re.search(r"<rule_id>([^<]+)</rule_id>", entrypoint_text)
    manager_rules = {int(value) for value in rule_match.group(1).split(",")} if rule_match else set()
    if integration_rules != expected_rules or manager_rules != expected_rules:
        raise ValidationError("Wazuh, n8n and controller rule routing are not synchronized")


def validate_compose_readiness() -> None:
    compose_text = (SOAR_DIR / "compose.yaml").read_text(encoding="utf-8")
    tcp_readiness = "pg_isready -h 127.0.0.1 -p 5432 -U n8n -d n8n"
    if tcp_readiness not in compose_text:
        raise ValidationError(
            "The SOAR database healthcheck must verify the TCP path used by the controller"
        )


def validate_loopback_publication() -> None:
    compose_text = (SOAR_DIR / "compose.yaml").read_text(encoding="utf-8")
    host_network = "sanoli_soar_host"
    if compose_text.count(f"      - {host_network}\n") != 2:
        raise ValidationError(
            "n8n and the controller must attach to the dedicated host-publication network"
        )
    required_network_policy = (
        f"  {host_network}:\n"
        f"    name: {host_network}\n"
        "    driver: bridge\n"
        "    internal: false\n"
        "    driver_opts:\n"
        '      com.docker.network.bridge.host_binding_ipv4: "127.0.0.1"'
    )
    if required_network_policy not in compose_text:
        raise ValidationError(
            "The host-publication bridge must default every published port to loopback"
        )
    required_bindings = {
        '"127.0.0.1:${SOAR_CONTROLLER_PORT:-5680}:5680/tcp"',
        '"${SOAR_BIND_ADDRESS:-127.0.0.1}:${SOAR_PUBLIC_PORT:-5678}:5678/tcp"',
    }
    # Compare normalized YAML list items so indentation cannot weaken the policy check.
    stripped_lines = {line.strip().removeprefix("- ") for line in compose_text.splitlines()}
    if not required_bindings.issubset(stripped_lines):
        raise ValidationError("SOAR HTTP ports must remain bound to host loopback")
    required_n8n_network_path = {
        "N8N_LISTEN_ADDRESS: 0.0.0.0",
        '"fetch(\'http://n8n:5678/healthz\').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"',
    }
    if not required_n8n_network_path.issubset(stripped_lines):
        raise ValidationError(
            "n8n readiness must validate the container interface used by Docker forwarding"
        )


def main() -> int:
    try:
        catalog, routing = validate_catalog()
        validate_workflows(routing)
        validate_wazuh_routing(set(routing))
        validate_compose_readiness()
        validate_loopback_publication()
    except ValidationError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    print(
        f"PASS SOAR static validation: {len(EXPECTED_WORKFLOWS)} workflows, "
        f"{len(catalog['playbooks'])} playbooks, {len(routing)} routed rules."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
