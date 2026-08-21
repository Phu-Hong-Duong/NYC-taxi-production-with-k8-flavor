"""The retrieval parity's laws and the point-in-time proof's — M8-S3.

Five properties, made falsifiable here rather than argued in the doc:

1. **The wall holds on the two new modules too.** `infra/feast/retrieve.py`
   imports `feast` and never `taxi_mlops`; `scripts/feast_retrieval.py` and
   `scripts/feast_retrieval_rows.py` import `taxi_mlops` and never `feast`. AST,
   never grep — every one of these files argues its own design at length and a
   word search would pass on the argument (gotchas #53/#68/#99).
2. **The bar is EXACT and lives in ONE place.** `docs/feast_pit_m8.md` §2 argues
   it; `scripts/feast_retrieval.py` applies it; this asserts they are the same
   number, so a widened bar is a red test rather than a diff nobody read (F-017,
   and M8 law 4: a mismatch is a finding, never a bar to widen).
3. **The comparison is two-sided about absence.** Both-missing is agreement,
   one-missing is a MISMATCH — pinned on real arrays, because a check that
   quietly dropped nulls would print `0.000e+00` while being blind to exactly the
   rows zones 264/265 produce.
4. **The reader reads.** No deploy, no fit of anything but the truth it compares
   against, no registry verb, no alias, no materialization.
5. **F-056's classification cannot degrade into a count.** The three classes must
   stay distinct, and `unexplained` must be a failure rather than a note.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

RETRIEVER = REPO / "infra" / "feast" / "retrieve.py"
COMPARER = REPO / "scripts" / "feast_retrieval.py"
ROWS_SCRIPT = REPO / "scripts" / "feast_retrieval_rows.py"
ROWS_CSV = REPO / "infra" / "feast" / "retrieval_rows.csv"
DOC = REPO / "docs" / "feast_pit_m8.md"

PARITY_RECORD = REPO / "automation" / "runs" / "m8-pit" / "retrieval_parity.json"
PROOF_RECORD = REPO / "automation" / "runs" / "m8-pit" / "pit_proof.json"


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _called_names(path: Path) -> set[str]:
    """Every dotted callee name actually INVOKED, from the AST."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        parts: list[str] = []
        while isinstance(target, ast.Attribute):
            parts.append(target.attr)
            target = target.value
        if isinstance(target, ast.Name):
            parts.append(target.id)
        if parts:
            names.add(".".join(reversed(parts)))
    return names


# ----------------------------------------------------------- the wall ---
def test_the_retriever_imports_feast_and_never_the_project() -> None:
    roots = _imported_roots(RETRIEVER)
    assert "feast" in roots, "infra/feast/retrieve.py is the quarantine's side; it needs feast"
    assert "taxi_mlops" not in roots, (
        "retrieve.py runs under .venv-feast (pandas 2.3.3) and must never import taxi_mlops — "
        "one import across the wall is how a quarantine stops being one"
    )


@pytest.mark.parametrize("path", [COMPARER, ROWS_SCRIPT])
def test_this_side_imports_the_project_and_never_feast(path: Path) -> None:
    roots = _imported_roots(path)
    assert "taxi_mlops" in roots
    assert "feast" not in roots, (
        f"{path.name} runs under pandas 3.0.5, where feast cannot be installed at all "
        "(M8 law 4: feast 0.66.0 pins pandas<3)"
    )


def test_the_retriever_lives_outside_the_feature_repo_directory() -> None:
    """`feast apply` imports every module in the repo dir looking for definitions."""
    assert RETRIEVER.parent.name == "feast"
    assert not (REPO / "infra" / "feast" / "feature_repo" / "retrieve.py").exists(), (
        "a script beside definitions.py would be imported by every apply and every plan"
    )


# --------------------------------------------------------- the one bar ---
def test_the_bar_the_script_applies_is_the_bar_the_doc_argues() -> None:
    """F-017: every literal derived on both sides, never typed twice."""
    import feast_retrieval

    assert feast_retrieval.TOLERANCE == 0.0
    body = DOC.read_text(encoding="utf-8")
    assert "The bar is EXACT" in body, "docs/feast_pit_m8.md §2 no longer argues an exact bar"
    assert re.search(r"bar of `0\.0`", body), (
        "the doc must state the same number the script applies; a bar argued in one file "
        "and applied in another is two bars"
    )


def test_the_doc_argues_the_bar_before_it_reports_a_measurement() -> None:
    """The ordering M8 law 4 is about, asserted on the document's own structure."""
    body = DOC.read_text(encoding="utf-8")
    argument = body.index("## 2. The tolerance")
    measurement = body.index("## 5. Retrieval parity — the measurement")
    assert argument < measurement


# ------------------------------------------- absence is compared, not dropped ---
def test_both_missing_is_agreement_and_one_missing_is_a_mismatch() -> None:
    import feast_retrieval

    ours = np.array([1.0, np.nan, np.nan, 4.0])
    theirs = np.array([1.0, np.nan, 3.0, 4.0])
    verdict = feast_retrieval.compare("x", "float", ours, theirs, np.arange(4))
    assert verdict.both_missing == 1
    assert verdict.one_missing == 1
    assert verdict.mismatches == 1, (
        "a one-sided null must FAIL: it is the difference between 'the store has no row' "
        "and 'the feature path has no value', which is the whole no-geometry question"
    )
    assert verdict.max_abs_delta == 0.0


def test_a_float_that_differs_at_all_fails_because_the_bar_is_exact() -> None:
    import feast_retrieval

    ours = np.array([1.0, 2.0])
    theirs = np.array([1.0, 2.0 + 1e-12])
    verdict = feast_retrieval.compare("x", "float", ours, theirs, np.arange(2))
    assert verdict.mismatches == 1, "1e-12 is not exact, and the bar is exact by argument"


def test_strings_and_bools_are_compared_by_value() -> None:
    import feast_retrieval

    words = feast_retrieval.compare(
        "b",
        "string",
        np.array(["Queens", "Bronx"]),
        np.array(["Queens", "Brooklyn"]),
        np.arange(2),
    )
    assert words.mismatches == 1
    flags = feast_retrieval.compare(
        "f", "bool", np.array([True, False]), np.array([True, True]), np.arange(2)
    )
    assert flags.mismatches == 1


# ------------------------------------------------------- it is a READER ---
def test_the_comparer_never_deploys_promotes_or_materializes() -> None:
    called = _called_names(COMPARER)
    for forbidden in (
        "mlflow.set_registered_model_alias",
        "mlflow.register_model",
        "store.materialize",
        "registry.promote",
    ):
        assert forbidden not in called, f"{COMPARER.name} calls {forbidden}"

    # The shell half is asked of the INVOCATION, never of the words. The first
    # draft searched the file body for "materialize" and went red on the
    # docstring sentence promising it does not materialize — gotcha #99 for the
    # second time in this repo, and in a test file again.
    tree = ast.parse(COMPARER.read_text(encoding="utf-8"))
    runs = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"run", "Popen", "call", "check_output", "check_call", "system"}
    ]
    assert len(runs) == 1, (
        f"{COMPARER.name} makes {len(runs)} subprocess call(s); it crosses the wall exactly "
        "once and does nothing else out of process"
    )
    command = COMPARER.read_text(encoding="utf-8").split("command = [")[1].split("]")[0]
    for token in ("kubectl", "helm", "feast", "mlflow"):
        assert token not in command, (
            f"the one subprocess call names {token!r}; it may launch the quarantine "
            "interpreter and this repo's retriever, and nothing else"
        )
    assert "QUARANTINE_PYTHON" in command and "RETRIEVER" in command


def test_the_only_fit_is_the_truth_being_compared_against() -> None:
    """The aggregates are re-fitted from data/processed, never rebuilt from the store."""
    called = _called_names(COMPARER)
    assert "aggregates.fit" in called
    body = COMPARER.read_text(encoding="utf-8")
    assert "point_in_time=True" in body
    assert "point_in_time=False" not in body, (
        "the leakage switch belongs to scripts/leakage_redteam.py and to nothing else; "
        "the naive pass here is made with TIMESTAMPS, which is the honest demonstration"
    )


def test_the_naive_timestamp_is_derived_from_the_configured_train_months() -> None:
    import feast_retrieval

    assert str(feast_retrieval.naive_timestamp(("2019-01", "2019-06"))) == "2019-07-01 00:00:00"
    assert str(feast_retrieval.naive_timestamp(("2020-11", "2020-12"))) == "2021-01-01 00:00:00"


# --------------------------------------------------- F-056's classification ---
def test_the_shortfall_classes_stay_distinct_and_unexplained_is_a_failure() -> None:
    body = COMPARER.read_text(encoding="utf-8")
    for key in (
        "duplicate_key_and_timestamp",
        "earlier_than_every_source_row",
        "unexplained",
        "earliest_source_stamp",
    ):
        assert key in body, f"F-056's classification lost the {key!r} class"
    assert "for shortfall in unexplained:" in body, (
        "an unexplained missing row must reach `problems` and fail the run; a note would "
        "make the check a description of whatever the store happened to return"
    )


def test_the_earliest_source_stamp_is_read_and_never_typed() -> None:
    """A typed stamp drifts from the sources it claims to describe."""
    body = COMPARER.read_text(encoding="utf-8")
    assert 'read_parquet(REPO_ROOT / "data" / "feast" / f"{source}.parquet")' in body
    assert not re.search(r'"2019-0\d-01T00:00:00"', body), (
        "a source stamp literal in the classifier is a second home for a number the "
        "published parquet already holds"
    )


# ------------------------------------------------------- the declared rows ---
def test_the_row_set_is_committed_and_every_row_names_why() -> None:
    import csv

    with ROWS_CSV.open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 88
    assert {row["stratum"] for row in rows} == {
        "hazard",
        "month-boundary",
        "ordinary",
        "airport",
        "no-geometry",
        "long-trip",
    }
    for row in rows:
        assert row["why"].strip(), f"row {row['row_id']} has no reason to be in the set"
    assert [int(row["row_id"]) for row in rows] == list(range(len(rows)))


def test_the_hazard_rows_are_the_parity_hazards_and_are_not_retyped() -> None:
    """One row set across two seams — and imported, so it cannot drift from parity's."""
    import csv

    sys.path.insert(0, str(REPO / "src"))
    from taxi_mlops.serving import parity

    with ROWS_CSV.open() as handle:
        hazards = [row for row in csv.DictReader(handle) if row["stratum"] == "hazard"]
    assert len(hazards) == len(parity.HAZARDS)
    for row, hazard in zip(hazards, parity.HAZARDS, strict=True):
        assert row["pickup_datetime"] == hazard.request.pickup_datetime
        assert int(row["PULocationID"]) == hazard.request.pu_location_id
        assert int(row["DOLocationID"]) == hazard.request.do_location_id
        assert row["why"].startswith(hazard.name)
    source = ROWS_SCRIPT.read_text(encoding="utf-8")
    assert "parity.HAZARDS" in source, "the hazards must be imported, never copied"


def test_the_boundary_rows_straddle_every_train_month_boundary() -> None:
    import csv

    sys.path.insert(0, str(REPO / "src"))
    from taxi_mlops.data.config import load_splits

    with ROWS_CSV.open() as handle:
        boundary = [row for row in csv.DictReader(handle) if row["stratum"] == "month-boundary"]
    assert len(boundary) == 2 * len(load_splits().train)
    for index in range(0, len(boundary), 2):
        before = boundary[index]["pickup_datetime"]
        after = boundary[index + 1]["pickup_datetime"]
        assert before[8:10] != "01" and after[8:10] == "01", (
            "a boundary pair is the last minute of one month and the first of the next"
        )


def test_the_drawn_strata_refuse_to_come_back_short() -> None:
    """The guard that replaced `USING SAMPLE ... REPEATABLE`, which returned zero
    airport rows out of 3,237,471 and said nothing (gotcha #78's family)."""
    source = ROWS_SCRIPT.read_text(encoding="utf-8")
    assert "if len(frame) != PER_STRATUM:" in source

    # Asked of the SQL the drawer actually builds, not of the file: the module
    # docstring for SEED quotes `USING SAMPLE ... REPEATABLE` at length to explain
    # why it is gone, and a body search would match the explanation (gotcha #99).
    tree = ast.parse(source)
    drawer = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_drawn_rows"
    )
    sql = "".join(
        node.value
        for node in ast.walk(drawer)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    )
    assert "ORDER BY hash(" in sql
    assert "USING SAMPLE" not in sql, (
        "the sampled draw returned ZERO airport rows out of 3,237,471 because DuckDB "
        "samples the scan and not the filtered set"
    )


# ------------------------------------------------------------- the records ---
@pytest.mark.needs_records
def test_the_measured_parity_is_exact_and_no_column_is_one_sidedly_null() -> None:
    record = json.loads(PARITY_RECORD.read_text())
    assert record["tolerance"] == 0.0
    assert record["max_abs_delta_over_all_float_columns"] == 0.0
    assert record["rows"] == 88
    for column in record["columns"]:
        assert column["mismatches"] == 0, f"{column['column']} disagrees with the feature path"
        assert column["one_missing"] == 0, (
            f"{column['column']} is null on exactly one side — the store and the feature "
            "path disagree about whether this row has a value at all"
        )
    for shortfall in record["shortfalls"]:
        assert not shortfall["unexplained"], f"{shortfall['answer']} lost rows (F-056)"


@pytest.mark.needs_records
def test_the_no_geometry_rows_are_asserted_two_sidedly() -> None:
    record = json.loads(PARITY_RECORD.read_text())
    checks = {check["side"]: check for check in record["no_geometry"]["checks"]}
    for side in ("pu", "do"):
        assert checks[side]["rows_without_geometry"] > 0, (
            "the row set no longer covers zones 264/265 — about 1% of every split, and "
            "the class F-030 was found on"
        )
        assert checks[side]["store_returned_null_for_all"]
        assert checks[side]["store_returned_a_row_for_any"] == 0
    assert checks["row"]["rows_without_geometry"] > 0


@pytest.mark.needs_records
def test_the_naive_join_leaks_and_the_honest_one_is_pinned_to_our_tables() -> None:
    proof = json.loads(PROOF_RECORD.read_text())
    assert proof["naive_equals_full_window"]["mismatches"] == 0, (
        "the naive answer must BE our full-window table; without that the difference "
        "below is only 'two joins disagree'"
    )
    leaking = [column for column, spread in proof["leak"].items() if spread["differing_rows"] > 0]
    assert len(leaking) == 3, (
        "a naive join that produces no difference proves nothing — that is a defect in the "
        "row set or the stamps, not a clean bill of health"
    )
    assert proof["leak"]["od_median_duration_min"]["one_missing"] > 0, (
        "the purest form of the leak is a row the honest join must tell NOTHING and the "
        "naive one answers — 2019-01 has no history at all"
    )


@pytest.mark.needs_records
def test_every_month_boundary_pair_was_served_a_different_window() -> None:
    proof = json.loads(PROOF_RECORD.read_text())
    pairs = proof["boundary_pairs"]
    assert len(pairs) == 6
    for pair in pairs:
        assert pair["seconds_apart"] == 120
        assert pair["windows_differ"], (
            f"{pair['before']} and {pair['after']} were served the same window; the "
            "end-of-window convention is what makes them differ"
        )
    first = pairs[0]
    assert first["od_median_before"] is None and first["od_median_after"] is not None, (
        "the first boundary is the one the convention exists for: two minutes apart, one "
        "row is entitled to nothing and the other to January"
    )
    assert len({pair["od_median_naive"] for pair in pairs}) == 1, (
        "the naive join gives every row the same answer, which is what makes it look stable"
    )
