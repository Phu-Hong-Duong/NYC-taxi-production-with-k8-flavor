"""Batch inference on the scoring months (M7-S2): what may be written, and where.

Each test below is a way this story could have gone wrong with nothing looking
broken — which is the failure mode a monitoring table is uniquely exposed to,
because its numbers have no registry tag to disagree with.

* the rows land in the scoring-predictions tree and **nowhere else** — a 2020
  file under ``data/predictions/`` is swept into the ``error_segments`` mart,
  whose ``overall`` row is asserted equal to the evaluator's KPI-09/KPI-10;
* the sixth reconciliation can say NO — and it distinguishes *not yet scored*
  from *partly scored*, because only the second produces a plausible number;
* nothing in this path mutates the registry (AST, not grep — gotchas #53/#68);
* the ids stay apart: no KPI-09/KPI-10 anywhere near the monitoring mart, and
  the four new ids are defined in ``docs/kpi_definitions.md`` before any board
  can cite them.
"""

from __future__ import annotations

import ast
import dataclasses
import json
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from conftest import raw_frame

from taxi_mlops.data.analyst import (
    SCORING_PREDICTION_VIEWS,
    build,
    report,
    scored_scoring_months,
    scoring_prediction_reconciliation,
)
from taxi_mlops.data.config import load_config
from taxi_mlops.data.ingest import ingest
from taxi_mlops.training import batch
from taxi_mlops.training import predictions as predictions_mod

REPO_ROOT = Path(__file__).resolve().parents[2]
BATCH_SOURCE = REPO_ROOT / "src" / "taxi_mlops" / "training" / "batch.py"

SPLIT_ROWS = {"2019-01": 12, "2019-02": 9, "2019-03": 6}
SCORING_ROWS = {"2020-01": 7, "2020-02": 5}


def _seed(cfg, month: str, rows: int) -> None:
    path = cfg.raw_path(month)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(raw_frame(month, rows), preserve_index=False), path)


@pytest.fixture
def scored_cfg(data_cfg, tmp_path):
    """Two scoring months ingested, both scored by a stand-in for the champion."""
    analyst = dict(data_cfg.analyst)
    analyst["database_path"] = str(tmp_path / "analyst.duckdb")
    scoring = dict(data_cfg.scoring)
    scoring["months"] = list(SCORING_ROWS)
    cfg = dataclasses.replace(data_cfg, analyst=analyst, scoring=scoring)
    for month, rows in {**SPLIT_ROWS, **SCORING_ROWS}.items():
        _seed(cfg, month, rows)
    ingest(list(cfg.splits.months), cfg)
    ingest(cfg=cfg, scoring=True)
    for month in SCORING_ROWS:
        _publish(cfg, month)
    return cfg


def _rows_out(cfg, month: str) -> int:
    return json.loads(cfg.scoring_rejections_path(month).read_text())["rows_out"]


def _publish(cfg, month: str, *, rows: int | None = None) -> Path:
    """Write a scoring-predictions file the way `batch` would, without a model."""
    source = pq.read_table(cfg.scoring_path(month)).to_pandas()
    if rows is not None:
        source = source.head(rows)
    features = pd.DataFrame(
        {
            "hour": pd.to_datetime(source["tpep_pickup_datetime"]).dt.hour.astype("int16"),
            "dayofweek": pd.to_datetime(
                source["tpep_pickup_datetime"]
            ).dt.dayofweek.astype("int16"),
            "PULocationID": source["PULocationID"],
            "DOLocationID": source["DOLocationID"],
            "passenger_count": source["passenger_count"],
        }
    )
    frame = batch.build_frame(
        month=month,
        pickup_date=pd.to_datetime(source["tpep_pickup_datetime"]).dt.date,
        features=features,
        actual=source["trip_duration_minutes"],
        predicted=source["trip_duration_minutes"].to_numpy() + 1.0,
        model_name="nyc-taxi-eta",
        model_version="2",
    )
    return predictions_mod.write(
        frame,
        cfg.scoring_predictions_path(month),
        cfg,
        columns=predictions_mod.SCORING_PREDICTION_COLUMNS,
    )


# ---- where the rows may land ------------------------------------------------


def test_a_split_month_has_no_scoring_predictions_path(data_cfg):
    """The refusal that keeps 2020 rows out of the mart the gate is checked by."""
    with pytest.raises(KeyError, match="not in configs/data.yaml"):
        data_cfg.scoring_predictions_path("2019-01")


def test_the_two_prediction_trees_are_different_directories(data_cfg):
    """A subdirectory would be swept up by `data/predictions`'s own glob."""
    scoring_root = Path(data_cfg.scoring_predictions_dir).resolve()
    settled_root = Path(data_cfg.predictions_dir).resolve()
    assert scoring_root != settled_root
    assert settled_root not in scoring_root.parents


def test_the_shipped_config_keeps_them_apart():
    """Checked on the SHIPPED config, not only on the fixture's redirected one."""
    cfg = load_config()
    assert cfg.scoring_predictions_dir != cfg.predictions_dir
    assert not cfg.scoring_predictions_dir.startswith(cfg.predictions_dir.rstrip("/") + "/")


def test_the_scoring_tree_is_gitignored_and_not_dvc_tracked():
    """M2-S4's argument, inherited: a pin refreshed on every champion move lives stale."""
    ignored = (REPO_ROOT / ".gitignore").read_text()
    cfg = load_config()
    assert f"{cfg.scoring_predictions_dir}/" in ignored
    assert not (REPO_ROOT / f"{cfg.scoring_predictions_dir}.dvc").exists()


# ---- the column contract ----------------------------------------------------


def test_the_two_column_contracts_are_separate_objects():
    """Not a superset, not a subset: the two files answer different questions."""
    settled = set(predictions_mod.PREDICTION_COLUMNS)
    scoring = set(predictions_mod.SCORING_PREDICTION_COLUMNS)
    assert "split" in settled and "split" not in scoring
    assert "pickup_date" in scoring and "pickup_date" not in settled
    # The floor is the gate's other half and does not travel to a scoring month.
    assert not any(c.startswith("floor_") for c in scoring)


def test_build_frame_writes_exactly_the_contract(data_cfg):
    features = pd.DataFrame(
        {
            "hour": [1, 2],
            "dayofweek": [3, 4],
            "PULocationID": [100, 200],
            "DOLocationID": [110, 210],
            "passenger_count": [1.0, 2.0],
            "hour_sin": [0.1, 0.2],
        }
    )
    frame = batch.build_frame(
        month="2020-03",
        pickup_date=pd.Series([pd.Timestamp("2020-03-01").date()] * 2),
        features=features,
        actual=pd.Series([10.0, 20.0]),
        predicted=[11.0, 19.0],
        model_name="nyc-taxi-eta",
        model_version="2",
    )
    assert list(frame.columns) == list(predictions_mod.SCORING_PREDICTION_COLUMNS)
    # `hour_sin` is a real feature and is deliberately NOT written: nine geometry
    # and calendar features are a pure function of two identity columns.
    assert "hour_sin" not in frame.columns
    assert frame["model_version"].tolist() == ["2", "2"]


def test_build_frame_refuses_a_matrix_missing_an_identity_column():
    with pytest.raises(ValueError, match="SCORING_PREDICTION_COLUMNS"):
        batch.build_frame(
            month="2020-03",
            pickup_date=pd.Series([pd.Timestamp("2020-03-01").date()]),
            features=pd.DataFrame({"hour": [1]}),
            actual=pd.Series([10.0]),
            predicted=[11.0],
            model_name="nyc-taxi-eta",
            model_version="2",
        )


def test_one_writer_serves_both_trees():
    """The column contract varies; the writer options may not (twins, M2-S4)."""
    source = predictions_mod.write.__doc__ or ""
    assert "columns" in source
    tree = ast.parse((REPO_ROOT / "src/taxi_mlops/training/predictions.py").read_text())
    writers = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "to_parquet"
    ]
    assert len(writers) == 1, "a second to_parquet is a second writer configuration"


# ---- the sixth reconciliation ----------------------------------------------


def test_the_layer_builds_and_the_view_appears(scored_cfg):
    names = build(scored_cfg)
    for view in SCORING_PREDICTION_VIEWS:
        assert view in names
    assert scored_scoring_months(scored_cfg) == list(SCORING_ROWS)


def test_every_scoring_row_got_exactly_one_prediction(scored_cfg):
    build(scored_cfg)
    rows = scoring_prediction_reconciliation(scored_cfg)
    assert {r[0] for r in rows} == set(SCORING_ROWS)
    for month, observed, expected, ok in rows:
        assert ok, f"{month}: {observed} != {expected}"
        assert observed == _rows_out(scored_cfg, month)
    assert report(scored_cfg) is True


def test_a_partly_scored_month_is_RED_not_pending(scored_cfg):
    """The failure this check exists for: a plausible number over a subset.

    Half a month's predictions produce a perfectly ordinary MAE. Nothing about
    the value looks wrong — it is simply an average over rows nobody chose.
    """
    month = "2020-01"
    _publish(scored_cfg, month, rows=3)
    build(scored_cfg)
    rows = {r[0]: r for r in scoring_prediction_reconciliation(scored_cfg)}
    assert rows[month][1] == 3
    assert rows[month][3] is False
    assert report(scored_cfg) is False


def test_an_unscored_month_is_pending_and_still_GREEN(scored_cfg):
    """Ingested-but-not-yet-scored is a normal state; a guard that fails on a
    correct system is how a guard becomes a formality (gotcha #50)."""
    scored_cfg.scoring_predictions_path("2020-02").unlink()
    build(scored_cfg)
    rows = {r[0]: r for r in scoring_prediction_reconciliation(scored_cfg)}
    assert rows["2020-02"][1] == 0 and rows["2020-02"][3] is False
    assert report(scored_cfg) is True


def test_a_mislabelled_month_is_caught_by_the_full_outer_join(scored_cfg):
    """A file whose `month` column says something the ingest never wrote."""
    path = scored_cfg.scoring_predictions_path("2020-01")
    frame = pq.read_table(path).to_pandas()
    frame["month"] = "2020-09"
    predictions_mod.write(
        frame,
        path,
        scored_cfg,
        columns=predictions_mod.SCORING_PREDICTION_COLUMNS,
    )
    build(scored_cfg)
    rows = {r[0]: r for r in scoring_prediction_reconciliation(scored_cfg)}
    assert "2020-09" in rows, "a month only the predictions know about must surface"
    assert rows["2020-09"][2] == 0 and rows["2020-09"][3] is False
    assert rows["2020-01"][1] == 0
    assert report(scored_cfg) is False


def test_the_view_derives_error_in_sql_and_carries_no_floor(scored_cfg):
    from taxi_mlops.data.analyst import connect

    build(scored_cfg)
    con = connect(scored_cfg, read_only=True)
    try:
        columns = [r[0] for r in con.execute("DESCRIBE scoring_predictions").fetchall()]
        bad = con.execute(
            "SELECT COUNT(*) FROM scoring_predictions "
            "WHERE abs_error_minutes <> ABS(predicted_minutes - actual_minutes)"
        ).fetchone()[0]
    finally:
        con.close()
    assert "abs_error_minutes" in columns and "signed_error_minutes" in columns
    assert not any("floor" in c for c in columns)
    assert bad == 0


# ---- the refusals, asserted structurally ------------------------------------


def _batch_tree() -> ast.AST:
    return ast.parse(BATCH_SOURCE.read_text())


def test_the_batch_path_cannot_mutate_the_registry():
    """AST, never grep: this module argues its own design in prose (#53/#68)."""
    forbidden = {
        "set_registered_model_alias",
        "delete_registered_model_alias",
        "create_model_version",
        "register_model",
        "create_registered_model",
        "delete_model_version",
        "transition_model_version_stage",
        "set_model_version_tag",
        "log_model",
        "start_run",
    }
    called = {
        node.func.attr
        for node in ast.walk(_batch_tree())
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not (called & forbidden), f"batch.py calls {sorted(called & forbidden)}"


def test_the_self_check_runs_before_any_write():
    """The property, not the prose: `_self_check` is called before the loop that
    builds frames, and the write happens after both."""
    tree = _batch_tree()
    fn = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "score_scoring_months"
    )
    order: list[str] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name in {"_self_check", "write"}:
                order.append((node.lineno, name))
    order.sort()
    names = [n for _, n in order]
    assert names, "neither the self-check nor the write was found"
    assert names[0] == "_self_check", f"the first of {names} must be the self-check"


def test_the_manifest_spells_the_monitoring_ids_and_disowns_the_gate_ids():
    payload = batch.manifest(
        model={"name": "nyc-taxi-eta", "version": "2"},
        self_check={"split": "test", "registry_kpi_09": "3.2403"},
        tolerance_minutes=5.0,
        results=[
            batch.MonthResult(
                month="2020-03",
                rows=10,
                metrics=_metrics(),
                mean_actual=12.0,
                mean_predicted=13.0,
                mean_signed_error=1.0,
                days=31,
            )
        ],
    )
    keys = set(payload["months"][0])
    assert {"kpi_14_mae_minutes", "kpi_15_within_tolerance_pct",
            "kpi_16_mean_signed_error_minutes", "kpi_17_scored_trips"} <= keys
    assert not any(k.startswith(("kpi_09", "kpi_10")) for k in keys)
    # The self-check's registry number is KPI-09 and is labelled as such — it is
    # the ONE gate number in this file, and it is about the holdout, not 2020.
    assert payload["self_check"]["registry_kpi_09"] == "3.2403"
    assert "KPI-09/KPI-10" in payload["note"]
    assert payload["metric_source"] == "taxi_mlops.training.evaluate"
    # Timestamp-free, like every other manifest this program writes.
    assert "timestamp" not in json.dumps(payload).lower()


def _metrics():
    from taxi_mlops.training.evaluate import Metrics

    return Metrics(
        contender="nyc-taxi-eta@champion",
        split="scoring:2020-03",
        n=10,
        mae=4.0,
        within_tolerance_rate=70.0,
        tolerance_minutes=5.0,
        rmse=6.0,
        median_ae=3.0,
        p90_ae=9.0,
    )


# ---- the ids stay apart -----------------------------------------------------


def test_the_monitoring_mart_names_no_gate_kpi():
    """A board reading `scoring_daily` must not be able to render KPI-09/10."""
    sql = (REPO_ROOT / "analytics/dbt/models/marts/scoring_daily.sql").read_text()
    body = "\n".join(
        line for line in sql.splitlines() if not line.strip().startswith("--")
    )
    assert "kpi_09" not in body.lower() and "kpi_10" not in body.lower()
    for column in ("kpi_14_mae_min", "kpi_15_within_tol_pct",
                   "kpi_16_mean_signed_error_min", "kpi_17_scored_trips"):
        assert column in body


def test_every_new_id_is_defined_before_it_is_published():
    """The id law's teeth: a mart column whose id has no definition is a number
    with no formula, window or owner."""
    definitions = (REPO_ROOT / "docs/kpi_definitions.md").read_text()
    for kpi in ("KPI-14", "KPI-15", "KPI-16", "KPI-17"):
        assert f"### {kpi} —" in definitions, f"{kpi} has no definition"
    for column in ("kpi_14_mae_min", "kpi_15_within_tol_pct",
                   "kpi_16_mean_signed_error_min", "kpi_17_scored_trips"):
        assert column in definitions, f"{column} is published but not documented"
    # And the window is stated as what it is, not as a split.
    assert "MONITORING" in definitions


def test_the_mart_is_published_and_the_publish_list_is_the_only_list():
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import marts_publish  # scripts/ is not a package; the path insert is the import

    assert "scoring_daily" in marts_publish.MARTS
    marts_sh = (REPO_ROOT / "scripts" / "marts.sh").read_text()
    assert "scoring_daily" not in marts_sh, "a second mart list is twins (M4-S5)"
