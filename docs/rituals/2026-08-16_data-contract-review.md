# Data Contract Review — 2026-08-16 (M1-S2)

Date: 2026-08-16 · Story: M1-S2 · Contract under review: `configs/data.yaml` +
`src/taxi_mlops/data/contract.py` + `clean.py` **as committed at `22d1448`**
(M1-S1's story commit, merged as `943c977`) — not the working tree.

Roles present (as blocks, PROMPTS Prompt D):

```
── role-block: role:DE · story: M1-S2 ──
charter read: yes · open findings owned by this role: none at entry
this block produces: DVC pinning, the DuckDB analyst layer, `make data`,
  the byte-identical rebuild proof · refusals in play: no silent schema change;
  no dtype cast outside ingest
```

```
── role-block: role:DA · story: M1-S2 (DA hat for the ritual) ──
charter read: yes · open findings owned by this role: none at entry
this block produces: the challenges below · refusals in play: a number without
  its definition and window; querying raw parquet when the analyst layer exists
```

**Data the challenges were run against:** the analyst layer built this session —
`trips_clean` (56,127,878 rows, 8 months, 2019-01…08), `ingest_rejections`,
`ingest_months`, `raw_manifest`. Every figure below came from a query against a
named view; no raw parquet was read (DA refusal #2). Row counts reconcile
against S1's reports month by month (`make duckdb` → GREEN, 8/8).

---

## 1. What was read

| Artifact | What it claims to guarantee |
|---|---|
| `configs/data.yaml:contract` | required + year-aware columns, one canonical dtype cast, `on_unknown_column: refuse` |
| `configs/data.yaml:clean` | ten named rejection rules, applied in order, `max_rejected_fraction: 0.10` |
| `contract.validate_input/validate_output` | structure refuses; `nullable: false` is a POST-clean guarantee |
| `clean.clean` | every dropped row attributed to a rule, counted twice |

## 2. Challenges

### DCR-01 — The rejected rows exist only as counts. Nobody can say what was thrown away.

**Claim (DA).** 914,459 rows (1.603%) were dropped, and the contract is
scrupulous about *counting* them — but not one of them was *kept*. The counts
answer "how many"; they cannot answer "which kind", and that is the question an
EDA report and an error memo both need.

**Evidence.** Rule totals over all 8 months (`ingest_rejections`):

| rule | rejected_by | matched | % of all rows |
|---|---:|---:|---:|
| duration_below_min | 512,388 | 569,710 | 0.8983% |
| duration_above_max | 159,300 | 159,300 | 0.2793% |
| distance_non_positive | 117,932 | 465,911 | 0.2067% |
| fare_negative | 64,284 | 96,308 | 0.1127% |
| duration_non_positive | 57,322 | 57,322 | 0.1005% |
| pickup_outside_month | 3,182 | 3,688 | 0.0056% |
| distance_above_max | 51 | 238 | 0.0001% |
| location_out_of_range · missing_timestamp · passenger_count_out_of_range | 0 | 0 | 0 |

`duration_above_max` alone removes 159,300 trips over 120 minutes. Whether those
are meter faults or a real long-haul/airport population is **unanswerable from
the artifacts that exist** — the rows are gone, and no view can reach them.
The consequence if this is wrong: the model never sees long trips, the KPI board
under-reports revenue, and neither shows a symptom.

**DE response.** Correct, and it is a real gap rather than an oversight of
counting. Fixing it means ingest writing a rejected-row artifact, which changes
what lands on disk — immediately after this story proved byte-identity over the
current outputs, and inside a story whose scope is DVC + the analyst layer.
Doing it here would be scope creep with a rebuild proof to re-run.

**Verdict: CARRIED** → `ledgers/findings.md` **F-005** (owner DE). Not a debt
row: no milestone's quoted scope promises this capability, so inventing a
landing for it would be the carried-to-nowhere failure gotcha #19 exists to stop.

### DCR-02 — The missingness is one correlated event, and one column disguises it as data.

**Claim (DA).** M1-S1's handoff records "passenger_count nulls (28,672/month) …
one vendor batch". The batch is real and larger in consequence than recorded:
the same rows are null in **three** columns and carry a **fourth** value that is
not null at all — `payment_type = 0`, which on a dashboard reads as a payment
category rather than as a marker for "this vendor sent nothing".

**Evidence.** One query over `trips_clean`, all 8 months:

```
all_four_together = 261,781   (passenger_count IS NULL AND RatecodeID IS NULL
                               AND store_and_fwd_flag IS NULL AND payment_type = 0)
passenger_count IS NULL = 261,781      payment_type = 0 = 261,781
payment_type = 0 AND passenger_count IS NOT NULL = 0
months affected = 8 of 8
```

The coincidence is exact, with zero exceptions, in every month. And the vendor
breakdown is sharper than "one vendor":

| VendorID | rows (all) | rows in the null batch |
|---:|---:|---:|
| 2 | 35,177,412 | 261,562 |
| 1 | 20,685,586 | 0 |
| 4 | 264,661 | 0 |
| **5** | **219** | **219** |

**VendorID 5 exists nowhere else in 56M rows** — 219 of 219 of its trips are
inside the batch. So it is not one vendor's batch; it is one dominant vendor
plus a vendor that only ever appears when the data is broken.

The consequence if this is ignored: `SELECT payment_type, COUNT(*)` — the most
natural KPI query there is — returns a 261,781-row category that means "unknown",
and a DA who filters `WHERE passenger_count IS NOT NULL` unknowingly removes
exactly that same set, so two analysts filtering "differently" get identical
numbers and neither learns why.

**DE response.** The correlation is accepted and the "one vendor batch" wording
in the M1-S1 handoff is corrected here (two VendorIDs, one of which is otherwise
absent). Making `payment_type = 0` a rejection rule is refused: it would delete
261,781 rows over a field that is not the target — the identical reasoning S1
used to decline a rule for `passenger_count` nulls — and a cleaning decision of
that size is not the DA's to take alone in a review.

**Verdict: CHANGED** — the anomaly is made impossible to miss instead of being
cleaned away. `configs/data.yaml:analyst.known_domains` now documents the TLC
dictionary domains (reporting only, enforcing nothing) and the analyst layer
publishes **`unknown_domain_values`**. Undo: delete the config block and the
view; no data, contract or gate moves either way.

### DCR-03 — `fare_amount` has a floor and no ceiling.

**Claim (DA).** `fare_negative` removes 64,284 rows at the bottom; nothing looks
at the top. A KPI board reporting fare figures cannot defend them.

**Evidence.** Over `trips_clean` (56,127,878 rows):

```
fare min = 0.00     fare max = 671,123.14     fare p99.9 = 85.50
rows with fare > 1,000 = 12        rows with fare > 10,000 = 4
mean fare, all rows        = 13.1740
mean fare, fare <= 1,000   = 13.1398
```

**DE response — ANSWERED, with the number that settles it.** The maximum is
absurd (a $671k taxi fare, ~7,850× the 99.9th percentile) but it is **12 rows in
56 million**, and the honest measurement is the effect: the mean moves by
0.26%. That does not justify a new rejection rule, and a rule would mean picking
a threshold from a distribution the EDA has not yet examined — a guess wearing a
rule's clothes. It is *not* harmless for every statistic: any `MAX`, `SUM`, or
high-percentile KPI is destroyed by those 12 rows, and an unscaled model target
would be too.

**Verdict: ANSWERED** (contract stands) **+ action item AI-2** — S3's KPI doc
must state the window and outlier treatment for every money KPI, and cite these
numbers. "Average fare" without a window is exactly the number the DA charter
refuses.

### DCR-04 — Four categorical columns carry values the dictionary does not describe.

**Claim (DA).** `VendorID`, `RatecodeID` and `payment_type` are typed `Int64`
with no declared domain, so a new code is indistinguishable from a real one.
S1 already flagged `RatecodeID 99` and left it undomained on purpose; the
review's addition is that it is a *class* of gap, not one value.

**Evidence** (`unknown_domain_values`, all 8 months):

| column | value | rows | months seen |
|---|---|---:|---:|
| VendorID | 4 | 264,661 | 8 |
| payment_type | 0 | 261,781 | 8 |
| RatecodeID | 99 | 949 | 8 |
| VendorID | 5 | 219 | 8 |

Each appears in **all eight months**, so none is a one-off corruption; they are
undocumented-but-stable, which is the hardest kind to notice.

**DE response.** Accepted as the same finding as DCR-02 seen one level up. The
contract's `on_unknown_column: refuse` watches for columns appearing, vanishing
and being renamed (gotcha #31); nothing was watching a column growing a new
VALUE. Enforcing these domains would refuse every month, which is why they are
documented and reported rather than enforced.

**Verdict: CHANGED** — same change as DCR-02 (`known_domains` +
`unknown_domain_values`), and it is now a standing report rather than four
observations in a handoff.

## 3. Decisions with numbers

1. The contract's **cleaning rules stand unchanged**. Total rejection 1.603%
   (914,459 of 57,042,337), ceiling 10% — the seam is nowhere near being tested.
2. **No new rejection rule** was added by this review. The two candidates were
   priced: `payment_type = 0` would cost 261,781 rows (0.466%) over a non-target
   field; a fare ceiling would cost 12 rows and move the mean 0.26%. Neither is
   a cleaning decision this review is entitled to take.
3. **The layer gained a report instead**: `unknown_domain_values`, covering 4
   documented columns and surfacing 4 undocumented values totalling 527,610 rows.
4. **Row counts reconcile end to end**: 8 of 8 months, view rows == the
   `rows_out` each ingest report claimed, 56,127,878 total.

## 4. Dissent

**Recorded, unresolved.** The DA holds that DCR-01 is the most consequential
item in this review and that carrying it to a findings row is a deferral, not an
answer: every number in the forthcoming EDA report describes the 98.397% that
survived, and the report will not be able to say whether the missing 1.603% was
noise or a population. The DE holds that the fix belongs with the story that
consumes it, not with the story that discovered it. Both positions are in
F-005; the disagreement is about timing, not about whether it is a gap.

Second, smaller dissent: the DA would have preferred `unknown_domain_values` to
be part of `data_health`, so no board can be built without seeing it. The DE
refused on cost — `data_health` is metadata-only and answers instantly, while
this view scans 56M rows, and a health board that is slow gets turned off.
Settled in the DE's favour, recorded here because the DA's reason was good.

## 5. Action items

| Id | Item | Owner | Where tracked | Lands |
|---|---|---|---|---|
| AI-1 | Make the rejected rows characterizable (sample or full sidecar, DVC-tracked, contract-typed) | DE | `ledgers/findings.md` **F-005** | proposed M1-S3; conditions in the ledger row |
| AI-2 | Every money KPI in the KPI doc carries its window and outlier treatment, citing DCR-03's figures | DA | M1-S3 story scope (KPI doc) | M1-S3 |
| AI-3 | The data-health board carries an `unknown_domain_values` card; if a new value appears, it must be visible without anyone querying | DA | M1-S5 story scope (boards) | M1-S5 |
| AI-4 | Correct the "one vendor batch" wording when it is next relied on: two VendorIDs (2 and 5), and 5 appears nowhere else | DA | this minute + M1-S3's EDA | M1-S3 |

---

*A zero-finding review is itself a defect (ORG.md). This one raised four
challenges: two produced a change to the shipped code, one was answered with the
number that settles it, and one is carried as a finding with dissent recorded
rather than argued away.*
