# EDA report — NYC yellow taxi, 2019-01…08 (M1-S3, role:DA)

**Read date:** 2026-08-16 · **Analyst block:** DA (MLE consulted on the modelling
verdicts) · **Every number below came from a named DuckDB view**, via
`python -m taxi_mlops.data query "<SQL>"`. No raw parquet was opened by this
report — the DA charter refuses it, and the analyst layer exists so that two
people cannot spell a glob two ways and get two truths.

Views cited: `trips_clean`, `trips_train`, `trips_val`, `trips_test`,
`data_health`, `ingest_months`, `ingest_rejections`, `unknown_domain_values`.
Rebuild them with `make duckdb` (seconds; they are views, they copy nothing).

**Appendix R** (`docs/rejected_rows_appendix.md`, M2-S1) describes the 1.603%
this report does not: the rejected rows, retained since M2-S1 and published as
`trips_rejected`. It answers E-11 / F-005.

---

## 0. The window this report describes — stated first, because it is not the whole data

Everything below describes **56,127,878 rows: the 98.397% of TLC 2019-01…08 that
survived the M1-S1 contract**. It does not describe the 914,459 rows the ingest
rejected, because nothing on disk retains them (finding **F-005**, open, owner
DE). This is not a footnote — it is the boundary of every claim in this
document. Where a rejection rule could plausibly have removed a *population*
rather than *noise*, the section says so explicitly.

| | rows | share |
|---|---|---|
| TLC delivered (`ingest_months.rows_in`) | 57,042,337 | 100% |
| survived the contract (`trips_clean`) | 56,127,878 | 98.397% |
| rejected, counted only (`ingest_rejections`) | 914,459 | 1.603% |

**Splits are months, and months are not interchangeable** (§4 shows why):

| split | months | rows |
|---|---|---|
| train | 2019-01…06 | 43,987,422 |
| val | 2019-07 | 6,189,748 |
| test | 2019-08 | 5,950,708 |

---

## 1. Volume and data health, by month

`SELECT split, month, rows_in, rows_out, rows_rejected, rejected_pct FROM data_health ORDER BY month`

| split | month | rows_in | rows_out | rejected | rejected % |
|---|---|---|---|---|---|
| train | 2019-01 | 7,696,617 | 7,584,656 | 111,961 | 1.455 |
| train | 2019-02 | 7,049,370 | 6,947,080 | 102,290 | 1.451 |
| train | 2019-03 | 7,866,620 | 7,753,921 | 112,699 | 1.433 |
| train | 2019-04 | 7,475,949 | 7,369,167 | 106,782 | 1.428 |
| train | 2019-05 | 7,598,445 | 7,481,898 | 116,547 | 1.534 |
| train | 2019-06 | 6,971,560 | 6,850,700 | 120,860 | 1.734 |
| val | 2019-07 | 6,310,419 | 6,189,748 | 120,671 | 1.912 |
| test | 2019-08 | 6,073,357 | 5,950,708 | 122,649 | 2.020 |

**The rejection rate is not flat — it rises monotonically from 1.428% (April) to
2.020% (August), a 41% relative increase across the eight months.** The absolute
count of rejected rows *rises* (106,782 → 122,649) while the total volume *falls*
(7.48M → 6.07M). Whatever is being rejected is growing in both share and count as
volume shrinks. That is a trend, not a constant, and the val/test months sit at
the top of it — so the held-out months are the *dirtiest* months, which flatters
nothing and is worth knowing before M2 reads a metric off them.

Actionable consequence: **`max_rejected_fraction: 0.10` is not a live guard at
this trajectory** (we are at one fifth of it), but the data-health board
(M1-S5) should plot the rate as a *series*, not a current value. A threshold
alarm at 10% would not have noticed anything described in this paragraph.

## 2. What the contract rejected, by rule

`SELECT rule, SUM(rejected_by), SUM(matched) FROM ingest_rejections GROUP BY rule ORDER BY 2 DESC`

| rule | rejected_by (attributed) | matched (independent) |
|---|---|---|
| duration_below_min | 512,388 | 569,710 |
| duration_above_max | 159,300 | 159,300 |
| distance_non_positive | 117,932 | 465,911 |
| fare_negative | 64,284 | 96,308 |
| duration_non_positive | 57,322 | 57,322 |
| pickup_outside_month | 3,182 | 3,688 |
| distance_above_max | 51 | 238 |
| missing_timestamp | 0 | 0 |
| passenger_count_out_of_range | 0 | 0 |
| location_out_of_range | 0 | 0 |

Reading the two columns together is the whole point. `distance_non_positive` is
attributed 117,932 drops but *matches* 465,911 rows — **three quarters of the
zero-distance trips were already gone**, removed by an earlier duration rule.
A single-column report would have shown this rule shrinking and someone would
eventually have concluded that zero-distance trips were getting rarer.

**Three rules have never fired: `missing_timestamp`, `location_out_of_range`,
`passenger_count_out_of_range` — 0 attributed AND 0 matched across 57M rows.**
The DA reads this as a live, useful fact rather than dead code: the contract's
`nullable: false` on the timestamps and the `min/max` on PU/DO are *upstream*
guarantees TLC is currently honouring. They are the rules whose first non-zero
count is a genuine event. The data-health board should show them at zero rather
than omit them (an omitted rule cannot be seen to start firing).

**F-005 bites hardest here.** `duration_above_max` removes 159,300 trips over
120 minutes, and no artifact can say whether those are meter faults or a real
long-haul population. §5 shows that trips of 60–120 minutes are 0.88% of the
data and are overwhelmingly airport-rate trips; whether the >120 tail is the
same population continued, or a different phenomenon entirely, **this report
cannot answer and does not guess.**

> **ANSWERED 2026-08-17 by M2-S1 — see `docs/rejected_rows_appendix.md`.** The
> rejected rows are now retained (`data/rejected/`, DVC-pinned) and queryable as
> the `trips_rejected` view, and the answer is *both, in a ratio of 24 to 1*:
> **85.0%** of the 159,300 are a normal short trip (median 2.19 mi, $12.00)
> whose clock ran 23–24 hours and stopped the next day at the same time of day —
> a session artefact, correctly rejected. **3.5% (5,601 trips)** in the 120–180
> minute band are genuine long-haul: 52.8% touch an airport, 66.0% run ≥ 10
> miles, and 32.87% carry an out-of-city rate code against 2.7497% of the clean
> data. The paragraph above stands as written — it was the honest thing to say
> with the artifacts that existed then; this note is what changed.

## 3. The target: `trip_duration_minutes`

`SELECT split, COUNT(*), AVG, STDDEV_SAMP, MIN, quantiles, MAX FROM trips_clean GROUP BY split`

| split | rows | mean | sd | min | p05 | p25 | p50 | p75 | p95 | p99 | max |
|---|---|---|---|---|---|---|---|---|---|---|---|
| train | 43,987,422 | 14.3697 | 11.4741 | 1.00 | 3.20 | 6.70 | 11.1500 | 18.2667 | 36.80 | 58.4333 | 120.00 |
| val | 6,189,748 | 14.7090 | 11.6703 | 1.00 | 3.25 | 6.8667 | 11.4167 | 18.7167 | 38.00 | 58.95 | 119.9667 |
| test | 5,950,708 | 14.4590 | 11.3728 | 1.00 | 3.25 | 6.85 | 11.2833 | 18.3167 | 37.2667 | 57.6833 | 120.00 |

The min of exactly 1.00 and max of exactly 120.00 are the cleaning window's
edges (`duration_below_min: 1.0`, `duration_above_max: 120.0`), not properties
of taxis. **Any distributional statement about the target's tails is a statement
about our window.** This is stated here once and assumed everywhere after.

**Our window is not the public one.** The MLOps Zoomcamp's reference notebook —
the closest thing this problem has to a public benchmark — filters with
`df[(df.duration >= 1) & (df.duration <= 60)]` (read live 2026-08-16,
`01-intro/duration-prediction.ipynb`; see `docs/prior_art.md` row 10). Ours keeps
1–120 minutes, so **our data includes 493,876 trips theirs discards** (0.8799% of
rows, the 60–120 minute band) — and those are the longest, hardest, most
airport-heavy trips (§5). Any comparison of our MAE against a published Zoomcamp
number is invalid unless the windows are matched first. Recorded here so nobody
makes that comparison casually in M2.

**Shape** (`SKEWNESS`, `KURTOSIS` over `trips_clean`):

| statistic | raw target | log(target) |
|---|---|---|
| skewness | **2.1857** | **−0.0892** |
| kurtosis | 7.0892 | — |

The raw target is strongly right-skewed with heavy tails; **`ln(duration)` is
essentially symmetric (skew −0.089).** This is the single most actionable
modelling fact in the report, and it is handed to the MLE as an observation, not
a decision: a squared-error objective on the raw target will spend its capacity
on the long right tail, and the log transform costs one line. (M2 owns the
choice and must prove it against the gate; scout numbers stay scout-internal,
gotcha #15.)

**Tail mass**: 0.8799% of trips exceed 60 minutes; 12,462 exceed 100 minutes;
677,351 are under 2 minutes (1.21% — these survived the 1-minute floor and are
real, very short, mostly intra-Midtown hops, §6).

## 4. The months are not exchangeable — a drift signal inside the training set

`SELECT month, AVG(trip_duration_minutes), MEDIAN, QUANTILE_CONT(0.9), AVG(trip_distance), AVG(dist)/AVG(dur)*60 FROM trips_clean GROUP BY month`

| month | mean min | p50 min | p90 min | mean miles | p50 miles | mph (of means) |
|---|---|---|---|---|---|---|
| 2019-01 | 13.0326 | 10.2667 | 25.50 | 2.8538 | 1.56 | 13.138 |
| 2019-02 | 13.8843 | 10.90 | 27.20 | 2.9422 | 1.60 | 12.715 |
| 2019-03 | 14.3494 | 11.15 | 28.3167 | 3.0479 | 1.65 | 12.744 |
| 2019-04 | 14.5711 | 11.3667 | 28.6167 | 3.0635 | 1.68 | 12.615 |
| 2019-05 | 15.1602 | 11.6167 | 30.00 | 3.0901 | 1.69 | 12.230 |
| 2019-06 | 15.2851 | 11.7333 | 30.1333 | 3.1352 | 1.70 | 12.307 |
| 2019-07 | 14.7090 | 11.4167 | 29.00 | 3.1469 | 1.70 | 12.837 |
| 2019-08 | 14.4590 | 11.2833 | 28.2833 | 3.2027 | 1.71 | 13.290 |

**Mean trip duration rises 17.3% from January to June (13.03 → 15.29 min), then
falls in July and August.** Median tracks it. Meanwhile mean distance rises
*monotonically all eight months* (2.85 → 3.20 mi) — so the summer decline in
duration is not shorter trips, it is **faster ones**: effective speed bottoms out
in May (12.23 mph) and recovers to 13.29 mph by August, the fastest month after
January.

This matters more than it looks:

1. **The train/val/test split is a time split across a non-stationary series.**
   A model fit on Jan–Jun sees a target whose mean is *rising* through the
   training window and is asked to predict July and August, which are *falling*.
   The train mean (14.3697) happens to sit close to the val mean (14.7090) — a
   2.4% gap — but that closeness is a coincidence of averaging a rising series,
   not evidence of stability. **M2 should not read the small train↔val gap as
   "no drift".**
2. **A month feature would be actively harmful.** `month` is in `trips_clean` as
   a split label; any feature derived from it cannot generalise past 2019-08 and
   would encode exactly the trend above. Named here so M2/M3 do not have to
   rediscover it.
3. **This is the drift the M7 loop should be able to see.** A seasonal signal of
   this size, present in the *training* data, is a free realism check for the
   drift detector before any synthetic drift is injected.

## 5. Rate codes: 2.5% of trips carry 3.5× the duration

`SELECT RatecodeID, COUNT(*), pct, AVG(dur), MEDIAN(dur), AVG(dist) FROM trips_clean GROUP BY 1`

| RatecodeID | trips | % | mean min | p50 min | mean miles |
|---|---|---|---|---|---|
| 1 (standard) | 54,138,112 | 96.4549 | 13.36 | 10.85 | 2.57 |
| 2 (JFK flat) | 1,388,075 | 2.4731 | **46.12** | 44.60 | 17.63 |
| NULL | 261,781 | 0.4664 | 35.81 | 33.00 | 10.52 |
| 5 (negotiated) | 183,610 | 0.3271 | 34.87 | 32.32 | 12.21 |
| 3 (Newark) | 111,638 | 0.1989 | 41.36 | 38.05 | 17.67 |
| 4 (Nassau/Westchester) | 43,651 | 0.0778 | 38.10 | 34.85 | 19.35 |
| 99 (**undocumented**) | 949 | 0.0017 | 12.86 | 10.35 | 2.08 |
| 6 (group ride) | 62 | 0.0001 | 12.31 | 6.25 | 2.89 |

**RatecodeID is the highest-leverage low-cardinality feature in the dataset.**
Standard-rate trips average 13.4 minutes; JFK flat-fare trips average 46.1 — and
they are 2.47% of all trips, i.e. 1.39M rows, far too many to treat as outliers.
Newark and Nassau/Westchester behave the same way. A model without this column
must infer "this is an airport run" from distance and zone, which it can do, but
the column states it directly.

Two cautions the MLE should have:

- **RatecodeID 99 is undocumented and behaves like standard rate** (12.86 min
  mean vs 13.36 for code 1). 949 rows in 8 months. It is in
  `unknown_domain_values` for exactly this reason. It is not worth a rule; it is
  worth not being surprised by.
- **The NULL rate code is not missing data, it is a batch** — see §7.

## 6. Time-of-day and day-of-week structure

Hour of pickup (`EXTRACT(hour FROM tpep_pickup_datetime)` over `trips_clean`), selected rows:

| hour | trips | mean min | p50 min | mean miles | mph |
|---|---|---|---|---|---|
| 02 | 789,566 | 11.350 | 9.517 | 3.257 | 17.22 |
| 05 | 520,350 | 12.353 | 8.583 | 4.880 | **23.70** |
| 08 | 2,592,453 | 14.403 | 11.233 | 2.759 | 11.49 |
| 09 | 2,633,997 | 14.632 | 11.733 | 2.687 | 11.02 |
| 14 | 3,115,825 | 16.182 | 12.117 | 3.085 | 11.44 |
| 15 | 3,129,288 | 16.637 | 12.117 | 3.061 | 11.04 |
| 16 | 2,954,514 | **16.798** | 11.933 | 3.133 | 11.19 |
| 17 | 3,340,628 | 16.136 | 11.967 | 2.949 | **10.97** |
| 18 | 3,696,192 | 14.556 | 11.433 | 2.739 | 11.29 |
| 23 | 2,305,528 | 13.434 | 10.917 | 3.486 | 15.57 |

Day of week:

| day | trips | mean min | p50 min | mph |
|---|---|---|---|---|
| Sunday | 6,732,195 | 13.049 | 10.067 | 15.34 |
| Monday | 7,198,063 | 14.117 | 10.750 | 13.56 |
| Tuesday | 8,217,141 | 14.499 | 11.400 | 12.36 |
| Wednesday | 8,565,757 | 14.977 | 11.717 | 11.89 |
| Thursday | 8,809,970 | **15.492** | 11.983 | **11.66** |
| Friday | 8,634,463 | 15.017 | 11.567 | 12.07 |
| Saturday | 7,970,289 | 13.316 | 10.650 | 13.23 |

**Effective speed varies by a factor of 2.16 across the day** (23.70 mph at 05:00
vs 10.97 mph at 17:00). Peak *volume* (18:00, 3.70M trips) and peak *duration*
(16:00, 16.80 min) are two hours apart — the busiest hour is not the slowest one.
Thursday is both the slowest and the highest-volume day; the weekend is 1.5–2.4
minutes faster than midweek at similar distances.

**Note the divergence between mean and median in the afternoon**: at 14:00–15:00
the mean is 16.2–16.6 min while the median is flat at 12.12. The afternoon does
not slow *every* trip down; it lengthens the tail. A model evaluated only on MAE
will be scored mostly on the median behaviour and can be quietly bad in exactly
the hours that generate complaints — which is why KPI-10 (within-tolerance rate)
exists alongside KPI-09 (MAE) in the KPI doc.

## 7. Missingness — and one column that is a rollout, not a defect

`SELECT COUNT(*), SUM(CASE WHEN <col> IS NULL ...) FROM trips_clean`

| column | null rows | % of 56,127,878 |
|---|---|---|
| VendorID, payment_type, fare_amount, trip_distance, PU/DOLocationID, both timestamps | **0** | 0 |
| passenger_count | 261,781 | 0.4664 |
| RatecodeID | 261,781 | 0.4664 |
| store_and_fwd_flag | 261,781 | 0.4664 |
| congestion_surcharge | **5,046,505** | **8.99** |
| airport_fee | **56,127,878** | **100.00** |

### 7a. The 261,781-row null batch (three columns, identical count)

Confirmed at the M1-S2 Data Contract Review and re-confirmed here: exactly
261,781 rows have `passenger_count`, `RatecodeID` and `store_and_fwd_flag` all
null **and** `payment_type = 0`, with zero exceptions, in all 8 months. It is
two vendors: VendorID 2 contributes 261,562 and **VendorID 5 contributes 219 —
which is every trip VendorID 5 has in 56M rows.**

These rows are *not* average: mean duration 35.81 min against 13.36 for standard
rate. Dropping them would silently remove a long-trip population; imputing
`passenger_count` for them would invent data for the group least like the rest.
**Recommended treatment for M2: an explicit `is_null_batch` indicator, not
imputation** — the missingness is the signal, and it is perfectly correlated
with `payment_type = 0`, which on any board reads as a payment *category*.

### 7b. `congestion_surcharge` — 63.46% null in January only, and it is a cutover

Per-month null rate: **2019-01 = 63.4565%**, every other month 0.42–0.56% (i.e.
identical to the null batch above). Per-day within January:

| pickup date | rows | % null congestion_surcharge |
|---|---|---|
| 2019-01-17 | 280,709 | 100.000 |
| 2019-01-18 | 263,042 | 99.980 |
| 2019-01-19 | 232,836 | 99.998 |
| 2019-01-20 | 199,811 | 99.822 |
| **2019-01-21** | **189,316** | **1.118** |
| 2019-01-22 | 251,494 | 1.406 |
| 2019-01-31 | 280,512 | 0.311 |

**The column is switched on between 2019-01-20 and 2019-01-21 — a cliff from
99.8% null to 1.1% null in one day**, then settles. The regulatory reason is not
established by this report and is not needed: the modelling consequence is fixed
either way.

**This is a trap with a name.** A feature built on `congestion_surcharge`, or
any imputation of it fitted on the training set, learns "January" — because 20 of
the 31 January days are structurally null and no other month is. It would look
harmless in training (train is 6 months, only one contaminated) and would be
untestable in val/test (July and August are clean). **Recommendation to M2:
either exclude `congestion_surcharge` or restrict training to 2019-02 onward,
and state which; do not impute it.** This is the same failure family as gotcha
#31 (drift by column) and the DCR's drift-by-value: here it is *drift by
availability*, and it is inside the training window.

### 7c. `airport_fee` — the column exists and contains nothing

`SELECT COUNT(airport_fee), COUNT(DISTINCT airport_fee) FROM trips_clean GROUP BY split` returns
**0 and 0 for all three splits.** All 56,127,878 rows are null. The contract
already knows this (`from_year: 2021`), but a reader of the schema alone would
see a plausible airport-fee feature and reach for it. It carries zero
information in this window; §5's RatecodeID 2/3 is the actual airport signal.

## 8. Money columns are outlier-poisoned — the number that settles AI-2

DCR-03 was answered at M1-S2 with "12 rows move the mean by 0.26%". Here is the
sharper version, and it is the strongest argument in this report for defining
every money KPI with a window:

| statistic over `trips_clean` | value |
|---|---|
| `CORR(fare_amount, trip_duration_minutes)` — all rows | **0.0735** |
| `CORR(fare_amount, trip_duration_minutes)` — rows with `fare_amount BETWEEN 0 AND 200` | **0.8708** |
| rows excluded by that window | **3,131** of 56,127,878 (**0.0056%**) |
| mean fare of those 3,131 rows | 869.13 |
| max fare | 671,123.14 |

**Removing 1 row in every 17,927 moves the fare↔duration correlation from 0.07 to
0.87 — a factor of 11.8.** Un-windowed, the relationship between fare and
duration is invisible; windowed, it is one of the strongest in the data. Any
dashboard card, KPI, or feature-importance readout computed over raw
`fare_amount` is not merely imprecise, it is *inverted in meaning*.

Per-split extremes (`fare_amount`, `total_amount`, `trip_distance`):

| split | fare p50 | fare p99 | fare p99.9 | fare max | total max | distance max |
|---|---|---|---|---|---|---|
| train | 9.50 | 52.00 | 84.00 | 671,123.14 | 671,124.94 | 99.07 |
| val | 9.50 | 52.00 | 91.50 | 6,666.65 | 6,667.45 | 97.70 |
| test | 9.50 | 52.00 | 93.00 | 411,042.01 | 411,042.81 | 97.29 |

The median is identical to the cent across all three splits (9.50) while the
maxima differ by two orders of magnitude between them. **Action AI-2 is
discharged in `docs/kpi_definitions.md`: KPI-08 states its window and outlier
treatment in its own definition, and no money KPI in that document is defined
without one.**

**Leakage warning, handed to the MLE.** `fare_amount`, `tip_amount`,
`tolls_amount`, `total_amount`, `payment_type` and `store_and_fwd_flag` are all
recorded **at or after trip end**. They are not available when an ETA is quoted.
Their correlation with the target (0.87 windowed) is precisely what makes them
dangerous: a model using them would score beautifully offline and be
unimplementable at M5's serving boundary. The features available at quote time
are: pickup timestamp, PU/DO zone, passenger count, RatecodeID (known at hail),
and — if and only if a distance estimate exists at quote time — `trip_distance`.
**`trip_distance` itself deserves scrutiny at M3: the TLC value is the *meter's
recorded* distance, i.e. the distance actually driven, which a quote-time system
does not have.** That is the dossier's question (M3 owns OSRM / zone-centroid
distances); this report only flags that the strongest numeric predictor
(§9) may not be honestly available.

## 9. What predicts the target

`SELECT CORR(...) FROM trips_clean`

| pair | Pearson r |
|---|---|
| trip_distance ↔ trip_duration_minutes | **0.8066** |
| ln(trip_distance) ↔ ln(trip_duration_minutes) | **0.8464** |
| fare_amount ↔ trip_duration_minutes (raw) | 0.0735 |
| total_amount ↔ trip_duration_minutes (raw) | 0.0885 |

Distance is the dominant single predictor and the relationship is *more* linear
in logs (0.8066 → 0.8464), consistent with §3's finding that the log target is
symmetric. See §8 for why the fare rows are what they are.

**Zone cardinality**: 263 distinct pickup zones, 263 dropoff zones, **48,634
distinct OD pairs observed**. That is a large but tractable categorical space —
and it is not uniformly populated:

| PU → DO | trips | mean min | sd min | mean miles |
|---|---|---|---|---|
| **264 → 264** | **409,128** | 13.34 | 10.41 | 2.75 |
| 237 → 236 | 340,730 | 6.49 | 3.26 | 1.06 |
| 236 → 237 | 290,050 | 7.69 | 3.98 | 1.06 |
| 236 → 236 | 282,492 | 4.41 | 3.50 | 0.63 |
| 237 → 237 | 270,054 | 5.19 | 3.87 | 0.67 |
| 239 → 238 | 156,194 | 4.83 | 2.38 | 0.84 |

**The single most common "route" in the dataset is not a route.** Zone 264 is
TLC's *unknown* zone: it appears as pickup on 512,436 trips and zone 265 (also
unknown/outside-NYC) on 11,958 more — 524,394 trips, 0.93% of the data, whose
origin is not a place. Its duration standard deviation (10.41 min) is triple that
of the genuine top pairs (2.4–4.0 min), which is what you would expect from a
bucket containing everything rather than one corridor. **M2 must treat 264/265 as
a distinct "unknown" category, never as a zone with a location.**

**Unseen categories at inference** — the cold-start question, asked before M5
rather than after:

| split | rows | OD pairs never seen in train | % |
|---|---|---|---|
| val (2019-07) | 6,189,748 | 1,157 | 0.0187 |
| test (2019-08) | 5,950,708 | 968 | 0.0163 |

Small, but **not zero and never will be** — 48,634 observed pairs out of 263² =
69,169 possible means a third of the space has never occurred. Any OD-pair
encoding needs an explicit unseen bucket; a model that raises on an unknown
category will raise roughly 1 request in 5,400 in production, which is far too
often for an exception path nobody wrote.

## 10. Categorical distributions, for completeness

`payment_type` over `trips_clean`:

| payment_type | trips | % | mean min |
|---|---|---|---|
| 1 (credit card) | 40,415,494 | 72.0061 | 14.55 |
| 2 (cash) | 15,194,808 | 27.0718 | 13.69 |
| **0 (undocumented)** | 261,781 | 0.4664 | **35.81** |
| 3 (no charge) | 193,039 | 0.3439 | 14.72 |
| 4 (dispute) | 62,756 | 0.1118 | 15.11 |

`payment_type = 0` is the null batch of §7a wearing a category's clothes — and
its mean duration (35.81 min) is 2.6× the credit-card mean, so it will move any
board that segments by payment method.

Values the TLC dictionary does not describe (`unknown_domain_values`, all 8 months each):

| column | value | rows |
|---|---|---|
| VendorID | 4 | 264,661 |
| payment_type | 0 | 261,781 |
| RatecodeID | 99 | 949 |
| VendorID | 5 | 219 |

## 11. A reference floor for M2 — SQL statistics, **not model results**

Computed entirely in SQL over the analyst views. **These are EDA reference
statistics, not model metrics.** Gotcha #15 governs: reported model numbers come
from `taxi_mlops.training.evaluate` and nowhere else, and nothing below may be
quoted as a model result.

Fitted on `trips_train` only, evaluated on `trips_val` / `trips_test`:

| predictor | val MAE (min) | test MAE (min) |
|---|---|---|
| constant = train median (11.15) | **7.8866** | 7.6667 |
| constant = train mean (14.3697), RMSE | 11.6752 | 11.3732 |
| **median by (hour, day-of-week, PU, DO) from train** | **3.7170** | 3.5090 |

The group-median predictor falls back to the global median where a group is
unseen: 94,403 val rows (1.53%) and 87,989 test rows (1.48%).

For the same group-median predictor on val: **78.693% of trips land within 5
minutes** of the prediction and 44.117% within 2 minutes.

**What this buys.** A trained model that does not beat **3.72 min val MAE** has
not learned anything a `GROUP BY` does not already know. The honest bar for M2 is
that number, not the 7.89 of the constant baseline — quoting the easy baseline
would make any model look good, which is the sort of flattery this program exists
to refuse. The 78.7% within-5-minutes figure is the reference for **KPI-10** and
the shape the M5 SLO should be argued from.

---

## 12. Findings this report hands forward

| # | To | Finding |
|---|---|---|
| E-1 | M2 (MLE) | `ln(target)` is symmetric (skew −0.089) where the raw target is not (2.19). Consider the log objective; prove it, do not assume it. |
| E-2 | M2 (MLE) | `congestion_surcharge` is 63.46% null in 2019-01 with a one-day cutover at 2019-01-21. Exclude it or train from 2019-02; do not impute (§7b). |
| E-3 | M2 (MLE) | `airport_fee` is 100% null in every row of this window — zero information (§7c). |
| E-4 | M2/M5 | Post-trip columns (`fare_amount`, `tip_amount`, `total_amount`, `tolls_amount`, `payment_type`, `store_and_fwd_flag`) are leakage for a quote-time ETA (§8). |
| E-5 | M3 (dossier) | `trip_distance` is the *driven* distance from the meter, not a quote-time estimate. The strongest predictor may not be honestly available (§8). |
| E-6 | M2 | Zones 264/265 are "unknown", not places; 264→264 is the largest OD "route" at 409,128 trips (§9). |
| E-7 | M2/M6 | ~0.017% of val/test rows carry an OD pair unseen in train; an unseen-category path is required, not optional (§9). |
| E-8 | M2 | The null batch (261,781 rows, `payment_type = 0`) has 2.6× the mean duration. Indicator, not imputation (§7a). |
| E-9 | M1-S5 (board) | Rejection rate rises monotonically 1.428% → 2.020% across the window. Plot it as a series; a 10% threshold sees nothing (§1). |
| E-10 | M7 | The Jan→Jun target trend (+17.3%) is real drift already present in training data — a free realism check for the detector before synthetic drift (§4). |
| E-11 | **ANSWERED 2026-08-17 (M2-S1, F-005 closed)** | Everything here still describes the surviving 98.397%; the complement is now described too, in `docs/rejected_rows_appendix.md` from the `trips_rejected` view. `duration_above_max`'s 159,300 trips are **85.0% a 23–24 h clock artefact** and **3.5% genuine JFK-shaped long-haul** (§0, §2). |

## 13. Reproducing every number here

```bash
make duckdb                                     # rebuild the views (seconds)
python -m taxi_mlops.data query "<SQL>"         # read-only; each § quotes its SQL
```

Row counts in this report reconcile with M1-S1's ingest reports by construction —
`make duckdb` exits 1 if any view's count disagrees with the report that wrote
the data (verified at M1-S2: 8 months, `ALL 56,127,878`, every count reconciled).
