"""M7-S4: the retrain challenger — F-020's transfer, and the laws it may not break.

Every test here is about a property that has no other symptom. A wrongly-rescaled
knob does not raise; it produces a model that is merely different, reported beside
3.2403 as though the two were the same configuration at two scales.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

from taxi_mlops.training import retrain as R

REPO = Path(__file__).resolve().parents[2]
SOURCE = (REPO / "src/taxi_mlops/training/retrain.py").read_text()
RUN_SOURCE = (REPO / "src/taxi_mlops/training/retrain_run.py").read_text()


# ------------------------------------------------------ F-020, half one: scale ----


def test_count_scaled_knobs_are_rescaled_by_the_row_ratio():
    """Prevents F-020 recurring: a leaf floor chosen on a sample and applied whole.

    The numbers are M3-S4's own — `min_data_in_leaf: 1293` chosen on the sniper's
    6,598,113-row sample and applied to the 43,987,422-row refit."""
    params = {"min_data_in_leaf": 1293, "num_leaves": 535, "learning_rate": 0.1193}
    out, moves = R.rescale(params, chosen_at_rows=6_598_113, target_rows=43_987_422)
    assert out["min_data_in_leaf"] == 8620
    # The transfer's definition: the knob means the same FRACTION at both scales.
    before = 6_598_113 / 1293
    after = 43_987_422 / out["min_data_in_leaf"]
    assert abs(after - before) / before < 0.001
    # And the thing F-020 measured, reproduced: unchanged it would have been ~6.7x
    # weaker at the scale it was fitted at.
    assert round(43_987_422 / 1293) == 34_020
    assert [m["knob"] for m in moves] == ["min_data_in_leaf"]


def test_nothing_that_is_not_a_row_count_is_touched():
    """Prevents: a 'transfer' that rescales the model instead of the scale.

    `num_leaves` at 44M rows means what it meant at 6.6M. Multiplying it by 6.67
    would invent a different model and file it as a scale correction."""
    params = {"num_leaves": 535, "learning_rate": 0.1193, "feature_fraction": 0.898,
              "bagging_fraction": 0.886, "lambda_l1": 4.6e-08, "lambda_l2": 1.7e-05,
              "max_cat_threshold": 27, "cat_smooth": 64.36}
    out, moves = R.rescale(params, chosen_at_rows=6_598_113, target_rows=43_987_422)
    assert out == params
    assert moves == []


def test_every_count_scaled_knob_carries_its_reason():
    """Prevents: a knob added to the list because it looked numeric. The list is a
    claim about LightGBM's semantics and each entry must argue it."""
    assert R.COUNT_SCALED
    for knob, reason in R.COUNT_SCALED.items():
        assert len(reason) > 40, knob
        assert "row" in reason.lower(), f"{knob}: the reason must say why it is a row count"


def test_an_absent_search_scale_is_a_reported_no_op_and_never_a_guess():
    """Prevents: a divisor invented for a champion that came from no sampled search.

    F-020 IS the finding that assuming a sample fraction produces a plausible
    configuration nobody can check. So `chosen_at_rows=None` leaves the knob alone
    and says so in the record — silence would be indistinguishable from a transfer
    that happened to be the identity."""
    out, moves = R.rescale({"min_data_in_leaf": 1293}, chosen_at_rows=None,
                           target_rows=43_987_422)
    assert out["min_data_in_leaf"] == 1293
    assert len(moves) == 1 and moves[0]["factor"] is None
    assert "no scale transfer" in moves[0]["reason"]


def test_an_integer_knob_stays_an_integer_and_never_reaches_zero():
    out, _ = R.rescale({"min_data_in_leaf": 5}, chosen_at_rows=43_987_422,
                       target_rows=1_000)
    assert out["min_data_in_leaf"] == 1 and isinstance(out["min_data_in_leaf"], int)


# ----------------------------------------------------- F-020, half two: rounds ----


def test_the_round_budget_is_re_derived_and_never_inherited():
    """Prevents: a refit whose budget is a SEARCH parameter. The sniper's 800 is a
    per-trial cap at 15% and both M3 refits ran into it (800/800 and 791/800)."""
    derived, note = R.round_budget(800, 500)
    assert derived == 800 * R.ROUND_BUDGET_HEADROOM
    assert "PER-TRIAL" in note and "compute bound" in note


def test_a_re_derived_budget_is_never_smaller_than_the_configured_one():
    """A cap can only ever be too small. `configs/train.yaml` is the floor."""
    assert R.round_budget(100, 500)[0] == 500
    assert R.round_budget(None, 500) == (500, R.round_budget(None, 500)[1])
    assert "nothing to re-derive" in R.round_budget(None, 500)[1]


def test_whether_the_cap_bound_the_fit_is_reported_not_inferred(monkeypatch):
    """Prevents the half of F-020 a results table cannot show: 791 of 800 and a
    converged fit look identical in a metrics row. `ended_by` is a field."""
    assert '"ended_by"' in RUN_SOURCE or "'ended_by'" in RUN_SOURCE
    assert "round_cap" in RUN_SOURCE and "early_stopping" in RUN_SOURCE
    assert "TRUNCATED" in RUN_SOURCE


# --------------------------------------------- the generated config is not a home ----


def test_every_block_but_model_is_copied_from_train_yaml_verbatim():
    """Prevents: a GENERATED config becoming a second home for the gate (F-013).

    The whole point of a synthesized training config is that only the model block
    is synthesized. If this ever admitted a `gate` of its own, a retrain could be
    judged against a bar nobody reviewed."""
    raw = yaml.safe_load((REPO / "configs/train.yaml").read_text())
    prov = R.Provenance(
        champion_version="2", champion_run_id="r", champion_run_name="auto-lgbm-v2",
        feature_set="v2", tuned_params={"min_data_in_leaf": 1293, "num_leaves": 535},
        chosen_at_rows=6_598_113, chosen_at_source="s", inherited_round_cap=800,
        inherited_round_cap_source="s",
    )
    cfg, record = R.build_config(raw, prov, target_rows=43_987_422, name="probe")
    for block in R.COPIED_VERBATIM:
        assert cfg[block] == raw[block], block
    assert set(cfg) == set(R.COPIED_VERBATIM) | {"model"}
    assert "gate" in R.COPIED_VERBATIM and "data" in R.COPIED_VERBATIM
    assert cfg["gate"] == raw["gate"]
    # The training WINDOW is copied too: moving it into 2020 changes what the
    # holdout measures and is an ARCH/PO question, not a generated default.
    assert cfg["data"]["train_months"] == raw["data"]["train_months"]
    assert cfg["data"]["test_month"] == raw["data"]["test_month"]
    assert record["round_budget"]["derived"] == 2400


def test_the_tuned_params_sit_on_top_of_the_configured_base_and_never_replace_it():
    """Prevents: a tuned dict used as the WHOLE param set, silently dropping
    `objective: l1` — the loss KPI-09 is defined as — and every determinism knob."""
    raw = yaml.safe_load((REPO / "configs/train.yaml").read_text())
    prov = R.Provenance(
        champion_version="2", champion_run_id="r", champion_run_name="n", feature_set="v2",
        tuned_params={"num_leaves": 535}, chosen_at_rows=None, chosen_at_source=None,
        inherited_round_cap=None, inherited_round_cap_source=None,
    )
    cfg, _ = R.build_config(raw, prov, target_rows=10, name="probe")
    lgb = cfg["model"]["lightgbm"]
    assert lgb["objective"] == "l1" and lgb["metric"] == "l1"
    assert lgb["deterministic"] is True and "seed" in lgb
    assert lgb["num_leaves"] == 535, "the tuned value must win over the base"


def test_recorded_fit_metadata_is_not_passed_to_lightgbm_as_a_parameter():
    """Prevents: `best_iteration` / `train_rows` reaching LightGBM as knobs. They
    are what the fitting script recorded ABOUT the fit; one is ignored and one is
    not, and neither failure prints anything."""
    assert {"best_iteration", "train_rows", "num_boost_round"} <= R.NOT_HYPERPARAMETERS


# ---------------------------------------------------------------- the laws ----


def test_the_retrain_can_never_promote():
    """Prevents the one thing an unattended scheduled job must not be able to do.

    Asserted on the parsed call, not on the text: this module argues at length
    about promotion, so a grep would pass on the argument (#53/#68)."""
    tree = ast.parse(RUN_SOURCE)
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "run"]
    assert calls, "retrain_run must call taxi_mlops.training.run"
    for call in calls:
        promote = [kw for kw in call.keywords if kw.arg == "promote"]
        assert promote, "promote must be passed EXPLICITLY, never left to a default"
        assert promote[0].value.value is False
    # And no parameter of `retrain` may switch it — a law with a keyword argument
    # is a default (tasks.train's rule, inherited).
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "retrain")
    names = [a.arg for a in fn.args.args + fn.args.kwonlyargs]
    assert "promote" not in names


def test_the_retrain_names_no_registry_write_verb():
    """Prevents: a second promotion path. `registry.promote` and the raw alias
    setter are both mutations; a retrain reads the registry and nothing else."""
    for source in (SOURCE, RUN_SOURCE):
        tree = ast.parse(source)
        called = {
            node.func.attr for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        forbidden = {"set_registered_model_alias", "delete_registered_model_alias",
                     "create_model_version", "register_model", "promote",
                     "transition_model_version_stage", "set_model_version_tag"}
        assert not (called & forbidden), called & forbidden


def test_a_sampled_retrain_is_not_entitled_to_a_verdict():
    """F-008, inherited rather than re-implemented: `judge=not sampled` is passed to
    the one module that owns the rule."""
    tree = ast.parse(RUN_SOURCE)
    call = next(n for n in ast.walk(tree)
                if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "run")
    judge = next(kw for kw in call.keywords if kw.arg == "judge")
    assert isinstance(judge.value, ast.UnaryOp) and isinstance(judge.value.op, ast.Not)


def test_the_row_count_is_measured_and_never_typed():
    """Prevents: F-020's divisor becoming a constant that stops being true the
    first time a month is re-ingested."""
    assert "43_987_422" not in RUN_SOURCE and "43987422" not in RUN_SOURCE
    assert "num_rows" in RUN_SOURCE


def test_the_exit_codes_say_which_kind_of_silence_this_was():
    """Prevents a scheduler confusing 'refused' with 'not judged' (M3-S1's F-008
    landing). 0 = a verdict that passed · 1 = refused · 2 = could not build ·
    3 = no verdict was issued."""
    cli = (REPO / "src/taxi_mlops/training/__main__.py").read_text()
    block = cli.split('if args.command == "retrain":')[1]
    assert "return 3" in block, "3 = no verdict was issued (F-008)"
    assert "return 2" in block, "2 = the challenger could not be built"
    assert 'return 0 if verdict["passed"] else 1' in block, "0 = passed · 1 = refused"
    assert "F-008" in block


# ---------------------------------------------------------------- wiring ----


def test_the_make_targets_exist_and_the_default_promotes_nothing():
    makefile = (REPO / "Makefile").read_text()
    line = next(ln for ln in makefile.splitlines() if ln.startswith("retrain:"))
    assert "Promotes NOTHING" in line
    assert "--promote" not in makefile.split("retrain:")[1].splitlines()[1]
    assert "retrain-schedule:" in makefile


def test_the_schedule_is_declared_in_code_with_its_inputs():
    """Prevents: a cadence that lives in somebody's shell history.

    `flyte create trigger` cannot pass task inputs, so a CLI-created trigger would
    fire the retrain with its DEFAULTS. Declared triggers carry the cadence, the
    inputs and the reasoning as one reviewable object."""
    wf = (REPO / "pipelines/flyte/workflows.py").read_text()
    tree = ast.parse(wf)
    triggers = [n for n in ast.walk(tree)
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute) and n.func.attr == "Trigger"]
    assert len(triggers) == 2, "the production cadence and the cheap firing proof"
    for call in triggers:
        kwargs = {kw.arg for kw in call.keywords}
        assert {"name", "automation", "inputs", "description"} <= kwargs
    activations = [kw.value.value for call in triggers for kw in call.keywords
                   if kw.arg == "auto_activate"]
    assert activations == [False], (
        "exactly one trigger declares auto_activate, and it is the monthly one "
        "turning itself OFF: a full-data retrain firing unattended on a laptop "
        "spends hours of CPU to produce a verdict nobody reads"
    )


def test_the_scheduled_task_is_uncached_and_unretried():
    """A cached retrain would answer 'what is serving?' from a cache — wrong
    precisely when the alias has moved, which is the only time anyone asks."""
    wf = (REPO / "pipelines/flyte/workflows.py").read_text()
    tree = ast.parse(wf)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.AsyncFunctionDef) and n.name == "retrain")
    deco = next(d for d in fn.decorator_list if isinstance(d, ast.Call))
    kwargs = {kw.arg: kw.value for kw in deco.keywords}
    assert kwargs["cache"].value == "disable"
    assert kwargs["retries"].value == 0
    assert "triggers" in kwargs


def test_the_schedule_script_refuses_a_stale_image():
    """A trigger fires forever. A schedule registered against an image the tree has
    outgrown runs code nobody can identify — F-026 one cadence up."""
    script = (REPO / "scripts/retrain_schedule.sh").read_text()
    assert "F-026" in script and "exit 3" in script
    assert "pipelines" in script.split("IMAGE_PATHS=(")[1].split(")")[0]
    assert "get trigger" in script, "the triggers are read back off the SERVER"


@pytest.mark.parametrize("knob", sorted(R.COUNT_SCALED))
def test_the_count_scaled_list_names_only_real_lightgbm_parameters(knob):
    """Prevents: a knob rescaled under a name LightGBM does not know, which it
    accepts and ignores — a transfer that reports itself as done and did nothing."""
    known = {"min_data_in_leaf", "min_child_samples", "min_data_in_bin",
             "min_sum_hessian_in_leaf", "min_child_weight"}
    assert knob in known
