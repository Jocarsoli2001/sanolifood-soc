#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd -- "$script_dir/../.." && pwd)"
cd "$project_dir"

if [[ ! -f compose.yaml ]] || ! grep -qx 'name: sanolifood' compose.yaml; then
  printf 'FAIL: este script debe ejecutarse dentro del proyecto SanoliFood esperado.\n' >&2
  exit 2
fi

if [[ ! -f .env ]]; then
  printf 'FAIL: no existe .env. Conserva la configuración validada de v0.2.2.\n' >&2
  exit 3
fi

set_env_value() {
  local key="$1" value="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '%s=%s\n' "$key" "$value" >> .env
  fi
}

backup_dir="$(dirname -- "$project_dir")/sanolifood-backups"
mkdir -p "$backup_dir"
umask 077
backup_file="$backup_dir/sanolifood-pre-v0.3.0-$(date -u +%Y%m%dT%H%M%SZ).dump"

printf 'Creando respaldo PostgreSQL previo a la migración...\n'
docker compose exec -T postgres sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' > "$backup_file"
test -s "$backup_file"

set_env_value APP_VERSION 0.3.0
set_env_value RUN_MIGRATIONS true
set_env_value RUN_SCHEMA_CHECK true
set_env_value RUN_BOOTSTRAP true
set_env_value RUN_DEMO_SEED true

docker compose config --quiet
printf 'Construyendo la imagen sanolifood/app:0.3.0...\n'
docker compose build --no-cache --pull app
printf 'Aplicando la migración y esperando los healthchecks...\n'
docker compose up -d --wait --wait-timeout 240

"$project_dir/infrastructure/scripts/healthcheck.sh"
docker compose exec -T app alembic current
docker compose exec -T app python -m sanolifood.schema_guard

printf 'Ejecutando la suite en SQLite aislado...\n'
docker compose run --rm --no-deps \
  -e DATABASE_URL=sqlite+pysqlite:///:memory: \
  -e APP_ENV=test \
  --entrypoint pytest app -q

"$project_dir/infrastructure/scripts/healthcheck.sh"
printf '\nActualización v0.3.0 completada sin eliminar volúmenes.\n'
printf 'Respaldo previo: %s\n' "$backup_file"
printf 'Migración esperada: 20260817_0003 (head)\n'
