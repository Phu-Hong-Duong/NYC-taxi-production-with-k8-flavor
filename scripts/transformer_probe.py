"""Can this thing work at all? — the cheap probe in front of a build and a KServe deploy.

M8-S4 leg 3. `make transformer-probe` runs the transformer's whole request path
IN THIS PROCESS, on the host, against the two real services it will depend on:
the quarantined feature server and the champion's own predictor, each reached by
an ephemeral `kubectl port-forward`. Roughly a minute, against ~7 minutes of image
build plus a KServe deploy this repo's history prices at 2-3 defects each (F-036,
F-037, F-038, F-039).

This is the M4-S4 `DRILL_STAGE=ingest` idiom, and leg 2 is the reason it is here:
its 30-second `feast-serve-probe` decided the shape by measurement, and the first
defect the build then hit was a missing execute bit rather than a question about
Feast. A probe's yield is usually not the thing it was pointed at.

**WHAT IT EXERCISES:** the store client, the `lookups` seam, `build_matrix`, the
V2 payload, and mlserver. **WHAT IT DOES NOT:** KServe's transformer wiring, the
Ingress, and the pod's own environment — which is exactly what the deploy is for,
and why a green probe is not an accept check.

It POSTs to the CHAMPION'S OWN PREDICTOR through a port-forward, which is a read:
no alias is moved, nothing is deployed, and the champion's own route is not
touched. The forwarded port is 8086 and not 80 for the same reason the store's is
6380 and the feature server's is 6567 — a probe that borrows a service's
conventional port is a probe that can end up talking to something else.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from taxi_mlops.serving.client import QuoteRequest, build_matrix, v2_payload  # noqa: E402
from taxi_mlops.serving.feature_store import FeatureServer  # noqa: E402
from taxi_mlops.serving.parity import HAZARDS  # noqa: E402
from taxi_mlops.serving.transformer import Transform  # noqa: E402
from taxi_mlops.training.run import load_train_config  # noqa: E402


def forward(namespace: str, service: str, local: int, remote: int) -> subprocess.Popen:
    return subprocess.Popen(  # noqa: S603
        ["kubectl", "-n", namespace, "port-forward", f"svc/{service}", f"{local}:{remote}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_for(url: str, seconds: int = 40) -> bool:
    for _ in range(seconds):
        try:
            with urllib.request.urlopen(url, timeout=2):  # noqa: S310
                return True
        except urllib.error.HTTPError:
            return True  # it answered; the status is not what is under test
        except (urllib.error.URLError, OSError):
            time.sleep(1)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-port", type=int, default=6567)
    parser.add_argument("--predictor-port", type=int, default=8086)
    parser.add_argument("--rows", type=int, default=len(HAZARDS))
    args = parser.parse_args()

    forwards = [
        forward("feast", "feast-server", args.feature_port, 6566),
        forward("serving", "nyc-taxi-eta-predictor", args.predictor_port, 80),
    ]
    try:
        feature_url = f"http://127.0.0.1:{args.feature_port}"
        predictor = f"http://127.0.0.1:{args.predictor_port}"
        if not wait_for(f"{feature_url}/health"):
            print("[probe] FAIL: the feature server never answered — is it deployed?")
            return 1
        if not wait_for(f"{predictor}/v2/models/nyc-taxi-eta"):
            print("[probe] FAIL: the champion's predictor never answered")
            return 1
        print(f"[probe] feature server {feature_url}")
        print(f"[probe] predictor      {predictor}  (the champion's own, read-only)")

        cfg = load_train_config()["features"]
        requests = [h.request for h in HAZARDS][: args.rows]
        transform = Transform(
            server=FeatureServer(url=feature_url),
            predictor_url=f"{predictor}/v2/models/nyc-taxi-eta/infer",
            features_cfg=cfg,
        )

        # ---- the matrix, both ways. This is the parity's own question asked
        # before a pod exists: same rows, same code, reference data from two
        # different places.
        stored, sources = transform.matrix(requests)
        committed = build_matrix(requests, cfg)
        identical = stored.equals(committed)
        print(f"[probe] lookups        {json.dumps(sources)}")
        print(
            f"[probe] matrix         {stored.shape[0]} rows x {stored.shape[1]} columns; "
            f"store-backed == committed: {identical}"
        )
        if not identical:
            differing = [c for c in committed.columns if not stored[c].equals(committed[c])]
            print(f"[probe] FAIL: these columns differ: {differing}")
            return 1

        # ---- the number, both ways.
        response, _ = transform.predict(requests)
        theirs = [float(v) for v in response["outputs"][0]["data"]]
        body = json.dumps(v2_payload(committed, list(committed.columns)), allow_nan=False).encode()
        request = urllib.request.Request(  # noqa: S310 — the forward
            f"{predictor}/v2/models/nyc-taxi-eta/infer",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=60) as raw:  # noqa: S310
            ours = [float(v) for v in json.loads(raw.read())["outputs"][0]["data"]]

        worst = max(abs(a - b) for a, b in zip(theirs, ours, strict=True))
        print(f"[probe] version        {response.get('model_version')!r}")
        print(
            f"[probe] first row      {theirs[0]:.6f} minutes (store) "
            f"vs {ours[0]:.6f} (committed)"
        )
        print(f"[probe] max |delta|    {worst:.3e} over {len(theirs)} declared hazards")
        if worst != 0.0:
            print("[probe] FAIL: the two boundaries disagree before a pod even exists")
            return 1

        # The refusal, because a probe that only proves the happy path leaves the
        # expensive discovery for the deploy.
        try:
            transform.matrix([QuoteRequest("2031-07-04T09:15:00", 132, 48, 1.0)])
        except Exception as exc:  # noqa: BLE001
            print(f"[probe] refusal        {type(exc).__name__}: {str(exc)[:90]}…")
        else:
            print("[probe] FAIL: a 2031 quote was NOT refused (F-019)")
            return 1

        print()
        print("[probe] GREEN — everything except KServe's own wiring works. Build the image.")
        return 0
    finally:
        for handle in forwards:
            handle.terminate()
            handle.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
