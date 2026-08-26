#!/usr/bin/env bash
set -Eeuo pipefail

failed=0

check_command() {
  local command_name="$1"
  if command -v "$command_name" >/dev/null 2>&1; then
    printf 'OK   command       %s\n' "$command_name"
  else
    printf 'FAIL command       %s is missing\n' "$command_name"
    failed=1
  fi
}

check_command docker
check_command ip
check_command awk
check_command curl

if [[ "$(uname -s)" == "Linux" ]]; then
  printf 'OK   operating     Linux host network namespace available\n'
else
  printf 'FAIL operating     Suricata live capture requires Linux\n'
  failed=1
fi

if docker info >/dev/null 2>&1; then
  printf 'OK   docker        daemon reachable\n'
else
  printf 'FAIL docker        daemon is not reachable\n'
  failed=1
fi

runtime_env="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)/runtime/.env"
runtime_interface=""
if [[ -s "$runtime_env" ]]; then
  runtime_interface="$(awk -F= '$1 == "SURICATA_INTERFACE" {print $2; exit}' "$runtime_env")"
fi
capture_interface="${SURICATA_INTERFACE_OVERRIDE:-${runtime_interface:-$(ip route show default 2>/dev/null | awk '{print $5; exit}')}}"
if [[ -n "$capture_interface" ]] && ip link show "$capture_interface" >/dev/null 2>&1; then
  printf 'OK   interface     %s\n' "$capture_interface"
else
  printf 'FAIL interface     configured capture interface is unavailable\n'
  failed=1
fi

host_cidr="$(ip -o -4 addr show dev "$capture_interface" 2>/dev/null | awk '{print $4; exit}')"
if [[ -n "$host_cidr" ]]; then
  printf 'OK   host-cidr     %s\n' "$host_cidr"
else
  printf 'FAIL host-cidr     no IPv4 address found on %s\n' "$capture_interface"
  failed=1
fi

if docker network inspect sanoli_dmz >/dev/null 2>&1; then
  dmz_id="$(docker network inspect -f '{{.Id}}' sanoli_dmz)"
  dmz_bridge="br-${dmz_id:0:12}"
  dmz_subnet="$(docker network inspect -f '{{(index .IPAM.Config 0).Subnet}}' sanoli_dmz)"
  printf 'OK   dmz-bridge    %s subnet=%s\n' "$dmz_bridge" "$dmz_subnet"
else
  printf 'FAIL dmz-network   sanoli_dmz does not exist; run make up first\n'
  failed=1
fi

available_kib="$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)"
available_mib="$((available_kib / 1024))"
if (( available_mib >= 1536 )); then
  printf 'OK   memory        %s MiB available\n' "$available_mib"
else
  printf 'FAIL memory        %s MiB available; at least 1536 MiB is required\n' "$available_mib"
  failed=1
fi

available_kib_disk="$(df -Pk / | awk 'NR==2 {print $4}')"
available_gib_disk="$((available_kib_disk / 1024 / 1024))"
if (( available_gib_disk >= 8 )); then
  printf 'OK   disk          %s GiB free\n' "$available_gib_disk"
else
  printf 'FAIL disk          %s GiB free; at least 8 GiB is required\n' "$available_gib_disk"
  failed=1
fi

exit "$failed"
