"""M4-S4: the task-pod wiring, as twins that cannot drift quietly.

Everything here is a pair of facts written in two files, in the shape
`test_platform_scripts.py`'s port twins established at M0-S3. None of these pairs
fails at deploy time, which is the whole reason they are tested:

* a drifted MinIO endpoint or key id is a task that RUNS, succeeds, and puts its
  result somewhere nobody reads — or a 403 hours later in a training run;
* a tree staged but not mounted is an empty directory that reads as "no data for
  that month";
* a stager pointed at a different claim silently fills a volume nothing consumes;
* and the two halves of F-023's split-horizon fix exist precisely BECAUSE they
  must differ — an edit that makes them agree re-breaks either the CLI's upload or
  the task's writes, and neither failure names these files.

Nothing here needs a cluster. The live half is `make pipeline` and the transcript
in `docs/pipeline_m4.md` §5.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PODTEMPLATE = REPO / "infra" / "manifests" / "flyte-task-podtemplate.yaml"
DATA_PVC = REPO / "infra" / "manifests" / "flyte-task-data-pvc.yaml"
STAGER_POD = REPO / "infra" / "manifests" / "flyte-data-stager.yaml"
STAGER_SCRIPT = REPO / "scripts" / "stage_pipeline_data.sh"
FLYTE_VALUES = REPO / "infra" / "helm" / "flyte" / "values.yaml"
SECRETS = REPO / "scripts" / "platform_secrets.sh"
MLFLOW_VALUES = REPO / "infra" / "helm" / "mlflow" / "values.yaml"


def _yaml(path: Path):
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(path.read_text())


def _default_container() -> dict:
    return _yaml(PODTEMPLATE)["template"]["spec"]["containers"][0]


def _env() -> dict[str, str]:
    return {e["name"]: e.get("value") for e in _default_container()["env"]}


def test_task_pods_and_the_flyte_server_address_the_same_minio_as_the_same_user():
    values = _yaml(FLYTE_VALUES)
    s3 = values["configuration"]["storage"]["providerConfig"]["s3"]
    env = _env()
    assert env["FLYTE_AWS_ENDPOINT"] == s3["endpoint"]
    assert env["FLYTE_AWS_ACCESS_KEY_ID"] == s3["accessKey"]


def test_the_task_pod_endpoints_are_in_cluster_names_and_never_localhost():
    """A pod's `localhost` is the pod. This is the half of F-023 that faces in."""
    env = _env()
    for key in ("FLYTE_AWS_ENDPOINT", "MLFLOW_TRACKING_URI", "MLFLOW_S3_ENDPOINT_URL"):
        assert "localhost" not in env[key], f"{key} would resolve to the pod itself"
        assert "svc.cluster.local" in env[key]


def test_the_client_signing_endpoint_is_the_host_route_and_differs_from_the_pods():
    """F-023's fix, both halves, asserted against each other rather than by value."""
    values = _yaml(FLYTE_VALUES)
    signing = values["configuration"]["inline"]["storage"]["signedUrl"]["stowConfigOverride"]
    serving = values["configuration"]["storage"]["providerConfig"]["s3"]["endpoint"]
    assert "localhost" in signing["endpoint"], "the CLI cannot resolve an in-cluster name"
    assert signing["endpoint"] != serving


def test_the_named_pod_template_is_the_one_the_flyte_config_asks_for():
    values = _yaml(FLYTE_VALUES)
    configured = values["configuration"]["inline"]["plugins"]["k8s"][
        "default-pod-template-name"
    ]
    assert configured == _yaml(PODTEMPLATE)["metadata"]["name"]


def test_the_task_image_is_never_pulled():
    """D-001: `kind load` put it in containerd and it exists in no registry."""
    assert _default_container()["imagePullPolicy"] in {"IfNotPresent", "Never"}


def test_the_default_container_is_named_default():
    """The k8s plugin's contract for "merge these into the primary container"."""
    assert _default_container()["name"] == "default"


def test_every_staged_tree_is_mounted_and_every_mounted_tree_is_staged():
    staged = re.search(r"^TREES=\(([^)]*)\)", STAGER_SCRIPT.read_text(), re.M)
    assert staged, "TREES=(...) not found in the stager"
    staged_trees = set(staged.group(1).split())
    mounted = {m["subPath"] for m in _default_container()["volumeMounts"]}
    assert staged_trees == mounted


def test_the_data_is_mounted_under_data_but_never_over_it():
    """gotcha #58, as a test: the committed `data/reference/` must stay visible.

    A single mount at /app/data would mask the lookup tables the feature path
    reads, producing an image that imports every module and cannot build a
    feature. Mounting the trees individually is what keeps them visible.
    """
    paths = [m["mountPath"].rstrip("/") for m in _default_container()["volumeMounts"]]
    assert "/app/data" not in paths
    assert all(p.startswith("/app/data/") for p in paths)


def test_the_pod_template_the_pvc_and_the_stager_all_name_one_claim():
    claim = _yaml(DATA_PVC)["metadata"]["name"]
    template_claim = _yaml(PODTEMPLATE)["template"]["spec"]["volumes"][0][
        "persistentVolumeClaim"
    ]["claimName"]
    stager = _yaml(STAGER_POD)
    stager_claim = stager["spec"]["volumes"][0]["persistentVolumeClaim"]["claimName"]
    assert template_claim == claim
    assert stager_claim == claim
    assert "STAGER_POD:-" + stager["metadata"]["name"] in STAGER_SCRIPT.read_text()


def test_no_secret_value_is_written_into_any_of_the_new_manifests():
    """Credentials reach pods by reference; the endpoint and key id are not secret."""
    for path in (PODTEMPLATE, DATA_PVC, STAGER_POD):
        text = path.read_text()
        assert "SECRET_ACCESS_KEY=" not in text
        assert "secretKey:" not in text
    refs = {r["secretRef"]["name"] for r in _default_container()["envFrom"]}
    assert refs == {"flyte-task-storage", "flyte-task-mlflow"}
    for name in refs:
        assert name in SECRETS.read_text(), f"{name} is referenced but never converged"


def test_the_stager_pins_its_image_by_digest():
    """The Metabase precedent: a tag alone is not a pin."""
    image = _yaml(STAGER_POD)["spec"]["containers"][0]["image"]
    assert "@sha256:" in image


def test_mlflow_allows_every_name_it_is_addressed_by_with_and_without_the_port():
    """F-025, and specifically the half that broke the host route.

    Setting `serverAllowedHosts` REPLACES MLflow's default list, and the uvicorn
    middleware compares the whole Host header — port included. A list of bare
    hostnames fixes the in-cluster client and 403s every host-side one, so both
    forms have to be present for every name.
    """
    allowed = set(_yaml(MLFLOW_VALUES)["serverAllowedHosts"])
    assert "*" not in allowed, "a wildcard deletes the protection rather than configuring it"
    for name in ("localhost", "127.0.0.1", "mlflow.mlflow.svc.cluster.local", "mlflow.mlflow"):
        assert name in allowed
        assert f"{name}:5000" in allowed, f"{name} without its port 403s the host route"


def test_the_task_pods_mlflow_route_is_the_service_mlflow_actually_allows():
    """The two files that would otherwise disagree about one hostname."""
    allowed = set(_yaml(MLFLOW_VALUES)["serverAllowedHosts"])
    uri = _env()["MLFLOW_TRACKING_URI"]
    host = uri.split("//", 1)[1]
    assert host in allowed, f"a task pod addresses {host}, which MLflow would refuse"
