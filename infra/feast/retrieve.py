#!/usr/bin/env python
"""Historical retrieval, run INSIDE the quarantine — the far side of the wall.

M8-S3. This module imports `feast` and **may not import `taxi_mlops`**: it runs
under `.venv-feast` (pandas 2.3.3) while everything that builds a feature matrix
runs under this project's interpreter (pandas 3.0.5). It is the mirror image of
`scripts/feast_sources.py`, which imports `taxi_mlops` and never `feast`, and
`tests/unit/test_feast_repo.py` pins both directions by AST — one import across
that line is how a quarantine stops being one (M8 law 4).

It deliberately lives OUTSIDE `feature_repo/`: `feast apply` imports every Python
module it finds in the repo directory looking for definitions, so a script placed
beside `definitions.py` would be imported by every apply and every plan.

**What it does, and what it refuses to do.** It reads an entity dataframe written
by this project's side, calls `get_historical_features` for each requested view,
and writes the answers back as parquet. It computes nothing: every number that
comes out was put in by `make feast-sources`, and the comparison against the ONE
`taxi_mlops.features` path happens on the other side of the wall, where that path
lives. Parquet is the only thing that crosses in either direction.

**Two retrievals, and the difference between them IS the proof.** The honest one
passes each row its own event timestamp, so Feast's point-in-time join
(`source.event_timestamp <= entity.event_timestamp`) hands it the newest window
that had already ENDED when the trip happened. The naive one overwrites every
timestamp with a single instant AFTER the last window closed — which is exactly
the shape `docs/feature_dossier.md` §4 trap 2 describes and M3-S3's leakage red
team measured: the same join, the same code, one column different, and a March
row served an aggregate computed with June in it. Nothing here decides which is
right; it produces both so the difference can be measured.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from feast import FeatureStore

REPO_DIR = Path(__file__).resolve().parent / "feature_repo"

#: view -> (join keys it needs, columns it returns). The join keys are the
#: entity-dataframe column names, which are the column names the REST of this
#: program already uses (`PULocationID`, `hour`, ...) — the composite-entity
#: decision `definitions.py` argues, paying off here as "no encode step exists to
#: disagree with itself".
VIEWS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "zone_static": (
        ("zone_id",),
        ("centroid_lat", "centroid_lon", "borough", "is_airport"),
    ),
    "calendar_day_flags": (
        ("date_key",),
        ("is_holiday", "is_near_holiday", "is_business_day"),
    ),
    "od_window_stats": (
        ("PULocationID", "DOLocationID"),
        ("od_median_duration_min", "window_months"),
    ),
    "pu_hour_window_stats": (
        ("PULocationID", "hour"),
        ("pu_hour_mean_speed_kmh", "pu_hour_trips_per_day", "window_months"),
    ),
}


def _retrieve(
    store: FeatureStore, entities: pd.DataFrame, view: str, *, key_map: dict[str, str] | None = None
) -> pd.DataFrame:
    """One `get_historical_features` call, returned with `row_id` still attached.

    `key_map` renames an entity-frame column onto the view's join key — the one
    thing `zone_static` needs, because a trip has TWO zones and a view keyed on
    `zone_id` must be asked twice rather than guessing which one was meant.
    """
    join_keys, columns = VIEWS[view]
    frame = entities.copy()
    for source_column, join_key in (key_map or {}).items():
        frame[join_key] = frame[source_column]
    wanted = ["row_id", "event_timestamp", *join_keys]
    job = store.get_historical_features(
        entity_df=frame[wanted],
        features=[f"{view}:{column}" for column in columns],
    )
    out = job.to_df()
    return out[["row_id", *columns]].sort_values("row_id", ignore_index=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entities", required=True, help="parquet written by this repo's side")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument(
        "--naive-timestamp",
        default=None,
        help="if given, a SECOND retrieval of the time-varying views with every "
        "row's timestamp replaced by this instant — the leaky join, produced on "
        "purpose so the difference can be measured",
    )
    args = parser.parse_args(argv)

    entities = pd.read_parquet(args.entities)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    store = FeatureStore(repo_path=str(REPO_DIR))
    print(f"[retrieve] feast project {store.project!r}, {len(entities):,} entity row(s)")

    written: dict[str, dict[str, int]] = {}

    def write(frame: pd.DataFrame, name: str) -> None:
        path = out_dir / f"{name}.parquet"
        frame.to_parquet(path, index=False)
        written[name] = {"rows": int(len(frame)), "columns": int(frame.shape[1])}
        print(f"[retrieve] {name:<28s} {len(frame):>6,} rows -> {path.name}")

    write(_retrieve(store, entities, "zone_static", key_map={"PULocationID": "zone_id"}), "pu_zone")
    write(_retrieve(store, entities, "zone_static", key_map={"DOLocationID": "zone_id"}), "do_zone")
    write(_retrieve(store, entities, "calendar_day_flags"), "calendar")
    write(_retrieve(store, entities, "od_window_stats"), "od_window")
    write(_retrieve(store, entities, "pu_hour_window_stats"), "pu_hour_window")

    if args.naive_timestamp:
        naive = entities.copy()
        naive["event_timestamp"] = pd.Timestamp(args.naive_timestamp)
        print(f"[retrieve] naive pass: every timestamp overwritten with {args.naive_timestamp}")
        write(_retrieve(store, naive, "od_window_stats"), "od_window_naive")
        write(_retrieve(store, naive, "pu_hour_window_stats"), "pu_hour_window_naive")

    (out_dir / "retrieval.json").write_text(
        json.dumps(
            {
                "project": store.project,
                "entity_rows": int(len(entities)),
                "naive_timestamp": args.naive_timestamp,
                "written": written,
                "pandas": pd.__version__,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"[retrieve] wrote {len(written)} answer file(s) under {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
