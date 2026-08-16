# BLUEPRINT — Crosstown Mobility: ETA & Reliability Program

Version 3.0 — 2026-08-16 (BUILD-READY; the autonomous cadence, per PO
directions recorded verbatim in ADR-010: Fable is the sole Grand Architect and
authors every kickoff; the closure prompt is retired with its triage folded
into the Architect's boundary session; sessions are short, fresh, and
story-scoped, chaining themselves locally via automation/next_session.sh
(default +120s) with a STOP kill switch, a daily cap, and ONE PO inbox
(AWAITING_PO.md); git autonomy granted (branch/PR/merge-on-green, lineage
kept); FORK POLICY: direction decisions WAIT for the PO — no auto-proceeding
on recommendations, and recommendations must state the cost of the honest
option. §13 rewritten; M0 gains the harness-proof; templates updated.)
Version 2.6 — 2026-08-12 (PO-directed add: the clickable stakeholder demo —
zone pickers + time → live ETA — lands as an M9 story, deliberately OFF the M5
acceptance path.)
Version 2.5 — 2026-08-12 (DA expanded to full capacity at the principal's
direction — ADR-009: dbt-built analyst marts published to Postgres, Metabase as
the BI layer on-cluster, DA artifacts added to M2/M6/M7, and the hard boundary
law: marts serve humans and never feed the model. M1 resized to ~two sessions.)
Version 2.4 — 2026-08-12 (artisan track pre-loaded with the competition-proven
curriculum at the principal's direction: `docs/artisan_playbook.md` now carries
the adapted feature catalog with why-it-works, the professional iteration
protocol, the production-vs-competition divergences, and the leakage traps —
including the serving-time-availability trap that puts v1's `trip_distance`
under formal review at the M3 Design Review. Gotcha #21 added.)
Version 2.3 — 2026-08-12 (M3 redesigned as craft × automation at the principal's
direction, verbatim in ADR-008: the Kaggle-grade artisan workflow and the
AutoML×Optuna workflow run side by side under equal budgets, judged by the same
gate, with a feature dossier harvested from community wisdom and a 2×2 bake-off
isolating features-vs-tuning contributions.)
Version 2.2 — 2026-08-12 (downstream-first re-derivation at the principal's
direction: §14 downstream map added; M6 gains the shadow-before-canary story;
M7's batch inference made an explicit product. The stack survives re-derivation
unchanged — see §14's closing note.)
Version 2.1 — 2026-08-12 (v2.0 + §13 milestone-boundary governance: ARCH role,
debt register, closure sweeps — at the principal's direction, same day).
Version 2.0 — 2026-08-12, superseding v1.0 (same day) at the principal's direction.
Authored by Claude (Cowork planning session) as execution augment.
Status: **plan approved, awaiting Session 1 (M0)**. v1's four settled forks carry
forward unchanged; v2 adds the organizational overlay, the AutoML×Optuna program,
and the prior-art benchmark — under the latitude grant recorded in §2.

This document is the single source of truth for architecture and roadmap.
`docs/org/ORG.md` is the constitution (who does what, who can say no). `CLAUDE.md`
holds live environment facts; `HANDOFF.md` holds session state. When this document
and observed reality disagree, reality wins — record the delta.

---

## 1. Mission, restated professionally

**The company frame.** Crosstown Mobility, Inc. (fictional) is a NYC ride platform.
Its dispatch, pricing, and customer app all consume one upstream signal: predicted
trip duration (ETA). The ETA & Reliability Program builds that model *and the
production system around it* — and, per the principal's direction, builds it **the
way an enterprise builds it: as an organization**, with a Data Engineer, Data
Analyst, ML Engineer, MLOps/Platform Engineer, and SRE whose work flows through
committed artifacts, separated duties, and adversarial review. The interplay
between roles IS the curriculum; the platform is the exercise machine.

Restated: *a self-hosted, end-to-end ML platform on local kind, exercising the full
production loop (versioned data → orchestrated training with an AutoML scout and an
Optuna tuner → registry-gated promotion → canaried serving → SLO-monitored
operation → drift-triggered retraining → online features), executed as a simulated
multi-role organization with role-owned deliverables, fresh-eyes review, ledgers,
and rituals — and benchmarked against the best public implementations of the same
problem.*

Non-goals unchanged from v1: no cloud spend, no GPUs, no real user data, no
Kubeflow, no state-of-the-art modeling ambitions. One addition: the org simulation
is **not** allowed to become paperwork theater — every ritual must produce an
artifact a real company would keep (protocol §5: a ritual without committed
minutes did not occur).

## 2. Settled forks and standing grants (do not relitigate)

v1 forks, verbatim, 2026-08-12: orchestrator **"Flyte (Recommended)"** · cluster
**"Local kind (Recommended)"** · extensions **all four** (monitoring+drift, CI/CD,
DVC, Feast) · hardware **"32 GB or more"**.

New directions from the principal, 2026-08-12, quoted:

- Org mandate: *"how data engineer, data analyst, machine learning engineer and ML
  ops technique blending together … I want to see how they work together in
  tandem."* — the role simulation is accepted scope, not gold-plating. ("SLE" in
  the same message is read as **SRE**; if that misreads it, say so and it reopens.)
- AutoML mandate: *"I also want to see the convenience of autoML framework
  combined with Optuna or Raytune to tune the best model return from autoMl."*
- Prior-art mandate: *"there must be someone else who does a pretty good job on
  this dataset … I want to see how they work side by side and complement each
  other."*
- **Latitude grant (standing):** *"Feel free to add, change or modify as you wish,
  don't let my instruction constraint your developing direction and hinder your
  best judgement."* — recorded per protocol §2 as a standing approval for design
  latitude within this project's scope. ASK-class items (money, deletions, gate
  loosening, org-constitution changes) still go to the principal.

## 3. What we take from the predecessor — adopt, adapt, surpass

The principal's prior program (Ashford Lending, Home Credit dataset) proved an
organizational method over ~12 milestones. Its org constitution and executor
playbook were read from the connected repo on 2026-08-12 and mined deliberately.
The two projects share no domain; they share a *method*.

**Adopted intact** (proven, domain-neutral): roles as charters **with refusal
criteria** ("a role that cannot say no is decoration"); roles communicate through
committed artifacts and ledgers, never vibes; **fresh-session review** that reads
committed artifacts only and reads the builder's own account LAST (anti-anchoring);
**no self-sign-off, ever**; the **mandatory-finding rule** (a review with zero
findings is itself a defect — something wasn't looked at hard enough); rituals that
produce committed minutes; gamedays gated on a positive control; the field-note law
(every story ends with a LEARNING_GUIDE note before the next starts); PR-per-story
with role labels; walls counted across sessions.

**Adapted, not copied** — the predecessor's 2nd/3rd line is a *bank's* (Model Risk
Management, Compliance, Internal Audit — SR 11-7 geometry), because it decides
credit. A mobility platform's assurance geometry is **Google-SRE-shaped**: SLOs and
error budgets, Production Readiness Review before go-live, canary + rehearsed
rollback, gamedays, blameless postmortems, and a **Staff ML Reviewer** for
fresh-eyes model review. Same principle — builder ≠ challenger ≠ assurer — in the
industry-correct costume (the principal's own protocol §5: "the geometry is the
industry's, not one project's"). We keep ONE reviewing role (REV) instead of three,
because a taxi ETA mockup carrying a fair-lending office would be cosplay.

**Aimed to surpass**: the predecessor hand-rolled its serving and monitoring; this
program uses the industry stack end-to-end (KServe, Prometheus/Grafana, Evidently,
Feast) on real Kubernetes, adds CI on every PR from day one, adds the AutoML×Optuna
program the predecessor never ran (it *banned* its AutoML tool to a quarantine venv
after dependency wars — tuition we inherit, §5), and adds an explicit external
benchmark: our implementation reviewed against the community's best (§6).

**How a Data Analyst exists in a Kubernetes world** [v2.5]. The honest
resolution of "DA in k8s": the analyst never touches kubectl — the *platform*
hosts their tools, and they consume URLs. Three layers make it work. DuckDB
stays the DA's local exploration workbench (it is an embedded, in-process
engine — which is exactly why a served BI tool cannot sit on it). The **gold
marts** — analyst-facing aggregate tables built by **dbt** and published into
the one Postgres — are the served warehouse layer. **Metabase**, one container
on the cluster, is the BI layer over those marts: saved questions, dashboards,
self-service. Refresh is orchestrated by the same single DAG owner: `dbt build`
+ publish runs as ONE Flyte task at the tail of the monthly pipeline (dbt's
internal DAG executes *within* that task, like a compiler — Flyte still owns
WHEN; ADR-005 stands). And one boundary law with teeth, the analytics sibling
of the features law: **marts serve humans and never feed the model** — if a
mart aggregate looks model-worthy, it graduates through the dossier and the
shared features path, never by direct import (gotcha #22). Rejected occupants
of the BI seat: Superset (Redis+workers — too heavy for the laptop), Streamlit
(an app, not self-service BI; the predecessor already taught it), Grafana
(owned by the SRE and shaped for service telemetry, not business questions).

## 4. The organization (constitution: docs/org/ORG.md; charters: docs/org/ROLES.md)

Seven roles, one executor, role-per-block rotation:

| Role | Owns | Refuses (teeth — full list in ROLES.md) |
|---|---|---|
| **PO** (principal = user; agent prepares options) | scope, gates, acceptance | scope creep without a fork; vanity metrics |
| **DE** Data Engineer | ingestion, contracts, DuckDB analyst layer, DVC | data without a contract; silent schema pass-through; untyped ingest |
| **DA** Data Analyst | EDA, KPI definitions, error analysis, drift interpretation, prior-art survey | numbers without definitions; dashboards reading unpublished tables |
| **MLE** ML Engineer | features, training, AutoML scout, Optuna tuner, registry | quoting an AutoML leaderboard as a result; touching the gate; features outside the shared path |
| **MLOps** Platform | cluster, Flyte, KServe, CI, images | manual deploys; unpinned versions; secrets in git |
| **SRE** | SLOs, monitoring, canary/rollback, gamedays, incident response | go-live without a PRR; alerts nobody tested; a rollback never rehearsed |
| **REV** Staff ML Reviewer | fresh-eyes review at marked gates | reviewing in the builder's session; zero-finding reviews; closing its own findings |

Independence rules (mechanical, from the predecessor's playbook): REV blocks run in
a **fresh session over committed artifacts only**, builder's narrative last;
sign-off ledger producer ≠ approver on every row; REV must **re-derive at least one
number from raw materials** per review. Rituals with committed minutes: Data
Contract Review (M1) · Design Review (M3, M4) · Production Readiness Review (M5) ·
Gameday (M6) · Monitoring Review (M7) · Blameless Postmortem (on first real
incident). RACI for load-bearing deliverables lives in ORG.md.

**How "in tandem" becomes visible** (the principal's actual ask): every artifact
crosses a role boundary — DE publishes a contract the MLE must consume unchanged;
the MLE registers a model only the MLOps role may deploy; SRE guards the deploy
with gates the MLE cannot loosen; DA writes the memos that decide whether drift
matters; REV challenges everyone from a fresh session. The ledgers record every
crossing. That braid — not any single component — is the enterprise experience.

## 5. The AutoML × Optuna program (M3) — scout and sniper

Design, encoding both the mandate and inherited tuition:

**FLAML is the scout.** A time-budgeted sweep (`configs/automl.yaml`, default 30
CPU-minutes) across LightGBM/XGBoost/RF/linear families on the training window.
FLAML over AutoGluon as default: pip-light, no downgrade pressure on the core
stack — the predecessor had to exile AutoGluon to a quarantine venv after it
demanded old scikit-learn/numpy; if the principal later wants AutoGluon, that
quarantine pattern (separate venv, exchanges *predictions only*, scored by OUR
metrics module) is the pre-approved shape (ADR-007).

**The leaderboard is a hypothesis, never a result.** Inherited scar, generalized:
AutoML-internal scores can *flip sign* against held-out truth. Rule: the scout's
output is (winning family + starting hyperparameters + its own numbers quoted as
"scout-internal"). Every number that reaches a report or the registry is recomputed
by `taxi_mlops.training.evaluate` on the held-out month.

**Optuna is the sniper.** Search space centered on the scout's winner; TPE +
MedianPruner; trial count budgeted in `configs/tuning.yaml`; **study storage in the
platform Postgres** (resumable studies — enterprise-shaped, and it exercises the
same database discipline as everything else); every trial an MLflow nested run
under one parent; best trial → challenger.

**The gate is the impartial judge.** Scout, sniper, and the M2 hand-built model all
pass through the SAME promotion gate (`configs/promotion.yaml`) — champion moves
only on held-out-month evidence. Nobody, including AutoML, gets a side door. The
complementarity the principal asked to see is exactly this: breadth-first scout →
depth-first tuner → impartial registry gate, each doing what the other cannot.

**Ray Tune** is deliberately the stretch (M9), not the default: it adds a KubeRay
operator and distributed workers — a fine second lesson AFTER Optuna has taught
single-node tuning, and affordable at 32 GB. Choosing both at once teaches neither.

**The craft track beside the machinery** [v2.3]. Automation competes against a
professional, not against nothing: M3 fields an **artisan track** — features
harvested from documented community wisdom (the 2017 Kaggle NYC taxi-duration
competition's top solutions are the canonical vein) and expert-guided iteration —
under a wall-clock budget equal to the automation track's compute budget. The
scout×sniper machinery then runs on BOTH feature sets (M2's request-scoped v1 and
the artisan v2), producing a 2×2 that isolates where improvement actually comes
from: features, tuning, or both. Community experience says features dominate;
M3 measures that on this data instead of asserting it. Equal budgets, one gate,
no favorites.

## 6. Prior art — benchmarked, not imitated (M1 story, revisited at M8)

The principal is right that this problem is well-trodden: **DataTalksClub's MLOps
Zoomcamp** — the most-followed public MLOps course — uses exactly this dataset and
exactly this target (NYC taxi trip duration), and hundreds of capstone repos
implement it end-to-end (existence verified 2026-08-12; contents surveyed live at
execution, not from memory). M1 carries a DA/MLE story: survey the Zoomcamp
curriculum plus 2–3 strong capstones and any public Feast-on-taxi implementations;
produce `docs/prior_art.md` with a three-column verdict per practice: **adopt**
(they do it better), **differ** (we chose otherwise, with the reason), **surpass**
(what none of them do). Known-in-advance differentiators to test against the
survey, honestly: our org simulation, ledgers, and fresh-eyes review; Flyte+KServe
against their typical Prefect/Mage+web-service stack; gamedays; the schema-drift
vs statistical-drift split. M8 (Feast) revisits the survey for the feature-store
comparison specifically — "side by side," as asked.

## 7. Stack additions to v1's pinned table (§4 of v1 carries forward)

| Component | Role | Pin policy |
|---|---|---|
| FLAML | AutoML scout | pin at M3 from live source; record in CLAUDE.md |
| Optuna | tuner, Postgres-backed studies | pin at M3; MLflow integration verified then |
| DuckDB | DA's analyst query layer over parquet | pin at M1 |
| Ray + KubeRay | stretch only (M9) | decided then, not now |
| dbt (dbt-duckdb) | analyst gold marts + tests [v2.5] | pin at M1; runs as one Flyte task from M4 |
| Metabase | BI layer over Postgres marts [v2.5] | pin at M1; one container; app-db in the one Postgres |

Everything else — kind v0.32.0, KServe v0.18.0 (Standard→Knative at canary),
MLflow 3.13.0, Flyte 2.0.24 (fallback 1.16.7, ADR-002), Feast 0.63.0, Evidently
0.7.21, TLC URL pattern — as pinned in v1 §4, all re-verified live at M0.

## 8. Repository skeleton — v2 deltas

```
mlops-nyc-taxi/
├── docs/
│   ├── org/ORG.md               # constitution: frame, RACI, independence rules
│   ├── org/ROLES.md             # seven charters WITH refusal criteria
│   ├── prior_art.md             # survey protocol + adopt/differ/surpass table (M1)
│   ├── LEARNING_GUIDE.md        # field notes, one per story (inherited law)
│   └── rituals/                 # minutes land here: PRR, gameday, reviews
├── src/taxi_mlops/tuning/       # FLAML scout + Optuna study code (M3)
├── configs/automl.yaml          # scout time budget, families, seed
├── configs/tuning.yaml          # trial budget, sampler/pruner, space bounds
└── (everything from v1 §5 unchanged: src/ never imports an orchestrator;
     features/ is the one transform path; Make is the interface)
```

## 9. Milestone plan v2 (role owners added; accept-when BEFORE work; every close SHOWS)

Verification discipline and wall rules from v1 apply throughout. REV gates marked ◆.

**M0 — Foundations & org bootstrap** (MLOps A; all roles). v1's M0 + the
constitution: ORG.md and ROLES.md committed; ledgers carry Role columns; CI live.
Accept when: v1's M0 gate passes (idempotent cluster + platform + verify-m0 green,
destroy/rebuild observed) AND the org docs exist with every charter carrying at
least three refusals AND [v3.0] the autonomy harness is battle-checked in real
use — M0's stories themselves arrive via the chain, and one mid-milestone
STOP/resume is exercised and logged. Show: MLflow UI + the constitution + the
chain's session logs.

**M1 — Data & analytics platform** (DE A; DA A for the analytics stories) [DA
track expanded v2.5 — expect ~two sessions, split after S5]. v1's M1 + Data
Contract Review ritual (minutes committed) + DuckDB analyst layer (DA queries
clean tables, never raw parquet) + `docs/prior_art.md` filled from a live
survey, PLUS the analytics platform:
- *S6 — Gold marts (DA, dbt)*: a dbt project under `analytics/dbt/` builds the
  analyst marts from processed data — `trips_clean`, `zone_hourly_stats`,
  `monthly_kpis` — with **dbt tests** (not_null, accepted ranges) as the DA's
  own quality gate, a second QA layer parallel to the DE's pandera contracts;
  a publish step lands the marts in the one Postgres. From M4 the build+publish
  runs as the tail task of the monthly Flyte pipeline.
- *S7 — BI layer (DA + MLOps deploy)*: Metabase on-cluster (one container,
  app-db in Postgres, port 3030), connected to the marts; dashboard v1 ships
  two boards — data-health (row counts, rejection rates, freshness) and the
  KPI board (definitions cited by id from the DA's KPI doc).
Accept when: v1's M1 gate (byte-identical rebuild, counted rejections,
red-teamed corrupt-file refusal) AND the contract review minutes exist AND
prior_art.md has ≥6 verdicts AND `dbt build` is green including tests (with one
test red-teamed on a seeded bad fixture, then passing) AND the Metabase boards
render from marts in the browser. Show: EDA report + prior-art table + the two
Metabase boards.

**M2 — Modeling I: honest baseline and the gate** (MLE A; DA R for error memo).
As v1's M2 (baseline, LightGBM v1, signature, promotion gate red-teamed with a
hobbled model) + DA error-analysis memo (where does it fail: zones? hours? long
trips?). The memo's segment queries also become a Metabase **error-segment board**
[v2.5], so the model's weak spots stay visible to everyone, not buried in a
doc. Accept when: v1's M2 gate AND the memo cites specific segments with
numbers AND the error-segment board renders and is linked from the memo.
Show: refusal transcript + memo + board. ◆ REV reviews M2 in a fresh session
(mandatory finding; re-derives one metric from raw predictions).

**M3 — Modeling II: craft × automation, side by side** [redesigned v2.3 at the
PO's direction — ADR-008] (MLE A; DA R for the dossier; Design Review ritual
first, covering both tracks' budgets and search plans). Two workflows, equal
budgets, one impartial gate. The fattest milestone in the plan: expect TWO
sessions, split at the S2/S3 boundary.

- *S1 — Feature dossier* (DA+MLE): harvest community wisdom LIVE — the 2017
  Kaggle NYC taxi-trip-duration competition's documented top solutions plus
  current write-ups — into `docs/feature_dossier.md`: each candidate feature
  with source, rationale, leakage-risk note, and an adaptation note where the
  data shape has changed (2019+ TLC files carry zone IDs, not coordinates —
  distance/bearing features come from TLC zone-shapefile centroids). Expected
  families: temporal decomposition + holiday/rush flags; zone-centroid
  haversine/bearing; airport-zone flags; circuity (odometer ÷ straight-line);
  train-only zone-pair and zone-hour aggregates; log1p target transform.
- *S2 — Artisan track* (MLE): executed **per the committed
  `docs/artisan_playbook.md`** [v2.4] — the competition-proven curriculum
  pre-loaded by the Architect (feature catalog with why-it-works, the
  sample-first/one-change/ledgered iteration protocol, the stop rule, the
  production-vs-competition divergences). Implement the dossier's survivors as
  feature-set v2 in the ONE shared path; expert iteration under an explicit
  wall-clock budget EQUAL to the automation track's compute budget — deliberate
  loops steered by M2's error memo, feature importance, and an **ablation
  table** proving which feature groups earn their keep. Includes the leakage red-team,
  on a disposable branch: fit one aggregate across ALL months on purpose, watch
  validation inflate while the untouched test month doesn't, document the gap,
  delete the branch. (Aggregates that survive ablation are the named candidates
  for Feast definitions at M8 — M3's craft becomes M8's catalog.)
- *S3 — Automation track* (MLE): the scout×sniper machinery per §5 — FLAML
  under budget, Optuna in Postgres (namespaced, resumable, kill-and-resume
  demonstrated), MLflow-nested trials, ≥1 pruned trial shown — run TWICE: on
  feature-set v1 and on v2.
- *S4 — The 2×2 bake-off (+ baseline)*: five contenders — baseline · M2 model
  (v1, hand) · artisan (v2, hand) · auto-tuned on v1 · auto-tuned on v2 — every
  number from `training.evaluate` on the untouched test month, gate verdicts
  printed for all five. The table isolates WHERE improvement came from:
  features, tuning, or both. Winner → challenger → the unchanged gate decides
  the alias. An automation loss (or an artisan loss) is a valid, reportable
  result.

Accept when: dossier holds ≥10 candidates each with source + leakage note; the
ablation table shows per-group deltas; the leakage red-team transcript exists
(inflation observed, then removed); S3's resumability and pruning arms pass as
before; all five gate verdicts printed from evaluator-traceable MLflow runs.
Show: the dossier, the ablation table, the 2×2 bake-off table.
◆ REV reviews the bake-off claim-by-claim AND audits v2's aggregate features for
leakage — re-deriving at least one aggregate from raw under the point-in-time
constraint.

**M4 — Pipeline on-cluster (Flyte)** (MLOps A; MLE R). v1's M3 unchanged: Flyte 2
per docs, containerized, ingest→validate→features→train→evaluate→register
parametrized by month; cache-hit rerun; kill-a-pod retry; wall rule → ADR-002
fallback. Accept/Show: as v1 M3.

**M5 — Serving & release** (MLOps A; SRE R). v1's M4 (KServe Standard, mlserver,
storage-config, THE parity test 1e-6, p95 measured, self-heal under load) + the
**Production Readiness Review**: SRE walks a written checklist (runbook exists,
rollback typed, alerts planned, capacity sanity) BEFORE the champion serves;
minutes committed; deployments ledger opens. Accept when: v1's M4 gate AND the
PRR minutes exist with every box carrying pasted evidence. Show: parity output +
PRR minutes.

**M6 — Reliability: SLOs, shadow → canary → rollback, gameday** (SRE A). v1's M5
+ an SLO document (latency p95, availability, error rate — targets chosen and
owned by SRE, numbers argued not copied) + **shadow before canary** [v2.2], the
real release sequence: the challenger first runs in shadow — scored on the same
live requests as the champion with ZERO user-facing traffic (mechanism chosen in
the M6 spike: traffic mirroring vs dual-send from the load client) — and a
disagreement report (prediction delta distribution on identical inputs) is
reviewed BEFORE any traffic shifts — the review is the DA's **shadow-analysis
memo** [v2.5]: the analyst, not the deployer, reads the disagreement
distribution (which segments diverge? is the delta benign?) and their verdict
is a named input to the canary go/no-go; only then canary 10% → 100% +
**Gameday 1**,
predecessor-style: positive control fired first, then staged failures (kill
predictor under load; break the storage-config secret; saturate CPU) each with a
**distinguishable signature** predicted BEFORE injection and checked after.
Accept when: the shadow comparison table exists with a quantified disagreement
rate before the first traffic shift; v1's M5 gate (canary 90/10 observed,
rollback <2min under load, alert fired in red-team); AND the gameday record shows
predicted-vs-observed signatures with at least one prediction wrong and
investigated (a gameday with all predictions right was too easy).
Show: the shadow disagreement table + Grafana during canary + gameday record.

**M7 — Drift, batch inference, & the retrain loop** (SRE A; MLE R; DA R for the
memo). v1's M6 (Evidently → Pushgateway → alert; COVID-month statistical drift vs
2025 schema-drift refusal, distinguishable; scheduled Flyte retrain landing a
challenger) + **batch inference as a product** [v2.2]: the scheduled monthly
workflow doesn't just score for drift — it WRITES a predictions table (parquet in
`data-processed` + a DuckDB view) that the DA queries like any consumer. This is
the batch-serving mode enterprises actually run more often than online serving,
made first-class rather than implicit — and surfaced as a Metabase
**predictions & drift board** over the predictions mart [v2.5]. + DA drift
memo: what ACTUALLY changed in 2020-03 (trip mix? zones? durations?) —
interpretation, not just detection.
Accept when: v1's M6 gate; the predictions table for the scored month exists and
the DA memo cites it; AND the memo explains the drift in domain terms with
numbers. Show: the two failure signatures + the predictions table + the memo.
◆ REV monitoring review (fresh session).

**M8 — Feature store (Feast) & the side-by-side** (DE A; MLE R). v1's M7
(zone-window aggregates, point-in-time training joins, transformer enrichment,
100-pair online/offline parity) + prior-art revisit: our Feast design against the
surveyed community implementations — one page, adopt/differ/surpass, honest.
Accept when: v1's M7 gate AND the comparison page exists. Show: parity table +
comparison.

**M9 — Stretch** (opt-in per story, EXCEPT the demo — committed by PO direction
2026-08-12): Ray Tune on KubeRay re-running the M3 study distributed (compare
wall-clock and best-trial parity); CI smoke on kind nightly; trivy +
secret-scan; README polished as a portfolio front door; and the **stakeholder
demo page** [v2.6] (MLOps R, DA C for stakeholder legibility): one
self-contained HTML page under `demo/` — two zone pickers (names from the TLC
zone lookup), a date-time picker, submit → live ETA from the InferenceService
with the serving model version shown. Dependency-free by design; the one
technical wrinkle (browser → ingress CORS) is decided at execution (ingress
annotation vs mlserver CORS config) and recorded. Never on the M5 acceptance
path — serving must prove itself in the terminal before it earns a face.
Accept when: the zone list renders from the lookup; a submitted trip returns a
live prediction with model version visible; and one non-technical person (the
PO counts) completes a query unassisted, observed. Show: the page itself —
which doubles as the interview artifact.

## 10. New traps seeded to the ledger (full text in docs/gotchas.md #15–18)

AutoML leaderboard ≠ result (sign can flip on held-out truth — inherited scar);
FLAML pins vs core stack (if it ever pressures a downgrade, quarantine like
AutoGluon, never downgrade the platform); Optuna study name collisions in shared
Postgres (namespace per milestone); reviewer-session leakage (a REV block that can
see the builder's context is void — start fresh, artifacts only).

## 11. Risks — v2 deltas

Org overhead inflates sessions (~+20–30% per milestone; accepted scope per the
mandate — watch it, and if a ritual stops earning its minutes, propose cutting it
as a fork rather than silently skipping). FLAML/Optuna version friction at M3:
low, both are pip-light. Gameday on kind can wedge the cluster: acceptable —
`make destroy && make cluster-up` is the rehearsed recovery, and that recovery
being boring is itself the lesson. Reviewer theater risk (REV finding trivia to
satisfy the mandatory-finding rule): mitigated by the re-derive-one-number rule —
a re-derivation either matches (evidence of soundness, recorded) or doesn't (a
real finding).

## 12. For the principal to consider later (queued, none blocking Session 1)

Protocol wiring in CLAUDE.md still needs your one-line choice (v1.x root copy vs
v2.0 import). AutoGluon as a second scout is pre-shaped but off by default (ADR-007)
— say the word if you want it. Ray/KubeRay stays stretch until you opt in (M9).
The cloud-port remains an available NEW fork (was offered, not chosen). And when
M9's portfolio polish lands: whether to publish the repo publicly — it is being
built to be shown.

## 13. Execution model — the autonomous cadence (v3.0; supersedes the v2.1 ritual below)

One human paste (Prompt A, into `claude --model fable`) bootstraps the program;
after that, sessions schedule each other locally: **executor (Opus) sessions,
one story each**, chaining every ~2 minutes; after a ◆ milestone's last story,
a **REV session** (fresh, mandatory finding); then an **ARCH session (Fable)**
at every milestone boundary that does the triage the old closure prompt did
(re-runs verifies, dispositions every finding/condition/debt with quoted
landings, tags the close) and **authors the next kickoff** — the Architect is
the sole planning authority. Mechanics, controls, and caveats live in
`automation/README.md`: `next_session.sh` (STOP kill switch, daily cap 40,
per-session logs), permission-mode choices, WSL-liveness caveat.

The PO's operating surface is three things: paste Prompt A once · answer
**AWAITING_PO.md** (the one inbox) when a fork parks there · `touch
automation/STOP` to pause. **Fork policy (PO direction, ADR-010): direction
decisions WAIT.** New findings that open a fork are written to the inbox with
options, honest trade-offs, and a recommendation that must state the cost of
the honest option — and the chain takes only independent stories meanwhile,
parking entirely when nothing independent remains. Hard-block classes (money,
credentials, destroying user data, loosening gates, rewriting history) never
proceed autonomously under any circumstances. Git autonomy is granted within
that frame: branch per story, PR, merge on green + verified accept-when,
lineage preserved.

*The v2.1 boundary ritual below is retained for history; v3.0 replaces its
mechanics while preserving its invariants (triage-before-close, quoted
carries, lineage proof, REV independence, no self-sign-off).*

## 13-legacy. Execution model — sessions, roles, and the milestone boundary

Rhythm unchanged (one milestone per session, verify by running, exit through the
handoff), plus **role-blocks** declared at session start and at each switch —
charter read at entry, ledgers at exit.

**The milestone boundary is governed** (v2.1, principal's direction): every
Mx → M<x+1> crossing runs three steps in order, none skippable. First the
executor sweeps leftovers (Prompt G → `docs/milestones/Mx_CLOSURE.md`): every
finding, condition, and due debt dispositioned as fixed / carried / accepted —
a CARRY is legal only with a landing milestone whose covering scope can be
QUOTED from §9 (the predecessor's carried-to-nowhere wound, gotcha #19), and
"NOT CLOSABLE" is an honest, respected verdict. Then the executor drafts the
next kickoff (Prompt E → `M<x+1>_KICKOFF.md`), with live-verified preconditions
and mandatory debt intake by id. Then the **Grand Architect (ARCH)** — a FRESH
session on the stronger model (executor drafts on the pinned `opus`; ARCH
audits on Fable, each session stating its configured model) — samples the
sweep, re-checks every carry quote, audits the kickoff, and countersigns,
amends with an edit trail, or **vetoes** with named defects; a second veto on
one boundary escalates to the PO. Only after countersignature is Mx tagged
closed (`git tag mx-closed`) and M<x+1> allowed to start. Model diversity here
is an independence mechanism: plans must survive a reader that did not write
them and reasons harder than their author.

`ledgers/debt.md` is the carry register; intake at each kickoff is mandatory
and diffed by ARCH. Prompts A–G with design rationale live in
`docs/PROMPTS.md` (v2.1); templates in `docs/milestones/`.

## 14. The downstream map (added v2.2 — the curriculum, stage by stage)

The principal's books stop where the trained model appears; everything after
that point is "downstream", and it is where most of this project deliberately
lives. The map below is the re-derivation: each downstream stage every
production ML system needs, where this plan teaches it, and which disciplines
blend there. Upstream is included once, for contrast — it is where Airflow
would sit if it ever joins.

| Stage (the concept) | What it means in practice | Lives at | Disciplines |
|---|---|---|---|
| *Upstream: ingestion & contracts* | raw data → validated, versioned tables | M1 | DE, DA |
| *Analytics serving (BI)* | dbt gold marts in Postgres + Metabase boards — the analyst's product surface | M1, grows M2/M7 [v2.5] | DA, DE |
| Evaluation & the promotion gate | held-out evidence decides, nobody bypasses | M2, M3 | MLE, REV |
| Packaging & registry | signed model + alias as THE train/serve interface | M2–M4 | MLE, MLOps |
| Pipeline productionization | the notebook-shaped flow becomes scheduled, cached, retryable containers | M4 | MLOps, MLE |
| Online serving | registry → live endpoint; parity proves no train/serve skew | M5 | MLOps, SRE |
| **Batch serving** | scheduled scoring writes a predictions table consumers query — the quiet workhorse of enterprise ML | M7 [v2.2] | MLE, DA |
| Release engineering | **shadow** (zero-risk comparison) → **canary** (10%) → full; rollback rehearsed BEFORE the flip | M6 [v2.2 adds shadow] | SRE, MLOps |
| Observability & SLOs | latency/error/traffic dashboards; alerts proven by firing them | M6 | SRE |
| Model monitoring & drift | statistical drift vs schema drift, caught by different gates | M7 | SRE, DA |
| The retrain loop | drift → trigger → new challenger, untouched by hand | M7 | MLE, SRE |
| Online features | offline/online consistency, point-in-time correctness | M8 | DE, MLE |
| Incident response | gamedays, distinguishable failures, postmortems | M6 | SRE |
| Governance | sign-offs, findings, debt, fresh-eyes review, boundary gates | every milestone | REV, ARCH, PO |
| Online experimentation (A/B) | measuring BUSINESS outcomes per variant — honestly out of reach without real users; the shadow story teaches the mechanics, the concept gets a LEARNING_GUIDE note, and faking outcome data would teach the wrong lesson | concept only | (noted, not built) |

**Why the stack survives the re-derivation.** Each row above demands a
capability, and the four names ChatGPT happened to recommend are simply the
standard seats for those capabilities: Kubernetes = run containers reliably;
an orchestrator = run the pipeline stages (Flyte here; Airflow/KFP are other
occupants of the same seat); MLflow = registry/lineage seat; KServe = serving
seat. The plan was derived from the rows, and the rows are tool-independent —
which is also why every seat is swappable later (the S3-API storage story, the
thin-wrapper law, and registry-as-interface exist precisely so no tool choice
can hold the curriculum hostage). The stack is the consequence of the map, not
its constraint.
