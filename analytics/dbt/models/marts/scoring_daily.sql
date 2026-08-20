{{ config(materialized = 'table', tags = ['aggregate', 'monitoring']) }}

-- scoring_daily — what the champion said about the scoring months, one row per day.
--
-- GRAIN: one row per (month, pickup_date). ~91 rows for 2020-01..03. Small
-- enough to be a TABLE a board hits on every refresh, and full-refresh forever
-- (D-003's split: the aggregates are rebuilt wholesale because it is under a
-- second and it makes drift between the mart and its source impossible).
--
-- WHY DAILY AND NOT MONTHLY. F-045, measured at M7-S1 before this model existed:
-- 2020-03's mean trip duration is 13.1645 against 2020-01's 13.2123 — a 0.36%
-- move, SMALLER than the ordinary Jan->Feb wobble — while its daily series runs
-- 240,520 trips at 14.878 min on the 5th to 5,361 trips at 9.715 min on the
-- 29th. The monthly aggregate is dominated by the ten ordinary days at its head.
-- A monitoring table at monthly grain would show the most drifted month this
-- program will ever hold as unremarkable. Monthly numbers are a `group by month`
-- away from these rows; the reverse is not true, which is the whole argument.
--
-- IT AGGREGATES MODEL OUTPUT, IT DOES NOT COMPUTE A MODEL METRIC FROM TRIPS.
-- `error_segments`' argument, one tree along (gotcha #15 read carefully). No
-- prediction is recomputed here and no model is re-scored: SQL groups rows
-- `taxi_mlops.training.batch` was handed by `taxi_mlops.training.evaluate`'s
-- own path.
--
-- THESE ARE MONITORING IDS AND NOT GATE IDS. KPI-09/KPI-10 are the evaluator's
-- numbers on a HELD-OUT SPLIT — a month the champion was judged on, with a
-- registry tag recording the verdict. These have a different window (a scoring
-- month the model was never judged on, at day grain) and therefore different
-- ids: KPI-14 (MAE), KPI-15 (within-tolerance rate), KPI-16 (mean signed error),
-- KPI-17 (scored trips). The id law, applied rather than argued around. A column
-- named kpi_09_* in this file would let a board render a monitoring number under
-- a promotion KPI's name, and the two answer different questions on purpose.
--
-- KPI-16 EXISTS BECAUSE DIRECTION IS THE PART THAT DRIFTS. KPI-14 is an
-- absolute error and cannot tell a model that quotes 3 minutes too long from one
-- that quotes 3 minutes too short — and in a month where the traffic vanished
-- those are opposite diagnoses. It is signed on purpose (positive = the champion
-- over-quotes), and it is allowed to be negative.
--
-- NO FLOOR, NO MARGIN. `error_segments` carries `kpi_13_margin_vs_floor_pct`
-- because the gate is an argument between two predictors and the mart has to be
-- able to re-open it. There is no such argument here: the honest floor is fitted
-- on the 2019 train months, and publishing a 2020 margin against it would put a
-- comparison on a board that no gate ever made, against a bar chosen for a
-- different world. If a later story wants "is the model rotting or is the world
-- different?", that is a drift question with its own declared reference (M7-S3).

{% set tolerance = var('tolerance_minutes') %}

with scored as (

    select
        month,
        pickup_date,
        model_name,
        model_version,
        actual_minutes,
        predicted_minutes,
        abs_error_minutes,
        signed_error_minutes
    from {{ source('analyst', 'scoring_predictions') }}

)

select
    month,
    pickup_date,

    -- Which model said it. Carried at day grain rather than assumed constant:
    -- M7 law 3 lets the alias move through the gate, so a series that did not
    -- carry its version could splice two models into one line on a board. The
    -- grain test asserts (month, pickup_date) is unique, so a day that somehow
    -- carried two versions would fail the build rather than average them.
    max(model_name)                                              as model_name,
    max(model_version)                                           as model_version,
    count(distinct model_version)                                as model_versions_seen,

    -- KPI-17 — scored trips. The one marginal that cannot be averaged away
    -- (F-045): 2020-03's collapse is a VOLUME collapse first and a duration
    -- change second.
    count(*)                                                     as kpi_17_scored_trips,

    -- KPI-14 — monitoring MAE, minutes.
    avg(abs_error_minutes)                                       as kpi_14_mae_min,

    -- KPI-15 — monitoring within-tolerance rate, percent, WITH its tolerance in
    -- the next column. The two travel together by rule (KPI-10's discipline,
    -- inherited): a rate whose tolerance is not on the same row is a number
    -- whose meaning lives in a config file the reader does not have.
    100.0 * avg(case when abs_error_minutes <= {{ tolerance }} then 1 else 0 end)
                                                                 as kpi_15_within_tol_pct,
    {{ tolerance }}                                              as tolerance_minutes,

    -- KPI-16 — monitoring mean signed error, minutes. Positive = over-quoting.
    avg(signed_error_minutes)                                    as kpi_16_mean_signed_error_min,

    -- The two distributions the error is a difference of. Published beside it
    -- because "the model got worse" and "the world got faster" produce the same
    -- KPI-14 and are told apart by these two columns.
    avg(actual_minutes)                                          as mean_actual_min,
    avg(predicted_minutes)                                       as mean_predicted_min,
    median(actual_minutes)                                       as median_actual_min,
    median(predicted_minutes)                                    as median_predicted_min

from scored
group by month, pickup_date
