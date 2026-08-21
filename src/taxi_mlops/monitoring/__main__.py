"""`python -m taxi_mlops.monitoring` — the drift job, and the headroom leg that argued its bar.

M7-S3. Three subcommands, and the split between them is the story's discipline:

  headroom   Compare the HELD-OUT 2019 months (val, test) against the train
             reference. These months have a verdict already — the champion was
             measured on them and PROMOTED — so the distance they sit at is by
             construction a distance that did NOT warrant action. This is the
             input to the threshold argument in `docs/slo_serving.md` §8, and it
             is RUN BEFORE the 2020 months are ever compared (M7 law 4).

  drift      Compare one scoring month against the same reference, print the
             numbers, optionally PUSH them.

  push-state Read the gateway back. A pusher that reports its own success is
             M4-S4's `flyte run --follow` exiting 0 over a failed run.

THIS JOB DOES NOT JUDGE, AND THAT IS DELIBERATE.
No threshold appears in this module or anywhere under `src/taxi_mlops/monitoring/`.
It computes quantities and pushes them; the bar lives in exactly one place,
`infra/monitoring/alerting_rules.yml` (signal A-8), argued in
`docs/slo_serving.md` §8, and a test fails if a bar-shaped constant appears here.
That is M5-S4's load-drill precedent — *"a READER: it POSTs and it times, and it
does not judge"* — and F-013's one-home law, applied to a new kind of number.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request

from ..data.config import repo_root
from .drift import DriftReport, compute_drift, compute_split_drift, write_report
from .pushgateway import (
    DEFAULT_IN_CLUSTER_URL,
    FRESHNESS_METRIC,
    Metric,
    PushError,
    push_metrics,
)

#: Where the tracked records land. `automation/runs/**/*.json` is tracked (F-029),
#: so a drift number a gate replays is a number review can see.
RECORD_DIR = repo_root() / "automation" / "runs" / "m7-drift"

#: The pushgateway job name. One string, referenced by the rules file's own
#: selectors and by `push-state` — F-017's both-sides rule for a label.
PUSH_JOB = "taxi-drift"


def build_metrics(report: DriftReport) -> list[Metric]:
    """The wire form of one drift report. Raw quantities only — no verdict."""
    month_labels = {"month": report.month, "reference": report.reference}
    metrics: list[Metric] = []

    for column in report.columns:
        metrics.append(
            Metric(
                name="taxi_drift_psi",
                value=float(column.psi),
                help=(
                    "Population stability index of one monitored column against the "
                    "champion's training distribution. 0 = identical; unbounded above."
                ),
                labels={**month_labels, "column": column.column, "kind": column.kind},
            )
        )
    for column in report.columns:
        metrics.append(
            Metric(
                name="taxi_drift_unseen_share",
                value=float(column.unseen_share),
                help=(
                    "Share of current rows in a category the reference never held. "
                    "Reported beside PSI and never folded into it: an unseen category "
                    "is a different event from a re-weighted one."
                ),
                labels={**month_labels, "column": column.column},
            )
        )

    metrics.append(
        Metric(
            name="taxi_drift_volume_ratio",
            value=float(report.volume_ratio),
            help=(
                "Trips per day this month divided by trips per day in the reference. "
                "Volume is the one marginal that cannot be averaged away (F-045)."
            ),
            labels=month_labels,
        )
    )
    metrics.append(
        Metric(
            name="taxi_drift_rows_total",
            value=float(report.current_rows),
            help="Rows compared for this month.",
            labels=month_labels,
        )
    )
    metrics.append(
        Metric(
            name="taxi_drift_reference_rows_total",
            value=float(report.reference_rows),
            help="Rows in the reference (the champion's train months).",
            labels=month_labels,
        )
    )
    metrics.append(
        Metric(
            name=FRESHNESS_METRIC,
            value=float(time.time()),
            help=(
                "Unix time at which this month's drift job last completed. A pushed "
                "metric persists after its producer dies, so every other series here "
                "is only meaningful beside this one."
            ),
            labels=month_labels,
        )
    )
    return metrics


def _print_report(report: DriftReport) -> None:
    print(
        f"[drift] {report.month}  vs {report.reference} "
        f"({'+'.join(report.reference_months)}, {report.reference_rows:,} rows)"
    )
    print(
        f"[drift]   rows {report.current_rows:,} · "
        f"{report.current_trips_per_day:,.0f} trips/day against the reference's "
        f"{report.reference_trips_per_day:,.0f} · volume ratio {report.volume_ratio:.4f}"
    )
    print(
        f"[drift]   denominator: {report.current_days} CALENDAR day(s), of which "
        f"{report.current_observed_days} held a trip (F-051: a day with no trips must "
        "not leave the denominator with the numerator)"
    )
    for column in report.columns:
        role = "TARGET" if column.column == "trip_duration_minutes" else "input "
        print(
            f"[drift]   {role} {column.column:<22s} PSI {column.psi:8.4f}  "
            f"unseen {column.unseen_share * 100:6.3f}%  "
            f"bins ref {column.reference_bins:3d} / cur {column.current_bins:3d}"
        )
        top = column.top_moves[0] if column.top_moves else None
        if top:
            print(
                f"[drift]          largest move: bin {top['bin']!r} "
                f"{float(top['reference_share']) * 100:.3f}% -> "
                f"{float(top['current_share']) * 100:.3f}% "
                f"({float(top['delta']) * 100:+.3f} pts)"
            )
    print(
        "[drift]   no verdict is issued here — the bar lives in "
        "infra/monitoring/alerting_rules.yml (A-8), argued in docs/slo_serving.md §8."
    )


def _cmd_headroom(args: argparse.Namespace) -> int:
    print(
        "[headroom] the two 2019 months the champion was JUDGED on, against the months "
        "it was FITTED on. Both have a verdict already: PROMOTE. Whatever distance they"
    )
    print(
        "[headroom] sit at is a distance that did not warrant action, which is what makes "
        "it legal to argue a bar from (M7 law 4)."
    )
    reports = []
    for split in ("val", "test"):
        report = compute_split_drift(split)
        reports.append(report)
        _print_report(report)
        print()
    path = RECORD_DIR / "headroom.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({r.month: r.to_dict() for r in reports}, indent=2, sort_keys=True) + "\n"
    )
    print(f"[headroom] recorded {path.relative_to(repo_root())}")
    hi = max(r.max_input_psi for r in reports)
    print(
        f"[headroom] highest INPUT-column PSI across both held-out months: {hi:.4f}. "
        "docs/slo_serving.md §8 argues the bar from this and states its margin."
    )
    return 0


def _cmd_drift(args: argparse.Namespace) -> int:
    months = args.months
    exit_code = 0
    for month in months:
        report = compute_drift(month)
        _print_report(report)
        path = write_report(report, RECORD_DIR / f"drift-{month}.json")
        print(f"[drift]   recorded {path.relative_to(repo_root())}")
        if args.push:
            metrics = build_metrics(report)
            try:
                target = push_metrics(
                    metrics,
                    url=args.pushgateway,
                    job=PUSH_JOB,
                    grouping={"month": report.month},
                )
            except PushError as error:
                print(f"[drift]   PUSH FAILED: {error}", file=sys.stderr)
                exit_code = 1
                continue
            print(f"[drift]   pushed {len(metrics)} series -> {target}")
        print()
    return exit_code


def _cmd_push_state(args: argparse.Namespace) -> int:
    """Read the gateway's own /metrics back. A pusher must not be its own witness."""
    target = args.pushgateway.rstrip("/") + "/metrics"
    with urllib.request.urlopen(target, timeout=30) as response:  # noqa: S310
        body = response.read().decode("utf-8")
    lines = [
        line
        for line in body.splitlines()
        if line.startswith("taxi_drift_") and not line.startswith("#")
    ]
    print(f"[push-state] {target} holds {len(lines)} taxi_drift_* sample(s)")
    for line in sorted(lines):
        print(f"[push-state]   {line}")
    return 0 if lines else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="taxi_mlops.monitoring", description=__doc__)
    parser.add_argument(
        "--pushgateway",
        default=DEFAULT_IN_CLUSTER_URL,
        help="gateway base URL (host-side callers pass a port-forwarded localhost)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    headroom = sub.add_parser(
        "headroom", help="drift of the held-out 2019 months (the bar's input)"
    )
    headroom.set_defaults(func=_cmd_headroom)

    drift = sub.add_parser("drift", help="drift of one or more scoring months")
    drift.add_argument("--months", nargs="+", required=True)
    drift.add_argument("--push", action="store_true", help="push to the gateway")
    drift.set_defaults(func=_cmd_drift)

    state = sub.add_parser("push-state", help="read the gateway back")
    state.set_defaults(func=_cmd_push_state)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
