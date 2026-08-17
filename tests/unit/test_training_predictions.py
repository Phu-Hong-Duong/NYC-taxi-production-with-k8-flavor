"""The published predictions artifact — its schema, its refusals, its provenance.

M2-S4 turns a claim ("KPI-09 is 3.2608") into evidence (the 5,950,708 rows it was
averaged over). That is only worth anything if the file is trustworthy, so what
is tested here is what would make it silently untrustworthy:

* a column dropped from the contract other code cites by name;
* a frame written for a feature set whose shape has moved;
* a manifest carrying a timestamp, which would make every re-run look like a
  change and train everyone to ignore the diff;
* a champion whose re-scored number disagrees with the tag the gate wrote on it —
  the one failure that says the published rows describe a different model.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from taxi_mlops.training import predictions as predictions_mod
from taxi_mlops.training.evaluate import Metrics
from taxi_mlops.training.score import Champion, ChampionError, _check_against_registry


def features(rows: int = 6) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "hour": np.arange(rows, dtype="int16") % 24,
            "dayofweek": np.arange(rows, dtype="int16") % 7,
            "PULocationID": np.full(rows, 132, dtype="int16"),
            "DOLocationID": np.full(rows, 230, dtype="int16"),
            "passenger_count": np.full(rows, 1.0, dtype="float32"),
        }
    )


def frame(rows: int = 6) -> pd.DataFrame:
    matrix = features(rows)
    return predictions_mod.build_frame(
        split="test",
        month="2019-08",
        features=matrix,
        actual=pd.Series(np.linspace(5.0, 40.0, rows)),
        predicted=np.linspace(6.0, 35.0, rows),
        floor_predicted=np.full(rows, 11.15),
        floor_unseen=np.array([False] * (rows - 1) + [True]),
        model_name="nyc-taxi-eta",
        model_version="1",
    )


def test_the_frame_is_exactly_the_published_contract_in_order():
    """PREDICTION_COLUMNS is cited by name by the analyst view and the mart.

    Prevents: a column quietly added or reordered here and a `SELECT *` two
    layers away meaning something different from what its header says.
    """
    assert list(frame().columns) == list(predictions_mod.PREDICTION_COLUMNS)


def test_the_error_columns_are_deliberately_absent():
    """`abs_error_minutes` is derived in SQL, in one place, from the two columns
    that define it.

    Prevents the twins failure at its most tempting: a stored error column and a
    computed one, agreeing until someone changes the clip or the units.
    """
    for derived in predictions_mod.DERIVED_IN_SQL:
        assert derived not in predictions_mod.PREDICTION_COLUMNS


def test_split_and_month_are_literals_not_parsed_from_anything():
    published = frame()
    assert set(published["split"]) == {"test"}
    assert set(published["month"]) == {"2019-08"}


def test_a_feature_set_that_has_moved_is_refused_rather_than_written():
    """Prevents: feature set v2 arriving and this writer silently publishing rows
    whose header promises v1's five columns."""
    matrix = features().drop(columns=["passenger_count"])
    with pytest.raises(ValueError, match="passenger_count"):
        predictions_mod.build_frame(
            split="val",
            month="2019-07",
            features=matrix,
            actual=pd.Series(np.ones(6)),
            predicted=np.ones(6),
            floor_predicted=np.ones(6),
            floor_unseen=np.zeros(6, dtype=bool),
            model_name="nyc-taxi-eta",
            model_version="1",
        )


def test_write_round_trips_through_the_data_paths_writer_pins(data_cfg, tmp_path):
    """The predictions use configs/data.yaml's writer, not a second one.

    Prevents: two parquet writer configurations in one repo, which is how a
    byte-identity proof starts applying to only half the files it names.
    """
    path = tmp_path / "predictions_2019-08.parquet"
    predictions_mod.write(frame(), path, data_cfg)
    read_back = pd.read_parquet(path)
    assert list(read_back.columns) == list(predictions_mod.PREDICTION_COLUMNS)
    assert len(read_back) == 6
    assert read_back["floor_unseen_group"].sum() == 1


def test_write_refuses_a_frame_missing_a_published_column(data_cfg, tmp_path):
    with pytest.raises(ValueError, match="predicted_minutes"):
        predictions_mod.write(
            frame().drop(columns=["predicted_minutes"]), tmp_path / "x.parquet", data_cfg
        )


def _metrics(mae: float) -> Metrics:
    return Metrics(
        contender="nyc-taxi-eta@champion",
        split="test",
        n=10,
        mae=mae,
        within_tolerance_rate=81.0,
        tolerance_minutes=5.0,
        rmse=5.0,
        median_ae=2.0,
        p90_ae=7.0,
    )


def test_the_manifest_carries_no_timestamp(tmp_path):
    """Timestamp-free by design, like data/raw_manifest.json.

    Prevents: every re-run producing a diff, which teaches whoever reads these
    files that a diff means nothing — on the one file whose diff should mean the
    model moved.
    """
    payload = predictions_mod.manifest(
        model={"name": "nyc-taxi-eta", "version": "1"},
        floor={"name": "baseline-group-median"},
        tolerance_minutes=5.0,
        metrics=[_metrics(3.2608)],
    )
    path = predictions_mod.write_manifest(payload, tmp_path / "predictions.json")
    text = path.read_text()
    assert "2026-" not in text and "generated_at" not in text
    again = predictions_mod.write_manifest(payload, tmp_path / "again.json")
    assert again.read_text() == text
    assert json.loads(text)["metric_source"] == "taxi_mlops.training.evaluate"


def champion(tag_mae: str | None) -> Champion:
    return Champion(
        model_name="nyc-taxi-eta",
        alias="champion",
        version="1",
        run_id="deadbeef",
        uri="models:/nyc-taxi-eta@champion",
        target_transform="none",
        feature_names=list(features().columns),
        trees=500,
        tags={} if tag_mae is None else {"gate_challenger_mae": tag_mae},
        booster=None,
    )


def test_a_champion_that_rescores_differently_is_refused(capsys):
    """The strongest check in the scoring path, and the only symptom this defect
    has: the version that loads is not the version the gate promoted, or this
    path builds features differently from the one that fitted it."""
    with pytest.raises(ChampionError, match="3.2608"):
        _check_against_registry(champion("3.2608"), [_metrics(4.0)], "test")


def test_a_champion_that_reproduces_its_own_tag_passes(capsys):
    _check_against_registry(champion("3.2608"), [_metrics(3.260828)], "test")
    assert "MATCH" in capsys.readouterr().out


def test_an_untagged_champion_says_so_rather_than_pretending_to_check(capsys):
    """A version promoted before the gate wrote tags cannot be checked. Saying
    nothing would look identical to checking and passing."""
    _check_against_registry(champion(None), [_metrics(3.2608)], "test")
    assert "nothing to check" in capsys.readouterr().out
