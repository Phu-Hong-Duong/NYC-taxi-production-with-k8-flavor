"""The gate, tested at the boundaries it exists to hold — and refusing on purpose.

A gate is only worth what its refusals are worth, so most of this file is about
the ways it must say no: to a challenger that ties the floor, to one that buys
its mean by quoting more riders wrongly, to a comparison made on the wrong split
or against the flattering floor, and to a winner that could not be served.

Everything here is cluster-free. `gate.decide` is a pure function of two
`Metrics` and a config, and `registry.promote` takes its client — so the
dangerous half is exercised against a fake that records what was called.
"""

from __future__ import annotations

import pytest

from taxi_mlops.data.config import load_yaml
from taxi_mlops.training import gate, registry
from taxi_mlops.training.evaluate import Metrics

TRAIN_CFG = load_yaml("configs/train.yaml")
GATE_CFG = TRAIN_CFG["gate"]

# The measured M2-S2 numbers, so a change to the shipped config is checked
# against the model that exists rather than against a number invented for a test.
V1_TEST_MAE, FLOOR_TEST_MAE = 3.2608, 3.5090
V1_TEST_WITHIN, FLOOR_TEST_WITHIN = 81.480, 80.322


def metrics(
    contender: str,
    *,
    mae: float,
    within: float = 80.0,
    split: str = "test",
    n: int = 5_950_708,
    tolerance: float = 5.0,
) -> Metrics:
    return Metrics(
        contender=contender,
        split=split,
        n=n,
        mae=mae,
        within_tolerance_rate=within,
        tolerance_minutes=tolerance,
        rmse=mae * 1.5,
        median_ae=mae * 0.7,
        p90_ae=mae * 2.1,
    )


def floor(mae: float = FLOOR_TEST_MAE, within: float = FLOOR_TEST_WITHIN, **kw) -> Metrics:
    return metrics(GATE_CFG["floor"], mae=mae, within=within, **kw)


# ------------------------------------------------------------- the shipped config ---
def test_the_shipped_margin_admits_v1_and_the_headroom_is_stated():
    """The bar must not be one cut to fit the model we happen to have."""
    decision = gate.decide(
        metrics("lightgbm-v1", mae=V1_TEST_MAE, within=V1_TEST_WITHIN), floor(), GATE_CFG
    )
    assert decision.passed
    assert decision.observed_pct == pytest.approx(7.07, abs=0.01)
    assert decision.required_pct < decision.observed_pct / 3, (
        "the configured margin is within a third of the measured gap — that is a "
        "rubber stamp shaped like a gate"
    )


def test_the_bar_is_the_honest_floor_and_the_flattering_one_is_not_configurable_into_it():
    assert GATE_CFG["floor"] == "baseline-group-median"
    assert GATE_CFG["holdout_split"] == "test"


# ---------------------------------------------------------------- the refusals ---
def test_a_challenger_that_merely_ties_the_floor_is_refused():
    decision = gate.decide(metrics("tie", mae=FLOOR_TEST_MAE), floor(), GATE_CFG)
    assert not decision.passed
    assert decision.verdict == "REFUSE"


def test_a_challenger_just_under_the_margin_is_refused_and_just_over_it_passes():
    """The boundary is `>=`, and it is tested from both sides so it cannot drift."""
    required = float(GATE_CFG["min_improvement_pct"])
    exact = FLOOR_TEST_MAE * (1 - required / 100)
    assert gate.decide(metrics("exact", mae=exact, within=99.0), floor(), GATE_CFG).passed
    just_under = metrics("just-under", mae=exact * 1.0001, within=99.0)
    assert not gate.decide(just_under, floor(), GATE_CFG).passed


def test_a_model_that_buys_its_mean_by_quoting_more_riders_wrongly_is_refused():
    """KPI-09 improves 10%, KPI-10 regresses. The second condition earns its keep."""
    sneaky = metrics("mean-chaser", mae=FLOOR_TEST_MAE * 0.9, within=FLOOR_TEST_WITHIN - 0.001)
    decision = gate.decide(sneaky, floor(), GATE_CFG)
    assert not decision.passed
    margin_check, kpi10_check = decision.checks
    assert margin_check.passed and not kpi10_check.passed
    assert "KPI-10" in kpi10_check.name


def test_a_hobbled_model_is_refused_by_a_wide_margin():
    """The red team's shape: a model fitted to noise predicts ~the constant median."""
    hobbled = metrics("lightgbm-v1-hobbled-shuffled-target", mae=7.6667, within=48.372)
    decision = gate.decide(hobbled, floor(), GATE_CFG)
    assert not decision.passed
    assert decision.observed_pct < 0
    assert all(not check.passed for check in decision.checks)


# ------------------------------------------------- refusing to judge at all ---
def test_the_gate_refuses_to_judge_on_val_because_early_stopping_read_it():
    with pytest.raises(gate.GateError, match="val"):
        gate.decide(
            metrics("lightgbm-v1", mae=V1_TEST_MAE, split="val"),
            floor(split="val"),
            GATE_CFG,
        )


def test_the_gate_refuses_the_flattering_floor_as_a_bar():
    with pytest.raises(gate.GateError, match="constant-median"):
        gate.decide(
            metrics("lightgbm-v1", mae=V1_TEST_MAE),
            metrics("baseline-constant-median", mae=7.6667),
            GATE_CFG,
        )


def test_the_gate_refuses_two_numbers_computed_over_different_populations():
    with pytest.raises(gate.GateError, match="not a comparison"):
        gate.decide(metrics("lightgbm-v1", mae=V1_TEST_MAE, n=10), floor(), GATE_CFG)


def test_the_gate_refuses_two_different_kpi10_tolerances():
    with pytest.raises(gate.GateError, match="tolerances differ"):
        gate.decide(metrics("lightgbm-v1", mae=V1_TEST_MAE, tolerance=3.0), floor(), GATE_CFG)


# ------------------------------------------------------------- the transcript ---
@pytest.mark.parametrize("mae,expected", [(V1_TEST_MAE, "PROMOTE"), (7.6667, "REFUSE")])
def test_both_numbers_are_printed_on_a_pass_and_on_a_refusal_alike(mae, expected):
    """A verdict without its two numbers teaches the reader to trust it or ignore it."""
    text = gate.verdict_lines(gate.decide(metrics("c", mae=mae, within=99.0), floor(), GATE_CFG))
    assert expected in text
    assert f"{mae:.4f}" in text and f"{FLOOR_TEST_MAE:.4f}" in text
    assert "baseline-group-median" in text
    if expected == "REFUSE":
        assert "Nothing was registered" in text


# ------------------------------------------------------------------ promotion ---
class FakeVersion:
    def __init__(self, version, run_id):
        self.version, self.run_id, self.aliases = str(version), run_id, []


class FakeClient:
    """Records what was called. Absence raises, exactly as MlflowClient's does."""

    def __init__(self, versions=None, alias_at=None, model_exists=True):
        self.versions = list(versions or [])
        self.alias_at = alias_at
        self.model_exists = model_exists
        self.calls: list[str] = []

    def get_registered_model(self, name):
        self.calls.append("get_registered_model")
        if not self.model_exists:
            raise RuntimeError("not found")
        return object()

    def create_registered_model(self, name, description=None):
        self.calls.append("create_registered_model")
        self.model_exists = True

    def search_model_versions(self, filter_string):
        self.calls.append("search_model_versions")
        return list(self.versions)

    def create_model_version(self, name, source, run_id):
        self.calls.append("create_model_version")
        version = FakeVersion(len(self.versions) + 1, run_id)
        self.versions.append(version)
        return version

    def set_model_version_tag(self, name, version, key, value):
        self.calls.append("set_model_version_tag")

    def get_model_version_by_alias(self, name, alias):
        self.calls.append("get_model_version_by_alias")
        if self.alias_at is None:
            raise RuntimeError("alias not set")
        return FakeVersion(self.alias_at, "whatever")

    def set_registered_model_alias(self, name, alias, version):
        self.calls.append("set_registered_model_alias")
        self.alias_at = str(version)


class FakeInfo:
    def __init__(self, signature="sig", example="example"):
        self.signature = signature
        self.saved_input_example_info = example


def promote(client, run_id="run-1", info=None, **kw):
    return registry.promote(
        client,
        model_name="nyc-taxi-eta",
        alias="champion",
        run_id=run_id,
        model_info=lambda uri: info or FakeInfo(),
        **kw,
    )


def test_the_first_promotion_creates_the_model_the_version_and_the_alias():
    client = FakeClient(model_exists=False)
    result = promote(client)
    assert (result.version, result.version_created, result.alias_moved) == ("1", True, True)
    assert result.previous_version is None
    assert "create_registered_model" in client.calls
    assert client.alias_at == "1"


def test_re_promoting_the_same_run_is_a_no_op_and_mints_no_second_version():
    """M1-S5's law, applied to the registry: a converging path that creates a
    duplicate every time is not converging, it is accumulating."""
    client = FakeClient(versions=[FakeVersion(1, "run-1")], alias_at="1")
    result = promote(client)
    assert result.noop and result.version == "1"
    assert "create_model_version" not in client.calls
    assert "set_registered_model_alias" not in client.calls


def test_a_new_winner_moves_the_alias_and_keeps_the_old_version():
    client = FakeClient(versions=[FakeVersion(1, "run-1")], alias_at="1")
    result = promote(client, run_id="run-2")
    assert (result.version, result.previous_version, result.alias_moved) == ("2", "1", True)
    assert len(client.versions) == 2, "nothing here may delete a superseded version"


def test_a_model_without_a_signature_is_not_promotable():
    with pytest.raises(registry.PromotionError, match="signature"):
        promote(FakeClient(), info=FakeInfo(signature=None))


def test_a_model_without_an_input_example_is_not_promotable():
    with pytest.raises(registry.PromotionError, match="input example"):
        promote(FakeClient(), info=FakeInfo(example=None))


def test_an_artifact_that_cannot_be_read_back_points_at_gotcha_5():
    def boom(uri):
        raise RuntimeError("404")

    with pytest.raises(registry.PromotionError, match="gotcha #5"):
        registry.promote(
            FakeClient(), model_name="m", alias="champion", run_id="r", model_info=boom
        )


def test_the_results_table_stays_aligned_when_a_contender_has_a_long_name():
    """The red-team contender's name is 35 characters and used to shove every
    column after it out of line — on exactly the run whose table gets pasted into
    a refusal transcript and retyped by hand."""
    from taxi_mlops.training.evaluate import results_table

    rows = [metrics("lightgbm-v1-hobbled-shuffled-target", mae=7.6667), floor()]
    lines = results_table(rows).splitlines()
    rule_at = next(i for i, line in enumerate(lines) if line.strip().startswith("---"))
    rule, body = lines[rule_at], lines[rule_at + 1 :]
    assert len(body) == len(rows)
    assert {len(line) for line in body} == {len(rule)}, (
        "the data rows and the rule are different lengths — the table is misaligned"
    )


# --------------------------------------------------------------- the interface ---
def test_make_train_is_real_and_no_longer_echoes_todo():
    """The Makefile is THE interface; a target echoing TODO after its milestone
    landed is a lie with a tab character in front of it."""
    import pathlib

    text = pathlib.Path("Makefile").read_text()
    recipe = text.split("\ntrain:", 1)[1].split("\n.PHONY")[0].split("\n")[1]
    assert "TODO" not in recipe
    assert "python -m taxi_mlops.training train" in recipe
    assert "bash scripts/train_redteam.sh" in text


def test_the_refusal_exits_non_zero_and_the_red_team_inverts_that():
    """From M4 `make train` is a pipeline step. A gate that says no while exiting
    0 is a gate the pipeline cannot hear."""
    import pathlib

    cli = pathlib.Path("src/taxi_mlops/training/__main__.py").read_text()
    assert "return 0 if result.decision.passed else 1" in cli

    script = pathlib.Path("scripts/train_redteam.sh").read_text()
    assert 'STATUS" -eq 0' in script, "the red team must fail when the gate PASSES"
    assert 'STATUS" -ne 1' in script, (
        "an exit code that is neither 0 nor the gate's 1 means the run died before "
        "the verdict — the red team must call that inconclusive, not a pass"
    )
    assert 'BEFORE" != "$AFTER' in script, "the red team must compare the registry across the run"
    # Promotion stays ENABLED in the red team: the proof is that the GATE stopped
    # the hobbled model, not that a flag did.
    assert "--no-promote" not in script


def test_nothing_in_the_registry_module_deletes():
    import pathlib

    source = pathlib.Path("src/taxi_mlops/training/registry.py").read_text()
    for forbidden in ("delete_registered_model", "delete_model_version"):
        assert forbidden not in source, (
            f"{forbidden} in the promotion path: a champion that was replaced is "
            "exactly what a rollback needs to find. Destroying is `make destroy`'s job."
        )
