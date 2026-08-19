"""route_availability_probe.py — is the route answering, second by second? (M6-S1)

A deliberately small instrument with one job: poll the live quote endpoint at a
fixed rate for a stated window and write down, per second, whether it answered.
It exists because M6 law 2 says every mutation of the wire is recorded WITH its
measured outage, and "the helm upgrade finished" is not that measurement.

TWO RULES IT INHERITS, BOTH PAID FOR ALREADY:

* **The outage is anchored on failure→success, never on failure→failure**
  (gotcha #75). M5-S4's first attempt computed `last_error - first_error` and
  reported a 182-second "outage" for a service that was dead for 13 seconds and
  then dropped ten requests out of 1,400 while saturated. Here `outage_seconds`
  is `first success AFTER the first failure` minus `first failure`, and the raw
  per-sample log is written too so a future reader can re-derive it differently
  and see that they disagree.
* **It is an OPEN loop.** A sample is due at `t0 + k/rate` whether or not the
  previous one has returned, so a hanging server produces missed samples rather
  than quietly reducing its own load (M5-S4's coordinated-omission argument, one
  layer down).

It sends the model's own readiness endpoint, not an inference: this measures the
ROUTE, and a 24-feature body would make the sample depend on the feature path
too.

    uv run python scripts/route_availability_probe.py --seconds 240 \
        --out automation/runs/m6-monitoring/ingress-roll.json --label "ingress-nginx metrics roll"
"""

from __future__ import annotations

import argparse
import json
import pathlib
import threading
import time
import urllib.error
import urllib.request

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
ROUTE = "http://localhost:8081"
SERVING_HOST = "nyc-taxi-eta-serving.local"
PATH = "/v2/models/nyc-taxi-eta/ready"


def sample(results: list[dict], index: int, due: float) -> None:
    req = urllib.request.Request(ROUTE + PATH, headers={"Host": SERVING_HOST})
    sent = time.time()
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            status, err = resp.status, None
            resp.read()
    except urllib.error.HTTPError as exc:
        status, err = exc.code, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001 — a refused connection is the signal
        status, err = 0, f"{type(exc).__name__}: {exc}"
    done = time.time()
    results.append({
        "index": index,
        "due_offset_s": round(due, 3),
        "offset_s": round(sent - due + due, 3),
        "latency_ms": round((done - sent) * 1000, 2),
        "status": status,
        "ok": status == 200,
        "error": err,
    })


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seconds", type=float, default=240.0)
    ap.add_argument("--rate", type=float, default=2.0, help="samples per second")
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    total = int(args.seconds * args.rate)
    results: list[dict] = []
    threads: list[threading.Thread] = []
    t0 = time.time()
    for k in range(total):
        due = k / args.rate
        delay = t0 + due - time.time()
        if delay > 0:
            time.sleep(delay)
        th = threading.Thread(target=sample, args=(results, k, due), daemon=True)
        th.start()
        threads.append(th)
    for th in threads:
        th.join(timeout=10)

    results.sort(key=lambda r: r["index"])
    failures = [r for r in results if not r["ok"]]
    outage = None
    if failures:
        first_fail = failures[0]
        after = [r for r in results
                 if r["index"] > first_fail["index"] and r["ok"]]
        if after:
            outage = round(after[0]["due_offset_s"] - first_fail["due_offset_s"], 3)

    record = {
        "label": args.label,
        "started_unix": t0,
        "window_s": args.seconds,
        "rate_per_s": args.rate,
        "samples": len(results),
        "ok": sum(1 for r in results if r["ok"]),
        "failed": len(failures),
        "first_failure_offset_s": failures[0]["due_offset_s"] if failures else None,
        "first_success_after_failure_offset_s": (
            round(failures[0]["due_offset_s"] + outage, 3)
            if outage is not None else None),
        "outage_seconds": outage,
        "outage_anchors": ("first failure -> first success after it "
                           "(NOT first error -> last error, gotcha #75)"),
        "status_counts": {},
        "samples_raw": results,
    }
    for r in results:
        key = str(r["status"])
        record["status_counts"][key] = record["status_counts"].get(key, 0) + 1

    out = pathlib.Path(args.out)
    if not out.is_absolute():
        out = REPO_ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + "\n")

    print(f"[route-probe] {args.label or PATH}: {record['ok']}/{record['samples']} "
          f"ok, {record['failed']} failed, outage="
          f"{record['outage_seconds']} s -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
