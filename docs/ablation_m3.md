# The artisan ablation — feature set v2, earned group by group (M3-S3)

Date: 2026-08-17 · Story: M3-S3 · Role: MLE · Track: **artisan** (Design Review
DR-03: the artisan searches FEATURES and holds hyperparameters at v1's).

Every number in this document came from `taxi_mlops.training.evaluate` and
nowhere else (gotcha #15), on the **validation** month 2019-07. **The test month
was not read by this story, at all** — DR-05 §3 gives each contender one shot at
it, and that shot is M3-S5's.

Reproduce: `make ablation` (15% sample, six experiments) ·
`make ablation ABLATION_ARGS="--full-scale --sets v1,v1_g1,v1_g2,v2 --log-model"`
(the confirmation). Machine-readable rows: `docs/ablation_m3.json` (the 15%
sample, §2) and `docs/ablation_m3_confirmation.json` (full data, §5) — two files
because §2's verdicts are built from the sample rows and overwriting them would
destroy the evidence the verdicts cite. MLflow experiment: **`m3-artisan`**.

**Anything long in this program is run detached** (`automation/run_detached.sh`)
— the confirmation was killed once, mid-fit, by the session that was waiting for
it. Gotcha #45.

---

## 1. The protocol this ran under, and why each rule is here

| rule | source | what it prevented here |
|---|---|---|
| groups declared in a FIXED ORDER before anything was fitted | DR-02 anti-forking-paths | the five groups and their contents are in `configs/features.yaml: groups`, committed with the code that reads them |
| every group tried is reported, survivors AND drops | DR-02 | three of five groups lost; a table with only the winners in it would have implied a hit rate of 100% |
| a group is KEPT only at >= 0.50% relative val MAE | DR-02, playbook §3.4 | g3 (+0.14%) is a real improvement and is still dropped — it is not worth a permanent branch in the serving transform |
| KPI-10 reported per group beside val MAE | DR-02 addition (DA's), AI-2 | a mean over 6M rows can improve while more riders are quoted wrongly |
| one change per experiment, fixed seeds | playbook §3.2 | each row differs from the reference in exactly one group |
| sample-first, winners confirmed at full scale | playbook §3.1 | it CONFIRMED — both keeps held to within 0.02 points at 6.7× the rows, and §5's pre-registered prediction that they would not is left standing beside the measurement that refuted it |
| hyperparameters held at v1's | DR-03 | so M3-S5's 2x2 can answer "features or tuning?" |
| fitting wall-clock measured and printed | DR-01, AI-1 | "equal budgets" is a number somebody can check |

---

## 2. The ablation table (15% stratified sample · 6,598,113 train rows · 928,462 val rows)

Reference is `v1` — the same five columns the serving champion eats. Δ is
relative val MAE against that reference; positive is better.

| experiment | groups | features | val MAE | Δ val MAE | KPI-10 | Δ KPI-10 | best iter | fit s | verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `v1` | — (base) | 5 | 3.4935 | — | 79.552% | — | 500 | 91 | reference |
| `v1_g1` | g1 temporal extras | 15 | 3.4312 | **+1.78%** | 80.145% | +0.594 | 500 | 119 | **KEEP** |
| `v1_g2` | g2 centroid geometry | 14 | 3.4715 | **+0.63%** | 79.734% | +0.182 | 500 | 108 | **KEEP** |
| `v1_g3` | g3 spatial identity | 11 | 3.4887 | +0.14% | 79.582% | +0.030 | 500 | 111 | drop — under the bar |
| `v1_g4` | g4 trip re-encodings | 6 | 3.4938 | −0.01% | 79.534% | −0.017 | 500 | 105 | drop — measured zero, as predicted |
| `v1_g5` | g5 point-in-time aggregates | 8 | 3.5503 | **−1.63%** | 78.866% | −0.686 | 88 | 24 | drop — **and it is the finding** |

Measured fitting wall-clock for this invocation: **557.1 s** (DR-01 condition 1).

MLflow runs, one per row, experiment `m3-artisan`:
`45e8cf85588e4132b80665c3f77c803b` (v1) · `artisan-v1_g1` · `artisan-v1_g2` ·
`artisan-v1_g3` · `artisan-v1_g4` · `7c98f97c55d64328b6d1e0cd51c9a143` (v1_g5).

---

## 3. What each group turned out to be worth

**g1 — temporal extras (+1.78%, the largest single win).** Cyclic hour and
week-position, minute-of-day, part-of-day, weekend, and the three calendar flags
off a committed federal-holiday table. The dossier's honest caveat at row 3 said
to expect *a small or zero delta*, because a boosted tree can split an integer
hour into the same buckets by itself — the sources that leaned on cyclic
encodings were fitting neural nets. **That caveat was wrong here**, and by a wide
enough margin to be the milestone's largest single feature win.

Why is a **hypothesis and is labelled one**, because the experiment that would
settle it was not run: the likely carrier is `minute_of_day`, since v1 gave the
model an integer hour and nothing finer — 08:55 and 09:05 sat 1 apart on a scale
where the whole morning peak is one step wide — and the cyclic and bucket
encodings really are re-statements a tree can derive. But the group was admitted
as a group, and **which member carries the +1.78% is a question this ablation
cannot answer.** It is the obvious first thing for a successor to split apart, and
if `minute_of_day` alone carries most of it then v2 is presently paying for nine
columns to get the value of one.

**g2 — centroid geometry (+0.63%, the F-007(b) substitute earning its keep).**
Haversine, the two Manhattan legs, bearing, log-distance, midpoint, and the
`has_geometry` flag. It clears the bar and it is the group with the strongest
prior claim on the milestone: DR-04 adopted it as the quote-time replacement for
`trip_distance` on a correlation argument (0.7873 vs the meter's 0.8068), and
this is the first time it has been asked what it is worth *on top of the zone
identity v1 already had*. The answer — a real but modest 0.63% — is worth
sitting with: **the correlation argument overstates the marginal value, because
`PULocationID` and `DOLocationID` were already in the model.** A zone pair is a
strictly finer description of a route than the distance between two zone
centroids; what the distance adds is a smooth ORDERING over pairs the tree has
few rows for. Its value should therefore fall as data grows — and §5 measures
exactly that.

**g3 — spatial identity (+0.14%, dropped).** Airport flags and borough pair,
aimed by `docs/error_memo_m2.md` at the airport segment (1.90× the error) and at
the OD-fallback rows. It improves and it does not clear a maintenance-cost bar.
The reading is the same as g2's, one step further: 132, 138 and 1 are already
*in* the model as zone ids, and "is this zone JFK" is a fact a tree can learn
from one categorical split. The flags told it nothing it could not already say.
Dropping this group is the DR-02 bar doing precisely the job it was argued for —
this is not a null result, it is a small real gain that does not pay rent.

**g4 — trip re-encodings (−0.01%, dropped).** Included, per DR-03's own note, so
that "expected zero" would be **measured** once rather than assumed forever. It
came back at minus one hundredth of one percent. That is the cheapest row in
this table and the one most likely to save a future session an afternoon.

**g5 — point-in-time aggregates (−1.63%, dropped).** §4.

---

## 4. The surprise: the strongest family in every source is the one that lost

Dossier row 14 calls the aggregate family "the single strongest aggregate family
in the sources", and the artisan playbook §1 lesson 4 says "traffic lives in
aggregates". Fitted legally, it made the model **worse on both KPI-09 and
KPI-10**, and it is the only group that did.

Three things are true at once, and the order matters:

1. **The legal version is weaker than the illegal one by construction.** A row
   in train month *k* is served an aggregate built from months 1..*k−1* and
   nothing else, so the first train month (7.3M rows, a sixth of train) gets NaN
   and month 2 gets a one-month window while val gets six. The feature the model
   is fitted on is therefore *not the feature it is scored on* — a train/serve
   skew the point-in-time constraint creates rather than cures.
2. **`od_median_duration_min` is the gate's own floor wearing a feature's
   clothes.** `baseline-group-median-od-fallback` is a `GROUP BY (PU, DO)`
   median; so is this column. Handing a booster its own baseline as an input is
   not obviously useful, and here it was actively harmful: the model early-stopped
   at **iteration 88** against 500 for every other row in the table. It found the
   column, leaned on it, and stopped learning the thing it was better at.
3. **The competition sources had no such constraint.** Their group statistics are
   taken over train and test together, which is legal when the test period
   interleaves the train period — and it is why the family looks so strong in
   their write-ups. `docs/leakage_redteam_m3.md` measures what that version buys
   here, on purpose, so the comparison is a number instead of an argument.

**What this does NOT license.** It does not say historical aggregates are
worthless for ETA — it says *this* keying, *this* point-in-time scheme, and *this*
train window make them worthless here, on top of features that already encode the
zone pair. A leave-one-out or rolling-window encoding with a shorter, constant
history is a different experiment, and it is named in the dossier's verdict
column as an M8 Feast candidate rather than deleted.

---

## 5. Full-scale confirmation — the rule that earned itself, but not where it was expected to

Playbook §3.1 requires sample winners to be re-measured at full scale before
they are called keeps. **Both keeps survived, and the confirmation's own
surprise is that it had nothing to correct.**

*This section was written in two sittings and the second one had to argue with
the first.* The paragraph below the trend table originally predicted that g2
would keep shrinking, and it is left standing with its refutation beside it —
a prediction quietly deleted after the measurement arrives teaches nobody
anything, and this one was wrong in a specific, reusable way.

Watch the geometry group across three data sizes, all val, all the same code:

| train rows | g2's Δ val MAE over v1 |
|---:|---:|
| ~220k (0.5%, the harness smoke test — see the caveat) | **+2.98%** |
| 6,598,113 (15%, the ablation) | **+0.6312%** |
| 43,987,422 (100%, the confirmation) | **+0.6277%** |

*(The 0.5% row was the `--no-mlflow` run that proved the harness worked before
any budget was spent on it. It has **no MLflow row**, so by playbook §3.3 it is
not a result and is quoted here only as the third point of a trend. The two rows
below it are both ledgered.)*

**Written before the confirmation ran:** *"The trend is not noise and it is not
a bug — it is g2's whole mechanism. Centroid distance is a smooth ordering over
zone pairs the tree has too few rows to learn individually, and every extra row
is one more row it does have. A feature whose job is to substitute for missing
data is worth less as the data arrives, so a 15% sample systematically
over-values it. Any keep decision taken on the sample alone would have
over-stated this group."*

**What the confirmation measured:** +0.6312% at 15% and **+0.6277%** at 100% —
the same number to two decimal places, on 6.7× the rows. The mechanism argument
is not wrong about *why* the 0.5% run was inflated; it is wrong about the shape
of the curve. The collapse happens between 0.5% and 15% and is **flat**
thereafter, which says the ordering-over-sparse-pairs story is a **small-sample**
effect that has already exhausted itself by 6.6M rows, not a slope that keeps
running. g1 behaved the same way (+1.7834% → +1.7712%). The reusable lesson is
narrower than the one this section first drew and more useful: **a 15% sample of
44M rows was an unbiased estimate of both group deltas to within 0.02
percentage points, and the run that lied was the 220k smoke test nobody was
supposed to quote.** The playbook's confirmation rule still earned its budget —
it is what turned "probably fine" into a number — but it earned it by
confirming, and the honest report of a confirmation is that nothing moved.

### The confirmation table (full data · 43,987,422 train rows · 6,189,748 val rows)

Same code, same seed (`20260817`), same evaluator, no sampling. Rows from
`docs/ablation_m3_confirmation.json`; every one is an MLflow run in `m3-artisan`.

| experiment | groups | features | val MAE | Δ val MAE | KPI-10 | Δ KPI-10 | best iter | fit s | run id | verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| `v1` | — (base) | 5 | 3.4760 | — | 79.693% | — | 500 | 485.0 | `a4d9f9ebd62a4e628ce7dccecce55fd3` | reference |
| `v1_g1` | g1 temporal extras | 15 | 3.4145 | **+1.77%** | 80.263% | +0.569 | 500 | 579.6 | `9fd1429002104c61ad111c94731109bb` | **KEEP confirmed** |
| `v1_g2` | g2 centroid geometry | 14 | 3.4542 | **+0.63%** | 79.894% | +0.200 | 500 | 501.1 | `9494748ffcbd4dcd971f31976a03a0f7` | **KEEP confirmed** |
| **`v2`** | **g1 + g2** | **24** | **3.3905** | **+2.46%** | **80.506%** | **+0.813** | 500 | 569.4 | `6807116edf4c49d681a31bd941298a81` | **feature set v2** |

Measured fitting wall-clock for this invocation: **2,135.0 s** (DR-01 condition 1).

**Two readings the table supports and one it does not.**

1. **The groups are additive, very nearly.** 1.7712% + 0.6277% = 2.3989% against
   a measured **2.4597%** for the two together. The 0.06-point excess is the only
   interaction this story ever measured and it is too small to build on; what it
   does rule out is the opposite worry — that the two groups were describing the
   same thing twice and would collapse when combined. They do not.
2. **v1 reproduced itself exactly across two independent invocations**, run 71
   minutes apart on the same data: `3.47603843547682` from the run the killed
   session started at 13:40:05Z, and `3.47603843547682` from this one. The fit is
   deterministic and the harness is not carrying state between arms. It also
   equals **M2-S2's 3.4760** val MAE for `lightgbm-v1` — a third instrument, from
   a different script, agreeing to four decimals on the same five columns.
3. **What it does NOT support is any comparison to the gate.** These are
   validation numbers on 2019-07. The bar M3 must clear is **3.2848 test MAE**
   (`docs/promotion_gate_m3.md`), on 2019-08, which no number in this document
   has been near. v2 is a *contender*, and it becomes a verdict at M3-S5.

**Fitting budget (DR-01 condition 1, artisan track).** Budget **9,000 s**.
Logged and spent: **3,313.9 s** across 15 runs in `m3-artisan` — the 15% ablation
(557.1 s, 6 arms), the confirmation (2,135.0 s, 4 arms), the **455.5 s** orphan
`artisan-v1` arm from the run that was killed at 13:50:07Z (gotcha #45, counted
because the CPU really burned) and the §7 post-fix re-measurement (166.2 s, 2
arms). Two red-team arms logged no `fit_seconds` and are therefore unmeasured
rather than free — stated so the total is read as a floor. **~37% of the artisan
budget, and the track stopped because its stop rule fired, not because it ran
out** (three of five groups under the bar; §3).

---

## 6. Feature set v2, as committed

`configs/features.yaml: sets.v2` — **the one home for feature-set definitions**
since this story (F-013's features half, Design Review AI-6). `configs/train.yaml`
holds a version and a pointer and nothing else.

v2 = base + `g1_temporal_extras` + `g2_centroid_geometry`, **24 features**:

```
hour dayofweek PULocationID DOLocationID passenger_count
hour_sin hour_cos weekpos_sin weekpos_cos minute_of_day part_of_day
is_weekend is_holiday is_near_holiday is_business_day
centroid_haversine_km centroid_dlat_km centroid_dlon_km centroid_manhattan_km
centroid_bearing_deg log1p_haversine_km midpoint_lat midpoint_lon has_geometry
```

Every one of them carries a `REQUEST_TIME_SOURCE` entry naming where a live
request would get it (gotcha #21, pinned by a test), and nine of them are lookups
into a 263-row table that ships with the model — no service call, no live join.

**Membership was decided by the full-scale numbers, not the sample's** — the
kickoff's own instruction, and it happens to have changed nothing: both groups
cleared DR-02's bar on both conditions at 44M rows (g1 +1.77% / +0.569 KPI-10
points, g2 +0.63% / +0.200). Had g2 landed under 0.50% the set would have shipped
as base + g1 and this paragraph would say so.

**The v2 booster is logged and servable**: run `6807116edf4c49d681a31bd941298a81`
in `m3-artisan`, fitted on all 43,987,422 train rows with **signature + input
example** (`--log-model`). It is a *contender*, not a candidate for the alias —
nothing in this story touches the registry, and a test keeps the registry API out
of the story's diff. The gate sees it at M3-S5.

**`configs/train.yaml` still names v1**, deliberately. Version 1 of
`nyc-taxi-eta` is serving and its signature is over v1's five columns; the config
line moves as part of a promotion at M3-S5 or not at all.

---

## 7. Limits of this table, stated rather than discovered later

- **Groups, not features.** Every verdict is about a group. g1's +1.78% is not
  attributed to any member of it, and the ablation as specified cannot do that.
- **One seed.** `seed: 20260817`, fixed, one fit per row. The playbook's optional
  3-seed average (§3.7) was not spent; at these margins (+1.77% and +0.63%
  against a 0.50% bar) the confirmation run was the better use of the budget.
  **g2 still sits 0.13 points above the bar at full scale**, so a seed sweep
  remains the reasonable thing for a successor to want — the confirmation says
  the sample was not lying, which is a different claim from "the margin is
  comfortable". Budget remains: ~5,690 s of the artisan 9,000.
- **Val only.** No number here has faced the promotion gate, and none of them is
  comparable to the 3.3518 test-MAE bar in `docs/promotion_gate_m3.md` — that is
  a different month.
- **The aggregates were tried once, one way.** §4's last paragraph.
- **No interaction was searched.** The groups were tested against v1 and then the
  survivors combined; g3 might pay in the presence of g2, and nothing here would
  have seen it.
- **§2's g3 row was measured before a defect in `zones.load_zone_table` was
  fixed, and the row was RE-MEASURED rather than annotated.** The shipped TLC
  lookup spells "not a place" two ways — zone 264 carries Borough `Unknown`,
  zone 265 carries `N/A` — and the loader took both literally, minting a second
  borough code whose meaning is "we do not know". 265 is **0.2238% of train rows
  and 0.2742% of val rows**, so the effect had to be small; small is not a
  measurement, so the drill was re-run at the same 15% and the same seed after
  the fold (`--story M3-S3-postfix`, `docs/ablation_m3_g3_postfix.json`):

  | arm | before the fold | after the fold | run id (post-fix) |
  |---|---:|---:|---|
  | `v1` control | 3.4935018525 | **3.4935018525** | `4cb2964ae1264f83a4e8a8679f55660b` |
  | `v1_g3` | 3.4886629511 (+0.1385%) | 3.4881427170 (**+0.1534%**) | `14b697188eba4ce98991cbfbc614756c` |

  The control reproduced to ten decimal places, which is what licenses reading
  the 0.0149-point move as the fix rather than as run-to-run noise. **g3's
  verdict is unchanged and unchangeable by this** — it needs 0.50% and gained
  0.015. §2's table is left at the numbers its verdicts were taken on, with this
  row as the correction; the groups that shipped (g1, g2) contain no borough
  feature and no v2 number is affected.
- **`make train` cannot fit a set that uses the point-in-time aggregates.**
  `run.py` builds its splits through `load_split`, which does not fit the
  aggregate tables — only `scripts/artisan_ablation.py` and the red-team do. That
  costs nothing today because g5 was dropped and v2 needs no fitted tables, and
  the failure is loud rather than silent (`build_features` raises naming the
  missing tables and why they must come from TRAIN). It is recorded as a gap
  rather than plugged, because plumbing that nothing uses is plumbing nothing
  tests. **A future story that admits an aggregate group owes `run.py` that
  path.**
- **MLflow's signature warning applies to v2 and is not new.** Logging a booster
  whose matrix carries integer columns produces MLflow's "integer columns cannot
  represent missing values" hint. v1's champion already has it (`PULocationID`,
  `DOLocationID` are int16); v2 adds nine more integer columns, seven of them
  flags that are never null. The one that could matter at M5 is
  `passenger_count`, which is float32 precisely because the contract allows it to
  be null. Named here so M5 meets it in a document rather than in a schema
  enforcement error.
