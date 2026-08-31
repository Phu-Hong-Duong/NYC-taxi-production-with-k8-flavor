"""The two shell libraries the gates and the red-team drills share (CU-S3).

Eight gates carried a byte-identical counting harness and eight record-editing
drills carried a byte-identical snapshot/restore scaffold. Consolidating them
moved two properties out of sixteen files and into two, so the guards that used
to pin the per-file copies are RE-DERIVED here — to the lib-level property,
never widened away (gotcha #50). The per-file tests still assert that each gate
and each drill USES the lib; this file asserts what the lib does.

Most of what follows RUNS the library rather than reading it. The old pins were
text (`"trap restore EXIT" in body`), which is what a check looks like when the
implementation is in the file under test. With one implementation there is no
reason to settle for that: a drill that traps and restores can be watched doing
it, including on the path that matters — an abnormal exit.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest
from conftest import REPO, without_comments

HARNESS = REPO / "scripts" / "lib" / "verify_harness.sh"
RESTORE = REPO / "scripts" / "lib" / "redteam_restore.sh"

GATES = [REPO / "scripts" / f"verify_m{n}.sh" for n in range(2, 10)]
DRILLS = [REPO / "scripts" / f"verify_m{n}_redteam.sh" for n in range(3, 10)] + [
    REPO / "scripts" / "gate_margin_redteam.sh"
]


def _bash(script: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", script], cwd=cwd, capture_output=True, text=True, timeout=60
    )


# --------------------------------------------------------------------------
# The libraries exist, parse, and are sourced rather than executed.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("lib", [HARNESS, RESTORE], ids=lambda p: p.name)
def test_the_library_parses(lib: Path) -> None:
    """`bash -n` is the cheapest possible guard and it covers the failure a
    sourced file has that a standalone script does not: a syntax error here
    takes sixteen callers down at once."""
    assert lib.exists(), f"{lib.name} is missing — sixteen scripts source it"
    assert _bash(f"bash -n {lib}", REPO).returncode == 0, f"{lib.name} does not parse"


@pytest.mark.parametrize("lib", [HARNESS, RESTORE], ids=lambda p: p.name)
def test_the_library_says_what_deliberately_does_not_live_in_it(lib: Path) -> None:
    """A shared file's real risk is the next consolidation, not this one. Both
    headers name what must stay per-caller — the gates' legs and verdict blocks,
    the drills' plants and assertions — so a future session moving one of those
    in has to delete the sentence saying not to."""
    header = lib.read_text().split("\n\n")[0] + lib.read_text()
    assert "DELIBERATELY DOES NOT LIVE HERE" in header


def test_the_libraries_reach_the_task_image() -> None:
    """CU-S3 created this repo's first scripts→scripts source edge, and a sourced
    file that does not travel is a caller that dies at run time rather than at
    build time. `.dockerignore`'s rule is "the image contains what git contains"
    and it names no path under `scripts/`; the F-026 guard already treats
    `scripts/` as an image input, so an edit here refuses a stale image."""
    excluded = [
        line for line in (REPO / ".dockerignore").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#") and "scripts" in line
    ]
    assert not excluded, f".dockerignore excludes something under scripts/: {excluded}"
    for guarded in (REPO / "scripts" / "run_pipeline.sh", REPO / "scripts" / "retrain_schedule.sh"):
        assert "docker scripts" in guarded.read_text(), (
            f"{guarded.name}'s F-026 IMAGE_PATHS no longer covers scripts/ — an edit "
            "to a sourced lib would not refuse a stale image"
        )


# --------------------------------------------------------------------------
# verify_harness.sh — the counters, watched counting.
# --------------------------------------------------------------------------


def test_consume_counts_verdicts_and_fail_moves_the_counter() -> None:
    """The harness's whole job: PASS|/FAIL| lines become counts, anything else
    becomes a note, and only FAIL moves FAILS. Run, not read."""
    out = _bash(
        f'source {HARNESS}\n'
        'consume < <(printf "PASS|a\\nFAIL|b\\nsomething else\\nPASS|c\\n")\n'
        'echo "FAILS=$FAILS CONSUMED=$CONSUMED"\n',
        REPO,
    )
    assert "FAILS=1 CONSUMED=3" in out.stdout, out.stdout + out.stderr
    assert "something else" in out.stdout, "a non-verdict line was swallowed instead of noted"


def test_expect_verdicts_fails_a_leg_that_never_ran() -> None:
    """M2-S5's rule, and the reason it exists: a leg that dies on import emits
    zero verdicts, which without this guard is indistinguishable from a leg with
    nothing to say."""
    out = _bash(
        f'source {HARNESS}\n'
        'consume < <(printf "")\n'
        'expect_verdicts 3 "the leg"\n'
        'echo "FAILS=$FAILS"\n',
        REPO,
    )
    assert "FAILS=1" in out.stdout, out.stdout + out.stderr
    assert "expected at least 3" in out.stderr, "the failure does not say what was expected"


def test_a_pipe_would_lose_the_count_which_is_why_the_idiom_is_pinned() -> None:
    """The negative half, MEASURED rather than asserted in a comment. `… |
    consume` runs the function in a subshell, so its FAIL is counted and then
    discarded at the closing brace — the gate reports GREEN over a red leg. This
    is the defect `consume < <(` prevents, and the per-gate tests pin the idiom
    at every call site."""
    out = _bash(
        f'source {HARNESS}\n'
        'printf "FAIL|b\\n" | consume\n'
        'echo "FAILS=$FAILS"\n',
        REPO,
    )
    assert "FAILS=0" in out.stdout, (
        "a piped consume kept the count — the subshell hazard the idiom guards "
        "against no longer exists, so the pin should be re-argued, not kept"
    )


@pytest.mark.parametrize("gate", GATES, ids=lambda p: p.name)
def test_every_gate_sources_the_harness_and_defines_none_of_it_itself(gate: Path) -> None:
    """The migration's own invariant: one home. A gate that re-declared `FAILS=0`
    or its own `consume()` would shadow the lib and be a copy again."""
    body = without_comments(gate)
    assert "scripts/lib/verify_harness.sh" in body, f"{gate.name} does not source the harness"
    for redeclared in ("FAILS=0", "consume() {", "expect_verdicts() {", "pass() {"):
        assert redeclared not in body, f"{gate.name} re-declares {redeclared!r} — two homes"


# --------------------------------------------------------------------------
# redteam_restore.sh — the scaffold, watched restoring.
# --------------------------------------------------------------------------


def test_the_scaffold_restores_from_a_byte_copy_on_an_ABNORMAL_exit(tmp_path: Path) -> None:
    """The property the old per-file pins approximated with `"trap restore EXIT"
    in body`: a drill that dies mid-tamper still leaves the record as it found
    it. Here it is watched — the fake drill tampers and then exits 1 without
    ever calling the restore itself."""
    target = tmp_path / "record.json"
    target.write_text('{"measured": 13.75}\n')
    before = hashlib.sha256(target.read_bytes()).hexdigest()

    rc = _bash(
        'set -uo pipefail\n'
        'REDTEAM_LABEL="[test-drill]"\n'
        f'source {RESTORE}\n'
        f'redteam_snapshot "{target}"\n'
        f'printf "TAMPERED" > "{target}"\n'
        'exit 1\n',
        REPO,
    )
    assert rc.returncode == 1
    assert hashlib.sha256(target.read_bytes()).hexdigest() == before, (
        "the EXIT trap did not put the record back — a crashed drill damages evidence"
    )
    assert "restored" in rc.stdout, "the restore happened silently; a drill must say so"


def test_the_scaffold_verifies_the_restore_by_sha_rather_than_trusting_cp(tmp_path: Path) -> None:
    """`sha256sum` was the old pin; the property behind it is that a put-back
    which did not put anything back must not read as success.

    The arm is chosen so `cp` RETURNS 0 and the restore is still wrong: the
    target is replaced by a directory, which `cp` happily copies *into*. An
    exit-code check would have called that a restore. The sha check is the only
    thing standing between a drill and silently damaged evidence."""
    target = tmp_path / "record.json"
    target.write_text('{"measured": 13.75}\n')

    out = _bash(
        'set -uo pipefail\n'
        'REDTEAM_LABEL="[test-drill]"\n'
        f'source {RESTORE}\n'
        f'redteam_snapshot "{target}"\n'
        f'rm "{target}" && mkdir "{target}"\n'
        'redteam_restore\n',
        REPO,
    )
    assert "RESTORE DID NOT MATCH" in out.stderr, out.stdout + out.stderr


def test_a_restore_that_cannot_run_names_the_byte_copy_it_kept(tmp_path: Path) -> None:
    """The other failure branch: `cp` itself fails. The message must name the
    temp copy FIRST — it was taken at step 0 of this run, so it is right under
    every condition, where `git checkout --` is right only if the file was
    committed as the drill found it."""
    target = tmp_path / "record.json"
    target.write_text('{"measured": 13.75}\n')

    out = _bash(
        'set -uo pipefail\n'
        'REDTEAM_LABEL="[test-drill]"\n'
        f'source {RESTORE}\n'
        f'redteam_snapshot "{target}"\n'
        f'chmod 400 "{target}"\n'
        'redteam_restore\n'
        f'chmod 600 "{target}"\n',
        REPO,
    )
    assert "COULD NOT RESTORE" in out.stderr, out.stdout + out.stderr
    assert "Copy it back by hand" in out.stderr, (
        "a failed restore does not name the byte copy it kept — the one recovery "
        "that is right under every condition"
    )


def test_assert_restored_reports_byte_identity_rather_than_claiming_it(tmp_path: Path) -> None:
    """Step 3 of every drill. It must PASS on an honest restore and it must be
    able to fail: the second arm proves the comparison is real by moving the
    file after the scaffold has already restored and disarmed."""
    target = tmp_path / "record.json"
    target.write_text('{"measured": 13.75}\n')

    good = _bash(
        'set -uo pipefail\n'
        'REDTEAM_LABEL="[test-drill]"\n'
        f'source {RESTORE}\n'
        f'redteam_snapshot "{target}"\n'
        f'printf "TAMPERED" > "{target}"\n'
        'redteam_assert_restored\n'
        'echo "PROBLEMS=$PROBLEMS"\n',
        REPO,
    )
    assert "byte-identical to what the drill found" in good.stdout, good.stdout + good.stderr
    assert "PROBLEMS=0" in good.stdout

    bad = _bash(
        'set -uo pipefail\n'
        'REDTEAM_LABEL="[test-drill]"\n'
        f'source {RESTORE}\n'
        f'redteam_snapshot "{target}"\n'
        'redteam_restore\n'
        f'printf "LATE TAMPER" > "{target}"\n'
        'redteam_assert_restored\n'
        'echo "PROBLEMS=$PROBLEMS"\n',
        REPO,
    )
    assert "PROBLEMS=1" in bad.stdout, (
        "the byte-identity check cannot fail — it is a claim, not a comparison"
    )


def test_the_scaffold_refuses_to_load_without_a_label(tmp_path: Path) -> None:
    """`say` prints the drill's name. An unset label would print an empty prefix
    on every line of a destructive drill's transcript, so the lib refuses at
    source time rather than degrading (F-048's rule)."""
    out = _bash(f"unset REDTEAM_LABEL; source {RESTORE}; echo LOADED", REPO)
    assert "LOADED" not in out.stdout
    assert "REDTEAM_LABEL" in out.stderr


@pytest.mark.parametrize("drill", DRILLS, ids=lambda p: p.name)
def test_every_drill_uses_the_scaffold_and_defines_none_of_it_itself(drill: Path) -> None:
    """The per-drill half of the re-derived property. Each drill must source the
    scaffold, take its snapshot (which is what arms the trap), and end by
    asserting byte-identity — and must not carry its own copy of any of it."""
    body = without_comments(drill)
    assert "scripts/lib/redteam_restore.sh" in body, f"{drill.name} does not source the scaffold"
    assert "redteam_snapshot " in body, f"{drill.name} never snapshots — nothing arms the trap"
    assert "redteam_assert_restored" in body, (
        f"{drill.name} never proves it put the record back"
    )
    for redeclared in ("restore() {", "trap restore EXIT", 'BACKUP="$(mktemp)"'):
        assert redeclared not in body, f"{drill.name} re-declares {redeclared!r} — two homes"
