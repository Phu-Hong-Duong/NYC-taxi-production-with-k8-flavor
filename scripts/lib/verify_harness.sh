#!/usr/bin/env bash
# verify_harness.sh — the counting harness every milestone gate shares. SOURCE it.
#
# Consolidated at CU-S3 out of eight byte-identical copies (verify_m2…verify_m9);
# the eight `consume()` bodies normalised to ONE string before a line was moved.
# Nothing here is new: this file is the copies, deleted eight times and written
# once.
#
# WHAT LIVES HERE — the plumbing that counts, and only that:
#   * FAILS / CONSUMED, the two counters a gate's verdict is read off
#   * pass / fail / note / section, the four printers
#   * consume,          which turns a leg's `PASS|`/`FAIL|` lines into counts
#   * expect_verdicts,  which makes a leg that never ran a FAILURE
#
# WHAT DELIBERATELY DOES NOT LIVE HERE, and must not move here later:
#   * A GATE'S LEGS. The legs are the program's arguments and they are
#     deliberately divergent second witnesses — verify-m6 and verify-m7 ask
#     about the same Prometheus in different ways ON PURPOSE. A shared leg
#     would make two witnesses into one.
#   * A GATE'S VERDICT BLOCK. Each gate's GREEN banner names what to SHOW, and
#     the "Show:" lines are §9's own accept language, per milestone.
#   * REPO_ROOT / cd / KUBECTL. `${BASH_SOURCE[0]}` inside a sourced file points
#     at THIS file, so a repo root computed here would be `scripts/`. Each gate
#     computes its own root and sources this file with it — which also means a
#     gate still runs from any working directory.
#
# THE ONE SHAPE THAT IS LOAD-BEARING, and the reason it is a comment and not a
# convention: `consume` MUST be called as `consume < <(...)`, never `... |
# consume`. A pipeline runs the function in a SUBSHELL, so every FAIL it counts
# is discarded at the closing brace and the gate reports GREEN over a red leg.
# That is the M2-S5 lesson, and `tests/unit/test_verify_m{2,3,4}.py` pin the
# idiom at every call site.
#
# Usage, in a gate, after REPO_ROOT is computed:
#     source "$REPO_ROOT/scripts/lib/verify_harness.sh"
#
# It is sourced, never executed: it defines and returns.

FAILS=0
CONSUMED=0
pass() { printf '  \033[32mok  \033[0m %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1" >&2; FAILS=$((FAILS + 1)); }
note() { printf '       %s\n' "$1"; }
section() { printf '\n== %s ==\n' "$1"; }

# Reads `PASS|msg` / `FAIL|msg` lines from a leg and counts them here, so the
# tally lives in exactly one place. Anything else is printed as a note. ALWAYS
# call as `consume < <(...)`: a pipeline would run this in a subshell and throw
# the counters away at the closing brace.
consume() {
  CONSUMED=0
  local line
  while IFS= read -r line; do
    case "$line" in
      "PASS|"*) pass "${line#PASS|}"; CONSUMED=$((CONSUMED + 1)) ;;
      "FAIL|"*) fail "${line#FAIL|}"; CONSUMED=$((CONSUMED + 1)) ;;
      *) note "$line" ;;
    esac
  done
}

# The gates' rule 2, applied to the checker itself: a leg that dies on import
# contributes zero silent passes. Demanding a positive count turns that into a
# failure instead of into nothing.
expect_verdicts() {
  local want="$1" label="$2"
  if [[ "$CONSUMED" -lt "$want" ]]; then
    fail "$label emitted $CONSUMED verdict(s), expected at least $want — the check did not run"
  fi
}
