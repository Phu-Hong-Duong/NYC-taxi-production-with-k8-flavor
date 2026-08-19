"""monitoring_accept.py — does the metrics pipeline actually carry a rider's
request all the way to a rendered panel? (M6-S1, behind `make monitoring-accept`)

WHY THIS IS NOT A TARGET LIST. `up == 1` for a scrape job proves Prometheus can
open a TCP connection to a port. It does not prove that a request becomes a
number, and it is exactly as green when the counter it scrapes never moves —
which is the same picture a dashboard paints when nothing is happening (gotcha
#59: assert on the positive artifact the thing exists to produce). So the middle
leg here READS A COUNTER, SENDS ONE REAL QUOTE THROUGH THE LIVE ENDPOINT, WAITS
FOR A SCRAPE, AND READS IT AGAIN. If that number does not move, the pipeline is
broken no matter how many targets are up.

WHY THE BOARD'S QUERY IS PARSED OUT OF THE CHECKED-IN JSON. Re-typing a PromQL
expression here would give the repo two copies of it, and the copy in this file
would be the one that stays right (F-017, gotchas #49/#50 — a literal encodes the
day it was written). The board's panels are read from
`analytics/grafana/dashboards/serving.json` and every one of their expressions is
executed against Prometheus. A panel whose query is a typo is then a FAILING
check rather than an empty rectangle nobody scrolls to.

It is a READER of the model: it asks the endpoint for one prediction (the same
thing `make quote` does) and touches no registry, no alias, no manifest.

    uv run python scripts/monitoring_accept.py
    uv run python scripts/monitoring_accept.py --json   # machine-readable record
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DASHBOARD = REPO_ROOT / "analytics" / "grafana" / "dashboards" / "serving.json"
RECORD_DIR = REPO_ROOT / "automation" / "runs" / "m6-monitoring"

# The route M5-S1 installed. Host-based, because kind publishes host ports at
# cluster-CREATE only and this cluster is not rebuilding (M6 law 1).
ROUTE = "http://localhost:8081"
PROM_HOST = "prometheus.local"
GRAFANA_HOST = "grafana.local"

# The scrape interval this repo configures for the predictor job, plus slack.
# Named here rather than typed inline so the reason for the wait is legible.
SCRAPE_INTERVAL_S = 15
SCRAPE_WAIT_S = 40

# Every job the M6-S1 values file expects to exist. Derived-ish: these are the
# job names a reviewer can find in prometheus-values.yaml (ours) or in the
# chart's defaults (the two kubernetes-* ones), and a missing one is a scrape
# that silently stopped rather than a target that is merely down.
REQUIRED_JOBS = (
    "kserve-predictors",             # ours — the predictor's own /metrics on 8082
    "kubernetes-service-endpoints",  # chart default — ingress-nginx + kube-state-metrics
    "kubernetes-nodes-cadvisor",     # chart default — container CPU + CFS throttling
)

failures: list[str] = []
verdicts = 0


def ok(msg: str) -> None:
    global verdicts
    verdicts += 1
    print(f"ok  {msg}")


def fail(msg: str) -> None:
    global verdicts
    verdicts += 1
    failures.append(msg)
    print(f"FAIL {msg}")


def http_get(host: str, path: str, timeout: int = 20) -> tuple[int, str]:
    req = urllib.request.Request(ROUTE + path, headers={"Host": host})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def promql(expr: str) -> dict:
    path = "/api/v1/query?" + urllib.parse.urlencode({"query": expr})
    status, body = http_get(PROM_HOST, path)
    if status != 200:
        raise RuntimeError(f"Prometheus answered HTTP {status} for {expr!r}")
    payload = json.loads(body)
    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus refused {expr!r}: {payload}")
    return payload["data"]


def scalar(expr: str, default: float = 0.0) -> float:
    result = promql(expr)["result"]
    if not result:
        return default
    return float(result[0]["value"][1])


# --- 1. the route answers, and it is the right server -------------------------
def check_route() -> None:
    status, _ = http_get(PROM_HOST, "/-/healthy")
    if status == 200:
        ok(f"Prometheus answers through the 8081 ingress as Host: {PROM_HOST} "
           f"(/-/healthy -> 200)")
    else:
        fail(f"Prometheus /-/healthy through the ingress -> HTTP {status}")

    status, body = http_get(GRAFANA_HOST, "/api/health")
    if status == 200:
        try:
            version = json.loads(body).get("version", "?")
        except ValueError:
            version = "?"
        ok(f"Grafana answers through the same route as Host: {GRAFANA_HOST} "
           f"(/api/health -> 200, version {version})")
    else:
        fail(f"Grafana /api/health through the ingress -> HTTP {status}")


# --- 2. every job this program configured is being scraped --------------------
def check_targets() -> None:
    status, body = http_get(PROM_HOST, "/api/v1/targets?state=active")
    if status != 200:
        fail(f"/api/v1/targets -> HTTP {status}")
        return
    targets = json.loads(body)["data"]["activeTargets"]
    by_job: dict[str, list[dict]] = {}
    for t in targets:
        by_job.setdefault(t["labels"].get("job", "?"), []).append(t)
    for job in REQUIRED_JOBS:
        found = by_job.get(job, [])
        up = [t for t in found if t.get("health") == "up"]
        if not found:
            fail(f"scrape job {job!r} has NO targets — the config never took")
        elif not up:
            reason = found[0].get("lastError") or "(no error text)"
            fail(f"scrape job {job!r}: {len(found)} target(s), none up — {reason}")
        else:
            ok(f"scrape job {job!r}: {len(up)}/{len(found)} target(s) up")

    # The predictor is the one target whose PORT was probed rather than believed
    # (KServe's own pod annotation advertises 8080, which 404s on this runtime).
    # Say which port is actually being scraped, so a future reader sees the fact
    # and not the assumption.
    for t in by_job.get("kserve-predictors", []):
        ok(f"  predictor target {t['labels'].get('inferenceservice','?')} "
           f"-> {t.get('scrapeUrl')} ({t.get('health')})")


# --- 3. one real request becomes a number ------------------------------------
def check_request_becomes_a_number() -> dict:
    expr = ('sum(rest_server_requests_total'
            '{job="kserve-predictors",path="/v2/models/{model_name}/infer"})')
    before = scalar(expr)
    print(f"    counter before: {before:.0f}  ({expr})")

    proc = subprocess.run(
        ["make", "quote"], cwd=REPO_ROOT, capture_output=True, text=True,
    )
    quoted = proc.returncode == 0
    # The line that carries the ANSWER, not the last line make happens to print.
    lines = [ln for ln in proc.stdout.splitlines() if "minute" in ln.lower()]
    answer = lines[-1].strip() if lines else (proc.stdout.strip().splitlines() or ["(no output)"])[-1]
    if quoted:
        ok(f"one real quote sent through the live endpoint: {answer[:120]}")
    else:
        fail(f"`make quote` exited {proc.returncode} — no request to observe. "
             f"{(proc.stderr or proc.stdout).strip()[-200:]}")
        return {"before": before, "after": before, "delta": 0.0, "quoted": False}

    print(f"    waiting {SCRAPE_WAIT_S}s for a scrape "
          f"(the job's interval is {SCRAPE_INTERVAL_S}s) …")
    time.sleep(SCRAPE_WAIT_S)
    after = scalar(expr)
    delta = after - before
    print(f"    counter after:  {after:.0f}")
    if delta >= 1:
        ok(f"the request reached Prometheus: inference counter {before:.0f} -> "
           f"{after:.0f} (+{delta:.0f}) — a scrape target being 'up' could not "
           f"have told us this")
    else:
        fail(f"the inference counter did not move ({before:.0f} -> {after:.0f}) "
             f"even though a quote was served — the scrape reaches a port but "
             f"not this counter")
    return {"before": before, "after": after, "delta": delta, "quoted": quoted}


# --- 4. the board is provisioned, and every panel's query answers -------------
def check_board() -> dict:
    spec = json.loads(DASHBOARD.read_text())
    uid = spec["uid"]
    status, body = http_get(GRAFANA_HOST, f"/api/dashboards/uid/{uid}")
    if status == 200:
        live = json.loads(body)["dashboard"]
        ok(f"Grafana serves the provisioned board {uid!r} "
           f"({live.get('title')}) with {len(live.get('panels', []))} panel(s) — "
           f"provisioned from git, not clicked")
    else:
        fail(f"Grafana does not serve board {uid!r} (HTTP {status}) — the "
             f"ConfigMap or the sidecar label is wrong")

    answered: list[dict] = []
    for panel in spec["panels"]:
        for target in panel.get("targets", []):
            expr = target["expr"]
            try:
                data = promql(expr)
            except (RuntimeError, urllib.error.URLError) as exc:
                fail(f"panel {panel['id']} ({panel['title'][:40]}…) target "
                     f"{target['refId']}: {exc}")
                continue
            series = len(data["result"])
            answered.append({
                "panel": panel["id"], "refId": target["refId"],
                "series": series, "expr": expr,
            })
            print(f"    panel {panel['id']}.{target['refId']}: {series} series")
    if answered:
        # EVERY query must return at least one series, and that bar is the whole
        # value of this leg. The first draft called 0 series "legal for a counter
        # with no traffic yet" and printed it in green — which hid three real
        # defects at once: the ingress metrics Service was never discovered
        # (annotation missing), and two container panels could not draw at all
        # because a rate() over a 1-minute window at a 1-minute scrape interval
        # has one sample. A panel that renders an empty rectangle looks exactly
        # like a quiet system, so an empty rectangle must be a FAILURE here, not
        # a footnote. If a future panel is legitimately empty, this goes red and
        # a human decides — which is the correct place for that judgement.
        empty = [a for a in answered if not a["series"]]
        if empty:
            for a in empty:
                fail(f"panel {a['panel']}.{a['refId']} returned 0 series — it "
                     f"would render an empty rectangle, which is indistinguishable "
                     f"from a quiet system: {a['expr'][:120]}")
        else:
            ok(f"all {len(answered)} panel queries executed against Prometheus "
               f"and every one returned live series — no panel on this board "
               f"renders an empty rectangle")
    return {"uid": uid, "queries": answered}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true",
                        help="also write the record under automation/runs/m6-monitoring/")
    args = parser.parse_args()

    print("== monitoring accept (M6-S1) ==")
    print(f"route {ROUTE} · hosts {PROM_HOST} / {GRAFANA_HOST}\n")

    print("-- 1. the route answers --")
    check_route()
    print("\n-- 2. the scrape jobs --")
    check_targets()
    print("\n-- 3. one real request becomes a number --")
    counter = check_request_becomes_a_number()
    print("\n-- 4. the board, and every query on it --")
    board = check_board()

    print()
    if failures:
        print(f"[monitoring-accept] RED — {len(failures)} failure(s) of "
              f"{verdicts} sub-check(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"[monitoring-accept] GREEN — {verdicts} sub-check(s) passed.")

    if args.json:
        RECORD_DIR.mkdir(parents=True, exist_ok=True)
        path = RECORD_DIR / "accept.json"
        path.write_text(json.dumps({
            "route": ROUTE,
            "prometheus_host": PROM_HOST,
            "grafana_host": GRAFANA_HOST,
            "scrape_wait_s": SCRAPE_WAIT_S,
            "inference_counter": counter,
            "board": board,
            "sub_checks": verdicts,
        }, indent=2) + "\n")
        print(f"[monitoring-accept] record -> {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
