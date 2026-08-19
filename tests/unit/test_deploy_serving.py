"""M5-S1: the serving platform recipe's cluster-free half.

What is testable without a cluster is exactly the set of things that are wrong in
a file rather than wrong in a pod, and every one of them has cost this program a
session somewhere:

* the ROUTE is two numbers and one node name written in two files. Nothing at
  runtime complains when they drift — a controller on the wrong node simply
  answers nothing, and it looks precisely like a KServe fault (the M5 kickoff's
  risk R2). So the ingress values' nodeSelector is asserted against the cluster
  name in the kind config, and the hostPort against the same file's mapping.
* ``DRY_RUN=1`` must mutate nothing, helm included (gotcha #30: ``DRY_RUN=1 make
  destroy`` deleted the cluster for four milestones because the preview covered
  the files and not the most expensive action).
* the deployment MODE is the one decision ADR-004 made, and a chart default of
  ``Knative`` is one line away at all times.
* versions are pinned, because an unpinned chart is a different platform on a
  different day (MLOps charter, first refusal).

The live half — the route actually answering, the rollouts, the mode read back
off the ConfigMap the controller consumes — is proved by running the script
against the real cluster; the transcript is docs/serving_m5.md §2.
"""

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "deploy_serving.sh"
KIND_CONFIG = REPO / "infra" / "kind" / "kind-config.yaml"
INGRESS_VALUES = REPO / "infra" / "helm" / "ingress-nginx" / "values.yaml"
CERTMANAGER_VALUES = REPO / "infra" / "helm" / "cert-manager" / "values.yaml"
KSERVE_VALUES = REPO / "infra" / "helm" / "kserve" / "values.yaml"
MAKEFILE = REPO / "Makefile"

pytestmark = pytest.mark.unit


def code_only(text: str) -> str:
    """Everything a shell would execute, with comments and blank lines removed.

    This repo's scripts argue their own design at length, so a grep for a word is
    a grep of the argument as often as of the code (gotchas #35, #53, #60, #68).
    Anything asserting what the script DOES gets this; anything asserting what it
    SAYS reads the raw text on purpose."""
    return "\n".join(
        line for line in text.splitlines() if line.strip() and not line.strip().startswith("#")
    )


@pytest.fixture(scope="module")
def script() -> str:
    return SCRIPT.read_text()


@pytest.fixture(scope="module")
def kind_config() -> dict:
    return yaml.safe_load(KIND_CONFIG.read_text())


@pytest.fixture(scope="module")
def ingress_values() -> dict:
    return yaml.safe_load(INGRESS_VALUES.read_text())


@pytest.fixture(scope="module")
def kserve_values() -> dict:
    return yaml.safe_load(KSERVE_VALUES.read_text())


# ------------------------------------------------------------------ the route --


def test_the_ingress_is_pinned_to_the_node_whose_ports_kind_publishes(
    kind_config: dict, ingress_values: dict
) -> None:
    """Prevents R2: a controller scheduled on a worker answers nothing, and the
    symptom (curl: connection refused on :8081) points at KServe, at the ingress
    class, at the Service — at everything except where it actually is.

    The expected value is DERIVED from the kind config's cluster name rather than
    typed, so renaming the cluster fails here instead of at minute forty."""
    expected_node = f"{kind_config['name']}-control-plane"
    selector = ingress_values["controller"]["nodeSelector"]
    assert selector["kubernetes.io/hostname"] == expected_node

    # …and that node is the one carrying the mapping. A selector naming a node
    # with no published ports is the same failure with a different spelling.
    publishing = [
        node
        for node in kind_config["nodes"]
        if any(m["containerPort"] == 80 for m in node.get("extraPortMappings", []))
    ]
    assert len(publishing) == 1, "exactly one node may publish the serving route"
    assert publishing[0]["role"] == "control-plane"


def test_the_controller_binds_the_container_ports_kind_maps_to_the_host(
    kind_config: dict, ingress_values: dict
) -> None:
    """The route is two hops: kind maps host 8081 -> node 80, and the controller
    must actually BIND 80 on that node. A ClusterIP Service alone would leave hop
    two missing and the whole path silent."""
    mappings = {
        m["containerPort"]: m["hostPort"]
        for node in kind_config["nodes"]
        for m in node.get("extraPortMappings", [])
    }
    host_ports = ingress_values["controller"]["hostPort"]
    assert host_ports["enabled"] is True
    assert host_ports["ports"]["http"] in mappings
    assert host_ports["ports"]["https"] in mappings
    # The CLAUDE.md port family's serving pair, asserted from the config side.
    assert mappings[host_ports["ports"]["http"]] == 8081
    assert mappings[host_ports["ports"]["https"]] == 8443


def test_the_controller_tolerates_the_taint_the_node_it_is_pinned_to_carries(
    ingress_values: dict,
) -> None:
    """A nodeSelector without the matching toleration leaves the pod Pending
    forever with a message about taints and nothing about ports."""
    tolerations = ingress_values["controller"]["tolerations"]
    assert any(
        t.get("key") == "node-role.kubernetes.io/control-plane"
        and t.get("effect") == "NoSchedule"
        for t in tolerations
    )


def test_the_script_derives_the_node_and_port_rather_than_typing_them(
    script: str,
) -> None:
    """gotcha #52: the fix that changes a VALUE leaves the hazard in scope; the
    fix that derives it removes the hazard. Both the node name and the host port
    must come out of the kind config at run time."""
    assert 'CLUSTER_NAME="$(awk' in script
    assert 'INGRESS_NODE="${CLUSTER_NAME}-control-plane"' in script
    assert "ROUTE_PORT=" in script and "kind-config.yaml" in script
    # …and the derived value is CHECKED against the values file, not merely used.
    assert 'grep -q "kubernetes.io/hostname: $INGRESS_NODE"' in script


# ------------------------------------------------------------------- DRY_RUN --


def test_dry_run_reaches_no_mutating_verb(script: str) -> None:
    """gotcha #30. Everything after the DRY_RUN branch exits, so the preview
    cannot fall through into a helm upgrade — a preview that 'only' re-runs the
    upgrades is a preview that restarts things under whatever is reading them."""
    branch = script.split('if [[ "$DRY_RUN" == "1" ]]; then', 1)[1]
    preview = branch.split("fi", 1)[0]
    for verb in ("helm upgrade", "kubectl apply", "helm repo add"):
        # The preview may NAME the verb in a WOULD line; it may not run one.
        for line in preview.splitlines():
            stripped = line.strip()
            if stripped.startswith("echo ") or stripped.startswith("#"):
                continue
            assert verb not in stripped, f"DRY_RUN reaches a real {verb}"
    assert "exit 0" in preview, "the DRY_RUN branch must exit, never fall through"


# ------------------------------------------------------------------- the mode --


def test_kserve_is_configured_for_raw_deployment_not_knative(
    kserve_values: dict,
) -> None:
    """ADR-004's one decision. The chart's default is Knative, which drags
    Knative Serving and Istio in behind it."""
    assert kserve_values["kserve"]["controller"]["deploymentMode"] == "RawDeployment"


def test_the_script_reads_the_mode_back_off_the_live_configmap(script: str) -> None:
    """A submitted value proves what was asked for; the ConfigMap proves what the
    controller consumes. #59's rule: assert on the artifact the thing exists to
    produce."""
    assert "inferenceservice-config" in script
    assert "defaultDeploymentMode" in script
    assert 'if [[ "$DEPLOY_MODE" != "RawDeployment" ]]' in script


def test_the_kserve_ingress_class_is_the_one_this_script_installs(
    kserve_values: dict, ingress_values: dict
) -> None:
    """KServe stamps this class onto the Ingress it generates. If it names a class
    no controller owns, the InferenceService goes Ready and nothing routes to it —
    a green object with a dead URL."""
    kserve_class = kserve_values["kserve"]["controller"]["gateway"]["ingressGateway"][
        "className"
    ]
    assert kserve_class == ingress_values["controller"]["ingressClassResource"]["name"]


def test_the_accept_check_asserts_positively_on_the_controller(script: str) -> None:
    """gotcha #59: `flyte run --follow` exited 0 over a run that died, and a check
    written against the exit code printed `ok`. Here the failure shape is the
    same — a 404 is the PASS, so 'no error' proves nothing. The discriminator has
    to be a positive artifact of the thing that is supposed to answer.

    It must ALSO not be a signature the deployed thing suppresses: the first
    version of this check demanded a `Server: nginx` header, which modern
    ingress-nginx omits on purpose, and it went RED over a perfectly good
    install. `/healthz` is the controller's own endpoint on the same port."""
    code = code_only(script)
    assert "/healthz" in code
    assert 'HEALTHZ_CODE" != "200"' in code
    assert "server:" not in code.lower(), (
        "the Server header is suppressed by ingress-nginx — it cannot be the "
        "discriminator"
    )


# ------------------------------------------------------------------- the pins --


@pytest.mark.parametrize(
    "variable",
    [
        "INGRESS_CHART_VERSION",
        "CERTMANAGER_CHART_VERSION",
        "KSERVE_CHART_VERSION",
    ],
)
def test_every_chart_version_is_pinned_to_an_exact_string(
    script: str, variable: str
) -> None:
    """MLOps charter, first refusal: unpinned versions. A range would make this a
    different platform on a different day, silently."""
    match = re.search(rf'^{variable}="([^"]+)"', script, re.M)
    assert match, f"{variable} is not assigned a literal"
    value = match.group(1)
    assert value not in ("", "latest")
    for wildcard in ("*", "^", "~", ">", "<"):
        assert wildcard not in value, f"{variable}={value} is a range, not a pin"


def test_the_fallback_adr_is_named_where_the_wall_would_be_hit(script: str) -> None:
    """The three-attempt rule is only useful if the next session meets the
    fallback at the wall instead of going looking for it."""
    assert "ADR-004" in script
    assert "mlserver" in script


# ------------------------------------------------------------------- wiring ----


def test_the_make_target_exists_and_installs_no_model() -> None:
    """Serving reads the pointer and never moves it (M5 law 2). This target has no
    business knowing the registry exists — the champion goes on the wire at S2."""
    line = next(
        ln for ln in MAKEFILE.read_text().splitlines() if ln.startswith("deploy-serving:")
    )
    assert "DRY_RUN=1 previews" in line
    assert "Installs NO model" in line


def test_the_deploy_never_touches_the_registry_or_the_alias(script: str) -> None:
    """M5 law 2, made falsifiable. The champion is version 2 before and after
    every M5 story, and the cheapest guarantee is a script that cannot name it.

    Asserted over CODE only — this file's own header explains at length that the
    script has no business reading the registry, and a word-search would find
    every one of those sentences. #53/#68's rule: in a repo where prose is
    load-bearing, a check about code must look only where code is."""
    for needle in ("champion", "models:/", "mlflow"):
        assert needle not in code_only(script).lower(), (
            f"the serving platform deploy names '{needle}' in CODE — it has no "
            "business reading or moving the serving pointer"
        )


def test_the_deploy_reads_no_secret(script: str) -> None:
    """The model store credential is S2's, and it is a NEW read-only MinIO
    identity so a leaked serving credential cannot write the registry's
    artifacts. Nothing here reads .env, so nothing here can leak it.

    Code only, for the same reason as the test above."""
    code = code_only(script)
    assert ".env" not in code
    assert "--set" not in code, "a --set argument is visible in ps and in history"
