#!/usr/bin/env python3
"""Print the 90/10 split as Prometheus itself renders it, minute by minute (M6-S4).

The §9/M6 leg says the split must be OBSERVED from the ingress's per-backend
counters, and `automation/runs/m6-canary/release_drill.json` records that as two
edge reads differenced. This is the same fact drawn as a series, which is what a
human looks at in Grafana and what `docs/release_rehearsal_m6.md` pastes — the
board and the record must not be two different claims.

It is a READER: one range query, no mutation, no deploy. `--minutes` bounds how
far back it looks, because Prometheus's retention here is short and a window that
outruns it prints an honest nothing rather than a guess.

Usage: uv run python scripts/canary_split_paste.py [--minutes 90]
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request

PROM = "http://localhost:8081"
PROM_HOST = "prometheus.local"
QUERY = (
    "sum by (canary) (increase("
    'nginx_ingress_controller_requests{namespace="serving",ingress="nyc-taxi-eta"}'
    "[1m]))"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--minutes", type=int, default=90)
    args = parser.parse_args()

    now = int(time.time())
    url = f"{PROM}/api/v1/query_range?" + urllib.parse.urlencode(
        {"query": QUERY, "start": now - args.minutes * 60, "end": now, "step": "60"}
    )
    request = urllib.request.Request(url, headers={"Host": PROM_HOST})  # noqa: S310
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        payload = json.loads(response.read())

    series = {
        s["metric"].get("canary") or "main": {int(t): float(v) for t, v in s["values"]}
        for s in payload["data"]["result"]
    }
    canary_key = next((k for k in series if k != "main"), None)
    stamps = sorted(set().union(*(s.keys() for s in series.values()))) if series else []

    print(f"{'minute (UTC)':<22}{'champion':>10}{'canary':>10}{'canary %':>10}")
    for stamp in stamps:
        main = series.get("main", {}).get(stamp, 0.0)
        canary = series.get(canary_key, {}).get(stamp, 0.0) if canary_key else 0.0
        # The main-backend series is the TOTAL for the ingress, canary included,
        # because ingress-nginx counts every request under the same ingress label
        # and only ADDS the canary label to the ones it diverted.
        champion = max(main - canary, 0.0)
        total = champion + canary
        if total < 0.5:
            continue
        when = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stamp))
        print(f"{when:<22}{champion:>10.0f}{canary:>10.0f}{100.0 * canary / total:>9.1f}%")
    if canary_key:
        print(f"\ncanary backend: {canary_key}")
    else:
        print("\nno canary-labelled series in this window — no split was live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
