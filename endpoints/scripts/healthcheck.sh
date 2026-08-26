#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$script_dir/common.sh"
load_wazuh_runtime
failed=0

agent_output="$("${compose[@]}" exec -T wazuh.manager /var/ossec/bin/agent_control -ls 2>&1)"

check_agent() {
  local agent_name="$1" platform="$2" expected_group="$3"
  local agent_line agent_id agent_state group_output

  # Wazuh 4.14 emits CSV (ID,Name,IP,State,) while older releases can emit
  # the labelled "ID: ..., Name: ..." representation. Accept both so this
  # public healthcheck remains stable across supported manager outputs.
  agent_line="$(awk -F',' -v name="$agent_name" '$2 == name { print; exit }' \
    <<< "$agent_output")"
  if [[ -n "$agent_line" ]]; then
    agent_id="$(cut -d',' -f1 <<< "$agent_line" | tr -d '[:space:]')"
    agent_state="$(cut -d',' -f4 <<< "$agent_line" | tr -d '[:space:]')"
  else
    agent_line="$(grep -F "Name: ${agent_name}," <<< "$agent_output" | head -n 1 || true)"
    agent_id="$(sed -nE 's/.*ID: ([0-9]+),.*/\1/p' <<< "$agent_line")"
    if grep -Eq "Name: ${agent_name},.*Active" <<< "$agent_line"; then
      agent_state='Active'
    elif [[ -n "$agent_line" ]]; then
      agent_state='Disconnected'
    else
      agent_state=''
    fi
  fi

  if [[ "$agent_state" == 'Active' ]]; then
    printf 'OK   %-18s name=%s state=active\n' "$platform" "$agent_name"
    group_output="$("${compose[@]}" exec -T wazuh.manager \
      /var/ossec/bin/agent_groups -s -i "$agent_id" 2>&1 || true)"
    if grep -Fq "$expected_group" <<< "$group_output"; then
      printf 'OK   %-18s agent=%s group=%s\n' 'group assignment' "$agent_name" "$expected_group"
    else
      printf 'FAIL %-18s agent=%s expected=%s\n' 'group assignment' "$agent_name" "$expected_group"
      failed=1
    fi
  elif [[ -n "$agent_line" ]]; then
    printf 'FAIL %-18s name=%s state=disconnected\n' "$platform" "$agent_name"
    failed=1
  else
    printf 'FAIL %-18s name=%s state=not-enrolled\n' "$platform" "$agent_name"
    failed=1
  fi
}

check_agent "$LINUX_AGENT_NAME" 'Ubuntu endpoint' "$LINUX_AGENT_GROUP"
check_agent "$WINDOWS_AGENT_NAME" 'Windows endpoint' "$WINDOWS_AGENT_GROUP"

for group_name in "$LINUX_AGENT_GROUP" "$WINDOWS_AGENT_GROUP"; do
  if "${compose[@]}" exec -T wazuh.manager \
      test -s "/var/ossec/etc/shared/${group_name}/agent.conf"; then
    printf 'OK   %-18s %s\n' 'central policy' "$group_name"
  else
    printf 'FAIL %-18s %s missing\n' 'central policy' "$group_name"
    failed=1
  fi
done

exit "$failed"
