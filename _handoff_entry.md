## Session 2026-08-16 (t) — M1-S4: four marts in the one Postgres, a debt closed on a volume that was already old, and the first `unchanged` this project has ever printed

### State
on-track — EXECUTOR (**Opus 5, claude-opus-5**, stated first line), role:DA with
the MLOps hat for the publish plumbing, one story. **PR #8 MERGED on green CI**
(`lint-test pass 41s`; the runner log confirms `114 passed in 19.59s` and
`All checks passed!`), merge commit `b1ce17a`, story commit `a2ed135`, lineage
proven: `git branch -r --contains a2ed135` → `origin/main` (after
`git fetch --prune`). Tree clean and level with origin; story branch deleted both
sides. **Next: EXECUTOR runs M1-S5** (Metabase + the two boards + `verify-m1`) —
the M1 exit story.

### Staleness check of (s)'s Next — reality matched, nothing to reconcile
`git status --short --branch` → `## main...origin/main`, clean at `0fa5f56` ·
`kubectl get nodes` → 3/3 Ready (v1.36.1, ~95m old) · MLflow/MinIO/Postgres all
`Running` · 8 processed months on disk under their splits · `data/analyst.duckdb`
present (274,432 bytes) · `dbt-duckdb` genuinely absent from `pyproject.toml`, as
(s) said. Checked before being relied on.

### Done (every leg with the command and what came back)

- **`make marts` is real, and it is two halves in one order.** `dbt build`
  (models AND tests, interleaved) → publish. First run: **PASS=39 WARN=0 ERROR=0
  SKIP=0** over 4 models, 34 data tests and 1 seed in **3.24s**, then

  ```
  [marts] publishing trips_clean …        COPY 56127878
  [marts] publishing zone_hourly_stats …  COPY 44792
  [marts] publishing monthly_kpis …       COPY 8
  [marts] publishing rejections_by_rule … COPY 80
  ```

  `COPY 56127878` is **exactly** the ingest total M1-S1 wrote and M1-S2
  reconciled. Counts read back identical from both engines (DuckDB
  `main_marts.*` and `psql -d marts`).

- **Second `make marts`: 220.4s, exit 0, identical counts** — and the atomic
  swap was watched happening. Mid-run, `pg_stat_user_tables` showed
  `trips_clean` still serving **56,127,878** rows while `trips_clean__staging`
  filled beside it; the staging table then vanished into the rename. A reader
  sees the old mart or the new one, never a half-loaded one. The NOTICEs differ
  between runs exactly as they should (run 1 skipped `DROP TABLE trips_clean`
  four times; run 2 only the staging names).

- **THE NUMBER OF THE STORY — two independent implementations landed on the same
  integer.** `monthly_kpis.kpi_04_undocumented_rows` counts distinct rows
  carrying a value the TLC dictionary does not describe, computed from
  `trips_clean` against the domains in `configs/data.yaml`. Its eight monthly
  values:

  ```
  104,498 + 80,636 + 74,718 + 73,666 + 60,486 + 55,926 + 44,034 + 33,422
      = 527,386
  ```

  **527,386 is exactly M1-S3's figure** — including the subtlety that summing
  the `unknown_domain_values` view instead gives 527,610, because 219 trips
  carry both `VendorID = 5` and `payment_type = 0`. Same story for KPI-08:
  318+300+380+395+442+424+451+421 = **3,131**, the EDA's excluded-row count to
  the row. Neither was engineered to match; they came by different routes on
  different days. **New observation the mart makes visible and nobody had:** the
  undocumented-value rate falls **monotonically, 1.3778% (Jan) → 0.5616%
  (Aug)** — the opposite direction to KPI-02's rejection rate, which rises over
  the same months. M1-S3 recorded that the four codes appear in all 8 months; it
  did not record that their share is halving.

- **The red team is a command, and it found something the plan got wrong.**
  `make marts-redteam` unions two checked-in impossible trips (999.5 min and
  0.2 min) behind a dbt var and **inverts the exit code** — a green build with
  those rows in it means the tests are not testing. Observed:

  ```
  Done. PASS=19 WARN=0 ERROR=1 SKIP=19 NO-OP=0 REUSED=0 TOTAL=39
  ERROR: in test accepted_range_trips_clean_trip_duration_minutes__120__1
    Got 2 results, configured to fail if != 0
  ```

  **The 19 SKIPs were not the prediction.** `seeds/redteam/README.md` first
  claimed the reconciliation test would also go RED (the mart would hold two
  rows the ingest never claimed). It does not — it is skipped, along with both
  aggregate models and all their tests, because `dbt build` interleaves tests
  with models and **never hands a failing fact to what is built on it**. That is
  a stronger guarantee than the one predicted, and the README now says so rather
  than keeping the tidier wrong sentence. The run also restores the local DuckDB
  layer to green before exiting (the failed build had left `trips_clean`
  carrying the fixture) and never touches Postgres.

- **D-002 CLOSED, proven on a volume that was already 117 minutes old.**
  `scripts/postgres_databases.sh`, invoked as step **[5/7]** of
  `scripts/deploy_platform.sh` — never by hand. PGDATA's `PG_VERSION` is stamped
  `2026-08-16 15:47:03`; `marts` was created at 17:44. Both runs, verbatim:

  ```
  RUN 1 — volume initialised 15:47, 'marts' absent
  [pg-db] mlflow: before = role present, database present
  [pg-db] ok  mlflow owner=mlflow
  [pg-db] marts:  before = role absent, database absent
  [pg-db] ok  marts owner=marts
  [pg-db] 2 database(s) converged (no password printed, by design)

  RUN 2 — same command again
  [pg-db] mlflow: before = role present, database present
  [pg-db] ok  mlflow owner=mlflow
  [pg-db] marts:  before = role present, database present
  [pg-db] ok  marts owner=marts
  ```

  `mlflow` is deliberately IN the list and printed `role present, database
  present` on both runs — untouched, and the free proof that the guards are real
  no-ops rather than untested branches. `SELECT datname || ' owner=' ||
  pg_get_userbyid(datdba)` → `marts owner=marts`, `mlflow owner=mlflow`.
  `CREATE DATABASE` cannot sit in a transaction or a DO block, hence the
  `\gexec` + `WHERE NOT EXISTS` form. No password reaches argv — credentials go
  to psql on stdin as `\set` variables, because argv shows up in `ps` inside the
  pod and in a kubectl audit log.

- **F-003 CLOSED by its own condition (a), in one attempt as instructed.**
  `kubectl apply -f infra/manifests/postgres.yaml -v=9` prints the PATCH body
  kubectl actually sends, and it is exactly one field:

  ```
  {"spec":{"volumeClaimTemplates":[{"metadata":{"name":"data"},"spec":{
     "accessModes":["ReadWriteOnce"],"resources":{"requests":{"storage":"8Gi"}}}}]}}
  ```

  **Cause:** `volumeClaimTemplates` is an ATOMIC list under strategic-merge patch
  (no patchMergeKey), so kubectl compares the whole list against the live object
  — into which the apiserver has defaulted `apiVersion: v1`, `kind:
  PersistentVolumeClaim`, `spec.volumeMode: Filesystem` and `status: {phase:
  Pending}` (read back live). Our manifest omitted all four, so desired could
  never equal live. **Fix:** state them. Three applies in a row then printed
  `configured (server dry run)` → `configured` → **`statefulset.apps/postgres
  unchanged`** — the first `unchanged` in this project's life. Nothing was
  disturbed: generation 1 = observedGeneration, pod `creationTimestamp
  2026-08-16T15:46:45Z`, `restarts=0`, `kubectl diff -f` silent.
  `storageClassName` stays UNSET — the apiserver does not write it back, so
  naming kind's local-path would cost portability for nothing.

- **Four marts, not three, and the fourth is argued rather than slipped in.**
  `trips_clean` 56,127,878 · `zone_hourly_stats` 44,792 · `monthly_kpis` 8 ·
  **`rejections_by_rule` 80**. BLUEPRINT names the first three. The fourth
  exists because M1-S5's data-health board must render **KPI-03**, Metabase can
  only query Postgres, and `ingest_rejections` lives in DuckDB — an embedded
  engine no served BI tool can reach (BLUEPRINT §3 says exactly that). Its grain
  is (month, rule), so it could not have been a column on either aggregate.
  Without it the KPI is defined, computable and unrenderable.

- **Tests + lint.** 21 new unit tests (`tests/unit/test_marts.py`), each
  docstring naming the failure it prevents. `uv run pytest tests/unit -q` →
  **114 passed** (was 93), cluster-free and dbt-free. `uv run ruff check src
  tests scripts pipelines` → `All checks passed!`. CI ran them for real:
  `114 passed in 19.59s`.

- **Docs/ledgers**: CLAUDE.md gains the pins (dbt-core 1.12.2, dbt-duckdb
  1.11.0), three command rows and a "gold marts" section · `docs/kpi_definitions.md`
  gains a table naming the mart COLUMN for every KPI id, so M1-S5's cards do not
  have to guess · `analytics/dbt/README.md` rewritten · `ledgers/debt.md` D-002
  **closed** with its evidence · `ledgers/findings.md` F-003 **closed** with its
  transcript · `ledgers/deployments.md` gains the publish row · LEARNING_GUIDE
  field note written BEFORE this handoff (field-note law).

### Decisions (craft-level, inside scope, each with its undo)

- **`trips_clean` is published to Postgres at FULL GRAIN, and the cost is stated
  rather than hidden.** ~**13 GB** in the Postgres volume, ~**23 GB peak**
  mid-swap (the old table and the staging copy exist at once, with autovacuum
  working on the one about to be dropped), and ~3.5 minutes of every `make
  marts`. Node disk after: 783 G free of 1007 G. It is published anyway because
  a BI layer that cannot reach trip grain is not self-service, and because
  publishing an aggregate under a fact table's name would be a mart that lies
  about what it is. **Undo:** drop it from `MARTS=()` in `scripts/marts.sh` and
  Metabase loses trip-grain self-service. **For M4** (which runs this monthly as
  a Flyte task): this wants an incremental materialisation, and the 23 GB peak is
  the number that argues for it.
- **The publish opens no port.** DuckDB → CSV on stdout → `kubectl exec -i` →
  `psql \copy`. Measured **before** designing around it: 2,000,000 rows / 104 MB
  in **1.9s (~55 MB/s)** — an order of magnitude better than the estimate that
  would have killed full-grain publishing. Rejected, with reasons in the script
  header: a NodePort for 5432 (publishes a database on the laptop, contradicts
  the port family), `kubectl port-forward` (a background process the recipe must
  babysit), DuckDB's `postgres` extension (downloaded at run time — an unpinned
  dependency inside the build path).
- **dbt SOURCES the analyst layer, attached read-only; no model reads parquet.**
  `read_parquet` would have been shorter and would have given the repo a second
  definition of `split` and `month` one directory from the first. Same rule for
  KPI-04's domains: read from `configs/data.yaml` into `--vars`, with **no
  default** — an absent var must fail the build, because an empty domain list
  reports 100% undocumented and looks like a catastrophe rather than a bug.
- **`accepted_range` and the grain check are ours, not `dbt_utils`.** A $0,
  every-version-pinned program does not fetch a package from dbt Hub inside its
  build path for one macro. **Undo:** add `packages.yml`, delete two files.
- **`mlflow` is inside D-002's DATABASES list.** The recipe describes the whole
  server; `10-mlflow.sh` becomes the empty-volume fast path rather than a second,
  divergent source of truth. It also makes every run print a live no-op proof.
- **`.env` grew an ADDITIVE branch.** Volume-baked secrets stay in `REQUIRED` and
  are never regenerated; a NEW consumer's credential (marts now, Metabase at S5)
  is generated and appended, because it is not yet inside any volume. Hard-failing
  instead would have left the operator hand-editing a secrets file — the manual
  step the recipe exists to remove.

### Defects / Surprises
- **dbt 1.12 refuses to start if the telemetry opt-out is set in both places.**
  `config:` in profiles.yml + `flags:` in dbt_project.yml → `Do not specify
  both`. Belt-and-braces broke the build. The opt-out now lives in
  `dbt_project.yml` + `DO_NOT_TRACK`/`DBT_SEND_ANONYMOUS_USAGE_STATS` in
  `scripts/marts.sh`, pinned by a test. Worth knowing: `uv add dbt-duckdb` pulled
  **`snowplow-tracker`** in as a dependency, and the first (failing) run also
  emitted `Error uploading artifacts to artifact ingestion API` — gotcha #32's
  dbt sibling is real, not theoretical.
- **`Catalog "analyst" does not exist` on the first publish.** `trips_clean` is a
  VIEW over the attached analyst database, and a view is a stored QUERY — the
  database it reads is not carried inside the file. dbt attaches it via
  profiles.yml; every other reader must too. Fixed in `scripts/marts_export.py`
  with the reason written next to the ATTACH.
- **My own test had the bug this repo keeps warning about, again.**
  `test_model_quality_kpis_are_not_computed_in_sql` failed — because
  `monthly_kpis.sql`'s own COMMENT explaining why there is no `kpi_09_*` column
  matched the regex looking for one. The assertion fired for the wrong reason.
  Fixed by stripping SQL comments first, which is what the test meant anyway:
  read the SELECT list, not the argument for it. Exactly the shape of M1-S3's
  KPI-10 bug, one session later.
- A second self-inflicted one: the deploy-order test compared against the first
  occurrence of `community-charts/mlflow`, which is the `helm repo add` line, not
  the install. Now anchored on `upgrade --install mlflow`.
- **No walls hit** (nothing needed three attempts). **Nothing parked. No fork
  opened** — every choice above sits inside the kickoff's scope with a stated
  undo, and none touched a gate, a threshold or a budget.

### Next
1. **EXECUTOR: M1-S5** per `docs/milestones/M1_KICKOFF.md` — the M1 exit story:
   the **planned cluster rebuild first** (3030 hostPort→nodePort twins + the
   drift unit test; kind publishes ports at CREATE time only), then
   `make deploy-metabase` (one container, pinned image, **app-db in Postgres via
   D-002's mechanism** — add a `metabase:metabase:METABASE_DB_PASSWORD` line to
   `DATABASES` in `scripts/postgres_databases.sh` and an entry to `ADDITIVE` in
   `scripts/platform_secrets.sh`; that is the whole change), the two boards, and
   `make verify-m1` implemented + red-teamed once.
   **Starting state:** cluster `mlops-taxi` UP, database `marts` holding 4
   published marts (13 GB), tree clean on `main` at `b1ce17a`.
2. **Four things S5 should carry in.** (a) The rebuild **wipes the marts** with
   the PVC — that is fine and is a free re-proof: `make marts` brings them back
   from the recipe alone, and the fresh volume exercises D-002's other path.
   Budget ~4 minutes for it. (b) **Re-verify MLflow holds only `Default`** before
   destroying (kickoff precondition). (c) F-003's remaining condition: the fix
   was proved on an EXISTING object — after the rebuild, apply the postgres
   manifest twice and confirm the second says `unchanged`; if it does not,
   reopen F-003 with that transcript. (d) `docs/kpi_definitions.md` now names the
   mart column for every KPI id — the board cards should cite that table, and
   **KPI-09/KPI-10 must appear on no card** (they are columns nowhere, by test).
3. **The boards have everything they need in Postgres**: data-health from
   `monthly_kpis` (KPI-01/02/04/05) + `rejections_by_rule` (KPI-03, and its three
   permanently-zero rules must still render — a rule you cannot see cannot be
   seen to start firing); KPI board from `monthly_kpis` + `zone_hourly_stats`,
   with **KPI-08's excluded-row count on the same card as its value**.
4. **For ARCH at the M1 boundary**: F-005 still waits (M1-S3's scope judgement,
   with reasons). F-006/F-007 are open, owned by MLE, landing M2/M3. New for the
   pile: the 23 GB peak argues that M4's Flyte marts task should be incremental,
   not full-refresh.
5. Standing, PO's hands, non-blocking: AWAITING_PO 2026-08-16-2 (allowlist).

