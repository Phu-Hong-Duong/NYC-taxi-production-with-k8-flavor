"""The M5 gate, tested as a thing that can be wrong (M5-S5).

Fourth in the line after `test_verify_m2/m3/m4.py`, same premise:
`scripts/verify_m5.sh` is the only artifact whose job is to say whether M5
happened, and nothing else checks IT. So these tests pin the properties that
would fail SILENTLY — a leg that stops reading a record keeps printing `ok`, a
parse that returns nothing keeps printing `ok` unless somebody demanded a
positive count.

M5 adds three properties its predecessors did not need:

  * IT MAY ASK THE SERVICE FOR ONE PREDICTION, and must not do more. A serving
    gate that never asks the endpoint for the artifact it exists to produce
    would pass against a dead model with a healthy `Ready` condition (gotcha
    #59/#71). One request is evidence; a load run is a re-measurement, and
    re-measuring p95 inside the gate would make the gate the thing that decides
    what p95 is.

  * IT MUST NOT MOVE OR STOP ANYTHING. `make serve`, `make load-drill`,
    `make stop-start-drill` and every registry-mutating verb are forbidden: the
    stop annotation in particular is one `kubectl annotate` away from a gate
    that takes the endpoint down to check that it is up.

  * NO LITERAL VERSION. The champion is version 2 today. A gate that typed `2`
    would go RED the first time a legitimate promotion happens — gotchas
    #49/#50, the disease `verify-m2` caught at M3-S5.

House rule inherited from gotcha #35 and re-learned at #68: match the
INVOCATION, never the word. This gate prints advice ("run `make serve`") and
argues about promotion in prose, so every assertion about what it DOES is made
against a comment-stripped copy, with the needle in command position.
"""

from __future__ import annotations

import re

import pytest
from conftest import REPO, invokes, without_comments

VERIFY_M5 = REPO / "scripts" / "verify_m5.sh"
REDTEAM = REPO / "scripts" / "verify_m5_redteam.sh"
MAKEFILE = REPO / "Makefile"
RUNBOOK = REPO / "docs" / "runbooks" / "serving.md"
REHEARSAL = REPO / "scripts" / "serving_stop_start_rehearsal.py"


# ------------------------------------------------------- the Makefile contract --
def test_the_m5_targets_are_real_and_no_longer_echo_todo():
    text = MAKEFILE.read_text()
    for target in ("verify-m5:", "verify-m5-redteam:", "stop-start-drill:"):
        body = text.split(f"\n{target}", 1)[1].split("\n.PHONY")[0]
        recipe = body.split("\n")[1]
        assert "TODO" not in recipe, f"{target} still echoes TODO"
    assert "bash scripts/verify_m5.sh" in text
    assert "bash scripts/verify_m5_redteam.sh" in text
    assert any(
        "verify-m5-redteam" in line for line in text.splitlines() if line.startswith(".PHONY")
    )


def test_the_gate_has_no_skip_flag_and_no_fast_mode():
    """M1's rule, inherited a fifth time: a gate with a fast mode is a gate that
    runs in fast mode."""
    body = without_comments(VERIFY_M5)
    for forbidden in ("SKIP_", "FAST", "--quick", "QUICK"):
        assert forbidden not in body, f"{forbidden} appears in the gate — no skip flag exists"


# --------------------------------------------------- what the gate must NOT do --
def test_the_gate_re_runs_nothing_expensive():
    """The evidence M5 reads cost a ~6.5-minute drill including a deliberate
    outage, and the parity sweep needs a live sweep of 16 rows. Re-running any of
    it inside the gate would make verification the thing that produces the
    numbers being verified."""
    body = without_comments(VERIFY_M5)
    for command in (
        "make load-drill",
        "make load",
        "make serve",
        "make parity",
        "make parity-redteam",
        "make stop-start-drill",
        "make pipeline",
        "make train",
        "make predictions",
        "make marts",
    ):
        assert not invokes(body, command), f"the gate runs `{command}` — it must only read"
    assert "serving_load_drill.py" not in body
    assert "serving_stop_start_rehearsal.py" not in body
    assert "deploy_champion.sh" not in body


def test_the_gate_cannot_stop_restart_or_delete_anything():
    """The stop annotation is exactly reversible, which is what makes it
    tempting — and a gate that takes the endpoint down to check that it is up is
    not a gate. `kubectl` may only be asked questions."""
    body = without_comments(VERIFY_M5)
    read_only = {"get", "describe", "version", "config"}
    # Both spellings the gate uses: the shell array `"${KUBECTL[@]}" <verb>` and
    # the embedded Python helper's `kubectl("<verb>", ...)`.
    verbs = re.findall(r'"\$\{KUBECTL\[@\]\}"\s+(\w[\w-]*)', body)
    verbs += re.findall(r'kubectl\(\s*"(\w[\w-]*)"', body)
    verbs += re.findall(r'kubectl\(\s*"-n",\s*[\w\[\]"\.]+,\s*"(\w[\w-]*)"', body)
    assert verbs, "no kubectl invocation found — the test is not looking where the gate looks"
    offenders = sorted({v for v in verbs if v not in read_only})
    assert not offenders, f"the gate uses mutating kubectl verb(s): {offenders}"
    for mutating in ("annotate", "delete", "apply", "scale", "patch"):
        assert f"kubectl {mutating}" not in body


def test_the_gate_never_mutates_the_registry():
    body = without_comments(VERIFY_M5)
    for verb in (
        "set_registered_model_alias",
        "delete_registered_model_alias",
        "register_model",
        "create_model_version",
        "transition_model_version_stage",
    ):
        # The mutating verbs appear ONLY inside the §7 leg's own deny-list, which
        # is a set literal it searches the serving package for — never a call.
        calls = re.findall(rf"\.{verb}\(", body)
        assert not calls, f"the gate CALLS {verb}"


# ------------------------------------------------ properties, never literals ----
def test_the_gate_types_no_champion_version_no_run_id_no_pod_name():
    """F-017, gotchas #49/#50. The served version must be compared with what the
    alias says; a literal would turn the next legitimate promotion into a RED
    gate for doing the right thing."""
    body = without_comments(VERIFY_M5)
    assert not re.search(r"version\s*==\s*[\"']?2[\"']?", body)
    assert not re.search(r"\b[0-9a-f]{32}\b", body), "a run id is typed in the gate"
    assert not re.search(r"nyc-taxi-eta-predictor-[0-9a-f]{6,}", body), "a pod name is typed"
    assert "auto-lgbm-v2" not in body
    # The version comparison exists and is made against the alias.
    assert "alias_version" in body and "get_model_version_by_alias" in body


def test_the_parity_bar_comes_from_the_module_not_from_the_record():
    """A record that loosened its own tolerance would otherwise pass against
    itself — the shape M2-S5's replay legs exist to prevent."""
    body = without_comments(VERIFY_M5)
    assert "parity_mod.TOLERANCE_MINUTES" in body
    assert "parity_mod.HAZARDS" in body, "the hazard count must come from code, not from the record"


def test_every_python_leg_demands_a_minimum_verdict_count():
    """M2's rule: a leg that dies on import contributes zero silent passes unless
    somebody demanded a positive count."""
    body = without_comments(VERIFY_M5)
    legs = body.count("consume < <(")
    expectations = body.count("expect_verdicts ")
    # `expect_verdicts` is defined once and then called per leg.
    assert legs >= 6, f"only {legs} leg(s) found — the gate lost a section"
    assert expectations >= legs, (
        f"{legs} legs but only {expectations - 1} expect_verdicts call(s) — a leg can die silently"
    )


@pytest.mark.needs_records
def test_the_gate_reads_the_tracked_records_it_names():
    body = VERIFY_M5.read_text()
    for record in (
        "automation/runs/m5-parity/parity.json",
        "automation/runs/m5-load/headline.json",
        "automation/runs/m5-load/selfheal.json",
        "automation/runs/m5-load/ramp.json",
        "automation/runs/m5-s5/stop-start.json",
        "automation/runs/m3s5/bakeoff.json",
    ):
        assert record in body, f"the gate does not read {record}"
        assert (REPO / record).exists(), f"{record} is named by the gate but does not exist"


@pytest.mark.needs_records
def test_the_records_the_gate_replays_are_tracked_by_git():
    """F-029, closed at M5-S1: a gate replaying evidence that is not in the
    repository is a gate whose inputs review cannot see. `git check-ignore` is a
    two-second command and gotcha #69 is what it prevents."""
    import subprocess

    for record in (
        "automation/runs/m5-load/selfheal.json",
        "automation/runs/m5-s5/stop-start.json",
    ):
        result = subprocess.run(
            ["git", "check-ignore", "-q", record], cwd=REPO, capture_output=True
        )
        assert result.returncode != 0, (
            f"{record} is gitignored — the red team's edit would leave no diff"
        )


# ------------------------------------------------------------ the red team ------
def test_the_red_team_restores_under_a_trap_and_verifies_the_restore():
    body = REDTEAM.read_text()
    assert "trap restore EXIT" in body, "a crashed drill must still put the record back"
    assert "sha256sum" in body, "the restore must be verified, not assumed"
    assert "git status --porcelain" in body, "a clean drill leaves a clean tree (F-029)"


def test_the_red_team_breaks_one_field_of_one_record_and_nothing_else():
    body = without_comments(REDTEAM)
    assert "selfheal.json" in body
    assert 'recovery["outage_seconds"]' in body
    # It must not touch the cluster, the registry or any other record.
    for forbidden in ("kubectl", "make serve", "make load-drill", "set_registered_model_alias"):
        assert not invokes(body, forbidden), f"the red team runs `{forbidden}`"
    assert "headline.json" not in body and "parity.json" not in body


def test_the_red_team_asserts_both_witnesses_and_the_survivors():
    """A drill that only checked the exit code would pass against a gate that
    went red for the wrong reason, and one that only checked the failure would
    not notice the suite collapsing."""
    body = REDTEAM.read_text()
    assert "does not equal recovered_at" in body, "the anchor witness is not asserted"
    assert "the runbook quotes number(s) that no record holds" in body, (
        "the runbook witness is not asserted"
    )
    assert "still passed" in body and "collateral damage" in body


# ------------------------------------------------- the runbook it verifies ------
def test_the_runbook_states_what_is_not_rehearsed():
    """The M4-S2 backup precedent: an unrehearsed path says so in every artifact
    that mentions it, not in one footnote."""
    text = RUNBOOK.read_text()
    assert len(re.findall(r"NOT\s+REHEARSED", text, re.I)) >= 2
    assert "set_registered_model_alias" in text, "the rollback must be TYPED, not described"
    assert "features.version" in text, (
        "a rollback that moves only the alias yields a 500 on every quote — the runbook must say so"
    )


def test_the_rehearsal_script_types_the_same_commands_the_runbook_prints():
    """One string, two consumers (F-017 applied to prose): a runbook whose
    commands drift from the drill that proved them is a runbook nobody proved."""
    runbook = RUNBOOK.read_text()
    script = REHEARSAL.read_text()
    assert "serving.kserve.io/stop=true --overwrite" in runbook
    assert "serving.kserve.io/stop=true" in script
    assert "serving.kserve.io/stop-" in runbook and "serving.kserve.io/stop-" in script


def test_the_rehearsal_refuses_to_measure_a_service_that_is_already_down():
    """A stop drill against a stopped service measures nothing and would report a
    suspiciously fast stop."""
    body = REHEARSAL.read_text()
    assert "REFUSED" in body and "not answering before the drill" in body
