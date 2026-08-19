#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
env_file="$(cd -- "$script_dir/.." && pwd)/runtime/.env"
[[ -f "$env_file" ]] || { printf 'Run make wazuh-bootstrap first.\n' >&2; exit 1; }

set -a
# shellcheck disable=SC1090
source "$env_file"
set +a

printf 'Wazuh Dashboard: https://127.0.0.1:%s\n' "${WAZUH_DASHBOARD_PORT:-8443}"
printf 'Usuario:          %s\n' "$WAZUH_INDEXER_USERNAME"
printf 'Contraseña:       %s\n' "$WAZUH_INDEXER_PASSWORD"
printf '\nNo incluyas esta salida en Git, capturas o evidencias.\n'
