# The boundary moves — a transformer beside the champion, and the bar its answers are held to

**M8-S4 leg 3.** Leg 1 put the online store on the cluster and measured its
projection at `0.000e+00`. Leg 2 put a quarantined Feast feature server in front
of it and measured the HTTP door at `0.000e+00`. This leg puts the *request path*
behind that door: a rider's four fields go to a pod, the pod derives the
champion's 24 features through `taxi_mlops.features`, and the stored lookups come
out of the feature store instead of the committed CSVs.

## 1. What actually moved, and what deliberately did not

Since M5-S2 every client of this program has built the matrix itself. `make
quote`, `make parity`, `make load`, the M5 gate, M6's canary and gameday drills —
all of them POST twenty-four named, typed features. That is a working system with
an honest weakness, and `load.py`'s own docstring has carried it since M5-S4:

> The feature matrix is built ONCE, before the clock starts […] They do NOT
> include `quote_time.build_features`, which in M5 runs in the caller's process
> […] and which M7 moves into a KServe transformer — at which point it lands
> INSIDE this measurement and the number will move.

This is that milestone arriving. The transformer accepts `at`, `pu`, `do`,
`passenger_count` and nothing else, which is what a dispatch system knows at the
moment a rider asks.

**What did not move: the champion's own wire.** `nyc-taxi-eta` is untouched for
the whole story — same InferenceService, same pod, same 24-column contract — and
`make verify-m5` green at exit is the proof rather than the claim. The transformer
is a SECOND InferenceService with its own KServe-generated host and its own
predictor, which is the M6-S3 shadow precedent: it can be deleted and take
exactly its own objects with it. Putting a transformer on the champion's own isvc
would have changed what every existing client sends, and F-040 already measured
which direction of schema change hurts (27.93 s of `HTTP 500` at the logged
signature, because removing features breaks requests in flight).

**What did not move either: `uv.lock`.** The transformer is
`http.server.ThreadingHTTPServer`, `urllib` and `json` — stdlib. A web framework
for one POST route at 4 req/s would put three packages into a numeric stack
gotcha #36 is this repo's record of not taking chances with.

## 2. Which reference data crosses the wall — F-059, landed as code

Leg 2 ended with a finding rather than a defect: **a feature store is a good home
for a per-entity measurement and a bad home for anything a program computes**, and
the three are indistinguishable in a schema. `taxi_mlops.features.lookups` is
where that now lives, as a type:

| reference group | source at request time | why |
|---|---|---|
| zone centroids (lat/lon) | **the feature store** | a per-entity measurement: zone 132's latitude is a property of zone 132 |
| calendar `is_holiday` / `is_near_holiday` | **the feature store** | per-date facts |
| `is_business_day` | committed code | it is `weekday & not-holiday`; the store has it, and taking it would give the program two definitions of a business day for no gain |
| borough dictionary | **committed table** | the CODE is assigned by first-appearance order over the whole lookup CSV, so it is a property of the table's iteration order and not of the zone. Fetching two zones and numbering what came back is a silent, total category re-map with every value individually correct |
| `is_airport` | **committed code** | three integers, total over every id including TLC's non-places 264/265, which the store has no row for. Sourcing a total function from a partial store turns "not an airport" into "no answer" for exactly the ~1% of rows that already carry no geometry (F-030's class) |

The refusal is structural, not documented: `Lookups` has only two fields, the
borough and airport branches of the dispatch call `zones` directly, and
`tests/unit/test_lookups_seam.py` asks the **AST** whether they still do. Not the
behaviour — a store whose values happen to agree would make a behavioural test
pass for a design that is wrong, and the failure it would hide is invisible in
every individual value.

`Lookups.sources` reports all four groups, including the two that did not cross,
and the transformer returns it as the `X-Taxi-Lookups` response header. That is
what makes "the store was consulted" checkable from outside the pod: **a
transformer that silently fell back to its committed CSVs would serve perfectly
correct quotes and prove nothing at all about the store** — ADR-012's own named
failure mode for the materializer, one layer along.

## 3. THE BAR, ARGUED BEFORE THE COMPARISON RAN

*(This section and `scripts/transformer_parity.py` are committed BEFORE any
comparison record exists — M8 law 4's ordering, checkable from git rather than
asserted here. Every M8 seam has re-argued its own bar rather than inheriting the
previous one, because a sentence written about a parquet read is not an argument
about an HTTP request path.)*

**The bar is EXACT — zero difference, on every one of the 16 declared hazards.**

The M8 kickoff says a *wider* bar than M5-S3's 1e-6 needs a dtype argument rather
than a shrug. A **tighter** one needs an argument too, and this is it. There are
exactly three differences between the two paths, and none of them can move a bit:

1. **Where two reference tables came from.** The centroids and the calendar flags
   arrive over HTTP instead of off a CSV. Leg 2 measured that projection exact
   over 108 comparisons, and — the stronger fact — `make transformer-probe`
   re-measured the *whole matrix* on the host before this bar was written:
   store-backed and committed-table builds of all 16 hazards, `.equals()` True,
   24 columns each. So this is not a hope about float64 round-tripping through
   JSON; it is a measured precondition of the bar.
2. **A second mlserver process.** Same image
   (`taxi-mlops-predictor:mlserver-1.7.1-lgb-4.7.0`), same champion bytes resolved
   from the same alias by the same F-009 two hops, same runtime. LightGBM
   inference is a per-row traversal of a fixed forest summed in tree order — it
   does not depend on thread count, batch size or process identity. M5-S3 already
   measured `0.000e+00` across a *bigger* gap than this one (Python 3.10 vs 3.12,
   pandas 2.2.3 vs 3.0.5).
3. **One extra JSON hop**, transformer to predictor, in-cluster. It uses the SAME
   `client.v2_payload` the host uses, so the wire carries the matrix's own dtypes
   (int16, float32) exactly as it does today; and JSON's number grammar carries a
   float64 losslessly because every encoder here emits Python's
   shortest-round-trip `repr`.

The features are cast to float32/int16 *before* either path serialises, so the
one place a rounding could hide — a float64 → float32 → float64 round trip — is
common to both and happens at the same line of the same function.

**A nonzero result is therefore a FINDING, not a bar to widen**, and it would be a
finding with an address: the probe already isolates the matrix, so a delta here
with an identical matrix there would name the predictor or the wire, and a delta
in both would name the seam.

**The bar's companion is `X-Taxi-Lookups`.** A parity of `0.000e+00` measured
against a transformer that never called the store is a measurement of nothing.
The reader asserts the header on the same response it reads the number from.

## 4. The result

```
[transformer-parity] 16 declared hazards (parity.HAZARDS, imported)
[transformer-parity] A  matrix built HERE  -> http://localhost:8081/v2/models/nyc-taxi-eta/infer
[transformer-parity] B  raw request        -> http://localhost:8081/v2/models/nyc-taxi-eta-transformer/infer
[transformer-parity] bar: EXACT (docs/transformer_m8.md §3, argued before this ran)

[transformer-parity] ok  ordinary-midday         champion=10.665224  transformer=10.665224  |d|=0.000e+00
[transformer-parity] ok  airport-jfk             champion=59.558275  transformer=59.558275  |d|=0.000e+00
[transformer-parity] ok  no-geometry-both        champion= 9.655549  transformer= 9.655549  |d|=0.000e+00
[transformer-parity] ok  unseen-od-pair          champion=41.463649  transformer=41.463649  |d|=0.000e+00
[transformer-parity] ok  federal-holiday         champion=39.001937  transformer=39.001937  |d|=0.000e+00
[transformer-parity] ok  long-haul-boundary      champion=48.180011  transformer=48.180011  |d|=0.000e+00
[transformer-parity] ok  out-of-year-2026        champion= 7.375985  transformer= 7.375985  |d|=0.000e+00
                                                        … 16 of 16, all 0.000e+00 …

[transformer-parity] ok  max |champion - transformer| = 0.000e+00 minutes across 16 declared hazards, bar EXACT
[transformer-parity] ok  both boundaries served the SAME registry version: champion='2', transformer='2'
[transformer-parity] ok  the pod really consulted the store: X-Taxi-Lookups='airport_constant=committed-code,
                         borough_dictionary=committed-table,calendar=feature-store,centroids=feature-store'
[transformer-parity] ok  and F-059's two refused groups did not cross
[transformer-parity] GREEN — the boundary moved and the number did not.
```

The whole table is committed at `docs/transformer_parity_table.md`; the record is
`automation/runs/m8-transformer/transformer-parity.json`.

**Read the rows, not just the total.** `no-geometry-both` is the F-030 class —
zones 264/265, which the store has no row for and the committed table holds NaN
for; both sides produced NaN through the same named fallback and the booster
answered 9.655549 twice. `federal-holiday` is the row every record in this repo
already carries at 39.001937, now produced by a pod from four raw fields.
`out-of-year-2026` is a date beyond the training window and inside the store's
calendar, which is what makes the horizon refusal at 2031 a boundary rather than
a wall.

**What the third check buys.** A parity of `0.000e+00` measured against a
transformer that never called the store is a measurement of nothing, and it would
look exactly like this one. `X-Taxi-Lookups` is read off the same response the
number came from.

## 5. p95 at the new boundary

M5-S4's shape exactly — 4 req/s for 60 s at concurrency 8, hazard mix, open loop —
because the only useful thing to do with this number is put it beside the
champion's, and two percentiles measured at different shapes are not comparable.
Both arms run back to back in one invocation, so the champion's arm is a CONTROL
measured on the same laptop in the same minutes rather than a figure quoted from
a record made four days and one host reboot ago.

**Run 2 (2026-08-23T12:08Z, against the deployed image `taxi-mlops-pipeline:2cdcb36`):**

| latency_ms (scheduled → response) | champion | transformer | delta |
|---|---:|---:|---:|
| p50 | 31.1 | 49.3 | **+18.1** |
| p95 | 113.1 | 118.1 | **+5.0** |
| p99 | 117.0 | 160.4 | +43.5 |
| max | 119.0 | 249.6 | +130.6 |

240/240 requests on each arm, **zero errors on both**, achieved 4.01 req/s on
both, `model_version` `['2']` on both — read off the timed responses.

**What is inside the transformer's number that is not inside the champion's:**
decoding four raw inputs, **two HTTP calls to the quarantined feature server**,
`build_features` over 24 columns, the V2 encode, and a second in-cluster hop to
the predictor. So a larger number is the expected reading and is not a
regression — it is a boundary that moved, exactly as `load.py`'s docstring said
it would in M5-S4.

### The honest reading, which is narrower than the table

**Quote the p50 delta; do not quote the p95 delta as a figure.** Two runs eight
minutes apart, same shape, same code, same pods:

| | run 1 (12:00Z) | run 2 (12:08Z) |
|---|---:|---:|
| p50 delta | +16.8 ms | +18.1 ms |
| p95 delta | **+23.0 ms** | **+5.0 ms** |
| p99 delta | −104.9 ms | +43.5 ms |

The p50 move is stable to about a millisecond across both. The p95 and p99 deltas
are not: run 1's champion arm carried a p99 of 345 ms and a max of 545 ms, run
2's carried 117 and 119. That tail is host contention on a laptop — the same
effect M6-S2 refused to claim credit for when the CPU-request change appeared to
improve p99 by 73%. Both records are tracked
(`transformer-load.json` and `transformer-load-run1.json`) so this is checkable
rather than asserted; **the reportable cost of the moved boundary is ~18 ms at
p50**, and the p95 is "within the same band, and the band is wider than the
effect".

### A prediction that was pessimistic, and why

M5-S4 priced the feature build at **~30 ms cold for one row** and warned the M7
delta would land inside this measurement. The measured p50 move is **~18 ms** —
and it buys *more* than the feature build, because it also includes two
round-trips to another pod and a second HTTP hop. The gap is the word **cold**:
that 30 ms was a first call, paying module import and the `lru_cache` fill on
`load_zone_table` / `load_calendar`. A warm pod pays neither, and the store path
does not read those CSVs at all. Gotcha #80's family — an analogy from a
differently-conditioned measurement, and this time it erred in the safe
direction.

## 6. Teardown, and why the service is still up

**Teardown proven**, the M6-S3 shadow precedent: `TEARDOWN=1 make
deploy-transformer` deleted `InferenceService/nyc-taxi-eta-transformer` and KServe
took its two Deployments, its two Services and its Ingress with it. What was left
in `serving` was the champion's Deployment, Service and Ingress at **4d6h** — and
the stronger check, its predictor POD at the same uid
`9b1f1b03-7dfe-458f-a8b0-cd045c61b18c`, still answering 39.0019 minutes. That is
the evidence that nothing in this story ever touched the champion's own wire; a
list of surviving object names would not have distinguished "untouched" from
"recreated".

It was then **re-deployed and deliberately left up**, for the reason M6-S3 left
the v1 shadow running: M8-S5's gate is the next story, it will want to ask a live
system the same kind of question `verify-m5` §2 asks, and standing it back up
costs a `make deploy-transformer`.

> **CLOSED 2026-08-23 (M9-S2).** The paragraph below is left unedited because it
> is what the next story was handed, and one of its predictions was wrong in an
> instructive way. The signal is **A-12** (SLO-S1) and **A-13** (SLO-S2), argued
> in `docs/slo_serving.md` §9 and watched firing in `docs/store_watchdog_m9.md`.
> **The prediction that did not hold:** "the transformer would quote confidently
> from nine NaN geometry features". Measured, with the store emptied for real,
> the transformer answers **HTTP 422** — because every request also carries a
> DATE, and `calendar_from_store` refuses an unanswered one (F-019 on the store's
> wire). The geometry analysis below is exactly right and it is not the half that
> decides: the calendar refuses first, on every request, and that is why an
> emptied store is a refusal rather than a wrong number. What the store watchdog
> adds is the part no client can do — noticing at all.

**What is NOT closed, and it now has a third consumer.** There is still no alert
on an empty or stale online store. Leg 1 named it, leg 2 repeated it, and this leg
is the one that puts *rider-shaped traffic* behind it: if Redis were emptied, the
feature server would answer `null` for every zone, `zone_table_from_store` would
return an all-NaN table, and the transformer would quote confidently from
nine NaN geometry features — the F-030 class, arriving through the store instead
of through the request. The transformer refuses an unreachable store (503) and a
date the store cannot answer (422), but it does not and cannot refuse a store that
answers `null` for a zone that legitimately has no row. That distinction belongs to
a rule watching the store, not to a client.
