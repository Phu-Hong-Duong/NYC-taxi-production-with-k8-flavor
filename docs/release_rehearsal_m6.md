# The release rehearsal (M6-S4) — traffic that actually moved, and the rollback that finally ran

*Story: M6-S4 · role:SRE (A), MLOps (R) · 2026-08-19 · records:
`automation/runs/m6-canary/release_drill.json`,
`automation/runs/m6-rollback/alias_rollback.json`*

Three rehearsals in one story, in an order that ends where it started: shift
rider traffic to a second model server, take it back, and then do the harder
thing — move `@champion` itself, both ways, and measure what that costs.

Everything here mutates what is on the wire. Every mutation is in
`ledgers/deployments.md`, and the end state is the one M5 left behind:
`@champion` version **2**, `configs/train.yaml: features.version` **v2**, the
champion serving 100%, `make verify-m5` **GREEN**, `make parity` **0.000e+00**.

---

## 0. What the canary carried, and why it was not v1

M6-S3's DA memo returned **NO-GO for v1** (`docs/shadow_analysis_m6.md`): on
1,016 dual-sent rows the champion is closer on 54.4% and decisively better on
long trips, and the 5.9M-row holdout had already answered. Shifting rider
traffic to a model a memo has just refused would be a release nobody wants to
make.

So the canary is **the champion's own bytes under the challenger path** — a
second InferenceService resolved from the same `@champion` alias. Its
disagreement table is trivially 0.000 and the memo covers it. Everything the
*mechanism* can get wrong is exercised in full; the only thing held constant is
the thing the memo said no to.

That choice has a cost worth stating: because both backends serve version 2
under the same model name, **the client cannot tell them apart**, and every
response in this run carries `model_version: 2`. A constant version stamp here
is not evidence that no traffic moved. M6-S3 could attribute at the client only
because its canary was *broken* — the 404 rate was the split measurement — and
that is not a property to design for.

## 1. ADR-011's two conditions, and the third nobody predicted

ADR-011 left M6-S4 one explicitly **unproven** thing: `MLSERVER_MODEL_NAME` as
the remedy for condition 2 (the V2 model name is in the URL path, so canary
traffic aimed at `/v2/models/nyc-taxi-eta/infer` 404s on a pod that serves
`nyc-taxi-eta-canary`). It is now proved, **both ways** —

```
   MLSERVER_MODEL_NAME on the canary Deployment: 'nyc-taxi-eta'
[quote] served by nyc-taxi-eta version 2 via …/v2/models/nyc-taxi-eta/infer
        (Host: nyc-taxi-eta-canary-serving.local)
[quote] 2019-07-04T09:15:00  zone 132 -> 48, 1 passenger(s)  ->  39.0019 minutes
ok  /v2/models/nyc-taxi-eta-canary/ready -> 404 — the override is what answers, not a catch-all
```

The negative half matters: a runtime that answered to *both* names would pass a
positive-only check and tell us nothing about which name carried the request.
It is also worth recording that KServe injects `MLSERVER_MODEL_NAME` from the
InferenceService name and our value **wins the merge** — checked on the
Deployment object as well as on the wire, because "our env survived" and "the
model answers to that name" are different facts and either can hold while the
release mechanism is broken.

### F-039 — the third condition, found by going 0% for a new reason

The first release drill named its Ingress `nyc-taxi-eta-canary`. That is exactly
the name KServe RawDeployment generates for the InferenceService of that name.
`kubectl apply` succeeded, the canary annotations sat on the **controller-owned**
object, and KServe reconciled them away within seconds:

```
  baseline   ingress      0/211    = 0.0%   pods 220/0 = 0.0%
  canary_10  ingress      0/420    = 0.0%   pods 420/0 = 0.0%
  canary_100 ingress      0/300    = 0.0%   pods 300/3 = 0.99%
  reverted   ingress      0/300    = 0.0%   pods 300/0 = 0.0%
```

**Three requests of three hundred** — the window between the apply and the
reconcile — and no error in any log. The whole record is kept unedited at
`automation/runs/m6-canary/attempt1-ingress-name-collision/`.

What makes this worth a finding rather than a typo is that the symptom is
**byte-for-byte ADR-011 condition 1's** (gotcha #81, a canary pointed at a
Service some other Ingress claims). This program had just spent a story learning
condition 1, had written a manifest, a script and a drill against it — and the
obvious reading of 0% was the wrong one. The route is now
`nyc-taxi-eta-canary-route`, and the drill **refuses** to weight any Ingress
carrying `ownerReferences`, plus requires the controller to register the backend
with `noServer: true` and the applied weight before a window is measured. That
precondition costs one second where the symptom cost a six-minute load run.

**What caught it was measuring the split from counters rather than from the
annotation just applied.** That is the discipline condition 1 bought, paying for
itself against a different cause — gotcha **#85**.

## 2. The split, measured (`make canary`, PASS 11/11)

One continuous 6-minute open-loop load run at **4 req/s, concurrency 8, hazard
mix** — M5-S4's headline shape, unchanged on purpose because the SLO is written
against it — with the weight changed from inside the load client's own
per-second callback, so the split and the latencies share one clock.

| window | ingress `canary` counter | the two pods' own counters | failed |
|---|---|---|---|
| baseline (no canary Ingress) | 0 of 177 | 204 / 0 = 0.0% | 0 |
| `canary-weight: 10` | **41 of 420 = 9.76%** | 379 / 39 = **9.33%** | 0 |
| `canary-weight: 100` | **301 of 301 = 100%** | 0 / 240 = **100%** | 0 |
| reverted (Ingress deleted) | 0 of 300 | 300 / 0 = 0.0% | 0 |

**Two witnesses, from two different processes.** `nginx_ingress_controller_requests`
carries a `canary="serving-nyc-taxi-eta-canary-backend-80"` label on every
request the router diverted — that is the §9/M6 "per-backend counter" and it is
the claim. The predictors' own `rest_server_requests_total`, scraped per pod
because M6-S1 discovers predictors by label, is the corroboration: mlserver
counts what it was actually asked, which no ingress configuration can fake. A
record claiming 10% at the router and 0% at the pods would be a contradiction,
not a rounding difference.

The same fact as Prometheus renders it minute by minute
(`uv run python scripts/canary_split_paste.py`) — the green run is 15:24–15:29,
and 15:16–15:21 above it is F-039's failed attempt at full load with a canary
that moved nothing:

```
minute (UTC)            champion    canary  canary %
2026-08-19T15:16:36Z         240         0      0.0%      <- attempt 1, weight 10 applied
2026-08-19T15:18:36Z         240         0      0.0%      <- attempt 1, weight 100 applied
2026-08-19T15:21:36Z         240         0      0.0%
2026-08-19T15:24:36Z         179         0      0.0%      <- attempt 2 baseline
2026-08-19T15:25:36Z         213        13      5.9%      <- weight 10 applied mid-minute
2026-08-19T15:26:36Z         192        24     11.1%
2026-08-19T15:27:36Z           0       185    100.0%      <- weight 100
2026-08-19T15:28:36Z           0       224    100.0%
2026-08-19T15:29:36Z         240         0      0.0%      <- reverted
```

**Zero of 1,440 requests failed**, across two weight changes and a revert. An
Ingress edit reloads nginx and touches no pod: the champion's predictor kept the
same UID throughout, and the drill asserts that rather than assuming it. This is
also why the weight lives on an *Ingress* annotation and never on the
InferenceService — F-038 measured `kubectl annotate isvc` rolling the champion's
only predictor twice for 174 of 200 requests returning 502.

### The revert: 0.37 s against a 120-second budget

`kubectl delete ingress nyc-taxi-eta-canary-route`, and the controller had
dropped the backend **0.37 s** later — timed against the controller's OWN
`/configuration/backends`, polled every 0.25 s from the moment the delete was
issued, because that is the router's runtime state rather than the object (which
disappears the instant the API server accepts the delete). §9/M6 asks for under
two minutes under load. **No requests were lost.**

The operational consequence is in the runbook: **prefer the traffic revert.**
It is one deletion, it costs nothing, and it does not touch the champion at all.

## 3. The alias rollback, run for real (`make rollback`, PASS 10/10)

`docs/runbooks/serving.md` §4 said **TYPED, NOT REHEARSED** from M5-S5 until
this story, for a reason that was correct then: M5 was legislated alias-neutral.
The M5 PRR routed the rehearsal here; M6's kickoff sanctions exactly two alias
moves, and these are they.

The script runs the runbook's **own** three moves — a raw
`set_registered_model_alias` (never `registry.promote`, which refuses an alias
move with no gate Decision — F-011), then `configs/train.yaml:
features.version`, then `make serve` — with the route probed twice a second
throughout, sending the matrix a real client would be building at that instant.

| | alias | config line | `make serve` | **total** | **outage** | probes failed |
|---|---|---|---|---|---|---|
| v2 → v1 | 0.050 s | <0.001 s | 35.30 s | **35.35 s** | **27.93 s** | 55 of 85 |
| v1 → v2 | 0.034 s | <0.001 s | 34.34 s | **34.38 s** | **0.50 s** | 1 of 81 |

### F-040 — a rollback is not a 0.5 s re-deploy, and it is not symmetric

Gotcha #80 established that a model re-deploy costs **0.5 s**: at one replica
`maxUnavailable` floors to zero, so a surge pod must be ready before the old one
goes. §4.4 then guessed a rollback would "expect longer than 18.24 s". Both were
reasoning about the *pod*. The cost is in the **second move**.

The moment `features.version` becomes `v1`, every client on the wire sends a
**5-column** matrix while the pod still holds the **24-column** model, and
MLflow's logged signature refuses it — `HTTP 500` until the replacement answers,
then a single `HTTP 502` for the swap. The error classes say it precisely: leg 1
recorded `['HTTP 500', 'HTTP 502']`, leg 2 recorded `['HTTP 502']` alone.

**Rolling forward is nearly free because a 24-column request sent to a
5-column model is *tolerated*** — MLflow takes the columns its signature names
and ignores the rest. Removing features breaks requests in flight; adding
features does not.

The remedy that follows — reorder to alias → `make serve` → config line, so
clients keep sending 24 columns until the new pod is up — **has not been run**.
It would cost two more alias moves and M6 sanctions two. It is written into §4
as *not rehearsed, do not silently substitute during an incident*, and routed to
M6-S5. The same discipline ADR-011 used for `MLSERVER_MODEL_NAME`: a named
remedy is not a proved one.

### The half-way state is where the coherence check earns its name

`make verify-m5` was run at `@champion` = version 1 — a state it was never
written to run in. It went **RED with 3 FAILs**, and §2's coherence check stayed
**GREEN**:

```
ok   the served version's feature_set tag ('v1') equals configs/train.yaml's
     features.version — the client builds the matrix this model eats

FAIL the live answer 10.291528327 differs from the recorded 10.665224429 by more
     than the recorded tolerance
FAIL the configured feature set is 5 features wide, the parity record was measured at 24
FAIL @champion -> version 1 (run 3adee05a…) is not the bake-off's recorded winner (92b73bd4…)
```

Green at v2 alone is satisfiable by a literal; green at **v1 as well** is what
makes it a coherence check (F-017, gotchas #49/#50). And the red is the gate
doing its job — a gate that stayed green while the alias pointed somewhere else
would not be watching the pointer at all. At the end state it is **GREEN**
again, `configs/train.yaml` is byte-identical by `git hash-object`, and the
champion's answer for the parity row reproduces **39.001937** exactly.

**What this story predicted wrong, kept:** the prediction said those failures
would be *only* about the bake-off winner. Two of the three are the M5 gate
asking the endpoint for a real prediction and noticing a different model is
serving — the same fact through a different instrument. The check was replaced
by a property that survives both states rather than by a wider keyword list
(gotcha #50), and the verdict re-judged from the recorded evidence rather than
by spending two more alias moves — the `verify-m3` replay idiom.

## 4. What is on the wire at the end

```
inferenceservice/nyc-taxi-eta          Ready True   12h
inferenceservice/nyc-taxi-eta-shadow   Ready True   73m     <- M6-S3's, left for S5
```

The canary InferenceService, its dedicated backend Service and its route are
gone (`make canary-deploy TEARDOWN=1`); deleting the InferenceService takes its
Deployment, Service and generated Ingress with it, which is why a second isvc
was preferred to editing the champion's spec in the first place.
`make verify-m5` **GREEN**, `make parity` **0.000e+00 over 16 hazard rows**,
`@champion` version **2**.

## 5. What M6-S5 inherits

- **The reordered rollback (F-040's remedy) is a named gameday candidate** and
  the only way to close the 27.93 s window. It needs two alias moves; S5's
  gameday is the sanctioned place to spend them.
- **A canary carrying a genuinely different model is still unrehearsed.** The
  *name* problem is solved (`MLSERVER_MODEL_NAME`); a differing *signature*
  behind the same name is the second wall, and nothing has met it.
- **The admission webhook is still off**, and this story hand-authored Ingresses
  again. ADR-011 argued the ~15 s outage was better spent once, here — it was
  not spent, because the canary route turned out to need no webhook to be
  validated and the drill's own precondition catches what a webhook would.
  Re-routed to S5 with that noted, not silently dropped.
- **The `nyc-taxi-eta-shadow` InferenceService is still running**, as M6-S3
  left it. `make shadow TEARDOWN=1` removes it cleanly.
