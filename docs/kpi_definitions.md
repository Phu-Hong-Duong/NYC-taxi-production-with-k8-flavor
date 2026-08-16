# KPI definitions — one number, one definition, one window (M1-S3, role:DA)

**Authored:** 2026-08-16 (M1-S3) · **Owner of this document:** DA ·
**Cited by:** M1-S5's KPI board (every card names a KPI id), M2's error-analysis
memo, M5's SLO argument, M7's drift memos.

## The rules this document is written under

1. **A number without a definition and a window is not a KPI** (DA charter,
   refusal #1). Every entry below states its formula, its source view, its
   window, and who owns it.
2. **Every money KPI states its outlier treatment in its own definition.** This
   discharges **AI-2** from the M1-S2 Data Contract Review. The reason is not
   fastidiousness: `fare_amount` has a maximum of 671,123.14 against a p99.9 of
   93.00, and excluding 3,131 rows out of 56,127,878 (0.0056%) moves the
   fare↔duration correlation from 0.0735 to 0.8708 (eda_report.md §8). An
   un-windowed money number is not imprecise, it is meaningless.
3. **Source is always a named view, never a parquet path.** If a KPI cannot be
   expressed against `trips_clean`, `data_health`, `ingest_months`,
   `ingest_rejections` or `unknown_domain_values`, it needs a mart (M1-S4), not
   a private query.
4. **Model-quality KPIs (KPI-09, KPI-10) are DEFINED here and MEASURED from M2
   onward by `taxi_mlops.training.evaluate` only** (gotcha #15). A value
   computed any other way — including the SQL reference floors in
   eda_report.md §11 — may not be reported against these ids.
5. **Changing a formula changes the id.** KPI-03 always means what it means
   below. A different window is KPI-03b, not a quietly edited KPI-03; otherwise
   a board's history silently stops meaning one thing.

All observed values below are over **2019-01…08, `trips_clean`, 56,127,878
rows** unless the entry says otherwise.

---

## Data-health KPIs (live now, board at M1-S5)

### KPI-01 — Trips ingested per month
- **Formula:** `SELECT month, rows_out FROM data_health`
- **Source:** `data_health` (← `ingest_months`)
- **Window:** one calendar month, by `month` label from `configs/train.yaml`
- **Owner:** DE (produces) · DA (reports)
- **Observed:** 5,950,708 (2019-08) … 7,753,921 (2019-03); 56,127,878 total
- **Read it as:** volume delivered *after* the contract. Pair with KPI-02 —
  a fall in KPI-01 with a flat KPI-02 is a quieter month; a fall with a rising
  KPI-02 is a quality problem.

### KPI-02 — Row rejection rate
- **Formula:** `rows_rejected / rows_in` per month, as a percentage
  (`data_health.rejected_pct`)
- **Source:** `data_health`
- **Window:** one calendar month
- **Owner:** DE
- **Observed:** 1.428% (2019-04) → 2.020% (2019-08); 1.603% over the window
- **Alarm shape:** **plot as a series, not a threshold.** The ingest refuses a
  month above `max_rejected_fraction` (10%), which is 5× the worst month
  observed — that guard would not have noticed the 41% relative rise across
  these eight months (eda_report.md §1). The board's job is the trend.

### KPI-03 — Rejections attributed per rule
- **Formula:** `SELECT rule, SUM(rejected_by), SUM(matched) FROM ingest_rejections GROUP BY rule`
- **Source:** `ingest_rejections`
- **Window:** one calendar month, or the full window for totals
- **Owner:** DE
- **Observed (window totals):** `duration_below_min` 512,388 · `duration_above_max`
  159,300 · `distance_non_positive` 117,932 (attributed) vs 465,911 (matched)
- **Two columns, on purpose:** `rejected_by` is first-violated attribution and
  sums exactly to rows dropped; `matched` is independent hits. A rule shadowed by
  an earlier one reads 0 in the first column and cannot be presumed dead.
  **Rules currently at zero on both counts — `missing_timestamp`,
  `location_out_of_range`, `passenger_count_out_of_range` — must still be shown.**
  A rule you cannot see cannot be seen to start firing.

### KPI-04 — Undocumented-value rate (drift by value)
- **Formula:** `SUM(unknown_domain_values.rows) / KPI-01` per column, per month
- **Source:** `unknown_domain_values`
- **Window:** one calendar month
- **Owner:** DA
- **Observed:** VendorID 4 → 264,661 · payment_type 0 → 261,781 · RatecodeID 99
  → 949 · VendorID 5 → 219 (each present in all 8 months). **527,386 distinct
  rows (0.9396%) carry at least one undocumented value** — less than the sum of
  the four counts (527,610), because VendorID 5's 219 trips all also carry
  `payment_type = 0`. Sum the view's rows and you double-count; the KPI is
  `COUNT(DISTINCT row)`, measured 2026-08-16.
- **Read it as:** the contract refuses a column that appears, vanishes or is
  renamed (gotcha #31). Nothing refuses a column that grows a **new code**. This
  KPI is that watch. A *new row* appearing in this view is the event; the
  existing four are known and steady.

### KPI-05 — Raw-byte provenance match
- **Formula:** count of months where `data_health.raw_sha256` equals the pin in
  `data/raw_manifest.json`, over months expected (8)
- **Source:** `data_health` (← `raw_manifest`)
- **Window:** point-in-time, at ingest
- **Owner:** DE
- **Observed:** 8/8
- **Read it as:** a binary. Anything below 8/8 means the numbers on every other
  card describe bytes we did not pin, and the board should say so rather than
  render.

---

## Operational KPIs (the business's view of the fleet)

### KPI-06 — Median trip duration
- **Formula:** `MEDIAN(trip_duration_minutes)` over `trips_clean`
- **Source:** `trips_clean`
- **Window:** one calendar month; segmentable by hour, day-of-week, PU zone,
  RatecodeID
- **Outlier treatment:** none needed — the target is already bounded to
  [1, 120] minutes by the contract's `duration_below_min` / `duration_above_max`
  rules. **This bound is part of the definition**, not an incidental fact: KPI-06
  is the median duration *of trips the contract accepted*, and 159,300 trips over
  120 minutes are outside it (F-005).
- **Owner:** DA
- **Observed:** 11.15 min (train) · 11.4167 (val) · 11.2833 (test); by month
  10.2667 (Jan) → 11.7333 (Jun)

### KPI-07 — P90 trip duration
- **Formula:** `QUANTILE_CONT(trip_duration_minutes, 0.9)` over `trips_clean`
- **Source:** `trips_clean`
- **Window / outlier treatment:** as KPI-06
- **Owner:** DA
- **Observed:** 25.50 min (2019-01) → 30.13 min (2019-06) → 28.28 (2019-08)
- **Why P90 and not the mean:** the mean and median diverge sharply in the
  afternoon (16:00 mean 16.80 vs median 12.12) — the slow hours lengthen the tail
  rather than shifting the centre. A fleet KPI that only tracks the centre cannot
  see the trips that generate complaints.

### KPI-08 — Mean fare per trip **(windowed — money KPI, AI-2)**
- **Formula:** `AVG(fare_amount) FROM trips_clean WHERE fare_amount BETWEEN 0 AND 200`
- **Source:** `trips_clean`
- **Window:** one calendar month **AND** the value window `fare_amount ∈ [0, 200]`
- **Outlier treatment — stated, not implied:** rows with `fare_amount > 200` are
  **excluded and counted**. Observed: 3,131 rows of 56,127,878 (0.0056%),
  themselves averaging 869.13, maximum 671,123.14. **The count of excluded rows
  must be rendered on the same card as the value.** A windowed number with its
  exclusion hidden is worse than an un-windowed one, because it looks careful.
- **Owner:** DA
- **Observed:** 13.1263 (windowed) vs 13.1740 (all rows) — a 0.36% difference in
  the *mean*. The mean is the robust case; **the danger is elsewhere.** Any
  MAX, SUM, percentile-above-p99, variance, or correlation over `fare_amount`
  moves by orders of magnitude, not fractions of a percent (correlation with the
  target: 0.0735 raw → 0.8708 windowed). **No SUM or MAX of a money column may
  be published without this window.**
- **Sibling ids, same rule:** a windowed `total_amount` KPI is **KPI-08b**, a
  windowed `tip_amount` KPI is **KPI-08c**; both inherit this entry's window and
  exclusion-count requirement. Neither is on the M1-S5 board — named here so the
  first person who needs one does not invent an unwindowed version.

### KPI-09 — ETA absolute error (MAE)
- **Formula:** `MEAN(|predicted_duration − actual_duration|)` in minutes, on the
  held-out split
- **Source:** **`taxi_mlops.training.evaluate` only** (gotcha #15). Not a SQL
  view; not an AutoML leaderboard; not a scout-internal number.
- **Window:** one evaluation split (val = 2019-07, test = 2019-08), whole split
- **Owner:** MLE (produces) · DA (reports) · REV (audits)
- **Observed:** **not yet measured — M2 owns the first value.**
- **Reference floor (EDA statistic, NOT a KPI-09 value):** a train-fitted
  `GROUP BY (hour, day-of-week, PU, DO)` median achieves 3.7170 min on val
  (eda_report.md §11). **A model above that number has learned nothing a SQL
  query does not already know.** The constant-median baseline (7.8866) is the
  *easy* floor and must not be the one quoted.

### KPI-10 — ETA within-tolerance rate
- **Formula:** `P(|predicted − actual| ≤ 5 minutes)` on the held-out split, as a
  percentage
- **Source:** **`taxi_mlops.training.evaluate` only** (gotcha #15)
- **Window:** one evaluation split; tolerance fixed at **5 minutes**
- **Owner:** MLE (produces) · DA (reports) · SRE (consumes for the M5 SLO)
- **Observed:** **not yet measured — M2 owns the first value.**
- **Reference floor (EDA statistic):** the same group-median predictor lands
  within 5 minutes on **78.693%** of val trips (44.117% within 2 minutes).
- **Why this exists next to KPI-09:** MAE is dominated by the median trip and can
  be respectable while the model is badly wrong in the slow afternoon hours that
  generate complaints (eda_report.md §6). A rate-within-tolerance is the number a
  rider experiences and the shape an SLO can be written against. **The 5-minute
  tolerance is a DA proposal, not a settled SLO** — M5 owns the SLO, and moving
  the tolerance is a PO fork, not an edit.

---

## Segment dimensions every board should support

Named once here so each board does not reinvent them, and so M2's error memo and
M7's drift memo segment the same way:

| dimension | source column | why it matters (evidence) |
|---|---|---|
| hour of day | `EXTRACT(hour FROM tpep_pickup_datetime)` | speed varies 2.16× across the day (23.70 → 10.97 mph) |
| day of week | `DAYOFWEEK(tpep_pickup_datetime)` | Thursday is slowest AND busiest; weekend 1.5–2.4 min faster |
| rate code | `RatecodeID` | code 2 (JFK) is 2.47% of trips at 3.5× the mean duration |
| PU / DO zone | `PULocationID`, `DOLocationID` | 48,634 observed OD pairs; **264/265 are "unknown", not places** |
| month | `month` | target mean rises 17.3% Jan→Jun (a reporting dimension **only** — never a model feature, eda_report.md §4) |
| null batch | `payment_type = 0` | 261,781 rows at 2.6× the mean duration |

## What is deliberately NOT a KPI yet

- **Anything requiring the rejected rows** (e.g. "share of trips over 2 hours").
  Blocked on **F-005**: the rejected rows exist only as counts. Naming a KPI we
  cannot compute would be a promise the data cannot keep.
- **Cost / revenue per zone.** Needs `total_amount` windowed (KPI-08b) *and* a
  zone dimension table; M1-S4's marts are the right home, not this document.
- **Freshness / lag.** Meaningless on a fixed 2019 archive. It becomes real when
  M4 schedules ingest, and it should be defined then against the real clock
  rather than invented now against a static file.
