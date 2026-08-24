"""F-047: the `needs_records` marker — what it means, and what stops it decaying.

`make image-smoke` had been RED since M5-S5 and nobody noticed, because nothing
runs it. Every failure was one shape: a test that reads a tracked record under
`automation/runs/`, which `.dockerignore` correctly keeps out of the task image —
those records are host evidence, and an artifact that carried them would be
carrying evidence it can never be the source of truth for (the same reason F-048's
option (b) was refused).

The decided fix (ARCH, M7 boundary, option (a)) is a MARKER, deselected for the
in-image run only. A marker like that is one bad afternoon away from being the
skip flag M1 refused, so these tests hold three properties: it covers every test
that really reads a record, it is honoured in exactly one place, and it is not
carried by tests that do not need it.

The check is an AST walk and deliberately not a grep. Several tests legitimately
MENTION a record path while asserting it appears in a script's body; a needle
matching words would flag those, and the fix a tired reader reaches for is to
widen the check until it stops meaning anything (gotchas #53/#68/#99). What is
flagged is a reading call whose RECEIVER is a record path — and the receiver's
source is NORMALISED before it is matched, because a path is spelled two ways in
this suite (`REPO / "automation/runs/x.json"` and `REPO / "automation" / "runs"`)
and the first version of this check saw only one of them (gotcha #46's family,
found by running it).

**The second, older answer is GONE — F-054, closed at M9-S3.** Twelve tests
across `test_canary_and_rollback.py` and `test_shadow_and_spike.py` used to guard
their record reads with `skipif(not RECORD.exists())`, which also makes the
in-image run green — by skipping. That is the weaker shape: on the HOST an absent
record means a drill was never run, and a silent skip is how a check stops being
one (F-029 converted exactly such a skip into an assertion at M5-S1, and the
deciding fact here is the same one — those records are git-tracked, so a fresh
clone HAS them and the assertion can only catch a deleted or lost record). This
module used to ACCEPT that form and argue against it; it now REFUSES it, and the
refusal is derived from the AST across every test file rather than enumerated
against the two that happened to carry it.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SMOKE = REPO / "scripts" / "image_smoke.sh"
PYPROJECT = REPO / "pyproject.toml"
TEST_FILES = sorted((REPO / "tests" / "unit").glob("test_*.py"))
READING_CALLS = {"read_text", "read_bytes", "open", "glob", "iterdir", "exists", "stat"}
DESELECT = "not needs_records"


def _names_a_record(segment: str | None) -> bool:
    """Does this source segment name a path under automation/runs/, however spelled?

    `REPO / "automation/runs/m5-load/headline.json"` and
    `REPO / "automation" / "runs" / "m6-gameday"` are the same path and the second
    is invisible to a substring match — which is what the first draft of this
    check missed, and it missed it on four real tests.
    """
    if not segment:
        return False
    return "automationruns" in re.sub(r"[\"'\s/]+", "", segment)


def _tests(tree: ast.Module) -> list[ast.FunctionDef]:
    return [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]


def _record_constants(source: str, tree: ast.Module) -> set[str]:
    """Module-level names bound to a path under automation/runs/."""
    return {
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
        and _names_a_record(ast.get_source_segment(source, node.value))
    }


def _mentions_a_record(segment: str, record_names: set[str]) -> bool:
    return _names_a_record(segment) or any(
        re.search(rf"\b{name}\b", segment) for name in record_names
    )


def _record_reading_tests(path: Path) -> set[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    record_names = _record_constants(source, tree)

    def reads_a_record(func: ast.AST) -> bool:
        for node in ast.walk(func):
            if not isinstance(node, ast.Call):
                continue
            reader = isinstance(node.func, ast.Attribute) and node.func.attr in READING_CALLS
            if reader and _mentions_a_record(
                ast.get_source_segment(source, node.func.value) or "", record_names
            ):
                return True
            # A record CONSTANT handed to something else is a record dependency
            # too: `_run(RECORD)` shells out and reads it. Restricted to the names
            # bound to record paths rather than to any mention, because a string
            # literal in an argument is usually an assertion ABOUT a path and not a
            # read of one (`str(DEFAULT_RECORD).startswith("automation/runs/")`),
            # and a check that flags those teaches the next reader to widen it
            # until it means nothing. The honest residual: a literal record path
            # passed to a function that reads it is invisible here — `make
            # image-smoke` is the empirical backstop, and it is what caught the two
            # this static check could not.
            for argument in [*node.args, *(kw.value for kw in node.keywords)]:
                if isinstance(argument, ast.Name) and argument.id in record_names:
                    return True
        return False

    return {node.name for node in _tests(tree) if reads_a_record(node)}


def _skip_guarded(path: Path) -> set[str]:
    """Tests whose record read is guarded by a `skipif` on that record's existence.

    The older answer to the same problem. It used to be subtracted from the
    coverage check — i.e. accepted — and is now what `test_no_record_read_is_
    guarded_by_a_skip` refuses (F-054). Decorators only: this suite discusses the
    old form in prose, and a needle matching words would match the argument
    against it (gotcha #99).
    """
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    record_names = _record_constants(source, tree)
    return {
        node.name
        for node in _tests(tree)
        for decorator in node.decorator_list
        if "skipif" in (segment := ast.get_source_segment(source, decorator) or "")
        and _mentions_a_record(segment, record_names)
    }


def _marked(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in _tests(tree)
        for decorator in node.decorator_list
        if "needs_records" in ast.dump(decorator)
    }


def test_every_test_that_reads_a_tracked_record_carries_the_marker() -> None:
    """Prevents F-047 recurring — and prevents it recurring UNSEEN.

    The expensive half of that finding was not the red run: it was that
    `image-smoke` sits on no gate's path, so its red went unread for a milestone
    and a half. This is a unit test, and CI runs it on every PR.
    """
    unmarked = {
        path.name: sorted(missing)
        for path in TEST_FILES
        if (missing := _record_reading_tests(path) - _marked(path))
    }
    assert not unmarked, (
        "these tests read a tracked record under automation/runs/ but carry no "
        "@pytest.mark.needs_records, so they will fail inside the task image where "
        f"those records correctly do not exist: {unmarked}"
    )


def test_no_record_read_is_guarded_by_a_skip() -> None:
    """F-054: the marker names WHERE a test runs; it may not decide whether it passes.

    `skipif(not RECORD.exists())` and `@pytest.mark.needs_records` both make the
    in-image run green, and they are not the same answer. On the host an absent
    record means the drill was never run, and the skip form reports that as a
    pass. The records are tracked (F-029 option A), so the assertion form costs a
    fresh clone nothing and catches exactly one new thing: a deleted record.

    Derived across every test file rather than enumerated against the two that
    carried the old form — a check listing its own known offenders goes green the
    day a third file grows one.
    """
    guarded = {path.name: sorted(found) for path in TEST_FILES if (found := _skip_guarded(path))}
    assert not guarded, (
        "these tests skip when their record is missing instead of failing, which on the "
        f"host is a drill that was never run reported as a pass (F-054): {guarded}"
    )


def test_the_marker_is_honoured_in_exactly_one_place_and_is_not_a_skip_flag() -> None:
    """The line between "this test is about the host" and "this failure is optional"."""
    assert DESELECT in SMOKE.read_text(), "the in-image run must deselect the marker"
    pyproject = PYPROJECT.read_text()
    assert "needs_records:" in pyproject, "an unregistered marker is a typo waiting to happen"
    addopts = re.search(r"^addopts\s*=\s*(.+)$", pyproject, re.M)
    assert addopts and DESELECT not in addopts.group(1), (
        "deselecting needs_records by default would hide these tests from every host run "
        "and from CI — the marker names WHERE a test can run, never whether it must pass"
    )
    offenders = sorted(
        path.name for path in REPO.glob("scripts/*.sh")
        if DESELECT in path.read_text(encoding="utf-8") and path.name != SMOKE.name
    )
    assert not offenders, f"{offenders} also deselect the marker; exactly one place may"


def test_no_test_is_marked_that_does_not_need_it() -> None:
    """A marker on a test that does not need records is a test the image silently drops.

    One family is exempt by name rather than by silence: the `..._tracked_by_git`
    tests ask `git ls-files` about those same records, and the image carries no
    `.git` either — host-only for the same reason through a different mechanism.
    """
    for path in TEST_FILES:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        reading = _record_reading_tests(path)
        record_names = _record_constants(source, tree)
        by_name = {node.name: node for node in _tests(tree)}
        for name in sorted(_marked(path)):
            if name in reading or name.endswith("tracked_by_git"):
                continue
            body = ast.get_source_segment(source, by_name[name]) or ""
            assert _mentions_a_record(body, record_names), (
                f"{path.name}::{name} is marked needs_records but neither reads a record "
                "nor asks git about one"
            )


def test_the_in_image_run_is_still_the_whole_suite_otherwise() -> None:
    """`SKIP_UNIT=1` stays a FAILURE, and the deselect must not have widened it.

    M4-S3 made skipping the in-image suite count as a failed check rather than a
    pass. F-047's fix narrows what that suite contains by one marker; it must not
    have loosened anything else on the way past.
    """
    body = SMOKE.read_text()
    assert "SKIP_UNIT=1 is a debugging lever, never a pass" in body
    invocation = next(line for line in body.splitlines() if "pytest tests/unit" in line)
    assert "-m 'not needs_records'" in invocation, invocation
    assert "--ignore" not in invocation and "-k " not in invocation, (
        "the in-image run may deselect the record marker and nothing else"
    )
