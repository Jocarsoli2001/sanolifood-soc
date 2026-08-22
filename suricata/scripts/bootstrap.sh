#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
suricata_dir="$(cd -- "$script_dir/.." && pwd)"
project_dir="$(cd -- "$suricata_dir/.." && pwd)"

cd "$project_dir"
"$script_dir/preflight.sh"
"$script_dir/discover-network.sh"

# shellcheck source=common.sh
source "$script_dir/common.sh"
load_runtime

docker volume inspect sanolifood_suricata_logs >/dev/null 2>&1 \
  || docker volume create sanolifood_suricata_logs >/dev/null

"${compose[@]}" config --quiet
printf 'Pulling Suricata %s...\n' "$SURICATA_VERSION"
"${compose[@]}" pull
"$script_dir/config-test.sh"

printf 'Starting the Suricata IDS sensor on %s...\n' "$SURICATA_INTERFACE"
"${compose[@]}" up -d --wait --wait-timeout 240

if [[ -f "$project_dir/wazuh/runtime/.env" ]] && \
   docker compose --env-file "$project_dir/wazuh/runtime/.env" \
     -f "$project_dir/wazuh/compose.yaml" ps -q wazuh.manager | grep -q .; then
  printf 'Recreating Wazuh manager to mount Suricata EVE telemetry...\n'
  "$project_dir/wazuh/scripts/reload-rules.sh"
else
  printf 'WARN Wazuh is not running; start it later with make wazuh-up.\n'
fi

"$script_dir/healthcheck.sh"

printf '\nSuricata is operational in IDS mode.\n'
printf 'Capture interface: %s\n' "$SURICATA_INTERFACE"
printf 'HOME_NET: %s\n' "$SURICATA_HOME_NET"
printf 'Next: run make suricata-test-rules.\n'
