#!/usr/bin/env bash
# deploy_metabase.sh — the BI seat behind `make deploy-metabase`: Metabase, one
# container, app-db in the one Postgres, reachable at http://localhost:3030 by a
# route the cluster declares rather than a port-forward somebody remembers.
#
# Idempotent end to end, and deliberately SELF-SUFFICIENT: it re-runs the two
# pieces of the platform recipe it depends on (secrets, databases) instead of
# documenting "run make deploy-platform first". Both are converge-not-create, so
# the cost of re-running them is a no-op and the benefit is that this target
# cannot be defeated by being run in the wrong order.
#
# Order matters:
#   namespace -> secrets -> app-db in Postgres -> Deployment -> host route check
#                                                            -> boards
# Metabase runs its own schema migrations against an EMPTY `metabase` database on
# first boot; it cannot create that database itself, which is exactly what D-002
# exists for (scripts/postgres_databases.sh).
#
# Usage: scripts/deploy_metabase.sh              (via `make deploy-metabase`)
#        SKIP_BOARDS=1 scripts/deploy_metabase.sh   (deploy only, no provisioning)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")
METABASE_URL="${METABASE_URL:-http://localhost:3030}"
SKIP_BOARDS="${SKIP_BOARDS:-0}"

echo "== [1/5] namespace =="
"${KUBECTL[@]}" apply -f "$REPO_ROOT/infra/manifests/namespaces.yaml"

echo "== [2/5] secrets from .env (metabase-db + metabase-marts-db) =="
bash "$REPO_ROOT/scripts/platform_secrets.sh"

echo "== [3/5] the 'metabase' app-db in the one Postgres (D-002) =="
bash "$REPO_ROOT/scripts/postgres_databases.sh"

echo "== [4/5] Metabase =="
"${KUBECTL[@]}" apply -f "$REPO_ROOT/infra/manifests/metabase.yaml"
# First boot migrates the app-db and is genuinely slow; the manifest's
# startupProbe allows up to 10 minutes and this timeout must not be tighter.
"${KUBECTL[@]}" -n metabase rollout status deployment/metabase --timeout=900s

# The route a human will open, asked as the thing rather than a proxy for it
# (verify_m0.sh's design rule). A ready Deployment behind a Service whose
# selector matches nothing looks identical to a working one from the outside.
#
# WHY THIS RETRIES INSTEAD OF ASKING ONCE. Observed the first time this ran:
# `rollout status` returned, and a single 20s curl came back `000`. The route was
# fine — `rollout status` succeeds the instant the readinessProbe flips, and
# Metabase's FIRST request through the node port, on a JVM that has just finished
# migrating its app-db, is slower than any one-shot timeout worth setting. A
# check that races the thing it checks reports a broken deploy roughly at random,
# which is worse than no check at all: it teaches you to re-run and shrug.
echo "== [5/5] host route =="
code=000
for attempt in $(seq 1 30); do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$METABASE_URL/api/health" || true)"
  [[ "$code" == "200" ]] && break
  [[ "$attempt" == "1" ]] && echo "[metabase] waiting for the first response through hostPort 3030 …"
  sleep 10
done
if [[ "$code" != "200" ]]; then
  echo "[metabase] FAIL: $METABASE_URL/api/health returned '$code' (expected 200)" >&2
  echo "[metabase]       hostPort 3030 is published at cluster-CREATE time only —" >&2
  echo "[metabase]       if it is missing from \`docker port\`, the cluster predates" >&2
  echo "[metabase]       the kind-config row and needs cluster-down + cluster-up." >&2
  exit 1
fi
echo "[metabase] ok  $METABASE_URL/api/health -> 200 (via kind hostPort 3030 -> nodePort 30300)"

if [[ "$SKIP_BOARDS" == "1" ]]; then
  echo "[metabase] SKIP_BOARDS=1 — deployed, boards not provisioned."
  exit 0
fi

echo
uv run --project "$REPO_ROOT" python "$REPO_ROOT/scripts/metabase_boards.py"

echo
echo "[deploy-metabase] done. Now prove it: make verify-m1"
echo "  Metabase  $METABASE_URL   (credentials: .env, never printed)"
