#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$script_dir/common.sh"
load_runtime

printf 'Testing Suricata configuration and local signatures...\n'
"${compose[@]}" run --rm --no-deps suricata \
  -T \
  --set "vars.address-groups.HOME_NET=[$SURICATA_HOME_NET]" \
  -S /opt/sanolifood/local.rules

printf 'OK   suricata configuration and signatures are valid\n'
