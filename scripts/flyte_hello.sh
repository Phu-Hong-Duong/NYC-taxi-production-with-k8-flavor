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

echo "== flyte hello (remote) =="
"${KUBECTL[@]}" -n "$NAMESPACE" port-forward "$SERVICE" "${LOCAL_PORT}:${REMOTE_PORT}" \
  >/tmp/flyte-hello-portforward.log 2>&1 &
pf_pid=$!
trap 'kill "$pf_pid" 2>/dev/null || true' EXIT

for _ in $(seq 1 20); do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 \
    "http://127.0.0.1:${LOCAL_PORT}/healthcheck" || true)"
  [[ "$code" == "200" ]] && break
  sleep 2
done
if [[ "${code:-000}" != "200" ]]; then
  echo "[flyte-hello] FAIL: the API did not answer through the forward (got '${code:-000}')" >&2
  exit 1
fi
echo "[flyte-hello] endpoint up: localhost:${LOCAL_PORT}"

FLYTE=(uv run --project "$REPO_ROOT" flyte
       --endpoint "localhost:${LOCAL_PORT}" --insecure
       --project "$PROJECT" --domain "$DOMAIN")

# Projects are namespaces for runs; creating one is idempotent in intent, so a
# second run must not fail on "already exists".
"${FLYTE[@]}" create project "$PROJECT" >/dev/null 2>&1 \
  && echo "[flyte-hello] project '$PROJECT' created" \
  || echo "[flyte-hello] project '$PROJECT' already present (or creation refused; the run below is the real check)"

out="$("${FLYTE[@]}" run "$REPO_ROOT/pipelines/flyte/hello.py" main --name "$NAME" 2>&1)"
echo "$out"

if ! grep -qiF "$EXPECTED" <<<"$out"; then
  echo "[flyte-hello] FAIL: the run did not return '$EXPECTED'" >&2
  exit 1
fi
echo "[flyte-hello] ok  two tasks ran on-cluster and the second consumed the first's output"
