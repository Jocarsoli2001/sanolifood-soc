#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
endpoints_dir="$(cd -- "$script_dir/.." && pwd)"
project_dir="$(cd -- "$endpoints_dir/.." && pwd)"
wazuh_dir="$project_dir/wazuh"
wazuh_env="$wazuh_dir/runtime/.env"
wazuh_compose="$wazuh_dir/compose.yaml"

LAB_INTERFACE="${LAB_INTERFACE:-enp0s8}"
LAB_MANAGER_IP="${LAB_MANAGER_IP:-10.20.0.10}"
LAB_HOME_NET="${LAB_HOME_NET:-10.20.0.0/24}"
WINDOWS_ENDPOINT_IP="${WINDOWS_ENDPOINT_IP:-10.20.0.20}"
LINUX_AGENT_NAME="${LINUX_AGENT_NAME:-sanolifood-ubuntu-01}"
WINDOWS_AGENT_NAME="${WINDOWS_AGENT_NAME:-sanolifood-win-01}"
LINUX_AGENT_GROUP="${LINUX_AGENT_GROUP:-sanolifood-linux}"
WINDOWS_AGENT_GROUP="${WINDOWS_AGENT_GROUP:-sanolifood-windows}"
WAZUH_AGENT_VERSION="${WAZUH_AGENT_VERSION:-4.14.7}"

require_command() {
  local command_name="$1"
  command -v "$command_name" >/dev/null 2>&1 || {
    printf 'Missing required command: %s\n' "$command_name" >&2
    exit 1
  }
}

load_wazuh_runtime() {
  [[ -s "$wazuh_env" ]] || {
    printf 'Run make wazuh-bootstrap first; %s is missing.\n' "$wazuh_env" >&2
    exit 1
  }
  set -a
  # shellcheck disable=SC1090
  source "$wazuh_env"
  set +a
  compose=(docker compose --env-file "$wazuh_env" -f "$wazuh_compose")
}

check_tcp() {
  local host="$1" port="$2"
  timeout 3 bash -c "</dev/tcp/${host}/${port}" >/dev/null 2>&1
}
