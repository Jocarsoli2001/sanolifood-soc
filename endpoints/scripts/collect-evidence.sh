#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$script_dir/common.sh"
load_wazuh_runtime
evidence_dir="$project_dir/evidence/END-001"
mkdir -p "$evidence_dir"

"$script_dir/healthcheck.sh" > "$evidence_dir/health.txt" 2>&1
"${compose[@]}" exec -T wazuh.manager /var/ossec/bin/agent_control -ls \
  > "$evidence_dir/agents.txt" 2>&1
"${compose[@]}" exec -T wazuh.manager /var/ossec/bin/agent_groups -l \
  > "$evidence_dir/groups.txt" 2>&1

{
  for group_name in "$LINUX_AGENT_GROUP" "$WINDOWS_AGENT_GROUP"; do
    printf '===== %s =====\n' "$group_name"
    "${compose[@]}" exec -T wazuh.manager \
      /var/ossec/bin/verify-agent-conf \
      -f "/var/ossec/etc/shared/${group_name}/agent.conf"
  done
} > "$evidence_dir/central-policy-validation.txt" 2>&1

"${compose[@]}" exec -T wazuh.manager sh -c '
  test -f /var/ossec/logs/alerts/alerts.json || exit 0
  grep -E "\"id\":\"1102(00|10|11|20)\"" /var/ossec/logs/alerts/alerts.json | tail -n 40 || true
' > "$evidence_dir/endpoint-alerts.jsonl"

systemctl status wazuh-agent --no-pager \
  > "$evidence_dir/ubuntu-agent-service.txt" 2>&1 || true
dpkg-query -W -f='${Package}\t${Version}\n' wazuh-agent \
  > "$evidence_dir/ubuntu-agent-version.txt" 2>&1 || true

if [[ -n "${WINDOWS_SSH:-}" ]]; then
  ssh "$WINDOWS_SSH" \
    'powershell.exe -NoProfile -NonInteractive -Command "Get-Content -LiteralPath '\''C:\ProgramData\SanoliFood\Endpoint\install-manifest.txt'\''"' \
    > "$evidence_dir/windows-install-manifest.txt"
  ssh "$WINDOWS_SSH" \
    'powershell.exe -NoProfile -NonInteractive -Command "Get-Content -LiteralPath '\''C:\ProgramData\SanoliFood\Endpoint\validation-result.txt'\''"' \
    > "$evidence_dir/windows-validation.txt"
  ssh "$WINDOWS_SSH" \
    'powershell.exe -NoProfile -NonInteractive -Command "Get-Service -Name WazuhSvc,Sysmon* -ErrorAction Stop | Select-Object Name,Status,StartType | Format-Table -AutoSize"' \
    > "$evidence_dir/windows-services.txt"
fi

sha256sum \
  "$wazuh_dir/config/manager/shared/$LINUX_AGENT_GROUP/agent.conf" \
  "$wazuh_dir/config/manager/shared/$WINDOWS_AGENT_GROUP/agent.conf" \
  "$endpoints_dir/config/windows/sysmonconfig.xml" \
  "$endpoints_dir/windows/Install-SanoliFoodEndpoint.ps1" \
  "$endpoints_dir/windows/Test-SanoliFoodEndpoint.ps1" \
  "$endpoints_dir/config/linux/quality-policy.yml" \
  "$endpoints_dir/config/windows/quality-policy.json" \
  > "$evidence_dir/configuration-sha256.txt"

"$script_dir/check-live.sh" > "$evidence_dir/live-validation.txt" 2>&1

printf 'Endpoint evidence created in %s\n' "$evidence_dir"
printf 'Review it before Git. No enrollment password, key or Windows credential was collected.\n'
printf 'Store dashboard and Windows Event Viewer screenshots in the external evidence archive.\n'
