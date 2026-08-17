# Design Review — 2026-08-17 (M3-S2)

Date: 2026-08-17 · Story: M3-S2 · Milestone: M3 (Modeling II — craft ×
automation, side by side) · Convened by the M3 kickoff, §"M3-S2", six named
agenda items.

**Under review:** the plan the next three stories will execute —
`docs/feature_dossier.md` (authored this session), `docs/artisan_playbook.md`
(v1.0, committed 2026-08-12), `configs/automl.yaml`, `configs/tuning.yaml`,
`configs/train.yaml: features/baselines/gate`, and
`src/taxi_mlops/features/quote_time.py` **as committed at `b5708d5`** plus this
story's working tree — not a remembered version of any of them.

Roles present (as blocks, PROMPTS.md Prompt D):

```
── role-block: role:DA · story: M3-S2 ──
charter read: yes · open findings owned by this role: none at entry
this block produces: the live harvest, the zone-centroid artifact and its
  proofs, the three measurements in dossier §3 · refusals in play: a number
  without its definition and window; querying raw parquet when the analyst
  layer exists; explaining a result by restating it
```

```
── role-block: role:MLE (hat, for the review) · story: M3-S2 ──
charter read: yes · open findings owned by this role: F-007(b) (closing here),
  F-008/F-010/F-011/F-012/F-013 (all M3-S1's, PARKED — see §0)
this block produces: decisions DR-01…DR-06 · refusals in play: quoting an
  AutoML-internal number as a result; touching the promotion gate or the
  holdout month's role in it; features outside taxi_mlops/features
```

**Data every figure was run against:** the DuckDB analyst layer built at M2-S4
(12 views, 3 reconciliations green) — `trips_train` (43,987,422 rows),
`trips_clean` (56,127,878), `trips_val`, `trips_test` — joined to
`data/reference/taxi_zone_centroids.csv` (263 rows, sha256 `37910367…`). No raw
parquet was read.

---

## 0. The one thing this review could not do, said first

**M3-S1 has not run.** This session opened to a host where Docker Desktop was
not running (gotcha #34: `/mnt/wsl` held only `resolv.conf`, so `kubectl` and
`docker` are dangling symlinks and the kind cluster is down). S1 needs the live
MLflow registry — its four findings close only on a watched incumbent refusal,
a floor-mismatch write refusal, and `make verify-m2` GREEN 49/49. So S1 is
parked and S2 was taken as the next independent story, exactly as the kickoff's
sequencing permits: **S2 promotes nothing.**

The consequence for this ritual is confined to one agenda item. **DR-06 fixes
the POLICY the bake-off is judged under and names the number S1 must fill.** It
is minuted as a decision with a forward dependency, not as an open question —
but nobody should read it as if S1's measurement already exists.

---

## 1. Agenda item 1 — equal budgets · decision **DR-01**

**The problem with "equal budgets" as written.** BLUEPRINT §9/M3 requires "two
workflows, equal budgets". `configs/automl.yaml` pins `time_budget_s: 1800`;
`docs/artisan_playbook.md` §3 says "one loop ≈ 30–45 min; budget = automation
track's". Taken literally that gives the artisan **one loop**, which cannot
execute the playbook's own stop rule ("two consecutive loops below threshold").
The two documents were written to different units — a scout's wall-clock cap
versus a human-ish iteration count — and neither is wrong alone.

**DR-01 (adopted).** Budgets are equalised in **model-fitting wall-clock
seconds**, and both tracks **report their actual spend** so the equality is
checkable rather than asserted.

| track | budget | derivation |
|---|---|---|
| automation (S4) | 2 × 1800 s scout (`time_budget_s`, run on v1 and on v2) + one Optuna study of `n_trials: 60` | already pinned in `configs/automl.yaml` / `configs/tuning.yaml`; **not edited by this review** |
| artisan (S3) | **9,000 s (150 min)** of fitting wall-clock | 3,600 s of scout + an estimated ~5,400 s for 60 pruned TPE trials on the playbook's ~15% sample |

Conditions, all three binding:

1. Each track prints its **measured** fitting seconds in its story PR. The
   §9/M3 "equal budgets" claim is then a number somebody can check, which is
   the only kind this program accepts.
2. If S4's *actual* spend lands materially under 9,000 s, S5's bake-off table
   states both actuals and says so. **We do not retroactively hand the loser
   more budget** — an unequal race that is reported honestly is a result; a
   race re-run until the preferred side wins is not.
3. Budget is *fitting* time, not session time. Reading, writing the ledger and
   arguing are free, on both sides, because they are free for neither.

**Dissent (DA), recorded.** 9,000 s is an estimate resting on an unmeasured
per-trial cost; if Optuna's 60 trials come in at half that, the artisan will
have had roughly double the automation track's compute and the bake-off's
headline ("craft vs automation") is compromised in the artisan's favour.
**Answer (MLE):** accepted as a real risk, which is exactly why condition 2
requires both actuals to be printed rather than the budget to be trusted. The
alternative — measuring S4 first and sizing S3 from it — inverts the kickoff's
story order for no gain, since S3's own stop rule may end it well under budget.
**Action AI-1 carries this.**

---

## 2. Agenda item 2 — the keep-threshold for feature groups · decision **DR-02**

**DR-02 (adopted, with one addition).** The playbook's default stands: a
feature GROUP is kept only if it improves **relative val MAE by ≥ 0.50%**.
Re-argued rather than inherited, because a threshold nobody re-derived is a
number nobody will defend at S5:

- **It is not a noise threshold.** On 6,189,748 val rows, 0.50% of a ~3.48 min
  MAE (≈1.04 s) is far outside sampling noise. Statistical significance is not
  what this bar is for.
- **It is a maintenance-cost bar**, the same argument `configs/train.yaml: gate`
  makes for the gate's 2.00%: every admitted group is code in the ONE shared
  transform path, a serving dependency (gotcha #21), and a thing that can break
  at 3am. A group worth less than a second of mean error does not earn that.
- **Addition (DA's, accepted):** the ablation table must report **KPI-10
  (within-5-min rate) per group alongside val MAE**, and a group that improves
  the mean while *lowering* KPI-10 is escalated in the S3 PR rather than
  auto-kept. This mirrors the gate's two-condition shape without duplicating
  the gate — a mean over 6M rows can improve while more riders are quoted
  wrongly, which is the exact failure `docs/error_memo_m2.md` was written about.
- **Anti-forking-paths condition:** the groups are declared in a fixed order
  **before** S3 fits anything (DR-03), and the ablation reports every group
  tried, including the dropped ones. A table showing only survivors is a
  garden of forking paths with the forks pruned.
- Full-scale confirmation before "keep" remains law (playbook §3.1): sample-first
  iteration, winners re-measured at full scale.

---

## 3. Agenda item 3 — both tracks' search plans · decision **DR-03**

**DR-03 (adopted).** The two tracks are given **disjoint search axes**, and
this is what makes the 2×2 bake-off able to isolate anything at all:

> **The artisan searches FEATURES and holds hyperparameters at v1's.
> The automation track searches HYPERPARAMETERS and is handed feature sets it
> does not invent.**

Without this the 2×2 has four cells that each vary both axes, and "was it
features or was it tuning?" — the question §9/M3 asks the table to answer —
becomes unanswerable.

**Artisan (S3), groups in this fixed order**, from `docs/feature_dossier.md`:

| group | dossier rows | what it tests |
|---|---|---|
| G1 temporal extras | 3, 4, 5, 6 | does finer/cyclic/calendar time beat a bare integer hour for a tree? |
| G2 centroid geometry | 7, 8, 9, 10, 11 | the F-007(b) substitute and its relatives — the group we expect to pay |
| G3 spatial identity | 12, 13 | airport flags + borough pair; aimed at the 1.48% fallback rows and the airport segment |
| G4 trip re-encodings | 17 | passenger-count buckets; expected ~zero, included so "expected zero" is measured once |
| G5 point-in-time aggregates | 14, 15, 16 | the HIGH-leakage family, train-only and point-in-time — and the source of S3's mandated red-team |

Hyperparameters stay at v1's (`configs/train.yaml`), seeds fixed, early stopping
on val, one change per experiment, one MLflow run in `m3-artisan` per row.

**Automation (S4):** FLAML scout under `configs/automl.yaml` **twice** — once
on v1, once on S3's v2 — producing a family + starting params, every internal
number labelled **scout-internal** (gotcha #15). Optuna sniper centred on each
scout winner, TPE + MedianPruner per `configs/tuning.yaml`, study namespaced
`m3` (gotcha #17), storage in the one Postgres via D-002's recipe.

**Neither track touches the gate, the evaluator, or the test month.** The test
month is read exactly once per contender, at S5.

---

## 4. Agenda item 4 — F-007(b), formally · decision **DR-04**

**The question.** `trip_distance` is the single strongest predictor in the data
(`r` = 0.8066 raw, 0.8464 in logs — `docs/eda_report.md` §9) and it is the
meter's **driven** distance, recorded when the trip ends. A quote-time ETA
service does not have it. F-007 condition (b) requires M3 to resolve this
either with an honest substitute or with a recorded assumption that the meter
distance is treated as available.

**DR-04 (adopted, unanimously).** **`trip_distance` stays excluded. The
zone-centroid haversine distance is the quote-time substitute**, together with
its relatives (dossier rows 7–11). The decision rests on a measurement made
this session, not on preference:

| predictor | `r` with target | in logs | status |
|---|---|---|---|
| `trip_distance` (meter, post-trip) | 0.8068 | 0.8279 | **excluded by law** — `EXCLUSIONS` + `FeatureLeakageError` |
| zone-centroid haversine (quote-time) | **0.7873** | 0.7734 | **adopted as the substitute** |

43,439,267 train rows. **The substitute retains 97.6% of the excluded feature's
raw correlation with the target.** The choice therefore costs about 2% of a
correlation and buys a model that can actually be served — which is not a
trade-off, it is a bargain, and it is the reason this was worth measuring
instead of arguing.

Supporting evidence (dossier §3a): centroid distance correlates with the meter's
driven distance at **0.9661** over 41.2M rows, straight-line ≤ driven on
**81.662%** of them, median circuity **1.2952**.

**Three conditions attached to DR-04, all of them S3's to satisfy:**

1. **The 1.1–1.2% with no geometry is an explicit path, not a NaN.** Zones
   264/265 are "Unknown" and get no centroid by design. Measured: train
   1.2462%, val 1.0113%, test 1.0753%. Every spatial feature owes them a named
   fallback **and a test**. Precedent and warning: the ~1.48% unseen-OD
   fallback rows buy **75.4%** of the current champion's whole advantage
   (`docs/error_memo_m2.md` §1) — the small fraction is where the value is.
2. **Circuity (dossier row 19) is REFUSED**, because it is defined as driven ÷
   straight-line and the numerator is the excluded column. It survives as an
   EDA statistic only. Recorded so a future session finds the refusal rather
   than re-inventing the feature.
3. **The exclusion registry does not get an exception.** `EXCLUSIONS` keeps
   refusing `trip_distance` at both ends (config and matrix); the `revisit`
   note on that entry is discharged by pointing at this decision, and the
   column is not re-admitted.

**F-007 closes on this decision** (condition (a) was discharged at M2-S2). The
ledger row is updated in this story's PR.

---

## 5. Agenda item 5 — bake-off comparability · decision **DR-05**

**DR-05 (adopted).** All five S5 contenders — the gate's floor baseline, M2
champion v1, artisan-v2, auto-tuned-on-v1, auto-tuned-on-v2 — share ONE fitting
window and ONE measurement path:

1. **Full-data, TRAIN-ONLY fits.** Every contender is refit on the full
   configured train months before it faces the gate. **`docs/artisan_playbook.md`
   §3.7's "refit the winning config on train+val" is NOT used at M3** — recorded
   explicitly, because it is committed curriculum and a future reader would
   otherwise assume it applied. Reason: val is where early stopping looked, and
   a contender refit on train+val is measured against a floor fit on train
   alone, so the two are no longer the same experiment.
2. **Scout and sniper sample by design, and sampled numbers never face the
   gate.** F-008 measured the trap: on a one-month sample the floor degraded
   faster than the model and the margin *improved* 7.07% → 16.85%. Sampled runs
   are scout-internal (gotcha #15). **This rule's enforcement is M3-S1's**, and
   S1 has not run — see DR-06 and AI-4.
3. **One evaluator, one test month, one shot per contender**
   (`taxi_mlops.training.evaluate`). All five gate verdicts are printed,
   including the floor's REFUSE against itself.
4. **An automation loss — or an artisan loss — is a result**, reported as such.
   Neither track is re-run to improve its showing.

---

## 6. Agenda item 6 — the bar the bake-off is judged against · decision **DR-06**

**Status: policy decided here; the number is M3-S1's to measure and record.**
S1 is parked (§0). This item is minuted rather than deferred because the thing
a Design Review owes is the *rule*, and the rule can be fixed now in a way that
constrains whatever S1 measures.

**DR-06 (adopted).**

1. **The bake-off is judged by the S1-hardened gate, unchanged, at S5.** No
   contender is compared against a bar assembled at S5.
2. **The honest headroom is +2.71%, and nothing in M3 may quote +7.07% as
   headroom.** F-010 re-derived that giving the SAME floor one more backoff
   level (global → OD-pair → global) collapses v1's margin from +7.07% to
   **+2.71%** against a 2.00% bar. v1's promotion still stands; the claim that
   the bar has room to spare does not. This review adopts F-010's number as the
   milestone's working headroom.
3. **S1 chooses the floor and re-argues the bar in `configs/train.yaml: gate`,
   with the reasoning in the comment** — either adopting
   `baseline-group-median-od-fallback` as the gate's floor with the bar
   re-argued against ITS margin, or keeping the published floor with the bar
   re-argued against **+2.71%**. Both are tightening or honesty; neither is a
   PO fork (CLAUDE.md: gates loosen only via PO fork; tightening is the MLE's
   to argue).
4. **What this review forbids, whichever S1 picks:** the bar may not be
   *loosened*; the floor may not be *edited* in place (a deeper hierarchy is a
   NEW named baseline — `configs/train.yaml: baselines` already legislates
   this); and the bake-off may not begin before S1 has merged, because F-011
   means an unhardened gate can hand `@champion` to a model worse than the one
   serving.
5. **S5 quotes the bar's number from `configs/train.yaml` as committed**, not
   from these minutes. Minutes are a record of an argument; the config is the
   gate.

**Dissent (DA), recorded.** Minuting a decision whose central number does not
exist yet risks reading, in six months, as if the review had seen it.
**Answer (MLE):** accepted; hence this section's status line, §0, and AI-4 —
S1 must link back to DR-06 when it records the number, so the two halves of the
decision are findable from each other.

---

## 7. Action items

| id | action | owner | due | status |
|---|---|---|---|---|
| **AI-1** | Print measured fitting wall-clock seconds for the track, in the story PR (DR-01 condition 1) | MLE | S3 **and** S4 | open |
| **AI-2** | Ablation table reports KPI-10 per group beside val MAE; every group tried is listed, survivors and drops (DR-02) | MLE | S3 | open |
| **AI-3** | Every spatial feature gets a named, tested fallback for zones 264/265 (DR-04 condition 1) | MLE | S3 | open |
| **AI-4** | S1 records its floor/bar decision in `configs/train.yaml: gate` with a comment citing **DR-06**; S5 quotes the config, not these minutes | MLE | S1, then S5 | open — **S1 parked** |
| **AI-5** | S5's bake-off table states both tracks' actual budget spend and flags any material inequality (DR-01 condition 2) | MLE | S5 | open |
| **AI-6** | `configs/features.yaml`'s stale `v1` line (naming `trip_distance`, which DR-04 keeps excluded) is resolved when feature sets get ONE home — F-013's features half | MLE | S3 | open — **not this story's** (kickoff routes it to S3) |

## 8. Decisions at a glance

| id | decision | agenda item |
|---|---|---|
| DR-01 | Equal budgets in fitting wall-clock seconds; artisan 9,000 s; both tracks report actuals | 1 |
| DR-02 | Keep-threshold ≥0.50% relative val MAE, re-argued as maintenance cost; KPI-10 reported per group; fixed group order; all groups listed | 2 |
| DR-03 | Disjoint search axes — artisan searches features, automation searches hyperparameters; five artisan groups in a fixed order | 3 |
| DR-04 | **F-007(b) resolved**: `trip_distance` stays excluded; zone-centroid haversine is the quote-time substitute (retains 97.6% of its correlation); three conditions attached | 4 |
| DR-05 | Bake-off: full-data train-only fits for all five; playbook §3.7's train+val refit explicitly NOT used at M3; one evaluator, one shot | 5 |
| DR-06 | Bake-off judged by the S1-hardened gate; **+2.71% is the working headroom, +7.07% may not be quoted**; S1 sets the number in the config; bar may not be loosened | 6 |
