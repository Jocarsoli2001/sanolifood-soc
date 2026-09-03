#!/usr/bin/env python3
"""Generate bounded, attributable SanoliFood business security events."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[2]
BASE_URL = "http://127.0.0.1:8080"
RUN_ID_PATTERN = re.compile(r"^SF-EVAL-SCN-00[56]-\d{8}T\d{6}Z-[0-9a-f]{8}$")


class BusinessScenarioError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise BusinessScenarioError(f"missing local runtime configuration: {path}")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key] = value.strip().strip('"').strip("'")
    return values


class AppClient:
    def __init__(self, run_id: str):
        jar = http.cookiejar.CookieJar()
        self.opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(jar))
        self.run_id = run_id
        self.requests = 0
        self.statuses: list[int] = []

    def request(
        self, path: str, *, method: str = "GET", form: dict[str, str] | None = None
    ) -> tuple[int, str]:
        if not path.startswith("/") or "://" in path:
            raise BusinessScenarioError("only relative paths on loopback are allowed")
        data = urlencode(form).encode("utf-8") if form is not None else None
        request = Request(
            BASE_URL + path,
            data=data,
            headers={
                "User-Agent": "SanoliFood-Evaluation/0.8",
                "X-SanoliFood-Evaluation": self.run_id,
            },
            method=method,
        )
        self.requests += 1
        try:
            with self.opener.open(request, timeout=10) as response:
                status = response.status
                text = response.read(2_097_152).decode("utf-8", errors="replace")
        except HTTPError as exc:
            status = exc.code
            text = exc.read(2_097_152).decode("utf-8", errors="replace")
        except (URLError, TimeoutError) as exc:
            raise BusinessScenarioError(f"application unavailable: {exc}") from exc
        self.statuses.append(status)
        if status != 200:
            raise BusinessScenarioError(f"unexpected HTTP status {status} for {path}")
        return status, text


def csrf_token(html: str) -> str:
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if not match:
        raise BusinessScenarioError("CSRF token not found")
    return match.group(1)


def login(client: AppClient, env: dict[str, str]) -> str:
    username = env.get("BOOTSTRAP_ADMIN_USERNAME", "")
    password = env.get("BOOTSTRAP_ADMIN_PASSWORD", "")
    if not username or not password or password.startswith("CHANGE_ME"):
        raise BusinessScenarioError("valid local bootstrap credentials are required")
    _, page = client.request("/auth/login")
    token = csrf_token(page)
    _, landing = client.request(
        "/auth/login",
        method="POST",
        form={"username": username, "password": password, "csrf_token": token},
    )
    if "Cerrar sesión" not in landing:
        raise BusinessScenarioError("administrator login did not complete")
    return username


def submit(client: AppClient, path: str, form: dict[str, str]) -> str:
    _, page = client.request(path, method="POST", form=form)
    if "No se pudo completar" in page:
        raise BusinessScenarioError(f"business operation rejected at {path}")
    return page


def inventory_adjustment(client: AppClient, run_id: str) -> dict[str, object]:
    _, page = client.request("/inventory")
    token = csrf_token(page)
    ingredient = re.search(
        r'<option value="(\d+)">ING-TOM-001\s+·', page
    )
    if not ingredient:
        raise BusinessScenarioError("reproducible ingredient ING-TOM-001 not found")
    ingredient_id = ingredient.group(1)
    common = {
        "ingredient_id": ingredient_id,
        "movement_type": "adjustment",
        "reason": "Controlled v0.8 evaluation with exact compensation",
        "csrf_token": token,
    }
    submit(
        client,
        "/inventory/movements",
        {**common, "quantity": "100.000", "reference": run_id},
    )
    submit(
        client,
        "/inventory/movements",
        {**common, "quantity": "-99.999", "reference": f"RESTORE-A-{run_id}"},
    )
    submit(
        client,
        "/inventory/movements",
        {**common, "quantity": "-0.001", "reference": f"RESTORE-B-{run_id}"},
    )
    return {"ingredient_sku": "ING-TOM-001", "net_quantity_delta": "0.000"}


def quality_failure(client: AppClient, run_id: str) -> dict[str, object]:
    _, page = client.request("/quality")
    token = csrf_token(page)
    lot = re.search(r'<option value="(\d+)">([^<]+)</option>', page)
    if not lot:
        raise BusinessScenarioError("no inspectable production lot is available")
    submit(
        client,
        "/quality/checks",
        {
            "lot_id": lot.group(1),
            "check_type": run_id,
            "measured_value": "9.000",
            "unit": "validation-unit",
            "min_value": "4.000",
            "max_value": "5.000",
            "notes": "Controlled persistent evidence for the v0.8 evaluation",
            "csrf_token": token,
        },
    )
    return {"lot": lot.group(2).strip(), "result": "fail", "persistent_record": True}


def execute(stimulus: str, run_id: str) -> dict[str, object]:
    env = load_env(ROOT / ".env")
    client = AppClient(run_id)
    started_at = utc_now()
    actor = login(client, env)
    client.requests = 0
    client.statuses.clear()
    if stimulus == "inventory_adjustment":
        effect = inventory_adjustment(client, run_id)
    elif stimulus == "quality_failure":
        effect = quality_failure(client, run_id)
    else:
        raise BusinessScenarioError(f"unsupported stimulus: {stimulus}")
    return {
        "status": "completed",
        "run_id": run_id,
        "stimulus": stimulus,
        "actor_username": actor,
        "request_count": client.requests,
        "http_statuses": client.statuses,
        "effect": effect,
        "started_at": started_at,
        "completed_at": utc_now(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stimulus", choices=("inventory_adjustment", "quality_failure"))
    parser.add_argument("run_id")
    args = parser.parse_args()
    try:
        if not RUN_ID_PATTERN.fullmatch(args.run_id):
            raise BusinessScenarioError("invalid v0.8 evaluation run identifier")
        print(json.dumps(execute(args.stimulus, args.run_id), sort_keys=True))
        return 0
    except BusinessScenarioError as exc:
        print(f"Business scenario failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
