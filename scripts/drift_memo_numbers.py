"""Reprint every number in `docs/drift_memo_m7.md`, from the views, the mart and
the tracked drift records.

The M2-S4 precedent (`scripts/error_memo_numbers.py`) applied to the drift memo:
a memo full of figures nobody can re-run is a memo nobody can check, so this is
the memo's twin — one section per memo section, in the memo's order, each
printing the query it ran.

Three sources, and which one a number comes from is the number's meaning:

  * `analyst.trips_scoring` / `analyst.trips_scoring_rejected` — the 2020 rows
    the contract admitted and refused. Facts about the WORLD.
  * `main_marts.scoring_daily` — the monitoring mart (M7-S2). Facts about the
    CHAMPION's error, under monitoring ids KPI-14/15/16/17. They are not
    KPI-09/KPI-10 and not KPI-11/KPI-13: same instrument
    (`taxi_mlops.training.evaluate`), different window, different ids
    (gotcha #15). No floor column exists here, deliberately — see the memo §6.1.
  * `automation/runs/m7-drift/drift-*.json` — what the drift job measured, read
    back as data rather than retyped. Facts about the INSTRUMENTS.

This script computes no model metric of its own. Every error number is read from
what `evaluate` published; the world numbers are ordinary aggregates over rows.

Requires `make duckdb` (the analyst layer) and `make marts` (the mart). It reads
both read-only and writes nothing.

Usage:  uv run python scripts/drift_memo_numbers.py
        uv run python scripts/drift_memo_numbers.py 1 5 6   (only those sections)
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
MARTS_DB = REPO_ROOT / "analytics" / "dbt" / "marts.duckdb"
ANALYST_DB = REPO_ROOT / "data" / "analyst.duckdb"
DRIFT_RECORDS = REPO_ROOT / "automation" / "runs" / "m7-drift"

# The memo's analytical device, in one place so no two sections can disagree
# about where March 2020 was cut. The dates are the memo's §2 argument; changing
# them here changes every number that uses them, which is the point.
PERIOD_SQL = """case
    when month <> '2020-03' then month
    when {date_expr} <= date '2020-03-10' then '2020-03 (01-10)'
    when {date_expr} <= date '2020-03-21' then '2020-03 (11-21)'
    else '2020-03 (22-31)'
end"""
PERIOD_TRIPS = PERIOD_SQL.format(date_expr="cast(tpep_pickup_datetime as date)")
PERIOD_PREDS = PERIOD_SQL.format(date_expr="pickup_date")

AIRPORT_SQL = (
    "case when PULocationID in (1, 132, 138) or DOLocationID in (1, 132, 138) "
    "then 'airport' else 'ordinary' end"
)

# (memo section, title, sql)
QUERIES: list[tuple[str, str, str]] = [
    (
        "1",
        "the file, before a single row is read (analyst.raw_manifest)",
        """
        select month, bytes,
               round(bytes / 1048576.0, 1) as mib,
               round(100.0 * bytes / max(bytes) over (), 1) as pct_of_largest
        from analyst.raw_manifest
        where month in ('2019-01', '2019-03', '2020-01', '2020-02', '2020-03')
        order by month
        """,
    ),
    (
        "1",
        "rows in, rows out, and what the contract refused (analyst.scoring_months)",
        """
        select month, rows_in, rows_out, rows_rejected,
               round(100.0 * rejected_fraction, 4) as rejected_pct
        from analyst.scoring_months order by month
        """,
    ),
    (
        "1",
        "the 2019 reference the champion was fitted and judged on (analyst.ingest_months)",
        """
        select split, count(*) as months, sum(rows_out) as rows_out,
               round(avg(rows_out), 0) as mean_rows_per_month
        from analyst.ingest_months group by 1 order by 1
        """,
    ),
    (
        "1",
        "the daily series March 2020 — the shape the monthly row averages away",
        f"""
        select cast(tpep_pickup_datetime as date) as pickup_date,
               dayname(tpep_pickup_datetime) as day,
               count(*) as trips,
               round(avg(trip_duration_minutes), 3) as mean_duration_min,
               round(avg(trip_distance), 3) as mean_distance_mi,
               {PERIOD_TRIPS} as period
        from analyst.trips_scoring where month = '2020-03'
        group by 1, 2, 6 order by 1
        """,
    ),
    (
        "1",
        "the whole-month row — the number a monthly window would look at",
        """
        select month, count(*) as trips,
               round(avg(trip_duration_minutes), 4) as mean_duration_min,
               round(avg(trip_distance), 4) as mean_distance_mi
        from analyst.trips_scoring group by 1 order by 1
        """,
    ),
    (
        "2",
        "the three Marches, and the two ordinary months beside them",
        f"""
        with by_period as (
            select {PERIOD_TRIPS} as period, count(*) as trips
            from analyst.trips_scoring group by 1)
        select period, trips,
               case when period like '2020-03%' then round(
                   100.0 * trips
                   / sum(case when period like '2020-03%' then trips end) over (), 3)
               end as pct_of_march
        from by_period order by period
        """,
    ),
    (
        "3",
        "trip mix by period — what the remaining rider was buying",
        f"""
        select {PERIOD_TRIPS} as period, count(*) as trips,
               round(avg(trip_duration_minutes), 4) as mean_duration_min,
               round(avg(trip_distance), 4) as mean_distance_mi,
               round(avg(passenger_count), 4) as mean_passengers,
               round(avg(fare_amount), 4) as mean_fare_usd,
               round(avg(total_amount), 4) as mean_total_usd
        from analyst.trips_scoring group by 1 order by 1
        """,
    ),
    (
        "3",
        "the streets emptied — miles per hour, two ways",
        f"""
        select {PERIOD_TRIPS} as period, count(*) as trips,
               round(60.0 * avg(trip_distance) / avg(trip_duration_minutes), 4)
                   as mph_of_the_averages,
               round(median(trip_distance / (trip_duration_minutes / 60.0)), 4)
                   as median_trip_mph
        from analyst.trips_scoring
        where trip_duration_minutes > 0
        group by 1 order by 1
        """,
    ),
    (
        "3",
        "what the contract refused, per rule — a stable refusal profile",
        """
        select month, rejection_rule, count(*) as rejected
        from analyst.trips_scoring_rejected
        group by 1, 2 order by month, rejected desc
        """,
    ),
    (
        "4",
        "the clock: share of trips by pickup hour, January against the last ten days",
        f"""
        with p as (select {PERIOD_TRIPS} as period,
                          hour(tpep_pickup_datetime) as pickup_hour
                   from analyst.trips_scoring)
        select pickup_hour,
               round(100.0 * count(*) filter (where period = '2020-01')
                     / sum(count(*) filter (where period = '2020-01')) over (), 3)
                   as jan_pct,
               round(100.0 * count(*) filter (where period = '2020-03 (22-31)')
                     / sum(count(*) filter (where period = '2020-03 (22-31)')) over (), 3)
                   as late_march_pct
        from p group by 1 order by 1
        """,
    ),
    (
        "5",
        "airports as a share of the city's taxi work (JFK 132 / LGA 138 / EWR 1)",
        f"""
        select {PERIOD_TRIPS} as period, count(*) as trips,
               round(100.0 * count(*) filter (
                   where PULocationID in (1, 132, 138)
                      or DOLocationID in (1, 132, 138)) / count(*), 4) as airport_pct,
               round(100.0 * count(*) filter (
                   where PULocationID in (264, 265)
                      or DOLocationID in (264, 265)) / count(*), 4) as unknown_zone_pct
        from analyst.trips_scoring group by 1 order by 1
        """,
    ),
    (
        "5",
        "the same share on the 2019 splits the champion was fitted and judged on",
        """
        select split, count(*) as trips,
               round(100.0 * count(*) filter (
                   where PULocationID in (1, 132, 138)
                      or DOLocationID in (1, 132, 138)) / count(*), 4) as airport_pct
        from analyst.trips_clean group by 1 order by 1
        """,
    ),
    (
        "5",
        "the airport gap, measured in a world the 2019 memo never saw "
        "(docs/error_memo_m2.md §7 row 2)",
        f"""
        with p as (select {PERIOD_PREDS} as period, {AIRPORT_SQL} as bucket,
                          abs_error_minutes, signed_error_minutes
                   from analyst.scoring_predictions)
        select period,
               count(*) filter (where bucket = 'airport') as airport_trips,
               round(avg(abs_error_minutes) filter (where bucket = 'airport'), 4)
                   as airport_mae,
               round(avg(abs_error_minutes) filter (where bucket = 'ordinary'), 4)
                   as ordinary_mae,
               round(avg(abs_error_minutes) filter (where bucket = 'airport')
                     / avg(abs_error_minutes) filter (where bucket = 'ordinary'), 4)
                   as gap_ratio,
               round(avg(signed_error_minutes) filter (where bucket = 'airport'), 4)
                   as airport_bias_min
        from p group by 1 order by 1
        """,
    ),
    (
        "6",
        "the monitoring ids, rolled up from the daily mart (main_marts.scoring_daily)",
        """
        select month, sum(kpi_17_scored_trips) as kpi_17_trips,
               round(sum(kpi_14_mae_min * kpi_17_scored_trips)
                     / sum(kpi_17_scored_trips), 4) as kpi_14_mae_min,
               round(sum(kpi_15_within_tol_pct * kpi_17_scored_trips)
                     / sum(kpi_17_scored_trips), 3) as kpi_15_within_pct,
               round(sum(kpi_16_mean_signed_error_min * kpi_17_scored_trips)
                     / sum(kpi_17_scored_trips), 4) as kpi_16_bias_min,
               count(distinct model_version) as model_versions
        from main_marts.scoring_daily group by 1 order by 1
        """,
    ),
    (
        "6",
        "the daily series, from the day it started moving",
        """
        select pickup_date, dayname(pickup_date) as day, kpi_17_scored_trips as trips,
               round(kpi_14_mae_min, 4) as kpi_14_mae_min,
               round(kpi_15_within_tol_pct, 3) as kpi_15_within_pct,
               round(kpi_16_mean_signed_error_min, 4) as kpi_16_bias_min,
               round(mean_actual_min, 3) as mean_actual_min,
               round(mean_predicted_min, 3) as mean_quoted_min
        from main_marts.scoring_daily
        where pickup_date >= date '2020-03-08' order by pickup_date
        """,
    ),
    (
        "6",
        "the best and worst days of each month, by KPI-14",
        """
        with ranked as (
            select month, pickup_date, kpi_14_mae_min, kpi_17_scored_trips,
                   row_number() over (partition by month order by kpi_14_mae_min) as best,
                   row_number() over (partition by month order by kpi_14_mae_min desc) as worst
            from main_marts.scoring_daily)
        select month,
               max(case when best = 1 then pickup_date end) as best_day,
               round(max(case when best = 1 then kpi_14_mae_min end), 4) as best_mae,
               max(case when worst = 1 then pickup_date end) as worst_day,
               round(max(case when worst = 1 then kpi_14_mae_min end), 4) as worst_mae
        from ranked where best = 1 or worst = 1 group by 1 order by 1
        """,
    ),
    (
        "6",
        "weekday against weekend, in the collapse and in an ordinary month",
        f"""
        with p as (select {PERIOD_PREDS} as period,
                          case when dayofweek >= 5 then 'weekend' else 'weekday' end as part,
                          abs_error_minutes
                   from analyst.scoring_predictions)
        select period, part, count(*) as trips,
               round(avg(abs_error_minutes), 4) as mae_min
        from p where period in ('2020-01', '2020-03 (22-31)')
        group by 1, 2 order by 1, 2
        """,
    ),
    (
        "7",
        "what the drift job measured, read back off the tracked records",
        f"""
        select month, current_rows, round(current_trips_per_day, 1) as trips_per_day,
               round(volume_ratio, 4) as volume_ratio,
               round(max_input_psi, 4) as max_input_psi, reference, reference_rows
        from read_json_auto('{DRIFT_RECORDS}/drift-2020-*.json') order by month
        """,
    ),
    (
        "7",
        "per column, and the target kept separate from the inputs",
        f"""
        select month, c.column as column_name, round(c.psi, 4) as psi,
               round(100.0 * c.unseen_share, 6) as unseen_pct
        from (select month, unnest(columns) as c
              from read_json_auto('{DRIFT_RECORDS}/drift-2020-*.json'))
        order by month, psi desc
        """,
    ),
    (
        "7",
        "the headroom leg — the two 2019 months whose verdict already exists",
        f"""
        with raw as (
            select json(content) as j from read_text('{DRIFT_RECORDS}/headroom.json')),
        months as (select j, unnest(json_keys(j)) as month from raw)
        select month,
               cast(json_extract_string(j, '$."' || month || '".current_rows') as bigint)
                   as current_rows,
               round(cast(json_extract_string(j, '$."' || month || '".volume_ratio')
                          as double), 4) as volume_ratio,
               round(cast(json_extract_string(j, '$."' || month || '".max_input_psi')
                          as double), 4) as max_input_psi
        from months order by month
        """,
    ),
    (
        "7",
        "and WHICH column carried it — the size of a move is half of what it is",
        f"""
        with raw as (
            select json(content) as j from read_text('{DRIFT_RECORDS}/headroom.json')),
        -- the month keys are DERIVED from the record, never typed here
        months as (select j, unnest(json_keys(j)) as month from raw),
        cols as (
            select month,
                   unnest(cast(json_extract(j, '$."' || month || '".columns') as json[])) as c
            from months)
        select month,
               json_extract_string(c, '$.column') as column_name,
               round(cast(json_extract_string(c, '$.psi') as double), 4) as psi
        from cols
        qualify row_number() over (partition by month order by psi desc) <= 2
        order by month, psi desc
        """,
    ),
]


def _fmt(value: object) -> str:
    if value is None:
        return "(null)"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _show(con: duckdb.DuckDBPyConnection, section: str, title: str, sql: str) -> None:
    print("\n" + "=" * 100)
    print(f"§{section}  {title}")
    print("=" * 100)
    rel = con.execute(sql)
    cols = [d[0] for d in rel.description]
    rows = rel.fetchall()
    widths = [
        max(len(c), *(len(_fmt(r[i])) for r in rows)) if rows else len(c)
        for i, c in enumerate(cols)
    ]
    print("  ".join(c.rjust(w) for c, w in zip(cols, widths, strict=True)))
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print("  ".join(_fmt(v).rjust(w) for v, w in zip(row, widths, strict=True)))


def main(argv: list[str]) -> int:
    for path in (MARTS_DB, ANALYST_DB):
        if not path.exists():
            print(f"missing {path} — run `make predictions-scoring && make duckdb && make marts`")
            return 2
    if not DRIFT_RECORDS.is_dir():
        print(f"missing {DRIFT_RECORDS} — run `make drift`")
        return 2

    wanted = set(argv) or {section for section, _, _ in QUERIES}
    unknown = wanted - {section for section, _, _ in QUERIES}
    if unknown:
        print(f"no such section(s): {', '.join(sorted(unknown))}")
        return 2

    con = duckdb.connect(str(MARTS_DB), read_only=True)
    con.execute(f"attach '{ANALYST_DB}' as analyst (read_only)")
    try:
        for section, title, sql in QUERIES:
            if section in wanted:
                _show(con, section, title, sql)
    finally:
        con.close()
    print("\nEvery number above is in docs/drift_memo_m7.md. A disagreement is a defect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
