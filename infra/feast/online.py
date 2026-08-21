#!/usr/bin/env python
"""Both halves of the online/offline comparison, run INSIDE the quarantine.

M8-S4. This module imports `feast` and **may not import `taxi_mlops`**: it runs
under `.venv-feast` (pandas 2.3.3) while everything that builds a feature matrix
runs under this project's interpreter (pandas 3.0.5). It is the sibling of
`retrieve.py` and the mirror image of `scripts/feast_sources.py`;
`tests/unit/test_feast_repo.py` pins both directions by AST, because one import
across that line is how a quarantine stops being one (M8 law 4).

Like `retrieve.py` it lives OUTSIDE `feature_repo/` — `feast apply` imports every
module it finds in the repo directory looking for definitions.

**Why both halves are read in ONE process.** The two answers must come from the
same registry, the same repo config and the same instant. Splitting them across
two invocations would leave a window in which a `feast apply` or a
materialization could land between them, and the resulting table would compare
two stores that were never simultaneously true. It also means the entity frame is
read once, so the two halves cannot disagree about which rows were asked for.

**It computes nothing.** Every number it returns was put into one of the two
stores by this project's own side of the wall. The comparison happens over there,
where `taxi_mlops.features` lives; parquet is the only thing that crosses.

**The offline half is retrieved at ONE instant, and that is not a shortcut.**
`feast materialize` keeps the LATEST row per entity key, so the online store
serves the full window to every request and has no history at all. The honest
offline counterpart of that is a retrieval at an instant after the last window
closed — which is what `--as-of` carries. Retrieving at each row's own timestamp
would produce a table in which a correctly-working store disagrees with itself
(`docs/feast_online_m8.md` §1).
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pandas as pd
from feast import FeatureStore

REPO_DIR = Path(__file__).resolve().parent / "feature_repo"

#: view -> (join keys, columns). Deliberately the SAME table `retrieve.py`
#: carries: the two seams must ask for the same columns, and two copies of this
#: mapping would be the twin this repo keeps deleting. It is duplicated here
#: rather than imported only because the two scripts are separate entry points on
#: the far side of a wall; `tests/unit/test_feast_online.py` asserts they agree.
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

#: The five answer sets, in the order the comparison reads them:
#: (name, view, {entity-frame column -> the view's join key}).
REQUESTS: tuple[tuple[str, str, dict[str, str]], ...] = (
    ("pu_zone", "zone_static", {"PULocationID": "zone_id"}),
    ("do_zone", "zone_static", {"DOLocationID": "zone_id"}),
    ("calendar", "calendar_day_flags", {}),
    ("od_window", "od_window_stats", {}),
    ("pu_hour_window", "pu_hour_window_stats", {}),
)


def _prepared(entities: pd.DataFrame, key_map: dict[str, str]) -> pd.DataFrame:
    frame = entities.copy()
    for source_column, join_key in key_map.items():
        frame[join_key] = frame[source_column]
    return frame


def online(store: FeatureStore, entities: pd.DataFrame, view: str, key_map: dict[str, str]):
    """`get_online_features` — a LOOKUP, one answer row per requested row.

    The entity rows are handed over as a list of dicts because that is the API's
    own shape; the join keys are the column names the rest of this program
    already uses, which is the composite-entity decision `definitions.py` argues
    paying off again (no encode step exists to disagree with itself).
    """
    join_keys, columns = VIEWS[view]
    frame = _prepared(entities, key_map)
    rows = frame[list(join_keys)].to_dict("records")
    answer = store.get_online_features(
        features=[f"{view}:{column}" for column in columns],
        entity_rows=rows,
    ).to_df()
    answer.insert(0, "row_id", frame["row_id"].to_numpy())
    return answer[["row_id", *join_keys, *columns]]


def offline(
    store: FeatureStore, entities: pd.DataFrame, view: str, key_map: dict[str, str], as_of: str
):
    """`get_historical_features` at ONE instant — a JOIN, which may return fewer rows.

    It returns the join keys alongside the values on purpose: the caller
    re-attaches these answers BY KEY and never by position, because a duplicate
    `(entity keys, timestamp)` is answered once (F-056 cause 1) and aligning on
    order would manufacture a mismatch out of correct behaviour.
    """
    join_keys, columns = VIEWS[view]
    frame = _prepared(entities, key_map)
    frame["event_timestamp"] = pd.Timestamp(as_of)
    job = store.get_historical_features(
        entity_df=frame[["row_id", "event_timestamp", *join_keys]],
        features=[f"{view}:{column}" for column in columns],
    )
    return job.to_df()[["row_id", *join_keys, *columns]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entities", required=True, help="parquet written by this repo's side")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument(
        "--as-of",
        required=True,
        help="the instant the OFFLINE half is retrieved at — after the last window closed, "
        "because the online store has no history to compare against",
    )
    args = parser.parse_args(argv)

    if "${" in os.environ.get("FEAST_REDIS_CONNECTION", "${unset}"):
        raise SystemExit(
            "[online] FEAST_REDIS_CONNECTION is unset. The online store's address is "
            "deliberately not a committed constant (ADR-012): it is "
            "redis.feast.svc.cluster.local:6379 in the cluster and localhost:6380 behind a "
            "port-forward on the host. Start the forward and export it — "
            "`kubectl -n feast port-forward svc/redis 6380:6379`."
        )

    entities = pd.read_parquet(args.entities)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    store = FeatureStore(repo_path=str(REPO_DIR))
    print(f"[online] feast project {store.project!r}, {len(entities):,} declared pair(s)")
    print(f"[online] offline half retrieved as of {args.as_of}")

    written: dict[str, dict[str, int]] = {}
    for name, view, key_map in REQUESTS:
        on = online(store, entities, view, key_map)
        off = offline(store, entities, view, key_map, args.as_of)
        on.to_parquet(out_dir / f"{name}.online.parquet", index=False)
        off.to_parquet(out_dir / f"{name}.offline.parquet", index=False)
        written[name] = {"online_rows": int(len(on)), "offline_rows": int(len(off))}
        note = "" if len(on) == len(off) else "   <- shapes differ; the caller classifies it"
        print(f"[online] {name:<16s} online {len(on):>4,}   offline {len(off):>4,}{note}")

    (out_dir / "online.json").write_text(
        json.dumps(
            {
                "project": store.project,
                "declared_pairs": int(len(entities)),
                "as_of": args.as_of,
                "written": written,
                "pandas": pd.__version__,
                "connection": os.environ.get("FEAST_REDIS_CONNECTION"),
            },
            indent=2,
        )
        + "\n"
    )
    print(f"[online] wrote {len(written) * 2} answer file(s) under {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
