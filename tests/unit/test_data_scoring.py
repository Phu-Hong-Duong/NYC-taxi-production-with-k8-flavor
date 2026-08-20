"""The scoring tree (M7-S1): the same contract, a different destination.

What must hold, and each of these is a way the story could have gone wrong
without anything looking broken:

* a scoring month lands in the scoring trees and **nowhere else** — one row of
  2020 inside ``data/processed/`` reaches the training matrix, the marts and
  every board through globs written when that directory meant "the settled 2019
  months", and it arrives with no error anywhere (M7 law 2);
* ``trips_clean`` does not grow scoring rows — the view every KPI, mart and card
  is defined over must keep meaning what it meant;
* the scoring reconciliations can say NO, per month and per (month, rule);
* a month may not be a split month AND a scoring month;
* the contract probe measures without acquiring.
"""

from __future__ import annotations

import dataclasses
import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from conftest import raw_frame

from taxi_mlops.data.analyst import (
    SCORING_VIEWS,
    VIEWS,
    build,
    ingested_scoring_months,
    report,
    scoring_reconciliation,
    scoring_rejection_reconciliation,
)
from taxi_mlops.data.config import load_config
from taxi_mlops.data.ingest import ingest

SPLIT_ROWS = {"2019-01": 12, "2019-02": 9, "2019-03": 6}
SCORING_ROWS = {"2020-01": 7, "2020-02": 5}


def _seed(cfg, month: str, rows: int) -> None:
    path = cfg.raw_path(month)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(raw_frame(month, rows), preserve_index=False), path)


@pytest.fixture
def scoring_cfg(data_cfg, tmp_path):
    """Three split months and two scoring months, all really ingested."""
    analyst = dict(data_cfg.analyst)
    analyst["database_path"] = str(tmp_path / "analyst.duckdb")
    scoring = dict(data_cfg.scoring)
    scoring["months"] = list(SCORING_ROWS)
    cfg = dataclasses.replace(data_cfg, analyst=analyst, scoring=scoring)
    for month, rows in {**SPLIT_ROWS, **SCORING_ROWS}.items():
        _seed(cfg, month, rows)
    ingest(list(cfg.splits.months), cfg)
    ingest(cfg=cfg, scoring=True)
    return cfg


# ---- the config: one month, one meaning ------------------------------------


def test_a_month_may_not_be_both_a_split_and_a_scoring_month(tmp_path):
    """The one mistake the two-file separation makes possible, checked."""
    import yaml

    from taxi_mlops.data.config import repo_root

    # Built from the SHIPPED config so the guard is exercised against the real
    # file's shape, not against an invented one.
    data_yaml = tmp_path / "data.yaml"
    raw = yaml.safe_load((repo_root() / "configs" / "data.yaml").read_text())
    raw["scoring"]["months"] = ["2019-01"]  # already the first train month
    data_yaml.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match="never both"):
        load_config(data_yaml)


def test_the_shipped_config_names_disjoint_month_lists():
    cfg = load_config()
    assert set(cfg.scoring_months).isdisjoint(cfg.splits.months)
    assert cfg.scoring_months, "M7-S1 configured scoring months; an empty list is a regression"


def test_label_of_dispatches_and_names_both_files_when_it_cannot(scoring_cfg):
    assert scoring_cfg.label_of("2020-01") == "scoring"
    assert scoring_cfg.label_of("2019-01") == "train"
    with pytest.raises(KeyError, match="named nowhere"):
        scoring_cfg.label_of("2031-12")


def test_the_settled_path_methods_never_answer_for_a_scoring_month(scoring_cfg):
    """processed_path/rejected_path/rejections_path mean 'the settled months'.

    Every existing caller — the training matrix, the rebuild proof, the marts,
    the analyst's trips_clean — reads them with that meaning. A dispatcher
    hiding in them would put a 2020 month wherever any of them is called.
    """
    for method in ("processed_path", "rejected_path", "rejections_path"):
        with pytest.raises(KeyError):
            getattr(scoring_cfg, method)("2020-01")


# ---- the trees: where the rows land, and where they do not ------------------


def test_a_scoring_month_lands_only_in_the_scoring_trees(scoring_cfg):
    for month in SCORING_ROWS:
        assert scoring_cfg.scoring_path(month).exists()
        assert scoring_cfg.scoring_rejected_path(month).exists()
        assert scoring_cfg.scoring_rejections_path(month).exists()

    from pathlib import Path

    settled = list(scoring_cfg.path_for("processed_dir").rglob("*.parquet"))
    settled += list(Path(scoring_cfg.rejected["dir"]).rglob("*.parquet"))
    assert settled, "the settled trees should exist — this test is about what is NOT in them"
    assert not [p for p in settled if "2020" in p.name]


def test_trips_clean_never_grows_a_scoring_row(scoring_cfg):
    """The view every KPI, mart and board is defined over keeps its meaning."""
    build(scoring_cfg)
    import duckdb

    con = duckdb.connect(str(scoring_cfg.analyst["database_path"]), read_only=True)
    try:
        assert con.execute("SELECT COUNT(*) FROM trips_clean").fetchone()[0] == sum(
            SPLIT_ROWS.values()
        )
        assert con.execute("SELECT COUNT(*) FROM trips_scoring").fetchone()[0] == sum(
            SCORING_ROWS.values()
        )
        splits = {r[0] for r in con.execute("SELECT DISTINCT split FROM trips_clean").fetchall()}
        assert splits == {"train", "val", "test"}
        assert {
            r[0] for r in con.execute("SELECT DISTINCT split FROM trips_scoring").fetchall()
        } == {"scoring"}
    finally:
        con.close()


def test_the_scoring_views_appear_only_when_the_tree_does(data_cfg, tmp_path):
    """`make data`, `make rebuild-proof` and the M1 gate run without a scoring month."""
    analyst = dict(data_cfg.analyst)
    analyst["database_path"] = str(tmp_path / "analyst.duckdb")
    cfg = dataclasses.replace(data_cfg, analyst=analyst)
    for month, rows in SPLIT_ROWS.items():
        _seed(cfg, month, rows)
    ingest(list(cfg.splits.months), cfg)

    assert ingested_scoring_months(cfg) == []
    created = build(cfg)
    assert sorted(created) == sorted(VIEWS)
    assert not set(SCORING_VIEWS) & set(created)


def test_build_creates_exactly_the_published_scoring_view_names(scoring_cfg):
    created = build(scoring_cfg)
    assert set(SCORING_VIEWS) <= set(created)
    assert sorted(created) == sorted(VIEWS + SCORING_VIEWS)


# ---- the reconciliations: they must be able to say NO -----------------------


def test_the_scoring_reconciliations_agree_on_a_clean_build(scoring_cfg, capsys):
    build(scoring_cfg)
    rows = scoring_reconciliation(scoring_cfg)
    assert {r[0] for r in rows} == set(SCORING_ROWS)
    assert all(agree for *_, agree in rows)
    assert {month: n for month, n, _, _ in rows} == SCORING_ROWS

    rules = scoring_rejection_reconciliation(scoring_cfg)
    assert rules and all(agree for *_, agree in rules)
    assert report(scoring_cfg) is True
    assert "scoring months (M7)" in capsys.readouterr().out


def test_a_scoring_month_that_lost_rows_is_caught(scoring_cfg):
    """RED-TEAM: the failure with no symptom — every drift number just gets smaller."""
    build(scoring_cfg)
    victim = scoring_cfg.scoring_path("2020-01")
    table = pq.read_table(victim)
    pq.write_table(table.slice(0, 3), victim)

    build(scoring_cfg)
    rows = scoring_reconciliation(scoring_cfg)
    bad = [r for r in rows if not r[3]]
    assert [r[0] for r in bad] == ["2020-01"]
    assert bad[0][1:3] == (3, SCORING_ROWS["2020-01"])
    assert report(scoring_cfg) is False


def test_a_scoring_sidecar_filed_under_the_wrong_rule_is_caught(scoring_cfg):
    """RED-TEAM: per (month, rule), because a monthly total hides a relabelling.

    The sidecar's whole job is answering *which kind* of row was dropped. A
    sidecar with a perfect monthly total and every row under the wrong rule
    answers that question wrongly, confidently, forever.
    """
    build(scoring_cfg)
    month = "2020-01"
    # Give the month one genuinely rejected row, then relabel it.
    report_path = scoring_cfg.scoring_rejections_path(month)
    payload = json.loads(report_path.read_text())
    payload["rules"][0]["rejected_by"] += 1
    payload["rules"][1]["rejected_by"] -= 1
    report_path.write_text(json.dumps(payload))

    build(scoring_cfg)
    rules = scoring_rejection_reconciliation(scoring_cfg)
    disagreed = [r for r in rules if not r[4]]
    assert {r[1] for r in disagreed} >= {payload["rules"][0]["name"]}
    assert report(scoring_cfg) is False


# ---- the contract's refusal shapes -----------------------------------------


def test_a_renamed_required_column_names_the_absence_AND_the_arrival(data_cfg):
    """Measured at M7-S1: the message used to name only half of what happened.

    A rename raises in the missing-required branch, which returns before the
    unknown-column branch can run — so an operator was told a field had
    vanished and never told what had arrived in its place.
    """
    from taxi_mlops.data.contract import validate_input
    from taxi_mlops.data.errors import SchemaEventError

    df = raw_frame("2019-01", 4).rename(columns={"VendorID": "VendorID_v2"})
    with pytest.raises(SchemaEventError) as excinfo:
        validate_input(df, "2019-01", data_cfg)
    message = str(excinfo.value)
    assert "VendorID" in message and "VendorID_v2" in message
    assert "aliases" in message


def test_the_probe_refuses_to_acquire_into_data_raw():
    """A probe that leaves data behind is an ingest wearing a smaller name."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    import contract_probe

    assert contract_probe.main(["--month", "2025-01", "--raw-dir", "data/raw"]) == 2


def test_the_probe_writes_nothing_under_any_data_tree():
    """AST, not grep: the file argues about writing at length (gotchas #53/#68)."""
    import ast
    from pathlib import Path

    source = (Path(__file__).resolve().parents[2] / "scripts" / "contract_probe.py").read_text()
    tree = ast.parse(source)
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    for forbidden in ("write_processed", "write_parquet", "to_parquet"):
        assert forbidden not in called
    names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "write_processed" not in names
    assert "ingest" not in names and "ingest_month" not in names
