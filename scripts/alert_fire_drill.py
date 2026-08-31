#!/usr/bin/env python
"""Fire real alerts against the live stack, with the prediction written FIRST.

M6-S2, behind `make alert-fire-drill`. The M6 kickoff asks for "at least one
alert FIRED in a red team, observed end to end" with a
**prediction-before-firing**: which alert, at what threshold, expected to fire in
what window, written down BEFORE the injection. That is the gameday shape
rehearsed small, and it is the same discipline as M4-S5's kill drill and M5-S4's
self-heal drill — both of which wrote their prediction to disk before touching
anything, and one of which was WRONG and is kept unedited because of it.

WHAT IT INJECTS, AND WHY THAT IS NOT SYNTHETIC.
Two request shapes, both of which this endpoint answers today and both of which
are real failure modes with a ledger row behind them:

  * a **malformed V2 body** -> HTTP 422. This is F-030's class exactly: for a
    whole milestone ~1% of riders (every trip touching a zone with no centroid)
    got a 422 because the client serialised `NaN`, and no instrument said so.
  * a **valid V2 body the model's logged signature refuses** -> HTTP 500. This
    is F-032's class exactly: the half-finished rollback. `@champion` v2 eats 24
    features and v1 eats 5, so moving the alias without moving
    `configs/train.yaml` puts a 24-feature stream in front of a 5-feature model
    and every rider gets a 500 while every condition still reads `Ready`.

So the injection does not manufacture an error the system cannot produce; it
provokes two the system produces for real, from the client side, over the same
route a rider uses.

WHY BOTH AT ONCE, AND WHY THAT IS THE STRONGER TEST.
A-3 (rejections, `for: 2m`) and A-2 (edge 5xx, `for: 5m`) have different sustain
windows, so ONE injection carrying both classes must fire them **in a predicted
order with a predicted gap**. A drill that predicts only "something will fire"
is satisfied by almost any behaviour; one that predicts a sequence can be wrong
about the sequence. The prediction also includes the alerts that must **NOT**
fire (A-1, A-5, A-6, A-7) — distinguishable signatures, which is the property
S5's gameday is graded on and is cheap to rehearse here.

WHAT IT DOES NOT TOUCH. No pod is deleted, no deployment is edited, no manifest
is applied, no alias is read for anything but the record and never written. The
service stays up throughout and answers ordinary quotes the whole time; the only
cost is error budget deliberately spent (~7 minutes of failing requests at a low
rate, which §4 of docs/slo_serving.md prices).

Usage:
    make alert-fire-drill
    make alert-fire-drill DRILL_ARGS="--inject-seconds 420 --rate 4"
    make alert-fire-drill DRILL_ARGS="--dry-run"     # preflight + prediction only
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RECORD_DIR = REPO_ROOT / "automation" / "runs" / "m6-slo"

# This file is executed directly and is also loaded by the suite through
# `spec_from_file_location`, which puts nothing on sys.path — so it declares
# where its libraries live, exactly as its neighbours declare `src`.
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from _lib import ports  # noqa: E402
from _lib.k8s import start_forward, stop_forward  # noqa: E402
from _lib.monitoring import alertmanager_alerts, http_get, prom_rules  # noqa: E402

ROUTE = "http://localhost:8081"
PROM_HOST = "prometheus.local"
INFER_PATH = "/v2/models/nyc-taxi-eta/infer"
SERVING_HOST = "nyc-taxi-eta-serving.local"

# An EPHEMERAL local port for the Alertmanager forward, torn down on exit. It is
# deliberately NOT in CLAUDE.md's port family: the family lists ports this
# program DECLARES, and a forward that exists for four minutes inside one drill
# is not a declared route (the `make flyte-actions` precedent, which uses 8092
# for the same reason). The NUMBER lives in `_lib.ports`, which is the only
# place the whole set is visible — see that module for the collision that
# coordination-by-comment could not see.
ALERTMANAGER_LOCAL_PORT = ports.port("ALERTMANAGER_ALERT_DRILL")

# The two injected shapes. Neither is invented — see the module docstring.
MALFORMED_BODY: dict[str, Any] = {
    "inputs": [{"name": "hour", "shape": [1, 1], "datatype": "NOT-A-DATATYPE", "data": [9]}]
}
SIGNATURE_REFUSED_BODY: dict[str, Any] = {
    "inputs": [{"name": "hour", "shape": [1, 1], "datatype": "INT16", "data": [9]}]
}


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def say(msg: str) -> None:
    print(f"[alert-drill] {msg}", flush=True)


# --- readers ---------------------------------------------------------------
# `http_get`, `prom_rules` and `alertmanager_alerts` moved to `_lib.monitoring`
# at CU-S4; they were byte-identical here, in the drift fire drill and in the
# gameday. What stayed is everything below that READS an answer for this drill.


def served_version() -> str | None:
    """Read the alias the endpoint reports. A READ — this drill never writes one."""
    try:
        status, body = http_get(SERVING_HOST, f"{ROUTE}/v2/models/nyc-taxi-eta")
        if status == 200:
            return json.loads(body).get("versions") or "reported-empty"
    except Exception:  # noqa: BLE001 — a failed read is recorded, not fatal
        return None
    return None


# --- the injector -------------------------------------------------------------


class Injector:
    """Posts failing requests at a stated rate until told to stop.

    OPEN LOOP, the M5-S4 rule: the next request is due at `t0 + k/rate`
    regardless of whether the last one returned. A closed loop would make the
    injected rate a consequence of the server's latency, which is the thing
    coordinated omission means.
    """

    def __init__(self, rate: float) -> None:
        self.rate = rate
        self.stop = threading.Event()
        self.counts: dict[str, int] = {}
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _post(self, body: dict[str, Any]) -> str:
        data = json.dumps(body).encode()
        request = urllib.request.Request(  # noqa: S310
            f"{ROUTE}{INFER_PATH}",
            data=data,
            headers={"Content-Type": "application/json", "Host": SERVING_HOST},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310
                return str(response.status)
        except urllib.error.HTTPError as error:
            return str(error.code)
        except Exception as error:  # noqa: BLE001
            return type(error).__name__

    def _run(self) -> None:
        start = time.monotonic()
        k = 0
        while not self.stop.is_set():
            due = start + k / self.rate
            delay = due - time.monotonic()
            if delay > 0 and self.stop.wait(delay):
                return
            body = MALFORMED_BODY if k % 2 == 0 else SIGNATURE_REFUSED_BODY
            code = self._post(body)
            self.counts[code] = self.counts.get(code, 0) + 1
            k += 1

    def start(self) -> None:
        self.thread.start()

    def halt(self) -> None:
        self.stop.set()
        self.thread.join(timeout=30)


# --- the drill ----------------------------------------------------------------

# What the drill claims will happen. WRITTEN TO DISK BEFORE THE INJECTION STARTS.
# `expected_fire_after_s` is derived, not guessed: the expression becomes true
# within about one scrape interval (15 s) plus one evaluation (15 s) of the
# injection starting, and the rule then has to hold for its own `for:` window.
PREDICTION = {
    "must_fire": [
        {
            "alert": "PredictorRequestRejectionRateHigh",
            "signal": "A-3",
            "for_seconds": 120,
            "expected_fire_after_s": 150,
            "why": (
                "half the injected requests are malformed bodies answered 422, so the 4xx "
                "share of infers goes to ~0.5 against a 0.01 bar within one scrape; the "
                "rule then holds for its 2m sustain."
            ),
        },
        {
            "alert": "ServingEdge5xxRateHigh",
            "signal": "A-2",
            "for_seconds": 300,
            "expected_fire_after_s": 330,
            "why": (
                "the other half are bodies the model's logged signature refuses, answered "
                "500 and counted at the EDGE by ingress-nginx; the 5xx share goes to ~0.5 "
                "against a 0.10 bar, then holds for its 5m sustain."
            ),
        },
    ],
    "must_fire_in_this_order": ["PredictorRequestRejectionRateHigh", "ServingEdge5xxRateHigh"],
    "must_not_fire": [
        {
            "alert": "PredictorLatencySLOBurning",
            "signal": "A-1",
            "why": "it selects status_code=\"200\" only; a rejected request is not a slow one.",
        },
        {
            "alert": "PredictorNoAvailableReplica",
            "signal": "A-5",
            "why": "nothing is deleted or scaled; the replica stays available throughout.",
        },
        {
            "alert": "PredictorRestartFlapping",
            "signal": "A-5",
            "why": "a rejected request does not restart a container.",
        },
        {
            "alert": "PredictorCpuThrottledSustained",
            "signal": "A-6",
            "why": (
                "a 422 is refused before the model runs and a signature refusal is cheap; "
                "neither approaches the CPU ceiling at this rate."
            ),
        },
        {
            "alert": "PredictorStorageInitializerNotReady",
            "signal": "A-7",
            "why": "the pod is already initialised and is not being replaced.",
        },
    ],
    "must_clear_after_injection_stops": True,
    "the_service_stays_up": (
        "an ordinary quote must still succeed during the injection — this drill provokes "
        "errors, it does not cause an outage."
    ),
}


def preflight(rule_names: set[str]) -> list[str]:
    problems: list[str] = []
    rules = prom_rules(PROM_HOST, ROUTE)
    for name in sorted(rule_names):
        rule = rules.get(name)
        if rule is None:
            problems.append(f"rule {name} is not loaded in Prometheus")
        elif rule["state"] != "inactive":
            problems.append(
                f"rule {name} is already {rule['state']} — the drill would prove nothing"
            )
        elif rule["health"] != "ok":
            problems.append(f"rule {name} health is {rule['health']}")
    return problems


def poll_states(rule_names: set[str]) -> dict[str, str]:
    rules = prom_rules(PROM_HOST, ROUTE)
    return {name: rules.get(name, {}).get("state", "absent") for name in rule_names}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rate", type=float, default=4.0, help="injected requests per second")
    parser.add_argument(
        "--inject-seconds",
        type=float,
        default=420.0,
        help="how long to inject; must exceed the longest `for:` under test plus a scrape",
    )
    parser.add_argument(
        "--clear-timeout",
        type=float,
        default=480.0,
        help="how long to wait for every fired alert to go back to inactive",
    )
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument(
        "--dry-run", action="store_true", help="preflight + prediction, no injection"
    )
    parser.add_argument("--record", default=str(RECORD_DIR / "alert-fire-drill.json"))
    parser.add_argument(
        "--prediction-record", default=str(RECORD_DIR / "alert-fire-prediction.json")
    )
    args = parser.parse_args(argv)

    must_fire = [entry["alert"] for entry in PREDICTION["must_fire"]]
    must_not_fire = [entry["alert"] for entry in PREDICTION["must_not_fire"]]
    watched = set(must_fire) | set(must_not_fire)

    print("== alert fire drill (M6-S2) ==")
    print(f"route {ROUTE} · prometheus host {PROM_HOST}\n")

    # --- phase 0: preflight ---------------------------------------------------
    say("phase 0 — preflight: every watched rule loaded, healthy and INACTIVE")
    problems = preflight(watched)
    if problems:
        for problem in problems:
            say(f"FAIL: {problem}")
        return 1
    say(f"ok  {len(watched)} rule(s) loaded, healthy, inactive")

    version = served_version()
    say(f"ok  the endpoint answers; served version metadata: {version!r} (read, never written)")

    # --- phase 1: the prediction, ON DISK, BEFORE the injection ---------------
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    prediction_payload = {
        "story": "M6-S2",
        "written_at": now(),
        "written_before_injection": True,
        "injection": {
            "rate_per_second": args.rate,
            "seconds": args.inject_seconds,
            "shapes": ["malformed V2 body -> 422", "signature-refused body -> 500"],
        },
        "prediction": PREDICTION,
    }
    Path(args.prediction_record).write_text(json.dumps(prediction_payload, indent=2) + "\n")
    say(f"phase 1 — prediction written BEFORE anything was injected -> {args.prediction_record}")
    for entry in PREDICTION["must_fire"]:
        say(
            f"    PREDICT {entry['signal']} {entry['alert']} FIRES at about "
            f"T+{entry['expected_fire_after_s']}s (for={entry['for_seconds']}s)"
        )
    say(f"    PREDICT the order is {' then '.join(PREDICTION['must_fire_in_this_order'])}")
    for entry in PREDICTION["must_not_fire"]:
        say(f"    PREDICT {entry['signal']} {entry['alert']} stays INACTIVE")

    if args.dry_run:
        say("--dry-run — preflight passed and the prediction is on disk; nothing was injected.")
        return 0

    # --- phase 2: the Alertmanager forward ------------------------------------
    say(f"phase 2 — forwarding Alertmanager to localhost:{ALERTMANAGER_LOCAL_PORT} (ephemeral)")
    forward = start_forward(
        "svc/prometheus-alertmanager", "monitoring", ALERTMANAGER_LOCAL_PORT, 9093
    )

    timeline: list[dict[str, Any]] = []
    fired_at: dict[str, float] = {}
    pending_at: dict[str, float] = {}
    ever_fired: set[str] = set()
    quote_during_injection: dict[str, Any] = {}

    try:
        # --- phase 3: inject ---------------------------------------------------
        say(f"phase 3 — injecting {args.rate} req/s of failing requests for {args.inject_seconds}s")
        injector = Injector(args.rate)
        t0 = time.monotonic()
        injector.start()

        last_states: dict[str, str] = dict.fromkeys(watched, "inactive")
        healthy_quote_checked = False
        while time.monotonic() - t0 < args.inject_seconds:
            time.sleep(args.poll_seconds)
            elapsed = round(time.monotonic() - t0, 1)
            states = poll_states(watched)
            for name, state in sorted(states.items()):
                if state != last_states.get(name):
                    timeline.append({"t_plus_s": elapsed, "alert": name, "state": state})
                    say(f"    T+{elapsed:6.1f}s  {name} -> {state}")
                    if state == "pending" and name not in pending_at:
                        pending_at[name] = elapsed
                    if state == "firing" and name not in fired_at:
                        fired_at[name] = elapsed
                        ever_fired.add(name)
                    last_states[name] = state

            # One ordinary quote mid-injection: the drill claims the service stays
            # up, and a claim nobody checked is a claim (gotcha #59).
            if not healthy_quote_checked and elapsed > 30:
                healthy_quote_checked = True
                result = subprocess.run(  # noqa: S603
                    [
                        "uv",
                        "run",
                        "python",
                        "-m",
                        "taxi_mlops.serving",
                        "--at",
                        "2019-07-04T09:15:00",
                        "--pu",
                        "132",
                        "--do",
                        "48",
                    ],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                )
                quote_during_injection = {
                    "exit_code": result.returncode,
                    "stdout": result.stdout.strip().splitlines()[-1] if result.stdout else "",
                }
                verdict = "ok " if result.returncode == 0 else "FAIL"
                tail = quote_during_injection["stdout"]
                say(f"    {verdict} an ordinary quote DURING the injection: {tail}")

            if all(name in fired_at for name in must_fire) and elapsed > 60:
                say(
                    f"    every predicted alert has fired at T+{elapsed}s — "
                    "stopping the injection early"
                )
                break

        injector.halt()
        injected = dict(sorted(injector.counts.items()))
        say(f"phase 3 done — injected responses by status: {injected}")

        # --- phase 4: alertmanager received it --------------------------------
        say("phase 4 — did the alert reach Alertmanager, or only Prometheus's own UI?")
        am = alertmanager_alerts(ALERTMANAGER_LOCAL_PORT)
        am_names = sorted({a["labels"].get("alertname", "?") for a in am})
        say(f"    Alertmanager holds {len(am)} alert(s): {am_names}")
        am_received = [name for name in must_fire if name in am_names]

        # --- phase 5: it clears -----------------------------------------------
        say(
            f"phase 5 — injection stopped; waiting up to {args.clear_timeout}s "
            "for a return to inactive"
        )
        cleared_at: dict[str, float] = {}
        t1 = time.monotonic()
        while time.monotonic() - t1 < args.clear_timeout:
            states = poll_states(watched)
            elapsed = round(time.monotonic() - t1, 1)
            for name in sorted(ever_fired):
                if states.get(name) == "inactive" and name not in cleared_at:
                    cleared_at[name] = elapsed
                    say(f"    T+{elapsed:6.1f}s after stop  {name} -> inactive")
            if all(name in cleared_at for name in ever_fired):
                break
            time.sleep(args.poll_seconds)
    finally:
        stop_forward(forward)

    # --- the verdict ----------------------------------------------------------
    print()
    checks: list[tuple[bool, str]] = []
    for entry in PREDICTION["must_fire"]:
        name = entry["alert"]
        checks.append((name in fired_at, f"{entry['signal']} {name} FIRED (predicted it would)"))
    order_observed = [n for n, _ in sorted(fired_at.items(), key=lambda kv: kv[1])]
    checks.append(
        (
            order_observed == PREDICTION["must_fire_in_this_order"],
            f"the firing order was the predicted one: {order_observed}",
        )
    )
    for entry in PREDICTION["must_not_fire"]:
        name = entry["alert"]
        checks.append(
            (name not in ever_fired, f"{entry['signal']} {name} stayed inactive (predicted)")
        )
    checks.append(
        (
            sorted(am_received) == sorted(must_fire),
            f"Alertmanager received every fired alert: {am_received}",
        )
    )
    checks.append(
        (
            quote_during_injection.get("exit_code") == 0,
            "an ordinary quote succeeded DURING the injection — errors, not an outage",
        )
    )
    checks.append(
        (
            sorted(cleared_at) == sorted(ever_fired) and bool(ever_fired),
            "every fired alert returned to inactive after the injection stopped: "
            f"{sorted(cleared_at)}",
        )
    )

    failures = [text for good, text in checks if not good]
    for good, text in checks:
        say(("ok  " if good else "FAIL ") + text)

    payload = {
        "story": "M6-S2",
        "measured_at": now(),
        "injection": {
            "rate_per_second": args.rate,
            "seconds_requested": args.inject_seconds,
            "responses_by_status": injected,
        },
        "prediction": PREDICTION,
        "observed": {
            "pending_at_s": pending_at,
            "fired_at_s": fired_at,
            "firing_order": order_observed,
            "cleared_after_stop_s": cleared_at,
            "never_fired": sorted(set(must_not_fire) - ever_fired),
            "alertmanager_received": am_received,
            "quote_during_injection": quote_during_injection,
            "timeline": timeline,
        },
        "checks": [{"passed": good, "check": text} for good, text in checks],
        "verdict": "GREEN" if not failures else "RED",
        "note": (
            "The prediction in this file is byte-identical to the one written to "
            "alert-fire-prediction.json BEFORE the injection began — it is carried here so a "
            "reader has predicted and observed side by side."
        ),
    }
    Path(args.record).write_text(json.dumps(payload, indent=2) + "\n")
    say(f"record -> {args.record}")

    if failures:
        say(f"RED — {len(failures)} check(s) failed.")
        return 1
    say(f"GREEN — {len(checks)} check(s) passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
