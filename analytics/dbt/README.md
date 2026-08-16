# analytics/dbt — the DA's gold marts (M1-S4; role:DA, MLOps hat for the publish)

`make marts` is the whole path: **dbt build (models AND tests) → publish to the
one Postgres**. `make marts-redteam` is its twin — it proves the tests can go
red. Neither is a hand-typed command against a database.

## The four marts, and why there are four

| mart | grain | rows (2019-01…08) | materialised |
|---|---|---|---|
| `trips_clean` | one accepted trip | 56,127,878 | view in DuckDB, **table** in Postgres |
| `zone_hourly_stats` | month × split × pickup zone × hour | 44,792 | table |
| `monthly_kpis` | month | 8 | table |
| `rejections_by_rule` | month × rejection rule | 80 | table |

BLUEPRINT §9/M1-S6 names the first three. `rejections_by_rule` was added
deliberately, and the reason is a boundary rather than a preference: M1-S5's
data-health board has to render **KPI-03** (rejections attributed per rule),
Metabase can only query Postgres, and `ingest_rejections` lives in the DuckDB
analyst layer — an embedded engine no served BI tool can reach. Its grain is
(month, rule), which is neither of the other two, so it could not be a column on
either. Without it the KPI is defined, computable, and unrenderable.

## Where the data comes from — and the one thing this project would not do

dbt attaches `data/analyst.duckdb` **read-only** and sources the views by name.
It would have been shorter to `read_parquet('data/processed/**')` straight from
dbt. That would also have given the project a **second definition** of what
`split` and `month` mean, sitting one directory away from the first — and the
repo has already paid for that lesson twice (the port family, the split months).
Attaching means a view renamed in `taxi_mlops.data.analyst` breaks `dbt build`
loudly instead of quietly disagreeing with it.

The same rule governs KPI-04's documented TLC domains: they live in
`configs/data.yaml:analyst.known_domains` and reach dbt as a `--vars` payload
that `scripts/marts.sh` reads from that file. There is deliberately **no default
value** — a missing var fails the build, because an empty domain list would
report 100% of rows as undocumented and look like a catastrophic drift event.

## How the marts reach Postgres

Postgres is **ClusterIP-only** by design (CLAUDE.md's port family annotates 5432
"in-cluster only"). So the publish opens no TCP connection: DuckDB writes CSV to
stdout and `kubectl exec -i` pipes it into `psql \copy` inside the pod.
Measured 2026-08-16: **2,000,000 rows / 104 MB in 1.9s (~55 MB/s)**.

Each mart lands in a `<name>__staging` table and is swapped in inside one
transaction, so a reader sees the old table or the new one and never a
half-loaded one. Re-running is a no-op in the sense that matters: same end
state, every time.

Rejected alternatives, recorded so nobody re-litigates them at 3am: a NodePort
for 5432 (publishes a database on the laptop and contradicts the port family),
`kubectl port-forward` (a background process the recipe would have to babysit),
and DuckDB's `postgres` extension (downloaded at run time — an unpinned
dependency in the build path, which the MLOps charter refuses).

**The honest cost of publishing `trips_clean` at full grain: ~13 GB in the
Postgres volume and several minutes on every `make marts`.** It is published
anyway because a BI layer that cannot reach trip grain is not self-service, and
because the alternative — quietly publishing an aggregate under the name of a
fact table — would be a mart that lies about what it is. M4, which runs this as
a Flyte task monthly, should revisit it as an incremental model.

## The tests, and the fixture that must turn them red

`dbt build` runs 34 data tests interleaved with the models, so a red test stops
the publish and a failed upstream is never handed to a downstream model that
then passes. They are the DA's QA layer — **parallel to, not replacing**, the
DE's pandera contracts: pandera decides what may enter `data/processed/`, these
decide what may be published to a human.

`accepted_range` is our own generic test (`macros/test_accepted_range.sql`)
rather than `dbt_utils`: this program is $0 and pins every dependency, and one
twenty-line macro we own is cheaper to trust than a package fetched from dbt Hub
inside the build path. `dbt_utils`' `unique_combination_of_columns` is likewise
twelve lines in `tests/assert_zone_hourly_grain_is_unique.sql`.

`make marts-redteam` unions the out-of-contract fixture in `seeds/redteam/` and
**inverts the exit code**: a green build with two impossible trips in it means
the tests are not testing, and the script says so and fails. See
`seeds/redteam/README.md` for why the fixture is checked in rather than
hand-edited once.

## Boundary law

These marts serve **humans** (ADR-009, gotcha #22). Model code never imports
them — `grep -r "analytics" src/taxi_mlops/` stays empty, and
`tests/unit/test_marts.py::test_model_code_never_imports_a_mart` fails if it
does not. A mart aggregate that looks model-worthy graduates through the feature
dossier and the shared features path, never by direct import.

From M4 the build+publish runs as the tail task of the monthly Flyte pipeline;
until then `make marts` is the path.
