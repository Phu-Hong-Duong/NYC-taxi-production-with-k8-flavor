# Feast, side by side — our design against the surveyed community

**M8-S5 leg 1.** BLUEPRINT §6 asks M1's prior-art survey to be *revisited for the
feature store specifically, side by side, once ours exists*. Ours exists now
(M8-S2 the quarantine and the repo, M8-S3 the point-in-time proof, M8-S4 the
online store and the feature server), so this page compares it against what the
community actually ships — one verdict per practice, honest in both directions.

It is a sibling of `docs/prior_art.md`, not a replacement: that page's row 13 is
the general Feast row from M1, and rows 1–13 there stand. This page is narrower
and deeper, and it is allowed to disagree with us.

Verdicts, unchanged from M1's protocol: **ADOPT** (they do it better — take it,
credit it) · **DIFFER** (we chose otherwise — say why, honestly) · **SURPASS**
(we do something none of them do — prove it, don't assert it).

---

## 0. Method, and four limits stated before any verdict

**Everything below was fetched and read on 2026-08-23**, not recalled.
`WebSearch`/`WebFetch` remain outside this session's permission allowlist
(**F-001**), so the harvest ran through the two tools that are on it: the
authenticated GitHub API (`gh api search/repositories`, `gh api repos/<r>`,
`gh api repos/<r>/git/trees/main?recursive=1`) for discovery, metadata and file
inventories, and `curl` against `raw.githubusercontent.com` for file contents.
**Every row cites the specific file it read.** Where a row makes a claim about
what a repository does *not* do, the evidence is a recursive tree listing — an
absence asserted from a directory listing, not from a skim.

1. **The population is tiny, and that is the finding before it is a limit.**
   Searching the GitHub API for Feast applied to this exact problem returns
   **three** substantive repositories (below) at 0★ each. A feature store on NYC
   taxi data is not a crowded field; the surveyed practice is what three careful
   individuals did, not a consensus.
2. **A SURPASS row means "none of these three does it"**, never "nobody does
   it". Each SURPASS row says so in its own reason.
3. **Code, not just READMEs, for every substantive claim.** M1's survey limited
   itself to what repositories *document*; these repositories are small enough to
   read, so the rows below cite `definitions.py`, `inference.py`,
   `feature_store.yaml` and the aggregation SQL directly. Where a row rests on a
   README sentence it says "README".
4. **We are comparing designs, not outcomes.** None of the three publishes a
   model-quality number against ours, and this page does not claim ours predicts
   better. It compares how each program *knows its feature store is correct*.

### Sources, with live API metadata (read 2026-08-23)

| key | source | what was read | metadata |
|---|---|---|---|
| **F** | [adilsaid64/feast-fare-price-prediction](https://github.com/adilsaid64/feast-fare-price-prediction) — "feast-trip-duration-prediction" | `README.md` · `feature_repo/definitions.py` · `feature_repo/feature_store.yaml` · `serving/inference.py` · `training/dataset.py` · `aggregation/location_hourly_features.py` · `pyproject.toml` · full tree | 0★, pushed **2026-08-15**, Python, 439 KB. Feast + Redis + Postgres + MLflow + FastAPI on NYC taxi **trip duration** — the closest analogue to this program that exists publicly |
| **G** | [Facco000/mlops-end-to-end-nyc-taxi](https://github.com/Facco000/mlops-end-to-end-nyc-taxi) | `feature_repo/taxi_features/feature_repo/feature_definitions.py` · `feature_store.yaml` · `feature_repo/test_workflow.py` · full tree | 0★, pushed **2026-01-06**, Jupyter, 844 KB. XGBoost + MLflow + Feast, NYC taxi trip duration |
| **H** | [airdmhund1/nyc-taxi-mlops](https://github.com/airdmhund1/nyc-taxi-mlops) | `features/feature_repo/feature_views.py` · `entities`/`services.py` · `feature_store.yaml` · full tree | 0★, pushed **2025-08-25**, Python, 853 KB. Airflow + Spark + MinIO + Feast + MLflow + FastAPI + Superset + Grafana |
| **I** | [feast-dev/feast](https://github.com/feast-dev/feast) | repo metadata; the scaffold `feast init` emits, observed **inside G** (see row 6) | **7,225★**, pushed 2026-08-22 — the upstream project, for what its defaults are |
| — | ours | `infra/feast/feature_repo/definitions.py` · `feature_store.yaml` · `docs/feast_catalog.md` · the tracked records under `automation/runs/m8-*` | this repository at `12ef731` |

**Same problem, confirmed:** F predicts trip duration in seconds from pickup
zone, dropoff zone, distance and hour-of-week, with Feast supplying completed-hour
zone statistics — the same target, the same entity vocabulary and very nearly the
same feature idea as our g5 family. G predicts trip duration. H builds hourly zone
demand. The comparison is like for like.

---

## 1. The verdicts

| # | Source (what was read) | Practice observed | Verdict | Reason / what we do |
|---|---|---|---|---|
| **1** | **F** — `feature_repo/definitions.py`, `training/dataset.py`, `serving/inference.py` | A **`FeatureService`** (`duration_prediction_fs`) names the feature list once in the registry. Training calls `store.get_historical_features(features=store.get_feature_service(NAME))`; serving calls `store.get_online_features(features=feature_service)`. The train path and the serve path name **the same object**, and the list itself lives in the registry rather than in either caller. **H** does the same (`services.py`, `demand_service`). | **ADOPT** | **They have a mechanism where we have a convention.** Our feature list at request time is `taxi_mlops.serving.feature_store.ZONE_FEATURES` — a Python constant in the transformer's own package, correct today and unenforceable across the wall. A `FeatureService` is exactly the shape F-013 keeps arguing for one layer up (one home for a list) and it is registered where both sides can read it. **Credit: F and H.** Honest reason it is not landed in this story: applying one changes the registry that `automation/runs/m8-feast/registry.json`, `tests/unit/test_feast_repo.py` and `make feast-plan-check` are all pinned against, and would require the feature server redeployed and M8-S4's three parity records re-measured. It is routed (§3) with that cost stated, not quietly skipped. |
| **2** | **F** — `aggregation/location_hourly_features.py`, in SQL: `DATE_TRUNC('hour', pickup_datetime) + INTERVAL '1 hour' AS event_timestamp`; README: *"timestamped at the end of each hour so the current trip cannot leak into its own features"* | **End-of-window feature timestamps.** A statistic computed over an hour is stamped at the hour's *end*, so a point-in-time join cannot hand a trip a window that contains it. | **ADOPT — and it is the one row where the community was ahead of us in writing** | This was already `docs/prior_art.md`'s M1 ADOPT and it landed at **M8-S2**: our six point-in-time windows are stamped `2019-02-01 … 2019-07-01`, each at its own window's exclusive end, and **2019-01 gets no rows at all** because it has no history. F is independent confirmation from a second author on the same dataset — and it is the **only** one of the three that does it (G's view has no window at all, row 7; H's `hourly_zone_demand` carries a `ttl` but the tree shows the stamping happens in a Spark job outside the repo's feature code). Where we go further is the *proof*, which is row 9's, not this row's. |
| **3** | **F** — `serving/inference.py`: `if any(feature_row[col] is None for col in FEAST_FEATURE_COLUMNS): raise HTTPException(status_code=404, detail=f"No online features for pulocationid={...}")` | **The request is REFUSED when the online store has no row for the entity.** A missing feature is a 404 with the entity named, never a default and never a silent NaN. | **ADOPT the principle · DIFFER on the mechanism — and this row names an open residual of ours** | The principle is right and we say so in three documents already: a store that answers `null` produces a confident wrong number with nothing red anywhere (ADR-012's named failure mode; `docs/transformer_m8.md` §6). **A blanket copy of their check would be wrong here and the difference is real**: zones **264/265** are TLC's "Unknown", they legitimately have **no row**, `null` *is* the correct answer for them, and ~1% of every split is in that class (DR-04 condition 1). F's entity is a pickup zone whose lagged statistic exists for every real zone, so for them `None` can only mean *no data*; for us it is two different facts wearing one value. What we have instead: `Lookups.sources` travels back on the `X-Taxi-Lookups` response header, so a caller can see the store was consulted — but **there is still no alert on an empty or stale online store**, which is the residual M8-S4 legs 1, 2 and 3 each restated and none closed. F's row is the community's answer to the half of it that *is* per-request, and it belongs to whichever story puts a reader in front of that store. Routed in §3. |
| **4** | **F** — `serving/inference.py`, `_log_step` 1..7: the request, the entity rows, the resolved feature service, the raw Redis response, the merged model row **labelled by origin** (`from_redis` / `from_request` / `from_clock`), the model frame's shape and columns, the prediction with its model URI | **The enriched request is traced end to end, and every value is labelled with where it came from.** | **DIFFER — and theirs is better at what a log is for** | We answer the same question with `X-Taxi-Lookups`, which reports all four lookup groups **including the two that deliberately did not cross the wall** (F-059: borough and the airport constant are computed, not fetched). The trade is explicit: ours is a *machine-checkable* artifact — `make transformer-accept` and `make transformer-parity` both assert it on the same response they read the number from, so a pod that silently fell back to its committed CSVs fails a check rather than being noticed by a human reading a log. Theirs is *richer for a human debugging one request*: origin labels per value, the resolved feature list, the raw store response. Neither subsumes the other, and the honest sentence is that F's trace would have told a debugger more, faster, about any of the three defects M8-S4 hit. |
| **5** | **F** — `ttl=timedelta(hours=3)`; **H** — `ttl=timedelta(days=7)` | Every feature view carries a **TTL**, bounding how stale an online lookup may be. | **DIFFER, and the reason is semantic rather than a default we never set** | All four of our views are `ttl=None`, argued in `definitions.py` at each one. For `zone_static`: a centroid is not a measurement that goes stale — the table changes when TLC redraws the zones, which is a new artifact with a new sha256, not an expiry. For the window aggregates: a window is *the best available knowledge until a later window supersedes it*, so a 2019-07 val row and a 2019-08 test row must both be served the window stamped `2019-07-01` — which is exactly what `aggregates.transform` serves them, and **a TTL would make the store disagree with the fitted model as the gap widened** (M8-S3 measured that agreement at `0.000e+00`; a TTL would have made it a function of the clock). Honest cost of our choice, which F's TTL does buy them: **nothing in our store expires**, so a materialization that stops running leaves plausible values in place forever. Our answer is at a different layer (A-10/A-11's freshness and absence rules on the drift surface) and it does **not** yet cover the online store — the same residual as row 3. |
| **6** | **G** — `feature_repo/taxi_features/data/registry.db` and `data/online_store.db` are **committed blobs** in the tree; **H** — `features/feature_repo/data/registry.db` likewise, with `registry: data/registry.db` in `feature_store.yaml`. **F** does not: its registry path is `${FEAST_REGISTRY_PATH}` (MinIO) | The applied Feast registry is a **binary file in git**, beside the Python that defines it. | **SURPASS** (over G and H; F is level with us on the storage and behind on the check) | Our `registry.db` is **gitignored and generated** — `definitions.py` is the source of truth, and the feature server runs `feast apply` in its **entrypoint at every start**, so a pod's registry is a function of the image's git content rather than of whatever a laptop had applied the day it was built. A committed registry is precisely the second home **F-013** has now been invoked to delete three times, with the aggravation that it is a binary: an inconsistency between it and the `.py` beside it produces no reviewable diff. What makes ours a SURPASS rather than a preference is that the agreement is **checked**: `make feast-plan-check` reads the applied registry back and requires every reported difference against git to be **clock-only**. That check exists because of **F-055** — `feast plan` re-stamps `DataSource.meta` at import, so it can *never* report "no changes", and an always-noisy reading looks like diligence. Red-teamed live: one renamed field made it FAIL naming the view while the other three still read clock-only. |
| **7** | **G** — `feature_definitions.py`: `trip = Entity(name="trip_id", join_keys=["trip_id"], description="Unique trip identifier")`, and the view's schema includes `fare_amount`, `trip_distance`, `passenger_count`, pickup/dropoff lat-lon, with `ttl=None` | The feature view is keyed on the **prediction's own unique id**, and its schema carries **post-trip columns**. | **SURPASS**, stated as a design property and not as a criticism of a learning repository | Two structural facts, both checkable from the file. **(a)** A point-in-time join keyed on a unique trip id can only ever return that trip's own row, so the store cannot express *what was knowable before this trip*, which is the guarantee a feature store exists to make. Our entities are the things that *outlive* a request — zone, OD pair, (zone, hour), calendar day — which is what makes M8-S3's honest-vs-naive comparison (row 9) a question with two possible answers. **(b)** `fare_amount` is unknown at quote time. This program refuses that class in a **type**: `taxi_mlops.features.quote_time.EXCLUSIONS` names **18** refused columns with a reason and a ledger row each, `FeatureLeakageError` refuses a matrix *or a config* that re-admits one, and the registry deliberately also excludes the three money columns F-007 did not list. G's model may well be predicting duration partly from fare. Not one of the three surveyed repositories carries a leakage guard of any kind. |
| **8** | **All three** — full recursive tree listings, read 2026-08-23. **F**: no test file of any kind. **G**: one, `feature_repo/test_workflow.py`, which is Feast's own `feast init` scaffold left unmodified — it operates on `driver_id: 1001` and `driver_stats.parquet`, prints its steps and **asserts nothing**. **H**: one, `tests/smoke/test_api_health.py` | **No repository ships an assertion that its point-in-time join is point-in-time correct.** F performs the join correctly (`training/dataset.py` passes a real `event_timestamp` per row) — nothing checks that it stays correct. | **SURPASS** — and this is the row the whole milestone was for | `make feast-retrieval` runs the join **twice against the same store with one column different**: the honest pass sends each row its own timestamp; the naive pass overwrites every timestamp with the instant the last window closed. They differ on **61 of 76** OD rows (max **8.2000** min), 53/69 speeds and 62/78 rates; **10 rows the honest join must tell nothing** (2019-01, the first train month, which has no history) are handed a number by the naive one; and all six month-boundary pairs — 120 seconds apart — were served **different windows**, walking `(no row) → 2019-01 → …,02 → …,03 → …,04 → …,05 → full` while the naive column sat constant. Two clauses make it a proof rather than a demo: **the naive answer IS our own full-window table** (0 mismatches over 88 rows), so the leak is identified and not merely different, and **the honest answer reconciles with `aggregates.transform` at `0.000e+00`**, so the correct side is anchored to the code the champion is fitted through. Without that last clause a difference would only prove that two joins disagree. Sample of three: a fourth repository may do this. |
| **9** | **All three** — tree listings; no file in any repository compares an online lookup against the offline value for the same entity | **Nobody measures the online/offline seam.** Materialization is run (`feast materialize`, `materialize_incremental`) and the online result is consumed at inference; that the two agree is assumed. | **SURPASS** | `make feast-online-parity` compares **100 declared pairs across 16 columns** and measures **`max |online − offline| = 0.000e+00` against a bar of EXACT** — with **`one missing` ZERO on every column**, which is the load-bearing count: the two sides agree about *which rows have no value at all*, not merely about the values. The bar was argued for that specific path (protobuf `double` is fixed-width; the entity-key serialization is pinned at version 3; `materialize` selects rather than aggregates) and **committed at `3777e71` before the comparison ran**. It is anchored — the seven static columns are additionally compared against `taxi_mlops.features.zones`/`.calendar`, the champion's own lookup, because two Feast reads agreeing with each other is not a measurement. And it can go **RED**: `make feast-online-parity-redteam` copies one OD pair's *real serialized bytes* onto another pair's key — the protobuf parses, the dtype is right, nothing logs anything — and the table fails at **8.727e+01** naming the column, with 26 other sub-checks still passing and a sha256-identical restore. |
| **10** | **F** — `pyproject.toml`: one project environment declaring `"feast[aws,postgres,redis]>=0.59.0"` and `"pandas>=2.3.3"` together. **G**, **H** — likewise single-environment. **Feast 0.66.0** declares `pandas<3,>=1.4.3` (read off the installed distribution's metadata, `automation/runs/m8-feast/probe.json`) | **Feast and the modelling code live in ONE Python environment.** Nobody needs a wall, because nobody in this population runs pandas 3. | **DIFFER — our wall is their non-problem, and the measurement is the row** | This project pins **pandas 3.0.5** (M1-S1) and has done since before Feast was in scope, so `uv add feast` is not a thing that can happen here: gotcha #36's shape, measured at the M8 draft and re-measured by the probe. The quarantine `.venv-feast` **is** the design (M8 law 4) — **66 exact pins** in `infra/feast/requirements-feast.txt` installed `--no-deps` (64 at M8-S2, plus `redis`/`hiredis` when the online store landed), and `scripts/feast_quarantine.sh` **aborts if `uv.lock`'s sha256 changes across its own run**, so the invariant is in the code and not in a write-up. The honest costs, both real: a second interpreter to keep reproducible, and one JSON document over a ClusterIP Service as the only thing that crosses at request time (M8-S4 leg 2's shape (i); shape (ii), a hand-rolled direct store read, was **refused with a reason** — re-implementing Feast's entity-key serialization on our side of the wall returns somebody else's row when it is subtly wrong). The measured consolation is that the wall is one package wide: **the two sides differ on `pandas` and nothing else** — numpy 2.5.2, pyarrow 25.0.1 and CPython 3.12.14 are identical on both, which is the premise M8-S3's and M8-S4's exact-bar arguments rest on. **If this project had not pinned pandas 3, F's single environment would be the better design and we would have taken it.** |
| **11** | **F**, **G**, **H** — READMEs and `definitions.py` descriptions: each lists the features it defines, with what they mean | **The catalog lists what is in the store.** | **SURPASS** | Ours records **what each entry is worth, including the entries worth nothing**. `docs/feast_catalog.md` and the views' own `tags` carry a verdict per entry — **in-champion** / **catalog-only** / **candidate** — with its measurement: `zone_static` +0.63% relative val MAE (KEEP), `calendar_day_flags` +1.77% (KEEP), and the two window views **catalog-only at −1.63%, KPI-10 −0.686 points, DROPPED**, labelled a **15%-SAMPLE** number because a dropped group is never refitted and no full-data figure exists (gotcha #15). The uncomfortable half is the point: **g5 — point-in-time aggregates, the strongest family in every source `docs/feature_dossier.md` harvested, and the family F's whole store is made of — LOST our ablation**, and the leakage red team's `+1.56%` on the month it saw against `−3.83%` on the untouched one sits beside it. A catalog that lists only winners cannot be used to argue against repeating an experiment, which is most of what a catalog is asked to do a year later. |
| **12** | **F** — `offline_store: type: postgres` (a real warehouse, aggregation pushed into SQL). **H** — `type: file` over Spark-written parquet. **G** — the `feast init` default. **Ours** — `type: file` over parquet written by `scripts/feast_sources.py` | Where the offline store lives, and who computes what goes into it. | **DIFFER, with F's choice acknowledged as stronger for their shape** | F's aggregation is an `INSERT … SELECT … ON CONFLICT DO UPDATE` inside Postgres: the offline store computes its own features and Feast reads the table. Ours is parquet under `data/feast/`, written by a producer that imports `taxi_mlops` and calls **`aggregates.fit(point_in_time=True)`** — the same function the champion's own g5 experiment ran through. That is the whole reason: **M8 law 2 forbids recomputing anything the program already owns**, and a SQL re-implementation of the window aggregates would be a second definition of a number `configs/features.yaml` exists to keep single. The cost we accept is that our offline store is files a producer must re-run, where F's is a table that updates itself. |

**Also observed, too small for a row:** H pins `entity_key_serialization_version: 2`
where F, G and we pin **3** — ours is pinned with a stated reason (a Feast upgrade
inside the quarantine must not silently change how a materialization encodes keys).
F sets `registry.cache_ttl_seconds: 60`; we set none, which matters less because
our server re-applies at start. G's tree still contains Feast's tutorial
`driver_stats.parquet` beside the taxi data.

---

## 2. Scorecard, and what it is honest to conclude

**12 rows: 2 ADOPT (one of them a principle we take with the mechanism refused
for a measured reason) · 4 DIFFER · 5 SURPASS · 1 ADOPT-confirmed** — counting
row 2 as its own kind, because "we already do this and so do they" is neither a
gap nor an edge.

What the community is better at, in one sentence each, because these are the
rows that cost something to write:

* **F's `FeatureService`** is a registered contract where our feature list is a
  Python constant on one side of a wall. That is a real gap and it is routed.
* **F refuses a request whose features are missing.** We return the number. Our
  reason for not copying the check is sound (null is a legitimate answer for ~1%
  of our rows) and it is *not* a reason for having no answer at all.
* **F's per-request trace** would have shortened three of M8-S4's debugging
  sessions.
* **F's single environment** is simply the better design for anyone who has not
  pinned pandas 3, and we would have taken it.

What we do that none of the three does, stated as properties rather than as
adjectives: **an assertion that the point-in-time join is point-in-time correct**
(row 8) · **a measurement of the online/offline seam, with a red team that can
turn it red** (row 9) · **a catalog that records which features LOST** (row 11) ·
**a generated registry whose agreement with git is checked** (row 6) · **a typed
refusal of quote-time-unknowable columns** (row 7).

The single sentence this page exists to make available to a reviewer: **all three
surveyed implementations get point-in-time correctness right by writing the join
correctly; this one gets it right and can prove it did, twice, against two
independent anchors.** That is the difference between a design and a design under
review — and on the population size, three repositories is what "the community"
means here.

---

## 3. What the survey changed (routed, not silently absorbed)

| # | Action | Owner | Why it is not in this story |
|---|---|---|---|
| **R-1** | Define a Feast **`FeatureService`** naming the champion's stored feature list, and have `taxi_mlops.serving.feature_store` request it by name instead of by column list (row 1; credit **F**, **H**). | routed to the M8 boundary / a future serving story | Applying it mutates the registry that `automation/runs/m8-feast/registry.json`, `tests/unit/test_feast_repo.py` and `make feast-plan-check` are pinned against, and the feature server would need a redeploy and M8-S4's three parity records a re-measurement. That is a story, not a paragraph, and M8-S5's chartered scope is this page plus the gate. |
| **R-2** | **An alert on an empty or stale online store** — the residual M8-S4 legs 1, 2 and 3 each restated and none closed, now with the community's per-request half attached (row 3; credit **F**) and its TTL half named (row 5). | routed to the M8 boundary; it belongs to the story that puts a reader in front of the store | It is a new monitored signal with a threshold, and a threshold argued in the same session that first measures the thing it watches is the pattern M8 law 4 exists to forbid. It needs its own headroom leg. |
| **R-3** | Consider a **per-request lookup trace** richer than the `X-Taxi-Lookups` header — origin labels per value, in the transformer's log (row 4; credit **F**). | noted, unscheduled | Craft-level, no correctness claim rides on it, and the machine-checkable half already exists. Recorded so the idea is not lost rather than proposed as work. |

None of the three opens a fork: R-1 and R-3 are additive craft, and R-2 is a
monitoring story whose shape is already named in `docs/transformer_m8.md` §6 and
ADR-012. Nothing here contradicts a decision already recorded.
