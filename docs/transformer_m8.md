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

*(filled in by `make transformer-parity`; the table is committed at
`docs/transformer_parity_table.md`)*

## 5. p95 at the new boundary

*(filled in by `make transformer-load`)*

## 6. Teardown

*(filled in at story exit)*
