#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
soar_dir="$(cd -- "$script_dir/.." && pwd)"
project_dir="$(cd -- "$soar_dir/.." && pwd)"
runtime_dir="$soar_dir/runtime"
env_file="$runtime_dir/.env"
compose_file="$soar_dir/compose.yaml"

require_command() {
  local command_name="$1"
  command -v "$command_name" >/dev/null 2>&1 || {
    printf 'Missing required command: %s\n' "$command_name" >&2
    exit 1
  }
}

load_runtime() {
  [[ -s "$env_file" ]] || {
    printf 'Run make soar-up first; %s is missing.\n' "$env_file" >&2
    exit 1
  }
  set -a
  # shellcheck disable=SC1090
  source "$env_file"
  set +a
  compose=(docker compose --env-file "$env_file" -f "$compose_file")
}
