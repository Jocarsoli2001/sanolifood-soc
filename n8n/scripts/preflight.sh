#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$script_dir/common.sh"

for command_name in docker curl openssl python3 sha256sum; do
  require_command "$command_name"
done
docker compose version >/dev/null

"$script_dir/prepare-runtime.sh"
load_runtime

python3 -m json.tool "$soar_dir/config/playbooks.json" >/dev/null
for workflow in "$soar_dir"/workflows/*.json; do
  python3 -m json.tool "$workflow" >/dev/null
done

docker network inspect sanoli_app >/dev/null 2>&1 || {
  printf 'The application network sanoli_app does not exist. Start the application first.\n' >&2
  exit 1
}

if docker network inspect sanoli_soar >/dev/null 2>&1; then
  soar_network_internal="$(docker network inspect --format '{{.Internal}}' sanoli_soar)"
  [[ "$soar_network_internal" == "true" ]] || {
    printf 'The existing sanoli_soar network is not internal. Stop its services and recreate it securely.\n' >&2
    exit 1
  }
fi

docker image inspect sanolifood/app:0.7.0 >/dev/null 2>&1 || {
  printf 'The application image sanolifood/app:0.7.0 is not built yet. Run make up first.\n' >&2
  exit 1
}

if [[ "$SOAR_RESPONSE_MODE" == "live" ]]; then
  printf 'WARN SOAR_RESPONSE_MODE=live: approved controls will affect the laboratory application.\n'
else
  printf 'OK   response mode       dry-run\n'
fi
printf 'OK   n8n version         %s\n' "$N8N_VERSION"
printf 'OK   workflow files      %s\n' "$(find "$soar_dir/workflows" -maxdepth 1 -type f -name '*.json' | wc -l)"
printf 'OK   playbook catalog    synchronized\n'
printf 'OK   secrets             generated locally and ignored by Git\n'
