#!/usr/bin/env bash
set -Eeuo pipefail

minimum_cpus=4
minimum_memory_kib=$((8 * 1024 * 1024))
minimum_disk_kib=$((50 * 1024 * 1024))
required_map_count=262144
failed=0

check_command() {
  local command_name="$1"
  if command -v "$command_name" >/dev/null 2>&1; then
    printf 'OK   command      %s\n' "$command_name"
  else
    printf 'FAIL command      %s not found\n' "$command_name"
    failed=1
  fi
}

check_command docker
check_command openssl
check_command curl

if docker compose version >/dev/null 2>&1; then
  printf 'OK   compose      %s\n' "$(docker compose version --short)"
else
  printf 'FAIL compose      docker compose is unavailable\n'
  failed=1
fi

cpu_count="$(nproc)"
if (( cpu_count >= minimum_cpus )); then
  printf 'OK   cpu          %s logical processors\n' "$cpu_count"
else
  printf 'FAIL cpu          %s available; %s required\n' "$cpu_count" "$minimum_cpus"
  failed=1
fi

memory_kib="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)"
if (( memory_kib >= minimum_memory_kib )); then
  printf 'OK   memory       %.1f GiB\n' "$(awk -v value="$memory_kib" 'BEGIN {print value/1024/1024}')"
else
  printf 'FAIL memory       %.1f GiB available; 8 GiB required\n' "$(awk -v value="$memory_kib" 'BEGIN {print value/1024/1024}')"
  failed=1
fi

disk_kib="$(df -Pk . | awk 'NR == 2 {print $4}')"
if (( disk_kib >= minimum_disk_kib )); then
  printf 'OK   disk         %.1f GiB free\n' "$(awk -v value="$disk_kib" 'BEGIN {print value/1024/1024}')"
else
  printf 'FAIL disk         %.1f GiB free; 50 GiB required\n' "$(awk -v value="$disk_kib" 'BEGIN {print value/1024/1024}')"
  failed=1
fi

map_count="$(sysctl -n vm.max_map_count 2>/dev/null || printf '0')"
if (( map_count >= required_map_count )); then
  printf 'OK   map_count    %s\n' "$map_count"
else
  printf 'FAIL map_count    %s available; %s required\n' "$map_count" "$required_map_count"
  failed=1
fi

exit "$failed"
