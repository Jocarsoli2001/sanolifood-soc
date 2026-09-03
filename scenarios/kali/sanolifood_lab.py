#!/usr/bin/env python3
"""Bounded HTTP stimuli for the isolated SanoliFood laboratory."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener


SOC_IPV4 = "10.20.0.10"
KALI_IPV4 = "10.20.0.30"
APP_PORT = 8080
BASE_URL = f"http://{SOC_IPV4}:{APP_PORT}"
MAX_REQUESTS = 30
RUN_ID_PATTERN = re.compile(r"^SF-EVAL-SCN-00[1-4]-\d{8}T\d{6}Z-[0-9a-f]{8}$")


class ScenarioError(RuntimeError):
    pass


class LabClient:
    def __init__(self, run_id: str):
        jar = http.cookiejar.CookieJar()
        self.opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(jar))
        self.run_id = run_id
        self.requests = 0
        self.statuses: list[int] = []

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        form: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        accepted: set[int] | None = None,
    ) -> tuple[int, str]:
        if self.requests >= MAX_REQUESTS:
            raise ScenarioError("request ceiling reached")
        if not path.startswith("/") or "://" in path:
            raise ScenarioError("only relative paths on the fixed lab target are allowed")
        body = urlencode(form).encode("utf-8") if form is not None else None
        request_headers = {
            "User-Agent": "SanoliFood-Evaluation/0.8",
            "X-SanoliFood-Evaluation": self.run_id,
            **(headers or {}),
        }
        request = Request(
            BASE_URL + path,
            data=body,
            headers=request_headers,
            method=method,
        )
        self.requests += 1
        try:
            with self.opener.open(request, timeout=10) as response:
                status = response.status
                text = response.read(1_048_576).decode("utf-8", errors="replace")
        except HTTPError as exc:
            status = exc.code
            text = exc.read(1_048_576).decode("utf-8", errors="replace")
        except (URLError, TimeoutError) as exc:
            raise ScenarioError(f"fixed target unavailable: {exc}") from exc
        self.statuses.append(status)
        allowed = accepted or {200}
        if status not in allowed:
            raise ScenarioError(f"unexpected HTTP status {status} for {path}")
        return status, text


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_host() -> None:
    try:
        completed = subprocess.run(
            ["ip", "-j", "-4", "address"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        addresses = {
            item.get("local")
            for interface in json.loads(completed.stdout)
            for item in interface.get("addr_info", [])
        }
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        raise ScenarioError(f"unable to inspect Kali interfaces: {exc}") from exc
    if KALI_IPV4 not in addresses:
        raise ScenarioError(f"Kali must own the fixed laboratory address {KALI_IPV4}")


def csrf_token(html: str) -> str:
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if not match:
        raise ScenarioError("CSRF token was not present in the login page")
    return match.group(1)


def execute(stimulus: str, run_id: str, marker: str) -> dict[str, object]:
    validate_host()
    client = LabClient(run_id)
    client.request("/health/ready")
    client.requests = 0
    client.statuses.clear()
    started_at = utc_now()

    if stimulus == "ndr_validation":
        client.request(
            f"/health/ready?sf_run_id={run_id}",
            headers={"X-SanoliFood-Lab": "ndr-validation"},
        )
    elif stimulus == "auth_failures":
        _, login_html = client.request("/auth/login")
        token = csrf_token(login_html)
        for _ in range(5):
            client.request(
                "/auth/login",
                method="POST",
                form={
                    "username": marker,
                    "password": "Evaluation-Only-Invalid-Password",
                    "csrf_token": token,
                },
                accepted={401},
            )
    elif stimulus == "web_path_validation":
        client.request(f"/.env?sf_run_id={run_id}", accepted={403, 404})
    elif stimulus == "sqli_signature_validation":
        client.request(
            f"/__sf_evaluation_only__?sf_run_id={run_id}&q=UNION%20SELECT%20VALIDATION",
            accepted={403, 404},
        )
    else:
        raise ScenarioError(f"unsupported stimulus: {stimulus}")

    return {
        "status": "completed",
        "run_id": run_id,
        "marker": marker,
        "stimulus": stimulus,
        "source_ip": KALI_IPV4,
        "target_ip": SOC_IPV4,
        "target_port": APP_PORT,
        "request_count": client.requests,
        "http_statuses": client.statuses,
        "started_at": started_at,
        "completed_at": utc_now(),
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "stimulus",
        choices=(
            "ndr_validation",
            "auth_failures",
            "web_path_validation",
            "sqli_signature_validation",
        ),
    )
    result.add_argument("run_id")
    result.add_argument("marker")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if not RUN_ID_PATTERN.fullmatch(args.run_id):
            raise ScenarioError("invalid v0.8 evaluation run identifier")
        if not re.fullmatch(r"[A-Za-z0-9._-]{3,80}", args.marker):
            raise ScenarioError("invalid evaluation marker")
        print(json.dumps(execute(args.stimulus, args.run_id, args.marker), sort_keys=True))
        return 0
    except ScenarioError as exc:
        print(f"Kali scenario failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
