#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd -- "$script_dir/../.." && pwd)"
cd "$project_dir"

if [[ ! -f compose.yaml ]] || ! grep -qx 'name: sanolifood' compose.yaml; then
  printf 'FAIL: execute this script from the expected SanoliFood repository.\n' >&2
  exit 2
fi
if [[ ! -f .env ]]; then
  printf 'FAIL: .env is missing; preserve the validated v0.3.0 configuration.\n' >&2
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
backup_file="$backup_dir/sanolifood-pre-v0.4.0-$(date -u +%Y%m%dT%H%M%SZ).dump"

printf 'Creating a PostgreSQL backup before the observability change...\n'
docker compose exec -T postgres sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' > "$backup_file"
test -s "$backup_file"

set_env_value APP_VERSION 0.4.0
set_env_value APP_LOG_FILE /var/log/sanolifood/sanolifood.jsonl

docker compose config --quiet
printf 'Building sanolifood/app:0.4.0 with persistent JSON telemetry...\n'
docker compose build --pull app
docker compose up -d --wait --wait-timeout 300

"$project_dir/infrastructure/scripts/healthcheck.sh"
docker compose exec -T app test -s /var/log/sanolifood/sanolifood.jsonl

printf 'Running the isolated application suite...\n'
docker compose run --rm --no-deps \
  -e DATABASE_URL=sqlite+pysqlite:///:memory: \
  -e APP_ENV=test \
  -e APP_LOG_FILE= \
  --entrypoint pytest app -q

"$project_dir/wazuh/scripts/bootstrap.sh"
"$project_dir/wazuh/scripts/reload-rules.sh"
"$project_dir/wazuh/scripts/test-rules.sh"

printf '\nUpgrade v0.4.0 completed without deleting application or Wazuh volumes.\n'
printf 'Database backup: %s\n' "$backup_file"
printf 'Use make wazuh-credentials only outside screenshots or recordings.\n'
