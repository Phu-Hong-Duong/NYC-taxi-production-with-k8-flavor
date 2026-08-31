"""The SLO document, the alert rules, and the drill that fires them — M6-S2.

WHAT THESE TESTS ARE FOR. M6-S2 is the story where this program starts owning
NUMBERS: an SLO target, six alert thresholds, and a CPU request. Numbers are the
easiest artefact in a repo to drift, because changing one is a one-character diff
that no compiler and no runtime objects to. So the properties asserted here are
mostly about the numbers' *arguments* still existing beside them, and about the
several places that must agree not being allowed to disagree quietly:

  * a rules file and a values file that could both hold rules (the twin problem
    this program has hit with port pairs, the mart list and `.dockerignore`);
  * a rules file and a script that claims which signals are implementable;
  * a rules file and the drill that predicts which of its rules fire;
  * a rules file and the SLO document that owns its thresholds' reasoning;
  * a manifest's CPU request and the document that argued the value.

Every check parses code or YAML rather than grepping prose. These files argue
their own design at length, so a word-search hits the argument as often as the
code — gotchas #35/#53/#60/#68, five stories running.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
RULES = REPO / "infra" / "monitoring" / "alerting_rules.yml"
RENDERER = REPO / "scripts" / "render_alert_rules.py"
DRILL = REPO / "scripts" / "alert_fire_drill.py"
#: M7-S3's drill. There are two from here on, and the coverage test takes their
#: union — see `test_the_drill_watches_every_rule_in_the_file`.
DRIFT_DRILL = REPO / "scripts" / "drift_fire_drill.py"
#: M8-S1's drill (F-050's pair). Three from here on, same union.
PERSISTENCE_DRILL = REPO / "scripts" / "drift_persistence_drill.py"
#: M9-S2's drill (the online store's pair, A-12/A-13). Four.
STORE_DRILL = REPO / "scripts" / "store_watch_drill.py"

#: Every drill that carries a literal PREDICTION, and therefore every drill whose
#: prediction the coverage test may take the union of. Named explicitly rather
#: than globbed: a glob would silently accept a drill that LOST its prediction,
#: which is the failure this list exists to make loud.
ALERT_DRILLS = (DRILL, DRIFT_DRILL, PERSISTENCE_DRILL, STORE_DRILL)
DEPLOY = REPO / "scripts" / "deploy_monitoring.sh"
PROM_VALUES = REPO / "infra" / "helm" / "monitoring" / "prometheus-values.yaml"
SLO_DOC = REPO / "docs" / "slo_serving.md"
ISVC = REPO / "infra" / "manifests" / "inferenceservice-champion.yaml"
MAKEFILE = REPO / "Makefile"

pytestmark = pytest.mark.unit

# The value M6-S2 argued and applied. It appears here ONCE; every other assertion
# reads it from the manifest or the document, so this is the single place a future
# change has to come through.
CPU_REQUEST = "1500m"


def executable_lines(text: str) -> str:
    """Everything a shell would execute, comments AND blank lines removed.

    Deliberately NOT `conftest.without_comments`, and the name now says so. This
    one also drops blank lines, so it is a different function that happened to
    share a name with `test_task_image`'s copy — the same one-name-two-meanings
    shape the `_calls()` split was about (CU-S2). Kept local and renamed rather
    than merged: unifying it would have changed what one of the two callers sees.
    """
    return "\n".join(
        line
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


@pytest.fixture(scope="module")
def rules() -> dict:
    return yaml.safe_load(RULES.read_text())


@pytest.fixture(scope="module")
def all_rules(rules) -> list[dict]:
    return [rule for group in rules["groups"] for rule in group["rules"]]


@pytest.fixture(scope="module")
def slo_text() -> str:
    return SLO_DOC.read_text()


@pytest.fixture(scope="module")
def renderer_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("render_alert_rules", RENDERER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- the rules file itself -----------------------------------------------------


def test_the_shipped_rules_file_is_shippable(renderer_module, rules):
    """The validator that runs at deploy time must pass on what is committed."""
    names = renderer_module.validate(rules)
    assert len(names) == len(set(names)), "two rules share a name"
    assert names, "no rules"


def test_every_rule_carries_the_argument_for_its_own_threshold(all_rules):
    """A number with no reasoning beside it is a number nobody can review.

    The M6 kickoff legislates HOW thresholds must be argued; this is the
    mechanical half of that — the argument has to be in the file, and it has to
    point at the document that owns it."""
    for rule in all_rules:
        why = rule["annotations"]["why"]
        assert "slo_serving.md" in why, (
            f"{rule['alert']}'s `why` does not cite the SLO document, so its number is "
            "argued nowhere a reviewer would look"
        )


def test_every_rule_with_a_sustain_window_explains_the_window(all_rules):
    """`for: 5m` vs `for: 2m` vs `for: 0m` is a judgement, not a default.

    The prior-art ADOPT is sustained conditions; the exceptions are where sustain
    is WRONG (a flap counter already carries its own window). Either way the
    choice is a decision and has to be written down."""
    for rule in all_rules:
        window = rule.get("for", "0m")
        if window != "5m":
            assert "sustain" in rule["annotations"], (
                f"{rule['alert']} uses for={window}, which is not the ADOPTed 5m default, "
                "and does not say why"
            )


def test_no_rule_hides_a_second_threshold_in_a_label(all_rules):
    """A threshold belongs in the expression, where Prometheus evaluates it."""
    for rule in all_rules:
        for key, value in (rule.get("labels") or {}).items():
            assert not re.fullmatch(r"[0-9.]+", str(value)), (
                f"{rule['alert']} carries a bare number in label {key!r}"
            )


# --- the twin guards -----------------------------------------------------------


def test_the_values_file_holds_no_rules_because_the_rules_file_does(prom_values_map=None):
    """ONE copy of the rules. The chart's key stays empty on purpose.

    Two files that can both hold rules fail the same way every time: one is
    edited and the other is the one that runs."""
    values = yaml.safe_load(PROM_VALUES.read_text())
    embedded = values["serverFiles"]["alerting_rules.yml"]
    assert embedded == {}, (
        "prometheus-values.yaml has grown its own copy of the alert rules. The rules live "
        f"in {RULES.relative_to(REPO)} and are nested in by scripts/render_alert_rules.py; "
        "two copies is the twin problem."
    )


def test_the_deploy_provisions_the_rules_file_and_validates_it_first():
    """The rules reach the cluster from git, and a malformed file fails early."""
    body = executable_lines(DEPLOY.read_text())
    # The invocation is a quoted absolute path, so the flag does not sit adjacent
    # to the script name in the text — match the two together rather than as one
    # literal (gotcha #68's tokenisation lesson, on a test this time).
    assert re.search(r'render_alert_rules\.py"?\s+--check', body), (
        "the deploy does not validate the rules before installing them, so a malformed "
        "rules file would be a successful helm upgrade over a Prometheus with no rules"
    )
    assert body.count("--values") >= 2, "the rules overlay is not passed to helm"
    assert 'rm -f "$RULES_OVERLAY"' in body, "the generated overlay is not cleaned up"


def test_the_implemented_signal_set_and_the_documented_absences_agree(renderer_module, slo_text):
    """F-035, made checkable from both sides.

    Two of the PRR's seven signals have no metric source in this stack. That is a
    documented absence, not an omission — so the script's set and the document's
    prose must name the same gaps, and adding a rule for one without saying so
    fails here."""
    absent = renderer_module.KNOWN_SIGNALS - renderer_module.IMPLEMENTED_SIGNALS

    # M7-S3 REWROTE THIS ASSERTION, AND THE REASON IS GOTCHA #50 FOR THE FIFTH
    # TIME. It used to read `assert "A-4" in absent` — an M6-era FACT encoded as
    # a literal — so the moment F-035 was legitimately CLOSED by giving A-3's
    # client half and A-4 real metric sources, this guard went red for the
    # program doing exactly the right thing. A guard that fires when the
    # behaviour improves teaches the next session to edit assertions.
    #
    # The PROPERTY that holds at every state is coherence, in both directions:
    # whatever the renderer calls an absence must be explained in §6, and
    # whatever §6 explains must actually be absent from the rules.
    assert absent == renderer_module.DOCUMENTED_ABSENCES, (
        "render_alert_rules.py's two sets disagree with each other"
    )
    assert "F-035" in slo_text, "the SLO document does not carry the finding for the gaps"
    for signal in sorted(absent):
        assert signal in slo_text, f"{signal} is absent from the rules and unexplained in §6"
    # §6 must state each gap's LANDING, not merely the gap — and when there are
    # no gaps left it must say how they were closed rather than going silent.
    assert "pushgateway" in slo_text, (
        "§6 must name where the absences land (M7's pushgateway) — or, once they have "
        "landed, what closed them"
    )
    if not absent:
        assert "CLOSED at M7-S3" in slo_text, (
            "the renderer claims no signal is absent, but §6 does not record the closure. "
            "An empty absence list is a claim and needs its evidence in the document."
        )


def test_the_slo_document_names_every_implemented_alert(all_rules, slo_text):
    """The prose and the rules are checked against each other, not each alone."""
    for rule in all_rules:
        assert rule["alert"] in slo_text, (
            f"{rule['alert']} exists as a rule and is named nowhere in the SLO document"
        )


def test_every_prr_signal_is_dispositioned_in_the_document(renderer_module, slo_text):
    for signal in sorted(renderer_module.KNOWN_SIGNALS):
        assert signal in slo_text, f"{signal} is not dispositioned in the SLO document"


# --- the latency rule's peculiar shape ----------------------------------------


def test_the_latency_rule_counts_buckets_and_never_interpolates(all_rules):
    """§2.1: this stack's histogram cannot measure this service's p95.

    Measured — the client's whole-round-trip p95 (84.4 ms) came in BELOW
    `histogram_quantile`'s estimate over the same window (111.6 ms), which is
    impossible for a real measurement and is explained by a 150 ms-wide bucket.
    So the SLO's number is a bucket EDGE and the rule counts. A future edit back
    to `histogram_quantile` would look tidier and would measure nothing."""
    latency = [r for r in all_rules if r["labels"]["signal"] == "A-1"]
    assert len(latency) == 1
    expr = latency[0]["expr"]
    assert "histogram_quantile" not in expr, (
        "A-1 has gone back to histogram_quantile. At mlserver's default bucket resolution "
        "that is an interpolation across a 150 ms bucket, not a measurement — see "
        "docs/slo_serving.md §2.1"
    )
    assert 'le="0.25"' in expr, "A-1 no longer measures against a bucket EDGE"
    assert 'status_code="200"' in expr, (
        "A-1 must select successful requests only; a rejected request is not a slow one, "
        "and mixing them lets a burst of fast 4xx mask a latency regression"
    )


def test_the_error_rate_rule_is_measured_at_the_edge(all_rules):
    """When the predictor dies its exporter dies with it.

    An error-rate alert written against mlserver's own counters cannot fire for
    the outage that matters most — the series does not go to zero, it stops
    existing. ingress-nginx is a different process on a different node."""
    edge = [r for r in all_rules if r["labels"]["signal"] == "A-2"]
    assert len(edge) == 1
    expr = edge[0]["expr"]
    assert "nginx_ingress_controller_requests" in expr, (
        "A-2 no longer reads the edge. A 5xx rate measured on the predictor's own /metrics "
        "is blind to the predictor being gone."
    )
    assert "rest_server" not in expr


def test_something_can_fire_without_any_traffic_at_all(all_rules):
    """A-2's blind spot has to be covered by something, and it is A-5.

    Every ratio-shaped rule is blind on an idle service: 0/0 produces no series
    and no series produces no alert. So at least one rule must read a state
    rather than a rate."""
    stateful = [
        r
        for r in all_rules
        if "kube_deployment_status_replicas_available" in r["expr"]
        or "kube_pod_init_container_status_ready" in r["expr"]
    ]
    assert stateful, (
        "every rule is a rate or a ratio, so an idle broken service raises nothing at all"
    )


# --- the drill -----------------------------------------------------------------


def _alerts_named(node: object) -> set[str]:
    """Every value filed under an `alert` key, at any depth of a prediction."""
    found: set[str] = set()
    if isinstance(node, dict):
        value = node.get("alert")
        if isinstance(value, str):
            found.add(value)
        for child in node.values():
            found |= _alerts_named(child)
    elif isinstance(node, list):
        for child in node:
            found |= _alerts_named(child)
    return found


def test_the_drill_watches_every_rule_in_the_file(all_rules):
    """A new rule forces a decision: does the drill expect it to fire or not?

    The drill's prediction is the both-sides check for the rules file. If a rule
    could be added without appearing in either list, the drill would silently
    stop covering it — which is how a positive control becomes a formality."""
    # THE UNION OF THE DRILLS, because there are four of them from M9-S2 on.
    #
    # The property worth keeping is "no rule has fallen out of every drill's
    # sight", and that was the same as "this drill watches every rule" only
    # while one drill existed. The serving injection drill cannot sensibly
    # predict a drift rule's behaviour (it pushes no drift metric and its
    # 422/500 injection cannot move one), and the drift drill has no business
    # predicting the storage-initializer alert. Demanding either cover the
    # other's rules would push a session toward padding a prediction list with
    # entries nobody reasoned about — which is how a positive control becomes a
    # formality by a different route than the one this test was written for.
    #
    # THE COLLECTION IS DERIVED, NOT KEY-PATHED. Until M9-S2 this test walked
    # each drill's prediction along its own hand-written key path
    # (`["must_fire"]`, `["absence"]["must_not_fire"]`, …), so every new drill
    # cost a bespoke block here and a drill that restructured its prediction
    # would have gone silently uncounted. It now collects every value filed
    # under an `alert` key at any depth — the same property, asked in a way that
    # does not need editing when a fourth drill shapes its prediction its own
    # way.
    watched: set[str] = set()
    for path in ALERT_DRILLS:
        found = False
        for node in ast.walk(ast.parse(path.read_text())):
            target = None
            if isinstance(node, ast.AnnAssign):
                target = getattr(node.target, "id", None)
            elif isinstance(node, ast.Assign):
                target = next(
                    (getattr(t, "id", None) for t in node.targets if getattr(t, "id", None)), None
                )
            if target == "PREDICTION":
                watched |= _alerts_named(ast.literal_eval(node.value))
                found = True
        assert found, f"{path.name} has no literal PREDICTION to review"

    declared = {rule["alert"] for rule in all_rules}
    assert watched >= declared, (
        f"the {len(ALERT_DRILLS)} drills between them watch {sorted(watched)} but the rules file "
        f"declares {sorted(declared)}; {sorted(declared - watched)} is covered by neither. Every "
        "rule must be predicted to fire or predicted not to by SOME drill — an unlisted rule is a "
        "rule that has stopped being exercised."
    )


def test_the_drill_predicts_an_order_and_a_negative(all_rules):
    """A drill that predicts only 'something fires' cannot be wrong."""
    source = DRILL.read_text()
    tree = ast.parse(source)
    prediction = next(
        ast.literal_eval(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(getattr(t, "id", None) == "PREDICTION" for t in node.targets)
    )
    assert len(prediction["must_fire"]) >= 2, "no order can be predicted from one alert"
    assert prediction["must_fire_in_this_order"] == [
        e["alert"] for e in prediction["must_fire"]
    ]
    assert prediction["must_not_fire"], "no negative prediction — nothing is distinguishable"
    for entry in prediction["must_fire"] + prediction["must_not_fire"]:
        assert entry.get("why"), f"{entry['alert']} is predicted without a reason"


def test_the_drill_mutates_no_serving_state():
    """It provokes errors. It does not delete, scale, patch or promote.

    Parsed, not grepped: the module explains at length what it deliberately does
    NOT do, and a word-search would hit that explanation (gotcha #53)."""
    tree = ast.parse(DRILL.read_text())
    forbidden = {"delete", "scale", "patch", "apply", "rollout", "annotate", "edit"}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value in forbidden
        ):
            pytest.fail(f"the drill passes the kubectl verb {node.value!r} somewhere")
        if isinstance(node, ast.Attribute) and node.attr in {
            "set_registered_model_alias",
            "delete_registered_model_alias",
            "create_model_version",
            "transition_model_version_stage",
        }:
            pytest.fail(f"the drill calls the registry-mutating {node.attr}")
    # The only kubectl it may run is a read-only port-forward.
    kubectl_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.List)
        and node.elts
        and isinstance(node.elts[0], ast.Constant)
        and node.elts[0].value == "kubectl"
    ]
    for call in kubectl_calls:
        verbs = [e.value for e in call.elts if isinstance(e, ast.Constant)]
        assert "port-forward" in verbs, f"a kubectl call that is not a port-forward: {verbs}"


def test_the_drill_writes_its_prediction_before_it_injects():
    """The M4-S5 / M5-S4 discipline: on disk first, or it is a rationalisation."""
    tree = ast.parse(DRILL.read_text())
    main = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    lines_writing_prediction = [
        node.lineno
        for node in ast.walk(main)
        if isinstance(node, ast.Attribute) and node.attr == "write_text"
    ]
    lines_starting_injection = [
        node.lineno
        for node in ast.walk(main)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "start"
    ]
    assert lines_writing_prediction and lines_starting_injection
    assert min(lines_writing_prediction) < min(lines_starting_injection), (
        "the injection starts before the prediction is written to disk"
    )


def test_the_drill_checks_the_service_stayed_up():
    """It claims 'errors, not an outage'. A claim nobody checked is a claim."""
    source = DRILL.read_text()
    assert "quote_during_injection" in source
    assert "taxi_mlops.serving" in source, (
        "the drill never asks for an ordinary quote during the injection, so its "
        "'the service stays up' claim is unverified (gotcha #59)"
    )


# --- the CPU request -----------------------------------------------------------


def test_the_cpu_request_is_the_argued_value_and_stays_burstable():
    """M5 measured 1.31 cores against a 200m request — a ~6.5x under-reservation.

    The request is what the SCHEDULER reserves and what sets the container's CPU
    weight; it is not a cap. It is deliberately below the limit: setting it equal
    would make the pod Guaranteed and reserve the whole ceiling for load the SLO
    does not promise to serve."""
    document = yaml.safe_load(ISVC.read_text())
    resources = document["spec"]["predictor"]["model"]["resources"]
    assert resources["requests"]["cpu"] == CPU_REQUEST, (
        f"the CPU request is {resources['requests']['cpu']}, not the argued {CPU_REQUEST}"
    )
    assert resources["limits"]["cpu"] == "2", "the limit moved; M6-S2 changed the request only"
    request_cores = int(CPU_REQUEST.rstrip("m")) / 1000
    assert request_cores < float(resources["limits"]["cpu"]), (
        "request == limit makes the pod Guaranteed and reserves the saturation ceiling"
    )
    assert resources["requests"]["memory"] == "1Gi", (
        "the memory request moved too. M6-S2 changed ONE thing so the before/after p95 "
        "comparison attributes to one cause."
    )


def test_the_cpu_request_change_is_argued_where_the_numbers_live(slo_text):
    assert CPU_REQUEST in slo_text or "1.5" in slo_text, (
        "the CPU request value is not argued in the SLO document"
    )
    assert "200m" in slo_text, "the value it replaced is not recorded"
    assert "not expected to move" in slo_text or "should not move" in slo_text, (
        "§7 does not state the prediction the before/after measurement tests"
    )


# --- the targets ---------------------------------------------------------------


def test_the_make_targets_exist_and_the_validator_is_separable():
    body = MAKEFILE.read_text()
    for target in ("alert-rules:", "alert-fire-drill:"):
        assert target in body, f"no `make {target[:-1]}`"
    assert "render_alert_rules.py --check" in body


def test_the_slo_document_states_the_load_shape_with_every_latency_number(slo_text):
    """A percentile without its arrival rate is not comparable to itself (M5-S4)."""
    assert "4 req/s" in slo_text
    assert "concurrency 8" in slo_text
    assert "hazard mix" in slo_text


def test_the_slo_document_prices_in_what_a_deploy_costs(slo_text):
    """An availability target that forbids deploying is violated by design."""
    for measured in ("14.53", "15.0", "18.24"):
        assert measured in slo_text, (
            f"the measured outage {measured}s is not priced into the availability argument"
        )
