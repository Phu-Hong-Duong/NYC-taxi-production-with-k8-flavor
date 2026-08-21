# The online store and the 100-pair parity (M8-S4, leg 1)

**Role block: MLE (A), SRE (R).** Refusals in play: nothing is fitted for a
model · no alias is read or moved · the champion's own wire is untouched · a
mismatch is a finding, never a widened bar.

> **§1 and §2 of this document were committed BEFORE the comparison ran.** The
> declared pair set (`infra/feast/online_pairs.csv`) and the bar below are fixed
> in commit `HEAD~` of this story's branch, ahead of the first line of
> `automation/runs/m8-online/online_parity.json` — M8 law 4's ordering made
> checkable from git rather than asserted in prose, which is the M7-S3 headroom
> precedent and the M8-S3 one. §3 onward were written from the numbers.

## §0 What this leg claims, and what it does not

It claims: **the online store is a lossless projection of the offline store at
one instant**, measured over 100 declared (entity, timestamp) pairs and 14
columns, against a bar of EXACT.

It does **not** claim that a request-path caller gets the champion's features
from the store — nothing reads it on the request path yet. That is leg 2 (the
transformer), and the kickoff names this exact cut as the safe stopping point:
*"store + 100-pair parity landed, transformer undone — the blueprint's accept
artifact already exists"*.

## §1 What materialization actually does, and why it decides the comparison

`feast materialize START END` writes, for every entity key, the **latest** source
row whose `event_timestamp` falls in the window. The online store holds one value
per key and **no history**: it is structurally incapable of the point-in-time
join M8-S3 measured.

* For the two **static** views (`zone_static`, `calendar_day_flags`) that is a
  distinction without a difference — one row per key, ever.
* For the two **time-varying** views it means the store serves the **full
  window** (the `2019-07-01` stamp) to every request. That is precisely the
  *naive* column `docs/feast_pit_m8.md` §4 defines, and M8-S3 measured it equal
  to our own full-window `aggregates.fit` table with **0 mismatches over 88
  rows**.

So the offline half of this table is retrieved **at an instant after the last
window closed**, not at each row's own timestamp. Comparing an online answer
against a per-row point-in-time answer would report the store working correctly
as a mismatch — gotcha #50, and it would have been the easy mistake to make.

**The consequence is worth stating plainly, because it is the honest limit of
every online feature store and not a defect of this one: an online store cannot
serve a point-in-time feature.** M8-S3's proof is what a training set is entitled
to; this table is what a request gets. They are the same numbers only for
features that do not vary in time — which, in this champion, is all nine geometry
features and all three calendar flags, i.e. **every stored feature the champion
actually eats**. The two time-varying views are `catalog-only`
(`docs/feast_catalog.md`): they lost the M3 ablation, and nothing serves them.

## §2 The bar: EXACT, and the dtype argument it needs

M8-S3's bar was `TOLERANCE = 0.0` and its argument was one sentence: *nothing on
the store's side of the wall performs arithmetic*, so every crossing is a copy, a
lossless `float32 -> float64` widening, or parquet's typed encoding.

**That argument does not transfer for free**, and HANDOFF (bz) said so: an online
store adds a serialization format and a network hop the offline path did not
have. So it is re-made here for the new path, before the number was seen:

1. **Redis stores bytes, and Feast decides them.** A materialized value is a
   `feast.protos.types.Value` protobuf serialized into a Redis hash field. A
   `Float64` field becomes a protobuf `double` — 64-bit IEEE 754, the same
   representation `float64` already is. Protobuf `double` is fixed-width and
   round-trips bit for bit; there is no text form and no decimal formatting
   anywhere on the path, which is where float error usually enters.
2. **`Bool` and `String` have no numeric path at all** — `bool_val` and
   `string_val` are exact by construction.
3. **The network hop moves bytes, not numbers.** Redis is a byte store; the
   client is `redis-py` with `hiredis` parsing bulk strings. Nothing in the hop
   parses a float.
4. **The pinned serialization version is what keeps (1) true across upgrades.**
   `entity_key_serialization_version: 3` in `feature_store.yaml` fixes how entity
   keys are encoded, so a Feast upgrade inside the quarantine cannot silently
   change which key a value lands under.
5. **The one place arithmetic could enter is materialization itself**, and it
   does not: `materialize` selects rows, it does not aggregate them. Every number
   in the store was computed by `taxi_mlops.features.aggregates` on this side of
   the wall, months of code before Feast saw it.

So the bar is **EXACT — `TOLERANCE = 0.0`** again, and it is a real bar rather
than a hedge: a nonzero result here would be a finding to investigate (which side
rounded?), never a number to widen a bar to. It lives as a module constant in
`scripts/feast_online_parity.py` so the gate and the tests read the number the
script applied rather than the one the prose argues (F-017).

**What the bar is measured over, and the count that carries it.** `NaN != NaN`,
so both-missing counts as agreement and **one-missing counts as a MISMATCH**.
That asymmetry is the load-bearing half: ~1% of real traffic has no geometry at
all (zones 264/265 are not places — DR-04 condition 1), and a comparison that
dropped nulls would print a perfect zero while being blind to exactly those rows.
The comparator is **imported from M8-S3's script, not re-implemented**, so the
two seams cannot drift apart in how they define agreement.

## §3 The declared pairs

`infra/feast/online_pairs.csv`, 100 rows, each naming its hazard. The first 88
are **imported from `infra/feast/retrieval_rows.csv`** — M8-S3's committed set,
read rather than retyped, so the offline seam and the online seam are measured
against ONE population and a disagreement between the two tables is a fact about
the stores. A unit test compares the two files field by field.

The 12 added rows are hazards the online seam has and the offline one does not:

| id | hazard | why it is here |
|---|---|---|
| 88 | `unknown-zone-pair` 264 -> 265 | TLC's two non-places; both stores must decline both halves |
| 89 | `zone-out-of-range` 999 | a key that cannot exist must return null, not raise |
| 90, 91 | `duplicate-entity-key`, exact twins | `get_historical_features` answers such a pair ONCE (F-056 cause 1); `get_online_features` answers per requested row |
| 92 | `max-window-drift-od` | the row where a wrong-stamp materialization shows up by the largest margin |
| 93, 94 | `hour-0`, `hour-23` | both ends of the clock entity |
| 95 | `calendar-horizon-2030` | the far end of F-019's committed holiday table |
| 96 | `calendar-dst-spring-forward` | 2019-03-10, the day US clocks skip an hour |
| 97 | `calendar-leap-day` | 2020-02-29 |
| 98 | `airport-to-airport` 132 -> 138 | a thin cell in the segment whose error gap held across a regime change |
| 99 | `same-zone-round-trip` 237 -> 237 | two composite join keys carrying the same value |

**Row 92's first design was refused by the data, and the refusal is the more
interesting fact.** The intent was a key whose newest source row predates the
full window, so that a materialize filtering on the window's END would leave it
null. No such key exists: the point-in-time windows are **cumulative** (window
*k* is fitted over months 1..*k*), so the full window's key set is a superset of
every earlier one's. That is structural, not luck, so the row was replaced rather
than approximated — it is now the OD pair whose median duration moves most across
its windows (**169 -> 191, 80.15 minutes of drift**), which does the same job
strictly better: if materialization served any stamp but the newest, that is the
row where the error is largest.

## §4 The result

**`max |online − offline| = 0.000e+00` across 16 columns and 100 declared pairs,
against a bar of EXACT — and `one missing` is ZERO on every one of them.**

| column | kind | compared | mismatches | max abs delta | both missing | one missing |
|---|---|---:|---:|---:|---:|---:|
| `pu_zone.centroid_lat` | float | 100 | 0 | 0.000e+00 | 13 | 0 |
| `pu_zone.centroid_lon` | float | 100 | 0 | 0.000e+00 | 13 | 0 |
| `pu_zone.borough` | string | 100 | 0 | — | 13 | 0 |
| `pu_zone.is_airport` | bool | 100 | 0 | — | 13 | 0 |
| `do_zone.centroid_lat` | float | 100 | 0 | 0.000e+00 | 19 | 0 |
| `do_zone.centroid_lon` | float | 100 | 0 | 0.000e+00 | 19 | 0 |
| `do_zone.borough` | string | 100 | 0 | — | 19 | 0 |
| `do_zone.is_airport` | bool | 100 | 0 | — | 19 | 0 |
| `calendar.is_holiday` | bool | 100 | 0 | — | 0 | 0 |
| `calendar.is_near_holiday` | bool | 100 | 0 | — | 0 | 0 |
| `calendar.is_business_day` | bool | 100 | 0 | — | 0 | 0 |
| `od_window.od_median_duration_min` | float | 100 | 0 | 0.000e+00 | 3 | 0 |
| `od_window.window_months` | string | 100 | 0 | — | 3 | 0 |
| `pu_hour_window.pu_hour_mean_speed_kmh` | float | 100 | 0 | 0.000e+00 | 13 | 0 |
| `pu_hour_window.pu_hour_trips_per_day` | float | 100 | 0 | 0.000e+00 | 1 | 0 |
| `pu_hour_window.window_months` | string | 100 | 0 | — | 1 | 0 |

**Zero is the honest expectation here rather than a pleasant surprise**, which is
what §2 exists to have said in advance. The one number that is not a
restatement of the bar is `one missing = 0` on every column: the store and the
feature path agree about *which rows have no value at all*, and that is the
column where a plausible defect would actually live.

**The two-sided no-geometry assertion held.** Our path reports no geometry on 13
pickup rows and 19 dropoff rows; the store declined exactly those, **0
disagreements** — zones `264, 265, 999` on the pickup side and `264, 265` on the
dropoff side. The store is never asked to produce a row for a non-place; it is
asked to be silent about the same ones we are.

**One internal consistency worth reading slowly**: `pu_hour_mean_speed_kmh` is
missing on 13 rows while `pu_hour_trips_per_day` is missing on 1, out of the same
view and the same keys. That is correct — the speed is derived from centroid
distance, so it is unavailable exactly where geometry is, while trips-per-day
needs no geometry at all. A store that answered both or neither would be the
suspicious reading.

### §4.1 The table can go RED — `make feast-online-parity-redteam`, PASSED

A table of zeros is not evidence until something has been watched making it
non-zero, and the sceptical reading of §4 is *two reads of one store will always
agree*. The drill copies one OD pair's **real serialized bytes** onto another
pair's Redis key: every byte was written by Feast, the protobuf parses, the dtype
is right, the value is a real median from a real pair, and nothing logs anything.
That is what a wrong-row or wrong-stamp materialization looks like from outside,
and it is the one failure the offline store cannot detect for itself.

It plants on **row 92** — the pair the declared set named *in advance* as the one
where a wrong value shows up by the largest margin — and the donor is derived,
not chosen after the fact. Observed: target `169 -> 191`, donor `14 -> 259`,

* **RED, exit 1, `max |online − offline| = 8.727e+01`**, naming
  `od_window.od_median_duration_min` — 87 minutes of skew from one hash field;
* **26 other sub-check lines still passed** — a gate that fails on any edit is a
  checksum, not a gate (the `verify-m3` red team's rule);
* the restore is **byte-identical by sha256 over the hash**
  (`bd91004815981b5c…` before the plant and after the restore);
* the re-run is **GREEN** again and `git status` is clean.

Both parity runs inside the drill use `--no-write`, so the committed accept
artifact can never be overwritten with a tampered verdict — a unit test pins
that, because a drill that rewrote the table it is testing would be planting
evidence rather than looking for it.

## §5 The anchor: this is not two Feast reads agreeing with each other

A table where the store agrees with the store would pass for any materialization
that copied consistently, including one that copied the wrong stamp consistently.
Two things stop that reading:

1. **The static columns are additionally compared against the ONE
   `taxi_mlops.features` path** — `zones.load_zone_table()` and
   `calendar.build_calendar_features()`, the same functions the champion's own
   24-column matrix is built from. Those seven columns are what the champion
   actually eats, and the store agrees with the model's own lookup and not merely
   with another Feast read.
2. **The time-varying columns are anchored by an INHERITED measurement, cited and
   not re-run**: M8-S3 measured the naive (full-window) retrieval equal to our
   own `aggregates.fit` table with 0 mismatches over 88 rows
   (`automation/runs/m8-pit/pit_proof.json`). Re-fitting 43,987,422 rows to
   restate that would cost three minutes to learn nothing new. It is named as
   inherited evidence rather than folded silently into this story's numbers.

## §6 What F-056 does to this table, and what it does not

M8-S3 found that `get_historical_features` returns **fewer** rows than it was
asked for, for two reasons a left join cannot tell apart (a duplicate
`(entity keys, timestamp)`, and no source row at or before the timestamp). Rows
90 and 91 exist to meet that on purpose: they are exact twins.

The two APIs answer differently and **both are expected to be right**:
`get_online_features` is a lookup and should answer per requested row;
`get_historical_features` is a join and should collapse the twins. So the offline
answers are re-attached **by the entity keys the store actually keyed on**, never
by position, and any shortfall is CLASSIFIED rather than asserted away — an
`unexplained` row is a FAIL naming row ids, which is M8-S3's own closure shape.

**And it is not a rare edge here — it is the majority of every answer**, because
every declared pair is retrieved at the SAME instant, so `(keys, timestamp)`
duplicates are the rule rather than the exception:

| answer | declared | returned by the join | duplicate entity key | UNEXPLAINED |
|---|---:|---:|---:|---:|
| `pu_zone` | 100 | 34 | 66 | 0 |
| `do_zone` | 100 | 37 | 63 | 0 |
| `calendar` | 100 | 79 | 21 | 0 |
| `od_window` | 100 | 67 | 33 | 0 |
| `pu_hour_window` | 100 | 73 | 27 | 0 |

`get_online_features` answered **100 of 100 on every view**; the join answered as
few as **34**. The two APIs disagree about the SHAPE of the answer and both are
right — and M8-S3's second cause (*no source row at or before the timestamp*) is
correctly **empty**, because a retrieval after the last window closed cannot
predate its own sources. Had this table been aligned by position it would have
compared a store against a shuffled copy of itself, and the failure would have
been loud, random and mystifying. **F-056 stopped being an M8-S3 curiosity and
became the normal case the moment the timestamps stopped varying.**

## §7 End state

* `@champion` version **2** / `feature_set v2`, versions `['1', '2']` — read and
  unmoved. No version was created; nothing was fitted for a model.
* `make verify-m5` **GREEN** and `make verify-m7` **GREEN** — the champion's own
  wire was never touched by this story, and both gates re-asked the endpoint for
  a prediction to prove it (`10.665224` minutes, stamped `model_version='2'`).
* Host unit suite **1041 passed** (33 new), `ruff` clean.
* `uv.lock` **byte-identical to the `m7-closed` tag** (`git diff m7-closed --
  uv.lock` is empty); the quarantine gained exactly two pins, `redis==7.4.1` and
  `hiredis==3.4.1`, which are feast's own `[redis]` extra.
* All four settled DVC pins: `Data and pipelines are up to date.`
* The store is up, holding **57,688 keys / 14.32 MiB** against a 512mb
  `noeviction` cap, materialized in **7 s**.
* **The transformer is NOT built.** That is leg 2, and this is the kickoff's own
  declared safe stopping point: the blueprint's accept artifact — the parity
  table — exists and is committed. The three candidate shapes are still in the
  kickoff's order and none has been attempted, so leg 2 inherits an unspent
  3-attempt wall.
