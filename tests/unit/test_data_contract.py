"""The contract: year-awareness, the single cast, and schema changes as EVENTS.

These are the DE charter's refusals expressed as tests — a contract nobody has
watched say no is a hope, not a contract.
"""

from __future__ import annotations

import dataclasses

import pandas as pd
import pytest
from conftest import raw_frame, raw_frame_2025

from taxi_mlops.data.contract import (
    cast,
    expected_columns,
    validate_input,
    validate_output,
)
from taxi_mlops.data.errors import DataContractError, SchemaEventError


def test_year_awareness_is_structural(data_cfg):
    """2019 must not be asked for a column TLC had not invented yet; 2025 must be."""
    y2019 = expected_columns(data_cfg, 2019)
    y2025 = expected_columns(data_cfg, 2025)
    assert y2019["cbd_congestion_fee"]["required"] is False
    assert y2025["cbd_congestion_fee"]["required"] is True
    assert y2019["airport_fee"]["required"] is False  # from_year 2021
    assert y2025["airport_fee"]["required"] is True
    assert y2019["congestion_surcharge"]["required"] is True


def test_2019_frame_validates_and_is_cast_once(data_cfg):
    df, events = validate_input(raw_frame("2019-01"), "2019-01", data_cfg)
    assert df["passenger_count"].dtype == "Int64"
    assert df["PULocationID"].dtype == "Int64"
    assert str(df["tpep_pickup_datetime"].dtype) == "datetime64[us]"
    assert df["airport_fee"].dtype == "float64"
    # airport_fee ships in 2019 ahead of its from_year — announced, not silent.
    assert any("ahead of its from_year" in e for e in events)


def test_2025_shape_validates_and_alias_is_announced(data_cfg):
    """The year-awareness proof: a 2025-shaped frame passes the same contract."""
    df, events = validate_input(raw_frame_2025(), "2025-01", data_cfg)
    assert "airport_fee" in df.columns and "Airport_fee" not in df.columns
    assert any("alias applied" in e for e in events), events
    # int32 in, canonical Int64 out — the cast is what makes 2019 and 2025 one table.
    assert df["VendorID"].dtype == "Int64"
    assert df["PULocationID"].dtype == "Int64"
    assert df["cbd_congestion_fee"].dtype == "float64"


def test_2025_frame_missing_new_column_is_refused(data_cfg):
    df = raw_frame_2025().drop(columns=["cbd_congestion_fee"])
    with pytest.raises(SchemaEventError, match="cbd_congestion_fee"):
        validate_input(df, "2025-01", data_cfg)


def test_missing_required_column_is_refused(data_cfg):
    df = raw_frame("2019-01").drop(columns=["trip_distance"])
    with pytest.raises(SchemaEventError, match="trip_distance"):
        validate_input(df, "2019-01", data_cfg)


def test_unknown_column_is_refused_by_default(data_cfg):
    df = raw_frame("2019-01")
    df["surprise_surcharge"] = 1.0
    with pytest.raises(SchemaEventError, match="surprise_surcharge"):
        validate_input(df, "2019-01", data_cfg)


def test_unknown_column_under_warn_policy_is_announced_not_silent(data_cfg):
    cfg = dataclasses.replace(data_cfg, contract={**data_cfg.contract, "on_unknown_column": "warn"})
    df = raw_frame("2019-01")
    df["surprise_surcharge"] = 1.0
    _, events = validate_input(df, "2019-01", cfg)
    assert any("surprise_surcharge" in e and "WARNING" in e for e in events)


def test_non_integral_value_cannot_be_cast_silently(data_cfg):
    """A fractional passenger count must break loudly, not round away."""
    df = raw_frame("2019-01")
    df.loc[0, "passenger_count"] = 1.5
    with pytest.raises(DataContractError, match="passenger_count"):
        cast(df, expected_columns(data_cfg, 2019))


def test_output_contract_catches_a_broken_cleaning_rule(data_cfg):
    """If location_out_of_range stopped working, the output contract must refuse."""
    df, _ = validate_input(raw_frame("2019-01"), "2019-01", data_cfg)
    df["trip_duration_minutes"] = 10.0
    df.loc[0, "PULocationID"] = 999  # a row no rule removed
    with pytest.raises(DataContractError, match="PULocationID"):
        validate_output(df, "2019-01", data_cfg)


def test_output_contract_requires_the_target(data_cfg):
    df, _ = validate_input(raw_frame("2019-01"), "2019-01", data_cfg)
    with pytest.raises(DataContractError, match="trip_duration_minutes"):
        validate_output(df, "2019-01", data_cfg)


def test_output_contract_refuses_a_null_target(data_cfg):
    df, _ = validate_input(raw_frame("2019-01"), "2019-01", data_cfg)
    df["trip_duration_minutes"] = 10.0
    df.loc[0, "trip_duration_minutes"] = pd.NA
    with pytest.raises(DataContractError, match="trip_duration_minutes"):
        validate_output(df, "2019-01", data_cfg)
