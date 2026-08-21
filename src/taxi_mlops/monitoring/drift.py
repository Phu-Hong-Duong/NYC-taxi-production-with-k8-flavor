"""Drift detection: what the champion was fitted on, against what the world is sending.

M7-S3. The loop this module is one link of: `make data-scoring` ingests a month
(M7-S1) -> `make predictions-scoring` scores it (M7-S2) -> **this** compares its
input distribution against the champion's training distribution and pushes the
comparison to Prometheus, where a rule decides whether anyone is woken up.

WHAT "DRIFT" MEANS HERE, STATED BEFORE ANY NUMBER
-------------------------------------------------
Two different questions get called drift and they have opposite remedies:

  * **Input drift** — the world is sending different requests than the model was
    fitted on. Detectable with NO ground truth, on the day the requests arrive.
    That is what this module measures and what the alert fires on.
  * **Performance decay** — the model's error got worse. Needs labels, which for
    an ETA arrive when the trip ENDS, and in a real deployment arrive far later
    than that. M7-S2's KPI-14/15/16 are that series, and they are deliberately
    NOT this module's alert: an alert that can only fire once the labels have
    landed is an alert that reports history.

We happen to hold labels for the scoring months, which makes it tempting to
alert on error directly. The reason not to is stated here so it is a decision
and not an omission: a production drift signal must work on the day of, and a
signal that quietly depends on labels would pass every test on this dataset and
fire never in the deployment it is written for.

THE REFERENCE IS THE TRAIN MONTHS, AND THAT IS NOT A CONVENIENCE
----------------------------------------------------------------
`reference = trips_train` (2019-01..06) — the rows the champion was actually
FITTED on. Not "the last 30 days", not the previous scoring month. Two reasons:

  1. **Point-in-time honesty** (gotcha #43's family). Drift is a statement about
     the distance between what the model LEARNED and what it is being asked. The
     only distribution that is "what it learned" is the fitting distribution.
  2. **A moving reference cannot see a slow move.** If January is compared with
     December and February with January, a world that drifts 3% a month never
     trips anything, and the model is a year out of date with a green board.
     This is the same argument as M7-S2's "no floor column, no margin": a
     comparison must be against the thing the verdict was made about.

Its cost, stated: the reference never moves, so a legitimately-changed world
keeps alerting until someone retrains and the reference is re-declared with the
new champion. That is the intended behaviour — a drift alert is a request for a
decision, not a fault report.

WHY THE ALERTING NUMBER IS COMPUTED IN SQL AND NOT BY EVIDENTLY
---------------------------------------------------------------
Evidently 0.7.21 IS in this project (probed against pandas 3.0.5 at M7-S3 entry;
resolves, imports and computes) and it runs here as a SECOND WITNESS —
`drift_evidently.py`, on a seeded sample, recorded in the run JSON. It is not
the alerting instrument, for one reason that is about arithmetic rather than
taste: five of the six monitored columns are CATEGORICAL, so their distribution
is completely described by value counts, and DuckDB computes value counts over
43,987,422 reference rows exactly, in seconds, with no sampling and no memory.
A sampled estimate of a quantity that can be computed exactly is a worse number
that also changes between runs — and a threshold compared against a number that
moves when nothing moved is the shape of every alert nobody trusts.

PSI, AND THE ONE CHOICE INSIDE IT THAT MATTERS
-----------------------------------------------
Population Stability Index over bin shares:

    PSI = sum_bins (cur_share - ref_share) * ln(cur_share / ref_share)

symmetric, zero when the distributions match, and unbounded above. The choice
that matters is what happens to a bin the reference never saw: `ln(x/0)` is
infinite, so an unseen category would make PSI infinite and useless. We floor
both shares at `SHARE_FLOOR` (one part in ten million, well below the smallest
share a 44M-row reference can resolve) AND report the unseen mass separately as
`unseen_share`, because "3% of this month's trips start in a zone the model
never saw" is a different sentence from "the mix shifted" and deserves not to be
laundered into one number. The numeric column's bin EDGES come from the
reference and only the reference — edges recomputed per current month would
compare each month against a ruler that month drew.

THE VOLUME DENOMINATOR IS THE CALENDAR, NOT THE DATA (F-051)
-------------------------------------------------------------
`volume_ratio` is trips-per-day over trips-per-day, and *which* days go in the
denominator decides whether the signal is monotonic in the thing it watches.
This module used to divide by `COUNT(DISTINCT observed date)`. Under that rule a
day on which the city took NO trips leaves the numerator and the denominator
**together**, so the ratio measures "how busy were the days that happened" —
which RISES as a shutdown deepens. REV measured it at the M7 review by deleting
2020-03's quietest days outright (a strictly worse shutdown): 0 zeroed -> 0.3913
FIRES, 6 -> 0.4768 fires, **8 -> 0.5143 SILENT**, 14 -> 0.6641. The same
arithmetic reads a truncated extract as healthy: a 20-of-31-day file is divided
by 20.

So the denominator is the **calendar days the window covers** —
`calendar.monthrange` per month, the same authority `verify-m7` §3 already
trusts for the mart's grain — and a day with no trips now costs the ratio
exactly what it should. This is the implementation catching up to the calendar
language `docs/slo_serving.md` §8.4 and A-9's own annotation already use
("trips per day"); **the 0.50 bar did not move.** All three shipped scoring
months hold every one of their calendar days, so their recorded ratios are
unchanged — and the report now carries `*_observed_days` beside `*_days` so
that claim is readable off the record instead of taken on trust.
"""

from __future__ import annotations

import calendar
import json
import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import duckdb

from ..data.analyst import database_path
from ..data.config import DataConfig, load_config

#: A share below which a bin is treated as "effectively absent". One part in ten
#: million: the reference holds ~44M rows, so the smallest share it can resolve
#: at all is ~2.3e-8, and this floor sits an order of magnitude above that. It
#: exists to keep `ln` finite, never to hide a category — see `unseen_share`.
SHARE_FLOOR = 1e-7

ColumnKind = Literal["categorical", "numeric"]


@dataclass(frozen=True)
class MonitoredColumn:
    """One signal, its kind, and why a quote-time drift monitor watches it."""

    name: str
    kind: ColumnKind
    expression: str
    why: str


#: THE MONITORED SET, and it is a subset of the model's inputs on purpose.
#:
#: The champion (feature set v2) eats 24 columns, but 19 of them are
#: DETERMINISTIC FUNCTIONS of the five below plus the calendar: the centroid
#: geometry is a lookup on (PULocationID, DOLocationID), the temporal extras are
#: arithmetic on the pickup timestamp, the holiday flags are a table join. A
#: monitor that watched all 24 would report 19 correlated restatements of five
#: facts, and its "share of columns drifted" — the number the alert reads —
#: would be dominated by however many derived columns happen to hang off the
#: signal that moved. Watching the SOURCES keeps that share interpretable.
#:
#: `trip_duration_minutes` is the sixth and it is not an input at all: it is the
#: TARGET. It is monitored because target drift and input drift have different
#: diagnoses (inputs the same + target moved = the relationship changed; both
#: moved = the world changed), and its metric is reported under its own id so it
#: can never be averaged into the input share the alert reads.
MONITORED_COLUMNS: tuple[MonitoredColumn, ...] = (
    MonitoredColumn(
        name="hour",
        kind="categorical",
        expression="CAST(EXTRACT(hour FROM tpep_pickup_datetime) AS BIGINT)",
        why=(
            "The strongest temporal feature and the one a demand shock moves first: "
            "a city that stops commuting loses its two rush hours before it loses "
            "anything else."
        ),
    ),
    MonitoredColumn(
        name="dayofweek",
        kind="categorical",
        expression="CAST(EXTRACT(dow FROM tpep_pickup_datetime) AS BIGINT)",
        why=(
            "Separates a weekday collapse from a weekend one. A lockdown flattens the "
            "weekday/weekend contrast the model relies on."
        ),
    ),
    MonitoredColumn(
        name="PULocationID",
        kind="categorical",
        expression="PULocationID",
        why=(
            "263 zones plus the two 'unknown' ids. Where trips START is the geography "
            "signal that moves when offices, airports or nightlife stop — and it is "
            "the key nine of the champion's geometry features are looked up on."
        ),
    ),
    MonitoredColumn(
        name="DOLocationID",
        kind="categorical",
        expression="DOLocationID",
        why=(
            "The other half of the OD pair. PU can hold still while DO moves — the "
            "airport run is a DO event, and `docs/error_memo_m2.md` §7 row 2 is about "
            "exactly those rows."
        ),
    ),
    MonitoredColumn(
        name="passenger_count",
        kind="categorical",
        expression="passenger_count",
        why=(
            "A weak feature and deliberately kept: it is the cheapest detector of a "
            "DATA-SIDE change (a vendor filling the field differently) as opposed to a "
            "world-side one, and telling those apart is the first question after a fire."
        ),
    ),
    MonitoredColumn(
        name="trip_duration_minutes",
        kind="numeric",
        expression="trip_duration_minutes",
        why=(
            "THE TARGET, monitored separately and never inside the input share. Inputs "
            "steady + target moved = the relationship changed under the model; both "
            "moved = the world changed. Opposite remedies."
        ),
    ),
)

#: Fixed bin edges for the numeric column, in minutes. Declared here rather than
#: derived per run: the contract admits 1..120 minutes (`configs/data.yaml`), so
#: the range is a property of the data contract and not of any month. Quantile
#: edges from the reference would be defensible too; fixed edges are preferred
#: because they are READABLE — "the 5-10 minute bin lost a third of its share" is
#: a sentence, and "decile 4 moved" is not.
DURATION_BIN_EDGES: tuple[float, ...] = (
    0.0, 3.0, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0, 25.0, 30.0, 45.0, 60.0, 120.0,
)


@dataclass
class ColumnDrift:
    """One column's comparison, with the parts that must not be averaged together."""

    column: str
    kind: ColumnKind
    psi: float
    #: Share of CURRENT rows in a bin/category the REFERENCE never held. Reported
    #: beside PSI and never folded into it: an unseen category is a different
    #: event from a re-weighted one.
    unseen_share: float
    reference_bins: int
    current_bins: int
    #: The bins that moved most, largest absolute share change first. This is what
    #: a human reads at 3am; the PSI is what the rule reads.
    top_moves: list[dict[str, float | str]] = field(default_factory=list)


@dataclass
class DriftReport:
    """One (reference, current month) comparison — the unit this module produces."""

    month: str
    reference: str
    reference_months: list[str]
    reference_rows: int
    current_rows: int
    #: Mean trips per CALENDAR DAY, both sides. Volume is the one marginal that
    #: cannot be averaged away (F-045): a month can hold its every distribution
    #: and simply contain half as much world.
    reference_trips_per_day: float
    current_trips_per_day: float
    volume_ratio: float
    columns: list[ColumnDrift]
    computed_at: str
    #: The denominators, and the days that actually held a trip beside them
    #: (F-051). `days` is what the ratio divides by — the calendar. `observed_days`
    #: is a diagnostic: when it is SHORTER than `days`, the window contains days on
    #: which nothing happened, which is exactly the event the old denominator
    #: hid. Defaulted so a record written before F-051 still loads.
    reference_days: int = 0
    current_days: int = 0
    reference_observed_days: int = 0
    current_observed_days: int = 0

    # ---- the numbers the alert reads -------------------------------------
    @property
    def input_columns(self) -> list[ColumnDrift]:
        """The five INPUT columns. The target is excluded, by name, deliberately."""
        return [c for c in self.columns if c.column != "trip_duration_minutes"]

    @property
    def target_drift(self) -> ColumnDrift | None:
        for column in self.columns:
            if column.column == "trip_duration_minutes":
                return column
        return None

    def drifted_share(self, column_bar: float) -> float:
        """Share of INPUT columns whose PSI is at or above the per-column bar."""
        inputs = self.input_columns
        if not inputs:
            return 0.0
        return sum(1 for c in inputs if c.psi >= column_bar) / len(inputs)

    @property
    def max_input_psi(self) -> float:
        inputs = self.input_columns
        return max((c.psi for c in inputs), default=0.0)

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["max_input_psi"] = self.max_input_psi
        return payload


def _psi(reference_shares: dict[str, float], current_shares: dict[str, float]) -> float:
    """PSI over the union of bins, both sides floored so `ln` stays finite.

    The union is walked in SORTED order, and that is not tidiness: float addition
    is not associative, so an unordered `set` walk makes the last bit of every PSI
    a function of Python's per-process string hash seed. Observed while re-running
    this module at M8-S1 — 2020-02's `hour` moved 0.0015194096507573718 ->
    0.001519409650757372 with nothing else changed. Nothing downstream reads the
    17th digit, but this module's own docstring argues for exact SQL counts over a
    sampled estimate on the grounds that a sampled number "changes between runs",
    and a number that changes between runs is not the shape to defend that with.
    """
    total = 0.0
    for key in sorted(set(reference_shares) | set(current_shares)):
        ref = max(reference_shares.get(key, 0.0), SHARE_FLOOR)
        cur = max(current_shares.get(key, 0.0), SHARE_FLOOR)
        total += (cur - ref) * math.log(cur / ref)
    return total


def _top_moves(
    reference_shares: dict[str, float],
    current_shares: dict[str, float],
    limit: int = 5,
) -> list[dict[str, float | str]]:
    moves = []
    for key in sorted(set(reference_shares) | set(current_shares)):
        ref = reference_shares.get(key, 0.0)
        cur = current_shares.get(key, 0.0)
        moves.append(
            {"bin": str(key), "reference_share": ref, "current_share": cur, "delta": cur - ref}
        )
    # Sort by size, then by bin name — a stable tie-break, for the same reason.
    moves.sort(key=lambda m: (-abs(float(m["delta"])), str(m["bin"])))
    return moves[:limit]


def _shares_categorical(
    connection: duckdb.DuckDBPyConnection, view: str, column: MonitoredColumn, where: str
) -> tuple[dict[str, float], int]:
    rows = connection.execute(
        f"SELECT CAST({column.expression} AS VARCHAR) AS bin, COUNT(*) AS n "  # noqa: S608
        f"FROM {view} WHERE {where} GROUP BY 1"
    ).fetchall()
    total = sum(int(n) for _, n in rows)
    if total == 0:
        return {}, 0
    return {str(b): int(n) / total for b, n in rows}, total


def _shares_numeric(
    connection: duckdb.DuckDBPyConnection, view: str, column: MonitoredColumn, where: str
) -> tuple[dict[str, float], int]:
    """Bin with the DECLARED edges. Anything outside them lands in an edge bin —
    it cannot happen under the contract (1..120 min) and the query says so rather
    than dropping rows silently."""
    cases = []
    for index in range(len(DURATION_BIN_EDGES) - 1):
        low, high = DURATION_BIN_EDGES[index], DURATION_BIN_EDGES[index + 1]
        cases.append(
            f"WHEN {column.expression} < {high} THEN '[{low:g},{high:g})'"
        )
    case_sql = "CASE " + " ".join(cases) + f" ELSE '[{DURATION_BIN_EDGES[-1]:g},inf)' END"
    rows = connection.execute(
        f"SELECT {case_sql} AS bin, COUNT(*) AS n FROM {view} "  # noqa: S608
        f"WHERE {where} AND {column.expression} IS NOT NULL GROUP BY 1"
    ).fetchall()
    total = sum(int(n) for _, n in rows)
    if total == 0:
        return {}, 0
    return {str(b): int(n) / total for b, n in rows}, total


def _shares(
    connection: duckdb.DuckDBPyConnection, view: str, column: MonitoredColumn, where: str
) -> tuple[dict[str, float], int]:
    if column.kind == "numeric":
        return _shares_numeric(connection, view, column, where)
    return _shares_categorical(connection, view, column, where)


def calendar_days(months: Sequence[str]) -> int:
    """How many days the window COVERS — the denominator `volume_ratio` divides by.

    F-051. Derived from the calendar (`YYYY-MM` -> `calendar.monthrange`) and never
    from the data, because the data is the numerator: letting a quiet day leave both
    sides at once makes the ratio non-monotonic in the collapse it exists to detect.
    """
    total = 0
    for month in months:
        year, mon = (int(part) for part in str(month).split("-")[:2])
        total += calendar.monthrange(year, mon)[1]
    return total


def _observed_days(connection: duckdb.DuckDBPyConnection, view: str, where: str) -> int:
    """Days on which at least one trip happened. A DIAGNOSTIC, never a denominator."""
    (count,) = connection.execute(
        f"SELECT COUNT(DISTINCT CAST(tpep_pickup_datetime AS DATE)) FROM {view} WHERE {where}"  # noqa: S608
    ).fetchone()
    return int(count or 0)


def trips_per_day(rows: int, days: int) -> float:
    """Rows over calendar days. Pure, so the monotonicity property can be tested."""
    return rows / days if days else 0.0


def compute_drift(
    month: str,
    *,
    cfg: DataConfig | None = None,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> DriftReport:
    """Compare one scoring month's input distribution against the TRAIN months.

    Reads the analyst layer only — `trips_train` and `trips_scoring`, both of
    which M1-S2/M7-S1 reconcile against the ingest reports that wrote them. No
    parquet path appears here, for M1-S2's reason: a renamed file must not be
    able to relabel data.
    """
    cfg = cfg or load_config()
    owned = connection is None
    connection = connection or duckdb.connect(str(database_path(cfg)), read_only=True)
    try:
        reference_months = [
            str(m)
            for (m,) in connection.execute(
                "SELECT DISTINCT month FROM trips_train ORDER BY 1"
            ).fetchall()
        ]
        ref_where = "1=1"
        cur_where = f"month = '{month}'"

        (current_rows,) = connection.execute(
            f"SELECT COUNT(*) FROM trips_scoring WHERE {cur_where}"  # noqa: S608
        ).fetchone()
        if not current_rows:
            raise ValueError(
                f"trips_scoring holds no rows for {month!r}. Ingest it first "
                "(`make data-scoring`) — a drift report over zero rows is not a "
                "quiet month, it is an absent one."
            )

        (reference_rows,) = connection.execute("SELECT COUNT(*) FROM trips_train").fetchone()

        columns: list[ColumnDrift] = []
        for column in MONITORED_COLUMNS:
            ref_shares, _ = _shares(connection, "trips_train", column, ref_where)
            cur_shares, _ = _shares(connection, "trips_scoring", column, cur_where)
            unseen = sum(
                share for key, share in cur_shares.items() if ref_shares.get(key, 0.0) <= 0.0
            )
            columns.append(
                ColumnDrift(
                    column=column.name,
                    kind=column.kind,
                    psi=_psi(ref_shares, cur_shares),
                    unseen_share=unseen,
                    reference_bins=len(ref_shares),
                    current_bins=len(cur_shares),
                    top_moves=_top_moves(ref_shares, cur_shares),
                )
            )

        ref_days = calendar_days(reference_months)
        cur_days = calendar_days([month])
        ref_per_day = trips_per_day(reference_rows, ref_days)
        cur_per_day = trips_per_day(current_rows, cur_days)

        return DriftReport(
            month=month,
            reference="train-2019",
            reference_months=reference_months,
            reference_rows=int(reference_rows),
            current_rows=int(current_rows),
            reference_trips_per_day=ref_per_day,
            current_trips_per_day=cur_per_day,
            volume_ratio=(cur_per_day / ref_per_day) if ref_per_day else 0.0,
            columns=columns,
            computed_at=datetime.now(UTC).isoformat(timespec="seconds"),
            reference_days=ref_days,
            current_days=cur_days,
            reference_observed_days=_observed_days(connection, "trips_train", ref_where),
            current_observed_days=_observed_days(connection, "trips_scoring", cur_where),
        )
    finally:
        if owned:
            connection.close()


def compute_split_drift(
    split: str,
    *,
    cfg: DataConfig | None = None,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> DriftReport:
    """The same comparison for a HELD-OUT 2019 split — this is the headroom leg.

    `docs/slo_serving.md` §8 argues the drift bar from the PSI of the val and
    test months against this same reference. Those months have a verdict already:
    the champion was measured on them and PROMOTED, so whatever distance they sit
    at is by construction a distance that did NOT warrant action. Setting the bar
    from data whose verdict exists is the only way to argue a drift threshold
    without setting it equal to the number the thing under test just produced
    (M7 law 4).
    """
    if split not in {"val", "test"}:
        raise ValueError(
            f"{split!r} is not a held-out split. The headroom leg reads val or test; "
            "reading 'train' would compare the reference with itself."
        )
    cfg = cfg or load_config()
    owned = connection is None
    connection = connection or duckdb.connect(str(database_path(cfg)), read_only=True)
    try:
        view = f"trips_{split}"
        (current_rows,) = connection.execute(f"SELECT COUNT(*) FROM {view}").fetchone()  # noqa: S608
        (reference_rows,) = connection.execute("SELECT COUNT(*) FROM trips_train").fetchone()
        reference_months = [
            str(m)
            for (m,) in connection.execute(
                "SELECT DISTINCT month FROM trips_train ORDER BY 1"
            ).fetchall()
        ]
        months = [
            str(m)
            for (m,) in connection.execute(
                f"SELECT DISTINCT month FROM {view} ORDER BY 1"  # noqa: S608
            ).fetchall()
        ]

        columns = []
        for column in MONITORED_COLUMNS:
            ref_shares, _ = _shares(connection, "trips_train", column, "1=1")
            cur_shares, _ = _shares(connection, view, column, "1=1")
            unseen = sum(
                share for key, share in cur_shares.items() if ref_shares.get(key, 0.0) <= 0.0
            )
            columns.append(
                ColumnDrift(
                    column=column.name,
                    kind=column.kind,
                    psi=_psi(ref_shares, cur_shares),
                    unseen_share=unseen,
                    reference_bins=len(ref_shares),
                    current_bins=len(cur_shares),
                    top_moves=_top_moves(ref_shares, cur_shares),
                )
            )

        ref_days = calendar_days(reference_months)
        cur_days = calendar_days(months)
        ref_per_day = trips_per_day(reference_rows, ref_days)
        cur_per_day = trips_per_day(current_rows, cur_days)

        return DriftReport(
            month="+".join(months),
            reference="train-2019",
            reference_months=reference_months,
            reference_rows=int(reference_rows),
            current_rows=int(current_rows),
            reference_trips_per_day=ref_per_day,
            current_trips_per_day=cur_per_day,
            volume_ratio=(cur_per_day / ref_per_day) if ref_per_day else 0.0,
            columns=columns,
            computed_at=datetime.now(UTC).isoformat(timespec="seconds"),
            reference_days=ref_days,
            current_days=cur_days,
            reference_observed_days=_observed_days(connection, "trips_train", "1=1"),
            current_observed_days=_observed_days(connection, view, "1=1"),
        )
    finally:
        if owned:
            connection.close()


def write_report(report: DriftReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n")
    return path
