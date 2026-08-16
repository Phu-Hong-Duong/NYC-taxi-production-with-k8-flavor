"""The DuckDB analyst layer — cluster-free, network-free, built on real artifacts.

The fixture runs the REAL ingest over tiny seeded months, so the views here are
built over parquet and rejection JSON that the shipping code wrote. A test that
hand-writes its own fixture files stops testing the pipeline and starts testing
the fixture.

What must say NO:

* a catalogue whose views see a different number of rows than the ingest report
  that produced them — the failure that looks like healthy, smaller numbers;
* a build over processed data that is not there — silent empty views are worse
  than a missing file;
* a view reaching into ``data/raw`` for rows (DA charter refusal #2).
"""

from __future__ import annotations

import dataclasses
import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from conftest import raw_frame

from taxi_mlops.data import __main__ as cli
from taxi_mlops.data.analyst import VIEWS, build, build_sql, database_path, reconciliation, report
from taxi_mlops.data.ingest import ingest

ROWS = {"2019-01": 12, "2019-02": 9, "2019-03": 6}


@pytest.fixture
def analyst_cfg(data_cfg, tmp_path):
    """Three tiny months, really ingested, with the catalogue redirected into tmp."""
    # Only the PATH is redirected: the shipped known_domains ride along, so this
    # tests the domains that actually ship rather than a copy invented here.
    analyst = dict(data_cfg.analyst)
    analyst["database_path"] = str(tmp_path / "analyst.duckdb")
    cfg = dataclasses.replace(data_cfg, analyst=analyst)
    for month, rows in ROWS.items():
        path = cfg.raw_path(month)
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(
            pa.Table.from_pandas(raw_frame(month, rows), preserve_index=False), path
        )
    ingest(list(cfg.splits.months), cfg)
    return cfg


def test_build_creates_exactly_the_published_view_names(analyst_cfg):
    """VIEWS is what the EDA report, dbt sources and boards will cite by name."""
    created = build(analyst_cfg)
    assert sorted(created) == sorted(VIEWS)
    assert database_path(analyst_cfg).exists()


def test_build_is_idempotent(analyst_cfg):
    assert sorted(build(analyst_cfg)) == sorted(build(analyst_cfg)) == sorted(VIEWS)


def test_view_counts_reconcile_with_the_ingest_report(analyst_cfg):
    build(analyst_cfg)
    rows = reconciliation(analyst_cfg)
    assert {r[1] for r in rows} == set(ROWS)  # every configured month present
    assert all(agree for *_, agree in rows)
    observed = {month: n for _, month, n, _, _ in rows}
    assert observed == ROWS  # these months are clean end to end: nothing dropped


def test_reconciliation_catches_a_catalogue_that_lost_a_month(analyst_cfg):
    """RED-TEAM: the failure mode with no symptom — every number just gets smaller.

    A month whose parquet is truncated to fewer rows still answers every query
    happily. Only the cross-check against what ingest SAID it wrote notices.
    """
    build(analyst_cfg)
    victim = analyst_cfg.processed_path("2019-02")
    table = pq.read_table(victim)
    pq.write_table(table.slice(0, 3), victim)  # 9 rows -> 3, nothing else touched

    rows = reconciliation(analyst_cfg)
    disagreed = [r for r in rows if not r[4]]
    assert [r[1] for r in disagreed] == ["2019-02"]
    assert disagreed[0][2] == 3 and disagreed[0][3] == ROWS["2019-02"]
    assert report(analyst_cfg) is False


def test_cli_duckdb_exits_nonzero_when_counts_disagree(analyst_cfg, monkeypatch):
    """The exit code is the contract: `make data` must fail, not print a warning."""
    monkeypatch.setattr(cli, "load_config", lambda *a, **k: analyst_cfg)
    assert cli.main(["duckdb"]) == 0

    report_path = analyst_cfg.rejections_path("2019-03")
    written = json.loads(report_path.read_text())
    written["rows_out"] += 1  # ingest now claims one row more than it wrote
    report_path.write_text(json.dumps(written))

    assert cli.main(["duckdb"]) == 1


def test_build_refuses_when_processed_data_is_absent(analyst_cfg):
    missing = analyst_cfg.processed_path("2019-01")
    missing.unlink()
    with pytest.raises(FileNotFoundError, match=missing.name):
        build(analyst_cfg)


def test_split_labels_come_from_config_not_from_filenames(analyst_cfg):
    """Rename a file and the label must not follow — the label is a config fact."""
    statements = "\n".join(build_sql(analyst_cfg))
    for month in analyst_cfg.splits.months:
        split = analyst_cfg.splits.split_of(month)
        assert f"SELECT '{split}' AS split, '{month}' AS month" in statements
    # one branch per configured month, no more: a glob would silently pick up strays
    assert statements.count("read_parquet(") == len(analyst_cfg.splits.months)


def test_no_view_reads_raw_parquet(analyst_cfg):
    """DA charter refusal: the analyst queries clean tables, never the raw files.

    The raw MANIFEST is fair game — a checksum is provenance, not data — so the
    assertion is specific: nothing under raw_dir with a .parquet extension.
    """
    statements = "\n".join(build_sql(analyst_cfg))
    raw_dir = str(analyst_cfg.path_for("raw_dir"))
    assert f"{raw_dir}/yellow_tripdata" not in statements
    assert str(analyst_cfg.path_for("manifest_path")) in statements  # provenance kept


def test_data_health_joins_rows_to_the_sha256_that_produced_them(analyst_cfg):
    """The board-ready view: without the pin, 'is this the data we think?' is unanswerable."""
    build(analyst_cfg)
    con = __import__("duckdb").connect(str(database_path(analyst_cfg)), read_only=True)
    try:
        rows = con.execute(
            "SELECT month, rows_out, raw_sha256, rejected_pct FROM data_health ORDER BY month"
        ).fetchall()
    finally:
        con.close()
    assert [r[0] for r in rows] == sorted(ROWS)
    manifest = json.loads(analyst_cfg.path_for("manifest_path").read_text())["files"]
    for month, rows_out, sha, _pct in rows:
        assert sha == manifest[month]["sha256"]
        assert rows_out == ROWS[month]


def test_unknown_domain_values_reports_but_never_rejects(analyst_cfg):
    """DCR-02/DCR-04: drift by VALUE has no symptom — a new code just becomes a
    category on a board. The view must SEE an undocumented value and the row
    must survive: this reports, it does not clean."""
    victim = analyst_cfg.processed_path("2019-01")
    table = pq.read_table(victim)
    payments = table.column("payment_type").to_pylist()
    payments[0] = 0  # not in the TLC dictionary — and not null, so it looks real
    table = table.set_column(
        table.schema.get_field_index("payment_type"),
        "payment_type",
        pa.array(payments, type=table.schema.field("payment_type").type),
    )
    pq.write_table(table, victim)

    build(analyst_cfg)
    con = __import__("duckdb").connect(str(database_path(analyst_cfg)), read_only=True)
    try:
        found = con.execute(
            "SELECT column_name, value, rows FROM unknown_domain_values ORDER BY column_name"
        ).fetchall()
        kept = con.execute(
            "SELECT COUNT(*) FROM trips_clean WHERE month = '2019-01'"
        ).fetchone()
    finally:
        con.close()
    assert ("payment_type", "0", 1) in found
    assert kept[0] == ROWS["2019-01"]  # reported, not dropped
    assert all(agree for *_, agree in reconciliation(analyst_cfg))


def test_documented_domains_come_from_config(analyst_cfg):
    """The domains are documentation, so they live in configs — but they must
    actually reach the SQL, or the view silently reports nothing forever."""
    statements = "\n".join(build_sql(analyst_cfg))
    for column in analyst_cfg.analyst["known_domains"]:
        assert f"'{column}' AS column_name" in statements
    assert "'99'" not in statements  # RatecodeID 99 is data, never a documented value


def test_rejection_counts_are_queryable_per_rule(analyst_cfg):
    """S1 wrote them beside the data; a board needs them in SQL, per rule and month."""
    build(analyst_cfg)
    con = __import__("duckdb").connect(str(database_path(analyst_cfg)), read_only=True)
    try:
        rules = con.execute(
            "SELECT DISTINCT rule FROM ingest_rejections ORDER BY rule"
        ).fetchall()
        months = con.execute("SELECT COUNT(DISTINCT month) FROM ingest_rejections").fetchone()
    finally:
        con.close()
    configured = sorted(r["name"] for r in analyst_cfg.clean["rules"])
    assert [r[0] for r in rules] == configured
    assert months[0] == len(ROWS)
