"""M4-S1: the task graph's cluster-free invariants.

The expensive half — six stages over a real month — needs the data tree, MLflow
and ~7M rows, and it is the story's rehearsal transcript. What runs here is
everything that decides whether that transcript means anything:

* the graph is the one BLUEPRINT §9/M4 names, in that order;
* the stages carry NO logic — every body calls into `taxi_mlops`, and this file
  fails if a stage grows a rule of its own;
* `src/` still never imports an orchestrator, and now the reverse direction is
  checked too: `pipelines/` may not import Flyte at M4-S1 either, because a
  graph that already needs the orchestrator to be TESTED is not decorator-deep;
* a REFUSE is a return value, and the CLI's exit-code mapping is stated once;
* nothing in this file can move the champion alias.

Each test's docstring names the failure it prevents.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TASKS = REPO / "pipelines" / "tasks.py"

pytestmark = pytest.mark.unit


def _load():
    spec = importlib.util.spec_from_file_location("pipeline_tasks", TASKS)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod          # dataclasses resolves annotations via sys.modules
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def tasks():
    return _load()


@pytest.fixture(scope="module")
def source():
    return TASKS.read_text(encoding="utf-8")


def _imports(node: ast.AST, prefixes: tuple[str, ...] = ("taxi_mlops",)) -> list[str]:
    """Modules actually IMPORTED under `node`, read from the AST.

    Not a substring search: `taxi_mlops` and `pipelines` appear in this repo's
    prose on nearly every page, and a text check would be answering a question
    about documentation while claiming to answer one about dependencies. That is
    gotcha #35 one file over, and it went red here before it went green.
    """
    found: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Import):
            found += [a.name for a in child.names]
        elif isinstance(child, ast.ImportFrom):
            found.append(child.module or "")
    return [name for name in found if name.startswith(prefixes)]


# ------------------------------------------------------------------ the graph ---


def test_the_graph_is_the_one_the_blueprint_names(tasks):
    """Prevents: a stage quietly appearing or vanishing between the gate's text
    and the code. §9/M4: 'ingest->validate->features->train->evaluate->register',
    plus the tail §9/M1-S6 promised — 'from M4 the build+publish runs as the tail
    task of the monthly Flyte pipeline' — which landed at M4-S5 as D-003's closure.
    The tail is LAST and asserted to be last: marts published before the run that
    produced them has a verdict would be a warehouse describing a model nobody
    judged."""
    assert tasks.STAGES == (
        "ingest_month", "validate", "build_features", "train", "evaluate", "register",
        "publish_marts",
    )
    for name in tasks.STAGES:
        assert callable(getattr(tasks, name)), f"{name} is declared but not defined"


def test_every_stage_returns_a_typed_serializable_result(tasks):
    """Prevents: a stage returning a DataFrame, a booster or a dict, which works
    in one process and dies the moment M4-S4 puts the stages in separate pods."""
    import dataclasses

    returns = {
        "ingest_month": tasks.IngestResult,
        "validate": tasks.ValidationResult,
        "build_features": tasks.FeatureResult,
        "train": tasks.TrainResult,
        "evaluate": tasks.EvaluationResult,
        "register": tasks.RegisterResult,
        "publish_marts": tasks.MartsResult,
    }
    assert set(returns) == set(tasks.STAGES), (
        "a stage was added to the graph and not to this map, so its return type is "
        "unchecked — which is the one property this test exists for"
    )
    for name, kind in returns.items():
        assert dataclasses.is_dataclass(kind), f"{name} must return a dataclass"
        hints = getattr(getattr(tasks, name), "__annotations__", {})
        assert hints.get("return") is kind or hints.get("return") == kind.__name__, (
            f"{name} must declare -> {kind.__name__}; Flyte types the graph from these"
        )


def test_the_stages_hold_no_logic_of_their_own(source):
    """Prevents the drift this file exists to stop: a rule moving out of
    `taxi_mlops` and into the orchestration layer, where the contract tests, the
    exclusion registry and the gate's unit tests cannot see it. Structural proxy
    — every stage body must reach into `taxi_mlops` — but the real defence is
    that a second home for a rule is visible in this file's diff."""
    tree = ast.parse(source)
    stages = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    for stage in ("ingest_month", "validate", "build_features", "train"):
        assert _imports(stages[stage]), f"{stage} does not call into taxi_mlops"
    # `evaluate` and `register` read the manifest the earlier stages wrote — they
    # must NOT import a computing module, because then they could compute.
    for stage in ("evaluate", "register"):
        assert not _imports(stages[stage]), (
            f"{stage} imports {_imports(stages[stage])} — it reports a decision that "
            "was already made; a reporting stage that can compute will one day compute"
        )


def test_the_marts_tail_reaches_the_marts_code_and_never_the_registry(source):
    """M4-S5's stage, held to both boundaries at once.

    ADR-009 says the marts serve humans and model code never imports them, so the
    publish lives in `scripts/` and this stage calls it — the dependency runs
    pipelines -> scripts, never through `src/`. And M4's standing law says no
    pipeline stage moves `@champion`, so the tail must not reach the registry at
    all: it publishes DATA, and it would have no reason to resolve an alias except
    to become a second promotion path.
    """
    tree = ast.parse(source)
    stages = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    stage = stages["publish_marts"]
    names = {
        n.attr for n in ast.walk(stage) if isinstance(n, ast.Attribute)
    } | {n.id for n in ast.walk(stage) if isinstance(n, ast.Name)}
    assert "marts_publish" in names, "the tail no longer calls the shared publish module"
    imported = _imports(stage)
    assert any(m.startswith("taxi_mlops.data") for m in imported), (
        "the tail must rebuild the analyst layer through taxi_mlops.data, which owns it"
    )
    forbidden = [m for m in imported if m.startswith(("taxi_mlops.training", "mlflow"))]
    assert not forbidden, f"the marts tail reaches the registry/model code: {forbidden}"


def test_the_marts_tail_is_the_last_stage_and_the_local_rehearsal_opts_in(source, tasks):
    """Two properties that are easy to break in opposite directions.

    LAST: marts published before the run has a verdict would be a warehouse
    describing a model nobody judged. OPT-IN locally: every other stage of
    `make pipeline-local` writes only into `data/` and MLflow, so a rehearsal that
    republished the warehouse two Metabase boards read by default would be a command
    whose name lies about its blast radius.
    """
    assert tasks.STAGES[-1] == "publish_marts"
    assert "--publish" in source
    tree = ast.parse(source)
    rehearse = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "rehearse"
    )
    publish_kw = [a for a in rehearse.args.kwonlyargs if a.arg == "publish"]
    assert publish_kw, "rehearse no longer takes a publish switch"
    default = rehearse.args.kw_defaults[rehearse.args.kwonlyargs.index(publish_kw[0])]
    assert isinstance(default, ast.Constant) and default.value is False, (
        "the local rehearsal now publishes the warehouse by default"
    )


def test_pipelines_does_not_import_an_orchestrator_yet(source):
    """Prevents: a graph that cannot be tested without Flyte. ADR-002's fallback
    is only decorator-deep if the callables stand up on their own; S4 adds the
    decorators in `pipelines/flyte/`, not here."""
    for forbidden in ("flytekit", "pyflyte", "@task", "@workflow"):
        assert forbidden not in source, f"{forbidden} appears in pipelines/tasks.py"


def test_src_still_never_imports_the_pipeline_layer():
    """Prevents the dependency inverting. `pipelines/` imports `src/`, never the
    reverse (BLUEPRINT conventions, ADR-001) — otherwise the model code cannot be
    used, or tested, without an orchestrator.

    Read off the AST's import nodes and not off the text: the word 'pipelines'
    appears in this codebase's prose constantly, and a substring check would fail
    on a docstring — gotcha #35's shape, and it caught this test on its first run.
    """
    offenders = {}
    for path in sorted((REPO / "src" / "taxi_mlops").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        hits = sorted(
            {name for name in _imports(tree, prefixes=("pipelines", "flytekit"))}
        )
        if hits:
            offenders[str(path.relative_to(REPO))] = hits
    assert not offenders, f"{offenders} — src/ must not import the orchestration layer"


# --------------------------------------------- verdict-as-data, and no promotion ---


def test_a_refusal_is_a_return_value_and_the_task_is_green(tasks, tmp_path):
    """Prevents: modelling a REFUSE as a task failure. A refused challenger is a
    successful run of a working gate; making it an exception puts a retry on the
    program's one 'no' and eventually gets the stage disabled."""
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({
        "challenger": {"name": "c"}, "metric_source": "taxi_mlops.training.evaluate",
        "metrics": [], "champion_alias_version": "2",
        "decision": {
            "verdict": "REFUSE", "passed": False, "challenger": "c", "floor": "f",
            "split": "test", "n": 10, "challenger_mae": 3.4, "floor_mae": 3.35,
            "challenger_within": 80.0, "floor_within": 80.7, "observed_pct": -1.5,
            "required_pct": 2.0, "incumbent_version": "2", "checks": [],
        },
    }))
    result = tasks.register(str(manifest))
    assert result.decision == "REFUSE" and result.promoted is False
    assert result.margins["observed_pct_vs_floor"] == -1.5
    assert result.exit_code == 1                      # what a SHELL would see
    assert result.champion_alias_version == "2"


def test_a_sampled_run_returns_no_verdict_and_never_a_pass(tasks, tmp_path):
    """Prevents F-008's confusion reaching the pipeline: 'not judged' must not
    arrive downstream looking like 'judged and satisfied'."""
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({
        "challenger": {"name": "c"}, "metric_source": "taxi_mlops.training.evaluate",
        "metrics": [], "decision": None, "champion_alias_version": "2",
    }))
    result = tasks.register(str(manifest))
    assert result.decision == "NO_VERDICT" and result.promoted is False
    assert result.exit_code == 3
    assert "F-008" in result.reason


def test_the_exit_code_mapping_matches_the_cli_contract(tasks):
    """Prevents two copies of the exit-code rules drifting. The CLI's docstring
    is the contract; this property is the pipeline's read of the same table."""
    cli = (REPO / "src/taxi_mlops/training/__main__.py").read_text(encoding="utf-8")
    assert "1  the gate REFUSED" in cli and "3  NO VERDICT" in cli
    mapping = {v: tasks.RegisterResult(decision=v, promoted=False, reason="").exit_code
               for v in ("PROMOTE", "REFUSE", "NO_VERDICT")}
    assert mapping == {"PROMOTE": 0, "REFUSE": 1, "NO_VERDICT": 3}


def test_no_stage_can_move_the_champion_alias(tasks, source, tmp_path):
    """Prevents M4's standing law being a comment. `train` passes promote=False
    unconditionally (not as a parameter with a default), and `register`'s
    promoting branch is not built — it refuses loudly and names the one path
    that may promote."""
    assert "promote=False" in source
    assert "promote=True" not in source.replace("if promote:", "")
    for api in ("set_registered_model_alias", "delete_registered_model_alias",
                "create_model_version", "register_model"):
        assert api not in source, f"{api} appears in the pipeline layer"

    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({"challenger": {"name": "c"}, "metrics": [],
                                    "metric_source": "e", "decision": None}))
    with pytest.raises(NotImplementedError, match="F-016"):
        tasks.register(str(manifest), promote=True)


def test_train_never_offers_a_promote_parameter(tasks):
    """Prevents the law becoming a default. A keyword argument that could be
    flipped is not a law — the M4 pipeline has no promoting call site at all."""
    import inspect

    assert "promote" not in inspect.signature(tasks.train).parameters


# ---------------------------------------------------------------- the reporting ---


def test_evaluate_reports_the_one_evaluators_numbers_and_computes_none(tasks, tmp_path):
    """Prevents gotcha #15 leaking into the orchestration layer: only
    `taxi_mlops.training.evaluate` may produce a reported number, so this stage
    lifts and types, and filters to the challenger's own rows."""
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({
        "challenger": {"name": "lightgbm-v1"},
        "metric_source": "taxi_mlops.training.evaluate",
        "metrics": [
            {"contender": "lightgbm-v1", "split": "test", "n": 5, "mae": 3.26,
             "within_tolerance_rate": 81.48},
            {"contender": "baseline-constant-median", "split": "test", "n": 5,
             "mae": 7.66, "within_tolerance_rate": 50.0},
        ],
        "decision": None,
    }))
    result = tasks.evaluate(str(manifest))
    assert result.metric_source == "taxi_mlops.training.evaluate"
    assert [m.contender for m in result.metrics] == ["lightgbm-v1"]
    assert result.metrics[0].kpi_09_mae_minutes == 3.26


# ------------------------------------------------------------------- wiring ---


def test_the_make_target_exists_and_asks_for_no_verdict():
    """Prevents: a rehearsal that claims a result. The local driver is a plumbing
    smoke test on one month — F-008's exit-3 class — and `--gate` is not in it."""
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    line = next(ln for ln in makefile.splitlines() if ln.startswith("pipeline-local:"))
    assert "NO verdict" in line
    recipe = makefile.split("pipeline-local:")[1].splitlines()[1]
    assert "pipelines/tasks.py --month $(MONTH)" in recipe
    assert "--gate" not in recipe
