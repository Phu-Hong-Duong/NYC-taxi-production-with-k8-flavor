# verify-m8 transcripts (M8-S5 leg 2, 2026-08-23)

Pasted, not summarised. Both runs are on the live cluster with the champion
and the transformer up, the online store holding its materialized keys and
the feature server answering.

## 1. `make verify-m8` — GREEN

```text

[verify-m8] the M8 gate — a wall that must hold, four seams measured against
            bars argued before them, a point-in-time join proved by its own
            counterexample, and a page that is allowed to disagree with us.

== 1. the wall — Feast is quarantined, and the invariant is ASKED rather than remembered ==
  ok   uv.lock is BYTE-IDENTICAL to the m7-closed tag — five M8 stories, a feature repo, an online store, a feature server and a transformer, and the project's dependency graph did not move
  ok   `feast` is ABSENT from the project environment, asked of `uv pip list` (241 packages) and not inferred from the lock
  ok   the wall is real and measured: feast 0.66.0 declares 'pandas<3,>=1.4.3' against this project's pandas 3.0.5 — a quarantine, not a preference
  ok   and the wall is ONE package wide — the two sides differ on ['pandas'] and agree on numpy 2.5.2, pyarrow 25.0.1, python 3.12.14, which is the premise every M8 exact bar is argued from
  ok   the quarantine installs 66 EXACT pins with `--no-deps` — every line carries `==`, so the environment is a function of the reviewed file and not of a resolver's mood
  ok   every package the probe recorded is still pinned; the file gained ['hiredis', 'redis'] since — the online store's own client (ADR-012), added in sorted position rather than by regeneration
  ok   the import law holds in BOTH directions (ast, never grep): definitions.py imports feast and not taxi_mlops; feast_sources.py imports taxi_mlops and not feast
  ok   `feast` appears nowhere in pyproject.toml — there is no `uv add feast` in this repository and the milestone's premise says there never will be

== 2. the feature repo — a registry DERIVED from git, and a catalog that records its losers ==
  ok   the APPLIED registry holds exactly the 4 feature views declared in git (calendar_day_flags, od_window_stats, pu_hour_window_stats, zone_static) — two independently produced lists, not a file compared with itself
  ok   and exactly the 5 declared entities — the join keys the rest of this program already spells the same way
  ok   `feast plan` reported 4 object(s) and ZERO substantive differences — F-055's checkable statement, since the always-noisy reading (clock re-stamps) can never say 'no changes'
  ok   no registry.db is TRACKED, and the 1 generated copy/copies on disk are gitignored (asked of `git check-ignore`) — the definitions in git are the source of truth and the feature server re-applies them in its entrypoint, so a pod's registry is a function of the image's git content
  ok   every declared view carries a verdict tag in ['candidate', 'catalog-only', 'in-champion'] — {'candidate': 0, 'catalog-only': 2, 'in-champion': 2}
  ok   the catalog names every view AND records 2 CATALOG-ONLY entr(y/ies) (od_window_stats, pu_hour_window_stats) — the family every surveyed source swears by, kept in the store with the measurement that kept it out of the champion
  ok   and the losing number is labelled a SAMPLE number in the tag itself (gotcha #15) — a dropped group is never refitted, so no full-data figure for it exists to quote

== 3. the four seams — every bar EXACT, every bar argued BEFORE its record existed (law 4) ==
              offline retrieval (M8-S3): bar committed 678s before the record it judges
              online/offline (M8-S4 leg 1): bar committed 356s before the record it judges
              the HTTP feature server (M8-S4 leg 2): bar committed 320s before the record it judges
              the moved boundary (M8-S4 leg 3): bar committed 546s before the record it judges
  ok   all four seams measured EXACTLY 0.000e+00 against a bar of EXACT: offline retrieval (M8-S3) (14 cols) · online/offline (M8-S4 leg 1) (16 cols) · the HTTP feature server (M8-S4 leg 2) (6 cols) · the moved boundary (M8-S4 leg 3) (16 hazard rows)
  ok   and `one missing` is ZERO on every column of every seam that reports it (offline retrieval (M8-S3): 14, online/offline (M8-S4 leg 1): 16, the HTTP feature server (M8-S4 leg 2): 6) — the two sides agree about which values do not EXIST, which is the count a null-dropping comparison would be blind to
  ok   all 4 bar documents state EXACT in bold — the gate parsed the bar it judges against out of the prose that argues it, and typed none of them (F-017)
  ok   and all 4 bars were COMMITTED BEFORE the records they judge, checked from `git log --diff-filter=A` — M8 law 4 read off git rather than asserted in prose
  ok   2 seam reader(s) take their hazard rows from `serving.parity.HAZARDS` by import rather than by retyping (ast) — five seams, one declared row set, so a row added for one is measured by all
  ok   §9/M8's 'Show: parity table' exists at docs/feast_online_parity_table.md and names the same 100 declared pairs the record measured
  ok   every zone column's `both missing` equals the record's own two-sided no-geometry count (pu 13, do 19) — a null-dropping comparison would print the same 0.000e+00 and this is what it could not fake
  ok   and the ANCHOR block counts the same missing rows for every column it shares with the seam (11 anchored columns) — two independently built comparisons inside one record, which is why a single edited field contradicts something
  ok   and the committed table renders exactly what the record holds for all 16 columns — the third witness, and the only one a human diffs

== 4. the point-in-time proof — a DIFFERENCE with two anchors, not a sentence about a join ==
  ok   honest and naive disagree on every one of the 3 time-varying columns — od_median_duration_min: 61/76 · pu_hour_mean_speed_kmh: 53/69 · pu_hour_trips_per_day: 62/78; worst pu_hour_trips_per_day at 116.6017
  ok   the NAIVE answer IS our own full-window table (88 rows, 0 mismatches) — the leak is identified, not merely observed, which is what makes the difference in (a) attributable
  ok   and the HONEST answer reconciles with `aggregates.transform` at 0.000e+00 over 7 float column(s) — the correct side is anchored to the champion's own code, so the gate is not choosing between two unanchored joins
  ok   rows the honest join must tell NOTHING and the naive one hands a number: {'od_median_duration_min': 10, 'pu_hour_mean_speed_kmh': 8, 'pu_hour_trips_per_day': 10} — the first train month has no history, and `AggregateTables.empty()` serving NaN is the correct answer a leak overwrites
  ok   7 DISTINCT windows were served across the declared rows (2019-01, 2019-01,2019-02, 2019-01,2019-02,2019-03, 2019-01,2019-02,2019-03,2019-04, 2019-01,2019-02,2019-03,2019-04,2019…) including '(no row)' for the month with no history — an honest join is about what a row was entitled to know, not about whether the number moved
  ok   F-056's shortfall is CLASSIFIED rather than asserted away — every unanswered row is a duplicate entity key or predates the first source row, and UNEXPLAINED is 0 across 5 view(s)
  ok   the comparer RE-FITS the truth through `aggregates.fit` (ast) rather than reading back the parquet Feast reads — reconstructing the truth from the artifact under test would pass for no join at all

== 5. the live system — five questions, and the store is asked whether it holds anything ==
       [mlflow] tracking: http://localhost:5000
       [mlflow] artifacts: direct to http://localhost:9000 (server does not proxy)
       [mlflow] credentials set from .env: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
  ok   the CHAMPION answered 10.665224 minutes stamped model_version='2' — equal to what the alias resolves to, reproducing the parity record's 'ordinary-midday' row. M8 put a second service on the cluster and left this one alone
  ok   the TRANSFORMER answered 10.665224 for the same hazard from FOUR RAW FIELDS — |champion − transformer| = 0.000e+00 live, at the same model_version='2'
  ok   and X-Taxi-Lookups reports all 4 groups INCLUDING the 2 that did NOT cross the wall (airport_constant, borough_dictionary) — F-059 as a header, so a pod that fell back to its CSVs cannot pass for one that read the store
  ok   the FEATURE SERVER answered two-sidedly: a real zone got a centroid (40.758028) and TLC's non-place 264 got null — a store that answered for a non-place would be inventing a location, and one that declined a real zone would be a missing feature
  ok   the ONLINE STORE holds 57,688 keys right now — the count the materialization recorded, survived on its PVC. An empty store answers every lookup with null and nothing red anywhere, which is exactly why the gate asks
  ok   and its eviction policy is 'noeviction' (recorded off the running server) — a correctness setting, not tuning: an evicting feature store drops the key the next request asks for and answers null
  ok   every scraped predictor exporter in namespace 'serving' reads up==1 (2 target(s)) — F-043's question asked live, since a predictor does not have to die to stop reporting, it only has to be busy

== 6. F-059 as a TYPE, and the pointer nothing in M8 may touch ==
  ok   `Lookups` carries exactly ['geometry_table', 'calendar'] (ast) — F-059 as a type: there is no field a fetched borough code or airport flag could arrive in, so the wrong design is unrepresentable rather than merely untaken
  ok   and ZONE_FEATURES asks the store for ['centroid_lat', 'centroid_lon'] and nothing else — the borough encoding is a property of the whole committed table, and `is_airport` is a TOTAL function that answers for the non-places the store has no row for
  ok   the transformer refuses in three distinguishable classes — an unreachable store is 503 (ours, retryable) while an uncovered date and an unknown input are 422 (the caller's); both codes present in the module (ast)
  ok   not one of 13 M8 modules CALLS a registry-mutating verb (ast over call names, not grep) — law 3 as a structural property rather than as a report that nothing happened to be promoted

== 7. the comparison page, §9/M8's accept answered line by line, and the pointer ==
  ok   the comparison page carries 12 rows, every one with a verdict in ['ADOPT', 'DIFFER', 'SURPASS'] — {'ADOPT': 3, 'DIFFER': 4, 'SURPASS': 5}
  ok   and it is honest in both directions: 3 ADOPT and 5 SURPASS — a survey with no ADOPT is a press release
  ok   every row cites at least one of the 4 declared sources (F, G, H, I) — per-row provenance, so no claim about a community repository floats free of what was actually read
  ok   and the harvest method is stated with its limit named (F-001: WebFetch/WebSearch are off the allowlist, so the survey ran through `gh api` + `curl`) — the M1-S3 and M3-S2 idiom, third use
              §9/M8 accept-when, quoted: "v1's M7 gate AND the comparison page exists."
                              Show: "parity table + comparison"
  ok   accept answered: (i) v1's M7 gate is `make verify-m7`, a live target run separately as its own evidence — the same treatment `verify-m7` gave M6's; (ii) the comparison page exists at docs/feast_side_by_side.md; (iii) Show — the parity table at docs/feast_online_parity_table.md and the comparison page, both committed
       [mlflow] tracking: http://localhost:5000
       [mlflow] artifacts: direct to http://localhost:9000 (server does not proxy)
       [mlflow] credentials set from .env: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
  ok   NOT ONE of the 2 registry versions was created after the m7-closed tag — the strong form of law 3, because a promotion cannot hide from it: it must create a version, and a version carries its own creation time
  ok   and F-032's invariant still holds live: the served version (2) eats 'v2', which is what configs/train.yaml tells every client to build
  ok   all 5 settled DVC pins are up to date (processed, raw, rejected, scoring, scoring_rejected) — M8 read the trees and wrote none of them (law 2), and the feature store's parquet lives in its own untracked directory on `data/predictions/`'s terms
  ok   the deployments ledger carries a row for every M8 story whose records describe a deployed object (owes M8-S4; rows present: M8-S1, M8-S4) — read row by row, because the milestone's own prose names other stories

[verify-m8] GREEN — every M8 sub-check passed.
            Show: parity table   docs/feast_online_parity_table.md
                  comparison     docs/feast_side_by_side.md
                  the seams      docs/feast_pit_m8.md · feast_online_m8.md ·
                                 feast_server_m8.md · transformer_m8.md
```

exit code: **0**

## 2. `make verify-m8-redteam` — the gate goes RED, then GREEN again

```text

[verify-m8-redteam] 0. the record as it stands (restored to exactly this, whatever happens)
  automation/runs/m8-online/online_parity.json  sha256 153c4399deab…

[verify-m8-redteam] 1. rewrite ONE count: a column reports ZERO missing values — what a null-dropping comparison prints
  pu_zone.centroid_lat: both_missing 13 -> 0 — the record now says every one of the 100 declared pairs had a value on BOTH sides. UNTOUCHED: compared 100, mismatches 0, max_abs_delta 0.0, one_missing 0, verdict 'PASSED', and the headline max_abs_delta 0.0 across all 16 columns. The pass still reads as a pass; it now describes a comparison that never looked at the 13 zones with no geometry.

[verify-m8-redteam] 2. make verify-m8 — expected RED, naming the run's own no-geometry block, its anchor AND the table
[verify-m8] the M8 gate — a wall that must hold, four seams measured against
  FAIL the seam's missing counts do not reconcile with the run's own no-geometry assertion: pu_zone.centroid_lat: both_missing 0 vs 13 rows with no geometry
  FAIL the seam and its anchor disagree about which rows are missing: pu_zone.centroid_lat: seam says 0, its anchor says 13
  FAIL the table a reviewer reads and the record disagree: pu_zone.centroid_lat: the table renders '13', the record holds 0
[verify-m8] RED — 3 sub-check(s) failed.
  ok   the gate exited 1 — RED against a record whose missing counts no longer reconcile
  ok   the NO-GEOMETRY leg fired: the run asserted two-sidedly that the store declined exactly the zones our path has no geometry for, and one column now claims it saw values for all of them
  ok   the ANCHOR leg fired: the second, independently-built comparison against taxi_mlops.features counted the same rows and still says so
  ok   the PROSE leg fired: docs/feast_online_parity_table.md — the blueprint's named accept artifact — renders a number the record no longer holds
  ok   48 sub-check line(s) still passed — the gate reports everything, not the first thing
  ok   unaffected leg still green: BYTE-IDENTICAL to the m7-closed tag
  ok   unaffected leg still green: is ABSENT from the project environment
  ok   unaffected leg still green: the import law holds in BOTH directions
  ok   unaffected leg still green: COMMITTED BEFORE the records they judge
  ok   unaffected leg still green: the NAIVE answer IS our own full-window table
  ok   unaffected leg still green: answered two-sidedly
  ok   unaffected leg still green: holds 57
  ok   unaffected leg still green: carries exactly
  ok   unaffected leg still green: honest in both directions
  ok   unaffected leg still green: NOT ONE of the
  ok   the four-seam headline leg is STILL GREEN — the planted record keeps the measured delta and the verdict intact, so the gate went red on a WRONG POPULATION rather than on the fact of an edit
  ok   and the one-missing leg is still green — the plant moved the count nobody was checking, which is exactly why the three new witnesses had to exist

[verify-m8-redteam] 3. restore the record and re-run — expected GREEN again
  restored automation/runs/m8-online/online_parity.json (sha256 153c4399deab…)
  ok   automation/runs/m8-online/online_parity.json is byte-identical to what the drill found (sha256 153c4399deab…)
[verify-m8] GREEN — every M8 sub-check passed.
            Show: parity table   docs/feast_online_parity_table.md
                  comparison     docs/feast_side_by_side.md
                  the seams      docs/feast_pit_m8.md · feast_online_m8.md ·
                                 feast_server_m8.md · transformer_m8.md
  ok   the gate is GREEN again (51 sub-check line(s), exit 0) — the drill left nothing behind
  ok   git status is clean for automation/runs/m8-online/online_parity.json — the restore is byte-identical to the committed record

[verify-m8-redteam] PASSED: the M8 gate went RED on ONE rewritten missing
                    count — a column reporting zero missing values, which is
                    what a comparison that dropped nulls prints and is better
                    than the truth — named the run own no-geometry assertion,
                    its independent anchor AND the accept table a reviewer
                    diffs, left the measured delta standing, kept counting
                    every other sub-check, and returned GREEN on restore.
```

exit code: **0**
