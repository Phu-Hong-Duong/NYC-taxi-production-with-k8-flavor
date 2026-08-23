#!/usr/bin/env bash
# M8-S4 leg 2 — the CHEAP PROBE that stands in front of an image build.
#
# The kickoff orders the transformer's three Feast shapes (i) -> (ii) -> (iii),
# and shape (i) is "Feast's feature server as its own quarantined pod, HTTP from
# the transformer". Building that pod costs a Dockerfile, a pinned base, a
# registry delivery mechanism and a `kind load` to three nodes — and every one of
# those is wasted if `feast serve` cannot answer an online lookup at all against
# this repo's config.
#
# So this asks the cheapest possible version of the question FIRST, on the HOST,
# inside the existing quarantine, against the real in-cluster Redis through the
# ephemeral 6380 forward `make feast-materialize` already uses: start the server,
# POST one `/get-online-features` for a real entity, print what comes back, stop.
# ~30 seconds against ~30 minutes. It is the `DRILL_STAGE=ingest` idiom (M4-S4)
# and gotcha #62's lesson: the defects a cheap probe finds are almost never about
# the expensive thing it is standing in front of.
#
# It writes NOTHING into the store (a read), deploys nothing, and touches no
# registry, no alias and no image.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VENV_FEAST="$REPO_ROOT/.venv-feast/bin/feast"
REPO="$REPO_ROOT/infra/feast/feature_repo"
PORT="${FEAST_SERVE_PORT:-6570}"
: "${FEAST_REDIS_CONNECTION:=localhost:6380}"
export FEAST_REDIS_CONNECTION

if [[ ! -x "$VENV_FEAST" ]]; then
  echo "[probe] FAIL: the quarantine is not built — run 'make feast-quarantine'" >&2
  exit 2
fi

echo "[probe] feast serve, quarantine only, store=$FEAST_REDIS_CONNECTION port=$PORT"
LOG="$REPO_ROOT/automation/runs/m8-transformer/serve-probe.log"
mkdir -p "$(dirname "$LOG")"

( cd "$REPO" && exec "$VENV_FEAST" serve --host 127.0.0.1 --port "$PORT" --no-access-log ) \
  >"$LOG" 2>&1 &
pid=$!
trap 'kill "$pid" 2>/dev/null || true' EXIT

code=000
for _ in $(seq 1 30); do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 \
    "http://127.0.0.1:${PORT}/health" || true)"
  [[ "$code" == "200" ]] && break
  sleep 1
done
echo "[probe] /health -> $code"
if [[ "$code" != "200" ]]; then
  echo "[probe] the server never came up; its log:" >&2
  tail -40 "$LOG" >&2
  exit 1
fi

echo "[probe] POST /get-online-features for zone 132 (JFK) — the champion's own lookup"
curl -s --max-time 20 -X POST "http://127.0.0.1:${PORT}/get-online-features" \
  -H 'Content-Type: application/json' \
  -d '{"features":["zone_static:centroid_lat","zone_static:centroid_lon","zone_static:is_airport"],
       "entities":{"zone_id":[132,264]}}' | head -c 2000
echo
echo "[probe] done — the server is stopped by the EXIT trap."
