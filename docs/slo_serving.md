# Serving SLOs — the quote endpoint

**Owner:** SRE (accountable). **Written:** 2026-08-19 (M6-S2). **Scope:** the
`nyc-taxi-eta` InferenceService as it is deployed today — one replica, KServe
Standard mode, no canary, reached through the 8081 ingress.

This document OWNS the numbers. Nothing else in the repo may invent a serving
threshold: `infra/monitoring/alerting_rules.yml` implements the ones below and
every rule's `why` annotation points back here. Loosening or tightening a target
is a **PO fork**, never an edit (the constitution's gate rule, applied to SLOs).

---

## 0. The two rules this document was written under

**(1) No target is set equal to a number that was just measured.** That is
gotchas #63 and #74 in bar-form, and this program has already paid for both: a
cache bar measured on the wrong clock called a 98.7% saving a failure, and a
load test run at the CPU limit measured the quota instead of the service. A
target copied from an observation reports the past and cannot be violated by the
present. **Every target below is argued from two things and says which:** the
*harm* it exists to prevent, and the *measured headroom* between where the
service works and where it is observed to degrade.

**(2) Every number states its instrument, and the instruments disagree.** This
milestone found out the hard way that they do (§2). A latency figure without its
instrument and its load shape is not comparable to itself.

---

## 1. What this service is, in the terms an SLO needs

A rider asks for an ETA and waits, on a screen, for one number. The request is
**one synchronous call inside an interactive flow** — not a batch job, not a
background refresh. That single fact sets the shape of every target here:

* **Latency is the product.** A quote that arrives late is a quote nobody read.
* **A 5xx is an outage; a 4xx is a working guard.** They are counted separately
  and only one of them spends the error budget (§3, SLO-A1 vs SLO-R1). Folding
  F-019's typed refusal into an error rate would page the on-call for a
  data-horizon problem, and hiding it would let the horizon expire in silence.
* **There is one replica and no canary**, so a pod loss is a full outage of the
  only route in. Measured: **14.53 s** (killed pod, M5-S4) · **15.0 s** (ingress
  roll, M6-S1/F-033) · **18.24 s** (stop/start, M5-S5) — and **0.5 s** for an
  ordinary re-deploy, which is *not* in that family and which this story got
  wrong before it measured it (§4.1). An availability target that forbids what
  every deploy costs is a target the program plans to violate, so §4 prices them
  in explicitly.

---

## 2. The instruments, and the one that cannot measure what it looks like it measures

| # | Instrument | What it sees | Where it lives |
|---|---|---|---|
| I-1 | **The load client** (`make load`, open-loop) | The whole round trip, scheduled→response, from outside the cluster. The closest thing this program has to what a rider feels. | Records under `automation/runs/` |
| I-2 | **mlserver's histogram** (`rest_server_request_duration_seconds`) | Server-side handling only, on the predictor pod. | Prometheus, job `kserve-predictors` |
| I-3 | **ingress-nginx counters** (`nginx_ingress_controller_requests`) | Every request that reached the route, by status and host — *including the ones the predictor never answered*. | Prometheus, job `kubernetes-service-endpoints` |
| I-4 | **kube-state-metrics** | Replicas available, restarts, init-container readiness. Needs no traffic to say anything. | Prometheus |
| I-5 | **the kubelet's cAdvisor** | Container CPU and CFS throttling. | Prometheus |

### 2.1 I-2's p95 is an interpolation, and it overshot the truth by 32%

Measured 2026-08-19 over one window, the SLO's own load shape:

```
I-1 (client, whole round trip, strictly MORE than the server does):  p95  84.4 ms
I-2 histogram_quantile(0.95, rate(..._bucket[3m])):                  p95 111.6 ms
```

A quantile estimated over a superset cannot legally exceed one estimated over a
subset, so **111.6 ms is not a measurement of anything**. The cause is bucket
resolution — mlserver's default boundaries jump straight from `0.1` to `0.25`,
and this service's tail lives inside that 150 ms-wide gap:

```
le=0.075  212      le=0.25   258        <- 13 observations spread over 150 ms
le=0.1    245      le=0.5    258
                   +Inf      259
```

`histogram_quantile` interpolates linearly across the bucket that contains the
95th observation, and that bucket is wider than the entire range of interest.

**The consequence, and it shapes A-1:** this stack cannot alert on a server-side
p95, so **the SLO's latency number is chosen to BE a bucket edge** and the alert
counts requests beyond it instead of estimating a quantile. `le="0.25"` is an
exact count. Nothing is interpolated anywhere in A-1.

**What is NOT claimed:** that I-2 is useless. Its counters (`status_code` at
source) are exact and A-3 depends on them; only its *quantiles* are unusable at
this bucket resolution. Re-bucketing mlserver is not a knob this program has
(the buckets are compiled into the runtime), so the workaround is the design.

---

## 3. The targets

### SLO-L1 · latency — *95% of quotes complete within 250 ms server-side*

| | |
|---|---|
| **Instrument** | I-2, on the `le="0.25"` bucket edge — an exact count, never `histogram_quantile` (§2.1) |
| **Load shape it holds at** | 4 req/s, concurrency 8, hazard mix, single replica, 2-core limit |
| **Observed at that shape** | **258 of 259 infers within 250 ms (99.6%)** — 0.4% beyond, against a 5% budget |
| **Alert** | A-1 `PredictorLatencySLOBurning`, fraction beyond 250 ms > 5%, `for: 5m` |

**The argument.** The harm bar is interactive-feel: a quote is one call inside a
page, and 250 ms is where a single in-page call stops feeling immediate. The
headroom argument is what fixes the number rather than the observation: the
service's measured **ceiling** is ~6 req/s per replica (96% of the CPU limit),
and at the first rate past it — 8 req/s — the client-side p95 is **190.1 ms**.
So 250 ms is set *above the p95 the service produces while saturated* and below
the harm bar. **A saturated service is still inside SLO; only something worse
than saturation breaks it.** That is deliberate: SLO-L1 is not a capacity alarm
(A-6 is), and a latency target that fires whenever the box is busy teaches the
on-call to route it to trash.

**Why not the other bucket edge.** `le="0.1"` was the alternative and it is
where the observation actually sits: 245/259 = **94.6%** within 100 ms. A "95%
within 100 ms" target would have been in breach *on the day it was written* —
a target set from the instrument's resolution rather than from harm. Named here
so nobody re-derives it and thinks it was missed.

### SLO-A1 · availability — *99.9% of quote-route requests answered non-5xx, monthly*

| | |
|---|---|
| **Instrument** | I-3, at the **edge** — see below |
| **Budget** | 0.1% of requests; at a sustained 4 req/s that is ~**43 minutes** of full outage per 30 days |
| **Alerts** | A-2 `ServingEdge5xxRateHigh` (>10% 5xx, `for: 5m`) · A-5 `PredictorNoAvailableReplica` (`< 1`, `for: 2m`) · A-5 `PredictorRestartFlapping` (>2 restarts in 15m) · A-7 `PredictorStorageInitializerNotReady` (`for: 3m`) |

**Measured at the edge, and that is the load-bearing choice.** When the
predictor dies, its `/metrics` endpoint dies with it: the series does not fall to
zero, it stops existing. An error-rate alert written against mlserver's own
counters therefore **cannot fire for the outage that matters most**.
ingress-nginx is a different process on a different node and is the only witness
present at the failure it reports.

**The argument for 99.9%, with the deploy cost priced in.** The budget is 43
minutes a month. This program's *measured* per-mutation outage is 14.5–18.2 s,
so the budget affords **~140 deployment-shaped outages a month** and the program
performs roughly five. The constraint 99.9% actually imposes is therefore not on
deploying — it is that **any single incident longer than 43 minutes spends the
whole month**, which is exactly the right thing for a one-replica service with no
canary to be held to. 99.99% (4.3 min/month) was rejected: it would be spent by
**fifteen** ordinary deploys, i.e. a target that forbids releasing.

**Why the alerts do not equal the SLO.** A-2's threshold is **10%**, not 0.1%,
and that is arithmetic rather than laxity: at 4 req/s the *longest healthy
recovery this program has measured* (18.24 s) is 73 failures inside a 5-minute
rate window carrying ~1200 — **6.1%**. A 5% alert would page for a system that
healed itself in eighteen seconds. 10% is unreachable by any single recovery ever
measured here and is reached immediately by a service that is simply down. The
budget is still spent by those blips; it is spent silently, which is what an
error *budget* is for and what an error *page* is not.

**A-2's blind spot, stated because it is real:** a ratio has no value when nobody
is asking. On an idle service A-2 cannot fire at all. **A-5 is the answer** — it
reads a replica count from I-4 and needs no traffic. The two are complements, not
alternatives, and neither alone covers the space.

### SLO-R1 · rejections — *fewer than 1% of inference requests rejected as malformed*

| | |
|---|---|
| **Instrument** | I-2's counters, `status_code=~"4.."` — exact, not a quantile |
| **Alert** | A-3 `PredictorRequestRejectionRateHigh`, > 1%, `for: 2m` |
| **Explicitly NOT in SLO-A1's error budget** | A 4xx is the request's fault. It is a guard working, not a service failing. |

**The argument.** F-030 is the worked example and it is why this target exists at
all: for an entire milestone ~1% of riders — every trip touching a zone with no
centroid — received a 422 because the client serialised `NaN`, and **no
instrument anywhere said so**. 1% is chosen as the bar because that is the
approximate size of a *whole class of rider* in this data (the no-geometry share
is 1.0–1.2% of every split): a defect that silently disenfranchises a class of
user is exactly the size of thing this must catch, and anything larger would have
let F-030 run forever. `for: 2m` and not 5m because a malformed body is a
client-version or encoding defect — it does not self-heal, so the sustain window
only has to outlast a probe.

### SLO-C1 · saturation — *not a user-facing SLO; an operating limit*

| | |
|---|---|
| **Instrument** | I-5, fraction of CFS periods throttled |
| **Alert** | A-6 `PredictorCpuThrottledSustained`, > 0.90, `for: 10m` |

**The argument, and it could not have been guessed.** This container is
throttled at **every rate it has ever been measured at**, including ones where it
is demonstrably healthy. From M5-S4's ramp (20 s windows, 200 CFS periods each):

| target rate | throttled fraction | client p50 | client p95 | errors |
|---|---|---|---|---|
| 2 req/s | 0.23 | 18.5 ms | 85.5 ms | 0 |
| 4 req/s | 0.51 | 19.1 ms | 108.6 ms | 0 |
| 6 req/s | 0.79 | 18.1 ms | 81.9 ms | 0 |
| 8 req/s | ~1.00 | **115.5 ms** | **190.1 ms** | 0 |

So "any throttling" fires on a healthy service, and **zero errors at every row**
is gotcha #74 rendered as a table: saturation is invisible to every error-rate
and health-check signal in this document. The threshold has to come from where
throttling starts to *hurt* — between the last harmless observation (0.79, p50
unchanged) and the first harmful one (~1.00, p50 6.4× worse). **0.90**, sustained
10m because the honest response is "add a replica or raise the limit" and nobody
should be paged at 3am for a two-minute burst.

---

## 4. The error budget, and what it is spent on

| Event | Measured cost | Budget share (30 d at 4 req/s) | Why it costs that |
|---|---|---|---|
| **A model re-deploy (`make serve`)** | **0.5 s** | 0.02% | Rolling update, surge pod allowed |
| Killed predictor pod, self-healed | 14.53 s | 0.56% | No surge — the pod is gone before a replacement exists |
| Ingress controller roll (F-033) | 15.0 s | 0.58% | `Recreate` **forced** by a `hostPort` the surge pod could not bind |
| Stop/start of the InferenceService | 18.24 s | 0.70% | `spec.replicas` removed entirely, then recreated from scratch |

Five ordinary mutations a month spend well under **1%** of the budget. This is
written down so that a future proposal to deploy more often is answered with
arithmetic rather than nerves — and so that the reverse claim, that the program
cannot afford to deploy, is answerable too.

### 4.1 The prediction in this section was wrong, and the correction is the useful part

The first draft of this table said a model re-deploy costs **~15–18 s**, by
analogy with the three numbers above it. Measured across the CPU-request roll
this story performed (`automation/runs/m6-slo/cpu-request-roll.json`, a 2 req/s
open-loop probe running across the whole `make serve`):

```
399/400 ok · 1 failed (one 502) · first failure +31.5 s -> first success +32.0 s
outage 0.5 s        (anchored first-failure -> first-success, gotcha #75)
new pod created +17.0 s, old pod terminated ~+31.5 s
```

**A re-deploy is not in the same family as the other three, and the mechanism
says why.** The predictor Deployment's strategy is
`RollingUpdate{maxSurge: 25%, maxUnavailable: 25%}`, and at **one replica**
`maxUnavailable: 25%` floors to **zero** — the Deployment is *forbidden* from
having no available pod, so a surge pod must become ready before the old one is
removed. The other three all destroy the only pod first: a kill has nothing
waiting, a stop removes `spec.replicas` altogether, and ingress-nginx was
**forced** onto `Recreate` because its surge pod could never bind the `hostPort`
the old one held (F-033). The 0.5 s that remains is the endpoint list switching.

**What this measurement's resolution actually is**, stated because the number is
small: the probe samples every 0.5 s, exactly one sample failed, so the true
outage is somewhere in (0, 1.0] s and 0.5 s is the anchored figure. A finer probe
would resolve it better; nothing in this document needs it to.

**Why this matters beyond the table.** It is M6-S4's canary and rollback that
inherit it: a weight flip or a re-deploy is nearly free, and the ~15 s figure —
which was about to be quoted at those stories as the cost of a release step —
belongs only to the mutations that destroy the pod first.

---

## 5. What the SLOs deliberately do not cover

* **Model quality.** KPI-09/KPI-10 are the model's SLIs and are measured by
  `taxi_mlops.training.evaluate` against held-out data, never from the wire
  (gotcha #15). An endpoint answering 200 with a bad number is inside every SLO
  here, and that is the promotion gate's job, not the on-call's.
* **The horizon.** F-019's refusal is correctness, not availability — see §6.
* **Anything with more than one replica.** Every number here is stated for the
  deployed topology: one replica, 2-core limit, no canary. M6-S4's canary and any
  future second replica change the availability arithmetic and this document has
  to be re-argued, not re-tuned.

---

## 6. Two of the PRR's seven signals have no metric source in this stack (F-035)

The M5 PRR named A-1…A-7 as a **plan**. Implementing it found that two of them
cannot be Prometheus rules here. They are named absences, not omissions, and
`scripts/render_alert_rules.py` fails if this list and the rules file disagree.

### A-3's client half — the count of `UncoveredDateError` refusals

**Measured, not assumed.** The M6 kickoff expected this to be the cheap alert to
fire ("a burst of past-horizon quotes… no outage at all"). It cannot be:

```
$ (Prometheus)  sum(rest_server_requests_total{path=~".*infer"})   ->  22
$ make quote QUOTE_ARGS="--at 2031-07-04T09:15:00 --pu 132 --do 48"
  [quote] REFUSED (422): … covers through 2030 …            exit 2
$ (Prometheus, after a scrape)                                     ->  22
```

The refusal is raised in the **client**, before a request is built — which is
F-019's decision working exactly as designed (refuse rather than degrade). The
consequence is that **the guard is invisible to the monitoring stack**: the
signal F-019 bought exists as an exit code, and nothing scrapes exit codes.

*Options, with honest costs.* (a) Instrument the client and push — needs a
pushgateway, which is M7's and is off by one values flag today. (b) A synthetic
prober CronJob asking for a date N days out and exporting the answer — a new
component and a new thing to maintain, to watch a CSV whose contents change once
a year. (c) Check the horizon where checks live: **`verify-m6` asserts the
table's coverage**, which catches the expiry *before* any rider meets it rather
than counting riders who already have.

**Taken: (c) now, (a) at M7** when the pushgateway exists for drift anyway. The
cost of (c), stated: it catches the *horizon*, not a *burst* — a client sending
in-horizon garbage at volume is caught by SLO-R1's server-side half, but a
client refusing locally in a loop is seen by nobody until someone runs the gate.

### A-4 — served version ≠ registry `@champion`

`version="None"` in every mlserver metric (F-034, measured at M6-S1), and MLflow
exports no Prometheus metrics at all. **The comparison has no two series to
make** — it is not a threshold problem, there is no data.

It is implemented instead as a **live check**, which is where it already was:
`verify-m5` §2 asks the endpoint for one prediction and requires its
`model_version` to equal what the alias resolves to, and `verify-m6` inherits
that. The honest cost: a check runs when someone runs it, so **a half-finished
rollback is caught at the next gate run and not at the next minute** — the
window F-032 describes stays open until then. Closing it properly needs an
exporter that reads MLflow, which is a new component; the recommendation is to
build it on M7's pushgateway rather than to add one now for a single gauge.

---

## 7. The CPU request, and why changing it is not expected to move p95

Recorded here because §3's capacity numbers are what argued it. See
`docs/monitoring_m6.md` §9 and the deployments ledger for the change itself.

The predictor requested **200m** and was measured using **1.31 cores** at the
SLO's stated shape — an under-reservation of ~6.5×. The request is what the
**scheduler** reserves and what sets the container's CPU **weight**; it is not a
cap. So the honest prediction, written before the change:

* **Throttling will not change.** Throttling is the *limit*'s doing (2 cores),
  and the limit is not moving.
* **p95 should not move materially** on a node with 20 allocatable cores and no
  contention. The request buys correct *scheduling arithmetic* — the node stops
  believing this pod needs a fifth of a core — and protection under future
  contention, not speed today.
* **If p95 does move materially, that is a finding, not a footnote.**

### 7.1 Measured, with the change as the only difference

Two `make load` runs of an identical shape either side of the change
(`automation/runs/m6-slo/load-{before,after}.json`, compared by
`scripts/cpu_request_resize_record.py` so the comparison is derived and not
typed):

| | p50 | p95 | p99 | max | ≥N of 240 over the 250 ms SLO target |
|---|---|---|---|---|---|
| **before** (`200m`) | 29.4 ms | 84.4 ms | 433.7 ms | 692.9 ms | 2 |
| **after** (`1500m`) | 29.5 ms | 112.7 ms | 118.9 ms | 142.9 ms | **0** |

**The prediction holds, and the honest reading is more careful than either
column.** The body did not move — p50 by 0.175 ms. p95 rose 28 ms, and that is
**inside the run-to-run spread of this identical shape**: M5-S4 measured 104.2 ms
on the same four requests per second, so the three measurements of one shape span
84–113 ms and the change sits inside them. It is not attributable.

**The extreme tail improved sharply and that is not claimed either.** p99 fell
73% and max fell 79% — but the before run's slow requests were in its **10th and
11th seconds**, mid-run rather than at start-up, which is the signature of host
contention on a laptop rather than of a scheduler's arithmetic. Claiming a
CPU-request change fixed a 700 ms stall would be the flattering reading, and
this program's rule is that the flattering floor is the one you name and refuse
(M2-S2).

**On the SLO's own instrument, which is the number that matters:** at most 2 of
240 requests beyond 250 ms before and 0 of 240 after, against a 5% budget. A-1
would not have fired in either run. The scheduler now sees the truth about this
pod, which was the entire point, and nothing a rider experiences moved.
