#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
suricata_dir="$(cd -- "$script_dir/.." && pwd)"
project_dir="$(cd -- "$suricata_dir/.." && pwd)"

"$script_dir/config-test.sh"

wazuh_env="$project_dir/wazuh/runtime/.env"
[[ -f "$wazuh_env" ]] || { printf 'Run make wazuh-bootstrap first.\n' >&2; exit 1; }
wazuh_compose=(docker compose --env-file "$wazuh_env" -f "$project_dir/wazuh/compose.yaml")

test_event() {
  local sample_file="$1" expected_rule="$2" output detected_rule
  output="$("${wazuh_compose[@]}" exec -T wazuh.manager /var/ossec/bin/wazuh-logtest < "$sample_file" 2>&1)"
  detected_rule="$(grep -oE "id:[[:space:]]*'[0-9]+'" <<< "$output" | tail -n 1 | tr -cd '0-9' || true)"
  if [[ "$detected_rule" == "$expected_rule" ]]; then
    printf 'OK   %-34s Wazuh-rule=%s\n' "$(basename "$sample_file")" "$expected_rule"
  else
    printf '%s\n' "$output"
    printf 'FAIL %-34s expected=%s detected=%s\n' \
      "$(basename "$sample_file")" "$expected_rule" "${detected_rule:-none}" >&2
    return 1
  fi
}

test_event "$project_dir/wazuh/tests/events/suricata-validation.json" 110100
test_event "$project_dir/wazuh/tests/events/suricata-port-scan.json" 110110
test_event "$project_dir/wazuh/tests/events/suricata-web-enumeration.json" 110120
test_event "$project_dir/wazuh/tests/events/suricata-sqli.json" 110130
test_event "$project_dir/wazuh/tests/events/suricata-http-rate.json" 110140
