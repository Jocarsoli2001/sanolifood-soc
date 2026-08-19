#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
wazuh_dir="$(cd -- "$script_dir/.." && pwd)"
env_file="$wazuh_dir/runtime/.env"

if [[ ! -f "$env_file" ]]; then
  printf 'Wazuh runtime has not been initialized; nothing to stop.\n'
  exit 0
fi

docker compose --env-file "$env_file" -f "$wazuh_dir/compose.yaml" down
printf 'Wazuh containers stopped. Persistent volumes were preserved.\n'
