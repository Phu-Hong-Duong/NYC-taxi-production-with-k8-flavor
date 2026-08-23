"""The M8-S4 leg 3 readers are READERS — M5-S3's property, transplanted.

Four scripts arrived with this story and three of them touch a live cluster. The
standing rule since M5-S3 is that a measurement must not be able to change what it
measures: a parity that could re-deploy, or a load run that could move an alias,
produces a number about a system it disturbed.

Everything here is asked of the **AST**. These files argue their own design in
prose that names the very verbs being forbidden — `deploy_transformer.sh` is
mentioned by the parity's docstring, "materialize" appears in the sentence saying
it does not — and gotcha #99 is this repo's record of three needles in a gate's
own test file matching the gate quoting itself.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

pytestmark = pytest.mark.unit

READERS = ("transformer_parity.py", "transformer_load.py", "transformer_probe.py")

#: Verbs that change the system under measurement. `apply` is deliberately not
#: here — it is `str.apply`-shaped and too common to be a useful needle; the
#: subprocess check below is what catches a reader shelling out to kubectl apply.
MUTATING = {
    "set_registered_model_alias",
    "delete_registered_model_alias",
    "create_model_version",
    "transition_model_version_stage",
    "log_model",
    "materialize",
    "materialize_incremental",
}


def _tree(name: str) -> ast.AST:
    return ast.parse((REPO / "scripts" / name).read_text())


@pytest.mark.parametrize("name", READERS)
def test_the_readers_call_no_mutating_verb(name: str) -> None:
    called = {
        node.func.attr
        for node in ast.walk(_tree(name))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    } | {
        node.func.id
        for node in ast.walk(_tree(name))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not (called & MUTATING)


@pytest.mark.parametrize("name", READERS)
def test_the_readers_never_shell_out_to_a_mutation(name: str) -> None:
    """A reader may port-forward. It may not apply, delete, scale or patch.

    The probe stands up two `kubectl port-forward`s and that is the only
    subprocess any of these may make — checked on the argv LIST that is actually
    passed, never on the file's text.
    """
    forbidden = {"apply", "delete", "patch", "scale", "annotate", "create", "replace", "edit"}
    for node in ast.walk(_tree(name)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        target = getattr(func, "attr", None) or getattr(func, "id", None)
        if target not in {"Popen", "run", "check_call", "check_output"}:
            continue
        assert node.args, f"{name}: a subprocess call with no argv to inspect"
        argv = node.args[0]
        assert isinstance(argv, ast.List), f"{name}: argv must be a literal list to be checkable"
        words = {e.value for e in argv.elts if isinstance(e, ast.Constant)}
        assert not (words & forbidden), f"{name} shells out to a mutation: {words & forbidden}"


def test_the_parity_bar_is_exact_and_names_where_it_was_argued() -> None:
    """A bar with no argument beside it is a number nobody can review.

    The value AND the pointer are both asserted: M8's three previous seams each
    re-argued their own bar rather than inheriting one, and a script that quietly
    pointed at another story's section would be inheriting by another route.
    """
    source = (REPO / "scripts" / "transformer_parity.py").read_text()
    module = ast.parse(source)
    tolerance = next(
        node.value
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(getattr(t, "id", None) == "TOLERANCE" for t in node.targets)
    )
    assert isinstance(tolerance, ast.Constant) and tolerance.value == 0.0
    assert "docs/transformer_m8.md" in source


def test_the_load_shape_is_m5_s4s_and_is_not_re_derived() -> None:
    """Two percentiles measured at different shapes are not comparable.

    The whole value of the transformer's p95 is sitting beside the champion's, so
    the rate, the window, the concurrency and the mix are constants here rather
    than a ramp's output — and a ramp would additionally re-choose a rate against
    a container whose ceiling gotcha #74 says must not be measured at.
    """
    module = ast.parse((REPO / "scripts" / "transformer_load.py").read_text())
    shape = next(
        node.value
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(getattr(t, "id", None) == "SHAPE" for t in node.targets)
    )
    assert isinstance(shape, ast.Dict)
    values = {k.value: v.value for k, v in zip(shape.keys, shape.values, strict=True)}
    assert values == {"rate": 4.0, "seconds": 60.0, "concurrency": 8, "mix": "hazards"}


def test_the_load_run_sets_no_threshold() -> None:
    """The bar for serving latency lives in docs/slo_serving.md and nowhere else."""
    source = (REPO / "scripts" / "transformer_load.py").read_text()
    module = ast.parse(source)
    comparisons = [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.Compare)
        and any(
            isinstance(c, ast.Constant) and isinstance(c.value, float) for c in node.comparators
        )
    ]
    # `error_rate == 0.0` is a count of failures, not a latency bar: zero is not
    # a threshold anybody chose. Anything else would be.
    for node in comparisons:
        for comparator in node.comparators:
            if isinstance(comparator, ast.Constant) and isinstance(comparator.value, float):
                assert comparator.value == 0.0, (
                    "a float threshold appeared in the load reader. M5-S4's precedent: "
                    "a READER that does not judge — the bar is the SLO document's."
                )
