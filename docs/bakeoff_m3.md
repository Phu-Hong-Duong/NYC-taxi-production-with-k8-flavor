# The M3 bake-off — five contenders, one evaluator, one untouched month

**Story:** M3-S5 (role:MLE) · **Command:** `make bakeoff` ·
**Rows:** `automation/runs/m3s5/bakeoff.json` · **Status:** MEASURED 2026-08-18
(`automation/runs/m3s5-bakeoff.log`, 493 s) — §3–§6 carry the numbers; the alias
transition they authorise is `make champion-transition`.

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

Measured 2026-08-18 by `make bakeoff`, detached, **493 s wall-clock end to end**
(03:24:40 → 03:32:53 Z; `automation/runs/m3s5-bakeoff.log`). **5,950,708 test
rows**, untouched by training and by selection. The floor was fitted on the six
train months (**43,987,422 rows**, 1,610,050 groups + 46,938 backoff cells); the
four models were LOADED.

> **CORRECTION — 2026-08-18 (M4-S1, finding F-018, filed by REV at the M3
> review).** The five words "**and by selection**" in the paragraph above are
> **FALSE of the run this document reports**, and they are left standing rather
> than edited so that what was claimed and what was true can both be read. When
> this bake-off ran, `scripts/bakeoff_m3.py` chose its winner with
> `min(contenders, key=… metrics["test"].mae)` — the five arms were ranked on
> the very month the sentence calls selection-free, and `gate.verdict_lines`
> then printed the same claim on all five verdicts. The holdout was untouched by
> **training**; it was not untouched by **selection**.
>
> **What this costs the result, honestly.** A max-of-five taken on the holdout
> biases the winner's margin over the floor (+3.33%) upward by an amount nobody
> measured. And the choice was not academic: the two v2 arms finished **0.0022
> min apart** (§3, below), so which of them serves was settled on the test
> month. **What it does not cost**: the identity of the champion. §3's own
> paragraph — "the val ranking and the test ranking are the same ranking" —
> reports that auto-on-v2 leads on val as well (3.3823 vs 3.3905), so selecting
> on val would have chosen the same model. That is why `automation/runs/m3s5/
> bakeoff.json` and every number in this document **stand as measured and were
> not re-run**: re-running would spend hours re-litigating verdicts that do not
> change, and silently rewriting them would destroy the record of a real defect.
>
> **What was repaired instead (M4-S1, before M7's retrain loop inherits the
> shape):** the script now ranks on **val**, inside the val pass, before the
> holdout split is loaded — so there is no holdout number in existence to rank
> on — and it records `winner_selected_on` in its JSON. `gate.verdict_lines`
> no longer asserts selection-purity on its own authority: the claim is a
> caller-supplied argument that defaults to the weaker, always-true sentence,
> and a bake-off does not pass it (`gate.py` property 7). Ledger:
> `ledgers/findings.md` F-018.

| contender | family | trees | test KPI-09 (min) | test KPI-10 | vs floor | vs champion v1 |
|---|---|---:|---:|---:|---:|---:|
| **auto-on-v2** — `auto-lgbm-v2` | lgbm | 791 | **3.2403** | 81.577% | **+3.33%** | **+0.63%** |
| artisan v2 — `artisan-v2` | lgbm | 500 | 3.2425 | **81.582%** | +3.26% | +0.56% |
| champion v1 — `lightgbm-v1` | lgbm | 500 | 3.2608 | 81.480% | +2.71% | — |
| floor — `baseline-group-median-od-fallback` | group-by | — | 3.3518 | 80.733% | +0.00% | −2.79% |
| auto-on-v1 — `auto-xgboost-v1` | xgboost | 800 | 3.5038 | 79.747% | −4.54% | −7.45% |

**Every one of the four models re-measured its own recorded val MAE to float64
before it was allowed a test number** — `3.47603843547682` · `3.3905388307148137`
· `3.724473218110082` · `3.3822796832477016`, each equal to the value its own
MLflow run recorded at fitting time, in three cases from a different script on a
different day. That is what makes this table evidence: the artifact that was
loaded is provably the artifact that was measured, and this file builds features
the same way the paths that fitted them did.

**The val ranking and the test ranking are the same ranking.** auto-on-v2 <
artisan v2 < champion v1 < auto-on-v1 on val (3.3823 · 3.3905 · 3.4760 · 3.7245)
and in exactly that order on test. Selection pressure on val did not reorder
anything on the untouched month — worth recording precisely because it is the
failure this program was structured to catch, and it did not occur.

**The two v2 arms split the two KPIs.** auto-on-v2 wins KPI-09 by **0.0022 min —
134 milliseconds** of mean error, 0.069% relative — while artisan v2 is ahead on
KPI-10 by **0.005 points**. The ranking rule is KPI-09, declared in
`scripts/bakeoff_m3.py` before any number existed, so the winner is auto-on-v2.
It is a win, and it is a win of that size; §5 refuses to inflate it. *(2026-08-18
correction, F-018: the ranking METRIC was pre-registered, the ranking SPLIT was
the holdout — see the note in §3. On val the same two arms sit in the same order,
3.3823 vs 3.3905, so the winner is unchanged; since M4-S1 the script ranks
there.)*

## 4. The five gate verdicts

| contender | KPI-09 vs floor | KPI-10 vs floor | KPI-09 vs incumbent | KPI-10 vs incumbent | verdict |
|---|---|---|---|---|---|
| floor | ✗ +0.00% | ✓ −0.000 | ✗ −2.79% | ✗ −0.746 | **REFUSE** |
| champion v1 | ✓ +2.71% | ✓ +0.746 | ✓ −0.00% | ✓ +0.000 | PROMOTE |
| artisan v2 | ✓ +3.26% | ✓ +0.849 | ✓ +0.56% | ✓ +0.103 | PROMOTE |
| auto-on-v1 | ✗ −4.54% | ✗ −0.987 | ✗ −7.45% | ✗ −1.733 | **REFUSE** |
| auto-on-v2 | ✓ +3.33% | ✓ +0.844 | ✓ +0.63% | ✓ +0.097 | PROMOTE |

**The floor refused itself at exactly +0.00%, on the condition that matters and
on two more.** It is the cheapest demonstration available that the bar is a bar,
and it also shows the incumbent condition doing work no floor condition can: the
floor is 2.79% WORSE than what is serving, and F-011's condition is the only one
of the four that would have noticed.

**auto-on-v1 failed all four checks.** It is worse than the floor, worse than the
incumbent, and worse on both KPIs — the one contender in this table that the gate
would have had to refuse under any reading. Its F-015 caveat travels in its row:
the 800-round cap bound it **mid-descent** (val still falling 0.02808 MAE over
its last 100 rounds) after a study that got 9 trials of a configured 60. **That
caveat explains the size of the loss; it does not convert the row into a pass**,
and DR-01 condition 2 forbids the obvious repair — refitting the losing arm
bigger after seeing its number.

**Champion v1 passing against itself is not a tautology worth hiding.** Its
incumbent deltas read `−0.00%` and `+0.000` because it IS the incumbent; the
informative half of its row is `+2.71%` over the floor, which is M3-S1's headroom
number re-measured by a different script and reproduced to the digit.

The bar is quoted from `configs/train.yaml: gate` and never from the minutes
(DR-06): KPI-09 at least **2.00%** below `baseline-group-median-od-fallback`,
KPI-10 must not regress against the floor, and both must not regress against the
**incumbent** — version 1 at **3.2608 min / 81.480%** (F-011, and it has no
knob). The floor measured **3.3518** on test at M3-S1, so the bar a challenger
must clear is **≤ 3.2848** — and the incumbent condition makes the operative
number **≤ 3.2608**, which is tighter.

## 5. The 2×2 arithmetic — features, tuning, or both?

Read against `champion v1`, because that is the cell both tracks started from.
Any other reference makes the two deltas incomparable.

| cell | what moved | test KPI-09 | vs champion v1 |
|---|---|---:|---:|
| champion v1 | — (the origin) | 3.2608 | — |
| artisan v2 | **features only** (v1 → v2, v1's hyperparameters held fixed) | 3.2425 | **+0.56%** |
| auto-on-v1 | **tuning only** (v1 features, scout → sniper) | 3.5038 | **−7.45%** |
| auto-on-v2 | **both** | 3.2403 | **+0.63%** |

**The answer is features.** Features alone bought +0.56%; adding tuning on top of
them bought **+0.07 percentage points more** — 0.0022 min, 134 ms of mean error,
**one seventh of DR-02's own ≥0.50% keep bar for a single feature group**. On the
program's own standard for "worth keeping", the tuning increment does not clear
it. It is reported as a win because it is one, and at its measured size.

**What it cost to buy those 134 ms**: the automation track spent **9,133.8 s** of
fitting against the artisan's **3,313.9 s** (§7) — **2.76×** the wall-clock for
**+0.07 points** on top of what the artisan had already found.

**The square is not additive, and the reason is a confound this table cannot
remove.** Additivity would predict the "both" cell at 0.56 − 7.45 = −6.89%; it
measured +0.63%. The tuning axis is not one variable: the tuning-only cell is
**xgboost truncated mid-descent** (F-015) and the both-cell is **lgbm that
flattened under the same cap** (0.00034 MAE over its last 100 rounds, ~82× less
slope). Family, budget and truncation all move along that axis at once, so
**−7.45% is not a measurement of "what tuning does"** — it is a measurement of
what this budget did to xgboost on v1. Stated here rather than in a footnote,
because the 2×2's whole purpose is causal attribution and one of its two axes is
only partly clean.

**What the square does support, and it is the useful half:** on the features
axis, both tracks agree. Two independently-searched v2 models land 0.0022 min
apart (3.2425 and 3.2403) from opposite methods — hand-chosen feature groups with
fixed hyperparameters, and tuned hyperparameters on feature groups the tuner did
not invent. The feature set, not the search, is what moved this model.

## 6. The alias decision

**The alias MOVES. `auto-on-v2` (`auto-lgbm-v2`, run
`92b73bd4f77d4a05b92472bfcfb3cccf`) is the winner by the pre-registered rule
(lowest test KPI-09) and its verdict is PROMOTE on all four checks** — +3.33%
over the floor against a required 2.00%, KPI-10 +0.844 over the floor, and
against incumbent version 1 both KPI-09 (+0.63%) and KPI-10 (+0.097 points)
improve. `configs/train.yaml: features.version` moves `v1` → `v2` in the same
change, because `scripts/bakeoff_m3.py` refuses to promote a winner that line
does not describe.

**Three things this decision is honest about.**

1. **The winning margin over the runner-up is 134 ms and the runner-up is better
   on KPI-10.** Had the pre-registered ranking metric been KPI-10, the artisan's
   hand-built v2 would be the champion instead. The rule was fixed before the
   numbers existed, which is exactly what stops that observation from becoming a
   re-ranking.
2. **The incumbent condition is non-regression, not a margin** — so a **+0.63%**
   (1.2 s) improvement is enough to move what is served, while the same program
   demands **2.00%** (~4 s) over the floor before it will own a booster at all.
   The asymmetry is defensible (the booster is already owned; the marginal cost
   of a version bump is not the cost of adopting a model class) but it means the
   champion pointer can churn on differences smaller than the program's own keep
   bar. Filed as **F-016** rather than acted on: changing a gate condition after
   seeing the number it would have changed is the one edit this program never
   makes on its own authority.
3. **A promotion is not a claim that tuning paid.** §5 is the claim about tuning,
   and it says +0.07 points for 2.76× the budget.

The verdict is taken by the S1-hardened gate unchanged, with the incumbent
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
