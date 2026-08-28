#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$script_dir/common.sh"
load_runtime

evidence_dir="$project_dir/evidence/SOAR-001"
mkdir -p "$evidence_dir"

"$script_dir/healthcheck.sh" > "$evidence_dir/health.txt" 2>&1
"${compose[@]}" ps > "$evidence_dir/compose-status.txt"
"${compose[@]}" images > "$evidence_dir/container-images.txt"
"${compose[@]}" exec -T n8n n8n --version > "$evidence_dir/n8n-version.txt"
curl -fsS --max-time 10 \
  "http://127.0.0.1:${SOAR_CONTROLLER_PORT:-5680}/healthz" \
  | python3 -m json.tool > "$evidence_dir/controller-health.json"

python3 "$soar_dir/tools/soar_client.py" validate \
  > "$evidence_dir/live-validation.json"
python3 "$soar_dir/tools/soar_client.py" export "$evidence_dir"

printf 'integration_state=%s\n' "$(tr -d '[:space:]' < "$runtime_dir/integration.state")" \
  > "$evidence_dir/wazuh-forwarding-state.txt"

container_ids="$("${compose[@]}" ps -q)"
if [[ -n "$container_ids" ]]; then
  # shellcheck disable=SC2086
  docker stats --no-stream $container_ids > "$evidence_dir/resource-usage.txt"
fi

sha256sum \
  "$soar_dir/compose.yaml" \
  "$soar_dir/config/playbooks.json" \
  "$soar_dir/integrations/custom-sanolifood-soar" \
  "$soar_dir"/workflows/*.json \
  "$project_dir/app/src/sanolifood/soar"/*.py \
  "$project_dir/wazuh/config/manager/entrypoint/20-sanolifood-soar.sh" \
  > "$evidence_dir/configuration-sha256.txt"

printf 'SOAR evidence created in %s\n' "$evidence_dir"
printf 'Review it before Git. Runtime secrets, credentials and database contents were not collected.\n'
