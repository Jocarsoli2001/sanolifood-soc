#!/usr/bin/env bash
set -euo pipefail

base_url="${SANOLIFOOD_URL:-http://127.0.0.1:${PUBLIC_HTTP_PORT:-8080}}"
failed=0

check_service() {
  local service="$1"
  local container_id state health
  container_id="$(docker compose ps -q "$service")"
  if [[ -z "$container_id" ]]; then
    printf 'FAIL %-12s state=missing health=unknown\n' "$service"
    failed=1
    return
  fi
  state="$(docker inspect --format '{{.State.Status}}' "$container_id")"
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' "$container_id")"
  if [[ "$state" == "running" && "$health" == "healthy" ]]; then
    printf 'OK   %-12s state=%s health=%s\n' "$service" "$state" "$health"
  else
    printf 'FAIL %-12s state=%s health=%s\n' "$service" "$state" "$health"
    failed=1
  fi
}

check_service postgres
check_service app
check_service nginx

if curl --fail --silent --show-error "$base_url/health/ready" | grep -q '"status":"ready"'; then
  printf 'OK   %-12s %s\n' "HTTP" "$base_url/health/ready"
else
  printf 'FAIL %-12s %s\n' "HTTP" "$base_url/health/ready"
  failed=1
fi

exit "$failed"
