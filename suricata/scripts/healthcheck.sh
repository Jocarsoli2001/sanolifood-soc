#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$script_dir/common.sh"
load_runtime
failed=0

container_id="$("${compose[@]}" ps -q suricata)"
if [[ -z "$container_id" ]]; then
  printf 'FAIL suricata         state=missing health=unknown\n'
  exit 1
fi

state="$(docker inspect --format '{{.State.Status}}' "$container_id")"
health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' "$container_id")"
if [[ "$state" == "running" && "$health" == "healthy" ]]; then
  printf 'OK   suricata         state=%s health=%s\n' "$state" "$health"
else
  printf 'FAIL suricata         state=%s health=%s\n' "$state" "$health"
  failed=1
fi

if ip link show "$SURICATA_INTERFACE" >/dev/null 2>&1; then
  printf 'OK   interface        %s\n' "$SURICATA_INTERFACE"
else
  printf 'FAIL interface        %s is unavailable\n' "$SURICATA_INTERFACE"
  failed=1
fi

if "${compose[@]}" exec -T suricata test -r /var/log/suricata/eve.json; then
  printf 'OK   EVE telemetry    /var/log/suricata/eve.json\n'
else
  printf 'FAIL EVE telemetry    eve.json is not readable\n'
  failed=1
fi

wazuh_env="$project_dir/wazuh/runtime/.env"
if [[ -f "$wazuh_env" ]]; then
  wazuh_compose=(docker compose --env-file "$wazuh_env" -f "$project_dir/wazuh/compose.yaml")
  wazuh_manager_id="$("${wazuh_compose[@]}" ps --status running -q wazuh.manager)"
  if [[ -z "$wazuh_manager_id" ]]; then
    printf 'SKIP Wazuh ingestion  manager is not running\n'
  elif "${wazuh_compose[@]}" exec -T wazuh.manager test -r /var/log/suricata/eve.json; then
    printf 'OK   Wazuh ingestion  EVE volume readable by manager\n'
  else
    printf 'FAIL Wazuh ingestion  manager cannot read EVE volume\n'
    failed=1
  fi
fi

exit "$failed"
