"""Config loading. Every knob comes from configs/*.yaml; none is written in code.

Split months are read from configs/train.yaml (the one source of truth for which
month is train/val/test) and everything else from configs/data.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


def repo_root() -> Path:
    """The repo root, derived from this file's location (works from any cwd)."""
    return Path(__file__).resolve().parents[3]


def load_yaml(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_absolute():
        p = repo_root() / p
    with p.open() as fh:
        return yaml.safe_load(fh)


@dataclass(frozen=True)
class Splits:
    """Which month belongs to which split, from configs/train.yaml."""

    train: tuple[str, ...]
    val: tuple[str, ...]
    test: tuple[str, ...]

    @property
    def months(self) -> tuple[str, ...]:
        """Every configured month, in split order — the ingest work list."""
        return self.train + self.val + self.test

    def split_of(self, month: str) -> str:
        for name in ("train", "val", "test"):
            if month in getattr(self, name):
                return name
        raise KeyError(f"month {month!r} is in no split in configs/train.yaml")


def load_splits(train_config: str | Path = "configs/train.yaml") -> Splits:
    cfg = load_yaml(train_config)["data"]

    def as_tuple(value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        return tuple(value) if isinstance(value, list) else (value,)

    return Splits(
        train=as_tuple(cfg.get("train_months")),
        val=as_tuple(cfg.get("val_month")),
        test=as_tuple(cfg.get("test_month")),
    )


@dataclass(frozen=True)
class DataConfig:
    """configs/data.yaml, plus the splits it deliberately does not duplicate."""

    source: dict[str, Any]
    contract: dict[str, Any]
    clean: dict[str, Any]
    write: dict[str, Any]
    splits: Splits

    def path_for(self, key: str) -> Path:
        """Resolve a configured directory/file key against the repo root."""
        return repo_root() / self.source[key]

    def raw_path(self, month: str) -> Path:
        return self.path_for("raw_dir") / self.source["filename_pattern"].format(month=month)

    def url(self, month: str) -> str:
        return self.source["url_pattern"].format(month=month)

    def processed_path(self, month: str) -> Path:
        """Processed outputs are filed under their split — the split is visible on disk."""
        name = self.source["filename_pattern"].format(month=month)
        return self.path_for("processed_dir") / self.splits.split_of(month) / name

    def rejections_path(self, month: str) -> Path:
        """Written BESIDE the output it explains (no silent drops, ever)."""
        return self.processed_path(month).with_suffix(".rejections.json")


def load_config(
    data_config: str | Path = "configs/data.yaml",
    train_config: str | Path = "configs/train.yaml",
) -> DataConfig:
    raw = load_yaml(data_config)
    return DataConfig(
        source=raw["source"],
        contract=raw["contract"],
        clean=raw["clean"],
        write=raw["write"],
        splits=load_splits(train_config),
    )
