#!/usr/bin/env bash
# isvc_deploy.sh — the deploy skeleton every serving script on this cluster
# shares. SOURCE it.
#
# Consolidated at CU-S5 out of five copies of the route-port heredoc, four
# copies of the alias no-move guard, four copies of the two readiness waits and
# three copies of the route wait. As at CU-S3, the bodies were fingerprinted
# BEFORE anything moved, and the fingerprint changed the design: four of the
# five heredocs are byte-identical and the fifth (deploy_transformer.sh) had
# drifted to a cwd-relative config path and a shorter refusal message. The
# merged version keeps the STRICTER behaviour of every cluster it replaces —
# that is the rule this repo consolidates by, and each instance is named below.
#
# WHAT LIVES HERE — the mechanism, and only the mechanism:
#   * isvc_route_port          the kind-config read (gotcha #52: derive, never type)
#   * isvc_champion_version    the alias READ (a read; nothing here mutates)
#   * isvc_assert_alias_unmoved  before != after -> exit 2
#   * isvc_wait_ready          rollout status FIRST, then the isvc-level wait
#   * isvc_wait_route          the third leg: ask the ROUTE (F-037)
#
# WHAT DELIBERATELY DOES NOT LIVE HERE, and must not move here later:
#   * EVERY ACCEPT CHECK. `make serve` asks for a prediction, the canary asks
#     ADR-011 condition 2 both ways, the transformer asks for a RAW quote and
#     reads `X-Taxi-Lookups` off the answer. Those are the program's arguments
#     (gotcha #59) and not one of them is a copy of another. A shared accept
#     check would turn four witnesses into one.
#   * THE ALIAS GUARD'S ARGUMENT. The mechanism is shared; the sentence is not.
#     `deploy_champion.sh` cites M5 kickoff law 2 and `deploy_shadow.sh` cites
#     M6 law 3, because those are different laws about different deploys. The
#     citation is passed IN as trailing arguments and stays with its caller.
#   * DRY_RUN NARRATIONS. Each is a bespoke description of what that script
#     would do, and the audit's own do-not-consolidate row names them.
#   * THE MANIFEST RENDER AND ITS PLACEHOLDER REFUSAL. Every script templates a
#     different object.
#
# THE ONE ORDER THAT IS LOAD-BEARING, and it is why `isvc_wait_ready` exists at
# all: `rollout status` runs FIRST and the InferenceService-level wait SECOND.
#   * gotcha #71 — on a RE-deploy the isvc's Ready condition is satisfied by the
#     pod being REPLACED, so an isvc-first wait returns while the new pod is
#     `Init:0/1` and the accept check then interrogates the predecessor. Watched
#     happen at M5-S2, reporting `(unversioned)` when the version stamp was the
#     change under test. `rollout status` waits for the NEW ReplicaSet and is
#     the leg that cannot be satisfied by the thing you are replacing.
#   * F-036 / gotcha #79 — the second leg is `--for=jsonpath=` and NOT
#     `--for=condition=`. kubectl v1.36 ignores a resource's conditions while
#     `status.observedGeneration < metadata.generation`, and KServe v0.20.0
#     leaves observedGeneration behind on every re-deploy (observed live at
#     generation=3 / observedGeneration=2 with every condition True). The
#     condition form can therefore never be satisfied, on any re-deploy, no
#     matter how healthy the result — it times out and, under `set -e`, takes
#     the accept check with it. `tests/unit/test_script_libs.py` pins the ORDER
#     here rather than the flag, because the flag has already had to change once
#     and the per-file pin went red for a correct fix (gotcha #50).
#
# CONVENTION, the same one `verify_harness.sh` uses: this file computes no
# REPO_ROOT and builds no kubectl invocation. The caller defines `REPO_ROOT`,
# `KUBECTL` (an array, so `--context` is pinned once per script) and its own
# namespace, and sources this file with them already set. That is also what
# keeps every deploy runnable from any working directory.
#
# It is sourced, never executed: it defines and returns.

# --------------------------------------------------------------------------
# The route port — read from the kind config, never typed (gotcha #52).
# --------------------------------------------------------------------------
# kind publishes host ports at cluster-CREATE time only, so the declared route
# is a fact about `infra/kind/kind-config.yaml` and about nothing else. A typed
# 8081 stays correct until somebody edits that file, and then it is wrong in the
# direction that looks like a broken service.
#
# The path is REQUIRED and callers pass an absolute one. The copy in
# deploy_transformer.sh had drifted to the cwd-relative `infra/kind/
# kind-config.yaml`, which is correct only when the script is run from the repo
# root; every other copy anchored it at $REPO_ROOT. The strict form wins.
isvc_route_port() {
  local kind_config="${1:?isvc_route_port needs the path to the kind config}"
  python3 - "$kind_config" <<'PY'
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
}

# --------------------------------------------------------------------------
# The alias, read before and read after.
# --------------------------------------------------------------------------
# Every serving deploy in this program is alias-NEUTRAL, and a claim nobody
# checks is a sentence. So the version is read on both sides of the script's own
# mutations and a difference is a FAILURE with its own exit code — not a
# warning, because a pipeline cannot hear a warning.
#
# This is a READ. `resolve_champion_storage.py` is pinned as a reader by
# `tests/unit/test_deploy_champion.py`, and no function in this file names a
# mutating registry verb.
isvc_champion_version() {
  uv run python "$REPO_ROOT/scripts/resolve_champion_storage.py" 2>/dev/null \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])'
}

# isvc_assert_alias_unmoved <before> <after> <what-kind-of-deploy> [why-line...]
#
# The trailing arguments are the CALLER's argument for why this must not have
# happened — the law it cites, in its own words. They are printed to stderr
# under the failure. A shared sentence here would make four different laws look
# like one.
isvc_assert_alias_unmoved() {
  local before="$1" after="$2" what="$3"
  shift 3
  if [[ "$before" != "$after" ]]; then
    echo "FAIL: @champion moved from $before to $after during a $what." >&2
    local line
    for line in "$@"; do
      echo "      $line" >&2
    done
    exit 2
  fi
}

# --------------------------------------------------------------------------
# The two readiness waits, in the order that is the whole point.
# --------------------------------------------------------------------------
# isvc_wait_ready <namespace> <isvc-name> <timeout> [component...]
#
# Components default to `predictor`. deploy_transformer.sh passes `predictor
# transformer`, because an isvc with a transformer has TWO Deployments and
# waiting on one of them is gotcha #71 with the other half unwatched.
isvc_wait_ready() {
  local ns="$1" name="$2" timeout="$3"
  shift 3
  local components=("$@")
  # An `if` and not `[[ … ]] && components=(predictor)`: under the callers'
  # `set -euo pipefail` the short-circuit form leaves the list's status at 1
  # whenever components WERE supplied, which is a subtlety a reader of four
  # deploy scripts should not have to re-derive.
  if [[ ${#components[@]} -eq 0 ]]; then
    components=(predictor)
  fi

  local component
  for component in "${components[@]}"; do
    "${KUBECTL[@]}" -n "$ns" rollout status \
      "deploy/$name-$component" --timeout="$timeout"
  done
  "${KUBECTL[@]}" -n "$ns" wait \
    --for=jsonpath='{.status.conditions[?(@.type=="Ready")].status}'=True \
    "inferenceservice/$name" --timeout="$timeout"
  "${KUBECTL[@]}" -n "$ns" get pods -o wide \
    -l "serving.kserve.io/inferenceservice=$name"
}

# --------------------------------------------------------------------------
# The third leg — ASK THE ROUTE. F-037.
# --------------------------------------------------------------------------
# isvc_wait_route <url> <host-header> <timeout-seconds> <ingress-hint>
#
# Both waits above can pass while the accept check gets a bare nginx `404 Not
# Found`, and neither was wrong: `rollout status` is about the ReplicaSet and
# the isvc's `Ready` condition is about the PREDICTOR. KServe creates the
# Ingress as a separate object and ingress-nginx then has to observe it and
# reload — so on a FIRST deploy there is a window in which the service is
# genuinely ready and its route genuinely does not exist. Observed live at
# M6-S3: the Ingress object was six seconds old when the quote 404'd.
#
# This is gotcha #71's family with a different mechanism. #71 is "a wait the
# thing you are REPLACING can satisfy"; on a first deploy there is no
# predecessor. This is "a wait about a DIFFERENT OBJECT than the one the next
# step uses" — every condition being true about the pod says nothing about
# whether nginx can route to it. So readiness is asked of the instrument that
# answers the question the accept check is about to ask: the route itself,
# under the Host header the next step will send.
#
# IT FAILS ON TIMEOUT, and that is the strictest of the three copies it
# replaces. `deploy_shadow.sh` and `deploy_canary.sh` exited 1 with a hint;
# `deploy_transformer.sh` polled sixty times and then fell through SILENTLY into
# its accept check, so an unroutable transformer reported as a failed accept —
# the confusing failure F-060/gotcha #105 is about, one layer earlier. A wait
# that gives up quietly is not a wait.
isvc_wait_route() {
  local url="$1" host="$2" timeout="$3" hint="$4"
  local deadline=$(( SECONDS + timeout ))
  until curl -sf -o /dev/null -H "Host: $host" "$url"; do
    if (( SECONDS >= deadline )); then
      echo "FAIL: $host never became routable in ${timeout}s, though the workload is Ready." >&2
      echo "      The pod is fine; the Ingress is the suspect. Check:" >&2
      echo "        $hint" >&2
      exit 1
    fi
    sleep 2
  done
  echo "ok  $host answers $url"
}
