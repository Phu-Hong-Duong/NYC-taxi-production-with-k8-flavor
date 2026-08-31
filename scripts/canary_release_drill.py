#!/usr/bin/env python3
"""The release rehearsal: 10% -> 100% -> revert, under sustained load (M6-S4).

One continuous open-loop load run against the CHAMPION'S OWN HOST, with the
canary weight changed from inside the load client's per-second callback — so the
weight changes and the latencies share one clock, exactly as M5-S4's kill drill
shares one clock with the kill it measures. A weight flipped by a separate
`sleep` in a shell is a weight whose position in the timeline is a guess.

    0 ..  60 s   no canary Ingress exists            100% champion
   60 .. 180 s   canary-weight: 10                   the 90/10 window
  180 .. 270 s   canary-weight: 100                  the fully-shifted window
  270 .. 360 s   the canary Ingress is DELETED       reverted, 100% champion

--------------------------------------------------------------------------
THE SPLIT IS READ FROM COUNTERS, NEVER FROM THE ANNOTATION
--------------------------------------------------------------------------
ADR-011 condition 1's failure mode is SILENT: at M6-S3 a canary that was
configured, linked and logged clean moved **0 of 200 requests**, reporting
`{weight: 0, weightTotal: 0}` while the champion's backend genuinely listed it
under `alternativeBackends`. So an observed share asserted from its own
configuration is not a measurement (gotcha #81), and this drill asks two
independent systems:

  WITNESS 1 (the claim): `nginx_ingress_controller_requests`. ingress-nginx
  stamps a `canary="<ns>-<svc>-<port>"` label on every request it routes to an
  alternative backend, so the split is a label selector on the router's own
  counter — the "ingress per-backend counters" §9/M6 asks for.

  WITNESS 2 (the corroboration, from a different process): the two predictors'
  OWN `rest_server_requests_total`, scraped per pod because M6-S1 discovers
  predictors by label and the canary carries it. mlserver counts what it was
  actually asked, which is a fact no ingress configuration can fake.

Both are cumulative counters read at the window's edges and differenced. They
are scraped every 15 s (M6-S1's interval), so each window's covered interval is
its stated length +/- one scrape — which moves the COUNTS a little and the SHARE
essentially not at all. The record carries both so a reader can check that.

WHY THE CLIENT CANNOT BE A WITNESS HERE, SAID OUT LOUD. The canary serves the
champion's own bytes under the champion's own model name, so every response in
this run carries `model_version: 2` whichever pod produced it. That is the
memo-approved delta (M6-S3 returned NO-GO for v1) and it is also the reason a
constant version stamp in this record is NOT evidence that no traffic moved.
M6-S3 could attribute at the client only because its canary was BROKEN — the
404 rate was the split measurement — which is not a property to design for.

--------------------------------------------------------------------------
WHAT IS MUTATED, AND WHAT IS DELIBERATELY NOT
--------------------------------------------------------------------------
Exactly one object is created, edited and deleted: the canary INGRESS. No
InferenceService is annotated — F-038 measured `kubectl annotate isvc` rolling
the champion's only predictor twice for **174 of 200 requests returning 502** —
and no pod, Deployment, Service or registry alias is touched. The champion's
predictor pod is expected to have the same UID and the same age (plus the
drill's runtime) at the end, and the drill asserts it.

Usage: uv run python scripts/canary_release_drill.py            (via `make canary`)
       uv run python scripts/canary_release_drill.py --dry-run  (writes the
           prediction, applies nothing, ~2 s)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from taxi_mlops.serving.client import Endpoint
from taxi_mlops.serving.load import run_load

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from _lib.k8s import kubectl  # noqa: E402

RECORD = REPO_ROOT / "automation/runs/m6-canary/release_drill.json"
INGRESS_MANIFEST = REPO_ROOT / "infra/manifests/canary-ingress.yaml"
WEIGHT_PLACEHOLDER = "CANARY-WEIGHT-SET-AT-RUN-TIME"

NAMESPACE = "serving"
CHAMPION = "nyc-taxi-eta"
CANARY_ISVC = "nyc-taxi-eta-canary"
#: NOT `nyc-taxi-eta-canary` — that name belongs to the Ingress KServe generates
#: for the canary InferenceService, and applying these annotations to it is
#: accepted, reverted seconds later, and silent (F-039).
CANARY_INGRESS = "nyc-taxi-eta-canary-route"
CANARY_BACKEND_KEY = f"{NAMESPACE}-nyc-taxi-eta-canary-backend-80"
ROUTE = "http://localhost:8081"
PROM = "http://localhost:8081"
PROM_HOST = "prometheus.local"

#: M5-S4's headline shape, unchanged on purpose: the SLO is written against it
#: (docs/slo_serving.md), so a release rehearsed at some other rate would be a
#: rehearsal of a load nobody has a target for.
RATE = 4.0
CONCURRENCY = 8

#: The phase boundaries, in seconds from the start of the single load run.
T_CANARY_10 = 60
T_CANARY_100 = 180
T_REVERT = 270
T_END = 360

#: How long after a weight change the measured window starts. nginx reloads its
#: configuration on an Ingress edit; requests in flight across the reload are
#: served by whichever backend was current when they were routed, so counting
#: them would blur the share by an amount that has nothing to do with the weight.
SETTLE_SECONDS = 15

#: nginx draws the canary per request, so an observed share is a binomial sample.
#: Over a 105 s window at 4 req/s (~420 requests) the 95% interval for a true 10%
#: is about +/-3 points; the bar is 5, which is outside the instrument's own noise
#: and still far too tight to confuse 10% with 0% or 100% (#63/#74 in bar form).
SHARE_TOLERANCE_POINTS = 5.0

#: §9/M6's number. The revert must be possible in under two minutes under load.
REVERT_BUDGET_SECONDS = 120.0

#: ATTEMPT 1 WENT RED AND ITS RECORD IS KEPT UNEDITED at
#: automation/runs/m6-canary/attempt1-ingress-name-collision/ — the M5-S4
#: `attempt1-at-the-ceiling` and M6-S3 `attempt1-no-dedicated-service` precedent,
#: third milestone running. What it found is F-039 and it is worth more than the
#: green run: the failure it produced is BYTE-FOR-BYTE the failure this story was
#: built to avoid.
SUPERSEDED_PREDICTIONS = {
    "run1_the_dedicated_service_was_enough": {
        "predicted": (
            "with ADR-011's two conditions satisfied — a dedicated backend Service and "
            "MLSERVER_MODEL_NAME on the canary — weight 10 moves about a tenth of the traffic"
        ),
        "observed": (
            "0 of 420 requests at weight 10, and 3 of 300 at weight 100 — the ingress "
            "counter recorded no canary-labelled request at all"
        ),
        "why_it_was_wrong": (
            "F-039, and it is NOT either ADR-011 condition. The canary Ingress was named "
            "`nyc-taxi-eta-canary`, which is exactly the name KServe generates for the "
            "InferenceService of that name. `kubectl apply` wrote the canary annotations "
            "onto the CONTROLLER-OWNED object; KServe reconciled them away seconds later. "
            "The three requests that did reach the canary pod at weight 100 are that "
            "window. The route is now `nyc-taxi-eta-canary-route`, and this drill refuses "
            "to weight any Ingress that carries ownerReferences."
        ),
    },
}

PREDICTION: dict[str, Any] = {
    "written_before_anything_was_applied": True,
    "p1_weight_10_moves_about_a_tenth": (
        f"During the settled 90/10 window, {100 - 10}/10 +/- {SHARE_TOLERANCE_POINTS} points "
        "of requests are attributed to the canary backend by "
        "nginx_ingress_controller_requests{canary!=''}."
    ),
    "p2_the_two_witnesses_agree": (
        "The share computed from the ingress counter and the share computed from the two "
        "predictors' own rest_server_requests_total agree within 3 points, in BOTH weighted "
        "windows. They are different processes counting different things; a disagreement "
        "would mean one of them is not measuring what this drill thinks it is."
    ),
    "p3_weight_100_moves_essentially_all_of_it": (
        "At canary-weight 100, >= 95% of settled-window requests reach the canary and the "
        "champion predictor's own counter is flat to within a handful of requests."
    ),
    "p4_a_weight_flip_costs_zero_requests": (
        "ZERO failed requests across both weight changes and across the revert. No pod is "
        "created, destroyed or rescheduled by an Ingress edit, so this should not even cost "
        "the 0.5 s a model re-deploy costs (gotcha #80). If any request fails, that is a "
        "finding about ingress-nginx's reload and not a footnote."
    ),
    "p5_the_revert_is_seconds_not_minutes": (
        f"Deleting the canary Ingress returns the split to 100/0 in well under 10 s of "
        f"wall-clock — measured from the controller's OWN backend configuration, polled — "
        f"against the {REVERT_BUDGET_SECONDS:.0f} s budget. One object is deleted and nginx "
        "reloads; nothing is scheduled, pulled or downloaded."
    ),
    "p6_the_version_stamp_proves_nothing_here": (
        "Every response in every phase carries model_version 2, INCLUDING the fully-shifted "
        "window, because the canary is the champion's own bytes under the champion's own "
        "model name. This is stated as a prediction so that nobody later reads a constant "
        "version stamp in this record as evidence that no traffic moved."
    ),
    "p7_the_champion_pod_is_never_touched": (
        "The champion predictor pod has the same UID at the end of the drill as at the "
        "start, and @champion is version 2 throughout. The only mutated object is the "
        "canary Ingress (F-038: an isvc annotation would not have been metadata)."
    ),
}


# `kubectl` moved to `_lib.k8s` at CU-S4 (it was defined eight times, six
# distinct bodies, all pinning the same context).


def promql(query: str) -> dict[str, float]:
    """One instant query, returned as {series-fingerprint: value}.

    Through the SAME 8081 route everything else in M6 uses (law 1) — Prometheus
    has no hostPort and will not get one before a PO-sanctioned rebuild.
    """
    url = f"{PROM}/api/v1/query?" + urllib.parse.urlencode({"query": query})
    request = urllib.request.Request(url, headers={"Host": PROM_HOST})  # noqa: S310
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        payload = json.loads(response.read())
    if payload.get("status") != "success":
        raise RuntimeError(f"prometheus refused {query!r}: {payload}")
    out: dict[str, float] = {}
    for series in payload["data"]["result"]:
        key = json.dumps(series["metric"], sort_keys=True)
        out[key] = float(series["value"][1])
    return out


def scalar(query: str) -> float:
    """A query that must collapse to one number — 0.0 when the series is absent.

    Absent is a legitimate answer here: before the first canary request exists,
    there is no series carrying the canary label at all, and treating that as an
    error would make the baseline window unmeasurable.
    """
    values = promql(query)
    if not values:
        return 0.0
    if len(values) > 1:
        raise RuntimeError(f"{query!r} returned {len(values)} series, expected 1")
    return next(iter(values.values()))


def counters() -> dict[str, float]:
    """The whole measurement surface, read in one place at a window's edge."""
    selector = f'namespace="{NAMESPACE}",ingress="{CHAMPION}"'
    return {
        "ingress_total": scalar(f"sum(nginx_ingress_controller_requests{{{selector}}})"),
        # A request routed to an alternative backend carries the `canary` label
        # naming that backend; a request served by the main one carries no such
        # label at all. `canary!=""` is therefore the split, said by the router.
        "ingress_canary": scalar(
            f'sum(nginx_ingress_controller_requests{{{selector},canary!=""}})'
        ),
        "champion_pod": scalar(
            f'sum(rest_server_requests_total{{pod=~"{CHAMPION}-predictor-.*"}})'
        ),
        "canary_pod": scalar(
            f'sum(rest_server_requests_total{{pod=~"{CANARY_ISVC}-predictor-.*"}})'
        ),
    }


def backends() -> dict[str, Any]:
    raw = kubectl(
        "-n", "ingress-nginx", "exec", "deploy/ingress-nginx-controller", "--",
        "curl", "-s", "http://127.0.0.1:10246/configuration/backends",
    )
    return {b["name"]: b for b in json.loads(raw)}


def canary_is_live_in_nginx() -> bool:
    """Does the controller's OWN configuration currently carry the canary backend?

    The instrument for the revert's wall-clock. It is the router's runtime state,
    not the Ingress object and not the annotation — the object disappears the
    instant the API server accepts the delete, which is the thing being measured
    the distance FROM.
    """
    try:
        backend = backends().get(CANARY_BACKEND_KEY)
    except Exception:  # noqa: BLE001 — a transient exec failure is not "gone"
        return True
    if backend is None:
        return False
    return bool((backend.get("trafficShapingPolicy") or {}).get("weight", 0))


def refuse_an_owned_ingress() -> None:
    """A hand-authored route must be owned by NOBODY — F-039.

    KServe generates an Ingress per InferenceService and reconciles it forever.
    Writing canary annotations onto one is accepted by the API server, works for
    a few seconds, and is then quietly undone — which looks exactly like
    ADR-011 condition 1's silently-inert canary. Asked BEFORE the first weight,
    so the answer costs a second rather than a six-minute load run.
    """
    owners = kubectl(
        "-n", NAMESPACE, "get", "ingress", CANARY_INGRESS,
        "-o", "jsonpath={.metadata.ownerReferences[*].name}", check=False,
    )
    if owners:
        raise RuntimeError(
            f"ingress {CANARY_INGRESS} is OWNED by {owners} — a controller will revert "
            "these annotations and the split will read 0% with no error anywhere (F-039)"
        )


def registered_canary_policy() -> dict[str, Any]:
    """What the controller's OWN runtime configuration says about the canary."""
    backend = backends().get(CANARY_BACKEND_KEY) or {}
    return {
        "present": bool(backend),
        "noServer": backend.get("noServer"),
        "trafficShapingPolicy": backend.get("trafficShapingPolicy"),
    }


def apply_weight(weight: int) -> dict[str, Any]:
    """Apply the weight, then require the CONTROLLER to have accepted it.

    Two different facts, and this program has now paid for confusing them twice:
    the annotation is an INTENT (and can be reverted, or discarded, without a
    word), while `noServer: true` plus a non-zero weight in the controller's
    runtime configuration is the router agreeing to draw the canary. Neither is
    the measurement — that is the counters', below — but a precondition that
    fails loudly here saves a window that would otherwise measure nothing.
    """
    text = INGRESS_MANIFEST.read_text()
    if WEIGHT_PLACEHOLDER not in text:
        raise RuntimeError(f"{INGRESS_MANIFEST} no longer carries {WEIGHT_PLACEHOLDER}")
    manifest = text.replace(WEIGHT_PLACEHOLDER, str(weight))
    proc = subprocess.run(  # noqa: S603 — fixed argv, no shell
        ["kubectl", "--context", "kind-mlops-taxi", "apply", "-f", "-"],
        input=manifest, capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"applying canary weight {weight} failed: {proc.stderr.strip()}")
    refuse_an_owned_ingress()
    deadline = time.perf_counter() + 30.0
    policy = registered_canary_policy()
    while time.perf_counter() < deadline:
        if policy["noServer"] is True and (policy["trafficShapingPolicy"] or {}).get(
            "weight"
        ) == weight:
            return policy
        time.sleep(1.0)
        policy = registered_canary_policy()
    raise RuntimeError(
        f"the controller did not register {CANARY_BACKEND_KEY} as a canary at weight "
        f"{weight} within 30 s — it reports {policy}. Refusing to measure a window whose "
        "split is not configured (ADR-011 condition 1 / F-039)."
    )


def remove_canary_route() -> None:
    kubectl("-n", NAMESPACE, "delete", "ingress", CANARY_INGRESS, "--ignore-not-found")


def champion_pod_uid() -> str:
    return kubectl(
        "-n", NAMESPACE, "get", "pods",
        "-l", f"serving.kserve.io/inferenceservice={CHAMPION}",
        "-o", "jsonpath={.items[0].metadata.uid}",
    )


def champion_alias_version() -> str:
    proc = subprocess.run(  # noqa: S603 — fixed argv, no shell
        ["uv", "run", "python", str(REPO_ROOT / "scripts/resolve_champion_storage.py")],
        capture_output=True, text=True, check=True, cwd=REPO_ROOT,
    )
    return str(json.loads(proc.stdout)["version"])


def share(before: dict[str, float], after: dict[str, float]) -> dict[str, Any]:
    """The two witnesses' shares over one window, plus the counts behind them."""
    ingress_total = after["ingress_total"] - before["ingress_total"]
    ingress_canary = after["ingress_canary"] - before["ingress_canary"]
    champion_pod = after["champion_pod"] - before["champion_pod"]
    canary_pod = after["canary_pod"] - before["canary_pod"]
    pod_total = champion_pod + canary_pod
    return {
        "ingress": {
            "requests": round(ingress_total, 1),
            "to_canary": round(ingress_canary, 1),
            "canary_share_pct": round(100.0 * ingress_canary / ingress_total, 2)
            if ingress_total
            else None,
        },
        "pods": {
            "champion": round(champion_pod, 1),
            "canary": round(canary_pod, 1),
            "canary_share_pct": round(100.0 * canary_pod / pod_total, 2) if pod_total else None,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    RECORD.parent.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {
        "story": "M6-S4",
        "what": "canary 10% -> 100% -> revert, under sustained load",
        "prediction": PREDICTION,
        "superseded_predictions": SUPERSEDED_PREDICTIONS,
        "shape": {
            "rate_per_second": RATE,
            "concurrency": CONCURRENCY,
            "mix": "hazards",
            "seconds": T_END,
            "settle_seconds_after_each_weight_change": SETTLE_SECONDS,
            "scrape_interval_seconds": 15,
            "note": (
                "counters are cumulative and scraped every 15 s, so each window's covered "
                "interval is its stated length +/- one scrape. That moves the COUNTS and "
                "not the SHARE, which is what every check below is written against."
            ),
        },
        "phases": {},
    }
    RECORD.write_text(json.dumps(record, indent=2) + "\n")
    print(f"[canary] prediction written to {RECORD} — nothing has been applied yet")

    if args.dry_run:
        print("[canary] --dry-run: would run one 360 s load at 4 req/s against the CHAMPION's")
        print("         host, applying canary-weight 10 at t=60, 100 at t=180, and deleting")
        print("         the canary Ingress at t=270. Nothing was applied.")
        return 0

    endpoint = Endpoint(name=CHAMPION, namespace=NAMESPACE, route=ROUTE)
    uid_before = champion_pod_uid()
    alias_before = champion_alias_version()
    print(f"[canary] champion predictor uid {uid_before}")
    print(f"[canary] @champion is version {alias_before} (read before any change)")

    # Edges are captured from inside the load run so their timestamps come off the
    # same clock as the requests they bound.
    edges: dict[str, dict[str, float]] = {}
    events: list[dict[str, Any]] = []
    revert: dict[str, Any] = {}

    def mark(name: str, elapsed: int) -> None:
        edges[name] = counters()
        events.append({"at_s": elapsed, "edge": name})

    def on_second(elapsed: int) -> None:
        if elapsed == 5:
            mark("baseline_start", elapsed)
        elif elapsed == T_CANARY_10 - 5:
            mark("baseline_end", elapsed)
        elif elapsed == T_CANARY_10:
            policy = apply_weight(10)
            events.append({"at_s": elapsed, "action": "canary-weight: 10", "registered": policy})
            print(f"[canary] t+{elapsed}s  canary-weight 10 applied and REGISTERED {policy}")
        elif elapsed == T_CANARY_10 + SETTLE_SECONDS:
            mark("w10_start", elapsed)
        elif elapsed == T_CANARY_100 - 5:
            mark("w10_end", elapsed)
        elif elapsed == T_CANARY_100:
            policy = apply_weight(100)
            events.append({"at_s": elapsed, "action": "canary-weight: 100", "registered": policy})
            print(f"[canary] t+{elapsed}s  canary-weight 100 applied and REGISTERED {policy}")
        elif elapsed == T_CANARY_100 + SETTLE_SECONDS:
            mark("w100_start", elapsed)
        elif elapsed == T_REVERT - 5:
            mark("w100_end", elapsed)
        elif elapsed == T_REVERT:
            # THE REVERT, TIMED ON THE CONTROLLER'S OWN STATE.
            started = time.perf_counter()
            remove_canary_route()
            deleted = time.perf_counter()
            while canary_is_live_in_nginx():
                if time.perf_counter() - started > REVERT_BUDGET_SECONDS:
                    break
                time.sleep(0.25)
            cleared = time.perf_counter()
            revert.update(
                {
                    "issued_at_s": elapsed,
                    "api_delete_seconds": round(deleted - started, 3),
                    "nginx_cleared_seconds": round(cleared - started, 3),
                    "budget_seconds": REVERT_BUDGET_SECONDS,
                    "instrument": (
                        "the ingress-nginx controller's own /configuration/backends, polled "
                        "every 0.25 s from the moment the delete was issued; resolution is "
                        "bounded by one kubectl exec (~0.5 s), which is stated rather than "
                        "hidden because the budget it is measured against is 120 s"
                    ),
                }
            )
            events.append({"at_s": elapsed, "action": "canary Ingress DELETED"})
            print(f"[canary] t+{elapsed}s  reverted in {revert['nginx_cleared_seconds']}s")
        elif elapsed == T_REVERT + SETTLE_SECONDS:
            mark("reverted_start", elapsed)
        elif elapsed == T_END - 5:
            mark("reverted_end", elapsed)

    print(f"[canary] one {T_END} s load run at {RATE} req/s begins — the weight changes ride")
    print("         inside it, so the split and the latencies share one clock")
    try:
        result = run_load(
            endpoint,
            rate=RATE,
            seconds=T_END,
            concurrency=CONCURRENCY,
            mix="hazards",
            label="m6-s4 canary release rehearsal",
            note="10% -> 100% -> revert, all on the champion's own host",
            on_second=on_second,
        )
    finally:
        # The wire goes back where it started even if the run dies mid-window.
        remove_canary_route()

    # The tail edge can land after the last worker has finished; take it here.
    if "reverted_end" not in edges:
        edges["reverted_end"] = counters()

    record["events"] = events
    record["revert"] = revert
    record["load"] = result.as_record()
    record["phases"] = {
        "baseline": share(edges["baseline_start"], edges["baseline_end"]),
        "canary_10": share(edges["w10_start"], edges["w10_end"]),
        "canary_100": share(edges["w100_start"], edges["w100_end"]),
        "reverted": share(edges["reverted_start"], edges["reverted_end"]),
    }
    uid_after = champion_pod_uid()
    alias_after = champion_alias_version()
    record["champion"] = {
        "predictor_pod_uid_before": uid_before,
        "predictor_pod_uid_after": uid_after,
        "alias_version_before": alias_before,
        "alias_version_after": alias_after,
    }

    p = record["phases"]
    w10_ing = p["canary_10"]["ingress"]["canary_share_pct"]
    w10_pod = p["canary_10"]["pods"]["canary_share_pct"]
    w100_ing = p["canary_100"]["ingress"]["canary_share_pct"]
    w100_pod = p["canary_100"]["pods"]["canary_share_pct"]
    checks = {
        "c1_baseline_moved_nothing": p["baseline"]["ingress"]["canary_share_pct"] == 0.0,
        "c2_weight_10_observed_from_the_ingress_counter": w10_ing is not None
        and abs(w10_ing - 10.0) <= SHARE_TOLERANCE_POINTS,
        "c3_weight_10_corroborated_by_the_pods_own_counters": w10_pod is not None
        and abs(w10_pod - w10_ing) <= 3.0,
        "c4_weight_100_shifted_everything": w100_ing is not None and w100_ing >= 95.0,
        "c5_weight_100_corroborated_by_the_pods_own_counters": w100_pod is not None
        and abs(w100_pod - w100_ing) <= 3.0,
        "c6_revert_returned_the_split_to_zero": p["reverted"]["ingress"]["canary_share_pct"]
        == 0.0
        and p["reverted"]["pods"]["canary"] == 0.0,
        "c7_revert_inside_the_budget": bool(revert)
        and revert["nginx_cleared_seconds"] <= REVERT_BUDGET_SECONDS,
        "c8_no_request_failed_all_run": len(result.errors) == 0,
        "c9_one_version_served_throughout": result.served_versions == ["2"],
        "c10_the_champion_pod_was_never_replaced": uid_before == uid_after,
        "c11_the_alias_never_moved": alias_before == alias_after == "2",
    }
    record["checks"] = checks
    record["verdict"] = "PASS" if all(checks.values()) else "FAIL"
    RECORD.write_text(json.dumps(record, indent=2) + "\n")

    print()
    for name, phase in record["phases"].items():
        print(
            f"  {name:<10} ingress {phase['ingress']['to_canary']:>6.0f}/"
            f"{phase['ingress']['requests']:<6.0f} = {phase['ingress']['canary_share_pct']}%"
            f"   pods {phase['pods']['champion']:.0f}/{phase['pods']['canary']:.0f}"
            f" = {phase['pods']['canary_share_pct']}%"
        )
    print(
        f"\n  revert: nginx cleared the canary backend {revert.get('nginx_cleared_seconds')}s "
        f"after the delete was issued (budget {REVERT_BUDGET_SECONDS:.0f}s)"
    )
    print(
        f"  load:   {len(result.attempts)} requests, {len(result.errors)} failed, "
        f"p50 {result.percentiles('latency_ms')['p50']:.1f} ms, "
        f"p95 {result.percentiles('latency_ms')['p95']:.1f} ms "
        f"at {result.achieved_rate:.2f} req/s"
    )
    print(f"\n[canary] {RECORD}")
    for name, ok in checks.items():
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
    print(f"[canary] {record['verdict']} — {sum(checks.values())}/{len(checks)} checks")
    return 0 if record["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
