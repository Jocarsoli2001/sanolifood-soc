#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
wazuh_dir="$(cd -- "$script_dir/.." && pwd)"
project_dir="$(cd -- "$wazuh_dir/.." && pwd)"
runtime_dir="$wazuh_dir/runtime"
env_file="$runtime_dir/.env"
compose_file="$wazuh_dir/compose.yaml"

cd "$project_dir"
"$script_dir/preflight.sh"

mkdir -p "$runtime_dir/certs"
chmod 0700 "$runtime_dir" "$runtime_dir/certs"

random_password() {
  printf 'Sf!%sAa1' "$(openssl rand -hex 18)"
}

if [[ ! -f "$env_file" ]]; then
  indexer_password="$(random_password)"
  dashboard_password="$(random_password)"
  api_password="$(random_password)"
  registration_password="$(random_password)"
  {
    printf 'WAZUH_VERSION=4.14.7\n'
    printf 'WAZUH_DASHBOARD_PORT=8443\n'
    printf 'WAZUH_AGENT_PORT=1514\n'
    printf 'WAZUH_ENROLLMENT_PORT=1515\n'
    printf 'WAZUH_SYSLOG_PORT=514\n'
    printf 'WAZUH_AGENT_BIND_ADDRESS=0.0.0.0\n'
    printf 'WAZUH_INDEXER_JAVA_OPTS="-Xms1g -Xmx1g"\n'
    printf 'WAZUH_INDEXER_USERNAME=admin\n'
    printf 'WAZUH_INDEXER_PASSWORD=%s\n' "$indexer_password"
    printf 'WAZUH_DASHBOARD_USERNAME=kibanaserver\n'
    printf 'WAZUH_DASHBOARD_PASSWORD=%s\n' "$dashboard_password"
    printf 'WAZUH_API_USERNAME=wazuh-wui\n'
    printf 'WAZUH_API_PASSWORD=%s\n' "$api_password"
    printf 'WAZUH_REGISTRATION_PASSWORD=%s\n' "$registration_password"
  } > "$env_file"
  chmod 0600 "$env_file"
  printf 'Credenciales locales creadas en wazuh/runtime/.env.\n'
fi

set -a
# shellcheck disable=SC1090
source "$env_file"
set +a

required_variables=(
  WAZUH_VERSION WAZUH_INDEXER_USERNAME WAZUH_INDEXER_PASSWORD
  WAZUH_DASHBOARD_USERNAME WAZUH_DASHBOARD_PASSWORD
  WAZUH_API_USERNAME WAZUH_API_PASSWORD WAZUH_REGISTRATION_PASSWORD
)
for variable_name in "${required_variables[@]}"; do
  if [[ -z "${!variable_name:-}" ]]; then
    printf 'Missing required value %s in %s\n' "$variable_name" "$env_file" >&2
    exit 1
  fi
done

hash_password() {
  local plain_password="$1" hash_output
  hash_output="$(
    docker run --rm \
      --env JAVA_HOME=/usr/share/wazuh-indexer/jdk \
      --entrypoint /usr/share/wazuh-indexer/plugins/opensearch-security/tools/hash.sh \
      "wazuh/wazuh-indexer:${WAZUH_VERSION}" -p "$plain_password" 2>/dev/null \
      | grep -E '^\$2[aby]\$' | tail -n 1
  )"
  [[ -n "$hash_output" ]] || {
    printf 'Unable to generate a Wazuh indexer password hash.\n' >&2
    exit 1
  }
  printf '%s' "$hash_output"
}

if [[ ! -f "$runtime_dir/internal_users.yml" ]]; then
  printf 'Generando hashes bcrypt para las cuentas internas...\n'
  admin_hash="$(hash_password "$WAZUH_INDEXER_PASSWORD")"
  dashboard_hash="$(hash_password "$WAZUH_DASHBOARD_PASSWORD")"
  internal_users_template="$(<"$wazuh_dir/config/indexer/internal_users.yml.template")"
  internal_users_template="${internal_users_template//__ADMIN_HASH__/$admin_hash}"
  internal_users_template="${internal_users_template//__DASHBOARD_HASH__/$dashboard_hash}"
  printf '%s\n' "$internal_users_template" > "$runtime_dir/internal_users.yml"
  chmod 0600 "$runtime_dir/internal_users.yml"
fi

dashboard_template="$(<"$wazuh_dir/config/dashboard/wazuh.yml.template")"
dashboard_template="${dashboard_template//__API_USERNAME__/$WAZUH_API_USERNAME}"
dashboard_template="${dashboard_template//__API_PASSWORD__/$WAZUH_API_PASSWORD}"
printf '%s\n' "$dashboard_template" > "$runtime_dir/wazuh.yml"
printf '%s\n' "$WAZUH_REGISTRATION_PASSWORD" > "$runtime_dir/authd.pass"
chmod 0600 "$runtime_dir/wazuh.yml" "$runtime_dir/authd.pass"

certificate_files=(
  root-ca.pem root-ca-manager.pem wazuh.indexer.pem wazuh.indexer-key.pem
  admin.pem admin-key.pem wazuh.manager.pem wazuh.manager-key.pem
  wazuh.dashboard.pem wazuh.dashboard-key.pem
)
certificates_complete=1
for certificate_file in "${certificate_files[@]}"; do
  [[ -s "$runtime_dir/certs/$certificate_file" ]] || certificates_complete=0
done

if (( certificates_complete == 0 )); then
  if find "$runtime_dir/certs" -mindepth 1 -type f -print -quit | grep -q .; then
    printf 'Certificate directory is incomplete. Preserve it for diagnosis and move it aside before retrying.\n' >&2
    exit 1
  fi
  printf 'Generando certificados TLS autofirmados con la herramienta oficial de Wazuh...\n'
  docker compose -f "$wazuh_dir/generate-certs.yaml" run --rm generator
fi

docker volume inspect sanolifood_app_logs >/dev/null 2>&1 \
  || docker volume create sanolifood_app_logs >/dev/null

docker compose --env-file "$env_file" -f "$compose_file" config --quiet
printf 'Descargando imágenes Wazuh %s...\n' "$WAZUH_VERSION"
docker compose --env-file "$env_file" -f "$compose_file" pull
printf 'Levantando Wazuh y esperando healthchecks...\n'
docker compose --env-file "$env_file" -f "$compose_file" \
  up -d --wait --wait-timeout 600

"$script_dir/healthcheck.sh"
if [[ -x "$project_dir/endpoints/scripts/configure-groups.sh" ]]; then
  "$project_dir/endpoints/scripts/configure-groups.sh"
fi
printf '\nWazuh central está operativo.\n'
printf 'Dashboard local: https://127.0.0.1:%s\n' "${WAZUH_DASHBOARD_PORT:-8443}"
printf 'Para consultar las credenciales sin capturarlas: make wazuh-credentials\n'
