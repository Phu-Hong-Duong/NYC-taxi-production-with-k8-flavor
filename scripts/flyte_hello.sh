#!/usr/bin/env bash
# flyte_hello.sh — run pipelines/flyte/hello.py ON THE CLUSTER, behind
# `make flyte-hello` (M4-S2's "ONE hello-workflow runs remotely to completion").
#
# WHY A SCRIPT AND NOT A DOCUMENTED COMMAND LINE. The endpoint is not a declared
# route (see scripts/flyte_console.sh for why Flyte gets no hostPort while the
# cluster is stateful), so every remote invocation has to stand up a
# port-forward, use it, and tear it down. A command a human has to remember to
# clean up after leaves a listener that makes the NEXT `make ports` lie.
#
# WHAT A PASS PROVES, precisely: the control plane accepted a task defined on
# this host, uploaded the code to the `flyte-data` bucket this story configured,
# scheduled a pod onto a kind node, ran it, moved its output through that same
# blob store into a SECOND task, and returned the final value here. Two tasks
# rather than one on purpose — one task passing only proves a pod ran.
#
# Usage: scripts/flyte_hello.sh              (via `make flyte-hello`)
#        FLYTE_HELLO_NAME=... to change the greeting argument
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
NAME="${FLYTE_HELLO_NAME:-crosstown}"
EXPECTED="HELLO ${NAME} FROM A FLYTE TASK"

# --- the split-horizon endpoint, and why the client needs its own -------------
# Flyte's blob store is ONE MinIO with TWO names. Pods reach it as
# `minio.platform.svc.cluster.local:9000` (in-cluster DNS, what
# infra/helm/flyte/values.yaml configures); this host reaches the same server as
# `localhost:9000` (the kind hostPort -> nodePort 30900 route from M0-S3). The
# CLI uploads its code bundle DIRECTLY to the object store, so with only the
# server's endpoint in hand it fails at upload with
# `ConnectError: [Errno -2] Name or service not known` — a DNS error for a name
# that is perfectly correct on the other side of the cluster boundary, three
# steps after the image and bundle succeeded, which reads like a storage outage
# and is not one.
# The SDK's own answer is client-side storage settings (flyte.storage.S3 maps
# these env vars onto its fields), so the two sides name the same bucket by the
# route each can actually take. Credentials are read from .env and never echoed.
# shellcheck disable=SC1090
set -a; source "${ENV_FILE:-$REPO_ROOT/.env}"; set +a
export FLYTE_AWS_ENDPOINT="${FLYTE_CLIENT_S3_ENDPOINT:-${MLFLOW_S3_ENDPOINT_URL:-http://localhost:9000}}"
export FLYTE_AWS_ACCESS_KEY_ID="$FLYTE_S3_ACCESS_KEY"
export FLYTE_AWS_SECRET_ACCESS_KEY="$FLYTE_S3_SECRET_KEY"

echo "== flyte hello (remote) =="
echo "[flyte-hello] client blob endpoint $FLYTE_AWS_ENDPOINT (pods use the in-cluster name; same MinIO)"
"${KUBECTL[@]}" -n "$NAMESPACE" port-forward "$SERVICE" "${LOCAL_PORT}:${REMOTE_PORT}" \
  >/tmp/flyte-hello-portforward.log 2>&1 &
pf_pid=$!
trap 'kill "$pf_pid" 2>/dev/null || true' EXIT

for _ in $(seq 1 20); do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 \
    "http://127.0.0.1:${LOCAL_PORT}/healthz" || true)"
  [[ "$code" == "200" ]] && break
  sleep 2
done
if [[ "${code:-000}" != "200" ]]; then
  echo "[flyte-hello] FAIL: the API did not answer through the forward (got '${code:-000}')" >&2
  exit 1
fi
echo "[flyte-hello] endpoint up: localhost:${LOCAL_PORT}"

# `--endpoint`/`--insecure` are ROOT options; `--project`/`--domain` belong to
# the SUBCOMMAND. Putting the latter on the root gives `No such option
# '--project'` — and `uv run --project` is a THIRD, unrelated `--project` (uv's
# own, meaning the python project directory). Three flags of the same name on one
# command line, two of which are wrong in any given position.
FLYTE=(uv run --project "$REPO_ROOT" flyte
       --endpoint "localhost:${LOCAL_PORT}" --insecure)
SCOPE=(--project "$PROJECT" --domain "$DOMAIN")

# Projects namespace runs, and a run into a project that does not exist fails at
# CODE UPLOAD with `project "nyc-taxi" not found` — after the image resolves and
# the bundle is built, which reads like a storage problem and is not one.
# `create project` takes `--id` and `--name`, not a positional. The first version
# of this line passed a positional and swallowed the error, so the run failed
# three steps later for a reason the transcript did not contain: hence the
# `create` output is now shown when it fails.
if "${FLYTE[@]}" get project 2>/dev/null | grep -qF -- "$PROJECT"; then
  echo "[flyte-hello] project '$PROJECT' already present"
else
  "${FLYTE[@]}" create project --id "$PROJECT" --name "$PROJECT" \
    --description "Crosstown ETA program (M4-S2)"
  echo "[flyte-hello] project '$PROJECT' created"
fi

# `|| rc=$?` rather than a bare substitution: under `set -e` a failing command
# inside `$( )` exits the script THERE, so the output that says why is discarded
# at exactly the moment it is wanted. Observed here on the first run — exit 2,
# not one line of diagnosis.
# `--follow` (`-f`) is what makes this an ACCEPTANCE test rather than a launch.
# Without it `flyte run` uploads, creates the run, prints its URL and exits 0 —
# so the script's own grep for the greeting was the only thing standing between
# "the orchestrator ran our work" and "the orchestrator accepted our work",
# which are different claims and the second one is cheap. With `--follow` the
# CLI waits for the run to reach a terminal state and prints its output, so a
# task that fails on-cluster fails this script.
rc=0
out="$("${FLYTE[@]}" run --follow "${SCOPE[@]}" \
       "$REPO_ROOT/pipelines/flyte/hello.py" main --name "$NAME" 2>&1)" || rc=$?
echo "$out"
if [[ "$rc" != "0" ]]; then
  echo "[flyte-hello] FAIL: \`flyte run\` exited $rc (output above)" >&2
  exit 1
fi

if ! grep -qiF -- "$EXPECTED" <<<"$out"; then
  echo "[flyte-hello] FAIL: the run did not return '$EXPECTED'" >&2
  exit 1
fi
echo "[flyte-hello] ok  two tasks ran on-cluster and the second consumed the first's output"
