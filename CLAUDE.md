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
| (FLAML/Optuna/DuckDB rows land at their milestones) | | | |

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
9000←30900 and 9001←30901 (`infra/helm/minio/values.yaml`), 8081←80 / 8443←443
(ingress, M5). Each pair is TWINS across two files — `tests/unit/
test_platform_scripts.py` fails if they drift. Adding a port means
`make cluster-down && make cluster-up`; there is no live path.

## Commands (fill as they become real; each idempotent, each with a verify twin)
| Intent | Command | Verified |
|---|---|---|
| Cluster up | `make cluster-up` | VERIFIED 2026-08-16 (M0-S2): created 3-node `mlops-taxi`, re-ran → `already exists — no-op` exit 0, down→up rebuild from the pinned config, all exit 0 |
| Port pre-check (gotcha #10) | `make ports` | VERIFIED 2026-08-16 (M0-S2): passes clean; RED-TEAMED with a dummy listener on 5000 → exit 2 naming port, purpose and holding pid, through `make cluster-up` too |
| Cluster down | `make cluster-down` | VERIFIED 2026-08-16 (M0-S2): deletes, and no-ops when already absent (both exit 0) |
| Platform | `make deploy-platform` | VERIFIED 2026-08-16 (M0-S3): MinIO + Postgres + MLflow up; re-run on the live stack = clean upgrade (helm rev 3, namespaces/service/configmap `unchanged`) and it REPAIRED a hand-inflicted `scale --replicas=0` |
| Gate check M0 | `make verify-m0` | VERIFIED 2026-08-16 (M0-S3): 18 sub-checks GREEN, exit 0; RED-TEAMED by scaling MLflow to 0 → exit 1 naming 5 failures. Secrets come from `.env` (gitignored) via `scripts/platform_secrets.sh` — never printed, never committed |
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
namespaces (#17), REV freshness (#18).
