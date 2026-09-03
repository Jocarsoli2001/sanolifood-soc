#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd -- "$script_dir/../.." && pwd)"
evaluation_dir="$project_dir/evaluation"
results_dir="$evaluation_dir/results"
evidence_dir="$project_dir/evidence/EVAL-001"

cd "$project_dir"
python3 "$evaluation_dir/tools/evalctl.py" summary >/dev/null

[[ -s "$results_dir/results.csv" && -s "$results_dir/summary.json" ]] || {
  printf 'No evaluation results are available.\n' >&2
  exit 1
}

python3 - "$results_dir/summary.json" <<'PY'
import json
import sys
from pathlib import Path

summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected = {f"SCN-{number:03d}" for number in range(1, 9)}
completed = set(summary.get("complete_scenarios", []))
if completed != expected:
    missing = ", ".join(sorted(expected - completed)) or "none"
    raise SystemExit(f"Evaluation campaign is incomplete; missing: {missing}")
if summary.get("pending_decision_count"):
    raise SystemExit("Evaluation campaign still has runs awaiting an analyst decision")
if summary.get("live_verified_run_count", 0) < 1:
    raise SystemExit(
        "Complete at least one supervised live run with verified effect and restoration before EVAL-001"
    )
PY

mkdir -p "$evidence_dir/runs"
cp "$evaluation_dir/config/scenarios.json" "$evidence_dir/scenario-catalog.json"
cp "$results_dir/results.csv" "$evidence_dir/results.csv"
cp "$results_dir/summary.json" "$evidence_dir/summary.json"
cp "$results_dir/summary.md" "$evidence_dir/summary.md"

find "$results_dir/runs" -mindepth 1 -maxdepth 1 -type d -print0 \
  | while IFS= read -r -d '' run_dir; do
      run_name="${run_dir##*/}"
      mkdir -p "$evidence_dir/runs/$run_name"
      for artifact in result.json scenario.json stimulus-receipt.json wazuh-alert.json soar-incident.json live-control-verification.json rollback-receipts.json rollback-errors.json; do
        [[ -f "$run_dir/$artifact" ]] && cp "$run_dir/$artifact" "$evidence_dir/runs/$run_name/$artifact"
      done
    done

make soc-health > "$evidence_dir/health.txt" 2>&1
python3 "$evaluation_dir/scripts/validate-static.py" > "$evidence_dir/static-validation.txt"
docker stats --no-stream > "$evidence_dir/resource-usage.txt"
docker compose ps > "$evidence_dir/application-compose-status.txt"
docker compose --env-file wazuh/runtime/.env -f wazuh/compose.yaml ps \
  > "$evidence_dir/wazuh-compose-status.txt"
docker compose --env-file n8n/runtime/.env -f n8n/compose.yaml ps \
  > "$evidence_dir/soar-compose-status.txt"
{
  git status -sb
  git log -1 --oneline --decorate
  date -u +%Y-%m-%dT%H:%M:%SZ
} > "$evidence_dir/repository-state.txt"

find evaluation/config evaluation/scripts evaluation/tools scenarios \
  endpoints/scripts/validate-linux.sh endpoints/windows/Test-SanoliFoodEndpoint.ps1 \
  -type f -print0 \
  | sort -z \
  | xargs -0 sha256sum > "$evidence_dir/configuration-sha256.txt"

printf 'Evaluation evidence created in %s\n' "$evidence_dir"
printf 'Review it before Git. Credentials, runtime secrets and database contents were not collected.\n'
