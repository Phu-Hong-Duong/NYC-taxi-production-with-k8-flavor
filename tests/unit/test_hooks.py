"""The pre-commit hook's own laws — M9-S13.

The hook is the one artifact in this program that NO gate can see: `.git/hooks`
is untracked by git's design, so nothing here can assert that the file is
installed on your machine. The PO was told that when they said yes, and the
honest response is to be precise about which halves ARE checkable:

1. **The tracked script exists and git records it EXECUTABLE.** A hook that git
   checks out at 0644 is a hook git skips *silently* — no error, no scan, and
   `ls` shows the file sitting right there. M8-S4 leg 2 lost a build to exactly
   this shape.
2. **The installer really sets the bit**, asked by RUNNING it into a temp
   directory and reading the mode back — not by grepping the script for `chmod`,
   which passes on a script that chmods the wrong file.
3. **It never destroys.** A pre-existing hook that is not ours is left alone and
   named; overwriting one is an explicit `FORCE=1`.
4. **`--check` distinguishes the three ways a hook fails to be a hook**: absent,
   stale, and present-but-not-executable.
5. **The hook fails CLOSED.** No `|| true`, no `exit 0` fallback: a scanner that
   did not run has not cleared a commit.
6. **The hook shares the AUDIT's acknowledgement table**, because a second copy
   of the rules with no copy of the argument for `scripts/gameday_m6.py` refuses
   every commit that touches the gameday, and the first thing its owner learns is
   `--no-verify`.
7. **`staged-secrets` is not one of the audit's legs** and cannot write a record.
8. **The drill does not install its own subject**, and both drills draw their
   plant from ONE generator (F-071's lesson lives in one place or in neither).
"""

from __future__ import annotations

import ast
import importlib.util
import os
import re
import stat
import subprocess
from pathlib import Path

import pytest
from conftest import REPO, read_record

HOOK = REPO / "scripts" / "hooks" / "pre-commit"
INSTALLER = REPO / "scripts" / "install_hooks.sh"
DRILL = REPO / "scripts" / "hook_redteam.sh"
SCANNER = REPO / "scripts" / "security_scan.py"
PLANT = REPO / "scripts" / "redteam_plant.py"
SCAN_REDTEAM = REPO / "scripts" / "security_scan_redteam.sh"
MAKEFILE = REPO / "Makefile"
# Spelled in full: F-047's marker guard resolves a record constant from the source
# of its assignment, and a name built from another name reads to it as an
# ordinary path.
HOOK_RECORD = REPO / "automation/runs/m9-hook/redteam.json"


def _module():
    spec = importlib.util.spec_from_file_location("security_scan", SCANNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# 1. the tracked script, and the bit git remembers
# --------------------------------------------------------------------------- #
def test_the_hook_is_tracked_and_git_records_it_executable():
    entry = subprocess.run(
        ["git", "ls-files", "-s", "scripts/hooks/pre-commit"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert entry, "scripts/hooks/pre-commit is not tracked — then it is not the tracked half"
    assert entry[0] == "100755", (
        f"git records mode {entry[0]} for the hook. At 100644 a fresh clone installs a "
        "file git then SKIPS without a word — the failure mode is silence, which is "
        "why the mode is asserted rather than assumed (M8-S4 leg 2's 0644)."
    )


def test_the_hook_fails_closed():
    text = HOOK.read_text()
    assert "--stage staged-secrets" in text and "--no-write" in text, (
        "the hook must run the staged leg, and it must not be able to write the "
        "tracked record from inside a commit"
    )
    assert "|| true" not in text, (
        "a `|| true` anywhere in a hook turns a scanner that could not run into a "
        "commit that was cleared. It fails closed on purpose."
    )
    assert re.search(r"exit 1", text), "the missing-instrument path must refuse, not pass"
    assert "set -euo pipefail" in text


def test_the_hook_states_the_limit_it_cannot_prove():
    text = HOOK.read_text().lower()
    for phrase in ("no-verify", "security-scan", "untracked"):
        assert phrase in text, (
            f"the hook's own header must say {phrase!r}: it is bypassable, it is not "
            "the audit of record, and nothing in this repo can see whether it is "
            "installed. A limit that lives only in a write-up is a limit nobody reads."
        )


# --------------------------------------------------------------------------- #
# 2. the installer, RUN rather than read
# --------------------------------------------------------------------------- #
def _install(dest: Path, *args: str, force: str | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "HOOKS_DIR": str(dest)}
    if force is not None:
        env["FORCE"] = force
    return subprocess.run(
        ["bash", str(INSTALLER), *args], cwd=REPO, capture_output=True, text=True, env=env
    )


def test_the_installer_sets_the_execute_bit_and_reads_it_back(tmp_path):
    dest = tmp_path / "hooks"
    proc = _install(dest)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    installed = dest / "pre-commit"
    assert installed.read_bytes() == HOOK.read_bytes()
    mode = stat.S_IMODE(installed.stat().st_mode)
    assert mode & 0o111, (
        f"installed at mode {mode:o}. This is asked by running the installer and "
        "reading the file back, not by grepping the script for `chmod` — that "
        "would pass on a script that chmods the wrong path."
    )


def test_the_installer_is_idempotent(tmp_path):
    dest = tmp_path / "hooks"
    assert _install(dest).returncode == 0
    second = _install(dest)
    assert second.returncode == 0
    assert "already current" in second.stdout


def test_the_installer_refuses_to_overwrite_a_hook_that_is_not_ours(tmp_path):
    dest = tmp_path / "hooks"
    dest.mkdir()
    foreign = dest / "pre-commit"
    foreign.write_text("#!/bin/sh\necho somebody else owns this\n")
    proc = _install(dest)
    assert proc.returncode == 2, "a foreign hook must stop the installer, not be overwritten"
    assert "REFUSED" in proc.stdout and "FORCE=1" in proc.stdout
    assert foreign.read_text().startswith("#!/bin/sh"), "and it must still be there"

    forced = _install(dest, force="1")
    assert forced.returncode == 0
    assert foreign.read_bytes() == HOOK.read_bytes()


@pytest.mark.parametrize(
    "break_it, expected",
    [
        (lambda p: p.unlink(), "NOT INSTALLED"),
        (lambda p: p.write_text("#!/bin/sh\nexit 0\n"), "STALE"),
        (lambda p: p.chmod(0o644), "NOT EXECUTABLE"),
    ],
)
def test_check_distinguishes_the_three_ways_a_hook_stops_being_one(tmp_path, break_it, expected):
    dest = tmp_path / "hooks"
    assert _install(dest).returncode == 0
    assert _install(dest, "--check").returncode == 0

    break_it(dest / "pre-commit")
    proc = _install(dest, "--check")
    assert proc.returncode == 1, f"{expected} must be a non-zero answer"
    assert expected in proc.stdout, proc.stdout


# --------------------------------------------------------------------------- #
# 3. the staged leg: one acknowledgement table, and no record
# --------------------------------------------------------------------------- #
def test_the_staged_leg_is_not_one_of_the_audits_legs():
    mod = _module()
    assert "staged-secrets" not in mod.STAGES, (
        "the audit record's leg set must not gain a leg that describes whatever "
        "happened to be staged the minute somebody ran the audit"
    )
    assert "staged-secrets" in mod.STAGE_CHOICES
    assert mod.STAGE_CHOICES[: len(mod.STAGES)] == mod.STAGES


def test_the_staged_leg_uses_the_audits_own_acknowledgement_table():
    """The point of putting the hook's leg in this module rather than in a script
    of its own. A second scanner with no copy of the gameday argument refuses
    every commit that touches `scripts/gameday_m6.py`."""
    source = SCANNER.read_text()
    tree = ast.parse(source)
    fn = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "stage_staged_secrets"
    )
    called = {
        node.func.id
        for node in ast.walk(fn)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "_classify" in called, (
        "the staged leg must classify through the same function as the audit — "
        "`_classify` is where `_acknowledge` is applied"
    )


def test_the_staged_leg_cannot_write():
    mod = _module()
    with pytest.raises(RuntimeError):
        mod.stage_staged_secrets(write=True)


def test_the_cli_refuses_the_staged_leg_without_no_write():
    proc = subprocess.run(
        ["uv", "run", "python", str(SCANNER), "--stage", "staged-secrets"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "requires --no-write" in proc.stderr
    assert "dirty the tree inside the commit" in proc.stderr, (
        "the refusal has to say WHY, or the next reader deletes it as pedantry"
    )


def test_a_staged_finding_is_classified_as_heading_for_history():
    mod = _module()
    out = mod._classify(
        [{"RuleID": "generic-api-key", "File": "whatever.txt", "StartLine": 2, "Secret": "x"}],
        origin="staged",
    )
    assert len(out["blocking"]) == 1
    assert "staged for commit" in out["blocking"][0]["why"]
    assert out["local_only"] == [], (
        "the index is not the disk: .gitignore has nothing to say about a file "
        "somebody has already `git add`ed"
    )


def test_classify_refuses_an_origin_it_does_not_know():
    mod = _module()
    with pytest.raises(ValueError):
        mod._classify([], origin="somewhere-else")


# --------------------------------------------------------------------------- #
# 4. the drill
# --------------------------------------------------------------------------- #
def test_the_drill_does_not_install_its_own_subject():
    text = DRILL.read_text()
    calls = re.findall(r"install_hooks\.sh[^\n|)]*", text)
    assert calls, "the drill must at least ASK whether the hook is installed"
    for call in calls:
        assert "--check" in call, (
            f"the drill invokes the installer as {call!r}. A drill that installs the "
            "hook it is about to test can pass against a hook of its own making — "
            "and it would leave a clone in a state its owner did not choose."
        )


def test_the_drill_asserts_the_negative_control_and_the_documented_limit():
    text = DRILL.read_text()
    assert "the commit SUCCEEDS with the hook installed" in text, (
        "without the negative control, 'the plant was blocked' is equally consistent "
        "with a hook that refuses everything"
    )
    assert "demonstrably RAN" in text, (
        "gotcha #81 at the commit boundary: an installed hook doing nothing looks "
        "exactly like an installed hook that passed"
    )
    assert "--no-verify" in text, "the bypass is MEASURED here, not asserted in a doc"
    assert "cat-file -e" in text, (
        "'I deleted the branch' and 'the object is gone' are different claims"
    )


def test_both_drills_draw_their_plant_from_one_generator():
    for drill in (DRILL, SCAN_REDTEAM):
        text = drill.read_text()
        assert "redteam_plant.py" in text, f"{drill.name} must use the shared generator"
        assert "secrets.choice" not in text, (
            f"{drill.name} carries its own draw. F-071 is the record of what goes "
            "wrong when a plant is drawn without regard for the rules that must "
            "match it, and a lesson learned in one copy is a lesson the other has not."
        )


def test_the_generator_draws_what_the_rules_can_match():
    """F-071, as a property rather than as a comment: the alphabet excludes the
    characters `generic-api-key` will not match, and the entropy floor is cleared
    over the WHOLE string, prefix included."""
    spec = importlib.util.spec_from_file_location("redteam_plant", PLANT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for _ in range(25):
        key_id, secret, h_id, h_secret = mod.aws_pair()
        assert key_id.startswith("AKIA") and len(key_id) == 20
        assert set(key_id) <= set(mod.ALNUM_UPPER + "AKIA")
        assert set(secret) <= set(mod.ALNUM), "`+` and `/` truncate the match — F-071"
        assert h_id >= 3.6 and h_secret >= 4.8


# --------------------------------------------------------------------------- #
# 5. the targets, and the record
# --------------------------------------------------------------------------- #
def test_the_make_targets_exist():
    text = MAKEFILE.read_text()
    for target in ("install-hooks", "install-hooks-check", "hook-redteam"):
        assert re.search(rf"^{re.escape(target)}:", text, re.M), f"no `make {target}`"


@pytest.mark.needs_records
def test_the_drill_record_says_it_passed_and_what_it_does_not_prove():
    rec = read_record(HOOK_RECORD)
    assert rec["verdict"] == "PASSED"
    assert rec["failures"] == 0
    assert rec["checks"] >= 15
    assert set(rec["arms"]) == {"A_negative_control", "B_refusal", "C_documented_limit"}
    assert "untracked" in rec["what_this_does_not_prove"], (
        "a record for an unverifiable artifact that does not say so is the claim "
        "this story was told not to make"
    )


@pytest.mark.needs_records
def test_the_record_holds_no_credential_shaped_value():
    """The scan flagged its own record thirteen times at M9-S9. This one is written
    by a drill that handles a real-shaped credential; the record must carry none of
    it — not the value, not a long digest under a credential-shaped key."""
    text = HOOK_RECORD.read_text()
    assert not re.search(r"AKIA[A-Z0-9]{16}", text)
    without_head = text.replace(read_record(HOOK_RECORD)["git_head"], "")
    assert not re.search(r"[A-Za-z0-9]{40,}", without_head), (
        "a long high-entropy run in a tracked record is what `generic-api-key` is for"
    )
