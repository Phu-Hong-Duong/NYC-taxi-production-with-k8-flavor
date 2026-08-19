# M5-S4 — what the endpoint costs under load, and what losing it costs

*Executor session, 2026-08-19. Role block: SRE. Every number here was produced by
`make load-drill` and every one of them is in a tracked JSON under
`automation/runs/m5-load/`. Nothing was promoted, no alias moved, no manifest
changed; the only mutation in the story is one pod deleted and immediately
replaced by its own controller.*

---

## 0. The one-paragraph version

At **4 requests/second for 60 seconds at concurrency 8**, over the committed
hazard mix, the deployed champion answers with **p50 17.2 ms, p95 104.2 ms,
p99 107.2 ms, max 115.4 ms** and **zero errors in 240 requests**, costing
**1.31 of its 2 CPU cores** (0.326 core-seconds per request). Its ceiling is
between **6 and 8 req/s** for this pod: 6 req/s runs at 96% of the CPU limit and
8 req/s at 101%, where p50 jumps from 18 ms to 116 ms. **Killing the predictor
pod mid-load costs 14.53 seconds of unavailability** — 58 failed requests, 56 of
them `503` — after which a **different pod object** (a new uid, on a *different
node*) serves the **same model version**, and the remaining 559 requests of the
window all succeed. One replica, so a lost pod is a real outage and not a blip.

## 1. The shape is part of the number

`docs/kpi_definitions.md` made this program's rule explicit for money KPIs: a
figure states its window and its treatment inline, because a number that outlives
its conditions gets quoted in conditions that never held. A latency percentile is
the same object. So every record here carries the rate, the window, the
concurrency, the request mix, the rows per request and the **achieved** rate, and
`summary_lines` will not print a percentile without them.

Two design choices do the actual work.

**The loop is open.** The cheap way to load a service is a closed loop — N
threads, each firing the next request when the last returns. It measures the
wrong thing: the arrival rate becomes a *consequence* of the latency, so when the
server slows down the client politely sends less, the queueing a real arrival
stream would cause never happens, and the p95 you publish is the service time of
an unloaded server wearing a load test's clothes. That is coordinated omission.
Here request *k* is due at `t0 + k/rate` whether or not anything is free to send
it, and two quantities come out:

| | measured from | what it answers |
|---|---|---|
| `service_ms` | sent → response | what the server took |
| `latency_ms` | **scheduled** → response | what a caller who wanted a quote *at that instant* waited |

`latency_ms` is the headline. While the client keeps up they are equal — in the
headline run they differ by 0.1 ms — and when they diverge the run has told you
its stated rate was not achieved, which is exactly the fact a closed loop hides.

**The percentiles are nearest-rank.** No interpolation, so every number quoted is
a request that actually happened. For a figure going into a Production Readiness
Review, *some request took this long* is a stronger sentence than *the
distribution suggests*.

**What is not in the number.** The feature matrix is built once, before the clock
starts, and the request bodies are JSON-encoded before it too. These percentiles
are the wire and the server: encode → ingress → mlserver → MLflow → LightGBM →
back. They do **not** include `quote_time.build_features`, which in M5 runs in
the caller's process (~30 ms cold for one row) and which M7 moves into a KServe
transformer — at which point it lands *inside* this measurement. Saying so now
means M7's delta reads as a boundary moving rather than as a regression.

The mix is `parity.HAZARDS` — the sixteen committed rows M5-S3 declared: the
airports, the two no-geometry zones, the unseen OD pair, the long-haul tail, the
clock seams. A load test that sends one Midtown hop 600 times exercises one path
through the trees and the identical serialisation buffer every time.

## 2. The ramp — the headline rate is chosen, not guessed

Four rates, 20 s each, concurrency 8, hazard mix. CPU is read from the
container's own cgroup (`cpu.stat`) before and after each step and differenced;
`kubectl top` is unavailable on this cluster (no metrics-server, checked) and
installing one to fill in a capacity box would be a platform change inside a
measurement story. The cgroup counters are what a metrics-server would sample
anyway, and a delta of a cumulative counter over a known wall time has no
sampling error at all.

| target | achieved | errors | p50 | p95 | p99 | mean cores | % of 2-core limit | throttled periods |
|---|---|---|---|---|---|---|---|---|
| 2 req/s | 2.049 | 0 | 18.5 ms | 85.5 ms | 86.0 ms | 0.692 | 35% | 46 |
| 4 req/s | 4.046 | 0 | 19.1 ms | 108.6 ms | 113.9 ms | 1.447 | 72% | 102 |
| 6 req/s | 6.046 | 0 | 18.1 ms | 81.9 ms | 107.3 ms | 1.920 | **96%** | 158 |
| 8 req/s | 8.043 | 0 | **115.5 ms** | 190.1 ms | 230.0 ms | 2.018 | **101%** | 199 |

The knee is unmistakable at 8 req/s, where p50 goes from ~18 ms to 115 ms because
the container is spending its whole quota and the kernel is stopping it. **The
selection rule takes the highest step that held its stated rate, returned no
errors, *and* stayed under 90% of the CPU limit** — 4 req/s. The third clause was
not there the first time this ran, and §5 is what it cost.

Note that throttling is non-zero at *every* rate, including 2 req/s at 35% mean
utilisation. That is not a contradiction: CFS accounts in 100 ms periods, and a
single inference burst wider than the quota inside one period is throttled even
when the minute-long average is a third of the limit. Mean utilisation is a
budget statement; the throttle counter is a latency statement.

## 3. The headline

```
[load] headline-4rps-60s: hazards mix, 1 row(s)/request, target 4 req/s for 60s
       at concurrency 8 -> achieved 4.02 req/s over 59.8s
[load] requests 240 ok 240 errors 0 (0.00%)
[load] latency_ms (scheduled->response)  p50 17.2  p95 104.2  p99 107.2  max 115.4
[load] service_ms (sent->response)       p50 17.0  p95 104.1  p99 107.1  max 115.3
[load] served by version(s) ['2'] — stamped on the timed responses
[drill] capacity: 78.2 CPU-seconds over 59.8s = 1.31 mean cores of a 2 CPU limit
        (0.326 core-s/request); throttled 246 period(s) for 183.1s;
        memory now 236 MiB, peak since start 284 MiB
```

**The version is read off the timed responses themselves**, not from a metadata
call: mlserver stamps `model_version` on every answer, so "which model served
this window?" is answered by the answers. All 240 say `2`, which is what
`@champion` resolves to.

### Capacity, for the PRR

| | observed | configured |
|---|---|---|
| CPU, mean over the window | **1.31 cores** | request `200m`, limit `2` |
| CPU per request | **0.326 core-seconds** | — |
| memory, current | **236 MiB** | request `1Gi`, limit `3Gi` |
| memory, peak since container start | **284 MiB** | — |
| replicas | **1** | 1 |

Three things a reader should take from this table and one they should not.

- **The CPU request is wrong by an order of magnitude.** 200m is what the
  scheduler uses to place the pod and what a future autoscaler would use to
  decide it is idle; the pod actually needs ~1.3 cores to serve 4 req/s and 2.0
  to serve 8. This is a real finding but it is **not fixed here** — changing a
  deployed workload's resources is a change to what is on the wire, and M5-S4 is
  a measurement story. It is written into the PRR's capacity box as S5's input.
- **Memory is comfortable and flat.** 236 MiB steady against a 1 GiB request; the
  284 MiB peak is cumulative since the container started, so it is a high-water
  mark and not a window measurement — a *delta* of `memory.peak` would mean
  nothing and is not reported.
- **0.326 core-seconds per single-row request is expensive** for a LightGBM
  predict over 24 features, and almost all of it is the runtime rather than the
  trees: an HTTP hop, a JSON decode, a pandas frame, MLflow's signature
  enforcement, and back. At 8 req/s it falls to 0.251 core-s/request — the same
  fixed costs amortised over more work. Batching (`rows_per_request`) is the
  obvious lever and the client already takes it; nothing in M5 needs it.
- **What not to take:** this is one pod, one node, on a laptop that is also
  running the whole kind cluster, the Postgres holding 13 GB of marts and this
  session. These numbers are a capacity *shape*, not a production SLO. The SLO
  document is M6's by the kickoff's own scope list.

## 4. Losing the pod

`kubectl delete pod` fires **from inside the load window**, at T+25 s of 180 s,
through the load client's own per-second callback — so the kill and the latencies
share one clock. A kill scheduled by a separate `sleep` in a shell lands at an
offset nobody measured, and "the error window was 14 seconds" would be 14 seconds
from an event whose position is a guess.

**The prediction was written to disk before the kill** (`kill-prediction.json`,
`written_before_the_kill: true`). M4-S5's kill drill established that habit the
expensive way: it predicted a pod *name*, the controller recreated the pod under
the same name with a new uid, and a correct survival was reported as a failed
drill. The wrong prediction was kept rather than quietly corrected, and the
property was fixed to the one that holds under every controller's naming scheme.
This drill asserts the same thing: **identity, never a name.**

```
[drill] T+25s: deleting pod nyc-taxi-eta-predictor-7ff5ccd649-77b54
        (uid f6bf83df-e734-42e0-a424-b5714e4c8270)

  ok   the kill fired inside the load window (T+25s)
  ok   a DIFFERENT pod object serves afterwards: uid f6bf83df-… -> 2ba0096c-…
  ok   the kill was actually felt: 58 failed request(s), classes {'HTTP 502': 2, 'HTTP 503': 56}
  ok   AVAILABILITY returned inside the load window: unavailable for 14.53s
       (first refusal T+25.5s -> answering again T+40.03s of 180s), 15.03s from
       the kill itself, 14s of it with no successful response at all
  ok   the service stayed UP for the last 30s: every second returned at least one
       successful response (30 bucket(s))
  ok   one model version served the whole window: ['2']
  ok   the endpoint answers cleanly after the drill
```

| | |
|---|---|
| unavailable | **14.53 s** (first refusal → answering again) |
| from the kill itself | 15.03 s |
| seconds with no successful response at all | 14 |
| failed requests | 58 of 720 (56 × `503`, 2 × `502`) |
| requests after recovery | 559, **0 errors** |
| errors before the kill | 0 of 100 |
| replacement | a different uid — **and a different node**: `mlops-taxi-worker` → `mlops-taxi-worker2` |
| model version, whole window | `2` |

Three things worth reading twice.

**The replacement landed on a different node, and that was already paid for.**
M5-S2 delivered the predictor image to all three nodes with `kind load` and its
note in CLAUDE.md says why: *"required, not convenient: M5-S4 kills the predictor
and the replacement may land elsewhere."* It did. Had the image been on one node
the drill would have measured an `ImagePullBackOff` instead of a recovery.

**58 failed requests is not the same fact as 14.53 seconds**, and the drill
reports both because they answer different questions. The seconds are what the
runbook quotes; the request count is what an SLO's error budget would be spent
from, and it is a function of the rate.

**The residual error rate after recovery is measured and deliberately not
gated.** 0 of 559 after recovery, against 0 of 100 before the kill — the pre-kill
segment of the same run is the only fair control available (same client, same
rate, same minute). An error-rate *threshold* would be an SLO, the SLO document
is M6's, and inventing one here would mean setting a bar from the number that had
just been seen.

**The honest reading of 14.53 s:** one replica, and a pod that must run an init
container to download the model out of MinIO before mlserver starts. There is no
second replica to absorb the gap and no canary to shift to — `canaryTrafficPercent`
requires Serverless mode and ADR-004 chose Standard, whose cost this program has
been recording since M1's prior-art read. So on this deployment, *any* event that
replaces the predictor pod — a node drain, an image change, a rollback — costs
about fifteen seconds of 503s. That is M6's material, and the runbook M5-S5 writes
should quote this number rather than a hope.

## 5. What the first attempt measured, and why it is kept

The first run of this drill is preserved, unedited, at
`automation/runs/m5-load/attempt1-at-the-ceiling/`. It went **RED**, and it was
right to.

Its ramp selection rule had two clauses instead of three — highest step that held
its rate with no errors — so it chose **8 req/s**, at which the container ran at
**2.003 of its 2 cores** and was CPU-throttled in **601 of ~601 periods**. Two
things followed:

1. The headline p95 it produced (237 ms) is a measurement of the *CFS quota*, not
   of the service. Every millisecond above ~100 was the kernel stopping the
   process.
2. The self-heal leg became unreadable. Sitting on the limit, a perfectly healthy
   pod drops the odd request: the run showed a 13-second dead window and then
   **ten more scattered 502/503s over the following 170 seconds**, one at a time,
   at T+50, 59, 63, 68, 121, 138, 149, 170, 200, 205. The kill's cost could not
   be separated from the load's.

And the drill's own arithmetic made it worse. It reported
`outage_seconds_measured: 182.4` — because it computed *last error minus first
error*. The service was unavailable for **13 seconds** and then served 1,400 more
requests while dropping about ten of them. Folding those together produces a
three-minute outage that never happened; a runbook quoting it would be wrong by
an order of magnitude, and the tail check that failed was failing for a reason
that had nothing to do with the kill.

Both were fixed as **quantities, not thresholds** — the M4-S4 lesson (gotcha #63)
in a new place:

- The outage is now anchored on the first *failure* after the kill and closed by
  the first *success* after that, with `fully_unavailable_seconds` and the
  residual rate reported separately and the pre-kill segment as their control.
  (Anchoring on "the first success after the kill" was tried and is also wrong: a
  pod takes a moment to stop answering, so it finds a success 50 ms in and reports
  a 0.05-second outage for a service about to be down for fourteen seconds.)
- The rate selection gained a third clause with a mechanism behind it rather than
  a number reverse-engineered from a result: the phase after the ramp deliberately
  destroys the pod, and a rate that already spends the whole quota leaves no
  headroom for the replacement to come back into.

The two attempts then **corroborate each other on the thing that matters**:
attempt 1 measured 13 fully-dead seconds at 8 req/s and attempt 2 measured 14 at
4 req/s. Self-heal takes about fourteen seconds regardless of the load, and the
long tail in attempt 1 belonged to the saturation. That agreement is worth more
than either run alone, which is the argument for keeping the failed one.

## 6. What is pinned, so this cannot quietly stop being true

`tests/unit/test_load.py`, 33 checks, cluster-free. The load-bearing ones:

- **the arrival schedule is open-loop, checked structurally** (`scheduled = index
  / rate`, asserted by parsing the AST). A closed loop passes every behavioural
  test on a fast server and would be invisible until the day the server was slow.
- **`latency_ms` is measured from the scheduled instant**, with a numeric example.
- **percentiles are nearest-rank** and are computed over successful requests only
  — averaging a connection refusal's 3 ms into a p95 makes an outage look fast.
- **the summary cannot print a percentile without the shape.**
- **the drill's kill target is compared by uid**, and comparing a `.name` fails
  the test by name.
- **the prediction is written before the kill in program order**, not just in the
  prose that says so.
- **a drill that disturbed nothing cannot be green** — with one replica, zero
  errors means the load was not in flight across the kill.
- **no error-rate threshold exists in the drill** (that is an SLO, and the SLO
  document is M6's).
- **the outage is not `last_error - first_error`** — pinned by replaying attempt
  1's timeline as a fixture and asserting the naive span is >150 s while the
  measured outage is ~14 s.
- **neither the client nor the drill touches the registry**, and the only
  mutating `kubectl` verb either may use is `delete`, of a `pod`.

Both structural tests were falsified before being trusted: turning the open loop
into a closed one and relaxing the disturbed-nothing check each turn the suite
red, and both restore.

## 7. Commands

| Intent | Command |
|---|---|
| One stated load shape, recorded | `make load LOAD_ARGS="--rate 4 --seconds 60 --concurrency 8"` |
| The whole drill (ramp → headline → kill) | `make load-drill` |
| Phases 0–2 only, ~40 s, no pod is killed | `make load-drill DRILL_ARGS="--ramp 5,10 --ramp-seconds 6 --seconds 10 --skip-selfheal --out /tmp/probe"` |

The probe form is the M4-S4 habit: a cheap run of the same code in front of the
expensive one. It found three defects in this drill before the first real kill.

Records, all tracked (F-029's regime, so an edit to one is a diff review can see):

```
automation/runs/m5-load/
├── preflight.json              who was answering, and with what
├── ramp.json + ramp-Nrps.json  the four steps, with CPU per step
├── headline.json               the quoted shape, plus the capacity block
├── kill-prediction.json        written BEFORE the kill
├── selfheal.json               the timeline, the recovery, the seven checks
├── summary.json                what the M5 gate reads
└── attempt1-at-the-ceiling/    the RED run, unedited (§5)
```
