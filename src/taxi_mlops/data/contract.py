"""The data contract: year-aware structure, and the ONE dtype cast.

Division of labour, deliberately:

* **Structure is a contract matter.** Columns present/absent/renamed, and the
  dtype every column must have, are checked here. A violation refuses the whole
  month — you cannot drop your way out of a missing column.
* **Row-level domain violations are a CLEANING matter** (see clean.py). A
  passenger_count of 99 is one bad row, not a broken file, so it is counted
  against a named rule and dropped, never silently and never as a schema crash.

`nullable` in configs/data.yaml describes the guarantee downstream gets — i.e.
the POST-clean state. The input schema relaxes it, because raw is raw; the
output schema enforces it, which makes the output contract a live check on the
cleaning rules themselves.

Year-awareness (gotcha #6) is structural, not cosmetic: `year_columns` carry the
first year they are required, so 2019 does not demand `cbd_congestion_fee` and
2025 does. Observed 2026-08-16: 2019 files carry 19 columns with `airport_fee`;
2025-01 carries 20 with `Airport_fee` and `cbd_congestion_fee`, and half the id
columns arrive as int32 instead of int64. The canonical cast is what makes those
two years the same table downstream.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pandera.pandas as pa

from .config import DataConfig
from .errors import DataContractError, SchemaEventError

TARGET_DTYPE = "float64"


def year_of(month: str) -> int:
    return int(month.split("-")[0])


def expected_columns(cfg: DataConfig, year: int) -> dict[str, dict[str, Any]]:
    """Canonical column -> spec, for one year. Required first, then year columns.

    A year column whose `from_year` is still ahead is included as optional: TLC
    sometimes ships a column early and all-null (2019-01 already carries
    `airport_fee`), and an early arrival is not a defect.
    """
    specs: dict[str, dict[str, Any]] = {}
    for name, spec in cfg.contract["required_columns"].items():
        specs[name] = {**spec, "required": True}
    for name, spec in cfg.contract["year_columns"].items():
        specs[name] = {**spec, "required": year >= spec["from_year"]}
    return specs


def resolve_aliases(
    df: pd.DataFrame, specs: dict[str, dict[str, Any]]
) -> tuple[pd.DataFrame, list[str]]:
    """Rename known spellings to their canonical name, announcing each one."""
    renames: dict[str, str] = {}
    events: list[str] = []
    for name, spec in specs.items():
        if name in df.columns:
            continue
        for alias in spec.get("aliases", []) or []:
            if alias in df.columns:
                renames[alias] = name
                events.append(f"alias applied: {alias!r} -> {name!r}")
                break
    return (df.rename(columns=renames), events) if renames else (df, events)


def check_columns(
    df: pd.DataFrame,
    specs: dict[str, dict[str, Any]],
    month: str,
    on_unknown: str = "refuse",
) -> list[str]:
    """Presence/absence/unknown checks. Returns the announced events; raises on refusal.

    `on_unknown` comes from configs/data.yaml (`contract.on_unknown_column`):
    `refuse` stops the month, `warn` announces and continues. Either way the
    column is NEVER silent — that is the whole point (DE charter).
    """
    events: list[str] = []
    missing = [n for n, s in specs.items() if s["required"] and n not in df.columns]
    unknown = [c for c in df.columns if c not in specs]
    if missing:
        # The unknown columns are named HERE too, and that is not decoration.
        # A RENAMED column is both an absence and an arrival, and this branch
        # raises before the unknown-column branch below can ever be reached —
        # so a refusal that named only the absence sent the reader looking for a
        # deletion when the field had merely moved. Measured at M7-S1 against a
        # real 2025 file: `VendorID -> VendorID_v2` reported `['VendorID']`
        # absent and said nothing about what had arrived in its place.
        arrived = f" Unknown column(s) in the same file: {unknown}." if unknown else ""
        raise SchemaEventError(
            f"{month}: required column(s) absent from the source file: {missing}."
            f"{arrived} "
            "A column that vanished is an EVENT -- update the contract deliberately "
            "(if it was RENAMED, an `aliases:` entry in configs/data.yaml is the fix)."
        )
    for name in (n for n, s in specs.items() if not s["required"] and n in df.columns):
        events.append(f"column {name!r} present ahead of its from_year -- accepted, typed, unused")

    if unknown:
        message = (
            f"{month}: unknown column(s) in the source file: {unknown}. "
            "A new column is an EVENT (DE charter) -- add it to configs/data.yaml "
            "year_columns (or as an alias) before it reaches anything downstream."
        )
        if on_unknown == "refuse":
            raise SchemaEventError(message)
        events.append(f"WARNING: {message}")
    return events


def cast(df: pd.DataFrame, specs: dict[str, dict[str, Any]]) -> pd.DataFrame:
    """THE dtype cast. Nowhere else in the codebase may call astype on these columns.

    Gotcha #7: raw dtypes are the crash source downstream (nullable float
    passenger_count, object flags, int32-vs-int64 ids across years). One cast,
    at ingest, in this function.
    """
    out = df.copy()
    for name, spec in specs.items():
        if name not in out.columns:
            continue
        target = spec["dtype"]
        if out[name].dtype == target:
            continue
        try:
            out[name] = out[name].astype(target)
        except (TypeError, ValueError) as exc:
            raise DataContractError(
                f"column {name!r}: cannot cast {out[name].dtype} -> {target}: {exc}"
            ) from exc
    return out


def dtypes_table(df: pd.DataFrame) -> str:
    """The dtypes table ingest prints — the evidence that the cast happened."""
    width = max(len(str(c)) for c in df.columns)
    lines = [
        f"  {'column'.ljust(width)}  dtype           nulls",
        f"  {'-' * width}  --------------  -----",
    ]
    for col in df.columns:
        dtype = str(df[col].dtype).ljust(14)
        lines.append(f"  {str(col).ljust(width)}  {dtype}  {int(df[col].isna().sum())}")
    return "\n".join(lines)


def _column(spec: dict[str, Any], *, nullable: bool, with_domain: bool) -> pa.Column:
    checks = []
    if with_domain:
        if "min" in spec:
            checks.append(pa.Check.ge(spec["min"]))
        if "max" in spec:
            checks.append(pa.Check.le(spec["max"]))
        if "allowed" in spec:
            checks.append(pa.Check.isin(spec["allowed"]))
    return pa.Column(spec["dtype"], checks=checks or None, nullable=nullable, required=False)


def input_schema(cfg: DataConfig, year: int) -> pa.DataFrameSchema:
    """Structure only: right dtypes, nothing about row validity (that is clean.py's job)."""
    specs = expected_columns(cfg, year)
    return pa.DataFrameSchema(
        {n: _column(s, nullable=True, with_domain=False) for n, s in specs.items()},
        strict=False,
        coerce=False,
        name=f"tlc_yellow_input_{year}",
    )


def output_schema(cfg: DataConfig, year: int) -> pa.DataFrameSchema:
    """What downstream is promised: post-clean nullability AND the domains the rules enforced.

    This doubles as a check on clean.py — if a rejection rule stops working, the
    domain check here fails and the month is refused instead of quietly shipped.
    """
    specs = expected_columns(cfg, year)
    columns = {
        n: _column(s, nullable=s.get("nullable", True), with_domain=True) for n, s in specs.items()
    }
    columns[cfg.clean["target"]] = pa.Column(TARGET_DTYPE, nullable=False, required=True)
    return pa.DataFrameSchema(
        columns, strict=False, coerce=False, name=f"tlc_yellow_output_{year}"
    )


def _validate(schema: pa.DataFrameSchema, df: pd.DataFrame, month: str, stage: str) -> pd.DataFrame:
    try:
        return schema.validate(df, lazy=True)
    except pa.errors.SchemaErrors as exc:
        columns = ["column", "check", "failure_case"]
        cases = exc.failure_cases[columns].head(10).to_string(index=False)
        raise DataContractError(
            f"{month}: {stage} contract violated ({len(exc.failure_cases)} failure case(s)); "
            f"first rows:\n{cases}"
        ) from exc


def validate_input(df: pd.DataFrame, month: str, cfg: DataConfig) -> tuple[pd.DataFrame, list[str]]:
    """Resolve aliases, refuse schema events, cast once, check structure. Returns (df, events)."""
    specs = expected_columns(cfg, year_of(month))
    df, events = resolve_aliases(df, specs)
    events += check_columns(df, specs, month, cfg.contract["on_unknown_column"])
    df = cast(df, specs)
    return _validate(input_schema(cfg, year_of(month)), df, month, "input"), events


def validate_output(df: pd.DataFrame, month: str, cfg: DataConfig) -> pd.DataFrame:
    return _validate(output_schema(cfg, year_of(month)), df, month, "output")
