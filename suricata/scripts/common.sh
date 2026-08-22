#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
suricata_dir="$(cd -- "$script_dir/.." && pwd)"
project_dir="$(cd -- "$suricata_dir/.." && pwd)"
env_file="$suricata_dir/runtime/.env"
compose_file="$suricata_dir/compose.yaml"

require_runtime() {
  [[ -f "$env_file" ]] || {
    printf 'Run make suricata-discover first.\n' >&2
    exit 1
  }
}

load_runtime() {
  require_runtime
  set -a
  # shellcheck disable=SC1090
  source "$env_file"
  set +a
  compose=(docker compose --env-file "$env_file" -f "$compose_file")
}
