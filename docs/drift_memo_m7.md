# Drift memo — what actually changed in March 2020, and what the champion did about it

**Author:** DA (M7-S5, 2026-08-20) · **Model under observation:**
`models:/nyc-taxi-eta@champion` → registry version **2** (`auto-lgbm-v2`, feature
set **v2**, 24 features), the model that was serving throughout.
**Companion script:** `uv run python scripts/drift_memo_numbers.py [section…]` —
one section per section here, in this order, printing the query it ran.
**Companion detection write-up:** `docs/drift_detection_m7.md` (what the alerts
did). **Named reader of:** `docs/error_memo_m2.md` §7 row 2 and §9.7 row 5 —
both are answered in §5 and §6.1.

---

## §0 What this memo is, and what it is not

This is **interpretation, not detection**. M7-S3 already built the instruments and
watched them decide: input drift stayed inactive, the volume alert fired
(`docs/drift_detection_m7.md`). This memo asks the question an alert cannot
answer — *what actually happened to the city, and what did that do to the
quotes we gave riders?*

Three kinds of number appear here and the difference is the point:

| kind | source | what it is a fact about |
|---|---|---|
| world | `analyst.trips_scoring`, `analyst.trips_scoring_rejected`, `analyst.raw_manifest`, `analyst.scoring_months` | the rows the contract admitted and refused |
| model error | `main_marts.scoring_daily`, `analyst.scoring_predictions` | the champion's error, under **monitoring** ids KPI-14/15/16/17 |
| instrument | `automation/runs/m7-drift/*.json` (tracked) | what the drift job measured |

**The monitoring ids are not the promotion ids and not the M2 segment ids.**
KPI-14/15/16/17 come from the same instrument as everything else in this program
(`taxi_mlops.training.evaluate` — gotcha #15), over a **new window**: a scoring
month the champion was never judged on. KPI-09/KPI-10 belong to the held-out
2019-08 test month and appear nowhere here; KPI-11/12/13 belong to segments of
the 2019 splits. Reusing an id across windows is how a chart's history silently
stops meaning one thing.

**The champion was never retrained on any of this.** M7-S4 built a rescaled
challenger against the settled 2019 window and the gate **refused** it
(`docs/retrain_m7.md`); `@champion` is version 2 before and after every number
below. Nothing in this memo moved a pointer.

---

## §1 Start with the file

Before a single row is parsed, the download says something:

| month | bytes | MiB | share of the largest file we hold |
|---|---:|---:|---:|
| 2019-03 | 116,017,372 | 110.6 | 100.0% |
| 2019-01 | 110,439,634 | 105.3 | 95.2% |
| 2020-01 | 93,562,858 | 89.2 | 80.6% |
| 2020-02 | 92,134,881 | 87.9 | 79.4% |
| **2020-03** | **44,442,590** | **42.4** | **38.3%** |

*(`analyst.raw_manifest`, sha256-pinned at ingest.)*

March 2020's file is **38.3% the size of March 2019's**. That is not a
corruption, a truncated download or a schema change — the contract read it
without a single structural complaint (§1.2). It is simply a month with less
month in it.

### 1.1 Rows in, rows out

| month | rows in | rows out | rejected | rejected % |
|---|---:|---:|---:|---:|
| 2020-01 | 6,405,008 | 6,279,806 | 125,202 | 1.9548% |
| 2020-02 | 6,299,367 | 6,185,309 | 114,058 | 1.8106% |
| 2020-03 | 3,007,687 | 2,948,237 | 59,450 | 1.9766% |

*(`analyst.scoring_months`.)* The 2019 reference the champion was fitted on is
**43,987,422 train rows over six months** — a mean of **7,331,237 rows a month**
— plus 6,189,748 val and 5,950,708 test rows (`analyst.ingest_months`).

**March 2020 delivered 2,948,237 clean rows where an ordinary training month
delivered 7.3 million.** And the most important thing about the rejection column
is how *boring* it is: **1.9766%**, against January's 1.9548% and February's
1.8106%. The refusal profile per rule is the same shape in all three months —
`duration_below_min` largest, then `distance_non_positive`, then `fare_negative`
(§3.3). Nothing about the file was wrong. The data-quality instrument had
nothing to say, because there was no data-quality problem: **March 2020 is
structurally impeccable and statistically alien.**

### 1.2 The daily series is the finding

`analyst.trips_scoring`, grouped by pickup date:

| date | day | trips | mean duration (min) |
|---|---|---:|---:|
| 2020-03-05 | Thursday | **240,520** | 14.669 |
| 2020-03-06 | Friday | 239,720 | **14.878** |
| 2020-03-11 | Wednesday | 179,443 | 13.314 |
| 2020-03-16 | Monday | 62,513 | 11.613 |
| 2020-03-20 | Friday | 26,789 | 10.245 |
| 2020-03-26 | Thursday | 10,329 | 9.699 |
| **2020-03-29** | **Sunday** | **5,361** | 9.715 |

From the peak on **2020-03-05 (240,520 trips)** to **2020-03-29 (5,361)** is a
fall of **97.8%** in twenty-four days. The whole-month row for March is
**2,948,237 trips at a mean duration of 13.1645 minutes** — and *that number is
0.36% below January's 13.2123*. The month-level aggregate is not
wrong; it is dominated by a period during which nothing had happened yet.

---

## §2 The three Marches

Every section below cuts March 2020 the same way, and the cut is declared once
(in `scripts/drift_memo_numbers.py`, `PERIOD_SQL`) so no two sections can
disagree about it:

| period | trips | share of the month |
|---|---:|---:|
| **2020-03 (01–10)** — before | 2,011,616 | **68.231%** |
| **2020-03 (11–21)** — during | 838,721 | 28.448% |
| **2020-03 (22–31)** — after | **97,900** | **3.321%** |

The dates are chosen from the data, not from a news archive: the daily series
holds flat through the 10th, falls continuously from the 11th, and is flat again
at its floor from the 22nd.

**This is the single most useful fact in the memo for anyone building a
monitoring window.** A row-weighted monthly average of March 2020 is
**68% a description of an ordinary month** and **3% a description of the event**.
The average is weighted by exactly the rows that disappeared.

---

## §3 What the remaining rider was buying

| period | trips | duration (min) | distance (mi) | passengers | fare (\$) | total (\$) |
|---|---:|---:|---:|---:|---:|---:|
| 2020-01 | 6,279,806 | 13.2123 | 2.9378 | 1.5180 | 12.5410 | 18.5431 |
| 2020-02 | 6,185,309 | 13.5707 | 2.8628 | 1.5066 | 12.4897 | 18.5064 |
| 2020-03 (01–10) | 2,011,616 | 13.7372 | 2.8849 | 1.4893 | 12.8437 | 18.8130 |
| 2020-03 (11–21) | 838,721 | 12.1963 | 2.9825 | 1.4422 | 12.1380 | 17.8309 |
| **2020-03 (22–31)** | **97,900** | **9.6927** | **3.1169** | **1.3028** | **11.5737** | **16.4631** |

*(`analyst.trips_scoring`.)*

Read the first two numeric columns together, because they move in **opposite
directions**. Between an ordinary January and the last ten days of March the
mean trip got **26.6% shorter in time** (13.2123 → 9.6927 minutes) and
**6.1% longer in distance** (2.9378 → 3.1169 miles).

### 3.1 The streets emptied

| period | mph of the averages | median trip mph |
|---|---:|---:|
| 2020-01 | 13.3411 | 10.2062 |
| 2020-02 | 12.6573 | 9.8559 |
| 2020-03 (01–10) | 12.6003 | 9.9574 |
| 2020-03 (11–21) | 14.6727 | 11.5058 |
| **2020-03 (22–31)** | **19.2942** | **15.2339** |

*(`analyst.trips_scoring`, `trip_duration_minutes > 0`. The two columns answer
different questions — the ratio of the means, and the median of the per-trip
ratio; both are given because the first is what an aggregate dashboard shows and
the second is what a rider experiences.)*

**The median New York taxi trip went 49.3% faster.** That is the mechanism
behind everything in §6: the model's job is to predict *minutes*, and the
minutes-per-mile of the city changed under it while nothing about the requests
themselves looked unusual.

### 3.2 Fewer people per car

Mean passengers falls **1.5180 → 1.3028**, a 14.2% drop, and it falls
monotonically across the five periods. Shared and group travel stopped before
solo travel did.

### 3.3 The contract's own opinion

| rule | 2020-01 | 2020-02 | 2020-03 |
|---|---:|---:|---:|
| duration_below_min | 64,166 | 60,524 | 29,844 |
| distance_non_positive | 27,341 | 20,466 | 12,232 |
| fare_negative | 14,908 | 15,562 | 8,648 |
| duration_above_max | 14,193 | 13,249 | 6,182 |
| duration_non_positive | 4,406 | 3,975 | 2,131 |
| pickup_outside_month | 178 | 276 | 402 |
| distance_above_max | 10 | 6 | 11 |

*(`analyst.trips_scoring_rejected`; first-match filing, M2-S1's law.)* Same rules,
same order, counts falling roughly with volume. The one row that goes the other
way is `pickup_outside_month` (178 → 276 → **402**) — trips whose meter opened in
the previous month, which is a *rate* that rises when the denominator collapses,
not a new fault.

---

## §4 The clock

Share of trips by pickup hour, an ordinary January against the last ten days of
March (`analyst.trips_scoring`):

| hour | Jan % | late-Mar % | | hour | Jan % | late-Mar % |
|---:|---:|---:|---|---:|---:|---:|
| 00 | 2.635 | 1.387 | | 12 | 5.351 | 5.991 |
| 01 | 1.888 | **0.676** | | 13 | 5.422 | 6.434 |
| 02 | 1.375 | 0.449 | | 14 | 5.752 | **7.018** |
| 03 | 0.959 | 0.373 | | 15 | 5.877 | 6.989 |
| 04 | 0.725 | 0.527 | | 16 | 5.577 | 6.697 |
| 05 | 0.855 | 1.430 | | 17 | 6.252 | 6.865 |
| 06 | 1.935 | **4.461** | | 18 | **6.852** | 6.033 |
| 07 | 3.721 | 6.065 | | 19 | 6.199 | 5.020 |
| 08 | 4.727 | 6.117 | | 20 | 5.500 | 3.570 |
| 09 | 4.765 | 5.478 | | 21 | 5.507 | 2.446 |
| 10 | 4.703 | 5.820 | | 22 | 4.885 | 2.114 |
| 11 | 4.916 | 6.095 | | 23 | 3.621 | 1.943 |

Two movements, and they are not the same movement:

- **The night ends.** Every hour from 21:00 to 03:00 loses between **46% and
  67%** of its share; 01:00 goes 1.888% → **0.676%** and 02:00 loses the most
  (1.375% → 0.449%). Evening social travel is what disappeared first and
  hardest.
- **The morning arrives earlier.** 06:00 goes 1.935% → **4.461%**, more than
  double, and 07:00–08:00 both gain. The remaining trips have the shape of
  people who have to be somewhere early — the profile flattens into a working
  day with no evening attached to it.

The evening peak (18:00, 6.852% in January) is no longer the day's maximum;
**14:00 is (7.018%)**. A model whose strongest temporal feature is `hour` is
being asked about a differently-shaped day.

---

## §5 The map, and the airport question

| period | trips | touches JFK/LGA/EWR | touches zone 264/265 ("unknown") |
|---|---:|---:|---:|
| 2020-01 | 6,279,806 | 7.0561% | 0.8484% |
| 2020-02 | 6,185,309 | 6.5496% | 0.7910% |
| 2020-03 (01–10) | 2,011,616 | 6.3832% | 0.8014% |
| 2020-03 (11–21) | 838,721 | 6.1168% | 0.8142% |
| **2020-03 (22–31)** | 97,900 | **4.4974%** | **1.0756%** |

For scale, the same measure on the splits the champion was fitted and judged on:
**train 7.3600% · val 8.3453% · test 8.8175%** (`analyst.trips_clean`).

Airport work fell **from 7.06% of the city's taxi trips to 4.50%** — it did not
merely shrink with everything else, it shrank *faster* than everything else.
Meanwhile the share of trips involving a zone with **no geometry at all**
(264/265, TLC's "unknown", which by DR-04's design have no centroid row and
therefore a named fallback for all nine geometry features) rose from 0.85% to
**1.08%**.

### 5.1 `docs/error_memo_m2.md` §7 row 2, from a third instrument

That row has been open since M2-S4 and reads, after M3: *the champion is ~1.9×
worse on airport trips, and v2's OD geometry — the feature set that was supposed
to "identify them instantly" — did not close it. Either the straight-line
distance already carries what an airport flag would add, or the penalty is about
traffic and terminal dwell rather than distance.* M6-S3's shadow run measured it
a second time, on the wire, and agreed.

Here is the third measurement, on months the memo never saw
(`analyst.scoring_predictions`):

| period | airport trips | airport MAE | ordinary MAE | **gap ratio** | airport bias (min) |
|---|---:|---:|---:|---:|---:|
| 2020-01 | 443,107 | 5.6639 | 2.8295 | **2.0017×** | +2.1939 |
| 2020-02 | 405,113 | 5.3889 | 2.8114 | **1.9168×** | +1.0610 |
| 2020-03 (01–10) | 128,406 | 5.3666 | 2.8881 | **1.8582×** | +1.0394 |
| 2020-03 (11–21) | 51,303 | 8.1382 | 3.4677 | **2.3468×** | +5.8026 |
| 2020-03 (22–31) | 4,403 | 10.4912 | 5.0689 | **2.0697×** | +8.6580 |

**The gap ratio sits between 1.86× and 2.00× in the three ordinary periods and
between 2.07× and 2.35× through the collapse.** Between January and the last ten
days of March the airport MAE rose 85% (5.6639 → 10.4912) and the ordinary MAE
rose 79% (2.8295 → 5.0689): both roughly doubled, and the *ratio* barely moved.

That is evidence for the memo's second reading, and against the first. If the
airport penalty were carried by *distance* — something v2's centroid haversine
measures directly — a world in which the roads emptied and speed rose 49% should
have changed the airport gap, because distance is exactly the term whose
minutes-per-mile changed. It did not. The penalty travels with something the
geometry does not see, and the two candidates the memo named — **terminal dwell
and queueing, and the airport-specific traffic regime** — are both plausible
under a constant ratio while a distance explanation is not.

**Recommendation stands and is now three-times evidenced (§9, row 1):** an
explicit quote-time airport flag is still owed, and it should be evaluated for
what it is — a *regime* indicator, not a distance proxy.

---

## §6 What the champion's error did

All numbers here are **monitoring** ids over `main_marts.scoring_daily` (91 rows,
daily grain, `model_version` = 2 on every row, `model_versions_seen` = 1 by dbt
test).

| month | KPI-17 trips | KPI-14 MAE (min) | KPI-15 within 5 min | KPI-16 bias (min) |
|---|---:|---:|---:|---:|
| 2020-01 | 6,279,806 | 3.0295 | 83.226% | +0.2836 |
| 2020-02 | 6,185,309 | 2.9802 | 83.768% | −0.1703 |
| **2020-03** | 2,948,237 | **3.3227** | **80.569%** | **+0.5468** |

Read at monthly grain, March 2020 looks like a slightly worse month. **It was
not a slightly worse month.**

### 6.1 A note on what is deliberately absent

`marts.scoring_daily` carries **no floor column and no margin column**. That is
`docs/error_memo_m2.md` §9.7 row 5's condition honoured by refusing the
comparison rather than by making it: the honest floor
(`baseline-group-median-od-fallback`, the name that travels on the champion
version's `gate_floor` tag) is **fitted on the 2019 train months**, and a "margin"
computed against it on 2020 data would publish a comparison no gate ever made,
against a bar chosen for a different world. Month-over-month KPI-11/KPI-13 is
only meaningful against the same floor; here it would not be, so it is not
published. What *is* published — MAE, within-tolerance rate, signed bias, count —
needs no reference model to mean something.

### 6.2 The daily series, which is where the event is

| date | day | trips | KPI-14 | KPI-15 | KPI-16 | mean actual | mean quoted |
|---|---|---:|---:|---:|---:|---:|---:|
| 2020-03-09 | Mon | 172,339 | 2.8598 | 85.146% | +0.0369 | 13.350 | 13.387 |
| 2020-03-12 | Thu | 167,799 | 3.4456 | 78.248% | +1.2210 | 13.754 | 14.975 |
| 2020-03-16 | Mon | 62,513 | 3.9527 | 73.399% | +2.6236 | 11.613 | 14.237 |
| 2020-03-18 | Wed | 35,307 | 5.4856 | 58.292% | +4.5529 | 10.763 | 15.315 |
| 2020-03-19 | Thu | 29,016 | 5.8571 | 56.259% | +4.9249 | 10.296 | 15.221 |
| **2020-03-26** | **Thu** | 10,329 | **6.3693** | **53.723%** | **+5.3197** | 9.699 | 15.019 |
| 2020-03-31 | Tue | 9,026 | 5.9596 | 55.717% | +4.8401 | 9.591 | 14.431 |

Compare against the best and worst day of each month:

| month | best day | best KPI-14 | worst day | worst KPI-14 |
|---|---|---:|---|---:|
| 2020-01 | 2020-01-19 | 2.3970 | 2020-01-03 | 3.5757 |
| 2020-02 | 2020-02-17 | 2.4043 | 2020-02-20 | 3.3021 |
| 2020-03 | 2020-03-01 | 2.5161 | **2020-03-26** | **6.3693** |

**March 2020's worst day is 78% worse than January's worst day**, and on it
**barely half of riders (53.723%) got a quote within five minutes** against a
fleet norm above 83%. The two "best day" entries are worth a glance too:
2020-01-19 is a Sunday, and 2020-02-17 is Presidents' Day — a federal holiday the
feature set knows about by name.

### 6.3 The model did not get confused. It kept answering the old question.

The last two columns are the whole diagnosis. On 2020-03-26 the mean *actual*
trip was **9.699 minutes** and the champion's mean *quote* was **15.019** — it
kept quoting the trip the same request would have taken in a normal city.
KPI-16, the **signed** bias, is what says so out loud: it climbs
**+0.0369 → +5.3197 minutes** across the month and never once goes negative
after the 9th.

This is why KPI-16 exists as a separate id. An absolute error cannot distinguish
a model quoting five minutes too long from one quoting five minutes too short,
and in a month when the streets emptied those are opposite diagnoses with
opposite fixes. **The champion was systematically over-quoting**, by an amount
that tracks the collapse almost exactly. Nothing was broken; the world stopped
matching the training set, and the model — correctly, from its own point of view
— kept describing the training set.

### 6.4 The best days in the collapse are the days the model was already told the
city would be quiet

| period | part of week | trips | KPI-14 |
|---|---|---:|---:|
| 2020-01 | weekday | 4,781,361 | 3.1306 |
| 2020-01 | weekend | 1,498,445 | 2.7069 |
| 2020-03 (22–31) | weekday | 75,167 | **5.7308** |
| 2020-03 (22–31) | weekend | 22,733 | **3.9306** |

*(`analyst.scoring_predictions`, `dayofweek >= 5`.)* In January weekend error is
**13.5% below** weekday error; in the last ten days of March it is **31.4%
below** — the gap between the two roughly doubles. Look back at §6.2 and the dips
are exactly on 03-21, 03-22, 03-28 and 03-29 — every Saturday and Sunday.

The reading is not that weekends were spared. It is that **`dayofweek` is the
one feature that already encodes "the city is quiet today"**, so on the two days
a week when the model expected a quiet city, its quotes were less wrong. The
model had a vocabulary for this event and could only reach it two days in seven.

---

## §7 What the instruments said, and what no instrument here could say

Read back off the tracked records (`automation/runs/m7-drift/*.json`):

| month | rows | trips/day | **volume ratio** | **max input PSI** |
|---|---:|---:|---:|---:|
| 2020-01 | 6,279,806 | 202,574.4 | 0.8336 | 0.0103 |
| 2020-02 | 6,185,309 | 213,286.5 | 0.8776 | 0.0087 |
| **2020-03** | 2,948,237 | 95,104.4 | **0.3913** | **0.0217** |

And the headroom leg, the two 2019 months whose verdict already exists — the
champion was measured on them and promoted:

| month | rows | volume ratio | max input PSI | carried by |
|---|---:|---:|---:|---|
| 2019-07 | 6,189,748 | 0.8216 | **0.0323** | `dayofweek` |
| 2019-08 | 5,950,708 | 0.7899 | 0.0137 | `PULocationID` |

**The most-moved input column in the worst month this program will ever hold sits
at PSI 0.0217 — lower than an ordinary, accepted July 2019 does at 0.0323.**
And July's 0.0323 is `dayofweek`, i.e. *five Mondays*: calendar arithmetic, the
least model-meaningful move a month can make.

That is not an instrument failure, and it is worth being precise about why. PSI
is a distance between **shares**. By the shape of its requests, March 2020 is not
a strange month: the same kinds of trip were requested from the same places at
roughly the same relative frequencies. The city did not start taking *different*
taxi trips. **It stopped taking taxi trips.** Halve every count and PSI is
exactly zero, which is why volume had to be measured as its own marginal (A-9)
rather than as a refinement of A-8 — and why A-8 correctly stayed inactive while
A-9 fired for 2020-03 alone.

**Two honest limitations, both already on the record:**

1. **The window hides the event.** At monthly grain the input signal is flat
   through a catastrophe, and §2 shows exactly why — 68% of the month's rows
   pre-date it. §4's hour profile and §3's speed numbers are computed over the
   *last ten days*, and they are not flat at all. A daily drift window would very
   likely fire A-8 on 22–31 March. That change is **not** made here: the window
   is part of the bar, and moving it after seeing that A-8 stayed quiet is
   exactly the threshold-walking M7 law 4 forbids. It is routed to ARCH with this
   evidence.
2. **No instrument in this stack could have told anyone *why*.** The alert that
   fired says trips/day fell by 61%. Everything in §3–§6 — the speed, the clock,
   the airports, the sign of the bias — required a human to ask. That is the
   division of labour this memo exists to demonstrate, not a gap to close with
   another rule.

---

## §8 What this memo does not claim

- **It does not claim the champion should be retrained on 2020 data.** That is a
  direction decision with a live fork behind it (AWAITING_PO 2026-08-18-1), and
  the evidence cuts both ways: the model is over-quoting by five minutes on 3.3%
  of a month's rows, and those rows are drawn from a world that — from March
  2020's own vantage point — nobody could say would persist. Fitting to a
  ten-day regime is how a model learns an emergency as if it were a season.
- **It does not claim any of these numbers is a promotion metric.** No number
  here has faced a gate. The one challenger M7 built was judged on the settled
  2019 holdout and refused (`docs/retrain_m7.md`).
- **It does not compare the champion to a floor on 2020 data** (§6.1).
- **It does not attribute causes outside the data.** "The streets emptied" is a
  statement about `trip_distance / trip_duration_minutes`; every domain reading
  above is anchored to a column, and where a reading is a *hypothesis* — terminal
  dwell in §5.1, essential-worker travel in §4 — it says so.

---

## §9 Recommendations

| # | to | recommendation | evidence |
|---|---|---|---|
| 1 | MLE (M8/M9) | **An explicit quote-time airport flag, evaluated as a regime indicator rather than a distance proxy.** The gap held at ~2× across a world in which speed rose 49%, which is the observation a distance explanation has to survive and does not. Third independent measurement of `error_memo_m2.md` §7 row 2; the row should now be read as *evidence for the dwell/traffic reading*, not as an open coin-flip. | §5.1 |
| 2 | ARCH (M7 boundary) | **Decide the drift window deliberately.** Monthly grain is the kickoff's specification and it shipped; §2 and §7 price its cost exactly. The daily series already exists (`marts.scoring_daily`). This memo does not choose, on purpose. | §2, §7 |
| 3 | SRE / MLE | **Keep KPI-16 (signed bias) on the first screen of any monitoring board.** It is the only published number that distinguishes over-quoting from under-quoting, and in this event it is the number that reads as a diagnosis rather than as a degradation. | §6.3 |
| 4 | MLE | **`dayofweek` is the model's only vocabulary for "quiet city" and it is a seven-valued one.** Whatever a future feature review does about regime shifts, it should note that in the collapse weekend error sat **31.4% below** weekday error, against **13.5% below** in an ordinary January — a cheap, already-fitted signal pointing at what a demand or congestion feature would carry. | §6.4 |
| 5 | DA (standing) | **Report drift months with the daily series beside the monthly row, always.** Every monthly figure in §1 and §6 is defensible and every one of them understates the event by roughly the ratio in §2. | §1.2, §2, §6.2 |

---

*Every figure above re-prints from `uv run python scripts/drift_memo_numbers.py`.
A disagreement between this document and that script is a defect in one of them.*
