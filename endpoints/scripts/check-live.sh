#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$script_dir/common.sh"
load_wazuh_runtime

alerts_file=/var/ossec/logs/alerts/alerts.json
failed=0
check_rule() {
  local rule_id="$1" description="$2"
  if "${compose[@]}" exec -T wazuh.manager sh -c \
      'test -f "$1" && grep -F "\"id\":\"$2\"" "$1" | tail -n 1 | grep -q .' \
      sh "$alerts_file" "$rule_id"; then
    printf 'OK   %-22s rule=%s\n' "$description" "$rule_id"
  else
    printf 'FAIL %-22s rule=%s not observed\n' "$description" "$rule_id"
    failed=1
  fi
}

check_rule 110200 'Windows Sysmon probe'
check_rule 110210 'Ubuntu quality FIM'
check_rule 110211 'Windows quality FIM'
check_rule 110220 'Ubuntu log probe'

if (( failed == 0 )); then
  printf 'PASS endpoint telemetry path: host -> Wazuh agent -> manager -> alert.\n'
fi
exit "$failed"
