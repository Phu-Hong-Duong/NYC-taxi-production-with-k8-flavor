"""M0-S3: the platform recipe's cluster-free parts, red-teamed.

Three things are testable without a cluster, and all three are things that must
say NO:

* ``check_charters.sh`` — the M0 gate's "every charter carries at least three
  refusals". A counter that has never counted a failure is decoration.
* ``platform_secrets.sh`` — it invents credentials and refuses drift. Anything
  that touches secrets gets tested against a throwaway .env, never the real one.
* the port twins — a NodePort in a manifest and a ``containerPort`` in the kind
  config are the same number written in two files. Nothing at runtime complains
  when they drift; the URL just stops answering.

The live half (deploy, health, buckets) is proved by running ``make verify-m0``
against a real cluster — see the M0-S3 handoff entry, not here.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CHARTERS = REPO / "scripts" / "check_charters.sh"
SECRETS = REPO / "scripts" / "platform_secrets.sh"
KIND_CONFIG = REPO / "infra" / "kind" / "kind-config.yaml"
MLFLOW_NODEPORT = REPO / "infra" / "manifests" / "mlflow-nodeport.yaml"
METABASE_MANIFEST = REPO / "infra" / "manifests" / "metabase.yaml"
MINIO_VALUES = REPO / "infra" / "helm" / "minio" / "values.yaml"

NEEDS_OPENSSL = pytest.mark.skipif(
    shutil.which("openssl") is None, reason="openssl not installed"
)


def run(script: Path, *args, env=None):
    return subprocess.run(
        ["bash", str(script), *args],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


# --------------------------------------------------------------- charters ----

CHARTER = """# Role charters

## AA — Alpha
Mission: something.
Produces: something else.
REFUSES: one thing; two things; three things.
Tensions: with everyone.

## BB — Beta
Mission: something.
REFUSES: only this; and that.
Tensions: none.
"""


def test_charters_passes_the_real_roles_file():
    """The constitution as committed must satisfy the gate it declares."""
    proc = run(CHARTERS)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "all 8 charters" in proc.stdout


def test_charters_refuses_a_charter_with_too_few_refusals(tmp_path):
    roles = tmp_path / "ROLES.md"
    roles.write_text(CHARTER)

    proc = run(CHARTERS, str(roles))

    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "BB" in proc.stderr and "2 refusals" in proc.stderr
    assert "ok   AA" in proc.stdout  # the passing charter still reports


def test_charters_counts_a_refusal_block_that_wraps_across_lines(tmp_path):
    """Real charters wrap; a line-based counter would score this 1 and pass it."""
    roles = tmp_path / "ROLES.md"
    roles.write_text(
        "## CC — Gamma\n"
        "REFUSES: first item that runs\nlong; second item;\nthird item.\n"
        "Tensions: x.\n"
    )

    proc = run(CHARTERS, str(roles))

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "3 refusals" in proc.stdout


def test_charters_refuses_a_file_it_cannot_parse(tmp_path):
    """Silence is the dangerous answer: no headings must fail, not pass vacuously."""
    roles = tmp_path / "ROLES.md"
    roles.write_text("no headings here, just prose about refusing things\n")

    proc = run(CHARTERS, str(roles))

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "could not parse" in proc.stderr


def test_charters_refuses_a_missing_file(tmp_path):
    proc = run(CHARTERS, str(tmp_path / "nope.md"))
    assert proc.returncode == 1
    assert "no such file" in proc.stderr


# ---------------------------------------------------------------- secrets ----

REQUIRED_KEYS = [
    "MINIO_ROOT_USER",
    "MINIO_ROOT_PASSWORD",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "POSTGRES_PASSWORD",
    "MLFLOW_DB_USER",
    "MLFLOW_DB_PASSWORD",
]


def secrets_env(tmp_path, **extra):
    """A clean environment: the real .env and the real cluster stay out of reach."""
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "ENV_FILE": str(tmp_path / ".env"),
        "APPLY": "0",
    }
    env.update(extra)
    return env


@NEEDS_OPENSSL
def test_secrets_generates_a_complete_env_file(tmp_path):
    proc = run(SECRETS, env=secrets_env(tmp_path))

    assert proc.returncode == 0, proc.stdout + proc.stderr
    body = (tmp_path / ".env").read_text()
    values = dict(
        line.split("=", 1) for line in body.splitlines() if "=" in line and not line.startswith("#")
    )
    for key in REQUIRED_KEYS:
        assert values.get(key), f"{key} missing or empty in the generated .env"
    assert values["MLFLOW_DB_PASSWORD"] != values["POSTGRES_PASSWORD"], (
        "one password reused for two accounts"
    )


@NEEDS_OPENSSL
def test_secrets_never_regenerates_an_existing_env(tmp_path):
    """Regenerating would orphan the passwords already inside the Postgres volume."""
    run(SECRETS, env=secrets_env(tmp_path))
    first = (tmp_path / ".env").read_text()

    proc = run(SECRETS, env=secrets_env(tmp_path))

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (tmp_path / ".env").read_text() == first
    assert "using existing" in proc.stdout


@NEEDS_OPENSSL
def test_secrets_prints_no_secret_value(tmp_path):
    proc = run(SECRETS, env=secrets_env(tmp_path))
    values = dict(
        line.split("=", 1)
        for line in (tmp_path / ".env").read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    output = proc.stdout + proc.stderr
    for key in ("MINIO_ROOT_PASSWORD", "POSTGRES_PASSWORD", "MLFLOW_DB_PASSWORD"):
        assert values[key] not in output, f"{key} leaked into the session log"


def test_secrets_refuses_an_env_missing_a_required_key(tmp_path):
    (tmp_path / ".env").write_text(
        "MINIO_ROOT_USER=minioadmin\nMINIO_ROOT_PASSWORD=x\nAWS_ACCESS_KEY_ID=mlflow\n"
        "AWS_SECRET_ACCESS_KEY=y\nMLFLOW_DB_USER=mlflow\nMLFLOW_DB_PASSWORD=z\n"
    )

    proc = run(SECRETS, env=secrets_env(tmp_path))

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "POSTGRES_PASSWORD" in proc.stderr


def test_secrets_refuses_when_the_minio_user_drifts_from_the_chart(tmp_path):
    """.env and infra/helm/minio/values.yaml name the same identity; drift = 403s."""
    (tmp_path / ".env").write_text(
        "MINIO_ROOT_USER=minioadmin\nMINIO_ROOT_PASSWORD=x\nAWS_ACCESS_KEY_ID=someone-else\n"
        "AWS_SECRET_ACCESS_KEY=y\nPOSTGRES_PASSWORD=p\nMLFLOW_DB_USER=mlflow\n"
        "MLFLOW_DB_PASSWORD=z\n"
    )

    proc = run(SECRETS, env=secrets_env(tmp_path))

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "twins" in proc.stderr


def test_the_minio_user_in_values_is_the_one_the_secrets_script_demands():
    """The other half of the twin: the chart really does create user 'mlflow'."""
    assert re.search(r"^\s*-\s*accessKey:\s*mlflow\s*$", MINIO_VALUES.read_text(), re.M)


# ------------------------------------------------------------- port twins ----


def kind_port_map() -> dict[int, int]:
    """containerPort -> hostPort, as the kind config declares them."""
    text = KIND_CONFIG.read_text()
    pairs = re.findall(r"containerPort:\s*(\d+)\s*(?:#[^\n]*)?\n\s*hostPort:\s*(\d+)", text)
    return {int(c): int(h) for c, h in pairs}


def test_kind_maps_the_documented_host_ports_to_the_service_node_ports():
    assert kind_port_map() == {
        80: 8081,
        443: 8443,
        30500: 5000,
        30900: 9000,
        30901: 9001,
        30300: 3030,
    }


def test_metabase_node_port_is_the_one_kind_publishes_on_3030():
    """M1-S5's twin. kind publishes host ports at cluster-CREATE time only, so a
    drift here is not a config bug you fix with `kubectl apply` — it is a cluster
    rebuild. That is exactly why the pair is asserted rather than trusted."""
    node_port = int(re.search(r"nodePort:\s*(\d+)", METABASE_MANIFEST.read_text()).group(1))
    assert kind_port_map()[node_port] == 3030


def test_mlflow_node_port_is_the_one_kind_publishes_on_5000():
    node_port = int(re.search(r"nodePort:\s*(\d+)", MLFLOW_NODEPORT.read_text()).group(1))
    assert kind_port_map()[node_port] == 5000


def test_minio_node_ports_are_the_ones_kind_publishes_on_9000_and_9001():
    values = MINIO_VALUES.read_text()
    ports = [int(p) for p in re.findall(r"nodePort:\s*(\d+)", values)]
    assert [kind_port_map()[p] for p in ports] == [9000, 9001]
