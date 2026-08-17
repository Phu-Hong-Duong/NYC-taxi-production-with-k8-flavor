# Appendix R — what the contract threw away (M2-S1, role:DE)

Companion to `docs/eda_report.md`, which describes the surviving **98.397%** and
says so at its §0. This appendix describes the other **1.603%** — 914,459 rows
over 2019-01…08 — and exists because F-005 asked one question the counts could
not answer: **the 159,300 trips over 120 minutes, are they meter faults or a
real long-haul population?**

Every number below came from `python -m taxi_mlops.data query "<SQL>"` against
the DuckDB analyst layer, run 2026-08-17. **No parquet path was opened**: the
rows are read through the `trips_rejected` view, the counts through
`ingest_rejections`, the clean comparisons through `trips_clean`. Each section
quotes its SQL. The sidecar the view sits on is written by `make ingest`, pinned
by DVC (`data/rejected.dvc`), and proved byte-identically re-derivable by
`make rebuild-proof` alongside `data/processed` (16/16 outputs, two witnesses).

**The answer, in one line:** *mostly meter faults, and the fault has a
signature.* **85.0%** of the above-max population is a normal short taxi trip —
median **2.19 miles**, median fare **$12.00** — whose clock ran for **23–24
hours** and stopped one day later at almost the same time of day. A real
long-haul population exists too, but it is **5,601 trips (3.5%)**, it is
**JFK-shaped**, and it sits in the 120–180 minute band immediately past the
rule's boundary.

---

## R1. What is in the sidecar at all

```sql
SELECT rejection_rule, COUNT(*) AS rows,
       ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER (), 3) AS pct_of_rejected,
       COUNT(*) FILTER (WHERE rejection_rules LIKE '%,%') AS also_broke_another_rule
FROM trips_rejected GROUP BY 1 ORDER BY 2 DESC
```

| rejection_rule | rows | % of rejected | also broke another rule |
|---|---:|---:|---:|
| duration_below_min | 512,388 | 56.032% | 307,634 |
| **duration_above_max** | **159,300** | **17.420%** | 2,469 |
| distance_non_positive | 117,932 | 12.896% | 2,776 |
| fare_negative | 64,284 | 7.030% | 0 |
| duration_non_positive | 57,322 | 6.268% | 57,322 |
| pickup_outside_month | 3,182 | 0.348% | 68 |
| distance_above_max | 51 | 0.006% | 0 |
| *(missing_timestamp · location_out_of_range · passenger_count_out_of_range)* | **0** | 0% | — |

Two facts worth carrying forward.

**Three of the ten rules have never rejected a row** in this window. They are not
dead — `ingest_rejections` shows `matched = 0` for them too, so nothing was
shadowing them; the 2019 files simply contain no null timestamp, no zone id
outside 1–265 and no passenger count outside 0–9. A rule with no live victims is
a rule nobody would notice breaking, which is why `tests/unit/test_data_clean.py`
provokes each of them with a purpose-built row.

**`rejection_rule` is first-match; `rejection_rules` lists them all.** The
`also_broke_another_rule` column is the per-ROW view of the shadowing that
`rejected_by` vs `matched` shows per rule — e.g. every one of the 57,322
`duration_non_positive` rows also violates `duration_below_min`, because a trip
of ≤ 0 minutes is also under 1 minute.

---

## R2. The above-max population, by duration band

```sql
SELECT CASE
         WHEN trip_duration_minutes < 180   THEN 'a. 120-180 min'
         WHEN trip_duration_minutes < 360   THEN 'b. 3-6 h'
         WHEN trip_duration_minutes < 720   THEN 'c. 6-12 h'
         WHEN trip_duration_minutes < 1380  THEN 'd. 12-23 h'
         WHEN trip_duration_minutes <= 1440 THEN 'e. 23-24 h (the wall)'
         ELSE 'f. over 24 h' END AS band,
       COUNT(*) AS rows, ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER (),3) AS pct,
       ROUND(MEDIAN(trip_distance),2) AS med_miles,
       ROUND(MEDIAN(fare_amount),2)  AS med_fare,
       ROUND(MEDIAN(total_amount),2) AS med_total
FROM trips_rejected WHERE rejection_rule='duration_above_max' GROUP BY 1 ORDER BY 1
```

| band | rows | % | median miles | median fare | median total |
|---|---:|---:|---:|---:|---:|
| a. 120–180 min | 5,601 | 3.516% | 18.06 | $62.00 | $75.80 |
| b. 3–6 h | 3,331 | 2.091% | 4.22 | $29.00 | $36.96 |
| c. 6–12 h | 5,510 | 3.459% | 5.29 | $23.50 | $27.94 |
| d. 12–23 h | 9,334 | 5.859% | 5.42 | $22.00 | $26.30 |
| **e. 23–24 h (the wall)** | **135,460** | **85.035%** | **2.19** | **$12.00** | **$16.56** |
| f. over 24 h | 64 | 0.040% | 0.00 | $20.75 | $23.05 |

The distribution is not a tail, it is a **spike**: p25 = 1,392.2 min, median =
1,415.0, p75 = 1,432.7 — i.e. the middle half of the population sits between
23.2 and 23.9 hours. Max is 43,648 minutes (30.3 days).

```sql
SELECT COUNT(*), MIN, QUANTILE_CONT(.25), MEDIAN, QUANTILE_CONT(.75),
       QUANTILE_CONT(.95), QUANTILE_CONT(.99), MAX  -- of trip_duration_minutes
FROM trips_rejected WHERE rejection_rule = 'duration_above_max'
```
→ `159300 | 120.02 | 1392.20 | 1415.02 | 1432.72 | 1438.30 | 1439.17 | 43648.02`

---

## R3. The wall is a 24-hour clock artefact, and it says so twice

```sql
SELECT CASE WHEN trip_duration_minutes BETWEEN 1380 AND 1440
            THEN 'wall 23-24h' ELSE 'the rest' END AS pop,
       COUNT(*) AS rows,
       COUNT(*) FILTER (WHERE date_diff('day', tpep_pickup_datetime, tpep_dropoff_datetime)=1)
         AS dropoff_next_day,
       AVG(EXTRACT(hour FROM tpep_pickup_datetime))  AS mean_pickup_hour,
       AVG(EXTRACT(hour FROM tpep_dropoff_datetime)) AS mean_dropoff_hour,
       100.0*COUNT(*) FILTER (WHERE EXTRACT(hour FROM tpep_pickup_datetime)
                                  = EXTRACT(hour FROM tpep_dropoff_datetime))/COUNT(*)
         AS pct_same_clock_hour
FROM trips_rejected WHERE rejection_rule='duration_above_max' GROUP BY 1
```

| population | rows | dropoff next day | mean pickup hour | mean dropoff hour | same clock hour |
|---|---:|---:|---:|---:|---:|
| wall 23–24h | 135,460 | 134,067 (99.0%) | 13.29 | 13.16 | **62.64%** |
| the rest | 23,840 | 16,873 (70.8%) | 12.98 | 6.99 | 0.02% |

**Witness 1 — the timestamps.** A wall trip is picked up at ~13:00 and dropped
off at ~13:00 *the following day*, in 62.6% of cases within the same clock hour.
That is a session that was closed a day later, not a journey that took a day.

**Witness 2 — the money, which was never wrong.** The fare and distance of the
wall population look like an ordinary trip, and nothing like the genuine long
trips the rule *keeps*:

```sql
SELECT COUNT(*), MEDIAN(trip_distance), MEDIAN(fare_amount), MEDIAN(total_amount)
  FROM trips_rejected WHERE rejection_rule='duration_above_max'
                        AND trip_duration_minutes BETWEEN 1380 AND 1440
UNION ALL SELECT … FROM trips_clean
UNION ALL SELECT … FROM trips_clean WHERE trip_duration_minutes >= 100
```

| population | rows | median miles | median fare | median total |
|---|---:|---:|---:|---:|
| wall 23–24h (rejected) | 135,460 | 2.19 | $12.00 | $16.56 |
| every clean trip (1–120 min) | 56,127,878 | 1.66 | $9.50 | $14.30 |
| clean tail, 100–120 min | 12,522 | 19.10 | $53.00 | $75.30 |

The wall population is a *slightly longer than typical short trip*. If those
135,460 rows were really 23-hour journeys, the meter would have charged for
them; it did not, because the meter measured a normal ride and only the
timestamps are unusable. **They are correctly rejected**, and — importantly for
M2-S2 — they are not a population an ETA model is missing out on. There is no
`trip_duration_minutes` in them worth learning.

The **64 rows over 24 hours** are the same class in worse condition: median
distance **0.00 miles**, 100% next-day-or-later, up to 30 days.

---

## R4. There *is* a real long-haul population, and it is JFK-shaped

The gradient across the bands is monotone in every discriminator, which is what
makes it an interpretation rather than a story:

```sql
SELECT <band>, COUNT(*) AS rows,
       100.0*COUNT(*) FILTER (WHERE PULocationID IN (132,138,1)
                                 OR DOLocationID IN (132,138,1))/COUNT(*) AS pct_touch_airport,
       100.0*COUNT(*) FILTER (WHERE trip_distance >= 10)/COUNT(*)        AS pct_ge_10_miles,
       100.0*COUNT(*) FILTER (WHERE fare_amount >= 40)/COUNT(*)          AS pct_fare_ge_40,
       100.0*COUNT(*) FILTER (WHERE date_diff('day', tpep_pickup_datetime,
                                              tpep_dropoff_datetime) >= 1)/COUNT(*)
                                                                          AS pct_dropoff_next_day
FROM trips_rejected WHERE rejection_rule='duration_above_max' GROUP BY 1 ORDER BY 1
```
*(zone ids: 132 = JFK, 138 = LaGuardia, 1 = Newark — `docs/eda_report.md` §10)*

| band | rows | touches an airport | ≥ 10 miles | fare ≥ $40 | dropoff next day |
|---|---:|---:|---:|---:|---:|
| a. 120–180 min | 5,601 | **52.78%** | **66.01%** | **78.41%** | 16.34% |
| b. 3–6 h | 3,331 | 40.92% | 35.94% | 41.94% | 63.07% |
| c. 6–12 h | 5,510 | 44.72% | 35.66% | 32.14% | 92.23% |
| d. 12–23 h | 9,334 | 43.55% | 34.81% | 27.88% | 93.85% |
| e. 23–24 h (wall) | 135,460 | **10.55%** | **9.95%** | **7.42%** | **98.97%** |
| f. over 24 h | 64 | 15.63% | 12.50% | 40.63% | 100.00% |

The 120–180 minute band is the only one that behaves like travel: two thirds run
ten miles or more, four fifths cost $40+, and only one in six crosses midnight.
Its top origin–destination pairs are unambiguous:

```sql
SELECT PULocationID, DOLocationID, COUNT(*), MEDIAN(trip_duration_minutes),
       MEDIAN(trip_distance), MEDIAN(fare_amount)
FROM trips_rejected WHERE rejection_rule='duration_above_max'
                      AND trip_duration_minutes < 180
GROUP BY 1,2 ORDER BY 3 DESC LIMIT 10
```

| PU → DO | rows | median min | median miles | median fare |
|---|---:|---:|---:|---:|
| 132 → 265 (JFK → outside NYC) | 448 | 134.4 | 43.36 | $164.50 |
| 132 → 132 (JFK → JFK) | 177 | 144.0 | 35.33 | $52.00 |
| 138 → 265 (LGA → outside NYC) | 73 | 134.1 | 44.81 | $161.00 |
| 132 → 230 | 72 | 132.4 | 19.31 | $52.00 |
| 132 → 1 (JFK → Newark) | 60 | 132.5 | 35.63 | $130.00 |
| 132 → 48 | 60 | 129.0 | 19.49 | $52.00 |
| 230 → 132 | 47 | 131.0 | 17.98 | $52.00 |
| 264 → 264 (unknown → unknown) | 43 | 153.9 | 0.55 | $59.00 |
| 132 → 264 | 41 | 141.4 | 18.84 | $52.00 |
| 132 → 163 | 39 | 130.0 | 19.16 | $52.00 |

The recurring **$52.00** is the JFK↔Manhattan flat fare, and the rate codes agree:

```sql
SELECT RatecodeID, COUNT(*), MEDIAN(trip_distance), MEDIAN(fare_amount)
FROM trips_rejected WHERE rejection_rule='duration_above_max'
                      AND trip_duration_minutes < 180 GROUP BY 1 ORDER BY 2 DESC
```

| RatecodeID | rows | % | median miles | median fare |
|---|---:|---:|---:|---:|
| 1 standard | 2,499 | 44.62% | 10.70 | $63.50 |
| **2 JFK flat** | **1,251** | **22.34%** | 20.51 | $52.00 |
| 5 negotiated | 1,189 | 21.23% | 0.59 | $69.00 |
| 3 Newark | 391 | 6.98% | 20.70 | $114.00 |
| 4 Nassau/Westchester | 199 | 3.55% | 48.64 | $220.00 |
| NULL · 99 · 6 | 72 | 1.29% | — | — |

**32.87%** of the band carries a rate code that means *this trip leaves the
city* (2, 3 or 4). The same measure over the delivered data is **2.7497%**
(`SELECT 100.0*COUNT(*) FILTER (WHERE RatecodeID IN (2,3,4))/COUNT(*) FROM
trips_clean`) — a **12-fold** enrichment. These are out-of-town runs.

---

## R5. How much of each month this is — and why M2-S4 should care

```sql
SELECT split, month, COUNT(*) AS rows_above_max,
       COUNT(*) FILTER (WHERE trip_duration_minutes < 180)          AS plausible_long,
       COUNT(*) FILTER (WHERE trip_duration_minutes BETWEEN 1380 AND 1440) AS wall
FROM trips_rejected WHERE rejection_rule='duration_above_max' GROUP BY 1,2
-- joined to ingest_months for rows_out
```

| split | month | above max | % of the month as delivered | plausible long | wall |
|---|---|---:|---:|---:|---:|
| train | 2019-01 | 21,332 | 0.2805% | 417 | 18,739 |
| train | 2019-02 | 19,092 | 0.2741% | 471 | 16,581 |
| train | 2019-03 | 21,250 | 0.2733% | 567 | 18,282 |
| train | 2019-04 | 20,353 | 0.2754% | 654 | 17,324 |
| train | 2019-05 | 21,138 | 0.2817% | 960 | 17,924 |
| train | 2019-06 | 20,080 | 0.2923% | 1,020 | 16,940 |
| **val** | 2019-07 | 18,531 | 0.2985% | 849 | 15,313 |
| **test** | 2019-08 | 17,524 | 0.2936% | 663 | 14,357 |

Unlike the overall rejection rate — which rises **1.428% → 2.020%** across the
window (`docs/eda_report.md` §3) — the above-max share is nearly flat, 0.273% to
0.299%. **The rising rejection rate is not being driven by this rule**, so
whatever explains the trend lives in `duration_below_min` /
`distance_non_positive`, and that is where a future drift memo should look.

The `plausible_long` column is the one that moves: it more than doubles from 417
(2019-01) to 1,020 (2019-06). Small numbers, but they are real trips, and they
are the population immediately outside the boundary M2-S4's error memo has to
reason about.

**What M2-S4 may now say honestly.** The memo's "does it fail on long trips?"
question is bounded at 120 minutes by rule, and the boundary is now
*characterised* rather than merely acknowledged: the clean tail at 100–120
minutes holds **12,522** trips (median 19.1 miles, $53), and immediately past it
sit **5,601** genuine long trips the model never sees — the same shape, 18.06
miles, $62. The discontinuity at the boundary is an artefact of the rule, not of
the city, and the error memo should say so when it reports the long-duration
segment.

---

## R6. The other rejected populations, briefly

Not F-005's question, but the sidecar answers it now and silence would be its
own kind of report.

```sql
SELECT rejection_rule, COUNT(*), MEDIAN(trip_duration_minutes), MEDIAN(trip_distance),
       MEDIAN(fare_amount), 100.0*COUNT(*) FILTER (WHERE trip_distance=0)/COUNT(*)
FROM trips_rejected GROUP BY 1 ORDER BY 2 DESC
```

| rule | rows | median min | median miles | median fare | zero miles |
|---|---:|---:|---:|---:|---:|
| duration_below_min | 512,388 | 0.267 | 0.00 | $3.00 | 56.95% |
| distance_non_positive | 117,932 | 5.950 | 0.00 | $9.50 | 100% |
| fare_negative | 64,284 | 4.700 | 0.67 | −$5.00 | 0% |
| duration_non_positive | 57,322 | 0.000 | 0.00 | $9.50 | 95.00% |
| pickup_outside_month | 3,182 | 10.533 | 1.81 | $9.50 | 1.82% |

The majority rule, `duration_below_min` (56% of all rejects), is a **16-second
median trip that went nowhere and charged $3.00** — the flag-drop of a ride that
was cancelled or immediately voided. `fare_negative` is the only population that
looks like a *normal completed trip* (4.7 min, 0.67 mi) with a sign flipped:
these are almost certainly refunds/adjustments booked as trips. None of the five
is a population an ETA model wants.

---

## What this closes, and what it does not

**Closes F-005's remaining question.** The rejected rows are retained
(`data/rejected/<split>/`, DVC-pinned, `trips_rejected`), each carries the rule
that rejected it, and the `duration_above_max` population is decided with
numbers: **85.0% clock artefact, 3.5% real long-haul, the rest a graded mixture**
— not "meter faults or long trips" but *both, in a ratio of 24 to 1, separable
by a query anyone can now re-run.*

**Does not change any rule.** `max_minutes: 120.0` is unchanged and this
appendix argues it should stay: the population it removes is 85% unusable, and
the 5,601 genuine long trips it also removes are 0.010% of the delivered data.
Raising the ceiling to admit them would admit the wall with them. Loosening a
cleaning threshold is a PO fork in any case (CLAUDE.md), and nothing here asks
for one.

**Does not re-open the EDA's numbers.** Everything in `docs/eda_report.md` still
describes the surviving 98.397%; this appendix describes the complement. E-11 in
that report's open-questions table is answered by this document.
