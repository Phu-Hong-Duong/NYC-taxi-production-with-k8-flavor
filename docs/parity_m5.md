# M5-S3 — THE parity test: what the endpoint computes, measured

**Story:** M5-S3 (role:MLE) · **Date:** 2026-08-19 · **Executor:** Claude Opus 5

**The one-line result: `max |offline − online| = 0.000e+00 minutes over 16 hazard
rows`, bar 1e-6.** Not "within tolerance" — *identical*, to every bit float64 can
hold, on every row including the ones with no geometry at all.

**And the story found a defect worth more than the number: for one milestone the
deployed system answered HTTP 422 to every request whose zone had no centroid.**
That is F-030, below.

---

## 0. Why this test is the most load-bearing serving fact

Everything this program has published about model quality — KPI-09 3.2403 min,
KPI-10 80.552%, the +2.71% the gate promoted on, every KPI-13 in the mart, every
card on every board — was measured by a booster loaded into a *host* Python
process. What a rider would actually be quoted comes out of a *container*: a
different base image, Python 3.10.12 against training's 3.12.14, pandas 2.2.3
against 3.0.5, numpy 2.2.6 against 2.5.2, reached over an HTTP hop that
serialises every feature to text and parses it back.

Between those two there was no measurement. M5-S2 proved an InferenceService is
`Ready` and answers **one** row, and said out loud in its own handoff that a spot
check must never stand in for this. Train/serve skew is the classic failure of
this seam precisely because both halves keep working while they disagree: the
endpoint returns a plausible number of minutes either way, and nothing goes red.

## 1. What is measured, and what is not

**ONE matrix is built and scored TWICE.** `taxi_mlops.features` builds the 16×24
matrix; `score.load_champion` + `_as_trained` scores it in this process;
`client.infer_matrix` sends that same object to the endpoint. The delta is
therefore attributable to the model bytes, the serving runtime and the wire —
and not to two feature builds that could have differed.

That is the honest reading and it is narrower than "there is no skew":

- **PROVED:** the deployed model computes what the registered model computes,
  bit for bit, on every hazard row. The published KPI numbers describe the thing
  on the wire.
- **NOT PROVED:** that a *future* feature build in the pod matches this one. M7's
  KServe transformer moves feature building server-side; that seam does not exist
  yet and will need its own measurement. `serving/parity.py`'s docstring says so
  where the next person will read it.

## 2. The rows, and why each is there

Sixteen rows, declared and committed in `HAZARDS`, each carrying the reason it is
in the set. Random sampling was rejected: it gives a number that changes every
run, a red team that cannot plant a cause, and — the real objection — the rows
that break serving are never the average ones.

| hazard | what it exercises |
|---|---|
| `ordinary-midday` / `ordinary-weekend-night` | the common case, both ends of the clock |
| `airport-jfk` / `airport-lga` / `airport-ewr` | the 8.8% of trips carrying 1.9× the error (M2-S4 §4) |
| `no-geometry-both` (264→264) | nine NaN features, `has_geometry=0`; the largest single OD "route" in the data (409,128 trips) |
| `no-geometry-one-sided` (132→265) | half the geometry missing — haversine NaN, borough and airport flags still defined |
| `unseen-od-pair` (55→148) | an OD pair in `trips_test` **6 times** and in `trips_train` **never** |
| `federal-holiday` | `is_holiday=1` — and it is M5-S2's exact spot-check row, kept on purpose |
| `near-holiday` | `is_near_holiday` without `is_holiday`: the flag pair that must not collapse |
| `midnight-boundary` / `week-boundary` | the cyclical encodings' seams (`hour_sin=0`, `hour_cos=1`) |
| `long-haul-boundary` (Bronx→Staten Island) | the 100–120 min band where KPI-12 is 0.103% and the ceiling lives |
| `passenger-count-zero` / `-max` | 0 = "not stated" (bucket 4), and the top of the admitted range |
| `out-of-year-2026` | F-019's extended table in use, outside every month the model ever saw |

The unseen pair is a **committed literal**, found by asking the analyst layer
once:

```sql
WITH tr AS (SELECT DISTINCT PULocationID AS pu, DOLocationID AS dz FROM trips_train),
     te AS (SELECT PULocationID AS pu, DOLocationID AS dz, COUNT(*) AS n
            FROM trips_test GROUP BY 1,2)
SELECT te.pu, te.dz, te.n FROM te LEFT JOIN tr USING (pu, dz)
WHERE tr.pu IS NULL ORDER BY te.n DESC LIMIT 5;
-- 55|148|6   93|52|6   235|23|6   39|201|5   244|23|5
```

Committing the answer keeps parity a seconds-long reader instead of re-scanning
44M rows to re-derive a constant that cannot change.

## 3. F-030 — the missing-geometry path could not be quoted AT ALL

**Found by building the hazard set; fixed the same session; it had been live
since the endpoint existed.**

Zones 264 and 265 are TLC's "Unknown" and "N/A" — not places. They have no
centroid by design (DR-04 condition 1), so `quote_time.build_features` produces
`NaN` for all nine geometry features and sets `has_geometry = 0`, which is
LightGBM's documented missing path and exactly what the champion was fitted on.

`json.dumps` writes a Python `float('nan')` as the bare token `NaN`. **That is
not JSON** — Python emits it by default, and no conforming parser accepts it. The
endpoint's answer, in full:

```
$ make quote QUOTE_ARGS="--at 2019-03-11T00:30:00 --pu 264 --do 264"
RuntimeError: the endpoint answered 422 … {"detail":[{"type":"json_invalid",
  "loc":["body",1241],"msg":"JSON decode error","ctx":{"error":"unexpected character"}}]}
```

A byte offset. Not the feature, not the zone, not the word NaN — a parser
refusing a malformed document, which is the least actionable error a client can
receive. And the affected population is not exotic: ~1.0–1.2% of every split, and
264→264 alone is the single most common OD pair in the data.

**The fix** (`client._wire_values`): missing goes on the wire as JSON `null`,
which mlserver decodes back into the tensor as NaN — the very value the booster
treats as missing. An **infinity is refused** rather than encoded: equally
unrepresentable in JSON, but not a missing value, so mapping it to `null` would
launder a broken feature into a plausible quote. And `_post` now passes
`allow_nan=False`, so the *next* path that forgets becomes a loud `ValueError`
here instead of a 422 about byte 1241 there.

That `null` really is the same missing value is not argued, it is measured: the
`no-geometry-both` row parities at **0.000e+00** against the locally-loaded model
scoring an actual NaN.

```
no-geometry-both           9.655548885     9.655548885     0.000e+00
no-geometry-one-sided     35.124482043    35.124482043     0.000e+00
```

**Why nothing caught this earlier.** Every client before M5-S2 was offline and
passed a DataFrame straight to LightGBM, where NaN is ordinary. M5-S2's accept
check was one row — an ordinary JFK trip with full geometry. The defect needed a
request from the 1% and there had never been one.

## 4. The red team, and the arm that went green

`make parity-redteam` plants a cause and asserts the test names it. What is
different here from every earlier red team is what it must *not* do: the obvious
lever — point the endpoint at another model — would mean a deploy and a pointer
move, i.e. breaking production to prove a test works. Both arms plant the cause
inside the TEST. Nothing is redeployed, no pod restarts, the alias is read and
never written, and the drill re-runs the real test at the end to prove it left
nothing behind.

**Arm A — every feature under its own name, carrying its neighbour's values.**
Names right, dtypes right, shapes right, every value in range; only the pairing
is wrong. Measured skew:

```
airport-jfk               59.558275075    27.359989704     3.220e+01
long-haul-boundary        48.180011330     6.076692624     4.210e+01
[parity] max |offline - online| = 4.210e+01 minutes … the bar is 1.0e-06
[parity] FAIL: the deployed model does not compute what the registered one computes.
```

A 48-minute trip quoted at 6 minutes, from a request in which every single input
is individually valid. That is the failure mode with no other symptom, and it is
why this test exists.

**The first draft of arm A did not work, and that is the finding.** It rotated
the *order* of the inputs in the V2 body — on the reasoning, written into
`client.v2_payload`'s docstring since M5-S2, that a V2 payload is positional and
a reordering silently swaps `PULocationID` for `DOLocationID`. The measured
delta was **0.000e+00 on all 16 rows**. The drill went green under its own
tampering.

**This runtime pairs inputs by NAME.** mlserver hands MLflow a *named* frame and
the logged signature selects and reorders it. So the wire order is not
load-bearing on this deployment, and the docstring's property 2 was false. It has
been **corrected rather than deleted**: sending the model's own order stays
right, because a positional V2 runtime is legal and M7's transformer may be one,
and it costs nothing. What is no longer claimed is that the ordering is the thing
standing between us and a mispaired feature. **The logged signature is** — for
the second time in this milestone, after it refused the lossy `float64 → int32`
cast at M5-S2.

A red team that passes on the first try tells you the test is red-able. This one
told us a documented property of the system was wrong.

**Arm B — the offline side loads registry version 1 while the wire serves the
champion.** Addressing an explicit version is a *read*; moving an alias would be
a mutation, and a red team never mutates the pointer it is checking (hence
`load_champion(..., version_number=…)`, one branch at the resolution step so the
drill exercises the real loader — which M5-S5's typed rollback will want at
exactly this precision).

Arm B refuses **before** producing a number:

```
RuntimeError: the loaded model eats ['hour','dayofweek','PULocationID','DOLocationID',
'passenger_count'] but the config describes [… 24 …]. Parity would compare two
different feature sets.
```

That is the honest outcome and worth stating plainly: version 1 is the v1 feature
set (5 columns) and version 2 is v2 (24), so a "delta" between them could only be
produced by a test willing to compare two models on two different matrices. The
guard declines to manufacture a number a reader would believe. The version-
mismatch verdict (`the endpoint is serving version X while the alias resolves to
Y`) is the second net, and it is what would fire if a future version-1-vs-2 pair
*did* share a feature set — a delta of 0.000e+00 across two different models
must never read as PASS.

## 5. Acceptance transcripts

### 5.1 `make parity` — GREEN

```
[parity] offline: models:/nyc-taxi-eta@champion -> version 2 (run 92b73bd4f77d4a05b92472bfcfb3cccf, 791 trees)
[parity] one matrix: 16 rows x 24 features, built once
[parity] online : http://localhost:8081/v2/models/nyc-taxi-eta/infer (Host: nyc-taxi-eta-serving.local) answered as nyc-taxi-eta version 2

hazard                   offline (min)    online (min)       |delta|
----------------------  --------------  --------------  ------------
ordinary-midday           10.665224429    10.665224429     0.000e+00
ordinary-weekend-night     4.662505785     4.662505785     0.000e+00
airport-jfk               59.558275075    59.558275075     0.000e+00
airport-lga               44.611286067    44.611286067     0.000e+00
airport-ewr               40.201289421    40.201289421     0.000e+00
no-geometry-both           9.655548885     9.655548885     0.000e+00
no-geometry-one-sided     35.124482043    35.124482043     0.000e+00
unseen-od-pair            41.463649154    41.463649154     0.000e+00
federal-holiday           39.001937154    39.001937154     0.000e+00
near-holiday               6.077414150     6.077414150     0.000e+00
midnight-boundary          4.771408855     4.771408855     0.000e+00
week-boundary              4.247801081     4.247801081     0.000e+00
long-haul-boundary        48.180011330    48.180011330     0.000e+00
passenger-count-zero       5.921518128     5.921518128     0.000e+00
passenger-count-max        6.104270692     6.104270692     0.000e+00
out-of-year-2026           7.375984575     7.375984575     0.000e+00

[parity] max |offline - online| = 0.000e+00 minutes over 16 hazard rows (every row agrees EXACTLY); the bar is 1.0e-06
[parity] PASS: train/serve skew is MEASURED, not assumed — the deployed champion (version 2) reproduces the registered one on every hazard row, including the ones with no geometry at all.
[parity] record -> automation/runs/m5-parity/parity.json
```

**`federal-holiday` = 39.001937154**, which is M5-S2's `39.0019` at full
precision. The one number that already existed is reproduced by the many.

### 5.2 `make parity-redteam` — PASSED (7 checks, 0 failures)

```
[redteam] @champion resolves to version 2 before the drill
=== ARM A — every feature carries its neighbour value (the served model is untouched)
ok    arm A: parity exited 1 (non-zero) with the columns rotated
ok    arm A: the verdict names the disagreement rather than only exiting non-zero
ok    arm A: measured max |delta| = 4.210e+01 minutes, far above the 1e-6 bar
=== ARM B — the offline side loads version 1 while the wire still serves the champion
ok    arm B: parity exited 1 (non-zero) against version 1
ok    arm B: the refusal names the cause (a different model, not a wider delta)
=== AFTER — nothing was mutated, and the real test is green again
ok    @champion still resolves to version 2 (unmoved across the drill)
ok    the untampered parity run is GREEN again (exit 0), so the drill left nothing behind
[redteam] 7 check(s), 0 failure(s)
[redteam] PASSED — `make parity` goes RED for a planted cause and GREEN without one.
```

## 6. Why 0.000e+00 and not the ~1e-7 the kickoff expected

The kickoff predicted float noise from a float32 → float64 → float32 round trip.
There is none, and the reason is in the M5-S2 fix that removed it: **the wire
carries the matrix's own dtypes**. A `float32` feature goes out as `FP32` and
arrives as `float32`; an `int16` as `INT16`. LightGBM then converts to `float64`
internally on *both* sides from *identical* float32 bits, so the trees traverse
identical thresholds and sum identical leaf values.

The prediction path also crosses none of the three version differences that
worried M5-S2: pandas and numpy carry the values, they do not compute them, and
**lightgbm is 4.7.0 on both sides**. That paragraph in M5-S2's handoff named
itself "the first suspect if S3's parity comes back wide". It came back at zero;
the suspect is cleared, and the derived predictor image stands.

**Zero is a stronger result than 1e-7 and it is also a more brittle one to
maintain.** Anything that reintroduces a dtype round trip — a transformer, a
different runtime, a payload that widens `FP32` to `FP64` for convenience —
moves this number off zero. The bar stays 1e-6 because that is the honest
tolerance for a *seam*, not because zero is expected forever; but a run that
comes back at 1e-7 is a change worth a sentence in a handoff, not a shrug.

## 7. What this story did NOT do

- **It did not measure latency.** M5-S4 owns p95/p99 under stated load. Parity
  sends 16 rows in one request and times nothing.
- **It did not touch the registry or the deployment.** `@champion` is version 2
  before and after both commands, read by the drill itself. No pod restarted, no
  helm release moved, no alias written. Pinned by AST tests, not by grep.
- **It did not test the transformer seam**, which does not exist until M7 (§1).
- **It did not re-fit anything.** Parity loads a registered model and POSTs; the
  whole run is seconds.
