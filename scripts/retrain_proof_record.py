"""Read what the SCHEDULED retrain actually resolved, off the control plane. F-048's proof.

A trigger that is registered and a trigger that fires look identical in a
configuration table (gotcha #81, one layer up), and a pod that resolves F-020's
transfer looks identical to one that silently does not — the only difference is a
`null` in a field. `make retrain-schedule` proves the first half by reading the
triggers back off the server. This reads the second half: it finds the most recent
firing of `retrain-schedule-proof`, takes the record the POD returned as its
output, and writes it down.

**It is a READER.** It launches nothing, aborts nothing, promotes nothing and
touches no alias — it asks the server what already happened. The pod's own JSON is
carried through verbatim into the record beside a small verdict block, so a
reviewer compares the same numbers the pod produced rather than a retelling.

The two numbers that close F-048 are `rescale_factor` **6.6667** and `round_cap`
**2400** — what the HOST resolved for the same champion in the same minute, and
what a pod could not resolve at all until the scale moved onto the version.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import flyte

from taxi_mlops.data.config import repo_root

DEFAULT_TASK = "taxi-pipeline-train.retrain"
DEFAULT_RECORD_DIR = "automation/runs/m8-provenance"
#: What the host resolves for champion version 2 (M7-S4's own numbers, and the
#: closing condition F-048's ledger row states). They are compared, never assumed:
#: a mismatch is the finding still open, not a reason to edit this constant.
EXPECTED = {"rescale_factor": 6.6667, "round_cap": 2400}


def _runs(task: str, limit: int) -> list[Any]:
    """The most recent runs OF THIS TASK, newest first — filtered by the SERVER.

    The unfiltered list comes back OLDEST FIRST, which is how the first version of
    this reader looked through forty runs of M4's pipeline and reported that the
    trigger had never fired. `listall` takes `task_name` and `sort_by`, so the
    question is asked where the answer is rather than reconstructed here — and the
    ordering is then the server's claim rather than this script's assumption.
    """
    from flyte.remote import Run

    async def _go() -> list[Any]:
        out: list[Any] = []
        async for run in Run.listall.aio(
            task_name=task, sort_by=("created_at", "desc"), limit=limit
        ):
            out.append((run, await run.details.aio()))
        return out

    return asyncio.run(_go())


def _payload(run: Any) -> dict[str, Any] | None:
    """The record the POD returned. The task's output is JSON text, by design —
    a verdict travels as content and never as a path (`/app/automation/runs/...`
    on that pod is not a path any other pod has)."""
    try:
        outputs = run.outputs()
    except Exception as exc:  # noqa: BLE001 — a run with no outputs is a normal answer
        print(f"[proof] {run.name}: no readable outputs ({exc})")
        return None
    # `ActionOutputs` is neither a mapping nor a string: `str()` on it gives
    # `ActionOutputs(o0="{...}")`, which json.loads correctly refuses — and the
    # first version of this reader read that refusal as "the trigger has not
    # fired", which is #59's family (an absence inferred from a parse failure).
    # So the accessors are tried explicitly and an unreadable output SAYS so.
    candidates = []
    for accessor in (lambda: outputs["o0"], lambda: outputs.o0, lambda: outputs):
        try:
            candidates.append(accessor())
        except Exception:  # noqa: BLE001, S110 — the next accessor is the answer
            continue
    for value in candidates:
        if not isinstance(value, str):
            continue
        try:
            parsed = json.loads(value)
        except ValueError:
            continue
        if isinstance(parsed, dict) and "rescale_factor" in parsed:
            return parsed
    print(f"[proof] {run.name}: outputs present but not a retrain record ({outputs!r:.80})")
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="localhost:8096")
    parser.add_argument("--project", default="nyc-taxi")
    parser.add_argument("--domain", default="development")
    parser.add_argument("--task", default=DEFAULT_TASK)
    parser.add_argument("--limit", type=int, default=6, help="how many of ITS runs to read")
    parser.add_argument("--out", default="", help="write the record here (tracked JSON)")
    args = parser.parse_args(argv)

    flyte.init(endpoint=args.endpoint, insecure=True, project=args.project, domain=args.domain)

    found: list[dict[str, Any]] = []
    for run, details in _runs(args.task, args.limit):
        payload = _payload(run)
        if payload is None:
            continue
        started = details.pb2.run_spec.run_start_time
        found.append({
            "run": run.name,
            "phase": str(run.phase).replace("ActionPhase.", ""),
            "task_version": details.pb2.action.metadata.task.id.version,
            "started_at": datetime.fromtimestamp(started.seconds, tz=UTC).isoformat()
            if started.seconds else "",
            "record": payload,
        })

    if not found:
        print(f"[proof] no run of {args.task} among the last {args.limit} carried a readable "
              "record — the trigger may not have fired yet since the redeploy")
        return 1

    newest = found[0]
    record = newest["record"]
    print("=" * 78)
    print(f"[proof] run          : {newest['run']}  ({newest['phase']}, {newest['started_at']})")
    print(f"[proof] task version : {newest['task_version']}")
    print(f"[proof] champion     : version {record.get('champion_version')}")
    print(f"[proof] target_rows  : {record.get('target_rows'):,}")
    print(f"[proof] rescale_factor: {record.get('rescale_factor')}")
    print(f"[proof] round_cap     : {record.get('round_cap')}")
    print(f"[proof] decision      : {record.get('decision')}  promoted={record.get('promoted')}")

    checks: list[dict[str, Any]] = []
    factor = record.get("rescale_factor")
    checks.append({
        "check": "the pod resolved F-020's scale transfer",
        "expected": EXPECTED["rescale_factor"],
        "observed": None if factor is None else round(float(factor), 4),
        "passed": factor is not None
        and round(float(factor), 4) == EXPECTED["rescale_factor"],
    })
    checks.append({
        "check": "the pod re-derived the round budget",
        "expected": EXPECTED["round_cap"],
        "observed": record.get("round_cap"),
        "passed": record.get("round_cap") == EXPECTED["round_cap"],
    })
    checks.append({
        "check": "the proof trigger plans only and promotes nothing",
        "expected": True,
        "observed": bool(record.get("plan_only")) and not record.get("promoted"),
        "passed": bool(record.get("plan_only")) and not record.get("promoted"),
    })
    for check in checks:
        flag = "ok  " if check["passed"] else "FAIL"
        print(f"[proof] {flag} {check['check']}: expected {check['expected']}, "
              f"observed {check['observed']}")

    payload = {
        "finding": "F-048",
        "written_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "task": args.task,
        "trigger": "retrain-schedule-proof",
        "expected": EXPECTED,
        "checks": checks,
        "passed": all(check["passed"] for check in checks),
        "run": newest,
        "earlier_runs_seen": [
            {"run": row["run"], "started_at": row["started_at"],
             "task_version": row["task_version"],
             "rescale_factor": row["record"].get("rescale_factor"),
             "round_cap": row["record"].get("round_cap")}
            for row in found
        ],
    }
    if args.out:
        out = repo_root() / args.out if not Path(args.out).is_absolute() else Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, default=str) + "\n")
        print(f"[proof] record -> {out}")
    print("=" * 78)
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
