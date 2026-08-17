#!/usr/bin/env bash
# predictions_redteam.sh — prove `make predictions` REFUSES to publish rows whose
# floor was fitted over a window the champion's gate never saw (F-012, M3-S1).
#
# The failure this drills is the quietest one in the program. `score.score()`
# re-fits the honest floor and writes `floor_predicted_minutes` on all 12,140,456
# published rows; `marts.error_segments.kpi_13_margin_vs_floor_pct`, the whole §1
# decomposition of the error memo and every card on the error-segment board are
# comparisons against that column. Until M3-S1 only the CHALLENGER half of the
# gate's argument was checked against the registry. So: re-fit the floor over
# different months, the champion still re-scores at 3.2608, the write proceeds,
# every KPI-13 in the warehouse shifts — and `make verify-m2` stays GREEN 49/49.
#
# The drill: fit the floor on ONE train month instead of six and try to publish.
#   expected: exit 2, the refusal naming BOTH numbers, and data/predictions/
#   byte-identical afterwards — checked by sha256, not by an mtime and not by
#   trusting the exit code.
#
# It is the twin of scripts/train_redteam.sh and inverts the same way: here the
# refusal IS the result, so a successful publish is this script's failure.
#
# Usage: bash scripts/predictions_redteam.sh   (via `make predictions-redteam`)
# Runtime: ~4 min. It scores the real champion over the real held-out months,
# because a refusal demonstrated on a toy is a refusal nobody has seen.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

printf '\n\033[1m[red team] F-012: the floor half of the gate, checked as a refusal to write\033[0m\n\n'

fingerprint() {
  uv run python - <<'PY'
import hashlib
import pathlib

root = pathlib.Path("data/predictions")
for path in sorted(root.rglob("*")):
    if path.is_file():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"{digest}  {path.relative_to(root)}")
PY
}

BEFORE="$(fingerprint)"
if [[ -z "$BEFORE" ]]; then
  printf '\033[31m[red team] data/predictions/ is empty — run `make predictions` first; there is\n'
  printf '           nothing here for a refusal to protect.\033[0m\n' >&2
  exit 1
fi
printf '%s\n' "$BEFORE" | sed 's/^/  before  /'

echo
echo "[red team] fitting the published floor on 2019-01 alone (the champion's gate used six months)"
echo
uv run python -m taxi_mlops.training predict --floor-train-months 2019-01
STATUS=$?
echo
echo "[red team] the command exited $STATUS"

AFTER="$(fingerprint)"
echo
printf '%s\n' "$AFTER" | sed 's/^/  after   /'
echo

FAILED=0
if [[ "$STATUS" -eq 0 ]]; then
  printf '\033[31m  FAIL the write SUCCEEDED — the floor half of the gate is unchecked again\033[0m\n' >&2
  FAILED=1
elif [[ "$STATUS" -ne 2 ]]; then
  printf '\033[31m  FAIL exit %d is neither 0 nor the refusal'"'"'s 2 — the run died before the check,\n' "$STATUS" >&2
  printf '       which makes this drill inconclusive rather than passed\033[0m\n' >&2
  FAILED=1
else
  printf '  \033[32mok  \033[0m the write was REFUSED (exit 2), not warned about\n'
fi

if [[ "$BEFORE" != "$AFTER" ]]; then
  printf '\033[31m  FAIL data/predictions/ CHANGED during a refused run — the refusal came too late\033[0m\n' >&2
  FAILED=1
else
  printf '  \033[32mok  \033[0m every published file is byte-identical (sha256) — nothing was rewritten\n'
fi

echo
if [[ "$FAILED" -ne 0 ]]; then
  printf '\033[31m[red team] FAILED.\033[0m\n' >&2
  exit 1
fi
printf '\033[32m[red team] GREEN — a floor fitted on the wrong window cannot reach the warehouse.\033[0m\n'
exit 0
