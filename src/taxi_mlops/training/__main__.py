"""CLI: `python -m taxi_mlops.training train`.

`make train` stays M2-S3's to wire — the gate verdict is what makes that target
what it claims to be, and this story deliberately promotes nothing.
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m taxi_mlops.training")
    sub = parser.add_subparsers(dest="command", required=True)

    train = sub.add_parser(
        "train",
        help="fit both baselines and LightGBM v1, score every one of them through "
        "taxi_mlops.training.evaluate, log runs to MLflow",
    )
    train.add_argument(
        "--train-months",
        nargs="+",
        default=None,
        metavar="YYYY-MM",
        help="override the configured train months — the sample-first protocol "
        "(prove the path on one month, then scale). Any run that used it says so.",
    )
    train.add_argument(
        "--ablation",
        action="store_true",
        help="also fit the log1p-target variant (EDA finding E-1: prove it)",
    )
    train.add_argument(
        "--no-mlflow",
        action="store_true",
        help="skip tracking — for a cluster-free smoke test, never for a result",
    )

    # A training run redirected to a log file is block-buffered by default, so a
    # 40-minute fit prints nothing until it ends and reads exactly like a hang.
    # Observed on this story's first full run.
    sys.stdout.reconfigure(line_buffering=True)

    args = parser.parse_args(argv)
    if args.command == "train":
        # FIRST, before a single row is read. The shim may re-exec this process,
        # and re-execing after loading 42M rows would throw that work away and
        # do it twice — observed once (M2-S2) when the call sat inside model.fit.
        from .openmp import ensure_openmp

        print(f"[openmp] {ensure_openmp()}")

        from .run import run

        if args.train_months:
            print(f"[run] SAMPLE RUN — train months overridden: {', '.join(args.train_months)}")
        run(
            train_months=tuple(args.train_months) if args.train_months else None,
            ablation=args.ablation,
            log_to_mlflow=not args.no_mlflow,
        )
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
