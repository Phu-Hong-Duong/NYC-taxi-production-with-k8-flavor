#!/usr/bin/env python
"""Build the DECLARED row set the retrieval parity and the PIT proof are measured on.

M8-S3. Run ONCE with `--refresh`; its output — `infra/feast/retrieval_rows.csv` —
is COMMITTED and read thereafter. The comparison never samples: a set drawn at
run time gives a number that changes every run, a red team that cannot plant a
cause, and a set that never contains the rows that actually break things. That is
M5-S3's argument for `parity.HAZARDS`, applied a second time, and it is why
sixteen of these rows ARE `parity.HAZARDS` — imported, never retyped, so the wire
seam and the store seam are measured against one row set.

Runs on THIS side of the quarantine (pandas 3.0.5); imports `taxi_mlops` and
never `feast` (M8 law 4, AST-pinned in `tests/unit/test_feast_repo.py`).

The three strata and their reasons are argued in `docs/feast_pit_m8.md` §3. The
one worth restating here is `month-boundary`: six pairs of rows straddling a
train-month boundary by two minutes each. Adjacent rows differ by 120 seconds and
must be served DIFFERENT windows, because the window a row is entitled to changes
at the instant the month does. Two minutes is the smallest interval over which
the join's behaviour is visible, and a boundary that a naive join cannot see is
exactly where the leakage lives.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from taxi_mlops.data import analyst  # noqa: E402
from taxi_mlops.data.config import load_config, load_splits  # noqa: E402
from taxi_mlops.serving import parity  # noqa: E402

ROWS_CSV = REPO_ROOT / "infra" / "feast" / "retrieval_rows.csv"

FIELDS = ("row_id", "stratum", "why", "pickup_datetime", "PULocationID", "DOLocationID",
          "passenger_count")

#: The seed the drawn strata were drawn at. Recorded rather than defaulted: an
#: unreproducible draw in a committed artifact is a number nobody can check twice
#: (M7-S3's Evidently note, same rule).
#:
#: The draw is `ORDER BY hash(<the row's own key columns>, SEED) LIMIT n`, and
#: that is a correction rather than a preference. The first version asked DuckDB
#: for `USING SAMPLE reservoir(15 ROWS) REPEATABLE (seed)` after a `WHERE`, and
#: got **11 ordinary rows, 1 no-geometry row and ZERO airport rows** out of a
#: stratum holding 3,237,471 of them — the sample is taken from the SCAN and the
#: filter is applied to what survives it, so a selective stratum can come back
#: empty while looking like a sample that simply found nothing. A draw that
#: silently returns fewer rows than asked for is the shape of gotcha #78: an
#: empty stratum and a stratum that does not exist render identically. Ordering
#: by a hash is deterministic, uses no sampling engine, and cannot return short.
SEED = 20260821

#: The OD pair the boundary rows use. 161 -> 237 (Midtown Center -> Upper East
#: Side South) is the busiest ordinary pair in this data, so the window it is
#: served is dense in every month and a median that moves between windows moves
#: for a reason rather than for want of rows.
BOUNDARY_PU, BOUNDARY_DO = 161, 237

#: `WHERE` clauses, one per drawn stratum, with the reason each is in the set.
#: These are M6-S3's shadow strata kept verbatim so the two stories' samples are
#: comparable.
STRATA: tuple[tuple[str, str, str], ...] = (
    (
        "ordinary",
        "the common case: both zones have geometry, neither is an airport, "
        "5-30 minutes — the rows that dominate every published number",
        "PULocationID BETWEEN 1 AND 263 AND DOLocationID BETWEEN 1 AND 263 "
        "AND PULocationID NOT IN (1,132,138) AND DOLocationID NOT IN (1,132,138) "
        "AND trip_duration_minutes BETWEEN 5 AND 30",
    ),
    (
        "airport",
        "JFK/LGA/EWR: 8.8% of trips carrying 1.86-2.35x the error across three "
        "measurements (docs/error_memo_m2.md 7 row 2) — the segment the catalog's "
        "airport_regime_flag candidate exists for",
        "PULocationID IN (1,132,138) OR DOLocationID IN (1,132,138)",
    ),
    (
        "no-geometry",
        "zone 264/265 (TLC 'Unknown'): NO ROW in zone_static by design (DR-04 "
        "condition 1), so the store must answer null and our path must report "
        "has_geometry = 0 — the two-sided assertion of the tolerance argument",
        "PULocationID > 263 OR DOLocationID > 263",
    ),
    (
        "long-trip",
        "the 100-120 min band the contract admits, where KPI-12 is 0.103% and the "
        "champion's ceiling lives (docs/error_memo_m2.md 5)",
        "trip_duration_minutes >= 100",
    ),
)

PER_STRATUM = 15


def _boundary_rows(train_months: tuple[str, ...]) -> list[dict[str, object]]:
    """Two rows per train-month boundary, 120 seconds apart.

    The stamps are DERIVED from the configured train months, never typed: the
    last minute of month *k* and the first minute of month *k+1*. The pair
    straddling the final train month reaches into the val month, which is the one
    boundary where the later row is served the FULL window — the same transition
    `aggregates.transform` makes when it falls through to `tables.full`.
    """
    import pandas as pd

    out: list[dict[str, object]] = []
    for month in train_months:
        period = pd.Period(month, freq="M")
        end = period.end_time.floor("min")  # last minute of the month
        start = (period + 1).start_time + pd.Timedelta(minutes=1)
        for stamp, side in ((end, "before"), (start, "after")):
            out.append(
                {
                    "stratum": "month-boundary",
                    "why": (
                        f"{side} the {month}/{(period + 1)} boundary, 120s from its twin: "
                        "the two rows MUST be served different windows, and a naive join "
                        "cannot tell them apart"
                    ),
                    "pickup_datetime": stamp.strftime("%Y-%m-%dT%H:%M:%S"),
                    "PULocationID": BOUNDARY_PU,
                    "DOLocationID": BOUNDARY_DO,
                    "passenger_count": 1.0,
                }
            )
    return out


def _hazard_rows() -> list[dict[str, object]]:
    """The sixteen rows `make parity` measures the wire with — imported, not retyped."""
    return [
        {
            "stratum": "hazard",
            "why": f"{hazard.name}: {hazard.why}",
            "pickup_datetime": hazard.request.pickup_datetime,
            "PULocationID": hazard.request.pu_location_id,
            "DOLocationID": hazard.request.do_location_id,
            "passenger_count": hazard.request.passenger_count,
        }
        for hazard in parity.HAZARDS
    ]


def _drawn_rows() -> list[dict[str, object]]:
    """A deterministic hash-ordered draw per stratum from `trips_train`.

    It REFUSES a short draw. A stratum that comes back with fewer rows than
    `PER_STRATUM` is either empty or being filtered by something the caller did
    not intend, and both look exactly like a small sample once the CSV is
    committed — see `SEED`'s note for the version of this that shipped zero
    airport rows out of three million and said nothing.
    """
    out: list[dict[str, object]] = []
    with analyst.connect(load_config(), read_only=True) as connection:
        for name, why, where in STRATA:
            frame = connection.execute(
                "SELECT strftime(tpep_pickup_datetime, '%Y-%m-%dT%H:%M:%S') AS pickup, "
                "PULocationID, DOLocationID, passenger_count "
                f"FROM trips_train WHERE {where} "
                "ORDER BY hash(tpep_pickup_datetime, PULocationID, DOLocationID, "
                f"passenger_count, {SEED}) LIMIT {PER_STRATUM}"
            ).fetchdf()
            print(f"[rows] {name:<14s} {len(frame):>3d} row(s) drawn (seed {SEED})")
            if len(frame) != PER_STRATUM:
                raise SystemExit(
                    f"[rows] stratum {name!r} returned {len(frame)} row(s), not "
                    f"{PER_STRATUM}. A short draw in a committed row set is "
                    "indistinguishable from a stratum nobody covered; fix the "
                    "predicate rather than accepting the rows it happened to yield."
                )
            for record in frame.to_dict("records"):
                out.append(
                    {
                        "stratum": name,
                        "why": why,
                        "pickup_datetime": record["pickup"],
                        "PULocationID": int(record["PULocationID"]),
                        "DOLocationID": int(record["DOLocationID"]),
                        "passenger_count": (
                            float(record["passenger_count"])
                            if record["passenger_count"] == record["passenger_count"]
                            else 1.0
                        ),
                    }
                )
    return out


def build() -> list[dict[str, object]]:
    splits = load_splits()
    rows = [*_hazard_rows(), *_boundary_rows(tuple(splits.train)), *_drawn_rows()]
    for index, row in enumerate(rows):
        row["row_id"] = index
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="rebuild and OVERWRITE the committed row set. Without it this prints "
        "what the committed file holds and changes nothing",
    )
    args = parser.parse_args(argv)

    if not args.refresh:
        if not ROWS_CSV.exists():
            print(f"[rows] {ROWS_CSV} does not exist — run with --refresh", file=sys.stderr)
            return 1
        with ROWS_CSV.open() as handle:
            existing = list(csv.DictReader(handle))
        counts: dict[str, int] = {}
        for row in existing:
            counts[row["stratum"]] = counts.get(row["stratum"], 0) + 1
        print(f"[rows] {ROWS_CSV.relative_to(REPO_ROOT)}: {len(existing)} declared row(s)")
        for stratum, count in sorted(counts.items()):
            print(f"[rows]   {stratum:<16s} {count:>3d}")
        return 0

    rows = build()
    ROWS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with ROWS_CSV.open("w", newline="") as handle:
        # `\n`, not csv's `\r\n` default: a committed artifact whose line endings
        # git has to normalise on every touch is a diff nobody can read.
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in FIELDS})
    print(f"[rows] wrote {len(rows)} declared row(s) -> {ROWS_CSV.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
