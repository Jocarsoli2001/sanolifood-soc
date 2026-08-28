#!/usr/bin/env bash
set -Eeuo pipefail

: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${SOAR_DB_PASSWORD:?SOAR_DB_PASSWORD is required}"

psql \
  --set=ON_ERROR_STOP=1 \
  --set=soar_password="$SOAR_DB_PASSWORD" \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" <<'SQL'
SELECT format('CREATE ROLE soar_app LOGIN PASSWORD %L', :'soar_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'soar_app')
\gexec

SELECT 'CREATE DATABASE soar OWNER soar_app'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'soar')
\gexec
SQL

psql \
  --set=ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname soar <<'SQL'
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO soar_app;
SQL
