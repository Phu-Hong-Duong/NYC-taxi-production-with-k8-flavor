#!/usr/bin/env bash
# stage_pipeline_data.sh — put the DVC-pinned data trees on the PVC that Flyte
# task pods mount, behind `make stage-data` (M4-S4).
#
# WHY THIS EXISTS AT ALL: kind nodes cannot see the host filesystem (an
# `extraMounts` entry is a kind-config edit, and a kind-config edit means a
# cluster rebuild, which the M4 statefulness law forbids). So the only way host
# bytes reach a pod is over the API server, which is what this does.
#
# THE TRANSFER IS `tar | kubectl exec -i`, the M1-S4 shape. Not `kubectl cp`:
# `cp` shells out to tar anyway, has no progress, and silently truncates paths
# longer than 100 chars on some builds. Streaming tar means one process, one
# pipe, and the same measured path M1-S4 used to move 104 MB into Postgres.
#
# IDEMPOTENCE, and what it is NOT. A re-run re-streams the trees and lets tar
# overwrite: the source is byte-identical by construction (M1-S1's ingest is
# byte-reproducible and both trees are DVC-pinned), so a second run converges to
# the same bytes rather than appending. What this script does NOT do is DELETE —
# a file on the volume that is not in the source survives. That is deliberate for
# the same reason `postgres_databases.sh` never drops: destroying is
# `make destroy`'s job, and a stager that prunes could eat an ingest stage's
# output the moment somebody staged from a partial tree. `RESTAGE=1` forces the
# re-stream when the size check would otherwise skip it.
#
# NO SECRET IS INVOLVED and nothing here writes to the cluster except the volume.
#
# Usage: scripts/stage_pipeline_data.sh          (via `make stage-data`)
#        RESTAGE=1 scripts/stage_pipeline_data.sh    (re-stream even if present)
#        DRY_RUN=1 scripts/stage_pipeline_data.sh    (measure, transfer nothing)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")
NAMESPACE="${FLYTE_NAMESPACE:-flyte}"
STAGER="${STAGER_POD:-taxi-data-stager}"
DRY_RUN="${DRY_RUN:-0}"
RESTAGE="${RESTAGE:-0}"

# The four trees, and they are the four the PodTemplate mounts by subPath.
# TWINS with infra/manifests/flyte-task-podtemplate.yaml — a tree staged here and
# not mounted there is invisible to every task, and a tree mounted there and not
# staged here is an empty directory that reads as "no data for that month".
# tests/unit/test_platform_scripts.py fails if the two lists drift.
#
# `predictions` joined at M4-S5, for the marts tail task: the `error_segments` mart
# sources the analyst layer's `predictions` view. It is the one tree here that is
# NOT DVC-pinned (M2-S4 decided that deliberately — model output regenerable from
# pinned inputs plus a registry version, and a pin that goes stale every time the
# champion moves looks like provenance without being any), so its provenance is
# `data/predictions/predictions.json` and the registry, not a `.dvc` file. That
# also means it does not enter the pipeline's cache salt, which is honest: it
# cannot, because nothing pins it.
TREES=(raw processed rejected predictions)

echo "== stage pipeline data =="

for tree in "${TREES[@]}"; do
  if [[ ! -d "$REPO_ROOT/data/$tree" ]]; then
    echo "[stage-data] FAIL: $REPO_ROOT/data/$tree does not exist — run 'make data' first" >&2
    exit 1
  fi
done

host_bytes=$(du -sb "${TREES[@]/#/$REPO_ROOT/data/}" | awk '{s+=$1} END {print s}')
echo "[stage-data] source: $(numfmt --to=iec "$host_bytes") across ${TREES[*]}"

if [[ "$DRY_RUN" == "1" ]]; then
  echo "[stage-data] DRY_RUN — WOULD apply infra/manifests/flyte-task-data-pvc.yaml"
  echo "[stage-data] DRY_RUN — WOULD start pod $STAGER and stream ${TREES[*]} into it"
  echo "[stage-data] nothing was applied, nothing was transferred"
  exit 0
fi

# The PVC first: `WaitForFirstConsumer` means it stays Pending until a pod wants
# it, so creating it here and mounting it below is the same step in two halves.
"${KUBECTL[@]}" apply -f "$REPO_ROOT/infra/manifests/flyte-task-data-pvc.yaml"

# The stager is the volume's FIRST consumer, which is what binds the PV to a
# node — every task pod then follows it there by the PV's own nodeAffinity. It
# holds nothing else: no project image (the data has to arrive before an image
# that would read it is relevant), no credentials, and it sleeps rather than
# serving anything.
if ! "${KUBECTL[@]}" -n "$NAMESPACE" get pod "$STAGER" >/dev/null 2>&1; then
  "${KUBECTL[@]}" apply -f "$REPO_ROOT/infra/manifests/flyte-data-stager.yaml"
fi
"${KUBECTL[@]}" -n "$NAMESPACE" wait --for=condition=Ready "pod/$STAGER" --timeout=300s

staged_bytes=$("${KUBECTL[@]}" -n "$NAMESPACE" exec "$STAGER" -- \
  sh -c 'du -sb /stage 2>/dev/null | cut -f1' || echo 0)
echo "[stage-data] volume currently holds $(numfmt --to=iec "${staged_bytes:-0}")"

# The skip is on SIZE, not on existence, and the difference is the point: a
# half-streamed tree exists. It is still only a cheap check — `RESTAGE=1` is the
# honest way to force the transfer, and the byte-level proof that the staged
# trees match the host is the per-file count check at the end, which always runs.
if [[ "$RESTAGE" != "1" && "${staged_bytes:-0}" -ge "$host_bytes" ]]; then
  echo "[stage-data] already staged (>= source size) — skipping the transfer (RESTAGE=1 forces it)"
else
  for tree in "${TREES[@]}"; do
    echo "[stage-data] streaming data/$tree ..."
    tar -C "$REPO_ROOT/data" -cf - "$tree" \
      | "${KUBECTL[@]}" -n "$NAMESPACE" exec -i "$STAGER" -- tar -C /stage -xf -
  done
fi

# The check that makes this a stage and not a hope: every tree's FILE COUNT on
# the volume must equal the host's. Counting files rather than comparing sizes
# catches the failure a size check cannot — a tree that arrived truncated at one
# file, which is exactly what a killed stream leaves behind.
fail=0
for tree in "${TREES[@]}"; do
  host_n=$(find "$REPO_ROOT/data/$tree" -type f | wc -l)
  pod_n=$("${KUBECTL[@]}" -n "$NAMESPACE" exec "$STAGER" -- \
          sh -c "find /stage/$tree -type f 2>/dev/null | wc -l" | tr -d '[:space:]')
  if [[ "$host_n" == "$pod_n" ]]; then
    echo "[stage-data] ok  $tree: $pod_n file(s) on the volume == $host_n on the host"
  else
    echo "[stage-data] FAIL $tree: $pod_n file(s) on the volume != $host_n on the host" >&2
    fail=1
  fi
done
[[ "$fail" == "0" ]] || exit 1

# The stager is deleted: a pod holding an RWO volume open for no reason is a pod
# that will one day be the reason a task cannot schedule. The PVC and its data
# survive it — that is what a PVC is.
"${KUBECTL[@]}" -n "$NAMESPACE" delete pod "$STAGER" --wait=false >/dev/null
echo "[stage-data] ok  stager removed; the volume and its data remain"
echo "[stage-data] done."
