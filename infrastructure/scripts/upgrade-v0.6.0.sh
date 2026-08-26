#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd -- "$script_dir/../.." && pwd)"
cd "$project_dir"

printf 'Validating the v0.5.1 SOC baseline...\n'
./infrastructure/scripts/healthcheck.sh
./wazuh/scripts/healthcheck.sh
./endpoints/scripts/preflight.sh

printf 'Binding Suricata to the isolated corporate segment...\n'
LAB_INTERFACE="${LAB_INTERFACE:-enp0s8}"
LAB_HOME_NET="${LAB_HOME_NET:-10.20.0.0/24}"
LAB_MANAGER_IP="${LAB_MANAGER_IP:-10.20.0.10}"

if grep -q '^WAZUH_AGENT_BIND_ADDRESS=' wazuh/runtime/.env; then
  sed -i "s|^WAZUH_AGENT_BIND_ADDRESS=.*|WAZUH_AGENT_BIND_ADDRESS=${LAB_MANAGER_IP}|" \
    wazuh/runtime/.env
else
  printf 'WAZUH_AGENT_BIND_ADDRESS=%s\n' "$LAB_MANAGER_IP" >> wazuh/runtime/.env
fi
chmod 0600 wazuh/runtime/.env

SURICATA_INTERFACE_OVERRIDE="$LAB_INTERFACE" \
SURICATA_HOME_NET_OVERRIDE="$LAB_HOME_NET" \
  ./suricata/scripts/bootstrap.sh

printf 'Publishing centralized Wazuh endpoint policies...\n'
./endpoints/scripts/configure-groups.sh

printf 'Testing the complete detection ruleset...\n'
./wazuh/scripts/test-rules.sh

printf '\nEndpoint manager preparation completed.\n'
printf 'Next commands:\n'
printf '  sudo ./endpoints/scripts/install-ubuntu-agent.sh\n'
printf '  ./endpoints/scripts/stage-windows.sh WINDOWS_USER@10.20.0.20\n'
printf 'Then run the staged Windows installer from an elevated PowerShell.\n'
