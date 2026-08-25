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

import re
from pathlib import Path

import pytest

from taxi_mlops.data.config import load_yaml
from taxi_mlops.training import gate, gate_eras, registry
from taxi_mlops.training.evaluate import Metrics

REPO = Path(__file__).resolve().parents[2]
TRAIN_CFG = load_yaml("configs/train.yaml")
GATE_CFG = TRAIN_CFG["gate"]

# The measured numbers, so a change to the shipped config is checked against the
# models that exist rather than against numbers invented for a test.
#   M2-S2/S3: v1 and the single-level floor it was gated against.
#   M3-S1   : the two-level floor the gate judges against from now on (F-010).
V1_TEST_MAE, V1_TEST_WITHIN = 3.2608, 81.480
M2_FLOOR_TEST_MAE, M2_FLOOR_TEST_WITHIN = 3.5090, 80.322
FLOOR_TEST_MAE, FLOOR_TEST_WITHIN = 3.3518, 80.733


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
def test_the_shipped_margin_still_admits_the_model_that_is_serving():
    """A bar the incumbent could not clear would be a rollback dressed as a gate.

    The headroom is now 1.35x (+2.71% observed against a 2.00% bar) and not the
    3.5x M2 claimed, because F-010's floor is 0.157 min stronger. That is the
    number DR-06 §2 adopted as M3's working headroom, and it is asserted here so
    the config and the milestone's story cannot drift apart.
    """
    decision = gate.decide(
        metrics("lightgbm-v1", mae=V1_TEST_MAE, within=V1_TEST_WITHIN), floor(), GATE_CFG
    )
    assert decision.passed
    assert decision.observed_pct == pytest.approx(2.71, abs=0.01)
    assert decision.required_pct < decision.observed_pct, (
        "the model that is SERVING would be refused by the shipped bar — tightening "
        "past the incumbent is a rollback, and it is not what F-010 asked for"
    )


def test_the_floor_only_ever_got_harder_and_the_old_margin_is_not_the_new_one():
    """F-010 in one assertion: the same challenger, two floors, 2.6x the margin.

    The M2 number is kept here on purpose. It is not wrong — it is what v1 was
    promoted at, and `verify-m2` replays it — but it describes a comparison
    against a floor the program has since improved on, and DR-06 §2 forbids
    quoting it as headroom.
    """
    assert FLOOR_TEST_MAE < M2_FLOOR_TEST_MAE, "the gate's floor got easier, not harder"
    old = gate.improvement_pct(V1_TEST_MAE, M2_FLOOR_TEST_MAE)
    new = gate.improvement_pct(V1_TEST_MAE, FLOOR_TEST_MAE)
    assert old == pytest.approx(7.07, abs=0.01)
    assert new == pytest.approx(2.71, abs=0.01)


def test_the_bar_is_the_honest_floor_and_the_flattering_one_is_not_configurable_into_it():
    assert GATE_CFG["floor"] == "baseline-group-median-od-fallback"
    assert GATE_CFG["holdout_split"] == "test"
    assert float(GATE_CFG["min_improvement_pct"]) >= 2.0
    assert GATE_CFG["require_no_kpi10_regression"] is True


def test_the_configured_floor_is_one_the_program_can_actually_fit():
    """A floor named in the gate that `fit_floor` cannot build is a bar that
    exists only in a config file — and it would fail at the one moment it
    matters, in the middle of a training run that has already been paid for."""
    import pandas as pd

    from taxi_mlops.training import baselines

    frame = pd.DataFrame(
        {
            "hour": [1, 1, 2],
            "dayofweek": [0, 0, 0],
            "PULocationID": [10, 10, 11],
            "DOLocationID": [20, 20, 21],
        }
    )
    fitted = baselines.fit_floor(
        GATE_CFG["floor"], frame, pd.Series([4.0, 6.0, 8.0]), TRAIN_CFG["baselines"]
    )
    assert fitted.name == GATE_CFG["floor"]


# ---------------------------------------------------------------- the refusals ---
def test_a_challenger_that_merely_ties_the_floor_is_refused():
    decision = gate.decide(metrics("tie", mae=FLOOR_TEST_MAE), floor(), GATE_CFG)
    assert not decision.passed
    assert decision.verdict == "REFUSE"


def test_a_challenger_just_under_the_margin_is_refused_and_just_over_it_passes():
    """The boundary is `>=`, and it is tested from both sides so it cannot drift.

    Both sides are nudged by a millisecond of MAE rather than sitting exactly ON
    the boundary: `floor * (1 - 2/100)` does not round-trip to exactly 2.00% in
    binary, so a test written on the knife edge asserts the behaviour of IEEE 754
    rather than the behaviour of the gate. It found that out by going red when
    the floor changed — the same arithmetic, a different last bit.
    """
    required = float(GATE_CFG["min_improvement_pct"])
    exact = FLOOR_TEST_MAE * (1 - required / 100)
    just_over = metrics("just-over", mae=exact - 1e-6, within=99.0)
    assert gate.decide(just_over, floor(), GATE_CFG).passed
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


# --------------------------------------------- the incumbent condition (F-011) ---
def incumbent(mae: float = V1_TEST_MAE, within: float = V1_TEST_WITHIN, **kw) -> gate.Incumbent:
    return gate.Incumbent(
        version=kw.pop("version", "1"),
        mae=mae,
        within_tolerance_rate=within,
        split=kw.pop("split", "test"),
        source="version tags",
    )


def test_a_challenger_that_clears_the_floor_but_is_worse_than_the_champion_is_refused():
    """F-011's failure, in the units the finding was filed in.

    The finding's own example was 3.40 min — worse than champion v1's 3.2608 and
    comfortably clear of the M2 floor's bar. Against F-010's stronger floor that
    challenger is now refused by the MARGIN, which is a fair thing to notice: a
    better bar shrinks the window where F-011 bites. It does not close it. 3.2800
    clears the floor bar by +2.14% and is still 0.0192 min worse than the model
    that is serving, and that window is exactly where a tuned M3 contender lands.
    """
    challenger = metrics("tuned-but-worse", mae=3.2800, within=81.5)
    against_floor_only = gate.decide(challenger, floor(), GATE_CFG)
    assert against_floor_only.passed, "the premise of the finding: the floor bar admits it"

    decision = gate.decide(challenger, floor(), GATE_CFG, incumbent=incumbent())
    assert not decision.passed
    failed = [c for c in decision.checks if not c.passed]
    assert len(failed) == 1 and "serving champion" in failed[0].name
    assert "3.2800" in failed[0].detail and "3.2608" in failed[0].detail


def test_a_challenger_better_on_the_mean_and_worse_for_riders_is_refused_against_the_champion():
    """KPI-09 improves against the incumbent, KPI-10 does not. One mean, six
    million riders: the second condition is the one they feel."""
    sneaky = metrics("mean-chaser", mae=V1_TEST_MAE - 0.05, within=V1_TEST_WITHIN - 0.2)
    decision = gate.decide(sneaky, floor(), GATE_CFG, incumbent=incumbent())
    assert not decision.passed
    failed = [c for c in decision.checks if not c.passed]
    assert len(failed) == 1 and "KPI-10" in failed[0].name and "serving champion" in failed[0].name


def test_a_genuinely_better_challenger_still_passes_with_an_incumbent_present():
    better = metrics("v2", mae=V1_TEST_MAE - 0.1, within=V1_TEST_WITHIN + 0.5)
    decision = gate.decide(better, floor(), GATE_CFG, incumbent=incumbent())
    assert decision.passed
    assert len(decision.checks) == 4, (
        "floor margin, floor KPI-10, incumbent KPI-09, incumbent KPI-10"
    )


def test_a_tie_with_the_incumbent_is_REFUSED_from_M9_S10_on():
    """The identity case, and the argument this test used to make against it.

    Until M9-S10 this asserted the opposite, for a reason worth keeping visible:
    *"re-gating the champion's own numbers must not refuse it — `make train` is
    idempotent by run, and a re-run that cannot reach its own verdict again
    would make every promotion a one-way door."* The PO's F-016 letter decided
    the other way (AWAITING_PO 2026-08-24-4), and the one-way-door fear does not
    bite, because the idempotence it names lives in `registry.promote` and not
    here: a re-run that produces the champion's own numbers changes NOTHING
    about the registry under either rule — the alias already points at that
    model. What changed is the exit code of such a re-run: 0 (a no-op promotion)
    becomes 1 (a refusal). That is the honest cost, and it is the correct
    reading — +0.0000% buys nothing, and a transition that buys nothing is not
    worth the alias move, the version stamp on every published prediction, or
    the rollback it obliges.
    """
    same = metrics("lightgbm-v1", mae=V1_TEST_MAE, within=V1_TEST_WITHIN)
    decision = gate.decide(same, floor(), GATE_CFG, incumbent=incumbent())
    assert not decision.passed
    failed = [c for c in decision.checks if not c.passed]
    assert len(failed) == 1 and "serving champion" in failed[0].name
    assert f"required >= {float(GATE_CFG['incumbent_min_improvement_pct']):.2f}%" in failed[0].detail


def test_the_champion_re_fitted_is_not_a_regression_against_its_own_rounded_tag():
    """The defect the first real run found, pinned so it cannot come back.

    `registry.promote` records the incumbent's KPI-09 at four decimals. A
    deterministic re-fit of that same champion measures 3.2608234…, and
    `3.2608234 <= 3.2608` is False — so the gate refused the model that is
    serving, against itself, on 23 microseconds of arithmetic. Numbers are
    compared at the resolution the registry recorded them at; this test uses the
    unrounded measurement on purpose, because the rounded one could never fail.

    M9-S10's margin changed the VERDICT here (a tie is now a refusal, see above)
    and left the property intact one level down: the comparison is still made at
    four decimals, so the re-fit still reads as EXACTLY zero and not as the
    −0.00072% regression its unrounded digits would suggest. The verdict moved;
    the arithmetic this test exists for did not, so the assertion moved with it
    rather than the test being deleted.
    """
    refit = metrics("lightgbm-v1", mae=3.2608234567, within=81.4801234)
    decision = gate.decide(refit, floor(), GATE_CFG, incumbent=incumbent())
    observed = gate.improvement_pct(
        round(refit.mae, gate.INCUMBENT_MAE_DECIMALS), incumbent().mae
    )
    assert observed == 0.0, "the re-fit is being judged on digits the registry never recorded"
    assert "+0.00% vs incumbent" in next(
        c.detail for c in decision.checks if "serving champion" in c.name
    )


def test_a_regression_bigger_than_the_recorded_resolution_is_still_caught():
    """The other side of the same line: rounding must not become a free pass.
    One ten-thousandth of a minute is the smallest difference the registry can
    represent, and it must read as NEGATIVE — under a margin every non-improving
    challenger is refused anyway, so the refusal alone would no longer prove the
    rounding did not swallow it."""
    worse = metrics("v2", mae=V1_TEST_MAE + 0.0001, within=V1_TEST_WITHIN)
    decision = gate.decide(worse, floor(), GATE_CFG, incumbent=incumbent())
    assert not decision.passed
    assert (
        gate.improvement_pct(
            round(worse.mae, gate.INCUMBENT_MAE_DECIMALS), incumbent().mae
        )
        < 0.0
    )


def test_the_rounding_constants_are_twins_of_the_tags_the_registry_writes():
    """gate.py rounds to the precision run._promote formats with. Two files, one
    number — the port-family lesson applied to a decimal place."""
    import pathlib

    source = pathlib.Path("src/taxi_mlops/training/run.py").read_text()
    mae_tag = (
        '"gate_challenger_mae": f"{decision.challenger_mae:.'
        f'{gate.INCUMBENT_MAE_DECIMALS}f}}"'
    )
    assert mae_tag in source
    assert (
        f'"gate_challenger_within_rate": f"{{decision.challenger_within:.'
        f'{gate.INCUMBENT_WITHIN_DECIMALS}f}}"' in source
    )


def test_the_gate_refuses_an_incumbent_measured_on_another_split():
    with pytest.raises(gate.GateError, match="not a comparison"):
        gate.decide(
            metrics("v2", mae=3.0), floor(), GATE_CFG, incumbent=incumbent(split="val")
        )


def test_the_incumbent_travels_on_the_decision_and_into_the_run():
    decision = gate.decide(
        metrics("v2", mae=3.0, within=99.0), floor(), GATE_CFG, incumbent=incumbent()
    )
    assert decision.incumbent is not None and decision.incumbent.version == "1"
    assert decision.as_mlflow()["gate_incumbent_mae"] == V1_TEST_MAE
    text = gate.verdict_lines(decision)
    assert "incumbent : version 1" in text and "3.2608" in text and "81.480" in text


def test_a_verdict_without_an_incumbent_says_so_out_loud():
    """The first promotion has no incumbent, and M2's replayed verdicts carry
    none. Silence would be indistinguishable from a comparison nobody made."""
    decision = gate.decide(metrics("v1", mae=V1_TEST_MAE, within=99.0), floor(), GATE_CFG)
    assert decision.incumbent is None
    assert "incumbent : none" in gate.verdict_lines(decision)
    assert "gate_incumbent_mae" not in decision.as_mlflow()


# ------------------------------------------ the sampled-run refusal (F-008) ---
def test_the_gate_issues_no_verdict_for_a_sampled_training_run():
    configured = list(TRAIN_CFG["data"]["train_months"])
    gate.assert_full_train_months(configured, configured)  # the full set is fine
    with pytest.raises(gate.GateError, match="SAMPLED"):
        gate.assert_full_train_months(configured[:1], configured)


def test_the_sampled_refusal_names_both_month_sets_and_the_direction_of_the_error():
    configured = list(TRAIN_CFG["data"]["train_months"])
    with pytest.raises(gate.GateError) as exc:
        gate.assert_full_train_months(["2019-01"], configured)
    message = str(exc.value)
    assert "2019-01" in message and configured[-1] in message
    # The trap is that a sample makes the transcript look BETTER. If the message
    # does not say so, the next reader assumes the refusal is bureaucracy.
    assert "16.85%" in message and "FLOOR" in message


def test_the_same_months_in_a_different_order_are_refused_and_that_is_deliberate():
    """A reordered month list is not the same fit, so it does not get the same
    verdict. `bagging_fraction: 0.8` with `bagging_freq: 1` samples rows by
    position, so feeding January last changes which rows each tree sees — the
    model differs in the last decimals. Comparing lists rather than sets keeps
    "this verdict describes that fit" true; the cost is that somebody who types
    the six months out of order gets a refusal, which is the safe direction.
    """
    configured = list(TRAIN_CFG["data"]["train_months"])
    gate.assert_full_train_months(configured, configured)
    with pytest.raises(gate.GateError):
        gate.assert_full_train_months(list(reversed(configured)), configured)


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


def test_the_selection_purity_claim_must_be_earned_by_the_caller():
    """F-018 / property 7. The gate can vouch for training-purity — it refuses
    metrics from any split but the configured holdout. It cannot see how the
    challenger it was handed was CHOSEN, and for the whole of M3-S5 it printed
    that claim on behalf of a bake-off that had ranked five arms on this very
    month. So the strong sentence is now an argument, and the DEFAULT is the
    weaker one: a claim nobody made must not be printed as if somebody had."""
    decision = gate.decide(metrics("c", mae=V1_TEST_MAE, within=99.0), floor(), GATE_CFG)

    default = gate.verdict_lines(decision)
    assert "untouched by training" in default
    assert "by selection" not in default

    earned = gate.verdict_lines(decision, holdout_untouched_by_selection=True)
    assert "untouched by training and by selection" in earned

    # Both forms keep the shape `verify-m2` parses out of the committed M2/M3
    # transcripts — a repaired claim must not orphan the record it was made in.
    for text in (default, earned):
        assert re.search(r"holdout\s+: \w+ — [\d,]+ rows", text)


def test_the_single_challenger_paths_are_the_ones_that_claim_selection_purity():
    """Prevents the fix being cosmetic: `make train` and the incumbent red team
    fit or construct exactly ONE challenger, so they earn the claim; the bake-off
    ranks contenders and must not. Checked in the source because the alternative
    is running three cluster-bound commands to read one keyword argument."""
    run_src = (REPO / "src/taxi_mlops/training/run.py").read_text()
    redteam_src = (REPO / "scripts/gate_redteam_incumbent.py").read_text()
    bakeoff_src = (REPO / "scripts/bakeoff_m3.py").read_text()

    assert "verdict_lines(decision, holdout_untouched_by_selection=True)" in run_src
    assert "verdict_lines(decision, holdout_untouched_by_selection=True)" in redteam_src
    assert "verdict_lines(decision, holdout_untouched_by_selection=False)" in bakeoff_src


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
    # `incumbent_version` defaults to whatever the fake's alias actually holds:
    # the honest caller states what the gate compared against, and the tests that
    # are ABOUT the bypass pass it explicitly.
    kw.setdefault("incumbent_version", client.alias_at)
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
            FakeClient(),
            model_name="m",
            alias="champion",
            run_id="r",
            incumbent_version=None,
            model_info=boom,
        )


# -------------------------------- the alias may not be moved by a decision that
# -------------------------------- never read what it points at (F-011, part 2) ---
def test_a_promotion_that_never_consulted_the_incumbent_cannot_move_the_alias():
    """`gate.decide` takes its incumbent OPTIONALLY — the first promotion has
    none, and M2's replayed verdicts carry none. This is what stops "optional"
    from meaning "skippable": the mutating half re-reads the alias itself."""
    client = FakeClient(versions=[FakeVersion(1, "run-1")], alias_at="1")
    with pytest.raises(registry.PromotionError, match="F-011"):
        promote(client, run_id="run-2", incumbent_version=None)
    assert client.alias_at == "1", "the alias moved despite the refusal"
    assert "set_registered_model_alias" not in client.calls


def test_a_promotion_decided_against_a_stale_champion_is_refused():
    """Two runs that both passed against version 1 cannot both replace it: the
    second one's acknowledgement is stale by the time it reaches the registry."""
    client = FakeClient(versions=[FakeVersion(1, "a"), FakeVersion(2, "b")], alias_at="2")
    with pytest.raises(registry.PromotionError, match="points at version 2"):
        promote(client, run_id="run-3", incumbent_version="1")
    assert client.alias_at == "2"


def test_a_first_promotion_states_that_there_was_no_incumbent():
    client = FakeClient(model_exists=False)
    result = promote(client, incumbent_version=None)
    assert result.alias_moved and client.alias_at == "1"


def test_a_promotion_claiming_an_incumbent_that_is_gone_is_refused():
    """The alias was deleted underneath the run (the verify-m2 red team does
    exactly this). Promoting anyway would hide that something moved it."""
    client = FakeClient(versions=[FakeVersion(1, "run-1")], alias_at=None)
    with pytest.raises(registry.PromotionError, match="not set"):
        promote(client, run_id="run-2", incumbent_version="1")
    assert client.alias_at is None


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


# ------------------------- F-068: the identity case under any incumbent margin ---
# These pinned the ARITHMETIC of a finding while `gate.decide` had no incumbent
# margin — they existed so that whoever landed F-016 option B could not land it
# without meeting the case that stopped it (F-068, AWAITING_PO 2026-08-24-4).
# M9-S10 landed it, so they are UPDATED to the landed behaviour rather than
# deleted: the case they pinned is now the behaviour they assert.
def test_a_challenger_identical_to_the_incumbent_is_exactly_zero_and_therefore_refused():
    """The pre-registered rule, and the number the whole finding turns on.

    M3-S1 re-fitted v1 on full data and measured 3.2608 — the incumbent's own
    recorded value — and M3-S5's bake-off scored the serving champion as one of
    its five contenders, so both carry a challenger judged against ITSELF. Under
    non-regression-with-no-margin that was a PASS at +0.0000% and both are
    RECORDED as PROMOTE; under the landed margin both are REFUSED, which is why
    those two rows are replayed era-aware (`gate_eras`) rather than re-judged.
    """
    same = metrics("lightgbm-v1", mae=V1_TEST_MAE, within=V1_TEST_WITHIN)
    assert gate.improvement_pct(same.mae, incumbent().mae) == 0.0
    assert not gate.decide(same, floor(), GATE_CFG, incumbent=incumbent()).passed
    # ...and it is the MARGIN that refuses it: under the era that was in force
    # when those two verdicts were taken, the same numbers still promote.
    pre_b = {**GATE_CFG, "incumbent_min_improvement_pct": gate_eras.PRE_B_MARGIN_PCT}
    assert gate.decide(same, floor(), pre_b, incumbent=incumbent()).passed


def test_the_identity_case_is_refused_by_ANY_positive_incumbent_margin():
    """Why F-016 option B's number is not the thing that stopped it.

    0.50% was the PO's choice, but the two flipped replays sit at exactly
    +0.0000% — so a margin of one ten-thousandth of a percent refuses them too.
    The identity case must be answered by whatever lands, at whatever bar; a
    smaller number is not a way around it.
    """
    same = metrics("lightgbm-v1", mae=V1_TEST_MAE, within=V1_TEST_WITHIN)
    observed = gate.improvement_pct(same.mae, incumbent().mae)
    for margin in (0.001, 0.10, 0.50, 2.00):
        assert observed < margin, (
            f"a challenger identical to the incumbent clears a {margin}% margin — "
            "then F-068's premise is wrong and the finding should be re-read"
        )


def test_the_nearest_surviving_recorded_verdict_has_six_hundredths_of_a_point_of_daylight():
    """`artisan v2` is the row that says how close 0.50% runs to history.

    M3-S5 recorded it PROMOTE at 3.2425 against incumbent v1's 3.2608 —
    +0.5612%. It survives 0.50% and dies at 0.57%. That margin of safety is a
    number the PO's answer is entitled to see, so it is asserted rather than
    remembered.
    """
    artisan = metrics("artisan-v2", mae=3.2425, within=81.582)
    observed = gate.improvement_pct(artisan.mae, incumbent().mae)
    assert 0.50 <= observed < 0.57
    assert round(observed, 4) == 0.5612
    # ...and it is a RECORDED PROMOTE that survives the landed bar, which is the
    # half that says 0.50 was chosen with history in view rather than around it.
    assert gate.decide(artisan, floor(), GATE_CFG, incumbent=incumbent()).passed


# ------------------- M9-S10: the incumbent MARGIN, from both sides and the edges ---
def test_a_challenger_that_beats_the_champion_by_less_than_the_margin_is_refused_BY_NAME():
    """+0.3% — a real improvement, and not one worth a transition.

    0.3% of 3.2608 min is ~0.6 seconds of mean error. The refusal must NAME the
    bar, because "refused" with no number is what teaches a reader to stop
    reading refusals.
    """
    near = metrics("challenger-just-short", mae=V1_TEST_MAE * (1 - 0.003), within=V1_TEST_WITHIN)
    decision = gate.decide(near, floor(), GATE_CFG, incumbent=incumbent())
    assert not decision.passed
    failed = [c for c in decision.checks if not c.passed]
    assert len(failed) == 1 and "serving champion" in failed[0].name
    assert "required >= 0.50%" in failed[0].detail and "+0.30% vs incumbent" in failed[0].detail


def test_the_transition_this_program_actually_made_would_still_be_made():
    """+0.63% — M3-S5's alias move, the one observation the PO's number was set
    below rather than above. A margin that would have refused the program's own
    only transition is a bar chosen from the wrong end."""
    winner = metrics("auto-lgbm-v2", mae=3.2403, within=81.577)
    decision = gate.decide(winner, floor(), GATE_CFG, incumbent=incumbent())
    assert decision.passed
    assert gate.improvement_pct(winner.mae, incumbent().mae) == pytest.approx(0.63, abs=0.01)


def test_the_margin_boundary_is_inclusive_from_both_sides():
    """`>=`, tested either side by two ten-thousandths of a minute — the M2
    precedent (a test written exactly ON the boundary asserts IEEE 754 rather
    than the gate)."""
    required = float(GATE_CFG["incumbent_min_improvement_pct"])
    exact = round(V1_TEST_MAE * (1 - required / 100), gate.INCUMBENT_MAE_DECIMALS)
    over = metrics("just-over", mae=exact - 0.0002, within=V1_TEST_WITHIN)
    under = metrics("just-under", mae=exact + 0.0002, within=V1_TEST_WITHIN)
    assert gate.decide(over, floor(), GATE_CFG, incumbent=incumbent()).passed
    assert not gate.decide(under, floor(), GATE_CFG, incumbent=incumbent()).passed


def test_an_absent_margin_RAISES_rather_than_defaulting_when_an_incumbent_is_present():
    """F-048's rule, on the one value where a default is indistinguishable from
    the old behaviour: zero IS plain non-regression, so a `.get(key, 0.0)` would
    silently un-land this whole story for any caller that assembled a config by
    hand."""
    without = dict(GATE_CFG)
    without.pop("incumbent_min_improvement_pct")
    with pytest.raises(gate.GateError) as raised:
        gate.decide(metrics("x", mae=3.0), floor(), without, incumbent=incumbent())
    assert "incumbent_min_improvement_pct" in str(raised.value)
    # ...and with no incumbent there is no margin to apply, so the same config
    # judges the floor conditions perfectly well. The raise is scoped to the
    # comparison that needs the number, not to the config's shape.
    assert gate.decide(metrics("x", mae=3.0, within=99.0), floor(), without).passed


def _with_margin(margin: float) -> dict:
    cfg = dict(GATE_CFG)
    cfg["incumbent_min_improvement_pct"] = margin
    return cfg


def test_every_verdict_records_the_bar_it_was_judged_under():
    """The recorded field, in the places a future replay could read it.

    `None` exactly when there was no incumbent — the state that means "there was
    nothing to beat", never the state that means "nobody wrote the bar down".
    """
    decision = gate.decide(
        metrics("v2", mae=V1_TEST_MAE - 0.1, within=V1_TEST_WITHIN + 0.5),
        floor(),
        GATE_CFG,
        incumbent=incumbent(),
    )
    assert decision.incumbent_required_pct == float(GATE_CFG["incumbent_min_improvement_pct"])
    assert decision.as_mlflow()["gate_incumbent_required_pct"] == decision.incumbent_required_pct
    parsed = gate_eras.parse_recorded_margin(gate.verdict_lines(decision).splitlines())
    assert parsed == decision.incumbent_required_pct
    first_promotion = gate.decide(metrics("v1", mae=V1_TEST_MAE), floor(), GATE_CFG)
    assert first_promotion.incumbent_required_pct is None
    assert "gate_incumbent_required_pct" not in first_promotion.as_mlflow()
    assert gate_eras.parse_recorded_margin(gate.verdict_lines(first_promotion).splitlines()) is None


def test_the_transcript_line_and_the_replay_regex_are_twins():
    """`gate.verdict_lines` writes it and `gate_eras.MARGIN_RE` reads it. Two
    files, one sentence — the port-family lesson applied to a transcript, and
    the failure it prevents is silent: a changed line makes a RECORDED margin
    read as an absence, which is the one inference this story exists to remove.
    """
    source = (REPO / "src/taxi_mlops/training/gate.py").read_text(encoding="utf-8")
    assert "[gate] incumbent bar: KPI-09 at least " in source
    for margin in (0.0, 0.5, 2.0):
        decision = gate.decide(
            metrics("x", mae=1.0, within=99.0),
            floor(),
            _with_margin(margin),
            incumbent=incumbent(),
        )
        rendered = gate.verdict_lines(decision).splitlines()
        assert gate_eras.parse_recorded_margin(rendered) == margin


def test_the_recorded_margin_reaches_the_version_tags_and_the_retrain_record():
    """Where a replay would actually look: both writers name the field, so a
    verdict recorded by either is unambiguous about its own bar."""
    promote = (REPO / "src/taxi_mlops/training/run.py").read_text(encoding="utf-8")
    assert '"gate_incumbent_required_pct"' in promote
    retrain = (REPO / "src/taxi_mlops/training/retrain_run.py").read_text(encoding="utf-8")
    assert '"incumbent_required_pct": decision.incumbent_required_pct' in retrain
