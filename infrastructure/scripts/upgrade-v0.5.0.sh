#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd -- "$script_dir/../.." && pwd)"
cd "$project_dir"

printf 'Validating the existing application and Wazuh baseline...\n'
./infrastructure/scripts/healthcheck.sh
./wazuh/scripts/healthcheck.sh

printf 'Validating the Suricata host prerequisites...\n'
./suricata/scripts/preflight.sh

printf 'Deploying the versioned Suricata IDS sensor...\n'
./suricata/scripts/bootstrap.sh

printf 'Testing application and NDR detection rules in Wazuh...\n'
./wazuh/scripts/test-rules.sh
./suricata/scripts/test-rules.sh

printf 'Validating the complete SOC stack...\n'
./infrastructure/scripts/healthcheck.sh
./wazuh/scripts/healthcheck.sh
./suricata/scripts/healthcheck.sh

printf '\nUpgrade to the Suricata NDR increment completed.\n'
printf 'From another computer, send the validation request documented in docs/IMPLEMENTATION-05-suricata-ndr.md.\n'
printf 'Then run: make suricata-check-live\n'
