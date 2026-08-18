"""Fit a tiny booster with a trial that always votes to prune, and report what happened.

A helper, not a test: the leading underscore keeps pytest from collecting it.
It exists as a separate PROCESS because `taxi_mlops.tuning.fit` calls
`ensure_openmp()`, which on this host re-execs the interpreter (gotcha #37) —
and re-execing a pytest process restarts the whole session mid-run. A child can
re-exec as much as it likes.

Prints exactly one line: `PRUNED <reports>` or `NOT_PRUNED <reports>`.

Usage: python tests/unit/_prune_probe.py <lgbm|xgboost>
"""

from __future__ import annotations

import sys

import numpy as np
import optuna
import pandas as pd

from taxi_mlops.training.datasets import Split
from taxi_mlops.tuning import fit as fit_mod


class AlwaysPrune:
    """A trial that records what it was told and always votes to prune."""

    number = 0

    def __init__(self) -> None:
        self.reports: list[tuple[int, float]] = []

    def report(self, value: float, step: int) -> None:
        self.reports.append((step, float(value)))

    def should_prune(self) -> bool:
        return True

    def set_user_attr(self, *_args: object) -> None:
        pass


def main() -> int:
    family = sys.argv[1]
    rng = np.random.default_rng(0)
    rows = 400
    frame = pd.DataFrame({"a": rng.normal(size=rows), "b": rng.normal(size=rows)})
    y = pd.Series(frame["a"] * 2.0 + rng.normal(size=rows))
    train = Split("train", ("2019-01",), frame, y)
    val = Split("val", ("2019-07",), frame.copy(), y.copy())
    trial = AlwaysPrune()

    params = {"learning_rate": 0.1} if family == "lgbm" else {"eta": 0.1}
    base = {"objective": "l1", "metric": "l1", "num_threads": 2, "seed": 0, "verbose": -1}
    outcome = "NOT_PRUNED"
    try:
        fit_mod.fit(
            family, params, train, val, [], base_params=base,
            num_boost_round=fit_mod.REPORT_EVERY_ROUNDS * 4,
            early_stopping_rounds=1000, trial=trial,
        )
    except optuna.TrialPruned:
        outcome = "PRUNED"
    print(f"{outcome} {[step for step, _ in trial.reports]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
