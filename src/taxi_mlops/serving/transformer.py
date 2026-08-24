"""The transformer: a RAW quote in, the champion's number out, the boundary moved.

M8-S4 leg 3. Until now every client of this program built the 24-column matrix
itself and sent the FEATURES over the wire — `make quote`, `make parity`,
`make load`, the M5 gate. That is a working system with an honest weakness: the
feature build lives in the caller, so "training and serving agree about what a
feature is" is a property of every caller separately. This process moves it
inside the cluster. A rider's request now carries what a rider knows — a time,
two zone ids, a party size — and the 24 features are derived in a pod, from the
same `taxi_mlops.features` code the trainer used, with the CENTROID and CALENDAR
reference data read out of the online feature store.

--------------------------------------------------------------------------
WHY THIS IS STDLIB AND NOT A FRAMEWORK
--------------------------------------------------------------------------
`http.server.ThreadingHTTPServer`, `urllib`, `json`. No FastAPI, no uvicorn, no
KServe SDK. Adding a web framework to serve one POST route at the 4 req/s the SLO
is written against would put three new packages into the project graph — and
gotcha #36 is this repo's record of what an unbounded `uv add` can quietly do to
a pinned numeric stack. `uv.lock` is byte-identical to the `m7-closed` tag at
this story's exit, as it has been at every M8 story's, and that is checkable.

--------------------------------------------------------------------------
THE WALL, AND WHERE IT IS
--------------------------------------------------------------------------
This runs in OUR image (pandas 3.0.5, `src/taxi_mlops`). feast 0.66.0 pins
`pandas<3`, so it cannot import Feast — and does not: `serving.feature_store`
speaks JSON to the quarantined feature server leg 2 deployed. Shape (i) of the
kickoff's three, and the only one under which the wall stays a wall.

--------------------------------------------------------------------------
ONE ENCODER, ONE DECODER, ONE MODULE
--------------------------------------------------------------------------
`encode_raw` (what a client sends) and `decode_raw` (what this server reads) are
deliberately in the same file. A client that encodes in one module and a server
that decodes in another are twins, and this repo has a standing lesson about
twins drifting (the port family, `MARTS=(...)`, the two spellings of a record
path). A round-trip test pins them together.

Requests are paired BY NAME, never by position — the V2 body names its inputs and
the champion's own signature taught this program the lesson twice already (the
lossy `float64 -> int32` refusal at M5-S2, and F-031's red team that went green
under its own tampering at M5-S3).

--------------------------------------------------------------------------
WHAT IT RETURNS, AND WHAT IT DOES NOT ADD
--------------------------------------------------------------------------
The predictor's V2 response, VERBATIM. Not re-serialised, not re-rounded, not
wrapped. So the number a caller reads is the number mlserver produced and
`model_version` is still the champion's registry version, stamped by the same
mechanism M5-S2 established — the version stamp survives the new boundary rather
than being re-asserted by this process.

What it adds is one RESPONSE HEADER, `X-Taxi-Lookups`, naming where each
reference group was actually read from. A transformer that silently fell back to
its committed CSVs would serve perfectly correct quotes and prove nothing at all
about the store, which is ADR-012's own named failure mode one layer along. The
header makes the claim falsifiable from outside the pod.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pandas as pd

from ..features import quote_time
from ..training.run import load_train_config
from .client import QuoteRefused, QuoteRequest, build_matrix, v2_payload
from .feature_store import DEFAULT_FEATURE_SERVER, FeatureServer, FeatureStoreUnavailable
from .feature_store import lookups_for as lookups_for_frame

#: The four raw inputs, their V2 datatypes, and the `QuoteRequest` field each
#: fills. This dict IS the request schema — `encode_raw` and `decode_raw` both
#: read it, so neither can grow a field the other does not know about.
RAW_INPUTS: dict[str, tuple[str, str]] = {
    "pickup_datetime": ("BYTES", "pickup_datetime"),
    "PULocationID": ("INT32", "pu_location_id"),
    "DOLocationID": ("INT32", "do_location_id"),
    "passenger_count": ("FP64", "passenger_count"),
}


def encode_raw(requests: list[QuoteRequest]) -> dict[str, Any]:
    """A batch of rider questions as a V2 body — four inputs, not twenty-four.

    Deliberately still the V2 shape rather than a bespoke JSON object: the URL
    path, the envelope and the response are all unchanged from the champion's own
    wire, so the ONLY difference a reader has to hold in their head is that the
    inputs are the request instead of the matrix.
    """
    if not requests:
        raise ValueError("no requests — a quote batch of zero rows has no meaning")
    rows = len(requests)
    inputs = []
    for name, (datatype, field) in RAW_INPUTS.items():
        values = [getattr(r, field) for r in requests]
        if name == "pickup_datetime":
            values = [str(v) for v in values]
        elif datatype == "INT32":
            values = [int(v) for v in values]
        else:
            values = [float(v) for v in values]
        inputs.append({"name": name, "shape": [rows, 1], "datatype": datatype, "data": values})
    return {"inputs": inputs}


def decode_raw(body: dict[str, Any]) -> list[QuoteRequest]:
    """A V2 body back into rider questions. BY NAME, and it refuses a partial one.

    An input the schema does not name is refused rather than ignored: a client
    sending `passengers` instead of `passenger_count` would otherwise get every
    row quoted at the default party size, which is a wrong number nobody can see
    is wrong. Same argument as Feast's join key answering 500 on an unrecognised
    name (`feature_store`, hazard 2) — except that here we get to make it loud.
    """
    inputs = body.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        raise QuoteRefused("the body carries no 'inputs' array")
    by_name = {}
    for entry in inputs:
        name = entry.get("name")
        if name in by_name:
            raise QuoteRefused(f"input {name!r} appears twice — which one is the request?")
        by_name[name] = entry
    unknown = sorted(set(by_name) - set(RAW_INPUTS))
    if unknown:
        raise QuoteRefused(
            f"unknown input(s) {unknown}. This endpoint takes a RAW quote request "
            f"({sorted(RAW_INPUTS)}), not a feature matrix — the champion's own host "
            "is where a pre-built matrix goes. Ignoring them would quote every row "
            "at a default this caller never asked for."
        )
    missing = sorted(set(RAW_INPUTS) - set(by_name))
    if missing:
        raise QuoteRefused(f"missing required input(s) {missing}")

    lengths = {len(by_name[name]["data"]) for name in RAW_INPUTS}
    if len(lengths) != 1:
        raise QuoteRefused(
            f"the inputs carry different row counts ({sorted(lengths)}) — a batch "
            "whose columns disagree about how many rows it has cannot be paired"
        )
    rows = lengths.pop()
    if rows == 0:
        raise QuoteRefused("a quote batch of zero rows has no meaning")
    return [
        QuoteRequest(
            pickup_datetime=str(by_name["pickup_datetime"]["data"][i]),
            pu_location_id=int(by_name["PULocationID"]["data"][i]),
            do_location_id=int(by_name["DOLocationID"]["data"][i]),
            passenger_count=float(by_name["passenger_count"]["data"][i]),
        )
        for i in range(rows)
    ]


@dataclass
class Transform:
    """The whole request path, with no HTTP in it, so it can be tested without a socket."""

    server: FeatureServer
    predictor_url: str
    features_cfg: dict[str, Any]
    timeout: float = 30.0

    def matrix(self, requests: list[QuoteRequest]) -> tuple[pd.DataFrame, dict[str, str]]:
        """Requests -> the champion's 24 columns, with the reference data NAMED.

        The store is consulted ONCE per batch for the distinct zones and the
        distinct dates, then the matrix is built through `client.build_matrix` —
        the same function `make quote` and `make parity` call, which is what makes
        "the transformer builds features the way training does" a structural fact
        rather than a promise. The only thing that differs is where two reference
        tables came from, and `Lookups.sources` reports it.
        """
        frame = pd.DataFrame([r.as_row() for r in requests])
        lookups = lookups_for_frame(self.server, frame)
        return build_matrix(requests, self.features_cfg, lookups=lookups), lookups.sources

    def predict(self, requests: list[QuoteRequest]) -> tuple[dict[str, Any], dict[str, str]]:
        matrix, sources = self.matrix(requests)
        payload = v2_payload(matrix, quote_time.feature_names(self.features_cfg))
        body = json.dumps(payload, allow_nan=False).encode()
        request = urllib.request.Request(  # noqa: S310 — a fixed in-cluster Service
            self.predictor_url, data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
            return json.loads(response.read()), sources


def _handler(transform: Transform, model_name: str) -> type[BaseHTTPRequestHandler]:
    infer_path = f"/v2/models/{model_name}/infer"
    ready_paths = {
        "/health",
        "/v2/health/ready",
        f"/v2/models/{model_name}",
        f"/v2/models/{model_name}/ready",
    }

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
            sys.stderr.write("[transformer] %s\n" % (fmt % args))

        def _send(self, status: int, payload: dict[str, Any], headers: dict[str, str]) -> None:
            body = json.dumps(payload, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path in ready_paths:
                self._send(200, {"name": model_name, "ready": True}, {})
                return
            self._send(404, {"error": f"no such path {self.path!r}"}, {})

        def do_POST(self) -> None:  # noqa: N802
            # THE BODY IS READ BEFORE ANY BRANCH, AND THAT ORDER IS LOAD-BEARING
            # (F-069). `protocol_version = "HTTP/1.1"` means keep-alive, so a
            # response sent while the request's body is still in the socket leaves
            # those bytes to be parsed as the NEXT request's request-line. The
            # 404-on-a-wrong-path branch below used to return without reading, and
            # ingress-nginx pools upstream connections — so the caller who was
            # PUNISHED was the next one, with a perfectly good request answered
            # `400 Bad request syntax` and its own body echoed back at it. Found
            # when this story's parity run followed the deploy accept's
            # ADR-011-condition-2 negative check onto the same pooled connection.
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            if self.path != infer_path:
                # The model name is in the PATH — ADR-011 condition 2's lesson.
                # A 404 here is the correct, loud answer; answering anyway would
                # make two differently-named endpoints indistinguishable.
                self._send(404, {"error": f"no such path {self.path!r}; try {infer_path}"}, {})
                return
            try:
                requests = decode_raw(json.loads(raw))
                response, sources = transform.predict(requests)
            except QuoteRefused as exc:
                # 422 and NOT 500: a refusal is the guard working. F-019's typed
                # refusal and the store's coverage refusal both land here, and
                # A-3 counts exactly this class per window (docs/slo_serving.md).
                self._send(getattr(exc, "http_status", 422), {"error": str(exc)}, {})
                return
            except FeatureStoreUnavailable as exc:
                # 503 and NOT 422: our dependency is down, the caller did nothing
                # wrong, and collapsing the two would make an outage look like a
                # malformed quote in every panel that splits 4xx from 5xx.
                self._send(503, {"error": str(exc)}, {})
                return
            except json.JSONDecodeError as exc:
                self._send(400, {"error": f"the body is not JSON: {exc}"}, {})
                return
            except Exception as exc:  # noqa: BLE001 — nothing may take the server down
                traceback.print_exc()
                self._send(500, {"error": f"{type(exc).__name__}: {exc}"}, {})
                return
            self._send(
                200,
                response,
                {"X-Taxi-Lookups": ",".join(f"{k}={v}" for k, v in sorted(sources.items()))},
            )

    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    # KServe appends `--model_name` and `--predictor_host` to a custom
    # transformer's args. They are accepted here AND readable from the
    # environment, and `parse_known_args` means an argument this program has
    # never heard of cannot stop the pod — a serving process that refuses to
    # start over an unrecognised flag is an outage caused by a platform upgrade.
    # What actually arrived is PRINTED, so the deploy record carries it rather
    # than this docstring guessing.
    parser.add_argument("--model_name", default=os.environ.get("MODEL_NAME", "nyc-taxi-eta"))
    parser.add_argument("--predictor_host", default=os.environ.get("PREDICTOR_HOST", ""))
    parser.add_argument(
        "--predictor_model_name", default=os.environ.get("PREDICTOR_MODEL_NAME", "")
    )
    parser.add_argument(
        "--feature_server", default=os.environ.get("FEATURE_SERVER_URL", DEFAULT_FEATURE_SERVER)
    )
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080")))
    args, extra = parser.parse_known_args(argv)
    if extra:
        print(f"[transformer] arguments this program does not read: {extra}", flush=True)

    if not args.predictor_host:
        print(
            "[transformer] FAIL: no predictor host. PREDICTOR_HOST is unset and KServe "
            "passed no --predictor_host. Refusing to start rather than defaulting to "
            "something: a default would send every quote to the wrong model, or to "
            "nothing, and answer 503 in a way that looks like a cold start.",
            file=sys.stderr,
        )
        return 2

    predictor_model = args.predictor_model_name or args.model_name
    host = args.predictor_host
    if "://" not in host:
        host = f"http://{host}"
    predictor_url = f"{host}/v2/models/{predictor_model}/infer"

    cfg = load_train_config()["features"]
    transform = Transform(
        server=FeatureServer(url=args.feature_server),
        predictor_url=predictor_url,
        features_cfg=cfg,
    )
    print(f"[transformer] model            {args.model_name}", flush=True)
    print(f"[transformer] predictor        {predictor_url}", flush=True)
    print(f"[transformer] feature server   {args.feature_server}", flush=True)
    print(
        f"[transformer] features          {len(quote_time.feature_names(cfg))} "
        f"(set {load_train_config()['features'].get('version', '?')})",
        flush=True,
    )
    server = ThreadingHTTPServer(("0.0.0.0", args.port), _handler(transform, args.model_name))  # noqa: S104
    print(f"[transformer] listening on 0.0.0.0:{args.port}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
