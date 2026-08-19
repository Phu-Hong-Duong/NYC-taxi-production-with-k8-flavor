#!/usr/bin/env python
"""Gameday 1 — staged failures with distinguishable signatures, predicted FIRST.

M6-S5, behind `make gameday`. BLUEPRINT §9/M6 asks for a predecessor-style
gameday: a **positive control before any negative result**, then staged failures
each carrying a signature written down BEFORE the injection and checked after.

WHY THE POSITIVE CONTROL COMES FIRST, AND WHY IT IS NOT CEREMONY.
Three of the four scenarios below make a claim of the form "alert X did NOT
fire". That sentence is worthless from an instrument nobody has just seen work:
a Prometheus that lost its rules, an Alertmanager that lost its route, a scrape
config that silently stopped discovering the predictor would all produce a
perfect run of silent alerts. So scenario 0 fires two REAL alerts end to end
(Prometheus rule -> pending -> firing -> Alertmanager) and only then are the
negatives worth reading. It is the prior-art ADOPT, and it is the reason the
kill scenario's "nothing fired" is evidence rather than an absence of evidence.

THE FOUR SCENARIOS AND WHAT MAKES THEM DISTINGUISHABLE.

  0. **control** — the M6-S2 injection, re-run as the control: malformed bodies
     (422) and signature-refused bodies (500) fire A-3 then A-2, in that order.
     Delegated to `scripts/alert_fire_drill.py` rather than re-implemented; its
     records are written into this gameday's directory so the control that this
     gameday actually ran is the one on disk beside it.

  1. **kill** — M5-S4's self-heal drill re-run, with the ALERTS in the
     prediction. Signature: a short burst of 5xx AT THE EDGE, a new pod object,
     and — the interesting half — NO alert.

  2. **storage** — break the MinIO credential the storage-initializer uses, then
     delete the pod. Signature: the REPLACEMENT never starts. No 5xx spike,
     because there is no traffic; an init container that never becomes ready;
     A-5 then A-7. Explicitly the opposite shape to (1), which is the whole
     point of running both.

  3. **saturation** — drive past the measured CPU ceiling. Signature: latency
     and CFS throttling with ZERO errors (gotcha #74 as a prediction), which no
     error-rate alert and no health probe can see.

WHAT IT COSTS, STATED UP FRONT. Scenario 2 is a REAL OUTAGE of the only
predictor, held long enough for a `for: 3m` rule to fire — about five minutes.
The undo is staged before the injection (the M2 red-team rule): `make serve`
re-converges the secret from `.env`, idempotently, proven four times at M5-S2.
Scenarios 0 and 3 spend error budget and CPU but take nothing down; scenario 1
costs the ~15 s a killed pod has cost every time it has been measured.

WHAT IT NEVER TOUCHES. No alias is written (`@champion` is read at the start and
at the end and a move is a FAILED check). No registry version is minted. No helm
release is upgraded except by `make serve`'s own idempotent re-converge. The
cluster is never taken down.

Usage:
    make gameday                         # every scenario, in order
    make gameday GAMEDAY_ARGS="--scenario predict"      # predictions only
    make gameday GAMEDAY_ARGS="--scenario kill"         # one scenario
    make gameday GAMEDAY_ARGS="--scenario report"       # assemble the record
"""

from __future__ import annotations

import argparse
import contextlib
import json
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

RECORD_DIR = REPO_ROOT / "automation" / "runs" / "m6-gameday"

ROUTE = "http://localhost:8081"
PROM_HOST = "prometheus.local"
SERVING_HOST = "nyc-taxi-eta-serving.local"
SERVING_NS = "serving"
ISVC_NAME = "nyc-taxi-eta"
PREDICTOR_DEPLOY = f"{ISVC_NAME}-predictor"
STORAGE_SECRET = "minio-serving"

#: Every rule this gameday watches, by alert name -> signal id. Derived from the
#: rules file at run time is NOT possible without a YAML dependency in a script
#: that must run on a broken cluster, so the names are checked against
#: Prometheus's loaded set in every preflight: a renamed rule fails the drill
#: rather than silently becoming an alert that "did not fire".
WATCHED: dict[str, str] = {
    "PredictorLatencySLOBurning": "A-1",
    "ServingEdge5xxRateHigh": "A-2",
    "PredictorRequestRejectionRateHigh": "A-3",
    "PredictorNoAvailableReplica": "A-5",
    "PredictorRestartFlapping": "A-5",
    "PredictorCpuThrottledSustained": "A-6",
    "PredictorStorageInitializerNotReady": "A-7",
}

ALERTMANAGER_LOCAL_PORT = 9096  # ephemeral, torn down on exit (the 8092 precedent)


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def say(msg: str) -> None:
    print(f"[gameday] {msg}", flush=True)


# --- readers ------------------------------------------------------------------


def http_get(host: str, url: str, timeout: float = 20.0) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"Host": host})  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def prom_query(expr: str) -> list[dict[str, Any]]:
    from urllib.parse import quote

    status, body = http_get(PROM_HOST, f"{ROUTE}/api/v1/query?query={quote(expr)}")
    if status != 200:
        raise RuntimeError(f"Prometheus query -> {status}: {body[:200]}")
    payload = json.loads(body)
    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus query failed: {payload}")
    return payload["data"]["result"]


def prom_scalar(expr: str, default: float = 0.0) -> float:
    result = prom_query(expr)
    if not result:
        return default
    return float(result[0]["value"][1])


def rule_states() -> dict[str, str]:
    status, body = http_get(PROM_HOST, f"{ROUTE}/api/v1/rules")
    if status != 200:
        raise RuntimeError(f"Prometheus /api/v1/rules -> {status}")
    out: dict[str, str] = {}
    for group in json.loads(body)["data"]["groups"]:
        for rule in group["rules"]:
            if rule.get("type") == "alerting":
                out[rule["name"]] = rule["state"]
    return out


def kubectl(*args: str, check: bool = True) -> str:
    result = subprocess.run(  # noqa: S603
        ["kubectl", *args], capture_output=True, text=True, check=False
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"kubectl {' '.join(args)} -> {result.returncode}: {result.stderr}")
    return result.stdout.strip()


def predictor_pod() -> dict[str, str]:
    """Name and UID of the champion's predictor pod. IDENTITY, never name alone.

    M4-S5's lesson: the k8s plugin can recreate a pod under the SAME name with a
    new UID, so "a different pod came back" is a claim about the uid.
    """
    out = kubectl(
        "-n",
        SERVING_NS,
        "get",
        "pods",
        "-l",
        f"serving.kserve.io/inferenceservice={ISVC_NAME}",
        "-o",
        "jsonpath={range .items[*]}{.metadata.name},{.metadata.uid},{.status.phase}{'\\n'}{end}",
    )
    for line in out.splitlines():
        name, uid, phase = line.split(",")
        if phase != "Succeeded":
            return {"name": name, "uid": uid, "phase": phase}
    return {"name": "", "uid": "", "phase": "absent"}


def champion_version() -> str:
    out = subprocess.run(  # noqa: S603
        ["uv", "run", "python", "scripts/resolve_champion_storage.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        return "unreadable"
    return str(json.loads(out.stdout)["version"])


# --- the shared discipline ----------------------------------------------------


def preflight(*, need_endpoint: bool = True) -> list[str]:
    """Every watched rule loaded, healthy, INACTIVE; and no residue in the windows.

    The residue check matters because the scenarios run back to back and every
    rule here reads a `rate(...[5m])`. A scenario that starts while the previous
    one's errors are still inside the window would measure the previous one.
    """
    problems: list[str] = []
    states = rule_states()
    for name in sorted(WATCHED):
        state = states.get(name)
        if state is None:
            problems.append(f"rule {name} is not loaded in Prometheus")
        elif state != "inactive":
            problems.append(f"rule {name} is already {state} — a scenario now would prove nothing")
    if need_endpoint:
        status, _ = http_get(SERVING_HOST, f"{ROUTE}/v2/models/nyc-taxi-eta")
        if status != 200:
            problems.append(f"the endpoint does not answer metadata: HTTP {status}")
    return problems


def settle(max_seconds: float = 420.0, poll: float = 15.0) -> dict[str, Any]:
    """Wait until the previous scenario has left every 5-minute rate window.

    Positive condition (gotcha #59): the edge 5xx rate AND the predictor 4xx rate
    must both read zero, and every watched rule must be inactive.
    """
    expr_5xx = (
        'sum(rate(nginx_ingress_controller_requests{namespace="serving",'
        'ingress="nyc-taxi-eta",status=~"5.."}[5m]))'
    )
    expr_4xx = (
        'sum(rate(rest_server_requests_total{job="kserve-predictors",'
        'path=~".*infer",status_code=~"4.."}[5m]))'
    )
    t0 = time.monotonic()
    while True:
        elapsed = time.monotonic() - t0
        edge = prom_scalar(expr_5xx)
        rejected = prom_scalar(expr_4xx)
        states = rule_states()
        busy = sorted(n for n in WATCHED if states.get(n) != "inactive")
        if edge == 0.0 and rejected == 0.0 and not busy:
            say(
                f"    settled after {elapsed:.0f}s — edge 5xx rate 0, 4xx rate 0, "
                "all rules inactive"
            )
            return {"settled": True, "seconds": round(elapsed, 1)}
        if elapsed > max_seconds:
            say(
                f"    NOT settled after {elapsed:.0f}s (edge5xx={edge:.4f} 4xx={rejected:.4f} "
                f"busy={busy}) — recorded, continuing"
            )
            return {"settled": False, "seconds": round(elapsed, 1), "busy": busy}
        time.sleep(poll)


class AlertWatcher:
    """Polls rule states and records every transition against one clock."""

    def __init__(self) -> None:
        self.timeline: list[dict[str, Any]] = []
        self.first_pending: dict[str, float] = {}
        self.first_firing: dict[str, float] = {}
        self.last: dict[str, str] = dict.fromkeys(WATCHED, "inactive")
        self.t0 = time.monotonic()

    def poll(self) -> None:
        elapsed = round(time.monotonic() - self.t0, 1)
        states = rule_states()
        for name in sorted(WATCHED):
            state = states.get(name, "absent")
            if state != self.last.get(name):
                self.timeline.append({"t_plus_s": elapsed, "alert": name, "state": state})
                say(f"    T+{elapsed:6.1f}s  {WATCHED[name]} {name} -> {state}")
                if state == "pending" and name not in self.first_pending:
                    self.first_pending[name] = elapsed
                if state == "firing" and name not in self.first_firing:
                    self.first_firing[name] = elapsed
                self.last[name] = state

    def watch(self, seconds: float, poll: float = 10.0) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.poll()
            time.sleep(poll)
        self.poll()

    def as_record(self) -> dict[str, Any]:
        return {
            "timeline": self.timeline,
            "first_pending_at_s": self.first_pending,
            "first_firing_at_s": self.first_firing,
            "ever_fired": sorted(self.first_firing),
        }


def alertmanager_names(port: int) -> list[str]:
    status, body = http_get("localhost", f"http://localhost:{port}/api/v2/alerts")
    if status != 200:
        return []
    return sorted({a["labels"].get("alertname", "?") for a in json.loads(body)})


class AlertmanagerForward:
    def __enter__(self) -> int:
        self.proc = subprocess.Popen(  # noqa: S603
            [
                "kubectl",
                "-n",
                "monitoring",
                "port-forward",
                "svc/prometheus-alertmanager",
                f"{ALERTMANAGER_LOCAL_PORT}:9093",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(4)
        return ALERTMANAGER_LOCAL_PORT

    def __exit__(self, *exc: object) -> None:
        self.proc.terminate()


# --- the predictions ----------------------------------------------------------
#
# EVERY NUMBER BELOW IS DERIVED, AND THE DERIVATION IS IN THE `why`. Two of them
# contradict the M6 kickoff's own expectation, and that is deliberate: the
# kickoff predicted scenario 1 would fire A-2 and A-5, and the arithmetic of the
# thresholds M6-S2 argued says it cannot. Writing the arithmetic down is what
# makes one of us wrong in public.

KILL_RATE = 4.0
KILL_SECONDS = 300.0
KILL_AT = 30.0
SATURATION_RATE = 8.0
SATURATION_SECONDS = 780.0

PREDICTIONS: dict[str, dict[str, Any]] = {
    "control": {
        "title": "positive control — fire A-3 then A-2 end to end",
        "injection": "malformed bodies (422) and signature-refused bodies (500) at 4 req/s",
        "must_fire": ["PredictorRequestRejectionRateHigh", "ServingEdge5xxRateHigh"],
        "must_not_fire": [
            "PredictorLatencySLOBurning",
            "PredictorNoAvailableReplica",
            "PredictorRestartFlapping",
            "PredictorCpuThrottledSustained",
            "PredictorStorageInitializerNotReady",
        ],
        "signature": (
            "errors WITHOUT an outage: an ordinary quote succeeds throughout, no pod is "
            "replaced, and the two alerts arrive in ascending order of their sustain windows "
            "(A-3 at about T+150 s, A-2 at about T+330 s)."
        ),
        "why": (
            "this is M6-S2's measured drill re-run as the control. It proves the whole path — "
            "scrape, rule evaluation, pending, firing, Alertmanager — before any 'nothing "
            "fired' below is read as evidence."
        ),
    },
    "kill": {
        "title": "kill the predictor under load",
        "injection": (
            f"{KILL_RATE} req/s open-loop for {KILL_SECONDS:.0f}s, hazard mix, the predictor "
            f"pod deleted at T+{KILL_AT:.0f}s from inside the load client's own callback"
        ),
        "must_fire": [],
        "must_not_fire": sorted(WATCHED),
        "signature": (
            "a SHORT burst of 5xx at the edge (about 14-15 s, the number three prior "
            "measurements agree on), a DIFFERENT pod uid, zero errors after recovery — and "
            "NO ALERT AT ALL."
        ),
        "why": (
            "A-2 needs the 5xx SHARE over a 5-minute rate window to exceed 0.10 and hold for "
            f"5m. At {KILL_RATE} req/s a {KILL_SECONDS:.0f}s window carries about "
            f"{int(KILL_RATE * KILL_SECONDS)} requests and a ~15 s outage costs about 60 of "
            "them, i.e. ~5% — under the bar by about half. A-5 needs NO available replica for "
            "2m and the replacement is ready in well under one. The flapping rule needs 3 "
            "restarts of kserve-container in 15m and this is one pod REPLACEMENT, not a "
            "container restart, so its counter does not move at all. THIS CONTRADICTS THE M6 "
            "KICKOFF, which predicted A-2/A-5 would fire within their windows; the thresholds "
            "M6-S2 argued were chosen precisely so that one self-heal cannot page, and if the "
            "kickoff is right instead then the 10% bar is reachable by a normal recovery and "
            "docs/slo_serving.md §3's arithmetic is wrong."
        ),
        "quantities": {
            "expected_outage_seconds_between": [10.0, 25.0],
            "expected_edge_5xx_share_peak_below": 0.10,
            "expected_new_pod_uid": True,
        },
    },
    "storage": {
        "title": "break the storage credential, then delete the pod",
        "injection": (
            f"secret/{STORAGE_SECRET}'s AWS_SECRET_ACCESS_KEY overwritten with a wrong value, "
            "then the predictor pod deleted. NO load is applied."
        ),
        "must_fire": ["PredictorNoAvailableReplica", "PredictorStorageInitializerNotReady"],
        "must_not_fire": [
            "PredictorLatencySLOBurning",
            "ServingEdge5xxRateHigh",
            "PredictorRequestRejectionRateHigh",
            "PredictorRestartFlapping",
            "PredictorCpuThrottledSustained",
        ],
        "signature": (
            "the REPLACEMENT never starts: the pod sits in Init, the route answers 503 with no "
            "5xx RATIO to speak of because nobody is asking, and the two alerts that fire are "
            "the two that need no traffic. Utterly unlike scenario 1, which is what makes the "
            "pair worth running."
        ),
        "why": (
            "A-5 is `replicas_available < 1 for 2m` and the replacement cannot become "
            "available at all, so it fires at about T+2m plus one scrape. A-7 is "
            "`init_container_ready == 0 for 3m` and fires about a minute LATER. NOTE THE "
            "ORDER: the A-7 rule's own `why` annotation claims it 'fires before A-5 does', "
            "and 2m < 3m says it cannot. If A-7 arrives second, that annotation is wrong and "
            "the SLO doc owes a correction. A-2 stays inactive DESPITE a total outage — the "
            "blind spot docs/slo_serving.md §3 documents for it, demonstrated rather than "
            "asserted. The flapping rule watches kserve-container, which never starts, so its "
            "restart counter never moves."
        ),
        "quantities": {
            "expected_a5_fires_before_a7": True,
            "expected_undo": "make serve re-converges the secret from .env and the pod starts",
        },
    },
    "saturation": {
        "title": "drive past the measured CPU ceiling",
        "injection": (
            f"{SATURATION_RATE} req/s open-loop for {SATURATION_SECONDS:.0f}s — M5-S4 measured "
            "8 req/s at 101% of the 2-core limit"
        ),
        "must_fire": ["PredictorCpuThrottledSustained"],
        "must_not_fire": [
            "ServingEdge5xxRateHigh",
            "PredictorRequestRejectionRateHigh",
            "PredictorNoAvailableReplica",
            "PredictorRestartFlapping",
            "PredictorStorageInitializerNotReady",
        ],
        "unpredictable": ["PredictorLatencySLOBurning"],
        "signature": (
            "latency and throttling with ZERO errors. Nothing crashes, nothing restarts, the "
            "route answers every request — and the service is nonetheless degraded by a "
            "factor of about six at the p50. A-6 is the only signal that can see it."
        ),
        "why": (
            "gotcha #74 as a prediction. M5-S4's ramp measured the throttled fraction at 0.23 "
            "/ 0.51 / 0.79 / ~1.00 at 2/4/6/8 req/s with ZERO errors on every row, so at 8 "
            "req/s the fraction should sit above A-6's 0.90 bar and the rule fires after its "
            f"10m sustain — which is why the window is {SATURATION_SECONDS:.0f}s and not the "
            "180 s a latency measurement would need. A-1 is listed UNPREDICTABLE on purpose: "
            "it counts requests slower than 250 ms among status 200, and at saturation the "
            "p50 was 115 ms with an unmeasured tail. Predicting it either way would be a "
            "guess dressed as a derivation."
        ),
        "quantities": {
            "expected_error_count": 0,
            "expected_throttled_fraction_above": 0.90,
        },
    },
}


def write_predictions(path: Path) -> dict[str, Any]:
    payload = {
        "story": "M6-S5",
        "written_at": now(),
        "written_before_any_injection": True,
        "scenario_order": ["control", "kill", "storage", "saturation"],
        "positive_control_first": True,
        "predictions": PREDICTIONS,
        "note": (
            "Written by `make gameday GAMEDAY_ARGS='--scenario predict'` before anything was "
            "injected. The accept bar (§9/M6) is that at least one prediction is WRONG and "
            "investigated; nothing here is engineered to be wrong, and two of them "
            "deliberately contradict the M6 kickoff's own expectation."
        ),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


# --- scenario 0: the positive control ----------------------------------------


def scenario_control(args: argparse.Namespace) -> int:
    say("scenario 0 — POSITIVE CONTROL (delegated to scripts/alert_fire_drill.py)")
    record = RECORD_DIR / "control.json"
    result = subprocess.run(  # noqa: S603
        [
            "uv",
            "run",
            "python",
            "scripts/alert_fire_drill.py",
            "--record",
            str(record),
            "--prediction-record",
            str(RECORD_DIR / "control-prediction.json"),
            "--inject-seconds",
            str(args.control_seconds),
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    if result.returncode != 0:
        say("RED — the positive control did not fire; no negative result below is readable.")
        return 1
    payload = json.loads(record.read_text())
    fired = sorted(payload["observed"]["fired_at_s"])
    say(f"ok  the control fired {fired} and reached Alertmanager — negatives are now readable.")
    return 0


# --- scenario 1: kill the predictor under load --------------------------------


def scenario_kill(args: argparse.Namespace) -> int:
    from taxi_mlops.serving.client import Endpoint
    from taxi_mlops.serving.load import run_load

    say("scenario 1 — KILL THE PREDICTOR UNDER LOAD")
    problems = preflight()
    if problems:
        for problem in problems:
            say(f"FAIL: {problem}")
        return 1
    settle_record = settle()

    before = predictor_pod()
    alias_before = champion_version()
    say(f"    pod before: {before['name']} uid={before['uid']} · @champion {alias_before}")

    watcher = AlertWatcher()
    killed: dict[str, Any] = {}

    def on_second(elapsed: float) -> None:
        watcher.poll()
        if not killed and elapsed >= KILL_AT:
            killed["at_s"] = round(elapsed, 2)
            killed["pod"] = before["name"]
            say(f"    T+{elapsed:.1f}s  deleting pod {before['name']}")
            kubectl("-n", SERVING_NS, "delete", "pod", before["name"], "--wait=false")
            killed["deleted_at"] = now()

    endpoint = Endpoint(name="nyc-taxi-eta", namespace=SERVING_NS)
    with AlertmanagerForward() as am_port:
        result = run_load(
            endpoint,
            rate=KILL_RATE,
            seconds=KILL_SECONDS,
            concurrency=8,
            mix="hazards",
            label="m6-s5 gameday scenario 1 — kill under load",
            note="the prediction is on disk; the alerts are watched on the load client's clock",
            on_second=on_second,
        )
        say(f"    load done — watching the alerts for a further {args.kill_watch:.0f}s")
        watcher.watch(args.kill_watch)
        am = alertmanager_names(am_port)

    after = predictor_pod()
    alias_after = champion_version()
    load_record = result.as_record()
    errors = len(result.errors)

    # The outage, anchored the M5-S4 way (gotcha #75): first FAILURE -> first
    # SUCCESS after it. NOT last_error - first_error, which called a 13-second
    # outage 182 seconds once and was headed for a runbook.
    first_error = min((a.scheduled for a in result.errors), default=None)
    recovered = (
        min((a.scheduled for a in result.ok_attempts if a.scheduled > first_error), default=None)
        if first_error is not None
        else None
    )
    outage_seconds = (
        round(recovered - first_error, 2)
        if (first_error is not None and recovered is not None)
        else None
    )

    peak_share = prom_scalar(
        'max_over_time((sum(rate(nginx_ingress_controller_requests{namespace="serving",'
        'ingress="nyc-taxi-eta",status=~"5.."}[5m])) / '
        'sum(rate(nginx_ingress_controller_requests{namespace="serving",'
        'ingress="nyc-taxi-eta"}[5m])))[15m:15s])'
    )

    prediction = PREDICTIONS["kill"]
    checks: list[tuple[bool, str]] = [
        (bool(killed), f"the pod was deleted mid-load at T+{killed.get('at_s')}s"),
        (
            after["uid"] not in ("", before["uid"]),
            f"a DIFFERENT pod object served afterwards: uid {before['uid'][:8]}… -> "
            f"{after['uid'][:8]}… (identity, never name)",
        ),
        (
            outage_seconds is not None
            and prediction["quantities"]["expected_outage_seconds_between"][0]
            <= outage_seconds
            <= prediction["quantities"]["expected_outage_seconds_between"][1],
            f"the outage was {outage_seconds}s, inside the predicted "
            f"{prediction['quantities']['expected_outage_seconds_between']}",
        ),
        (
            peak_share < 0.10,
            f"the edge 5xx SHARE peaked at {peak_share:.4f}, below A-2's 0.10 bar "
            "(predicted: a single self-heal cannot reach it)",
        ),
        (
            not watcher.first_firing,
            f"NO alert fired: {sorted(watcher.first_firing) or 'none'} (predicted none)",
        ),
        (not am, f"Alertmanager holds nothing from this scenario: {am}"),
        (alias_after == alias_before, f"@champion unmoved: {alias_before} -> {alias_after}"),
    ]
    return finish(
        "kill",
        prediction,
        {
            "settle": settle_record,
            "pod_before": before,
            "pod_after": after,
            "kill": killed,
            "outage_seconds": outage_seconds,
            "error_count": errors,
            "edge_5xx_share_peak": peak_share,
            "alertmanager": am,
            "alias": {"before": alias_before, "after": alias_after},
            "load": load_record,
            "alerts": watcher.as_record(),
        },
        checks,
        args,
    )


# --- scenario 2: break the storage credential ---------------------------------


def scenario_storage(args: argparse.Namespace) -> int:
    say("scenario 2 — BREAK THE STORAGE CREDENTIAL, THEN DELETE THE POD")
    problems = preflight()
    if problems:
        for problem in problems:
            say(f"FAIL: {problem}")
        return 1
    settle_record = settle()

    # THE UNDO IS STAGED BEFORE THE INJECTION (the M2 red-team rule). The secret's
    # current bytes are captured here; `make serve` is the documented re-converge
    # and the captured copy is the belt to its braces.
    original = kubectl(
        "-n",
        SERVING_NS,
        "get",
        "secret",
        STORAGE_SECRET,
        "-o",
        "jsonpath={.data.AWS_SECRET_ACCESS_KEY}",
    )
    if not original:
        say("FAIL: could not read the secret to stage an undo — refusing to inject.")
        return 1
    # The captured bytes go to a temp file OUTSIDE the repo. `make serve` is the
    # documented undo and re-converges from `.env`; this copy is the belt to its
    # braces, and a credential must not be one `git add -f` away from a commit.
    backup_path = Path(tempfile.gettempdir()) / "m6s5-storage-secret-undo.b64"
    backup_path.write_text(original + "\n")
    backup_path.chmod(0o600)
    say(f"    undo staged: {len(original)} base64 chars captured outside the repo tree")

    before = predictor_pod()
    alias_before = champion_version()
    watcher = AlertWatcher()
    observed: dict[str, Any] = {"settle": settle_record, "pod_before": before}
    restored = False

    try:
        with AlertmanagerForward() as am_port:
            say("    injecting: AWS_SECRET_ACCESS_KEY -> a wrong value")
            kubectl(
                "-n",
                SERVING_NS,
                "patch",
                "secret",
                STORAGE_SECRET,
                "--type=merge",
                "-p",
                json.dumps({"data": {"AWS_SECRET_ACCESS_KEY": "d3JvbmctY3JlZGVudGlhbC1nYW1lZGF5"}}),
            )
            observed["injected_at"] = now()
            watcher.t0 = time.monotonic()
            say(f"    deleting pod {before['name']}")
            kubectl("-n", SERVING_NS, "delete", "pod", before["name"], "--wait=false")

            say(f"    watching for {args.storage_watch:.0f}s (A-5 at ~2m, A-7 at ~3m)")
            watcher.watch(args.storage_watch, poll=10.0)

            replacement = predictor_pod()
            # SCOPED TO THE CHAMPION'S PODS, and the scoping was added after the
            # first run recorded `1.0` here for a pod that had been in
            # Init:Error for three minutes. The rule itself is a per-SERIES
            # comparison and fired on the right pod; this field is a summary,
            # and `prom_scalar` takes the first result — which was the v1
            # SHADOW's storage-initializer, perfectly ready and entirely
            # irrelevant. A reader's field must not silently answer about a
            # different pod than the one under test.
            init_ready = prom_scalar(
                'kube_pod_init_container_status_ready{namespace="serving",'
                'container="storage-initializer",pod=~"nyc-taxi-eta-predictor.*"}',
                default=-1.0,
            )
            route_status, _ = http_get(SERVING_HOST, f"{ROUTE}/v2/models/nyc-taxi-eta")
            observed["replacement_pod"] = replacement
            observed["init_container_ready_metric"] = init_ready
            observed["route_status_while_broken"] = route_status
            observed["alertmanager"] = alertmanager_names(am_port)
    finally:
        say("    UNDO: re-converging the secret from .env via `make serve`")
        undo = subprocess.run(  # noqa: S603
            ["make", "serve"], cwd=REPO_ROOT, capture_output=True, text=True, check=False
        )
        observed["undo_exit_code"] = undo.returncode
        observed["undo_tail"] = undo.stdout.strip().splitlines()[-3:] if undo.stdout else []
        restored = undo.returncode == 0
        if not restored:
            say("    `make serve` did not return 0 — restoring the captured secret directly")
            kubectl(
                "-n",
                SERVING_NS,
                "patch",
                "secret",
                STORAGE_SECRET,
                "--type=merge",
                "-p",
                json.dumps({"data": {"AWS_SECRET_ACCESS_KEY": original}}),
            )
            kubectl("-n", SERVING_NS, "delete", "pod", predictor_pod()["name"], "--wait=false")
            kubectl(
                "-n",
                SERVING_NS,
                "rollout",
                "status",
                f"deploy/{PREDICTOR_DEPLOY}",
                "--timeout=300s",
            )
            restored = True

    say("    waiting for the alerts to clear")
    clear = AlertWatcher()
    clear.watch(args.clear_watch, poll=15.0)
    observed["after_undo_states"] = rule_states()
    observed["alerts"] = watcher.as_record()
    observed["clear_timeline"] = clear.timeline
    alias_after = champion_version()
    observed["alias"] = {"before": alias_before, "after": alias_after}

    fired = watcher.first_firing
    a5 = fired.get("PredictorNoAvailableReplica")
    a7 = fired.get("PredictorStorageInitializerNotReady")
    prediction = PREDICTIONS["storage"]
    checks = [
        (a5 is not None, f"A-5 PredictorNoAvailableReplica FIRED at T+{a5}s (predicted ~150s)"),
        (
            a7 is not None,
            f"A-7 PredictorStorageInitializerNotReady FIRED at T+{a7}s (predicted ~210s)",
        ),
        (
            a5 is not None and a7 is not None and a5 < a7,
            f"A-5 arrived BEFORE A-7 ({a5}s vs {a7}s) — the order the sustain windows imply, "
            "and the OPPOSITE of what A-7's own `why` annotation claims",
        ),
        (
            "ServingEdge5xxRateHigh" not in fired,
            "A-2 stayed inactive THROUGH A TOTAL OUTAGE — its documented blind spot, "
            "demonstrated (a ratio has no value when nobody is asking)",
        ),
        (
            "PredictorRestartFlapping" not in fired,
            "the flapping rule stayed inactive — it watches kserve-container, which never started",
        ),
        (restored, f"the staged undo worked: `make serve` exit {observed['undo_exit_code']}"),
        (
            http_get(SERVING_HOST, f"{ROUTE}/v2/models/nyc-taxi-eta")[0] == 200,
            "the endpoint answers again after the undo",
        ),
        (alias_after == alias_before, f"@champion unmoved: {alias_before} -> {alias_after}"),
    ]
    return finish("storage", prediction, observed, checks, args)


# --- scenario 3: saturate the CPU ---------------------------------------------


def scenario_saturation(args: argparse.Namespace) -> int:
    from taxi_mlops.serving.client import Endpoint
    from taxi_mlops.serving.load import run_load

    say("scenario 3 — SATURATE THE CPU")
    problems = preflight()
    if problems:
        for problem in problems:
            say(f"FAIL: {problem}")
        return 1
    settle_record = settle()

    throttle_expr = (
        'sum(rate(container_cpu_cfs_throttled_periods_total{namespace="serving",'
        'container="kserve-container",pod=~"nyc-taxi-eta-predictor.*"}[5m])) / '
        'sum(rate(container_cpu_cfs_periods_total{namespace="serving",'
        'container="kserve-container",pod=~"nyc-taxi-eta-predictor.*"}[5m]))'
    )
    before_throttle = prom_scalar(throttle_expr, default=-1.0)
    before_pod = predictor_pod()
    watcher = AlertWatcher()
    samples: list[dict[str, Any]] = []

    def on_second(elapsed: float) -> None:
        if int(elapsed) % 15 == 0:
            watcher.poll()
        if int(elapsed) % 60 == 0 and elapsed > 0:
            with contextlib.suppress(Exception):  # a sample is evidence, not the drill
                samples.append(
                    {
                        "t_plus_s": round(elapsed),
                        "throttled_fraction": prom_scalar(throttle_expr, -1.0),
                    }
                )

    endpoint = Endpoint(name="nyc-taxi-eta", namespace=SERVING_NS)
    with AlertmanagerForward() as am_port:
        result = run_load(
            endpoint,
            rate=SATURATION_RATE,
            seconds=SATURATION_SECONDS,
            concurrency=16,
            mix="hazards",
            label="m6-s5 gameday scenario 3 — saturation",
            note="past the measured ceiling; the prediction is throttling with zero errors",
            on_second=on_second,
        )
        watcher.poll()
        am = alertmanager_names(am_port)

    after_throttle = prom_scalar(throttle_expr, default=-1.0)
    after_pod = predictor_pod()
    load_record = result.as_record()
    percentiles = result.percentiles()
    prediction = PREDICTIONS["saturation"]
    fired = watcher.first_firing

    checks = [
        (
            "PredictorCpuThrottledSustained" in fired,
            "A-6 PredictorCpuThrottledSustained FIRED at "
            f"T+{fired.get('PredictorCpuThrottledSustained')}s (predicted after its 10m sustain)",
        ),
        (
            len(result.errors) == 0,
            f"ZERO errors across {len(result.attempts)} requests — saturation shows up as "
            "latency, never as failure (gotcha #74)",
        ),
        (
            after_throttle > prediction["quantities"]["expected_throttled_fraction_above"],
            f"the throttled fraction reached {after_throttle:.4f} > "
            f"{prediction['quantities']['expected_throttled_fraction_above']} (was "
            f"{before_throttle:.4f} before)",
        ),
        (
            "ServingEdge5xxRateHigh" not in fired,
            "A-2 stayed inactive — there were no errors to count",
        ),
        (
            "PredictorNoAvailableReplica" not in fired and after_pod["uid"] == before_pod["uid"],
            "the pod was never replaced and A-5 stayed inactive — a saturated service is UP",
        ),
        (
            "PredictorStorageInitializerNotReady" not in fired,
            "A-7 stayed inactive — distinguishable from scenario 2",
        ),
    ]
    return finish(
        "saturation",
        prediction,
        {
            "settle": settle_record,
            "throttled_fraction": {"before": before_throttle, "after": after_throttle},
            "throttle_samples": samples,
            "percentiles_ms": percentiles,
            "error_count": len(result.errors),
            "pod": {"before": before_pod, "after": after_pod},
            "alertmanager": am,
            "alerts": watcher.as_record(),
            "load": load_record,
        },
        checks,
        args,
    )


# --- the verdict --------------------------------------------------------------


def finish(
    name: str,
    prediction: dict[str, Any],
    observed: dict[str, Any],
    checks: list[tuple[bool, str]],
    args: argparse.Namespace,
) -> int:
    print()
    failures = [text for good, text in checks if not good]
    for good, text in checks:
        say(("ok  " if good else "FAIL ") + text)
    payload = {
        "story": "M6-S5",
        "scenario": name,
        "measured_at": now(),
        "prediction": prediction,
        "observed": observed,
        "checks": [{"passed": good, "check": text} for good, text in checks],
        "verdict": "AS PREDICTED" if not failures else "PREDICTION WRONG",
        "note": (
            "A FAILED check here does not mean the system misbehaved — it means the "
            "PREDICTION was wrong, which is what §9/M6 grades this gameday on. Read the "
            "check text, then the scenario's section in docs/gameday_m6.md."
        ),
    }
    record = RECORD_DIR / f"{name}.json"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps(payload, indent=2) + "\n")
    say(f"record -> {record}")
    if failures:
        say(f"{len(failures)} prediction(s) WRONG — investigate, do not edit the prediction.")
        return 0 if args.tolerate_wrong else 1
    say(f"every prediction held: {len(checks)} check(s).")
    return 0


def scenario_report(args: argparse.Namespace) -> int:
    """Assemble one record from the four, and state the accept bar's verdict."""
    scenarios = ["control", "kill", "storage", "saturation"]
    parts: dict[str, Any] = {}
    for name in scenarios:
        path = RECORD_DIR / f"{name}.json"
        parts[name] = json.loads(path.read_text()) if path.exists() else None
    wrong: list[str] = []
    for name, part in parts.items():
        if part is None:
            continue
        failed = [c["check"] for c in part.get("checks", []) if not c["passed"]]
        if failed:
            wrong.append(f"{name}: {failed}")
    payload = {
        "story": "M6-S5",
        "assembled_at": now(),
        "scenario_order": scenarios,
        "positive_control_first": True,
        "scenarios_present": {k: v is not None for k, v in parts.items()},
        "predictions_that_were_wrong": wrong,
        "accept_bar": (
            "§9/M6: at least one prediction wrong and investigated. A gameday with every "
            "prediction right was too easy."
        ),
        "accept_bar_met": bool(wrong),
    }
    path = RECORD_DIR / "gameday.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
    say(f"assembled -> {path}")
    for line in wrong:
        say(f"    WRONG PREDICTION: {line}")
    say(f"accept bar met (>=1 wrong prediction): {payload['accept_bar_met']}")
    return 0


SCENARIOS = {
    "control": scenario_control,
    "kill": scenario_kill,
    "storage": scenario_storage,
    "saturation": scenario_saturation,
    "report": scenario_report,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        default="all",
        choices=["all", "predict", *SCENARIOS],
        help="which scenario to run; 'predict' writes the predictions and stops",
    )
    parser.add_argument("--control-seconds", type=float, default=420.0)
    parser.add_argument("--kill-watch", type=float, default=330.0)
    parser.add_argument("--storage-watch", type=float, default=330.0)
    parser.add_argument("--clear-watch", type=float, default=180.0)
    parser.add_argument(
        "--tolerate-wrong",
        action="store_true",
        default=True,
        help="a wrong prediction exits 0 (it is the accept bar, not a failure)",
    )
    args = parser.parse_args(argv)

    predictions_path = RECORD_DIR / "predictions.json"
    if args.scenario in ("all", "predict") or not predictions_path.exists():
        write_predictions(predictions_path)
        say(f"predictions written BEFORE any injection -> {predictions_path}")
        for name, entry in PREDICTIONS.items():
            say(f"    {name}: fires={entry['must_fire'] or 'NOTHING'}")
    if args.scenario == "predict":
        return 0

    order = ["control", "kill", "storage", "saturation", "report"]
    todo = order if args.scenario == "all" else [args.scenario]
    for name in todo:
        code = SCENARIOS[name](args)
        if code != 0:
            say(f"scenario {name} returned {code} — stopping.")
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
