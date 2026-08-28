#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$script_dir/common.sh"
load_runtime

if [[ "${1:-}" != "--confirm" ]]; then
  printf 'Refusing to enable live response without explicit confirmation.\n' >&2
  printf 'First run make soar-validate-live in dry-run mode, then use:\n' >&2
  printf '  ./n8n/scripts/enable-live-responses.sh --confirm\n' >&2
  exit 2
fi

if [[ "$SOAR_RESPONSE_MODE" == "live" ]]; then
  printf 'SOAR live response is already enabled.\n'
  exit 0
fi

python3 "$soar_dir/tools/soar_client.py" validate >/dev/null

protected_csv=",${SOAR_PROTECTED_IPS// /},"
[[ "$protected_csv" == *",10.20.0.10,"* ]] || {
  printf 'The Ubuntu SOC address 10.20.0.10 must remain protected.\n' >&2
  exit 1
}
[[ "$protected_csv" == *",10.20.0.20,"* ]] || {
  printf 'The Windows endpoint address 10.20.0.20 must remain protected.\n' >&2
  exit 1
}

sed -i 's/^SOAR_RESPONSE_MODE=.*/SOAR_RESPONSE_MODE=live/' "$env_file"
chmod 0600 "$env_file"
if ! "${compose[@]}" up -d --force-recreate --no-deps \
  --wait --wait-timeout 180 soar-controller; then
  sed -i 's/^SOAR_RESPONSE_MODE=.*/SOAR_RESPONSE_MODE=dry-run/' "$env_file"
  "${compose[@]}" up -d --force-recreate --no-deps soar-controller >/dev/null 2>&1 || true
  printf 'Live mode activation failed and the runtime setting was returned to dry-run.\n' >&2
  exit 1
fi

mode="$(curl -fsS --max-time 8 "http://127.0.0.1:${SOAR_CONTROLLER_PORT:-5680}/healthz" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["response_mode"])')"
[[ "$mode" == "live" ]] || {
  sed -i 's/^SOAR_RESPONSE_MODE=.*/SOAR_RESPONSE_MODE=dry-run/' "$env_file"
  "${compose[@]}" up -d --force-recreate --no-deps soar-controller >/dev/null 2>&1 || true
  printf 'Controller did not enter live response mode.\n' >&2
  exit 1
}

printf 'Live SOAR responses are enabled for approved actions only.\n'
printf 'Run make soar-validate-live now; the validation applies and rolls back its control.\n'
