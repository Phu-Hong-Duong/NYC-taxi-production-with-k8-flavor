"""THE metric source. Every reported model number in this program comes from here.

Gotcha #15, stated as code: an AutoML leaderboard, a LightGBM early-stopping log
and a SQL `GROUP BY` are all hypotheses. A RESULT is what this module computes on
a held-out split. KPI-09 (ETA MAE) and KPI-10 (within-tolerance rate) get their
first measured values through this function and may be sourced nowhere else
(`docs/kpi_definitions.md`).

Three contenders go through one code path on purpose. If the constant-median and
group-median baselines were computed in SQL and only the model came through here,
the comparison would be between two measuring instruments as much as between two
predictors — and the model's instrument would be the one nobody had checked.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class Metrics:
    """One (contender, split) result. Frozen: a metric that can be edited is a claim."""

    contender: str
    split: str
    n: int
    mae: float
    within_tolerance_rate: float
    tolerance_minutes: float
    rmse: float
    median_ae: float
    p90_ae: float
    unseen_rate: float | None = None

    @property
    def kpi_09(self) -> float:
        """KPI-09 — ETA absolute error (MAE), minutes."""
        return self.mae

    @property
    def kpi_10(self) -> float:
        """KPI-10 — ETA within-tolerance rate, percent."""
        return self.within_tolerance_rate

    def as_mlflow_metrics(self) -> dict[str, float]:
        """Metric names carry the SPLIT, never the contender — the run is the contender."""
        out = {
            f"{self.split}_mae": self.mae,
            f"{self.split}_within_{self.tolerance_minutes:g}min_rate": (
                self.within_tolerance_rate
            ),
            f"{self.split}_rmse": self.rmse,
            f"{self.split}_median_ae": self.median_ae,
            f"{self.split}_p90_ae": self.p90_ae,
            f"{self.split}_rows": float(self.n),
        }
        if self.unseen_rate is not None:
            out[f"{self.split}_unseen_group_rate"] = self.unseen_rate
        return out


def evaluate(
    contender: str,
    split: str,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    cfg: dict[str, Any],
    *,
    unseen_rate: float | None = None,
) -> Metrics:
    """Held-out metrics for one contender on one split.

    Refuses NaN rather than propagating it: `np.mean` of a NaN prediction is NaN,
    which renders as a blank cell in a table and reads as "not run yet" instead of
    "the predictor has a hole in it". A baseline whose fallback failed to fire is
    exactly that hole.
    """
    y_true = np.asarray(y_true, dtype="float64")
    y_pred = np.asarray(y_pred, dtype="float64")
    if y_true.shape != y_pred.shape:
        raise ValueError(f"{contender}/{split}: {y_true.shape} truths vs {y_pred.shape} preds")
    if y_true.size == 0:
        raise ValueError(f"{contender}/{split}: nothing to evaluate")
    holes = int(np.isnan(y_pred).sum())
    if holes:
        raise ValueError(
            f"{contender}/{split}: {holes:,} prediction(s) are NaN. A metric computed "
            "over a predictor with a hole in it is not a smaller metric, it is a "
            "different one — fix the fallback."
        )

    error = np.abs(y_pred - y_true)
    tolerance = float(cfg["tolerance_minutes"])
    return Metrics(
        contender=contender,
        split=split,
        n=int(y_true.size),
        mae=float(error.mean()),
        within_tolerance_rate=float(100.0 * (error <= tolerance).mean()),
        tolerance_minutes=tolerance,
        rmse=float(np.sqrt(np.mean((y_pred - y_true) ** 2))),
        median_ae=float(np.median(error)),
        p90_ae=float(np.percentile(error, 90)),
        unseen_rate=unseen_rate,
    )


def results_table(results: list[Metrics]) -> str:
    """The one table this milestone quotes. KPI ids in the header, so nothing is retyped."""
    header = (
        "  contender                    split       rows      KPI-09      KPI-10   "
        "  RMSE   medAE   p90AE"
    )
    rule = (
        "  ---------------------------  -----  -----------  ----------  ----------  "
        "------  ------  ------"
    )
    lines = [
        "  KPI-09 = mean |predicted - actual|, minutes (lower is better)",
        f"  KPI-10 = % of trips within {results[0].tolerance_minutes:g} minutes"
        " (higher is better)",
        "",
        header,
        rule,
    ]
    for m in results:
        lines.append(
            f"  {m.contender:<27}  {m.split:<5}  {m.n:>11,}  {m.mae:>10.4f}  "
            f"{m.within_tolerance_rate:>9.3f}%  {m.rmse:>6.3f}  {m.median_ae:>6.3f}  "
            f"{m.p90_ae:>6.3f}"
        )
    return "\n".join(lines)
