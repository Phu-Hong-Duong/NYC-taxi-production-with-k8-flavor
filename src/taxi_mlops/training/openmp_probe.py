"""`python -m taxi_mlops.training.openmp_probe` — ask which OpenMP this process got.

Added at M4-S3 for a specific reason, and it is F-024's other half. The obvious
way to probe is `python -c "from …openmp import ensure_openmp; ensure_openmp()"`
— and that is the ONE invocation form the shim cannot serve: CPython does not
preserve the `-c` source string, so a re-exec cannot rebuild its own command line
(the shim now refuses that form outright instead of exec'ing a broken argv).

A module run with `-m` is the form `_relaunch_argv()` was written for and the form
every real entry point in this program uses (`python -m taxi_mlops.training …`),
so this file is the probe that takes the SAME path a task takes. That matters for
what it is used for: `scripts/image_smoke.sh` asserts this prints exactly
`openmp: system libgomp.so.1` inside the task image and nothing else — no
`[openmp]` announcement — which is the evidence debt D-004 asks for, and
`scripts/image_smoke_redteam.sh` masks the system library and asserts the
announcement appears. A probe that could not fire the shim would make the first
assertion untestable.

Exit: 0 an OpenMP runtime is in hand · 1 none could be found or borrowed.
"""

from __future__ import annotations

import sys

from taxi_mlops.training.openmp import OpenMPUnavailableError, ensure_openmp


def main() -> int:
    try:
        print(ensure_openmp())
    except OpenMPUnavailableError as error:
        print(f"openmp: UNAVAILABLE — {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
