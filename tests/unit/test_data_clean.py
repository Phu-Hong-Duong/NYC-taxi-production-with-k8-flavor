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
    kept, _rejected, report = clean(df, MONTH, data_cfg)
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
    _, _rejected, report = clean(df, MONTH, cfg)
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
    kept, _rejected, report = clean(prepared(df, data_cfg), MONTH, data_cfg)
    by_name = {r["name"]: r for r in report.rules}
    assert report.rows_rejected == 1 and len(kept) == 9
    assert by_name["distance_non_positive"]["rejected_by"] == 1
    assert by_name["fare_negative"]["rejected_by"] == 0
    assert by_name["fare_negative"]["matched"] == 1  # shadowed, not dead


def test_null_distance_is_rejected_not_carried(data_cfg):
    df = raw_frame(MONTH, rows=10)
    df.loc[0, "trip_distance"] = None
    kept, _rejected, report = clean(prepared(df, data_cfg), MONTH, data_cfg)
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
    _, _rejected, report = clean(df, MONTH, data_cfg)
    payload = report.to_dict()
    assert payload["rows_in"] - payload["rows_out"] == payload["rows_rejected"] == 1
    assert "fare_negative" in report.table()


# ------------------------------------ the retained sidecar (M2-S1, F-005) ----
#
# Until this existed the rejected rows were a NUMBER. Every test below asserts
# something a count cannot: that the rows are the same rows, filed under the
# same rule, and that they never rejoin the clean data.

def test_kept_and_rejected_partition_the_month(data_cfg):
    """Every row goes to exactly one side. A row in neither is a silent drop —
    the thing this whole module exists to make impossible — and a row in both
    would put a contract violation into the training data."""
    df = prepared(raw_frame(MONTH, rows=40), data_cfg)
    df.loc[0, "trip_distance"] = 0.0
    df.loc[1, "fare_amount"] = -5.0
    kept, rejected, report = clean(df, MONTH, data_cfg)
    assert len(kept) + len(rejected) == report.rows_in == 40
    assert len(rejected) == report.rows_rejected == 2
    # the surviving side really is clean: neither seeded violation is in it
    assert (kept["trip_distance"] > 0).all()
    assert (kept["fare_amount"] >= 0).all()


def test_sidecar_rule_counts_equal_the_reports_first_match_attribution(data_cfg):
    """The reconciliation law, at unit scale: `rejection_rule` IS `rejected_by`.

    If these two ever attribute differently, `make duckdb` fails — so this test
    is what keeps that gate from being the first place anyone finds out.
    """
    cfg = dataclasses.replace(data_cfg, clean={**data_cfg.clean, "max_rejected_fraction": 1.0})
    df = prepared(one_row_per_rule(cfg), cfg)
    _, rejected, report = clean(df, MONTH, cfg)
    observed = rejected["rejection_rule"].value_counts().to_dict()
    expected = {r["name"]: r["rejected_by"] for r in report.rules if r["rejected_by"]}
    assert observed == expected
    assert len(expected) == len(cfg.clean["rules"])  # every rule fired, so every rule is checked
    assert rejected["rejection_rule"].isna().sum() == 0


def test_rejection_rules_lists_every_rule_the_row_violates(data_cfg):
    """The per-ROW half of the shadowing story the two-column table tells per rule.

    A 0-distance, negative-fare row is FILED under distance_non_positive (first
    match, so the counts balance) and must still say it was also fare_negative —
    otherwise characterising a rejected population means re-deriving the rules.
    """
    df = raw_frame(MONTH, rows=20)
    df.loc[0, "trip_distance"] = 0.0
    df.loc[0, "fare_amount"] = -5.0
    df.loc[1, "fare_amount"] = -5.0
    _, rejected, _ = clean(prepared(df, data_cfg), MONTH, data_cfg)
    by_rule = dict(zip(rejected["rejection_rule"], rejected["rejection_rules"], strict=True))
    assert by_rule["distance_non_positive"] == "distance_non_positive,fare_negative"
    assert by_rule["fare_negative"] == "fare_negative"
    # the filing rule is always the FIRST entry of the all-match list
    for rule, rules in by_rule.items():
        assert rules.split(",")[0] == rule


def test_the_sidecar_keeps_the_columns_and_the_derived_target(data_cfg):
    """The point of retaining rows is to answer questions nobody has asked yet.
    A rejected row that kept only its rule name would answer none of them."""
    df = prepared(raw_frame(MONTH, rows=20), data_cfg)
    df.loc[0, "trip_distance"] = 0.0
    kept, rejected, _ = clean(df, MONTH, data_cfg)
    assert set(kept.columns) - {"rejection_rule", "rejection_rules"} <= set(rejected.columns)
    assert data_cfg.clean["target"] in rejected.columns
    assert rejected[data_cfg.clean["target"]].iloc[0] == 10.0


def test_a_row_with_no_derivable_target_is_still_retained(data_cfg):
    """missing_timestamp rows have a NaN target and NaT timestamps — the rows an
    implementation that assumes the sidecar looks like the clean data would lose.

    The rule fires ZERO times over 2019-01..08 (`ingest_rejections`), which is
    exactly why it is provoked here: a rule with no live victims is one nobody
    would notice breaking, and this one guards the column the target is derived
    from. Its sibling `duration_non_positive` retains 57,322 real rows.
    """
    df = raw_frame(MONTH, rows=20)
    df.loc[0, "tpep_dropoff_datetime"] = pd.NaT
    _, rejected, _ = clean(prepared(df, data_cfg), MONTH, data_cfg)
    assert len(rejected) == 1
    assert rejected["rejection_rule"].iloc[0] == "missing_timestamp"
    assert pd.isna(rejected[data_cfg.clean["target"]].iloc[0])


def test_a_refused_month_never_reaches_the_sidecar(data_cfg):
    """A refusal leaves NOTHING behind — the sidecar is for rows that were
    counted, not for months that were refused (configs/data.yaml:rejected)."""
    cfg = dataclasses.replace(data_cfg, clean={**data_cfg.clean, "max_rejected_fraction": 0.10})
    df = raw_frame(MONTH, rows=10)
    df.loc[0:1, "trip_distance"] = 0.0  # 20% > 10% ceiling
    with pytest.raises(RejectionThresholdError):
        clean(prepared(df, cfg), MONTH, cfg)  # raises before anything is returned


def test_sort_is_deterministic(data_cfg):
    df = prepared(raw_frame(MONTH, rows=50), data_cfg)
    kept, _rejected, _ = clean(df, MONTH, data_cfg)
    once = sort_deterministically(kept, data_cfg)
    twice = sort_deterministically(kept.sample(frac=1, random_state=7), data_cfg)
    pd.testing.assert_frame_equal(once, twice)
