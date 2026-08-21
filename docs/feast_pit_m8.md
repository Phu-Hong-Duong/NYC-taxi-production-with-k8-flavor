# Point-in-time correctness, measured — retrieval parity and the leak made visible (M8-S3)

*Written 2026-08-21. §1–§4 are the DESIGN and the ARGUMENT and were committed
before the first comparison ran; §5 onward carry the measurements. The ordering
is not a courtesy — it is the only thing that makes the bar in §2 a bar rather
than a description of a number that had already been seen (M8 law 4, the
discipline `docs/slo_serving.md` §8 and `automation/runs/m7-drift/headroom.json`
established at M7-S3 and which `verify-m7` §4 checks on three clocks including
git).*

---

## 1. What is measured, and what is not

Two measurements, both read-only over settled data. Nothing is fitted, no alias
is read or moved, no registry version is minted, no threshold moves (M8 law 3).

**(1) Retrieval parity.** For a DECLARED, committed row set, every feature the
Feast store hands back through `get_historical_features` must equal the value the
ONE `taxi_mlops.features` path uses for that same row. The comparison crosses the
quarantine: Feast reads the parquet under `data/feast/` with **pandas 2.3.3**,
joins, and writes parquet back; this side reads it with **pandas 3.0.5** and
computes the truth through the same functions the champion's own matrix comes out
of. That seam is real — M5-S3 measured the mlserver seam at `0.000e+00` precisely
because nothing on its numeric path differed — so it is measured rather than
assumed.

**What this does NOT claim.** It does not prove the store could serve the
champion at request time; that is M8-S4's online path and its own 100-pair table.
It does not prove the *published* aggregates are the right features — they lost
the M3 ablation and the catalog says so. And it says nothing about a value the
store does not hold: the nine geometry features and the cyclical encodings are
DERIVED on this side from the lookups the store serves, so what is measured here
is the lookups, and the derivations are already covered by `make parity`.

**(2) The point-in-time proof.** M3-S3's leakage red team, run through M8's
machinery. The same rows are retrieved twice from the same store by the same
call, differing in exactly one column: the honest pass passes each row its own
event timestamp, the naive pass overwrites every timestamp with a single instant
after the last window closed. The naive pass is `docs/feature_dossier.md` §4
trap 2 in its purest form — a March row served an aggregate computed with June in
it — and the assertion is two-sided:

* the two joins **differ** wherever the naive one reaches forward (the difference
  IS the leakage, in minutes and km/h), and
* the honest join's values **equal** what our own
  `aggregates.fit(point_in_time=True)` + `transform` serve the same rows — two
  implementations, one number, which is the strongest shape this program trusts.

The second half is what makes the first half mean something. A naive-vs-honest
difference alone is consistent with the honest join being wrong in some other
way; reconciling the honest join against the fitted tables pins it.

**Why end-of-window stamps are what make this work** (`docs/prior_art.md`'s
ADOPT, landed at M8-S2): a table over months ending with *m* is knowable at the
first instant of *m+1*, so it is stamped there, and Feast's join condition
`source.event_timestamp <= entity.event_timestamp` therefore hands a row of month
*k* exactly the table `aggregates.transform` hands it — months 1..k-1. The
correspondence is not a coincidence to be discovered; it was derived in
`scripts/feast_sources.py` and is already pinned by
`tests/unit/test_feast_repo.py::test_the_window_stamps_in_the_registry_are_the_six_month_starts`.
This story measures whether the join actually behaves that way on real rows.

---

## 2. The tolerance, argued from the dtype path — BEFORE the first comparison

**The bar is EXACT — `0.0` on every column, integer, categorical and float
alike** — and the reason it can be exact rather than a float epsilon is a
property of the design, not an optimism about floating point:

> **Nothing on the store's side of the wall performs arithmetic.** Feast does not
> compute these numbers; `make feast-sources` computes them on THIS side, through
> the same functions the champion's matrix uses, and the store's entire job is to
> remember them and to pick the right row. A retrieval is a copy and a join. A
> copy of a float that is never added to anything is the same float.

Column by column, the path each value takes:

| Column(s) | Our side holds | Producer writes | Parquet | Feast returns | Bar |
|---|---|---|---|---|---|
| `centroid_lat` · `centroid_lon` | `float64` (`zones.ZoneTable`) | `.astype("float64")` — identity | DOUBLE | `float64` | **exact** |
| `borough` · `window_months` | `str` | `str` | BYTE_ARRAY/UTF8 | `str` | **exact** |
| `is_airport` · `is_holiday` · `is_near_holiday` · `is_business_day` | `bool`/`int16` 0-1 | `.astype("bool")` | BOOLEAN | `bool` | **exact** |
| `od_median_duration_min` · `pu_hour_mean_speed_kmh` · `pu_hour_trips_per_day` | `float32` (`AggregateTables`) | `.astype("float64")` — a **lossless widening**: every float32 has an exact float64 representation | DOUBLE | `float64` | **exact** |

The float32 row is the only one that needs an argument beyond "a copy is a copy",
and it is the well-known direction: widening `float32 -> float64` is exact for
every finite value, so comparing our `float32` widened the same way is a
comparison of two identical bit patterns. Had the producer *narrowed* — float64
sources written as float32 — the bar would have had to be a float bar with a
stated ulp, and the honest thing would have been to fix the producer instead.

Two supporting facts, both already measured and neither assumed here: the M8-S2
probe recorded that the two sides of this quarantine **differ on exactly one
package — pandas** (`automation/runs/m8-feast/probe.json`; numpy 2.5.2, pyarrow
25.0.1 and CPython 3.12.14 are identical on both), and pandas is not on this
path — pyarrow is what encodes and decodes every value that crosses. And M5-S3's
precedent says a seam across two runtimes can measure exactly zero when nothing
on the numeric path differs.

**What would make it nonzero, named now so a result cannot be rationalised
later.** A producer that computed instead of copying · a float32 column written
as float32 and decoded through a dtype that rounds · a store-side aggregation or
a TTL silently dropping a row · a join that served the wrong window. **Each is a
finding to investigate — which side rounded, which dtype narrowed — and never a
bar to widen** (M8 law 4; the M5-S3 red team's rule, and gotcha #73's).

**Missing values are compared, not skipped.** `NaN != NaN`, so the comparison
treats *both missing* as equal and *one missing* as a MISMATCH. This is
load-bearing rather than pedantic: zones 264 and 265 are TLC's "Unknown", have no
centroid by design (DR-04 condition 1) and therefore have **no row in
`zone_static`**, so the store's answer for them is null. Our side's zone table
answers `NaN` for the same zones. A comparison that quietly dropped nulls would
be blind to exactly the ~1% of rows F-030 was found on, and to the largest single
OD "route" in this data (264→264, 409,128 trips).

**One representation difference is asserted rather than compared**, and it is
named here because discovering it later would look like a mismatch: for a
no-geometry zone the store returns null for `borough` and `is_airport`, while
`zones.load_zone_table()` answers borough `"Unknown"` and airport `False`. Those
are the same fact in two vocabularies — "not a place" — so the check for those
rows is the two-sided one: **the store must return null AND our path must report
`has_geometry = 0`**. Manufacturing a "Unknown"/False row in the store to make a
column-wise comparison succeed would be putting a plausible place into a feature
store to satisfy a test.

---

## 3. The row set — declared, committed, each row naming why

`infra/feast/retrieval_rows.csv`, read by the comparison and never generated
inside it. Sampling at run time would give a number that changes every run, a red
team that cannot plant a cause, and a set that never contains the rows that
actually break things (M5-S3's argument, applied a second time).

| Stratum | Rows | Why it is in the set |
|---|---|---|
| `hazard` | 16 | **Imported verbatim from `taxi_mlops.serving.parity.HAZARDS`**, not retyped — the same sixteen rows `make parity` measures the wire with, so the two seams are measured against one row set. Each carries its own `why` from that module: airports, an OD pair unseen in train, the 100–120 min tail, midnight and week seams, passenger_count 0 and 6, F-019's 2026 date, and the two no-geometry rows. |
| `month-boundary` | 12 | The PIT proof's own rows: six pairs, each straddling a train-month boundary by two minutes. Adjacent rows differ by 120 seconds and MUST be served different windows — the smallest possible interval over which the join's behaviour is visible. |
| `ordinary` · `airport` · `no-geometry` · `long-trip` | 4 × 15 | Drawn ONCE from `trips_train` with a recorded seed and committed, so real key combinations across all six train months are covered without the set moving between runs. The four strata are M6-S3's shadow strata, kept so the two stories' samples are comparable. |

---

## 4. How the proof is run

`make feast-retrieval` is the whole path, and it crosses the wall exactly twice,
both times through parquet:

1. **this side** builds the entity dataframe from the committed row set and
   writes it to `data/feast/`;
2. **the quarantine** (`infra/feast/retrieve.py`, which imports `feast` and never
   `taxi_mlops`) runs five honest retrievals and two naive ones and writes the
   answers back as parquet;
3. **this side** computes the truth through `taxi_mlops.features` —
   `zones.load_zone_table()`, `calendar.flags()`, and
   `aggregates.fit(point_in_time=True)` over the six train months followed by
   `transform` — and compares.

The aggregate tables are **re-fitted from `data/processed/`**, never reconstructed
from the parquet the store reads. Rebuilding the truth from the artifact under
test would compare the store against itself and pass for any join at all.

The naive timestamp is derived, not typed: it is the first instant after the last
window's stamp, read off the published `window_months`.

**A property observed while building this and stated because a reader will hit
it:** `get_historical_features` returns one row per DISTINCT (entity keys, event
timestamp), so the naive pass — which collapses every row onto one instant —
legitimately returns FEWER rows than it was given whenever two rows share entity
keys. The honest pass must not: its rows carry distinct real timestamps, so a
short answer there would mean rows were dropped, and the comparison asserts the
honest retrieval's row count equals the row set's.

---

## 5. Retrieval parity — the measurement

*(pending — filled from `automation/runs/m8-pit/retrieval_parity.json`)*

## 6. The point-in-time proof — the measurement

*(pending — filled from `automation/runs/m8-pit/pit_proof.json`)*
