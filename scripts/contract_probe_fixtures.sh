#!/usr/bin/env bash
# `make contract-probe-fixtures` — watch the contract REFUSE, three shapes (M7-S1).
#
# The 2025 leg of M7-S1 was a measurement and it came back VALIDATED: the real
# 2025-01 file passes the year-aware contract (the `Airport_fee -> airport_fee`
# alias fires, `cbd_congestion_fee` is required and present, the int32/int64
# spread is absorbed by THE cast). That is a SURPASS over the blueprint's
# premise — and it leaves the refusal side of the story unwatched, which is the
# half M7-S3 needs: a schema break must look NOTHING like a statistical one.
#
# So the refusal is demonstrated on structurally-wrong frames DERIVED FROM THE
# REAL FILE, one per shape TLC could actually produce:
#   drop-required     a field disappears
#   rename-required   a field moves to a new spelling
#   unknown-column    a field appears that no config knows
#
# Each must exit 1 (REFUSED), and each must write nothing. The exit code is the
# assertion: a refusal that exits 0 is a refusal a pipeline cannot hear.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

MONTH="${PROBE_MONTH:-2025-01}"
ROWS="${PROBE_ROWS:-200000}"
OUT_DIR="automation/runs/m7-s1"
fails=0

for fixture in drop-required rename-required unknown-column; do
  echo
  echo "=== fixture: ${fixture} (${MONTH}, first ${ROWS} rows of the REAL file) ==="
  uv run python scripts/contract_probe.py \
    --month "${MONTH}" --rows "${ROWS}" --fixture "${fixture}" \
    --out "${OUT_DIR}/contract_probe_fixture_${fixture}.json"
  code=$?
  if [[ "${code}" -eq 1 ]]; then
    echo "ok  exit ${code} — REFUSED, as a schema break must be"
  else
    echo "FAIL exit ${code} — expected 1 (REFUSED). A contract that admits this shape is not a contract." >&2
    fails=$((fails + 1))
  fi
done

# Nothing may have been written. Checked, not asserted in prose: the probe's
# whole claim is that measuring a month is not a way to acquire one.
echo
for tree in data/processed data/rejected data/scoring data/scoring_rejected; do
  if find "${tree}" -name "*${MONTH}*" -print -quit 2>/dev/null | grep -q .; then
    echo "FAIL ${tree}/ contains a ${MONTH} artifact — the probe wrote data" >&2
    fails=$((fails + 1))
  else
    echo "ok  ${tree}/ holds nothing for ${MONTH}"
  fi
done

echo
if [[ "${fails}" -eq 0 ]]; then
  echo "[fixtures] PASSED — 3 refusal shape(s) watched, exit 1 each, nothing written."
  exit 0
fi
echo "[fixtures] FAILED — ${fails} check(s)." >&2
exit 1
