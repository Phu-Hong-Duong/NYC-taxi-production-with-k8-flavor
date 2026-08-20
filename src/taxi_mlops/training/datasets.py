"""Load the split months the contract blessed — and only the columns v1 needs.

Reading the whole frame would cost ~14 GB for six months and buy nothing: the
columns not read are, without exception, columns `taxi_mlops.features` refuses.
The narrow read is therefore not an optimisation, it is the exclusion registry
expressed as I/O — a column that never enters the process cannot leak into a
matrix by accident.

Splits come from `configs/train.yaml` via `taxi_mlops.data.config`, never from a
filename: M1-S2's law (a renamed file must not be able to relabel data) applies
with more force here, because relabelling test as train is undetectable
downstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from ..data.config import DataConfig
from ..features import quote_time


@dataclass(frozen=True)
class Split:
    """One split's feature matrix and target, with the months that produced it."""

    name: str
    months: tuple[str, ...]
    features: pd.DataFrame
    y: pd.Series

    def __len__(self) -> int:
        return len(self.y)


def required_columns(features_cfg: dict, target: str) -> list[str]:
    """Exactly what must be read off disk for this set, plus the label.

    The set is ASKED (`quote_time.source_columns`) rather than the list being
    maintained here: M3-S3's derived features need `PULocationID`/`DOLocationID`
    for geometry and the pickup timestamp for the point-in-time join, and a
    reader widened by hand every time a feature lands is a reader that will one
    day be widened past the exclusion registry.
    """
    needed = [*quote_time.source_columns(features_cfg), target]
    seen: list[str] = []
    for column in needed:
        if column not in seen:
            seen.append(column)
    return seen


def load_frame(
    split: str,
    data_cfg: DataConfig,
    columns: list[str],
    *,
    months: tuple[str, ...] | None = None,
    sample_fraction: float | None = None,
    seed: int = 0,
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """The narrow parquet read, before any feature is built.

    Split out at M3-S3 so the artisan ablation can read six months ONCE and then
    build a dozen different feature matrices from the same rows. Re-reading per
    experiment would spend most of the Design Review's fitting budget (DR-01) on
    I/O and, worse, would let two experiments differ by which rows they happened
    to sample.

    `sample_fraction` is the playbook's sample-first protocol (§3.1), applied
    PER MONTH so the sample is stratified by month rather than by luck — the
    target mean rises 17.3% Jan->Jun, so an unstratified sample of six months is
    a sample of a different distribution. The seed is fixed and passed in.
    """
    wanted = months if months is not None else getattr(data_cfg.splits, split)
    if not wanted:
        raise ValueError(f"split {split!r} has no months in configs/train.yaml")

    frames = []
    for index, month in enumerate(wanted):
        path = data_cfg.processed_path(month)
        if not path.exists():
            raise FileNotFoundError(
                f"{path} is missing — run `make data` before training "
                "(the model never reads data/raw, only what the contract blessed)"
            )
        frame = pq.read_table(path, columns=columns).to_pandas()
        if sample_fraction is not None:
            # A different seed per month, derived from the fixed one: the same
            # seed for every month would take the same ROW POSITIONS out of each,
            # which is not obviously harmful and is not obviously harmless either.
            frame = frame.sample(frac=sample_fraction, random_state=seed + index)
        frames.append(frame)

    frame = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
    del frames
    return frame, tuple(wanted)


def load_split(
    split: str,
    data_cfg: DataConfig,
    features_cfg: dict,
    target: str,
    *,
    months: tuple[str, ...] | None = None,
    fitted: Any = None,
) -> Split:
    """Read a split's months, build features, return matrix + target."""
    columns = required_columns(features_cfg, target)
    frame, wanted = load_frame(split, data_cfg, columns, months=months)
    features = quote_time.build_features(frame, features_cfg, fitted=fitted)
    y = frame[target].astype("float64")
    # Free the source frame's memory before the caller stacks another split on
    # top of it: six months of train is the peak this program has, and it is
    # reached here rather than in LightGBM.
    del frame
    return Split(name=split, months=wanted, features=features, y=y)


@dataclass(frozen=True)
class ScoringMonth:
    """One scoring month's matrix, target and pickup dates (M7-S2).

    A sibling of `Split` rather than a `Split` with `name='scoring'`, because the
    two are not the same kind of thing and every consumer must be made to notice:
    a `Split` is data a model was fitted on or judged on, and a `ScoringMonth` is
    data the model has nothing to do with until it is asked for a quote. The
    difference shows up immediately in what may be said about the numbers — a
    metric on a `Split` can be KPI-09; the same arithmetic here is a monitoring
    series under its own id (`docs/kpi_definitions.md`'s id law).

    `pickup_date` rides alongside because the drift story needs a DAILY series
    and the feature matrix cannot supply one: `hour` and `dayofweek` are cyclical
    and the calendar date is deliberately not a feature (the EDA's finding that
    `month` is a reporting dimension, never a feature). F-045 is the reason this
    is not an afterthought — 2020-03's monthly mean moved 0.36% while its daily
    series ran 240,520 trips to 5,361.
    """

    month: str
    features: pd.DataFrame
    y: pd.Series
    pickup_date: pd.Series

    def __len__(self) -> int:
        return len(self.y)


def load_scoring_month(
    month: str,
    data_cfg: DataConfig,
    features_cfg: dict,
    target: str,
    *,
    fitted: Any = None,
) -> ScoringMonth:
    """Read ONE scoring month, build features through the same path training used.

    The read is the same narrow read (`required_columns`) and the matrix is built
    by the same `quote_time.build_features` — which is the property that makes an
    error number on this month comparable with anything at all. A second feature
    path for monitoring would produce numbers that drift from the model's own
    view of the world and blame the world for it.

    The month must be a CONFIGURED scoring month: `scoring_predictions_path`
    refuses anything else, and the refusal is worth more here than a helpful
    default, because the only way to reach this function with a split month is a
    caller that has confused the two.
    """
    path = data_cfg.scoring_path(month)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing — run `make data-scoring` before scoring "
            f"{month} (the model never reads data/raw, only what the contract blessed)"
        )
    columns = required_columns(features_cfg, target)
    frame = pq.read_table(path, columns=columns).to_pandas()
    features = quote_time.build_features(frame, features_cfg, fitted=fitted)
    y = frame[target].astype("float64")
    pickup = pd.to_datetime(frame[quote_time.PICKUP_TIMESTAMP]).dt.date
    del frame
    return ScoringMonth(month=month, features=features, y=y, pickup_date=pickup)
