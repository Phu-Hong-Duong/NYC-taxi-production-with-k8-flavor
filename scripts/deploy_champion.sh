#!/usr/bin/env bash
# deploy_champion.sh — the champion on the wire (M5-S2), behind `make serve`.
#
# It puts ONE model on the platform M5-S1 installed: a read-only MinIO identity,
# the ServingRuntime that image runs in, and an InferenceService whose storageUri
# is RESOLVED FROM THE ALIAS at deploy time.
#
#   secrets -> minio (the readonly `serving` user) -> resolve @champion
#           -> ServingRuntime -> ServiceAccount+Secret -> InferenceService
#           -> ready -> the route answers with a PREDICTION
#
# THE ALIAS IS READ AND NEVER MOVED (M5 kickoff law 2). The version is read
# BEFORE and AFTER every mutation this script makes and a change is a FAILURE,
# not a warning — the M4 runner's shape. Nothing here calls a mutating registry
# API; `scripts/resolve_champion_storage.py` is a reader and a test pins that.
#
# THE CLUSTER IS STATEFUL AND THIS SCRIPT NEVER TAKES IT DOWN (law 1). It
# publishes no host port — it uses the route M5-S1 stood up — touches no PVC and
# no database, and the only helm release it upgrades is MinIO, converge-only, to
# add a user. `purge: false` on every bucket is unchanged.
#
# SELF-SUFFICIENT (the M1-S5 rule, inherited a fourth time): it re-runs the
# secrets and MinIO legs it depends on rather than documenting "run
# deploy-platform first", so it cannot be defeated by running order.
#
# NO SECRET REACHES A COMMAND LINE. The predictor's credential is applied with
# `create secret --dry-run=client -o yaml | kubectl apply -f -`, the shape
# platform_secrets.sh uses, and is never echoed.
#
# Usage: scripts/deploy_champion.sh            (via `make serve`)
#        DRY_RUN=1 scripts/deploy_champion.sh  (prints the plan, mutates NOTHING
#                                               — helm included, gotcha #30)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")
HELM=(helm --kube-context "$CONTEXT")
DRY_RUN="${DRY_RUN:-0}"
WAIT_TIMEOUT="${SERVE_WAIT_TIMEOUT:-15m}"

SERVING_NS="serving"
ISVC_NAME="nyc-taxi-eta"
RUNTIME_MANIFEST="$REPO_ROOT/infra/manifests/serving-runtime-mlserver.yaml"
ISVC_MANIFEST="$REPO_ROOT/infra/manifests/inferenceservice-champion.yaml"
MINIO_CHART_VERSION="5.4.0"       # the pin deploy_platform.sh owns; asserted below

# The in-cluster MinIO name, NOT the host one. F-023's lesson from the other
# side: split horizon is the HOST's problem and never a pod's — a pod that was
# handed `localhost:9000` would resolve it to itself.
MINIO_ENDPOINT="minio.platform.svc.cluster.local:9000"

# The route and its Host header. The port is read from the kind config for the
# same reason deploy_serving.sh reads it (gotcha #52: derive, never type); the
# host is what KServe's domainTemplate builds, so it is a function of the
# InferenceService's own name and namespace.
KIND_CONFIG="$REPO_ROOT/infra/kind/kind-config.yaml"
ROUTE_PORT="$(python3 - "$KIND_CONFIG" <<'PY'
import sys
import yaml

cfg = yaml.safe_load(open(sys.argv[1]))
for node in cfg["nodes"]:
    for mapping in node.get("extraPortMappings", []):
        if mapping["containerPort"] == 80:
            print(mapping["hostPort"])
            sys.exit(0)
sys.exit("no extraPortMapping publishes containerPort 80 — the M5 route does not exist")
PY
)"
ROUTE="http://localhost:$ROUTE_PORT"
ISVC_HOST="$ISVC_NAME-$SERVING_NS.local"

echo "== the champion on the wire =="
echo "   route     $ROUTE  (Host: $ISVC_HOST)"
echo "   runtime   $(basename "$RUNTIME_MANIFEST")"
echo "   model     resolved from the ALIAS at deploy time — never typed"

# ------------------------------------------------------------------ DRY_RUN --
if [[ "$DRY_RUN" == "1" ]]; then
  echo
  echo "== [1/7] secrets ==     DRY_RUN — WOULD run scripts/platform_secrets.sh (adds minio-serving-user)"
  echo "== [2/7] minio ==       DRY_RUN — WOULD converge minio $MINIO_CHART_VERSION (adds the 'serving' user + the serving-readonly policy)"
  echo "== [3/7] resolve ==     DRY_RUN — WOULD read models:/$ISVC_NAME@champion (a READ; the alias is never moved)"
  echo "== [4/7] runtime ==     DRY_RUN — WOULD apply $RUNTIME_MANIFEST"
  echo "== [5/7] credential ==  DRY_RUN — WOULD apply serviceaccount/taxi-serving + secret/minio-serving in $SERVING_NS"
  echo "== [6/7] isvc ==        DRY_RUN — WOULD apply $ISVC_MANIFEST with the resolved storageUri"
  echo "== [7/7] accept ==      DRY_RUN — WOULD POST one quote to $ROUTE/v2/models/$ISVC_NAME/infer"
  echo
  echo "DRY_RUN — nothing was applied, no helm release was upgraded, no secret was written."
  exit 0
fi

# The alias BEFORE anything. Read from the registry, printed, and compared at the
# end: this script's strongest claim is that it changed nothing about what is
# champion, and a claim nobody checks is a sentence.
champion_version() {
  uv run python scripts/resolve_champion_storage.py 2>/dev/null \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])'
}
ALIAS_BEFORE="$(champion_version)"
echo "   @champion is version $ALIAS_BEFORE (read before any change)"

echo
echo "== [1/7] secrets from .env (adds minio-serving-user) =="
bash "$REPO_ROOT/scripts/platform_secrets.sh"

echo
echo "== [2/7] MinIO — the READ-ONLY 'serving' identity =="
# The chart's post-install Job is what creates users idempotently. Converging the
# release is how the identity comes into being from the recipe rather than from
# somebody's `mc admin user add` — the same argument deploy_flyte.sh makes for
# the flyte-data bucket.
"${HELM[@]}" upgrade --install minio minio/minio \
  --version "$MINIO_CHART_VERSION" \
  --namespace platform --create-namespace \
  -f "$REPO_ROOT/infra/helm/minio/values.yaml" \
  --wait --timeout 10m
"${KUBECTL[@]}" -n platform rollout status deployment/minio --timeout=300s

echo
echo "== [3/7] resolve the alias (F-009's two hops, in ONE place) =="
RESOLVED="$(uv run python "$REPO_ROOT/scripts/resolve_champion_storage.py" 2>/dev/null)"
STORAGE_URI="$(printf '%s' "$RESOLVED" | python3 -c 'import json,sys; print(json.load(sys.stdin)["storage_uri"])')"
REGISTRY_SOURCE="$(printf '%s' "$RESOLVED" | python3 -c 'import json,sys; print(json.load(sys.stdin)["registry_source"])')"
VERSION="$(printf '%s' "$RESOLVED" | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])')"
echo "   models:/$ISVC_NAME@champion -> version $VERSION"
echo "   the registry's own source   : $REGISTRY_SOURCE   <- EMPTY prefix (F-009)"
echo "   what KServe will download   : $STORAGE_URI"

echo
echo "== [4/7] the ServingRuntime =="
"${KUBECTL[@]}" apply -f "$RUNTIME_MANIFEST"

echo
echo "== [5/7] the predictor's read-only credential =="
# The endpoint and the region are NOT secret and live in annotations where a diff
# can read them; only the two key values come from .env, and neither is echoed.
set -a; source "$REPO_ROOT/.env"; set +a
"${KUBECTL[@]}" -n "$SERVING_NS" create secret generic minio-serving \
  --from-literal=AWS_ACCESS_KEY_ID="$SERVING_S3_ACCESS_KEY" \
  --from-literal=AWS_SECRET_ACCESS_KEY="$SERVING_S3_SECRET_KEY" \
  --dry-run=client -o yaml \
  | "${KUBECTL[@]}" annotate --local -f - -o yaml \
      "serving.kserve.io/s3-endpoint=$MINIO_ENDPOINT" \
      "serving.kserve.io/s3-usehttps=0" \
      "serving.kserve.io/s3-region=${AWS_DEFAULT_REGION:-us-east-1}" \
  | "${KUBECTL[@]}" apply -f - >/dev/null
echo "   ok  $SERVING_NS/minio-serving (endpoint $MINIO_ENDPOINT, https off — in-cluster)"

"${KUBECTL[@]}" -n "$SERVING_NS" apply -f - >/dev/null <<YAML
apiVersion: v1
kind: ServiceAccount
metadata:
  name: taxi-serving
  namespace: $SERVING_NS
secrets:
  - name: minio-serving
YAML
echo "   ok  $SERVING_NS/taxi-serving (serviceaccount)"

echo
echo "== [6/7] the InferenceService =="
# The placeholder is replaced with the RESOLVED uri. A python one-liner and not
# `sed` because the value contains slashes and a `sed s|..|..|` whose delimiter
# collides with the payload is the kind of thing that half-works.
python3 - "$ISVC_MANIFEST" "$STORAGE_URI" "$VERSION" > /tmp/isvc-rendered.$$.yaml <<'PY'
import sys

path, storage_uri, version = sys.argv[1], sys.argv[2], sys.argv[3]
substitutions = {
    "RESOLVED-AT-DEPLOY-TIME-FROM-THE-CHAMPION-ALIAS": storage_uri,
    "CHAMPION-VERSION-RESOLVED-AT-DEPLOY-TIME": f'"{version}"',
}
text = open(path).read()
for placeholder, value in substitutions.items():
    if placeholder not in text:
        sys.exit(f"{path} no longer carries the {placeholder} placeholder — refusing to guess")
    text = text.replace(placeholder, value)
sys.stdout.write(text)
PY
trap 'rm -f /tmp/isvc-rendered.$$.yaml' EXIT
"${KUBECTL[@]}" apply -f /tmp/isvc-rendered.$$.yaml

echo
echo "   waiting for the predictor (first start downloads $STORAGE_URI)…"
# THE ROLLOUT FIRST, AND THAT ORDER IS THE FIX FOR A REAL FALSE GREEN. On a
# RE-deploy the InferenceService's `Ready` condition is satisfied by the pod
# ALREADY SERVING, so `kubectl wait --for=condition=Ready inferenceservice`
# returns instantly while the new pod is still `Init:0/1` — and the accept check
# below then interrogates the OLD predictor and passes. Watched happen on this
# story's third deploy: the new pod was 0 s old and `Init:0/1` in the very
# `get pods` this script prints, and the quote came back from its predecessor
# reporting `(unversioned)` when the change under test was the version stamp.
# `rollout status` waits for the new ReplicaSet specifically; the ISVC condition
# stays as the second leg because it is what KServe itself considers serving.
# Siblings of gotchas #59/#65: a wait that can be satisfied by the thing you are
# replacing is not a wait.
"${KUBECTL[@]}" -n "$SERVING_NS" rollout status \
  "deploy/$ISVC_NAME-predictor" --timeout="$WAIT_TIMEOUT"
"${KUBECTL[@]}" -n "$SERVING_NS" wait --for=condition=Ready \
  "inferenceservice/$ISVC_NAME" --timeout="$WAIT_TIMEOUT"
"${KUBECTL[@]}" -n "$SERVING_NS" get pods -o wide -l "serving.kserve.io/inferenceservice=$ISVC_NAME"

echo
echo "== [7/7] read it back — a PREDICTION, not a health check =="
# gotcha #59, and the shape M5-S1 had to learn twice: assert on the artifact this
# thing exists to produce. A ready pod and a 200 on /v2/models prove the platform;
# only a NUMBER proves the champion is loaded and answering. The request is built
# through the ONE feature path, so this line is also the first end-to-end proof
# that training and serving agree about what a feature is — the MEASURED version
# of that is M5-S3's parity test and this is not it.
uv run python -m taxi_mlops.serving --route "$ROUTE" --at "2019-07-04T09:15:00"

echo
ALIAS_AFTER="$(champion_version)"
if [[ "$ALIAS_BEFORE" != "$ALIAS_AFTER" ]]; then
  echo "FAIL: @champion moved from $ALIAS_BEFORE to $ALIAS_AFTER during a DEPLOY." >&2
  echo "      M5 is legislated alias-neutral (kickoff law 2). Nothing in this" >&2
  echo "      script calls a mutating registry API, so something else did." >&2
  exit 2
fi
echo "ok  @champion is version $ALIAS_AFTER — the same version this script read before it started"
echo "ok  $ISVC_NAME answers on $ROUTE (Host: $ISVC_HOST)"
