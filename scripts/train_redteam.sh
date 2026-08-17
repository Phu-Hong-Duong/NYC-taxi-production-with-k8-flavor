#!/usr/bin/env bash
# M2-S3 · role:MLE — prove the promotion gate can say NO.
#
# A gate that has only ever been watched saying yes is a gate nobody has seen
# work. This submits a DELIBERATELY hobbled challenger (train labels permuted;
# val and test untouched) through exactly the path `make train` uses — same fit,
# same evaluator, same gate, promotion ENABLED — and expects a refusal.
#
# The exit code is inverted deliberately, the way `RED_TEAM=1 scripts/marts.sh`
# is: here the refusal IS the result, and a PASS would mean the gate admitted a
# model fitted to noise. Promotion is left enabled on purpose — the proof is that
# the GATE stopped it, not that a flag did.
#
#   scripts/train_redteam.sh              (make train-redteam)
#   TRANSCRIPT=path scripts/train_redteam.sh   tee the run somewhere quotable
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
HOBBLE="${HOBBLE:-shuffled-target}"
TRANSCRIPT="${TRANSCRIPT:-}"

echo "== RED TEAM: a challenger hobbled with '$HOBBLE' goes through the REAL gate =="
echo "== A pass here would mean the gate admits a model fitted to permuted labels. =="
echo

registry_state() {
  uv run python - <<'PY'
import mlflow
from taxi_mlops.data.config import load_yaml
from taxi_mlops.training import tracking
cfg = load_yaml("configs/train.yaml")
tracking.configure(cfg["mlflow"])
client = mlflow.MlflowClient()
name = cfg["registry"]["model_name"]
alias = cfg["registry"]["champion_alias"]
try:
    versions = client.search_model_versions(f"name='{name}'")
except Exception:
    versions = []
print(f"registered_model={name} versions={sorted(int(v.version) for v in versions)}")
for v in sorted(versions, key=lambda v: int(v.version)):
    print(f"  version={v.version} run_id={v.run_id}")
# The alias is read through get_model_version_by_alias and NOT off the version
# objects: search_model_versions returns them with `aliases` empty (observed on
# server 3.15.1), so a snapshot built from that field would be blind to exactly
# the mutation this red team is checking for.
try:
    print(f"  alias @{alias} -> version {client.get_model_version_by_alias(name, alias).version}")
except Exception:
    print(f"  alias @{alias} -> UNSET")
PY
}

echo "-- registry BEFORE the red team --"
BEFORE="$(registry_state)"
echo "$BEFORE"
echo

set +e
if [[ -n "$TRANSCRIPT" ]]; then
  uv run python -m taxi_mlops.training train --hobble "$HOBBLE" 2>&1 | tee "$TRANSCRIPT"
  STATUS=${PIPESTATUS[0]}
else
  uv run python -m taxi_mlops.training train --hobble "$HOBBLE"
  STATUS=$?
fi
set -e

echo
echo "-- registry AFTER the red team --"
AFTER="$(registry_state)"
echo "$AFTER"
echo

if [[ "$STATUS" -eq 0 ]]; then
  echo "[train-redteam] RED-TEAM FAILED: the gate PROMOTED a model hobbled with '$HOBBLE'." >&2
  echo "[train-redteam] The gate is not gating. Do not trust the champion alias." >&2
  exit 1
fi
if [[ "$STATUS" -ne 1 ]]; then
  echo "[train-redteam] RED-TEAM INCONCLUSIVE: exit $STATUS is not the gate's refusal (1)." >&2
  echo "[train-redteam] Something failed BEFORE the verdict; the gate was never asked." >&2
  exit "$STATUS"
fi
if [[ "$BEFORE" != "$AFTER" ]]; then
  echo "[train-redteam] RED-TEAM FAILED: the registry CHANGED across a refusal." >&2
  echo "[train-redteam] A refused challenger must leave it exactly as it found it." >&2
  exit 1
fi

echo "[train-redteam] RED-TEAM PASSED: the gate REFUSED the hobbled challenger (exit 1),"
echo "[train-redteam] printing both numbers above, and the registry is byte-for-byte the"
echo "[train-redteam] state it was in before the run. The hobbled MLflow run is kept and"
echo "[train-redteam] clearly marked (tags red_team / hobbled / do_not_promote) — a deleted"
echo "[train-redteam] refusal cannot be checked by anyone who was not watching it happen."
