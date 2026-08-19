"""Stop the InferenceService, start it again, and TIME both halves (M5-S5).

The runbook (`docs/runbooks/serving.md`) types four procedures: deploy, stop,
start, rollback. Three of them are rehearsed and this script is how — it runs
the exact commands the runbook prints and records what they cost, so the
runbook quotes an observation instead of a hope (the M5-S4 lesson: never print
a number without the shape it was measured in).

WHY STOP/START IS REHEARSED AND ROLLBACK IS NOT. Stopping touches one
annotation on one InferenceService: no registry pointer moves, no config
changes, and removing the annotation is an exact undo. A rollback moves
`@champion`, and M5 is legislated alias-neutral (kickoff law 2) — so the
rollback is TYPED, argued, and honestly labelled un-rehearsed, the same
asymmetry `scripts/platform_backup.sh` states about restore.

It is a DRILL, not a gate: it mutates the thing it measures on purpose, and
`make verify-m5` only ever READS the record it writes. Expect ~15-60 s of
deliberate unavailability while it runs.

Usage: uv run python scripts/serving_stop_start_rehearsal.py
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import time
import urllib.request

NS = "serving"
NAME = "nyc-taxi-eta"
HOST = "nyc-taxi-eta-serving.local"
READY_URL = f"http://localhost:8081/v2/models/{NAME}/ready"
RECORD = pathlib.Path("automation/runs/m5-s5/stop-start.json")

#: The two commands the runbook types. They live here as data so the runbook,
#: this drill and the gate all quote ONE string (F-017: derived, never retyped).
STOP_COMMAND = (
    f"kubectl -n {NS} annotate inferenceservice {NAME} "
    "serving.kserve.io/stop=true --overwrite"
)
START_COMMAND = f"kubectl -n {NS} annotate inferenceservice {NAME} serving.kserve.io/stop-"

K = ["kubectl", "--context", "kind-mlops-taxi", "-n", NS]


def sh(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), capture_output=True, text=True)


def _json(*args: str) -> dict:
    out = sh(*args).stdout.strip()
    return json.loads(out) if out.startswith("{") else {}


def isvc() -> dict:
    return _json(*K, "get", "inferenceservice", NAME, "-o", "json")


def replicas() -> tuple[int | None, int]:
    deploy = _json(*K, "get", "deploy", f"{NAME}-predictor", "-o", "json")
    return deploy.get("spec", {}).get("replicas"), deploy.get("status", {}).get("readyReplicas", 0)


def conditions(doc: dict) -> dict[str, str]:
    return {c["type"]: c["status"] for c in doc.get("status", {}).get("conditions", [])}


def answering() -> bool:
    """Does the route answer for this model right now? The only honest 'up'."""
    req = urllib.request.Request(READY_URL, headers={"Host": HOST}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001 — any failure is 'not answering', which is the fact
        return False


def main() -> int:
    record: dict = {"story": "M5-S5", "phase": "stop-start-rehearsal"}
    before = isvc()
    spec, ready = replicas()
    record["before"] = {
        "conditions": conditions(before),
        "annotations": before.get("metadata", {}).get("annotations", {}),
        "answering": answering(),
        "spec_replicas": spec,
        "ready_replicas": ready,
    }
    print("[stop-start] before:", json.dumps(record["before"])[:400])
    if not record["before"]["answering"]:
        print("[stop-start] REFUSED: the endpoint is not answering before the drill — "
              "a stop drill against a stopped service measures nothing")
        return 2

    # ---- stop -------------------------------------------------------------
    t0 = time.time()
    out = sh(*K, "annotate", "inferenceservice", NAME, "serving.kserve.io/stop=true", "--overwrite")
    record["stop_command"] = STOP_COMMAND
    record["stop_stdout"] = (out.stdout + out.stderr).strip()
    print("[stop-start]", record["stop_stdout"])

    record["seconds_to_stop"] = None
    for _ in range(90):
        time.sleep(1)
        spec, ready = replicas()
        if (spec in (0, None)) and not answering():
            record["seconds_to_stop"] = round(time.time() - t0, 2)
            record["after_stop"] = {
                "conditions": conditions(isvc()),
                "spec_replicas": spec,
                "ready_replicas": ready,
                "pods": sh(*K, "get", "pods", "--no-headers").stdout.strip(),
            }
            break
    print(f"[stop-start] stopped after {record['seconds_to_stop']} s: "
          f"{json.dumps(record.get('after_stop', {}))[:400]}")

    # ---- start ------------------------------------------------------------
    t1 = time.time()
    out = sh(*K, "annotate", "inferenceservice", NAME, "serving.kserve.io/stop-")
    record["start_command"] = START_COMMAND
    record["start_stdout"] = (out.stdout + out.stderr).strip()
    print("[stop-start]", record["start_stdout"])

    record["seconds_to_serve_again"] = None
    for _ in range(300):
        time.sleep(1)
        if answering():
            record["seconds_to_serve_again"] = round(time.time() - t1, 2)
            break
    spec, ready = replicas()
    record["after_start"] = {
        "conditions": conditions(isvc()),
        "annotations": isvc().get("metadata", {}).get("annotations", {}),
        "pods": sh(*K, "get", "pods", "-o", "wide", "--no-headers").stdout.strip(),
        "spec_replicas": spec,
        "ready_replicas": ready,
        "answering": answering(),
    }
    print(f"[stop-start] answering again after {record['seconds_to_serve_again']} s")
    print(json.dumps(record["after_start"], indent=1)[:900])

    record["passed"] = bool(
        record["seconds_to_stop"] is not None
        and record["seconds_to_serve_again"] is not None
        and record["after_start"]["answering"]
        and "serving.kserve.io/stop" not in record["after_start"]["annotations"]
    )
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(record, indent=2) + "\n")
    print(f"[stop-start] {'PASSED' if record['passed'] else 'FAILED'} — record: {RECORD}")
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
