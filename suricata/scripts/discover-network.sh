#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
suricata_dir="$(cd -- "$script_dir/.." && pwd)"
runtime_dir="$suricata_dir/runtime"
env_file="$runtime_dir/.env"

capture_interface="${SURICATA_INTERFACE_OVERRIDE:-$(ip route show default | awk '{print $5; exit}')}"
[[ -n "$capture_interface" ]] || { printf 'Unable to discover capture interface.\n' >&2; exit 1; }
ip link show "$capture_interface" >/dev/null

host_cidr="$(ip -o -4 addr show dev "$capture_interface" | awk '{print $4; exit}')"
[[ -n "$host_cidr" ]] || { printf 'No IPv4 address found on %s.\n' "$capture_interface" >&2; exit 1; }
host_ip="${host_cidr%/*}"
home_net="${SURICATA_HOME_NET_OVERRIDE:-$host_ip/32}"

docker network inspect sanoli_dmz >/dev/null
dmz_id="$(docker network inspect -f '{{.Id}}' sanoli_dmz)"
dmz_bridge="br-${dmz_id:0:12}"
dmz_subnet="$(docker network inspect -f '{{(index .IPAM.Config 0).Subnet}}' sanoli_dmz)"

mkdir -p "$runtime_dir"
{
  printf 'SURICATA_VERSION=8.0.6\n'
  printf 'SURICATA_INTERFACE=%s\n' "$capture_interface"
  printf 'SURICATA_HOME_NET=%s\n' "$home_net"
  printf 'SURICATA_HOST_IP=%s\n' "$host_ip"
  printf 'SURICATA_DMZ_BRIDGE=%s\n' "$dmz_bridge"
  printf 'SURICATA_DMZ_SUBNET=%s\n' "$dmz_subnet"
} > "$env_file"
chmod 0600 "$env_file"

printf 'Suricata runtime created: interface=%s HOME_NET=%s\n' "$capture_interface" "$home_net"
printf 'DMZ documented: bridge=%s subnet=%s\n' "$dmz_bridge" "$dmz_subnet"
