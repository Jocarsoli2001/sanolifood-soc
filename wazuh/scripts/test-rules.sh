#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
wazuh_dir="$(cd -- "$script_dir/.." && pwd)"
env_file="$wazuh_dir/runtime/.env"
compose_file="$wazuh_dir/compose.yaml"
compose=(docker compose --env-file "$env_file" -f "$compose_file")

[[ -f "$env_file" ]] || { printf 'Run make wazuh-bootstrap first.\n' >&2; exit 1; }

test_event() {
  local sample_file="$1" expected_rule="$2" output detected_rule
  output="$("${compose[@]}" exec -T wazuh.manager /var/ossec/bin/wazuh-logtest < "$sample_file" 2>&1)"
  detected_rule="$(grep -oE "id:[[:space:]]*'[0-9]+'" <<< "$output" | tail -n 1 | tr -cd '0-9' || true)"
  if [[ "$detected_rule" == "$expected_rule" ]]; then
    printf 'OK   %-34s rule=%s\n' "$(basename "$sample_file")" "$expected_rule"
  else
    printf '%s\n' "$output"
    printf 'FAIL %-34s expected=%s detected=%s\n' \
      "$(basename "$sample_file")" "$expected_rule" "${detected_rule:-none}" >&2
    return 1
  fi
}

test_native_rule_contract() {
  local rule_id="$1" parent="$2" required_field="$3" label="$4" block

  block="$(
    sed -n \
      "/<rule id=\"$rule_id\" /,/<\/rule>/p" \
      "$wazuh_dir/rules/sanolifood_rules.xml"
  )"

  if [[ -n "$block" ]] &&
     grep -Fq "<if_sid>$parent</if_sid>" <<< "$block" &&
     grep -Fq "name=\"$required_field\"" <<< "$block"; then
    printf 'OK   %-34s native-rule=%s parent=%s\n' \
      "$label" "$rule_id" "$parent"
  else
    printf 'FAIL %-34s invalid native rule contract\n' "$label" >&2
    return 1
  fi
}

test_event "$wazuh_dir/tests/events/auth-login-failed.json" 110010
test_event "$wazuh_dir/tests/events/inventory-adjustment.json" 110020
test_event "$wazuh_dir/tests/events/quality-check-failed.json" 110030
test_event "$wazuh_dir/tests/events/suricata-validation.json" 110100
test_event "$wazuh_dir/tests/events/suricata-port-scan.json" 110110
test_event "$wazuh_dir/tests/events/suricata-web-enumeration.json" 110120
test_event "$wazuh_dir/tests/events/suricata-sqli.json" 110130
test_event "$wazuh_dir/tests/events/suricata-http-rate.json" 110140
test_native_rule_contract 110200 61603 win.eventdata.commandLine endpoint-windows-sysmon
test_native_rule_contract 110210 550,554 file endpoint-linux-fim
test_native_rule_contract 110211 550,554 file endpoint-windows-fim
test_event "$wazuh_dir/tests/events/endpoint-linux-validation.txt" 110220
