#!/usr/bin/env bash
# deploy_flyte.sh — Flyte on the kind cluster, behind `make deploy-flyte` (M4-S2).
#
# Idempotent end to end, and deliberately SELF-SUFFICIENT: like
# scripts/deploy_metabase.sh it re-runs the pieces of the platform recipe it
# depends on (namespaces, secrets, databases, and the MinIO release that owns the
# bucket) instead of documenting "run make deploy-platform first". All four are
# converge-not-create, so re-running them costs a no-op and buys a target that
# cannot be defeated by being run in the wrong order (the M1-S5 rule).
#
# Order matters and is not incidental:
#   namespaces -> secrets -> the `flyte` database (D-002) -> MinIO (bucket+user)
#              -> flyte-binary -> readiness -> the API answers
# The chart's own init container blocks on Postgres answering AND on the `flyte`
# database existing — which initdb cannot create on a volume it finished with in
# May, which is exactly what D-002 exists for.
#
# THE CLUSTER IS STATEFUL AND THIS SCRIPT NEVER TAKES IT DOWN (M4 kickoff's top
# law). It publishes no host port, edits no kind config, and touches no PVC that
# is not its own. Reaching the console is `make flyte-console` — the recorded
# deviation from the declared-route doctrine, argued in infra/helm/flyte/values.yaml.
#
# SECRETS NEVER REACH A COMMAND LINE. The flyte-binary chart renders its database
# password and its S3 secret key out of VALUES, so they arrive here as a
# mode-600 temporary overlay that is deleted by an EXIT trap — not via `--set`,
# whose arguments are visible in `ps` and land in shell history.
#
# Usage: scripts/deploy_flyte.sh            (via `make deploy-flyte`)
#        DRY_RUN=1 scripts/deploy_flyte.sh  (render the manifests, apply nothing)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")
HELM=(helm --kube-context "$CONTEXT")
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"
NAMESPACE="${FLYTE_NAMESPACE:-flyte}"
RELEASE="${FLYTE_RELEASE:-flyte}"
DRY_RUN="${DRY_RUN:-0}"

# --- pins ---------------------------------------------------------------------
# Read LIVE 2026-08-18 from `helm search repo flyteorg --versions`. See the
# values file for why "flyte-binary v2.0.x" IS the 2.x line ADR-002 chose and
# `flyte-core v1.16.x` is the older one. Recorded in CLAUDE.md's pin table with
# the read-back command. Bump here, in one diff, never by letting helm resolve.
FLYTE_REPO_URL="https://flyteorg.github.io/flyte"
FLYTE_CHART="flyteorg/flyte-binary"
FLYTE_CHART_VERSION="v2.0.42"
# ADR-002's pre-approved fallback, stated here so the next reader does not have
# to go looking at the wall: chart v1.5.1 (appVersion 1.16.0). It executes
# WITHOUT a new decision if the 2.x line hits the three-attempt wall.
FLYTE_FALLBACK_CHART_VERSION="v1.5.1"

MINIO_REPO_URL="https://charts.min.io/"
MINIO_CHART_VERSION="5.4.0"   # twin of scripts/deploy_platform.sh — change both

echo "== [1/6] helm repos (idempotent) =="
"${HELM[@]}" repo add flyteorg "$FLYTE_REPO_URL" --force-update >/dev/null
"${HELM[@]}" repo add minio "$MINIO_REPO_URL" --force-update >/dev/null
"${HELM[@]}" repo update flyteorg minio >/dev/null
echo "   $FLYTE_CHART $FLYTE_CHART_VERSION (fallback $FLYTE_FALLBACK_CHART_VERSION, ADR-002)"

# DRY_RUN must not mutate ANYTHING, including the steps that are "only" no-ops
# on a converged cluster — gotcha #30 is the precedent: `DRY_RUN=1 make destroy`
# deleted the cluster for four milestones because the preview covered the files
# and not the most expensive action. A preview that re-runs a helm upgrade is a
# preview that can restart MinIO under whatever is reading it.
if [[ "$DRY_RUN" == "1" ]]; then
  echo "== [2/6] namespaces ==            DRY_RUN — WOULD apply infra/manifests/namespaces.yaml"
  echo "== [3/6] secrets from .env ==     DRY_RUN — WOULD run scripts/platform_secrets.sh"
  DRY_RUN=1 bash "$REPO_ROOT/scripts/postgres_databases.sh"
  echo "== [5/6] MinIO ==                 DRY_RUN — WOULD helm upgrade minio $MINIO_CHART_VERSION (bucket flyte-data, user flyte)"
else
  echo "== [2/6] namespaces =="
  "${KUBECTL[@]}" apply -f "$REPO_ROOT/infra/manifests/namespaces.yaml"

  echo "== [3/6] secrets from .env (adds minio-flyte-user) =="
  bash "$REPO_ROOT/scripts/platform_secrets.sh"

  echo "== [4/6] the 'flyte' database in the one Postgres (D-002) =="
  bash "$REPO_ROOT/scripts/postgres_databases.sh"

  echo "== [5/6] MinIO — the flyte-data bucket and the flyte user =="
  # The chart's post-install Jobs are what create buckets and users idempotently.
  # Re-running the release here is the ONLY reason this step exists: it is how the
  # bucket comes into being from the recipe rather than from somebody's `mc mb`.
  "${HELM[@]}" upgrade --install minio minio/minio \
    --version "$MINIO_CHART_VERSION" \
    --namespace platform \
    -f "$REPO_ROOT/infra/helm/minio/values.yaml" \
    --wait --timeout 10m
  "${KUBECTL[@]}" -n platform rollout status deployment/minio --timeout=300s
fi

# --- the secret overlay -------------------------------------------------------
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a
for k in FLYTE_DB_USER FLYTE_DB_PASSWORD FLYTE_S3_ACCESS_KEY FLYTE_S3_SECRET_KEY; do
  if [[ -z "${!k:-}" ]]; then
    echo "[flyte] FAIL: $ENV_FILE has no value for $k — run scripts/platform_secrets.sh" >&2
    exit 1
  fi
done
OVERLAY="$(mktemp)"
chmod 600 "$OVERLAY"
trap 'rm -f "$OVERLAY"' EXIT
cat > "$OVERLAY" <<EOF
configuration:
  database:
    postgres:
      username: ${FLYTE_DB_USER}
      password: ${FLYTE_DB_PASSWORD}
  storage:
    providerConfig:
      s3:
        accessKey: ${FLYTE_S3_ACCESS_KEY}
        secretKey: ${FLYTE_S3_SECRET_KEY}
EOF

echo "== [6/6] Flyte ($FLYTE_CHART $FLYTE_CHART_VERSION) =="
if [[ "$DRY_RUN" == "1" ]]; then
  # --dry-run renders; the overlay still supplies the values so the render is the
  # real one, and it is piped to a count rather than to stdout so no secret is
  # ever printed by a preview.
  rendered=$("${HELM[@]}" upgrade --install "$RELEASE" "$FLYTE_CHART" \
    --version "$FLYTE_CHART_VERSION" --namespace "$NAMESPACE" \
    -f "$REPO_ROOT/infra/helm/flyte/values.yaml" -f "$OVERLAY" \
    --dry-run 2>&1 | grep -c '^kind:' || true)
  echo "[flyte] DRY_RUN — chart renders ($rendered top-level kind: lines). Nothing applied."
  exit 0
fi

"${HELM[@]}" upgrade --install "$RELEASE" "$FLYTE_CHART" \
  --version "$FLYTE_CHART_VERSION" \
  --namespace "$NAMESPACE" \
  -f "$REPO_ROOT/infra/helm/flyte/values.yaml" \
  -f "$OVERLAY" \
  --wait --timeout 10m

# `kubectl rollout status` takes one named resource — it has no --selector — so
# the deployments are enumerated and waited on by name. Enumerating rather than
# listing them literally means a chart that grows a component (the console and
# the connector are already two of three) is covered without editing this line.
while read -r dep; do
  [[ -n "$dep" ]] || continue
  "${KUBECTL[@]}" -n "$NAMESPACE" rollout status "$dep" --timeout=600s
done < <("${KUBECTL[@]}" -n "$NAMESPACE" get deploy -o name)

echo
echo "[flyte] pods:"
"${KUBECTL[@]}" -n "$NAMESPACE" get pods
echo
echo "[flyte] done. Reach it with:  make flyte-console"
echo "[flyte] (no host port is published for Flyte — see infra/helm/flyte/values.yaml"
echo "[flyte]  for why the declared-route doctrine is deviated from here.)"
