# M7-S1 transcripts — pasted, not remembered

Every block below is the literal stdout of the command named above it, captured
during the M7-S1 session on 2026-08-20. `docs/scoring_months_m7.md` argues about
these numbers; this file is where they came from.

The ingest transcript in §1 is the SECOND run of the day. That is deliberate:
the first run produced the tree, and re-running the whole command afterwards left
`dvc status data/scoring.dvc data/scoring_rejected.dvc` reading `Data and
pipelines are up to date.` — the byte-identity property M1-S2 proved for the
settled months, holding for the new tree at no extra cost.


## §1 · `make ingest-scoring` — the three months through the ONE contract

```
uv run python -m taxi_mlops.data ingest --scoring
[ingest] 3 month(s): 2020-01, 2020-02, 2020-03
[ingest] manifest: /home/longt/NYC-taxi-production-with-k8-flavor/data/raw_manifest.json

=== 2020-01 (scoring) ===
  raw: yellow_tripdata_2020-01.parquet [present] 93,562,858 bytes
  sha256: 0c32c1d5ef0d37ac3ff1a3f1880f247cc40165edf18626e5a86866296a4a5b93
  SCHEMA EVENT: column 'airport_fee' present ahead of its from_year -- accepted, typed, unused
  dtypes after THE cast (contract.cast, the only cast in the codebase):
  column                 dtype           nulls
  ---------------------  --------------  -----
  VendorID               Int64           0
  tpep_pickup_datetime   datetime64[us]  0
  tpep_dropoff_datetime  datetime64[us]  0
  passenger_count        Int64           65441
  trip_distance          float64         0
  RatecodeID             Int64           65441
  store_and_fwd_flag     str             65441
  PULocationID           Int64           0
  DOLocationID           Int64           0
  payment_type           Int64           0
  fare_amount            float64         0
  extra                  float64         0
  mta_tax                float64         0
  tip_amount             float64         0
  tolls_amount           float64         0
  improvement_surcharge  float64         0
  total_amount           float64         0
  congestion_surcharge   float64         65441
  airport_fee            float64         6405008
  rejections (first-violated rule attributed; matched = independent hits):
  rule                          rejected_by       pct   matched
  ----------------------------  -----------  --------  --------
  missing_timestamp                       0    0.000%         0
  duration_non_positive               4,406    0.069%     4,406
  duration_below_min                 64,166    1.002%    68,572
  duration_above_max                 14,193    0.222%    14,193
  pickup_outside_month                  178    0.003%       212
  distance_non_positive              27,341    0.427%    70,200
  distance_above_max                     10    0.000%        21
  fare_negative                      14,908    0.233%    19,505
  location_out_of_range                   0    0.000%         0
  passenger_count_out_of_range            0    0.000%         0
  ----------------------------  -----------  --------  --------
  TOTAL                             125,202    1.955%
  rows in 6,405,008 -> rows out 6,279,806
  wrote data/scoring/2020-01/yellow_tripdata_2020-01.parquet
  wrote yellow_tripdata_2020-01.rejections.json
  wrote data/scoring_rejected/2020-01/yellow_tripdata_2020-01.parquet (125,202 rejected row(s) retained)

=== 2020-02 (scoring) ===
  raw: yellow_tripdata_2020-02.parquet [present] 92,134,881 bytes
  sha256: e57df0e7c410c02d78cd59a31394a118f3d92c50560a2d8fa3a2bf5e17dcffaa
  SCHEMA EVENT: column 'airport_fee' present ahead of its from_year -- accepted, typed, unused
  rejections (first-violated rule attributed; matched = independent hits):
  rule                          rejected_by       pct   matched
  ----------------------------  -----------  --------  --------
  missing_timestamp                       0    0.000%         0
  duration_non_positive               3,975    0.063%     3,975
  duration_below_min                 60,524    0.961%    64,499
  duration_above_max                 13,249    0.210%    13,249
  pickup_outside_month                  276    0.004%       303
  distance_non_positive              20,466    0.325%    60,485
  distance_above_max                      6    0.000%        24
  fare_negative                      15,562    0.247%    20,007
  location_out_of_range                   0    0.000%         0
  passenger_count_out_of_range            0    0.000%         0
  ----------------------------  -----------  --------  --------
  TOTAL                             114,058    1.811%
  rows in 6,299,367 -> rows out 6,185,309
  wrote data/scoring/2020-02/yellow_tripdata_2020-02.parquet
  wrote yellow_tripdata_2020-02.rejections.json
  wrote data/scoring_rejected/2020-02/yellow_tripdata_2020-02.parquet (114,058 rejected row(s) retained)

=== 2020-03 (scoring) ===
  raw: yellow_tripdata_2020-03.parquet [present] 44,442,590 bytes
  sha256: 6fa1343946bc1e3702fc351ff9818787cc40e4cf2b095d947ff5e452b5b42f84
  SCHEMA EVENT: column 'airport_fee' present ahead of its from_year -- accepted, typed, unused
  rejections (first-violated rule attributed; matched = independent hits):
  rule                          rejected_by       pct   matched
  ----------------------------  -----------  --------  --------
  missing_timestamp                       0    0.000%         0
  duration_non_positive               2,131    0.071%     2,131
  duration_below_min                 29,844    0.992%    31,975
  duration_above_max                  6,182    0.206%     6,182
  pickup_outside_month                  402    0.013%       426
  distance_non_positive              12,232    0.407%    31,396
  distance_above_max                     11    0.000%        28
  fare_negative                       8,648    0.288%    11,034
  location_out_of_range                   0    0.000%         0
  passenger_count_out_of_range            0    0.000%         0
  ----------------------------  -----------  --------  --------
  TOTAL                              59,450    1.977%
  rows in 3,007,687 -> rows out 2,948,237
  wrote data/scoring/2020-03/yellow_tripdata_2020-03.parquet
  wrote yellow_tripdata_2020-03.rejections.json
  wrote data/scoring_rejected/2020-03/yellow_tripdata_2020-03.parquet (59,450 rejected row(s) retained)

[ingest] per-month summary
  month     rows_in       rows_out    rejected      pct
  -------  ------------  ------------  ----------  -------
  2020-01     6,405,008     6,279,806     125,202   1.955%
  2020-02     6,299,367     6,185,309     114,058   1.811%
  2020-03     3,007,687     2,948,237      59,450   1.977%
  -------  ------------  ------------  ----------  -------
  ALL        15,712,062    15,413,352     298,710   1.901%
[ingest] GREEN — 3 month(s) ingested, contract enforced, drops counted.
```

## §2 · `make duckdb` — 16 views, five reconciliations

```
uv run python -m taxi_mlops.data duckdb
[duckdb] /home/longt/NYC-taxi-production-with-k8-flavor/data/analyst.duckdb
[duckdb] 16 view(s): data_health, ingest_months, ingest_rejections, prediction_runs, predictions, raw_manifest, scoring_months, scoring_rejections, trips_clean, trips_rejected, trips_scoring, trips_scoring_rejected, trips_test, trips_train, trips_val, unknown_domain_values

[duckdb] view rows vs the ingest report that wrote them
  split  month     view rows     rows_out    agree
  -----  -------  ------------  ------------  -----
  train  2019-01     7,584,656     7,584,656    yes
  train  2019-02     6,947,080     6,947,080    yes
  train  2019-03     7,753,921     7,753,921    yes
  train  2019-04     7,369,167     7,369,167    yes
  train  2019-05     7,481,898     7,481,898    yes
  train  2019-06     6,850,700     6,850,700    yes
  val    2019-07     6,189,748     6,189,748    yes
  test   2019-08     5,950,708     5,950,708    yes
  ALL               56,127,878

[duckdb] retained rejected rows vs the per-rule counts (F-005)
  split  month    rule                            sidecar   rejected_by  agree
  -----  -------  ----------------------------  -----------  ------------  -----
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
  split  month    prediction rows      rows_out    agree
  -----  -------  ---------------  ------------  -----
  val    2019-07        6,189,748     6,189,748    yes
  test   2019-08        5,950,708     5,950,708    yes
  ALL                  12,140,456    12,140,456    yes
[duckdb] GREEN — 8 month(s), every count reconciled: True
```

## §3 · `make contract-probe PROBE_ARGS="--month 2025-01"` — the measurement

```
[probe] month 2025-01 (contract year 2025)
[probe] acquisition dir data/probe/ — data/raw and its manifest are untouched
[probe] raw: yellow_tripdata_2025-01.parquet [present] 59,158,238 bytes
[probe] sha256: 9af277e4c0d3f9deb30644da822981e1e7df6af58313170fd3aa8a474485488a
[probe] 3,475,226 row(s), 20 column(s) as delivered:
        ['VendorID', 'tpep_pickup_datetime', 'tpep_dropoff_datetime', 'passenger_count', 'trip_distance', 'RatecodeID', 'store_and_fwd_flag', 'PULocationID', 'DOLocationID', 'payment_type', 'fare_amount', 'extra', 'mta_tax', 'tip_amount', 'tolls_amount', 'improvement_surcharge', 'total_amount', 'congestion_surcharge', 'Airport_fee', 'cbd_congestion_fee']
[probe] SCHEMA EVENT: alias applied: 'Airport_fee' -> 'airport_fee'
[probe] dtypes after THE cast (contract.cast, the only cast in the codebase):
  column                 dtype           nulls
  ---------------------  --------------  -----
  VendorID               Int64           0
  tpep_pickup_datetime   datetime64[us]  0
  tpep_dropoff_datetime  datetime64[us]  0
  passenger_count        Int64           540149
  trip_distance          float64         0
  RatecodeID             Int64           540149
  store_and_fwd_flag     str             540149
  PULocationID           Int64           0
  DOLocationID           Int64           0
  payment_type           Int64           0
  fare_amount            float64         0
  extra                  float64         0
  mta_tax                float64         0
  tip_amount             float64         0
  tolls_amount           float64         0
  improvement_surcharge  float64         0
  total_amount           float64         0
  congestion_surcharge   float64         540149
  airport_fee            float64         540149
  cbd_congestion_fee     float64         0

[probe] VALIDATED — 2025-01 passed the input contract for 2025 with 1 schema event(s). Nothing was written.
[probe] record: automation/runs/m7-s1/contract_probe_2025-01.json
```

## §4 · `make contract-probe-fixtures` — the refusal, watched three ways

```

=== fixture: drop-required (2025-01, first 200000 rows of the REAL file) ===
[probe] month 2025-01 (contract year 2025)
[probe] acquisition dir data/probe/ — data/raw and its manifest are untouched
[probe] raw: yellow_tripdata_2025-01.parquet [present] 59,158,238 bytes
[probe] sha256: 9af277e4c0d3f9deb30644da822981e1e7df6af58313170fd3aa8a474485488a
[probe] 200,000 row(s), 20 column(s) as delivered:
        ['VendorID', 'tpep_pickup_datetime', 'tpep_dropoff_datetime', 'passenger_count', 'trip_distance', 'RatecodeID', 'store_and_fwd_flag', 'PULocationID', 'DOLocationID', 'payment_type', 'fare_amount', 'extra', 'mta_tax', 'tip_amount', 'tolls_amount', 'improvement_surcharge', 'total_amount', 'congestion_surcharge', 'Airport_fee', 'cbd_congestion_fee']
[probe] FIXTURE drop-required: dropped required column 'VendorID'
        (delete a required column — the shape of TLC removing a field)

[probe] REFUSED — SchemaEventError: 2025-01: required column(s) absent from the source file: ['VendorID']. A column that vanished is an EVENT -- update the contract deliberately (if it was RENAMED, an `aliases:` entry in configs/data.yaml is the fix).
[probe] nothing was written: no processed output, no sidecar, no report.
[probe] record: automation/runs/m7-s1/contract_probe_fixture_drop-required.json
ok  exit 1 — REFUSED, as a schema break must be

=== fixture: rename-required (2025-01, first 200000 rows of the REAL file) ===
[probe] month 2025-01 (contract year 2025)
[probe] acquisition dir data/probe/ — data/raw and its manifest are untouched
[probe] raw: yellow_tripdata_2025-01.parquet [present] 59,158,238 bytes
[probe] sha256: 9af277e4c0d3f9deb30644da822981e1e7df6af58313170fd3aa8a474485488a
[probe] 200,000 row(s), 20 column(s) as delivered:
        ['VendorID', 'tpep_pickup_datetime', 'tpep_dropoff_datetime', 'passenger_count', 'trip_distance', 'RatecodeID', 'store_and_fwd_flag', 'PULocationID', 'DOLocationID', 'payment_type', 'fare_amount', 'extra', 'mta_tax', 'tip_amount', 'tolls_amount', 'improvement_surcharge', 'total_amount', 'congestion_surcharge', 'Airport_fee', 'cbd_congestion_fee']
[probe] FIXTURE rename-required: renamed required column 'VendorID' -> 'VendorID_v2'
        (rename a required column to an unknown spelling — a field that moved)

[probe] REFUSED — SchemaEventError: 2025-01: required column(s) absent from the source file: ['VendorID']. Unknown column(s) in the same file: ['VendorID_v2']. A column that vanished is an EVENT -- update the contract deliberately (if it was RENAMED, an `aliases:` entry in configs/data.yaml is the fix).
[probe] nothing was written: no processed output, no sidecar, no report.
[probe] record: automation/runs/m7-s1/contract_probe_fixture_rename-required.json
ok  exit 1 — REFUSED, as a schema break must be

=== fixture: unknown-column (2025-01, first 200000 rows of the REAL file) ===
[probe] month 2025-01 (contract year 2025)
[probe] acquisition dir data/probe/ — data/raw and its manifest are untouched
[probe] raw: yellow_tripdata_2025-01.parquet [present] 59,158,238 bytes
[probe] sha256: 9af277e4c0d3f9deb30644da822981e1e7df6af58313170fd3aa8a474485488a
[probe] 200,000 row(s), 20 column(s) as delivered:
        ['VendorID', 'tpep_pickup_datetime', 'tpep_dropoff_datetime', 'passenger_count', 'trip_distance', 'RatecodeID', 'store_and_fwd_flag', 'PULocationID', 'DOLocationID', 'payment_type', 'fare_amount', 'extra', 'mta_tax', 'tip_amount', 'tolls_amount', 'improvement_surcharge', 'total_amount', 'congestion_surcharge', 'Airport_fee', 'cbd_congestion_fee']
[probe] FIXTURE unknown-column: added unknown column 'surge_multiplier'
        (add a column no config knows — the shape of TLC adding a field)

[probe] REFUSED — SchemaEventError: 2025-01: unknown column(s) in the source file: ['surge_multiplier']. A new column is an EVENT (DE charter) -- add it to configs/data.yaml year_columns (or as an alias) before it reaches anything downstream.
[probe] nothing was written: no processed output, no sidecar, no report.
[probe] record: automation/runs/m7-s1/contract_probe_fixture_unknown-column.json
ok  exit 1 — REFUSED, as a schema break must be

ok  data/processed/ holds nothing for 2025-01
ok  data/rejected/ holds nothing for 2025-01
ok  data/scoring/ holds nothing for 2025-01
ok  data/scoring_rejected/ holds nothing for 2025-01

[fixtures] PASSED — 3 refusal shape(s) watched, exit 1 each, nothing written.
```
