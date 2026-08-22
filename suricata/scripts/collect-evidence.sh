#!/usr/bin/env bash
set -Eeuo pipefail
trap 'printf "FAIL NDR evidence collection at line %s.\n" "$LINENO" >&2' ERR

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$script_dir/common.sh"
load_runtime
evidence_dir="$project_dir/evidence/NDR-001"
wazuh_env="$project_dir/wazuh/runtime/.env"

mkdir -p "$evidence_dir"
"${compose[@]}" ps > "$evidence_dir/compose-status.txt"
"${compose[@]}" images > "$evidence_dir/container-images.txt"
"$script_dir/healthcheck.sh" > "$evidence_dir/health.txt" 2>&1
"$script_dir/config-test.sh" > "$evidence_dir/configuration-test.txt" 2>&1
"$script_dir/test-rules.sh" > "$evidence_dir/rule-tests.txt" 2>&1

{
  printf 'capture_interface=%s\n' "$SURICATA_INTERFACE"
  printf 'home_net=%s\n' "$SURICATA_HOME_NET"
  printf 'host_ip=%s\n' "$SURICATA_HOST_IP"
  printf 'dmz_bridge=%s\n' "$SURICATA_DMZ_BRIDGE"
  printf 'dmz_subnet=%s\n' "$SURICATA_DMZ_SUBNET"
  ip -br link show "$SURICATA_INTERFACE"
} > "$evidence_dir/sensor-topology.txt"

"${compose[@]}" exec -T suricata sh -c \
  'grep -F '"'"'"event_type":"alert"'"'"' /var/log/suricata/eve.json | tail -n 30 || true' \
  > "$evidence_dir/eve-alerts.jsonl"

"${compose[@]}" exec -T suricata sh -c \
  'tail -n 80 /var/log/suricata/stats.log 2>/dev/null || true' \
  > "$evidence_dir/suricata-stats.txt"

if [[ -f "$wazuh_env" ]]; then
  wazuh_compose=(docker compose --env-file "$wazuh_env" -f "$project_dir/wazuh/compose.yaml")
  "${wazuh_compose[@]}" exec -T wazuh.manager sh -c \
    'grep -E '"'"'"id":"1101(00|10|20|30|40)"'"'"' /var/ossec/logs/alerts/alerts.json | tail -n 30 || true' \
    > "$evidence_dir/wazuh-ndr-alerts.jsonl"
fi

container_id="$("${compose[@]}" ps -q suricata)"
docker stats --no-stream "$container_id" > "$evidence_dir/resource-usage.txt"

sha256sum \
  "$suricata_dir/compose.yaml" \
  "$suricata_dir/rules/local.rules" \
  "$project_dir/wazuh/config/manager/ossec.conf" \
  "$project_dir/wazuh/rules/sanolifood_rules.xml" \
  > "$evidence_dir/configuration-sha256.txt"

printf 'NDR evidence created in %s\n' "$evidence_dir"
printf 'Review it before Git. Runtime values and packet payloads were not copied.\n'
printf 'Add the screenshots listed in docs/IMPLEMENTATION-05-suricata-ndr.md to your external evidence archive.\n'
