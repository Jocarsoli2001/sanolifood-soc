#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$script_dir/common.sh"
load_runtime

wazuh_env="$project_dir/wazuh/runtime/.env"
[[ -f "$wazuh_env" ]] || { printf 'Run make wazuh-bootstrap first.\n' >&2; exit 1; }
wazuh_compose=(docker compose --env-file "$wazuh_env" -f "$project_dir/wazuh/compose.yaml")

eve_match="$("${compose[@]}" exec -T suricata sh -c \
  'grep -F '\''"signature_id":9900001'\'' /var/log/suricata/eve.json | tail -n 1' || true)"
[[ -n "$eve_match" ]] || {
  printf 'FAIL Suricata SID 9900001 was not found. Send the documented validation request from Windows first.\n' >&2
  exit 1
}
printf 'OK   Suricata EVE     signature_id=9900001\n'

wazuh_match="$("${wazuh_compose[@]}" exec -T wazuh.manager sh -c \
  'grep -F '\''"id":"110100"'\'' /var/ossec/logs/alerts/alerts.json | tail -n 1' || true)"
[[ -n "$wazuh_match" ]] || {
  printf 'FAIL Wazuh rule 110100 was not found. Wait 20 seconds and retry.\n' >&2
  exit 1
}
printf 'OK   Wazuh alert      rule=110100\n'
printf 'PASS live NDR telemetry path: network -> Suricata -> EVE -> Wazuh.\n'
