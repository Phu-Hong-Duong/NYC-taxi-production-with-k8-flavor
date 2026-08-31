"""The front door's laws — M9-S8.

`README.md` is the first artifact a public reader meets and the only one nobody
runs, which makes it the easiest thing in this repo to let drift: no gate fails
when a quickstart command is renamed out from under it, and a number that was true
in August reads exactly like one that still is.

`scripts/readme_check.py` is the twin that re-derives it — the
`error_memo_numbers.py` / `drift_memo_numbers.py` idiom, one audience out. These
tests are about the CHECKER, because a checker that can be quietly narrowed is a
front door with no check at all:

1. **It actually runs, and it is GREEN right now** — invoked as a subprocess, the
   way `make readme-check` invokes it.
2. **Every claim carries a non-digit anchor**, so the presence half cannot be
   satisfied by a substring of some other number (gotcha #76).
3. **Every claim's record exists**, and is a tracked file or a named command — a
   claim pointing at a record a fresh clone does not have is unverifiable there.
4. **The CLI's default includes the test-count leg.** The tests call the checker
   with `--no-collect` to avoid nesting pytest inside pytest; that escape hatch
   must not become the default, or the number goes unchecked everywhere.
5. **The Status table's rows are named**, so a rewrite of the front door that
   drops the ledger it grew from is a RED test and not a diff nobody reads.
"""

from __future__ import annotations

import ast
import importlib.util
import re
import subprocess
import sys

import pytest
from conftest import REPO

CHECKER = REPO / "scripts" / "readme_check.py"
README = REPO / "README.md"

#: The tree the README's evidence table points into. Named here, and asserted in
#: the tests that need it, because the dependency is otherwise invisible: those
#: tests reach the records through a SUBPROCESS, and F-047's static guard reads
#: this file — not the checker's claim table — to decide what carries the marker.
#: Without this constant the marker would be correct and unexplained; with it the
#: guard agrees, and the honest residual that finding already names (a record read
#: behind an indirection) does not grow by one more instance.
RECORDS = REPO / "automation" / "runs"


def _module():
    spec = importlib.util.spec_from_file_location("readme_check", CHECKER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Registered BEFORE execution: `Claim` is a dataclass in a module using
    # postponed annotations, and dataclasses resolves those through
    # `sys.modules[cls.__module__]` — absent, the class body raises.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def checker():
    return _module()


@pytest.mark.needs_records
def test_the_checker_is_green_against_the_committed_readme():
    """The claim this whole story rests on, asserted rather than trusted.

    `--no-collect` skips exactly one leg — the one that shells out to pytest —
    because this test IS a pytest process. `make readme-check` runs it whole, and
    `test_the_cli_default_still_collects` keeps that true.
    """
    assert RECORDS.exists(), "the README's evidence table points into automation/runs/"
    proc = subprocess.run(
        [sys.executable, str(CHECKER), "--no-collect"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        "README.md makes a claim the repository does not support:\n" + proc.stdout[-3000:]
    )
    assert "GREEN" in proc.stdout


def test_every_claim_carries_an_anchor(checker):
    """A bare number matches almost any document, so it is not a check.

    `10` is inside `104.226`; `55` is inside `557,688`. The rendered form has to
    carry its unit, its noun or its markdown delimiters, and the checker refuses
    one that does not — this test asserts the refusal covers the shipped table.
    """
    bare = [
        claim.rendered
        for claim in (*checker.CLAIMS, *checker.COMMAND_CLAIMS, checker.TEST_COUNT_CLAIM)
        if not re.search(r"[^\d.,]", claim.rendered)
    ]
    assert not bare, f"these claims are bare numbers with nothing to anchor them: {bare}"


@pytest.mark.needs_records
def test_every_claim_names_a_record_that_exists(checker):
    """A claim whose record is missing is a claim nobody can re-derive.

    A record is either a path in this repo or a command a reader can run; the
    second form is spelled with a space, which is how the two are told apart.
    """
    assert RECORDS.is_dir(), "the README's evidence table points into automation/runs/"
    missing = []
    for claim in (*checker.CLAIMS, *checker.COMMAND_CLAIMS, checker.TEST_COUNT_CLAIM):
        record = claim.record
        if " " in record:  # a command, e.g. `uv run pytest tests/unit -q`
            continue
        if not (REPO / record).exists():
            missing.append(record)
    assert not missing, f"claims point at records this repo does not hold: {missing}"


@pytest.mark.needs_records
def test_every_claimed_record_is_tracked_by_git(checker):
    """F-029's rule, one artifact along: what a reader is told to check must be
    visible to review. An untracked record makes the front door's evidence
    unavailable to anyone who did not run the drill on this machine."""
    paths = sorted(
        {
            claim.record
            for claim in (*checker.CLAIMS, *checker.COMMAND_CLAIMS)
            if " " not in claim.record
        }
    )
    proc = subprocess.run(
        ["git", "ls-files", "--error-unmatch", *paths],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        "the README cites records git does not track:\n" + proc.stderr[-1500:]
    )


def test_the_cli_default_still_collects():
    """`--no-collect` is an escape hatch for nesting, not a default.

    Asked of the AST: the flag must be opt-in (`store_true`), and the leg must be
    guarded by *not* having asked for it. A default that skipped would leave the
    test-count claim unchecked in every run, including `make readme-check`.
    """
    tree = ast.parse(CHECKER.read_text())
    actions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "attr", "") == "add_argument"
        and any(
            isinstance(arg, ast.Constant) and arg.value == "--no-collect" for arg in node.args
        )
    ]
    assert len(actions) == 1, "the --no-collect flag is declared somewhere else now"
    action = {kw.arg: kw.value for kw in actions[0].keywords}["action"]
    assert isinstance(action, ast.Constant) and action.value == "store_true", (
        "--no-collect must be opt-in; a store_false or a default of True skips the "
        "test-count leg for every caller"
    )
    source = CHECKER.read_text()
    assert "if not args.no_collect:" in source, (
        "the test-count leg is no longer guarded by the absence of --no-collect"
    )


def test_the_status_table_keeps_every_row(checker):
    """Append-only history: the front door gains an audience, it does not lose
    its ledger. Ten milestone rows plus the four close rows (program, epilogue,
    publish, and the followability cleanup — each row joined the pin at its own
    close; the cleanup's on 2026-08-31)."""
    text = README.read_text()
    assert len(checker.STATUS_ROWS) == 14
    missing = [row for row in checker.STATUS_ROWS if row not in text]
    assert not missing, f"the Status table has lost rows: {missing}"


def test_the_checker_reads_and_does_not_write(checker):
    """It is a READER — M5-S4's load-drill precedent. It may not deploy, promote,
    materialize or write a record, and the one subprocess it launches is pytest's
    collector. Asked of the AST, because this module argues about `write` and
    `deploy` in prose (gotcha #53/#99)."""
    tree = ast.parse(CHECKER.read_text())
    launched = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "attr", "") == "run"
        and getattr(getattr(node.func, "value", None), "id", "") == "subprocess"
    ]
    assert len(launched) == 1, "the checker launches something new; it is meant to READ"
    argv = launched[0].args[0]
    assert isinstance(argv, ast.List)
    words = [element.value for element in argv.elts if isinstance(element, ast.Constant)]
    assert words[:3] == ["uv", "run", "pytest"], f"unexpected subprocess: {words}"
    forbidden = ("write_text", "mkdir", "unlink", "kubectl", "helm", "docker")
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in forbidden:
            raise AssertionError(f"the checker calls {node.attr}; it is a reader")
