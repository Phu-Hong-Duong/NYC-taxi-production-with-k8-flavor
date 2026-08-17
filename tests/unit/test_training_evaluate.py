"""THE metric source is arithmetic anyone can check by hand, and it refuses holes.

If `evaluate` is the only thing allowed to report a number (gotcha #15), then the
whole program's model evidence rests on this file. So the assertions here are
hand-computable on purpose — a test that checks the implementation against itself
would be the one thing worse than no test.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from taxi_mlops.data.config import load_yaml
from taxi_mlops.training.evaluate import evaluate, results_table

CFG = {"tolerance_minutes": 5.0}


def test_mae_and_within_tolerance_are_the_numbers_you_would_compute_by_hand():
    y = np.array([10.0, 10.0, 10.0, 10.0])
    yhat = np.array([10.0, 12.0, 16.0, 4.0])  # errors 0, 2, 6, 6
    m = evaluate("hand", "val", y, yhat, CFG)
    assert m.mae == pytest.approx(3.5)             # (0+2+6+6)/4  -> KPI-09
    assert m.within_tolerance_rate == pytest.approx(50.0)  # 2 of 4 within 5 -> KPI-10
    assert m.median_ae == pytest.approx(4.0)
    assert m.n == 4


def test_the_tolerance_boundary_is_inclusive():
    """<= 5, not < 5. Stated by a test because a rider at exactly 5 minutes is
    either inside or outside the SLO, and 'roughly' is not a definition."""
    m = evaluate("edge", "val", np.array([10.0]), np.array([15.0]), CFG)
    assert m.within_tolerance_rate == 100.0


def test_kpi_ids_are_the_metric_names():
    m = evaluate("ids", "test", np.array([1.0, 2.0]), np.array([1.0, 3.0]), CFG)
    assert m.kpi_09 == m.mae
    assert m.kpi_10 == m.within_tolerance_rate


def test_a_nan_prediction_is_refused_not_averaged_away():
    """np.mean of a NaN is NaN, which renders as a blank cell and reads as
    'not run yet' rather than 'the fallback did not fire'."""
    with pytest.raises(ValueError, match="NaN"):
        evaluate("holed", "val", np.array([1.0, 2.0]), np.array([1.0, np.nan]), CFG)


def test_mismatched_lengths_are_refused():
    with pytest.raises(ValueError, match="truths"):
        evaluate("bad", "val", np.array([1.0, 2.0]), np.array([1.0]), CFG)


def test_an_empty_split_is_refused_rather_than_scoring_zero():
    with pytest.raises(ValueError, match="nothing to evaluate"):
        evaluate("empty", "val", np.array([]), np.array([]), CFG)


def test_metrics_are_frozen():
    """A metric that can be edited after the fact is a claim, not a measurement."""
    m = evaluate("frozen", "val", np.array([1.0]), np.array([2.0]), CFG)
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.mae = 0.0  # type: ignore[misc]


def test_mlflow_metric_names_carry_the_split_and_the_tolerance():
    m = evaluate("named", "val", np.array([1.0]), np.array([2.0]), CFG)
    keys = m.as_mlflow_metrics()
    assert "val_mae" in keys
    assert "val_within_5min_rate" in keys


def test_the_unseen_rate_travels_with_the_metrics_when_there_is_one():
    m = evaluate("floor", "val", np.array([1.0]), np.array([2.0]), CFG, unseen_rate=1.53)
    assert m.as_mlflow_metrics()["val_unseen_group_rate"] == 1.53
    assert "val_unseen_group_rate" not in evaluate(
        "model", "val", np.array([1.0]), np.array([2.0]), CFG
    ).as_mlflow_metrics()


def test_the_results_table_names_both_kpi_ids():
    rows = [evaluate("c", split, np.array([1.0]), np.array([2.0]), CFG)
            for split in ("val", "test")]
    table = results_table(rows)
    assert "KPI-09" in table and "KPI-10" in table


def test_the_shipped_tolerance_is_five_minutes():
    """KPI-10 is defined at 5 minutes; moving it is a PO fork, not an edit
    (docs/kpi_definitions.md). A config drift here would silently redefine the KPI."""
    assert load_yaml("configs/train.yaml")["evaluate"]["tolerance_minutes"] == 5.0
