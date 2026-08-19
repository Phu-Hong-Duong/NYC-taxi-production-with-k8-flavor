"""`python -m taxi_mlops.serving` — one quote, through the wire, typed.

The smoke client `make serve`'s last step runs and `make quote` exposes. It is
deliberately not a load tool (M5-S4 owns that) and not the parity test (M5-S3
owns that, and a spot check must never be allowed to masquerade as it — the
handoff says so out loud).

Exit codes, because a pipeline reads them and prose is not a signal:
  0  a quote was returned
  2  the request was REFUSED by this deployment (F-019's typed boundary — an
     uncovered date, the caller's fault, fixable by `make holidays`)
  1  anything else
The refusal gets its own code for the same reason `make train`'s "no verdict"
does: "I will not answer that" and "I could not answer" are different facts and a
caller that cannot tell them apart will retry the one that never succeeds.
"""

from __future__ import annotations

import argparse
import sys

from .client import DEFAULT_ROUTE, Endpoint, QuoteRefused, QuoteRequest, predict, served_version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--route", default=DEFAULT_ROUTE, help="the declared route")
    parser.add_argument("--name", default="nyc-taxi-eta", help="the InferenceService name")
    parser.add_argument("--namespace", default="serving")
    parser.add_argument(
        "--at",
        default="2019-07-04T09:15:00",
        help="the pickup timestamp; the default is inside the champion's own year",
    )
    parser.add_argument("--pu", type=int, default=132, help="PULocationID (132 = JFK)")
    parser.add_argument("--do", dest="do", type=int, default=48, help="DOLocationID")
    parser.add_argument("--passengers", type=float, default=1.0)
    args = parser.parse_args(argv)

    endpoint = Endpoint(name=args.name, namespace=args.namespace, route=args.route)
    request = QuoteRequest(
        pickup_datetime=args.at,
        pu_location_id=args.pu,
        do_location_id=args.do,
        passenger_count=args.passengers,
    )

    try:
        minutes = predict([request], endpoint)
    except QuoteRefused as refusal:
        print(f"[quote] REFUSED ({refusal.http_status}): {refusal}", file=sys.stderr)
        return 2

    metadata = served_version(endpoint)
    # What the SERVER says it is serving, asked rather than remembered. mlserver
    # reports the model version it loaded; KServe reports the name it routes.
    print(
        f"[quote] served by {metadata.get('name', args.name)} "
        f"version {metadata.get('versions') or metadata.get('version') or '(unversioned)'} "
        f"via {endpoint.infer_url} (Host: {endpoint.host})"
    )
    print(
        f"[quote] {args.at}  zone {args.pu} -> {args.do}, "
        f"{args.passengers:g} passenger(s)  ->  {minutes[0]:.4f} minutes"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised through `make quote`
    raise SystemExit(main())
