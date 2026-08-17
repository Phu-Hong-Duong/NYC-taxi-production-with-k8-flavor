# The promotion gate — M2-S3 (role:MLE, 2026-08-17)

The gate is the one place this program is allowed to say **no** about a model.
This document is its argument, its two transcripts, and its limits. Every number
below came from `taxi_mlops.training.evaluate` and nowhere else (gotcha #15).

- Code: `src/taxi_mlops/training/gate.py` (decides) · `registry.py` (acts)
- Knobs: `configs/train.yaml: gate` and `: registry` — **loosening any of them is
  a PO fork, not an edit** (CLAUDE.md). Tightening is the MLE's to argue.
- Commands: `make train` (exit 0 promoted · **exit 1 refused**) ·
  `make train-redteam` (expects the refusal; inverts the exit code)

---

## 1. What the gate requires, and why those things

| Condition | Value | Why this and not something else |
|---|---|---|
| Split judged | `test` (2019-08, 5,950,708 rows) | Early stopping reads **val** (`model.early_stopping_rounds: 30`). A verdict on val would score a model against a month it has already been fitted to once. `decide()` **raises** if handed metrics from any other split — the holdout's role in the gate is not a knob. |
| The bar | `baseline-group-median`, re-derived in the same run | A floor quoted from a document drifts away from the data in silence; one recomputed every run cannot. Passing `baseline-constant-median` in **raises** rather than flatters. |
| KPI-09 margin | **≥ 2.00%** below the floor | See §2. |
| KPI-10 | must not regress vs the floor | KPI-09 is a mean over ~6M rows; KPI-10 is what one rider experiences. A challenger that improves the average while quoting more riders wrongly has optimised what we report and degraded what we promise — and only the second is on M5's SLO. This condition can refuse a model the margin would admit, and a unit test holds that shape. |
| Servability | signature **and** input example, read back from the logged artifact | The MLE charter refuses "a model registered without signature + input example". `registry.assert_servable` reads the metadata **back** rather than trusting that the logging call passed one: those are two different claims, and only the second is what a serving container finds. |

## 2. Why the margin is 2.00%

The measured gap between LightGBM v1 and the honest floor on test is **7.07%**
(3.2608 vs 3.5090 min). The bar is set at 2.00% — with headroom, deliberately,
so it is a bar and not a rubber stamp cut to fit the model we happen to have. A
margin of 7% would have admitted v1 by a hair and made every future re-run a
coin-flip; a margin of 0% would promote a tie.

**It is not a statistical bar.** Over 5,950,708 test rows even 0.5% would be
significant. It is a **maintenance-cost** bar: 2% of the floor is ~4 seconds of
mean error, and a model whose entire advantage over a `GROUP BY` is four seconds
does not earn a booster to serve, a registry version to track, and a rollback
path to rehearse. Below that line, ship the lookup table.

**The flattering floor is named in the config as NOT the bar.** Against
`baseline-constant-median` (7.6667 min on test) v1 reads as a **57%** triumph.
That is the number a demo quotes and a rider never feels. The red team below
makes the cost of that choice concrete: the hobbled model **ties** the flattering
floor to four decimals (+0.00%), so a gate built on it with any margin at or
below zero would have promoted a model fitted to permuted labels.

## 3. Transcript A — the gate REFUSING a hobbled challenger

`make train-redteam`. The challenger is fitted on **permuted train labels**; val
and test labels are untouched (shuffling those would be a broken *measurement*
rather than a broken *model*, and the gate would be refusing the wrong thing).
It goes through the same fit, the same evaluator and the same gate, with
**promotion enabled** — the proof is that the gate stopped it, not that a flag
did.

```
== RED TEAM: a challenger hobbled with 'shuffled-target' goes through the REAL gate ==
== A pass here would mean the gate admits a model fitted to permuted labels. ==

-- registry BEFORE the red team --
registered_model=nyc-taxi-eta versions=[]
  alias @champion -> UNSET

[data] train   43,987,422 rows  months=2019-01,2019-02,2019-03,2019-04,2019-05,2019-06
[data] val      6,189,748 rows  months=2019-07
[data] test     5,950,708 rows  months=2019-08

[model] RED TEAM: fitting a deliberately hobbled challenger (shuffled-target)
[model] It goes through the same fit, the same evaluator and the same gate.
[model] HOBBLED (shuffled-target): train labels permuted; val and test are UNTOUCHED
Training until validation scores don't improve for 30 rounds
Early stopping, best iteration is:
[1]     val's l1: 7.88657
[model] best_iteration=1

  contender                            split       rows      KPI-09      KPI-10     RMSE   medAE   p90AE
  -----------------------------------  -----  -----------  ----------  ----------  ------  ------  ------
  baseline-constant-median             val      6,189,748      7.8866     47.505%  12.201   5.283  17.850
  baseline-constant-median             test     5,950,708      7.6667     48.372%  11.844   5.183  17.133
  baseline-group-median                val      6,189,748      3.7170     78.693%   6.222   2.342   7.933
  baseline-group-median                test     5,950,708      3.5090     80.322%   5.811   2.292   7.317
  lightgbm-v1-hobbled-shuffled-target  val      6,189,748      7.8866     47.433%  12.201   5.283  17.853
  lightgbm-v1-hobbled-shuffled-target  test     5,950,708      7.6667     48.303%  11.844   5.183  17.134

==============================================================================
[gate] PROMOTION GATE — configs/train.yaml: gate (loosening it is a PO fork)
[gate] holdout   : test — 5,950,708 rows, untouched by training and by selection
[gate] challenger: lightgbm-v1-hobbled-shuffled-target KPI-09 7.6667 min  ·  KPI-10 48.303%
[gate] floor     : baseline-group-median        KPI-09 3.5090 min  ·  KPI-10 80.322%
[gate] required  : KPI-09 at least 2.00% below the floor
[gate] observed  : KPI-09 -118.49% vs the floor
[gate]   FAIL KPI-09 margin over the honest floor: 7.6667 vs 3.5090 min = -118.49% (required >= 2.00%)
[gate]   FAIL KPI-10 (within 5 min) does not regress: 48.303% vs 80.322% = -32.018 points
[gate] VERDICT   : REFUSE
[gate] Nothing was registered and no alias moved. A refused challenger leaves the registry exactly as it found it.
[gate] context   : the FLATTERING floor (baseline-constant-median) is 7.6667 min on test and is NOT the bar — against it this would read as +0.00%.
==============================================================================

[mlflow] lightgbm-v1-hobbled-shuffled-target: model logged with signature + input example
[mlflow] lightgbm-v1-hobbled-shuffled-target: run 5f8ed04b4b934918a348abd1e6a05937

[promote] SKIPPED — the gate refused. Nothing registered, no alias moved.

-- registry AFTER the red team --
registered_model=nyc-taxi-eta versions=[]
  alias @champion -> UNSET

[train-redteam] RED-TEAM PASSED: the gate REFUSED the hobbled challenger (exit 1),
[train-redteam] printing both numbers above, and the registry is byte-for-byte the
[train-redteam] state it was in before the run.
```

**Four things in that transcript are worth more than the verdict.**

1. **The hobbled model is not merely bad — it is the constant median.** Fitted to
   permuted labels, LightGBM's `l1` objective early-stopped at **iteration 1**
   and its test MAE is **7.6667**, equal to `baseline-constant-median` to four
   decimals. A model that has learned nothing converges on the one prediction
   that minimises absolute error when you know nothing: the median. The floor
   comparison is not an abstraction; it is what "learned nothing" numerically is.

2. **It was refused on both conditions, not one.** −118.49% on KPI-09 and −32.018
   points on KPI-10. A gate that only ever fails on its first condition has a
   second condition nobody has watched.

3. **The registry is identical across the refusal**, and the script checks that
   rather than asserting it: `versions=[] · alias @champion -> UNSET` before and
   after. The check reads the alias through `get_model_version_by_alias`, not off
   the version objects — `search_model_versions` returns them with `aliases`
   empty on server 3.15.1, so a snapshot built from that field would have been
   blind to exactly the mutation being checked for.

4. **The hobbled run is kept and marked, not deleted.** Tags `red_team=M2-S3`,
   `hobbled=shuffled-target`, `do_not_promote`, and the name says it too. The
   kickoff allowed cleanup *or* clear marking; marking is the better evidence,
   because a deleted refusal cannot be checked by anyone who was not watching it
   happen. It holds no alias and is not a registry version at all.

## 4. Transcript B — the gate PROMOTING v1

`make train`, exit **0**. Same command, same data, same evaluator, same gate —
only the challenger differs.

```
[data] train   43,987,422 rows  months=2019-01,2019-02,2019-03,2019-04,2019-05,2019-06
[data] val      6,189,748 rows  months=2019-07
[data] test     5,950,708 rows  months=2019-08

[model] fitting LightGBM v1
[500]   val's l1: 3.47604
Did not meet early stopping. Best iteration is:
[500]   val's l1: 3.47604
[model] best_iteration=500

  contender                    split       rows      KPI-09      KPI-10     RMSE   medAE   p90AE
  ---------------------------  -----  -----------  ----------  ----------  ------  ------  ------
  baseline-constant-median     val      6,189,748      7.8866     47.505%  12.201   5.283  17.850
  baseline-constant-median     test     5,950,708      7.6667     48.372%  11.844   5.183  17.133
  baseline-group-median        val      6,189,748      3.7170     78.693%   6.222   2.342   7.933
  baseline-group-median        test     5,950,708      3.5090     80.322%   5.811   2.292   7.317
  lightgbm-v1                  val      6,189,748      3.4760     79.693%   5.481   2.315   7.474
  lightgbm-v1                  test     5,950,708      3.2608     81.480%   5.047   2.263   6.862

[evaluate] lightgbm-v1 BEATS the honest floor on val: 3.4760 vs 3.7170 min (+6.48%)
[evaluate] val is the REPORT. The gate below judges on test, and only test.

==============================================================================
[gate] PROMOTION GATE — configs/train.yaml: gate (loosening it is a PO fork)
[gate] holdout   : test — 5,950,708 rows, untouched by training and by selection
[gate] challenger: lightgbm-v1                  KPI-09 3.2608 min  ·  KPI-10 81.480%
[gate] floor     : baseline-group-median        KPI-09 3.5090 min  ·  KPI-10 80.322%
[gate] required  : KPI-09 at least 2.00% below the floor
[gate] observed  : KPI-09 +7.07% vs the floor
[gate]   ok   KPI-09 margin over the honest floor: 3.2608 vs 3.5090 min = +7.07% (required >= 2.00%)
[gate]   ok   KPI-10 (within 5 min) does not regress: 81.480% vs 80.322% = +1.158 points
[gate] VERDICT   : PROMOTE
[gate] context   : the FLATTERING floor (baseline-constant-median) is 7.6667 min on test and is NOT the bar — against it this would read as +57.47%.
==============================================================================

[mlflow] lightgbm-v1: model logged with signature + input example
[mlflow] lightgbm-v1: run 3adee05a855a424bb664c7fea3735703

[promote] registered model: nyc-taxi-eta
[promote] version         : 1  (created)
[promote] run             : 3adee05a855a424bb664c7fea3735703
[promote] alias @champion   : unset -> 1
[promote] serving resolves models:/nyc-taxi-eta@champion -> version 1 (M5's deployment reads exactly this).
```

**Every number in that table reproduced M2-S2's to four decimals** on a separate
invocation a day's work later — `deterministic: true` and a fixed seed, doing
what they were configured to do. It is also the **fourth** independent
re-derivation of the group-median floor (M1-S3's SQL, M2-S2's evaluator, the red
team above, and this run), which is why 3.5090 can be treated as a fact about the
data rather than an output of one program.

`lightgbm-v1` again ran **500/500 rounds with val still improving** — the number
is a floor for LightGBM on these five features, not its ceiling. M3 is where that
is spent, and reading 3.2608 as "tuned" would misprice it.

## 5. Re-running the gate on the same champion is a no-op

Promotion is idempotent **by run**: `registry.promote` looks for a version
already minted from that run id and reuses it rather than minting a second, and
an alias already pointing at that version is left alone. This is M1-S5's law
applied to the registry — a converging path that creates a duplicate on every
invocation is not converging, it is accumulating.

Proven live against the champion the run above created, by calling the same
function with the same arguments (rather than spending twenty minutes retraining
a deterministic model to exercise one branch):

```
=== registry as the run left it ===
  version=1 run_id=3adee05a855a424bb664c7fea3735703 status=READY
  alias @champion -> version 1
  version tags:
    feature_set = v1
    gate_challenger_mae = 3.2608
    gate_floor = baseline-group-median
    gate_floor_mae = 3.5090
    gate_holdout_split = test
    gate_observed_pct = 7.07
    gate_required_pct = 2.00
    gate_verdict = PROMOTE
    metric_source = taxi_mlops.training.evaluate
  signature : inputs: ['hour': integer (required), 'dayofweek': integer (required),
              'PULocationID': integer (required), 'DOLocationID': integer (required),
              'passenger_count': float (required)] outputs: [Tensor('float64', (-1,))]
  input example present: True

=== re-running promotion on the SAME champion ===
[promote] version         : 1  (already registered for this run)
[promote] alias @champion   : already version 1 — NO-OP (re-running the gate on the same champion changes nothing)
  noop? True
  versions after: [1]
  alias after: 1

=== the red team's hobbled run: marked, and holding nothing ===
  tag red_team = 'M2-S3'
  tag hobbled = 'shuffled-target'
  tag do_not_promote = 'yes — fitted to permuted train labels on purpose'
  tag gate_verdict = 'REFUSE'
  is it a registry version? False
  its gate_passed metric: 0.0
```

**The verdict travels with the version, not only with the transcript.** Those
tags mean the question "what was this champion measured against, and by how
much?" is answered by the registry itself — no one has to find the session that
promoted it. The same numbers are on the run as metrics (`gate_passed`,
`gate_observed_pct`, …), which is what makes the hobbled run legible as a
refusal a month from now.

## 6. Limits, stated because they are real

- **The margin is measured against a floor fitted on the same training data.**
  Observed while smoke-testing this story on one train month: the group-median
  floor *itself* degraded (4.1138 vs 3.5090 min on test, because the lookup table
  is built from a sixth of the rows), so the model's margin over it *rose* to
  16.85% while the model was actually **worse** (3.4207 vs 3.2608). **A sampled
  run makes this gate easier to pass, not harder.** M3's scout and sniper train
  on samples by design; a gate verdict from a sampled run is not comparable to
  one from a full run, and M3 must either gate only full-data contenders or
  record the sample beside the verdict. **Raised as F-008 (`ledgers/findings.md`,
  landing M3)** rather than left here — a limit recorded only in prose is one the
  next session does not run into.
- **The gate judges two numbers on one month.** It cannot see the segments M2-S4's
  error memo is for: a model can clear 2% overall while being far worse than the
  floor in a specific zone or hour. Segment-level conditions are not in this gate
  and should not be smuggled in without the memo's evidence.
- **`deterministic: true` and a fixed seed make a re-run reproduce**, so a verdict
  near the margin does not flip on noise. It has not been tested against a
  LightGBM version change, and would not survive one silently.
