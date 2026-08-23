"""p95 at the NEW boundary — the same shape, the same loop, a different payload.

M8-S4 leg 3. M5-S4 measured the champion at 4 req/s for 60 s at concurrency 8,
open loop, hazard mix, and `load.py`'s own docstring recorded what that number
excluded:

> They do NOT include `quote_time.build_features`, which in M5 runs in the
> caller's process (~30 ms cold for one row […]) and which M7 moves into a KServe
> transformer — at which point it lands INSIDE this measurement and the number
> will move. Saying so now means the M7 delta reads as a boundary moving rather
> than as a regression.

This is the run that number was written for. The shape is M5-S4's EXACTLY — same
rate, window, concurrency and mix — because the only useful thing to do with this
p95 is put it beside the old one, and two percentiles measured at different
shapes are not comparable (that is the whole first paragraph of `load.py`).

**What is now inside the number that was not before:** decoding four raw inputs,
two HTTP calls to the quarantined feature server, building the 24-column matrix,
encoding a V2 body, and a second in-cluster HTTP hop to the predictor. So a
*larger* p95 is the expected reading and is not a regression — it is a boundary
that moved, and the size of the move is the finding.

**It runs BOTH ARMS, back to back, in one invocation.** The champion's own p95 is
re-measured in the same minutes on the same laptop rather than quoted from a
record made four days ago on a machine that has since rebooted — because the
delta is what is being reported, and a delta between two runs separated by a host
restart is partly a measurement of the host. M5-S4's record stays the number of
record for the champion; this run's champion arm is the CONTROL.

A READER: it POSTs and it times. It deploys nothing, moves no alias and sets no
threshold — the bar for serving latency lives in `docs/slo_serving.md` and
nowhere else (M5-S4's precedent, and M7 law 4's).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from taxi_mlops.serving.client import DEFAULT_ROUTE, Endpoint  # noqa: E402
from taxi_mlops.serving.load import LoadResult, run_load, summary_lines  # noqa: E402
from taxi_mlops.serving.parity import HAZARDS  # noqa: E402
from taxi_mlops.serving.transformer import encode_raw  # noqa: E402

RECORD = REPO / "automation" / "runs" / "m8-transformer" / "transformer-load.json"
NAMESPACE = "serving"

#: M5-S4's headline shape, and it is not a knob here. The ramp that CHOSE 4 req/s
#: measured this container's ceiling at ~6 req/s (96% of the CPU limit) and
#: gotcha #74 is why a rate at the ceiling measures the quota rather than the
#: service. Re-deriving the rate would produce a number that is not comparable
#: with the one this run exists to be compared against.
SHAPE = {"rate": 4.0, "seconds": 60.0, "concurrency": 8, "mix": "hazards"}


def raw_bodies() -> list[bytes]:
    """One pre-encoded RAW body per declared hazard — the same mix, one row each."""
    return [
        json.dumps(encode_raw([hazard.request]), allow_nan=False).encode() for hazard in HAZARDS
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route", default=DEFAULT_ROUTE)
    parser.add_argument("--seconds", type=float, default=SHAPE["seconds"])
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    champion = Endpoint(name="nyc-taxi-eta", namespace=NAMESPACE, route=args.route)
    transformer = Endpoint(
        name="nyc-taxi-eta-transformer", namespace=NAMESPACE, route=args.route
    )

    print(
        f"[transformer-load] shape: {SHAPE['rate']:g} req/s for {args.seconds:g}s at "
        f"concurrency {SHAPE['concurrency']}, {SHAPE['mix']} mix, open loop "
        "(M5-S4's, unchanged — so the two arms are comparable)"
    )

    runs: dict[str, LoadResult] = {}
    runs["champion"] = run_load(
        champion,
        rate=SHAPE["rate"],
        seconds=args.seconds,
        concurrency=SHAPE["concurrency"],
        mix=SHAPE["mix"],
        label="champion (matrix built in the client) — the CONTROL, measured now",
        note=(
            "The M5-S4 record stays the champion's number of record. This arm exists "
            "so the delta is not partly a measurement of a host that has rebooted "
            "since."
        ),
    )
    print()
    for line in summary_lines(runs["champion"]):
        print(line)

    runs["transformer"] = run_load(
        transformer,
        rate=SHAPE["rate"],
        seconds=args.seconds,
        concurrency=SHAPE["concurrency"],
        mix=SHAPE["mix"],
        label="transformer (features built in the pod, lookups from the store)",
        note=(
            "Inside this number and not the champion's: raw decode, two feature-server "
            "calls, build_features over 24 columns, the V2 encode, and a second "
            "in-cluster hop to the predictor."
        ),
        bodies=raw_bodies(),
    )
    print()
    for line in summary_lines(runs["transformer"]):
        print(line)

    a = runs["champion"].percentiles("latency_ms")
    b = runs["transformer"].percentiles("latency_ms")
    print()
    print("[transformer-load] the boundary, priced (latency_ms, scheduled -> response):")
    for key in ("p50", "p95", "p99", "max"):
        print(
            f"[transformer-load]   {key:>4}  champion {a[key]:>8.1f} ms   "
            f"transformer {b[key]:>8.1f} ms   delta {b[key] - a[key]:>+8.1f} ms"
        )
    print(
        f"[transformer-load] versions: champion {runs['champion'].served_versions} · "
        f"transformer {runs['transformer'].served_versions} — read off the timed responses"
    )

    healthy = all(r.error_rate == 0.0 for r in runs.values())
    print(
        f"[transformer-load] errors: champion {len(runs['champion'].errors)} · "
        f"transformer {len(runs['transformer'].errors)}"
    )
    if not healthy:
        for name, result in runs.items():
            if result.errors:
                print(f"[transformer-load]   {name}: {result.error_window()['classes']}")

    if not args.no_write:
        RECORD.parent.mkdir(parents=True, exist_ok=True)
        RECORD.write_text(
            json.dumps(
                {
                    "story": "M8-S4 leg 3",
                    "shape": {**SHAPE, "seconds": args.seconds},
                    "shape_source": "M5-S4's headline, unchanged so the arms compare",
                    "arms": {name: result.as_record() for name, result in runs.items()},
                    "delta_latency_ms": {
                        key: round(b[key] - a[key], 3) for key in ("p50", "p95", "p99", "max")
                    },
                    "what_moved_into_the_number": [
                        "decode of the four raw inputs",
                        "two HTTP calls to the quarantined feature server",
                        "quote_time.build_features over 24 columns",
                        "the V2 encode of the matrix",
                        "a second in-cluster HTTP hop to the predictor",
                    ],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        print(f"[transformer-load] recorded {RECORD.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
