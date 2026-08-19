#!/usr/bin/env bash
# verify_m5_redteam.sh — prove `make verify-m5` can go RED, and can come back.
#
# The twin of verify-m2/m3/m4's red teams, aimed at the number M5 exists to
# publish: **how long the endpoint is gone when its pod dies**.
#
# What it breaks, and why this one. The kickoff asks for a POINTER-class or
# ONE-FIELD fault — break what something SAYS, never what it IS. M2 deleted an
# alias, M3 rewrote a measured KPI, M4 flipped one cache status. M5's
# equivalent is `recovery.outage_seconds` in
# `automation/runs/m5-load/selfheal.json`, rewritten to the record's OWN
# `error_window.span_s` — and nothing else changes.
#
# That is deliberately the most plausible lie this file can tell:
#
#   * the replacement value is DERIVED FROM THE RECORD ITSELF, not invented, so
#     it is internally sourced and self-consistent-looking;
#   * it is wrong by 0.28 s — a rounding-sized discrepancy, not an absurdity;
#   * and it is the exact mistake a real session made: M5-S4's first attempt
#     computed the outage as `last_error - first_error` and reported **182 s**
#     for a service that was down for 13 (gotcha #75). Anchoring an outage on
#     the error SPAN rather than on first-failure -> first-success is the error
#     this program has already made once, at scale.
#
# Two independent legs must catch it, and they read different artifacts:
#
#   * the ANCHOR leg (§5) — the record must reconcile with itself:
#     `recovered_at - first_error_after_kill` is the outage, and the rewritten
#     number no longer equals it;
#   * the RUNBOOK leg (§6) — `docs/runbooks/serving.md` quotes 14.53 s to an
#     operator, and a gate that lets prose and record drift apart is how a
#     runbook comes to quote a hope.
#
# The second is the one worth having. A gate that only checked the record's
# internal arithmetic would be checking a file against itself; the runbook leg
# is what makes the number the OPERATOR reads part of the same verdict.
#
# The honest expectation is a SMALL blast radius — one field in one file — so
# this drill asserts both halves, exactly as M3's and M4's do:
#   * the RED run NAMES the outage and both witnesses, and
#   * every other section still RUNS and still passes.
#
# Safety: the record is restored by an EXIT trap from a byte copy taken before
# the edit, and the restore is verified by sha256, not assumed. It touches no
# cluster state, no pod, no image, no MLflow run, no registry version and no
# alias — the served model is never even read for writing. `@champion` is a
# READ throughout, by the gate it runs.
#
# Usage: scripts/verify_m5_redteam.sh   (via `make verify-m5-redteam`)
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

RECORD="automation/runs/m5-load/selfheal.json"
BACKUP="$(mktemp)"
RESTORED=0
PROBLEMS=0

say() { printf '\n\033[1m[verify-m5-redteam] %s\033[0m\n' "$1"; }
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
    printf '\033[31m[verify-m5-redteam] COULD NOT RESTORE %s.\033[0m\n' "$RECORD" >&2
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
  echo "$RECORD is missing — there is no self-heal record to red-team. Run make load-drill." >&2
  exit 2
fi
cp "$RECORD" "$BACKUP"
BEFORE_SHA="$(sha256sum "$RECORD" | cut -d' ' -f1)"
printf '  %s  sha256 %s…\n' "$RECORD" "${BEFORE_SHA:0:12}"

# ------------------------------------------------------------ 1. break it -----
say "1. rewrite ONE number: the outage becomes the error SPAN — gotcha #75's mistake, re-made"
if ! RECORD="$RECORD" uv run python - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["RECORD"])
rec = json.loads(path.read_text())
recovery = rec["recovery"]
was = recovery["outage_seconds"]
# The wrong quantity, taken FROM THE RECORD rather than typed: the span from the
# first error to the last one. That is what M5-S4's first attempt reported, and
# it is what an outage looks like to anybody who has not thought about anchors.
now = recovery["error_window"]["span_s"]
recovery["outage_seconds"] = now
rec["recovery"] = recovery
path.write_text(json.dumps(rec, indent=2) + "\n")
print(f"  recovery.outage_seconds {was} -> {now} (the error-window span, derived from the "
      f"record itself; recovered_at {recovery['recovered_at_s']} and first_error "
      f"{recovery['first_error_after_kill_s']} are UNTOUCHED, as are all "
      f"{len(rec['checks'])} recorded checks and the pod uids)")
PY
then
  echo "could not tamper with the record; the drill cannot prove anything." >&2
  exit 2
fi

# ------------------------------------------------------ 2. the gate must go RED
say "2. make verify-m5 — expected RED, naming the arithmetic AND the runbook"
red_log="$(bash scripts/verify_m5.sh 2>&1)"
red_rc=$?
printf '%s\n' "$red_log" | grep -E 'FAIL|\[verify-m5\]'

if [[ "$red_rc" -ne 0 ]]; then
  ok "the gate exited $red_rc — RED against a record whose outage no longer reconciles"
else
  bad "the gate exited 0 — it read a plausible number and believed it"
fi
if printf '%s\n' "$red_log" | grep -q "does not equal recovered_at"; then
  ok "the ANCHOR leg fired: the recorded outage is not recovered_at - first_error, which is the only arithmetic that makes it an outage"
else
  bad "no leg re-derived the outage from its anchors — the gate is reading a summary field it cannot check"
fi
if printf '%s\n' "$red_log" | grep -q "the runbook quotes number(s) that no record holds"; then
  ok "the RUNBOOK leg fired: the operator-facing document and the record now disagree — the second witness, reading a different artifact"
else
  bad "the runbook leg did NOT fire — prose and record may drift apart without the gate noticing"
fi

# "Others still counted": every section that does not read this field must still
# have RUN and passed. A suite that stops at the first failure reports one
# problem and hides forty.
red_oks="$(printf '%s\n' "$red_log" | grep -c 'ok  ')"
if [[ "$red_oks" -ge 40 ]]; then
  ok "$red_oks sub-check line(s) still passed — the gate reports everything, not the first thing"
else
  bad "only $red_oks sub-check(s) still passed — the suite collapsed instead of continuing"
fi
for still_green in "the declared route answers" \
                   "stamped model_version" \
                   "max |offline - online|" \
                   "the headline rate was chosen at" \
                   "a DIFFERENT pod object served afterwards" \
                   "the rollback is TYPED" \
                   "is the winner the M3 bake-off recorded"; do
  if printf '%s\n' "$red_log" | grep -qF "$still_green"; then
    ok "unaffected leg still green: ${still_green}"
  else
    bad "leg '${still_green}' did not pass during the RED run — collateral damage"
  fi
done

# The record's OTHER self-heal facts must still pass their own checks: a leg that
# went red for every field of this file would be a leg that fails on ANY edit
# rather than on a wrong one — M3's and M4's drills assert the same property.
if printf '%s\n' "$red_log" | grep -q "the self-heal drill recorded"; then
  ok "the drill's own recorded checks still passed — the gate went red on the WRONG number, not on the edit"
else
  bad "the self-heal checks leg went red too — the gate fails on any edit rather than on a wrong one"
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
green_log="$(bash scripts/verify_m5.sh 2>&1)"
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
  printf '\033[32m[verify-m5-redteam] PASSED: the M5 gate went RED on ONE rewritten outage\033[0m\n'
  printf '\033[32m                    number — the exact wrong anchor gotcha #75 records — named\033[0m\n'
  printf '\033[32m                    both the arithmetic and the runbook that quotes it, kept\033[0m\n'
  printf '\033[32m                    counting every other sub-check, and returned GREEN when the\033[0m\n'
  printf '\033[32m                    record was restored.\033[0m\n'
  exit 0
fi
printf '\033[31m[verify-m5-redteam] FAILED: %d problem(s) with the gate itself.\033[0m\n' "$PROBLEMS" >&2
exit 1
