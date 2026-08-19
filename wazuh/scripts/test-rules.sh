#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
wazuh_dir="$(cd -- "$script_dir/.." && pwd)"
env_file="$wazuh_dir/runtime/.env"
compose_file="$wazuh_dir/compose.yaml"
compose=(docker compose --env-file "$env_file" -f "$compose_file")

[[ -f "$env_file" ]] || { printf 'Run make wazuh-bootstrap first.\n' >&2; exit 1; }

test_event() {
  local sample_file="$1" expected_rule="$2" output
  output="$("${compose[@]}" exec -T wazuh.manager /var/ossec/bin/wazuh-logtest < "$sample_file" 2>&1)"
  if grep -q "id: '$expected_rule'" <<< "$output"; then
    printf 'OK   %-28s rule=%s\n' "$(basename "$sample_file")" "$expected_rule"
  else
    printf '%s\n' "$output"
    printf 'FAIL %-28s expected rule=%s\n' "$(basename "$sample_file")" "$expected_rule" >&2
    return 1
  fi
}

test_event "$wazuh_dir/tests/events/auth-login-failed.json" 110010
test_event "$wazuh_dir/tests/events/inventory-adjustment.json" 110020
test_event "$wazuh_dir/tests/events/quality-check-failed.json" 110030
