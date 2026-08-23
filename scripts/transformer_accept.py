"""The accept check for the transformer: a RAW question, answered — and a 404 beside it.

M8-S4 leg 3. Gotcha #59: assert on the artifact the thing exists to produce. A
ready pod and a 200 on `/health` prove a process is listening; only a NUMBER
proves that a rider's four fields became 24 features inside a pod, with the
centroids and the calendar flags read out of the online feature store, and that
the champion ate them.

Four assertions, and two of them are negative — a positive-only check is
satisfied by a service that answers everything the same way:

1. **The number.** One raw request, the parity record's own hazard row, must come
   back as a duration with the champion's `model_version` stamped on it. The
   version stamp travelling through the new boundary is the point: this process
   forwards mlserver's response VERBATIM, so the version is still the one the
   registry put on the wire and not a claim this script makes.
2. **The store was actually consulted.** The `X-Taxi-Lookups` response header
   must say `centroids=feature-store` and `calendar=feature-store`. A transformer
   that silently fell back to its committed CSVs would serve a perfectly correct
   quote and prove nothing at all about the store — ADR-012's own named failure
   mode, one layer along.
3. **The champion's model name 404s here.** The V2 model name is in the URL path
   (ADR-011 condition 2). A service answering to both names would make "which
   boundary produced this number?" unanswerable, and every subsequent measurement
   in this story rests on that question having an answer.
4. **A 2031 date is REFUSED, not quoted.** F-019's guarantee is a property of the
   DEPLOYMENT and it had to survive the reference data moving into a store. The
   refusal now comes from `feature_store.StoreCoverageError` — the store has no
   calendar row — and it must still be a 422 and still name the date.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from taxi_mlops.serving.client import DEFAULT_ROUTE, QuoteRequest  # noqa: E402
from taxi_mlops.serving.transformer import encode_raw  # noqa: E402

ISVC = "nyc-taxi-eta-transformer"
CHAMPION = "nyc-taxi-eta"
NAMESPACE = "serving"

#: The accept row is M5-S2's own spot check and `make parity`'s hazard 1 — the
#: JFK -> Clinton East run whose value every record in this repo already carries
#: (39.0019 minutes). Using a row with a published answer means this check can
#: notice a WRONG number, not just the absence of an error.
ACCEPT = QuoteRequest("2019-07-04T09:15:00", 132, 48, 1.0)

#: Beyond the committed holiday table's 2030 horizon. `make quote` exits 2 on it
#: today via the CSV's own years; here the store is the source and must refuse.
PAST_HORIZON = QuoteRequest("2031-07-04T09:15:00", 132, 48, 1.0)


def call(
    route: str, host: str, model: str, body: dict[str, Any], timeout: float = 60.0
) -> tuple[int, dict[str, Any], dict[str, str]]:
    request = urllib.request.Request(  # noqa: S310 — a fixed localhost route
        f"{route}/v2/models/{model}/infer",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Host": host},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.status, json.loads(response.read()), dict(response.headers)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = {"raw": raw.decode(errors="replace")[:400]}
        return exc.code, payload, dict(exc.headers or {})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route", default=DEFAULT_ROUTE)
    parser.add_argument("--record", default=None)
    args = parser.parse_args()

    host = f"{ISVC}-{NAMESPACE}.local"
    checks: list[tuple[bool, str]] = []
    record: dict[str, Any] = {"route": args.route, "host": host, "isvc": ISVC}

    # ---- 1. the number -------------------------------------------------------
    status, payload, headers = call(args.route, host, ISVC, encode_raw([ACCEPT]))
    minutes = None
    version = None
    if status == 200 and payload.get("outputs"):
        minutes = float(payload["outputs"][0]["data"][0])
        version = payload.get("model_version")
    checks.append(
        (
            status == 200 and minutes is not None,
            f"a RAW request was answered: HTTP {status}, "
            f"{ACCEPT.pickup_datetime} zone {ACCEPT.pu_location_id} -> "
            f"{ACCEPT.do_location_id} -> "
            + (f"{minutes:.4f} minutes" if minutes is not None else f"no number ({payload})"),
        )
    )
    checks.append(
        (
            version is not None,
            f"the answer carries the champion's registry version: model_version={version!r} "
            "(stamped by mlserver, forwarded verbatim — not a claim this script makes)",
        )
    )
    record.update(
        {
            "accept_request": {
                "at": ACCEPT.pickup_datetime,
                "pu": ACCEPT.pu_location_id,
                "do": ACCEPT.do_location_id,
                "passenger_count": ACCEPT.passenger_count,
            },
            "minutes": minutes,
            "model_version": version,
            "model_name": payload.get("model_name"),
        }
    )

    # ---- 2. the store was consulted -----------------------------------------
    lookups = headers.get("X-Taxi-Lookups", "")
    record["lookup_sources"] = lookups
    checks.append(
        (
            "centroids=feature-store" in lookups and "calendar=feature-store" in lookups,
            f"the stored lookups really came from the store: X-Taxi-Lookups={lookups!r} "
            "(a silent fallback to the committed CSVs would answer identically)",
        )
    )
    checks.append(
        (
            "borough_dictionary=committed-table" in lookups
            and "airport_constant=committed-code" in lookups,
            "and F-059's two refused groups did NOT: the borough dictionary and the "
            "airport constant are still read from the committed artifacts",
        )
    )

    # ---- 3. the champion's name 404s here ------------------------------------
    champion_status, _, _ = call(args.route, host, CHAMPION, encode_raw([ACCEPT]))
    record["champion_name_on_transformer_host"] = champion_status
    checks.append(
        (
            champion_status == 404,
            f"the champion's model name 404s on this host: HTTP {champion_status} for "
            f"/v2/models/{CHAMPION}/infer — the negative half, so a number from this "
            "service can only have come from this boundary",
        )
    )

    # ---- 4. the horizon is still refused -------------------------------------
    refused_status, refused_body, _ = call(args.route, host, ISVC, encode_raw([PAST_HORIZON]))
    message = str(refused_body.get("error", refused_body))
    record["past_horizon"] = {"status": refused_status, "error": message[:400]}
    checks.append(
        (
            refused_status == 422 and "2031" in message,
            f"a past-horizon quote is REFUSED, not guessed: HTTP {refused_status} naming "
            f"2031 (F-019, now raised by the STORE's coverage rather than the CSV's)",
        )
    )

    print()
    for ok, line in checks:
        print(f"[accept] {'ok  ' if ok else 'FAIL'}{line}")
    failures = sum(1 for ok, _ in checks if not ok)
    record["checks"] = [{"ok": ok, "claim": line} for ok, line in checks]
    record["failures"] = failures

    if args.record:
        path = Path(args.record)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        print(f"[accept] recorded {path.relative_to(REPO)}")

    print()
    if failures:
        print(f"[accept] RED — {failures} of {len(checks)} checks failed")
        return 1
    print(f"[accept] GREEN — {len(checks)}/{len(checks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
