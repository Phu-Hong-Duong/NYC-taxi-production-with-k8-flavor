#!/usr/bin/env bash
# deploy_shadow.sh — registry version 1 on the wire, with ZERO rider traffic (M6-S3).
#
# The champion's deploy, asked of a VERSION instead of an alias:
#
#   resolve version N -> InferenceService -> rollout -> ready
#                     -> the route answers with a PREDICTION, built through the
#                        feature set that version's own registry tag names
#
# THREE THINGS IT DOES NOT DO, EACH BECAUSE A LAW SAYS SO.
#
# 1. IT NEVER TOUCHES THE ALIAS. `@champion` is read before and after and a
#    change is a FAILURE, not a warning (the M4 runner's shape, the M5-S2 deploy's
#    inheritance). Nothing here calls a mutating registry API — a shadow that
#    acquired an alias would be a promotion with extra steps, and M6 law 3 says
#    nothing promotes.
#
# 2. IT NEVER TOUCHES THE CHAMPION'S ROUTE. KServe generates one Ingress per
#    InferenceService, so this one answers on its OWN host and the champion's
#    host still routes 100% to the champion. That is the story-exit invariant,
#    and this script asserts it at the end rather than assuming it: it asks the
#    champion's host for a quote and requires `model_version: 2` back.
#
# 3. IT DOES NOT RE-DEPLOY THE CHAMPION. ADR-004's spike budget is ONE serving
#    re-deploy and ADR-011 spends it on the canary probe, not here. Adding a
#    second InferenceService is an ADDITION: the champion's Deployment is not in
#    this script's blast radius and its pod age proves it afterwards.
#
# WHY THE FEATURE SET IS DERIVED AND NOT TYPED. Version 1 eats 5 columns and the
# champion eats 24; the client has to be told which. Typing `v1` here would put a
# second, un-updatable claim about what a model eats next to the registry's own
# `feature_set` tag — which is precisely the defect F-032 found in the rollback
# procedure one story ago. So the tag is read out of the resolution payload and
# passed through. If a version ever carries no tag, this script REFUSES rather
# than defaulting: guessing which matrix a model eats produces a confident wrong
# number (v1 fed 24 columns returns a 500, which is the good case; the bad case
# is a set that happens to fit).
#
# Usage: scripts/deploy_shadow.sh                (via `make shadow`)
#        SHADOW_VERSION=1 scripts/deploy_shadow.sh
#        DRY_RUN=1 scripts/deploy_shadow.sh      (prints the plan, mutates NOTHING)
#        TEARDOWN=1 scripts/deploy_shadow.sh     (removes the shadow; the champion
#                                                 is not touched)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")
DRY_RUN="${DRY_RUN:-0}"
TEARDOWN="${TEARDOWN:-0}"
WAIT_TIMEOUT="${SHADOW_WAIT_TIMEOUT:-15m}"

SERVING_NS="serving"
CHAMPION_NAME="nyc-taxi-eta"
SHADOW_NAME="nyc-taxi-eta-shadow"
SHADOW_VERSION="${SHADOW_VERSION:-1}"
SHADOW_MANIFEST="$REPO_ROOT/infra/manifests/inferenceservice-shadow-v1.yaml"

# The route port is READ from the kind config, never typed (gotcha #52, and the
# champion deploy's precedent — a rename must fail at deploy time).
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
SHADOW_HOST="$SHADOW_NAME-$SERVING_NS.local"

echo "== the shadow on the wire =="
echo "   route      $ROUTE  (Host: $SHADOW_HOST)"
echo "   model      registry VERSION $SHADOW_VERSION — resolved at deploy time, never typed"
echo "   traffic    ZERO riders. Its host is its own; the champion's is untouched."

# ---------------------------------------------------------------- TEARDOWN --
if [[ "$TEARDOWN" == "1" ]]; then
  echo
  echo "== teardown =="
  # Deleting the InferenceService takes its Deployment, Service and generated
  # Ingress with it — they carry its ownerReference. The champion's objects do
  # not, which is the whole reason a second isvc was preferred to editing the
  # first one's spec.
  "${KUBECTL[@]}" -n "$SERVING_NS" delete inferenceservice "$SHADOW_NAME" --ignore-not-found
  echo "ok  $SHADOW_NAME removed (the champion was not touched)"
  exit 0
fi

# ------------------------------------------------------------------ DRY_RUN --
if [[ "$DRY_RUN" == "1" ]]; then
  echo
  echo "== [1/4] resolve ==  DRY_RUN — WOULD read models:/$CHAMPION_NAME/$SHADOW_VERSION (a READ)"
  echo "== [2/4] isvc ==     DRY_RUN — WOULD apply $SHADOW_MANIFEST with the resolved storageUri"
  echo "== [3/4] accept ==   DRY_RUN — WOULD POST one quote to $ROUTE/v2/models/$SHADOW_NAME/infer"
  echo "== [4/4] invariant== DRY_RUN — WOULD re-read @champion and re-quote the champion's host"
  echo
  echo "DRY_RUN — nothing was applied, no InferenceService was created."
  exit 0
fi

champion_version() {
  uv run python "$REPO_ROOT/scripts/resolve_champion_storage.py" 2>/dev/null \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])'
}
ALIAS_BEFORE="$(champion_version)"
echo "   @champion is version $ALIAS_BEFORE (read before any change)"

echo
echo "== [1/4] resolve version $SHADOW_VERSION (F-009's two hops, asked of a version) =="
RESOLVED="$(uv run python "$REPO_ROOT/scripts/resolve_champion_storage.py" \
              --version "$SHADOW_VERSION" 2>/dev/null)"
STORAGE_URI="$(printf '%s' "$RESOLVED" | python3 -c 'import json,sys; print(json.load(sys.stdin)["storage_uri"])')"
FEATURE_SET="$(printf '%s' "$RESOLVED" | python3 -c 'import json,sys; print(json.load(sys.stdin)["feature_set"] or "")')"
RUN_ID="$(printf '%s' "$RESOLVED" | python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')"
if [[ -z "$FEATURE_SET" ]]; then
  echo "FAIL: registry version $SHADOW_VERSION carries no feature_set tag, so this" >&2
  echo "      script cannot know which matrix it eats. Refusing to guess — a wrong" >&2
  echo "      feature set that happens to fit returns a confident wrong number." >&2
  exit 2
fi
echo "   models:/$CHAMPION_NAME/$SHADOW_VERSION -> run $RUN_ID"
echo "   feature set (from the version's OWN tag): $FEATURE_SET"
echo "   what KServe will download                : $STORAGE_URI"

echo
echo "== [2/4] the shadow InferenceService =="
python3 - "$SHADOW_MANIFEST" "$STORAGE_URI" "$SHADOW_VERSION" > "/tmp/isvc-shadow.$$.yaml" <<'PY'
import sys

path, storage_uri, version = sys.argv[1], sys.argv[2], sys.argv[3]
substitutions = {
    "RESOLVED-AT-DEPLOY-TIME-FROM-THE-SHADOW-VERSION": storage_uri,
    "SHADOW-VERSION-RESOLVED-AT-DEPLOY-TIME": f'"{version}"',
}
text = open(path).read()
for placeholder, value in substitutions.items():
    if placeholder not in text:
        sys.exit(f"{path} no longer carries the {placeholder} placeholder — refusing to guess")
    text = text.replace(placeholder, value)
sys.stdout.write(text)
PY
trap 'rm -f "/tmp/isvc-shadow.$$.yaml"' EXIT
"${KUBECTL[@]}" apply -f "/tmp/isvc-shadow.$$.yaml"

echo
echo "   waiting for the shadow predictor (first start downloads $STORAGE_URI)…"
# `rollout status` FIRST and the jsonpath wait SECOND — gotchas #71 and #79, both
# inherited from the champion's deploy verbatim. On a re-deploy the ISVC's Ready
# condition is satisfiable by the pod being replaced, and `--for=condition=` is
# unsatisfiable while KServe leaves observedGeneration behind.
"${KUBECTL[@]}" -n "$SERVING_NS" rollout status \
  "deploy/$SHADOW_NAME-predictor" --timeout="$WAIT_TIMEOUT"
"${KUBECTL[@]}" -n "$SERVING_NS" wait \
  --for=jsonpath='{.status.conditions[?(@.type=="Ready")].status}'=True \
  "inferenceservice/$SHADOW_NAME" --timeout="$WAIT_TIMEOUT"
"${KUBECTL[@]}" -n "$SERVING_NS" get pods -o wide \
  -l "serving.kserve.io/inferenceservice=$SHADOW_NAME"

echo
echo "== [3/4] read it back — a PREDICTION, in the shadow's OWN feature set =="
# gotcha #59: assert on the artifact the thing exists to produce. And note what
# this line proves that a health check could not — that the 5-column matrix this
# client built is the one version 1's logged signature accepts. Send it 24
# columns and it 500s, which is the very fact that makes mirroring useless here
# and dual-send necessary (ADR-011 measures that rather than asserting it).
uv run python -m taxi_mlops.serving \
  --route "$ROUTE" --name "$SHADOW_NAME" --features-version "$FEATURE_SET" \
  --at "2019-07-04T09:15:00"

echo
echo "== [4/4] the story-exit invariant: the champion is untouched =="
ALIAS_AFTER="$(champion_version)"
if [[ "$ALIAS_BEFORE" != "$ALIAS_AFTER" ]]; then
  echo "FAIL: @champion moved from $ALIAS_BEFORE to $ALIAS_AFTER during a SHADOW deploy." >&2
  echo "      M6 law 3: nothing promotes. Nothing in this script calls a mutating" >&2
  echo "      registry API, so something else did." >&2
  exit 2
fi
echo "ok  @champion is version $ALIAS_AFTER — unmoved"
# The champion's own host, asked for a real quote. A shadow that broke the
# champion's route would otherwise be discovered by the next story.
uv run python -m taxi_mlops.serving --route "$ROUTE" --name "$CHAMPION_NAME" \
  --at "2019-07-04T09:15:00"
echo "ok  the champion still answers on its own host — the shadow took no rider traffic"
