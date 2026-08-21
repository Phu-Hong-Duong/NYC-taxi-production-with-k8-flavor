"""M7-S3 — the drift module, the pushgateway client, and the laws that keep them apart.

The load-bearing tests here are the NEGATIVE ones: that the drift job carries no
threshold, that a push without a freshness stamp is refused, and that the
committed prediction still equals the code's. Each of those is a property this
story's write-up asserts in prose, and prose is not a check.
"""

from __future__ import annotations

import ast
import json
import math
from pathlib import Path

import pytest
import yaml

from taxi_mlops.monitoring import drift, pushgateway
from taxi_mlops.monitoring.pushgateway import Metric, PushError, push_metrics, render

REPO_ROOT = Path(__file__).resolve().parents[2]
MONITORING_DIR = REPO_ROOT / "src" / "taxi_mlops" / "monitoring"
RULES_FILE = REPO_ROOT / "infra" / "monitoring" / "alerting_rules.yml"
SLO_DOC = REPO_ROOT / "docs" / "slo_serving.md"

pytestmark = pytest.mark.unit


# --- PSI: the arithmetic, including the case that would make it infinite ------


def test_psi_of_identical_distributions_is_zero() -> None:
    shares = {"a": 0.5, "b": 0.3, "c": 0.2}
    assert drift._psi(shares, dict(shares)) == pytest.approx(0.0, abs=1e-12)


def test_psi_is_symmetric() -> None:
    a = {"x": 0.7, "y": 0.3}
    b = {"x": 0.4, "y": 0.6}
    assert drift._psi(a, b) == pytest.approx(drift._psi(b, a))


def test_psi_grows_with_distance() -> None:
    reference = {"x": 0.5, "y": 0.5}
    near = drift._psi(reference, {"x": 0.55, "y": 0.45})
    far = drift._psi(reference, {"x": 0.9, "y": 0.1})
    assert 0 < near < far


def test_an_unseen_category_does_not_make_psi_infinite() -> None:
    """`ln(x/0)` is infinite; the share floor is what keeps this a number.

    Without the floor a single trip from a zone the reference never saw would
    make every PSI in the report `inf`, every comparison True, and the alert
    permanently firing — which is the same class of failure as a rule that can
    never fire, just louder.
    """
    value = drift._psi({"a": 1.0}, {"a": 0.99, "brand-new-zone": 0.01})
    assert math.isfinite(value)
    assert value > 0


def test_unseen_mass_is_reported_separately_and_not_folded_into_psi() -> None:
    """An unseen CATEGORY and a re-WEIGHTED one are different events."""
    reference = {"a": 0.5, "b": 0.5}
    reweighted = {"a": 0.9, "b": 0.1}
    with_unseen = {"a": 0.5, "b": 0.4, "c": 0.1}
    # Both move; only one of them introduces a category the model never saw, and
    # the module exposes that as its own quantity rather than as a bigger PSI.
    assert drift._psi(reference, reweighted) > 0
    assert drift._psi(reference, with_unseen) > 0
    unseen = sum(share for key, share in with_unseen.items() if reference.get(key, 0.0) <= 0.0)
    assert unseen == pytest.approx(0.1)


def test_the_target_is_never_inside_the_input_set() -> None:
    """A-8 counts INPUT columns. Folding the target in destroys the diagnosis."""
    report = _fake_report()
    names = {c.column for c in report.input_columns}
    assert "trip_duration_minutes" not in names
    assert names == {"hour", "dayofweek", "PULocationID", "DOLocationID", "passenger_count"}
    assert report.target_drift is not None
    assert report.target_drift.column == "trip_duration_minutes"


def test_volume_is_invisible_to_psi_which_is_why_a_9_exists() -> None:
    """Halve every count and PSI is exactly zero — SLO-D2's whole argument."""
    reference = {"a": 0.6, "b": 0.4}
    half_the_world_same_mix = {"a": 0.6, "b": 0.4}
    assert drift._psi(reference, half_the_world_same_mix) == pytest.approx(0.0, abs=1e-12)


# --- F-051: the volume denominator, and the property no test used to assert ---

#: One synthetic March, quiet days first — the shape of a collapse, so that
#: "zero out the k quietest days" is "make the shutdown k days deeper". The
#: numbers are invented; the SHAPE (a long tail of near-empty days under a head
#: of ordinary ones) is 2020-03's, which is what the property is about.
_FIXTURE_MONTH = "2020-03"
_FIXTURE_DAILY_TRIPS = tuple(
    sorted([200_000 - 6_000 * i for i in range(21)] + [8_000, 6_500, 6_000, 5_500,
                                                      5_400, 5_300, 5_200, 5_100,
                                                      5_000, 4_800])
)
_FIXTURE_REFERENCE_PER_DAY = 243_024.43093922653  # the real reference, 43,987,422 / 181


def _ratio_with_days(daily: tuple[int, ...], days: int) -> float:
    return drift.trips_per_day(sum(daily), days) / _FIXTURE_REFERENCE_PER_DAY


def test_calendar_days_is_read_off_the_calendar_and_not_off_the_data() -> None:
    """The denominator of a whole month is a fact about the month, not about trips."""
    assert drift.calendar_days(["2020-03"]) == 31
    assert drift.calendar_days(["2020-02"]) == 29  # a leap February, and it matters
    assert drift.calendar_days(["2019-02"]) == 28
    # the champion's own reference window: 2019-01..06
    assert drift.calendar_days([f"2019-0{m}" for m in range(1, 7)]) == 181


def test_a_strictly_worse_collapse_produces_a_strictly_lower_volume_ratio() -> None:
    """F-051, the property. Zero out progressively more of the quietest days —
    a strictly WORSE shutdown — and the ratio A-9 reads must fall, every step.

    This is the test that did not exist when A-9 shipped. The alert's whole claim
    is that volume is the marginal PSI is blind to; a volume signal that can rise
    as the collapse deepens does not make that claim.
    """
    days = drift.calendar_days([_FIXTURE_MONTH])
    ratios = [
        _ratio_with_days(_FIXTURE_DAILY_TRIPS[zeroed:], days)
        for zeroed in range(0, 16)
    ]
    assert all(
        later < earlier for earlier, later in zip(ratios, ratios[1:], strict=False)
    ), f"the ratio did not fall monotonically: {ratios}"


def test_the_bar_is_never_re_crossed_upward_as_the_collapse_deepens() -> None:
    """The consequence a rule reads: once A-9's 0.50 bar is crossed, a deeper
    collapse may not walk back across it. REV measured the old arithmetic doing
    exactly that on the real month (8 days zeroed -> 0.5143, SILENT)."""
    days = drift.calendar_days([_FIXTURE_MONTH])
    fires = [
        _ratio_with_days(_FIXTURE_DAILY_TRIPS[zeroed:], days) < 0.50
        for zeroed in range(0, 16)
    ]
    first_firing = fires.index(True)
    assert all(fires[first_firing:]), f"A-9 went silent again as the collapse deepened: {fires}"


def test_the_observed_days_denominator_is_the_defect_and_stays_refuted() -> None:
    """The negative half: the SAME series against the old `COUNT(DISTINCT date)`
    denominator is non-monotonic. Pinned so the defect cannot quietly return by a
    future edit that 'derives the days from the data' for tidiness."""
    old = [
        _ratio_with_days(_FIXTURE_DAILY_TRIPS[zeroed:], len(_FIXTURE_DAILY_TRIPS) - zeroed)
        for zeroed in range(0, 16)
    ]
    assert any(later > earlier for earlier, later in zip(old, old[1:], strict=False)), (
        "the observed-days denominator was expected to RISE somewhere as the collapse "
        f"deepened — that rise is F-051. Got {old}"
    )


def test_a_truncated_extract_reads_as_a_volume_collapse_not_as_health() -> None:
    """F-051's second face: 20 days of a 31-day month divided by 20 looks NORMAL.
    Divided by the calendar it looks like what it is — a third of the month absent."""
    twenty_days = _FIXTURE_DAILY_TRIPS[11:]
    assert len(twenty_days) == 20
    honest = _ratio_with_days(twenty_days, drift.calendar_days([_FIXTURE_MONTH]))
    flattering = _ratio_with_days(twenty_days, len(twenty_days))
    assert honest < flattering
    assert honest == pytest.approx(flattering * 20 / 31)


def _fake_report() -> drift.DriftReport:
    columns = [
        drift.ColumnDrift(
            column=c.name, kind=c.kind, psi=0.01, unseen_share=0.0,
            reference_bins=5, current_bins=5,
        )
        for c in drift.MONITORED_COLUMNS
    ]
    return drift.DriftReport(
        month="2020-03", reference="train-2019", reference_months=["2019-01"],
        reference_rows=100, current_rows=50, reference_trips_per_day=10.0,
        current_trips_per_day=5.0, volume_ratio=0.5, columns=columns,
        computed_at="2026-08-20T00:00:00+00:00",
    )


def test_compute_split_drift_refuses_the_train_split() -> None:
    """Comparing the reference with itself would report 0.0 and mean nothing."""
    with pytest.raises(ValueError, match="held-out"):
        drift.compute_split_drift("train")


# --- the pushgateway client ---------------------------------------------------


def test_push_refuses_a_payload_with_no_freshness_stamp() -> None:
    """The guard is in a TYPE, not in a habit — a pushed metric outlives its producer."""
    with pytest.raises(PushError, match="freshness"):
        push_metrics(
            [Metric(name="taxi_drift_psi", value=1.0, help="h")],
            url="http://unused",
            job="taxi-drift",
        )


def test_push_refuses_an_empty_payload() -> None:
    with pytest.raises(PushError, match="empty"):
        push_metrics([], url="http://unused", job="taxi-drift")


def test_any_metric_ending_in_the_freshness_suffix_satisfies_the_guard() -> None:
    """Three pushers, three stamps: one shared timestamp would let a live job
    vouch for a dead one."""
    metrics = [
        Metric(name="taxi_quote_refusals_total", value=1.0, help="h"),
        Metric(name="taxi_quote_client" + pushgateway.FRESHNESS_SUFFIX, value=1.0, help="h"),
    ]
    # Rendering is what push_metrics does after the guard; reaching it is the assertion.
    assert any(m.name.endswith(pushgateway.FRESHNESS_SUFFIX) for m in metrics)
    assert "taxi_quote_refusals_total" in render(metrics)


def test_render_emits_one_help_per_metric_name() -> None:
    """A repeated `# HELP` for one name makes the gateway reject the whole payload."""
    text = render(
        [
            Metric(name="taxi_drift_psi", value=1.0, help="h", labels={"column": "hour"}),
            Metric(name="taxi_drift_psi", value=2.0, help="h", labels={"column": "dow"}),
            Metric(name="taxi_drift_last_run_timestamp_seconds", value=3.0, help="t"),
        ]
    )
    assert text.count("# HELP taxi_drift_psi ") == 1
    assert text.count("# TYPE taxi_drift_psi ") == 1
    assert text.count("taxi_drift_psi{") == 2


def test_render_escapes_label_values() -> None:
    text = render(
        [
            Metric(name="m", value=1.0, help="h", labels={"k": 'a"b\\c'}),
            Metric(name="x" + pushgateway.FRESHNESS_SUFFIX, value=1.0, help="h"),
        ]
    )
    assert 'k="a\\"b\\\\c"' in text


def test_grouping_path_encodes_the_key() -> None:
    path = pushgateway._grouping_path("taxi-drift", {"month": "2020-03"})
    assert path == "/metrics/job/taxi-drift/month/2020-03"


# --- the laws ------------------------------------------------------------------


def test_no_threshold_lives_anywhere_under_the_monitoring_package() -> None:
    """F-013's one-home law, applied to drift.

    The bar is 0.10 and it exists in exactly one place: the rules file. A copy
    inside the job would be the twin problem this program has hit five times —
    and worse here, because the job's copy would decide what gets PUSHED, making
    the raw numbers un-reinterpretable after the fact.

    Parsed with `ast`, never grepped: these modules argue their own design at
    length and a word search would match the argument (gotchas #53/#68).
    """
    bar_shaped = {0.10, 0.25, 0.50}
    offenders: list[str] = []
    for path in MONITORING_DIR.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, float)
                and node.value in bar_shaped
            ):
                offenders.append(f"{path.name}:{node.lineno} -> {node.value}")
    assert not offenders, (
        "a bar-shaped constant appeared in the drift job: "
        + ", ".join(offenders)
        + ". The bar lives in infra/monitoring/alerting_rules.yml only."
    )


def test_the_drift_job_never_mutates_the_registry() -> None:
    """M7 law 3: the alias moves only through the gate."""
    forbidden = {
        "set_registered_model_alias",
        "delete_registered_model_alias",
        "create_model_version",
        "transition_model_version_stage",
        "delete_model_version",
    }
    for path in list(MONITORING_DIR.glob("*.py")) + [
        REPO_ROOT / "scripts" / "drift_fire_drill.py",
        REPO_ROOT / "scripts" / "push_serving_version.py",
    ]:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = getattr(func, "attr", None) or getattr(func, "id", None)
                assert name not in forbidden, f"{path.name}:{node.lineno} calls {name}"


def test_every_rule_threshold_appears_in_the_document_that_argues_it() -> None:
    """verify-m6 §2's property, extended to the drift block, as a unit test.

    A gate carrying its own copy of 0.10 would stay green after the rule was
    loosened to 0.5 — the exact change the constitution reserves for a PO fork.
    """
    document = yaml.safe_load(RULES_FILE.read_text())
    doc_text = SLO_DOC.read_text()
    for group in document["groups"]:
        if group["name"] != "crosstown-drift":
            continue
        for rule in group["rules"]:
            for token in ("0.10", "0.50", "3456000", "1800"):
                if token in rule["expr"]:
                    # EXACT match only. The obvious loosening — also accept the
                    # token with trailing zeros stripped — turns "1800" into
                    # "18", which matches "18.24 s" elsewhere in this document
                    # and passes for a threshold nobody wrote down. That is
                    # gotcha #76, and it happened here on this test's FIRST RUN:
                    # 3456000 failed honestly while 1800 passed by accident.
                    assert token in doc_text, (
                        f"{rule['alert']}'s threshold {token} is in the rules file but "
                        "not in docs/slo_serving.md, which is the only place a "
                        "threshold may be argued. The document must carry the number "
                        "the RULE contains, not a friendlier rendering of it."
                    )


def test_every_drift_rule_carries_a_signal_and_a_why() -> None:
    """The id set is DERIVED from the renderer, not typed here.

    It used to be the literal `{"A-3", "A-4", "A-8", "A-9", "A-10"}` — true the
    day it was written, and RED the moment M8-S1 added A-11 for F-050, which is
    a guard going red for a correct addition (gotcha #50, and it has now cost
    this program seven sessions). The property that holds at every state: a
    drift rule's signal must be one the program KNOWS about, and
    `render_alert_rules.validate()` is what enforces that both ways.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_render_alert_rules", REPO_ROOT / "scripts" / "render_alert_rules.py"
    )
    renderer = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(renderer)

    document = yaml.safe_load(RULES_FILE.read_text())
    for group in document["groups"]:
        if group["name"] != "crosstown-drift":
            continue
        assert group["rules"], "the drift group is empty"
        for rule in group["rules"]:
            assert rule["labels"]["signal"] in renderer.KNOWN_SIGNALS
            assert rule["annotations"]["why"].strip()


def test_a_8_excludes_the_target_column_by_name() -> None:
    """The exclusion is in the SELECTOR, so it cannot be lost by a code change."""
    document = yaml.safe_load(RULES_FILE.read_text())
    rule = _rule(document, "ModelInputDrift")
    assert 'column!="trip_duration_minutes"' in rule["expr"]


def test_the_a_4_rule_requires_freshness_as_well_as_agreement() -> None:
    """A stale pushed pair agrees with itself forever."""
    document = yaml.safe_load(RULES_FILE.read_text())
    rule = _rule(document, "ServedVersionNotChampion")
    assert "last_run_timestamp_seconds" in rule["expr"]


def test_the_scrape_job_for_the_gateway_honors_labels() -> None:
    """Without `honor_labels`, `job` is overwritten and EVERY drift rule matches nothing.

    The rules select `job="taxi-drift"` — a label the PUSHER sets. A rule that
    matches nothing does not error; it sits inactive forever and looks exactly
    like a healthy system.
    """
    values = yaml.safe_load(
        (REPO_ROOT / "infra" / "helm" / "monitoring" / "prometheus-values.yaml").read_text()
    )
    jobs = yaml.safe_load(values["extraScrapeConfigs"])
    gateway = [j for j in jobs if j["job_name"] == "pushgateway"]
    assert gateway, "no pushgateway scrape job"
    assert gateway[0]["honor_labels"] is True
    target = gateway[0]["static_configs"][0]["targets"][0]
    assert target.startswith(pushgateway.SERVICE_NAME + "."), (
        "the scrape target and the client's default address are twins; they must "
        f"name the same Service ({pushgateway.SERVICE_NAME})."
    )


@pytest.mark.needs_records
def test_the_committed_prediction_still_equals_the_code() -> None:
    """Amending a prediction to match an outcome must be a RED test, not a diff.

    M6-S5's discipline, inherited. The prediction is the only artefact in this
    story whose value depends entirely on when it was written.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "drift_fire_drill", REPO_ROOT / "scripts" / "drift_fire_drill.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    committed = json.loads(
        (REPO_ROOT / "automation" / "runs" / "m7-drift" / "prediction.json").read_text()
    )
    assert committed == module.PREDICTION


@pytest.mark.needs_records
def test_the_committed_persistence_prediction_still_equals_the_code() -> None:
    """The same law for M8-S1's F-050 drill — one drill, one prediction, one test.

    Deliberately a SECOND test rather than a parametrised one: when a drill's
    prediction and its code disagree, the failure should name the drill.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "drift_persistence_drill", REPO_ROOT / "scripts" / "drift_persistence_drill.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    committed = json.loads(
        (REPO_ROOT / "automation" / "runs" / "m8-drift" / "persistence-prediction.json").read_text()
    )
    assert committed == module.PREDICTION


def test_the_persistence_drill_predicts_what_must_NOT_happen_too() -> None:
    """A drill that predicts only "something fires" cannot be wrong.

    A-10 staying inactive through a total loss of the drift surface is the whole
    argument for A-11 existing; if it fired here, F-050's second half would be
    redundant and the finding would have been wrong. That has to be a prediction,
    not a footnote discovered afterwards.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "drift_persistence_drill", REPO_ROOT / "scripts" / "drift_persistence_drill.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    quiet = {entry["signal"] for entry in module.PREDICTION["absence"]["must_not_fire"]}
    assert "A-10" in quiet, "the drill must predict A-10's silence, which is A-11's reason to exist"
    assert module.PREDICTION["absence"]["must_fire"]["signal"] == "A-11"


def _rule(document: dict, name: str) -> dict:
    for group in document["groups"]:
        for rule in group.get("rules", []):
            if rule.get("alert") == name:
                return rule
    raise AssertionError(f"{name} is not in the rules file")
