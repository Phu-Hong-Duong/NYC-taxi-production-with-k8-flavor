#!/usr/bin/env python
"""Make A-4's two series exist: what the wire serves, and what the registry points at.

M7-S3, F-035's second half — and the reason it was impossible until now is worth
restating, because it is a fact about the platform and not about effort. F-034
(M6-S1, measured): **no mlserver metric carries the model version** — every
sample is labelled `version="None"` — and MLflow exports no Prometheus metrics at
all. A-4 is `served != registry`, and there were not two series to compare. It
was never a threshold problem; there was no data.

This script makes the data, by asking the two systems that DO know:

  * the **endpoint**, for one real prediction — because the version is stamped on
    the ANSWER (M5-S2), not available from a metadata call. `GET
    /v2/models/nyc-taxi-eta` reports `versions: []` on this runtime; the answer to
    an infer carries `model_version`. Reading the stamp off the response being
    returned means it cannot describe a different moment than the number beside it.
  * the **registry**, for `models:/nyc-taxi-eta@champion`, through
    `scripts/resolve_champion_storage.py` — the one place the serving path
    resolves the alias (F-009). Nothing here re-implements that resolution.

WHAT THIS DOES NOT DO, STATED SO THE CUT IS A DECISION
-------------------------------------------------------
It does not install a schedule. It is a script proven to push; what runs it on a
cadence lands with **M7-S4**, the story that installs a scheduler. That is why
A-4's rule carries a freshness clause (`< 1800`): until a cadence exists, a
stale pair must not read as a healthy service, and `verify-m5` §2 remains the
check that actually runs at every gate and asks the endpoint directly.

IT READS THE ALIAS AND NEVER WRITES IT. M7 law 3 reserves alias moves for the
gate; an AST test asserts no registry-mutating verb appears in this file.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from taxi_mlops.monitoring.pushgateway import (  # noqa: E402
    DEFAULT_IN_CLUSTER_URL,
    Metric,
    push_metrics,
)

JOB = "taxi-serving-version"
SERVED_METRIC = "taxi_serving_model_version"
REGISTRY_METRIC = "taxi_registry_champion_version"
FRESHNESS_METRIC = "taxi_serving_version_last_run_timestamp_seconds"


def served_version(route: str, name: str, namespace: str) -> tuple[int | None, str]:
    """Ask the ENDPOINT, by making it answer. Returns (version, how-it-was-read)."""
    out = subprocess.run(  # noqa: S603
        [
            "uv", "run", "python", "-m", "taxi_mlops.serving",
            "--route", route, "--name", name, "--namespace", namespace,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        return None, f"the endpoint did not answer (exit {out.returncode})"
    for line in out.stdout.splitlines():
        if "version" in line and "served by" in line:
            for token in line.split():
                if token.isdigit():
                    return int(token), line.strip()
    return None, "the endpoint answered but stamped no version on its response"


def registry_version() -> tuple[int | None, str]:
    """Ask the REGISTRY, through the one resolver the serving path uses (F-009)."""
    out = subprocess.run(  # noqa: S603
        ["uv", "run", "python", "scripts/resolve_champion_storage.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        return None, f"the registry did not answer (exit {out.returncode})"
    payload = json.loads(out.stdout)
    return int(payload["version"]), f"models:/{payload.get('name', '?')}@champion"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pushgateway", default=DEFAULT_IN_CLUSTER_URL)
    parser.add_argument("--route", default="http://localhost:8081")
    parser.add_argument("--name", default="nyc-taxi-eta")
    parser.add_argument("--namespace", default="serving")
    parser.add_argument(
        "--no-push", action="store_true", help="read both sides and print; push nothing"
    )
    args = parser.parse_args(argv)

    served, served_how = served_version(args.route, args.name, args.namespace)
    registry, registry_how = registry_version()
    print(f"[a-4] served   : {served}  ({served_how})")
    print(f"[a-4] registry : {registry}  ({registry_how})")

    if served is None or registry is None:
        # A missing reading is NOT pushed as a zero. A gauge of 0 against a
        # registry gauge of 2 is a MISMATCH, so pushing a placeholder would
        # page an on-call for an unreadable endpoint — the alert would be
        # right about its own arithmetic and wrong about the world.
        print(
            "[a-4] REFUSING to push: one side is unreadable, and a placeholder would "
            "be indistinguishable from a real mismatch.",
            file=sys.stderr,
        )
        return 1

    if served == registry:
        print(f"[a-4] agree: the wire and the registry are both version {served}")
    else:
        print(f"[a-4] MISMATCH: the wire serves {served}, @champion is {registry}")

    if args.no_push:
        print("[a-4] --no-push: nothing was pushed.")
        return 0

    target = push_metrics(
        [
            Metric(
                name=SERVED_METRIC,
                value=float(served),
                help="Registry version the live endpoint stamped on a real prediction.",
                labels={"model": args.name, "namespace": args.namespace},
            ),
            Metric(
                name=REGISTRY_METRIC,
                value=float(registry),
                help="Registry version that models:/<name>@champion currently resolves to.",
                labels={"model": args.name, "namespace": args.namespace},
            ),
            Metric(
                name=FRESHNESS_METRIC,
                value=float(time.time()),
                help=(
                    "Unix time of this reader's last successful run. A-4's rule requires "
                    "it: a stale pushed pair agrees with itself forever."
                ),
                labels={"model": args.name, "namespace": args.namespace},
            ),
        ],
        url=args.pushgateway,
        job=JOB,
        grouping={"model": args.name},
    )
    print(f"[a-4] pushed 3 series -> {target}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.URLError as error:
        print(f"[a-4] push failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
