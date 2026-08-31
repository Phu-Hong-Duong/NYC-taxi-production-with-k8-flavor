"""The `lookups` seam's laws — M8-S4 leg 3.

Three properties, and the first is the one this story exists to protect.

1. **F-059: the seam reaches the centroids and the calendar, and NOTHING else.**
   The borough dictionary is an ENCODING whose codes depend on the whole lookup
   table's iteration order, and `is_airport` is a CONSTANT total function that
   answers for the two non-places the store has no row for. Both must keep
   reading the committed artifacts. This is asked of the **AST**, never of the
   behaviour: a store whose values happen to agree with the committed table
   would make a behavioural test pass for a design that is wrong, and the
   failure it hides — a silent total category re-map — is invisible in every
   individual value.
2. **An absent `Lookups` changes nothing.** Every caller since M3-S3 passes
   none, so the default must be bit-identical to what those callers got before
   the parameter existed.
3. **The wall stays a wall on this side of it.** `serving.feature_store` and
   `serving.transformer` run in the pandas-3 image and may not import feast.
"""

from __future__ import annotations

import ast
import sys

import pandas as pd
import pytest
from conftest import REPO

sys.path.insert(0, str(REPO / "src"))

from taxi_mlops.features import calendar as calendar_mod  # noqa: E402
from taxi_mlops.features import quote_time  # noqa: E402
from taxi_mlops.features import zones as zones_mod  # noqa: E402
from taxi_mlops.features.lookups import COMMITTED, Lookups  # noqa: E402

pytestmark = pytest.mark.unit

QUOTE_TIME = REPO / "src" / "taxi_mlops" / "features" / "quote_time.py"

#: The derived features whose branch must NOT consult `lookups`. Named here
#: rather than derived, because the list IS the decision — adding a name to it
#: is how a future reviewer widens or narrows F-059 deliberately.
COMMITTED_ONLY = ("pu_is_airport", "do_is_airport", "is_airport_trip", "borough_pair")


def _derived_dispatch() -> ast.FunctionDef:
    tree = ast.parse(QUOTE_TIME.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_derived_columns":
            return node
    raise AssertionError("quote_time._derived_columns has been renamed")


def _branch_source(feature: str) -> str:
    """The source of the dispatch branch that builds `feature`."""
    source = QUOTE_TIME.read_text()
    dispatch = _derived_dispatch()
    for node in ast.walk(dispatch):
        if not isinstance(node, ast.If):
            continue
        test = ast.get_source_segment(source, node.test) or ""
        if f'"{feature}"' in test or f"'{feature}'" in test:
            return "\n".join(
                ast.get_source_segment(source, stmt) or "" for stmt in node.body
            )
    raise AssertionError(f"no dispatch branch builds {feature!r}")


def test_the_seam_exists_and_is_a_parameter() -> None:
    """`lookups` is an argument of the ONE transform path, not a module global.

    A global would make "which reference data was this row built against?" a
    property of the process rather than of the call — the identical argument
    `fitted` carries for the point-in-time tables (dossier §4 trap 2).
    """
    signature = quote_time.build_features.__code__.co_varnames
    assert "lookups" in signature
    assert isinstance(COMMITTED, Lookups)
    assert COMMITTED.geometry_table is None and COMMITTED.calendar is None


@pytest.mark.parametrize("feature", COMMITTED_ONLY)
def test_f059_the_committed_only_branches_never_read_the_seam(feature: str) -> None:
    """The borough code and the airport constant may not come from a store.

    AST and not behaviour: see the module docstring. The check is that the
    branch's own source calls `zones_mod` and never mentions `lookups`.
    """
    branch = _branch_source(feature)
    assert "lookups" not in branch, (
        f"the {feature!r} branch reads the `lookups` seam. F-059: "
        "a borough CODE is an encoding over the whole table and `is_airport` is a "
        "total constant, so neither is a per-entity value a store can supply. "
        "See taxi_mlops.features.lookups."
    )
    assert "zones_mod." in branch


def test_the_geometry_and_calendar_branches_DO_read_the_seam() -> None:
    """The positive half — without it the test above passes on a seam nobody wired.

    A test suite that only forbids is satisfied by doing nothing at all.
    """
    source = QUOTE_TIME.read_text()
    dispatch = ast.get_source_segment(source, _derived_dispatch()) or ""
    assert "table=lookups.geometry_table" in dispatch
    assert "calendar=lookups.calendar" in dispatch


def test_an_absent_lookups_is_identical_to_an_explicit_committed_one() -> None:
    """The default must be exactly what every pre-M8 caller already got."""
    cfg = {
        "temporal": ["hour", "dayofweek"],
        "passthrough": ["PULocationID", "DOLocationID"],
        "categorical": [],
        "derived": [
            "centroid_haversine_km",
            "midpoint_lat",
            "has_geometry",
            "is_holiday",
            "is_near_holiday",
            "is_business_day",
            "pu_borough",
            "borough_pair",
            "pu_is_airport",
        ],
    }
    frame = pd.DataFrame(
        {
            quote_time.PICKUP_TIMESTAMP: pd.to_datetime(
                ["2019-07-04T09:15:00", "2019-03-11T23:59:00", "2019-05-20T12:00:00"]
            ),
            "PULocationID": [132, 264, 100],
            "DOLocationID": [48, 264, 265],
        }
    )
    default = quote_time.build_features(frame, cfg)
    explicit = quote_time.build_features(
        frame,
        cfg,
        lookups=Lookups(
            geometry_table=zones_mod.load_zone_table(), calendar=calendar_mod.load_calendar()
        ),
    )
    assert default.equals(explicit)


def test_sources_names_all_four_reference_groups() -> None:
    """A record that reported only what it fetched could not show what it refused."""
    sources = Lookups(
        geometry_table=zones_mod.load_zone_table(), calendar=calendar_mod.load_calendar()
    ).sources
    assert sources["centroids"] == "feature-store"
    assert sources["calendar"] == "feature-store"
    # Not knobs. If either of these ever reports anything else, F-059 was undone.
    assert sources["borough_dictionary"] == "committed-table"
    assert sources["airport_constant"] == "committed-code"
    assert COMMITTED.sources["centroids"] == "committed-table"


@pytest.mark.parametrize("module", ["feature_store", "transformer"])
def test_the_pandas_three_side_never_imports_feast(module: str) -> None:
    """Shape (i)'s whole premise, pinned where it can regress.

    Asked of the AST because both files argue the wall at length in prose, and a
    grep for the word would match the argument (gotchas #53/#68/#99).
    """
    path = REPO / "src" / "taxi_mlops" / "serving" / f"{module}.py"
    tree = ast.parse(path.read_text())
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    offenders = [name for name in imported if name.split(".")[0] == "feast"]
    assert not offenders, (
        f"serving/{module}.py imports {offenders}. feast 0.66.0 pins pandas<3 against "
        "this project's 3.0.5 — the door is a JSON document, not an import (M8 law 4)."
    )
