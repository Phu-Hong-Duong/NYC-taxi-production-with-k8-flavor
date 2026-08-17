"""The FLAML scout — M3-S4, the automation track's first half.

**What a scout is for.** It spends `configs/automl.yaml: time_budget_s` deciding
which model FAMILY and which region of hyperparameter space are worth the
sniper's 60 trials. That is all. BLUEPRINT §5 and gotcha #15 make the rest of
the rule explicit and this script obeys it on every line it prints: **every
number FLAML computes is scout-internal.** FLAML's `best_loss` is measured by
FLAML's own estimator wrapper, on FLAML's own internal split behaviour, in
FLAML's own units — it is a hypothesis about ordering, not a result. The only
numbers this program reports come from `taxi_mlops.training.evaluate`, and the
scout never calls it, because the scout has nothing to report.

**Run twice, on v1 and on v2, and that is the point** (DR-03). The artisan
searched features holding v1's hyperparameters; the automation track searches
hyperparameters on feature sets it did not invent. Running the scout on both
sets is what fills the 2×2's two automation cells, and it is also the only way
the bake-off can say whether the best family for 5 features is the best family
for 24.

**Sampling, and why the scout's sample is smaller than the artisan's** (F-008).
The artisan iterated at 15% because a 0.50% relative-MAE keep decision needed
that resolution. The scout is not deciding 0.50% of anything: it is ranking four
families, and FLAML sub-samples internally on top of whatever it is given. So it
runs at 5% by default — a knob on this script, stated in its output and on the
MLflow run, and irrelevant to any published number because the contenders the
gate eventually sees are refit on the full configured train months. Every run
this script logs is tagged `sample_run=yes` and `do_not_promote`.

`--time-budget` exists for smoke runs and prints a warning that says the run is
not the configured scout. The configured value is never edited to make a session
fit: DR-01 pinned it and did not touch it.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from taxi_mlops.data.config import load_config, load_yaml
from taxi_mlops.features import quote_time, sets
from taxi_mlops.training.datasets import Split, load_frame
from taxi_mlops.training.run import load_train_config

#: Playbook §3.1's sample-first law, at the scout's resolution. See the docstring.
DEFAULT_SAMPLE = 0.05
DEFAULT_SEED = 20260817
AUTOML_CONFIG = "configs/automl.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", dest="feature_set", default="v1", help="feature set NAME to scout")
    parser.add_argument("--sample-fraction", type=float, default=DEFAULT_SAMPLE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--experiment", default="m3-automl")
    parser.add_argument("--story", default="M3-S4")
    parser.add_argument(
        "--time-budget",
        type=float,
        default=0.0,
        help="override configs/automl.yaml time_budget_s — SMOKE ONLY, and it says so",
    )
    parser.add_argument("--no-mlflow", action="store_true", help="smoke path; never a result")
    parser.add_argument("--out", default="", help="write the scout's verdict here as JSON")
    args = parser.parse_args()

    # Before any read: FLAML imports LightGBM at module scope, so on this host the
    # OpenMP shim must have re-exec'd already (gotcha #37). Doing it first also
    # keeps the log linear — see scripts/artisan_ablation.py for the same note.
    from taxi_mlops.training.openmp import ensure_openmp

    ensure_openmp()

    automl_cfg = load_yaml(AUTOML_CONFIG)
    train_cfg = load_train_config()
    data_cfg = load_config()
    target = train_cfg["target"]
    budget = float(args.time_budget or automl_cfg["time_budget_s"])
    smoke = bool(args.time_budget)

    features_cfg = sets.resolve_set(args.feature_set)
    feature_names = quote_time.feature_names(features_cfg)

    print("=" * 78)
    print(f"[scout] feature set   : {args.feature_set} ({len(feature_names)} features)")
    families = ", ".join(automl_cfg["estimator_list"])
    print(f"[scout] families      : {families}  (the config, not a verdict)")
    print(f"[scout] metric        : {automl_cfg['metric']}  · task {automl_cfg['task']}")
    print(f"[scout] time budget   : {budget:,.0f}s" + ("  ** SMOKE OVERRIDE **" if smoke else ""))
    print(f"[scout] sample        : {args.sample_fraction:.0%} of train, seed {args.seed}")
    print("[scout] DR-03: this track searches HYPERPARAMETERS; the feature set is handed to it")
    print("[scout] gotcha #15: every number FLAML prints below is SCOUT-INTERNAL, never a result")
    print("[scout] the TEST month is not read by this script")
    print("=" * 78)

    columns = [*quote_time.source_columns(features_cfg), target]
    read_started = time.monotonic()
    train_frame, train_months = load_frame(
        "train", data_cfg, columns, sample_fraction=args.sample_fraction, seed=args.seed
    )
    val_frame, val_months = load_frame(
        "val", data_cfg, columns, sample_fraction=args.sample_fraction, seed=args.seed
    )
    train = Split("train", train_months, quote_time.build_features(train_frame, features_cfg),
                  train_frame[target].astype("float64"))
    val = Split("val", val_months, quote_time.build_features(val_frame, features_cfg),
                val_frame[target].astype("float64"))
    del train_frame, val_frame
    print(
        f"\n[data] train {len(train):>12,} rows  months={','.join(train_months)}\n"
        f"[data] val   {len(val):>12,} rows  months={','.join(val_months)}\n"
        f"[data] read + matrices in {time.monotonic() - read_started:.1f}s "
        "(NOT fitting time — DR-01 condition 3)"
    )

    from flaml import AutoML

    automl = AutoML()
    started = time.monotonic()
    automl.fit(
        X_train=train.features,
        y_train=train.y,
        X_val=val.features,
        y_val=val.y,
        task=automl_cfg["task"],
        metric=automl_cfg["metric"],
        time_budget=budget,
        estimator_list=list(automl_cfg["estimator_list"]),
        seed=int(automl_cfg["seed"]),
        eval_method="holdout",
        n_jobs=int(train_cfg["model"]["lightgbm"]["num_threads"]),
        verbose=1,
        early_stop=True,
    )
    fitting_seconds = time.monotonic() - started

    verdict: dict[str, Any] = {
        "feature_set": args.feature_set,
        "n_features": len(feature_names),
        "family": automl.best_estimator,
        "params": {k: v for k, v in (automl.best_config or {}).items()},
        "scout_internal_loss": float(automl.best_loss),
        "scout_internal_metric": automl_cfg["metric"],
        "time_budget_s": budget,
        "smoke_override": smoke,
        "fitting_seconds": fitting_seconds,
        "sample_fraction": args.sample_fraction,
        "seed": args.seed,
        "train_rows": len(train),
        "val_rows": len(val),
        "train_months": list(train_months),
        "val_month": list(val_months),
        "estimator_list": list(automl_cfg["estimator_list"]),
        "run_id": None,
    }

    print("\n" + "=" * 78)
    print(f"[scout] WINNING FAMILY : {verdict['family']}")
    print(f"[scout] starting params: {json.dumps(verdict['params'], sort_keys=True)}")
    print(
        f"[scout] scout-internal {verdict['scout_internal_metric']} = "
        f"{verdict['scout_internal_loss']:.4f} — a HYPOTHESIS about ordering (gotcha #15). "
        "It is not KPI-09 and must not be quoted as one."
    )
    print(_leaderboard(automl))
    print("=" * 78)
    print(
        f"[budget] measured FITTING wall-clock this invocation: {fitting_seconds:,.1f}s "
        "of the configured "
        f"{budget:,.0f}s (DR-01 AI-1)."
    )

    if not args.no_mlflow:
        verdict["run_id"] = _log(args, train_cfg, verdict)
    if args.out:
        Path(args.out).write_text(json.dumps(verdict, indent=2, default=str) + "\n")
        print(f"[scout] verdict written to {args.out}")
    return 0


def _leaderboard(automl: Any) -> str:
    """Per-family best, from FLAML's own record. Labelled on every line it prints."""
    lines = ["", "  scout-internal leaderboard (FLAML's numbers, NOT KPI-09):",
             f"  {'family':<14} {'best internal loss':>20} {'wall s':>10}"]
    lines.append(f"  {'-' * 14} {'-' * 20} {'-' * 10}")
    for family in getattr(automl, "estimator_list", []) or []:
        loss = automl.best_loss_per_estimator.get(family)
        seconds = (getattr(automl, "time_to_find_best_model_per_estimator", {}) or {}).get(family)
        shown = "not reached in budget" if loss is None or loss == float("inf") else f"{loss:.4f}"
        lines.append(f"  {family:<14} {shown:>20} {(seconds or 0.0):>10.1f}")
    return "\n".join(lines)


def _log(args: argparse.Namespace, train_cfg: dict[str, Any], verdict: dict[str, Any]) -> str:
    import mlflow

    from taxi_mlops.training import tracking

    tracking.configure(train_cfg["mlflow"])
    mlflow.set_experiment(args.experiment)
    with mlflow.start_run(run_name=f"scout-{args.feature_set}") as active:
        mlflow.set_tags(
            {
                "story": args.story,
                "milestone": args.story.split("-")[0],
                "role": "MLE",
                "track": "automation",
                "stage": "scout",
                "feature_set": args.feature_set,
                # The two tags that keep gotcha #15 legible six months from now,
                # on the artifact rather than in a transcript.
                "metric_source": "FLAML internal — SCOUT-INTERNAL, NOT the evaluator",
                "scout_internal": "yes",
                "sample_run": "yes",
                "do_not_promote": f"yes — {args.sample_fraction:.0%} sample, a hypothesis (F-008)",
                "winning_family": str(verdict["family"]),
            }
        )
        mlflow.log_params(
            {
                "feature_set": args.feature_set,
                "n_features": verdict["n_features"],
                "estimator_list": ",".join(verdict["estimator_list"]),
                "time_budget_s": verdict["time_budget_s"],
                "sample_fraction": args.sample_fraction,
                "sample_seed": args.seed,
                "train_rows": verdict["train_rows"],
                **{f"best_{k}": v for k, v in verdict["params"].items()},
            }
        )
        # Metric names carry `scout_internal_` so no dashboard can pick them up
        # and render them beside a KPI.
        mlflow.log_metrics(
            {
                "scout_internal_loss": verdict["scout_internal_loss"],
                "scout_fit_seconds": verdict["fitting_seconds"],
            }
        )
        print(f"[mlflow] scout-{args.feature_set}: run {active.info.run_id}")
        return active.info.run_id


if __name__ == "__main__":
    raise SystemExit(main())
