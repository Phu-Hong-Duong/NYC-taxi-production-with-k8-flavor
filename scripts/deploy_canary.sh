#!/usr/bin/env bash
# deploy_canary.sh — the challenger PATH, carrying the champion's own bytes (M6-S4).
#
# What a release rehearsal needs is a second place for rider traffic to go. This
# script builds it and then PROVES the one thing ADR-011 could only name:
#
#   resolve @champion -> InferenceService (MLSERVER_MODEL_NAME overridden)
#                     -> rollout -> ready -> route
#                     -> the canary's OWN host answers /v2/models/nyc-taxi-eta/infer
#                        with a NUMBER, and 404s on its own isvc name
#                     -> the dedicated backend Service, selector ASSERTED
#
# ADR-011 CONDITION 2, PROVED HERE OR NOWHERE. M6-S3 measured that canary-routed
# traffic returns **404**: the V2 model name is in the URL path, KServe injects
# `MLSERVER_MODEL_NAME` from the InferenceService name, and a canary Ingress
# cannot rewrite the path (`rewrite-target` changed the share by 0 points).
# `MLSERVER_MODEL_NAME: nyc-taxi-eta` on this isvc is the NAMED BUT UNPROVEN
# remedy the M6-S3 handoff routed here. Step [4/6] is the proof and it has a
# NEGATIVE half — the canary must 404 on `nyc-taxi-eta-canary` — because a
# service answering to both names would pass a positive-only check while telling
# us nothing about which name carried the request.
#
# THREE THINGS IT DOES NOT DO.
#
# 1. IT NEVER TOUCHES THE ALIAS. `@champion` is read before and after; a change
#    is a FAILURE (M6 law 3, the shadow deploy's inheritance verbatim).
#
# 2. IT MOVES NO TRAFFIC. No canary Ingress is created here — this script only
#    builds the destination. The weight is `scripts/canary_release_drill.py`'s,
#    under load, measured from counters. Deploy and release are separate acts and
#    the split second of a release should not be hiding inside a model download.
#
# 3. IT DOES NOT RE-DEPLOY THE CHAMPION. Adding a second InferenceService is an
#    ADDITION; the champion's Deployment is not in this script's blast radius and
#    its pod age proves it afterwards. In particular nothing here annotates an
#    isvc — F-038 cost 174 of 200 requests a 502 doing exactly that.
#
# Usage: scripts/deploy_canary.sh                 (via `make canary-deploy`)
#        DRY_RUN=1 scripts/deploy_canary.sh       (prints the plan, mutates NOTHING)
#        TEARDOWN=1 scripts/deploy_canary.sh      (removes the canary and its
#                                                  backend Service; the champion
#                                                  is not touched)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")
# The deploy skeleton (CU-S5), sourced after REPO_ROOT and KUBECTL.
source "$REPO_ROOT/scripts/lib/isvc_deploy.sh"
DRY_RUN="${DRY_RUN:-0}"
TEARDOWN="${TEARDOWN:-0}"
WAIT_TIMEOUT="${CANARY_WAIT_TIMEOUT:-15m}"

SERVING_NS="serving"
CHAMPION_NAME="nyc-taxi-eta"
CANARY_NAME="nyc-taxi-eta-canary"
CANARY_BACKEND="nyc-taxi-eta-canary-backend"
# The hand-authored route. NOT `$CANARY_NAME`: that name belongs to the Ingress
# KServe generates for this InferenceService, and writing canary annotations onto
# it is accepted, reverted within seconds, and completely silent (F-039).
CANARY_ROUTE="nyc-taxi-eta-canary-route"
CANARY_MANIFEST="$REPO_ROOT/infra/manifests/inferenceservice-canary.yaml"
BACKEND_MANIFEST="$REPO_ROOT/infra/manifests/canary-backend-service.yaml"

# The route port is READ from the kind config, never typed (gotcha #52).
KIND_CONFIG="$REPO_ROOT/infra/kind/kind-config.yaml"
ROUTE_PORT="$(isvc_route_port "$KIND_CONFIG")"
ROUTE="http://localhost:$ROUTE_PORT"
CANARY_HOST="$CANARY_NAME-$SERVING_NS.local"

echo "== the canary path =="
echo "   route      $ROUTE  (Host: $CANARY_HOST — its OWN host; no rider traffic yet)"
echo "   model      models:/$CHAMPION_NAME@champion — the champion's own bytes"
echo "   traffic    NONE. The weight is the drill's, not the deploy's."

# ---------------------------------------------------------------- TEARDOWN --
if [[ "$TEARDOWN" == "1" ]]; then
  echo
  echo "== teardown =="
  # The Ingress first, in case a drill died holding a weight: a canary route
  # pointing at a Service that is about to disappear would send rider traffic to
  # a 503 for as long as it took to delete the rest.
  "${KUBECTL[@]}" -n "$SERVING_NS" delete ingress "$CANARY_ROUTE" --ignore-not-found
  "${KUBECTL[@]}" -n "$SERVING_NS" delete svc "$CANARY_BACKEND" --ignore-not-found
  "${KUBECTL[@]}" -n "$SERVING_NS" delete inferenceservice "$CANARY_NAME" --ignore-not-found
  echo "ok  $CANARY_NAME removed (the champion was not touched)"
  exit 0
fi

# ------------------------------------------------------------------ DRY_RUN --
if [[ "$DRY_RUN" == "1" ]]; then
  echo
  echo "== [1/6] resolve ==  DRY_RUN — WOULD read models:/$CHAMPION_NAME@champion (a READ)"
  echo "== [2/6] isvc ==     DRY_RUN — WOULD apply $CANARY_MANIFEST with the resolved storageUri"
  echo "== [3/6] route ==    DRY_RUN — WOULD poll $ROUTE/v2/models/$CHAMPION_NAME/ready on $CANARY_HOST"
  echo "== [4/6] name ==     DRY_RUN — WOULD prove ADR-011 condition 2 both ways"
  echo "== [5/6] backend ==  DRY_RUN — WOULD apply $BACKEND_MANIFEST and assert its selector"
  echo "== [6/6] invariant== DRY_RUN — WOULD re-read @champion and re-quote the champion's host"
  echo
  echo "DRY_RUN — nothing was applied, no InferenceService was created."
  exit 0
fi

ALIAS_BEFORE="$(isvc_champion_version)"
echo "   @champion is version $ALIAS_BEFORE (read before any change)"

echo
echo "== [1/6] resolve @champion (F-009's two hops, exactly as the champion deploy does) =="
RESOLVED="$(uv run python "$REPO_ROOT/scripts/resolve_champion_storage.py" 2>/dev/null)"
read_field() { printf '%s' "$RESOLVED" | python3 -c "import json,sys; print(json.load(sys.stdin)[\"$1\"] or '')"; }
STORAGE_URI="$(read_field storage_uri)"
CANARY_VERSION="$(read_field version)"
FEATURE_SET="$(read_field feature_set)"
RUN_ID="$(read_field run_id)"
if [[ -z "$FEATURE_SET" ]]; then
  echo "FAIL: the champion version carries no feature_set tag — refusing to guess" >&2
  exit 2
fi
echo "   models:/$CHAMPION_NAME@champion -> version $CANARY_VERSION, run $RUN_ID"
echo "   feature set (from the version's OWN tag): $FEATURE_SET"
echo "   what KServe will download                : $STORAGE_URI"

echo
echo "== [2/6] the canary InferenceService =="
python3 - "$CANARY_MANIFEST" "$STORAGE_URI" "$CANARY_VERSION" > "/tmp/isvc-canary.$$.yaml" <<'PY'
import sys

path, storage_uri, version = sys.argv[1], sys.argv[2], sys.argv[3]
substitutions = {
    "RESOLVED-AT-DEPLOY-TIME-FROM-THE-CHAMPION-ALIAS": storage_uri,
    "CANARY-VERSION-RESOLVED-AT-DEPLOY-TIME": f'"{version}"',
}
text = open(path).read()
for placeholder, value in substitutions.items():
    if placeholder not in text:
        sys.exit(f"{path} no longer carries the {placeholder} placeholder — refusing to guess")
    text = text.replace(placeholder, value)
sys.stdout.write(text)
PY
trap 'rm -f "/tmp/isvc-canary.$$.yaml"' EXIT
"${KUBECTL[@]}" apply -f "/tmp/isvc-canary.$$.yaml"

echo
echo "   waiting for the canary predictor (first start downloads $STORAGE_URI)…"
# `rollout status` FIRST, the jsonpath wait SECOND — gotchas #71 and #79, both
# argued and pinned in `scripts/lib/isvc_deploy.sh`.
isvc_wait_ready "$SERVING_NS" "$CANARY_NAME" "$WAIT_TIMEOUT"

# The override has to be checked on the OBJECT as well as on the wire: KServe
# injects MLSERVER_MODEL_NAME itself, and "our value won the merge" is a fact
# about the Deployment, while "the model answers to that name" is a fact about
# mlserver. Both are asserted, because either alone can be true while the release
# mechanism is broken.
INJECTED_NAME="$("${KUBECTL[@]}" -n "$SERVING_NS" get deploy "$CANARY_NAME-predictor" \
  -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="MLSERVER_MODEL_NAME")].value}')"
echo "   MLSERVER_MODEL_NAME on the canary Deployment: '$INJECTED_NAME'"
if [[ "$INJECTED_NAME" != "$CHAMPION_NAME" ]]; then
  echo "FAIL: KServe kept its own MLSERVER_MODEL_NAME ('$INJECTED_NAME'). ADR-011" >&2
  echo "      condition 2's remedy does not hold on this KServe version: canary-routed" >&2
  echo "      traffic would 404 on the model name. Do not proceed to a weight." >&2
  exit 2
fi

echo
echo "== [3/6] wait for the ROUTE (not the pod — F-037) =="
# The model name is the champion's, so mlserver's readiness path is too. That is
# itself the first half of condition 2's proof, and it is why this loop asks for
# `/v2/models/nyc-taxi-eta/ready` on the CANARY's host.
isvc_wait_route "$ROUTE/v2/models/$CHAMPION_NAME/ready" "$CANARY_HOST" 180 \
  "kubectl -n $SERVING_NS get ingress $CANARY_NAME"

echo
echo "== [4/6] ADR-011 condition 2, PROVED — both ways =="
# Positive: a real quote, in the champion's feature set, under the champion's
# model NAME, served by a different pod (gotcha #59 — assert on the artifact).
uv run python -m taxi_mlops.serving \
  --route "$ROUTE" --name "$CHAMPION_NAME" --host "$CANARY_HOST" \
  --features-version "$FEATURE_SET" --at "2019-07-04T09:15:00"
# Negative: the isvc's own name must NOT be served. Without this, a runtime that
# answered to every name would pass the positive half and prove nothing about
# which name canary traffic will carry.
NEG_STATUS="$(curl -s -o /dev/null -w '%{http_code}' -H "Host: $CANARY_HOST" \
  "$ROUTE/v2/models/$CANARY_NAME/ready")"
if [[ "$NEG_STATUS" != "404" ]]; then
  echo "FAIL: /v2/models/$CANARY_NAME/ready returned $NEG_STATUS, expected 404." >&2
  echo "      The canary answers to its own isvc name too, so the positive check" >&2
  echo "      above does not establish that the override is what carried it." >&2
  exit 2
fi
echo "ok  /v2/models/$CANARY_NAME/ready -> 404 — the override is what answers, not a catch-all"

echo
echo "== [5/6] the dedicated backend Service (ADR-011 condition 1) =="
"${KUBECTL[@]}" apply -f "$BACKEND_MANIFEST"
COMMITTED_SELECTOR="$(python3 -c '
import json, sys, yaml
print(json.dumps(yaml.safe_load(open(sys.argv[1]))["spec"]["selector"], sort_keys=True))
' "$BACKEND_MANIFEST")"
GENERATED_SELECTOR="$("${KUBECTL[@]}" -n "$SERVING_NS" get svc "$CANARY_NAME-predictor" \
  -o jsonpath='{.spec.selector}' | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin), sort_keys=True))')"
if [[ "$COMMITTED_SELECTOR" != "$GENERATED_SELECTOR" ]]; then
  echo "FAIL: the committed backend selector $COMMITTED_SELECTOR does not match the" >&2
  echo "      selector KServe generated for this canary, $GENERATED_SELECTOR." >&2
  echo "      A Service that selects nothing fails as a 503 blamed on the pod." >&2
  exit 2
fi
ENDPOINTS="$("${KUBECTL[@]}" -n "$SERVING_NS" get endpoints "$CANARY_BACKEND" \
  -o jsonpath='{.subsets[*].addresses[*].ip}')"
if [[ -z "$ENDPOINTS" ]]; then
  echo "FAIL: $CANARY_BACKEND has no endpoints — it selects no running pod." >&2
  exit 2
fi
echo "ok  $CANARY_BACKEND selector == KServe's own, endpoints: $ENDPOINTS"

echo
echo "== [6/6] the story-exit invariant: the champion is untouched =="
# No trailing why-line, and that is this caller's own text preserved rather than
# improved: the other three cite a law here and this one never did. Naming the
# asymmetry instead of quietly resolving it — writing a citation for a script
# that had none would be inventing an argument inside a deduplication.
ALIAS_AFTER="$(isvc_champion_version)"
isvc_assert_alias_unmoved "$ALIAS_BEFORE" "$ALIAS_AFTER" "CANARY deploy"
echo "ok  @champion is version $ALIAS_AFTER — unmoved"
uv run python -m taxi_mlops.serving --route "$ROUTE" --name "$CHAMPION_NAME" \
  --at "2019-07-04T09:15:00"
echo "ok  the champion still answers on its own host — no traffic has moved"
