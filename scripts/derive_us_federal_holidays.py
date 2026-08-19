#!/usr/bin/env python3
"""Derive `data/reference/us_federal_holidays.csv` from the statute (M5-S2, F-019).

WHY THIS EXISTS. The committed table held ten rows and every one of them was
2019. `taxi_mlops.features.calendar` raises on an uncovered year — correctly, at
training time, because a silent "not a holiday" for 2020 would look exactly like
a right answer and the feature would decay into a constant. But `features/` is
the ONE transform path for training AND serving (CLAUDE.md), and the champion
M3-S5 promoted eats `is_holiday`/`is_near_holiday`/`is_business_day`. So from the
first quote M5 serves, that same correct raise is a hard failure on every request
dated outside 2019. That is F-019, and this file is half of its fix; the other
half is the typed refusal in `taxi_mlops.serving.client`, because a table always
ends somewhere and the day it ends must not be a 500.

WHY A DERIVER AND NOT A HAND-EDIT. The rows are law — 5 U.S.C. §6103 — and law is
computable. A hand-extended table is eleven chances a year to typo a Monday, and
nothing in the repo would notice: a wrong holiday date is a feature that is
quietly wrong on exactly the days the feature exists for. The rules live here,
the data stays a committed CSV a reviewer can read (the decision
`features/calendar.py` records and this file keeps), and the two are tied
together by `make holidays` being idempotent and by a test that re-derives.

WHY IT IS TRUSTWORTHY, and this is the whole argument: **re-deriving 2019 alone
reproduces the ten hand-written rows exactly, names included.** Those rows were
written by a human from the OPM calendar at M3-S3, long before this script
existed, so agreement is evidence about the rules and not about the author. It
also proves the one rule a reader is most likely to get wrong — Juneteenth is
federal from 2021, so a rule set that emitted it for 2019 would fail here.

TWO DECISIONS RECORDED RATHER THAN ASSUMED.

1. **A weekend holiday emits TWO rows: the date itself and the observed day.**
   §6103(b) moves the DAY OFF to the adjacent weekday, and that is when offices
   close and the commute disappears; the statutory date is when the city
   celebrates and the fireworks traffic happens. Both days are anomalous for a
   trip-duration model, and picking one would be picking which anomaly to be
   blind to. The observed row is named `<Holiday> (observed)` so the two are
   distinguishable in the table, and `is_holiday` fires on both. **No 2019
   holiday falls on a weekend**, so this decision changes no number any milestone
   has measured — checked, not assumed (see `--year 2019` above).

2. **The horizon is a range this script is CALLED with, and the default stops at
   2030.** A longer default would be a bigger claim about a statute that changed
   as recently as 2021 (Juneteenth). 2030 is past anything this program plans and
   the cost of moving it is this one flag. The wall is real either way, which is
   why the serving boundary types it instead of relying on the table being long
   enough.

NOTES ARE HUMAN PROSE AND ARE PRESERVED. The `note` column carries a reviewer's
sentences — the 2019-01-21 row records that MLK Day is also F-006's
congestion_surcharge cliff. A deriver that erased them would be a deriver nobody
would run twice, so existing notes are read back in and re-emitted against their
date. Only rows the file has never held get a generated note.

Usage: make holidays                       (2019..2030, in place)
       uv run python scripts/derive_us_federal_holidays.py --to 2035
       uv run python scripts/derive_us_federal_holidays.py --year 2019 --stdout
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TABLE = REPO_ROOT / "data" / "reference" / "us_federal_holidays.csv"

#: The default horizon. See decision 2 in the module docstring.
FIRST_YEAR = 2019
LAST_YEAR = 2030

#: Juneteenth National Independence Day became a federal holiday on 2021-06-17.
#: The first observance was 2021, which is why a rule set that emits it for 2019
#: fails this script's own reproduction check.
JUNETEENTH_FROM = 2021

MONDAY, THURSDAY, SATURDAY, SUNDAY = 0, 3, 5, 6


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    """The n-th `weekday` of a month (n=1 is the first)."""
    first = dt.date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + dt.timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> dt.date:
    """The last `weekday` of a month."""
    following = dt.date(year + 1, 1, 1) if month == 12 else dt.date(year, month + 1, 1)
    last = following - dt.timedelta(days=1)
    return last - dt.timedelta(days=(last.weekday() - weekday) % 7)


def statutory_holidays(year: int) -> list[tuple[dt.date, str]]:
    """The eleven (ten before 2021) federal holidays of `year`, 5 U.S.C. §6103(a).

    Fixed dates are returned on their statutory date; `observed_rows` below adds
    the day off when one of them lands on a weekend.
    """
    days: list[tuple[dt.date, str]] = [
        (dt.date(year, 1, 1), "New Year's Day"),
        (_nth_weekday(year, 1, MONDAY, 3), "Birthday of Martin Luther King Jr."),
        (_nth_weekday(year, 2, MONDAY, 3), "Washington's Birthday"),
        (_last_weekday(year, 5, MONDAY), "Memorial Day"),
        (dt.date(year, 7, 4), "Independence Day"),
        (_nth_weekday(year, 9, MONDAY, 1), "Labor Day"),
        (_nth_weekday(year, 10, MONDAY, 2), "Columbus Day"),
        (dt.date(year, 11, 11), "Veterans Day"),
        (_nth_weekday(year, 11, THURSDAY, 4), "Thanksgiving Day"),
        (dt.date(year, 12, 25), "Christmas Day"),
    ]
    if year >= JUNETEENTH_FROM:
        days.append((dt.date(year, 6, 19), "Juneteenth National Independence Day"))
    return sorted(days)


def observed_date(day: dt.date) -> dt.date | None:
    """§6103(b): Saturday's day off is the Friday before, Sunday's the Monday after.

    Returns None when the holiday already falls on a weekday. Only the fixed-date
    holidays can ever trigger this — the four Monday holidays and Thanksgiving
    are defined as weekdays.
    """
    if day.weekday() == SATURDAY:
        return day - dt.timedelta(days=1)
    if day.weekday() == SUNDAY:
        return day + dt.timedelta(days=1)
    return None


def derive(first_year: int, last_year: int) -> list[tuple[dt.date, str]]:
    """Every row the table should hold for `[first_year, last_year]`, date-sorted."""
    rows: list[tuple[dt.date, str]] = []
    for year in range(first_year, last_year + 1):
        for day, name in statutory_holidays(year):
            rows.append((day, name))
            shifted = observed_date(day)
            if shifted is not None:
                rows.append((shifted, f"{name} (observed)"))
    # An observed day can be pulled into the neighbouring year (Jan 1 on a
    # Saturday is observed on Dec 31 of the year before), so sort at the end
    # rather than per year.
    return sorted(rows)


def render(rows: list[tuple[dt.date, str]], notes: dict[str, str]) -> str:
    """The CSV bytes. `lineterminator` is set because csv defaults to CRLF."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["date", "name", "note"])
    for day, name in rows:
        iso = day.isoformat()
        default = "observed day off — the statutory date fell on a weekend" \
            if name.endswith("(observed)") else ""
        writer.writerow([iso, name, notes.get(iso, default)])
    return buffer.getvalue()


def existing_notes(path: Path) -> dict[str, str]:
    """Read back the human prose in the `note` column, keyed by date."""
    if not path.exists():
        return {}
    with path.open(newline="") as handle:
        return {
            row["date"]: row.get("note") or ""
            for row in csv.DictReader(handle)
            if (row.get("note") or "").strip()
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from", dest="first", type=int, default=FIRST_YEAR)
    parser.add_argument("--to", dest="last", type=int, default=LAST_YEAR)
    parser.add_argument(
        "--year",
        type=int,
        help="shorthand for --from Y --to Y; `--year 2019 --stdout` is the "
        "reproduction check this script's docstring rests on",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="print the table instead of writing it (writes nothing at all)",
    )
    parser.add_argument("--path", type=Path, default=TABLE)
    args = parser.parse_args(argv)

    first = args.year if args.year else args.first
    last = args.year if args.year else args.last
    if last < first:
        parser.error(f"--to {last} is before --from {first}")

    rows = derive(first, last)
    text = render(rows, existing_notes(args.path))

    if args.stdout:
        sys.stdout.write(text)
        return 0

    before = args.path.read_text() if args.path.exists() else None
    args.path.write_text(text)
    years = sorted({day.year for day, _ in rows})
    observed = sum(1 for _, name in rows if name.endswith("(observed)"))
    print(
        f"[holidays] {len(rows)} rows covering {years[0]}..{years[-1]} "
        f"({observed} observed-day rows) -> {args.path.relative_to(REPO_ROOT)}"
    )
    print(
        "[holidays] unchanged" if before == text
        else "[holidays] the table CHANGED — read the diff before committing it"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised through `make holidays`
    raise SystemExit(main())
