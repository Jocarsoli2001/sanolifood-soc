#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$script_dir/common.sh"

if (( EUID != 0 )); then
  printf 'Run this installer with sudo.\n' >&2
  exit 1
fi

for command_name in curl gpg systemctl apt-get dpkg-query; do
  require_command "$command_name"
done
load_wazuh_runtime

if ! check_tcp "$LAB_MANAGER_IP" 1514 || ! check_tcp "$LAB_MANAGER_IP" 1515; then
  printf 'Wazuh manager ports are not reachable at %s.\n' "$LAB_MANAGER_IP" >&2
  exit 1
fi

install -d -m 0750 -o root -g root /etc/sanolifood
install -m 0640 -o root -g root \
  "$endpoints_dir/config/linux/quality-policy.yml" \
  /etc/sanolifood/quality-policy.yml

installed_version="$(dpkg-query -W -f='${Version}' wazuh-agent 2>/dev/null || true)"
if [[ "$installed_version" == "${WAZUH_AGENT_VERSION}-1" ]] && \
   [[ -s /var/ossec/etc/client.keys ]]; then
  systemctl enable --now wazuh-agent
  printf 'OK   wazuh-agent      %s already installed and enrolled\n' "$installed_version"
  exit 0
fi

if [[ -n "$installed_version" ]]; then
  printf 'An existing wazuh-agent %s was found without the expected enrollment.\n' \
    "$installed_version" >&2
  printf 'Preserve /var/ossec for diagnosis before performing a clean reenrollment.\n' >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends ca-certificates curl gnupg rsyslog
systemctl enable --now rsyslog

install -d -m 0755 /usr/share/keyrings
key_tmp="$(mktemp)"
trap 'rm -f "$key_tmp"' EXIT
curl -fsSL https://packages.wazuh.com/key/GPG-KEY-WAZUH -o "$key_tmp"
gpg --batch --yes --dearmor -o /usr/share/keyrings/wazuh.gpg "$key_tmp"
chmod 0644 /usr/share/keyrings/wazuh.gpg

printf '%s\n' \
  'deb [signed-by=/usr/share/keyrings/wazuh.gpg] https://packages.wazuh.com/4.x/apt/ stable main' \
  > /etc/apt/sources.list.d/wazuh.list
apt-get update -qq

if ! apt-cache madison wazuh-agent | awk '{print $3}' | grep -Fxq "${WAZUH_AGENT_VERSION}-1"; then
  printf 'Pinned wazuh-agent version %s-1 is unavailable in the configured repository.\n' \
    "$WAZUH_AGENT_VERSION" >&2
  exit 1
fi

WAZUH_MANAGER="$LAB_MANAGER_IP" \
WAZUH_MANAGER_PORT=1514 \
WAZUH_PROTOCOL=tcp \
WAZUH_REGISTRATION_SERVER="$LAB_MANAGER_IP" \
WAZUH_REGISTRATION_PORT=1515 \
WAZUH_REGISTRATION_PASSWORD="$WAZUH_REGISTRATION_PASSWORD" \
WAZUH_AGENT_NAME="$LINUX_AGENT_NAME" \
WAZUH_AGENT_GROUP="$LINUX_AGENT_GROUP" \
  apt-get install -y "wazuh-agent=${WAZUH_AGENT_VERSION}-1"

apt-mark hold wazuh-agent >/dev/null
systemctl daemon-reload
systemctl enable --now wazuh-agent

if ! systemctl is-active --quiet wazuh-agent; then
  systemctl status wazuh-agent --no-pager || true
  exit 1
fi

printf 'OK   wazuh-agent      version=%s name=%s group=%s\n' \
  "$WAZUH_AGENT_VERSION" "$LINUX_AGENT_NAME" "$LINUX_AGENT_GROUP"
printf 'OK   FIM target       /etc/sanolifood/quality-policy.yml\n'
printf 'The enrollment password was used in memory and was not written by this script.\n'
