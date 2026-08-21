"""Refit the sniper's winner on the FULL configured train months — M3-S4's deliverable.

Everything upstream of this script ran on a sample, and F-008 is the reason that
matters: a sampled run degrades the gate's FLOOR faster than it degrades the
model, so a sampled number can flatter a contender into a promotion it did not
earn. M3-S1 made that structurally impossible (a sampled `make train` gets no
verdict at all), and the Design Review's rule 5 states the positive form: **all
five bake-off contenders are full-data, train-only fits.** This is where the
automation track's two cells become that.

It re-fits, it does not re-search. The hyperparameters are read from the sniper's
verdict JSON and printed; the only thing that changes between the study's best
trial and this run is how many rows the booster saw. Val is measured through
`taxi_mlops.training.evaluate` — the one instrument — and the model is logged
with signature and input example so M3-S5 can hand it to the gate without
re-fitting anything.

The TEST month is not read here. It is read once per contender, at S5, by the
gate. A tuned model that had seen it would have spent the measurement that
decides whether it ships.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from taxi_mlops.data.config import load_config
from taxi_mlops.features import quote_time, sets
from taxi_mlops.training.datasets import Split, load_frame
from taxi_mlops.training.evaluate import evaluate
from taxi_mlops.training.run import load_train_config
from taxi_mlops.tuning import fit as fit_mod


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verdict", required=True, help="the sniper verdict JSON to refit")
    parser.add_argument("--experiment", default="m3-automl")
    parser.add_argument("--story", default="M3-S4")
    parser.add_argument(
        "--sample-fraction", type=float, default=0.0,
        help="SMOKE ONLY. Non-zero makes this not the deliverable, and the run says so.",
    )
    parser.add_argument("--no-mlflow", action="store_true", help="smoke path; never a result")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    from taxi_mlops.training.openmp import ensure_openmp

    ensure_openmp()

    verdict = json.loads(Path(args.verdict).read_text())
    train_cfg = load_train_config()
    data_cfg = load_config()
    target = train_cfg["target"]
    model_cfg = train_cfg["model"]
    family = verdict["family"]
    feature_set = verdict["feature_set"]
    params = dict(verdict["best_params"])
    if not params:
        raise SystemExit(
            f"{args.verdict} has no best_params — the study completed no trial, so there "
            "is nothing to refit. Run the sniper first (`make tune`)."
        )
    fraction = args.sample_fraction or None
    features_cfg = sets.resolve_set(feature_set)
    categorical = quote_time.categorical_names(features_cfg)
    name = f"auto-{family}-{feature_set}"

    print("=" * 78)
    print(f"[refit] contender    : {name}")
    print(f"[refit] from study   : {verdict['study']} (best trial {verdict['best_trial_number']})")
    scale = ("FULL DATA (the deliverable)" if fraction is None
             else f"{fraction * 100:g}% SAMPLE — SMOKE, not the deliverable")
    print(f"[refit] scale        : {scale}")
    print(f"[refit] params       : {json.dumps(params, sort_keys=True, default=str)}")
    print(f"[refit] rounds cap   : {verdict['max_rounds']} · early stopping on VAL")
    print("[refit] DR-05: full-data, TRAIN-ONLY; TEST is read once, at M3-S5, by the gate")
    print("=" * 78)

    columns = [*quote_time.source_columns(features_cfg), target]
    read_started = time.monotonic()
    train_frame, train_months = load_frame("train", data_cfg, columns, sample_fraction=fraction,
                                           seed=verdict["seed"])
    val_frame, val_months = load_frame("val", data_cfg, columns, sample_fraction=fraction,
                                       seed=verdict["seed"])
    train = Split("train", train_months, quote_time.build_features(train_frame, features_cfg),
                  train_frame[target].astype("float64"))
    val = Split("val", val_months, quote_time.build_features(val_frame, features_cfg),
                val_frame[target].astype("float64"))
    del train_frame, val_frame
    print(f"\n[data] train {len(train):>12,} rows · val {len(val):>12,} rows · read + matrices in "
          f"{time.monotonic() - read_started:.1f}s (NOT fitting time — DR-01 condition 3)")

    started = time.monotonic()
    model = fit_mod.fit(
        family, params, train, val, categorical, base_params=model_cfg["lightgbm"],
        num_boost_round=int(verdict["max_rounds"]),
        early_stopping_rounds=int(model_cfg["early_stopping_rounds"]),
        name=name, verbose=True,
    )
    fitting_seconds = time.monotonic() - started
    metrics = evaluate(name, "val", val.y.to_numpy(), model.predict(val.features),
                       train_cfg["evaluate"])

    row: dict[str, Any] = {
        "contender": name,
        "family": family,
        "feature_set": feature_set,
        "study": verdict["study"],
        "params": params,
        "best_iteration": model.best_iteration,
        "val_mae": metrics.mae,
        "val_within_rate": metrics.within_tolerance_rate,
        "sample_val_mae": verdict["best_value_sample_val_mae"],
        "train_rows": len(train),
        "val_rows": len(val),
        "train_months": list(train_months),
        "val_month": list(val_months),
        "full_data": fraction is None,
        "fitting_seconds": fitting_seconds,
        "run_id": None,
    }
    print(
        f"\n[refit] {name}: val MAE {metrics.mae:.4f} min · KPI-10 "
        f"{metrics.within_tolerance_rate:.3f}% · best_iteration {model.best_iteration} · "
        f"fit {fitting_seconds:,.1f}s"
    )
    print(
        f"[refit] the study's best SAMPLE value was {verdict['best_value_sample_val_mae']} — "
        "the two are not comparable and neither is a verdict; the gate judges on TEST at S5"
    )
    print(f"[budget] measured FITTING wall-clock here: {fitting_seconds:,.1f}s (DR-01 AI-1)")

    if not args.no_mlflow:
        row["run_id"] = _log(args, train_cfg, model, metrics, row, val, fraction,
                             verdict=verdict)
    if args.out:
        Path(args.out).write_text(json.dumps(row, indent=2, default=str) + "\n")
        print(f"[refit] row written to {args.out}")
    return 0


def _log(
    args: argparse.Namespace, train_cfg: dict[str, Any], model: Any, metrics: Any,
    row: dict[str, Any], val: Split, fraction: float | None,
    verdict: dict[str, Any] | None = None,
) -> str:
    import mlflow

    from taxi_mlops.training import registry as registry_mod
    from taxi_mlops.training import tracking

    tracking.configure(train_cfg["mlflow"])
    mlflow.set_experiment(args.experiment)
    with mlflow.start_run(run_name=row["contender"]) as active:
        mlflow.set_tags(
            {
                "story": args.story, "milestone": args.story.split("-")[0], "role": "MLE",
                "track": "automation", "stage": "refit-full-data",
                "feature_set": row["feature_set"], "family": row["family"],
                "optuna_study": row["study"],
                "metric_source": "taxi_mlops.training.evaluate",
                "sample_run": "no" if fraction is None else "yes",
                "do_not_promote": (
                    "no — full-data fit; the gate sees it at M3-S5"
                    if fraction is None
                    else f"yes — {fraction*100:g}% SMOKE sample (F-008)"
                ),
                "hyperparameters_from": "optuna sniper (DR-03: automation searches params)",
                # F-048: the SCALE those hyperparameters were chosen at, written at
                # FIT TIME on the run that will one day become a version. It is the
                # divisor F-020's transfer needs, and until M8-S1 it existed only in
                # a host JSON — invisible to the pod that has to do the transfer.
                # `run._promote` copies these onto the version; the retrain resolver
                # reads them there and never touches the filesystem.
                **(
                    {}
                    if verdict is None
                    else {
                        registry_mod.SEARCH_SCALE_ROWS: str(int(verdict["train_rows"])),
                        registry_mod.SEARCH_SCALE_ROUND_CAP: str(int(verdict["max_rounds"])),
                        registry_mod.SEARCH_SCALE_SOURCE: (
                            f"optuna study {verdict['study']} at sample_fraction "
                            f"{verdict.get('sample_fraction')}, recorded at refit time by "
                            "scripts/automl_refit.py"
                        ),
                    }
                ),
            }
        )
        mlflow.log_params(
            {
                **{k: v for k, v in row["params"].items()},
                "family": row["family"], "feature_set": row["feature_set"],
                "best_iteration": row["best_iteration"], "train_rows": row["train_rows"],
                "n_features": len(model.feature_names),
            }
        )
        mlflow.log_metrics({**metrics.as_mlflow_metrics(), "fit_seconds": row["fitting_seconds"]})
        fit_mod.log_model(model, val.features.head(5).copy())
        print(f"[mlflow] {row['contender']}: run {active.info.run_id}")
        return active.info.run_id


if __name__ == "__main__":
    raise SystemExit(main())
