"""LightGBM v1 on feature set v1. Params come from configs/train.yaml, never here.

Two decisions are recorded rather than assumed, because M1-S3's EDA asked M2 to
prove them (E-1) and because a future reader will otherwise re-litigate both:

1. **Objective `l1`.** KPI-09 is MAE in minutes, and `l1` minimises exactly that
   on exactly that scale. `l2` would optimise a metric nobody reports and would
   let the 100-120 minute tail (12,522 trips) drag every prediction upward.
2. **No target transform in v1.** `log1p` is available and is run as a labelled
   ABLATION so the choice is a measurement. Training on log and exponentiating
   back optimises the median of a different loss; it is a win when the metric is
   relative, and KPI-09 is absolute.

Early stopping reads VAL. Test is never seen by training or selection — it is
the month M2-S3's promotion gate judges on, and a model that has been early-
stopped against it has already been fitted to it once.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .datasets import Split
from .openmp import ensure_openmp


@dataclass(frozen=True)
class TrainedModel:
    """A booster plus everything needed to reproduce and report it."""

    booster: Any
    name: str
    target_transform: str
    feature_names: list[str]
    categorical: list[str]
    best_iteration: int
    params: dict[str, Any]

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        """Predictions in MINUTES, whatever scale the model was fitted on."""
        raw = self.booster.predict(features, num_iteration=self.best_iteration)
        values = np.asarray(raw, dtype="float64")
        if self.target_transform == "log1p":
            values = np.expm1(values)
        # A duration is never negative. Clipping at zero is not cosmetic: the
        # promotion gate and the M5 SLO both read a number a rider could be quoted.
        return np.clip(values, 0.0, None)


def _transform(y: pd.Series, how: str) -> np.ndarray:
    if how == "none":
        return y.to_numpy(dtype="float64")
    if how == "log1p":
        return np.log1p(y.to_numpy(dtype="float64"))
    raise ValueError(f"model.target_transform: {how!r} is not one of none|log1p")


def fit(
    train: Split,
    val: Split,
    model_cfg: dict[str, Any],
    categorical: list[str],
    *,
    name: str | None = None,
    target_transform: str | None = None,
) -> TrainedModel:
    """Fit one LightGBM contender. The only place `import lightgbm` happens."""
    ensure_openmp()
    import lightgbm as lgb

    how = target_transform or model_cfg["target_transform"]
    params = dict(model_cfg["lightgbm"])
    rounds = int(model_cfg["num_boost_round"])

    train_set = lgb.Dataset(
        train.features,
        label=_transform(train.y, how),
        categorical_feature=categorical,
        free_raw_data=True,
    )
    val_set = lgb.Dataset(
        val.features,
        label=_transform(val.y, how),
        categorical_feature=categorical,
        reference=train_set,
        free_raw_data=True,
    )

    booster = lgb.train(
        params,
        train_set,
        num_boost_round=rounds,
        valid_sets=[val_set],
        valid_names=["val"],
        callbacks=[
            lgb.early_stopping(int(model_cfg["early_stopping_rounds"]), verbose=True),
            lgb.log_evaluation(int(model_cfg["log_period"])),
        ],
    )
    return TrainedModel(
        booster=booster,
        name=name or model_cfg["name"],
        target_transform=how,
        feature_names=list(train.features.columns),
        categorical=list(categorical),
        best_iteration=int(booster.best_iteration or rounds),
        params=params,
    )
