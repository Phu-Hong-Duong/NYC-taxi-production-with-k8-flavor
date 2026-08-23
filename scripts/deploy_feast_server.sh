#!/usr/bin/env bash
# M8-S4 leg 2 — the Feast feature server on the cluster, and an accept check that
# is an ANSWER rather than a list of ready objects.
#
# `DRY_RUN=1` mutates nothing (gotcha #30's rule, pinned by a test).
# `TEARDOWN=1` removes exactly its own two objects and leaves Redis alone.
#
# THE ACCEPT IS A REAL ONLINE LOOKUP, MADE FROM A DIFFERENT POD. Gotcha #59: a
# readiness probe passing proves the process is listening, and #78's sibling says
# an empty answer and a healthy one render identically. So this asks the server
# the question it exists to answer — one `/get-online-features` for a zone the
# champion actually eats — and requires the value back. It asks from INSIDE the
# Redis pod rather than from the server's own container, because the thing under
# test includes Service DNS and cross-pod reachability, and a server curling
# itself proves neither.
#
# It also asks for a zone that MUST come back null (264, TLC's "Unknown", which
# has no centroid by DR-04 condition 1). A check that only ever asserts presence
# passes against a server that answers every question with the same row.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

NAMESPACE="feast"
MANIFEST="infra/manifests/feast-server.yaml"
RECORD_IN="automation/runs/m8-transformer/feast-server-image.json"
RECORD_OUT="automation/runs/m8-transformer/feast-server-deploy.json"
mkdir -p "$(dirname "$RECORD_OUT")"

if [[ "${TEARDOWN:-0}" == "1" ]]; then
  echo "[feast-server] TEARDOWN=1 — removing the Deployment and Service only."
  echo "[feast-server]   Redis, its PVC and its 57,688 keys are NOT touched: the store"
  echo "[feast-server]   is a different tenant with a different state class (ADR-012)."
  kubectl -n "$NAMESPACE" delete deploy/feast-server svc/feast-server --ignore-not-found
  kubectl -n "$NAMESPACE" get deploy,svc
  exit 0
fi

if [[ ! -f "$RECORD_IN" ]]; then
  echo "[feast-server] FAIL: $RECORD_IN is missing — run 'make feast-server-image' first." >&2
  exit 2
fi
IMAGE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["image"])' "$RECORD_IN")"

# A `-dirty` image carries uncommitted work and must not back a verdict — the
# M4-S3 rule, and M8-S1 leg 2 spent a rebuild learning to honour it.
if [[ "$IMAGE" == *-dirty ]]; then
  echo "[feast-server] FAIL: the built image is $IMAGE." >&2
  echo "[feast-server]   A '-dirty' tag means the image carries work that is not in git," >&2
  echo "[feast-server]   so nothing it produces can be attributed to a commit. Commit," >&2
  echo "[feast-server]   then 'make feast-server-image' again." >&2
  exit 3
fi
echo "[feast-server] image $IMAGE"

if [[ "${DRY_RUN:-0}" == "1" ]]; then
  echo "[feast-server] DRY_RUN=1 — nothing was applied."
  exit 0
fi

echo "[feast-server] applying $MANIFEST"
sed "s|FEAST_SERVER_IMAGE|$IMAGE|" "$MANIFEST" | kubectl apply -f -

echo "[feast-server] waiting for the rollout"
kubectl -n "$NAMESPACE" rollout status deploy/feast-server --timeout=300s

# ---------------------------------------------------------------- the accept ---
echo "[feast-server] ACCEPT: one online lookup, asked from the Redis pod (Service DNS included)"
BODY='{"features":["zone_static:centroid_lat","zone_static:centroid_lon","zone_static:is_airport"],"entities":{"zone_id":[132,264]}}'
ANSWER="$(kubectl -n "$NAMESPACE" exec deploy/redis -- \
  wget -q -O- --header='Content-Type: application/json' \
  --post-data="$BODY" \
  http://feast-server.feast.svc.cluster.local:6566/get-online-features)"
echo "[feast-server]   $ANSWER"

python3 - "$ANSWER" "$IMAGE" "$RECORD_OUT" <<'PY'
import json, subprocess, sys

answer, image, record = sys.argv[1], sys.argv[2], sys.argv[3]
payload = json.loads(answer)
names = payload["metadata"]["feature_names"]
values = {n: r["values"] for n, r in zip(names, payload["results"])}

failures = []
# JFK (132) is one of the three airport zones and it is IN the champion's matrix
# through all nine geometry features. Its centroid was measured at M3-S2 against
# the published airport point (0.63 km) and is committed.
lat, lon = values["centroid_lat"][0], values["centroid_lon"][0]
if not (isinstance(lat, float) and 40.5 < lat < 40.8):
    failures.append(f"zone 132 centroid_lat={lat!r} is not in the NYC latitude band")
if not (isinstance(lon, float) and -74.3 < lon < -73.6):
    failures.append(f"zone 132 centroid_lon={lon!r} is not in the NYC longitude band")
if values["is_airport"][0] is not True:
    failures.append(f"zone 132 is_airport={values['is_airport'][0]!r}, expected True")

# THE NEGATIVE HALF. 264 is TLC's "Unknown" — not a place — and it has no
# centroid BY DESIGN (DR-04 condition 1). A store that answered it a number
# would be inventing a location, and a check that never asks would not notice.
for column in ("centroid_lat", "centroid_lon"):
    if values[column][1] is not None:
        failures.append(
            f"zone 264 {column}={values[column][1]!r} — it must be null: 264 is TLC's "
            "'Unknown', not a place, and it carries no geometry by design"
        )

for f in failures:
    print(f"[feast-server] FAIL {f}")
if failures:
    sys.exit(1)

print(f"[feast-server] ok  zone 132 -> ({lat}, {lon}) is_airport=True")
print("[feast-server] ok  zone 264 -> null centroid, the no-geometry path answered as itself")

served = subprocess.run(
    ["kubectl", "-n", "feast", "get", "deploy", "feast-server",
     "-o", "jsonpath={.spec.template.spec.containers[0].image}"],
    capture_output=True, text=True, check=True).stdout.strip()
if served != image:
    print(f"[feast-server] FAIL the live Deployment runs {served!r}, not {image!r}")
    sys.exit(1)
print(f"[feast-server] ok  the live Deployment runs {served} — read back off the object")

with open(record, "w") as fh:
    json.dump(
        {
            "image": image,
            "service": "feast-server.feast.svc.cluster.local:6566",
            "accept": {
                "asked_from": "the redis pod, over Service DNS",
                "zone_132": {"centroid_lat": lat, "centroid_lon": lon, "is_airport": True},
                "zone_264": {"centroid_lat": None, "centroid_lon": None},
            },
            "note": (
                "M8-S4 leg 2 shape (i). Stateless: no volume, no ledger state class, "
                "registry derived from definitions.py at every start. The accept is an "
                "ANSWER asked from a different pod, and it asserts the null half too."
            ),
        },
        fh, indent=2, sort_keys=True)
    fh.write("\n")
print(f"[feast-server] recorded {record}")
PY

echo "[feast-server] GREEN"
