# The feature catalog — what the store holds, where it came from, and what it is worth

**M8-S2 · 2026-08-21 · role: DE (A), MLE (R)**
Definitions: `infra/feast/feature_repo/definitions.py` (in git) ·
Producer: `scripts/feast_sources.py` · Registry record:
`automation/runs/m8-feast/registry.json` · Probe: `automation/runs/m8-feast/probe.json`

---

## §0. What this page is for, and the one thing that makes it different

A feature catalog usually lists what a store can serve. This one also records
**what each entry is worth, measured** — including the entries that are worth
nothing, with the number that says so.

That is not a stylistic preference. The single strongest feature family in every
source `docs/feature_dossier.md` harvested — historical zone/OD aggregates, "the
congestion memory" — is in this catalog and is **NOT in the champion**, because
when M3-S3 measured its only legal form it made the model **worse**. A catalog
that listed it beside the winners with no verdict would invite the next engineer
to spend a milestone rediscovering that, and would look exactly like a catalog
that had never tried.

So every entry below carries one of three verdicts:

| Verdict | Meaning |
|---|---|
| **in-champion** | feature set **v2** (registry version 2, serving now) is built from this table today |
| **catalog-only** | defined, materializable, and deliberately **not** in any model — with the measurement that kept it out |
| **candidate** | a definition worth trying, with the evidence that motivates it. **Nothing is fitted** (M8 law 3); a model that eats one of these is a future milestone's gate story |

The verdicts live in two places on purpose: as `tags` on the Feast objects (so
they travel with the definition into the registry) and in this page (so a human
reads them). `tests/unit/test_feast_repo.py` fails if the two disagree — the
catalog cannot drift from the store, and neither can quietly acquire an entry
the other has not heard of.

---

## §1. The wall, and why there are two interpreters

Measured live, twice — at the milestone's draft and again by this story's probe:

```
[quarantine]   project    pandas 3.0.5
[quarantine]   quarantine pandas 2.3.3  feast 0.66.0
[probe] feast 0.66.0 in 64 packages; the two sides differ on ['pandas']
```

`feast 0.66.0` declares `pandas<3,>=1.4.3`. This project runs pandas **3.0.5** —
a version every published number in this repository was measured on. There is no
resolution that satisfies both, so **there is no `uv add feast` in this
repository and never will be**: the isolated interpreter `.venv-feast` is the
design, not the fallback (M8 law 4; gotcha #16's quarantine, and the
full-`mlflow` shape of gotcha #36).

Two facts about that measurement are load-bearing for M8-S3:

- **The two sides differ on exactly ONE package.** numpy `2.5.2`, pyarrow
  `25.0.1` and CPython `3.12.14` are identical on both sides. The seam M8-S3
  measures is therefore a pandas seam and nothing else — which is the same shape
  as M5-S3's mlserver parity, where three packages differed, none of them on the
  numeric path, and the answer came back `0.000e+00`.
- **Nothing crosses the wall except parquet.** `scripts/feast_sources.py` imports
  `taxi_mlops` and not `feast`; `definitions.py` imports `feast` and not
  `taxi_mlops`. Both directions are asserted by AST in
  `tests/unit/test_feast_repo.py`, because one import across that line is how a
  quarantine stops being one.

The quarantine rebuilds from a committed, complete pin file with
`uv pip install --no-deps -r infra/feast/requirements-feast.txt` — 64 exact pins,
no resolution at install time. **Proved from scratch this session**: the venv was
deleted and rebuilt, and the same 64 packages came back. Its exit invariant is
checked rather than asserted — `uv.lock`'s sha256 before and after, with a
difference aborting the script.

---

## §2. Where the data comes from — and what may not be touched

Every source is derived **read-only** from an artifact this program already had
and already pinned (M8 law 2):

| Source parquet | Rows | Derived from | Through |
|---|---|---|---|
| `zone_static.parquet` | 263 | `data/reference/taxi_zone_centroids.csv` + `taxi_zone_lookup.csv` (`make zones`, M3-S2) | `taxi_mlops.features.zones.load_zone_table` |
| `calendar_day.parquet` | 4,383 | `data/reference/us_federal_holidays.csv` (`make holidays`, M5-S2) | `taxi_mlops.features.calendar.flags` |
| `od_window_stats.parquet` | 248,169 | `data/processed/` train months 2019-01..06 (43,987,422 rows) | `taxi_mlops.features.aggregates.fit(point_in_time=True)` |
| `pu_hour_window_stats.parquet` | 35,589 | the same 43,987,422 rows | the same call |

**Nothing is computed in the feature repo.** The flags are not re-derived from
the holiday CSV; the aggregates are not re-implemented in SQL. Each one comes out
of the same function the champion's own matrix comes out of, because a store that
recomputes what the feature path computes is a second definition of a number this
repo already owns — M1-S2's `split`/`month` lesson one layer along, and the
mistake `configs/features.yaml` exists to prevent one layer up.

The outputs land in `data/feast/`, which is **gitignored and deliberately not
DVC-tracked**, on `data/predictions/`'s terms exactly: it is derived output,
regenerable by one command from pinned inputs, and a `.dvc` pin that must be
refreshed every time an upstream tree moves is provenance that lies. The
provenance is this page plus `automation/runs/m8-feast/registry.json`.

Story-exit invariant, run after the sources were built:

```
data/processed.dvc          up to date
data/rejected.dvc           up to date
data/scoring.dvc            up to date
data/scoring_rejected.dvc   up to date
```

---

## §3. Entities

| Entity | Join key | Why this shape |
|---|---|---|
| `zone` | `zone_id` | a TLC LocationID. 1..263 have geometry; **264/265 have no row at all** |
| `pickup_zone` | `PULocationID` | half of the OD pair |
| `dropoff_zone` | `DOLocationID` | the other half |
| `pickup_hour` | `hour` | 0..23 — the congestion window's second key |
| `calendar_day` | `date_key` | `YYYY-MM-DD` |

**The OD pair is a composite of two zone entities, not a synthetic
`od_pair_id`.** The join keys are then the column names the rest of this program
already uses (`PULocationID`, `DOLocationID`), so a retrieval request and a
feature matrix spell the pair the same way and no encode/decode step exists to
disagree with itself.

**Zones 264 and 265 get no row, and that absence is load-bearing.** They are
TLC's "Unknown" and "N/A" — not places (DR-04 condition 1, `docs/eda_report.md`
§9) — and `264 -> 264` is the largest single OD "route" in the data. A retrieval
for them returns **null**, which is precisely the `has_geometry = 0` fallback the
champion's own matrix carries for those ~1% of rows. Manufacturing a row with
zeroed coordinates would put a plausible-looking place at the equator into a
feature store, which is the failure F-030 already paid for once at the wire.

---

## §4. The catalog

### `zone_static` — **in-champion** {#zone_static}

263 rows · entity `zone` · no TTL · stamped `2019-01-01T00:00:00`

| Field | Type | In the champion as |
|---|---|---|
| `centroid_lat`, `centroid_lon` | Float64 | the input to all nine **g2** geometry features |
| `borough` | String | g3's `pu_borough` / `do_borough` / `borough_pair` — **not** in v2 |
| `is_airport` | Bool | g3's airport flags — **not** in v2; see `airport_regime_flag` below |

**Verdict: in-champion.** Feature set v2 carries nine centroid-derived features
(`centroid_haversine_km`, `centroid_bearing_deg`, `midpoint_lat`, …) and every
one of them is a lookup on exactly this table. Group **g2 measured +0.63%
relative val MAE with KPI-10 +0.200 points at full data — KEEP**
(`docs/ablation_m3.md` §5). Serving these from a store changes no number; it
changes *who owns the lookup at request time*, which is M8-S4's question and not
this story's.

**No TTL, and that is a claim rather than a default:** a zone's centroid is not a
measurement that goes stale. The table changes only when TLC redraws the zones,
and that is a new artifact with a new sha256, not an expiry.

Honest note on two of the four fields: `borough` and `is_airport` are **catalog
content on an in-champion table**. They are here because they are facts about a
zone that this repo already derives, and because `airport_regime_flag` needs
`is_airport` to exist before it can be tried. Group g3, which is what a model
made of them, measured **+0.14% — under DR-02's 0.50% bar, dropped.**

### `calendar_day_flags` — **in-champion** {#calendar_day_flags}

4,383 rows (2019-01-01 … 2030-12-31) · entity `calendar_day` · no TTL ·
stamped `2019-01-01T00:00:00`

| Field | Type |
|---|---|
| `is_holiday`, `is_near_holiday`, `is_business_day` | Bool |

**Verdict: in-champion.** These three columns are part of group **g1**, the
largest single win of the M3 ablation: **+1.77% relative val MAE, KPI-10 +0.569
points at full data — KEEP.**

**The horizon is the table's, not a guess.** F-019 made an uncovered date a typed
`UncoveredDateError` (HTTP 422) rather than a silent "not a holiday", so this view
stops exactly where the committed table stops — 2030. A store that answered
`is_holiday = false` for 2031 would be doing the thing F-019 refused, one layer
further from anyone who could notice.

**Why every row carries the derivation stamp rather than its own date.** A
calendar fact about 2027-07-04 is knowable the moment the statute is read — 5
U.S.C. §6103 is the source and `make holidays` derived all 146 holidays at once.
Stamping each row at its own date would make a point-in-time join withhold a
date's flags from a request *about that date*, which is the opposite of the
truth. This is the one view where end-of-window and knowability come apart, and
it is stamped by knowability.

### `od_window_stats` — **catalog-only** {#od_window_stats}

248,169 rows across 6 windows · entities `pickup_zone` + `dropoff_zone` · no TTL

| Field | Type |
|---|---|
| `od_median_duration_min` | Float64 |
| `window_months` | String (the window's own months, so a retrieved row can say what it was computed from) |

### `pu_hour_window_stats` — **catalog-only** {#pu_hour_window_stats}

35,589 rows across the same 6 windows · entities `pickup_zone` + `pickup_hour` ·
no TTL

| Field | Type |
|---|---|
| `pu_hour_mean_speed_kmh` | Float64 — from the **centroid** distance, never the meter's `trip_distance` (an excluded column) |
| `pu_hour_trips_per_day` | Float64 — a **rate**, never a count |
| `window_months` | String |

**Verdict for both: catalog-only, and the measurement is the whole entry.**

Group **g5 — point-in-time aggregates** is the strongest family in every source
this program read, and it is the one that **lost**: **−1.63% relative val MAE,
KPI-10 −0.686 points**, dropped (`docs/ablation_m3.md` §4). Two things must be
said about that number rather than around it:

1. **It is a 15%-sample number, and it is labelled as one** (gotcha #15). The
   four groups that were *kept or nearly kept* were re-confirmed at full data;
   a dropped group is never refitted, so no full-data number for g5 exists and
   this catalog does not invent one.
2. **The illegal version would have passed.** M3-S3's mandated red team fitted
   the same tables across the val month on purpose: **+1.56% on the month it saw,
   −3.83% on the untouched one** (`docs/leakage_redteam_m3.md`). The family is
   not weak — its *legal* form is weak, because our `PULocationID` /
   `DOLocationID` already **are** the key the aggregate is grouped on, so the
   memory adds little the identity did not already carry.

That pair is why these views exist here and not in `configs/features.yaml: v2`,
and it is the reason this catalog records losers at all.

**A rate, not a count, and the reason survives the move into a store.** The
window grows month by month, so a raw count would encode "how late in the
training window this row is" — `month` re-entering by the back door, which this
program forbids outright. `pu_hour_trips_per_day` divides by the distinct days in
the window. A future consumer reading it out of a feature store, months from now
and without `aggregates.py` open, needs that in the catalog.

**A trap named for whoever materializes these to an online store (M8-S4):** the
online store keeps only the LATEST value per entity key, so an online read of
these views can only ever return the **full** window (stamped 2019-07-01). That
is correct for serving a request *today* and completely wrong as an answer about
a 2019-03 row. The point-in-time semantics live in the OFFLINE store, and any
online/offline parity table for these two views must compare like with like.

**No TTL, and here that is a semantic claim.** A window aggregate is the best
available knowledge until a later window supersedes it, so a val row in 2019-07
and a test row in 2019-08 must both be served the window stamped 2019-07-01 —
which is exactly what `aggregates.transform` serves them. A TTL would make the
store disagree with the fitted model as the gap widened.

### `airport_regime_flag` — **candidate** {#airport_regime_flag}

Not a view. A recorded candidate, buildable today from
`zone_static.is_airport` on both ends of a trip, declared in `definitions.py`
as `AIRPORT_REGIME_CANDIDATE` so it travels with the definitions rather than
living only in prose.

**Why it is worth trying, in three independent measurements** — the named reader
`docs/error_memo_m2.md` §7 row 2 has been waiting for:

| When | The airport error gap | Source |
|---|---|---|
| M2-S4 | **1.90×** ordinary error, KPI-12 59.988% | `docs/error_memo_m2.md` §6 |
| M3-S5 | **1.91×**, and it held even though v2 now carries the OD geometry §4 predicted would identify airports | `docs/error_memo_m2.md` §9 |
| M7-S5 | **1.86–2.00×** in three ordinary periods, **2.07–2.35×** through the 2020-03 collapse | `docs/drift_memo_m7.md` |

**The third measurement is the one that discriminates.** Through March 2020 the
roads emptied and the median trip ran **49.3% faster** — minutes-per-mile changed
outright. If the airport penalty were carried by *distance*, the ratio had to
move; it barely did. A quantity that holds constant across a regime change rules
out a hypothesis that a quantity measured once cannot, which is why the drift
memo recommends the flag be evaluated as a **regime indicator** and not as a
distance proxy.

**Nothing is fitted for it here** (M8 law 3). Note what stands against it: group
g3, which contained plain airport flags, measured **+0.14%** and was dropped. The
candidate is not "add the flag again" — it is "evaluate it as the regime term the
three measurements point at", which is a gate story with a hypothesis, not a
column.

---

## §5. Event timestamps: end-of-window, derived, never typed

The prior-art ADOPT (`docs/prior_art.md`): **a feature computed over a window is
knowable only once the window has ended.** M3-S3 paid for that lesson in the
leakage red team, and here it becomes a timestamp convention.

`aggregates.fit` builds, for train month *k*, a table over months **1..k−1 and
nothing else**. So the table over a window ending with month *m* becomes knowable
at the first instant of month *m+1*, and that instant is its `event_timestamp` —
derived in `scripts/feast_sources.py` from the window's own months, never typed.
Read back off the applied registry:

| Window | `event_timestamp` | OD rows | pu-hour rows | Served by `aggregates.transform` to |
|---|---|---|---|---|
| (none) | — *no rows at all* | — | — | 2019-01, which gets NaN: no history |
| 2019-01 | `2019-02-01T00:00:00` | 32,164 | 5,628 | 2019-02 |
| 2019-01..02 | `2019-03-01T00:00:00` | 37,921 | 5,835 | 2019-03 |
| 2019-01..03 | `2019-04-01T00:00:00` | 41,475 | 5,947 | 2019-04 |
| 2019-01..04 | `2019-05-01T00:00:00` | 44,020 | 6,012 | 2019-05 |
| 2019-01..05 | `2019-06-01T00:00:00` | 45,651 | 6,063 | 2019-06 |
| 2019-01..06 | `2019-07-01T00:00:00` | **46,938** | 6,104 | every later month — val 2019-07 **and** test 2019-08 |

**The correspondence is exact, and that is what M8-S3 measures.** Feast's
point-in-time join takes the newest row with `event_timestamp <= entity
timestamp`. Under these stamps, a 2019-04 pickup is handed the 2019-01..03
window — the same table `aggregates.transform` hands it — and a val or test row
is handed the full window, which is what `transform` does for any month outside
the fitted set. The two implementations should therefore agree on every key. That
is S3's two-sided assertion, and it is set up here rather than discovered there.

**The first train month deliberately has no rows.** `AggregateTables.empty()`
serves 2019-01 NaN rather than a number containing its own answer; a
point-in-time lookup before 2019-02-01 returning null **is** that NaN, expressed
in the store's vocabulary.

**One corroboration nobody arranged.** The full window's OD table holds **46,938**
rows. `docs/promotion_gate_m3.md` records that M3-S1's floor,
`baseline-group-median-od-fallback`, was fitted over the same six months with
**46,938 backoff cells**. Two entirely different code paths — a baseline's
`(PU, DO)` backoff table and a feature store's source parquet — counting the same
set of OD pairs and arriving at the same integer.

---

## §6. What `feast plan` cannot tell you — F-055

`feast plan` **can never report "no changes" for this repo**, and the reason is
not our configuration. Feast stamps `created_timestamp` / `last_updated_timestamp`
into a `DataSource`'s `meta` when the Python object is constructed — that is
import time, i.e. every invocation — so the registry's stored copy and the
freshly-imported one always differ, and `plan` faithfully prints four "Updated
feature view" blocks whose entire content is two clock readings.

A signal that says *changed* whether or not anything changed cannot answer the
question `plan` exists to answer. It is gotcha **#78** in a new place: there, an
empty panel was indistinguishable from a quiet system; here, a full diff is
indistinguishable from a real edit.

So `make feast-plan-check` asserts the statement that **can** be false: every
difference `plan` reports is confined to those two clock fields. Anything else —
a renamed field, a moved source path, a changed dtype, a view appearing or
vanishing — is substantive and exits 1 naming it.

```
[plan] Updated  feature view  calendar_day_flags     clock only (Feast re-stamps meta on import — F-055)
[plan] Updated  feature view  zone_static            clock only (Feast re-stamps meta on import — F-055)
[plan] Updated  feature view  pu_hour_window_stats   clock only (Feast re-stamps meta on import — F-055)
[plan] Updated  feature view  od_window_stats        clock only (Feast re-stamps meta on import — F-055)
[plan] feast says: No changes to infrastructure
[plan] 4 object(s) reported, 4 clock-only, 0 substantive
[plan] ok  the registry matches the definitions in git (no substantive diff)
```

**Red-teamed live**, because a checker nobody has watched say no is a checker
nobody has checked: one field renamed in `definitions.py`
(`centroid_lat` → `centroid_lat_TAMPERED`), the check went **FAIL naming
`zone_static`** and the tampered field, **the other three views still read
clock-only**, and the file was restored from git and re-applied to GREEN. A
checker that went red on all four would have been checking that something
changed, not what.

---

## §7. What this story deliberately did not do

- **Nothing was fitted, no alias moved, no registry version was minted**
  (M8 law 3). `@champion` is version 2 before and after; this story never read it.
- **No feature here is added to the champion.** The catalog records candidates;
  a model that eats one is a future milestone's gate story (M8 out-of-scope list).
- **No online store, no materialization, no feature server.** M8-S4's, with its
  own two-sided reachability decision. The `online=True` flag on these views says
  they are *eligible*; the sqlite store `feast apply` created is empty.
- **The retrieval parity is not measured here.** M8-S3 owns it, with the
  tolerance argued from the dtype path **before** the first comparison runs
  (M8 law 4's family). This page states what makes that measurement possible —
  one pandas version of difference, and an exact correspondence between the
  stamps and `aggregates.transform`.

## §8. Commands

| Intent | Command |
|---|---|
| Build the quarantine from its exact pins, prove `uv.lock` untouched, write the probe | `make feast-quarantine` |
| Re-resolve Feast and rewrite the pin file | `make feast-quarantine QUARANTINE_ARGS=--resolve` |
| Build the parquet Feast reads, from the settled trees | `make feast-sources` (`SOURCES_ARGS=--static-only` skips the 43.9M-row fit) |
| Register the git-defined entities and views | `make feast-apply` |
| Ask whether the registry still matches git (F-055) | `make feast-plan-check` |
| Read the applied registry back and record it | `make feast-registry` |
