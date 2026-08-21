#!/usr/bin/env python
"""Historical retrieval parity, and the point-in-time proof — the whole path.

M8-S3. Runs on THIS side of the quarantine (pandas 3.0.5); imports `taxi_mlops`
and **never `feast`** (M8 law 4, AST-pinned). It shells out to
`infra/feast/retrieve.py`, which is the mirror image, and parquet is the only
thing that crosses in either direction.

**A READER.** It fits aggregate tables in this process and it writes its own two
records; it deploys nothing, materializes nothing, mints no MLflow run, reads no
registry alias and touches no settled tree. `tests/unit/test_feast_retrieval.py`
pins that by AST.

The design, the tolerance and the row set are argued in `docs/feast_pit_m8.md`,
which was committed BEFORE this script first ran — the bar is a bar because of
that ordering and not because of this docstring (M8 law 4).

TWO MEASUREMENTS
----------------
**(1) Retrieval parity.** Every column the store hands back must equal what the
ONE `taxi_mlops.features` path uses for the same row. The bar is EXACT on every
column — the argument is §2 of the doc, and it reduces to: nothing on the store's
side of the wall performs arithmetic, so every crossing is a copy, a lossless
`float32 -> float64` widening, or parquet's own typed encoding.

**(2) The point-in-time proof.** The same rows retrieved twice from the same
store by the same call, differing in exactly ONE column — the honest pass sends
each row its own event timestamp, the naive pass overwrites every timestamp with
the instant the LAST window became knowable. The assertion is two-sided: the
joins must DIFFER where the naive one reaches forward, and the honest join must
RECONCILE with our own `aggregates.fit(point_in_time=True)` + `transform`.

**The truth is re-fitted from `data/processed/`, never rebuilt from the parquet
the store reads.** Reconstructing it from the artifact under test would compare
the store against itself and would pass for any join at all — including no join.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from taxi_mlops.data.config import load_config, load_splits  # noqa: E402
from taxi_mlops.features import aggregates, zones  # noqa: E402
from taxi_mlops.features import calendar as calendar_features  # noqa: E402
from taxi_mlops.training import datasets  # noqa: E402

ROWS_CSV = REPO_ROOT / "infra" / "feast" / "retrieval_rows.csv"
QUARANTINE_PYTHON = REPO_ROOT / ".venv-feast" / "bin" / "python"
RETRIEVER = REPO_ROOT / "infra" / "feast" / "retrieve.py"
WORK_DIR = REPO_ROOT / "data" / "feast" / "retrieval"
RECORD_DIR = REPO_ROOT / "automation" / "runs" / "m8-pit"

#: The bar, in the units of each column. EXACT — see `docs/feast_pit_m8.md` §2.
#: It is a module constant so `verify-m8` and the tests read the number this
#: script actually applied rather than re-typing the one the doc argues (F-017).
TOLERANCE = 0.0

#: The target the aggregates are fitted on — the same column `aggregates.fit` is
#: handed everywhere else in this program.
TARGET = "trip_duration_minutes"


@dataclass
class ColumnVerdict:
    """One column, compared row by row, with both kinds of disagreement counted."""

    column: str
    kind: str
    compared: int
    mismatches: int
    max_abs_delta: float | None
    both_missing: int
    one_missing: int
    examples: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.mismatches == 0

    def as_record(self) -> dict[str, Any]:
        return {
            "column": self.column,
            "kind": self.kind,
            "compared": self.compared,
            "mismatches": self.mismatches,
            "max_abs_delta": self.max_abs_delta,
            "both_missing": self.both_missing,
            "one_missing": self.one_missing,
            "examples": self.examples[:5],
        }


def _missing(values: np.ndarray) -> np.ndarray:
    """True where a value is absent, whatever absence looks like for that dtype."""
    if values.dtype.kind in "fc":
        return np.isnan(values)
    return pd.isna(values)


def compare(
    column: str, kind: str, ours: np.ndarray, theirs: np.ndarray, row_ids: np.ndarray
) -> ColumnVerdict:
    """Compare one column. Both-missing is agreement; one-missing is a MISMATCH.

    The asymmetry is the point (`docs/feast_pit_m8.md` §2): `NaN != NaN`, so a
    comparison that quietly dropped nulls would be blind to exactly the rows
    zones 264/265 produce — about 1% of every split, and the largest single OD
    "route" in this data.
    """
    ours = np.asarray(ours, dtype="object" if kind != "float" else "float64")
    theirs = np.asarray(theirs, dtype="object" if kind != "float" else "float64")
    ours_missing, theirs_missing = _missing(ours), _missing(theirs)
    both_missing = ours_missing & theirs_missing
    one_missing = ours_missing ^ theirs_missing

    comparable = ~(ours_missing | theirs_missing)
    if kind == "float":
        delta = np.zeros(len(ours), dtype="float64")
        delta[comparable] = np.abs(
            ours[comparable].astype("float64") - theirs[comparable].astype("float64")
        )
        differs = comparable & (delta > TOLERANCE)
        max_delta = float(delta[comparable].max()) if comparable.any() else None
    else:
        differs = comparable & np.array(
            [
                (bool(a) != bool(b)) if kind == "bool" else (str(a) != str(b))
                for a, b in zip(ours, theirs, strict=True)
            ]
        )
        max_delta = None

    bad = differs | one_missing
    examples = [
        {
            "row_id": int(row_ids[index]),
            "ours": None if ours_missing[index] else _plain(ours[index]),
            "theirs": None if theirs_missing[index] else _plain(theirs[index]),
        }
        for index in np.flatnonzero(bad)
    ]
    return ColumnVerdict(
        column=column,
        kind=kind,
        compared=int(len(ours)),
        mismatches=int(bad.sum()),
        max_abs_delta=max_delta,
        both_missing=int(both_missing.sum()),
        one_missing=int(one_missing.sum()),
        examples=examples,
    )


def _plain(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    return value


def load_rows() -> pd.DataFrame:
    """The committed row set. Read, never generated here."""
    if not ROWS_CSV.exists():
        raise SystemExit(
            f"[retrieval] {ROWS_CSV} is missing. It is a COMMITTED artifact — rebuild it "
            "deliberately with `uv run python scripts/feast_retrieval_rows.py --refresh`, "
            "which changes the set every measurement in docs/feast_pit_m8.md was made on."
        )
    with ROWS_CSV.open() as handle:
        records = list(csv.DictReader(handle))
    frame = pd.DataFrame(records)
    frame["row_id"] = frame["row_id"].astype("int64")
    frame["PULocationID"] = frame["PULocationID"].astype("int64")
    frame["DOLocationID"] = frame["DOLocationID"].astype("int64")
    frame["passenger_count"] = frame["passenger_count"].astype("float64")
    frame["tpep_pickup_datetime"] = pd.to_datetime(frame["pickup_datetime"])
    return frame.sort_values("row_id", ignore_index=True)


def naive_timestamp(train_months: tuple[str, ...]) -> pd.Timestamp:
    """The instant the LAST window became knowable — derived, never typed.

    Sending this as every row's event timestamp is what makes the naive pass
    leaky: under `source.event_timestamp <= entity.event_timestamp` every row,
    including one in January, then matches the window fitted over every train
    month. That is `docs/feature_dossier.md` §4 trap 2 with the timestamps
    rather than the code changed, which is the honest way to demonstrate it —
    the leak is a property of the join key, not of the SQL.
    """
    last = pd.Period(train_months[-1], freq="M")
    return pd.Timestamp((last + 1).start_time)


def write_entities(rows: pd.DataFrame) -> Path:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    entities = pd.DataFrame(
        {
            "row_id": rows["row_id"].to_numpy(),
            "PULocationID": rows["PULocationID"].to_numpy(),
            "DOLocationID": rows["DOLocationID"].to_numpy(),
            "hour": rows["tpep_pickup_datetime"].dt.hour.to_numpy(),
            "date_key": rows["tpep_pickup_datetime"].dt.strftime("%Y-%m-%d").to_numpy(),
            "event_timestamp": rows["tpep_pickup_datetime"].to_numpy(),
        }
    )
    path = WORK_DIR / "entities.parquet"
    entities.to_parquet(path, index=False)
    return path


def run_quarantine(entities: Path, naive: pd.Timestamp) -> dict[str, Any]:
    """Cross the wall. The far side imports feast; this side never does."""
    if not QUARANTINE_PYTHON.exists():
        raise SystemExit(
            f"[retrieval] the quarantine interpreter {QUARANTINE_PYTHON} does not exist. "
            "Build it with `make feast-quarantine` — feast is NOT and will never be a "
            "project dependency (M8 law 4: it pins pandas<3 against our 3.0.5)."
        )
    command = [
        str(QUARANTINE_PYTHON),
        str(RETRIEVER),
        "--entities",
        str(entities),
        "--out-dir",
        str(WORK_DIR),
        "--naive-timestamp",
        naive.strftime("%Y-%m-%dT%H:%M:%S"),
    ]
    print(f"[retrieval] crossing the wall: {' '.join(command[1:])}")
    subprocess.run(command, check=True, cwd=REPO_ROOT)
    return json.loads((WORK_DIR / "retrieval.json").read_text())


#: entity-key columns per answer file. The naive files key on the same entity as
#: their honest twins; only the timestamp differs, which is the whole design.
ANSWER_KEYS: dict[str, tuple[str, ...]] = {
    "pu_zone": ("PULocationID",),
    "do_zone": ("DOLocationID",),
    "calendar": ("date_key",),
    "od_window": ("PULocationID", "DOLocationID"),
    "od_window_naive": ("PULocationID", "DOLocationID"),
    "pu_hour_window": ("PULocationID", "hour"),
    "pu_hour_window_naive": ("PULocationID", "hour"),
}


def _entity_frame(rows: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "row_id": rows["row_id"].to_numpy(),
            "PULocationID": rows["PULocationID"].to_numpy(),
            "DOLocationID": rows["DOLocationID"].to_numpy(),
            "hour": rows["tpep_pickup_datetime"].dt.hour.to_numpy(),
            "date_key": rows["tpep_pickup_datetime"].dt.strftime("%Y-%m-%d").to_numpy(),
            "event_timestamp": rows["tpep_pickup_datetime"].to_numpy(),
        }
    )


def _answers(name: str, rows: pd.DataFrame, *, by_row: bool = True) -> pd.DataFrame:
    """Read one answer file back and align it to the row set — by keys, not by luck.

    **`get_historical_features` does not return one row per row you asked for**,
    and the two reasons it returns fewer are different facts that a bare
    left-join-on-row_id would blur into one NaN (F-056):

    * **Duplicate `(entity keys, event_timestamp)`.** The answer carries the
      first of them. The others are not missing data — the store answered them,
      once — so they are recovered here by joining on the keys the store actually
      keyed on. Accepting a NaN for them would manufacture a mismatch against a
      feature path that has a perfectly good value.
    * **No source row at or before the entity's timestamp.** Then the row is
      DROPPED from the answer rather than returned null, and after this alignment
      it is legitimately NaN. That is the correct feature value — a 2019-01 row
      has no history and `AggregateTables.empty()` serves it NaN too — but it is
      the caller's job to say so, which `explain_shortfall` does.

    `by_row=False` is the naive pass, where every timestamp is the same instant
    and the join is on keys alone.
    """
    frame = pd.read_parquet(WORK_DIR / f"{name}.parquet")
    keys = list(ANSWER_KEYS[name])
    entity = _entity_frame(rows)
    features = [column for column in frame.columns if column != "row_id"]
    with_keys = frame.merge(entity, on="row_id", how="left")
    join_on = [*keys, "event_timestamp"] if by_row else keys
    lookup = with_keys[[*join_on, *features]].drop_duplicates(join_on)
    aligned = entity[["row_id", *join_on]].merge(lookup, on=join_on, how="left")
    return aligned.sort_values("row_id", ignore_index=True)


def explain_shortfall(name: str, rows: pd.DataFrame) -> dict[str, Any]:
    """Classify every declared row the store did not answer for. No class = FAIL.

    The two legitimate classes are named in `_answers`. Anything else is a row
    the store lost, and a retrieval that silently returns fewer rows than it was
    given is gotcha #78's disease in a new place: "this row has no feature" and
    "this row is not in the answer" render identically once a caller joins back.
    """
    frame = pd.read_parquet(WORK_DIR / f"{name}.parquet")
    keys = list(ANSWER_KEYS[name])
    entity = _entity_frame(rows)
    absent = entity[~entity["row_id"].isin(frame["row_id"])]

    answered_keys = set(
        map(tuple, frame.merge(entity, on="row_id", how="left")[[*keys, "event_timestamp"]].values)
    )
    view = name.replace("_naive", "")
    source = {
        "pu_zone": "zone_static",
        "do_zone": "zone_static",
        "calendar": "calendar_day",
        "od_window": "od_window_stats",
        "pu_hour_window": "pu_hour_window_stats",
    }[view]
    earliest = pd.read_parquet(REPO_ROOT / "data" / "feast" / f"{source}.parquet")[
        "event_timestamp"
    ].min()

    duplicates, before_first, unexplained = [], [], []
    for record in absent.to_dict("records"):
        signature = tuple(record[key] for key in keys) + (record["event_timestamp"],)
        if signature in answered_keys:
            duplicates.append(int(record["row_id"]))
        elif pd.Timestamp(record["event_timestamp"]) < earliest:
            before_first.append(int(record["row_id"]))
        else:
            unexplained.append(int(record["row_id"]))
    return {
        "answer": name,
        "declared": int(len(entity)),
        "returned": int(len(frame)),
        "duplicate_key_and_timestamp": duplicates,
        "earlier_than_every_source_row": before_first,
        "earliest_source_stamp": pd.Timestamp(earliest).isoformat(),
        "unexplained": unexplained,
    }


def our_truth(rows: pd.DataFrame, naive: pd.Timestamp) -> dict[str, Any]:
    """Every value the ONE feature path uses for these rows.

    The aggregate tables are fitted here, from `data/processed/` through the ONE
    loader. `naive_values` is the SAME `transform` call with every timestamp
    moved past the fitted months, which is how `aggregates.transform` itself
    falls through to `tables.full` — so "what the full window says" is produced
    by the public API rather than by reaching into the dense arrays.
    """
    table = zones.load_zone_table()
    pu_ids = zones._clip_ids(rows["PULocationID"])
    do_ids = zones._clip_ids(rows["DOLocationID"])
    flags = calendar_features.flags(rows["tpep_pickup_datetime"])
    geometry = zones.geometry(rows["PULocationID"], rows["DOLocationID"], table)

    data_cfg = load_config()
    splits = load_splits()
    months = tuple(splits.train)
    columns = ["tpep_pickup_datetime", "PULocationID", "DOLocationID", TARGET]
    print(f"[retrieval] fitting the truth: train months {','.join(months)}")
    frame, _ = datasets.load_frame("train", data_cfg, columns, months=months)
    print(f"[retrieval] {len(frame):,} rows read; fitting point-in-time aggregates")
    fitted = aggregates.fit(frame, TARGET, point_in_time=True)
    del frame
    print(fitted.describe())

    honest = aggregates.transform(fitted, rows)
    leaky_frame = rows.copy()
    leaky_frame["tpep_pickup_datetime"] = naive
    naive_values = aggregates.transform(fitted, leaky_frame)

    def zone_column(ids: np.ndarray, what: str) -> np.ndarray:
        if what == "lat":
            return table.lat[ids]
        if what == "lon":
            return table.lon[ids]
        if what == "borough":
            return np.array([table.boroughs[code] for code in table.borough_code[ids]])
        return np.isin(ids, list(zones.AIRPORT_ZONES))

    return {
        "pu": {what: zone_column(pu_ids, what) for what in ("lat", "lon", "borough", "airport")},
        "do": {what: zone_column(do_ids, what) for what in ("lat", "lon", "borough", "airport")},
        "pu_has_geometry": ~np.isnan(table.lat[pu_ids]),
        "do_has_geometry": ~np.isnan(table.lat[do_ids]),
        "row_has_geometry": geometry.has_geometry.astype("bool"),
        "flags": flags,
        "honest": honest,
        "naive": naive_values,
        "fitted_months": fitted.fitted_months,
        "full_window_months": fitted.full.months,
    }


def retrieval_parity(rows: pd.DataFrame, truth: dict[str, Any]) -> list[ColumnVerdict]:
    """Column by column, the store's answer against the feature path's."""
    row_ids = rows["row_id"].to_numpy()
    verdicts: list[ColumnVerdict] = []

    for side, name in (("pu", "pu_zone"), ("do", "do_zone")):
        answers = _answers(name, rows)
        mine = truth[side]
        verdicts.append(
            compare(f"{side}.centroid_lat", "float", mine["lat"], answers["centroid_lat"], row_ids)
        )
        verdicts.append(
            compare(f"{side}.centroid_lon", "float", mine["lon"], answers["centroid_lon"], row_ids)
        )
        # Only where the store HAS the zone: for a no-geometry zone the store has
        # no row at all and our table answers "Unknown"/False — the same fact in
        # two vocabularies, asserted two-sidedly below rather than compared here
        # (docs/feast_pit_m8.md §2).
        present = truth[f"{side}_has_geometry"]
        verdicts.append(
            compare(
                f"{side}.borough (zones with geometry)",
                "string",
                mine["borough"][present],
                answers["borough"].to_numpy()[present],
                row_ids[present],
            )
        )
        verdicts.append(
            compare(
                f"{side}.is_airport (zones with geometry)",
                "bool",
                mine["airport"][present],
                answers["is_airport"].to_numpy()[present],
                row_ids[present],
            )
        )

    calendar = _answers("calendar", rows)
    for flag in ("is_holiday", "is_near_holiday", "is_business_day"):
        verdicts.append(
            compare(flag, "bool", np.asarray(truth["flags"][flag]), calendar[flag], row_ids)
        )

    od = _answers("od_window", rows)
    verdicts.append(
        compare(
            "od_median_duration_min",
            "float",
            truth["honest"]["od_median_duration_min"],
            od["od_median_duration_min"],
            row_ids,
        )
    )
    pu_hour = _answers("pu_hour_window", rows)
    for column in ("pu_hour_mean_speed_kmh", "pu_hour_trips_per_day"):
        verdicts.append(
            compare(column, "float", truth["honest"][column], pu_hour[column], row_ids)
        )
    return verdicts


def no_geometry_assertion(rows: pd.DataFrame, truth: dict[str, Any]) -> dict[str, Any]:
    """The two-sided one: the store says NOTHING and our path says has_geometry = 0.

    Comparing "Unknown" against null column-wise would be comparing two
    vocabularies; manufacturing a zeroed row in the store to make that comparison
    succeed would put a plausible place at the equator into a feature store.
    """
    checks: list[dict[str, Any]] = []
    for side, name in (("pu", "pu_zone"), ("do", "do_zone")):
        answers = _answers(name, rows)
        absent = ~truth[f"{side}_has_geometry"]
        store_null = answers["centroid_lat"].isna().to_numpy() & (
            answers["borough"].isna().to_numpy()
        )
        checks.append(
            {
                "side": side,
                "rows_without_geometry": int(absent.sum()),
                "store_returned_null_for_all": bool(np.all(store_null[absent])),
                "store_returned_a_row_for_any": int((~store_null & absent).sum()),
                "zones": sorted({int(z) for z in rows.loc[absent, f"{side.upper()}LocationID"]}),
            }
        )
    row_level = ~truth["row_has_geometry"]
    checks.append(
        {
            "side": "row",
            "rows_without_geometry": int(row_level.sum()),
            "our_path_reports_has_geometry_zero": int(row_level.sum()),
            "note": "zones.geometry().has_geometry is 0 exactly where a haversine is NaN",
        }
    )
    return {"checks": checks}


def pit_proof(rows: pd.DataFrame, truth: dict[str, Any]) -> dict[str, Any]:
    """Honest vs naive, and honest vs our own point-in-time tables."""
    row_ids = rows["row_id"].to_numpy()
    honest_od = _answers("od_window", rows)
    naive_od = _answers("od_window_naive", rows, by_row=False)
    honest_pu = _answers("pu_hour_window", rows)
    naive_pu = _answers("pu_hour_window_naive", rows, by_row=False)

    def spread(ours: np.ndarray, theirs: np.ndarray) -> dict[str, Any]:
        ours = np.asarray(ours, dtype="float64")
        theirs = np.asarray(theirs, dtype="float64")
        comparable = ~(np.isnan(ours) | np.isnan(theirs))
        delta = np.abs(ours[comparable] - theirs[comparable])
        return {
            "compared": int(comparable.sum()),
            "differing_rows": int((delta > 0).sum()),
            "max_abs_delta": float(delta.max()) if comparable.any() else None,
            "mean_abs_delta": float(delta.mean()) if comparable.any() else None,
            "one_missing": int((np.isnan(ours) ^ np.isnan(theirs)).sum()),
        }

    leak = {
        "od_median_duration_min": spread(
            honest_od["od_median_duration_min"], naive_od["od_median_duration_min"]
        ),
        "pu_hour_mean_speed_kmh": spread(
            honest_pu["pu_hour_mean_speed_kmh"], naive_pu["pu_hour_mean_speed_kmh"]
        ),
        "pu_hour_trips_per_day": spread(
            honest_pu["pu_hour_trips_per_day"], naive_pu["pu_hour_trips_per_day"]
        ),
    }

    # The naive answer must BE the full window — the strongest statement of what
    # the leak is: a January row handed an aggregate computed with June in it.
    naive_is_full = compare(
        "naive od == our full-window table",
        "float",
        truth["naive"]["od_median_duration_min"],
        naive_od["od_median_duration_min"],
        row_ids,
    )
    windows = honest_od["window_months"].fillna("(no row)")
    boundary = rows["stratum"].to_numpy() == "month-boundary"
    boundary_pairs = []
    boundary_rows = rows[boundary].reset_index(drop=True)
    boundary_windows = windows.to_numpy()[boundary]
    boundary_honest = np.asarray(honest_od["od_median_duration_min"], dtype="float64")[boundary]
    boundary_naive = np.asarray(naive_od["od_median_duration_min"], dtype="float64")[boundary]
    for index in range(0, len(boundary_rows) - 1, 2):
        before, after = index, index + 1
        boundary_pairs.append(
            {
                "before": boundary_rows.loc[before, "pickup_datetime"],
                "after": boundary_rows.loc[after, "pickup_datetime"],
                "seconds_apart": int(
                    (
                        boundary_rows.loc[after, "tpep_pickup_datetime"]
                        - boundary_rows.loc[before, "tpep_pickup_datetime"]
                    ).total_seconds()
                ),
                "window_before": str(boundary_windows[before]),
                "window_after": str(boundary_windows[after]),
                "windows_differ": str(boundary_windows[before]) != str(boundary_windows[after]),
                "od_median_before": _finite(boundary_honest[before]),
                "od_median_after": _finite(boundary_honest[after]),
                "od_median_naive": _finite(boundary_naive[after]),
            }
        )

    return {
        "leak": leak,
        "naive_equals_full_window": naive_is_full.as_record(),
        "windows_served": {
            str(window): int(count) for window, count in windows.value_counts().items()
        },
        "boundary_pairs": boundary_pairs,
    }


def _finite(value: float) -> float | None:
    return None if np.isnan(value) else float(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-write", action="store_true", help="print the verdicts and write no record"
    )
    args = parser.parse_args(argv)

    rows = load_rows()
    splits = load_splits()
    naive = naive_timestamp(tuple(splits.train))
    print(
        f"[retrieval] {len(rows)} declared row(s) from {ROWS_CSV.relative_to(REPO_ROOT)}; "
        f"bar = EXACT ({TOLERANCE}) on every column (docs/feast_pit_m8.md §2)"
    )
    print(f"[retrieval] naive timestamp (DERIVED from train months): {naive.isoformat()}")

    entities = write_entities(rows)
    meta = run_quarantine(entities, naive)

    print("\n[retrieval] --- what the store did NOT answer for, and why (F-056) ---")
    shortfalls = [
        explain_shortfall(name, rows)
        for name in ("pu_zone", "do_zone", "calendar", "od_window", "pu_hour_window")
    ]
    for shortfall in shortfalls:
        print(
            f"[retrieval] {shortfall['answer']:<16s} declared {shortfall['declared']}  "
            f"returned {shortfall['returned']}  duplicate-key "
            f"{len(shortfall['duplicate_key_and_timestamp'])}  before-first-source-row "
            f"{len(shortfall['earlier_than_every_source_row'])} (earliest source stamp "
            f"{shortfall['earliest_source_stamp']})  UNEXPLAINED "
            f"{len(shortfall['unexplained'])}"
        )
    unexplained = [s for s in shortfalls if s["unexplained"]]

    truth = our_truth(rows, naive)
    verdicts = retrieval_parity(rows, truth)
    geometry_checks = no_geometry_assertion(rows, truth)
    proof = pit_proof(rows, truth)

    print("\n[retrieval] --- retrieval parity: the store vs the ONE feature path ---")
    width = max(len(v.column) for v in verdicts)
    for verdict in verdicts:
        delta = "n/a" if verdict.max_abs_delta is None else f"{verdict.max_abs_delta:.3e}"
        mark = "ok  " if verdict.ok else "FAIL"
        print(
            f"[retrieval] {mark} {verdict.column:<{width}s}  {verdict.compared:>3d} compared  "
            f"max|delta| {delta:>9s}  both-missing {verdict.both_missing:>3d}  "
            f"one-missing {verdict.one_missing:>3d}"
        )
        for example in verdict.examples[:3]:
            print(f"[retrieval]        row {example['row_id']}: ours={example['ours']!r} "
                  f"theirs={example['theirs']!r}")

    failures = [v for v in verdicts if not v.ok]
    max_delta = max((v.max_abs_delta or 0.0) for v in verdicts)
    print(
        f"[retrieval] max |ours - store| over every float column = {max_delta:.3e} "
        f"against a bar of {TOLERANCE}"
    )

    print("\n[retrieval] --- the no-geometry rows: a two-sided assertion, not a comparison ---")
    for check in geometry_checks["checks"]:
        print(f"[retrieval] {check}")
    two_sided_ok = all(
        c.get("store_returned_null_for_all", True) for c in geometry_checks["checks"]
    )

    print("\n[retrieval] --- the point-in-time proof ---")
    for column, spread in proof["leak"].items():
        print(
            f"[retrieval] {column:<26s} honest vs naive: {spread['differing_rows']}/"
            f"{spread['compared']} rows differ  max {spread['max_abs_delta']}  "
            f"mean {spread['mean_abs_delta']}"
        )
    naive_full = proof["naive_equals_full_window"]
    print(
        f"[retrieval] the naive answer IS the full window: {naive_full['mismatches']} "
        f"mismatch(es) over {naive_full['compared']} row(s)"
    )
    print("[retrieval] windows the honest join served: " + json.dumps(proof["windows_served"]))
    for pair in proof["boundary_pairs"]:
        print(
            f"[retrieval] {pair['before']} -> {pair['after']} ({pair['seconds_apart']}s): "
            f"[{pair['window_before']}] -> [{pair['window_after']}] "
            f"differ={pair['windows_differ']}  od_median "
            f"{pair['od_median_before']} -> {pair['od_median_after']} "
            f"(naive would say {pair['od_median_naive']})"
        )

    leaks_somewhere = any(s["differing_rows"] > 0 for s in proof["leak"].values())
    boundaries_differ = all(pair["windows_differ"] for pair in proof["boundary_pairs"])

    stamped = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    parity_record = {
        "measured_at": stamped,
        "row_set": str(ROWS_CSV.relative_to(REPO_ROOT)),
        "rows": int(len(rows)),
        "tolerance": TOLERANCE,
        "max_abs_delta_over_all_float_columns": max_delta,
        "columns": [v.as_record() for v in verdicts],
        "shortfalls": shortfalls,
        "no_geometry": geometry_checks,
        "quarantine": meta,
        "fitted_months": list(truth["fitted_months"]),
    }
    proof_record = {
        "measured_at": stamped,
        "naive_timestamp": naive.isoformat(),
        "fitted_months": list(truth["fitted_months"]),
        "full_window_months": list(truth["full_window_months"]),
        **proof,
    }
    if not args.no_write:
        RECORD_DIR.mkdir(parents=True, exist_ok=True)
        (RECORD_DIR / "retrieval_parity.json").write_text(
            json.dumps(parity_record, indent=2) + "\n"
        )
        (RECORD_DIR / "pit_proof.json").write_text(json.dumps(proof_record, indent=2) + "\n")
        print(f"\n[retrieval] records -> {RECORD_DIR.relative_to(REPO_ROOT)}/")

    problems: list[str] = []
    if failures:
        problems.append(f"{len(failures)} column(s) disagree with the feature path")
    for shortfall in unexplained:
        problems.append(
            f"{shortfall['answer']}: the store lost row(s) {shortfall['unexplained']} for no "
            "reason this check can account for — neither a duplicate entity key nor a "
            "timestamp earlier than every source row"
        )
    if not two_sided_ok:
        problems.append("a no-geometry zone came back with a row in the store")
    if not leaks_somewhere:
        problems.append(
            "the naive join produced NO difference anywhere — the proof proves nothing, "
            "which is a defect in the row set or in the stamps, not a clean bill of health"
        )
    if not boundaries_differ:
        problems.append("a month-boundary pair was served the SAME window on both sides")
    if naive_full["mismatches"]:
        problems.append("the naive answer is not the full-window table")

    if problems:
        for problem in problems:
            print(f"[retrieval] FAIL {problem}")
        return 1
    print("\n[retrieval] PASSED — the store reproduces the feature path exactly, and the "
          "point-in-time join is the reason the naive one differs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
