#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$script_dir/common.sh"
load_wazuh_runtime

groups=("$LINUX_AGENT_GROUP" "$WINDOWS_AGENT_GROUP")
current_groups="$("${compose[@]}" exec -T wazuh.manager /var/ossec/bin/agent_groups -l 2>&1)"

for group_name in "${groups[@]}"; do
  if grep -Fq "$group_name" <<< "$current_groups"; then
    printf 'OK   group            %s already exists\n' "$group_name"
  else
    "${compose[@]}" exec -T wazuh.manager \
      /var/ossec/bin/agent_groups -a -g "$group_name" -q >/dev/null
    printf 'OK   group            %s created\n' "$group_name"
  fi

  "${compose[@]}" exec -T wazuh.manager sh -c '
    group_name="$1"
    source_file="/wazuh-config-mount/etc/shared/${group_name}/agent.conf"
    target_dir="/var/ossec/etc/shared/${group_name}"
    test -s "$source_file"
    mkdir -p "$target_dir"
    cp "$source_file" "$target_dir/agent.conf"
    chown wazuh:wazuh "$target_dir" "$target_dir/agent.conf"
    chmod 0770 "$target_dir"
    chmod 0660 "$target_dir/agent.conf"
  ' sh "$group_name"

  "${compose[@]}" exec -T wazuh.manager \
    /var/ossec/bin/verify-agent-conf \
    -f "/var/ossec/etc/shared/${group_name}/agent.conf" >/dev/null
  printf 'OK   policy           %s/agent.conf valid and published\n' "$group_name"
done

printf 'PASS centralized endpoint policies are ready for enrollment.\n'
