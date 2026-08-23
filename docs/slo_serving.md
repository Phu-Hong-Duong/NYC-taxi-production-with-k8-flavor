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

### 2.2 Above ~90% CPU, no IN-POD instrument may be trusted — including I-2 (F-043)

**A component under stress is an unreliable reporter of its own stress.** This is
not a caution, it is a measurement. During M6-S5's saturation gameday
(`automation/runs/m6-gameday/saturation.json`, `docs/gameday_m6.md` §4.2), with
the predictor pinned at a CFS-throttled fraction of **0.9996**:

```
the LOADED predictor's /metrics :   scrape_duration 4.613 s, and one scrape had up == 0
the IDLE v1 shadow's /metrics   :   scrape_duration 0.004 s, up == 1   (same job, every 15 s)
```

Two instances of the same exporter, scraped by the same Prometheus job, 1,150×
apart. A failed scrape makes the series **stale**, and a stale series makes an
expression evaluate over nothing — which is why **A-1 fired at T+349.3 s and then
cleared itself at T+514.3 s while the load was still running.** The alert did not
decide the latency was fine; it lost the ability to see.

The idle shadow was an accident — an M6-S3 leftover — and it is the only reason
this is a measurement rather than a theory. It is worth saying plainly: **the
cheapest possible control for "is this exporter lying?" is a second, idle
instance of it scraped by the same job.**

**What holds under saturation, and what the on-call should read instead:**

| Instrument | Where the process runs | Survives predictor saturation? |
|---|---|---|
| I-2 mlserver histogram/counters | **inside the predictor** | **No** — this section |
| I-5 cAdvisor (A-6, throttling) | the kubelet, on the node | **Yes** — it is what reported the 0.9996 |
| I-3 ingress-nginx (A-2, edge 5xx) | a different pod, a different node | **Yes** |
| I-4 kube-state-metrics (A-5, A-7) | the API server's view | **Yes** |

So **A-6 is the alert a saturated service produces**, A-2 and A-5 are the
availability witnesses, and A-1's silence during a saturation event carries no
information. A-1's `why` annotation says so at the rule.

*Disposition (ARCH, M6→M7 boundary, option (c)): accept and document.* No target
loosens and no threshold moves — an instrument limitation is documented, not a
bar changed. Raising the CPU limit (option (a)) stays available at a future
capacity conversation argued from real traffic. **Drift metrics are structurally
outside this failure mode**: they are pushed by a batch job to a gateway on
another node, so the producer and the scrape are decoupled by design.

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

> **CORRECTION, 2026-08-19 (M6-S5, F-041) — the paragraph above is kept
> UNEDITED because decisions were made from it, and it is wrong about which
> mechanism protects us.** Gameday 1 killed the predictor under exactly the load
> shape that arithmetic assumes, and the edge 5xx share **peaked at 0.5000**:
> `ServingEdge5xxRateHigh` went `pending` at T+89.2 s and back to `inactive` at
> T+103.2 s, and `PredictorNoAvailableReplica` did the same at T+59.1 s →
> T+74.1 s. The error is dividing an outage's failures by a FULL window's
> traffic. `rate(...[5m])` extrapolates from the samples actually inside the
> window; thirty seconds into a load run that window holds thirty seconds of
> requests, so immediately after a kill the denominator is small and nearly all
> of it is the outage. 6.1% is what the ratio decays TO, not what it reaches.
> **What stops a self-heal from paging is the `for: 5m` sustain, not the 10%
> threshold** — and the same holds for A-5, whose 2-minute sustain absorbed a
> 15-second dip. Both thresholds stand: they are not loosened, and no number in
> this document changes. What changes is the argument, and one operational fact
> nobody had written down: **during any ordinary self-heal an on-call will see
> A-2 and A-5 sitting `pending`, in red, and neither will ever fire.** Evidence:
> `automation/runs/m6-gameday/kill.json`, `docs/gameday_m6.md` §2.1.

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

## 6. The two signals that had no metric source — CLOSED at M7-S3 (F-035)

> **DATED UPDATE, 2026-08-20 (M7-S3). Both absences are now sources, and the
> sections below are kept unedited as the record of why they were absences.**
> The reason both were impossible was the same one, stated at M6-S2: *the fact
> lives in a CLIENT, and no client here is scraped.* M7-S3 installs the
> pushgateway for drift, which makes a client able to speak. So:
>
> * **A-3's client half** — `taxi_quote_refusals_total`, pushed by the quote
>   client itself when `UncoveredDateError` refuses a request. Its rule is
>   `increase(...[1h]) > 0` and that shape is deliberate: this is **not** a rate
>   problem needing a fleet. One refusal means the holiday table's horizon has
>   expired, which is a fact about the repository, not about traffic volume — so
>   a single event is the event. Option (a) of the three costed below, landed at
>   the milestone it was costed for. Option (c) (`verify-m6`'s coverage check)
>   stays in place: it catches the expiry *before* a rider meets it, and this
>   catches the rider who already did.
> * **A-4** — `taxi_serving_model_version` and `taxi_registry_champion_version`,
>   pushed by `scripts/push_serving_version.py`, which asks the live endpoint for
>   one prediction and the registry for the alias and pushes both. There are two
>   series now, so the comparison exists. **Its rule requires freshness as well
>   as agreement** (§8.5's argument applied a second time): a stale pushed pair
>   agrees with itself forever.
>   **Honest cut, stated because it is real:** the *cadence* is not installed
>   here. The pusher is a script proven to push, and what runs it on a schedule
>   lands with M7-S4's scheduler — the story that installs one. Until then A-4's
>   freshness half is what stops the version half from lying, and `verify-m5` §2
>   remains the check that actually runs at every gate.
>
> `scripts/render_alert_rules.py`'s absence-agreement check moved with them:
> `IMPLEMENTED_SIGNALS` now holds all ten ids and the documented-absence set is
> empty, so this closure could not have been claimed without the rules existing.

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

---

## 8. The drift targets (M7-S3) — argued before the drift job saw a 2020 month

**Read §0 first: the rule that no bar is set equal to a number just measured
applies here with a sharper edge than anywhere else in this document.** Every
other threshold here was argued against a service whose behaviour nobody was
trying to prove. A drift bar is argued against a month — March 2020 — that this
program went and fetched *because* it expects it to be extreme. So the order of
work is recorded, and it is checkable from the records' own timestamps:

1. the **headroom leg ran first** and read only 2019 data
   (`automation/runs/m7-drift/headroom.json`);
2. the bars below were written from it;
3. the **prediction** was written to
   `automation/runs/m7-drift/prediction.json`;
4. *then* 2020-01..03 were compared.

A bar chosen after step 4 would be a bar chosen to make an alert agree, which is
the thing M7 law 4 exists to forbid.

### 8.1 The instrument, and what it deliberately cannot see

`taxi_mlops.monitoring.drift` compares one month's **input distribution** with
the champion's **training distribution** (`trips_train`, 2019-01..06, 43,987,422
rows — the rows the champion was actually fitted on, not a rolling window; the
module's docstring argues why a moving reference cannot see a slow move). Six
columns are monitored: five inputs and, separately, the target.

The statistic is **PSI over bin shares**, computed exactly from DuckDB value
counts — no sampling, so the number does not move when nothing moved. Evidently
0.7.21 runs beside it on a seeded sample as a second witness and is *not* the
alerting instrument (`drift_evidently.py` says why).

**What PSI structurally cannot see: volume.** PSI is a distance between *shares*.
Halve every count and PSI is exactly zero. A city that stops moving but keeps the
same mix of trips is invisible to it — which is precisely the F-045 shape M7-S1
measured from the other side. That is why SLO-D2 exists and is not a refinement
of SLO-D1: it is the marginal the first instrument is blind to.

**What the WINDOW cannot see, stated because it was measured and not fixed
(F-046, decided at the M7→M8 boundary).** The paragraph above is about columns;
this one is about the month. *A regime change confined to part of a month is
invisible to SLO-D1 at monthly grain regardless of which columns are watched:
2020-03 measured a largest input PSI of 0.0217 — below an accepted July 2019's
0.0323 — while its last ten days ran a different city.* The mechanism is the one
the drift memo states in the form that generalises: a row-weighted average of a
collapse is weighted by exactly the rows that disappeared (68.231% of March's
rows fall before the 11th; 3.321% after the 21st). **The signal was never absent
— it was averaged.**

The boundary accepted the monthly window rather than adding a daily drift job,
and the reliance that makes that honest is SLO-D2: **A-9 needs no column to move
at all, and since M8-S1 its ratio is monotonic in the depth of the collapse**
(F-051 — the denominator is the calendar days the window covers, so a day with
no trips can no longer leave the numerator and the denominator together). The
residual cost is recorded rather than netted out: **a shape change with no
volume change — a vendor re-routing, a fare-rule change, a new pickup pattern at
constant demand — confined to part of a month would be missed entirely by both
rules.** A daily or rolling window is the upgrade that buys it, and it is
deliberately *not* scheduled here: it needs its own 2019 daily headroom leg
before any bar can be argued (law 4's family — choosing a window after seeing
which window would have fired is the same move as walking a threshold), a push
cadence, and a staleness story per window. The daily series already exists on
the OUTPUT side (`marts.scoring_daily`, and the M7-S5 board renders it), so the
gap is specifically the INPUT side.

### 8.2 The headroom, measured on months whose verdict already exists

The two held-out 2019 months are the only data in this repository that is
*known* not to have warranted action: the champion was measured on them and
**PROMOTED**. Whatever distance they sit at from the reference is, by
construction, a distance the program has already decided to live with.

| Column | PSI, val 2019-07 | PSI, test 2019-08 |
|---|---|---|
| `hour` | 0.0006 | 0.0009 |
| `dayofweek` | **0.0323** | 0.0077 |
| `PULocationID` | 0.0091 | 0.0137 |
| `DOLocationID` | 0.0085 | 0.0126 |
| `passenger_count` | 0.0010 | 0.0013 |
| `trip_duration_minutes` *(target)* | 0.0011 | 0.0008 |
| **trips/day vs reference** | **0.8216** | **0.7899** |

The largest of them, 0.0323, is `dayofweek` in July — and reading *what* it is
matters as much as its size: July 2019 held five Mondays against the reference
months' average, so it is **calendar arithmetic**, the least model-meaningful
move a month can make. The largest genuinely-behavioural number is
`PULocationID` at **0.0137**.

### 8.2a The rules these targets are implemented by

| Signal | Alert | Target | `for:` |
|---|---|---|---|
| **A-8** | `ModelInputDrift` | SLO-D1 | 5m |
| **A-9** | `ScoringVolumeCollapse` | SLO-D2 | 5m |
| **A-10** | `DriftMetricsStale` | SLO-D3 | — |
| **A-11** | `DriftMetricsAbsent` | SLO-D4 | 10m |

and the two F-035 landings that ride the same gateway (§6's dated update):
**A-3**'s client half as `QuoteHorizonRefusals`, and **A-4** as
`ServedVersionNotChampion`.

### 8.3 SLO-D1 · input drift — *fewer than two of the five monitored input columns at PSI ≥ 0.10*

**The per-column bar is 0.10.** Two independent arguments have to agree before a
number goes in this document, and here they do:

* **Headroom.** 0.10 is **3.1× the highest distance a PROMOTED month sits at**,
  and **7.3× the largest behavioural one**. Ordinary seasonality — a different
  count of Mondays, a summer zone mix — does not get near it. There is real
  daylight between the bar and everything this program has observed and accepted.
* **It is not a number we invented.** PSI's 0.10 / 0.25 "investigate /
  significant" convention is decades old and published everywhere. That matters
  for exactly one reason: an on-call who did not write this document has a prior
  for what 0.10 means, and a house-special bar of 0.037 would be a number only
  its author could interpret at 3am.

**The alert requires TWO columns, and the cost of that is stated rather than
hidden.** A single column crossing 0.10 is more consistent with a data-side
artefact than with a moved world — `passenger_count` is in the monitored set for
exactly that purpose — and the champion's inputs are strongly correlated
(hour↔dayofweek, PU↔DO), so a real world event moves several at once. Requiring
two makes the page mean *the world moved*.

*The blind spot this buys, named:* **one column going catastrophically wrong does
not page.** A vendor that starts sending `passenger_count = 0` for every trip
moves one column to a huge PSI and A-8 stays silent. That is a deliberate trade —
it is visible on the board and in the monthly memo, and the complement is SLO-D2,
which needs no column to move at all. If a single-column catastrophe ever
happens here, this is the paragraph that was wrong and the split should be
re-argued, not the bar walked.

**Sustain: `for: 5m`.** F-041's mechanism — a `rate()` window that is empty when
an event starts — **does not apply to these rules**, because they read last-value
gauges from a bulletin board rather than a window of samples. The sustain's only
job here is to outlive a failed scrape of the gateway or a half-written push, and
5 minutes is 20 evaluations at the 15 s interval.

### 8.4 SLO-D2 · volume — *the scoring month holds at least half the reference's trips per day*

**The bar is 0.50.** The lowest ordinary observation in this repository is
**0.7899** (August 2019 against the reference), so 0.50 sits **29 percentage
points below the quietest month a promoted champion was judged on**. A summer dip
is ~20%; halving is not a dip. The harm side is what makes it worth a page rather
than a chart: a model quoting confidently into a market that has lost half its
trips is quoting into a *different* market, and volume is the marginal SLO-D1 is
structurally blind to (§8.1).

**"Trips per day" means per CALENDAR day, and that sentence became true on
2026-08-21 (F-051).** It is what this section and A-9's annotation always said;
it is not what the job computed. Until M8-S1 the denominator was
`COUNT(DISTINCT observed date)` — the days that held a trip — so a day on which
the city took *no* trips left the numerator **and the denominator together**, and
the ratio measured *how busy were the days that happened*. That quantity **rises
as a shutdown deepens**: REV measured it at the M7 review by deleting 2020-03's
quietest days outright — a strictly worse month — and watched the ratio walk from
0.3913 through 0.4768 to **0.5143, back across this bar and silent**. The same
arithmetic read a truncated 20-of-31-day extract as healthy.

The bar did not move; the denominator did. What the change buys is a **property**,
now asserted by tests and re-measured by `make drift-monotonicity`: *a strictly
worse collapse produces a strictly lower ratio, and a month that has crossed 0.50
cannot walk back across it.* An alert whose whole claim is that it sees the
marginal PSI cannot see has to be monotonic in that marginal, and §8.1's
acceptance of the monthly window (F-046) rests on this rule specifically.

### 8.5 SLO-D3 · freshness — *a drift number older than 40 days is not a drift number*

The gateway is a **bulletin board, not a store of events**: a pushed metric
persists until it is overwritten or deleted. So "the drift metric is present and
below the bar" is equally consistent with *the drift job died in March and
January's reassuring number is still pinned to the wall*. This is gotcha #78's
empty-panel disease inverted — not a blank rectangle that looks like calm, but a
stale number that looks like health.

**40 days — `3456000` seconds, which is the literal the rule contains** — because
the cadence is monthly: a month plus a week plus a weekend. One late run does not
page; a stopped job does. Every push carries
`taxi_drift_last_run_timestamp_seconds` and
`taxi_mlops.monitoring.pushgateway.push_metrics` **refuses a payload without a
metric named `*_last_run_timestamp_seconds`** — a guard in a type rather than in
a habit.

The seconds are written here, and not just "40 days", on purpose: a check that
compares a rule against the document arguing it has to compare the number the
rule actually holds. Rendering `3456000` as "40 days" in the doc and leaving the
check to do the arithmetic is how a threshold ends up argued nowhere (the first
run of `test_every_rule_threshold_appears_in_the_document_that_argues_it` failed
on exactly this, and passed A-4's `1800` **by accident** — `"1800".rstrip("0")`
is `"18"`, which matches `18.24 s` in §7.1. Gotcha #76, found by the test on
itself.)

### 8.5a SLO-D4 · existence — *the drift surface is there at all* (added 2026-08-21, F-050)

**A-10 cannot fire on an absent series, and that is arithmetic, not an
oversight.** `time() - max by (month) (taxi_drift_last_run_timestamp_seconds)`
evaluated over zero series is *zero series* — not a large number. So the state
this section spent a paragraph warning about, "the drift job died and its
reassuring number is still pinned to the wall", has a worse sibling that D-3 is
structurally blind to: **the wall is gone.** Every panel renders empty, every
rule sits `inactive`, and nothing anywhere says so.

It was not hypothetical. The pushgateway ran on an `emptyDir`, so it lost its
entire store on every pod restart, and this cluster is a laptop: **measured three
times inside 24 hours** of the finding being raised (F-050), twice within
fourteen. Each time, `verify-m7` §5 was the only thing that noticed, and only
because it had been written to ask the paired question — *are the series there,
or is there an accounted-for reason they are not?*

The fix is a pair, and neither half is honest alone:

* **The store survives an ordinary restart.** The gateway now writes to a
  PersistentVolume (`--persistence.file`, checkpointed every 10s). This removes
  the event that actually recurs here.
* **A-11 pages when the series are absent for 10 minutes.** With the volume in
  place an absence means somebody *deleted* something — a cluster rebuild, a
  wiped PVC, a namespace removed — which is exactly what should page. Landing
  A-11 alone, on an `emptyDir`, would have fired on every reboot and trained its
  reader to ignore it; that is why the boundary decided the two together.

**The 10 minutes is argued from the benign cause.** The only thing that
legitimately produces an absence here is the gateway pod being replaced, and a
replaced pod re-serves the same series the moment it is Ready — measured at
~30 s in this repo's own drill. Ten minutes is an order of magnitude of headroom
over that. An hour would be defensible too, by A-10's monthly-cadence logic; the
shorter window is preferred because a wiped board costs nothing to notice and a
great deal to leave, and because a drill has to be able to watch it fire.

**What A-11 still cannot see**, stated rather than netted out: a gateway holding
*some* series and not others. `absent()` is a statement about the whole selector,
so a partial loss — one month's group deleted while two remain — leaves it
inactive. A-10 covers the months that remain, and nothing covers the month that
does not. The cost is bounded by the cadence: a monthly job re-pushes every
month it is asked for, and the drift memo cites months by name.

**A-4's freshness window is 30 minutes — `1800` seconds** (§6's dated update).

### 8.6 What these targets deliberately do not cover

* **Performance decay.** M7-S2's KPI-14/15/16 are the champion's error series on
  the scoring months, and they are *not* what A-8 fires on. An ETA's labels
  arrive when the trip ends and in a real deployment far later; an alert that can
  only fire once the labels have landed reports history. Drift is the signal that
  works on the day of. The error series is the memo's (M7-S5) and the gate's.
* **What to do about it.** A drift alert is a request for a decision — retrain,
  re-scope, or accept — not a fault report. Nothing here auto-retrains, and M7
  law 3 means nothing here can move `@champion`.
* **A moving reference.** Stated as a cost in the module: the reference does not
  follow the world, so a legitimately-changed world keeps alerting until someone
  retrains and re-declares it. That is intended. An alert that silences itself by
  redefining normal is the drift-monitoring failure mode.

## 9. The online-store targets (M9-S2) — argued from the store's own sources, before the drill

M8-S4's three legs each ended with the same residual sentence, and none of them
closed it: **there is no alert on an empty or stale online store.** This section
is the argument; `infra/monitoring/alerting_rules.yml` is where it becomes true.

The order is M8 law 4, ninth inheritance and checkable from git rather than
asserted here: `automation/runs/m9-store-watch/headroom.json` was measured
first, this section was written from it, both were committed, and only then did
the drill run that first crosses a bar.

### 9.1 What makes this store different from every other thing this stack watches

The Feast online store is the only dependency on the quote path whose failure is
**silent by construction**. An all-null store yields an all-NaN geometry table,
and **NaN is the correct answer for TLC zones 264/265** — they have no centroid
by design (DR-04 condition 1), they are ~1% of every split, and `264 -> 264` is
the largest single OD "route" in the data. So no client can refuse a null on
sight: the same value that means *this zone is not a place* also means *the store
is empty*. That is gotcha #78's disease with the panel removed entirely, and it
is why the signal has to be a watchdog and not a guard in the request path.

Two facts bound how bad that can get, and both are measured:

* the store's **only rider-facing reader** is the transformer (M8-S4 leg 3), and
  it reads **two** of the four views — `zone_static` and `calendar_day_flags`
  (F-059 keeps the borough dictionary and the airport constant on the committed
  side of the wall);
* the champion's own wire never touches the store at all. A store failure cannot
  reach the rider path of record.

### 9.2 The headroom, measured before any bar was written

`automation/runs/m9-store-watch/headroom.json`, 2026-08-23. Feast writes one
Redis key per distinct entity key per view, so the store's size has a source of
truth that is not itself:

| view | distinct entity keys | share | read by the transformer |
|---|---:|---:|---|
| `zone_static` | 263 | 0.46% | **yes** |
| `calendar_day_flags` | 4,383 | 7.60% | **yes** |
| `od_window_stats` | 46,938 | 81.37% | no |
| `pu_hour_window_stats` | 6,104 | 10.58% | no |
| **total (derived from `data/feast/*.parquet`)** | **57,688** | | |

**Three witnesses agree at 57,688**: the count derived from the published
sources, the count `automation/runs/m8-online/materialize.json` recorded on
2026-08-21, and the live `DBSIZE` read off the running server. The derivation is
`count(distinct <entity keys>)` per view — no number in this table is typed.

Two consequences decide the whole design.

**(a) The key count cannot see the loss that would actually hurt a rider.** The
transformer's entire dependency is **4,646 keys, 8.054% of the store**. A store
that lost `zone_static` and `calendar_day_flags` completely still reads 53,042
keys — 92% of normal — and every quote it backs is refused or wrong. Worse: zone
132's centroid is **one key of 57,688**, so losing exactly the key that breaks
every JFK quote moves the count by 0.0017%. Any bar on the count is therefore a
*coarse* signal by construction, and something else has to be the load-bearing
one.

**(b) There is no partial-loss mechanism.** `maxmemory-policy` is `noeviction`
(ADR-012 — a correctness setting, not tuning), the store uses 14.32 MiB of a
512 MB cap, and `feast materialize` either completes or fails. So the realistic
population is bimodal — full, or gone — and a bar placed anywhere strictly inside
the gap catches the same events. That is an argument for **not choosing a number
at all**.

### 9.3 "Stale" does not mean what it means everywhere else in this document

SLO-D3 asks whether the drift *job* has run recently, and 40 days is argued from
a monthly cadence. Applied here that question has no answer, because **the data
in this store is settled**: the materialized windows are 2019-01..2019-07, the
zone centroids are TLC's 2019 shapefile, and the holiday table runs to 2030. A
store filled in August 2026 is exactly as correct in 2027. A clock-age bar on its
*contents* would be a number chosen to avoid paging rather than to catch anything.

So this section defines stale differently, and the definition is the useful part:

> **A store is stale when it disagrees with the sources it was filled from.**

That is a comparison between two quantities the watchdog can both measure — the
live `DBSIZE` and the count derived from `data/feast/*.parquet` — and it needs
**no threshold whatsoever**. It self-updates: a legitimate `make feast-sources`
that grows or shrinks the sources moves both sides together as soon as
`make feast-materialize` runs, and the window in between — sources changed, store
not refilled — is *exactly* the stale state this rule exists to catch.

### SLO-S1 · integrity — *the online store answers what its sources say it holds*

**Two rules, one signal (A-12)**, the A-5 precedent (a signal whose failure has
two shapes that need two expressions). Neither carries a bar on a measured
quantity.

**A-12a `OnlineStoreCanaryFailing` — the load-bearing half.** Four claims about
what the store answers, checked on every run of the reader and pushed as
`taxi_online_store_canary{check=...}`:

| check | claim | why this one |
|---|---|---|
| `store_reachable` | `DBSIZE` was readable at all | see below — this is the one that is reported rather than withheld |
| `zone_answers` | zone **132** returns a non-null centroid | a *place* must have a location. This is the JFK zone the whole program's records quote — `39.0019` minutes is measured on a trip out of it |
| `nonplace_declines` | zone **264** returns **null**, and not an error | the negative half. A store that answered for a non-place would be inventing a location, and a check that only asserted presence would pass against a server answering every question with the same row |
| `calendar_answers` | **2019-07-04** returns its holiday flags | the half that actually refuses the rider: `calendar_from_store` RAISES on an unanswered date (F-019 carried onto the store's wire), so this is the claim whose failure the transformer converts into a 422 |

The expression is `== 0` — a property, not a threshold. `$labels.check` names
which claim failed, which is why the four are four series and not one boolean.

**Why `store_reachable` is a reported 0 and not a refusal to push.**
`scripts/push_serving_version.py` refuses to push when either side is unreadable,
and it is right to: an unknown served version is not a mismatch, so a placeholder
would page an on-call for an unreadable endpoint. **The rule inverts here.** If
the Redis pod is gone, *"I could not read `DBSIZE`"* is not a gap in the
measurement — it **is** the measurement. A reader that withheld it would leave
the last healthy reading on the board to go quietly stale, which is precisely the
failure this signal exists to prevent. The honest cost, named rather than netted
out: a broken `kubectl` on the operator's own laptop reads the same as a broken
store. That is acceptable because the reader is operator-invoked (below) — a
laptop that cannot reach the cluster is not silently running this in a loop.

**A-12b `OnlineStoreIncomplete` — the coarse half, and the one that closes
"stale".** `taxi_online_store_keys < taxi_online_store_keys_expected`: the store
holds fewer keys than its own sources define. Both sides are measured by the same
reader on the same run; the right-hand side is derived from the committed parquet
by `count(distinct <entity keys>)`. **There is no number on either side of that
comparison**, which is the strongest form §9.2(b) permits.

**Both rules sustain `for: 2m`, and both carry a freshness clause of `1800`
seconds** (A-4's window, §8.5). The sustain is not the usual "don't page for a
transient" — this condition has no transient form in the sense A-4 means, but it
has exactly one: `feast materialize` writes into an empty store over ~7 seconds
(recorded), and a reader that ran mid-write would see a partial count. 2m is an
order of magnitude over the only benign cause, which is the same argument A-11's
10m makes about a pod replacement.

**The freshness clause, and the honest cost it buys.** Neither rule may fire on a
reading older than 30 minutes. That is A-4's landed shape and it is here for
A-4's reason: **this reader has no scheduler.** M9 legislates no new Flyte
trigger (F-058), the store watchdog adds no image and no CronJob, so the reader
runs when `make store-watch` is run — by the drill, by `make verify-m9`, and by
an operator. A pushed reading therefore goes stale, and the clause makes a stale
reading **inactive** rather than falsely green.

That is a real gap and it is named rather than netted out: *while nobody runs the
reader, A-12 cannot fire.* Three things bound it, and none of them is a promise
that the gap is small:

1. **A-13 (below) still fires** — the surface disappearing is caught whether or
   not anybody is pushing;
2. **`make verify-m9` asks the store the same question live at every crossing**,
   which is the check that actually runs (the same complement `verify-m6` is to
   A-3's client half);
3. **the failure is not fast-moving.** A store that lost its keys stays lost —
   `noeviction` and a settled source mean nothing refills it by accident — so a
   reading taken hours late still reports the same fault.

**Deliberately NOT shipped: a staleness rule on the store's reading.** A
staleness bar can only be argued from a cadence. This reader has none by design,
so any number would be chosen to avoid paging rather than to catch anything — and
shipping one would put a page on the calendar for the design instead of for a
fault. The absence is recorded here rather than left to be inferred.

### SLO-S2 · existence — *the watchdog's surface is there at all* (A-13)

`absent(taxi_online_store_last_run_timestamp_seconds{job="taxi-store-watch"})`,
**`for: 10m`**, and it exists for the reason F-050 measured on this machine three
times in twenty-four hours: **A-12's freshness clause is structurally unable to
see its own series disappear.** `time() - stamp < 1800` over zero series is zero
series, not a stale reading — so a gateway that lost its store makes A-12 go
quiet and the panel go blank, which is what a healthy store looks like. A-10 and
A-11 are the same pair one board along, and the argument transfers whole.

**The sustain, 10m, is A-11's number and it is inherited with its precondition
re-checked, not assumed.** The headroom leg reads the live pushgateway back:
`--persistence.file` is present in its args and its PVC is `Bound`. On an
emptyDir this rule would fire on every ordinary host reboot and teach its reader
to ignore it; on the volume it fires when somebody *deleted* something.

### 9.4 What these targets deliberately do not cover

* **A wrong store rather than an empty one.** A store materialized from the wrong
  sources has the right key count and answers every canary correctly while every
  *value* is wrong. Nothing here catches that, and nothing cheap can:
  `make feast-online-parity` (100 declared pairs, bar EXACT) is the instrument
  that would, and it is a gate-time check, not a watchdog.
* **The champion's wire.** It reads committed tables and cannot be affected by
  any of this. Said out loud because an on-call reading A-12 at 3am needs to know
  the rider path of record is not down.
* **Redis itself.** No native `/metrics` exporter was added (the costed option
  (i) in the M9 kickoff). The reader asks the questions an exporter cannot —
  `DBSIZE` is one of them, but *does zone 132 still have a location* is not a
  quantity Redis exports about itself.
