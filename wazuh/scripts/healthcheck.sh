#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
wazuh_dir="$(cd -- "$script_dir/.." && pwd)"
env_file="$wazuh_dir/runtime/.env"
compose_file="$wazuh_dir/compose.yaml"
failed=0

[[ -f "$env_file" ]] || {
  printf 'FAIL runtime      run make wazuh-bootstrap first\n'
  exit 1
}

set -a
# shellcheck disable=SC1090
source "$env_file"
set +a

compose=(docker compose --env-file "$env_file" -f "$compose_file")

check_service() {
  local service="$1" container_id state health
  container_id="$("${compose[@]}" ps -q "$service")"
  if [[ -z "$container_id" ]]; then
    printf 'FAIL %-18s state=missing health=unknown\n' "$service"
    failed=1
    return
  fi
  state="$(docker inspect --format '{{.State.Status}}' "$container_id")"
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' "$container_id")"
  if [[ "$state" == "running" && "$health" == "healthy" ]]; then
    printf 'OK   %-18s state=%s health=%s\n' "$service" "$state" "$health"
  else
    printf 'FAIL %-18s state=%s health=%s\n' "$service" "$state" "$health"
    failed=1
  fi
}

check_service wazuh.indexer
check_service wazuh.manager
check_service wazuh.dashboard

dashboard_url="https://127.0.0.1:${WAZUH_DASHBOARD_PORT:-8443}/app/wz-home"
if curl -sk --fail --max-time 10 "$dashboard_url" >/dev/null; then
  printf 'OK   %-18s %s\n' HTTPS "$dashboard_url"
else
  printf 'FAIL %-18s %s\n' HTTPS "$dashboard_url"
  failed=1
fi

if "${compose[@]}" exec -T wazuh.manager test -r /var/log/sanolifood/sanolifood.jsonl; then
  printf 'OK   %-18s %s\n' telemetry /var/log/sanolifood/sanolifood.jsonl
else
  printf 'FAIL %-18s application log is not readable\n' telemetry
  failed=1
fi

exit "$failed"
