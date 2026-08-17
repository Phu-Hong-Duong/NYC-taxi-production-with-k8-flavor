# The automation track — FLAML scout × Optuna sniper (M3-S4)

*role:MLE · executed 2026-08-17 · Design Review decisions DR-01 (budget), DR-03
(disjoint axes), DR-05 (full-data contenders) bind every section below.*

This is the automation half of M3's 2×2. Its counterpart is
`docs/ablation_m3.md`, the artisan track, and the two exist to answer one
question at M3-S5: **was the improvement features, or tuning, or both?** That
question has an answer only because DR-03 gave the two tracks disjoint search
axes —

> The artisan searches FEATURES and holds hyperparameters at v1's.
> The automation track searches HYPERPARAMETERS and is handed feature sets it
> does not invent.

— so nothing in this document proposes a feature, and nothing in
`ablation_m3.md` proposes a hyperparameter.

**Nothing here promotes.** The registry API appears in none of this story's
scripts and a test keeps it out. The two contenders this track produces are
handed to the gate at M3-S5, once, on the test month.

---

## 0. The budget, declared before any result existed

DR-01 equalises the two tracks in **model-fitting wall-clock seconds** and gives
each **9,000 s**. The artisan spent **3,313.9 s** of its share and stopped on its
own stop rule (two consecutive loops below the keep threshold). This track's
share was split in `scripts/automation_track.sh`'s header **before the first fit**,
so that no phase could be handed more budget once its number was known:

| phase | budget | where the number comes from |
|---|---:|---|
| scout on v1 | 1,800 s | `configs/automl.yaml: time_budget_s` — DR-01 pinned it and did not edit it |
| scout on v2 | 1,800 s | the same budget, the other feature set |
| sniper on v1 | 1,500 s | `n_trials: 60` **or** the cap, whichever binds first |
| sniper on v2 | 1,500 s | ditto |
| two full-data refits | ~1,700 s | measured, not capped — DR-05 requires full data |
| **total** | **~8,300 s** | of 9,000 |

DR-01 condition 2 forbids retroactively handing the loser more budget, so a study
that stops at trial 34 of 60 because its share ran out **reports that** and is not
re-run. `scripts/optuna_sniper.py` prints which limit bound it (`stopped_on`).

Actual per-phase fitting seconds are printed by the track's own ledger at the end
of `automation/runs/m3s4-automation-track.log` and are recorded in §6.

---

## 1. The dependencies, resolved live, and the risk that did not bite

`uv add "flaml>=2" "optuna>=4" "xgboost>=3" "psycopg[binary]>=3"` — bounded on
purpose (gotcha #36: an unbounded `uv add mlflow` once resolved silently to a
version two majors behind the server). Read back with the shim active:

```
flaml 2.6.0 · optuna 4.9.0 · xgboost 3.4.1 · psycopg 3.3.4
sqlalchemy 2.0.52 · alembic 1.19.1 · lightgbm 4.7.0 (unchanged)
pandas 3.0.5 · numpy 2.5.2 · scipy 1.18.0 · scikit-learn 1.9.0  <- all unchanged
```

**The kickoff's named risk — "xgboost needs OpenMP too, and this host has none"
— is discharged by measurement.** The shim's `LD_LIBRARY_PATH` covers any
consumer in-process, and xgboost trained on the first attempt with nothing added:

```
xgboost trained ok, preds [2.9600425 2.9600425 2.9600425]
```

The fallback the kickoff authorised (drop xgboost from `estimator_list` and let
FLAML run the remaining families) was not needed and was not used.

Two things worth knowing anyway:

- **FLAML imports LightGBM at module scope**, so `ensure_openmp()` must run
  *before* `from flaml import AutoML`. Every script here calls it as its first
  statement after argument parsing — which also keeps the log linear, because
  the re-exec otherwise happens several minutes of parquet reading later and
  throws all of it away (gotcha #37, third consumer).
- **xgboost drags `nvidia-nccl-cu13` (241 MB) in as a hard dependency on Linux.**
  There is no GPU on this machine and it is never loaded. Recorded because a
  241 MB download inside a $0, every-version-pinned program should be a fact
  somebody wrote down rather than a surprise in a container build at M4.

## 2. Where the study lives — D-002's recipe, for the third time

Optuna's whole value here is that a study **outlives the process that runs it**.
That is a property of storage, so the study lives in the one Postgres.

**The database arrived by the recipe M1-S4 promised and M1-S5 first re-tested:
one line in `scripts/postgres_databases.sh` and one ADDITIVE key in
`scripts/platform_secrets.sh`.** A test now pins both halves. `optuna` is the
recipe's **third** consumer after `marts` and `metabase`, and the first that is
**not a pod** — the study driver runs on the host, so it gets a role and no
Kubernetes Secret.

The evidence that it really was created on an existing volume — D-002's entire
point, since `docker-entrypoint-initdb.d` runs once on an empty data directory
and editing that ConfigMap later is a silent no-op:

```
datname  | owner    | directory created
---------+----------+------------------------
mlflow   | mlflow   | 2026-08-17 02:36:54+00
marts    | marts    | 2026-08-17 02:36:59+00
metabase | metabase | 2026-08-17 02:36:59+00
optuna   | optuna   | 2026-08-17 15:59:17+00   <- this story, 13h later, same volume
```

and the second run's idempotence, from `make deploy-platform`:

```
[pg-db] optuna: before = role present, database present
[pg-db] ok  optuna owner=optuna
[pg-db] 4 database(s) converged (no password printed, by design)
```

**No DSN is in any config.** `configs/tuning.yaml` says `storage: postgres` and
that stays a *word*; `taxi_mlops.tuning.storage` assembles
`postgresql+psycopg://…` from `.env` in memory, and `describe()` is what a log is
allowed to print. A test walks every file under `configs/` looking for a
connection string, not just `tuning.yaml` — the next stub will be called
something else.

`postgresql+psycopg://` is spelled out because SQLAlchemy 2's bare
`postgresql://` still means psycopg**2**, which this project does not install.

### Why a port-forward and not a published port

CLAUDE.md's port family annotates 5432 **in-cluster only**, and kind publishes
host ports at cluster-CREATE time only. Adding one means
`make cluster-down && make cluster-up`, which takes the PVCs — and with them
MLflow's backend database, the registry, and the champion. **A cluster rebuild is
not a price a tuning story gets to pay.** The other in-cluster path this repo
already owns (`kubectl exec` + psql on stdin, M1-S4) carries CSV, not a live
SQLAlchemy session.

So the sniper opens a `kubectl port-forward` for as long as it runs and closes it
after. Nothing is published, nothing survives the process — and killing the
process takes the tunnel with it while leaving every trial in Postgres. That
asymmetry is exactly what the next section demonstrates.

## 3. Kill-and-resume — and the zombie the first drill found

`make tune-resume-drill` runs the real sniper on its own study
(`m3-resume-drill-v1`, so the kill never lands on a study whose trials are part
of a reported number), kills it with **SIGKILL on the process group** after three
trials, and reads the trial counts back over a *fresh connection to Postgres*
rather than from the process under test. SIGKILL and not SIGTERM on purpose: a
terminate handler could flush state on the way out, which would prove that our
shutdown path works rather than that the storage does.

**The first run passed the letter of the requirement and failed its spirit**, and
that is the most useful thing this story found:

```
[drill] Postgres AFTER the kill, on a fresh connection: {'COMPLETE': 2, 'RUNNING': 1, 'TOTAL': 3}
[drill] Postgres AFTER the resume: {'COMPLETE': 7, 'RUNNING': 1, 'TOTAL': 8}
```

The trial count continued — §9/M3's ask, satisfied. But **the trial that was
mid-fit at the moment of the kill stayed `RUNNING` in Postgres forever.** Optuna
cannot tell a process that is thinking from a process that no longer exists, so
that row is never completed, never retried, and never failed, while still
occupying a slot in every "how many trials do we have" sum that follows. The
resumed study had asked for `n_trials - len(trials)` more work, so it silently
delivered **seven** answered trials where eight were requested — one lost trial
per kill, invisible unless somebody read the states rather than the total.

Two fixes, both in this story:

1. **A heartbeat.** `taxi_mlops.tuning.storage.rdb_storage` builds an
   `RDBStorage` with `heartbeat_interval` and `RetryFailedTrialCallback`, so a
   running trial stamps the row, `study.optimize` fails trials whose stamp has
   gone stale past the grace period, and the failed trial is re-enqueued with the
   same parameters. The interval is a knob because the drill needs a short one to
   *watch* the reaping and a real study wants a long one so a slow trial is never
   mistaken for a dead process.
2. **Count answers, not rows.** The sniper now asks for `n_trials` minus the
   **ANSWERED** trials (`COMPLETE` + `PRUNED`). Everything else is still owed.

The drill after both, with a 5 s heartbeat and its 15 s grace period waited out
in the open:

```
[drill] Postgres reports 3 trial(s); killing pid 123019 with SIGKILL
[drill] arm 1 process is gone (returncode -9 = killed by signal)
[drill] Postgres AFTER the kill, on a fresh connection: {'COMPLETE': 2, 'RUNNING': 1, 'TOTAL': 3}
[drill] waiting 17s — one heartbeat grace period (5s x 3) — so the trial that died mid-fit can be seen to be dead
[drill] arm 2 starting — SAME command, no resume flag
[drill] arm 2 exited 0
[drill] Postgres AFTER the resume: {'COMPLETE': 8, 'FAIL': 1, 'TOTAL': 9}
[drill] arm 2 announced it opened the study with 3 existing trial(s)
[drill] ok   trials survived the SIGKILL
[drill] ok   the trial killed mid-fit was reaped by the heartbeat
[drill] ok   no trial is left stuck RUNNING
[drill] ok   the study answered all 8 requested trials
[drill] PASS
```

Arm 2 runs the **same command** — there is no resume flag, and there is nothing
to remember. The resumed study now does not merely continue; it **recovers**.

## 4. The pruner, and why the live run is not its evidence

`configs/tuning.yaml` pins `MedianPruner(n_startup_trials=10, n_warmup_steps=20)`.
A "step" is whatever the reporter counts, so `taxi_mlops.tuning.fit` counts
**boosting rounds** and reports every `REPORT_EVERY_ROUNDS = 25` of them — which
is the only unit in which "warm up for 20" means something a reader can predict.
A test fails if those two numbers stop being expressible in each other.

A 16-trial smoke study at 0.5% finished with **zero pruned trials**. That is a
perfectly good outcome (TPE converged and nothing was worse than the running
median) and **terrible evidence, because it is exactly what a pruner wired to
nothing also looks like.** So the propagation path is pinned by a test instead:
`report → should_prune → TrialPruned`, out through LightGBM's callback list *and*
XGBoost's `TrainingCallback`, through `fit`'s `finally`, to Optuna — both
families, because they are two different callback protocols and the live smoke
only ever exercised one.

That test runs the fit in a **child process**, for gotcha #37's reason: `fit`
calls `ensure_openmp()`, which on this host re-execs the interpreter, and
re-execing a pytest process restarts the test session in the middle of itself.
The first draft of the test did exactly that and hung.

## 5. F-008's guard, exercised on a real sampled run

This milestone's scout and sniper **sample by design** — 5% for the scout, 15%
for every sniper trial. F-008 measured what that does to a verdict: the gate's
floor is fitted on the same rows as the challenger, so shrinking train degrades
the **bar** faster than it degrades the model. On one train month the margin went
7.07% → 16.85% *without the model getting better*. A sampled run does not produce
a weaker number; it produces a **flattering** one.

M3-S1 closed that by refusing to issue a verdict at all. `make f008-guard` runs
both refusals from one place:

```
[f-008] -m taxi_mlops.training train --train-months 2019-01 --no-promote
[f-008] expecting exit 2 — a sampled train set is GATE-DISQUALIFYING: no verdict is possible
[f-008] ok   exit 2 (expected 2)

[f-008] -m taxi_mlops.training train --train-months 2019-01 --no-gate
[f-008] expecting exit 3 — the sample-first smoke path: a table, and NO verdict issued
[gate] NO VERDICT was issued for this run (see above). Exit 3.
[promote] SKIPPED — no verdict was issued (sampled run, F-008). A run the gate
          declined to judge cannot promote, with or without --no-promote.
[f-008] ok   exit 3 (expected 3)

[f-008] PASS — 2/2
```

Two distinct exit codes, because "no verdict was possible" and "no verdict was
asked for" must never be confused by a pipeline (they will be, at M4).

Every run this track logs carries the same claim on the artifact rather than in a
transcript: `sample_run=yes`, `do_not_promote=yes — <n>% sample (F-008)`, and —
on the scout — `metric_source: FLAML internal — SCOUT-INTERNAL, NOT the
evaluator`, so gotcha #15 is legible to somebody who finds the run in six months
and never reads this document.

## 6. The scout, the sniper, and the two contenders

*Landing from the detached run `automation/runs/m3s4-automation-track.log`
(status `automation/runs/m3s4-automation-track.status`, outputs
`automation/runs/m3s4/*.json`). This section is written by the session that reads
that status file — it is deliberately empty rather than provisional, because a
table of numbers nobody has measured is worse than no table.*

What the run does, in order, so the numbers can be checked against the intent:

1. `scout on v1` and `scout on v2` — FLAML, 5% sample, `estimator_list`
   `[lgbm, xgboost, rf, extra_tree]`, 1,800 s each. Output: a **family** and
   **starting params**, plus a leaderboard every line of which is labelled
   scout-internal. Only the loss is shown on that leaderboard: FLAML exposes no
   per-family wall clock, and an earlier draft printed one from an attribute that
   does not exist — every cell came back `0.0`, which reads like a measurement
   and is not one.
2. `sniper on v1` and `sniper on v2` — Optuna, TPE + MedianPruner, 15% sample,
   space **centred on that set's scout winner** and clipped to absolute bounds,
   ≤1,500 s each, every trial an MLflow nested run under one parent in
   `m3-automl`.
3. `refit auto-on-v1` and `refit auto-on-v2` — the study's best parameters, refit
   on the **full** configured train months (DR-05), measured by
   `taxi_mlops.training.evaluate`, logged with signature and input example.

### The one refusal path this track has

`taxi_mlops.tuning.space.SUPPORTED_FAMILIES` is `(lgbm, xgboost)`. FLAML's
`estimator_list` is deliberately wider — the scout is allowed to tell us
something we did not expect — so **if the scout names `rf` or `extra_tree`, the
sniper REFUSES** rather than quietly tuning the runner-up, because a sniper that
silently retargets is a sniper whose report does not describe what it did. That
would be a finding and a decision taken in the open, not a number.

## 7. Open, named, not silently carried

- **A rounds cap of 800 for the sniper and its refits, against v1's 500.** v1
  never early-stopped (500/500 with val still improving), so a tuner that could
  only ever ask for 500 would be unable to trade a smaller learning rate for more
  rounds — which is half of what tuning a booster *is*. The ceiling is a BUDGET
  decision (DR-01), not a modelling one, and it is stated where it is set.
- **The scout samples at 5% and the sniper at 15%, and those are different
  numbers on purpose.** The artisan needed 15% because a 0.50% relative-MAE keep
  decision needed that resolution; the scout is ranking four families and FLAML
  sub-samples internally on top of whatever it is given. Both are printed on
  every run and stamped on every MLflow run.
- **If an XGBoost contender wins the bake-off at M3-S5**, `score.load_champion`'s
  resolution path (F-009's localized workaround) has only ever been exercised
  against a LightGBM flavor. The model is logged under its own flavor here and
  `mlflow.pyfunc` reads both, but that is an argument, not a measurement. Named
  for S5 rather than assumed.
- **`make train` still cannot fit a set that uses the point-in-time aggregates**
  (carried from M3-S3, `docs/ablation_m3.md` §7). v2 needs no fitted tables, so
  this track is unaffected.
