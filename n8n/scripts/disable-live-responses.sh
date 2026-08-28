#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$script_dir/common.sh"
load_runtime

sed -i 's/^SOAR_RESPONSE_MODE=.*/SOAR_RESPONSE_MODE=dry-run/' "$env_file"
chmod 0600 "$env_file"
"${compose[@]}" up -d --force-recreate --no-deps \
  --wait --wait-timeout 180 soar-controller
mode="$(curl -fsS --max-time 8 "http://127.0.0.1:${SOAR_CONTROLLER_PORT:-5680}/healthz" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["response_mode"])')"
[[ "$mode" == "dry-run" ]] || {
  printf 'Controller did not confirm dry-run mode. Keep Wazuh forwarding disabled while diagnosing.\n' >&2
  exit 1
}
printf 'SOAR containment returned to dry-run mode. Existing live controls keep their TTL and rollback schedule.\n'
