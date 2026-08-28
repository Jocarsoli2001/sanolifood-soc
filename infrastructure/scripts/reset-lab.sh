#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd -- "$script_dir/../.." && pwd)"
cd "$project_dir"

if [[ "${1:-}" != "--confirm" ]]; then
  printf 'Uso: %s --confirm\n' "$0" >&2
  printf 'Este comando elimina exclusivamente los contenedores, redes y volúmenes declarados por SanoliFood.\n' >&2
  exit 2
fi

if [[ ! -f compose.yaml ]] || ! grep -qx 'name: sanolifood' compose.yaml; then
  printf 'FAIL: el directorio actual no contiene el proyecto Compose sanolifood esperado.\n' >&2
  exit 3
fi

soar_env="$project_dir/n8n/runtime/.env"
soar_compose="$project_dir/n8n/compose.yaml"
if [[ -s "$soar_env" && -f "$soar_compose" ]]; then
  soar_controller_id="$(
    docker compose --env-file "$soar_env" -f "$soar_compose" \
      ps -q soar-controller 2>/dev/null || true
  )"
  if [[ -n "$soar_controller_id" ]]; then
    printf 'FAIL: el plano SOAR sigue desplegado y conserva estado asociado a PostgreSQL.\n' >&2
    printf 'Ejecute primero make soar-down; después repita make reset-lab.\n' >&2
    exit 4
  fi
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

set_env_value() {
  local key="$1" value="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '%s=%s\n' "$key" "$value" >> .env
  fi
}

session_secret_value="$(openssl rand -hex 32)"
postgres_password_value="$(openssl rand -hex 24)"
admin_password_value="Sf!$(openssl rand -hex 12)Aa1"

set_env_value APP_VERSION 0.7.0
set_env_value SESSION_SECRET "$session_secret_value"
set_env_value POSTGRES_DB sanolifood
set_env_value POSTGRES_USER sanolifood_app
set_env_value POSTGRES_PASSWORD "$postgres_password_value"
set_env_value DATABASE_URL "postgresql+psycopg://sanolifood_app:${postgres_password_value}@postgres:5432/sanolifood"
set_env_value BOOTSTRAP_ADMIN_USERNAME admin.sanolifood
set_env_value BOOTSTRAP_ADMIN_PASSWORD "$admin_password_value"
set_env_value RUN_MIGRATIONS true
set_env_value RUN_SCHEMA_CHECK true
set_env_value RUN_BOOTSTRAP true
set_env_value RUN_DEMO_SEED true

docker compose config --quiet

printf 'Eliminando exclusivamente el estado Docker de SanoliFood...\n'
docker compose down --volumes --remove-orphans

printf 'Construyendo SanoliFood Operations v0.7.0 sin caché...\n'
docker compose build --no-cache --pull app

printf 'Levantando la plataforma completa y esperando sus healthchecks...\n'
docker compose up -d --wait --wait-timeout 240

"$project_dir/infrastructure/scripts/healthcheck.sh"
printf 'Ejecutando pruebas en una base SQLite aislada...\n'
docker compose run --rm --no-deps \
  -e DATABASE_URL=sqlite+pysqlite:///:memory: \
  -e APP_ENV=test \
  --entrypoint pytest app -q

printf 'Confirmando que pytest no alteró PostgreSQL...\n'
docker compose exec -T app python -m sanolifood.schema_guard
"$project_dir/infrastructure/scripts/healthcheck.sh"

printf '\nReconstrucción limpia completada.\n'
printf 'Usuario inicial: admin.sanolifood\n'
printf 'Contraseña inicial: %s\n' "$admin_password_value"
printf 'Guárdala ahora y no la incluyas en Git ni en capturas.\n'

unset session_secret_value postgres_password_value admin_password_value
