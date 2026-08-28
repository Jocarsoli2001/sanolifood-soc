#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$script_dir/common.sh"
load_runtime

printf 'disabled\n' > "$runtime_dir/integration.state"
chmod 0600 "$runtime_dir/integration.state"
if [[ -f "$project_dir/wazuh/runtime/.env" ]]; then
  if ! "$project_dir/wazuh/scripts/reload-rules.sh"; then
    printf 'WARN Wazuh was unavailable; forwarding will be removed on its next bootstrap.\n' >&2
  fi
fi
"${compose[@]}" down
