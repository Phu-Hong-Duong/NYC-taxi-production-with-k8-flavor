# Feature dossier — M3-S2 (harvested live 2026-08-17)

The menu the artisan track (M3-S3) orders from, and the evidence the Design
Review argued over. Every row names where the idea came from, what it costs in
leakage risk, and what had to change because our data is shaped differently
from the data the idea was invented on.

**The verdict column is filled by M3-S3's ablation numbers, never by
enthusiasm.** Two rows already carry a verdict, and only because a number
exists: row 18 was *measured and lost* at M2-S2, and row 7 carries the
measurement this session made to resolve F-007(b). Everything else says
`pending S3`.

---

## 0. Method, and its honest limits

Harvested live on **2026-08-17** through the two tools on this session's
allowlist — `curl` against `raw.githubusercontent.com` and the authenticated
GitHub API (`gh api search/repositories`, `gh api .../git/trees`). `WebSearch`
and `WebFetch` remain off the allowlist (**F-001**), so this is M1-S3's
`docs/prior_art.md` path re-used, not a new one.

**Three limits, stated rather than glossed:**

1. **The Kaggle leaderboard could not be read, so the playbook's competition
   record is NOT independently re-verified here.** `docs/artisan_playbook.md`
   §0 states 1,257 teams and winning RMSLE 0.28976 (external data) / 0.36185
   (without), checked by ARCH on 2026-08-12. Fetched live today,
   `https://www.kaggle.com/competitions/nyc-taxi-trip-duration` returns **HTTP
   200 and 5,632 bytes of JavaScript shell** — `og:title` = "New York City Taxi
   Trip Duration", `og:description` = "Share code and data to improve ride time
   predictions", and **zero** occurrences of `1257`, `0.28976`, `0.36185` or
   even the string `RMSLE`. The leaderboard route is the same shell. So: **the
   competition's existence and identity are confirmed live; its numbers are
   not.** They are carried as ARCH's 2026-08-12 reading, attributed, and no
   number in this dossier or in M3's gate depends on them. Three attempts, then
   stopped (wall recorded in the handoff).
2. **The community record for THIS problem is 2016 data with lat/lon.** The
   competition's files carry pickup/dropoff coordinates; ours carry zone ids
   (2019+ TLC). Every spatial row below therefore has an adaptation note, and
   the adaptation is the same one each time — the zone-centroid table this
   story derived (§2).
3. **Code read, not results reproduced.** Where a row cites a repository, the
   citation is to code that is actually in the file named, read today. None of
   these solutions was re-run; their Kaggle scores are their authors' claims.

**Sources, with live metadata (read 2026-08-17):**

| key | source | what was read | live metadata |
|---|---|---|---|
| **A** | [yennanliu/NYC_Taxi_Trip_Duration](https://github.com/yennanliu/NYC_Taxi_Trip_Duration) | [`script/prepare.py`](https://github.com/yennanliu/NYC_Taxi_Trip_Duration/blob/master/script/prepare.py), [`run/submit_xgb_core_377_OSRM.py`](https://github.com/yennanliu/NYC_Taxi_Trip_Duration/blob/master/run/submit_xgb_core_377_OSRM.py) | 17★, pushed 2023-01-07; author claims **top 6%, RMSLE 0.377** |
| **B** | [Currie32/NYC-Taxi-Trip-Duration](https://github.com/Currie32/NYC-Taxi-Trip-Duration) | [`notebook.py`](https://github.com/Currie32/NYC-Taxi-Trip-Duration/blob/master/notebook.py), `README.md` | 5★, pushed 2017-07-25 (contemporaneous with the competition); author claims **top 13%** |
| **C** | [Sh-31/NYC-Taxi-Trip-Duration](https://github.com/Sh-31/NYC-Taxi-Trip-Duration) | [`prepare.py`](https://github.com/Sh-31/NYC-Taxi-Trip-Duration/blob/main/prepare.py), `README.md` | 7★, pushed 2024-09-02; the modern re-tread, links its own Kaggle notebook |
| **D** | `docs/artisan_playbook.md` (in-repo, v1.0 2026-08-12) | §0–§5 | ARCH's pre-loaded curriculum; §0's numbers are its own, see limit 1 |
| **E** | `docs/eda_report.md`, `docs/error_memo_m2.md`, `docs/kpi_definitions.md` (in-repo) | the numbers cited inline | our own measurements — the only *results* in this file |

**Live drift found, and it matters.** Source A's `load_OSRM_data()` cites the
companion dataset `https://www.kaggle.com/oscarleo/new-york-city-taxi-with-osrm`
— the OSRM road-network routes that `docs/artisan_playbook.md` §1 lesson 3
calls "the single biggest edge". Fetched today that URL returns **HTTP 404**
(generic Kaggle page, no dataset `og:title`). The playbook's bounded adaptation
— compute our own 263×263 zone matrix against a local OSRM container — is
therefore not merely the cheaper option, it is the only reachable one. It stays
the named **M9 stretch** (kickoff §"Out of scope"), and nothing in M3 depends
on it.

---

## 1. The candidates

Leakage-risk vocabulary, used strictly:

- **none** — knowable at quote time from the request alone.
- **derived** — knowable at quote time only because we ship a lookup table with
  the model; the table itself must be fit on TRAIN months (gotcha #21: the row
  must name its request-time source).
- **HIGH** — target-derived. Legal only fit on TRAIN months and keyed
  point-in-time; illegal any other way.
- **REFUSED** — cannot be a feature here at all, with the reason.

| # | Candidate | Family | Source | Rationale | Leakage risk | Adaptation note | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | `pickup_hour` | temporal | A `get_time_feature`; B; C | congestion is a clock phenomenon | none | direct | **in v1** (M2) |
| 2 | `pickup_weekday` | temporal | A; B | weekday/weekend demand differ | none | direct | **in v1** (M2) |
| 3 | cyclic hour / week-position (`sin`,`cos`) | temporal | A `get_time_cyclic` (`pickup_hour_sin/cos`, `week_delta_sin/cos`) | 23:00 and 00:00 are adjacent, integers say they are 23 apart | none | direct. **Honest caveat**: this mattered most for the neural nets in this population (B is a TF net); a boosted tree splits an integer hour into the same buckets by itself. Expect a small or zero delta and let the ablation say so | pending S3 |
| 4 | holiday · near-holiday · business-day flags | temporal | B (`pickup_holiday`, `pickup_near_holiday`, `pickup_businessday`) | a Tuesday in July ≠ July 4th; traffic collapses and airport runs spike | none — a calendar is knowable years ahead | needs a US-holiday calendar as a committed lookup (no new runtime dep for one table). NYC-specific days (parade closures, UN General Assembly) are NOT in a federal calendar — a known gap, not a silent one | pending S3 |
| 5 | rush-hour / part-of-day bucket flags | temporal | A `get_label_feature` (`hr_6_9`, `hr_10_20`, `hr_21_5`, `weekend`) | encodes the shape of the day coarsely | none | direct. Same caveat as row 3 — trees can find these cuts; the value is in *interaction* with the spatial features | pending S3 |
| 6 | `pickup_minute_of_day` | temporal | B (`pickup_minute_of_the_day`) | the 08:55 → 09:05 transition is not a step function | none | direct; strictly finer than row 1 | pending S3 |
| 7 | **zone-centroid haversine distance** | spatial | A `get_haversine_distance`; B `haversine_distance`; C `haversine_distance` — all three compute it on lat/lon | distance is the strongest single predictor of duration in every source and in our own EDA | **none** — pre-trip knowable, which is the entire point | **the F-007(b) substitute.** Sources use per-trip coordinates; we have zone ids, so the distance is between the two zone CENTROIDS (§2). Request-time source: `PULocationID`/`DOLocationID` in the request + the shipped centroid table | **measured this session** — see §3. `r` with the target **0.7873** vs the meter's 0.8068 (**97.6%** of it), on 43,439,267 train rows. Kept as a candidate on evidence; its *marginal* value over v1's features is still S3's to measure |
| 8 | zone-centroid Manhattan distance | spatial | A `get_manhattan_distance`; B `manhattan_distance` | a taxi cannot fly; the grid makes travel the sum of two legs | none | centroid-to-centroid, decomposed into its lat-leg and lon-leg | pending S3 |
| 9 | zone-centroid bearing | spatial | A `get_direction`; B `calculate_bearing` | Manhattan is anisotropic — crosstown is slower than uptown for the same distance | none | centroid-to-centroid | pending S3 |
| 10 | `log1p` of the distance features | spatial | B (`log_distance`, `log_haversine_distance`, `log_manhattan_distance`) | compresses the long right tail of distance | none | direct. Our own support: `E`/EDA measured `r` rising 0.8066 → 0.8464 for the meter distance under logs | pending S3 |
| 11 | trip mid-point (centroid of the two centroids) | spatial | A `gat_trip_center` | "which part of the city is this trip in" is not answered by either endpoint alone | none | midpoint of the two zone centroids | pending S3 |
| 12 | airport flags (JFK=132, LGA=138, EWR=1) | spatial | D §2; **E** — `docs/error_memo_m2.md` | our own error memo: airports are 8.817% of trips and carry **1.90×** the error, at **59.988%** KPI-12 | none | **better here than in the sources**: they had to *infer* airports by clustering coordinates; a zone id names them exactly. Ids confirmed against the shapefile's own `zone` field this session | **DROPPED at M3-S3** as part of **g3 spatial identity**: +0.14% relative val MAE (KPI-10 +0.030 pts) against DR-02's >=0.50% bar, 15% sample. A real improvement that does not pay a maintenance-cost bar. The reading: 132/138/1 are already IN the model as `PULocationID`/`DOLocationID` values, and 'is this zone JFK' is one categorical split a tree makes for itself — the flag told it nothing it could not already say. The error memo's 1.90x airport error is real and is NOT addressed by naming the airports; it needs a feature that knows about queues, which is M9's OSRM/wait-time territory. `docs/ablation_m3.md` §3 |
| 13 | **borough pair** | spatial | derived from the shapefile/`taxi_zone_lookup.csv` `borough` field | a coarse backoff that exists for every OD pair, including ones never seen in training | none | 7 values (incl. `EWR`, `Unknown`) → 49 pairs. **Motivated by our own numbers**: ~1.48% of held-out rows fall back for want of an OD cell, and `docs/error_memo_m2.md` §1 shows **75.4%** of the champion's entire advantage over the floor is bought on exactly those rows. This is the cheapest thing that could help there | **DROPPED at M3-S3** with the rest of **g3** (+0.14%, see row 12). Kept as a WORKING PIECE even so: `borough_pair` is built, tested and available in the transform path, because it is the only spatial descriptor defined for zones 264/265 (DR-04 condition 1) — a future set that needs an always-present coarse backoff does not have to re-derive it. It just does not earn a place in v2 on today's numbers |
| 14 | OD-pair median duration | aggregate | A `get_cluser_feature` (`avg_cluster_duration`); A `get_avg_feature` | congestion has memory; this is the single strongest aggregate family in the sources | **HIGH** — target-derived | TRAIN months only, keyed point-in-time. Our zone pair replaces their KMeans-cluster pair. **This is also the gate's own floor** (`baseline-group-median`), so as a *feature* it must beat the thing it is made of | **DROPPED at M3-S3** as part of **g5 point-in-time aggregates**, and it is the milestone's surprise: the group came in at **-1.63% val MAE, -0.686 KPI-10 points** — the only one of five that made the model WORSE. Two causes, both structural: this column is the gate's own floor (`baseline-group-median-od-fallback`) wearing a feature's clothes, and the point-in-time cutoff that makes it legal serves a train row a 1-month window and a val row a 6-month one (gotcha #43). The model early-stopped at iteration **88** against 500 for every other experiment. `docs/ablation_m3.md` §4 |
| 15 | PU-zone × hour historical mean speed | aggregate | A `avg_cluster_speed_`, `get_cluser_feature` | traffic proxy: the same OD pair is a different trip at 08:00 and 22:00 | **HIGH** — and doubly so, see §4 trap 1 | TRAIN months only, point-in-time. Requires an aggregate of a quantity (speed) that is itself illegal per-trip | **DROPPED at M3-S3** with the rest of **g5** (row 14). Built and tested: the speed aggregate is computed from the CENTROID distance, never `trip_distance`, pinned by an AST-parsing test — so §4 trap 1 is closed by construction rather than by care |
| 16 | demand counts (trips per zone per hour, rolling) | aggregate | A `trip_cluser_count` (240-min rolling, shifted −120 min); B `ride_counts` | congestion is caused by the other cars | **HIGH** for us, for a reason the sources did not have — see §4 trap 2 | TRAIN months only, and the window must close strictly BEFORE the quote instant | **DROPPED at M3-S3** with the rest of **g5** (row 14). One design note worth keeping: it is a RATE (trips / distinct days in the window), never a count, because the point-in-time window grows month by month and a raw count would encode 'how late in the training window this row is' — `month` re-entering by the back door. Pinned by a test that doubles the window and demands the same number |
| 17 | passenger-count buckets | trip | B (`no_passengers`, `one_passenger`, `few_passengers`, `many_passengers`) | 0 passengers is a data artefact, not a small group | none | v1 already carries raw `passenger_count`; this is a re-encoding, expected to be near-zero for a tree | **DROPPED at M3-S3** as **g4 trip re-encodings**: **-0.01%** relative val MAE (KPI-10 -0.017 pts). Included in the fixed group order precisely so that 'expected near-zero for a tree' would be MEASURED once instead of assumed forever, and it came back at minus one hundredth of one percent. The cheapest row in the ablation table |
| 18 | `log1p` **target** transform | target | D §1 lesson 1 — the community's **#1** lesson; A, B, C all do it | errors on durations are multiplicative | none (inverted before the MAE gate) | — | **MEASURED AND REJECTED at M2-S2**: 3.4803 val / 3.2688 test vs 3.4760 / 3.2608 raw — consistently *worse*. Our gate is **MAE in minutes** and LightGBM's `l1` objective minimises exactly that on exactly that scale; the comp's metric was RMSLE, which is MAE-in-log-space, so their lesson is a statement about *their* metric. S3 may retest it on v2 features; it starts from behind |
| 19 | circuity = driven ÷ straight-line | trip shape | D §2 | route directness | **REFUSED** | needs `trip_distance`, the meter's post-trip odometer. Usable as an EDA statistic only — measured this session at median **1.2952** (§3) — never as a feature. Recorded here so a future session finds the refusal instead of re-inventing the idea |
| 20 | OSRM road-network distance / travel time | route truth | D §1 lesson 3; A `load_OSRM_data()` | rivers, bridges and one-way grids are real; this was the biggest single edge in the competition | none (pre-trip knowable) | **the source dataset is 404 today** (§0). Bounded adaptation is a one-time 263×263 matrix against a local OSRM container | **out of M3 by kickoff scope** — named M9 stretch |
| 21 | PCA rotation of coordinates; KMeans place-clusters | spatial | A `pca_lon_lat`, `get_clustering` (40 clusters); B (`kmeans_pickup`/`kmeans_dropoff`, 15 clusters) | rotating ~30° aligns tree splits with the street grid; clustering discretizes space into "places" | none | **NOT TRANSFERABLE, and that is a finding not an omission**: TLC zones already ARE the clusters, hand-drawn by people who know the city, and they are stable across years — whereas a KMeans fit is a new random artefact per run. We inherit the *idea* through zone identity (already v1) and rows 7–13 | **refused, with reason** |

**Count: 21 candidates, 19 of them live for S3** (row 20 out of scope, row 21
refused). The §9/M3 gate leg asks for ≥10 with source + leakage note.

---

## 2. The zone-centroid table — what makes rows 7–13 possible

`data/reference/taxi_zone_centroids.csv`, 263 rows, committed, derived by
`make zones` (`scripts/derive_zone_centroids.py`) from the TLC shapefile.

| | |
|---|---|
| source | `https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip` — the same CloudFront host our trip parquet comes from |
| pinned | `data/reference/reference_manifest.json`, sha256 `f6d71191…adf17` (1,022,574 bytes) + `taxi_zone_lookup.csv` sha256 `1a99e105…c8ed` (12,331 bytes) |
| derived table | sha256 `37910367c359be3546bd3ed87cd89e84a220bf327e0ab1bfcab91795b01e3ac2`, 263 rows |
| CRS | **read from the .prj inside the zip**, never hardcoded: `NAD83 / New York Long Island (ftUS)`. Centroids are area-weighted in the projected plane (feet), then transformed to WGS84 — a centroid taken in degrees is distorted by the cos(latitude) scaling |
| coverage | zones **1–263**. TLC's `264`/`265` ("Unknown") get **no row**, deliberately: they are not places, and 264→264 is the largest single OD "route" in the data. Rows 7–13 owe them an explicit fallback at S3 — measured below |

**How it is checked** (`tests/unit/test_zone_centroids.py`, 13 tests, cluster-free):

- **A byte-identity twin**, which is the load-bearing one: the committed CSV is
  re-derived from the committed zip on every CI run and must come back byte for
  byte — `make rebuild-proof`'s argument at 263-row scale, for about a second.
- **An outside witness for the projection**: the three airport zones must land
  within 3 km of their published positions. Derived vs published — JFK **0.63
  km**, LaGuardia **0.11 km**, Newark **0.26 km**. A wrong CRS moves every
  centroid together, and nothing internal notices.
- **Two TLC files must agree**: the shapefile's `.dbf` and the separately
  published `taxi_zone_lookup.csv` agree on borough + zone name for **all 263**
  zones.
- **The derivation refuses rather than writing a wrong table** — red-teamed by
  moving a landmark's truth: exit 1, and no file written.
- **Holes subtract**: a square with its right half hollowed must have its
  centroid left of the middle, which fails if ring areas are summed unsigned.

**Red-teamed 2026-08-17** (transcript in the story PR): editing JFK's latitude
by `40.646985 → 40.647985` — **111 metres**, one digit, one row of 263 — turned
two independent legs red (the sha256 pin and the byte-identity re-derivation)
and left the other 11 green; restoring gave back sha256 `37910367…` and 13/13.
Worth writing down: that edit passes **every semantic check in the file**,
because the landmark tolerance is 3 km. Semantic checks have tolerances; byte
identity does not, and that is why the twin is the one that matters.

**Not trusted from the source**: the `.dbf` ships `Shape_Area`/`Shape_Leng`
columns carrying values like `0.00078` for a zone whose own coordinates are in
feet — i.e. computed in some other CRS and shipped anyway. Areas here are
re-derived from the geometry; a test pins that they are plausible in km².

---

## 3. Measurements made this session (the only results in this file)

Run against the DuckDB analyst layer — `trips_train` / `trips_clean`, never raw
parquet (DA refusal #2) — joined to the centroid table. Reproduce with
`uv run python -m taxi_mlops.data query "…"`; the queries are in the story PR.

**(a) Does centroid distance behave like a distance?** 41,182,160 train rows
with distinct PU/DO zones, both with geometry:

| statistic | value |
|---|---|
| `corr`(centroid straight-line km, meter driven km) | **0.9661** |
| straight-line ≤ driven (physics says it should be) | **81.662%** |
| median circuity (driven ÷ straight-line) | **1.2952** |
| p10 / p90 circuity | 0.8752 / 1.9060 |

The 18.3% where the straight line comes out *longer* is not a bug, it is the
zone granularity: two points inside one large zone can be far closer to each
other than the zones' centroids are. It is the honest cost of having ids
instead of coordinates, and it is the reason row 7's value has to be *measured*
rather than assumed.

**(b) How much of the forbidden feature's power does the legal one keep?**
43,439,267 train rows:

| predictor | `r` with `trip_duration_minutes` | in logs |
|---|---|---|
| `trip_distance` (the meter — **excluded by law**, F-007) | 0.8068 | 0.8279 |
| zone-centroid haversine (**quote-time legal**) | **0.7873** | 0.7734 |

**The substitute retains 97.6% of the meter's raw correlation.** Sanity: the
0.8068 here reproduces the EDA's independently computed 0.8066 (the tiny
difference is this join dropping the no-geometry rows), so the query is
measuring what it claims to.

**(c) What has no geometry at all?** Rows whose PU or DO is 264/265:

| split | rows | no geometry | share |
|---|---|---|---|
| train | 43,987,422 | 548,155 | **1.2462%** |
| val | 6,189,748 | 62,595 | **1.0113%** |
| test | 5,950,708 | 63,987 | **1.0753%** |

Same order of magnitude as the ~1.48% unseen-OD fallback that `docs/
error_memo_m2.md` §1 shows buys three quarters of the champion's advantage. S3
therefore owes every spatial feature an explicit unseen/absent-zone path, and
owes it a test — not a `NaN` that LightGBM will quietly route somewhere.

---

## 4. Leakage traps, restated with what the live sources actually do

`docs/artisan_playbook.md` §5 states the traps. Reading the sources today gives
them a worked example, and the example is more useful than the warning.

**Trap 1 — per-trip speed is the target wearing a mask.** Source A computes
`avg_speed_h = 3600 × distance_haversine / trip_duration` and then takes group
means of it (`avg_cluster_speed_`, `get_cluser_feature`). The *aggregate* is a
legitimate traffic proxy; the per-trip quantity it is built from is `target`
rearranged. Rows 15 and 16 are legal only as aggregates, only fit on TRAIN.

**Trap 2 — aggregates fit over everything at once.** Source A's pipeline is,
verbatim from `run/submit_xgb_core_377_OSRM.py`:

```python
df_all = pd.concat([df_train_, df_test], axis=0)   # "let model view test data when training as well"
...
df_all_ = get_cluser_feature(df_all_)   # groupby(pickup_cluster, dropoff_cluster).mean()['trip_duration']
df_all_ = get_avg_feature(df_all_)      # groupby(weekday, hour).mean()['trip_duration'], hour_avg, month_avg, ...
```

**Read precisely, because the sloppy reading is wrong.** Kaggle's test rows have
no `trip_duration`, so `.mean()` skips them and the test *labels* do not leak.
Two things do:

1. **No point-in-time constraint.** A January trip receives a group mean
   computed from the whole period, June included. Under the competition's
   *random* split that is fair — train and test are the same period. Under our
   *temporal* split it is a model reading its own future, and it is exactly the
   inflation M3-S3's red-team is required to stage and then remove.
2. **The count features genuinely use the test period.**
   `trip_cluser_count`'s 240-minute rolling count and `coord_count` are computed
   over `df_all`, and counts need no label. In a competition, test features are
   given, so this is legal. At *serving* time you cannot count trips that have
   not happened yet. Row 16's window must close strictly before the quote
   instant.

This is the clearest thing the harvest produced: **the same line of code is
correct in a competition and disqualifying in production**, and the difference
is the split, not the code. `docs/artisan_playbook.md` §4 already says
"random K-fold → temporal splits"; this is what it costs.

**Trap 3 — the odometer is not knowable at quote time.** Resolved formally at
this milestone's Design Review; see `docs/rituals/2026-08-17_design-review-m3.md`
decision **DR-04** and row 19 above. F-007 closes on it.

**Trap 4 — filter asymmetry.** Rows the contract rejects in training still
arrive as live requests. Not a feature question; it is M5's, and it is recorded
here so it is not discovered there.

---

## 5. What graduates to M8 (Feast)

Rows **14, 15, 16** are the point-in-time, train-only aggregates. Any of them
that survives S3's ablation is a **named M8 Feast candidate** — they are
precisely the features whose value depends on being served with the same
timestamp discipline they were trained with. Rows 1–13 need no feature store: a
committed lookup table plus the request is enough, which is itself an argument
for preferring them where the ablation says they are close.
