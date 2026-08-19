# ADR-011 — How this program does canary and shadow

- **Status:** ACCEPTED (2026-08-19, M6-S3)
- **Supersedes:** nothing. **Discharges:** ADR-004's deferred spike.
- **Decided by:** EXECUTOR/Opus in role block SRE (Accountable), inside ADR-004's
  pre-approved budget of ONE serving re-deploy. Not a PO fork — the kickoff's
  ARCH self-check records it as "an executor decision inside ADR-004's
  pre-approved budget".
- **Evidence:** `automation/runs/m6-spike/canary_spike.json` (PASS 7/7, tracked),
  the superseded first run kept unedited at
  `automation/runs/m6-spike/attempt1-no-dedicated-service/`, and
  `make canary-spike`, which re-runs the whole thing in about four minutes.

## Context

ADR-004 chose KServe **Standard (RawDeployment)** mode and recorded the cost in
its own text: `canaryTrafficPercent` requires the **Serverless** profile, so the
prior art's canary story does not apply to us. It deferred one question to a
timeboxed spike: *what mechanism gives this program traffic-split canary and
shadow on a stateful kind cluster?*

The M6 kickoff named three candidates and pre-refused one:

- **(i) Knative/Serverless** — KServe's native `canaryTrafficPercent`, at the cost
  of a whole second serving stack on a cluster that must not be rebuilt, and a
  contradiction with every M5 artifact (the runbook, `verify-m5` §1's
  RawDeployment read-back). Pre-refused unless (ii) fails at its wall: ADR-004's
  budget is one re-deploy, and a Knative install is not a re-deploy.
- **(ii) Two InferenceServices behind the EXISTING ingress-nginx**, split by a
  hand-authored canary Ingress.
- **(iii) Dual-send from the client**, which the blueprint pre-approves as the
  mirroring alternative.

The kickoff's recommendation was **(ii) for traffic, (iii) for the v1
disagreement table**. This ADR confirms that recommendation and — the reason it
is worth reading — records **two constraints the spike found that nobody had
predicted**, either of which would have cost M6-S4 a session.

## Decision

**Traffic-split canary: option (ii), ingress-nginx canary annotations, subject to
two mandatory conditions.** Shadow of a different-schema challenger: **option
(iii), dual-send.** Knative is **not** adopted; ADR-004's fallback stays armed and
unspent.

### Condition 1 — the canary backend needs its OWN Service (or the split is silent)

`ingress-nginx` keys backends by `<namespace>-<service>-<port>`, and a backend
may hold exactly one role. Point a canary Ingress at a Service that some
*non-canary* Ingress also routes to, and the ordinary registration wins: the
canary link is created and its **weight is discarded**.

Measured, at weight 50, twice:

| | shared Service | dedicated Service |
|---|---|---|
| requests that left the champion | **0 of 200** | **100 of 200** |
| champion's `alternativeBackends` | `[serving-nyc-taxi-eta-shadow-predictor-80]` | `[serving-nyc-taxi-eta-canary-backend-80]` |
| canary backend `noServer` | `false` | **`true`** |
| canary `trafficShapingPolicy` | `{weight: 0, weightTotal: 0}` | **`{weight: 50, weightTotal: 100}`** |
| errors, warnings, events | **none** | none |

This matters more here than in a generic cluster, because **KServe RawDeployment
generates an Ingress for every InferenceService**. So the natural canary target —
a second isvc's predictor Service — *always already has* a non-canary Ingress,
and the natural implementation of option (ii) is exactly the one that silently
does nothing. The remedy is a plain Service selecting the same pods, referenced
by the canary Ingress alone; it is four lines, it touches no KServe object, and
it deletes cleanly.

The failure's SHAPE is the reason this is a condition and not a footnote: a
canary that reports `alternativeBackends` correctly, logs nothing, raises no
event, and moves zero traffic is indistinguishable from a canary at 0% — which is
what a 10% canary looks like to anyone who reads the annotation rather than the
counters. **A canary must be verified from traffic counters, never from its own
configuration** (the §9/M6 "canary 90/10 OBSERVED from metrics" leg, now with a
mechanism behind it).

### Condition 2 — both backends must serve the SAME V2 model name

In the Open Inference (V2) protocol **the model name is in the URL path**. The
champion's traffic asks for `/v2/models/nyc-taxi-eta/infer`. A second
InferenceService named `nyc-taxi-eta-shadow` serves a model called
`nyc-taxi-eta-shadow` and answers **404** — measured, 100 of 100 canary-routed
requests, never a number.

This is a property of *any* two-InferenceService split on this stack, not of our
particular challenger, and it cannot be fixed at the ingress: adding
`rewrite-target` to the canary Ingress changed the share by **0 points** (100/200
before, 100/200 after), because **ingress-nginx applies only `canary-*`
annotations from a canary Ingress and inherits the rest from the main one**.

The named remedy, which **M6-S4 must prove before it trusts a weight**: set
`MLSERVER_MODEL_NAME` on the canary InferenceService so both backends answer to
the champion's model name. It is one environment variable in a manifest this
program already renders at deploy time. It is recorded as unproven on purpose —
this spike's budget was spent, and a remedy asserted is exactly what this ADR
exists to stop being.

### What mirroring can and cannot do

`nginx.ingress.kubernetes.io/mirror-target` on the Ingress **KServe owns** was
probed and it **works at the ingress layer**: the annotation survived a
controller reconcile, and `nginx.conf` gained a real `mirror` directive. So
mirroring is available to this program for a **same-schema, same-name**
challenger.

It **cannot** shadow version 1, for two independent reasons already measured:
condition 2's 404, and — behind it — v1's logged signature covering 5 columns
while the wire carries 24 (F-032's shape). Hence dual-send for the disagreement
table, which is option (iii) chosen for a reason rather than by preference.

## Consequences

**Good.** No new serving stack; ADR-004's Standard-mode choice survives intact
and every M5 artifact stays true. The mechanism is four lines of YAML that the
KServe reconciler does not own and that delete cleanly. Both conditions are
discovered *now*, with numbers, instead of during S4's rehearsal under load.

**Costs, stated honestly.**

- A canary here is **two objects hand-authored outside the operator's model** — a
  Service and an Ingress that nothing reconciles. If someone deletes the isvc, the
  canary Service survives selecting nothing. S4 owns their teardown.
- **The admission webhook is still disabled** (`infra/helm/ingress-nginx/
  values.yaml`), and its own comment says *"re-enable it the day someone
  hand-writes an Ingress."* That day is today. It was **not** re-enabled in this
  story and that is a deliberate deferral, not an oversight: enabling it rolls the
  ingress-nginx controller, which F-033 forced onto `Recreate`, i.e. a real ~15 s
  outage of the only route into this cluster — and S4 hand-authors the same
  objects again, so the outage is better spent once, there, than twice.
  **Routed to M6-S4** with this paragraph as its argument.
- **A canary observed only from its annotation is not observed.** Condition 1's
  failure mode makes this a rule, not advice.

**What this ADR does not claim.** That the canary backend served correctly. Every
canary-routed request in this spike returned 404 by construction — the probe used
the v1 shadow as a convenient, distinguishable backend, and the 404 rate *is* the
split measurement. "The canary answered with a number" is S4's to demonstrate,
with the champion's own bytes behind it and condition 2 satisfied.

## Alternatives not taken

- **(i) Knative/Serverless.** Pre-refused by the kickoff and not needed: (ii)
  works. Adopting it would have replaced a four-line YAML mechanism with a second
  serving stack on a cluster that cannot be rebuilt, and invalidated the M5
  runbook and gate. Stays the fallback if S4 finds condition 2's remedy unworkable.
- **Cluster-wide `disableIngressCreation: true`** in KServe's
  `inferenceservice-config`, which would stop the generated Ingress that causes
  condition 1. Refused: it is cluster-scoped, so it would remove the **champion's**
  route as well, and hand this program's only ingress to hand-written objects. The
  dedicated-Service remedy is strictly smaller.
- **`rewrite-target` on the canary Ingress** to paper over condition 2. Refused
  because it was **measured not to work** (0-point change), not because it was
  disliked.
