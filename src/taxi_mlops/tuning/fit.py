"""Fit one tuned contender — LightGBM or XGBoost, one interface, one predict().

`taxi_mlops.training.model` fits *the* v1 model: its parameters come from
`configs/train.yaml` and it deliberately offers no way to override them, because
M2's story was "these settings, argued". The automation track's whole job is to
override them (DR-03), and it may do so with a family v1 does not use — so this
module exists rather than a flag being bolted onto `model.fit`. The two paths
share what matters and nothing else: predictions come back in MINUTES, clipped
at zero, exactly as `TrainedModel.predict` returns them, because the evaluator
and the gate downstream cannot tell which module fitted the thing they judge.

The pruning callbacks live here too. Optuna 4 moved `optuna.integration` out
into a separate distribution; rather than add a package for two adapters, each
is ~15 lines against the booster's own callback protocol, and being ours they
report in the unit the pruner's `n_warmup_steps` is configured in — boosting
rounds — instead of whatever the vendored version happened to count.

Early stopping reads VAL and the test month is not opened here. That is the same
law `model.py` states, and it is worth restating in the module that a tuner
could most easily be talked into bending: a hyperparameter chosen against test
has spent the one measurement the gate has left.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from ..training.datasets import Split
from ..training.openmp import ensure_openmp
from .space import SUPPORTED_FAMILIES, check_family

#: How often a trial reports its val MAE to the pruner. `configs/tuning.yaml`
#: sets `n_warmup_steps: 20`, and a "step" is whatever the reporter counts — so
#: it is counted in BOOSTING ROUNDS here, which is the only unit in which "warm
#: up for 20" means something a reader can predict.
REPORT_EVERY_ROUNDS = 25


@dataclass(frozen=True)
class TunedModel:
    """A tuned booster plus everything needed to score, log and reproduce it."""

    family: str
    booster: Any
    name: str
    params: dict[str, Any]
    num_boost_round: int
    best_iteration: int
    feature_names: list[str]
    categorical: list[str] = field(default_factory=list)

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        """Predictions in minutes, clipped at zero — a duration is never negative."""
        if self.family == "lgbm":
            raw = self.booster.predict(features, num_iteration=self.best_iteration)
        else:
            import xgboost as xgb

            matrix = xgb.DMatrix(features, enable_categorical=True)
            raw = self.booster.predict(matrix, iteration_range=(0, self.best_iteration))
        return np.clip(np.asarray(raw, dtype="float64"), 0.0, None)


class _Reporter:
    """Shared pruning logic: report val MAE every N rounds, raise if pruned."""

    def __init__(self, trial: Any | None) -> None:
        self.trial = trial

    def __call__(self, rounds: int, value: float) -> None:
        if self.trial is None:
            return
        import optuna

        self.trial.report(value, step=rounds)
        if self.trial.should_prune():
            raise optuna.TrialPruned(f"pruned at round {rounds} with val MAE {value:.4f}")


def _lgbm_params(params: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    """Searched knobs over the config's fixed ones. `objective` is never searched."""
    merged = dict(base)
    merged.update(params)
    merged["objective"] = base["objective"]
    merged["metric"] = base["metric"]
    return merged


def fit(
    family: str,
    params: dict[str, Any],
    train: Split,
    val: Split,
    categorical: list[str],
    *,
    base_params: dict[str, Any],
    num_boost_round: int,
    early_stopping_rounds: int,
    trial: Any | None = None,
    name: str | None = None,
    verbose: bool = False,
) -> TunedModel:
    """Fit one contender of `family` with `params`, early-stopped on `val`."""
    check_family(family)
    ensure_openmp()
    report = _Reporter(trial)
    label = name or f"auto-{family}"

    if family == "lgbm":
        import lightgbm as lgb

        merged = _lgbm_params(params, base_params)

        def _callback(env: Any) -> None:
            rounds = env.iteration + 1
            if rounds % REPORT_EVERY_ROUNDS:
                return
            for _, metric, value, *_rest in env.evaluation_result_list:
                if metric in ("l1", "mae"):
                    report(rounds, float(value))

        train_set = lgb.Dataset(
            train.features, label=train.y.to_numpy(dtype="float64"),
            categorical_feature=categorical, free_raw_data=True,
        )
        val_set = lgb.Dataset(
            val.features, label=val.y.to_numpy(dtype="float64"),
            categorical_feature=categorical, reference=train_set, free_raw_data=True,
        )
        callbacks = [lgb.early_stopping(early_stopping_rounds, verbose=verbose), _callback]
        if verbose:
            callbacks.append(lgb.log_evaluation(100))
        booster = lgb.train(
            merged, train_set, num_boost_round=num_boost_round,
            valid_sets=[val_set], valid_names=["val"], callbacks=callbacks,
        )
        return TunedModel(
            family=family, booster=booster, name=label, params=merged,
            num_boost_round=num_boost_round,
            best_iteration=int(booster.best_iteration or num_boost_round),
            feature_names=list(train.features.columns), categorical=list(categorical),
        )

    import xgboost as xgb

    merged = {
        "objective": "reg:absoluteerror",
        "eval_metric": "mae",
        "tree_method": "hist",
        "max_cat_to_onehot": 1,
        "nthread": int(base_params.get("num_threads", 16)),
        "seed": int(base_params.get("seed", 0)),
        **params,
    }

    class _Prune(xgb.callback.TrainingCallback):
        def after_iteration(self, model: Any, epoch: int, evals_log: Any) -> bool:
            rounds = epoch + 1
            if rounds % REPORT_EVERY_ROUNDS:
                return False
            history = evals_log.get("val", {}).get("mae")
            if history:
                report(rounds, float(history[-1]))
            return False

    dtrain = xgb.DMatrix(train.features, label=train.y.to_numpy("float64"), enable_categorical=True)
    dval = xgb.DMatrix(val.features, label=val.y.to_numpy("float64"), enable_categorical=True)
    booster = xgb.train(
        merged, dtrain, num_boost_round=num_boost_round,
        evals=[(dval, "val")], early_stopping_rounds=early_stopping_rounds,
        verbose_eval=100 if verbose else False, callbacks=[_Prune()],
    )
    best = int(getattr(booster, "best_iteration", num_boost_round - 1)) + 1
    return TunedModel(
        family=family, booster=booster, name=label, params=merged,
        num_boost_round=num_boost_round, best_iteration=best,
        feature_names=list(train.features.columns), categorical=list(categorical),
    )


def log_model(model: TunedModel, example: pd.DataFrame) -> None:
    """Log the booster under its OWN MLflow flavor, with signature + input example.

    The flavor matters downstream: M5 resolves `models:/nyc-taxi-eta@champion`
    and loads it, and a booster logged under the wrong flavor is a serving
    failure that only appears at serving time. `infer_signature` is computed
    from the same rows the example carries, so the signature describes the
    matrix this model was actually fitted on rather than a hand-typed schema.
    """
    import mlflow
    from mlflow.models import infer_signature

    signature = infer_signature(example, model.predict(example))
    flavor = mlflow.lightgbm if model.family == "lgbm" else mlflow.xgboost
    flavor.log_model(model.booster, name="model", signature=signature, input_example=example)
    print(
        f"[mlflow] {model.name}: model logged under the {model.family} flavor "
        "with signature + input example"
    )


__all__ = ["SUPPORTED_FAMILIES", "TunedModel", "fit", "log_model", "REPORT_EVERY_ROUNDS"]
