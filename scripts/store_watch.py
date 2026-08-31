#!/usr/bin/env python
"""Ask the online store whether it still holds what it was filled with, and push the answer.

M9-S2, R-2's landing. `make store-watch`.

This is the metric SOURCE for A-12 and A-13. It reads two things and pushes
four series; it applies no bar and prints no verdict (the bars live in
`infra/monitoring/alerting_rules.yml`, argued in `docs/slo_serving.md` §9).

  * **`DBSIZE`, off the running server** — via `kubectl exec`, the readback
    idiom `feast_materialize.sh` already uses. Never off the command that wrote
    it.
  * **The canary, through the feature server** — the same HTTP wire the
    transformer uses (`/get-online-features`), over an ephemeral port-forward.
    Four claims, one of them negative; `store_health.CHECKS` argues each.

WHAT IT DOES NOT DO, STATED SO THE CUT IS A DECISION
------------------------------------------------------
**It installs no schedule.** M9 legislates no new Flyte trigger (F-058) and this
story adds no image and no CronJob, so the cadence is whoever runs it: the drill,
`make verify-m9`, an operator. That is `push_serving_version.py`'s landed shape
and it is why both A-12 rules carry a freshness clause — a pushed reading older
than 30 minutes makes them INACTIVE rather than falsely green. The gap is named
in `docs/slo_serving.md` §9 with the three things that bound it, and it is not
papered over here.

**It moves nothing.** No alias is read or written, no feature is materialized,
no pod is touched. Its only side effect is a PUT to the pushgateway, and
`--no-push` removes even that.

WHY THE PORT-FORWARDS ARE 6568 AND 9100
-----------------------------------------
Not 6566/9091 (the Services' own ports — a probe that collides with one can end
up talking to something that is not under test) and not 6567/9096/9097/9098/9099,
which belong to `feast_server_parity.py` and the two drift drills. A reader that
steals a running drill's port fails for its own reasons, which is #55 and it has
cost this program a session. Both forwards are ephemeral and torn down here;
neither is a route, because kind publishes host ports at cluster-CREATE only
(M9 law 1).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from _lib import ports  # noqa: E402
from _lib.k8s import kubectl_run as _kubectl  # noqa: E402
from _lib.k8s import start_forward, stop_forward  # noqa: E402

from taxi_mlops.monitoring.pushgateway import (  # noqa: E402
    DEFAULT_IN_CLUSTER_URL,
    Metric,
    push_metrics,
)
from taxi_mlops.monitoring.store_health import (  # noqa: E402
    CANARY_DATE,
    CANARY_METRIC,
    CANARY_NONPLACE,
    CANARY_ZONE,
    CHECKS,
    FRESHNESS_METRIC,
    KEYS_EXPECTED_METRIC,
    KEYS_METRIC,
    PUSH_JOB,
    evaluate_canary,
    expected_keys,
)

NAMESPACE = "feast"
FORWARD_PORT = ports.port("FEAST_SERVER_WATCH")
GATEWAY_PORT = ports.port("PUSHGATEWAY_STORE_WATCH")
STORE_LABEL = "feast-online"

#: The feature refs the canary asks for — the same two the transformer requests
#: (`serving.feature_store.ZONE_FEATURES`) and the same two calendar flags.
#: Spelled here rather than imported from the serving package on purpose: this
#: reader must keep working if the transformer is redeployed or removed, and the
#: strings it sends are what the STORE answers to, not what a client wants.
ZONE_REFS = ["zone_static:centroid_lat", "zone_static:centroid_lon"]
DAY_REFS = ["calendar_day_flags:is_holiday", "calendar_day_flags:is_near_holiday"]


# `_kubectl`, `_forward` and `_wait_http` moved to `_lib.k8s` at CU-S4. The
# forward now WAITS for its socket instead of returning a process that may not
# be listening yet, so the "never came up" branch below is a real answer rather
# than a guess made after a fixed sleep.


def read_dbsize() -> tuple[int | None, str]:
    """DBSIZE off the running server. Returns (value, how-it-was-read)."""
    pod = _kubectl(
        "-n", NAMESPACE, "get", "pod", "-l", "app=redis",
        "-o", "jsonpath={.items[0].metadata.name}",
    )
    if pod.returncode != 0 or not pod.stdout.strip():
        return None, f"no redis pod answered ({pod.stderr.strip() or 'no pod found'})"
    out = _kubectl("-n", NAMESPACE, "exec", pod.stdout.strip(), "--", "redis-cli", "DBSIZE")
    if out.returncode != 0:
        return None, f"redis-cli DBSIZE failed on {pod.stdout.strip()}: {out.stderr.strip()}"
    try:
        return int(out.stdout.strip()), f"redis-cli DBSIZE on {pod.stdout.strip()}"
    except ValueError:
        return None, f"redis-cli DBSIZE answered {out.stdout.strip()!r}"


def _post(url: str, body: dict[str, Any], timeout: float = 15.0) -> dict[str, Any]:
    request = urllib.request.Request(  # noqa: S310 — a fixed localhost forward
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read())


def online(url: str, features: list[str], entities: dict[str, list[Any]]) -> dict[str, list[Any]]:
    """One `/get-online-features`, re-keyed BY NAME.

    The by-name rebuild is not tidiness: the server does not preserve the
    request's column order (M8-S4 leg 2 measured it), so a client zipping by
    position reads values under each other's names.
    """
    payload = _post(f"{url}/get-online-features", {"features": features, "entities": entities})
    names = payload["metadata"]["feature_names"]
    results = payload["results"]
    if len(names) != len(results):
        raise RuntimeError(
            f"the server named {len(names)} columns and returned {len(results)} blocks"
        )
    return {name: block["values"] for name, block in zip(names, results, strict=True)}


def read_canary(url: str) -> tuple[dict[str, Any], bool, str]:
    """Ask the store the four questions. Returns (observations, failed, how)."""
    try:
        zones = online(url, ZONE_REFS, {"zone_id": [CANARY_ZONE, CANARY_NONPLACE]})
        days = online(url, DAY_REFS, {"date_key": [CANARY_DATE]})
    except Exception as error:  # noqa: BLE001 — every failure here is one class
        return {}, True, f"the feature server did not answer: {error!r}"
    return (
        {
            "zone_centroid": (zones["centroid_lat"][0], zones["centroid_lon"][0]),
            "nonplace_centroid": (zones["centroid_lat"][1], zones["centroid_lon"][1]),
            "calendar_flags": (days["is_holiday"][0], days["is_near_holiday"][0]),
        },
        False,
        f"{url}/get-online-features",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pushgateway",
        default=None,
        help=(
            "gateway URL. Omitted on the host means an EPHEMERAL port-forward; an "
            f"in-cluster caller passes {DEFAULT_IN_CLUSTER_URL}"
        ),
    )
    parser.add_argument("--feature-server", default=None, help="an already-running server")
    parser.add_argument("--port", type=int, default=FORWARD_PORT)
    parser.add_argument("--gateway-port", type=int, default=GATEWAY_PORT)
    parser.add_argument("--no-push", action="store_true", help="read and print; push nothing")
    parser.add_argument("--json", dest="as_json", action="store_true", help="payload to stdout")
    args = parser.parse_args(argv)

    dbsize, dbsize_how = read_dbsize()
    derived = expected_keys(REPO_ROOT)

    forward = None
    url = args.feature_server
    if url is None:
        forward = start_forward("svc/feast-server", NAMESPACE, args.port, 6566)
        url = f"http://127.0.0.1:{args.port}"
    try:
        observations, lookup_failed, canary_how = read_canary(url)
    finally:
        if forward is not None:
            stop_forward(forward)

    canary = evaluate_canary(
        dbsize=dbsize,
        zone_centroid=observations.get("zone_centroid"),
        nonplace_centroid=observations.get("nonplace_centroid"),
        calendar_flags=observations.get("calendar_flags"),
        lookup_failed=lookup_failed,
    )

    print(f"[store-watch] keys        : {dbsize}  ({dbsize_how})")
    print(f"[store-watch] keys expected: {derived['total']}  "
          f"(count(distinct entity keys) over data/feast/*.parquet)")
    print(f"[store-watch] canary       : {canary_how}")
    for check in CHECKS:
        print(f"[store-watch]   {canary[check.name]}  {check.name:18s} {check.claim}")

    metrics = [
        Metric(
            name=CANARY_METRIC,
            value=float(canary[check.name]),
            help="1 when the online store satisfied this canary claim, 0 when it did not.",
            labels={"store": STORE_LABEL, "check": check.name},
        )
        for check in CHECKS
    ]
    metrics.append(
        Metric(
            name=KEYS_EXPECTED_METRIC,
            value=float(derived["total"]),
            help=(
                "Keys the published sources define: count(distinct entity keys) per view. "
                "The right-hand side of A-12b, so the rule needs no threshold."
            ),
            labels={"store": STORE_LABEL},
        )
    )
    if dbsize is not None:
        metrics.append(
            Metric(
                name=KEYS_METRIC,
                value=float(dbsize),
                help="Keys the online store actually holds, read off the running server.",
                labels={"store": STORE_LABEL},
            )
        )
    else:
        # Deliberately omitted rather than pushed as a zero. A zero here would be
        # a claim about the STORE made from a failure to reach it; the failure
        # itself is reported by the `store_reachable` canary check, which is
        # firing at the same moment. A-12b goes unevaluable and A-12a carries it.
        print("[store-watch] DBSIZE unreadable — the keys series is OMITTED, not zeroed; "
              "the store_reachable check is what reports it")
    metrics.append(
        Metric(
            name=FRESHNESS_METRIC,
            value=float(time.time()),
            help=(
                "Unix time of this reader's last run. Both A-12 rules require it: this "
                "reader has no scheduler, so a stale reading must be INACTIVE, not green."
            ),
            labels={"store": STORE_LABEL},
        )
    )

    payload = {
        "recorded_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "keys": dbsize,
        "keys_how": dbsize_how,
        "keys_expected": derived["total"],
        "keys_expected_per_view": derived["per_view"],
        "canary": canary,
        "canary_how": canary_how,
        "observations": {k: list(v) for k, v in observations.items()},
        "issues_no_verdict": (
            "the bars live in infra/monitoring/alerting_rules.yml, argued in "
            "docs/slo_serving.md §9"
        ),
    }
    if args.as_json:
        print(json.dumps(payload, indent=2))

    if args.no_push:
        print("[store-watch] --no-push: nothing was pushed.")
        return 0

    gateway_forward = None
    gateway_url = args.pushgateway
    if gateway_url is None:
        try:
            gateway_forward = start_forward(
                "svc/prometheus-prometheus-pushgateway",
                "monitoring",
                args.gateway_port,
                9091,
            )
        except RuntimeError:
            print(
                "[store-watch] FAIL: the pushgateway forward never came up. The gateway has no "
                "hostPort (M9 law 1); pass --pushgateway explicitly from inside the cluster.",
                file=sys.stderr,
            )
            return 1
        gateway_url = f"http://127.0.0.1:{args.gateway_port}"
    try:
        target = push_metrics(
            metrics, url=gateway_url, job=PUSH_JOB, grouping={"store": STORE_LABEL}
        )
    finally:
        if gateway_forward is not None:
            stop_forward(gateway_forward)
    print(f"[store-watch] pushed {len(metrics)} series -> {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
