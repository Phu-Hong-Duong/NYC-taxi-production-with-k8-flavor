"""The honest floors, fitted on train and re-derived through the model's path.

The group-median floor (3.7170 val MAE, eda_report.md §11) is the bar M2-S3's
promotion gate used. It is recomputed here rather than quoted because a floor
computed by a different instrument than the model is not a comparison, and
because gotcha #15 forbids reporting the SQL number as a result.

The unseen-group fallback is the point of this file. ~1.5% of val rows carry a
(hour, dow, PU, DO) combination train never saw, and a lookup that raises on them
is not "a baseline with an edge case" — it is the exact shape of a 500 at M5's
serving boundary. It is therefore an explicit, counted, tested path.

M3-S1 adds a THIRD floor and does not edit the second one. `configs/train.yaml:
baselines` legislated that in M2 ("a deeper hierarchy … is a NEW baseline with a
new name, never an edit"), and F-010 is why it matters: giving the same lookup
one more backoff level — the (PU, DO) median for a row whose full key train never
saw — rescues 98.9% of the fallback rows and collapses the champion's margin from
+7.07% to +2.71%. A floor that gets quietly better makes every historical verdict
unreproducible; a floor that gets better under a new NAME makes the tightening a
diff. Both live here, both are fitted the same way, and the gate names the one it
is judging against.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Prediction:
    """Predictions plus how many of them the predictor had to guess at."""

    values: np.ndarray
    #: Rows the predictor had to GUESS at — i.e. rows that fell all the way
    #: through to the global median. For a one-level lookup that is every row the
    #: table missed; for a backoff lookup it is only the rows no level answered,
    #: which is the number a fallback rate is supposed to mean.
    unseen: int
    #: WHICH rows were guessed at, not just how many. Carried since M2-S4, where
    #: the published predictions file records the flag per row: a fallback rate
    #: is a summary, and the question "are the unseen groups the ones we get
    #: wrong?" cannot be asked of a summary. Derived from the same computation as
    #: `unseen`, so the count and the flags cannot disagree — a second pass to
    #: re-derive the mask would be a second definition of "unseen".
    unseen_mask: np.ndarray | None = None
    #: Rows a LATER level of the lookup answered after the first one missed.
    #: Reported separately from `unseen` because "the table had no row for this
    #: trip" and "the coarse table answered it" are different events, and F-010's
    #: whole finding is that the second one is 98.9% of the first one's rows.
    backoff: int = 0

    @property
    def unseen_rate(self) -> float:
        return 100.0 * self.unseen / len(self.values) if len(self.values) else 0.0

    @property
    def backoff_rate(self) -> float:
        return 100.0 * self.backoff / len(self.values) if len(self.values) else 0.0


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


@dataclass(frozen=True)
class GroupMedianODFallback:
    """The same lookup with one more backoff level: full key -> (PU, DO) -> global.

    F-010's floor, and the reason it exists as a separate class rather than as a
    flag on `GroupMedian`: the published floor is what M2's verdicts were argued
    against, and a knob that can make it stronger can also make somebody's
    historical +7.07% unreproducible. Two names, two numbers, one evaluator.

    It is still a `GROUP BY` — no new column, no new model, the same train rows.
    That is exactly what makes it the harder question for a booster to answer:
    "what do you buy over the best SIMPLE predictor", not over the first one.
    """

    keys: tuple[str, ...]
    fallback_keys: tuple[str, ...]
    table: pd.DataFrame
    fallback_table: pd.DataFrame
    fallback: float
    name: str = "baseline-group-median-od-fallback"

    @classmethod
    def fit(
        cls,
        features: pd.DataFrame,
        y: pd.Series,
        keys: list[str],
        fallback_keys: list[str],
    ) -> GroupMedianODFallback:
        missing = [k for k in list(keys) + list(fallback_keys) if k not in features.columns]
        if missing:
            raise ValueError(
                f"baselines names {missing}, which the feature matrix does not carry. "
                f"Features: {list(features.columns)}."
            )
        if not set(fallback_keys) < set(keys):
            # A backoff level that is not a COARSENING of the level above it is a
            # different lookup wearing the same name: it could answer rows the
            # first level answered differently, and "the fallback fired" would
            # stop meaning "the full key was unseen".
            raise ValueError(
                f"the fallback keys {fallback_keys} must be a strict subset of the "
                f"primary keys {keys} — a backoff level has to be COARSER, not other."
            )
        return cls(
            keys=tuple(keys),
            fallback_keys=tuple(fallback_keys),
            table=_median_table(features, y, keys),
            fallback_table=_median_table(features, y, fallback_keys, column="__fallback__"),
            fallback=float(y.median()),
        )

    @property
    def groups(self) -> int:
        return len(self.table)

    @property
    def fallback_groups(self) -> int:
        return len(self.fallback_table)

    def predict(self, features: pd.DataFrame) -> Prediction:
        joined = features[list(self.keys)].merge(self.table, on=list(self.keys), how="left")
        values = joined["__pred__"].to_numpy(dtype="float64", copy=True)
        missed = np.isnan(values)

        coarse = features[list(self.fallback_keys)].merge(
            self.fallback_table, on=list(self.fallback_keys), how="left"
        )
        rescue = coarse["__fallback__"].to_numpy(dtype="float64", copy=True)
        rescued = missed & ~np.isnan(rescue)
        values[rescued] = rescue[rescued]

        unseen_mask = np.isnan(values)
        values[unseen_mask] = self.fallback
        return Prediction(
            values,
            unseen=int(unseen_mask.sum()),
            unseen_mask=unseen_mask,
            backoff=int(rescued.sum()),
        )


def _median_table(
    features: pd.DataFrame, y: pd.Series, keys: list[str], column: str = "__pred__"
) -> pd.DataFrame:
    frame = features[list(keys)].copy()
    frame["__y__"] = y.to_numpy()
    table = frame.groupby(list(keys), observed=True, sort=False)["__y__"].median()
    return table.reset_index().rename(columns={"__y__": column})


def fit_floor(name: str, features: pd.DataFrame, y: pd.Series, cfg: dict):
    """Fit the floor a CALLER names, from `configs/train.yaml: baselines`.

    The one place a floor name becomes a fitted object. `make predictions`
    (M3-S1, F-012) needs this: the floor it publishes beside the champion's rows
    must be the floor that champion's gate verdict was argued against, which is
    recorded on the registry version and can therefore differ from whatever the
    config names TODAY. Resolving that by hand at two call sites is how the two
    would drift.
    """
    if name == GroupMedian.name:
        return GroupMedian.fit(features, y, list(cfg["group_keys"]))
    if name == GroupMedianODFallback.name:
        return GroupMedianODFallback.fit(
            features, y, list(cfg["group_keys"]), list(cfg["od_fallback_keys"])
        )
    raise ValueError(
        f"no baseline is named {name!r}. Known floors: {GroupMedian.name!r}, "
        f"{GroupMedianODFallback.name!r}. A floor nobody can rebuild is a number, "
        "not a bar."
    )
