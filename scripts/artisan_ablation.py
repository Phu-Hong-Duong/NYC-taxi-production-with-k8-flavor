"""The artisan track's iteration loop — one group per experiment, measured.

M3-S3, executed per `docs/artisan_playbook.md` §3 under the Design Review's
decisions:

- **DR-03**: the artisan searches FEATURES and holds hyperparameters at v1's.
  Nothing in this script reads `configs/train.yaml: model.lightgbm` except to
  pass it through unchanged — the automation track (S4) owns that axis, and the
  2×2 bake-off can only answer "features or tuning?" if neither track wanders.
- **DR-02**: a group is KEPT only if it improves relative val MAE by >= 0.50%,
  and KPI-10 is reported for every group beside it (AI-2). Every group declared
  in `configs/features.yaml: groups` is run and reported, survivors and drops —
  a table showing only winners is a garden of forking paths with the forks
  pruned.
- **DR-01**: fitting wall-clock seconds are MEASURED and printed (AI-1), so
  "equal budgets" is a number somebody can check rather than an assertion.
- **DR-05 / playbook §3.0**: the TEST month is not read here. Not once. Every
  number this script prints is val, and val is the report; the gate judges on
  test exactly once per contender, at S5.

Sample-first (playbook §3.1): iteration runs on a stratified ~15% sample and the
survivors are re-measured at full scale before anything is called a keep. The
sample is stratified BY MONTH, because the target mean rises 17.3% Jan->Jun.

Every run lands in MLflow experiment `m3-artisan` — playbook §3.3's "no row, no
claim", enforced by there being nowhere else for the number to come from. The
metric is `taxi_mlops.training.evaluate` and nothing else (gotcha #15).

This script is a .py rather than a heredoc for the reason gotcha #37 records:
the OpenMP shim re-execs the interpreter, and a program fed on stdin cannot be
replayed because the source is gone by then.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import pandas as pd

from taxi_mlops.data.config import load_config
from taxi_mlops.features import aggregates as aggregates_mod
from taxi_mlops.features import quote_time, sets
from taxi_mlops.training import model as model_mod
from taxi_mlops.training.datasets import Split, load_frame
from taxi_mlops.training.evaluate import Metrics, evaluate
from taxi_mlops.training.run import load_train_config

#: Playbook §3.1. 15% of 43,987,422 train rows is ~6.6M — enough that a 0.50%
#: relative MAE difference is far outside sampling noise, small enough that a
#: loop is minutes rather than half an hour.
DEFAULT_SAMPLE = 0.15

#: Fixed, and passed to both the row sample and (through configs/train.yaml)
#: LightGBM. Playbook §3.2: fixed seeds, one change per experiment.
DEFAULT_SEED = 20260817


def _resolve(name: str) -> dict[str, Any]:
    return sets.resolve_set(name)


def _split_for(
    name: str,
    frame: pd.DataFrame,
    months: tuple[str, ...],
    features_cfg: dict[str, Any],
    target: str,
    fitted: aggregates_mod.PointInTimeAggregates | None,
) -> Split:
    matrix = quote_time.build_features(frame, features_cfg, fitted=fitted)
    return Split(name=name, months=months, features=matrix, y=frame[target].astype("float64"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sets",
        default="",
        help="comma-separated set names; default = v1 then every group set, in "
        "configs/features.yaml's declared order (DR-03's fixed order)",
    )
    parser.add_argument("--sample-fraction", type=float, default=DEFAULT_SAMPLE)
    parser.add_argument(
        "--full-scale",
        action="store_true",
        help="no sampling — the confirmation run the playbook requires before a keep",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--experiment", default="m3-artisan")
    parser.add_argument("--story", default="M3-S3")
    parser.add_argument("--no-mlflow", action="store_true", help="smoke path; never a result")
    parser.add_argument(
        "--log-model",
        action="store_true",
        help="log the booster with signature + input example (the v2 deliverable)",
    )
    parser.add_argument("--out", default="", help="write the measured rows here as JSON")
    args = parser.parse_args()

    # BEFORE the reads. `ensure_openmp` re-execs this interpreter once on a host
    # with no system libgomp (gotcha #37, AWAITING_PO 2026-08-17-1), and it is
    # normally triggered by the first `model.fit` — which on this script is
    # several minutes of parquet reading and aggregate fitting later, all of
    # which is then thrown away and done again. Calling it first costs nothing
    # and makes the log linear.
    from taxi_mlops.training.openmp import ensure_openmp

    ensure_openmp()

    train_cfg = load_train_config()
    data_cfg = load_config()
    target = train_cfg["target"]
    eval_cfg = train_cfg["evaluate"]

    names = [n.strip() for n in args.sets.split(",") if n.strip()] or (
        ["v1"] + [f"v1_{g.split('_')[0]}" for g in sets.group_names()]
    )
    resolved = {name: _resolve(name) for name in names}
    fraction = None if args.full_scale else args.sample_fraction

    print("=" * 78)
    print(f"[artisan] experiments : {', '.join(names)}")
    scale = "FULL DATA" if fraction is None else f"{fraction:.0%} sample"
    print(f"[artisan] scale       : {scale}")
    print(f"[artisan] seed        : {args.seed}")
    print("[artisan] hyperparameters are HELD at v1's (DR-03: the artisan searches features)")
    print("[artisan] the TEST month is not read by this script (DR-05, playbook §3.0)")
    print("=" * 78)

    # One narrow read for every experiment: the union of what any set needs.
    columns: list[str] = []
    for cfg in resolved.values():
        for column in quote_time.source_columns(cfg):
            if column not in columns:
                columns.append(column)
    columns.append(target)

    read_started = time.monotonic()
    train_frame, train_months = load_frame(
        "train", data_cfg, columns, sample_fraction=fraction, seed=args.seed
    )
    val_frame, val_months = load_frame(
        "val", data_cfg, columns, sample_fraction=fraction, seed=args.seed
    )
    print(
        f"\n[data] train {len(train_frame):>12,} rows  months={','.join(train_months)}\n"
        f"[data] val   {len(val_frame):>12,} rows  months={','.join(val_months)}\n"
        f"[data] read in {time.monotonic() - read_started:.1f}s "
        "(NOT fitting time — DR-01 condition 3 counts fitting only)"
    )

    # Fitted on TRAIN rows only, point-in-time by month. Built once and shared:
    # every experiment that asks for the aggregates gets the SAME tables, so a
    # difference between two rows of the table is the feature set and nothing else.
    fitted = None
    if any(quote_time.FITTED_FEATURES & set(cfg["derived"]) for cfg in resolved.values()):
        started = time.monotonic()
        fitted = aggregates_mod.fit(train_frame, target)
        print(f"\n{fitted.describe()}")
        print(f"[aggregates] fitted in {time.monotonic() - started:.1f}s")

    rows: list[dict[str, Any]] = []
    reference: Metrics | None = None
    fitting_seconds = 0.0

    for name in names:
        cfg = resolved[name]
        feature_names = quote_time.feature_names(cfg)
        print("\n" + "-" * 78)
        shown = cfg["groups"] or ["-"]
        print(f"[experiment] {name}: {len(feature_names)} features, groups={shown}")
        train_split = _split_for("train", train_frame, train_months, cfg, target, fitted)
        val_split = _split_for("val", val_frame, val_months, cfg, target, fitted)

        started = time.monotonic()
        trained = model_mod.fit(
            train_split,
            val_split,
            train_cfg["model"],
            quote_time.categorical_names(cfg),
            name=f"artisan-{name}",
        )
        seconds = time.monotonic() - started
        fitting_seconds += seconds
        metrics = evaluate(
            f"artisan-{name}", "val", val_split.y.to_numpy(), trained.predict(val_split.features),
            eval_cfg,
        )
        if reference is None:
            reference = metrics
        delta_pct = 100.0 * (reference.mae - metrics.mae) / reference.mae
        delta_within = metrics.within_tolerance_rate - reference.within_tolerance_rate
        row = {
            "set": name,
            "groups": cfg["groups"],
            "n_features": len(feature_names),
            "features": feature_names,
            "val_mae": metrics.mae,
            "val_within_rate": metrics.within_tolerance_rate,
            "delta_mae_pct": delta_pct,
            "delta_within_points": delta_within,
            "best_iteration": trained.best_iteration,
            "fit_seconds": seconds,
            "train_rows": len(train_split),
            "val_rows": len(val_split),
            "run_id": None,
        }
        print(
            f"[experiment] {name}: val MAE {metrics.mae:.4f} min "
            f"({delta_pct:+.2f}% vs {reference.contender}) · KPI-10 "
            f"{metrics.within_tolerance_rate:.3f}% ({delta_within:+.3f} pts) · "
            f"best_iteration {trained.best_iteration} · fit {seconds:.1f}s"
        )

        if not args.no_mlflow:
            row["run_id"] = _log(
                args, train_cfg, cfg, trained, metrics, row, train_split, val_split, fitted
            )
        rows.append(row)
        del train_split, val_split, trained

    print("\n" + "=" * 78)
    print(_table(rows, train_cfg))
    print("=" * 78)
    print(
        f"[budget] measured FITTING wall-clock this invocation: {fitting_seconds:,.1f}s "
        f"(DR-01 AI-1). Reading, building matrices and writing the ledger are free "
        "on both tracks, so they are not counted."
    )
    if args.out:
        Path(args.out).write_text(
            json.dumps({"fitting_seconds": fitting_seconds, "rows": rows}, indent=2) + "\n"
        )
        print(f"[artisan] measured rows written to {args.out}")
    return 0


def _table(rows: list[dict[str, Any]], train_cfg: dict[str, Any]) -> str:
    bar = 0.50
    out = [
        "| experiment | groups | features | val MAE | Δ val MAE | KPI-10 | Δ KPI-10 | "
        "best iter | fit s | verdict |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for index, row in enumerate(rows):
        if index == 0:
            verdict = "reference"
            delta = "—"
            delta_within = "—"
        else:
            kept = row["delta_mae_pct"] >= bar
            lowers = row["delta_within_points"] < 0
            verdict = (
                "**KEEP**" if kept and not lowers
                else ("ESCALATE — mean up, KPI-10 down" if kept else "drop")
            )
            delta = f"{row['delta_mae_pct']:+.2f}%"
            delta_within = f"{row['delta_within_points']:+.3f}"
        out.append(
            f"| `{row['set']}` | {', '.join(row['groups']) or '-- (base)'} | "
            f"{row['n_features']} | "
            f"{row['val_mae']:.4f} | {delta} | {row['val_within_rate']:.3f}% | {delta_within} | "
            f"{row['best_iteration']} | {row['fit_seconds']:.0f} | {verdict} |"
        )
    return "\n".join(out)


def _log(
    args: argparse.Namespace,
    train_cfg: dict[str, Any],
    features_cfg: dict[str, Any],
    trained: model_mod.TrainedModel,
    metrics: Metrics,
    row: dict[str, Any],
    train_split: Split,
    val_split: Split,
    fitted: aggregates_mod.PointInTimeAggregates | None,
) -> str:
    import mlflow
    from mlflow.models import infer_signature

    from taxi_mlops.training import tracking

    tracking.configure(train_cfg["mlflow"])
    mlflow.set_experiment(args.experiment)
    with mlflow.start_run(run_name=trained.name) as active:
        mlflow.set_tags(
            {
                "story": args.story,
                "milestone": args.story.split("-")[0],
                "role": "MLE",
                "track": "artisan",
                "feature_set": features_cfg["version"],
                "feature_groups": ",".join(features_cfg["groups"]) or "none",
                "metric_source": "taxi_mlops.training.evaluate",
                "train_months": ",".join(train_split.months),
                "val_month": ",".join(val_split.months),
                # DR-05 §2 / F-008: a sampled number is scout-internal and can
                # never be a verdict. Said on the run, where somebody who finds
                # it in six months will be looking.
                "sample_run": "no" if args.full_scale else "yes",
                "do_not_promote": (
                    "no — full-data fit; the gate sees it at M3-S5"
                    if args.full_scale
                    else f"yes — {args.sample_fraction:.0%} sample (F-008)"
                ),
                "aggregates_point_in_time": (
                    "n/a"
                    if fitted is None
                    else ("yes" if fitted.point_in_time else "NO — RED TEAM")
                ),
            }
        )
        mlflow.log_params(
            {
                **dict(trained.params),
                "feature_set": features_cfg["version"],
                "features": ",".join(row["features"]),
                "n_features": row["n_features"],
                "best_iteration": trained.best_iteration,
                "sample_fraction": "1.0" if args.full_scale else str(args.sample_fraction),
                "sample_seed": args.seed,
                "train_rows": row["train_rows"],
            }
        )
        mlflow.log_metrics({**metrics.as_mlflow_metrics(), "fit_seconds": row["fit_seconds"]})
        if args.log_model:
            example = val_split.features.head(5).copy()
            mlflow.lightgbm.log_model(
                trained.booster,
                name="model",
                signature=infer_signature(example, trained.predict(example)),
                input_example=example,
            )
            print(f"[mlflow] {trained.name}: model logged with signature + input example")
        print(f"[mlflow] {trained.name}: run {active.info.run_id}")
        return active.info.run_id


if __name__ == "__main__":
    raise SystemExit(main())
