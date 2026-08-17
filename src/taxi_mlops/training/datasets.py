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
