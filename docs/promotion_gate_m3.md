# The promotion gate, hardened — M3-S1 (role:MLE, 2026-08-17)

`docs/promotion_gate_m2.md` is the gate's founding argument and stays true as a
record of what M2 decided. This document is what M3-S1 changed and why, and it
supersedes M2's §2 on one point only: **the floor, and therefore the headroom.**

Four findings land here, each closed by its own evidence and none by prose:

| Finding | What was wrong | Where it is closed below |
|---|---|---|
| **F-010** | The gate's "headroom, deliberately" (+7.07%) was mostly the floor's fallback being bad | §1 — the floor got stronger, measured |
| **F-011** | A challenger worse than the model that is SERVING could take the alias | §3 — the watched refusal |
| **F-012** | `make predictions` checked the challenger half of the gate's argument and not the floor half | §4 — the refused write |
| **F-008** | A sampled training run makes the gate EASIER to pass | §5 — the refused verdict |
| **F-013** (gate half) | A second, contradictory gate lived in `configs/promotion.yaml` | §6 — deleted, pinned by a test |

Every number below came from `taxi_mlops.training.evaluate` and nowhere else
(gotcha #15). Nothing in this story promoted anything: `@champion` is version 1
before and after, and the registry snapshots are in §3.

- Code: `gate.py` (decides, pure) · `registry.py` (acts, the only mutator) ·
  `run.py` (`_resolve_incumbent` — the registry read that feeds the gate) ·
  `score.py` (the published floor's check) · `baselines.py` (the new floor)
- Knobs: `configs/train.yaml: gate` and `: baselines`. **Loosening any of them is
  a PO fork, not an edit** (CLAUDE.md). Everything below is a tightening.
- Commands: `make train` · `make train-redteam` · **`make gate-redteam`** (new,
  F-011) · **`make predictions-redteam`** (new, F-012)

---

## 1. The floor got stronger, and the headroom got honest (F-010)

The M2 floor answers a trip whose `(hour, dayofweek, PU, DO)` cell train never
saw with the **global median — 11.15 minutes for everyone**, Midtown-to-Midtown
and JFK-to-Brooklyn alike. 1.479% of test rows land there, and M2-S4's error
memo measured what that is worth: **75.4% of the champion's entire advantage over
the floor is bought on those 1.48% of rows.**

`baseline-group-median-od-fallback` gives the same lookup one more backoff level
— `(hour, dow, PU, DO)` → `(PU, DO)` → global. It is a NEW name and not an edit,
because M2's verdicts were argued against the old floor and must stay
reproducible (`configs/train.yaml: baselines` legislated exactly this in M2).
It is still a `GROUP BY`: no new column, no new model, the same 43,987,422 train
rows.

Measured in one run, all four contenders through one evaluator:

| contender | val KPI-09 | val KPI-10 | test KPI-09 | test KPI-10 |
|---|---|---|---|---|
| `baseline-constant-median` (the flattering floor) | 7.8866 | 47.505% | 7.6667 | 48.372% |
| `baseline-group-median` (M2's floor) | 3.7170 | 78.693% | 3.5090 | 80.322% |
| **`baseline-group-median-od-fallback`** (the gate's floor now) | **3.5515** | **79.111%** | **3.3518** | **80.733%** |
| `lightgbm-v1` (champion v1, re-fitted) | 3.4760 | 79.693% | 3.2608 | 81.480% |

The lookup gained **46,938 backoff cells** beside its 1,610,050 full-key groups.

**The consequence, which is the finding:** v1's margin over the bar falls from
**+7.07% to +2.71%**. F-010's independent re-derivation from the published
prediction rows predicted 3.3518 and +2.71%; this run measured 3.3518 and +2.71%
by fitting the thing rather than by reasoning about it. Two instruments, same
number — which is what says the floor is what the finding said it was.

**The gate decision (DR-06 §3, action AI-4): adopt it.** The reasoning lives in
`configs/train.yaml: gate` beside the value, where a loosening would be a visible
diff. In one line: the gate exists to ask *what does this booster buy over the
best simple predictor*, and until now it asked what the booster bought over the
first one. The **2.00% bar is unchanged and that is a conclusion, not an
omission** — it is a maintenance-cost bar, 2% of 3.3518 is ~4.0 seconds of mean
error, and the cost of owning a booster did not change when the floor improved.
What changed is the headroom: **1.35×, not 3.5×**.

**+7.07% may not be quoted as headroom anywhere in M3** (DR-06 §2). It is not a
wrong number — it is what version 1 was promoted at, it is tagged on the version,
and `verify-m2` replays it — but it describes a comparison against a floor the
program has since improved on.

Honest cost of this choice, stated because it is real: M3's bake-off now has to
beat **3.3518** by 2%, i.e. land at **≤ 3.2848** on the test month. The artisan
and automation tracks inherit a bar 0.157 minutes harder than the one M2 set,
and a contender that would have looked like a 5% win against the old floor may
be refused. That is the point of the change and it is the expensive option.

## 2. The gate, as it now reads (the transcript `make train` prints)

`python -m taxi_mlops.training train --no-promote --experiment m3-gate --story M3-S1`
— full data, promotion deliberately withheld (S5 owns the alias; this story
moves nothing).

```
[features] set v1: hour, dayofweek, PULocationID, DOLocationID, passenger_count
[features] categorical: PULocationID, DOLocationID, dayofweek
[features] refused by the registry: 18 column(s) — taxi_mlops.features.quote_time.EXCLUSIONS names each with its reason
[data] train   43,987,422 rows  months=2019-01,2019-02,2019-03,2019-04,2019-05,2019-06
[data] val      6,189,748 rows  months=2019-07
[data] test     5,950,708 rows  months=2019-08

[baseline] constant median = 11.1500 min (train)
[baseline] group median over (hour, dayofweek, PULocationID, DOLocationID): 1,610,050 groups, fallback 11.1500 min
[baseline] group median with (PULocationID, DOLocationID) backoff: 1,610,050 groups + 46,938 backoff cells, fallback 11.1500 min

[model] fitting LightGBM v1
Training until validation scores don't improve for 30 rounds
[50]	val's l1: 3.96899
[100]	val's l1: 3.63497
[150]	val's l1: 3.5475
[200]	val's l1: 3.51318
[250]	val's l1: 3.49954
[300]	val's l1: 3.49124
[350]	val's l1: 3.48572
[400]	val's l1: 3.48175
[450]	val's l1: 3.47872
[500]	val's l1: 3.47604
Did not meet early stopping. Best iteration is:
[500]	val's l1: 3.47604
[model] best_iteration=500

[evaluate] every number below came from taxi_mlops.training.evaluate
[evaluate] (gotcha #15: nothing else in this program may report one)

  KPI-09 = mean |predicted - actual|, minutes (lower is better)
  KPI-10 = % of trips within 5 minutes (higher is better)

  contender                          split       rows      KPI-09      KPI-10     RMSE   medAE   p90AE
  ---------------------------------  -----  -----------  ----------  ----------  ------  ------  ------
  baseline-constant-median           val      6,189,748      7.8866     47.505%  12.201   5.283  17.850
  baseline-constant-median           test     5,950,708      7.6667     48.372%  11.844   5.183  17.133
  baseline-group-median              val      6,189,748      3.7170     78.693%   6.222   2.342   7.933
  baseline-group-median              test     5,950,708      3.5090     80.322%   5.811   2.292   7.317
  baseline-group-median-od-fallback  val      6,189,748      3.5515     79.111%   5.644   2.333   7.700
  baseline-group-median-od-fallback  test     5,950,708      3.3518     80.733%   5.245   2.283   7.117
  lightgbm-v1                        val      6,189,748      3.4760     79.693%   5.481   2.315   7.474
  lightgbm-v1                        test     5,950,708      3.2608     81.480%   5.047   2.263   6.862

[evaluate] lightgbm-v1 BEATS the honest floor on val: 3.4760 vs 3.5515 min (+2.12%)
[evaluate] val is the REPORT. The gate below judges on test, and only test.

==============================================================================
[gate] PROMOTION GATE — configs/train.yaml: gate (loosening it is a PO fork)
[gate] holdout   : test — 5,950,708 rows, untouched by training and by selection
[gate] challenger: lightgbm-v1                  KPI-09 3.2608 min  ·  KPI-10 81.480%
[gate] floor     : baseline-group-median-od-fallback KPI-09 3.3518 min  ·  KPI-10 80.733%
[gate] incumbent : version 1                    KPI-09 3.2608 min  ·  KPI-10 81.480%   [version tags + run 3adee05a855a…]
[gate] required  : KPI-09 at least 2.00% below the floor
[gate] observed  : KPI-09 +2.71% vs the floor
[gate]   ok   KPI-09 margin over the honest floor: 3.2608 vs 3.3518 min = +2.71% (required >= 2.00%)
[gate]   ok   KPI-10 (within 5 min) does not regress: 81.480% vs 80.733% = +0.746 points
[gate]   ok   KPI-09 does not regress against the serving champion (v1): 3.2608 vs 3.2608 min (-0.00% vs incumbent)
[gate]   ok   KPI-10 does not regress against the serving champion (v1): 81.480% vs 81.480% = +0.000 points
[gate] VERDICT   : PROMOTE
[gate] context   : the FLATTERING floor (baseline-constant-median) is 7.6667 min on test and is NOT the bar — against it this would read as +57.47%.
```

Note the incumbent line, which is new, and the verdict: re-gating the champion
against **itself** must be a PASS, or every promotion would be a one-way door and
`make train` would stop being idempotent.

**What this run cost to get right, recorded because a unit test could not have
found it.** The first full run of the hardened gate **refused the champion
against its own registry tag**: `registry.promote` records KPI-09 at four
decimals (`3.2608`), a deterministic re-fit measures `3.260823…`, and
`3.260823 <= 3.2608` is False. The comparison was being made at a precision the
incumbent's numbers do not exist at. `gate.INCUMBENT_MAE_DECIMALS` /
`INCUMBENT_WITHIN_DECIMALS` now round the challenger to the resolution the
registry recorded, a test pins them as twins of the format strings in
`run._promote`, and a regression of one ten-thousandth of a minute is still
refused. Nothing about this is visible on a synthetic `Metrics` object, which is
why the story ran the real thing.

## 3. The incumbent condition, and a watched refusal (F-011)

The floor answers *is a booster worth serving at all*. Only the model that is
serving answers *is this one better than what riders already get*. Before M3-S1
`gate.decide` read exactly two `Metrics` and the registry was never consulted, so
a challenger materially worse than version 1 could clear the floor bar and take
the alias — F-011's own arithmetic put it at roughly **58,000 more test-month
riders quoted wrongly** than under the model it replaced.

Two halves, because either alone can be walked around:

1. **`gate.decide` gains an incumbent condition** on KPI-09 **and** KPI-10, fed
   from the resolved `@champion` version's own tags. It is optional in the
   signature — the first promotion has no incumbent, and M2's recorded verdicts
   replay without one — and it has **no config knob**, ever: a switch that can
   break an invariant is a trapdoor, not a knob.
2. **`registry.promote` refuses to move an alias whose current version the
   decision did not read.** `incumbent_version` is a required argument with no
   default, the live alias is re-read at promotion time, and a mismatch raises.
   This is what stops "optional" from meaning "skippable", and it closes the race
   where two runs both gated against version 1 and both moved the alias.

`make gate-redteam` watches both. The challenger is **built, not fitted**: the
champion's own booster with a fixed **+0.06 min (3.6 s)** bias on every quote.
M2-S3's permuted-label hobble scores 7.6667 and is refused by a mile, which
proves nothing about this condition; F-011 lives in a window ~0.02 minutes wide
and no hobbled *fit* lands there on purpose. The constant was chosen by querying
`data/predictions/test` for the MAE of `predicted + δ` at several δ — that query
chose a constant and reported nothing; every number in the transcript is computed
by the evaluator on the spot, and the drill FAILS if the constructed challenger
does not really clear the floor bar.

```
[registry] before: @champion -> version 1, versions [1]

[data] train   43,987,422 rows  months=2019-01,2019-02,2019-03,2019-04,2019-05,2019-06
[baseline] baseline-group-median-od-fallback: 1,610,050 groups
[data] test     5,950,708 rows  months=2019-08

[evaluate] every number below came from taxi_mlops.training.evaluate

  KPI-09 = mean |predicted - actual|, minutes (lower is better)
  KPI-10 = % of trips within 5 minutes (higher is better)

  contender                          split       rows      KPI-09      KPI-10     RMSE   medAE   p90AE
  ---------------------------------  -----  -----------  ----------  ----------  ------  ------  ------
  champion-v1-as-served              test     5,950,708      3.2608     81.480%   5.047   2.263   6.862
  champion-v1-plus-0.06min           test     5,950,708      3.2667     81.423%   5.044   2.277   6.860
  baseline-group-median-od-fallback  test     5,950,708      3.3518     80.733%   5.245   2.283   7.117

  ok   the registry names an incumbent to defend (version 1)
  ok   PREMISE: the floor conditions ADMIT this challenger (+2.54% vs baseline-group-median-od-fallback)
  ok   PREMISE: the challenger is worse than what is serving (3.2667 vs 3.2608 min)

==============================================================================
[gate] THE SAME GATE, with the incumbent condition live
[gate] holdout   : test — 5,950,708 rows, untouched by training and by selection
[gate] challenger: champion-v1-plus-0.06min     KPI-09 3.2667 min  ·  KPI-10 81.423%
[gate] floor     : baseline-group-median-od-fallback KPI-09 3.3518 min  ·  KPI-10 80.733%
[gate] incumbent : version 1                    KPI-09 3.2608 min  ·  KPI-10 81.480%   [version tags + run 3adee05a855a…]
[gate] required  : KPI-09 at least 2.00% below the floor
[gate] observed  : KPI-09 +2.54% vs the floor
[gate]   ok   KPI-09 margin over the honest floor: 3.2667 vs 3.3518 min = +2.54% (required >= 2.00%)
[gate]   ok   KPI-10 (within 5 min) does not regress: 81.423% vs 80.733% = +0.689 points
[gate]   FAIL KPI-09 does not regress against the serving champion (v1): 3.2667 vs 3.2608 min (-0.18% vs incumbent)
[gate]   FAIL KPI-10 does not regress against the serving champion (v1): 81.423% vs 81.480% = -0.057 points
[gate] VERDICT   : REFUSE
[gate] Nothing was registered and no alias moved. A refused challenger leaves the registry exactly as it found it.
==============================================================================

  ok   the gate REFUSED the challenger (VERDICT REFUSE; the CLI exits 1)
  ok   every failed condition is an INCUMBENT condition: ['KPI-09 does not regress against the serving champion (v1)', 'KPI-10 does not regress against the serving champion (v1)']
  ok   KPI-09 against the incumbent is in the transcript with both models' numbers
  ok   the floor conditions still PASSED — this refusal is the new condition's

  ok   registry.promote REFUSED the bypass: @champion points at version 1 and this promotion was decided against incumbent NOTHING (…

  ok   the registry is IDENTICAL after the drill: {'alias': '1', 'versions': [1]}

[red team] GREEN — the gate refused a challenger the floor admitted, named
           the incumbent, and moved nothing. F-011 cannot happen silently.
```

## 4. The floor half of the published comparison (F-012)

`make predictions` re-fits the honest floor and writes `floor_predicted_minutes`
on all 12,140,456 published rows. `marts.error_segments.kpi_13_margin_vs_floor_pct`,
the error memo's whole §1 decomposition and every card on the error-segment board
are comparisons against that column — and until M3-S1 only the *challenger* half
was tied back to the registry. Re-fit the floor over a different window and every
one of those numbers moves while the champion still re-scores at 3.2608 and
`verify-m2` stays GREEN 49/49.

Two changes, and the first is the one that will matter at S5:

- **The floor is the one the CHAMPION's verdict was argued against**, read off
  the version's `gate_floor` tag — not whatever `configs/train.yaml` names today.
  After §1 those legitimately differ: version 1 was gated against
  `baseline-group-median`, and the next promotion will face
  `baseline-group-median-od-fallback`. Publishing rows that compare v1 against a
  bar it never faced would make every KPI-13 a comparison nobody made.
- **Its re-scored MAE is checked against `gate_floor_mae` as a refusal to
  write**, on exactly the same terms as the challenger's — not a printed note.

```
before  da7ed369e808f12e3485094594ea0fbedc043fe58eceda8c356479cf656e717b  predictions.json
  before  d4ddf2a6d2f36f1749c3a4d295772950ddd74bf0ed9f5f08c550bd6fe43a49e4  test/predictions_2019-08.parquet
  before  343258756bb1289f88d5163370a39ad4f5288b635679e3a50648ca45c697869a  val/predictions_2019-07.parquet

[red team] fitting the published floor on 2019-01 alone (the champion's gate used six months)

[openmp] no system libgomp.so.1; linked libgomp-e985bcbb.so.1.0.0 -> /home/longt/NYC-taxi-production-with-k8-flavor/.venv/lib/openmp/libgomp.so.1 and re-executing once with LD_LIBRARY_PATH set (see taxi_mlops.training.openmp)
[openmp] openmp: system libgomp.so.1


[score] alias models:/nyc-taxi-eta@champion resolves to models:/m-4a4e7bdcd17a43b29aa9bd103073bb2c (F-009: load it, not the alias)

[score] champion   : models:/nyc-taxi-eta@champion -> version 1
[score] run        : 3adee05a855a424bb664c7fea3735703  (500 trees)
[score] features   : hour, dayofweek, PULocationID, DOLocationID, passenger_count (matches the config)
[data] train    7,584,656 rows  months=2019-01
[score] RED TEAM: the floor is being fitted on an overridden month set. The check below is expected to REFUSE the write.
[baseline] baseline-group-median over (hour, dayofweek, PULocationID, DOLocationID): 789,894 groups, fallback 10.2667 min
[data] val      6,189,748 rows  months=2019-07
[data] test     5,950,708 rows  months=2019-08

[evaluate] every number below came from taxi_mlops.training.evaluate

  KPI-09 = mean |predicted - actual|, minutes (lower is better)
  KPI-10 = % of trips within 5 minutes (higher is better)

  contender                    split       rows      KPI-09      KPI-10     RMSE   medAE   p90AE
  ---------------------------  -----  -----------  ----------  ----------  ------  ------  ------
  nyc-taxi-eta@champion        val      6,189,748      3.4760     79.693%   5.481   2.315   7.474
  baseline-group-median        val      6,189,748      4.3912     74.543%   7.563   2.517   9.892
  nyc-taxi-eta@champion        test     5,950,708      3.2608     81.480%   5.047   2.263   6.862
  baseline-group-median        test     5,950,708      4.1138     76.735%   7.113   2.417   8.967
[score] registry says version 1 was promoted at KPI-09 3.2608 on test; scoring it now measures 3.2608
[score] MATCH — the published rows describe the model the gate promoted.
[score] registry says version 1 was gated against floor 'baseline-group-median' at KPI-09 3.5090 on test; re-fitting that floor now measures 4.1138
[score] FAIL: the floor re-fits to 4.1138 on test, but the champion's own registry tag says it was gated against 3.5090. The rows this command would publish would compare the champion against a DIFFERENT bar from the one it passed — every KPI-13 in the mart, the memo and the board would move and nothing else would notice. Refusing to write them. (If the training window really has moved, the champion needs re-gating, not the predictions re-publishing.)

[red team] the command exited 2

  after   da7ed369e808f12e3485094594ea0fbedc043fe58eceda8c356479cf656e717b  predictions.json
  after   d4ddf2a6d2f36f1749c3a4d295772950ddd74bf0ed9f5f08c550bd6fe43a49e4  test/predictions_2019-08.parquet
  after   343258756bb1289f88d5163370a39ad4f5288b635679e3a50648ca45c697869a  val/predictions_2019-07.parquet

  ok   the write was REFUSED (exit 2), not warned about
  ok   every published file is byte-identical (sha256) — nothing was rewritten

[red team] GREEN — a floor fitted on the wrong window cannot reach the warehouse.
```

## 5. A sampled run gets no verdict (F-008)

The bar is re-derived from the challenger's own training data — deliberately, so
it cannot drift from a document. So a sample degrades the **floor** as well as
the model, and the floor faster: its lookup loses whole cells and falls back more
often while a booster keeps generalising. Measured at M2-S3 on one month of six:
floor 3.5090 → 4.1138, model 3.2608 → **3.4207**, margin 7.07% → **16.85%**. The
model got worse and the transcript got better.

`gate.assert_full_train_months` now refuses to issue a verdict for such a run,
**before a row is read**, so the refusal costs seconds instead of a training run.
`--no-gate` is the sample-first smoke path: it is legal ONLY with
`--train-months`, so it can never skip a gate a promotable run would have faced,
it can promote nothing, its MLflow runs are tagged `sample_run` /
`do_not_promote` / `gate_verdict: NONE`, and it exits **3** — its own code,
because "the gate did not judge this" and "the gate judged this and was
satisfied" are the two things a pipeline must never confuse.

```
$ make train --train-months 2019-01          # i.e. without --no-gate
[openmp] openmp: system libgomp.so.1
[run] SAMPLE RUN — train months overridden: 2019-01

[gate] NO VERDICT: the gate issues no verdict for a SAMPLED run (F-008). This run trained on 2019-01 and configs/train.yaml: data.train_months is 2019-01, 2019-02, 2019-03, 2019-04, 2019-05, 2019-06. Sampling degrades the FLOOR faster than the model (measured: margin 7.07% -> 16.85% on one month of six), so a sampled verdict reads better than the full-data one it is standing in for. Use --no-gate for a sample-first smoke run: it prints the table, issues no verdict, and can promote nothing.
$ echo $?
2

$ python -m taxi_mlops.training train --no-gate      # without a sample
[gate] NO VERDICT: --no-gate is only legal for a SAMPLED run (--train-months). On the configured months the gate is the point of the command: a full-data fit that skipped its verdict is a result with no bar attached.
$ echo $?
2
```

This session's `--no-gate` smoke run on 2019-01 also re-measured F-008's numbers
from scratch: floor **4.1138**, model **3.4207** on test — M2-S3's figures to
four decimals, from a different session and a changed code path.

## 6. The gate has one home (F-013, gate half)

`configs/promotion.yaml` carried `gate_ratio: 0.85` — a bar agreeing with nothing
in the program, written before the first training run, and the first thing a
session grepping `configs/` for "promotion" would find. Deleted. A test now fails
if any file under `configs/` other than `train.yaml` names a gate knob, checking
the **knobs rather than the filename**, because the next stub will have a
different name. `docs/BLUEPRINT.md`'s pointer was corrected in the same PR, since
a spec naming a deleted file is the same defect one level up.

The features half of F-013 (`configs/features.yaml`) is **M3-S3's** and untouched
here.

## 7. Limits, stated

- **The incumbent comparison assumes both models were scored on the same holdout
  month.** The version carries `gate_holdout_split` and the gate refuses a
  cross-split comparison, but the holdout *month* is a config value, not a tag,
  on versions promoted before M3-S1. If `data.test_month` ever moves, every
  incumbent comparison against an older version silently changes meaning.
  Versions promoted from now on carry more of their own context
  (`gate_challenger_within_rate`, `gate_floor_within_rate`,
  `gate_incumbent_version`); the month itself is still not among them.
- **Champion v1's KPI-10 is read off its RUN, not its version.** Versions
  promoted before M3-S1 were tagged with KPI-09 only. Backfilling the tag would
  be a registry write from outside `registry.py`, which is the one rule this
  story would not break to make a transcript tidier — so the number is read where
  it already exists and `_resolve_incumbent` prints its provenance.
- **The gate still knows nothing about serving cost.** A challenger with 5,000
  trees that beats the incumbent by 0.3% passes, and M5's latency SLO is where
  that gets caught. Named here rather than filed, because M5 owns the number.
