#!/usr/bin/env python
"""F-050's pair, proved: the store survives a pod, and its ABSENCE is a page.

M8-S1 leg 1. Two claims, and each is worth little without the other:

  (a) the pushgateway now writes to a PersistentVolume, so the event that
      actually recurs on this machine — a host restart taking the pod with it —
      no longer empties the drift board;
  (b) A-11 (`absent(taxi_drift_last_run_timestamp_seconds{job="taxi-drift"})`)
      fires when the series are gone, which A-10 is structurally unable to do:
      `time() - max by (month) (X)` over zero series is zero series, not a large
      number.

WHY THIS DRILL EXISTS AT ALL, RATHER THAN A SENTENCE IN A VALUES FILE
----------------------------------------------------------------------
A PVC that is mounted but never written to looks exactly like working
persistence right up to the moment it is needed — pushgateway keeps its metrics
in memory unless `--persistence.file` names one, and the chart mounts the volume
either way. So the only honest test is to destroy the pod and read the series
back. Likewise A-11: a rule that selects a label nobody sets sits `inactive`
forever and is indistinguishable from a healthy system (gotcha #92), so it has
to be watched firing.

THE PREDICTION IS WRITTEN FIRST AND IS COMMITTED
-------------------------------------------------
`PREDICTION` lands on disk before the first mutation, and a unit test asserts
the committed copy still equals this object — so amending a prediction to match
an outcome is a RED test, not a diff nobody reads (M6-S5's gameday discipline,
inherited). The negative predictions are the load-bearing half: A-10 must stay
inactive through the wipe (its blind spot, demonstrated rather than asserted)
and A-11 must be inactive before it.

WHAT THIS DRILL DELIBERATELY DOES NOT DO
-----------------------------------------
It touches no InferenceService, moves no alias, fits nothing and injects no
fault at the endpoint. Its one destructive act is deleting the drift SERIES —
and it ends by pushing the real 2020 numbers back, because the board must end
carrying the truth (M7-S3's rule: March 2020 really did lose 61% of its trips,
and latching that off to tidy a transcript would be publishing a false board).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from _lib import ports  # noqa: E402
from _lib.k8s import kubectl, start_forward, stop_forward  # noqa: E402
from _lib.monitoring import (  # noqa: E402
    alertmanager_holds,
    firing_labels,
    http_get,
    prom_query,
    prom_rules,
)
from _lib.monitoring import rule_state as _rule_state  # noqa: E402

from taxi_mlops.monitoring.__main__ import PUSH_JOB, build_metrics  # noqa: E402
from taxi_mlops.monitoring.drift import compute_drift  # noqa: E402
from taxi_mlops.monitoring.pushgateway import (  # noqa: E402
    SERVICE_NAME,
    delete_group,
    push_metrics,
)

RECORD_DIR = REPO_ROOT / "automation" / "runs" / "m8-drift"
ROUTE = "http://localhost:8081"
PROM_HOST = "prometheus.local"
NAMESPACE = "monitoring"
POD_SELECTOR = "app.kubernetes.io/name=prometheus-pushgateway"

#: Ephemeral forwards, torn down on exit, and deliberately NOT 9096/9097: those
#: are `drift_fire_drill.py`'s, and a drill that steals a running drill's port
#: is a drill that fails for its own reasons (#55).
PUSHGATEWAY_LOCAL_PORT = ports.port("PUSHGATEWAY_PERSISTENCE_DRILL")
ALERTMANAGER_LOCAL_PORT = ports.port("ALERTMANAGER_PERSISTENCE_DRILL")

MONTHS = ("2020-01", "2020-02", "2020-03")

ABSENCE_ALERT = "DriftMetricsAbsent"
STALE_ALERT = "DriftMetricsStale"
VOLUME_ALERT = "ScoringVolumeCollapse"

#: A PURE LITERAL, deliberately: `tests/unit/test_slo_and_alerts.py` reads every
#: drill's prediction with `ast.literal_eval` rather than by importing it, so a
#: coverage test can never be satisfied by a module with a side effect. Alert
#: names are spelled out here even though constants for them exist above.
PREDICTION: dict[str, Any] = {
    "written_before": "the gateway's pod is deleted and before any series is wiped",
    "pair_decided_at": "the M7->M8 boundary (F-050 (a)+(b) together)",
    "survival": {
        "claim": (
            "deleting the pushgateway pod destroys the pod and NOT the data: the same "
            "number of taxi_drift_* samples is readable from a different pod object."
        ),
        "confidence": "high",
        "because": (
            "persistentVolume.enabled plus --persistence.file=/data/pushgateway.data, "
            "checkpointed every 10s, and pushgateway also writes on a clean SIGTERM. "
            "Before this story the same delete emptied the store completely — that is "
            "F-050, measured three times on host restarts."
        ),
        "expected_restart_seconds_below": 180,
    },
    "absence": {
        "must_fire": {
            "alert": "DriftMetricsAbsent",
            "signal": "A-11",
            "confidence": "high",
            "after_about_seconds": 600,
            "because": (
                "the rule has for: 10m and the wipe removes every series the selector "
                "names, so `absent(...)` becomes 1 within a scrape interval and stays."
            ),
            "must_reach_alertmanager": True,
        },
        "must_not_fire": [
            {
                "alert": "DriftMetricsStale",
                "signal": "A-10",
                "because": (
                    "THIS IS THE POINT OF A-11. A-10 reads `time() - max by (month)(stamp)`, "
                    "and over zero series that expression has no value — so the rule stays "
                    "inactive through a total loss of the drift surface. If A-10 fires here, "
                    "A-11 is redundant and the finding was wrong."
                ),
            },
            {
                "alert": "ScoringVolumeCollapse",
                "signal": "A-9",
                "because": (
                    "no volume series exists during the wipe, so A-9 has nothing to compare. "
                    "An empty board renders exactly like a calm one — restated as a "
                    "prediction because it is the failure this pair exists to end."
                ),
            },
        ],
    },
    "clearing": {
        "claim": (
            "re-pushing the real 2020 numbers clears A-11 within a scrape interval, and "
            "A-9 returns for 2020-03 only — the board ends carrying the truth, not a "
            "convenient silence."
        ),
        "confidence": "high",
        "volume_ratios_about": {"2020-01": 0.83, "2020-02": 0.88, "2020-03": 0.39},
    },
    "not_touched": [
        "@champion (read, never written)",
        "the InferenceService and the wire",
        "every threshold in infra/monitoring/alerting_rules.yml",
        "the settled data pins",
    ],
}


def say(msg: str) -> None:
    print(f"[persistence-drill] {msg}", flush=True)


# --- readers ---------------------------------------------------------------
# The bodies moved to `_lib.monitoring` at CU-S4. These two wrappers stay
# because every caller below sits inside a `wait_for` poll: they must RE-READ
# the rules on each call, so binding a rules dict once would silently freeze a
# drill that exists to watch a state change.


def rule_state(alert: str) -> str:
    return _rule_state(prom_rules(PROM_HOST, ROUTE), alert)


def firing_months(alert: str) -> set[str]:
    return firing_labels(prom_rules(PROM_HOST, ROUTE), alert, "month")


def gateway_samples(port: int) -> int:
    """How many taxi_drift_* samples the GATEWAY itself holds — read off /metrics.

    Asked of the gateway and not of Prometheus, deliberately: Prometheus keeps a
    scraped sample for minutes after its source disappears, so a survival check
    that queried Prometheus would pass on a gateway that lost everything.
    """
    status, body = http_get("localhost", f"http://localhost:{port}/metrics", timeout=15)
    if status != 200:
        return -1
    return sum(
        1
        for line in body.splitlines()
        if line.startswith("taxi_drift_") and not line.startswith("#")
    )


def gateway_pod() -> tuple[str, str, bool]:
    """(name, uid, ready). Identity is the UID — a pod can come back under its
    own name with a different object behind it (M4-S5's lesson)."""
    payload = json.loads(
        kubectl("get", "pod", "-l", POD_SELECTOR, "-o", "json") or '{"items": []}'
    )
    items = payload.get("items") or []
    if not items:
        return "", "", False
    pod = items[0]
    ready = all(
        c.get("status") == "True"
        for c in pod.get("status", {}).get("conditions", [])
        if c.get("type") == "Ready"
    ) and bool(pod.get("status", {}).get("conditions"))
    return pod["metadata"]["name"], pod["metadata"]["uid"], ready


def push_real_months(port: int, reports: dict[str, Any] | None = None) -> dict[str, float]:
    """Push the three real scoring months. Computes them if not handed in."""
    ratios: dict[str, float] = {}
    for month in MONTHS:
        report = (reports or {}).get(month) or compute_drift(month)
        (reports if reports is not None else {})[month] = report
        push_metrics(
            build_metrics(report),
            url=f"http://localhost:{port}",
            job=PUSH_JOB,
            grouping={"month": report.month},
        )
        ratios[month] = float(report.volume_ratio)
        say(f"  pushed {month}: volume ratio {report.volume_ratio:.4f}")
    return ratios


def wait_for(predicate, timeout: float, poll: float = 10.0) -> tuple[bool, float]:
    start = time.time()
    while time.time() - start < timeout:
        try:
            if predicate():
                return True, time.time() - start
        except Exception as error:  # noqa: BLE001
            say(f"  (poll error, retrying: {error})")
        time.sleep(poll)
    return False, time.time() - start


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="write the prediction, delete nothing, push nothing",
    )
    parser.add_argument(
        "--absence-timeout",
        type=int,
        default=900,
        help="seconds to wait for A-11 (its sustain is 10m)",
    )
    args = parser.parse_args(argv)

    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    prediction_path = RECORD_DIR / "persistence-prediction.json"
    prediction_path.write_text(json.dumps(PREDICTION, indent=2, sort_keys=True) + "\n")
    say(f"prediction written FIRST -> {prediction_path.relative_to(REPO_ROOT)}")
    if args.dry_run:
        say("--dry-run: nothing was deleted, nothing was pushed.")
        return 0

    record: dict[str, Any] = {
        "story": "M8-S1 leg 1",
        "finding": "F-050 (a)+(b)",
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "prediction": PREDICTION,
        "checks": [],
    }
    failures: list[str] = []

    def check(passed: bool, message: str) -> None:
        record["checks"].append({"ok": bool(passed), "message": message})
        say(("ok   " if passed else "FAIL ") + message)
        if not passed:
            failures.append(message)

    forwards: list[subprocess.Popen] = []
    try:
        forwards.append(
            start_forward(f"svc/{SERVICE_NAME}", NAMESPACE, PUSHGATEWAY_LOCAL_PORT, 9091)
        )
        forwards.append(
            start_forward("svc/prometheus-alertmanager", NAMESPACE, ALERTMANAGER_LOCAL_PORT, 9093)
        )

        # --- phase 0: the volume is real, and the pod is the one holding it ----
        say("phase 0 — what is actually mounted (read, never assumed)")
        pvc = json.loads(kubectl("get", "pvc", "-o", "json"))
        gw_pvcs = [
            i["metadata"]["name"]
            for i in pvc["items"]
            if "pushgateway" in i["metadata"]["name"]
            and i["status"]["phase"] == "Bound"
        ]
        check(bool(gw_pvcs), f"the gateway has a BOUND PersistentVolumeClaim: {gw_pvcs}")
        pod_args = kubectl(
            "get", "pod", "-l", POD_SELECTOR,
            "-o", "jsonpath={.items[0].spec.containers[0].args}",
        )
        check(
            "--persistence.file=" in pod_args,
            f"the running container carries --persistence.file (args: {pod_args}) — a mounted "
            "volume with no flag is decoration, because pushgateway keeps metrics in memory "
            "unless one names a file",
        )

        # --- phase 1: undo the empty state F-050 left behind -------------------
        say("phase 1 — push the REAL 2020 numbers (this is also F-050's recorded one-command fix)")
        ratios = push_real_months(PUSHGATEWAY_LOCAL_PORT)
        before = gateway_samples(PUSHGATEWAY_LOCAL_PORT)
        check(before > 0, f"the gateway holds {before} taxi_drift_* sample(s) after the push")
        record["pushed_volume_ratios"] = ratios

        # --- phase 2: SURVIVAL — destroy the pod, keep the data ---------------
        say("phase 2 — delete the gateway pod mid-life; the series must outlive it")
        name_before, uid_before, _ = gateway_pod()
        say(f"  pod before: {name_before} uid={uid_before}")
        killed_at = time.time()
        kubectl("delete", "pod", "-l", POD_SELECTOR, "--wait=false")
        for process in forwards[:1]:
            stop_forward(process)
        ready, waited = wait_for(lambda: gateway_pod()[2] and gateway_pod()[1] != uid_before,
                                 timeout=300, poll=3)
        restart_seconds = round(time.time() - killed_at, 2)
        name_after, uid_after, _ = gateway_pod()
        say(f"  pod after:  {name_after} uid={uid_after} (ready after {restart_seconds}s)")
        check(ready and uid_after != uid_before,
              f"a DIFFERENT pod object is serving ({uid_before[:8]}… -> {uid_after[:8]}…), "
              f"ready {restart_seconds}s after the delete — identity, never name (M4-S5)")
        forwards[0] = start_forward(f"svc/{SERVICE_NAME}", NAMESPACE, PUSHGATEWAY_LOCAL_PORT, 9091)
        time.sleep(3)
        after = gateway_samples(PUSHGATEWAY_LOCAL_PORT)
        check(
            after == before and after > 0,
            f"the NEW pod serves the SAME {after} sample(s) the old one held (before={before}) — "
            "the store survived the pod. On an emptyDir this read 0, three times, on host "
            "restarts (F-050)",
        )
        record["survival"] = {
            "pod_before": {"name": name_before, "uid": uid_before},
            "pod_after": {"name": name_after, "uid": uid_after},
            "restart_seconds": restart_seconds,
            "samples_before": before,
            "samples_after": after,
        }
        check(
            restart_seconds < PREDICTION["survival"]["expected_restart_seconds_below"],
            f"the restart took {restart_seconds}s, under the predicted "
            f"{PREDICTION['survival']['expected_restart_seconds_below']}s — this is the number "
            "A-11's 10m sustain is argued against",
        )

        # --- phase 3: ABSENCE — wipe the store, watch A-11 -------------------
        say("phase 3 — wipe the drift series deliberately; A-11 must page and A-10 must not")
        # Waited for rather than asserted instantly: the push has to be scraped
        # (15s) and evaluated before the rule can leave the state F-050 left it
        # in, and a check that fails on a scrape interval fails for its own
        # reasons (#55).
        quiet, quiet_after = wait_for(lambda: rule_state(ABSENCE_ALERT) == "inactive",
                                      timeout=180, poll=10)
        check(quiet,
              f"{ABSENCE_ALERT} is inactive BEFORE the wipe ({quiet_after:.0f}s after the push "
              "cleared the state F-050 left the gateway in) — a rule that is always firing "
              "proves nothing when it fires")
        wiped_at = time.time()
        for month in MONTHS:
            delete_group(
                url=f"http://localhost:{PUSHGATEWAY_LOCAL_PORT}",
                job=PUSH_JOB,
                grouping={"month": month},
            )
        emptied = gateway_samples(PUSHGATEWAY_LOCAL_PORT)
        check(emptied == 0, f"the gateway now holds {emptied} taxi_drift_* sample(s)")
        volume_series = 'taxi_drift_volume_ratio{job="taxi-drift"}'
        gone, _ = wait_for(lambda: not prom_query(PROM_HOST, ROUTE, volume_series),
                           timeout=180, poll=10)
        check(gone, "Prometheus sees no taxi_drift_volume_ratio series at all — the board is "
                    "blank, which is exactly what a calm month looks like")

        fired, _ = wait_for(lambda: rule_state(ABSENCE_ALERT) == "firing",
                            timeout=args.absence_timeout, poll=15)
        fired_after = round(time.time() - wiped_at, 1)
        predicted_at = PREDICTION["absence"]["must_fire"]["after_about_seconds"]
        check(fired, f"{ABSENCE_ALERT} (A-11) FIRED {fired_after}s after the wipe "
                     f"(predicted about {predicted_at}s — its sustain is 10m)")
        at_am, _ = wait_for(lambda: alertmanager_holds(ALERTMANAGER_LOCAL_PORT, ABSENCE_ALERT),
                            timeout=120, poll=10)
        check(at_am, "Alertmanager holds it — a rule firing only in Prometheus's own UI has "
                     "not reached anybody")
        stale_state = rule_state(STALE_ALERT)
        check(stale_state == "inactive",
              f"{STALE_ALERT} (A-10) stayed {stale_state} through a TOTAL loss of the drift "
              "surface — its blind spot demonstrated rather than asserted, and the whole "
              "argument for A-11 existing")
        volume_state = rule_state(VOLUME_ALERT)
        check(volume_state == "inactive",
              f"{VOLUME_ALERT} (A-9) is {volume_state} while the series are gone: the collapse "
              "of March 2020 is still true and nothing was rendering it")
        record["absence"] = {
            "wiped_at": datetime.fromtimestamp(wiped_at, UTC).isoformat(timespec="seconds"),
            "fired_after_seconds": fired_after,
            "reached_alertmanager": at_am,
            "a10_state_during": stale_state,
            "a9_state_during": volume_state,
        }

        # --- phase 4: CLEAR — and the board ends carrying the truth ----------
        say("phase 4 — re-push the real numbers; A-11 clears and March 2020 is back on the board")
        cleared_push_at = time.time()
        push_real_months(PUSHGATEWAY_LOCAL_PORT)
        restored = gateway_samples(PUSHGATEWAY_LOCAL_PORT)
        check(restored == before, f"the gateway holds {restored} sample(s) again (was {before})")
        cleared, _ = wait_for(lambda: rule_state(ABSENCE_ALERT) == "inactive",
                              timeout=300, poll=10)
        check(cleared, f"{ABSENCE_ALERT} cleared {round(time.time() - cleared_push_at, 1)}s after "
                       "the re-push — the rule follows the data and is not latched")
        back, _ = wait_for(lambda: rule_state(VOLUME_ALERT) in {"pending", "firing"},
                           timeout=300, poll=15)
        check(back, f"{VOLUME_ALERT} (A-9) is {rule_state(VOLUME_ALERT)} again — the board ends "
                    "carrying the truth: March 2020 really did lose 61% of its trips, and "
                    "silencing that to tidy a transcript would be publishing a false board")
        record["clearing"] = {
            "alert_cleared": cleared,
            "a9_state_after": rule_state(VOLUME_ALERT),
            "a9_firing_months": sorted(firing_months(VOLUME_ALERT)),
            "samples_restored": restored,
        }
    finally:
        for process in forwards:
            stop_forward(process)

    record["finished_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    record["passed"] = not failures
    record["failures"] = failures
    path = RECORD_DIR / "persistence.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    say(f"recorded {path.relative_to(REPO_ROOT)}")
    total = len(record["checks"])
    if failures:
        say(f"FAILED — {len(failures)} of {total} check(s) failed")
        return 1
    say(f"PASSED — {total}/{total} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
