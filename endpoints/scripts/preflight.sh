#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$script_dir/common.sh"

failed=0
for command_name in docker ip curl timeout ssh scp; do
  if command -v "$command_name" >/dev/null 2>&1; then
    printf 'OK   command          %s\n' "$command_name"
  else
    printf 'FAIL command          %s is missing\n' "$command_name"
    failed=1
  fi
done

if [[ -s "$wazuh_env" ]]; then
  printf 'OK   Wazuh runtime    local credentials present and ignored by Git\n'
else
  printf 'FAIL Wazuh runtime    run make wazuh-bootstrap first\n'
  failed=1
fi

if ip link show "$LAB_INTERFACE" >/dev/null 2>&1; then
  interface_cidr="$(ip -o -4 addr show dev "$LAB_INTERFACE" | awk '{print $4; exit}')"
  if [[ "${interface_cidr%/*}" == "$LAB_MANAGER_IP" ]]; then
    printf 'OK   lab interface    %s address=%s\n' "$LAB_INTERFACE" "$interface_cidr"
  else
    printf 'FAIL lab interface    %s expected=%s actual=%s\n' \
      "$LAB_INTERFACE" "$LAB_MANAGER_IP" "${interface_cidr:-none}"
    failed=1
  fi
else
  printf 'FAIL lab interface    %s is missing\n' "$LAB_INTERFACE"
  failed=1
fi

if docker info >/dev/null 2>&1; then
  printf 'OK   Docker           daemon reachable\n'
else
  printf 'FAIL Docker           daemon unavailable\n'
  failed=1
fi

if (( failed == 0 )); then
  load_wazuh_runtime
  manager_id="$("${compose[@]}" ps -q wazuh.manager)"
  if [[ -n "$manager_id" ]] && [[ "$(docker inspect -f '{{.State.Health.Status}}' "$manager_id")" == healthy ]]; then
    printf 'OK   Wazuh manager    healthy\n'
  else
    printf 'FAIL Wazuh manager    missing or unhealthy\n'
    failed=1
  fi
fi

for port in 1514 1515; do
  if check_tcp "$LAB_MANAGER_IP" "$port"; then
    printf 'OK   manager port     %s/tcp reachable at %s\n' "$port" "$LAB_MANAGER_IP"
  else
    printf 'FAIL manager port     %s/tcp unavailable at %s\n' "$port" "$LAB_MANAGER_IP"
    failed=1
  fi
done

if check_tcp "$WINDOWS_ENDPOINT_IP" 22; then
  printf 'OK   Windows SSH      %s:22 reachable\n' "$WINDOWS_ENDPOINT_IP"
else
  printf 'WARN Windows SSH      %s:22 not reachable; staging will require manual copy\n' "$WINDOWS_ENDPOINT_IP"
fi

exit "$failed"
