"""The plumbing that surrounds the model: what gets read, and how the client is wired.

Two failures live here and neither announces itself. A narrow read that quietly
widens puts a post-trip column back inside the process (F-007's shape). A client
missing its S3 endpoint creates a run that looks perfect and whose artifacts 404
later, usually at the moment something tries to serve the model (gotcha #5).
"""

from __future__ import annotations

import sys
import types

import pytest

from taxi_mlops.data.config import load_yaml
from taxi_mlops.features.quote_time import EXCLUDED_COLUMNS
from taxi_mlops.training import openmp, tracking
from taxi_mlops.training.datasets import required_columns

TRAIN_CFG = load_yaml("configs/train.yaml")


# ------------------------------------------------------------------ what is read ---
def test_the_read_is_narrow_and_the_narrowness_is_the_exclusion_registry():
    """A column that never enters the process cannot leak into a matrix by accident."""
    columns = required_columns(TRAIN_CFG["features"], TRAIN_CFG["target"])
    leaked = set(columns) & EXCLUDED_COLUMNS - {TRAIN_CFG["target"]}
    assert not leaked, f"the training read pulls refused column(s) off disk: {leaked}"


def test_the_read_covers_exactly_what_v1_needs():
    columns = required_columns(TRAIN_CFG["features"], TRAIN_CFG["target"])
    assert columns == [
        "tpep_pickup_datetime",
        "PULocationID",
        "DOLocationID",
        "passenger_count",
        "trip_duration_minutes",
    ]


# ------------------------------------------------------------------- the openmp shim ---
def test_the_relaunch_rebuilds_a_dash_m_invocation(monkeypatch):
    """sys.argv does not round-trip `python -m package`: argv[0] is __main__.py, and
    replaying it dies on 'attempted relative import with no known parent package'.
    Observed once (M2-S2) before this existed."""
    spec = types.SimpleNamespace(name="taxi_mlops.training.__main__")
    fake = types.SimpleNamespace(__spec__=spec)
    monkeypatch.setitem(sys.modules, "__main__", fake)
    monkeypatch.setattr(sys, "argv", ["/x/taxi_mlops/training/__main__.py", "train", "--ablation"])
    assert openmp._relaunch_argv() == ["-m", "taxi_mlops.training", "train", "--ablation"]


def test_a_plain_script_invocation_is_replayed_verbatim(monkeypatch):
    fake = types.SimpleNamespace(__spec__=None)
    monkeypatch.setitem(sys.modules, "__main__", fake)
    monkeypatch.setattr(sys, "argv", ["scripts/thing.py", "--flag"])
    assert openmp._relaunch_argv() == ["scripts/thing.py", "--flag"]


def test_the_status_probe_never_re_execs_and_always_explains_itself():
    loadable, how = openmp.openmp_status()
    assert isinstance(loadable, bool)
    assert how.strip()


def test_a_caller_that_forbids_re_exec_gets_a_refusal_not_a_fork(monkeypatch):
    monkeypatch.setattr(openmp, "_load", lambda: False)
    monkeypatch.setattr(openmp, "_vendored", lambda: openmp.Path("/somewhere/libgomp.so.1.0.0"))
    with pytest.raises(openmp.OpenMPUnavailableError, match="re-exec"):
        openmp.ensure_openmp(allow_reexec=False)


def test_no_openmp_anywhere_names_the_real_fix_rather_than_the_workaround(monkeypatch):
    monkeypatch.setattr(openmp, "_load", lambda: False)
    monkeypatch.setattr(openmp, "_vendored", lambda: None)
    with pytest.raises(openmp.OpenMPUnavailableError, match="libgomp1"):
        openmp.ensure_openmp()


# -------------------------------------------------------------------- the client ---
def test_the_client_is_pointed_at_minio_as_well_as_the_tracking_server(tmp_path, monkeypatch):
    """gotcha #5: the run appears either way; only the artifacts know the difference."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AWS_ACCESS_KEY_ID=k\nAWS_SECRET_ACCESS_KEY=s\nAWS_DEFAULT_REGION=us-east-1\n"
    )
    # delenv through monkeypatch for every key `configure` writes, so the fixture
    # restores them: a test that leaves AWS_* set has changed the environment of
    # every test after it, and that kind of green is worse than red.
    for key in ("MLFLOW_TRACKING_URI", "MLFLOW_S3_ENDPOINT_URL", *tracking._S3_KEYS):
        monkeypatch.delenv(key, raising=False)
    tracking.configure(TRAIN_CFG["mlflow"], env_file=env_file)
    import os

    assert os.environ["MLFLOW_S3_ENDPOINT_URL"] == TRAIN_CFG["mlflow"]["s3_endpoint_url"]
    assert os.environ["MLFLOW_TRACKING_URI"] == TRAIN_CFG["mlflow"]["tracking_uri"]


def test_an_exported_variable_beats_the_checked_in_default(tmp_path, monkeypatch):
    """M4's in-cluster caller exports cluster DNS names and needs no code change."""
    env_file = tmp_path / ".env"
    env_file.write_text("AWS_ACCESS_KEY_ID=k\nAWS_SECRET_ACCESS_KEY=s\nAWS_DEFAULT_REGION=r\n")
    for key in tracking._S3_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow.mlflow.svc.cluster.local:5000")
    monkeypatch.setenv("MLFLOW_S3_ENDPOINT_URL", "http://minio.platform.svc.cluster.local:9000")
    uri = tracking.configure(TRAIN_CFG["mlflow"], env_file=env_file)
    assert uri.endswith("cluster.local:5000")


def test_missing_credentials_are_refused_by_NAME_and_the_value_never_appears(
    tmp_path, monkeypatch, capsys
):
    env_file = tmp_path / ".env"
    env_file.write_text("AWS_ACCESS_KEY_ID=visible-secret\n")
    for key in ("AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(tracking.TrackingConfigError) as excinfo:
        tracking.configure(TRAIN_CFG["mlflow"], env_file=env_file)
    message = str(excinfo.value)
    assert "AWS_SECRET_ACCESS_KEY" in message
    assert "visible-secret" not in message
    assert "visible-secret" not in capsys.readouterr().out


def test_an_absent_env_file_points_at_the_script_that_owns_it(tmp_path):
    with pytest.raises(tracking.TrackingConfigError, match="platform_secrets"):
        tracking.configure(TRAIN_CFG["mlflow"], env_file=tmp_path / "nope")


# ------------------------------------------------------------- the story boundary ---
def test_this_story_registers_nothing():
    """M2-S3 owns promotion. A `champion` alias set here would be a gate nobody wrote."""
    import pathlib

    source = "\n".join(
        p.read_text() for p in pathlib.Path("src/taxi_mlops/training").glob("*.py")
    )
    # The API SURFACE, not the word: this package's docstrings say "champion" a
    # lot, precisely to record that S3 owns it. A test that banned the word would
    # be punishing the documentation for describing the boundary it keeps.
    for forbidden in (
        "register_model(",
        "registered_model_name",
        "set_registered_model_alias",
        "MlflowClient().set_",
    ):
        assert forbidden not in source, f"M2-S2 must not touch the registry: found {forbidden!r}"
