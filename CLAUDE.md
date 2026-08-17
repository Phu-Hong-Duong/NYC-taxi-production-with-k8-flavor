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
| (FLAML/Optuna rows land at their milestones) | | | |

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
| Gate checks | `make verify-m1` … `verify-m8` | pending each milestone |
| Scout / sniper | `make automl` / `make tune` | pending M3 |
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
a COMMENT and the survivors ran as commands (#35).
