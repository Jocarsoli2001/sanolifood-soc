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

printf 'Restarting Wazuh manager to load versioned rules...\n'
  "${compose[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 240 wazuh.manager

for _ in {1..48}; do
  container_id="$("${compose[@]}" ps -q wazuh.manager)"
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' "$container_id")"
  if [[ "$health" == "healthy" ]]; then
    printf 'OK   wazuh.manager      rules reloaded; health=healthy\n'
    exit 0
  fi
  sleep 5
done

printf 'FAIL wazuh.manager did not become healthy after the rules reload.\n' >&2
"${compose[@]}" logs --no-color --tail=100 wazuh.manager >&2
exit 1
