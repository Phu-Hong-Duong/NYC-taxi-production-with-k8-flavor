#!/usr/bin/env bash
# M8-S4 leg 3 — the transformer beside the champion, and an accept check that is
# a QUOTE FROM A RAW REQUEST.
#
# `DRY_RUN=1` mutates nothing (gotcha #30's rule, pinned by a test).
# `TEARDOWN=1` deletes exactly this InferenceService and nothing else — the
# M6-S3 shadow precedent, which is also how this story proves the champion's own
# objects were never touched.
#
# THE ALIAS IS READ AND NEVER MOVED (M8 law 3, M5's law 2 inherited). It is read
# BEFORE and AFTER every mutation and a change is a FAILURE, not a warning.
#
# THE ACCEPT IS THE ARTIFACT THIS THING EXISTS TO PRODUCE (gotcha #59): a rider's
# RAW question — a time, two zone ids, a party size — answered with a number.
# A ready pod proves the platform; only a number proves that 24 features were
# derived in a pod from stored lookups and that the champion ate them. And it
# asserts the NEGATIVE half too (the M6-S4 idiom): the transformer must 404 on
# the champion's own model name, because a service answering to both names would
# pass a positive-only check and prove nothing about which boundary answered.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")
SERVING_NS="serving"
ISVC_NAME="nyc-taxi-eta-transformer"
CHAMPION_NAME="nyc-taxi-eta"
MANIFEST="infra/manifests/inferenceservice-transformer.yaml"
IMAGE_RECORD="automation/runs/m4-image/image.json"
RECORD_OUT="automation/runs/m8-transformer/transformer-deploy.json"
WAIT_TIMEOUT="${TRANSFORMER_WAIT_TIMEOUT:-15m}"
mkdir -p "$(dirname "$RECORD_OUT")"

if [[ "${TEARDOWN:-0}" == "1" ]]; then
  echo "[transformer] TEARDOWN=1 — deleting InferenceService/$ISVC_NAME only."
  echo "[transformer]   The champion's own isvc, the feature server and Redis are NOT touched."
  "${KUBECTL[@]}" -n "$SERVING_NS" delete "inferenceservice/$ISVC_NAME" --ignore-not-found
  echo
  echo "[transformer] what is left in $SERVING_NS:"
  "${KUBECTL[@]}" -n "$SERVING_NS" get isvc,deploy,svc,ingress
  exit 0
fi

# The route. Read from the kind config for gotcha #52's reason (derive, never
# type), exactly as deploy_champion.sh does.
ROUTE_PORT="$(python3 - "infra/kind/kind-config.yaml" <<'PY'
import sys

import yaml

cfg = yaml.safe_load(open(sys.argv[1]))
for node in cfg["nodes"]:
    for mapping in node.get("extraPortMappings", []):
        if mapping["containerPort"] == 80:
            print(mapping["hostPort"])
            sys.exit(0)
sys.exit("no extraPortMapping publishes containerPort 80")
PY
)"
ROUTE="http://localhost:$ROUTE_PORT"
ISVC_HOST="$ISVC_NAME-$SERVING_NS.local"

if [[ ! -f "$IMAGE_RECORD" ]]; then
  echo "[transformer] FAIL: $IMAGE_RECORD is missing — run 'make image-load' first." >&2
  exit 2
fi
IMAGE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["image_ref"])' "$IMAGE_RECORD")"

# A `-dirty` image carries uncommitted work and must not back a verdict (M4-S3).
if [[ "$IMAGE" == *-dirty ]]; then
  echo "[transformer] FAIL: the task image is $IMAGE." >&2
  echo "[transformer]   Commit the tree and re-run 'make image-load'." >&2
  exit 3
fi

# F-026's guard, one service along: this pod's `src/taxi_mlops` comes from the
# IMAGE, so an image built before the seam landed would serve the PREVIOUS
# feature code with a perfectly green transcript. The image's own manifest
# records the sha it was built at.
BUILT_AT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("git_sha",""))' \
  "$IMAGE_RECORD" 2>/dev/null || true)"
CHANGED="$(git diff --name-only "${BUILT_AT:-HEAD}" -- src pyproject.toml uv.lock docker 2>/dev/null || true)"
if [[ -n "$CHANGED" ]]; then
  echo "[transformer] FAIL: the image was built at ${BUILT_AT:-?} and these have changed since:" >&2
  printf '  %s\n' $CHANGED >&2
  echo "[transformer]   The transformer's feature code comes from the image (F-026)." >&2
  echo "[transformer]   Run 'make image-load' and try again." >&2
  exit 3
fi

echo "== the transformer beside the champion =="
echo "   route     $ROUTE  (Host: $ISVC_HOST)"
echo "   image     $IMAGE"
echo "   model     resolved from the ALIAS at deploy time — never typed"

if [[ "${DRY_RUN:-0}" == "1" ]]; then
  echo
  echo "== [1/4] resolve ==  DRY_RUN — WOULD read models:/$CHAMPION_NAME@champion (a READ)"
  echo "== [2/4] apply ==    DRY_RUN — WOULD apply $MANIFEST with image $IMAGE"
  echo "== [3/4] wait ==     DRY_RUN — WOULD wait for deploy/$ISVC_NAME-{predictor,transformer}"
  echo "== [4/4] accept ==   DRY_RUN — WOULD POST one RAW quote to $ROUTE/v2/models/$ISVC_NAME/infer"
  echo
  echo "DRY_RUN — nothing was applied and no InferenceService was created."
  exit 0
fi

champion_version() {
  uv run python scripts/resolve_champion_storage.py 2>/dev/null \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])'
}
ALIAS_BEFORE="$(champion_version)"
echo "   @champion is version $ALIAS_BEFORE (read before any change)"

echo
echo "== [1/4] resolve the alias (F-009's two hops, in ONE place) =="
RESOLVED="$(uv run python scripts/resolve_champion_storage.py 2>/dev/null)"
STORAGE_URI="$(printf '%s' "$RESOLVED" | python3 -c 'import json,sys; print(json.load(sys.stdin)["storage_uri"])')"
VERSION="$(printf '%s' "$RESOLVED" | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])')"
echo "   models:/$CHAMPION_NAME@champion -> version $VERSION"
echo "   the SAME bytes the champion serves: $STORAGE_URI"

echo
echo "== [2/4] the InferenceService =="
RENDERED="$(mktemp)"
trap 'rm -f "$RENDERED"' EXIT
python3 - "$MANIFEST" "$STORAGE_URI" "$VERSION" "$IMAGE" > "$RENDERED" <<'PY'
import sys

path, storage_uri, version, image = sys.argv[1:5]
substitutions = {
    "RESOLVED-AT-DEPLOY-TIME-FROM-THE-CHAMPION-ALIAS": storage_uri,
    "CHAMPION-VERSION-RESOLVED-AT-DEPLOY-TIME": f'"{version}"',
    "TASK_IMAGE_RESOLVED_AT_DEPLOY_TIME": image,
}
text = open(path).read()
for placeholder, value in substitutions.items():
    if placeholder not in text:
        sys.exit(f"{path} no longer carries {placeholder} — refusing to guess")
    text = text.replace(placeholder, value)
sys.stdout.write(text)
PY
"${KUBECTL[@]}" apply -f "$RENDERED"

echo
echo "== [3/4] wait for BOTH halves =="
# `rollout status` FIRST and on BOTH Deployments — gotcha #71: on a re-deploy the
# InferenceService's Ready condition is satisfied by the pods being replaced, so
# a condition wait can return while the new transformer is still Init. And the
# second leg is `--for=jsonpath=` and not `--for=condition=`, which is F-036:
# kubectl v1.36 refuses to read conditions while observedGeneration trails
# generation, and KServe v0.20.0 leaves it behind on every re-deploy.
for component in predictor transformer; do
  "${KUBECTL[@]}" -n "$SERVING_NS" rollout status \
    "deploy/$ISVC_NAME-$component" --timeout="$WAIT_TIMEOUT"
done
"${KUBECTL[@]}" -n "$SERVING_NS" wait \
  --for=jsonpath='{.status.conditions[?(@.type=="Ready")].status}'=True \
  "inferenceservice/$ISVC_NAME" --timeout="$WAIT_TIMEOUT"
"${KUBECTL[@]}" -n "$SERVING_NS" get pods -o wide \
  -l "serving.kserve.io/inferenceservice=$ISVC_NAME"

echo
echo "   what the transformer process ACTUALLY resolved (read off its own log,"
echo "   never off the manifest that was submitted):"
"${KUBECTL[@]}" -n "$SERVING_NS" logs "deploy/$ISVC_NAME-transformer" --tail=20 \
  | sed -n 's/^\[transformer\] /     /p' || true

echo
echo "== [4/4] accept — a RAW request, answered =="
uv run python scripts/transformer_accept.py --route "$ROUTE" --record "$RECORD_OUT"

echo
ALIAS_AFTER="$(champion_version)"
if [[ "$ALIAS_BEFORE" != "$ALIAS_AFTER" ]]; then
  echo "FAIL: @champion moved from $ALIAS_BEFORE to $ALIAS_AFTER during a DEPLOY." >&2
  exit 2
fi
echo "ok  @champion is version $ALIAS_AFTER — unchanged across this deploy"
echo "ok  $ISVC_NAME answers RAW requests on $ROUTE (Host: $ISVC_HOST)"
