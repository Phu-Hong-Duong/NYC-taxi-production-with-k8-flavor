"""The shared helpers' semantics, pinned — because a name is not a guarantee.

CU-S2 consolidated this suite's copied helpers into `tests/conftest.py`. The
cleanup that motivated it found the opposite of a saving: `_calls()` defined
seven times with THREE different meanings under one name, so two tests that read
identically asserted different things. Splitting them is only half the fix. The
other half is here: if a later session quietly re-unifies the three, or "tidies"
`referenced_names` onto an `ast.Call` guard, these tests go red naming the
property that was lost.

Every assertion below is about a DIFFERENCE between helpers. A test that only
checked each one in isolation would pass for a file where all three had been
collapsed into the same function.
"""

from __future__ import annotations

import pytest
from conftest import (
    REPO,
    called_names,
    called_paths,
    imported_roots,
    invokes,
    phony_targets,
    read_record,
    referenced_names,
    without_comments,
)

# One fixture that every semantics below reads differently. `banned_verb` is
# REFERENCED and never called; `client.promote` is called through a dotted path.
SAMPLE = '''
import json
import os.path
from taxi_mlops.training import registry

handler = registry.banned_verb          # referenced, NEVER called
client.promote(version=2)               # dotted call
plain()                                 # bare call
'''


@pytest.fixture
def sample(tmp_path):
    path = tmp_path / "sample.py"
    path.write_text(SAMPLE)
    return path


def test_referenced_names_is_strictly_broader_than_called_names(sample) -> None:
    """The whole reason test_tuning keeps the broad form.

    Its guard forbids the registry API from appearing at all, so a name that is
    assigned, aliased or passed on without being invoked is already the
    violation. Collapsing it onto the call-guarded helper would weaken a live
    guard inside a diff that reads as pure deduplication (gotcha #50).
    """
    assert "banned_verb" in referenced_names(sample)
    assert "banned_verb" not in called_names(sample), (
        "called_names has stopped being Call-guarded — it now reports a name "
        "that is only referenced, which makes it a synonym for referenced_names"
    )
    assert called_names(sample) < referenced_names(sample)


def test_called_paths_keeps_the_receiver_that_called_names_discards(sample) -> None:
    """`a.promote()` and `b.promote()` are one name and two paths."""
    assert "client.promote" in called_paths(sample)
    assert "promote" in called_names(sample)
    assert "client.promote" not in called_names(sample), (
        "called_names is reporting dotted paths — the two helpers have merged"
    )


def test_called_paths_is_a_list_so_callers_can_count() -> None:
    assert isinstance(called_paths(REPO / "tests" / "conftest.py"), list)
    assert isinstance(called_names(REPO / "tests" / "conftest.py"), set)


def test_without_comments_drops_comment_lines_and_keeps_blank_ones() -> None:
    """Blank lines are load-bearing for callers that assert on line structure."""
    text = "alpha\n\n# a comment naming forbidden_verb\n    # indented too\nomega\n"
    stripped = without_comments(text)
    assert "forbidden_verb" not in stripped
    assert "indented too" not in stripped
    assert stripped.splitlines() == ["alpha", "", "omega"]


def test_without_comments_reads_a_path_or_text_alike(tmp_path) -> None:
    path = tmp_path / "f.sh"
    path.write_text("# comment\nreal\n")
    assert without_comments(path) == without_comments(path.read_text())


def test_without_comments_keeps_trailing_comments_deliberately() -> None:
    """Stripping them needs a quoting-aware parser; a half-parser is gotcha #35."""
    assert without_comments("run --flag  # why") == "run --flag  # why"


def test_invokes_separates_running_a_command_from_naming_one() -> None:
    """The house rule, and both halves matter."""
    assert invokes("make pipeline", "make pipeline")
    assert invokes("foo && make pipeline", "make pipeline")
    assert not invokes("advice: run `make pipeline` after this", "make pipeline")
    assert not invokes("kubectl -n flyte get deploy", "flyte get")


def test_phony_targets_sees_a_continued_declaration() -> None:
    """F-083: the audit's parser could not, and reported five gaps that were not."""
    makefile = ".PHONY: alpha beta \\\n\tgamma delta\n\nalpha:\n\techo hi\n"
    assert phony_targets(makefile) == {"alpha", "beta", "gamma", "delta"}


def test_phony_targets_reads_the_real_makefile_and_agrees_with_its_targets() -> None:
    """A helper nobody points at the real artifact is a helper nobody has tested."""
    declared = phony_targets((REPO / "Makefile").read_text())
    assert "verify-m9" in declared and "readme-check" in declared


def test_record_refuses_a_missing_record_and_names_what_writes_it(tmp_path) -> None:
    """F-054: an absent tracked record is a deletion, never a reason to skip."""
    with pytest.raises(AssertionError) as excinfo:
        read_record(
            REPO / "automation" / "runs" / "does-not-exist.json", produced_by="make thing"
        )
    assert "TRACKED record" in str(excinfo.value)
    assert "make thing" in str(excinfo.value), (
        "the failure message must name the command that writes the record — "
        "'this file is gone' leaves the reader asking 'put there by what?'"
    )


def test_imported_roots_reads_the_ast_and_not_the_text(sample) -> None:
    assert imported_roots(sample) == {"json", "os", "taxi_mlops"}
