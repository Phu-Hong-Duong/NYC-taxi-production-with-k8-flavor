"""The two honest floors, fitted on train and re-derived through the model's path.

The group-median floor (3.7170 val MAE, eda_report.md §11) is the bar M2-S3's
promotion gate uses. It is recomputed here rather than quoted because a floor
computed by a different instrument than the model is not a comparison, and
because gotcha #15 forbids reporting the SQL number as a result.

The unseen-group fallback is the point of this file. ~1.5% of val rows carry a
(hour, dow, PU, DO) combination train never saw, and a lookup that raises on them
is not "a baseline with an edge case" — it is the exact shape of a 500 at M5's
serving boundary. It is therefore an explicit, counted, tested path.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Prediction:
    """Predictions plus how many of them the predictor had to guess at."""

    values: np.ndarray
    unseen: int
    #: WHICH rows were guessed at, not just how many. Carried since M2-S4, where
    #: the published predictions file records the flag per row: a fallback rate
    #: is a summary, and the question "are the unseen groups the ones we get
    #: wrong?" cannot be asked of a summary. Derived from the same computation as
    #: `unseen`, so the count and the flags cannot disagree — a second pass to
    #: re-derive the mask would be a second definition of "unseen".
    unseen_mask: np.ndarray | None = None

    @property
    def unseen_rate(self) -> float:
        return 100.0 * self.unseen / len(self.values) if len(self.values) else 0.0


@dataclass(frozen=True)
class ConstantMedian:
    """Predict the train median for everything. The FLATTERING floor.

    Named that way here so it cannot be quoted innocently: it is the number that
    makes any model look good, and CLAUDE.md forbids using it as the bar.
    """

    value: float
    name: str = "baseline-constant-median"

    @classmethod
    def fit(cls, y: pd.Series) -> ConstantMedian:
        return cls(value=float(y.median()))

    def predict(self, features: pd.DataFrame) -> Prediction:
        return Prediction(np.full(len(features), self.value, dtype="float64"), unseen=0)


@dataclass(frozen=True)
class GroupMedian:
    """Median duration of the train trips sharing a row's (hour, dow, PU, DO).

    The HONEST floor: a model that does not beat it has learned nothing a `GROUP
    BY` already knows.
    """

    keys: tuple[str, ...]
    table: pd.DataFrame
    fallback: float
    name: str = "baseline-group-median"

    @classmethod
    def fit(cls, features: pd.DataFrame, y: pd.Series, keys: list[str]) -> GroupMedian:
        missing = [k for k in keys if k not in features.columns]
        if missing:
            raise ValueError(
                f"baselines.group_keys names {missing}, which the feature matrix does "
                f"not carry. Features: {list(features.columns)}."
            )
        frame = features[list(keys)].copy()
        target = "__y__"
        frame[target] = y.to_numpy()
        table = frame.groupby(list(keys), observed=True, sort=False)[target].median()
        table = table.reset_index().rename(columns={target: "__pred__"})
        # The SAME single-level fallback eda_report.md §11 used, deliberately: a
        # deeper hierarchy predicts better and would stop being the published
        # floor. See configs/train.yaml: baselines.
        return cls(keys=tuple(keys), table=table, fallback=float(y.median()))

    @property
    def groups(self) -> int:
        return len(self.table)

    def predict(self, features: pd.DataFrame) -> Prediction:
        joined = features[list(self.keys)].merge(self.table, on=list(self.keys), how="left")
        # copy=True is load-bearing under pandas 3.x: to_numpy() hands back a
        # READ-ONLY view there, and writing the fallback into it raises.
        values = joined["__pred__"].to_numpy(dtype="float64", copy=True)
        unseen_mask = np.isnan(values)
        # Counted, not just handled: the number goes into the run's metrics, so a
        # fallback that starts firing on 40% of rows is visible rather than merely
        # survivable.
        values[unseen_mask] = self.fallback
        return Prediction(values, unseen=int(unseen_mask.sum()), unseen_mask=unseen_mask)
