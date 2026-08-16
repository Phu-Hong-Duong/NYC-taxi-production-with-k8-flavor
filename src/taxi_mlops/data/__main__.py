"""CLI: `python -m taxi_mlops.data {ingest,duckdb,query}`. Exit 0 means it held.

Any IngestError exits 1 with a typed, file-naming message and nothing written.
`duckdb` exits 1 if a view's row count disagrees with the ingest report that
wrote the data — a catalogue that points at the wrong months is not an error
anyone notices from the numbers alone.
"""

from __future__ import annotations

import argparse
import sys

from .analyst import connect, report
from .config import load_config
from .errors import IngestError
from .ingest import ingest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m taxi_mlops.data")
    sub = parser.add_subparsers(dest="command", required=True)

    # Declared ONCE and inherited by every subcommand — two copies of the same
    # flag are twins waiting to drift (the port-family lesson, CLAUDE.md).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", default="configs/data.yaml")
    common.add_argument("--train-config", default="configs/train.yaml")

    run = sub.add_parser(
        "ingest",
        parents=[common],
        help="download -> validate -> clean -> split, with counts",
    )
    run.add_argument(
        "--month",
        action="append",
        dest="months",
        help="ingest only this month (repeatable); default = every month in configs/train.yaml",
    )

    sub.add_parser(
        "duckdb",
        parents=[common],
        help="(re)build the analyst views and reconcile their row counts",
    )

    ask = sub.add_parser(
        "query",
        parents=[common],
        help="run one SQL statement against the analyst layer (read-only)",
    )
    ask.add_argument("sql", help="the statement; views are those of `duckdb` (see analyst.VIEWS)")

    args = parser.parse_args(argv)
    cfg = load_config(args.config, args.train_config)

    if args.command == "duckdb":
        return 0 if report(cfg) else 1

    if args.command == "query":
        con = connect(cfg, read_only=True)
        try:
            print(con.sql(args.sql))
        finally:
            con.close()
        return 0

    try:
        ingest(args.months, cfg)
    except IngestError as exc:
        print(f"\n[ingest] REFUSED — {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
