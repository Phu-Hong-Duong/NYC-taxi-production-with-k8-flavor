"""Run a month's REAL file through the data contract and report what it says.

M7-S1. The kickoff's schema-drift leg is a MEASUREMENT, not an assumption: the
contract is year-aware by design (gotcha #6 — `year_columns` carry `from_year`,
and a 2025-shaped frame validates in unit tests), so a 2025 file may well pass.
Whether it does is a fact about TLC's 2025 schema and our config, and the only
honest way to hold it is to ask.

WHAT THIS SCRIPT REFUSES TO DO. It writes no processed output, no sidecar, no
rejection report and no row anywhere under `data/processed`, `data/rejected` or
`data/scoring`. It does not touch `data/raw` or `data/raw_manifest.json` either:
the file it downloads lands in its own probe directory under its own manifest,
so probing a month is not a way to acquire one. A probe that leaves data behind
is an ingest wearing a smaller name.

EXIT CODES — the outcome is the RESULT, so it is in the code:
  0  VALIDATED  the file passed the input contract for its year
  1  REFUSED    the contract said no (SchemaEventError / DataContractError),
                naming the month and the columns. This is a measurement.
  2  the probe itself failed (download, unreadable bytes, bad arguments)

`--fixture` demonstrates the refusal SHAPE on a structurally-wrong frame derived
from a real file, for the case where the real one validates: a contract whose
refusal has never been watched is a claim, not a check.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from taxi_mlops.data.config import load_config, repo_root
from taxi_mlops.data.contract import dtypes_table, expected_columns, validate_input, year_of
from taxi_mlops.data.download import ensure_month, load_manifest, save_manifest
from taxi_mlops.data.errors import IngestError
from taxi_mlops.data.ingest import read_raw

#: The fixture shapes, each naming a real failure mode the contract must refuse.
FIXTURES = {
    "drop-required": "delete a required column — the shape of TLC removing a field",
    "rename-required": "rename a required column to an unknown spelling — a field that moved",
    "unknown-column": "add a column no config knows — the shape of TLC adding a field",
}


def _probe_config(raw_dir: str):
    """A config whose acquisition points at a throwaway directory.

    Everything else — the contract, the year columns, the aliases, the cast — is
    the SHIPPED config, read from `configs/data.yaml`. A probe against a copy of
    the contract would measure the copy.
    """
    cfg = load_config()
    source = {
        **cfg.source,
        "raw_dir": raw_dir,
        "manifest_path": f"{raw_dir}/probe_manifest.json",
    }
    return replace(cfg, source=source)


def _apply_fixture(df, kind: str, cfg, month: str):
    """Break the frame's STRUCTURE in one named way. Returns (df, description)."""
    specs = expected_columns(cfg, year_of(month))
    required = [n for n, s in specs.items() if s["required"] and n in df.columns]
    victim = required[0]
    if kind == "drop-required":
        return df.drop(columns=[victim]), f"dropped required column {victim!r}"
    if kind == "rename-required":
        return (
            df.rename(columns={victim: f"{victim}_v2"}),
            f"renamed required column {victim!r} -> {victim + '_v2'!r}",
        )
    if kind == "unknown-column":
        out = df.copy()
        out["surge_multiplier"] = 1.0
        return out, "added unknown column 'surge_multiplier'"
    raise KeyError(kind)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="contract_probe")
    parser.add_argument("--month", required=True, help="e.g. 2025-01")
    parser.add_argument(
        "--raw-dir",
        default="data/probe",
        help="throwaway acquisition directory; NEVER data/raw (default: %(default)s)",
    )
    parser.add_argument(
        "--fixture",
        choices=sorted(FIXTURES),
        help="break the real frame's structure in this named way before validating",
    )
    parser.add_argument("--rows", type=int, default=0, help="validate only the first N rows")
    args = parser.parse_args(argv)

    if Path(args.raw_dir).resolve() == (repo_root() / "data" / "raw").resolve():
        print("[probe] REFUSED: --raw-dir may not be data/raw. A probe acquires nothing.")
        return 2

    cfg = _probe_config(args.raw_dir)
    month = args.month
    print(f"[probe] month {month} (contract year {year_of(month)})")
    print(f"[probe] acquisition dir {args.raw_dir}/ — data/raw and its manifest are untouched")

    manifest_path = cfg.path_for("manifest_path")
    manifest = load_manifest(manifest_path)
    try:
        action = ensure_month(cfg, month, manifest)
        save_manifest(manifest_path, manifest)
        raw = cfg.raw_path(month)
        print(f"[probe] raw: {raw.name} [{action}] {raw.stat().st_size:,} bytes")
        print(f"[probe] sha256: {manifest[month]['sha256']}")
        df = read_raw(raw)
    except Exception as exc:  # acquisition/readability is the PROBE failing, not the contract
        print(f"[probe] PROBE FAILED — {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.rows:
        df = df.head(args.rows)
    print(f"[probe] {len(df):,} row(s), {len(df.columns)} column(s) as delivered:")
    print(f"        {list(df.columns)}")

    if args.fixture:
        df, described = _apply_fixture(df, args.fixture, cfg, month)
        print(f"[probe] FIXTURE {args.fixture}: {described}")
        print(f"        ({FIXTURES[args.fixture]})")

    try:
        validated, events = validate_input(df, month, cfg)
    except IngestError as exc:
        print(f"\n[probe] REFUSED — {type(exc).__name__}: {exc}")
        print("[probe] nothing was written: no processed output, no sidecar, no report.")
        return 1

    for event in events:
        print(f"[probe] SCHEMA EVENT: {event}")
    print("[probe] dtypes after THE cast (contract.cast, the only cast in the codebase):")
    print(dtypes_table(validated))
    print(
        f"\n[probe] VALIDATED — {month} passed the input contract for {year_of(month)} "
        f"with {len(events)} schema event(s). Nothing was written."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
