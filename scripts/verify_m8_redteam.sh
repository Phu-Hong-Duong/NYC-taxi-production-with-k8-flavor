#!/usr/bin/env bash
# verify_m8_redteam.sh — prove `make verify-m8` can go RED, and can come back.
#
# The seventh in the line after verify-m2/m3/m4/m5/m6/m7's red teams, and it
# plants the same CLASS of fault every one of them plants: break what a record
# SAYS, never what the system IS. M2 deleted an alias, M3 rewrote a measured
# KPI, M4 flipped one cache status, M5 and M6 each rewrote one outage number, M7
# turned a rate into a total. M8's equivalent is the count this whole milestone
# turns out to rest on — `both_missing` on ONE column of the 100-pair record,
# rewritten from the true 13 to **0**.
#
# WHY THIS FIELD, AND WHY THIS VALUE. It is the most plausible lie this file can
# tell, because it is not a lie about a measurement at all — it is what a
# CORRECT-LOOKING measurement of the wrong population reports:
#
#   * `compared`, `mismatches` and `max_abs_delta` are left exactly as they
#     were, so the headline the whole milestone quotes — `max |online − offline|
#     = 0.000e+00` — is untouched, the verdict stays `PASSED`, and every seam
#     summary still reads as a clean pass;
#   * zero missing values is what a comparison that silently DROPPED NULLS
#     would print. That is not a hypothetical: `docs/feast_online_m8.md` §2
#     argues at length that a null-dropping comparison "would print a perfect
#     zero while being blind to exactly those rows", the ~1% of every split
#     that carries no geometry and on which F-030 was found. The planted record
#     describes exactly that comparison, and it looks BETTER than the truth;
#   * and it is a smaller, tidier number than the one it replaces, which is the
#     direction a careless edit actually goes.
#
# THREE INDEPENDENT LEGS MUST CATCH IT, AND THEY READ THREE DIFFERENT THINGS:
#
#   * the NO-GEOMETRY leg (§3) — the run's own two-sided assertion says the
#     store declined 13 pickup zones and our path has no geometry for the same
#     13. A column claiming zero missing values contradicts the block six lines
#     below it in the same file;
#   * the ANCHOR leg (§3) — the seven static columns are compared a SECOND time
#     against `taxi_mlops.features`, and that comparison counted its own missing
#     rows. One edited field leaves the seam and its own anchor disagreeing;
#   * the PROSE leg (§3) — `docs/feast_online_parity_table.md` is the
#     blueprint's named accept artifact and the file a reviewer diffs. It
#     renders `both missing` per column, and the planted record no longer
#     matches the table that is supposed to have been generated from it.
#
# The third is the one worth having, and it is the M5/M6/M7 design transplanted:
# a gate that only re-derived the record's internal arithmetic would be checking
# a file against itself. The first two are worth having because they are two
# INDEPENDENT internal witnesses — the anchor block exists for a completely
# different reason (without it the table would be two Feast reads agreeing with
# each other) and only incidentally counts the same nulls.
#
# The honest expectation is a SMALL blast radius — one field in one file — so
# this drill asserts BOTH halves:
#   * the RED run NAMES the missing counts and all three witnesses, and
#   * every other section still RUNS and still passes — including the leg that
#     reports the headline delta, which the planted value does NOT break. That
#     is what separates a gate that goes red on a WRONG number from one that
#     goes red on ANY edit.
#
# Safety: the record is restored by an EXIT trap from a byte copy taken before
# the edit, and the restore is verified by sha256, not assumed. It touches no
# cluster state, no pod, no image, no MLflow run, no registry version, no alias,
# no Prometheus rule, no Redis key and no traffic. Nothing is materialized,
# nothing is deployed and nothing is applied — the drill's entire footprint is
# one tracked JSON file that ends the run byte-identical to how it started.
#
# Usage: scripts/verify_m8_redteam.sh   (via `make verify-m8-redteam`)
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

RECORD="automation/runs/m8-online/online_parity.json"

# The snapshot / restore / verify-sha scaffold — the byte copy, the EXIT trap,
# the sha-verified put-back, and the say/ok/bad printers — lives in ONE place
# from CU-S3 on. What deliberately did NOT move: this drill's PLANT, its
# assertions about the RED run, and its refusal when the record is missing.
REDTEAM_LABEL="[verify-m8-redteam]"
# shellcheck source=lib/redteam_restore.sh
source "$REPO_ROOT/scripts/lib/redteam_restore.sh"

# ------------------------------------------------------ 0. snapshot the truth --
say "0. the record as it stands (restored to exactly this, whatever happens)"
if [[ ! -s "$RECORD" ]]; then
  echo "$RECORD is missing — there is no parity record to red-team." >&2
  echo "Run: make feast-online-parity" >&2
  exit 2
fi
redteam_snapshot "$RECORD"

# ------------------------------------------------------------ 1. break it -----
say "1. rewrite ONE count: a column reports ZERO missing values — what a null-dropping comparison prints"
if ! RECORD="$RECORD" uv run python - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["RECORD"])
rec = json.loads(path.read_text())

# The target is CHOSEN from the record, never typed: the first pickup-zone column
# that actually has missing rows to hide. A drill that typed a column name would
# stop working the day the column list legitimately changed, and would also stop
# being an argument about the property.
target = next(c for c in rec["seam"]
              if c["column"].startswith("pu_zone.") and c["both_missing"] > 0)
was = target["both_missing"]
target["both_missing"] = 0
path.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")

geom = rec["no_geometry"]["pu"]["rows_without_geometry_our_path"]
print(f"  {target['column']}: both_missing {was} -> 0 — the record now says every one of the "
      f"{target['compared']} declared pairs had a value on BOTH sides. UNTOUCHED: compared "
      f"{target['compared']}, mismatches {target['mismatches']}, max_abs_delta "
      f"{target['max_abs_delta']}, one_missing {target['one_missing']}, verdict "
      f"{rec['verdict']!r}, and the headline max_abs_delta {rec['max_abs_delta']} across all "
      f"{len(rec['seam'])} columns. The pass still reads as a pass; it now describes a "
      f"comparison that never looked at the {geom} zones with no geometry.")
PY
then
  echo "could not tamper with the record; the drill cannot prove anything." >&2
  exit 2
fi

# ------------------------------------------------------ 2. the gate must go RED
say "2. make verify-m8 — expected RED, naming the run's own no-geometry block, its anchor AND the table"
red_log="$(bash scripts/verify_m8.sh 2>&1)"
red_rc=$?
printf '%s\n' "$red_log" | grep -E 'FAIL|\[verify-m8\]'

if [[ "$red_rc" -ne 0 ]]; then
  ok "the gate exited $red_rc — RED against a record whose missing counts no longer reconcile"
else
  bad "the gate exited 0 — it read a clean-looking pass and believed it"
fi
if printf '%s\n' "$red_log" | grep -q "do not reconcile with the run's own no-geometry assertion"; then
  ok "the NO-GEOMETRY leg fired: the run asserted two-sidedly that the store declined exactly the zones our path has no geometry for, and one column now claims it saw values for all of them"
else
  bad "no leg cross-checked the missing counts against the no-geometry assertion — the gate is reading a summary field it cannot check"
fi
if printf '%s\n' "$red_log" | grep -q "seam and its anchor disagree about which rows are missing"; then
  ok "the ANCHOR leg fired: the second, independently-built comparison against taxi_mlops.features counted the same rows and still says so"
else
  bad "the anchor leg did NOT fire — one edited field contradicted nothing inside its own record"
fi
if printf '%s\n' "$red_log" | grep -q "the table a reviewer reads and the record disagree"; then
  ok "the PROSE leg fired: docs/feast_online_parity_table.md — the blueprint's named accept artifact — renders a number the record no longer holds"
else
  bad "the prose leg did NOT fire — the Show artifact and the record may drift apart unnoticed"
fi

# "Others still counted": every section that does not read this field must still
# have RUN and passed. A suite that stops at the first failure reports one
# problem and hides fifty.
red_oks="$(printf '%s\n' "$red_log" | grep -c 'ok  ')"
if [[ "$red_oks" -ge 40 ]]; then
  ok "$red_oks sub-check line(s) still passed — the gate reports everything, not the first thing"
else
  bad "only $red_oks sub-check(s) still passed — the suite collapsed instead of continuing"
fi
for still_green in "BYTE-IDENTICAL to the lock-rebaselined-m9-publish tag" \
                   "is ABSENT from the project environment" \
                   "the import law holds in BOTH directions" \
                   "COMMITTED BEFORE the records they judge" \
                   "the NAIVE answer IS our own full-window table" \
                   "answered two-sidedly" \
                   "holds 57" \
                   "carries exactly" \
                   "honest in both directions" \
                   "NOT ONE of the"; do
  if printf '%s\n' "$red_log" | grep -qE "$still_green"; then
    ok "unaffected leg still green: ${still_green}"
  else
    bad "leg '${still_green}' did not pass during the RED run — collateral damage"
  fi
done

# THE LEG THAT MUST **NOT** FIRE, and it is the point of choosing this field.
# The headline delta is untouched, so the seam's own pass/fail verdict has no
# reason to complain — a gate that went red there too would be a gate that fails
# on ANY edit rather than on a wrong one.
if printf '%s\n' "$red_log" | grep -q "all four seams measured EXACTLY 0.000e+00"; then
  ok "the four-seam headline leg is STILL GREEN — the planted record keeps the measured delta and the verdict intact, so the gate went red on a WRONG POPULATION rather than on the fact of an edit"
else
  bad "the headline leg went red too — the plant was too crude to distinguish a wrong number from any change"
fi
if printf '%s\n' "$red_log" | grep -q "one missing. is ZERO on every column"; then
  ok "and the one-missing leg is still green — the plant moved the count nobody was checking, which is exactly why the three new witnesses had to exist"
else
  bad "the one-missing leg went red too — collateral damage inside the same block"
fi

# ------------------------------------------------------------ 3. put it back --
say "3. restore the record and re-run — expected GREEN again"
redteam_assert_restored
green_log="$(bash scripts/verify_m8.sh 2>&1)"
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
  printf '\033[32m[verify-m8-redteam] PASSED: the M8 gate went RED on ONE rewritten missing\033[0m\n'
  printf '\033[32m                    count — a column reporting zero missing values, which is\033[0m\n'
  printf '\033[32m                    what a comparison that dropped nulls prints and is better\033[0m\n'
  printf '\033[32m                    than the truth — named the run own no-geometry assertion,\033[0m\n'
  printf '\033[32m                    its independent anchor AND the accept table a reviewer\033[0m\n'
  printf '\033[32m                    diffs, left the measured delta standing, kept counting\033[0m\n'
  printf '\033[32m                    every other sub-check, and returned GREEN on restore.\033[0m\n'
  exit 0
fi
printf '\033[31m[verify-m8-redteam] FAILED: %d problem(s) with the gate itself.\033[0m\n' "$PROBLEMS" >&2
exit 1
