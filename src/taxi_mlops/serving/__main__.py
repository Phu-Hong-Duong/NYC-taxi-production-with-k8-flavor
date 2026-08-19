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

from ..features import sets
from .client import DEFAULT_ROUTE, Endpoint, QuoteRefused, QuoteRequest, infer, minutes_of


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--route", default=DEFAULT_ROUTE, help="the declared route")
    parser.add_argument("--name", default="nyc-taxi-eta", help="the InferenceService name")
    parser.add_argument("--namespace", default="serving")
    # M6-S3. A second model is on the wire (the v1 shadow) and it eats a DIFFERENT
    # matrix — 5 columns against the champion's 24. Without this the only way to
    # quote it would be a second client, which is the one thing this module
    # exists to prevent: features are built by `taxi_mlops.features` for every
    # target or train/serve skew is a matter of luck.
    #
    # The default is deliberately None and not "v2": absent this flag the config
    # decides, so a rollback that moves `features.version` moves this too. A
    # caller that names a set is naming it for a NON-champion target and should
    # derive it from that target's `feature_set` registry tag rather than typing
    # it — `scripts/deploy_shadow.sh` does exactly that.
    parser.add_argument(
        "--features-version",
        default=None,
        help="feature set to build with (default: configs/train.yaml's). The shadow's "
        "comes from its registry version's feature_set tag, never from a constant.",
    )
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

    features_cfg = sets.resolve_set(args.features_version) if args.features_version else None

    try:
        response = infer([request], endpoint, features_cfg=features_cfg)
    except QuoteRefused as refusal:
        print(f"[quote] REFUSED ({refusal.http_status}): {refusal}", file=sys.stderr)
        return 2

    minutes = minutes_of(response)
    # The version is read off THIS response, not off a metadata call: it is the
    # server's own stamp on the very answer being printed, so it cannot describe
    # a different moment than the number beside it.
    print(
        f"[quote] served by {response.get('model_name', args.name)} "
        f"version {response.get('model_version') or '(unversioned)'} "
        f"via {endpoint.infer_url} (Host: {endpoint.host})"
    )
    print(
        f"[quote] {args.at}  zone {args.pu} -> {args.do}, "
        f"{args.passengers:g} passenger(s)  ->  {minutes[0]:.4f} minutes"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised through `make quote`
    raise SystemExit(main())
