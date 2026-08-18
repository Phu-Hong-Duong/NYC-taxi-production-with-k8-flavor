# The M3 bake-off — five contenders, one evaluator, one untouched month

**Story:** M3-S5 (role:MLE) · **Command:** `make bakeoff` ·
**Rows:** `automation/runs/m3s5/bakeoff.json` · **Status:** §3–§6 land with the
detached run named in HANDOFF.

## 0. What this document is, and what it is not

M3 asked one question and built a 2×2 to answer it: **did the improvement come
from FEATURES, from TUNING, or from both?** Four cells of that square were
measured on the VALIDATION month by M2-S2, M3-S3 and M3-S4. **None of them has
faced the gate.** This is where the fifth row — the gate's own floor — joins
them and where all five are read on the TEST month, once.

Every number in §3 onward comes from `taxi_mlops.training.evaluate` (gotcha #15).
No val number anywhere in this program is a prediction of a test number, and none
of the val numbers restated in §1 is a verdict.

## 1. The five contenders, declared before they were measured

Pre-registration is the same discipline DR-02 imposed on M3-S3's feature groups,
applied one level up: which cells exist, and what each is a measurement *of*, are
fixed in `scripts/bakeoff_m3.py: CONTENDERS` and pinned by a test. A losing arm
cannot become a different arm at write-up time.

| contender | track | features | hyperparameters | val MAE (NOT a verdict) | val KPI-10 |
|---|---|---|---|---:|---:|
| floor — `baseline-group-median-od-fallback` | floor | (a two-level `GROUP BY`) | none | 3.5515 | — |
| champion v1 — `lightgbm-v1` | artisan | v1 (5) | hand, `configs/train.yaml: model` | 3.4760 | 79.693% |
| artisan v2 — `artisan-v2` | artisan | v2 (24) | hand — v1's, held fixed (DR-03) | 3.3905 | 80.506% |
| auto-on-v1 — `auto-xgboost-v1` | automation | v1 (5) | tuned (FLAML scout → Optuna sniper) | 3.7245 | 78.003% |
| auto-on-v2 — `auto-lgbm-v2` | automation | v2 (24) | tuned (FLAML scout → Optuna sniper) | 3.3823 | 80.552% |

**The axes are disjoint, and that is what makes the square answer anything**
(DR-03): the artisan track searched FEATURES holding v1's hyperparameters, the
automation track searched HYPERPARAMETERS on feature sets it did not invent. If
both tracks had moved both axes, no delta in the square would isolate a cause.

**One row carries a caveat and one row deliberately does not.** `auto-on-v1` hit
its 800-round cap **mid-descent** — val still falling 0.02808 MAE over its last
100 rounds — from a study that got **9 trials of a configured 60** and was
stopped by the clock, not by convergence (**F-015**). `auto-on-v2` hit the same
cap **flat**: 0.00034 MAE over its last 100 rounds, ~82× less slope. A cap is a
truncation only if the curve is still moving under it, so F-015 attaches to the
first row and to no other. The caveats travel *in the row* rather than in a
footnote, and a test fails if that stops being true.

## 2. Method — what was fitted here, and what deliberately was not

**Nothing is re-fitted.** All four model contenders are LOADED from the MLflow
artifacts their val numbers describe. `scripts/automl_refit.py` says why in its
own docstring: it logged each model with signature and input example "so M3-S5
can hand it to the gate without re-fitting anything". A re-fit would be a
different MLflow run, and **the version this bake-off promotes must be the
version this bake-off measured**.

**The floor is the one thing fitted here, and it must be.** `gate.py`'s second
property requires the bar re-derived from the challenger's own training data in
the same invocation — a floor quoted from a document drifts away from the data
silently, and a floor recomputed every run cannot.

**No contender is identified by a run id typed into a file.** The champion comes
from the ALIAS (so the bake-off judges what is actually serving), the two
automation arms from the JSON their own track wrote, and the artisan arm from a
search that refuses to proceed unless it matches exactly one full-scale run. A
hardcoded id would be correct today and a silent lie the first time an experiment
is re-run.

**The admission check is the strongest thing here.** Before any test number is
put on a contender, each loaded artifact must re-measure the val MAE its own
MLflow run records, to float64. If it does not, then either the artifact loaded
is not the artifact that was measured, or this file builds features differently
from the path that fitted it — and **neither defect has any other symptom**. It
is `score.py`'s `_check_against_registry` discipline (M2-S4) applied to four
contenders instead of one, and it is what makes §3 evidence rather than output.

**Five verdicts, the floor's against itself included.** The floor as its own
challenger is an expected REFUSE at exactly +0.00%. Printing it is the cheapest
possible demonstration that the bar is a bar: a gate only ever shown passing is a
gate nobody has watched work.

## 3. The results table (test month, 2019-08)

*Pending — filled from the detached run's transcript.*

## 4. The five gate verdicts

*Pending.*

The bar is quoted from `configs/train.yaml: gate` and never from the minutes
(DR-06): KPI-09 at least **2.00%** below `baseline-group-median-od-fallback`,
KPI-10 must not regress against the floor, and both must not regress against the
**incumbent** — version 1 at **3.2608 min / 81.480%** (F-011, and it has no
knob). The floor measured **3.3518** on test at M3-S1, so the bar a challenger
must clear is **≤ 3.2848** — and the incumbent condition makes the operative
number **≤ 3.2608**, which is tighter.

## 5. The 2×2 arithmetic — features, tuning, or both?

*Pending.*

Read against `champion v1`, because that is the cell both tracks started from.
Any other reference makes the two deltas incomparable.

## 6. The alias decision

*Pending.*

Whatever it is, it is taken by the S1-hardened gate unchanged, with the incumbent
condition live, and `registry.promote` refuses to move an alias whose current
version the decision did not read. If the alias moves, `configs/train.yaml:
features.version` moves in the same change — `scripts/bakeoff_m3.py` refuses to
promote a winner that line does not describe, because `score.py` and `verify-m2`
both check the champion against it.

## 7. What each track cost, measured, and why the seconds do not settle it

| track | fitting wall-clock | stopped because |
|---|---:|---|
| artisan (M3-S3) | **3,313.9 s** | its own keep rule — a result |
| automation (M3-S4) | **9,133.8 s** | the DR-01 clock expired **mid-search**, on both studies |

**2.76×**, and the automation track went **1.49% over its declared 9,000 s
share** (per-phase and mechanical: FLAML's `time_budget_s` bounds its search loop
and not the retrain after it; Optuna checks its cap *between* trials, so the
trial in flight overruns). Reported at the size it happened, per DR-01 condition
2, and never re-run.

**The two tracks stopped for different KINDS of reason, and that is the part
normalising seconds cannot fix.** One stopped because it had learned what it set
out to learn; the other stopped because a clock ran out while it was still
searching. A "seconds per point of MAE" figure would put those side by side as if
they were the same currency.
