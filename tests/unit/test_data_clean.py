"""Counted rejections: the counts must balance, and every named rule must fire.

A rejection table nobody has seen produce a nonzero number for a given rule is a
rule that may not exist. Each one is provoked here with a purpose-built row.
"""

from __future__ import annotations

import dataclasses

import pandas as pd
import pytest
from conftest import raw_frame

from taxi_mlops.data.clean import add_target, clean, sort_deterministically
from taxi_mlops.data.contract import validate_input
from taxi_mlops.data.errors import RejectionThresholdError

MONTH = "2019-01"


def prepared(df: pd.DataFrame, cfg) -> pd.DataFrame:
    return validate_input(df, MONTH, cfg)[0]


def test_target_is_derived_in_minutes(data_cfg):
    df = prepared(raw_frame(MONTH, rows=2), data_cfg)
    out = add_target(df, data_cfg)
    assert out["trip_duration_minutes"].tolist() == [10.0, 10.0]


def test_counts_balance_against_the_row_counts(data_cfg):
    df = prepared(raw_frame(MONTH, rows=20), data_cfg)
    df.loc[0, "trip_distance"] = 0.0
    df.loc[1, "fare_amount"] = -3.0
    kept, report = clean(df, MONTH, data_cfg)
    assert report.rows_in == 20
    assert report.rows_out == len(kept) == 18
    assert sum(r["rejected_by"] for r in report.rules) == report.rows_rejected == 2


def one_row_per_rule(cfg) -> pd.DataFrame:
    """A frame where row i violates rule i and nothing else violates anything."""
    rules = [r["name"] for r in cfg.clean["rules"]]
    df = raw_frame(MONTH, rows=len(rules) + 5)
    index = {name: i for i, name in enumerate(rules)}
    df.loc[index["missing_timestamp"], "tpep_dropoff_datetime"] = pd.NaT
    row = index["duration_non_positive"]
    df.loc[row, "tpep_dropoff_datetime"] = df.loc[row, "tpep_pickup_datetime"]
    row = index["duration_below_min"]
    df.loc[row, "tpep_dropoff_datetime"] = df.loc[row, "tpep_pickup_datetime"] + pd.Timedelta(
        seconds=30
    )
    row = index["duration_above_max"]
    df.loc[row, "tpep_dropoff_datetime"] = df.loc[row, "tpep_pickup_datetime"] + pd.Timedelta(
        hours=5
    )
    row = index["pickup_outside_month"]
    df.loc[row, "tpep_pickup_datetime"] = pd.Timestamp("2001-02-02 14:55:07")
    df.loc[row, "tpep_dropoff_datetime"] = pd.Timestamp("2001-02-02 15:05:07")
    df.loc[index["distance_non_positive"], "trip_distance"] = 0.0
    df.loc[index["distance_above_max"], "trip_distance"] = 500.0
    df.loc[index["fare_negative"], "fare_amount"] = -1.0
    df.loc[index["location_out_of_range"], "DOLocationID"] = 999
    df.loc[index["passenger_count_out_of_range"], "passenger_count"] = 42.0
    return df


def test_every_named_rule_fires_exactly_once(data_cfg):
    """Deliberately ceiling-free: this frame is 2/3 garbage because every rule needs a victim."""
    cfg = dataclasses.replace(data_cfg, clean={**data_cfg.clean, "max_rejected_fraction": 1.0})
    df = prepared(one_row_per_rule(cfg), cfg)
    _, report = clean(df, MONTH, cfg)
    for rule in report.rules:
        assert rule["rejected_by"] == 1, f"rule {rule['name']} never fired: {report.table()}"
        # matched may exceed 1 where rules legitimately overlap (a 0-minute trip is
        # both non-positive and below-min); it may never be 0 when a row was built for it.
        assert rule["matched"] >= 1, f"rule {rule['name']} matched nothing"


def test_overlapping_row_is_attributed_once_but_matched_twice(data_cfg):
    """The shadowing case the two-column table exists for."""
    df = raw_frame(MONTH, rows=10)
    df.loc[0, "trip_distance"] = 0.0  # distance_non_positive
    df.loc[0, "fare_amount"] = -5.0  # fare_negative — same row, later rule
    kept, report = clean(prepared(df, data_cfg), MONTH, data_cfg)
    by_name = {r["name"]: r for r in report.rules}
    assert report.rows_rejected == 1 and len(kept) == 9
    assert by_name["distance_non_positive"]["rejected_by"] == 1
    assert by_name["fare_negative"]["rejected_by"] == 0
    assert by_name["fare_negative"]["matched"] == 1  # shadowed, not dead


def test_null_distance_is_rejected_not_carried(data_cfg):
    df = raw_frame(MONTH, rows=10)
    df.loc[0, "trip_distance"] = None
    kept, report = clean(prepared(df, data_cfg), MONTH, data_cfg)
    by_name = {r["name"]: r for r in report.rules}
    assert by_name["distance_non_positive"]["rejected_by"] == 1
    assert kept["trip_distance"].isna().sum() == 0


def test_a_month_that_loses_too_much_is_refused(data_cfg):
    cfg = dataclasses.replace(data_cfg, clean={**data_cfg.clean, "max_rejected_fraction": 0.10})
    df = raw_frame(MONTH, rows=10)
    df.loc[0:1, "trip_distance"] = 0.0  # 20% > 10% ceiling
    with pytest.raises(RejectionThresholdError, match="broken input"):
        clean(prepared(df, cfg), MONTH, cfg)


def test_report_table_and_json_agree(data_cfg):
    df = prepared(raw_frame(MONTH, rows=10), data_cfg)
    df.loc[0, "fare_amount"] = -1.0
    _, report = clean(df, MONTH, data_cfg)
    payload = report.to_dict()
    assert payload["rows_in"] - payload["rows_out"] == payload["rows_rejected"] == 1
    assert "fare_negative" in report.table()


def test_sort_is_deterministic(data_cfg):
    df = prepared(raw_frame(MONTH, rows=50), data_cfg)
    kept, _ = clean(df, MONTH, data_cfg)
    once = sort_deterministically(kept, data_cfg)
    twice = sort_deterministically(kept.sample(frac=1, random_state=7), data_cfg)
    pd.testing.assert_frame_equal(once, twice)
