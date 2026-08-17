# M2 KICKOFF — Modeling I: honest baseline and the gate   (authored by: ARCH/Fable · 2026-08-17 · v3.0: the Architect is sole author)

Session model stated: **Fable 5 (claude-fable-5)** — architect sessions on any
other model are void (ORG.md rule 7).

**M2 carries ◆** (ORG.md RACI): the last story exits to a fresh REV session
(`automation/next_session.sh rev 120`), never straight to ARCH. REV's mandatory
finding + re-derivation rules apply (gotcha #18: fresh session, artifacts only).

## 0. Boundary triage of M1 (the closure sweep, folded in)

**Verify re-run (by the approver, this session, 2026-08-17):** `make verify-m1`
→ **GREEN, exit 0, all 9 sections, every sub-check `ok`** — including the slow
leg run honestly (`ok rebuild-proof GREEN — 16 output(s) byte-identical after a
full re-derive` with the DVC second witness), rejections fully attributed
(`rows_in=57,042,337 rows_out=56,127,878 dropped=914,459 attributed=914,459
rules=10`), corrupt-source refusal typed and named, `dbt build`
`PASS=39 WARN=0 ERROR=0`, marts-redteam red on the named test, all four marts
reconciled in Postgres (56,127,878 · 44,792 · 8 · 80), Metabase on its declared
route with both boards existing AND a card run per board, all four gate
documents present, and the boundary-law grep empty. Closing line verbatim:
`[verify-m1] GREEN — every M1 sub-check passed.`

**Lineage spot-check (gotcha #20):** `git branch -r --contains d954edc`
(M1-S5's story commit) → `origin/main`. Tree clean and level:
`## main...origin/main` at `001a027`.

**Every open finding, condition, and due debt from M1, dispositioned:**

| Item | Disposition |
|---|---|
| F-005 (rejected rows exist only as counts; routed to ARCH at this boundary by its own condition) | **ABSORBED INTO M2-S1 (role:DE) — the ARCH scoping call the row prescribes, decided, not slid.** Landing scope quoted from §9/M2: the DA error memo must answer *"where does it fail: zones? hours? long trips?"* — and the long-trips answer is bounded by rule at 120 minutes unless the discarded `duration_above_max` population (159,300 trips) becomes queryable. Two facts S3 left for this decision both argue IN: the rejection rate is non-stationary (1.428%→2.020%, rising), and val/test are the two dirtiest months — the memo will sit on exactly the data whose discards are least characterized. Stays a FINDING (closes only on its own evidence conditions); ledger row annotated. |
| F-006 (congestion_surcharge availability cliff inside the training window) | **INTAKEN → M2-S2**, its named landing ("closes when M2 records an explicit, evidenced choice"). The kickoff directs the recommendation: EXCLUDE from feature-set v1 (with `airport_fee`, 100% null); a differently-evidenced choice by the MLE also closes it. A silent inclusion does not. |
| F-007 (post-trip columns + meter `trip_distance` are quote-time leakage) | **CONDITION (a) INTAKEN → M2-S2**: `taxi_mlops.features` defines the quote-time feature set with the post-trip columns named as excluded and why. **Condition (b) stays M3's** (dossier resolves `trip_distance` — OSRM/zone-centroid substitute or a recorded assumption). Row stays open until both; annotated. |
| F-001 (starter allowlist; agent cannot self-widen) | **PO fork standing** — AWAITING_PO 2026-08-16-2, non-blocking, unchanged through five M1 sessions. Nothing new owed; the paste is the PO's. |
| D-001 (images → kind nodes) | **CARRY, not due** — landing M4, quoted scope re-verified: §9/M4 *"v1's M3 unchanged: Flyte 2 per docs, **containerized**, ingest→validate→features→train→evaluate→register"*. Ledger row unchanged. |
| 23 GB full-refresh peak (S4's stated cost, S5's pile) | **NEW DEBT D-003, landing M4** with scope quoted from §9/M1-S6: *"From M4 the build+publish runs as the tail task of the monthly Flyte pipeline"* — the story that makes the publish scheduled must make it incremental or record why not. Ledger row added this session. |
| Gotcha #34 (Docker Desktop's lifecycle owns `kubectl`; chain self-heal vs park?) | **ARCH DECISION: the chain PARKS, it does not self-heal.** Launching Windows-side processes from an unattended session is autonomy nobody granted (same class as gotcha #23's hard blocks: the host is the PO's, not the chain's). The recovery is one launch + ~15s and is documented in gotcha #34; every session's staleness check already detects it (S5 proved that live). Risk-table row below; not a fork — nothing is parked today. |
| `_handoff_entry.md` near-miss (the handoff fold was a habit, not a check) | **FIXED FORWARD → M2-S5**: `verify-m2` gains a sub-check that no stray handoff fragment sits at the repo root. A convention that depends on one last manual step will eventually skip it; now something looks. |

**Verdict: M1 CLEANLY CLOSED — tagged `m1-closed`.** All §9/M1 accept-when
legs green against the quoted text, verify re-run green at the boundary by the
approver, sign-off row added (producer EXEC S1–S5, PRs #5–#9; approver
ARCH/Fable — producer ≠ approver holds), no open item carried silently.

## Preconditions (verified LIVE at draft time 2026-08-17 — pastes, not memory)

| Precondition | Check run | Observed |
|---|---|---|
| M1 gate green at the boundary | `make verify-m1` | GREEN, exit 0, all sections `ok` (paste in §0 / HANDOFF (v)) |
| Cluster up | `kubectl get nodes` | 3/3 Ready, v1.36.1, ~48m old (S5's planned rebuild) |
| MLflow up and EMPTY — M2 writes the first real experiments | `curl localhost:5000/health` · `POST /api/2.0/mlflow/experiments/search` | `200` · exactly one experiment: `{"experiment_id":"0","name":"Default"}` — nothing to collide with |
| Metabase up (S4 adds the error-segment board) | `curl localhost:3030/api/health` | `200`; verify-m1 confirmed 2 dashboards / 17 cards, every card on the `marts` warehouse |
| Analyst layer live (S1 extends it; S2 reads splits from it) | `ls data/analyst.duckdb` + verify-m1 leg 1–2 | present (274,432 bytes); every view count reconciled to the ingest reports inside the gate run |
| Splits configured | `configs/train.yaml` | train `2019-01`…`2019-06` · val `2019-07` · test `2019-08` · target `trip_duration_minutes` · `model: {}` awaiting M2 |
| ML deps not yet present | `grep -E "lightgbm\|mlflow\|scikit" pyproject.toml` | empty — S2 adds `lightgbm`/`mlflow`/`scikit-learn` via `uv add` (resolve live, never pre-pin from memory; pins → CLAUDE.md). MLflow SERVER is 3.15.1 — check client/server compatibility at add time (gotcha #14's shape arrives at M5; cheaper to match now) |
| Disk headroom (sidecar ~+1 GB, predictions parquet, LightGBM artifacts) | `df -h /home/longt` | 948G free |
| Tree clean, level with origin | `git status --short --branch` | `## main...origin/main`, clean, HEAD `001a027`, tag `m1-closed` |

## Debt intake (every ledgers/debt.md row landing here, by id — or a PO fork, never a silent re-carry)

| Debt id | Origin | What lands here | Absorbed into story |
|---|---|---|---|
| — | — | **No debt row lands at M2.** D-001 (M0-S2) lands M4 (quoted in §0). D-003 (raised at this boundary) lands M4 (quoted in §0). Both restated so the carries are visible, not silent. | — |
| (findings intake) | F-005 · F-006 · F-007(a) | Findings are not debt, but their landings are honored the same way: F-005 → S1 · F-006 → S2 · F-007(a) → S2. Each closes ONLY by its ledger row's own evidence conditions. | S1, S2 |

## Gate being served (BLUEPRINT §9/M2, quoted)

> As v1's M2 (baseline, LightGBM v1, signature, promotion gate red-teamed with
> a hobbled model) + DA error-analysis memo (where does it fail: zones? hours?
> long trips?). The memo's segment queries also become a Metabase
> **error-segment board** [v2.5], so the model's weak spots stay visible to
> everyone, not buried in a doc. Accept when: v1's M2 gate AND the memo cites
> specific segments with numbers AND the error-segment board renders and is
> linked from the memo. Show: refusal transcript + memo + board.
> ◆ REV reviews M2 in a fresh session (mandatory finding; re-derives one
> metric from raw predictions).

Standing law restated for every story: reported numbers come from
`taxi_mlops.training.evaluate` ONLY (gotcha #15) · the honest reference floor
is the **group-median 3.7170 val MAE**, never the constant-median 7.8866
(M1-S3, quoted in CLAUDE.md) · `month` is a reporting dimension, never a
feature · marts boundary law: `grep -r "analytics" src/taxi_mlops/` stays
empty; marts may read model OUTPUT FILES, model code never reads marts.

## Stories (5; each independently finishable, safe stopping point after each)

### M2-S1 — The rejected rows become queryable (F-005 lands)  (role:DE)
Do: extend `taxi_mlops.data` ingest to RETAIN rejected rows as a sidecar under
`data/rejected/` (per month, parquet, each row carrying the NAME of the rule
that rejected it; a row failing multiple rules is the executor's craft call —
first-match or all-match — recorded in the config/docstring). The refusal path
is UNTOUCHED: a month refused for structure or `max_rejected_fraction` writes
no sidecar — refusals are structural, sidecars are for counted rows. Knobs in
`configs/data.yaml`, none hardcoded. Re-run `make data` end-to-end: the
processed outputs must come back **byte-identical** (same rows dropped, same
writer pins — this is a free re-proof, and a drift here is a real defect, not
noise). DVC order law holds (gotcha #33): sidecar tracked as its own target
(`data/rejected.dvc` or folded per DVC layout — craft call), pinned LAST.
Analyst layer gains `trips_rejected` (a VIEW) plus reconciliation: per-month,
per-rule sidecar counts must EQUAL the ingest report's counted rejections
(914,459 total) or `make duckdb` exits 1 — same law the other views obey. Then
ANSWER the finding's question with committed queries: what IS the
`duration_above_max` population (159,300 trips)? Duration distribution beyond
120, OD-pair/airport concentration, fare shape — meter faults or a real
long-haul population, decided with numbers. Close F-005 in the ledger with
that evidence, in the same PR.
Accept when: `make data` green with sidecar; per-rule reconciliation exact
(914,459, table printed); `make rebuild-proof` still GREEN after the change;
the characterization is committed (EDA appendix or `docs/` note citing named
views only); F-005 ledger row closed by its own conditions; PR green +
lineage.
Evidence plan: reconciliation table + rebuild-proof paste + the
characterization's numbers + the ledger diff.
Safe stop: after merge; data path whole, finding closed, nothing else touched.

### M2-S2 — Quote-time features, honest baselines, LightGBM v1 — all through one evaluator  (role:MLE)
Do: `taxi_mlops.features` — the ONE transform path for training AND serving
(convention already law). Feature-set v1 is **quote-time pure**: temporal
decomposition (hour, dow — never `month`), PU/DO zone ids, `passenger_count`;
EXCLUSIONS NAMED IN CODE with reasons — the six post-trip columns (F-007(a):
this is its closing evidence), `trip_distance` (meter-driven; M3's dossier
owns the substitute — record the deferral where the exclusion lives),
`congestion_surcharge` (F-006: recommended EXCLUDE, citing the 2019-01-21
cliff; an alternative evidenced choice also closes the finding — a silent
inclusion does not), `airport_fee` (100% null). `taxi_mlops.training` with
`evaluate` as THE metric source (gotcha #15): MAE + within-5-min (KPI-09 /
KPI-10 get their FIRST measured values here, cited by id). Evaluate must
re-derive both baselines through the same code path the model uses — constant
train-median AND group-median (hour, dow, PU, DO) with an explicit
unseen-group fallback (~0.017% of val/test rows carry unseen OD pairs; a KeyError
path is a crash in serving's shape). Expect ≈7.89 / ≈3.72 val MAE — a large
disagreement with the EDA's SQL floors is a bug in evaluate, not a discovery.
Then LightGBM v1 on feature-set v1 (`log1p` target transform is available and
EDA-argued; craft call, recorded), params in `configs/train.yaml`, run logged
to MLflow (experiment `m2-modeling` — namespaced now so gotcha #17 never
bites), with **signature + input example** on the logged model. All three
contenders' val/test numbers printed by ONE `evaluate` invocation path.
Accept when: features module names every exclusion with its reason (F-007(a)
+ F-006 evidence; ledger rows updated in the PR); `evaluate` prints the
baseline floors and LightGBM v1 val/test MAE + within-5 from one code path;
MLflow holds the runs with params, metrics, signature, input example; unit
tests cover the unseen-group fallback and the exclusions (a post-trip column
reaching the feature matrix must FAIL a test); PR green + lineage.
Evidence plan: the evaluate table (3 contenders × val/test) + MLflow run ids +
the exclusion docstrings/test.
Safe stop: after merge; model exists and is measured, nothing promoted yet.

### M2-S3 — The promotion gate: it can say no, and it is watched saying no  (role:MLE)
Do: `make train` becomes real (config-driven, one command). Promotion gate:
challenger must beat the **group-median floor** on the untouched TEST month by
a margin set in `configs/train.yaml` (MLE chooses the margin with a reason;
gates loosen only via PO fork ever after; the flattering constant-median floor
is named in the config comment as NOT the bar). Winner gets the `champion`
alias in the MLflow registry; gate verdict PRINTED with both numbers either
way. **RED-TEAM: a deliberately hobbled model** (shuffled target or 1% sample
— executor's pick) submitted through the SAME gate → REFUSED, transcript
pasted with both numbers, and the hobbled run/model cleaned up or clearly
marked — it must never linger as champion or pollute the registry namespace.
Then the real v1 promotes: registry shows v1 with signature, alias set.
Accept when: gate refuses the hobbled model (transcript with both numbers);
real v1 promoted with `champion` alias + signature; thresholds live in
`configs/train.yaml` with the reason comment; re-running the gate on the same
champion is a stated no-op; PR green + lineage.
Evidence plan: refusal transcript + promotion transcript + registry listing
(`mlflow` API paste).
Safe stop: after merge; champion aliased, gate proven refusing.

### M2-S4 — The error memo and the error-segment board  (role:DA; MLE consulted on interpretation)
Do: `evaluate` (S2's path — extend, don't fork it) writes row-level
predictions for val+test as parquet under `data/predictions/` (keys, y, yhat,
model version) — model OUTPUT files, which marts may read (boundary law's
one-way door; the grep stays empty). Analyst view over it, reconciled
(prediction row count == split row count or exit 1). dbt gains an
`error_segments` mart (grain: segment × split — zones, hours, duration bands
INCLUDING the 100–120 tail; S1's sidecar characterization is the context for
what sits just past the boundary) published to the one Postgres by the
existing `make marts` path. **DA error memo** (`docs/error_memo_m2.md`):
where does v1 fail — zones? hours? long trips? — every number from a named
view/mart or from evaluate's artifacts, KPI-09/KPI-10 cited by id with their
S2-measured values. New segment metrics that deserve ids get NEW ones
(KPI-11…, additive — the id law: a changed formula is a new id, never an
edit). **Error-segment board** in Metabase from checked-in JSON via the
existing `scripts/metabase_boards.py` path, every card citing a KPI id,
linked from the memo. KPI-09/KPI-10 may now appear on cards ONLY as values
sourced from evaluate's published artifacts, never computed in SQL — if the
mart cannot carry them honestly, the cards state the value's provenance.
Accept when: memo cites specific segments with numbers; the board renders via
the API (existence + a card RUN, the verify-m1 precedent) and the memo links
it; predictions reconciliation exact; boundary-law grep still empty; PR green
+ lineage.
Evidence plan: the memo + board API listing + reconciliation paste.
Safe stop: after merge; weak spots visible to everyone, in doc and board.

### M2-S5 — verify-m2, red-teamed, and the ◆ exit  (role:MLOps)
Do: implement `make verify-m2` per its Makefile contract, superseding the
stub, covering at least: registry holds v1 with signature + champion alias ·
the gate refusal transcript exists with both numbers · MLflow experiment
`m2-modeling` holds the runs · evaluate's numbers are the ONLY KPI-09/KPI-10
source (doc-contract tests already forbid the rest) · predictions
reconciliation · `error_segments` mart queryable with counts reconciled ·
error-segment board exists via API AND a card runs · memo exists and links
the board · marts boundary grep empty · **no stray `_handoff_entry.md` (or
sibling fragment) at repo root** — the (u) near-miss becomes a check. Then
**red-team it once**: break one leg (e.g. drop the champion alias) → RED
naming exactly that leg, others still counted → restore → GREEN (both
pasted). Wire in what M1's gate taught: every sub-check asserts a POSITIVE
count or a matched line — a check wired to no sensor is a green light;
`--verify`-style probes stay impatient (60s), deploys stay patient.
Accept when: `make verify-m2` GREEN exit 0 with every sub-check printing;
red-teamed to RED once naming the broken leg (both transcripts pasted); PR
green + lineage.
Evidence plan: both verify transcripts.
Safe stop: the M2 exit. **Ritual: M2 carries ◆ →
`automation/next_session.sh rev 120`** (fresh REV session, artifacts only,
mandatory finding, re-derives ≥1 metric from raw predictions — the
predictions parquet exists precisely so REV can). REV exits to
`automation/next_session.sh architect 120` for the M2 boundary.

## Out of scope (named now so creep is visible later)

FLAML/Optuna and any tuning beyond hand-set v1 params (M3) · the feature
dossier, OSRM / zone-centroid distances, and ANY `trip_distance` substitute
(M3 — F-007(b) lands there) · train-only aggregate features (M3's artisan
track) · Flyte / containerized pipelines (M4; D-001, D-003 land there) ·
serving, KServe, parity tests (M5) · drift machinery (M7) · Feast (M8) ·
incremental mart materialisation (M4, D-003) · widening the session allowlist
(PO's hands, AWAITING_PO 2026-08-16-2) · loosening any gate or threshold
(PO fork, ever).

## Risks & walls (carried counts restated; fallbacks cite ADRs)

| Risk / wall | Count | Fallback |
|---|---|---|
| LightGBM/scikit resolve friction against pandas 3.x / numpy 2.5 (pyproject pins) | 0 | 3-attempt wall → quarantine the pressure, never downgrade the core stack (gotcha #16's law; ADR-002's spirit). Record the resolution in CLAUDE.md pins either way |
| MLflow CLIENT vs server 3.15.1 skew (registry aliases, signature API) | 0 | Match major at `uv add` time; if the resolver fights, pin client to the server's line — gotcha #14 is the M5 bill for getting this wrong |
| Training memory on 6 months (~42M rows × few features, 47Gi WSL) | 0 | Sample-first protocol (artisan playbook's law arrives early): prove the path on 1 month, then scale; LightGBM histograms are frugal — if memory walls anyway, train on a documented sample and STATE it (never silently) |
| Sidecar rewrite breaks byte-identity of processed outputs | 0 | It must not (same rows, same writer) — if bytes wobble, that IS a finding on the ingest change, not noise; rebuild-proof is the tripwire (gotcha #33's order law holds) |
| Hobbled model lingers as champion / pollutes registry | 0 | The red-team leg's own accept-when: cleanup or explicit marking is part of the transcript |
| Predictions/marts grain confusion (row-level predictions are model artifacts, not a mart) | 0 | Boundary law one-way door: marts READ `data/predictions/` files; nothing in `src/taxi_mlops/` names `analytics` (grep is a gate leg) |
| Docker Desktop down after host restart — `kubectl: command not found` at 3am | 1 (M1-S5) | Gotcha #34: the chain PARKS naming the gotcha (ARCH decision §0); recovery is one launch + ~15s, kind self-restarts; NEVER self-launch Windows processes |
| Kaspersky TLS on new PyPI wheels (gotcha #9) | 0 | Import AV root CA into WSL trust — never disable verification |
| Two writers on append-only docs (PO opens a parallel window) | 1 (M0-S1) | Rebase onto origin/main, keep theirs, renumber yours; never force-push main |
| Allowlist friction (F-001) | n/a | Known workarounds (`make` targets, `python3`, file tools); non-blocking; the paste stays in AWAITING_PO 2026-08-16-2 |

## Open PO questions (options · recommendation · default-with-date)

None blocking — the chain continues. Standing, non-blocking: **AWAITING_PO
2026-08-16-2** (allowlist paste, Option A recommended; F-001 closes when a
session runs `chmod`/`ls` unprompted).

## ARCH self-check (v3.0)

model stated Fable: **yes** (claude-fable-5, first line) · every story sized
for one short executor session: **yes** (S2 fattest — features + baselines +
model — but every metric flows through one evaluator and the floors are
pre-computed references; S1 rides the proven ingest/DVC/duckdb patterns;
walls named) · debt intake diffed against ledgers/debt.md: **yes** (D-001 and
D-003 both restated not-due with quoted M4 landings; no row lands here;
findings F-005/F-006/F-007(a) intaken by id into S1/S2) · forks routed to
AWAITING_PO: **yes** (none new; one standing non-blocking entry restated;
gotcha #34 resolved as an ARCH decision, not a fork — nothing parked)
