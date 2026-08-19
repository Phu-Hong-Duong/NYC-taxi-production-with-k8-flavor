"""THE parity test: the champion loaded here vs the champion on the wire, 1e-6.

M5-S3. This is the single most load-bearing serving fact this program can state,
and until it is measured every other serving claim rests on an assumption:

    *the number the endpoint returns is the number the model was gated on.*

Nothing else checks it. The promotion gate measured a model in this process
(M2-S3, M3-S5). `make predictions` re-scores that model in this process and
refuses to publish if it moved (M2-S4). `make serve` proves an InferenceService
is Ready and answers ONE row (M5-S2). Between the last two there is a container
built from a different base, running a different Python, a different pandas and
a different numpy, reached over an HTTP hop that serialises every feature to
text — and no measurement across it. Train/serve skew is the classic failure of
this seam precisely because both halves keep working while they disagree.

WHAT IS MEASURED, AND WHAT IS NOT
---------------------------------
ONE matrix is built, through `taxi_mlops.features`, and scored TWICE: once by
the booster loaded out of the registry into this process, once by the deployed
predictor. So the delta is attributable to the model bytes, the serving runtime
and the wire — and NOT to two feature builds that could have differed. That is
deliberate and it is the honest reading of the number: this test proves the
deployed model computes what the local one computes. It does NOT prove the
transformer M7 will add builds features the way training does; that seam does
not exist yet, and when it does it needs its own measurement.

The kickoff's expectation was float noise (~1e-7) because of a float32/float64
round trip. M5-S2 measured 0.000e+00 on one row instead, and this run says
whether that survives the hazards. Either way the MEASURED max is printed: a bar
passed silently teaches nothing, and a delta that walks from 0 to 1e-7 is a fact
about the runtime worth seeing before it walks to 1e-3.

THE ROWS ARE DECLARED, NAMED AND COMMITTED
------------------------------------------
`HAZARDS` below is the whole request set, one entry per thing that could
plausibly break differently on the two sides. Sampling random rows would give a
number that changes every run and a red team that cannot plant a cause; and the
rows that break serving are never the average ones. Each row says which hazard
it exists for, so a future reader can tell whether a new hazard is covered.

Two of them are worth naming here because they are the reason for the file:

- **no geometry (264/265).** Nine NaN features and `has_geometry = 0`. F-030
  was found by this story: the request was not merely wrong, it was a 422,
  because `json.dumps` writes NaN as a token JSON does not have. The fix is in
  `client._wire_values`; this row is what keeps it fixed, and what proves that
  mlserver's `null` decodes to the SAME missing value the booster was fitted on.
- **an unseen OD pair.** `55 -> 148` occurs 6 times in `trips_test` and never in
  `trips_train` — found by asking the analyst layer once (the query is in the
  entry's note) and committed as a literal, so parity stays a seconds-long
  reader instead of re-scanning 44M rows to re-derive a constant.

This module is a READER. It resolves the alias, loads a model, and POSTs; it
creates no run, moves no alias, deploys nothing and writes nothing but its own
record. `tests/unit/test_parity.py` pins that by parsing the AST, the way
`flyte_run_actions.py` is pinned.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .client import DEFAULT_ROUTE, Endpoint, QuoteRequest, build_matrix, minutes_of

#: The bar. `max |offline - online|` over every hazard row, in MINUTES. It is a
#: bar on the SEAM, not on the model: the two sides run the same trees over the
#: same inputs, so anything above float noise means one of them is not the model
#: we think it is. 1e-6 min is 60 microseconds of quoted ETA — far below any
#: number a rider or a KPI can see, and far above float32 round-trip noise.
TOLERANCE_MINUTES = 1e-6


@dataclass(frozen=True)
class Hazard:
    """One request, and the reason it is in the set."""

    name: str
    why: str
    request: QuoteRequest


#: Every row this test sends. Ordered roughly ordinary -> exotic; the ordering
#: has no meaning to the assertion, which is a max over all of them.
HAZARDS: tuple[Hazard, ...] = (
    Hazard(
        "ordinary-midday",
        "the common case: a weekday Midtown -> Upper East Side hop, all features present",
        QuoteRequest("2019-07-10T14:20:00", 161, 237, 1.0),
    ),
    Hazard(
        "ordinary-weekend-night",
        "is_weekend=1 and part_of_day at the other end of the clock",
        QuoteRequest("2019-07-06T02:45:00", 79, 107, 2.0),
    ),
    Hazard(
        "airport-jfk",
        "JFK (132): 8.8% of trips carry 1.9x the error (M2-S4 §4) — the segment "
        "whose gap M3's geometry did not close, so the segment to watch on the wire",
        QuoteRequest("2019-07-09T17:30:00", 132, 230, 1.0),
    ),
    Hazard(
        "airport-lga",
        "LaGuardia (138), the second airport zone",
        QuoteRequest("2019-07-11T08:05:00", 138, 161, 3.0),
    ),
    Hazard(
        "airport-ewr",
        "Newark (1): out-of-city, the longest ordinary haul the contract admits",
        QuoteRequest("2019-07-12T19:40:00", 1, 161, 1.0),
    ),
    Hazard(
        "no-geometry-both",
        "F-030 and DR-04 condition 1: zone 264 is TLC's 'Unknown', so all nine "
        "geometry features are NaN and has_geometry=0. 264->264 is the largest "
        "single OD 'route' in this data (409,128 trips). This row is the one that "
        "returned HTTP 422 before the wire encoding was fixed",
        QuoteRequest("2019-03-11T00:30:00", 264, 264, 1.0),
    ),
    Hazard(
        "no-geometry-one-sided",
        "half the geometry missing: a real pickup, a 265 ('N/A') dropoff — the "
        "haversine is NaN while the borough and airport flags are still defined",
        QuoteRequest("2019-07-08T12:00:00", 132, 265, 1.0),
    ),
    Hazard(
        "unseen-od-pair",
        "55 -> 148 occurs 6 times in trips_test and NEVER in trips_train (asked "
        "once of the analyst layer: SELECT ... FROM trips_test LEFT JOIN "
        "DISTINCT(trips_train) ... WHERE tr.pu IS NULL ORDER BY n DESC). The floor "
        "backs off on rows like this; the booster does not, which is where 96.9% "
        "of its advantage now lives (M3 §9)",
        QuoteRequest("2019-07-15T13:10:00", 55, 148, 1.0),
    ),
    Hazard(
        "federal-holiday",
        "is_holiday=1. This is M5-S2's spot-check row, kept on purpose: the ONE "
        "number that already exists must still be reproduced by the many",
        QuoteRequest("2019-07-04T09:15:00", 132, 48, 1.0),
    ),
    Hazard(
        "near-holiday",
        "is_near_holiday=1 without is_holiday — the flag pair that must not collapse",
        QuoteRequest("2019-07-03T18:00:00", 236, 141, 1.0),
    ),
    Hazard(
        "midnight-boundary",
        "hour=0 exactly: hour_sin=0.0 and hour_cos=1.0, the cyclical encoding's seam",
        QuoteRequest("2019-07-16T00:00:00", 48, 68, 1.0),
    ),
    Hazard(
        "week-boundary",
        "Monday 00:00: weekpos wraps, dayofweek=0, is_business_day=1",
        QuoteRequest("2019-07-15T00:00:00", 100, 230, 1.0),
    ),
    Hazard(
        "long-haul-boundary",
        "Bronx -> Staten Island: the 100-120 min band where KPI-12 is 0.103% and "
        "the champion's ceiling lives (M2-S4 §5). The tail is where a runtime "
        "difference would show up first",
        QuoteRequest("2019-07-13T11:00:00", 3, 6, 1.0),
    ),
    Hazard(
        "passenger-count-zero",
        "passenger_count=0 is 'not stated' and buckets to 4 — a legal value the "
        "contract admits and the naive reader assumes cannot happen",
        QuoteRequest("2019-07-17T15:45:00", 90, 234, 0.0),
    ),
    Hazard(
        "passenger-count-max",
        "the top of the contract's admitted range, so the bucket edge is exercised",
        QuoteRequest("2019-07-18T21:20:00", 170, 162, 6.0),
    ),
    Hazard(
        "out-of-year-2026",
        "F-019's extension in use: a date outside every month this model ever saw, "
        "inside the derived holiday table. It must parity like any other row — the "
        "refusal boundary is dates the table does NOT cover, and that is a client "
        "refusal (422) which never reaches the wire",
        QuoteRequest("2026-11-26T16:30:00", 161, 237, 1.0),
    ),
)


@dataclass(frozen=True)
class RowResult:
    hazard: Hazard
    offline: float
    online: float

    @property
    def delta(self) -> float:
        return abs(self.offline - self.online)

    def as_record(self) -> dict[str, Any]:
        request = self.hazard.request
        return {
            "hazard": self.hazard.name,
            "why": self.hazard.why,
            "pickup_datetime": request.pickup_datetime,
            "PULocationID": request.pu_location_id,
            "DOLocationID": request.do_location_id,
            "passenger_count": request.passenger_count,
            "offline_minutes": self.offline,
            "online_minutes": self.online,
            "abs_delta_minutes": self.delta,
        }


@dataclass(frozen=True)
class ParityResult:
    rows: list[RowResult]
    tolerance: float
    champion_version: str
    champion_run_id: str
    served_version: str
    served_model: str
    endpoint: str
    feature_names: list[str]
    note: str = ""

    @property
    def max_delta(self) -> float:
        return max((row.delta for row in self.rows), default=0.0)

    @property
    def worst(self) -> RowResult | None:
        """The row with the widest delta — or None when every delta is ZERO.

        `max()` over an all-zero list returns the FIRST row, and printing
        "worst: ordinary-midday" beside 0.000e+00 invents a ranking that does not
        exist. When nothing disagrees there is no worst row, and saying so is the
        difference between a report and a rendering of a data structure.
        """
        if self.max_delta <= 0.0:
            return None
        return max(self.rows, key=lambda row: row.delta)

    @property
    def versions_agree(self) -> bool:
        return str(self.served_version) == str(self.champion_version)

    @property
    def passed(self) -> bool:
        return self.max_delta <= self.tolerance and self.versions_agree

    def as_record(self) -> dict[str, Any]:
        return {
            "story": "M5-S3",
            "measured_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endpoint": self.endpoint,
            "tolerance_minutes": self.tolerance,
            "max_abs_delta_minutes": self.max_delta,
            "worst_hazard": self.worst.hazard.name if self.worst else None,
            "rows": len(self.rows),
            "passed": self.passed,
            "champion": {"version": self.champion_version, "run_id": self.champion_run_id},
            "served": {"model": self.served_model, "version": self.served_version},
            "versions_agree": self.versions_agree,
            "feature_names": self.feature_names,
            "note": self.note,
            "results": [row.as_record() for row in self.rows],
        }


def measure(
    endpoint: Endpoint,
    *,
    hazards: tuple[Hazard, ...] = HAZARDS,
    tolerance: float = TOLERANCE_MINUTES,
    train_config: str = "configs/train.yaml",
    offline_version: str | None = None,
    permute_columns: bool = False,
    note: str = "",
) -> ParityResult:
    """Build one matrix, score it twice, and return every row's delta.

    `offline_version` and `permute_columns` exist for `make parity-redteam` and
    for nothing else: they plant a cause in the TEST while leaving the served
    model untouched — no alias moves, no pod restarts, nothing is redeployed.
    They are parameters rather than a separate copy of this function because a
    red team that runs different code from the test proves something about the
    copy.
    """
    from ..features import quote_time
    from ..training.openmp import ensure_openmp

    # Before anything imports lightgbm on this host (gotcha #37). This re-execs
    # the interpreter, which is why parity is a module and never a `python -c`
    # (F-024: the shim cannot replay a -c source string).
    print(f"[openmp] {ensure_openmp()}")

    from ..training import score as score_mod
    from ..training.run import load_train_config

    train_cfg = load_train_config(train_config)
    features_cfg = train_cfg["features"]
    names = quote_time.feature_names(features_cfg)

    if offline_version:
        print(
            f"[parity] RED TEAM: loading version {offline_version} offline instead of "
            "following the alias — the endpoint is untouched"
        )
    champion = score_mod.load_champion(train_cfg, version_number=offline_version)
    print(
        f"[parity] offline: {champion.uri} -> version {champion.version} "
        f"(run {champion.run_id}, {champion.trees} trees)"
    )
    if champion.feature_names != names:
        raise RuntimeError(
            f"the loaded model eats {champion.feature_names} but the config describes "
            f"{names}. Parity would compare two different feature sets."
        )

    requests = [hazard.request for hazard in hazards]
    matrix = build_matrix(requests, features_cfg)
    print(f"[parity] one matrix: {len(matrix)} rows x {len(names)} features, built once")

    offline = score_mod._as_trained(champion).predict(matrix[names])

    sent_matrix = matrix
    if permute_columns:
        # RED TEAM ARM A: every feature carries its NEIGHBOUR's value.
        #
        # The first version of this arm rotated the ORDER of the inputs in the
        # body and measured a delta of exactly 0.000e+00 — the drill went green
        # under its own tampering, which is the only way a red team can teach
        # something. **This runtime pairs inputs by NAME.** mlserver hands
        # mlflow a named frame and the logged signature reorders it, so the
        # order on the wire is not load-bearing (M5-S3; the client's docstring
        # used to claim the opposite and has been corrected).
        #
        # So the cause is planted where it can actually exist: the names and
        # their dtypes stay exactly right, and the VALUES move one feature to
        # the left. Every input is individually valid — right name, right type,
        # right shape, a number in range — and the endpoint returns a perfectly
        # plausible number of minutes for the wrong trip. That is the skew this
        # whole test exists to detect, and it is the shape a positional runtime
        # would produce for free.
        rotated = {
            name: matrix[names[(index + 1) % len(names)]].to_numpy().astype(matrix[name].dtype)
            for index, name in enumerate(names)
        }
        sent_matrix = pd.DataFrame(rotated, index=matrix.index)[names]
        print(
            "[parity] RED TEAM: every feature is sent under its own name and dtype "
            f"carrying the NEXT feature's values ({names[0]} <- {names[1]})"
        )

    response = infer_frame(sent_matrix, names, names, endpoint)
    online = minutes_of(response)
    served_version = str(response.get("model_version") or "")
    served_model = str(response.get("model_name") or "")
    print(
        f"[parity] online : {endpoint.infer_url} (Host: {endpoint.host}) answered as "
        f"{served_model or '(unnamed)'} version {served_version or '(unversioned)'}"
    )

    rows = [
        RowResult(hazard, float(off), float(on))
        for hazard, off, on in zip(hazards, offline, online, strict=True)
    ]
    return ParityResult(
        rows=rows,
        tolerance=tolerance,
        champion_version=str(champion.version),
        champion_run_id=str(champion.run_id),
        served_version=served_version,
        served_model=served_model,
        endpoint=endpoint.infer_url,
        feature_names=names,
        note=note,
    )


def infer_frame(
    matrix: pd.DataFrame,
    send_order: list[str],
    model_order: list[str],
    endpoint: Endpoint,
) -> dict[str, Any]:
    """POST the matrix under `send_order`. Normally that IS the model's order."""
    from .client import infer_matrix

    if sorted(send_order) != sorted(model_order):
        raise ValueError("the send order must be a permutation of the model's features")
    return infer_matrix(matrix, send_order, endpoint)


def table(result: ParityResult) -> str:
    """One line per row, widest delta last on the eye — the number IS the point."""
    width = max(len(row.hazard.name) for row in result.rows)
    lines = [
        f"{'hazard'.ljust(width)}  {'offline (min)':>14}  {'online (min)':>14}  {'|delta|':>12}",
        f"{'-' * width}  {'-' * 14}  {'-' * 14}  {'-' * 12}",
    ]
    for row in result.rows:
        lines.append(
            f"{row.hazard.name.ljust(width)}  {row.offline:>14.9f}  "
            f"{row.online:>14.9f}  {row.delta:>12.3e}"
        )
    return "\n".join(lines)


def verdict_lines(result: ParityResult) -> list[str]:
    """What is printed instead of the word PASS on its own."""
    lines = []
    if not result.versions_agree:
        lines.append(
            f"[parity] FAIL: the endpoint is serving version {result.served_version!r} "
            f"while the alias resolves to version {result.champion_version!r}. A delta "
            "measured across two different models is not a parity measurement."
        )
    worst = result.worst
    where = f" (worst: {worst.hazard.name})" if worst else " (every row agrees EXACTLY)"
    lines.append(
        f"[parity] max |offline - online| = {result.max_delta:.3e} minutes over "
        f"{len(result.rows)} hazard rows{where}; the bar is {result.tolerance:.1e}"
    )
    if result.max_delta > result.tolerance:
        lines.append(
            "[parity] FAIL: the deployed model does not compute what the registered "
            "one computes. The published KPI-09/KPI-10 describe the local model, so "
            "above this bar every serving claim in this repo is about a different "
            "model from the one on the wire."
        )
    elif result.passed:
        lines.append(
            "[parity] PASS: train/serve skew is MEASURED, not assumed — the deployed "
            f"champion (version {result.served_version}) reproduces the registered one "
            "on every hazard row, including the ones with no geometry at all."
        )
    return lines


def write_record(result: ParityResult, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.as_record(), indent=2, sort_keys=False) + "\n")
    return path


#: Where the record lands. Tracked under M5-S1's regime (F-029): a gate that
#: replays a record must replay one review can see.
DEFAULT_RECORD = Path("automation/runs/m5-parity/parity.json")


def main(argv: list[str] | None = None) -> int:
    """`make parity`. Exit 0 = measured and within the bar, 1 = anything else.

    There is no skip flag and no fast mode (M1's rule, inherited by every gate
    since): the whole run is seconds, and a parity test with a way to not run is
    a parity test that will one day not have run.
    """
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--route", default=DEFAULT_ROUTE)
    parser.add_argument("--name", default="nyc-taxi-eta")
    parser.add_argument("--namespace", default="serving")
    parser.add_argument(
        "--tolerance", type=float, default=TOLERANCE_MINUTES,
        help="the bar in minutes; LOOSENING it is a PO fork, not a flag you reach for",
    )
    parser.add_argument("--record", default=str(DEFAULT_RECORD))
    parser.add_argument("--no-record", action="store_true", help="measure, write nothing")
    parser.add_argument(
        "--permute-columns", action="store_true",
        help="RED TEAM arm A: send every feature under its own name carrying the "
             "NEXT feature's values — a body in which every input is individually valid",
    )
    parser.add_argument(
        "--against-version", default=None,
        help="RED TEAM arm B: load an EXPLICIT registry version offline (e.g. 1) and "
             "compare the live endpoint against it. Addressing a version reads the "
             "registry; moving an alias would mutate it, and a red team never does",
    )
    parser.add_argument("--note", default="")
    args = parser.parse_args(argv)

    endpoint = Endpoint(name=args.name, namespace=args.namespace, route=args.route)
    result = measure(
        endpoint,
        tolerance=args.tolerance,
        offline_version=args.against_version,
        permute_columns=args.permute_columns,
        note=args.note,
    )

    print()
    print(table(result))
    print()
    for line in verdict_lines(result):
        print(line)

    if not args.no_record:
        written = write_record(result, Path(args.record))
        print(f"[parity] record -> {written}")
    return 0 if result.passed else 1


if __name__ == "__main__":  # pragma: no cover — exercised through `make parity`
    raise SystemExit(main())
