# HANDOFF — append-only, newest entry on top

## Session 2026-08-16 (j) — Session 0.9: BUILD-READY — v3.0 autonomous cadence

### State
on-track / READY — planning phase closed at the PO's direction ("the review is
complete"); the repo is a build-ready kit. User's move: the go-live steps in
automation/README.md one-time setup, then paste Prompt A (docs/PROMPTS.md
v3.0) into `claude --model fable` on the laptop.

### Done
- Autonomy harness shipped: automation/next_session.sh (roles executor/rev/
  architect → models opus/opus/fable, default +120s, STOP kill switch, daily
  cap 40 with self-noting halt, per-session logs; bash -n clean AND
  functionally tested against a stubbed `claude` in the planning sandbox:
  STOP-halt observed, scheduled fire observed with correct model+flags+prompt,
  cap-halt observed writing its own AWAITING_PO entry) + three
  self-run prompt files + AWAITING_PO.md single inbox + automation/README.md
  (permission modes, WSL-liveness caveat, controls).
- Governance rewritten to v3.0 per PO directions (ALL verbatim in ADR-010):
  Fable = sole Grand Architect authoring every kickoff (E/F dissolved); the
  closure prompt retired with its triage folded into ARCH boundary sessions
  (protection preserved, PO burden removed); story-scoped chained sessions
  (context hygiene); git autonomy granted (branch/PR/merge-on-green);
  FORK POLICY: direction decisions WAIT in the inbox — no auto-proceed on
  recommendations, anti-demo-bias clause in every prompt; hard-block classes
  never autonomous (gotcha #23). WSL-scheduler caveat = gotcha #24.
- BLUEPRINT v3.0 (§13 rewritten, v2.1 ritual kept as legacy; M0 gate now
  includes harness-in-real-use + STOP/resume proof); PROMPTS v3.0 (one human
  prompt remains: bootstrap Prompt A); ORG rule 7 + ARCH charter rewritten;
  kickoff template gains §0 triage; closure template deleted; CLAUDE.md
  conventions + commands updated.
- LOCAL execution confirmed as mandatory, not preference: the kind cluster
  lives on the laptop; no cloud trigger was created anywhere.

### Decisions
- All six PO directions quoted verbatim in ADR-010, including the mid-turn
  fork-policy addition. Model-diversity plan review (v2.1's one virtue lost)
  consciously traded for simplicity; compensations recorded in ADR-010.

### Defects/Surprises
- none in execution (nothing executed yet — the first real execution IS the
  chain's Session 1).

### Next
On the laptop: (1) automation/README.md one-time setup — permission flags,
model pin, git remote; (2) wire the protocol line in CLAUDE.md; (3)
`claude --model fable` in the repo root, paste Prompt A; (4) watch
AWAITING_PO.md and the ledgers. The program runs itself from there.

## Session 2026-08-12 (i) — Session 0.8: stakeholder demo committed to M9 (v2.6)

### State
on-track / OPEN — small scope add per PO direction; zero infrastructure
executed. User's move: unchanged (Session 1, Prompt A).

### Done
- Stakeholder demo page added as a COMMITTED M9 story (no longer opt-in):
  BLUEPRINT §9/M9 story + accept-when (incl. one non-technical user completing
  a query unassisted); demo/README.md contract stub; Makefile `demo` target;
  README status row. Deliberately off the M5 acceptance path.

### Decisions
- PO direction 2026-08-12, verbatim: "please add this to the project" (re: the
  clickable one-page ETA demo offered in conversation). CORS approach is an
  execution-time decision, recorded when made.

### Defects/Surprises
- none.

### Next
Unchanged: unzip into WSL2 home, wire the protocol line in CLAUDE.md, paste
Prompt A.

## Session 2026-08-12 (h) — Session 0.7: hardware fact — 64 GB (factual updates only)

### State
on-track / OPEN — plan version stays v2.5; facts corrected; zero infrastructure
executed. User's move: unchanged (Session 1, Prompt A).

### Done
- Machine RAM corrected to 64 GB across working memory: CLAUDE.md env facts
  (WSL grant ~48 GB), gotcha #2 example values, Prompt A environment line.
  ADR-009 amended by marker: Superset rejection's RAM leg void, complexity leg
  stands; BI seat swap stays cheap (marts-in-Postgres is the stable interface).

### Decisions
- PO default recorded, colleague-style: Metabase stands unless the PO says
  "Superset" (ADR-010 if so). Kubeflow decision NOT reopened — its grounds were
  dev-loop, duplication, and no-soft-fallback, not RAM.

### Defects/Surprises
- The original 32 GB figure came from the fork option label ("32 GB or more"),
  not a measurement — lesson: record hardware as measured numbers, not option
  labels; corrected where the next session will read it.

### Next
Unchanged: unzip into WSL2 home, wire the protocol line in CLAUDE.md, paste
Prompt A. M0 now grants WSL ~48 GB per gotcha #2.

## Session 2026-08-12 (g) — Session 0.6: DA at full capacity (v2.5)

### State
on-track / OPEN — blueprint at v2.5; still zero infrastructure executed. User's
move: unchanged (Session 1, Prompt A).

### Done
- DA track expanded per PO direction (verbatim in ADR-009): dbt gold marts
  (analytics/dbt/, tests as the DA's own QA layer, red-teamed once) published
  to the one Postgres; Metabase as the BI layer on-cluster (port 3030); DA
  boards at M1 (data-health + KPI), M2 (error-segments), M7 (predictions &
  drift); DA shadow-analysis memo gates the M6 canary go. Marts refresh runs
  as ONE Flyte task from M4 (ADR-005 stands). M1 resized ~two sessions.
- Boundary law installed where it will trip: gotcha #22 (marts never feed the
  model; grep check named), ROLES.md DA charter + refusals, ORG RACI rows,
  CLAUDE.md conventions + port family, Makefile marts/deploy-metabase targets,
  §14 map row.

### Decisions
- BI seat: Metabase over Superset (weight) / Streamlit (not self-service;
  predecessor taught it) / Grafana (SRE telemetry) — ADR-009. Earlier
  conversational "no dbt" stance amended into a boundary, not a ban.

### Defects/Surprises
- Planning slip, recovered: a heredoc'd python edit to the Makefile died on a
  quote-collision SyntaxError; redone via file-edit tooling. Lesson: prefer
  structured edits over string-surgery for Makefiles.

### Next
Unchanged: unzip into WSL2 home, wire the protocol line in CLAUDE.md, paste
Prompt A. M0 unchanged; M1 now carries S6/S7 (marts + BI).

## Session 2026-08-12 (f) — Session 0.5: artisan playbook pre-loaded (v2.4)

### State
on-track / OPEN — blueprint at v2.4; still zero infrastructure executed. User's
move: unchanged (Session 1, Prompt A).

### Done
- docs/artisan_playbook.md authored: competition record verified live
  2026-08-12 (two leagues — external-data winner 0.28976 RMSLE with OSRM+weather
  vs no-external 0.36185; the "road network beat every modeling trick" lesson);
  five winner lessons with why-it-works; adapted feature catalog; the
  sample-first / one-change / ledgered iteration protocol with a declared
  keep-threshold and stop rule; production-vs-competition divergences
  (temporal splits, MAE gate, no stacking) each with reasons; leakage traps.
- NEW TRAP surfaced by the playbook work: serving-time availability —
  trip_distance is post-trip odometer, unusable for true pre-trip ETA. Gotcha
  #21 added; configs/features.yaml annotated; v1's trip_distance placed under
  formal review at the M3 Design Review. BLUEPRINT §9/M3-S2 now binds to the
  playbook.

### Decisions
- PO intent honored: the curriculum is PRE-LOADED (Architect-authored), not
  left to live discovery; S1's dossier still verifies live sources and corrects
  drift — trust, then verify.

### Defects/Surprises
- The trip_distance serving-availability issue is a REAL defect-class catch
  made at planning time, before any code — logged as the durable lesson in
  gotcha #21 and the playbook, where the next attempt will trip.

### Next
Unchanged: unzip into WSL2 home, wire the protocol line in CLAUDE.md, paste
Prompt A. M0–M2 scope unchanged; M3 executes S2 per the playbook.

## Session 2026-08-12 (e) — Session 0.4: M3 redesigned — craft × automation (v2.3)

### State
on-track / OPEN — blueprint at v2.3; still zero infrastructure executed. User's
move: unchanged (Session 1, Prompt A).

### Done
- M3 redesigned per PO direction (verbatim in ADR-008): artisan track (community
  feature dossier + budgeted expert iteration + ablation + leakage red-team)
  beside the automation track (scout×sniper on BOTH feature sets), five-contender
  2×2 bake-off, unchanged gate as judge. BLUEPRINT §5 + §9/M3 rewritten;
  docs/feature_dossier.md template seeded (10 candidate rows); configs/
  features.yaml feature-set registry added; Makefile verify-m3 contract updated.
- M3 sized honestly at ~two sessions (split at S2/S3 boundary).
- Arc recorded: ablation-surviving aggregates are M8's named Feast candidates.

### Decisions
- ADR-008 (equal budgets rule guards against unbounded "Kaggle grinding";
  automation-loses is a valid reportable outcome). OSRM routing / weather joins
  deliberately NOT absorbed into M3 — they are an M9-stretch fork if wanted.

### Defects/Surprises
- none in execution (nothing executed).

### Next
Unchanged: unzip into WSL2 home, wire the protocol line in CLAUDE.md, paste
Prompt A. M0–M2 scope unchanged by v2.3.

## Session 2026-08-12 (d) — Session 0.3: downstream-first re-derivation (v2.2)

### State
on-track / OPEN — blueprint at v2.2; still zero infrastructure executed. User's
move: unchanged (Session 1, Prompt A).

### Done
- Re-derived the plan from the principal's stated goal (learn the DOWNSTREAM of
  ML, many disciplines blending) instead of from the inherited tool list.
  Result: structure confirmed; two additions only. BLUEPRINT §14 added — the
  downstream map (stage → milestone → disciplines, upstream row for contrast,
  honest A/B-testing limitation). M6 gains shadow-before-canary (disagreement
  table gates the first traffic shift). M7 makes batch inference a first-class
  product (predictions table in DuckDB, DA as consumer).
- Verification: section-reference integrity preserved (no renumbering — §14
  appended; §9 references from PROMPTS/Makefile untouched).

### Decisions
- Stack seats (K8s/MLflow/Flyte/KServe) re-affirmed as consequence of the
  downstream map, not a constraint inherited from ChatGPT — recorded in §14's
  closing note. A/B testing stays concept-only: faking business outcomes would
  teach the wrong lesson (candor over coverage).

### Defects/Surprises
- none in execution (nothing executed).

### Next
Unchanged: unzip into WSL2 home, wire the protocol line in CLAUDE.md, paste
Prompt A. M0 scope unchanged by v2.2.

## Session 2026-08-12 (c) — Session 0.2: milestone-boundary governance (ARCH + debt register)

### State
on-track / OPEN — v2.1: boundary ritual added at the principal's direction;
still zero infrastructure executed. User's move: unchanged (Session 1, Prompt A).

### Done
- PROMPTS v2.1: Prompt E (kickoff draft, executor model), Prompt F (Grand
  Architect boundary review on Fable — audit, amend with edit trail, veto with
  escalation-after-two), Prompt G (pre-closure leftover sweep with dispositions).
- docs/milestones/ kickoff + closure templates; ledgers/debt.md (carries need
  QUOTED landings); gotchas #19 (carried-to-nowhere) + #20 (MERGED-reaching-
  nothing); ARCH chartered in ROLES.md; ORG.md independence rule 7; BLUEPRINT
  §13 rewritten, version 2.1; CLAUDE.md conventions updated.
- Verification observed this session: stubs compile, unit sanity passes, all
  YAML strict-parses, Makefile parses, gotcha ordering asserted programmatically.

### Decisions
- Principal's direction (2026-08-12, this session): executor model (pinned
  `opus`) DRAFTS milestone kickoffs; Fable as Grand Architect independently
  audits/improves/vetoes; and every milestone close is preceded by a leftover
  sweep — motivated by predecessor pain: closed milestones whose unaddressed
  issues derailed later work. Interpreted into: G → E → F boundary ritual,
  debt register with quoted landings, NOT-CLOSABLE as a respected verdict.
- Wrong-model review is void (sessions state their configured model first).

### Defects/Surprises
- none in execution (nothing executed).

### Next
Unchanged: unzip into WSL2 home, wire the protocol line in CLAUDE.md, paste
Prompt A. M0 has no kickoff gate (nothing precedes it); its close runs G + F,
and every later boundary runs G → E → F.

## Session 2026-08-12 (b) — Session 0.1: v2 re-scope — org overlay, AutoML×Optuna, prior art

### State
on-track / OPEN — blueprint and prompts rewritten to v2.0, org constitution and
charters added, scaffold extended; still zero infrastructure executed. User's
move: open Session 1 with Prompt A (docs/PROMPTS.md v2).

### Done
- BLUEPRINT v2.0 + PROMPTS v2.0 (supersede v1, same day, at principal's
  direction); docs/org/ORG.md + ROLES.md (7 charters, each with refusals);
  ADR-006 (platform-shaped org overlay), ADR-007 (FLAML scout × Optuna sniper,
  Ray deferred to M9, AutoGluon quarantine-on-request); configs/automl.yaml +
  tuning.yaml; tuning package contract; prior_art.md survey protocol;
  LEARNING_GUIDE + rituals scaffolding; gotchas #15–18; signoffs ledger gains
  Producer/Approver role columns; README/CLAUDE.md/Makefile renumbered to M0–M9.
- Verification: stubs compile, unit sanity passes, all YAML strict-parses,
  Makefile parses (observed in planning sandbox this session).
- Predecessor org docs (ORG.md, EXECUTOR_PLAYBOOK.md) read from the connected
  Ashford repo 2026-08-12; adopt/adapt/surpass recorded in BLUEPRINT §3.

### Decisions
- Principal's new mandates + standing latitude grant recorded VERBATIM in
  BLUEPRINT §2 ("SLE" read as SRE — flagged, reopens if misread). Org geometry:
  platform-shaped (SRE/PRR/gameday + one Staff Reviewer), not bank-shaped
  (ADR-006). AutoML=scout, Optuna=sniper, gate=judge (ADR-007).

### Defects/Surprises
- none in execution (nothing executed). One planning slip, recovered: gotchas
  #15–18 initially landed below the seed-line marker; marker relocated, ordering
  verified programmatically.

### Next
Unchanged in kind, updated in content: open Claude Code in this repo, wire the
protocol line in CLAUDE.md (user's choice of master), paste Prompt A (v2).
Session scope: M0 only — now including the org bootstrap — gated by BLUEPRINT
§9/M0 Accept-when.

## Session 2026-08-12 — Session 0: scaffold and plan (Cowork planning session)

### State
on-track / OPEN — scaffold generated, plan approved, no code executed yet; user's
move: open Session 1 in Claude Code with Prompt A (docs/PROMPTS.md).

### Done
- Four planning forks settled by user (recorded in BLUEPRINT §2 and ADR-001/003;
  selections quoted verbatim there).
- Stack pinned from live sources dated 2026-08-12 (BLUEPRINT §4) — pins are
  hypotheses until M0 re-verifies them.
- Repo skeleton generated; Python stubs compile (`python -m compileall` clean) and
  the sanity test passes (`pytest tests/unit` green in the planning sandbox) —
  NOTHING beyond that is verified; no cluster has ever been created from this repo.

### Decisions
- Flyte 2.x primary with flyte-binary 1.16.x fallback behind a three-attempt wall
  (ADR-002); KServe Standard mode first, Knative decision deferred to an M5 spike
  (ADR-004); DVC versions data, never orchestrates (ADR-005).

### Defects/Surprises
- none — no execution yet. Gotchas ledger pre-seeded from prior-project tuition
  instead (docs/gotchas.md).

### Next
Open Claude Code in this repo. Wire the protocol line in CLAUDE.md (one of the two
options in the comment — user's choice of master version). Paste Prompt A from
docs/PROMPTS.md. Session scope: M0 only, gated by BLUEPRINT §6/M0 "Accept when".
