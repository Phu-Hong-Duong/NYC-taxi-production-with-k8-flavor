"""The calendar features — a lookup table, deliberately, and not a library.

Dossier row 4: a Tuesday in July is not July 4th. Traffic collapses, airport runs
spike, and the clock features (`hour`, `dayofweek`) cannot see any of it, because
a holiday is a Thursday like any other as far as `dt.dayofweek` is concerned.

Two decisions recorded rather than assumed:

1. **A committed CSV, not a new runtime dependency.** `holidays` and
   `pandas.tseries.holiday` both exist and both would work. Neither earns a
   dependency in the training AND serving path for ten rows of data that change
   once a year — and a table in the repo is a table a reviewer can read, which a
   library's internal rule set is not. `data/reference/us_federal_holidays.csv`
   is the whole feature.

2. **The gap is named, not silent.** This is the FEDERAL calendar. New York's own
   traffic days — the Thanksgiving and Pride parades, the UN General Assembly
   week, the marathon — close streets and are not in it, so the feature is
   weaker here than the same feature would be for a city with a federal-holiday
   traffic profile. Recorded in the dossier at row 4 and repeated here because
   this is where somebody would otherwise assume the coverage is complete.

A date outside the table's covered years RAISES rather than returning "not a
holiday": a silent False for 2020 would look exactly like a correct answer, and
the feature would quietly decay into a constant.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

HOLIDAY_TABLE = "data/reference/us_federal_holidays.csv"

#: How far from a holiday still counts as "near". One day either side: the
#: traffic anomaly of July 4th reaches July 3rd's evening and July 5th's morning,
#: and a wider window would start calling an ordinary week a holiday week.
NEAR_DAYS = 1


@dataclass(frozen=True)
class HolidayCalendar:
    """The set of holiday dates and the years it can answer for."""

    holidays: frozenset[np.datetime64]
    near: frozenset[np.datetime64]
    years: frozenset[int]

    def assert_covers(self, dates: np.ndarray) -> None:
        years = pd.DatetimeIndex(dates[~pd.isna(dates)]).year.unique()
        missing = sorted(set(int(y) for y in years) - self.years)
        if missing:
            raise ValueError(
                f"{HOLIDAY_TABLE} covers {sorted(self.years)} but the frame carries "
                f"{missing}. Returning 'not a holiday' for an uncovered year would look "
                "exactly like a correct answer, so this raises instead. Add the rows."
            )


@lru_cache(maxsize=4)
def load_calendar(path: str = HOLIDAY_TABLE) -> HolidayCalendar:
    table = Path(path)
    if not table.exists():
        raise FileNotFoundError(f"{path} is missing — it is a committed artifact")
    frame = pd.read_csv(table, parse_dates=["date"])
    dates = pd.DatetimeIndex(frame["date"])
    near: set[np.datetime64] = set()
    for offset in range(-NEAR_DAYS, NEAR_DAYS + 1):
        near.update((dates + pd.Timedelta(days=offset)).to_numpy())
    return HolidayCalendar(
        holidays=frozenset(dates.to_numpy()),
        # "near" excludes the holidays themselves: the two flags answer different
        # questions, and a near-flag that is 1 on the day as well would make the
        # holiday flag redundant with it.
        near=frozenset(near - set(dates.to_numpy())),
        years=frozenset(int(y) for y in dates.year.unique()),
    )


def flags(timestamps: pd.Series, calendar: HolidayCalendar | None = None) -> dict[str, np.ndarray]:
    """`is_holiday`, `is_near_holiday`, `is_business_day` for a frame of pickups."""
    calendar = calendar or load_calendar()
    days = timestamps.dt.normalize().to_numpy()
    calendar.assert_covers(days)
    is_holiday = np.isin(days, list(calendar.holidays)).astype("int16")
    is_near = np.isin(days, list(calendar.near)).astype("int16")
    weekday = (timestamps.dt.dayofweek.to_numpy() < 5).astype("int16")
    return {
        "is_holiday": is_holiday,
        "is_near_holiday": is_near,
        # A business day is a weekday that is not a holiday — the thing a
        # commuter-flow model actually wants, and not the same as `is_weekend`
        # inverted, which is the mistake this line exists to not make.
        "is_business_day": (weekday & (1 - is_holiday)).astype("int16"),
    }
