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

import ast
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
WORKFLOWS = REPO / "pipelines" / "flyte" / "workflows.py"
DRILL = REPO / "scripts" / "pipeline_cache_drill.sh"


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


# --- the cache, and the two stages that refuse one (M4-S4, leg 2) --------------
#
# All of these parse the AST. `workflows.py` argues its cache design at length in
# prose, so a check that grepped for the word "cache" would pass on the argument
# and never look at the decorator — gotcha #53, which cost two red tests in one
# file for finding a module name in a docstring.


def _workflow_tree():
    return ast.parse(WORKFLOWS.read_text())


def _tasks() -> dict[str, ast.Call]:
    """Every `@<env>.task(...)` in workflows.py, by function name."""
    found: dict[str, ast.Call] = {}
    for node in ast.walk(_workflow_tree()):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            call = dec if isinstance(dec, ast.Call) else None
            attr = call.func if call else dec
            if isinstance(attr, ast.Attribute) and attr.attr == "task":
                found[node.name] = call
    return found


def _cache_arg(call: ast.Call | None) -> str | None:
    """What a task decorator says about caching: a literal, a name, or None."""
    if call is None:
        return None
    for kw in call.keywords:
        if kw.arg == "cache":
            if isinstance(kw.value, ast.Constant):
                return str(kw.value.value)
            if isinstance(kw.value, ast.Name):
                return kw.value.id
    return None


def test_every_pipeline_task_declares_its_cache_explicitly():
    """No stage may INHERIT a caching decision.

    A task that says nothing gets whatever the SDK's default is that release —
    which makes "is this stage cached?" a question about flyte's version rather
    than about this repo. Every stage states it, so the answer is always in the
    diff.
    """
    tasks = _tasks()
    assert tasks, "no @env.task decorators found — the parser, not the pipeline, broke"
    silent = [name for name, call in tasks.items() if _cache_arg(call) is None]
    assert not silent, f"these tasks inherit their caching instead of declaring it: {silent}"


def test_the_uncached_stages_are_exactly_register_and_main():
    """Both refusals are deliberate and both are argued in their own docstrings.

    `register` reads the LIVE registry, so a cached verdict answers "what is
    serving?" with what WAS serving. `main` is uncached so the rerun's evidence
    stays per-stage — a cached parent returns in one action and proves nothing
    about the five stages underneath it.
    """
    disabled = {n for n, c in _tasks().items() if _cache_arg(c) == "disable"}
    assert disabled == {"register", "main"}, (
        f"the set of uncached stages moved to {disabled}; if that is intended, the "
        f"docstring arguing it must move too, and so must the drill's own list"
    )


def test_the_cached_stages_all_share_one_cache_object():
    """Five stages, one policy. Per-stage cache settings would be five places to
    check when the answer to "what invalidates this?" has to be one sentence."""
    cached = {n: _cache_arg(c) for n, c in _tasks().items() if _cache_arg(c) != "disable"}
    assert set(cached) == {"ingest", "validate", "build_features", "train", "evaluate"}
    assert set(cached.values()) == {"_STAGE_CACHE"}, cached


def test_the_drill_and_the_workflow_agree_on_which_stages_are_uncached():
    """A twin, in the shape M0-S3 established for the port pairs.

    The drill asserts CACHE_DISABLED for the stages it lists in `UNCACHED` and
    CACHE_HIT for every other one. If a stage loses its cache in workflows.py and
    the drill is not told, the drill goes red for a change somebody made on
    purpose; if a stage GAINS a cache and the drill still excuses it, the drill
    silently stops checking it. Neither failure names these files, which is why
    the pair is pinned here.
    """
    text = DRILL.read_text()
    match = re.search(r"UNCACHED = \{([^}]*)\}", text)
    assert match, "the drill no longer names an UNCACHED set"
    listed = {piece.strip().strip('"\'') for piece in match.group(1).split(",") if piece.strip()}
    disabled = {n for n, c in _tasks().items() if _cache_arg(c) == "disable"}
    assert listed == disabled, f"drill says {listed}, workflows.py says {disabled}"


def test_the_cache_salt_travels_to_the_pod_exactly_like_the_image_ref():
    """The salt is computed on the host and must be READ in the pod, never recomputed.

    The `.dvc` pins are not in the task image and must not be (they describe the
    tree a run was launched from, not the tree the image was built from). So the
    only thing that keeps client and pod on one cache key is this variable being
    in every TaskEnvironment's env_vars — the same lesson `TAXI_PIPELINE_IMAGE`
    paid for when the first on-cluster run died at import.
    """
    tree = _workflow_tree()
    env_vars_keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_ENV_VARS" for t in node.targets
        ):
            assert isinstance(node.value, ast.Dict)
            env_vars_keys = {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
    assert env_vars_keys == {"TAXI_PIPELINE_IMAGE", "TAXI_DATA_PIN"}, env_vars_keys

    environments = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "TaskEnvironment"
    ]
    assert len(environments) == 3, "expected the light/data/train environments"
    for env in environments:
        passed = {kw.arg for kw in env.keywords}
        assert "env_vars" in passed, "a TaskEnvironment stopped carrying env_vars"
        value = next(kw.value for kw in env.keywords if kw.arg == "env_vars")
        assert isinstance(value, ast.Name) and value.id == "_ENV_VARS", (
            "an environment builds its own env_vars — then one pod's cache salt "
            "can differ from another's, and the stages stop sharing a key"
        )


def test_the_data_pin_refuses_rather_than_defaulting():
    """A salt that falls back to a constant produces the exact failure it exists
    to prevent — a green transcript over data nobody can identify — and produces
    it silently. So `_data_pin` raises, and the raise names the remedy."""
    func = next(
        node
        for node in ast.walk(_workflow_tree())
        if isinstance(node, ast.FunctionDef) and node.name == "_data_pin"
    )
    raises = [n for n in ast.walk(func) if isinstance(n, ast.Raise)]
    assert raises, "_data_pin no longer refuses; it now has a silent default"
    returns = [n for n in ast.walk(func) if isinstance(n, ast.Return)]
    constant_returns = [r for r in returns if isinstance(r.value, ast.Constant)]
    assert not constant_returns, "a constant fallback salt is not a salt"


def test_the_action_reader_only_reads():
    """`verify-m4` (M4-S5) is meant to reuse this, and a gate that can mutate the
    run it is judging is not a gate. Checked structurally: the module may call
    listall/get and nothing that launches, aborts or deletes."""
    tree = ast.parse((REPO / "scripts" / "flyte_run_actions.py").read_text())
    # Scoped to the FLYTE objects. A blanket ban on the verb `run` fails on
    # `asyncio.run(...)`, which is how this module has a main at all — and a check
    # that fires on the wrong thing gets edited rather than heeded (gotcha #50).
    remote = {"Action", "ActionDetails", "Run", "flyte", "client", "remote"}
    called = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        base = node.func.value
        while isinstance(base, ast.Attribute):
            base = base.value
        if isinstance(base, ast.Name) and base.id in remote:
            called.add(node.func.attr)
    forbidden = called & {"run", "launch", "abort", "delete", "terminate", "create", "deploy"}
    assert not forbidden, f"the action reader calls {forbidden} — it is supposed to only read"
    assert called, "the parser found no flyte calls at all — it is checking nothing"


def test_the_runner_refuses_an_image_older_than_the_source_it_would_run():
    """F-026, pinned. `src/taxi_mlops` reaches a task pod ONLY through the image
    (flyte's default copy-style bundles the loaded modules, and every stage imports
    the model code inside its function body), while the image tag comes from a
    manifest only `make image-load` rewrites. So the runner must diff the image's
    commit against HEAD — and must do it over the paths the image is the sole
    carrier of, which pointedly EXCLUDES `pipelines/`: that is what the bundle
    ships, so refusing on it would refuse a run whose code did reach the pod.
    """
    text = (REPO / "scripts" / "run_pipeline.sh").read_text()
    # Read the array off its own line. `test_cluster_scripts.py` learned at M2-S1
    # that finding a shell array's end with the next `)` truncates it at the first
    # paren in a trailing comment (gotcha #35), so this matches the whole line and
    # the array is deliberately written without one.
    match = re.search(r"^IMAGE_PATHS=\(([^)\n]*)\)\s*$", text, re.M)
    assert match, "run_pipeline.sh no longer declares the image-carried paths"
    paths = set(match.group(1).split())
    assert paths == {"src", "pyproject.toml", "uv.lock", "docker"}, paths
    assert "pipelines" not in paths, (
        "pipelines/ travels in the code bundle; guarding it would refuse runs whose "
        "code genuinely reached the pod"
    )
    assert "exit 3" in text, "the drift refusal needs its own exit code"
    assert "IMAGE_DRIFT_OK" in text, "the waiver must exist and must announce itself"
