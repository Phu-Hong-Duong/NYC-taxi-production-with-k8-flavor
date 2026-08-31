#!/usr/bin/env python
"""F-051's counterfactual, re-run against the FIXED arithmetic.

M8-S1 leg 1. REV raised F-051 at the M7 review by re-implementing the ratio from
`drift.py`'s docstring and deleting 2020-03's quietest days one at a time — a
strictly WORSE shutdown — then showing the ratio RISE back across A-9's bar
(`scripts/rev_rederive_m7.py` §3, which deliberately did not import the module
under review). *Dated note, CU-S1 2026-08-31: that instrument was RETIRED — its
measurement is banked in the M7 review's tracked record, and the record is the
artifact. The sentence above stays because it is the provenance of the number
this file exists to answer; only the affordance of re-running it is gone.*

So this is the other side of the same measurement: the SAME counterfactual,
computed through the shipped functions (`drift.calendar_days`, `drift.trips_per_day`)
so that what is demonstrated is the program's behaviour and not a re-derivation of
it. The old denominator is kept in the table beside the new one, because the point
is not that the new series falls — it is that the old one did not.

Read-only. Opens the analyst layer, writes nothing, pushes nothing, and takes the
bar from `infra/monitoring/alerting_rules.yml` rather than typing 0.50 (F-017:
a literal on both sides of a check is one literal).

    uv run python scripts/f051_counterfactual.py [--month 2020-03]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from taxi_mlops.data.analyst import database_path  # noqa: E402
from taxi_mlops.data.config import load_config, repo_root  # noqa: E402
from taxi_mlops.monitoring import drift  # noqa: E402

RULES_FILE = repo_root() / "infra" / "monitoring" / "alerting_rules.yml"


def a9_bar() -> float:
    """The 0.50 in A-9's own selector, parsed rather than remembered."""
    match = re.search(
        r"taxi_drift_volume_ratio\{[^}]*\}\s*<\s*([0-9.]+)", RULES_FILE.read_text()
    )
    if not match:
        raise SystemExit(f"could not find A-9's bar in {RULES_FILE}")
    return float(match.group(1))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", default="2020-03")
    parser.add_argument("--max-zeroed", type=int, default=15)
    args = parser.parse_args(argv)

    bar = a9_bar()
    cfg = load_config()
    con = duckdb.connect(str(database_path(cfg)), read_only=True)
    try:
        reference_months = [
            str(m)
            for (m,) in con.execute(
                "SELECT DISTINCT month FROM trips_train ORDER BY 1"
            ).fetchall()
        ]
        (reference_rows,) = con.execute("SELECT COUNT(*) FROM trips_train").fetchone()
        daily = con.execute(
            "SELECT CAST(tpep_pickup_datetime AS DATE) AS d, COUNT(*) AS n "
            "FROM trips_scoring WHERE month = ? GROUP BY 1 ORDER BY 2 ASC",
            [args.month],
        ).fetchall()
    finally:
        con.close()

    reference_days = drift.calendar_days(reference_months)
    reference_per_day = drift.trips_per_day(int(reference_rows), reference_days)
    calendar = drift.calendar_days([args.month])

    print(f"F-051 counterfactual — {args.month}, through the SHIPPED arithmetic")
    print(f"  reference {int(reference_rows):,} rows / {reference_days} calendar days "
          f"= {reference_per_day:,.4f} trips/day  ({'+'.join(reference_months)})")
    print(f"  {args.month} covers {calendar} calendar days; {len(daily)} of them held a trip")
    print(f"  A-9 fires below {bar} (parsed from {RULES_FILE.relative_to(repo_root())})\n")
    print("  Delete the k quietest days outright — a strictly WORSE shutdown each step.\n")
    print(f"  {'zeroed':>6} {'trips left':>12} | {'/calendar':>10} {'ratio':>7} {'A-9':>8}"
          f" | {'/observed':>10} {'ratio':>7} {'A-9':>8}")
    print("  " + "-" * 82)

    fixed: list[float] = []
    old: list[float] = []
    for zeroed in range(args.max_zeroed + 1):
        left = daily[zeroed:]
        rows = sum(int(n) for _, n in left)
        new_ratio = drift.trips_per_day(rows, calendar) / reference_per_day
        old_ratio = drift.trips_per_day(rows, len(left)) / reference_per_day
        fixed.append(new_ratio)
        old.append(old_ratio)
        print(
            f"  {zeroed:>6} {rows:>12,} | {rows / calendar:>10,.0f} {new_ratio:>7.4f} "
            f"{'FIRES' if new_ratio < bar else '*SILENT*':>8} | "
            f"{rows / len(left):>10,.0f} {old_ratio:>7.4f} "
            f"{'FIRES' if old_ratio < bar else '*SILENT*':>8}"
        )

    monotonic = all(b < a for a, b in zip(fixed, fixed[1:], strict=False))
    old_rose = [k for k, (a, b) in enumerate(zip(old, old[1:], strict=False), start=1) if b > a]
    old_silent = [k for k, r in enumerate(old) if r >= bar]
    print()
    print(f"  shipped denominator (calendar): monotonically falling = {monotonic}; "
          f"never silent after first firing = {all(r < bar for r in fixed)}")
    print(f"  old denominator (observed days): ROSE at k = {old_rose}; "
          f"SILENT at k = {old_silent}")
    print()
    if not monotonic or any(r >= bar for r in fixed):
        print("  FAIL — the shipped arithmetic is still non-monotonic in the collapse.")
        return 1
    if not old_rose:
        print("  FAIL — the old arithmetic did not reproduce F-051 on this month; the")
        print("         comparison proves nothing and the table should not be quoted.")
        return 1
    print("  OK — a deeper collapse now produces a lower ratio at every step, and the")
    print("       month never walks back across the bar. F-051's own series is the")
    print("       control: the denominator it used rises, and goes silent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
