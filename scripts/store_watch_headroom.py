#!/usr/bin/env python
"""The headroom leg for the online-store watchdog — facts first, bars afterwards.

M9-S2, and it runs BEFORE `docs/slo_serving.md` §9 is written, before any rule
exists and before the drill that first crosses a bar. That order is M8 law 4
(ninth inheritance) and it is checkable from git rather than asserted here: the
commit that ADDS the section arguing the bars must precede the commit that adds
the drill record judging them.

**IT ISSUES NO VERDICT AND CONTAINS NO THRESHOLD.** M5-S4's load drill and
M7-S3's drift job established the shape: a reader that measures and does not
judge, so the numbers stay re-interpretable after the fact and a bar can never be
set equal to the quantity it was just handed. A unit test asserts no bar-shaped
constant lives in this file.

WHAT IT MEASURES, AND WHY EACH ONE DECIDES SOMETHING
-----------------------------------------------------
1. **The expected key count, DERIVED from the sources.** The online store's
   `DBSIZE` is not a magic number: Feast writes one Redis key per distinct
   ENTITY KEY per view, so the count is the sum of distinct entity keys across
   `data/feast/*.parquet`. If that sum equals what the materialization recorded,
   the store's size has a source of truth that is not itself — which means a
   rule can compare the store against its sources and need no threshold at all.
   That is the whole difference between a bar somebody chose and a property.

2. **The composition, per view.** The transformer — the only rider-facing reader
   of this store (M8-S4 leg 3) — eats `zone_static` and `calendar_day_flags` and
   nothing else (F-059). Their share of the key count is what decides whether a
   count-based bar can protect a rider at all.

3. **What the store is CONFIGURED to be unable to do**: `maxmemory-policy`. With
   `noeviction` (ADR-012, a correctness setting and not tuning) there is no
   mechanism by which this store silently sheds a fraction of its keys — so the
   failure population is bimodal, full or gone, and a bar placed anywhere inside
   the gap catches the same events. That is an argument for not agonising over
   the number, and for preferring the property.

4. **The recorded refusal classes of the reader in front of it** and **the
   recorded cost of refilling it** — the two numbers that decide whether the
   drill's undo is cheap and what the drill should predict.

5. **The pushgateway's persistence facts.** An `absent()` rule is only honest on
   a gateway whose store survives a pod (F-050 (a)+(b), decided together at the
   M7->M8 boundary). This reads back that the volume is still there, because
   inheriting the argument without re-checking its precondition is how a rule
   becomes a page for a laptop being switched off.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

RECORD_DIR = REPO_ROOT / "automation" / "runs" / "m9-store-watch"
RECORD = RECORD_DIR / "headroom.json"

MATERIALIZE_RECORD = REPO_ROOT / "automation" / "runs" / "m8-online" / "materialize.json"
TRANSFORMER_ACCEPT = (
    REPO_ROOT / "automation" / "runs" / "m8-transformer" / "transformer-deploy.json"
)
PERSISTENCE_RECORD = REPO_ROOT / "automation" / "runs" / "m8-drift" / "persistence.json"

#: One entry per published source: the parquet, and the columns Feast keys it on.
#: Read off `infra/feast/feature_repo/definitions.py`'s entities rather than
#: invented — the join keys are the same strings the feature server answers to.
VIEWS: dict[str, dict[str, Any]] = {
    "zone_static": {"file": "zone_static.parquet", "entity": ["zone_id"]},
    "calendar_day_flags": {"file": "calendar_day.parquet", "entity": ["date_key"]},
    "od_window_stats": {
        "file": "od_window_stats.parquet",
        "entity": ["PULocationID", "DOLocationID"],
    },
    "pu_hour_window_stats": {
        "file": "pu_hour_window_stats.parquet",
        "entity": ["PULocationID", "hour"],
    },
}

#: The views the TRANSFORMER actually reads (M8-S4 leg 3; F-059 keeps the borough
#: dictionary and the airport constant on the committed side of the wall).
TRANSFORMER_VIEWS = ("zone_static", "calendar_day_flags")

NAMESPACE = "feast"


def _kubectl(*args: str) -> str:
    out = subprocess.run(  # noqa: S603
        ["kubectl", "--context", "kind-mlops-taxi", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        raise RuntimeError(f"kubectl {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout.strip()


def derived_expected_keys() -> dict[str, Any]:
    """One Redis key per distinct entity key per view — computed from the parquet."""
    import duckdb

    per_view: dict[str, int] = {}
    for name, spec in VIEWS.items():
        path = REPO_ROOT / "data" / "feast" / spec["file"]
        if not path.exists():
            raise RuntimeError(
                f"{path} is missing — the expected key count is DERIVED from the published "
                "sources, and a derivation with no source is a typed constant in disguise. "
                "Run: make feast-sources"
            )
        keys = ", ".join(spec["entity"])
        expr = keys if len(spec["entity"]) == 1 else f"({keys})"
        per_view[name] = int(
            duckdb.sql(f"select count(distinct {expr}) from '{path.as_posix()}'").fetchone()[0]
        )
    total = sum(per_view.values())
    transformer = sum(per_view[v] for v in TRANSFORMER_VIEWS)
    return {
        "per_view": per_view,
        "total": total,
        "transformer_dependency_keys": transformer,
        "transformer_dependency_share": transformer / total if total else None,
        "derived_from": "count(distinct <entity keys>) over data/feast/*.parquet",
    }


def live_store() -> dict[str, Any]:
    pod = _kubectl(
        "-n", NAMESPACE, "get", "pod", "-l", "app=redis",
        "-o", "jsonpath={.items[0].metadata.name}",
    )
    dbsize = int(_kubectl("-n", NAMESPACE, "exec", pod, "--", "redis-cli", "DBSIZE"))
    policy = _kubectl(
        "-n", NAMESPACE, "exec", pod, "--", "redis-cli", "CONFIG", "GET", "maxmemory-policy"
    ).splitlines()[-1].strip()
    maxmemory = int(
        _kubectl(
            "-n", NAMESPACE, "exec", pod, "--", "redis-cli", "CONFIG", "GET", "maxmemory"
        ).splitlines()[-1].strip()
    )
    return {"pod": pod, "dbsize": dbsize, "maxmemory_policy": policy, "maxmemory_bytes": maxmemory}


def gateway_persistence() -> dict[str, Any]:
    """The precondition an `absent()` rule rests on, re-checked rather than inherited."""
    claim = _kubectl(
        "-n", "monitoring", "get", "deploy", "prometheus-prometheus-pushgateway",
        "-o", "jsonpath={.spec.template.spec.containers[0].args}",
    )
    pvc = _kubectl(
        "-n", "monitoring", "get", "pvc",
        "-o", "jsonpath={range .items[*]}{.metadata.name}={.status.phase} {end}",
    )
    return {
        "pushgateway_args": claim,
        "persistence_file_flag": "--persistence.file" in claim,
        "monitoring_pvcs": pvc.strip(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-write", action="store_true", help="print; record nothing")
    args = parser.parse_args(argv)

    materialize = json.loads(MATERIALIZE_RECORD.read_text())
    accept = json.loads(TRANSFORMER_ACCEPT.read_text())
    persistence = json.loads(PERSISTENCE_RECORD.read_text()) if PERSISTENCE_RECORD.exists() else {}

    expected = derived_expected_keys()
    live = live_store()

    print("[headroom] --- what the store IS, derived from the sources it was filled from ---")
    for name, count in expected["per_view"].items():
        share = count / expected["total"] * 100
        mark = "  <- the transformer reads this" if name in TRANSFORMER_VIEWS else ""
        print(f"[headroom]   {name:24s} {count:>7,} distinct entity keys  ({share:5.2f}%){mark}")
    print(f"[headroom]   {'TOTAL (derived)':24s} {expected['total']:>7,}")
    print(f"[headroom]   {'recorded by materialize':24s} {materialize['store']['dbsize']:>7,}"
          f"   ({MATERIALIZE_RECORD.relative_to(REPO_ROOT)})")
    print(f"[headroom]   {'live DBSIZE':24s} {live['dbsize']:>7,}")
    agree = expected["total"] == materialize["store"]["dbsize"] == live["dbsize"]
    print(f"[headroom]   three witnesses agree: {agree}")
    print(
        f"[headroom]   the TRANSFORMER's whole dependency is "
        f"{expected['transformer_dependency_keys']:,} keys = "
        f"{expected['transformer_dependency_share'] * 100:.3f}% of the store"
    )

    print("[headroom] --- what the store cannot do, by configuration ---")
    print(f"[headroom]   maxmemory-policy = {live['maxmemory_policy']} "
          f"(maxmemory {live['maxmemory_bytes']:,} bytes; used at materialization "
          f"{materialize['store']['used_memory_human']})")

    print("[headroom] --- the cost of the undo, recorded ---")
    print(f"[headroom]   a full re-materialization took {materialize['elapsed_seconds']}s "
          f"on {materialize['recorded_at']}")

    print("[headroom] --- the reader in front of the store, recorded ---")
    print(f"[headroom]   a healthy quote: {accept['minutes']} minutes, "
          f"model_version={accept['model_version']!r}")
    print(f"[headroom]   an uncovered date: HTTP {accept['past_horizon']['status']} "
          "(StoreCoverageError — the CALENDAR half refuses)")
    print("[headroom]   an unreachable store: HTTP 503 (FeatureStoreUnavailable) — "
          "src/taxi_mlops/serving/transformer.py")

    print("[headroom] --- the precondition an absent() rule rests on ---")
    gateway = gateway_persistence()
    flag = gateway["persistence_file_flag"]
    print(f"[headroom]   pushgateway --persistence.file present: {flag}")
    print(f"[headroom]   monitoring PVCs: {gateway['monitoring_pvcs']}")

    payload = {
        "story": "M9-S2",
        "leg": "headroom — measured BEFORE docs/slo_serving.md §9 argues any bar",
        "recorded_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expected_keys": expected,
        "live_store": live,
        "materialization": {
            "recorded_at": materialize["recorded_at"],
            "dbsize": materialize["store"]["dbsize"],
            "elapsed_seconds": materialize["elapsed_seconds"],
            "used_memory_human": materialize["store"]["used_memory_human"],
            "window": materialize["window"],
        },
        "three_witnesses_agree": agree,
        "reader_in_front": {
            "healthy_minutes": accept["minutes"],
            "healthy_model_version": accept["model_version"],
            "uncovered_date_status": accept["past_horizon"]["status"],
            "uncovered_date_error_class": "StoreCoverageError (QuoteRefused, http_status 422)",
            "unreachable_store_status": 503,
            "unreachable_error_class": "FeatureStoreUnavailable",
            "source": "automation/runs/m8-transformer/transformer-deploy.json + "
                      "src/taxi_mlops/serving/{feature_store,transformer}.py",
        },
        "gateway": gateway,
        "gateway_persistence_drill": {
            "record": str(PERSISTENCE_RECORD.relative_to(REPO_ROOT)),
            "survived_pod_delete": bool(persistence),
        },
        "issues_no_verdict": (
            "This leg measures. Every bar argued from it lives in docs/slo_serving.md §9, "
            "and every rule implementing one lives in infra/monitoring/alerting_rules.yml."
        ),
    }

    if args.no_write:
        print("[headroom] --no-write: nothing was recorded.")
        return 0
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"[headroom] record: {RECORD.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
