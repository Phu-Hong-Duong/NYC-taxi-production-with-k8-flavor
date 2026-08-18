# The M3 gate, watched passing and watched failing (M3-S5)

Both transcripts, pasted whole and unedited except for ANSI colour codes and
`make`'s directory chatter. They are the M3 accept-when's evidence: *`make
verify-m3` GREEN exit 0 with every sub-check printing; red-teamed to RED once
naming the broken leg, others still counted, restored GREEN.*

Run on **2026-08-18** against the live cluster, with `@champion` at version 2
(`auto-lgbm-v2`, run `92b73bd4f77d4a05b92472bfcfb3cccf`, feature set v2).

**What to notice in the GREEN run.** 46 sub-checks across 8 sections in under
five seconds, and the registry is identical before and after (alias → 2,
versions `['1', '2']`, checked by hand). Nothing here is re-fitted. M3 cost
**12,447 s** of fitting across its two tracks; a gate that re-derived any of it
would cost more than the milestone it verifies and would mint MLflow runs on
every verification. So the gate reads committed docs, committed JSON, the Optuna
storage in the ONE Postgres, and the registry — and it *replays* the recorded
numbers through the decision code that is on disk right now.

**What to notice in the RED run.** The injected fault is ONE number in
`automation/runs/m3s5/bakeoff.json`: `auto-on-v1`'s measured KPI-09 moves from
3.5038 (a REFUSE at −4.54% against the floor) to 3.2000 (a comfortable PROMOTE),
with its recorded verdict left at REFUSE. That is precisely the residue a session
which edited a table after seeing it would leave behind, and it is invisible to a
`grep` for the word REFUSE. §5 catches it because it never reads the recorded
verdict — it feeds the recorded NUMBERS back through `gate.decide` and demands
the same answer.

Three things the drill asserts beyond "it went red", each of which a weaker gate
would fail:

* it **names** the row and both verdicts (`replaying auto-on-v1 through today's
  gate gives PROMOTE, the bake-off recorded REFUSE`);
* the four **untampered** replays still pass — which is what separates a replay
  leg from a checksum: it must go red on a *wrong* number, not on any edit;
* **44 of 46** sub-checks still ran and passed. A suite that collapses to one
  failure when one thing breaks tells you nothing about the rest of the system.

The record is restored from a byte copy under an `EXIT` trap and the restore is
*verified* by sha256 (`c4a323ea072a…` before and after), not assumed.

---

## 1. `make verify-m3` — GREEN, exit 0

```
[verify-m3] the M3 gate — dossier, ablation, leakage drill, tuning,
            the five bake-off verdicts, the guards, and the alias.
            It re-reads and re-replays; it re-fits NOTHING.

== 1. the dossier: >=10 candidates, each with a source and a leakage note ==
  ok   the dossier holds 20 candidates (the gate asks for >= 10)
  ok   every one of the 20 candidates names where it came from (Source column)
  ok   every one of the 20 candidates carries a leakage note
  ok   all 3 HIGH-leakage candidate(s) are constrained to TRAIN months in their adaptation note (playbook §5 trap 1)
  ok   7 candidate(s) carry a REFUSED/DROPPED verdict with a reason (rows 12, 13, 14, 15, 16, 17, 21) — the dossier says no as well as yes

== 2. the ablation: per-group deltas, and DR-02's bar re-applied to them ==
  ok   all 5 declared groups have an ablation row (v1_g1, v1_g2, v1_g3, v1_g4, v1_g5) — every group tried is reported
  ok   every group row carries BOTH deltas — relative val MAE and KPI-10 points (DR-02)
  ok   re-applying DR-02's >= 0.50% bar to the table's own numbers reproduces all 5 verdicts
  ok   3 group(s) LOST and are in the table anyway (v1_g3, v1_g4, v1_g5) — a table of winners only would imply a 100% hit rate
  ok   feature set v2 in the registry is exactly the surviving group(s): ['g1_temporal_extras', 'g2_centroid_geometry']

== 3. the leakage red-team: inflation observed, and the switch still leaks ==
  ok   the drill's transcript is on file and its three numbers parse: seen +0.0551, unseen -0.1367, inflation +0.1917 min
  ok   they reconcile: +0.0551 - (-0.1367) = +0.1918 = the recorded inflation (within 4-dp rounding)
  ok   the leak flattered the month it saw and hurt the month it did not — which is the whole finding, and the direction a green drill must have
  ok   aggregates.fit(point_in_time=True) is still the DEFAULT — the honest path is the one you get by not thinking about it
  ok   exactly one CALLER may flip it, and it is the red team: scripts/leakage_redteam.py (the switch itself is defined in src/taxi_mlops/features/aggregates.py)

== 4. tuning: the studies live in Postgres, one PRUNED, one survived a kill ==
  ok   the `optuna` database in the ONE Postgres holds 5 study/studies with 59 trial(s) total
  ok   sniper-v1: study 'm3-sniper-v1' is in Postgres with 9 trial(s), the count its JSON records ({'COMPLETE': 9})
  ok   sniper-v2: study 'm3-sniper-v2' is in Postgres with 21 trial(s), the count its JSON records ({'COMPLETE': 15, 'PRUNED': 6})
  ok   the pruner FIRED and the storage remembers: m3-sniper-v2 6 pruned
  ok   a study outlived its process: killed at 3 trial(s), reopened with 3, finished with 9 and 1 dead trial(s) reaped — and Postgres still holds all 9

== 5. the bake-off: five verdicts replayed through gate.decide as it is on disk NOW ==
  ok   the bake-off recorded all 5 contenders on 'test' — floor, champion v1, artisan v2, auto-on-v1, auto-on-v2
  ok   replayed floor: 3.3518 vs floor 3.3518 min, incumbent v1 3.2608 -> REFUSE (+0.00%), as the bake-off recorded
  ok   replayed champion v1: 3.2608 vs floor 3.3518 min, incumbent v1 3.2608 -> PROMOTE (+2.71%), as the bake-off recorded
  ok   replayed artisan v2: 3.2425 vs floor 3.3518 min, incumbent v1 3.2608 -> PROMOTE (+3.26%), as the bake-off recorded
  ok   replayed auto-on-v1: 3.5038 vs floor 3.3518 min, incumbent v1 3.2608 -> REFUSE (-4.54%), as the bake-off recorded
  ok   replayed auto-on-v2: 3.2403 vs floor 3.3518 min, incumbent v1 3.2608 -> PROMOTE (+3.33%), as the bake-off recorded
  ok   the replayed set is not all-passing: 3 PROMOTE, 2 REFUSE — including the floor judged against itself
  ok   all 4 model contenders name the MLflow run their numbers came from (3adee05a…, 6807116e…, ec0eba69…, 92b73bd4…)
  ok   docs/bakeoff_m3.md names all five contenders by run name (the gate's 'Show')

== 6. the guards: incumbent, val, flattering floor, and the sampled run ==
  ok   F-011 armed: a challenger 0.02 min worse than the incumbent is REFUSED by name ('KPI-09 does not regress against the serving champion (v1)') while it still clears the floor bar (3.2603 vs 3.3518 min = +2.73% (required >= 2.00%))
       [mlflow] tracking: http://localhost:5000
       [mlflow] artifacts: direct to http://localhost:9000 (server does not proxy)
       [mlflow] credentials set from .env: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
  ok   registry.promote REFUSES a promotion that did not read the incumbent (incumbent_version=None) — @champion points at version 2 and this promotion was decided against incumbent NOTHING (al…
  ok   the gate REFUSES to judge on val (early stopping read it) — GateError, not a warning
  ok   the gate REFUSES the flattering constant-median floor as the bar
  ok   F-008 armed: a run fitted on 1 of 6 configured train months is gate-DISQUALIFIED before a row is read (a shrunken train degrades the BAR faster than the model)
  ok   the bar is unchanged: KPI-09 margin >= 2.0% and the KPI-10 no-regression condition still armed

== 7. the alias: the registry is coherent with the bake-off's recorded outcome ==
       [mlflow] tracking: http://localhost:5000
       [mlflow] artifacts: direct to http://localhost:9000 (server does not proxy)
       [mlflow] credentials set from .env: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
  ok   the bake-off's winner 'auto-on-v2' (auto-lgbm-v2) carries a PROMOTE verdict — the alias decision followed the gate, not the ranking
  ok   models:/nyc-taxi-eta@champion -> version 2, run 92b73bd4f77d… — the run the bake-off named as winner
  ok   the version carries the bake-off's own numbers: KPI-09 3.2403 vs floor baseline-group-median-od-fallback — the registry answers 'measured against what?'
  ok   none of the 1 REFUSED contender(s) is a registry version (2 version(s) total) — a refusal leaves the registry as it found it
  ok   configs/train.yaml names feature set 'v2' — the winner's set, so a re-fit today starts from what is serving
  ok   the champion's signature is exactly the 24 feature(s) features.sets.resolve expands 'v2' to, in order

== 8. F-013: the stubs are really gone, and each thing has exactly one home ==
  ok   configs/promotion.yaml is gone — the bar that agreed with nothing in the program (gate_ratio: 0.85) is not there to be found first
  ok   no file under configs/ except train.yaml names a gate knob (4 knob(s) checked across 5 other config file(s))
  ok   configs/train.yaml: features holds only ['registry', 'version'] — the column lists live in configs/features.yaml and nowhere else
  ok   features.sets.resolve RAISES on a column list in train.yaml — the one expansion in the program cannot be walked around
  ok   grep -r 'analytics' src/taxi_mlops/ is EMPTY — model code reads no mart (ADR-009, gotcha #22)

[verify-m3] GREEN — every M3 sub-check passed.
            Show: the dossier      docs/feature_dossier.md
                  the ablation     docs/ablation_m3.md
                  the bake-off     docs/bakeoff_m3.md (2x2 + floor, five verdicts)
                  the leakage drill docs/leakage_redteam_m3.md
[exit 0]
```

---

## 2. `make verify-m3-redteam` — RED, named, restored, GREEN again

```
[verify-m3-redteam] 0. the record as it stands (restored to exactly this, whatever happens)
  automation/runs/m3s5/bakeoff.json  sha256 c4a323ea072a…

[verify-m3-redteam] 1. rewrite ONE contender's measured KPI-09 so its number and its verdict disagree
  auto-on-v1 test KPI-09 3.5038422819518478 -> 3.2 (its recorded verdict is still 'REFUSE')

[verify-m3-redteam] 2. make verify-m3 — expected RED, naming auto-on-v1 and both verdicts
[verify-m3] the M3 gate — dossier, ablation, leakage drill, tuning,
  FAIL replaying auto-on-v1 through today's gate gives PROMOTE, the bake-off recorded REFUSE — the gate moved under the transcript
  FAIL the replay produced {'PROMOTE': 3, 'REFUSE': 1} — a bake-off nobody was refused in is a bake-off nobody was judged in
[verify-m3] RED — 2 sub-check(s) failed.
  ok   the gate exited 1 — RED against a record whose number contradicts its verdict
  ok   it NAMES the broken row AND both verdicts: replayed PROMOTE vs recorded REFUSE
  ok   all 4 untampered replays still passed — the leg reads numbers, not files
  ok   44 sub-check(s) still ran and passed — the gate reports everything, not the first thing
  ok   unaffected leg still green: the dossier holds
  ok   unaffected leg still green: reproduces all 5 verdicts
  ok   unaffected leg still green: the pruner FIRED
  ok   unaffected leg still green: a study outlived its process
  ok   unaffected leg still green: F-011 armed
  ok   unaffected leg still green: features.sets.resolve RAISES

[verify-m3-redteam] 3. restore the record and re-run — expected GREEN again
  restored automation/runs/m3s5/bakeoff.json (sha256 c4a323ea072a…)
  ok   automation/runs/m3s5/bakeoff.json is byte-identical to what the drill found (sha256 c4a323ea072a…)

[verify-m3] GREEN — every M3 sub-check passed.
            Show: the dossier      docs/feature_dossier.md
                  the ablation     docs/ablation_m3.md
                  the bake-off     docs/bakeoff_m3.md (2x2 + floor, five verdicts)
                  the leakage drill docs/leakage_redteam_m3.md
  ok   the gate is GREEN again (46 sub-checks, exit 0) — the drill left nothing behind

[verify-m3-redteam] PASSED: the M3 gate went RED on ONE contradicted number,
                    named the row and both verdicts, kept counting every other
                    sub-check, and returned GREEN when the record was restored.
[exit 0]
```
