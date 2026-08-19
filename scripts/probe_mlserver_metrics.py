"""Probe: does the mlserver predictor expose Prometheus metrics, and where? (M6-S1)

The M6 kickoff believes `/metrics` on 8082 and says so with the instruction that
made M5-S1 cheap: ASK THE SERVER, never the docs (gotcha #70 — the serving route
went RED demanding a `Server: nginx` header that modern ingress-nginx suppresses
on purpose). A scrape config written against a believed port produces a target
that is permanently DOWN and a dashboard that renders an empty panel, which is
the same picture as "nothing is happening".

So this asks. It port-forwards the live predictor pod on both the believed
metrics port and the inference port, GETs /metrics on each, and prints what came
back: HTTP status, line count, and the series names that mention a model, a
request or an inference — the ones a serving board would actually plot.

It is a READER: no deploy, no restart, no registry call. Run it before writing a
scrape config, and again if the predictor image ever changes.

    uv run python scripts/probe_mlserver_metrics.py
"""

from __future__ import annotations

import subprocess
import time
import urllib.error
import urllib.request

NAMESPACE = "serving"
ISVC_LABEL = "serving.kserve.io/inferenceservice=nyc-taxi-eta"

# The believed metrics port first, then the inference port — mlserver has
# historically served metrics on both depending on `METRICS_PORT`.
PORTS = (8082, 8080)


def predictor_pod() -> str:
    out = subprocess.run(
        ["kubectl", "-n", NAMESPACE, "get", "pod", "-l", ISVC_LABEL,
         "-o", "jsonpath={.items[0].metadata.name}"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    if not out:
        raise SystemExit(f"no predictor pod matches {ISVC_LABEL} in ns/{NAMESPACE}")
    return out


def probe(pod: str, remote: int) -> None:
    local = 19000 + remote % 1000
    pf = subprocess.Popen(
        ["kubectl", "-n", NAMESPACE, "port-forward", f"pod/{pod}",
         f"{local}:{remote}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(4)
    url = f"http://127.0.0.1:{local}/metrics"
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as exc:
        print(f"\n=== :{remote}/metrics -> FAILED ({type(exc).__name__}: {exc}) ===")
        return
    finally:
        pf.terminate()
        pf.wait()

    lines = [ln for ln in body.splitlines() if ln.strip()]
    samples = [ln for ln in lines if not ln.startswith("#")]
    names = sorted({ln.split("{")[0].split(" ")[0] for ln in samples})
    print(f"\n=== :{remote}/metrics -> HTTP {status}, {len(lines)} lines, "
          f"{len(names)} distinct series ===")
    print("  first 10 samples:")
    for ln in samples[:10]:
        print("   ", ln[:120])
    interesting = [n for n in names
                   if any(k in n for k in ("model", "request", "infer"))]
    print(f"  serving-relevant series ({len(interesting)}):")
    for n in interesting:
        print("   ", n)
    # The LABELS are what a board and an alert are written against — a counter
    # called `rest_server_requests_total` is only a 5xx/422 split if it carries
    # a status-code label. Print one sample per interesting series, whole.
    print("  one whole sample per serving-relevant series (labels included):")
    seen: set[str] = set()
    for ln in samples:
        name = ln.split("{")[0].split(" ")[0]
        if name in interesting and name not in seen:
            seen.add(name)
            print("   ", ln[:200])


def main() -> None:
    pod = predictor_pod()
    print(f"predictor pod: {pod}  (ns/{NAMESPACE})")
    for port in PORTS:
        probe(pod, port)


if __name__ == "__main__":
    main()
