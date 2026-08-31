"""M5-S2: the holiday table, its deriver, and what F-019's fix must not disturb.

Three classes of defect, none of which announces itself:

1. **A wrong holiday date.** `is_holiday` is quietly wrong on exactly the days
   the feature exists for, and no downstream check notices — the column is still
   an int16 of the right length. The rules are statute (5 U.S.C. §6103), so they
   are testable against known answers and against the ten rows a human wrote from
   the OPM calendar at M3-S3, months before the deriver existed.
2. **A table extension that MOVES A MEASURED NUMBER.** Every M1–M4 verdict was
   computed with the ten-row table. If extending it changed one holiday or one
   near-holiday day inside 2019-01..2019-08, the champion's own gate numbers
   would silently stop being reproducible. Asserted directly, on the window.
3. **A guard softened while nobody was looking.** F-019 is closed by extending
   the table AND typing the boundary — NOT by making `assert_covers` lenient. A
   test that only checked "2026 works now" would stay green if somebody deleted
   the raise.
"""

from __future__ import annotations

import csv
import datetime as dt
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from conftest import REPO

from taxi_mlops.features import calendar

TABLE = REPO / "data" / "reference" / "us_federal_holidays.csv"
DERIVER = REPO / "scripts" / "derive_us_federal_holidays.py"

sys.path.insert(0, str(REPO / "scripts"))
import derive_us_federal_holidays as deriver  # noqa: E402

pytestmark = pytest.mark.unit

#: The eight months every M1–M4 number was measured over.
MEASURED_WINDOW = (dt.date(2019, 1, 1), dt.date(2019, 8, 31))


def committed_rows() -> list[dict[str, str]]:
    with TABLE.open(newline="") as handle:
        return list(csv.DictReader(handle))


def test_the_rules_reproduce_the_ten_hand_written_2019_rows_exactly():
    """The deriver's whole claim to being trusted.

    Those ten rows were written by a human at M3-S3 from the published federal
    calendar, long before `scripts/derive_us_federal_holidays.py` existed. So
    agreement is evidence about the RULES and not about their author — including
    the one a reader is most likely to get wrong, Juneteenth, which is federal
    only from 2021 and must therefore be ABSENT here."""
    rendered = deriver.render(deriver.derive(2019, 2019), deriver.existing_notes(TABLE))
    expected = "".join(TABLE.read_text().splitlines(keepends=True)[:11])
    assert rendered == expected
    assert "Juneteenth" not in rendered


def test_make_holidays_is_idempotent_against_the_committed_table():
    """`make holidays` re-run on a clean tree must change nothing.

    A deriver whose output drifts from what is committed makes every later diff
    unreadable, and would mean the table in git is not the table the rules
    describe."""
    rendered = deriver.render(
        deriver.derive(deriver.FIRST_YEAR, deriver.LAST_YEAR), deriver.existing_notes(TABLE)
    )
    assert rendered == TABLE.read_text()


def test_the_deriver_runs_as_a_script_and_writes_nothing_under_stdout():
    """`--stdout` is the reproduction check's transport; it must not touch the file."""
    before = TABLE.read_bytes()
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(DERIVER), "--year", "2019", "--stdout"],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO,
    )
    assert result.stdout.startswith("date,name,note\n")
    assert TABLE.read_bytes() == before


@pytest.mark.parametrize(
    ("date", "name"),
    [
        # Movable feasts, checked against the published federal calendar.
        ("2026-01-19", "Birthday of Martin Luther King Jr."),
        ("2026-11-26", "Thanksgiving Day"),
        ("2030-05-27", "Memorial Day"),
        ("2024-10-14", "Columbus Day"),
        # Fixed dates.
        ("2025-06-19", "Juneteenth National Independence Day"),
        ("2027-12-25", "Christmas Day"),
    ],
)
def test_known_dates_are_in_the_table_under_their_statutory_names(date: str, name: str):
    rows = {(row["date"], row["name"]) for row in committed_rows()}
    assert (date, name) in rows


def test_juneteenth_starts_in_2021_and_not_before():
    by_year = {
        int(row["date"][:4])
        for row in committed_rows()
        if row["name"].startswith("Juneteenth")
    }
    assert min(by_year) == 2021
    assert by_year == set(range(2021, deriver.LAST_YEAR + 1))


def test_a_weekend_holiday_produces_both_the_date_and_the_observed_day():
    """Decision 1 in the deriver: both days are anomalous, so both are rows.

    2021-07-04 was a Sunday, so the day off moved to Monday the 5th. Picking one
    of the two would be picking which traffic anomaly to be blind to."""
    rows = {(row["date"], row["name"]) for row in committed_rows()}
    assert ("2021-07-04", "Independence Day") in rows
    assert ("2021-07-05", "Independence Day (observed)") in rows
    assert dt.date(2021, 7, 4).weekday() == deriver.SUNDAY


def test_an_observed_day_may_land_in_the_previous_year():
    """2022-01-01 is a Saturday, so its day off is 2021-12-31 — which is why the
    deriver sorts once at the end rather than per year."""
    rows = {(row["date"], row["name"]) for row in committed_rows()}
    assert ("2021-12-31", "New Year's Day (observed)") in rows


def test_the_human_note_on_the_mlk_row_survived_the_extension():
    """The `note` column is a reviewer's prose (F-006's cliff shares MLK Day).
    A deriver that erased it would be one nobody runs twice."""
    note = next(row["note"] for row in committed_rows() if row["date"] == "2019-01-21")
    assert "congestion_surcharge" in note and "F-006" in note


def test_extending_the_table_changed_no_flag_inside_the_measured_window():
    """THE regression that matters: every M1-M4 number was measured with the
    ten-row table, and a changed holiday or near-holiday day inside 2019-01..08
    would make the champion's own gate numbers unreproducible.

    Compared as SETS over the window rather than by reading the diff, because a
    near-holiday day can be introduced by a row in a different year entirely
    (2019-12-31's neighbour is 2020-01-01)."""
    start, end = MEASURED_WINDOW
    now = calendar.load_calendar()

    ten_row_table = deriver.render(deriver.derive(2019, 2019), deriver.existing_notes(TABLE))
    original = _calendar_from_text(ten_row_table)

    def within(days) -> set:
        return {d for d in days if start <= pd.Timestamp(d).date() <= end}

    assert within(now.holidays) == within(original.holidays)
    assert within(now.near) == within(original.near)


def test_the_uncovered_year_guard_is_still_a_raise():
    """F-019 is closed by a longer table plus a typed boundary — never by making
    this lenient. A silent 'not a holiday' for an uncovered year looks exactly
    like a correct answer, which is the whole reason the raise exists."""
    loaded = calendar.load_calendar()
    beyond = max(loaded.years) + 1
    with pytest.raises(ValueError) as excinfo:
        loaded.assert_covers(np.array([np.datetime64(f"{beyond}-03-05")]))
    assert calendar.HOLIDAY_TABLE in str(excinfo.value)
    assert str(beyond) in str(excinfo.value)


def test_the_horizon_is_a_stated_number_and_the_table_reaches_it():
    years = {int(row["date"][:4]) for row in committed_rows()}
    assert max(years) == deriver.LAST_YEAR
    assert min(years) == deriver.FIRST_YEAR


def _calendar_from_text(text: str) -> calendar.HolidayCalendar:
    """Build a HolidayCalendar from CSV text, through the module's own loader."""
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as handle:
        handle.write(text)
        path = handle.name
    try:
        return calendar.load_calendar(path)
    finally:
        Path(path).unlink()
