#!/usr/bin/env python
"""THE 100-pair online/offline parity table — the blueprint's named accept artifact.

M8-S4 leg 1. Runs on THIS side of the quarantine (pandas 3.0.5); imports
`taxi_mlops` and **never `feast`** (M8 law 4, AST-pinned). It shells out exactly
twice — once to `kubectl port-forward` (the online store has no hostPort, ADR-012)
and once to `infra/feast/online.py`, the far side of the wall — and parquet is the
only thing that crosses.

**A READER.** It deploys nothing, materializes nothing, fits nothing, mints no
MLflow run, reads no registry alias and touches no settled tree. Its only writes
are scratch parquet under `data/feast/online/` and its two records.

The design, the bar and the declared pair set are argued in
`docs/feast_online_m8.md`, which was committed BEFORE this script first ran —
the bar is a bar because of that ordering and not because of this docstring
(M8 law 4, the M7-S3 and M8-S3 precedent).

WHAT IS COMPARED, AND AGAINST WHAT
----------------------------------
**(1) The seam materialization creates.** Every column the ONLINE store hands
back must equal what the OFFLINE store hands back for the same entity key at an
instant AFTER the last window closed. The instant matters: `feast materialize`
keeps the latest row per key, so the online store serves the full window to every
request and has no history — retrieving the offline half at each row's own
timestamp would report a correctly-working store as a mismatch (gotcha #50, and
`docs/feast_online_m8.md` §1).

**(2) An anchor to the ONE feature path, so this is not two Feast reads agreeing
with each other.** The seven STATIC columns — the pickup and dropoff centroids,
boroughs and airport flags, and the three calendar flags — are additionally
compared against `taxi_mlops.features.zones` and `.calendar`, which is where the
champion's own 24-column matrix gets them. Those are the stored features the
champion actually eats. The two time-varying views are anchored by an INHERITED
measurement, cited and not re-run: M8-S3 measured the full-window retrieval equal
to our `aggregates.fit` table with 0 mismatches over 88 rows.

THE COMPARATOR IS IMPORTED, NOT RE-IMPLEMENTED
----------------------------------------------
`compare()` and `ColumnVerdict` come from `scripts/feast_retrieval.py`. Both M8
seams are then judged by ONE definition of agreement — both-missing agrees,
**one-missing is a MISMATCH** — and that definition cannot drift between the two
tables. `NaN != NaN`, so a comparison that dropped nulls would print a perfect
zero while being blind to the ~1% of real traffic that has no geometry at all.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from taxi_mlops.features import zones  # noqa: E402
from taxi_mlops.features import calendar as calendar_features  # noqa: E402

# The comparator, imported so the two M8 seams cannot disagree about what
# agreement means. `feast_retrieval` imports taxi_mlops and never feast, so this
# does not widen the wall.
from feast_retrieval import ColumnVerdict, compare  # noqa: E402
from feast_source_window import window as source_window  # noqa: E402

PAIRS_CSV = REPO_ROOT / "infra" / "feast" / "online_pairs.csv"
QUARANTINE_PYTHON = REPO_ROOT / ".venv-feast" / "bin" / "python"
READER = REPO_ROOT / "infra" / "feast" / "online.py"
WORK_DIR = REPO_ROOT / "data" / "feast" / "online"
RECORD_DIR = REPO_ROOT / "automation" / "runs" / "m8-online"
TABLE_MD = REPO_ROOT / "docs" / "feast_online_parity_table.md"

#: The bar, in the units of each column. EXACT — argued for THIS path (protobuf
#: `double` is fixed-width, bool/string have no numeric path, the hop moves bytes,
#: the entity-key serialization is pinned, and `materialize` selects rather than
#: aggregates) in `docs/feast_online_m8.md` §2. A module constant so the gate and
#: the tests read the number this script applied, never the one the prose argues
#: (F-017).
TOLERANCE = 0.0

#: answer name -> the keys that answer is keyed on, as `(the VIEW's join key, the
#: ENTITY frame's column)`. The two names differ for exactly one view and that is
#: deliberate: a trip has TWO zones, so a view keyed on `zone_id` must be asked
#: twice and the answer comes back under the view's name, not the trip's. Getting
#: this pair wrong is not a silent error — the aligner raises a KeyError — which
#: is why it is a table rather than a convention.
#:
#: The offline half is re-attached BY THESE, never by position: every declared
#: pair is retrieved at the SAME instant, so `(keys, timestamp)` duplicates are
#: the rule rather than the exception here (F-056 cause 1), and aligning on order
#: would manufacture a mismatch out of correct behaviour.
ANSWER_KEYS: dict[str, tuple[tuple[str, str], ...]] = {
    "pu_zone": (("zone_id", "PULocationID"),),
    "do_zone": (("zone_id", "DOLocationID"),),
    "calendar": (("date_key", "date_key"),),
    "od_window": (("PULocationID", "PULocationID"), ("DOLocationID", "DOLocationID")),
    "pu_hour_window": (("PULocationID", "PULocationID"), ("hour", "hour")),
}

#: answer name -> the columns compared for it.
ANSWER_COLUMNS: dict[str, tuple[tuple[str, str], ...]] = {
    "pu_zone": (
        ("centroid_lat", "float"),
        ("centroid_lon", "float"),
        ("borough", "string"),
        ("is_airport", "bool"),
    ),
    "do_zone": (
        ("centroid_lat", "float"),
        ("centroid_lon", "float"),
        ("borough", "string"),
        ("is_airport", "bool"),
    ),
    "calendar": (
        ("is_holiday", "bool"),
        ("is_near_holiday", "bool"),
        ("is_business_day", "bool"),
    ),
    "od_window": (("od_median_duration_min", "float"), ("window_months", "string")),
    "pu_hour_window": (
        ("pu_hour_mean_speed_kmh", "float"),
        ("pu_hour_trips_per_day", "float"),
        ("window_months", "string"),
    ),
}


def load_pairs() -> pd.DataFrame:
    """The committed pair set. Read, never generated here."""
    if not PAIRS_CSV.exists():
        raise SystemExit(
            f"[online-parity] {PAIRS_CSV} is missing. It is a COMMITTED artifact — rebuild "
            "it deliberately with `uv run python scripts/feast_online_pairs.py --refresh`, "
            "which changes the set every number in docs/feast_online_m8.md was measured on."
        )
    with PAIRS_CSV.open() as handle:
        records = list(csv.DictReader(handle))
    frame = pd.DataFrame(records)
    frame["row_id"] = frame["row_id"].astype("int64")
    frame["PULocationID"] = frame["PULocationID"].astype("int64")
    frame["DOLocationID"] = frame["DOLocationID"].astype("int64")
    frame["tpep_pickup_datetime"] = pd.to_datetime(frame["pickup_datetime"])
    return frame.sort_values("row_id", ignore_index=True)


def entity_frame(rows: pd.DataFrame) -> pd.DataFrame:
    """The same shape M8-S3 hands the store — one definition of an entity row."""
    return pd.DataFrame(
        {
            "row_id": rows["row_id"].to_numpy(),
            "PULocationID": rows["PULocationID"].to_numpy(),
            "DOLocationID": rows["DOLocationID"].to_numpy(),
            # int64 explicitly: `dt.hour` is int32, and merging it against the
            # store's int64 join key makes dask warn about a dtype mismatch on
            # every retrieval. The warning is harmless here and the cast is not a
            # fix for it — it is the same "spell one thing one way" rule the
            # composite entity keys already follow.
            "hour": rows["tpep_pickup_datetime"].dt.hour.to_numpy().astype("int64"),
            "date_key": rows["tpep_pickup_datetime"].dt.strftime("%Y-%m-%d").to_numpy(),
            "event_timestamp": rows["tpep_pickup_datetime"].to_numpy(),
        }
    )


@contextmanager
def port_forward(local_port: int, namespace: str = "feast"):
    """The host's only route to the online store — ephemeral, and torn down here.

    Redis gets no hostPort (ADR-012: kind publishes host ports at cluster-CREATE
    only and this cluster's PVCs are the only copy of the registry), so the host
    reaches it exactly the way `make flyte-console` and the pushgateway are
    reached. The local port is deliberately 6380 rather than 6379 so a run can
    never silently talk to a developer's own local Redis.
    """
    command = [
        "kubectl",
        "--context",
        os.environ.get("KUBE_CONTEXT", "kind-mlops-taxi"),
        "-n",
        namespace,
        "port-forward",
        "svc/redis",
        f"{local_port}:6379",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        deadline = time.time() + 20
        ready = False
        while time.time() < deadline:
            if process.poll() is not None:
                raise SystemExit(
                    "[online-parity] the port-forward exited immediately:\n"
                    + (process.stdout.read() if process.stdout else "")
                )
            line = process.stdout.readline() if process.stdout else ""
            if "Forwarding from" in line:
                ready = True
                break
        if not ready:
            raise SystemExit("[online-parity] the port-forward never reported Forwarding from")
        print(f"[online-parity] forward: localhost:{local_port} -> svc/redis:6379 (ephemeral)")
        yield f"localhost:{local_port}"
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover - belt and braces
            process.kill()


def run_quarantine(entities: Path, as_of: pd.Timestamp, connection: str) -> dict[str, Any]:
    """Cross the wall. The far side imports feast; this side never does."""
    if not QUARANTINE_PYTHON.exists():
        raise SystemExit(
            f"[online-parity] the quarantine interpreter {QUARANTINE_PYTHON} does not exist. "
            "Build it with `make feast-quarantine` — feast is NOT and will never be a "
            "project dependency (M8 law 4: it pins pandas<3 against our 3.0.5)."
        )
    environment = dict(os.environ, FEAST_REDIS_CONNECTION=connection)
    subprocess.run(
        [
            str(QUARANTINE_PYTHON),
            str(READER),
            "--entities",
            str(entities),
            "--out-dir",
            str(WORK_DIR),
            "--as-of",
            as_of.isoformat(),
        ],
        check=True,
        env=environment,
    )
    return json.loads((WORK_DIR / "online.json").read_text())


def _online(name: str, rows: pd.DataFrame) -> pd.DataFrame:
    """The online answer, aligned by row_id — a LOOKUP returns one row per request."""
    frame = pd.read_parquet(WORK_DIR / f"{name}.online.parquet")
    entity = entity_frame(rows)
    if len(frame) != len(entity):
        raise SystemExit(
            f"[online-parity] {name}: get_online_features returned {len(frame)} rows for "
            f"{len(entity)} declared pairs. A LOOKUP must answer per requested row; a "
            "shortfall here is not F-056's join behaviour and must not be explained away."
        )
    return frame.sort_values("row_id", ignore_index=True)


def _keyed_entities(name: str, rows: pd.DataFrame) -> pd.DataFrame:
    """The declared pairs, carrying the key columns under the VIEW's own names."""
    entity = entity_frame(rows)
    keyed = pd.DataFrame({"row_id": entity["row_id"]})
    for view_key, entity_column in ANSWER_KEYS[name]:
        keyed[view_key] = entity[entity_column].to_numpy()
    return keyed


def _offline(name: str, rows: pd.DataFrame) -> pd.DataFrame:
    """The offline answer, re-attached BY THE KEYS the store keyed on (F-056)."""
    frame = pd.read_parquet(WORK_DIR / f"{name}.offline.parquet")
    keys = [view_key for view_key, _ in ANSWER_KEYS[name]]
    keyed = _keyed_entities(name, rows)
    features = [column for column, _ in ANSWER_COLUMNS[name]]
    lookup = frame[[*keys, *features]].drop_duplicates(keys)
    aligned = keyed.merge(lookup, on=keys, how="left")
    return aligned.sort_values("row_id", ignore_index=True)


def explain_shortfall(name: str, rows: pd.DataFrame) -> dict[str, Any]:
    """Classify every declared pair the OFFLINE join did not answer. No class = FAIL.

    Both legitimate classes were measured at M8-S3 (F-056): a duplicate
    `(entity keys, timestamp)` is answered once, and a row with no source row at
    or before its timestamp is DROPPED rather than nulled. Here every row is
    retrieved at the same instant — after the last window closed — so the second
    class should be empty and the first is deliberately provoked by declared rows
    90 and 91. Anything else is a row the store lost, and after a left join a
    lost row and a genuinely absent value render identically (gotcha #78).
    """
    frame = pd.read_parquet(WORK_DIR / f"{name}.offline.parquet")
    keys = [view_key for view_key, _ in ANSWER_KEYS[name]]
    keyed = _keyed_entities(name, rows)
    answered = set(map(tuple, frame[keys].drop_duplicates().to_numpy().tolist()))
    absent = keyed[~keyed["row_id"].isin(frame["row_id"])]

    duplicates, unexplained = [], []
    for record in absent.to_dict("records"):
        signature = tuple(record[key] for key in keys)
        (duplicates if signature in answered else unexplained).append(int(record["row_id"]))
    return {
        "answer": name,
        "declared": int(len(keyed)),
        "returned": int(len(frame)),
        "duplicate_entity_key": duplicates,
        "unexplained": unexplained,
    }


def seam_parity(rows: pd.DataFrame) -> list[ColumnVerdict]:
    """(1) online vs offline, column by column, over every declared pair."""
    row_ids = rows["row_id"].to_numpy()
    verdicts: list[ColumnVerdict] = []
    for name, columns in ANSWER_COLUMNS.items():
        online = _online(name, rows)
        offline = _offline(name, rows)
        for column, kind in columns:
            verdicts.append(
                compare(
                    f"{name}.{column}",
                    kind,
                    online[column].to_numpy(),
                    offline[column].to_numpy(),
                    row_ids,
                )
            )
    return verdicts


def feature_path_anchor(rows: pd.DataFrame) -> list[ColumnVerdict]:
    """(2) the STATIC columns against the ONE `taxi_mlops.features` path.

    These seven columns are every stored feature the champion actually eats: the
    nine g2 geometry features are all lookups on the centroid table and the three
    g1 calendar flags are this table. Comparing them against the functions the
    champion's own matrix is built from is what stops this whole exercise being
    two Feast reads agreeing with each other.

    `borough` and `is_airport` are compared only where the store HAS the zone: for
    a no-geometry zone the store has no row at all while our table answers
    "Unknown"/False — the same fact in two vocabularies, asserted two-sidedly by
    `no_geometry_assertion` rather than compared here (M8-S3's decision, inherited).
    """
    row_ids = rows["row_id"].to_numpy()
    table = zones.load_zone_table()
    flags = calendar_features.flags(rows["tpep_pickup_datetime"])
    verdicts: list[ColumnVerdict] = []

    for side, name, column in (("pu", "pu_zone", "PULocationID"), ("do", "do_zone", "DOLocationID")):
        ids = zones._clip_ids(rows[column])
        online = _online(name, rows)
        present = ~np.isnan(table.lat[ids])
        verdicts.append(
            compare(
                f"anchor.{side}.centroid_lat", "float", table.lat[ids], online["centroid_lat"], row_ids
            )
        )
        verdicts.append(
            compare(
                f"anchor.{side}.centroid_lon", "float", table.lon[ids], online["centroid_lon"], row_ids
            )
        )
        boroughs = np.array([table.boroughs[code] for code in table.borough_code[ids]])
        verdicts.append(
            compare(
                f"anchor.{side}.borough (zones with geometry)",
                "string",
                boroughs[present],
                online["borough"].to_numpy()[present],
                row_ids[present],
            )
        )
        verdicts.append(
            compare(
                f"anchor.{side}.is_airport (zones with geometry)",
                "bool",
                np.isin(ids, list(zones.AIRPORT_ZONES))[present],
                online["is_airport"].to_numpy()[present],
                row_ids[present],
            )
        )

    calendar_answer = _online("calendar", rows)
    for flag in ("is_holiday", "is_near_holiday", "is_business_day"):
        verdicts.append(
            compare(
                f"anchor.{flag}", "bool", np.asarray(flags[flag]), calendar_answer[flag], row_ids
            )
        )
    return verdicts


def no_geometry_assertion(rows: pd.DataFrame) -> dict[str, Any]:
    """Two-sided, never compared: the store says NOTHING, our path says Unknown/False.

    Zones 264/265 are TLC's non-places and have no centroid row by design (DR-04
    condition 1). Manufacturing a zeroed row in the store to make a column-wise
    comparison succeed would put a plausible place at the equator into a feature
    store. So the assertion is that the ONLINE store returns null for exactly the
    rows our path reports as having no geometry.
    """
    table = zones.load_zone_table()
    result: dict[str, Any] = {}
    for side, name, column in (("pu", "pu_zone", "PULocationID"), ("do", "do_zone", "DOLocationID")):
        ids = zones._clip_ids(rows[column])
        ours_missing = np.isnan(table.lat[ids])
        online = _online(name, rows)
        theirs_missing = online["centroid_lat"].isna().to_numpy()
        result[side] = {
            "rows_without_geometry_our_path": int(ours_missing.sum()),
            "rows_the_store_declined": int(theirs_missing.sum()),
            "disagreements": int((ours_missing != theirs_missing).sum()),
            "zone_ids": sorted({int(value) for value in rows[column].to_numpy()[ours_missing]}),
        }
    result["ok"] = all(side["disagreements"] == 0 for key, side in result.items() if key != "ok")
    return result


def _finite(value: float | None) -> float | None:
    return None if value is None or not np.isfinite(value) else float(value)


def write_table(verdicts: list[ColumnVerdict], anchors: list[ColumnVerdict], meta: dict[str, Any]):
    """The committed accept artifact — the table a human reads, in one file."""
    lines = [
        "# The 100-pair online/offline parity table (M8-S4)",
        "",
        "**Generated by `make feast-online-parity`. Do not hand-edit** — it is the",
        "blueprint's named accept artifact for M8 and the file a reviewer diffs.",
        "The design, the declared pair set and the bar are argued in",
        "`docs/feast_online_m8.md`; the record is",
        "`automation/runs/m8-online/online_parity.json`.",
        "",
        f"* declared pairs: **{meta['declared_pairs']}**",
        f"* offline half retrieved as of: **{meta['as_of']}** (after the last window closed —",
        "  the online store keeps the latest row per key and has no history)",
        f"* bar: **EXACT (tolerance {meta['tolerance']})**",
        f"* measured: **{meta['measured_at']}**",
        "",
        "## (1) The seam materialization creates — online vs offline",
        "",
        "| column | kind | compared | mismatches | max abs delta | both missing | one missing |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]

    def row(verdict: ColumnVerdict) -> str:
        delta = "—" if verdict.max_abs_delta is None else f"{verdict.max_abs_delta:.3e}"
        return (
            f"| `{verdict.column}` | {verdict.kind} | {verdict.compared} | {verdict.mismatches} "
            f"| {delta} | {verdict.both_missing} | {verdict.one_missing} |"
        )

    lines += [row(verdict) for verdict in verdicts]
    lines += [
        "",
        "## (2) The anchor — the STATIC columns against the ONE `taxi_mlops.features` path",
        "",
        "These seven columns are every stored feature the champion actually eats.",
        "Without this block the table above would be two Feast reads agreeing with",
        "each other. The two time-varying views are anchored by an INHERITED",
        "measurement instead (M8-S3: the full-window retrieval equals our",
        "`aggregates.fit` table, 0 mismatches over 88 rows) — cited, not re-run.",
        "",
        "| column | kind | compared | mismatches | max abs delta | both missing | one missing |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    lines += [row(verdict) for verdict in anchors]
    lines += ["", f"**Verdict: {meta['verdict']}**", ""]
    TABLE_MD.write_text("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-port", type=int, default=6380)
    parser.add_argument(
        "--no-write", action="store_true", help="print the verdicts and write no record or table"
    )
    args = parser.parse_args(argv)

    rows = load_pairs()
    _, as_of = source_window()
    print(f"[online-parity] {len(rows)} declared pair(s) from {PAIRS_CSV.name}")
    print(f"[online-parity] offline half retrieved as of {as_of.isoformat()} (DERIVED)")
    print(f"[online-parity] bar: EXACT, tolerance {TOLERANCE}")

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    entities_path = WORK_DIR / "entities.parquet"
    entity_frame(rows).to_parquet(entities_path, index=False)

    with port_forward(args.local_port) as connection:
        crossing = run_quarantine(entities_path, as_of, connection)

    verdicts = seam_parity(rows)
    anchors = feature_path_anchor(rows)
    geometry = no_geometry_assertion(rows)
    shortfalls = {name: explain_shortfall(name, rows) for name in ANSWER_KEYS}

    print("\n[online-parity] (1) the seam: online vs offline")
    for verdict in verdicts:
        delta = "—" if verdict.max_abs_delta is None else f"{verdict.max_abs_delta:.3e}"
        mark = "ok  " if verdict.ok else "FAIL"
        print(
            f"[online-parity]   {mark} {verdict.column:<44s} n={verdict.compared:<4d} "
            f"mismatch={verdict.mismatches:<3d} max|d|={delta:<10s} "
            f"both-missing={verdict.both_missing:<3d} one-missing={verdict.one_missing}"
        )
    print("[online-parity] (2) the anchor: the store vs the ONE feature path")
    for verdict in anchors:
        delta = "—" if verdict.max_abs_delta is None else f"{verdict.max_abs_delta:.3e}"
        mark = "ok  " if verdict.ok else "FAIL"
        print(
            f"[online-parity]   {mark} {verdict.column:<44s} n={verdict.compared:<4d} "
            f"mismatch={verdict.mismatches:<3d} max|d|={delta}"
        )

    print("[online-parity] (3) the no-geometry rows, asserted two-sidedly")
    for side in ("pu", "do"):
        info = geometry[side]
        print(
            f"[online-parity]   {side}: our path has no geometry on "
            f"{info['rows_without_geometry_our_path']} row(s), the store declined "
            f"{info['rows_the_store_declined']}, disagreements {info['disagreements']} "
            f"(zones {info['zone_ids']})"
        )

    print("[online-parity] (4) the offline join's shortfall, CLASSIFIED (F-056)")
    unexplained_total = 0
    for name, info in shortfalls.items():
        unexplained_total += len(info["unexplained"])
        print(
            f"[online-parity]   {name:<16s} declared={info['declared']} "
            f"returned={info['returned']} duplicate-key={len(info['duplicate_entity_key'])} "
            f"UNEXPLAINED={len(info['unexplained'])}"
        )

    deltas = [verdict.max_abs_delta for verdict in verdicts if verdict.max_abs_delta is not None]
    worst = max(deltas) if deltas else 0.0
    failures = [verdict.column for verdict in verdicts + anchors if not verdict.ok]
    ok = not failures and geometry["ok"] and unexplained_total == 0
    verdict_text = "PASSED" if ok else "FAILED"
    print(
        f"\n[online-parity] max |online - offline| = {worst:.3e} over "
        f"{len(verdicts)} column(s) and {len(rows)} declared pair(s), bar {TOLERANCE}"
    )
    print(f"[online-parity] {verdict_text}")
    if failures:
        print(f"[online-parity] failing column(s): {failures}")

    if not args.no_write:
        meta = {
            "declared_pairs": int(len(rows)),
            "as_of": as_of.isoformat(),
            "tolerance": TOLERANCE,
            "measured_at": datetime.now(UTC).isoformat(),
            "verdict": verdict_text,
        }
        RECORD_DIR.mkdir(parents=True, exist_ok=True)
        (RECORD_DIR / "online_parity.json").write_text(
            json.dumps(
                {
                    "story": "M8-S4",
                    **meta,
                    "max_abs_delta": _finite(worst),
                    "crossing": crossing,
                    "seam": [verdict.as_record() for verdict in verdicts],
                    "anchor_to_feature_path": [verdict.as_record() for verdict in anchors],
                    "no_geometry": geometry,
                    "offline_shortfall": shortfalls,
                    "inherited_anchor": (
                        "the time-varying columns' agreement with taxi_mlops.features."
                        "aggregates is M8-S3's measurement (automation/runs/m8-pit/"
                        "pit_proof.json: the full-window retrieval, 0 mismatches over 88 "
                        "rows) — cited, not re-run"
                    ),
                },
                indent=2,
            )
            + "\n"
        )
        write_table(verdicts, anchors, meta)
        print(f"[online-parity] record: {(RECORD_DIR / 'online_parity.json').relative_to(REPO_ROOT)}")
        print(f"[online-parity] table : {TABLE_MD.relative_to(REPO_ROOT)}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
