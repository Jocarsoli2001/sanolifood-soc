#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd -- "$script_dir/../.." && pwd)"
cd "$project_dir"

[[ -s n8n/runtime/.env ]] || {
  printf 'SOAR runtime configuration is missing. Run make soar-up first.\n' >&2
  exit 1
}

set -a
# shellcheck disable=SC1091
source n8n/runtime/.env
set +a

[[ "${SOAR_RESPONSE_MODE:-}" == "dry-run" ]] || {
  printf 'Return SOAR to dry-run before deploying the live verification guard.\n' >&2
  exit 1
}

printf 'Validating the versioned live-verification code...\n'
make eval-static-check
make eval-test

printf 'Rebuilding the shared application/controller image...\n'
docker compose build app
docker compose up -d --no-build --wait --wait-timeout 240 app nginx
docker compose --env-file n8n/runtime/.env -f n8n/compose.yaml \
  up -d --no-deps --force-recreate --wait --wait-timeout 240 soar-controller

printf 'Running application and platform regression tests...\n'
make test
make health
make soar-health

python3 <<'PY'
import json
import os
from urllib.request import ProxyHandler, Request, build_opener

body = json.dumps(
    {"control_type": "app_account_lock", "target": "eval.deployment.probe"}
).encode("utf-8")
request = Request(
    "http://127.0.0.1:8080/internal/soar/enforcement-probe",
    data=body,
    headers={
        "Authorization": "Bearer " + os.environ["SOAR_INTERNAL_TOKEN"],
        "Content-Type": "application/json",
    },
    method="POST",
)
with build_opener(ProxyHandler({})).open(request, timeout=8) as response:
    payload = json.loads(response.read(65536).decode("utf-8"))
if payload.get("decision") != "allow" or payload.get("enforced") is not False:
    raise SystemExit("Live verification probe did not return the safe baseline state")
print("OK   live verification   baseline=allow endpoint=ready")
PY

printf '\nLive-effect verification is deployed. SOAR remains in dry-run mode.\n'
