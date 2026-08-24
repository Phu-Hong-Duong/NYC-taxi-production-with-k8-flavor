"""The laws M9-S2's watchdog lives under, asked of the AST and of the files themselves.

Three families, and none of them can be satisfied by the drill passing:

  * **the prediction is committed and unamended** — the M6-S5 gameday discipline,
    fourth inheritance. A prediction that can be edited into agreement with its
    own outcome is not a prediction.
  * **the two sides are derived from each other** — the metric names, the job
    label and the canary's subjects appear in the rules file and in the module,
    and a test compares them rather than a human remembering to. F-017.
  * **the reader and the drill stay inside their refusals** — no registry verb,
    no alias, no fit, and (for the reader) no mutation of the store it watches.

Everything structural is asked of `ast`, never grepped: these modules argue their
own design at length and a word search matches the argument (gotchas #53/#68/#99).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
MODULE = REPO / "src" / "taxi_mlops" / "monitoring" / "store_health.py"
READER = REPO / "scripts" / "store_watch.py"
HEADROOM = REPO / "scripts" / "store_watch_headroom.py"
DRILL = REPO / "scripts" / "store_watch_drill.py"
RULES = REPO / "infra" / "monitoring" / "alerting_rules.yml"
SLO_DOC = REPO / "docs" / "slo_serving.md"
PREDICTION_FILE = REPO / "automation" / "runs" / "m9-store-watch" / "prediction.json"
MAKEFILE = REPO / "Makefile"

pytestmark = pytest.mark.unit


def _literal(path: Path, name: str) -> object:
    for node in ast.walk(ast.parse(path.read_text())):
        target = None
        if isinstance(node, ast.AnnAssign):
            target = getattr(node.target, "id", None)
        elif isinstance(node, ast.Assign):
            target = next(
                (getattr(t, "id", None) for t in node.targets if getattr(t, "id", None)), None
            )
        if target == name:
            return ast.literal_eval(node.value)
    raise AssertionError(f"{path.name} has no literal {name}")


def _store_rules() -> list[dict]:
    doc = yaml.safe_load(RULES.read_text())
    return [
        r
        for g in doc["groups"]
        for r in g["rules"]
        if r.get("labels", {}).get("signal") in ("A-12", "A-13")
    ]


def _calls(path: Path) -> set[str]:
    """Every called NAME and attribute — an invocation, never a mention."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


# --- the prediction --------------------------------------------------------------


@pytest.mark.needs_records
def test_the_committed_prediction_still_equals_the_drill_s_own() -> None:
    """Amending a prediction to match an outcome must be a RED test, not a quiet diff."""
    assert PREDICTION_FILE.exists(), (
        f"{PREDICTION_FILE.relative_to(REPO)} is missing — the drill writes it before its "
        "first mutation and it is committed, so its absence means the record of what was "
        "expected is gone."
    )
    assert json.loads(PREDICTION_FILE.read_text()) == _literal(DRILL, "PREDICTION")


def test_the_prediction_carries_negatives_and_they_are_the_load_bearing_half() -> None:
    prediction = _literal(DRILL, "PREDICTION")
    assert prediction["empty_store"]["must_not_fire"], (
        "a drill that predicts only 'something fires' cannot be wrong"
    )
    # The one that justifies A-13 existing at all: A-12 must be predicted SILENT
    # through a deleted surface. If that negative were dropped, the drill would
    # pass just as happily against a stack in which A-13 were redundant.
    assert prediction["deleted_surface"]["must_not_fire"]["alert"] == "OnlineStoreCanaryFailing"


def test_the_prediction_records_the_expectation_it_supersedes() -> None:
    """This one number has had three states and all three stay on the record.

    The M9 kickoff expected 503; the 2026-08-23 drill predicted and MEASURED 422,
    which is F-062 itself; M9-S7 landed the PO's answer (b) and it is 503 again.
    Keeping the superseded expectation beside the new one is the `error_memo_m2`
    §9 precedent: a prediction that silently replaces an earlier one cannot be
    compared against the decision that was made from it — and here the superseded
    one is the finding's own evidence.
    """
    rider = _literal(DRILL, "PREDICTION")["empty_store"]["rider_request"]
    assert "supersedes" in rider and "422" in rider["supersedes"]
    assert "attempt1-422-era" in rider["supersedes"], (
        "the superseded RECORDS have to be findable, not just the sentence"
    )
    assert rider["expected_status"] == 503


def test_f019_s_guarantee_is_predicted_in_BOTH_store_states() -> None:
    """The regression F-062's discriminator could have caused, pinned as a claim.

    An uncovered date must stay the CALLER's 422 while the store answers, and
    become OURS the moment it does not. A drill that only predicted the empty
    case would pass against a deployment that had stopped refusing past-horizon
    dates altogether.
    """
    spec = _literal(DRILL, "PREDICTION")["empty_store"]["uncovered_date_survives"]
    assert spec["expected_status_when_healthy"] == 422
    assert spec["expected_status_while_empty"] == 503


# --- both sides derived ----------------------------------------------------------


def test_every_metric_the_rules_read_is_one_the_module_declares() -> None:
    """F-017: a metric name renamed on one side must not be a rule that matches nothing.

    A selector nobody satisfies does not error — it sits `inactive` forever and is
    indistinguishable from a healthy system (gotcha #92, measured on this stack).
    """
    declared = {
        _literal(MODULE, name)
        for name in ("KEYS_METRIC", "KEYS_EXPECTED_METRIC", "CANARY_METRIC", "FRESHNESS_METRIC")
    }
    used = set()
    for rule in _store_rules():
        for token in rule["expr"].replace("(", " ").replace("{", " ").split():
            if token.startswith("taxi_online_store"):
                used.add(token)
    assert used, "no store rule reads a taxi_online_store_* series"
    assert used <= declared, f"rules read {sorted(used - declared)}, which the module declares no"


def test_every_store_rule_selects_the_job_the_reader_pushes_under() -> None:
    job = _literal(MODULE, "PUSH_JOB")
    for rule in _store_rules():
        assert f'job="{job}"' in rule["expr"], (
            f"{rule['alert']} does not select job={job!r}; without honor_labels the pushed "
            "samples arrive as job=pushgateway and this rule matches nothing, silently"
        )


def test_the_canary_subjects_are_the_ones_the_document_argues() -> None:
    text = SLO_DOC.read_text()
    for name in ("CANARY_ZONE", "CANARY_NONPLACE"):
        assert str(_literal(MODULE, name)) in text
    assert _literal(MODULE, "CANARY_DATE") in text


def test_the_checks_tuple_is_the_one_the_reader_pushes_and_each_argues_itself() -> None:
    """Every canary claim carries its own reason, the renderer's rule one level down."""
    source = MODULE.read_text()
    for name in ("CHECK_REACHABLE", "CHECK_ZONE", "CHECK_NONPLACE", "CHECK_CALENDAR"):
        assert f"{name} = " in source
    # `CHECKS` is built from `Check(...)` calls so it cannot be read with
    # literal_eval; assert on the structure instead — four entries, each with a
    # non-empty claim and why.
    tree = ast.parse(source)
    checks = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Check"
    ]
    assert len(checks) == 4, f"expected four canary claims, found {len(checks)}"
    for call in checks:
        assert len(call.args) == 3, "every Check carries an id, a claim and a why"


def test_no_store_rule_carries_a_bar_on_a_measured_quantity() -> None:
    """§9.2's conclusion, made structural.

    The only number permitted on the right of a comparison in these rules is the
    freshness window — the same 1800 A-4 argues. A key-count bar or a canary
    fraction would be a number somebody chose about a quantity whose legitimate
    value moves with the sources.
    """
    import re

    freshness = "1800"
    for rule in _store_rules():
        numbers = re.findall(r"[<>]=?\s*([0-9]*\.?[0-9]+)", rule["expr"])
        assert set(numbers) <= {freshness}, (
            f"{rule['alert']} compares against {sorted(set(numbers) - {freshness})}. §9.2 argues "
            "these rules hold no bar on a measured quantity: A-12b compares the store against "
            "its own sources and A-12a is a property (== 0)."
        )


# --- the refusals ----------------------------------------------------------------


REGISTRY_VERBS = {
    "set_registered_model_alias",
    "delete_registered_model_alias",
    "create_model_version",
    "transition_model_version_stage",
    "delete_model_version",
    "delete_registered_model",
}


@pytest.mark.parametrize("path", [MODULE, READER, HEADROOM, DRILL])
def test_the_watchdog_never_touches_the_registry(path: Path) -> None:
    assert not (_calls(path) & REGISTRY_VERBS), (
        f"{path.name} calls a registry-mutating verb. M9 law 3: the alias does not move and "
        "nothing is fitted."
    )


#: Needles that are only ever an INVOCATION, never prose. A redis verb and a
#: script path reach a subprocess as exact argv elements, so matching whole
#: string CONSTANTS is the difference between "this file runs it" and "this file
#: mentions it".
#:
#: The first draft of this test searched the source TEXT for `"materialize"` and
#: went red on three files for naming `automation/runs/m8-online/materialize.json`
#: and for a docstring explaining that the reader does not materialize. That is
#: gotcha #99 — a needle matching the file quoting itself — and the repair is the
#: same one this repo has made four times: ask for the shape of an invocation.
MUTATING_ARGV = {"FLUSHDB", "FLUSHALL", "materialize", "apply"}


def _string_constants(path: Path) -> set[str]:
    return {
        node.value
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


@pytest.mark.parametrize("path", [MODULE, READER, HEADROOM])
def test_the_reader_never_mutates_the_thing_it_watches(path: Path) -> None:
    """A watchdog that can write to the store cannot be trusted to report on it."""
    constants = _string_constants(path)
    offenders = sorted(constants & MUTATING_ARGV)
    assert not offenders, (
        f"{path.name} passes {offenders} somewhere an argv element goes. Only the DRILL may "
        "break the store, and only `make feast-materialize` may refill it."
    )
    scripts = sorted(c for c in constants if c.endswith("feast_materialize.sh"))
    assert not scripts, f"{path.name} invokes {scripts} — refilling the store is not a read"


def test_the_drill_stages_its_undo_before_the_injection() -> None:
    """M6-S5's rule, asked of line ORDER rather than of intent.

    The check that the repair is available must appear before the FLUSHDB that
    makes it necessary. A drill that discovers its undo is missing afterwards has
    already broken the thing.
    """
    lines = DRILL.read_text().splitlines()
    staged = next(i for i, line in enumerate(lines) if "the undo is staged BEFORE" in line)
    flush = next(i for i, line in enumerate(lines) if '"FLUSHDB"' in line)
    assert staged < flush, (
        "the FLUSHDB appears before the undo is staged — M6-S5's ordering, and the reason it "
        "is a rule is that the reverse only shows up on the run where the undo is missing"
    )


def test_the_drill_puts_the_truth_back() -> None:
    """The board must end carrying the fact, not a convenient silence (M7-S3's rule)."""
    source = DRILL.read_text()
    assert "feast_materialize.sh" in source, (
        "the drill empties the store and must refill it with the one command the runbook names"
    )
    assert "run_reader()" in source


def test_the_make_targets_exist_and_point_at_these_scripts() -> None:
    text = MAKEFILE.read_text()
    for target, script in (
        ("store-watch-headroom:", "store_watch_headroom.py"),
        ("store-watch:", "store_watch.py"),
        ("store-watch-drill:", "store_watch_drill.py"),
    ):
        assert target in text and script in text
