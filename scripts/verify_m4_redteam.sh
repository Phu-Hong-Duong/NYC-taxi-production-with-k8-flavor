#!/usr/bin/env bash
# verify_m4_redteam.sh — prove `make verify-m4` can go RED, and can come back.
#
# The twin of `verify-m2-redteam` and `verify-m3-redteam`, aimed at the leg that
# is M4's whole point: **the cache-hit rerun**.
#
# What it breaks, and why this one. The kickoff asks for a POINTER-class fault —
# break what something SAYS, never what it IS. M2 deleted an alias (a pointer to
# a model), M3 rewrote a measured number in a record. M4's equivalent is one
# field of one action in `automation/runs/m4-cache/cache_drill.json`: run 2's
# `train` stage moves from `CACHE_HIT` to `CACHE_POPULATED`, and NOTHING ELSE
# changes — its duration stays 140 ms, its phase stays SUCCEEDED, MLflow's
# recorded run counts stay 16 -> 16.
#
# That is deliberately the most PLAUSIBLE possible lie. Every field is
# individually well-formed; the record still describes a green run of seven
# stages; a reader skimming it sees nothing wrong. What it now claims is that
# the 31-minute fit re-executed on the rerun. Three things in the file contradict
# that, and the gate must notice at least the interesting ones:
#
#   * the CLAIM leg — a cacheable stage that is not a CACHE_HIT (the direct read);
#   * the CROSS-SYSTEM leg — a stage that re-executed its fit while the tracking
#     server, which cannot see the cache and has never heard of Flyte, minted no
#     run. Two independent witnesses, now disagreeing.
#
# The second is the one worth having. It is the reason the drill asks three
# systems and ranks them, and a gate that only read `cache_status` would have
# believed this file.
#
# The honest expectation is a SMALL blast radius — one field in one file — so
# this drill asserts both halves, exactly as M3's does:
#   * the RED run NAMES `train` and both witnesses, and
#   * every other section still RUNS and still passes.
#
# Safety: the record is restored by an EXIT trap from a byte copy taken before
# the edit, so a Ctrl-C, a failure or a crash mid-drill still leaves it as found
# — and the restore is verified by sha256, not assumed. It touches no cluster
# state, no image, no MLflow run, no registry version, and no warehouse row.
#
# THE RECORD IS A TRACKED FILE from M5-S1 on (F-029 option A: verdict JSONs are
# committed, logs and .status stay ignored). This drill is the argument for that
# policy in one line — the fault it plants is an edited record, and until M5-S1
# an edited record left no diff for a reviewer to see. Two consequences: a clean
# drill leaves a CLEAN TREE (the restore is byte-identical, so anything `git
# status` shows afterwards is a drill that did not finish), and a crashed drill
# is recoverable by `git checkout --` as well as from the byte copy.
#
# Usage: scripts/verify_m4_redteam.sh   (via `make verify-m4-redteam`)
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

RECORD="automation/runs/m4-cache/cache_drill.json"
BACKUP="$(mktemp)"
RESTORED=0
PROBLEMS=0

say() { printf '\n\033[1m[verify-m4-redteam] %s\033[0m\n' "$1"; }
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
    printf '\033[31m[verify-m4-redteam] COULD NOT RESTORE %s.\033[0m\n' "$RECORD" >&2
    printf 'The drill kept a copy at %s — copy it back by hand.\n' "$BACKUP" >&2
    printf '  (or, if it was committed as found:  git checkout -- %s)\n' "$RECORD" >&2
    return 0
  fi
  rm -f "$BACKUP"
}
trap restore EXIT

# ------------------------------------------------------ 0. snapshot the truth --
say "0. the record as it stands (restored to exactly this, whatever happens)"
if [[ ! -s "$RECORD" ]]; then
  echo "$RECORD is missing — there is no cache record to red-team. Run make pipeline-cache-drill." >&2
  exit 2
fi
cp "$RECORD" "$BACKUP"
BEFORE_SHA="$(sha256sum "$RECORD" | cut -d' ' -f1)"
printf '  %s  sha256 %s…\n' "$RECORD" "${BEFORE_SHA:0:12}"

# ------------------------------------------------------------ 1. break it -----
say "1. rewrite ONE field: run 2's train stage claims it re-executed, and nothing else changes"
if ! RECORD="$RECORD" uv run python - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["RECORD"])
rec = json.loads(path.read_text())
# The most expensive stage of the rerun, named from the record rather than typed:
# whichever cacheable stage cost run 1 the most is the one whose reuse the drill
# exists to demonstrate, and therefore the one worth lying about.
run1 = {a["short_name"]: a for a in rec["run1"]["actions"]}
target = max(
    (a for a in rec["run2"]["actions"] if a["cache_status"] == "CACHE_HIT"),
    key=lambda a: run1.get(a["short_name"], {}).get("duration_ms", 0),
)
was = target["cache_status"]
target["cache_status"] = "CACHE_POPULATED"
path.write_text(json.dumps(rec, indent=2) + "\n")
print(f"  run 2 / {target['short_name']}: cache_status {was} -> {target['cache_status']} "
      f"(duration still {target['duration_ms']} ms, phase still {target['phase']}, "
      f"MLflow counts untouched at {rec['mlflow_runs']['after_run1']} -> "
      f"{rec['mlflow_runs']['after_run2']})")
PY
then
  echo "could not tamper with the record; the drill cannot prove anything." >&2
  exit 2
fi

# ------------------------------------------------------ 2. the gate must go RED
say "2. make verify-m4 — expected RED, naming the stage and both witnesses"
red_log="$(bash scripts/verify_m4.sh 2>&1)"
red_rc=$?
printf '%s\n' "$red_log" | grep -E 'FAIL|\[verify-m4\]'

if [[ "$red_rc" -ne 0 ]]; then
  ok "the gate exited $red_rc — RED against a record whose cache claim contradicts MLflow"
else
  bad "the gate exited 0 — it read a well-formed record and believed it"
fi
if printf '%s\n' "$red_log" | grep -q "cacheable stage(s) did not hit on the rerun.*train"; then
  ok "the CLAIM leg names the stage: train is a cacheable stage that did not read CACHE_HIT"
else
  bad "no leg named the stage whose cache_status was rewritten — a failure you have to guess at"
fi
if printf '%s\n' "$red_log" | grep -q "two witnesses CONTRADICT each other"; then
  ok "the CROSS-SYSTEM leg fired: the record says a fit re-executed while MLflow minted nothing — the leg a gate reading only cache_status would not have had"
else
  bad "the cross-system leg did NOT fire — the gate is trusting one witness about a question two can answer"
fi

# "Others still counted": every section that does not read this file must still
# have RUN and passed. A suite that stops at the first failure reports one
# problem and hides forty.
red_oks="$(printf '%s\n' "$red_log" | grep -c 'ok  ')"
if [[ "$red_oks" -ge 33 ]]; then
  ok "$red_oks sub-check(s) still ran and passed — the gate reports everything, not the first thing"
else
  bad "only $red_oks sub-check(s) still passed — the suite collapsed instead of continuing"
fi
for still_green in "is wrapped by a Flyte task" \
                   "in-container OpenMP is the SYSTEM package" \
                   "a DIFFERENT pod object ran" \
                   "the budget of" \
                   "reconciles with the analyst layer" \
                   "is a registry version"; do
  if printf '%s\n' "$red_log" | grep -qF "$still_green"; then
    ok "unaffected leg still green: ${still_green}"
  else
    bad "leg '${still_green}' did not pass during the RED run — collateral damage"
  fi
done

# The record's OTHER stages must still pass their own checks. A leg that went red
# for all five cacheable stages would be a leg that fails on any edit rather than
# on a wrong one — the same property M3's drill asserts about its four survivors.
if printf '%s\n' "$red_log" | grep -q "run 1 POPULATED all"; then
  ok "run 1's populate leg still passed — the drill's other 4 cacheable stages were not collateral"
else
  bad "the populate leg went red too — the check fails on ANY edit, not on a wrong one"
fi

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
green_log="$(bash scripts/verify_m4.sh 2>&1)"
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
  printf '\033[32m[verify-m4-redteam] PASSED: the M4 gate went RED on ONE rewritten cache\033[0m\n'
  printf '\033[32m                    status, named the stage AND the contradiction between two\033[0m\n'
  printf '\033[32m                    independent witnesses, kept counting every other sub-check,\033[0m\n'
  printf '\033[32m                    and returned GREEN when the record was restored.\033[0m\n'
  exit 0
fi
printf '\033[31m[verify-m4-redteam] FAILED: %d problem(s) with the gate itself.\033[0m\n' "$PROBLEMS" >&2
exit 1
