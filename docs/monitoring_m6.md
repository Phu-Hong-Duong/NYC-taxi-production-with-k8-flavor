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
