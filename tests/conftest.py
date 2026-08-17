"""Shared fixtures. Markers: unit (default), integration (needs cluster), smoke.
pyproject addopts excludes integration+smoke by default — CI stays cluster-free.

The data fixtures below deliberately build on the REAL configs/data.yaml (paths
redirected into tmp_path) rather than an invented one: a test that carries its
own copy of the contract stops testing the contract that ships.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd
import pytest

from taxi_mlops.data.config import DataConfig, Splits, load_config

RAW_2019_DTYPES = {
    "VendorID": "int64",
    "passenger_count": "float64",
    "trip_distance": "float64",
    "RatecodeID": "float64",
    "PULocationID": "int64",
    "DOLocationID": "int64",
    "payment_type": "int64",
}
MONEY_COLUMNS = [
    "fare_amount",
    "extra",
    "mta_tax",
    "tip_amount",
    "tolls_amount",
    "improvement_surcharge",
    "total_amount",
    "congestion_surcharge",
]


def raw_frame(month: str = "2019-01", rows: int = 8) -> pd.DataFrame:
    """A raw-shaped 2019 TLC frame: valid rows, in the dtypes the source really ships."""
    start = pd.Timestamp(f"{month}-05 08:00:00")
    pickup = pd.to_datetime([start + pd.Timedelta(minutes=7 * i) for i in range(rows)])
    df = pd.DataFrame(
        {
            "VendorID": np.ones(rows, dtype="int64"),
            "tpep_pickup_datetime": pickup,
            "tpep_dropoff_datetime": pickup + pd.Timedelta(minutes=10),
            "passenger_count": np.ones(rows, dtype="float64"),
            "trip_distance": np.full(rows, 2.5, dtype="float64"),
            "RatecodeID": np.ones(rows, dtype="float64"),
            "store_and_fwd_flag": pd.Series(["N"] * rows, dtype="object"),
            "PULocationID": np.full(rows, 100, dtype="int64"),
            "DOLocationID": np.full(rows, 200, dtype="int64"),
            "payment_type": np.ones(rows, dtype="int64"),
        }
    )
    for column in MONEY_COLUMNS:
        df[column] = np.full(rows, 1.0, dtype="float64")
    df["airport_fee"] = pd.Series([None] * rows, dtype="object")
    return df


def raw_frame_2025(rows: int = 4) -> pd.DataFrame:
    """A 2025-shaped frame — the columns AND dtypes observed live on 2026-08-16.

    2025 renames airport_fee -> Airport_fee, adds cbd_congestion_fee, and ships
    the id columns as int32 where 2019 shipped int64. If the contract were frozen
    to 2019 this frame would fail, which is exactly what this shape is for.
    """
    df = raw_frame("2025-01", rows)
    df = df.rename(columns={"airport_fee": "Airport_fee"})
    df["Airport_fee"] = np.full(rows, 1.75, dtype="float64")
    df["cbd_congestion_fee"] = np.full(rows, 0.75, dtype="float64")
    for column in ("VendorID", "PULocationID", "DOLocationID"):
        df[column] = df[column].astype("int32")
    for column in ("passenger_count", "RatecodeID"):
        df[column] = df[column].astype("int64")
    return df


@pytest.fixture
def data_cfg(tmp_path) -> DataConfig:
    """The shipped configs/data.yaml, with every path pointed inside tmp_path."""
    cfg = load_config()
    source = dict(cfg.source)
    source["raw_dir"] = str(tmp_path / "raw")
    source["processed_dir"] = str(tmp_path / "processed")
    source["manifest_path"] = str(tmp_path / "raw_manifest.json")
    # The rejected sidecar's path is redirected here too. Miss this and every
    # test that ingests writes into the REAL data/rejected/, quietly corrupting
    # the tree the DVC pin describes — a test suite that damages the data is the
    # worst kind of green.
    rejected = dict(cfg.rejected)
    rejected["dir"] = str(tmp_path / "rejected")
    return dataclasses.replace(
        cfg,
        source=source,
        rejected=rejected,
        # Same reason as `rejected` above, one tree further along: with the real
        # `data/predictions` in place a test that builds the analyst layer would
        # otherwise pick up the REAL published predictions and reconcile them
        # against three seeded months.
        predictions_dir=str(tmp_path / "predictions"),
        splits=Splits(train=("2019-01",), val=("2019-02",), test=("2019-03",)),
    )
