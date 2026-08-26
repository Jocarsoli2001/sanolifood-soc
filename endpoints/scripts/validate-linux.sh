#!/usr/bin/env bash
set -Eeuo pipefail

if (( EUID != 0 )); then
  printf 'Run this validation with sudo.\n' >&2
  exit 1
fi

systemctl is-active --quiet wazuh-agent || {
  printf 'wazuh-agent is not active.\n' >&2
  exit 1
}

timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'validation_timestamp: %s\n' "$timestamp" \
  > /etc/sanolifood/validation-probe.yml
chmod 0640 /etc/sanolifood/validation-probe.yml
logger -p authpriv.notice -t sanolifood-validation \
  "endpoint-validation outcome=success timestamp=$timestamp"

printf 'OK   Linux FIM probe  /etc/sanolifood/validation-probe.yml\n'
printf 'OK   Linux log probe  tag=sanolifood-validation\n'
printf 'Allow up to 30 seconds, then run make endpoint-check-live on the SOC host.\n'
