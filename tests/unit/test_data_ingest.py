"""Ingest refusals and the manifest pin — cluster-free and network-free.

The refusal tests assert TWO things every time: the typed error naming the file,
AND that nothing was written. A refusal that leaves a half month on disk is not
a refusal, it is a corruption with an error message.
"""

from __future__ import annotations

import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from conftest import raw_frame

from taxi_mlops.data import __main__ as cli
from taxi_mlops.data.download import ensure_month, load_manifest, save_manifest, sha256_file
from taxi_mlops.data.errors import (
    ChecksumDriftError,
    CorruptSourceError,
    RejectionThresholdError,
)
from taxi_mlops.data.ingest import ingest, read_raw

MONTH = "2019-01"


def seed_raw(cfg, month: str = MONTH, rows: int = 40) -> None:
    path = cfg.raw_path(month)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(raw_frame(month, rows), preserve_index=False), path)


def test_ingest_writes_output_and_rejection_report(data_cfg):
    seed_raw(data_cfg)
    [report] = ingest([MONTH], data_cfg)
    out = data_cfg.processed_path(MONTH)
    assert out.exists() and out.parent.name == "train"  # split visible on disk
    written = json.loads(data_cfg.rejections_path(MONTH).read_text())
    assert written["rows_in"] == report.rows_in == 40
    assert [r["name"] for r in written["rules"]] == [
        r["name"] for r in data_cfg.clean["rules"]
    ]


def test_ingest_writes_the_rejected_sidecar_beside_the_counts(data_cfg):
    """M2-S1 (F-005): the dropped rows land on disk, under their split, with the
    rule that dropped them — and their count matches the report's, file to file."""
    seed_raw(data_cfg, rows=40)
    df = raw_frame(MONTH, rows=40)
    df.loc[0, "trip_distance"] = 0.0
    df.loc[1, "fare_amount"] = -5.0
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), data_cfg.raw_path(MONTH))

    [report] = ingest([MONTH], data_cfg)
    sidecar = data_cfg.rejected_path(MONTH)
    assert sidecar.exists() and sidecar.parent.name == "train"  # split visible on disk
    assert sidecar.parent.parent != data_cfg.processed_path(MONTH).parent.parent

    rows = pq.read_table(sidecar).to_pandas()
    assert len(rows) == report.rows_rejected == 2
    counted = {r["name"]: r["rejected_by"] for r in report.rules if r["rejected_by"]}
    assert rows["rejection_rule"].value_counts().to_dict() == counted


def test_corrupt_parquet_is_refused_and_nothing_is_written(data_cfg):
    """The red-team in unit form: garbage bytes must never become a processed month."""
    path = data_cfg.raw_path(MONTH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"PAR1this is not a parquet file at all")
    with pytest.raises(CorruptSourceError, match=path.name):
        ingest([MONTH], data_cfg)
    assert not data_cfg.processed_path(MONTH).exists()
    assert not data_cfg.rejections_path(MONTH).exists()
    assert not data_cfg.rejected_path(MONTH).exists()


def test_a_month_over_the_ceiling_leaves_no_sidecar_either(data_cfg):
    """A refused month leaves NOTHING behind, and 'nothing' now has one more
    file in it. A sidecar written for a month whose output was refused would be
    rejects belonging to a month that does not exist downstream."""
    df = raw_frame(MONTH, rows=10)
    df.loc[0:1, "trip_distance"] = 0.0  # 20% > the shipped 10% ceiling
    path = data_cfg.raw_path(MONTH)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), path)
    with pytest.raises(RejectionThresholdError, match="broken input"):
        ingest([MONTH], data_cfg)
    assert not data_cfg.processed_path(MONTH).exists()
    assert not data_cfg.rejected_path(MONTH).exists()


def test_truncated_parquet_is_refused(data_cfg):
    seed_raw(data_cfg)
    path = data_cfg.raw_path(MONTH)
    path.write_bytes(path.read_bytes()[: len(path.read_bytes()) // 2])
    with pytest.raises(CorruptSourceError, match=path.name):
        read_raw(path)


def test_cli_exits_nonzero_on_a_refusal(data_cfg, tmp_path, monkeypatch):
    """The exit code is part of the contract — `make ingest` must fail, not warn."""
    data_cfg.raw_path(MONTH).parent.mkdir(parents=True, exist_ok=True)
    data_cfg.raw_path(MONTH).write_bytes(b"not parquet")
    monkeypatch.setattr(cli, "load_config", lambda *a, **k: data_cfg)
    assert cli.main(["ingest", "--month", MONTH]) == 1
    assert not data_cfg.processed_path(MONTH).exists()


def test_cli_exits_zero_on_success(data_cfg, monkeypatch):
    seed_raw(data_cfg)
    monkeypatch.setattr(cli, "load_config", lambda *a, **k: data_cfg)
    assert cli.main(["ingest", "--month", MONTH]) == 0


def test_checksum_drift_is_an_event_not_a_refresh(data_cfg):
    """Gotcha #6: TLC backfills in place. Ingest must not silently adopt new bytes."""
    seed_raw(data_cfg)
    manifest: dict = {}
    assert ensure_month(data_cfg, MONTH, manifest) == "present"
    seed_raw(data_cfg, rows=41)  # same month, different bytes
    with pytest.raises(ChecksumDriftError, match="sha256"):
        ensure_month(data_cfg, MONTH, manifest)


def test_present_file_is_not_re_downloaded(data_cfg):
    """skip-if-present, proven by an unreachable URL: touching the network would fail."""
    seed_raw(data_cfg)
    cfg = data_cfg
    cfg.source["url_pattern"] = "http://127.0.0.1:1/{month}.parquet"
    assert ensure_month(cfg, MONTH, {}) == "present"


def test_manifest_is_deterministic_and_timestamp_free(data_cfg, tmp_path):
    """A manifest diff must always mean the DATA moved (S2 builds its proof on this)."""
    seed_raw(data_cfg)
    path = tmp_path / "m.json"
    entry = {MONTH: {"file": "x.parquet", "url": "u", "bytes": 1, "sha256": "abc"}}
    save_manifest(path, entry)
    first = path.read_bytes()
    save_manifest(path, entry)
    assert path.read_bytes() == first
    assert load_manifest(path) == entry
    assert "time" not in json.loads(first)


def test_sha256_matches_a_known_digest(data_cfg, tmp_path):
    import hashlib

    blob = tmp_path / "blob.bin"
    blob.write_bytes(b"crosstown")
    assert sha256_file(blob) == hashlib.sha256(b"crosstown").hexdigest()
