"""M5-S3: the parity test's cluster-free half.

`make parity` needs a live endpoint and a registry; almost everything that could
be WRONG about it does not. What is pinned here is the set of properties that,
if they quietly stopped holding, would leave a green parity run meaning nothing:

* **it is a READER.** A parity test that could deploy, promote or move an alias
  would be able to make itself pass. Pinned by parsing the AST, not by grepping
  for words — this module argues about promotion and aliases at length in prose
  (gotchas #53/#68).
* **the bar is 1e-6 and there is no way to skip the test.** A tolerance that can
  be loosened by a flag somebody reaches for is not a bar; loosening it is a PO
  fork.
* **the hazard set really spans the hazards it claims**, including the two the
  story was written for: a row with no geometry at all, and an OD pair unseen in
  training. A parity run over sixteen ordinary midtown trips would pass forever
  and prove nothing.
* **NaN leaves this process as `null` and an infinity does not leave at all**
  (F-030). The encoding is the fix; these are the tests that keep it.
* **the verdict cannot claim more than it measured** — no "worst row" when
  nothing disagrees, and no PASS when the endpoint answered as a different
  version from the one loaded offline.
"""

from __future__ import annotations

import ast
import json

import numpy as np
import pandas as pd
import pytest
from conftest import REPO, called_paths

from taxi_mlops.serving import client, parity

PARITY_SOURCE = REPO / "src" / "taxi_mlops" / "serving" / "parity.py"
REDTEAM = REPO / "scripts" / "parity_redteam.sh"
MAKEFILE = REPO / "Makefile"

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------
# It is a reader
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "verb",
    [
        "set_registered_model_alias",
        "delete_registered_model_alias",
        "create_model_version",
        "register_model",
        "log_model",
        "transition_model_version_stage",
        "delete_model_version",
    ],
)
def test_parity_never_mutates_the_registry(verb: str) -> None:
    """A test that can move the pointer it checks can make itself pass."""
    assert verb not in called_paths(PARITY_SOURCE), (
        f"{PARITY_SOURCE.name} invokes {verb} — parity is a READER. It resolves an "
        "alias, loads a model and POSTs; anything that mutates the registry belongs "
        "in registry.py, which is the one module allowed to."
    )


def test_parity_deploys_nothing() -> None:
    source = PARITY_SOURCE.read_text()
    tree = ast.parse(source)
    shelling = [
        name
        for name in called_paths(PARITY_SOURCE)
        if name.split(".")[0] in {"subprocess", "os"} and "environ" not in name
    ]
    assert not shelling, (
        f"{PARITY_SOURCE.name} shells out ({shelling}). Parity measures a deployment; "
        "it does not create, restart or repair one."
    )
    imported = {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "kubernetes" not in imported


def test_the_record_is_written_where_review_can_see_it() -> None:
    """F-029's regime: a record a gate replays must be one a diff shows."""
    assert str(parity.DEFAULT_RECORD).startswith("automation/runs/")
    assert str(parity.DEFAULT_RECORD).endswith(".json"), (
        "logs under automation/runs/ are gitignored and only *.json is tracked, so a "
        "record written under any other extension is invisible to review (F-029)."
    )


# --------------------------------------------------------------------------
# The bar
# --------------------------------------------------------------------------


def test_the_bar_is_one_micro_minute() -> None:
    assert parity.TOLERANCE_MINUTES == 1e-6


def test_there_is_no_skip_flag() -> None:
    """M1's rule, inherited by every gate since: a fast mode is a mode it runs in."""
    source = PARITY_SOURCE.read_text()
    for flag in ("--skip", "--fast", "SKIP_PARITY"):
        assert flag not in source, f"{flag} would make a green run mean 'not run'"


def test_the_makefile_wires_both_targets() -> None:
    makefile = MAKEFILE.read_text()
    assert "taxi_mlops.serving.parity" in makefile
    assert "scripts/parity_redteam.sh" in makefile


# --------------------------------------------------------------------------
# The hazard set spans the hazards
# --------------------------------------------------------------------------


def test_every_hazard_names_itself_and_is_unique() -> None:
    names = [hazard.name for hazard in parity.HAZARDS]
    assert len(names) == len(set(names))
    for hazard in parity.HAZARDS:
        assert len(hazard.why) > 30, f"{hazard.name} does not say why it is in the set"


def test_the_set_covers_the_no_geometry_path() -> None:
    """DR-04 condition 1 and F-030: the rows the wire could not carry at all."""
    unknown = {264, 265}
    covered = [
        hazard
        for hazard in parity.HAZARDS
        if unknown & {hazard.request.pu_location_id, hazard.request.do_location_id}
    ]
    assert len(covered) >= 2, (
        "parity must send at least a both-sides-unknown row and a one-sided one. These "
        "are the rows that returned HTTP 422 before F-030 was fixed, and ~1% of every "
        "split lands on them."
    )
    both = [
        hazard
        for hazard in covered
        if {hazard.request.pu_location_id, hazard.request.do_location_id} <= unknown
    ]
    assert both, "264->264 is the largest single OD 'route' in this data — send it"


def test_the_set_covers_airports_and_the_tail() -> None:
    airports = {1, 132, 138}  # EWR, JFK, LGA — the zones M2-S4 measured 1.9x error on
    hit = {
        zone
        for hazard in parity.HAZARDS
        for zone in (hazard.request.pu_location_id, hazard.request.do_location_id)
        if zone in airports
    }
    assert hit == airports, f"missing airport zones: {sorted(airports - hit)}"


def test_the_set_covers_an_out_of_training_year() -> None:
    """F-019's extension: a date no training month contains must still parity."""
    years = {hazard.request.pickup_datetime[:4] for hazard in parity.HAZARDS}
    assert years - {"2019"}, "every hazard row is inside the training year"


def test_the_hazard_rows_build_and_carry_missing_geometry(
) -> None:
    """The set is not merely declared — it must survive the ONE feature path."""
    from taxi_mlops.features import quote_time
    from taxi_mlops.training.run import load_train_config

    cfg = load_train_config()["features"]
    matrix = parity.build_matrix([h.request for h in parity.HAZARDS], cfg)
    assert len(matrix) == len(parity.HAZARDS)
    assert list(matrix.columns) >= quote_time.feature_names(cfg)
    assert matrix["centroid_haversine_km"].isna().any(), (
        "no hazard row exercises the missing-geometry path — the reason this test exists"
    )
    assert (matrix["has_geometry"] == 0).any()


# --------------------------------------------------------------------------
# F-030: what a NaN becomes on the wire
# --------------------------------------------------------------------------


def test_missing_travels_as_json_null() -> None:
    matrix = pd.DataFrame(
        {"a": pd.Series([1.5, np.nan], dtype="float32"), "b": pd.Series([1, 2], dtype="int16")}
    )
    payload = client.v2_payload(matrix, ["a", "b"])
    assert payload["inputs"][0]["data"] == [1.5, None]
    body = json.dumps(payload, allow_nan=False)
    assert "null" in body
    assert json.loads(body)["inputs"][0]["data"][1] is None


def test_an_infinity_is_refused_rather_than_encoded() -> None:
    matrix = pd.DataFrame({"a": pd.Series([np.inf], dtype="float32")})
    with pytest.raises(ValueError, match="infinity"):
        client.v2_payload(matrix, ["a"])


def test_the_encoder_cannot_emit_a_nan_token_again() -> None:
    """The guard, not the encoding: `_post` must forbid the non-standard tokens."""
    source = (REPO / "src" / "taxi_mlops" / "serving" / "client.py").read_text()
    tree = ast.parse(source)
    # Scoped to `_post`, which is the one place a body LEAVES this process. The
    # other `json.dumps` in the module renders a response into an error message
    # for a human, where a NaN token is harmless and forbidding it would be a
    # rule about prose rather than about the wire.
    post = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_post"
    )
    dumps = [
        node
        for node in ast.walk(post)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "dumps"
    ]
    assert dumps, "client._post no longer serialises a body — this test is stale"
    for call in dumps:
        assert any(kw.arg == "allow_nan" for kw in call.keywords), (
            "json.dumps emits the non-standard tokens NaN/Infinity by DEFAULT, and that "
            "default is what sent malformed bodies to the endpoint for a whole milestone "
            "(F-030). Pass allow_nan=False and encode missing as null."
        )


# --------------------------------------------------------------------------
# The verdict claims exactly what it measured
# --------------------------------------------------------------------------


def _result(deltas: list[float], *, served: str = "2", champion: str = "2") -> parity.ParityResult:
    rows = [
        parity.RowResult(hazard, 10.0, 10.0 + delta)
        for hazard, delta in zip(parity.HAZARDS, deltas, strict=False)
    ]
    return parity.ParityResult(
        rows=rows,
        tolerance=parity.TOLERANCE_MINUTES,
        champion_version=champion,
        champion_run_id="r",
        served_version=served,
        served_model="nyc-taxi-eta",
        endpoint="http://localhost:8081/v2/models/nyc-taxi-eta/infer",
        feature_names=["hour"],
    )


def test_no_worst_row_is_named_when_nothing_disagrees() -> None:
    result = _result([0.0, 0.0, 0.0])
    assert result.worst is None
    assert "every row agrees EXACTLY" in " ".join(parity.verdict_lines(result))


def test_the_worst_row_is_named_when_something_does() -> None:
    result = _result([0.0, 1e-3, 0.0])
    assert result.worst is not None
    assert result.worst.hazard.name == parity.HAZARDS[1].name
    assert not result.passed


def test_a_version_mismatch_cannot_pass_however_small_the_delta() -> None:
    """Two models agreeing on sixteen rows is not the same claim as parity."""
    result = _result([0.0, 0.0], served="1", champion="2")
    assert result.max_delta == 0.0
    assert not result.passed
    assert not result.versions_agree
    assert any("is serving version" in line for line in parity.verdict_lines(result))


def test_the_measured_max_is_always_printed() -> None:
    """A bar passed silently teaches nothing (the kickoff's words)."""
    lines = " ".join(parity.verdict_lines(_result([0.0])))
    assert "max |offline - online|" in lines


def test_the_record_carries_every_row_and_the_verdict() -> None:
    record = _result([0.0, 0.0]).as_record()
    assert record["max_abs_delta_minutes"] == 0.0
    assert record["passed"] is True
    assert len(record["results"]) == 2
    assert record["results"][0]["why"]


# --------------------------------------------------------------------------
# The red team plants a cause without touching the served model
# --------------------------------------------------------------------------


def test_the_redteam_never_deploys_or_promotes() -> None:
    source = REDTEAM.read_text()
    banned = ("kubectl apply", "kubectl delete", "kubectl rollout restart", "make serve",
              "helm upgrade", "helm install")
    for needle in banned:
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("*"):
                continue  # prose about what it must not do is not doing it (#68)
            assert needle not in stripped, (
                f"parity_redteam.sh runs {needle!r}. A drill that redeploys to prove a "
                "test works has broken the thing under test."
            )


def test_the_redteam_inverts_its_exit_code_and_re_runs_the_real_test() -> None:
    source = REDTEAM.read_text()
    assert "PASSED" in source and "FAILED" in source
    assert "--permute-columns" in source, "arm A is not wired"
    assert "--against-version 1" in source, "arm B is not wired"
    assert "parity.json" in source, "the drill must leave the untampered record behind"


def test_the_permute_lever_moves_values_not_names() -> None:
    """The lever must plant a cause this runtime can actually express.

    The first draft rotated the ORDER of the inputs and the endpoint answered
    identically, because mlserver pairs by NAME. A red team whose tampering is
    a no-op reports PASS for a test that never went red.
    """
    tree = ast.parse(PARITY_SOURCE.read_text())
    measure = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "measure"
    )
    body = ast.dump(measure)
    assert "sent_matrix" in body, (
        "the permute lever must build a MATRIX whose values moved; permuting the name "
        "list alone is a no-op against a name-matching runtime."
    )
