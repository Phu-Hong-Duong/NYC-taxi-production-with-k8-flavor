"""M3-S5: the bake-off's cluster-free invariants.

The expensive half of this story — five contenders on the untouched test month —
cannot run here: it needs the cluster, the registry and ~50M rows. What CAN run
here is everything that decides whether those numbers mean anything: that the 2x2
is complete and was declared before it was measured, that no contender is
identified by a run id typed into the file, that the script re-fits nothing, that
a model which fails to reproduce its own recorded val number is refused, that a
second run cannot quietly disagree with the first, and that the alias cannot move
to a model `configs/train.yaml` does not describe.

Each test's docstring names the failure it prevents.
"""

import ast
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "bakeoff_m3.py"


def _load():
    spec = importlib.util.spec_from_file_location("bakeoff_m3", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    # Registered BEFORE exec: `dataclasses` resolves a string annotation by
    # looking the defining module up in `sys.modules`, so a module that is only
    # exec'd dies on the first `field(default_factory=...)` with an AttributeError
    # about NoneType. `scripts/derive_zone_centroids.py` gets away without this
    # because it declares no dataclass.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def bakeoff():
    return _load()


@pytest.fixture(scope="module")
def source():
    return SCRIPT.read_text()


pytestmark = pytest.mark.unit


# ------------------------------------------------- the square, pre-registered ----


def test_the_square_is_complete_and_declared(bakeoff):
    """Prevents: a cell quietly missing from the 2x2, so 'features or tuning?' is
    answered from three numbers and a guess."""
    cells = {
        (spec.feature_set, spec.track)
        for spec in bakeoff.CONTENDERS
        if spec.track != "floor"
    }
    assert cells == {("v1", "artisan"), ("v2", "artisan"),
                     ("v1", "automation"), ("v2", "automation")}
    floors = [spec for spec in bakeoff.CONTENDERS if spec.track == "floor"]
    assert len(floors) == 1, "the gate's floor is the fifth row and there is exactly one"
    assert len(bakeoff.CONTENDERS) == 5


def test_the_two_search_axes_stay_disjoint(bakeoff):
    """Prevents: DR-03 quietly breaking — the artisan arms must hold v1's
    hyperparameters and the automation arms must not invent feature sets. If both
    tracks moved both axes, no delta in the square isolates anything."""
    by_track = {spec.label: spec for spec in bakeoff.CONTENDERS}
    assert "hand" in by_track["artisan v2"].hyperparameters
    assert "tuned" in by_track["auto-on-v1"].hyperparameters
    assert "tuned" in by_track["auto-on-v2"].hyperparameters
    assert by_track["champion v1"].feature_set == by_track["auto-on-v1"].feature_set
    assert by_track["artisan v2"].feature_set == by_track["auto-on-v2"].feature_set


def test_f015_is_attached_to_the_row_it_belongs_to_and_to_no_other(bakeoff):
    """Prevents: the truncation caveat being spread across both automation arms.

    Session (aj) measured the difference: auto-on-v1 gained 0.02808 MAE over its
    last 100 rounds under the cap and auto-on-v2 gained 0.00034 — ~82x less slope.
    A cap is a truncation only if the curve is still moving under it, so the
    contender that had earned no caveat must not be given one."""
    by_label = {spec.label: spec for spec in bakeoff.CONTENDERS}
    v1_caveats = " ".join(by_label["auto-on-v1"].caveats)
    v2_caveats = " ".join(by_label["auto-on-v2"].caveats)
    assert "F-015" in v1_caveats and "MID-DESCENT" in v1_caveats
    assert "F-015" in v2_caveats and "does NOT attach" in v2_caveats
    assert not by_label["champion v1"].caveats and not by_label["artisan v2"].caveats


def test_no_contender_is_identified_by_a_hardcoded_run_id(source):
    """Prevents: a 32-hex id pasted into the script. It would be correct today and
    a silent lie the first time an experiment is re-run — the champion must come
    from the ALIAS, the automation arms from the JSON their own track wrote."""
    ids = re.findall(r"\b[0-9a-f]{32}\b", source)
    assert not ids, f"the bake-off names run ids directly: {ids}"
    kinds = {spec.source[0] for spec in _load().CONTENDERS}
    assert kinds == {"floor", "registry-alias", "mlflow-run", "refit-json"}


# ---------------------------------------------------- it re-fits nothing ----


def test_the_bakeoff_fits_no_model(source):
    """Prevents: the bake-off quietly re-fitting a contender. A re-fit is a
    different MLflow run, and the version this promotes must be the version this
    measured — M3-S4's refit script logged its models precisely so that S5 would
    not have to."""
    body = "\n".join(
        line for line in source.splitlines() if not line.strip().startswith("#")
    )
    for forbidden in ("lgb.train", "xgb.train", "model_mod.fit", "fit_mod.fit",
                      "model.fit(", "TunedModel.fit"):
        assert forbidden not in body, f"the bake-off calls {forbidden}"
    # The one exception, and it is required by gate.py's second property: the
    # FLOOR is re-derived from the challenger's own training data in this run.
    assert "baselines.fit_floor" in body


def test_the_bakeoff_names_no_registry_write_api(source):
    """Prevents: a second promotion path. The alias moves through `run._promote`
    — the same function `make train` calls, with the same tags and the same
    `registry.promote` refusals — or it does not move."""
    tree = ast.parse(source)
    called = {
        node.func.attr for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    for mutator in ("set_registered_model_alias", "delete_registered_model_alias",
                    "create_model_version", "create_registered_model",
                    "delete_model_version", "set_model_version_tag", "delete_run"):
        assert mutator not in called, f"the bake-off calls {mutator} itself"
    assert "_promote" in source


# ------------------------------------------------------- the admission check ----


class _Metrics:
    def __init__(self, mae):
        self.mae = mae


def _item(bakeoff, label, recorded, measured):
    spec = next(s for s in bakeoff.CONTENDERS if s.label == label)
    item = bakeoff.Loaded(spec=spec, name=label, run_id="r", family="lgbm",
                          recorded_val_mae=recorded, best_iteration=1)
    item.metrics = {"val": _Metrics(measured)}
    return item


def test_a_contender_that_cannot_reproduce_its_val_number_is_refused(bakeoff):
    """Prevents: the strongest failure this script has no other symptom for — the
    artifact loaded is not the artifact the published val number describes, or
    this file builds features differently from the path that fitted it. Either
    way every test number below would describe a model nobody can identify."""
    items = [_item(bakeoff, "artisan v2", 3.3905388307148137, 3.3905388307148137),
             _item(bakeoff, "auto-on-v2", 3.3822796832477016, 3.3900000000000000)]
    with pytest.raises(SystemExit) as excinfo:
        bakeoff._assert_val_reproduced(items, smoke=False)
    assert "auto-on-v2" in str(excinfo.value)
    assert "artisan v2" not in str(excinfo.value), "only the failing row is named"


def test_float64_noise_over_six_million_rows_is_not_a_mismatch(bakeoff):
    """Prevents: the opposite failure — a tolerance so tight that summation noise
    reads as a defect. The tolerance is for float64, not for disagreement."""
    tiny = bakeoff.VAL_REPRODUCTION_TOLERANCE / 10
    items = [_item(bakeoff, "artisan v2", 3.3905388307148137, 3.3905388307148137 + tiny)]
    bakeoff._assert_val_reproduced(items, smoke=False)  # must not raise
    assert bakeoff.VAL_REPRODUCTION_TOLERANCE <= 1e-8, (
        "anything looser stops being a check on identity"
    )


def test_a_smoke_run_reports_mismatches_and_enforces_nothing(bakeoff):
    """Prevents: the smoke path failing for the one reason it is expected to. A
    truncated split cannot reproduce a full-data number and must not pretend to —
    and it must not be able to launder a real mismatch either, which is why a
    smoke run writes no JSON and promotes nothing."""
    items = [_item(bakeoff, "auto-on-v2", 3.3822796832477016, 4.4)]
    bakeoff._assert_val_reproduced(items, smoke=True)  # must not raise
    source = SCRIPT.read_text()
    assert "SMOKE: no JSON written, nothing promoted" in source


# -------------------------------------------------- a second run must agree ----


def _payload(test_mae):
    return {
        "holdout_split": "test",
        "contenders": [
            {"label": "auto-on-v2", "val_mae": 3.38, "test_mae": test_mae,
             "test_within_rate": 80.0},
        ],
    }


def test_a_second_run_that_measures_something_else_is_refused(bakeoff, tmp_path):
    """Prevents: the promoting invocation quietly disagreeing with the read-only
    one. Same artifacts, same rows, same evaluator — the numbers are deterministic,
    so a difference is a change nobody declared."""
    path = tmp_path / "bakeoff.json"
    bakeoff._write(path, _payload(3.1))
    with pytest.raises(SystemExit) as excinfo:
        bakeoff._write(path, _payload(3.2))
    assert "3.1 -> 3.2" in str(excinfo.value)
    assert json.loads(path.read_text())["contenders"][0]["test_mae"] == 3.1


def test_a_second_run_that_reproduces_is_accepted(bakeoff, tmp_path):
    """Prevents: the drift guard being so strict that the reproduction proof
    cannot be taken at all."""
    path = tmp_path / "bakeoff.json"
    bakeoff._write(path, _payload(3.1))
    bakeoff._write(path, _payload(3.1))
    assert json.loads(path.read_text())["contenders"][0]["test_mae"] == 3.1


# ---------------------------------------------- the alias and the config line ----


class _Decision:
    def __init__(self, passed):
        self.passed = passed


def test_a_refused_winner_moves_nothing_and_exits_nonzero(bakeoff):
    """Prevents: a bake-off with no winner good enough being read as a promotion.
    The gate's refusal must reach the shell, exactly as `make train`'s does."""
    spec = next(s for s in bakeoff.CONTENDERS if s.label == "auto-on-v2")
    winner = bakeoff.Loaded(spec=spec, name="auto-lgbm-v2", run_id="r", family="lgbm",
                            recorded_val_mae=3.38, best_iteration=791)
    assert bakeoff._promote_winner(winner, _Decision(False), {"features": {"version": "v2"}}) == 1


def test_the_alias_cannot_move_to_a_model_the_config_does_not_describe(bakeoff):
    """Prevents: minting a champion version the next `make predictions` refuses to
    score. `score.py` compares the champion's feature names against
    `configs/train.yaml: features`, and `verify-m2` checks the same line — so the
    config moves as PART of a promotion (M3-S3's law) or the promotion does not
    happen."""
    spec = next(s for s in bakeoff.CONTENDERS if s.label == "auto-on-v2")
    winner = bakeoff.Loaded(spec=spec, name="auto-lgbm-v2", run_id="r", family="lgbm",
                            recorded_val_mae=3.38, best_iteration=791)
    with pytest.raises(SystemExit) as excinfo:
        bakeoff._promote_winner(winner, _Decision(True), {"features": {"version": "v1"}})
    message = str(excinfo.value)
    assert "features.version" in message and "'v1'" in message and "'v2'" in message


# --------------------------------------- F-018: where the winner is ranked ----


def _ranked(bakeoff, rows):
    """Build `Loaded` rows carrying only the two numbers the ranking can see."""
    from taxi_mlops.training.evaluate import Metrics

    def m(split, mae):
        return Metrics(contender="x", split=split, n=10, mae=mae, within_tolerance_rate=80.0,
                       tolerance_minutes=5.0, rmse=0.0, median_ae=0.0, p90_ae=0.0)

    loaded = []
    for label, val_mae, test_mae in rows:
        spec = next(s for s in bakeoff.CONTENDERS if s.label == label)
        item = bakeoff.Loaded(spec=spec, name=label, run_id="r", family="lgbm",
                              recorded_val_mae=val_mae, best_iteration=1)
        item.metrics["val"] = m("val", val_mae)
        item.metrics["test"] = m("test", test_mae)
        loaded.append(item)
    return loaded


def test_the_winner_is_ranked_on_val_even_when_the_holdout_disagrees(bakeoff):
    """Prevents F-018's regression: ranking five contenders by their HOLDOUT MAE
    and then gating the winner on the same month. The rows below are built so the
    two splits DISAGREE — `artisan v2` wins val, `auto-on-v2` wins test — because
    a test where they agree (which is what M3-S5 actually observed) cannot tell
    the two rules apart, and that is exactly why the defect survived a bake-off
    everybody read."""
    loaded = _ranked(bakeoff, [
        ("floor", 9.9, 9.9),
        ("champion v1", 3.4760, 3.2608),
        ("artisan v2", 3.3800, 3.2500),   # best on val
        ("auto-on-v2", 3.3900, 3.2000),   # best on test
    ])
    winner = bakeoff._select_winner(loaded, "test")
    assert winner.spec.label == "artisan v2"
    assert bakeoff.SELECTION_SPLIT == "val"


def test_the_floor_is_the_bar_and_never_a_candidate_to_serve(bakeoff):
    """Prevents: a floor so good it takes the alias. `loaded[0]` is the bar; it
    still gets a holdout number and a verdict of its own, but it is not ranked."""
    loaded = _ranked(bakeoff, [
        ("floor", 0.1, 0.1),             # absurdly good, still not a candidate
        ("champion v1", 3.4760, 3.2608),
        ("artisan v2", 3.3800, 3.2500),
    ])
    assert bakeoff._select_winner(loaded, "test").spec.label == "artisan v2"


def test_the_selection_happens_before_the_holdout_is_scored(source):
    """Prevents: the ranking drifting back below the holdout pass, where a test
    number would exist to rank on. Structural, because the behavioural test above
    cannot see WHEN the call happens — the fix is the ordering, not the metric."""
    tree = ast.parse(source)
    main = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "main")
    calls = [n for n in ast.walk(main)
             if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_select_winner"]
    assert len(calls) == 1, "the winner is chosen in exactly one place"
    loops = [n for n in ast.walk(main) if isinstance(n, ast.For)]
    inside = [ln for ln in loops if calls[0].lineno <= (ln.end_lineno or 0)
              and calls[0].lineno >= ln.lineno]
    assert inside, "_select_winner must be called INSIDE the split loop (val iteration)"
    # …and guarded by the val branch, so no holdout metric exists when it runs.
    guards = [n for n in ast.walk(main) if isinstance(n, ast.If)
              and n.lineno <= calls[0].lineno <= (n.end_lineno or 0)
              and "val" in ast.unparse(n.test)]
    assert guards, "the selection call must sit under the `split == 'val'` guard"


def test_the_json_records_where_the_winner_was_ranked(source):
    """Prevents: a future reader having to read the code that wrote the file to
    learn which split decided. The M3 record predates the key, deliberately."""
    assert '"winner_selected_on": SELECTION_SPLIT' in source

    # The M3 record itself lives under the gitignored `automation/runs/`, so CI
    # never sees it — skip rather than assert-on-absence, which would be green in
    # CI for a reason that has nothing to do with the property.
    record = REPO / "automation/runs/m3s5/bakeoff.json"
    if not record.exists():
        pytest.skip(f"{record} is a local run artifact (automation/runs/ is gitignored)")
    assert "winner_selected_on" not in json.loads(record.read_text()), (
        "the M3 record must NOT be regenerated — its silence is the honest marker "
        "of the run that ranked on the holdout (see docs/bakeoff_m3.md §3's note)"
    )


# ------------------------------------------------------------- wiring ----


def test_the_make_target_exists_and_promotes_nothing_by_default():
    """Prevents: a bake-off that promotes because somebody ran the default target.
    `--promote-winner` is an explicit, separate invocation."""
    makefile = (REPO / "Makefile").read_text()
    line = next(ln for ln in makefile.splitlines() if ln.startswith("bakeoff:"))
    assert "promotes nothing" in line
    recipe = makefile.split("bakeoff:")[1].splitlines()[1]
    assert "scripts/bakeoff_m3.py $(BAKEOFF_ARGS)" in recipe
    assert "--promote-winner" not in recipe
