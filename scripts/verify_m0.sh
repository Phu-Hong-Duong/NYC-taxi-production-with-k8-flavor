#!/usr/bin/env bash
# verify_m0.sh — the M0 gate, executable. BLUEPRINT §9/M0, quoted:
#
#   "idempotent cluster + platform + verify-m0 green, destroy/rebuild observed
#    AND the org docs exist with every charter carrying at least three refusals"
#
# Design rule: every check observes the THING, not a proxy for it. "The
# Deployment says Ready" is a proxy; "the URL a human will open returns the UI"
# is the thing. Where both are cheap we do both, because they fail differently.
#
# Prints one line per sub-check and exits nonzero if ANY fails — it keeps going
# rather than stopping at the first, so one run tells you everything that is
# broken instead of the first thing.
#
# Usage: scripts/verify_m0.sh        (via `make verify-m0`)
set -uo pipefail   # deliberately NOT -e: a failing check must be counted, not fatal

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")
MLFLOW_URL="${MLFLOW_URL:-http://localhost:5000}"
MINIO_URL="${MINIO_URL:-http://localhost:9000}"

FAILS=0
pass() { printf '  \033[32mok  \033[0m %s\n' "$1"; }

fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1" >&2; FAILS=$((FAILS + 1)); }
note() { printf '       %s\n' "$1"; }
section() { printf '\n== %s ==\n' "$1"; }

# RED-TEAMED 2026-08-16 and it caught this script: `kubectl rollout status` on a
# Deployment scaled to 0 replicas exits 0 and prints "successfully rolled out" —
# because zero replicas is a complete rollout. Scaling MLflow to 0 therefore made
# verify-m0 print "ok deployment/mlflow rolled out" while every URL check failed.
# So the readiness question is asked as a NUMBER: at least one ready replica, and
# ready == desired. The rollout check stays because it fails differently (a
# half-finished or wedged rollout).
workload_ready() {
  local ns="$1" ref="$2" ready desired
  if ! "${KUBECTL[@]}" -n "$ns" rollout status "$ref" --timeout=60s >/dev/null 2>&1; then
    fail "$ns/$ref did not finish rolling out"
    return 1
  fi
  ready="$("${KUBECTL[@]}" -n "$ns" get "$ref" -o jsonpath='{.status.readyReplicas}' 2>/dev/null)"
  desired="$("${KUBECTL[@]}" -n "$ns" get "$ref" -o jsonpath='{.spec.replicas}' 2>/dev/null)"
  ready="${ready:-0}"; desired="${desired:-0}"
  if [[ "$ready" =~ ^[0-9]+$ ]] && (( ready >= 1 )) && [[ "$ready" == "$desired" ]]; then
    pass "$ns/$ref ready ($ready/$desired replicas)"
  else
    fail "$ns/$ref has $ready/$desired ready replicas"
  fi
}

# ---------------------------------------------------------------- cluster ----
section "1. cluster"
if nodes="$("${KUBECTL[@]}" get nodes --no-headers 2>&1)"; then
  total=$(printf '%s\n' "$nodes" | grep -c .)
  ready=$(printf '%s\n' "$nodes" | awk '$2 == "Ready"' | grep -c .)
  if [[ "$total" -gt 0 && "$ready" == "$total" ]]; then
    pass "kind cluster reachable — $ready/$total nodes Ready"
  else
    fail "only $ready/$total nodes Ready"
    note "$nodes"
  fi
else
  fail "cannot reach context '$CONTEXT' — is the cluster up? (make cluster-up)"
  note "$nodes"
fi

for ns in platform mlflow; do
  if "${KUBECTL[@]}" get namespace "$ns" >/dev/null 2>&1; then
    pass "namespace $ns exists"
  else
    fail "namespace $ns missing (make deploy-platform)"
  fi
done

# --------------------------------------------------------------- postgres ----
section "2. Postgres — the one database"
workload_ready platform statefulset/postgres

# The MLflow database and role must exist and be owned correctly — the initdb
# hook runs only on a fresh volume, so this is the check that catches "the PVC
# survived a change to the init script".
pg_q() { "${KUBECTL[@]}" -n platform exec statefulset/postgres -- \
           psql -U postgres -tAc "$1" 2>/dev/null | tr -d '[:space:]'; }
owner="$(pg_q "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='mlflow'")"
if [[ "$owner" == "mlflow" ]]; then
  pass "database 'mlflow' exists, owned by role 'mlflow'"
else
  fail "database 'mlflow' missing or wrongly owned (got: '${owner:-<none>}')"
fi

# MLflow's schema living in OUR Postgres is the proof the backend store is real
# and not the chart's in-memory sqlite fallback.
exp_rows="$("${KUBECTL[@]}" -n platform exec statefulset/postgres -- \
  psql -U postgres -d mlflow -tAc "SELECT count(*) FROM experiments" 2>/dev/null | tr -d '[:space:]')"
if [[ "${exp_rows:-}" =~ ^[0-9]+$ ]] && (( exp_rows >= 1 )); then
  pass "MLflow schema is in Postgres — experiments table has $exp_rows row(s)"
else
  fail "MLflow schema not found in Postgres (backend store may be sqlite)"
fi

# ------------------------------------------------------------------ minio ----
section "3. MinIO — the S3"
workload_ready platform deployment/minio

# `mc` runs INSIDE the pod using the pod's own env, so no credential ever appears
# in an argument list, a process table, or this session's log.
mc_in_pod() { "${KUBECTL[@]}" -n platform exec deployment/minio -- sh -c \
  'mc alias set v http://127.0.0.1:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1 && '"$1" 2>/dev/null; }
buckets="$(mc_in_pod 'mc ls v')"
if grep -q "mlflow-artifacts" <<< "$buckets"; then
  pass "bucket mlflow-artifacts exists"
  note "$(printf '%s' "$buckets" | head -5)"
else
  fail "bucket mlflow-artifacts not found"
  note "buckets seen: ${buckets:-<none>}"
fi
if mc_in_pod 'mc admin user list v' | awk '$2 == "mlflow"' | grep -q .; then
  pass "MinIO user 'mlflow' exists (MLflow does not use the root account)"
else
  fail "MinIO user 'mlflow' missing — artifacts will 403 (gotcha #5 territory)"
fi
if curl -fsS --max-time 10 "$MINIO_URL/minio/health/live" >/dev/null 2>&1; then
  pass "MinIO S3 API answers on $MINIO_URL (host route via kind hostPort)"
else
  fail "MinIO S3 API unreachable at $MINIO_URL"
fi

# ----------------------------------------------------------------- mlflow ----
section "4. MLflow — tracking & registry"
workload_ready mlflow deployment/mlflow

health="$(curl -fsS --max-time 10 "$MLFLOW_URL/health" 2>&1)"
if [[ "$health" == *OK* ]]; then
  pass "MLflow /health on $MLFLOW_URL -> $health"
else
  fail "MLflow /health failed at $MLFLOW_URL (got: ${health:-<nothing>})"
fi

ui="$(curl -fsS --max-time 15 "$MLFLOW_URL/" 2>&1)"
if grep -qi "mlflow" <<< "$ui" && grep -qi "<html" <<< "$ui"; then
  pass "MLflow UI payload served at $MLFLOW_URL ($(printf '%s' "$ui" | wc -c) bytes of HTML)"
else
  fail "MLflow UI did not return an HTML page at $MLFLOW_URL"
fi

# The API round-trip proves server -> Postgres works, and the artifact location
# proves the server -> MinIO wiring, without writing anything.
api="$(curl -fsS --max-time 15 -X POST -H 'Content-Type: application/json' \
        -d '{"max_results": 10}' "$MLFLOW_URL/api/2.0/mlflow/experiments/search" 2>&1)"
if grep -q '"experiments"' <<< "$api"; then
  pass "MLflow REST API answers (experiments/search)"
else
  fail "MLflow REST API did not answer (got: $(printf '%s' "${api:-<nothing>}" | head -c 200))"
fi
if grep -q 's3://mlflow-artifacts' <<< "$api"; then
  pass "artifact root is s3://mlflow-artifacts (MinIO), not a container filesystem"
else
  fail "artifact root is NOT s3://mlflow-artifacts — artifacts would land in a pod and vanish"
  note "$(printf '%s' "${api:-}" | head -c 300)"
fi

# ------------------------------------------------------------- constitution --
section "5. the constitution (org docs)"
DOCS=(
  docs/BLUEPRINT.md
  docs/org/ORG.md
  docs/org/ROLES.md
  docs/gotchas.md
  docs/LEARNING_GUIDE.md
  AWAITING_PO.md
  HANDOFF.md
  ledgers/debt.md
  ledgers/findings.md
  ledgers/signoffs.md
  ledgers/deployments.md
)
missing=()
for f in "${DOCS[@]}"; do
  [[ -s "$REPO_ROOT/$f" ]] || missing+=("$f")
done
if [[ ${#missing[@]} -eq 0 ]]; then
  pass "all ${#DOCS[@]} org/ledger documents present and non-empty"
else
  fail "missing or empty: ${missing[*]}"
fi

charters="$(bash "$REPO_ROOT/scripts/check_charters.sh" 2>&1)"
if [[ $? -eq 0 ]]; then
  pass "every charter carries >= 3 refusals"
  printf '%s\n' "$charters" | sed 's/^/     /'
else
  fail "charter refusal check failed"
  printf '%s\n' "$charters" | sed 's/^/     /' >&2
fi

# ---------------------------------------------------------------- verdict ----
printf '\n'
if (( FAILS == 0 )); then
  echo "[verify-m0] GREEN — every M0 sub-check passed."
  echo "            Show: MLflow UI $MLFLOW_URL · MinIO console http://localhost:9001"
  exit 0
fi
echo "[verify-m0] RED — $FAILS sub-check(s) failed (see FAIL lines above)." >&2
exit 1
