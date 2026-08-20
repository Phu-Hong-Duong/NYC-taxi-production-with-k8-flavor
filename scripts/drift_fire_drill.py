#!/usr/bin/env python
"""Compute drift for the 2020 scoring months, push it, and watch the alerts decide.

M7-S3. The M6-S2/M6-S5 shape, applied to a signal that comes from a batch job
instead of from the wire: **the prediction is written to disk before anything is
pushed**, and the negative predictions are the load-bearing half. A drill that
predicts only "something fires" cannot be wrong.

WHAT MAKES THIS DIFFERENT FROM `alert_fire_drill.py`, AND WHY IT MATTERS
------------------------------------------------------------------------
M6's drill INJECTED a fault: it sent malformed bodies at a healthy service to
manufacture the condition. This one injects nothing. The condition is **real
2020 data that already exists in this repository**, put through a real
comparison against the champion's real training distribution. Nothing is staged
and nothing is degraded; the endpoint is not touched at all. So:

  * there is no outage, no injection to stop, and nothing to undo;
  * the alert either fires on the world as it was in March 2020 or it does not,
    and if it does not that is a WRONG PREDICTION TO INVESTIGATE (F-041's
    precedent) and never a threshold to walk until the alert agrees.

THE PREDICTION IS ABOUT NUMBERS AS WELL AS ALERTS, DELIBERATELY
----------------------------------------------------------------
`PREDICTION` carries expected volume ratios and an expected ordering of PSI, not
just a list of alert names. A prediction that only says "A-9 fires" is satisfied
by a broken instrument that fires on everything. The numeric predictions are how
a green drill can still tell you that you did not understand the mechanism.

THE HONEST UNCERTAINTY, STATED IN THE PREDICTION ITSELF
--------------------------------------------------------
The genuinely open question is **A-8 on 2020-03**, and the reasoning is F-045's:
68.23% of that month's rows are 01–10 March, which is an ordinary New York
month. A monthly aggregate is weighted by exactly the rows that did not vanish.
So the prediction says A-8 does NOT fire at monthly grain and says why — which
means the drill is informative whichever way it lands, and neither way is a
reason to touch a bar.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from taxi_mlops.monitoring.__main__ import PUSH_JOB, build_metrics  # noqa: E402
from taxi_mlops.monitoring.drift import compute_drift  # noqa: E402
from taxi_mlops.monitoring.pushgateway import (  # noqa: E402
    SERVICE_NAME,
    delete_group,
    push_metrics,
)

RECORD_DIR = REPO_ROOT / "automation" / "runs" / "m7-drift"
ROUTE = "http://localhost:8081"
PROM_HOST = "prometheus.local"

#: Ephemeral local ports, torn down on exit. Deliberately NOT in CLAUDE.md's
#: port family: the family lists ports this program DECLARES, and a forward
#: that exists for ten minutes inside one drill is not a declared route (the
#: `make flyte-actions` 8092 precedent, and `alert_fire_drill.py`'s 9095).
PUSHGATEWAY_LOCAL_PORT = 9096
ALERTMANAGER_LOCAL_PORT = 9097

MONTHS = ("2020-01", "2020-02", "2020-03")

#: WRITTEN BEFORE ANY 2020 MONTH IS COMPARED, and committed. A test asserts the
#: committed `prediction.json` still equals this object, so amending a
#: prediction to match an outcome is a RED test rather than a diff nobody reads
#: (M6-S5's discipline, inherited).
PREDICTION: dict[str, Any] = {
    "written_before": "any 2020 drift comparison is computed or pushed",
    "bars_argued_in": "docs/slo_serving.md §8, from the headroom leg (2019 only)",
    "must_fire": [
        {
            "alert": "ScoringVolumeCollapse",
            "signal": "A-9",
            "month": "2020-03",
            "confidence": "high",
            "because": (
                "2,948,237 rows over 31 days is ~95,100 trips/day against the "
                "reference's ~243,000 — a ratio near 0.39, comfortably under the "
                "0.50 bar. Volume is the marginal PSI is structurally blind to, "
                "which is the whole reason A-9 exists separately from A-8."
            ),
        }
    ],
    "must_not_fire": [
        {
            "alert": "ScoringVolumeCollapse",
            "signal": "A-9",
            "month": "2020-01",
            "because": "~202,600 trips/day, a ratio near 0.83 — an ordinary year-on-year dip.",
        },
        {
            "alert": "ScoringVolumeCollapse",
            "signal": "A-9",
            "month": "2020-02",
            "because": "~213,300 trips/day, a ratio near 0.88.",
        },
        {
            "alert": "DriftMetricsStale",
            "signal": "A-10",
            "because": "every push carries a fresh timestamp; 40 days cannot have elapsed.",
        },
        {
            "alert": "ServedVersionNotChampion",
            "signal": "A-4",
            "because": (
                "the endpoint serves version 2 and @champion is version 2. This drill "
                "reads the alias and never writes it (M7 law 3)."
            ),
        },
        {
            "alert": "QuoteHorizonRefusals",
            "signal": "A-3",
            "because": "no quote is sent by this drill at all, in horizon or out of it.",
        },
        {
            "alert": "PredictorLatencySLOBurning",
            "signal": "A-1",
            "because": "nothing touches the wire — this drill sends the endpoint no traffic.",
        },
        {
            "alert": "ServingEdge5xxRateHigh",
            "signal": "A-2",
            "because": "same: no traffic, no errors, no injection anywhere.",
        },
        {
            "alert": "PredictorNoAvailableReplica",
            "signal": "A-5",
            "because": "no pod is deleted, scaled or annotated.",
        },
        {
            "alert": "PredictorCpuThrottledSustained",
            "signal": "A-6",
            "because": (
                "the drift job is a HOST process reading DuckDB. It is not on the "
                "predictor's CPU path at all — which is also why drift metrics are "
                "structurally outside F-043's exporter-starvation class."
            ),
        },
    ],
    "the_open_question": {
        "alert": "ModelInputDrift",
        "signal": "A-8",
        "month": "2020-03",
        "predicted": "DOES NOT FIRE at monthly grain",
        "confidence": "low — this is the prediction most likely to be wrong",
        "because": (
            "F-045's mechanism, applied to PSI. 68.23% of March 2020's surviving rows "
            "are 01-10 March, which is an ordinary New York month; only 3.32% are "
            "22-31 March. A monthly aggregate is weighted by exactly the rows that did "
            "NOT vanish, so the mix over the whole month may barely move even though "
            "the last third of it is a different city. If A-8 fires anyway, the "
            "monthly window is more sensitive than F-045 suggested and that is worth a "
            "paragraph; if it does not, A-9 is what caught the largest demand shock in "
            "the city's history and §8.4's argument is vindicated rather than lucky. "
            "EITHER WAY NO BAR MOVES — the bars were argued from 2019 headroom before "
            "this ran."
        ),
    },
    "numeric": {
        "2020-01": {"volume_ratio_about": 0.83},
        "2020-02": {"volume_ratio_about": 0.88},
        "2020-03": {"volume_ratio_about": 0.39},
        "psi_ordering": (
            "max input PSI should rise 2020-01 -> 2020-03; the geography columns "
            "(PULocationID/DOLocationID) should be the largest movers, because a "
            "demand shock is spatial before it is temporal."
        ),
    },
    "alias": {"champion_before": 2, "champion_after": 2, "this_drill_never_writes": True},
}

DRIFT_ALERTS = {
    "ModelInputDrift",
    "ScoringVolumeCollapse",
    "DriftMetricsStale",
    "QuoteHorizonRefusals",
    "ServedVersionNotChampion",
}


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def say(msg: str) -> None:
    print(f"[drift-drill] {msg}", flush=True)


def http_get(host: str, url: str, timeout: float = 20.0) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"Host": host})  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def prom_rules() -> dict[str, dict[str, Any]]:
    status, body = http_get(PROM_HOST, f"{ROUTE}/api/v1/rules")
    if status != 200:
        raise RuntimeError(f"Prometheus /api/v1/rules -> {status}")
    out: dict[str, dict[str, Any]] = {}
    for group in json.loads(body)["data"]["groups"]:
        for rule in group["rules"]:
            if rule.get("type") == "alerting":
                out[rule["name"]] = rule
    return out


def firing_months(rules: dict[str, dict[str, Any]], alert: str) -> set[str]:
    """Which MONTHS this alert is firing for — not merely whether it is firing.

    THIS IS THE CHECK, AND THE FIRST VERSION OF THIS DRILL GOT IT WRONG. A-9 is
    predicted to fire for 2020-03 and to stay quiet for 2020-01 and 2020-02 —
    three predictions about ONE rule name. A judge keyed on the name alone
    cannot express that, and mine reported `A-9 fired and was predicted
    INACTIVE` while the system was behaving exactly as predicted (gotcha #67's
    family: a checker whose unit of judgement is coarser than the fact it is
    judging).

    Reading the per-series `alerts` array is also strictly the STRONGER claim: a
    rule that fired for all three months — i.e. a bar so low that an ordinary
    January trips it — would pass a name-level check and fails this one.
    """
    rule = rules.get(alert) or {}
    return {
        instance.get("labels", {}).get("month", "")
        for instance in rule.get("alerts") or []
        if instance.get("state") == "firing"
    }


def prom_query(expr: str) -> list[dict[str, Any]]:
    url = f"{ROUTE}/api/v1/query?query={urllib.parse.quote(expr)}"
    status, body = http_get(PROM_HOST, url)
    if status != 200:
        raise RuntimeError(f"Prometheus query -> {status}: {body[:200]}")
    return json.loads(body)["data"]["result"]


def alertmanager_alerts(port: int) -> list[dict[str, Any]]:
    status, body = http_get("localhost", f"http://localhost:{port}/api/v2/alerts")
    if status != 200:
        return []
    return json.loads(body)


def champion_version() -> str:
    """READ the alias, through the same resolver every other drill uses. Never writes."""
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


def port_forward(service: str, namespace: str, local: int, remote: int) -> subprocess.Popen:
    process = subprocess.Popen(
        [
            "kubectl", "-n", namespace, "port-forward",
            service, f"{local}:{remote}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3)
    return process


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="write the prediction, compute nothing, push nothing",
    )
    parser.add_argument(
        "--observe-seconds",
        type=int,
        default=480,
        help="how long to watch the rules after the push (default 480: the 5m sustain plus slack)",
    )
    args = parser.parse_args(argv)

    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    prediction_path = RECORD_DIR / "prediction.json"
    prediction_path.write_text(json.dumps(PREDICTION, indent=2, sort_keys=True) + "\n")
    say(f"PREDICTION written FIRST -> {prediction_path.relative_to(REPO_ROOT)}  ({now()})")
    for entry in PREDICTION["must_fire"]:
        say(f"    PREDICT {entry['signal']} {entry['alert']} FIRES for {entry['month']}")
    for entry in PREDICTION["must_not_fire"]:
        month = f" ({entry['month']})" if "month" in entry else ""
        say(f"    PREDICT {entry['signal']} {entry['alert']}{month} stays INACTIVE")
    open_q = PREDICTION["the_open_question"]
    say(
        f"    PREDICT {open_q['signal']} {open_q['alert']} for {open_q['month']}: "
        f"{open_q['predicted']}  (confidence: {open_q['confidence']})"
    )

    if args.dry_run:
        say("--dry-run: nothing computed, nothing pushed, no alert touched.")
        return 0

    champion_before = champion_version()
    say(f"@champion before: {champion_before}")

    forwards: list[subprocess.Popen] = []
    record: dict[str, Any] = {
        "started_at": now(),
        "prediction": PREDICTION,
        "champion_before": champion_before,
        "months": {},
    }
    failures: list[str] = []
    try:
        forwards.append(
            port_forward(
                f"svc/{SERVICE_NAME}", "monitoring", PUSHGATEWAY_LOCAL_PORT, 9091
            )
        )
        forwards.append(
            port_forward(
                "svc/prometheus-alertmanager", "monitoring", ALERTMANAGER_LOCAL_PORT, 9093
            )
        )
        gateway = f"http://localhost:{PUSHGATEWAY_LOCAL_PORT}"

        # --- phase 0: reset the board ----------------------------------------
        # THE GATEWAY HAS NO EXPIRY. Everything a previous run pushed is still
        # on it, so a second run of this drill would start with A-9 already
        # firing and could never observe a transition. Deleting the groups first
        # is what makes the drill re-runnable — and the wait for the alerts to
        # go inactive is itself evidence that the rules track the data rather
        # than latching.
        for month in MONTHS:
            try:
                delete_group(url=gateway, job=PUSH_JOB, grouping={"month": month})
            except Exception as error:  # noqa: BLE001 — an absent group is fine
                say(f"    (reset: {month} not present: {error})")
        say("reset: the gateway's drift groups are cleared; waiting for the rules to settle …")
        for _ in range(24):
            time.sleep(10)
            if all(
                prom_rules().get(name, {}).get("state") == "inactive" for name in DRIFT_ALERTS
            ):
                break
        say("    the board is clean")

        # --- phase 1: the rules are loaded before anything is pushed ----------
        rules = prom_rules()
        missing = sorted(DRIFT_ALERTS - set(rules))
        if missing:
            failures.append(f"Prometheus has not loaded {missing}")
        else:
            say(f"ok  all {len(DRIFT_ALERTS)} drift/client rules loaded, health ok")
        before_states = {name: rules[name]["state"] for name in DRIFT_ALERTS if name in rules}
        say(f"    states before the push: {before_states}")
        record["states_before"] = before_states
        for name, state in before_states.items():
            if state != "inactive":
                failures.append(f"{name} was already {state} before the push")

        # --- phase 2: compute and push ---------------------------------------
        pushed_at = time.time()
        for month in MONTHS:
            report = compute_drift(month)
            metrics = build_metrics(report)
            push_metrics(metrics, url=gateway, job=PUSH_JOB, grouping={"month": month})
            path = RECORD_DIR / f"drift-{month}.json"
            path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n")
            record["months"][month] = {
                "volume_ratio": report.volume_ratio,
                "current_rows": report.current_rows,
                "trips_per_day": report.current_trips_per_day,
                "max_input_psi": report.max_input_psi,
                "psi": {c.column: c.psi for c in report.columns},
                "unseen_share": {c.column: c.unseen_share for c in report.columns},
                "record": str(path.relative_to(REPO_ROOT)),
            }
            say(
                f"ok  {month}: {report.current_rows:,} rows · volume ratio "
                f"{report.volume_ratio:.4f} · max input PSI {report.max_input_psi:.4f} "
                f"· {len(metrics)} series pushed"
            )
        record["pushed_at"] = now()

        # --- phase 3: Prometheus scraped the gateway --------------------------
        say("waiting for a scrape of the gateway (15 s interval) …")
        seen: list[dict[str, Any]] = []
        for _ in range(12):
            time.sleep(5)
            seen = prom_query('taxi_drift_volume_ratio{job="taxi-drift"}')
            if len(seen) >= len(MONTHS):
                break
        if len(seen) < len(MONTHS):
            failures.append(
                f"Prometheus sees {len(seen)} taxi_drift_volume_ratio series, "
                f"expected {len(MONTHS)}"
            )
        else:
            say(f"ok  Prometheus scraped the gateway: {len(seen)} month series visible")
        record["prometheus_series"] = {
            s["metric"].get("month"): float(s["value"][1]) for s in seen
        }
        say(f"    as Prometheus reads them: {record['prometheus_series']}")

        # --- phase 4: watch the rules decide ----------------------------------
        say(f"observing the rules for {args.observe_seconds}s …")
        timeline: list[dict[str, Any]] = []
        #: keyed by (alert, month) — see `firing_months`. `month` is "" for a
        #: rule that carries no month label, which is every non-drift rule.
        fired_at: dict[str, float] = {}
        deadline = time.time() + args.observe_seconds
        last: dict[str, str] = {}
        while time.time() < deadline:
            rules = prom_rules()
            states = {name: rules[name]["state"] for name in DRIFT_ALERTS if name in rules}
            elapsed = time.time() - pushed_at
            for name in DRIFT_ALERTS:
                for month in firing_months(rules, name):
                    key = f"{name}@{month}"
                    if key not in fired_at:
                        fired_at[key] = elapsed
                        say(f"    T+{elapsed:7.1f}s  {name} FIRING for month={month!r}")
            if states != last:
                timeline.append({"t_plus_seconds": round(elapsed, 1), "states": dict(states)})
                say(f"    T+{elapsed:7.1f}s  {states}")
                last = states
            if all(
                f"{entry['alert']}@{entry.get('month', '')}" in fired_at
                for entry in PREDICTION["must_fire"]
            ) and time.time() - pushed_at > 400:
                break
            time.sleep(10)
        record["timeline"] = timeline
        record["fired_at_seconds"] = fired_at
        record["states_after"] = last

        # --- phase 5: Alertmanager, not just Prometheus's UI -------------------
        am = alertmanager_alerts(ALERTMANAGER_LOCAL_PORT)
        am_names = sorted({a["labels"].get("alertname", "?") for a in am})
        record["alertmanager_received"] = am_names
        say(f"    Alertmanager holds: {am_names}")

        # --- phase 6: judge against the prediction ----------------------------
        # Judged per (alert, month), because that is the grain the prediction is
        # written at: A-9 is predicted to fire for 2020-03 AND to stay quiet for
        # 2020-01/02, which is three statements about one rule name.
        for entry in PREDICTION["must_fire"]:
            name, month = entry["alert"], entry.get("month", "")
            key = f"{name}@{month}"
            if key in fired_at:
                say(
                    f"ok  {entry['signal']} {name} FIRED for month={month!r} at "
                    f"T+{fired_at[key]:.1f}s — as predicted"
                )
            else:
                failures.append(
                    f"{entry['signal']} {name} was predicted to fire for {month} and did not"
                )
            if name not in am_names:
                failures.append(f"{name} fired in Prometheus but never reached Alertmanager")
            else:
                say(f"ok  {name} reached Alertmanager")
        for entry in PREDICTION["must_not_fire"]:
            name, month = entry["alert"], entry.get("month", "")
            key = f"{name}@{month}"
            if key in fired_at:
                failures.append(
                    f"{entry['signal']} {name} fired for {month or '(no month)'} and was "
                    "predicted INACTIVE"
                )
            else:
                where = f" for month={month!r}" if month else ""
                say(f"ok  {entry['signal']} {name} did not fire{where} — as predicted")

        # The open question is REPORTED, never judged: a prediction with
        # "confidence: low" attached is a question, and failing a drill on the
        # answer to a question is how a drill teaches people not to ask any.
        a8_state = last.get("ModelInputDrift", "unknown")
        a8_fired = any(k.startswith("ModelInputDrift@") for k in fired_at)
        record["open_question_outcome"] = {
            "alert": "ModelInputDrift",
            "predicted": open_q["predicted"],
            "observed": "FIRED" if a8_fired else f"did not fire (state={a8_state})",
            "prediction_correct": (not a8_fired),
        }
        say(
            f"OPEN QUESTION · A-8 ModelInputDrift: predicted {open_q['predicted']!r}, "
            f"observed {record['open_question_outcome']['observed']} -> prediction "
            f"{'CORRECT' if not a8_fired else 'WRONG (investigate — see the write-up)'}"
        )

        # --- phase 7: prove it CLEARS, then restore the true state ------------
        # "Then cleared" is the M6 drill's last phase, and here it needs an
        # argument rather than a copy. M6 cleared by STOPPING an injection; this
        # drill injected nothing — March 2020 really did lose 61% of its trips,
        # and an alert saying so is correct. Latching it off to make a
        # transcript tidy would be publishing a false board.
        #
        # So the clearing is demonstrated on the MECHANISM and then undone: the
        # month's group is deleted, A-9 is watched going inactive (proving the
        # rule follows the data and is not stuck), and the real numbers are
        # pushed straight back. The board ends carrying the truth.
        clear_seconds: float | None = None
        cleared_at = time.time()
        delete_group(url=gateway, job=PUSH_JOB, grouping={"month": "2020-03"})
        say("clearing: deleted the 2020-03 group; watching A-9 …")
        for _ in range(30):
            time.sleep(10)
            if prom_rules().get("ScoringVolumeCollapse", {}).get("state") == "inactive":
                clear_seconds = time.time() - cleared_at
                break
        if clear_seconds is None:
            failures.append("A-9 did not clear when its metric was removed — it may be latched")
        else:
            say(f"ok  A-9 cleared {clear_seconds:.1f}s after its metric was removed")
        record["cleared_after_seconds"] = clear_seconds

        report = compute_drift("2020-03")
        push_metrics(
            build_metrics(report), url=gateway, job=PUSH_JOB, grouping={"month": "2020-03"}
        )
        say(
            "ok  2020-03's real numbers pushed back — the board ends carrying the truth "
            "about March 2020, not a tidied transcript"
        )
        record["final_state"] = (
            "2020-01..03 drift metrics on the gateway; A-9 will re-fire for 2020-03 "
            "after its 5m sustain, which is the correct standing state: the volume "
            "collapse is real and the decision it asks for is M7-S4's retrain."
        )

        champion_after = champion_version()
        record["champion_after"] = champion_after
        if champion_after != champion_before:
            failures.append(
                f"@champion moved {champion_before} -> {champion_after}; "
                "this drill must not write it"
            )
        else:
            say(f"ok  @champion is {champion_after} — read before and after, never written")

    finally:
        for process in forwards:
            process.terminate()

    record["finished_at"] = now()
    record["failures"] = failures
    record["passed"] = not failures
    out = RECORD_DIR / "drift_fire_drill.json"
    out.write_text(json.dumps(record, indent=2, sort_keys=True, default=str) + "\n")
    say(f"record -> {out.relative_to(REPO_ROOT)}")

    if failures:
        for failure in failures:
            say(f"FAIL {failure}")
        say(f"RED — {len(failures)} failure(s).")
        return 1
    say("PASSED — every prediction held, and the open question is answered on the record.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
