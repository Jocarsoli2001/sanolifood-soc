#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$script_dir/common.sh"
load_runtime

backup_root="$project_dir/backups/soar"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
destination="$backup_root/$timestamp"
mkdir -p "$destination"
chmod 0700 "$backup_root" "$destination"

"${compose[@]}" exec -T soar-db pg_dump \
  --username n8n --dbname n8n --format=custom --no-owner --no-acl \
  > "$destination/n8n-database.dump"
"${compose[@]}" exec -T soar-db pg_dump \
  --username soar_app --dbname soar --format=custom --no-owner --no-acl \
  > "$destination/soar-database.dump"
cp "$env_file" "$destination/runtime.env"
chmod 0600 "$destination"/*

sha256sum "$destination"/* > "$destination/SHA256SUMS"
printf 'SOAR configuration and database backup created in %s\n' "$destination"
printf 'The backup contains secrets and is excluded from Git; store it in a protected location.\n'
