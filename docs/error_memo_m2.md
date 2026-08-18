# Error memo — where the ETA champion is wrong (M2-S4, role:DA)

**Authored:** 2026-08-17 (M2-S4) · **Owner:** DA · **MLE consulted** on
interpretation · **Subject:** `models:/nyc-taxi-eta@champion` → registry version
**1**, MLflow run `3adee05a855a424bb664c7fea3735703`, feature set v1
(quote-time pure, five features, no distance).

> ### ⚠ READ THIS BEFORE §1: the champion moved on 2026-08-18
>
> **§0–§8 below describe registry version 1 and are the M2 record. They are no
> longer what `make predictions` publishes.** M3-S5's bake-off promoted version
> **2** (`auto-lgbm-v2`, run `92b73bd4f77d4a05b92472bfcfb3cccf`, feature set
> **v2**, 24 features), and the published prediction rows, the mart, the board
> and this memo's twin all describe *that* model now.
>
> **[§9 is the dated M3 section](#9-2026-08-18-the-same-questions-asked-of-the-champion-that-is-actually-served-m3-s5)**
> — same questions, same queries, same order, re-answered against what is
> served. It is the section the twin reproduces; §0–§8's figures are kept
> unedited because a memo that silently rewrites its own numbers cannot be
> compared against the decisions that were made from them.
>
> Two things moved between the two sets of numbers, not one: **the model**
> (v1 → v2) **and the honest floor** (`baseline-group-median` →
> `baseline-group-median-od-fallback`, M3-S1/F-010). §9 keeps them apart
> wherever the difference matters, and says so where it cannot.

**Board:** [Error segments (M2)](http://localhost:3030/dashboard/4) — 11 cards,
defined in `analytics/metabase/boards/error_segments.json` and converged by
`make boards`. The **name** is the address that survives (boards are idempotent
by name, M1-S5); the id was 4 when this memo was written, and would be renumbered
by a `make destroy` and rebuild, so trust the name over the URL.
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

uv run python scripts/error_memo_numbers.py   # reprints EVERY number below
```

That last command is this memo's twin: one section per section here, in this
order, printing the query it ran. A memo full of figures nobody can re-run is a
memo nobody can check — and it earned itself on its first run, catching four
last-digit rounding slips in §4 and §6 that had been typed rather than pasted.

**Since 2026-08-18 the twin reprints §9, not §1–§6.** It reads the published
predictions, and those describe whichever model is `@champion`; the section
numbering is unchanged because §9 asks the same questions in the same order.
`make champion-transition` runs the refresh chain above and prints the twin's
output for whoever owes the next dated section.

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
| touches JFK / LGA / EWR | 524,702 | 8.817% | **5.7340** | 5.9685 | **59.988%** | 35.18 |
| no airport | 5,426,006 | 91.183% | 3.0217 | 3.2712 | 83.558% | 12.45 |

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
**3.85**. **10.82% of test riders (13.44% on val) are quoted a number at least
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

---

## 9. 2026-08-18 — the same questions, asked of the champion that is actually served (M3-S5)

**Subject:** `models:/nyc-taxi-eta@champion` → registry version **2**, MLflow run
`92b73bd4f77d4a05b92472bfcfb3cccf`, contender `auto-lgbm-v2` — feature set **v2**
(24 quote-time features: v1's five, plus M3-S3's `g1` temporal extras and `g2`
zone-centroid geometry), hyperparameters from M3-S4's FLAML scout → Optuna
sniper. Promoted by M3-S5's five-contender bake-off at **KPI-09 3.2403 min ·
KPI-10 81.577%** on the untouched test month — **+3.33%** over the honest floor
and **+0.63%** over version 1.

**Author's note on what this section is not.** It is a *refresh*, not a second
analysis wave: same queries, same order, no new segments (M7 owns the next wave —
M3 kickoff, "Out of scope"). It exists because §0–§8 describe a model nobody
serves any more, and a memo describing an unserved model is exactly the failure
`make verify-m2`'s memo-twin leg is a tripwire for.

**Two things moved, and every comparison below inherits both.** The champion went
v1 → v2, *and* the honest floor went `baseline-group-median` →
`baseline-group-median-od-fallback` (M3-S1, **F-010**: one extra `(PU, DO)`
backoff level before the global median). The published rows carry whichever floor
the serving champion's `gate_floor` tag names, so every `floor MAE` and every
KPI-13 in this section is against the *new*, harder floor. Where a §1–§8 number
changed, the honest answer to "why" is usually "the floor", and it is said each
time rather than implied.

*(Every figure below was printed by `scripts/error_memo_numbers.py` inside
`make champion-transition` step 6, transcript in
`automation/runs/m3s5-transition.log`. Spot-checked against the mart by hand
before being typed here.)*

### 9.0 The rollup still reproduces the evaluator

| split | trips | KPI-11 (mart) | KPI-09 (evaluator) | KPI-12 (mart) | KPI-10 (evaluator) |
|---|---:|---:|---:|---:|---:|
| val (2019-07) | 6,189,748 | 3.3823 | 3.3823 | 80.552% | 80.552% |
| test (2019-08) | 5,950,708 | 3.2403 | 3.2403 | 81.577% | 81.577% |

The dbt test that fails the build unless these four pairs agree (§0) survived a
champion transition without an edit — which is the point of asserting a
*property* rather than a literal.

### 9.1 §1's headline INVERTED, and the model did not do it

| rows | share of test | KPI-11 (model) | floor MAE | KPI-13 | KPI-12 |
|---|---:|---:|---:|---:|---:|
| floor has a real group median | **99.9837%** (5,949,740) | 3.2394 | 3.3474 | **+3.23%** | 81.583% |
| floor falls back to the global median | **0.0163%** (968) | 8.7314 | **29.8623** | **+70.76%** | 43.388% |

Decomposing the 0.1115 min the champion takes off the floor's MAE:

* rows the floor can answer: `0.999837 × (3.3474 − 3.2394)` = **0.1080 min**, or
  **96.9%** of the gap;
* rows it cannot: `0.000163 × (29.8623 − 8.7314)` = **0.0034 min**, or
  **3.1%** of the gap.

*(The two parts sum to 0.1114 against a measured 0.1115 — four-decimal rounding
in the segment MAEs, not a missing population.)*

**At M2 the split was 24.6% / 75.4%; it is now 96.9% / 3.1%.** Three quarters of
the champion's advantage used to be bought on 1.48% of rows; it is now bought
almost entirely on the ordinary 99.98%. **This is F-010 landing, not the model
improving where it used to be weak.** The old floor guessed 11.15 minutes for
every trip whose `(hour, dow, PU, DO)` cell was unseen — 87,989 test rows. The
new floor backs off to `(PU, DO)` first and only 968 test rows fall past that.
The fallback population did not get easier: on those 968 rows the floor is now
wrong by **29.86 minutes** (it was 18.57 on a much larger, easier set), because
what survives two levels of backoff is genuinely strange.

Consequences, restated for the milestones that inherited §1's version:

1. **§1's recommendation to M3 (row 3 of §7 — "report KPI-13 split by floor
   coverage in the bake-off") was answered by making the floor better instead.**
   The bake-off's margins are no longer coverage-dominated: they are 96.9%
   accuracy. That is the honest reading of why M3's headroom is **+2.71%** and
   not M2's +7.07% (M3-S1, DR-06).
2. **M5's "one request in 68 is in the naive-answer regime" is now one in
   6,148.** The serving-shaped number changed by two orders of magnitude and the
   parity/SLO work should use the new one.
3. **The 968 rows are still worth a degraded class**, precisely because the floor
   is *worse* on them than it ever was on the old 1.48%.

### 9.2 The ceiling lifted, and it is still a ceiling

| actual duration | trips | share | KPI-11 | KPI-12 | KPI-13 | mean actual | mean quoted |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1–5 min | 824,986 | 13.864% | 2.2532 | 92.531% | **−0.19%** | 3.55 | 5.70 |
| 5–10 min | 1,754,599 | 29.486% | 2.0204 | 93.651% | +0.44% | 7.45 | 8.38 |
| 10–20 min | 2,106,266 | 35.395% | 2.9649 | 82.384% | +2.50% | 14.19 | 13.89 |
| 20–30 min | 747,431 | 12.560% | 4.5533 | 64.691% | +5.70% | 24.11 | 22.46 |
| 30–45 min | 347,541 | 5.840% | 6.6312 | 49.605% | +6.48% | 36.00 | 32.86 |
| 45–60 min | 121,577 | 2.043% | 9.2142 | 37.607% | +6.25% | 51.21 | 46.39 |
| 60–100 min | 47,338 | 0.796% | 15.8268 | 23.182% | +6.23% | 69.47 | 56.02 |
| **100–120 min** | **970** | 0.016% | **57.7729** | **0.103%** | +2.00% | 107.92 | **50.15** |

The sharpest sentence in this memo needs one word changed. §2 said the champion
quotes **none** of the 970 longest trips within five minutes. Version 2 quotes
**one** — KPI-12 0.103% is a single trip — and its best quote in that band is
**4.459 minutes** out, against version 1's 9.7. Every other row improves modestly
and in the same direction.

The mechanism is unchanged, and the whole-split evidence says so:

* the highest number the champion ever predicts on test is **97.105 minutes**
  (was 92.155), against a maximum truth of 120.0 (val: 98.237 vs 119.967);
* it quotes above 60 minutes for **34,814** test trips (0.585%, was 28,083) while
  **48,097** (0.808%) actually run past 60;
* of the trips that really do exceed 60 minutes, **43.07%** now get a quote above
  60 at all (was 36.86%).

**The zone-centroid straight-line distance (`g2`) is doing exactly what M3-S2's
DR-04 predicted, and no more.** It keeps 97.6% of the forbidden meter distance's
correlation with the target, and it bought roughly five minutes of ceiling and
six points of long-trip reach — real, and nowhere near enough to quote a
two-hour trip. §7 row 1's recommendation is therefore **partially discharged, not
closed**: the distance substitute landed, and 0.103% is still not a number
anybody would ship an SLO against. The remaining gap is the difference between a
straight line between two zone centroids and a route through traffic, which is
the M9 OSRM stretch (`docs/prior_art.md`; the companion dataset is 404, our own
263×263 matrix is the only reachable version).

### 9.3 The `GROUP BY` still wins on short trips — on one month now, not two

| segment | trips | KPI-11 | floor MAE | KPI-13 |
|---|---:|---:|---:|---:|
| duration band 1–5 min (test) | 824,986 | 2.2532 | 2.2490 | **−0.19%** |

It is still the **only** segment above 5,000 trips where KPI-13 is negative — but
it is now negative on **test only**. The val row that made this "a finding rather
than a month" at M2 (−0.79%) no longer clears zero, and the test deficit shrank
from −0.88% to −0.19%: about **0.004 min**, roughly a quarter of a second. The
small negatives thinned too: **7 segments covering 139 test trips** (5 pickup
zones, 2 drop-off zones) against M2's 12 segments and 487 trips.

**Honest reading: this finding is weakening, and it is not yet gone.** The
over-quote on short trips is still there — mean quoted 5.70 against mean actual
3.55, **+2.15 min** (v1: +2.17) — so the mechanism §3 described has not changed;
the model simply got a little better at the band while the floor got better too.
It is one month from being noise, and M7's drift memo is where that gets settled.
Nothing should be built on it in between.

### 9.4 Zones: same ranking, same two stories, uniformly smaller errors

| pickup zone | trips | KPI-11 | KPI-12 | floor MAE | KPI-13 | bias | mean actual |
|---|---:|---:|---:|---:|---:|---:|---:|
| **264** (*"unknown", not a place*) | 43,808 | **7.1581** | 51.612% | 7.4131 | +3.44% | −2.79 | 14.71 |
| **132** (JFK) | 230,490 | 5.8937 | 59.895% | 6.0494 | +2.57% | −1.04 | 37.64 |
| **138** (LaGuardia) | 167,740 | 5.1375 | 63.093% | 5.2862 | +2.81% | −0.78 | 29.23 |
| 261 | 39,545 | 3.7829 | 75.802% | 3.9879 | +5.14% | −0.26 | 18.80 |
| 88 | 25,496 | 3.6382 | 77.608% | 3.9038 | +6.80% | −0.26 | 18.91 |

Best-served for contrast: 263 (2.4666, 88.611%), 238 (2.5602), 262 (2.5690), 239
(2.5874). 262 drop-off zones and 260 pickup zones appear in test, unchanged.

**Airports:**

| bucket | trips | share | KPI-11 | floor MAE | KPI-12 | mean actual |
|---|---:|---:|---:|---:|---:|---:|
| touches JFK / LGA / EWR | 524,702 | 8.817% | **5.7224** | 5.8815 | **60.022%** | 35.18 |
| no airport | 5,426,006 | 91.183% | 3.0003 | 3.1071 | 83.662% | 12.45 |

**§4's headline survives version 2 almost exactly: 1.91× the error (was 1.90×)
and 23.6 points less often within five minutes (was 24).** The airport gap is the
one §4 finding v2 did *not* move, and that is informative — v2's new features
include the OD geometry that §4 said would "identify them instantly", and the
gap held. Two readings, and this memo cannot choose between them: either the
straight-line distance already carries what an explicit airport flag would add,
or the airport penalty is about *traffic and terminal dwell* rather than
*distance*, in which case the flag is still owed and M7's dossier should say so.
**§7 row 2 stays open**, with this as its new evidence.

Zone 264 is still the worst-served pickup "zone" in New York — KPI-12 **51.6%**
against 81.6% fleet-wide — and M3-S2's decision to give 264/265 **no centroid
row** is why v2 helped it least: the model's newest features are, for those
trips, a named and tested fallback rather than a measurement. §4's advice to M5
stands unchanged and is now better founded: **treat a request resolving to
264/265 as degraded.**

### 9.5 Hours and days: the shape is the city's, and the city did not change

| | best | worst | spread |
|---|---|---|---|
| KPI-11 by hour | 02:00 — **2.2556** | 15:00 — **3.8612** | 1.71× |
| KPI-12 by hour | 02:00 — 91.922% | 15:00 — 75.475% | 16.4 pts |
| KPI-13 by hour | 09:00 — +2.22% | 04:00 — **+14.76%** | — |
| KPI-11 by day | Sunday — 2.7988 | Thursday — **3.4911** | 1.25× |

Everything §5 said still holds: worst through the afternoon, best in the small
hours, Thursday both busiest (1,077,039 test trips) and worst-served. The one
number worth re-reading is **KPI-13 at 04:00 — +14.76%, against +16.03% at M2**,
while the evening trough moved from +5.13% to **+2.22%**. The booster still earns
most where the lookup table is thinnest, but the whole curve compressed, because
the new floor has a second backoff level exactly where the old one was thinnest.
**§5's mechanism is intact and its magnitudes are floor-dependent** — a useful
warning for M7, which will compare these numbers across months and must compare
them against the same floor to mean anything.

### 9.6 The asymmetry is smaller and still the wrong way

On test version 2 over-quotes **55.23%** of trips and under-quotes 44.77%; when
early it is early by **2.81** minutes and when late it is late by **3.77**.
**10.34% of test riders (13.22% on val) are still quoted a number at least five
minutes shorter than the truth** — down from 10.82% / 13.44%, an improvement of
roughly half a point that leaves the finding entirely intact. **§7 row 4's
recommendation to SRE is unchanged: the M5 SLO needs a one-sided companion**,
because KPI-10 counts both directions equally and a rider does not.

**`passenger_count` not stated** — 33,014 test trips (0.555%), KPI-11 **5.8570**
(was 6.0719) against 3.2403 fleet-wide, KPI-12 **55.549%**, mean true duration
**34.41** minutes against the split's 14.459. Still a population, not a gap. One
number changed enormously and it is the floor's doing again: **1.29%** of them
are also unseen-group rows, against §6's 40.7%. The old floor had never seen
their `(hour, dow, PU, DO)` cell; the new one nearly always has their `(PU, DO)`.
Its MAE on them is 7.8558 and KPI-13 is +25.44% (was +58.10%) — the model is
still doing real work here, just less of it relative to a floor that improved.

### 9.7 What changed in §7's recommendations

| # | To | Status after v2 |
|---|---|---|
| 1 | MLE (M3) | **Partially discharged.** The quote-time distance substitute (`g2`, zone-centroid haversine) landed and is in the served model; the ceiling moved 92.155 → 97.105 min and long-trip reach 36.86% → 43.07%. KPI-12 in the 100–120 band went 0.000% → 0.103%. Still the sharpest failure in the set; the remainder is routing, i.e. the M9 OSRM stretch. |
| 2 | MLE (M3) | **Open, with new evidence.** v2 has the OD geometry and the airport gap held at 1.91×. Either the geometry already carries it or the penalty is not distance-shaped — §9.4. |
| 3 | MLE (M3) | **Answered differently than asked.** Rather than splitting the bake-off's KPI-13 by floor coverage, M3-S1 made the floor cover the rows (F-010). Coverage now explains 3.1% of the margin instead of 75.4%. |
| 4 | SRE (M5) | **Unchanged and still owed** — 10.34% test / 13.22% val quoted ≥5 min short; zones 264/265 degraded at KPI-12 51.6%. |
| 5 | DA (M7) | **Unchanged, and §9.5 adds a condition**: a month-over-month KPI-11/KPI-13 comparison is only meaningful against the same floor. The floor's name travels on the champion's `gate_floor` tag; the drift memo should cite it. |

### 9.8 What this section still cannot say

Everything in §8 applies unchanged — no rate code, no distance, no money column,
nothing about trips past 120 minutes, nothing causal. One addition specific to
v2: **it cannot attribute any of these deltas to tuning versus features.** The
served model is `auto-on-v2`, which is both v2's feature set *and* the Optuna
sniper's hyperparameters, and the bake-off measured that pairing as **+0.63%**
over v1 of which **+0.56%** was features alone (`docs/bakeoff_m3.md` §5). Every
improvement in this section is therefore overwhelmingly a *feature* result, but
this memo's queries cannot separate them and did not try.
