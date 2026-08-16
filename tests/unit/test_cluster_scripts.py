"""M0-S2: the two dangerous bits of the cluster recipe, tested cluster-free.

Why these two and nothing else: the port pre-check is the thing that must REFUSE
(a check that never says no is decoration), and `destroy` is the only target that
deletes. Everything else in scripts/cluster.sh needs a real kind cluster and is
verified by running it (M0-S2 / M0-S4 accept-when), not here.

`destroy` is exercised against a sandbox COPY of the script whose kind config
names a cluster that does not exist — so the test can never delete the real one.
"""

import shutil
import socket
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PRECHECK = REPO / "scripts" / "port_precheck.sh"
CLUSTER_SH = REPO / "scripts" / "cluster.sh"
NEEDS_SS = pytest.mark.skipif(shutil.which("ss") is None, reason="iproute2 'ss' not installed")


def run(*args, cwd=None, env=None):
    return subprocess.run(
        ["bash", *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=120
    )


@NEEDS_SS
def test_port_precheck_refuses_a_busy_port_and_names_it():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        port = sock.getsockname()[1]
        proc = run(str(PRECHECK), str(port))
        assert proc.returncode == 2, proc.stdout + proc.stderr
        assert str(port) in proc.stderr
        assert "REFUSING" in proc.stderr


@NEEDS_SS
def test_port_precheck_passes_once_the_port_is_free():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    proc = run(str(PRECHECK), str(port))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "OK" in proc.stdout


def _sandbox(tmp_path: Path, regenerable: str | None = None) -> Path:
    """Copy the recipe into tmp_path, pointed at a cluster name that cannot exist."""
    (tmp_path / "scripts").mkdir()
    shutil.copy(PRECHECK, tmp_path / "scripts" / "port_precheck.sh")
    text = CLUSTER_SH.read_text()
    if regenerable is not None:
        start = text.index("REGENERABLE=(")
        end = text.index(")", start) + 1
        text = text[:start] + f"REGENERABLE=({regenerable})" + text[end:]
    (tmp_path / "scripts" / "cluster.sh").write_text(text)
    (tmp_path / "infra" / "kind").mkdir(parents=True)
    (tmp_path / "infra" / "kind" / "kind-config.yaml").write_text(
        "kind: Cluster\nname: sandbox-cluster-that-does-not-exist\n"
        "nodes:\n  - role: control-plane\n"
    )
    return tmp_path / "scripts" / "cluster.sh"


def test_destroy_deletes_regenerable_state_and_spares_raw_data_and_env(tmp_path):
    script = _sandbox(tmp_path)
    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "yellow_2019-09.parquet").write_text("the original download")
    (tmp_path / "data" / "processed").mkdir(parents=True)
    (tmp_path / "data" / "processed" / "train.parquet").write_text("regenerable")
    (tmp_path / ".env").write_text("SECRET=hunter2")
    (tmp_path / ".dvc" / "cache").mkdir(parents=True)
    (tmp_path / ".dvc" / "cache" / "blob").write_text("possibly the only copy")

    proc = run(str(script), "destroy")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not (tmp_path / "data" / "processed").exists()
    assert (tmp_path / "data" / "raw" / "yellow_2019-09.parquet").read_text() == (
        "the original download"
    )
    assert (tmp_path / ".env").read_text() == "SECRET=hunter2"
    assert (tmp_path / ".dvc" / "cache" / "blob").exists()


def test_destroy_dry_run_deletes_nothing(tmp_path):
    script = _sandbox(tmp_path)
    (tmp_path / "data" / "processed").mkdir(parents=True)
    (tmp_path / "data" / "processed" / "train.parquet").write_text("regenerable")

    proc = run(str(script), "destroy", env={"PATH": "/usr/bin:/bin", "DRY_RUN": "1"})

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "WOULD remove data/processed" in proc.stdout
    assert (tmp_path / "data" / "processed" / "train.parquet").exists()


@pytest.mark.parametrize(
    "bad_path",
    ["data/raw", ".env", "data/raw/../raw/subdir", "../outside-the-repo"],
)
def test_destroy_guard_refuses_protected_and_escaping_paths(tmp_path, bad_path):
    """The guard, not the allowlist, is what stands between a typo and data loss."""
    script = _sandbox(tmp_path, regenerable=f'"{bad_path}"')
    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "keep.parquet").write_text("the original download")

    proc = run(str(script), "destroy")

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "REFUSING" in proc.stderr
    assert (tmp_path / "data" / "raw" / "keep.parquet").exists()
