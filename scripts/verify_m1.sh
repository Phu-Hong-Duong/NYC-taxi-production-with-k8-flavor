#!/usr/bin/env bash
# verify_m1.sh — the M1 gate, executable. BLUEPRINT §9/M1, quoted:
#
#   "Accept when: v1's M1 gate (byte-identical rebuild, counted rejections,
#    red-teamed corrupt-file refusal) AND the contract review minutes exist AND
#    prior_art.md has >=6 verdicts AND `dbt build` is green including tests (with
#    one test red-teamed on a seeded bad fixture, then passing) AND the Metabase
#    boards render from marts in the browser. Show: EDA report + prior-art table
#    + the two Metabase boards."
#
# Design rule inherited from verify_m0.sh: every check observes the THING, not a
# proxy for it. "The JSON file defining a dashboard exists in git" is a proxy;
# "the running Metabase holds that dashboard AND one of its cards executes and
# returns rows" is the thing. Where both are cheap we do both, because they fail
# differently.
#
# Two of the negative legs are RED-TEAMS, not assertions about happy paths: this
# gate fails if the corrupt-file refusal stops refusing, or if the dbt tests stop
# being able to go red. A green suite that cannot go red is not evidence.
#
# Leg 1 deletes and rebuilds ~1 GB of processed parquet, because the
# byte-identity claim is worthless when checked against data that was never
# re-derived. There is no fast mode and no skip flag: a gate with one is a gate
# that runs with it.
#
# MEASURED 2026-08-17 (M1-S5), because a guess would have been wrong: the whole
# gate is **~98 s** green end to end on this machine (the estimate written while
# building it was "15-25 minutes" — off by an order of magnitude, which is worth
# recording, since the fear of a slow gate is exactly what tempts people to add
# the skip flag). A failing run costs ~115 s: leg 7 spends up to 60 s waiting for
# a Metabase that is supposed to already be up.
#
# Prints one line per sub-check and exits nonzero if ANY fails — it keeps going
# rather than stopping at the first, so one run tells you everything broken.
#
# Usage: scripts/verify_m1.sh        (via `make verify-m1`)
set -uo pipefail   # deliberately NOT -e: a failing check must be counted, not fatal

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")
METABASE_URL="${METABASE_URL:-http://localhost:3030}"
SANDBOX="$REPO_ROOT/.verify_m1_sandbox"

FAILS=0
pass() { printf '  \033[32mok  \033[0m %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1" >&2; FAILS=$((FAILS + 1)); }
note() { printf '       %s\n' "$1"; }
section() { printf '\n== %s ==\n' "$1"; }

cleanup() { rm -rf "$SANDBOX"; }
trap cleanup EXIT

# ------------------------------------------------- 1. byte-identical rebuild --
section "1. data: byte-identical rebuild from DVC-pinned raw (v1's M1 gate)"
note "deleting and rebuilding data/processed/ — this is the slow leg, by design"
# Every assertion below is anchored on a string rebuild_proof.sh actually prints.
# The first draft of this leg grepped for 'YES' (the script prints lowercase
# 'yes') and for 'dvc status' (it prints "second witness — DVC's own view"), so
# it reported "0 output(s) byte-identical" and PASSED. A check that parses
# nothing and passes is worse than one that fails: it is a green light wired to
# no sensor. Hence the explicit count > 0 below.
if rebuild_log="$(bash scripts/rebuild_proof.sh 2>&1)"; then
  # Anchored on the proof's OWN count, not on a grep for lines ending in 'yes'.
  # The first version counted every such line in the whole log and so also
  # counted the duckdb reconciliation's per-month rows — it printed "16" for 8
  # outputs, and M2-S1's second derived tree plus its second reconciliation
  # would have pushed it to 25. Right for the wrong reason is still a sensor
  # pointing somewhere else; the number quoted below is now the number the
  # proof hashed.
  identical="$(printf '%s\n' "$rebuild_log" \
    | sed -n 's/^\[rebuild-proof\] \([0-9]\+\) output(s), all byte-identical: True$/\1/p')"
  if [[ -n "$identical" && "$identical" -gt 0 ]]; then
    pass "rebuild-proof GREEN — $identical output(s) byte-identical after a full re-derive"
  else
    fail "rebuild-proof exited 0 but its table shows $identical identical output(s)"
    note "$(printf '%s\n' "$rebuild_log" | tail -12)"
  fi
  # The second witness, computed by different code from different metadata. If
  # rebuild_proof.sh ever stops asking DVC, this line stops finding the answer.
  if printf '%s\n' "$rebuild_log" | grep -q "second witness"; then
    pass "the proof carried its SECOND witness (DVC's own view), not just our own hashes"
  else
    fail "rebuild-proof no longer consults DVC — one witness agreeing with itself is not evidence"
  fi
else
  fail "rebuild-proof FAILED (data/processed/ is not a pure function of pinned raw + this repo)"
  note "$(printf '%s\n' "$rebuild_log" | tail -15)"
fi

# --------------------------------------------------- 2. counted rejections ----
section "2. data: rejections are COUNTED and attributed, never silent"
missing_reports=0
for f in data/processed/*/*.parquet; do
  [[ -f "${f%.parquet}.rejections.json" ]] || missing_reports=$((missing_reports + 1))
done
months="$(ls data/processed/*/*.parquet 2>/dev/null | wc -l)"
if [[ "$months" -gt 0 && "$missing_reports" -eq 0 ]]; then
  pass "every one of $months processed month(s) has its rejection report beside it"
else
  fail "$missing_reports of $months processed month(s) have no rejection report"
fi

# The report's shape, read from a real file rather than assumed: `rules` is a
# LIST of {name, rejected_by, matched, params}. `rejected_by` attributes each
# dropped row to exactly ONE rule (so it sums to the drop count); `matched`
# counts every rule a row tripped (so it sums higher). Confusing the two is the
# easy mistake, and it makes the reconciliation fail for a reason that looks like
# data corruption.
rej_summary="$(uv run python - <<'PY' 2>&1
import json, pathlib
rows_in = rows_out = 0
rules = {}
for p in sorted(pathlib.Path("data/processed").rglob("*.rejections.json")):
    r = json.loads(p.read_text())
    rows_in += r["rows_in"]; rows_out += r["rows_out"]
    for rule in r["rules"]:
        rules[rule["name"]] = rules.get(rule["name"], 0) + rule["rejected_by"]
attributed = sum(rules.values())
dropped = rows_in - rows_out
print(f"rows_in={rows_in:,} rows_out={rows_out:,} dropped={dropped:,} "
      f"attributed={attributed:,} rules={len(rules)}")
print("OK" if dropped == attributed else "MISMATCH")
PY
)"
if printf '%s\n' "$rej_summary" | grep -q '^OK$'; then
  pass "every dropped row is attributed to a named rule — $(printf '%s\n' "$rej_summary" | head -1)"
else
  fail "dropped rows do not equal rows attributed to rules (silent drops)"
  note "$rej_summary"
fi

# ------------------------------------- 3. RED-TEAM: corrupt-file refusal -------
section "3. RED-TEAM: a corrupt source file is REFUSED (not repaired, not skipped)"
# Sandboxed: the fixture is written into a throwaway raw_dir declared by a
# throwaway config, so the gate can prove the refusal without ever putting a
# corrupt byte near data/raw. The month is one the splits already know.
rm -rf "$SANDBOX"; mkdir -p "$SANDBOX/raw" "$SANDBOX/processed"
uv run python - <<'PY' >/dev/null
import pathlib, yaml
cfg = yaml.safe_load(open("configs/data.yaml"))
cfg["source"]["raw_dir"] = ".verify_m1_sandbox/raw"
cfg["source"]["processed_dir"] = ".verify_m1_sandbox/processed"
cfg["source"]["manifest_path"] = ".verify_m1_sandbox/raw_manifest.json"
pathlib.Path(".verify_m1_sandbox/data.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
name = cfg["source"]["filename_pattern"].format(month="2019-01")
# Parquet's magic footer is "PAR1". These bytes are not that, and never were.
pathlib.Path(".verify_m1_sandbox/raw", name).write_bytes(b"this is not a parquet file\n" * 64)
PY
refusal="$(uv run python -m taxi_mlops.data ingest --config .verify_m1_sandbox/data.yaml --month 2019-01 2>&1)"
refusal_rc=$?
wrote="$(find "$SANDBOX/processed" -name '*.parquet' 2>/dev/null | wc -l)"
if [[ "$refusal_rc" -ne 0 ]]; then
  pass "the corrupt month exits nonzero (rc=$refusal_rc)"
else
  fail "the corrupt month exited 0 — a refusal that does not refuse"
fi
if printf '%s\n' "$refusal" | grep -q 'CorruptSourceError'; then
  pass "refusal is TYPED (CorruptSourceError), not a stack trace from deep in pyarrow"
else
  fail "no CorruptSourceError in the output — the refusal is untyped"
  note "$(printf '%s\n' "$refusal" | tail -5)"
fi
if printf '%s\n' "$refusal" | grep -q 'yellow_tripdata_2019-01.parquet'; then
  pass "the refusal NAMES the offending file"
else
  fail "the refusal does not name the file it refused"
fi
if [[ "$wrote" -eq 0 ]]; then
  pass "nothing was written — no half month left behind (write-to-temp-then-rename)"
else
  fail "$wrote parquet file(s) written despite the refusal"
fi

# --------------------------------------------------- 4. dbt build + tests -----
section "4. marts: dbt build green INCLUDING its tests"
if dbt_log="$(SKIP_PUBLISH=1 bash scripts/marts.sh 2>&1)"; then
  # dbt prefixes every line with a timestamp and ANSI colour, so the summary is
  # never at column 0 — anchoring on '^Done\.' silently matched nothing and this
  # branch printed "dbt build PASS — no summary line" while passing.
  summary="$(printf '%s\n' "$dbt_log" | grep -oE 'Done\. PASS=[0-9]+ WARN=[0-9]+ ERROR=[0-9]+ SKIP=[0-9]+.*' | tail -1)"
  if [[ -z "$summary" ]]; then
    fail "dbt build exited 0 but printed no 'Done. PASS=…' summary — nothing was parsed"
  elif [[ "$summary" == *"ERROR=0"* ]]; then
    pass "dbt build PASS — $summary"
  else
    fail "dbt build summary reports errors: $summary"
  fi
  ntests="$(printf '%s\n' "$dbt_log" | grep -cE 'PASS (test|not_null|unique|accepted)')"
  if [[ "$ntests" -ge 1 ]]; then
    pass "the build ran data tests interleaved with the models ($ntests test line(s))"
  else
    fail "no dbt test lines in the build output — models built, nothing was tested"
  fi
else
  fail "dbt build FAILED"
  note "$(printf '%s\n' "$dbt_log" | tail -15)"
fi

# ------------------------------ 5. RED-TEAM: the dbt tests can still FAIL ------
section "5. RED-TEAM: seeded bad fixture makes a NAMED dbt test go red"
# marts.sh inverts its own exit code under RED_TEAM=1: a GREEN build with
# impossible trips in it means the tests are not testing, and the script says so.
redteam_log="$(RED_TEAM=1 bash scripts/marts.sh 2>&1)"
redteam_rc=$?
if [[ "$redteam_rc" -eq 0 ]]; then
  pass "marts-redteam exits 0 (its exit code is INVERTED: the dbt build went red as it must)"
else
  fail "marts-redteam exit $redteam_rc — the seeded impossible trips did NOT turn a test red"
  note "$(printf '%s\n' "$redteam_log" | tail -15)"
fi
if printf '%s\n' "$redteam_log" | grep -q 'accepted_range_trips_clean_trip_duration_minutes'; then
  pass "the red test is NAMED (accepted_range on trip_duration_minutes), not an anonymous failure"
else
  fail "the red-team output does not name which test failed"
fi
# And it must leave the local layer green again — a red-team that poisons the
# workspace is a red-team you stop running.
if tail_log="$(SKIP_PUBLISH=1 bash scripts/marts.sh 2>&1)"; then
  pass "the workspace is GREEN again after the red-team (the fixture did not survive it)"
else
  fail "dbt is still red after marts-redteam — the fixture was left behind"
  note "$(printf '%s\n' "$tail_log" | tail -10)"
fi

# --------------------------------------- 6. marts published to the Postgres ---
section "6. marts: published to the ONE Postgres, row counts reconciled"
declare -A EXPECTED_FROM_INGEST
ingest_total="$(uv run python - <<'PY'
import json, pathlib
print(sum(json.loads(p.read_text())["rows_out"]
          for p in pathlib.Path("data/processed").rglob("*.rejections.json")))
PY
)"
psql_marts() { "${KUBECTL[@]}" -n platform exec -i postgres-0 -- psql -U postgres -d marts -tAc "$1" 2>/dev/null; }
for mart in trips_clean zone_hourly_stats monthly_kpis rejections_by_rule; do
  n="$(psql_marts "SELECT count(*) FROM marts.$mart")"
  if [[ -n "$n" && "$n" =~ ^[0-9]+$ && "$n" -gt 0 ]]; then
    pass "marts.$mart is queryable in Postgres — $(printf "%'d" "$n") rows"
    EXPECTED_FROM_INGEST[$mart]="$n"
  else
    fail "marts.$mart is missing or empty in the Postgres (got '${n:-<nothing>}')"
  fi
done
published="${EXPECTED_FROM_INGEST[trips_clean]:-}"
if [[ -n "$published" && "$published" == "$ingest_total" ]]; then
  pass "marts.trips_clean row count == the ingest total the rejection reports claim ($(printf "%'d" "$ingest_total"))"
else
  fail "marts.trips_clean has '${published:-<nothing>}' rows, the ingest reports claim '$ingest_total'"
fi

# ---------------------------------------------- 7. Metabase + the two boards --
section "7. BI: Metabase answers on its declared route and holds both boards"
if docker port mlops-taxi-control-plane 2>/dev/null | grep -q '^30300/tcp'; then
  pass "kind publishes hostPort 3030 -> nodePort 30300 (declared route, not a port-forward)"
else
  fail "the control-plane container publishes no 30300 mapping — cluster predates the kind-config row"
fi
code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$METABASE_URL/api/health" || true)"
if [[ "$code" == "200" ]]; then
  pass "$METABASE_URL/api/health -> 200 (the URL a human opens)"
else
  fail "$METABASE_URL/api/health returned '$code'"
fi
# The app-db must be the one Postgres. An H2 file-db would work perfectly until
# the first rollout, then take the boards with it.
mb_db="$("${KUBECTL[@]}" -n metabase get deploy metabase \
          -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="MB_DB_TYPE")].value}' 2>/dev/null)"
if [[ "$mb_db" == "postgres" ]]; then
  pass "Metabase's app-db is postgres (no H2 file-db — it would die with the pod)"
else
  fail "Metabase MB_DB_TYPE is '${mb_db:-<unset>}', expected 'postgres'"
fi
mb_tables="$("${KUBECTL[@]}" -n platform exec -i postgres-0 -- \
  psql -U postgres -d metabase -tAc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" 2>/dev/null)"
if [[ -n "$mb_tables" && "$mb_tables" =~ ^[0-9]+$ && "$mb_tables" -gt 10 ]]; then
  pass "the 'metabase' database in the one Postgres holds its app schema ($mb_tables tables)"
else
  fail "the 'metabase' database holds ${mb_tables:-<nothing>} public tables — app-db is elsewhere"
fi
if boards_log="$(uv run python scripts/metabase_boards.py --verify 2>&1)"; then
  printf '%s\n' "$boards_log" | grep -E 'ok|FAIL'
  pass "both boards verified through the Metabase API (existence AND a card that RUNS)"
else
  fail "the Metabase board check failed"
  note "$(printf '%s\n' "$boards_log" | tail -20)"
fi

# ------------------------------------------------------- 8. the documents -----
section "8. the documents the gate names"
minutes="$(ls docs/rituals/*data*contract*review*.md docs/rituals/*contract*.md 2>/dev/null | sort -u | head -5)"
if [[ -n "$minutes" ]]; then
  pass "contract review minutes exist: $(printf '%s' "$minutes" | tr '\n' ' ')"
else
  fail "no data-contract-review minutes under docs/rituals/"
fi
verdicts="$(grep -coE '\b(adopt|differ|surpass)\b' docs/prior_art.md 2>/dev/null || echo 0)"
verdict_rows="$(grep -cE '^\|.*(ADOPT|DIFFER|SURPASS)' docs/prior_art.md 2>/dev/null || echo 0)"
if [[ "$verdict_rows" -ge 6 ]]; then
  pass "docs/prior_art.md carries $verdict_rows verdict rows (gate wants >= 6)"
else
  fail "docs/prior_art.md carries $verdict_rows verdict rows, gate wants >= 6 (loose matches: $verdicts)"
fi
kpi_ids="$(grep -coE '^### KPI-[0-9]+' docs/kpi_definitions.md 2>/dev/null || echo 0)"
if [[ "$kpi_ids" -ge 5 ]]; then
  pass "docs/kpi_definitions.md defines $kpi_ids KPIs by id (gate wants >= 5)"
else
  fail "docs/kpi_definitions.md defines $kpi_ids KPIs by id, gate wants >= 5"
fi
if [[ -s docs/eda_report.md ]]; then
  pass "docs/eda_report.md present ($(wc -l < docs/eda_report.md) lines) — the gate's 'Show'"
else
  fail "docs/eda_report.md is missing or empty"
fi

# --------------------------------------------- 9. the marts boundary law ------
section "9. the marts boundary law (ADR-009, gotcha #22)"
if leak="$(grep -rn "analytics" src/taxi_mlops/ 2>/dev/null)"; then
  fail "model code references the analytics layer — train/serve skew through the back door"
  note "$leak"
else
  pass "grep -r 'analytics' src/taxi_mlops/ is EMPTY — marts serve humans, not the model"
fi

# ------------------------------------------------------------------ verdict ---
echo
if [[ "$FAILS" -eq 0 ]]; then
  printf '\033[32m[verify-m1] GREEN — every M1 sub-check passed.\033[0m\n'
  echo "            Show: EDA report docs/eda_report.md · prior art docs/prior_art.md"
  echo "                  Metabase boards $METABASE_URL (Data health · KPI board)"
  exit 0
fi
printf '\033[31m[verify-m1] RED — %d sub-check(s) failed.\033[0m\n' "$FAILS" >&2
exit 1
