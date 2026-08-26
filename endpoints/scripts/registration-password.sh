#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$script_dir/common.sh"
load_wazuh_runtime

printf 'Wazuh enrollment password (do not capture or commit):\n'
printf '%s\n' "$WAZUH_REGISTRATION_PASSWORD"
