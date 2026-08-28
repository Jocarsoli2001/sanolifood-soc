#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd -- "$script_dir/../.." && pwd)"
cd "$project_dir"

printf 'Validating the v0.6.0 SOC baseline...\n'
./infrastructure/scripts/healthcheck.sh
./wazuh/scripts/healthcheck.sh
./suricata/scripts/healthcheck.sh
./endpoints/scripts/healthcheck.sh

backup_dir="$(dirname -- "$project_dir")/sanolifood-backups"
mkdir -p "$backup_dir"
chmod 0700 "$backup_dir"
umask 077
backup_file="$backup_dir/sanolifood-pre-v0.7.0-$(date -u +%Y%m%dT%H%M%SZ).dump"

printf 'Creating a PostgreSQL backup before the SOAR control migration...\n'
docker compose exec -T postgres sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl' \
  > "$backup_file"
test -s "$backup_file"

printf 'Validating the versioned SOAR artifacts...\n'
python3 ./n8n/scripts/validate-static.py
./n8n/scripts/prepare-runtime.sh

printf 'Rebuilding the application with reversible SOAR controls...\n'
docker compose config --quiet
docker compose up -d --build --wait --wait-timeout 300
./infrastructure/scripts/healthcheck.sh

printf 'Starting the isolated n8n control plane in dry-run mode...\n'
./n8n/scripts/bootstrap.sh

printf '\nSanoliFood v0.7.0 platform services are ready in dry-run mode.\n'
printf 'Application database backup: %s\n' "$backup_file"
printf 'Open the n8n editor, create its local owner account, then run:\n'
printf '  make soar-install-workflows\n'
printf 'Wazuh forwarding remains disabled until workflow publication succeeds.\n'
