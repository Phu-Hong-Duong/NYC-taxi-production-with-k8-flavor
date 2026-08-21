"""What a detached job's `.status` file can and cannot mean (gotcha #97).

M7-S4 gave the retrain a vocabulary of exit codes — 0 passed · 1 refused · 2
could not build · 3 no verdict · 4 crashed — and the previous leg added the 4
precisely so an unhandled crash could not wear a verdict's clothes. Then the
re-run was detached as `make retrain`, refused correctly (CLI exit 1), and its
status file read `FAILED 2`, which in that vocabulary means *the challenger
could not be built* about a challenger that had been built, fitted for 27
minutes and judged.

The cause is not in this repository: **GNU make exits 2 for any failed
recipe.** The vocabulary collapses to {0, 2} at the make boundary, and 2 is a
word already in use.

These tests pin the two halves of what was done about it:
  1. the collapse itself, MEASURED against a throwaway makefile rather than
     asserted from documentation (gotcha #70's family — ask the tool);
  2. the mitigations that do not create a twin — the recipe echoes the CLI's
     own code into the log, and the header says the record, not the status
     word, is the authority.

Deliberately NOT pinned: a `CMD=` escape hatch on `make detach`. Retyping a
recipe at the launch site to preserve an exit code would put the command in
two places, and this program's rule about twins outranks the convenience.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MAKEFILE = (REPO / "Makefile").read_text(encoding="utf-8")


def _recipe(target: str) -> str:
    """The recipe body of a target — its tab-indented lines only."""
    lines = MAKEFILE.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(f"{target}:"):
            body: list[str] = []
            for nxt in lines[i + 1 :]:
                if nxt.startswith("\t"):
                    body.append(nxt)
                elif nxt.strip() == "":
                    continue
                else:
                    break
            return "\n".join(body)
    raise AssertionError(f"no target {target!r} in the Makefile")


@pytest.mark.skipif(
    shutil.which("make") is None,
    # Found by M8-S1 leg 2, and it is F-047's shape a second time: this test has
    # been RED inside the task image since the day it landed, because the image
    # ships no `make` — and nothing runs `make image-smoke`, so nobody saw it. The
    # answer is the idiom this suite already uses for `ss`, `git` and `docker`: a
    # missing TOOL is a different fact from a failing assertion, and it is not the
    # record marker either, because what is absent here is a binary rather than
    # evidence.
    reason="GNU make is not installed here (it is not in the task image)",
)
def test_make_collapses_every_failing_recipe_to_exit_2(tmp_path: Path) -> None:
    """The measurement the whole gotcha rests on.

    Written as an executed probe and not as a comment, because the claim is
    about a tool's behaviour on THIS machine and a remembered number is a
    number nobody re-checked.
    """
    (tmp_path / "Makefile").write_text("one:\n\t@exit 1\nthree:\n\t@exit 3\nzero:\n\t@exit 0\n")

    codes = {}
    for target in ("zero", "one", "three"):
        proc = subprocess.run(  # noqa: S603 — fixed argv, no shell
            ["make", "-s", "-C", str(tmp_path), target],
            capture_output=True,
            text=True,
            check=False,
        )
        codes[target] = proc.returncode

    assert codes["zero"] == 0, "a successful recipe must still come back 0"
    assert codes["one"] == 2, "a recipe exiting 1 is reported by make as 2"
    assert codes["three"] == 2, "a recipe exiting 3 is ALSO reported as 2 — the vocabulary is gone"


def test_the_retrain_recipe_echoes_the_clis_own_exit_code() -> None:
    """The log keeps what the status file cannot.

    The recipe runs the CLI, captures `$?`, prints it with the vocabulary
    beside it, and re-exits with it. Re-exiting matters as much as the echo:
    a recipe that swallowed the code to make the line printable would turn
    every refusal into a green make.
    """
    body = _recipe("retrain")
    assert "rc=$$?" in body, "the recipe must capture the CLI's own exit code"
    assert "CLI exit code" in body, "and print it, because make's own code cannot carry it"
    assert "exit $$rc" in body, "and re-exit with it — a swallowed code is a false green"
    assert "gotcha #97" in body, "with a pointer to why, where the operator reads it"


def test_the_detach_header_says_the_record_is_the_authority() -> None:
    """A .status word is triage; the record the run exists to produce is proof.

    This is gotcha #59 in the place it was learned the third time: assert
    positively on the artifact, and read a MISSING record as the crash signal
    rather than trying to decode a collapsed number.
    """
    header = MAKEFILE.split(".PHONY: detach")[0]
    assert "gotcha #97" in header
    assert re.search(r"exits 2 for ANY failed\s+# recipe", header), (
        "the header must state the collapse, not just point at it"
    )
    assert "read the RECORD" in header
    assert "ABSENCE" in header, "the discriminator that survives the collapse must be named"


def test_the_retrain_help_text_does_not_promise_what_make_cannot_deliver() -> None:
    """The help line used to advertise `exit 0/1/3` with no caveat.

    A target's ## text is read by `make help`, i.e. by exactly the operator
    who is about to detach it. Naming the codes without naming the collapse
    is how the last three sessions each re-learned this.
    """
    line = next(ln for ln in MAKEFILE.splitlines() if ln.startswith("retrain: ##"))
    assert "CLI exit" in line, "the codes must be attributed to the CLI, not to make"
    assert "collapses" in line, "and the collapse must be named on the same line"
