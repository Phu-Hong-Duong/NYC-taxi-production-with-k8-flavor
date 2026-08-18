#!/usr/bin/env bash
# flyte_actions.sh — read a run's per-stage detail off the control plane, behind
# `make flyte-actions RUN=<name>` (M4-S5).
#
# `scripts/flyte_run_actions.py` is the reader (M4-S4 wrote it when a full-data
# run's per-stage detail turned out to exist nowhere but the server: `flyte run
# --follow` had logged `Scrolled 2 lines`). It needs an endpoint, and Flyte has no
# declared route while the cluster is stateful — so every reader until now had to
# stand up its own port-forward inline, which is why the same seven lines exist in
# `run_pipeline.sh` and in both drills.
#
# This is those seven lines, once, for the case where a human (or `verify-m4`) wants
# a run's stages after the fact. It READS: the reader is pinned by a test that it
# calls nothing which launches, aborts or deletes, and this wrapper adds nothing.
#
# Usage: make flyte-actions RUN=rw98pj84z4jh5ldqrxqp
#        make flyte-actions RUN=… ACTIONS_ARGS=--json
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")
NAMESPACE="${FLYTE_NAMESPACE:-flyte}"
RELEASE="${FLYTE_RELEASE:-flyte}"
SERVICE="${FLYTE_SERVICE:-svc/${RELEASE}-flyte-binary-http}"
# 8092, not 8090 or 8091: those belong to `run_pipeline.sh` and to the drills, and
# a reader that steals a port from a run in flight is a reader that breaks the thing
# it was asked to describe.
PORT="${ACTIONS_PORT:-8092}"
RUN="${RUN:?usage: make flyte-actions RUN=<run-name>}"

"${KUBECTL[@]}" -n "$NAMESPACE" port-forward "$SERVICE" "${PORT}:8090" \
  >/tmp/flyte-actions-portforward.log 2>&1 &
pf_pid=$!
trap 'kill "$pf_pid" 2>/dev/null || true' EXIT

for _ in $(seq 1 20); do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 \
    "http://127.0.0.1:${PORT}/healthz" || true)"
  [[ "$code" == "200" ]] && break
  sleep 2
done
if [[ "${code:-000}" != "200" ]]; then
  echo "[actions] FAIL: the Flyte API did not answer through the forward (got '${code:-000}')" >&2
  exit 1
fi

uv run --project "$REPO_ROOT" python "$REPO_ROOT/scripts/flyte_run_actions.py" \
  "$RUN" --endpoint "localhost:${PORT}" ${ACTIONS_ARGS:-}
