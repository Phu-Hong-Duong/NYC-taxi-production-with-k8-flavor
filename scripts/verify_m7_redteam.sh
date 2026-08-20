#!/usr/bin/env bash
# verify_m7_redteam.sh — prove `make verify-m7` can go RED, and can come back.
#
# The sixth in the line after verify-m2/m3/m4/m5/m6's red teams, and it plants
# the same CLASS of fault every one of them plants: break what a record SAYS,
# never what the system IS. M2 deleted an alias, M3 rewrote a measured KPI, M4
# flipped one cache status, M5 and M6 each rewrote one outage number. M7's
# equivalent is the quantity this whole milestone is ABOUT —
# `volume_ratio` in `automation/runs/m7-drift/drift-2020-03.json`, rewritten
# from a ratio of RATES to a ratio of TOTALS, and nothing else changes.
#
# WHY THIS FIELD, AND WHY THIS VALUE. It is the most plausible lie this file can
# tell, and it is the milestone's own thesis turned against it:
#
#   * the replacement is DERIVED FROM THE RECORD ITSELF — `current_rows` over
#     `reference_rows / len(reference_months)`, i.e. this month's trips against
#     the reference's trips PER MONTH. Every term is in the file;
#   * it is wrong by about one percentage point (0.3913 -> 0.4021), which is a
#     rounding-sized discrepancy rather than an absurdity, and it stays well
#     under the 0.50 bar — so the alert still fires, the verdict is unchanged,
#     and NOTHING about the story reads differently to somebody who skims;
#   * and it is the exact mistake M7-S5's memo exists to warn about. F-045 is
#     the finding that a row-weighted monthly aggregate of a collapse is
#     weighted by exactly the rows that disappeared. A month is not a unit of
#     demand; a day is. Swapping the rate for the total is that error wearing a
#     summary field's clothes, and February's 29 days are the reason it does not
#     cancel out.
#
# THREE INDEPENDENT LEGS MUST CATCH IT, AND THEY READ THREE DIFFERENT ARTIFACTS:
#
#   * the ANCHOR leg (§5) — the record must reconcile with its own numerator and
#     denominator: `current_trips_per_day / reference_trips_per_day`. The
#     rewritten value is a different quotient of the same file;
#   * the SECOND-WITNESS leg (§5) — `drift_fire_drill.json` recorded what the
#     live gateway held while the alert was being judged, and that is a
#     separately-written tracked record. A claim only one artifact makes is not
#     a measurement;
#   * the PROSE leg (§7) — `docs/drift_memo_m7.md` §7 tabulates the ratio for a
#     human, and a gate that lets the write-up and the record drift apart is how
#     a milestone comes to be remembered by a number no measurement holds.
#
# The third is the one worth having. A gate that only re-derived the record's
# internal arithmetic would be checking a file against itself; the prose leg is
# what puts the number a HUMAN reads inside the same verdict. This is M5-S5's
# and M6-S5's design, transplanted, and it is deliberate: the gates fail the
# same way for the same reason, so the shape is learnable.
#
# The honest expectation is a SMALL blast radius — one field in one file — so
# this drill asserts BOTH halves:
#   * the RED run NAMES the ratio and all three witnesses, and
#   * every other section still RUNS and still passes — including the leg that
#     checks the bar has daylight on both sides of it, which the planted value
#     does NOT break. That is what separates a gate that goes red on a WRONG
#     number from one that goes red on ANY edit.
#
# Safety: the record is restored by an EXIT trap from a byte copy taken before
# the edit, and the restore is verified by sha256, not assumed. It touches no
# cluster state, no pod, no image, no MLflow run, no registry version, no alias,
# no Prometheus rule, no pushed metric and no traffic. Nothing is injected,
# nothing is killed and nothing is deployed — the drill's entire footprint is
# one tracked JSON file that ends the run byte-identical to how it started.
#
# Usage: scripts/verify_m7_redteam.sh   (via `make verify-m7-redteam`)
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

RECORD="automation/runs/m7-drift/drift-2020-03.json"
BACKUP="$(mktemp)"
RESTORED=0
PROBLEMS=0

say() { printf '\n\033[1m[verify-m7-redteam] %s\033[0m\n' "$1"; }
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
    printf '\033[31m[verify-m7-redteam] COULD NOT RESTORE %s.\033[0m\n' "$RECORD" >&2
    printf 'The drill kept a copy at %s — copy it back by hand.\n' "$BACKUP" >&2
    printf '  (or, since it is tracked:  git checkout -- %s)\n' "$RECORD" >&2
    return 0
  fi
  rm -f "$BACKUP"
}
trap restore EXIT

# ------------------------------------------------------ 0. snapshot the truth --
say "0. the record as it stands (restored to exactly this, whatever happens)"
if [[ ! -s "$RECORD" ]]; then
  echo "$RECORD is missing — there is no drift record to red-team. Run make drift." >&2
  exit 2
fi
cp "$RECORD" "$BACKUP"
BEFORE_SHA="$(sha256sum "$RECORD" | cut -d' ' -f1)"
printf '  %s  sha256 %s…\n' "$RECORD" "${BEFORE_SHA:0:12}"

# ------------------------------------------------------------ 1. break it -----
say "1. rewrite ONE number: the volume ratio becomes a ratio of TOTALS — F-045's own mistake"
if ! RECORD="$RECORD" uv run python - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["RECORD"])
rec = json.loads(path.read_text())
was = rec["volume_ratio"]
# The wrong quantity, taken FROM THE RECORD rather than typed: this month's
# TRIPS against the reference's trips per MONTH. Every term is already in the
# file, so the value is internally sourced and reads as self-consistent to
# anybody who does not stop to ask what a "ratio" is a ratio OF.
now = rec["current_rows"] / (rec["reference_rows"] / len(rec["reference_months"]))
rec["volume_ratio"] = now
path.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
print(f"  volume_ratio {was:.10f} -> {now:.10f} (rows over rows-per-reference-month, derived from "
      f"the record itself). It is still under the 0.50 bar, so the ALERT STILL FIRES and the "
      f"verdict does not change. UNTOUCHED: current_rows {rec['current_rows']:,}, "
      f"current_trips_per_day {rec['current_trips_per_day']:.4f}, reference_trips_per_day "
      f"{rec['reference_trips_per_day']:.4f}, max_input_psi {rec['max_input_psi']:.6f}, and every "
      f"one of the {len(rec['columns'])} per-column PSI values")
PY
then
  echo "could not tamper with the record; the drill cannot prove anything." >&2
  exit 2
fi

# ------------------------------------------------------ 2. the gate must go RED
say "2. make verify-m7 — expected RED, naming the anchors, the second witness AND the memo"
red_log="$(bash scripts/verify_m7.sh 2>&1)"
red_rc=$?
printf '%s\n' "$red_log" | grep -E 'FAIL|\[verify-m7\]'

if [[ "$red_rc" -ne 0 ]]; then
  ok "the gate exited $red_rc — RED against a record whose ratio no longer reconciles"
else
  bad "the gate exited 0 — it read a plausible number and believed it"
fi
if printf '%s\n' "$red_log" | grep -q "do not reconcile with the run's anchors"; then
  ok "the ANCHOR leg fired: a volume ratio is trips/DAY over trips/DAY, and the planted value is a different quotient of the same file"
else
  bad "no leg re-derived the ratio from its anchors — the gate is reading a summary field it cannot check"
fi
if printf '%s\n' "$red_log" | grep -q "the drill record and the per-month records disagree"; then
  ok "the SECOND-WITNESS leg fired: what the drill observed on the live gateway and what the per-month record now claims are two different numbers"
else
  bad "the second-witness leg did NOT fire — a claim only one tracked artifact makes is passing as a measurement"
fi
if printf '%s\n' "$red_log" | grep -q "the memo quotes number(s) no record holds"; then
  ok "the PROSE leg fired: docs/drift_memo_m7.md §7 and the record now disagree — the third witness, and the only one a human reads"
else
  bad "the prose leg did NOT fire — the write-up and the record may drift apart without the gate noticing"
fi

# "Others still counted": every section that does not read this field must still
# have RUN and passed. A suite that stops at the first failure reports one
# problem and hides sixty.
red_oks="$(printf '%s\n' "$red_log" | grep -c 'ok  ')"
if [[ "$red_oks" -ge 50 ]]; then
  ok "$red_oks sub-check line(s) still passed — the gate reports everything, not the first thing"
else
  bad "only $red_oks sub-check(s) still passed — the suite collapsed instead of continuing"
fi
for still_green in "still returns exactly" \
                   "differ in all" \
                   "reconcile for every month" \
                   "are LOADED and health=ok" \
                   "and nothing else — 2019 only" \
                   "COMMITTED before any 2020 drift record" \
                   "was REFUSED and promoted=False" \
                   "stamped model_version"; do
  if printf '%s\n' "$red_log" | grep -qE "$still_green"; then
    ok "unaffected leg still green: ${still_green}"
  else
    bad "leg '${still_green}' did not pass during the RED run — collateral damage"
  fi
done

# THE LEG THAT MUST **NOT** FIRE, and it is the point of choosing a plausible
# value. The planted ratio is still below the bar and still above every accepted
# 2019 month, so the daylight check has no reason to complain — a gate that went
# red here too would be a gate that fails on ANY edit rather than on a wrong one.
if printf '%s\n' "$red_log" | grep -q "daylight on both sides"; then
  ok "the bar-daylight leg is STILL GREEN — the planted value keeps the alert firing and the argument intact, so the gate went red on a WRONG number rather than on the fact of an edit"
else
  bad "the daylight leg went red too — the plant was too crude to distinguish a wrong number from any change"
fi
if printf '%s\n' "$red_log" | grep -q "exactly the predicted alert fired"; then
  ok "the drill's own verdict still passes — only the ratio moved, not the outcome it produced"
else
  bad "the drill-verdict leg went red too — collateral damage inside the same evidence chain"
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
green_log="$(bash scripts/verify_m7.sh 2>&1)"
green_rc=$?
printf '%s\n' "$green_log" | tail -5
if [[ "$green_rc" -eq 0 ]]; then
  green_oks="$(printf '%s\n' "$green_log" | grep -c 'ok  ')"
  ok "the gate is GREEN again ($green_oks sub-check line(s), exit 0) — the drill left nothing behind"
else
  bad "the gate is still RED after the restore (rc=$green_rc) — the drill damaged something"
  printf '%s\n' "$green_log" | grep 'FAIL' >&2
fi

# A clean drill leaves a CLEAN TREE — a property that could only be stated once
# the records became tracked files (F-029, closed at M5-S1).
dirty="$(git status --porcelain "$RECORD")"
if [[ -z "$dirty" ]]; then
  ok "git status is clean for $RECORD — the restore is byte-identical to the committed record"
else
  bad "the tree is dirty after the drill: $dirty"
fi

# ------------------------------------------------------------------ verdict ---
echo
if [[ "$PROBLEMS" -eq 0 ]]; then
  printf '\033[32m[verify-m7-redteam] PASSED: the M7 gate went RED on ONE rewritten volume\033[0m\n'
  printf '\033[32m                    ratio — a total where a rate belongs, which is F-045 itself —\033[0m\n'
  printf '\033[32m                    named the arithmetic, the second tracked witness AND the memo\033[0m\n'
  printf '\033[32m                    that quotes it, left the bar-daylight argument standing, kept\033[0m\n'
  printf '\033[32m                    counting every other sub-check, and returned GREEN when the\033[0m\n'
  printf '\033[32m                    record was restored.\033[0m\n'
  exit 0
fi
printf '\033[31m[verify-m7-redteam] FAILED: %d problem(s) with the gate itself.\033[0m\n' "$PROBLEMS" >&2
exit 1
