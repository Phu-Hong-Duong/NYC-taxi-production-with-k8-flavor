"""M6-S3 — the shadow, the spike, and the prose that quotes their records.

Three families of check, in ascending order of what they are worth:

1. STRUCTURAL — the shadow path is a reader, the deploy waits in the right order,
   the probe cleans up. Parsed with `ast` and not grepped, because every file
   here argues its own design at length and a word search greps the argument
   (gotchas #53/#68, both of which cost this repo a red test for the wrong
   reason).
2. DERIVED-ON-BOTH-SIDES — no literal that is a fact about today (a version, a
   measured number) is typed into an assertion. F-017 / gotchas #49/#50.
3. PROSE AGAINST RECORDS — every number ADR-011 and the DA memo quote must exist
   in the record they cite. The M5-S5 shape: a document that quotes a number no
   record holds is how a runbook becomes fiction, and it is the half of the M5
   gate that its red team could not walk around.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SHADOW_MODULE = REPO / "src/taxi_mlops/serving/shadow.py"
DEPLOY_SHADOW = REPO / "scripts/deploy_shadow.sh"
SPIKE_PROBE = REPO / "scripts/canary_spike_probe.py"
SHADOW_MANIFEST = REPO / "infra/manifests/inferenceservice-shadow-v1.yaml"
ADR = REPO / "docs/decisions/ADR-011-canary-and-shadow-mechanism.md"
MEMO = REPO / "docs/shadow_analysis_m6.md"
SPIKE_RECORD = REPO / "automation/runs/m6-spike/canary_spike.json"
SHADOW_RECORD = REPO / "automation/runs/m6-shadow/disagreement.json"


def _calls(path: Path) -> set[str]:
    """Every callable NAME invoked in a file, however it is spelled.

    `foo()`, `a.b.foo()` and `a.foo()` all contribute `foo`, so a ban survives an
    import being renamed — and, unlike a grep, prose naming the same verb does not
    trip it.
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


# --------------------------------------------------------------- structural --

#: Every MLflow verb that changes registry state. The shadow path may read the
#: registry all it likes; M6 law 3 says nothing promotes, and a shadow that could
#: move an alias would be a promotion with extra steps.
MUTATING_REGISTRY_VERBS = {
    "set_registered_model_alias",
    "delete_registered_model_alias",
    "create_model_version",
    "create_registered_model",
    "delete_model_version",
    "delete_registered_model",
    "transition_model_version_stage",
    "set_model_version_tag",
    "register_model",
    "log_model",
    "promote",
}


def test_the_shadow_run_is_a_reader() -> None:
    offenders = _calls(SHADOW_MODULE) & MUTATING_REGISTRY_VERBS
    assert not offenders, (
        f"{SHADOW_MODULE.name} calls {sorted(offenders)}. The shadow run measures; "
        "it does not mint, tag or point anything."
    )


def test_the_shadow_run_deploys_nothing() -> None:
    """It must not be able to change the cluster it is measuring.

    Asserted on the IMPORTS rather than on call names. The first draft banned the
    call name `run` and went red on `shadow.run()` — the module's own entry point.
    A ban keyed on a bare name cannot tell a subprocess from a local function, and
    a test that fires on correct code teaches the next session to edit assertions
    (gotcha #50, the lesson this repo keeps re-learning).
    """
    forbidden = {"subprocess", "os", "shutil"}
    imported: set[str] = set()
    for node in ast.walk(ast.parse(SHADOW_MODULE.read_text())):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    offenders = imported & forbidden
    assert not offenders, (
        f"{SHADOW_MODULE.name} imports {sorted(offenders)}. A reader that can apply a "
        "manifest is a deploy script with a modest docstring."
    )


def test_the_shadow_builds_each_target_through_the_one_feature_path() -> None:
    """The whole construction rests on this: one raw request, two matrices, one builder."""
    source = SHADOW_MODULE.read_text()
    tree = ast.parse(source)
    calls = _calls(SHADOW_MODULE)
    assert "build_matrix" in calls, (
        "the shadow must build its matrices with taxi_mlops.serving.client.build_matrix — "
        "a second builder makes every delta ambiguous between 'the models disagree' "
        "and 'the clients disagree'."
    )
    # And it must resolve BOTH feature sets by name rather than hardcoding columns.
    resolved = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "resolve_set"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    }
    assert {"v1", "v2"} <= resolved, (
        f"the shadow resolves {sorted(resolved)}; it must resolve both targets' sets "
        "through the registry (configs/features.yaml), never a column list."
    )


def test_the_spike_probe_cleans_up_in_a_finally_block() -> None:
    """A probe that leaves a canary behind on failure has changed the wire."""
    tree = ast.parse(SPIKE_PROBE.read_text())
    tries = [node for node in ast.walk(tree) if isinstance(node, ast.Try) and node.finalbody]
    assert tries, "the spike probe must clean up under a finally block, not on the happy path"
    cleaned = any(
        isinstance(inner, ast.Call)
        and isinstance(inner.func, ast.Name)
        and inner.func.id == "cleanup"
        for node in tries
        for statement in node.finalbody
        for inner in ast.walk(statement)
    )
    assert cleaned, "the finally block must call cleanup() — the canary must not outlive a crash"


def test_the_spike_probe_never_annotates_an_inferenceservice() -> None:
    """F-038, and it cost a real outage.

    The first run forced a reconcile with `kubectl annotate isvc`, believing it
    spec-neutral. KServe propagates an InferenceService's annotations onto its pod
    template, so it rolled the champion's only predictor — twice — and the
    end-state batch measured 174 of 200 requests returning 502.
    """
    source = SPIKE_PROBE.read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != "kubectl":
            continue
        args = [a.value for a in node.args if isinstance(a, ast.Constant)]
        if "annotate" in args:
            assert not ({"isvc", "inferenceservice"} & set(args)), (
                "the spike probe annotates an InferenceService. KServe propagates isvc "
                "annotations onto the pod template, so that is a Deployment roll and a "
                "real outage of the only replica (F-038)."
            )


# ------------------------------------------------------- the deploy's shape --


def test_the_shadow_deploy_waits_on_the_rollout_before_the_condition() -> None:
    """gotchas #71 and #79, inherited from the champion's deploy.

    The ORDER is asserted, never the flag text — M6-S2 re-pinned the champion's
    equivalent test for exactly this reason (gotcha #50, fourth time).
    """
    text = DEPLOY_SHADOW.read_text()
    rollout = text.index("rollout status")
    condition = text.index("--for=jsonpath=")
    assert rollout < condition, (
        "`rollout status` must come FIRST: the InferenceService's Ready condition is "
        "satisfiable by the pod being replaced, and rollout status is the leg that is not."
    )
    assert "--for=condition=Ready" not in text, (
        "F-036: `--for=condition=` is unsatisfiable while KServe leaves observedGeneration "
        "behind, which it does on every re-deploy."
    )


def test_the_shadow_deploy_waits_on_the_route_too() -> None:
    """F-037 — the wait that neither of the other two covers."""
    text = DEPLOY_SHADOW.read_text()
    assert "/ready" in text and "F-037" in text, (
        "the deploy must wait for the ROUTE by asking it. Both pod-level waits can pass "
        "while nginx has not yet loaded the generated Ingress, and the accept check then "
        "gets a bare 404 over a perfectly good service."
    )


def test_the_shadow_deploy_refuses_a_version_with_no_feature_set_tag() -> None:
    text = DEPLOY_SHADOW.read_text()
    assert "carries no feature_set tag" in text and "exit 2" in text, (
        "an untagged version must be REFUSED, not defaulted: guessing which matrix a "
        "model eats produces a confident wrong number when the guess happens to fit."
    )


def test_the_shadow_deploy_reads_the_alias_before_and_after() -> None:
    text = DEPLOY_SHADOW.read_text()
    assert text.count("champion_version") >= 3, (
        "the alias must be read before AND after every mutation, with a difference "
        "treated as a failure (M6 law 3)."
    )
    assert "ALIAS_BEFORE" in text and "ALIAS_AFTER" in text


def test_the_shadow_manifest_carries_no_resolved_storage_uri() -> None:
    """What serves is a registry pointer; a committed S3 path is a second address."""
    text = SHADOW_MANIFEST.read_text()
    assert "RESOLVED-AT-DEPLOY-TIME-FROM-THE-SHADOW-VERSION" in text
    assert "s3://" not in text, (
        "the shadow manifest names an S3 path. It must be resolved at deploy time — a "
        "committed path is a claim about today that nothing keeps in step."
    )


# ------------------------------------------ prose against records (M5-S5's) --


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:\.\d+)?", text))


@pytest.mark.skipif(not SPIKE_RECORD.exists(), reason="the spike has not been run here")
def test_adr_011_quotes_the_spike_record() -> None:
    """Every load-bearing claim in the ADR must be true of the record it cites."""
    record = json.loads(SPIKE_RECORD.read_text())
    text = ADR.read_text()
    phases = record["phases"]

    assert record["verdict"] == "PASS", "the ADR is written over a passing spike"

    # Condition 1: the shared-Service canary moved nothing; the dedicated one split.
    shared = phases["p1_shared_service"]["batch"]
    dedicated = phases["p2_dedicated_service"]["batch"]
    assert shared["left_the_champion_pct"] == 0.0
    moved = dedicated["sent"] - dedicated["by_status"]["200"]
    assert f"**{moved} of {dedicated['sent']}**" in text, (
        f"the ADR must quote the measured split ({moved} of {dedicated['sent']}) — "
        "the table's numbers are the whole reason condition 1 is a condition."
    )
    assert f"**0 of {shared['sent']}**" in text

    # Condition 1's mechanism, quoted from the record rather than remembered.
    tsp = phases["p2_dedicated_service"]["canary_trafficShapingPolicy"]
    assert f"weight: {tsp['weight']}, weightTotal: {tsp['weightTotal']}" in text
    assert phases["p2_dedicated_service"]["canary_noServer"] is True

    # Condition 2: rewrite-target changed nothing.
    rewritten = phases["p3_rewrite_target"]["batch"]
    assert abs(
        rewritten["left_the_champion_pct"] - dedicated["left_the_champion_pct"]
    ) <= 10.0, "the ADR claims rewrite-target changed the share by 0 points"
    assert "**0 points**" in text

    # The mirror finding must match what was observed, in BOTH halves.
    mirror = phases["p4_mirror_target"]
    claims_it_works = "gained a real `mirror` directive" in text
    assert claims_it_works == (
        mirror["annotation_survived_on_the_object"] and mirror["nginx_conf_has_a_mirror_directive"]
    ), "the ADR's mirror claim disagrees with the record's two mirror observations"


@pytest.mark.skipif(not SHADOW_RECORD.exists(), reason="the shadow has not been run here")
def test_the_memo_quotes_the_disagreement_record() -> None:
    record = json.loads(SHADOW_RECORD.read_text())
    text = MEMO.read_text()
    quoted = _numbers(text)

    for segment, stats in record["by_segment"].items():
        assert str(stats["rows"]) in quoted, f"the memo does not state {segment}'s row count"
        for key in ("mean_abs_delta_min", "max_abs_delta_min"):
            value = f"{stats[key]:.2f}"
            assert value in text, f"the memo omits {segment}.{key} = {value}"

    overall = record["overall"]
    assert f"{overall['champion_mae_min']:.2f}" in text
    assert f"{overall['shadow_mae_min']:.2f}" in text
    assert str(overall["rows"]) in quoted


@pytest.mark.skipif(not SHADOW_RECORD.exists(), reason="the shadow has not been run here")
def test_the_memo_carries_a_named_verdict_and_does_not_claim_a_bakeoff() -> None:
    text = MEMO.read_text()
    assert "NO-GO" in text, "the kickoff requires a NAMED verdict as input to S4's go/no-go"
    assert "not a re-run of the m3 bake-off" in text.lower().replace("**", ""), (
        "a stratified sample scored on the wire must say it is not the measurement of "
        "record — gotcha #15's discipline (a number from a sample is labelled as one)."
    )
    record = json.loads(SHADOW_RECORD.read_text())
    assert record["overall"]["champion_mae_min"] > 3.2403, (
        "sanity: the stratified sample over-weights hard segments, so its MAE must be "
        "well above the full holdout's. If it is not, the sample is not stratified."
    )


@pytest.mark.skipif(not SHADOW_RECORD.exists(), reason="the shadow has not been run here")
def test_the_served_versions_were_read_off_the_answers() -> None:
    record = json.loads(SHADOW_RECORD.read_text())
    assert record["served_versions"] == {"champion": "2", "shadow": "1"}, (
        "the record must carry the versions the ENDPOINTS stamped on their own "
        "responses — which model produced this number travels with the number."
    )


def test_adr_011_records_the_deferred_admission_webhook_with_its_cost() -> None:
    """The values file's own note came due this story; deferring it must be argued."""
    text = ADR.read_text()
    assert "admission webhook" in text and "M6-S4" in text, (
        "ADR-011 must record that the hand-written Ingress made the ingress-nginx "
        "admission webhook's own re-enable trigger live, where it was routed, and why."
    )
