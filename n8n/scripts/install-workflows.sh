#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$script_dir/common.sh"
load_runtime

"$script_dir/healthcheck.sh"

workflow_files=(
  00-error-handler.json
  01-alert-intake.json
  02-analyst-decision.json
  03-expiration-rollback.json
  04-health-metrics.json
)
workflow_ids=(
  SfSoarError0701
  SfSoarIntake071
  SfSoarDecision1
  SfSoarExpiry071
  SfSoarHealth071
)

printf 'Importing versioned SOAR workflows into the existing n8n owner project...\n'
for workflow_file in "${workflow_files[@]}"; do
  "${compose[@]}" exec -T n8n \
    n8n import:workflow --input="/opt/sanolifood/workflows/${workflow_file}"
done

printf 'Publishing workflows in dependency order...\n'
for workflow_id in "${workflow_ids[@]}"; do
  "${compose[@]}" exec -T n8n n8n publish:workflow --id="$workflow_id"
done

"${compose[@]}" restart n8n >/dev/null
container_id="$("${compose[@]}" ps -q n8n)"
for _ in $(seq 1 60); do
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' "$container_id")"
  [[ "$health" == "healthy" ]] && break
  sleep 2
done
health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' "$container_id")"
[[ "$health" == "healthy" ]] || {
  printf 'n8n did not become healthy after workflow publication.\n' >&2
  exit 1
}

printf 'enabled\n' > "$runtime_dir/integration.state"
chmod 0600 "$runtime_dir/integration.state"

printf 'Enabling authenticated Wazuh forwarding after successful publication...\n'
if ! "$project_dir/wazuh/scripts/reload-rules.sh"; then
  printf 'disabled\n' > "$runtime_dir/integration.state"
  "$project_dir/wazuh/scripts/reload-rules.sh" >/dev/null 2>&1 || true
  printf 'Wazuh forwarding was rolled back because manager reload failed.\n' >&2
  exit 1
fi

wazuh_env="$project_dir/wazuh/runtime/.env"
wazuh_compose="$project_dir/wazuh/compose.yaml"
if [[ -f "$wazuh_env" ]]; then
  if ! docker compose --env-file "$wazuh_env" -f "$wazuh_compose" exec -T wazuh.manager \
    sh -c "test -x /var/ossec/integrations/custom-sanolifood-soar && grep -q '<name>custom-sanolifood-soar</name>' /var/ossec/etc/ossec.conf"; then
    "$script_dir/disable-integration.sh" >/dev/null 2>&1 || true
    printf 'Wazuh forwarding was rolled back because integration verification failed.\n' >&2
    exit 1
  fi
fi

if ! "$script_dir/healthcheck.sh"; then
  "$script_dir/disable-integration.sh" >/dev/null 2>&1 || true
  printf 'Wazuh forwarding was rolled back because the final healthcheck failed.\n' >&2
  exit 1
fi
printf '\nSOAR workflows are published and Wazuh forwarding is enabled.\n'
printf 'Run make soar-validate-live before changing SOAR_RESPONSE_MODE from dry-run.\n'
