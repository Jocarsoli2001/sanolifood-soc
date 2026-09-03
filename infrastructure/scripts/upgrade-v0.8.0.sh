#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd -- "$script_dir/../.." && pwd)"
cd "$project_dir"

printf 'Validating the v0.7.0 platform baseline...\n'
make soc-health

[[ -s n8n/runtime/.env ]] || {
  printf 'SOAR runtime configuration is missing. Run make soar-up first.\n' >&2
  exit 1
}
set -a
# shellcheck disable=SC1091
source n8n/runtime/.env
set +a
[[ "${SOAR_RESPONSE_MODE:-}" == "dry-run" ]] || {
  printf 'Return SOAR to dry-run with make soar-disable-live before upgrading.\n' >&2
  exit 1
}
[[ "$(tr -d '[:space:]' < n8n/runtime/integration.state)" == "enabled" ]] || {
  printf 'Wazuh forwarding is disabled. Run make soar-install-workflows first.\n' >&2
  exit 1
}

printf 'Validating bounded scenarios, application, detections and sensor rules...\n'
make validate
make wazuh-test-rules
make suricata-test-rules

mkdir -p evaluation/results/runs
chmod 0750 evaluation/results evaluation/results/runs

printf '\nSanoliFood v0.8.0 evaluation framework is ready.\n'
printf 'The next step is to configure isolated Kali as 10.20.0.30/24 and run:\n'
printf '  make eval-preflight KALI_SSH=usuario@10.20.0.30\n'
printf 'All response controls remain in dry-run until explicitly enabled.\n'
