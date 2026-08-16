#!/usr/bin/env bash
# cluster.sh — the kind cluster lifecycle behind `make cluster-up|cluster-down|destroy`.
# Every path is idempotent: running it twice is a no-op, not an error, because a
# recipe you are afraid to re-run is not a recipe (MLOps charter).
#
#   up       port pre-check (only when a create is actually pending) -> kind create
#            -> kubeconfig export -> wait Ready -> print the recipe fingerprint
#   down     delete the cluster only; leaves every file on disk alone
#   destroy  down + delete REGENERABLE state from an explicit allowlist, with a
#            deny-list guard. Never data/raw, never .env, never .dvc/cache.
#            DRY_RUN=1 prints the plan and deletes nothing.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KIND_CONFIG="${KIND_CONFIG:-$REPO_ROOT/infra/kind/kind-config.yaml}"

# The cluster name is declared in the kind config — parsed, never re-typed, so
# the two can't drift.
CLUSTER="$(awk '/^name:/ {print $2; exit}' "$KIND_CONFIG")"
if [[ -z "${CLUSTER:-}" ]]; then
  echo "[cluster] FAIL: no 'name:' in $KIND_CONFIG — refusing to guess a cluster name." >&2
  exit 1
fi

# Regenerable state destroy may remove. Everything here must be reproducible by a
# make target; if you cannot name the command that rebuilds it, it does not belong.
REGENERABLE=(
  "data/processed"    # rebuilt by `make data`
  "data/interim"      # rebuilt by `make data`
  "mlruns"            # local MLflow store; the cluster's store is in Postgres/MinIO
  ".pytest_cache"
  ".ruff_cache"
)

# Never, under any argument, any typo, any future edit. Checked by realpath after
# symlink resolution, so a symlink pointing out of an allowlisted dir cannot smuggle
# one of these in.
DENY=(
  "data/raw"      # the original download — DVC-pinned, but re-fetching costs bandwidth and TLC may have backfilled (gotcha #6)
  ".env"          # secrets, user-created
  ".git"
  ".dvc/cache"    # with a local-only DVC remote this IS the only copy
  ".venv"         # regenerable, but deleting it buys nothing and costs a re-sync every rebuild
)

cluster_exists() {
  kind get clusters 2>/dev/null | grep -qx "$CLUSTER"
}

cmd_up() {
  if cluster_exists; then
    echo "[cluster-up] cluster '$CLUSTER' already exists — no-op."
    # Repair the kubeconfig entry rather than assume it: same end state either way.
    kind export kubeconfig --name "$CLUSTER" >/dev/null
    kubectl --context "kind-$CLUSTER" get nodes
    return 0
  fi

  # The pre-check runs ONLY on the create path. Once our own cluster is up it
  # holds the kind hostPorts itself, and a pre-check on the no-op path would
  # refuse because we succeeded — idempotence would die on its own success.
  bash "$REPO_ROOT/scripts/port_precheck.sh"

  echo "[cluster-up] creating kind cluster '$CLUSTER' from $KIND_CONFIG"
  kind create cluster --config "$KIND_CONFIG"
  kind export kubeconfig --name "$CLUSTER" >/dev/null
  kubectl --context "kind-$CLUSTER" wait --for=condition=Ready nodes --all --timeout=300s
  kubectl --context "kind-$CLUSTER" get nodes -o wide

  echo "[cluster-up] recipe fingerprint (record pins in CLAUDE.md):"
  kind --version
  docker inspect "${CLUSTER}-control-plane" --format 'node image: {{.Config.Image}}'
}

cmd_down() {
  if ! cluster_exists; then
    echo "[cluster-down] cluster '$CLUSTER' is already absent — no-op."
    return 0
  fi
  echo "[cluster-down] deleting kind cluster '$CLUSTER'"
  kind delete cluster --name "$CLUSTER"
}

# Refuse any path that escapes the repo or lands on the deny list.
guard_path() {
  local rel="$1" abs
  abs="$(cd "$REPO_ROOT" && realpath -m "$rel")"
  case "$abs" in
    "$REPO_ROOT"/*) : ;;
    *) echo "[destroy] REFUSING '$rel': resolves to '$abs', outside the repo." >&2; return 1 ;;
  esac
  local d dabs
  for d in "${DENY[@]}"; do
    dabs="$(cd "$REPO_ROOT" && realpath -m "$d")"
    if [[ "$abs" == "$dabs" || "$abs" == "$dabs"/* ]]; then
      echo "[destroy] REFUSING '$rel': resolves into protected path '$d'." >&2
      return 1
    fi
  done
  return 0
}

cmd_destroy() {
  echo "[destroy] protected, never touched: ${DENY[*]}"

  # The cluster is the most expensive thing destroy deletes, so it obeys DRY_RUN
  # like everything else. It did NOT until M0-S4: cmd_down ran unconditionally
  # while the footer printed "nothing was deleted" — a preview that deleted the
  # cluster (gotcha #30). Observed live, not reasoned about.
  if [[ "${DRY_RUN:-0}" == "1" ]]; then
    if cluster_exists; then
      echo "[destroy] WOULD delete kind cluster '$CLUSTER' (and with it every PVC inside)"
    else
      echo "[destroy] skip   kind cluster '$CLUSTER' (already absent)"
    fi
  else
    cmd_down
  fi

  local rel
  for rel in "${REGENERABLE[@]}"; do
    guard_path "$rel" || exit 1
    if [[ ! -e "$REPO_ROOT/$rel" ]]; then
      echo "[destroy] skip   $rel (absent)"
      continue
    fi
    if [[ "${DRY_RUN:-0}" == "1" ]]; then
      echo "[destroy] WOULD remove $rel"
    else
      echo "[destroy] remove $rel"
      rm -rf "${REPO_ROOT:?}/$rel"
    fi
  done
  if [[ "${DRY_RUN:-0}" == "1" ]]; then
    echo "[destroy] DRY_RUN=1 — nothing was deleted."
  fi
  echo "[destroy] done. Rebuild with: make cluster-up deploy-platform"
}

case "${1:-}" in
  up) cmd_up ;;
  down) cmd_down ;;
  destroy) cmd_destroy ;;
  *) echo "usage: $(basename "$0") up|down|destroy   (DRY_RUN=1 supported by destroy)" >&2; exit 1 ;;
esac
