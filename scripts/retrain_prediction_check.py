#!/usr/bin/env python3
"""Judge a retrain record against the prediction that was written BEFORE it ran.

M7-S4's completion leg re-ran a 28-minute full-data fit. A repeat of an
expensive fit is only EVIDENCE if what it must produce was written down first
(`automation/runs/m7-retrain/rerun-prediction.json`, committed before launch,
the `automation/runs/m6-gameday/predictions.json` shape); otherwise it is a
do-over, and "it matched" is a sentence nobody can check. This script is the
check: it reads the prediction's own `predicted_exactly` block, resolves each
field against the machine-written record, and exits 1 if any of them disagree.

Three properties it was built with, each paid for elsewhere in this program:

* **It compares at the precision the PREDICTION was written at** (gotcha #42:
  a number that has been through a `%.4f` exists only at that precision, and
  comparing a fresh float against it compares against rounding noise). The
  record holds 3.241213716575134; the prediction says 3.2412; the comparison
  is at four decimals because that is what was claimed.
* **There is a precision FLOOR of one decimal** (gotcha #90: `verify-m6`
  rendered a recorded 13.75 at zero decimals as `14`, which matches almost
  anything). A prediction field written to zero decimals is refused as
  un-checkable rather than compared loosely.
* **The LOOSE block is reported and never fails, and a loose field that did
  not hold is printed as `differs`, not omitted.** A checker that quietly
  drops what it cannot judge degrades toward "they agree", which is the
  failure direction gotcha #94 names.

It reads two files and asks no live system. Usage:

    uv run python scripts/retrain_prediction_check.py \
        [--prediction PATH] [--record PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_PREDICTION = REPO / "automation/runs/m7-retrain/rerun-prediction.json"
DEFAULT_RECORD = REPO / "automation/runs/m7-retrain/latest.json"
DEFAULT_STATUS = REPO / "automation/runs/m7-s4-retrain-rerun.status"

MIN_DECIMALS = 1  # gotcha #90 — a zero-decimal comparison is not a comparison


def _shown(path: Path) -> str:
    """Repo-relative when it can be, absolute when it cannot.

    A checker pointed at a path outside the repo — which is exactly what its
    own red-team tests do — must not die formatting its header. A verifier
    that fails for its own reasons and blames the artifact is gotcha #55.
    """
    try:
        return str(path.resolve().relative_to(REPO))
    except ValueError:
        return str(path)


def _decimals(value: Any) -> int:
    """How many decimal places the PREDICTION was written to."""
    d = Decimal(str(value))
    exponent = d.as_tuple().exponent
    return max(0, -int(exponent))


def _challenger_metric(record: dict, split: str, key: str) -> Any:
    name = record["challenger"]
    for row in record["metrics"]:
        if row["contender"] == name and row["split"] == split:
            return row[key]
    raise KeyError(f"no {name} row for split {split} in the record's metrics")


def _reasons(record: dict) -> list[dict]:
    return record["verdict"]["reasons"]


# Each entry: prediction key -> a callable resolving the RECORD's own answer.
# Written as explicit paths rather than a name-matching walk, because the two
# files are different shapes on purpose: one is a human's claim, the other is
# a machine's report, and a resolver that guessed would be checking a
# convention instead of a number.
EXACT_RESOLVERS = {
    "verdict": lambda r: r["verdict"]["verdict"],
    "challenger_mae_test": lambda r: r["verdict"]["challenger_mae"],
    "challenger_within_test": lambda r: r["verdict"]["challenger_within_rate"],
    "challenger_mae_val": lambda r: _challenger_metric(r, "val", "mae"),
    "challenger_within_val": lambda r: _challenger_metric(
        r, "val", "within_tolerance_rate"
    ),
    "floor": lambda r: r["verdict"]["floor"],
    "floor_mae_test": lambda r: r["verdict"]["floor_mae"],
    "floor_within_test": lambda r: r["verdict"]["floor_within_rate"],
    "incumbent_version": lambda r: r["verdict"]["incumbent_version"],
    "incumbent_mae": lambda r: r["verdict"]["incumbent_mae"],
    "incumbent_within": lambda r: r["verdict"]["incumbent_within_rate"],
    "observed_pct_vs_floor": lambda r: r["verdict"]["observed_pct_vs_floor"],
    "required_pct_vs_floor": lambda r: r["verdict"]["required_pct_vs_floor"],
    "best_iteration": lambda r: r["fit"]["best_iteration"],
    "round_cap": lambda r: r["fit"]["round_cap"],
    "ended_by": lambda r: r["fit"]["ended_by"],
    "n_test_rows": lambda r: r["verdict"]["n"],
    "checks_passed": lambda r: sum(1 for c in _reasons(r) if c["passed"]),
    "checks_failed": lambda r: sum(1 for c in _reasons(r) if not c["passed"]),
}

# Prose fields in `predicted_exactly` that name a SHAPE rather than a value.
# They are checked structurally — never by substring, which would pass on the
# prediction's own wording appearing anywhere.
STRUCTURAL = {
    "why_exact": None,  # the argument for exactness; nothing to resolve
    "which_checks_fail": "incumbent_only",
}

# Reported, never fatal. `exit_code` is here and it is the one that did not
# hold — see docs/retrain_m7.md §4 and gotcha #97.
LOOSE_KEYS = ("fit_seconds", "exit_code", "status_file_word", "mlflow_run_id")


def _structural_incumbent_only(record: dict) -> tuple[bool, str]:
    failed = [c["check"] for c in _reasons(record) if not c["passed"]]
    passed = [c["check"] for c in _reasons(record) if c["passed"]]
    ok = (
        len(failed) == 2
        and all("champion" in c for c in failed)
        and len(passed) == 2
        and not any("champion" in c for c in passed)
    )
    return ok, f"failed: {failed}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prediction", type=Path, default=DEFAULT_PREDICTION)
    ap.add_argument("--record", type=Path, default=DEFAULT_RECORD)
    ap.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    args = ap.parse_args(argv)

    prediction = json.loads(args.prediction.read_text())
    record = json.loads(args.record.read_text())

    print(f"prediction : {_shown(args.prediction)}")
    print(f"             written {prediction['written_at']} by {prediction['written_by']}")
    print(f"record     : {_shown(args.record)}")
    print(f"             generated {record.get('generated_at')}")
    print()

    failures: list[str] = []
    exact = prediction["predicted_exactly"]

    print("EXACT — a mismatch here is the result, not an inconvenience")
    for key, claimed in exact.items():
        if key in STRUCTURAL:
            kind = STRUCTURAL[key]
            if kind is None:
                continue
            ok, detail = _structural_incumbent_only(record)
            print(f"  {'ok  ' if ok else 'FAIL'} {key:<24} structural: {detail}")
            if not ok:
                failures.append(f"{key}: {detail}")
            continue

        resolver = EXACT_RESOLVERS.get(key)
        if resolver is None:
            failures.append(f"{key}: the prediction claims it and this check cannot resolve it")
            print(f"  FAIL {key:<24} UNRESOLVED — the prediction claims a field this check cannot read")
            continue

        actual = resolver(record)
        if isinstance(claimed, str):
            ok = str(actual) == claimed
            shown = actual
        elif isinstance(claimed, bool):
            ok = bool(actual) is claimed
            shown = actual
        elif isinstance(claimed, int):
            ok = int(actual) == claimed
            shown = actual
        else:
            places = _decimals(claimed)
            if places < MIN_DECIMALS:
                failures.append(f"{key}: predicted to {places} decimals — below the floor of {MIN_DECIMALS}")
                print(f"  FAIL {key:<24} predicted to {places} decimals; the floor is {MIN_DECIMALS} (gotcha #90)")
                continue
            ok = round(float(actual), places) == round(float(claimed), places)
            shown = f"{float(actual):.{places + 6}f} -> {round(float(actual), places)}"
        print(f"  {'ok  ' if ok else 'FAIL'} {key:<24} predicted {claimed!r:<22} record {shown}")
        if not ok:
            failures.append(f"{key}: predicted {claimed!r}, record {actual!r}")

    print()
    print("MUST HOLD REGARDLESS — properties of the path, not of the numbers")
    must = [
        ("promoted is false", record.get("promoted") is False, repr(record.get("promoted"))),
        (
            "champion_alias_version is 2",
            str(record.get("champion_alias_version")) == "2",
            repr(record.get("champion_alias_version")),
        ),
        (
            "the record is full-data",
            record.get("sampled") is False,
            f"sampled={record.get('sampled')!r}",
        ),
    ]
    for name, ok, detail in must:
        print(f"  {'ok  ' if ok else 'FAIL'} {name:<32} {detail}")
        if not ok:
            failures.append(f"{name}: {detail}")

    print()
    print("LOOSE — reported, never fatal; a loose field that DIFFERS is printed as differs")
    loose = prediction["predicted_loosely"]
    status_word = (
        args.status.read_text().strip()
        if args.status.exists()
        else "(no status file at the given path)"
    )
    observed = {
        "fit_seconds": record["fit"]["seconds"],
        "mlflow_run_id": record["fit"]["run_id"],
        # The status file holds the code the DETACHED WRAPPER saw, which is
        # make's, not the CLI's — the whole of gotcha #97.
        "exit_code": status_word.split()[1] if len(status_word.split()) > 1 else status_word,
        "status_file_word": f"{status_word}  ({args.status.name})",
    }
    for key in LOOSE_KEYS:
        if key not in loose:
            continue
        seen = observed.get(key, "(not readable from here)")
        print(f"  ..   {key:<20} predicted {loose[key]}")
        print(f"       {'':<20} observed  {seen}")
    if str(observed["exit_code"]) != str(loose.get("exit_code")):
        print(
            f"  DIFFERS: the CLI's exit code was predicted {loose.get('exit_code')} and the status "
            f"file holds {observed['exit_code']}. It is not a wrong prediction about the fit — "
            "`make` exits 2 for ANY failed recipe, so the retrain's 0/1/2/3/4 vocabulary does not "
            "survive being detached as a make TARGET. docs/retrain_m7.md §4, gotcha #97."
        )

    print()
    if failures:
        print(f"MISMATCH — {len(failures)} field(s) disagree with the prediction:")
        for f in failures:
            print(f"  - {f}")
        print("Do NOT edit the prediction. The discrepancy is the result.")
        return 1
    print(
        f"REPRODUCED — all {len(EXACT_RESOLVERS) + 1} exact claims and "
        f"{len(must)} path properties hold."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
