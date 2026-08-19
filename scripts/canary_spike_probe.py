#!/usr/bin/env python3
"""ADR-004's spike, MEASURED: does ingress-nginx give this program a traffic split? (M6-S3)

ADR-004 deferred one question — "what mechanism gives this program canary and
shadow?" — to a timeboxed spike with a pre-approved budget of ONE serving
re-deploy. This is that spike, and it is a script rather than a paragraph
because the question is empirical: KServe RawDeployment GENERATES the champion's
Ingress and owns it, so whether a hand-authored second Ingress can share its host
without the reconciler fighting it is a fact about this cluster, not about the
documentation.

--------------------------------------------------------------------------
THE PREDICTION IS WRITTEN TO DISK BEFORE ANYTHING IS APPLIED
--------------------------------------------------------------------------
The M4-S5 / M5-S4 / M6-S2 discipline, third milestone running. A probe that
decides what it expected after seeing the answer has measured nothing. The
predictions live in `PREDICTION` below, are written to the record as the FIRST
action, and every one of them is checked.

--------------------------------------------------------------------------
WHY THE SHADOW'S 500s ARE THE INSTRUMENT, AND NOT A DEFECT
--------------------------------------------------------------------------
The probe sends the CHAMPION's own 24-column matrix at the champion's host and
counts status codes. Requests nginx routes to the champion return 200 with a
number; requests it routes to the canary backend — the v1 shadow — return 500,
because v1's logged signature covers 5 columns and refuses the other 19.

That refusal is F-032's shape, it was predicted in writing in
`infra/manifests/inferenceservice-shadow-v1.yaml` before the first 500 was seen,
and it is exactly what makes this a good instrument: the two backends are
DISTINGUISHABLE at the client with no server-side attribution needed. One
experiment therefore answers two questions — what fraction of traffic moved, and
whether raw mirroring can shadow a different-schema model. It cannot, and the
500 rate is the measurement of that rather than an assertion about it.

This is also why the probe is honest about what it does NOT prove: a 500 rate of
~10% shows nginx SPLIT the traffic; it does not show the canary backend would
have served correctly. A same-schema canary is S4's, with the champion's own
bytes behind it, and that is where "the canary answered" becomes checkable.

--------------------------------------------------------------------------
WHAT IT LEAVES BEHIND
--------------------------------------------------------------------------
Nothing. The canary Ingress is deleted and the mirror annotation removed under an
EXIT trap, and the last phase re-asserts that the champion's host returns 200 on
every one of a fresh batch. M6 law 2: every story ends where it started.

Usage: uv run python scripts/canary_spike_probe.py
       uv run python scripts/canary_spike_probe.py --dry-run   (prints the plan
                                                                and the prediction,
                                                                applies nothing)
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

RECORD = Path("automation/runs/m6-spike/canary_spike.json")
CANARY_INGRESS = "nyc-taxi-eta-canary"
CHAMPION_ISVC = "nyc-taxi-eta"
SHADOW_ISVC = "nyc-taxi-eta-shadow"
NAMESPACE = "serving"
ROUTE = "http://localhost:8081"

#: How many requests each weighted phase sends. nginx's canary weight is applied
#: per-request with a random draw, so the OBSERVED share is a sample from a
#: binomial and will not equal the weight exactly. 200 requests puts the 95%
#: interval for a true 10% at roughly ±4 points, which is why the tolerance
#: below is 8 and not 2 — a bar tighter than the instrument's own noise is a
#: flaky check, and this program has paid for that lesson twice (#63, #74).
BATCH = 200
WEIGHT_TOLERANCE_POINTS = 8.0

PREDICTION: dict[str, Any] = {
    "written_before_anything_was_applied": True,
    "p1_canary_ingress_is_accepted": (
        "A second Ingress named nyc-taxi-eta-canary, sharing the champion's host "
        "and carrying nginx.ingress.kubernetes.io/canary=true, is ACCEPTED by the "
        "API server and is not deleted by KServe's reconciler. Reason: KServe owns "
        "objects it created (ownerReference to the InferenceService); this one has "
        "no such reference and a different name, so it is not in the controller's "
        "desired state at all. Risk if wrong: the operator garbage-collects it and "
        "option (ii) is dead — the fallback is dual-send from the client."
    ),
    "p2_weight_10_splits_traffic": (
        f"With canary-weight=10, about 10% of {BATCH} requests to the champion's "
        f"host return 500 (routed to the v1 shadow, whose signature refuses a "
        f"24-column matrix) and the rest return 200. Tolerance "
        f"±{WEIGHT_TOLERANCE_POINTS} points for binomial noise at n={BATCH}."
    ),
    "p3_weight_50_moves_the_share": (
        f"Raising canary-weight to 50 moves the observed 500 share to about 50% "
        f"of {BATCH}. This is the check that the annotation is the KNOB rather "
        "than a coincidence: a split that does not track the weight is not a "
        "traffic split, it is a broken backend."
    ),
    "p4_v1_cannot_be_mirrored": (
        "Every request that reaches the shadow with the champion's matrix returns "
        "500 and never a number — v1 eats 5 features, the wire carries 24. So raw "
        "traffic mirroring cannot shadow v1, and the disagreement table must come "
        "from dual-send with per-target feature builds. Predicted in the shadow "
        "manifest before the first 500 was observed."
    ),
    "p5_mirror_annotation_is_reverted_or_kept": (
        "UNKNOWN, and deliberately not guessed — this is the probe's open "
        "question. Adding nginx.ingress.kubernetes.io/mirror-target to the "
        "Ingress KServe OWNS either survives (the controller does not reconcile "
        "annotations it did not set) or is stripped (it does). Both outcomes are "
        "informative and the ADR records whichever happens. What IS predicted: "
        "even if it survives, it cannot usefully shadow v1, for p4's reason."
    ),
    "p6_end_state_is_exactly_the_start_state": (
        f"After cleanup, {BATCH} requests to the champion's host return 200 with "
        "model_version 2 and zero 500s: no canary Ingress, no mirror annotation, "
        "the champion serving 100%."
    ),
}


def kubectl(*args: str, check: bool = True) -> str:
    proc = subprocess.run(  # noqa: S603 — fixed argv, no shell
        ["kubectl", "--context", "kind-mlops-taxi", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"kubectl {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def canary_ingress_yaml(weight: int) -> str:
    """A SECOND Ingress the KServe controller does not own.

    No ownerReference, a name the controller never generates, and the same host
    as the champion's — which is what ingress-nginx requires for a canary: the
    canary rule is merged into the rule set of the non-canary Ingress serving the
    same host, and traffic is drawn between them per request.
    """
    return f"""
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {CANARY_INGRESS}
  namespace: {NAMESPACE}
  annotations:
    nginx.ingress.kubernetes.io/canary: "true"
    nginx.ingress.kubernetes.io/canary-weight: "{weight}"
  labels:
    app.kubernetes.io/part-of: crosstown-eta
    crosstown.io/serving-role: canary-probe
spec:
  ingressClassName: nginx
  rules:
    - host: {CHAMPION_ISVC}-{NAMESPACE}.local
      http:
        paths:
          - backend:
              service:
                name: {SHADOW_ISVC}-predictor
                port:
                  number: 80
            path: /
            pathType: Prefix
"""


def apply(manifest: str) -> str:
    proc = subprocess.run(  # noqa: S603 — fixed argv, no shell
        ["kubectl", "--context", "kind-mlops-taxi", "apply", "-f", "-"],
        input=manifest,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"apply failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def send_batch(n: int, body: bytes, host: str, url: str) -> dict[str, Any]:
    """Send `n` identical requests and count what came back, by status.

    Statuses, not latencies: this probe is about WHERE a request went, and the
    status code is the attribution. Bodies of the 200s are sampled so the record
    can show that the champion's answers are real numbers and not empty 200s.
    """
    counts: dict[str, int] = {}
    versions: dict[str, int] = {}
    sample_value: float | None = None
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
            if sample_value is None:
                sample_value = float(payload["outputs"][0]["data"][0])
        except urllib.error.HTTPError as exc:
            key = str(exc.code)
            counts[key] = counts.get(key, 0) + 1
        except Exception as exc:  # noqa: BLE001 — a transport failure is a result too
            key = type(exc).__name__
            counts[key] = counts.get(key, 0) + 1
    return {
        "sent": n,
        "by_status": counts,
        "model_versions_seen": versions,
        "a_sampled_prediction": sample_value,
        "non_200_share_pct": round(100.0 * (n - counts.get("200", 0)) / n, 2),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    RECORD.parent.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {"prediction": PREDICTION, "phases": {}}
    # THE PREDICTION LANDS FIRST, before a single object is applied. If this
    # process dies mid-probe the file on disk still says what was expected.
    RECORD.write_text(json.dumps(record, indent=2) + "\n")
    print(f"[spike] prediction written to {RECORD} — nothing has been applied yet")
    for key, text in PREDICTION.items():
        if key != "written_before_anything_was_applied":
            print(f"        {key}: {text[:96]}…")

    if args.dry_run:
        print("\n[spike] --dry-run: would apply the canary Ingress at weights 10 and 50,")
        print("        probe the mirror annotation, then delete both and re-check the champion.")
        return 0

    # The champion's own matrix, encoded ONCE. Encoding per request would put a
    # feature build inside the measurement, and this probe times nothing but it
    # is still the wrong shape (M5-S4's lesson about what a measurement contains).
    cfg = sets.resolve_set("v2")
    requests = [QuoteRequest("2019-07-04T09:15:00", 132, 48, 1.0)]
    matrix = build_matrix(requests, cfg)
    body = json.dumps(v2_payload(matrix, quote_time.feature_names(cfg)), allow_nan=False).encode()
    champion = Endpoint(name=CHAMPION_ISVC, namespace=NAMESPACE, route=ROUTE)

    def cleanup() -> None:
        kubectl("-n", NAMESPACE, "delete", "ingress", CANARY_INGRESS, "--ignore-not-found")
        kubectl(
            "-n", NAMESPACE, "annotate", "ingress", CHAMPION_ISVC,
            "nginx.ingress.kubernetes.io/mirror-target-", "--overwrite", check=False,
        )

    try:
        # ---------------------------------------------------------- phase 0 --
        print("\n[spike] phase 0 — the baseline, before any canary exists")
        record["phases"]["p0_baseline"] = send_batch(BATCH, body, champion.host, champion.infer_url)
        print(f"        {record['phases']['p0_baseline']['by_status']}")

        # ---------------------------------------------------------- phase 1 --
        print(f"\n[spike] phase 1 — hand-authored canary Ingress at weight 10")
        print("        " + apply(canary_ingress_yaml(10)))
        time.sleep(10)  # nginx observes the object and reloads its config
        owner = kubectl(
            "-n", NAMESPACE, "get", "ingress", CANARY_INGRESS,
            "-o", "jsonpath={.metadata.ownerReferences}",
        )
        record["phases"]["p1_canary_accepted"] = {
            "exists": bool(kubectl("-n", NAMESPACE, "get", "ingress", CANARY_INGRESS, "-o", "name")),
            "owner_references": owner or "(none — KServe does not own it)",
        }
        record["phases"]["p2_weight_10"] = send_batch(
            BATCH, body, champion.host, champion.infer_url
        )
        print(f"        {record['phases']['p2_weight_10']}")

        # ---------------------------------------------------------- phase 2 --
        print("\n[spike] phase 2 — the same Ingress at weight 50 (is the weight the KNOB?)")
        print("        " + apply(canary_ingress_yaml(50)))
        time.sleep(10)
        record["phases"]["p3_weight_50"] = send_batch(
            BATCH, body, champion.host, champion.infer_url
        )
        print(f"        {record['phases']['p3_weight_50']}")

        # ---------------------------------------------------------- phase 3 --
        # Does the operator strip an annotation it did not set, on an object it
        # OWNS? Asked of the champion's generated Ingress, which is the only
        # place a mirror-target could go.
        print("\n[spike] phase 3 — mirror-target on the Ingress KServe OWNS")
        kubectl("-n", NAMESPACE, "delete", "ingress", CANARY_INGRESS, "--ignore-not-found")
        kubectl(
            "-n", NAMESPACE, "annotate", "ingress", CHAMPION_ISVC,
            f"nginx.ingress.kubernetes.io/mirror-target=http://{SHADOW_ISVC}-predictor."
            f"{NAMESPACE}.svc.cluster.local/v2/models/{SHADOW_ISVC}/infer",
            "--overwrite",
        )
        # Force the controller to reconcile by touching the InferenceService it
        # watches: an annotation bump is the cheapest spec-neutral edit there is.
        kubectl(
            "-n", NAMESPACE, "annotate", "isvc", CHAMPION_ISVC,
            f"crosstown.io/spike-probe={int(time.time())}", "--overwrite",
        )
        time.sleep(30)
        survived = kubectl(
            "-n", NAMESPACE, "get", "ingress", CHAMPION_ISVC,
            "-o", "jsonpath={.metadata.annotations.nginx\\.ingress\\.kubernetes\\.io/mirror-target}",
        )
        mirrored = send_batch(50, body, champion.host, champion.infer_url)
        record["phases"]["p4_mirror_annotation"] = {
            "annotation_after_a_forced_reconcile": survived or "(stripped by the controller)",
            "survived": bool(survived),
            "champion_batch_while_mirroring": mirrored,
        }
        print(f"        survived: {bool(survived)} — {survived or 'stripped'}")
        print(f"        {mirrored['by_status']}")
    finally:
        print("\n[spike] cleanup — the wire goes back exactly where it started")
        cleanup()
        kubectl(
            "-n", NAMESPACE, "annotate", "isvc", CHAMPION_ISVC,
            "crosstown.io/spike-probe-", "--overwrite", check=False,
        )
        time.sleep(10)

    record["phases"]["p5_end_state"] = send_batch(BATCH, body, champion.host, champion.infer_url)
    print(f"        end state: {record['phases']['p5_end_state']['by_status']}")

    # ------------------------------------------------------------- verdicts --
    p2, p3 = record["phases"]["p2_weight_10"], record["phases"]["p3_weight_50"]
    end = record["phases"]["p5_end_state"]
    checks = {
        "p1_canary_ingress_accepted_and_not_gc'd": record["phases"]["p1_canary_accepted"]["exists"],
        "p2_weight_10_within_tolerance": abs(p2["non_200_share_pct"] - 10.0)
        <= WEIGHT_TOLERANCE_POINTS,
        "p3_weight_50_within_tolerance": abs(p3["non_200_share_pct"] - 50.0)
        <= WEIGHT_TOLERANCE_POINTS,
        "p3_share_moved_with_the_weight": p3["non_200_share_pct"] > p2["non_200_share_pct"],
        "p4_shadow_never_answered_the_champion's_matrix": "200"
        not in {k for k in p2["by_status"] if k != "200"}
        and p2["model_versions_seen"].get("1") is None,
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
