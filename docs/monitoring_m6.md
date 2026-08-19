# The eyes — Prometheus, Grafana, and what a request looks like from four sides (M6-S1)

*Executor session, 2026-08-19. Role blocks: SRE (Accountable), MLOps (Responsible).*
*Nothing in this story promotes, moves an alias, or sets a threshold. `@champion`
is version 2 before and after and is never read by the deployed code.*

---

## 0. What this story does and does not claim

It claims: metrics from the predictor, the ingress controller, kube-state-metrics
and the kubelet's cAdvisor are being collected; a real rider request becomes a
number in Prometheus, proved by sending one and watching the counter move; and a
serving board provisioned from checked-in JSON renders every one of its panels
from live data.

It does not claim: that any of those numbers is *good*. **No threshold, no alert
rule, no SLO exists after this story** — those are M6-S2's, and a bar set here
would be a bar set from the number just observed (gotchas #63/#74 in bar form).
The board deliberately draws no threshold line, and a test fails if one appears.

---

## 1. The backup, first

The M4-S2/M5-S1 precedent: new tenants land beside state that has no other copy,
so the copy gets refreshed first.

```
[backup] destination /home/longt/dvc-remote/nyc-taxi-platform-backups/2026-08-19T05-59-36Z
[backup] 6 database(s) on the server: flyte marts metabase mlflow optuna postgres
  flyte 91.9KiB · marts 1.2GiB · metabase 330.3KiB · mlflow 67.9KiB · optuna 27.0KiB · postgres 387.0B
[backup-minio] mirrored flyte-data: 184 object(s), 0.7 MiB
[backup-minio] mirrored mlflow-artifacts: 147 object(s), 443.3 MiB
[backup-minio] ok  331 object(s) verified on disk by count AND bytes
total on disk: 1.6GiB
```

Nobody edited a list of databases or buckets: the script enumerates them from the
server, which is why the `serving` identity's objects (created at M5-S2, after the
previous backup) are covered. **Restore is still not rehearsed** — M6-S5's.

---

## 2. The probe that decided the scrape config

The kickoff said the predictor's metrics endpoint was *believed* to be `/metrics`
on 8082, and said to probe it. That instruction earned itself immediately.

KServe stamps its own hint on the predictor pod:

```
prometheus.kserve.io/path: /metrics
prometheus.kserve.io/port: "8080"
serving.kserve.io/enable-prometheus-scraping: "false"
```

`make probe-mlserver-metrics` asked the live pod instead:

```
predictor pod: nyc-taxi-eta-predictor-7ff5ccd649-xj2q6  (ns/serving)
=== :8082/metrics -> HTTP 200, 119 lines, 24 distinct series ===
  serving-relevant series (14):
    model_infer_request_success_total   model_infer_request_failure_total
    model_infer_request_duration_{count,sum}
    rest_server_requests_total          rest_server_requests_in_progress
    rest_server_request_duration_seconds_{bucket,count,sum}
  one whole sample per serving-relevant series (labels included):
    model_infer_request_success_total{model="nyc-taxi-eta",version="None"} 13.0
    rest_server_requests_total{app_name="mlserver",method="GET",
        path="/v2/models/{model_name}/ready",status_code="200"} 2.0
    rest_server_request_duration_seconds_bucket{app_name="mlserver",le="0.005",…} 2.0
=== :8080/metrics -> FAILED (HTTPError: HTTP Error 404: Not Found) ===
```

**KServe's own annotation points at a 404.** A scrape config written from it would
have produced a target that is permanently DOWN and a serving board that renders
empty rectangles — which is the same picture as a quiet system. Gotcha #70 ("ask
the server") for the second time, on a second server.

Three facts from that dump that shape everything downstream:

* `rest_server_requests_total` carries **`status_code`**, so the 5xx-vs-422 split
  the SLO document will need (ours vs the request's, F-019's typed refusal) exists
  at the source and does not have to be derived.
* `rest_server_request_duration_seconds_bucket` is a **histogram**, so a real
  server-side p95 is available — a different instrument from M5-S4's client-side
  p95, and it will read lower because it excludes the wire.
* `model_infer_request_success_total{model="nyc-taxi-eta",version="None"}` — **the
  model VERSION is not in the metric.** A-4 (a version-mismatch alert) cannot be
  built from mlserver's counters; the version lives on the response body, which is
  where `verify-m5` §2 already reads it. Written down here so M6-S2 does not
  discover it while writing the rule.

The probe stays in the repo, and a test fails if the values file drifts back to
8080 or if the probe is deleted: a pinned port whose measurement has been thrown
away is a remembered number.

---

## 3. The stack, and why it is the small one

`prometheus-community/prometheus` **29.27.0** (Prometheus **v3.14.0**) +
`grafana/grafana` **10.5.15** (Grafana **12.3.1**), both read live with
`helm search repo … --versions`.

**Not `kube-prometheus-stack`.** That chart brings the prometheus-operator and
~10 CRDs whose entire job is to turn ServiceMonitor objects into the nine-line
scrape config this repo now carries in a values file. Two costs decided it, and
both are specific to this program rather than general taste: CRDs are
cluster-scoped state on a cluster that is **stateful and must not be rebuilt**, so
a heavy install is a heavy thing to reverse; and M6-S2's alert rules would become
PrometheusRule objects **living in the cluster**, when the rule since M1-S5 is that
what renders is checked in and converged. `kube-prometheus-stack` is the recorded
fallback if this route ever hits its 3-attempt wall.

Off, with reasons, not by omission:

| Component | State | Why |
|---|---|---|
| node-exporter | **off** | Nothing in M6's alert plan or board reads a host-level metric. Container CPU and CFS throttling come from the kubelet's cAdvisor, already scraped. A 3-node DaemonSet for metrics with no reader is footprint. |
| pushgateway | **off** | M7's (drift), named by port in the kickoff's out-of-scope list. One value flips it on. |
| Alertmanager | **on** | M6-S2 must watch an alert fire end to end; an alert with no receiver is a row in a UI. |
| kube-state-metrics | **on** | A-5's source (restarts, readiness, replica counts). |

**The UIs ride the existing route** (M6 law 1): host-based Ingress on the 8081
controller M5-S1 installed — `prometheus.local`, `grafana.local`. Ports 3000 and
9091 stay reserved names in CLAUDE.md's port family, not routes, until a
PO-sanctioned rebuild; kind publishes host ports at cluster-CREATE only.

---

## 4. The wire change, and the deadlock it uncovered

`controller.metrics.enabled: true` on ingress-nginx buys the one instrument that
can see a request which never reached a pod — `nginx_ingress_controller_requests`,
labelled by host and status. It is also the per-backend counter M6-S4's canary
will be **observed** from, as opposed to asserted from an annotation.

Enabling it rolls the controller Deployment, which is the only route into the
cluster. What happened instead:

```
$ kubectl -n ingress-nginx get pods
ingress-nginx-controller-5988ff9b7c-mr9mj   0/1   Pending   0   10m
ingress-nginx-controller-74dcb9db98-whhtb   1/1   Running   0   3h14m

Warning  FailedScheduling  0/3 nodes are available: 1 node(s) didn't have free
ports for the requested pod ports, 2 node(s) didn't match Pod's node
affinity/selector.
```

**A RollingUpdate can never complete here.** The values file pins the controller
to one node (it must — that is the node whose port 80 kind publishes as 8081) with
`hostPort` and `replicaCount: 1`. The chart's default strategy is RollingUpdate
with maxSurge 25% / maxUnavailable 25%, which at one replica means *start the new
pod, then stop the old one* — and the new pod cannot start, because the old one is
holding port 80 on the only node it is allowed to run on.

The failure mode is the interesting part: **nothing was broken.** The old pod kept
serving, and a 420-second availability probe at 2 req/s recorded **840/840 ok**.
The helm upgrade would simply have hit its 20-minute timeout with a perfectly
healthy route. A rollout that can never complete is not a safe rollout; it is an
invisible one, and the "zero outage" it produced was the strongest possible
evidence for the wrong conclusion.

Fixed by `updateStrategy: {type: Recreate}` — the old pod is deleted before the
new one starts — with the honest cost stated in the values file: **every future
change to this Deployment costs a real outage of the only route into the cluster.**
That cost is unavoidable, not chosen: any strategy that keeps the old pod alive
cannot schedule the new one.

Measured, on the roll that actually happened:

```
[route-probe] M6-S1: ingress-nginx controller.metrics.enabled + updateStrategy
Recreate roll: 570/600 ok, 30 failed, outage=15.0 s
```

`automation/runs/m6-monitoring/ingress-metrics-roll.json` (tracked), anchored
first-failure → first-success (gotcha #75 — the error-span anchor would say
something else, and M5-S4's first attempt shipped that mistake). **15.0 s** sits
between the two numbers this program already owns: 14.53 s for a killed predictor
pod (M5-S4) and 18.24 s for a stop/start (M5-S5). Three different mutations, three
measurements within four seconds of each other — which is a real input to M6-S2's
availability target, and it is why an availability SLO that forbids what every
deploy costs is a target the program plans to violate.

**The clean-up cost one helm rollback.** Killing the timed-out upgrade left the
release in `pending-upgrade`, which refuses the next upgrade; `helm rollback
ingress-nginx 2` cleared it without touching the running pod (which already matched
revision 2's template).

---

## 5. What the accept check asks, and the three defects it found

`make monitoring-accept` is deliberately **not** a target list. `up == 1` proves
Prometheus can open a TCP connection; it is exactly as green when the counter it
scrapes never moves. So the middle leg reads a counter, **sends one real quote**,
waits for a scrape, and reads it again — and the board leg **parses every PromQL
expression out of the checked-in dashboard JSON** and executes it (re-typing a
query here would give the repo two copies, and this one would be the copy that
stayed right — F-017).

Its first run was GREEN and should not have been. Three panels reported "0 series"
and the checker printed, in green, *"legal for a counter with no traffic yet"*.
Three real defects were sitting inside that sentence:

1. **The ingress metrics Service was never discovered.** The chart creates it and
   annotates it with nothing; Prometheus's endpoint-discovery job keys on exactly
   `prometheus.io/scrape`. Every target was up, and the edge panel was empty,
   because a target list cannot tell you about a component that was never found.
   Fixed with two annotations — a Service change, so **no pod roll and no outage**.
2. **The scrape interval could not describe the board.** The chart's global default
   is 1 minute; a `rate(x[1m])` needs two samples inside its window, so both
   container panels evaluated to nothing. Set to **15s** — M6's events are minutes
   long (a canary shift, a kill, a gameday injection), and a sampling interval of
   the same order as the event cannot describe it.
3. **A permanently-down target.** KServe's controller advertises itself for
   scraping and then serves through kube-rbac-proxy over HTTPS with a cert-manager
   certificate: `x509: cannot validate certificate`. A permanently-red target is
   worse than an absent one — it is what teaches an on-call to stop reading the
   target list. Fixed by a **deep merge onto the chart's own job** (two keys,
   `bearer_token_file` + `tls_config.insecure_skip_verify`), *not* by copying its
   12-entry `relabel_configs` list, because helm replaces lists and a copied list
   is right on the day it is pasted.

So the check now **fails on an empty panel**. If a future panel is legitimately
empty, this goes red and a human decides — which is the correct place for that
judgement, and it is exactly the judgement the green version was making silently.

The passing run:

```
-- 1. the route answers --
ok  Prometheus answers through the 8081 ingress as Host: prometheus.local (/-/healthy -> 200)
ok  Grafana answers through the same route as Host: grafana.local (/api/health -> 200, version 12.3.1)

-- 2. the scrape jobs --
ok  scrape job 'kserve-predictors': 1/1 target(s) up
ok  scrape job 'kubernetes-service-endpoints': 6/6 target(s) up
ok  scrape job 'kubernetes-nodes-cadvisor': 3/3 target(s) up
ok    predictor target nyc-taxi-eta -> http://10.244.1.12:8082/metrics (up)

-- 3. one real request becomes a number --
    counter before: 17
ok  one real quote sent through the live endpoint: [quote] 2019-07-04T09:15:00
      zone 132 -> 48, 1 passenger(s)  ->  39.0019 minutes
    waiting 40s for a scrape (the job's interval is 15s) …
    counter after:  18
ok  the request reached Prometheus: inference counter 17 -> 18 (+1) — a scrape
    target being 'up' could not have told us this

-- 4. the board, and every query on it --
ok  Grafana serves the provisioned board 'crosstown-serving' with 7 panel(s) —
    provisioned from git, not clicked
    panel 2.A: 1 · 3.A: 1 · 3.B: 1 · 3.C: 1 · 4.A: 1 · 4.B: 1 · 5.A: 2 ·
    6.A: 1 · 6.B: 1 · 7.A: 1 · 7.B: 1   (series)
ok  all 11 panel queries executed against Prometheus and every one returned live
    series — no panel on this board renders an empty rectangle

[monitoring-accept] GREEN — 10 sub-check(s) passed.
```

That quote — `39.0019 minutes` — is the same value M5-S2's accept check and
M5-S3's parity record carry for the same row. It was not engineered to match; it is
what asking the same endpoint the same question returns.

---

## 6. The board

`analytics/grafana/dashboards/serving.json`, provisioned through a ConfigMap the
deploy builds **from those files every run**, so the board in the cluster is the
board in git (M1-S5's Metabase property, reached by a different mechanism). Seven
panels; its first panel is text, and it says which instrument each number comes
from — because M5 measured the same quantities from the client side and the two are
not the same number:

* **predictor-side** (mlserver :8082) — excludes the network and the ingress hop,
  so it reads lower than `make load`'s p95 (M5-S4: p50 17.2 / p95 104.2 ms at
  4 req/s, concurrency 8 — the client's number, and the one the SLO doc will own);
* **edge** (ingress-nginx) — includes that hop, and is the only place a request
  that never reached the pod appears at all;
* **container** (cAdvisor) — CPU against the 2-core limit, and `nr_throttled`,
  because a load test at the limit measures the quota rather than the service
  (gotcha #74) and that shows up as latency, never as an error.

The isvc panels are broken out **by label, not by name**, so M6-S3's shadow and
M6-S4's canary appear the moment they exist without anyone editing a scrape config.

---

## 7. Idempotence, and the wire where M5 left it

A third full run, changing nothing:

```
$ kubectl -n monitoring get pods
grafana-6869f5d4d4-9zqw9                         2/2  Running  0  9m16s
prometheus-alertmanager-0                        1/1  Running  0  11m
prometheus-kube-state-metrics-5cdc869448-qhkc2   1/1  Running  0  11m
prometheus-server-7dd5d95695-q276z               2/2  Running  0  11m
$ kubectl -n ingress-nginx get pods
ingress-nginx-controller-5988ff9b7c-jppjw        1/1  Running  0  11m
```

Every pod older than the run that "upgraded" it, 0 restarts — the M4-S2 shape.
Worth noting for M6-S2: the **Prometheus server pod did not restart when its scrape
config changed** either. The chart runs a configmap-reload sidecar, so a rules file
lands without a restart. S2's alert rules are therefore cheap to iterate on.

`DRY_RUN=1 make deploy-monitoring` was run first and mutated nothing — helm
included (gotcha #30), verified against `helm list -A`.

And the acceptance condition that matters most, run after every mutation:

```
[verify-m5] GREEN — every M5 sub-check passed.        (49 sub-checks, 7 sections)
```

`@champion` is version 2, the served version's `feature_set` tag still equals
`configs/train.yaml`'s `features.version`, and the live endpoint still reproduces
the parity record at 0.000e+00. The eyes were installed; the wire is where M5 left
it.

---

## 8. What M6-S2 inherits, precisely

* **A histogram, not a gauge**, for server-side latency — `histogram_quantile` over
  `rest_server_request_duration_seconds_bucket`, and it is a *different* number from
  the SLO's client-side p95. The SLO document must say which instrument each target
  is measured with.
* **`status_code` at the source**, so the 5xx-vs-422 split (A-2 vs A-3) is a label
  selector and not a derivation.
* **No model version in any mlserver metric** (`version="None"`). A-4 needs another
  source; the response body carries it, and `verify-m5` §2 already reads it there.
* **Three measured deployment outages within four seconds of each other** — 14.53 s
  (killed pod), 15.0 s (route roll), 18.24 s (stop/start). An availability target
  must price these in, or it forbids the act of deploying.
* **`serverFiles.alerting_rules.yml` already exists and is empty**, on purpose, so
  S2's diff is about alerts rather than about plumbing.
* **A rules change costs no restart** (configmap-reload sidecar), so the
  prediction → inject → observe → clear loop is minutes, not tens of minutes.
* **The CPU request re-size is still S2's**, and this board's panel 6 is the
  before/after instrument for it.

---

## 9. Judgement (M6-S2) — the SLOs, the alerts, and the one number that was wrong

The document is `docs/slo_serving.md` and it OWNS every serving threshold; this
section records what was built and what building it found.

### 9.1 The rules, and how they reach the cluster

`infra/monitoring/alerting_rules.yml` is a **plain Prometheus rules file** — the
format `promtool check rules` reads — and it is the only copy.
`scripts/render_alert_rules.py` parses it, refuses it if any rule lacks an
`expr`, a `severity`, a PRR signal id or a written `why`, and nests it under the
chart's `serverFiles."alerting_rules.yml"` as a second `--values` overlay that
`deploy_monitoring.sh` passes to helm and deletes on EXIT. The chart's own key
stays an empty map on purpose, and a test fails if it stops being empty: two
files that can both hold rules is the twin problem this program has already paid
for four times.

```
$ make alert-rules
[alert-rules] ok  7 rule(s) validated
[alert-rules]     A-1  PredictorLatencySLOBurning             for=5m   severity=warning
[alert-rules]     A-2  ServingEdge5xxRateHigh                 for=5m   severity=critical
[alert-rules]     A-3  PredictorRequestRejectionRateHigh      for=2m   severity=warning
[alert-rules]     A-5  PredictorNoAvailableReplica            for=2m   severity=critical
[alert-rules]     A-5  PredictorRestartFlapping               for=0m   severity=warning
[alert-rules]     A-6  PredictorCpuThrottledSustained         for=10m  severity=warning
[alert-rules]     A-7  PredictorStorageInitializerNotReady    for=3m   severity=critical

$ (Prometheus /api/v1/rules, read back)
group crosstown-serving interval 15
  … all 7 rules, state=inactive, health=ok
```

§6's promise held exactly: **the Prometheus pod did not restart** for a config
change that added seven rules (38 m old across the upgrade, 0 restarts).

### 9.2 The alert that fired, and the order it fired in

`make alert-fire-drill` writes its prediction to disk **before** it injects
anything (`automation/runs/m6-slo/alert-fire-prediction.json`), then sends two
request shapes the endpoint really produces — a malformed V2 body (**422**,
F-030's class) and a body the model's logged signature refuses (**500**, F-032's
class, the half-finished rollback). One injection, two alerts with different
sustain windows, so the drill must predict a **sequence**:

```
PREDICT A-3 fires at about T+150s (for=120s)   ->   OBSERVED T+150.5s
PREDICT A-2 fires at about T+330s (for=300s)   ->   OBSERVED T+330.6s
PREDICT the order A-3 then A-2                 ->   OBSERVED in that order
PREDICT A-1/A-5/A-5/A-6/A-7 stay inactive      ->   all five inactive
Alertmanager holds 2 alert(s): [both]          ->   they reached a receiver, not just a UI
an ordinary quote DURING the injection: 39.0019 minutes   ->   errors, not an outage
both cleared -> inactive 315.1s after the injection stopped
[alert-drill] GREEN — 11 check(s) passed.
```

Injected: **662 × 422 and 661 × 500**. Nothing was deleted, scaled or promoted;
`@champion` was read and never written. The five negative predictions are the
part worth keeping — a drill that predicts only "something fires" cannot be
wrong, and S5's gameday is graded on **distinguishable** signatures.

### 9.3 F-035 — two of the seven PRR signals cannot be rules here

Both for the same reason: **the fact lives in a client, and no client here is
scraped.** A-3's client half (F-019's `UncoveredDateError`) was the alert the M6
kickoff expected to be free — measured, it is not available at all:

```
sum(rest_server_requests_total{path=~".*infer"})   ->  22
make quote --at 2031-07-04T09:15:00   ->  REFUSED (422) … covers through 2030, exit 2
sum(...) after a scrape                            ->  22
```

A-4 needs `served version != registry @champion`, and no mlserver metric carries
a version (F-034) while MLflow exports no Prometheus metrics — there are not two
series to compare. Both are dispositioned in `docs/slo_serving.md` §6 with
options and costs, both land on M7's pushgateway, and the renderer FAILS if the
implemented set and the documented absences ever disagree.

### 9.4 The instrument that cannot measure what it looks like it measures

`histogram_quantile(0.95, …)` on mlserver's buckets reported **111.6 ms** for a
window in which the client — timing the whole round trip, i.e. strictly more —
measured **84.4 ms**. A quantile over a superset cannot exceed one over a subset,
so the histogram's number is an interpolation across a bucket 150 ms wide
(`le` jumps 0.1 → 0.25, and 13 of 259 observations live in that gap). So
**SLO-L1's target is a bucket EDGE (250 ms) and A-1 counts requests beyond it**
instead of estimating a quantile. Full working in `docs/slo_serving.md` §2.1.

### 9.5 The CPU request, and the prediction this story got wrong

`200m → 1500m` (limit unchanged, memory request unchanged so the comparison has
one cause), argued from M5-S4's measured 1.31 cores plus ~15%, deliberately
below the limit so the pod stays Burstable.

| | p50 | p95 | p99 | max | ≥N of 240 over the 250 ms target |
|---|---|---|---|---|---|
| before `200m` | 29.4 ms | 84.4 ms | 433.7 ms | 692.9 ms | 2 |
| after `1500m` | 29.5 ms | 112.7 ms | 118.9 ms | 142.9 ms | **0** |

The prediction — *a request is not a cap, so p95 should not move materially* —
holds: p50 moved 0.175 ms, and p95's 28 ms sits inside the run-to-run spread of
this identical shape (M5-S4 measured 104.2 ms). The tail's improvement is **not**
claimed as an effect: the before run's slow requests were in its 10th and 11th
seconds, mid-run, which is host contention and not a scheduler's arithmetic.

**What this story predicted wrong was the cost of applying it.** The SLO
document's first draft said a re-deploy costs ~15–18 s, by analogy with three
measured mutations. Measured: **0.5 s, one 502 of 400 samples**. At one replica
`RollingUpdate`'s `maxUnavailable: 25%` floors to **zero**, so a surge pod must
be ready before the old one goes — the other three all destroy the only pod
first. Corrected in §4.1 with the mechanism, and it is M6-S4 that inherits it: a
canary weight flip or a re-deploy is nearly free, and the ~15 s figure belongs
only to mutations that destroy the pod first. Gotcha **#80**.

### 9.6 F-036 — the deploy's readiness wait could never succeed

Found by running `make serve`: it hung for **fifteen minutes** and then failed,
over an InferenceService with every condition `True` and its pod `Running 1/1`.
kubectl v1.36 ignores conditions while `observedGeneration` trails `generation`,
and KServe v0.20.0 leaves it behind on every re-deploy (`generation=3` /
`observedGeneration=2`). Under `set -e` the timeout takes the accept check with
it, so the single failure mode is a correct deploy reporting as a broken one.
Fixed to the `--for=jsonpath=` form, verified live; `rollout status` stays FIRST
(gotcha #71's fix untouched). Gotcha **#79**.

### 9.7 What M6-S3/S4/S5 inherit from this story

* **A deploy costs 0.5 s, not 15 s** (§9.5) — S4's canary and rollback timings
  should be argued from that, and the ~15 s numbers reserved for pod destruction.
* **`make serve` works again** (§9.6). S4 runs it at least twice.
* **A-2 has NOT been fired by a real outage** — only by injected 5xx. Its
  `for: 5m` means a ~20 s drill cannot fire it, which is why the kickoff routes
  that proof to S5's gameday kill scenario. A-5 likewise: it is the rule that
  fires without traffic and it has never fired.
* **The board draws no threshold line** and S2 did not add one. Now that the SLO
  numbers exist, a threshold annotation on panel 3 is a legitimate S3+ nicety —
  and it must read the number from the same place A-1 does, or it becomes a twin.
* **The error budget arithmetic is in §4** of the SLO doc, so S4's canary shifts
  and S5's injections can be priced rather than worried about.
