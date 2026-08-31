#!/usr/bin/env python3
"""ADR-004's spike, MEASURED: does ingress-nginx give this program a traffic split? (M6-S3)

ADR-004 deferred one question — "what mechanism gives this program canary and
shadow?" — to a timeboxed spike whose pre-approved budget is ONE serving
re-deploy. This is that spike, and it is a script rather than a paragraph
because the question is empirical: KServe RawDeployment GENERATES an Ingress per
InferenceService and owns it, so whether a hand-authored second Ingress can
share the champion's host is a fact about this cluster, not about documentation.

--------------------------------------------------------------------------
THE PREDICTION IS WRITTEN TO DISK BEFORE ANYTHING IS APPLIED
--------------------------------------------------------------------------
The M4-S5 / M5-S4 / M6-S2 discipline, third milestone running. A probe that
decides what it expected after seeing the answer has measured nothing.

**Two of the first run's predictions were WRONG, and they are the most valuable
output of this story.** They are kept below under `superseded_predictions`,
verbatim, with what actually happened — the M5-S4 `attempt1-at-the-ceiling`
precedent. The first run's whole record is kept unedited at
`automation/runs/m6-spike/attempt1-no-dedicated-service/`.

  WRONG 1 — "a canary Ingress pointing at the shadow's own Service splits the
  traffic." It does not, and it fails SILENTLY: 0 of 200 requests moved at
  weight 10 AND at weight 50, with no error in any log. ingress-nginx keys
  backends by `<namespace>-<service>-<port>` and a backend may hold ONE role.
  The champion's backend did carry `alternativeBackends:
  [serving-nyc-taxi-eta-shadow-predictor-80]` — the canary LINK was wired — but
  that key is also an ordinary backend, because KServe generated an Ingress for
  the shadow too. The ordinary registration wins: `noServer` stays false and the
  policy reads `{weight: 0, weightTotal: 0}`. A canary that is configured,
  linked, and moves nothing.

  WRONG 2 — "traffic that reaches the shadow returns 500 at v1's signature."
  It returns **404**, and the mechanism matters more than the number: in the V2
  (Open Inference) protocol THE MODEL NAME IS IN THE URL PATH. The champion's
  traffic asks for `/v2/models/nyc-taxi-eta/infer`; the shadow's mlserver serves
  `nyc-taxi-eta-shadow` and has no such model, so the request is refused before
  any signature is consulted. The schema mismatch is real but it is the SECOND
  wall, not the first.

--------------------------------------------------------------------------
WHAT THE PROBE DOES NOT ANNOTATE, AND WHY (F-038)
--------------------------------------------------------------------------
The first run forced a controller reconcile with `kubectl annotate isvc` — a
supposedly spec-neutral edit. It rolled the champion's only predictor pod, twice,
and the end-state batch caught the outage: **174 of 200 requests returned 502**,
with the controller logging `connect() failed (111: Connection refused)` against
the replaced pod's dead IP. KServe propagates an InferenceService's annotations
onto its pod template, so annotating an isvc is a Deployment change. This script
does not annotate the isvc at all.

Usage: uv run python scripts/canary_spike_probe.py
       uv run python scripts/canary_spike_probe.py --dry-run
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
from typing import Any

from taxi_mlops.features import quote_time, sets
from taxi_mlops.serving.client import Endpoint, QuoteRequest, build_matrix, v2_payload

# This file has no REPO_ROOT of its own (its record path is relative to the
# repo root it is run from). The insert is still needed: `uv run python
# scripts/x.py` puts scripts/ on sys.path, but a loader that reads this file
# by path does not.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from _lib.k8s import kubectl  # noqa: E402

RECORD = Path("automation/runs/m6-spike/canary_spike.json")
# NOTE (M6-S4, F-039): this name is safe only while no InferenceService is called
# `nyc-taxi-eta-canary` — KServe generates an Ingress named after the isvc, and
# writing canary annotations onto a controller-owned object is accepted and then
# reverted, silently. M6-S4's own route is `nyc-taxi-eta-canary-route` for exactly
# that reason. Re-running this SPIKE while `make canary-deploy` is up would
# reproduce F-039 rather than ADR-011 condition 1; tear the canary down first.
CANARY_INGRESS = "nyc-taxi-eta-canary"
CANARY_SERVICE = "nyc-taxi-eta-canary-backend"
CHAMPION_ISVC = "nyc-taxi-eta"
SHADOW_ISVC = "nyc-taxi-eta-shadow"
NAMESPACE = "serving"
ROUTE = "http://localhost:8081"

#: nginx draws the canary per request, so an observed share is a binomial sample.
#: At n=200 the 95% interval for a true 50% is about ±7 points, which is why the
#: tolerance is 10 and not 2 — a bar tighter than the instrument's own noise is a
#: flaky check, and this program has paid for that twice (#63, #74).
BATCH = 200
WEIGHT = 50
WEIGHT_TOLERANCE_POINTS = 10.0

SUPERSEDED_PREDICTIONS = {
    "run1_p2_weight_10_splits_traffic": {
        "predicted": "with canary-weight=10, ~10% of 200 requests reach the shadow",
        "observed": "0 of 200 at weight 10 and 0 of 200 at weight 50 — no error anywhere",
        "why_it_was_wrong": (
            "the canary Ingress pointed at the shadow's OWN Service, which KServe's "
            "generated Ingress had already registered as an ordinary backend. One "
            "backend key, two roles; the ordinary role wins and the weight is dropped."
        ),
    },
    "run1_p4_shadow_500s_at_the_signature": {
        "predicted": "traffic reaching the shadow returns 500 — v1's signature refuses 24 columns",
        "observed": "404",
        "why_it_was_wrong": (
            "the V2 protocol carries the model name in the URL PATH. The shadow's "
            "mlserver serves `nyc-taxi-eta-shadow`, so `/v2/models/nyc-taxi-eta/infer` "
            "is refused as an unknown model before a signature is ever consulted. The "
            "signature wall is real and is simply behind this one."
        ),
    },
}

PREDICTION: dict[str, Any] = {
    "written_before_anything_was_applied": True,
    "p1_shared_service_canary_moves_nothing": (
        f"A canary Ingress at weight {WEIGHT} pointing at the shadow's OWN Service moves "
        f"0 of {BATCH} requests, and reports no error. The champion's backend still shows "
        "the alternativeBackends LINK while the alternative's trafficShapingPolicy reads "
        "weight 0 — configured, linked, inert."
    ),
    "p2_dedicated_service_canary_splits": (
        f"The same Ingress pointed at a DEDICATED Service (selecting the same pods, "
        f"referenced by nothing else) splits at weight {WEIGHT}: about half of {BATCH} "
        f"requests leave the champion, ±{WEIGHT_TOLERANCE_POINTS} points. The canary "
        "backend registers with noServer=true and weight/weightTotal 50/100."
    ),
    "p3_canary_traffic_404s_on_the_model_name": (
        "Every request the canary receives returns 404 and never a number, because the "
        "V2 model name is in the URL path. This is the constraint S4 inherits: a "
        "traffic-split canary needs both backends serving the SAME V2 model name."
    ),
    "p4_rewrite_target_cannot_fix_it": (
        "Adding rewrite-target to the CANARY Ingress does not change the 404 share: "
        "ingress-nginx applies only canary-* annotations from a canary Ingress and "
        "inherits the rest from the main one. So the model-name mismatch cannot be "
        "papered over at the ingress; it must be fixed at the backend."
    ),
    "p5_mirror_target_on_a_kserve_owned_ingress": (
        "UNKNOWN and deliberately not guessed. The annotation is added to the Ingress "
        "KServe OWNS and checked two ways that the first run conflated: does the "
        "ANNOTATION persist, and does nginx.conf actually gain a `mirror` directive? "
        "The first run only asked the first question, and asked the second AFTER "
        "cleanup had already removed the annotation — which measures nothing."
    ),
    "p6_end_state_is_exactly_the_start_state": (
        f"After cleanup, {BATCH} requests to the champion's host return 200 with "
        "model_version 2 and zero failures."
    ),
}


# `kubectl` moved to `_lib.k8s` at CU-S4 (it was defined eight times, six
# distinct bodies, all pinning the same context).


def apply(manifest: str) -> str:
    proc = subprocess.run(  # noqa: S603 — fixed argv, no shell
        ["kubectl", "--context", "kind-mlops-taxi", "apply", "-f", "-"],
        input=manifest, capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"apply failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def canary_ingress(backend_service: str, weight: int, rewrite: str | None = None) -> str:
    extra = (
        f'\n    nginx.ingress.kubernetes.io/rewrite-target: "{rewrite}"' if rewrite else ""
    )
    return f"""
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {CANARY_INGRESS}
  namespace: {NAMESPACE}
  annotations:
    nginx.ingress.kubernetes.io/canary: "true"
    nginx.ingress.kubernetes.io/canary-weight: "{weight}"{extra}
  labels:
    crosstown.io/serving-role: canary-probe
spec:
  ingressClassName: nginx
  rules:
    - host: {CHAMPION_ISVC}-{NAMESPACE}.local
      http:
        paths:
          - backend:
              service:
                name: {backend_service}
                port:
                  number: 80
            path: /
            pathType: Prefix
"""


#: A Service selecting the shadow's pods that NOTHING else routes to. The selector
#: is read off the shadow's own Service at run time rather than typed, so a KServe
#: labelling change fails here instead of silently selecting no pods.
def canary_service(selector: dict[str, str]) -> str:
    lines = "\n".join(f"    {k}: {v}" for k, v in selector.items())
    return f"""
apiVersion: v1
kind: Service
metadata:
  name: {CANARY_SERVICE}
  namespace: {NAMESPACE}
  labels:
    crosstown.io/serving-role: canary-probe
spec:
  selector:
{lines}
  ports:
    - name: http
      port: 80
      protocol: TCP
      targetPort: 8080
"""


def backends() -> dict[str, Any]:
    raw = kubectl(
        "-n", "ingress-nginx", "exec", "deploy/ingress-nginx-controller", "--",
        "curl", "-s", "http://127.0.0.1:10246/configuration/backends",
    )
    return {b["name"]: b for b in json.loads(raw)}


def nginx_has_mirror() -> bool:
    conf = kubectl(
        "-n", "ingress-nginx", "exec", "deploy/ingress-nginx-controller", "--",
        "cat", "/etc/nginx/nginx.conf",
    )
    return "mirror " in conf or "mirror_request_body" in conf


def send_batch(n: int, body: bytes, host: str, url: str) -> dict[str, Any]:
    """Send `n` identical requests and count what came back, BY STATUS.

    Statuses, not latencies: this probe is about WHERE a request went, and on a
    split with two distinguishable backends the status code IS the attribution.
    """
    counts: dict[str, int] = {}
    versions: dict[str, int] = {}
    sample: float | None = None
    for _ in range(n):
        request = urllib.request.Request(  # noqa: S310 — a fixed http:// route
            url, data=body, headers={"Content-Type": "application/json", "Host": host}
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                payload = json.loads(response.read())
            counts["200"] = counts.get("200", 0) + 1
            version = str(payload.get("model_version"))
            versions[version] = versions.get(version, 0) + 1
            if sample is None:
                sample = float(payload["outputs"][0]["data"][0])
        except urllib.error.HTTPError as exc:
            counts[str(exc.code)] = counts.get(str(exc.code), 0) + 1
        except Exception as exc:  # noqa: BLE001 — a transport failure is a result too
            counts[type(exc).__name__] = counts.get(type(exc).__name__, 0) + 1
    return {
        "sent": n,
        "by_status": counts,
        "model_versions_seen": versions,
        "a_sampled_prediction": sample,
        "left_the_champion_pct": round(100.0 * (n - counts.get("200", 0)) / n, 2),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    RECORD.parent.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {
        "prediction": PREDICTION,
        "superseded_predictions": SUPERSEDED_PREDICTIONS,
        "phases": {},
    }
    RECORD.write_text(json.dumps(record, indent=2) + "\n")
    print(f"[spike] prediction written to {RECORD} — nothing has been applied yet")

    if args.dry_run:
        print("[spike] --dry-run: would probe the shared-Service canary, the dedicated-Service")
        print("        canary, rewrite-target, and mirror-target — then remove all of them.")
        return 0

    cfg = sets.resolve_set("v2")
    matrix = build_matrix([QuoteRequest("2019-07-04T09:15:00", 132, 48, 1.0)], cfg)
    body = json.dumps(v2_payload(matrix, quote_time.feature_names(cfg)), allow_nan=False).encode()
    champion = Endpoint(name=CHAMPION_ISVC, namespace=NAMESPACE, route=ROUTE)
    selector = json.loads(
        kubectl("-n", NAMESPACE, "get", "svc", f"{SHADOW_ISVC}-predictor",
                "-o", "jsonpath={.spec.selector}")
    )

    def cleanup() -> None:
        kubectl("-n", NAMESPACE, "delete", "ingress", CANARY_INGRESS, "--ignore-not-found")
        kubectl("-n", NAMESPACE, "delete", "svc", CANARY_SERVICE, "--ignore-not-found")
        kubectl("-n", NAMESPACE, "annotate", "ingress", CHAMPION_ISVC,
                "nginx.ingress.kubernetes.io/mirror-target-", "--overwrite", check=False)

    try:
        print("\n[spike] phase 0 — baseline, no canary exists")
        record["phases"]["p0_baseline"] = send_batch(BATCH, body, champion.host, champion.infer_url)
        print(f"        {record['phases']['p0_baseline']['by_status']}")

        print(f"\n[spike] phase 1 — canary at weight {WEIGHT} on the shadow's SHARED Service")
        apply(canary_ingress(f"{SHADOW_ISVC}-predictor", WEIGHT))
        time.sleep(12)
        back = backends()
        alt_key = f"{NAMESPACE}-{SHADOW_ISVC}-predictor-80"
        record["phases"]["p1_shared_service"] = {
            "champion_alternativeBackends": back[f"{NAMESPACE}-{CHAMPION_ISVC}-predictor-80"].get(
                "alternativeBackends"
            ),
            "alternative_noServer": back.get(alt_key, {}).get("noServer"),
            "alternative_trafficShapingPolicy": back.get(alt_key, {}).get("trafficShapingPolicy"),
            "batch": send_batch(BATCH, body, champion.host, champion.infer_url),
        }
        shared = record["phases"]["p1_shared_service"]
        print(f"        tsp={shared['alternative_trafficShapingPolicy']}")
        print(f"        {shared['batch']['by_status']}")

        print("\n[spike] phase 2 — the SAME canary on a DEDICATED Service")
        apply(canary_service(selector))
        apply(canary_ingress(CANARY_SERVICE, WEIGHT))
        time.sleep(12)
        back = backends()
        ded_key = f"{NAMESPACE}-{CANARY_SERVICE}-80"
        record["phases"]["p2_dedicated_service"] = {
            "canary_noServer": back.get(ded_key, {}).get("noServer"),
            "canary_trafficShapingPolicy": back.get(ded_key, {}).get("trafficShapingPolicy"),
            "batch": send_batch(BATCH, body, champion.host, champion.infer_url),
        }
        dedicated = record["phases"]["p2_dedicated_service"]
        print(f"        tsp={dedicated['canary_trafficShapingPolicy']}")
        print(f"        {dedicated['batch']['by_status']}")

        print("\n[spike] phase 3 — rewrite-target on the CANARY Ingress")
        apply(canary_ingress(CANARY_SERVICE, WEIGHT,
                             rewrite=f"/v2/models/{SHADOW_ISVC}/infer"))
        time.sleep(12)
        record["phases"]["p3_rewrite_target"] = {
            "batch": send_batch(BATCH, body, champion.host, champion.infer_url)
        }
        print(f"        {record['phases']['p3_rewrite_target']['batch']['by_status']}")

        print("\n[spike] phase 4 — mirror-target on the Ingress KServe OWNS")
        kubectl("-n", NAMESPACE, "delete", "ingress", CANARY_INGRESS, "--ignore-not-found")
        kubectl("-n", NAMESPACE, "annotate", "ingress", CHAMPION_ISVC,
                f"nginx.ingress.kubernetes.io/mirror-target=http://{SHADOW_ISVC}-predictor."
                f"{NAMESPACE}.svc.cluster.local/v2/models/{SHADOW_ISVC}/infer", "--overwrite")
        time.sleep(30)
        # BOTH questions, asked WHILE the annotation is still in place — the first
        # run asked the second one after cleanup, which measures nothing.
        jsonpath = (
            "jsonpath={.metadata.annotations."
            "nginx\\.ingress\\.kubernetes\\.io/mirror-target}"
        )
        survived = kubectl(
            "-n", NAMESPACE, "get", "ingress", CHAMPION_ISVC, "-o", jsonpath
        )
        record["phases"]["p4_mirror_target"] = {
            "annotation_survived_on_the_object": bool(survived),
            "annotation": survived or "(stripped by the KServe controller)",
            "nginx_conf_has_a_mirror_directive": nginx_has_mirror(),
            "batch": send_batch(50, body, champion.host, champion.infer_url),
        }
        print(f"        annotation survived: {bool(survived)}")
        print(f"        nginx has a mirror directive: "
              f"{record['phases']['p4_mirror_target']['nginx_conf_has_a_mirror_directive']}")
    finally:
        print("\n[spike] cleanup — the wire goes back exactly where it started")
        cleanup()
        time.sleep(12)

    record["phases"]["p5_end_state"] = send_batch(BATCH, body, champion.host, champion.infer_url)
    print(f"        end state: {record['phases']['p5_end_state']['by_status']}")

    p1 = record["phases"]["p1_shared_service"]
    p2 = record["phases"]["p2_dedicated_service"]
    p3 = record["phases"]["p3_rewrite_target"]
    end = record["phases"]["p5_end_state"]
    checks = {
        "p1_shared_service_canary_moved_nothing": p1["batch"]["left_the_champion_pct"] == 0.0,
        "p1_the_link_existed_while_the_weight_did_not": (
            f"{NAMESPACE}-{SHADOW_ISVC}-predictor-80" in (p1["champion_alternativeBackends"] or [])
            and (p1["alternative_trafficShapingPolicy"] or {}).get("weight") == 0
        ),
        "p2_dedicated_service_canary_split_the_traffic": abs(
            p2["batch"]["left_the_champion_pct"] - WEIGHT
        ) <= WEIGHT_TOLERANCE_POINTS,
        "p2_canary_registered_as_canary_only": p2["canary_noServer"] is True
        and (p2["canary_trafficShapingPolicy"] or {}).get("weight") == WEIGHT,
        "p3_canary_traffic_never_returned_a_number": "1"
        not in p2["batch"]["model_versions_seen"],
        "p4_rewrite_target_did_not_change_the_share": abs(
            p3["batch"]["left_the_champion_pct"] - p2["batch"]["left_the_champion_pct"]
        ) <= WEIGHT_TOLERANCE_POINTS,
        "p6_end_state_is_100pct_champion": end["by_status"].get("200") == BATCH
        and set(end["model_versions_seen"]) == {"2"},
    }
    record["checks"] = checks
    record["verdict"] = "PASS" if all(checks.values()) else "FAIL"
    RECORD.write_text(json.dumps(record, indent=2) + "\n")

    print(f"\n[spike] {RECORD}")
    for name, ok in checks.items():
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
    print(f"[spike] {record['verdict']} — {sum(checks.values())}/{len(checks)} checks")
    return 0 if record["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
