#!/bin/sh
set -eu

# Defense in depth: even an older/manual `docker compose run app pytest`
# invocation must not initialize or reuse the operational PostgreSQL database.
case "${1:-}" in
  pytest|*/pytest)
    export DATABASE_URL="${SANOLIFOOD_TEST_DATABASE_URL:-sqlite+pysqlite:///:memory:}"
    export APP_ENV=test
    exec "$@"
    ;;
esac

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  alembic upgrade head
fi

if [ "${RUN_SCHEMA_CHECK:-true}" = "true" ]; then
  python -m sanolifood.schema_guard
fi

if [ "${RUN_BOOTSTRAP:-true}" = "true" ]; then
  python -m sanolifood.bootstrap
fi

if [ "${RUN_DEMO_SEED:-true}" = "true" ]; then
  python -m sanolifood.bootstrap_business
fi

exec "$@"
