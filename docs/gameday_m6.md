# Gameday 1 — what we predicted, what happened, and the one we got wrong

M6-S5 · 2026-08-19 · role:SRE (Accountable), MLOps (R)
Evidence: `automation/runs/m6-gameday/*.json` (predictions written before any
injection) · `automation/runs/m6-restore/restore_drill.json`
Commands: `make gameday` · `make restore-drill`

---

## 0. What this exercise is graded on, and why the bar is strange

§9/M6's accept bar is **"at least one prediction wrong and investigated"**, with
the reason written into the kickoff: *a gameday with all predictions right was
too easy*. That is not a licence to engineer a surprise. It is a bar on the
DIFFICULTY of the predictions: a drill that predicts only "something will break"
is satisfied by almost any behaviour and teaches nothing, so the predictions here
are quantitative, name specific alerts by id, and include what must **not** fire.

Every prediction in this document was written to
`automation/runs/m6-gameday/predictions.json` by
`make gameday GAMEDAY_ARGS="--scenario predict"` **before the first injection**,
and the file is committed. Two of them deliberately contradict the M6 kickoff's
own expectation (§1.2 below) — which is the honest way to make one of us wrong in
public rather than after the fact.

## 1. The positive control, and why it comes first

Three of the four scenarios make a claim of the form *alert X did NOT fire*. That
sentence is worth nothing from an instrument nobody has just watched work: a
Prometheus that lost its rules, an Alertmanager whose route broke, a scrape
config that silently stopped discovering the predictor would each produce a
flawless run of silent alerts. So scenario 0 fires two real alerts end to end
first. It is the prior-art ADOPT, and it is the reason the kill scenario's
"nothing fired" below is evidence rather than an absence of evidence.

**Injection** (`scripts/alert_fire_drill.py`, delegated to rather than
re-implemented): 4 req/s of two shapes this endpoint really produces — a
malformed V2 body answered **422** (F-030's class) and a body the model's logged
signature refuses answered **500** (F-032's class). Observed: **672 × 422 and
671 × 500**.

| signal | predicted | observed |
|---|---|---|
| A-3 `PredictorRequestRejectionRateHigh` (`for: 2m`) | fires at ~T+150 s | **pending T+50.5 s, firing T+170.5 s** |
| A-2 `ServingEdge5xxRateHigh` (`for: 5m`) | fires at ~T+330 s | **pending T+35.0 s, firing T+335.6 s** |
| order | A-3 then A-2 | **A-3 then A-2** |
| A-1 · A-5 (×2) · A-6 · A-7 | all stay inactive | **all inactive** |
| Alertmanager | holds both | **holds both** |
| an ordinary quote mid-injection | succeeds | **39.0019 minutes** |
| both clear after the stop | yes | **330.1 s after the stop** |

**GREEN 11/11** (`automation/runs/m6-gameday/control.json`). Two things worth
carrying forward from it. The **pending** timestamps are the honest measure of
detection — the expression crossed its bar within one scrape both times, and
everything after that is the `for:` window doing exactly what it was chosen to
do. And the **330 s to clear** is not a system being slow: with no other traffic
the ratio stays at ~0.5 until the last injected sample leaves the 5-minute rate
window, at which point the expression evaluates to `NaN` (0/0) and the rule goes
inactive on the next evaluation. An alert here cannot clear faster than its own
rate window, and that is the number an incident timeline should expect.

<!-- SCENARIO-0 -->

## 2. Scenario 1 — kill the predictor under load

**Injection**: 4 req/s open-loop for 300 s, concurrency 8, hazard mix — M5-S4's
headline shape — with the predictor pod deleted at **T+30 s** from inside the
load client's own per-second callback, so the kill and the latencies share one
clock.

| | predicted | observed |
|---|---|---|
| outage | 10–25 s | **13.75 s** (first failure 30.5 s → first success 44.25 s) |
| errors | a short burst | **55 of 1,200** — 52 × `503`, 3 × `502` |
| the replacement | a DIFFERENT pod object | uid `f7177380…` → **`3fd7165a…`** |
| alerts FIRING | **none** | **none** |
| Alertmanager | nothing | nothing |
| the edge 5xx share peak | **below A-2's 0.10 bar** | **0.5000 — WRONG** |
| `@champion` | unmoved | 2 → 2 |

The outage corroborates the three numbers this program already had: 14.53 s for
a killed pod (M5-S4), 15.0 s for the ingress roll (M6-S1), 18.24 s for a
stop/start (M5-S5). Four mutations, four numbers inside five seconds of each
other.

### 2.1 The prediction that was wrong, and what it changes

**The claim**: at 4 req/s a 5-minute rate window carries ~1,200 requests and a
~15 s outage costs ~60 of them, so the 5xx SHARE peaks near 5% and A-2's 10% bar
is unreachable by a single self-heal. The M6-S2 SLO document argues its threshold
in exactly those words: *"10% is unreachable by any single recovery ever measured
here."*

**What happened**: the share reached **0.5000**, and the rule's own state
timeline shows it — **A-2 went `pending` at T+89.2 s and back to `inactive` at
T+103.2 s.** Fourteen seconds of pending. `PredictorNoAvailableReplica` did the
same thing thirty seconds earlier: **pending T+59.1 s, inactive T+74.1 s.**

**Why the arithmetic was wrong.** It divided the outage's errors by a FULL
window's traffic, and the window is not full. `rate(...[5m])` extrapolates from
the samples actually inside the window, and 30 seconds into a load run that
window holds 30 seconds of requests, not five minutes of them. Immediately after
the kill the denominator is small and almost all of it is the outage, so the
ratio spikes towards 1 and then decays as ordinary traffic refills the window.
The steady-state figure the SLO document computed is the number the ratio decays
TO, not the number it reaches.

**So what actually stopped the page is the `for: 5m` sustain, not the
threshold** — and the same is true of A-5, where a 2-minute sustain absorbed a
15-second dip that a bare threshold would have paged for. Both alerts are
correct; both arguments for them were not. This is **F-041**, and
`docs/slo_serving.md` §3 now carries the correction beside the original
paragraph rather than instead of it (the `error_memo_m2.md` §9 precedent): a
threshold argued from a steady-state ratio is an argument about the wrong
quantity, and the sustain window is where the safety actually lives.

**The operational consequence is not cosmetic.** An on-call looking at
Prometheus during any ordinary self-heal will see two alerts **pending**, in red,
neither of which will ever fire. That is the system working, and nobody had
written it down.

<!-- SCENARIO-1 -->

## 3. Scenario 2 — break the storage credential, then delete the pod

**Injection**: `secret/minio-serving`'s `AWS_SECRET_ACCESS_KEY` overwritten with
a wrong value, then the predictor pod deleted. **No load at all** — deliberately,
because the point of this scenario is what the instruments say when a service is
completely down and nobody is asking it for anything.

**The undo was staged before the injection** (the M2 red-team rule; a unit test
asserts the capture lexically precedes the patch): the original bytes were
captured to a temp file outside the repository, and `make serve` — idempotent,
proven four times at M5-S2 — is the documented re-converge.

| | predicted | observed |
|---|---|---|
| the replacement | never starts | `Init:Error`, **3 restarts in 44 s** |
| the failure | 403 on the artifact store | `S3 error … (403) … HeadBucket: Forbidden` — **exactly M5-S2's class** |
| A-5 `PredictorNoAvailableReplica` (`for: 2m`) | ~T+150 s | **pending T+30.1 s, firing T+150.2 s** |
| A-7 `PredictorStorageInitializerNotReady` (`for: 3m`) | ~T+210 s | **pending T+30.1 s, firing T+210.2 s** |
| the order | A-5 **before** A-7 | **A-5 before A-7**, by 60 s |
| A-2 during a TOTAL outage | inactive | **inactive** |
| the flapping rule | inactive | **inactive** |
| the route | down | **503** |
| the undo | `make serve` restores it | exit 0; **A-7 cleared 15 s later, A-5 30 s** |
| `@champion` | unmoved | 2 → 2 |

**8/8 as predicted** (`automation/runs/m6-gameday/storage.json`). Three of those
rows are worth more than the pass.

**A-2 stayed silent through a complete outage**, which is the blind spot
`docs/slo_serving.md` §3 documents in a sentence — *a ratio has no value when
nobody is asking* — demonstrated rather than asserted. A-5 is the complement that
needs no traffic, and this is the scenario where that design decision earns
itself.

**The flapping rule stayed silent too, and for a reason that is easy to get
wrong.** `PredictorRestartFlapping` counts restarts of `kserve-container`. This
pod restarted three times in forty-four seconds — but every one of those was the
**init** container, and `kserve-container` never started at all. A rule written
against "the pod restarted" would have fired here and blurred two signatures into
one; the rule written against the model container does not.

**The signature is genuinely distinguishable from scenario 1**, which is the
property this pair exists to demonstrate: a kill gives a 14-second burst of edge
5xx, two alerts flickering `pending`, and no firing; a broken credential gives no
5xx ratio at all, a 503 route, and two alerts firing sixty seconds apart in a
fixed order.

### 3.1 The annotation that was wrong, and the change deliberately not made

A-7's own `why` annotation claimed it *"fires before A-5 does, because a pod that
never initialises never had a replica to lose"*. That is true about the CAUSE and
silent about the two `for:` windows underneath it: A-5 sustains for 2m and A-7
for 3m, and both expressions became true in the same scrape. **A-7 arrives
sixty seconds later, every time.**

The annotation is corrected in `infra/monitoring/alerting_rules.yml` to state the
measured order. **The threshold is not touched.** Making A-7 arrive first means
shortening it to ~1 m, which would be a threshold changed on the authority of the
number that had just been measured — the edit this program does not make on its
own (F-016's precedent). Recorded here as a recommendation for the M6→M7
boundary, with the honest counter-argument: what the pair actually buys is not an
ordering but a **signature** — *A-5 alone* is "the replica is gone", *A-5 then
A-7* is "the replacement cannot fetch its model" — and that signature works
whichever arrives first.

<!-- SCENARIO-2 -->

## 4. Scenario 3 — saturate the CPU

<!-- SCENARIO-3 -->

## 5. The restore rehearsal — the label moves one notch, not to green

Every backup artifact this program has written since M4-S2 carried the same
sentence: **RESTORE IS NOT REHEARSED.** The dumps were proven COMPLETE (a gzip
CRC over every byte plus pg_dump's own completion marker, both legs red-teamed
against a deliberately truncated copy of the real 1.2 GiB file) and the object
mirror was proven by count AND bytes — but "these files restore a working
platform" stayed a hypothesis, and a hypothesis in a lifeboat is the worst place
to keep one.

`make restore-drill` (`scripts/restore_rehearsal.py`) is that hypothesis tested
as far as a stateful cluster allows. **GREEN 17/17**, record
`automation/runs/m6-restore/restore_drill.json`, backup
`2026-08-19T05-59-36Z`.

| what | result |
|---|---|
| `mlflow` → `mlflow_restore_drill` | restored in **2.34 s**, `ON_ERROR_STOP=1`, exit 0 |
| `optuna` → `optuna_restore_drill` | restored in **0.78 s** |
| `metabase` → `metabase_restore_drill` | restored in **7.29 s** |
| counted tables vs the LIVE database | mlflow `experiments=8 runs=101 registered_models=1 model_versions=2` · optuna `studies=5 trials=59` · metabase `report_card=67 report_dashboard=4 core_user=2` — every one equal |
| the restored registry's alias | `champion\|2`, identical to live |
| the restored studies vs `automation/runs/m3s4/sniper-*.json` | `m3-sniper-v1: 9` · `m3-sniper-v2: 21` — the trial counts M3-S4 recorded |
| the restored boards vs `analytics/metabase/boards/*.json` | all **3 dashboards / 28 cards** present BY NAME |
| objects | `flyte-data` restored **whole** — 184 objects / 783,327 bytes into a scratch bucket in 31.7 s, count AND bytes equal to the mirror on disk |
| one MLflow artifact | restored and **byte-identical to the live object by sha256** (`1/models/m-c6ba7243…/artifacts/MLmodel`) |
| the live platform | database list unchanged, bucket list unchanged, **no scratch survives** |

**What this claims.** The three small, irreplaceable dumps load into a running
Postgres and produce databases whose contents match both the live platform and
records committed in this repository, and the object mirror uploads back
byte-identically.

**What it refuses to claim, and this is the point.** Nothing was restored OVER
anything. Every database was created fresh under a `_restore_drill` suffix and
dropped; every object went into a scratch bucket that was deleted. **A full
restore over a dead platform is still un-rehearsed** and needs a PO-sanctioned
rebuild to try. So every artifact that read *NOT REHEARSED* now reads
*scratch-rehearsed 2026-08-19; full restore over a dead platform still not* —
one notch, and no further. A drill that overstated itself would be worse than
the sentence it replaced.

**Why `marts` is not in it.** 1.2 GiB of the 1.6 GiB backup, and the ONE database
already provably rebuildable from DVC pins plus `make marts` (M1-S5's
fresh-volume proof, which republished 56,127,878 rows onto a brand-new volume and
matched M1-S4's counts to the row). Restoring it into a scratch database would
cost the peak M4-S5 measured — 2.075× the database size — to re-prove a path
another proof already covers.

**The transport is the one `make marts` already uses**, and for the same reason:
`zcat` on the host piped into `kubectl exec -i psql` inside the pod. Nothing of
ours publishes 5432, and a restore procedure that first needs a port opened is a
procedure nobody can run during an incident.

### 5.1 The check that was wrong, kept because it found something real

The drill's first run went **RED on one check of seventeen**, and the restore was
not what was wrong. The check compared the restored Metabase app-db against
`analytics/metabase/boards/*.json` by COUNT and expected 3 dashboards / 28 cards.
It found **4 / 67**.

The extra content is Metabase's own: an `E-commerce Insights` dashboard and its
example questions, created by Metabase's setup from the bundled Sample Database
(`creator_id 13371338`, its internal user). Nothing was broken, and nothing had
drifted — **`scripts/metabase_boards.py` converges by name and never deletes**,
which M1-S5 stated as a deliberate asymmetry, so the app-db is a SUPERSET of the
repo's boards by design.

The check is now a subset check by NAME: every dashboard and every card this
repository commits must survive the restore, and what else the app-db holds is
recorded rather than judged. Worth keeping because of what it corrects in the
prose elsewhere: *"the boards are checked-in JSON"* is a claim about **our**
boards. It was never a claim that the app-db mirrors the repository, and a check
written as though it were would have gone red on a correct backup of a correct
platform every time it ran.

<!-- ACCEPT -->
