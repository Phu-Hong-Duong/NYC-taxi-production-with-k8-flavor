#!/usr/bin/env bash
# image_build_load.sh — build the task image and put it on every kind node.
# Behind `make image-load` (build+load) and `make image-build` (build only).
# Owner story: M4-S3. Decision D-001 lives in docker/DECISION-D001-image-delivery.md.
#
# THE TAG IS THE GIT SHA, and that is a correctness property, not bookkeeping.
# Kubernetes pulls with `imagePullPolicy: IfNotPresent` for any tag that is not
# `:latest`, and `kind load` puts an image into each node's containerd store by
# TAG. A mutable tag (`:latest`, `:dev`) therefore gives you a cluster where some
# nodes may hold last week's bytes under this week's name, and nothing anywhere
# says so. `<short-sha>` cannot do that; `<short-sha>-dirty` says out loud that
# the image contains uncommitted work and must not be the one a verdict is
# argued from.
#
# Idempotence, and its honest limit. Re-running with an unchanged tree re-uses
# every docker layer and re-loads the same bytes: the node's image ID is
# identical before and after (the script prints both, so this is checked rather
# than claimed). It does NOT skip the load when the node already has the tag —
# `kind load` of an identical image costs a few seconds, and skipping it would
# mean trusting a tag on a node we did not read, which is precisely the failure
# the SHA tag exists to prevent.
#
# Usage:
#   scripts/image_build_load.sh              # build + load onto every node
#   scripts/image_build_load.sh --build-only # build, do not touch the cluster
#   DRY_RUN=1 scripts/image_build_load.sh    # print the plan, mutate nothing
# Exit: 0 ok · 1 build or load failed · 2 preconditions missing.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DOCKERFILE="docker/Dockerfile.pipeline"
IMAGE_NAME="${IMAGE_NAME:-taxi-mlops-pipeline}"
CLUSTER="${KIND_CLUSTER:-mlops-taxi}"
DRY_RUN="${DRY_RUN:-0}"
BUILD_ONLY=0
[[ "${1:-}" == "--build-only" ]] && BUILD_ONLY=1

# Where the reference is recorded for the next session and for verify-m4. Under
# automation/runs/ because that is where this program already keeps machine-read
# run artifacts (verify-m3 §4/§5 read automation/runs/m3s4/*.json and
# m3s5/bakeoff.json the same way). It is DERIVED state: delete it and the next
# `make image-load` writes it again.
MANIFEST_DIR="automation/runs/m4-image"
MANIFEST="${MANIFEST_DIR}/image.json"

say() { printf '%s\n' "$*"; }
die() { printf 'FAIL  %s\n' "$*" >&2; exit "${2:-1}"; }

command -v docker >/dev/null || die "docker not found — is Docker Desktop running? (gotcha #34)" 2
[[ -f "$DOCKERFILE" ]] || die "missing $DOCKERFILE" 2

# --- the tag ------------------------------------------------------------------
sha="$(git rev-parse --short HEAD)"
if [[ -n "$(git status --porcelain)" ]]; then
  TAG="${sha}-dirty"
  dirty="yes"
else
  TAG="$sha"
  dirty="no"
fi
IMAGE_REF="${IMAGE_NAME}:${TAG}"

say "== task image =================================================="
say "  dockerfile : $DOCKERFILE"
say "  image      : $IMAGE_REF   (tree dirty: $dirty)"
say "  cluster    : $CLUSTER"
say "  context    : $REPO_ROOT  (.dockerignore excludes data/ and .venv/)"

if [[ "$DRY_RUN" == "1" ]]; then
  say ""
  say "DRY_RUN=1 — would run:"
  say "  docker build -f $DOCKERFILE -t $IMAGE_REF ."
  [[ "$BUILD_ONLY" == "1" ]] || say "  kind load docker-image $IMAGE_REF --name $CLUSTER"
  say "DRY_RUN=1 — nothing was built, nothing was loaded."
  exit 0
fi

# --- before: what the nodes hold under this tag right now ----------------------
# Read FIRST so idempotence can be shown rather than asserted.
node_image_id() { # node, ref -> image id or "absent"
  docker exec "$1" crictl images --output json 2>/dev/null \
    | python3 -c '
import json, sys
want = sys.argv[1]
try:
    data = json.load(sys.stdin)
except Exception:
    print("absent"); raise SystemExit
for image in data.get("images", []):
    for tag in image.get("repoTags") or []:
        if tag in (want, "docker.io/library/" + want):
            print(image.get("id", "?")); raise SystemExit
print("absent")
' "$2"
}

mapfile -t NODES < <(kind get nodes --name "$CLUSTER" 2>/dev/null || true)
if [[ "$BUILD_ONLY" == "0" && ${#NODES[@]} -eq 0 ]]; then
  die "no nodes for kind cluster '$CLUSTER' — run 'make cluster-up' first" 2
fi

declare -A BEFORE=()
if [[ "$BUILD_ONLY" == "0" ]]; then
  say ""
  say "-- before ------------------------------------------------------"
  for node in "${NODES[@]}"; do
    BEFORE["$node"]="$(node_image_id "$node" "$IMAGE_REF")"
    say "  $node: ${BEFORE[$node]}"
  done
fi

# --- build --------------------------------------------------------------------
say ""
say "-- build -------------------------------------------------------"
build_start=$(date +%s)
docker build -f "$DOCKERFILE" -t "$IMAGE_REF" . || die "docker build failed"
build_seconds=$(( $(date +%s) - build_start ))

image_id="$(docker image inspect "$IMAGE_REF" --format '{{.Id}}')"
# TWO sizes, because they answer different questions and quoting one as "the size"
# is how a 1.7 GB duplicated layer stays invisible. `docker image inspect .Size`
# under Docker 29's containerd store is the CONTENT size — what is stored and what
# `kind load` streams to each node. The sum of `docker history` is what the layers
# occupy UNPACKED on a node's filesystem, and it is the number that noticed the
# chown mistake this Dockerfile records.
image_bytes="$(docker image inspect "$IMAGE_REF" --format '{{.Size}}')"
unpacked_bytes="$(docker history "$IMAGE_REF" --no-trunc --format '{{.Size}}' \
  | python3 -c '
import sys
units = {"B": 1, "kB": 1e3, "MB": 1e6, "GB": 1e9, "TB": 1e12}
total = 0.0
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    for suffix, factor in sorted(units.items(), key=lambda kv: -len(kv[0])):
        if line.endswith(suffix):
            total += float(line[: -len(suffix)]) * factor
            break
print(int(total))
')"
base_digest="$(grep -m1 '^FROM python' "$DOCKERFILE" | sed 's/^FROM //')"
say ""
say "  built in ${build_seconds}s"
say "  image id   : $image_id"
say "  content    : $(( image_bytes / 1024 / 1024 )) MiB stored/transferred ($image_bytes bytes)"
say "  unpacked   : ~$(( unpacked_bytes / 1000 / 1000 )) MB of layers on a node (docker history sum)"
say "  base       : $base_digest"

if [[ "$BUILD_ONLY" == "1" ]]; then
  say ""
  say "OK — built $IMAGE_REF (--build-only: the cluster was not touched)."
  exit 0
fi

# --- load ---------------------------------------------------------------------
# D-001: `kind load docker-image`, not a local registry. The registry pattern
# needs containerdConfigPatches in infra/kind/kind-config.yaml, and a kind-config
# change means cluster-down/up — which destroys the PVCs holding the MLflow
# registry, MinIO's artifacts, the Metabase app-db and both Optuna studies. The
# full argument, including when the registry pattern should land, is in
# docker/DECISION-D001-image-delivery.md.
say ""
say "-- load onto ${#NODES[@]} node(s) ------------------------------"
load_start=$(date +%s)
kind load docker-image "$IMAGE_REF" --name "$CLUSTER" || die "kind load failed"
load_seconds=$(( $(date +%s) - load_start ))
say "  loaded in ${load_seconds}s"

# --- read back FROM THE NODES, with crictl -------------------------------------
# The read-back is the evidence, and it is deliberately taken with the nodes' own
# tool: `kind load` exiting 0 says the transfer ran, `crictl images` says what
# containerd will actually hand a pod. They are different claims.
say ""
say "-- read-back (crictl on each node) -----------------------------"
# NOTE for whoever reads both numbers: the id containerd prints is NOT the id
# docker printed above. Docker names this build by its manifest-LIST digest;
# containerd names the image by its CONFIG digest. Both are correct and they
# differ by construction, so the comparison below is node-id against node-id.
#
# And that is not merely tidiness — OBSERVED 2026-08-18 across two consecutive
# builds of an identical tree: docker's manifest-list digest CHANGED
# (bf82ba68… -> 3e5066b4…) while containerd's config digest stayed
# 65c9b2b49163… on all three nodes. BuildKit's provenance attestation carries
# build metadata, so the outer digest is not reproducible; the config digest is.
# An idempotence check written against docker's id would report a change on every
# rebuild and mean nothing by it.
failures=0
containerd_id="unknown"
for node in "${NODES[@]}"; do
  after="$(node_image_id "$node" "$IMAGE_REF")"
  [[ "$after" != "absent" ]] && containerd_id="$after"
  if [[ "$after" == "absent" ]]; then
    say "  FAIL  $node: $IMAGE_REF is NOT in containerd"
    failures=$(( failures + 1 ))
    continue
  fi
  note=""
  if [[ "${BEFORE[$node]}" == "$after" ]]; then
    note="  (unchanged — idempotent re-load)"
  elif [[ "${BEFORE[$node]}" != "absent" ]]; then
    note="  (replaced ${BEFORE[$node]})"
  fi
  say "  ok    $node: $after$note"
done
(( failures == 0 )) || die "$failures node(s) do not have $IMAGE_REF"

# --- record -------------------------------------------------------------------
mkdir -p "$MANIFEST_DIR"
python3 - "$MANIFEST" "$IMAGE_REF" "$IMAGE_NAME" "$TAG" "$image_id" "$image_bytes" \
         "$base_digest" "$dirty" "$build_seconds" "$load_seconds" "$unpacked_bytes" \
         "$containerd_id" "${NODES[@]}" <<'PY'
import json, subprocess, sys
(path, ref, name, tag, image_id, size, base, dirty, build_s, load_s, unpacked,
 containerd_id), nodes = sys.argv[1:13], sys.argv[13:]
record = {
    "image_ref": ref,
    "image_name": name,
    "tag": tag,
    "image_id": image_id,
    "containerd_image_id": containerd_id,
    "content_bytes": int(size),
    "unpacked_bytes_approx": int(unpacked),
    "base_image": base,
    "git_sha": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
    "tree_dirty": dirty == "yes",
    "build_seconds": int(build_s),
    "load_seconds": int(load_s),
    "nodes": nodes,
    "dockerfile": "docker/Dockerfile.pipeline",
}
with open(path, "w") as handle:
    json.dump(record, handle, indent=2, sort_keys=True)
    handle.write("\n")
print(f"  wrote {path}")
PY

say ""
say "OK — $IMAGE_REF is on all ${#NODES[@]} node(s). Prove it runs OUR code: make image-smoke"
