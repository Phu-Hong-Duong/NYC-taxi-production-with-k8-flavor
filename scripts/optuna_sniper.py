"""The Optuna sniper — M3-S4, the automation track's second half.

The scout named a family and a region; this narrows inside it. Everything that
makes the arm worth having is a property of where the study LIVES:

- **Storage is the one Postgres**, via `taxi_mlops.tuning.storage` (the DSN is
  assembled from `.env` in memory and never printed; `configs/tuning.yaml` says
  `storage: postgres` and carries no connection string, by its own law).
- **Resumable by construction.** `load_if_exists=True` plus a namespaced study
  name means killing this process and running the same command again continues
  the same study — the trial count picks up where it stopped, because the trials
  were never in this process to begin with. `scripts/sniper_resume_drill.py`
  kills it on purpose and watches exactly that.
- **Namespaced** `m3-…` (gotcha #17): one Postgres serves the whole program and
  a study called `sniper` collides the first time M7 reaches for the obvious word.

**What the trial value is, precisely.** It is val MAE computed by
`taxi_mlops.training.evaluate` — the same instrument every other number in this
program comes from — on a SAMPLE. That makes it a legitimate ordering signal and
NOT a result: F-008 measured that shrinking train degrades the gate's floor
faster than it degrades a model, so a sampled number can never be a verdict. The
run tags say so, `--sample-fraction` is printed on every line that matters, and
the contender the gate eventually judges is refit on the full configured train
months by `scripts/automl_refit.py`.

**The budget is enforced, not hoped for** (DR-01). `--budget-seconds` caps the
study's wall clock; whichever of `n_trials` and the budget binds first ends the
study, and the transcript says which. Stopping at trial 34 of 60 because the
equal-budget share ran out is a result to report, not a failure to hide — the
artisan track stopped on its own stop rule at 3,313.9 s of 9,000 and reported
that too.
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
from taxi_mlops.training.evaluate import evaluate
from taxi_mlops.training.run import load_train_config
from taxi_mlops.tuning import fit as fit_mod
from taxi_mlops.tuning import space, storage

DEFAULT_SAMPLE = 0.15  # the artisan's resolution: a tuning delta and a feature delta
DEFAULT_SEED = 20260817  # are then measured on the same instrument
TUNING_CONFIG = "configs/tuning.yaml"

#: The rounds cap trials are allowed. v1 uses 500 and never early-stopped, so a
#: tuner that could only ever ask for 500 would be unable to trade a smaller
#: learning rate for more of them — which is half of what tuning a booster IS.
#: The ceiling is a BUDGET decision (DR-01), stated here rather than buried:
#: 1,200 rounds at 15% is the most a single trial may cost.
DEFAULT_MAX_ROUNDS = 1200


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", dest="feature_set", default="v1")
    parser.add_argument("--scout", default="", help="scout verdict JSON — it centres the space")
    parser.add_argument("--family", default="", help="override the scout's family (smoke only)")
    parser.add_argument("--n-trials", type=int, default=0, help="default: tuning.yaml n_trials")
    parser.add_argument("--budget-seconds", type=float, default=0.0, help="DR-01 cap; 0 = none")
    parser.add_argument("--sample-fraction", type=float, default=DEFAULT_SAMPLE)
    parser.add_argument("--max-rounds", type=int, default=DEFAULT_MAX_ROUNDS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--experiment", default="m3-automl")
    parser.add_argument("--story", default="M3-S4")
    parser.add_argument("--label", default="", help="study label; default = sniper-<set>")
    parser.add_argument("--no-mlflow", action="store_true", help="smoke path; never a result")
    parser.add_argument("--out", default="", help="write the study's verdict here as JSON")
    args = parser.parse_args()

    from taxi_mlops.training.openmp import ensure_openmp

    ensure_openmp()

    import optuna

    tuning_cfg = load_yaml(TUNING_CONFIG)
    train_cfg = load_train_config()
    data_cfg = load_config()
    target = train_cfg["target"]
    model_cfg = train_cfg["model"]
    n_trials = int(args.n_trials or tuning_cfg["n_trials"])
    label = args.label or f"sniper-{args.feature_set}"
    name = storage.study_name(tuning_cfg["study_namespace"], label)

    scout: dict[str, Any] = {}
    if args.scout:
        scout = json.loads(Path(args.scout).read_text())
    family = space.check_family(args.family or scout.get("family") or "lgbm")
    centre = space.centre_from_scout(family, scout.get("params"))

    features_cfg = sets.resolve_set(args.feature_set)
    feature_names = quote_time.feature_names(features_cfg)
    categorical = quote_time.categorical_names(features_cfg)

    print("=" * 78)
    print(f"[sniper] study        : {name}   (gotcha #17: namespaced per milestone)")
    print(f"[sniper] feature set  : {args.feature_set} ({len(feature_names)} features) — DR-03: "
          "handed to this track, not invented by it")
    origin = "  (from the scout)" if scout else "  (no scout verdict given)"
    print(f"[sniper] family       : {family}{origin}")
    print(f"[sniper] sampler      : {tuning_cfg['sampler']}  · pruner {tuning_cfg['pruner']}")
    cap = f"  · budget {args.budget_seconds:,.0f}s" if args.budget_seconds else "  · no cap"
    print(f"[sniper] trials       : {n_trials}{cap}")
    print(f"[sniper] sample       : {args.sample_fraction:.0%} of train, seed {args.seed}")
    print(f"[sniper] storage      : {storage.describe()}")
    print("[sniper] trial value = val MAE from taxi_mlops.training.evaluate ON A SAMPLE —")
    print("[sniper]   an ordering signal, never a verdict (F-008); the winner is refit full-data.")
    print("[sniper] the TEST month is not read by this script")
    print("=" * 78)
    print("\n[sniper] search space, centred on the scout's winner:")
    print(space.describe(family, centre))

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
        f"\n[data] train {len(train):>12,} rows · val {len(val):>12,} rows · read + matrices in "
        f"{time.monotonic() - read_started:.1f}s (NOT fitting time — DR-01 condition 3)"
    )

    fitting = {"seconds": 0.0}
    started_wall = time.monotonic()

    with storage.port_forward():
        study = optuna.create_study(
            study_name=name,
            storage=storage.storage_url(),
            direction="minimize",
            load_if_exists=True,
            sampler=_sampler(optuna, tuning_cfg["sampler"]),
            pruner=_pruner(optuna, tuning_cfg["pruner"]),
        )
        already = len(study.trials)
        print(
            f"\n[sniper] study opened with {already} existing trial(s) — "
            + ("a RESUME: the trials were in Postgres, not in the process that made them"
               if already else "a fresh study")
        )
        study.set_user_attr("feature_set", args.feature_set)
        study.set_user_attr("family", family)
        study.set_user_attr("sample_fraction", args.sample_fraction)

        parent = _open_parent(args, train_cfg, tuning_cfg, family, name, already) \
            if not args.no_mlflow else None
        try:
            study.optimize(
                _objective(args, train, val, categorical, model_cfg, train_cfg, family,
                           centre, fitting, parent),
                n_trials=max(0, n_trials - already),
                timeout=args.budget_seconds or None,
                gc_after_trial=True,
            )
        finally:
            if parent is not None:
                _close_parent(study, fitting)

        verdict = _summarise(study, args, family, name, fitting, started_wall, n_trials,
                             len(train), len(val), train_months, val_months, feature_names)

    print("\n" + "=" * 78)
    print(_report(verdict))
    print("=" * 78)
    if args.out:
        Path(args.out).write_text(json.dumps(verdict, indent=2, default=str) + "\n")
        print(f"[sniper] verdict written to {args.out}")
    return 0


def _sampler(optuna: Any, cfg: dict[str, Any]) -> Any:
    if cfg["type"] != "tpe":
        raise ValueError(f"configs/tuning.yaml: sampler.type {cfg['type']!r} — only 'tpe' is wired")
    return optuna.samplers.TPESampler(seed=int(cfg["seed"]))


def _pruner(optuna: Any, cfg: dict[str, Any]) -> Any:
    if cfg["type"] != "median":
        raise ValueError(f"configs/tuning.yaml: pruner.type {cfg['type']!r} — only median is wired")
    return optuna.pruners.MedianPruner(
        n_startup_trials=int(cfg["n_startup_trials"]),
        # Counted in BOOSTING ROUNDS: taxi_mlops.tuning.fit reports every
        # REPORT_EVERY_ROUNDS rounds, so this threshold means what it reads like.
        n_warmup_steps=int(cfg["n_warmup_steps"]),
    )


def _objective(
    args: argparse.Namespace, train: Split, val: Split, categorical: list[str],
    model_cfg: dict[str, Any], train_cfg: dict[str, Any], family: str,
    centre: dict[str, float], fitting: dict[str, float], parent: Any,
) -> Any:
    eval_cfg = train_cfg["evaluate"]

    def objective(trial: Any) -> float:
        params = space.suggest(trial, family, centre)
        rounds = int(args.max_rounds)
        started = time.monotonic()
        try:
            model = fit_mod.fit(
                family, params, train, val, categorical,
                base_params=model_cfg["lightgbm"], num_boost_round=rounds,
                early_stopping_rounds=int(model_cfg["early_stopping_rounds"]),
                trial=trial, name=f"auto-{family}-{args.feature_set}-t{trial.number}",
            )
        finally:
            fitting["seconds"] += time.monotonic() - started
        metrics = evaluate(
            f"auto-{family}-{args.feature_set}-t{trial.number}", "val",
            val.y.to_numpy(), model.predict(val.features), eval_cfg,
        )
        trial.set_user_attr("best_iteration", model.best_iteration)
        trial.set_user_attr("val_within_rate", metrics.within_tolerance_rate)
        print(
            f"[trial {trial.number:>3}] val MAE {metrics.mae:.4f} (sample) · KPI-10 "
            f"{metrics.within_tolerance_rate:.3f}% · best_iter {model.best_iteration} · "
            f"{time.monotonic() - started:.1f}s"
        )
        if parent is not None:
            _log_trial(args, trial, params, metrics, model, family)
        del model
        return metrics.mae

    return objective


def _open_parent(
    args: argparse.Namespace, train_cfg: dict[str, Any], tuning_cfg: dict[str, Any],
    family: str, study: str, already: int,
) -> Any:
    import mlflow

    from taxi_mlops.training import tracking

    tracking.configure(train_cfg["mlflow"])
    mlflow.set_experiment(args.experiment)
    run = mlflow.start_run(run_name=f"{tuning_cfg['mlflow']['parent_run_name']}-{args.feature_set}")
    mlflow.set_tags(
        {
            "story": args.story, "milestone": args.story.split("-")[0], "role": "MLE",
            "track": "automation", "stage": "sniper", "feature_set": args.feature_set,
            "family": family, "optuna_study": study,
            "metric_source": "taxi_mlops.training.evaluate ON A SAMPLE — ordering only",
            "sample_run": "yes",
            "do_not_promote": f"yes — {args.sample_fraction:.0%} sample (F-008)",
            # The evidence a resumed study leaves in MLflow: a second parent whose
            # first trial number is not zero.
            "resumed": "yes" if already else "no",
            "trials_before_this_process": str(already),
        }
    )
    print(f"[mlflow] parent run {run.info.run_id} ({'resumed' if already else 'fresh'} study)")
    return run


def _close_parent(study: Any, fitting: dict[str, float]) -> None:
    import mlflow

    best = None
    with_value = [t for t in study.trials if t.value is not None]
    if with_value:
        best = min(with_value, key=lambda t: t.value)
    if best is not None:
        mlflow.log_metrics({"best_trial_val_mae_sample": float(best.value)})
        mlflow.log_params({f"best_{k}": v for k, v in best.params.items()})
    mlflow.log_metrics({"sniper_fit_seconds": fitting["seconds"], "trials": len(study.trials)})
    mlflow.end_run()


def _log_trial(
    args: argparse.Namespace, trial: Any, params: dict[str, Any], metrics: Any,
    model: Any, family: str,
) -> None:
    import mlflow

    with mlflow.start_run(run_name=f"trial-{trial.number:03d}", nested=True):
        mlflow.set_tags(
            {
                "stage": "sniper-trial", "family": family, "feature_set": args.feature_set,
                "optuna_trial": str(trial.number), "sample_run": "yes",
                "do_not_promote": f"yes — {args.sample_fraction:.0%} sample (F-008)",
            }
        )
        mlflow.log_params({**params, "best_iteration": model.best_iteration})
        mlflow.log_metrics(metrics.as_mlflow_metrics())


def _summarise(
    study: Any, args: argparse.Namespace, family: str, name: str, fitting: dict[str, float],
    started_wall: float, n_trials: int, train_rows: int, val_rows: int,
    train_months: tuple[str, ...], val_months: tuple[str, ...], feature_names: list[str],
) -> dict[str, Any]:
    import optuna

    states = [t.state for t in study.trials]
    complete = sum(s == optuna.trial.TrialState.COMPLETE for s in states)
    pruned = sum(s == optuna.trial.TrialState.PRUNED for s in states)
    failed = sum(s == optuna.trial.TrialState.FAIL for s in states)
    best = study.best_trial if complete else None
    return {
        "study": name,
        "feature_set": args.feature_set,
        "n_features": len(feature_names),
        "family": family,
        "trials_total": len(study.trials),
        "trials_complete": complete,
        "trials_pruned": pruned,
        "trials_failed": failed,
        "trials_requested": n_trials,
        "stopped_on": (
            "budget" if args.budget_seconds and len(study.trials) < n_trials else "n_trials"
        ),
        "budget_seconds": args.budget_seconds,
        "wall_seconds": time.monotonic() - started_wall,
        "fitting_seconds": fitting["seconds"],
        "best_params": dict(best.params) if best else {},
        "best_value_sample_val_mae": float(best.value) if best else None,
        "best_trial_number": best.number if best else None,
        "best_within_rate_sample": (best.user_attrs.get("val_within_rate") if best else None),
        "best_iteration": (best.user_attrs.get("best_iteration") if best else None),
        "sample_fraction": args.sample_fraction,
        "seed": args.seed,
        "max_rounds": args.max_rounds,
        "train_rows": train_rows,
        "val_rows": val_rows,
        "train_months": list(train_months),
        "val_month": list(val_months),
    }


def _report(v: dict[str, Any]) -> str:
    lines = [
        f"[sniper] study {v['study']} · family {v['family']} · set {v['feature_set']}",
        f"[sniper] trials: {v['trials_total']} total = {v['trials_complete']} complete + "
        f"{v['trials_pruned']} PRUNED + {v['trials_failed']} failed "
        f"(requested {v['trials_requested']}, stopped on {v['stopped_on']})",
    ]
    if v["best_value_sample_val_mae"] is None:
        lines.append("[sniper] no completed trial — nothing to hand the refit")
        return "\n".join(lines)
    lines += [
        f"[sniper] best trial {v['best_trial_number']}: val MAE "
        f"{v['best_value_sample_val_mae']:.4f} on a {v['sample_fraction']:.0%} sample "
        "— an ORDERING number, not KPI-09 (F-008; the refit is what the gate may see)",
        f"[sniper] best params: {json.dumps(v['best_params'], sort_keys=True, default=str)}",
        f"[budget] measured FITTING wall-clock this invocation: {v['fitting_seconds']:,.1f}s "
        f"of {v['wall_seconds']:,.1f}s wall (DR-01 AI-1)",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
