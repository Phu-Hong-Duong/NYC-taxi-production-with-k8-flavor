# M7-S4 transcripts — pasted, not summarised

Companion to `docs/retrain_m7.md`. Every claim in that document has a paste here.
Progress-bar lines and MLflow's three-line credential banner are stripped; nothing
else is edited.

---

## §1 — F-022's execution half: `make bakeoff BAKEOFF_ARGS="--smoke-rows 20000"`

The closure condition the ledger names is *"one execution of the resulting script
that gets past contender resolution"*. This is that execution. **Exit 0**, five
contenders resolved, five verdicts printed, no JSON written, nothing promoted.

The load-bearing line is the second `[resolve]`: the alias row's feature set is
**DERIVED from the artifact**, and it reads `v2` where the pre-registered Spec
used to say `v1`.

```
==============================================================================
[bakeoff] M3-S5 — five contenders, one evaluator, one untouched month
[bakeoff] NOTHING IS RE-FITTED: the four models are loaded from the MLflow
[bakeoff] artifacts their val numbers describe. Only the floor is fitted.
[bakeoff] *** SMOKE RUN (20,000 rows/split) — NOT A RESULT ***
==============================================================================

[bakeoff] the 2x2 (+ floor), declared before a number is measured:

  contender        track       features      hyperparameters
  ---------------- ----------- ------------- ----------------------------------------
  floor            floor       v1            none — it is a two-level GROUP BY
  champion (alias) incumbent   (the model's) whatever the serving champion was fitted with
  artisan v2       artisan     v2            hand (v1's, held fixed — DR-03)
  auto-on-v1       automation  v1            tuned (FLAML scout -> Optuna sniper)
  auto-on-v2       automation  v2            tuned (FLAML scout -> Optuna sniper)

  configs/train.yaml: features.version is 'v2' (what is SERVING; it moves only as part of a promotion)
[resolve] models:/nyc-taxi-eta@champion -> version 2 (run 92b73bd4f77d4a05b92472bfcfb3cccf)
[resolve] champion (alias) auto-lgbm-v2       family=lgbm     features=v2 (24) (DERIVED from the artifact — F-022) trees=791 recorded val MAE 3.3822796832477016
[resolve] m3-artisan/artisan-v2 (sample_fraction=1.0) -> run 6807116edf4c49d681a31bd941298a81
[resolve] artisan v2       artisan-v2         family=lgbm     features=v2 (24) trees=500 recorded val MAE 3.3905388307148137
[resolve] automation/runs/m3s4/refit-v1.json -> run ec0eba69389d44bc9f4dadcbad8e4094 (auto-xgboost-v1)
[resolve] auto-on-v1       auto-xgboost-v1    family=xgboost  features=v1 (5) trees=800 recorded val MAE 3.724473218110082
[resolve] automation/runs/m3s4/refit-v2.json -> run 92b73bd4f77d4a05b92472bfcfb3cccf (auto-lgbm-v2)
[resolve] auto-on-v2       auto-lgbm-v2       family=lgbm     features=v2 (24) trees=791 recorded val MAE 3.3822796832477016

[floor] fitting baseline-group-median-od-fallback from the configured train months
[data] train       20,000 rows  months=2019-01,2019-02,2019-03,2019-04,2019-05,2019-06   <<< SMOKE TRUNCATION, NOT A RESULT
```

and the tail, where the square declines to re-base itself onto the alias:

```
[gate] selection : the winner was chosen on VAL before any test number existed — val MAE, ranked above
==============================================================================

[bakeoff] the 2x2 is NOT printed: no contender occupies its origin cell (features v1, hand hyperparameters).
[bakeoff] Through M3 the incumbent row held it, because the alias held lightgbm-v1. Since F-022 that row means 'whatever is serving', and what serves is a tuned v2 model — the square's OWN 'both' cell.
[bakeoff] M3's answer stands as measured: docs/bakeoff_m3.md §6 (features +0.56%, tuning on top of them +0.07 points).

[bakeoff] WINNER (selected on val): artisan v2 (artisan-v2) — val KPI-09 3.1207 min
[bakeoff] its test numbers, measured AFTER it was chosen: KPI-09 2.2731 min · 91.280% KPI-10
[bakeoff] its verdict: PROMOTE

[bakeoff] SMOKE: no JSON written, nothing promoted, no number above is a result.
```

Every number on those last four lines is a **20,000-row smoke number** and the
banner says so on entry and on exit. The verdicts are the path being exercised,
not a result; M3's five verdicts stand as recorded and `verify-m3` §5 replays
those, not these.

---

## §2 — F-020's transfer, resolved live: `make retrain RETRAIN_ARGS="--plan-only"`

Seconds, fits nothing, mints no run, issues no verdict. It exists so the
provenance chain — alias → version → run → refit record → study → sniper record —
can be checked without spending an hour of CPU on it.

```
[openmp] openmp: system libgomp.so.1
==============================================================================
[retrain] challenger : retrain-rescaled-v2
[retrain] champion   : version 2 (auto-lgbm-v2, run 92b73bd4f77d…), feature set v2
[retrain] F-020 (1)  : count-scaled knobs chosen on 6,598,113 rows, fitting on 43,987,422 -> factor 6.6667 (automation/runs/m3s4/sniper-v2.json)
[retrain]              min_data_in_leaf: 1293 -> 8620 — 1 row in 5,103 where it was chosen; unchanged here it would be 1 in 34,020 (F-020); rescaled it is 1 in 5,103
[retrain] F-020 (2)  : rounds 500 configured / 800 inherited -> 2400
[retrain]              re-derived: 800 (the sniper's PER-TRIAL cap at its sample, which the champion's refit inherited and then ran into) x 3 = 2400. It is a compute bound, not a model choice — the fit reports whether early stopping or the cap ended it.
[retrain] passed through unchanged (not row counts): bagging_fraction, cat_smooth, feature_fraction, lambda_l1, lambda_l2, learning_rate, max_cat_threshold, num_leaves
==============================================================================
[retrain] resolved config -> automation/runs/m7-retrain/retrain_config_<stamp>.yaml
[retrain] record -> automation/runs/m7-retrain/retrain_plan_<stamp>.json
```

`1 row in 5,103` on the first and third clauses is the transfer's definition —
the knob means the same FRACTION at both scales — and `1 in 34,020` is F-020's
own number, recomputed here from the tracked records rather than quoted.

---

## §3 — The schedule: `make retrain-schedule`

The image guard fires first. It fired for real on this story's own commit
(`scripts/retrain_schedule.sh`) and the image was rebuilt rather than the guard
narrowed:

```
[schedule] task image: taxi-mlops-pipeline:820adbd
[schedule] FAIL: the task image predates the source it would run (F-026).
[schedule]   committed:   scripts/retrain_schedule.sh
[schedule]       Fix: make image-load
```

After `make image-load`:

```
[schedule] task image: taxi-mlops-pipeline:72a4013
[schedule] ok  image 72a4013 carries this tree's src pyproject.toml uv.lock docker scripts analytics pipelines
[schedule] ok  control plane answers /healthz -> 200
[schedule] deploying environment 'train_env' from pipelines/flyte/workflows.py
  ✓ Built image for environment taxi-pipeline-train: taxi-mlops-pipeline:72a4013
  > Bundling code...
  ✓ Code bundle: 25 files, 0.361328125 MB (compressed 0.09818649291992188 MB)
  > Deploying task taxi-pipeline-train.retrain, with image taxi-mlops-pipeline:72a4013 version 6d5b536b975b7814c829cb3ef2bcbaf8 from pipelines.flyte.workflows.retrain
  ✓ Deployed task taxi-pipeline-train.retrain (version 6d5b536b975b7814c829cb3ef2bcbaf8)
```

and then the triggers **read back off the server**, not off the file that was
submitted:

```
[schedule] triggers, READ BACK OFF THE SERVER:
                                    Triggers
 Task_name                    Name                     Automation                  Auto_activate
 taxi-pipeline-train.retrain  retrain-schedule-proof   every 20 minutes starting   True
                                                       at now
 taxi-pipeline-train.retrain  retrain-monthly          cron: 0 3 1 * * (UTC)       False
```

`Auto_activate False` on the monthly row is the decision in §5 of the write-up,
visible in the control plane's own answer rather than only in the source.

---

## §4 — The proof trigger firing, and the defect it found

Registered 05:31:54Z. **Fired 05:51:54Z**, twenty minutes later, exactly as
`FixedRate(20)` says — read off the control plane's own record of the run, never
off the trigger's configuration (gotcha #81 one cadence up: a registered trigger
and a firing trigger look identical in a `get trigger` table).

```
'name': 'taxi-pipeline-train.retrain',
'triggerName': 'retrain-schedule-proof',
'phase': 'ACTION_PHASE_SUCCEEDED',
'startTime': '2026-08-20T05:51:54Z',
'endTime':   '2026-08-20T05:51:58.502156Z',
'podName':   'r5d5ce577470fc2ce-a0-0'
```

Four and a half seconds, one pod, run `r5d5ce577470fc2ce`. The schedule
mechanism is proven: **registered, reconciled by the server, and observed firing
once**, which is what M7 owes.

**And its output is F-048.** The returned record:

```
ActionOutputs(o0="{"challenger": "retrain-rescaled-v2", "champion_version": "2",
"target_rows": 43987422, "rescale_factor": null, "round_cap": 500,
"plan_only": true, "sampled": false, "decision": "PLAN_ONLY", "promoted": false, …}")
```

`rescale_factor: null` and `round_cap: 500`, against the host's `6.6667` and
`2400` **for the same champion in the same minute**. The pod's own log says why:

```
[retrain] F-020 (1)  : no sampled search behind this champion — no scale transfer to make
[retrain]              min_data_in_leaf: 1293 (unchanged)
[retrain] F-020 (2)  : rounds 500 configured / None inherited -> 500
[retrain]              no inherited search cap: the configured budget of 500 rounds stands.
                       There is nothing to re-derive.
```

That sentence is **honest about what the code could see and false about the
world**: `.dockerignore` excludes `automation/runs/`, so inside a task pod the
provenance chain is absent for a reason that has nothing to do with the champion.
The reported-no-op design is right — F-020 *is* the finding that assuming a
sample fraction produces a plausible configuration nobody can check — and it
turns out the same design lets a **missing file** wear a legitimate absence's
clothes. Gotcha #94's shape with the direction reversed.

No number is wrong yet: the scheduled path has only ever planned, the full-data
measurement was made on the host where the chain resolves, and `retrain-monthly`
is registered inactive. Filed with three options and routed to ARCH; the guard
that must land under any of them is that **"no refit record names this run" and
"I cannot see any records at all" must not produce the same sentence.**

---

## §5 — The full-data retrain and its verdict

### §5.1 — Attempt 1: the verdict was reached and could not be written down

The detached run of 2026-08-20T05:59Z fitted for 28 minutes, was correctly
REFUSED, and then died serialising the verdict. `automation/runs/*.log` is
gitignored (transcripts, not records), so the run's own output is pasted here —
this section IS the evidence, and it is kept because a refusal nobody can read is
the same as no refusal.

```
[evaluate] every number below came from taxi_mlops.training.evaluate
[evaluate] (gotcha #15: nothing else in this program may report one)

  contender                          split       rows      KPI-09      KPI-10     RMSE   medAE   p90AE
  ---------------------------------  -----  -----------  ----------  ----------  ------  ------  ------
  baseline-constant-median           val      6,189,748      7.8866     47.505%  12.201   5.283  17.850
  baseline-constant-median           test     5,950,708      7.6667     48.372%  11.844   5.183  17.133
  baseline-group-median              val      6,189,748      3.7170     78.693%   6.222   2.342   7.933
  baseline-group-median              test     5,950,708      3.5090     80.322%   5.811   2.292   7.317
  baseline-group-median-od-fallback  val      6,189,748      3.5515     79.111%   5.644   2.333   7.700
  baseline-group-median-od-fallback  test     5,950,708      3.3518     80.733%   5.245   2.283   7.117
  retrain-rescaled-v2                val      6,189,748      3.3811     80.570%   5.347   2.257   7.244
  retrain-rescaled-v2                test     5,950,708      3.2412     81.568%   5.006   2.247   6.852

[evaluate] retrain-rescaled-v2 BEATS the honest floor on val: 3.3811 vs 3.5515 min (+4.80%)
[evaluate] val is the REPORT. The gate below judges on test, and only test.

==============================================================================
[gate] PROMOTION GATE — configs/train.yaml: gate (loosening it is a PO fork)
[gate] holdout   : test — 5,950,708 rows, untouched by training and by selection
[gate] challenger: retrain-rescaled-v2          KPI-09 3.2412 min  ·  KPI-10 81.568%
[gate] floor     : baseline-group-median-od-fallback KPI-09 3.3518 min  ·  KPI-10 80.733%
[gate] incumbent : version 2                    KPI-09 3.2403 min  ·  KPI-10 81.577%   [version tags]
[gate] required  : KPI-09 at least 2.00% below the floor
[gate] observed  : KPI-09 +3.30% vs the floor
[gate]   ok   KPI-09 margin over the honest floor: 3.2412 vs 3.3518 min = +3.30% (required >= 2.00%)
[gate]   ok   KPI-10 (within 5 min) does not regress: 81.568% vs 80.733% = +0.835 points
[gate]   FAIL KPI-09 does not regress against the serving champion (v2): 3.2412 vs 3.2403 min (-0.03% vs incumbent)
[gate]   FAIL KPI-10 does not regress against the serving champion (v2): 81.568% vs 81.577% = -0.009 points
[gate] VERDICT   : REFUSE
[gate] Nothing was registered and no alias moved. A refused challenger leaves the registry exactly as it found it.
[gate] context   : the FLATTERING floor (baseline-constant-median) is 7.6667 min on test and is NOT the bar — against it this would read as +57.72%.
==============================================================================

[mlflow] retrain-rescaled-v2: model logged with signature + input example
[mlflow] retrain-rescaled-v2: run d2f69f90a5a84e00b02e670b6a409990

[promote] SKIPPED — the gate refused. Nothing registered, no alias moved.

[retrain] the fit ended by EARLY_STOPPING: best_iteration 779 of a 2400-round cap, 1,682.5s
Traceback (most recent call last):
  File "/home/longt/.../src/taxi_mlops/training/retrain_run.py", line 184, in retrain
    {"passed": c.passed, "text": c.text} for c in decision.checks
                                 ^^^^^^
AttributeError: 'Check' object has no attribute 'text'
make[1]: *** [Makefile:245: retrain] Error 1
----------------------------------------------------------------
[detached] exit 2 at 2026-08-20T06:27:56Z
```

**Read the last three lines together, because they are the second defect.**
`gate.Check` carries `name`/`passed`/`detail` and never had a `text`; the record
writer asked for one. The traceback then exited with a status this program had
*already given a meaning*, so `automation/runs/m7-retrain-fulldata.status` read
`FAILED 2` and HANDOFF (bo)'s decoding key turns 2 into **"the challenger could
not be built"** — about a challenger that had been built, fitted for 28 minutes
and judged. The boot ritual of the next session was told the opposite of what had
happened, and only the log disagreed.

Both are fixed in `6972618`: the serialiser is a function that can be executed
without spending the fit, and a crash exits **4**, outside the 0/1/2/3 verdict
vocabulary. The full argument — including why the `hasattr` guard that was on the
line made it *look* checked, and why every test of this module had asserted on its
source text — is in `docs/retrain_m7.md` §7.1.

### §5.2 — Attempt 2: the same fit, through the repaired writer

*(Filled by the re-run; the record is `automation/runs/m7-retrain/latest.json` and
what it must reproduce was written down first, in
`automation/runs/m7-retrain/rerun-prediction.json`.)*
