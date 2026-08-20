# M7-S2 transcripts — pasted, not remembered

Every number in `docs/batch_inference_m7.md` comes from one of these. Progress
bars and MLflow artifact-download spinners are stripped; nothing else is edited.

---

## §1 — `make predictions-scoring` (the whole run)

Command: `uv run python -m taxi_mlops.training score-scoring`
Full log: `automation/runs/m7s2-batch.log`.

```
[openmp] no system libgomp.so.1; linked libgomp-e985bcbb.so.1.0.0 -> …/.venv/lib/openmp/libgomp.so.1
         and re-executing once with LD_LIBRARY_PATH set (see taxi_mlops.training.openmp)
[openmp] openmp: system libgomp.so.1
[mlflow] tracking: http://localhost:5000
[mlflow] artifacts: direct to http://localhost:9000 (server does not proxy)
[mlflow] credentials set from .env: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
[score] alias models:/nyc-taxi-eta@champion resolves to models:/m-04478c4795474ecc81756f74398dc1a3
        (F-009: load it, not the alias)
[batch] champion   : models:/nyc-taxi-eta@champion -> version 2
[batch] run        : 92b73bd4f77d4a05b92472bfcfb3cccf  (791 trees)
[batch] feature set: 'v2' (registry tag)
[batch] features   : 24 columns (matches the config)
[batch] self-check: re-scoring the test month (5,950,708 rows, 2019-08)
[batch] registry says version 2 was promoted at KPI-09 3.2403 on test; this path measures 3.2403
[batch] MATCH — the path that writes these rows reproduces the gate's number.
[data] scoring 2020-01    6,279,806 rows
[data] scoring 2020-02    6,185,309 rows
[data] scoring 2020-03    2,948,237 rows

[evaluate] every number below came from taxi_mlops.training.evaluate
[evaluate] its WINDOW is a scoring month, so its ids are KPI-14..17 —
[evaluate] KPI-09/KPI-10 belong to a held-out split and are not these.

month             rows  days  KPI-14 MAE KPI-15 <=5m %  KPI-16 bias  mean actual  mean quote
--------------------------------------------------------------------------------------------
2020-01      6,279,806    31      3.0295        83.226       0.2836      13.2123     13.4959
2020-02      6,185,309    29      2.9802        83.768      -0.1703      13.5707     13.4005
2020-03      2,948,237    31      3.3227        80.569       0.5468      13.1645     13.7113
[batch] wrote    6,279,806 rows -> data/scoring_predictions/2020-01/scoring_predictions_2020-01.parquet
[batch] wrote    6,185,309 rows -> data/scoring_predictions/2020-02/scoring_predictions_2020-02.parquet
[batch] wrote    2,948,237 rows -> data/scoring_predictions/2020-03/scoring_predictions_2020-03.parquet
[batch] wrote provenance -> data/scoring_predictions/scoring_predictions.json
[batch] next: `make duckdb` reconciles these rows, then `make marts`.
```

The self-check is the two lines in the middle. `3.2403` is the champion's own
`gate_challenger_mae` registry tag, written by the promotion gate at M3-S5;
re-measuring it here is what licenses everything below it.

---

## §2 — `make duckdb`: six reconciliations, 17 views

```
[duckdb] /home/longt/NYC-taxi-production-with-k8-flavor/data/analyst.duckdb
[duckdb] 17 view(s): data_health, ingest_months, ingest_rejections, prediction_runs,
         predictions, raw_manifest, scoring_months, scoring_predictions, scoring_rejections,
         trips_clean, trips_rejected, trips_scoring, trips_scoring_rejected, trips_test,
         trips_train, trips_val, unknown_domain_values

[duckdb] view rows vs the ingest report that wrote them
  ALL               56,127,878

[duckdb] retained rejected rows vs the per-rule counts (F-005)
  ALL             (all rules)                       914,459       914,459    yes
  80 (month, rule) pair(s) checked, 0 disagreement(s)

[duckdb] scoring months (M7): view rows vs the ingest report, and the sidecar per rule
  month     view rows     rows_out    agree
  -------  ------------  ------------  -----
  2020-01     6,279,806     6,279,806    yes
  2020-02     6,185,309     6,185,309    yes
  2020-03     2,948,237     2,948,237    yes
  ALL        15,413,352    15,413,352    yes
  30 (month, rule) pair(s) checked, 0 disagreement(s); sidecar rows 298,710 == counted 298,710

[duckdb] published predictions vs the held-out rows they claim to cover
  ALL                  12,140,456    12,140,456    yes

[duckdb] batch predictions vs the scoring rows they claim to cover (M7-S2)
  month    prediction rows      rows_out    agree
  -------  ---------------  ------------  -----
  2020-01        6,279,806     6,279,806    yes
  2020-02        6,185,309     6,185,309    yes
  2020-03        2,948,237     2,948,237    yes
  ALL           15,413,352    15,413,352    yes
[duckdb] GREEN — 8 month(s), every count reconciled: True
```

The settled numbers are unmoved: 56,127,878 clean · 914,459 sidecar ·
12,140,456 held-out predictions · 15,413,352 scoring rows.

---

## §3 — March 2020, day by day (the drift signature)

`uv run python -m taxi_mlops.data query "SELECT pickup_date, COUNT(*) AS trips,
ROUND(AVG(abs_error_minutes),4) AS kpi_14, ROUND(100*AVG(CASE WHEN
abs_error_minutes<=5 THEN 1 ELSE 0 END),3) AS kpi_15,
ROUND(AVG(signed_error_minutes),4) AS kpi_16, ROUND(AVG(actual_minutes),4) AS
mean_actual, ROUND(AVG(predicted_minutes),4) AS mean_quote FROM
scoring_predictions WHERE month='2020-03' GROUP BY 1 ORDER BY 1"`

```
┌─────────────┬────────┬────────┬────────┬─────────┬─────────────┬────────────┐
│ pickup_date │ trips  │ kpi_14 │ kpi_15 │ kpi_16  │ mean_actual │ mean_quote │
├─────────────┼────────┼────────┼────────┼─────────┼─────────────┼────────────┤
│ 2020-03-01  │ 175925 │ 2.5161 │  88.95 │  -0.039 │     12.3792 │    12.3402 │
│ 2020-03-02  │ 190103 │ 2.8922 │ 84.901 │ -0.1985 │     13.6914 │    13.4928 │
│ 2020-03-03  │ 219329 │ 3.1828 │ 81.798 │ -0.6986 │     14.3666 │     13.668 │
│ 2020-03-04  │ 225942 │ 3.0592 │ 82.629 │ -0.1442 │     14.3201 │     14.176 │
│ 2020-03-05  │ 240520 │ 3.2994 │  80.16 │  0.0879 │     14.6688 │    14.7567 │
│ 2020-03-06  │ 239720 │ 3.4291 │  79.33 │ -1.1272 │     14.8776 │    13.7504 │
│ 2020-03-07  │ 204484 │  2.769 │ 86.074 │ -0.2169 │     12.6786 │    12.4617 │
│ 2020-03-08  │ 162424 │ 3.1886 │ 87.576 │ -0.2903 │     12.6272 │    12.3369 │
│ 2020-03-09  │ 172339 │ 2.8598 │ 85.146 │  0.0369 │     13.3502 │     13.387 │
│ 2020-03-10  │ 180830 │ 3.0616 │ 82.615 │  0.3966 │     13.4267 │    13.8233 │
│     ·       │     ·  │    ·   │    ·   │     ·   │         ·   │       ·    │
│ 2020-03-22  │   9998 │ 3.9676 │ 74.805 │  2.5102 │      9.9933 │    12.5035 │
│ 2020-03-23  │  13161 │ 4.8719 │  65.39 │  3.7648 │      9.7598 │    13.5246 │
│ 2020-03-24  │  11399 │ 5.7247 │ 57.628 │  4.7558 │      9.6923 │    14.4481 │
│ 2020-03-25  │  10755 │ 6.1419 │ 54.747 │  5.1128 │      9.7434 │    14.8561 │
│ 2020-03-26  │  10329 │ 6.3693 │ 53.723 │  5.3197 │      9.6989 │    15.0185 │
│ 2020-03-27  │  11307 │ 5.9431 │ 57.009 │  4.9484 │      9.6757 │    14.6241 │
│ 2020-03-28  │   7374 │ 3.9549 │ 73.841 │  2.4557 │      9.3688 │    11.8245 │
│ 2020-03-29  │   5361 │  3.828 │ 76.031 │  2.1506 │      9.7151 │    11.8657 │
│ 2020-03-30  │   9190 │  5.284 │ 62.318 │  4.0652 │       9.571 │    13.6362 │
│ 2020-03-31  │   9026 │ 5.9596 │ 55.717 │  4.8401 │      9.5909 │     14.431 │
└─────────────┴────────┴────────┴────────┴─────────┴─────────────┴────────────┘
  31 rows (20 shown)                                                7 columns
```

The same rows in three windows:

```
┌────────────────────┬─────────┬──────────────┬────────┬────────┬────────┬─────────────┬────────────┐
│       window       │  trips  │ pct_of_month │ kpi_14 │ kpi_15 │ kpi_16 │ mean_actual │ mean_quote │
├────────────────────┼─────────┼──────────────┼────────┼────────┼────────┼─────────────┼────────────┤
│ Mar 01-10 (before) │ 2011616 │        68.23 │ 3.0463 │ 83.582 │ -0.245 │     13.7372 │    13.4922 │
│ Mar 11-21 (during) │  838721 │        28.45 │ 3.7534 │ 75.498 │ 2.0265 │     12.1963 │    14.2228 │
│ Mar 22-31 (after)  │   97900 │         3.32 │ 5.3128 │ 62.118 │ 4.1412 │      9.6927 │    13.8339 │
└────────────────────┴─────────┴──────────────┴────────┴────────┴────────┴─────────────┴────────────┘
```

And the daily extremes per month, which is the F-045 statement in one row each:

```
┌─────────┬────────┬─────────┬────────────────┬───────────────┬───────────────┬─────────────┬─────────────┐
│  month  │ n_days │  trips  │ mean_daily_mae │ min_day_trips │ max_day_trips │ min_day_mae │ max_day_mae │
├─────────┼────────┼─────────┼────────────────┼───────────────┼───────────────┼─────────────┼─────────────┤
│ 2020-01 │     31 │ 6279806 │         3.0116 │        158357 │        239177 │       2.397 │      3.5757 │
│ 2020-02 │     29 │ 6185309 │         2.9533 │        145724 │        253802 │      2.4043 │      3.3021 │
│ 2020-03 │     31 │ 2948237 │         4.1669 │          5361 │        240520 │      2.5161 │      6.3693 │
└─────────┴────────┴─────────┴────────────────┴───────────────┴───────────────┴─────────────┴─────────────┘
```

---

## §4 — `make marts`: dbt build and the publish

Full log: `automation/runs/m7s2-marts.log`.

```
Finished running 1 seed, 5 table models, 73 data tests, 1 view model in 0 hours 0 minutes and 5.53 seconds (5.53s).
Completed successfully
Done. PASS=80 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=80

== [2/2] publish to Postgres (over kubectl exec — 5432 is never published) ==
COPY 56127878
COPY 44792
COPY 8
COPY 80
COPY 1151
COPY 91
[marts]   error_segments       ~1,151 rows
[marts]   monthly_kpis         ~8 rows
[marts]   rejections_by_rule   ~80 rows
[marts]   scoring_daily        ~91 rows
[marts]   trips_clean          ~56,127,878 rows
[marts]   zone_hourly_stats    ~44,792 rows
[marts] done. Metabase (M1-S5) reads exactly these tables.
```

PASS=80, against PASS=57 at M4-S5: one model, two singular tests
(`assert_scoring_daily_grain_is_unique`, `assert_scoring_daily_reconcile`) and
the column tests on it. `COPY 91` is 31 + 29 + 31 days.

Read back **out of Postgres**, not out of the publish log — the publish
reporting a row count it just wrote is one witness, and the point of the mart is
that a BI tool can reach it:

```
$ kubectl -n platform exec postgres-0 -- psql -U postgres -d marts -c "SELECT month, count(*) AS days,
    sum(kpi_17_scored_trips) AS trips, round(avg(kpi_14_mae_min)::numeric,4) AS mean_daily_kpi14,
    round(max(kpi_14_mae_min)::numeric,4) AS worst_day_kpi14,
    round(max(kpi_16_mean_signed_error_min)::numeric,4) AS worst_day_bias,
    max(model_version) AS model_version, max(model_versions_seen) AS versions_seen
  FROM marts.scoring_daily GROUP BY month ORDER BY month;"

  month  | days |  trips  | mean_daily_kpi14 | worst_day_kpi14 | worst_day_bias | model_version | versions_seen
---------+------+---------+------------------+-----------------+----------------+---------------+---------------
 2020-01 |   31 | 6279806 |           3.0116 |          3.5757 |         1.8463 | 2             |             1
 2020-02 |   29 | 6185309 |           2.9533 |          3.3021 |         0.6741 | 2             |             1
 2020-03 |   31 | 2948237 |           4.1669 |          6.3693 |         5.3197 | 2             |             1
(3 rows)
```

6,279,806 + 6,185,309 + 2,948,237 = **15,413,352**, the ingest's own total.
`versions_seen = 1` on every month: no day's series is spliced across two models.

---

## §5 — the alias, read and unmoved; the pins, untouched

Before (at resolve time, §1): `models:/nyc-taxi-eta@champion -> version 2`.
After the whole run, the reconciliation and the publish:

```
AFTER: @champion -> 2 run 92b73bd4f77d4a05b92472bfcfb3cccf
versions: ['1', '2']

$ uv run dvc status data/processed.dvc data/rejected.dvc data/scoring.dvc data/scoring_rejected.dvc
Data and pipelines are up to date.

$ git status --porcelain
 M ledgers/findings.md
?? docs/batch_inference_m7.md
?? docs/batch_inference_m7_transcripts.md
```

No new registry version, no alias move, all four DVC pins up to date, and
`data/scoring_predictions/` does not appear in `git status` — it is gitignored,
which is the intended state and is asserted by a unit test rather than by this
paste alone.
