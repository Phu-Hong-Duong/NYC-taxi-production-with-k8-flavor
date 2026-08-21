#!/usr/bin/env python
"""Build the parquet Feast READS — from the settled artifacts, into a tree of its own.

M8-S2. This script runs on THIS side of the quarantine wall (pandas 3.0.5) and
**imports no Feast**: it is the producer, `infra/feast/feature_repo/definitions.py`
is the consumer, and parquet is the only thing that crosses between them (M8 law 4;
`docs/feast_catalog.md` §2). A test asserts the import law in both directions.

**What it reads and what it may not touch (M8 law 2).** Every input is a settled,
already-pinned artifact: `data/processed/` through the ONE loader
(`taxi_mlops.training.datasets.load_frame`), `data/reference/taxi_zone_centroids.csv`
and `data/reference/us_federal_holidays.csv` through the ONE feature path. Nothing
is written back into any of them; the outputs land in `data/feast/`, which is
gitignored and NOT DVC-tracked for `data/predictions/`'s reason exactly — it is
derived output, regenerable by one command from pinned inputs, and a `.dvc` pin
that must be refreshed every time an upstream tree moves is provenance that lies.

**The event-timestamp convention, which is the whole point of the time-varying
views.** The prior-art ADOPT (`docs/prior_art.md`) is END-OF-WINDOW stamps: a
feature computed over a window is knowable only when the window has ENDED. Our
aggregates are fitted per month cutoff — `aggregates.fit` builds, for train month
*k*, a table over months 1..k-1 and nothing else — so the table over a window
ending with month *m* becomes knowable at the first instant of month *m+1*, and
that instant is its `event_timestamp`. Written the other way round: the table a
row of month *k* is entitled to is stamped exactly at the start of month *k*, and
Feast's point-in-time join (`event_timestamp <= entity timestamp`) therefore hands
that row the same table `aggregates.transform` hands it. That correspondence is
not a coincidence to be checked later — it is what M8-S3's point-in-time proof
measures, and it is why the stamps are derived here from the window's own months
rather than typed.

The first train month gets NO ROWS at all, deliberately: it has no history, and
`AggregateTables.empty()` serves it NaN rather than a number containing its own
answer. A point-in-time lookup before the first stamp returning null IS that NaN,
expressed in the store's vocabulary.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from taxi_mlops.data.config import load_config, load_splits  # noqa: E402
from taxi_mlops.features import aggregates, calendar as calendar_features, zones  # noqa: E402
from taxi_mlops.training import datasets  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "feast"

#: The stamp every static (non-time-varying) row carries. A store still needs an
#: event timestamp for a table that does not vary in time, and inventing "now"
#: would make two runs of this script produce different bytes. So the stamp is
#: the DERIVATION date of the artifact being published — the day
#: `make zones` wrote the centroid table — read off the reference manifest.
STATIC_FALLBACK_STAMP = pd.Timestamp("2019-01-01T00:00:00")


@dataclass(frozen=True)
class Written:
    path: Path
    rows: int
    columns: tuple[str, ...]


def _write(frame: pd.DataFrame, name: str) -> Written:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{name}.parquet"
    # Feast's side is pandas 2 / pyarrow 25; ours is pandas 3 / pyarrow 25. The
    # WRITER is pinned (the same pair `configs/data.yaml: write` pins for the
    # settled trees), and arrow's types are what actually cross the wall — which
    # is the seam M8-S3 measures rather than assumes.
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), path, compression="snappy")
    return Written(path=path, rows=len(frame), columns=tuple(frame.columns))


def _static_stamp() -> pd.Timestamp:
    """The centroid table's own derivation date, never `now`."""
    manifest = REPO_ROOT / "data" / "reference" / "reference_manifest.json"
    if manifest.exists():
        payload = json.loads(manifest.read_text())
        for key in ("derived_at", "generated_at", "created_at"):
            if isinstance(payload.get(key), str):
                return pd.Timestamp(payload[key]).tz_localize(None)
    return STATIC_FALLBACK_STAMP


def build_zone_static(stamp: pd.Timestamp) -> Written:
    """One row per zone the committed centroid table HAS — 263, not 265.

    Zones 264/265 are TLC's "Unknown": not places, and deliberately given no
    geometry (DR-04 condition 1, `docs/feature_dossier.md`). They get no row here
    either, and that absence is load-bearing: a retrieval for zone 264 returns
    null, which is exactly the `has_geometry = 0` fallback the champion's own
    matrix carries for those rows. Manufacturing a row with zeroed coordinates
    would put a plausible place at the equator into a feature store.
    """
    table = zones.load_zone_table()
    ids = np.flatnonzero(~np.isnan(table.lat))
    frame = pd.DataFrame(
        {
            "zone_id": ids.astype("int64"),
            "centroid_lat": table.lat[ids].astype("float64"),
            "centroid_lon": table.lon[ids].astype("float64"),
            # The borough comes off the lookup table's code, through the ONE
            # reader — including its folding of TLC's two spellings of "not a
            # place" onto one Unknown code.
            "borough": [table.boroughs[c] for c in table.borough_code[ids]],
            "is_airport": np.isin(ids, list(zones.AIRPORT_ZONES)),
        }
    )
    frame["event_timestamp"] = stamp
    return _write(frame.sort_values("zone_id").reset_index(drop=True), "zone_static")


def build_calendar_day(stamp: pd.Timestamp) -> Written:
    """One row per calendar DATE the holiday table covers, flags from the ONE path.

    The flags are not re-derived here — `taxi_mlops.features.calendar` computes
    them, the same code the champion's `is_holiday` / `is_near_holiday` /
    `is_business_day` come out of. A feature store that recomputes what the
    feature path computes is a second definition (M1-S2's `split`/`month` lesson,
    one layer along), and the store's job is to REMEMBER, not to decide.

    The horizon is the table's, not a guess: F-019 made an uncovered date a typed
    REFUSAL, so this view stops exactly where the refusal starts.
    """
    calendar = calendar_features.load_calendar()
    years = sorted(calendar.years)
    dates = pd.date_range(f"{years[0]}-01-01", f"{years[-1]}-12-31", freq="D")
    flags = calendar_features.flags(pd.Series(dates), calendar)
    frame = pd.DataFrame(
        {
            "date_key": dates.strftime("%Y-%m-%d"),
            "is_holiday": np.asarray(flags["is_holiday"]).astype("bool"),
            "is_near_holiday": np.asarray(flags["is_near_holiday"]).astype("bool"),
            "is_business_day": np.asarray(flags["is_business_day"]).astype("bool"),
        }
    )
    # A calendar fact about 2027-07-04 is knowable the moment the statute is read,
    # not on the day itself: 5 U.S.C. §6103 is the source and `make holidays`
    # derived the whole table at once. So every row carries the DERIVATION stamp,
    # and a point-in-time join never withholds a date's own flags from it.
    frame["event_timestamp"] = stamp
    return _write(frame, "calendar_day")


def _window_stamp(window_months: tuple[str, ...]) -> pd.Timestamp:
    """The first instant at which a window's table is knowable.

    END-OF-WINDOW, expressed as the exclusive end: a table over months ending
    with `m` is complete when `m` is over, i.e. at 00:00:00 on the first day of
    the following month. Derived from the window's own months — never typed.
    """
    last = pd.Period(window_months[-1], freq="M")
    return pd.Timestamp((last + 1).start_time)


def _long_od(table: aggregates.AggregateTables, stamp: pd.Timestamp) -> pd.DataFrame:
    keys = np.flatnonzero(~np.isnan(table.od_median))
    return pd.DataFrame(
        {
            "PULocationID": (keys // (zones.MAX_ZONE_ID + 1)).astype("int64"),
            "DOLocationID": (keys % (zones.MAX_ZONE_ID + 1)).astype("int64"),
            "od_median_duration_min": table.od_median[keys].astype("float64"),
            "event_timestamp": stamp,
            "window_months": ",".join(table.months),
        }
    )


def _long_pu_hour(table: aggregates.AggregateTables, stamp: pd.Timestamp) -> pd.DataFrame:
    keys = np.flatnonzero(~np.isnan(table.pu_hour_rate))
    return pd.DataFrame(
        {
            "PULocationID": (keys // 24).astype("int64"),
            "hour": (keys % 24).astype("int64"),
            "pu_hour_mean_speed_kmh": table.pu_hour_speed[keys].astype("float64"),
            "pu_hour_trips_per_day": table.pu_hour_rate[keys].astype("float64"),
            "event_timestamp": stamp,
            "window_months": ",".join(table.months),
        }
    )


def build_window_aggregates(train_months: tuple[str, ...] | None = None) -> dict[str, Written]:
    """The g5 family, published as time-varying views — catalog-only, and the
    catalog says why (it LOST the M3 ablation at -1.63%).

    One row set per DISTINCT window, each stamped at its own exclusive end. The
    windows are exactly the ones `aggregates.fit` builds: months 1..k-1 for each
    train month k (stamped at the start of month k), plus the full window over
    every fitted month (stamped at the start of the month after the last one),
    which is what val and test rows are served.
    """
    data_cfg = load_config()
    splits = load_splits()
    months = tuple(train_months or splits.train)
    target = "trip_duration_minutes"
    columns = ["tpep_pickup_datetime", "PULocationID", "DOLocationID", target]
    print(f"[feast-sources] reading train months {','.join(months)} ({len(columns)} columns)")
    frame, wanted = datasets.load_frame("train", data_cfg, columns, months=months)
    print(f"[feast-sources] {len(frame):,} rows read; fitting point-in-time aggregates")
    fitted = aggregates.fit(frame, target, point_in_time=True)
    del frame
    print(fitted.describe())

    od_parts: list[pd.DataFrame] = []
    pu_parts: list[pd.DataFrame] = []
    seen: set[tuple[str, ...]] = set()
    for table in [*(fitted.by_month[m] for m in fitted.fitted_months), fitted.full]:
        if not table.months or table.months in seen:
            continue
        seen.add(table.months)
        stamp = _window_stamp(table.months)
        od_parts.append(_long_od(table, stamp))
        pu_parts.append(_long_pu_hour(table, stamp))
        print(
            f"[feast-sources]   window {','.join(table.months):<47s} knowable at "
            f"{stamp.isoformat()}  od={len(od_parts[-1]):>7,}  pu_hour={len(pu_parts[-1]):>6,}"
        )

    od = pd.concat(od_parts, ignore_index=True).sort_values(
        ["event_timestamp", "PULocationID", "DOLocationID"], ignore_index=True
    )
    pu_hour = pd.concat(pu_parts, ignore_index=True).sort_values(
        ["event_timestamp", "PULocationID", "hour"], ignore_index=True
    )
    return {
        "od_window_stats": _write(od, "od_window_stats"),
        "pu_hour_window_stats": _write(pu_hour, "pu_hour_window_stats"),
        "_meta": Written(path=Path(",".join(wanted)), rows=len(seen), columns=tuple(wanted)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--train-months",
        nargs="+",
        default=None,
        help="SMOKE override — a narrower window makes a smaller source and is NOT "
        "the catalog's published table. `--static-only` is the cheaper smoke.",
    )
    parser.add_argument(
        "--static-only",
        action="store_true",
        help="build the two static views only; skip the 43.9M-row aggregate fit",
    )
    args = parser.parse_args(argv)

    stamp = _static_stamp()
    written: dict[str, Written] = {}
    written["zone_static"] = build_zone_static(stamp)
    written["calendar_day"] = build_calendar_day(stamp)
    for name, item in written.items():
        print(f"[feast-sources] {name:<22s} {item.rows:>7,} rows -> {item.path.name}")

    if args.static_only:
        print("[feast-sources] --static-only: the time-varying views were NOT rebuilt")
        return 0

    aggs = build_window_aggregates(tuple(args.train_months) if args.train_months else None)
    meta = aggs.pop("_meta")
    for name, item in aggs.items():
        print(f"[feast-sources] {name:<22s} {item.rows:>7,} rows -> {item.path.name}")
    print(
        f"[feast-sources] {meta.rows} distinct window(s) over months "
        f"{','.join(meta.columns)}"
        + ("  [SAMPLED — not the catalog's table]" if args.train_months else "")
    )
    print(f"[feast-sources] wrote {len(written) + len(aggs)} source(s) under {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
