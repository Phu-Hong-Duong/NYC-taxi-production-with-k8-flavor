"""Point-in-time aggregates — congestion has memory, and remembering it is where
this problem leaks.

Dossier rows 14/15/16, and dossier §4 traps 1-2. This is the single strongest
feature family in every source we read and it is one line of code away from
disqualifying:

- **Per-trip speed is the target wearing a mask** (speed = distance / duration).
  It is never a feature. What IS legal is an *aggregate* of historical speed,
  because a historical average over other people's trips is knowable before this
  rider's trip happens. `pu_hour_mean_speed_kmh` is computed from the CENTROID
  distance (`zones.geometry`), never the meter's `trip_distance`, so no excluded
  column enters even the aggregate.
- **An aggregate fitted over all months inflates validation** while a month it
  never saw stays honest. The famous top-6% solution in `docs/feature_dossier.md`
  does exactly this and is correct *in a competition*: its group means are taken
  over train+test concatenated. Nothing about the code is wrong; the split is.

So the constraint is in the type, not in a comment. `fit` builds ONE lookup per
month cutoff, and a row in train month *k* is only ever served the table built
from months 1..k-1. A row in the first train month gets NaN — not a number
containing its own answer. Rows outside the fitted months (val, test) get the
table built from every fitted month, which for them IS the point-in-time
history, since the fitted months all precede them.

`point_in_time=False` exists for exactly one caller: M3-S3's mandated leakage
red-team, which fits across every month on purpose so the inflation can be
watched and measured (`docs/leakage_redteam_m3.md`). It refuses to be silent —
the tables carry the flag and every builder prints it.

**Window-size stability, which is not obvious and is load-bearing.** The cutoff
window GROWS month by month, so any statistic that grows with sample size would
encode "how late in the training window this row is" — `month` re-entering by
the back door, which CLAUDE.md forbids outright. Medians and means are
window-stable; raw counts are not, which is why `pu_hour_trips_per_day` is a
RATE (trips ÷ distinct days in the window) and not a count.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import zones

#: Dense-array key spaces. TLC ids are 1..265, so 266 covers them with 0 free for
#: the out-of-range sentinel `zones._clip_ids` produces.
_ZONE_SLOTS = zones.MAX_ZONE_ID + 1
_OD_SLOTS = _ZONE_SLOTS * _ZONE_SLOTS
_PU_HOUR_SLOTS = _ZONE_SLOTS * 24

AGGREGATE_FEATURES = ("od_median_duration_min", "pu_hour_mean_speed_kmh", "pu_hour_trips_per_day")


@dataclass(frozen=True)
class AggregateTables:
    """Three dense lookups fitted on one window of months. NaN where unseen."""

    od_median: np.ndarray
    pu_hour_speed: np.ndarray
    pu_hour_rate: np.ndarray
    months: tuple[str, ...]
    rows: int

    @classmethod
    def empty(cls) -> AggregateTables:
        """The first train month's table: no history, therefore no numbers.

        Not zeros. A zero would be a measurement of an empty street; NaN is
        LightGBM's documented "I was not told", which is the truth here.
        """
        return cls(
            od_median=np.full(_OD_SLOTS, np.nan, dtype="float32"),
            pu_hour_speed=np.full(_PU_HOUR_SLOTS, np.nan, dtype="float32"),
            pu_hour_rate=np.full(_PU_HOUR_SLOTS, np.nan, dtype="float32"),
            months=(),
            rows=0,
        )


@dataclass(frozen=True)
class PointInTimeAggregates:
    """A table per month cutoff, plus the one served to months after the window."""

    by_month: dict[str, AggregateTables]
    full: AggregateTables
    fitted_months: tuple[str, ...]
    point_in_time: bool

    def describe(self) -> str:
        if not self.point_in_time:
            return (
                f"[aggregates] LEAKY BY REQUEST: one table fitted across all of "
                f"{','.join(self.fitted_months)} ({self.full.rows:,} rows) and served to "
                "every row including the months it was built from. Red-team only."
            )
        lines = [
            f"[aggregates] point-in-time over {len(self.fitted_months)} fitted month(s): "
            f"{','.join(self.fitted_months)}"
        ]
        for month in self.fitted_months:
            table = self.by_month[month]
            history = ",".join(table.months) if table.months else "NOTHING (first month)"
            lines.append(f"[aggregates]   {month} is served history {history}")
        lines.append(
            f"[aggregates]   any later month is served all {self.full.rows:,} fitted rows"
        )
        return "\n".join(lines)


def month_key(timestamps: pd.Series) -> pd.Series:
    """`YYYY-MM` per row, derived from the pickup timestamp.

    Deriving it here rather than reading a `month` column is deliberate: `month`
    is an EXCLUDED column (it is a reporting dimension, never a feature), and a
    join key is not a feature. It never reaches the matrix — the output of
    `build_features` is checked against the exclusion registry either way.
    """
    return timestamps.dt.strftime("%Y-%m")


def _od_index(pu: np.ndarray, do: np.ndarray) -> np.ndarray:
    return pu.astype("int64") * _ZONE_SLOTS + do.astype("int64")


def _pu_hour_index(pu: np.ndarray, hour: np.ndarray) -> np.ndarray:
    return pu.astype("int64") * 24 + hour.astype("int64")


def _dense(keys: np.ndarray, values: np.ndarray, slots: int) -> np.ndarray:
    out = np.full(slots, np.nan, dtype="float32")
    out[keys] = values
    return out


def _fit_window(
    pu: np.ndarray,
    do: np.ndarray,
    hour: np.ndarray,
    duration: np.ndarray,
    distance_km: np.ndarray,
    days: int,
    months: tuple[str, ...],
) -> AggregateTables:
    """Build the three lookups from one window of rows."""
    od_key = _od_index(pu, do)
    pu_hour_key = _pu_hour_index(pu, hour)

    frame = pd.DataFrame(
        {
            "od": od_key,
            "puh": pu_hour_key,
            "duration": duration,
            # km/h over the STRAIGHT LINE between zone centroids. Lower than a
            # speedometer would read (median circuity is 1.2952, dossier §3a) —
            # which is fine: it is a consistent congestion proxy, not a claim
            # about how fast anybody drove.
            "speed": np.where(duration > 0, distance_km / (duration / 60.0), np.nan),
        }
    )
    od_median = frame.groupby("od", sort=False)["duration"].median()
    grouped = frame.groupby("puh", sort=False)
    speed = grouped["speed"].mean()
    counts = grouped.size()
    return AggregateTables(
        od_median=_dense(od_median.index.to_numpy(), od_median.to_numpy(), _OD_SLOTS),
        pu_hour_speed=_dense(speed.index.to_numpy(), speed.to_numpy(), _PU_HOUR_SLOTS),
        # A RATE, not a count — see the module docstring on window-size stability.
        pu_hour_rate=_dense(
            counts.index.to_numpy(), counts.to_numpy() / max(days, 1), _PU_HOUR_SLOTS
        ),
        months=months,
        rows=int(len(frame)),
    )


def fit(
    frame: pd.DataFrame,
    target: str,
    *,
    point_in_time: bool = True,
    zone_table: zones.ZoneTable | None = None,
    timestamp: str = "tpep_pickup_datetime",
) -> PointInTimeAggregates:
    """Fit the aggregate lookups. The frame is TRAIN rows only — enforced by the caller.

    `point_in_time=False` is the leakage red-team's switch and nothing else's; it
    is named in the returned object and printed by `describe()`, because a leaky
    table that does not announce itself is the entire failure mode.
    """
    for column in (timestamp, "PULocationID", "DOLocationID", target):
        if column not in frame.columns:
            raise ValueError(
                f"aggregates.fit needs {column!r}; the frame carries {list(frame.columns)}"
            )
    pu = zones._clip_ids(frame["PULocationID"])
    do = zones._clip_ids(frame["DOLocationID"])
    hour = frame[timestamp].dt.hour.to_numpy(dtype="int64")
    duration = frame[target].to_numpy(dtype="float64")
    distance = zones.geometry(frame["PULocationID"], frame["DOLocationID"], zone_table).haversine_km
    months_series = month_key(frame[timestamp])
    months_array = months_series.to_numpy()
    day_index = frame[timestamp].dt.normalize()
    fitted = tuple(sorted(pd.unique(months_series)))

    def window(mask: np.ndarray, window_months: tuple[str, ...]) -> AggregateTables:
        if not mask.any():
            return AggregateTables.empty()
        return _fit_window(
            pu[mask],
            do[mask],
            hour[mask],
            duration[mask],
            distance[mask],
            days=int(day_index[mask].nunique()),
            months=window_months,
        )

    everything = window(np.ones(len(frame), dtype=bool), fitted)
    if not point_in_time:
        return PointInTimeAggregates(
            by_month={month: everything for month in fitted},
            full=everything,
            fitted_months=fitted,
            point_in_time=False,
        )

    by_month: dict[str, AggregateTables] = {}
    for position, month in enumerate(fitted):
        history = fitted[:position]
        by_month[month] = window(np.isin(months_array, history), history) if history else (
            AggregateTables.empty()
        )
    return PointInTimeAggregates(
        by_month=by_month, full=everything, fitted_months=fitted, point_in_time=True
    )


def transform(
    tables: PointInTimeAggregates,
    frame: pd.DataFrame,
    *,
    timestamp: str = "tpep_pickup_datetime",
) -> dict[str, np.ndarray]:
    """Serve each row the table its own month is entitled to. Unseen key -> NaN."""
    pu = zones._clip_ids(frame["PULocationID"])
    do = zones._clip_ids(frame["DOLocationID"])
    hour = frame[timestamp].dt.hour.to_numpy(dtype="int64")
    od_key = _od_index(pu, do)
    pu_hour_key = _pu_hour_index(pu, hour)
    months = month_key(frame[timestamp]).to_numpy()

    out = {
        "od_median_duration_min": np.empty(len(frame), dtype="float32"),
        "pu_hour_mean_speed_kmh": np.empty(len(frame), dtype="float32"),
        "pu_hour_trips_per_day": np.empty(len(frame), dtype="float32"),
    }
    # Every row belongs to exactly one window: its own month if that month was
    # fitted (a train row), otherwise the full history (a val or test row, which
    # by construction comes after every fitted month).
    assigned = np.zeros(len(frame), dtype=bool)
    for month, table in tables.by_month.items():
        mask = months == month
        if not mask.any():
            continue
        assigned |= mask
        out["od_median_duration_min"][mask] = table.od_median[od_key[mask]]
        out["pu_hour_mean_speed_kmh"][mask] = table.pu_hour_speed[pu_hour_key[mask]]
        out["pu_hour_trips_per_day"][mask] = table.pu_hour_rate[pu_hour_key[mask]]
    rest = ~assigned
    if rest.any():
        out["od_median_duration_min"][rest] = tables.full.od_median[od_key[rest]]
        out["pu_hour_mean_speed_kmh"][rest] = tables.full.pu_hour_speed[pu_hour_key[rest]]
        out["pu_hour_trips_per_day"][rest] = tables.full.pu_hour_rate[pu_hour_key[rest]]
    return out
