# Batch inference as a product — the predictions table (M7-S2)

**Role block:** MLE (Accountable) · DA (Responsible). Executed 2026-08-20.
**Transcripts:** `docs/batch_inference_m7_transcripts.md` (pasted, not remembered).
**Record:** `data/scoring_predictions/scoring_predictions.json` (gitignored with
the rows it describes — see §2), `automation/runs/m7s2-batch.log`.

`@champion` is version **2** before and after. Nothing here fits a model, mints
a run, creates a version or moves a pointer.

---

## 0. What this story is, in one paragraph

`make predictions` (M2-S4) answers *what did the promoted model predict on the
months it was judged on?* — evidence for an argument that has already been had.
`make predictions-scoring` answers the question a running system asks every
month: *what is the champion saying about data nobody has judged it on?* The
output is a predictions table the DA queries like any other consumer — 15.4M
rows of parquet, a DuckDB view, and a published Postgres mart — carrying the
registry version that produced every row, plus four new monitoring KPI ids.

## 1. The check this path could not make for itself, and how it got one

M2-S4's strongest property is a refusal: the champion's registry tags say it was
promoted at KPI-09 **3.2403** on the holdout, so re-scoring it must return
3.2403 or nothing is published. **These rows have no such anchor.** No tag says
what the champion scores on 2020-03, because no gate ever asked — and the thing
that would go wrong silently is not "the number disagrees with a tag", it is
that the number was produced by a different model, or a differently-built
matrix, from the one that serves. A wrong-but-plausible MAE on a COVID month
reads exactly like drift, which is precisely what the next story is going to be
asked to believe.

So the path buys the missing check by a detour: **before it writes a single
monitoring row it re-scores the HOLDOUT month and requires the champion's own
promotion tag back.** A month with a known answer proves the loader, the feature
path and the booster; only then is a month with no known answer written.

```
[batch] self-check: re-scoring the test month (5,950,708 rows, 2019-08)
[batch] registry says version 2 was promoted at KPI-09 3.2403 on test; this path measures 3.2403
[batch] MATCH — the path that writes these rows reproduces the gate's number.
```

It costs one extra split load (~2 min of the run). The alternative is a
predictions table whose provenance stops at *a model was loaded*. The chain is
now: **registry tag → self-check → these rows → this mart**, and every link is
checked by something other than itself.

`tests/unit/test_batch_inference.py` asserts by AST that `_self_check` is called
before the first write, and that no registry-mutating verb appears in the module
at all — parsed, never grepped, because this file argues its own design in prose
(gotchas #53/#68).

## 2. Where the rows live, and the one thing that must not happen

`data/scoring_predictions/<month>/` — a **fourth** tree, not a subdirectory of
`data/predictions/`. The reason is specific rather than tidy: `data/predictions/`
is globbed by `predicted_months`, read by the `predictions` view and aggregated
by the `error_segments` mart, whose `overall` row is asserted **equal to the
evaluator's KPI-09/KPI-10** by a dbt test. A 2020 file inside it would either
turn that test red for a correct batch run or — if the shapes happened to line
up — let a board render a monitoring number under a promotion KPI's id. This is
`data/scoring/`'s argument (M7-S1, law 2) applied one layer downstream, to model
output.

Gitignored and **not** DVC-tracked, on M2-S4's terms exactly: regenerable in one
command from a DVC-pinned scoring tree plus a registry version, and a pin that
must be refreshed every time the champion moves is a pin that lives stale. The
provenance is the manifest plus the registry.

The column contract (`predictions.SCORING_PREDICTION_COLUMNS`) is a **separate
tuple**, neither a superset nor a subset of M2-S4's:

| in the scoring rows, not the settled ones | in the settled rows, not the scoring ones |
|---|---|
| `pickup_date` — the drift story is a daily one (§4) and no feature carries a calendar date | `split` — a scoring month has none; that is what makes it one |
| | `floor_predicted_minutes`, `floor_unseen_group` — see below |

**No floor, and therefore no margin.** `error_segments` carries
`kpi_13_margin_vs_floor_pct` because the gate is an argument between two
predictors and the mart must be able to re-open it. There is no such argument
here: the honest floor is fitted on the 2019 train months, and a 2020 margin
against it would publish a comparison no gate ever made, against a bar chosen
for a different world. *Is the model rotting or is the world different?* is a
real question and it is **M7-S3's**, with its own declared reference — not a
column smuggled in here. Nine geometry and calendar features are also absent:
they are a pure function of two identity columns, and the first thing a stored
derivation does is rot.

## 3. What was run, and what it measured

`make predictions-scoring` → **15,413,352 rows across 2020-01..03**, one file
per month, one manifest. Every number below came from
`taxi_mlops.training.evaluate` — the one metric source (gotcha #15) — over a new
window, and therefore under new ids (`docs/kpi_definitions.md`: KPI-14 MAE,
KPI-15 within-tolerance, KPI-16 signed bias, KPI-17 volume).

| month | rows | days | KPI-14 MAE | KPI-15 ≤5 min | KPI-16 bias | mean actual | mean quote |
|---|---|---|---|---|---|---|---|
| 2020-01 | 6,279,806 | 31 | 3.0295 | 83.226% | +0.2836 | 13.2123 | 13.4959 |
| 2020-02 | 6,185,309 | 29 | 2.9802 | 83.768% | −0.1703 | 13.5707 | 13.4005 |
| 2020-03 | 2,948,237 | 31 | **3.3227** | **80.569%** | **+0.5468** | 13.1645 | 13.7113 |

For scale, and deliberately not as a comparison the gate would recognise: the
champion's KPI-09 on the 2019-08 holdout is **3.2403**. These are different
windows and different ids; what the row above says is that on a monthly average
the champion looks *ordinary* in March 2020.

## 4. The finding: the monthly row hides the month

**F-045 was measured on the input side at M7-S1** — 2020-03's mean trip duration
is 13.1645 against 2020-01's 13.2123, a 0.36% move, *smaller than the ordinary
Jan→Feb wobble*. This story measured the same mechanism on the **output** side,
and it is worse there, because a row-weighted average is weighted by exactly the
rows that vanished.

March 2020, split at the collapse:

| window | trips | share of month | KPI-14 | KPI-15 | KPI-16 | mean actual | mean quote |
|---|---|---|---|---|---|---|---|
| Mar 01–10 (before) | 2,011,616 | **68.23%** | 3.0463 | 83.582% | −0.245 | 13.7372 | 13.4922 |
| Mar 11–21 (during) | 838,721 | 28.45% | 3.7534 | 75.498% | +2.0265 | 12.1963 | 14.2228 |
| Mar 22–31 (after) | 97,900 | **3.32%** | **5.3128** | **62.118%** | **+4.1412** | 9.6927 | 13.8339 |

**Sixty-eight percent of March 2020 is January.** The ten days that broke are
3.32% of the month's rows, so a monthly aggregate averages a 75%-worse error
into invisibility — 3.3227 for the month against 5.3128 for the days that
matter. At day grain the worst day is **6.3693** (2020-03-26, 10,329 trips),
against a worst day of 3.5757 in January and 3.3021 in February; the *unweighted*
mean of March's daily MAEs is 4.1669 against January's 3.0116.

**KPI-16 is the column that says which thing broke.** Mean actual duration falls
to 9.69 minutes in the last ten days — an empty city, faster trips — while the
champion keeps quoting 13.83, because it learned a congested January. The bias
goes from ≈0 to **+4.14 minutes of systematic over-quoting**, and on the worst
day **+5.32**. An absolute error cannot tell a model quoting three minutes too
long from one quoting three minutes too short, and in a month where the traffic
vanished those are opposite diagnoses. Here the diagnosis is unambiguous and it
is not *the model got worse*: it is *the world changed and the model did not
follow*.

**This is a measurement, not a threshold.** M7 law 4 reserves the drift window,
the reference and the bar for S3, argued before the job runs — and choosing any
of the three from the numbers just measured is the same error one level up. What
S3 inherits is the shape: a monthly window can average this event away, a daily
one cannot, and the volume series (KPI-17) moves first and largest.

## 5. Counts reconcile ingest → predictions → mart, in three places

`make duckdb` now runs **six** reconciliations over **17 views** and exits 1 on
any of them. The sixth is this story's:

```
[duckdb] batch predictions vs the scoring rows they claim to cover (M7-S2)
  month    prediction rows      rows_out    agree
  2020-01        6,279,806     6,279,806    yes
  2020-02        6,185,309     6,185,309    yes
  2020-03        2,948,237     2,948,237    yes
  ALL           15,413,352    15,413,352    yes
[duckdb] GREEN — 8 month(s), every count reconciled: True
```

The authority is the **ingest report's `rows_out`**, not the predictions file:
comparing the mart against the predictions alone would prove that SQL can sum a
column — if the batch job scored 14 of 15.4M rows, mart and predictions would
agree perfectly and both would be wrong. FULL OUTER JOIN, so a month present
only in the predictions (a mislabelled file) surfaces too.

It distinguishes two states that look alike and are not:

* **pending** — a month ingested but not yet scored. `make data-scoring` and
  `make predictions-scoring` are two commands on purpose, so this is normal and
  stays GREEN. A guard that fails on a correct system is how a guard becomes a
  formality (gotcha #50).
* **NO** — a month scored *partly*. This is the failure the check exists for,
  because half a month's rows produce a perfectly ordinary MAE over rows nobody
  chose. Red-teamed in unit form, along with a mislabelled month.

The third link travels with the mart into Postgres:
`assert_scoring_daily_reconcile` fails the build unless, for every month in the
mart, mart rows == prediction rows == the ingest report's `rows_out`. Checking it
in dbt as well as in DuckDB is not redundant — the DuckDB legs run before dbt is
invoked, and this one stops a mart rebuilt from a half-written view reaching
Postgres.

## 6. The mart, and why it is daily

`marts.scoring_daily` — one row per (month, pickup_date), 91 rows for three
months, full-refresh forever (D-003's split: the aggregates are rebuilt
wholesale because it costs under a second and makes drift between the mart and
its source impossible). `dbt build` **PASS=80** (was 57 at M4-S5), models and
tests interleaved.

Monthly numbers are a `GROUP BY month` away from these rows; the reverse is not
true, and §4 is the whole argument. Two columns exist specifically to keep the
mart honest:

* `model_versions_seen` — must be 1, asserted. M7's alias may legitimately move
  through the gate, and a day whose quotes came from two models is a spliced
  series that averaging would hide.
* `mean_actual_min` / `mean_predicted_min` — *the model got worse* and *the
  world got faster* produce the same KPI-14 and are told apart by these two.

## 7. Accept-when, clause by clause

| Clause (M7 kickoff, §M7-S2) | Verdict |
|---|---|
| the predictions table for 2020-03 exists (parquet + view + mart) | **YES** — `data/scoring_predictions/2020-03/…parquet` (2,948,237 rows) · view `scoring_predictions` (17 views) · mart `marts.scoring_daily`. 2020-01 and 2020-02 landed too |
| with the champion's version stamped | **YES** — `model_version` on every row, and `model_versions_seen = 1` asserted per day |
| the alias read-not-written | **YES** — `@champion` version 2 before and after; AST test forbids every registry-mutating verb in the module |
| counts reconcile end to end | **YES** — 15,413,352 == 15,413,352 in DuckDB (leg 6) and again in dbt against the ingest report |
| new KPI ids defined with formula/window/owner before any board cites them | **YES** — KPI-14..17 in `docs/kpi_definitions.md`, and a test fails if a published column has no definition. No board cites them yet (M7-S5's) |
| `@champion` version 2 before and after | **YES** — read at resolve time and asserted unchanged after the publish |

## 8. What S3 and S4 inherit, precisely

* **The daily series exists** — `scoring_predictions` (DuckDB) and
  `marts.scoring_daily` (Postgres, so Metabase can reach it). S3's drift job does
  not have to re-derive it.
* **The reference question is untouched and is S3's.** This story declares no
  drift reference and no threshold, deliberately (law 4). §4 is evidence about
  the *shape* of the event, not a proposed bar.
* **The batch path is a callable, and S4 wires the schedule.** Entry point:
  `taxi_mlops.training.batch.score_scoring_months(months=..., write=...)`, a
  plain function in `src/` that imports no orchestrator (the boundary law) —
  `make predictions-scoring` is its CLI. **It was host-rehearsed, not run
  on-cluster**: a Flyte stage would have to be added to `pipelines/tasks.py`,
  and this story commits under `src/`, `scripts/` and `analytics/`, so the next
  on-cluster run rebuilds its image and colds every cached stage anyway
  (gotcha #66). S4 pays that once, with the schedule.
* **The self-check is not free and S4 should know its cost.** ~2 minutes of the
  run is re-scoring the holdout. It is deliberately not optional: the whole
  value of a monitoring number is that somebody will act on it.
* **The floor is still absent from the scoring tree**, by argument (§2). If S3
  or S5 wants a "would a `GROUP BY` have done better in March 2020?" line, that
  is a new reference with its own declaration, not a column added here.
