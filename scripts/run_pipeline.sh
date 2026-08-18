#!/usr/bin/env bash
# run_pipeline.sh — the six-stage pipeline ON THE CLUSTER, behind
# `make pipeline MONTH=YYYY-MM` (M4-S4).
#
# It is a script for the same reason scripts/flyte_hello.sh is: Flyte has no
# declared route while the cluster is stateful (adding a hostPort means a
# rebuild, and since M2 the PVCs hold the only copy of the registry), so every
# remote invocation has to stand up a port-forward, use it and tear it down. A
# documented command line leaves a listener behind that makes the next
# `make ports` lie.
#
# THE STANDING LAW THIS SCRIPT OBEYS: no run of this pipeline moves `@champion`.
# It is not enforced by a flag here — a law with a flag is a default (M4-S1). It
# is enforced in `pipelines.tasks.train`, which passes `promote=False`
# unconditionally and has no promote parameter, and in `pipelines.tasks.register`,
# whose promoting branch raises. This script reads the alias BEFORE and AFTER and
# fails if it moved, which is the check that would catch a future third path.
#
# SAMPLED RUNS GET NO VERDICT (F-008). `TRAIN_MONTHS=` set to anything makes the
# run sampled, and a sampled run is passed `judge=false`: the floor is fitted on
# the same shrunken data as the challenger, so sampling makes the gate EASIER to
# pass (measured at M2-S3: margin 7.07% -> 16.85% on one train month). "Not
# judged" and "judged and satisfied" must never be confused by a pipeline.
#
# Usage: scripts/run_pipeline.sh                       (via `make pipeline`)
#        MONTH=2019-02 scripts/run_pipeline.sh
#        TRAIN_MONTHS=2019-01 scripts/run_pipeline.sh  (sampled smoke, no verdict)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")
NAMESPACE="${FLYTE_NAMESPACE:-flyte}"
RELEASE="${FLYTE_RELEASE:-flyte}"
SERVICE="${FLYTE_SERVICE:-svc/${RELEASE}-flyte-binary-http}"
LOCAL_PORT="${FLYTE_LOCAL_PORT:-8090}"
REMOTE_PORT="${FLYTE_REMOTE_PORT:-8090}"
PROJECT="${FLYTE_PROJECT:-nyc-taxi}"
DOMAIN="${FLYTE_DOMAIN:-development}"
MONTH="${MONTH:-2019-01}"
TRAIN_MONTHS="${TRAIN_MONTHS:-}"
# The marts tail task (M4-S5, D-003). ON by default — the monthly pipeline is the
# publish's home from M4 on, and an opt-in tail is a tail nobody runs. The two
# ORCHESTRATOR drills set this to 0: the cache drill and the kill drill are about
# Flyte's behaviour, and republishing 7.5M warehouse rows twice per drill would add
# minutes to their wall-clock (which the cache drill measures as evidence) for no
# extra coverage of the thing under test.
PUBLISH_MARTS="${PUBLISH_MARTS:-1}"
RUN_DIR="${PIPELINE_RUN_DIR:-$REPO_ROOT/automation/runs/m4-pipeline}"

# A sampled run is verdict-free BY CONSTRUCTION, not by the caller remembering.
if [[ -n "$TRAIN_MONTHS" ]]; then
  JUDGE="false"; JUDGE_FLAG="--no-judge"
  echo "[pipeline] SAMPLED run (train months: $TRAIN_MONTHS) — F-008: no verdict will be issued"
else
  JUDGE="true"; JUDGE_FLAG="--judge"
  echo "[pipeline] FULL-DATA run (train months: whatever configs/train.yaml names)"
fi

if [[ "$PUBLISH_MARTS" == "1" ]]; then
  PUBLISH_FLAG="--publish"
  echo "[pipeline] marts tail task ON — the run ends by republishing the warehouse"
else
  PUBLISH_FLAG="--no-publish"
  echo "[pipeline] marts tail task OFF (PUBLISH_MARTS=0) — the warehouse is not touched"
fi

# The client's blob-store route, and it is the OTHER side of the split horizon
# F-023 named. The server signs upload URLs with the endpoint
# infra/helm/flyte/values.yaml sets under `signedUrl.stowConfigOverride`; this
# host takes the kind hostPort -> nodePort 30900 route to the same MinIO.
# Credentials come from .env and are never echoed.
# shellcheck disable=SC1090
set -a; source "${ENV_FILE:-$REPO_ROOT/.env}"; set +a
export FLYTE_AWS_ENDPOINT="${FLYTE_CLIENT_S3_ENDPOINT:-${MLFLOW_S3_ENDPOINT_URL:-http://localhost:9000}}"
export FLYTE_AWS_ACCESS_KEY_ID="$FLYTE_S3_ACCESS_KEY"
export FLYTE_AWS_SECRET_ACCESS_KEY="$FLYTE_S3_SECRET_KEY"

mkdir -p "$RUN_DIR"

echo "== pipeline: $MONTH =="
IMAGE_REF="$(python3 -c "
import json, pathlib, sys
p = pathlib.Path('$REPO_ROOT/automation/runs/m4-image/image.json')
if not p.exists():
    sys.exit('no task image manifest — run: make image-load')
print(json.loads(p.read_text())['image_ref'])
")"
echo "[pipeline] task image $IMAGE_REF"

# --- F-026: the image is where the MODEL CODE comes from, and nothing said so ---
# `flyte run` defaults to `--copy-style loaded_modules`, so the code bundle carries
# only what is imported AT REGISTRATION — observed 22 files, against 36 `.py` files
# in `src/taxi_mlops` alone. Every stage body imports `pipelines.tasks` (and through
# it `taxi_mlops`) INSIDE the function, so the modules that compute every number in
# this pipeline arrive in the TASK IMAGE. Its tag is read out of a manifest that
# only `make image-load` rewrites — so editing `src/`, committing, and running this
# script executes the PREVIOUS code and prints a green transcript.
#
# The line above used to promise that "a pull error here means the tree moved",
# which is a protection that does not exist: M4-S3's loud-`ImagePullBackOff`
# property fires for a tag no node holds, and a stale manifest names a tag every
# node holds. So the check is made explicitly, and it is SCOPED to the paths that
# reach a pod only through the image. `pipelines/` is deliberately absent — that IS
# the code bundle, so an edit there does reach the pod, and refusing on it would
# have refused this story's own cache drill. A guard that fires when nothing is
# wrong is a guard that gets deleted (gotcha #50).
#
# M4-S5 WIDENED THE LIST, because the marts tail task moved two more directories
# behind the same door. `scripts/marts_publish.py` is loaded BY PATH from inside the
# task pod, and the dbt project under `analytics/` — models, tests, seeds, profile —
# has no other way to reach a pod at all: it is not importable, so no `--copy-style`
# would ever carry it. An edit to a mart's SQL with a stale image publishes the
# PREVIOUS model definition and reconciles perfectly against it.
IMAGE_SHA="${IMAGE_REF##*:}"
IMAGE_PATHS=(src pyproject.toml uv.lock docker scripts analytics)
if [[ "${IMAGE_DRIFT_OK:-0}" == "1" ]]; then
  echo "[pipeline] WARN: IMAGE_DRIFT_OK=1 — not checking whether image $IMAGE_SHA carries this tree's code"
elif [[ "$IMAGE_SHA" == *-dirty ]]; then
  echo "[pipeline] FAIL: the image was built from a DIRTY tree ($IMAGE_SHA), so what it" >&2
  echo "[pipeline]       carries cannot be identified. Commit, then: make image-load" >&2
  exit 3
elif ! git -C "$REPO_ROOT" cat-file -e "${IMAGE_SHA}^{commit}" 2>/dev/null; then
  echo "[pipeline] WARN: image tag '$IMAGE_SHA' is not a commit in this repo — drift unverifiable"
else
  drift="$(git -C "$REPO_ROOT" diff --name-only "$IMAGE_SHA" HEAD -- "${IMAGE_PATHS[@]}")"
  dirty="$(git -C "$REPO_ROOT" status --porcelain -- "${IMAGE_PATHS[@]}")"
  if [[ -n "$drift$dirty" ]]; then
    echo "[pipeline] FAIL: the task image predates the source it would run (F-026)." >&2
    echo "[pipeline]       image $IMAGE_SHA vs HEAD $(git -C "$REPO_ROOT" rev-parse --short HEAD), differing under ${IMAGE_PATHS[*]}:" >&2
    { [[ -n "$drift" ]] && sed 's/^/[pipeline]         committed: /' <<<"$drift"; } >&2 || true
    { [[ -n "$dirty" ]] && sed 's/^/[pipeline]         uncommitted: /' <<<"$dirty"; } >&2 || true
    echo "[pipeline]       These reach a task pod ONLY through the image, so this run would" >&2
    echo "[pipeline]       compute its numbers with the old code. Fix: make image-load" >&2
    echo "[pipeline]       (IMAGE_DRIFT_OK=1 waives this, and says so in the transcript.)" >&2
    exit 3
  fi
  echo "[pipeline] ok  image $IMAGE_SHA carries this tree's ${IMAGE_PATHS[*]} (F-026 checked)"
fi

# The data has to be on the volume before a task looks for it. Cheap to assert,
# expensive to discover from inside a pod as a FileNotFoundError three stages in.
if ! "${KUBECTL[@]}" -n "$NAMESPACE" get pvc taxi-data >/dev/null 2>&1; then
  echo "[pipeline] FAIL: PVC taxi-data does not exist — run 'make stage-data' first" >&2
  exit 1
fi

"${KUBECTL[@]}" -n "$NAMESPACE" port-forward "$SERVICE" "${LOCAL_PORT}:${REMOTE_PORT}" \
  >/tmp/flyte-pipeline-portforward.log 2>&1 &
pf_pid=$!
trap 'kill "$pf_pid" 2>/dev/null || true' EXIT

for _ in $(seq 1 20); do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 \
    "http://127.0.0.1:${LOCAL_PORT}/healthz" || true)"
  [[ "$code" == "200" ]] && break
  sleep 2
done
if [[ "${code:-000}" != "200" ]]; then
  echo "[pipeline] FAIL: the Flyte API did not answer through the forward (got '${code:-000}')" >&2
  exit 1
fi

FLYTE=(uv run --project "$REPO_ROOT" flyte
       --endpoint "localhost:${LOCAL_PORT}" --insecure)
SCOPE=(--project "$PROJECT" --domain "$DOMAIN")

# --- the alias, BEFORE ---------------------------------------------------------
# Read from the registry, not from a config file: the law is about what is
# SERVING, and configs/train.yaml only records what was promoted last.
# The alias is read through `get_model_version_by_alias` and NOT off the objects
# `search_model_versions` returns: on server 3.15.1 those come back with `aliases`
# EMPTY, so a snapshot built from that field would be blind to exactly the
# mutation this check exists to catch (M2-S3 found that, the hard way).
# `tail -1` and not the whole output: `tracking.configure()` prints three banner
# lines to stdout before anything here runs, so capturing the command wholesale
# makes the "alias" a four-line blob — which then compares EQUAL to itself before
# and after and reports "ok @champion unchanged" no matter what happened. A check
# that cannot fail is worse than no check (gotcha #50's shape), and this one was
# caught by its own transcript printing a paragraph where a version goes.
champion_alias() {
  { uv run --project "$REPO_ROOT" python - <<'PY' 2>/dev/null || echo 'UNREADABLE'
import mlflow
from taxi_mlops.data.config import load_yaml
from taxi_mlops.training import tracking
cfg = load_yaml("configs/train.yaml")
tracking.configure(cfg["mlflow"])
client = mlflow.MlflowClient()
name, alias = cfg["registry"]["model_name"], cfg["registry"]["champion_alias"]
try:
    print(client.get_model_version_by_alias(name, alias).version)
except Exception:
    print("UNSET")
PY
  } | tail -1
}

champion_before="$(champion_alias)"
echo "[pipeline] @champion before: $champion_before"

rc=0
# The follow output goes to a FILE and is read back, rather than being captured
# straight into a variable. Two reasons, and the second is the one that forced it:
#
#   1. A command substitution holds everything until the command EXITS, so for the
#      31 minutes of a full-data run the transcript exists nowhere a human (or
#      another script) can look. §9 of docs/pipeline_m4.md is a whole section about
#      per-stage detail that had to be recovered from the server because it was
#      never written down; this is the same problem one layer earlier.
#   2. The kill drill (M4-S5) has to learn the run's NAME while the run is still
#      going, because it cannot delete a pod belonging to a run it cannot name.
#      With the output buffered in a variable it polled a file that stayed empty
#      until the very thing it was waiting to interrupt had already finished.
FOLLOW_LOG="$RUN_DIR/flyte_run.log"
: >"$FOLLOW_LOG"
"${FLYTE[@]}" run --follow "${SCOPE[@]}" \
  "$REPO_ROOT/pipelines/flyte/workflows.py" main \
  --month "$MONTH" --train_months "$TRAIN_MONTHS" "$JUDGE_FLAG" "$PUBLISH_FLAG" \
  >"$FOLLOW_LOG" 2>&1 || rc=$?
out="$(cat "$FOLLOW_LOG")"
echo "$out"

RUN_NAME="$(sed -e 's/\x1b\[[0-9;]*[a-zA-Z]//g' <<<"$out" \
            | sed -n 's/.*Created Run:[[:space:]]*\([A-Za-z0-9_-]\+\).*/\1/p' | head -1)"

# --- the alias, AFTER ----------------------------------------------------------
# Read unconditionally, INCLUDING on a failed run: "the pipeline crashed" and
# "the pipeline crashed after moving the alias" are different incidents and the
# second one must not be discoverable only by someone who thought to look.
champion_after="$(champion_alias)"
echo "[pipeline] @champion after:  $champion_after"

if [[ "$champion_before" != "$champion_after" ]]; then
  echo "[pipeline] FAIL: @champion MOVED ($champion_before -> $champion_after). No M4 run may promote." >&2
  exit 2
fi
echo "[pipeline] ok  @champion unchanged at $champion_after"

if [[ -n "$RUN_NAME" ]]; then
  # The run's own record, written where a successor session (or verify-m4) can
  # read it without a port-forward and without parsing this transcript.
  python3 - "$RUN_DIR/pipeline_run.json" "$RUN_NAME" "$MONTH" "$TRAIN_MONTHS" \
           "$JUDGE" "$IMAGE_REF" "$champion_after" "$rc" <<'PY'
import json, sys
path, run, month, train_months, judge, image, champion, rc = sys.argv[1:9]
json.dump(
    {
        "run_name": run,
        "month": month,
        "train_months": [m for m in train_months.split(",") if m],
        "judged": judge == "true",
        "image_ref": image,
        "champion_after": champion,
        "cli_exit": int(rc),
        "project": "nyc-taxi",
        "domain": "development",
    },
    open(path, "w"),
    indent=2,
)
print(f"[pipeline] run record -> {path}")
PY
fi

if [[ "$rc" != "0" ]]; then
  echo "[pipeline] FAIL: \`flyte run\` exited $rc (output above)" >&2
  exit 1
fi

if [[ -z "$RUN_NAME" ]]; then
  echo "[pipeline] FAIL: could not find the run name in \`flyte run\` output" >&2
  exit 1
fi

# The verdict is the run's OUTPUT, read back out of the blob store — not scraped
# off a log line. A task that printed the right thing and returned nothing is a
# task that did not produce a verdict (the flyte-hello lesson, applied here).
io="$("${FLYTE[@]}" get io "${SCOPE[@]}" "$RUN_NAME" --outputs-only 2>&1)" || {
  echo "$io"; echo "[pipeline] FAIL: could not read the run's outputs" >&2; exit 1; }
echo "$io"

# THE ASSERTION THAT MAKES THIS A CHECK, and it was added because its absence
# printed a green line over a dead run. `flyte run --follow` EXITS 0 when the run
# it followed FAILED — observed 2026-08-18, run rkfzd2sf9zb7r45prvsm died on
# ErrImagePull and this script said "ok … six stages on-cluster". Every signal
# available was consistent with success: exit code 0, a run name, a readable
# outputs blob. The only thing that differed was the CONTENT of the outputs
# (`ActionOutputs(o0=None)`), because a failed workflow returns nothing.
#
# So the check is POSITIVE and about the thing the pipeline exists to produce:
# the register stage's verdict, which is a JSON object with a `decision`. That is
# strictly stronger than asserting a phase string — a run can reach SUCCEEDED and
# still be asserted against here if it ever stops emitting a verdict — and it
# cannot be satisfied by a stage that merely printed something (gotcha #51: ask of
# any self-assertion whether the component could tell if it were false).
if ! grep -qF -- '"decision"' <<<"$io"; then
  # ANSI stripped for the failure message only: the CLI draws its output in a box
  # with colour, and pasting that raw into an error line makes the one thing the
  # reader needs (o0=None) unfindable in a wall of escape codes.
  echo "[pipeline] FAIL: the run produced no verdict — its outputs were:" >&2
  sed -e 's/\x1b\[[0-9;]*[a-zA-Z]//g' <<<"$io" >&2
  echo "[pipeline]       (a FAILED run returns o0=None; \`flyte run\` exits 0 either way)" >&2
  exit 1
fi

# The stage count is DERIVED, not typed. It said "six stages" for a month after the
# graph grew a seventh, which is the smallest possible version of a transcript that
# describes something other than what ran — and the reason it went unnoticed is that
# nothing reads a summary line for information. `pipelines.tasks.STAGES` is the one
# declaration of the graph, so the line quotes it and tells the truth about the tail.
ran="$(python3 -c "
import re, pathlib
src = pathlib.Path('$REPO_ROOT/pipelines/tasks.py').read_text()
names = re.search(r'STAGES: tuple\[str, \.\.\.\] = \(([^)]*)\)', src).group(1)
n = len([x for x in re.findall(r'\"([a-z_]+)\"', names)])
print(n if '$PUBLISH_MARTS' == '1' else n - 1)
")"
echo "[pipeline] ok  run $RUN_NAME completed; $ran stage(s) on-cluster for $MONTH" \
     "(marts tail $([[ "$PUBLISH_MARTS" == "1" ]] && echo ON || echo OFF))"
