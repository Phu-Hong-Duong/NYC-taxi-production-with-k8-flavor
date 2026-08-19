"""The load client: a STATED rate, for a STATED window, at a STATED concurrency.

M5-S4. An unqualified latency is not a measurement. "p95 is 180 ms" is a fact
about a load shape as much as about a system, and quoting it without the shape
is how a capacity number outlives the conditions that produced it. So every
record this module writes carries the rate, the window, the concurrency, the
request mix and the ACHIEVED rate beside the percentiles, and the summary line
refuses to print a percentile without them.

--------------------------------------------------------------------------
OPEN LOOP, AND WHY IT IS NOT THE EASY ONE
--------------------------------------------------------------------------
The cheap way to load a service is a closed loop: N threads, each firing the
next request the moment the last one returns. It is three lines shorter and it
measures the wrong thing. In a closed loop the arrival rate is a CONSEQUENCE of
the latency — when the server slows down, the client politely sends less — so
the queueing that a real arrival stream would cause never happens, and the p95
you get is the service time of an unloaded server dressed up as a load test.
This is coordinated omission, and it flatters.

So arrivals here are SCHEDULED: request *k* is due at `t0 + k/rate`, whether or
not anything is free to send it. Two numbers come out of that and both are
reported:

- **service_ms** = sent -> response. What the server took.
- **latency_ms** = SCHEDULED -> response. What a caller who wanted a quote at
  that instant actually waited, including the time its request spent waiting for
  a free connection.

While the client keeps up the two are the same. When they diverge, the client
(or the server) is the bottleneck and the stated rate was not achieved — which
is why `achieved_rate_per_second` is in the record next to the target. A p95
quoted from `service_ms` alone during a run that fell behind is the same lie the
closed loop tells, one layer down.

--------------------------------------------------------------------------
WHAT IS AND IS NOT IN THE NUMBER
--------------------------------------------------------------------------
The feature matrix is built ONCE, before the clock starts, and every request
re-sends rows out of it. So these percentiles are the WIRE and the SERVER:
JSON encode -> ingress -> mlserver -> MLflow -> LightGBM -> back. They do NOT
include `quote_time.build_features`, which in M5 runs in the caller's process
(~30 ms cold for one row, measured and reported separately by the drill as
`feature_build_ms`) and which M7 moves into a KServe transformer — at which
point it lands INSIDE this measurement and the number will move. Saying so now
means the M7 delta reads as a boundary moving rather than as a regression.

The mix is `parity.HAZARDS` by default, cycled: airports, no-geometry zones,
the unseen OD pair, the long-haul tail, the clock seams. A load test that sends
one ordinary Midtown hop 600 times measures one path through the trees and the
identical serialisation buffer every time; the hazard set is already declared,
already committed, and spans the honest shapes (M5-S3). `--mix ordinary`
restricts to the single common row when the question really is "one row, many
times".

This module is a READER of the endpoint: it POSTs and it times. It resolves no
alias, loads no model, deploys nothing and writes nothing but its own record —
pinned by `tests/unit/test_load.py` the way parity's reader property is.
"""

from __future__ import annotations

import json
import math
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .client import DEFAULT_ROUTE, Endpoint, build_matrix, v2_payload
from .parity import HAZARDS

#: Where load records land. Tracked under M5-S1's regime (F-029): the M5 gate
#: replays these, and a gate must replay a record review can see.
DEFAULT_RECORD_DIR = Path("automation/runs/m5-load")


@dataclass(frozen=True)
class Attempt:
    """One request's whole life, in monotonic seconds relative to the start."""

    index: int
    scheduled: float
    sent: float
    done: float
    ok: bool
    status: int | None = None
    error: str | None = None
    model_version: str | None = None

    @property
    def service_ms(self) -> float:
        return (self.done - self.sent) * 1000.0

    @property
    def latency_ms(self) -> float:
        return (self.done - self.scheduled) * 1000.0

    @property
    def queue_ms(self) -> float:
        return (self.sent - self.scheduled) * 1000.0


def percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile — no interpolation, so every number is OBSERVED.

    An interpolated p99 over 600 samples is a weighted average of two requests
    that happened; the nearest-rank one IS a request that happened. For a
    latency figure that will be quoted in a PRR, "some request took this long"
    is a stronger sentence than "the distribution suggests".
    """
    if not values:
        return float("nan")
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


@dataclass
class LoadResult:
    """Everything measured, and everything needed to read it honestly."""

    target_rate: float
    seconds: float
    concurrency: int
    mix: str
    rows_per_request: int
    endpoint: str
    host: str
    attempts: list[Attempt] = field(default_factory=list)
    label: str = ""
    note: str = ""
    started_at: str = ""
    wall_seconds: float = 0.0

    @property
    def ok_attempts(self) -> list[Attempt]:
        return [a for a in self.attempts if a.ok]

    @property
    def errors(self) -> list[Attempt]:
        return [a for a in self.attempts if not a.ok]

    @property
    def achieved_rate(self) -> float:
        return len(self.attempts) / self.wall_seconds if self.wall_seconds > 0 else 0.0

    @property
    def error_rate(self) -> float:
        return len(self.errors) / len(self.attempts) if self.attempts else 0.0

    @property
    def served_versions(self) -> list[str]:
        """Every distinct version stamp seen ON the responses being timed.

        Not a metadata call: mlserver stamps `model_version` on each answer, so
        a load run also answers "was one model serving the whole window?" — the
        question the self-heal drill needs when a replacement pod appears.
        """
        return sorted({a.model_version for a in self.ok_attempts if a.model_version})

    def percentiles(self, field_name: str = "latency_ms") -> dict[str, float]:
        values = [getattr(a, field_name) for a in self.ok_attempts]
        return {
            "min": min(values) if values else float("nan"),
            "p50": percentile(values, 0.50),
            "p95": percentile(values, 0.95),
            "p99": percentile(values, 0.99),
            "max": max(values) if values else float("nan"),
        }

    def buckets(self) -> list[dict[str, Any]]:
        """Per-SECOND counts, so an error window can be read off the timeline.

        One second is the resolution, and it bounds how precisely any outage can
        be stated from this list alone — which is why `first_error_s` and
        `last_error_s` are recorded exactly, from the raw attempts, beside it
        (the M4-S5 `marts-peak` lesson: record the sample interval, because it
        bounds the peak).
        """
        by_second: dict[int, list[Attempt]] = {}
        for attempt in self.attempts:
            by_second.setdefault(int(attempt.scheduled), []).append(attempt)
        out = []
        for second in sorted(by_second):
            group = by_second[second]
            ok = [a for a in group if a.ok]
            out.append(
                {
                    "second": second,
                    "sent": len(group),
                    "ok": len(ok),
                    "errors": len(group) - len(ok),
                    "p95_latency_ms": round(percentile([a.latency_ms for a in ok], 0.95), 3)
                    if ok
                    else None,
                }
            )
        return out

    def error_window(self) -> dict[str, Any]:
        errors = self.errors
        if not errors:
            return {"errors": 0, "first_error_s": None, "last_error_s": None, "span_s": 0.0}
        first = min(a.scheduled for a in errors)
        last = max(a.done for a in errors)
        return {
            "errors": len(errors),
            "first_error_s": round(first, 3),
            "last_error_s": round(last, 3),
            "span_s": round(last - first, 3),
            "classes": dict(Counter(a.error or f"HTTP {a.status}" for a in errors)),
        }

    def as_record(self) -> dict[str, Any]:
        return {
            "story": "M5-S4",
            "label": self.label,
            "measured_at": self.started_at,
            "shape": {
                "target_rate_per_second": self.target_rate,
                "window_seconds": self.seconds,
                "concurrency": self.concurrency,
                "mix": self.mix,
                "rows_per_request": self.rows_per_request,
                "achieved_rate_per_second": round(self.achieved_rate, 3),
                "wall_seconds": round(self.wall_seconds, 3),
            },
            "endpoint": self.endpoint,
            "host": self.host,
            "requests": {
                "sent": len(self.attempts),
                "ok": len(self.ok_attempts),
                "errors": len(self.errors),
                "error_rate": round(self.error_rate, 6),
            },
            # latency_ms is the headline (scheduled -> response, so a client that
            # falls behind cannot hide it); service_ms is kept beside it because
            # the difference between them IS the coordinated-omission gap.
            "latency_ms": {k: round(v, 3) for k, v in self.percentiles("latency_ms").items()},
            "service_ms": {k: round(v, 3) for k, v in self.percentiles("service_ms").items()},
            "queue_ms": {k: round(v, 3) for k, v in self.percentiles("queue_ms").items()},
            "served_versions": self.served_versions,
            "error_window": self.error_window(),
            "buckets_per_second": self.buckets(),
            "note": self.note,
        }


def _mix_requests(mix: str) -> list[Any]:
    if mix == "hazards":
        return [hazard.request for hazard in HAZARDS]
    if mix == "ordinary":
        return [HAZARDS[0].request]
    raise ValueError(f"unknown mix {mix!r} — known: hazards, ordinary")


def build_bodies(mix: str, rows_per_request: int, features_cfg: dict[str, Any]) -> list[bytes]:
    """Pre-encode every distinct request body ONCE, before the clock starts.

    Encoding is not free (24 named inputs of JSON per request) and it happens in
    the CALLER, so leaving it inside the timed section would put client CPU into
    a number the PRR will read as server latency. The bodies are bytes by the
    time the load starts; the timed section is `urlopen` and nothing else.
    """
    from ..features import quote_time

    names = quote_time.feature_names(features_cfg)
    requests = _mix_requests(mix)
    matrix = build_matrix(requests, features_cfg)
    bodies = []
    for start in range(0, len(matrix), rows_per_request):
        chunk = matrix.iloc[start : start + rows_per_request]
        if len(chunk) < rows_per_request and start > 0:
            continue
        bodies.append(json.dumps(v2_payload(chunk, names), allow_nan=False).encode())
    if not bodies:
        bodies.append(json.dumps(v2_payload(matrix, names), allow_nan=False).encode())
    return bodies


def _fire(url: str, host: str, body: bytes, timeout: float) -> tuple[int, str | None]:
    request = urllib.request.Request(  # noqa: S310 — a fixed http:// route, not user input
        url, data=body, headers={"Content-Type": "application/json", "Host": host}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        payload = json.loads(response.read())
        return response.status, str(payload.get("model_version") or "") or None


def run_load(
    endpoint: Endpoint,
    *,
    rate: float,
    seconds: float,
    concurrency: int,
    mix: str = "hazards",
    rows_per_request: int = 1,
    timeout: float = 20.0,
    features_cfg: dict[str, Any] | None = None,
    label: str = "",
    note: str = "",
    on_second: Any = None,
) -> LoadResult:
    """Drive the endpoint at `rate` req/s for `seconds`, and time every request.

    `on_second(elapsed)` is called from the driver thread once a second. The
    self-heal drill uses it to kill the predictor pod at a stated offset INSIDE
    the load window, so the kill and the measurement share one clock — a kill
    timed by a separate `sleep` in a shell is a kill whose position in the
    timeline is a guess.
    """
    if features_cfg is None:
        from ..training.run import load_train_config

        features_cfg = load_train_config()["features"]

    bodies = build_bodies(mix, rows_per_request, features_cfg)
    total = max(1, int(round(rate * seconds)))
    url, host = endpoint.infer_url, endpoint.host

    attempts: list[Attempt] = []
    lock = threading.Lock()
    counter = {"next": 0}
    t0 = time.perf_counter()

    def worker() -> None:
        while True:
            with lock:
                index = counter["next"]
                if index >= total:
                    return
                counter["next"] = index + 1
            scheduled = index / rate
            delay = scheduled - (time.perf_counter() - t0)
            if delay > 0:
                time.sleep(delay)
            sent = time.perf_counter() - t0
            status: int | None = None
            version: str | None = None
            error: str | None = None
            try:
                status, version = _fire(url, host, bodies[index % len(bodies)], timeout)
                ok = True
            except urllib.error.HTTPError as exc:
                ok, status, error = False, exc.code, f"HTTP {exc.code}"
            except urllib.error.URLError as exc:
                ok, error = False, f"URLError: {exc.reason}"
            except Exception as exc:  # noqa: BLE001 — a load client must survive its own faults
                ok, error = False, f"{type(exc).__name__}: {exc}"
            done = time.perf_counter() - t0
            with lock:
                attempts.append(
                    Attempt(index, scheduled, sent, done, ok, status, error, version)
                )

    started_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    threads = [threading.Thread(target=worker, daemon=True) for _ in range(concurrency)]
    for thread in threads:
        thread.start()

    if on_second is not None:
        tick = 0
        while any(thread.is_alive() for thread in threads):
            time.sleep(0.25)
            elapsed = time.perf_counter() - t0
            while elapsed >= tick:
                on_second(tick)
                tick += 1
    for thread in threads:
        thread.join()

    result = LoadResult(
        target_rate=rate,
        seconds=seconds,
        concurrency=concurrency,
        mix=mix,
        rows_per_request=rows_per_request,
        endpoint=url,
        host=host,
        attempts=sorted(attempts, key=lambda a: a.index),
        label=label,
        note=note,
        started_at=started_at,
        wall_seconds=time.perf_counter() - t0,
    )
    return result


def summary_lines(result: LoadResult) -> list[str]:
    """The percentiles, and never without the shape that produced them."""
    latency = result.percentiles("latency_ms")
    service = result.percentiles("service_ms")
    lines = [
        f"[load] {result.label or 'run'}: {result.mix} mix, "
        f"{result.rows_per_request} row(s)/request, target {result.target_rate:g} req/s "
        f"for {result.seconds:g}s at concurrency {result.concurrency} "
        f"-> achieved {result.achieved_rate:.2f} req/s over {result.wall_seconds:.1f}s",
        f"[load] requests {len(result.attempts)} ok {len(result.ok_attempts)} "
        f"errors {len(result.errors)} ({result.error_rate * 100:.2f}%)",
        f"[load] latency_ms (scheduled->response)  p50 {latency['p50']:.1f}  "
        f"p95 {latency['p95']:.1f}  p99 {latency['p99']:.1f}  max {latency['max']:.1f}",
        f"[load] service_ms (sent->response)       p50 {service['p50']:.1f}  "
        f"p95 {service['p95']:.1f}  p99 {service['p99']:.1f}  max {service['max']:.1f}",
    ]
    gap = latency["p95"] - service["p95"]
    if gap > 0.10 * service["p95"]:
        lines.append(
            f"[load] NOTE: p95 latency exceeds p95 service by {gap:.1f} ms — requests are "
            "waiting for a free worker, so the stated rate is above what this client and "
            "server sustain together. Read the latency figure, not the service one."
        )
    versions = result.served_versions
    if versions:
        lines.append(f"[load] served by version(s) {versions} — stamped on the timed responses")
    return lines


def write_record(result: LoadResult, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.as_record(), indent=2) + "\n")
    return path


def main(argv: list[str] | None = None) -> int:
    """`make load`. Exit 0 = the window completed; the numbers are the product.

    A load client does not PASS or FAIL: it measures. The bar lives in the M5
    gate, which reads the recorded numbers — putting a threshold here would mean
    a capacity measurement that quietly refuses to report the day it matters.
    """
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--route", default=DEFAULT_ROUTE)
    parser.add_argument("--name", default="nyc-taxi-eta")
    parser.add_argument("--namespace", default="serving")
    parser.add_argument("--rate", type=float, default=10.0, help="target requests per second")
    parser.add_argument("--seconds", type=float, default=60.0, help="the window")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--mix", default="hazards", choices=["hazards", "ordinary"])
    parser.add_argument("--rows-per-request", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--label", default="")
    parser.add_argument("--note", default="")
    parser.add_argument("--record", default=None, help="where the JSON lands")
    parser.add_argument("--no-record", action="store_true")
    args = parser.parse_args(argv)

    endpoint = Endpoint(name=args.name, namespace=args.namespace, route=args.route)
    result = run_load(
        endpoint,
        rate=args.rate,
        seconds=args.seconds,
        concurrency=args.concurrency,
        mix=args.mix,
        rows_per_request=args.rows_per_request,
        timeout=args.timeout,
        label=args.label or f"{args.rate:g}rps-{args.seconds:g}s",
        note=args.note,
    )
    print()
    for line in summary_lines(result):
        print(line)
    if not args.no_record:
        path = Path(args.record or DEFAULT_RECORD_DIR / f"load-{result.label}.json")
        print(f"[load] record -> {write_record(result, path)}")
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised through `make load`
    raise SystemExit(main())
