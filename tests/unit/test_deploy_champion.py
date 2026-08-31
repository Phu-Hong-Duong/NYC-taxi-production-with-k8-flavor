"""M5-S2: the champion-deploy recipe's cluster-free half.

The live half — a prediction off the declared route, the read-only credential
actually downloading, the idempotent re-run proved by pod age — is in
docs/serving_m5.md §3. What is here is what a diff can be wrong about:

* **the alias must be READ and never moved** (M5 kickoff law 2). Two independent
  guards: no mutating registry verb appears in either the deploy or the resolver,
  and the deploy reads the version before AND after its own mutations.
* **the storageUri must never be a literal.** A committed S3 path is a second
  address for the champion that nothing keeps in step with the registry — the day
  the alias moves, an apply would still succeed and serve the wrong model.
* **``DRY_RUN=1`` must mutate nothing, helm included** (gotcha #30).
* **the credential must be least-privilege AND sufficient.** MinIO's built-in
  ``readonly`` is neither: it omits ``s3:ListBucket``, which is what KServe's
  storage-initializer HEADs the bucket with, and it is bucket-WIDE. Both halves
  are asserted so a future simplification back to ``policy: readonly`` fails here
  instead of in a 403 that reads like a wrong password.
* **the images must be pinned**, and the base by digest (the Metabase precedent).
"""

from __future__ import annotations

import re

import pytest
import yaml
from conftest import REPO, executable_lines

DEPLOY = REPO / "scripts" / "deploy_champion.sh"
RESOLVER = REPO / "scripts" / "resolve_champion_storage.py"
RUNTIME = REPO / "infra" / "manifests" / "serving-runtime-mlserver.yaml"
ISVC = REPO / "infra" / "manifests" / "inferenceservice-champion.yaml"
MINIO_VALUES = REPO / "infra" / "helm" / "minio" / "values.yaml"
SECRETS = REPO / "scripts" / "platform_secrets.sh"
DOCKERFILE = REPO / "docker" / "serving.Dockerfile"
MAKEFILE = REPO / "Makefile"

pytestmark = pytest.mark.unit

PLACEHOLDERS = (
    "RESOLVED-AT-DEPLOY-TIME-FROM-THE-CHAMPION-ALIAS",
    "CHAMPION-VERSION-RESOLVED-AT-DEPLOY-TIME",
)


@pytest.fixture(scope="module")
def deploy() -> str:
    return DEPLOY.read_text()


@pytest.fixture(scope="module")
def isvc() -> dict:
    return yaml.safe_load(ISVC.read_text())


@pytest.fixture(scope="module")
def runtime() -> dict:
    return yaml.safe_load(RUNTIME.read_text())


@pytest.fixture(scope="module")
def minio_values() -> dict:
    return yaml.safe_load(MINIO_VALUES.read_text())


# --------------------------------------------------------------------------
# The alias is read, never moved
# --------------------------------------------------------------------------


def test_neither_the_deploy_nor_the_resolver_names_a_mutating_registry_verb(deploy):
    """M5 is legislated alias-neutral. The needles are METHOD CALLS, so they are
    matched with a trailing `(` — gotcha #68's lesson, where a ban on running a
    command caught the message telling a human to run it."""
    forbidden = (
        "set_registered_model_alias(",
        "delete_registered_model_alias(",
        "create_model_version(",
        "transition_model_version_stage(",
        "register_model(",
    )
    for source in (executable_lines(deploy), executable_lines(RESOLVER.read_text())):
        for needle in forbidden:
            assert needle not in source, f"{needle} must not appear in the serving path"


def test_the_deploy_reads_the_champion_version_before_and_after_its_own_changes(deploy):
    """A claim nobody checks is a sentence. The script reads the alias first,
    reads it again at the end, and treats a difference as a FAILURE."""
    body = executable_lines(deploy)
    assert body.count("champion_version)") >= 2, "the alias must be read on both sides"
    assert "ALIAS_BEFORE" in body and "ALIAS_AFTER" in body
    assert re.search(r'if \[\[ "\$ALIAS_BEFORE" != "\$ALIAS_AFTER" \]\]', body)
    assert "exit 2" in body


def test_the_resolver_is_a_reader():
    """`verify-m5` is meant to reuse it, so it must be safe to call from a gate —
    the same property `flyte_run_actions.py` is pinned for."""
    body = executable_lines(RESOLVER.read_text())
    for verb in ("delete_", "create_", ".log_", "set_tag(", "update_"):
        assert verb not in body, f"a reader must not call {verb}"


# --------------------------------------------------------------------------
# The storageUri is resolved, never typed
# --------------------------------------------------------------------------


def test_the_committed_inferenceservice_carries_placeholders_not_a_model_path(isvc):
    text = ISVC.read_text()
    for placeholder in PLACEHOLDERS:
        assert placeholder in text
    model = isvc["spec"]["predictor"]["model"]
    assert model["storageUri"] == PLACEHOLDERS[0]
    # Deliberately not a valid URI: an accidental `kubectl apply -f` of this file
    # must fail rather than half-work.
    assert not model["storageUri"].startswith("s3://")


def test_no_committed_serving_file_names_a_run_id_a_logged_model_id_or_a_bucket_path():
    """The literals that would rot the day the alias moves (F-017's rule, and
    F-022's reasoning one layer up: the row means 'the champion, whatever it is
    now')."""
    patterns = (
        re.compile(r"\bm-[0-9a-f]{32}\b"),      # a logged-model id
        re.compile(r"s3://mlflow-artifacts/\d"),  # a resolved artifact prefix
    )
    for path in (ISVC, RUNTIME, DEPLOY):
        body = executable_lines(path.read_text())
        for pattern in patterns:
            assert not pattern.search(body), f"{path.name} names a literal that will rot"


def test_the_deploy_refuses_to_render_if_a_placeholder_has_gone(deploy):
    body = executable_lines(deploy)
    assert "refusing to guess" in body


# --------------------------------------------------------------------------
# DRY_RUN mutates nothing (gotcha #30)
# --------------------------------------------------------------------------


def invocations_only(text: str) -> str:
    """`code_only`, minus every line that only PRINTS or only ASSIGNS.

    Written after this very test went red twice on its own subject, for two
    different not-a-command reasons: the DRY_RUN banner says `WOULD helm upgrade
    minio …`, which is the script promising NOT to do the thing, and
    `HELM=(helm --kube-context …)` builds the array the command is later run
    THROUGH. Gotcha #68 for the fifth and sixth time — a needle about running a
    command must sit where a shell would START one, and neither an `echo` nor an
    assignment is such a place."""
    assignment = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
    return "\n".join(
        line
        for line in executable_lines(text).splitlines()
        if not line.strip().startswith("echo") and not assignment.match(line.strip())
    )


def test_dry_run_returns_before_any_mutating_verb(deploy):
    body = executable_lines(deploy)
    marker = "DRY_RUN — nothing was applied"
    assert marker in body
    preview = invocations_only(deploy[: deploy.index(marker)])
    for verb in ("helm", "upgrade --install", "apply -f", "create secret", "rollout"):
        assert verb not in preview, f"DRY_RUN previews reach {verb!r} before returning"
    assert "exit 0" in body[body.index(marker) : body.index(marker) + 200]


def test_the_makefile_exposes_serve_quote_and_holidays():
    body = MAKEFILE.read_text()
    assert "serve:" in body and "scripts/deploy_champion.sh" in body
    assert "quote:" in body and "taxi_mlops.serving" in body
    assert "holidays:" in body and "derive_us_federal_holidays.py" in body


# --------------------------------------------------------------------------
# The credential: least privilege AND sufficient
# --------------------------------------------------------------------------


def test_the_serving_identity_uses_a_custom_policy_and_not_minio_s_readonly(minio_values):
    """MinIO's built-in `readonly` grants `s3:GetObject` + `s3:GetBucketLocation`
    and NOT `s3:ListBucket`, so the storage-initializer's HeadBucket 403s — on a
    user that exists, under a policy called "readonly", which reads exactly like
    a wrong password. Observed live at M5-S2."""
    serving = next(u for u in minio_values["users"] if u["accessKey"] == "serving")
    assert serving["policy"] == "serving-readonly"
    assert serving["policy"] not in {"readonly", "readwrite", "writeonly", "consoleAdmin"}
    assert serving["existingSecret"] == "minio-serving-user"
    assert "secretKey" not in str(serving.get("secretKey", "")), "no secret in values"


def test_the_serving_policy_exists_grants_no_write_and_is_scoped_to_one_bucket(minio_values):
    policy = next(p for p in minio_values["policies"] if p["name"] == "serving-readonly")
    actions = {action for statement in policy["statements"] for action in statement["actions"]}
    resources = {res for statement in policy["statements"] for res in statement["resources"]}

    assert actions == {"s3:GetObject", "s3:GetBucketLocation", "s3:ListBucket"}
    # The sufficiency half: without ListBucket the download 403s.
    assert "s3:ListBucket" in actions
    # The least-privilege half: not one verb that can change a byte.
    assert not any(
        action.startswith(("s3:Put", "s3:Delete", "s3:Create", "s3:Abort")) for action in actions
    )
    assert actions != {"s3:*"}
    # Scoped: it cannot see the orchestrator's bucket at all.
    assert resources == {"arn:aws:s3:::mlflow-artifacts/*", "arn:aws:s3:::mlflow-artifacts"}
    assert not any("flyte" in resource for resource in resources)


def test_the_serving_credential_is_additive_and_required_in_the_secrets_recipe():
    body = SECRETS.read_text()
    assert "SERVING_S3_ACCESS_KEY=serving SERVING_S3_SECRET_KEY=" in body
    assert "SERVING_S3_ACCESS_KEY SERVING_S3_SECRET_KEY" in body
    assert "minio-serving-user" in body


def test_no_secret_value_reaches_a_command_line(deploy):
    """The deploy pipes `create secret --dry-run=client -o yaml` into apply, the
    shape platform_secrets.sh uses. A `--from-literal` on a `kubectl create`
    that is not `--dry-run` would put the value where `ps` can read it."""
    body = executable_lines(deploy)
    for line in body.splitlines():
        if "--from-literal" in line:
            assert "SERVING_S3_" in line, "only the serving keys, by name, never a value"
    assert "--dry-run=client -o yaml" in body
    assert "echo" not in executable_lines(deploy).split("SERVING_S3_SECRET_KEY")[1].splitlines()[0]


def test_the_predictor_reaches_minio_by_its_IN_CLUSTER_name(deploy):
    """F-023's lesson from the other side: split horizon is the HOST's problem
    and never a pod's. A pod handed `localhost:9000` resolves it to itself."""
    body = executable_lines(deploy)
    assert "minio.platform.svc.cluster.local:9000" in body
    assert "localhost:9000" not in body


# --------------------------------------------------------------------------
# Pins
# --------------------------------------------------------------------------


def test_the_runtime_image_is_pinned_and_is_not_latest(runtime):
    image = runtime["spec"]["containers"][0]["image"]
    assert not image.endswith(":latest"), "an unpinned tag is a different model on a different day"
    assert ":" in image
    assert runtime["spec"]["containers"][0]["imagePullPolicy"] == "IfNotPresent"


def test_the_predictor_base_image_is_pinned_by_tag_AND_digest():
    """The Metabase precedent (M1-S5): a tag is a name, a digest is a fact."""
    from_lines = [
        line for line in DOCKERFILE.read_text().splitlines() if line.startswith("FROM ")
    ]
    assert len(from_lines) == 1
    assert "@sha256:" in from_lines[0]
    assert "seldonio/mlserver:1.7.1-mlflow" in from_lines[0]


def test_the_predictor_image_pins_lightgbm_to_the_champion_s_version():
    """`MLmodel` records `lgb_version: 4.7.0`; a range here would let a rebuild
    serve a different booster implementation than the one the gate measured."""
    assert 'pip install --no-cache-dir "lightgbm==4.7.0"' in DOCKERFILE.read_text()


def test_the_runtime_declares_only_the_format_it_can_actually_serve(runtime):
    """The upstream manifest claims eight formats; this image carries LightGBM
    and MLflow and nothing else new, so `autoSelect` on sklearn or xgboost would
    be a trap for the next InferenceService somebody writes."""
    formats = {entry["name"] for entry in runtime["spec"]["supportedModelFormats"]}
    assert formats == {"mlflow"}
    assert runtime["spec"]["protocolVersions"] == ["v2"]


def test_the_inferenceservice_pins_raw_deployment_mode_and_the_runtime(isvc):
    """Belt and braces on purpose: the cluster-wide default is a ConfigMap
    somebody could change, and an InferenceService that silently became
    Serverless would sit Unknown asking for a Knative control plane."""
    assert isvc["metadata"]["annotations"]["serving.kserve.io/deploymentMode"] == "RawDeployment"
    model = isvc["spec"]["predictor"]["model"]
    assert model["runtime"] == yaml.safe_load(RUNTIME.read_text())["metadata"]["name"]
    assert model["modelFormat"]["name"] == "mlflow"
    assert isvc["spec"]["predictor"]["serviceAccountName"] == "taxi-serving"


def test_the_deploy_waits_for_the_ROLLOUT_and_not_only_the_isvc_condition(deploy):
    """The false green this story watched happen: on a re-deploy the
    InferenceService's Ready condition is satisfied by the pod ALREADY SERVING,
    so the accept check interrogated the predictor being replaced. Siblings of
    gotchas #59/#65 — a wait that the thing you are replacing can satisfy is not
    a wait.

    THIS TEST USED TO PIN THE LITERAL `--for=condition=Ready`, and M6-S2 had to
    change that flag (F-036: kubectl v1.36 ignores conditions while
    `observedGeneration` trails `generation`, which KServe v0.20.0 leaves behind
    on every re-deploy, so the wait could never succeed). The literal went red
    for a correct fix — gotcha #50 exactly. What this story's ordering decision
    actually asserts is the ORDER of two waits, so that is what is asserted now,
    derived rather than typed: whatever form the InferenceService-level wait
    takes, it must come after the rollout."""
    body = executable_lines(deploy)
    assert "rollout status" in body
    rollout = body.index("rollout status")
    isvc_waits = [
        match.start()
        for match in re.finditer(r"wait\b", body)
        if "inferenceservice/" in body[match.start() : match.start() + 400]
    ]
    assert isvc_waits, "there is no InferenceService-level readiness wait at all"
    assert rollout < min(isvc_waits), "the rollout must be waited on FIRST"
