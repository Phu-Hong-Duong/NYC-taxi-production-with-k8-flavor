#!/usr/bin/env bash
# deploy_feast_store.sh — the Feast ONLINE store on the kind cluster. (M8-S4)
#
# It installs ONE thing and knows about nothing else: a single-container Redis in
# a new `feast` namespace, from `infra/manifests/redis.yaml` (that file's header
# argues the manifest-not-a-chart call, the missing hostPort, the volume and
# `noeviction`; ADR-012 records the decision and the state class).
#
# WHAT IT DELIBERATELY DOES NOT DO. It does not materialize — `make
# feast-materialize` is a separate command because writing features is a data
# operation with its own record, and a deploy that quietly filled the store would
# make "is the store fresh?" unanswerable from the deploy's own output. It does
# not read `.env`, does not know the registry exists, and never reads or moves
# `@champion` (M8 law 3, the `deploy_serving.sh` precedent — a test asserts it
# cannot name the alias in code).
#
# THE ACCEPT CHECK IS AN ANSWER FROM THE SERVER, NEVER A LIST OF READY OBJECTS
# (gotcha #59, and #70's correction of it — ask the thing its own question). A
# Deployment reporting Available says nothing about whether Redis is willing to
# accept a write; `redis-cli PING` -> `PONG` plus a real SET/GET/DEL round trip
# on a scratch key is what the materializer is actually going to need, so that is
# what is asked. The scratch key is deleted by the same command that wrote it.
#
#   scripts/deploy_feast_store.sh              apply, wait, accept
#   DRY_RUN=1 scripts/deploy_feast_store.sh    print the plan, mutate NOTHING
#   TEARDOWN=1 scripts/deploy_feast_store.sh   delete the namespace and its PVC
#
# TEARDOWN takes the PVC with it and therefore the materialized features. That is
# safe BECAUSE of ADR-012's state class — every byte is regenerable by one
# command — and it is exactly why the teardown prints that command rather than
# asking for confirmation it cannot get in an unattended chain.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")
DRY_RUN="${DRY_RUN:-0}"
TEARDOWN="${TEARDOWN:-0}"
NAMESPACE="feast"
MANIFEST="infra/manifests/redis.yaml"
WAIT_TIMEOUT="${FEAST_STORE_WAIT_TIMEOUT:-5m}"
RECORD_DIR="automation/runs/m8-online"
RECORD="$RECORD_DIR/store.json"

if [[ "$TEARDOWN" == "1" ]]; then
  echo "[store] TEARDOWN — deleting namespace '$NAMESPACE' (this takes the PVC and the"
  echo "[store]            materialized features with it; rebuild with:"
  echo "[store]              make deploy-feast-store && make feast-materialize)"
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "[store] DRY_RUN=1 — nothing was deleted"
    exit 0
  fi
  "${KUBECTL[@]}" delete namespace "$NAMESPACE" --ignore-not-found --wait=true
  echo "[store] ok  namespace deleted"
  exit 0
fi

echo "[store] context      : $CONTEXT"
echo "[store] manifest     : $MANIFEST"
echo "[store] image (pinned by TAG AND DIGEST — the Metabase precedent):"
grep -m1 -o 'redis:[0-9].*' "$MANIFEST" | sed 's/^/[store]   /'

if [[ "$DRY_RUN" == "1" ]]; then
  echo "[store] DRY_RUN=1 — server-side dry run, nothing is applied"
  "${KUBECTL[@]}" apply -f "$MANIFEST" --dry-run=server
  echo "[store] DRY_RUN=1 — nothing was applied, nothing was waited on"
  exit 0
fi

echo "[store] [1/4] applying"
"${KUBECTL[@]}" apply -f "$MANIFEST"

echo "[store] [2/4] waiting for the rollout (timeout $WAIT_TIMEOUT)"
# rollout status FIRST, then the pod — gotcha #71: a readiness condition the
# object being REPLACED can satisfy is not a wait.
"${KUBECTL[@]}" -n "$NAMESPACE" rollout status deploy/redis --timeout="$WAIT_TIMEOUT"
"${KUBECTL[@]}" -n "$NAMESPACE" wait --for=condition=Ready pod -l app=redis --timeout="$WAIT_TIMEOUT"

POD="$("${KUBECTL[@]}" -n "$NAMESPACE" get pod -l app=redis -o jsonpath='{.items[0].metadata.name}')"
NODE="$("${KUBECTL[@]}" -n "$NAMESPACE" get pod "$POD" -o jsonpath='{.spec.nodeName}')"
UID_="$("${KUBECTL[@]}" -n "$NAMESPACE" get pod "$POD" -o jsonpath='{.metadata.uid}')"
AGE="$("${KUBECTL[@]}" -n "$NAMESPACE" get pod "$POD" -o jsonpath='{.status.startTime}')"
echo "[store]   pod $POD on $NODE (uid ${UID_}, started $AGE)"

echo "[store] [3/4] accept: asking the server, not the object list"
PONG="$("${KUBECTL[@]}" -n "$NAMESPACE" exec "$POD" -- redis-cli PING)"
[[ "$PONG" == "PONG" ]] || { echo "[store] FAIL — PING returned '$PONG'" >&2; exit 1; }
echo "[store]   ok  PING -> PONG"

SCRATCH="__deploy_accept_$$"
"${KUBECTL[@]}" -n "$NAMESPACE" exec "$POD" -- redis-cli SET "$SCRATCH" ok >/dev/null
GOT="$("${KUBECTL[@]}" -n "$NAMESPACE" exec "$POD" -- redis-cli GET "$SCRATCH")"
"${KUBECTL[@]}" -n "$NAMESPACE" exec "$POD" -- redis-cli DEL "$SCRATCH" >/dev/null
[[ "$GOT" == "ok" ]] || { echo "[store] FAIL — SET/GET round trip returned '$GOT'" >&2; exit 1; }
echo "[store]   ok  SET/GET/DEL round trip on a scratch key (a write, which is what a"
echo "[store]       materialization needs and a readiness probe does not prove)"

# The two settings whose failure mode is SILENT, read back off the running server
# rather than off the manifest that was submitted (the deploy_serving.sh idiom).
POLICY="$("${KUBECTL[@]}" -n "$NAMESPACE" exec "$POD" -- redis-cli CONFIG GET maxmemory-policy | tail -1)"
MAXMEM="$("${KUBECTL[@]}" -n "$NAMESPACE" exec "$POD" -- redis-cli CONFIG GET maxmemory | tail -1)"
KEYS="$("${KUBECTL[@]}" -n "$NAMESPACE" exec "$POD" -- redis-cli DBSIZE)"
echo "[store]   ok  maxmemory-policy=$POLICY maxmemory=$MAXMEM dbsize=$KEYS  (read off the SERVER)"
[[ "$POLICY" == "noeviction" ]] || {
  echo "[store] FAIL — eviction policy is '$POLICY'. An evicting online store drops the" >&2
  echo "[store]        key the next request asks for and answers null, which reads as a" >&2
  echo "[store]        missing feature and not as a full store." >&2
  exit 1; }

echo "[store] [4/4] recording"
mkdir -p "$RECORD_DIR"
IMAGE="$("${KUBECTL[@]}" -n "$NAMESPACE" get deploy redis -o jsonpath='{.spec.template.spec.containers[0].image}')"
PVC="$("${KUBECTL[@]}" -n "$NAMESPACE" get pvc redis-data -o jsonpath='{.status.phase} {.status.capacity.storage}')"
cat > "$RECORD" <<JSON
{
  "story": "M8-S4",
  "recorded_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "namespace": "$NAMESPACE",
  "image": "$IMAGE",
  "pod": "$POD",
  "pod_uid": "$UID_",
  "node": "$NODE",
  "pvc": "$PVC",
  "maxmemory_policy": "$POLICY",
  "maxmemory": "$MAXMEM",
  "dbsize_at_deploy": $KEYS,
  "accept": {"ping": "$PONG", "write_round_trip": "$GOT"},
  "host_reach": "kubectl port-forward -n feast svc/redis 6380:6379 (ephemeral; NO hostPort — see the manifest header)",
  "in_cluster_reach": "redis.feast.svc.cluster.local:6379",
  "state_class": "REGENERABLE — rebuild with make feast-materialize; ledger row yes, backup obligation no (ADR-012)"
}
JSON
echo "[store] record: $RECORD"
echo "[store] DONE — the store is up and EMPTY. Fill it: make feast-materialize"
