#!/usr/bin/env python
"""flyte_run_actions.py — what a Flyte run's actions did, and whether they were CACHED.

WHY THIS IS A FILE AND NOT A `flyte get action` INVOCATION. The CLI's action table
prints name and phase. The thing M4-S4's second leg has to prove is neither: it is
`cache_status`, a field the control plane sets per action
(`CatalogCacheStatus`: CACHE_MISS · CACHE_POPULATED · CACHE_HIT · CACHE_DISABLED …)
and the CLI does not render. Without it the only available evidence for "the rerun
reused run 1" is a wall-clock, and a wall-clock is a *symptom* — it is equally
consistent with a machine that was simply less busy the second time. Asking the
server what it recorded is the positive assertion (gotcha #59's rule, applied to a
cache instead of an exit code).

It is a READER. It launches nothing, retries nothing, mutates nothing; the only
thing it can do to a cluster is ask it three questions. That is what makes it safe
for `verify-m4` (M4-S5) to reuse, and reuse is the intent: a gate that re-derives
its own view of a run would be a second definition of "what happened".

Usage (needs a route to the Flyte API — `scripts/run_pipeline.sh` and
`scripts/pipeline_cache_drill.sh` stand one up around it):

    uv run python scripts/flyte_run_actions.py <run-name> [--json] [--endpoint host:port]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

import flyte
from flyteidl2.core import catalog_pb2

# The enum arrives as an int. Rendering it as an int would make every transcript
# in this program require a lookup table to read, so it is named here — once.
CACHE_STATUS_NAMES = {
    value: name
    for name, value in catalog_pb2.CatalogCacheStatus.items()
}

#: The statuses that mean "this action did not run; its result was reused".
HIT = ("CACHE_HIT",)
#: The statuses that mean "this action ran and its result was written to the cache".
POPULATED = ("CACHE_POPULATED",)


def collect(run_name: str) -> list[dict]:
    """Every action of `run_name`, in creation order, with what the server recorded.

    THE LIST VIEW DOES NOT NAME THE TASK — `Action.task_name` comes back empty from
    `listall`, because the list response carries no `metadata.task`. That leaves
    seven opaque ids like `bubrkhgpmdqfk04g3x113g4xj`, and a cache assertion made
    against a positional guess ("the fourth one is train") is an assertion that
    silently re-points itself the day a stage is inserted. So each action's DETAIL
    is fetched, one call apiece, which is where `metadata.task.id.name` lives
    (`taxi-pipeline-train.train`). Seven cheap reads to make the evidence say what
    it means.
    """
    from flyte.remote import Action, ActionDetails

    async def _go() -> list[dict]:
        rows: list[dict] = []
        async for action in Action.listall.aio(for_run_name=run_name):
            detail = await ActionDetails.get.aio(run_name=run_name, name=action.name)
            status = detail.pb2.status
            meta = detail.pb2.metadata
            rows.append(
                {
                    "action": action.name,
                    "task": detail.task_name or action.task_name or "",
                    "short_name": meta.task.short_name if meta.HasField("task") else "",
                    "parent": meta.parent or "",
                    "phase": str(action.phase).replace("ActionPhase.", ""),
                    "cache_status": CACHE_STATUS_NAMES.get(
                        action.pb2.status.cache_status,
                        f"UNKNOWN({action.pb2.status.cache_status})",
                    ),
                    # duration_ms is the server's own number for how long the action
                    # took. A cache hit's is near zero, which is the corroborating
                    # evidence — corroborating, never the claim itself.
                    "duration_ms": int(getattr(action.pb2.status, "duration_ms", 0) or 0),
                    "attempts": int(getattr(status, "attempt", 0) or 0),
                }
            )
        return rows

    return asyncio.run(_go())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_name")
    parser.add_argument("--endpoint", default="localhost:8090")
    parser.add_argument("--project", default="nyc-taxi")
    parser.add_argument("--domain", default="development")
    parser.add_argument("--json", action="store_true", help="machine-readable, for a drill")
    args = parser.parse_args(argv)

    flyte.init(
        endpoint=args.endpoint, insecure=True, project=args.project, domain=args.domain
    )
    rows = collect(args.run_name)
    if args.json:
        json.dump({"run_name": args.run_name, "actions": rows}, sys.stdout, indent=2)
        print()
        return 0
    if not rows:
        print(f"[actions] no actions found for run {args.run_name}")
        return 1
    width = max(len(r["action"]) for r in rows)
    for row in rows:
        label = row["short_name"] or (row["task"] or "(parent)")
        print(
            f"  {row['action']:<{width}}  {label:<16} {row['phase']:<10} "
            f"{row['cache_status']:<16} {row['duration_ms'] / 1000.0:9.1f}s"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised live by the drill
    raise SystemExit(main())
