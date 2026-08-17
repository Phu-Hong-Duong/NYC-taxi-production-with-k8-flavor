{{ config(materialized = 'table', tags = ['aggregate', 'model']) }}

-- error_segments — where the champion is wrong, at every grain the memo asks about.
--
-- GRAIN: one row per (split, segment, segment_value). ~2 x 580 rows: 24 hours,
-- 7 days, up to 265 pickup zones, up to 265 drop-off zones, the passenger
-- counts, eight duration bands, the unseen-group flag, and one `overall` row per
-- split. Small enough to be a TABLE a board can hit on every refresh.
--
-- IT AGGREGATES MODEL OUTPUT, IT DOES NOT COMPUTE A MODEL METRIC FROM TRIPS.
-- The distinction is gotcha #15 read carefully, and it is the reason this mart
-- is allowed to exist at all. KPI-09 and KPI-10 are produced by
-- `taxi_mlops.training.evaluate` and may be sourced nowhere else; what this
-- model reads is that evaluator's OWN published rows — one row per held-out
-- trip, carrying the actual, the champion's quote and the floor's quote
-- (`data/predictions/`, written by `taxi_mlops.training.score`). No prediction
-- is recomputed here and no model is re-scored; SQL only groups rows it was
-- handed. The segment numbers are therefore NEW ids (KPI-11, KPI-12, KPI-13 in
-- docs/kpi_definitions.md) because they have a new window — a segment, not a
-- whole split — and this repo's id law says a changed formula is a new id.
--
-- THE `overall` ROW IS THE CHECK. Aggregated over a whole split, KPI-11 must
-- equal KPI-09 and KPI-12 must equal KPI-10 to four decimals, because they are
-- the same arithmetic over the same rows. A schema test asserts exactly that
-- against the values the evaluator measured, so a mart that quietly filtered,
-- double-counted or lost rows cannot publish plausible segment numbers.
--
-- WHY THE FLOOR TRAVELS ALONGSIDE. The promotion gate is an argument between two
-- predictors, settled once on the aggregate. Segment MAE alone says "v1 is worst
-- in the slow afternoon" — which is also true of the `GROUP BY` and of the clock
-- itself. `margin_vs_floor_pct` is the number that says whether the booster is
-- earning anything in a segment, and it is allowed to go negative.

with scored as (

    select
        split,
        month,
        hour,
        dayofweek,
        PULocationID,
        DOLocationID,
        passenger_count,
        actual_minutes,
        predicted_minutes,
        floor_predicted_minutes,
        floor_unseen_group,
        abs_error_minutes,
        signed_error_minutes,
        floor_abs_error_minutes,

        -- Duration bands over the ACTUAL duration, not the predicted one: the
        -- question is "how wrong is it on long trips", and bucketing by the
        -- model's own guess would let a model that never predicts a long trip
        -- report an empty long-trip bucket and a perfect score.
        --
        -- The top band is 100-120 and is deliberately its own bucket rather than
        -- part of a 60+ tail: 120 minutes is where the contract's
        -- `duration_above_max` rule starts rejecting rows (M2-S1), so this band
        -- is the last one the model ever sees, and what sits immediately past it
        -- is characterised in docs/rejected_rows_appendix.md rather than here.
        case
            when actual_minutes <   5 then '01: 1-5 min'
            when actual_minutes <  10 then '02: 5-10 min'
            when actual_minutes <  20 then '03: 10-20 min'
            when actual_minutes <  30 then '04: 20-30 min'
            when actual_minutes <  45 then '05: 30-45 min'
            when actual_minutes <  60 then '06: 45-60 min'
            when actual_minutes < 100 then '07: 60-100 min'
            else                           '08: 100-120 min (contract edge)'
        end as duration_band,
        case
            when actual_minutes <   5 then 1
            when actual_minutes <  10 then 5
            when actual_minutes <  20 then 10
            when actual_minutes <  30 then 20
            when actual_minutes <  45 then 30
            when actual_minutes <  60 then 45
            when actual_minutes < 100 then 60
            else                           100
        end as duration_band_floor

    from {{ source('analyst', 'predictions') }}

)

{{ segment_error_metrics('overall',       "'all held-out trips'", '0',                    var('tolerance_minutes')) }}
union all
{{ segment_error_metrics('hour',          'hour',                'hour',                 var('tolerance_minutes')) }}
union all
{{ segment_error_metrics('dayofweek',     'dayofweek',           'dayofweek',            var('tolerance_minutes')) }}
union all
{{ segment_error_metrics('pickup_zone',   'PULocationID',        'PULocationID',         var('tolerance_minutes')) }}
union all
{{ segment_error_metrics('dropoff_zone',  'DOLocationID',        'DOLocationID',         var('tolerance_minutes')) }}
union all
{{ segment_error_metrics('passenger_count', 'passenger_count',   'passenger_count',      var('tolerance_minutes')) }}
union all
{{ segment_error_metrics('duration_band', 'duration_band',       'duration_band_floor',  var('tolerance_minutes')) }}
union all
{{ segment_error_metrics('unseen_group',  'floor_unseen_group',  'case when floor_unseen_group then 1 else 0 end', var('tolerance_minutes')) }}
