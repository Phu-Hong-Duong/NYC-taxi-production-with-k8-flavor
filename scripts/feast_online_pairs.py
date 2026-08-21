#!/usr/bin/env python
"""The 100 DECLARED (entity, timestamp) pairs the online parity is measured on.

M8-S4. `infra/feast/online_pairs.csv` is a COMMITTED artifact; this script writes
it, and running it with `--refresh` changes the set every published number was
measured on. That is the M8-S3 rule for `retrieval_rows.csv`, inherited verbatim
and for the same reason: a sampled row set gives a number that changes every run,
a red team that cannot plant a cause, and — the real objection — the rows that
break a feature store are never the average ones.

**The first 88 rows are IMPORTED from `infra/feast/retrieval_rows.csv`, not
retyped.** M8-S3's offline seam and this story's online seam are then measured
against ONE row set, so a disagreement between the two tables is a fact about the
stores and never about two different populations. `tests/unit/test_feast_online.py`
compares the two files field by field.

**The 12 added rows are the hazards the ONLINE seam has and the offline one does
not**, each naming its own. They fall into three families:

*   **Keys the store cannot answer.** An unknown-zone pair (264 -> 265, neither is
    a place — DR-04 condition 1) and a zone id the TLC table has never held. A
    lookup must come back NULL, not raise, and — the half that matters — the
    offline store must decline the same rows. `one missing` is the load-bearing
    count in both tables.
*   **A duplicate entity key, deliberately exact.** Rows 90 and 91 are identical
    in every entity column AND in the timestamp. `get_historical_features`
    answers such a pair ONCE (F-056 cause 1, measured at M8-S3) while
    `get_online_features` answers per requested row: the two APIs legitimately
    disagree about the SHAPE of the answer, and a table that aligned them by
    position would manufacture a mismatch out of correct behaviour.
*   **The key that would show a wrong-stamp materialization first.** Row 92 is
    DERIVED, and its first design was refused BY THE DATA. The intent was a key
    whose newest source row predates the full window, so that a materialize
    quietly filtering on the window's end would leave it null — and no such key
    exists, because the point-in-time windows are CUMULATIVE (window *k* is
    fitted over months 1..*k*), which makes the full window's key set a superset
    of every earlier one's. That is a structural property and not luck, so the
    row was replaced rather than approximated: it is now the OD pair whose
    `od_median_duration_min` moves MOST between its earliest and its latest
    window stamp (the query is in the row's own `why`). Same job, strictly
    better instrument — if materialization served any stamp but the newest,
    this is the row where the error is largest, and it is measured against the
    exact value the offline store returns for the same instant.

Nothing here is sampled and nothing is random: every added row is a literal
chosen for a named reason, except row 92's zone ids, which are derived and then
written down so the next reader gets the constant rather than the scan.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROWS = REPO_ROOT / "infra" / "feast" / "retrieval_rows.csv"
PAIRS_CSV = REPO_ROOT / "infra" / "feast" / "online_pairs.csv"
OD_SOURCE = REPO_ROOT / "data" / "feast" / "od_window_stats.parquet"

FIELDS = (
    "row_id",
    "stratum",
    "why",
    "pickup_datetime",
    "PULocationID",
    "DOLocationID",
    "passenger_count",
)

#: The added rows, in order. `(stratum, why, pickup_datetime, PU, DO, passengers)`
#: — PU/DO of `None` on row 92 is filled in from the published source.
ADDED: tuple[tuple[str, str, str, int | None, int | None, float], ...] = (
    (
        "online-hazard",
        "unknown-zone-pair: 264 -> 265, TLC's two non-places. Neither has a centroid row "
        "by design (DR-04 condition 1), so BOTH stores must decline both halves; 264->264 "
        "is the largest single OD 'route' in the data, so this is ~1% of real traffic",
        "2019-06-14T13:05:00",
        264,
        265,
        1.0,
    ),
    (
        "online-hazard",
        "zone-out-of-range: 999 is an id the TLC lookup has never held. A store lookup on a "
        "key that cannot exist must return null, not raise — a driver that raises here turns "
        "a nonsense request into a 500 instead of a refused feature",
        "2019-06-14T13:06:00",
        999,
        1,
        1.0,
    ),
    (
        "online-hazard",
        "duplicate-entity-key (a of 2): identical to the next row in EVERY entity column and "
        "in the timestamp. get_historical_features answers the pair ONCE (F-056 cause 1); "
        "get_online_features answers per requested row. The disagreement is about the shape "
        "of the answer, not about a value",
        "2019-05-02T09:15:00",
        161,
        237,
        1.0,
    ),
    (
        "online-hazard",
        "duplicate-entity-key (b of 2): the exact twin of the previous row",
        "2019-05-02T09:15:00",
        161,
        237,
        1.0,
    ),
    (
        "online-hazard",
        "max-window-drift-od: DERIVED — the OD pair whose od_median_duration_min moves most "
        "between its EARLIEST and its LATEST window stamp in "
        "data/feast/od_window_stats.parquet (group by the pair, take the value at "
        "min(event_timestamp) and at max(event_timestamp), order by |difference| desc). "
        "Materialize keeps the latest row per key, so this is the row where serving any "
        "stamp but the newest shows up by the largest possible margin. It REPLACED an "
        "'absent from the full window' row that the data refused: the windows are "
        "cumulative, so no key's latest row is stale",
        "2019-06-14T13:07:00",
        None,
        None,
        1.0,
    ),
    (
        "online-hazard",
        "hour-0: midnight, the bottom end of pu_hour_window_stats' clock entity",
        "2019-06-03T00:12:00",
        161,
        230,
        1.0,
    ),
    (
        "online-hazard",
        "hour-23: the top end of the same clock, one row after the wrap",
        "2019-06-03T23:47:00",
        161,
        230,
        2.0,
    ),
    (
        "online-hazard",
        "calendar-horizon-2030: 2030-12-25 is inside the committed holiday table's coverage "
        "(F-019 derived it to 2030 and refuses beyond). A store that stops short of the "
        "table's own horizon would answer null on a date the quote path accepts",
        "2030-12-25T10:00:00",
        161,
        237,
        1.0,
    ),
    (
        "online-hazard",
        "calendar-dst-spring-forward: 2019-03-10, the day US clocks skip 02:00-03:00. The "
        "date_key is a calendar day and must be unaffected; the row exists so that stays a "
        "measured fact rather than an assumption",
        "2019-03-10T02:30:00",
        161,
        237,
        1.0,
    ),
    (
        "online-hazard",
        "calendar-leap-day: 2020-02-29 exists in the derived table and in no other year",
        "2020-02-29T12:00:00",
        161,
        237,
        1.0,
    ),
    (
        "online-hazard",
        "airport-to-airport: JFK (132) -> LGA (138). Both zones carry the segment whose "
        "error gap held at 1.86-2.35x across a regime change (docs/drift_memo_m7.md), and "
        "an OD pair of two airports is rare enough to test a thin cell",
        "2019-06-20T18:40:00",
        132,
        138,
        1.0,
    ),
    (
        "online-hazard",
        "same-zone-round-trip: 237 -> 237. A legitimate OD pair whose two entity join keys "
        "carry the same value — the composite-entity encoding must not collapse them",
        "2019-06-21T15:25:00",
        237,
        237,
        1.0,
    ),
)


def _max_window_drift_pair() -> tuple[int, int]:
    """The pair for row 92, asked of the published source rather than typed.

    The OD pair whose median duration moves most between its first and its last
    point-in-time window. Ties are broken by the key itself, so two runs over the
    same sources produce the same committed row.
    """
    if not OD_SOURCE.exists():
        raise SystemExit(
            f"[pairs] {OD_SOURCE} is missing — run `make feast-sources` first. Row 92's "
            "zone ids are DERIVED from it and must not be guessed."
        )
    frame = pd.read_parquet(
        OD_SOURCE,
        columns=["PULocationID", "DOLocationID", "event_timestamp", "od_median_duration_min"],
    )
    frame = frame.sort_values("event_timestamp")
    grouped = frame.groupby(["PULocationID", "DOLocationID"], sort=True)
    first = grouped["od_median_duration_min"].first()
    last = grouped["od_median_duration_min"].last()
    windows = grouped["event_timestamp"].nunique()
    drift = (last - first).abs()[windows > 1]
    if drift.empty:
        raise SystemExit(
            "[pairs] no OD pair appears in more than one window — row 92's hazard cannot be "
            "constructed against these sources. Do not substitute a single-window pair: it "
            "would test nothing and read as if it did."
        )
    ranked = sorted(drift.items(), key=lambda item: (-item[1], item[0]))
    (pu, do), moved = ranked[0]
    print(f"[pairs] row 92 derived: {int(pu)} -> {int(do)}, |drift| {moved:.4f} min across windows")
    return int(pu), int(do)


def build() -> list[dict[str, object]]:
    if not SOURCE_ROWS.exists():
        raise SystemExit(f"[pairs] {SOURCE_ROWS} is missing — M8-S3's committed row set")
    with SOURCE_ROWS.open() as handle:
        inherited = list(csv.DictReader(handle))
    rows: list[dict[str, object]] = [dict(record) for record in inherited]

    derived_pu, derived_do = _max_window_drift_pair()
    next_id = max(int(record["row_id"]) for record in rows) + 1
    for stratum, why, stamp, pu, do, passengers in ADDED:
        if pu is None or do is None:
            pu, do = derived_pu, derived_do
            why = f"{why} [derived: {pu} -> {do}]"
        rows.append(
            {
                "row_id": next_id,
                "stratum": stratum,
                "why": why,
                "pickup_datetime": stamp,
                "PULocationID": pu,
                "DOLocationID": do,
                "passenger_count": passengers,
            }
        )
        next_id += 1
    return rows


def write(rows: list[dict[str, object]]) -> None:
    with PAIRS_CSV.open("w", newline="") as handle:
        # `lineterminator="\n"`: csv defaults to CRLF, and the committed row set
        # this file inherits from is LF. Two committed CSVs with different line
        # endings make a field-by-field diff between them read as a whole-file
        # rewrite the first time anyone looks.
        writer = csv.DictWriter(handle, fieldnames=list(FIELDS), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in FIELDS})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="REBUILD the committed pair set. This changes the set every published "
        "number in docs/feast_online_m8.md was measured on.",
    )
    args = parser.parse_args(argv)

    if args.refresh or not PAIRS_CSV.exists():
        rows = build()
        write(rows)
        print(f"[pairs] wrote {PAIRS_CSV.relative_to(REPO_ROOT)} — {len(rows)} declared pair(s)")
    with PAIRS_CSV.open() as handle:
        rows = list(csv.DictReader(handle))
    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row["stratum"])] = counts.get(str(row["stratum"]), 0) + 1
    print(f"[pairs] {len(rows)} declared pair(s) in {PAIRS_CSV.relative_to(REPO_ROOT)}")
    for stratum, count in sorted(counts.items()):
        print(f"[pairs]   {stratum:<16s} {count:>3d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
