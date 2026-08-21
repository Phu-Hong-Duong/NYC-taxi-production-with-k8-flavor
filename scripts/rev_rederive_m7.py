"""REV's M7 re-derivation — the ◆ review's arithmetic, re-runnable by anyone.

Written at the ◆ M7 review (2026-08-21) by REV, a fresh session with zero
builder context. It exists for the reason `scripts/error_memo_numbers.py` and
`scripts/drift_memo_numbers.py` exist: **a re-derivation nobody can re-run is a
re-derivation nobody can check.** A reviewer's "I recomputed it and it matched"
is worth exactly as much as the transcript it is written in, unless the
recomputation is a file.

WHAT IS DELIBERATELY NOT IMPORTED
---------------------------------
`taxi_mlops.monitoring.drift` — the module under review. Its PSI, its share
queries and its trips-per-day arithmetic are re-implemented here from the
FORMULA in its docstring, against the analyst layer directly. Calling
`compute_drift()` and comparing its output with the JSON it wrote would prove
only that the file was written by the function, which nobody doubted.

Likewise §4 reads `data/scoring_predictions/**.parquet` — the published rows —
and never `marts.scoring_daily`, `predictions.json`, or
`taxi_mlops.training.evaluate`. The mart is what the memo cites; the parquet is
what the mart is built from. Checking the memo against the mart checks a sum;
checking it against the rows checks the claim.

SECTIONS
--------
  1. PSI per monitored column, 2020-03 vs trips_train
  2. volume_ratio for all three scoring months
  3. A-9's denominator under a DEEPER collapse  <- this is F-051
  4. KPI-14/15/16 for the scoring months and the memo's three March periods

Read-only. Writes nothing, pushes nothing, touches no cluster.

    uv run python scripts/rev_rederive_m7.py [1|2|3|4 ...]
"""

from __future__ import annotations

import math
import sys

import duckdb

DB = "data/analyst.duckdb"
SHARE_FLOOR = 1e-7  # drift.py's documented floor, re-declared not imported
A9_BAR = 0.50  # infra/monitoring/alerting_rules.yml, ScoringVolumeCollapse
PARQUET = 'read_parquet("data/scoring_predictions/{m}/*.parquet")'
MONTHS = ("2020-01", "2020-02", "2020-03")

#: The five inputs plus the target, re-declared from drift.MONITORED_COLUMNS'
#: documented expressions rather than imported from it.
CATEGORICAL = {
    "hour": "CAST(EXTRACT(hour FROM tpep_pickup_datetime) AS BIGINT)",
    "dayofweek": "CAST(EXTRACT(dow FROM tpep_pickup_datetime) AS BIGINT)",
    "PULocationID": "PULocationID",
    "DOLocationID": "DOLocationID",
    "passenger_count": "passenger_count",
}
DURATION_EDGES = (0.0, 3.0, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0, 25.0, 30.0, 45.0, 60.0, 120.0)


def psi(reference: dict[str, float], current: dict[str, float]) -> float:
    """PSI = sum_bins (cur - ref) * ln(cur / ref), both shares floored."""
    total = 0.0
    for key in set(reference) | set(current):
        ref = max(reference.get(key, 0.0), SHARE_FLOOR)
        cur = max(current.get(key, 0.0), SHARE_FLOOR)
        total += (cur - ref) * math.log(cur / ref)
    return total


def shares(con: duckdb.DuckDBPyConnection, sql: str) -> dict[str, float]:
    rows = con.execute(sql).fetchall()
    total = sum(int(n) for _, n in rows)
    return {str(b): int(n) / total for b, n in rows}


def duration_case() -> str:
    whens = " ".join(
        f"WHEN trip_duration_minutes < {DURATION_EDGES[i + 1]:g} "
        f"THEN '[{DURATION_EDGES[i]:g},{DURATION_EDGES[i + 1]:g})'"
        for i in range(len(DURATION_EDGES) - 1)
    )
    return f"CASE {whens} ELSE '[120,inf)' END"


def section_1(con: duckdb.DuckDBPyConnection) -> None:
    print("1. PSI per monitored column, 2020-03 vs trips_train")
    print("   claim: automation/runs/m7-drift/drift-2020-03.json\n")
    for name, expr in CATEGORICAL.items():
        ref = shares(con, f"SELECT CAST({expr} AS VARCHAR), COUNT(*) FROM trips_train GROUP BY 1")
        cur = shares(
            con,
            f"SELECT CAST({expr} AS VARCHAR), COUNT(*) FROM trips_scoring "
            f"WHERE month='2020-03' GROUP BY 1",
        )
        print(f"   {name:22s} psi = {psi(ref, cur):.15f}")
    case = duration_case()
    ref = shares(
        con,
        f"SELECT {case}, COUNT(*) FROM trips_train "
        f"WHERE trip_duration_minutes IS NOT NULL GROUP BY 1",
    )
    cur = shares(
        con,
        f"SELECT {case}, COUNT(*) FROM trips_scoring WHERE month='2020-03' "
        f"AND trip_duration_minutes IS NOT NULL GROUP BY 1",
    )
    print(
        f"   {'trip_duration_minutes':22s} psi = {psi(ref, cur):.15f}   (the TARGET, "
        "excluded from A-8's share by name)"
    )


def reference_per_day(con: duckdb.DuckDBPyConnection) -> tuple[int, int, float]:
    rows, days = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT CAST(tpep_pickup_datetime AS DATE)) FROM trips_train"
    ).fetchone()
    return int(rows), int(days), rows / days


def section_2(con: duckdb.DuckDBPyConnection) -> None:
    print("2. volume_ratio, all three scoring months")
    print("   claim: each month's drift-<m>.json\n")
    ref_rows, ref_days, ref_per_day = reference_per_day(con)
    print(f"   reference {ref_rows:,} rows / {ref_days} days = {ref_per_day:.4f} trips/day")
    for month in MONTHS:
        rows, days = con.execute(
            "SELECT COUNT(*), COUNT(DISTINCT CAST(tpep_pickup_datetime AS DATE)) "
            "FROM trips_scoring WHERE month = ?",
            [month],
        ).fetchone()
        print(
            f"   {month}: {rows:>10,} / {days} days = {rows / days:>10.4f}  "
            f"ratio = {(rows / days) / ref_per_day:.16f}"
        )


def section_3(con: duckdb.DuckDBPyConnection) -> None:
    """F-051. The denominator counts days OBSERVED, so a day with no trips
    leaves the numerator and the denominator together — and the ratio RISES."""
    print("3. F-051 — A-9's denominator under a DEEPER collapse")
    print("   drift._days counts DISTINCT observed dates, not the month's days.")
    print("   Simulated by deleting 2020-03's quietest days outright: a strictly")
    print("   WORSE shutdown, and therefore a strictly lower ratio — or not.\n")
    _, _, ref_per_day = reference_per_day(con)
    days = con.execute(
        "SELECT CAST(tpep_pickup_datetime AS DATE), COUNT(*) FROM trips_scoring "
        "WHERE month='2020-03' GROUP BY 1 ORDER BY 2 ASC"
    ).fetchall()
    print(
        f"   {'zeroed':>7} {'trips left':>12} {'obs days':>9} {'trips/day':>12} "
        f"{'ratio':>8}   A-9 at {A9_BAR}"
    )
    print("   " + "-" * 62)
    for zeroed in (0, 4, 6, 8, 10, 12, 14):
        left = days[zeroed:]
        rows = sum(int(n) for _, n in left)
        ratio = (rows / len(left)) / ref_per_day
        verdict = "FIRES" if ratio < A9_BAR else "*** SILENT ***"
        print(
            f"   {zeroed:>7} {rows:>12,} {len(left):>9} {rows / len(left):>12,.1f} "
            f"{ratio:>8.4f}   {verdict}"
        )
    print("\n   the same series against CALENDAR days (31) — which is what")
    print('   docs/slo_serving.md §8.4 \'s "trips per day" says to a reader:\n')
    for zeroed in (0, 6, 10, 14):
        rows = sum(int(n) for _, n in days[zeroed:])
        ratio = (rows / 31) / ref_per_day
        verdict = "FIRES" if ratio < A9_BAR else "SILENT"
        print(f"   {zeroed:>7} {rows:>12,} {31:>9} {rows / 31:>12,.1f} {ratio:>8.4f}   {verdict}")


def section_4(con: duckdb.DuckDBPyConnection) -> None:
    print("4. KPI-14/15/16 from the published prediction rows")
    print("   claim: docs/drift_memo_m7.md · marts.scoring_daily · CLAUDE.md\n")
    agg = """SELECT COUNT(*), AVG(ABS(predicted_minutes - actual_minutes)),
      AVG(CASE WHEN ABS(predicted_minutes - actual_minutes) <= 5 THEN 1.0 ELSE 0 END) * 100,
      AVG(predicted_minutes - actual_minutes), AVG(actual_minutes), AVG(predicted_minutes)
      FROM {src} {where}"""
    for month in MONTHS:
        r = con.execute(agg.format(src=PARQUET.format(m=month), where="")).fetchone()
        print(
            f"   {month}  rows={r[0]:>10,}  KPI-14={r[1]:.4f}  KPI-15={r[2]:.3f}%  "
            f"KPI-16={r[3]:+.4f}"
        )

    src = PARQUET.format(m="2020-03")
    total = con.execute(agg.format(src=src, where="")).fetchone()[0]
    print("\n   2020-03 cut into the memo's three periods (PERIOD_SQL's boundaries):")
    for label, where in (
        ("Mar 01-10", "WHERE pickup_date < DATE '2020-03-11'"),
        ("Mar 11-21", "WHERE pickup_date >= DATE '2020-03-11' AND pickup_date < DATE '2020-03-22'"),
        ("Mar 22-31", "WHERE pickup_date >= DATE '2020-03-22'"),
    ):
        r = con.execute(agg.format(src=src, where=where)).fetchone()
        print(
            f"     {label}: rows={r[0]:>9,} ({r[0] / total * 100:6.3f}%)  KPI-14={r[1]:.4f}  "
            f"KPI-15={r[2]:6.3f}%  KPI-16={r[3]:+.4f}  actual={r[4]:6.3f}  pred={r[5]:6.3f}"
        )

    print("\n   worst day each side of the collapse:")
    for month in ("2020-01", "2020-03"):
        d, mae, n = con.execute(
            f"SELECT pickup_date, AVG(ABS(predicted_minutes - actual_minutes)) m, COUNT(*) "
            f"FROM {PARQUET.format(m=month)} GROUP BY 1 ORDER BY m DESC LIMIT 1"
        ).fetchone()
        print(f"     {month}: {d}  KPI-14={mae:.4f}  rows={n:,}")

    print("\n   model_version stamped on the rows (must be exactly one per month):")
    for month in MONTHS:
        versions = con.execute(
            f"SELECT DISTINCT model_version FROM {PARQUET.format(m=month)}"
        ).fetchall()
        print(f"     {month}: {[v[0] for v in versions]}")


SECTIONS = {"1": section_1, "2": section_2, "3": section_3, "4": section_4}


def main() -> int:
    wanted = sys.argv[1:] or list(SECTIONS)
    unknown = [w for w in wanted if w not in SECTIONS]
    if unknown:
        print(f"unknown section(s) {unknown}; choose from {sorted(SECTIONS)}", file=sys.stderr)
        return 2
    con = duckdb.connect(DB, read_only=True)
    try:
        for index, key in enumerate(wanted):
            if index:
                print()
            print("=" * 74)
            SECTIONS[key](con)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
