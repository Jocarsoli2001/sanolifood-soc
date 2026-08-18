#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd -- "$script_dir/../.." && pwd)"
evidence_dir="$project_dir/evidence/BUS-001"
mkdir -p "$evidence_dir"
cd "$project_dir"

docker compose ps > "$evidence_dir/compose-status.txt"
docker compose images > "$evidence_dir/container-images.txt"
"$project_dir/infrastructure/scripts/healthcheck.sh" > "$evidence_dir/health.txt" 2>&1
docker compose exec -T app alembic current > "$evidence_dir/alembic-current.txt" 2>&1
docker compose exec -T app python -m sanolifood.schema_guard > "$evidence_dir/schema-guard.txt" 2>&1
docker compose run --rm --no-deps \
  -e DATABASE_URL=sqlite+pysqlite:///:memory: \
  -e APP_ENV=test \
  --entrypoint pytest app -q > "$evidence_dir/automated-tests.txt" 2>&1
docker compose exec -T postgres sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off -c \
  "select (select count(*) from suppliers) suppliers,
          (select count(*) from ingredients) ingredients,
          (select count(*) from production_lots) production_lots,
          (select count(*) from quality_checks) quality_checks,
          (select count(*) from audit_events) audit_events;"' \
  > "$evidence_dir/business-counts.txt"
docker compose exec -T postgres sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off -c \
  "select occurred_at,event_type,outcome,actor_username,correlation_id
   from audit_events
   where event_type like '\''inventory.%'\''
      or event_type like '\''production.%'\''
      or event_type like '\''quality.%'\''
   order by id desc limit 30;"' \
  > "$evidence_dir/business-events.txt"
docker compose logs --no-color --tail=500 app > "$evidence_dir/application-events.jsonl"

printf 'Evidencia textual creada en %s\n' "$evidence_dir"
printf 'Añade las cinco capturas indicadas en docs/IMPLEMENTATION-03-business-core.md.\n'
printf 'Revisa el contenido antes de incorporarlo a Git.\n'
