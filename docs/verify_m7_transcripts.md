# `verify-m7` transcripts (M7-S5 leg 2) — pasted, not remembered

Two runs, unedited apart from ANSI colour codes. The first is `make verify-m7`
against the repository as it stands; the second is `make verify-m7-redteam`,
which rewrites ONE number in a tracked record, requires the gate to name it from
three different artifacts, requires one named leg to stay GREEN, restores the
record from a byte copy verified by sha256, and re-runs the gate.

Measured wall-clock for the gate alone: **5.328 s** (`subprocess.run` around
`scripts/verify_m7.sh`, exit 0).

---

## §1 · `make verify-m7` — GREEN, 62 sub-checks in 7 sections

```text

[verify-m7] the M7 gate — a scoring month that is not a fourth split, two
            failure signatures that must not look alike, a predictions table the DA
            queries, bars argued before the data was seen, and a retrain that said no.

== 1. the scoring months — 2020 arrived, and the settled 2019 bytes did not move ==
  ok   3 scoring month(s) ['2020-01', '2020-02', '2020-03'] are disjoint from the 8 split month(s) — a month cannot be both trained on and scored for drift, because then its drift reference would contain itself
  ok   load_config REFUSES a month that is in both lists — ValueError naming '2019-01'. A scoring month that is also a split month is the one mistake this separation makes possible, so it is checked in a type
  ok   trips_clean still returns exactly {test, train, val} — no scoring row reached the tree the program's numbers rest on (M7 law 2, asked of the rows)
  ok   the scoring views hold exactly the configured months ['2020-01', '2020-02', '2020-03'] and 15,413,352 row(s) == 15,413,352 the ingest reports claim — the reconciliation `make duckdb` exits 1 on, re-asked here without rebuilding it
  ok   data/processed.dvc and data/rejected.dvc are unmodified in git while the scoring trees carry their OWN pins (data/scoring.dvc, data/scoring_rejected.dvc) — new artifacts beside the settled ones, never inside them
  ok   the REAL 2025-01 file came back VALIDATED (exit 0, 3,475,226 rows, 20 columns, 1 schema event(s)) and the probe acquired NOTHING — no entry for its year in data/raw_manifest.json. A structural verdict, measured rather than assumed, and a SURPASS over the blueprint's premise that a future year would refuse
  ok   3 refusal shapes on the record (drop-required, rename-required, unknown-column) — every one SchemaEventError, REFUSED, exit 1, and ['2025-01'] appears in NO ingest or scoring month. The exit code is the assertion; the absence is the signature
  ok   3 legacy path accessor(s) still RAISE for a scoring month — every existing caller means the settled trees, and none of them silently learned a new destination

== 2. the two failure signatures — DISTINGUISHABLE from the records, not from a table ==
  ok   statistical drift (2020-03): contract passed, exit 0, 2,948,237 rows written, and a drift record exists for the month — there is something to compare, and it moved
  ok   schema drift (fixtures): SchemaEventError, exit 1, ZERO rows written — no output, no sidecar, no report, and therefore NO DRIFT METRIC AT ALL. That last clause is the dangerous one: a drift board showing 'no alert' looks identical to a healthy month
  ok   the two signatures differ in all 4 discriminating fields (drift_metric, exit_code, report_exists, rows_written) — this is §9/M7's 'Show', asserted as a difference between record shapes rather than as a sentence in a table
  ok   exactly 3 drift record(s) exist, one per configured scoring month ['2020-01', '2020-02', '2020-03'] — the absence a refused month produces is countable, because the present ones are
  ok   the absence has exactly one guard and it exists: DriftMetricsStale — a schema refusal produces no metric, so the only signal that a month SHOULD have been compared and was not is staleness. Slow, and honest about being slow
  ok   both write-ups tabulate the pair and quote the record's own row count (2,948,237) beside the refusal — docs/scoring_months_m7.md, docs/drift_detection_m7.md

== 3. batch inference as a product — the table the DA queries, and its three-way reconciliation ==
       [mlflow] tracking: http://localhost:5000
       [mlflow] artifacts: direct to http://localhost:9000 (server does not proxy)
       [mlflow] credentials set from .env: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
  ok   every published row is stamped with version 2, which is what @champion resolves to RIGHT NOW (run 92b73bd4f77d…) — resolved by alias, never by `source` (F-009's two hops)
  ok   the path proved itself on a month with a KNOWN answer before writing one with none: re-scoring the test split (5,950,708 rows) measured 3.2403 against the champion's own gate_challenger_mae tag of 3.2403 — read off the registry, not off the manifest that claims it
  ok   ingest -> predictions -> mart reconcile for every month, 15,413,352 rows across 3 month(s) — three systems (DuckDB, a manifest file, Postgres), and the AUTHORITY is the ingest report: a job that scored 14 of 15.4M rows would have the other two agreeing and both wrong
  ok   model_versions_seen is 1 on every month of the mart (2020-01, 2020-02, 2020-03) — M7's alias may legitimately move through the gate, and a spliced series would average two champions into invisibility
  ok   the mart carries a row for every calendar day of every month (2020-01=31, 2020-02=29, 2020-03=31) — derived from the calendar, so a February that lost a day cannot pass
  ok   4 monitoring ids are defined and every one is labelled MONITORING (KPI-14, KPI-15, KPI-16, KPI-17), and NO column of marts.scoring_daily names KPI-09 or KPI-10 — the window is new, so the ids are new, and the evaluator's holdout ids stay the evaluator's
  ok   the mart carries no floor and no margin column (14 columns checked) — a 2020 margin against a 2019-fitted floor is a comparison no gate ever made, and the way to honour that is to refuse to publish it
  ok   no registry-mutating verb is CALLED anywhere in the batch scoring path (ast over the module, never a word search) — it resolves the alias, stamps the version and mints nothing

== 4. the judgement — the drift signals LOADED, argued in §8, and holding no bar of their own ==
  ok   all 5 M7 rule(s) across signals ['A-10', 'A-3', 'A-4', 'A-8', 'A-9'] are LOADED and health=ok in the live Prometheus (DriftMetricsStale, ModelInputDrift, QuoteHorizonRefusals, ScoringVolumeCollapse, ServedVersionNotChampion)
  ok   6 threshold(s) parsed out of the M7 rules and found in the SECTIONS that own them (§6 and §8, 13,834 characters of the document, not all of it) — a bar argued in the latency section is not an argument for a drift bar
  ok   every M7 rule carries a `signal` label and an `annotations.why` — a threshold whose argument is not written beside it is a number nobody can review
  ok   every one of the 10 known signals ['A-1', 'A-10', 'A-2', 'A-3', 'A-4', 'A-5', 'A-6', 'A-7', 'A-8', 'A-9'] now has a rule and the documented-absence list is EMPTY — F-035 closed by landing, not by prose, and `render_alert_rules.py` fails in both directions so it cannot be re-opened quietly
  ok   A-8's selector excludes 'trip_duration_minutes' BY NAME — the target is monitored and pushed but is not an input, and averaging it into the share would destroy exactly the distinction that makes the alert actionable
  ok   A-9 reads a volume series and A-8 reads a PSI series, and neither expression mentions the other's — the marginal PSI is structurally blind to is measured separately rather than folded in
  ok   no bar-shaped constant ([0.1, 0.5, 1800.0, 3456000.0]) appears anywhere under src/taxi_mlops/monitoring/ — the job computes and pushes, the RULE judges, and one home for a threshold means the pushed numbers can be re-read against a different bar later. Excluded and said so: [0.0, 2.0], which are ordinary arithmetic
  ok   the pushgateway's scrape job sets honor_labels: true, which is what lets the rules select ['taxi-drift', 'taxi-quote-client', 'taxi-serving-version'] at all — without it every pushed sample arrives as job="pushgateway", every rule matches nothing, and nothing errors
  ok   push_metrics REFUSES a payload with no *_last_run_timestamp_seconds (PushError) — a pushed metric persists after its producer dies, so 'drift is fine' and 'the drift job died in March' would otherwise render identically

== 5. the order of work — the bars argued before the data was seen, and the drill that judged them ==
  ok   the headroom leg read ['2019-07', '2019-08'] and nothing else — 2019 only. Its largest input distance is dayofweek at 0.0323 in 2019-07, a month whose verdict already exists (the champion was measured on it and PROMOTED)
  ok   the headroom ran at 2026-08-20T04:14:49+00:00 and the first 2020 comparison at 2026-08-20T04:38:31+00:00 — the order of work checked on the records' own stamps, never on the order the write-ups are arranged in
  ok   the prediction was COMMITTED before any 2020 drift record was — git's own commit clocks, 640 s apart. A prediction written after the outcome is not a prediction, and the only witness that cannot be edited into agreement is the history
  ok   the drill's embedded prediction is field-by-field equal to the committed automation/runs/m7-drift/prediction.json — the record was judged against the file, and the file has not moved since
  ok   exactly the predicted alert fired, for exactly the predicted month: ScoringVolumeCollapse@2020-03 at T+331.5 s, and it reached ALERTMANAGER — a rule that goes red only in Prometheus's own UI has not alerted anybody
  ok   all 7 must-not-fire alert(s) stayed inactive (DriftMetricsStale, PredictorCpuThrottledSustained, PredictorLatencySLOBurning, PredictorNoAvailableReplica, QuoteHorizonRefusals, ServedVersionNotChampion, ServingEdge5xxRateHigh) — the negative half, which is what makes the drill falsifiable
  ok   the open question was pre-registered at confidence 'low — this is the prediction most likely to be wrong' — ModelInputDrift predicted 'DOES NOT FIRE at monthly grain', observed 'did not fire (state=inactive)', correct=True. The monthly window's blind spot is a recorded result, not a footnote
  ok   every recorded volume ratio re-derives from its own anchors — trips/DAY over trips/DAY, not rows over rows (2020-01=0.8336, 2020-02=0.8776, 2020-03=0.3913). A month is not a unit of demand; a day is
  ok   the drill's observed gateway series agree with all 3 per-month drift records — two tracked artifacts written by two phases of the work, and a claim only one of them makes is not a measurement
  ok   the bar 0.5 sits below the quietest ACCEPTED month (0.7899) and above the month that fired (0.3913) — daylight on both sides, and both sides read from records rather than typed here
  ok   the gateway holds no drift series and the reason is accounted for: its container started 2026-08-20T14:25:30+00:00, AFTER the drill pushed at 2026-08-20T04:38:35Z — a bulletin board keeps nothing across a restart. **F-050**: A-10 catches a STALE number and cannot fire on an ABSENT one, so this state is silent. Re-push with `make drift DRIFT_ARGS="--push"`; the gate may not
  ok   the rule was shown to CLEAR (40.0 s after its series was deleted) and the real numbers were then pushed straight back — March 2020 really did lose most of its trips, and latching that off to tidy a transcript would publish a false board

== 6. the retrain — the loop closed, the transfer made, and the pointer that did not move ==
  ok   the challenger was REFUSED and promoted=False: 2 condition(s) passed (3.30% against a 2.00% floor bar) and 2 failed — KPI-09 does not regress against the serving champion (v2); KPI-10 does not regress against the serving champion (v2). A refusal is a working gate, not a failed story
  ok   the count-scaled knob was re-derived at the scale it is USED at: min_data_in_leaf 1293 -> 8620 (x6.6667 = 43,987,422 / 6,598,113), i.e. 1 row in 5103 where it was chosen and 1 in 5103 after — against 1 in 34020 if it had travelled unchanged
  ok   1 knob(s) rescaled and 8 recorded as passed through (bagging_fraction, cat_smooth, feature_fraction, lambda_l1, lambda_l2, learning_rate, max_cat_threshold, num_leaves) — the rule is declared as a named set, so a knob nobody thought about cannot be mistaken for one that was considered
  ok   the round budget re-derives (800 x 3 = 2400, floored at the configured 500) and the fit reports ended_by='early_stopping' at 779 of 2400 — 1621 rounds unspent, so this challenger is unambiguously NOT truncated
  ok   all 21 claims written at 2026-08-20T06:40:00+00:00 hold in a record generated at 2026-08-20T06:43:38+00:00 — compared at the precision the PREDICTION was written to, and two MLflow runs of one configuration agreeing to the last kept digit is this program's second determinism observation
  ok   retrain() has NO `promote` parameter and passes promote=False unconditionally (1 call site(s)) — an unattended job that can move @champion can put an unreviewed model in front of riders at 04:00, so the refusal is in the signature
       [mlflow] tracking: http://localhost:5000
       [mlflow] artifacts: direct to http://localhost:9000 (server does not proxy)
       [mlflow] credentials set from .env: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
  ok   not one of the 8 run(s) the retrain fitted in experiment 'm7-retrain' is a registry version — a promotion cannot hide from that, because it must create a version and a version carries its run
  ok   @champion is version 2, still the run the M3 bake-off recorded as its winner, and all 2 version(s) carry gate_verdict=PROMOTE — the challenger stayed a run, and the pointer never moved (derived, never typed)
  ok   the bake-off derives the incumbent's feature set from the loaded artifact (_feature_set_of) and its alias row pre-registers feature_set=None — F-022's cause was a pointer designed to move carrying a label true only on the day it was written
  ok   2 trigger(s) are declared in code WITH their inputs (retrain-monthly, retrain-schedule-proof) and 1 is registered inactive (retrain-monthly) — hours of CPU on a laptop nobody watches is a PO's call about compute, and turning it on is one field

== 7. the memo against the records, the board that renders it, and the champion still on the wire ==
  ok   all 14 instrument number(s) docs/drift_memo_m7.md quotes are held by the record it cites, at the precision the document wrote them (floor: one decimal — gotcha #90, because 13.75 rendered at zero decimals is `14` and matches anything)
  ok   the memo cites the predictions table by name (marts.scoring_daily) and reads it through 4 monitoring ids (KPI-14, KPI-15, KPI-16, KPI-17) — §9/M7's 'the DA memo cites it', answered with the mart rather than with a re-computation
  ok   no value is published under a promotion id anywhere in the memo (2 mention(s), all of them saying those ids belong to the held-out split) — the ban is on attaching a number, not on naming the id it may not be attached to
  ok   the memo has a runnable twin (scripts/drift_memo_numbers.py) covering all 10 of its numbered sections — every figure comes from a named view or mart, and the script prints the SQL it ran
  ok   the board carries 8 cards citing only monitoring ids (KPI-14, KPI-15, KPI-16, KPI-17), no KPI-09/KPI-10 anywhere, and no floor/margin/kpi_13 column in any card's SQL — the comparison §6.1 refuses to publish cannot arrive through a card
  ok   KPI-16 (signed bias) is on the board (1 card(s)) and 6 card(s) plot the DAILY grain — a monthly row is a GROUP BY away from daily rows and the reverse is not true, which is the whole finding this board exists to render
       [mlflow] tracking: http://localhost:5000
       [mlflow] artifacts: direct to http://localhost:9000 (server does not proxy)
       [mlflow] credentials set from .env: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
  ok   the endpoint answered 10.665224 minutes stamped model_version='2' — equal to what the alias resolves to, reproducing the parity record's 'ordinary-midday' row to 0.000e+00 minutes. M7 ended where M6 did
  ok   the served version's feature_set tag (v2) equals configs/train.yaml's features.version (v2) — the invariant F-032 found nothing enforcing, and M7 did not move either half
  ok   the deployments ledger carries a row for every M7 story that touched the wire (M7-S1, M7-S3, M7-S4, M7-S5) — S2 is host-side batch scoring and mutated nothing on the cluster

[verify-m7] GREEN — every M7 sub-check passed.
            Show: the two signatures    docs/scoring_months_m7.md §8 · docs/drift_detection_m7.md §8
                  the predictions table marts.scoring_daily · data/scoring_predictions/scoring_predictions.json
                  the memo              docs/drift_memo_m7.md · scripts/drift_memo_numbers.py
```

---

## §2 · `make verify-m7-redteam` — PASSED

The plant is `volume_ratio` in `automation/runs/m7-drift/drift-2020-03.json`,
rewritten from a ratio of RATES to a ratio of TOTALS. The replacement is derived
from the record's own fields (`current_rows` over `reference_rows / 6`), is wrong
by about one percentage point, and stays under the 0.50 bar — so the alert still
fires, the verdict is unchanged, and nothing reads differently to a skim.

It is F-045 itself: *a month is not a unit of demand; a day is.*

```text

[verify-m7-redteam] 0. the record as it stands (restored to exactly this, whatever happens)
  automation/runs/m7-drift/drift-2020-03.json  sha256 2e5202e6c395…

[verify-m7-redteam] 1. rewrite ONE number: the volume ratio becomes a ratio of TOTALS — F-045's own mistake
  volume_ratio 0.3913368668 -> 0.4021472775 (rows over rows-per-reference-month, derived from the record itself). It is still under the 0.50 bar, so the ALERT STILL FIRES and the verdict does not change. UNTOUCHED: current_rows 2,948,237, current_trips_per_day 95104.4194, reference_trips_per_day 243024.4309, max_input_psi 0.021667, and every one of the 6 per-column PSI values

[verify-m7-redteam] 2. make verify-m7 — expected RED, naming the anchors, the second witness AND the memo
[verify-m7] the M7 gate — a scoring month that is not a fourth split, two
  FAIL volume ratio(s) that do not reconcile with the run's anchors (recorded vs current_trips_per_day/reference_trips_per_day): {'2020-03': (0.402147277464908, 0.3913368667803675)}
  FAIL the drill record and the per-month records disagree on the ratio: {'2020-03': (0.3913368667803675, 0.402147277464908)}
  FAIL the memo quotes number(s) no record holds: ['2020-03 volume ratio=0.402147277464908']
[verify-m7] RED — 3 sub-check(s) failed.
  ok   the gate exited 1 — RED against a record whose ratio no longer reconciles
  ok   the ANCHOR leg fired: a volume ratio is trips/DAY over trips/DAY, and the planted value is a different quotient of the same file
  ok   the SECOND-WITNESS leg fired: what the drill observed on the live gateway and what the per-month record now claims are two different numbers
  ok   the PROSE leg fired: docs/drift_memo_m7.md §7 and the record now disagree — the third witness, and the only one a human reads
  ok   59 sub-check line(s) still passed — the gate reports everything, not the first thing
  ok   unaffected leg still green: still returns exactly
  ok   unaffected leg still green: differ in all
  ok   unaffected leg still green: reconcile for every month
  ok   unaffected leg still green: are LOADED and health=ok
  ok   unaffected leg still green: and nothing else — 2019 only
  ok   unaffected leg still green: COMMITTED before any 2020 drift record
  ok   unaffected leg still green: was REFUSED and promoted=False
  ok   unaffected leg still green: stamped model_version
  ok   the bar-daylight leg is STILL GREEN — the planted value keeps the alert firing and the argument intact, so the gate went red on a WRONG number rather than on the fact of an edit
  ok   the drill's own verdict still passes — only the ratio moved, not the outcome it produced

[verify-m7-redteam] 3. restore the record and re-run — expected GREEN again
  restored automation/runs/m7-drift/drift-2020-03.json (sha256 2e5202e6c395…)
  ok   automation/runs/m7-drift/drift-2020-03.json is byte-identical to what the drill found (sha256 2e5202e6c395…)

[verify-m7] GREEN — every M7 sub-check passed.
            Show: the two signatures    docs/scoring_months_m7.md §8 · docs/drift_detection_m7.md §8
                  the predictions table marts.scoring_daily · data/scoring_predictions/scoring_predictions.json
                  the memo              docs/drift_memo_m7.md · scripts/drift_memo_numbers.py
  ok   the gate is GREEN again (62 sub-check line(s), exit 0) — the drill left nothing behind
  ok   git status is clean for automation/runs/m7-drift/drift-2020-03.json — the restore is byte-identical to the committed record

[verify-m7-redteam] PASSED: the M7 gate went RED on ONE rewritten volume
                    ratio — a total where a rate belongs, which is F-045 itself —
                    named the arithmetic, the second tracked witness AND the memo
                    that quotes it, left the bar-daylight argument standing, kept
                    counting every other sub-check, and returned GREEN when the
                    record was restored.
```

---

## §3 · What the two runs prove together

| Claim | Where it is shown |
|---|---|
| The gate is GREEN over the repository as it stands | §1, closing line |
| 62 sub-checks across 7 sections | §1, counted with `grep -c 'ok  '` |
| It re-runs nothing expensive | §1 contains no ingest, no score, no drift job, no fit, no deploy — and `tests/unit/test_verify_m7.py` pins that as a property of the script |
| It asks the live system exactly three questions | one prediction (§7), one PromQL query (§5), one rules read (§4) — pinned by test |
| The gate can go RED | §2, `[verify-m7] RED — 3 sub-check(s) failed.` |
| …from three independent artifacts | the anchor arithmetic, `drift_fire_drill.json`, and `docs/drift_memo_m7.md` |
| …on a WRONG number rather than on any edit | the bar-daylight leg and the drill-verdict leg both stay GREEN under the plant |
| …with everything else still counted | 59 sub-check lines still passed during the RED run |
| …and it comes back | byte-identical sha256 restore, GREEN 62/62, clean tree |

---

## §4 · BLUEPRINT §9/M7's accept-when, quoted and answered line by line

> **"v1's M6 gate"**

`make verify-m6` is green and unchanged by this story — M7 added five alert
rules to the file its §2 parses, and its whole-document threshold search
accommodates them. Re-run at this session's end state: **GREEN 63/63**.

> **"the predictions table for the scored month exists"**

`marts.scoring_daily`, 91 daily rows across 2020-01..03, published from
`data/scoring_predictions/` and stamped `model_version = 2` on every row.
**§3 checks it in three systems at once** — the ingest reports in DuckDB, the
scoring manifest on disk, the mart in Postgres — and names the ingest report as
the AUTHORITY, because a job that scored fourteen of 15.4M rows would have the
other two agreeing and both wrong. Observed: **15,413,352 rows, three ways**.

> **"and the DA memo cites it"**

§7 requires `docs/drift_memo_m7.md` to name `scoring_daily` and to read it
through the monitoring ids. Observed: the mart named, **KPI-14/15/16/17** all
cited, and **no value published under KPI-09 or KPI-10** anywhere in the memo —
the ids may be *named* (the memo says out loud that they belong to the held-out
split) but never carry a number.

> **"AND the memo explains the drift in domain terms with numbers"**

§7's prose leg takes **14 instrument numbers** out of the memo's §7 table and
requires each to be held by the record it cites, at the precision the document
wrote it, with a floor of one decimal (gotcha #90). The domain reading itself —
speed, the clock, the airports, the sign of the bias — is re-derivable by
`scripts/drift_memo_numbers.py`, whose section coverage §7 also checks.

> **"Show: the two failure signatures + the predictions table + the memo"**

All three are shown by the gate itself, and the first is shown as a
**difference between record shapes** rather than as a sentence in a table: §2
builds the statistical signature from the drift and ingest records and the
schema signature from the fixture records, then requires them to differ in
**all four** discriminating fields — exit code, rows written, report present,
drift metric present. The last one is the dangerous one, and it is an absence,
which is why it is counted where a landed month would have to appear rather
than read off a field the record cannot honestly carry.

---

## §5 · One finding, raised by the gate on its own first run

**F-050 — a pushgateway restart deletes the drift series, and A-10 cannot see
it.** The gate's live PromQL query returned **zero** `taxi_drift_volume_ratio`
series against three tracked records. Nothing had drifted and nothing was
wrong with M7's work: the pushgateway pod had restarted (host reboot,
`startedAt 2026-08-20T14:25:30Z` against the drill's `pushed_at
2026-08-20T04:38:35Z`), and a gateway keeps nothing across a restart.

The consequence is the part worth recording. **SLO-D3/A-10 exists to catch a
STALE number and cannot fire on an ABSENT one** — `time() - max by (month)
(taxi_drift_last_run_timestamp_seconds)` over no series is no series, so the
rule sits `inactive` and the board renders empty. That is gotcha #78's
empty-panel disease one layer up: the guard written against "a number nobody
refreshed" is blind to "a number nobody has".

**How the gate handles it, and why it is not simply a FAIL.** Re-populating the
gateway means re-running the drift job, which this gate is forbidden to do, so
demanding the samples would turn the M7 gate red for a laptop reboot with no
defect behind it (gotcha #50). Instead §5 asks the **pair**: either the series
are present, or the gateway has restarted since the drill pushed them and the
absence is accounted for by two clocks. An absence with no restart behind it is
still a FAIL, so the check degrades in the correct direction — and the passing
line names F-050 and prints the one command that fixes it.

Routed to the M7 boundary with two costed options in `ledgers/findings.md`.
