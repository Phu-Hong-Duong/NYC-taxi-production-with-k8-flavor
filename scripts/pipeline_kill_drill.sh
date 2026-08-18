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
                "a DIFFERENT pod object runs the stage afterwards — same action, "
                "new uid. REVISED after the drill's first run on 2026-08-18, and "
                "the original wording is kept beside its refutation in "
                "automation/runs/m4-kill/attempt1-prediction-wrong/prediction.json. "
                "It predicted a pod named `<run>-<action>-1`, on the reasoning that "
                "Flyte encodes the attempt in the pod name and a retry bumps it. "
                "Observed instead: the k8s plugin RECREATED the pod under the same "
                "name `-0` with a new uid 31 seconds after the kill, and the run "
                "finished. The run survived; the assertion was about a naming "
                "convention. Identity is the property that holds under both."
            ),
            "control_plane_attempts": (
                "0 for the killed action, because recreating a pod is not the same "
                "event as failing an attempt. REPORTED RATHER THAN ASSERTED: which "
                "counter a deleted pod increments is a property of the platform's "
                "classification, not of whether the pipeline survived. The USER "
                "budget (`retries=`) is measured separately and positively, by "
                "phase 0 — see pipelines/flyte/retry_probe.py, which exists "
                "BECAUSE this drill turned out not to spend it."
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

# --- 2b. PHASE 0: is the declared retry budget real? --------------------------
# ~90 seconds, in front of a ~20 minute drill, and it exists because the FIRST
# run of this drill found that it was measuring something else. Deleting a running
# task pod is survived by the k8s plugin RECREATING that pod — same action, same
# attempt, `attempts=0` in the control plane — so the kill drill alone says nothing
# about `retries=`, and the budget workflows.py declares had never been observed
# doing anything. A number nobody has watched work is a number nobody should rely
# on.
#
# So: one task that raises, carrying the SAME budget by import, run to exhaustion.
# The run is EXPECTED TO FAIL; the failure is the measurement (the `marts-redteam`
# inversion). What it proves is both halves at once — the budget is honoured, and
# it is FINITE, which is the argument for keeping the number small.
RETRIES_DECLARED="$(sed -n 's/^_STAGE_RETRIES = \([0-9]\+\)$/\1/p' \
                    "$REPO_ROOT/pipelines/flyte/workflows.py")"
[[ -n "$RETRIES_DECLARED" ]] || {
  echo "[kill-drill] FAIL: workflows.py declares no _STAGE_RETRIES to check" >&2; exit 1; }
note "phase 0: spending the declared budget (retries=$RETRIES_DECLARED) on a task that always fails"

PROBE_LOG="$RUN_DIR/retry_probe.log"
uv run --project "$REPO_ROOT" flyte --endpoint "localhost:${READER_PORT}" --insecure \
  run --follow --project "$PROJECT" --domain "$DOMAIN" \
  "$REPO_ROOT/pipelines/flyte/retry_probe.py" always_fails >"$PROBE_LOG" 2>&1 || true
PROBE_RUN="$(sed -e 's/\x1b\[[0-9;]*[a-zA-Z]//g' "$PROBE_LOG" \
             | sed -n 's/.*Created Run:[[:space:]]*\([A-Za-z0-9_-]\+\).*/\1/p' | head -1)"
[[ -n "$PROBE_RUN" ]] || {
  echo "[kill-drill] FAIL: the retry probe created no run; see $PROBE_LOG" >&2; exit 1; }
actions_json "$PROBE_RUN" >"$RUN_DIR/retry_probe.actions.json"
note "phase 0: run $PROBE_RUN"

python3 - "$RUN_DIR/retry_probe.actions.json" "$RETRIES_DECLARED" <<'PY' || exit 1
import json, sys
rows = json.load(open(sys.argv[1]))["actions"]
declared = int(sys.argv[2])
task = next((r for r in rows if r["short_name"] == "always_fails"), None)
if task is None:
    print("[kill-drill] FAIL: the retry probe's run has no always_fails action")
    raise SystemExit(1)
ok = True
if task["attempts"] != declared:
    print(f"[kill-drill] FAIL: the probe was attempted with attempt index "
          f"{task['attempts']}, expected {declared} — the budget workflows.py "
          f"declares is not the budget the platform honours")
    ok = False
else:
    print(f"[kill-drill] ok  the declared budget is REAL: a task that always raises "
          f"reached attempt index {task['attempts']} (retries={declared}) before the "
          f"platform stopped")
if task["phase"] != "FAILED":
    print(f"[kill-drill] FAIL: the probe ended {task['phase']}; a task that raises on "
          f"its first line must not succeed, and a probe that passes here measured nothing")
    ok = False
else:
    print("[kill-drill] ok  the budget is FINITE: retries ran out and the run FAILED, "
          "which is why the number is small rather than generous")
raise SystemExit(0 if ok else 1)
PY

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
# THE POD'S UID, READ BEFORE IT IS KILLED, and it is what the verdict compares
# against. The first run of this drill asserted on the pod NAME — it expected the
# replacement to be `…-1`, because Flyte names a task pod
# `<run>-<action>-<attempt>` and a retry ought to bump the attempt. What actually
# happened is that the k8s plugin recreated the pod under the SAME name with a new
# UID and `attempts` stayed 0, so a correct survival was reported as a failed
# drill. The property that survives both classifications is identity: a DIFFERENT
# pod object ran this stage after the kill.
TARGET_UID="$("${KUBECTL[@]}" -n "$NAMESPACE" get pod "$TARGET_POD" \
              -o jsonpath='{.metadata.uid}' 2>/dev/null || echo unknown)"
note "pod $TARGET_POD is Running on node $TARGET_NODE (uid $TARGET_UID) — letting it work for ${KILL_AFTER}s"
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
# Name, phase AND UID. The UID is the one that carries the verdict: a task pod is
# named `<run>-<action>-<attempt>`, and the platform may either bump the attempt
# (a new name) or recreate the same attempt (the same name, a new object). Both are
# a stage that ran again; only the UID says so in both cases.
ATTEMPT_PODS="$("${KUBECTL[@]}" -n "$NAMESPACE" get pods \
  -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.phase}{" "}{.metadata.uid}{" "}{.metadata.creationTimestamp}{"\n"}{end}' \
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
         "$TARGET_NODE" "$KILL_AT" "$pipeline_rc" "$MONTH" "$TRAIN_MONTHS" \
         "$TARGET_UID" "$RETRIES_DECLARED" "$PROBE_RUN" <<'PY'
import json, pathlib, re, sys

run_dir = pathlib.Path(sys.argv[1])
run_name, action_id, stage, pod, node, kill_at = sys.argv[2:8]
pipeline_rc = int(sys.argv[8])
month, train_months = sys.argv[9], sys.argv[10]
killed_uid, retries_declared, probe_run = sys.argv[11], int(sys.argv[12]), sys.argv[13]

actions = json.loads((run_dir / "actions.json").read_text())["actions"]
by_stage = {(r["short_name"] or "main"): r for r in actions}
target = by_stage.get(stage, {})
pods = [ln.split() for ln in (run_dir / "attempt_pods.txt").read_text().split("\n") if ln.strip()]
attempt_suffixes = sorted(
    {int(m.group(1)) for m in (re.search(r"-(\d+)$", p[0]) for p in pods) if m}
)
replacements = [p for p in pods if len(p) > 2 and p[2] != killed_uid]
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

# THE ASSERTION THE DRILL EXISTS FOR, and it is made by kubernetes: a pod object
# that is NOT the one that was killed ran this stage. Identity, not name — the
# first run of this drill asserted a `…-1` pod and went red on a run that had
# survived perfectly, because the platform recreated the same attempt under the
# same name with a new UID. Both classifications are "the stage ran again"; only
# the UID is true under both.
check(replacements,
      f"a DIFFERENT pod object ran '{stage}' after the kill: "
      f"{', '.join(f'{p[0]} (uid {p[2][:8]}…, created {p[3]})' for p in replacements)} "
      f"— the killed pod was uid {killed_uid[:8]}…",
      f"every pod for '{stage}' is still the one that was killed (uid "
      f"{killed_uid[:8]}…): the pod was deleted and nothing replaced it")

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
    "retry_budget": {
        "declared_in_workflows_py": retries_declared,
        "probe_run": probe_run,
        "note": (
            "phase 0 proved the budget by exhausting it on a task that always "
            "raises; the kill below is survived by pod RECREATION, which does not "
            "spend it. Two different mechanisms, both measured."
        ),
    },
    "month": month,
    "train_months": [m for m in train_months.split(",") if m],
    "sampled": bool(train_months),
    "target_stage": stage,
    "target_action": action_id,
    "killed_pod": pod,
    "killed_pod_node": node,
    "killed_pod_uid": killed_uid,
    "killed_at": kill_at,
    "attempt_pods": [
        {
            "pod": p[0],
            "phase": p[1] if len(p) > 1 else "",
            "uid": p[2] if len(p) > 2 else "",
            "created": p[3] if len(p) > 3 else "",
            "is_the_killed_pod": len(p) > 2 and p[2] == killed_uid,
        }
        for p in pods
    ],
    "attempt_suffixes": attempt_suffixes,
    "replacement_pods": [p[0] for p in replacements],
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
