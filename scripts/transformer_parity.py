"""THE parity through the moved boundary: a RAW request in a pod vs a matrix built on the host.

M8-S4 leg 3. Four seams in this program have now been measured, each against the
same 16 declared hazards: the WIRE (M5-S3, host-built matrix vs the endpoint), the
OFFLINE store (M8-S3), the ONLINE store (leg 1), the HTTP door (leg 2). This is
the fifth and the one the others were for — **the whole boundary at once**:

  A. the champion, as it serves today: this process builds the 24 features from
     the committed CSVs and POSTs the MATRIX to `nyc-taxi-eta`;
  B. the transformer: this process POSTs the four RAW fields to
     `nyc-taxi-eta-transformer`, and a pod derives the same 24 features — with
     the centroids and the calendar flags read out of the online feature store —
     and forwards them to a predictor holding the same champion bytes.

**THE BAR IS EXACT AND IT WAS ARGUED FIRST** — `docs/transformer_m8.md` §3,
committed before this script produced any record (M8 law 4's ordering, checkable
from git rather than asserted here).

**WHY THIS IS NOT A RE-RUN OF LEG 2'S MEASUREMENT.** Leg 2 measured the feature
server's ANSWERS against the champion's own lookup: six columns of reference
data. This measures the QUOTE — every intermediate between a rider's question and
a number, including nine geometry features derived from those coordinates, the
float32 cast, the V2 encoding, a second mlserver process, and LightGBM. A lossless
projection of the inputs does not by itself make the outputs equal; that is what a
tolerance argument is for, and §3 makes it.

**IT IS A READER.** It resolves the alias only to READ which version is serving,
deploys nothing, materializes nothing and moves no pointer — pinned by
`tests/unit/test_transformer_parity.py` the way M5-S3's reader property is.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from taxi_mlops.serving.client import (  # noqa: E402
    DEFAULT_ROUTE,
    Endpoint,
    build_matrix,
    infer_matrix,
    minutes_of,
)
from taxi_mlops.serving.parity import HAZARDS  # noqa: E402
from taxi_mlops.serving.transformer import encode_raw  # noqa: E402
from taxi_mlops.training.run import load_train_config  # noqa: E402

#: Not a tolerance — an assertion of identity. docs/transformer_m8.md §3.
TOLERANCE = 0.0

CHAMPION = "nyc-taxi-eta"
TRANSFORMER = "nyc-taxi-eta-transformer"
NAMESPACE = "serving"

RECORD = REPO / "automation" / "runs" / "m8-transformer" / "transformer-parity.json"
TABLE = REPO / "docs" / "transformer_parity_table.md"


def _post_raw(endpoint: Endpoint, requests: list, timeout: float = 60.0) -> tuple[dict, dict]:
    """POST the RAW request body and hand back the response AND its headers.

    The headers matter: `X-Taxi-Lookups` is how this reader proves the pod
    consulted the store rather than falling back to its own committed CSVs — a
    fallback would produce an identical number and a meaningless 0.000e+00.
    """
    import urllib.request

    body = json.dumps(encode_raw(requests), allow_nan=False).encode()
    request = urllib.request.Request(  # noqa: S310 — a fixed http:// route
        endpoint.infer_url,
        data=body,
        headers={"Content-Type": "application/json", "Host": endpoint.host},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read()), dict(response.headers)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route", default=DEFAULT_ROUTE)
    parser.add_argument("--tolerance", type=float, default=TOLERANCE)
    parser.add_argument("--no-write", action="store_true", help="print, record nothing")
    args = parser.parse_args()

    champion = Endpoint(name=CHAMPION, namespace=NAMESPACE, route=args.route)
    transformer = Endpoint(name=TRANSFORMER, namespace=NAMESPACE, route=args.route)
    cfg = load_train_config()["features"]
    requests = [h.request for h in HAZARDS]

    print(f"[transformer-parity] {len(requests)} declared hazards (parity.HAZARDS, imported)")
    print(f"[transformer-parity] A  matrix built HERE  -> {champion.infer_url}")
    print(f"[transformer-parity] B  raw request        -> {transformer.infer_url}")
    print("[transformer-parity] bar: EXACT (docs/transformer_m8.md §3, argued before this ran)")

    # ---- A: the champion, exactly as every client has addressed it since M5-S2.
    names = list(build_matrix(requests, cfg).columns)
    matrix = build_matrix(requests, cfg)
    response_a = infer_matrix(matrix, names, champion)
    minutes_a = minutes_of(response_a)

    # ---- B: the transformer, addressed the way a rider's question arrives.
    response_b, headers = _post_raw(transformer, requests)
    minutes_b = minutes_of(response_b)

    lookups = headers.get("X-Taxi-Lookups", "")
    version_a = str(response_a.get("model_version"))
    version_b = str(response_b.get("model_version"))

    deltas = np.abs(minutes_a - minutes_b)
    worst = float(deltas.max())
    breaches = [i for i, d in enumerate(deltas) if float(d) > args.tolerance]

    print()
    width = max(len(h.name) for h in HAZARDS)
    for i, hazard in enumerate(HAZARDS):
        status = "ok  " if float(deltas[i]) <= args.tolerance else "FAIL"
        print(
            f"[transformer-parity] {status}{hazard.name:<{width}}  "
            f"champion={minutes_a[i]:>9.6f}  transformer={minutes_b[i]:>9.6f}  "
            f"|d|={float(deltas[i]):.3e}"
        )

    checks: list[tuple[bool, str]] = [
        (
            not breaches,
            f"max |champion - transformer| = {worst:.3e} minutes across {len(requests)} "
            f"declared hazards, bar EXACT",
        ),
        (
            version_a == version_b and version_a not in ("None", ""),
            f"both boundaries served the SAME registry version: champion={version_a!r}, "
            f"transformer={version_b!r} — read off the two ANSWERS, not off a metadata call",
        ),
        (
            "centroids=feature-store" in lookups and "calendar=feature-store" in lookups,
            f"the pod really consulted the store: X-Taxi-Lookups={lookups!r} — without "
            "this, a silent fallback to the committed CSVs would produce the same zero",
        ),
        (
            "borough_dictionary=committed-table" in lookups
            and "airport_constant=committed-code" in lookups,
            "and F-059's two refused groups did not cross: the borough dictionary and "
            "the airport constant are still the committed artifacts",
        ),
    ]

    print()
    for ok, line in checks:
        print(f"[transformer-parity] {'ok  ' if ok else 'FAIL'}{line}")

    failures = sum(1 for ok, _ in checks if not ok)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    if not args.no_write:
        RECORD.parent.mkdir(parents=True, exist_ok=True)
        RECORD.write_text(
            json.dumps(
                {
                    "bar": "EXACT",
                    "bar_argued_in": "docs/transformer_m8.md §3",
                    "measured_at": stamp,
                    "route": args.route,
                    "champion": {"endpoint": champion.infer_url, "host": champion.host},
                    "transformer": {"endpoint": transformer.infer_url, "host": transformer.host},
                    "hazards": len(requests),
                    "feature_set": cfg.get("version"),
                    "features": len(names),
                    "lookup_sources": lookups,
                    "model_version": {"champion": version_a, "transformer": version_b},
                    "max_abs_delta_minutes": worst,
                    "breaches": [HAZARDS[i].name for i in breaches],
                    "rows": [
                        {
                            "hazard": h.name,
                            "at": h.request.pickup_datetime,
                            "pu": h.request.pu_location_id,
                            "do": h.request.do_location_id,
                            "champion_minutes": float(minutes_a[i]),
                            "transformer_minutes": float(minutes_b[i]),
                            "abs_delta": float(deltas[i]),
                        }
                        for i, h in enumerate(HAZARDS)
                    ],
                    "checks": [{"ok": ok, "claim": line} for ok, line in checks],
                    "failures": failures,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        TABLE.write_text(_table(stamp, minutes_a, minutes_b, deltas, worst, lookups, version_a))
        print(f"[transformer-parity] recorded {RECORD.relative_to(REPO)}")
        print(f"[transformer-parity] wrote    {TABLE.relative_to(REPO)}")

    print()
    if failures:
        print(f"[transformer-parity] RED — {failures} check(s) failed. A nonzero delta is a")
        print("[transformer-parity]       FINDING (which hop rounded?), never a bar to widen.")
        return 1
    print("[transformer-parity] GREEN — the boundary moved and the number did not.")
    return 0


def _table(
    stamp: str,
    a: np.ndarray,
    b: np.ndarray,
    deltas: np.ndarray,
    worst: float,
    lookups: str,
    version: str,
) -> str:
    lines = [
        "# The transformer parity table — a raw request in a pod vs a matrix built on the host",
        "",
        f"Generated by `make transformer-parity` at {stamp}. Bar: **EXACT**, argued in",
        "`docs/transformer_m8.md` §3 and committed before this table existed.",
        "",
        f"Champion registry version **{version}** on both sides, read off the two answers.",
        f"Reference data on the transformer's side: `{lookups}`.",
        "",
        "| # | hazard | champion (min) | transformer (min) | \\|delta\\| |",
        "|---|---|---:|---:|---:|",
    ]
    for i, hazard in enumerate(HAZARDS):
        lines.append(
            f"| {i + 1} | {hazard.name} | {a[i]:.6f} | {b[i]:.6f} | {float(deltas[i]):.3e} |"
        )
    lines += [
        "",
        f"**max |delta| = {worst:.3e} minutes over {len(HAZARDS)} rows.**",
        "",
        "The rows are `taxi_mlops.serving.parity.HAZARDS`, imported and never retyped, so",
        "the wire seam (`make parity`), the offline seam (M8-S3), the online seam (leg 1),",
        "the HTTP seam (leg 2) and this one are all measured against ONE declared row set.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
