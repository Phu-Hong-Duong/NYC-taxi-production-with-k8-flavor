"""The M6 gate, tested as a thing that can be wrong (M6-S5 leg 2).

Fifth in the line after `test_verify_m2/m3/m4/m5.py`, same premise:
`scripts/verify_m6.sh` is the only artifact whose job is to say whether M6
happened, and nothing else checks IT. So these tests pin the properties that
would fail SILENTLY — a leg that stops reading a record keeps printing `ok`, a
parse that returns nothing keeps printing `ok` unless somebody demanded a
positive count.

M6 adds three properties its predecessors did not need:

  * ITS EVIDENCE COST AN OUTAGE. The gameday is ~55 minutes of injections
    including a deliberate ~5 minute total outage of the only predictor; the
    canary and rollback drills move rider traffic and the alias. A gate that
    re-ran any of it would cost an outage per verification AND would move the
    pointer M6 law 3 forbids moving. So the forbidden list here is longer than
    M5's, and it includes the drills whose whole purpose is to break things.

  * IT MUST NOT INJECT, KILL, SHIFT OR PROMOTE. `kubectl` may only be asked
    questions, the Prometheus API may only be read, and no registry-mutating
    verb may be called. The one write-shaped thing the gate does is send a
    single inference request, which is a read of the service.

  * NO THRESHOLD IS TYPED. Every alert threshold is parsed out of
    `infra/monitoring/alerting_rules.yml` and looked for in
    `docs/slo_serving.md`. A gate that typed `0.05` would go green after
    somebody loosened the rule to 0.5 — which is precisely the change the
    constitution reserves for a PO fork.

House rule inherited from gotcha #35 and re-learned at #68: match the
INVOCATION, never the word. This gate prints advice and argues about alerting in
prose, so every assertion about what it DOES is made against a comment-stripped
copy, with the needle in command position.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
VERIFY_M6 = REPO / "scripts" / "verify_m6.sh"
REDTEAM = REPO / "scripts" / "verify_m6_redteam.sh"
MAKEFILE = REPO / "Makefile"
RULES = REPO / "infra" / "monitoring" / "alerting_rules.yml"


def without_comments(path: pathlib.Path) -> str:
    """Drop whole-line comments (shell and the embedded Python alike)."""
    return "\n".join(
        line for line in path.read_text().splitlines() if not line.lstrip().startswith("#")
    )


def invokes(body: str, command: str) -> bool:
    """Is `command` RUN here, or merely named?"""
    pattern = rf"(?:^|\||&&|;|\$\()\s*{re.escape(command)}(?:\s|$)"
    return bool(re.search(pattern, body, re.M))


# ------------------------------------------------------- the Makefile contract --
def test_the_m6_targets_are_real_and_no_longer_echo_todo():
    text = MAKEFILE.read_text()
    for target in ("verify-m6:", "verify-m6-redteam:"):
        body = text.split(f"\n{target}", 1)[1].split("\n.PHONY")[0]
        recipe = body.split("\n")[1]
        assert "TODO" not in recipe, f"{target} still echoes TODO"
    assert "bash scripts/verify_m6.sh" in text
    assert "bash scripts/verify_m6_redteam.sh" in text
    assert any(
        "verify-m6-redteam" in line for line in text.splitlines() if line.startswith(".PHONY")
    )


def test_the_gate_has_no_skip_flag_and_no_fast_mode():
    """M1's rule, inherited a SIXTH time: a gate with a fast mode is a gate that
    runs in fast mode."""
    body = without_comments(VERIFY_M6)
    for forbidden in ("SKIP_", "FAST", "--quick", "QUICK"):
        assert forbidden not in body, f"{forbidden} appears in the gate — no skip flag exists"


# --------------------------------------------------- what the gate must NOT do --
def test_the_gate_re_runs_nothing_expensive():
    """M6's evidence cost ~55 minutes of injections and a deliberate ~5 minute
    outage of the only predictor. Re-running any of it inside the gate would make
    verification the thing that produces the numbers being verified — and would
    cost an outage every time somebody asked whether the milestone happened."""
    body = without_comments(VERIFY_M6)
    for command in (
        "make gameday",
        "make canary",
        "make canary-deploy",
        "make canary-spike",
        "make rollback",
        "make restore-drill",
        "make alert-fire-drill",
        "make shadow",
        "make shadow-run",
        "make load",
        "make load-drill",
        "make serve",
        "make deploy-monitoring",
        "make backup",
        "make train",
    ):
        assert not invokes(body, command), f"the gate runs `{command}` — it must only read"
    # The needle must sit where a shell would START a command (gotcha #68, and
    # this test earned it on its first run): the gate legitimately READS
    # `scripts/platform_backup.sh` as a FILE to check the rehearsal label it
    # prints, and a bare `in body` search called that an invocation.
    scripts = (
        "gameday_m6.py",
        "canary_release_drill.py",
        "alias_rollback_rehearsal.py",
        "restore_rehearsal.py",
        "alert_fire_drill.py",
        "canary_spike.py",
        "serving_load_drill.py",
        "deploy_champion.sh",
        "deploy_monitoring.sh",
        "platform_backup.sh",
    )
    # ...and the launcher itself must sit in command position, or the `sh` in
    # `bash` — or in `..._backup.sh": Path(...)` — matches. Two rounds of the
    # same lesson in one test.
    launcher = r"(?:^|[|;&(]|\$\()\s*(?:bash|sh|python3?|uv run python)\s+\S*"
    for script in scripts:
        assert not re.search(rf"{launcher}{re.escape(script)}", body, re.M), (
            f"the gate RUNS {script} — it must only read its record"
        )
        assert not re.search(rf"subprocess\.run\(\[[^\]]*{re.escape(script)}", body), (
            f"the gate spawns {script} — it must only read its record"
        )


def test_the_gate_cannot_inject_kill_shift_or_deploy():
    """`kubectl` may only be asked questions. A gate that deletes a pod to check
    that self-heal works has re-run the gameday; a gate that applies an Ingress
    has shifted rider traffic to verify that traffic can be shifted."""
    body = without_comments(VERIFY_M6)
    read_only = {"get", "describe", "version", "config"}
    verbs = re.findall(r'"\$\{KUBECTL\[@\]\}"\s+(\w[\w-]*)', body)
    verbs += re.findall(r'kubectl\(\s*"(\w[\w-]*)"', body)
    verbs += re.findall(r'kubectl\(\s*"-n",\s*[\w\[\]"\.]+,\s*"(\w[\w-]*)"', body)
    assert verbs, "no kubectl invocation found — the test is not looking where the gate looks"
    offenders = sorted({v for v in verbs if v not in read_only})
    assert not offenders, f"the gate uses mutating kubectl verb(s): {offenders}"
    for mutating in ("annotate", "delete", "apply", "scale", "patch", "exec", "cp"):
        assert f"kubectl {mutating}" not in body


def test_the_gate_only_reads_prometheus():
    """The one HTTP surface this gate talks to that PREDECESSORS did not. The
    admin API can delete series and the reload endpoint can swap the rules the
    gate is checking, so both are forbidden; only queries and read endpoints
    appear."""
    body = without_comments(VERIFY_M6)
    for forbidden in ("/api/v1/admin", "delete_series", "/-/reload", "/api/v2/silences"):
        assert forbidden not in body, f"the gate touches {forbidden}"
    assert '"POST"' not in body and "method=\"POST\"" not in body
    assert "/api/v1/query" in body and "/api/v1/rules" in body


def test_the_gate_never_mutates_the_registry():
    body = without_comments(VERIFY_M6)
    for verb in (
        "set_registered_model_alias",
        "delete_registered_model_alias",
        "register_model",
        "create_model_version",
        "transition_model_version_stage",
    ):
        assert not re.findall(rf"\.{verb}\(", body), f"the gate CALLS {verb}"


# ------------------------------------------------ properties, never literals ----
def test_the_gate_types_no_champion_version_no_pod_name_no_run_id():
    """F-017, gotchas #49/#50. M6's two sanctioned alias moves round-tripped, so
    the champion is version 2 again today — and a gate that typed `2` would go
    RED at M7's first legitimate promotion for doing the right thing."""
    body = without_comments(VERIFY_M6)
    assert not re.search(r"version\s*==\s*[\"']?2[\"']?", body)
    assert not re.search(r"\b[0-9a-f]{32}\b", body), "a run id is typed in the gate"
    assert not re.search(r"nyc-taxi-eta-predictor-[0-9a-f]{6,}", body), "a pod name is typed"
    assert "auto-lgbm-v2" not in body
    assert "get_model_version_by_alias" in body, "the version must come from the alias"


def test_no_alert_threshold_is_typed_in_the_gate():
    """Every number in a rule is parsed out of the rules file and looked for in
    the SLO document. A gate carrying its own copy of `0.05` would stay green
    after the rule was loosened to `0.5` — the exact change the constitution
    reserves for a PO fork."""
    body = without_comments(VERIFY_M6)
    thresholds = set(re.findall(r"[<>]=?\s*([0-9]*\.?[0-9]+)", RULES.read_text()))
    assert thresholds, "no thresholds parsed out of the rules file — the test is looking wrongly"
    # The gate may not carry a rule's threshold as its own literal. Values that
    # are also ordinary small integers (1, 2, 0) are excluded: they are counts
    # everywhere in this file and carry no threshold meaning on their own.
    interesting = {t for t in thresholds if float(t) not in (0.0, 1.0, 2.0)}
    for value in interesting:
        assert not re.search(rf"[<>]=?\s*{re.escape(value)}\b", body), (
            f"the gate types the threshold {value} — it must read it from {RULES.name}"
        )
    assert "alerting_rules.yml" in body and "slo_serving.md" in body


def test_the_signal_set_comes_from_the_renderer_not_from_a_literal_list():
    """F-035's two documented absences must be derived on both sides. A gate with
    its own hardcoded `{'A-1', ...}` would not notice A-4 acquiring a source, nor
    a signal quietly dropping out."""
    body = without_comments(VERIFY_M6)
    assert "IMPLEMENTED_SIGNALS" in body and "KNOWN_SIGNALS" in body
    assert "render_alert_rules.py" in body
    assert not re.search(r"\{\s*[\"']A-1[\"']\s*,", body), "the gate hardcodes a signal set"


def test_the_prose_precision_floor_is_one_decimal():
    """The defect the red team found on its first run, pinned so it cannot come
    back: allowing a record's number to render at ZERO decimals lets 13.75 match
    the string '14', which appears in almost any document — so the planted 13.501
    passed the prose leg. Gotcha #76 in the rounding direction."""
    body = VERIFY_M6.read_text()
    ranges = re.findall(r"for d in range\((\d+),\s*\d+\)", body)
    assert ranges, "no precision policy found — the test is not looking where the gate looks"
    assert all(int(start) >= 1 for start in ranges), (
        f"a prose-comparison precision policy starts at {ranges} — d=0 rounds 13.75 to '14'"
    )


# ------------------------------------------------------ the legs must have run --
def test_every_python_leg_demands_a_minimum_verdict_count():
    """M2's rule: a leg that dies on import contributes zero silent passes unless
    somebody demanded a positive count. M6's §1 leg in particular talks to four
    workloads and two HTTP services, so it has plenty of ways to die early."""
    body = without_comments(VERIFY_M6)
    legs = body.count("consume < <(")
    expectations = body.count("expect_verdicts ")
    assert legs >= 7, f"only {legs} leg(s) found — the gate lost a section"
    assert expectations >= legs, (
        f"{legs} legs but only {expectations - 1} expect_verdicts call(s) — a leg can die silently"
    )


@pytest.mark.needs_records
def test_the_gate_reads_the_tracked_records_it_names():
    body = VERIFY_M6.read_text()
    for record in (
        "automation/runs/m6-shadow/disagreement.json",
        "automation/runs/m6-canary/release_drill.json",
        "automation/runs/m6-spike/canary_spike.json",
        "automation/runs/m6-rollback/alias_rollback.json",
        "automation/runs/m6-restore/restore_drill.json",
        "automation/runs/m5-parity/parity.json",
        "automation/runs/m3s5/bakeoff.json",
    ):
        assert record in body, f"the gate does not read {record}"
        assert (REPO / record).exists(), f"{record} is named by the gate but does not exist"


@pytest.mark.needs_records
def test_the_records_the_gate_replays_are_tracked_by_git():
    """F-029, closed at M5-S1: a gate replaying evidence that is not in the
    repository is a gate whose inputs review cannot see. `git check-ignore` is a
    two-second command and gotcha #69 is what it prevents."""
    for record in (
        "automation/runs/m6-gameday/predictions.json",
        "automation/runs/m6-gameday/kill.json",
        "automation/runs/m6-canary/release_drill.json",
        "automation/runs/m6-rollback/alias_rollback.json",
        "automation/runs/m6-restore/restore_drill.json",
    ):
        result = subprocess.run(
            ["git", "check-ignore", "-q", record], cwd=REPO, capture_output=True
        )
        assert result.returncode != 0, f"{record} is GITIGNORED but the gate replays it"


# ------------------------------------------------------------ the red team ------
def test_the_red_team_breaks_exactly_one_field_and_restores_it():
    body = REDTEAM.read_text()
    assert 'RECORD="automation/runs/m6-gameday/kill.json"' in body
    assert "trap restore EXIT" in body, "the restore is not guaranteed on an unexpected exit"
    assert "sha256sum" in body, "the restore is asserted rather than verified"
    # The planted value is DERIVED from the record, never typed: a hand-picked
    # number is a fault nobody would ever make, and this one has a history.
    assert "error_window\"][\"span_s\"]" in body or 'error_window"]["span_s"]' in body
    assert "13.75" not in body and "13.501" not in body, "the drill types the numbers it plants"


def test_the_red_team_touches_no_cluster_state():
    """A red team that broke the running service to prove the gate works would be
    the M5-S3 mistake (planting the cause on the cluster instead of in the test).
    Its whole footprint is one tracked JSON file."""
    body = without_comments(REDTEAM)
    for forbidden in ("kubectl", "helm", "docker", "make serve", "make gameday", "mlflow"):
        assert not invokes(body, forbidden), f"the red team runs {forbidden}"
    assert "verify_m6.sh" in body, "the red team does not actually run the gate"


def test_the_red_team_asserts_both_halves():
    """RED for the planted cause AND everything else still counted. A drill that
    only asserted 'the gate went red' would pass for a gate that fails on any
    edit at all."""
    body = REDTEAM.read_text()
    assert "still passed" in body, "the drill does not assert the other sub-checks kept running"
    assert "unaffected leg still green" in body
    assert "git status --porcelain" in body, "a clean drill must leave a clean tree (F-029)"


# ------------------------------------------ the accept-when, as a data contract --
@pytest.mark.needs_records
def test_the_records_the_accept_when_rests_on_say_what_it_needs():
    """§9/M6 accepts on three things. This test does not re-check the gate's
    logic — it pins that the RECORDS still carry the fields those clauses are
    read from, so a future re-run of a drill that drops a field fails here rather
    than silently weakening a sub-check."""
    canary = json.loads((REPO / "automation/runs/m6-canary/release_drill.json").read_text())
    rollback = json.loads((REPO / "automation/runs/m6-rollback/alias_rollback.json").read_text())
    gameday = json.loads((REPO / "automation/runs/m6-gameday/gameday.json").read_text())
    shadow = json.loads((REPO / "automation/runs/m6-shadow/disagreement.json").read_text())

    # "canary 90/10 observed" — observed means a counter, from two witnesses.
    ten = canary["phases"]["canary_10"]
    assert ten["ingress"]["canary_share_pct"] > 0 and ten["pods"]["canary_share_pct"] > 0

    # "rollback <2min under load" — the moves are timed and the route sampled.
    assert rollback["leg_1_rollback"]["seconds"]["all_three_moves"] < 120.0
    assert rollback["leg_1_rollback"]["route"]["sent"] > 0

    # "at least one prediction wrong and investigated".
    assert gameday["accept_bar_met"] is True
    assert gameday["predictions_that_were_wrong"]

    # "a quantified disagreement rate before the first traffic shift".
    assert shadow["overall"]["rows"] > 0
    assert shadow["overall"]["mean_abs_delta_min"] is not None
