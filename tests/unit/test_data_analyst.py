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
from taxi_mlops.data.analyst import (
    OPTIONAL_VIEWS,
    VIEWS,
    build,
    build_sql,
    database_path,
    prediction_reconciliation,
    predicted_months,
    reconciliation,
    rejection_reconciliation,
    report,
)
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
    # One branch per configured month per parquet-backed view, no more: a glob
    # would silently pick up strays. Two such views since M2-S1 — trips_clean
    # and trips_rejected — and the count is spelled out rather than hardcoded so
    # a third one has to come here and say so.
    parquet_views = ("trips_clean", "trips_rejected")
    assert statements.count("read_parquet(") == len(parquet_views) * len(
        analyst_cfg.splits.months
    )
    for view in parquet_views:
        assert f"CREATE OR REPLACE VIEW {view} AS" in statements


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


# ------------------------------- the retained rejected rows (M2-S1, F-005) ----

DIRTY = {"2019-01": (40, 3), "2019-02": (20, 1), "2019-03": (20, 0)}


@pytest.fixture
def dirty_cfg(data_cfg, tmp_path):
    """Months that really lose rows, so the sidecar has something to be wrong about.

    `analyst_cfg`'s months are clean end to end — perfect for the row-count
    reconciliation and useless for this one, where every count under test is
    zero unless something was actually rejected.
    """
    analyst = dict(data_cfg.analyst)
    analyst["database_path"] = str(tmp_path / "analyst.duckdb")
    cfg = dataclasses.replace(data_cfg, analyst=analyst)
    for month, (rows, bad) in DIRTY.items():
        df = raw_frame(month, rows)
        if bad:
            df.loc[0, "trip_distance"] = 0.0  # distance_non_positive
        if bad > 1:
            df.loc[1, "fare_amount"] = -5.0  # fare_negative
        if bad > 2:
            # both, in one row: filed under the first, listing both
            df.loc[2, "trip_distance"] = 0.0
            df.loc[2, "fare_amount"] = -5.0
        path = cfg.raw_path(month)
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pandas(df, preserve_index=False), path)
    ingest(list(cfg.splits.months), cfg)
    return cfg


def test_trips_rejected_publishes_the_rows_the_counts_describe(dirty_cfg):
    """F-005's closing capability, in SQL: not 'how many' but 'which kind'."""
    build(dirty_cfg)
    con = __import__("duckdb").connect(str(database_path(dirty_cfg)), read_only=True)
    try:
        per_month = con.execute(
            "SELECT month, COUNT(*) FROM trips_rejected GROUP BY month ORDER BY month"
        ).fetchall()
        rules = con.execute(
            "SELECT rejection_rule, rejection_rules, COUNT(*) FROM trips_rejected "
            "GROUP BY 1, 2 ORDER BY 1, 2"
        ).fetchall()
        splits = con.execute(
            "SELECT DISTINCT split, month FROM trips_rejected ORDER BY month"
        ).fetchall()
    finally:
        con.close()
    assert per_month == [(m, bad) for m, (_rows, bad) in sorted(DIRTY.items()) if bad]
    assert ("distance_non_positive", "distance_non_positive,fare_negative", 1) in rules
    assert ("fare_negative", "fare_negative", 1) in rules
    # split labels are config facts here exactly as they are in trips_clean
    assert splits == [
        (dirty_cfg.splits.split_of(m), m) for m, (_r, b) in sorted(DIRTY.items()) if b
    ]


def test_a_rejected_row_never_appears_in_the_clean_view(dirty_cfg):
    """The two views must not overlap. `trips_rejected` is deliberately NOT
    unioned into `trips_clean`: one careless SELECT must not train on rows the
    output contract refused."""
    build(dirty_cfg)
    con = __import__("duckdb").connect(str(database_path(dirty_cfg)), read_only=True)
    try:
        clean_bad = con.execute(
            "SELECT COUNT(*) FROM trips_clean WHERE trip_distance <= 0 OR fare_amount < 0"
        ).fetchone()[0]
        clean_rows, rejected_rows = (
            con.execute("SELECT COUNT(*) FROM trips_clean").fetchone()[0],
            con.execute("SELECT COUNT(*) FROM trips_rejected").fetchone()[0],
        )
        columns = [r[0] for r in con.execute("DESCRIBE trips_clean").fetchall()]
    finally:
        con.close()
    assert clean_bad == 0
    assert clean_rows + rejected_rows == sum(rows for rows, _bad in DIRTY.values())
    assert "rejection_rule" not in columns  # the clean view has no such notion


def test_rejection_reconciliation_agrees_rule_by_rule(dirty_cfg):
    build(dirty_cfg)
    rows = rejection_reconciliation(dirty_cfg)
    assert all(agree for *_, agree in rows)
    # every configured rule is checked for every month, including the ones that
    # never fire: a rule with no rows is exactly how a broken rule looks
    assert len(rows) == len(dirty_cfg.clean["rules"]) * len(DIRTY)
    assert sum(observed for *_, observed, _e, _a in rows) == sum(b for _r, b in DIRTY.values())
    assert report(dirty_cfg) is True


def test_reconciliation_catches_a_sidecar_that_lost_rows(dirty_cfg):
    """RED-TEAM, the counts' half of the M1-S2 lesson: a sidecar missing rows
    answers every query happily and only disagrees with what ingest COUNTED."""
    build(dirty_cfg)
    victim = dirty_cfg.rejected_path("2019-01")
    pq.write_table(pq.read_table(victim).slice(0, 1), victim)  # 3 rejected rows -> 1

    disagreed = [r for r in rejection_reconciliation(dirty_cfg) if not r[5]]
    assert {r[1] for r in disagreed} == {"2019-01"}
    assert sum(expected - observed for *_, observed, expected, _ in disagreed) == 2
    assert report(dirty_cfg) is False


def test_reconciliation_catches_rows_filed_under_the_wrong_rule(dirty_cfg):
    """The monthly total can be perfect while every row is misfiled — and a
    sidecar filed under the wrong rule is useless for the one question it exists
    to answer. Hence per (month, rule), never per month."""
    build(dirty_cfg)
    victim = dirty_cfg.rejected_path("2019-01")
    table = pq.read_table(victim)
    index = table.schema.get_field_index("rejection_rule")
    relabelled = pa.array(["fare_negative"] * table.num_rows, type=table.schema.field(index).type)
    pq.write_table(table.set_column(index, "rejection_rule", relabelled), victim)

    rows = rejection_reconciliation(dirty_cfg)
    assert sum(r[3] for r in rows) == 4  # the TOTAL is untouched: 3 + 1 rejected rows
    disagreed = {(r[1], r[2]) for r in rows if not r[5]}
    assert disagreed == {("2019-01", "fare_negative"), ("2019-01", "distance_non_positive")}
    assert report(dirty_cfg) is False


def test_cli_duckdb_exits_nonzero_when_the_sidecar_disagrees(dirty_cfg, monkeypatch):
    """The exit code is the contract, for this reconciliation as for the other."""
    monkeypatch.setattr(cli, "load_config", lambda *a, **k: dirty_cfg)
    assert cli.main(["duckdb"]) == 0
    victim = dirty_cfg.rejected_path("2019-02")
    pq.write_table(pq.read_table(victim).slice(0, 0), victim)  # 1 rejected row -> 0
    assert cli.main(["duckdb"]) == 1


def test_build_refuses_when_the_sidecar_is_absent(dirty_cfg):
    """A missing sidecar must say 'run make ingest', not surface as a DuckDB
    parse error inside someone's query three views later."""
    missing = dirty_cfg.rejected_path("2019-01")
    missing.unlink()
    with pytest.raises(FileNotFoundError, match=missing.name):
        build(dirty_cfg)


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


# --------------------------------------------------------------------------- #
# The published predictions (M2-S4): a view that must not exist until it can,
# and a reconciliation that must refuse a model scored on a subset.
# --------------------------------------------------------------------------- #


def seed_predictions(cfg, *, months=None, drop=0, relabel=None):
    """Write prediction files the way `taxi_mlops.training.score` writes them.

    Deliberately through the SHIPPING writer and off the SHIPPING processed
    parquet, so this exercises the contract other layers cite rather than a
    fixture invented here.
    """
    import pandas as pd

    from taxi_mlops.training import predictions as predictions_mod

    months = months or list(cfg.splits.val + cfg.splits.test)
    for month in months:
        source = pd.read_parquet(cfg.processed_path(month))
        rows = len(source) - drop
        source = source.head(rows)
        matrix = pd.DataFrame(
            {
                "hour": source["tpep_pickup_datetime"].dt.hour.astype("int16"),
                "dayofweek": source["tpep_pickup_datetime"].dt.dayofweek.astype("int16"),
                "PULocationID": source["PULocationID"].astype("int16"),
                "DOLocationID": source["DOLocationID"].astype("int16"),
                "passenger_count": source["passenger_count"].astype("float32"),
            }
        )
        actual = source["trip_duration_minutes"].astype("float64")
        frame = predictions_mod.build_frame(
            split=relabel or cfg.splits.split_of(month),
            month=month,
            features=matrix,
            actual=actual,
            predicted=actual.to_numpy() + 1.0,
            floor_predicted=actual.to_numpy() + 2.0,
            floor_unseen=[False] * rows,
            model_name="nyc-taxi-eta",
            model_version="1",
        )
        predictions_mod.write(frame, cfg.predictions_path(month), cfg)
    predictions_mod.write_manifest(
        predictions_mod.manifest(
            model={"name": "nyc-taxi-eta", "alias": "champion", "version": "1"},
            floor={"name": "baseline-group-median"},
            tolerance_minutes=5.0,
            metrics=[],
        ),
        cfg.predictions_manifest_path(),
    )


def test_the_data_path_builds_when_no_model_has_ever_been_scored(analyst_cfg, capsys):
    """The catalogue must not depend on the modelling path.

    Prevents the dependency running backwards: `make data`, `make rebuild-proof`
    and the whole M1 gate run on a repo where no champion exists, and a layer that
    refused to build without one would make the data path wait for a model.
    """
    assert predicted_months(analyst_cfg) == []
    assert sorted(build(analyst_cfg)) == sorted(VIEWS)
    assert report(analyst_cfg) is True
    assert "no model output" in capsys.readouterr().out


def test_scored_months_add_exactly_the_optional_views_and_reconcile(analyst_cfg):
    seed_predictions(analyst_cfg)
    assert predicted_months(analyst_cfg) == list(
        analyst_cfg.splits.val + analyst_cfg.splits.test
    )
    assert sorted(build(analyst_cfg)) == sorted(VIEWS + OPTIONAL_VIEWS)
    rows = prediction_reconciliation(analyst_cfg)
    assert [(split, month, agree) for split, month, _o, _e, agree in rows] == [
        ("val", "2019-02", True),
        ("test", "2019-03", True),
    ]
    assert report(analyst_cfg) is True


def test_the_view_derives_the_error_columns_every_consumer_reads(analyst_cfg):
    """`abs_error_minutes` is defined ONCE, in the view, from the two columns
    that define it — so a mart, a card and a memo cannot mean three things."""
    seed_predictions(analyst_cfg)
    build(analyst_cfg)
    con = __import__("duckdb").connect(str(database_path(analyst_cfg)), read_only=True)
    try:
        columns = {r[0] for r in con.execute("DESCRIBE predictions").fetchall()}
        errors = con.execute(
            "SELECT DISTINCT ROUND(abs_error_minutes, 6), ROUND(signed_error_minutes, 6), "
            "ROUND(floor_abs_error_minutes, 6) FROM predictions"
        ).fetchall()
    finally:
        con.close()
    assert {"abs_error_minutes", "signed_error_minutes", "floor_abs_error_minutes"} <= columns
    # the fixture quotes every trip 1 minute long and the floor 2 minutes long
    assert errors == [(1.0, 1.0, 2.0)]


def test_reconciliation_refuses_a_model_scored_on_a_subset(analyst_cfg):
    """RED-TEAM. A model scored on 90% of a holdout produces a perfectly
    plausible MAE — an average over a subset nobody chose, with no symptom."""
    seed_predictions(analyst_cfg, drop=2)
    build(analyst_cfg)
    rows = prediction_reconciliation(analyst_cfg)
    assert [agree for *_rest, agree in rows] == [False, False]
    assert report(analyst_cfg) is False


def test_reconciliation_refuses_predictions_labelled_with_the_wrong_split(analyst_cfg):
    """RED-TEAM, and the reason the join is a FULL OUTER one: relabelling a
    holdout is undetectable downstream — every number stays right and describes
    the wrong month."""
    seed_predictions(analyst_cfg, months=list(analyst_cfg.splits.val), relabel="test")
    build(analyst_cfg)
    rows = prediction_reconciliation(analyst_cfg)
    # the val month is missing entirely, and a ('test', '2019-02') pair appears
    # that the ingest report has never heard of
    assert ("test", "2019-02", False) in [(s, m, a) for s, m, _o, _e, a in rows]
    assert report(analyst_cfg) is False


def test_prediction_runs_reports_the_evaluators_numbers_and_never_computes_them(analyst_cfg):
    """The provenance view: which champion produced these rows. It is read from
    the manifest the evaluator wrote — this layer has no other way to know, and
    must not acquire one."""
    seed_predictions(analyst_cfg)
    build(analyst_cfg)
    con = __import__("duckdb").connect(str(database_path(analyst_cfg)), read_only=True)
    try:
        rows = con.execute(
            "SELECT DISTINCT model_name, model_version, model_alias FROM prediction_runs"
        ).fetchall()
    finally:
        con.close()
    # the seeded manifest carries no split metrics, so the view is empty of rows
    # but exists and is typed — an absent view and an empty one are different
    # failures and only the first should ever be silent
    assert rows == []
