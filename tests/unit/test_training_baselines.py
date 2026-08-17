"""The two floors, and the unseen-group path that is not an edge case.

~1.5% of val rows carry a (hour, dow, PU, DO) combination train never saw
(eda_report.md §11). A lookup that raises on them is not a baseline with a rough
edge — it is the exact shape of a 500 at M5's serving boundary, arriving on the
day a new zone opens. So the fallback is provoked here, and it is COUNTED, not
merely survived.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from taxi_mlops.training.baselines import ConstantMedian, GroupMedian

KEYS = ["hour", "dayofweek", "PULocationID", "DOLocationID"]


def features(rows: list[tuple[int, int, int, int]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=KEYS).astype("int16")


def test_constant_median_predicts_the_train_median_for_everything():
    y = pd.Series([1.0, 2.0, 3.0, 100.0])
    baseline = ConstantMedian.fit(y)
    assert baseline.value == 2.5
    prediction = baseline.predict(features([(8, 1, 100, 200)] * 3))
    assert prediction.values.tolist() == [2.5, 2.5, 2.5]
    assert prediction.unseen == 0


def test_group_median_uses_the_group_where_it_has_one():
    train = features([(8, 1, 100, 200), (8, 1, 100, 200), (9, 1, 100, 200)])
    y = pd.Series([10.0, 20.0, 99.0])
    baseline = GroupMedian.fit(train, y, KEYS)
    assert baseline.groups == 2
    prediction = baseline.predict(features([(8, 1, 100, 200), (9, 1, 100, 200)]))
    assert prediction.values.tolist() == [15.0, 99.0]
    assert prediction.unseen == 0


def test_an_unseen_group_falls_back_instead_of_raising():
    """The whole point of this file: a KeyError here is a serving outage there."""
    train = features([(8, 1, 100, 200), (8, 1, 100, 200)])
    y = pd.Series([10.0, 20.0])
    baseline = GroupMedian.fit(train, y, KEYS)
    prediction = baseline.predict(features([(8, 1, 100, 200), (3, 6, 264, 265)]))
    assert prediction.values.tolist() == [15.0, 15.0]  # fallback == train median
    assert prediction.unseen == 1
    assert prediction.unseen_rate == 50.0


def test_the_fallback_is_the_train_median_not_the_group_table_mean():
    """It matches eda_report.md §11's single-level fallback exactly, so the
    published 3.7170 floor stays a number this code path can be checked against."""
    train = features([(8, 1, 100, 200), (9, 1, 100, 200), (9, 1, 100, 200)])
    y = pd.Series([1.0, 50.0, 60.0])
    baseline = GroupMedian.fit(train, y, KEYS)
    assert baseline.fallback == 50.0  # median of ALL train rows, not of the groups


def test_no_prediction_is_ever_nan():
    """A NaN prediction reads as 'not run yet' in a table, which is the worst
    possible disguise for 'the predictor has a hole in it'."""
    train = features([(8, 1, 100, 200)])
    baseline = GroupMedian.fit(train, pd.Series([12.0]), KEYS)
    prediction = baseline.predict(features([(i, 2, 3, 4) for i in range(20)]))
    assert not np.isnan(prediction.values).any()
    assert prediction.unseen == 20


def test_group_keys_the_matrix_does_not_carry_are_refused_by_name():
    train = features([(8, 1, 100, 200)])
    with pytest.raises(ValueError, match="weather"):
        GroupMedian.fit(train, pd.Series([12.0]), [*KEYS, "weather"])


def test_the_fit_does_not_mutate_the_feature_matrix():
    train = features([(8, 1, 100, 200), (8, 1, 100, 200)])
    before = list(train.columns)
    GroupMedian.fit(train, pd.Series([10.0, 20.0]), KEYS)
    assert list(train.columns) == before
