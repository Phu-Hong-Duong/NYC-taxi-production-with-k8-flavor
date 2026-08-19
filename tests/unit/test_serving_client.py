"""M5-S2: the quote client's cluster-free half.

What is testable without an endpoint is the set of things that are wrong in a
file rather than wrong in a pod — and every one below either cost this story a
red run or would have gone unnoticed until a wrong number reached a rider:

* **the wire's dtypes.** The first payload sent `FP64` for all 24 features and
  the endpoint answered 500: MLflow enforces the logged signature and refuses
  `float64 -> int32` as lossy. That refusal is the signature working; the fix was
  to stop lying about the types. A regression here is a 500 on every quote.
* **the feature ORDER and the feature PATH.** A V2 payload is a list, so a
  reordering swaps `PULocationID` for `DOLocationID` and returns a plausible
  number. And if this module ever built a feature itself, train/serve skew would
  become a matter of luck rather than of construction.
* **F-019's refusal is typed, and it is a TRANSLATION.** The calendar's raise
  must still be a raise; this module turns it into something a caller can act on
  (422, "your date", fixable) instead of something that reads as "the model is
  broken" (500).
* **the Host header.** KServe builds it from a domainTemplate in a values file
  three directories away. Nothing at runtime complains when the two drift — the
  ingress simply returns 404 and it looks like the model failed to deploy.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest
import yaml

from taxi_mlops.features import calendar, quote_time
from taxi_mlops.serving import client
from taxi_mlops.training.run import load_train_config

REPO = Path(__file__).resolve().parents[2]
CLIENT_SOURCE = REPO / "src" / "taxi_mlops" / "serving" / "client.py"
KSERVE_VALUES = REPO / "infra" / "helm" / "kserve" / "values.yaml"
ISVC_MANIFEST = REPO / "infra" / "manifests" / "inferenceservice-champion.yaml"

pytestmark = pytest.mark.unit

COVERED = "2019-07-04T09:15:00"


@pytest.fixture(scope="module")
def features_cfg() -> dict:
    return load_train_config()["features"]


@pytest.fixture(scope="module")
def one_request() -> list[client.QuoteRequest]:
    return [client.QuoteRequest(pickup_datetime=COVERED, pu_location_id=132, do_location_id=48)]


# --------------------------------------------------------------------------
# The wire carries the model's types
# --------------------------------------------------------------------------


def test_the_payload_carries_each_column_s_own_dtype(one_request, features_cfg):
    """The regression for this story's 500. `hour` is int16 in the matrix the
    trainer built, so the wire must say INT16 — not FP64, which MLflow correctly
    refuses to cast back down."""
    matrix = client.build_matrix(one_request, features_cfg)
    payload = client.v2_payload(matrix, quote_time.feature_names(features_cfg))
    by_name = {entry["name"]: entry for entry in payload["inputs"]}

    for name, entry in by_name.items():
        expected = client._V2_DATATYPES[str(matrix[name].dtype)]
        assert entry["datatype"] == expected, f"{name} went on the wire as {entry['datatype']}"

    # And the two families are genuinely different, so the test would notice a
    # regression to one-dtype-for-everything.
    assert by_name["hour"]["datatype"] == "INT16"
    assert by_name["centroid_haversine_km"]["datatype"] == "FP32"
    assert len({entry["datatype"] for entry in payload["inputs"]}) > 1


def test_an_unknown_dtype_stops_the_request_rather_than_being_coerced(features_cfg):
    matrix = pd.DataFrame({"hour": pd.Series(["09"], dtype="object")})
    with pytest.raises(ValueError) as excinfo:
        client.v2_payload(matrix, ["hour"])
    assert "V2 datatype" in str(excinfo.value)


def test_the_payload_is_in_the_model_s_feature_order(one_request, features_cfg):
    names = quote_time.feature_names(features_cfg)
    payload = client.v2_payload(client.build_matrix(one_request, features_cfg), names)
    assert [entry["name"] for entry in payload["inputs"]] == names


def test_a_matrix_missing_a_feature_is_refused(features_cfg):
    matrix = pd.DataFrame({"hour": pd.Series([9], dtype="int16")})
    with pytest.raises(ValueError) as excinfo:
        client.v2_payload(matrix, ["hour", "dayofweek"])
    assert "dayofweek" in str(excinfo.value)


# --------------------------------------------------------------------------
# The ONE transform path
# --------------------------------------------------------------------------


def test_the_client_builds_features_by_CALLING_the_training_path(features_cfg):
    """Structural, not behavioural: a reimplementation that happened to agree
    today would pass any numeric check and diverge on the next feature change.
    So the assertion is that `quote_time.build_features` is INVOKED (gotcha #53 —
    in a repo where prose is load-bearing, a check about code parses code)."""
    tree = ast.parse(CLIENT_SOURCE.read_text())
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "build_features" in called
    assert "feature_names" in called


def test_the_matrix_the_client_builds_is_the_champion_s_columns(one_request, features_cfg):
    matrix = client.build_matrix(one_request, features_cfg)
    assert list(matrix.columns) == quote_time.feature_names(features_cfg)
    assert len(matrix) == 1


# --------------------------------------------------------------------------
# F-019's typed boundary
# --------------------------------------------------------------------------


def test_a_date_past_the_table_is_refused_with_a_422_naming_the_fix(features_cfg):
    beyond = max(calendar.load_calendar().years) + 1
    request = [
        client.QuoteRequest(
            pickup_datetime=f"{beyond}-03-05T09:15:00", pu_location_id=132, do_location_id=48
        )
    ]
    with pytest.raises(client.UncoveredDateError) as excinfo:
        client.build_matrix(request, features_cfg)

    refusal = excinfo.value
    assert refusal.http_status == 422
    assert isinstance(refusal, client.QuoteRefused)
    message = str(refusal)
    assert calendar.HOLIDAY_TABLE in message, "the refusal must name the file to edit"
    assert str(beyond) in message, "the refusal must say what was asked for"
    assert "make holidays" in message, "a refusal that does not name its fix is an outage"
    # A TRANSLATION, not a softening: the calendar's own raise is still what
    # produced it.
    assert isinstance(refusal.__cause__, ValueError)


def test_a_date_inside_the_table_builds_the_whole_matrix(one_request, features_cfg):
    """The companion that proves the refusal above is about the DATE and not
    about some other defect in the request."""
    matrix = client.build_matrix(one_request, features_cfg)
    assert not matrix.isna().all().any()


def test_a_non_calendar_value_error_is_not_dressed_up_as_a_refusal(features_cfg):
    """`build_matrix` must only translate the calendar's raise. Anything else is
    a defect and must keep its own type, or a bug in the feature path would be
    reported to callers as 'your date is out of range'."""
    with pytest.raises(ValueError) as excinfo:
        client.build_matrix(
            [client.QuoteRequest(pickup_datetime=COVERED, pu_location_id=132, do_location_id=48)],
            {**features_cfg, "temporal": [*features_cfg["temporal"], "not_a_feature"]},
        )
    assert not isinstance(excinfo.value, client.QuoteRefused)


def test_an_empty_batch_is_refused():
    with pytest.raises(ValueError):
        client.request_frame([])


# --------------------------------------------------------------------------
# The route: twins across three files
# --------------------------------------------------------------------------


def test_the_host_header_matches_kserve_s_domain_template():
    """KServe stamps the Ingress host from `domainTemplate` + `domain`. If this
    client's template drifts, every request 404s at the ingress and it looks
    exactly like a model that failed to deploy."""
    values = yaml.safe_load(KSERVE_VALUES.read_text())
    gateway = values["kserve"]["controller"]["gateway"]
    rendered = (
        gateway["domainTemplate"]
        .replace("{{ .Name }}", "{name}")
        .replace("{{ .Namespace }}", "{namespace}")
        .replace("{{ .IngressDomain }}", gateway["domain"])
    )
    assert rendered == client.DEFAULT_HOST_TEMPLATE

    endpoint = client.Endpoint(name="nyc-taxi-eta", namespace="serving")
    assert endpoint.host == "nyc-taxi-eta-serving.local"
    assert endpoint.infer_url.endswith("/v2/models/nyc-taxi-eta/infer")


def test_the_default_endpoint_names_the_committed_inferenceservice():
    manifest = yaml.safe_load(ISVC_MANIFEST.read_text())
    endpoint = client.Endpoint(
        name=manifest["metadata"]["name"], namespace=manifest["metadata"]["namespace"]
    )
    assert endpoint.host == "nyc-taxi-eta-serving.local"


def test_the_declared_route_port_is_the_one_the_kind_config_publishes():
    kind_config = yaml.safe_load((REPO / "infra" / "kind" / "kind-config.yaml").read_text())
    published = [
        mapping["hostPort"]
        for node in kind_config["nodes"]
        for mapping in node.get("extraPortMappings", [])
        if mapping["containerPort"] == 80
    ]
    assert f"http://localhost:{published[0]}" == client.DEFAULT_ROUTE


# --------------------------------------------------------------------------
# It reads; it never promotes
# --------------------------------------------------------------------------


def test_the_client_touches_no_registry_api():
    """M5 law 2: serving reads the pointer and never moves it. The client does
    not reach the registry at all — the deploy resolves the alias once, in one
    place, and hands the answer over as a storageUri."""
    source = CLIENT_SOURCE.read_text()
    tree = ast.parse(source)
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    forbidden = {
        "set_registered_model_alias",
        "delete_registered_model_alias",
        "create_model_version",
        "transition_model_version_stage",
        "register_model",
    }
    assert not (called & forbidden)
