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


def _precheck_with_fake_docker(tmp_path: Path, container: str, port: int) -> tuple[Path, dict]:
    """A copy of the pre-check whose `docker ps` reports ONE container publishing `port`.

    F-021: the pre-check must distinguish our own kind node containers from a
    foreign stack. Both states are exercised by changing only the container NAME,
    which is exactly the signal the script keys on — so a fix that stopped
    reading the name would fail one of the two tests.
    """
    (tmp_path / "scripts").mkdir(exist_ok=True)
    script = tmp_path / "scripts" / "port_precheck.sh"
    shutil.copy(PRECHECK, script)
    (tmp_path / "infra" / "kind").mkdir(parents=True, exist_ok=True)
    (tmp_path / "infra" / "kind" / "kind-config.yaml").write_text(
        "kind: Cluster\nname: mlops-taxi\nnodes:\n  - role: control-plane\n"
    )
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    fake_docker = bindir / "docker"
    fake_docker.write_text(
        "#!/usr/bin/env bash\n"
        f'printf "%s\\t%s\\n" "{container}" "0.0.0.0:{port}->80/tcp"\n'
        "exit 0\n"
    )
    fake_docker.chmod(0o755)
    return script, {"PATH": f"{bindir}:/usr/sbin:/usr/bin:/sbin:/bin"}


@NEEDS_SS
def test_port_precheck_says_held_by_us_when_our_own_cluster_holds_it(tmp_path):
    """F-021: our own kind node publishing a family port is EXPECTED, not a refusal.

    Before this, `make ports` went red against the live platform and told the
    reader to "stop that stack" — advice that deletes the PVCs holding the only
    copy of the registry, both Optuna studies and the Metabase app-db.
    """
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        port = sock.getsockname()[1]
        script, env = _precheck_with_fake_docker(tmp_path, "mlops-taxi-control-plane", port)
        proc = run(str(script), str(port), env=env)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "held by US" in proc.stdout
    assert "mlops-taxi-control-plane" in proc.stdout
    assert "REFUSING" not in proc.stderr


@NEEDS_SS
def test_port_precheck_still_refuses_a_genuinely_foreign_holder(tmp_path):
    """The gotcha #10 refusal survives the F-021 fix — same port, different owner."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        port = sock.getsockname()[1]
        script, env = _precheck_with_fake_docker(tmp_path, "somebody-elses-stack-web-1", port)
        proc = run(str(script), str(port), env=env)

    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "REFUSING" in proc.stderr
    assert str(port) in proc.stderr
    assert "held by US" not in proc.stdout


def _sandbox(tmp_path: Path, regenerable: str | None = None) -> Path:
    """Copy the recipe into tmp_path, pointed at a cluster name that cannot exist."""
    (tmp_path / "scripts").mkdir()
    shutil.copy(PRECHECK, tmp_path / "scripts" / "port_precheck.sh")
    text = CLUSTER_SH.read_text()
    if regenerable is not None:
        # Split on the array's closing paren AT THE START OF A LINE, not on the
        # first ')' after the opener: the entries carry prose comments with
        # parens of their own, and the naive version silently truncated the
        # array mid-way, producing a script whose remaining entries ran as
        # COMMANDS (observed M2-S1 — every guard test failed with rc 127).
        # test_the_catalogue_is_destroyable_and_the_dvc_cache_is_not already
        # knew this; the helper did not.
        start = text.index("REGENERABLE=(")
        end = text.index("\n)", start) + 2
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


def _sandbox_with_live_cluster(tmp_path: Path) -> tuple[Path, Path, dict]:
    """Sandbox whose fake `kind` reports the cluster as EXISTING and logs every call.

    The tests above point at a cluster name that cannot exist, which is what makes
    them safe — and is exactly why they could not see gotcha #30: `cmd_down` always
    no-opped, so a dry run that deleted a REAL cluster looked identical to one that
    did not. This shim restores the missing half without going near a real cluster.
    """
    script = _sandbox(tmp_path)
    calls = tmp_path / "kind-calls.log"
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake_kind = bindir / "kind"
    fake_kind.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "$@" >> "{calls}"\n'
        'if [[ "$1 $2" == "get clusters" ]]; then\n'
        "  echo sandbox-cluster-that-does-not-exist\n"
        "fi\n"
        "exit 0\n"
    )
    fake_kind.chmod(0o755)
    env = {"PATH": f"{bindir}:/usr/bin:/bin"}
    return script, calls, env


def test_destroy_dry_run_spares_the_cluster_itself(tmp_path):
    """gotcha #30: DRY_RUN must cover the most expensive deletion, not just files."""
    script, calls, env = _sandbox_with_live_cluster(tmp_path)

    proc = run(str(script), "destroy", env={**env, "DRY_RUN": "1"})

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "WOULD delete kind cluster" in proc.stdout
    assert "delete cluster" not in calls.read_text()


def test_destroy_without_dry_run_does_delete_the_cluster(tmp_path):
    """Positive control: without it, the test above passes on a broken shim."""
    script, calls, env = _sandbox_with_live_cluster(tmp_path)

    proc = run(str(script), "destroy", env=env)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "delete cluster --name sandbox-cluster-that-does-not-exist" in calls.read_text()


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
