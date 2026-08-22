#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
wazuh_dir="$(cd -- "$script_dir/.." && pwd)"
env_file="$wazuh_dir/runtime/.env"
compose_file="$wazuh_dir/compose.yaml"

[[ -f "$env_file" ]] || { printf 'Run make wazuh-bootstrap first.\n' >&2; exit 1; }
compose=(docker compose --env-file "$env_file" -f "$compose_file")

[[ -n "$("${compose[@]}" ps -q wazuh.manager)" ]] || {
  printf 'Wazuh manager is not deployed.\n' >&2
  exit 1
}

docker volume inspect sanolifood_suricata_logs >/dev/null 2>&1 \
  || docker volume create sanolifood_suricata_logs >/dev/null

printf 'Recreating Wazuh manager to load versioned rules and telemetry mounts...\n'
"${compose[@]}" up -d --no-deps --force-recreate \
  --wait --wait-timeout 240 wazuh.manager

container_id="$("${compose[@]}" ps -q wazuh.manager)"
health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' "$container_id")"
if [[ "$health" == "healthy" ]]; then
  printf 'OK   wazuh.manager      configuration reloaded; health=healthy\n'
else
  printf 'FAIL wazuh.manager      health=%s\n' "$health" >&2
  "${compose[@]}" logs --no-color --tail=100 wazuh.manager >&2
  exit 1
fi
