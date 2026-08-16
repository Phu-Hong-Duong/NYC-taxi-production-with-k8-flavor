#!/usr/bin/env bash
# `make data` — the whole data path, one command, idempotent (M1-S2, role:DE).
#
#   ingest   download -> contract -> clean -> split, counted rejections  (M1-S1)
#   duckdb   (re)build the analyst views and reconcile their row counts
#   dvc      re-hash data/raw + data/processed, then push to the remote
#
# ORDER MATTERS AND IS NOT ALPHABETICAL. DVC runs LAST because it pins what the
# earlier steps produced; running it first would push the previous run's bytes
# and every downstream proof would be one run stale.
#
# The DVC leg is skippable (SKIP_DVC=1) for one honest reason: `make data` is
# also the rebuild command in the byte-identity proof, and that proof must be
# able to rebuild WITHOUT the pin being refreshed underneath it — otherwise the
# thing being tested updates the thing it is tested against. Default is on.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "[data] 1/3 ingest"
uv run python -m taxi_mlops.data ingest

echo
echo "[data] 2/3 duckdb analyst layer"
uv run python -m taxi_mlops.data duckdb

echo
if [[ "${SKIP_DVC:-0}" == "1" ]]; then
  echo "[data] 3/3 dvc — SKIPPED (SKIP_DVC=1); the pin still describes the PREVIOUS run"
  exit 0
fi

if ! uv run dvc status >/dev/null 2>&1; then
  echo "[data] FAIL: no DVC repo here — run 'uv run dvc init' (see data/README.md)." >&2
  exit 1
fi

echo "[data] 3/3 dvc add + push"
# `dvc add` on an already-tracked dir re-hashes and rewrites the .dvc file only
# if the bytes moved; unchanged data makes this a no-op (that is the whole point
# of running it every time rather than remembering to).
uv run dvc add data/raw data/processed
uv run dvc push

echo
echo "[data] dvc status (workspace):"
uv run dvc status
echo "[data] dvc status (remote):"
uv run dvc status --cloud
echo "[data] GREEN — data ingested, views rebuilt, bytes pinned and pushed."
