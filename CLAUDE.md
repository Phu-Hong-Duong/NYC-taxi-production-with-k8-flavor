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
  **Amended 2026-08-24 (program close): the PO re-granted WSL to 40 GB on
  2026-08-22 (`free -h` reads 39Gi live); the full platform runs inside it.
  Gotcha #2 carries the same dated note.**
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
| Flyte chart | **`flyteorg/flyte-binary` v2.0.42** — and the name inverts the intuition: THIS is the Flyte **2.x** line (unified `flyte-core-components` manager), while `flyteorg/flyte-core`/`flyteorg/flyte` are **1.16.x**. ADR-002's pre-approved fallback is `flyte-binary` **v1.5.1** (appVersion 1.16.0) | 2026-08-18 | `helm search repo flyteorg --versions` (M4-S2), read back with `helm -n flyte list`. Pinned in `scripts/deploy_flyte.sh` beside the fallback version |
| Flyte server image | `cr.flyte.org/flyteorg/flyte-binary-v2:v2.0.42` | 2026-08-18 | chart-pinned (M4-S2); one Deployment, plus `flyteconnector` (chart default, unused here — left on deliberately, see the values file) |
| Flyte console image | `ghcr.io/unionai-oss/flyteconsole-v2:latest@sha256:3cea5ec7ea1ebb2d2b392d60988c028ff45965e3a7eecb0e1ba51d7ec81e6cdb` — TAG AND DIGEST, the Metabase precedent | 2026-08-18 | `docker buildx imagetools inspect` (M4-S2). The chart's default is the bare tag `latest`, which is not a pin at all. **99 MB, and it took 9m49s to pull** — which is why `deploy_flyte.sh` waits 20m, not 10m |
| Task image base | `python:3.12.14-slim-trixie@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a` — TAG AND DIGEST (the Metabase precedent). `trixie` = Debian 13, which is what the kind nodes already run, so one libc family across node and workload | 2026-08-18 | `docker pull` + `docker image inspect` (M4-S3). Interpreter in-image is CPython 3.12.14 `[GCC 14.2.0]`; the HOST's 3.12.14 is uv-managed python-build-standalone `[Clang 22.1.3]` — same version, different compiler, and the graph is identical package-for-package (215/215, checked), which is what actually determines the numbers |
| uv (in the task image) | **0.12.5**, `ghcr.io/astral-sh/uv:0.12.5@sha256:e85be844203885286c60ffad8a858d48afb6c5a5c237ca0e67f12e74b8f174b1` — the same version that resolved `uv.lock` on the host | 2026-08-18 | M4-S3. A different uv could legally re-resolve; same binary + `--frozen` means it cannot |
| libgomp (in the task image) | **libgomp1 14.2.0-19** (Debian trixie), a real apt package — **D-004's closure** | 2026-08-18 | `dpkg-query` INSIDE the image (M4-S3). The shim stays in the code as the laptop path; `make image-smoke` proves it never fires in the container and `make image-smoke-redteam` proves that check can go red |
| Task image | `taxi-mlops-pipeline:<git-short-sha>` (`-dirty` when the tree is not clean) · **737 MiB** content / **~1,898 MB** unpacked · on all 3 nodes by `kind load` | 2026-08-18 | `make image-load` (M4-S3); current ref + both image ids in `automation/runs/m4-image/image.json`. `nvidia-nccl-cu13` is 241 MB of it (hard dep of xgboost on linux, never loaded) — noted, not fought |
| Flyte SDK / CLI | **`flyte` 2.6.1** (brings `flyteidl2` **2.0.42** — an exact match to the chart) | 2026-08-18 | `uv add "flyte>=2.6,<3"` (M4-S2). **Gotcha #36 checked at add time: 29 packages installed, only the project rebuilt, and pandas 3.0.5 · numpy 2.5.2 · scikit-learn 1.9.0 · mlflow-skinny 3.15.1 · lightgbm 4.7.0 · xgboost 3.4.1 all unchanged.** The CLI is `flyte` (verb/noun), NOT `pyflyte`/`flytectl` — those are the 1.x tools |
| Data stager image | `busybox:1.38.0@sha256:dc2d74b28e4cf8984fa52af1f39bc7c3d9c73760b41a74d629f5d11b1ab28616` — TAG AND DIGEST | 2026-08-18 | `docker image inspect --format '{{index .RepoDigests 0}}'` (M4-S4). The short-lived pod `make stage-data` uses to untar the data trees onto the PVC. busybox because the whole job is `tar -x`/`du`/`find`, and because the MLflow chart's db-check init container already pinned this version at M0 — a version this program has, not a new dependency |
| MLflow `serverAllowedHosts` | 8 entries: `localhost`/`127.0.0.1`/`mlflow.mlflow.svc.cluster.local`/`mlflow.mlflow`, **each with and without `:5000`** | 2026-08-18 | `infra/helm/mlflow/values.yaml` (M4-S4, **F-025**). Not a version pin but it belongs beside one: setting this value REPLACES MLflow's default list, and the uvicorn middleware compares the WHOLE Host header — port included — so a list of bare hostnames 403s every host-side client. Both forms, always |
| ingress-nginx chart | **4.15.1** (appVersion **1.15.1**), image `registry.k8s.io/ingress-nginx/controller:v1.15.1@sha256:594ceea76b01c592858f803f9ff4d2cb40542cae2060410b2c95f75907d659e1` — the chart pins by TAG AND DIGEST itself | 2026-08-19 | `helm search repo ingress-nginx --versions` (M5-S1), read back with `helm list -A`. **Not** the upstream `deploy/static/provider/kind` manifest: it selects `ingress-ready=true`, a label kind writes only when the kind config asks and ours does not — and the kind config is read at cluster-CREATE only, so the label is unavailable at a price M5 will not pay |
| cert-manager chart | **v1.21.1** (appVersion v1.21.1), images `quay.io/jetstack/cert-manager-{controller,webhook,cainjector,startupapicheck}:v1.21.1` | 2026-08-19 | `helm search repo jetstack --versions` (M5-S1). It exists for ONE reason: KServe's controller runs admission/conversion webhooks, and a webhook is an HTTPS endpoint the API server calls. `crds.enabled: true` (the release owns them), `crds.keep: false` |
| KServe charts | **`oci://ghcr.io/kserve/charts/kserve-crd` and `…/kserve-resources`, both v0.20.0** — OCI, so the version IS the tag and there is no repo index to drift. Digests `sha256:92deb742d22a…` (crd) and `sha256:956c4860374f…` (resources) | 2026-08-19 | `helm show chart oci://…` + `curl` against the KServe releases API (M5-S1; v0.20.0 released 2026-08-06). Images: `kserve/kserve-controller:v0.20.0` · `kserve/storage-initializer:v0.20.0` · `quay.io/brancz/kube-rbac-proxy:v0.18.0`. **Six CRDs register cleanly on Kubernetes v1.36.1** — the M5 kickoff's risk R1 did not materialise and ADR-004's plain-mlserver fallback stays armed and unspent |
| Predictor image | `taxi-mlops-predictor:mlserver-1.7.1-lgb-4.7.0` — built from `docker.io/seldonio/mlserver:1.7.1-mlflow@sha256:492c8bbac687b148ad81a57278368f0aaaa2b3f72b09302419258d36058fe000` (TAG AND DIGEST, the Metabase precedent) plus **one** package, `lightgbm==4.7.0`. **720 MB on each node**, delivered by `kind load` (D-001's mechanism) to all 3 — required, not convenient: M5-S4 kills the predictor and the replacement may land elsewhere | 2026-08-19 | `docker image inspect` + `crictl images` on the nodes (M5-S2). KServe's own kustomization pins `mlserver:1.7.1`; the derived image exists because the stock one **cannot load this champion** — `ModuleNotFoundError: No module named 'lightgbm'`, measured in one `docker run` before a manifest was written. Its base carries **Python 3.10.12 · pandas 2.2.3 · numpy 2.2.6** against training's 3.12.14 / 3.0.5 / 2.5.2, unfixable by pinning (mlserver 1.7.1 is a py3.10 conda base and full `mlflow` pins `pandas<3`) — and it does not matter because none of the three is on the numeric path: the matrix is built client-side, the wire carries its dtypes, and **lightgbm is 4.7.0 on both sides**. Measured, not argued: one row matched bit for bit |
| ClusterServingRuntime | **`taxi-mlserver`, ours** (`infra/manifests/serving-runtime-mlserver.yaml`), ONE supportedModelFormat (`mlflow`), protocol **v2**, `imagePullPolicy: IfNotPresent` | 2026-08-19 | M5-S2. **KServe v0.20.0's `kserve-resources` chart ships NO runtimes** — `kubectl get clusterservingruntimes` said `No resources found` and `helm template … \| grep -c 'kind: ClusterServingRuntime'` returned **0**. Upstream keeps them as plain manifests in `config/runtimes/`, image-substituted at release time, so a runtime is ours to declare either way; declaring it puts the image in the same diff as every other pin instead of arriving through a `newTag: latest` |
| MinIO serving identity | user `serving`, custom policy **`serving-readonly`** — `GetObject` + `GetBucketLocation` + `ListBucket` on `mlflow-artifacts` ONLY | 2026-08-19 | M5-S2. Not a version pin, but it belongs beside one: MinIO's built-in `readonly` omits **`s3:ListBucket`**, which is what KServe's storage-initializer HEADs the bucket with — so a correct install 403s on a user that exists under a policy called "readonly", and it reads exactly like a wrong password. The custom policy is strictly BETTER than what it replaces: read-only and scoped to one bucket, so a leaked serving credential cannot see `flyte-data` at all |
| Prometheus chart | **`prometheus-community/prometheus` 29.27.0** (appVersion **v3.14.0**), images `quay.io/prometheus/prometheus:v3.14.0` + `quay.io/prometheus-operator/prometheus-config-reloader:v0.93.1` (chart-pinned). Subcharts: alertmanager **ON**, kube-state-metrics **ON**, **node-exporter OFF**, **pushgateway OFF** | 2026-08-19 | `helm search repo prometheus-community --versions` (M6-S1), read back with `helm -n monitoring list`. **NOT `kube-prometheus-stack`**: that chart brings the operator plus ~10 CRDs whose job is to turn ServiceMonitor objects into the nine-line scrape config this repo carries in a values file — and CRDs are cluster-scoped state on a cluster that must not be rebuilt, while M6-S2's alert rules would become PrometheusRule objects LIVING IN THE CLUSTER when the rule since M1-S5 is that what renders is checked in. It is the recorded 3-attempt-wall fallback. node-exporter is off because nothing in M6 reads a host-level metric (container CPU and CFS throttling come from the kubelet's cAdvisor, already scraped); pushgateway is off because it is M7's |
| Prometheus `global.scrape_interval` | **15s** (chart default is **1m**) — and it was a DEFECT before it was a preference | 2026-08-19 | M6-S1. A `rate(x[1m])` needs two samples inside its window, so at the chart default both container panels on the serving board evaluated to **nothing** and the accept check reported "0 series", which reads exactly like an idle container. M6's events are minutes long (a canary shift, a kill, a gameday injection); a sampling interval of the same order as the event cannot describe it |
| Grafana chart | **`grafana/grafana` 10.5.15** (appVersion **12.3.1**) | 2026-08-19 | `helm search repo grafana --versions` (M6-S1). Persistence **OFF** deliberately — the inverse of M1-S5's Metabase decision and for the same reason: Metabase's H2 file held the BOARDS, so losing it lost the work; here the boards and the datasource are provisioned from git on every start, so Grafana's sqlite holds only a human's UI preferences. Admin credential from Secret `monitoring/grafana-admin` (`admin.existingSecret`), never `--set` (readable by `ps`) and never the chart default (a published password) |
| Predictor metrics endpoint | **`:8082/metrics`, PROBED** — and KServe's own pod annotation says **8080**, which returns **404** on this runtime | 2026-08-19 | `make probe-mlserver-metrics` against the live pod (M6-S1, **F-034**). 24 series, of which the load-bearing ones are `rest_server_requests_total{status_code=…}` (the 5xx-vs-422 split at source), `rest_server_request_duration_seconds_bucket` (a histogram, so a real server-side p95) and `model_infer_request_{success,failure}_total`. **The model VERSION is NOT in any mlserver metric** (`version="None"`) — so M6-S2's A-4 needs another source, and the response body is it |
| ingress-nginx `updateStrategy` | **`Recreate`, and it is FORCED** (chart default is RollingUpdate) | 2026-08-19 | M6-S1, **F-033**. `hostPort` + `replicaCount: 1` + a single-node `nodeSelector` means the surge pod can never bind port 80 while the old pod holds it, so a RollingUpdate deadlocks — observed Pending for 10 minutes with the route serving 840/840 and the helm upgrade heading for its 20m timeout. Honest cost, unavoidable rather than chosen: every change to that Deployment now costs a real outage of the only route in. **Measured: 15.0 s** |
| Predictor CPU **request** | **1500m** (limit unchanged at **2**; memory request unchanged at 1Gi) — was `200m`, an under-reservation of ~6.5× against M5-S4's measured **1.31 cores** at the SLO's own load shape | 2026-08-19 | `infra/manifests/inferenceservice-champion.yaml` (M6-S2), read back off the live Deployment. Argued from the measurement **plus ~15%**, never set equal to it, and deliberately BELOW the limit so the pod stays **Burstable**: request == limit would make it Guaranteed and reserve the saturation ceiling (~6 req/s) for load the SLO does not promise to serve, on a node with 20 allocatable cores. **Applying it cost 0.5 s of route unavailability, not the ~15 s three prior measurements implied** — gotcha #80 |
| Serving alert rules | **7 rules across 6 signal ids** (A-1, A-2, A-3, A-5 ×2, A-6, A-7) in `infra/monitoring/alerting_rules.yml`, a plain Prometheus rules file · thresholds **5%** beyond 250 ms · **10%** edge 5xx · **1%** 4xx · **<1** available replica · **>2** restarts/15 m · **0.90** CFS-throttled fraction | 2026-08-19 | M6-S2, read back off `/api/v1/rules` (7 loaded, `health=ok`). Every threshold's argument lives in `docs/slo_serving.md`, and `scripts/render_alert_rules.py` REFUSES a rule with no `annotations.why`. **A-4 and A-3's client half have NO rule and that is recorded** (F-035) |
| KServe `deploymentMode` | **`RawDeployment`** (ADR-004's Standard mode) — the chart default is `Knative` | 2026-08-19 | `infra/helm/kserve/values.yaml`, and READ BACK off `configmap/inferenceservice-config` by `scripts/deploy_serving.sh` rather than off the values that were submitted. Honest cost, landing on M6: **Standard mode has no canary** — `canaryTrafficPercent` requires Serverless (the prior-art ADOPT) |

| trivy | **0.74.0**, sha256 of the installed binary `d89bcc6510a267f11b773398cbf1be5520ce39f9e8b6633178c4487f05b7d791` | 2026-08-24 | `make security-tools` (M9-S9). Into `~/.local/bin`, the M0-S1 precedent. The VERSION is pinned in `scripts/security_tools.sh` and never resolved from `latest`, and it is read BACK off the binary. What the publisher's `*_checksums.txt` proves is stated in the record itself: same origin, same TLS session, so it detects corruption and NOT tampering — the durable pin is the sha256, recorded in a tracked file. Sigstore attestations are NOT verified (that needs `cosign`, a third binary this program is not adding), recorded as a limit |
| gitleaks | **8.30.1**, sha256 `88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509` | 2026-08-24 | `make security-tools` (M9-S9). The secret scanner; the history leg runs it with `--log-opts='--all --full-history'`, which walks every ref and not just HEAD's ancestry — a secret removed from `main` by a later commit still lives in the objects the old commit points at, and that is what publishing exposes |
| Redis (the Feast ONLINE store) | **`redis:8.2-alpine@sha256:30abb90e62f14b737010746def3ba99cc79fe19dcdb3d37b41f21fc62e7da19d`** — TAG AND DIGEST, the Metabase precedent. Plain manifest (`infra/manifests/redis.yaml`), not a chart — the header says why. `maxmemory 512mb` + **`maxmemory-policy noeviction`** (a correctness setting, not tuning) · RDB `--save "60 1000"` onto a 1Gi PVC · `strategy: Recreate` · **no hostPort** | 2026-08-21 | `docker image inspect` (M8-S4), read back off the live Deployment and off the running server with `redis-cli CONFIG GET`. ADR-012 records why it is Redis and not sqlite (two-sided reachability) and not Postgres (blast radius: the ONE Postgres holds five irreplaceable tenants and an online store is the opposite state class) |
| redis / hiredis (in the QUARANTINE only) | **`redis==7.4.1` · `hiredis==3.4.1`** — feast's own `[redis]` extra (`redis<8,>=4.2.2`, `hiredis<4,>=2.0.0`, read off feast's metadata) | 2026-08-21 | M8-S4. The only two lines `infra/feast/requirements-feast.txt` gained (+2/−0, hand-inserted in sorted position — see F-057 for why not by regeneration), and `scripts/feast_quarantine.sh`'s `FEAST_PIN` is now `feast[redis]==0.66.0` so a future `--resolve` produces the set the pin file already holds. **`uv.lock` byte-identical to the `m7-closed` tag across the whole story** |

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
  docs, **RECORDED — and, from M5-S1, COMMITTED — JSON** (the row said
  "committed" until M4-S5 leg 3 found `automation/runs/` gitignored and
  corrected it to "recorded"; **F-029** option A then made the correction moot
  the right way round, by tracking the verdict JSONs), the
  Optuna storage and the registry, and **replays**:
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

## The honest holdout and the task graph (M4-S1) — what the gate may claim, and where the pipeline's seams are
- **F-018 CLOSED, and the fix is an ORDERING, not a key.** The bake-off used to
  pick its winner with `min(…, key=… metrics["test"].mae)` — five contenders read
  on the untouched month, lowest takes the alias — while `gate.verdict_lines`
  printed that the holdout was "untouched by training **and by selection**".
  Changing `"test"` to `"val"` would have left the ranking sitting AFTER both
  splits were scored, in a scope where a holdout number exists and only politeness
  stops its use. So `_select_winner` now runs **inside the val pass**, before the
  holdout parquet is loaded: there is no test number in existence to rank on.
  `SELECTION_SPLIT = "val"` carries the argument; the payload records
  `winner_selected_on`; the floor stays out of the ranking (it is the BAR) while
  keeping its own verdict.
- **The gate stopped claiming what only its caller can know** (`gate.py` property
  7). Training-purity the gate vouches for — it refuses metrics from any other
  split. Selection-purity is a fact about the CALLER's process. So
  `verdict_lines(decision, *, holdout_untouched_by_selection=False)`: the default
  is the weaker, always-true sentence, `make train` and the incumbent red team
  earn the strong one (one challenger, no ranking step), and a bake-off does not.
  Both forms keep the shape `verify-m2` §2 parses out of the committed M2/M3
  transcripts — a corrected claim must not orphan the record it was made in.
- **The M3 record was corrected, never rewritten.** `bakeoff.json` is
  byte-unchanged, nothing was re-fitted, and `docs/bakeoff_m3.md` §3 carries a
  DATED note that leaves the false five words standing above it. The champion
  survives its own method defect because val and test ranked identically — which
  the memo had already recorded, and which is exactly why the defect went unseen.
- **The regression test makes the two splits DISAGREE on purpose.** A fixture
  built from M3-S5's real numbers passes under BOTH rules and proves nothing.
  The companion test is structural (AST): `_select_winner` is called once, inside
  the split loop, under the `split == "val"` guard — because no behavioural test
  can catch the call drifting back below the holdout pass when the splits agree.
- **`pipelines/tasks.py` is the six-stage graph as plain Python**, typed in and
  out, every body a call into `taxi_mlops` (no logic moves). Two decisions worth
  re-reading before M4-S4: **the train/evaluate/register seam is where the CODE's
  seam is** (`run.run()` fits, scores and gates in one call, so `train` runs it
  and writes a run MANIFEST; the other two read the manifest, which is a JSON path
  because at S4 they are separate pods) and **a REFUSE is a return value, never an
  exception** — a refused challenger is a successful run of a working gate, and
  modelling it as a task failure attaches a retry to the program's one "no". The
  CLI's exit-code mapping is stated ONCE, in `RegisterResult.exit_code`.
- **No stage can move `@champion`**: `train` passes `promote=False`
  unconditionally and has NO `promote` parameter (a law with a keyword argument is
  a default); `register`'s promoting branch is deliberately unbuilt while F-016 is
  on the PO's desk, and when built must call `run._promote`, never a second path.
- **F-019 got a TRIPWIRE, not a fix** — one test builds the configured set for a
  2026-dated request and asserts the raise names `us_federal_holidays.csv` and
  both years. The extend-vs-policy decision is M5's, with the runbook in hand.
- **F-022 (new, blocking at M7): `scripts/bakeoff_m3.py` has been un-runnable
  since its own `--promote-winner` moved the alias.** `champion v1` resolves by
  ALIAS (deliberately — "the bake-off judges what is actually serving") while its
  Spec pre-registers `feature_set="v1"`; the alias now points at a v2 model, so
  `_load_booster` refuses. Pre-existing, found because M4-S1 tried to smoke the
  repaired script. Nothing re-runs a bake-off, and `verify-m3` §5 REPLAYS the
  recorded verdicts rather than re-running it, so nothing caught it.

## The lifeboat, the holder-aware port guard, and Flyte on the cluster (M4-S2)
- **`make backup` is the platform's only copy that survives the cluster**, and it
  ran BEFORE Flyte became the fifth tenant. It **enumerates its targets from the
  server** — every non-template database, every bucket — because a hardcoded list
  is a twin of `postgres_databases.sh` and a backup whose target list drifts
  succeeds, prints a size, and omits what somebody added last month. This story
  is its own proof: `flyte` and `flyte-data` are covered by the next run because
  nobody had to remember them. Observed: 5 databases + 105 objects, **1.5 GiB**.
- **Every dump is proven COMPLETE, host-side, over every byte**: `gzip -t` (CRC)
  plus pg_dump's own `-- PostgreSQL database dump complete`. Both legs were
  proven against a **deliberately truncated copy** before being trusted. The
  first design — `-Fc` + `pg_restore --list` over `kubectl exec -i` — was
  replaced, not tuned: a custom archive's TOC is at the FRONT, so `--list`
  succeeds on a file whose tail was never written (gotcha #54), and it hung on a
  1 MB dump having worked on a 1.2 GB one.
- **RESTORE IS SCRATCH-REHEARSED (2026-08-19, M6-S5) AND NO FURTHER, and every
  artifact says exactly that** (script header, the `MANIFEST.txt` text, the
  **line the script PRINTS at runtime**, the ledger rows, this row) — and that
  sentence was FALSE for a day: the runtime `echo` and the deployments ledger
  were still on the old label when `make verify-m6` §7 asked (**F-044**, gotcha
  **#91**). The check is what makes the claim falsifiable now. The three small irreplaceable dumps load into SCRATCH
  databases and check out; a full restore over a DEAD platform has still never
  been performed and needs a PO-sanctioned rebuild. Same-disk limit as the DVC
  remote. The label moved one notch — it did not go green.
- **Honest cost passed to M7**: `marts` is 1.2 GiB and **210 s** of the ~4 minute
  run and is the ONE database already provably rebuildable from DVC pins
  (M1-S5's fresh-volume proof); the other four total **377 KiB, under 2 s**, and
  are the irreplaceable ones. Every database is dumped as the kickoff specifies.
- **Flyte 2 is `flyteorg/flyte-binary` v2.0.42** — the chart names invert the
  intuition (`flyte-core`/`flyte` are the 1.16.x line). It needs **ONE** database,
  not the two the kickoff budgeted: the unified binary reads a single
  `runs.database`, so D-002 gained one line and held a **fourth** time. Its blob
  store is the existing MinIO in a NEW bucket under a NEW identity — a leaked
  orchestrator credential must not reach the registry's artifacts.
- **The first install failed for a reason that was not Flyte**: `context deadline
  exceeded` at `--wait --timeout 10m` while all three pods were healthy — the
  99 MB console image took **9m49s** to pull. Timeout is now 20m with the
  measurement beside it. The re-run is the idempotence evidence: all three
  deployments "successfully rolled out" while every pod was **17 minutes old**.
- **No secret reaches a command line**: the chart renders its DB password and S3
  key out of VALUES, so the deploy writes a mode-600 temp overlay and deletes it
  on EXIT. `DRY_RUN=1` mutates nothing, helm upgrades included (gotcha #30).
- **The hello-workflow does NOT complete — F-023, wall recorded at 5 attempts.**
  The CLI reaches the control plane (project created, image resolved, bundle
  built) and dies uploading the bundle: the blob store is ONE MinIO with TWO
  names, and the client is handed the in-cluster one. Setting the SDK's
  documented `FLYTE_AWS_ENDPOINT` did not change the symptom. **ADR-002's
  fallback is NOT executed** — its trigger is "deployment or MLflow interop", and
  deployment succeeded (`/healthz` 200, helm `deployed`). Next probes, in order,
  are recorded in the finding so nobody restarts the search.

## The task image (M4-S3) — what it contains, how it reaches the nodes, and how D-004 died
- **`make image-load` is the whole path**: build → `kind load` → read back off
  every node with the nodes' OWN tool (`docker exec <node> crictl images`), each
  node's image id printed BEFORE and after so an idempotent re-load reads
  `(unchanged)` instead of being asserted. `make image-build` stops before the
  cluster; `DRY_RUN=1` mutates nothing (gotcha #30's rule, pinned by a test).
- **The tag is the git short sha, and that is a correctness property.** k8s pulls
  `IfNotPresent` for any non-`:latest` tag and `kind load` writes into containerd
  BY TAG, so a mutable tag gives you nodes holding last week's bytes under this
  week's name with nothing saying so. An immutable tag turns a stale node into a
  MISSING image — a loud `ImagePullBackOff`, not a wrong number. `-dirty` says
  the image carries uncommitted work and must not back a verdict. A test refuses
  `:latest`. **Two ids, both legitimately different**: docker names a BuildKit
  build by its manifest-LIST digest, containerd by its CONFIG digest; both are in
  `automation/runs/m4-image/image.json`.
- **D-001 DECIDED: `kind load`, with the registry pattern deferred WITH a date
  and a trigger** (`docker/DECISION-D001-image-delivery.md`). `containerdConfig-
  Patches` lives in the kind config, the kind config is read only at cluster-
  CREATE, and this cluster's PVCs are the only copy of the registry — so the
  better option is unavailable at a price M4 may pay. It lands at the next
  PO-sanctioned rebuild (the same event that owes Flyte its declared 8080 route);
  the trigger that makes it worth it is **image churn**. `infra/kind/kind-
  config.yaml`'s `TODO(M4)` is now a pointer to that note.
- **D-004 CLOSED by evidence, and by evidence that the evidence can fail.**
  `libgomp1` is a real package; `make image-smoke` runs **10 checks inside the
  container** — `dpkg-query` says installed, `ldconfig` resolves it from a system
  lib dir and not a wheel, `openmp_status()` is `(True, 'system libgomp.so.1')`
  on the FIRST line, `python -m taxi_mlops.training.openmp_probe` prints one line
  with **no `[openmp]` announcement**, and `/app/.venv/lib/openmp` does not exist
  even though both the xgboost and scikit-learn wheels still ship a borrowable
  copy. That last pair is NEGATIVE evidence, which is the only shape that can
  retire this debt — the shim WORKS, so a debt that keeps working never closes.
  **`make image-smoke-redteam` masks the system library with an EMPTY FILE in ONE
  `--rm` container** (image, nodes and cluster untouched — the alias-deletion
  shape) and all three flip; a check that stays green under the mask fails the
  drill, exit code inverted like `marts-redteam`'s.
- **The image contains what git contains.** `.dockerignore` mirrors the repo's own
  ignore rules and a test asserts it BOTH ways: everything `data/.gitignore` names
  is excluded, and `data/reference/` is NOT. The first draft excluded `data/`
  wholesale and produced an image that imports every module and cannot build a
  feature — 1.1 MB under `data/` is committed lookup tables (zone centroids, TLC
  lookup, the pinned shapefile, the holiday table). **The in-image unit suite is
  what caught it: 28 failed + 10 errors against 452 passed.** Same draft's
  `.env.*` glob ate the committed `.env.example`. Data reaches tasks at RUN time —
  M4-S4's decision (MinIO or a staged PVC); `kind extraMounts` is a config edit
  and therefore forbidden, exactly like the registry pattern.
- **pytest is installed in the image on purpose** — check 6 runs `tests/unit`
  in-image (471 passed, 6 skipped) and a separate "test stage" would prove a suite
  passes in an image that is not the one that ships. Check 7 runs a real stage:
  `pipelines.tasks.validate('2019-01')` puts 7,584,656 rows back through the
  output contract, reading the host's DVC-pinned tree bind-mounted READ-ONLY.
- **Two build lessons with numbers.** `chown -R` at the end of a Dockerfile was a
  **1.7 GB duplicate layer** costing **139 s** (gotcha #57): creating the non-root
  user BEFORE installing anything gave the same image at 736 MiB instead of 1408.
  It hid because `docker image inspect .Size` is the CONTENT size under Docker
  29's containerd store, so the script now prints content AND unpacked. And
  `bash -lc` in a container is a trap (gotcha #56): a login shell rebuilds PATH
  and drops `/app/.venv/bin`, so `python` becomes the base interpreter — it cost
  one wrong RED verdict in the drill.
- **F-024, found by the drill and fixed the same session**: the shim could never
  re-exec a `python -c` invocation (CPython keeps no `-c` source string), so it
  announced success and then printed `Argument expected for the -c option`.
  Present since M2-S2, reproduced on the host, blast radius = ad-hoc probes only.
  It now REFUSES that form before mutating anything and names the three ways out;
  `openmp_probe` is the `-m`-runnable replacement, which is what the smoke uses.


## The pipeline on-cluster (M4-S4) — F-023's real cause, how a task pod is wired, and the checkers that lied
- **F-023 CLOSED, and the finding's own probe 2 was impossible.** The client never
  BUILDS an upload URL — it asks the dataproxy for one and PUTs to the
  `signed_url` the SERVER mints (`CreateUploadLocationResponse`), which is exactly
  why M4-S2's `FLYTE_AWS_ENDPOINT` attempts changed nothing. The recorded probe
  "point both sides at `<node-ip>:30900`" has no answer on this machine: from WSL
  `172.19.0.3:30900` and even `172.19.0.3:6443` return **000**, because kubectl
  reaches the cluster through a docker-PUBLISHED loopback port (`127.0.0.1:35553`)
  and the docker bridge is not routable from this side. Fixed with flytestdlib's
  own lever, `storage.signedUrl.stowConfigOverride` — which the 2.x CHART renders
  no value for but the 2.x BINARY carries (`grep -ao "stowConfigOverride"
  /usr/local/bin/flyte` hits) — supplied through `configuration.inline`. It
  changes the SIGNING endpoint only; pods keep the in-cluster name. **ADR-002's
  fallback was not executed and stays armed.**
- **`infra/manifests/flyte-task-podtemplate.yaml` is "what a task pod in this
  program looks like"**, named once by `plugins.k8s.default-pod-template-name` and
  by every `TaskEnvironment`. It carries the MinIO identity, the MLflow route,
  `imagePullPolicy: IfNotPresent` and the data volume — so a task added at M7
  inherits all of it by naming one string, and `pipelines/flyte/workflows.py`
  contains no endpoint at all. **The container must be named `default`** (the k8s
  plugin's contract). **Three storage configs already existed and none of them
  reached the process that runs our code**: the ConfigMap configures the server,
  the copilot Secret the sidecar, the overlay helm — while the Flyte 2 python
  runtime builds its own `flyte.storage.S3` from ITS environment and, unset, fell
  through to the AWS credential chain: `PUT http://169.254.169.254/latest/api/token`,
  i.e. a task that ran perfectly and had nowhere to put its result. The inline
  `plugins.k8s` block was checked for CLOBBERING the chart's: a live task pod
  carries both sets (`_U_EP_OVERRIDE` and `FLYTE_AWS_*`), so it deep-merged.
- **Data reaches tasks on a staged PVC, mounted by SUBPATH** (`make stage-data`,
  1.8G, verified by per-tree FILE COUNTS — 8/16/8 host == volume — because a
  killed stream leaves a tree that exists and is wrong). Subpath and not
  `/app/data`: that directory in the image holds the committed `data/reference/`
  lookup tables, and one mount over it rebuilds gotcha #58 exactly. **The rejected
  option is named**: tasks-read-from-MinIO is what M7 will want, and it is not a
  platform change but a rewrite of `taxi_mlops`'s IO, in the milestone whose
  premise is that `src/` does not move.
- **The green run is SAMPLED and says so.** `make pipeline MONTH=2019-01
  TRAIN_MONTHS=2019-01` → six stages on-cluster, ingest **7,696,617 → 7,584,656
  rows, 1.4547% rejected** (M4-S1's host rehearsal reproduced TO THE ROW by the
  same code in a container), train `lightgbm-v1` in **869.7 s**, and register
  returning **`NO_VERDICT`** as data — a green pipeline with no verdict, which is
  F-008 honored by construction. `@champion` read before and after by the runner:
  version 2, and a move is exit 2, not a warning. The **full-data** run and the
  **cache-hit rerun** are NOT done — see `docs/pipeline_m4.md` §8.
- **The manifest's CONTENT travels between stages, not its path.** M4-S1 wrote a
  path "because at S4 they are separate pods" — and separate pods is exactly why
  a path cannot be the thing that travels. Passing the text puts the dependency in
  the DAG where retry and cache can see it; a shared writable mount would hide it.
- **F-025 (new, closed): MLflow refused every in-cluster client for four
  milestones** — `403 'Invalid Host header - possible DNS rebinding attack
  detected'`, because MLflow 3.x's uvicorn allow-list is derived from an ingress
  this release does not have. Latent because every client until M4 was host-side.
  Fixed with `serverAllowedHosts`, listed EXPLICITLY (`["*"]` deletes the
  protection rather than configuring it) — **and the first fix broke the host
  route**, because setting the value replaces MLflow's default AND the middleware
  compares the whole header, port included.
- **`tracking.configure` no longer requires a `.env` that a pod cannot have.** Its
  docstring promised since M2-S2 that "an in-cluster caller … needs no code
  change"; `load_env` refused on the file's absence before precedence could apply.
  A missing file is now an empty source, the refusal moved to a value no source
  supplies, and the banner names the source it actually used (it used to print
  "set from .env" inside a pod that has none).
- **Four of this story's five defects were in the CHECKERS**, and the worst printed
  `ok … six stages on-cluster` over a run that had died on `ErrImagePull`:
  **`flyte run --follow` exits 0 when the run it followed FAILED**, and every other
  signal (run name, readable outputs blob) was consistent with success. The
  assertion is now POSITIVE — the outputs must carry a `"decision"` — and it caught
  the next three failures instead of painting them green.

## The cache, the full-data run, and what an image carries (M4-S4, second session)
- **The full-data run is DONE and its per-stage detail was recovered from the
  SERVER, not from a log.** `flyte run --follow` streams the parent's log and
  printed `Scrolled 2 lines`, so the transcript §5 shows for the sampled run does
  not exist for this one — but the control plane recorded every action, and
  `scripts/flyte_run_actions.py` reads it back: **six stages, 1909.7 s, of which
  the fit is 1874.7 s and everything else together is 34.6 s (98.2% is one
  stage)**. That ratio is the entire argument for caching this pipeline.
- **Its verdict is a REFUSE, and the REFUSE is the gate working.** The challenger
  cleared the FLOOR condition at **+3.26% against a 2.00% bar** and was refused by
  F-011's **incumbent** condition: the pipeline fits `configs/train.yaml`'s set v2
  with v1's hyperparameters — which is M3's `artisan v2` — measuring **3.2425** on
  the holdout against the serving champion's **3.2403**. **The pipeline re-derived
  M3-S5's bake-off number to four decimals**, on a kind node, in a container, and
  was then correctly told it is 0.07% worse than what serves. A pipeline that
  promoted here would have been the defect. Honest gap carried to M4-S5: the
  output's `margins` carries the FLOOR numbers only, so the JSON shows REFUSE
  beside a passing margin and the reader must know M3-S1 to reconcile them.
- **The cache-hit rerun: 33 minutes to 11 seconds, GREEN 19/19.** `make
  pipeline-cache-drill MONTH=2019-01` (detached): run 1 populated all five
  cacheable stages (**train 1935.2 s**), run 2 hit all five (**train 0.1 s**);
  executed stages **1966.9 s -> 3.2 s (0.2%)**, wall-clock **1974 s -> 11 s
  (0.6%)**, MLflow **12 -> 16 -> 16** (four runs are what one fit costs, so "no
  new runs" is the positive statement that the fit did not happen twice), and
  `@champion` version **2** after both. `register` re-executed both times at 3.2 s
  — which is the only reason that last line means anything.
- **`make pipeline-cache-drill` asks THREE systems, and ranks them.** The claim is
  the control plane's per-action `cache_status` (`CACHE_HIT`/`CACHE_POPULATED`/
  `CACHE_DISABLED` — a field the CLI does not render, which is why the reader
  exists). The clock corroborates and is deliberately the WEAKEST leg: a faster
  second run is equally consistent with a less busy machine. **MLflow is the
  strongest**: a re-executed train stage MINTS A RUN, so the experiment's run count
  must be identical across run 2 — said by a different server, in a different
  database, by code that has never heard of Flyte.
- **The cache key covers code + inputs + DATA, and the third term is the one that
  matters.** Every stage declares a month string or a row count and then reads
  1.8 GB off a volume Flyte cannot see, so the honest failure mode is not a stale
  model, it is **a stale model with a green transcript**. The salt is a hash of
  `data/*.dvc` (a content hash of each tracked tree, committed, changed only by
  `make data`), and it TRAVELS to the pods in `TAXI_DATA_PIN` for the same reason
  and by the same mechanism as `TAXI_PIPELINE_IMAGE` — the pins are not in the
  image and must not be. `_data_pin()` RAISES rather than defaulting: a salt that
  falls back to a constant produces exactly the failure it exists to prevent.
- **Two stages refuse a cache.** `register` reads the LIVE registry — a cached
  answer to "what is serving right now?" is wrong precisely when the alias has
  moved, which is the only time anyone asks; it costs **3.7 s against a 31-minute
  fit**, the rare case where correct is also nearly free. `main` is uncached so
  the rerun's evidence stays per-stage: a cached parent returns in ONE action and
  could not distinguish "five stages reused" from "the whole thing skipped" — and
  M4-S5's kill-a-pod drill would have no pod to kill. Both are pinned by tests
  that **parse the AST**, because the file argues its cache design at length and a
  grep for the word would pass on the argument (gotcha #53).
- **The cheap probe found three defects before the expensive run started.**
  `DRILL_STAGE=ingest make pipeline-cache-drill` runs one stage twice in ~40 s
  (against ~35 min) and is `make flyte-hello`'s idea one layer up. It caught: an
  apostrophe inside `${VAR:+word}` that swallowed four lines and reported itself
  as `line 72: $!: unbound variable` on an innocent port-forward (**gotcha #62**);
  a bar measured on the wrong clock, which called a **98.7% saving** a failure
  because a one-stage rerun is mostly launch overhead (**gotcha #63**); and a
  drill that would have gone red comparing two reruns to each other, because the
  cache outlives a drill. None of the three was about caching, which is the usual
  yield of a cheap probe.
- **F-026 (new, closed): a task pod's `src/taxi_mlops` comes from the IMAGE, not
  the code bundle.** `flyte run` defaults to `--copy-style loaded_modules` (22
  files observed, against 36 `.py` in `src/taxi_mlops` alone) and every stage
  imports the model code INSIDE its body — so editing `src/`, committing and
  running the pipeline executes the PREVIOUS code with a green transcript. The
  runner now diffs the image manifest's sha against HEAD over **`src/`,
  `pyproject.toml`, `uv.lock`, `docker/`** and exits **3**. `pipelines/` is
  deliberately NOT guarded: that IS the bundle, and guarding it would have refused
  this story's own drill. The old comment — "a pull error here means the tree
  moved" — described a protection that does not exist: M4-S3's loud
  `ImagePullBackOff` fires for a tag no node holds, and a stale manifest names a
  tag every node holds.

## Losing a pod (M4-S5, leg 1) — what survives it, and the two mechanisms people confuse
- **`make pipeline-kill-drill` deletes the pod a stage is running in, mid-work,
  and the pipeline finishes anyway.** GREEN 9 checks (2 in phase 0, 7 after),
  month **2019-03**, sampled and therefore verdict-free (F-008). **31 seconds
  from kill to a DIFFERENT pod object**; `train` cost **939.8 s** against ~870 for
  an undisturbed sampled fit, i.e. the fit restarted from zero and the loss was
  the ~123 s in flight. `@champion` **2** before and after.
- **The prediction is written to disk BEFORE the kill, and the first one was
  wrong.** It expected a pod named `…-1` (Flyte names task pods
  `<run>-<action>-<attempt>`); what happens is that the k8s plugin **recreates the
  pod under the SAME name with a new UID**, so a correct survival was reported as
  a failed drill, 6/7. Kept whole in `automation/runs/m4-kill/attempt1-prediction-
  wrong/`. The fix was the right PROPERTY, not a looser bar: **identity, not
  name** — a different pod object ran the stage, true under either classification.
- **A deleted pod does NOT spend the retry budget, and that is why phase 0
  exists.** The control plane recorded the killed action at **one attempt**, so
  `retries=2` had never been observed doing anything. `pipelines/flyte/
  retry_probe.py` is one task that always raises, carrying the same budget **by
  import**; it settles at **attempt index 3** and the run **FAILS** — the budget is
  real AND finite, which is the argument for the number being small (at 31 minutes
  a stage, a generous budget is just a slower way to hide a systematic fault).
  Two mechanisms, both measured, not interchangeable.
- **Every stage declares `retries=_STAGE_RETRIES`; `main` declares `0`.** A parent
  attempt can only re-run the child that just exhausted its own budget — same
  answer, three times the cost, three reports of one fault. What makes a budget
  safe on the gate stage is M4-S1's decision that **a REFUSE is a return value**:
  a refusal is not a failure, so it never reaches the retry machinery. Pinned by
  an AST test that fails if `register` starts raising.
- **F-027 (new, closed): the action reader had been answering `attempts: 0` for
  everything.** `getattr(status, "attempt", 0)` — the field is `attempts`, plural,
  and a protobuf answers `getattr` for its own fields only, so the typo returned
  the default instead of raising. Every run this program ever inspected, including
  `automation/runs/m4-cache/cache_drill.json`, carries a default where a
  measurement looks like it should be. Those runs genuinely were not retried, so
  no claim is wrong — but `verify-m4` must not read the old values as evidence.
  Pinned against `ActionStatus.DESCRIPTOR`, never against the string.
- **`run_pipeline.sh` now streams `flyte run --follow` to `flyte_run.log`**
  instead of capturing it into a shell variable. The drill cannot kill a pod
  belonging to a run it cannot name, and the name exists only in that output —
  which, buffered, appears when the run it meant to interrupt is already over.
  Same absence §9 had to recover from the server, one layer earlier.

## The marts tail task (M4-S5 leg 2) — D-003's decision, and the twin it did not create
- **`make pipeline` is SEVEN stages now.** `publish_marts` is the tail §9/M1-S6
  promised at M1 and D-003 held open until the publish became scheduled: rebuild the
  analyst layer (which is also the step that RECONCILES — the stage refuses to
  publish from a catalogue that disagrees with the ingest reports that wrote it) →
  `dbt build` (models AND tests interleaved) → publish. Proven on-cluster, run
  `rw98pj84z4jh5ldqrxqp`: **90.6 s of an 886.6 s run (10.2%)**, the publish itself
  **71.9 s**, in-pod `dbt build` **PASS=57 in 9.96 s**, 2019-01 published
  month-scoped and **all 8 months reconciled `yes`**, `@champion` **2 → 2**.
- **D-003 CLOSED, and the decision is a SPLIT because the marts are not one kind of
  object.** Measured on today's data with `make marts-peak` before either option was
  argued: **full refresh 228.2 s, `marts` DB 15.33 → 27.96 → 13.48 GiB (2.075×)**;
  **month-scoped (2019-03, 7.75M rows) 82.7 s, peak 15.33 GiB**. So the four
  aggregates (~46,000 rows between them) stay **full-refresh forever** — under a
  second, and it buys the strongest property a publish can have, that the mart IS the
  source with no possibility of drift. `trips_clean` is **month-scoped**: it is the
  entire peak, its grain IS the month (an indexed column), and a monthly pipeline
  re-derives ONE month, so a full refresh republishes ~7.5M changed rows by rewriting
  56M. **Peak −45.2%, wall −63.8%.** M1-S4's remembered "~23 GB" was OPTIMISTIC — it
  is 27.96 GiB now, because `error_segments` joined at M2-S4.
- **Two things got worse and both are recorded as costs.** The **steady state rises**
  (a scoped publish leaves ~7.75M dead tuples, so `end` is 15.33 GiB against a full
  refresh's 13.48 — a lower PEAK bought with a higher FLOOR of about one month of
  dead space), and **the mart can now drift from its source** in a way a full refresh
  made impossible. So `reconcile` asks Postgres and DuckDB for the same per-month
  counts after every scoped publish and refuses unless every month agrees. That check
  is the price of the decision, not a nicety — a month deleted and not re-streamed
  answers every query happily and just returns fewer rows (M1-S2's catalogue lesson,
  one layer downstream). A first publish has no month to replace, falls back to a full
  refresh, and **says so** — the one publish that legitimately pays the peak must not
  look like the rest.
- **One body of SQL, two thin transports, and the move was FORCED.** `make marts`
  publishes over `kubectl exec` because nothing of ours publishes 5432; a task pod has
  neither kubectl nor a kubeconfig, and giving a pipeline stage cluster credentials to
  shell into another pod would be worse than any of the three alternatives `marts.sh`
  already rejects. So `scripts/marts_publish.py` owns the swap SQL — the statement
  that decides what a board renders — and everything below its `Transport` protocol is
  transport-blind. The **mart list**, the **dbt `--vars` payload** and
  **`--no-partial-parse`** moved with it: `marts.sh` has no `MARTS=(...)` array any
  more and a test fails if one returns. The CSV producer is one thing too and it is a
  **subprocess on both sides** (`marts_export.py`, which gained `--where` so the
  scoped stream filters inside DuckDB); **its exit code is checked**, because a
  `Popen` read to EOF looks identical whether it finished or died three rows in.
- **What a pod needed that it did not have**: `flyte-task-marts` (the **fourth**
  consumer of the `marts` role, and the pod publishes **AS `marts`, never as the
  superuser** — a scheduled publish is a seat nobody is watching); `data/predictions/`
  as a **fourth staged tree**, because `error_segments` sources the analyst layer's
  `predictions` view and that view is CONDITIONAL on the tree existing; and the
  **F-026 guard widened to `scripts/` and `analytics/`** — the tail loads
  `marts_publish.py` by path in-pod and the dbt project is not importable at all, so
  the image is its only carrier.
- **The tail does not read the verdict, does not touch the registry, and is
  UNCACHED.** It consumes `verdict` only for the edge it draws: a pipeline whose data
  publish depended on a model verdict would leave the warehouse a month stale every
  time the gate said no, which is precisely when a DA wants to look. Its uncaching is
  the first in this repo argued from EFFECTS rather than inputs — its product is a
  mutation of a Postgres the cache cannot see, so a hit would return "published, 7.5M
  rows" in 0.1 s having published nothing, and it would be RIGHT by the cache's own
  rules. The local rehearsal opts IN (`PIPELINE_LOCAL_ARGS=--publish`) and both
  orchestrator drills opt out (`PUBLISH_MARTS=0`).
- **An image rebuild invalidates every cached stage** (gotcha **#66**, found by this
  run): five stages read `CACHE_POPULATED` on a month they were already populated for,
  same data pin, function bodies untouched — the tag is the git short sha, so every
  commit is a new image and it reaches a task both as the environment's image and as
  `TAXI_PIPELINE_IMAGE`. Correct, and it agrees with F-026 from the other side; the
  unpriced cost is that one commit under `src`/`scripts`/`analytics`/`docker`/
  `pyproject.toml`/`uv.lock` turns the next full-data run back into a 31-minute fit.
  **Leg 3's consequence**: `verify-m4`'s cache leg must read the RECORDED evidence in
  `automation/runs/m4-cache/cache_drill.json`, not re-ask about the latest run.
- **The runner's summary line was a small version of the same disease.** It said "six
  stages on-cluster" for a month after the graph grew a seventh, and nobody noticed
  because nothing reads a summary line for information. It now DERIVES the count from
  `pipelines.tasks.STAGES` and names whether the tail was on.

## The M4 gate (M4-S5 leg 3) — what it asks, what it refuses to do, and the ground it found soft
- **`make verify-m4` is 39 sub-checks in 7 sections, seconds, and it RE-RUNS
  NOTHING** — a stronger clause than M3's "re-fits nothing", because M4's evidence
  cost ~95 minutes on-cluster AND because re-running any of it would **mint MLflow
  runs**, which is the quantity the cache leg's strongest check counts. A gate that
  launched a pipeline would corrupt the evidence it exists to read. No skip flag, no
  fast mode (M1's rule, third inheritance). It reads: the live control plane, the
  cluster, the registry, the warehouse, the image *from inside a container*, the code
  *with `ast`*, and the records the drills wrote.
- **The alias law is asked in its strong form.** "Is `@champion` still 2?" is
  satisfiable by not looking. What §7 asks instead: **not one of the 28 runs the M4
  pipeline fitted in `m4-pipeline` is a registry version** — a promotion cannot hide
  from that, because it must create a version and a version carries its run. Plus
  `tasks.train` has no `promote` parameter (AST), and every recorded run's
  `champion_after` must equal the live alias — the gate never asserts the VALUE.
- **The cache leg reads the RECORDED drill, never the newest run** (gotcha #66): the
  image tag is the git short sha, so one commit makes every stage `CACHE_POPULATED`
  and a gate written the obvious way would go red for a commit.
- **Two witnesses must AGREE, which is stronger than either passing.** The control
  plane's `cache_status` and MLflow's run count answer the same question — did the fit
  run twice? — so a record claiming a stage re-executed while the tracking server
  minted nothing is a contradiction. **This is what `make verify-m4-redteam` proves**:
  it flips ONE field (run 2's `train`, `CACHE_HIT` → `CACHE_POPULATED`) and leaves
  duration, phase and the MLflow counts alone — the most plausible lie the file can
  tell, and internally consistent to any reader who skims. **RED with 2 FAILs, 37
  sub-checks still passing, byte-identical restore under an EXIT trap, then GREEN
  39/39.** A gate reading only `cache_status` would have believed it.
- **Every literal is derived on BOTH sides** (F-017, gotchas #49/#50): the stage set
  from `tasks.STAGES`; the flyte-task→callable map parsed out of `workflows.py`
  (nothing declares it — `ingest` wraps `ingest_month`); the uncached set from the
  `cache="disable"` decorator args; the retry budget from `_STAGE_RETRIES`; the
  experiment from the new `tasks.DEFAULT_EXPERIMENT` (extracted this session — the
  gate had typed `"m4-pipeline"`, which is exactly the literal `verify-m2` was burned
  by). A test fails if a run name, an MLflow run id or a tagged image ref appears in
  the script at all.
- **F-029 (new, OPEN, ARCH's at the M4 boundary): both M3's and M4's gates replay
  records that are GITIGNORED.** `git ls-files automation/runs/` is EMPTY. So a fresh
  clone runs those legs red for no defect, and — the part that matters — an edit to a
  record, which is exactly what both red teams simulate, **leaves no diff for a
  reviewer to see**. Two artifacts had already written the false version down:
  `verify_m3.sh`'s header said "committed JSON", and its red team advised
  `git checkout --` on an untracked file. All three false statements (those two plus
  CLAUDE.md's own row) were corrected the day it was found; the POLICY was not
  changed, because what belongs under review is not an executor's call. Three costed
  options are in the ledger row. **CLOSED at M5-S1 (2026-08-19): ARCH decided option
  A at the M4 boundary and the mechanics landed — `automation/runs/**/*.json` is
  tracked (32 records), logs and `.status` stay ignored, and both gates and both red
  teams were re-run green over the moved files.** The gitignore is pattern-based
  because a bare directory exclusion stops git descending and makes any `!` rule
  beneath it silently do nothing.
- **The gate's own first run went RED for the right reason and the wrong target**
  (gotcha **#67**): "every run has a `main` parent" named the retry probe, which is
  built to have neither a parent nor a success. Fixed by DERIVING what a pipeline run
  is (one that ran ≥1 stage of this graph), not by an exclusion list — and the
  excluded record is printed, not silently dropped. Its tests then went red three
  times for matching WORDS not INVOCATIONS (gotcha **#68**): the ban on running
  `make pipeline` caught the gate's own advice line, and the ban on `flyte get` caught
  `kubectl -n flyte get deploy`.

## The records under review, and the serving platform (M5-S1)
- **`automation/runs/**/*.json` is TRACKED from this story on — F-029 CLOSED.**
  Two milestone gates REPLAY those records and both red teams simulate an EDITED
  one, so what a gate reads must be what review can see; until now an edit left
  no diff. 32 records, 236 KB, largest under 100 KB. **Logs and `.status` stay
  ignored** — transcripts, and no gate reads them for a verdict. The gitignore is
  pattern-based and had to be: a bare `automation/runs/` exclusion makes git stop
  DESCENDING, so a `!` rule beneath it is silently inert (`automation/runs/**` +
  `!automation/runs/**/` + `!automation/runs/**/*.json`, verified both directions
  with `git check-ignore -v`). Re-run over the moved files: **verify-m3 46/46 ·
  verify-m4 39/39 · both red teams PASSED** with sha256-verified restores. The
  new checkable property: **a clean drill leaves a CLEAN TREE**, which could not
  be stated while the files were invisible to git. Also: `test_bakeoff.py`'s
  skip-when-the-record-is-absent became an ASSERTION (host suite **544 passed, no
  skips**). What this does NOT claim: the records are now REVIEWABLE, not
  verified — a tampered record is a **diff**, and what used to stand between a
  rewritten number and a green gate was only that nobody rewrote it.
- **`make deploy-serving` installs a route, a CA and an operator — and NO model.**
  It does not read `.env`, passes no `--set`, and a test asserts it cannot name
  `champion`/`models:/`/`mlflow` **in code** (asserted over code only, because the
  script argues its own design and a word-search greps the argument — #53/#68
  applied before they bit). M5 law 2 made falsifiable at the cheapest level: a
  script that does not know the registry exists. `@champion` version 2, unread.
- **The route's second hop is the whole trick.** kind published 8081←80 on the
  control-plane node at CREATE; that is a route only once something BINDS 80 on
  that node. `hostPort` + a hostname nodeSelector + a toleration for that node's
  taint — and the node name is DERIVED from the kind config's cluster name, with
  the values file asserted against it, so a rename fails at deploy time rather
  than scheduling onto a node with no published ports (gotcha #52). The upstream
  kind ingress manifest was NOT used: it selects `ingress-ready=true`, a label
  this cluster was built without, and the kind config is read at create time only.
- **KServe is Standard/RawDeployment (ADR-004) and the mode is read back off the
  live ConfigMap**, never off the values submitted. Six CRDs registered cleanly on
  **Kubernetes v1.36.1**, so risk R1 did not materialise and the plain-mlserver
  fallback is armed and unspent. Honest cost, landing on M6: **Standard has no
  canary** — `canaryTrafficPercent` requires Serverless.
- **`make backup` ran first and proved its own design.** 6 databases and 331
  objects where M4-S2 had 5 and 105 — nobody edited a list, because the script
  enumerates from the server. **Restore is still NOT rehearsed** and every
  artifact says so.
- **The accept check went RED over a perfectly good install** by demanding
  `Server: nginx`, a header modern ingress-nginx suppresses on purpose. #59 says
  assert on a positive artifact; it does not say check the artifact EXISTS. Fixed
  by asking the server: `GET /healthz` -> 200 is the controller's OWN endpoint
  (`/nginx-health` 404s), the same shape M4-S2 found for Flyte. **gotcha #70.**

## The champion on the wire (M5-S2) — what serves, what refuses, and the two rows it closed
- **`make serve` is the whole path** and it never moves the pointer: secrets ->
  MinIO (the read-only `serving` identity) -> **resolve `@champion`** -> the
  ServingRuntime -> the credential -> the InferenceService -> ready -> a
  **PREDICTION**. `@champion` is read BEFORE and AFTER its own mutations and a
  difference exits 2; a test parses the deploy AND the resolver for mutating
  registry verbs. Version **2** before and after. `make quote` asks the live
  endpoint through the ONE feature path; `DRY_RUN=1` mutates nothing.
- **The accept check is a prediction, not a health probe** (gotcha #59):
  `2019-07-04T09:15:00, zone 132 -> 48 -> 39.0019 minutes`, with mlserver
  stamping **`model_version: "2"`** on the response ITSELF — read off the answer
  being printed, not off a metadata call that could describe a different moment
  (`GET /v2/models/nyc-taxi-eta` reports `versions: []`; the two are different
  fields). It matches the locally-loaded champion **bit for bit** (absolute
  delta 0.000e+00) on ONE row — the 1e-6 gate over the honest hazards is M5-S3's
  and a spot check must not stand in for it.
- **F-009 CLOSED by option (b), and (a) is UNAVAILABLE rather than unpreferred.**
  A version's `source` is set at creation and MLflow cannot change it, so fixing
  it means a NEW version — what M5 is legislated not to do — and it would leave
  version 1, **the rollback target M5-S5 depends on**, still broken. The property,
  now documented: **a version's `source` is a RUN uri while the artifacts live
  under the LOGGED MODEL's `artifact_location`; every consumer that needs bytes
  must resolve alias -> logged model -> artifact_location and none may read
  `source`.** A deploy that trusted `source` would hand KServe an EMPTY prefix,
  the storage-initializer would download zero objects and **succeed**, and
  mlserver would fail on a missing `MLmodel` — the artifact-shaped error that
  blames the wrong thing. Resolved in ONE place
  (`scripts/resolve_champion_storage.py`, a reader), with gotcha #39's
  discriminator wired in as `--check`.
- **F-019 CLOSED, and the decision is BOTH halves because each alone is
  unshippable.** The table is derived from 5 U.S.C. §6103 to **2030**
  (`make holidays`), AND an uncovered date is REFUSED in a type
  (`UncoveredDateError`, `http_status = 422`, `make quote` exits 2) before
  anything reaches the wire. **Refuse, not degrade-and-flag**: degrading returns
  a wrong quote nobody can see is wrong, refusing is a countable failure with its
  fix in the error text — **M6's alert plan gains a named signal, the count of
  422s per window.** Nothing measured moved: re-deriving 2019 reproduces the ten
  hand-written rows BYTE FOR BYTE (written by a human months before the deriver,
  so agreement is evidence about the RULES — Juneteenth is federal only from
  2021 and is correctly absent), and the holiday/near sets inside
  2019-01..08 are asserted unchanged. **The M4-S1 tripwire was re-pinned in the
  same PR** to the DECIDED behaviour, with the horizon READ from the table.
- **A false green worth remembering**: on a re-deploy the InferenceService's
  `Ready` condition is satisfied by the pod being REPLACED, so
  `kubectl wait --for=condition=Ready inferenceservice` returned while the new
  pod was `Init:0/1` and the accept check interrogated the predecessor — reporting
  `(unversioned)` when the version stamp was the change under test. **A wait the
  thing you are replacing can satisfy is not a wait** (gotcha #71). Fixed by
  waiting on `rollout status deploy/…-predictor` FIRST.
- **The wire carries the matrix's own dtypes.** Sending `FP64` for all 24
  features answered **500: Can not safely convert float64 to int32** — MLflow
  enforcing the logged signature and refusing a lossy cast. The fix was to stop
  lying about the types, never to strip the signature.

## Parity, measured (M5-S3) — the number, the defect it found, and the claim it does NOT make
- **`max |offline − online| = 0.000e+00` minutes over 16 hazard rows, bar 1e-6.**
  Not "within tolerance" — identical, to every bit float64 holds. Every quality
  number this program has published (KPI-09 3.2403, KPI-10 80.552%, every KPI-13
  in the mart) was measured in a HOST process; the rider's quote comes out of a
  container running Python 3.10.12 / pandas 2.2.3 / numpy 2.2.6 against
  training's 3.12.14 / 3.0.5 / 2.5.2. **That seam is now measured, and M5-S2's
  "first suspect if parity comes back wide" is cleared** — none of the three
  differing packages is on the numeric path, lightgbm is 4.7.0 on both sides, and
  the wire carrying the matrix's own dtypes means the trees traverse identical
  float32 bits. Zero is stronger than the kickoff's predicted ~1e-7 AND more
  brittle: anything that reintroduces a dtype round trip moves it, so a future
  1e-7 is worth a sentence, not a shrug.
- **ONE matrix, scored TWICE.** Built through `taxi_mlops.features`, scored by
  the registry-loaded booster and by the endpoint. So the delta is the model
  bytes + the runtime + the wire, and NOT two feature builds that could differ.
  Said out loud in the module and in `docs/parity_m5.md` §1: this does NOT prove
  M7's transformer will build features the way training does — that seam does not
  exist yet and needs its own measurement.
- **The rows are DECLARED, COMMITTED and each names its hazard.** Sampling would
  give a number that changes every run, a red team that cannot plant a cause,
  and — the real objection — the rows that break serving are never the average
  ones. The unseen OD pair (`55 -> 148`: 6 in `trips_test`, 0 in `trips_train`)
  is a committed literal with the query in its note, so parity stays a
  seconds-long reader instead of re-scanning 44M rows for a constant.
- **F-030, found by building that set and live since the endpoint existed:
  the missing-geometry path could not be quoted AT ALL.** Zones 264/265 have no
  centroid by design (DR-04 condition 1) → nine NaN features → `json.dumps`
  writes the bare token `NaN`, which is not JSON → **`HTTP 422 … "loc":
  ["body",1241] … unexpected character`**, a byte offset naming neither the
  feature nor the zone. ~1% of every split, and 264->264 is the largest single OD
  "route" in the data. Missing now travels as `null`; an **infinity is REFUSED**
  (equally unrepresentable, but not a missing value — laundering it would present
  a broken feature as an absent one); `_post` passes **`allow_nan=False`** so the
  next path that forgets fails loudly HERE. Proof that `null` is the same missing
  value the booster was fitted on: those rows parity at **0.000e+00**.
- **The red team plants its cause inside the TEST, never on the cluster.** The
  obvious lever — point the endpoint elsewhere — would break production to prove
  a test works. Arm A: every feature under its own name and dtype carrying its
  neighbour's values (**42.10 min** of skew, every input individually valid).
  Arm B: load version **1** offline (a READ) while the wire serves the champion —
  refused at the feature-set guard before a number exists, because a "delta"
  between a 5-column and a 24-column model could only be manufactured.
- **F-031 / gotcha #73: arm A's first draft went GREEN under its own tampering.**
  It rotated the ORDER of the inputs, on the client's own documented property
  that a V2 body is positional — and measured 0.000e+00. **This runtime pairs by
  NAME**: mlserver hands MLflow a named frame and the logged signature reorders
  it. The docstring was CORRECTED, not deleted (a positional V2 runtime is legal,
  M7's transformer may be one, and the ordering costs nothing) — what is no
  longer claimed is that the ordering is what protects us. **The logged signature
  is**, for the second time this milestone after it refused the lossy
  `float64 -> int32` cast at M5-S2.

## p95 and self-heal (M5-S4) — the shape the number belongs to, and the fifteen seconds
- **`make load-drill` is the whole path**: preflight (who is answering, with what)
  → a ramp that CHOOSES the headline rate → the headline window with the
  container's CPU measured across it → the predictor pod deleted MID-LOAD. The
  numbers: **p50 17.2 · p95 104.2 · p99 107.2 · max 115.4 ms at 4 req/s for 60 s,
  concurrency 8, hazard mix, 0 errors in 240 requests**, and **14.53 s of
  unavailability** when the pod is destroyed. `@champion` version 2, read off the
  timed responses themselves and never written.
- **The loop is OPEN, and that is the whole design.** A closed loop (N threads,
  each firing when the last returns) makes the arrival rate a CONSEQUENCE of the
  latency, so a slowing server quietly receives less load and the queueing a real
  arrival stream would cause never happens — coordinated omission, and its p95 is
  an unloaded server's service time in a load test's clothes. Arrival *k* is due
  at `t0 + k/rate` regardless; the headline is `latency_ms` (**scheduled** →
  response), `service_ms` (sent → response) sits beside it, and the GAP between
  them is the omission made visible. A percentile is never printed without its
  rate, window, concurrency, mix and ACHIEVED rate.
- **The measurement excludes the feature build, and says so.** Bodies are encoded
  before the clock starts, so these percentiles are the wire + the server. M7's
  transformer moves `build_features` (~30 ms cold, one row) INTO the pod and
  therefore into this number — written down now so that delta reads as a boundary
  moving rather than a regression.
- **Capacity, for the PRR: 1.31 of 2 CPU cores (0.326 core-s/request), 236 MiB
  against a 1 GiB request — and the CPU REQUEST of `200m` understates real usage
  by ~6×.** Recorded, deliberately not changed: editing a deployed workload's
  resources is a change to what is on the wire, and this is a measurement story.
  Read from the container's own cgroup (`cpu.stat`, differenced across the
  window) because there is no metrics-server and installing one would be a
  platform change inside a measurement.
- **The ceiling is measured: 6 req/s = 96% of the CPU limit, 8 req/s = 101%**,
  where p50 jumps 18 → 115 ms. **A rate at the ceiling measures the QUOTA, not
  the service** (gotcha #74) — so the ramp's selection rule has a third clause
  (stay under 90% of the limit) with a mechanism behind it: the next phase
  destroys the pod, and a rate that spends the whole quota leaves no headroom for
  the replacement to come back into.
- **Self-heal: 14.53 s, one replica, no canary.** 58 failed requests of 720
  (56×`503`, 2×`502`), then 559 with zero errors against zero in the 100 before
  the kill. The replacement is a **different pod object by UID** — identity, never
  name (M4-S5's lesson) — **on a different node**, which is M5-S2's `kind load` to
  all three nodes paid back exactly as its note predicted. The kill fires from
  INSIDE the load client's own per-second callback, so the kill and the latencies
  share one clock. The prediction is written to disk BEFORE the kill.
- **The residual error rate is REPORTED and deliberately NOT gated.** Its control
  is the pre-kill segment of the same run (same client, same rate, same minute).
  An error-rate threshold is an SLO, the SLO document is M6's by the kickoff's own
  scope list, and a bar set here would be a bar set from the number just seen.
- **The first attempt went RED and is kept unedited** (`automation/runs/m5-load/
  attempt1-at-the-ceiling/`). Its two-clause ramp rule chose 8 req/s, so its p95
  measured the CFS quota; and it reported a **182-second "outage"** computed as
  `last_error - first_error` when the service was down for **13 seconds** and then
  served 1,400 requests while dropping ten (gotcha #75). Both fixed as
  QUANTITIES, never thresholds — gotcha #63's lesson in a new place. The two runs
  then CORROBORATE: 13 dead seconds at 8 req/s, 14 at 4 req/s, so self-heal costs
  ~14 s regardless of load and attempt 1's long tail belonged to the saturation.

## The runbook, the PRR and the M5 gate (M5-S5) — the rollback nobody could type in one move
- **A rollback is THREE moves, and nothing enforced the second one — F-032.**
  `@champion` version 2 eats **24** features, version 1 eats **5**, and the
  client builds its matrix from `configs/train.yaml: features.version`. So the
  obvious rollback (move the alias, `make serve`) loads a 5-column model under a
  24-column request stream: MLflow's logged signature refuses it, the rider gets
  a **500**, and every condition on the InferenceService still says `Ready` —
  no restart, no event, no probe. `docs/runbooks/serving.md` §4 types all three
  moves and makes the config line **derivable**: every registry version carries
  a `feature_set` tag written at promotion time, so the target says what it
  eats. **`make verify-m5` §2 asserts the invariant live** (served version's
  `feature_set` == `configs/train.yaml: features.version`), which turns a
  half-finished rollback into a RED gate naming the shape instead of a 500
  nobody can attribute. Step 3 is a raw `set_registered_model_alias` ON PURPOSE:
  `registry.promote()` refuses to move an alias without a gate `Decision` and
  its `incumbent_version` (F-011), and a human overriding the gate in an
  incident should look unusual, be typed by hand and leave a commit — **a `make
  rollback` that bypasses the gate is explicitly refused here** (M6 owns the
  rehearsed revert).
- **Stop/start is REHEARSED; the rollback is NOT, and both say so where they are
  used.** `make stop-start-drill` runs the runbook's own commands: the route
  stopped answering **3.12 s** after `serving.kserve.io/stop=true` and answered
  again **18.24 s** after the annotation was removed, on a new pod. Two things
  running it corrected: **`spec.replicas` goes ABSENT, not `0`** (so "scale it
  back to 1" is wrong advice and `kubectl scale` is fought by the controller),
  and a restart costs **more** than the 14.53 s a killed pod costs, because the
  Deployment's pod is recreated from scratch rather than replaced by a
  ReplicaSet already watching. The rollback moves `@champion`, which M5 is
  legislated not to do — so it is labelled NOT REHEARSED in its own section, in
  §8's list, in the PRR and in the deployments ledger (the M4-S2 backup
  precedent).
- **`make verify-m5` is 49 sub-checks in 7 sections, 5.8 s, and it re-runs
  nothing expensive — but it DOES ask for one prediction.** A serving gate that
  never asks the service for the artifact it exists to produce would pass
  against a dead model with a healthy `Ready` condition (#59/#71). So §2 sends
  ONE hazard row and requires the answer to (a) carry a `model_version` equal to
  what the ALIAS resolves to and (b) reproduce the parity record's row for that
  hazard — §9/M5's "Show: parity output", re-shown at the cost of one request
  rather than a full sweep. Everything else is read: the tracked records, the
  live cluster, the registry, the committed docs. No skip flag, no fast mode
  (M1's rule, fifth inheritance).
- **The gate checks the PROSE against the records.** Every number
  `docs/runbooks/serving.md` quotes is compared with the record it cites, and
  every `make` target it types is checked against the Makefile — a renamed
  target turns an incident procedure into a typo at the worst possible moment.
  That leg is also the red team's second witness: **one rewritten number
  (`recovery.outage_seconds` 14.53 → 14.251, taken from the record's OWN
  `error_window.span_s` — gotcha #75's mistake re-made, wrong by 0.28 s) makes
  the record stop reconciling with its anchors AND makes the runbook quote a
  number no record holds.** A gate that only re-derived the arithmetic would be
  checking a file against itself. **RED with 2 FAILs, 47 sub-check lines still
  passing, byte-identical sha256 restore, GREEN again.**
- **The PRR minutes say first what they could NOT do** (`docs/rituals/
  2026-08-19_prr-m5.md` §0): the champion was already serving when the review
  was held (§9/M5 says "BEFORE the champion serves"; three of the four boxes are
  only fillable with S3/S4's numbers), the rollback could not be rehearsed, and
  no alert can fire because there is no Prometheus. Box 3 is therefore a PLAN
  with **seven named signals, each with a source that exists today and each of
  which would have caught something that actually happened in M5** — including
  **A-3, the count of 422s per window**, which is the signal F-019's typed
  refusal bought and the horizon's smoke alarm. **Thresholds are deliberately
  absent**: a bar set here would be set from the number just measured, and the
  SLO document is M6's.
- **Capacity, and the one open recommendation:** 1.31 of 2 cores at 4 req/s ·
  0.326 core-s/request · 236 MiB of a 1 GiB request · ceiling ~6 req/s per
  replica. **The CPU REQUEST of `200m` understates real usage by ~6×** — routed
  to M6 with a re-measurement, because changing it is a change to what is on the
  wire and a review does not edit the wire (M5-S4 made the same call).
- **The gate's first run went RED against a correct install** because it read
  KServe's deployment mode out of the values file **with a regex** and matched
  the comment "The chart's default is `deploymentMode: Knative`" — prose where a
  parser reads it as code, gotchas #53/#60 for the fifth time. It parses the
  YAML now. Two smaller ones: demanding the runbook quote the record's number at
  FULL precision fails on a document sensibly writing `104.2 ms` for 104.226
  (gotcha #42 applied to prose), and the first fix for that accepted a bare
  substring — which would have matched `14` inside `14.53` and let the red
  team's planted number through.

## The eyes (M6-S1) — what is scraped, what it cost the wire, and the three zeros
- **`make deploy-monitoring` is the whole path**: `make backup` first (M4-S2/M5-S1
  precedent — 6 databases + 331 objects, 1.6 GiB, `2026-08-19T05-59-36Z`) → the
  route → namespaces + secrets → Prometheus (+Alertmanager +kube-state-metrics) →
  the dashboard ConfigMap built FROM `analytics/grafana/dashboards/*.json` →
  Grafana → the accept check. `DRY_RUN=1` mutates nothing, helm included. It
  **re-runs `deploy_serving.sh`** rather than carrying a second copy of the
  ingress chart pin: ONE file owns the ingress values and ONE script owns the
  release, so there is no pair to drift; the cost is ~1 min of no-op upgrades.
  **It installs no alert rule and no threshold** — those are S2's, and the board
  draws no threshold line (pinned by a test).
- **The UIs ride the EXISTING 8081 route, host-based** (`prometheus.local`,
  `grafana.local`) — M6 law 1. Ports 3000/9091 stay reserved NAMES in the port
  family, not routes, until a PO-sanctioned rebuild.
- **F-034: the platform advertised a metrics port that 404s.** KServe stamps
  `prometheus.kserve.io/port: "8080"` on the predictor pod; the live pod answers
  **404** there and **200 with 24 series** on **8082**. A scrape config written
  from the platform's own annotation — the obvious move — yields a permanently-DOWN
  target and a board of empty rectangles, with no error anywhere. `make
  probe-mlserver-metrics` is the measurement and it stays in the repo: a pinned
  port whose probe has been deleted is a remembered number.
- **F-033: the ingress controller could never complete a rolling update**, latent
  since M5-S1. `hostPort` + 1 replica + a single-node selector vs the chart's
  default RollingUpdate = the surge pod can never bind port 80. It sat Pending
  **10 minutes** while the old pod served **840/840** and the upgrade headed for a
  20m timeout — *the zero outage was the strongest evidence for the wrong
  conclusion* (gotcha #77). `Recreate` now, and the honest cost is unavoidable:
  every change to that Deployment is a real outage of the only route in.
  **Measured 15.0 s**, which corroborates 14.53 s (killed pod) and 18.24 s
  (stop/start) — three mutations, three numbers within four seconds.
- **The accept check is a MEASUREMENT, not a target list**: it reads a counter,
  sends ONE real quote (`zone 132 -> 48 -> 39.0019 minutes`, the parity row's own
  value), waits a scrape, and requires the counter to move — then parses **every
  panel's PromQL out of the checked-in dashboard JSON** and executes it. Its first
  run was GREEN with three panels at "0 series" and each zero was a different real
  defect (ingress metrics Service never *discovered*; `rate([1m])` at a 1m scrape
  interval evaluates to nothing; one genuinely-down rbac-proxy target). **An empty
  panel is now a FAILURE** — it is indistinguishable from a quiet system, so green
  must not be the default rendering of "no data" (gotcha #78).
- **A scrape/rules change costs NO restart** (configmap-reload sidecar; the
  Prometheus pod was older than the upgrade that changed its config) — so S2's
  predict → inject → observe → clear loop is minutes.
- **What M6-S2 inherits, precisely**: a *histogram* for server-side latency (a
  different instrument from M5-S4's client-side p95 — the SLO doc must say which)
  · `status_code` at source, so 5xx-vs-422 is a label selector · **no model
  version in any mlserver metric**, so A-4 needs the response body ·
  `serverFiles.alerting_rules.yml` already present and empty on purpose.

## Judgement (M6-S2) — the SLOs, the alerts that fired, and the number the analogy got wrong
- **`docs/slo_serving.md` OWNS every serving threshold** and nothing else may
  invent one. Four targets: **SLO-L1** 95% of quotes within **250 ms**
  server-side · **SLO-A1** 99.9% non-5xx monthly, measured **at the edge** ·
  **SLO-R1** <1% of infers rejected as malformed, explicitly OUTSIDE A1's error
  budget (a 4xx is a guard working) · **SLO-C1** saturation, an operating limit
  and not a user promise. Every target states its **instrument** and its **load
  shape**, and none is set equal to a number just measured (#63/#74 in bar-form).
- **The p95 instrument cannot measure this service's p95, and the SLO is shaped
  around that.** `histogram_quantile(0.95, …)` returned **111.6 ms** for a window
  where the client's WHOLE-ROUND-TRIP p95 was **84.4 ms** — impossible for a real
  measurement: mlserver's buckets jump `le` 0.1 → 0.25 and 13 of 259 observations
  live in that 150 ms gap, so the estimate is interpolation. **So SLO-L1's number
  IS a bucket edge and A-1 counts requests beyond it** — exact, no interpolation
  anywhere. Its counters are fine; only its quantiles are unusable.
- **A-2 is measured at the EDGE because a dead predictor cannot report its own
  absence** — the series does not fall to zero, it stops existing. Its threshold
  is **10%** and that is arithmetic, not laxity: at 4 req/s the longest healthy
  recovery ever measured here (18.24 s) is **6.1%** of a 5-minute window, so a 5%
  bar would page for a system that healed itself in eighteen seconds. Honest
  blind spot, stated: **a ratio has no value when nobody is asking**, so A-2
  cannot fire on an idle service — **A-5 is the complement**, reading a replica
  count and needing no traffic. A test fails if every rule becomes a ratio.
- **A-6's threshold could not have been guessed: this container is throttled at
  every rate it has ever been measured at.** M5-S4's ramp, throttled fraction vs
  client p50: **0.23 → 18.5 ms · 0.51 → 19.1 ms · 0.79 → 18.1 ms · ~1.00 →
  115.5 ms**, with **zero errors on every row** (#74 as a table). "Any throttling"
  fires on a healthy service, so the bar is **0.90** — between the last harmless
  observation and the first harmful one — sustained 10m.
- **`make alert-fire-drill` fired two alerts end to end, GREEN 11/11, and its
  prediction was on disk first.** ONE injection carrying both shapes the endpoint
  really produces (malformed body → 422, F-030's class; signature-refused body →
  500, F-032's class) must fire two rules with different sustain windows **in a
  predicted order**: **A-3 at T+150.5 s (predicted 150) then A-2 at T+330.6 s
  (predicted 330)**, both reaching **Alertmanager** and not just Prometheus's UI,
  all **five must-not-fire alerts inactive**, an ordinary quote succeeding
  throughout (errors, not an outage), both cleared 315.1 s after the stop. The
  negative predictions are the load-bearing half — a drill that predicts only
  "something fires" cannot be wrong.
- **F-035: two of the PRR's seven signals have no metric source, for the same
  reason — the fact lives in a CLIENT and no client here is scraped.** Measured,
  not assumed: a past-horizon `make quote` (exit 2, F-019's refusal raised before
  a request is built) left the infer counter at **22 → 22**, so the kickoff's
  "A-3 can be fired for free by past-horizon quotes" is false against this stack.
  A-4 needs served-version vs registry and **no mlserver metric carries a
  version** while MLflow exports no metrics — there are not two series. Both are
  named absences with options, costs and an M7-pushgateway landing;
  `render_alert_rules.py` FAILS if the implemented set and the documented
  absences disagree, so the gap cannot be quietly forgotten OR quietly closed.
- **The CPU request is 1500m on the wire and the p95 prediction held**: p50 29.4
  → 29.5 ms, p95 84.4 → 112.7 ms (inside this shape's run-to-run spread — M5-S4
  measured 104.2), and on the SLO's own instrument **≥2 of 240 beyond 250 ms
  before vs 0 of 240 after**. The tail's improvement (p99 −73%, max −79%) is
  deliberately NOT claimed: the before run's slow requests were mid-run, which is
  host contention, and the flattering reading is the one this program names and
  refuses.
- **What this story predicted WRONG is the useful part (#80).** The SLO doc's
  first draft priced a model re-deploy at ~15–18 s by analogy with three measured
  mutations. Measured across a real `make serve`: **0.5 s, one 502 of 400
  samples.** At ONE replica `RollingUpdate`'s `maxUnavailable: 25%` floors to
  **zero**, so a surge pod must be ready before the old one goes; the other three
  numbers all destroy the only pod first (kill · stop removes `spec.replicas` ·
  ingress-nginx FORCED onto `Recreate` by its hostPort). **M6-S4 inherits this**:
  a canary weight flip is nearly free.
- **F-036, found by running the thing: `make serve` hung 15 minutes and then
  FAILED over a healthy service.** kubectl v1.36 ignores a resource's conditions
  while `observedGeneration` trails `generation`, and KServe v0.20.0 leaves it
  behind on every re-deploy (observed 3 vs 2, all conditions `True`, pod Running
  1/1). Under `set -e` the timeout took the accept check with it — the one failure
  mode is a correct deploy reporting as broken (#55's family). Second wait leg is
  now `--for=jsonpath=`; `rollout status` stays FIRST (#71 untouched). The M5 test
  that pinned `--for=condition=Ready` went red for the correct fix and was
  re-pinned to the ORDER of the two waits — **gotcha #50, fourth time.**

## The spike and the shadow (M6-S3) — a second model on the wire, and what a canary here really needs
- **ADR-011 discharges ADR-004's deferred spike, and its two CONDITIONS are the
  point** (`docs/decisions/ADR-011-…`, evidence `make canary-spike`, PASS 7/7).
  Option **(ii)** — two InferenceServices behind the EXISTING ingress-nginx —
  is CONFIRMED for traffic and **(iii)** dual-send for the v1 table; Knative
  stays pre-refused and unspent. **Condition 1: a canary backend needs its OWN
  Service.** ingress-nginx keys backends by `<ns>-<svc>-<port>` and a backend
  holds ONE role, so a canary pointed at a Service some non-canary Ingress also
  claims gets its weight silently discarded — **0 of 200 moved** at weight 50,
  `{weight: 0, weightTotal: 0}`, while the champion's backend still listed it
  under `alternativeBackends`. With a dedicated Service: **100 of 200 moved**,
  `noServer: true`, `{weight: 50, weightTotal: 100}`. It bites THIS program
  specifically because KServe RawDeployment generates an Ingress per isvc, so
  the natural canary target always already has one. **Condition 2: both backends
  must serve the same V2 model NAME** — the name is in the URL path, so
  canary-routed requests returned **404** (not the 500 at the signature everyone
  predicts; that wall is real and never reached), and `rewrite-target` on the
  canary changed the share by **0 points** because ingress-nginx applies only
  `canary-*` annotations from a canary Ingress. The named remedy is
  `MLSERVER_MODEL_NAME` and **M6-S4 must PROVE it** — it is recorded as unproven
  on purpose. `mirror-target` on the KServe-owned Ingress DOES work (annotation
  survived a reconcile, `nginx.conf` gained a real `mirror` directive), so
  mirroring is available for a same-schema, same-name challenger.
- **`make shadow` puts registry version 1 on the wire with ZERO rider traffic**,
  and it never moves the pointer: `@champion` is read before and after, a change
  exits 2. It resolves BY VERSION through F-009's identical two hops
  (`resolve_champion_storage.py --version N` — F-009 is a property of MLflow 3's
  layout, not of aliases) and **derives the feature set from the version's own
  `feature_set` tag**, refusing an untagged version rather than defaulting: a
  wrong feature set that happens to fit returns a confident wrong number. The
  shadow gets its own KServe-generated host; the champion's is untouched.
- **The disagreement table is DUAL-SEND, and that was forced, not preferred**
  (`make shadow-run`, a reader). Mirroring cannot shadow v1 for two measured
  reasons — condition 2's 404, and behind it v1's 5-column signature against the
  wire's 24 (F-032's shape). So the same raw requests are built into each
  target's matrix through the ONE `taxi_mlops.features` path, which is the only
  construction under which a delta means *the models* disagree.
- **The sample is STRATIFIED and every overall number over-weights hard rows by
  construction** — 250 each from ordinary/airport/no-geometry/long-trip plus
  parity's 16 hazards, 1,016 rows. Champion MAE reads **8.61** here against
  **3.2403** on the full holdout, and `docs/bakeoff_m3.md` remains the
  measurement of record (gotcha #15: a number from a sample is labelled as one).
- **The DA memo's verdict is NO-GO for v1 — with a thinner margin than the
  kickoff predicted** (`docs/shadow_analysis_m6.md`). Long trips are the fault
  line and the only decisive segment: mean disagreement **2.65 min**, max
  **36.42**, champion closer on **63.6%**. **Airports are a tie — champion MAE
  5.97 vs 5.99, and the champion is BEHIND on within-5-minutes** — so v2's
  centroid geometry is worth ~nothing there, which is `docs/error_memo_m2.md` §7
  row 2 confirmed from a second, wire-side instrument; **the row stays open and
  now has two independent measurements pointing the same way**. On no-geometry
  rows the shadow is closer MORE often (champion 47.6%) — v2's nine geometry
  features are all NaN there, so a model that never had them is a coin flip.
  Ordinary trips are a near-tie. The verdict is still no because the holdout
  already answered on 5.9M rows and nothing here is a reason to CHANGE.
- **The admission webhook is still OFF and that is now a dated deferral.** The
  ingress values file's own note says re-enable it the day someone hand-writes
  an Ingress; that day was this story. Not done here because enabling it rolls
  the controller F-033 forced onto `Recreate` — a real ~15 s outage of the only
  route in — and **S4 hand-authors the same objects again**, so the outage is
  better spent once, there. Argued in ADR-011, routed to M6-S4.

## The release rehearsal (M6-S4) — traffic that moved, and what a rollback really costs
- **`make canary` shifted rider traffic 10% → 100% → back, and ZERO of 1,440
  requests failed.** One continuous 6-minute open-loop run at M5-S4's headline
  shape (4 req/s, concurrency 8, hazards), with the weight changed from inside
  the load client's own per-second callback so the split and the latencies share
  one clock. Observed **from counters, never from the annotation**: ingress
  `canary` label **41/420 = 9.76%** at weight 10 and **301/301 = 100%** at 100,
  corroborated by the two predictors' OWN `rest_server_requests_total` at
  **9.33%** and **100%** — two processes counting the same requests, which is
  what makes a claimed split checkable. **The revert is 0.37 s** (one
  `kubectl delete ingress`, timed against the controller's own
  `/configuration/backends` polled at 0.25 s) against §9/M6's 120 s budget, and
  it costs no requests — so the runbook now says **prefer the traffic revert**.
  The champion's predictor kept the same UID throughout: an Ingress edit reloads
  nginx and touches no pod, which is exactly what F-038 proved an **isvc**
  annotation does not.
- **ADR-011 condition 2's remedy is PROVED, both ways.** `MLSERVER_MODEL_NAME:
  nyc-taxi-eta` on the canary isvc wins KServe's merge (checked on the
  Deployment object) and the canary answers `/v2/models/nyc-taxi-eta/infer` with
  **39.0019 minutes** on its own host while **404ing on its own isvc name** —
  the negative half, because a runtime answering to both names would pass a
  positive-only check and prove nothing about which name carried the request.
- **F-039 cost the first run and is the story's best find: a hand-authored
  Ingress must not take a KServe-GENERATED name.** The route was called
  `nyc-taxi-eta-canary`, which is what KServe generates for the isvc of that
  name; `kubectl apply` wrote the canary annotations onto the controller's own
  object and the controller reverted them — **0 of 420 moved at weight 10, 3 of
  300 at weight 100**, no error anywhere. The symptom is byte-for-byte ADR-011
  condition 1's, which this program had just spent a story learning, so the
  obvious diagnosis was the wrong one. Route renamed `…-canary-route`; the drill
  now REFUSES to weight an Ingress carrying `ownerReferences` and requires the
  controller to register `noServer: true` at the applied weight first — a
  one-second precondition where the symptom cost a six-minute run. Kept unedited
  at `automation/runs/m6-canary/attempt1-ingress-name-collision/`.
- **The canary carried the CHAMPION'S OWN BYTES**, because M6-S3's DA memo
  returned NO-GO for v1. Honest cost, stated: both backends serve version 2
  under one model name, so **every response in the record carries
  `model_version: 2` and that is NOT evidence no traffic moved**. M6-S3 could
  attribute at the client only because its canary was broken.
- **F-032's un-rehearsed half is RUN — `make rollback`, both ways, PASS 10/10 —
  and F-040 is what it found.** v2→v1: alias 0.050 s · config <0.001 s ·
  `make serve` 35.30 s = **35.35 s**, with **27.93 s of failing requests (55 of
  85 probes)**. v1→v2: **34.38 s** and **0.501 s, one 502**. Gotcha #80's 0.5 s
  is what a re-DEPLOY costs; a ROLLBACK's cost is the second move. The instant
  `features.version` becomes `v1`, every client sends a 5-column matrix while
  the pod still holds the 24-column model and the logged signature refuses it
  (`HTTP 500`) — leg 1's error classes are `['HTTP 500','HTTP 502']`, leg 2's is
  `['HTTP 502']` alone. **Removing features breaks requests in flight; adding
  features does not**, because MLflow takes the columns its signature names and
  ignores the rest. The remedy (alias → `make serve` → config line last) is
  **named and UNPROVEN** — it needs two more alias moves and M6 sanctions two —
  so it is in §4 labelled do-not-substitute-mid-incident and routed to M6-S5.
- **The M5 gate was run at a state it was never written for, and that is the
  point.** At `@champion` = version 1 `verify-m5` went **RED with 3 FAILs while
  §2's coherence check stayed GREEN at `v1`** — green at v2 alone is satisfiable
  by a literal. Two of the three failures were the gate ASKING the endpoint for
  a prediction and noticing a different model serves; the drill's prediction had
  said "only about the bake-off winner" and that is kept as a superseded
  prediction. **The check was corrected and the verdict RE-JUDGED from the
  recorded evidence** (`--rejudge`, the `verify-m3` replay idiom) rather than by
  spending two more sanctioned alias moves.
- **`verify-m5`'s own NOT-REHEARSED assertion was gotcha #50 waiting to fire.**
  Running the rollback correctly would have turned it RED. It now reads the §4
  HEADING (not the body — §4 legitimately contains both "REHEARSED 2026-08-19"
  and a sentence about an un-rehearsed mitigation, and the first repair got that
  wrong) and requires a dated rehearsal claim to cite a record this repo holds.
- **End state is exactly M5's**: canary torn down, `@champion` **2**,
  `features.version` **v2**, `configs/train.yaml` byte-identical by
  `git hash-object`, `make verify-m5` **GREEN**, `make parity` **0.000e+00** over
  16 hazard rows. The v1 shadow is deliberately LEFT RUNNING for M6-S5.

## Gameday 1 and the first restore (M6-S5 leg 1) — every alert behaved, and two of our written arguments did not
- **`make gameday` is four scenarios in one order, and the POSITIVE CONTROL is
  first because three of the four make a claim of the form "alert X did not
  fire".** That sentence is worth nothing from an instrument nobody has just
  watched work — a Prometheus that lost its rules would produce a flawless run of
  silent alerts. Control (M6-S2's injection, delegated to `alert_fire_drill.py`,
  not re-implemented): **GREEN 11/11**, A-3 at **T+170.5 s**, A-2 at **T+335.6 s**,
  both at **Alertmanager**, both clear **330.1 s** after the stop — and that clear
  time is a floor, not slowness: with no other traffic the ratio holds until the
  last sample leaves the 5-minute window, at which point the expression is `NaN`.
- **EVERY prediction was on disk before the first injection**
  (`automation/runs/m6-gameday/predictions.json`, committed) and a test asserts
  the committed file still equals the code's `PREDICTIONS` — so amending a
  prediction to match an outcome is a RED test, not a diff nobody reads.
- **F-041, the wrong prediction that matters: A-2's and A-5's thresholds were
  argued from a STEADY-STATE ratio, and the transient crosses them.** The SLO doc
  computed that a ~15 s outage costs ~60 of the ~1,200 requests in a 5-minute
  window (~5%) and concluded 10% is "unreachable by any single recovery". The
  kill measured the edge 5xx share **peaking at 0.5000**, with **A-2 pending
  T+89.2 → 103.2 s** and **A-5 pending T+59.1 → 74.1 s**. `rate(...[5m])`
  extrapolates from the samples IN the window, and 30 s into a load run that
  window holds 30 s of traffic — 6.1% is what the ratio decays TO, not what it
  reaches. **What stops a self-heal paging is the `for:` sustain, not the
  threshold.** No number moved; the argument was corrected beside the original
  (the `error_memo_m2.md` §9 precedent) and one operational fact got written down:
  **during any ordinary self-heal an on-call sees A-2 and A-5 sitting `pending`,
  in red, and neither will ever fire.**
- **The kill itself is the fourth number in a family**: **13.75 s** (55 of 1,200
  requests, 52×503 + 3×502, a different pod uid) against 14.53 s (killed pod,
  M5-S4), 15.0 s (ingress roll, M6-S1) and 18.24 s (stop/start, M5-S5).
- **The storage break went 8/8 and its value is the three rows that are not the
  pass.** `403 … HeadBucket: Forbidden` — M5-S2's class exactly — then **A-5 at
  T+150.2 s and A-7 at T+210.2 s**: A-5 FIRST, the opposite of what A-7's own
  `why` annotation claimed (**F-042**, annotation corrected, threshold
  deliberately NOT touched). **A-2 stayed inactive through a TOTAL outage** — its
  documented blind spot demonstrated rather than asserted. And the flapping rule
  stayed inactive because it counts `kserve-container` restarts while all three
  restarts were the INIT container: a rule written against "the pod restarted"
  would have blurred two signatures into one. The undo was staged BEFORE the
  injection (pinned by a test on line order) and `make serve` cleared both alerts
  within 30 s.
- **Saturation fired A-6 at T+844.3 s = 244.1 + 600.2 — the sustain clock starts
  when the RATIO crosses, not when the load starts.** The throttled fraction
  climbed 0.414 → 0.686 → 0.826 → 0.927 → 1.000 over five minutes as the window
  filled (F-041's mechanism with the sign reversed), ending at **0.9996**. Client
  p50 latency **94,553 ms** against service p50 **1,084 ms** at an achieved
  **6.775 of 8 req/s** — the open loop showing a backlog a closed one would hide.
- **The second wrong prediction: saturation DOES produce errors, given time.**
  **125 × HTTP 502 of 6,240 (2.00%)**, where M5-S4's 60-second ramp measured zero
  at the same rate. Gotcha #74 is refined by DURATION, not reversed: latency
  first, errors much later — and at 2.00% nowhere near A-2's bar, so the page a
  saturated service produces is still A-6's.
- **F-043 (OPEN, routed to the M6→M7 boundary): the predictor's own exporter
  starves under the condition it exists to report.** A-1 fired at T+349.3 s and
  cleared itself at **T+514.3 s while the load was still running**. Measured over
  the window: the loaded predictor's `/metrics` reached **`scrape_duration`
  4.613 s with `up == 0`** (a scrape failed outright) while the IDLE v1 shadow,
  scraped by the same job every 15 s, stayed at **0.004 s / `up == 1`**. A failed
  scrape makes the series stale and A-1's expression evaluate over nothing. The
  SLO doc already argues A-2 belongs at the EDGE because a dead predictor cannot
  report its absence; **a predictor does not have to die to stop reporting, it
  only has to be busy** — and the signal that held up (A-6) reads the kubelet's
  cAdvisor, a different process on the node.
- **The restore is REHEARSED — into SCRATCH state, and the label moved exactly
  one notch.** `make restore-drill` GREEN **17/17**: mlflow **2.34 s** · optuna
  **0.78 s** · metabase **7.29 s** into `<db>_restore_drill` databases with
  `ON_ERROR_STOP=1`, every counted table equal to the LIVE database, the restored
  registry carrying the same `champion|2` pointer, the restored studies carrying
  the trial counts `automation/runs/m3s4` recorded (**a second witness that is
  not the live database** — live-vs-restored alone is also what restoring the
  wrong backup into the wrong place would show), `flyte-data` restored WHOLE (184
  objects / 783,327 bytes) and one MLflow artifact **byte-identical by sha256**.
  Live databases and buckets untouched, no scratch survived. **A full restore
  over a DEAD platform is still un-rehearsed** and every artifact says so.
- **The restore drill's first run went RED on a check that was wrong**, and the
  correction is worth more than the check: it compared the Metabase app-db
  against `analytics/metabase/boards/*.json` by COUNT (3 dashboards / 28 cards)
  and found 4 / 67. Nothing had drifted — `metabase_boards.py` converges by name
  and NEVER deletes (M1-S5's stated asymmetry), and Metabase's setup creates its
  own `E-commerce Insights` example dashboard. **"The boards are checked-in JSON"
  is a claim about OUR boards, never that the app-db mirrors the repo.** The
  check is a subset-by-NAME check now.
- **`make verify-m6` IS NOT BUILT — that is the declared leg boundary** (the
  M4-S5 precedent, and the M6 kickoff names it as a legitimate stopping point).
  End state is exactly M5's: `@champion` **2**, `features.version` **v2**,
  `make verify-m5` **GREEN 49/49**, `make parity` **0.000e+00** over 16 hazard
  rows, endpoint answering. The v1 shadow is still up.

## The M6 gate (M6-S5 leg 2) — what it asks, what it refuses to ask, and the labels it found stale
- **`make verify-m6` is 63 sub-checks in 7 sections, 2.147 s, and it RE-RUNS
  NOTHING** — the strongest form yet of a clause M3 started, because M6's
  evidence cost ~55 minutes of staged failures **including a deliberate ~5
  minute total outage of the only predictor**, two alias moves and two weight
  shifts. A gate that re-provoked any of it would cost an outage per
  verification AND would move the pointer M6 law 3 forbids moving. No skip flag,
  no fast mode (M1's rule, **sixth** inheritance). It reads: the tracked records,
  the live cluster, the live Prometheus, the registry, the committed docs — and
  it asks the live system exactly three questions: one PromQL query, one
  rules-API read, one prediction.
- **The live question no predecessor gate could ask is F-043's.** The gameday
  found the predictor's own exporter starving under saturation (4 ms → 4.613 s,
  one scrape failing outright) so the latency alert cleared itself mid-event. §1
  asks whether that exporter is healthy RIGHT NOW — one query, scoped to the
  champion's InferenceService **by name read off the manifest**, never "the
  first result" (the gameday's own storage record picked up the SHADOW's series
  that way), and bounded by the scrape interval **read from the values file**
  rather than by a typed number.
- **No threshold is typed, and that is what makes §2 a review surface.** Every
  number on the right-hand side of a comparison in
  `infra/monitoring/alerting_rules.yml` is parsed out and looked for in
  `docs/slo_serving.md`; a gate carrying its own `0.05` would stay green after
  the rule was loosened to `0.5`, which is exactly the change the constitution
  reserves for a PO fork. The `for:` sustains are compared file-vs-server too,
  because **F-041 made the sustain the load-bearing half**: what stops a
  self-heal paging is the sustain, not the threshold.
- **"Shadow before canary" is an ORDERING, and it is checked on clocks.** The
  disagreement record says 14:49:23Z and the canary run says 15:23:48Z — two
  records, their own stamps, not the order the write-ups are arranged in. It is
  the only check that could catch that clause backwards.
- **"90/10 observed" means a counter, and it means two of them.** ingress
  9.76% against the two predictors' own 9.33%, 0.43 points apart — different
  processes counting the same requests, which is what makes a claimed split
  checkable (gotcha #81: a canary that is linked, logged clean and moving zero
  traffic looks exactly like a canary at 0%). The gate also asserts the record
  keeps its own **honest cost** — the canary carried the champion's bytes, so
  the version stamp proves nothing about the split.
- **The gameday's predictions are checked TWICE and both are necessary.** They
  were written before the first injection **by clock** (16:03:35Z vs 16:15:07Z,
  the records' own stamps, never the file's claim about itself), AND each
  scenario record's prediction is **field-by-field equal** to the committed
  file — because a prediction can be written first and then quietly edited into
  the record it is judged against.
- **The kill's outage is re-derived from its own arrivals** (gotcha #75, the
  `verify-m5` §5 idiom transplanted): an outage closes on the first SUCCESS
  after the last failure, so it is strictly LONGER than the error span and
  inside one arrival gap of it — a bound computed from the run's own rate. That
  is the check `verify-m6-redteam` plants against.
- **Two stale labels, found by the gate on its first run — F-044.** The restore
  label had moved one notch everywhere except the `echo`
  `scripts/platform_backup.sh` PRINTS (the only version an operator sees) and
  `ledgers/deployments.md`, while CLAUDE.md asserted every artifact said it.
  **The header is for review; the runtime line is for 3am** (gotcha #91). The
  historical M4-S2 ledger row keeps its original sentence with a DATED note
  beside it — decisions were made from what it said.
- **The red team's own first run went RED on the gate, not on the record**
  (gotcha #90). It plants `observed.outage_seconds` 13.75 → **13.501**, the
  record's OWN error-window span; §7's prose leg rendered 13.75 at ZERO decimals
  as `14`, which appears in almost any document, so the planted value matched
  too and only ONE witness spoke. The precision floor is one decimal now. This
  is gotcha #76 a second time, arriving through rounding instead of
  tokenisation — and both were only ever found because the planted value was
  close enough to be plausible.

## The scoring months (M7-S1) — the same pipeline pointed somewhere else
- **A scoring month is not a fourth split, and the trees are how that is
  enforced.** `configs/data.yaml: scoring` names 2020-01..03,
  `data/scoring/<month>/` and `data/scoring_rejected/<month>/`, each with its own
  DVC pin. One 2020 row inside `data/processed/` would reach the training matrix,
  the dbt marts and every board through globs written when that directory meant
  "the settled 2019 months" — with no error anywhere. `trips_clean` is
  deliberately NOT unioned with the new rows and a test asserts
  `SELECT DISTINCT split FROM trips_clean` is still exactly `{train,val,test}`;
  four new views (`trips_scoring`, `trips_scoring_rejected`, `scoring_months`,
  `scoring_rejections`) carry the 2020 data and a consumer must ask for them.
- **The months are named in data.yaml, not train.yaml, and the one mistake that
  makes possible is REFUSED.** Split months are a MODELLING fact (what a model is
  fitted to and judged on); a scoring month is the opposite. `load_config` raises
  if a month appears in both lists — a month cannot be both trained on and
  scored for drift, because then its drift reference would contain itself.
- **ONE code path, and the tree comes from config membership.** `ingest_month`
  writes through `cfg.output_path`/`report_path`/`sidecar_path`. The old
  `processed_path`/`rejected_path`/`rejections_path` are UNCHANGED and still
  raise for a scoring month, pinned by a test: every existing caller means "the
  settled months", and a dispatcher hiding inside them would put a 2020 month
  wherever any of them is called. `make data` is untouched too — `make
  data-scoring` is a separate command, because one command doing both would make
  every scoring ingest a rewrite of the trees the program's numbers rest on.
- **Observed: 15,712,062 → 15,413,352 rows (1.901% rejected).** `make duckdb`
  now runs **five** reconciliations (16 views): the scoring views' rows against
  the reports that wrote them (15,413,352 == 15,413,352) and the scoring sidecar
  per (month, rule) (**298,710 == 298,710, 30 pairs, 0 disagreements**). Both
  red-teamed in unit form. The settled numbers are unchanged: 56,127,878 clean,
  914,459 sidecar, 12,140,456 predictions.
- **M7 law 2 held and is checkable**: `dvc status data/processed.dvc
  data/rejected.dvc` → `up to date`, neither `.dvc` modified in git,
  `data/raw_manifest.json` **+18/−0 with zero diff lines mentioning 2019**. And
  the new tree inherited the old one's best property for free — a full second
  `make ingest-scoring` left `data/scoring.dvc` up to date, i.e. 15.4M rows
  re-derived byte-identically, because it writes through the same
  `write_processed` under the same pinned writer options.
- **The pre-routed risk did not materialise, and the way it did not is the
  point.** 2020-03 rejects **1.977%** against a `max_rejected_fraction` of 0.10
  — indistinguishable from 2020-01's 1.955%. **March 2020 is structurally
  impeccable and statistically alien**: nothing about the file is wrong, there is
  simply half as much world in it (3,007,687 raw rows against 6,405,008). No
  threshold was touched because none needed to be.
- **The 2025 leg was a MEASUREMENT and it came back VALIDATED — a SURPASS.** The
  real `yellow_tripdata_2025-01.parquet` (59,158,238 bytes, 3,475,226 rows, 20
  columns) passes the shipped contract with ONE schema event, `alias applied:
  'Airport_fee' -> 'airport_fee'`. Three M1-S1 mechanisms carried it untouched:
  the alias entry, `from_year: 2025` making `cbd_congestion_fee` required and
  present, and THE cast absorbing 2025's int32/int64 spread. It does NOT claim
  2025 could be ingested and used — validation is a structural verdict, and the
  cleaning profile and a 2019-fitted champion's meaning on 2025 data are unasked.
- **So the refusal was watched on fixtures instead, and the exit code is the
  assertion.** `make contract-probe-fixtures` breaks the REAL file three ways —
  `drop-required`, `rename-required`, `unknown-column` — and requires **exit 1**
  from each plus four empty data trees afterwards. A refusal that exits 0 is a
  refusal a pipeline cannot hear. **The rename fixture found a real defect**: a
  renamed column is both an absence and an arrival, and `check_columns` raises in
  the missing branch before the unknown branch can run, so the message named
  `['VendorID']` as vanished and said nothing about `VendorID_v2` sitting right
  there. Both are named now, with `aliases:` offered as the fix. Each branch was
  individually correct — only running the fixture showed it.
- **The two signatures M7-S3 must keep apart, now on the record** (§8 of the
  write-up): statistical drift = contract passes, exit 0, 2,948,237 rows written,
  a distribution that moved; schema drift = `SchemaEventError`, exit 1, **no
  output, no sidecar, no report — and therefore NO DRIFT METRIC AT ALL**. The
  second is the dangerous one: a drift dashboard showing "no alert" looks
  identical to a healthy month, which is gotcha #78's empty-panel disease with
  the panel removed entirely.
- **F-045 (open, routed to M7-S3) is the most useful thing this story measured.**
  A drift metric over a WHOLE MONTH may not fire on the most drifted month this
  program will ever hold: 2020-03's mean trip duration is **13.1645** against
  2020-01's **13.2123** — a **0.36%** move, *smaller than the ordinary Jan→Feb
  wobble* (+2.71%) — while its daily series runs **240,520 trips at 14.878 min on
  2020-03-05** to **5,361 at 9.715 min on 2020-03-29**. The monthly aggregate is
  dominated by the ten ordinary days at its head. **Volume is the one marginal
  that cannot be averaged away.** Three readings are costed in the ledger and
  NONE is chosen here: the window, the reference and the bar are S3's to argue
  before the job runs (M7 law 4).

## Batch inference as a product (M7-S2) — the check a monitoring table cannot make for itself
- **`make predictions-scoring` is the whole path**: resolve `@champion` (F-009's
  two hops) → **prove the path on the holdout** → score every scoring month →
  parquet + manifest. **15,413,352 rows across 2020-01..03**, `@champion`
  version **2** before and after, no run minted, no version created, no pointer
  moved (AST-tested, not grepped).
- **The self-check is the story's centre, and it exists because these rows can
  be checked against NOTHING.** M2-S4's rows have an anchor — the champion's
  `gate_challenger_mae` tag says 3.2403 on the holdout, so re-scoring must
  return 3.2403 or nothing publishes. No tag says what the champion scores on
  2020-03, because no gate ever asked, and **a wrong-but-plausible MAE on a
  COVID month reads exactly like drift** — which is what the next story will be
  asked to believe. So the path re-scores the HOLDOUT first and refuses to write
  a single monitoring row unless the tag comes back: **measured 3.2403, MATCH.**
  A month with a known answer proves the loader, the feature path and the
  booster; only then is a month with no known answer written. ~2 min of the run,
  and deliberately not optional.
- **A fourth output tree, and the reason is specific rather than tidy.**
  `data/scoring_predictions/` is NOT a subdirectory of `data/predictions/`,
  because that directory is globbed by `predicted_months`, read by the
  `predictions` view and aggregated by `error_segments` — whose `overall` row is
  asserted EQUAL to the evaluator's KPI-09/KPI-10 by a dbt test. A 2020 file
  inside it either turns that test red for a correct batch run or lets a board
  render a monitoring number under a promotion KPI's id. Gitignored, not
  DVC-tracked, on M2-S4's terms exactly.
- **KPI-14/15/16/17 are new ids because the WINDOW is new** — a scoring month
  the champion was never *judged* on. Same instrument (`evaluate`, gotcha #15),
  new window, new ids, and the manifest SPELLS them in its keys so a reader
  cannot mistake one for the other. **KPI-16 (signed bias) is the one that says
  which thing broke**: an absolute error cannot tell a model quoting three
  minutes too long from one quoting three minutes too short, and in a month
  where the traffic vanished those are opposite diagnoses.
- **The monthly row hides the month, and this is F-045 measured on the OUTPUT
  side.** 2020-03's whole-month KPI-14 is **3.3227** — ordinary beside
  2020-01's 3.0295. Split at the collapse: **Mar 01–10 is 68.23% of the month's
  rows at KPI-14 3.0463** (January, to two decimals) · Mar 11–21 is 28.45% at
  3.7534 · **Mar 22–31 is 3.32% of the rows at KPI-14 5.3128, KPI-15 62.118%
  and KPI-16 +4.1412**. A row-weighted average is weighted by exactly the rows
  that vanished. Worst day **6.3693** (2020-03-26) against January's worst of
  3.5757; mean actual falls to 9.69 min while the champion keeps quoting 13.83 —
  *the world changed and the model did not follow*. **No threshold is set here**
  (M7 law 4): the window, the reference and the bar are S3's.
- **The mart is DAILY for that reason** — `marts.scoring_daily`, 91 rows,
  full-refresh, `dbt build` **PASS=80** (was 57). Monthly numbers are a
  `GROUP BY month` away from these rows; the reverse is not true.
  `model_versions_seen` must be **1** per day, asserted: M7's alias may move
  through the gate, and a spliced series would be averaged into invisibility.
  **No floor column and no margin**: the floor is fitted on the 2019 train
  months, and a 2020 margin against it would publish a comparison no gate ever
  made against a bar chosen for a different world.
- **`make duckdb` now runs SIX reconciliations over 17 views**, exit 1 on any.
  The new one's authority is the INGEST REPORT, not the predictions file —
  comparing the mart against the predictions alone would prove SQL can sum a
  column, since a job that scored 14 of 15.4M rows would have both agreeing and
  both wrong. It distinguishes **pending** (ingested, not yet scored — normal,
  stays GREEN; a guard that fails on a correct system is gotcha #50) from **NO**
  (scored PARTLY — the failure, because half a month produces an ordinary MAE
  over rows nobody chose). Observed **15,413,352 == 15,413,352**, and again in
  dbt via `assert_scoring_daily_reconcile`, which travels with the mart into the
  publish.
- **Host-rehearsed, not on-cluster, and said out loud.** The entry point is a
  plain callable in `src/` importing no orchestrator (the boundary law);
  **S4 wires the Flyte stage**, and pays gotcha #66's cold cache once — this
  story commits under `src/`, `scripts/` and `analytics/`, so the next
  on-cluster run rebuilds its image regardless.

## Drift detection (M7-S3) — the shape alert that correctly did not fire, and the volume alert that did
- **COVID March's most-moved INPUT column sits at PSI 0.0217 — lower than an
  ordinary July 2019 does (0.0323).** That one number is the story. By the shape
  of its requests March 2020 is not a strange month: the city did not start
  taking different taxi trips, it stopped taking taxi trips. Volume ratio
  **0.3913** against the reference's trips/day. So **A-8 (input drift) correctly
  stayed inactive and A-9 (volume) FIRED at T+331.5 s** — and had A-9 not existed
  as a separate signal this stack would have watched the collapse in silence with
  every drift panel green. `docs/slo_serving.md` §8.1 argued *before the run* that
  **PSI is a distance between SHARES, so halve every count and PSI is exactly
  zero** — A-9 is the marginal A-8 is structurally blind to, not a refinement of
  it. Written first, then demonstrated.
- **F-045 is now measured from THREE sides and they agree.** M7-S1 in the raw
  data (monthly mean duration moves 0.36%, less than an ordinary Jan→Feb wobble)
  · M7-S2 on the output side (whole-month KPI-14 3.3227 hiding a last-ten-days
  5.3128) · M7-S3 on the INPUT side (monthly PSI 0.0217). Three independent
  instruments, one conclusion: **a monthly aggregate cannot describe this event,
  and only volume survives the averaging.**
- **The order of work IS the argument, and it is checkable from git.** M7 law 4
  bites hardest here because a drift bar is argued against a month this program
  fetched *because* it expects it to be extreme. So: the **headroom leg ran
  first** reading 2019 ONLY (`headroom.json`) → the bars were written from it →
  the **prediction was written** → *then* 2020 was compared. Steps 2–3 are in
  commit `d113f26`, which lands before any 2020 drift record exists in the repo.
- **The bar is argued from months whose verdict already exists.** The two
  held-out 2019 months are the only data here *known* not to have warranted
  action — the champion was measured on them and PROMOTED. Highest input PSI
  across both: **0.0323**, and *what* it is matters as much as its size —
  `dayofweek` in July 2019, i.e. five Mondays, **calendar arithmetic**. Largest
  behavioural: 0.0137. So **0.10 is 3.1× the noisiest accepted month and 7.3× the
  largest behavioural one**, and it independently coincides with the published PSI
  convention — which matters because an on-call who did not write the doc already
  has a prior for what 0.10 means. A house-special 0.037 would not.
- **The job pushes raw quantities and issues NO verdict.** No threshold exists
  anywhere under `src/taxi_mlops/monitoring/` — the bar lives in the SELECTOR of
  one rule (`count(taxi_drift_psi{column!="trip_duration_minutes"} >= 0.10) >= 2`),
  so the pushed numbers stay re-interpretable after the fact. Pinned by an **AST**
  test, never a grep (these modules argue their own design at length — #53/#68).
  M5-S4's load-drill precedent: *a READER that does not judge*.
- **`honor_labels: true` is the one flag the whole thing rests on.** Prometheus
  overwrites a scraped sample's `job` with the target's — correct for a service
  reporting on itself, exactly wrong for a gateway reporting on somebody else.
  Without it every drift series arrives as `job="pushgateway"`, every rule selects
  `job="taxi-drift"` and matches nothing, and **the rules do not error — they sit
  inactive forever**, indistinguishable from a healthy system. Also why the
  gateway is deliberately NOT annotated for the generic endpoints job.
- **The gateway is a bulletin board, not a store of events**, and two guards in
  two layers say so: `push_metrics()` **refuses** a payload with no
  `*_last_run_timestamp_seconds` (a type), and **A-10** fires on a stamp older
  than 40 days (a rule). A pushed metric persists after its producer dies, so
  "drift is fine" and "the drift job died in March" render identically otherwise
  — gotcha #78's empty-panel disease inverted: not a blank rectangle that looks
  like calm, but a stale number that looks like health.
- **"Then cleared" needed an argument, not a copy.** M6's drill cleared by
  STOPPING an injection; this drill injected nothing — March 2020 really did lose
  61% of its trips and an alert saying so is correct. So the clearing is
  demonstrated on the MECHANISM (delete the group, watch A-9 go inactive, proving
  the rule follows the data and is not latched) and then **undone**: the real
  numbers go straight back and the board ends carrying the truth. The decision
  that alert asks for is M7-S4's retrain, not a silence.
- **Evidently is ADOPTED (0.7.21), and it is the SECOND witness by argument.**
  Probed FIRST in an isolated venv pinning the four numeric cores — the risk
  table's headline risk did not materialise: 27 packages installed, 1 uninstalled
  (the project, rebuilt), **pandas 3.0.5 · numpy 2.5.2 · scipy 1.18.0 ·
  scikit-learn 1.9.0 · lightgbm 4.7.0 · mlflow-skinny 3.15.1 all unchanged**. It
  is not the alerting instrument because five of six monitored columns are
  categorical, so DuckDB computes their distributions EXACTLY over 43,987,422
  reference rows — and a sampled estimate of an exactly-computable quantity is a
  worse number **that also moves between runs**. On the question the alert asks —
  *did any INPUT column drift?* — **the two instruments AGREE for both months:
  none did.** And read sceptically: Evidently flags the TARGET at 0.1014 in
  January and 0.1008 in March, essentially the same value in an ordinary month and
  in the collapse, so it does not distinguish them either.
- **F-035 CLOSED by landing, and the closure is ENFORCED rather than asserted.**
  Both absences had one cause — *the fact lives in a client and no client is
  scraped* — and the gateway fixes it. A-3's client half is
  `taxi_quote_refusals_total` with `increase(...[1h]) > 0`, and that shape is the
  argument: **one refusal means the holiday horizon expired, a fact about the
  REPOSITORY not about traffic**, so a single event is the event. A-4 is
  `scripts/push_serving_version.py`, which makes the two series F-034 said did not
  exist. `IMPLEMENTED_SIGNALS` now holds all ten ids, `DOCUMENTED_ABSENCES` is
  empty, and `validate()` fails in BOTH directions — the closure could not have
  been written in prose without the rules existing. **Honest cut: the metric
  SOURCE lands here; the CADENCE lands with M7-S4's scheduler**, which is why
  A-4's rule carries a freshness clause and `verify-m5` §2 stays the check that
  actually runs.
- **F-043 CLOSED as `docs/slo_serving.md` §2.2** — option (c), the boundary's
  decision. The measurement rather than a caution (4 ms → **4.613 s with one
  scrape at `up == 0`**, against the idle shadow's 0.004 s on the same job), a
  table of which instruments survive saturation, and **A-1 carries an
  `instrument_limit` annotation AT THE RULE** where an on-call reads it. No target
  loosened, no threshold moved. The generalisable line: **the cheapest control for
  "is this exporter lying?" is a second, idle instance of it scraped by the same
  job** — here that control was an accident, and it is the only reason F-043 is a
  measurement rather than a theory.
- **Two checker defects, both found by running the thing.** The drill judged
  per ALERT NAME while its prediction is per **(alert, month)** — A-9 is predicted
  to fire for 2020-03 *and* stay quiet for 2020-01/02, three statements about one
  rule — so it reported `A-9 fired and was predicted INACTIVE` over a system
  behaving exactly as predicted (#67's family). Reading the per-series `alerts`
  array is also the STRONGER claim: a bar so low that an ordinary January trips it
  passes a name-level check and fails this one. And the prose-vs-rule threshold
  test **passed `1800` by accident** (`"1800".rstrip("0")` is `"18"`, which
  matches `18.24 s` in §7.1) while failing `3456000` honestly — gotcha #76 found by
  the test on itself; exact match only now, and the doc carries the raw seconds.
- **Monthly grain is a known limitation, not a defended choice.** The kickoff
  specifies "current = one scoring month" and that shipped. §4 shows the cost: at
  this grain the input signal is flat through a catastrophe. A daily window would
  very likely fire A-8 on 22–31 March, and the daily series already exists
  (M7-S2's `scoring_daily`). **Deliberately not done here** — changing the window
  after seeing that A-8 stayed quiet is exactly the threshold-walking law 4
  forbids, because the window is part of the bar. Routed to ARCH at the boundary
  with the evidence.

## The scheduled retrain (M7-S4) — the transfer nobody had made, and a pointer that was pre-registered
- **Two findings, one shape: a number that was true where it was written, applied
  where it is not.** F-022: a bake-off row resolved the champion BY ALIAS (so the
  table judges what is serving) *and* pre-registered `feature_set="v1"` — both
  true the day they were written, and the bake-off's own `--promote-winner` then
  moved the alias to a v2 model, so every invocation since died at a refusal that
  was correct one layer too late. F-020: `min_data_in_leaf: 1293` was chosen on
  15% of train and applied at 100% — the same integer means **1 row in 5,103**
  where it was chosen and **1 in 34,020** where it was used. The distinction that
  fixes both: **pre-registration is right for a thing declared before its number
  existed and exactly wrong for a pointer designed to move**, and a
  hyperparameter is a number PLUS the scale it means it at.
- **F-022 CLOSED, both halves.** `Spec.feature_set` is `None` for the alias row;
  `_feature_set_of` derives the concrete set from the loaded booster's ORDERED
  feature names against `configs/features.yaml` and requires exactly one match;
  everything downstream reads `Loaded.feature_set` (AST-pinned — the file argues
  the change in prose that quotes the old label, #53/#68). The four
  pre-registered arms keep their Specs. Execution: `make bakeoff
  BAKEOFF_ARGS="--smoke-rows 20000"` -> **exit 0**, `champion (alias)
  auto-lgbm-v2 … features=v2 (24) (DERIVED from the artifact)`. **Honest cost,
  recorded**: the 2x2's origin cell (v1 features, hand params) was held by the
  incumbent row only by coincidence, so with the alias on a tuned v2 model the
  square would print `auto-on-v2 +0.00%` — correct arithmetic answering a
  different question. `SQUARE_BASE` describes the cell and the square is NOT
  printed when nothing occupies it. **Side finding**: `v1_g5` and
  `redteam_g5_leaky` declare identical ordered columns, so a model fitted on
  either is unidentifiable from its artifact — the derivation refuses rather than
  picks (neither is promotable, so refusing is the safe direction).
- **F-020 CLOSED by option (a) with option (b)'s rule landed as CODE.**
  `COUNT_SCALED` names the knobs whose LightGBM meaning is literally a row count
  (`min_data_in_leaf`, `min_data_in_bin`, `min_sum_hessian_in_leaf`), each with
  its reason and a test that refuses an entry whose reason does not argue it;
  everything else is passed through **and recorded as passed through**, because
  "considered and it does not scale" and "never looked" are different statements.
  `round_budget` re-derives the cap (the sniper's per-trial **800 x 3 = 2400**,
  floored at the configured 500) and the fit reports **`ended_by`** —
  `early_stopping` or `round_cap` — as a first-class field, which is the half a
  metrics table cannot show: the champion's own refit ended **791/800**.
- **The provenance is a chain of three TRACKED artifacts and an absent chain is a
  REPORTED no-op.** alias -> version -> RUN for the params (a config records what
  was configured; a run records what happened), then refit record -> study ->
  sniper record for the scale. A champion with no sampled search behind it has no
  transfer to make, and saying so is the whole point — F-020 IS the finding that
  assuming a sample fraction produces a plausible configuration nobody can check.
- **The generated training config is not a second home.** Every block except
  `model` is copied from `configs/train.yaml` verbatim (`COPIED_VERBATIM`:
  data/target/features/baselines/evaluate/**gate**/registry/mlflow) and a test
  asserts equality block by block; the tuned params sit ON TOP of the configured
  base, never instead of it (a tuned dict as the whole param set silently drops
  `objective: l1` — the loss KPI-09 is defined as). It is written under
  `automation/runs/m7-retrain/`, not under `configs/`, because `configs/` is
  where a human legislates.
- **It cannot promote, and that is structural.** `run(promote=False)` is passed
  unconditionally and `retrain()` has NO `promote` parameter — a law with a
  keyword argument is a default. An unattended job that can move `@champion` can
  put an unreviewed model in front of riders at 04:00; **a PROMOTE verdict is
  recorded and the alias stays where it is**, because promotion deferred is a
  state the registry expresses honestly and half a transition is not. Exit codes
  are `make train`'s own language: **0 passed · 1 refused · 2 could not build ·
  3 no verdict issued** (F-008).
- **Flyte 2.6.1 / chart v2.0.42 carries triggers NATIVELY — the kickoff's cron
  fallback was NOT executed and stays armed**, one attempt of a three-attempt
  wall. Asked of the tooling, not read off a version table (gotcha #70's family).
  **Declared in CODE with their inputs**: `flyte create trigger` cannot pass task
  inputs, so a CLI-created trigger would fire the retrain with its DEFAULTS and
  the cadence would live in somebody's shell history. Two triggers on one task:
  **`retrain-monthly`** (`Cron("0 3 1 * *")`, full-data, judged, **`auto_activate:
  False`**) and **`retrain-schedule-proof`** (`FixedRate(20)`, `plan_only=True`).
  The monthly one is registered and inactive ON PURPOSE — this cluster is a
  laptop and the full-data fit is hours of CPU under a 6-core task limit; turning
  it on is one field and a PO's call about compute.
- **The proof trigger PLANS ONLY, and that is what makes it a proof of the
  schedule.** It exercises the trigger firing, a pod on the pinned image, the
  PodTemplate's MLflow/MinIO wiring, the registry read, F-020's transfer and the
  record write — and stops exactly before the hour of CPU. A proof that fitted
  would be measuring the fit.
- **`make retrain-schedule` reads the triggers back OFF THE CONTROL PLANE**, never
  off the file it submitted (`deploy_serving.sh`'s ConfigMap precedent; gotcha
  #81 one layer up — a registered trigger and a firing trigger look identical in
  a configuration table). It also **refuses a stale image**, with `pipelines/` in
  its guarded paths where `run_pipeline.sh` deliberately leaves it out: there
  `pipelines/` is the per-run code BUNDLE, so guarding it would refuse the drill
  that edits it — but a trigger has no per-run bundle, the image is the only
  carrier of both halves, and a schedule fires forever. **The guard fired on this
  story's own commit and the image was rebuilt rather than the guard narrowed.**
- **The retrain is ONE stage, not seven, and it is outside `main`.** The monthly
  pipeline's upstream stages turn a NEW month into a matrix; a retrain reads the
  SETTLED window and changes nothing about the data, so inside `main` its cache
  key would depend on a month it never reads. Uncached for `register`'s reason
  (a cached answer to "what is serving right now?" is wrong precisely when the
  alias has moved) and `retries=0` (the fit is the whole stage and hours long; a
  retry budget is a slower way to hide a systematic fault).
- **Three inherited wiring guards went red for a correct addition and were
  RE-DERIVED rather than widened** (gotcha #50, sixth time): the pipeline's task
  set is now *what `main` awaits*, asked of the AST, so it stays true for
  additions nobody has thought of.

## The drift memo and the fourth board (M7-S5 leg 1) — what a monthly average is weighted by
- **Every honest monthly number about March 2020 understates it, and by the same
  ratio.** Mean duration **13.1645** against January's 13.2123 (**0.36%**);
  whole-month KPI-14 **3.3227** against 3.0295; max input PSI **0.0217**, lower
  than an *accepted* July 2019's 0.0323. None is wrong; all are dominated by the
  head of the month — **68.231% of March's rows fall before the 11th, 3.321%
  after the 21st**. A row-weighted average of a collapse **is weighted by exactly
  the rows that disappeared** (F-045, stated in the form that generalises).
- **The memo cuts March in three and declares the cut ONCE** (`PERIOD_SQL` in
  `scripts/drift_memo_numbers.py`), from the data and not from a news archive:
  the daily series is flat through the 10th, falls continuously from the 11th,
  and sits at its floor from the 22nd. Peak **240,520 trips (03-05)** →
  **5,361 (03-29)**, a **97.8%** fall in 24 days.
- **The world changed in a way PSI is structurally blind to, and the memo says
  which way.** Mean duration **−26.6%** while mean distance **+6.1%** — the
  median trip went **49.3% faster** (10.2062 → 15.2339 mph). The night ended
  (21:00–03:00 loses 46–67% of its share; 01:00 goes 1.888% → 0.676%) and the
  morning arrived earlier (06:00 **1.935% → 4.461%**), so the day's busiest hour
  moves from **18:00 to 14:00**. Passengers per trip 1.5180 → 1.3028. The
  contract had nothing to say: **1.9766% rejected against January's 1.9548%**,
  same rules in the same order.
- **KPI-16, the signed bias, is the number that reads as a diagnosis.** It climbs
  **+0.0369 (03-09) → +5.3197 (03-26)** and never turns negative after the 9th:
  on the 26th the mean actual trip was **9.699 min** and the champion's mean
  quote **15.019**. An absolute error cannot distinguish a model quoting too long
  from one quoting too short, and in this month those are opposite diagnoses with
  opposite fixes. March's worst day (**KPI-14 6.3693**, KPI-15 **53.723%**) is
  **78% worse** than January's worst.
- **The model's best days in the collapse are the days it was already told the
  city would be quiet.** Weekend error sat **31.4% below** weekday error in late
  March against **13.5%** in January, and the daily-series dips land exactly on
  03-21/22/28/29. `dayofweek` is the champion's only vocabulary for "quiet city"
  and it is a seven-valued one — it had a word for the event and could reach it
  two days in seven.
- **`docs/error_memo_m2.md` §7 row 2 gets its THIRD measurement, and this one
  can rule something out.** The airport gap sits at **1.86–2.00×** in the three
  ordinary periods and **2.07–2.35×** through the collapse; between January and
  late March the airport MAE rose 85% and the ordinary MAE 79%, so the *ratio*
  barely moved. If the penalty were carried by DISTANCE — the one term whose
  minutes-per-mile changed when the roads emptied — the ratio had to move. **A
  quantity that holds constant across a regime change discriminates between
  hypotheses a quantity measured once cannot**; the memo recommends an airport
  flag evaluated as a *regime* indicator, not a distance proxy.
- **§9.7 row 5's condition is honoured by REFUSING the comparison.** The mart
  carries no floor column and no margin column: the honest floor is fitted on the
  2019 train months, so a 2020 margin would publish a comparison no gate ever
  made against a bar chosen for a different world. Pinned by a board test that
  fails if any card's SQL says `floor`, `margin` or `kpi_13`.
- **The board is the fourth, and every card cites a MONITORING id.**
  `Predictions & drift (M7)` (id 5, 8 cards) over `marts.scoring_daily`, checked-in
  JSON converged by name. Board laws now tested: only KPI-14/15/16/17 may appear ·
  KPI-16 must be on it AND be a series · ≥3 cards must plot the DAILY grain and
  none may `GROUP BY month` · the tolerance is read off the mart, never typed ·
  `model_version` is visible somewhere (a spliced series averages two champions
  into invisibility).
- **`make board-cards` is gotcha #78 applied to Metabase.** `--verify` executes
  ONE card per dashboard — enough for the connection and the credentials, not
  enough for the board. The new reader runs the SQL a reviewer reads in the
  checked-in JSON straight at the one Postgres and **treats an empty card as a
  FAILURE**: **36 cards across 4 boards, 0 failures**. It is deliberately NOT
  wired into `verify-m1`, because widening a gate's behaviour late in a session
  is how a guard goes red for a correct system (gotcha #50).

## The M7 gate (M7-S5 leg 2) — the difference it asserts, and the hole it found
- **`make verify-m7` is 62 sub-checks in 7 sections, 5.328 s, and it RE-RUNS
  NOTHING** — seventh inheritance of M1's no-skip-flag rule. M7's evidence is
  15.7M raw rows ingested, 15.4M scored, a ~12 minute drift drill and a 1,618.4 s
  fit, but the stronger reason is new: **the ORDER OF WORK is part of the
  evidence.** The drift bars are legitimate because they were argued from 2019
  headroom BEFORE any 2020 month was compared, and a gate that recomputed the
  drift numbers would destroy the one property that makes them honest. It asks
  the live system exactly three questions — **one prediction, one PromQL query,
  one rules read** — pinned by test, and it may not push a metric (a gateway has
  no expiry, so anything the gate wrote would be read by a rule as a real job).
- **§2 is the §9/M7 "Show" leg and it is a DIFFERENCE, not a sentence.** The two
  failure signatures are built from their own records — statistical from the
  drift + ingest records, schema from the fixture records — and must differ in
  **all four** discriminating fields (exit code · rows written · report present ·
  drift metric present). The last is an absence, which a record cannot honestly
  claim about itself, so it is counted **where a landed month would have to
  appear** (`ingest_months ∪ scoring_months`). `rows_validated: 200000` in a
  refusal record means *rows read*, not *rows that passed* — the first draft
  believed the field name.
- **The order of work is checked on three clocks and one of them is git.**
  Headroom computed 04:14:49Z, first 2020 comparison 04:38:31Z; the prediction's
  ADD commit precedes the first 2020 drift record's by **640 s**; and the drill's
  embedded prediction is field-by-field equal to the committed file (a prediction
  can be written first and quietly edited into the record that judges it — the
  M6 gameday idiom, transplanted).
- **F-050, raised by the gate on its own first run: a pushgateway restart
  deletes every drift series, and A-10 cannot fire on an ABSENT one.** The live
  query returned **zero** series against three records saying three. Nothing had
  drifted — the gateway pod restarted after a host reboot. `time() - max by
  (month) (taxi_drift_last_run_timestamp_seconds) > 3456000` over no series **is
  no series**, so the staleness rule sits inactive and the board renders empty:
  gotcha **#78** one layer up, and the SLO doc's own "a pushed metric persists"
  argument blind to the board going away. **The gate asks the PAIR** — either the
  series are present, or the gateway restarted since the drill pushed them,
  checked on two clocks — so an absence nothing accounts for is still a FAIL,
  while a laptop reboot does not turn the milestone red (gotcha #50). Two costed
  options in the ledger; the recommendation is an `absent()` rule, whose honest
  cost is that it fires during ordinary development.
- **`verify-m6` had gone RED, and the cause was M7-S3 doing the right thing.**
  Its signal leg required the documented-absence list to be **non-empty** — true
  the day it was written, false the moment F-035 closed. Same leg read the
  renderer's sets with `ast.literal_eval` and silently got nothing once they
  became comprehensions: **a guard degrading into a guard about its own parser.**
  Both repaired to the property that holds at every state — import the sets,
  assert the AGREEMENT — **GREEN 63/63**. Gotcha #50, sixth time.
- **The red team plants F-045 itself.** One `volume_ratio` rewritten from a ratio
  of RATES to a ratio of TOTALS (`current_rows` over `reference_rows / 6` =
  0.4021 against 0.3913), derived from the record's own fields, wrong by one
  percentage point, and **still under the 0.50 bar** — so the alert still fires
  and nothing reads differently to a skim. **RED with 3 FAILs from THREE
  artifacts**: the anchor arithmetic, the drill record that watched the live
  gateway, and the memo a human reads. **59 sub-check lines still passed**, and
  the drill asserts the bar-daylight leg **must stay GREEN** — which is what
  separates a gate that fails on a WRONG number from one that fails on any edit.
- **Three needles in the gate's own test file matched WORDS, and all three were
  the gate quoting itself** (gotcha #99): `--push` in the advice line it PRINTS,
  `ingest_month` as a prefix of the `ingest_months` VIEW it reads, `retrain(`
  inside the sentence reporting what `ast` found. For the third no anchor helps —
  the sentence is legitimate — so the property changed: **the gate must never
  IMPORT the callable it inspects.**

## The drift surface, made trustworthy (M8-S1 leg 1) — one denominator, one deleted file, one volume, one new signal
- **A-9's volume ratio divides by CALENDAR days now, and the bar did not move
  (F-051).** The old denominator was `COUNT(DISTINCT observed date)`, so a day
  with no trips left the numerator **and the denominator together** and the ratio
  measured *how busy were the days that happened* — which RISES as a shutdown
  deepens. On the real COVID month, deleting the eight quietest days (a strictly
  worse world) walked it **0.3913 → 0.5143, SILENT**. `drift.calendar_days`
  (`calendar.monthrange`, the authority `verify-m7` §3 already trusts) is the
  denominator; `_observed_days` survives as a REPORTED diagnostic, so "every day
  was present" is readable off the record. **The three recorded ratios are
  byte-unchanged** (0.8336 · 0.8776 · 0.3913 — no diff line at all). This is
  implementation catching up to the calendar language §8.4 and the annotation
  already used (F-041's family), not a threshold change and not a PO fork.
- **The deliverable is the PROPERTY, and its load-bearing half is negative.**
  Four tests: a strictly worse collapse must lower the ratio at every step · a
  crossed bar may not be re-crossed upward · a 20-of-31-day extract reads as a
  collapse, not as health · **and the OLD denominator must still be
  non-monotonic**, pinned so the defect cannot return through an edit that
  "derives the days from the data" for tidiness. `make drift-monotonicity` re-runs
  REV's counterfactual **through the shipped functions** — the half
  `rev_rederive_m7.py` structurally could not do, since it deliberately does not
  import the module under review — and keeps the old column beside the new one as
  a CONTROL, failing if the old arithmetic stops reproducing the finding.
- **PSI was not deterministic and now is.** `_psi` summed an unordered set, so
  float non-associativity made the 17th digit a function of the process hash seed
  (observed live: `0.0015194096507573718` → `…72`). Nothing reads that digit — but
  the module argues for exact SQL counts over sampling on the grounds that a
  sampled number "changes between runs", and that argument cannot be made by a
  number that changes between runs. Sorted union; two consecutive runs are now
  identical apart from `computed_at`.
- **`configs/drift.yaml` is DELETED and the diagram that cited it is corrected
  (F-052).** It was read by nothing and both its numbers were wrong — reference
  `2019-08` (the *test* split, the thing `drift.py`'s docstring argues against)
  and a 0.5 *share* bar against A-8's live PSI ≥ 0.10 on ≥2 of 5. Not inert:
  `docs/m7_flow.html` rendered both under "Sources of truth". Both halves landed
  together — stamp, drift-check node, the Gate-2 diamond (now A-8's and A-9's real
  conditions), signature B's table (now carrying the MEASURED outcome), footer,
  with a dated note leaving visible what the page used to claim. **F-013's knob
  tuple is widened** with `reference_month`/`drift_share_threshold`/
  `psi_threshold`/`volume_ratio_threshold`: F-013 is a law about **bars**, not
  about the promotion gate, and a drift bar walked through five promotion names
  for a whole milestone.
- **The gateway is a stateful tenant now, and its ABSENCE is a page (F-050
  (a)+(b), proved together).** `make backup` first (`2026-08-21T05-00-56Z`, 6
  databases + 418 objects, 1.7 GiB). The PV plus
  `--persistence.file=/data/pushgateway.data --persistence.interval=10s`, all read
  live off the subchart (its `strategy.type` is ALREADY `Recreate`, which a
  node-local RWO volume needs — F-033 avoided by construction). **A mounted volume
  with no `--persistence.file` is decoration** — pushgateway keeps metrics in
  memory unless one names a file, and the chart mounts the volume either way; that
  is its own test. **A-11 `DriftMetricsAbsent`** (`absent(...)`, `for: 10m`,
  SLO-D4) is the other half, because **A-10 cannot fire on an absent series**:
  `time() - max by (month)(X)` over zero series is *zero series*, not a large
  number. A-10 carries a `blind_spot` annotation saying so at the rule.
- **Neither half is honest alone, and the recurrence measurement is what decided
  it**: the volume without the rule leaves nothing watching a real deletion; the
  rule without the volume pages on every laptop reboot and trains its reader to
  ignore it. **`make drift-persistence-drill` PASSED 16/16**, prediction committed
  first and pinned by a test: 48 samples survived a `kubectl delete pod` onto a
  **different pod object, ready in 13.12 s** (the same read returned 0 three times
  on an emptyDir); the deliberate wipe fired **A-11 at 625.1 s** against a 600 s
  sustain and reached **Alertmanager**, while **A-10 AND A-9 both stayed inactive
  through a total loss of the surface** — the negative predictions, and A-10's
  silence is A-11's whole reason to exist; the re-push cleared A-11 in **37.8 s**
  and A-9 returned for 2020-03, so the board ends carrying the truth.
- **F-046 closes on a sentence, and the sentence commits the program to
  something.** `docs/slo_serving.md` §8.1 now states the WINDOW's blindness beside
  PSI's — *a regime change confined to part of a month is invisible to SLO-D1 at
  monthly grain regardless of columns* — names the reliance that makes accepting
  it honest (A-9, monotonic since F-051 landed FIRST in the same story) and
  records the residual: **a shape change with NO volume change would be missed by
  both rules**. The daily window is named and deliberately NOT scheduled — it
  needs its own 2019 DAILY headroom leg, and choosing a window after seeing which
  window would have fired is walking a threshold by another route.
- **F-053, found by this story's own first command and closed in it: `make
  backup` was RUNNING `make restore-drill`.** The manifest heredoc's delimiter is
  unquoted (its body interpolates `$(human …)`) and the M6-S5 sentence named its
  target in backticks — command substitution, with `make`'s `Entering directory`
  chatter spliced mid-sentence into a lifeboat artifact. Dated by the artifacts:
  2026-08-19 clean, 2026-08-20 and 2026-08-21T04-53-42Z polluted. It never
  completed (the drill's record still has its 2026-08-19 mtime) — luck, not
  design, since `restore_rehearsal.py` creates and drops scratch databases in the
  ONE Postgres. **Gotcha #60's second occurrence, and the real finding is that
  the lesson had no test**; it has a repo-wide one now (every heredoc in
  `scripts/*.sh` + the Makefile), red-teamed RED on the exact two lines. The
  polluted manifest is KEPT as evidence beside its clean control.

## Where the scale lives (M8-S1 leg 2) — provenance ON the version, and a marker that is not a skip flag
- **F-048 CLOSED, both halves, in ONE image with one redeploy — and the ordering
  was the decision.** (c) alone would have left the deployed proof trigger red
  until (a) landed, which is why M7-S4 correctly declined to ship it by itself.
  **(c)**: `_search_scale` RAISES when the records DIRECTORY is invisible, naming
  `.dockerignore`, the finding and the fix — because *"no refit record names this
  run"* is a fact about the CHAMPION and *"I cannot see any records"* is a fact
  about the PROCESS, and inside a pod it is the second every time. The test asserts
  the two differ in KIND (one returns a reported no-op, one raises) and its visible
  arm points at a directory **the image also has**, so it makes the same assertion
  in a pod. **(a)**: three tags on the version through
  `registry.record_search_scale` — additive, idempotent BY VALUE, and **refusing a
  disagreeing rewrite** (provenance describes a fit that already happened; two
  answers is a defect somewhere and overwriting the older one destroys the evidence
  of which). AST-pinned to name no destructive verb and no alias verb: **a backfill
  that could move `@champion` would be a rollback wearing a provenance script's
  clothes.**
- **`NO_SEARCH` is a VALUE, not an absent tag, and that is the whole finding in one
  design decision.** "This champion had no sampled search" · "nobody ever recorded
  it" · "I cannot see the records" are now THREE answers where they used to be one
  sentence. Gotcha #94's shape in a provenance chain: a chain that degrades toward
  *nothing to do* hides its own breakage.
- **Who writes it: the refit at fit time, the promotion for every version, the
  backfill for the past.** `automl_refit.py` logs the divisor on the RUN (the one
  place that knows it while the run is being created); `run._promote` copies it onto
  the version **DERIVED from that run, never typed**, so a hand-configured fit
  records the honest no-op instead of leaving a hole; `make backfill-provenance`
  did versions 1 and 2 — **`2 version(s) changed; no alias was read or moved, no
  version was created, nothing was deleted`**, and a second run `0 version(s)
  changed`. Every number in that script is derived (run id -> `refit-*.json` ->
  study -> `sniper-*.json`); a constant there would be F-048 one layer along.
  The host then resolved **factor 6.6667 · `min_data_in_leaf` 1293 -> 8620 · round
  cap 2400** FROM THE REGISTRY — M7-S4's numbers, from a different authority.
- **And a POD did too, which is the row's own closing condition.** Proof run
  `rdc1f3841bd6455e6`, fired by `retrain-schedule-proof` at 06:31:54Z on task
  version `cfe8dc01a115…`: **`rescale_factor` 6.666666969783633 · `round_cap`
  2400 · `decision PLAN_ONLY promoted=false`**. The same reader had captured the
  BEFORE — **seven consecutive firings** of the same trigger, 20 minutes apart, on
  the same champion, every one `null`/500 — and both sides sit in ONE record
  (`automation/runs/m8-provenance/proof.json`, `earlier_runs_seen`), so the
  contrast is checkable rather than asserted. Incidental but worth knowing: the
  06:11:54Z firing still ran the OLD version *after the redeploy had returned* —
  **a trigger fires the version registered when it fires**, and a redeploy takes
  effect at the next tick.
- **F-047 CLOSED: `make image-smoke` GREEN 10/10** on freshly built
  `taxi-mlops-pipeline:5edf9fd`, in-image suite **928 passed · 19 skipped · 22
  deselected**. **The marker set was MEASURED, not enumerated**: the union of what
  fails with `automation/runs/` hidden on the host (18) and what failed inside the
  pre-story image (12) — two measurements because each sees what the other cannot
  (the host keeps its git index; the image has no `.git`). A list written from the
  ledger row would have been twelve; the answer is **21**.
- **A marker is one afternoon from being the skip flag M1 refused, so the tests
  that hold the line came first** (`tests/unit/test_record_marker.py`, by AST):
  deselected in exactly ONE place · **`addopts` may not deselect it** (that would
  hide these from every host run and from CI) · no other `scripts/*.sh` may · and
  nothing is marked that does not need it. **The guard caught its own author's new
  test on its first run**, and its first draft had missed four real tests because a
  record path is spelled two ways in this suite (`REPO / "automation/runs/x"` and
  `REPO / "automation" / "runs"`) — gotcha #46's family, and no substring match
  sees it.
- **The same command found the SECOND instance of the finding it was closing.**
  `test_detach_exit_codes` has been RED in-image since the day it landed, because
  the image ships no `make` — same shape, unseen for the same reason (nothing runs
  `image-smoke`). It carries a `skipif` on the binary now, the idiom this suite
  already uses for `ss`, `git` and `docker`. **F-054 (new, OPEN)**: twelve tests
  still guard record reads with `skipif(not RECORD.exists())`, which on the HOST
  passes silently when the drill was never run — F-029 made the opposite argument at
  M5-S1. The guard accepts the older form EXPLICITLY and argues against it, so the
  inconsistency is visible rather than blessed by silence.
- **One rebuild was spent on a `-dirty` tag**: `make retrain --plan-only` writes a
  tracked record, so running the provenance check before a build makes the next
  image `-dirty` — and a `-dirty` image must not back a verdict. Anything that
  writes into a tracked directory is a build input whether or not it feels like one.

## Feast, quarantined (M8-S2) — the wall measured, and a catalog that records its losers
- **There is no `uv add feast` in this repository and never will be.** feast
  0.66.0 declares `pandas<3,>=1.4.3` against this project's **3.0.5** — measured
  at the M8 draft and re-measured by the probe — so the isolated interpreter
  `.venv-feast` IS the design (M8 law 4, gotcha #16's quarantine, the
  full-`mlflow` shape of #36). **The two sides differ on exactly ONE package**:
  numpy 2.5.2, pyarrow 25.0.1 and CPython 3.12.14 are identical on both, which
  is what M8-S3's parquet-seam argument gets to start from (M5-S3's mlserver
  parity measured 0.000e+00 for exactly that reason). The quarantine rebuilds
  from **64 exact pins** in `infra/feast/requirements-feast.txt` with
  `--no-deps` — proved from scratch this session by deleting the venv — because
  a resolver consulted at install time can legally answer differently from the
  one that was reviewed. **The exit invariant is in the SCRIPT, not the
  write-up**: `uv.lock`'s sha256 before and after, and a difference aborts.
- **Parquet is the only thing that crosses, and both directions are AST-pinned.**
  `scripts/feast_sources.py` imports `taxi_mlops` and never `feast`;
  `infra/feast/feature_repo/definitions.py` imports `feast` and never
  `taxi_mlops`. One import across that line is how a quarantine stops being one.
- **Four views over artifacts this program already had, read-only** (M8 law 2):
  `zone_static` (263 rows — **in-champion**, the input to all nine g2 geometry
  features, +0.63% / KPI-10 +0.200 at full data) · `calendar_day_flags` (4,383
  days 2019..2030 — **in-champion**, g1, +1.77% / +0.569) · `od_window_stats`
  (248,169) and `pu_hour_window_stats` (35,589) — **CATALOG-ONLY**. Sources land
  in `data/feast/`, gitignored and NOT DVC-tracked on `data/predictions/`'s terms
  exactly. All four settled pins read `up to date` at exit; `uv.lock` is
  byte-identical to the `m7-closed` tag.
- **The catalog records what each entry is WORTH, including the entries worth
  nothing.** g5 — point-in-time aggregates, the strongest family in every source
  `docs/feature_dossier.md` harvested — is in the store and **not** in the
  champion, at **−1.63% relative val MAE / KPI-10 −0.686**, with the leakage red
  team's **+1.56% on the month it saw, −3.83% on the untouched one** beside it.
  **And that number is labelled a 15%-SAMPLE number** (gotcha #15): a dropped
  group is never refitted at full data, so no full-data figure for g5 exists and
  the page does not invent one. A catalog that lists only winners cannot be used
  to argue against repeating an experiment.
- **The verdicts are checked against the APPLIED REGISTRY, never against
  `definitions.py`.** They live as `tags` on the Feast objects and as prose in
  `docs/feast_catalog.md`; `tests/unit/test_feast_repo.py` compares the page with
  `automation/runs/m8-feast/registry.json`, which was read back off the store —
  the `deploy_serving.sh` idiom (read KServe's mode off the live ConfigMap)
  applied to a feature repo. It earned itself on its first run, going red because
  the registry still held tags edited minutes earlier.
- **F-055 (new, closed the same session): `feast plan` can NEVER say "no
  changes".** Feast re-stamps a DataSource's `meta` at import, so all four views
  report as "Updated" on a repo where nothing moved — **gotcha #78 in a new
  place, and the worse direction**, because an always-noisy reading looks like
  diligence where an empty panel at least looks empty. `make feast-plan-check`
  asserts the statement that CAN be false: every reported difference is confined
  to `("seconds:", "nanos:")` — an allowlist a test pins, since widening it is
  how a real diff would hide. **Red-teamed live**: one field renamed
  (`centroid_lat` → `centroid_lat_TAMPERED`) made it FAIL naming `zone_static`
  **while the other three still read clock-only** — a drill where everything goes
  red proves the checker noticed something, not what.
- **The stamps are END-OF-WINDOW and DERIVED, which sets up S3's proof rather
  than leaving it to be discovered.** A window ending with month *m* is knowable
  at the first instant of *m+1*, so `aggregates.fit`'s six cutoff tables become
  six stamps — **2019-02-01 … 2019-07-01** — under which Feast's point-in-time
  join hands each row the same table `aggregates.transform` hands it (a 2019-04
  row gets the 2019-01..03 window; val and test get the full one). **2019-01 has
  no rows at all**: it has no history, and a lookup returning null IS the NaN the
  model was fitted on. One corroboration nobody arranged — the full window's OD
  table holds **46,938** rows, the exact count M3-S1's
  `baseline-group-median-od-fallback` reported as backoff cells over the same six
  months, from entirely different code.
- **Nothing was fitted, no alias moved, no version was minted.** `@champion` is
  version 2 / `feature_set v2` at exit, `make verify-m7` **GREEN 62/62**, host
  suite **986 passed**. `airport_regime_flag` is recorded as a CANDIDATE with the
  three measurements that motivate it (1.90× · 1.91× · 1.86–2.35×), which is
  `docs/error_memo_m2.md` §7 row 2's named reader — catalog only.

## Point-in-time correctness, measured (M8-S3) — an exact seam, and the leak in one column
- **`max |ours − store| = 0.000e+00` across 14 columns and 88 declared rows, against
  a bar of EXACT** — and the bar was argued from the dtype path and COMMITTED
  (`27ea9a1`) before the comparison ran, which is M8 law 4's ordering made checkable
  from git rather than asserted (M7-S3's headroom precedent). The argument is one
  sentence: **nothing on the store's side of the wall performs arithmetic** —
  `make feast-sources` computes every number on THIS side through the champion's own
  functions and Feast's whole job is to remember it and pick the right row, so a
  retrieval is a copy, a lossless `float32 -> float64` widening, or parquet's typed
  encoding. A float bar would have been a hedge against a hazard that does not exist
  here; a *nonzero* result would have been a finding to investigate (which side
  rounded), never a bar to widen.
- **`one missing` is ZERO on every column, and that is the load-bearing number** —
  stronger than the deltas. Every value the store declines to answer is one the
  feature path declines too. `NaN != NaN`, so the comparison counts both-missing as
  agreement and **one-missing as a MISMATCH**; a check that dropped nulls would have
  printed the same `0.000e+00` while being blind to the ~1% of rows carrying no
  geometry — the class F-030 was found on.
- **The no-geometry rows are ASSERTED two-sidedly, never compared.** For zones
  264/265 the store has no row (DR-04 condition 1) while `zones.load_zone_table()`
  answers borough `"Unknown"` / airport `False` — the same fact in two vocabularies.
  So: the store must return **null** (11 PU rows, 18 DO rows, 0 exceptions) AND our
  path must report `has_geometry = 0` (20 rows). Manufacturing a zeroed row in the
  store to make a column-wise comparison succeed would put a plausible place at the
  equator into a feature store.
- **The PIT proof is two-sided, and the second half is what makes the first mean
  anything.** Same store, same call, ONE column different — the honest pass sends
  each row its own timestamp, the naive pass overwrites every timestamp with the
  instant the last window closed. Honest vs naive differ on **61 of 76** OD rows
  (max **8.2000** min), 53/69 speeds, 62/78 rates; **the naive answer IS our own
  full-window table, 0 mismatches over 88 rows**; and the honest answer reconciles
  with `aggregates.transform` at **0.000e+00**. Without that last clause a
  difference would only prove two joins disagree.
- **The purest form of the leak is 10 rows the honest join must tell NOTHING.**
  2019-01 is the first train month and has no history; `AggregateTables.empty()`
  serves it NaN and the naive join hands it a number computed from June.
- **All six month-boundary pairs were served DIFFERENT windows across 120 seconds**,
  and the walk reads like the design doc: `(no row) -> 2019-01 -> …,02 -> …,03 ->
  …,04 -> …,05 -> full`, od_median 161->237 **NaN -> 8.1833 -> 8.2667 -> 8.1667 ->
  8.1667 -> 8.2500 -> 8.3500**, with **the naive column constant at 8.3500 down the
  whole table** — which is exactly what makes a leaky feature look stable and good.
  Two rows deserve slow reading: the FIRST (two minutes apart, one gets NaN and the
  other January, because the window became knowable at 00:00 and not one second
  earlier) and the FOURTH (**the window changed while the value did not** — an
  honest join is about what a row was ENTITLED to know, so a check written against
  "the number moved" would have called that pair a failure).
- **F-056 (new, closed the same session): `get_historical_features` returns fewer
  rows than it was asked for, for two reasons a left join cannot tell apart.** The
  first run answered **77 of 88** on the time-varying views. Cause 1: duplicate
  `(entity keys, event_timestamp)` — one drawn row shares a pickup second AND a zone
  with another, and the store answered it *once*, so aligning on `row_id` would have
  manufactured a mismatch against a perfectly good value. Cause 2: **no source row
  at or before the timestamp** (all ten others are 2019-01; the earliest
  `od_window_stats` stamp is 2019-02-01) — the value is correctly nothing, but the
  row is DROPPED rather than nulled. Both legitimate, neither announced, and after
  any `how="left"` merge a NaN meaning *answered elsewhere*, one meaning *correctly
  nothing* and one meaning *lost* render identically (gotcha #78's disease again).
  So the script **asserts no count**: it CLASSIFIES every unanswered row, recovers
  the duplicates by joining on the keys the store actually keyed on, reads the
  earliest source stamp off the published parquet rather than typing it, and
  **`unexplained` is a FAIL naming row ids**. Observed: `duplicate-key 1 ·
  before-first-source-row 10 · UNEXPLAINED 0`.
- **The truth is RE-FITTED from `data/processed/`, never rebuilt from the parquet
  the store reads** — 43,987,422 rows through `aggregates.fit(point_in_time=True)`.
  Reconstructing it from the artifact under test would compare the store against
  itself and pass for any join at all, including no join.
- **The row set is declared and committed, 88 rows, each naming why**
  (`infra/feast/retrieval_rows.csv`): 16 **imported from `parity.HAZARDS`** so the
  wire seam and the store seam are measured against ONE row set · 12 straddling
  every train-month boundary by 120 s · 60 drawn across M6-S3's four strata. The
  draw **refuses to come back short**, because the first version used
  `USING SAMPLE reservoir(15 ROWS) REPEATABLE` after a `WHERE` and returned **ZERO
  airport rows out of a stratum holding 3,237,471** — DuckDB samples the SCAN, not
  the filtered set, and a short draw in a committed artifact is indistinguishable
  from a stratum nobody covered.
- **Nothing was fitted for a model, no alias moved, nothing materialized.**
  `@champion` version **2** / `feature_set v2`, versions `['1','2']` — no version 3.
  `make verify-m7` **GREEN 62/62**, host suite **1008 passed** (22 new), `uv.lock`
  byte-identical to the `m7-closed` tag, all four settled pins `up to date`,
  `make feast-plan-check` still `4 clock-only, 0 substantive`.
- **Two tests went red for matching WORDS and both were the file quoting itself**
  (gotcha #99, second time in this repo): `"materialize"` matched the comparer's own
  docstring promising it does not materialize, and `"USING SAMPLE"` matched the note
  explaining why it is gone. Both are asked of the **AST** now — the single
  subprocess invocation's argv, and the SQL `_drawn_rows` actually builds.

## The online store, and the 100-pair parity (M8-S4 leg 1) — a lossless projection, and the collapse that became the normal case
- **The store is an in-cluster Redis and the constraint that decided it is
  TWO-SIDED reachability** (ADR-012): the materializer writes it from the HOST
  inside the quarantine (there is no Feast image and building one would move the
  wall into the cluster), the leg-2 transformer reads it from a POD. **Feast's
  default sqlite file satisfies neither, and fails in the dangerous direction** —
  `feast materialize` writes a local file, reports success, and every in-cluster
  lookup returns null. So the address cannot be a committed constant: it is
  `${FEAST_REDIS_CONNECTION}`, expanded by Feast's own `os.path.expandvars`, with
  **no default** — an unset variable fails loudly naming itself, where a default
  would connect to something wrong (F-048's rule). The OFFLINE readers never open
  a connection, so the unexpanded literal is harmless to them. **1 of the
  3-attempt wall spent; it worked first time.**
- **Two settings whose failure mode is silent, both read back off the SERVER.**
  `maxmemory-policy noeviction` is a CORRECTNESS setting, not tuning: an evicting
  feature store drops the key the next request asks for, the lookup returns null,
  the transformer builds a NaN and the model quotes a confident wrong number with
  nothing red anywhere — with `noeviction` the materialization FAILS instead
  (57,688 keys / 14.32 MiB against a 512mb cap, so the margin is a number). And
  `strategy: Recreate`, because a node-local RWO volume plus RollingUpdate is
  F-033's deadlock — avoided by construction rather than discovered.
- **The state class is recorded in BOTH directions, because they are different
  questions.** Materialized features are REGENERABLE (7 s), so **ledger row yes,
  backup obligation no** — `make backup` enumerates from the server and will not
  see Redis, which is correct and is written down so nobody reads the absence as
  an omission. A PVC anyway: backup is about losing the machine, the volume is
  about losing the POD, and F-050 measured that event twice in fourteen hours on
  this machine. The residual is named, not netted out: **there is still no alert
  on an empty online store**, and it belongs to the story that puts a reader in
  front of it.
- **`max |online − offline| = 0.000e+00` across 16 columns and 100 declared
  pairs, bar EXACT — and `one missing` is ZERO on every one.** The bar was
  **re-argued for the new path and committed before the comparison ran** (commit
  `3777e71`): protobuf `double` is fixed-width, bool/string have no numeric path,
  the hop moves bytes, the entity-key serialization is pinned at version 3, and
  `materialize` SELECTS rather than aggregates. Inheriting M8-S3's sentence would
  have been a hedge — its argument was about parquet.
- **The anchor is what stops this being two Feast reads agreeing with each
  other.** The seven STATIC columns are additionally compared against
  `taxi_mlops.features.zones` and `.calendar` — the functions the champion's own
  matrix is built from, and **every stored feature the champion actually eats**.
  The two time-varying views are anchored by an INHERITED measurement, cited and
  not re-run (M8-S3: the full-window retrieval == our `aggregates.fit` table, 0
  mismatches over 88 rows); re-fitting 43.9M rows to restate it would cost three
  minutes to learn nothing.
- **An online store cannot serve a point-in-time feature, and that is the honest
  limit of the category rather than a defect of this one.** `materialize` keeps
  the latest row per key, so the time-varying views serve the FULL window to
  every request — which is exactly M8-S3's *naive* column. The offline half is
  therefore retrieved at an instant AFTER the last window closed; comparing
  against a per-row point-in-time answer would report a correctly-working store
  as a mismatch (gotcha #50). It costs nothing here because all twelve stored
  features the champion eats are static.
- **F-056 stopped being a curiosity and became the majority case** (gotcha #103).
  Hold every timestamp constant and the join's duplicate-collapse is no longer an
  edge: `get_historical_features` answered **34 rows of 100** on one view (37, 67,
  73 on the others) while `get_online_features` answered **100 of 100 on every
  one**. Nothing was wrong — a lookup returns one row per request and a join one
  row per distinct key — but aligning by POSITION would have compared the store
  against a shuffled copy of itself, and aligning by `row_id` alone would have
  read two thirds of the table as nulls. Aligned on the keys the store actually
  keyed on; shortfall CLASSIFIED, `UNEXPLAINED 0`, and M8-S3's second cause
  correctly EMPTY (a retrieval after the last window cannot predate its sources).
- **The declared row 92's first design was refused BY THE DATA, and the refusal
  is the better instrument.** The intent was a key whose newest source row
  predates the full window; no such key exists, because the point-in-time windows
  are **cumulative**, making the full window's key set a superset of every
  earlier one's. Replaced rather than approximated: it is now the OD pair whose
  median moves most across its windows (**169 -> 191, 80.15 min**) — the row where
  a wrong-stamp materialization shows up by the largest margin.
- **The table can go RED and was watched doing it.** The drill copies one OD
  pair's REAL serialized bytes onto another's key (the protobuf parses, the dtype
  is right, nothing logs anything — a drill that planted garbage would prove the
  parser works): **exit 1 at 8.727e+01 naming `od_window.od_median_duration_min`,
  26 sub-check lines still passing, sha256-identical restore, GREEN again, clean
  tree.** Both of its parity runs use `--no-write`, pinned by a test — a drill
  that rewrote the committed table with its own tampered verdict would be
  planting evidence rather than looking for it.
- **End state is exactly M8-S3's**: `@champion` **2** / `feature_set v2`,
  versions `['1','2']`, `make verify-m5` GREEN, `make verify-m7` **GREEN 62/62**,
  host suite **1041 passed**, `uv.lock` byte-identical to `m7-closed`, all four
  settled pins `up to date`. **The transformer is NOT built** — the kickoff's own
  declared safe stopping point, and leg 2 inherits an unspent 3-attempt wall.

## The wall with a door (M8-S4 leg 2) — the feature server, and three things that look alike in a schema
- **Shape (i) landed first try and 1 of the 3-attempt wall is spent.** The
  kickoff ordered (i) a Feast feature server in its own quarantined pod ->
  (ii) a thin direct store read -> (iii) Feast off the request path. (i) is the
  only one under which the wall stays a WALL: the transformer will run OUR image
  (pandas 3.0.5) and feast 0.66.0 pins `pandas<3`, so the two worlds share **one
  JSON document over a ClusterIP Service** and nothing else — `uv.lock` is
  byte-identical to `m7-closed` at exit, exactly as at every other M8 story's.
  **(ii) was refused with a reason, not skipped**: a "thin read" has to
  re-implement Feast's entity-key serialization, field naming and value encoding
  on our side of the wall, and getting any of them subtly wrong returns SOMEBODY
  ELSE'S ROW — a confident wrong number with nothing red anywhere. 203 MB of pod
  is cheap against owning a private copy of a vendor's encoding.
- **It was PROBED before it was built** (`make feast-serve-probe`, ~30 s against
  a build-and-load): `feast serve` on the HOST, in the quarantine that already
  existed, against the real in-cluster Redis. It answered zone 132 at JFK's
  centroid and zone 264 `null`. The M4-S4 `DRILL_STAGE=ingest` idiom, and it paid
  the usual way — the first defect the build then hit was a **missing execute
  bit** (`COPY` preserves the source's 0644; containerd reports
  `exec: permission denied`, which reads like a missing binary or a broken PATH).
- **The image carries no registry and no store address, and both absences are
  the point.** `feast apply` runs in the ENTRYPOINT at every start, so the pod's
  registry is a function of the image's git content rather than of whatever the
  host had applied the day it was built — a baked registry would be F-013's
  second home for a thing `definitions.py` owns. `${FEAST_REDIS_CONNECTION}` has
  **no default** (ADR-012/F-048's rule) and the entrypoint refuses before
  applying. It is built `--no-deps` from `infra/feast/requirements-feast.txt` —
  the SAME pin file `scripts/feast_quarantine.sh` uses, so there is one pin file
  and no twin. **STATELESS**: no volume, no backup obligation, losing the pod
  costs one restart.
- **The container mirrors the host's directory DEPTH rather than editing
  `definitions.py`**, which resolves its sources with `parents[3]`. Flattening it
  would have needed an edited file and therefore two definitions of where the
  offline sources live.
- **`max |ours − server| = 0.000e+00` across 6 columns and 108 comparisons, bar
  EXACT, `one missing` ZERO** — and the bar was argued for THIS path (JSON's
  number grammar carries a float64 losslessly because every encoder in this stack
  emits Python's shortest-round-trip repr; nothing on the server's side does
  arithmetic) and **committed at `91ab8a6`, before any record existed**.
  Inheriting M8-S3's parquet sentence or leg 1's protobuf one would have been a
  hedge wearing an argument's clothes. The anchor is `taxi_mlops.features` — the
  champion's OWN lookup — never the parquet the store was materialized from,
  which would be two Feast reads agreeing with each other.
- **F-059: a feature store is a good home for a per-entity MEASUREMENT and a bad
  home for anything a program COMPUTES — and the three are indistinguishable in a
  schema.** `borough` is an **encoding**: the code the champion eats is assigned
  by first-appearance order across the WHOLE lookup table, so it is a property of
  the table and not of the zone, and a transformer that fetched two zones and
  numbered what came back would produce a silent TOTAL category re-map with every
  individual value correct. `is_airport` is a **constant and a total function**:
  three integers in code, answering for every id including the non-places, which
  the store has no row for — so sourcing it from the store turns "not an airport"
  into "no answer" for exactly the ~1% of rows that already carry no geometry
  (F-030's class). A centroid is neither. **Leg 3 sources the centroids and the
  calendar flags from Feast and takes the borough dictionary and the airport
  constant from the committed tables**; `ZONE_FEATURES` excludes `borough` and a
  test asserts it.
- **The parity's first run went RED and the repair was not a wider bar.** It read
  `is_airport` ours=`False` vs store=`missing` on 264/265 while every numeric
  column sat at 0.000e+00 — a comparison holding a TOTAL function against a
  PARTIAL one. Repaired with the shape M8-S3 and leg 1 had already established:
  **partition the entities, assert the partition two-sidedly in BOTH directions**
  (a store declining a real zone is a missing feature; a store answering for a
  non-place is inventing a location), then compare columns only where both sides
  claim an answer. Observed: `declines EXACTLY [264, 265]`.
- **Worth knowing before writing any client: Feast's response does NOT preserve
  the request's column order.** Asked for `centroid_lat, centroid_lon,
  is_airport`, answered `zone_id, centroid_lat, is_airport, centroid_lon`. Pair
  by `metadata.feature_names`. This is gotcha #73's positional-vs-named lesson on
  a new wire, and a client zipping by position would send individually-valid
  values under each other's names — arm A of `make parity-redteam`, self-inflicted.
  The join key is `date_key` (`%Y-%m-%d`) and a WRONG key is not a soft failure:
  Feast answers **HTTP 500 with `Provided join_key_values: []`**, discarding an
  unrecognised key rather than complaining, so a plausible-looking name compares
  against nothing.
- **F-058, found by the boot ritual before the story started: a `FixedRate` Flyte
  trigger BACK-FILLS every window it missed while the control plane was down.**
  104 pods in `flyte`, **96 Pending**, all created in one 17-second burst two
  minutes after the binary restarted at host boot — ~2 days of missed
  `retrain-schedule-proof` firings replayed at once. They were unschedulable in a
  self-limiting way (`0/3 nodes … Insufficient memory` / PV node affinity) only
  because the retrain mounts the RWO `taxi-data` PVC and they queued behind one
  volume on one node — **luck, not design**. Deactivated with a one-command undo
  (`flyte update trigger … --deactivate`), read back off the control plane and
  never off the file submitted; the backlog drained itself (79 Completed in a
  minute) and was not aborted, because each firing is `plan_only`, mints no MLflow
  run and moves no alias. **The CODE is unchanged**, so `verify-m7`'s trigger leg
  — which reads the declarations with `ast` and never asks the server about
  activation — stayed GREEN, and `make retrain-schedule` re-activates it.
- **The transformer is NOT built** — the cut is stated in `docs/feast_server_m8.md`
  §6. Leg 3 inherits a stateless server at
  `feast-server.feast.svc.cluster.local:6566`, **2 of the 3-attempt wall unspent**,
  F-059 as a design input rather than a discovery, and no `lookups` seam in
  `quote_time.build_features` (it is not written). The residual leg 1 named is
  still open and still belongs to the story that puts a reader in front of the
  store: **there is no alert on an empty or stale online store.**

## The boundary moves (M8-S4 leg 3) — a raw request in a pod, and the number that did not change
- **`max |champion − transformer| = 0.000e+00` minutes across all 16 declared
  hazards, bar EXACT** — and the bar is *tighter* than M5-S3's 1e-6, argued in
  `docs/transformer_m8.md` §3 and **committed at `79aedb4` before any record
  existed**. A tighter bar needs an argument as much as a wider one does, and this
  one rests on a MEASURED premise rather than a plausible one: `make
  transformer-probe` had already shown the store-backed matrix bit-identical to
  the committed one, on the host, before the sentence was written. The remaining
  three differences cannot move a bit — a second mlserver on the same image and
  the same champion bytes, one extra in-cluster JSON hop through the SAME
  `client.v2_payload`, and reference data whose projection leg 2 measured exact.
- **The rows are worth reading, not just the total.** `no-geometry-both` (zones
  264/265, which the store has no row for and the committed table holds NaN for)
  produced NaN on both sides through the same named fallback and answered
  9.655549 twice; `federal-holiday` is the 39.001937 every record in this repo
  already carries, now produced by a pod from four raw fields.
- **What crosses the wall is F-059 as a TYPE.** `features.lookups.Lookups` has
  exactly two fields — `geometry_table` and `calendar` — so there is nowhere to
  put a fetched borough code or airport flag. The borough branches call `zones`
  directly and unconditionally, the store-backed `ZoneTable` is built with the
  COMMITTED borough arrays as defence in depth, and `feature_store.ZONE_FEATURES`
  asks for `centroid_lat`/`centroid_lon` and nothing else. The guard asks the
  **AST**, never the behaviour: a store whose values happened to agree would make
  a behavioural test pass for a design that is wrong, and the failure it hides —
  a total category re-map with every value individually correct — is invisible in
  every individual value.
- **`Lookups.sources` reports all four groups INCLUDING the two that did not
  cross**, and the transformer returns it as the `X-Taxi-Lookups` response header.
  Without it a parity of 0.000e+00 measured against a pod that silently fell back
  to its committed CSVs would look exactly like this one — ADR-012's own named
  failure mode, one layer along. Both the accept and the parity assert it on the
  same response they read the number from.
- **The transformer is stdlib**: `http.server.ThreadingHTTPServer`, `urllib`,
  `json`. No FastAPI, no uvicorn, no KServe SDK — three packages into a pinned
  numeric stack to serve one POST route at 4 req/s is what gotcha #36 is the
  record of not risking. **`uv.lock` is byte-identical to `m7-closed`** at exit,
  as at every other M8 story's. `encode_raw` and `decode_raw` live in ONE module
  so the client and the server cannot be twins.
- **It refuses in three distinguishable classes, and the distinction is the
  point.** A store that cannot be reached is **503** (ours, retryable); a date the
  store has no calendar row for is **422** — F-019's guarantee is a property of
  the DEPLOYMENT, not of the CSV, so it had to survive the reference data moving
  into a store; a body naming an input the schema does not know is **422 and
  named**, because ignoring it would quote every row at a default nobody asked
  for. Collapsing 503 into 422 would make a dependency outage look like a
  malformed quote in every panel that splits 4xx from 5xx.
- **The champion's own wire is untouched and the proof is a POD UID.** Teardown
  removed exactly the transformer's isvc and its five generated objects while the
  champion's Deployment/Service/Ingress stayed at 4d6h and its predictor pod kept
  uid `9b1f1b03-7dfe-458f…`, still answering 39.0019. A list of surviving object
  NAMES would not have distinguished "untouched" from "recreated". Then
  re-deployed and left up on purpose — M8-S5's gate inherits it live (the M6-S3
  shadow precedent, both halves).
- **p95: quote the p50, not the p95.** M5-S4's shape exactly (4 req/s, 60 s,
  concurrency 8, hazards, open loop), both arms back to back in one invocation so
  the champion is a CONTROL measured in the same minutes. **p50 31.1 -> 49.3
  (+18.1 ms), p95 113.1 -> 118.1 (+5.0), 240/240 ok on each arm, zero errors,
  4.01 req/s achieved on both.** But the p95 DELTA was **+23.0 ms** in a run eight
  minutes earlier while p50 held at +16.8 — that tail is host contention on a
  laptop, the reading M6-S2 already refused to take credit for once. Both records
  are tracked so the claim is checkable, and **the reportable cost of the moved
  boundary is ~18 ms at p50**.
- **The prediction was pessimistic and the word was `cold`** (gotcha #107).
  M5-S4 priced the feature build at ~30 ms for one row; the measured move is ~18
  ms and it buys the build PLUS two HTTP round trips to the feature server PLUS a
  second in-cluster hop. That 30 ms paid module import and the `lru_cache` fill on
  `load_zone_table`/`load_calendar`; a warm pod pays neither and the store path
  never reads those CSVs.
- **F-060, and it is a defect in a CHECK I write constantly.** The accept asserts
  that the CHAMPION'S model name 404s on the transformer's host — the negative
  half, without which a number from that service could have come from either
  boundary. Its first run PASSED that while failing every other check, because
  nginx had not loaded KServe's generated Ingress and the host was 404ing
  EVERYTHING (**F-037's shape on a brand-new isvc, where there is no predecessor
  to be satisfied by — gotcha #106**). A 404 because nothing is routed and a 404
  because the name is wrong are the same bytes. Repaired two ways and neither is a
  looser bar: the negative check is now conditional on the positive one, and the
  deploy gained a THIRD wait leg that asks the ROUTE under the Host header the
  next step will send. **Gotcha #105: where the artifact IS an absence, prove
  first that presence was possible.**
- **The F-026 guard fired on this story's own commit for a file the pod cannot
  run** (`serving/load.py` gained a `bodies` parameter, client code) — and the
  image was rebuilt rather than the guard narrowed, M7-S4's precedent, second
  occurrence.
- Exit state: `@champion` **2** / `feature_set v2`, versions `['1','2']` — **no
  version 3** · `make verify-m5` GREEN · `make verify-m7` **GREEN 62/62** · host
  suite **1091 passed** · ruff clean · `uv.lock` byte-identical to `m7-closed` ·
  all four settled DVC pins `up to date`. **The residual is still open and now has
  a third consumer: there is no alert on an empty or stale online store**, and this
  leg is the first to put rider-shaped traffic behind it.

## The side-by-side and the M8 gate (M8-S5) — a survey allowed to disagree with us, and the count the milestone rests on
- **Three Feast-on-taxi implementations exist publicly and all three were read
  live** (`docs/feast_side_by_side.md`, harvest 2026-08-23 through `gh api` +
  `curl` — F-001 stands). The population size IS the first finding: a GitHub API
  search for Feast applied to this exact problem returns **three** substantive
  repositories at 0★ each, so a SURPASS row means *none of these three*, said in
  each row. Every row cites the file it read, and **every claim about what a repo
  does NOT do rests on a recursive tree listing** rather than a skim.
- **12 rows: 3 ADOPT · 4 DIFFER · 5 SURPASS.** The ADOPTs are the ones that cost
  something to write. **F's `FeatureService`** is a registered contract naming the
  feature list once, read by BOTH `get_historical_features` and
  `get_online_features`; ours is `ZONE_FEATURES`, a Python constant on one side of
  a wall — a real gap, routed as **R-1** with its honest reason for not landing
  here (applying one mutates the registry three artifacts are pinned against and
  would need the server redeployed and M8-S4's three parity records re-measured).
  **F REFUSES a request whose online features are missing** (`HTTP 404`, entity
  named) — the principle is right and we say so in three documents, but a blanket
  copy would be wrong here because zones **264/265** legitimately have no row and
  `null` IS their correct answer; what it names is the residual **R-2**, still
  open. **F's 7-step origin-labelled trace** would have shortened three of M8-S4's
  debugging sessions.
- **The strongest DIFFER is that the wall is our problem and nobody else's.** F,
  G and H each hold Feast and their modelling code in ONE environment, and can,
  because none of them pinned pandas 3. Said plainly in the page: **if this
  project had not pinned pandas 3, F's single environment would be the better
  design and we would have taken it.**
- **What none of the three does, as properties**: an assertion that the
  point-in-time join is point-in-time correct (F performs it correctly; nothing
  checks that it stays so — F ships no test file, G's only one is Feast's
  unmodified `feast init` scaffold operating on `driver_id: 1001`, H's is an API
  health smoke) · a comparison of the online store against the offline value · a
  catalog that records which features LOST · a generated registry whose agreement
  with git is CHECKED · a typed refusal of quote-time-unknowable columns (G's view
  is keyed on `trip_id` and its schema carries `fare_amount`; a PIT join keyed on
  the prediction's own unique id can only return that trip's own row).
- **`make verify-m8` is 51 sub-checks in 7 sections and it RE-RUNS NOTHING** —
  eighth inheritance of M1's no-skip-flag rule, and here re-running would mean a
  ~7-minute image build that *changes the artifact under test* (gotcha #66). It
  asks the live system **exactly FIVE questions** — one prediction through the
  champion's wire, one through the transformer's, one feature-server lookup, one
  `DBSIZE`, one PromQL query — **and the count is pinned by its own test**,
  because a gate whose live footprint can grow quietly is one that will eventually
  re-run what it exists to read.
- **Law 4 is checked from GIT, four times.** A document cannot honestly testify
  that it was written before the measurement it judges, so the gate compares the
  commit that ADDED each bar's document with the commit that ADDED its record:
  678 s · 356 s · 320 s · 546 s, all four the right way round. The bar itself is
  PARSED out of the prose that argues it and typed nowhere.
- **The gate asks whether the online store holds anything**, which no predecessor
  needed to. An all-null store yields an all-NaN geometry table and a confident
  quote, and **no client can refuse that, because `null` is also the correct
  answer for zones 264/265** — gotcha #78 with the panel removed. 57,688 keys,
  read off the server, against the count the materialization recorded.
- **`one missing` and `both missing` are this milestone's thesis, so they got
  three witnesses.** `max |delta| = 0` is exactly what a comparison that silently
  DROPPED NULLS would print, blind to the ~1% of rows F-030 was found on. So each
  column's missing count must reconcile with the run's own two-sided no-geometry
  assertion, with the independently-built ANCHOR block, and with the number
  rendered in the committed table a reviewer diffs. **That is what the red team
  plants against**: one column's `both_missing` 13 → 0 — chosen from the record,
  never typed — leaving `compared`, `mismatches`, `max_abs_delta`, `one_missing`
  and the verdict untouched, so the pass still reads as a pass while describing a
  comparison that never looked. **RED with 3 FAILs from three artifacts, 48
  sub-check lines still passing, the headline-delta leg deliberately still GREEN,
  sha256-identical restore, GREEN 51/51, clean tree.**
- **F-061, found by the gate on its own first run and fixed at the cause.** The
  `kserve-predictors` scrape job keeps every pod carrying an isvc label and then
  forces mlserver's `:8082` on it — **two assumptions that were the same
  assumption** until M8-S4 leg 3 added a transformer pod, which is an isvc pod and
  is not an mlserver. It had become a permanently-DOWN target on the one signal
  whose entire value (F-043) is that `up == 0` means a predictor stopped
  reporting. Fixed with the discriminator KServe already sets
  (`component=predictor`), **not** by scoping the gate's question to the champion —
  narrowing a check to accommodate a defect is gotcha #50 inverted. No restart
  needed; the target list converged in under 5 s.
- **The gate's first run went RED eight times and four were its own defects**
  (gotcha #50, twice in one run): a registry demanded ABSENT FROM DISK when the
  property is *not tracked by git*; a bar regex encoding one sentence's word order
  instead of the bar; a typed script path (`feast_retrieval_parity.py` — the target
  runs `feast_retrieval.py`), now DERIVED from the Makefile recipe; a DVC summary
  line counted as one target out of four over a perfectly clean tree; and a ledger
  searched whole, so the milestone's own prose sentence "M8-S5's gate inherits it
  live" was read as a ledger row (gotcha #99, third occurrence). Then the TEST FILE
  went red three times for the same disease — the `feast` needle matched the gate
  *reporting* on `feast plan`, and `consume < <(` matched the instruction telling
  the next author to call it that way.
- **Nothing was fitted, no alias moved, no version was created.** `@champion` **2**
  / `feature_set v2`, versions `['1','2']` — and the gate asserts the strong form:
  not one registry version was created after the `m7-closed` tag, because a
  promotion cannot hide from a check that reads creation times. `uv.lock`
  byte-identical to `m7-closed`, host suite **1127 passed**, ruff clean, all
  settled DVC pins `up to date`, `verify-m5`/`m6`/`m7` all GREEN.

## The demo page (M9-S1) — the route that claimed less, and the one box left open
- **`http://localhost:8081/demo/` — and the Ingress rule carries NO `host:`.**
  Every route here is host-based (KServe and the charts generate them that way)
  and a browser cannot set a `Host` header on `fetch()`. A host-less rule lands
  in nginx's **DEFAULT server block**, so the page and the model share ONE
  origin and **CORS never happens** — a dissolution, not a configuration: no
  `enable-cors` annotation, no preflight, no allow-list to maintain, because
  there is no cross-origin request. **The refused alternative was measured
  first**: `location /healthz` lives only in the default block, so
  `host: localhost` would have moved the browser's Host into a named block that
  has none and turned `deploy_serving.sh`'s accept RED for a correct system
  (`Host: totally-unrouted.invalid` -> **200**, `Host: nyc-taxi-eta-serving.local`
  -> **404**, both curled before anything was applied). *When a new route would
  force an old assertion to be edited, look for the option that claims less.*
- **It claims TWO paths and neither is `/`.** `/demo` (Prefix) to a busybox
  `httpd`, and the transformer's infer path (**Exact** — one path, not the `/v2`
  tree). **No `rewrite-target` anywhere**: the ConfigMap mounts at `/www/demo`
  so busybox resolves `/demo/` natively. `/` stays 404 and `/healthz` stays 200,
  and `deploy_demo.sh` asserts both on every run rather than leaving the next
  `make deploy-serving` to discover them.
- **The page targets the TRANSFORMER, and the CHAMPION's own model name is
  deliberately UNROUTED here.** A browser cannot build the 24-column matrix and
  a JS re-implementation would be the second feature path the one-transform-path
  law forbids; M8-S4 leg 3 built the raw boundary for exactly this caller. The
  first route claimed the champion's name and every quote **404**'d — the V2
  model name is in the URL (ADR-011 condition 2, third occurrence) — and the fix
  inverted it: that 404 is now an ASSERTED negative, so the demo cannot quietly
  end up on the 24-column wire. Diagnosis was free only because the
  transformer's 404 body names the path it does answer to (**gotcha #111**).
- **Nothing about the page is typed twice.** `demo/index.html` is GENERATED
  (`make demo-page`) from three sources — the TLC zone lookup (265 zones), the
  server's own `transformer.RAW_INPUTS`, and a PUBLISHED parity row as the
  default trip — and a test regenerates it and demands byte-identity. A wrong
  field NAME would be refused loudly by `decode_raw`; a wrong DATATYPE would not
  be, and would quote a plausible number nobody could see was wrong.
- **The generator's first run substituted its own explanatory comment** — the
  paragraph naming the placeholders — shipping **795 `<option>` elements across
  two `<select>`s instead of 530**. It rendered, and no "the zone list matches
  the CSV" assertion would have caught it because all three copies matched. The
  guard is an **occurrence count** (`TOKEN_COUNTS`), not a cleverer parser:
  gotcha **#110**, and the fourth time prose has sat where a parser reads it as
  code.
- **TLC's two non-places are RENDERED, not hidden** (264 "Unknown", 265 "Outside
  of NYC", in their own labelled group). They carry no centroid by DR-04
  condition 1, they are ~1% of every split, `264 -> 264` is the largest single
  OD "route" in the data, and F-030 was found on that path. Quoting one returns
  **8.2445 min** from the features that remain. A picker that hid them would
  make the demo tidier than the world it quotes for. Three error classes render
  differently on purpose — **422** a refusal (a 2031 date: the horizon is a
  feature to demo, not to hide), **503** a dependency outage the caller cannot
  fix, anything else named as unexpected rather than blank (gotcha #78 at the UI).
- **`make demo-accept` PASSED 9/9, and it sends what the PAGE sends.** The
  endpoint, the request schema and the payload are READ OUT of `demo/index.html`
  and posted with **no Host override** — the one thing a browser cannot do and
  every other client in this repo does; a check that retyped any of the three
  would be measuring a look-alike. Bar **EXACT**, argued in `demo/README.md` §4
  and committed two commits before the record existed: **39.00193715359812 vs
  the recorded 39.00193715359812, |delta| = 0.000e+00**, `model_version` **'2'**
  off the ANSWER, `X-Taxi-Lookups` equal to the recorded string (the store was
  consulted through THIS path and F-059's two committed groups did not cross),
  and the page a browser receives **byte-identical to git by sha256**, fetched
  back through the route rather than asserted from the ConfigMap.
- **STATELESS, so ledger row YES and backup obligation NO** (M8-S4 leg 2's
  precedent, recorded in both directions so the absence does not read as an
  omission). No PVC, no database, no hostPort, no new image — `busybox:1.38.0`
  at the digest `flyte-data-stager.yaml` already pins, with a test asserting the
  two refs are ONE string. Losing all four objects costs one `make deploy-demo`.
- **The champion's wire is untouched and the proof is a pod UID**: still
  `9b1f1b03-7dfe-458f…`, the uid M8-S4 leg 3 recorded, at 4d age. `@champion` is
  never read by this story at all — no registry client is imported by any file
  it added (asked of the AST), and the version the page shows is mlserver's own
  stamp forwarded verbatim.
- **The §9/M9 box "one non-technical person completes a query unassisted,
  observed" is OPEN, by design and in writing** — in the accept record's
  `po_observed_run.status`, in the story record, and at AWAITING_PO
  2026-08-23-3 with the URL and the one command. `make verify-m9` is chartered
  to assert that entry exists and is honest, never to render the box green. A
  demo that marked its own human-observation box green would be the only
  dishonest artifact in this program.
  **CLOSED 2026-08-24 by the PO, landed by M9-S5** (the sentence above is kept:
  it describes the state the gate must still be able to express). The record
  reads `CLOSED — observed 2026-08-24, cited at AWAITING_PO 2026-08-23-3` and
  quotes the PO's note; the gate was RE-DERIVED, never hand-flipped, to the
  two-state property **OPEN-and-honest or CLOSED-and-CITED** — a CLOSED status
  with no citation, or one AWAITING_PO does not hold, is RED (demonstrated
  twice, 44 sub-checks still passing). The banner's box paragraph is derived
  from the record it just judged. **F-067 came with it**: `demo_accept.py`
  rewrites that record in full, so its literal `OPEN` block would have deleted
  the PO's closure on the next ordinary re-run — the decision is
  `human_box()` now, which carries a CLOSED block forward verbatim and can
  never author one (an AST test asks the narrow question, because the word
  itself matches the code RECOGNISING a closure).

## The online-store watchdog (M9-S2) — R-2 closed, with two rules carrying no number
- **The headroom leg did not calibrate a bar, it DELETED one.** Feast writes one
  Redis key per distinct entity key per view, so the store's size has a source of
  truth **that is not itself** — and **three witnesses agree at 57,688** (derived
  from `data/feast/*.parquet`, M8-S4's materialization record, the live `DBSIZE`;
  nobody typed it). So `OnlineStoreIncomplete` is `keys < keys_expected` with
  **no number on either side**, both measured by one reader on one run; it
  self-updates when `make feast-sources` legitimately changes the sources, and
  the window between a source change and the next materialize IS the stale state.
  Two other measurements made a count bar look actively bad: **the transformer's
  entire dependency is 4,646 keys, 8.054%** (a store that lost every feature the
  rider's path needs still reads 92% of normal), and **zone 132's centroid is ONE
  key of 57,688** — lose exactly the key that breaks every JFK quote and `DBSIZE`
  moves 0.0017%. **A quantity can be perfectly accurate and structurally unable
  to see the event it is watched for** — gotcha #59 arriving in an aggregate.
- **"Stale" had to be REDEFINED before it could be alerted on.** SLO-D3 asks
  whether the drift JOB ran recently and argues 40 days from a monthly cadence;
  that question has no answer here, because this store's data is SETTLED (2019
  windows, a 2019 shapefile, a holiday table to 2030) and a store filled in
  August 2026 is exactly as correct in 2027. A clock-age bar on its contents
  would be a number chosen to avoid paging. **A store is stale when it disagrees
  with the sources it was filled from.**
- **A-12a asks about ANSWERS, not size, and one of its four claims is negative.**
  The canary rides the feature server's own `/get-online-features` wire — the
  same one the transformer uses: zone 132 must answer, zone **264 must DECLINE**,
  2019-07-04 must return its holiday flags, and `DBSIZE` must have been readable.
  Expression `== 0`, a property. **A-13** is `absent(...)`, A-11's argument one
  board along: A-12's freshness clause is structurally unable to see its own
  series disappear, because `time() - stamp < 1800` over zero series is zero
  series. **The one number in any of the three expressions is A-4's `1800`**, and
  its cost is named rather than netted out — this reader has NO scheduler (M9
  legislates no new Flyte trigger — F-058 — and the story adds no image and no
  CronJob), so a reading older than 30 minutes makes A-12 **INACTIVE rather than
  falsely green**.
- **`store_reachable` is REPORTED as a 0, which inverts A-4's refusal rule on
  purpose.** `push_serving_version.py` refuses to push when a side is unreadable
  and is right to — an unknown served version is not a mismatch. Here it
  inverts: if the Redis pod is gone, *"I could not read DBSIZE"* is not a gap in
  the measurement, it **is** the measurement, and a reader that withheld it would
  leave the last healthy reading to go quietly stale. Honest cost: a broken
  `kubectl` on the operator's laptop reads the same as a broken store.
- **The prediction everyone had written for two milestones was WRONG, in the
  useful direction.** The kickoff, ADR-012 and two M8 write-ups all expected an
  emptied store to produce a **confident wrong number** from nine NaN geometry
  features. Measured with the store really empty: **HTTP 422**. The geometry half
  structurally CANNOT refuse (an all-null centroid table is exactly what zones
  264/265 legitimately produce) but every request also carries a DATE and
  `calendar_from_store` RAISES on an unanswered one — so **the thing standing
  between an empty store and a wrong quote is F-019's horizon guarantee, carried
  onto the store's wire two stories earlier for a different reason.** **503 is
  what an UNREACHABLE store produces** — a different phase of the same drill.
- **F-062 (new, OPEN, routed to the program close): a dead dependency is billed
  to the CALLER.** 422 is a 4xx, and SLO-R1 puts 4xx outside SLO-A1's
  availability budget on the argument that *a 4xx is a guard working* — so a
  totally dead store spends **zero** error budget and renders, in every panel
  that splits 4xx from 5xx, as riders sending bad requests. A-12 pages, so it is
  not silent; the ACCOUNTING is. Three costed options in the ledger row,
  recommendation (b): make `calendar_from_store` distinguish *this date is not
  covered* (422, F-019's case) from *the store answered nothing for any date*
  (503, ours). Not fixed here because changing what the served boundary returns
  is a behaviour change with three parity records behind it and M9 law 3 keeps
  the wire still.
- **The drill PASSED 28/28 across three phases with its prediction committed
  first** (`automation/runs/m9-store-watch/prediction.json`, pinned by a test
  against the drill's own literal). `FLUSHDB` 57,688 -> 0; **A-12a AND A-12b both
  FIRED at T+162.2 s and both reached Alertmanager**; the failing claims were
  read **per series** (`['calendar_answers','zone_answers']`) and not per rule
  name (gotcha #93); **all five must-not-fire negatives held** (A-13, A-2, A-5,
  A-11, A-4); the champion's own wire answered **39.0019 minutes throughout**;
  refill **57,688 keys in 9.9 s**; both rules cleared 30.0 s / 0.0 s and **the
  board ends carrying the truth, not a silence** (M7-S3's rule).
- **A measured limit of the negative check, recorded rather than left to be
  rediscovered:** `nonplace_declines` read **1 through the whole outage**. Zone
  264 returning `null` is the correct answer AND what a totally empty store
  returns, so that claim cannot distinguish "correctly declines" from "has
  nothing to decline with" — which is why the two POSITIVE checks are the ones
  that fire. **A negative assertion is strongest where presence is possible**
  (F-060/gotcha #105 meeting its own boundary).
- **F-063 (new, closed the same session): the drill's UNDO rewrote another
  milestone's tracked evidence.** `scripts/feast_materialize.sh` is the
  one-command repair the runbook names and it unconditionally writes
  `automation/runs/m8-online/materialize.json` — M8-S4's record, cited by §9 and
  by this story's own headroom leg — so the first run re-dated it from
  `2026-08-21T07:52:13Z` to its own minute. Fixed with `--no-record`, M8's record
  restored from git, the phase RE-RUN so every committed record was produced by
  the committed code, and the drill keeps its own `refill_seconds` where it
  belongs. Third occurrence of one shape (gotcha #48, F-053): **when a command is
  reused as somebody else's undo, audit what it does to state that already
  exists.** Visible only because `automation/runs/**/*.json` is tracked — F-029's
  option A, landed at M5-S1 and paying out three milestones later.
- **The order of work is the evidence and it is checkable from git** (M8 law 4,
  ninth inheritance): headroom recorded -> `docs/slo_serving.md` §9 argued FROM
  that record (both in `cedb9e8`) -> reader and rules (`c8290da`) -> the
  prediction committed (`408b472`) -> the drill ran and first crossed a bar.
- **What it deliberately does not cover, named in §6**: a store filled from the
  WRONG sources has the right key count and passes every canary (that instrument
  is `make feast-online-parity`, 100 declared pairs at bar EXACT, and it is
  gate-time rather than a watchdog) · the CADENCE, bounded by the freshness
  clause rather than claimed to be small · F-062's billing question.

## Two closures (M9-S3) — the tool made to agree with the reviewed artifact, and a guard whose verdict flipped
- **F-057 CLOSED, and the pin file did not move: +0/−0, sha256 `a700cd6b…`
  before and after.** The defect was that `--rewrite-pins` emitted distribution
  names as PUBLISHED (`PyYAML`, `typing_extensions`) where the file carries the
  normalized spelling, so the file's own regenerator could not reproduce the file
  it maintains and M8-S4's two real additions arrived as **+14/−12**. Normalizing
  fixes twelve spellings and leaves **three** lines still moving — the committed
  body is sorted **as LINES** (`mypy-extensions==…` before `mypy==…`, because
  `-` < `=`) while today's `uv pip freeze` name-sorts. **The tool was made to
  agree with the artifact, not the artifact rewritten to agree with the tool**,
  so the M9 kickoff's anticipated "regenerate in a commit that does nothing else"
  has NO CONTENT — and that is the stronger closure: the round trip is proved
  against a file under review since M8-S2 rather than against one the fix just
  wrote. Legitimate because this script is the file's ONLY producer
  (`feast_quarantine.sh --resolve` calls it) and sorting the lines is the order a
  reviewer verifies with `sort -c`. Honest cost, recorded: a hand-run `uv pip
  freeze` differs on those three lines.
- **PEP 503, not the finding's own one-liner** — `[-_.]+ -> -` lowercased,
  against the row's `lower().replace('_','-')`. They agree on all 66 names the
  quarantine holds today, which is exactly why it was worth doing before somebody
  adds a dotted name and gets a spelling no installer canonicalises to; both
  differing cases are in the test. And the transform maps many to one, so a
  COLLISION **raises** rather than silently dropping a pin from a file whose whole
  claim is completeness.
- **The from-pins rebuild was re-earned, not inherited**: `.venv-feast` deleted
  and rebuilt with `uv pip install --no-deps -r …` → the **same 66 packages, 0
  only-before, 0 only-after**, quarantine pandas 2.3.3 / feast 0.66.0 against the
  project's 3.0.5, feast absent from the project env, `uv.lock` `640154c5…`
  unchanged throughout. **M8-S2's probe record was deliberately NOT regenerated**
  — it is that story's tracked artifact and already diverges by design (64 pins,
  pre-`redis`/`hiredis`); rewriting another milestone's record as a side effect is
  F-053/F-063's shape (gotcha #48), and `make feast-quarantine` is the command
  whose job that is.
- **F-054 CLOSED: zero `skipif`-on-record-existence remain under `tests/`**, and
  the closure is a GUARD'S VERDICT rather than twelve edits. `test_record_marker.py`
  used to subtract the older form from its coverage check — i.e. accept it — and
  argue against it in prose; `_skip_guarded` now feeds a test that REFUSES it,
  **derived by AST across every test file** because a check naming its two known
  offenders goes green the day a third grows one. *A finding that lives as a
  documented exception inside a guard is closed by changing the guard's verdict;
  the instances are what it then catches.*
- **The deciding fact was that the records are TRACKED** (F-029 option A, M5-S1),
  so option (a)'s stated cost — a fresh clone cannot go green until the drills run
  — is void, and the assertion catches exactly one new thing: a deleted record.
  Each file carries one `_record()` helper asserting existence with a message that
  says what the absence MEANS, because the default failure is a bare
  `FileNotFoundError` five frames deep.
- **Host suite 1171 passed, NO SKIPS** (was 1167), and `-m 'not needs_records'`
  now deselects **53** where it deselected 41 — the twelve moved from skipping
  everywhere to running on the host and being deselected in the ONE place F-047
  allows. **Both halves red-teamed by planting the exact defect being closed**:
  one pin back as `PyYAML` → 2 tests RED from two independent angles (the
  artifact's own property and the round trip); one record moved aside → 3 FAILED
  naming the record and the finding, 12 still passing. Both restored, GREEN,
  clean tree.

## The last gate (M9-S4) — three questions instead of fourteen, and a check that had been reporting a comparison it never made
- **`make verify-m9` is 45 sub-checks in 7 sections, 4.450 s, and it RE-RUNS
  NOTHING** — ninth and FINAL inheritance of M1's no-skip-flag rule. M9's
  evidence is a deployed page, a materialized store and a drill that included a
  **real total outage of the transformer's dependency** (`FLUSHDB`), so
  re-provoking any of it would cost an outage per verification, and re-running
  the demo's own accept would overwrite the record the gate exists to read.
- **It asks THREE live questions and the interesting decision was subtraction.**
  One quote through the DEMO's own request path (endpoint, schema and payload
  read out of `demo/index.html` by the accept script's own helpers, module path
  DERIVED from the Makefile recipe, posted with **no Host override** — the one
  thing a browser cannot do and every other client here does), one rules read,
  one DBSIZE. The champion's wire, the feature server's two-sided answer and the
  exporter's health belong to `verify-m5` and `verify-m8`, which the boundary
  runs live as their own evidence. **A gate that re-asks its predecessors'
  questions is not stricter — its live footprint just grows every milestone**, so
  the test pins the ABSENCES too (no `client_mod.infer(`, no
  `get-online-features`, no `/api/v1/query`): a bound that only says "at most
  three" is satisfiable by three of somebody else's.
- **A gate that passes BECAUSE something is unfinished.** §9/M9's last accept
  line needs a human, and every gate in this program renders green. So this one
  checks the box is recorded HONESTLY — the record says OPEN, AWAITING_PO carries
  the invitation, the two agree on the URL — and prints it as an **OPEN ITEM in
  §2 and in its own GREEN banner**, where a reader who skims only the verdict
  still sees it. Three assertions in `tests/unit/test_verify_m9.py` hold that,
  banner included, because the failure mode is not a bug but a temptation.
- **Two rules carry no number, so the gate checks the ABSENCE of one.** A-12a
  compares a canary claim to `0`; A-12b compares a live key count to an expected
  count the reader pushes on the same run. Checkable instead: no numeric literal
  on either side of A-12b, the ONE number in all three rules (A-12's 1800 s
  freshness clause) argued in §9 **specifically**, and the strongest —
  **every series the rules SELECT is a series `store_health` PUSHES**, because a
  rule selecting a series nobody produces does not error, it sits `health=ok` and
  `inactive` forever (gotcha #92's shape), which is what a healthy store looks
  like.
- **The expected key count has three witnesses and the gate asks all three**:
  the headroom record's per-view counts summing to its own total (263 + 4,383 +
  46,938 + 6,104 = 57,688), the M8-S4 materialization record, and the live
  server. `keys < keys_expected` is only honest if the expected side is DERIVED
  from the store's sources rather than remembered.
- **Law 4 is checked from git four times** — 133 s · 0 s · 1878 s · 700 s — and
  it is the tenth inheritance: the demo's EXACT bar before the accept record, the
  headroom before §9 argues from it, §9 before the first drill record, the
  prediction before the record that judges it.
- **All three of its own first RED runs were the gate's defects, and the third is
  gotcha #50 again.** The F-054 leg asked "does any test skip on a `.exists()`?"
  and flagged a test skipping on `.venv-feast/bin/python` — a **gitignored build
  artifact**, absent in CI, where skipping is CORRECT and is this suite's idiom
  for `ss`/`git`/`make`/`docker`. F-054 is about **records** under
  `automation/runs`, which are TRACKED, so their absence means deleted-or-lost.
  Repaired by NARROWING to the right property (each file's record constants
  resolved from their own assignments), never by widening the bar.
- **F-064 CLOSED, and it is a clause that had shipped green nine times.**
  `verify_m8.sh` read `materialize["store"].get("keys")` where the record spells
  it `dbsize`, so `expected` was always `None`, the `expected is None` branch
  fired, and the leg tested **`dbsize > 0` alone** while telling its reader "the
  count the materialization recorded" — it would have passed a store holding ONE
  key, in the gate whose job on that line is to notice an empty store. Invisible
  precisely BECAUSE the original was written defensively; found when the M9 gate
  copied the clause and spelled it strictly. Fixed and `make verify-m8` re-run
  GREEN with the real comparison. **Gotcha #51's question asked of a PASSING
  check — and a defensive default in a VERIFIER is a different thing from one in
  a producer: in a producer it keeps the system running, in a verifier it keeps
  the verdict green.**
- **The red team plants a POPULATION, not a measurement**: `expected_keys.total`
  short by exactly the smallest view's 263 keys (the view chosen from the record,
  the one holding every centroid), which loosens no rule, leaves every alert
  inactive and 42 sub-checks green — and describes a store that could lose all
  its geometry and still satisfy A-12b. **RED with 3 FAILs from three artifacts**
  (the record's arithmetic, the live DBSIZE + materialization record, and the
  write-up), the no-number and ordering legs deliberately still GREEN, sha256
  restore, **GREEN 45/45**, clean tree. The prose witness had to be BUILT for the
  drill — the usual yield of writing the red team second is that it tells you
  which witness the gate was missing.
- **Nothing was fitted, no alias moved, no version created, no wire changed.**
  `@champion` **2** / `feature_set v2`, versions `['1','2']`, `uv.lock`
  byte-identical to `m7-closed`, all 5 settled DVC pins up to date, host suite
  **1204 passed** (was 1171), ruff clean, `verify-m5`/`m6`/`m7`/`m8` all GREEN.

## Whose fault is a null? (M9-S7) — the epilogue's one wire change, and the 404 that punished the next caller
- **An emptied online store answers HTTP 503 now, and that one number is the whole
  of F-062.** The refusal was always right — the champion eats holiday flags and a
  silent "not a holiday" is a wrong number nobody can see — but 4xx is the
  CALLER's class and SLO-R1 puts 4xx outside SLO-A1's error budget on the argument
  that *a 4xx is a guard working*. So a **totally dead dependency spent zero error
  budget** and rendered, in every panel that splits 4xx from 5xx, as riders sending
  bad requests. A-12 paged, so nothing was silent; the ACCOUNTING was. PO answer
  **(b)**, landed; SLO-R1's target and its 1% bar are UNALTERED — what moved is
  which requests are inside the budget.
- **Two different facts wore one value, so the fix asks a second QUESTION rather
  than reinterpreting the first answer.** For the requested date an empty store and
  a date past the horizon both return `null`, and Feast's per-result `statuses` say
  `NOT_FOUND` for both — the response cannot discriminate. On the failure path
  only, the store is asked for a date the committed holiday table **provably
  covers**: a sentinel DERIVED from that table's first year, which is the twin of
  the left edge of the `date_range` `build_calendar_day` generates the store's view
  with. Answered -> the caller's **422**. Null too -> **503
  `FeatureStoreUnavailable`**, ours. The rejected alternatives are recorded as
  WEAKER rather than merely different: the ZONE half cannot discriminate, because
  zones 264/265 legitimately have no row, so "every zone came back null" is a legal
  answer for a request naming only TLC's two non-places.
- **Three properties, and the third is the one that is usually skipped.** It costs
  the happy path nothing (failure path only, and skipped entirely when any date in
  the batch answered — the boundary's measured ~18 ms p50 is untouched). When the
  DISCRIMINATOR ITSELF cannot be built that is reported as ours too, not as the
  caller's (F-048's rule: an unresolvable value fails loudly rather than resolving
  to something convenient). And **the guarantee this could have destroyed is
  ASSERTED, not argued**: once a status depends on a second round trip, "F-019
  still refuses past-horizon dates" stops being something a code-reading can
  establish, so the drill asks in BOTH store states — **422 naming the year while
  the store answers, 503 while it does not**, with the year derived from the table.
- **The drill PASSED 36/36 across FOUR phases** against a prediction committed at
  `b89eea4` **before** the first `FLUSHDB` (checkable from git). A-12a/A-12b fired
  at **T+162.5 s** and reached Alertmanager, failing claims read per series; all
  five negatives inactive; refill **57,688 keys in 11.6 s**; both cleared 30.0/0.0 s
  and the board ends carrying the truth. **The fourth phase ran for the first time
  in this drill's life** — surface deleted, **A-13 FIRED at T+630.7 s while A-12
  stayed inactive**, the load-bearing negative. The 422-era records are kept
  unedited at `automation/runs/m9-store-watch/attempt1-422-era/` with a README:
  **that 422 IS the finding's evidence**, and a re-run that overwrote it would have
  been F-063/gotcha #48's shape a fourth time.
- **All three parity records came back 0.000e+00 at their committed EXACT bars**
  (`transformer-parity` 16 hazards · `server-parity` 6 columns/108 comparisons,
  `one missing` 0 · `online_parity` 16 columns/100 pairs, `UNEXPLAINED` 0). That is
  the assertion that an error-path change touched the error path and nothing else —
  a nonzero delta would have been a story-stopping finding, never a bar to widen.
- **F-069, found by the re-measurement and unrelated to the accounting: a 404 that
  leaves the request body unread poisons the NEXT caller.** `protocol_version =
  "HTTP/1.1"`, so a response sent while the body is still in the socket leaves those
  bytes to be parsed as the next request's request-LINE — and ingress-nginx pools
  upstream connections, so the victim is a different client entirely: a perfectly
  good quote answered **400 Bad request syntax** with its own JSON echoed back
  inside an HTML error page. The poison was planted by `do_POST`'s wrong-path 404 —
  **the deliberate negative check M8-S4 leg 3 added to prove the champion's model
  name does not answer here** — and paid for by the parity run that check exists to
  protect. Body is read BEFORE any branch now. The regression test drives two
  requests down ONE connection and its second request is a **422 and not a
  malformed body**, because a malformed body is a legitimate **400** — the same
  status a poisoned connection returns, so that version could not have told them
  apart. RED against the pre-fix module, restored, GREEN.
- **`verify-m9`'s drill leg was re-derived to ask for a PHASE, not a filename.** It
  keyed records on `drill-<phase>.json`, which is what `--phase empty` writes — but
  `--phase all`, the make target's DEFAULT, writes one `drill-all.json` holding
  every phase's block, so the gate went RED for the default invocation of the
  command it checks (gotcha #50's shape). One added sub-check too: F-019's
  guarantee across both store states, with both predicted sides read from the
  committed prediction so the leg carries no status literal of its own.
- Exit state: `@champion` **2** / `feature_set v2`, versions `['1','2']` — no
  version 3, nothing fitted, no alias moved · `uv.lock` byte-identical to
  `m7-closed` · all 5 settled DVC pins up to date · host suite **1220 passed** (was
  1204) · ruff clean · **`verify-m5`/`m6`/`m7`/`m8`/`m9` all GREEN**.

## The front door (M9-S8) — a README with a twin, and the number it caught in its own diff
- **`make readme-check` is the README's twin** — the
  `error_memo_numbers.py` / `drift_memo_numbers.py` idiom, one AUDIENCE out. Four
  legs, each able to fail alone: every `make <target>` the README names exists in
  the Makefile · every repo-relative path it links to exists · **every number in
  its evidence table is read back from the record that holds it**, at the
  precision the README renders it at (gotcha #42) · and the Status table still
  carries all twelve rows. 29 claims, 20 targets, 28 paths. A front door nobody
  can re-derive is marketing.
- **The proof that the twin was needed came UNPLANTED, out of this story's own
  diff.** The table shipped `1,220 tests` — true that morning. Seven new tests
  made it **1,227**, and the checker went RED naming the claim, the record and
  both values before anyone thought to look. The planted drill was run afterwards
  anyway (`13.75 s` → `13.5 s` in the self-heal row → RED naming the row; restored
  and sha256-verified byte-identical, `0324aabdbe4f913d` both sides).
- **A claim needs an ANCHOR or its presence half is vacuous** — and the rule fired
  on four of the author's own claims. The checker asserts the rendered text
  appears in the README and then that it equals the record; the first half is a
  substring search, so `10` is satisfied by the `10` inside `104.226 ms` and `55`
  by `557,688`. It now REFUSES a claim carrying no non-digit character, which is
  why the table renders `PSI 0.0217`, `**57,688** keys` and `10 gates · 8 red
  teams` rather than digits. Gotcha #76 said anchor the needle; this says the
  ARTIFACT must give it something to anchor to.
- **The Status table is byte-identical, and that is asserted twice** — by the
  checker's own leg and by a unit test naming all twelve rows. The front door
  gained an audience; it did not lose its ledger.
- **Two placeholder-vs-invocation defects, both in the checker's own legs, both
  gotcha #99's family.** `make verify-mN` is a FAMILY, not a target, and a
  lowercase-only pattern truncates it to `verify-m` — a target this repo has never
  had; the leg now reads the character AFTER the match and skips a word it stopped
  in the middle of. And the Status table's `PROGRAM_CLOSE.md` is prose shorthand
  inside a row whose subject is already `docs/milestones/`, so the path leg
  requires a `/` before resolving anything against the repo root.
- **A checker that dies reports nothing** (gotcha #94's direction): a resolver
  raising `KeyError` because a record's SHAPE moved used to abort the whole run at
  claim five. Every leg is wrapped now and reports *could not read the record*
  naming the claim, so one moved key costs one FAIL and not the other 29 verdicts.
- **The drift the method caught in passing**: `CLAUDE.md`'s M9-S2 row said "16
  rules across **10** signal ids (was 13 across 9)". The rules file says **13**
  ids and `git show m8-closed:` says the before-state was **11**. "Ten ids" was
  true at M7-S3 and carried forward twice without recounting. Corrected with a
  dated note beside the original; the README's copy of that fact is now read out
  of `alerting_rules.yml` on every run.
- **Three of the new tests reach records through a SUBPROCESS, which F-047's
  static guard cannot see** — it reads the test file, not the checker's claim
  table. They carry `needs_records` AND the file names the record directory in a
  constant it asserts, so the guard agrees rather than the marker sitting there
  unexplained; `-m 'not needs_records'` deselects **56** (was 53) and the in-image
  suite stays honest.
- Exit state: nothing fitted, no alias moved, no version created, **no wire
  touched** (a doc + one reader + one test file). `@champion` **2** /
  `feature_set v2` · host suite **1227 passed** (was 1220) · ruff clean ·
  `make verify-m5` and `make verify-m9` GREEN after the change.

## The pre-publish audit (M9-S9) — the scan that flagged its own record, and a drill that lied comfortably
- **Zero secrets in anything git holds, verdict `publishable: true`** — over every
  file on this disk, **every commit on every ref**, the three images this program
  builds, and `uv.lock` plus the hand-written manifests. trivy **0.74.0** and
  gitleaks **8.30.1**, pinned by VERSION (never `latest`) with sha256s in a
  tracked record. `.env` never entered git by design, so this VERIFIES hygiene
  rather than creating it — which makes the expected answer the same one a broken
  scanner gives, and is why every leg records the inputs it looked at (gotcha #59)
  and why `make security-scan-redteam` exists.
- **The triage is a classification and the tempting alternative is a lie by
  omission.** Findings split into **in git** (tracked, in history, or untracked
  AND unignored — one `git add -A` away), **acknowledged**, and **gitignored on
  this disk**, the last carrying `git check-ignore -v`'s own answer beside each
  one. `.env` trips the scanner ten times and that is CORRECT. A scan pointed only
  at tracked files would report zero and prove nothing about the hazard anyone
  actually has: a developer committing the `.env` they have been editing all week.
- **The one acknowledged finding is a DERIVATION, not a suppression.**
  `scripts/gameday_m6.py:699` holds the M6-S5 gameday's deliberately WRONG MinIO
  secret — *a credential designed not to work is the one string in this repo that
  must look exactly like a credential*. No `.gitleaksignore` (a suppression nobody
  can read is how the next real one hides behind it): it is keyed on the sha256 of
  the found bytes, and the scan DECODES the bytes it actually found and requires
  them to spell `wrong-credential-gameday`. It fails in BOTH directions — an entry
  matching nothing is a stale suppression and is itself a failure
  (`render_alert_rules.py`'s rule). A unit test proves the table offline too:
  encoding the claimed plaintext and hashing it must reproduce the key.
- **The scan flagged its own tracked record, thirteen times, and was right.** The
  first run wrote each finding as a 64-hex digest under a field called
  `secret_sha256` — `generic-api-key` fires on a long high-entropy value under a
  credential-shaped key, and both halves were there. Fixed in the ARTIFACT: a
  **12-character** `finding_id` in the record, the full digest kept in code where
  it is a dict key rather than a value after a credential-shaped name, and
  `_`-prefixed working fields stripped at the WRITE BOUNDARY so a leg added later
  cannot leak one. The quieter twin: the tree scan read its own previous raw
  report, making the finding count a function of how often the scan had been run —
  dropped, COUNTED and named, and the drop is BOUNDED (the code EXITS rather than
  dropping anything heading for `blocking`).
- **F-071 — the red team was flaky in the direction that reads as good news.**
  Two runs in five reported all six detection checks failing, i.e. *the scanner
  found nothing*, while the scan was perfect. Both causes were the PLANT:
  `generic-api-key` matches `[\w.=-]`, which excludes `+` and `/`, so a
  base64-alphabet secret with an early `+` was truncated below the rule's minimum
  length; and both rules carry an entropy floor a short random string clears only
  on average (a 20-char AWS-shaped id measured **3.15–4.22** bits over 2,000
  draws). **A randomly generated plant must be drawn against the properties the
  detector keys on** — the generator redraws above a stated floor, measures entropy
  over the WHOLE matched string (prefix included, because that is what the scanner
  sees) and PRINTS it. Four consecutive **16/16** runs after, one at the floor.
- **The drill also found a real gap on its first run**: a blocking HISTORY finding
  printed rule, file and line and **no commit** — and the remedy for a secret in
  history is per-commit. It prints commit/author/date now. And destruction is part
  of the drill: branch deleted, reflog expired, `gc --prune=now`, then
  `git cat-file -e` ASKED whether the object is gone — *"I deleted the branch"* and
  *"the object is gone"* are different claims and only the second is what
  publishing cares about.
- **CVEs are recorded, not chased — but the record splits the ones we can act
  on.** 201 · 196 · 879 across the three images (the predictor's is its py3.10
  mlserver base, which M5-S2 already recorded as unmovable), plus 5 dependency
  CVEs and **76 failed pod-security/Dockerfile misconfiguration checks**, listed
  per file rather than totalled so a hardening pass can start from the list. The
  actionable split is trivy's own `Class: lang-pkgs`: an OS package in a Debian
  base is Debian's to fix and ours to pin, a Python package in `uv.lock` is a line
  we wrote. Exactly one cluster qualifies — **`sqlparse` 0.5.5, three HIGH, fix in
  0.6.0**, transitive through dbt-core and mlflow-skinny — and it is **NOT bumped
  here** because `uv.lock` is asserted byte-identical to `m7-closed` by
  `verify-m8` §1: a PO fork with a stated cost (AWAITING_PO 2026-08-24-5), never a
  quiet edit. Exposure bounded and stated: nothing here parses SQL from an
  untrusted party.
- **No pre-commit hook, deliberately.** The M1 prior-art ADOPT was commit-time
  scanning; a hook lives in `.git/hooks`, which is not tracked and no gate here can
  verify — it would be a claim this repo could not check. `make security-scan` is
  the on-demand audit and its verdict is a tracked file.
- **Two smaller lessons.** A README claim of "489 commits" can never be right,
  because fixing it adds a commit — a number that invalidates its own correction
  belongs in the record, not the document. And my own new test forbade long hex in
  the record and tripped on commit shas and image ids: a guard firing on correct
  data is re-derived, never widened (gotcha #50) — the real property was always
  *a long value under a credential-shaped key*.
- Exit state: nothing fitted, no alias moved, no version created, **no wire
  touched, no cluster call that writes**. `@champion` **2** / `feature_set v2` ·
  host suite **1244 passed** (was 1227) · ruff clean · `uv.lock` byte-identical to
  `m7-closed` · `make readme-check` GREEN · `make verify-m9` GREEN 45/45.

## Port family (fleet rule: check for foreign stacks before cluster-up)
MLflow 5000 · MinIO 9000/9001 · Flyte console 8080 · Grafana 3000 ·
KServe ingress 8081 · Pushgateway 9091 · Metabase 3030 · Postgres 5432 (in-cluster only)
Enforced by `make ports` (`scripts/port_precheck.sh`), which checks this family
PLUS every `hostPort:` in `infra/kind/kind-config.yaml` (adds 8443, the ingress
TLS mapping). This list and the `PURPOSE` map in that script are twins — change
both together. Known limit (F-002): `ss` sees only inside the WSL VM.
**The check now resolves the HOLDER (F-021 CLOSED, M4-S2).** `ss` cannot answer
"whose?" — a published port is held by docker-proxy, not by the workload — so the
script reads `docker ps` and keeps the containers whose name starts with the
cluster name parsed out of the kind config. A busy port published by one of OUR
node containers prints `held by US — the 'mlops-taxi' cluster is up, which is
expected` and the check exits **0**; a foreign holder still gets the unchanged
gotcha #10 refusal at exit 2. Observed live: `10 required port(s): 4 free, 6 held
by us, 0 foreign`. Both states are pinned by tests that differ ONLY in the
container name. If `docker` is absent, every busy port reads foreign — the
pre-F-021 behaviour, which is the safe direction to fail in.
**Port 8080 is RESERVED, not used (M4-S2).** Flyte gets NO hostPort while the
cluster is stateful (adding one means a rebuild) and there is no ingress
controller until KServe at M5, so the console/API is reached with
`make flyte-console` — a recorded deviation from the declared-route doctrine,
with its reason, not a drift. The declared route lands at the next PO-sanctioned
rebuild.

**The demo page (M9-S1) adds NO port and NO route of its own.** It rides the
EXISTING 8081 ingress (M9 law 1: kind publishes host ports at cluster-CREATE
only), and its Ingress rule carries **no `host:`** — so it lives in nginx's
DEFAULT server block beside the `/healthz` that block already answers, claims
`/demo` and one exact infer path, and leaves `/` at 404. That is what makes the
page same-origin with the model and dissolves CORS. See `demo/README.md` §1 for
the alternative that was measured and refused.

**Redis (the Feast ONLINE store, M8-S4) is NOT in the port family, and that is a
decision.** It is not a required port: it gets **no hostPort** (M8/M7 law 1 —
kind publishes host ports at cluster-CREATE only), nothing binds it on the host,
and the only host access is an EPHEMERAL `kubectl port-forward` that
`make feast-materialize` and `make feast-online-parity` each start and tear down
themselves. That forward uses **6380, deliberately off 6379**, so a
materialization can never write into a developer's own local Redis if the forward
were to die. In-cluster readers use `redis.feast.svc.cluster.local:6379`. Same
recorded deviation as Flyte's console and the pushgateway — see ADR-012.

**Port 9091 is RESERVED, not used — and the pushgateway is LIVE behind it
(M7-S3).** The gateway runs in-cluster from M7-S3 and gets **NO hostPort**
(M7 law 1: kind publishes host ports at cluster-CREATE only, so adding one means
a rebuild). Prometheus scrapes it by Service name; a human reaches it with
`kubectl -n monitoring port-forward svc/prometheus-prometheus-pushgateway
9091:9091`. Same recorded deviation as Flyte's console and the monitoring UIs'
3000, and it lands at the same next PO-sanctioned rebuild. **The Service name
doubles the word `prometheus`** — the subchart's fullname template prefixes the
helm RELEASE name to its own chart name — and it was READ off the live Service
after the first guess left the scrape target `down`.

**How a host port reaches a service (M0-S3).** kind publishes host ports at
cluster-CREATE time only, so the route is declared, never port-forwarded:
`hostPort` in the kind config → `containerPort` = the Service's fixed
`nodePort`. Live pairs: 5000←30500 (`infra/manifests/mlflow-nodeport.yaml`),
9000←30900 and 9001←30901 (`infra/helm/minio/values.yaml`), **3030←30300**
(`infra/manifests/metabase.yaml`, added M1-S5), 8081←80 / 8443←443
(ingress, **LIVE from M5-S1**). Each pair is TWINS across two files — `tests/unit/
test_platform_scripts.py` fails if they drift. Adding a port means
`make cluster-down && make cluster-up`; there is no live path — M1-S5's
rebuild was PLANNED for exactly this reason, not discovered.

**8081/8443 are LIVE from M5-S1, and the second hop is the one people debug
wrong.** kind published `containerPort 80 -> hostPort 8081` on the CONTROL-PLANE
node at create time; that only becomes a route when something BINDS port 80 on
that node. So `infra/helm/ingress-nginx/values.yaml` uses `hostPort` plus a
`kubernetes.io/hostname` nodeSelector plus a toleration for that node's
`node-role.kubernetes.io/control-plane:NoSchedule` taint — the selector alone
leaves the pod Pending forever with a message about taints, and a controller on a
WORKER answers nothing and looks exactly like a KServe fault. The node name is
DERIVED from the kind config's cluster name by `scripts/deploy_serving.sh` and the
values file is asserted against it (gotcha #52), so a rename fails at deploy time.
Accept: `GET localhost:8081/` -> 404 (route up, nothing behind it yet) AND
`GET /healthz` -> 200 (the controller's own endpoint — gotcha #70).

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
| Gold marts, whole (M1-S4; publish refactored M4-S5) | `make marts` (dbt build incl. its tests → publish to Postgres; `SKIP_PUBLISH=1` stops at DuckDB; `MARTS_MONTHS=YYYY-MM` scopes the fact table) | VERIFIED 2026-08-16 (M1-S4): `dbt build` PASS=39 (4 models, 34 data tests, 1 seed) in 3.24s; publish printed `COPY 56127878` for `trips_clean` — exactly the ingest total — plus 44,792 · 8 · 80 for the aggregates. Re-run is a full refresh into `<name>__staging` swapped in inside ONE transaction, so a reader never sees a half-loaded mart (watched live: the old `trips_clean` still served 56,127,878 rows while `trips_clean__staging` filled). **RE-VERIFIED 2026-08-18 (M4-S5) after the publish moved into `scripts/marts_publish.py`**: `dbt build` PASS=57, publish printed `COPY 56127878` again and **225.8 s** through the same `kubectl exec` transport — the delegation changed the caller, not the SQL. `make verify-m1` **GREEN 41/41** over it |
| Prove the mart tests can FAIL | `make marts-redteam` | VERIFIED 2026-08-16 (M1-S4) — see the story's transcript. Unions `seeds/redteam/` (999.5-min and 0.2-min trips) and **inverts the exit code**: a GREEN build with impossible trips in it means the tests are not testing, and the script fails saying so. Never publishes |
| Databases in the one Postgres (D-002) | `scripts/postgres_databases.sh` (step [5/7] of `make deploy-platform`; `DRY_RUN=1` previews) | VERIFIED 2026-08-16 (M1-S4) on the EXISTING volume (PGDATA initialised 15:47, `marts` created 17:44): run 1 `before = role absent, database absent` → `ok marts owner=marts`; run 2 `before = role present, database present`, nothing changed; `mlflow` no-op on both |
| BI seat, whole (M1-S5) | `make deploy-metabase` (namespace → secrets → app-db via D-002 → Deployment → host-route check → boards; `SKIP_BOARDS=1` deploys only) | VERIFIED 2026-08-17 (M1-S5) — see the commands' Done rows in HANDOFF (u) |
| Boards only (M1-S5) | `make boards` (`python scripts/metabase_boards.py`; `--verify` is the read-only twin `verify-m1` uses) | VERIFIED 2026-08-17 (M1-S5): converges 17 cards + 2 dashboards from `analytics/metabase/boards/*.json`; idempotent BY NAME (second run updates in place, ids unchanged) |
| Gate check M1 | `make verify-m1` | RE-VERIFIED 2026-08-17 (M2-S1, after the ingest change): **37 `ok` sub-checks, 0 FAIL, exit 0** — leg 1 now reports `16 output(s) byte-identical`, and that number is finally the number the proof HASHED (it used to `grep -c` every line ending in `yes` across the whole log, so it printed 16 for 8 files; pinned by a test). VERIFIED 2026-08-17 (M1-S5): 9 sections, **30 sub-checks GREEN, exit 0, measured 98s**; RED-TEAMED by `kubectl -n metabase scale --replicas=0` → exit 2 naming exactly the 2 BI checks, other 28 still green, then restored → GREEN again. **No fast mode, no skip flag** — leg 1 deletes and rebuilds ~1 GB of processed parquet, because byte-identity checked against data that was never re-derived is not a check |
| Scoring months, whole (M7-S1) | `make data-scoring` (ingest --scoring → duckdb → dvc add data/raw + the two scoring trees + push; `SKIP_DVC=1` stops before the pin) · `make ingest-scoring` is the ingest alone | VERIFIED 2026-08-20 (M7-S1): **15,712,062 → 15,413,352 rows, 1.901% rejected** across 2020-01..03, per-rule tables printed, one schema event per month (`airport_fee` present ahead of its `from_year` — gotcha #6 working). **2020-03 rejects 1.977% against a 0.10 ceiling**: structurally impeccable, statistically alien (3,007,687 raw rows against 2020-01's 6,405,008). It writes ONLY into `data/scoring/` and `data/scoring_rejected/` — `dvc status data/processed.dvc data/rejected.dvc` reads `up to date`, neither `.dvc` is modified in git, and `data/raw_manifest.json` is **+18/−0 with zero diff lines mentioning 2019**. A full second run left `data/scoring.dvc` up to date, i.e. **15.4M rows re-derived byte-identically**. Transcript: `docs/scoring_months_m7_transcripts.md` §1 |
| Analyst layer, now five reconciliations (M7-S1) | `make duckdb` | RE-VERIFIED 2026-08-20 (M7-S1): **16 views** (four added) and **five** reconciliations, exit 1 on any. New: scoring rows vs their reports (**15,413,352 == 15,413,352**) and the scoring sidecar per (month, rule) (**298,710 == 298,710, 30 pairs, 0 disagreements**). The settled numbers unmoved — 56,127,878 · 914,459 · 12,140,456. Both new legs RED-TEAMED in unit form: a truncated scoring month, and a report whose per-rule counts were shuffled **with its monthly total left correct** (the shape a per-month check cannot see). `trips_clean` still returns exactly `{train,val,test}`, by test |
| Ask a month what the contract says, writing nothing (M7-S1) | `make contract-probe PROBE_ARGS="--month YYYY-MM"` (**exit 0 = VALIDATED · 1 = REFUSED · 2 = the probe itself failed**; `--fixture`, `--rows`, `--out` for a tracked record) | VERIFIED 2026-08-20 (M7-S1): the REAL `yellow_tripdata_2025-01.parquet` (59,158,238 bytes, sha256 `9af277e4c0d3…`, 3,475,226 rows, 20 columns) came back **VALIDATED** with one schema event, `alias applied: 'Airport_fee' -> 'airport_fee'` — the year-aware contract's first encounter with real 2025 bytes, and a **SURPASS** over the blueprint's premise. It **acquires nothing**: the file lands in `data/probe/` (gitignored, not DVC-tracked) under its own manifest, `data/raw` and `data/raw_manifest.json` are untouched, and `--raw-dir data/raw` is refused outright. An AST test forbids it calling any writer or the ingest |
| Watch the contract REFUSE (M7-S1) | `make contract-probe-fixtures` (`PROBE_MONTH=`/`PROBE_ROWS=` are the levers) | VERIFIED 2026-08-20 (M7-S1): **PASSED — 3 refusal shapes, exit 1 each, nothing written.** `drop-required` (a field disappears) · `rename-required` (a field moves) · `unknown-column` (a field arrives) — all derived from the REAL 2025-01 file, all `SchemaEventError`, and all four data trees checked empty for the probed month afterwards. **The exit code is the assertion**: a refusal that exits 0 is a refusal a pipeline cannot hear. `rename-required` found a real defect — the message named the absent column and said nothing about the unknown one that had replaced it, because the missing branch raises before the unknown branch can run. Both are named now, with `aliases:` offered as the fix |
| Score the champion on the SCORING months (M7-S2) | `make predictions-scoring` (`SCORING_ARGS="--months YYYY-MM"` narrows to configured months and cannot introduce one; `--no-write` prints the numbers and publishes nothing) | VERIFIED 2026-08-20 (M7-S2): `models:/nyc-taxi-eta@champion -> version 2`, feature set `v2` read off the version's own tag, 24 columns matching the config. **The self-check ran first and MATCHED**: re-scoring the 2019-08 holdout (5,950,708 rows) measured **3.2403** against the version's own `gate_challenger_mae` of **3.2403** — a month with a known answer proving the loader, the feature path and the booster before a month with no known answer is written. Then **15,413,352 rows** across 2020-01..03: **KPI-14 3.0295 / 2.9802 / 3.3227 · KPI-15 83.226 / 83.768 / 80.569% · KPI-16 +0.2836 / −0.1703 / +0.5468**, every number from `taxi_mlops.training.evaluate` under MONITORING ids. `@champion` **2** before and after; `versions: ['1','2']` unchanged. Transcript: `docs/batch_inference_m7_transcripts.md` §1 |
| Analyst layer, now SIX reconciliations (M7-S2) | `make duckdb` | RE-VERIFIED 2026-08-20 (M7-S2): **17 views** (one added) and **six** reconciliations, exit 1 on any. New: batch predictions vs the scoring rows they claim to cover — **15,413,352 == 15,413,352**, per month, against the INGEST REPORT's `rows_out` and not against the predictions file. Settled numbers unmoved: 56,127,878 · 914,459 · 12,140,456 · 15,413,352. RED-TEAMED in unit form three ways: a **partly** scored month (3 rows of 7 — the failure that produces a plausible MAE) goes RED, an **unscored** month reads `pending` and stays GREEN, and a **mislabelled** month surfaces through the FULL OUTER JOIN as a month only the predictions know about |
| The monitoring mart (M7-S2) | `make marts` (`scoring_daily` is the sixth mart, full-refresh) | VERIFIED 2026-08-20 (M7-S2): `dbt build` **PASS=80** (was 57 — one model, two singular tests, the column tests), publish printed **`COPY 91`** (31+29+31 days). Read back OUT OF POSTGRES, not off the publish log: `sum(kpi_17_scored_trips)` = 6,279,806 + 6,185,309 + 2,948,237 = **15,413,352**, `model_version` **2**, **`versions_seen = 1`** on every month. Worst day KPI-14 **6.3693** (2020-03) against **3.5757** (2020-01) — the daily grain seeing what the monthly row averages away |
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
| Rehearse the M4 graph locally (M4-S1) | `make pipeline-local MONTH=2019-01` (`uv run python pipelines/tasks.py --month …`; `--gate` exists only so the F-008 refusal can be watched) | VERIFIED 2026-08-18 (M4-S1): six stages composed on one month, **exit 0** — ingest 7,584,656/7,696,617 rows (1.4547% rejected, tracked tree unchanged in git) · validate re-read the parquet through the 2019 output contract, 20 columns · build_features set **v2**, 24 columns · train `lightgbm-v1` run `27aa90597f61…`, 265.8 s, sampled=True judged=False · evaluate reported the ONE evaluator's numbers · register **`decision=NO_VERDICT promoted=False`, CLI exit-code class 3** and `@champion is version 2 — read, never written`. **No orchestrator, no verdict, no result** — one train month against the champion's six (F-008). Transcript: `docs/pipeline_graph_m4.md` §4 |
| The serving PLATFORM (M5-S1) | `make deploy-serving` (`scripts/deploy_serving.sh`; `DRY_RUN=1` mutates NOTHING, helm included) — ingress-nginx + cert-manager + KServe Standard. **Installs NO model** | VERIFIED 2026-08-19 (M5-S1): four releases at REVISION 1 in **3m13s** — `ingress-nginx 4.15.1` · `cert-manager v1.21.1` · `kserve-crd`/`kserve-resources v0.20.0` — the controller landing on **mlops-taxi-control-plane** (the node whose port 80 kind publishes as 8081; the name is DERIVED from the kind config and the values file asserted against it), `serving-cert True` issued by cert-manager, and `defaultDeploymentMode: RawDeployment` **read back off the live `inferenceservice-config` ConfigMap**, not off the values submitted. **Idempotent re-run = REVISION 2 with every pod 4m44s/3m35s/2m35s old and unrestarted** (the M4-S2 shape). Six KServe CRDs register on **Kubernetes v1.36.1** — risk R1 did not materialise, ADR-004's mlserver fallback armed and unspent. Accept: `GET localhost:8081/` -> **404** (the pass: route up, nothing behind it) AND `GET /healthz` -> **200**. Its FIRST accept check went RED over a perfectly good install by demanding a `Server:` header ingress-nginx suppresses — **gotcha #70**. `DRY_RUN=1` verified to leave `helm list -A` and the namespace list untouched. Transcript: `docs/serving_m5.md` §2 |
| The champion ON THE WIRE (M5-S2) | `make serve` (`scripts/deploy_champion.sh`; `DRY_RUN=1` mutates NOTHING) — read-only MinIO identity + our ClusterServingRuntime + an InferenceService whose `storageUri` is RESOLVED from the alias | VERIFIED 2026-08-19 (M5-S2): InferenceService **Ready True**, predictor on `mlops-taxi-worker2`, 0 restarts; the accept check is a **PREDICTION** (gotcha #59) — `2019-07-04T09:15:00, zone 132 -> 48 -> 39.0019 minutes` with mlserver stamping **`model_version: "2"`** on the response itself, matching the locally-loaded champion **bit for bit** (absolute delta 0.000e+00, ONE row — the 1e-6 gate is M5-S3's). **Idempotent re-run = `unchanged`/`configured`, the SAME pod uid, 0 restarts, 2m1s old** (the M4-S2 shape). `@champion` version **2** read before AND after, unmoved (a move exits 2). Its first run 403'd on `HeadBucket` because MinIO's built-in `readonly` omits `s3:ListBucket`; its third printed a passing accept check against **the pod it was replacing**, because the InferenceService's Ready condition is satisfied by the predecessor (gotcha #71) — `rollout status` now runs first. Transcript: `docs/champion_on_the_wire_m5.md` §5 |
| Ask the live endpoint for a quote (M5-S2) | `make quote` (`QUOTE_ARGS="--at YYYY-MM-DDTHH:MM:SS --pu N --do N"`; **exit 0 = quoted · 2 = REFUSED by the typed boundary · 1 = anything else**) | VERIFIED 2026-08-19 (M5-S2): a 2019 request quotes, a **2026** request quotes where it used to raise (F-019's table half), and a **2031** request returns `REFUSED (422) … covers through 2030 … Extend the table: make holidays HOLIDAYS_TO=2031`, exit 2 (F-019's typed half). Builds features through the ONE `features/` path — it reimplements nothing, pinned by an AST test |
| THE parity test (M5-S3) | `make parity` (`PARITY_ARGS="--tolerance …"`; a READER — no deploy, no registry write, seconds) | VERIFIED 2026-08-19 (M5-S3): **`max \|offline − online\| = 0.000e+00` minutes over 16 hazard rows against a 1e-6 bar** — identical, not merely within tolerance, on every row including the two with no geometry at all. ONE matrix built through `taxi_mlops.features` and scored TWICE (locally-loaded champion vs the live endpoint), so the delta is attributable to the model bytes + runtime + wire and NOT to two feature builds. Rows are declared and committed, each naming its hazard: airports (JFK/LGA/EWR), an OD pair unseen in train (`55 -> 148`, 6 in test / 0 in train), the 100–120 min tail, midnight and week seams, passenger_count 0 and 6, a 2026 date (F-019's extension), and M5-S2's exact spot-check row — which reproduces at **39.001937154**. `@champion` version 2 read, never written. Transcript: `docs/parity_m5.md` §5.1 |
| One stated load shape (M5-S4) | `make load LOAD_ARGS="--rate 4 --seconds 60 --concurrency 8"` (open-loop; a READER — it POSTs and it times, and it does not judge: the bar lives in the M5 gate) | VERIFIED 2026-08-19 (M5-S4): **p50 17.2 · p95 104.2 · p99 107.2 · max 115.4 ms, 240/240 ok** at 4 req/s for 60 s, concurrency 8, hazard mix, achieved 4.02 req/s. `latency_ms` (scheduled→response) and `service_ms` (sent→response) differ by 0.1 ms — the client kept up, and the run says so rather than leaving it to be assumed. Every response carries `model_version: 2` |
| Ramp → headline p95 → kill the predictor mid-load (M5-S4) | `make load-drill` (`DRILL_ARGS="--ramp … --seconds … --kill-at …"`; `--skip-selfheal` is the ~40 s probe that kills nothing) | VERIFIED 2026-08-19 (M5-S4): **GREEN, 7/7 self-heal checks.** Ramp measured the ceiling (6 req/s = 96% of the 2-core limit, 8 req/s = 101% with p50 18→115 ms) and CHOSE 4 req/s; headline as above with **1.31 mean cores / 0.326 core-s per request / 236 MiB**; kill at T+25 s of 180 s → **14.53 s unavailable**, 58 failed requests (56×503, 2×502), then **559 with 0 errors**, a **different pod UID on a different node**, same model version throughout. Prediction written BEFORE the kill. **Its first attempt went RED at the CPU ceiling and is kept unedited** in `attempt1-at-the-ceiling/` — gotchas #74/#75 |
| Stop the endpoint and start it again, TIMED (M5-S5) | `make stop-start-drill` (`uv run python scripts/serving_stop_start_rehearsal.py`) | VERIFIED 2026-08-19 (M5-S5): the runbook's own §3 commands, RUN — `serving.kserve.io/stop=true` → the route stopped answering in **3.12 s** (`Stopped` False→True, `spec.replicas` **absent**, the old pod lingering as `Completed`), then `serving.kserve.io/stop-` → **answering again 18.24 s later** on a NEW pod (`…-qrd6f` → `…-xj2q6`). It REFUSES to run against a service that is already down (a stop drill against a stopped service measures nothing) and removes its own annotation. Record: `automation/runs/m5-s5/stop-start.json`. It is a DRILL — ~20 s of deliberate outage — and the gate only ever READS what it writes |
| Gate check M5 | `make verify-m5` | VERIFIED 2026-08-19 (M5-S5): **GREEN 49/49 sub-checks in 7 sections, 5.762 s, exit 0** — the route (`/healthz` 200, controller on the node DERIVED from the kind config) + KServe's mode read off the live ConfigMap and PARSED (not grepped) out of the values file · the champion on the wire, **asked for ONE prediction** whose `model_version` equals what the alias resolves to and whose value reproduces the parity record at **0.000e+00**, plus the **half-rollback coherence check** (F-032) · parity replayed against `parity.TOLERANCE_MINUTES` and `parity.HAZARDS` **on disk** · the load shape with its rate/window/concurrency/mix, the client's achieved rate, and the 90%-CPU clause (gotcha #74) · self-heal with the **outage re-derived from its anchors** (`40.03 − 25.5 = 14.53`; the error-span anchor would say 14.251 — gotcha #75) and the stop/start rehearsal · the runbook's every quoted number checked against the record it cites and every `make` target against the Makefile · the PRR's four boxes each carrying evidence · the alias equal to the M3 bake-off's recorded winner, every version carrying a gate verdict, and `src/taxi_mlops/serving/` unable to CALL a registry-mutating verb (ast, not grep). **Re-runs nothing expensive and mints nothing** (pinned by `tests/unit/test_verify_m5.py`), no skip flag, no fast mode. Transcript: `docs/verify_m5_transcripts.md` §1 |
| Prove the M5 gate can go RED | `make verify-m5-redteam` (`bash scripts/verify_m5_redteam.sh`) | VERIFIED 2026-08-19 (M5-S5): rewrites ONE number in `automation/runs/m5-load/selfheal.json` — `recovery.outage_seconds` **14.53 → 14.251**, taken from the record's OWN `error_window.span_s`, i.e. gotcha #75's mistake re-made and wrong by 0.28 s — leaving the anchors, the pod uids and all 7 recorded checks untouched → **RED exit 1 with 2 FAILs from TWO DIFFERENT ARTIFACTS**: the record stops reconciling with its own anchors, AND the runbook quotes a number no record holds. **47 sub-check lines still ran and passed**; restored under an EXIT trap and verified by sha256 (`f1712acf9f80…` before and after) with `git status` clean → **GREEN again**. Touches no pod, no image, no MLflow run, no registry version, no alias |
| Prove the parity test can go RED (M5-S3) | `make parity-redteam` (`bash scripts/parity_redteam.sh`) | VERIFIED 2026-08-19 (M5-S3): **PASSED, 7 checks, 0 failures.** Arm A sends every feature under its own name and dtype carrying its NEIGHBOUR's values — every input individually valid, only the pairing wrong → **max delta 4.210e+01 minutes** (a 48-minute trip quoted at 6) and the verdict names it. Arm B loads registry version **1** offline (a READ; moving an alias would be a mutation and a red team never moves the pointer it checks) while the wire serves the champion → refused at the feature-set guard BEFORE a number exists, because v1 eats 5 columns and v2 eats 24. Neither arm deploys, restarts or promotes; `@champion` is version 2 before and after and the untampered run is GREEN again at the end. **Its first arm A went green under its own tampering — that is F-031/gotcha #73** |
| Re-derive the holiday table (M5-S2, F-019) | `make holidays` (`HOLIDAYS_TO=YYYY` moves the horizon; `--year 2019 --stdout` is the reproduction check) | VERIFIED 2026-08-19 (M5-S2): **146 rows, 2019..2030, 16 observed-day rows**, and re-deriving 2019 alone reproduces the ten hand-written rows **byte for byte** (`diff` silent) — those rows predate this script by two milestones, so agreement is evidence about the RULES, Juneteenth included (federal from 2021, correctly absent from 2019). Idempotent; the human `note` column is preserved by date. 136 insertions, 0 deletions — and the holiday AND near-holiday sets inside 2019-01..08 are asserted unchanged, because a near-day can arrive from another year entirely |
| Back the platform up (M4-S2) | `make backup` (`scripts/platform_backup.sh` + `scripts/backup_minio.py`; `DRY_RUN=1` enumerates and sizes, writes nothing; `BACKUP_ROOT=` moves the destination) | VERIFIED 2026-08-18 (M4-S2): **5 databases enumerated FROM THE SERVER** — marts 1.2GiB/210s · metabase 295.6KiB · mlflow 53.9KiB · optuna 27.0KiB · postgres 389B — plus **105 MinIO objects / 352.3 MiB**, **1.5GiB total**, into `/home/longt/dvc-remote/nyc-taxi-platform-backups/2026-08-18T06-02-29Z/`. Every dump verified host-side by `gzip -t` over every byte AND pg_dump's own completion marker; the object mirror verified by object count AND byte total. **Both dump legs RED-TEAMED first against a deliberately truncated copy of the real 1.2GiB file** (`gzip -t` rc 1, marker rc 1). **RESTORE IS SCRATCH-REHEARSED from 2026-08-19 (M6-S5) and no further** — said in the header, in the `MANIFEST.txt` text and in the ledger; a full restore over a dead platform is still un-rehearsed. Same-disk limit, identical to the DVC remote's |
| Rehearse the restore (M6-S5) | `make restore-drill` (`RESTORE_ARGS="--backup <dir> --keep"`) — the newest backup's three SMALL dumps into `<db>_restore_drill` scratch databases + a scratch MinIO bucket, then dropped | VERIFIED 2026-08-19 (M6-S5): **GREEN 17/17.** mlflow **2.34 s** · optuna **0.78 s** · metabase **7.29 s** through `zcat \| kubectl exec -i psql -v ON_ERROR_STOP=1` (the `make marts` transport, because nothing of ours publishes 5432 and a restore path that needs a port opened is one nobody can run in an incident). Every counted table equals the LIVE database (mlflow experiments=8 runs=101 registered_models=1 model_versions=2 · optuna studies=5 trials=59 · metabase report_card=67 report_dashboard=4 core_user=2), the restored registry carries the same `champion\|2` pointer, and the restored studies carry the trial counts `automation/runs/m3s4/sniper-*.json` recorded (9 and 21) — **a second witness that is not the live database**, because live-vs-restored alone is also what restoring the wrong backup into the wrong place would show. Objects: `flyte-data` restored **WHOLE** (184 objects / 783,327 bytes, 31.7 s) into a scratch bucket and one MLflow `MLmodel` **byte-identical to the live object by sha256**. The live database list and bucket list are unchanged and **no scratch survives**. **`marts` is deliberately excluded** (1.2 GiB of the 1.6 GiB backup, and the ONE database provably rebuildable from DVC pins). Its FIRST run went RED on a check that was wrong, not on a restore that was — see the story section |
| Port pre-check, now holder-aware (F-021, M4-S2) | `make ports` | RE-VERIFIED 2026-08-18 (M4-S2) against the LIVE cluster: `6 port(s) held by US — the 'mlops-taxi' cluster is up, which is expected`, each naming port, purpose and `-> container mlops-taxi-control-plane`, then `OK — 10 required port(s): 4 free, 6 held by us, 0 foreign.` **exit 0** — where it used to refuse and advise stopping the stack that holds the registry. The foreign refusal is UNSOFTENED: two unit tests use the same bound port and the same fake `docker ps`, differing only in the container NAME (`mlops-taxi-control-plane` → exit 0 · `somebody-elses-stack-web-1` → exit 2), and M0-S2's fake-listener red-team (no docker shim) still goes red |
| Flyte on the cluster (M4-S2) | `make deploy-flyte` (`scripts/deploy_flyte.sh`; `DRY_RUN=1` mutates NOTHING, helm included) | VERIFIED 2026-08-18 (M4-S2): `STATUS: deployed REVISION: 2`, all three deployments rolled out, `[pg-db] flyte: before = role absent, database absent` → `ok flyte owner=flyte` (`5 database(s) converged`). **Idempotence proved by pod AGE**: the re-run reported every deployment rolled out while all three pods were **17 minutes old** — a clean upgrade that restarted nothing. First install FAILED `context deadline exceeded` with all pods healthy (the 99 MB console image took **9m49s** to pull); `--wait` is now 20m with that measurement written beside it. Self-sufficient (re-runs namespaces/secrets/D-002/MinIO, the M1-S5 rule). No secret on a command line — mode-600 overlay deleted on EXIT. Cluster never went down |
| Reach Flyte from the host (M4-S2) | `make flyte-console` (blocking forward) · `bash scripts/flyte_console.sh --check` (one-shot, tears the tunnel down) | VERIFIED 2026-08-18 (M4-S2): `ok  API answers: GET /healthz -> 200 (svc svc/flyte-flyte-binary-http:8090)`. The path was ASKED of the server, not remembered — `/healthcheck` (the 1.x path) returns 404, `/healthz` and `/readyz` return 200. **A port-forward, not a declared route, and that is recorded**: no hostPort exists for Flyte, adding one means a rebuild the statefulness law forbids, and there is no ingress controller until KServe at M5 — so the browser console is deliberately NOT forwarded (same-origin SPA; it would render and then fail every request) |
| Hello-workflow on the cluster (M4-S2, unblocked M4-S4) | `make flyte-hello` (`scripts/flyte_hello.sh`) | **VERIFIED 2026-08-18 (M4-S4) — F-023 CLOSED.** `ActionOutputs(o0="HELLO CROSSTOWN FROM A FLYTE TASK")`, three pods `Completed` (`a0` plus two child actions), the second task's input being the first's output **through the `flyte-data` bucket** — the seam test, not a pod-ran test. It needed the split-horizon fix (`signedUrl.stowConfigOverride`) AND two fixes to the CHECK itself: `flyte run` returns at LAUNCH, so `--follow` is what makes it an acceptance test; and `--follow` streams LOGS while these tasks RETURN a value, so the verdict is read with `flyte get io --outputs-only`. Grepping the follow output would have failed a perfect run and passed a task that merely printed the string. ~3 min; it is the cheapest check that Flyte itself is healthy |
| Gate check M2 / M3, re-run after the F-018 repair | `make verify-m2` · `make verify-m3` | RE-VERIFIED 2026-08-18 (M4-S1): **GREEN 55/55** and **GREEN 46/46**, both exit 0, **neither verify script touched by the diff** — including verify-m3 §5, which replays the bake-off's five recorded verdicts through `gate.decide` as it exists on disk, and verify-m2 §2, which parses the OLD holdout line out of the committed promotion transcripts (the repaired `verdict_lines` keeps the shape they are parsed with, on both forms of the sentence, pinned by a test) |
| Task image: build + reach every node (M4-S3) | `make image-load` (`make image-build` stops before the cluster; `DRY_RUN=1` previews) | VERIFIED 2026-08-18 (M4-S3): `taxi-mlops-pipeline:<git-sha>`, **737 MiB content / ~1,898 MB unpacked**, built in 352s, `kind load` in 26s, then read back with `crictl` on **all 3 nodes** (`ok mlops-taxi-{worker2,control-plane,worker}: sha256:eb6feb2c08ee…`), manifest written to `automation/runs/m4-image/image.json`. `DRY_RUN=1` prints the exact tag and `nothing was built, nothing was loaded`. D-001's decision (kind load, registry pattern deferred to the next sanctioned rebuild) is in `docker/DECISION-D001-image-delivery.md` |
| Prove the image runs OUR code and that D-004 is dead (M4-S3) | `make image-smoke` (`SKIP_UNIT=1` is a debugging lever that counts as a FAILURE, never a pass) | VERIFIED 2026-08-18 (M4-S3): **GREEN 10/10** — `libgomp1 14.2.0-19 install ok installed` · `libgomp.so.1 => /lib/x86_64-linux-gnu/libgomp.so.1` · `openmp_status() -> (True, 'system libgomp.so.1')` first line · no `[openmp]` line anywhere · lightgbm 4.7.0 / xgboost 3.4.1 / flaml 2.6.0 / pandas 3.0.5 / mlflow 3.15.1 / flyte all import clean · **215 host / 215 image packages, 0 disagreements** · `tests/unit` **471 passed, 6 skipped IN-IMAGE** · `validate(2019-01)` → **7,584,656 rows, 20 columns** through the output contract · no shim directory. Its first two runs were RED for the verifier's own reasons and once for a real `.dockerignore` bug — see `docs/task_image_m4.md` §5 |
| Prove the D-004 checks can go RED (M4-S3) | `make image-smoke-redteam` | VERIFIED 2026-08-18 (M4-S3): masks `/lib/x86_64-linux-gnu/libgomp.so.1` with an **empty file in ONE `--rm` container** → the probe flips to `(False, 'not loadable yet; a vendored copy exists at …scikit_learn.libs/libgomp-e985bcbb.so.1.0.0')`, the shim **announces itself**, `/app/.venv/lib/openmp` **appears**, F-024's `-c` refusal is asserted, and a fresh container from the same image reads `absent` again. Exit code inverted like `marts-redteam`'s: a check that stays green under the mask FAILS the drill. Touches no image, no node, no cluster |
| Stage the data a task pod reads (M4-S4) | `make stage-data` (`scripts/stage_pipeline_data.sh`; `RESTAGE=1` forces the re-stream, `DRY_RUN=1` measures and transfers nothing) | VERIFIED 2026-08-18 (M4-S4): **1.8G across raw/processed/rejected** onto PVC `taxi-data` by `tar | kubectl exec -i` (the M1-S4 shape — the kind nodes cannot see the host FS and `extraMounts` is a config edit, i.e. a rebuild), then checked by per-tree **FILE COUNTS** — `raw: 8 == 8 · processed: 16 == 16 · rejected: 8 == 8` — because a size check passes on a tree that arrived truncated. The stager pod is DELETED afterwards (a pod holding an RWO volume open is one day the reason a task cannot schedule) while the PVC and its data remain. `DRY_RUN=1` prints the source size and `nothing was applied, nothing was transferred`. Re-run skips on size unless `RESTAGE=1`; it never DELETES, for `postgres_databases.sh`'s reason |
| The six stages on-cluster (M4-S4) | `make pipeline MONTH=YYYY-MM` (`scripts/run_pipeline.sh`; `TRAIN_MONTHS=…` makes it a SAMPLED, verdict-free smoke — F-008) | **VERIFIED SAMPLED 2026-08-18 (M4-S4); the FULL-DATA run is NOT done and is M4-S5's inheritance.** Run `r5kzpr785rt8m6tn9b7l`: ingest **7,696,617 → 7,584,656 rows, 1.4547% rejected** (M4-S1's host rehearsal reproduced TO THE ROW, in a container) · validate 20 columns through the output contract · features set **v2**, 24 features · train `lightgbm-v1` run `e17ce5846aaf…` in **869.7 s** · evaluate reporting the ONE evaluator's numbers · register **`decision=NO_VERDICT promoted=false`** as DATA. `@champion` read BEFORE and AFTER by the script itself: **2 → 2**, and a move exits 2. **Its assertion is POSITIVE and had to be**: `flyte run --follow` exits 0 for a FAILED run, so the check is that the run's OUTPUTS carry a `"decision"` — the exit-code version printed `ok … six stages on-cluster` over a run that died on `ErrImagePull` |
| Prove the rerun REUSED the first run (M4-S4) | `make pipeline-cache-drill MONTH=YYYY-MM` (`DRILL_STAGE=ingest` is the ~40 s mechanism probe; `DRILL_MAX_RATIO`/`DRILL_MAX_STAGE_RATIO` are the two clocks' bars) | VERIFIED 2026-08-18 (M4-S4, second session): **GREEN 19/19**, run 1 `r56p9p7qwfsqgh6qgrlw` populating all five cacheable stages, run 2 `rbbvfb5mhfgz8cngx9rn` hitting all five — **train 1935.2 s -> 0.1 s**, executed stages **1966.9 s -> 3.2 s (0.2%)**, wall-clock **1974 s -> 11 s (0.6%)**, **MLflow 16 -> 16 across run 2** (and 12 -> 16 across run 1, so the saving is real), `@champion` **2** after both. Three independent systems, ranked: the control plane's `cache_status` is the CLAIM, the clock CORROBORATES, MLflow is the one that could catch a lie. It refuses to be green if run 1 executed nothing — a drill comparing two reruns can show no saving |
| Prove the pipeline survives losing a pod (M4-S5) | `make pipeline-kill-drill` (`MONTH=` picks an UNSEEN month — a cached stage runs in no pod; `KILL_STAGE=`/`KILL_AFTER=` are the levers; ~20 min, **run it detached**) | VERIFIED 2026-08-18 (M4-S5): **GREEN, 9 checks**, run `rb2cxpmsksx489qjbn5b` on 2019-03, sampled so verdict-free (F-008). Phase 0 first: a task that always raises settles at **attempt index 3** with `retries=2` and the run **FAILS** — the declared budget is real and finite, measured in ~90 s in front of the expensive leg. Then the kill: `train`'s pod deleted 120 s into its work, **a different pod object (uid `9d8b05a3…` vs `1223e07d…`) 31 seconds later**, `train` **939.8 s** against ~870 undisturbed, all six stages SUCCEEDED, verdict object produced, `@champion` **2** before and after. **Its prediction is written to disk BEFORE the kill and the first one was WRONG** (it expected a `…-1` pod; the plugin recreates the same attempt under the same name) — kept in `automation/runs/m4-kill/attempt1-prediction-wrong/`, and the assertion is now identity rather than name. Refuses to be green if the target stage came back `CACHE_HIT` |
| The marts tail task on-cluster (M4-S5, D-003) | `make pipeline MONTH=YYYY-MM` — the tail is stage **7** and ON by default; `PUBLISH_MARTS=0` drops it (both orchestrator drills do); `make pipeline-local PIPELINE_LOCAL_ARGS=--publish` is the host rehearsal, opt-in | VERIFIED 2026-08-18 (M4-S5 leg 2): run `rw98pj84z4jh5ldqrxqp`, sampled so verdict-free (F-008, `register` returned `NO_VERDICT` as data). `publish_marts` SUCCEEDED in **90.6 s of an 886.6 s run (10.2%)**: in-pod analyst rebuild → `dbt build` **PASS=57 in 9.96 s** → publish **71.9 s** as `marts@postgres.platform.svc.cluster.local` (**against 82.7 s host-side** — a pod's direct TCP beats `kubectl exec` by ~13%). **2019-01 month-scoped, all 8 months reconciled `yes`**, `@champion` **2 → 2** read by the runner before and after. First on-cluster attempt green, because §14 had already measured the two questions that usually cost the attempts |
| D-003: what a publish costs the volume | `make marts-peak` (full refresh) · `make marts-peak MARTS_MONTHS=YYYY-MM` (scoped) — samples `pg_database_size('marts')` and PGDATA every 5 s around any publish | VERIFIED 2026-08-18 (M4-S5): **full refresh 228.2 s, 15.33 → 27.96 → 13.48 GiB (peak/end 2.075×), PGDATA peak 204.62 GiB**; **month-scoped 2019-03 (7,753,921 rows) 82.7 s, peak 15.33 GiB**. **Peak −45.2%, wall −63.8%** — and M1-S4's remembered ~23 GB was optimistic. It MEASURES and does not judge: no threshold lives in a probe. Summaries in `automation/runs/m4-marts/*.json`, with the sample interval recorded because it bounds the peak's resolution |
| Read a run's stages without hand-rolling a forward (M4-S5) | `make flyte-actions RUN=<run-name>` (`ACTIONS_ARGS=--json`) | VERIFIED 2026-08-18 (M4-S5): printed all 8 actions of `rw98pj84z4jh5ldqrxqp` with phase, `cache_status`, duration and **`attempts: 1`** (F-027's fix, visible). It is the same seven port-forward lines `run_pipeline.sh` and both drills each carried inline, once — on port **8092**, so a reader cannot steal the port of a run in flight |
| What a Flyte run's actions actually did (M4-S4) | `uv run python scripts/flyte_run_actions.py <run> [--json]` (needs a route; the drill and `run_pipeline.sh` stand one up) | VERIFIED 2026-08-18 (M4-S4, second session): recovered the full-data run's per-stage detail that `--follow` never logged — **six stages, 1909.7 s, fit 1874.7 s, everything else 34.6 s**. Reads `cache_status`, which the CLI does not render. A READER: pinned by a test that it calls nothing which launches, aborts or deletes, because `verify-m4` is meant to reuse it |
| Gate check M4 | `make verify-m4` | VERIFIED 2026-08-19 (M4-S5 leg 3): **GREEN 39/39, exit 0**, 7 sections in seconds — control plane `/healthz` 200 + 3 Deployments available + the PodTemplate APPLIED with its container named `default` + its PVC Bound · the image on **all 3 nodes** by each node's own `crictl`, and **D-004 re-observed dead INSIDE the container** (`openmp: system libgomp.so.1` first line, no `[openmp]` anywhere) · all 7 stages of `tasks.STAGES` wrapped (AST), 29 actions across 4 recorded runs all SUCCEEDED, one run covering the whole graph, **28 MLflow runs all FINISHED** · the RECORDED cache drill (gotcha #66 — never the newest run): 5/5 `CACHE_HIT`, 1966.9 s → 3.2 s, MLflow 16 → 16, **and the two witnesses agree** · the kill drill: different pod **uid**, ONE attempt, and the probe at attempt index 3 against a declared budget of 2 · `publish_marts` last, CACHE_DISABLED, **8 months reconciled live, 56,127,878 rows, republishing nothing** · **none of the 28 pipeline runs is a registry version**. **RE-RUNS NOTHING** (no pipeline, no drill, no fit, no publish — pinned by `tests/unit/test_verify_m4.py`), no skip flag, no fast mode. Transcript: `docs/verify_m4_transcripts.md` §1 |
| Prove the M4 gate can go RED | `make verify-m4-redteam` (`bash scripts/verify_m4_redteam.sh`) | VERIFIED 2026-08-19 (M4-S5 leg 3): flips **ONE field** — run 2's `train` from `CACHE_HIT` to `CACHE_POPULATED` in `automation/runs/m4-cache/cache_drill.json`, leaving duration (140 ms), phase and the MLflow counts (16 → 16) untouched, i.e. a record that is internally well-formed and still describes a green seven-stage run → **RED exit 1 with 2 FAILs**: the CLAIM leg names `train`, and the **CROSS-SYSTEM leg fires** (`the two witnesses CONTRADICT each other … MLflow minted 0 run(s)`) — the leg a gate reading only `cache_status` would not have had. **37 of 39 sub-checks still ran and passed**; restored from a byte copy under an EXIT trap and verified by sha256 (`beb10ab49fb0…` before and after) → **GREEN 39/39**. The target is CHOSEN from the record (the cached stage that cost run 1 most), never typed. Touches no pod, no image, no MLflow run, no registry version, no mart row |
| The monitoring stack (M6-S1) | `make deploy-monitoring` (`scripts/deploy_monitoring.sh`; `DRY_RUN=1` mutates NOTHING, helm included) — Prometheus + Alertmanager + kube-state-metrics + Grafana through the EXISTING 8081 route. **Installs no alert rule and no threshold** | VERIFIED 2026-08-19 (M6-S1): `prometheus 29.27.0` and `grafana 10.5.15` deployed into `monitoring`; the accept check **GREEN 10/10** with targets `kserve-predictors` 1/1, `kubernetes-service-endpoints` 6/6, `kubernetes-nodes-cadvisor` 3/3 (**none permanently red**). **Idempotent re-run = every pod 9–11 min old, 0 restarts** (the M4-S2 shape) — and the Prometheus pod does not restart when its config changes at all (configmap-reload sidecar). `DRY_RUN=1` verified to leave `helm list -A` untouched. Its wire change is the ingress-nginx metrics roll — **F-033**, measured at **15.0 s** — and `make verify-m5` was re-run **GREEN 49/49** after it. Transcript: `docs/monitoring_m6.md` |
| Prove a rider's request becomes a number (M6-S1) | `make monitoring-accept` (`ACCEPT_ARGS=--json` writes the record) — the accept twin, re-runnable, ~1 min | VERIFIED 2026-08-19 (M6-S1): **GREEN 10/10.** It is not a target list (gotcha #59): it reads the inference counter, sends ONE real quote through the live endpoint (`2019-07-04T09:15:00 zone 132 -> 48 -> 39.0019 minutes` — the parity record's own value), waits 40 s for a scrape, and requires the counter to move (**17 → 18**). Then it parses **every panel's PromQL out of `analytics/grafana/dashboards/serving.json`** and executes all 11 against Prometheus, requiring live series from each — **an empty panel is a FAILURE**, because it is indistinguishable from a quiet system (gotcha #78). Its first run was green over three real defects |
| Ask the predictor where its metrics really are (M6-S1) | `make probe-mlserver-metrics` | VERIFIED 2026-08-19 (M6-S1, **F-034**): `:8082/metrics -> HTTP 200, 119 lines, 24 series` · `:8080/metrics -> HTTP 404` — against KServe's own pod annotation `prometheus.kserve.io/port: "8080"`. Prints one WHOLE sample per serving-relevant series, because the LABELS are what a board and an alert are written against; that is how `status_code` (the 5xx/422 split) and `version="None"` (no model version in any mlserver metric) were both found before a rule was written |
| Validate the alert rules (M6-S2) | `make alert-rules` (`scripts/render_alert_rules.py --check`; without `--check` it prints the helm values overlay the deploy passes) | VERIFIED 2026-08-19 (M6-S2): **7 rule(s) validated** across 6 signal ids, each printed with its `for:` and severity. It REFUSES a rule with no `expr`, no `labels.severity`, an unknown A-id or no `annotations.why` — *a threshold whose argument is not written beside it is a number nobody can review* — and it fails if the implemented-signal set and the documented absences (A-4, A-3's client half — F-035) ever disagree. It runs INSIDE `deploy_monitoring.sh` before helm, so a malformed rules file fails there instead of becoming a successful upgrade over a Prometheus with no rules. Read back off `/api/v1/rules`: 7 loaded, `health=ok`, all `inactive` |
| Fire real alerts, prediction FIRST (M6-S2) | `make alert-fire-drill` (`DRILL_ARGS="--dry-run"` is the ~5 s preflight that writes the prediction and injects nothing; ~8 min, no outage) | VERIFIED 2026-08-19 (M6-S2): **GREEN 11/11.** Prediction written to `automation/runs/m6-slo/alert-fire-prediction.json` BEFORE anything was injected (the M4-S5/M5-S4 discipline). ONE injection of two shapes the endpoint really produces — **662 × 422** (malformed body, F-030's class) and **661 × 500** (signature-refused body, F-032's half-rollback class) — fired **A-3 at T+150.5 s (predicted 150)** then **A-2 at T+330.6 s (predicted 330)**, in the predicted order, both held by **Alertmanager**, all **five must-not-fire alerts inactive**, an ordinary quote answering **39.0019 minutes** mid-injection, and both back to `inactive` **315.1 s** after the stop. Deletes nothing, scales nothing, promotes nothing (pinned by an AST test); `@champion` read, never written |
| Write the CPU-resize record from the runs (M6-S2) | `uv run python scripts/cpu_request_resize_record.py` | VERIFIED 2026-08-19 (M6-S2): derives the whole before/after comparison from the two tracked `make load` records and the availability probe rather than from typed numbers (the `error_memo_numbers.py` precedent). Prints `before p50 29.373 p95 84.437 p99 433.686 max 692.867` · `after p50 29.548 p95 112.677 p99 118.945 max 142.904` · `over the 250 ms SLO target: before >= 2/240, after >= 0/240` · `applying it cost the route 0.5 s` |
| Measure what a wire change costs the route (M6-S1) | `uv run python scripts/route_availability_probe.py --seconds N --rate 2 --out <path> --label "…"` | VERIFIED 2026-08-19 (M6-S1): open-loop, one sample due every 1/rate seconds regardless of whether the last returned; **outage anchored first-failure → first-success** (gotcha #75) with the raw per-sample log kept so a reader can re-derive it differently. Observed **15.0 s / 30 failed of 600** across the ingress metrics roll — and **840/840 ok with `outage=None`** across the deadlocked rollout that never replaced anything, which is exactly why pod AGE and not the probe is what proves a rollout happened |
| The v1 shadow on the wire (M6-S3) | `make shadow` (`DRY_RUN=1` previews, `TEARDOWN=1` removes, `SHADOW_VERSION=N` picks the version) | VERIFIED 2026-08-19 (M6-S3): `models:/nyc-taxi-eta/1 -> run 3adee05a…`, feature set **`v1` read from the version's OWN tag**, `s3://mlflow-artifacts/2/models/m-4a4e7bdc…/artifacts` downloaded, predictor Ready on `mlops-taxi-worker2`, and the accept check is a **PREDICTION in the shadow's own 5-column matrix** — `2019-07-04T09:15:00, zone 132 -> 48 -> 64.1043 minutes`, `model_version: 1`, against the champion's 39.0019 for the identical request. `@champion` version **2** read before AND after (a move exits 2), and the champion re-quoted on its own host at the end. **TEARDOWN proven**: deleting the isvc took its Deployment, Service and Ingress with it while the champion's three objects stayed at 9h age — which is the evidence that the shadow deploy never touched it. Its first run 404'd over a healthy service because the ISVC reports Ready before nginx has loaded the generated Ingress — **F-037**, fixed with a third wait leg that asks the route |
| Dual-send the shadow, write the disagreement table (M6-S3) | `make shadow-run` (`SHADOW_ARGS="--rows-per-segment N"`; a READER — deploys nothing, moves no alias) | VERIFIED 2026-08-19 (M6-S3): **1,016 rows** (250 each ordinary/airport/no-geometry/long-trip + parity's 16 hazards) sent to BOTH endpoints, each matrix built through the ONE feature path — v1's 5 columns, v2's 24. Champion MAE **8.61** vs shadow **8.93**, champion closer on **54.4%**; long_trip mean \|d\| **2.65** max **36.42** champion closer **63.6%**; **airport 5.97 vs 5.99** (a tie, and the champion is behind on within-5-min); no_geometry champion closer **47.6%** (the shadow wins). Served versions read off the ANSWERS: champion `2`, shadow `1`. Record + row-grain CSV in `automation/runs/m6-shadow/` |
| ADR-004's canary spike, MEASURED (M6-S3) | `make canary-spike` (`SPIKE_ARGS=--dry-run` writes the prediction and applies nothing) | VERIFIED 2026-08-19 (M6-S3): **PASS 7/7**, ~4 min, prediction on disk BEFORE anything was applied. Shared Service **0 of 200** moved (`{weight: 0, weightTotal: 0}` — silent) · dedicated Service **100 of 200** (`noServer: true`, `{weight: 50, weightTotal: 100}`) · canary traffic **404** (the V2 model name is in the URL path) · `rewrite-target` **0 points** of change · `mirror-target` on the KServe-owned Ingress survived a reconcile AND produced a real nginx `mirror` directive · end state **200/200 champion**. Cleans up under a `finally` block. **Its first run is kept unedited** at `automation/runs/m6-spike/attempt1-no-dedicated-service/` — two wrong predictions and a self-inflicted outage (F-038) |
| The canary PATH (M6-S4) | `make canary-deploy` (`DRY_RUN=1` previews, `TEARDOWN=1` removes) — a second isvc carrying the champion's OWN bytes + its dedicated backend Service. **Moves no traffic** | VERIFIED 2026-08-19 (M6-S4): `models:/nyc-taxi-eta@champion -> version 2`, `MLSERVER_MODEL_NAME` on the Deployment reads **`nyc-taxi-eta`** (KServe injects the isvc name; our override wins the merge), the canary's own host answers `/v2/models/nyc-taxi-eta/infer` with **39.0019 minutes** and **404s on `/v2/models/nyc-taxi-eta-canary/ready`** — ADR-011 condition 2's remedy proved with its negative half. Backend Service selector asserted against KServe's own generated one, endpoints non-empty. `@champion` version 2 read before AND after (a move exits 2) |
| Shift traffic 10 → 100 → back, MEASURED (M6-S4) | `make canary` (`DRILL_ARGS=--dry-run` writes the prediction and applies nothing; ~6 min foreground) | VERIFIED 2026-08-19 (M6-S4): **PASS 11/11.** Ingress `canary` counter **0/177 · 41/420 = 9.76% · 301/301 = 100% · 0/300**, the two predictors' own counters **204/0 · 379/39 = 9.33% · 0/240 = 100% · 300/0** — two witnesses from different processes, and a record claiming one without the other is a contradiction. **0 of 1,440 requests failed**, champion pod UID unchanged, revert **0.37 s** against a 120 s budget. **Its first run went RED at 0% for F-039** (the route took a KServe-generated Ingress name) and is kept unedited in `attempt1-ingress-name-collision/` |
| The split as Prometheus draws it (M6-S4) | `uv run python scripts/canary_split_paste.py [--minutes N]` (a READER — one range query) | VERIFIED 2026-08-19 (M6-S4): prints champion/canary/share per minute; the green run reads `5.9% · 11.1% · 100.0% · 100.0% · 0.0%` at 240 req/min, with the failed attempt's flat `0.0%` visible six minutes above it. It exists so the board and the record are not two different claims |
| The alias rollback, REHEARSED (M6-S4) | `make rollback` (`ROLLBACK_ARGS=--dry-run` previews; `--rejudge` re-derives the verdict from the record and moves nothing) | VERIFIED 2026-08-19 (M6-S4): **PASS 10/10**, the runbook's §4 three moves run for real BOTH ways. **v2→v1 = 35.35 s of moves and 27.93 s of failing requests (55 of 85 probes, `HTTP 500` at the logged signature); v1→v2 = 34.38 s and 0.501 s (one 502)** — F-040, gotcha #86. `verify-m5` at the half-way state: **RED, 3 FAILs, §2's coherence check GREEN at `v1`**; at the end state GREEN. `configs/train.yaml` byte-identical by `git hash-object`, `@champion` back to 2, the final answer reproducing the parity row at **39.001937**. It REFUSES to start from a half-rolled-back state, and moves the alias with a RAW `set_registered_model_alias` — never `registry.promote`, whose refusal (F-011) is the point |
| Gameday 1 — four staged failures, predictions FIRST (M6-S5) | `make gameday` (`GAMEDAY_ARGS="--scenario predict\|control\|kill\|storage\|saturation\|report"`; ~55 min end to end, **scenario 2 is a deliberate ~5 min outage**) | VERIFIED 2026-08-19 (M6-S5): **accept bar MET with TWO wrong predictions, neither engineered.** Control (delegated to `alert_fire_drill.py`) **GREEN 11/11** — A-3 T+170.5 s, A-2 T+335.6 s, both at Alertmanager, cleared 330.1 s after the stop. Kill: **13.75 s**, 55 of 1,200 requests, different pod uid, **nothing fired** — and the edge 5xx share **peaked at 0.5000** with A-2/A-5 flickering `pending` (**F-041**). Storage: **8/8**, `403 HeadBucket`, **A-5 T+150.2 s then A-7 T+210.2 s** (**F-042** — the opposite of A-7's own annotation), A-2 silent through a total outage, undo staged first and `make serve` exit 0. Saturation: **A-6 at T+844.3 s = 244.1 + 600.2**, throttled 0 → **0.9996**, client p50 **94,553 ms** vs service p50 **1,084 ms**, **125 × HTTP 502** (the second wrong prediction), and **F-043** — A-1 cleared itself mid-event because the loaded predictor's exporter hit `scrape_duration` 4.613 s with `up == 0` against the idle shadow's 0.004 s. `@champion` **2** read and asserted in every scenario |
| Rehearse the restore (M6-S5) | `make restore-drill` (`RESTORE_ARGS="--backup <dir> --keep"`) | VERIFIED 2026-08-19 — see the backup row above for the numbers. The **live** databases and buckets are only counted, never written, and no scratch survives the run |
| Gate check M6 | `make verify-m6` | VERIFIED 2026-08-20 (M6-S5 leg 2): **GREEN 63/63 sub-checks in 7 sections, 2.147 s, exit 0** — the eyes (Prometheus + Grafana on the EXISTING 8081 route, four workloads ready, one live PromQL query, and **F-043's live question: is the CHAMPION's exporter healthy right now**, scoped by isvc name and bounded by the configured scrape interval) · the judgement (all 7 rules LOADED and `health=ok`, every `for:` matching, **every threshold parsed out of the rules file and found in `docs/slo_serving.md`**, every rule carrying a `signal` and a `why`, F-035's absences agreeing with `render_alert_rules.py`, A-1 counting a bucket edge and never a quantile) · shadow BEFORE canary, the ordering checked on the two records' own clocks · 90/10 from COUNTERS with the two witnesses 0.43 points apart · the rollback's three moves at 35.347 s under load with the asymmetry and the half-way coherence line · the gameday (predictions written first BY CLOCK, each scenario's prediction field-equal to the committed file, control first and green, ≥1 wrong, the kill's outage re-derived from its own anchors) · the restore's compound label and the prose checked against the records · the alias law live. **RE-RUNS NOTHING** (no gameday, no injection, no traffic shift, no alias move, no restore, no deploy — pinned by `tests/unit/test_verify_m6.py`), no skip flag, no fast mode (M1's rule, **sixth** inheritance). Transcript: `docs/verify_m6_transcripts.md` §1 |
| Prove the M6 gate can go RED | `make verify-m6-redteam` (`bash scripts/verify_m6_redteam.sh`) | VERIFIED 2026-08-20 (M6-S5 leg 2): rewrites ONE number in `automation/runs/m6-gameday/kill.json` — `observed.outage_seconds` **13.75 → 13.501**, taken from the record's OWN `load.error_window.span_s`, i.e. gotcha #75's wrong anchor re-made and wrong by 0.249 s — leaving the anchors, the pod uids, the alias, the prediction and all 7 recorded checks untouched → **RED exit 1 with 2 FAILs from TWO DIFFERENT ARTIFACTS**: the record stops reconciling with its own arrivals, AND `docs/gameday_m6.md` quotes a number no record holds. **61 sub-check lines still ran and passed**; restored under an EXIT trap and verified by sha256 (`f73324ffa333…` before and after) with `git status` clean → **GREEN 63/63**. Touches no pod, no rule, no traffic, no MLflow run, no registry version, no alias. **Its FIRST run found a defect in the GATE**: the prose leg rendered 13.75 at zero decimals as `14`, matched, and stayed green — gotcha **#90** |
| The headroom leg — the input to the drift bar, 2019 data ONLY (M7-S3) | `make drift-headroom` | VERIFIED 2026-08-20 (M7-S3): the two HELD-OUT 2019 months against the 43,987,422-row train reference — months whose verdict already exists (the champion was measured on them and PROMOTED), which is what makes it legal to argue a bar from them without setting it from the number the thing under test just produced. **Highest INPUT-column PSI across both: 0.0323** (`dayofweek`, 2019-07) — and *what* it is matters as much as its size: July 2019 held five Mondays, i.e. **calendar arithmetic**, the least model-meaningful move a month can make. Largest behavioural: **0.0137** (`PULocationID`, 2019-08). Volume ratios 0.8216 / 0.7899. It **ran before `docs/slo_serving.md` §8 existed**, and the commit that carries §8 and the prediction (`d113f26`) lands before any 2020 drift record does — M7 law 4's order made checkable from git rather than asserted in prose. Record `automation/runs/m7-drift/headroom.json` |
| Drift for a scoring month, issuing NO verdict (M7-S3) | `make drift DRIFT_ARGS="--months YYYY-MM [--push]"` (`--push` needs a gateway; `make drift DRIFT_GATEWAY="--pushgateway http://localhost:9098"` for a port-forward) | VERIFIED 2026-08-20 (M7-S3): exact PSI from DuckDB value counts (no sampling, so the number does not move when nothing moved) over six monitored columns — five INPUTS and, separately, the TARGET, which is excluded from the alert's share **by name** because inputs-steady-plus-target-moved and both-moved are opposite diagnoses. **It prints no verdict and contains no threshold**: the bar lives in the SELECTOR of one Prometheus rule, and an **AST** test (never a grep — these modules argue their own design at length, #53/#68) fails if a bar-shaped constant appears anywhere under `src/taxi_mlops/monitoring/`. Observed 2020-01/02/03: max input PSI **0.0103 / 0.0087 / 0.0217**, volume ratio **0.8336 / 0.8776 / 0.3913**, `unseen_share` **0.000% on every column in every month** |
| Push 2020-01..03 and watch the rules decide, prediction FIRST (M7-S3) | `make drift-drill` (`DRILL_ARGS=--dry-run` writes the prediction and computes nothing; ~12 min, **no injection and no outage**) | VERIFIED 2026-08-20 (M7-S3): **PASSED.** Unlike M6's drill this one injects NOTHING — the condition is real 2020 data already in the repo — so there is nothing to stop and nothing to undo. **A-9 `ScoringVolumeCollapse` pending T+31.5 s → FIRING T+331.5 s for `month='2020-03'` ONLY**, reaching **Alertmanager**; A-9 for 2020-01/02 and all seven other watched rules **inactive as predicted**; the pre-registered open question — *does A-8 fire at monthly grain?*, tagged `confidence: low` — answered **correctly (it does not)**. `@champion` **2** before and after. **Phase 0 resets the gateway** (it has no expiry, so a second run would start with A-9 already firing and could never observe a transition) and **phase 7 proves it CLEARS then restores the truth**: the 2020-03 group deleted, A-9 inactive **40.0 s** later, real numbers pushed straight back — the board ends carrying the fact that March 2020 lost 61% of its trips, because latching it off to tidy a transcript would be publishing a false board. **Its first run went RED over a defect in its own JUDGE**, not the system: `fired_at` was keyed on the alert NAME while A-9's prediction is per **(alert, month)** — three statements about one rule — so it reported `A-9 fired and was predicted INACTIVE` over a system behaving exactly as predicted (#67's family). The repair reads the per-series `alerts` array, which is **strictly stronger**: a bar so low that an ordinary January trips it passes a name-level check and fails this one. The PREDICTION object was untouched, and a test pinning it to the committed JSON would have gone red if it had not been |
| Evidently beside our SQL PSI — a second instrument on the same question (M7-S3) | `make drift-witness WITNESS_ARGS="--months 2020-01 2020-03"` (a READER: deploys nothing, pushes nothing, touches no alert) | VERIFIED 2026-08-20 (M7-S3): Evidently **0.7.21** on a **seeded** 200,000-row sample per side (seed recorded, because an unreproducible number in a record is a number nobody can check twice). **On the question the alert asks — did any INPUT column drift? — the two instruments AGREE for both months: none did**, ours by PSI < 0.10 and theirs by Wasserstein-normed/Jensen-Shannon at their own defaults (the statistic each column got is recorded in `methods`, because that is exactly why the NUMBERS must not be compared). Read sceptically, which is what a second witness is for: Evidently flags the TARGET at **0.1014 in January and 0.1008 in March** — the same value in an ordinary month and in the collapse, both barely over its 0.1 default — so it does not distinguish them either, and "Evidently detected drift in March" would be true and misleading. **Its first run reported total disagreement and nothing had disagreed**: the parser looked for `metric_id` and `status`, and the payload carries `metric_name`, a structured `config` and `value`. **A second witness that cannot be read reports maximum disagreement** — the most alarming thing it could say and the least true |
| F-051's counterfactual, through the SHIPPED arithmetic (M8-S1) | `make drift-monotonicity` (`F051_ARGS="--month YYYY-MM"`; a READER — opens the analyst layer, writes nothing, pushes nothing, takes A-9's bar by PARSING the rules file) | VERIFIED 2026-08-21 (M8-S1 leg 1): 2020-03, deleting the k quietest days — a strictly worse shutdown each step — **against calendar days the ratio falls at every step, 0.3913 → 0.3583, and never re-crosses the bar**; against the OLD observed-days denominator the same series **ROSE at every k and went SILENT from k=8** (0.4768 · **0.5143** · 0.6641 — REV's numbers reproduced). The old column is the CONTROL, not decoration: the script FAILS if it stops reproducing F-051, because a table showing only the new series falling is consistent with a month that was never at risk |
| F-050's pair, proved: the store survives a pod, its absence pages (M8-S1) | `make drift-persistence-drill` (`PERSISTENCE_ARGS=--dry-run` writes the prediction and deletes nothing; ~18 min, **no outage** — the only destructive act is deleting the drift SERIES, and phase 4 pushes the real ones back) | VERIFIED 2026-08-21 (M8-S1 leg 1): **PASSED 16/16**, prediction committed BEFORE the run and pinned by a unit test. PVC **Bound 128Mi** and the container's args carry `--persistence.file` (a mounted volume with no flag is decoration) · 48 samples pushed, pod deleted, **a DIFFERENT pod object (uid `bf053286…` → `2a1591bc…`) ready in 13.12 s serving the SAME 48** — the same read returned **0** three times on an emptyDir (F-050) · wipe → **A-11 FIRED at 625.1 s** against its 600 s sustain and **reached Alertmanager**, while **A-10 stayed inactive through a TOTAL loss of the drift surface** (its blind spot demonstrated, not asserted — and the whole argument for A-11) and A-9 went quiet with it · re-push → **A-11 cleared in 37.8 s**, A-9 back for 2020-03. `@champion` **2**, read never written |
| A-4's two series: the wire vs the registry (M7-S3, F-035) | `make push-serving-version A4_ARGS="--no-push"` reads both and prints; without it, pushes | VERIFIED 2026-08-20 (M7-S3): `served: 2` read off a **real prediction** (the version is stamped on the ANSWER — `GET /v2/models/nyc-taxi-eta` reports `versions: []` on this runtime, M5-S2) and `registry: 2` through F-009's one resolver → `agree`, so A-4 correctly stays inactive. F-034 said there were not two series to compare; there are now. **It REFUSES to push when either side is unreadable** rather than pushing a placeholder zero — a gauge of 0 against a registry gauge of 2 is a MISMATCH, so a placeholder would page an on-call for an unreadable endpoint, with the alert right about its own arithmetic and wrong about the world. **Honest cut: the metric SOURCE lands here, the CADENCE lands with M7-S4's scheduler**, which is why A-4's rule carries a freshness clause (`< 1800`) — a stale pushed pair agrees with itself forever |
| Count a client-side refusal (M7-S3, F-035) | `make quote QUOTE_ARGS="--at 2031-07-04T09:15:00 --pu 132 --do 48 --push-metrics <gateway>"` | VERIFIED 2026-08-20 (M7-S3): the refusal exits 2 as always AND increments `taxi_quote_refusals_total`; after two past-horizon quotes `increase(...[1h])` read **1.2141** and **A-3's client half FIRED** (`QuoteHorizonRefusals`, pending → firing in 60 s) — the alert M6-S2 measured as impossible on this stack (`22 → 22` on the infer counter, because F-019 refuses in the CLIENT before a request exists). **Off by default**, because the gateway has no hostPort and a quote must not fail its metrics leg on a laptop with no port-forward; `record_refusal` never raises, so a rider cannot lose a quote to a down gateway. **Honest limitation recorded**: `increase()` needs the counter to move *while Prometheus is watching*, so the guarantee is "a horizon expiry produces a stream of refusals and will page", not "every single refusal will" — which is why `verify-m6`'s coverage check stays as the complement that catches the expiry BEFORE the first rider meets it |
| The retrain challenger, re-derived at its own scale (M7-S4, F-020) | `make retrain` (`RETRAIN_ARGS="--plan-only"` is the seconds-long provenance check that fits nothing; `--train-months YYYY-MM` is the SAMPLED, gate-disqualified path). **Exit 0 = a verdict that passed · 1 = refused · 2 = the challenger could not be built · 3 = no verdict was issued · 4 = the run CRASHED after it began (added M7-S4's completion leg, gotcha #96: the first full-data run's traceback exited with a status this program had already given a meaning, so its `.status` file told the next session "the challenger could not be built" about a challenger that had been built, fitted for 28 minutes and judged — an unhandled crash must not be able to wear a verdict's clothes, and note that a bare Python exception exits 1, which here means REFUSED)**. **Those are the CLI's codes and they DO NOT survive `make detach` — gotcha #97**: GNU make exits **2** for any failed recipe (measured, `tests/unit/test_detach_exit_codes.py`), so the vocabulary collapses to {0, 2} at the launcher and 2 collides with "could not be built". **Do not read a verdict out of a `.status` file — read the RECORD, and treat its ABSENCE as the crash signal**; the recipe also echoes the CLI's own code into the log and re-exits with it | VERIFIED 2026-08-20 (M7-S4), plan half: `models:/nyc-taxi-eta@champion -> version 2 (auto-lgbm-v2)`, feature set `v2` read off the version's own tag, and the transfer resolved from three TRACKED artifacts — **`min_data_in_leaf` 1293 -> 8620**, *1 row in 5,103 where it was chosen · 1 in **34,020** unchanged at the refit's scale (F-020's own number, recomputed from the records) · 1 in 5,103 after* — with `bagging_fraction, cat_smooth, feature_fraction, lambda_l1, lambda_l2, learning_rate, max_cat_threshold, num_leaves` **passed through and RECORDED as passed through**. Round budget **500 configured / 800 inherited -> 2400**, and the fit reports `ended_by` (`early_stopping` | `round_cap`) because the champion's own refit ended 791/800 and a metrics table cannot show that. It **cannot promote**: `promote=False` unconditional, no parameter to change it (AST-tested). Transcript: `docs/retrain_m7_transcripts.md` §2. **The FULL-DATA half, measured 2026-08-20T05:59Z on 43,987,422 train rows and judged on the untouched holdout: `retrain-rescaled-v2` KPI-09 **3.2412** / KPI-10 **81.568%** against the serving champion's **3.2403** / **81.577%** → **REFUSE**** — floor conditions passed (+3.30% against a 2.00% bar, KPI-10 +0.835 points), both F-011 incumbent conditions failed. **So F-020's correction is worth 54 milliseconds of mean error over 5,950,708 rows**, and that is the result rather than a disappointment: the finding was about REASONING — a knob applied at a scale it did not mean anything at — and the measurement says the champion was not materially harmed by it. **Half two is discharged in the direction that could not be arranged**: `ended_by: early_stopping` at **779 of the re-derived 2400-round cap**, 1,621 rounds unspent, so this fit is unambiguously NOT truncated where the champion's 791/800 cannot tell converged from truncated. **The verdict also feeds the open fork**: the refusal is −0.03% against an incumbent condition with NO margin, so AWAITING_PO 2026-08-18-1 has now seen that condition move the pointer on +0.63% (M3-S5) and hold it on −0.03% — had the arithmetic landed 54 ms the other way, the pre-registered gate would have spent the whole transition tail on it. **Attempt 1 reached this verdict and crashed writing it down** (`docs/retrain_m7.md` §7.1, gotchas #95/#96); **attempt 2 (2026-08-20T06:43:37Z, 1,618.4 s) reproduced every number and wrote the record** — see the next row |
| Judge the retrain record against the prediction written BEFORE the fit (M7-S4 completion leg) | `make retrain-prediction-check` (a READER: two files, no live system, no fit; exit 1 on any exact mismatch) | VERIFIED 2026-08-20 (M7-S4 completion leg): **REPRODUCED — all 20 exact claims and 3 path properties hold.** `automation/runs/m7-retrain/rerun-prediction.json` was committed BEFORE the re-run was launched, which is the only thing that makes a repeat of a 27-minute fit evidence rather than a do-over; the record `automation/runs/m7-retrain/latest.json` then came back at **3.2412 / 81.568% / val 3.3811 / 779 of 2400 / early_stopping / REFUSE on both incumbent conditions**, every field compared **at the precision the prediction was written at** (gotcha #42) under a **one-decimal floor** (gotcha #90). Two MLflow runs of one configuration agreeing to the last kept digit (`d2f69f90…`, `8fcc7b98…`) is this program's second determinism observation, after M3-S3's `3.47603843547682` twice. **The LOOSE block prints what did NOT hold rather than dropping it** (gotcha #94's failure direction): the exit code was predicted 1 and the status file holds 2 — gotcha #97, a fact about `make`, not about the fit. RED-TEAMED in unit form four ways (a 0.0001 move in the challenger's MAE, a REFUSE relabelled PROMOTE, the failing checks swapped to the floor's, and a path outside the repo — the last found a defect in the checker itself, #55's family). Registry read live afterwards: `@champion -> 2`, `VERSIONS: ['1','2']` — **no version 3 exists**, which is the strong form of "nothing was promoted" |
| Put F-020's divisor ON the version, derived from the tracked records (M8-S1, F-048) | `make backfill-provenance` (`BACKFILL_ARGS=--dry-run` resolves and writes nothing; `--version N` scopes it) | VERIFIED 2026-08-21 (M8-S1 leg 2): dry run resolved both versions, then the write — **`2 version(s) changed; no alias was read or moved, no version was created, nothing was deleted`** — then a third run: **`0 version(s) changed`**, `unchanged (already carries exactly this)` per version. Version 1 records `no sampled search` as a FACT (it is the hand-configured v1 and really had none); version 2 records **6,598,113 rows, cap 800** from `automation/runs/m3s4/sniper-v2.json`. It writes through `registry.record_search_scale` — the additive path inside the ONE module allowed to touch the registry — which **refuses a disagreeing rewrite** rather than overwriting a claim about a fit that already happened. AST-pinned to name no alias verb and no destructive verb. `@champion` version **2** before and after, never read by it. The host then resolved **factor 6.6667 · min_data_in_leaf 1293 -> 8620 · round cap 2400** off the registry instead of off a host JSON |
| Build the Feast QUARANTINE and prove it never touched the project graph (M8-S2) | `make feast-quarantine` (`QUARANTINE_ARGS=--resolve` re-resolves and rewrites the pin file; `--check` builds nothing) | VERIFIED 2026-08-21 (M8-S2): **`uv.lock` byte-identical across the run** (sha256 `640154c5…` before and after — a difference ABORTS the script, so the invariant is in the code and not in the write-up), `feast` **absent from the project environment** (asked of `uv pip list`, never assumed), and the two sides printed side by side: `project pandas 3.0.5` vs `quarantine pandas 2.3.3 feast 0.66.0`. **Reproducible from the committed pins alone**: the venv was DELETED and rebuilt with `uv pip install --no-deps -r infra/feast/requirements-feast.txt` and the same **64 packages** came back. The probe records both columns — **the two sides differ on `['pandas']` and nothing else** (numpy 2.5.2 · pyarrow 25.0.1 · CPython 3.12.14 identical), which is the fact M8-S3's seam argument rests on. Record: `automation/runs/m8-feast/probe.json` |
| Build the parquet Feast reads, from the SETTLED trees (M8-S2) | `make feast-sources` (`SOURCES_ARGS=--static-only` skips the 43.9M-row fit; `--train-months` is a SMOKE override that labels its own output) | VERIFIED 2026-08-21 (M8-S2), **3m07s**: `zone_static` **263** rows · `calendar_day` **4,383** · `od_window_stats` **248,169** · `pu_hour_window_stats` **35,589**, from 43,987,422 train rows through `aggregates.fit(point_in_time=True)` — the ONE path, never a re-implementation. Six windows, each stamped at its own EXCLUSIVE end (**2019-02-01 … 2019-07-01**, derived from the window's own months and never typed); **2019-01 gets no rows at all**, because it has no history. Writes ONLY into `data/feast/`: all four settled pins read `up to date` afterwards, and `uv.lock` is byte-identical to the `m7-closed` tag. A test asserts exactly ONE writer call exists in the module, so every output path is `OUT_DIR` by construction |
| Register the git-defined feature repo, and read it back (M8-S2) | `make feast-apply` · `make feast-registry` (the read-back, run INSIDE the quarantine) | VERIFIED 2026-08-21 (M8-S2): 5 entities and 4 feature views applied into a **gitignored, regenerable** local registry (`definitions.py` is the source of truth; a committed registry would be the second home F-013 keeps deleting). The read-back is the `deploy_serving.sh` idiom — never trust the file you submitted — and it caught its own drift on the first run, reporting tags edited minutes earlier. `automation/runs/m8-feast/registry.json` is what `tests/unit/test_feast_repo.py` compares the catalog against |
| The pin file's ROUND TRIP — the regenerator against the artifact it maintains (M9-S3, **F-057**) | `uv run python scripts/feast_probe_record.py --rewrite-pins` (pinned as a test: `uv run pytest tests/unit/test_feast_repo.py -k reproduces_the_committed`) | VERIFIED 2026-08-24 (M9-S3): the regeneration produced **NO DIFF AT ALL** — sha256 `a700cd6b52dcaaa974ed36b50286161eead2373bd07e38734e99de53d04e4131` before and after, `git diff` silent, 66 pins. `_freeze` canonicalises to **PEP 503** and a name collision REFUSES rather than dropping a pin; the body is written as its own lines SORTED, which is the ordering the committed file has carried since M8-S2 and the one a reviewer checks with `sort -c`. **The tool was made to agree with the reviewed artifact, not the artifact with the tool** — so the round trip is proved against a file that predates the fix. Honest cost: today's `uv pip freeze` name-sorts and so differs on the three hyphenated siblings (`mypy-extensions`/`mypy`, `pydantic-core`/`pydantic`, `uvicorn-worker`/`uvicorn`); this script is the file's only producer. Three tests, two needing no venv (so they run in CI and in the task image); the round trip writes to a **COPY**, never the tracked file (gotcha #48). **RED-TEAMED**: one pin restored to `PyYAML` → **2 tests RED from two independent angles**, restored, GREEN |
| Rebuild the quarantine from its pins alone — re-earned for the regenerated file (M9-S3) | `rm -rf .venv-feast && uv venv .venv-feast --python 3.12 && uv pip install --python .venv-feast --no-deps -r infra/feast/requirements-feast.txt` (M8-S2's proof, run again) | VERIFIED 2026-08-24 (M9-S3): the venv was DELETED and rebuilt from the committed pins and **the same 66 packages came back — 0 only-before, 0 only-after**. The wall re-read afterwards: `quarantine pandas 2.3.3 feast 0.66.0` vs `project pandas 3.0.5`, `feast in project env: False`, and `uv.lock` `640154c585a5b1e9…` byte-identical throughout. **`make feast-quarantine --check` was deliberately NOT run**: it rewrites `automation/runs/m8-feast/probe.json`, M8-S2's tracked record, and rewriting an earlier milestone's evidence as a side effect is F-053/F-063's shape |
| No record read may SKIP when its record is missing (M9-S3, **F-054**) | `uv run pytest tests/unit/test_record_marker.py -q` | VERIFIED 2026-08-24 (M9-S3): `test_no_record_read_is_guarded_by_a_skip` walks **every** file under `tests/unit` with `ast` — decorators only, because this suite argues about the old form in prose (gotcha #99) — and refuses `skipif(not RECORD.exists())`. The twelve that carried it (`test_canary_and_rollback.py` 8, `test_shadow_and_spike.py` 4) are assertions now, each through a `_record()` helper whose message says what the absence MEANS. **Host suite 1171 passed, NO SKIPS** (was 1167); `-m 'not needs_records'` deselects **53** (was 41). **RED-TEAMED**: `automation/runs/m6-shadow/disagreement.json` moved aside → **3 FAILED** naming the record and the finding while 12 still passed; restored → 15 passed, clean tree |
| Ask whether the registry still matches git (M8-S2, **F-055**) | `make feast-plan-check` (`make feast-plan` is the raw output for a human) | VERIFIED 2026-08-21 (M8-S2): **`4 object(s) reported, 4 clock-only, 0 substantive`** → `ok  the registry matches the definitions in git`. It exists because **`feast plan` can never say "no changes"** — Feast re-stamps `DataSource.meta` at import, so all four views report as Updated on a repo where nothing moved (gotcha #78's disease in its worse direction: an always-noisy reading looks like diligence). The checkable statement is that every difference is confined to `("seconds:", "nanos:")`, an allowlist a test pins. **RED-TEAMED live**: `centroid_lat` renamed to `centroid_lat_TAMPERED` in `definitions.py` → **FAIL naming `zone_static` and the field, with the other three views still reading clock-only**, then restored from git, re-applied, GREEN. Record: `automation/runs/m8-feast/plan.json` |
| The DECLARED row set both M8 seams are measured on (M8-S3) | `make feast-rows` (`ROWS_ARGS=--refresh` REBUILDS it, which changes the set every published number was measured on) | VERIFIED 2026-08-21 (M8-S3): **88 declared row(s)** — `hazard` 16 · `month-boundary` 12 · `ordinary`/`airport`/`no-geometry`/`long-trip` 15 each. The sixteen hazards are **imported from `taxi_mlops.serving.parity.HAZARDS`**, not retyped, so `make parity`'s wire seam and this story's store seam are measured against ONE row set (a test compares them field by field). The boundary twelve are DERIVED from `configs/train.yaml`'s own train months — the last minute of each and the first minute of the next, 120 s apart. The sixty drawn rows are `ORDER BY hash(<the row's own key columns>, 20260821) LIMIT 15`, and the drawer **refuses a short draw**: its first version asked for `USING SAMPLE reservoir(15 ROWS) REPEATABLE (seed)` after a `WHERE` and got **0 airport rows out of 3,237,471**, because DuckDB samples the scan and the filter is applied to what survives it |
| Retrieval parity + the point-in-time proof (M8-S3) | `make feast-retrieval` (`RETRIEVAL_ARGS=--no-write` prints the verdicts and writes no record; ~4 min, of which the 43.9M-row truth fit is nearly all) | VERIFIED 2026-08-21 (M8-S3): **PASSED.** Parity **`max \|ours − store\| = 0.000e+00` over 14 columns and 88 rows against a bar of EXACT**, with **`one missing` ZERO everywhere** — the store and the feature path agree about which rows have no value at all, not merely about the values. The two-sided no-geometry assertion held (11 PU / 18 DO rows, store returned a row for **none**, our path reports `has_geometry = 0` on 20). PIT: honest vs naive differ on **61/76** OD rows (max **8.2000** min), 53/69 speeds, 62/78 rates; **the naive answer IS our own full-window table (0 mismatches over 88)**; **10 rows the honest join must tell nothing are handed a number by the naive one** (2019-01 has no history); and **all six boundary pairs were served different windows across 120 s** while the naive column sat constant at 8.3500. The truth is re-fitted from `data/processed/`, never rebuilt from the parquet under test. A READER — AST-pinned to make exactly ONE subprocess call (the quarantine crossing) and to name no registry, deploy or materialize verb. Its first run went RED on its own count guard and that is **F-056** |
| What the SCHEDULED retrain actually resolved, off the control plane (M8-S1, F-048) | `uv run python scripts/retrain_proof_record.py --out automation/runs/m8-provenance/proof.json` (needs a route; a READER — launches nothing, aborts nothing, moves no alias) | VERIFIED 2026-08-21 (M8-S1 leg 2). It asks the server for the newest firings of `retrain-schedule-proof` and reads the record **the POD returned as its output** (the task returns JSON text: a verdict travels as content, never as a path). **Its first run captured the BEFORE state** — five consecutive firings on task version `6d5b536b975b…`, every one `rescale_factor: null, round_cap: 500`, exit **1** — which is F-048 alive, measured by the same instrument that reports the after; `earlier_runs_seen` keeps both in one file so the contrast is not taken on trust. Two defects it found in itself first: the unfiltered run list comes back **OLDEST FIRST** (so a 40-run scan saw only M4's pipeline and reported "the trigger never fired" — gotcha #59's family, an absence inferred from looking in the wrong place), and `ActionOutputs` is neither a mapping nor a string, so `json.loads(str(outputs))` refused and that refusal read as the same absence |
| Register the retrain's SCHEDULE and read it back off the server (M7-S4) | `make retrain-schedule` (`DRY_RUN=1` resolves and deploys nothing) | VERIFIED 2026-08-20 (M7-S4): **Flyte 2.6.1 / chart v2.0.42 carries triggers natively** — asked of the tooling, not read off a version table (gotcha #70's family) — so the kickoff's recorded cron fallback is **NOT executed and stays armed**. Deployed `taxi-pipeline-train.retrain` (version `6d5b536b975b…`, image `taxi-mlops-pipeline:72a4013`) with two triggers **declared in code with their inputs** (the CLI form cannot pass inputs, so a CLI-created trigger fires the DEFAULTS), then read them back **off the control plane**: `retrain-schedule-proof … every 20 minutes starting at now … True` and `retrain-monthly … cron: 0 3 1 * * (UTC) … **False**`. The monthly one is registered and inactive ON PURPOSE — hours of CPU under a 6-core limit on a laptop nobody watches; one field and a PO's call. **Its F-026 guard fired on this story's own commit** (`scripts/retrain_schedule.sh` not in the image) and the image was rebuilt rather than the guard narrowed |
| Prove the bake-off can be RUN again (M7-S4, F-022) | `make bakeoff BAKEOFF_ARGS="--smoke-rows 20000"` | VERIFIED 2026-08-20 (M7-S4): **exit 0**, past contender resolution for the first time since M3-S5's own promotion moved the alias. `[resolve] champion (alias) auto-lgbm-v2 family=lgbm features=v2 (24) **(DERIVED from the artifact — F-022)** trees=791` — the row that used to declare `v1` now reads its set off the loaded booster's ordered feature names. Five verdicts printed, **no JSON written, nothing promoted**, and the 2x2 **declines to print** because no contender occupies its origin cell (v1 features, hand params) — computing it against the alias would report `auto-on-v2 +0.00%`, correct arithmetic answering a different question. Transcript: `docs/retrain_m7_transcripts.md` §1 |
| Reprint every number in the drift memo (M7-S5) | `uv run python scripts/drift_memo_numbers.py [section…]` | VERIFIED 2026-08-20 (M7-S5 leg 1): the M2-S4 twin-script precedent applied to `docs/drift_memo_m7.md` — 19 queries across 7 sections, each printing the SQL it ran, over three sources whose difference IS the meaning: `analyst.*` (facts about the WORLD), `main_marts.scoring_daily` (facts about the CHAMPION's error, under **monitoring** ids), and `automation/runs/m7-drift/*.json` **read back as data** rather than retyped (`read_json_auto` / `json_keys`, so the record's own month keys are DERIVED, not typed). The March cut is declared ONCE as `PERIOD_SQL` so no two sections can disagree about it. Read-only, writes nothing, seconds. Transcript: `docs/drift_memo_m7_transcripts.md` §1 |
| The predictions & drift board (M7-S5) | `make boards` (`--verify` is the read-only twin) | VERIFIED 2026-08-20 (M7-S5 leg 1): **`Predictions & drift (M7)` created, id 5, 8 cards**, over `marts.scoring_daily`; the three existing boards reported `card updated` and kept their ids (idempotent BY NAME, M1-S5). `--verify` GREEN across all four dashboards — `card 'KPI-17 · trips scored per day' RAN and returned 91 row(s)` and `no card claims KPI-09/KPI-10` on every board. Six board laws added as unit tests, five of them M7-specific (monitoring ids only · KPI-16 present AND a series · ≥3 daily-grain cards, none rolled up to the month · the tolerance read off the mart · the model version visible) |
| Execute EVERY board card; an empty panel is a FAILURE (M7-S5) | `make board-cards` (`BOARD="…"` scopes it to one board) | VERIFIED 2026-08-20 (M7-S5 leg 1): **36 cards across all 4 boards, 0 failures.** It exists because `--verify` runs ONE card per dashboard, which proves the connection and the credentials and not the board — and an empty panel is indistinguishable from a quiet system (**gotcha #78**, learned expensively on the Grafana boards at M6-S1). It runs the SQL a reviewer reads in the checked-in JSON straight at the one Postgres over the `make marts` transport, so what is under test is the reviewed artifact. **Deliberately NOT wired into `verify-m1`**: widening a gate's behaviour late in a session is how a guard goes red for a correct system (gotcha #50) |
| Gate check M7 | `make verify-m7` | VERIFIED 2026-08-20 (M7-S5 leg 2): **GREEN 62/62 sub-checks in 7 sections, 5.328 s, exit 0** — the scoring months (`trips_clean` still exactly `{train,val,test}` asked of the ROWS · the config loader REFUSES a month in both lists · the 2019 pins unmodified in git while the scoring trees carry their own · the 2025 probe VALIDATED and having acquired nothing · three refusal shapes, exit 1 each, and their month in NO ingest or scoring table) · **the two failure signatures differing in all 4 discriminating fields**, built from record shapes rather than from a doc table, with the drift metric's ABSENCE counted where a landed month would have to appear · the predictions table reconciling **15,413,352 rows across three systems** with the ingest report as the AUTHORITY, the self-check matching the registry's own `gate_challenger_mae`, `model_versions_seen = 1` per month, a row per calendar day, and NO floor/margin/KPI-09/10 column · the drift judgement (5 M7 rules LOADED and `health=ok`, **every threshold parsed out and found in §6/§8 specifically** — a bar argued in the latency section is not an argument for a drift bar — the absence list EMPTY, A-8 excluding the target BY NAME, no bar-shaped constant under `src/taxi_mlops/monitoring/`, `honor_labels: true`, and `push_metrics` REFUSING a payload with no freshness stamp) · **the order of work on three clocks including git** · the retrain's REFUSE with F-020's rescale re-derived and **not one of its 8 runs a registry version** · the memo's 14 instrument numbers against the records at the precision the document wrote them. **RE-RUNS NOTHING** and asks the live system exactly three questions (one prediction, one PromQL query, one rules read), pinned by `tests/unit/test_verify_m7.py`. No skip flag, no fast mode (M1's rule, **seventh** inheritance). Transcript: `docs/verify_m7_transcripts.md` §1 |
| Prove the M7 gate can go RED | `make verify-m7-redteam` (`bash scripts/verify_m7_redteam.sh`) | VERIFIED 2026-08-20 (M7-S5 leg 2): rewrites ONE number in `automation/runs/m7-drift/drift-2020-03.json` — `volume_ratio` **0.3913 → 0.4021**, a ratio of TOTALS where a ratio of RATES belongs, derived from the record's OWN fields (`current_rows` over `reference_rows / 6`) and **still under the 0.50 bar so the alert still fires** → **RED exit 1 with 3 FAILs from THREE DIFFERENT ARTIFACTS**: the anchor arithmetic (trips/DAY over trips/DAY), `drift_fire_drill.json` (what the live gateway held while the alert was judged), and `docs/drift_memo_m7.md` §7 (the only witness a human reads). **59 sub-check lines still ran and passed**, and the **bar-daylight leg stayed GREEN by design** — the planted value keeps the argument intact, which is what separates a gate that fails on a WRONG number from one that fails on any edit. Restored under an EXIT trap, sha256-verified byte-identical, `git status` clean → **GREEN 62/62**. Touches no pod, no rule, no pushed metric, no MLflow run, no registry version, no alias. It is **F-045 itself** — *a month is not a unit of demand; a day is* — planted against the milestone that found it |
| The Feast ONLINE store (M8-S4, ADR-012) | `make deploy-feast-store` (`DRY_RUN=1` mutates nothing; `TEARDOWN=1` deletes the namespace **and its PVC**) — one in-cluster Redis, no hostPort, and **NO features** | VERIFIED 2026-08-21 (M8-S4): `redis:8.2-alpine@sha256:30abb90e62f1…` (TAG AND DIGEST) on `mlops-taxi-worker2`, PVC Bound 1Gi. The accept is an **answer from the server**, not a list of ready objects (gotcha #59): `PING -> PONG` **plus a real SET/GET/DEL round trip** — a WRITE, which is what a materialization needs and a readiness probe does not prove — then `maxmemory-policy=noeviction maxmemory=536870912 dbsize=0` read back **off the running server** rather than off the values submitted (`deploy_serving.sh`'s idiom). It **FAILS if the policy is anything but `noeviction`**: an evicting feature store drops the key the next request asks for and answers null, which reads as a feature with no value. It does not materialize (that is its own command with its own record) and it cannot name the champion in code (unit-tested). Record: `automation/runs/m8-online/store.json` |
| Fill the online store (M8-S4) | `make feast-materialize` (`MATERIALIZE_ARGS=--dry-run` prints the derived window and writes nothing) | VERIFIED 2026-08-21 (M8-S4): window **`2019-01-01T00:00:00` -> `2019-07-01T00:00:01`, DERIVED** from the published parquet by `scripts/feast_source_window.py` and never typed — a typed end would keep materializing successfully while silently ceasing to include a seventh window. Through an ephemeral port-forward on **6380**, inside the quarantine: `feast apply` first (a materialization into a store the registry does not know about is a half-configured success), then **57,688 keys / 14.32 MiB in 7 s**, read back off the SERVER. It **REFUSES to report success against a store that is empty afterwards** — an empty online store answers every lookup with null, which is F-050's shape one layer along. Record: `automation/runs/m8-online/materialize.json` |
| THE 100-pair online/offline parity (M8-S4) | `make feast-online-parity` (`PARITY_ARGS=--no-write` prints the verdicts and writes no record or table) | VERIFIED 2026-08-21 (M8-S4): **`max \|online − offline\| = 0.000e+00` across 16 columns and 100 declared pairs against a bar of EXACT, with `one missing` ZERO on every column** — the load-bearing count, because it says the store and the feature path agree about *which rows have no value at all*. Plus the ANCHOR (the seven static columns against `taxi_mlops.features.zones`/`.calendar`, the champion's own lookup — without it this is two Feast reads agreeing with each other), the **two-sided no-geometry assertion** (our path has no geometry on 13 pu / 19 do rows, the store declined exactly those, **0 disagreements**, zones `264, 265, 999`), and the offline join's shortfall **CLASSIFIED** — `34/37/79/67/73` rows returned for 100 declared, every one a duplicate entity key, **UNEXPLAINED 0** (gotcha #103). A READER: two subprocess launches, both named and AST-pinned. Artifact: `docs/feast_online_parity_table.md` (committed — the blueprint's named accept artifact) |
| Prove the parity table can go RED (M8-S4) | `make feast-online-parity-redteam` | VERIFIED 2026-08-21 (M8-S4): **PASSED.** Copies one OD pair's **real serialized bytes** onto another pair's Redis key — every byte written by Feast, the protobuf parses, the dtype is right, nothing logs anything; a drill that planted garbage would prove the parser works. Target is **row 92**, the pair the declared set named IN ADVANCE as the one where a wrong value shows up by the largest margin (`169 -> 191`), donor derived (`14 -> 259`). → **RED exit 1, `max = 8.727e+01`, naming `od_window.od_median_duration_min`**, with **26 other sub-check lines still passing** (a gate that fails on any edit is a checksum), **sha256-identical restore** (`bd91004815981b5c…` before the plant and after), GREEN again, `git status` clean. Both parity runs inside it use `--no-write` — pinned by a test, because a drill that rewrote the table it tests would be planting evidence |
| Can `feast serve` answer at all? — the probe in front of the build (M8-S4 leg 2) | `make feast-serve-probe` (host + quarantine + the real in-cluster Redis; a READ, ~30 s) | VERIFIED 2026-08-23 (M8-S4 leg 2): `/health -> 200`, then one `/get-online-features` came back with zone 132 at **`(-73.78653, 40.646985)` `is_airport: true`** and zone 264 at **`null`** — the two-sided no-geometry property, over HTTP, thirty seconds in front of a build-and-load. It decided shape (i) by measurement rather than by preference, and its yield was the usual one: the first defect the build then hit had nothing to do with Feast (a `COPY`ed entrypoint at 0644, reported by containerd as `exec: permission denied`) |
| The QUARANTINED feature server: build + every node (M8-S4 leg 2) | `make feast-server-image` (`DRY_RUN=1` builds nothing) | VERIFIED 2026-08-23 (M8-S4 leg 2): `taxi-mlops-feast-server:feast-0.66.0-a524771`, **203 MB**, built `--no-deps` from `infra/feast/requirements-feast.txt` — the SAME pin file the host quarantine uses, so one pin file and no twin — then `kind load` and **read back off all 3 nodes with each node's own `crictl`**. The tag carries a git short sha and `-dirty` (M4-S3's rule: a mutable tag makes a stale node a wrong number instead of a loud error), and `deploy_feast_server.sh` REFUSES a `-dirty` image at exit 3. Record: `automation/runs/m8-transformer/feast-server-image.json` |
| The feature server ON THE CLUSTER (M8-S4 leg 2) | `make deploy-feast-server` (`DRY_RUN=1` mutates nothing; `TEARDOWN=1` removes its two objects and leaves Redis alone) | VERIFIED 2026-08-23 (M8-S4 leg 2): rolled out, and the accept is an **ANSWER asked from the REDIS pod** so Service DNS and cross-pod reachability are under test (a server curling itself proves neither) — zone 132 -> `(40.646985, -73.78653) is_airport=True`, **zone 264 -> `null`**, and the null half is asserted because a check that only asserts presence passes against a server answering every question with the same row. The live Deployment's image is read back **off the object**. **STATELESS**: no volume, no hostPort (M8 law 1), no backup obligation; its registry is derived by `feast apply` in the entrypoint at every start. Record: `automation/runs/m8-transformer/feast-server-deploy.json` |
| THE HTTP-seam parity: the server's answers vs the champion's OWN lookup (M8-S4 leg 2) | `make feast-server-parity` (`SERVER_PARITY_ARGS=--no-write` records nothing). A READER — deploys nothing, materializes nothing, one subprocess (the ephemeral forward on **6567**), AST-pinned | VERIFIED 2026-08-23 (M8-S4 leg 2): **`max \|ours − server\| = 0.000e+00` across 6 columns and 108 comparisons against a bar of EXACT, with `one missing` ZERO** — the load-bearing count, because it says the two sides agree about which values do not EXIST. The bar was argued for THIS path and **committed at `91ab8a6` before any record existed** (`docs/feast_server_m8.md` §3). Rows are the 16 declared hazards **imported from `taxi_mlops.serving.parity.HAZARDS`**, never retyped — 23 distinct zones, 15 distinct pickup dates — so the wire, store, offline and HTTP seams are all measured against ONE row set. The store **declines EXACTLY the zones our path has no geometry for** (`[264, 265]`), asserted in both directions. **Its first run went RED on `is_airport` and that is F-059**, repaired by comparing like with like rather than by widening the bar. Record: `automation/runs/m8-transformer/server-parity.json` |
| The CHEAP PROBE in front of a build and a KServe deploy (M8-S4 leg 3) | `make transformer-probe` (host process, two ephemeral forwards, ~1 min) | VERIFIED 2026-08-23 (M8-S4 leg 3): it runs the transformer's WHOLE request path in the calling process against the two real services — `store-backed == committed: True` over 16 hazards x 24 columns, `max |delta| 0.000e+00`, version `'2'`, and the 2031 refusal raised by `StoreCoverageError`. Roughly a minute against a ~7-minute image build plus a KServe deploy this repo prices at 2-3 defects each (F-036/F-037/F-038/F-039). It exercises the store client, the `lookups` seam, `build_matrix`, the V2 payload and mlserver; it does NOT exercise KServe's transformer wiring or the Ingress, **which is why a green probe is not an accept check**. Its yield was the usual one: the deploy's single failure was attributable in seconds because everything else was already known to work |
| The transformer BESIDE the champion (M8-S4 leg 3) | `make deploy-transformer` (`DRY_RUN=1` mutates nothing; `TEARDOWN=1` deletes exactly its own isvc) | VERIFIED 2026-08-23 (M8-S4 leg 3): a SECOND InferenceService whose predictor holds **the same champion bytes** (resolved from the alias by the same F-009 two hops) and whose transformer runs OUR image. **Accept GREEN 6/6** and it is the artifact, not a ready-list (gotcha #59): a RAW request answered **39.0019 minutes** stamped `model_version='2'` — mlserver's own stamp, forwarded VERBATIM — with `X-Taxi-Lookups` proving the store was consulted AND that F-059's two groups were not, the champion's model name **404ing on this host** (conditional on the route being live — F-060), and a 2031 quote **REFUSED at 422** naming the date. `@champion` **2** before and after; a move exits 2. It REFUSES a `-dirty` image (exit 3) and refuses a stale one (F-026's guard over `src`/`pyproject.toml`/`uv.lock`/`docker`), which fired on this story's own commit. **Three wait legs**: `rollout status` on BOTH Deployments, then `--for=jsonpath=` (F-036, never `--for=condition=`), then **the ROUTE itself** — gotcha #106 |
| THE parity through the MOVED boundary (M8-S4 leg 3) | `make transformer-parity` (`TRANSFORMER_PARITY_ARGS=--no-write` records nothing). A READER | VERIFIED 2026-08-23 (M8-S4 leg 3): **`max |champion − transformer| = 0.000e+00` minutes across all 16 declared hazards against a bar of EXACT**, argued in `docs/transformer_m8.md` §3 and **committed at `79aedb4` before any record existed** — tighter than M5-S3's 1e-6, and defensible only because the probe had already measured the store-backed matrix bit-identical on the host. Arm A builds the matrix HERE and POSTs it to `nyc-taxi-eta`; arm B POSTs four RAW fields to `nyc-taxi-eta-transformer` and a pod does the rest. Plus three checks the delta alone cannot make: both answers carry registry version **2** (read off the two ANSWERS), the pod really consulted the store, and the borough dictionary and airport constant did not cross. Rows are `parity.HAZARDS`, **imported and never retyped**, so five seams now share ONE declared row set. Table: `docs/transformer_parity_table.md` |
| p95 at the NEW boundary, beside the old one (M8-S4 leg 3) | `make transformer-load` (`TRANSFORMER_LOAD_ARGS=--no-write`). A READER — it POSTs, it times, it sets no threshold | VERIFIED 2026-08-23 (M8-S4 leg 3): M5-S4's shape EXACTLY (4 req/s, 60 s, concurrency 8, hazard mix, open loop) through the SAME `run_load` with only the payload differing — two percentiles at different shapes are not comparable. **Both arms back to back in one invocation**, so the champion is a CONTROL measured in the same minutes rather than a figure quoted across a host reboot. **p50 31.1 -> 49.3 ms (+18.1), p95 113.1 -> 118.1 (+5.0), 240/240 ok on each arm, ZERO errors on both, 4.01 req/s achieved on both, version `['2']` on both.** **Quote the p50**: the p95 delta was **+23.0 ms** in a run eight minutes earlier while p50 held at +16.8, and both records are tracked (`transformer-load.json`, `transformer-load-run1.json`) so that is checkable rather than asserted — the tail is laptop contention, the reading M6-S2 already refused once |
| Gate check M8 | `make verify-m8` | VERIFIED 2026-08-23 (M8-S5 leg 2): **GREEN 51/51 sub-checks in 7 sections, exit 0** — the wall (`uv.lock` **byte-identical to the `m7-closed` tag**, `feast` **ABSENT** asked of `uv pip list` and not inferred from the lock, the conflict re-read live (`pandas<3,>=1.4.3` vs 3.0.5), the wall **one package wide**, 66 exact pins with `--no-deps`, the import law both directions by **ast**) · the feature repo (the APPLIED registry's 4 views and 5 entities equal to what `ast` parses out of `definitions.py` — two independently produced lists; `feast plan` 0 substantive, F-055's only checkable statement; no registry.db TRACKED and the generated one gitignored, asked of `git check-ignore`; every view carrying a verdict, 2 CATALOG-ONLY, the losing number labelled a SAMPLE number) · **the four seams, all at `0.000e+00` against a bar of EXACT that is PARSED from the prose arguing it, `one missing` ZERO on every column, and all four bars COMMITTED BEFORE the records they judge — 678 s · 356 s · 320 s · 546 s, read off `git log --diff-filter=A`** (M8 law 4 from git, not from a sentence) · the PIT proof as a DIFFERENCE with two anchors (honest vs naive disagree on every time-varying column, **the naive answer IS our own full-window table**, the honest one reconciles with `aggregates.transform` at zero, 10 rows told nothing, 7 distinct windows, F-056's shortfall CLASSIFIED with UNEXPLAINED 0) · **five live questions** (champion 10.665224 min at `model_version='2'` **exactly** the recorded value; the transformer answering the same hazard from four RAW fields at `|Δ| = 0.000e+00` with `X-Taxi-Lookups` naming the two groups that did NOT cross; the feature server two-sided; **57,688 keys** at `noeviction`; one PromQL query — F-043's, and it found **F-061**) · F-059 as a TYPE by ast · the page (12 rows, all verdicted, **3 ADOPT / 5 SURPASS**, per-row provenance) · **the alias law in its strong form: not one registry version created after the `m7-closed` tag**. **RE-RUNS NOTHING and MINTS NOTHING**, pinned by `tests/unit/test_verify_m8.py` (36 tests) incl. the five-question count. No skip flag, no fast mode (M1's rule, **eighth** inheritance). Transcript: `docs/verify_m8_transcripts.md` §1 |
| Prove the M8 gate can go RED | `make verify-m8-redteam` (`bash scripts/verify_m8_redteam.sh`) | VERIFIED 2026-08-23 (M8-S5 leg 2): rewrites ONE count in `automation/runs/m8-online/online_parity.json` — a pickup-zone column's `both_missing` **13 → 0**, the column CHOSEN from the record rather than typed — leaving `compared`, `mismatches`, `max_abs_delta`, `one_missing`, the headline delta and the `PASSED` verdict untouched. **It is not a lie about a measurement; it is what a correct-looking measurement of the wrong population reports** — zero missing values is exactly what a comparison that dropped nulls prints, and it looks BETTER than the truth. → **RED exit 1 with 3 FAILs from THREE artifacts**: the run's own two-sided no-geometry assertion, the independently-built ANCHOR block inside the same record, and `docs/feast_online_parity_table.md` — the blueprint's named accept artifact and the only witness a human diffs. **48 sub-check lines still ran and passed**, and **the four-seam headline leg stayed GREEN by design** — what separates a gate that fails on a WRONG POPULATION from one that fails on any edit. Restored under an EXIT trap, sha256-verified (`153c4399deab…`), `git status` clean → **GREEN 51/51**. Touches no pod, no image, no Redis key, no MLflow run, no registry version, no alias, no rule and no traffic |
| Gate checks | `make verify-m0` … `verify-m8` | M0/M1/M2/M3/M4/M5/M6/M7/M8 live |
| The stakeholder demo page (M9-S1) | `make demo-page` regenerates it from its three sources · `make demo-page-check` is the write-nothing twin | VERIFIED 2026-08-23 (M9-S1): **265 zones** from `data/reference/taxi_zone_lookup.csv`, **4 raw inputs** from `transformer.RAW_INPUTS`, and a default trip that is a PUBLISHED parity row — so the first thing a stakeholder sees is checkable against a record. `--check` regenerates in memory and diffs against git; a unit test runs it, and a second asserts regeneration is deterministic. **Its first run substituted the template's own explanatory comment** and shipped 795 `<option>` elements instead of 530 — gotcha **#110**, now guarded by an occurrence COUNT (`TOKEN_COUNTS`), because every one of the three copies matched the CSV |
| Deploy the demo + its route (M9-S1) | `make deploy-demo` (`DRY_RUN=1` mutates nothing; `TEARDOWN=1` removes its four objects and touches nothing else) | VERIFIED 2026-08-23 (M9-S1): ConfigMap rendered FROM `demo/index.html` (the file in git is the only copy), a `busybox:1.38.0` httpd Deployment at the digest the data stager already pins, a ClusterIP Service and ONE **host-less** Ingress. **Three wait legs**: `rollout status`, then the pod template's page-sha256 == the committed file's, then **the ROUTE itself** under the origin the browser will use (F-037/F-060, gotcha #106). It then asserts the two invariants it shares a server block with — **`/healthz` 200 and `/` 404** — rather than leaving the next `make deploy-serving` to discover them. F-039's precondition is asked of the CLUSTER: it refuses to write to any of its four names that carries `ownerReferences`. `DRY_RUN=1` verified to leave the namespace with no demo object. Deploys no model and cannot name the registry in code (AST-tested) |
| THE demo accept — real requests, sent the way the PAGE sends them (M9-S1) | `make demo-accept` (`DEMO_ACCEPT_ARGS=--no-write` records nothing). A READER | VERIFIED 2026-08-23 (M9-S1): **PASSED 9/9.** The endpoint, the request schema and the payload are READ OUT of `demo/index.html` and posted with **no Host header override** — the one thing a browser cannot do and every other client here does. Bar **EXACT**, argued in `demo/README.md` §4 and committed BEFORE the record existed: **39.00193715359812 vs the recorded 39.00193715359812, |delta| = 0.000e+00** against `automation/runs/m8-transformer/transformer-parity.json`'s `federal-holiday` row (matched on `(at, pu, do)`, never typed) · `model_version` **'2'** read off the ANSWER · `X-Taxi-Lookups` equal to the recorded string · the served page **byte-identical to git by sha256** (47,147 bytes, fetched back through the route) · a **2031** quote **422**-refused naming the date · the no-geometry path 264 -> 264 **quoted at 8.2445 min, not broken** · and the CHAMPION's own model name **404** on this origin, asserted only after a real quote succeeded (F-060). The PO-observed box is recorded **OPEN** in the record itself |
| The online store's key composition and refill cost — the input to §9's bars, measured BEFORE them (M9-S2) | `make store-watch-headroom` (`HEADROOM_ARGS=--out <path>`). A READER — it reads, it records, it argues nothing | VERIFIED 2026-08-23 (M9-S2): **three witnesses agree at 57,688 keys** — `count(distinct <entity keys>)` over `data/feast/*.parquet`, the count `automation/runs/m8-online/materialize.json` recorded on 2026-08-21, and the live `DBSIZE` off the running server. Per view: `zone_static` 263 (0.46%) · `calendar_day_flags` 4,383 (7.60%) · `od_window_stats` 46,938 (81.37%) · `pu_hour_window_stats` 6,104 (10.58%). **The transformer's ENTIRE dependency is 4,646 keys — 8.054%**, and zone 132's centroid is **one key of 57,688**, which is what killed the key-count bar before it was written: lose exactly the key that breaks every JFK quote and `DBSIZE` moves 0.0017%. Also read live: `maxmemory-policy noeviction`, 14.32 MiB against a 512 MB cap — so there is **no partial-loss mechanism** and the realistic population is bimodal. It ran BEFORE `docs/slo_serving.md` §9 existed and both landed in `cedb9e8`, which is what makes M8 law 4 checkable from git here |
| A-12/A-13's metric source: DBSIZE + a four-claim canary, pushed (M9-S2) | `make store-watch` (`STORE_WATCH_ARGS=--no-push` prints and pushes nothing; `--out <path>` records). A READER — it issues NO verdict and contains no bar | RE-VERIFIED LIVE 2026-08-24 after a host restart: `keys 57688` == `keys expected 57688`, and all four canary claims **1** through the feature server's own `/get-online-features` wire — `store_reachable` · `zone_answers` (132 returns a non-null centroid) · **`nonplace_declines` (264 returns null, and not an error)** · `calendar_answers` (2019-07-04 returns its holiday flags) — then `pushed 7 series -> job/taxi-store-watch/store/feast-online`. **No threshold lives anywhere in it**: the bars are the SELECTORS of three rules, argued in `docs/slo_serving.md` §9. `store_reachable` is REPORTED as a 0 rather than withheld, inverting `push_serving_version.py`'s refusal rule on purpose — an unreadable store IS the measurement. Ephemeral forwards on **6568/9100**, deliberately off every port a running drill owns (#55 has cost this program a session); neither is a route (M9 law 1) |
| Empty the online store, watch A-12 fire, watch the rider be REFUSED, refill, watch it clear (M9-S2) | `make store-watch-drill` (`DRILL_ARGS=--dry-run` writes the prediction and mutates nothing; `--phase health\|empty\|unreachable`; ~9 min, and the empty phase is a **real total outage of the transformer's dependency**) | VERIFIED 2026-08-23 (M9-S2): **PASSED — 28 checks across three phases, 0 failures** (`health` 5/5 · `empty` 19/19 · `unreachable` 4/4), prediction written to disk before the first mutation, committed in `408b472` and pinned by a test against the drill's own literal. `FLUSHDB` **57,688 -> 0**; the rider's quote came back **HTTP 422 — predicted 422, and the kickoff's superseded 503 is kept beside it in the prediction rather than quietly replaced**; **`OnlineStoreCanaryFailing` and `OnlineStoreIncomplete` both FIRED at T+162.2 s and both reached Alertmanager**, with the failing claims read **per series** (`['calendar_answers','zone_answers']`) and not per rule name (gotcha #93); **all five must-not-fire negatives inactive** (A-13, A-2, A-5, A-11, A-4); **the champion's own wire answered 39.0019 minutes throughout** — the store backs the transformer's raw boundary, not the 24-column wire; refill **57,688 keys in 9.9 s**; both rules cleared 30.0 s / 0.0 s and the real numbers went straight back, so **the board ends carrying the truth** (M7-S3's rule). It calls the refill with **`--no-record`** and a comment saying why — that is **F-063**, found by its own first run |
| Validate the alert rules, now sixteen (M9-S2) | `make alert-rules` | RE-VERIFIED 2026-08-23 (M9-S2): **16 rules validated across 10 signal ids** (was 13 across 9) — **DATED CORRECTION 2026-08-24 (M9-S8), original kept above: the id counts are wrong and the rule counts are right. `infra/monitoring/alerting_rules.yml` carries 16 rules across **13** signal ids (A-1…A-13, with A-12 holding two rules), and `git show m8-closed:` says the before-state was 13 rules across **11**. "Ten ids" was true at M7-S3 and was carried forward twice without recounting — the exact shape M9-S8's `make readme-check` now prevents in the README, where the same fact is read out of the rules file on every run** — the three new ones printed with their `for:` and severity — `A-12 OnlineStoreCanaryFailing for=2m critical` · `A-12 OnlineStoreIncomplete for=2m warning` · `A-13 OnlineStoreWatchdogAbsent for=10m warning`. Every one carries an `annotations.why` or the renderer REFUSES it, which is what stops a threshold shipping without the argument beside it. Read back off the live `prometheus-server` ConfigMap: all three present, **`health=ok`, and NO pod restart** — the configmap-reload sidecar, M6-S1's measurement re-confirmed a fourth time |
| Gate check M9 — the program's last crossing | `make verify-m9` | VERIFIED 2026-08-24 (M9-S4): **GREEN 45/45 sub-checks in 7 sections, 4.450 s, exit 0** — the demo page (530 `<option>` elements == 2 x the CSV's 265 zones, the request schema equal to `transformer.RAW_INPUTS` on wire name AND datatype AND source field, the default trip a PUBLISHED parity row, TLC's two non-places RENDERED and quotable at 8.2445 min, the served page byte-identical to git by sha256 read three ways, and the page posting to the RAW boundary and never the champion's 24-column wire) · §9/M9's accept answered line by line with the bar **PARSED** out of the section that argues it (`EXACT`, |Δ| 0.000e+00, cross-artifact against the transformer-parity row matched on (at, pu, do)) · **law 4 from git four times** (133 s · 0 s · 1878 s · 700 s) · the watchdog's three rules with **NO NUMBER on either side of A-12b**, the one bar (1800) argued in §9 specifically, and **every series the rules SELECT produced by `store_health`** — a rule selecting a series nobody pushes stays `health=ok`/`inactive` forever · **THREE live questions** (one quote through the DEMO's own request path at 39.00193715359812 stamped with the version the alias resolves to; the three rules LOADED `health=ok` with every `for:` equal to the file's; **57,688 keys with THREE WITNESSES agreeing**) · the drill's 28/0 with its prediction FIELD-EQUAL to the committed file · F-057 and F-054 as **derived** properties · the pointer, the lock, the pins, the nine inherited gates NOT nested, and **F-062 required to be an honest OPEN row**. **RE-RUNS NOTHING**, pinned by `tests/unit/test_verify_m9.py` (33 tests) incl. the three-question count and the absence of its predecessors' questions. No skip flag, no fast mode (M1's rule, **ninth and final** inheritance). **The PO-observed box is printed as an OPEN ITEM in §2 and in the GREEN banner and is never rendered green** — a test pins all three halves. Transcript: `docs/verify_m9_transcripts.md` §1. **RE-DERIVED AND RE-RUN 2026-08-24 (M9-S5): GREEN 45/45 with the box CLOSED** — §2's box leg now asks the two-state property (**OPEN and honest** — the invitation live in AWAITING_PO — **or CLOSED and CITED** — an entry the inbox really holds, carrying the observer's own words, compared on WORDS not bytes because a quoted note is wrapped inside a blockquote), the banner's box paragraph is DERIVED from the record §2 just judged, and a citation-free CLOSED is RED: demonstrated twice (no citation → *"it is CLOSED and cites no AWAITING_PO entry"*; a citation the inbox does not hold + a paraphrase → *"an entry this inbox does not hold; the note it quotes appears nowhere"*), **44 sub-check lines still passing each time**, sha256-identical restore (`ceec3ca26dbe…`), clean tree. Sub-check count unchanged — the leg was re-derived, not removed (gotcha #50). Tests now 35 |
| Prove the M9 gate can go RED | `make verify-m9-redteam` (`bash scripts/verify_m9_redteam.sh`) | VERIFIED 2026-08-24 (M9-S4): shortens ONE number in `automation/runs/m9-store-watch/headroom.json` — `expected_keys.total` **57,688 -> 57,425**, short by exactly the **263** keys of the view CHOSEN from the record as the smallest (`zone_static`, which holds every centroid the champion's nine geometry features are built from), derived from the record's own fields and leaving `per_view`, `transformer_dependency_keys`, the live_store block and the materialization block untouched. **It is not a lie about a measurement; it is a correct-looking expectation of the WRONG POPULATION** — and because A-12b compares metric-to-metric with no literal on either side, no rule is loosened and every alert stays `inactive`, while the store it describes could lose ALL its geometry and still satisfy the alert that exists to notice. → **RED exit 1 with 3 FAILs from THREE artifacts**: the record's own per-view arithmetic, the live `DBSIZE` beside the M8-S4 materialization record, and `docs/store_watchdog_m9.md` — the only witness a human reads, and **the leg that reads it had to be built for this drill**. **42 sub-check lines still ran and passed**, and the **no-number leg and law 4's ordering leg stayed GREEN by design** — what separates a gate that fails on a wrong number from one that fails on any edit. Restored under an EXIT trap, sha256-verified (`b875049f8289…`), `git status` clean → **GREEN 45/45**. Touches no pod, no image, no Redis key, no MLflow run, no registry version, no alias, no rule, no page and no traffic |
| Pin the two scanners this program audits itself with (M9-S9) | `make security-tools` (`DRY_RUN=1` installs nothing; `FORCE=1` re-downloads; `make security-tools-check` reads the versions back) | VERIFIED 2026-08-24 (M9-S9): **trivy 0.74.0** and **gitleaks 8.30.1** into `~/.local/bin`, each tarball matched against the publisher's `*_checksums.txt` and each installed binary's sha256 RECORDED in `automation/runs/m9-security/tools.json`. Versions read BACK off the binaries and compared with the pins — a disagreement exits 2. The record states what the checksum check does NOT prove (same origin, same TLS session; sigstore unverified for want of `cosign`) rather than leaving the reader to assume a chain of trust |
| The pre-publish audit (M9-S9) | `make security-scan` (`SCAN_ARGS="--stage tree-secrets"` is the seconds-long probe; `--no-write` records nothing) | VERIFIED 2026-08-24 (M9-S9): **0 secrets in git, `publishable: true`**, over every file on this disk, **every commit on every ref** (`--log-opts='--all --full-history'`), the three images this program builds and `uv.lock` + the manifests. **1 acknowledged** (the M6 gameday's deliberately wrong MinIO secret, its argument RE-DERIVED by base64-decoding the bytes actually found) and **10 local-only** (`.env`, each carrying `git check-ignore -v`'s own answer). CVEs recorded not chased — 201 · 196 · 879 for the three images, 5 dependency + 76 misconfiguration for the tree — with the actionable subset split out by trivy's `Class: lang-pkgs`: **`sqlparse` 0.5.5, three HIGH, fix in 0.6.0**, NOT bumped because `uv.lock` is asserted byte-identical to `m7-closed` (PO fork, AWAITING_PO 2026-08-24-5). It exits **1** on a blocking finding and **2** on a stale acknowledgement. Write-up: `docs/security_audit_m9.md` |
| Prove the secret scan can FIND one (M9-S9) | `make security-scan-redteam` | VERIFIED 2026-08-24 (M9-S9): **PASSED — 16 checks, 0 failures.** An AWS-shaped pair GENERATED at run time (a drill carrying a credential-shaped literal becomes a finding in the scan it tests) is planted twice: in an untracked, unignored working-tree file → **BLOCKING, reason `untracked AND NOT ignored`**; and in a real COMMIT on a scratch branch **asserted NOT reachable from HEAD** first, so what is under test is `--all` and not HEAD's ancestry → **BLOCKING, naming the commit**. Neither arm prints the secret. Then the plant is DESTROYED — branch deleted, reflog expired, `gc --prune=now` — and `git cat-file -e` is ASKED whether the object is gone, before the untampered scan comes back **GREEN with 0 blocking**, the tracked record sha256-unchanged (both arms `--no-write`, pinned by a test) and `git status` clean. **It was FLAKY on its first outing and that is F-071** — see the story section |
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
changed for the worse.** Newest (M4-S1): **a component printed a claim it was
structurally incapable of checking — the gate certified the holdout "untouched
by selection" for a bake-off that had ranked five arms on it (#51; ask of any
self-assertion, *could this component tell if it were false?*)**; **the fix that
changes a VALUE leaves the hazard in scope, the fix that changes the ORDER
removes it — and a regression test built from the real run passes under both
rules (#52)**; and **two tests went red for finding a module name in a DOCSTRING,
in one file, minutes apart (#53 — in a repo where prose is load-bearing, a check
about code structure must parse code)**. Newest (M4-S2), both about VERIFIERS:
**a backup's readability check could not detect the truncation it named (a `-Fc`
archive's TOC is at the front, so `pg_restore --list` passes on a half-written
file) and hung on a 1 MB dump having worked on a 1.2 GB one — #51's question
asked of a verifier (#54)**; and **the replacement then went red twice for its
own reasons: the completion marker is not the LAST line (Postgres 16.11 appends
`\unrestrict <token>` after it) and `grep -qF "$MARKER"` read the marker's
leading `--` as a flag — a verifier that fails for its own reasons and blames the
artifact is #50 one layer down (#55)**. Newest (M4-S3): **`bash -lc` inside a
container is a LOGIN shell, so it rebuilds PATH, drops the image's own venv, and
every `ModuleNotFoundError` gets reported as whatever the check was looking for —
#55 a third time, and it cost one wrong RED verdict (#56)**; **a `chown -R` at the
end of a Dockerfile duplicates every file it touches (1.7 GB, 139 s here) and
hides because the size everyone quotes is the CONTENT size, not the unpacked one
(#57)**; and **`.dockerignore` is not hygiene — `data/` is not one thing, and the
1.1 MB of COMMITTED lookup tables under it are what the feature path reads, so
excluding the directory wholesale builds an image that imports perfectly and
cannot build a feature. What caught it was running the project's own unit suite
INSIDE the artifact (28 failed + 10 errors), not reading the Dockerfile (#58)**.
Newest (M4-S4), and the first is the worst kind: **a green line over a dead run —
`flyte run --follow` EXITS 0 when the run it followed FAILED, so a check written
against the exit code printed `ok … six stages on-cluster` for a run that died on
ErrImagePull, with a run name and a readable outputs blob to agree with it; only
the outputs' CONTENT differed (`o0=None`). Assert POSITIVELY on the artifact the
thing exists to produce, never on the absence of an error (#59)**; **backticks in
an UNQUOTED heredoc are command substitution, so a pod manifest's own explanatory
comments naming `tar`, `du` and a docker command RAN them and spliced their output
into the YAML, which failed to parse on a line unrelated to the cause — #35 and
#53 a third time, and the fix is that prose must not sit anywhere a shell or a
parser will read it as code (#60)**; and **a security allow-list is replaced, not
extended, when you set it, and MLflow's host-header middleware compares the WHOLE
header INCLUDING the port — so the fix that let the first in-cluster client in
gave every host-side client the same 403, and the tell was
`curl -H 'Host: localhost' 127.0.0.1:5000/health` returning OK while
`curl localhost:5000/...` returned 403 (#61)**. Newest (M4-S4 second session),
and both were found by a 40-second probe standing in front of a 35-minute run:
**an apostrophe inside `${VAR:+word}` opens a quote, so bash swallowed four lines
and blamed a `$!` five lines below on a port-forward that was perfectly fine —
the fourth time prose has sat where a parser reads it as code (#62)**, and **a
bar measured on the wrong clock called a 98.7% saving a failure, because a
one-stage rerun is mostly the launch overhead no cache can touch; the fix was the
right quantity, not a looser threshold (#63)**. Newest (M4-S5), and both are about
INSTRUMENTS rather than systems: **a protobuf answers `getattr` for its own fields
only, so a field name misspelled in the singular returns the supplied DEFAULT
instead of raising — the run-actions reader reported `attempts: 0` for every action
of every run it was ever pointed at, including committed evidence, and `0` is
exactly what an un-retried action should say (#64, F-027)**; and **`--follow`
follows the LOG STREAM, which ends when the FIRST attempt's container exits, so
the CLI returned 7 seconds into a task that had two retries still to come and a
check read `RUNNING` as the final answer (#65 — sibling of #59: the CLI's return
says nothing about the run's outcome and nothing about its completeness)**.
Newest (M4-S5 leg 2): **rebuilding the task image invalidates every cached Flyte
stage, because the cache key covers the whole task SPEC and not just code, inputs
and data — five stages read `CACHE_POPULATED` on a month they were already
populated for, with the same data pin and untouched function bodies, purely because
the tag is the git short sha and every commit mints a new image. It is arguably
right and it agrees with F-026 from the other side; the unpriced cost is that ONE
commit under `src`/`scripts`/`analytics`/`docker`/`pyproject.toml`/`uv.lock` turns
the next full-data run back into a 31-minute fit, so a cache drill must hold the
image constant and a gate must read RECORDED cache evidence rather than re-asking
about the latest run (#66)**.
Newest (M4-S5 leg 3), and all three are about CHECKERS rather than systems: **a
checker's "every X must have Y" goes red on the one X that was BUILT without Y —
`verify-m4` demanded a parent action of every recorded run and named the retry
probe, which is designed to have neither a parent nor a success; the repair is to
DERIVE what counts as an X, never to add an exclusion list keyed on a name (#67)**;
**a test that forbids RUNNING a command catches the message telling a human to run
it, and catches a namespace named after a CLI — `make pipeline` matched the gate's
own advice line and `flyte get` matched `kubectl -n flyte get deploy`, so a needle
must sit where a shell would START a command (#68, #35's rule failing on a TEST
rather than on prose)**; and **a milestone gate can be replaying evidence that is
not in the repository and say the opposite in its own header — `automation/runs/`
was gitignored, so `verify-m3`'s replay inputs and every record `verify-m4` reads
were invisible to review, which is precisely the edit both red teams simulate. Run
`git check-ignore -v` before writing "committed" near a verifier (#69, F-029 —
the STATE was fixed at M5-S1 by tracking the records; the check is the lesson,
and it is a two-second command)**. Newest (M5-S1): **a positive
discriminator can name a signature the deployed thing deliberately SUPPRESSES —
the serving route's accept check demanded a `Server: nginx` header and went RED
over a healthy, correctly-scheduled controller serving a correct 404, because
modern ingress-nginx omits that header on purpose. #59 says assert on a positive
artifact; it does not say check that the artifact EXISTS. Ask the server:
`GET /healthz` -> 200 is the controller's own endpoint and `/nginx-health` 404s
(#70, sibling of #55 — a verifier failing for its own reasons and blaming the
artifact)*.
Newest (M5-S2): **a wait that the thing you are REPLACING can satisfy is not a
wait — on a RE-deploy `kubectl wait --for=condition=Ready inferenceservice`
returns in milliseconds because the OLD predictor is still serving, so the
accept check interrogated the pod being replaced and printed a pass. Only the
subject matter made it visible: the change under test was a version stamp, so
the predecessor answered `(unversioned)`. Ask of any readiness wait, could this
condition be true right now for a reason that has nothing to do with my change?
(#71, the third shape of #59/#65)**.
Newest (M5-S3): **`json.dumps` emits the bare token `NaN` BY DEFAULT — valid
Python output, invalid JSON — so a correct feature matrix serialises into a
document no parser accepts and the failure comes back from the far side as a byte
offset (`"loc":["body",1241]`) naming neither the feature nor the row. It had been
answering 422 to ~1% of all trips since the endpoint existed. Missing travels as
`null`, an infinity is REFUSED rather than laundered, and `allow_nan=False` makes
the next such path fail loudly on THIS side (#72, F-030)**; and **a red team that
goes GREEN under its own tampering has found something — read it before you
loosen it. The parity drill's first arm rotated the request's input ORDER, on a
property the client's docstring asserted, and measured 0.000e+00: the property was
false (this runtime pairs by NAME, via the logged signature). Move the plant to a
cause the system CAN express, and CORRECT the claim rather than delete it when the
practice it prescribed is still right for other reasons (#73, F-031 — #51's
question asked of a drill)**.
Newest (M5-S5): **a check that compares a machine's number with a human's
sentence needs a precision policy AND a tokenisation policy, and the second is
the easier to get silently wrong — demanding a runbook quote `104.226` failed a
document sensibly writing `104.2 ms` (#42 in prose), and the obvious fix, a bare
substring search, would have matched `14` inside `14.53` and let the red team's
planted number straight through (#76)**.
Newest (M6-S1), and both are about things that look FINE: **a rollout that can
never complete is indistinguishable from a system with nothing wrong with it — the
ingress controller's surge pod sat Pending for 10 minutes unable to bind a hostPort
the old pod still held, while the route served 840/840 and the helm upgrade headed
for a silent 20-minute timeout; `hostPort` + 1 replica + a single-node selector
FORCES `Recreate`, and pod AGE is the one-command answer to "did the thing I
changed actually get replaced?" (#77, F-033)**; and **a scrape target being `up`
says nothing about whether anything is measured, and a component that was never
DISCOVERED is not even a target — three board panels returned zero series with
every target green, for three different real reasons (an unannotated metrics
Service, a `rate([1m])` at a 1-minute scrape interval, and one genuinely-down
rbac-proxy endpoint). Execute every panel's own query and treat ZERO SERIES AS A
FAILURE: an empty rectangle is what a quiet system looks like, so green must not be
the default rendering of "no data" (#78, #59 applied to a dashboard)**.
Newest (M6-S2), and both are about things that were *reasoned* rather than
measured: **`kubectl wait --for=condition=X` silently requires the controller to
have updated `observedGeneration`, so a perfectly healthy resource can be
unwaitable forever — `make serve` hung fifteen minutes and then FAILED over an
InferenceService with every condition `True` and its pod `Running 1/1`, because
KServe v0.20.0 leaves observedGeneration behind on every re-deploy while kubectl
v1.36 (correctly) refuses to read conditions that may describe the previous spec.
The tell is that `--for=condition=` times out for EVERY condition on the object
while the `--for=jsonpath=` form reading the same condition succeeds in the same
second; one `kubectl get -o jsonpath` over generation/observedGeneration answers
it (#79, F-036)**; and **a 15-second outage is what a DESTROYED pod costs, not
what a DEPLOY costs — three mutations measured at 14.53/15.0/18.24 s made
"a re-deploy is ~15 s" look like a safe analogy, and the real number is 0.5 s,
because at one replica `maxUnavailable: 25%` floors to ZERO and a surge pod must
be ready before the old one goes. Three numbers agreeing with each other is not
evidence about a fourth mechanism (#80)**.
Newest (M6-S3), and the first two are about mechanisms that LOOK configured:
**a canary that is linked, logged clean and moving zero traffic is
indistinguishable from a canary at 0% — ingress-nginx keys backends by
`<ns>-<svc>-<port>` and a backend holds ONE role, so pointing a canary at a
Service some non-canary Ingress also claims silently discards the weight (0 of
200 moved, `{weight: 0, weightTotal: 0}`, while the main backend still listed it
under `alternativeBackends`). KServe generates an Ingress per InferenceService,
so the natural canary target always already has one and the natural
implementation is the broken one. Verify a split from traffic COUNTERS, never
from its own configuration (#81, ADR-011 condition 1)**; and **the V2 model name
is in the URL PATH, so two InferenceServices cannot share a split without both
answering to the same name — canary traffic 404s before any signature is
consulted, and `rewrite-target` cannot fix it because ingress-nginx applies only
`canary-*` annotations from a canary Ingress (#83)**. Then two about waits and
edits: **`kubectl annotate isvc` is not a metadata edit — KServe copies isvc
annotations onto the pod template, so a "spec-neutral" nudge rolled the
champion's only predictor twice and cost 174 of 200 requests a 502; on a resource
an operator templates from there is no metadata-only field until you have checked
what it copies downstream (#82, F-038)**; and **a readiness wait can be about a
different OBJECT than your next step uses — `rollout status` and the ISVC's Ready
condition both passed while the generated Ingress was 6 seconds old and nginx had
not loaded it, so the accept check got a bare 404 over a perfectly good service.
#71's family with no predecessor in sight; wait on the route by ASKING it
(#84, F-037)**.
Newest (M6-S4), and the first is #81 wearing a different cause: **a
hand-authored object must not take a name an operator GENERATES — the collision
is accepted, works for seconds, then undoes itself. A canary Ingress named
`nyc-taxi-eta-canary` (exactly what KServe generates for the isvc of that name)
took the annotations onto the CONTROLLER-OWNED object and had them reconciled
away: 0 of 420 requests moved at weight 10, 3 of 300 at weight 100 — and those
three are the window between apply and reconcile, the only tell there is. Worse,
the symptom is byte-for-byte #81's, which this program had just spent a story
learning, so the obvious diagnosis was wrong. `kubectl get <kind> <name> -o
jsonpath='{.metadata.ownerReferences[*].name}'` before writing to anything you
did not create; and take the precondition from the CONTROLLER's runtime state,
never from the annotation you just applied (#85, F-039)**. And: **"a deploy costs
0.5 s" is not "a rollback costs 0.5 s" — the asymmetry is in the SCHEMA, not the
pod. A rollback's second move changes what every client SENDS while the old pod
still serves: v2→v1 cost 27.93 s of failing requests (55 of 85 probes, almost all
`HTTP 500` at MLflow's logged signature) against 0.501 s and a single 502 for
v1→v2. The direction that hurts is the one that REMOVES features — a 24-column
request to a 5-column model is tolerated, a 5-column request to a 24-column model
is missing inputs and refused. The remedy that follows (deploy first, move the
config line last) is a CONSEQUENCE of the measurement and must be rehearsed
before it is trusted, never substituted mid-incident (#86, F-040)**.
Newest (M5-S4), and both are the same disease — **measure the quantity you will
quote**: **a load test run at the CPU limit measures the QUOTA, not the service,
and "held its rate with no errors" cannot detect that, because saturation shows
up as latency and not as failure — read `cpu.stat`'s `nr_throttled` across the
window, not just the mean (#74)**; and **an outage is not the span from the first
error to the last one — `last_error - first_error` called a 13-second downtime
plus a saturation error tail a 182-second outage, and it was headed for a runbook
(#75). Anchor the outage on the first FAILURE and close it on the first SUCCESS
after that; anchoring the start at the event overstates it, and anchoring recovery
on "the first success after the event" understates it catastrophically. Both were
caught by replaying the real timeline as a test fixture.**
Newest (M6-S5), and all three are about the ARGUMENTS written beside correct
alerts: **a `rate(...[5m])` window is EMPTY when an event begins, so a threshold
argued from the steady-state ratio is an argument about the wrong quantity — a
15-second outage 30 seconds into a load run made the edge 5xx share peak at 0.50
against a 0.10 bar, and what stopped the page was the `for: 5m` sustain, not the
threshold. The same mechanism runs backwards on the way up: A-6's throttled
fraction needed 244 s to climb 0.41 → 1.00 as its window filled, so its 10-minute
sustain started four minutes after the load did. When you write a bar, ask what
the denominator holds at t=0, and remember an on-call will watch alerts sit
`pending` through every ordinary self-heal (#87, F-041)**; **two alerts' arrival
ORDER is decided by their `for:` windows, never by the causal story about which
condition happens first — A-7's own annotation claimed it fires before A-5
because "a pod that never initialises never had a replica to lose", and with both
expressions true in the same scrape the 2m rule beat the 3m rule by exactly sixty
seconds (#88, F-042)**; and **a component under stress is an unreliable reporter
of its own stress — the predictor's `/metrics` went from 4 ms to 4.613 s and one
scrape FAILED under saturation, which made A-1 clear itself in the middle of the
event it was firing about. "Measure at the edge because a dead predictor cannot
report its absence" is the loud version; this is the quiet one, and the tell is a
firing alert going inactive while the symptom persists. An idle second instance
of the same exporter, scraped by the same job, is the cheapest possible control
(#89, F-043)**.
Newest (M6-S5 leg 2), and both were found by the M6 gate on its own first runs:
**a prose-vs-record check with no precision FLOOR passes against a number the
record does not hold — `verify-m6` rendered a recorded 13.75 at ZERO decimals as
`14`, which appears in almost any document of any length, so the red team's
planted 13.501 rendered as `14` too and matched. #76 arriving through ROUNDING
instead of through tokenisation, and the two properties are independent: #76's
anchors stop `13` matching inside `13.75`, this floor stops `13.75` becoming
`14`. Both were only ever visible because the plant was close enough to be
plausible — a drill planting `999` goes green and teaches nobody anything
(#90)**; and **the label an artifact PRINTS is a different artifact from the
label in its header, and only the printed one is read during an incident — the
restore's "scratch-rehearsed" label moved in the script header, the MANIFEST
text, the write-up and CLAUDE.md (which then asserted every artifact said so),
while `scripts/platform_backup.sh`'s own `echo` still told every future operator
`restore NOT rehearsed` and the deployments ledger still carried the old claim.
When a status label moves, enumerate the artifacts that carry it INCLUDING the
runtime output, make a check assert the COMPOUND claim, and correct a historical
ledger row with a dated note BESIDE the original rather than by rewriting it
(#91, F-044)**.
Newest (M7-S3), and all three are about MONITORING PLUMBING rather than about
systems: **a pushed metric arrives with the WRONG `job` label unless
`honor_labels: true` says otherwise, so every rule selecting on it matches
nothing while staying `health=ok` and `inactive` — indistinguishable from a
healthy system, and the near-miss is worse: an annotation would have got the
gateway scraped a SECOND time by a label-mangling job, giving two contradictory
copies of every number (#92)**; **a checker whose unit of judgement is coarser
than the fact it judges reports a failure over a perfect result — the drift
drill keyed its fired-at map on the alert NAME while its prediction is per
(alert, month), and printed an `ok … as predicted` line and a `FAIL … predicted
INACTIVE` line about the same rule in the same run. The repair is the per-SERIES
read, which is strictly STRONGER (a bar so low an ordinary January trips it
passes a name-level check and fails this one), and the PREDICTION object was
untouched because the defect was in the judge (#93 — #67 with the grain wrong
instead of the population wrong)**; and **a second witness that cannot be READ
reports maximum disagreement, which is the most alarming thing it could say and
the least true. Read a third-party payload's SHAPE off a real object before
parsing it, and check the failure DIRECTION of any cross-instrument check: one
that degrades toward "they agree" hides its own breakage, one that degrades
toward "they disagree" screams, and both are wrong — the code must distinguish
"no verdict" from "a verdict of disagreement" (#94)**.
Newest (M7-S4), and all three are one lesson arriving three times — **the last 5%
of a long job is the code nothing has run, and the channel it reports through is
narrower than the thing it is reporting**: **a 28-minute fit reached a correct
REFUSE and died serialising it, on an attribute that never existed; every test of
that module asserted on its SOURCE, and a string test sees a field being written
and cannot see that the field does not exist — make the post-expensive step a
FUNCTION callable in microseconds on a real object (#95)**; **an unhandled crash
exits with a status your program may already have given a meaning, so handle the
case you did not enumerate and exit OUTSIDE the vocabulary — and note a bare
Python exception exits 1, which in this repo's retrain vocabulary means REFUSED
(#96)**; and **`make` collapses every failing recipe to exit 2, so that whole
vocabulary — the new 4 included — dies at `make detach`, and 2 is a word already
in use. Stop reading verdicts out of exit codes: a refusal writes a RECORD and a
crash writes nothing, so the record's presence is the discriminator (#59's rule),
the recipe echoes its CLI's `$?` and re-exits with it, and the tempting `CMD=`
escape hatch on the launcher is refused because it preserves the code by creating
a twin (#97)**.
