#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$script_dir/common.sh"
load_runtime
failed=0

check_service() {
  local service="$1" container_id state health
  container_id="$("${compose[@]}" ps -q "$service")"
  if [[ -z "$container_id" ]]; then
    printf 'FAIL %-20s state=missing health=unknown\n' "$service"
    failed=1
    return
  fi
  state="$(docker inspect --format '{{.State.Status}}' "$container_id")"
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' "$container_id")"
  if [[ "$state" == "running" && "$health" == "healthy" ]]; then
    printf 'OK   %-20s state=%s health=%s\n' "$service" "$state" "$health"
  else
    printf 'FAIL %-20s state=%s health=%s\n' "$service" "$state" "$health"
    failed=1
  fi
}

check_service soar-db
check_service soar-controller
check_service n8n

if curl -fsS --max-time 8 "http://127.0.0.1:${SOAR_PUBLIC_PORT:-5678}/healthz" >/dev/null; then
  printf 'OK   %-20s http://127.0.0.1:%s/healthz\n' n8n-http "${SOAR_PUBLIC_PORT:-5678}"
else
  printf 'FAIL %-20s n8n health endpoint unavailable\n' n8n-http
  failed=1
fi

controller_health="$(curl -fsS --max-time 8 \
  "http://127.0.0.1:${SOAR_CONTROLLER_PORT:-5680}/healthz" 2>/dev/null || true)"
controller_mode="$(python3 -c \
  'import json,sys; print(json.loads(sys.argv[1]).get("response_mode", ""))' \
  "$controller_health" 2>/dev/null || true)"
if [[ "$controller_mode" == "$SOAR_RESPONSE_MODE" ]]; then
  printf 'OK   %-20s response_mode=%s\n' controller-http "$controller_mode"
else
  printf 'FAIL %-20s unavailable or response mode differs (expected=%s actual=%s)\n' \
    controller-http "$SOAR_RESPONSE_MODE" "${controller_mode:-unknown}"
  failed=1
fi

integration_state="$(tr -d '[:space:]' < "$runtime_dir/integration.state")"
if [[ "$integration_state" == "enabled" ]]; then
  workflow_export=/tmp/sanolifood-soar-health-workflows.json
  if "${compose[@]}" exec -T n8n \
    n8n export:workflow --all --output="$workflow_export" >/dev/null 2>&1 \
    && "${compose[@]}" exec -T n8n node -e '
      const fs = require("fs");
      const expected = new Set([
        "SfSoarError0701", "SfSoarIntake071", "SfSoarDecision1",
        "SfSoarExpiry071", "SfSoarHealth071"
      ]);
      const payload = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
      const workflows = Array.isArray(payload) ? payload : [payload];
      for (const workflow of workflows) {
        if (expected.has(workflow.id) && workflow.active === true) expected.delete(workflow.id);
      }
      if (expected.size) process.exit(1);
    ' "$workflow_export"; then
    printf 'OK   %-20s five workflows present and published\n' workflow-publication
  else
    printf 'FAIL %-20s one or more workflows are missing or unpublished\n' workflow-publication
    failed=1
  fi
  "${compose[@]}" exec -T n8n rm -f "$workflow_export" >/dev/null 2>&1 || true
else
  printf 'INFO %-20s disabled until make soar-install-workflows\n' wazuh-forwarding
fi

exit "$failed"
