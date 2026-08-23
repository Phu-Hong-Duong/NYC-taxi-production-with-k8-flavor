"""The demo's accept check: real requests, sent the way the PAGE sends them.

M9-S1. Gotcha #59, once more: assert on the artifact the thing exists to
produce. A deployed page and a Ready pod prove a process is listening; only a
NUMBER, obtained the way a browser obtains it, proves that a stakeholder opening
`http://localhost:8081/demo/` gets a live quote from the model that is serving.

WHAT MAKES THIS THE PAGE'S OWN REQUEST PATH RATHER THAN A LOOK-ALIKE
--------------------------------------------------------------------
Everything about the request is READ OUT OF `demo/index.html`:

* the endpoint      — the `ENDPOINT` constant the page's `fetch()` uses,
* the request schema — the `RAW_INPUTS` array the page encodes with,
* the payload        — the `DEFAULT_TRIP` the form opens on,

and the request is sent to the same origin with **no Host header override**,
which is the one thing a browser cannot do and every other client in this repo
does. A check that retyped any of the three would be measuring a second client
that happens to resemble the page — and the failure it could not see is the
interesting one: a page whose schema drifted from the server's.

The one thing that is NOT read from the page is the expected ANSWER. That comes
from `automation/runs/m8-transformer/transformer-parity.json`, matched on
`(at, pu, do)` — a tracked record measured by a different script through a
different route. Reading the expected value from the artifact under test is how a
comparison passes for any behaviour at all.

WHAT THIS SCRIPT DOES NOT DO
----------------------------
It does not import mlflow, resolve an alias, deploy anything, or write to the
cluster. The model version it reports is the one **mlserver stamped on the
answer** — the wire's own truth, forwarded verbatim through the transformer since
M8-S4 leg 3 — not a claim read from a registry and asserted about a response.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
PAGE = REPO / "demo" / "index.html"
ANCHOR_RECORD = REPO / "automation" / "runs" / "m8-transformer" / "transformer-parity.json"
DEFAULT_RECORD = REPO / "automation" / "runs" / "m9-demo" / "accept.json"
ROUTE = "http://localhost:8081"
PAGE_PATH = "/demo/"

#: Beyond the committed federal-holiday table's 2030 horizon (F-019). The page
#: advertises this in its own footer: the horizon is a feature to demo.
PAST_HORIZON_YEAR = 2031

#: An unclaimed path on the SAME origin. The route's rule is `Exact`, so this
#: must 404 — and it is only asserted after a real quote has succeeded, because
#: a 404 from an unloaded route and a 404 from an unclaimed path are the same
#: bytes (F-060, gotcha #106).
UNCLAIMED_PATH = "/v2/models/nyc-taxi-eta-transformer/infer"


class PageParseError(RuntimeError):
    """The page no longer carries a constant this check reads out of it."""


def _const(page: str, name: str) -> str:
    """The literal assigned to a top-level `const NAME = …;` in the page's script."""
    match = re.search(rf"^const {name} = (.*?);$", page, re.MULTILINE | re.DOTALL)
    if not match:
        raise PageParseError(
            f"demo/index.html has no `const {name} = …;` — this check reads the page's "
            "own request path out of the page, so a rename here must fail loudly rather "
            "than let the check quietly measure something it typed itself."
        )
    return match.group(1)


def read_page_contract(page: str) -> tuple[str, list[dict[str, str]], dict[str, Any]]:
    endpoint = json.loads(_const(page, "ENDPOINT"))
    schema = json.loads(_const(page, "RAW_INPUTS"))
    trip = json.loads(_const(page, "DEFAULT_TRIP"))
    return endpoint, schema, trip


def encode(schema: list[dict[str, str]], trip: dict[str, Any]) -> dict[str, Any]:
    """The page's `encodeRaw`, in Python. One row, paired BY NAME, shape [1, 1]."""
    inputs = []
    for spec in schema:
        raw = trip[spec["field"]]
        if spec["datatype"] == "BYTES":
            datum: Any = str(raw)
        elif spec["datatype"] == "INT32":
            datum = int(raw)
        else:
            datum = float(raw)
        inputs.append(
            {"name": spec["name"], "shape": [1, 1], "datatype": spec["datatype"], "data": [datum]}
        )
    return {"inputs": inputs}


def post(url: str, body: dict[str, Any], timeout: float = 60.0) -> tuple[int, Any, dict[str, str]]:
    """A same-origin POST with NO Host override — what the browser actually does."""
    request = urllib.request.Request(  # noqa: S310 — a fixed localhost route
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.status, json.loads(response.read()), dict(response.headers)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload: Any = json.loads(raw)
        except ValueError:
            payload = {"raw": raw.decode(errors="replace")[:400]}
        return exc.code, payload, dict(exc.headers or {})


def get(url: str, timeout: float = 30.0) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def anchor_for(trip: dict[str, Any]) -> dict[str, Any]:
    """The recorded row for the page's own default trip, matched on (at, pu, do)."""
    record = json.loads(ANCHOR_RECORD.read_text())
    for row in record["rows"]:
        if (
            row["at"] == trip["pickup_datetime"]
            and row["pu"] == trip["pu_location_id"]
            and row["do"] == trip["do_location_id"]
        ):
            return {
                "record": str(ANCHOR_RECORD.relative_to(REPO)),
                "hazard": row["hazard"],
                "minutes": row["transformer_minutes"],
                "model_version": record["model_version"]["transformer"],
                "lookup_sources": record["lookup_sources"],
            }
    raise SystemExit(
        f"[demo-accept] FAIL: the page's default trip {trip} matches no row in "
        f"{ANCHOR_RECORD.relative_to(REPO)}. The demo's opening quote is meant to be a "
        "number this repo has already published; if the default moved, move it to a row "
        "that is recorded, or record the new one first."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route", default=ROUTE)
    parser.add_argument("--record", default=str(DEFAULT_RECORD))
    parser.add_argument(
        "--no-write", action="store_true", help="print the verdicts, record nothing"
    )
    args = parser.parse_args()

    page_text = PAGE.read_text()
    endpoint, schema, trip = read_page_contract(page_text)
    anchor = anchor_for(trip)
    checks: list[tuple[bool, str]] = []
    record: dict[str, Any] = {
        "route": args.route,
        "page_url": args.route + PAGE_PATH,
        "endpoint": endpoint,
        "endpoint_read_from": "demo/index.html (the page's own ENDPOINT constant)",
        "default_trip": trip,
        "anchor": anchor,
    }

    # ---- 1. the page a browser receives is the page in git --------------------
    status, body = get(args.route + PAGE_PATH)
    served_sha = hashlib.sha256(body).hexdigest()
    committed_sha = hashlib.sha256(PAGE.read_bytes()).hexdigest()
    record["page"] = {
        "http_status": status,
        "served_sha256": served_sha,
        "committed_sha256": committed_sha,
        "bytes": len(body),
    }
    checks.append(
        (
            status == 200 and served_sha == committed_sha,
            f"the page a browser receives is byte-identical to demo/index.html "
            f"(HTTP {status}, {len(body)} bytes, sha256 {served_sha[:16]}…)",
        )
    )

    # ---- 2. the default trip, through the page's own request path -------------
    payload = encode(schema, trip)
    status, answer, headers = post(args.route + endpoint, payload)
    minutes = None
    version = None
    if status == 200 and isinstance(answer, dict) and answer.get("outputs"):
        minutes = float(answer["outputs"][0]["data"][0])
        version = answer.get("model_version")
    delta = None if minutes is None else abs(minutes - anchor["minutes"])
    record["quote"] = {
        "http_status": status,
        "request": payload,
        "minutes": minutes,
        "model_version": version,
        "abs_delta_minutes": delta,
        "bar": "EXACT — argued in demo/README.md §4 before this record existed",
    }
    checks.append(
        (
            status == 200 and minutes is not None,
            f"a live quote came back: HTTP {status}, "
            + (f"{minutes:.4f} minutes" if minutes is not None else f"no number ({answer})"),
        )
    )
    checks.append(
        (
            delta == 0.0,
            f"it reproduces the recorded {anchor['hazard']} row EXACTLY: "
            f"{minutes!r} vs {anchor['minutes']!r} (|delta| = "
            + (f"{delta:.3e}" if delta is not None else "n/a")
            + f"), anchor {anchor['record']}",
        )
    )
    checks.append(
        (
            version is not None and version == anchor["model_version"],
            f"the serving model version is stamped on the ANSWER: {version!r} "
            f"(recorded {anchor['model_version']!r}) — mlserver's own stamp, forwarded",
        )
    )

    # ---- 3. the store was consulted THROUGH THIS PATH -------------------------
    lookups = headers.get("X-Taxi-Lookups")
    record["quote"]["lookups"] = lookups
    checks.append(
        (
            lookups == anchor["lookup_sources"],
            f"X-Taxi-Lookups on the demo's own response: {lookups!r} "
            f"(recorded {anchor['lookup_sources']!r}) — the feature store was consulted "
            "and F-059's two committed groups did not cross",
        )
    )

    # ---- 4. the 2031 refusal renders as a refusal -----------------------------
    horizon_trip = dict(trip)
    horizon_trip["pickup_datetime"] = re.sub(
        r"^\d{4}", str(PAST_HORIZON_YEAR), str(trip["pickup_datetime"])
    )
    status, refused, _ = post(args.route + endpoint, encode(schema, horizon_trip))
    text = refused.get("error", "") if isinstance(refused, dict) else str(refused)
    record["refusal"] = {
        "pickup_datetime": horizon_trip["pickup_datetime"],
        "http_status": status,
        "error": text,
    }
    checks.append(
        (
            status == 422 and str(PAST_HORIZON_YEAR) in text,
            f"a {PAST_HORIZON_YEAR} quote is REFUSED, not guessed: HTTP {status}, "
            f"and the text names the date — {text[:150]!r}",
        )
    )

    # ---- 5. the no-geometry path answers, honestly ----------------------------
    # 264/265 are TLC bookkeeping and carry no centroid (DR-04 condition 1). The
    # pickers render them; quoting one must produce a NUMBER from the features
    # that remain, not an error — F-030's class, and the reason the page shows
    # them at all rather than pretending the world is tidy.
    unknown_trip = dict(trip)
    unknown_trip["pu_location_id"] = 264
    unknown_trip["do_location_id"] = 264
    status, unknown, unknown_headers = post(args.route + endpoint, encode(schema, unknown_trip))
    unknown_minutes = (
        float(unknown["outputs"][0]["data"][0])
        if status == 200 and isinstance(unknown, dict) and unknown.get("outputs")
        else None
    )
    record["no_geometry"] = {
        "trip": unknown_trip,
        "http_status": status,
        "minutes": unknown_minutes,
        "lookups": unknown_headers.get("X-Taxi-Lookups"),
    }
    checks.append(
        (
            status == 200 and unknown_minutes is not None,
            "the no-geometry path (zone 264 -> 264, TLC's 'Unknown') is QUOTED, not "
            f"broken: HTTP {status}, "
            + (
                f"{unknown_minutes:.4f} minutes"
                if unknown_minutes is not None
                else f"no number ({unknown})"
            ),
        )
    )

    # ---- 6. the negative, and it is conditional on the positive ---------------
    quote_succeeded = record["quote"]["minutes"] is not None
    status, _ = get(args.route + UNCLAIMED_PATH)
    record["unclaimed_path"] = {"path": UNCLAIMED_PATH, "http_status": status}
    checks.append(
        (
            quote_succeeded and status == 404,
            f"an unclaimed V2 path on the same origin 404s ({UNCLAIMED_PATH} -> {status}) "
            "— asserted only because a real quote succeeded first, since an unloaded "
            "route 404s identically (F-060)",
        )
    )

    # ---- 7. the invariants the demo's route shares a server block with --------
    health, _ = get(args.route + "/healthz")
    root, _ = get(args.route + "/")
    record["route_invariants"] = {"healthz": health, "root": root}
    checks.append(
        (
            health == 200 and root == 404,
            f"the host-less rule left deploy_serving.sh's accept standing: "
            f"/healthz -> {health}, / -> {root}",
        )
    )

    for ok, line in checks:
        print(f"[demo-accept] {'ok  ' if ok else 'FAIL'} {line}")
    failures = [line for ok, line in checks if not ok]
    record["checks"] = [{"ok": ok, "claim": line} for ok, line in checks]
    record["failures"] = failures
    record["verdict"] = "PASSED" if not failures else "FAILED"
    record["po_observed_run"] = {
        "status": "OPEN — cannot be closed by an unattended session",
        "box": (
            "BLUEPRINT §9/M9: one non-technical person (the PO counts) completes a "
            "query unassisted, observed"
        ),
        "url": args.route + PAGE_PATH,
        "raised_in": "AWAITING_PO.md",
    }

    if not args.no_write:
        out = Path(args.record)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        print(f"[demo-accept] recorded {out.relative_to(REPO)}")

    if failures:
        print(f"[demo-accept] FAILED — {len(failures)} check(s)")
        return 1
    print(f"[demo-accept] PASSED — {len(checks)}/{len(checks)} checks")
    print(f"[demo-accept] the PO-observed box stays OPEN by design: {args.route + PAGE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
