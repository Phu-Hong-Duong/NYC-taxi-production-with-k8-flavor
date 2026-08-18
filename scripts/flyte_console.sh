#!/usr/bin/env bash
# flyte_console.sh — reach Flyte from the host, behind `make flyte-console` (M4-S2).
#
# THE RECORDED DEVIATION. Everywhere else in this program a route is DECLARED,
# never port-forwarded: a kind hostPort mapped onto a Service's fixed nodePort,
# twins across two files, checked by a unit test (CLAUDE.md "How a host port
# reaches a service"). Flyte does not get one, and the reason is not laziness:
#   * kind publishes host ports at cluster-CREATE time ONLY. Declaring 8080 means
#     `kind delete` + `kind create`.
#   * Since M2 this cluster is STATEFUL. Its PVCs hold the only copy of the
#     MLflow registry (champion versions 1 and 2), every artifact in MinIO, the
#     Metabase app-db and both M3 Optuna studies. `make verify-m2` and
#     `make verify-m3` read that state live, so a rebuild turns two green gates
#     permanently red. The M4 kickoff's top law forbids it.
# So port 8080 stays RESERVED in CLAUDE.md's port family — unclaimed, waiting for
# the next PO-sanctioned rebuild, when the declared route costs nothing extra.
# The doctrine is not repealed; it is deferred, with the date and the reason.
#
# WHAT THIS FORWARDS, AND WHAT IT HONESTLY CANNOT. It forwards the Flyte **API**
# (service flyte-flyte-binary-http, port 8090) — the endpoint the SDK and CLI
# talk to, and therefore the one M4-S4's `make pipeline` needs. It does NOT
# forward the browser console, because forwarding it would not work: the console
# is a static SPA that calls the API SAME-ORIGIN (the chart's own values say so),
# so on its own localhost port it renders and then fails every request. Making it
# work needs an ingress putting both behind one host, and this cluster has no
# ingress CONTROLLER yet (`kubectl get ingressclass` -> No resources found; one
# arrives with KServe at M5). Printing a URL that loads a broken page would be
# worse than saying this out loud.
#
# Usage:
#   scripts/flyte_console.sh           # blocking port-forward; Ctrl-C to stop
#   scripts/flyte_console.sh --check   # one-shot: forward, probe, tear down
# Exit: 0 ok · 1 the API did not answer.
set -euo pipefail

CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")
NAMESPACE="${FLYTE_NAMESPACE:-flyte}"
RELEASE="${FLYTE_RELEASE:-flyte}"
SERVICE="${FLYTE_SERVICE:-svc/${RELEASE}-flyte-binary-http}"
LOCAL_PORT="${FLYTE_LOCAL_PORT:-8090}"
REMOTE_PORT="${FLYTE_REMOTE_PORT:-8090}"
MODE="${1:-serve}"

if [[ "$MODE" == "--check" ]]; then
  # Forward in the background, probe, and always tear the tunnel down — a check
  # that leaves a listener behind would make the NEXT run's port pre-check lie.
  "${KUBECTL[@]}" -n "$NAMESPACE" port-forward "$SERVICE" "${LOCAL_PORT}:${REMOTE_PORT}" \
    >/tmp/flyte-portforward.log 2>&1 &
  pf_pid=$!
  trap 'kill "$pf_pid" 2>/dev/null || true' EXIT

  code=000
  for _ in $(seq 1 20); do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 \
      "http://127.0.0.1:${LOCAL_PORT}/healthz" || true)"
    [[ "$code" == "200" ]] && break
    sleep 2
  done
  if [[ "$code" != "200" ]]; then
    echo "[flyte-console] FAIL: /healthz through the forward returned '$code' (expected 200)" >&2
    sed -n '1,20p' /tmp/flyte-portforward.log >&2 || true
    exit 1
  fi
  echo "[flyte-console] ok  API answers: GET /healthz -> 200 (svc ${SERVICE}:${REMOTE_PORT})"
  exit 0
fi

cat <<EOM
[flyte-console] forwarding the Flyte API to http://127.0.0.1:${LOCAL_PORT}
[flyte-console]   health:  curl http://127.0.0.1:${LOCAL_PORT}/healthz
[flyte-console]   the SDK/CLI endpoint for M4-S4's \`make pipeline\`
[flyte-console] the BROWSER console is not forwarded and would not work if it were
[flyte-console]   (same-origin SPA; needs an ingress, and no ingress controller
[flyte-console]    exists in this cluster until KServe brings one at M5).
[flyte-console] Ctrl-C to stop.
EOM
exec "${KUBECTL[@]}" -n "$NAMESPACE" port-forward "$SERVICE" "${LOCAL_PORT}:${REMOTE_PORT}"
