"""SCRATCH — deleted before commit. Follow-up numbers straight from the predictions view."""

import duckdb

con = duckdb.connect("data/analyst.duckdb", read_only=True)


def show(title, sql):
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)
    rel = con.execute(sql)
    cols = [d[0] for d in rel.description]
    for r in rel.fetchall():
        print(dict(zip(cols, r)))


show(
    "the model's ceiling vs the world's",
    """
    select split,
           round(max(predicted_minutes), 3) as max_predicted,
           round(max(actual_minutes), 3) as max_actual,
           round(quantile_cont(predicted_minutes, 0.9999), 3) as p9999_predicted,
           round(min(predicted_minutes), 3) as min_predicted
    from predictions group by split order by split
    """,
)

show(
    "over- vs under-quoting (test)",
    """
    select split,
           100.0*count(*) filter (where signed_error_minutes > 0)/count(*) as pct_over_quoted,
           100.0*count(*) filter (where signed_error_minutes < 0)/count(*) as pct_under_quoted,
           round(avg(signed_error_minutes) filter (where signed_error_minutes > 0), 3) as mean_over,
           round(avg(signed_error_minutes) filter (where signed_error_minutes < 0), 3) as mean_under,
           100.0*count(*) filter (where signed_error_minutes < -5)/count(*) as pct_late_by_5plus,
           100.0*count(*) filter (where signed_error_minutes > 5)/count(*) as pct_early_by_5plus
    from predictions group by split order by split
    """,
)

show(
    "null passenger_count vs the unseen-group fallback (test)",
    """
    select count(*) as rows_null_passenger,
           100.0*count(*) filter (where floor_unseen_group)/count(*) as pct_also_unseen,
           round(avg(abs_error_minutes), 4) as model_mae,
           round(avg(floor_abs_error_minutes), 4) as floor_mae,
           round(avg(actual_minutes), 3) as mean_actual,
           count(distinct PULocationID) as pu_zones
    from predictions where split='test' and passenger_count is null
    """,
)

show(
    "unseen-group rows: what do they look like (test)",
    """
    select round(avg(actual_minutes),3) as mean_actual,
           round(avg(predicted_minutes),3) as mean_pred,
           round(avg(floor_predicted_minutes),3) as mean_floor_pred,
           count(distinct PULocationID) as pu_zones,
           100.0*count(*) filter (where PULocationID in (264,265) or DOLocationID in (264,265))
                /count(*) as pct_unknown_zone
    from predictions where split='test' and floor_unseen_group
    """,
)

show(
    "the 100-120 band, in detail (test)",
    """
    select count(*) as trips,
           round(max(predicted_minutes),3) as max_pred,
           round(avg(predicted_minutes),3) as mean_pred,
           round(min(abs_error_minutes),3) as best_case_error,
           100.0*count(*) filter (where predicted_minutes >= 60)/count(*) as pct_predicted_over_60
    from predictions where split='test' and actual_minutes >= 100
    """,
)

show(
    "trips over 60 minutes: how often does the model reach past 60 (test)",
    """
    select count(*) as trips_over_60_actual,
           count(*) filter (where predicted_minutes > 60) as predicted_over_60,
           round(100.0*count(*) filter (where predicted_minutes > 60)/count(*), 4) as pct
    from predictions where split='test' and actual_minutes > 60
    """,
)

show(
    "how many test trips does the model EVER quote above 60 min",
    """
    select count(*) filter (where predicted_minutes > 60) as quoted_over_60,
           count(*) filter (where predicted_minutes > 45) as quoted_over_45,
           count(*) as rows
    from predictions where split='test'
    """,
)

show(
    "airport zones, both directions (test)",
    """
    select case when PULocationID in (132,138,1) or DOLocationID in (132,138,1)
                then 'touches JFK/LGA/EWR' else 'no airport' end as bucket,
           count(*) as trips,
           round(avg(abs_error_minutes),4) as model_mae,
           round(avg(floor_abs_error_minutes),4) as floor_mae,
           round(100.0*count(*) filter (where abs_error_minutes<=5)/count(*),3) as within5,
           round(avg(actual_minutes),3) as mean_actual
    from predictions where split='test' group by 1 order by 1
    """,
)
