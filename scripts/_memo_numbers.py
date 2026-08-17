"""SCRATCH — deleted before commit. Pull the error memo's numbers from the mart."""

import duckdb

con = duckdb.connect("analytics/dbt/marts.duckdb", read_only=True)


def show(title, sql):
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)
    rel = con.execute(sql)
    cols = [d[0] for d in rel.description]
    rows = rel.fetchall()
    print(" | ".join(c[:22].rjust(22) for c in cols))
    for r in rows:
        cells = []
        for v in r:
            cells.append(f"{v:22.4f}" if isinstance(v, float) else str(v)[:22].rjust(22))
        print(" | ".join(cells))


show(
    "OVERALL",
    """
    select split, trips, round(kpi_11_mae_min,4) mae, round(kpi_12_within_tol_pct,3) within5,
           round(floor_mae_min,4) floor_mae, round(floor_within_tol_pct,3) floor_within5,
           round(kpi_13_margin_vs_floor_pct,2) margin, round(model_bias_min,4) bias,
           round(model_p90_ae_min,3) p90, round(floor_unseen_pct,4) unseen_pct
    from main_marts.error_segments where segment='overall' order by split
    """,
)

show(
    "DURATION BANDS (test)",
    """
    select segment_value, trips, round(share_of_split_pct,3) as share_pct,
           round(kpi_11_mae_min,4) mae, round(kpi_12_within_tol_pct,3) within5,
           round(floor_mae_min,4) floor_mae, round(kpi_13_margin_vs_floor_pct,2) margin,
           round(model_bias_min,3) bias, round(mean_actual_min,2) mean_actual,
           round(mean_predicted_min,2) mean_pred
    from main_marts.error_segments where segment='duration_band' and split='test'
    order by segment_sort
    """,
)

show(
    "DURATION BANDS (val)",
    """
    select segment_value, trips, round(share_of_split_pct,3) as share_pct,
           round(kpi_11_mae_min,4) mae, round(kpi_12_within_tol_pct,3) within5,
           round(kpi_13_margin_vs_floor_pct,2) margin, round(model_bias_min,3) bias
    from main_marts.error_segments where segment='duration_band' and split='val'
    order by segment_sort
    """,
)

show(
    "HOURS (test)",
    """
    select cast(segment_sort as int) hr, trips, round(share_of_split_pct,2) as share_pct,
           round(kpi_11_mae_min,4) mae, round(kpi_12_within_tol_pct,3) within5,
           round(floor_mae_min,4) floor_mae, round(kpi_13_margin_vs_floor_pct,2) margin,
           round(model_bias_min,3) bias, round(mean_actual_min,2) mean_actual
    from main_marts.error_segments where segment='hour' and split='test' order by segment_sort
    """,
)

show(
    "DAY OF WEEK (test)  0=Mon",
    """
    select cast(segment_sort as int) dow, trips, round(kpi_11_mae_min,4) mae,
           round(kpi_12_within_tol_pct,3) within5, round(kpi_13_margin_vs_floor_pct,2) margin,
           round(model_bias_min,3) bias
    from main_marts.error_segments where segment='dayofweek' and split='test' order by segment_sort
    """,
)

show(
    "UNSEEN GROUP (both splits)",
    """
    select split, segment_value, trips, round(share_of_split_pct,4) as share_pct,
           round(kpi_11_mae_min,4) mae, round(kpi_12_within_tol_pct,3) within5,
           round(floor_mae_min,4) floor_mae, round(kpi_13_margin_vs_floor_pct,2) margin
    from main_marts.error_segments where segment='unseen_group' order by split, segment_value
    """,
)

show(
    "PASSENGER COUNT (test)",
    """
    select segment_value, trips, round(share_of_split_pct,3) as share_pct,
           round(kpi_11_mae_min,4) mae, round(kpi_12_within_tol_pct,3) within5,
           round(kpi_13_margin_vs_floor_pct,2) margin
    from main_marts.error_segments where segment='passenger_count' and split='test'
    order by trips desc
    """,
)

show(
    "WORST PICKUP ZONES (test, >=20000 trips), by MAE",
    """
    select segment_value as zone_id, trips, round(kpi_11_mae_min,4) mae,
           round(kpi_12_within_tol_pct,3) within5, round(floor_mae_min,4) floor_mae,
           round(kpi_13_margin_vs_floor_pct,2) margin, round(model_bias_min,3) bias,
           round(mean_actual_min,2) mean_actual
    from main_marts.error_segments where segment='pickup_zone' and split='test' and trips>=20000
    order by kpi_11_mae_min desc limit 12
    """,
)

show(
    "BEST PICKUP ZONES (test, >=20000 trips), by MAE",
    """
    select segment_value as zone_id, trips, round(kpi_11_mae_min,4) mae,
           round(kpi_12_within_tol_pct,3) within5, round(kpi_13_margin_vs_floor_pct,2) margin
    from main_marts.error_segments where segment='pickup_zone' and split='test' and trips>=20000
    order by kpi_11_mae_min asc limit 8
    """,
)

show(
    "WORST DROPOFF ZONES (test, >=20000 trips)",
    """
    select segment_value as zone_id, trips, round(kpi_11_mae_min,4) mae,
           round(kpi_12_within_tol_pct,3) within5, round(floor_mae_min,4) floor_mae,
           round(kpi_13_margin_vs_floor_pct,2) margin, round(model_bias_min,3) bias,
           round(mean_actual_min,2) mean_actual
    from main_marts.error_segments where segment='dropoff_zone' and split='test' and trips>=20000
    order by kpi_11_mae_min desc limit 12
    """,
)

show(
    "SEGMENTS WHERE THE FLOOR WINS (test, >=5000 trips)",
    """
    select segment, segment_value, trips, round(kpi_11_mae_min,4) mae,
           round(floor_mae_min,4) floor_mae, round(kpi_13_margin_vs_floor_pct,2) margin
    from main_marts.error_segments
    where split='test' and trips>=5000 and kpi_13_margin_vs_floor_pct < 0
    order by kpi_13_margin_vs_floor_pct asc limit 20
    """,
)

show(
    "SEGMENTS WHERE THE FLOOR WINS (test, any size) — count",
    """
    select segment, count(*) segments_where_floor_wins, sum(trips) trips_affected
    from main_marts.error_segments
    where split='test' and kpi_13_margin_vs_floor_pct < 0
    group by 1 order by 2 desc
    """,
)

show(
    "ZONE COVERAGE (test)",
    """
    select segment, count(*) distinct_values, min(trips) min_trips, max(trips) max_trips
    from main_marts.error_segments where split='test' group by 1 order by 1
    """,
)

show(
    "BIGGEST ZONES (test) by volume",
    """
    select segment_value as zone_id, trips, round(share_of_split_pct,3) as share_pct,
           round(kpi_11_mae_min,4) mae, round(kpi_12_within_tol_pct,3) within5,
           round(kpi_13_margin_vs_floor_pct,2) margin
    from main_marts.error_segments where segment='pickup_zone' and split='test'
    order by trips desc limit 10
    """,
)

show(
    "TOTAL ROWS IN MART",
    "select count(*) as n_rows, count(distinct segment) segments from main_marts.error_segments",
)
