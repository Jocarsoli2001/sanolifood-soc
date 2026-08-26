#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
suricata_dir="$(cd -- "$script_dir/.." && pwd)"
runtime_dir="$suricata_dir/runtime"
env_file="$runtime_dir/.env"

previous_interface=""
previous_home_net=""
if [[ -s "$env_file" ]]; then
  previous_interface="$(awk -F= '$1 == "SURICATA_INTERFACE" {print $2; exit}' "$env_file")"
  previous_home_net="$(awk -F= '$1 == "SURICATA_HOME_NET" {print $2; exit}' "$env_file")"
fi

if [[ -n "${SURICATA_INTERFACE_OVERRIDE:-}" ]]; then
  capture_interface="$SURICATA_INTERFACE_OVERRIDE"
elif [[ -n "$previous_interface" ]] && \
     ip link show "$previous_interface" >/dev/null 2>&1 && \
     ip -o -4 addr show dev "$previous_interface" | grep -q .; then
  capture_interface="$previous_interface"
else
  capture_interface="$(ip route show default | awk '{print $5; exit}')"
fi
[[ -n "$capture_interface" ]] || { printf 'Unable to discover capture interface.\n' >&2; exit 1; }
ip link show "$capture_interface" >/dev/null

host_cidr="$(ip -o -4 addr show dev "$capture_interface" | awk '{print $4; exit}')"
[[ -n "$host_cidr" ]] || { printf 'No IPv4 address found on %s.\n' "$capture_interface" >&2; exit 1; }
host_ip="${host_cidr%/*}"
if [[ -n "${SURICATA_HOME_NET_OVERRIDE:-}" ]]; then
  home_net="$SURICATA_HOME_NET_OVERRIDE"
elif [[ "$capture_interface" == "$previous_interface" && -n "$previous_home_net" ]]; then
  home_net="$previous_home_net"
else
  home_net="$host_ip/32"
fi

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
