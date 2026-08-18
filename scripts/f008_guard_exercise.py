"""Exercise M3-S1's F-008 guard on a real sampled run — M3-S4's required paste.

The M3 kickoff asks this story to exercise the guard once and paste it, and the
reason is specific to this milestone: **the automation track samples by design.**
The scout runs on 5% of train, every sniper trial runs on 15%, and F-008 measured
what that does to a verdict — the gate's floor is fitted on the same rows as the
challenger, so shrinking train degrades the BAR faster than it degrades the
model. On one train month the margin went 7.07% -> 16.85% *without the model
getting better*. A sampled run does not merely produce a weaker number; it
produces a FLATTERING one.

M3-S1 closed that by refusing to issue a verdict at all: `--train-months` is
gate-disqualifying and exits **2**, and `--no-gate` (the sample-first smoke path)
exits **3**. Two distinct codes, because "no verdict was possible" and "no
verdict was asked for" must never be confused by a pipeline.

This script runs both, from the same place, and reports the exit codes. It
promotes nothing, fits nothing (both paths refuse before a row is read), and
takes seconds. It is a .py rather than a shell one-liner for gotcha #37's
reason: the OpenMP shim re-execs, and stdin cannot be replayed.
"""

from __future__ import annotations

import subprocess
import sys

from taxi_mlops.data.config import repo_root

CASES = (
    (
        ["--train-months", "2019-01", "--no-promote"],
        2,
        "a sampled train set is GATE-DISQUALIFYING: no verdict is possible",
    ),
    (
        ["--train-months", "2019-01", "--no-gate"],
        3,
        "the sample-first smoke path: a table, and NO verdict issued",
    ),
)


def main() -> int:
    failures = 0
    for extra, expected, claim in CASES:
        argv = [sys.executable, "-m", "taxi_mlops.training", "train", *extra]
        print("=" * 78)
        print(f"[f-008] {' '.join(argv[1:])}")
        print(f"[f-008] expecting exit {expected} — {claim}")
        print("=" * 78)
        done = subprocess.run(argv, cwd=repo_root(), check=False)
        ok = done.returncode == expected
        failures += not ok
        print(f"[f-008] {'ok  ' if ok else 'FAIL'} exit {done.returncode} (expected {expected})\n")
    print(f"[f-008] {'PASS' if not failures else 'FAIL'} — {len(CASES) - failures}/{len(CASES)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
