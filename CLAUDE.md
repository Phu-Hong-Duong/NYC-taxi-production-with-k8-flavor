# CLAUDE.md — working memory for mlops-nyc-taxi (Crosstown ETA & Reliability Program)

<!-- PROTOCOL WIRING — user action required, pick ONE per your adopted master:
     v2.0-style:  @~/.claude/templates/UNIVERSAL_PROTOCOL.md
     v1.x-style:  copy UNIVERSAL_PROTOCOL.md to this repo's root.
     Flagged rather than auto-wired: adopting a protocol version is the user's
     call, not the scaffold's. -->

PROTOCOL_MODE: learning
<!-- Rationale: mockup — no real credentials, users, or live service. User
     confirmed in the Session-1 kickoff prompt (docs/PROMPTS.md). Production
     signals appearing later (real cloud, real data) reopen this. -->

## Project in one line
Enterprise-simulated MLOps program on local kind: NYC taxi ETA model through
Flyte → MLflow (+ FLAML scout × Optuna sniper) → KServe, with SLOs/gamedays,
drift loop, DVC, Feast — seven chartered roles, ledgers, fresh-eyes review.
Spec: docs/BLUEPRINT.md (v2). Constitution: docs/org/ORG.md + ROLES.md.

## Environment facts
- Machine: Windows 11 + WSL2 (Ubuntu) + Docker Desktop, 64 GB RAM (user-stated
  2026-08-12; grant ~48 GB to WSL via .wslconfig — VERIFY at M0 with `free -h`).
- Repo location: must be inside WSL2 fs (`/home/...`). Check `pwd` before anything.
- Canonical execution home (2026-08-16): `/home/longt/NYC-taxi-production-with-k8-flavor`
  (WSL Ubuntu, user `longt`; pre-staged by bootstrap). The Windows clone
  `C:\Users\longt\PycharmProjects\NYC-taxi-production-with-k8-flavor` is the
  PO's viewing copy — the chain NEVER runs there.
- Observed 2026-08-16 (bootstrap preflight): `.wslconfig` 48GB WRITTEN, inert
  until `wsl --shutdown` (was 31Gi); Docker WSL integration was OFF; TLS from
  WSL clean (Sectigo — no AV interception that day). Go-live checklist:
  AWAITING_PO.md 2026-08-16-1.
- Observed 2026-08-16 (M0-S1, after the PO ran go-live block A): `free -h`
  47Gi ✅ · `docker ps` answers in WSL ✅ · `gh auth status` ✅ (Phu-Hong-Duong,
  scopes gist/read:org/repo/workflow). Toolchain is sudo-free in
  `~/.local/bin` (kind, helm, uv installed by S1; kubectl pre-existed).
- Session permission mode = the SAFER allowlist (PO choice A4,
  `.claude/settings.local.json` + `--permission-mode acceptEdits`). The list
  is starter-sized: `ls`, `chmod`, `mkdir`, `printenv`, `tar`… are NOT on it,
  and Claude cannot widen it itself (writes to settings files are refused by
  the harness). S1 worked inside it via the allowlisted `python3` (gotcha #27);
  the paste to extend it is AWAITING_PO 2026-08-16-2 (non-blocking). The launch
  MODE itself now propagates down the chain (gotcha #26, fixed 2026-08-16 in
  `automation/next_session.sh` by a parallel ARCH session).
- Observed 2026-08-17 (M1-S5 boot): the host had restarted and **Docker Desktop
  was not running**, which presents as `kubectl: command not found` —
  `/usr/local/bin/kubectl` is a symlink into `/mnt/wsl/docker-desktop/cli-tools/`
  and that mount only exists while the daemon does (gotcha #34). Recovery is one
  launch + ~15s; kind's node containers restart themselves and the platform comes
  back with them (`make verify-m0` GREEN 18/18, nothing re-deployed).
- Kaspersky AV on host — gotcha #9 before debugging any TLS error.
- Cluster: kind, config at infra/kind/kind-config.yaml. $0 budget — nothing leaves
  this machine; no cloud credentials exist in this project.
- Predecessor repo (Ashford / Home Credit) may be connected read-only for
  reference. NEVER write into it; its lessons arrive via BLUEPRINT §3 and gotchas.

## Version pins (OBSERVED values — re-verify live at M0/M3 and overwrite; blueprint values are hypotheses)
| Component | Pinned | Observed on | Source |
|---|---|---|---|
| Docker Desktop engine | 29.6.2 (build dfc4efb) | 2026-08-16 | `docker --version` (M0-S1, in WSL) |
| claude CLI (Windows) | 2.1.233 | 2026-08-16 | `claude --version` (bootstrap preflight) |
| gh CLI (Windows) | 2.96.0 | 2026-08-16 | `gh --version` (bootstrap preflight) |
| gh CLI (WSL) | 2.46.0 (apt, Ubuntu build) | 2026-08-16 | `gh --version` (M0-S1) |
| claude CLI (WSL) | present & live — version string UNREAD (see note) | 2026-08-16 | this session ran through it; `claude --version` is not on the PO allowlist |
| kind | 0.32.0 | 2026-08-16 | `kind --version` (M0-S1; installed to `~/.local/bin`) |
| kind node image | `kindest/node:v1.36.1@sha256:3489c7674813ba5d8b1a9977baea8a6e553784dab7b84759d1014dbd78f7ebd5` | 2026-08-16 | **CONFIRMED at M0-S2** — a real `kind create cluster` printed `Ensuring node image (kindest/node:v1.36.1)` and `docker inspect mlops-taxi-control-plane` returned this exact digest, matching S1's binary extraction. Now pinned EXPLICITLY per node in `infra/kind/kind-config.yaml` (verified by a from-scratch rebuild), so a future kind upgrade cannot change Kubernetes versions silently |
| Kubernetes (kind nodes) | v1.36.1 · containerd 2.3.1 · Debian 13 (trixie) | 2026-08-16 | `kubectl get nodes -o wide` on the live cluster (M0-S2) |
| kubectl | v1.36.1 (kustomize v5.8.1) | 2026-08-16 | `kubectl version --client` (M0-S1; pre-existing in WSL) |
| helm | v3.19.0 (git 3d8990f, go1.24.7) | 2026-08-16 | `helm version` (M0-S1; installed to `~/.local/bin`) |
| uv | 0.12.5 | 2026-08-16 | `uv --version` (M0-S1; installed to `~/.local/bin`) |
| GNU make | 4.4.1 | 2026-08-16 | `make --version` (M0-S1) |
| git (WSL) | 2.53.0 | 2026-08-16 | `git --version` (M0-S1) |
| Python (system, WSL) | 3.14.4 | 2026-08-16 | `python3 --version` (M0-S1) — NOT the project interpreter |
| Python (project, uv-managed) | 3.12.14 | 2026-08-16 | `.python-version` = 3.12, pinned at M0-S1 for parity with ci.yml's `uv python install 3.12` |
| ruff | 0.16.3 | 2026-08-16 | `uv add --dev ruff` resolution (M0-S1); exact pin lives in `uv.lock` |
| pytest | 9.1.1 | 2026-08-16 | `uv add --dev pytest` resolution (M0-S1); exact pin lives in `uv.lock` |
| MinIO chart | `minio/minio` **5.4.0** (repo https://charts.min.io/) | 2026-08-16 | `helm list -A` on the live cluster (M0-S3); pinned in `scripts/deploy_platform.sh` |
| MinIO server image | `quay.io/minio/minio:RELEASE.2024-12-18T13-15-44Z` | 2026-08-16 | chart-pinned; read back from `kubectl -n platform get deploy minio -o jsonpath=…` |
| MinIO client (`mc`) image | `quay.io/minio/mc:RELEASE.2024-11-21T17-21-54Z` | 2026-08-16 | chart default (bucket/user Jobs) |
| MLflow chart | `community-charts/mlflow` **1.11.4** | 2026-08-16 | `helm list -A` (M0-S3); pinned in `scripts/deploy_platform.sh` |
| MLflow (app) | **3.15.1**, image `burakince/mlflow:3.15.1` | 2026-08-16 | `kubectl -n mlflow get deploy mlflow -o jsonpath=…`. BLUEPRINT §7 hypothesised 3.13.0 — the live chart is ahead; observation wins |
| MLflow db-check init image | `busybox:1.38.0` | 2026-08-16 | chart default, rendered by `helm template` |
| Postgres | **16.11** (Debian bookworm), image pinned by digest `postgres@sha256:a2420e9555e2224583fe84d0bb3f0b967e69354ae3a0be55a9c14e251388c4eb` | 2026-08-16 | `select version()` in the running pod; digest from `docker pull postgres:16.11-bookworm`. NOT helm — see `infra/manifests/postgres.yaml` header |
| pandas | **3.0.5** | 2026-08-16 | `uv add pandas` resolution (M1-S1). A 3.x major — `astype("string")` reports as `str`; exact graph in `uv.lock` |
| pyarrow | 25.0.1 | 2026-08-16 | `uv add pyarrow` (M1-S1). The parquet WRITER whose options `configs/data.yaml:write` pins — S2's byte-identity proof rests on this pair |
| pandera | 0.32.1 (`import pandera.pandas as pa`) | 2026-08-16 | `uv add pandera` (M1-S1) |
| numpy | 2.5.2 | 2026-08-16 | transitive via pandas (M1-S1) |
| PyYAML | 6.0.3 | 2026-08-16 | `uv add pyyaml` (M1-S1) — configs/*.yaml are read by code from M1 on |
| duckdb | 1.5.5 | 2026-08-16 | `uv add duckdb` (M1-S2). The analyst layer is VIEWS in this engine — it copies no rows |
| dvc | 3.67.1 | 2026-08-16 | `uv add dvc` (M1-S2). A runtime dep, not dev: `make data` invokes it. **Analytics disabled at init** — see gotcha #32 |
| dbt-core | **1.12.2** | 2026-08-16 | `uv run dbt --version` (M1-S4). Note it pulled **snowplow-tracker 1.1.0** in — the telemetry client. Opt-out is `flags.send_anonymous_usage_stats: false` in `dbt_project.yml` + `DO_NOT_TRACK=1` (gotcha #32's dbt sibling, now pinned by a test) |
| dbt-duckdb | **1.11.0** | 2026-08-16 | `uv run dbt --version` (M1-S4). A runtime dep, not dev: `make marts` invokes it |
| Metabase | **v0.63.13**, image pinned by TAG AND DIGEST `metabase/metabase:v0.63.13@sha256:6e188e7068c6e9cf7b24480ada80f335bca9135765764ee827245f44ffa9eace` | 2026-08-17 | `docker pull` (M1-S5). Newest stable at pin time (Docker Hub tag list read live; `v0.58-lts` was the conservative alternative and stays the 3-attempt-wall fallback). Plain manifest, not the chart — `infra/manifests/metabase.yaml` header says why |
| TLC yellow parquet (2019-01…08) | 8 files, sha256-pinned in `data/raw_manifest.json` | 2026-08-16 | `make ingest`; e.g. 2019-01 = `3ad95f39…26d`, 110,439,634 bytes. Manifest is timestamp-free by design: a diff = the bytes moved |
| lightgbm | **4.7.0** | 2026-08-17 | `uv add lightgbm` (M2-S2). Needs an OpenMP runtime this host does not ship — see gotcha #37 and debt D-004 |
| mlflow-skinny (CLIENT) | **3.15.1** — an EXACT match to the deployed server | 2026-08-17 | `uv add "mlflow-skinny>=3.15,<4"` (M2-S2). **NOT `mlflow`**: the full package pins `pandas<3` against our `pandas>=3.0.5`, and an unbounded `uv add mlflow` silently resolved to **1.27.0**, two majors behind the server (gotcha #36). We run the server in-cluster and only ever needed the client |
| scikit-learn | 1.9.0 | 2026-08-17 | `uv add scikit-learn` (M2-S2). Not used by v1's model; it is a declared dep because its wheel vendors the `libgomp` the OpenMP shim borrows (gotcha #37) — an accidental dependency made explicit |
| boto3 / botocore | 1.43.72 | 2026-08-17 | `uv add boto3` (M2-S2). Required because the tracking server does NOT proxy artifacts (`proxiedArtifactStorage: false`): the CLIENT writes to MinIO itself — gotcha #5 |
| scipy | 1.18.0 | 2026-08-17 | transitive via scikit-learn (M2-S2) |
| pyshp | **3.1.6** | 2026-08-17 | `uv add pyshp` (M3-S2). Pure-Python shapefile reader — zero transitive deps, which is why it beat geopandas for one lookup table |
| pyproj | **3.7.2** | 2026-08-17 | `uv add pyproj` (M3-S2). Does the ESRI-WKT → WGS84 transform for the zone centroids. **Checked at add time: pandas stayed 3.0.5 and numpy 2.5.2** — gotcha #36's silent-downgrade shape did NOT occur (3 packages touched, one of them the project itself) |
| FLAML | **2.6.0** | 2026-08-17 | `uv add "flaml>=2"` (M3-S4). Imports LightGBM at module scope, so `ensure_openmp()` must run BEFORE `from flaml import AutoML` (gotcha #37's third consumer) |
| Optuna | **4.9.0** | 2026-08-17 | `uv add "optuna>=4"` (M3-S4). Pulled `alembic` 1.19.1 + `sqlalchemy` 2.0.52 + `colorlog`/`greenlet` in. Note `optuna.integration` is NOT here — Optuna 4 moved it to a separate distribution, which is why `taxi_mlops.tuning.fit` writes its own pruning callbacks |
| XGBoost | **3.4.1** | 2026-08-17 | `uv add "xgboost>=3"` (M3-S4). The second OpenMP consumer the kickoff named as a risk: **discharged** — it trains under the shim's `LD_LIBRARY_PATH` with no extra work (proved live). It drags **`nvidia-nccl-cu13` 2.31.2 (241 MB)** in as a hard dep on linux — no GPU here, and it is never loaded |
| psycopg | **3.3.4** (`psycopg[binary]`) | 2026-08-17 | `uv add "psycopg[binary]>=3"` (M3-S4). Optuna's Postgres driver. SQLAlchemy's bare `postgresql://` still means psycopg**2**, so every DSN this repo builds says `postgresql+psycopg://` explicitly (pinned by a test) |
| **The M3-S4 add touched pandas/numpy not at all** | pandas 3.0.5 · numpy 2.5.2 · scikit-learn 1.9.0 unchanged | 2026-08-17 | Checked at add time against gotcha #36's silent-downgrade shape. Four packages requested, 12 installed, 1 uninstalled (the project itself, rebuilt) — no core downgrade |

## The data contract (M1-S1) — where the rules actually live
Knobs: `configs/data.yaml` (source/contract/clean/write). Split months are NOT
there — they live in `configs/train.yaml` and are read from it, so the two files
can never disagree (the port-family twins lesson, applied before it bit).
- **One cast, one place**: `taxi_mlops.data.contract.cast` — gotcha #7. Nothing
  else in the codebase may `astype` a TLC column.
- **Structure refuses, rows get counted**: a missing/renamed/unknown column
  refuses the whole month (SchemaEventError); a bad ROW is counted against a
  named rule and dropped (no silent drops). `max_rejected_fraction` (0.10) turns
  a too-thin month back into a refusal.
- **Year-aware by shape** (gotcha #6): `year_columns` carry `from_year`, so 2019
  is not asked for `cbd_congestion_fee` and 2025 is. Proven by a unit test that
  validates a 2025-shaped frame against the shipped contract.
- **`nullable: false` in the config = a POST-clean guarantee**: the output
  contract re-checks it, so a cleaning rule that stops working is caught rather
  than shipped.
- Observed 2019 rejection rate: **1.60% over 57.0M rows** (8 months, per-rule
  table printed by `make ingest` and written beside every output).

## The analyst layer + DVC (M1-S2) — how data is pinned and how it is asked
- **`make data` is the whole path**, in one order that is not negotiable:
  ingest → duckdb → `dvc add` + `dvc push`. DVC runs LAST because it pins what
  the earlier steps produced. `SKIP_DVC=1` exists for exactly one caller —
  `make rebuild-proof` — because a proof must never refresh the pin it is judged
  against (gotcha #33).
- **The analyst layer is VIEWS, not copies** (`data/analyst.duckdb`, rebuilt by
  `make duckdb`). The DA cites names — `trips_clean`, `trips_{train,val,test}`,
  `ingest_months`, `ingest_rejections`, `raw_manifest`, `data_health`,
  `unknown_domain_values` — never a parquet path. `split` and `month` are
  literals from `configs/train.yaml`, never parsed from a filename: a renamed
  file must not be able to relabel data.
- **The catalogue reconciles or it fails.** `make duckdb` exits 1 if any view's
  row count disagrees with the ingest report that wrote the data. A catalogue
  pointing at five months of eight answers every query happily, just smaller.
- **`known_domains` documents, it does not enforce** (`configs/data.yaml:
  analyst`). Added by the Data Contract Review; feeds `unknown_domain_values`,
  which reports what the data contains and the TLC dictionary does not describe.
  Observed 2019: `VendorID 4` (264,661) · `payment_type 0` (261,781) ·
  `RatecodeID 99` (949) · `VendorID 5` (219, and it appears NOWHERE else) —
  each in all 8 months. Drift by VALUE is the sibling of gotcha #31's drift by
  column, and it is the quieter one.
- **DVC remote: `/home/longt/dvc-remote/nyc-taxi`** — a plain directory outside
  the repo. Deliberately NOT MinIO: MinIO lives on a PVC in the kind cluster and
  `make destroy` takes PVCs with it, so that "backup" would die with the thing
  it was meant to survive. Honest limit: same physical disk — it survives
  `make destroy` and a wrong `rm -rf` in the repo, not disk loss.
  **`core.analytics = false`**, set at init and pinned by a test (gotcha #32).
- **`data/.gitignore` is DVC's and is the only copy.** The root `.gitignore` no
  longer names `data/raw` or `data/processed`; two copies would be twins, and a
  stale root entry would keep hiding the data if DVC tracking were ever lost.

## The rejected-row sidecar (M2-S1) — the half the counts could not describe
- **`make ingest` now RETAINS what it drops**: `data/rejected/<split>/` mirrors
  `data/processed/`, same writer pins, 16 files / 27 MB for 914,459 rows. Every
  contract column plus the derived target survives — the point of keeping rows
  is answering questions nobody has asked yet.
- **`rejection_rule` is FIRST-MATCH and that is law, not a knob** (`configs/
  data.yaml:rejected` argues its own case). It equals the report's `rejected_by`
  exactly, which is what makes the sidecar checkable; an `all_match` switch would
  double-count and break the reconciliation. All-match rides alongside as
  `rejection_rules` (comma-separated, filing rule always first).
- **A REFUSED month writes no sidecar.** Refusals are structural and leave
  nothing behind; sidecars are for rows that were COUNTED.
- **`make duckdb` now runs TWO reconciliations** and exits 1 on either. The new
  one is per **(month, rule)**, never per month: a sidecar that files every row
  under the wrong rule has a perfect monthly total and is useless. Observed
  2026-08-17: 914,459 == 914,459, 80 pairs, 0 disagreements.
- **`trips_rejected` is a VIEW and is deliberately NOT unioned into
  `trips_clean`** — one careless `SELECT *` must not train on rows the output
  contract refused. Separate tree for the same reason: every proof and view
  globs `data/processed`.
- **`make rebuild-proof` covers BOTH derived trees** (16/16 byte-identical, DVC
  asked about `data/processed.dvc` AND `data/rejected.dvc`). A proof that
  re-derives half a command's output proves half a command.
- **F-005's answer, and it is not "either"** (`docs/rejected_rows_appendix.md`):
  of `duration_above_max`'s 159,300 trips, **85.035% are a 23–24 h clock
  artefact** — median 2.19 mi, $12.00 fare, 98.97% dropped off the NEXT DAY,
  62.64% in the same clock hour — an ordinary short trip whose session closed a
  day late, and *the money was never wrong*. **3.516% (5,601) are real long-haul**
  in the 120–180 min band: 52.78% touch an airport, 32.87% carry an out-of-city
  rate code vs **2.7497%** of clean data. Both, 24:1. Also: the rising rejection
  rate (1.428→2.020%) is **not** this rule — its share is flat 0.273–0.299%.
- **Three of the ten rules have never fired** (missing_timestamp,
  location_out_of_range, passenger_count_out_of_range: `rejected_by = matched =
  0` over 8 months). Not shadowed — absent. Each is provoked by a unit test.

## EDA, KPIs and prior art (M1-S3) — the numbers other milestones must cite
- **`docs/kpi_definitions.md` owns every number's id.** KPI-01…KPI-10, each with
  formula, source VIEW, window, owner. M1-S5's board cards cite ids; M2's error
  memo and M7's drift memos cite ids. **Changing a formula changes the id**
  (KPI-03b, not an edited KPI-03) — otherwise a board's history silently stops
  meaning one thing. KPI-09 (ETA MAE) and KPI-10 (within-5-min rate) are DEFINED
  but **measured only by `taxi_mlops.training.evaluate`** (gotcha #15).
- **Every money KPI states its window and its outlier treatment inline** (AI-2,
  discharged). The reason, in one line: `CORR(fare_amount, trip_duration_minutes)`
  is **0.0735** over all 56,127,878 rows and **0.8708** over
  `fare_amount BETWEEN 0 AND 200` — 3,131 excluded rows (0.0056%) change it by
  11.8×, while the MEAN moves only 0.36%. The robust statistic is the one people
  check. The count of excluded rows renders on the same card as the value.
- **`docs/eda_report.md` describes the surviving 98.397%, and says so at §0.**
  F-005 (rejected rows kept only as counts) was judged OUT of M1-S3's pure-docs
  scope and routed to ARCH at the M1 boundary, reasons in the ledger row.
- **Traps the EDA found, now findings**: **F-006** `congestion_surcharge` is
  63.46% null in 2019-01 with a one-day cliff at **2019-01-21** — a feature built
  on it learns "January" and val/test (clean months) cannot catch it; `airport_fee`
  is 100% null in all 8 months. **F-007** the post-trip columns (`fare_amount`,
  `tip_amount`, `total_amount`, `tolls_amount`, `payment_type`,
  `store_and_fwd_flag`) are leakage for a quote-time ETA — and `trip_distance`,
  the strongest predictor (r 0.8066; 0.8464 in logs), is the meter's DRIVEN
  distance, which M3's dossier must resolve.
- **The honest reference floor for M2** (EDA statistic, NOT a model result):
  a train-fitted `GROUP BY (hour, dow, PU, DO)` median gives **3.7170 min val
  MAE** and **78.693% within 5 min**. The constant-median baseline (7.8866) is
  the flattering floor and must not be the one quoted.
- **Other load-bearing observations**: `ln(target)` is symmetric (skew −0.089 vs
  2.19 raw) · target mean rises **17.3% Jan→Jun** then falls — `month` is a
  reporting dimension, NEVER a feature · zones **264/265 are "unknown", not
  places**, and 264→264 is the largest OD "route" (409,128 trips) · ~0.017% of
  val/test rows carry an OD pair unseen in train, so an unseen-category path is
  required · rejection rate rises monotonically **1.428% → 2.020%**, so the
  health board plots a SERIES (the 10% refusal guard sees none of this).
- **`docs/prior_art.md`: 13 verdicts (6 ADOPT · 3 DIFFER · 4 SURPASS)**, eight
  sources read live 2026-08-16 via `curl` + `gh api` (WebSearch/WebFetch are off
  the allowlist — F-001). The adopt that saves a session: **KServe
  `canaryTrafficPercent` requires Serverless deployment mode; Standard mode does
  not support canary** — M6's canary story would have hit that wall. Also
  adopted: commit-time secret scanning, `for: 5m` sustained alert conditions,
  promotion gated on a deployed-container HTTP test, Feast end-of-hour feature
  timestamps (M8), dashboards provisioned from checked-in JSON (M1-S5).
  Comparability warning: the Zoomcamp benchmark filters duration to **1–60 min**;
  ours is **1–120**, so our data holds 493,876 trips theirs discards.

## The gold marts (M1-S4) — what is published, where, and the two rules that govern it
- **`make marts` is the whole path**: `dbt build` (models AND tests, interleaved
  — a red test stops the publish) → publish into database `marts`, schema
  `marts`, in the ONE Postgres. `make marts-redteam` is its twin and must go RED.
- **Four marts, not three.** `trips_clean` (56,127,878 rows) · `zone_hourly_stats`
  (44,792) · `monthly_kpis` (8) · **`rejections_by_rule` (80)**. The fourth was
  added deliberately: M1-S5's board must render **KPI-03**, Metabase can only
  query Postgres, and `ingest_rejections` lives in DuckDB — an embedded engine no
  served BI tool can reach. Its grain is (month, rule), so it could not be a
  column on either aggregate.
- **dbt SOURCES the analyst layer, attached read-only — it never reads parquet.**
  `read_parquet` in a dbt model would give the repo a second definition of
  `split` and `month` one directory from the first. Same rule for KPI-04's
  documented domains: they come from `configs/data.yaml` as a `--vars` payload
  that `scripts/marts.sh` reads, with **no default** — an absent var must fail
  the build, because an empty domain list reports 100% undocumented and looks
  like a catastrophe.
- **How data reaches an in-cluster-only Postgres:** DuckDB → CSV on stdout →
  `kubectl exec -i` → `psql \copy`. No port is published, no port-forward is
  babysat, no run-time-downloaded DuckDB extension enters the build path.
  Measured 2,000,000 rows / 104 MB in **1.9s (~55 MB/s)**.
- **The honest cost of full-grain `trips_clean`, stated because it is real:**
  ~13 GB in the Postgres volume, and a full-refresh publish holds the old table
  AND the staging copy at once — **23 GB peak**, plus autovacuum working on the
  table that is about to be dropped. M4 runs this monthly as a Flyte task and
  should revisit it as an incremental model. It is published at full grain
  anyway: a BI layer that cannot reach trip grain is not self-service, and
  publishing an aggregate under a fact table's name would be a mart that lies.
- **KPI ids are columns.** `monthly_kpis` carries one `kpi_NN_` column per id,
  and `docs/kpi_definitions.md` now names the mart column for every id.
  **KPI-09/KPI-10 are columns NOWHERE** (gotcha #15) — a test fails if they
  appear. KPI-08's value and its **excluded-row count** travel together, by test.
- **`accepted_range` and the grain check are OURS**, not `dbt_utils`: a $0,
  every-version-pinned program does not fetch a package from dbt Hub inside its
  build path for one macro.
- **Two independent computations agreed, and that is the layer's best evidence.**
  `monthly_kpis` computes KPI-04 from `trips_clean` + `configs/data.yaml`; its
  eight monthly values sum to **527,386** — exactly M1-S3's figure, including the
  219-trip double-count subtlety. KPI-08's monthly exclusions sum to **3,131**,
  the EDA's number to the row. Neither was engineered to match.
- **Boundary law in force** (ADR-009, gotcha #22): `grep -r "analytics"
  src/taxi_mlops/` is empty and a unit test keeps it that way.

## The BI seat (M1-S5) — what renders, from where, and the rules that keep it honest
- **`make deploy-metabase` is the whole path**: namespace → secrets → the
  `metabase` app-db via D-002 → Deployment → host-route check → boards. It
  re-runs the two platform pieces it depends on rather than documenting "run
  `make deploy-platform` first", so it cannot be defeated by running order.
- **The app-db is a real database in the ONE Postgres, never H2.** Metabase's
  default app-db is an H2 file inside the container holding the dashboards,
  cards, connections and users — i.e. everything the M1 gate calls "the boards".
  It dies with the pod, and losing a container filesystem is the NORMAL behaviour
  of a Deployment, not an edge case. `metabase` is D-002's **third** consumer,
  and it cost exactly what M1-S4 predicted: one line in
  `scripts/postgres_databases.sh`, one `ADDITIVE` entry in
  `scripts/platform_secrets.sh`. A test now makes that claim falsifiable.
- **Metabase reads the warehouse as `marts`, never as the superuser.** A BI seat
  that can drop the warehouse it reads is one misclick from a restore.
- **Boards are checked-in JSON, converged through the API** (`analytics/metabase/
  boards/*.json` → `scripts/metabase_boards.py`) — the prior-art ADOPT, landed. A
  dashboard built by clicking exists in exactly one app-db, cannot be reviewed in
  a PR, and cannot be rebuilt after `make destroy`. Idempotence is **by name**:
  cards and dashboards are matched on `name` and updated in place, so a second
  run leaves the same ids. The script **never archives or deletes** — same
  asymmetry as `postgres_databases.sh`; destroying is `make destroy`'s job.
- **Two boards, 17 cards, every card citing a KPI id.** Data health (10) ·
  (KPI-01/02/03/04/05) · KPI board (7) (KPI-01/06/07/08). Enforced by test:
  **KPI-09/KPI-10 appear on NO card** (gotcha #15) · **KPI-08's value and its
  excluded-row count are on the SAME card** (AI-2) · **KPI-03 renders every rule
  including the permanently-zero ones** — a rule you cannot see cannot be seen to
  start firing · **KPI-02 is a SERIES**, because the observed rate rises
  monotonically and an average hides exactly what the board is for.
- **Telemetry is off in two layers, because Metabase phones home in two**
  (gotcha #32): `MB_ANON_TRACKING_ENABLED` and `MB_CHECK_FOR_UPDATES` in the
  manifest, plus `allow_tracking: false` in the `/api/setup` call — the setup
  writes its own preference and would otherwise re-enable tracking at first login.

## Feature set v1, the two floors, and LightGBM v1 (M2-S2) — the first measured numbers
- **`python -m taxi_mlops.training train` is the whole path** (both floors + the
  model, one evaluator, one table). `make train` is deliberately still a stub:
  M2-S3 owns it, because the GATE verdict is what makes that target what it
  claims. **This story registers nothing** — `search_registered_models()` returns
  `[]`, and a test forbids the registry API in `src/taxi_mlops/training/`.
- **The include list is a knob, the exclude list is LAW.** `configs/train.yaml:
  features` names the five v1 columns (hour, dayofweek, PU, DO, passenger_count);
  `taxi_mlops.features.quote_time.EXCLUSIONS` names **18 refused columns**, each
  with its reason and ledger row, and `FeatureLeakageError` refuses a matrix OR a
  config that re-admits one. Same argument as M2-S1's first-match rule: a switch
  that can break an invariant is a trapdoor, not a knob. **F-006 CLOSED**
  (`congestion_surcharge` excluded citing the 2019-01-21 cliff, `airport_fee` at
  100% null); **F-007(a) DISCHARGED** — and the registry adds the three money
  columns F-007 did *not* list (`extra`, `mta_tax`, `improvement_surcharge`),
  because a registry that agreed with the finding rather than with the world
  would be the next trap. **F-007(b) is untouched and stays M3's.**
- **The evaluator re-derived the EDA's SQL floors to four decimals, and that is
  this story's best evidence.** `evaluate` measured the constant-median floor at
  **7.8866** val / 7.6667 test and the group-median floor at **3.7170** val /
  3.5090 test with **78.693%** within 5 min — the EDA's numbers exactly, computed
  by different code on a different engine. Unseen-group fallback fired on
  **1.5252%** of val and **1.4786%** of test rows (EDA said 1.53% / 1.48%).
  Nothing was tuned to match; a disagreement would have been a bug in `evaluate`.
- **KPI-09 / KPI-10 have their first measured values** (`docs/kpi_definitions.md`,
  run `598044f586524a82b385a6cf27f9a31b`): **3.4760 min val · 3.2608 min test**
  and **79.693% · 81.480%**. v1 beats the honest floor by **6.48%** on val and
  buys **one point** of within-5-minutes — the honest shape of a quote-time model
  with **no distance feature**. Quoting the constant-median floor would have made
  it look like a 56% win; that floor is named "the flattering one" in code.
- **E-1 answered by measurement, not opinion.** The `log1p` target ablation
  (`--ablation`, its own MLflow run) came in at **3.4803 val / 3.2688 test** —
  consistently *worse* than the raw target. v1 keeps `target_transform: none`
  because KPI-09 is MAE in minutes and objective `l1` minimises exactly that on
  exactly that scale. The ablation logs **metrics only**: a log-space booster
  needs a pyfunc wrapper to be servable, and shipping one for an ablation would
  put a wrapper nobody uses in the registry.
- **v1 never early-stopped** — 500/500 rounds with val still improving. The
  number is a floor for LightGBM on these five features, not its ceiling, and
  M3's scout/sniper is where that gets spent. Said out loud so nobody reads
  3.4760 as "tuned".
- **This host has no OpenMP.** `import lightgbm` dies without `libgomp.so.1`;
  `taxi_mlops.training.openmp` borrows the copy scikit-learn's wheel vendors
  (gotcha #37 for why nothing simpler works). Debt **D-004** puts the real
  package in M4's image; AWAITING_PO 2026-08-17-1 offers the PO a one-line fix
  for this laptop. Both non-blocking.

## The promotion gate and the first champion (M2-S3) — the one place this program says no
- **`make train` is the whole path now**: both floors + LightGBM v1 through ONE
  evaluator → the GATE on the untouched TEST month → promotion, only on a pass.
  **A refusal exits 1** (from M4 this is a pipeline step; a gate that says no
  while exiting 0 is a gate the pipeline cannot hear). `make train-redteam` is
  its twin and inverts that, exactly as `marts-redteam` does.
- **The bar: 2.00% KPI-09 margin over the group-median floor, plus KPI-10 must
  not regress.** The margin is a MAINTENANCE-COST bar, not a statistical one —
  over 5.95M test rows even 0.5% is significant, but 2% of the floor is ~4
  seconds of mean error, and a model whose whole advantage over a `GROUP BY` is
  four seconds does not earn a booster to serve and a rollback to rehearse. The
  measured gap is 7.07%, so the bar has headroom BY DESIGN. Both knobs live in
  `configs/train.yaml: gate` with their reasoning; **loosening either is a PO
  fork** (never an edit). The KPI-10 condition can refuse a model the margin
  admits: a mean over 6M rows can improve while more riders are quoted wrongly.
- **`gate.py` decides (pure), `registry.py` acts (mutating), and a test keeps
  them apart.** `decide()` RAISES rather than warns when handed val metrics
  (early stopping read val — judging there scores a model against a month it was
  already fitted to) or the flattering constant-median floor. The registry API
  appears in exactly one module, pinned by a test.
- **The red team is watched saying no.** A challenger fitted on PERMUTED train
  labels (val/test untouched — shuffling those is a broken measurement, not a
  broken model) goes through the same fit, evaluator and gate with promotion
  ENABLED: **REFUSED on both conditions** (−118.49% KPI-09, −32.018 points
  KPI-10), exit 1, and the script proves the registry is identical before and
  after. It reads the alias via `get_model_version_by_alias`, NOT off
  `search_model_versions` (which returns `aliases` EMPTY on server 3.15.1 — a
  snapshot built from that field would be blind to the exact mutation it checks).
  The hobbled run is KEPT and marked (`red_team`/`hobbled`/`do_not_promote`):
  a deleted refusal cannot be checked by anyone who was not watching.
- **What the refusal taught, and it is better than the verdict**: fitted to noise
  LightGBM early-stopped at **iteration 1** with test MAE **7.6667** — equal to
  `baseline-constant-median` to four decimals. "Learned nothing" numerically IS
  the median, and against the flattering floor that model scores **+0.00%**.
- **The champion exists**: `models:/nyc-taxi-eta@champion` → version **1**, run
  `3adee05a855a424bb664c7fea3735703`, signature + input example, promoted at
  +7.07% (81.480% vs 80.322% KPI-10). Promotion is **idempotent by RUN** —
  re-running reuses the version and leaves the alias alone (proved live, `noop?
  True`). Nothing in `registry.py` deletes: a replaced champion is what a
  rollback needs to find. The verdict travels ON the version as tags, so "what
  was this measured against?" is answered by the registry, not by a transcript.
- **F-008 (new, lands M3): a sampled run makes this gate EASIER to pass.** The
  floor is fitted on the same data as the challenger, so shrinking train degrades
  the BAR faster than the model. Measured on one train month: floor 3.5090 →
  4.1138, model 3.2608 → **3.4207** (worse), margin 7.07% → **16.85%** (better).
  M3's scout and sniper sample BY DESIGN.

## Row-level predictions, the error memo and its board (M2-S4) — where v1 is wrong, visibly
- **`make predictions` scores what was PROMOTED, never a fresh fit.** It resolves
  `models:/nyc-taxi-eta@champion`, reads the version back, stamps it on every row
  and mints nothing (no run, no version, no alias move). 12,140,456 rows to
  `data/predictions/<split>/` plus `predictions.json` provenance. The strongest
  thing it does is **refuse**: the champion's promotion tag says KPI-09 3.2608 on
  test, so re-scoring must return 3.2608 or the write is abandoned — a model that
  loads differently from the one that was gated has no other symptom.
- **`data/predictions/` is gitignored and deliberately NOT DVC-tracked.** It is
  model OUTPUT, regenerable in ~4 min from DVC-pinned inputs plus a registry
  version. A `.dvc` pin would need refreshing every time the champion moves (M3's
  bake-off, M7's retrains) — a pin stale by design is worse than none, because it
  looks like provenance. The real provenance is `predictions.json` + the registry.
- **`make duckdb` now runs THREE reconciliations** (views: 12). The new one:
  prediction rows == held-out rows per split, or exit 1. Observed 2026-08-17:
  6,189,748 + 5,950,708 = **12,140,456 == 12,140,456**.
- **KPI-11/12/13 are NEW ids because the WINDOW is new** (segment, not split) —
  the id law applied, not argued around. What licenses a mart carrying model-error
  numbers at all (gotcha #15): `assert_error_segments_reconcile` fails the build
  unless the whole-split row reproduces the evaluator's KPI-09/KPI-10 to four
  decimals. **A segment number that cannot roll up to the evaluator's is not a
  segmentation of it.** `prediction_runs` (which READS the evaluator's manifest,
  never computes) is never published to Postgres, so no board can render KPI-09/10.
- **The memo's headline is about COVERAGE, not accuracy** (`docs/error_memo_m2.md`).
  The gate's +7.07% decomposes: on the **98.521%** of test rows where the floor has
  a real group median the booster is worth **+1.88%** (~3.7 s); on the **1.479%**
  where it falls back it is worth **+68.19%** (floor MAE 18.5704). **Three quarters
  of the model's entire advantage over a `GROUP BY` is bought on 1.48% of rows** —
  F-008 from the other side, and it lands on M3.
- **The ceiling finding**: of the 970 longest trips the contract admits (100–120
  min), KPI-12 is **0.000%** — not one quoted within 5 min — mean quote 47.93 vs
  mean truth 107.92. Max prediction ever on test **92.155** against a max truth of
  **120.0**. Correct behaviour for `l1` with no distance feature, and the business
  case for M3's dossier. Airports (JFK/LGA/EWR, 8.817% of trips) carry **1.90×**
  the error at **59.988%** KPI-12; the floor is nearly as bad, so the gap is
  informational, not algorithmic. **1–5 min trips are the ONE segment >5,000 trips
  where the floor beats the booster** (−0.88% test, −0.79% val — both months).
- **`scripts/error_memo_numbers.py` is the memo's twin** — one section per memo
  section, printing the query it ran. It caught **four last-digit rounding slips**
  on its first run. A memo nobody can re-run is a memo nobody can check.
- **`make marts` builds with `--no-partial-parse`, and that is load-bearing**
  (gotcha #38): dbt's parse cache records node paths relative to wherever dbt was
  last run, so one hand-run from the repo root breaks every later build with an
  error naming a file that plainly exists. Costs nothing here (5 models).

## The M2 gate (M2-S5) — what it asks, and the two things it refuses to do
- **`make verify-m2` is 49 sub-checks in 9 sections, ~30s, and it re-fits
  NOTHING.** No `make train`, no `make predictions`, no registry write — pinned
  by `tests/unit/test_verify_m2.py`. The champion is a REGISTERED artifact; the
  gate's job is to check what was promoted, not to promote again. A gate with
  side effects on the registry it checks is not a gate. There is also **no skip
  flag** (M1's rule, inherited): a gate with a fast mode is a gate that runs in
  fast mode.
- **The refusal is checked by REPLAY, not by grep.** "The transcript contains
  the word REFUSE" stays green after somebody loosens `configs/train.yaml: gate`
  — the exact change the constitution reserves for a PO fork. So the gate parses
  M2-S3's pasted transcripts out of `docs/promotion_gate_m2.md` and feeds their
  numbers back through `gate.decide()` **as it exists on disk right now**:
  7.6667 vs 3.5090 must still come back REFUSE (−118.49%), 3.2608 vs 3.5090
  must still come back PROMOTE (+7.07%), and the gate must still raise on val
  metrics and on the flattering constant-median floor. A loosened bar is a RED
  gate, not a diff nobody read.
- **Every leg must prove it RAN.** M1 taught that a check wired to no sensor is
  a green light; M2 applies that one level up — each Python leg is required to
  emit a minimum number of verdicts (`expect_verdicts`), so a leg that dies on
  import FAILS instead of contributing zero silent passes. It earned itself in
  the red-team drill: with the alias gone the registry leg managed 1 verdict of
  the 7 it owes, and the guard is what said so. `consume` is called through
  process substitution and never a pipe — `| consume` would count the failures
  in a subshell and throw them away at the closing brace.
- **The cross-system checks are the ones worth having**: the mart's whole-split
  `overall` row must reproduce the evaluator's KPI-09/KPI-10 to 4 dp (Postgres
  on one side, `predictions.json` on the other) · the published rows must be
  stamped with the version that IS champion right now · re-scoring must return
  the champion's own `gate_challenger_mae` tag · the memo's headline number must
  equal what `scripts/error_memo_numbers.py` computes live.
- **`make verify-m2-redteam` breaks the POINTER, never the model.** It deletes
  the `@champion` alias (instant, exactly reversible, invisible to anything not
  actually reading the registry), asserts the gate goes RED **naming** it while
  38 other sub-checks still pass, then restores from an EXIT trap and asserts
  GREEN 49/49. Version 1, its run, its signature and its artifacts are untouched
  throughout. This is the only place in the repo that deletes registry state;
  `registry.py`'s no-delete property is intact.
- **The root-stray leg is wider than the filename that prompted it.** The
  kickoff asked for "no stray `_handoff_entry.md` at the repo root"; session (z)
  then left an empty `marts.duckdb` there, which was the FINGERPRINT of gotcha
  #38 and would have been hidden by a `.gitignore` entry. The check diffs the
  root against `git ls-files` plus a named list of what a working clone really
  has, and names whatever is left.

## The dossier, the zone centroids and the Design Review (M3-S2) — what M3 gets to build from
- **`make zones` is the whole path**: sha256-pinned TLC shapefile → 263 area-weighted
  centroids → `data/reference/taxi_zone_centroids.csv` (committed, 263 rows). It is
  what makes any *quote-time* distance possible: 2019 TLC files carry zone ids, not
  coordinates, so every community distance/bearing idea is untransferable without it.
- **The CRS is READ from the .prj inside the zip, never hardcoded** — pinned by a test
  that parses the AST so the file's own prose about not hardcoding `EPSG:2263` does not
  trip it. Centroids are area-weighted in the projected plane (feet) and transformed
  after; a centroid taken in degrees is distorted by the cos(latitude) scaling.
  `Shape_Area`/`Shape_Leng` in the shipped `.dbf` are IGNORED — read live they carry
  `0.00078` for a zone whose own coordinates are in feet, i.e. computed in some other CRS.
- **Zones 264/265 get NO row, deliberately.** They are TLC's "Unknown" — not places —
  and 264→264 is the largest single OD "route" in the data. Measured share with no
  geometry: train **1.2462%** · val **1.0113%** · test **1.0753%**. Every spatial feature
  owes them a named, tested fallback (DR-04 condition 1), because the ~1.48% fallback
  rows are where 75.4% of the champion's advantage already lives.
- **F-007(b) CLOSED by measurement, not by assumption** (Design Review **DR-04**):
  `trip_distance` stays excluded; the **zone-centroid haversine is the quote-time
  substitute**. Over 43,439,267 train rows the meter's driven distance correlates with
  the target at **0.8068** (reproducing the EDA's independent 0.8066) and the centroid
  straight line at **0.7873** — the legal feature keeps **97.6%** of the forbidden one's
  power. Centroid vs meter distance `r` = **0.9661**; straight-line ≤ driven on 81.662%;
  median circuity **1.2952**. Circuity itself is REFUSED as a feature — its numerator is
  the excluded column.
- **The dossier holds 21 candidates** (`docs/feature_dossier.md`), harvested live via
  `curl` + `gh api` (F-001: WebFetch is still off the allowlist). Two carry verdicts
  already, both because a number exists: the community's **#1 lesson — the `log1p`
  target — was MEASURED AND REJECTED at M2-S2** (worse on both splits; our gate is MAE
  in minutes and `l1` minimises exactly that, whereas the competition's metric was
  RMSLE), and row 7 carries this session's measurement. **PCA rotation and KMeans
  place-clusters are refused with a reason**: TLC zones already ARE the clusters, drawn
  by people who know the city and stable across years.
- **The harvest's best find is a worked leakage example, read precisely.** The top-6%
  source concatenates train+test and then takes group means of the target. The test
  *labels* do NOT leak (they are NaN, so `.mean()` skips them); what leaks is (a) no
  point-in-time constraint — a January trip gets a mean computed with June in it — and
  (b) the *count* features, which need no label and genuinely use the test period. **The
  same line of code is correct in a competition and disqualifying in production, and the
  difference is the split, not the code.**
- **Two live-drift facts worth keeping**: the Kaggle competition page is a JS shell
  (HTTP 200, 5,632 bytes, zero occurrences of `RMSLE` or any leaderboard number), so the
  playbook's §0 competition record is carried as ARCH's 2026-08-12 reading and **nothing
  in M3 depends on it**; and the OSRM companion dataset the playbook calls "the single
  biggest edge" is **404** at the URL the sources cite — which makes our own 263×263
  matrix the only reachable route, and it stays the M9 stretch.
- **Design Review decisions bind M3-S3/S4/S5** (`docs/rituals/2026-08-17_design-review-m3.md`):
  DR-01 equal budgets measured in *fitting wall-clock seconds*, artisan **9,000 s**, both
  tracks print actuals · DR-02 keep-threshold **≥0.50% relative val MAE**, re-argued as a
  maintenance-cost bar, with **KPI-10 reported per group** and every group listed
  including drops · DR-03 **disjoint search axes** — artisan searches FEATURES holding v1's
  hyperparameters, automation searches HYPERPARAMETERS on feature sets it does not invent,
  which is the only thing that lets the 2×2 answer "features or tuning?" · DR-05 all five
  contenders are **full-data, TRAIN-ONLY** fits and the playbook §3.7 train+val refit is
  explicitly NOT used at M3 · DR-06 **+2.71% is M3's working headroom and +7.07% may not
  be quoted as headroom**; the bar's number is S1's to set in `configs/train.yaml`, and
  S5 quotes the config, never the minutes.

## The hardened gate (M3-S1) — four refusals it could not make before, and what they cost
- **The floor is now `baseline-group-median-od-fallback`** (F-010, Design Review
  DR-06 §3): the same lookup with one more backoff level — `(hour, dow, PU, DO)`
  → `(PU, DO)` → global. A NEW name, never an edit (the config legislated that in
  M2), so M2's verdicts stay reproducible. Measured through the one evaluator:
  **3.5515 val · 3.3518 test** (vs the old floor's 3.7170 / 3.5090), 1,610,050
  groups + **46,938 backoff cells**. It reproduced REV's independent
  re-derivation to four decimals — two instruments, one number.
- **The headroom is +2.71%, and +7.07% may not be quoted as headroom** (DR-06
  §2). 75.4% of the champion's advantage was bought on the 1.48% of rows where
  the OLD floor guessed 11.15 min for everyone; give those rows a real answer and
  most of M2's "headroom" was the floor's fallback, not the booster. **The 2.00%
  bar is unchanged and that is a conclusion**: it is a maintenance-cost bar (~4.0
  s of mean error), and owning a booster did not get cheaper when the floor got
  better. Honest cost, stated: M3's bake-off must now land **≤3.2848** on test.
- **The gate consults the INCUMBENT** (F-011), on KPI-09 AND KPI-10, and it has
  **no knob** — when the alias is unset there is simply nothing to consult. The
  registry read lives in `run._resolve_incumbent` so `gate.decide` stays pure and
  cluster-free; `registry.promote` then refuses to move an alias whose current
  version the decision did not read (`incumbent_version` is required, the live
  alias is re-read at promotion time). Either half alone can be walked around.
- **A recorded number exists only at the precision it was recorded at.** The
  first full run of the new gate REFUSED the champion against its own tag: the
  registry says `3.2608`, a deterministic re-fit measures `3.260823…`. Fixed by
  `gate.INCUMBENT_MAE_DECIMALS` / `INCUMBENT_WITHIN_DECIMALS`, pinned as twins of
  the `%.4f`/`%.3f` in `run._promote`. Invisible to every unit test, because a
  test writes the same literal on both sides.
- **`make predictions` now checks the FLOOR half too** (F-012), as a refusal to
  write: the floor it fits is the one the CHAMPION's verdict was argued against
  (read off the version's `gate_floor` tag, NOT the current config — after this
  story they legitimately differ), and its re-scored MAE must equal
  `gate_floor_mae` or nothing is published.
- **A sampled run gets NO verdict** (F-008), refused before a row is read.
  `--no-gate` is the sample-first smoke path, legal ONLY with `--train-months`,
  promotes nothing, tags its runs `sample_run`/`do_not_promote`, and exits **3** —
  its own code, because "not judged" and "judged and satisfied" must never be
  confused by a pipeline.
- **The gate has ONE home** (F-013, gate half): `configs/promotion.yaml` and its
  contradictory `gate_ratio: 0.85` are deleted, and a test fails if any file under
  `configs/` other than `train.yaml` names a gate KNOB (knobs, not filenames — the
  next stub will be called something else). The features half is M3-S3's.
- **Nothing was promoted.** `@champion` is version 1 before and after; the full
  run used `--no-promote` and its runs live in experiment `m3-gate`.

## Feature set v2 (M3-S3) — five groups tried, two kept, and the family the sources swear by lost
- **`configs/features.yaml` is THE feature-set registry** (F-013's features half,
  **row CLOSED**): `base` + five declared `groups` + the sets; `configs/train.yaml:
  features` holds a `version` and a `registry` pointer and NOTHING else, and
  `taxi_mlops.features.sets.resolve` is the only expansion in the program — it
  RAISES if a column list grows back in `train.yaml`. The include list stays a
  knob; **`quote_time.EXCLUSIONS` is still the LAW** and every set in the registry
  is walked by a test that refuses one that re-admits an excluded column.
- **The five groups and their order were committed BEFORE anything was fitted**
  (DR-02 anti-forking-paths). Verdicts on a 15% sample, confirmed at full data,
  val 2019-07 only, keep bar **≥0.50% relative val MAE with KPI-10 not down**:
  **g1 temporal extras +1.77% KEEP · g2 centroid geometry +0.63% KEEP · g3
  spatial identity +0.15% DROP · g4 trip re-encodings −0.01% DROP · g5
  point-in-time aggregates −1.63% DROP.** Three of five lost and all three are in
  the table — `docs/ablation_m3.md`.
- **v2 = base + g1 + g2, 24 features**, full-data val **3.3905 (+2.46% over v1),
  KPI-10 80.506%**, logged with signature + input example (run
  `6807116edf4c49d681a31bd941298a81`, experiment `m3-artisan`). **No number in
  this story has faced the gate** — the bar is 3.2848 on test and that is M3-S5's.
  `configs/train.yaml` still names **v1**: the config line moves as part of a
  promotion or not at all.
- **The confirmation confirmed, and the pre-registered explanation was wrong.**
  g2 measured **+0.6312% at 15% and +0.6277% at 100%**; the doc predicted the
  delta would keep shrinking with data and §5 keeps the prediction beside its
  refutation. The run that lied was the **0.5% smoke test** the protocol had
  already ruled inadmissible. v1 reproduced **3.47603843547682** across two
  invocations 71 minutes apart, and it equals M2-S2's number from another script.
- **The strongest family in every source is the one that lost.** g5's legal,
  point-in-time version made the model worse on both KPIs — our `PULocationID`/
  `DOLocationID` already ARE the key the aggregate is grouped on, and the honest
  window means the feature the model is FITTED on is not the feature it is SCORED
  on (gotcha #43). The mandated leakage red-team (`make leakage-redteam`) fitted
  the same tables across val on purpose: **+1.56% on the month it saw, −3.83% on
  the untouched month** — it would have cleared the keep bar and been admitted.
  The leaky switch defaults off, lives in the type, and only one script may flip it.
- **DR-01 budget, artisan track: 3,313.9 s logged of 9,000** (two red-team arms
  logged no `fit_seconds`, so it is a floor). The track stopped on its stop rule.
- **Anything long runs detached.** `automation/run_detached.sh` + `watchdog.sh` on
  cron; ending a turn kills every background task the session started (gotcha #45).

## The automation track (M3-S4) — what tuning bought, what it cost, and the two rows it produced
- **`make automation-track` is the whole path**, six phases in one order: scout ×2
  (FLAML, 5% sample) → sniper ×2 (Optuna TPE + MedianPruner, 15% sample, studies in
  the ONE Postgres) → full-data refit ×2 (DR-05). **Every phase is skipped if its
  output JSON already exists**, so a killed track resumes at the phase it lost
  instead of re-spending the hours before it — the numbers live in
  `automation/runs/m3s4/*.json`, one file per phase, and NOT in the log.
  `docs/automation_track_m3.md` is the narrative; §6 is the numbers.
- **The scouts disagreed, which is why DR-03 made the sniper follow its own
  scout**: FLAML picked **xgboost on v1** (scout-internal 3.7627) and **lgbm on
  v2** (scout-internal 3.5035). Both are 5%-sample, FLAML-internal losses and
  neither is a result (gotcha #15). Neither scout named `rf`/`extra_tree`, so the
  sniper's refusal path stayed armed and untaken.
- **Both studies were stopped by the CLOCK, not by `n_trials: 60`** — v1 got
  **9 trials (0 pruned)**, v2 got **21 (6 PRUNED)**. The pruner bought more than
  double the search on the same budget, and v2's six prunings are what satisfies
  the §9/M3 ≥1-pruned-trial leg by measurement; v1's zero is why the armed-pruner
  unit test exists.
- **Automation LOST on v1, and its own budget says why.** `auto-on-v1` measured
  **3.7245 val MAE · 78.003% KPI-10** against hand-tuned v1's **3.4760 / 79.693%**
  — **7.15% worse** — and it hit its **800-round cap with val still falling ~0.03
  per 100 rounds**. It is a truncated model, not a converged one (the scout had
  proposed `n_estimators: 1635`). Refitting it bigger *after* seeing that number
  would spend budget the track already overspent, on the losing arm, which is what
  DR-01 condition 2 forbids — so the row stands as measured and labelled, and the
  call is M3-S5's.
- **Automation WON on v2, by 0.24%.** `auto-on-v2` (lgbm, 21 trials) measured
  **3.3823 val MAE · 80.552% KPI-10** against the artisan's v2 at **3.3905 /
  80.506%** — **+0.2436%** relative MAE, **+0.046** KPI-10 points. That is **less
  than half of DR-02's ≥0.50% keep bar for a single feature group**, bought with
  4,247.3 s on that arm alone. Against the same v1 baseline both tracks started
  from: features **+2.46%**, tuning-on-top-of-features **+2.70%**.
- **Both refits hit the 800-round cap; only v1 was hurt by it.** v2 never
  early-stopped either (best iteration 791/800) but its curve was flat —
  **0.00034** MAE over its last 100 rounds against v1's **0.02808**, ~**82×** less
  slope. A cap is a truncation only if the curve is still moving under it, so
  **F-015's caveat is v1's row and does not double**.
- **The track went OVER its DR-01 share and the overrun is per-phase and
  mechanical**: **9,133.8 s measured across six phases against 9,000 declared
  (+133.8 s, +1.49%)**. FLAML's `time_budget_s` bounds its search loop and not the
  retrain after it; Optuna checks its cap BETWEEN trials, so the trial in flight
  overruns. Against the artisan's 3,313.9 s that is **2.76×** — an unequal race,
  reported at the size it happened (DR-01 condition 2), never re-run. **The two
  tracks also stopped for different KINDS of reason** — the artisan on its own
  keep rule, the automation on a clock that expired mid-search on both studies —
  which is the asymmetry that survives normalising the seconds.
- **Nothing here promotes.** The registry API appears in none of this story's
  scripts, and a test keeps it out.

## The bake-off, the alias, and the M3 gate (M3-S5) — what the square answered and what the gate learned
- **The answer is FEATURES.** Five contenders, four LOADED from their MLflow
  artifacts and only the floor fitted, one evaluator, the untouched test month:
  **auto-on-v2 3.2403 · artisan v2 3.2425 · champion v1 3.2608 · floor 3.3518 ·
  auto-on-v1 3.5038**. Features alone bought **+0.56%** over v1 and tuning on top
  of them **+0.63%** — **+0.07 percentage points, 134 ms of mean error, one
  seventh of DR-02's own keep bar**, for 2.76× the artisan's wall-clock. **Val
  ranking == test ranking, exactly.** The floor refused itself at +0.00%, and
  F-011's incumbent condition is the only one of the four that notices it is
  2.79% worse than what serves. `docs/bakeoff_m3.md`.
- **The alias moved and the whole published chain followed it, in order**:
  `make champion-transition` → promote → `predictions` → `duckdb` → `marts` →
  `boards` → the memo's numbers PRINTED for the human who owes the prose.
  `@champion` is version **2** (`auto-lgbm-v2`, run `92b73bd4f77d…`, feature set
  **v2**, 24 features) and `configs/train.yaml: features.version` moved with it —
  the config line moves as part of a promotion or not at all.
- **`docs/error_memo_m2.md` §9 is the dated M3 section, and §0–§8 are kept
  UNEDITED as the M2 record.** A memo that silently rewrites its own numbers
  cannot be compared against the decisions made from them. §9's finding: **the
  coverage headline INVERTED** — three quarters of the champion's advantage used
  to be bought on 1.48% of rows, and it is now **96.9% bought on the ordinary
  99.98%**. That is **F-010 landing, not the model improving where it was weak**:
  the new floor backs off to `(PU, DO)` first, so only **968** test rows fall past
  it — and on those the floor is wrong by **29.86** minutes. Also: the ceiling
  lifted 92.155 → **97.105** min and the 100–120 band went 0.000% → **0.103%**
  KPI-12 (one trip of 970), while the **airport gap held at 1.91×** even though
  v2 carries the OD geometry §4 said would identify them — so §7 row 2 stays open
  with that as its new evidence.
- **`make verify-m3` is 46 sub-checks in 8 sections, 4.7 s, and it re-fits
  NOTHING** — M3 cost 12,447 s of fitting across two tracks, so a gate that
  re-derived any of it would cost more than the milestone. It reads committed
  docs, committed JSON, the Optuna storage and the registry, and **replays**:
  DR-02's keep bar is re-applied to the ablation table's own numbers, and the
  bake-off's five verdicts are re-computed through `gate.decide` as it exists on
  disk. `make verify-m3-redteam` proves it can say no.
- **The gate must assert PROPERTIES, not the literals that were true the day it
  was written** (F-017, gotchas #49/#50) — and this story paid for the rule.
  `verify-m2` pinned the champion's `gate_floor` name, its experiment, and read
  `do_not_promote` by key presence; **all three went RED on the first legitimate
  champion transition**, none of them about anything being wrong. A guard that
  fires when the program behaves correctly teaches the next session to edit
  assertions. Replaced by properties strictly stronger than the literals were,
  plus one cross-system check the literal could not make (the version's
  `gate_floor` must be the floor `predictions.json` published against — F-012 from
  the other end). GREEN **55/55**, one added, none removed.
- **F-016 is OPEN and was deliberately not acted on**: the incumbent condition is
  non-regression with **no margin**, so the alias moved on **+0.63% — 1.2 seconds**
  while the floor condition demands 2.00%. Changing a gate condition after seeing
  the number it would have changed is the edit this program never makes on its own
  authority. Routed to ARCH/PO at the M3 boundary; nothing waits on it.

## Port family (fleet rule: check for foreign stacks before cluster-up)
MLflow 5000 · MinIO 9000/9001 · Flyte console 8080 · Grafana 3000 ·
KServe ingress 8081 · Pushgateway 9091 · Metabase 3030 · Postgres 5432 (in-cluster only)
Enforced by `make ports` (`scripts/port_precheck.sh`), which checks this family
PLUS every `hostPort:` in `infra/kind/kind-config.yaml` (adds 8443, the ingress
TLS mapping). This list and the `PURPOSE` map in that script are twins — change
both together. Known limit (F-002): `ss` sees only inside the WSL VM.

**How a host port reaches a service (M0-S3).** kind publishes host ports at
cluster-CREATE time only, so the route is declared, never port-forwarded:
`hostPort` in the kind config → `containerPort` = the Service's fixed
`nodePort`. Live pairs: 5000←30500 (`infra/manifests/mlflow-nodeport.yaml`),
9000←30900 and 9001←30901 (`infra/helm/minio/values.yaml`), **3030←30300**
(`infra/manifests/metabase.yaml`, added M1-S5), 8081←80 / 8443←443
(ingress, M5). Each pair is TWINS across two files — `tests/unit/
test_platform_scripts.py` fails if they drift. Adding a port means
`make cluster-down && make cluster-up`; there is no live path — M1-S5's
rebuild was PLANNED for exactly this reason, not discovered.

## Commands (fill as they become real; each idempotent, each with a verify twin)
| Intent | Command | Verified |
|---|---|---|
| Cluster up | `make cluster-up` | VERIFIED 2026-08-16 (M0-S2): created 3-node `mlops-taxi`, re-ran → `already exists — no-op` exit 0, down→up rebuild from the pinned config, all exit 0 |
| Port pre-check (gotcha #10) | `make ports` | VERIFIED 2026-08-16 (M0-S2): passes clean; RED-TEAMED with a dummy listener on 5000 → exit 2 naming port, purpose and holding pid, through `make cluster-up` too |
| Cluster down | `make cluster-down` | VERIFIED 2026-08-16 (M0-S2): deletes, and no-ops when already absent (both exit 0) |
| Platform | `make deploy-platform` | VERIFIED 2026-08-16 (M0-S3): MinIO + Postgres + MLflow up; re-run on the live stack = clean upgrade (helm rev 3, namespaces/service/configmap `unchanged`) and it REPAIRED a hand-inflicted `scale --replicas=0` |
| Gate check M0 | `make verify-m0` | VERIFIED 2026-08-16 (M0-S3): 18 sub-checks GREEN, exit 0; RED-TEAMED by scaling MLflow to 0 → exit 1 naming 5 failures. Secrets come from `.env` (gitignored) via `scripts/platform_secrets.sh` — never printed, never committed |
| Ingest (M1-S1) | `make ingest` (`python -m taxi_mlops.data ingest [--month YYYY-MM]`) | VERIFIED 2026-08-16 (M1-S1): 8 months, 57,042,337 → 56,127,878 rows (1.603% rejected, per-rule table printed); re-run = all 8 outputs byte-identical + manifest unchanged. RED-TEAMED twice: seeded corrupt parquet → `CorruptSourceError` naming the file, exit 1, `processed/` never created; truncated pinned raw → `ChecksumDriftError`, exit 1, output sha256 and manifest pin both untouched |
| Data path, whole (M1-S2) | `make data` (ingest → duckdb → dvc add+push; `SKIP_DVC=1` stops before the pin) | VERIFIED 2026-08-16 (M1-S2): composed run green end to end; DVC leg runs LAST because it pins what the earlier legs produced. **RE-VERIFIED 2026-08-17 (M2-S1)** with the retaining ingest: 8 months, same 56,127,878 rows out, `data/rejected` now pinned as its own third target (`9 files pushed`, remote in sync) — and `data/processed.dvc` came back **unmodified in git**, i.e. a CHANGED ingest reproduced the M1 bytes exactly |
| Analyst layer (M1-S2, extended M2-S1) | `make duckdb` (`python -m taxi_mlops.data duckdb`) | VERIFIED 2026-08-16 (M1-S2): 9 views, and the row count of every one of the 8 months equals the `rows_out` its ingest report claimed (56,127,878 total). Exits 1 when they disagree — RED-TEAMED in unit form by truncating a month's parquet and by inflating a report's `rows_out`. **RE-VERIFIED 2026-08-17 (M2-S1): 10 views** (`trips_rejected` added) and a SECOND reconciliation, per (month, rule): **914,459 sidecar rows == 914,459 counted, 80 pairs, 0 disagreements**. Exits 1 on either — RED-TEAMED in unit form three ways: rows removed, rows RELABELLED under the wrong rule (monthly total untouched, so a per-month check would pass), sidecar deleted |
| Gold marts, whole (M1-S4) | `make marts` (dbt build incl. 34 tests → publish to Postgres; `SKIP_PUBLISH=1` stops at DuckDB) | VERIFIED 2026-08-16 (M1-S4): `dbt build` PASS=39 (4 models, 34 data tests, 1 seed) in 3.24s; publish printed `COPY 56127878` for `trips_clean` — exactly the ingest total — plus 44,792 · 8 · 80 for the aggregates. Re-run is a full refresh into `<name>__staging` swapped in inside ONE transaction, so a reader never sees a half-loaded mart (watched live: the old `trips_clean` still served 56,127,878 rows while `trips_clean__staging` filled) |
| Prove the mart tests can FAIL | `make marts-redteam` | VERIFIED 2026-08-16 (M1-S4) — see the story's transcript. Unions `seeds/redteam/` (999.5-min and 0.2-min trips) and **inverts the exit code**: a GREEN build with impossible trips in it means the tests are not testing, and the script fails saying so. Never publishes |
| Databases in the one Postgres (D-002) | `scripts/postgres_databases.sh` (step [5/7] of `make deploy-platform`; `DRY_RUN=1` previews) | VERIFIED 2026-08-16 (M1-S4) on the EXISTING volume (PGDATA initialised 15:47, `marts` created 17:44): run 1 `before = role absent, database absent` → `ok marts owner=marts`; run 2 `before = role present, database present`, nothing changed; `mlflow` no-op on both |
| BI seat, whole (M1-S5) | `make deploy-metabase` (namespace → secrets → app-db via D-002 → Deployment → host-route check → boards; `SKIP_BOARDS=1` deploys only) | VERIFIED 2026-08-17 (M1-S5) — see the commands' Done rows in HANDOFF (u) |
| Boards only (M1-S5) | `make boards` (`python scripts/metabase_boards.py`; `--verify` is the read-only twin `verify-m1` uses) | VERIFIED 2026-08-17 (M1-S5): converges 17 cards + 2 dashboards from `analytics/metabase/boards/*.json`; idempotent BY NAME (second run updates in place, ids unchanged) |
| Gate check M1 | `make verify-m1` | RE-VERIFIED 2026-08-17 (M2-S1, after the ingest change): **37 `ok` sub-checks, 0 FAIL, exit 0** — leg 1 now reports `16 output(s) byte-identical`, and that number is finally the number the proof HASHED (it used to `grep -c` every line ending in `yes` across the whole log, so it printed 16 for 8 files; pinned by a test). VERIFIED 2026-08-17 (M1-S5): 9 sections, **30 sub-checks GREEN, exit 0, measured 98s**; RED-TEAMED by `kubectl -n metabase scale --replicas=0` → exit 2 naming exactly the 2 BI checks, other 28 still green, then restored → GREEN again. **No fast mode, no skip flag** — leg 1 deletes and rebuilds ~1 GB of processed parquet, because byte-identity checked against data that was never re-derived is not a check |
| Ask the analyst layer | `python -m taxi_mlops.data query "<SQL>"` (read-only) | VERIFIED 2026-08-16 (M1-S2): every figure in the Data Contract Review minutes came from this path; no raw parquet was read |
| Byte-identical rebuild (M1 gate leg) | `make rebuild-proof` (`DRY_RUN=1` previews) | VERIFIED 2026-08-16 (M1-S2): wiped `data/processed/`, rebuilt by ONE command from DVC-pinned raw, **8/8 outputs byte-identical**, confirmed twice — our sha256 table and `dvc status data/processed.dvc`. RED-TEAMED twice: tampered raw → refused at step 2 **without deleting anything** (`data/processed` still 8 files); tampered output → table prints `NO` naming `val/yellow_tripdata_2019-07.parquet`, exit 1. **WIDENED + RE-VERIFIED 2026-08-17 (M2-S1): 16/16** — it now wipes and re-derives `data/rejected/` too and asks DVC about BOTH `.dvc` files (`data/processed.dvc: up to date` · `data/rejected.dvc: up to date`). A proof that re-derives half a command's output proves half a command |
| Baselines + LightGBM v1 (M2-S2) | `python -m taxi_mlops.training train` (`--ablation` adds the log1p variant; `--train-months` is the sample-first override; `--no-mlflow` is a smoke test, never a result) | VERIFIED 2026-08-17 (M2-S2): 43,987,422 train rows, 4 MLflow runs in `m2-modeling`, `lightgbm-v1` logged WITH signature + input example (7 artifacts in MinIO). The two floors came back **7.8866** and **3.7170** val MAE — the EDA's SQL numbers to four decimals, from different code. Registry left EMPTY on purpose (S3's) |
| Train + gate + promote (M2-S3, hardened M3-S1) | `make train` (`--no-promote` prints the verdict only; `--hobble shuffled-target` is the red team; `--train-months` is GATE-DISQUALIFYING and `--no-gate` is the sampled smoke path; `--experiment`/`--story` label the runs; **exit 1 = refused · exit 2 = no verdict possible · exit 3 = no verdict issued**) | VERIFIED 2026-08-17 (M3-S1): full data 43,987,422 rows, 500/500 rounds, all four contenders through one evaluator, gate now judged against `baseline-group-median-od-fallback` (**3.3518** test) with the **incumbent** consulted (version 1, 3.2608 / 81.480%) → **PROMOTE +2.71%**, exit 0, `--no-promote` so nothing moved. Re-measured M2's numbers exactly (7.8866 · 3.5090 · 3.2608 · 81.480%). Sampled run refused in seconds, exit 2; `--no-gate` sample printed its table and exited 3 |
| Prove the gate can REFUSE | `make train-redteam` (`bash scripts/train_redteam.sh`) | VERIFIED 2026-08-17 (M2-S3): a challenger fitted on permuted train labels went through the SAME gate with promotion ENABLED → **REFUSE on both conditions** (−118.49% KPI-09, −32.018 points KPI-10), CLI exit 1, script inverted it to 0. Registry snapshot identical across the run (`versions=[] · alias @champion -> UNSET` before AND after). Hobbled run kept and tagged `red_team`/`hobbled`/`do_not_promote`; it is not a registry version |
| Score the champion, publish rows (M2-S4, floor-checked M3-S1) | `make predictions` (`python -m taxi_mlops.training predict`; `--no-write` prints the numbers and publishes nothing; `--floor-train-months` is the F-012 red team's lever) | VERIFIED 2026-08-17 (M2-S4) and re-verified under the new check (M3-S1): it now fits the floor the CHAMPION was gated against — read off the version's `gate_floor` tag, observed `baseline-group-median`, NOT the config's new floor — and refuses to write unless that floor re-scores to the version's `gate_floor_mae` |
| Reprint every number in the error memo | `uv run python scripts/error_memo_numbers.py [section…]` | VERIFIED 2026-08-17 (M2-S4): all 7 sections reproduce `docs/error_memo_m2.md` from `marts.error_segments` + the `predictions` view — and caught 4 last-digit rounding slips on its first run, which were fixed in the memo |
| Error-segment board (M2-S4) | `make boards` (same path as M1-S5; `--verify` is the read-only twin) | VERIFIED 2026-08-17 (M2-S4): `Error segments (M2)` created with **11 cards**, every card citing a KPI id and querying the `marts` warehouse; `--verify` green on all 3 dashboards incl. `card 'KPI-13 · what the booster buys, by hour of day (test)' RAN and returned 24 row(s)` and `no card claims KPI-09/KPI-10` |
| Zone centroids (M3-S2) | `make zones` (`uv run python scripts/derive_zone_centroids.py`; `ZONES_ARGS=--refresh` re-downloads) | VERIFIED 2026-08-17 (M3-S2): 263 zones from the sha256-pinned TLC shapefile, CRS **read from the .prj** (`NAD83 / New York Long Island (ftUS)`), landmarks JFK **0.63 km** · LGA **0.11 km** · EWR **0.26 km** from their published points, `.dbf` and `taxi_zone_lookup.csv` agree on borough+zone for all 263, every centroid inside the NYC bbox. Idempotent: re-run gives sha256 `37910367…` unchanged. RED-TEAMED by a **111 m** edit to one of 263 rows → the sha256-pin leg AND the byte-identity re-derivation leg both fail while all 11 semantic checks still pass (the landmark tolerance is 3 km), restore → 13/13 |
| Artisan ablation (M3-S3) | `make ablation` (15% sample, six arms) · `make ablation ABLATION_ARGS="--full-scale --sets v1,v1_g1,v1_g2,v2 --log-model"` (the confirmation) | VERIFIED 2026-08-17 (M3-S3): six sample arms in `m3-artisan` (557.1 s of fitting) then the four-arm confirmation on **43,987,422** rows (2,135.0 s) → **v1 3.4760 · g1 +1.77% · g2 +0.63% · v2 3.3905 (+2.46%, KPI-10 80.506%)**, v2 logged with signature + input example. v1 reproduced `3.47603843547682` across two invocations 71 min apart. Val only, registry untouched. **Run it detached** (`automation/run_detached.sh`) — a session that waits for it kills it (gotcha #45) |
| Prove a leaky aggregate flatters val and nothing else (M3-S3) | `make leakage-redteam` (`uv run python scripts/leakage_redteam.py`) | VERIFIED 2026-08-17 (M3-S3): the same tables fitted across the val month ON PURPOSE → **+0.0551 min on the month it saw, −0.1367 min on the untouched month** (2019-06, held out for the drill so the TEST month stays unread), inflation **+0.1917 min**. Arm B would have cleared DR-02's keep bar. `aggregates.fit` defaults `point_in_time=True`; only this script may pass False, and a test fails if the leaky switch stops leaking |
| Gate check M2 | `make verify-m2` | VERIFIED 2026-08-17 (M2-S5), **RE-VERIFIED and WIDENED 2026-08-17 (M3-S1): GREEN 54/54**, **RE-RUN GREEN 54/54 2026-08-17 (M3-S3)** after the feature-registry refactor and the borough fix (was 49 — five sub-checks added to §2, none removed). §2 now replays M3's transcripts too, WITH the incumbent each one records; pins the floor by name; and measures the DIRECTION of the floor change from two committed transcripts (`3.5090 -> 3.3518 on the same 5,950,708 rows`), because a floor swap is only not-a-loosening if the new floor is harder. It re-reads and re-reconciles, it NEVER re-fits. **RE-VERIFIED and REPAIRED 2026-08-18 (M3-S5): GREEN 55/55** — the first legitimate champion transition turned three §1 sub-checks RED for doing the right thing (F-017, gotchas #49/#50), and each M2-era literal was replaced by the property that holds at every champion: the floor must be a name `baselines.fit_floor` can rebuild · the run must be FINISHED and NAMESPACED · a `do_not_promote` mark counts unless its VALUE says no. One sub-check ADDED, none removed |
| Prove the M2 gate can go RED | `make verify-m2-redteam` (`bash scripts/verify_m2_redteam.sh`) | VERIFIED 2026-08-17 (M2-S5): deletes the `@champion` alias → **RED, exit 1, 4 FAILs**, the first naming `models:/nyc-taxi-eta@champion does not resolve`, **38 sub-checks still ran and passed**; alias restored by EXIT trap → **GREEN**. Deletes only the POINTER — no version, no run, no artifact |  **RE-RUN 2026-08-17 (M3-S1): PASSED, restored run GREEN at 54 sub-checks**
| Prove the gate refuses a WORSE-THAN-CHAMPION challenger (M3-S1) | `make gate-redteam` (`uv run python scripts/gate_redteam_incumbent.py`) | VERIFIED 2026-08-17 (M3-S1): a challenger built as the champion **+0.06 min** on every quote scored **3.2667 / 81.423%**, cleared the floor bar at **+2.54%**, and was **REFUSED on both incumbent conditions** against version 1's 3.2608 / 81.480% while the floor conditions still passed. The bypass (`incumbent_version=None`) was refused by `registry.promote`. Registry identical before and after (alias 1, versions [1]). ~6 min; it is a .py and not a heredoc because the OpenMP shim re-execs and stdin cannot be replayed (gotcha #37) |
| Prove a wrong-window floor cannot be published (M3-S1) | `make predictions-redteam` (`bash scripts/predictions_redteam.sh`) | VERIFIED 2026-08-17 (M3-S1): floor fitted on 2019-01 instead of six months → re-fit measured **4.1138** against the version's `gate_floor_mae` **3.5090** → **write REFUSED, exit 2**, and all three published files **byte-identical by sha256** before and after |
| Gate check M3 | `make verify-m3` | VERIFIED 2026-08-18 (M3-S5): **GREEN 46/46 in 4.7 s, exit 0**, 8 sections — dossier (20 candidates, source + leakage note each, all 3 HIGH-risk rows constrained to TRAIN months) · ablation (5 groups, both deltas, **DR-02's 0.50% bar RE-APPLIED to the table's own numbers reproduces all five verdicts**, 3 drops present, v2 == the survivors) · leakage drill (three numbers parse AND reconcile, `point_in_time=True` still the default, exactly one CALLER may flip it) · tuning (both sniper studies in Postgres at the count their JSON records, 6 PRUNED, the resume drill's kill survived) · **the five bake-off verdicts replayed through `gate.decide` on disk** · the four guards (F-011 both halves, val, flattering floor, F-008) · registry coherent with `bakeoff.json`'s recorded winner · F-013's one home. **Re-fits NOTHING** (M3 cost 12,447 s of fitting) and leaves the registry identical — checked: alias 2, versions [1,2]. No skip flag, no fast mode. Transcript: `docs/verify_m3_transcripts.md` §1 |
| Prove the M3 gate can go RED | `make verify-m3-redteam` (`bash scripts/verify_m3_redteam.sh`) | VERIFIED 2026-08-18 (M3-S5): rewrites ONE contender's measured KPI-09 in `automation/runs/m3s5/bakeoff.json` (`auto-on-v1` 3.5038 → 3.2000) and leaves its recorded verdict at REFUSE → **RED exit 1**, naming the row AND both verdicts, **the four UNTAMPERED replays still passing** (what separates a replay from a checksum: red on a WRONG number, not on any edit), **44 of 46 sub-checks still ran and passed**; restored from a byte copy under an EXIT trap and verified by sha256 (`c4a323ea072a…` before and after) → **GREEN 46/46**. Touches no model, no run, no registry, no study |
| Gate checks | `make verify-m0` … `verify-m8` | M0/M1/M2/M3 live; M4+ pending each milestone |
| FLAML scout (M3-S4) | `make automl AUTOML_ARGS="--set v1"` (`--time-budget` is a SMOKE override and says so; `--no-mlflow` is never a result) | SMOKED 2026-08-17 (M3-S4): 4 families ran against pandas 3.0.5 at a 40s override, leaderboard printed with every line labelled **scout-internal** (gotcha #15). The configured 1,800s runs land with the detached track |
| Optuna sniper (M3-S4) | `make tune TUNE_ARGS="--set v1 --scout <verdict.json>"` (TPE + MedianPruner from `configs/tuning.yaml`; `--budget-seconds` is DR-01's cap; the study is namespaced `m3-…`, gotcha #17) | SMOKED 2026-08-17 (M3-S4): 4 xgboost trials and 16 lgbm trials through Postgres storage with MLflow nested runs under one parent; **the DSN is built from `.env` in memory and a test walks every `configs/*.yaml` for a connection string** |
| Prove a study outlives its process (M3-S4) | `make tune-resume-drill` | VERIFIED 2026-08-17 (M3-S4): `kill -9` on the process group after 3 trials → `{'COMPLETE': 2, 'RUNNING': 1}` read back on a FRESH Postgres connection; the SAME command again (no resume flag) opened the study with 3 existing trials and finished **8 answered of 8, 1 dead trial reaped and retried, 0 stuck**. Its first run PASSED while silently losing a trial — that is gotcha #47 |
| Exercise the F-008 sampled-run guard (M3-S4) | `make f008-guard` | VERIFIED 2026-08-17 (M3-S4): `--train-months 2019-01 --no-promote` → **exit 2** (gate-disqualified) and `--train-months 2019-01 --no-gate` → **exit 3** (`[promote] SKIPPED — no verdict was issued`). PASS 2/2 |
| The whole automation track (M3-S4) | `make automation-track` — scout ×2 → sniper ×2 → full-data refit ×2, budget DECLARED in the script header before any result exists; **run it detached**; every phase SKIPS if its JSON exists | VERIFIED END TO END 2026-08-18 (M3-S4): five phases ran 2026-08-17 16:26→18:46Z (scout v1/v2, sniper v1/v2, refit v1) and the PO stopped the machine for the night; the SAME command on 2026-08-18 02:40Z skipped all five BY NAME and ran only the missing refit → `[track] finished 2026-08-18T02:59:07Z; 0 phase(s) failed`. **The resume cost one phase, not six.** Numbers in `docs/automation_track_m3.md` §6, one JSON per phase in `automation/runs/m3s4/` (six files). **9,133.8 s of fitting across six phases against a 9,000 s DR-01 share** — it goes over by 1.49%, and §6.5 says which phases and why |
| Run something that must OUTLIVE the session | `make detach NAME=<slug> ROLE=executor\|rev\|architect TARGET=<make target>` | VERIFIED 2026-08-17 (M3-S4): launched the automation track under `setsid`, `--then-schedule executor`. It is a make target because `run_detached.sh` is not on the session allowlist (F-001) and `make` is — an unattended session must never have to reach past the Makefile to obey gotcha #45 |
| Destroy | `make destroy` (`DRY_RUN=1` previews) | VERIFIED 2026-08-16 (M0-S4): full destroy→rebuild→`verify-m0` GREEN cycle, both helm releases back at REVISION 1. `.env` sha256 identical across the cycle (same credentials); the cluster's DATA is gone by design (pre-destroy MLflow experiment → `RESOURCE_DOES_NOT_EXIST`; PVCs die with the cluster). **`DRY_RUN=1` deleted the cluster until this story** — fixed and regression-pinned (F-004, gotcha #30); the preview now leaves a live cluster untouched |
| Chain kill switch | `touch automation/STOP` | VERIFIED 2026-08-16 (M0-S4 drill): scheduler refuses, exit 0, daily counter unmoved, no log created, no residue after `rm`. The harder half — STOP written AFTER a session is scheduled, and the daily cap — is covered by `tests/unit/test_chain_script.py` against a sandboxed scheduler with a fake `claude` |
| Chain next session | `automation/next_session.sh <executor\|rev\|architect> [delay]` | REAL-CLI proven 2026-08-16 (hello-chain fired +60s; `opus`→claude-opus-5; log+counter OK) |
| Pause / resume chain | `touch automation/STOP` / rm + reschedule | REAL-CLI proven 2026-08-16 (refusal printed, exit 0, cap not burned, no residue) |

## Conventions
- uv for env/deps; ruff (line 100); pytest markers: unit / integration / smoke.
- Conventional commits; one story per branch; PR per story with `role:XX` label.
- **Role rotation**: block header (PROMPTS.md Prompt D) at every switch; charter
  read at entry; ledgers written at exit; REV only ever in fresh sessions
  (Prompt C); producer ≠ approver on every signoff row.
- **Autonomous cadence (v3.0 — ORG.md rule 7, ADR-010)**: story-scoped fresh
  sessions chain via `automation/next_session.sh` (executor=opus · rev=opus ·
  architect=fable; each states its model first). ARCH authors every kickoff
  AND does boundary triage (no separate closure step). Direction forks WAIT
  in AWAITING_PO.md — never auto-proceed on a recommendation; hard-block
  classes never proceed at all (gotcha #23). Git autonomy granted: branch/PR/
  merge-on-green, lineage kept. Carries need QUOTED landings (gotcha #19).
  Controls: automation/STOP · daily cap 40 · logs in automation/logs/.
- src/taxi_mlops NEVER imports an orchestrator; pipelines/ imports src/, never
  the reverse. features/ is the only transform path for training AND serving.
- All knobs in configs/*.yaml; none hardcoded. Gates/SLOs/thresholds loosen only
  via PO fork.
- Marts boundary law (ADR-009, gotcha #22): analytics/dbt marts serve humans;
  model code never imports them — model-worthy aggregates graduate via the
  dossier + features path.
- Scout numbers are "scout-internal"; reported numbers come from
  taxi_mlops.training.evaluate only (gotcha #15).
- **Field-note law**: every story ends with its docs/LEARNING_GUIDE.md note
  before the next story starts.

## Known traps
Read docs/gotchas.md BEFORE first kubectl of any session. Top three for this
machine: repo-in-WSL2-fs (#1), .wslconfig memory (#2), Kaspersky TLS (#9).
New-in-v2: AutoML leaderboard (#15), dependency quarantine (#16), Optuna study
namespaces (#17), REV freshness (#18). Newest: Docker Desktop owns `kubectl`'s
symlink (#34), a test that parses a shell array truncated it at the first `)` in
a COMMENT and the survivors ran as commands (#35), dbt's partial-parse cache
makes a build a function of where somebody once stood (#38), two different
MLflow faults print the same `MLmodel` error — one is F-009, the other is a
client without MinIO credentials (#39), and **a number that has been through a
`%.4f` exists only at that precision, so comparing a fresh measurement against it
compares against rounding noise (#42 — it refused the champion against itself)**.
Newest, and both cost a session: **ending a turn kills every background task the
session started, so "I'll pick this up when the run reports" destroys the run
(#45 — the chain died for 38 minutes; `automation/run_detached.sh` and the cron
`watchdog.sh` are the answer)**, and a reference file can spell its own null two
ways while the comment above the loop swears it does not (#46). Newest: **a
SIGKILLed Optuna trial stays RUNNING in the storage forever, so a resumed study
loses one trial per kill and the drill that finds this is the one that PASSED
(#47)**, and **the launcher for resumable jobs TRUNCATED the log of the run it
was resuming — one line before correctly skipping the phases that log described
(#48; when a job is built to be re-run, audit what its launcher does to state
that already exists)**. Newest, and they are the same lesson twice: **a tag named
`do_not_promote` whose VALUE is "no" reads as a refusal to any check that tests
for the KEY (#49)**, and **three `verify-m2` assertions encoded M2-era facts as
literals, so the first legitimate champion transition turned them RED for doing
the right thing (#50) — a guard that fires when the program behaves correctly
trains the next session to edit assertions, which is how a guard becomes a
formality. When a guard goes red, ask FIRST whether the thing it names actually
changed for the worse.**
