"""The reader that judges the retrain record against its prior prediction.

A repeat of a 27-minute fit is evidence only if what it had to produce was
written down first. `scripts/retrain_prediction_check.py` is what turns "it
reproduced exactly" from a sentence into a command, so these tests ask the
two questions that matter about any such checker: can it fail, and does it
fail for the right reason?

The tamper is deliberately PLAUSIBLE — one metric moved in its last kept
digit, the shape of the record untouched — because a drill that plants `999`
goes green everywhere and teaches nobody anything (gotcha #90).
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts/retrain_prediction_check.py"
PREDICTION = REPO / "automation/runs/m7-retrain/rerun-prediction.json"
RECORD = REPO / "automation/runs/m7-retrain/latest.json"
SOURCE = SCRIPT.read_text(encoding="utf-8")


def _run(record: Path, prediction: Path = PREDICTION) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — fixed argv, no shell
        [
            sys.executable,
            str(SCRIPT),
            "--prediction",
            str(prediction),
            "--record",
            str(record),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO,
    )


def test_the_committed_record_reproduces_the_committed_prediction() -> None:
    """The story's claim, as a test rather than as prose.

    If this ever goes red without either file being edited, the finding is
    about determinism and not about the checker.
    """
    proc = _run(RECORD)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "REPRODUCED" in proc.stdout
    assert "MISMATCH" not in proc.stdout


def test_it_goes_red_on_a_plausible_one_digit_tamper(tmp_path: Path) -> None:
    """A challenger MAE moved by 0.0001 — inside the precision the prediction
    was written at, and invisible to a reader skimming the file."""
    record = json.loads(RECORD.read_text())
    record["verdict"]["challenger_mae"] = record["verdict"]["challenger_mae"] + 0.0001
    target = tmp_path / "tampered.json"
    target.write_text(json.dumps(record))

    proc = _run(target)
    assert proc.returncode == 1
    assert "MISMATCH" in proc.stdout
    assert "challenger_mae_test" in proc.stdout


def test_it_goes_red_when_the_verdict_itself_is_rewritten(tmp_path: Path) -> None:
    """The most consequential single-field lie the record can tell: a REFUSE
    relabelled as a PROMOTE, with every number left alone."""
    record = json.loads(RECORD.read_text())
    record["verdict"]["verdict"] = "PROMOTE"
    target = tmp_path / "tampered.json"
    target.write_text(json.dumps(record))

    proc = _run(target)
    assert proc.returncode == 1
    assert "MISMATCH" in proc.stdout


def test_it_goes_red_when_the_failing_checks_stop_being_the_incumbent_ones(
    tmp_path: Path,
) -> None:
    """`which_checks_fail` is prose in the prediction and structure here.

    A record whose FLOOR condition failed while its numbers were left intact
    would describe a different event entirely, and a substring check on the
    prediction's wording would not notice.
    """
    record = json.loads(RECORD.read_text())
    for reason in record["verdict"]["reasons"]:
        reason["passed"] = "champion" in reason["check"]
    target = tmp_path / "tampered.json"
    target.write_text(json.dumps(record))

    proc = _run(target)
    assert proc.returncode == 1
    assert "which_checks_fail" in proc.stdout


def test_a_loose_field_that_differs_never_fails_the_check() -> None:
    """The exit code was predicted 1 and observed 2, and the check must say so
    while still returning 0 — the difference is gotcha #97, not a bad fit."""
    proc = _run(RECORD)
    assert proc.returncode == 0
    assert "DIFFERS" in proc.stdout, "a loose field that did not hold must be printed, not dropped"
    assert "gotcha #97" in proc.stdout


def test_the_precision_floor_exists_and_is_at_least_one_decimal() -> None:
    """gotcha #90: comparing at zero decimals is not comparing.

    Read off the module's own constant rather than off its prose, so the
    argument in the docstring cannot satisfy the test (gotchas #53/#68).
    """
    tree = ast.parse(SOURCE)
    floors = [
        node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(getattr(t, "id", "") == "MIN_DECIMALS" for t in node.targets)
        and isinstance(node.value, ast.Constant)
    ]
    assert floors == [1] or (floors and floors[0] >= 1), "MIN_DECIMALS must exist and be >= 1"


def test_it_is_a_reader() -> None:
    """No writes, no registry, no fit. It reads two files and judges them.

    Asked of the AST, because the module argues its own design at length and
    a grep for `open` would match the argument (gotchas #53/#68).
    """
    tree = ast.parse(SOURCE)
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    for forbidden in ("write_text", "mkdir", "unlink", "set_registered_model_alias", "log_model"):
        assert forbidden not in called, f"{forbidden} has no business in a checker"
    assert "read_text" in called
