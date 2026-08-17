{#
  segment_error_metrics — ONE definition of "how wrong was the model here?",
  emitted once per segment dimension by `error_segments`.

  Written as a macro rather than copied eight times because the eight blocks
  differ only in what they GROUP BY. Copied, they would be eight places for the
  within-tolerance rate to drift, and the first symptom would be a board where
  the hour cards and the zone cards quietly disagree about the same trips. This
  repo has paid that bill before (the port family, the split months).

  It reads the `scored` CTE by name from the model that calls it — deliberately,
  so the expensive scan of the predictions view happens exactly once and every
  segment aggregates the identical rows.

  `tolerance` is passed in from configs/train.yaml (evaluate.tolerance_minutes)
  via scripts/marts.sh --vars, with NO default: KPI-12 is a rate within a
  tolerance, and a mart that silently invented 5.0 would publish a number whose
  definition lives nowhere.
#}
{% macro segment_error_metrics(segment, value_expr, sort_expr, tolerance) %}
select
    split,
    '{{ segment }}'                                              as segment,
    -- COALESCE and not a filter: `passenger_count` is nullable by contract, and
    -- the trips where the rider stated no party size are a real population with
    -- a real error rate. Left as NULL the row renders as a blank label, which
    -- reads as a broken card rather than as a segment — found by the not_null
    -- test on the first build, which is what that test is for.
    coalesce(cast({{ value_expr }} as varchar), '(not stated)') as segment_value,
    cast({{ sort_expr }} as double)                              as segment_sort,

    count(*)                                                     as trips,
    100.0 * count(*) / sum(count(*)) over (partition by split)   as share_of_split_pct,

    -- KPI-11: the segment's ETA MAE, in minutes. Named `kpi_11_` because in this
    -- repo KPI ids ARE columns (CLAUDE.md), which is also what makes
    -- tests/unit/test_marts.py able to check that every published id is defined.
    avg(abs_error_minutes)                                       as kpi_11_mae_min,
    -- KPI-12: the segment's within-tolerance rate, in percent.
    100.0 * count(*) filter (where abs_error_minutes <= {{ tolerance }})
          / count(*)                                             as kpi_12_within_tol_pct,
    -- Signed, and it is not a rounding of the MAE: a segment can be 6 minutes
    -- wrong on average while being systematically 6 minutes SHORT, which is the
    -- half of "wrong" a rider actually experiences as a broken promise.
    avg(signed_error_minutes)                                    as model_bias_min,
    quantile_cont(abs_error_minutes, 0.9)                        as model_p90_ae_min,

    -- The honest floor's answer on the same rows. The gate compared these two
    -- predictors once, in the aggregate; this is the same comparison per segment.
    avg(floor_abs_error_minutes)                                 as floor_mae_min,
    100.0 * count(*) filter (where floor_abs_error_minutes <= {{ tolerance }})
          / count(*)                                             as floor_within_tol_pct,
    -- KPI-13: what the booster buys here, as a percentage of the floor's error.
    -- NEGATIVE means the `GROUP BY` wins in this segment, and those rows are the
    -- entire point of publishing this mart.
    100.0 * (avg(floor_abs_error_minutes) - avg(abs_error_minutes))
          / nullif(avg(floor_abs_error_minutes), 0)              as kpi_13_margin_vs_floor_pct,

    avg(actual_minutes)                                          as mean_actual_min,
    avg(predicted_minutes)                                       as mean_predicted_min,
    100.0 * count(*) filter (where floor_unseen_group) / count(*) as floor_unseen_pct,
    {{ tolerance }}                                              as tolerance_minutes
from scored
group by 1, 2, 3, 4
{% endmacro %}
