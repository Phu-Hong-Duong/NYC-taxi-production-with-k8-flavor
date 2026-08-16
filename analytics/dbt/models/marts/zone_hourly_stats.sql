{{ config(materialized = 'table', tags = ['aggregate']) }}

-- zone_hourly_stats — how long a trip out of a zone takes, by hour of day.
--
-- GRAIN: one row per (month, split, pickup zone, pickup hour). At most
-- 8 x 265 x 24 = 50,880 rows, which is why this one is a TABLE: the board hits
-- it on every refresh and it must not cost a 56M-row scan (the same reasoning
-- that kept `unknown_domain_values` out of `data_health` at M1-S2).
--
-- EVERY MONEY COLUMN CARRIES ITS WINDOW AND ITS EXCLUDED COUNT (KPI-08's rule,
-- AI-2 from the Data Contract Review). `fare_amount` maxes at 671,123.14
-- against a p99.9 of 93.00; a mean is barely moved by that, but this table also
-- publishes a SUM, and a SUM is moved by orders of magnitude. So the sum is
-- windowed and the number of rows the window dropped rides in the next column.
--
-- WHY MEDIAN AND P90 AND NOT A MEAN (KPI-06/KPI-07): the mean and the median
-- diverge sharply in the slow afternoon hours (16:00 mean 16.80 vs median
-- 12.12, eda_report.md §6) — those are the trips that generate complaints, and
-- a card that only tracks the centre cannot see them.
--
-- Zones 264 and 265 are "unknown", NOT places (eda_report.md §7). They are kept
-- rather than filtered, because a board that silently drops them reports a
-- smaller fleet; `pickup_zone_is_unknown` lets a card exclude them ON PURPOSE.

select
    month,
    split,
    PULocationID                                              as pickup_zone,
    pickup_hour,

    count(*)                                                  as trips,                        -- KPI-01, segmented
    median(trip_duration_minutes)                             as median_duration_min,          -- KPI-06
    quantile_cont(trip_duration_minutes, 0.9)                 as p90_duration_min,             -- KPI-07
    avg(trip_duration_minutes)                                as mean_duration_min,
    avg(trip_distance)                                        as mean_distance_miles,
    -- Speed from the two columns that define it, not from a stored field: there
    -- is no speed column in TLC data and inventing one silently would be worse.
    -- Guarded division — the contract already rejects duration <= 0, so this is
    -- belt and braces against a future rule change, not a known null.
    sum(trip_distance) / nullif(sum(trip_duration_minutes) / 60.0, 0)
                                                              as mean_speed_mph,

    -- KPI-08's window, stated in the data rather than in a comment on a card.
    avg(case when fare_amount between 0 and 200 then fare_amount end)
                                                              as kpi_08_mean_fare_windowed,
    sum(case when fare_amount between 0 and 200 then fare_amount end)
                                                              as kpi_08_sum_fare_windowed,
    count(*) filter (where fare_amount is not null and fare_amount not between 0 and 200)
                                                              as kpi_08_excluded_rows,

    (PULocationID in (264, 265))                              as pickup_zone_is_unknown

from {{ ref('trips_clean') }}
group by 1, 2, 3, 4
