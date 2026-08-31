#!/usr/bin/env bash
# verify_m6_redteam.sh — prove `make verify-m6` can go RED, and can come back.
#
# The fifth in the line after verify-m2/m3/m4/m5's red teams, and it plants the
# same CLASS of fault every one of them plants: break what a record SAYS, never
# what the system IS. M2 deleted an alias, M3 rewrote a measured KPI, M4 flipped
# one cache status, M5 rewrote one outage number. M6's equivalent is the outage
# the GAMEDAY measured when the predictor was killed under load —
# `observed.outage_seconds` in `automation/runs/m6-gameday/kill.json`, rewritten
# to the record's OWN `load.error_window.span_s`, and nothing else changes.
#
# WHY THIS FIELD, AND WHY THIS VALUE. It is the most plausible lie this file can
# tell:
#
#   * the replacement is DERIVED FROM THE RECORD ITSELF, not invented, so it is
#     internally sourced and looks self-consistent to anyone who skims;
#   * it is wrong by about a quarter of a second — a rounding-sized discrepancy,
#     not an absurdity;
#   * and it is the exact mistake this program has already made once, at scale:
#     M5-S4's first attempt computed the outage as `last_error - first_error`
#     and reported **182 s** for a service that was down for 13 (gotcha #75).
#     Anchoring an outage on the error SPAN rather than on first-failure ->
#     first-success is a mistake with a history here.
#
# TWO INDEPENDENT LEGS MUST CATCH IT, AND THEY READ DIFFERENT ARTIFACTS:
#
#   * the ANCHOR leg (§6) — the record must reconcile with its own arrivals: an
#     outage closes on the first SUCCESS after the last failure, so it is
#     strictly longer than the error span and shorter than one arrival gap
#     beyond it. The rewritten value is exactly the span, i.e. the excluded
#     bound;
#   * the PROSE leg (§7) — `docs/gameday_m6.md` quotes the real number to a
#     reader, and a gate that lets the write-up and the record drift apart is
#     how a milestone comes to be remembered by a number no measurement holds.
#
# The second is the one worth having. A gate that only re-derived the record's
# internal arithmetic would be checking a file against itself; the prose leg is
# what puts the number a HUMAN reads inside the same verdict. This is M5-S5's
# design, transplanted, and it is deliberate: the two gates fail the same way
# for the same reason, so the shape is learnable.
#
# The honest expectation is a SMALL blast radius — one field in one file — so
# this drill asserts BOTH halves:
#   * the RED run NAMES the outage and both witnesses, and
#   * every other section still RUNS and still passes.
#
# Safety: the record is restored by an EXIT trap from a byte copy taken before
# the edit, and the restore is verified by sha256, not assumed. It touches no
# cluster state, no pod, no image, no MLflow run, no registry version, no alias,
# no Prometheus rule and no traffic. Nothing is injected, nothing is killed and
# nothing is deployed — the drill's entire footprint is one tracked JSON file
# that ends the run byte-identical to how it started.
#
# Usage: scripts/verify_m6_redteam.sh   (via `make verify-m6-redteam`)
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

RECORD="automation/runs/m6-gameday/kill.json"

# The snapshot / restore / verify-sha scaffold — the byte copy, the EXIT trap,
# the sha-verified put-back, and the say/ok/bad printers — lives in ONE place
# from CU-S3 on. What deliberately did NOT move: this drill's PLANT, its
# assertions about the RED run, and its refusal when the record is missing.
REDTEAM_LABEL="[verify-m6-redteam]"
# shellcheck source=lib/redteam_restore.sh
source "$REPO_ROOT/scripts/lib/redteam_restore.sh"

# ------------------------------------------------------ 0. snapshot the truth --
say "0. the record as it stands (restored to exactly this, whatever happens)"
if [[ ! -s "$RECORD" ]]; then
  echo "$RECORD is missing — there is no gameday kill record to red-team. Run make gameday." >&2
  exit 2
fi
redteam_snapshot "$RECORD"

# ------------------------------------------------------------ 1. break it -----
say "1. rewrite ONE number: the gameday's outage becomes the error SPAN — gotcha #75, re-made"
if ! RECORD="$RECORD" uv run python - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["RECORD"])
rec = json.loads(path.read_text())
observed = rec["observed"]
was = observed["outage_seconds"]
# The wrong quantity, taken FROM THE RECORD rather than typed: the span from the
# first error to the last one. It is what M5-S4's first attempt reported, and it
# is what an outage looks like to anybody who has not thought about anchors.
now = observed["load"]["error_window"]["span_s"]
observed["outage_seconds"] = now
path.write_text(json.dumps(rec, indent=2) + "\n")
print(f"  observed.outage_seconds {was} -> {now} (the error-window span, derived from the record "
      f"itself). UNTOUCHED: the error window's own anchors "
      f"({observed['load']['error_window']['first_error_s']} "
      f"-> {observed['load']['error_window']['last_error_s']}), the {rec['observed']['error_count']} "
      f"failed requests, both pod uids, the alias {rec['observed']['alias']['before']} -> "
      f"{rec['observed']['alias']['after']}, the prediction, and all "
      f"{len(rec['checks'])} recorded checks")
PY
then
  echo "could not tamper with the record; the drill cannot prove anything." >&2
  exit 2
fi

# ------------------------------------------------------ 2. the gate must go RED
say "2. make verify-m6 — expected RED, naming the anchors AND the write-up that quotes them"
red_log="$(bash scripts/verify_m6.sh 2>&1)"
red_rc=$?
printf '%s\n' "$red_log" | grep -E 'FAIL|\[verify-m6\]'

if [[ "$red_rc" -ne 0 ]]; then
  ok "the gate exited $red_rc — RED against a record whose outage no longer reconciles"
else
  bad "the gate exited 0 — it read a plausible number and believed it"
fi
if printf '%s\n' "$red_log" | grep -q "does not reconcile with the run's anchors"; then
  ok "the ANCHOR leg fired: the recorded outage is not bounded by first-failure -> first-success, which is the only arithmetic that makes it an outage"
else
  bad "no leg re-derived the outage from its anchors — the gate is reading a summary field it cannot check"
fi
if printf '%s\n' "$red_log" | grep -q "quotes number(s) no record holds"; then
  ok "the PROSE leg fired: docs/gameday_m6.md and the record now disagree — the second witness, reading a different artifact"
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
for still_green in "the CHAMPION's exporter is up right now" \
                   "are LOADED and health=ok" \
                   "BEFORE the first traffic shift" \
                   "the INGRESS counter attributed" \
                   "the asymmetry is recorded" \
                   "the positive control ran FIRST" \
                   "stamped model_version"; do
  if printf '%s\n' "$red_log" | grep -qF "$still_green"; then
    ok "unaffected leg still green: ${still_green}"
  else
    bad "leg '${still_green}' did not pass during the RED run — collateral damage"
  fi
done

# The kill scenario's OTHER facts must still pass their own checks: a leg that
# went red for every field of this file would be a leg that fails on ANY edit
# rather than on a wrong one — M3's, M4's and M5's drills assert the same thing.
if printf '%s\n' "$red_log" | grep -q "carries the SAME prediction the committed file holds"; then
  ok "the kill record's prediction still matches the committed predictions file — the gate went red on the WRONG number, not on the edit"
else
  bad "the prediction-equality leg went red too — the gate fails on any edit rather than on a wrong one"
fi
if printf '%s\n' "$red_log" | grep -q "DISTINGUISHABLE signatures"; then
  ok "the kill's alert signature still reconciles with the storage break's — only the number moved"
else
  bad "the signature leg went red too — collateral damage inside the same record"
fi

# ------------------------------------------------------------ 3. put it back --
say "3. restore the record and re-run — expected GREEN again"
redteam_assert_restored
green_log="$(bash scripts/verify_m6.sh 2>&1)"
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
  printf '\033[32m[verify-m6-redteam] PASSED: the M6 gate went RED on ONE rewritten gameday\033[0m\n'
  printf '\033[32m                    outage — the exact wrong anchor gotcha #75 records — named\033[0m\n'
  printf '\033[32m                    both the arithmetic and the write-up that quotes it, kept\033[0m\n'
  printf '\033[32m                    counting every other sub-check, and returned GREEN when the\033[0m\n'
  printf '\033[32m                    record was restored.\033[0m\n'
  exit 0
fi
printf '\033[31m[verify-m6-redteam] FAILED: %d problem(s) with the gate itself.\033[0m\n' "$PROBLEMS" >&2
exit 1
