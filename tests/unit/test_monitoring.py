"""M6-S1: the monitoring stack's cluster-free half.

What can be wrong in a FILE rather than in a pod, for a metrics stack, is a
short and specific list — and every entry below is either something this session
actually got wrong or something a predecessor milestone paid for:

* **the scrape port was PROBED, and the probe must stay in the repo.** KServe
  stamps `prometheus.kserve.io/port: "8080"` on the predictor pod and 8080
  /metrics is a 404 on this runtime; 8082 answers. A values file that drifted
  back to the advertised port would produce a permanently-down target, which
  renders as an empty panel, which is the same picture as a quiet system
  (gotcha #70: ask the server).
* **`DRY_RUN=1` must mutate nothing, helm included** — gotcha #30, for which
  `DRY_RUN=1 make destroy` deleted the cluster for four milestones.
* **no password on a command line.** `--set adminPassword=…` is readable by
  `ps`; the chart default is published. The credential must come from a Secret.
* **the route is the EXISTING one.** M6 law 1: kind publishes host ports at
  cluster-CREATE only, so a monitoring UI that wants its own hostPort has found
  a wall, not a task.
* **the ingress controller cannot RollingUpdate.** hostPort + one replica +
  a single-node nodeSelector deadlocks the default strategy: the surge pod can
  never bind port 80. Found live here, by a rollout that hung for 10 minutes
  while the route served happily.
* **nothing here may promote, or even read the registry.** M6 law 3, made
  falsifiable at the cheapest possible level (M5-S1's precedent: a script that
  does not know the registry exists).

The live half — targets actually up, a real request moving a counter, every
panel query returning series — is `make monitoring-accept`, and its transcript
is docs/monitoring_m6.md.
"""

import ast
import json
import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
DEPLOY = REPO / "scripts" / "deploy_monitoring.sh"
ACCEPT = REPO / "scripts" / "monitoring_accept.py"
PROBE = REPO / "scripts" / "probe_mlserver_metrics.py"
PROM_VALUES = REPO / "infra" / "helm" / "monitoring" / "prometheus-values.yaml"
GRAFANA_VALUES = REPO / "infra" / "helm" / "monitoring" / "grafana-values.yaml"
INGRESS_VALUES = REPO / "infra" / "helm" / "ingress-nginx" / "values.yaml"
KIND_CONFIG = REPO / "infra" / "kind" / "kind-config.yaml"
DASHBOARDS = REPO / "analytics" / "grafana" / "dashboards"
SECRETS = REPO / "scripts" / "platform_secrets.sh"
MAKEFILE = REPO / "Makefile"

pytestmark = pytest.mark.unit


def code_only(text: str) -> str:
    """Everything a shell would execute, comments and blank lines removed.

    This repo's scripts argue their own design at length, so a grep for a word
    hits the argument as often as the code (gotchas #35, #53, #60, #68)."""
    return "\n".join(
        line for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


@pytest.fixture(scope="module")
def deploy() -> str:
    return DEPLOY.read_text()


@pytest.fixture(scope="module")
def prom_values() -> dict:
    return yaml.safe_load(PROM_VALUES.read_text())


@pytest.fixture(scope="module")
def grafana_values() -> dict:
    return yaml.safe_load(GRAFANA_VALUES.read_text())


@pytest.fixture(scope="module")
def ingress_values() -> dict:
    return yaml.safe_load(INGRESS_VALUES.read_text())


# --- the probed port ----------------------------------------------------------

def test_the_predictor_is_scraped_on_the_port_that_was_probed(prom_values):
    """8082, not the 8080 KServe advertises on the pod — which 404s here."""
    # code_only, because the block ARGUES its own port at length and names the
    # wrong one four times while doing so — gotcha #53 for the sixth time, and
    # it caught this test on its first run.
    scrape = code_only(prom_values["extraScrapeConfigs"])
    assert ":8082" in scrape, (
        "the predictor scrape config no longer names port 8082. KServe's own pod "
        "annotation says 8080 and that port answers 404 on mlserver 1.7.1 — "
        "re-run `make probe-mlserver-metrics` before changing this."
    )
    assert ":8080" not in scrape


def test_the_probe_that_established_that_port_still_exists():
    """The measurement, not just its conclusion. A pinned port whose probe has
    been deleted is a remembered number (the CLAUDE.md pin-table discipline)."""
    assert PROBE.exists()
    text = PROBE.read_text()
    assert "8082" in text and "8080" in text, "the probe must try both ports"
    assert "probe-mlserver-metrics:" in MAKEFILE.read_text(), (
        "the probe must be reachable through the Makefile — the session "
        "allowlist can run `make` and cannot run an arbitrary script (F-001)"
    )


def test_the_predictor_job_discovers_by_label_not_by_name(prom_values):
    """M6-S3's shadow and M6-S4's canary must be scraped without editing this
    file. Discovery keyed on an isvc NAME would silently miss both."""
    scrape = prom_values["extraScrapeConfigs"]
    assert "serving_kserve_io_inferenceservice" in scrape
    assert "nyc-taxi-eta" not in scrape, (
        "the scrape config names a specific InferenceService — a second isvc "
        "(shadow at S3, canary at S4) would then be invisible."
    )


# --- what is on, what is off, and why ------------------------------------------

def test_the_footprint_choices_are_the_argued_ones(prom_values):
    assert prom_values["prometheus-node-exporter"]["enabled"] is False, (
        "node-exporter has no reader: container CPU and CFS throttling come from the "
        "kubelet's cAdvisor, which the chart already scrapes"
    )
    # ON from M7-S3. It was `enabled: false` through M6 with the note that one
    # value flips it when the drift metrics arrive; they have.
    assert prom_values["prometheus-pushgateway"]["enabled"] is True, (
        "the drift job is a batch process that is gone before any scrape interval "
        "elapses — M7-S3's metrics have nowhere to live without the gateway"
    )
    # ON from M8-S1 (F-050 (a)), and the argument it replaces is kept here because
    # it was true and was still the wrong call: "the contents are re-derivable by
    # re-running the drift job over DVC-pinned data, so a lost PVC costs one
    # command" — which leaves out WHO RUNS THE COMMAND. The pod dies on every host
    # restart (measured three times in 24h), and between the restart and somebody
    # noticing, A-10 cannot fire because `time() - max(X)` over zero series is
    # zero series. A one-command repair nobody is prompted to run is not a repair.
    gateway = prom_values["prometheus-pushgateway"]
    assert gateway["persistentVolume"]["enabled"] is True, (
        "F-050: an emptyDir gateway loses the whole drift surface on every pod restart, "
        "and the rule that exists to catch a missing drift number cannot see an absent one"
    )
    assert any("--persistence.file=" in arg for arg in gateway["extraArgs"]), (
        "a mounted volume with no --persistence.file is decoration: pushgateway keeps its "
        "metrics in memory unless one names a file, and the chart mounts the volume either way"
    )
    assert "serviceAnnotations" not in prom_values["prometheus-pushgateway"], (
        "annotating the gateway would get it scraped by the chart's generic "
        "kubernetes-service-endpoints job, which does NOT set honor_labels — the pushed "
        "`job` label would be overwritten and every drift rule would match nothing while "
        "sitting quietly inactive. It has its own job in extraScrapeConfigs."
    )
    assert prom_values["kube-state-metrics"]["enabled"] is True
    assert prom_values["alertmanager"]["enabled"] is True, (
        "M6-S2 must watch an alert fire; an alert with no receiver is a row in a UI"
    )


def test_the_alerting_rules_file_exists_so_s2_lands_alerts_not_plumbing(prom_values):
    assert "alerting_rules.yml" in prom_values["serverFiles"]


def test_the_scrape_interval_can_describe_a_one_minute_rate(prom_values):
    """A rate() over a 1m window at a 1m scrape interval evaluates to nothing.
    This bit — three board panels drew empty and read as 'idle'."""
    interval = prom_values["server"]["global"]["scrape_interval"]
    seconds = int(re.sub(r"[^0-9]", "", interval))
    assert interval.endswith("s") and seconds <= 30, (
        f"scrape_interval={interval}: the board's rate([1m]) windows need at "
        f"least two samples inside them"
    )


def test_the_service_endpoints_job_is_merged_not_copied(prom_values):
    """Only scalar/map keys — helm REPLACES lists, so a relabel_configs here
    would be a stale copy of the chart's at the next bump."""
    job = prom_values["scrapeConfigs"]["kubernetes-service-endpoints"]
    assert "relabel_configs" not in job
    assert job["tls_config"]["insecure_skip_verify"] is True
    assert job["bearer_token_file"].startswith("/var/run/secrets/")


# --- the route (M6 law 1) ------------------------------------------------------

def test_the_uis_ride_the_existing_ingress_and_ask_for_no_new_host_port(
    prom_values, grafana_values, deploy
):
    assert prom_values["server"]["ingress"]["enabled"] is True
    assert prom_values["server"]["ingress"]["hosts"] == ["prometheus.local"]
    assert grafana_values["ingress"]["enabled"] is True
    assert grafana_values["ingress"]["hosts"] == ["grafana.local"]
    for values in (prom_values, grafana_values):
        assert "hostPort" not in yaml.dump(values)
    assert "NodePort" not in code_only(deploy)
    # The kind config is read at cluster-CREATE only; a monitoring hostPort would
    # mean a rebuild, and the cluster's PVCs are the only copy of the registry.
    kind = KIND_CONFIG.read_text()
    for port in ("3000", "9091"):
        assert f"hostPort: {port}" not in kind


def test_the_deploy_never_edits_the_kind_config(deploy):
    assert "kind-config" not in code_only(deploy)


# --- secrets -------------------------------------------------------------------

def test_the_grafana_password_never_reaches_a_command_line(deploy, grafana_values):
    body = code_only(deploy)
    assert "--set" not in body, "a --set on a helm command is readable by `ps`"
    assert grafana_values["admin"]["existingSecret"] == "grafana-admin"
    assert "adminPassword" not in yaml.dump(grafana_values), (
        "the chart's adminPassword value would put the password in a values file"
    )


def test_the_secrets_script_converges_the_grafana_credential():
    text = SECRETS.read_text()
    assert "GRAFANA_ADMIN_PASSWORD" in text
    assert "apply_secret monitoring grafana-admin" in text
    for key in ("admin-user", "admin-password"):
        assert key in text, "the key names are the chart's, not ours"


def test_no_secret_value_is_echoed(deploy):
    for line in code_only(deploy).splitlines():
        assert "PASSWORD" not in line.upper() or "echo" not in line.lower()


# --- DRY_RUN (gotcha #30) ------------------------------------------------------

def test_dry_run_guards_every_mutation_including_helm(deploy):
    body = code_only(deploy)
    assert 'DRY_RUN="${DRY_RUN:-0}"' in body
    # Every helm invocation that changes the cluster goes through `run`, which is
    # the single place DRY_RUN is honoured.
    for line in body.splitlines():
        if "upgrade --install" in line:
            assert line.strip().startswith("run "), (
                f"a helm upgrade outside the DRY_RUN guard: {line.strip()}"
            )
    # …and the one place it delegates, it passes DRY_RUN through.
    assert 'DRY_RUN="$DRY_RUN" bash "$REPO_ROOT/scripts/deploy_serving.sh"' in body


def test_dry_run_exits_before_anything_is_read_back(deploy):
    body = code_only(deploy)
    assert body.index('if [[ "$DRY_RUN" == "1" ]]; then') < body.index("get pods")


# --- M6 law 3: nothing here knows the registry exists --------------------------

def test_the_monitoring_stack_cannot_touch_the_registry(deploy):
    body = code_only(deploy) + code_only(PROM_VALUES.read_text())
    for forbidden in ("champion", "models:/", "set_registered_model_alias",
                      "mlflow models"):
        assert forbidden not in body, (
            f"deploy_monitoring names {forbidden!r} — M6 law 3 says the eyes do "
            f"not touch the pointer"
        )


def test_the_accept_check_reads_the_model_and_writes_nothing():
    """It asks for one quote (a read). Any registry-MUTATING verb is a defect —
    asserted over the parsed code, never over the prose (gotcha #53)."""
    tree = ast.parse(ACCEPT.read_text())
    called = {
        node.func.attr for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    for verb in ("set_registered_model_alias", "delete_registered_model_alias",
                 "create_model_version", "transition_model_version_stage",
                 "delete_model_version"):
        assert verb not in called


# --- the ingress controller's forced strategy ----------------------------------

def test_the_ingress_controller_cannot_roll_and_says_so(ingress_values):
    """hostPort + replicaCount 1 + a single-node nodeSelector: the surge pod can
    never bind port 80, so RollingUpdate hangs until helm times out."""
    controller = ingress_values["controller"]
    assert controller["replicaCount"] == 1
    assert controller["hostPort"]["enabled"] is True
    assert controller["updateStrategy"]["type"] == "Recreate", (
        "RollingUpdate deadlocks here — observed: '1 node(s) didn't have free "
        "ports for the requested pod ports', new pod Pending for 10 minutes"
    )


def test_the_ingress_metrics_service_advertises_itself_for_scraping(ingress_values):
    """Without this annotation the chart's metrics Service exists and is never
    discovered — every target up, and the edge panel empty."""
    metrics = ingress_values["controller"]["metrics"]
    assert metrics["enabled"] is True
    annotations = metrics["service"]["annotations"]
    assert annotations["prometheus.io/scrape"] == "true"
    assert annotations["prometheus.io/port"] == "10254"


# --- the boards are checked in --------------------------------------------------

def test_every_dashboard_is_valid_json_with_a_stable_uid():
    files = sorted(DASHBOARDS.glob("*.json"))
    assert files, "the board is provisioned from these files; there are none"
    uids = set()
    for path in files:
        spec = json.loads(path.read_text())
        assert spec.get("uid"), f"{path.name} has no uid — provisioning needs one"
        assert spec["uid"] not in uids, f"duplicate dashboard uid {spec['uid']}"
        uids.add(spec["uid"])
        assert spec.get("panels"), f"{path.name} has no panels"


def test_every_panel_target_carries_a_promql_expression():
    for path in sorted(DASHBOARDS.glob("*.json")):
        spec = json.loads(path.read_text())
        for panel in spec["panels"]:
            if panel["type"] == "text":
                continue
            assert panel.get("targets"), f"panel {panel['id']} has no query"
            for target in panel["targets"]:
                assert target.get("expr", "").strip()
                assert target.get("refId")


def test_the_board_draws_no_threshold_line():
    """Thresholds are the SLO document's (M6-S2). A bar drawn here would be a bar
    set from the number just observed — gotchas #63/#74 in dashboard form."""
    for path in sorted(DASHBOARDS.glob("*.json")):
        spec = json.loads(path.read_text())
        for panel in spec["panels"]:
            defaults = panel.get("fieldConfig", {}).get("defaults", {})
            steps = defaults.get("thresholds", {}).get("steps", [])
            assert not [s for s in steps if s.get("value") is not None], (
                f"panel {panel['id']} draws a threshold before the SLO doc exists"
            )


def test_the_deploy_builds_the_dashboard_configmap_from_those_files(deploy):
    body = code_only(deploy)
    assert "analytics/grafana/dashboards" in DEPLOY.read_text()
    assert "--from-file=" in body
    assert "grafana_dashboard=1" in body
    assert "delete" not in body, (
        "the converge scripts in this repo never delete; destroying is "
        "`make destroy`'s job (the postgres_databases.sh asymmetry)"
    )


def test_grafana_provisions_the_datasource_rather_than_asking_for_a_click(
    grafana_values,
):
    ds = grafana_values["datasources"]["datasources.yaml"]["datasources"][0]
    assert ds["type"] == "prometheus"
    assert ds["url"].endswith(".svc.cluster.local"), (
        "the datasource must use the in-cluster name — a datasource that left "
        "the cluster to come back in would depend on the route it debugs"
    )
    assert grafana_values["sidecar"]["dashboards"]["enabled"] is True


def test_grafana_telemetry_is_off_in_both_places(grafana_values):
    ini = grafana_values["grafana.ini"]
    assert ini["analytics"]["reporting_enabled"] is False
    assert ini["analytics"]["check_for_updates"] is False


# --- the accept check is a measurement, not a target list ----------------------

def test_the_accept_check_sends_a_real_request_and_requires_the_counter_to_move():
    text = ACCEPT.read_text()
    assert '"make", "quote"' in text, "a target list is not evidence of a pipeline"
    assert "delta >= 1" in text


def test_an_empty_panel_is_a_failure_not_a_footnote():
    """The first draft printed '0 series' in green and hid three real defects."""
    text = ACCEPT.read_text()
    assert "renders an empty rectangle" in text
    tree = ast.parse(text)
    fails = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "fail"
    ]
    assert len(fails) >= 6, "the accept check must be able to say no in every leg"


def test_the_accept_check_derives_its_queries_from_the_checked_in_board():
    """F-017: a PromQL expression re-typed here would be the copy that stays
    right while the board rots."""
    text = ACCEPT.read_text()
    assert "DASHBOARD.read_text()" in text
    assert "rest_server_request_duration_seconds_bucket" not in text, (
        "a board query is hardcoded in the checker"
    )


# --- the outage instrument ------------------------------------------------------

def test_the_route_probe_anchors_an_outage_on_failure_to_success():
    """gotcha #75: last_error - first_error called a 13 s outage 182 s."""
    text = (REPO / "scripts" / "route_availability_probe.py").read_text()
    assert "first success AFTER the first failure" in text or \
           "first failure -> first success" in text
    tree = ast.parse(text)
    src = ast.dump(tree)
    assert "samples_raw" in text, "the raw per-sample log must survive the summary"
    assert src is not None


# --- the Makefile wiring --------------------------------------------------------

def test_the_targets_exist_and_the_accept_twin_is_separable():
    makefile = MAKEFILE.read_text()
    for target in ("deploy-monitoring:", "monitoring-accept:",
                   "probe-mlserver-metrics:"):
        assert target in makefile
    assert "TODO(M6)" not in makefile.split("deploy-monitoring:")[1].split("\n")[1]
