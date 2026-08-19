#!/usr/bin/env bash
# verify_m3_redteam.sh — prove `make verify-m3` can go RED, and can come back.
#
# The twin of `verify-m2-redteam`, aimed at the leg that is M3's whole point.
#
# What it breaks, and why this one: **one measured number in the bake-off's
# record**. `automation/runs/m3s5/bakeoff.json` carries, for each of the five
# contenders, the numbers the evaluator measured AND the verdict the gate
# returned. §5 of the gate does not read that verdict and believe it — it feeds
# the numbers back through `gate.decide` as it exists on disk right now and
# demands the same answer. So the sharpest possible fault is a record whose
# number and whose verdict no longer agree: exactly what a session that edited a
# table after seeing it would leave behind, and exactly what a `grep` for the
# word REFUSE cannot see.
#
# This drill moves `auto-on-v1` from 3.5038 (a REFUSE at -4.54% against the
# floor) to 3.2000 (a comfortable PROMOTE), leaving its recorded verdict at
# REFUSE. Nothing else is touched: no model, no run, no registry state, no other
# contender's row.
#
# Because the fault is one row in one file, the honest expectation is a SMALL
# blast radius, and the drill asserts both halves —
#   * the RED run NAMES `auto-on-v1` and both verdicts, and
#   * every other section still RUNS and still passes (a gate that collapses to
#     one failure when one thing breaks tells you nothing about the rest).
#
# It also asserts the thing the M2 drill could not: the four UNTAMPERED replays
# still pass during the RED run. A replay leg that went red for all five would be
# a leg that fails on any edit rather than on a wrong one.
#
# Safety: the file is restored by an EXIT trap from a byte copy taken before the
# edit, so a Ctrl-C, a failure or a crash mid-drill still leaves the record as it
# found it — and the restore is verified by sha256, not assumed.
#
# THE RECORD IS A TRACKED FILE from M5-S1 on (F-029 option A: verdict JSONs are
# committed, logs and .status stay ignored). Two consequences worth stating,
# because this drill is the reason the policy exists. A clean drill leaves a
# CLEAN TREE — the EXIT-trap restore is byte-identical, so `git status` after a
# successful run shows nothing, and anything it does show is a drill that did not
# finish. And a crashed drill is now recoverable by `git checkout --` as well as
# from the byte copy below: two copies where there used to be one.
#
# Usage: scripts/verify_m3_redteam.sh   (via `make verify-m3-redteam`)
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

RECORD="automation/runs/m3s5/bakeoff.json"
BACKUP="$(mktemp)"
RESTORED=0
PROBLEMS=0

say() { printf '\n\033[1m[verify-m3-redteam] %s\033[0m\n' "$1"; }
ok()  { printf '  \033[32mok  \033[0m %s\n' "$1"; }
bad() { printf '  \033[31mFAIL\033[0m %s\n' "$1" >&2; PROBLEMS=$((PROBLEMS + 1)); }

restore() {
  [[ "$RESTORED" -eq 1 ]] && return 0
  if cp "$BACKUP" "$RECORD"; then
    RESTORED=1
    local now before
    now="$(sha256sum "$RECORD" | cut -d' ' -f1)"
    before="$(sha256sum "$BACKUP" | cut -d' ' -f1)"
    if [[ "$now" == "$before" ]]; then
      printf '  restored %s (sha256 %s…)\n' "$RECORD" "${now:0:12}"
    else
      printf '\033[31m  RESTORE DID NOT MATCH — %s is not what it was.\033[0m\n' "$RECORD" >&2
    fi
  else
    printf '\033[31m[verify-m3-redteam] COULD NOT RESTORE %s.\033[0m\n' "$RECORD" >&2
    # Two ways back, and the byte copy is named FIRST because it is the one that
    # is right under every condition. The record is a tracked file from M5-S1 on
    # (F-029 option A), so `git checkout --` also works — but only if the record
    # was committed in the state this drill found it, which is not something a
    # failing restore path may assume. The byte copy was taken at step 0 of THIS
    # run, so it is exactly what was there; it is deliberately not deleted here.
    printf 'Copy it back by hand:  cp %s %s\n' "$BACKUP" "$RECORD" >&2
    printf '  (or, if it was committed as found:  git checkout -- %s)\n' "$RECORD" >&2
    return 0
  fi
  rm -f "$BACKUP"
}
trap restore EXIT

# ------------------------------------------------------ 0. snapshot the truth --
say "0. the record as it stands (restored to exactly this, whatever happens)"
if [[ ! -s "$RECORD" ]]; then
  echo "$RECORD is missing — there is no bake-off record to red-team." >&2
  exit 2
fi
cp "$RECORD" "$BACKUP"
BEFORE_SHA="$(sha256sum "$RECORD" | cut -d' ' -f1)"
printf '  %s  sha256 %s…\n' "$RECORD" "${BEFORE_SHA:0:12}"

# ------------------------------------------------------------ 1. break it -----
say "1. rewrite ONE contender's measured KPI-09 so its number and its verdict disagree"
if ! RECORD="$RECORD" uv run python - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["RECORD"])
rec = json.loads(path.read_text())
target = next(c for c in rec["contenders"] if c["label"] == "auto-on-v1")
was = target["test_mae"]
target["test_mae"] = 3.2000          # a comfortable PROMOTE against a 3.3518 floor
target["test_within_rate"] = 82.000  # ...and no KPI-10 regression either
path.write_text(json.dumps(rec, indent=1) + "\n")
print(f"  auto-on-v1 test KPI-09 {was} -> {target['test_mae']} "
      f"(its recorded verdict is still {target['verdict']!r})")
PY
then
  echo "could not tamper with the record; the drill cannot prove anything." >&2
  exit 2
fi

# ------------------------------------------------------ 2. the gate must go RED
say "2. make verify-m3 — expected RED, naming auto-on-v1 and both verdicts"
red_log="$(bash scripts/verify_m3.sh 2>&1)"
red_rc=$?
printf '%s\n' "$red_log" | grep -E 'FAIL|\[verify-m3\]'

if [[ "$red_rc" -ne 0 ]]; then
  ok "the gate exited $red_rc — RED against a record whose number contradicts its verdict"
else
  bad "the gate exited 0 — it is trusting the recorded verdict instead of replaying it"
fi
if printf '%s\n' "$red_log" | grep -q 'replaying auto-on-v1 through today.s gate gives PROMOTE'; then
  ok "it NAMES the broken row AND both verdicts: replayed PROMOTE vs recorded REFUSE"
else
  bad "the RED run does not name auto-on-v1 with both verdicts — a failure you have to guess at"
fi
# The four untampered replays must STILL pass. This is the half that separates a
# replay leg from a checksum: it must go red on a wrong number, not on any edit.
survivors=0
for contender in "replayed floor" "replayed champion v1" "replayed artisan v2" "replayed auto-on-v2"; do
  if printf '%s\n' "$red_log" | grep -qF "$contender"; then
    survivors=$((survivors + 1))
  else
    bad "replay '$contender' stopped passing — the leg fails on ANY edit, not on a wrong one"
  fi
done
[[ "$survivors" -eq 4 ]] && ok "all 4 untampered replays still passed — the leg reads numbers, not files"

# "Others still counted": every section that does not read this file must still
# have RUN and passed. A suite that stops at the first failure reports one
# problem and hides forty.
red_oks="$(printf '%s\n' "$red_log" | grep -c 'ok  ')"
if [[ "$red_oks" -ge 40 ]]; then
  ok "$red_oks sub-check(s) still ran and passed — the gate reports everything, not the first thing"
else
  bad "only $red_oks sub-check(s) still passed — the suite collapsed instead of continuing"
fi
for still_green in "the dossier holds" "reproduces all 5 verdicts" \
                   "the pruner FIRED" "a study outlived its process" \
                   "F-011 armed" "features.sets.resolve RAISES"; do
  if printf '%s\n' "$red_log" | grep -qF "$still_green"; then
    ok "unaffected leg still green: ${still_green}"
  else
    bad "leg '${still_green}' did not pass during the RED run — collateral damage"
  fi
done

# ------------------------------------------------------------ 3. put it back --
say "3. restore the record and re-run — expected GREEN again"
restore
trap - EXIT
after_sha="$(sha256sum "$RECORD" | cut -d' ' -f1)"
if [[ "$after_sha" == "$BEFORE_SHA" ]]; then
  ok "$RECORD is byte-identical to what the drill found (sha256 ${after_sha:0:12}…)"
else
  bad "$RECORD changed across the drill — ${BEFORE_SHA:0:12}… -> ${after_sha:0:12}…"
fi
green_log="$(bash scripts/verify_m3.sh 2>&1)"
green_rc=$?
printf '%s\n' "$green_log" | tail -6
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
  printf '\033[32m[verify-m3-redteam] PASSED: the M3 gate went RED on ONE contradicted number,\033[0m\n'
  printf '\033[32m                    named the row and both verdicts, kept counting every other\033[0m\n'
  printf '\033[32m                    sub-check, and returned GREEN when the record was restored.\033[0m\n'
  exit 0
fi
printf '\033[31m[verify-m3-redteam] FAILED: %d problem(s) with the gate itself.\033[0m\n' "$PROBLEMS" >&2
exit 1
