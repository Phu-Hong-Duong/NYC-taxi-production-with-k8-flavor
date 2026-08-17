"""Target derivation and counted rejections. No row leaves quietly.

Two counts per rule, on purpose:

* **rejected_by** — rows attributed to the FIRST rule they violate. These sum
  exactly to the number of rows dropped, so the table balances against the row
  counts and nothing is double-counted.
* **matched** — rows the rule hits independently of the others. Without this a
  rule sitting behind an overlapping earlier rule reads as `0` and looks dead
  when it is merely shadowed.

Since M2-S1 the dropped rows are also RETAINED (F-005), not only counted: the
same pass that builds the table builds the sidecar frame, carrying two columns.

* ``rejection_rule`` — the first rule violated. Same attribution as
  ``rejected_by``, which is what makes the sidecar reconcile to the report
  exactly; ``make duckdb`` fails if it ever does not.
* ``rejection_rules`` — every rule the row violates, comma-separated, so the
  shadowed rules are visible per ROW as well as per count. A 200-minute trip
  that also has a zero distance is filed under ``duration_above_max`` and still
  says so.

Every threshold and bound is read from configs/data.yaml — the rules here own
the LOGIC, never the numbers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import DataConfig
from .errors import RejectionThresholdError

# The sidecar's own two columns. Names, not knobs: `trips_rejected` publishes
# them and the reconciliation cites them, so they are a contract in reviewed
# code — the same call analyst.VIEWS makes about view names.
RULE_COLUMN = "rejection_rule"
RULES_COLUMN = "rejection_rules"


@dataclass
class RejectionReport:
    """The per-month rejection table: printed, and written beside the output."""

    month: str
    rows_in: int
    rows_out: int = 0
    rules: list[dict[str, Any]] = field(default_factory=list)

    @property
    def rows_rejected(self) -> int:
        return self.rows_in - self.rows_out

    @property
    def rejected_fraction(self) -> float:
        return self.rows_rejected / self.rows_in if self.rows_in else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "month": self.month,
            "rows_in": self.rows_in,
            "rows_out": self.rows_out,
            "rows_rejected": self.rows_rejected,
            "rejected_fraction": round(self.rejected_fraction, 6),
            "rules": self.rules,
        }

    def table(self) -> str:
        width = max([len(r["name"]) for r in self.rules] + [len("rule")])
        head = f"  {'rule'.ljust(width)}  rejected_by       pct   matched"
        lines = [head, f"  {'-' * width}  -----------  --------  --------"]
        for rule in self.rules:
            pct = 100 * rule["rejected_by"] / self.rows_in if self.rows_in else 0.0
            lines.append(
                f"  {rule['name'].ljust(width)}  {rule['rejected_by']:>11,}  {pct:>7.3f}%"
                f"  {rule['matched']:>8,}"
            )
        lines.append(f"  {'-' * width}  -----------  --------  --------")
        lines.append(
            f"  {'TOTAL'.ljust(width)}  {self.rows_rejected:>11,}"
            f"  {100 * self.rejected_fraction:>7.3f}%"
        )
        lines.append(f"  rows in {self.rows_in:,} -> rows out {self.rows_out:,}")
        return "\n".join(lines)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n")


def month_bounds(month: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = pd.Timestamp(f"{month}-01")
    return start, start + pd.offsets.MonthBegin(1)


def add_target(df: pd.DataFrame, cfg: DataConfig) -> pd.DataFrame:
    """Derive the label. The only place trip duration is computed at ingest."""
    out = df.copy()
    delta = out["tpep_dropoff_datetime"] - out["tpep_pickup_datetime"]
    out[cfg.clean["target"]] = (delta.dt.total_seconds() / 60.0).astype("float64")
    return out


def _masks(df: pd.DataFrame, month: str, cfg: DataConfig) -> list[tuple[str, pd.Series, dict]]:
    """Build (name, violation_mask, params) per configured rule, in configured order."""
    target = cfg.clean["target"]
    cols = cfg.contract["required_columns"]
    duration = df[target]
    start, end = month_bounds(month)
    pickup = df["tpep_pickup_datetime"]

    def falsy(series: pd.Series) -> pd.Series:
        """NA-safe boolean mask: pd.NA in a comparison means 'not a violation'."""
        return series.fillna(False).astype(bool)

    def between(column: str) -> pd.Series:
        spec = cols[column]
        series = df[column]
        return falsy((series < spec["min"]) | (series > spec["max"])) | series.isna()

    builders = {
        "missing_timestamp": lambda p: pickup.isna() | df["tpep_dropoff_datetime"].isna(),
        "duration_non_positive": lambda p: falsy(duration <= 0),
        "duration_below_min": lambda p: falsy(duration < p["min_minutes"]),
        "duration_above_max": lambda p: falsy(duration > p["max_minutes"]),
        "pickup_outside_month": lambda p: falsy((pickup < start) | (pickup >= end)),
        # ~(x > 0) is True for NaN too: a missing distance is as unusable as a zero one.
        "distance_non_positive": lambda p: ~falsy(df["trip_distance"] > 0),
        "distance_above_max": lambda p: falsy(df["trip_distance"] > p["max_miles"]),
        "fare_negative": lambda p: falsy(df["fare_amount"] < 0),
        "location_out_of_range": lambda p: between("PULocationID") | between("DOLocationID"),
        "passenger_count_out_of_range": lambda p: falsy(
            df["passenger_count"].notna()
            & (
                (df["passenger_count"] < cols["passenger_count"]["min"])
                | (df["passenger_count"] > cols["passenger_count"]["max"])
            )
        ),
    }

    out = []
    for rule in cfg.clean["rules"]:
        name = rule["name"]
        if name not in builders:
            raise KeyError(f"configs/data.yaml names rule {name!r}, which clean.py cannot build")
        params = {k: v for k, v in rule.items() if k != "name"}
        out.append((name, builders[name](params), params))
    return out


def _label_rejected(
    df: pd.DataFrame,
    masks: list[tuple[str, pd.Series, dict]],
    dropped: pd.Series,
    first_rule: pd.Series,
) -> pd.DataFrame:
    """The sidecar frame: every dropped row, with its rule and all its rules.

    The all-match string is built on the SUBSET, never on the whole month: it
    concerns ~1.6% of the rows and running ten string concatenations over 7M
    rows to describe 114k of them would be paid on every ingest forever.
    """
    rejected = df.loc[dropped].copy()
    rejected[RULE_COLUMN] = first_rule.loc[dropped].astype("string")

    joined = np.full(len(rejected), "", dtype=object)
    for name, mask, _params in masks:
        joined = joined + np.where(mask.loc[dropped].to_numpy(), f",{name}", "")
    rejected[RULES_COLUMN] = pd.Series(
        [value[1:] for value in joined], index=rejected.index, dtype="string"
    )
    return rejected.reset_index(drop=True)


def clean(
    df: pd.DataFrame, month: str, cfg: DataConfig
) -> tuple[pd.DataFrame, pd.DataFrame, RejectionReport]:
    """Derive the target, drop rows against named rules, count AND keep every drop.

    Returns (kept, rejected, report). The rejected frame is the F-005 sidecar:
    the same rows the report counts, in the same first-match attribution, so the
    two can be checked against each other rather than merely believed.

    Raises RejectionThresholdError when a month loses more than the configured
    fraction — a month that thin is a broken input, not a cleaning success. The
    raise happens BEFORE anything is returned, so a refused month has no sidecar
    for the same reason it has no output.
    """
    df = add_target(df, cfg)
    report = RejectionReport(month=month, rows_in=len(df))

    masks = _masks(df, month, cfg)
    already = pd.Series(False, index=df.index)
    first_rule = pd.Series(pd.NA, index=df.index, dtype="string")
    for name, mask, params in masks:
        first = mask & ~already
        first_rule[first] = name
        report.rules.append(
            {
                "name": name,
                "rejected_by": int(first.sum()),
                "matched": int(mask.sum()),
                "params": params,
            }
        )
        already = already | mask

    kept = df.loc[~already].reset_index(drop=True)
    report.rows_out = len(kept)

    ceiling = cfg.clean["max_rejected_fraction"]
    if report.rejected_fraction > ceiling:
        raise RejectionThresholdError(
            f"{month}: rejected {report.rejected_fraction:.3%} of rows, ceiling is {ceiling:.3%}. "
            f"That is a broken input, not a cleaning result. Table:\n{report.table()}"
        )
    return kept, _label_rejected(df, masks, already, first_rule), report


def sort_deterministically(df: pd.DataFrame, cfg: DataConfig) -> pd.DataFrame:
    """Stable, configured sort so the same input always writes the same bytes (S2's proof)."""
    return df.sort_values(by=list(cfg.write["sort_by"]), kind="stable").reset_index(drop=True)
