"""Reprint every number in `docs/error_memo_m2.md`, from the mart and the view.

A memo full of figures nobody can re-run is a memo nobody can check. This script
is the memo's twin: one section per memo section, in the memo's order, each
printing the query it ran. `make marts` must have run (the mart) and `make
duckdb` before it (the `predictions` view it aggregates).

It computes NO metric of its own beyond the segment aggregates the mart already
publishes — KPI-09 and KPI-10 come from `taxi_mlops.training.evaluate` and are
read here from `prediction_runs`, never recomputed (gotcha #15).

Paths are resolved from the REPO ROOT, never from the caller's directory. That is
not fussiness: M2-S4 lost a `make marts` to exactly this — a dbt run from the
wrong cwd poisoned dbt's partial-parse cache with a relative `root_path` and left
an empty `marts.duckdb` at the repo root (gotcha #38).

Usage:  uv run python scripts/error_memo_numbers.py
        uv run python scripts/error_memo_numbers.py 1 2 4   (only those sections)
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
MARTS_DB = REPO_ROOT / "analytics" / "dbt" / "marts.duckdb"
ANALYST_DB = REPO_ROOT / "data" / "analyst.duckdb"

# (memo section, title, which database, sql)
QUERIES: list[tuple[str, str, str, str]] = [
    (
        "0",
        "the mart's whole-split rollup vs what the evaluator measured "
        "(KPI-11/12 must reproduce KPI-09/10)",
        "marts",
        """
        select e.split, e.trips,
               round(e.kpi_11_mae_min, 4)        as kpi_11_mart,
               round(r.kpi_09_mae_minutes, 4)    as kpi_09_evaluator,
               round(e.kpi_12_within_tol_pct, 3) as kpi_12_mart,
               round(r.kpi_10_within_pct, 3)     as kpi_10_evaluator
        from main_marts.error_segments e
        join analyst.prediction_runs r
          on r.split = e.split and r.contender like '%@champion'
        where e.segment = 'overall'
        order by e.split
        """,
    ),
    (
        "1",
        "the headline split by whether the floor had a group median to give",
        "marts",
        """
        select split, segment_value, trips, round(share_of_split_pct, 4) as share_pct,
               round(kpi_11_mae_min, 4) as mae, round(floor_mae_min, 4) as floor_mae,
               round(kpi_13_margin_vs_floor_pct, 2) as margin,
               round(kpi_12_within_tol_pct, 3) as within5
        from main_marts.error_segments
        where segment = 'unseen_group'
        order by split, segment_value
        """,
    ),
    (
        "2",
        "duration bands (test) — the ceiling finding",
        "marts",
        """
        select segment_value, trips, round(share_of_split_pct, 3) as share_pct,
               round(kpi_11_mae_min, 4) as mae, round(kpi_12_within_tol_pct, 3) as within5,
               round(kpi_13_margin_vs_floor_pct, 2) as margin,
               round(mean_actual_min, 2) as mean_actual,
               round(mean_predicted_min, 2) as mean_quoted
        from main_marts.error_segments
        where segment = 'duration_band' and split = 'test'
        order by segment_sort
        """,
    ),
    (
        "2",
        "the model's ceiling against the world's, and how far past 60 min it reaches",
        "analyst",
        """
        select split,
               round(max(predicted_minutes), 3) as max_predicted,
               round(max(actual_minutes), 3)    as max_actual,
               count(*) filter (where predicted_minutes > 60) as quoted_over_60,
               count(*) filter (where actual_minutes > 60)    as actually_over_60,
               round(100.0 * count(*) filter (
                   where actual_minutes > 60 and predicted_minutes > 60)
                   / nullif(count(*) filter (where actual_minutes > 60), 0), 2)
                   as pct_of_long_trips_quoted_long
        from predictions group by split order by split
        """,
    ),
    (
        "2",
        "the 100-120 band in detail (test) — best case, not just the average",
        "analyst",
        """
        select count(*) as trips,
               round(max(predicted_minutes), 3) as max_quoted,
               round(avg(predicted_minutes), 3) as mean_quoted,
               round(min(abs_error_minutes), 3) as best_single_quote_error,
               round(avg(actual_minutes), 3)    as mean_actual
        from predictions where split = 'test' and actual_minutes >= 100
        """,
    ),
    (
        "3",
        "every segment on either split where the floor BEATS the model (>=5,000 trips)",
        "marts",
        """
        select split, segment, segment_value, trips,
               round(kpi_11_mae_min, 4) as mae, round(floor_mae_min, 4) as floor_mae,
               round(kpi_13_margin_vs_floor_pct, 2) as margin
        from main_marts.error_segments
        where trips >= 5000 and kpi_13_margin_vs_floor_pct < 0
        order by kpi_13_margin_vs_floor_pct
        """,
    ),
    (
        "3",
        "and the small ones, counted rather than listed (test)",
        "marts",
        """
        select segment, count(*) as segments_where_floor_wins, sum(trips) as trips_affected
        from main_marts.error_segments
        where split = 'test' and kpi_13_margin_vs_floor_pct < 0 and trips < 5000
        group by 1 order by 2 desc
        """,
    ),
    (
        "4",
        "worst-served pickup zones (test, >= 20,000 trips)",
        "marts",
        """
        select segment_value as zone_id, trips, round(kpi_11_mae_min, 4) as mae,
               round(kpi_12_within_tol_pct, 3) as within5,
               round(floor_mae_min, 4) as floor_mae,
               round(kpi_13_margin_vs_floor_pct, 2) as margin,
               round(model_bias_min, 2) as bias, round(mean_actual_min, 2) as mean_actual
        from main_marts.error_segments
        where segment = 'pickup_zone' and split = 'test' and trips >= 20000
        order by kpi_11_mae_min desc limit 5
        """,
    ),
    (
        "4",
        "best-served pickup zones, for contrast (test, >= 20,000 trips)",
        "marts",
        """
        select segment_value as zone_id, trips, round(kpi_11_mae_min, 4) as mae,
               round(kpi_12_within_tol_pct, 3) as within5
        from main_marts.error_segments
        where segment = 'pickup_zone' and split = 'test' and trips >= 20000
        order by kpi_11_mae_min limit 4
        """,
    ),
    (
        "4",
        "zone counts appearing in the test split",
        "marts",
        """
        select segment, count(*) as distinct_zones
        from main_marts.error_segments
        where split = 'test' and segment in ('pickup_zone', 'dropoff_zone')
        group by 1 order by 1
        """,
    ),
    (
        "4",
        "airports, both directions — one CASE over the predictions view (test)",
        "analyst",
        """
        select case when PULocationID in (132, 138, 1) or DOLocationID in (132, 138, 1)
                    then 'touches JFK/LGA/EWR' else 'no airport' end as bucket,
               count(*) as trips,
               round(100.0 * count(*) / sum(count(*)) over (), 3) as share_pct,
               round(avg(abs_error_minutes), 4)       as model_mae,
               round(avg(floor_abs_error_minutes), 4) as floor_mae,
               round(100.0 * count(*) filter (where abs_error_minutes <= 5)
                     / count(*), 3) as within5,
               round(avg(actual_minutes), 2) as mean_actual
        from predictions where split = 'test' group by 1 order by 1
        """,
    ),
    (
        "5",
        "hours (test) — best and worst by each KPI",
        "marts",
        """
        select cast(segment_sort as int) as hour, trips,
               round(kpi_11_mae_min, 4) as mae, round(kpi_12_within_tol_pct, 3) as within5,
               round(kpi_13_margin_vs_floor_pct, 2) as margin
        from main_marts.error_segments
        where segment = 'hour' and split = 'test' order by segment_sort
        """,
    ),
    (
        "5",
        "days (test) — 0 = Monday, pandas' dayofweek",
        "marts",
        """
        select cast(segment_sort as int) as dayofweek, trips,
               round(kpi_11_mae_min, 4) as mae, round(kpi_12_within_tol_pct, 3) as within5,
               round(kpi_13_margin_vs_floor_pct, 2) as margin
        from main_marts.error_segments
        where segment = 'dayofweek' and split = 'test' order by segment_sort
        """,
    ),
    (
        "6",
        "the asymmetry: early vs late, and by how much",
        "analyst",
        """
        select split,
               round(100.0 * count(*) filter (where signed_error_minutes > 0)
                     / count(*), 2) as pct_over_quoted,
               round(100.0 * count(*) filter (where signed_error_minutes < 0)
                     / count(*), 2) as pct_under_quoted,
               round(avg(signed_error_minutes) filter
                     (where signed_error_minutes > 0), 2) as mean_when_early,
               round(avg(signed_error_minutes) filter
                     (where signed_error_minutes < 0), 2) as mean_when_late,
               round(100.0 * count(*) filter (where signed_error_minutes < -5)
                     / count(*), 2) as pct_quoted_5min_short
        from predictions group by split order by split
        """,
    ),
    (
        "6",
        "passenger_count not stated — a segment, not a gap (test)",
        "marts",
        """
        select segment_value, trips, round(share_of_split_pct, 3) as share_pct,
               round(kpi_11_mae_min, 4) as mae, round(kpi_12_within_tol_pct, 3) as within5,
               round(floor_mae_min, 4) as floor_mae,
               round(kpi_13_margin_vs_floor_pct, 2) as margin,
               round(mean_actual_min, 2) as mean_actual
        from main_marts.error_segments
        where segment = 'passenger_count' and split = 'test'
        order by trips desc
        """,
    ),
    (
        "6",
        "...and how much of that segment is ALSO an unseen group (test)",
        "analyst",
        """
        select count(*) as rows_not_stated,
               round(100.0 * count(*) filter (where floor_unseen_group)
                     / count(*), 2) as pct_also_unseen,
               round(avg(actual_minutes), 2) as mean_actual
        from predictions where split = 'test' and passenger_count is null
        """,
    ),
]


def _show(con: duckdb.DuckDBPyConnection, section: str, title: str, sql: str) -> None:
    print("\n" + "=" * 96)
    print(f"§{section}  {title}")
    print("=" * 96)
    rel = con.execute(sql)
    cols = [d[0] for d in rel.description]
    rows = rel.fetchall()
    widths = [
        max(len(c), *(len(_fmt(r[i])) for r in rows)) if rows else len(c)
        for i, c in enumerate(cols)
    ]
    print("  ".join(c.rjust(w) for c, w in zip(cols, widths, strict=True)))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print("  ".join(_fmt(v).rjust(w) for v, w in zip(r, widths, strict=True)))


def _fmt(value: object) -> str:
    if value is None:
        return "(null)"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def main(argv: list[str]) -> int:
    for path in (MARTS_DB, ANALYST_DB):
        if not path.exists():
            print(f"missing {path} — run `make predictions && make duckdb && make marts`")
            return 2
    wanted = set(argv) or {s for s, _, _, _ in QUERIES}

    # The mart database is opened read-write-capable only to ATTACH the analyst
    # layer beside it; nothing here writes. Read-only would refuse the ATTACH.
    con = duckdb.connect(str(MARTS_DB), read_only=True)
    con.execute(f"attach '{ANALYST_DB}' as analyst (read_only)")
    try:
        for section, title, database, sql in QUERIES:
            if section not in wanted:
                continue
            _show(con, section, title, sql if database == "marts" else _via_analyst(sql))
    finally:
        con.close()
    print("\nEvery number above is in docs/error_memo_m2.md. A disagreement is a defect.")
    return 0


def _via_analyst(sql: str) -> str:
    """Point a `predictions`/`prediction_runs` query at the attached analyst layer."""
    return sql.replace(" predictions", " analyst.predictions").replace(
        " prediction_runs", " analyst.prediction_runs"
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
