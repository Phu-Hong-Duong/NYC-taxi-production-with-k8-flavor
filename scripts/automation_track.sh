#!/usr/bin/env bash
# automation_track.sh — M3-S4's whole automation track, in one ordered command.
#
# THE BUDGET IS DECLARED HERE, BEFORE ANY RESULT EXISTS. Design Review DR-01
# equalises the two tracks in model-FITTING wall-clock seconds and gives each
# 9,000 s; the artisan (S3) spent 3,313.9 s of its share and stopped on its own
# stop rule. This track's 9,000 s is split up front so that no phase can be
# handed more budget after its number is known:
#
#   scout on v1        1,800 s   configs/automl.yaml: time_budget_s (DR-01 pinned it)
#   scout on v2        1,800 s   the same budget, the other feature set
#   sniper on v1       1,500 s   n_trials 60 OR the cap, whichever binds first
#   sniper on v2       1,500 s   ditto
#   two full refits  ~1,700 s   measured, not capped — DR-05 requires full data
#                    --------
#                     ~8,300 s  of 9,000
#
# Stopping a study at trial 34 of 60 because its share ran out is a RESULT and
# the sniper prints which limit bound it. Handing it more afterwards would be
# the thing DR-01 condition 2 forbids by name.
#
# EVERY PHASE IS SKIPPED IF ITS OUTPUT JSON ALREADY EXISTS. This job is ~2.5
# hours long and detached (gotcha #45); if it dies in phase 5, re-running it
# must not re-spend the 3,600 s the two scouts already burned. Re-running a
# phase means deleting its JSON, which is a deliberate act.
#
# A FAILING PHASE DOES NOT ABORT THE REST. A refit that runs out of memory
# should not cost the milestone the study that fed it: each phase's exit code is
# recorded and the script exits non-zero at the end if any phase failed. The
# session that reads the status file then knows exactly which half it has.
#
# Usage:  bash scripts/automation_track.sh            (all phases)
#         OUT_DIR=... bash scripts/automation_track.sh
set -uo pipefail
cd "$(dirname "$0")/.."

OUT_DIR="${OUT_DIR:-automation/runs/m3s4}"
SCOUT_SAMPLE="${SCOUT_SAMPLE:-0.05}"
SNIPER_SAMPLE="${SNIPER_SAMPLE:-0.15}"
SNIPER_BUDGET="${SNIPER_BUDGET:-1500}"
SNIPER_ROUNDS="${SNIPER_ROUNDS:-800}"
mkdir -p "${OUT_DIR}"

FAILED=0
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

phase() {
  local label="$1" out="$2"; shift 2
  echo
  echo "################################################################################"
  if [ -f "${out}" ]; then
    echo "# ${label} — SKIPPED, ${out} already exists (re-running means deleting it)"
    echo "################################################################################"
    return 0
  fi
  echo "# ${label}"
  echo "# $(date -u +%Y-%m-%dT%H:%M:%SZ)  ->  ${out}"
  echo "################################################################################"
  local code=0
  "$@" || code=$?
  if [ "${code}" -ne 0 ]; then
    echo "[track] PHASE FAILED (${code}): ${label} — continuing so the rest of the track survives"
    FAILED=$((FAILED + 1))
  fi
  return 0
}

echo "[track] M3-S4 automation track starting ${STARTED_AT}"
echo "[track] outputs -> ${OUT_DIR}"
echo "[track] DR-03: this track searches HYPERPARAMETERS on feature sets it did not invent"
echo "[track] nothing here promotes; the registry API is absent from every script it runs"

# --- 1-2. the scout, twice: once per feature set (DR-03) ----------------------
for SET in v1 v2; do
  phase "scout on ${SET} (FLAML, ${SCOUT_SAMPLE} sample, configs/automl.yaml budget)" \
    "${OUT_DIR}/scout-${SET}.json" \
    uv run python scripts/automl_scout.py \
      --set "${SET}" --sample-fraction "${SCOUT_SAMPLE}" --out "${OUT_DIR}/scout-${SET}.json"
done

# --- 3-4. the sniper, once per scout verdict ---------------------------------
for SET in v1 v2; do
  if [ ! -f "${OUT_DIR}/scout-${SET}.json" ]; then
    echo "[track] no scout verdict for ${SET} — skipping its sniper (it would centre on nothing)"
    FAILED=$((FAILED + 1))
    continue
  fi
  phase "sniper on ${SET} (Optuna, TPE + MedianPruner, <= ${SNIPER_BUDGET}s)" \
    "${OUT_DIR}/sniper-${SET}.json" \
    uv run python scripts/optuna_sniper.py \
      --set "${SET}" --scout "${OUT_DIR}/scout-${SET}.json" \
      --sample-fraction "${SNIPER_SAMPLE}" --budget-seconds "${SNIPER_BUDGET}" \
      --max-rounds "${SNIPER_ROUNDS}" --out "${OUT_DIR}/sniper-${SET}.json"
done

# --- 5-6. the two contenders, refit on the FULL train months (DR-05) ---------
for SET in v1 v2; do
  if [ ! -f "${OUT_DIR}/sniper-${SET}.json" ]; then
    echo "[track] no study verdict for ${SET} — skipping its refit (nothing to refit)"
    FAILED=$((FAILED + 1))
    continue
  fi
  phase "refit auto-on-${SET} on FULL train months (the bake-off contender)" \
    "${OUT_DIR}/refit-${SET}.json" \
    uv run python scripts/automl_refit.py \
      --verdict "${OUT_DIR}/sniper-${SET}.json" --out "${OUT_DIR}/refit-${SET}.json"
done

# --- the budget ledger DR-01 condition 1 asks for -----------------------------
echo
echo "################################################################################"
echo "# DR-01 budget ledger — measured FITTING seconds, per phase"
echo "################################################################################"
uv run python - "${OUT_DIR}" <<'PY'
import json, pathlib, sys
out = pathlib.Path(sys.argv[1])
total = 0.0
rows = []
for path in sorted(out.glob("*.json")):
    try:
        body = json.loads(path.read_text())
    except Exception as exc:                      # a half-written file is not a number
        rows.append((path.name, f"unreadable: {exc}")); continue
    seconds = body.get("fitting_seconds")
    if seconds is None:
        rows.append((path.name, "no fit_seconds recorded")); continue
    total += float(seconds)
    rows.append((path.name, f"{float(seconds):>10,.1f}s"))
width = max(len(n) for n, _ in rows) if rows else 10
for name, shown in rows:
    print(f"  {name:<{width}}  {shown}")
print(f"\n  {'TOTAL':<{width}}  {total:>10,.1f}s of the 9,000s DR-01 gave this track")
print("  (reading, building matrices and writing the ledger are free on both tracks)")
PY

echo
echo "[track] finished $(date -u +%Y-%m-%dT%H:%M:%SZ); ${FAILED} phase(s) failed"
exit $(( FAILED > 0 ? 1 : 0 ))
