"""The M3 gate, tested as a thing that can be wrong (M3-S5).

Sibling of `test_verify_m2.py`, same premise: `scripts/verify_m3.sh` is the only
artifact whose job is to say whether M3 happened, and nothing else checks IT. So
these tests check the properties that would fail SILENTLY — a leg that stops
reading the storage keeps printing `ok`; a parse that returns nothing keeps
printing `ok` unless somebody demanded a positive count.

M3 adds one property M2 did not need, and it is the expensive lesson of this
story: the gate must assert PROPERTIES, not the literals that happened to be true
on the day it was written. `verify-m2` pinned the floor's name, the champion's
experiment and read `do_not_promote` by presence; all three went RED on the first
legitimate champion transition, for doing the right thing. A literal that goes
red when the program behaves correctly teaches the next session to edit
assertions, which is how a guard becomes a formality. The tests below pin the
re-derivations that replaced them.

House rule inherited from gotcha #35: match the INVOCATION, never the word. Both
scripts talk ABOUT fitting and ABOUT promotion in their comments and in the lines
they print, so every assertion about what the script DOES is made against a
comment-stripped copy.
"""

from __future__ import annotations

import re

from conftest import REPO, without_comments

VERIFY_M3 = REPO / "scripts" / "verify_m3.sh"
REDTEAM = REPO / "scripts" / "verify_m3_redteam.sh"
MAKEFILE = REPO / "Makefile"


# ------------------------------------------------------- the Makefile contract --
def test_the_m3_targets_are_real_and_no_longer_echo_todo():
    """A target that echoes TODO after its milestone landed is a lie with a tab
    character in front of it."""
    text = MAKEFILE.read_text()
    for target in ("verify-m3:", "verify-m3-redteam:"):
        body = text.split(f"\n{target}", 1)[1].split("\n.PHONY")[0]
        recipe = body.split("\n")[1]
        assert "TODO" not in recipe, f"{target} still echoes TODO"
    assert "bash scripts/verify_m3.sh" in text
    assert "bash scripts/verify_m3_redteam.sh" in text
    assert "verify-m3-redteam" in text.split(".PHONY:", 1)[1].split("\n", 20)[0] or any(
        "verify-m3-redteam" in line for line in text.splitlines() if line.startswith(".PHONY")
    ), "verify-m3-redteam is not declared .PHONY"


# ----------------------------------------------- the gate has no side effects ---
def test_the_gate_refits_nothing():
    """M3's numbers cost 12,447 s of fitting across two tracks (3,313.9 artisan +
    9,133.8 automation). A gate that re-derived any of them would cost more than
    the milestone and would mint MLflow runs on every verification. It reads."""
    body = without_comments(VERIFY_M3)
    for invocation in ("make train", "make ablation", "make automl", "make tune",
                       "make automation-track", "make bakeoff", "make predictions",
                       "taxi_mlops.training train", "taxi_mlops.training predict",
                       "make champion-transition"):
        assert invocation not in body, (
            f"verify_m3.sh invokes {invocation!r} — the gate re-fits what it is meant to read"
        )
    # Script paths are matched as INVOCATIONS, not as strings: §3 names
    # `scripts/leakage_redteam.py` in an allowlist — "which file may flip the
    # leaky switch" — and a bare substring test would call that a re-fit. The
    # difference between naming a script and running one is the runner in front.
    for script in ("scripts/bakeoff_m3.py", "scripts/automation_track.sh",
                   "scripts/ablation_m3.py", "scripts/leakage_redteam.py",
                   "scripts/champion_transition.sh"):
        for runner in ("bash ", "sh ", "uv run python ", "python ", "python3 ", "$(", "`"):
            assert f"{runner}{script}" not in body, (
                f"verify_m3.sh runs {script!r} — the gate re-fits what it is meant to read"
            )


def test_the_gate_mutates_no_registry_and_no_study_state():
    """It may CALL `registry.promote` — that is §6's F-011 proof, and it is safe
    only because the incumbent check runs before any mutation. It may not call a
    mutator directly, and it may not write to the Optuna storage at all."""
    body = without_comments(VERIFY_M3)
    for mutator in ("set_registered_model_alias", "delete_registered_model_alias",
                    "create_model_version", "delete_model_version", "delete_run",
                    "create_study", "delete_study", "optuna.create_study"):
        assert mutator not in body, (
            f"verify_m3.sh calls {mutator} — a gate that edits what it checks"
        )
    # The one allowed call, pinned so the reasoning above stays true: it must be
    # the refusing form. A promote() with a real incumbent_version would move an
    # alias from inside a gate.
    assert "incumbent_version=None" in body, (
        "§6 no longer proves registry.promote refuses an unread incumbent"
    )


def test_the_optuna_read_is_read_only_sql():
    """The storage leg reaches into the ONE Postgres. It must SELECT and nothing
    else — a gate holding a psql session open against the tuning database is one
    typo from being the thing that loses a study."""
    body = without_comments(VERIFY_M3)
    statements = re.findall(r"psql[^\n]*-c\s*\\?\n?\s*\"([^\"]+)\"", body, re.S)
    assert statements, "the Optuna leg's SQL could not be found — the parse is wrong"
    for sql in statements:
        lowered = sql.lower()
        assert lowered.lstrip().startswith("select"), f"non-SELECT statement in the gate: {sql!r}"
        for forbidden in ("insert", "update", "delete", "drop", "truncate", "alter"):
            assert forbidden not in lowered, f"{forbidden.upper()} in the gate's SQL: {sql!r}"


def test_the_gate_has_no_fast_mode_or_skip_flag():
    """M1's rule, inherited twice now. This gate runs in 5 seconds; there is
    nothing to excuse. A gate with a skip flag is a gate that runs with it."""
    body = without_comments(VERIFY_M3)
    for flag in ("SKIP_", "FAST=", "QUICK=", "--quick", "--fast"):
        assert flag not in body, f"verify_m3.sh grew a {flag} escape hatch"


# ------------------------------------------- every leg must actually have run ---
def test_every_python_leg_is_guarded_by_a_minimum_verdict_count():
    """The 'green light wired to no sensor' lesson, applied to the checker.

    A leg that dies on import contributes zero FAIL lines and the gate sails past
    it. `expect_verdicts` makes under-running a failure in its own right.
    """
    body = without_comments(VERIFY_M3)
    legs = body.count("consume < <(")
    guards = body.count("expect_verdicts ")
    assert legs >= 8, f"only {legs} Python leg(s) found — the parse is looking at the wrong thing"
    assert guards >= legs, f"{legs} Python leg(s) but only {guards} expect_verdicts guard(s)"
    for want in re.findall(r"expect_verdicts (\d+)", body):
        assert int(want) >= 1, "an expect_verdicts guard demands zero verdicts — it guards nothing"


def test_consume_is_never_called_through_a_pipe():
    """`… | consume` runs the function in a SUBSHELL, so every FAIL it counts is
    discarded at the closing brace and the gate exits 0 with failures on screen."""
    body = without_comments(VERIFY_M3)
    assert "| consume" not in body
    assert body.count("consume < <(") == body.count("consume <")


def test_every_leg_catches_its_own_exception_and_reports_it_as_a_failure():
    """A leg that raises past its own handler prints a traceback to a stream the
    counter never reads, and `expect_verdicts` would be the only thing that
    noticed. Each leg says so itself, by name."""
    body = without_comments(VERIFY_M3)
    legs = body.count("consume < <(")
    handlers = body.count("check itself raised")
    assert handlers >= legs, (
        f"{legs} leg(s) but only {handlers} 'check itself raised' handler(s) — "
        "a leg can die without saying which one it was"
    )


# ------------------------------- the legs that carry M3, and what makes them real
def test_the_bakeoff_verdicts_are_REPLAYED_not_read():
    """The M2 replay law, applied to M3's five verdicts.

    "bakeoff.json says REFUSE" stays true after somebody loosens
    `configs/train.yaml: gate`. Feeding the recorded NUMBERS back through
    `gate.decide` as it exists on disk is the only version that goes red.
    """
    body = without_comments(VERIFY_M3)
    assert "from taxi_mlops.training.gate import Incumbent, decide" in body, (
        "the bake-off leg no longer imports the live decision function"
    )
    assert 'd = decide(' in body, "nothing is replayed through decide()"
    assert 'd.verdict == c["verdict"]' in body, (
        "the replay does not compare its own answer against the recorded verdict"
    )
    # ...and the replay must carry the incumbent, or it answers a different
    # question from the one the verdict answered (M3-S1's watched refusal is a
    # REFUSE only because of the incumbent).
    assert "block_cfg, incumbent)" in body, "the replay drops the incumbent"


def test_the_ablation_verdicts_are_RE_DERIVED_from_the_tables_own_numbers():
    """The property that replaced a literal. A test asserting `g1 == KEEP` would
    have to be edited by every future ablation; re-applying DR-02's bar to the
    numbers printed beside each verdict never does, and it goes red on exactly
    the two edits that matter — a verdict changed without its number, or a number
    changed without its verdict."""
    body = without_comments(VERIFY_M3)
    assert "KEEP_BAR_PCT = 0.50" in body, "the DR-02 keep bar is no longer in the gate"
    assert 'earned = r["d_mae"] >= KEEP_BAR_PCT' in body, (
        "the gate no longer re-applies the bar to the table's own numbers"
    )
    assert "earned != printed" in body, (
        "the gate does not compare its re-derivation against the printed verdict"
    )


def test_the_gate_pins_no_champion_run_experiment_or_floor_name():
    """The M3-S5 lesson, pinned so it cannot be un-learned.

    `verify-m2` hard-coded `baseline-group-median`, `m2-modeling` and a
    presence-read of `do_not_promote`, and all three went RED on the first
    correct champion transition. This gate is checked for the same shape: no
    run id, no experiment name, no floor name typed into an assertion.
    """
    body = without_comments(VERIFY_M3)
    for literal in ("baseline-group-median", "m3-automl", "m3-artisan", "m2-modeling",
                    "auto-lgbm-v2", "92b73bd4", "3adee05a"):
        assert literal not in body, (
            f"verify_m3.sh pins the literal {literal!r} — it will go red on the next "
            "legitimate promotion, and the session that fixes it will edit the assertion"
        )
    # The champion is identified by what the bake-off RECORDED, never by a name.
    assert 'mv.run_id == winner["run_id"]' in body, (
        "the alias leg no longer checks the champion against the bake-off's own winner"
    )


def test_the_gate_reads_the_optuna_storage_rather_than_a_log():
    """"a study is state in a database, not state in a process" is the whole
    finding of the resume drill (gotcha #47). A gate that read `trials_pruned`
    out of the phase JSON would believe a number the storage could contradict."""
    body = without_comments(VERIFY_M3)
    assert "join studies s on s.study_id = t.study_id" in body, (
        "the tuning leg no longer reads trial states from Postgres"
    )
    assert 'states.get(name)' in body and '== rec["trials_total"]' in body, (
        "the gate does not reconcile the storage against the phase JSON"
    )
    assert 'v.get("PRUNED")' in body, "the pruned-trial check no longer reads the storage"


# --------------------------------------------------- the drill that proves RED --
def test_the_redteam_restores_from_a_byte_copy_under_a_trap():
    """A drill that damages the record it borrowed is worse than no drill. The
    restore must be trapped (so a Ctrl-C still restores) and VERIFIED (so a
    silent write failure is not read as success)."""
    body = without_comments(REDTEAM)
    assert "trap restore EXIT" in body, (
        "the restore is not trapped — a Ctrl-C would leave the tamper on disk"
    )
    assert "sha256sum" in body, "the restore is assumed rather than verified"
    assert 'cp "$BACKUP" "$RECORD"' in body, "the restore does not come from a byte copy"


def test_the_redteam_asserts_the_untampered_replays_still_pass():
    """This is what separates a replay leg from a checksum: it must go red on a
    WRONG number, not on any edit. A drill that only checked "it went red" would
    pass against a gate that fails whenever the file's mtime changes."""
    body = without_comments(REDTEAM)
    assert "untampered replays still passed" in body
    assert "survivors" in body, "the drill does not count the replays that must survive"
    # ...and it must assert the blast radius stayed small.
    assert re.search(r'red_oks.*-ge 40', body), (
        "the drill does not require the other sub-checks to keep running"
    )


def test_the_redteam_breaks_data_and_never_the_model():
    """It edits one number in one committed JSON. It must not touch the registry,
    the studies, the parquet or the configs — a drill with a wide blast radius is
    an outage rehearsal, not a gate test."""
    body = without_comments(REDTEAM)
    for forbidden in ("delete_registered_model_alias", "set_registered_model_alias",
                      "delete_model_version", "configs/train.yaml", "configs/features.yaml",
                      "data/processed", "data/predictions", "psql"):
        assert forbidden not in body, f"the M3 drill touches {forbidden!r}"
