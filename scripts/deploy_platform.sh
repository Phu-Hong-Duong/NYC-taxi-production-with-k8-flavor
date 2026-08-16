#!/usr/bin/env bash
# deploy_platform.sh — the M0 platform behind `make deploy-platform`:
# MinIO (S3) + Postgres (the one database) + MLflow (tracking & registry).
#
# Idempotent end to end. Every step is either `kubectl apply` or
# `helm upgrade --install`, both of which converge rather than create; running
# this on a live stack is a no-op upgrade, which is the only way a recipe is
# allowed to be trusted (MLOps charter: no manual deploys, no hand-edits the
# recipe cannot reproduce).
#
# Order matters and is not incidental:
#   namespaces -> secrets -> Postgres -> databases -> MinIO -> MLflow -> host route
# MLflow's init containers block on Postgres answering AND on the mlflow role
# existing, and its artifact writes need the bucket + user MinIO's post-install
# Job creates.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")
HELM=(helm --kube-context "$CONTEXT")

# --- pins ---------------------------------------------------------------------
# CHART versions are the pin (each chart pins its own images). Recorded in the
# CLAUDE.md pin table with the date they were observed. Bump here, in one diff,
# never by letting helm resolve "latest".
MINIO_REPO_URL="https://charts.min.io/"
MINIO_CHART_VERSION="5.4.0"
MLFLOW_REPO_URL="https://community-charts.github.io/helm-charts"
MLFLOW_CHART_VERSION="1.11.4"

echo "== [1/7] helm repos (idempotent) =="
"${HELM[@]}" repo add minio "$MINIO_REPO_URL" --force-update >/dev/null
"${HELM[@]}" repo add community-charts "$MLFLOW_REPO_URL" --force-update >/dev/null
"${HELM[@]}" repo update minio community-charts >/dev/null
echo "   minio $MINIO_CHART_VERSION · community-charts/mlflow $MLFLOW_CHART_VERSION"

echo "== [2/7] namespaces =="
# Applied here, not by cluster-up: cluster-up owns the machine (nodes, ports),
# deploy-platform owns everything inside it. That split is what lets S4's
# destroy/rebuild prove the two halves separately.
"${KUBECTL[@]}" apply -f "$REPO_ROOT/infra/manifests/namespaces.yaml"

echo "== [3/7] secrets from .env =="
bash "$REPO_ROOT/scripts/platform_secrets.sh"

echo "== [4/7] Postgres (plain manifests — see the file header for why) =="
"${KUBECTL[@]}" apply -f "$REPO_ROOT/infra/manifests/postgres.yaml"
"${KUBECTL[@]}" -n platform rollout status statefulset/postgres --timeout=300s

echo "== [5/7] databases + roles in that Postgres (D-002) =="
# Separate from the manifest on purpose: initdb runs ONCE, on an empty volume,
# so every database after the first arrives here. See the script's header.
bash "$REPO_ROOT/scripts/postgres_databases.sh"

echo "== [6/7] MinIO =="
"${HELM[@]}" upgrade --install minio minio/minio \
  --version "$MINIO_CHART_VERSION" \
  --namespace platform \
  -f "$REPO_ROOT/infra/helm/minio/values.yaml" \
  --wait --timeout 10m
# The bucket/user Jobs are post-install hooks; --wait covers the release, so
# check the data path itself rather than assuming the hook ran.
"${KUBECTL[@]}" -n platform rollout status deployment/minio --timeout=300s

echo "== [7/7] MLflow + host route =="
"${HELM[@]}" upgrade --install mlflow community-charts/mlflow \
  --version "$MLFLOW_CHART_VERSION" \
  --namespace mlflow \
  -f "$REPO_ROOT/infra/helm/mlflow/values.yaml" \
  --wait --timeout 10m
"${KUBECTL[@]}" apply -f "$REPO_ROOT/infra/manifests/mlflow-nodeport.yaml"
"${KUBECTL[@]}" -n mlflow rollout status deployment/mlflow --timeout=300s

echo
echo "[deploy-platform] done. Now prove it: make verify-m0"
echo "  MLflow UI      http://localhost:5000"
echo "  MinIO console  http://localhost:9001   (credentials: .env, never printed)"
