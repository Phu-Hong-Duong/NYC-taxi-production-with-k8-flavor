#!/usr/bin/env bash
# pipeline_kill_drill.sh — delete the pod a stage is running in, mid-work, and
# prove the pipeline finishes anyway (M4-S5, the milestone's third §9 leg).
#
# Behind `make pipeline-kill-drill`. It is a GAMEDAY, so it obeys the gameday
# discipline this program adopts early (M6 owns the ritual; M4 owes the first
# rehearsal of it): the PREDICTED SIGNATURE IS WRITTEN TO DISK BEFORE THE KILL,
# and the verdict compares what happened against that file. A drill whose
# expectations are formed after the observation is not a drill, it is a
# description — and this program has already paid for assertions written to match
# a number that had already been seen (gotcha #50).
#
# WHAT IS BEING TESTED, precisely: the ORCHESTRATOR's retry. Not the model, not
# the gate, not a number. So the drill runs SAMPLED (`TRAIN_MONTHS` set), which
# makes it verdict-free by construction — F-008 honored rather than argued with,
# and the M4 kickoff names a sampled run as legal here for exactly this reason.
# Nothing here may promote: `run_pipeline.sh` reads `@champion` before and after
# and exits 2 if it moved, and this drill inherits that check by launching through
# it rather than around it.
#
# WHY IT KILLS THE `train` STAGE AND NOT A CHEAP ONE. The other five stages last
# between 3 and 14 seconds, so a kill against them tests whether this script can
# win a race. `train` is 31 minutes on full data and ~15 sampled, which is both
# long enough to hit reliably and the only stage whose loss would actually cost
# something — the honest target is the expensive one. The price is that the drill
# takes about as long as one pipeline plus one refit; run it detached (gotcha #45).
#
# WHY A FRESH MONTH. Five of six stages are cached, and a cache hit does not run
# in a pod — there would be nothing to kill and the drill would go green having
# tested nothing. So the default month is one this pipeline has never seen, and
# the verdict REFUSES to be green if the target stage came back CACHE_HIT. That is
# the same refusal the cache drill makes from the other side ("run 1 executed no
# stage"), and for the same reason: a drill that cannot fail proves nothing.
#
# IDEMPOTENCE IS WHY THIS IS SAFE, and it is not asserted here — it was earned:
#   ingest         M1-S1/M1-S2 — `make rebuild-proof`, 16/16 outputs byte-identical
#                  from the sha256-pinned raw, i.e. re-running it produces the
#                  same bytes, which is the strongest form of the property.
#   validate       reads the parquet back through the output contract. Pure.
#   build_features the ONE transform path (M2-S2); holds no state.
#   train          re-fits from the same data under the same config. Its honest
#                  cost on a retry is a LEFTOVER MLflow run from the killed
#                  attempt: the run is minted when the fit starts and the pod that
#                  would have closed it no longer exists. Named here rather than
#                  discovered by whoever next counts runs in `m4-pipeline`.
#   evaluate       reports what the one evaluator measured. Computes nothing.
#   register       reads the live registry; under M4's law it writes nothing.
#
# Usage: make pipeline-kill-drill                      (fresh month, ~35 min → detach)
#        MONTH=2019-03 make pipeline-kill-drill
#        KILL_STAGE=ingest make pipeline-kill-drill    (cheap, and a race — see above)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")
NAMESPACE="${FLYTE_NAMESPACE:-flyte}"
RELEASE="${FLYTE_RELEASE:-flyte}"
SERVICE="${FLYTE_SERVICE:-svc/${RELEASE}-flyte-binary-http}"
PROJECT="${FLYTE_PROJECT:-nyc-taxi}"
DOMAIN="${FLYTE_DOMAIN:-development}"
# A month the pipeline has never run, so nothing is cached and the kill lands on a
# pod that is really working. 2019-02 is a TRAIN-split month (configs/train.yaml),
# which keeps the drill inside the data the program already owns.
MONTH="${MONTH:-2019-02}"
# Sampled on purpose: same month as the data stage, so the run is verdict-free and
# the fit is one month rather than six.
TRAIN_MONTHS="${TRAIN_MONTHS:-$MONTH}"
KILL_STAGE="${KILL_STAGE:-train}"
# Seconds to let the target pod work before deleting it. Not zero: a pod killed in
# its first second tests container startup, not a stage losing work in flight.
KILL_AFTER="${KILL_AFTER:-120}"
# The drill's own reader route. Not 8090 — `run_pipeline.sh` binds that for the run
# it launches, and two tools on one port is an ordering nobody should have to know.
READER_PORT="${KILL_READER_PORT:-8092}"
RUN_DIR="${KILL_DRILL_DIR:-$REPO_ROOT/automation/runs/m4-kill}"
LAUNCH_TIMEOUT="${KILL_LAUNCH_TIMEOUT:-600}"

mkdir -p "$RUN_DIR"
note() { echo "[kill-drill] $*"; }

echo "== pipeline kill drill: month $MONTH, target stage '$KILL_STAGE' =="

# --- 1. THE PREDICTION, written before anything is launched -------------------
# It is a FILE and not an echo, because the verdict block below reads it back and
# reports predicted-vs-observed side by side. An expectation that lives only in a
# transcript is one a reader has to trust somebody did not edit afterwards.
PREDICTION="$RUN_DIR/prediction.json"
python3 - "$PREDICTION" "$MONTH" "$TRAIN_MONTHS" "$KILL_STAGE" "$KILL_AFTER" <<'PY'
import json, sys
path, month, train_months, stage, kill_after = sys.argv[1:6]
json.dump(
    {
        "written": "BEFORE the kill — this file is the drill's pre-registration",
        "month": month,
        "train_months": train_months,
        "target_stage": stage,
        "kill_after_seconds": int(kill_after),
        "predicted": {
            "what_is_killed": (
                "the pod named <run>-<action-id>-0, i.e. attempt 0 of the "
                f"'{stage}' action, deleted with `kubectl delete pod` while it is "
                "doing work"
            ),
            "orchestrator": (
                "Flyte marks that attempt failed and starts a second one; a NEW "
                "pod appears, named <run>-<action-id>-1. The attempt suffix is "
                "part of the pod name, so the retry is visible with `kubectl get "
                "pods` and does not depend on this script interpreting anything."
            ),
            "control_plane_attempts": (
                ">= 1 for the killed action. REPORTED RATHER THAN ASSERTED, and "
                "the reason is recorded here BEFORE the run so neither outcome can "
                "be presented afterwards as the one that was expected: Flyte "
                "distinguishes USER retries (governed by the task's `retries=`) "
                "from SYSTEM retries (network, container, k8s — governed by the "
                "platform). A pod deleted out from under a healthy container is "
                "plausibly either, and which counter it increments is a property "
                "of the platform's classification, not of whether the pipeline "
                "survived. The second pod and the completed run are the assertions."
            ),
            "run_outcome": (
                "the run reaches SUCCEEDED and its outputs carry a `decision` "
                "field — a NO_VERDICT decision, because the run is sampled"
            ),
            "stage_outcome": f"the '{stage}' action ends SUCCEEDED, having run twice",
            "champion": "unchanged — no M4 run may promote (kickoff law)",
            "known_cost": (
                "if the killed stage is `train`, the attempt that died leaves an "
                "MLflow run behind: the run is created when the fit starts and the "
                "process that would have ended it was killed. Expected, not a defect."
            ),
        },
    },
    open(path, "w"),
    indent=2,
)
print(f"[kill-drill] prediction written -> {path}")
PY
python3 -c "
import json,sys
p=json.load(open(sys.argv[1]))['predicted']
for k,v in p.items(): print(f'[kill-drill]   PREDICT {k}: {v}')
" "$PREDICTION"

# --- 2. the reader route ------------------------------------------------------
"${KUBECTL[@]}" -n "$NAMESPACE" port-forward "$SERVICE" "${READER_PORT}:8090" \
  >/tmp/flyte-kill-drill-portforward.log 2>&1 &
pf_pid=$!
trap 'kill "$pf_pid" 2>/dev/null || true' EXIT
for _ in $(seq 1 20); do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 \
    "http://127.0.0.1:${READER_PORT}/healthz" || true)"
  [[ "$code" == "200" ]] && break
  sleep 2
done
[[ "${code:-000}" == "200" ]] || { echo "[kill-drill] FAIL: no route to the Flyte API" >&2; exit 1; }

actions_json() {
  uv run --project "$REPO_ROOT" python "$REPO_ROOT/scripts/flyte_run_actions.py" \
    "$1" --endpoint "localhost:${READER_PORT}" --project "$PROJECT" --domain "$DOMAIN" \
    --json 2>/dev/null
}

# --- 3. launch the pipeline, in the background --------------------------------
# Through `run_pipeline.sh` and not around it: that script owns the F-026 image
# check, the PVC precondition, the alias read-back and the positive verdict
# assertion. A drill with its own launch path would be a second definition of what
# running this pipeline means, and the copy is always the one that drifts.
RUN_LOG="$RUN_DIR/pipeline.log"
FOLLOW_LOG="$RUN_DIR/flyte_run.log"
: >"$RUN_LOG"; : >"$FOLLOW_LOG"
MONTH="$MONTH" TRAIN_MONTHS="$TRAIN_MONTHS" PIPELINE_RUN_DIR="$RUN_DIR" \
  bash "$REPO_ROOT/scripts/run_pipeline.sh" >"$RUN_LOG" 2>&1 &
run_pid=$!
note "pipeline launched (pid $run_pid); transcript: $RUN_LOG"

# The run name appears in `flyte run --follow`'s first lines — and it is read from
# the FOLLOW log, not from run_pipeline.sh's stdout. That distinction cost this
# drill its first launch: `flyte run`'s output used to be captured into a shell
# variable, which does not exist until the command exits, so the file this loop
# polls stayed empty until the run it wanted to interrupt was already over. The
# fix is in run_pipeline.sh (it tees the follow output to `flyte_run.log`), and it
# is a better transcript for everyone, not only for this drill.
RUN_NAME=""
for _ in $(seq 1 "$LAUNCH_TIMEOUT"); do
  RUN_NAME="$(sed -e 's/\x1b\[[0-9;]*[a-zA-Z]//g' "$FOLLOW_LOG" \
              | sed -n 's/.*Created Run:[[:space:]]*\([A-Za-z0-9_-]\+\).*/\1/p' | head -1)"
  [[ -n "$RUN_NAME" ]] && break
  if ! kill -0 "$run_pid" 2>/dev/null; then
    echo "[kill-drill] FAIL: the pipeline exited before a run was created:" >&2
    tail -30 "$RUN_LOG" >&2
    exit 1
  fi
  sleep 1
done
[[ -n "$RUN_NAME" ]] || { echo "[kill-drill] FAIL: no run name after ${LAUNCH_TIMEOUT}s" >&2; exit 1; }
note "run $RUN_NAME"

# --- 4. wait for the target stage to be really running ------------------------
TARGET_ACTION=""
for _ in $(seq 1 "$LAUNCH_TIMEOUT"); do
  TARGET_ACTION="$(actions_json "$RUN_NAME" | python3 -c "
import json, sys
try:
    rows = json.load(sys.stdin)['actions']
except Exception:
    sys.exit(0)
for r in rows:
    if r['short_name'] == '$KILL_STAGE' and r['phase'] in ('RUNNING', 'SUCCEEDED'):
        print(r['action']); break
")"
  [[ -n "$TARGET_ACTION" ]] && break
  if ! kill -0 "$run_pid" 2>/dev/null; then
    echo "[kill-drill] FAIL: the pipeline finished before '$KILL_STAGE' was seen running" >&2
    tail -30 "$RUN_LOG" >&2
    exit 1
  fi
  sleep 5
done
[[ -n "$TARGET_ACTION" ]] || { echo "[kill-drill] FAIL: '$KILL_STAGE' never reached RUNNING" >&2; exit 1; }

TARGET_POD="${RUN_NAME}-${TARGET_ACTION}-0"
note "target action $TARGET_ACTION -> pod $TARGET_POD"

for _ in $(seq 1 120); do
  phase="$("${KUBECTL[@]}" -n "$NAMESPACE" get pod "$TARGET_POD" \
           -o jsonpath='{.status.phase}' 2>/dev/null || true)"
  [[ "$phase" == "Running" ]] && break
  sleep 5
done
if [[ "${phase:-}" != "Running" ]]; then
  echo "[kill-drill] FAIL: pod $TARGET_POD never reached Running (last: ${phase:-absent})" >&2
  exit 1
fi
TARGET_NODE="$("${KUBECTL[@]}" -n "$NAMESPACE" get pod "$TARGET_POD" \
               -o jsonpath='{.spec.nodeName}' 2>/dev/null || echo unknown)"
note "pod $TARGET_POD is Running on node $TARGET_NODE — letting it work for ${KILL_AFTER}s"
sleep "$KILL_AFTER"

# --- 5. the kill --------------------------------------------------------------
still="$("${KUBECTL[@]}" -n "$NAMESPACE" get pod "$TARGET_POD" \
         -o jsonpath='{.status.phase}' 2>/dev/null || true)"
if [[ "$still" != "Running" ]]; then
  echo "[kill-drill] FAIL: $TARGET_POD is '${still:-absent}' at kill time, not Running." >&2
  echo "[kill-drill]       The stage finished before the drill could kill it — nothing" >&2
  echo "[kill-drill]       was tested. Use a longer stage or a smaller KILL_AFTER." >&2
  exit 1
fi
KILL_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
note "KILLING $TARGET_POD at $KILL_AT"
"${KUBECTL[@]}" -n "$NAMESPACE" delete pod "$TARGET_POD" --wait=false
note "deleted; waiting for the run to finish"

# --- 6. wait for the pipeline to finish ---------------------------------------
set +e
wait "$run_pid"; pipeline_rc=$?
set -e
note "run_pipeline.sh exited $pipeline_rc"
grep -E "^\[pipeline\] (ok|FAIL|@champion)|^\[flyte\] " "$RUN_LOG" | sed 's/^/[kill-drill]   /' || true

# --- 7. what the cluster and the control plane saw ----------------------------
# The pods are listed by NAME, and the name is the evidence: Flyte names a task
# pod `<run>-<action>-<attempt>`, so a `-1` next to a `-0` is the retry, said by
# kubernetes rather than inferred from a log line.
ATTEMPT_PODS="$("${KUBECTL[@]}" -n "$NAMESPACE" get pods \
  -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.phase}{"\n"}{end}' \
  | grep "^${RUN_NAME}-${TARGET_ACTION}-" || true)"
echo "$ATTEMPT_PODS" | sed 's/^/[kill-drill]   pod /'
printf '%s\n' "$ATTEMPT_PODS" >"$RUN_DIR/attempt_pods.txt"

actions_json "$RUN_NAME" >"$RUN_DIR/actions.json"
uv run --project "$REPO_ROOT" python "$REPO_ROOT/scripts/flyte_run_actions.py" \
  "$RUN_NAME" --endpoint "localhost:${READER_PORT}" --project "$PROJECT" --domain "$DOMAIN" \
  | sed 's/^/[kill-drill] /'

# --- 8. the verdict -----------------------------------------------------------
set +e
python3 - "$RUN_DIR" "$RUN_NAME" "$TARGET_ACTION" "$KILL_STAGE" "$TARGET_POD" \
         "$TARGET_NODE" "$KILL_AT" "$pipeline_rc" "$MONTH" "$TRAIN_MONTHS" <<'PY'
import json, pathlib, re, sys

run_dir = pathlib.Path(sys.argv[1])
run_name, action_id, stage, pod, node, kill_at = sys.argv[2:8]
pipeline_rc = int(sys.argv[8])
month, train_months = sys.argv[9], sys.argv[10]

actions = json.loads((run_dir / "actions.json").read_text())["actions"]
by_stage = {(r["short_name"] or "main"): r for r in actions}
target = by_stage.get(stage, {})
pods = [ln.split() for ln in (run_dir / "attempt_pods.txt").read_text().split("\n") if ln.strip()]
attempt_suffixes = sorted(
    {int(m.group(1)) for m in (re.search(r"-(\d+)$", p[0]) for p in pods) if m}
)
transcript = (run_dir / "pipeline.log").read_text()

verdicts = []
def check(cond, good, bad):
    verdicts.append((bool(cond), good if cond else bad))

# The precondition that makes every other verdict mean something: the stage this
# drill killed must have RUN, not been served from the cache. A cache hit occupies
# no pod, so a green drill against one would be a drill that killed nothing.
check(target.get("cache_status") in {"CACHE_POPULATED", "CACHE_MISS", "CACHE_DISABLED"},
      f"'{stage}' really executed (cache_status {target.get('cache_status')}) — there "
      f"was a pod to kill",
      f"'{stage}' came back {target.get('cache_status')}: a cached stage runs in no pod, "
      f"so nothing was killed and this drill tested nothing. Use a month these stages "
      f"have never seen.")

# THE ASSERTION THE DRILL EXISTS FOR, and it is made by kubernetes: a second
# attempt's pod. Flyte encodes the attempt in the pod name, so this needs no
# interpretation of a status field whose semantics vary by failure class.
check(max(attempt_suffixes, default=-1) >= 1,
      f"a SECOND attempt pod exists: {', '.join(p[0].rsplit('-', 1)[1] for p in pods)} "
      f"(attempt suffixes {attempt_suffixes}) — the orchestrator re-ran '{stage}' "
      f"after the kill",
      f"only attempt(s) {attempt_suffixes} ever existed for '{stage}': the pod was "
      f"deleted and no retry was started")

check(target.get("phase") == "SUCCEEDED",
      f"'{stage}' ended SUCCEEDED despite losing its pod mid-work",
      f"'{stage}' ended {target.get('phase')}")

# The run's own product. `run_pipeline.sh` already asserts this positively (gotcha
# #59) and exits non-zero otherwise; the drill re-states it because "the retry
# happened" and "the pipeline finished" are two different claims.
check(pipeline_rc == 0,
      f"the pipeline completed (run_pipeline.sh exit {pipeline_rc}) — a killed pod "
      f"cost time, not the run",
      f"run_pipeline.sh exited {pipeline_rc}: the run did not survive the kill")
check("[pipeline] ok  @champion unchanged" in transcript,
      "@champion unchanged across the drill (read by run_pipeline.sh, before and after)",
      "the transcript does not contain run_pipeline.sh's alias-unchanged line")
check('"decision"' in transcript or "decision" in transcript,
      "the run produced a verdict object (NO_VERDICT — the drill is sampled, F-008)",
      "no decision in the run's outputs")

# Every OTHER stage must still have succeeded. A retry that rescued its own stage
# while the ones after it were skipped would satisfy every check above.
others = [n for n in by_stage if n != stage]
bad = [n for n in others if by_stage[n]["phase"] != "SUCCEEDED"]
check(not bad,
      f"the other {len(others)} action(s) all SUCCEEDED: {', '.join(sorted(others))}",
      f"these actions did not succeed: {', '.join(bad)}")

record = {
    "run_name": run_name,
    "month": month,
    "train_months": [m for m in train_months.split(",") if m],
    "sampled": bool(train_months),
    "target_stage": stage,
    "target_action": action_id,
    "killed_pod": pod,
    "killed_pod_node": node,
    "killed_at": kill_at,
    "attempt_pods": [{"pod": p[0], "phase": p[1] if len(p) > 1 else ""} for p in pods],
    "attempt_suffixes": attempt_suffixes,
    "control_plane_attempts": target.get("attempts"),
    "target_duration_s": round(target.get("duration_ms", 0) / 1000.0, 1),
    "pipeline_exit": pipeline_rc,
    "actions": actions,
}

# Predicted vs observed, side by side, on the one number the prediction file
# deliberately declined to assert.
print(f"[kill-drill] REPORTED (not asserted, see prediction.json): the control plane "
      f"recorded attempts={target.get('attempts')} for '{stage}'. A `kubectl delete pod` "
      f"is classified by the platform, not by this drill; the pod named `-1` is the "
      f"assertion.")

failures = [m for good, m in verdicts if not good]
for good, msg in verdicts:
    print(f"[kill-drill] {'ok  ' if good else 'FAIL: '}{msg}")

record["verdicts"] = len(verdicts)
record["failures"] = len(failures)
(run_dir / "kill_drill.json").write_text(json.dumps(record, indent=2))
print(f"[kill-drill] record -> {run_dir / 'kill_drill.json'}")
print(f"[kill-drill] {len(verdicts) - len(failures)}/{len(verdicts)} verdicts passed")
sys.exit(1 if failures else 0)
PY
py_rc=$?
set -e

if [[ "$py_rc" != "0" ]]; then
  echo "[kill-drill] DRILL FAILED" >&2
  exit 1
fi
echo "[kill-drill] GREEN — a stage lost its pod mid-work and the pipeline still finished"
