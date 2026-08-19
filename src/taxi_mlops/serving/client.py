"""The quote client: a typed request, the ONE feature path, the live endpoint.

M5-S2. This is the only thing in the repo that turns *what a rider asks* — a
pickup time, two zones, a party size — into *what the wire carries*. Three
properties it exists to hold, each of which has a failure mode with no other
symptom:

1. **Features are built by `taxi_mlops.features`, never here.** The predictor
   behind KServe eats the 24-column matrix the champion was fitted on; something
   has to build it, and if that something is not the training path then
   train/serve skew is a matter of luck. `build_features` is imported, not
   reimplemented, so a change to a feature changes both sides in one commit.
   M5-S3's parity test measures what this guarantees; it does not create it.

2. **The column ORDER is the model's, not the config's** — and what that buys is
   narrower than this file used to claim. The paragraph here said the V2 body is
   POSITIONAL, so a reordering would silently swap `PULocationID` for
   `DOLocationID`. **M5-S3's red team measured that and it is false for this
   runtime**: rotating the order of the inputs changed the answer by exactly
   0.000e+00 on all 16 hazard rows. mlserver hands MLflow a NAMED frame and the
   logged signature reorders it by name, so on this deployment the wire order is
   not load-bearing. The order still comes from `quote_time.feature_names(cfg)`,
   the same call the trainer made, for two reasons that survive the correction:
   a runtime that pairs positionally is a legal V2 implementation and M7's
   transformer may be one, and sending the model's own order costs nothing. What
   is NOT true is that this ordering is the thing standing between us and a
   mispaired feature — the signature is, and it is the second time in this
   milestone that the signature has caught what nothing else would have.

3. **An uncovered date is REFUSED, in a type, and never guessed.** See below.

--------------------------------------------------------------------------
F-019 AND WHAT WAS DECIDED (M5-S2, with the runbook in hand)
--------------------------------------------------------------------------
The champion eats `is_holiday`/`is_near_holiday`/`is_business_day`, which come
from a committed table that held ten rows, all 2019. `features/calendar.py`
raises on an uncovered year — right for training, and from M5 it is a 500 on
every quote dated outside the table.

**Decided: BOTH halves, because each alone is unshippable.**

- The table was EXTENDED to 2030 from the statute
  (`scripts/derive_us_federal_holidays.py`, and its 2019 rows re-derive byte for
  byte, so nothing any milestone measured moves). Extending alone is not a fix:
  a table always ends, and the day it ends the failure is exactly the one we set
  out to remove — only later, and to somebody who was not told it could happen.
- The boundary is TYPED here. An uncovered date raises `UncoveredDateError`, a
  `QuoteRefused` carrying `http_status = 422`, before a request is built and
  before anything reaches the wire.

**Refuse, not degrade-and-flag.** The two options differ in KIND, which is why
the SRE half is minuted in M5-S5's PRR rather than settled by taste: degrading
returns a WRONG QUOTE — the caller gets a number, the rider gets a time, and
nothing in the system knows the holiday flags were invented. Refusing is a
visible, countable, alertable outage confined to the dates nobody has entered
yet. A quote-time ETA has one job and it is to be a number somebody can rely on;
a silently-wrong one is worse than none, and it is the failure mode the calendar
module's own raise was written to prevent. The flag would also have to be
carried through the V2 payload, the response and every consumer to be worth
anything, and a flag nobody reads is a degradation with a comment on it.

**Where this boundary lives, honestly.** In M5 the features are built
client-side, so the refusal happens here and the "422" is a property of this
type rather than of an HTTP response the cluster emits. M7's KServe transformer
moves feature building into the pod; `http_status` is carried now so that move
is a change of transport and not a change of contract.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from ..features import calendar as calendar_mod
from ..features import quote_time
from ..training.run import load_train_config

#: The Host header KServe's generated Ingress matches on, built from the
#: InferenceService name and namespace by the domainTemplate in
#: infra/helm/kserve/values.yaml. Requests reach the declared route by NAME, so
#: this string is part of the contract between the deploy and every curl.
DEFAULT_HOST_TEMPLATE = "{name}-{namespace}.local"
DEFAULT_ROUTE = "http://localhost:8081"


class QuoteRefused(RuntimeError):
    """A request this system declines to answer, with the status it would return.

    A refusal is a first-class outcome and not an error in the model: the caller
    asked something outside what the deployed champion can honestly answer.
    """

    http_status = 400


class UncoveredDateError(QuoteRefused):
    """F-019: the pickup date is outside the committed holiday table's years."""

    http_status = 422


@dataclass(frozen=True)
class QuoteRequest:
    """What a rider's question carries at quote time, and nothing else.

    Deliberately the four columns `configs/features.yaml`'s `base` set names as
    request-time inputs. Anything a trip only has AFTER it happens is refused by
    `quote_time.EXCLUSIONS` upstream of here — this type simply has nowhere to
    put it.
    """

    pickup_datetime: str
    pu_location_id: int
    do_location_id: int
    passenger_count: float = 1.0

    def as_row(self) -> dict[str, Any]:
        return {
            quote_time.PICKUP_TIMESTAMP: pd.Timestamp(self.pickup_datetime),
            "PULocationID": int(self.pu_location_id),
            "DOLocationID": int(self.do_location_id),
            "passenger_count": float(self.passenger_count),
        }


def request_frame(requests: list[QuoteRequest]) -> pd.DataFrame:
    """The raw quote frame `build_features` eats. No feature logic lives here."""
    if not requests:
        raise ValueError("no requests — a quote batch of zero rows has no meaning")
    return pd.DataFrame([r.as_row() for r in requests])


def build_matrix(
    requests: list[QuoteRequest], features_cfg: dict[str, Any] | None = None
) -> pd.DataFrame:
    """Requests -> the champion's feature matrix, through the ONE transform path.

    The only thing added on top of `build_features` is F-019's typed refusal: the
    calendar's `ValueError` is caught HERE and re-raised as a `QuoteRefused`, so a
    caller can tell "you asked for a date I do not cover" (422, the request's
    fault, fixable by `make holidays`) from "the model is broken" (500). The
    underlying raise is left exactly as it is — it is still the guard that keeps
    training honest, and this is a translation, not a softening.
    """
    cfg = features_cfg if features_cfg is not None else load_train_config()["features"]
    frame = request_frame(requests)
    try:
        return quote_time.build_features(frame, cfg)
    except ValueError as exc:
        if calendar_mod.HOLIDAY_TABLE in str(exc):
            years = sorted(pd.DatetimeIndex(frame[quote_time.PICKUP_TIMESTAMP]).year.unique())
            raise UncoveredDateError(
                f"this deployment cannot quote for {years}: "
                f"{calendar_mod.HOLIDAY_TABLE} covers through "
                f"{sorted(calendar_mod.load_calendar().years)[-1]}, and the "
                "champion eats holiday flags. REFUSED rather than guessed — a "
                "quote built on invented holiday flags is a wrong number nobody "
                "can see is wrong (F-019). Extend the table: `make holidays "
                f"HOLIDAYS_TO={max(years)}`."
            ) from exc
        raise


#: numpy dtype -> Open Inference (V2) datatype. The map is deliberately narrow:
#: these are the only dtypes `quote_time.build_features` produces, and an
#: unlisted one should stop the request rather than be coerced into something
#: that looks close enough.
_V2_DATATYPES = {
    "int8": "INT8",
    "int16": "INT16",
    "int32": "INT32",
    "int64": "INT64",
    "float32": "FP32",
    "float64": "FP64",
}


def _wire_values(column: pd.Series) -> list[Any]:
    """A column's values as JSON can carry them — and NaN is the hard case.

    **F-030 (M5-S3): the missing-geometry path could not be quoted at all.**
    Zones 264/265 are TLC's "Unknown" and carry no centroid, so
    `quote_time.build_features` produces NaN for all nine geometry columns and
    `has_geometry = 0` — the named fallback DR-04 condition 1 requires, and
    LightGBM's documented missing-value path. `np.asarray(col).tolist()` turns
    those into Python `float('nan')`, and `json.dumps` writes them as the bare
    token `NaN`, which **is not JSON**. The endpoint answered:

        HTTP 422 {"type":"json_invalid","loc":["body",1241],
                  "msg":"JSON decode error","ctx":{"error":"unexpected character"}}

    — a parser refusing a malformed document, i.e. an error that names neither
    the feature nor the zone nor the word NaN. 264->264 is the largest single OD
    "route" in this data (409,128 trips) and the no-geometry share is ~1.0-1.2%
    of every split, so this was not an exotic corner: it was a whole class of
    rider the deployed system returned a parse error for.

    JSON has one spelling for "no value" and it is `null`; mlserver decodes it
    into the tensor as NaN, which is exactly what the booster was fitted to
    treat as missing. Measured, not assumed — M5-S3's parity run scores these
    rows offline against the endpoint and prints the delta.

    An INFINITY is refused rather than encoded. It is equally unrepresentable in
    JSON, but it is not a missing value: nothing in `quote_time` can produce one,
    so an inf here means a feature is broken and mapping it to `null` would
    launder a defect into a plausible quote.
    """
    values = np.asarray(column)
    if not np.issubdtype(values.dtype, np.floating):
        return values.tolist()
    finite = np.isfinite(values)
    if bool((~finite & ~np.isnan(values)).any()):
        raise ValueError(
            f"feature {column.name!r} contains an infinity, which JSON cannot carry and "
            "which no quote-time feature can legitimately produce. Refusing to send it: "
            "encoding it as null would present a broken feature to the model as a "
            "missing one."
        )
    return [None if np.isnan(v) else float(v) for v in values.tolist()]


def v2_payload(matrix: pd.DataFrame, feature_names: list[str]) -> dict[str, Any]:
    """The Open Inference (V2) request body: one input per feature, named + typed.

    **THE WIRE CARRIES THE MATRIX'S OWN DTYPES, and that is not a detail.** The
    first version of this function sent `FP64` for everything, on the reasoning
    that LightGBM predicts on a float matrix regardless. The endpoint answered
    500:

        Failed to enforce schema … Error: Incompatible input types for column
        hour. Can not safely convert float64 to int32.

    MLflow enforces the signature the model was LOGGED with, and it refuses a
    lossy cast — `float64 -> int32` is one, because nothing in the payload proves
    9.0 was ever an integer. That refusal is the model's signature doing its job,
    so the fix is to stop lying about the types rather than to strip the
    signature: `hour` is `int16` in the matrix the trainer built, so `INT16` is
    what the wire says. Sending the real dtypes also removes a float32 -> float64
    -> float32 round trip from the geometry columns, which is one fewer place for
    M5-S3's 1e-6 to have to survive.
    """
    missing = [name for name in feature_names if name not in matrix.columns]
    if missing:
        raise ValueError(f"the matrix is missing {missing} — it cannot be sent positionally")
    rows = len(matrix)
    inputs = []
    for name in feature_names:
        column = matrix[name]
        datatype = _V2_DATATYPES.get(str(column.dtype))
        if datatype is None:
            raise ValueError(
                f"feature {name!r} has dtype {column.dtype}, which this client has no "
                f"V2 datatype for (known: {sorted(set(_V2_DATATYPES.values()))}). "
                "Guessing one would send the model a column it was not fitted on."
            )
        inputs.append(
            {
                "name": name,
                "shape": [rows, 1],
                "datatype": datatype,
                "data": _wire_values(column),
            }
        )
    return {"inputs": inputs}


@dataclass(frozen=True)
class Endpoint:
    """Where the InferenceService answers, and under which Host header."""

    name: str
    namespace: str
    route: str = DEFAULT_ROUTE

    @property
    def host(self) -> str:
        return DEFAULT_HOST_TEMPLATE.format(name=self.name, namespace=self.namespace)

    @property
    def infer_url(self) -> str:
        return f"{self.route}/v2/models/{self.name}/infer"

    @property
    def ready_url(self) -> str:
        return f"{self.route}/v2/models/{self.name}/ready"

    @property
    def metadata_url(self) -> str:
        return f"{self.route}/v2/models/{self.name}"


def _post(url: str, host: str, body: dict[str, Any], timeout: float) -> dict[str, Any]:
    # `allow_nan=False` is the guard, not the encoding: `_wire_values` has already
    # turned every missing value into `null`, and this makes the failure mode of a
    # future path that forgets to a LOUD ValueError here rather than a 422 from the
    # server about an "unexpected character" at byte 1241 (F-030). Python's json
    # emits the non-standard tokens NaN/Infinity by DEFAULT; that default is what
    # let malformed bodies leave this process for a whole milestone.
    data = json.dumps(body, allow_nan=False).encode()
    request = urllib.request.Request(  # noqa: S310 — a fixed http:// route, not user input
        url, data=data, headers={"Content-Type": "application/json", "Host": host}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read())


def _get(url: str, host: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Host": host})  # noqa: S310
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read() or b"{}")


def served_version(endpoint: Endpoint, *, timeout: float = 30.0) -> dict[str, Any]:
    """What the endpoint says it is serving — asked of the server, not remembered."""
    return _get(endpoint.metadata_url, endpoint.host, timeout)


def infer_matrix(
    matrix: pd.DataFrame,
    feature_names: list[str],
    endpoint: Endpoint,
    *,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Send an ALREADY-BUILT matrix and return the endpoint's whole answer.

    M5-S3 needs this: parity scores ONE matrix twice, so that the delta it
    measures is the model + the runtime + the wire, and not two feature builds
    that could differ. `infer` below is this function plus the feature build, so
    there is still exactly one place that turns a matrix into a request body.
    """
    try:
        return _post(endpoint.infer_url, endpoint.host, v2_payload(matrix, feature_names), timeout)
    except urllib.error.HTTPError as exc:  # pragma: no cover — needs a live endpoint
        body = exc.read().decode(errors="replace")[:500]
        raise RuntimeError(
            f"the endpoint answered {exc.code} for {endpoint.infer_url} "
            f"(Host: {endpoint.host}): {body}"
        ) from exc


def infer(
    requests: list[QuoteRequest],
    endpoint: Endpoint,
    *,
    features_cfg: dict[str, Any] | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """The endpoint's WHOLE answer, not just the numbers.

    Callers want the numbers; the response also carries `model_name` and
    `model_version`, and those are the answer to "which model produced THIS
    prediction?" — stamped by the server on the very response being read, rather
    than fetched from a metadata call that could describe a different moment.
    """
    cfg = features_cfg if features_cfg is not None else load_train_config()["features"]
    names = quote_time.feature_names(cfg)
    matrix = build_matrix(requests, cfg)
    return infer_matrix(matrix, names, endpoint, timeout=timeout)


def minutes_of(response: dict[str, Any]) -> np.ndarray:
    """The predicted minutes out of a V2 response."""
    outputs = response.get("outputs") or []
    if not outputs:
        raise RuntimeError(f"the endpoint returned no outputs: {json.dumps(response)[:500]}")
    return np.asarray(outputs[0]["data"], dtype="float64")


def predict(
    requests: list[QuoteRequest],
    endpoint: Endpoint,
    *,
    features_cfg: dict[str, Any] | None = None,
    timeout: float = 60.0,
) -> np.ndarray:
    """Quote requests -> minutes, off the live endpoint. Raises on a refusal."""
    return minutes_of(infer(requests, endpoint, features_cfg=features_cfg, timeout=timeout))
