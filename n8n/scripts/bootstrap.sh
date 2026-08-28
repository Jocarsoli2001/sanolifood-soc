#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$script_dir/common.sh"

"$script_dir/preflight.sh"
load_runtime

app_compose=(docker compose --env-file "$project_dir/.env" -f "$project_dir/compose.yaml")
app_container_id="$("${app_compose[@]}" ps -q app)"
[[ -n "$app_container_id" ]] || {
  printf 'The SanoliFood application is not running. Run make up first.\n' >&2
  exit 1
}
container_token="$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' \
  "$app_container_id" | sed -n 's/^SOAR_INTERNAL_TOKEN=//p')"
if [[ "$container_token" != "$SOAR_INTERNAL_TOKEN" ]]; then
  printf 'Synchronizing the application with the generated SOAR service token...\n'
  "${app_compose[@]}" up -d --force-recreate --no-deps \
    --wait --wait-timeout 240 app nginx
fi

docker network inspect sanoli_soar >/dev/null 2>&1 \
  || docker network create --internal sanoli_soar >/dev/null

"${compose[@]}" config --quiet
printf 'Pulling pinned SOAR images...\n'
"${compose[@]}" pull soar-db n8n
printf 'Starting n8n, the case database and the SOAR controller...\n'
if ! "${compose[@]}" up -d --wait --wait-timeout 420; then
  printf '\nSOAR startup did not reach container readiness. Diagnostic state:\n' >&2
  "${compose[@]}" ps -a >&2 || true
  "${compose[@]}" logs --tail=80 n8n soar-controller soar-db >&2 || true
  exit 1
fi
if ! "$script_dir/healthcheck.sh"; then
  printf '\nContainers started, but the host access path failed. Port diagnostics:\n' >&2
  for service_name in n8n soar-controller; do
    container_id="$("${compose[@]}" ps -q "$service_name")"
    [[ -n "$container_id" ]] || continue
    docker inspect --format \
      '{{.Name}} configured={{json .HostConfig.PortBindings}} runtime={{json .NetworkSettings.Ports}}' \
      "$container_id" >&2 || true
  done
  exit 1
fi

printf '\nSOAR services are running in %s mode.\n' "$SOAR_RESPONSE_MODE"
printf 'From the administration PC, create an SSH tunnel:\n'
printf '  ssh -L %s:127.0.0.1:%s USUARIO@IP_DE_UBUNTU\n' \
  "${SOAR_PUBLIC_PORT:-5678}" "${SOAR_PUBLIC_PORT:-5678}"
printf 'Then open http://127.0.0.1:%s and create the first n8n owner account.\n' \
  "${SOAR_PUBLIC_PORT:-5678}"
printf 'After the owner exists, run: make soar-install-workflows\n'
printf 'Wazuh forwarding remains disabled until that command succeeds.\n'
