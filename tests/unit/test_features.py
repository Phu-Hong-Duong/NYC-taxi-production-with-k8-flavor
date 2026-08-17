"""Feature set v1 is quote-time pure, and the guard that says so can FAIL.

The defect this file exists to prevent does not look like a defect: a model built
on `fare_amount` scores beautifully on every held-out split and is unimplementable
at the serving boundary (F-007). Nothing offline catches it — so the exclusion
registry is tested the way a rejection rule is: each refusal is provoked.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from conftest import raw_frame

from taxi_mlops.data.config import load_yaml
from taxi_mlops.features import quote_time
from taxi_mlops.features.quote_time import (
    EXCLUDED_COLUMNS,
    EXCLUSIONS,
    FeatureLeakageError,
    build_features,
    categorical_names,
    feature_names,
)

TRAIN_CFG = load_yaml("configs/train.yaml")
FEATURES_CFG = TRAIN_CFG["features"]

# The six columns F-007(a) names. Hard-coded here on purpose: if someone deletes
# one from the registry, this list still knows what the finding said.
F_007_POST_TRIP = (
    "fare_amount",
    "tip_amount",
    "tolls_amount",
    "total_amount",
    "payment_type",
    "store_and_fwd_flag",
)


def frame(rows: int = 6) -> pd.DataFrame:
    df = raw_frame("2019-01", rows)
    df["trip_duration_minutes"] = 10.0
    return df


# ------------------------------------------------------------ the include set ---
def test_the_shipped_config_builds_the_five_v1_features():
    out = build_features(frame(), FEATURES_CFG)
    assert list(out.columns) == ["hour", "dayofweek", "PULocationID", "DOLocationID",
                                 "passenger_count"]
    assert len(out) == 6


def test_hour_and_dayofweek_come_from_the_pickup_timestamp():
    df = frame(3)
    df["tpep_pickup_datetime"] = pd.to_datetime(
        ["2019-01-05 08:30:00", "2019-01-06 23:59:00", "2019-01-07 00:00:00"]
    )
    out = build_features(df, FEATURES_CFG)
    assert out["hour"].tolist() == [8, 23, 0]
    # 2019-01-05 is a Saturday (5), the 6th a Sunday (6), the 7th a Monday (0).
    assert out["dayofweek"].tolist() == [5, 6, 0]


def test_passenger_count_keeps_its_nulls_as_nan_rather_than_an_invented_value():
    """A filled passenger count is a made-up passenger; LightGBM reads NaN natively."""
    df = frame(3)
    df.loc[1, "passenger_count"] = None
    out = build_features(df, FEATURES_CFG)
    assert out["passenger_count"].dtype == np.dtype("float32")
    assert bool(np.isnan(out["passenger_count"].iloc[1]))


def test_the_input_frame_is_never_modified():
    """gotcha #7's neighbour: this module encodes a matrix, it does not recast TLC data."""
    df = frame()
    before = df.dtypes.to_dict()
    build_features(df, FEATURES_CFG)
    assert df.dtypes.to_dict() == before
    assert "hour" not in df.columns


def test_a_temporal_name_this_module_cannot_derive_is_refused_not_skipped():
    cfg = {**FEATURES_CFG, "temporal": ["hour", "minute_of_year"]}
    with pytest.raises(ValueError, match="minute_of_year"):
        build_features(frame(), cfg)


# ---------------------------------------------------------- the exclude set ---
@pytest.mark.parametrize("column", F_007_POST_TRIP)
def test_every_post_trip_column_f_007_names_is_excluded_with_a_reason(column):
    exclusion = next(e for e in EXCLUSIONS if e.column == column)
    assert exclusion.finding == "F-007(a)"
    assert "trip end" in exclusion.reason


@pytest.mark.parametrize(
    "column,finding",
    [("trip_distance", "F-007(b)"), ("congestion_surcharge", "F-006"), ("airport_fee", "F-006")],
)
def test_the_findings_intaken_by_this_story_each_own_an_exclusion(column, finding):
    exclusion = next(e for e in EXCLUSIONS if e.column == column)
    assert exclusion.finding == finding
    assert exclusion.reason.strip()


def test_trip_distance_records_that_m3_owns_the_substitute_rather_than_this_story():
    exclusion = next(e for e in EXCLUSIONS if e.column == "trip_distance")
    assert "M3" in (exclusion.revisit or "")


def test_month_can_never_be_a_feature():
    """CLAUDE.md standing law. The target mean rises 17.3% Jan->Jun; `month` is
    a reporting dimension and a model given it learns the calendar of 2019."""
    assert "month" in EXCLUDED_COLUMNS


@pytest.mark.parametrize("column", sorted(EXCLUDED_COLUMNS))
def test_no_excluded_column_can_be_configured_into_the_feature_set(column):
    """The config is a knob; the registry is law. Adding a refused column to
    `passthrough` must fail loudly rather than train."""
    cfg = {**FEATURES_CFG, "passthrough": [*FEATURES_CFG["passthrough"], column]}
    with pytest.raises(FeatureLeakageError, match=column):
        feature_names(cfg)


def test_a_post_trip_column_reaching_the_matrix_by_another_route_still_fails():
    """The output-side half of the guard — the one that catches a builder, not a config."""
    leaked = pd.DataFrame({"hour": [1], "fare_amount": [9.5]})
    with pytest.raises(FeatureLeakageError, match="fare_amount"):
        quote_time.assert_quote_time_pure(leaked.columns)


def test_the_error_names_the_reason_not_just_the_column():
    """A refusal that does not explain itself gets worked around by the next reader."""
    with pytest.raises(FeatureLeakageError) as excinfo:
        quote_time.assert_quote_time_pure(["trip_distance"])
    assert "M3" in str(excinfo.value) or "driven" in str(excinfo.value).lower()


def test_no_feature_is_also_an_exclusion():
    assert not set(feature_names(FEATURES_CFG)) & EXCLUDED_COLUMNS


def test_every_shipped_feature_names_its_request_time_source():
    """gotcha #21's family: a serving feature that cannot say where it comes from
    at request time is the next `trip_distance`."""
    for name in feature_names(FEATURES_CFG):
        assert quote_time.REQUEST_TIME_SOURCE.get(name), name


def test_categorical_must_be_a_subset_of_the_features():
    cfg = {**FEATURES_CFG, "categorical": ["PULocationID", "not_a_feature"]}
    with pytest.raises(ValueError, match="not_a_feature"):
        categorical_names(cfg)


def test_a_duplicated_feature_is_refused():
    cfg = {**FEATURES_CFG, "passthrough": [*FEATURES_CFG["passthrough"], "PULocationID"]}
    with pytest.raises(ValueError, match="duplicat"):
        feature_names(cfg)
