# The scoring months — 2020 through the ONE contract, and the two refusal shapes

**M7-S1 · role:DE (A), MLE (R) · executed 2026-08-20 · EXEC/`claude-opus-5`**

What this story built: a place for months the model is SCORED on, as opposed to
months it is fitted and judged on — reached by the same acquisition, the same
contract, the same one cast, the same counted rejections and the same sidecar
discipline, and landing in trees the settled 2019 pins cannot see.

---

## §0 · Accept-when, answered clause by clause

| §M7-S1 clause | Answer | Where |
|---|---|---|
| shadow torn down with ledger row and `verify-m5` green | `make shadow TEARDOWN=1` removed exactly its own three objects; the champion's three were 21–23 h old and untouched. `make verify-m5` **GREEN 49/49** after | §1, `ledgers/deployments.md` |
| 2020-01..03 ingested into the scoring tree with per-rule rejection tables | **15,712,062 → 15,413,352 rows (1.901% rejected)**, three per-rule tables printed | §3 |
| the sidecars reconciling per (month, rule) | **298,710 == 298,710 across 30 pairs, 0 disagreements** | §4 |
| the 2019 trees byte-identical | `dvc status data/processed.dvc data/rejected.dvc` → `Data and pipelines are up to date.`; neither `.dvc` file modified in git; `data/raw_manifest.json` **+18/−0** with not one diff line mentioning 2019 | §5 |
| the 2025 contract behaviour MEASURED and recorded | **VALIDATED** — a SURPASS over the blueprint's premise, with the transcript and a tracked record | §6 |
| the schema-refusal transcript exists (real file or fixture, named which) | **FIXTURE**, three shapes, derived from the real 2025-01 file; exit **1** each; nothing written | §7 |
| analyst views reconcile or exit 1, proven by red-team unit shapes | two new reconciliations, both red-teamed in unit form (a truncated month; a sidecar relabelled with its monthly total intact) | §4, `tests/unit/test_data_scoring.py` |

---

## §1 · First move: the v1 shadow is down

The M6 boundary decided it (M7 kickoff §0): the shadow's evidentiary work is
done — the F-043 comparison is committed in `automation/runs/m6-gameday/
saturation.json` — and keeping a second predictor as a permanent fixture would
turn an M6-S3 leftover into unplanned wire state.

```
inferenceservice.serving.kserve.io "nyc-taxi-eta-shadow" deleted from serving namespace
ok  nyc-taxi-eta-shadow removed (the champion was not touched)
```

Read back immediately after: one InferenceService (`nyc-taxi-eta`), one
Deployment, one Service, one Ingress — **ages 21 h and 23 h**, i.e. the objects
the teardown did not touch are the objects it did not restart. `make verify-m5`
then went **GREEN 49/49**, which is the check that the champion is still on the
wire answering with the right version.

## §2 · What a scoring month is, and why it is not a fourth split

`configs/data.yaml: scoring` names three months, a tree and a sidecar tree.
`configs/train.yaml` is untouched.

**They are named in data.yaml and not train.yaml on purpose.** Split months live
in train.yaml because they are a MODELLING fact: which month a model is fitted
to, tuned on, judged on. A scoring month is the opposite — a month the model has
nothing to do with until it is asked for a quote. Naming them in train.yaml
would put months a model must never see inside the file that decides what it
sees. The port-family lesson asks for ONE place per fact, and each fact has one.
The single mistake this separation makes possible — a month in both lists — is
**refused by `load_config`**, not trusted.

**Separate trees, not a fourth split directory** (M7 law 2). One 2020 row inside
`data/processed/` would reach the training matrix, the dbt marts and every
Metabase board through globs that were written when that directory meant "the
settled 2019 months" — and it would arrive with no error anywhere. So:

```
data/scoring/<month>/yellow_tripdata_<month>.parquet   (+ .rejections.json)
data/scoring_rejected/<month>/yellow_tripdata_<month>.parquet
```

each with its own DVC pin, for the reason `data/rejected` is not folded into
`data/processed`: separate datasets that move independently do not share a hash.

**One code path, and the tree is chosen by config membership.** `ingest_month`
writes through `cfg.output_path` / `report_path` / `sidecar_path`, which dispatch
on whether the month is in `scoring.months`. The old `processed_path` /
`rejected_path` / `rejections_path` are UNCHANGED and still raise for a scoring
month — every existing caller of those three means "the settled 2019 months",
and a dispatcher hiding inside them would put a 2020 month wherever any of them
is called. A test asserts all three still refuse.

**`make data` was not touched either.** `make data-scoring` is a separate
command. A single command that did both would make every scoring ingest a
rewrite of the trees the whole program's numbers rest on.

## §3 · The three months, as the contract saw them

`make ingest-scoring` (transcript: `docs/scoring_months_m7_transcripts.md` §1).

| month | raw bytes | rows in | rows out | rejected | pct |
|---|---:|---:|---:|---:|---:|
| 2020-01 | 93,562,858 | 6,405,008 | 6,279,806 | 125,202 | 1.955% |
| 2020-02 | 92,134,881 | 6,299,367 | 6,185,309 | 114,058 | 1.811% |
| 2020-03 | **44,442,590** | 3,007,687 | **2,948,237** | 59,450 | 1.977% |
| ALL | | 15,712,062 | 15,413,352 | 298,710 | 1.901% |

Every month raised the same single schema event — `column 'airport_fee' present
ahead of its from_year -- accepted, typed, unused` — which is gotcha #6's design
working: TLC ships a column early and all-null, and an early arrival is not a
defect.

**The pre-routed risk did not materialise, and the way it did not is the
finding.** The M7 kickoff's risk table warned that 2020-03 might refuse at
`max_rejected_fraction: 0.10` because COVID data may be legitimately filthy. It
rejects **1.977%** — indistinguishable from 2020-01's 1.955% and only half a
point above 2019-01's 1.455%. **March 2020 is structurally impeccable and
statistically alien**, which is exactly the signature M7-S3 needs to hold apart
from a schema break: nothing about the file is wrong, there is simply half as
much world in it.

No threshold was touched, because none needed to be.

## §4 · The two new reconciliations

`make duckdb` now runs **five** and exits 1 on any of them. The new pair, on the
tree this story created:

```
[duckdb] scoring months (M7): view rows vs the ingest report, and the sidecar per rule
  month     view rows     rows_out    agree
  -------  ------------  ------------  -----
  2020-01     6,279,806     6,279,806    yes
  2020-02     6,185,309     6,185,309    yes
  2020-03     2,948,237     2,948,237    yes
  ALL        15,413,352    15,413,352    yes
  30 (month, rule) pair(s) checked, 0 disagreement(s); sidecar rows 298,710 == counted 298,710
```

Per (month, rule) and not per month, for M2-S1's reason: a sidecar that files
every row under the wrong rule has a perfect monthly total and is useless for the
one question it exists to answer. Both are red-teamed in unit form — a truncated
scoring month, and a report whose per-rule counts were shuffled while its monthly
total stayed correct. Both turn `report()` False.

The settled reconciliations are unchanged and still green: **56,127,878** clean
rows over 8 months, **914,459 == 914,459** sidecar rows over 80 pairs,
**12,140,456** predictions.

`trips_clean` is deliberately NOT unioned with the scoring rows and a test
enforces it: `SELECT DISTINCT split FROM trips_clean` is still exactly
`{train, val, test}`. Four new views carry the new data —
`trips_scoring`, `trips_scoring_rejected`, `scoring_months`,
`scoring_rejections` — and a consumer that wants 2020 has to say so.

## §5 · The settled 2019 bytes did not move, and that is checkable

```
$ uv run dvc status data/processed.dvc data/rejected.dvc
Data and pipelines are up to date.

$ git status --porcelain data/
M  data/raw.dvc                 <- legitimately gained three files
 M data/raw_manifest.json
A  data/scoring.dvc
A  data/scoring_rejected.dvc
                                <- data/processed.dvc and data/rejected.dvc: absent
$ git diff --stat data/raw_manifest.json
 data/raw_manifest.json | 18 ++++++++++++++++++
 1 file changed, 18 insertions(+)
$ git diff data/raw_manifest.json | grep -E '^[-+]' | grep -c 2019
0
```

**And the new tree inherited the old one's best property for free.** The whole
`make ingest-scoring` was run a SECOND time (its transcript is the one in
`docs/scoring_months_m7_transcripts.md` §1), after which:

```
$ uv run dvc status data/scoring.dvc data/scoring_rejected.dvc data/processed.dvc data/rejected.dvc
Data and pipelines are up to date.
```

— a full re-derivation of 15.4M rows produced byte-identical parquet, because the
scoring tree writes through the same `write_processed` under the same pinned
`compression`/`row_group_size`/`sort_by`. Nobody had to arrange that; it is what
"the same pipeline pointed somewhere else" buys.

`data/raw.dvc` IS re-pinned, and that is not a violation: `data/raw` legitimately
gained three files. The manifest is the file-by-file proof — it is timestamp-free
by design, so a diff there always means the DATA moved, and the diff is **+18/−0
with zero lines mentioning 2019**.

## §6 · The 2025 measurement: it VALIDATES — a SURPASS

The kickoff insisted this leg be a measurement and not an assumption. It is.
`make contract-probe PROBE_ARGS="--month 2025-01"` downloads the **real** file
(59,158,238 bytes, sha256 `9af277e4c0d3…`, 3,475,226 rows, 20 columns) into a
throwaway directory, runs it through the shipped contract, and writes nothing:

```
[probe] SCHEMA EVENT: alias applied: 'Airport_fee' -> 'airport_fee'
[probe] VALIDATED — 2025-01 passed the input contract for 2025 with 1 schema event(s).
        Nothing was written.
```

Three mechanisms carried it, all of them designed at M1-S1 and none of them
touched since: the `aliases` entry caught 2025's `Airport_fee` spelling; the
`from_year: 2025` entry made `cbd_congestion_fee` required and it was present;
and THE cast absorbed the int32/int64 spread that 2025 ships on the id columns.

**This is a SURPASS over the blueprint's premise**, which expected a future
month to break the contract and be *made* to pass. The year-aware contract
(gotcha #6) was written against a 2025 *probe* on 2026-08-16 and against a
2025-shaped unit fixture; this is the first time the real bytes were asked, and
they agree. What it does NOT claim: that 2025 could be ingested and used.
Validation is a structural verdict — the cleaning rules, the 2025 rejection
profile and whether a 2019-fitted champion means anything on 2025 data are all
unasked here.

The probe **acquires nothing**. Its file lands in `data/probe/` (gitignored, not
DVC-tracked), under its own manifest; `data/raw` and `data/raw_manifest.json` are
untouched, and it refuses `--raw-dir data/raw` outright. A probe that leaves data
behind is an ingest wearing a smaller name.

## §7 · The refusal shape, watched on three fixtures

Because the real 2025 file validated, the refusal side had to be demonstrated
another way — and a contract whose refusal has never been watched is a claim, not
a check. `make contract-probe-fixtures` breaks the **real** file's structure in
three ways TLC could actually produce, and requires **exit 1** from each:

| fixture | what it models | verdict |
|---|---|---|
| `drop-required` | a field disappears | `SchemaEventError: … required column(s) absent … ['VendorID']` |
| `rename-required` | a field moves to a new spelling | `… absent: ['VendorID']. Unknown column(s) in the same file: ['VendorID_v2']` |
| `unknown-column` | a field appears that no config knows | `… unknown column(s) … ['surge_multiplier']` |

```
[fixtures] PASSED — 3 refusal shape(s) watched, exit 1 each, nothing written.
```

The exit code is the assertion, not the message: a refusal that exits 0 is a
refusal a pipeline cannot hear. And the drill checks all four data trees hold
nothing for the probed month afterwards, because that is the claim being made.

**The rename fixture found a real defect in the refusal message.** A renamed
column is both an absence and an arrival, and `check_columns` raises in the
missing-required branch *before* the unknown-column branch can run — so the
message named `['VendorID']` as vanished and said nothing about `VendorID_v2`
sitting right there. An operator would have gone looking for a deletion when the
field had merely moved. Both are named now, with the fix (`aliases:`) in the
error text. It was found by running the fixture; reading the code would not have
shown it, because each branch is individually correct.

## §8 · The two signatures, side by side — what M7-S3 must keep apart

This is the pair §9/M7 asks to be shown, and it is now on the record:

| | **Statistical drift** (2020-03) | **Schema drift** (fixture) |
|---|---|---|
| the contract | **passes** — 1 event, the early `airport_fee` | **refuses** — `SchemaEventError` |
| exit code | 0 | **1** |
| rows written | 2,948,237 kept, 59,450 retained | **none — no output, no sidecar, no report** |
| rejection rate | 1.977%, ordinary | n/a: nothing was counted |
| what is visible downstream | a full month of rows whose *distribution* moved | **the absence of a month** |
| what an alert must read | a drift metric over the rows | a job that exited non-zero and produced no metric |

The right-hand column is the one that is easy to get wrong: a schema break
produces **no drift metric at all**, so a drift dashboard that shows "no alert"
looks identical to a healthy month. That is gotcha #78's empty-panel disease with
the panel removed entirely, and it is why S3's freshness guard is not optional.

## §9 · What S2, S3 and S5 inherit — including one warning worth more than the data

**Views**: `trips_scoring` (15,413,352 rows, `split='scoring'`, `month` a config
literal), `trips_scoring_rejected`, `scoring_months`, `scoring_rejections`.
Nothing in `trips_clean` moved.

**The warning — F-045, and it is the most useful thing this story measured.**
A drift metric computed over a WHOLE MONTH may not fire on the most drifted month
this program will ever hold:

| window | mean trip minutes | mean miles | trips |
|---|---:|---:|---:|
| 2019-01..03 (train) | 13.7563 | 2.9489 | 22,285,657 |
| 2020-01 | 13.2123 | 2.9378 | 6,279,806 |
| 2020-02 | 13.5707 | 2.8628 | 6,185,309 |
| **2020-03 (whole month)** | **13.1645** | 2.9204 | 2,948,237 |
| **2020-03, last 10 days** | **9.6927** | 3.1169 | 97,900 |

March 2020's monthly mean duration is **13.1645** against January's **13.2123** —
a **0.36%** move, smaller than the ordinary January→February wobble. Inside the
month the daily series runs **240,520 trips at 14.878 min on 2020-03-05** to
**5,361 trips at 9.715 min on 2020-03-29**: a 97.8% volume collapse and a 35%
shorter trip. The monthly aggregate is dominated by the ten normal days at its
head, and it averages the cliff away.

Routed to M7-S3 as a design input, deliberately NOT acted on here — the drift
window, reference and threshold are S3's to argue in the SLO-doc pattern
*before* the job runs (M7 law 4). What this measurement makes impossible is
S3 discovering it *after* choosing a window and then re-tuning a bar until the
alert agrees. The three candidate readings are in the finding.

**Volume itself is the loudest signal and it is free**: 3,007,687 raw rows
against 2020-01's 6,405,008, visible in the file size before a row is read
(44.4 MB against 93.6 MB).

**For S2**: `trips_scoring` carries the contract's 19 columns plus
`trip_duration_minutes`, so ground truth exists for every scoring month — the
error series S2 publishes are MONITORING numbers under NEW KPI ids, never
KPI-09/10 (gotcha #15, and the id law).

**Cache note (gotcha #66)**: this story commits under `src/` and `scripts/`, so
the next on-cluster run rebuilds its image and colds every cached stage. Priced
in the M7 risk table; nothing on-cluster ran here.
