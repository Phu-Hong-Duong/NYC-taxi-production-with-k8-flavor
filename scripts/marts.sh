#!/usr/bin/env bash
# marts.sh — `make marts`: build the dbt gold marts, then publish them into the
# one Postgres where Metabase can reach them (BLUEPRINT §9/M1-S6).
#
# TWO HALVES, IN THIS ORDER, AND THE ORDER IS THE DESIGN:
#   1. dbt build   — models AND tests. A failing test stops the script, so a
#                    mart that failed QA can never reach a board. `dbt build`
#                    rather than `dbt run && dbt test` for exactly that reason:
#                    build interleaves them per-model, so a broken upstream is
#                    never fed to a downstream model that then also passes.
#   2. publish     — materialise each mart in Postgres.
#
# HOW THE DATA REACHES POSTGRES, AND WHY NOT THE OBVIOUS WAY. Postgres is
# ClusterIP-only by design (CLAUDE.md's port family annotates 5432 "in-cluster
# only"; nothing of ours publishes a database on the host). So the publish does
# not connect over TCP at all: DuckDB writes CSV to stdout and `kubectl exec -i`
# pipes it into `psql \copy` inside the pod. Measured 2026-08-16: 2,000,000 rows
# (104 MB) through that pipe in 1.9s, ~55 MB/s. Rejected alternatives, recorded
# so nobody re-litigates them at 3am: a NodePort for 5432 (contradicts the port
# family and publishes a database on the laptop), `kubectl port-forward` (a
# background process the recipe must then babysit), and DuckDB's `postgres`
# extension (an extension downloaded at run time, i.e. an unpinned dependency in
# the build path — MLOps charter).
#
# IDEMPOTENCE IS FULL REFRESH IN A TRANSACTION. Each mart is loaded into a
# `<name>__staging` table and swapped in at COMMIT, so a reader either sees the
# old table or the new one and never a half-loaded one, and a publish that dies
# halfway leaves the previous mart serving. Re-running is a no-op in the only
# sense that matters: same end state, every time.
#
# Usage: scripts/marts.sh                 (build + publish)
#        SKIP_PUBLISH=1 scripts/marts.sh  (build + test only; no cluster needed)
#        RED_TEAM=1 scripts/marts.sh      (union the out-of-contract fixture —
#                                          the build MUST go red; never publishes)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DBT_DIR="$REPO_ROOT/analytics/dbt"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"
NAMESPACE="${POSTGRES_NAMESPACE:-platform}"
POD="${POSTGRES_POD:-postgres-0}"
KUBECTL=(kubectl --context "${KUBE_CONTEXT:-kind-mlops-taxi}")
SKIP_PUBLISH="${SKIP_PUBLISH:-0}"
RED_TEAM="${RED_TEAM:-0}"

# gotcha #32: the third place the telemetry is turned off. dbt_project.yml and
# profiles.yml cover project-aware runs; these cover everything else dbt does.
export DO_NOT_TRACK=1
export DBT_SEND_ANONYMOUS_USAGE_STATS=false
export DBT_PROFILES_DIR="$DBT_DIR"

# The tables the publish moves, in dependency-free order (each is standalone in
# Postgres). `trips_clean` is first because it is the expensive one — if the
# pipe is going to fail, fail before the cheap ones have been swapped.
MARTS=(trips_clean zone_hourly_stats monthly_kpis rejections_by_rule error_segments)

# ---- 1. known_domains: ONE definition, passed in, never copied into SQL ------
# monthly_kpis computes KPI-04 against the documented TLC domains. Those live in
# configs/data.yaml:analyst.known_domains and are read from there — a copy
# pasted into a .sql file would be the twins failure the port family and the
# split months already taught this repo (CLAUDE.md).
#
# M2-S4 adds a second one on the same terms: `tolerance_minutes` is KPI-12's
# tolerance and it lives in configs/train.yaml (evaluate.tolerance_minutes),
# where KPI-10 already reads it. A `5.0` typed into error_segments.sql would be a
# rate whose definition disagrees with the model's the day the DA and the SRE
# argue about the SLO — which is the M5 conversation this number exists for.
DBT_VARS="$(python3 - "$REPO_ROOT/configs/data.yaml" "$REPO_ROOT/configs/train.yaml" <<'PY'
import json, sys, yaml
cfg = yaml.safe_load(open(sys.argv[1]))
train = yaml.safe_load(open(sys.argv[2]))
print(json.dumps({
    "known_domains": cfg["analyst"]["known_domains"],
    "tolerance_minutes": float(train["evaluate"]["tolerance_minutes"]),
}))
PY
)"
GREEN_VARS="$DBT_VARS"
if [[ "$RED_TEAM" == "1" ]]; then
  DBT_VARS="$(python3 -c "
import json,sys
v = json.loads(sys.argv[1]); v['red_team'] = True; print(json.dumps(v))" "$DBT_VARS")"
  echo "== RED TEAM: the out-of-contract fixture is UNIONED IN — this build MUST fail =="
fi

# ---- 1b. the one upstream this build cannot fabricate ------------------------
# `error_segments` sources the analyst layer's `predictions` view, which exists
# only after a champion has been scored (`make predictions`, M2-S4). dbt's own
# failure for a missing source is a DuckDB "table does not exist" three frames
# deep in a compiled model — true, and useless. Say the sentence instead.
if [[ ! -f "$REPO_ROOT/data/analyst.duckdb" ]]; then
  echo "[marts] FAIL: no data/analyst.duckdb — run \`make data\` first." >&2
  exit 1
fi
if ! uv run python -c "
import duckdb, sys
con = duckdb.connect('$REPO_ROOT/data/analyst.duckdb', read_only=True)
names = {r[0] for r in con.execute('SHOW TABLES').fetchall()}
sys.exit(0 if {'predictions', 'prediction_runs'} <= names else 1)
"; then
  echo "[marts] FAIL: the analyst layer has no 'predictions' view." >&2
  echo "[marts] The error_segments mart aggregates the champion's published rows." >&2
  echo "[marts] Run:  make predictions  &&  make duckdb" >&2
  exit 1
fi

# ---- 2. dbt build (models + tests, interleaved) ------------------------------
#
# --no-partial-parse IS LOAD-BEARING, and it cost this project a broken build to
# learn (gotcha #38, M2-S4). dbt caches a parsed manifest in
# `target/partial_parse.msgpack`, and the node paths in it — `root_path` — are
# recorded RELATIVE TO THE DIRECTORY DBT WAS RUN FROM. One hand-run of `dbt`
# from the repo root therefore poisons every subsequent `make marts`: the cache
# says `root_path: analytics/dbt`, this script runs from `analytics/dbt`, and
# the seed load fails with `No files found that match the pattern
# "analytics/dbt/seeds/redteam/redteam_bad_trips.csv"` — naming a file that
# plainly exists, from a script whose own cwd is correct. Measured cost of
# turning the cache off on this project: nothing (5.74s vs 5.91s, i.e. inside
# the noise — there are five models). A build that can be broken by where
# somebody once stood is not idempotent, which is the property this whole script
# is built around.
#
# It is spelled out at each of the three call sites rather than hoisted into a
# shell array, deliberately: gotcha #35 is a test that parses an array in this
# very file and truncated it at the first `)` inside a comment.
echo "== [1/2] dbt build (models AND tests; a red test stops the publish) =="
cd "$DBT_DIR"
if [[ "$RED_TEAM" == "1" ]]; then
  # The failure IS the result here, so the exit code is inverted deliberately:
  # a GREEN build under the red-team fixture means the tests are not testing.
  if uv run dbt build --no-partial-parse --vars "$DBT_VARS"; then
    echo "[marts] RED-TEAM FAILED: dbt build was GREEN with out-of-contract rows in it." >&2
    echo "[marts] The tests are not testing. Do not ship these marts." >&2
    exit 1
  fi
  echo
  echo "[marts] RED-TEAM PASSED: dbt build went RED with the fixture in place (see the"
  echo "[marts] named failure above). Nothing was published — the publish lives in the"
  echo "[marts] half of this script the red-team branch never reaches."
  echo
  # Leave no contaminated state behind. The failed run still CREATED the
  # trips_clean view with the fixture unioned in, and a local DuckDB layer
  # holding two impossible trips is a trap for whoever queries it next. Rebuild
  # green before exiting — three seconds, and the red-team stops being something
  # somebody has to remember to clean up after.
  echo "[marts] restoring the local DuckDB layer to green …"
  uv run dbt build --no-partial-parse --vars "$GREEN_VARS" >/dev/null
  echo "[marts] restored. Postgres was never touched; run 'make marts' to republish."
  exit 0
fi
uv run dbt build --no-partial-parse --vars "$DBT_VARS"
cd "$REPO_ROOT"

if [[ "$SKIP_PUBLISH" == "1" ]]; then
  echo "[marts] SKIP_PUBLISH=1 — built and tested in DuckDB; nothing published."
  exit 0
fi

# ---- 3. publish to the one Postgres -----------------------------------------
echo
echo "== [2/2] publish to Postgres (over kubectl exec — 5432 is never published) =="

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[marts] FAIL: no $ENV_FILE — run \`make deploy-platform\` first (it owns .env)" >&2
  exit 1
fi
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a
: "${MARTS_DB_USER:?missing in .env — run make deploy-platform}"

# The database itself is D-002's job, not this script's: it is created by
# scripts/postgres_databases.sh from the deploy recipe. Fail loudly rather than
# creating it here, or there would be two places that make databases.
if ! "${KUBECTL[@]}" -n "$NAMESPACE" exec -i "$POD" -- \
      psql -tAc "SELECT 1 FROM pg_database WHERE datname = 'marts'" \
      -U postgres -d postgres | grep -q 1; then
  echo "[marts] FAIL: database 'marts' does not exist." >&2
  echo "[marts] It is created by scripts/postgres_databases.sh — run \`make deploy-platform\`." >&2
  exit 1
fi

psql_marts() {
  "${KUBECTL[@]}" -n "$NAMESPACE" exec -i "$POD" -- \
    psql -v ON_ERROR_STOP=1 -U postgres -d marts "$@"
}

# Schema `marts` inside database `marts`: Metabase is pointed at one schema, and
# a mart that appears is a mart that was published — not one that happened to
# land in `public` alongside whatever else ever touches this database.
psql_marts -q -c "CREATE SCHEMA IF NOT EXISTS marts AUTHORIZATION \"$MARTS_DB_USER\";"

published=()
for mart in "${MARTS[@]}"; do
  echo "[marts] publishing $mart …"
  # DuckDB owns the type mapping: it writes the CREATE TABLE for the staging
  # table from the mart's own schema, so a column added upstream arrives here
  # without a second schema to maintain (the twins lesson, again).
  ddl="$(uv run python "$REPO_ROOT/scripts/marts_export.py" ddl "$DBT_DIR/marts.duckdb" "$mart")"

  psql_marts -q -c "DROP TABLE IF EXISTS marts.\"${mart}__staging\";"
  psql_marts -q -c "CREATE TABLE marts.\"${mart}__staging\" (
  $ddl
);"

  # CSV over the pipe. `\copy` (client side) rather than `COPY ... FROM STDIN`
  # so psql reads OUR stdin instead of needing server-side file access. Both
  # ends stream: nothing of this ever lands on disk as a temp file.
  uv run python "$REPO_ROOT/scripts/marts_export.py" csv "$DBT_DIR/marts.duckdb" "$mart" \
    | "${KUBECTL[@]}" -n "$NAMESPACE" exec -i "$POD" -- \
        psql -v ON_ERROR_STOP=1 -U postgres -d marts \
        -c "\\copy marts.\"${mart}__staging\" FROM STDIN WITH (FORMAT csv, NULL '')"

  # The swap: old table out, staging in, in ONE transaction. A reader sees one
  # or the other, never a half-loaded mart.
  psql_marts -q -c "BEGIN;
    DROP TABLE IF EXISTS marts.\"${mart}\";
    ALTER TABLE marts.\"${mart}__staging\" RENAME TO \"${mart}\";
    ALTER TABLE marts.\"${mart}\" OWNER TO \"$MARTS_DB_USER\";
  COMMIT;"
  published+=("$mart")
done

# Indexes the two boards will actually use. Created after the swap because the
# swap replaces the table (and with it any index), and because loading first and
# indexing after is faster than the reverse.
psql_marts -q -c "
  CREATE INDEX IF NOT EXISTS trips_clean_month_idx        ON marts.trips_clean (month);
  CREATE INDEX IF NOT EXISTS trips_clean_pickup_zone_idx  ON marts.trips_clean (\"PULocationID\");
  CREATE INDEX IF NOT EXISTS zone_hourly_month_zone_idx   ON marts.zone_hourly_stats (month, pickup_zone);
"

echo
echo "[marts] published ${#published[@]} mart(s) into database 'marts', schema 'marts':"
psql_marts -c "SELECT relname AS mart, n_live_tup AS approx_rows
               FROM pg_stat_user_tables WHERE schemaname = 'marts' ORDER BY relname;"
echo "[marts] done. Metabase (M1-S5) reads exactly these tables."
