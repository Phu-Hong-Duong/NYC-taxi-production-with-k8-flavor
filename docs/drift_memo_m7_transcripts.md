# M7-S5 leg 1 — transcripts

Pasted from the session that produced `docs/drift_memo_m7.md` and
`analytics/metabase/boards/predictions_drift.json` (2026-08-20, EXECUTOR).
Nothing here is retyped; each section names the command that produced it.

`@champion` was registry version **2** throughout and was never written: leg 1
reads the analyst layer, the mart and the tracked drift records, and converges a
Metabase dashboard. It fits nothing, scores nothing and promotes nothing.

---

## §1 `uv run python scripts/drift_memo_numbers.py`

The memo's twin. Every number in `docs/drift_memo_m7.md` appears below; a
disagreement between the two is a defect in one of them.

```text

====================================================================================================
§1  the file, before a single row is read (analyst.raw_manifest)
====================================================================================================
  month        bytes    mib  pct_of_largest
-------  -----------  -----  --------------
2019-01  110,439,634  105.3            95.2
2019-03  116,017,372  110.6           100.0
2020-01   93,562,858   89.2            80.6
2020-02   92,134,881   87.9            79.4
2020-03   44,442,590   42.4            38.3

====================================================================================================
§1  rows in, rows out, and what the contract refused (analyst.scoring_months)
====================================================================================================
  month    rows_in   rows_out  rows_rejected  rejected_pct
-------  ---------  ---------  -------------  ------------
2020-01  6,405,008  6,279,806        125,202        1.9548
2020-02  6,299,367  6,185,309        114,058        1.8106
2020-03  3,007,687  2,948,237         59,450        1.9766

====================================================================================================
§1  the 2019 reference the champion was fitted and judged on (analyst.ingest_months)
====================================================================================================
split  months    rows_out  mean_rows_per_month
-----  ------  ----------  -------------------
 test       1   5,950,708            5950708.0
train       6  43,987,422            7331237.0
  val       1   6,189,748            6189748.0

====================================================================================================
§1  the daily series March 2020 — the shape the monthly row averages away
====================================================================================================
pickup_date        day    trips  mean_duration_min  mean_distance_mi           period
-----------  ---------  -------  -----------------  ----------------  ---------------
 2020-03-01     Sunday  175,925             12.379             3.232  2020-03 (01-10)
 2020-03-02     Monday  190,103             13.691              3.05  2020-03 (01-10)
 2020-03-03    Tuesday  219,329             14.367             2.776  2020-03 (01-10)
 2020-03-04  Wednesday  225,942              14.32             2.813  2020-03 (01-10)
 2020-03-05   Thursday  240,520             14.669             2.841  2020-03 (01-10)
 2020-03-06     Friday  239,720             14.878             2.698  2020-03 (01-10)
 2020-03-07   Saturday  204,484             12.679             2.702  2020-03 (01-10)
 2020-03-08     Sunday  162,424             12.627             3.213  2020-03 (01-10)
 2020-03-09     Monday  172,339              13.35             2.948  2020-03 (01-10)
 2020-03-10    Tuesday  180,830             13.427             2.752  2020-03 (01-10)
 2020-03-11  Wednesday  179,443             13.314             2.761  2020-03 (11-21)
 2020-03-12   Thursday  167,799             13.754             2.871  2020-03 (11-21)
 2020-03-13     Friday  131,883             12.698              2.91  2020-03 (11-21)
 2020-03-14   Saturday   87,574              10.42             2.938  2020-03 (11-21)
 2020-03-15     Sunday   58,245             10.581             3.485  2020-03 (11-21)
 2020-03-16     Monday   62,513             11.613             3.255  2020-03 (11-21)
 2020-03-17    Tuesday   44,500             11.115             3.193  2020-03 (11-21)
 2020-03-18  Wednesday   35,307             10.763             3.159  2020-03 (11-21)
 2020-03-19   Thursday   29,016             10.296             3.061  2020-03 (11-21)
 2020-03-20     Friday   26,789             10.245             3.075  2020-03 (11-21)
 2020-03-21   Saturday   15,652                9.9             3.317  2020-03 (11-21)
 2020-03-22     Sunday    9,998              9.993             3.603  2020-03 (22-31)
 2020-03-23     Monday   13,161               9.76             3.046  2020-03 (22-31)
 2020-03-24    Tuesday   11,399              9.692             3.115  2020-03 (22-31)
 2020-03-25  Wednesday   10,755              9.743               3.1  2020-03 (22-31)
 2020-03-26   Thursday   10,329              9.699              3.06  2020-03 (22-31)
 2020-03-27     Friday   11,307              9.676             2.999  2020-03 (22-31)
 2020-03-28   Saturday    7,374              9.369             2.989  2020-03 (22-31)
 2020-03-29     Sunday    5,361              9.715             3.289  2020-03 (22-31)
 2020-03-30     Monday    9,190              9.571             3.012  2020-03 (22-31)
 2020-03-31    Tuesday    9,026              9.591             3.027  2020-03 (22-31)

====================================================================================================
§1  the whole-month row — the number a monthly window would look at
====================================================================================================
  month      trips  mean_duration_min  mean_distance_mi
-------  ---------  -----------------  ----------------
2020-01  6,279,806            13.2123            2.9378
2020-02  6,185,309            13.5707            2.8628
2020-03  2,948,237            13.1645            2.9204

====================================================================================================
§2  the three Marches, and the two ordinary months beside them
====================================================================================================
         period      trips  pct_of_march
---------------  ---------  ------------
        2020-01  6,279,806        (null)
        2020-02  6,185,309        (null)
2020-03 (01-10)  2,011,616        68.231
2020-03 (11-21)    838,721        28.448
2020-03 (22-31)     97,900         3.321

====================================================================================================
§3  trip mix by period — what the remaining rider was buying
====================================================================================================
         period      trips  mean_duration_min  mean_distance_mi  mean_passengers  mean_fare_usd  mean_total_usd
---------------  ---------  -----------------  ----------------  ---------------  -------------  --------------
        2020-01  6,279,806            13.2123            2.9378            1.518         12.541         18.5431
        2020-02  6,185,309            13.5707            2.8628           1.5066        12.4897         18.5064
2020-03 (01-10)  2,011,616            13.7372            2.8849           1.4893        12.8437          18.813
2020-03 (11-21)    838,721            12.1963            2.9825           1.4422         12.138         17.8309
2020-03 (22-31)     97,900             9.6927            3.1169           1.3028        11.5737         16.4631

====================================================================================================
§3  the streets emptied — miles per hour, two ways
====================================================================================================
         period      trips  mph_of_the_averages  median_trip_mph
---------------  ---------  -------------------  ---------------
        2020-01  6,279,806              13.3411          10.2062
        2020-02  6,185,309              12.6573           9.8559
2020-03 (01-10)  2,011,616              12.6003           9.9574
2020-03 (11-21)    838,721              14.6727          11.5058
2020-03 (22-31)     97,900              19.2942          15.2339

====================================================================================================
§3  what the contract refused, per rule — a stable refusal profile
====================================================================================================
  month         rejection_rule  rejected
-------  ---------------------  --------
2020-01     duration_below_min    64,166
2020-01  distance_non_positive    27,341
2020-01          fare_negative    14,908
2020-01     duration_above_max    14,193
2020-01  duration_non_positive     4,406
2020-01   pickup_outside_month       178
2020-01     distance_above_max        10
2020-02     duration_below_min    60,524
2020-02  distance_non_positive    20,466
2020-02          fare_negative    15,562
2020-02     duration_above_max    13,249
2020-02  duration_non_positive     3,975
2020-02   pickup_outside_month       276
2020-02     distance_above_max         6
2020-03     duration_below_min    29,844
2020-03  distance_non_positive    12,232
2020-03          fare_negative     8,648
2020-03     duration_above_max     6,182
2020-03  duration_non_positive     2,131
2020-03   pickup_outside_month       402
2020-03     distance_above_max        11

====================================================================================================
§4  the clock: share of trips by pickup hour, January against the last ten days
====================================================================================================
pickup_hour  jan_pct  late_march_pct
-----------  -------  --------------
          0    2.635           1.387
          1    1.888           0.676
          2    1.375           0.449
          3    0.959           0.373
          4    0.725           0.527
          5    0.855            1.43
          6    1.935           4.461
          7    3.721           6.065
          8    4.727           6.117
          9    4.765           5.478
         10    4.703            5.82
         11    4.916           6.095
         12    5.351           5.991
         13    5.422           6.434
         14    5.752           7.018
         15    5.877           6.989
         16    5.577           6.697
         17    6.252           6.865
         18    6.852           6.033
         19    6.199            5.02
         20      5.5            3.57
         21    5.507           2.446
         22    4.885           2.114
         23    3.621           1.943

====================================================================================================
§5  airports as a share of the city's taxi work (JFK 132 / LGA 138 / EWR 1)
====================================================================================================
         period      trips  airport_pct  unknown_zone_pct
---------------  ---------  -----------  ----------------
        2020-01  6,279,806       7.0561            0.8484
        2020-02  6,185,309       6.5496             0.791
2020-03 (01-10)  2,011,616       6.3832            0.8014
2020-03 (11-21)    838,721       6.1168            0.8142
2020-03 (22-31)     97,900       4.4974            1.0756

====================================================================================================
§5  the same share on the 2019 splits the champion was fitted and judged on
====================================================================================================
split       trips  airport_pct
-----  ----------  -----------
 test   5,950,708       8.8175
train  43,987,422         7.36
  val   6,189,748       8.3453

====================================================================================================
§5  the airport gap, measured in a world the 2019 memo never saw (docs/error_memo_m2.md §7 row 2)
====================================================================================================
         period  airport_trips  airport_mae  ordinary_mae  gap_ratio  airport_bias_min
---------------  -------------  -----------  ------------  ---------  ----------------
        2020-01        443,107       5.6639        2.8295     2.0017            2.1939
        2020-02        405,113       5.3889        2.8114     1.9168             1.061
2020-03 (01-10)        128,406       5.3666        2.8881     1.8582            1.0394
2020-03 (11-21)         51,303       8.1382        3.4677     2.3468            5.8026
2020-03 (22-31)          4,403      10.4912        5.0689     2.0697             8.658

====================================================================================================
§6  the monitoring ids, rolled up from the daily mart (main_marts.scoring_daily)
====================================================================================================
  month  kpi_17_trips  kpi_14_mae_min  kpi_15_within_pct  kpi_16_bias_min  model_versions
-------  ------------  --------------  -----------------  ---------------  --------------
2020-01     6,279,806          3.0295             83.226           0.2836               1
2020-02     6,185,309          2.9802             83.768          -0.1703               1
2020-03     2,948,237          3.3227             80.569           0.5468               1

====================================================================================================
§6  the daily series, from the day it started moving
====================================================================================================
pickup_date        day    trips  kpi_14_mae_min  kpi_15_within_pct  kpi_16_bias_min  mean_actual_min  mean_quoted_min
-----------  ---------  -------  --------------  -----------------  ---------------  ---------------  ---------------
 2020-03-08     Sunday  162,424          3.1886             87.576          -0.2903           12.627           12.337
 2020-03-09     Monday  172,339          2.8598             85.146           0.0369            13.35           13.387
 2020-03-10    Tuesday  180,830          3.0616             82.615           0.3966           13.427           13.823
 2020-03-11  Wednesday  179,443          3.1536             81.498           0.9242           13.314           14.239
 2020-03-12   Thursday  167,799          3.4456             78.248            1.221           13.754           14.975
 2020-03-13     Friday  131,883          3.5344             77.537           1.6505           12.698           14.349
 2020-03-14   Saturday   87,574          3.4183             78.472            2.141            10.42           12.561
 2020-03-15     Sunday   58,245          3.3694             80.457           2.0459           10.581           12.627
 2020-03-16     Monday   62,513          3.9527             73.399           2.6236           11.613           14.237
 2020-03-17    Tuesday   44,500          4.8449             63.602           3.8071           11.115           14.922
 2020-03-18  Wednesday   35,307          5.4856             58.292           4.5529           10.763           15.315
 2020-03-19   Thursday   29,016          5.8571             56.259           4.9249           10.296           15.221
 2020-03-20     Friday   26,789          5.6054             58.296           4.6288           10.245           14.874
 2020-03-21   Saturday   15,652          4.2031              71.09           2.7802              9.9            12.68
 2020-03-22     Sunday    9,998          3.9676             74.805           2.5102            9.993           12.504
 2020-03-23     Monday   13,161          4.8719              65.39           3.7648             9.76           13.525
 2020-03-24    Tuesday   11,399          5.7247             57.628           4.7558            9.692           14.448
 2020-03-25  Wednesday   10,755          6.1419             54.747           5.1128            9.743           14.856
 2020-03-26   Thursday   10,329          6.3693             53.723           5.3197            9.699           15.019
 2020-03-27     Friday   11,307          5.9431             57.009           4.9484            9.676           14.624
 2020-03-28   Saturday    7,374          3.9549             73.841           2.4557            9.369           11.824
 2020-03-29     Sunday    5,361           3.828             76.031           2.1506            9.715           11.866
 2020-03-30     Monday    9,190           5.284             62.318           4.0652            9.571           13.636
 2020-03-31    Tuesday    9,026          5.9596             55.717           4.8401            9.591           14.431

====================================================================================================
§6  the best and worst days of each month, by KPI-14
====================================================================================================
  month    best_day  best_mae   worst_day  worst_mae
-------  ----------  --------  ----------  ---------
2020-01  2020-01-19     2.397  2020-01-03     3.5757
2020-02  2020-02-17    2.4043  2020-02-20     3.3021
2020-03  2020-03-01    2.5161  2020-03-26     6.3693

====================================================================================================
§6  weekday against weekend, in the collapse and in an ordinary month
====================================================================================================
         period     part      trips  mae_min
---------------  -------  ---------  -------
        2020-01  weekday  4,781,361   3.1306
        2020-01  weekend  1,498,445   2.7069
2020-03 (22-31)  weekday     75,167   5.7308
2020-03 (22-31)  weekend     22,733   3.9306

====================================================================================================
§7  what the drift job measured, read back off the tracked records
====================================================================================================
  month  current_rows  trips_per_day  volume_ratio  max_input_psi   reference  reference_rows
-------  ------------  -------------  ------------  -------------  ----------  --------------
2020-01     6,279,806       202574.4        0.8336         0.0103  train-2019      43,987,422
2020-02     6,185,309       213286.5        0.8776         0.0087  train-2019      43,987,422
2020-03     2,948,237        95104.4        0.3913         0.0217  train-2019      43,987,422

====================================================================================================
§7  per column, and the target kept separate from the inputs
====================================================================================================
  month            column_name     psi  unseen_pct
-------  ---------------------  ------  ----------
2020-01  trip_duration_minutes  0.0127         0.0
2020-01              dayofweek  0.0103         0.0
2020-01           PULocationID  0.0082         0.0
2020-01           DOLocationID  0.0082     1.6e-05
2020-01        passenger_count  0.0069         0.0
2020-01                   hour  0.0024         0.0
2020-02           PULocationID  0.0087         0.0
2020-02           DOLocationID  0.0086         0.0
2020-02  trip_duration_minutes  0.0075         0.0
2020-02              dayofweek  0.0061         0.0
2020-02        passenger_count  0.0052         0.0
2020-02                   hour  0.0015         0.0
2020-03              dayofweek  0.0217         0.0
2020-03        passenger_count  0.0171         0.0
2020-03           DOLocationID  0.0151         0.0
2020-03           PULocationID  0.0143         0.0
2020-03  trip_duration_minutes  0.0125         0.0
2020-03                   hour  0.0098         0.0

====================================================================================================
§7  the headroom leg — the two 2019 months whose verdict already exists
====================================================================================================
  month  current_rows  volume_ratio  max_input_psi
-------  ------------  ------------  -------------
2019-07     6,189,748        0.8216         0.0323
2019-08     5,950,708        0.7899         0.0137

====================================================================================================
§7  and WHICH column carried it — the size of a move is half of what it is
====================================================================================================
  month   column_name     psi
-------  ------------  ------
2019-07     dayofweek  0.0323
2019-07  PULocationID  0.0091
2019-08  PULocationID  0.0137
2019-08  DOLocationID  0.0126

Every number above is in docs/drift_memo_m7.md. A disagreement is a defect.
```

---

## §2 `make boards` — the fourth board, created

The converger is idempotent BY NAME (M1-S5): the three existing boards report
`card updated` and keep their ids, the new one reports `card created`.

```text
[boards] board 'Predictions & drift (M7)' (8 cards)
[boards]     card created: KPI-17 · trips scored per day — the collapse, and everything else is downstream of it  (KPI-17, line)
[boards]     card created: KPI-14 / KPI-15 · the monitoring headline, per month  (KPI-14, table)
[boards]     card created: KPI-14 · daily MAE — where the event actually is  (KPI-14, line)
[boards]     card created: KPI-16 · signed bias — the number that says WHICH WAY it broke  (KPI-16, line)
[boards]     card created: KPI-14 · what was quoted against what happened (2020-03)  (KPI-14, line)
[boards]     card created: KPI-15 · within-5-minutes rate, daily — the rider's view  (KPI-15, line)
[boards]     card created: KPI-14 / KPI-17 · the three Marches (and the two ordinary months beside them)  (KPI-14, table)
[boards]     card created: KPI-14 · the worst day of each month, and the best  (KPI-14, table)
[boards] ok  dashboard created: 'Predictions & drift (M7)' (id 5) — 8 cards
```

---

## §3 `uv run python scripts/metabase_boards.py --verify`

The read-only twin `make verify-m1` runs. It proves the connection, the KPI-09/10
law and ONE card per dashboard against live data.

```text
[boards] authenticated as the .env admin (instance was already set up)
  ok   Metabase holds a connection to the 'marts' warehouse
  ok   dashboard 'Data health' exists with 10 cards
  ok   dashboard 'Data health': every card queries the 'marts' warehouse
  ok   dashboard 'Data health': no card claims KPI-09/KPI-10 (gotcha #15)
  ok   dashboard 'Data health': card 'KPI-01 · trips ingested, all months' RAN and returned 1 row(s)
  ok   dashboard 'Error segments (M2)' exists with 11 cards
  ok   dashboard 'Error segments (M2)': every card queries the 'marts' warehouse
  ok   dashboard 'Error segments (M2)': no card claims KPI-09/KPI-10 (gotcha #15)
  ok   dashboard 'Error segments (M2)': card 'KPI-13 · what the booster buys, by hour of day (test)' RAN and returned 24 row(s)
  ok   dashboard 'KPI board' exists with 7 cards
  ok   dashboard 'KPI board': every card queries the 'marts' warehouse
  ok   dashboard 'KPI board': no card claims KPI-09/KPI-10 (gotcha #15)
  ok   dashboard 'KPI board': card 'KPI-08 · mean fare (windowed) by month, with exclusions' RAN and returned 8 row(s)
  ok   dashboard 'Predictions & drift (M7)' exists with 8 cards
  ok   dashboard 'Predictions & drift (M7)': every card queries the 'marts' warehouse
  ok   dashboard 'Predictions & drift (M7)': no card claims KPI-09/KPI-10 (gotcha #15)
  ok   dashboard 'Predictions & drift (M7)': card 'KPI-17 · trips scored per day — the collapse, and everything else is downstream of it' RAN and returned 91 row(s)
```

---

## §4 `make board-cards` — the other half of §3, and why it exists

`--verify` executes one card per dashboard, which is enough to prove the
connection and the credentials. It is not enough to prove the board. Gotcha #78:
a panel returning zero rows is indistinguishable from a quiet system, so green
must not be the default rendering of "no data" — M6-S1 shipped three empty
Grafana panels for three different real reasons with every scrape target green.

This runs the SQL a reviewer reads in the checked-in JSON, straight at the one
Postgres over the `make marts` transport, and **treats an empty card as a
failure**.

```text
[cards] board 'Data health' (10 cards)
  ok          1  KPI-01 · trips ingested, all months
  ok          1  KPI-01 · months in the mart
  ok          1  KPI-01 · newest month ingested
  ok          1  KPI-02 · overall rejection rate
  ok          8  KPI-01 · trips ingested per month
  ok          8  KPI-02 · rejection rate SERIES, by month
  ok         10  KPI-03 · rejections attributed per rule (every rule, including the zeroes)
  ok         80  KPI-03 · rejections per rule, by month
  ok          8  KPI-04 · undocumented-value rate (drift by VALUE)
  ok          8  KPI-05 · raw-byte provenance (sha256 per month)
[cards] board 'Error segments (M2)' (11 cards)
  ok          2  KPI-11 · the champion on each held-out split (equals the evaluator's value)
  ok          4  KPI-13 · the margin is bought on the rows the GROUP BY cannot answer
  ok          8  KPI-12 · within-5-min rate by true trip duration (test)
  ok          8  KPI-11 / KPI-13 · error and margin by true trip duration (test)
  ok         24  KPI-11 · error by hour of day (test)
  ok         24  KPI-13 · what the booster buys, by hour of day (test)
  ok         15  KPI-11 · worst pickup zones (test, >= 20,000 trips)
  ok         15  KPI-11 · worst drop-off zones (test, >= 20,000 trips)
  ok          7  KPI-12 · within-tolerance rate by day of week (test)
  ok         11  KPI-11 · error by stated party size (test)
  ok          8  KPI-13 · every segment where the GROUP BY beats the booster (test)
[cards] board 'KPI board' (7 cards)
  ok          1  KPI-06 · median trip duration, all months
  ok          1  KPI-07 · P90 trip duration, all months
  ok          1  KPI-08 · mean fare (windowed) WITH its excluded-row count
  ok          8  KPI-06 / KPI-07 · duration by month
  ok          8  KPI-08 · mean fare (windowed) by month, with exclusions
  ok         24  KPI-06 · median duration by pickup hour (the segmented view)
  ok         25  KPI-01 · busiest pickup zones (264/265 are 'unknown', not places)
[cards] board 'Predictions & drift (M7)' (8 cards)
  ok         91  KPI-17 · trips scored per day — the collapse, and everything else is downstream of it
  ok          3  KPI-14 / KPI-15 · the monitoring headline, per month
  ok         91  KPI-14 · daily MAE — where the event actually is
  ok         31  KPI-16 · signed bias — the number that says WHICH WAY it broke
  ok         31  KPI-14 · what was quoted against what happened (2020-03)
  ok         91  KPI-15 · within-5-minutes rate, daily — the rider's view
  ok          5  KPI-14 / KPI-17 · the three Marches (and the two ordinary months beside them)
  ok          3  KPI-14 · the worst day of each month, and the best

[cards] 36 card(s) executed, 0 failure(s) — an EMPTY panel is a failure (gotcha #78)
```

---

## §5 A sanity net, run once, and the thing it tells leg 2

Before the M7 gate exists, one throwaway pass asked the cheapest possible
question: **does every 3-4 decimal number in `docs/drift_memo_m7.md` appear in
the twin script's output at all?**

```text
191 3-4dp numbers in the memo, 0 not found in the script output
```

Two honest limits on that line, both of which are `make verify-m7`'s work and not
this one's:

1. **It checks presence, not placement.** A number that belongs in the airport row
   and was typed into the duration row passes this and is still wrong. The gate's
   prose-vs-record leg has to bind each claim to the query that produces it, the
   way `verify-m5` section 6 binds the runbook's numbers to the record each one
   cites.
2. **Trailing zeros had to be normalised, and the first pass reported 15 false
   misses because of it.** DuckDB's `round()` prints `1.061`; a table padded to a
   consistent width writes `1.0610`. That is gotcha #76's tokenisation problem
   arriving from the other direction - and it must be handled *without* letting a
   bare substring match through, since `13.75` rendered at zero decimals as `14`
   is exactly what let a planted value survive `verify-m6`'s first run
   (gotcha #90). The safe rule: compare at the precision the DOCUMENT wrote, with
   a floor of one decimal, and strip trailing zeros on both sides.

The throwaway was deleted rather than committed; the finding is recorded here so
leg 2 does not pay for it twice.
