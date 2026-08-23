#!/usr/bin/env bash
# M8-S4 leg 2 — build the quarantined feature server and put it on every node.
#
# The `scripts/image_build_load.sh` shape, deliberately: build, `kind load`, then
# READ IT BACK off every node with the nodes' own tool (`crictl images`), because
# a `kind load` that half-succeeded leaves a cluster that pulls
# `ImagePullBackOff` on whichever node the scheduler happens to pick — and M5-S4
# proved that a replacement pod can land on a different node than the one you
# watched.
#
# THE TAG CARRIES A GIT SHA AND THAT IS A CORRECTNESS PROPERTY (M4-S3's lesson,
# inherited). Kubernetes pulls `IfNotPresent` for any non-`:latest` tag and
# `kind load` writes into containerd BY TAG, so a mutable tag gives you nodes
# holding last week's bytes under this week's name with nothing saying so. This
# image's content is `requirements-feast.txt` + `definitions.py` +
# `feature_store.yaml` + the published parquet — `definitions.py` in particular
# is a file this program edits — so the version alone is not a pin. `-dirty` says
# the image carries uncommitted work and must not back a verdict.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

FEAST_VERSION="$(grep -iE '^feast==' infra/feast/requirements-feast.txt | head -1 | cut -d= -f3)"
if [[ -z "$FEAST_VERSION" ]]; then
  echo "[feast-image] FAIL: no 'feast==' line in infra/feast/requirements-feast.txt" >&2
  exit 2
fi

SHA="$(git rev-parse --short HEAD)"
if [[ -n "$(git status --porcelain -- docker/feast-server.Dockerfile docker/feast-server-entrypoint.sh infra/feast data/feast 2>/dev/null)" ]]; then
  SHA="${SHA}-dirty"
fi
IMAGE="taxi-mlops-feast-server:feast-${FEAST_VERSION}-${SHA}"
CLUSTER="$(grep -E '^name:' infra/kind/kind-config.yaml | awk '{print $2}')"
RECORD="automation/runs/m8-transformer/feast-server-image.json"
mkdir -p "$(dirname "$RECORD")"

echo "[feast-image] image  $IMAGE"
echo "[feast-image] feast  $FEAST_VERSION (from the ONE pin file, --no-deps)"
echo "[feast-image] cluster $CLUSTER"

if [[ "${DRY_RUN:-0}" == "1" ]]; then
  echo "[feast-image] DRY_RUN=1 — nothing was built, nothing was loaded."
  exit 0
fi

echo "[feast-image] building"
docker build -f docker/feast-server.Dockerfile -t "$IMAGE" .

echo "[feast-image] loading onto the $CLUSTER nodes"
kind load docker-image "$IMAGE" --name "$CLUSTER"

echo "[feast-image] reading it back off every node with the node's OWN tool"
failed=0
nodes="$(kind get nodes --name "$CLUSTER")"
for node in $nodes; do
  line="$(docker exec "$node" crictl images 2>/dev/null | grep -F "taxi-mlops-feast-server" || true)"
  if [[ -z "$line" ]]; then
    echo "[feast-image] FAIL $node: the image is not present" >&2
    failed=1
  else
    echo "[feast-image] ok  $node: $line"
  fi
done
[[ "$failed" == "0" ]] || exit 1

python3 - "$IMAGE" "$RECORD" <<'PY'
import json, subprocess, sys
image, record = sys.argv[1], sys.argv[2]
digest = subprocess.run(
    ["docker", "image", "inspect", "--format", "{{.Id}}", image],
    capture_output=True, text=True, check=True).stdout.strip()
size = subprocess.run(
    ["docker", "image", "inspect", "--format", "{{.Size}}", image],
    capture_output=True, text=True, check=True).stdout.strip()
head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                      check=True).stdout.strip()
payload = {
    "image": image,
    "docker_image_id": digest,
    "content_size_bytes": int(size),
    "git_head": head,
    "note": (
        "M8-S4 leg 2, shape (i): the pandas-2 half of the wall, containerised. "
        "Built --no-deps from infra/feast/requirements-feast.txt, the SAME pin "
        "file scripts/feast_quarantine.sh uses. Carries no registry (derived at "
        "start from definitions.py) and no store address (from the environment "
        "at run time, with no default)."
    ),
}
with open(record, "w") as fh:
    json.dump(payload, fh, indent=2, sort_keys=True)
    fh.write("\n")
print(f"[feast-image] recorded {record}")
print(f"[feast-image] content size {int(size)/1e6:.0f} MB")
PY
