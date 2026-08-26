#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
wazuh_dir="$(cd -- "$script_dir/.." && pwd)"
project_dir="$(cd -- "$wazuh_dir/.." && pwd)"
env_file="$wazuh_dir/runtime/.env"
evidence_dir="$project_dir/evidence/WAZ-001"

[[ -f "$env_file" ]] || { printf 'Run make wazuh-bootstrap first.\n' >&2; exit 1; }
mkdir -p "$evidence_dir"

set -a
# shellcheck disable=SC1090
source "$env_file"
set +a
compose=(docker compose --env-file "$env_file" -f "$wazuh_dir/compose.yaml")

"${compose[@]}" ps > "$evidence_dir/compose-status.txt"
"${compose[@]}" images > "$evidence_dir/container-images.txt"
"$script_dir/healthcheck.sh" > "$evidence_dir/health.txt" 2>&1
"${compose[@]}" exec -T wazuh.manager /var/ossec/bin/wazuh-control status \
  > "$evidence_dir/manager-status.txt" 2>&1 || true
"${compose[@]}" exec -T wazuh.indexer sh -c \
  'curl -sk --fail -u "admin:$INDEXER_PASSWORD" https://127.0.0.1:9200/_cluster/health?pretty' \
  > "$evidence_dir/indexer-cluster-health.json"
"${compose[@]}" exec -T wazuh.manager sh -c \
  'tail -n 50 /var/log/sanolifood/sanolifood.jsonl' \
  > "$evidence_dir/sanolifood-log-sample.jsonl"

{
  for sample_file in "$wazuh_dir"/tests/events/*.json; do
    printf '\n===== %s =====\n' "$(basename "$sample_file")"
    "${compose[@]}" exec -T wazuh.manager /var/ossec/bin/wazuh-logtest < "$sample_file"
  done
} > "$evidence_dir/ruleset-tests.txt" 2>&1

"${compose[@]}" exec -T wazuh.manager sh -c \
  'if test -f /var/ossec/logs/alerts/alerts.json; then grep -F "\"id\":\"1100" /var/ossec/logs/alerts/alerts.json | tail -n 30 || true; fi' \
  > "$evidence_dir/sanolifood-alerts.jsonl"

container_ids="$("${compose[@]}" ps -q)"
if [[ -n "$container_ids" ]]; then
  # shellcheck disable=SC2086
  docker stats --no-stream $container_ids > "$evidence_dir/resource-usage.txt"
fi

sha256sum \
  "$wazuh_dir/compose.yaml" \
  "$wazuh_dir/config/manager/ossec.conf" \
  "$wazuh_dir/config/manager/shared/sanolifood-linux/agent.conf" \
  "$wazuh_dir/config/manager/shared/sanolifood-windows/agent.conf" \
  "$wazuh_dir/config/indexer/wazuh.indexer.yml" \
  "$wazuh_dir/config/dashboard/opensearch_dashboards.yml" \
  "$wazuh_dir/rules/sanolifood_rules.xml" \
  > "$evidence_dir/configuration-sha256.txt"

docker run --rm \
  --volume "$wazuh_dir/runtime/certs:/certs:ro" \
  --entrypoint sh \
  nginx:1.28.0-alpine3.21 \
  -c 'find /certs -maxdepth 1 -type f -name "*.pem" ! -name "*key*" -exec sha256sum {} \; | sort' \
  > "$evidence_dir/public-certificates-sha256.txt"

printf 'Evidencia textual creada en %s\n' "$evidence_dir"
printf 'Revisa los archivos antes de incorporarlos a Git. No se recopilaron credenciales ni claves privadas.\n'
printf 'Las capturas sugeridas están documentadas en README.md, sección Evidencias y validación.\n'
