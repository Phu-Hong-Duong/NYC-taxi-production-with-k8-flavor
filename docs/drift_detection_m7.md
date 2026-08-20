# Drift detection (M7-S3) — the alert that fired, and the one that correctly did not

**Owner:** SRE (accountable), DA (reviewer). **Written:** 2026-08-20.
**Thresholds:** none live here. Every drift bar is argued in
`docs/slo_serving.md` §8 and implemented once, in
`infra/monitoring/alerting_rules.yml`. This document is the story of running it.

---

## 0. The headline, before the detail

March 2020 is the largest demand shock in this city's recorded history. Put
through a drift monitor comparing it with the champion's training distribution:

| | 2020-01 | 2020-02 | **2020-03** | *held-out 2019 months, for scale* |
|---|---|---|---|---|
| max **input** column PSI | 0.0103 | 0.0087 | **0.0217** | 0.0323 (val) · 0.0137 (test) |
| trips/day ÷ reference | 0.8336 | 0.8776 | **0.3913** | 0.8216 (val) · 0.7899 (test) |
| A-8 input drift (bar: 2 columns ≥ 0.10) | inactive | inactive | **inactive** | — |
| A-9 volume (bar: < 0.50) | inactive | inactive | **FIRED at T+331.5 s** | — |

**Read the top row twice.** COVID March's most-moved input column sits at PSI
**0.0217** — *lower than an ordinary July 2019 does* (0.0323). By the shape of
its requests, March 2020 is not a strange month. The city did not start taking
different taxi trips; it stopped taking taxi trips.

Everything worth saying in this story follows from that one fact.

---

## 1. What was built

| Piece | Where | What it does |
|---|---|---|
| The drift job | `taxi_mlops.monitoring.drift` | Exact PSI from DuckDB value counts, one scoring month against `trips_train` |
| The second witness | `taxi_mlops.monitoring.drift_evidently` | Evidently 0.7.21 on a seeded sample, corroborating, never alerting |
| The push client | `taxi_mlops.monitoring.pushgateway` | Text exposition format, `PUT`, and a freshness guard in a type |
| The CLI | `python -m taxi_mlops.monitoring` | `headroom` · `drift` · `push-state` |
| The gateway | `infra/helm/monitoring/prometheus-values.yaml` | Subchart on, **no hostPort** (M7 law 1), own scrape job with `honor_labels` |
| The rules | `infra/monitoring/alerting_rules.yml` | A-8, A-9, A-10 (drift) + A-3's client half and A-4 (F-035) |
| The drill | `scripts/drift_fire_drill.py` | Prediction first, push, observe, judge |
| A-3's client counter | `taxi_mlops.monitoring.client_counters` | The quote client counts its own refusals |
| A-4's version pusher | `scripts/push_serving_version.py` | Two series where F-034 said there were none |

`make backup` ran first, before the new tenant landed — the standing precedent
(M4-S2/M5-S1/M6-S1). Manifest `2026-08-20T04-07-22Z`: **6 databases, 1.6 GiB,
every dump gzip-CRC clean with pg_dump's own completion marker.**

---

## 2. The order of work, because with a drift bar the order IS the argument

M7 law 4 forbids a threshold set equal to the number just measured. That law
bites harder here than anywhere else in the program, for a reason worth naming:
every other threshold in `docs/slo_serving.md` was argued against a service
nobody was trying to prove anything about. A drift bar is argued against a month
this program went and fetched **because it expects it to be extreme**.

So the order is recorded, and it is checkable from git and from the records' own
clocks rather than from this paragraph:

| # | What | Evidence |
|---|---|---|
| 1 | The **headroom leg** ran, reading 2019 only | `automation/runs/m7-drift/headroom.json` |
| 2 | The bars were written from it | `docs/slo_serving.md` §8, commit `d113f26` |
| 3 | The **prediction** was written | `automation/runs/m7-drift/prediction.json`, same commit |
| 4 | *Then* 2020-01..03 were compared | `automation/runs/m7-drift/drift-2020-*.json` |

Steps 2 and 3 are in a commit that lands **before** any 2020 drift record exists
in the repository. A bar chosen after step 4 would be a bar chosen to make an
alert agree.

### 2.1 Why the headroom leg is legitimate and a 2020 measurement would not be

The two held-out 2019 months are the only data here that is *known* not to have
warranted action: the champion was measured on them and **PROMOTED**. Whatever
distance they sit at from the reference, the program has already decided to live
with it. That is what makes it legal to argue a bar from them.

The largest is **0.0323** — `dayofweek` in July 2019 — and *what* it is matters
as much as how big: July 2019 held five Mondays against the reference months'
average, so it is **calendar arithmetic**, the least model-meaningful move a
month can make. The largest genuinely behavioural number is `PULocationID` at
**0.0137**.

The bar 0.10 is therefore **3.1× the noisiest accepted month and 7.3× the
largest behavioural one**, and it independently coincides with the published
PSI "investigate" convention — which matters because an on-call who did not
write this document already has a prior for what 0.10 means.

---

## 3. The drill, and what it predicted

`make drift-drill`. **PASSED**, prediction on disk before anything was computed.

The negative predictions are the load-bearing half — a drill that predicts only
"something fires" cannot be wrong. Nine alerts were predicted **inactive**,
including A-9 itself *for the two ordinary months*, which is the prediction that
distinguishes a working bar from a bar so low that any month trips it.

```
A-9 ScoringVolumeCollapse   month=2020-03   pending T+31.5s -> FIRING T+331.5s
                                            (5m sustain, honoured to 1.5 s)
A-9                         month=2020-01   never fired    — as predicted
A-9                         month=2020-02   never fired    — as predicted
A-8 ModelInputDrift         all months      never fired    — the open question, answered
A-10, A-4, A-3, A-1, A-2, A-5, A-6          never fired    — as predicted
Alertmanager holds: ['ScoringVolumeCollapse']   @champion 2 before and after
```

### 3.1 The open question was pre-registered as the one most likely to be wrong

`PREDICTION["the_open_question"]` carries `confidence: low` and its own
reasoning: whether A-8 fires on 2020-03 **at monthly grain**. The prediction was
that it does not, because 68.23% of March's surviving rows are 01–10 March,
which is an ordinary New York month, and a monthly aggregate is weighted by
exactly the rows that did not vanish (F-045's mechanism, M7-S1).

**The prediction was correct**, and the drill reports it without judging it — a
question with `confidence: low` attached is a question, and failing a drill on
the answer to a question is how a drill teaches people to stop asking any.

### 3.2 "Then cleared" needed an argument here, not a copy

M6's drill cleared its alerts by **stopping an injection**. This drill injected
nothing: March 2020 really did lose 61% of its trips, and an alert saying so is
correct. Latching it off to make a transcript tidy would be publishing a false
board.

So the clearing is demonstrated on the *mechanism* and then undone: the month's
group is deleted, A-9 is watched going inactive (proving the rule follows the
data and is not stuck), and the real numbers are pushed straight back. **The
board ends carrying the truth about March 2020** — and the decision that alert
is asking for is M7-S4's retrain, not a silence.

---

## 4. The finding: the shape alert missed and the volume alert caught

This is the story's substance, and it is not what the milestone expected.

**A-8 did not fire on the most drifted month this program will ever hold, and
that is not a failure of the bar.** It is a property of the event:

* PSI is a distance between **shares**. Halve every count and PSI is exactly
  zero. A city that stops moving while keeping the same mix of trips is
  *structurally invisible* to it.
* March 2020 is very close to that. Its most-moved input column reads 0.0217 —
  below an ordinary July. Its `hour` distribution moved 0.0098. What collapsed
  was **how many**, not **which kind**.

Had A-9 not existed as a separate signal, this stack would have watched the
COVID collapse in silence with every drift panel green. That is the strongest
possible argument for `docs/slo_serving.md` §8.1's claim that A-9 is *not a
refinement of A-8 but the marginal A-8 cannot see* — written before the run, and
then demonstrated by it.

**F-045 is now measured from three sides.** M7-S1 found it in the raw data (a
monthly mean duration that moves 0.36%, less than an ordinary Jan→Feb wobble).
M7-S2 found it on the output side (whole-month KPI-14 3.3227, ordinary, hiding a
last-ten-days 5.3128). M7-S3 finds it on the *input* side: monthly-grain PSI
0.0217. **Three independent instruments, one conclusion: a monthly aggregate
cannot describe this event, and only volume survives the averaging.**

### 4.1 What did move, for the memo

The largest single bin moves in 2020-03 against the train reference are in
`automation/runs/m7-drift/drift-2020-03.json` under each column's `top_moves`.
`dayofweek` leads the input columns at 0.0217, `passenger_count` follows at
0.0171 — and the geography columns, which §8's prediction expected to lead
("a demand shock is spatial before it is temporal"), came **third and fourth**
(`DOLocationID` 0.0151, `PULocationID` 0.0143). **That sub-prediction was
wrong**, and it is left standing here beside its refutation rather than edited
(the `docs/ablation_m3.md` §5 precedent). The honest reading is that at these
magnitudes the ordering is noise: six numbers spanning 0.0098 to 0.0217 are not
a ranking, they are a flat line, which is itself the finding.

The interpretation — *what actually changed in March 2020, in domain terms* — is
**M7-S5's memo** and deliberately not attempted here. This story detects; the
memo interprets (BLUEPRINT §9/M7).

---

## 5. The second witness, and the failure it nearly reported

Evidently 0.7.21 runs on a seeded 200,000-row sample per side
(`make drift-witness`, record `second_witness.json`). It is **not** the alerting
instrument, and the reason is arithmetic: five of six monitored columns are
categorical, so their distributions are completely described by value counts,
which DuckDB computes **exactly** over 43,987,422 reference rows in seconds. A
sampled estimate of an exactly-computable quantity is a worse number that also
moves between runs — and a threshold compared against a number that moves when
nothing moved is the shape of every alert nobody trusts.

What it is for is the thing this program does everywhere else: **a claim only
one instrument can make is not checkable.** `drift.py` is code we wrote and its
PSI could be wrong in a way its own tests share.

**On the question the alert asks, the two instruments AGREE, for both months:**

| | our PSI ≥ 0.10 | Evidently past its own default | verdict on INPUT drift |
|---|---|---|---|
| 2020-01 | (none) | `trip_duration_minutes` | **agree: no input drifted** |
| 2020-03 | (none) | `trip_duration_minutes` | **agree: no input drifted** |

Two independent implementations, different statistics (Wasserstein-normed for
the numeric column, Jensen-Shannon for the categoricals — recorded per column in
`methods`), and the same answer: **the inputs did not move; something about the
target did.** That is corroboration of the design's central split, not of its
arithmetic.

*And it is worth reading Evidently's own flag sceptically*: it calls
`trip_duration_minutes` drifted at **0.1014 in January and 0.1008 in March** —
essentially the same value in an ordinary month and in the collapse, both barely
over its 0.1 default. It does not distinguish the two either. Quoting it as
"Evidently detected drift in March" would be true and misleading.

### 5.1 The parser failure that wore a finding's clothes

The first run of the witness printed **"the two instruments DISAGREE"** for
every column, with an empty ranking on one side. Nothing had disagreed: the
parser looked for `metric_id` and a `status` field, and Evidently's `.dict()`
has neither — it carries `metric_name`, a structured `config` (column, method,
threshold) and `value`.

Worth recording because of the direction of the error: **a second witness that
cannot be read reports maximum disagreement**, which is simultaneously the most
alarming thing it could say and the least true. The fix was to read the shape
off a real snapshot instead of assuming it (`automation/runs/m7s3-evprobe/`).

---

## 6. F-035 CLOSED — both absences now have a metric source

M6-S2's finding was precise: *the fact lives in a CLIENT, and no client here is
scraped.* The pushgateway is what changes that, and it was being installed for
drift anyway — which is exactly the landing M6-S2 costed.

**A-3's client half.** `taxi_quote_refusals_total`, pushed by the quote client
when F-019's `UncoveredDateError` refuses a request (`make quote
--push-metrics <url>`; off by default, because the gateway has no hostPort and a
quote must not fail its metrics leg on a laptop with no port-forward). The rule
is `increase(...[1h]) > 0` and that shape is the argument: this is **not** a
rate problem needing a fleet. One refusal means the holiday table's horizon has
expired — a fact about the repository, not about traffic — so a single event *is*
the event, and a threshold above zero would be a decision to serve some refusals
quietly.

**A-4.** `scripts/push_serving_version.py` asks the endpoint for one real
prediction (the version is stamped on the **answer**, M5-S2 — `GET
/v2/models/nyc-taxi-eta` reports `versions: []` on this runtime) and the registry
for the alias through F-009's one resolver, then pushes both. F-034 said there
were not two series to compare; now there are.

**Its rule requires freshness as well as agreement**, and that clause is
load-bearing rather than decorative: a stale pushed pair agrees with itself
forever, so without it a dead pusher reads as a healthy service.

**The honest cut, stated because it is real:** M7-S3 lands the metric *source*,
which is what F-035 said was missing. What runs the pusher on a **cadence** lands
with M7-S4, the story that installs a scheduler. Until then A-4's freshness half
is what stops the version half from lying, and `verify-m5` §2 remains the check
that actually runs, at every gate.

**The closure is enforced, not asserted.** `scripts/render_alert_rules.py`'s
`IMPLEMENTED_SIGNALS` now holds all ten ids and `DOCUMENTED_ABSENCES` is empty,
and `validate()` fails in **both** directions — so this closure could not have
been written in prose without the rules existing, and a future absence cannot be
created by quietly deleting a rule.

---

## 7. F-043 CLOSED — the instrument limit is documented where thresholds live

The M6→M7 boundary decided option (c): accept, and state the limit. Landed as
`docs/slo_serving.md` **§2.2**, with the measurement rather than a caution —
under a throttled fraction of 0.9996 the loaded predictor's `/metrics` went from
4 ms to **4.613 s with one scrape failing outright**, while the idle v1 shadow,
scraped by the same job every 15 s, held **0.004 s**. 1,150× apart. That is why
A-1 fired at T+349.3 s and cleared *itself* at T+514.3 s mid-event.

§2.2 carries a table of which instruments survive saturation (node-side cAdvisor
and edge-side ingress do; anything in-pod does not), and **A-1's rule now carries
an `instrument_limit` annotation** saying so at the rule, where an on-call reads
it. No target loosened and no threshold moved: an instrument limitation is
documented, not a bar changed.

One line worth carrying forward, from §2.2: **the cheapest possible control for
"is this exporter lying?" is a second, idle instance of it scraped by the same
job.** Here that control was an accident — an M6-S3 leftover — and it is the only
reason F-043 is a measurement rather than a theory.

*Drift metrics are structurally outside this failure mode*: a batch job pushes to
a gateway on another node, so the producer and the scrape are decoupled by
design.

---

## 8. The two failure signatures, side by side

The kickoff asks for these to be recorded distinguishably in one place. S1
produced the second; this story produced the first.

| | **Statistical drift** | **Schema drift** |
|---|---|---|
| Example | 2020-03 (M7-S3, this document) | a dropped/renamed/added column (M7-S1's fixtures) |
| Ingest | **succeeds**, exit 0 | **refuses**, `SchemaEventError`, **exit 1** |
| Rows written | 2,948,237 | **none** — no output, no sidecar, no report |
| Drift metric | computed, pushed, on the board | **none exists at all** |
| Alert | A-9 fires (A-8 correctly does not) | **nothing can fire** |
| What an operator sees | a red alert naming the month | a failed job; the drift board is *unchanged* |
| How it is caught | Prometheus | the pipeline's exit code — and A-10, eventually |

**The second is the dangerous one and A-10 is why it is in this document.** A
schema refusal produces no drift metric, so the drift board looks exactly like a
healthy month — gotcha #78's empty-panel disease with the panel removed
entirely. The only signal that a month *should* have been compared and was not is
**staleness**: `taxi_drift_last_run_timestamp_seconds` stops advancing, and
A-10 fires at 40 days. That is a slow guard, and it is honest about it; the fast
guard is the pipeline exit code, which is M7-S4's to wire into a schedule.

---

## 9. Decisions and their costs

**Evidently is ADOPTED, not DIFFERed.** The risk table's headline risk — the
resolver quietly downgrading pandas, gotcha #36's shape — did not materialise.
Probed **first**, in an isolated venv pinning this project's four numeric cores
(`automation/runs/m7s3-evprobe/`): resolves, imports, computes. Then added for
real: **27 packages installed, 1 uninstalled (the project, rebuilt), pandas
3.0.5 · numpy 2.5.2 · scipy 1.18.0 · scikit-learn 1.9.0 · lightgbm 4.7.0 ·
mlflow-skinny 3.15.1 all unchanged.** Its honest cost is 27 packages including a
web-server stack (litestar, uvloop, watchfiles) for a library used by one
corroborating script; that is priced and accepted rather than hidden.

**The reference is the train months and never moves.** Cost, stated: a
legitimately-changed world keeps alerting until someone retrains and re-declares
it. That is intended — an alert that silences itself by redefining normal is the
drift-monitoring failure mode. The alternative (compare each month with the
previous one) makes a world that drifts 3% a month invisible forever.

**The job pushes raw quantities and issues no verdict.** No threshold appears
anywhere under `src/taxi_mlops/monitoring/`, pinned by an AST test rather than a
grep (these modules argue their own design at length; a word search would match
the argument — gotchas #53/#68). The bar lives in the selector of one rule, so
the pushed numbers stay re-interpretable after the fact.

**Monthly grain, and it is a known limitation rather than a choice defended.**
The kickoff specifies "current = one scoring month" and that is what shipped. §4
shows what it costs: at this grain the input signal is flat through a
catastrophe. A daily or rolling-window drift job would very likely fire A-8 on
22–31 March, and the daily series already exists in both engines (M7-S2's
`scoring_daily`). It is **not** done here because changing the window after
seeing that A-8 stayed quiet is precisely the threshold-walking M7 law 4
forbids — the window is part of the bar. It is written up as a candidate for
ARCH at the M7 boundary, with the evidence, and it is not this story's to decide.

---

## 10. What this story did NOT do

* **No schedule.** The drift job is a callable and a CLI. What runs it monthly is
  M7-S4's (which installs a scheduler for the retrain anyway).
* **No board.** The Grafana/Metabase drift panels are M7-S5 leg 1's, with the
  memo they illustrate.
* **No retrain and no alias move.** `@champion` is version 2, read before and
  after every phase of the drill, and an AST test forbids a registry-mutating
  verb anywhere in this story's code (M7 law 3).
* **No threshold walked.** The bars are exactly as committed in `d113f26`, before
  a 2020 month was compared.
