#!/usr/bin/env bash
# M9-S1 — the stakeholder demo page on the cluster, same-origin with the model.
#
# `DRY_RUN=1` mutates nothing (gotcha #30's rule, pinned by a test).
# `TEARDOWN=1` removes exactly its own four objects and touches nothing else.
#
# WHAT THIS DOES NOT DO, and the list matters more than what it does: it does not
# read the registry, resolve an alias, deploy a model, build an image, or touch
# either InferenceService. The demo is a READER of a boundary that already
# exists. `@champion` is not consulted anywhere in this file — a test asserts it
# cannot be, the M5-S1 precedent (`deploy-serving` installs no model).
#
# THE PAGE IS BUILT FROM THE FILE IN GIT, at apply time, with no second copy:
# `kubectl create configmap --from-file` renders demo/index.html into a ConfigMap
# and the pod template carries that file's sha256, so a changed page rolls the
# pod instead of waiting on kubelet's ConfigMap refresh window. The accept then
# fetches the page BACK through the route and hashes what a browser would get.
#
# THE WAIT HAS THREE LEGS and the third is the one this repo keeps re-learning
# (F-037, F-060, gotcha #106): a rollout can be complete and an ISVC can be Ready
# while nginx has not yet loaded the Ingress, so an accept check gets a bare 404
# that looks exactly like a wrong path. Leg 3 asks the ROUTE, under the same
# origin the browser will use, before anything is asserted about it.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

NAMESPACE="serving"
MANIFEST="infra/manifests/demo.yaml"
PAGE="demo/index.html"
ANALYTICS="demo/analytics.html"
ROUTE="${DEMO_ROUTE:-http://localhost:8081}"
CONFIGMAP="taxi-demo-page"
DEPLOYMENT="taxi-demo-page"
INGRESS="taxi-demo-route"

if [[ "${TEARDOWN:-0}" == "1" ]]; then
  echo "[demo] TEARDOWN=1 — removing the page's own four objects."
  echo "[demo]   Neither InferenceService, neither Service KServe owns, and no"
  echo "[demo]   feature-store object is touched: the demo never owned them."
  kubectl -n "$NAMESPACE" delete \
    ingress/"$INGRESS" deploy/"$DEPLOYMENT" svc/"$DEPLOYMENT" cm/"$CONFIGMAP" \
    --ignore-not-found
  kubectl -n "$NAMESPACE" get ingress
  exit 0
fi

# ---- the page must be the one the generator produces -------------------------
# A demo whose committed HTML has drifted from the zone lookup would render a
# picker the model does not share. Refuse before deploying, not after.
uv run python scripts/build_demo_page.py --check

PAGE_SHA="$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$PAGE")"
echo "[demo] page $PAGE sha256 ${PAGE_SHA:0:16}…"

# The analytics companion is a second key in the SAME ConfigMap, so the roll
# trigger must cover it too: a pod rolled only on index.html's sha would keep
# serving a stale analytics page until kubelet's ConfigMap refresh window. The
# annotation therefore carries the sha256 over BOTH served files, in a fixed
# order, and leg 2 compares against that.
ANALYTICS_SHA="$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$ANALYTICS")"
echo "[demo] page $ANALYTICS sha256 ${ANALYTICS_SHA:0:16}…"
SERVED_SHA="$(printf '%s%s' "$PAGE_SHA" "$ANALYTICS_SHA" | python3 -c 'import hashlib,sys; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())')"

# ---- F-039's precondition, asked of the cluster and not of the manifest ------
# A hand-authored object must never take a name an operator GENERATES: the
# collision is accepted, works for seconds, and is then reconciled away with no
# error anywhere. `taxi-demo-*` collides with nothing KServe generates, and this
# check is what makes that a fact about the cluster rather than about a naming
# convention somebody remembered.
for kind_name in "ingress/$INGRESS" "deploy/$DEPLOYMENT" "service/$DEPLOYMENT"; do
  owners="$(kubectl -n "$NAMESPACE" get "$kind_name" \
    -o jsonpath='{.metadata.ownerReferences[*].kind}/{.metadata.ownerReferences[*].name}' \
    2>/dev/null || true)"
  if [[ -n "${owners:-}" && "$owners" != "/" ]]; then
    echo "[demo] FAIL: $kind_name already exists and is OWNED by $owners." >&2
    echo "[demo]   Writing to a controller-owned object is F-039: the write is" >&2
    echo "[demo]   accepted and then reverted, and the symptom is silence." >&2
    exit 3
  fi
done
echo "[demo] ok  no controller owns the four names this story writes"

if [[ "${DRY_RUN:-0}" == "1" ]]; then
  echo "[demo] DRY_RUN=1 — nothing was applied."
  echo "[demo]   would create configmap/$CONFIGMAP from $PAGE + $ANALYTICS"
  echo "[demo]   would apply $MANIFEST with PAGE_SHA256=$SERVED_SHA"
  exit 0
fi

# ---- apply -------------------------------------------------------------------
echo "[demo] rendering configmap/$CONFIGMAP from $PAGE + $ANALYTICS (the files in git are the only copies)"
kubectl -n "$NAMESPACE" create configmap "$CONFIGMAP" \
  --from-file=index.html="$PAGE" \
  --from-file=analytics.html="$ANALYTICS" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "[demo] applying $MANIFEST"
sed "s|PAGE_SHA256|$SERVED_SHA|" "$MANIFEST" | kubectl apply -f -

echo "[demo] leg 1/3 — the rollout"
kubectl -n "$NAMESPACE" rollout status deploy/"$DEPLOYMENT" --timeout=180s

echo "[demo] leg 2/3 — the pod is serving the sha the deploy asked for"
LIVE_SHA="$(kubectl -n "$NAMESPACE" get deploy "$DEPLOYMENT" \
  -o jsonpath='{.spec.template.metadata.annotations.taxi-mlops\.io/page-sha256}')"
if [[ "$LIVE_SHA" != "$SERVED_SHA" ]]; then
  echo "[demo] FAIL: the live pod template carries $LIVE_SHA, not $SERVED_SHA" >&2
  exit 1
fi
echo "[demo] ok  pod template annotation == the sha256 over both committed pages"

echo "[demo] leg 3/3 — the ROUTE answers, under the origin the browser will use"
deadline=$((SECONDS + 120))
code=000
while (( SECONDS < deadline )); do
  code="$(curl -s -o /dev/null -w '%{http_code}' "$ROUTE/demo/" || true)"
  [[ "$code" == "200" ]] && break
  sleep 2
done
if [[ "$code" != "200" ]]; then
  echo "[demo] FAIL: $ROUTE/demo/ answered $code after 120s." >&2
  echo "[demo]   A route that is not loaded and a route that is wrong are the" >&2
  echo "[demo]   same bytes (gotcha #106) — so nothing is asserted until this" >&2
  echo "[demo]   leg passes." >&2
  exit 1
fi
echo "[demo] ok  GET $ROUTE/demo/ -> 200"

# ---- the analytics companion serves the committed bytes ----------------------
# Same property leg 3 protects for index.html, asserted for the second key: a
# ConfigMap that silently dropped a file would leave /demo/analytics.html a 404
# that reads exactly like a wrong path (gotcha #106), and a stale key would
# serve yesterday's numbers under today's sha. Fetch it back through the route
# and hash what a browser would get.
FETCHED_SHA="$(curl -s "$ROUTE/demo/analytics.html" | python3 -c 'import hashlib,sys; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())')"
if [[ "$FETCHED_SHA" != "$ANALYTICS_SHA" ]]; then
  echo "[demo] FAIL: $ROUTE/demo/analytics.html served sha $FETCHED_SHA," >&2
  echo "[demo]   the committed $ANALYTICS is $ANALYTICS_SHA — the route is up but" >&2
  echo "[demo]   the analytics page is missing or stale in the ConfigMap." >&2
  exit 1
fi
echo "[demo] ok  GET $ROUTE/demo/analytics.html serves the committed bytes (sha256 match)"

# ---- the invariants this route must NOT have disturbed ----------------------
# The rule is host-less, so it lands in nginx's DEFAULT server block — the same
# block that answers /healthz and falls through to the default backend on /.
# Both are asserted here rather than left to the next `make deploy-serving` to
# discover, because a demo that quietly broke M5's accept check would be exactly
# the self-inflicted gotcha #50 this design was chosen to avoid.
health="$(curl -s -o /dev/null -w '%{http_code}' "$ROUTE/healthz" || true)"
root="$(curl -s -o /dev/null -w '%{http_code}' "$ROUTE/" || true)"
fails=0
[[ "$health" == "200" ]] || { echo "[demo] FAIL: $ROUTE/healthz -> $health, expected 200"; fails=1; }
[[ "$root" == "404" ]] || { echo "[demo] FAIL: $ROUTE/ -> $root, expected 404"; fails=1; }
(( fails == 0 )) || exit 1
echo "[demo] ok  deploy_serving.sh's two accept invariants still hold: /healthz 200, / 404"

echo "[demo] GREEN — the page is at $ROUTE/demo/"
echo "[demo] the accept check is 'make demo-accept' — this script deploys, it does not judge."
