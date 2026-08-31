#!/usr/bin/env python
"""Empty the online store on purpose, and watch what notices — prediction written FIRST.

M9-S2. `make store-watch-drill`.

Three questions, and the drill is built so that a wrong answer to any of them is
worth more than the pass:

  1. **What does a rider's request do when the store is empty?** Not a rhetorical
     question: an all-null store yields an all-NaN geometry table, and NaN is the
     CORRECT answer for zones 264/265 — so nothing on the geometry path can
     refuse. The CALENDAR half is what refuses, and this number has had three
     states worth reading in order: the M9 kickoff expected **503**; this drill's
     2026-08-23 run predicted and measured **422** (correct for the code as it
     then stood, and that measurement IS F-062 — a dead dependency billed to the
     caller, outside SLO-A1's error budget); and since M9-S7 landed the PO's
     answer (b) it is **503** again, restored by a code change rather than by an
     argument. The superseded prediction and its records are kept beside this one
     (`attempt1-422-era/`), because a re-run that silently rewrote them would
     erase the evidence the decision was made from.
  2. **Do A-12's two rules fire, and do they reach Alertmanager?** A rule firing
     only in Prometheus's own UI has not paged anybody.
  3. **Does A-12 stay silent when the SURFACE is deleted rather than the store?**
     That is the negative that justifies A-13's existence, and it is the same
     blind spot A-10 has and A-11 covers.

THE PREDICTION IS WRITTEN FIRST AND IS COMMITTED
-------------------------------------------------
`PREDICTION` lands on disk before the first mutation and a unit test asserts the
committed copy still equals this object — so amending a prediction to match an
outcome is a RED test, not a diff nobody reads (M6-S5's gameday discipline,
fourth inheritance). The negative predictions are the load-bearing half.

THE UNDO IS STAGED BEFORE THE INJECTION
-----------------------------------------
Every destructive phase proves its repair is available before it breaks
anything: the quarantine interpreter and the published sources for the store,
the recorded replica count for the feature server. M6-S5's rule, and a unit test
pins the ORDER.

WHAT IT DOES NOT TOUCH
-----------------------
The champion's own wire reads committed tables and never the store, so it is a
POSITIVE CONTROL here rather than a risk: it is asked for a quote in every phase
and must answer 39.0019 throughout. No alias is read or written, nothing is
fitted, no threshold is edited, and the store's whole state class is
REGENERABLE — `make feast-materialize` refills it in ~7 seconds (recorded).
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
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from _lib import ports  # noqa: E402
from _lib.k8s import kubectl, start_forward, stop_forward  # noqa: E402
from _lib.monitoring import alertmanager_holds as _am_holds  # noqa: E402
from _lib.monitoring import firing_labels, prom_rules  # noqa: E402
from _lib.monitoring import rule_state as _rule_state  # noqa: E402

from taxi_mlops.features.calendar import load_calendar  # noqa: E402
from taxi_mlops.monitoring.pushgateway import delete_group  # noqa: E402
from taxi_mlops.monitoring.store_health import PUSH_JOB  # noqa: E402
from taxi_mlops.serving.client import QuoteRequest  # noqa: E402
from taxi_mlops.serving.transformer import encode_raw  # noqa: E402

RECORD_DIR = REPO_ROOT / "automation" / "runs" / "m9-store-watch"
PREDICTION_FILE = RECORD_DIR / "prediction.json"

ROUTE = "http://localhost:8081"
PROM_HOST = "prometheus.local"
TRANSFORMER_HOST = "nyc-taxi-eta-transformer-serving.local"
CHAMPION_HOST = "nyc-taxi-eta-serving.local"

#: Ephemeral, and deliberately not any port another drill or reader claims:
#: 9096/9097 are the drift fire drill's, 9098/9099 the persistence drill's,
#: 9100 the reader's own gateway forward, 6567/6568 the two feature-server
#: readers'. A drill that steals a running process's port fails for its own
#: reasons (#55).
ALERTMANAGER_PORT = ports.port("ALERTMANAGER_STORE_DRILL")
GATEWAY_PORT = ports.port("PUSHGATEWAY_STORE_DRILL")

CANARY_ALERT = "OnlineStoreCanaryFailing"
INCOMPLETE_ALERT = "OnlineStoreIncomplete"
ABSENT_ALERT = "OnlineStoreWatchdogAbsent"
STORE_LABEL = "feast-online"

#: The V2 model name is in the URL PATH (ADR-011 condition 2), and the
#: transformer answers to its OWN name — the champion's 404s on that host, which
#: `make transformer-accept` asserts as a deliberate negative. Getting this wrong
#: is a 404 that looks exactly like a broken route (gotcha #111), and it cost
#: this drill its first baseline run.
TRANSFORMER_MODEL = "nyc-taxi-eta-transformer"

#: The request every phase sends: the parity table's own federal-holiday row, so
#: a healthy answer is checkable against a published record rather than against
#: this script's opinion. The BODY is built by `transformer.encode_raw` — the
#: server's own encoder — because a hand-rolled copy of a request schema is the
#: twin problem this program keeps deleting.
QUOTE_ROW = QuoteRequest("2019-07-04T09:15:00", 132, 48, 1.0)
HEALTHY_MINUTES = 39.00193715359812

#: The same trip, one year past the committed holiday table's horizon. F-019's
#: typed refusal is the REGRESSION F-062's discriminator could have caused — an
#: uncovered date must still be the caller's 422 while the store is answering —
#: so the drill asks for it in both states rather than trusting the argument.
#: The year is DERIVED from the table (`load_calendar`), never typed.
UNCOVERED_ROW = QuoteRequest(f"{max(load_calendar().years) + 1}-07-04T09:15:00", 132, 48, 1.0)

#: A PURE LITERAL: `tests/unit/test_store_watchdog.py` reads it with
#: `ast.literal_eval` rather than by importing this module, so the coverage test
#: can never be satisfied by a module with a side effect.
PREDICTION: dict[str, Any] = {
    "written_before": "the first FLUSHDB, and committed before the drill ran",
    "bars_argued_in": "docs/slo_serving.md §9, committed before this file",
    "empty_store": {
        "rider_request": {
            "claim": (
                "a quote against an EMPTY store is REFUSED with HTTP 503, not 422 and "
                "not a confident wrong number"
            ),
            "confidence": "high",
            "because": (
                "F-062 landed at M9-S7 on the PO's answer (b). Every request carries a "
                "date and calendar_from_store still RAISES on an unanswered one — F-019 "
                "carried onto the store's wire — but WHOSE failure that is now depends "
                "on a second question: the store is asked for a date the committed "
                "holiday table provably covers. An emptied store cannot answer that "
                "either, so the refusal is FeatureStoreUnavailable (503, ours) and it "
                "spends SLO-A1's availability budget. The geometry half still CANNOT "
                "refuse: an all-null centroid table is exactly what zones 264/265 "
                "legitimately produce, so the calendar is still what stands between an "
                "empty store and a quote nobody can see is wrong."
            ),
            "supersedes": (
                "this drill's own 2026-08-23 prediction of 422, which was CORRECT for "
                "the code as it then stood and is kept beside this one at "
                "automation/runs/m9-store-watch/attempt1-422-era/. That measurement IS "
                "F-062: a totally dead dependency billed to the caller as a 4xx, "
                "outside the error budget, rendering as riders sending bad requests. "
                "The M9 kickoff's original expectation of 503 — superseded on "
                "2026-08-23 and restored here by a code change rather than by an "
                "argument — is the third state of this one number and all three are on "
                "the record."
            ),
            "expected_status": 503,
        },
        "uncovered_date_survives": {
            "claim": (
                "with the store EMPTY a past-horizon quote is also 503; with the store "
                "HEALTHY it is still 422 naming the year — F-019's guarantee is the "
                "regression this change could have caused, so it is asserted rather "
                "than assumed"
            ),
            "confidence": "high",
            "because": (
                "the discriminator changes only which side of the wall is blamed. A "
                "live store answers the sentinel, so an uncovered date stays the "
                "caller's 422; a dead store answers nothing, and 'this deployment "
                "cannot establish whether its dependency is up' is ours."
            ),
            "expected_status_while_empty": 503,
            "expected_status_when_healthy": 422,
        },
        "champion_control": {
            "claim": "the champion's own wire answers 39.0019 throughout",
            "confidence": "high",
            "because": "it builds its matrix from committed tables and never reads the store",
        },
        "must_fire": [
            {
                "alert": "OnlineStoreCanaryFailing",
                "signal": "A-12",
                "confidence": "high",
                "after_about_seconds": 120,
                "because": "three of four canary checks go to 0 and the rule sustains 2m",
                "must_reach_alertmanager": True,
                "expected_failing_checks": ["zone_answers", "calendar_answers"],
            },
            {
                "alert": "OnlineStoreIncomplete",
                "signal": "A-12",
                "confidence": "high",
                "after_about_seconds": 120,
                "because": "0 keys against 57,688 the sources define",
                "must_reach_alertmanager": True,
            },
        ],
        "must_not_fire": [
            {
                "alert": "OnlineStoreWatchdogAbsent",
                "signal": "A-13",
                "because": "the surface is present and fresh — it is the store that is gone",
            },
            {
                "alert": "ServingEdge5xxRateHigh",
                "signal": "A-2",
                "because": "a 422 is a 4xx and the champion's wire is untouched",
            },
            {"alert": "PredictorNoAvailableReplica", "signal": "A-5", "because": "no pod moved"},
            {
                "alert": "DriftMetricsAbsent",
                "signal": "A-11",
                "because": "a different job's series, untouched by this drill",
            },
            {
                "alert": "ServedVersionNotChampion",
                "signal": "A-4",
                "because": "no alias moves and no deploy happens",
            },
        ],
        "clears": {
            "claim": "re-materializing clears both A-12 rules",
            "confidence": "high",
            "refill_seconds_below": 60,
            "expected_keys_after": 57688,
        },
    },
    "unreachable_store": {
        "claim": "with the feature server scaled to 0 the transformer answers HTTP 503",
        "confidence": "high",
        "because": (
            "FeatureStoreUnavailable is a distinct type precisely so a dependency "
            "outage does not look like a malformed quote — 503 ours, 422 the caller's"
        ),
        "expected_status": 503,
    },
    "deleted_surface": {
        "must_fire": {
            "alert": "OnlineStoreWatchdogAbsent",
            "signal": "A-13",
            "confidence": "high",
            "after_about_seconds": 600,
            "because": "the rule sustains 10m and absent() is true within a scrape",
            "must_reach_alertmanager": True,
        },
        "must_not_fire": {
            "alert": "OnlineStoreCanaryFailing",
            "signal": "A-12",
            "confidence": "high",
            "because": (
                "THE LOAD-BEARING NEGATIVE. `time() - stamp < 1800` over zero series is "
                "zero series, not a stale reading — so A-12 cannot see its own surface "
                "disappear, and a stack with only A-12 would render a wiped board "
                "exactly like a healthy store. That blind spot is A-13's whole reason "
                "to exist and it is demonstrated here rather than asserted."
            ),
        },
    },
    "never_touched": [
        "@champion (not read and not written by this drill)",
        "any registry version, any MLflow run",
        "the champion's InferenceService, its pod and its wire",
        "every threshold in infra/monitoring/alerting_rules.yml",
        "the settled data pins and data/feast/*.parquet",
    ],
}


def say(msg: str) -> None:
    print(f"[store-drill] {msg}", flush=True)


def http(
    host: str, url: str, body: dict[str, Any] | None = None, timeout: float = 30.0
) -> tuple[int, str]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Host": host}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()
    except Exception as error:  # noqa: BLE001
        return 0, str(error)


# --- readers ---------------------------------------------------------------
# The bodies moved to `_lib.monitoring` at CU-S4. `http()` above stayed: it POSTs
# an optional body (this drill quotes the transformer through it), so it is a
# request client and not a GET — merging it into `http_get` would have been two
# behaviours under one name, which is the hazard CU-S2 measured in `tests/`.
#
# These three are wrappers rather than direct calls because every caller below
# sits inside a `wait_for` poll and must RE-READ the rules each time.


def rule_state(alert: str) -> str:
    return _rule_state(prom_rules(PROM_HOST, ROUTE), alert)


def firing_checks(alert: str) -> set[str]:
    """Which `check` labels are FIRING — the per-series read, never the name-level one.

    gotcha #93: a rule judged by name cannot tell "A-12 fired for the right claim"
    from "A-12 fired for any claim at all", and a canary whose negative half was
    silently broken would pass the weaker check.
    """
    return firing_labels(prom_rules(PROM_HOST, ROUTE), alert, "check")


def alertmanager_holds(alert: str) -> bool:
    return _am_holds(ALERTMANAGER_PORT, alert)


def wait_for(
    predicate: Callable[[], bool], timeout: float, poll: float = 10.0
) -> tuple[bool, float]:
    start = time.time()
    while time.time() - start < timeout:
        try:
            if predicate():
                return True, time.time() - start
        except Exception as error:  # noqa: BLE001
            say(f"  (poll error, retrying: {error})")
        time.sleep(poll)
    return False, time.time() - start


def dbsize() -> int:
    pod = kubectl(
        "-n",
        "feast",
        "get",
        "pod",
        "-l",
        "app=redis",
        "-o",
        "jsonpath={.items[0].metadata.name}",
    ).strip()
    return int(kubectl("-n", "feast", "exec", pod, "--", "redis-cli", "DBSIZE").strip())


def quote(
    host: str, model: str = TRANSFORMER_MODEL, row: QuoteRequest = QUOTE_ROW
) -> tuple[int, str]:
    return http(host, f"{ROUTE}/v2/models/{model}/infer", encode_raw([row]))


def champion_quote() -> tuple[bool, str]:
    """The POSITIVE CONTROL: it reads committed tables, so it must be unaffected."""
    out = subprocess.run(  # noqa: S603
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
        check=False,
    )
    line = (out.stdout or out.stderr).strip().splitlines()[-1] if (out.stdout or out.stderr) else ""
    return out.returncode == 0 and "39.0019" in out.stdout, line


def run_reader() -> int:
    out = subprocess.run(  # noqa: S603
        ["uv", "run", "python", "scripts/store_watch.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    for line in out.stdout.splitlines():
        say(f"  | {line}")
    return out.returncode


class Checks:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def __call__(self, ok: bool, claim: str) -> bool:
        self.rows.append({"ok": bool(ok), "claim": claim})
        say(("ok   " if ok else "FAIL ") + claim)
        return bool(ok)

    @property
    def failures(self) -> int:
        return sum(1 for r in self.rows if not r["ok"])


# --- the phases ----------------------------------------------------------------


def phase_health(check: Checks) -> dict[str, Any]:
    """Baseline. Nothing is broken yet; everything that will be claimed is claimed now."""
    say("--- phase 0: the healthy baseline ---")
    keys = dbsize()
    check(keys > 0, f"the store holds {keys:,} keys before anything is broken")
    rc = run_reader()
    check(rc == 0, "the reader ran and pushed a fresh reading")
    ok_champ, line = champion_quote()
    check(ok_champ, f"the CHAMPION's wire answers (the positive control): {line}")
    status, body = quote(TRANSFORMER_HOST)
    minutes = None
    if status == 200:
        minutes = json.loads(body)["outputs"][0]["data"][0]
    check(
        status == 200 and minutes is not None and abs(minutes - HEALTHY_MINUTES) < 1e-9,
        f"the TRANSFORMER answers the parity row exactly: HTTP {status}, {minutes} minutes",
    )
    # F-019's guarantee, asked of a HEALTHY store: it is the regression F-062's
    # discriminator could have caused, and "it still works" is not a claim a
    # code-reading can make once the status depends on a second round trip.
    unc_spec = PREDICTION["empty_store"]["uncovered_date_survives"]
    unc_status, unc_body = quote(TRANSFORMER_HOST, row=UNCOVERED_ROW)
    unc_year = UNCOVERED_ROW.pickup_datetime[:4]
    check(
        unc_status == unc_spec["expected_status_when_healthy"] and unc_year in unc_body,
        f"an uncovered date is still the CALLER's refusal while the store is healthy: "
        f"HTTP {unc_status} naming {unc_year} (predicted "
        f"{unc_spec['expected_status_when_healthy']}) — F-019 survived F-062",
    )
    states = {a: rule_state(a) for a in (CANARY_ALERT, INCOMPLETE_ALERT, ABSENT_ALERT)}
    ok_quiet, _ = wait_for(
        lambda: all(rule_state(a) == "inactive" for a in states), timeout=660, poll=15
    )
    check(
        ok_quiet,
        f"all three store rules are inactive to start: { {a: rule_state(a) for a in states} }",
    )
    return {
        "keys": keys,
        "minutes": minutes,
        "champion_ok": ok_champ,
        "uncovered_status_when_healthy": unc_status,
        "states": {a: rule_state(a) for a in states},
    }


def phase_empty(check: Checks, gateway_url: str) -> dict[str, Any]:
    """FLUSHDB, watch what notices, then put the truth back."""
    say("--- phase 1: the store is emptied ---")

    # THE UNDO IS STAGED FIRST (M6-S5's rule; a unit test pins this order).
    venv = REPO_ROOT / ".venv-feast" / "bin" / "python"
    sources = sorted((REPO_ROOT / "data" / "feast").glob("*.parquet"))
    staged = venv.exists() and len(sources) == 4
    check(
        staged,
        f"the undo is staged BEFORE the injection: quarantine present={venv.exists()}, "
        f"{len(sources)} published source(s) — `make feast-materialize` can refill it",
    )
    if not staged:
        return {"aborted": "the undo was not available; nothing was broken"}

    before = dbsize()
    pod = kubectl(
        "-n",
        "feast",
        "get",
        "pod",
        "-l",
        "app=redis",
        "-o",
        "jsonpath={.items[0].metadata.name}",
    ).strip()
    kubectl("-n", "feast", "exec", pod, "--", "redis-cli", "FLUSHDB")
    t0 = time.time()
    after = dbsize()
    say(f"FLUSHDB: {before:,} keys -> {after:,}")
    check(after == 0, f"the store is empty ({before:,} -> {after:,} keys)")

    # ---- what a rider gets, measured rather than assumed --------------------
    empty_status, empty_body = quote(TRANSFORMER_HOST)
    say(f"the transformer answered HTTP {empty_status}: {empty_body[:220]}")
    predicted = PREDICTION["empty_store"]["rider_request"]["expected_status"]
    check(
        empty_status == predicted,
        f"a quote against the EMPTY store is HTTP {empty_status} — predicted {predicted} "
        "(the CALENDAR half refuses; the geometry half structurally cannot). At 422 "
        "this same request spent NO availability budget and rendered as a rider "
        "sending a bad request — that was F-062, and this is the number that closes it",
    )
    # Both refusals collapse onto OURS while the store is dead, and that is right:
    # with nothing answering, "was that date covered?" is a question this
    # deployment cannot answer, so it does not get to blame the caller for it.
    unc_empty_status, _ = quote(TRANSFORMER_HOST, row=UNCOVERED_ROW)
    unc_predicted = PREDICTION["empty_store"]["uncovered_date_survives"][
        "expected_status_while_empty"
    ]
    check(
        unc_empty_status == unc_predicted,
        f"and a PAST-HORIZON quote against the empty store is HTTP {unc_empty_status} "
        f"— predicted {unc_predicted}: with nothing answering, this deployment cannot "
        "establish whether that date was covered, and an unanswerable question is not "
        "the caller's fault",
    )
    check(
        empty_status != 200,
        "and it is NOT a confident wrong number — the thing an all-NaN geometry table "
        "alone would have produced",
    )
    ok_champ, line = champion_quote()
    check(ok_champ, f"the CHAMPION's wire is unaffected throughout: {line}")

    run_reader()
    fired: dict[str, Any] = {}
    for spec in PREDICTION["empty_store"]["must_fire"]:
        alert = spec["alert"]
        ok, secs = wait_for(lambda a=alert: rule_state(a) == "firing", timeout=420, poll=10)
        fired[alert] = {"fired": ok, "after_seconds": round(time.time() - t0, 1)}
        check(
            ok,
            f"{alert} ({spec['signal']}) FIRED {fired[alert]['after_seconds']}s after the "
            f"flush (predicted ~{spec['after_about_seconds']}s + detection)",
        )
        at_am, _ = wait_for(lambda a=alert: alertmanager_holds(a), timeout=180, poll=10)
        fired[alert]["reached_alertmanager"] = at_am
        check(
            at_am,
            f"Alertmanager holds {alert} — a rule firing only in Prometheus's own UI "
            "has paged nobody",
        )

    checks_firing = sorted(c for c in firing_checks(CANARY_ALERT) if c)
    expected = PREDICTION["empty_store"]["must_fire"][0]["expected_failing_checks"]
    check(
        set(expected) <= set(checks_firing),
        f"A-12a names WHICH claims failed: {checks_firing} (predicted at least {expected}) — "
        "the per-series read, never the name-level one (gotcha #93)",
    )

    quiet = {}
    for spec in PREDICTION["empty_store"]["must_not_fire"]:
        state = rule_state(spec["alert"])
        quiet[spec["alert"]] = state
        check(
            state != "firing",
            f"{spec['alert']} ({spec['signal']}) stayed {state} — {spec['because']}",
        )

    # ---- the undo, and the board ends carrying the truth ---------------------
    say("re-materializing (the one-command repair the runbook names) …")
    t_refill = time.time()
    # `--no-record`, and the flag exists BECAUSE this drill's first run found the
    # need for it: the refill rewrote `automation/runs/m8-online/materialize.json`
    # — a TRACKED record belonging to M8-S4, cited by both §9 and this story's own
    # headroom leg — with the drill's own minute. The refill is the right repair;
    # re-dating somebody else's evidence is not. The drill records its own refill
    # measurement below, where it belongs.
    refill = subprocess.run(  # noqa: S603
        ["bash", "scripts/feast_materialize.sh", "--no-record"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    refill_seconds = round(time.time() - t_refill, 1)
    restored = dbsize()
    check(
        refill.returncode == 0 and restored == before,
        f"the store is refilled: {restored:,} keys in {refill_seconds}s wall-clock "
        f"(the materialize itself is the ~7s the record holds)",
    )
    run_reader()
    cleared: dict[str, Any] = {}
    for spec in PREDICTION["empty_store"]["must_fire"]:
        alert = spec["alert"]
        ok, secs = wait_for(lambda a=alert: rule_state(a) == "inactive", timeout=420, poll=10)
        cleared[alert] = {"cleared": ok, "after_seconds": round(secs, 1)}
        check(ok, f"{alert} cleared {round(secs, 1)}s after the reader saw a healthy store")

    status, body = quote(TRANSFORMER_HOST)
    minutes = json.loads(body)["outputs"][0]["data"][0] if status == 200 else None
    check(
        status == 200 and minutes is not None and abs(minutes - HEALTHY_MINUTES) < 1e-9,
        f"and the rider's quote is exactly what it was: HTTP {status}, {minutes} minutes",
    )

    return {
        "keys_before": before,
        "keys_after_flush": after,
        "keys_restored": restored,
        # The MEASURED status, captured before any later request could overwrite it.
        # The first draft of this record recorded the PREDICTED one — a record that
        # cannot disagree with its prediction is not evidence about anything.
        "rider_status_while_empty": empty_status,
        "rider_body_while_empty": empty_body[:400],
        "rider_status_predicted": predicted,
        "uncovered_status_while_empty": unc_empty_status,
        "refill_seconds": refill_seconds,
        "fired": fired,
        "cleared": cleared,
        "must_not_fire_states": quiet,
        "canary_checks_firing": checks_firing,
        "final_minutes": minutes,
    }


def phase_unreachable(check: Checks) -> dict[str, Any]:
    """Scale the feature server to zero: a different failure, a different class."""
    say("--- phase 2: the store is UNREACHABLE (a different class from empty) ---")
    replicas = int(
        kubectl(
            "-n", "feast", "get", "deploy", "feast-server", "-o", "jsonpath={.spec.replicas}"
        ).strip()
    )
    check(
        replicas >= 1,
        f"the undo is staged first: feast-server is at {replicas} replica(s), "
        "which is what will be restored",
    )
    kubectl("-n", "feast", "scale", "deploy/feast-server", "--replicas=0")
    kubectl(
        "-n",
        "feast",
        "wait",
        "--for=delete",
        "pod",
        "-l",
        "app=feast-server",
        "--timeout=120s",
        check=False,
    )
    status, body = quote(TRANSFORMER_HOST)
    say(f"the transformer answered HTTP {status}: {body[:220]}")
    predicted = PREDICTION["unreachable_store"]["expected_status"]
    check(
        status == predicted,
        f"an UNREACHABLE store is HTTP {status} — predicted {predicted}, and the point is "
        "that it differs from the empty store's refusal: ours vs the caller's",
    )
    ok_champ, line = champion_quote()
    check(ok_champ, f"the CHAMPION's wire is still unaffected: {line}")
    kubectl("-n", "feast", "scale", "deploy/feast-server", f"--replicas={replicas}")
    kubectl("-n", "feast", "rollout", "status", "deploy/feast-server", "--timeout=180s")
    ok, secs = wait_for(lambda: quote(TRANSFORMER_HOST)[0] == 200, timeout=180, poll=5)
    check(ok, f"the transformer answers again {round(secs, 1)}s after the server came back")
    return {
        "replicas": replicas,
        "status_while_unreachable": status,
        "recovered_after_seconds": round(secs, 1),
    }


def phase_absent(check: Checks, gateway_url: str) -> dict[str, Any]:
    """Delete the SURFACE rather than the store — the negative that justifies A-13."""
    say("--- phase 3: the watchdog's surface is deleted ---")
    check(
        rule_state(ABSENT_ALERT) == "inactive",
        f"A-13 is inactive before the wipe (state={rule_state(ABSENT_ALERT)})",
    )
    delete_group(url=gateway_url, job=PUSH_JOB, grouping={"store": STORE_LABEL})
    t0 = time.time()
    say("the store-watch group is deleted from the gateway — the STORE itself is untouched")
    check(
        dbsize() > 0,
        f"the store still holds {dbsize():,} keys: this phase breaks the "
        "OBSERVATION, not the thing observed",
    )

    spec = PREDICTION["deleted_surface"]["must_fire"]
    ok, secs = wait_for(lambda: rule_state(ABSENT_ALERT) == "firing", timeout=900, poll=15)
    check(
        ok,
        f"{ABSENT_ALERT} (A-13) FIRED {round(time.time() - t0, 1)}s after the wipe "
        f"(predicted ~{spec['after_about_seconds']}s + detection)",
    )
    at_am, _ = wait_for(lambda: alertmanager_holds(ABSENT_ALERT), timeout=180, poll=10)
    check(at_am, f"Alertmanager holds {ABSENT_ALERT}")

    negative = rule_state(CANARY_ALERT)
    check(
        negative != "firing",
        f"THE LOAD-BEARING NEGATIVE: A-12 stayed {negative} through a total loss of the "
        "watchdog's surface — `time() - stamp < 1800` over zero series is zero series, not "
        "a stale reading, so A-12 cannot see its own absence. That is A-13's whole reason "
        "to exist, demonstrated rather than asserted",
    )

    run_reader()
    cleared, csecs = wait_for(lambda: rule_state(ABSENT_ALERT) == "inactive", timeout=420, poll=10)
    check(
        cleared,
        f"{ABSENT_ALERT} cleared {round(csecs, 1)}s after the reader pushed again — "
        "and the board ends carrying the truth, not a silence",
    )
    return {
        "fired_after_seconds": round(time.time() - t0, 1),
        "reached_alertmanager": at_am,
        "a12_state_during": negative,
        "cleared_after_seconds": round(csecs, 1),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase",
        default="all",
        choices=("predict", "health", "empty", "unreachable", "absent", "all"),
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="write the prediction and inject nothing"
    )
    args = parser.parse_args(argv)

    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    PREDICTION_FILE.write_text(json.dumps(PREDICTION, indent=2) + "\n")
    say(f"prediction written FIRST: {PREDICTION_FILE.relative_to(REPO_ROOT)}")
    if args.dry_run or args.phase == "predict":
        say("--dry-run: nothing was injected.")
        return 0

    check = Checks()
    am = start_forward("svc/prometheus-alertmanager", "monitoring", ALERTMANAGER_PORT, 9093)
    gw = start_forward(
        "svc/prometheus-prometheus-pushgateway", "monitoring", GATEWAY_PORT, 9091
    )
    gateway_url = f"http://localhost:{GATEWAY_PORT}"
    observed: dict[str, Any] = {}
    try:
        if args.phase in ("health", "all"):
            observed["health"] = phase_health(check)
        if args.phase in ("empty", "all"):
            observed["empty"] = phase_empty(check, gateway_url)
        if args.phase in ("unreachable", "all"):
            observed["unreachable"] = phase_unreachable(check)
        if args.phase in ("absent", "all"):
            observed["absent"] = phase_absent(check, gateway_url)
    finally:
        for process in (am, gw):
            stop_forward(process)
            process.wait(timeout=10)

    record = {
        "story": "M9-S2",
        "phase": args.phase,
        "recorded_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "prediction": PREDICTION,
        "observed": observed,
        "checks": check.rows,
        "failures": check.failures,
    }
    out = RECORD_DIR / f"drill-{args.phase}.json"
    out.write_text(json.dumps(record, indent=2) + "\n")
    say(f"record: {out.relative_to(REPO_ROOT)}")
    if check.failures:
        say(f"RED — {check.failures} check(s) failed of {len(check.rows)}.")
        return 1
    say(f"PASSED — {len(check.rows)} check(s), 0 failures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
