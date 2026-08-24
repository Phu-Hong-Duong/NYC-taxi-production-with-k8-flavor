"""The transformer's laws — M8-S4 leg 3.

The load-bearing test here is `test_a_store_backed_matrix_equals_the_committed_one`:
with a fake store that answers exactly what the committed tables hold, the
transformer's 24 columns must be BIT-IDENTICAL to what `make quote` builds today.
That is the offline half of the story's headline measurement, and having it in
unit form means the on-cluster parity is confirming a property rather than
discovering one.

The rest are refusals. Every one of them exists because the alternative failure is
silent: an ignored input quotes a default nobody asked for, a null calendar flag
decays the feature into a constant (F-019), and a store outage that presented as a
malformed request would be counted in the wrong half of every 4xx/5xx panel.
"""

from __future__ import annotations

import ast
import http.client
import json
import sys
import threading
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from taxi_mlops.features import calendar as calendar_mod  # noqa: E402
from taxi_mlops.features import zones as zones_mod  # noqa: E402
from taxi_mlops.serving import feature_store as fs  # noqa: E402
from taxi_mlops.serving import transformer as tf  # noqa: E402
from taxi_mlops.serving.client import QuoteRefused, build_matrix  # noqa: E402
from taxi_mlops.serving.parity import HAZARDS  # noqa: E402

pytestmark = pytest.mark.unit

REQUESTS = [h.request for h in HAZARDS]


class FakeServer(fs.FeatureServer):
    """A feature server that answers out of the COMMITTED tables.

    Deliberately not a recorded fixture of real responses: the question this
    fake is built to answer is *does the seam wire the values through
    unchanged?*, and the only way to make that a test about the SEAM rather than
    about a captured payload is to have both sides read the same source. The
    on-cluster parity is what asks whether the real store agrees — that is a
    different question and it needs a real store.
    """

    def __init__(self, *, blank_dates: tuple[str, ...] = (), empty: bool = False) -> None:
        super().__init__(url="http://fake")
        self.blank_dates = blank_dates
        #: `empty=True` is the store M9-S2's drill produced with `FLUSHDB`: it is
        #: REACHABLE and answers every question with `null`. That is the case
        #: F-062 is about — indistinguishable, byte for byte, from a date past
        #: the horizon unless a second question is asked.
        self.empty = empty
        self.calls: list[tuple[list[str], dict]] = []

    def get(self, features, entities):  # type: ignore[override]
        self.calls.append((list(features), dict(entities)))
        names = [f.split(":", 1)[1] for f in features]
        if self.empty:
            width = len(next(iter(entities.values())))
            return {name: [None] * width for name in names}
        if fs.ZONE_KEY in entities:
            table = zones_mod.load_zone_table()
            out: dict[str, list] = {name: [] for name in names}
            for zone_id in entities[fs.ZONE_KEY]:
                has = not bool(np.isnan(table.lat[zone_id]))
                for name in names:
                    if not has:
                        out[name].append(None)  # the store has no row at all
                    elif name == "centroid_lat":
                        out[name].append(float(table.lat[zone_id]))
                    elif name == "centroid_lon":
                        out[name].append(float(table.lon[zone_id]))
                    else:  # pragma: no cover — F-059 forbids asking for more
                        raise AssertionError(f"unexpected zone feature {name!r}")
            return out
        keys = entities[fs.DATE_KEY]
        flags = calendar_mod.flags(pd.Series([pd.Timestamp(k) for k in keys]))
        return {
            name: [
                None if keys[i] in self.blank_dates else bool(flags[name][i])
                for i in range(len(keys))
            ]
            for name in names
        }


# ------------------------------------------------------------------ the codec --
def test_encode_decode_round_trips_every_declared_hazard() -> None:
    assert tf.decode_raw(tf.encode_raw(REQUESTS)) == REQUESTS


def test_the_encoder_and_the_decoder_read_one_schema() -> None:
    """They are twins otherwise, and this repo has a standing lesson about twins."""
    body = tf.encode_raw(REQUESTS)
    assert sorted(i["name"] for i in body["inputs"]) == sorted(tf.RAW_INPUTS)
    assert all(i["shape"] == [len(REQUESTS), 1] for i in body["inputs"])


@pytest.mark.parametrize(
    "mutate, needle",
    [
        (lambda b: b["inputs"].append({"name": "passengers", "data": [1]}), "unknown input"),
        (lambda b: b["inputs"].pop(0), "missing required input"),
        (lambda b: b["inputs"][0]["data"].pop(), "different row counts"),
    ],
)
def test_the_decoder_refuses_rather_than_ignores(mutate, needle: str) -> None:
    """An ignored input quotes every row at a default the caller never asked for."""
    body = tf.encode_raw(REQUESTS)
    mutate(body)
    with pytest.raises(QuoteRefused, match=needle):
        tf.decode_raw(body)


def test_the_decoder_refuses_an_empty_batch() -> None:
    with pytest.raises(QuoteRefused):
        tf.decode_raw({"inputs": []})


# ------------------------------------------------------------------ the store --
def test_the_store_backed_zone_table_keeps_the_committed_borough_dictionary() -> None:
    """F-059, from the store side: the codes may not be re-derived per request."""
    committed = zones_mod.load_zone_table()
    stored = fs.zone_table_from_store(FakeServer(), [132, 48, 264, 265])
    assert stored.boroughs == committed.boroughs
    assert np.array_equal(stored.borough_code, committed.borough_code)


def test_the_store_backed_zone_table_leaves_the_non_places_missing() -> None:
    """264/265 have no row on either side — the same fallback, reached the same way."""
    stored = fs.zone_table_from_store(FakeServer(), [132, 264, 265])
    assert not np.isnan(stored.lat[132])
    assert np.isnan(stored.lat[264]) and np.isnan(stored.lat[265])


def test_only_the_two_permitted_zone_columns_are_ever_requested() -> None:
    """`is_airport` and `borough` live in the same view and must not be asked for."""
    server = FakeServer()
    fs.zone_table_from_store(server, [132, 48])
    asked = server.calls[0][0]
    assert asked == ["zone_static:centroid_lat", "zone_static:centroid_lon"]


def test_the_calendar_refuses_a_date_the_store_cannot_answer() -> None:
    """F-019's guarantee is a property of the DEPLOYMENT, not of the CSV.

    And, since F-062, it is a 422 only once the store has been SHOWN to be
    answering — here by the sentinel probe, which is the second call.
    """
    server = FakeServer(blank_dates=("2019-07-04",))
    with pytest.raises(fs.StoreCoverageError) as caught:
        fs.calendar_from_store(server, [pd.Timestamp("2019-07-04T09:15:00")])
    assert caught.value.http_status == 422
    assert "2019-07-04" in str(caught.value)
    assert len(server.calls) == 2, "the failure path must ask the liveness question"
    assert server.calls[1][1][fs.DATE_KEY] == [fs._liveness_sentinel()]


# ------------------------------------------------- F-062: whose failure is it? --
def test_a_wholly_dead_calendar_is_ours_and_not_the_callers() -> None:
    """The finding, in one assertion: an EMPTY store is a 503, never a 422.

    Before this landed, an emptied store answered `null` for every date and the
    caller got the 422 an uncovered date earns — so a totally dead dependency
    spent ZERO of SLO-A1's availability budget and rendered as riders sending bad
    requests (F-062, measured by `make store-watch-drill`'s empty phase).
    """
    server = FakeServer(empty=True)
    with pytest.raises(fs.FeatureStoreUnavailable) as caught:
        fs.calendar_from_store(server, [pd.Timestamp("2019-07-04T09:15:00")])
    # The class is the status: `FeatureStoreUnavailable` is deliberately NOT a
    # `QuoteRefused`, which is what the transformer's two except-blocks read.
    assert not isinstance(caught.value, QuoteRefused)
    assert "sentinel" in str(caught.value) and "F-062" in str(caught.value)


def test_the_liveness_sentinel_is_derived_from_the_committed_table() -> None:
    """A typed date would be a second definition of the store's own horizon.

    The store's `calendar_day_flags` view is built as
    `date_range(f"{years[0]}-01-01", …)` over this same table, so the sentinel is
    the twin of that expression's LEFT edge — the earliest covered day, chosen
    because the far end is where a legitimate horizon extension leaves a store one
    materialization behind.
    """
    years = sorted(calendar_mod.load_calendar().years)
    assert fs._liveness_sentinel() == f"{years[0]}-01-01"
    assert pd.Timestamp(fs._liveness_sentinel()).year in years


def test_the_discriminator_costs_the_happy_path_and_a_partial_batch_nothing() -> None:
    """The probe runs on the failure path only, and not even always there.

    A batch in which ANY date answered has already proved the store is alive, so
    no second call is made — which matters because the p50 of the moved boundary
    is a measured number (`automation/runs/m8-transformer/transformer-load.json`)
    and a probe on the happy path would move it.
    """
    happy = FakeServer()
    fs.calendar_from_store(happy, [pd.Timestamp("2019-07-04")])
    assert len(happy.calls) == 1

    partial = FakeServer(blank_dates=("2019-07-05",))
    with pytest.raises(fs.StoreCoverageError):
        fs.calendar_from_store(partial, [pd.Timestamp("2019-07-04"), pd.Timestamp("2019-07-05")])
    assert len(partial.calls) == 1, "a batch with a live witness needs no sentinel"


def test_the_calendar_does_not_fetch_a_flag_our_code_derives() -> None:
    """`is_business_day` is `weekday & not-holiday` and that arithmetic stays here."""
    server = FakeServer()
    fs.calendar_from_store(server, [pd.Timestamp("2019-07-04")])
    assert server.calls[0][0] == [
        "calendar_day_flags:is_holiday",
        "calendar_day_flags:is_near_holiday",
    ]


def test_an_unreachable_store_is_its_own_error_class() -> None:
    """503 vs 422: an outage must not be counted as a malformed request."""
    with pytest.raises(fs.FeatureStoreUnavailable):
        fs.FeatureServer(url="http://127.0.0.1:1", timeout=0.25).get(["a:b"], {"k": ["v"]})
    assert not issubclass(fs.FeatureStoreUnavailable, QuoteRefused)


# ------------------------------------------------------------- the whole path --
def test_a_store_backed_matrix_equals_the_committed_one() -> None:
    """THE property. Bit-identical, every column, every declared hazard.

    Not "close": the reference values are the same float64s, the arithmetic is
    the same function, and the dtypes are cast in the same place. A difference
    here would be a defect in the seam, not a tolerance to widen — which is the
    same sentence `docs/transformer_m8.md` §3 argues for the on-cluster bar.
    """
    transform = tf.Transform(
        server=FakeServer(), predictor_url="http://unused", features_cfg=_features_cfg()
    )
    stored, sources = transform.matrix(REQUESTS)
    assert stored.equals(build_matrix(REQUESTS, _features_cfg()))
    assert sources["centroids"] == "feature-store"
    assert sources["calendar"] == "feature-store"


def test_the_store_is_consulted_once_per_batch_not_once_per_row() -> None:
    """16 hazards, 23 distinct zones, 15 distinct dates -> two calls."""
    server = FakeServer()
    tf.Transform(server=server, predictor_url="http://x", features_cfg=_features_cfg()).matrix(
        REQUESTS
    )
    assert len(server.calls) == 2


def test_the_transformer_moves_no_alias_and_loads_no_model() -> None:
    """It is a request path, not a deploy. AST, never grep (#53/#68/#99)."""
    source = (REPO / "src" / "taxi_mlops" / "serving" / "transformer.py").read_text()
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
        "log_model",
    }
    assert not (called & forbidden)


# --------------------------------------------------------- F-069: the socket --
def test_a_404_does_not_poison_the_next_request_on_the_same_connection() -> None:
    """The body must be READ before any branch answers — keep-alive is the reason.

    `protocol_version = "HTTP/1.1"`, so a response sent while the request's body
    is still unread in the socket leaves those bytes to be parsed as the NEXT
    request's request-line. The victim is the next caller, whose perfectly good
    request comes back `400 Bad request syntax` with its own body echoed at it —
    and ingress-nginx pools upstream connections, so "the next caller" is a
    different client entirely. Observed live: the deploy accept's
    ADR-011-condition-2 negative check (a POST to the champion's model name, 404)
    followed immediately by this story's parity run, over one pooled connection.

    The second request is deliberately a coverage REFUSAL (**422**) and not a
    malformed body: a malformed body is a legitimate **400**, which is the same
    status a poisoned connection produces, so it could not tell the two apart.
    It needs no predictor — the refusal is raised while the lookups are built.
    """
    from http.server import ThreadingHTTPServer

    blank = REQUESTS[0].pickup_datetime[:10]
    handler = tf._handler(
        tf.Transform(
            server=FakeServer(blank_dates=(blank,)),
            predictor_url="http://127.0.0.1:1",
            features_cfg=_features_cfg(),
        ),
        "nyc-taxi-eta",
    )
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection(*httpd.server_address, timeout=5)
        conn.request(
            "POST",
            "/v2/models/somebody-elses-name/infer",
            body=json.dumps(tf.encode_raw(REQUESTS[:1])),
            headers={"Content-Type": "application/json"},
        )
        first = conn.getresponse()
        first.read()
        assert first.status == 404

        conn.request(
            "POST",
            "/v2/models/nyc-taxi-eta/infer",
            body=json.dumps(tf.encode_raw(REQUESTS[:1])),
            headers={"Content-Type": "application/json"},
        )
        second = conn.getresponse()
        payload = second.read()
        assert second.status == 422, (
            "the second request on the same connection was answered "
            f"{second.status} ({payload!r}) — the 404 above left its body in "
            "the socket (F-069)"
        )
        conn.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _features_cfg() -> dict:
    from taxi_mlops.training.run import load_train_config

    return load_train_config()["features"]
