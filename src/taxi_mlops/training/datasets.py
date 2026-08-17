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
    """Exactly what must be read off disk: the passthrough features, the pickup
    timestamp the temporal features are derived from, and the label."""
    needed = [quote_time.PICKUP_TIMESTAMP, *features_cfg["passthrough"], target]
    seen: list[str] = []
    for column in needed:
        if column not in seen:
            seen.append(column)
    return seen


def load_split(
    split: str,
    data_cfg: DataConfig,
    features_cfg: dict,
    target: str,
    *,
    months: tuple[str, ...] | None = None,
) -> Split:
    """Read a split's months, build features, return matrix + target."""
    wanted = months if months is not None else getattr(data_cfg.splits, split)
    if not wanted:
        raise ValueError(f"split {split!r} has no months in configs/train.yaml")

    columns = required_columns(features_cfg, target)
    frames = []
    for month in wanted:
        path = data_cfg.processed_path(month)
        if not path.exists():
            raise FileNotFoundError(
                f"{path} is missing — run `make data` before training "
                "(the model never reads data/raw, only what the contract blessed)"
            )
        frames.append(pq.read_table(path, columns=columns).to_pandas())

    frame = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
    features = quote_time.build_features(frame, features_cfg)
    y = frame[target].astype("float64")
    # Free the source frame's memory before the caller stacks another split on
    # top of it: six months of train is the peak this program has, and it is
    # reached here rather than in LightGBM.
    del frames, frame
    return Split(name=split, months=tuple(wanted), features=features, y=y)
