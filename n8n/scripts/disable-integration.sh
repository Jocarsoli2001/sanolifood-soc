#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$script_dir/common.sh"
load_runtime

printf 'disabled\n' > "$runtime_dir/integration.state"
chmod 0600 "$runtime_dir/integration.state"
"$project_dir/wazuh/scripts/reload-rules.sh"
printf 'Authenticated Wazuh-to-n8n forwarding is disabled. Existing incidents were preserved.\n'
