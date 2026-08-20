#!/usr/bin/env bash
# `make data-scoring` — the whole SCORING data path, one command (M7-S1, role:DE).
#
#   ingest   the configs/data.yaml `scoring.months`, through the SAME contract,
#            the same one cast (gotcha #7), the same counted rejections and the
#            same sidecar discipline — into data/scoring/ and data/scoring_rejected/
#   duckdb   (re)build the analyst views and reconcile: the scoring views' rows
#            against the ingest reports that wrote them, AND the scoring sidecar
#            per (month, rule) against the per-rule counts
#   dvc      re-hash data/raw (which just gained the scoring months' raw files)
#            + the two new scoring trees, and push
#
# THIS IS A SEPARATE COMMAND FROM `make data` ON PURPOSE (M7 law 2: the 2019
# training data is settled and stays byte-identical). `make data` re-derives the
# settled months and re-pins data/processed + data/rejected; nothing in M7 has
# any business doing that, and a single command that did both would make every
# scoring ingest a rewrite of the trees the whole program's numbers rest on.
# The two scoring trees are their OWN dvc targets for the same reason
# data/rejected is not folded into data/processed: separate datasets that move
# independently do not share a hash.
#
# data/raw IS re-pinned here, and that is not a violation — it legitimately
# gained three files. The 2019 raw bytes inside it are unchanged, which the
# manifest proves file by file (`data/raw_manifest.json` is timestamp-free by
# design: a diff there means the DATA moved).
#
# SKIP_DVC=1 stops before the pin, for `make data`'s reason: a proof must never
# refresh the pin it is judged against (gotcha #33).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "[data-scoring] 1/3 ingest (configs/data.yaml scoring.months)"
uv run python -m taxi_mlops.data ingest --scoring "$@"

echo
echo "[data-scoring] 2/3 duckdb analyst layer (all five reconciliations)"
uv run python -m taxi_mlops.data duckdb

echo
if [[ "${SKIP_DVC:-0}" == "1" ]]; then
  echo "[data-scoring] 3/3 dvc — SKIPPED (SKIP_DVC=1); the pin still describes the PREVIOUS run"
  exit 0
fi

if ! uv run dvc status >/dev/null 2>&1; then
  echo "[data-scoring] FAIL: no DVC repo here — run 'uv run dvc init' (see data/README.md)." >&2
  exit 1
fi

echo "[data-scoring] 3/3 dvc add + push"
uv run dvc add data/raw data/scoring data/scoring_rejected
uv run dvc push

echo
echo "[data-scoring] the settled 2019 pins — these MUST read 'up to date' (M7 law 2):"
uv run dvc status data/processed.dvc data/rejected.dvc
echo "[data-scoring] GREEN — scoring months ingested, views rebuilt, bytes pinned and pushed."
