# Error memo — where the ETA champion is wrong (M2-S4, role:DA)

**Authored:** 2026-08-17 (M2-S4) · **Owner:** DA · **MLE consulted** on
interpretation · **Subject:** `models:/nyc-taxi-eta@champion` → registry version
**1**, MLflow run `3adee05a855a424bb664c7fea3735703`, feature set v1
(quote-time pure, five features, no distance).

**Board:** [Error segments](http://localhost:3030) — Metabase dashboard
**"Error segments (M2)"**, defined in
`analytics/metabase/boards/error_segments.json`, converged by `make boards`.
Every card on it cites a KPI id from `docs/kpi_definitions.md`. Every number in
this memo comes from that board's mart (`marts.error_segments`) or from the
`predictions` view under it — the queries are named per section, and none of
them reads a parquet path.

**How to reproduce every number here, from a clean checkout:**

```
make data          # DVC-pinned raw -> data/processed (M1)
make train         # fits, gates, promotes -> models:/nyc-taxi-eta@champion (M2-S3)
make predictions   # scores THAT champion, publishes data/predictions/  (M2-S4)
make duckdb        # catalogues it; refuses if a held-out row lacks a prediction
make marts         # builds + tests error_segments, publishes it to Postgres
make boards        # renders the error-segment board from checked-in JSON
```

---

## 0. What this memo is allowed to say, and what it is not

The model's headline numbers are **KPI-09 3.2608 min** and **KPI-10 81.480%** on
the untouched test month, and they were produced by
`taxi_mlops.training.evaluate` — the only thing in this program permitted to
produce them (gotcha #15). This memo does not recompute them. It aggregates the
**rows** that evaluator published: one per held-out trip, carrying the actual
duration, the champion's quote, and the honest floor's quote for the same trip.

The segment numbers are therefore new ids — **KPI-11** (segment MAE), **KPI-12**
(segment within-5-min rate), **KPI-13** (segment margin over the honest floor) —
because their window is a segment rather than a split (`kpi_definitions.md`
rule 5). Rolled up over a whole split they reproduce KPI-09/KPI-10 exactly, and a
dbt test fails the build if they ever stop doing so:

| split | trips | KPI-11 (mart) | KPI-09 (evaluator) | KPI-12 (mart) | KPI-10 (evaluator) |
|---|---:|---:|---:|---:|---:|
| val (2019-07) | 6,189,748 | 3.4760 | 3.4760 | 79.693% | 79.693% |
| test (2019-08) | 5,950,708 | 3.2608 | 3.2608 | 81.480% | 81.480% |

Every table below is **test (2019-08)** unless it says otherwise: test is the
month neither the fit nor the early stopping ever saw. Val numbers are quoted
where the two disagree, because a segment finding that appears in only one month
is a finding about a month.

---

## 1. The headline, and it is not the headline the gate reported

The promotion gate recorded **+7.07%** over the honest floor. Split by whether
that floor had anything to say about a row, the same 7.07% looks like this:

| rows | share of test | KPI-11 (model) | floor MAE | KPI-13 | KPI-12 |
|---|---:|---:|---:|---:|---:|
| floor has a real group median | 98.521% (5,862,719) | 3.2211 | 3.2830 | **+1.88%** | 81.817% |
| floor falls back to the global median | **1.479%** (87,989) | 5.9066 | **18.5704** | **+68.19%** | 59.016% |

The floor is a `GROUP BY (hour, dayofweek, PU, DO)` median with a single-level
fallback: when a held-out trip carries a combination train never saw, it predicts
11.15 minutes — the global median — and is wrong by 18.57 minutes on average.

Decomposing the 0.2482 min the champion takes off the floor's MAE:

* rows the floor can answer: `0.985214 × (3.2830 − 3.2211)` = **0.0610 min**, or
  **24.6%** of the gap;
* rows it cannot: `0.014786 × (18.5704 − 5.9066)` = **0.1872 min**, or
  **75.4%** of the gap.

**Three quarters of the champion's entire advantage over a SQL query is bought on
1.48% of the rows.** On the 98.5% of trips where the lookup table has an answer,
the booster is worth 1.88% — about **3.7 seconds** of mean error.

That is not an argument against the model; it is an argument about *what the
model is for*. Generalising to unseen (hour, day, origin, destination)
combinations is precisely what a lookup table cannot do and a booster can, and at
M5 that 1.48% is not a rounding error — it is the request that would otherwise
return a number invented from a global median. But it does mean three things
this program should carry forward:

1. **The gate's margin is dominated by coverage, not by accuracy.** Any change
   that alters how often the floor falls back (more train months, a coarser key,
   a sampled run) moves the bar far more than it moves the model. This is
   **F-008** measured from the other side, and it lands on M3.
2. **KPI-13 near zero is not failure.** In a well-covered segment, 1.88% is what
   an honest booster on five quote-time features looks like.
3. **The 1.48% is a serving-shaped number**, not an offline one. M5's parity
   tests and M8's Feast candidates should both know that one request in 68 is in
   the regime where the naive answer is 18 minutes wrong.

*(Query: `SELECT * FROM marts.error_segments WHERE segment = 'unseen_group'`.)*

---

## 2. Long trips: the model has a ceiling, and it is below the data's

This is the sharpest failure in the set, and it is not a matter of degree.

| actual duration | trips | share | KPI-11 | KPI-12 | KPI-13 | mean actual | mean quoted |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1–5 min | 824,986 | 13.864% | 2.2728 | 92.422% | **−0.88%** | 3.55 | 5.72 |
| 5–10 min | 1,754,599 | 29.486% | 2.0213 | 93.683% | +0.24% | 7.45 | 8.37 |
| 10–20 min | 2,106,266 | 35.395% | 2.9743 | 82.365% | +1.91% | 14.19 | 13.85 |
| 20–30 min | 747,431 | 12.560% | 4.5608 | 64.610% | +10.31% | 24.11 | 22.24 |
| 30–45 min | 347,541 | 5.840% | 6.7219 | 48.482% | +18.88% | 36.00 | 32.44 |
| 45–60 min | 121,577 | 2.043% | 9.2264 | 37.969% | +21.63% | 51.21 | 45.43 |
| 60–100 min | 47,338 | 0.796% | 16.7513 | 21.106% | +12.72% | 69.47 | 54.17 |
| **100–120 min** | **970** | 0.016% | **59.9933** | **0.000%** | +3.79% | 107.92 | **47.93** |

Read the last row twice. Of the 970 longest trips the contract admits, the
champion quotes **none** of them within five minutes — KPI-12 is not "low", it is
**zero** — and its average quote is 47.9 minutes against an average truth of
107.9. The best single quote in that band is still 9.7 minutes out.

The mechanism is visible in the whole split, not just that band:

* the highest number the champion ever predicts on test is **92.155 minutes**,
  against a maximum truth of 120.0 (val: 95.614 vs 119.967);
* it quotes above 60 minutes for **28,083** test trips (0.472%) while **48,097**
  test trips (0.808%) actually run past 60;
* of the trips that really do exceed 60 minutes, only **36.86%** get a quote
  above 60 at all.

This is regression to the middle, and with an `l1` objective it is the *correct*
behaviour for a model that cannot see distance: given (hour, day, origin,
destination) alone, the conditional median of a New York taxi trip is simply not
108 minutes, no matter which cell you are in. The information that would separate
a two-hour trip from a twenty-minute one — how far it actually goes — is
`trip_distance`, which is the meter's driven distance and is refused as
quote-time leakage (`quote_time.EXCLUSIONS`, **F-007(b)**).

**What sits immediately past this band** is characterised in
`docs/rejected_rows_appendix.md`: the 159,300 trips the `duration_above_max` rule
rejects are **85.0% a 23–24 hour meter artefact** and **3.5% a genuine long-haul
population** (52.8% touching an airport). So the 100–120 band is not the edge of
a long tail that continues smoothly — it is the last band before a boundary
whose far side is mostly broken meters. Widening the contract to "fix" the model
would import that artefact into training. **The answer is a distance feature
(M3's dossier), not a wider bound.**

*(Query: `segment = 'duration_band'`; the ceiling figures come from the
`predictions` view directly — `MAX(predicted_minutes)`, and counts of
`predicted_minutes > 60`.)*

---

## 3. The one segment where the `GROUP BY` wins

| segment | trips | KPI-11 | floor MAE | KPI-13 |
|---|---:|---:|---:|---:|
| duration band 1–5 min (test) | 824,986 | 2.2728 | 2.2529 | **−0.88%** |
| duration band 1–5 min (val) | 858,350 | 2.2335 | — | **−0.79%** |

It is the **only** segment above 5,000 trips, on either split, where KPI-13 is
negative — and it holds in both months, which is what makes it a finding rather
than a month. Twelve more segments go negative (9 pickup zones, 3 drop-off
zones) and together they cover **487 test trips**; those are noise and are named
here so nobody rediscovers them as a pattern.

The mechanism is the same regression to the middle seen in §2, from the other
end: on the shortest trips the model **over-quotes by +2.17 minutes on average**
(the floor's median lookup does not). A rider told "6 minutes" for a 3.5-minute
hop is not harmed much — which is exactly why this is worth stating plainly
rather than fixing: **13.9% of all trips sit in a band where the booster is
slightly worse than a lookup table, and the program should know that before M3
claims a general win.**

---

## 4. Where it fails: zones

262 drop-off zones and 260 pickup zones appear in the test split. Ranked by
KPI-11 among zones with ≥20,000 trips:

| pickup zone | trips | KPI-11 | KPI-12 | floor MAE | KPI-13 | bias | mean actual |
|---|---:|---:|---:|---:|---:|---:|---:|
| **264** (*"unknown", not a place*) | 43,808 | **7.1640** | 51.778% | 7.5852 | +5.55% | −2.83 | 14.71 |
| **132** (JFK) | 230,490 | 5.8840 | 59.865% | 6.1146 | +3.77% | −1.38 | 37.64 |
| **138** (LaGuardia) | 167,740 | 5.1728 | 62.826% | 5.3606 | +3.50% | −1.03 | 29.23 |
| 261 | 39,545 | 3.8097 | 75.893% | 4.2100 | +9.51% | −0.44 | 18.80 |
| 88 | 25,496 | 3.6847 | 77.263% | 4.2584 | +13.47% | −0.40 | 18.91 |

Best-served zones for contrast: 263 (2.4649, 88.800%), 238 (2.5588), 239
(2.5786), 262 (2.5806) — all Manhattan-volume zones.

Two separate stories are stacked in that table:

**Airports.** Grouping every trip that touches JFK (132), LaGuardia (138) or
Newark (1) at either end:

| bucket | trips | share | KPI-11 | floor MAE | KPI-12 | mean actual |
|---|---:|---:|---:|---:|---:|---:|
| touches JFK / LGA / EWR | 524,702 | 8.818% | **5.7340** | 5.9685 | **59.988%** | 35.18 |
| no airport | 5,426,006 | 91.182% | 3.0217 | 3.2712 | 83.558% | 12.46 |

Airport trips are 8.8% of the fleet, carry **1.90× the error** and are quoted
within five minutes **24 points less often**. And the floor is nearly as bad
(KPI-13 is only +3.9%), which says this is not a modelling failure so much as a
missing feature: airport runs are long, and length is exactly what feature set v1
cannot see. `RatecodeID = 2` (the JFK flat fare) would identify them instantly
and is refused as quote-time leakage — but the **requested OD pair** is
quote-time knowable, and an airport flag derived from it is already named as an
M3 dossier candidate in `quote_time.EXCLUSIONS`. This memo is that candidate's
evidence.

**Zone 264.** The worst-served pickup zone in New York is not a place. 264 and
265 are the TLC's "unknown" codes (`eda_report.md` §7), and a model asked to
predict from an unknown origin does the only thing it can — it predicts the
average of a bag of unrelated trips. KPI-12 is 51.8% there against 81.5%
fleet-wide. Two consequences worth carrying: at M5 a request that resolves to 264
should be treated as **degraded**, not normal; and 264 is also the largest single
OD "route" in the data (264→264, 409,128 trips, `eda_report.md` §9), so this is
not a rare path.

*(Queries: `segment IN ('pickup_zone','dropoff_zone')`; the airport bucket is one
`CASE` over the `predictions` view — zone ids from `eda_report.md` §10.)*

---

## 5. Where it fails: hours and days

| | best | worst | spread |
|---|---|---|---|
| KPI-11 by hour | 02:00 — **2.2814** | 15:00 — **3.8453** | 1.69× |
| KPI-12 by hour | 02:00 — 91.797% | 17:00 — 75.972% | 15.8 pts |
| KPI-13 by hour | 19:00 — +5.13% | 04:00 — **+16.03%** | — |
| KPI-11 by day | Sunday — 2.8400 | Thursday — **3.5064** | 1.23× |

The error profile follows the traffic exactly: worst through the afternoon
(14:00–17:00, KPI-11 3.77–3.85, and 15:00–17:00 is where KPI-12 bottoms out at
76%), best in the small hours. Thursday is both the busiest day (1,077,039 test
trips) and the worst-served — the EDA already recorded Thursday as slowest and
busiest (`eda_report.md` §5), so this is the model inheriting the city rather
than misbehaving.

The interesting column is **KPI-13**, which runs the *other* way: the booster's
advantage over the floor is largest between 02:00 and 05:00 (+12.6% to +16.0%)
and smallest in the evening peak (+5.1% at 19:00). Those small-hours cells are
the thinnest ones in the lookup table, which is §1's finding again at a different
grain: the booster earns most where the `GROUP BY` has least data, and least
where it has plenty.

*(Queries: `segment IN ('hour','dayofweek')`. Day numbering is pandas'
`dayofweek`: 0 = Monday.)*

---

## 6. Two smaller findings, both real

**The error is asymmetric, and it is asymmetric the wrong way.** On test the
champion over-quotes 54.55% of trips and under-quotes 45.45% — but when it is
early it is early by 2.77 minutes on average and when it is late it is late by
**3.86**. **10.82% of test riders (13.44% on val) are quoted a number at least
five minutes shorter than the truth.** KPI-10 counts both directions equally;
a rider does not. If M5's SLO is written from KPI-10 alone it will be indifferent
to a change that trades early quotes for late ones. **Recommendation to SRE and
MLE: the M5 SLO should carry a one-sided companion** — the share of trips quoted
≥5 minutes short — and this memo's `predictions` view already computes it.

**`passenger_count` null is a segment, not a gap.** 33,014 test trips (0.555%)
carry no stated party size. Their KPI-11 is **6.0719** against 3.2608 fleet-wide
and their KPI-12 is **53.465%**. They are not a random sample: their mean true
duration is **34.4 minutes** (test-split mean **14.459**) and **40.7%** of them are also
unseen-group rows. The floor is catastrophic on them (MAE 14.4918, KPI-13
**+58.10%**), so the model is doing real work here — but "the party size was not
recorded" is evidently correlated with "this is an unusual, long trip", which is
worth knowing before anyone imputes the column. **The mart labels this segment
`(not stated)` rather than leaving it NULL**, because a blank label on a board
reads as a rendering fault instead of a population.

---

## 7. What this memo recommends

| # | To | Recommendation | Evidence |
|---|---|---|---|
| 1 | MLE (M3) | **A quote-time distance substitute is the single highest-value feature**, and the memo's §2 is its business case: zero percent of the longest trips are quoted within five minutes, and the model's ceiling (92 min) sits below the data's (120). | §2 |
| 2 | MLE (M3) | **An airport flag derived from the requested OD pair** — quote-time knowable, unlike `RatecodeID`. 8.8% of trips, 1.90× the error, and the floor is equally bad, so the gap is informational rather than algorithmic. | §4 |
| 3 | MLE (M3) | **Report KPI-13 split by floor coverage in the bake-off.** A contender that improves the aggregate margin by covering more unseen groups has done something different from one that improves accuracy, and today's gate cannot tell them apart. Related to **F-008**. | §1 |
| 4 | SRE (M5) | **Add a one-sided companion to the KPI-10 SLO** (share quoted ≥5 min short: 10.82% test / 13.44% val), and treat requests resolving to zone 264/265 as a **degraded** class (KPI-12 51.8%). | §4, §6 |
| 5 | DA (M7) | **The drift board should segment the same way this memo does** — the segment ids and the mart already exist, so a drift memo comparing KPI-11/KPI-12 month over month costs a query, not a design. | all |

## 8. What this memo cannot say

* **Nothing about `RatecodeID`, `trip_distance` or any money column.** The
  published predictions carry only the five features the model saw, plus the
  actual and the two quotes. That is deliberate — `datasets.load_split` reads
  narrow *because* the columns it does not read are the columns the feature
  registry refuses — so segmenting error by rate code would mean widening a
  read whose narrowness is a safety property. The airport analysis in §4 is done
  on **zone ids**, which the model does see, and reaches the same place.
* **Nothing about trips longer than 120 minutes.** They are outside the
  contract; `docs/rejected_rows_appendix.md` describes them, and the model has
  never been shown one.
* **Nothing causal.** Every number here is a conditional average over a segment
  of one month. "Airport trips are harder" is a description; "the airport flag
  will fix it" is a hypothesis, and M3's ablation is where it becomes a result.
