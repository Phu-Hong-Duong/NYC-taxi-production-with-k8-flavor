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
- Kaspersky AV on host — gotcha #9 before debugging any TLS error.
- Cluster: kind, config at infra/kind/kind-config.yaml. $0 budget — nothing leaves
  this machine; no cloud credentials exist in this project.
- Predecessor repo (Ashford / Home Credit) may be connected read-only for
  reference. NEVER write into it; its lessons arrive via BLUEPRINT §3 and gotchas.

## Version pins (OBSERVED values — re-verify live at M0/M3 and overwrite; blueprint values are hypotheses)
| Component | Pinned | Observed on | Source |
|---|---|---|---|
| Docker Desktop engine | 29.6.2 | 2026-08-16 | `docker version` (bootstrap preflight) |
| claude CLI (Windows) | 2.1.233 | 2026-08-16 | `claude --version` (bootstrap preflight) |
| gh CLI (Windows) | 2.96.0 | 2026-08-16 | `gh --version` (bootstrap preflight) |
| (kind/kubectl/helm/uv/make/python + WSL-side claude/gh: fill at M0-S1; FLAML/Optuna/DuckDB rows land at their milestones) | | | |

## Port family (fleet rule: check for foreign stacks before cluster-up)
MLflow 5000 · MinIO 9000/9001 · Flyte console 8080 · Grafana 3000 ·
KServe ingress 8081 · Pushgateway 9091 · Metabase 3030 · Postgres 5432 (in-cluster only)

## Commands (fill as they become real; each idempotent, each with a verify twin)
| Intent | Command | Verified |
|---|---|---|
| Cluster up / platform | `make cluster-up deploy-platform` | pending M0 |
| Gate checks | `make verify-m0` … `verify-m8` | pending each milestone |
| Scout / sniper | `make automl` / `make tune` | pending M3 |
| Destroy | `make destroy` | pending M0 |
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
