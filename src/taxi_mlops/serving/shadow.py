"""The shadow run: one rider question, two models, and where they disagree (M6-S3).

`make shadow-run`. It sends the SAME quote requests to the champion
(`nyc-taxi-eta`, registry version 2, 24 features) and to the shadow
(`nyc-taxi-eta-shadow`, registry version 1, 5 features), and writes the
disagreement table the DA memo reads.

--------------------------------------------------------------------------
WHY DUAL-SEND AND NOT MIRRORING — MEASURED, NOT ASSUMED
--------------------------------------------------------------------------
The obvious way to shadow is to mirror the live wire: ingress-nginx has a
`mirror-target` annotation, and M6-S3's spike proved it engages (the annotation
survives on the Ingress KServe owns, and nginx.conf gains a real `mirror`
directive). It still cannot shadow v1, for two reasons the spike separated:

1. **The V2 model name is in the URL path.** Mirrored traffic asks for
   `/v2/models/nyc-taxi-eta/infer`; the shadow's mlserver serves
   `nyc-taxi-eta-shadow` and answers **404**. Measured: 100 of 100 canary-routed
   requests, never a number.
2. **The schema differs.** Even addressed correctly, v1's logged signature
   covers 5 columns and the live wire carries 24 — F-032's shape.

(1) is a property of any two-InferenceService split and (2) is a property of
THIS challenger. Mirroring stays the right mechanism for a same-schema, same-name
challenger; ADR-011 records both walls with their numbers.

So each target's matrix is built through the ONE `taxi_mlops.features` path from
the SAME raw requests — v1's five columns for the shadow, v2's twenty-four for
the champion. That is the only construction under which a delta means "these two
models disagree" rather than "these two clients disagree".

--------------------------------------------------------------------------
THE REQUEST SET IS DECLARED AND STRATIFIED, AND THAT IS DELIBERATE
--------------------------------------------------------------------------
A flat random sample of test rows would be ~99% ordinary trips and would carry
roughly zero long trips and a handful of no-geometry rows — i.e. it would have
nothing to say about the three segments the memo exists to examine. This program
has a rule about that (M5-S3: *the rows that break serving are never the average
ones*), so the sample is STRATIFIED: a fixed number of rows per segment, drawn
deterministically, plus parity's 16 declared hazards.

The sample is reproducible without storing it: rows are ordered by a hash of
their own request fields and the first K taken, so the same analyst layer yields
the same rows on any machine, and `data/processed.dvc` pins the analyst layer.
`ORDER BY random()` would make every run a different table and the memo's numbers
unciteable.

**Truth travels with the rows.** `trips_test` carries `trip_duration_minutes`,
so the table records not only how far apart the two models are but which one was
closer — on the untouched holdout month. That is a stronger artifact than a pure
disagreement table and it costs nothing extra. What it is NOT is a re-run of the
bake-off: this is a sample, scored on the wire, and `docs/bakeoff_m3.md`'s
full-holdout numbers remain the measurement of record (gotcha #15's discipline —
a number from a sample is labelled as one).

This module is a READER. It resolves nothing that mutates, moves no alias,
deploys nothing, and writes only its own record.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..features import quote_time, sets
from .client import DEFAULT_ROUTE, Endpoint, QuoteRequest, build_matrix, infer_matrix, minutes_of
from .parity import HAZARDS

RECORD = Path("automation/runs/m6-shadow/disagreement.json")

CHAMPION_NAME = "nyc-taxi-eta"
SHADOW_NAME = "nyc-taxi-eta-shadow"

#: TLC's airport zones. JFK 132, LaGuardia 138, Newark 1 — the segment M2-S4
#: measured at 1.9x the error and M3's centroid geometry did NOT close
#: (`docs/error_memo_m2.md` §7 row 2, still open). v1 has no geometry at all, so
#: if geometry is what separates the two models this is where it should show.
AIRPORT_ZONES = (1, 132, 138)

#: TLC's "Unknown" zones. They are not places, they have no centroid by design
#: (DR-04 condition 1), and 264->264 is the largest single OD "route" in the
#: data. v2 carries nine NaN geometry features here and v1 carries none at all —
#: the one segment where the extra features are pure absence.
NO_GEOMETRY_ZONES = (264, 265)

#: Rows per segment. 250 is enough for a stable median and the quartiles the memo
#: quotes, and small enough that all eight requests (4 segments x 2 targets) fit
#: comfortably in one V2 body each.
ROWS_PER_SEGMENT = 250

SEGMENT_SQL: dict[str, str] = {
    "ordinary": (
        "PULocationID NOT IN {no_geom} AND DOLocationID NOT IN {no_geom} "
        "AND PULocationID NOT IN {airports} AND DOLocationID NOT IN {airports} "
        "AND trip_duration_minutes < 60"
    ),
    "airport": "(PULocationID IN {airports} OR DOLocationID IN {airports})",
    "no_geometry": "(PULocationID IN {no_geom} OR DOLocationID IN {no_geom})",
    "long_trip": "trip_duration_minutes >= 60",
}


def _segment_query(predicate: str, limit: int) -> str:
    where = predicate.format(no_geom=NO_GEOMETRY_ZONES, airports=AIRPORT_ZONES)
    return f"""
        SELECT tpep_pickup_datetime, PULocationID, DOLocationID,
               passenger_count, trip_duration_minutes
        FROM trips_test
        WHERE {where}
        ORDER BY hash(tpep_pickup_datetime || '|' || PULocationID || '|' ||
                      DOLocationID || '|' || passenger_count)
        LIMIT {limit}
    """


def load_sample(rows_per_segment: int = ROWS_PER_SEGMENT) -> pd.DataFrame:
    """The stratified request set, from the analyst layer's VIEWS (never parquet).

    M1-S2's rule, inherited: the DA cites view names, and so does this. A path
    would be a second definition of what `test` means.
    """
    # Local import: the quote path must not need duckdb, and this module is the
    # only part of `serving/` that reads the warehouse at all.
    from ..data.analyst import connect
    from ..data.config import load_config

    frames = []
    connection = connect(load_config(), read_only=True)
    try:
        for segment, predicate in SEGMENT_SQL.items():
            frame = connection.execute(_segment_query(predicate, rows_per_segment)).df()
            frame["segment"] = segment
            frames.append(frame)
    finally:
        connection.close()
    sample = pd.concat(frames, ignore_index=True)
    sample["source"] = "trips_test"
    return sample


def hazard_frame() -> pd.DataFrame:
    """Parity's 16 declared hazards, as rows with no truth attached.

    They are in the set because they are the rows most likely to make two models
    diverge for a structural reason rather than a statistical one. They carry no
    `trip_duration_minutes` — several are synthetic dates that no trip has — so
    every accuracy statistic below is computed on the sampled rows only, and the
    record says so per segment rather than leaving it to be assumed.
    """
    return pd.DataFrame(
        [
            {
                "tpep_pickup_datetime": pd.Timestamp(h.request.pickup_datetime),
                "PULocationID": h.request.pu_location_id,
                "DOLocationID": h.request.do_location_id,
                "passenger_count": h.request.passenger_count,
                "trip_duration_minutes": np.nan,
                "segment": "declared_hazard",
                "source": h.name,
            }
            for h in HAZARDS
        ]
    )


def _requests(frame: pd.DataFrame) -> list[QuoteRequest]:
    return [
        QuoteRequest(
            pickup_datetime=str(row.tpep_pickup_datetime),
            pu_location_id=int(row.PULocationID),
            do_location_id=int(row.DOLocationID),
            passenger_count=float(row.passenger_count),
        )
        for row in frame.itertuples()
    ]


def score(
    frame: pd.DataFrame, feature_set: str, endpoint: Endpoint, *, timeout: float = 300.0
) -> np.ndarray:
    """One target's answers for these rows, built through the ONE feature path."""
    cfg = sets.resolve_set(feature_set)
    requests = _requests(frame)
    matrix = build_matrix(requests, cfg)
    response = infer_matrix(matrix, quote_time.feature_names(cfg), endpoint, timeout=timeout)
    return minutes_of(response)


def _stats(group: pd.DataFrame) -> dict[str, Any]:
    delta = group["delta_minutes"]
    scored = group.dropna(subset=["trip_duration_minutes"])
    out: dict[str, Any] = {
        "rows": int(len(group)),
        "mean_abs_delta_min": round(float(delta.abs().mean()), 4),
        "median_abs_delta_min": round(float(delta.abs().median()), 4),
        "p90_abs_delta_min": round(float(delta.abs().quantile(0.90)), 4),
        "max_abs_delta_min": round(float(delta.abs().max()), 4),
        # Signed, because "how far apart" hides the direction and the direction is
        # what a memo needs: a challenger that is uniformly HIGHER is a different
        # problem from one that is noisier around the same centre.
        "mean_signed_delta_min_shadow_minus_champion": round(float(delta.mean()), 4),
        "shadow_quotes_higher_pct": round(float((delta > 0).mean() * 100.0), 2),
        "has_truth": bool(len(scored)),
    }
    if len(scored):
        champion_ae = (scored["champion_minutes"] - scored["trip_duration_minutes"]).abs()
        shadow_ae = (scored["shadow_minutes"] - scored["trip_duration_minutes"]).abs()
        out |= {
            "champion_mae_min": round(float(champion_ae.mean()), 4),
            "shadow_mae_min": round(float(shadow_ae.mean()), 4),
            "champion_closer_pct": round(float((champion_ae < shadow_ae).mean() * 100.0), 2),
            "champion_within_5min_pct": round(float((champion_ae <= 5).mean() * 100.0), 2),
            "shadow_within_5min_pct": round(float((shadow_ae <= 5).mean() * 100.0), 2),
        }
    return out


def run(
    route: str = DEFAULT_ROUTE,
    rows_per_segment: int = ROWS_PER_SEGMENT,
    record: Path = RECORD,
) -> dict[str, Any]:
    champion = Endpoint(name=CHAMPION_NAME, namespace="serving", route=route)
    shadow = Endpoint(name=SHADOW_NAME, namespace="serving", route=route)

    frame = pd.concat([load_sample(rows_per_segment), hazard_frame()], ignore_index=True)

    # Scored per segment: one V2 body per (segment, target), so a segment that
    # fails to encode names itself instead of taking the whole run down.
    champion_out: list[np.ndarray] = []
    shadow_out: list[np.ndarray] = []
    for segment in frame["segment"].unique():
        rows = frame[frame["segment"] == segment]
        champion_out.append(score(rows, "v2", champion))
        shadow_out.append(score(rows, "v1", shadow))
    frame["champion_minutes"] = np.concatenate(champion_out)
    frame["shadow_minutes"] = np.concatenate(shadow_out)
    frame["delta_minutes"] = frame["shadow_minutes"] - frame["champion_minutes"]

    payload: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "champion": {"endpoint": champion.infer_url, "feature_set": "v2"},
        "shadow": {"endpoint": shadow.infer_url, "feature_set": "v1"},
        "rows_per_segment": rows_per_segment,
        "what_this_is_not": (
            "a re-run of the M3 bake-off. These are sampled rows scored on the wire; "
            "docs/bakeoff_m3.md's full-holdout numbers remain the measurement of record."
        ),
        "overall": _stats(frame),
        "by_segment": {
            str(segment): _stats(frame[frame["segment"] == segment])
            for segment in frame["segment"].unique()
        },
    }
    # The served versions, read off the answers themselves rather than assumed —
    # the M5-S2 property: which model produced THIS number travels WITH it.
    payload["served_versions"] = {
        "champion": str(
            infer_matrix(
                build_matrix(_requests(frame.head(1)), sets.resolve_set("v2")),
                quote_time.feature_names(sets.resolve_set("v2")),
                champion,
            ).get("model_version")
        ),
        "shadow": str(
            infer_matrix(
                build_matrix(_requests(frame.head(1)), sets.resolve_set("v1")),
                quote_time.feature_names(sets.resolve_set("v1")),
                shadow,
            ).get("model_version")
        ),
    }
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps(payload, indent=2) + "\n")
    frame.to_csv(record.with_suffix(".csv"), index=False)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--route", default=DEFAULT_ROUTE)
    parser.add_argument("--rows-per-segment", type=int, default=ROWS_PER_SEGMENT)
    args = parser.parse_args(argv)

    payload = run(route=args.route, rows_per_segment=args.rows_per_segment)
    print(
        f"[shadow] champion version {payload['served_versions']['champion']} (v2) vs "
        f"shadow version {payload['served_versions']['shadow']} (v1)"
    )
    header = (
        f"{'segment':<18}{'rows':>6}{'mean|d|':>10}{'p90|d|':>10}"
        f"{'max|d|':>10}{'champ MAE':>12}{'shadow MAE':>12}{'champ closer':>14}"
    )
    print(header)
    print("-" * len(header))
    for segment, stats in payload["by_segment"].items():
        print(
            f"{segment:<18}{stats['rows']:>6}{stats['mean_abs_delta_min']:>10.2f}"
            f"{stats['p90_abs_delta_min']:>10.2f}{stats['max_abs_delta_min']:>10.2f}"
            f"{stats.get('champion_mae_min', float('nan')):>12.2f}"
            f"{stats.get('shadow_mae_min', float('nan')):>12.2f}"
            f"{stats.get('champion_closer_pct', float('nan')):>13.1f}%"
        )
    overall = payload["overall"]
    print("-" * len(header))
    print(
        f"{'ALL':<18}{overall['rows']:>6}{overall['mean_abs_delta_min']:>10.2f}"
        f"{overall['p90_abs_delta_min']:>10.2f}{overall['max_abs_delta_min']:>10.2f}"
        f"{overall.get('champion_mae_min', float('nan')):>12.2f}"
        f"{overall.get('shadow_mae_min', float('nan')):>12.2f}"
        f"{overall.get('champion_closer_pct', float('nan')):>13.1f}%"
    )
    print(f"[shadow] {RECORD}  (+ .csv, row grain)")
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised through `make shadow-run`
    raise SystemExit(main())
