# `verify-m6` transcripts (M6-S5 leg 2)

Pasted, unedited, from the runs that produced them on 2026-08-20. The gate is
`scripts/verify_m6.sh`; the red team is `scripts/verify_m6_redteam.sh`. Both are
in CLAUDE.md's command table and both are `make` targets.

Three things to read for, because they are the properties rather than the
numbers:

1. **Nothing here was re-run.** M6's evidence cost about fifty-five minutes of
   staged failures — including a deliberate ~5 minute total outage of the only
   predictor — plus two alias moves, two weight shifts and a restore into
   scratch databases. The gate's own wall-clock is **2.147 s**. Every number it
   judges comes from a tracked record (F-029), which is why a fresh clone judges
   the same bytes and why a tampered record is a diff.
2. **No threshold and no version is typed.** Every alert threshold is parsed out
   of `infra/monitoring/alerting_rules.yml` and looked for in
   `docs/slo_serving.md`; the served version is compared with what the alias
   resolves to. The string `2` in the output is printed, never asserted.
3. **It asks the live system three questions it could not answer from a file:**
   one Prometheus query, one rules-API read, and one prediction. The Prometheus
   one is new to this gate and exists because of F-043 — the predictor's own
   exporter went dark during the one event it was there to report, so §1 asks
   whether it is healthy *right now*.

---

## 0. §9/M6's accept-when, quoted and answered line by line

> "Accept when: the shadow comparison table exists with a quantified
> disagreement rate before the first traffic shift; v1's M5 gate (canary 90/10
> observed, rollback <2min under load, alert fired in red-team); AND the gameday
> record shows predicted-vs-observed signatures with at least one prediction
> wrong and investigated (a gameday with all predictions right was too easy).
> Show: the shadow disagreement table + Grafana during canary + gameday record."

| Clause | Where the gate answers it | Observed |
|---|---|---|
| "the shadow comparison table exists with a quantified disagreement rate" | §3 | 1,016 rows, mean **1.3976** min · median **0.6489** · p90 **3.2693** · max **36.4201**, segmented five ways, champion vs shadow served **2** vs **1** — read off the answers, not off the deploy |
| "**before** the first traffic shift" | §3 | the ordering checked on the two records' OWN clocks: shadow measured **2026-08-19T14:49:23Z**, first shift **2026-08-19T15:23:48Z**. It is an ordering, and this is the only check that could catch it backwards |
| "canary 90/10 observed" | §4 | ingress counter **41 of 420 = 9.76%** at weight 10, corroborated by the two predictors' own counters at **9.33%** (0.43 points apart); **100.0%** at weight 100; **0.0%** after the revert. Observed from traffic, never from the annotation (gotcha #81) |
| "rollback <2min under load" | §5 | **35.347 s** for all three moves, measured while an open-loop client was sending; version 1 actually answered **33.218 s** in. The traffic revert, separately, is **0.37 s** |
| "alert fired in red-team" | §6 | A-3 **T+170.5 s** then A-2 **T+335.6 s**, both **received by Alertmanager** — and all five must-not-fire alerts inactive, which is the half that makes the positive one falsifiable |
| "the gameday record shows predicted-vs-observed signatures" | §6 | four scenarios, the positive control first; the predictions written **16:03:35Z** against a first measurement at **16:15:07Z**, and each scenario's prediction **field-by-field equal** to the committed file |
| "at least one prediction wrong and investigated" | §6 | **two** were wrong (kill, saturation), neither engineered, both investigated in named passages of `docs/gameday_m6.md` |
| "Show: the shadow disagreement table" | closing lines | `automation/runs/m6-shadow/disagreement.json` · `docs/shadow_analysis_m6.md` |
| "Show: Grafana during canary" | §1 + closing lines | Grafana answers on the existing 8081 route (`/api/health` → 200); board `analytics/grafana/dashboards/serving.json`, its panels executed by `make monitoring-accept` |
| "Show: gameday record" | closing lines | `automation/runs/m6-gameday/` · `docs/gameday_m6.md` |

**What the gate additionally asks that the accept-when does not** — the M6
kickoff's own list: every rule LOADED and healthy in the live server (§2), every
threshold argued in the SLO document (§2), the restore rehearsal's label moved
exactly one notch everywhere it exists (§7), the prose checked against the
records (§3, §7), and the alias law in its strong form (§7).

---

## 1. `make verify-m6` — GREEN, 63 sub-checks across 7 sections, 2.147 s

```
[verify-m6] the M6 gate — the eyes, the judgement, shadow before canary,
            the split that moved, the rollback that was finally run, and a
            gameday graded on being wrong. It reads and it asks; it re-runs nothing.

== 1. the eyes — the stack is live, it answers, and the exporter is healthy RIGHT NOW ==
  ok   Prometheus answers through the EXISTING 8081 route as Host: prometheus.local (/-/healthy -> 200) — M6 law 1, no new hostPort was ever needed
  ok   Grafana answers on the same route as Host: grafana.local (/api/health -> 200) — 'Show: Grafana during canary' has somewhere to be shown
  ok   monitoring/prometheus-server (deploy): 1 ready replica(s)
  ok   monitoring/grafana (deploy): 1 ready replica(s)
  ok   monitoring/prometheus-kube-state-metrics (deploy): 1 ready replica(s)
  ok   monitoring/prometheus-alertmanager (statefulset): 1 ready replica(s)
  ok   Prometheus answered a live query: up{job="kserve-predictors"} returns 2 series — the predictor job is DISCOVERED, which is a stronger statement than 'the target is up'
  ok   the CHAMPION's exporter is up right now (up{job="kserve-predictors",inferenceservice="nyc-taxi-eta"} == 1 on 1 series) — scoped to 'nyc-taxi-eta', never 'the first result'
  ok   its scrape completes in 0.0023 s against the configured 15 s interval — the exporter is not starving (F-043's live question)

== 2. the judgement — every rule LOADED, every threshold argued in the SLO document ==
  ok   all 7 rule(s) in infra/monitoring/alerting_rules.yml are LOADED and health=ok in the live Prometheus — the checked-in file is what is judging the service
  ok   every rule's `for:` sustain matches the loaded one (PredictorLatencySLOBurning=5m, ServingEdge5xxRateHigh=5m, PredictorRequestRejectionRateHigh=2m, PredictorNoAvailableReplica=2m, PredictorRestartFlapping=0m, PredictorCpuThrottledSustained=10m, PredictorStorageInitializerNotReady=3m) — F-041 made this the load-bearing half: what stops a self-heal paging is the sustain, not the threshold
  ok   every threshold in every rule appears in docs/slo_serving.md — 6 number(s) parsed out of the expressions and found in the document that owns them
  ok   every rule carries a `signal` label and an `annotations.why` — the argument travels with the number (7 rules)
  ok   the implemented signals ['A-1', 'A-2', 'A-3', 'A-5', 'A-6', 'A-7'] are exactly the ones with a metric source, and the 1 absent one(s) ['A-4'] each have a named section in the SLO document (F-035 — the gap cannot be quietly forgotten OR quietly closed)
  ok   the SLO document declares 4 targets: SLO-L1, SLO-A1, SLO-R1, SLO-C1 — latency, availability, rejections and saturation
  ok   A-1 counts requests beyond the le="0.25" bucket edge and never calls histogram_quantile — §2.1's finding, encoded in the rule

== 3. shadow before canary — a quantified disagreement rate, and a verdict, BEFORE the shift ==
  ok   the disagreement table is quantified over 1016 rows: mean 1.3976 min, median 0.6489, p90 3.2693, max 36.4201 — a distribution, not an average
  ok   it is segmented 5 ways (airport, declared_hazard, long_trip, no_geometry, ordinary) — the question the blueprint asks the DA is WHICH segments diverge
  ok   the two endpoints served DIFFERENT versions (champion 2 vs shadow 1) and different feature sets (v2 vs v1) — read off the ANSWERS, not off the deploy
  ok   the shadow table was measured 2026-08-19T14:49:23Z, BEFORE the first traffic shift at 2026-08-19T15:23:48Z — the blueprint's ordering, checked against the two records' own clocks rather than against the order they are written up in
  ok   the DA memo states a verdict in its own heading: 'NO-GO for version 1.' — a named input to the go/no-go, not a summary
  ok   every headline number the memo quotes is in the record it cites (long-trip mean 2.6527 min, max 36.4201, champion closer 63.6%, 1016 rows)
  ok   the record and the memo both say what the sample is NOT — a stratified sample's MAE is not the holdout's, and docs/bakeoff_m3.md stays the measurement of record (gotcha #15)

== 4. canary 90/10 OBSERVED — from counters, by two witnesses, at no cost to the rider ==
  ok   the release drill recorded 11/11 checks passed
  ok   at canary-weight 10 the INGRESS counter attributed 41 of 420 requests to the canary = 9.76% — 90/10 observed from traffic, never from the annotation (gotcha #81)
  ok   the two witnesses agree at weight 10: ingress 9.76% vs the predictors' own counters 9.33% (0.43 points apart) — different processes, same event
  ok   weight 100 moved 100.0% and the revert returned the split to 0.0% over 300 requests — 10 -> 100 -> back
  ok   1440/1440 requests answered with 0 errors across both weight changes and the revert, and the champion predictor kept the same pod uid — an Ingress edit reloads nginx and touches no pod
  ok   the traffic revert took 0.37 s against the record's own 120 s budget, measured on the controller's /configuration/backends and not on the API call
  ok   the record states the honest cost in its own predictions: one version (2) served throughout, because the canary carried the champion's OWN bytes — the version stamp is NOT evidence about the split
  ok   @champion was version 2 before AND after the canary — a release rehearsal that moved the pointer would be a promotion
  ok   ADR-011 is committed (ADR-011-canary-and-shadow-mechanism.md) and its evidence is the spike record — PASS 7/7, including the shared-Service canary that moved nothing
  ok   the FAILED first attempt is kept unedited beside the green one (0.0% moved at weight 10) — a red run deleted is a lesson deleted

== 5. rollback <2 min under load — the runbook's own three moves, run for real, both ways ==
  ok   the rollback rehearsal recorded 10/10 checks passed, both directions
  ok   the rollback's three moves took 35.347 s — inside §9/M6's 2-minute bar, and measured while an open-loop client was sending
  ok   both legs moved all three things — the alias (1 then 2), configs/train.yaml's features.version (v1 then v2) and a re-deploy. F-032's un-rehearsed half, run
  ok   version 1 actually answered 33.218 s in — the rollback target served traffic, it did not merely get pointed at
  ok   the asymmetry is recorded: rolling BACK cost 27.928 s of failing requests (55 of 85, classes ['HTTP 500', 'HTTP 502']) against 0.501 s rolling forward — removing features refuses requests, adding them does not (F-040)
  ok   `verify-m5` at the half-way state exited 2 with 3 failure(s) while its coherence check stayed GREEN at 'v1' — the gate noticed the pointer moved, and the check that compares tag-to-config passed on the OTHER feature set
  ok   the end state is the declared one: @champion 2, features.version v2, configs/train.yaml byte-identical by git hash-object (4eaa1edfa5fd…), and `verify-m5` GREEN again
  ok   the runbook's §4 heading declares REHEARSED 2026-08-19 and cites a record this repo holds (automation/runs/m6-rollback/alias_rollback.json, automation/runs/m6-canary/release_drill.json) — M5's 'typed but not rehearsed' is discharged
  ok   §4 names the reordered remedy (deploy first, move the config line last) and labels it UNPROVEN — a mitigation nobody has run must not be substituted mid-incident

== 6. Gameday 1 — the control first, the predictions on disk first, and one of them wrong ==
  ok   the predictions were written 16:03:35Z, before the first scenario was measured at 16:15:07Z — checked on the records' own clocks, not on the file's claim about itself
  ok   each scenario record carries the SAME prediction the committed file holds (3 compared field-by-field) — amending one to match an outcome is a diff
  ok   the positive control ran FIRST and was GREEN 11/11 — the negatives that follow are made by an instrument that was just watched working
  ok   alerts FIRED and were RECEIVED: PredictorRequestRejectionRateHigh at T+170.5s, ServingEdge5xxRateHigh at T+335.6s — all reaching Alertmanager, not merely evaluating
  ok   all 5 must-NOT-fire alerts stayed inactive — the negative predictions are what make the positive one falsifiable
  ok   2 prediction(s) were WRONG (kill, saturation) and the write-up investigates them in 2 named passage(s) — §9/M6's bar, met without engineering a surprise
  ok   @champion was read before AND after 2 scenario(s) (kill, storage) and never moved — a gameday that promoted something would be the defect
  ok   the two outages have DISTINGUISHABLE signatures: the kill fired nothing while the broken credential fired ['PredictorNoAvailableReplica', 'PredictorStorageInitializerNotReady'] — the kickoff's requirement, measured
  ok   the kill's 13.75 s outage reconciles with its own anchors: strictly longer than the 13.501 s error SPAN and inside one arrival gap of it (2/4 req/s = 0.5 s) — the span itself is gotcha #75's wrong quantity
  ok   the storage scenario's undo ran clean (exit 0) and left all 7 rules inactive — the injection was reversible before it was made

== 7. the restore's honest label, the prose against the records, and the alias law ==
  ok   the restore drill recorded 17/17 checks passed across 3 database(s) and a MinIO bucket
  ok   every restore landed in a scratch database (mlflow_restore_drill, optuna_restore_drill, metabase_restore_drill) and a scratch bucket, the live database sizes are byte-identical before and after, and no scratch survived
  ok   the restored studies carry the trial counts a DIFFERENT record holds (m3-sniper-v1=9, m3-sniper-v2=21, from automation/runs/m3s4/sniper-*.json) — a witness that is not the live database
  ok   the restored registry carries the same pointer as the live one (champion|2) — a backup that loses the alias loses the rollback
  ok   one MLflow artifact came back byte-identical by sha256 (51aa46e27cc4…, 1274 bytes) — object counts prove a transfer, a hash proves the bytes
  ok   the label moved one notch in all 3 artifacts that carry it — including the 1 line(s) the backup PRINTS at runtime, and each says both halves (scratch-rehearsed AND full restore still not)
  ok   every headline number docs/gameday_m6.md quotes is in the record it cites (8 checked: outage 13.75 s, 5xx peak 0.5, A-6 at T+844.3 s)
  ok   the deployments ledger carries a row for every M6 story that touched the wire (M6-S1, M6-S2, M6-S3, M6-S4, M6-S5)
       [mlflow] tracking: http://localhost:5000
       [mlflow] artifacts: direct to http://localhost:9000 (server does not proxy)
       [mlflow] credentials set from .env: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
  ok   @champion is version 2, whose run is still the winner the M3 bake-off recorded — M6's two sanctioned alias moves round-tripped, and nothing else moved the pointer (derived from the record, never typed)
  ok   all 2 registry version(s) still carry gate_verdict=PROMOTE — M6 minted nothing, and the rollback rehearsal registered nothing by hand
  ok   the endpoint answered 10.665224 minutes stamped model_version='2' — equal to what the alias says, and reproducing the parity record's row for 'ordinary-midday' to 0.000e+00 minutes. M6 ended where M5 did

[verify-m6] GREEN — every M6 sub-check passed.
            Show: the shadow table    automation/runs/m6-shadow/disagreement.json · docs/shadow_analysis_m6.md
                  Grafana at canary   http://localhost:8081 (Host: grafana.local) · analytics/grafana/dashboards/serving.json
                  the gameday record  automation/runs/m6-gameday/ · docs/gameday_m6.md
```

### 1.1 The two stale labels this gate found on its first run

§7's rehearsal-label leg went RED against two artifacts that had been left
behind when M6-S5 leg 1 moved the restore label one notch:

* **`scripts/platform_backup.sh` still PRINTED the old claim at runtime.** Its
  header, its `MANIFEST.txt` text and CLAUDE.md all said *scratch-rehearsed
  2026-08-19*; line 85 — the one an operator actually reads when the backup runs
  — still said `restore NOT rehearsed (M6 gameday candidate)`. The header is for
  review; that line is for 3am.
* **`ledgers/deployments.md` carried the M4-S2 claim unqualified**, which
  asserted that "RESTORE IS NOT REHEARSED — stated in the script header, in
  every MANIFEST.txt and here". CLAUDE.md's backup row claimed four artifacts
  said the new label; two did not.

Both were fixed in this story. The historical M4-S2 row keeps its original
sentence with a **dated note beside it** rather than being rewritten — the
`error_memo_m2.md` §9 precedent: a ledger that silently updates its own past
cannot be compared against the decisions made from it.

---

## 2. `make verify-m6-redteam` — PASSED: RED with 2 FAILs, then GREEN 63/63

What it plants and why is argued in the script's own header. In one line: the
gameday's kill outage is rewritten to the record's **own** `error_window.span_s`
— the wrong anchor gotcha #75 records, a value derived from the file rather than
invented, wrong by about a quarter of a second. Two artifacts must contradict
it: the record's arithmetic, and the write-up that quotes the number.

```
[verify-m6-redteam] 0. the record as it stands (restored to exactly this, whatever happens)
  automation/runs/m6-gameday/kill.json  sha256 f73324ffa333…

[verify-m6-redteam] 1. rewrite ONE number: the gameday's outage becomes the error SPAN — gotcha #75, re-made
  observed.outage_seconds 13.75 -> 13.501 (the error-window span, derived from the record itself). UNTOUCHED: the error window's own anchors (30.5 -> 44.001), the 55 failed requests, both pod uids, the alias 2 -> 2, the prediction, and all 7 recorded checks

[verify-m6-redteam] 2. make verify-m6 — expected RED, naming the anchors AND the write-up that quotes them
[verify-m6] the M6 gate — the eyes, the judgement, shadow before canary,
  ok   the FAILED first attempt is kept unedited beside the green one (0.0% moved at weight 10) — a red run deleted is a lesson deleted
  FAIL the recorded outage 13.501 s does not reconcile with the run's anchors: the error span is 13.501 s and recovery closes on the next success, so the outage must lie in (13.501, 14.001] at 4 req/s
  FAIL the write-up quotes number(s) no record holds: {"the kill's outage": 13.501}
[verify-m6] RED — 2 sub-check(s) failed.
  ok   the gate exited 1 — RED against a record whose outage no longer reconciles
  ok   the ANCHOR leg fired: the recorded outage is not bounded by first-failure -> first-success, which is the only arithmetic that makes it an outage
  ok   the PROSE leg fired: docs/gameday_m6.md and the record now disagree — the second witness, reading a different artifact
  ok   61 sub-check line(s) still passed — the gate reports everything, not the first thing
  ok   unaffected leg still green: the CHAMPION's exporter is up right now
  ok   unaffected leg still green: are LOADED and health=ok
  ok   unaffected leg still green: BEFORE the first traffic shift
  ok   unaffected leg still green: the INGRESS counter attributed
  ok   unaffected leg still green: the asymmetry is recorded
  ok   unaffected leg still green: the positive control ran FIRST
  ok   unaffected leg still green: stamped model_version
  ok   the kill record's prediction still matches the committed predictions file — the gate went red on the WRONG number, not on the edit
  ok   the kill's alert signature still reconciles with the storage break's — only the number moved

[verify-m6-redteam] 3. restore the record and re-run — expected GREEN again
  restored automation/runs/m6-gameday/kill.json (sha256 f73324ffa333…)
  ok   automation/runs/m6-gameday/kill.json is byte-identical to what the drill found (sha256 f73324ffa333…)

[verify-m6] GREEN — every M6 sub-check passed.
            Show: the shadow table    automation/runs/m6-shadow/disagreement.json · docs/shadow_analysis_m6.md
                  Grafana at canary   http://localhost:8081 (Host: grafana.local) · analytics/grafana/dashboards/serving.json
                  the gameday record  automation/runs/m6-gameday/ · docs/gameday_m6.md
  ok   the gate is GREEN again (63 sub-check line(s), exit 0) — the drill left nothing behind
  ok   git status is clean for automation/runs/m6-gameday/kill.json — the restore is byte-identical to the committed record

[verify-m6-redteam] PASSED: the M6 gate went RED on ONE rewritten gameday
                    outage — the exact wrong anchor gotcha #75 records — named
                    both the arithmetic and the write-up that quotes it, kept
                    counting every other sub-check, and returned GREEN when the
                    record was restored.
```

### 2.1 The red team's FIRST run found a defect in the gate, not in the record

Its first attempt went **RED on the anchor leg and GREEN on the prose leg** —
i.e. the drill FAILED, because only one witness spoke. The cause was in
`verify_m6.sh`, not in the plant:

> §7's prose comparison rendered a record's number at every precision from
> **zero** decimals upward, so `13.75` also rendered as **`14`** — and `14`
> appears in almost any document. The planted `13.501` rendered as `14` too, and
> matched.

The floor is now **one decimal**, with the reason written beside it. An
integer-valued record (an error count) still renders as `55` because the
trailing zero is stripped, so nothing legitimate was lost.

This is **gotcha #76 for the second time, in the other direction**. M5-S5 found
that a bare substring search matches `14` *inside* `14.53`; this is the same
family, arriving through rounding instead of through tokenisation. Both make a
prose-vs-record check pass against a number the record does not hold, and both
were caught only because a red team planted a value close enough to be plausible
— a drill that had planted `999` would have gone green on both legs and taught
nobody anything.

---

## 3. What this gate deliberately does NOT check

Named so that the absences are visible rather than assumed:

* **It does not re-provoke an alert.** The `alert_fire_drill.py` path fires two
  real rules end to end and takes ~8 minutes; §6 reads its record (twice over —
  M6-S2's own run and the gameday's re-run of it as the positive control). What
  §2 checks live is that the rules are LOADED and healthy, which is the property
  that could have silently regressed since.
* **It does not shift traffic or move the alias.** Both are checked from
  records, and §7 asserts live that the alias is still the M3 bake-off's
  recorded winner — the form of the claim that cannot be satisfied by not
  looking.
* **It does not check the v1 shadow.** The shadow is a leftover of M6-S3 that
  M6-S5 leg 1 deliberately left running, and `make shadow TEARDOWN=1` removes
  it; making it a gate condition would turn an optional artifact into a
  requirement. §1's predictor query is scoped to the champion's
  InferenceService by name for the same reason, and because the gameday's
  storage record shows what "take the first result" costs.
* **It does not re-derive the canary share from Prometheus.** `make
  canary-split-paste` does that, and it needs a canary to be running. The gate
  reads the counters both witnesses recorded at the time.
