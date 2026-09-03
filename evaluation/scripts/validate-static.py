#!/usr/bin/env python3
"""Validate the bounded v0.8 evaluation catalog and its safety invariants."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "evaluation" / "config" / "scenarios.json"


def fail(message: str) -> None:
    print(f"FAIL evaluation static validation: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    payload = json.loads(CATALOG.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or payload.get("catalog_version") != "0.8.0":
        fail("unsupported catalog version")

    policy = payload.get("lab_policy", {})
    expected_policy = {
        "allowed_cidr": "10.20.0.0/24",
        "soc_ipv4": "10.20.0.10",
        "windows_ipv4": "10.20.0.20",
        "kali_ipv4": "10.20.0.30",
        "application_port": 8080,
        "max_requests_per_run": 30,
    }
    for key, expected in expected_policy.items():
        if policy.get(key) != expected:
            fail(f"{key} must remain fixed at {expected}")

    scenarios = payload.get("scenarios", [])
    expected_ids = [f"SCN-{number:03d}" for number in range(1, 9)]
    if [item.get("id") for item in scenarios] != expected_ids:
        fail("the catalog must contain SCN-001 through SCN-008 in order")

    allowed_sources = {"kali", "business", "linux_endpoint", "windows_endpoint"}
    rules: set[int] = set()
    for item in scenarios:
        scenario_id = item["id"]
        if item.get("source") not in allowed_sources:
            fail(f"{scenario_id} has an unsupported source")
        rule_id = item.get("expected_rule_id")
        if not isinstance(rule_id, int) or rule_id in rules:
            fail(f"{scenario_id} has a missing or duplicate Wazuh rule")
        rules.add(rule_id)
        actions = item.get("expected_actions", [])
        if not actions or actions[0] != "collect_evidence":
            fail(f"{scenario_id} must collect evidence first")
        budget = item.get("request_budget")
        if not isinstance(budget, int) or not 0 <= budget <= policy["max_requests_per_run"]:
            fail(f"{scenario_id} exceeds the request budget")

    kali_script = (ROOT / "scenarios" / "kali" / "sanolifood_lab.py").read_text(
        encoding="utf-8"
    )
    required_literals = [
        'SOC_IPV4 = "10.20.0.10"',
        'KALI_IPV4 = "10.20.0.30"',
        "MAX_REQUESTS = 30",
    ]
    for literal in required_literals:
        if literal not in kali_script:
            fail(f"Kali runner is missing fixed safeguard: {literal}")
    prohibited = ["nmap", "masscan", "metasploit", "subprocess.popen", "os.system"]
    lowered = kali_script.lower()
    for token in prohibited:
        if token in lowered:
            fail(f"Kali runner contains prohibited primitive: {token}")

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    for target in (
        "eval-preflight:",
        "eval-run:",
        "eval-decide:",
        "eval-deploy-live-verification:",
        "eval-summary:",
    ):
        if target not in makefile:
            fail(f"Makefile target missing: {target[:-1]}")

    internal_api = (
        ROOT / "app" / "src" / "sanolifood" / "web" / "soar_internal.py"
    ).read_text(encoding="utf-8")
    evaluator = (ROOT / "evaluation" / "tools" / "evalctl.py").read_text(
        encoding="utf-8"
    )
    if '"/enforcement-probe"' not in internal_api:
        fail("the application read-only enforcement probe is missing")
    for phase in ("before", "active", "after_rollback"):
        if f'phase="{phase}"' not in evaluator:
            fail(f"the live evaluator is missing phase {phase}")

    linux_probe = (ROOT / "endpoints" / "scripts" / "validate-linux.sh").read_text(
        encoding="utf-8"
    )
    windows_probe = (
        ROOT / "endpoints" / "windows" / "Test-SanoliFoodEndpoint.ps1"
    ).read_text(encoding="utf-8")
    if "--run-id" not in linux_probe or not re.search(r"\$RunId\b", windows_probe):
        fail("endpoint probes do not accept the evaluation run identifier")
    if "STIMULUS_STARTED_AT=" not in linux_probe or "STIMULUS_STARTED_AT=" not in windows_probe:
        fail("endpoint probes do not report the precise stimulus timestamp")

    print(
        "PASS evaluation static validation: "
        f"{len(scenarios)} scenarios, {len(rules)} unique rules, "
        "fixed lab target 10.20.0.10."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
