# mlops-nyc-taxi — Crosstown Mobility: ETA & Reliability Program

*Fleet codename: **crosstown** — lineage meridian → wrenfield → ashford → crosstown.
Cross-project lessons cite it as "(crosstown, YYYY-MM-DD)".*

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
| M0 Foundations & org bootstrap (MLOps) | **closed 2026-08-16** | tag `m0-closed` · M1 kickoff §0 |
| M1 Data platform, contracts, prior-art (DE/DA) | **closed 2026-08-17** | tag `m1-closed` · M2 kickoff §0 |
| M2 Modeling I: baseline & gate (MLE) ◆REV | **closed 2026-08-17** | tag `m2-closed` · M3 kickoff §0 |
| M3 Modeling II: AutoML × Optuna (MLE) ◆REV | **closed 2026-08-18** | tag `m3-closed` · M4 kickoff §0 |
| M4 Pipeline on-cluster: Flyte (MLOps) | **closed 2026-08-19** | tag `m4-closed` · M5 kickoff §0 |
| M5 Serving & PRR: KServe (MLOps/SRE) | **closed 2026-08-19** | tag `m5-closed` · `verify-m5` 49/49 · M6 kickoff §0 |
| M6 Reliability: SLO, canary, gameday (SRE) | **closed 2026-08-20** | tag `m6-closed` · `verify-m6` 63/63 · M7 kickoff §0 |
| M7 Drift & retrain loop (SRE/MLE/DA) ◆REV | **closed 2026-08-21** | tag `m7-closed` · `verify-m7` 62/62 · ◆REV APPROVE WITH CONDITIONS (F-051/F-052 → M8-S1) · M8 kickoff §0 |
| M8 Feast & side-by-side (DE/MLE) | **closed 2026-08-23** | tag `m8-closed` · `verify-m8` 51/51 · M9 kickoff §0 |
| M9 Stretch: demo page (committed) + boundary closure; Ray/CI/security = PO opt-in | **closed 2026-08-24** | tag `m9-closed` · `verify-m9` 45/45 · `docs/milestones/PROGRAM_CLOSE.md` §0 |
| **PROGRAM CLOSE** — all ten gates M0…M9 run live and GREEN at the close | **closed 2026-08-24, one box open by design** | `PROGRAM_CLOSE.md` — §9/M9's observed demo run waits on the PO (AWAITING_PO 2026-08-23-3); F-062 + publish-the-repo are the PO's (2026-08-24-2); the chain is parked deliberately |
| **M9 Epilogue** — the PO's answered close inbox: S5 observed-box lands in the record · S6 F-016(B) incumbent margin · S7 F-062(b) · S8 README front door · S9 trivy + secret-scan; the public flip stays the PO's click | **in progress 2026-08-24** | `docs/milestones/M9_EPILOGUE_KICKOFF.md` §0 · AWAITING_PO 2026-08-24-2 (all seven answers recorded; the observed run happened 2026-08-24 and S5 lands it) |

Per-milestone direction lives in the ARCH-authored `docs/milestones/M*_KICKOFF.md`
— one per milestone, and each kickoff's §0 is the closure verdict of the
milestone before it. Flipping the row above (state + evidence) is a step of the
Architect's boundary triage (`automation/architect_prompt.md`, kickoff template
§0), not decoration: a milestone is not closed until the front door says so.
(Rows backfilled 2026-08-19 by PO audit — the table had sat at "not started"
through five closes.)

## Quickstart (commands real since M0; each `verify-mN` is that milestone's scripted gate)

```bash
cp .env.example .env          # fill locally; .env never enters git
make cluster-up               # kind cluster from infra/kind/kind-config.yaml
make deploy-platform          # MinIO + Postgres + MLflow
make verify-m0                # the M0 acceptance gate, scripted
```

## Where things live

Spec + reasoning: `docs/BLUEPRINT.md` (v3.0) · constitution: `docs/org/` ·
milestone direction: `docs/milestones/` (ARCH kickoffs) · session
prompts: `docs/PROMPTS.md` · traps: `docs/gotchas.md` (read first) · decisions:
`docs/decisions/` · contracts index: `docs/CONTRACTS.md` · prior art:
`docs/prior_art.md` · field notes: `docs/LEARNING_GUIDE.md` · ritual minutes:
`docs/rituals/` · session state: `HANDOFF.md` · PO inbox: `AWAITING_PO.md` ·
gate crossings, findings, deploy events: `ledgers/`.

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
