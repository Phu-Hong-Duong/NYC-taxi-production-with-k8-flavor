"""Backfill F-048's scale provenance onto registry versions that predate the tags.

**Why this exists.** `taxi_mlops.training.retrain` has to know what SCALE a
champion's count-scaled knobs were chosen at — that number is F-020's divisor.
Until M8-S1 it lived only in the tracked host records under `automation/runs/`,
which `.dockerignore` correctly keeps out of the task image, so the scheduled
retrain resolved it to nothing and reported the absence as "this champion had no
sampled search behind it": a sentence that was true about what the pod could see
and false about the world (F-048). The fix puts the fact where the fact belongs —
on the version — and this script is how the versions that already exist get it.

**What it will and will not do.** It writes three tags, through
`registry.record_search_scale`, which is the additive path inside the one module
allowed to touch the registry: no version is created, nothing is deleted, and no
alias is read or moved. Re-running is a no-op; re-running with different numbers
is refused by that function rather than overwriting a claim about a fit that has
already happened.

**Every number is DERIVED, never typed.** A version's run id is matched against
`refit-*.json`, that record names its study, and the study's `sniper-*.json`
carries the row count and the per-trial round cap. A version whose run matches no
refit record is recorded as the explicit "no sampled search" — which is a fact
this script can establish only because it can see the records directory, and is
exactly the distinction the resolver's refusal is about.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from taxi_mlops.data.config import repo_root
from taxi_mlops.training import registry as registry_mod
from taxi_mlops.training.run import load_train_config


def scale_for_run(run_id: str, records_dir: str) -> tuple[int | None, int | None, str]:
    """(chosen_at_rows, round_cap, source) for a run, from the tracked records."""
    root = repo_root() / records_dir
    if not root.exists():
        raise SystemExit(
            f"[backfill] {records_dir} does not exist here. This script is the one place "
            "that turns the host records into version provenance, so it must be run "
            "where those records are — the whole point is that nothing else has to be."
        )
    for path in sorted(root.glob("refit-*.json")):
        row = json.loads(path.read_text())
        if str(row.get("run_id")) != run_id:
            continue
        sniper = root / f"sniper-{path.stem.split('-', 1)[1]}.json"
        if not sniper.exists():
            raise SystemExit(
                f"[backfill] {path} names study {row.get('study')!r} but {sniper} is "
                "missing — the scale is only knowable from the sniper's own record"
            )
        record = json.loads(sniper.read_text())
        if record.get("study") != row.get("study"):
            raise SystemExit(
                f"[backfill] {sniper} records study {record.get('study')!r}, "
                f"not {row.get('study')!r}"
            )
        return (
            int(record["train_rows"]),
            int(record["max_rounds"]),
            f"{sniper.relative_to(repo_root())} (study {record['study']}, "
            f"sample_fraction {record.get('sample_fraction')}), backfilled by "
            f"{Path(__file__).name}",
        )
    return None, None, (
        f"no refit record under {records_dir} names run {run_id}: this version's "
        "params were not chosen on a sample, so there is no transfer to make"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records-dir", default="automation/runs/m3s4")
    parser.add_argument("--version", default="", help="one version; default is all of them")
    parser.add_argument("--dry-run", action="store_true", help="resolve and print, write nothing")
    args = parser.parse_args()

    import mlflow

    from taxi_mlops.training import tracking

    train_cfg = load_train_config()
    tracking.configure(train_cfg["mlflow"])
    client = mlflow.MlflowClient()
    model_name = train_cfg["registry"]["model_name"]

    versions: list[Any] = sorted(
        client.search_model_versions(f"name='{model_name}'"), key=lambda v: int(v.version)
    )
    if args.version:
        versions = [v for v in versions if str(v.version) == str(args.version)]
        if not versions:
            raise SystemExit(f"[backfill] {model_name} has no version {args.version}")

    print("=" * 78)
    print(f"[backfill] {model_name}: {len(versions)} version(s)"
          + ("  — DRY RUN, nothing will be written" if args.dry_run else ""))
    changed = 0
    for version in versions:
        already = registry_mod.read_search_scale(getattr(version, "tags", None))
        rows, cap, source = scale_for_run(str(version.run_id), args.records_dir)
        shown = "no sampled search" if rows is None else f"{rows:,} rows, cap {cap}"
        print(f"[backfill] version {version.version} (run {str(version.run_id)[:12]}…): {shown}")
        print(f"[backfill]            source: {source}")
        if already is not None:
            print(f"[backfill]            already recorded: {already[0]} / {already[1]}")
        if args.dry_run:
            continue
        result = registry_mod.record_search_scale(
            client, model_name=model_name, version=str(version.version),
            chosen_at_rows=rows, round_cap=cap, source=source,
        )
        if result["written"]:
            changed += 1
            print(f"[backfill]            WROTE {', '.join(result['written'])}")
        else:
            print("[backfill]            unchanged (already carries exactly this)")
    print(f"[backfill] {changed} version(s) changed; no alias was read or moved, "
          "no version was created, nothing was deleted")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
