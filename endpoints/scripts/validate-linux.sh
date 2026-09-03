#!/usr/bin/env bash
set -Eeuo pipefail

run_id="manual-$(date -u +%Y%m%dT%H%M%SZ)"
if [[ "${1:-}" == "--run-id" && -n "${2:-}" && -z "${3:-}" ]]; then
  run_id="$2"
  [[ "$run_id" =~ ^SF-EVAL-SCN-[0-9]{3}-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$ ]] || {
    printf 'Invalid evaluation run identifier.\n' >&2
    exit 2
  }
elif (( $# > 0 )); then
  printf 'Usage: sudo %s [--run-id SF-EVAL-SCN-NNN-YYYYMMDDTHHMMSSZ-xxxxxxxx]\n' "${0##*/}" >&2
  exit 2
fi

if (( EUID != 0 )); then
  printf 'Run this validation with sudo.\n' >&2
  exit 1
fi

systemctl is-active --quiet wazuh-agent || {
  printf 'wazuh-agent is not active.\n' >&2
  exit 1
}

timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'STIMULUS_STARTED_AT=%s\n' "$timestamp"
printf 'validation_timestamp: %s\nrun_id: %s\n' "$timestamp" "$run_id" \
  > /etc/sanolifood/validation-probe.yml
chmod 0640 /etc/sanolifood/validation-probe.yml
logger -p authpriv.notice -t sanolifood-validation \
  "endpoint-validation outcome=success timestamp=$timestamp run_id=$run_id"

printf 'OK   Linux FIM probe  /etc/sanolifood/validation-probe.yml\n'
printf 'OK   Linux log probe  tag=sanolifood-validation\n'
printf 'OK   Evaluation ID   %s\n' "$run_id"
printf 'Allow up to 30 seconds, then run make endpoint-check-live on the SOC host.\n'
