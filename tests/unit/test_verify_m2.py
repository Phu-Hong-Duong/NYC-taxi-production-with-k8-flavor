"""The M2 gate, tested as a thing that can be wrong (M2-S5).

`scripts/verify_m2.sh` is the only artifact in this repo whose job is to say
whether the milestone happened. Nothing else checks IT, so these tests do — and
they check the properties that would fail silently, not the ones that fail
loudly. A leg that stops looking at the registry keeps printing `ok`; a leg
whose parse returns an empty string keeps printing `ok` unless somebody demanded
a positive count. M1's gate shipped with exactly that defect twice.

The house rule for these tests is gotcha #35's: match the INVOCATION, never the
word. Both scripts talk ABOUT `make train` and ABOUT deleting things in their
comments and in the lines they print to humans, so every assertion about what
the script DOES is made against a comment-stripped copy.
"""

from __future__ import annotations

import re

from conftest import REPO, without_comments

VERIFY_M2 = REPO / "scripts" / "verify_m2.sh"
REDTEAM = REPO / "scripts" / "verify_m2_redteam.sh"
MAKEFILE = REPO / "Makefile"


# ------------------------------------------------------- the Makefile contract --
def test_the_m2_targets_are_real_and_no_longer_echo_todo():
    """The Makefile is THE interface; a target that echoes TODO after its
    milestone landed is a lie with a tab character in front of it."""
    text = MAKEFILE.read_text()
    for target in ("verify-m2:", "verify-m2-redteam:"):
        body = text.split(f"\n{target}", 1)[1].split("\n.PHONY")[0]
        recipe = body.split("\n")[1]
        assert "TODO" not in recipe, f"{target} still echoes TODO"
    assert "bash scripts/verify_m2.sh" in text
    assert "bash scripts/verify_m2_redteam.sh" in text


# ----------------------------------------------- the gate has no side effects ---
def test_the_gate_never_refits_or_promotes_anything():
    """It checks what was promoted; it does not promote again.

    A gate that re-runs `make train` would mint MLflow runs on every
    verification and would judge a model the registry has never heard of. The
    champion is a registered artifact — the gate reads it.
    """
    body = without_comments(VERIFY_M2)
    for invocation in ("make train", "taxi_mlops.training train", "training.train",
                       "scripts/train_redteam.sh", "make predictions",
                       "taxi_mlops.training predict"):
        assert invocation not in body, (
            f"verify_m2.sh invokes {invocation!r} — the gate has side effects"
        )


def test_the_gate_mutates_no_registry_state():
    """`registry.py` is the only module allowed to write to the registry, and
    nothing in it deletes (M2-S3). The GATE writes nothing at all — the drill
    script is the one place a mutation is allowed to live."""
    body = without_comments(VERIFY_M2)
    for mutator in ("set_registered_model_alias", "delete_registered_model_alias",
                    "create_model_version", "delete_model_version", "delete_run"):
        assert mutator not in body, (
            f"verify_m2.sh calls {mutator} — a gate that edits what it checks"
        )


def test_the_gate_has_no_fast_mode_or_skip_flag():
    """M1's gate refused one for its slow leg and this one has no slow leg to
    excuse: it re-reads and re-reconciles in seconds. A gate with a skip flag is
    a gate that runs with the skip flag."""
    body = without_comments(VERIFY_M2)
    for flag in ("SKIP_", "FAST=", "QUICK="):
        assert flag not in body, f"verify_m2.sh grew a {flag} escape hatch"


# ------------------------------------------- every leg must actually have run ---
def test_every_python_leg_is_guarded_by_a_minimum_verdict_count():
    """The 'green light wired to no sensor' lesson, applied to the checker.

    A Python leg that dies on import contributes zero `FAIL` lines and the gate
    would sail past it. `expect_verdicts` demands each leg emit at least N
    verdicts, so under-running is itself a failure — this is what caught the
    dropped-alias case in the red-team drill, where the registry leg managed 1
    verdict of the 7 it owes.
    """
    body = without_comments(VERIFY_M2)
    legs = body.count("consume < <(")
    guards = body.count("expect_verdicts ")
    assert legs >= 5, f"only {legs} Python leg(s) found — the parse is looking at the wrong thing"
    assert guards >= legs, f"{legs} Python leg(s) but only {guards} expect_verdicts guard(s)"
    for want in re.findall(r"expect_verdicts (\d+)", body):
        assert int(want) >= 1, "an expect_verdicts guard demands zero verdicts — it guards nothing"


def test_consume_is_never_called_through_a_pipe():
    """`… | consume` runs the function in a SUBSHELL, so every FAIL it counts is
    discarded at the closing brace and the gate exits 0 with failures on screen.
    Process substitution keeps the counters in this shell."""
    body = without_comments(VERIFY_M2)
    assert "| consume" not in body
    assert body.count("consume < <(") == body.count("consume <")


# --------------------------------------------------- the legs that carry M2 -----
def test_the_gate_replays_the_transcript_through_the_live_decision_function():
    """The kickoff's leg is 'the gate refusal transcript exists with both
    numbers'. Grepping the doc for the word REFUSE would satisfy that sentence
    and would stay green after somebody loosened `configs/train.yaml: gate` —
    which is the exact change the constitution reserves for a PO fork. So the
    doc's own numbers are fed back through `decide()` as it exists on disk now.
    """
    body = without_comments(VERIFY_M2)
    assert "from taxi_mlops.training.gate import GateError, Incumbent, decide" in body
    assert "decide(metrics(" in body
    assert "min_improvement_pct" in body and ">= 2.0" in body
    assert "require_no_kpi10_regression" in body
    # and the two comparisons the gate must decline to make at all
    assert 'metrics(good["challenger"], "val")' in body
    assert "baseline-constant-median" in body


def test_the_replay_leg_checks_that_the_floor_only_ever_got_harder():
    """M3-S1 changed the gate's floor (F-010), which the replay leg has to allow
    or every historical verdict becomes unreproducible — and must not allow
    blindly, or "swap in an easier floor" becomes the way to loosen a gate
    without touching a threshold. The direction is measured from the two
    committed transcripts, both scored by the evaluator on the same month.
    """
    body = without_comments(VERIFY_M2)
    assert "docs/promotion_gate_m3.md" in body
    assert "m3_floor < m2_floor" in body
    # ...and the incumbent condition is proven armed rather than assumed
    assert "incumbent=inc" in body and "serving champion" in body


def test_the_gate_reads_the_champion_through_the_alias_not_through_a_search():
    """On MLflow server 3.15.1 `search_model_versions` returns versions whose
    `aliases` field is EMPTY (M2-S3's finding), so a champion resolved that way
    is a champion resolved by guessing."""
    body = without_comments(VERIFY_M2)
    assert "get_model_version_by_alias" in body
    # search_model_versions is fine for the pollution check (does any HOBBLED run
    # own a version?) — it must not be how the champion itself is found.
    champion_block = body.split('section "1.')[1].split('section "2.')[0]
    assert "search_model_versions" not in champion_block


def test_the_kpi_15_leg_looks_at_the_published_marts_not_only_at_the_docs():
    """gotcha #15: KPI-09/KPI-10 come from the evaluator and nowhere else. The
    doc-contract tests police the documents; this leg polices the WAREHOUSE,
    where a well-meaning `avg(abs(...))` column would otherwise appear."""
    body = without_comments(VERIFY_M2)
    assert "column_name LIKE '%kpi_09%'" in body
    assert "kpi_11_mae_min" in body and "kpi_12_within_tol_pct" in body


def test_the_rollup_leg_compares_the_mart_against_the_evaluator_artifact():
    """A segment number that cannot roll up to the evaluator's is not a
    segmentation of it. The comparison crosses two systems on purpose: Postgres
    on one side, the evaluator's published manifest on the other."""
    body = without_comments(VERIFY_M2)
    assert "data/predictions/predictions.json" in body
    assert "segment='overall'" in body
    assert "kpi_09_mae_minutes" in body


def test_the_root_stray_leg_is_wider_than_the_one_filename_that_prompted_it():
    """M2's kickoff asked for 'no stray _handoff_entry.md at the repo root'.
    Session (z) then left an empty `marts.duckdb` there — the FINGERPRINT of
    gotcha #38, which a filename-specific check would have missed and a
    .gitignore entry would have hidden. The leg diffs the root against
    `git ls-files` plus a named list of things a working clone really has.
    """
    body = without_comments(VERIFY_M2)
    assert "git" in body and "ls-files" in body
    assert "EXPECTED = {" in body
    # the whole point: it is not a search for one name
    assert 'listdir(".")' in body


# ------------------------------------------------------------ the red team -----
def test_the_red_team_restores_the_alias_no_matter_how_it_exits():
    """The drill deletes the single most load-bearing fact in M2. A Ctrl-C
    between the delete and the restore must not leave the program without a
    champion, so the restore is on an EXIT trap and is idempotent."""
    body = without_comments(REDTEAM)
    assert "trap restore EXIT" in body
    assert "delete_registered_model_alias" in body
    assert "set_registered_model_alias" in body
    # ...and it verifies the restore rather than assuming the write landed
    assert 'assert str(mv.version) == state["version"]' in body


def test_the_red_team_breaks_only_the_pointer_never_the_model():
    """Deleting the alias is exactly reversible; deleting a version or a run is
    not, and would destroy the evidence the whole milestone rests on."""
    body = without_comments(REDTEAM)
    # `delete_registered_model(` and not `delete_registered_model`: the second is
    # a prefix of `delete_registered_model_alias`, which is the ONE call this
    # drill is built on. A substring check here would ban the drill from itself —
    # the same class of mistake as gotcha #35, caught by running the test.
    for destructive in ("delete_model_version", "delete_registered_model(", "delete_run",
                        "delete_experiment", "rm -rf"):
        assert destructive not in body, f"the drill calls {destructive} — that is not a drill"


def test_the_red_team_asserts_the_other_legs_kept_running():
    """A gate that collapses to one failure when one thing breaks tells you
    nothing about the rest of the system. The drill demands the RED run still
    carries a large positive count of passing sub-checks, and names four legs
    that must be untouched by a missing champion."""
    body = without_comments(REDTEAM)
    assert 'red_oks="$(printf' in body
    assert '"$red_oks" -ge 25' in body
    assert "unaffected leg still green" in body
    assert "the gate is GREEN again" in body


# ------------------------------ M9-S10: the incumbent margin cannot be lowered --
MARGIN_REDTEAM = REPO / "scripts" / "gate_margin_redteam.sh"


def test_the_gate_replays_are_era_aware_and_the_ratchet_has_exactly_one_home():
    """Two halves, and only together do they mean anything (F-016/F-068).

    Era-awareness lets HISTORY replay against the bar it was actually taken
    against; on its own it would also let a LOOSENING replay perfectly. The
    ratchet is the half that does not move — and it is asserted here to appear
    ONCE, because the first draft of this leg asserted it twice and a lowered
    margin produced two FAILs carrying one sentence, which reads like two
    independent witnesses.
    """
    body = without_comments(VERIFY_M2)
    assert "gate_eras.in_force_margin(" in body
    assert "gate_eras.parse_recorded_margin(" in body
    assert body.count("gate_eras.assert_margin_never_decreased(") == 1
    # ...and the era-aware summary must NOT be about the live bar, or it would
    # fire alongside the ratchet on every loosening.
    assert "replayed ERA-AWARE" in body


def test_the_margin_drill_plants_a_plausible_number_and_restores_it_verifiably():
    """0.10 is the point: a well-formed, still-positive margin that still
    refuses the identity case, so it satisfies F-068's arithmetic while
    spending the PO's letter without one. A drill planting `-200` proves the
    parser works and teaches nobody anything."""
    body = without_comments(MARGIN_REDTEAM)
    assert 'PLANTED="0.10"' in body
    assert "trap restore EXIT" in body
    assert 'sha256sum "$CONFIG"' in body
    # It touches the config and NOTHING else — no registry verb, no cluster
    # mutation, no record rewritten.
    for forbidden in ("set_registered_model_alias", "delete_", "kubectl", "rm -rf", "--json"):
        assert forbidden not in body, f"the drill calls {forbidden} — that is not a drill"


def test_the_margin_drill_requires_the_era_aware_replays_to_STAY_green():
    """The load-bearing negative. If lowering today's bar turned the historical
    replays red, the replays would be reading the live config instead of the
    era — which is the defect era-awareness exists to prevent, arriving through
    the check that was supposed to prove it."""
    body = without_comments(MARGIN_REDTEAM)
    assert "replayed ERA-AWARE" in body
    assert "the replays are reading the live bar, not the era" in body
    assert '"$red_oks" -ge 50' in body
    assert "the gate is GREEN again" in body


def test_the_makefile_exposes_the_margin_drill():
    body = MAKEFILE.read_text()
    assert "gate-margin-redteam:" in body
    assert "bash scripts/gate_margin_redteam.sh" in body
