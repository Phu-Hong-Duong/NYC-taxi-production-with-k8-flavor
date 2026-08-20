"""CLI: `python -m taxi_mlops.training train` — what `make train` runs.

EXIT CODES ARE PART OF THE CONTRACT (M2-S3, extended M3-S1):

    0  the gate passed and the winner was promoted (or --no-promote was asked for)
    1  the gate REFUSED — the verdict printed with both numbers, registry untouched
    2  the command could not be run at all
    3  NO VERDICT was issued: a sampled run asked for with --no-gate (F-008)

3 is its own code and not 0, because "the gate did not judge this" and "the gate
judged this and was satisfied" are the two things a pipeline must never confuse.

A refusal exits non-zero on purpose. `make train` is a step in a pipeline from
M4 onward, and a gate that says "no" while exiting 0 is a gate the pipeline
cannot hear. `scripts/train_redteam.sh` inverts this deliberately, the way
`RED_TEAM=1 scripts/marts.sh` does: there, the refusal IS the result.
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
        "(prove the path on one month, then scale). GATE-DISQUALIFYING since "
        "M3-S1 (F-008): sampling degrades the floor faster than the model, so a "
        "sampled verdict flatters. Pair it with --no-gate to smoke-test.",
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
    train.add_argument(
        "--no-promote",
        action="store_true",
        help="print the gate verdict but do not touch the registry, even on a pass",
    )
    train.add_argument(
        "--hobble",
        choices=("shuffled-target",),
        default=None,
        help="RED TEAM: cripple the challenger on purpose and submit it to the SAME "
        "gate. Expect exit 1. scripts/train_redteam.sh wraps this and inverts it",
    )
    train.add_argument(
        "--no-gate",
        action="store_true",
        help="the sample-first smoke path: fit, score and print the table, issue NO "
        "verdict, promote nothing (exit 3). Legal ONLY with --train-months, so it "
        "can never skip a gate a promotable run would have faced",
    )
    train.add_argument(
        "--experiment",
        default=None,
        metavar="NAME",
        help="log to this MLflow experiment instead of configs/train.yaml's "
        "(gotcha #17: milestones keep their runs apart)",
    )
    train.add_argument(
        "--story",
        default=None,
        metavar="ID",
        help="tag every run with the story that produced it, e.g. M3-S1. Runs with "
        "no story stated are tagged 'unstated' rather than inheriting somebody else's",
    )

    predict = sub.add_parser(
        "predict",
        help="score the REGISTERED champion on val+test through the same evaluator and "
        "publish the row-level predictions under configs/train.yaml: "
        "evaluate.predictions_dir (M2-S4, the DA error memo's evidence)",
    )
    predict.add_argument(
        "--no-write",
        action="store_true",
        help="print the numbers, publish nothing — for checking the champion resolves",
    )
    predict.add_argument(
        "--floor-train-months",
        nargs="+",
        default=None,
        metavar="YYYY-MM",
        help="RED TEAM ONLY (F-012): fit the published floor on a different month "
        "set than the champion's gate used. Expect the write to be REFUSED and "
        "data/predictions/ to be untouched; scripts/predictions_redteam.sh wraps it",
    )

    batch = sub.add_parser(
        "score-scoring",
        help="score the REGISTERED champion on the SCORING months (M7-S2) and publish "
        "the row-level predictions under configs/train.yaml: "
        "evaluate.scoring_predictions_dir. Monitoring numbers, new ids (KPI-14..17) — "
        "never KPI-09/KPI-10, which belong to a held-out split",
    )
    batch.add_argument(
        "--months",
        nargs="+",
        default=None,
        metavar="YYYY-MM",
        help="narrow to a subset of the CONFIGURED scoring months. It cannot "
        "introduce one: a month absent from configs/data.yaml `scoring.months` is "
        "refused before a row is read",
    )
    batch.add_argument(
        "--no-write",
        action="store_true",
        help="print the numbers, publish nothing — for checking the champion resolves",
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

        from .gate import GateError
        from .run import run

        if args.train_months:
            print(f"[run] SAMPLE RUN — train months overridden: {', '.join(args.train_months)}")
        try:
            result = run(
                train_months=tuple(args.train_months) if args.train_months else None,
                ablation=args.ablation,
                log_to_mlflow=not args.no_mlflow,
                promote=not args.no_promote,
                hobble=args.hobble,
                judge=not args.no_gate,
                experiment=args.experiment,
                story=args.story,
            )
        except GateError as exc:
            # A refusal to JUDGE, which is not a refusal to promote: the gate is
            # declining to produce a verdict at all, so there is no verdict to
            # exit 1 with. Printed here rather than raised as a traceback because
            # it is a decision, not a crash.
            print(f"\n[gate] NO VERDICT: {exc}", file=sys.stderr)
            return 2
        if result.decision is None:
            print("\n[gate] NO VERDICT was issued for this run (see above). Exit 3.")
            return 3
        # The verdict IS the exit code. See the module docstring.
        return 0 if result.decision.passed else 1

    if args.command == "predict":
        # Same reason as `train`: the shim may re-exec, and re-execing after
        # loading the six train months would do that work twice.
        from .openmp import ensure_openmp

        print(f"[openmp] {ensure_openmp()}")

        from .score import ChampionError, score

        try:
            score(
                write=not args.no_write,
                floor_train_months=(
                    tuple(args.floor_train_months) if args.floor_train_months else None
                ),
            )
        except ChampionError as exc:
            print(f"[score] FAIL: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.command == "score-scoring":
        # Same reason as `train` and `predict`: the shim may re-exec, and
        # re-execing after loading a scoring month would do that work twice.
        from .openmp import ensure_openmp

        print(f"[openmp] {ensure_openmp()}")

        from .batch import score_scoring_months
        from .score import ChampionError

        try:
            score_scoring_months(
                months=tuple(args.months) if args.months else None,
                write=not args.no_write,
            )
        except ChampionError as exc:
            print(f"[batch] FAIL: {exc}", file=sys.stderr)
            return 2
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
