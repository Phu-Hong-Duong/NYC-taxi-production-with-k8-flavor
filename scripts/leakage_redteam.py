"""The leakage red-team — fit an aggregate across all months and watch val inflate.

M3-S3's mandated drill (kickoff; artisan playbook §5 trap 2). The claim under
test is not "leakage is bad", which nobody disputes. It is the sharper one the
dossier's harvest turned up: **the same line of code is correct in a competition
and disqualifying in production, and the difference is the split, not the code.**
The top-6% solution we read computes group means of the target over train and
test concatenated. That is legal there — their test period interleaves their
train period. Here it would ship a model whose offline numbers no live traffic
can reproduce.

So the drill runs the SAME feature set twice, changing exactly one thing:

    arm A — honest : aggregates fitted on the drill's train months, point-in-time
                     (a row in month k sees months 1..k-1 and nothing else)
    arm B — leaky  : the same aggregates fitted across the drill's train months
                     AND the validation month, with no cutoff at all

and reads TWO held-out months, because one is not enough to tell the difference:

    val (2019-07)     — inside arm B's aggregate fit. This is what inflates.
    holdout (2019-06) — in NEITHER arm's model fit and NEITHER arm's aggregate
                        fit. This is the month that stays honest, and the gap
                        between what the two arms claim on val and what they
                        deliver on an untouched month IS the measurement.

**The configured TEST month is not read by this script.** The playbook's
"untouched month" role is played by 2019-06, held out of everything here, so the
drill costs the test month nothing. S5 gets its one shot intact (DR-05 §3).

Why the leaky switch lives in `taxi_mlops.features.aggregates` rather than on a
branch that was deleted: the same argument M2-S3 made for keeping the hobbled
model (`model.HOBBLES`). A refusal nobody can re-run is a refusal that has to be
taken on trust. The switch is `point_in_time=False`, it is reachable only from
this script, and every table it builds prints `LEAKY BY REQUEST` on its own.
"""

from __future__ import annotations

import argparse
import time
from typing import Any

import pandas as pd

from taxi_mlops.data.config import load_config
from taxi_mlops.features import aggregates as aggregates_mod
from taxi_mlops.features import quote_time, sets
from taxi_mlops.training import model as model_mod
from taxi_mlops.training.datasets import Split, load_frame
from taxi_mlops.training.evaluate import Metrics, evaluate
from taxi_mlops.training.run import load_train_config

#: The drill's train months — the configured train window minus its last month,
#: which is promoted to the untouched holdout.
DRILL_TRAIN = ("2019-01", "2019-02", "2019-03", "2019-04", "2019-05")
DRILL_HOLDOUT = ("2019-06",)


def _split(name, frame, months, cfg, target, fitted) -> Split:
    return Split(
        name=name,
        months=months,
        features=quote_time.build_features(frame, cfg, fitted=fitted),
        y=frame[target].astype("float64"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-fraction", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=20260817)
    parser.add_argument("--set", default="v1_g5")
    parser.add_argument("--experiment", default="m3-artisan")
    parser.add_argument("--story", default="M3-S3")
    parser.add_argument("--no-mlflow", action="store_true")
    args = parser.parse_args()

    # Before the reads — the OpenMP shim re-execs once (gotcha #37) and would
    # otherwise throw away every frame this script had already loaded.
    from taxi_mlops.training.openmp import ensure_openmp

    ensure_openmp()

    train_cfg = load_train_config()
    data_cfg = load_config()
    target = train_cfg["target"]
    eval_cfg = train_cfg["evaluate"]
    cfg = sets.resolve_set(args.set)
    val_months = tuple(load_train_config()["data"]["val_month"].split(","))

    print("=" * 78)
    print("[redteam] LEAKAGE DRILL — dossier §4 trap 2, artisan playbook §5 trap 2")
    print(f"[redteam] feature set : {args.set} ({', '.join(cfg['groups'])})")
    print(f"[redteam] drill train : {','.join(DRILL_TRAIN)}")
    print(f"[redteam] val         : {','.join(val_months)}  <- arm B's aggregates see this")
    print(f"[redteam] holdout     : {','.join(DRILL_HOLDOUT)}  <- NEITHER arm sees this, at all")
    print("[redteam] the configured TEST month is NOT read by this script (DR-05 §3)")
    print("=" * 78)

    columns = [*quote_time.source_columns(cfg), target]
    frames: dict[str, tuple[pd.DataFrame, tuple[str, ...]]] = {}
    for name, months in (
        ("train", DRILL_TRAIN),
        ("val", val_months),
        ("holdout", DRILL_HOLDOUT),
    ):
        split_name = "train" if name == "holdout" else name
        frame, got = load_frame(
            split_name,
            data_cfg,
            columns,
            months=months,
            sample_fraction=args.sample_fraction,
            seed=args.seed,
        )
        frames[name] = (frame, got)
        print(f"[data] {name:<8} {len(frame):>10,} rows  months={','.join(got)}")

    results: dict[str, dict[str, Metrics]] = {}
    for arm, point_in_time in (("A_honest", True), ("B_leaky", False)):
        print("\n" + "-" * 78)
        print(f"[redteam] ARM {arm}")
        if point_in_time:
            source = frames["train"][0]
        else:
            # The leak, in one line, and it is not a mistake anybody would notice
            # in review: the validation month is concatenated in before the group
            # statistics are taken. This is what the top-6% source does.
            source = pd.concat([frames["train"][0], frames["val"][0]], ignore_index=True)
        fitted = aggregates_mod.fit(source, target, point_in_time=point_in_time)
        print(fitted.describe())

        splits = {
            name: _split(name, frame, months, cfg, target, fitted)
            for name, (frame, months) in frames.items()
        }
        started = time.monotonic()
        trained = model_mod.fit(
            splits["train"], splits["val"], train_cfg["model"],
            quote_time.categorical_names(cfg), name=f"redteam-{arm}",
        )
        print(f"[redteam] fit in {time.monotonic() - started:.1f}s")
        results[arm] = {
            name: evaluate(
                f"redteam-{arm}", name, splits[name].y.to_numpy(),
                trained.predict(splits[name].features), eval_cfg,
            )
            for name in ("val", "holdout")
        }
        for name, metrics in results[arm].items():
            print(
                f"[redteam] {arm} {name:<8}: MAE {metrics.mae:.4f} min · "
                f"KPI-10 {metrics.within_tolerance_rate:.3f}%"
            )
        if not args.no_mlflow:
            _log(args, train_cfg, cfg, arm, trained, results[arm], splits, fitted)
        del splits, trained, fitted, source

    print("\n" + "=" * 78)
    print(_table(results))
    print("=" * 78)
    val_gain = results["A_honest"]["val"].mae - results["B_leaky"]["val"].mae
    hold_gain = results["A_honest"]["holdout"].mae - results["B_leaky"]["holdout"].mae
    print(
        f"[redteam] the leak BOUGHT {val_gain:+.4f} min on the month it saw (val) and "
        f"{hold_gain:+.4f} min on the month it did not (holdout)."
    )
    print(
        f"[redteam] inflation = {val_gain - hold_gain:+.4f} min of val improvement that "
        "no untouched month reproduces. That difference is the whole finding: arm B "
        "would have been reported as the better model."
    )
    print(
        "[redteam] REMOVED: feature set v2 is fitted by `aggregates.fit(...)` with "
        "point_in_time defaulting to True, and only this script may pass False."
    )
    return 0


def _table(results: dict[str, dict[str, Metrics]]) -> str:
    out = [
        "| arm | aggregates fitted on | val MAE | val KPI-10 | holdout MAE | holdout KPI-10 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    labels = {
        "A_honest": "drill train only, point-in-time by month",
        "B_leaky": "drill train **+ val**, no cutoff",
    }
    for arm, metrics in results.items():
        out.append(
            f"| {arm.replace('_', ' ')} | {labels[arm]} | {metrics['val'].mae:.4f} | "
            f"{metrics['val'].within_tolerance_rate:.3f}% | {metrics['holdout'].mae:.4f} | "
            f"{metrics['holdout'].within_tolerance_rate:.3f}% |"
        )
    return "\n".join(out)


def _log(
    args: argparse.Namespace,
    train_cfg: dict[str, Any],
    cfg: dict[str, Any],
    arm: str,
    trained: model_mod.TrainedModel,
    metrics: dict[str, Metrics],
    splits: dict[str, Split],
    fitted: aggregates_mod.PointInTimeAggregates,
) -> None:
    import mlflow

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
                "red_team": f"{args.story} leakage drill",
                "feature_set": cfg["version"],
                "metric_source": "taxi_mlops.training.evaluate",
                "aggregates_point_in_time": "yes" if fitted.point_in_time else "NO — RED TEAM",
                "sample_run": "yes",
                "do_not_promote": (
                    "yes — sampled red-team arm"
                    + ("" if fitted.point_in_time else "; aggregates fitted across val ON PURPOSE")
                ),
            }
        )
        mlflow.log_params(
            {
                "arm": arm,
                "aggregate_months": ",".join(fitted.fitted_months),
                "point_in_time": fitted.point_in_time,
                "features": ",".join(quote_time.feature_names(cfg)),
                "sample_fraction": args.sample_fraction,
                "train_rows": len(splits["train"]),
            }
        )
        for value in metrics.values():
            mlflow.log_metrics(value.as_mlflow_metrics())
        print(f"[mlflow] {trained.name}: run {active.info.run_id}")


if __name__ == "__main__":
    raise SystemExit(main())
