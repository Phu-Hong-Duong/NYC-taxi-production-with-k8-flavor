# mlops-nyc-taxi — Crosstown Mobility: ETA & Reliability Program

A production-shaped ML platform on a laptop, **run as a simulated enterprise
organization**. NYC yellow-taxi **trip-duration (ETA) model** through: versioned
data (DVC + DuckDB analyst layer) → orchestrated pipeline (Flyte) → tracked
training with an **AutoML scout (FLAML) and an Optuna sniper** → registry-gated
promotion (MLflow) → registry-driven serving (KServe) → canary + rehearsed
rollback → SLOs, gamedays, monitoring + drift-triggered retraining
(Prometheus/Grafana/Evidently) → online features (Feast) — benchmarked against
the community's best public implementations of this same problem.

Seven chartered roles (PO · DE · DA · MLE · MLOps · SRE · REV) build it through
committed artifacts, ledgers, and fresh-eyes review — `docs/org/ORG.md` is the
constitution. The model is deliberately modest. **The platform behaviors and the
role interplay are the product.**

## Status — refreshed at every milestone close (a stale front door misleads)

| Milestone (owner) | State | Evidence |
|---|---|---|
| M0 Foundations & org bootstrap (MLOps) | not started | — |
| M1 Data platform, contracts, prior-art (DE/DA) | not started | — |
| M2 Modeling I: baseline & gate (MLE) ◆REV | not started | — |
| M3 Modeling II: AutoML × Optuna (MLE) ◆REV | not started | — |
| M4 Pipeline on-cluster: Flyte (MLOps) | not started | — |
| M5 Serving & PRR: KServe (MLOps/SRE) | not started | — |
| M6 Reliability: SLO, canary, gameday (SRE) | not started | — |
| M7 Drift & retrain loop (SRE/MLE/DA) ◆REV | not started | — |
| M8 Feast & side-by-side (DE/MLE) | not started | — |
| M9 Stretch: Ray, CI smoke, security + demo page (committed) | not started | — |

## Quickstart (real commands land at M0; shape is fixed now)

```bash
cp .env.example .env          # fill locally; .env never enters git
make cluster-up               # kind cluster from infra/kind/kind-config.yaml
make deploy-platform          # MinIO + Postgres + MLflow
make verify-m0                # the M0 acceptance gate, scripted
```

## Where things live

Spec + reasoning: `docs/BLUEPRINT.md` (v2) · constitution: `docs/org/` · session
prompts: `docs/PROMPTS.md` · traps: `docs/gotchas.md` (read first) · decisions:
`docs/decisions/` · prior art: `docs/prior_art.md` · field notes:
`docs/LEARNING_GUIDE.md` · ritual minutes: `docs/rituals/` · session state:
`HANDOFF.md` · gate crossings, findings, deploy events: `ledgers/`.

## Architecture (target)

```
TLC parquet ──> ingest/validate ──> features ──> train ─┬─ FLAML scout ──┐
   (DVC, DE)      (pandera, DE)    (shared, MLE)        │  (hypotheses)  │
                       │                                └─ Optuna sniper ┤
              DuckDB analyst layer (DA)                    (Postgres)    │
                                                                    gate ▼ (nobody bypasses)
                 KServe (mlserver) <── champion alias <── MLflow registry
                      │  ▲                                            ▲
        Feast online ─┘  └── canary/rollback (SRE,                Flyte (schedule,
        features (M8)         rehearsed, ledgered)                drift retrain M7)
          Prometheus / Grafana / Evidently / gamedays watching all of it (SRE)
                REV challenges everything from fresh sessions (◆)
```
