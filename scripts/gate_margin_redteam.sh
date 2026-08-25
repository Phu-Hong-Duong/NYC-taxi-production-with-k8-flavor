#!/usr/bin/env bash
# gate_margin_redteam.sh — prove the incumbent margin cannot be quietly lowered.
#
# M9-S10 landed F-016 option (b): the incumbent KPI-09 condition carries a
# margin (`configs/train.yaml: gate.incumbent_min_improvement_pct`, sanctioned at
# 0.50% by the PO at AWAITING_PO 2026-08-24-4), and the three milestone gates
# replay every recorded verdict against the bar IN FORCE when it was taken.
#
# Era-awareness is the half that makes the tightening landable. It is also,
# BY ITSELF, a hole: if every historical verdict is judged against its own old
# bar, then lowering the live bar tomorrow breaks nothing, replays perfectly,
# and leaves nine green sub-checks saying the gate is fine. The monotonic check
# in `verify-m2` §2 is the half that does not move, and this drill is the only
# thing that proves it fires.
#
# WHAT IT BREAKS, and why this and not something else: **one number in
# `configs/train.yaml`**, `0.50 -> 0.10`. Not a deletion (that raises, loudly,
# and is already pinned by a unit test) and not a nonsense value — 0.10 is a
# plausible, well-formed, still-positive margin that a session could type while
# believing it was being careful. It still refuses the identity case, so it
# still satisfies F-068's arithmetic; what it does is spend the PO's letter
# without one. That is the edit this check exists for.
#
# The honest expectation is a SMALL blast radius, and both halves are asserted:
#   * the RED run NAMES the loosening, with both numbers, and
#   * the ERA-AWARE replays STILL PASS — a historical verdict is not affected by
#     the live bar, so a drill that turned the whole leg red would prove the
#     replays were reading the config instead of the era.
#
# Safety: the config is restored by an EXIT trap from a byte copy taken before
# the edit, and the restore is verified by sha256 rather than assumed. A clean
# run leaves a clean tree. It touches no model, no run, no registry state, no
# alias, and nothing on the cluster.
#
# Usage: scripts/gate_margin_redteam.sh   (via `make gate-margin-redteam`)
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

CONFIG="configs/train.yaml"
PLANTED="0.10"
BACKUP="$(mktemp)"
RESTORED=0
PROBLEMS=0

say() { printf '\n\033[1m[gate-margin-redteam] %s\033[0m\n' "$1"; }
ok()  { printf '  \033[32mok  \033[0m %s\n' "$1"; }
bad() { printf '  \033[31mFAIL\033[0m %s\n' "$1" >&2; PROBLEMS=$((PROBLEMS + 1)); }

restore() {
  [[ "$RESTORED" -eq 1 ]] && return 0
  if cp "$BACKUP" "$CONFIG"; then
    RESTORED=1
    local now before
    now="$(sha256sum "$CONFIG" | cut -d' ' -f1)"
    before="$(sha256sum "$BACKUP" | cut -d' ' -f1)"
    if [[ "$now" == "$before" ]]; then
      printf '  restored %s (sha256 %s…)\n' "$CONFIG" "${now:0:12}"
    else
      printf '\033[31m  RESTORE DID NOT MATCH — %s is not what it was.\033[0m\n' "$CONFIG" >&2
    fi
  else
    printf '\033[31m[gate-margin-redteam] COULD NOT RESTORE %s.\033[0m\n' "$CONFIG" >&2
    # The byte copy is named FIRST because it is right under every condition;
    # `git checkout --` is right only if the file was committed as this drill
    # found it, which a failing restore path may not assume.
    printf 'Copy it back by hand:  cp %s %s\n' "$BACKUP" "$CONFIG" >&2
    printf '  (or, if it was committed as found:  git checkout -- %s)\n' "$CONFIG" >&2
    return 0
  fi
  rm -f "$BACKUP"
}
trap restore EXIT

# ------------------------------------------------------ 0. snapshot the truth --
say "0. the config as it stands (restored to exactly this, whatever happens)"
if [[ ! -s "$CONFIG" ]]; then
  echo "$CONFIG is missing — there is no gate config to red-team." >&2
  exit 2
fi
cp "$CONFIG" "$BACKUP"
BEFORE_SHA="$(sha256sum "$CONFIG" | cut -d' ' -f1)"
BEFORE_MARGIN="$(uv run python -c "
from taxi_mlops.data.config import load_yaml
print(f\"{float(load_yaml('configs/train.yaml')['gate']['incumbent_min_improvement_pct']):.2f}\")
")"
printf '  %s  sha256 %s…  incumbent margin %s%%\n' "$CONFIG" "${BEFORE_SHA:0:12}" "$BEFORE_MARGIN"

# ------------------------------------------------------------ 1. break it -----
say "1. lower the incumbent margin ${BEFORE_MARGIN}% -> ${PLANTED}% — a plausible number, typed without a letter"
if ! PLANTED="$PLANTED" CONFIG="$CONFIG" uv run python - <<'PY'
import os
import re
from pathlib import Path

path = Path(os.environ["CONFIG"])
text = path.read_text(encoding="utf-8")
pattern = re.compile(r"^(  incumbent_min_improvement_pct: )([\d.]+)$", re.MULTILINE)
found = pattern.search(text)
if found is None:
    raise SystemExit("no incumbent_min_improvement_pct line to plant against")
path.write_text(pattern.sub(rf"\g<1>{os.environ['PLANTED']}", text, count=1), encoding="utf-8")
print(f"  incumbent_min_improvement_pct: {found.group(2)} -> {os.environ['PLANTED']}")
PY
then
  echo "could not tamper with the config; the drill cannot prove anything." >&2
  exit 2
fi

# ------------------------------------------------- 2. the gate must go RED ----
say "2. make verify-m2 — expected RED, naming the loosening with both numbers"
red_log="$(bash scripts/verify_m2.sh 2>&1)"
red_rc=$?
printf '%s\n' "$red_log" | grep -E 'FAIL|\[verify-m2\]'

if [[ "$red_rc" -ne 0 ]]; then
  ok "the gate exited $red_rc — RED against a margin below the one the PO sanctioned"
else
  bad "the gate exited 0 — the incumbent margin can be lowered without anything noticing"
fi
if printf '%s\n' "$red_log" | grep -q "LOOSENED.*${PLANTED}%"; then
  ok "it NAMES the loosening AND the number it fell below (the monotonic check, verify-m2 §2)"
else
  bad "the RED run does not name the lowered margin — a failure you have to guess at"
fi
# The era-aware replays must be UNAFFECTED. A historical verdict is judged
# against the bar in force when it was taken, so lowering today's bar cannot
# touch it — and a drill that turned those red would have proved the replays
# were reading the live config instead of the era table.
survivors=0
for replayed in "replayed lightgbm-v1-hobbled-shuffled-target" \
                "replayed champion-v1-plus-0.06min" \
                "replayed ERA-AWARE"; do
  if printf '%s\n' "$red_log" | grep -qF "$replayed"; then
    survivors=$((survivors + 1))
  else
    bad "'$replayed' stopped passing — the replays are reading the live bar, not the era"
  fi
done
[[ "$survivors" -eq 3 ]] && ok "the era-aware replays all still passed — history is judged by its own bar, and only the LIVE bar moved"

red_oks="$(printf '%s\n' "$red_log" | grep -c 'ok  ')"
if [[ "$red_oks" -ge 50 ]]; then
  ok "$red_oks sub-check(s) still ran and passed — the gate reports everything, not the first thing"
else
  bad "only $red_oks sub-check(s) still passed — the suite collapsed instead of continuing"
fi

# ------------------------------------------------------------ 3. put it back --
say "3. restore the config and re-run — expected GREEN again"
restore
trap - EXIT
after_sha="$(sha256sum "$CONFIG" | cut -d' ' -f1)"
if [[ "$after_sha" == "$BEFORE_SHA" ]]; then
  ok "$CONFIG is byte-identical to what the drill found (sha256 ${after_sha:0:12}…)"
else
  bad "$CONFIG changed across the drill — ${BEFORE_SHA:0:12}… -> ${after_sha:0:12}…"
fi
green_log="$(bash scripts/verify_m2.sh 2>&1)"
green_rc=$?
printf '%s\n' "$green_log" | tail -5
if [[ "$green_rc" -eq 0 ]]; then
  green_oks="$(printf '%s\n' "$green_log" | grep -c 'ok  ')"
  ok "the gate is GREEN again ($green_oks sub-checks, exit 0) — the drill left nothing behind"
else
  bad "the gate is still RED after the restore (rc=$green_rc) — the drill damaged something"
  printf '%s\n' "$green_log" | grep 'FAIL' >&2
fi

# ------------------------------------------------------------------ verdict ---
echo
if [[ "$PROBLEMS" -eq 0 ]]; then
  printf '\033[32m[gate-margin-redteam] PASSED: the M2 gate went RED on a lowered incumbent\033[0m\n'
  printf '\033[32m                      margin, named both numbers, left every era-aware replay\033[0m\n'
  printf '\033[32m                      passing, and returned GREEN when the config was restored.\033[0m\n'
  exit 0
fi
printf '\033[31m[gate-margin-redteam] FAILED: %d problem(s) with the check itself.\033[0m\n' "$PROBLEMS" >&2
exit 1
