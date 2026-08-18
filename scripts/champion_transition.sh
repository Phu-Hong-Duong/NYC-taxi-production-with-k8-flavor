#!/usr/bin/env bash
# champion_transition.sh — the ordered chain a champion transition owes, in one
# command that either finishes it or says exactly where it stopped.
#
# WHY THIS IS A SCRIPT AND NOT A PARAGRAPH IN A HANDOFF.
# When the alias moves, four artifacts that describe "the champion" instantly
# describe a model nobody serves: the published row-level predictions, the
# analyst views over them, the gold marts, and the error board on top of those.
# M3's kickoff names the repair and its ORDER; the M3 risk table lists
# "champion transition leaves predictions/mart/board/memo describing the OLD
# model" as F-012's exact failure shape. An order that lives in prose is an
# order somebody performs from memory at 3am. This file is that order, executed.
#
# THE ORDER IS NOT NEGOTIABLE, for the same reason `make data`'s is not:
#
#   1. promote      the alias moves — everything after it reads the alias
#   2. predictions  re-score val+test with the NEW champion (F-012's floor
#                   check guards the write: the floor the champion was GATED
#                   against must re-score to the version's own tag, or nothing
#                   is published)
#   3. duckdb       the analyst views, incl. the predictions-vs-holdout
#                   reconciliation that exits 1 if a row count disagrees
#   4. marts        dbt build (models AND tests) → publish to Postgres; the
#                   error segments must still roll up to the evaluator's
#                   KPI-09/KPI-10 or the build fails
#   5. boards       the Metabase cards, converged from checked-in JSON
#   6. memo numbers PRINTED, not written — the M3 section of the error memo is
#                   prose a human owes; this step puts the live figures in the
#                   log so that human is not also re-running queries
#
# WHAT IT REFUSES TO DO TWICE. Step 1 is skipped when the alias ALREADY points
# at the winner's run. That is not politeness — `scripts/bakeoff_m3.py` re-reads
# the incumbent every invocation, so a second promoting run would re-judge the
# four losing contenders against the NEW incumbent and overwrite bakeoff.json's
# verdict column with verdicts that were never the ones taken. Steps 2–6 are
# idempotent by construction and are re-run unconditionally, which is what makes
# this script the right thing to relaunch after a failure in step 4.
#
# Usage:  make champion-transition
#         make champion-transition DRY_RUN=1     (preflight only — moves nothing)
#         make detach NAME=m3s5-transition ROLE=executor TARGET=champion-transition
set -uo pipefail
cd "$(dirname "$0")/.."

BAKEOFF_JSON="${BAKEOFF_JSON:-automation/runs/m3s5/bakeoff.json}"
DRY_RUN="${DRY_RUN:-0}"

step() { printf '\n==============================================================\n[transition] %s — %s\n==============================================================\n' "$1" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"; }

# ---------------------------------------------------------------- preflight ---
# Everything below reads the bake-off's recorded row set, never a number typed
# into this file: the winner, its run id and its feature set are facts the
# measurement produced.
[ -f "${BAKEOFF_JSON}" ] || {
  echo "[transition] REFUSED: ${BAKEOFF_JSON} does not exist. There is no measured" >&2
  echo "[transition] winner to transition to. Run 'make bakeoff' first." >&2
  exit 2
}

WINNER_LINE="$(uv run python scripts/champion_transition_winner.py "${BAKEOFF_JSON}")" || exit 2
IFS=$'\t' read -r WINNER_LABEL WINNER_NAME WINNER_RUN WINNER_SET WINNER_VERDICT <<<"${WINNER_LINE}"
[ -n "${WINNER_RUN:-}" ] || { echo "[transition] REFUSED: could not read a winner out of ${BAKEOFF_JSON}" >&2; exit 2; }

echo "[transition] bake-off winner : ${WINNER_LABEL} (${WINNER_NAME})"
echo "[transition] its run         : ${WINNER_RUN}"
echo "[transition] its feature set : ${WINNER_SET}"
echo "[transition] its verdict     : ${WINNER_VERDICT}"

if [ "${WINNER_VERDICT}" != "PROMOTE" ]; then
  echo "[transition] REFUSED: the winner's gate verdict is ${WINNER_VERDICT}, not PROMOTE."
  echo "[transition] The alias does not move, and nothing downstream of it is refreshed."
  echo "[transition] That is a result, not a failure — see docs/bakeoff_m3.md §6."
  exit 2
fi

CONFIGURED_SET="$(uv run python -c "import yaml,pathlib;print(yaml.safe_load(pathlib.Path('configs/train.yaml').read_text())['features']['version'])")"
if [ "${CONFIGURED_SET}" != "${WINNER_SET}" ]; then
  echo "[transition] REFUSED: configs/train.yaml says features.version=${CONFIGURED_SET} but the" >&2
  echo "[transition] winner eats ${WINNER_SET}. That line moves as PART of the promotion" >&2
  echo "[transition] (M3-S3's law) — commit it, then run this again." >&2
  exit 2
fi

ALIAS_RUN="$(uv run python scripts/champion_transition_winner.py --alias-run 2>/dev/null || true)"
echo "[transition] @champion now      : ${ALIAS_RUN:-<unset>}"

if [ "${DRY_RUN}" != "0" ]; then
  echo
  echo "[transition] DRY_RUN — preflight only. Nothing was promoted, re-scored or published."
  echo "[transition] The chain this would run, in order:"
  echo "[transition]   1 promote ${WINNER_NAME} (skipped when @champion already resolves to it)"
  echo "[transition]   2 make predictions   3 make duckdb   4 make marts   5 make boards"
  echo "[transition]   6 scripts/error_memo_numbers.py (printed, for the memo's M3 section)"
  exit 0
fi

# ------------------------------------------------------------ 1. the alias ---
step "1/6 promote the bake-off winner"
if [ "${ALIAS_RUN}" = "${WINNER_RUN}" ]; then
  echo "[transition] SKIPPED — @champion already resolves to the winner's run ${WINNER_RUN}."
  echo "[transition] Re-running the promoting bake-off would re-judge the four losing"
  echo "[transition] contenders against the NEW incumbent and overwrite the verdicts that"
  echo "[transition] were actually taken. The refresh steps below still run."
else
  echo "[transition] @champion currently resolves to run '${ALIAS_RUN:-<unset>}' — promoting."
  make bakeoff BAKEOFF_ARGS=--promote-winner || {
    echo "[transition] FAILED at step 1 (promotion). Nothing downstream ran; the incumbent" >&2
    echo "[transition] is still serving and every published artifact still describes it." >&2
    exit 1
  }
fi

# --------------------------------------------------- 2..5 the refresh chain ---
step "2/6 make predictions — re-score with the new champion (F-012's floor check guards the write)"
make predictions || { echo "[transition] FAILED at step 2 (predictions)." >&2; exit 1; }

step "3/6 make duckdb — analyst views + the predictions/holdout reconciliation"
make duckdb || { echo "[transition] FAILED at step 3 (duckdb)." >&2; exit 1; }

step "4/6 make marts — dbt build (models AND tests) + publish to Postgres"
make marts || { echo "[transition] FAILED at step 4 (marts)." >&2; exit 1; }

step "5/6 make boards — converge the Metabase cards"
make boards || { echo "[transition] FAILED at step 5 (boards)." >&2; exit 1; }

# ------------------------------------------------------- 6. the memo's ink ---
step "6/6 error-memo numbers — PRINTED for the human who owes the M3 section"
echo "[transition] These are the live figures for docs/error_memo_m2.md's dated M3"
echo "[transition] section. The prose is a human's; re-running the queries is not."
uv run python scripts/error_memo_numbers.py || {
  echo "[transition] step 6 failed — the refresh itself is DONE, only the printout is missing." >&2
  exit 1
}

printf '\n[transition] COMPLETE %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "[transition] Still owed by a human, and NOT done here:"
echo "[transition]   · the dated M3 section in docs/error_memo_m2.md (numbers above)"
echo "[transition]   · 'make verify-m2' — its 'champion right now' and memo-twin legs are"
echo "[transition]     the tripwires this refresh exists to satisfy, and the memo must be"
echo "[transition]     written BEFORE that leg can pass."
