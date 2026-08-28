#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
soar_dir="$(cd -- "$script_dir/.." && pwd)"
project_dir="$(cd -- "$soar_dir/.." && pwd)"
runtime_dir="$soar_dir/runtime"
secrets_dir="$runtime_dir/secrets"
env_file="$runtime_dir/.env"
app_env="$project_dir/.env"

command -v openssl >/dev/null 2>&1 || {
  printf 'OpenSSL is required to generate SOAR runtime secrets.\n' >&2
  exit 1
}
command -v python3 >/dev/null 2>&1 || {
  printf 'Python 3 is required to validate SOAR runtime policy.\n' >&2
  exit 1
}

mkdir -p "$secrets_dir"
chmod 0700 "$runtime_dir" "$secrets_dir"

random_hex() {
  openssl rand -hex "$1"
}

if [[ ! -f "$env_file" ]]; then
  n8n_db_password="SfN8n_$(random_hex 24)"
  soar_db_password="SfSoar_$(random_hex 24)"
  encryption_key="$(random_hex 32)"
  webhook_secret="$(random_hex 32)"
  analyst_secret="$(random_hex 32)"
  internal_token="$(random_hex 32)"
  {
    printf 'N8N_VERSION=2.36.7\n'
    printf 'N8N_DB_PASSWORD=%s\n' "$n8n_db_password"
    printf 'SOAR_DB_PASSWORD=%s\n' "$soar_db_password"
    printf 'N8N_ENCRYPTION_KEY=%s\n' "$encryption_key"
    printf 'SOAR_WEBHOOK_SECRET=%s\n' "$webhook_secret"
    printf 'SOAR_ANALYST_SECRET=%s\n' "$analyst_secret"
    printf 'SOAR_INTERNAL_TOKEN=%s\n' "$internal_token"
    printf 'SOAR_RESPONSE_MODE=dry-run\n'
    printf 'SOAR_PUBLIC_PORT=5678\n'
    printf 'SOAR_CONTROLLER_PORT=5680\n'
    printf 'SOAR_BIND_ADDRESS=127.0.0.1\n'
    printf 'N8N_HOST=127.0.0.1\n'
    printf 'SOAR_ALLOWED_CONTAINMENT_CIDRS=10.20.0.0/24\n'
    printf 'SOAR_PROTECTED_IPS=10.20.0.10,10.20.0.20,127.0.0.1\n'
    printf 'SOAR_PROTECTED_USERS=admin.sanolifood,socadmin\n'
    printf 'SOAR_MAX_TTL_SECONDS=1800\n'
    printf 'SOAR_HTTP_TIMEOUT_SECONDS=8\n'
  } > "$env_file"
  chmod 0600 "$env_file"
  printf 'Created local SOAR runtime configuration in n8n/runtime/.env.\n'
fi

set -a
# shellcheck disable=SC1090
source "$env_file"
set +a

required_variables=(
  N8N_VERSION N8N_DB_PASSWORD SOAR_DB_PASSWORD N8N_ENCRYPTION_KEY
  SOAR_WEBHOOK_SECRET SOAR_ANALYST_SECRET SOAR_INTERNAL_TOKEN
  SOAR_RESPONSE_MODE SOAR_ALLOWED_CONTAINMENT_CIDRS SOAR_PROTECTED_IPS
  SOAR_PROTECTED_USERS SOAR_MAX_TTL_SECONDS SOAR_HTTP_TIMEOUT_SECONDS
  SOAR_BIND_ADDRESS N8N_HOST SOAR_PUBLIC_PORT SOAR_CONTROLLER_PORT
)
for variable_name in "${required_variables[@]}"; do
  if [[ -z "${!variable_name:-}" ]]; then
    printf 'Missing required value %s in %s\n' "$variable_name" "$env_file" >&2
    exit 1
  fi
done

[[ "$SOAR_RESPONSE_MODE" == "dry-run" || "$SOAR_RESPONSE_MODE" == "live" ]] || {
  printf 'SOAR_RESPONSE_MODE must be dry-run or live.\n' >&2
  exit 1
}
[[ "$SOAR_BIND_ADDRESS" == "127.0.0.1" ]] || {
  printf 'SOAR_BIND_ADDRESS must remain 127.0.0.1; use the documented SSH tunnel.\n' >&2
  exit 1
}

python3 - "$SOAR_ALLOWED_CONTAINMENT_CIDRS" "$SOAR_PROTECTED_IPS" \
  "$SOAR_MAX_TTL_SECONDS" "$SOAR_PUBLIC_PORT" "$SOAR_CONTROLLER_PORT" <<'PY'
import ipaddress
import sys

cidrs, protected_ips, max_ttl, public_port, controller_port = sys.argv[1:]
networks = [ipaddress.ip_network(value.strip(), strict=False) for value in cidrs.split(",") if value.strip()]
if not networks or any(network.version != 4 for network in networks):
    raise SystemExit("SOAR containment requires at least one IPv4 CIDR")
for value in protected_ips.split(","):
    if value.strip():
        ipaddress.ip_address(value.strip())
if not 60 <= int(max_ttl) <= 3600:
    raise SystemExit("SOAR_MAX_TTL_SECONDS must be between 60 and 3600")
for name, value in (("SOAR_PUBLIC_PORT", public_port), ("SOAR_CONTROLLER_PORT", controller_port)):
    if not 1024 <= int(value) <= 65535:
        raise SystemExit(f"{name} must be an unprivileged TCP port")
PY

printf '%s\n' "$SOAR_WEBHOOK_SECRET" > "$secrets_dir/webhook.secret"
printf '%s\n' "$SOAR_ANALYST_SECRET" > "$secrets_dir/analyst.secret"
printf '%s\n' "$SOAR_INTERNAL_TOKEN" > "$secrets_dir/internal.token"
chmod 0600 "$secrets_dir"/*.secret "$secrets_dir"/*.token

if [[ ! -f "$runtime_dir/integration.state" ]]; then
  printf 'disabled\n' > "$runtime_dir/integration.state"
fi
chmod 0600 "$runtime_dir/integration.state"

[[ -f "$app_env" ]] || {
  printf 'Application .env is missing. Run make bootstrap and configure it before SOAR deployment.\n' >&2
  exit 1
}

upsert_app_setting() {
  local key="$1" value="$2"
  if grep -q "^${key}=" "$app_env"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$app_env"
  else
    printf '%s=%s\n' "$key" "$value" >> "$app_env"
  fi
}

upsert_app_setting SOAR_INTERNAL_TOKEN "$SOAR_INTERNAL_TOKEN"
upsert_app_setting SOAR_ALLOWED_CONTAINMENT_CIDRS "$SOAR_ALLOWED_CONTAINMENT_CIDRS"
upsert_app_setting SOAR_PROTECTED_IPS "$SOAR_PROTECTED_IPS"
upsert_app_setting SOAR_PROTECTED_USERS "$SOAR_PROTECTED_USERS"
upsert_app_setting SOAR_MAX_TTL_SECONDS "$SOAR_MAX_TTL_SECONDS"
chmod 0600 "$app_env"

if ! cmp -s "$soar_dir/config/playbooks.json" \
  "$project_dir/app/src/sanolifood/soar/playbooks.json"; then
  printf 'The n8n and controller playbook catalogs differ. Refusing deployment.\n' >&2
  exit 1
fi
