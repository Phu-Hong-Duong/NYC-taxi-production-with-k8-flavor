#!/usr/bin/env bash
# pipeline_cache_drill.sh — the SAME invocation twice, and the proof that the
# second one reused the first (M4-S4, the milestone's second leg).
#
# Behind `make pipeline-cache-drill`. It runs `scripts/run_pipeline.sh` twice with
# identical inputs and then asks THREE independent systems whether the second run
# actually re-used the first, because each one alone is refutable:
#
#   1. THE CONTROL PLANE — every action carries a `cache_status`, and the five
#      cacheable stages of run 2 must read CACHE_HIT. This is the claim; the other
#      two corroborate it. It is read with scripts/flyte_run_actions.py, which asks
#      the server what it recorded rather than inferring from a transcript.
#   2. THE CLOCK — run 2's wall-clock must be a fraction of run 1's. This is the
#      leg the kickoff names ("a wall-clock a fraction of run 1"), and it is the
#      WEAKEST of the three on its own: a faster second run is equally consistent
#      with a machine that was simply less busy. It is kept because it is what a
#      human notices, and because a cache that is "hit" while costing the same time
#      is a cache that is lying about something else.
#   3. MLFLOW — a re-executed train stage MINTS A RUN. So the experiment's run
#      count must be IDENTICAL before and after run 2, measured on a different
#      server, in a different database, by code that knows nothing about Flyte.
#      This is the strongest leg: it can fail while legs 1 and 2 both pass, and if
#      it ever does, the cache is not saving the fit — it is hiding a second one.
#
# And one property that is not about caching at all: `@champion` must read the same
# version after both runs. `register` is deliberately uncached (it reads the live
# registry), so run 2 re-derives its verdict from a CACHED manifest — which is the
# only reason that leg means anything: a cached input that no longer means what it
# meant would show up here and in no cache_status field.
#
# CHEAP MODE: `DRILL_STAGE=ingest make pipeline-cache-drill` runs ONE stage twice
# instead of the whole pipeline (~1 minute against ~35). It exists because the
# expensive drill should never be the first thing to discover that caching is
# misconfigured — the same reason `make flyte-hello` exists next to `make
# pipeline`. It proves the mechanism, not the milestone, and it says so.
#
# WHAT IT DOES NOT DO: it never promotes (run_pipeline.sh reads `@champion` before
# and after each run and exits 2 if it moved), never deletes, and mutates no
# cluster state beyond the two runs themselves.
#
# Usage: make pipeline-cache-drill                        (full, ~35 min → detach it)
#        DRILL_STAGE=ingest make pipeline-cache-drill     (mechanism probe, ~1 min)
#        MONTH=2019-02 make pipeline-cache-drill
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")
NAMESPACE="${FLYTE_NAMESPACE:-flyte}"
RELEASE="${FLYTE_RELEASE:-flyte}"
SERVICE="${FLYTE_SERVICE:-svc/${RELEASE}-flyte-binary-http}"
PROJECT="${FLYTE_PROJECT:-nyc-taxi}"
DOMAIN="${FLYTE_DOMAIN:-development}"
MONTH="${MONTH:-2019-01}"
TRAIN_MONTHS="${TRAIN_MONTHS:-}"
DRILL_STAGE="${DRILL_STAGE:-}"
# A port of its OWN, and not 8090: `run_pipeline.sh` stands up its own forward on
# 8090 and kills it on EXIT, so a drill holding that port would make every run it
# launches fail to bind. Two tools, two ports, no ordering to remember.
READER_PORT="${DRILL_READER_PORT:-8091}"
RUN_DIR="${CACHE_DRILL_DIR:-$REPO_ROOT/automation/runs/m4-cache}"
PIPELINE_RECORD="$REPO_ROOT/automation/runs/m4-pipeline/pipeline_run.json"
EXPERIMENT="${DRILL_EXPERIMENT:-m4-pipeline}"
# Run 2 must come in under this share of run 1's wall-clock. Deliberately loose:
# the number that matters is CACHE_HIT, and a tight bound here would turn a busy
# laptop into a red drill.
MAX_RATIO="${DRILL_MAX_RATIO:-0.50}"

mkdir -p "$RUN_DIR"
note() { echo "[cache-drill] $*"; }

echo "== pipeline cache drill: $MONTH${DRILL_STAGE:+ (MECHANISM PROBE, stage: $DRILL_STAGE — not the milestone's evidence)} =="

# --- the reader's route, stood up first because the cheap mode launches through it
"${KUBECTL[@]}" -n "$NAMESPACE" port-forward "$SERVICE" "${READER_PORT}:8090" \
  >/tmp/flyte-cache-drill-portforward.log 2>&1 &
pf_pid=$!
trap 'kill "$pf_pid" 2>/dev/null || true' EXIT
for _ in $(seq 1 20); do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 \
    "http://127.0.0.1:${READER_PORT}/healthz" || true)"
  [[ "$code" == "200" ]] && break
  sleep 2
done
[[ "${code:-000}" == "200" ]] || { echo "[cache-drill] FAIL: no route to the Flyte API" >&2; exit 1; }

# The client's blob-store route — the host side of F-023's split horizon, needed
# only by the cheap mode (the full mode's runs are launched by run_pipeline.sh,
# which sets this up for itself). Credentials come from .env and are never echoed.
# shellcheck disable=SC1090
set -a; source "${ENV_FILE:-$REPO_ROOT/.env}"; set +a
export FLYTE_AWS_ENDPOINT="${FLYTE_CLIENT_S3_ENDPOINT:-${MLFLOW_S3_ENDPOINT_URL:-http://localhost:9000}}"
export FLYTE_AWS_ACCESS_KEY_ID="$FLYTE_S3_ACCESS_KEY"
export FLYTE_AWS_SECRET_ACCESS_KEY="$FLYTE_S3_SECRET_KEY"

# --- the MLflow leg's BEFORE reading -------------------------------------------
mlflow_run_count() {
  { uv run --project "$REPO_ROOT" python - "$EXPERIMENT" <<'PY' 2>/dev/null || echo "UNREADABLE"
import sys
import mlflow
from taxi_mlops.data.config import load_yaml
from taxi_mlops.training import tracking
tracking.configure(load_yaml("configs/train.yaml")["mlflow"])
client = mlflow.MlflowClient()
exp = client.get_experiment_by_name(sys.argv[1])
print(0 if exp is None else len(client.search_runs([exp.experiment_id], max_results=50000)))
PY
  } | tail -1
}

# --- one invocation, timed -----------------------------------------------------
# `time` is not used: the drill needs the number as a value, not as a line of
# stderr somebody has to parse.
run_once() {
  local label="$1" logfile="$RUN_DIR/$1.log" t0 t1
  t0=$(date +%s)
  if [[ -n "$DRILL_STAGE" ]]; then
    uv run --project "$REPO_ROOT" flyte --endpoint "localhost:${READER_PORT}" --insecure \
      run --follow --project "$PROJECT" --domain "$DOMAIN" \
      "$REPO_ROOT/pipelines/flyte/workflows.py" "$DRILL_STAGE" --month "$MONTH" \
      >"$logfile" 2>&1 || true
    RUN_NAME="$(sed -e 's/\x1b\[[0-9;]*[a-zA-Z]//g' "$logfile" \
                | sed -n 's/.*Created Run:[[:space:]]*\([A-Za-z0-9_-]\+\).*/\1/p' | head -1)"
    python3 -c "
import json
json.dump({'run_name': '$RUN_NAME', 'month': '$MONTH', 'stage': '$DRILL_STAGE',
           'champion_after': 'NOT-READ (stage-only probe)'},
          open('$RUN_DIR/$label.json','w'), indent=2)
"
  else
    MONTH="$MONTH" TRAIN_MONTHS="$TRAIN_MONTHS" \
      bash "$REPO_ROOT/scripts/run_pipeline.sh" >"$logfile" 2>&1 || true
    # The run's identity comes from the record run_pipeline.sh writes, not from
    # this script re-parsing the same CLI output a second time — two parsers of
    # one format is a twin, and the copy is always the one that drifts.
    RUN_NAME="$(python3 -c "
import json
print(json.load(open('$PIPELINE_RECORD'))['run_name'])
")"
    cp "$PIPELINE_RECORD" "$RUN_DIR/$label.json"
  fi
  t1=$(date +%s)
  ELAPSED=$((t1 - t0))
  note "$label: run ${RUN_NAME:-UNKNOWN} in ${ELAPSED}s (transcript: $logfile)"
  grep -E "^\[pipeline\] (ok|FAIL)|^\[flyte\] " "$logfile" | sed 's/^/[cache-drill]   /' || true
  [[ -n "$RUN_NAME" ]] || { echo "[cache-drill] FAIL: $label produced no run name" >&2; exit 1; }
}

mlflow_before="$(mlflow_run_count)"
note "MLflow experiment '$EXPERIMENT' holds $mlflow_before run(s) before the drill"

run_once run1; run1_elapsed="$ELAPSED"; run1_name="$RUN_NAME"
mlflow_mid="$(mlflow_run_count)"
note "MLflow after run 1: $mlflow_mid run(s)"

run_once run2; run2_elapsed="$ELAPSED"; run2_name="$RUN_NAME"
mlflow_after="$(mlflow_run_count)"
note "MLflow after run 2: $mlflow_after run(s)"

if [[ "$run1_name" == "$run2_name" ]]; then
  echo "[cache-drill] FAIL: both legs report run $run1_name — run 2 never launched" >&2
  exit 1
fi

for leg in run1 run2; do
  name="$(python3 -c "import json;print(json.load(open('$RUN_DIR/$leg.json'))['run_name'])")"
  uv run --project "$REPO_ROOT" python "$REPO_ROOT/scripts/flyte_run_actions.py" \
    "$name" --endpoint "localhost:${READER_PORT}" --project "$PROJECT" --domain "$DOMAIN" \
    --json > "$RUN_DIR/$leg.actions.json"
  echo "[cache-drill] --- $leg ($name) ---"
  uv run --project "$REPO_ROOT" python "$REPO_ROOT/scripts/flyte_run_actions.py" \
    "$name" --endpoint "localhost:${READER_PORT}" --project "$PROJECT" --domain "$DOMAIN" \
    | sed 's/^/[cache-drill] /'
done

set +e
python3 - "$RUN_DIR" "$run1_elapsed" "$run2_elapsed" "$mlflow_before" "$mlflow_mid" \
         "$mlflow_after" "$MAX_RATIO" "$DRILL_STAGE" <<'PY'
import json, pathlib, sys

run_dir = pathlib.Path(sys.argv[1])
e1, e2 = int(sys.argv[2]), int(sys.argv[3])
mlf_before, mlf_mid, mlf_after = sys.argv[4], sys.argv[5], sys.argv[6]
max_ratio = float(sys.argv[7])
stage_only = sys.argv[8]

a1 = json.loads((run_dir / "run1.actions.json").read_text())["actions"]
a2 = json.loads((run_dir / "run2.actions.json").read_text())["actions"]

# `main` and `register` are uncached BY DESIGN and each argues its own case in
# pipelines/flyte/workflows.py. They are NAMED here rather than derived as
# "whatever came back disabled": if a stage silently loses its cache, this list is
# what turns that into a FAIL instead of into a quietly smaller expectation.
UNCACHED = {"main", "register"}

def by_stage(rows):
    return {(r["short_name"] or "main"): r for r in rows}

s1, s2 = by_stage(a1), by_stage(a2)
cacheable = sorted(n for n in s2 if n not in UNCACHED)
verdicts = []

def check(cond, good, bad):
    verdicts.append((bool(cond), good if cond else bad))

check(cacheable,
      f"run 2 exposed {len(cacheable)} cacheable stage(s): {', '.join(cacheable)}",
      "run 2 exposed no cacheable stage — the drill measured nothing")

for name in cacheable:
    was = s1.get(name, {})
    check(s2[name]["cache_status"] == "CACHE_HIT",
          f"{name}: run 2 CACHE_HIT (run 1 {was.get('cache_status', '?')}), "
          f"{was.get('duration_ms', 0) / 1000:.1f}s -> {s2[name]['duration_ms'] / 1000:.1f}s",
          f"{name}: run 2 cache_status is {s2[name]['cache_status']}, expected CACHE_HIT")
    check(was.get("cache_status") in {"CACHE_POPULATED", "CACHE_HIT"},
          f"{name}: run 1 {was.get('cache_status')} — it is what run 2 hit",
          f"{name}: run 1 reports {was.get('cache_status')}, so run 2's hit came "
          f"from somewhere this drill did not create")

for name in sorted(UNCACHED & set(s2)):
    check(s2[name]["cache_status"] == "CACHE_DISABLED",
          f"{name}: CACHE_DISABLED in run 2 — uncached on purpose, and still is",
          f"{name} reports {s2[name]['cache_status']} — it is supposed to be uncached")

ratio = (e2 / e1) if e1 else 1.0
check(ratio <= max_ratio,
      f"wall-clock {e1}s -> {e2}s ({ratio:.1%} of run 1, bar {max_ratio:.0%})",
      f"wall-clock {e1}s -> {e2}s ({ratio:.1%}) is not under {max_ratio:.0%} of run 1")

if stage_only:
    print("[cache-drill] NOTE: stage-only probe — the MLflow and @champion legs are "
          "not applicable and were not run. This proves the MECHANISM, not the milestone.")
else:
    check(mlf_after != "UNREADABLE" and mlf_after == mlf_mid,
          f"MLflow gained NO run across run 2 ({mlf_mid} -> {mlf_after}) — the fit did not "
          f"re-execute, and that is said by a different server than the one claiming the hit",
          f"MLflow went {mlf_mid} -> {mlf_after} across run 2: a cached train stage must "
          f"not mint a run")
    check(mlf_mid != mlf_before,
          f"run 1 DID fit ({mlf_before} -> {mlf_mid} MLflow runs) — run 2's saving is real",
          f"run 1 minted no MLflow run either ({mlf_before} -> {mlf_mid}); run 1 was itself "
          f"a cache hit, so this drill compares two reruns and proves nothing about cost")
    v1 = json.loads((run_dir / "run1.json").read_text())
    v2 = json.loads((run_dir / "run2.json").read_text())
    check(v1["champion_after"] == v2["champion_after"],
          f"@champion is version {v2['champion_after']} after both runs",
          f"@champion differs across the drill: {v1['champion_after']} vs {v2['champion_after']}")

failures = [m for good, m in verdicts if not good]
for good, msg in verdicts:
    print(f"[cache-drill] {'ok  ' if good else 'FAIL: '}{msg}")

(run_dir / "cache_drill.json").write_text(json.dumps({
    "run1": {"name": json.loads((run_dir / "run1.json").read_text())["run_name"],
             "seconds": e1, "actions": a1},
    "run2": {"name": json.loads((run_dir / "run2.json").read_text())["run_name"],
             "seconds": e2, "actions": a2},
    "wall_clock_ratio": round(ratio, 4),
    "mlflow_runs": {"before": mlf_before, "after_run1": mlf_mid, "after_run2": mlf_after},
    "stage_only": stage_only or None,
    "verdicts": len(verdicts),
    "failures": len(failures),
}, indent=2))
print(f"[cache-drill] record -> {run_dir / 'cache_drill.json'}")
print(f"[cache-drill] {len(verdicts) - len(failures)}/{len(verdicts)} verdicts passed")
sys.exit(1 if failures else 0)
PY
py_rc=$?
set -e

if [[ "$py_rc" != "0" ]]; then
  echo "[cache-drill] DRILL FAILED" >&2
  exit 1
fi
echo "[cache-drill] GREEN — the rerun reused run 1, and three systems agree"
