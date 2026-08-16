"""CLI: `python -m taxi_mlops.data ingest`. Exit 0 means the contract held.

Any IngestError exits 1 with a typed, file-naming message and nothing written.
"""

from __future__ import annotations

import argparse
import sys

from .config import load_config
from .errors import IngestError
from .ingest import ingest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m taxi_mlops.data")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("ingest", help="download -> validate -> clean -> split, with counts")
    run.add_argument(
        "--month",
        action="append",
        dest="months",
        help="ingest only this month (repeatable); default = every month in configs/train.yaml",
    )
    run.add_argument("--config", default="configs/data.yaml")
    run.add_argument("--train-config", default="configs/train.yaml")
    args = parser.parse_args(argv)

    cfg = load_config(args.config, args.train_config)
    try:
        ingest(args.months, cfg)
    except IngestError as exc:
        print(f"\n[ingest] REFUSED — {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
