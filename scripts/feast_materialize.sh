#!/usr/bin/env bash
# feast_materialize.sh — fill the ONLINE store from the offline parquet. (M8-S4)
#
# This is the one command in the program that crosses the wall in the WRITE
# direction, and it crosses two boundaries at once: the quarantine (Feast runs
# under `.venv-feast`, pandas 2.3.3, never under this project's interpreter — M8
# law 4) and the cluster (Redis has no hostPort, so the host reaches it through
# an ephemeral `kubectl port-forward` on 6380 — ADR-012 and the manifest header).
#
# WHAT MATERIALIZATION ACTUALLY MEANS HERE, because it decides how M8-S4's parity
# table is built. `feast materialize START END` writes, for every entity key, the
# LATEST source row whose `event_timestamp` falls in the window. The online store
# holds one value per key and no history: it is structurally incapable of the
# point-in-time join M8-S3 measured. For the two static views that is a
# distinction without a difference (one row per key, ever). For the two
# time-varying views it means the online store serves the FULL window — the
# 2019-07-01 stamp — to every request, which is precisely the "naive" column
# `docs/feast_pit_m8.md` §4 defines. So the offline half of the online/offline
# parity must be retrieved AT AN INSTANT AFTER THE LAST WINDOW CLOSED; comparing
# an online answer against a per-row point-in-time answer would report the store
# working correctly as a mismatch (gotcha #50).
#
# THE WINDOW IS DERIVED, NEVER TYPED. The end instant comes from the maximum
# `event_timestamp` across the published parquet — the same rule the row set and
# the source stamps already follow. A typed `2019-07-01` would silently stop
# materializing the day `make feast-sources` gains a seventh window.
#
#   scripts/feast_materialize.sh              apply, forward, materialize, record
#   scripts/feast_materialize.sh --dry-run    print the derived window, write NOTHING
#
# It touches no registry, no alias, no data tree, and no settled byte: its only
# mutation is the content of a store whose whole state class is REGENERABLE.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")
VENV_PY="$REPO_ROOT/.venv-feast/bin/python"
REPO_DIR="infra/feast/feature_repo"
LOCAL_PORT="${FEAST_REDIS_LOCAL_PORT:-6380}"
NAMESPACE="feast"
RECORD_DIR="automation/runs/m8-online"
RECORD="$RECORD_DIR/materialize.json"

DRY_RUN=0
case "${1:-}" in
  --dry-run) DRY_RUN=1 ;;
  "") ;;
  *) echo "unknown argument: $1" >&2; exit 2 ;;
esac

[[ -x "$VENV_PY" ]] || { echo "[materialize] the quarantine is missing — run: make feast-quarantine" >&2; exit 2; }

# --- the window, derived from the published sources ---------------------------
read -r START END < <(uv run python scripts/feast_source_window.py)
echo "[materialize] window (DERIVED from data/feast/*.parquet, never typed):"
echo "[materialize]   start $START   end $END"

if [[ "$DRY_RUN" == "1" ]]; then
  echo "[materialize] --dry-run — nothing was forwarded, nothing was written"
  exit 0
fi

# --- the forward --------------------------------------------------------------
FWD_LOG="$(mktemp)"
"${KUBECTL[@]}" -n "$NAMESPACE" port-forward svc/redis "${LOCAL_PORT}:6379" >"$FWD_LOG" 2>&1 &
FWD_PID=$!
cleanup() {
  kill "$FWD_PID" 2>/dev/null || true
  wait "$FWD_PID" 2>/dev/null || true
  rm -f "$FWD_LOG"
}
trap cleanup EXIT

for _ in $(seq 1 40); do
  grep -q "Forwarding from" "$FWD_LOG" && break
  sleep 0.25
done
grep -q "Forwarding from" "$FWD_LOG" || {
  echo "[materialize] FAIL — the port-forward never came up:" >&2; cat "$FWD_LOG" >&2; exit 1; }
echo "[materialize] forward: localhost:${LOCAL_PORT} -> svc/redis:6379 (ephemeral; pid $FWD_PID)"

export FEAST_REDIS_CONNECTION="localhost:${LOCAL_PORT}"
echo "[materialize] FEAST_REDIS_CONNECTION=$FEAST_REDIS_CONNECTION"

# `apply` before `materialize`, always: the repo config now names a different
# online store than the registry was last applied against, and a materialization
# into a store the registry does not know about is the kind of half-configured
# success that reads as data loss later.
echo "[materialize] [1/3] feast apply (the registry must know which store it is filling)"
( cd "$REPO_DIR" && FEAST_REDIS_CONNECTION="$FEAST_REDIS_CONNECTION" \
    uv run --no-project --python "$VENV_PY" feast apply )

echo "[materialize] [2/3] feast materialize"
SECONDS=0
( cd "$REPO_DIR" && FEAST_REDIS_CONNECTION="$FEAST_REDIS_CONNECTION" \
    uv run --no-project --python "$VENV_PY" feast materialize "$START" "$END" )
ELAPSED=$SECONDS
echo "[materialize] materialize finished in ${ELAPSED}s"

# --- read the result back off the SERVER, never off the command that wrote it --
echo "[materialize] [3/3] reading the store back (the deploy-scripts idiom)"
POD="$("${KUBECTL[@]}" -n "$NAMESPACE" get pod -l app=redis -o jsonpath='{.items[0].metadata.name}')"
KEYS="$("${KUBECTL[@]}" -n "$NAMESPACE" exec "$POD" -- redis-cli DBSIZE)"
USED="$("${KUBECTL[@]}" -n "$NAMESPACE" exec "$POD" -- redis-cli INFO memory | tr -d '\r' | awk -F: '/^used_memory_human:/{print $2}')"
MAXMEM="$("${KUBECTL[@]}" -n "$NAMESPACE" exec "$POD" -- redis-cli CONFIG GET maxmemory | tail -1)"
echo "[materialize]   dbsize=$KEYS  used_memory=$USED  maxmemory=$MAXMEM"
if [[ "$KEYS" -eq 0 ]]; then
  echo "[materialize] FAIL — the store is EMPTY after a materialization that reported success." >&2
  echo "[materialize]        An empty online store answers every lookup with null, which is" >&2
  echo "[materialize]        indistinguishable from a feature that has no value (F-050's shape)." >&2
  exit 1
fi

mkdir -p "$RECORD_DIR"
cat > "$RECORD" <<JSON
{
  "story": "M8-S4",
  "recorded_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "window": {"start": "$START", "end": "$END", "derived_from": "max/min event_timestamp across data/feast/*.parquet"},
  "elapsed_seconds": $ELAPSED,
  "store": {"dbsize": $KEYS, "used_memory_human": "$USED", "maxmemory_bytes": $MAXMEM, "pod": "$POD"},
  "connection": "$FEAST_REDIS_CONNECTION (ephemeral port-forward; in-cluster readers use redis.feast.svc.cluster.local:6379)",
  "semantics": "LATEST value per entity key in [start, end) — no history. The time-varying views therefore serve the FULL window to every request; see the script header and docs/feast_online_m8.md 3."
}
JSON
echo "[materialize] record: $RECORD"
echo "[materialize] DONE"
