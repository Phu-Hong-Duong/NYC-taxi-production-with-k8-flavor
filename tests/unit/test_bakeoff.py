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
        if spec.track not in {"floor", "incumbent"}
    }
    # Three declared cells, not four: since F-022 the origin cell (v1 features,
    # hand hyperparameters) is not DECLARED here at all — through M3 the incumbent
    # row happened to hold it, which is precisely the coupling F-022 broke. The
    # square is printed only when a contender occupies it; see
    # `test_the_square_is_not_printed_against_a_cell_it_is_not_about`.
    assert cells == {("v2", "artisan"), ("v1", "automation"), ("v2", "automation")}
    floors = [spec for spec in bakeoff.CONTENDERS if spec.track == "floor"]
    assert len(floors) == 1, "the gate's floor is the fifth row and there is exactly one"
    incumbents = [spec for spec in bakeoff.CONTENDERS if spec.track == "incumbent"]
    assert len(incumbents) == 1, "exactly one row means 'what is serving'"
    assert len(bakeoff.CONTENDERS) == 5


def test_the_two_search_axes_stay_disjoint(bakeoff):
    """Prevents: DR-03 quietly breaking — the artisan arms must hold v1's
    hyperparameters and the automation arms must not invent feature sets. If both
    tracks moved both axes, no delta in the square isolates anything."""
    by_track = {spec.label: spec for spec in bakeoff.CONTENDERS}
    assert "hand" in by_track["artisan v2"].hyperparameters
    assert "tuned" in by_track["auto-on-v1"].hyperparameters
    assert "tuned" in by_track["auto-on-v2"].hyperparameters
    assert by_track["artisan v2"].feature_set == by_track["auto-on-v2"].feature_set
    # The incumbent row is NOT part of either axis and declares no feature set:
    # since F-022 it means "whatever is serving" and reads its set off the loaded
    # model. `assert champion.feature_set == auto-on-v1.feature_set` was true when
    # the alias held lightgbm-v1 and is an M3-era FACT, not the DR-03 property this
    # test is about (gotcha #50).
    incumbent = next(s for s in bakeoff.CONTENDERS if s.source[0] == "registry-alias")
    assert incumbent.feature_set is None
    assert [s.feature_set for s in bakeoff.CONTENDERS if s.source[0] != "registry-alias"] \
        .count(None) == 0


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
    incumbent = next(s for s in bakeoff.CONTENDERS if s.source[0] == "registry-alias")
    assert not incumbent.caveats and not by_label["artisan v2"].caveats


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
                            recorded_val_mae=3.38, best_iteration=791, feature_set="v2")
    assert bakeoff._promote_winner(winner, _Decision(False), {"features": {"version": "v2"}}) == 1


def test_the_alias_cannot_move_to_a_model_the_config_does_not_describe(bakeoff):
    """Prevents: minting a champion version the next `make predictions` refuses to
    score. `score.py` compares the champion's feature names against
    `configs/train.yaml: features`, and `verify-m2` checks the same line — so the
    config moves as PART of a promotion (M3-S3's law) or the promotion does not
    happen."""
    spec = next(s for s in bakeoff.CONTENDERS if s.label == "auto-on-v2")
    winner = bakeoff.Loaded(spec=spec, name="auto-lgbm-v2", run_id="r", family="lgbm",
                            recorded_val_mae=3.38, best_iteration=791, feature_set="v2")
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
                              recorded_val_mae=val_mae, best_iteration=1,
                              feature_set=spec.feature_set or "v2")
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
        ("champion (alias)", 3.4760, 3.2608),
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
        ("champion (alias)", 3.4760, 3.2608),
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


@pytest.mark.needs_records
def test_the_json_records_where_the_winner_was_ranked(source):
    """Prevents: a future reader having to read the code that wrote the file to
    learn which split decided. The M3 record predates the key, deliberately."""
    assert '"winner_selected_on": SELECTION_SPLIT' in source

    # The M3 record is a TRACKED file from M5-S1 on (F-029 option A), so this no
    # longer skips in CI: the assertion below now runs everywhere. It used to skip
    # because `automation/runs/` was ignored wholesale and asserting on absence
    # would have been green in CI for a reason unrelated to the property.
    record = REPO / "automation/runs/m3s5/bakeoff.json"
    assert record.exists(), (
        f"{record} is committed (F-029) — its absence is a deleted record, not a "
        "clone without local artifacts"
    )
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


# ------------------------------------------------- F-022: the incumbent row ----


def test_the_incumbent_row_declares_no_feature_set(bakeoff):
    """Prevents: F-022 regressing — an alias-resolved contender pinned to a
    feature set by declaration.

    The bake-off died at `_load_booster` for every invocation between M3-S5's own
    `--promote-winner` and M7-S4, because the Spec said `feature_set="v1"` while
    the alias it resolves had moved to a v2 model. Pre-registration is right for
    an arm declared before its number existed and wrong for a pointer designed to
    move; option (a) (ARCH, M4 boundary) separates the two."""
    incumbent = [s for s in bakeoff.CONTENDERS if s.source[0] == "registry-alias"]
    assert len(incumbent) == 1, "exactly one row means 'what is serving'"
    assert incumbent[0].feature_set is None
    assert "v1" not in incumbent[0].label, (
        "the incumbent row's LABEL must not claim a version either — that is the "
        "same defect one layer up, and it is what made the M3 record's label false "
        "the moment the alias moved"
    )


def test_the_feature_set_is_derived_from_the_artifact_and_must_be_unambiguous(bakeoff):
    """Prevents: the derivation guessing. It matches the booster's ORDERED feature
    names against every set declared in configs/features.yaml and requires exactly
    one hit — a model matching none cannot be scored on a matrix this program can
    build, and one matching two has no answerable provenance."""
    from taxi_mlops.features import quote_time, sets

    by_columns: dict[tuple[str, ...], list[str]] = {}
    for name in sets.set_names():
        cols = tuple(quote_time.feature_names(sets.resolve_set(name)))
        by_columns.setdefault(cols, []).append(name)
    for cols, names in by_columns.items():
        if len(names) == 1:
            assert bakeoff._feature_set_of(list(cols), "probe") == names[0]
        else:
            # MEASURED, not assumed: `v1_g5` and `redteam_g5_leaky` declare the
            # SAME ordered columns — the red-team set differs only in how its
            # aggregates were FITTED (M3-S3's leaky arm), which no artifact can
            # report. So a model fitted on either is genuinely unidentifiable from
            # its own feature names, and the derivation refuses rather than picks.
            # It is the safe direction: no such model is promotable (g5 was
            # DROPPED and the leaky set exists only for `leakage_redteam.py`), and
            # a wrong answer here would score a champion on a matrix built from a
            # different definition of the same columns.
            assert sorted(names) == ["redteam_g5_leaky", "v1_g5"]
            with pytest.raises(SystemExit) as ambiguous:
                bakeoff._feature_set_of(list(cols), "probe")
            assert "2 declared feature set" in str(ambiguous.value)

    with pytest.raises(SystemExit) as unknown:
        bakeoff._feature_set_of(["not", "a", "declared", "set"], "probe")
    assert "0 declared feature set" in str(unknown.value)

    v2 = quote_time.feature_names(sets.resolve_set("v2"))
    with pytest.raises(SystemExit) as reordered:
        bakeoff._feature_set_of(list(reversed(v2)), "probe")
    assert "0 declared feature set" in str(reordered.value), (
        "matching must be on the ORDERED list: _load_booster's very next refusal "
        "is about column order, so an order-insensitive match here would hand it a "
        "set it then rejects for a reason this function already knew"
    )


def test_nothing_downstream_of_resolution_reads_the_declared_feature_set(source):
    """Prevents: a matrix built from the declaration the artifact could contradict.

    Everything after `_resolve` must read `Loaded.feature_set` — the concrete one.
    `spec.feature_set` may appear only where the declaration itself is the
    subject: the two resolution sites and the declaration table."""
    assert "item.spec.feature_set" not in source
    assert "winner.spec.feature_set" not in source
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Attribute) and node.attr == "feature_set"):
            continue
        inner = node.value
        if not (isinstance(inner, ast.Attribute) and inner.attr == "spec"):
            continue
        owner = _enclosing_function(tree, node.lineno)
        assert owner in {"_resolve", "_load_booster", "_print_declaration"}, (
            f"line {node.lineno} (in {owner}) reads the DECLARED feature set outside "
            "resolution; everything downstream must read Loaded.feature_set"
        )


def _enclosing_function(tree, lineno: int) -> str:
    best, best_start = "<module>", -1
    for fn in ast.walk(tree):
        if (isinstance(fn, ast.FunctionDef)
                and fn.lineno <= lineno <= (fn.end_lineno or fn.lineno)
                and fn.lineno > best_start):
            best, best_start = fn.name, fn.lineno
    return best


def test_the_square_is_not_printed_against_a_cell_it_is_not_about(source):
    """Prevents: the 2x2 quietly re-basing onto whatever holds the alias.

    With the alias on a tuned v2 model the square would report `auto-on-v2
    +0.00%` — arithmetic that is correct and answers a different question."""
    assert "SQUARE_BASE" in source
    tree = ast.parse(source)
    keys = {
        node.slice.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, str)
    }
    assert "champion v1" not in keys, (
        "the square must find its origin cell by DESCRIPTION (v1 features, hand "
        "hyperparameters), never by INDEXING a label that used to hold it. This "
        "assertion is on the parsed code and not on the text, because the script "
        "explains the change in prose that quotes the old label (#53/#68)"
    )
    assert "the 2x2 is NOT printed" in source
