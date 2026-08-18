# The automation track — FLAML scout × Optuna sniper (M3-S4)

*role:MLE · executed 2026-08-17, resumed and completed 2026-08-18 · Design Review decisions DR-01 (budget), DR-03
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

Actual per-phase fitting seconds are recorded in **§6.5**, read from each phase's
own JSON in `automation/runs/m3s4/`. (The track also prints a ledger at the end
of its log, but the log is not the record: it is rotated on every relaunch and a
resumable track gets relaunched — gotcha #48. The JSONs are.) **The track went
over: 9,133.8 s measured against 9,000 declared — +133.8 s, +1.49% — and §6.5
says which phases and why.**

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

*Every number below is read from `automation/runs/m3s4/*.json` — one file per
phase, written by the phase that measured it. This section was deliberately empty
until the numbers existed; it was first filled from **five of six** landed phases
with the sixth named as missing rather than omitted, and it is **complete here**:
all six phases have landed and every `pending` has been replaced by a
measurement.*

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

### 6.1 The two scouts — what FLAML picked, and on what

Both scouts ran the full configured budget on a 5% sample (2,199,371 train rows,
309,487 val rows, seed 20260817), all four families in `estimator_list`.

| scout | features | family chosen | scout-internal loss (MAE) | fitting s | MLflow run |
|---|---:|---|---:|---:|---|
| v1 | 5 | **xgboost** | *scout-internal* 3.7627 | 1,954.5 | `ca687e9974054f08ba1981e25f41870f` |
| v2 | 24 | **lgbm** | *scout-internal* 3.5035 | 1,853.0 | `a01cd9048a4f45c6a7759b233da3b46b` |

**Both numbers in that loss column are scout-internal and neither is a result**
(gotcha #15): they are FLAML's own hold-out loss on a 5% sample, not
`taxi_mlops.training.evaluate` on the val month. They are here to show what the
scout was *steering by*, and for one comparison only — against each other.

The scout's job was the family and the starting params, and it did it twice with
**different answers** (xgboost on v1, lgbm on v2), which is the reason DR-03 made
the sniper centre on *that set's* winner rather than on one global winner.

Neither scout named `rf` or `extra_tree`, so the refusal path in §6's last
subsection was never taken. It stays armed.

### 6.2 The two studies — 9 trials and 21 trials, both stopped by the clock

| study | family | requested | total | COMPLETE | **PRUNED** | FAILED | stopped on | best trial | best value (15% sample val MAE) | fitting s |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|
| `m3-sniper-v1` | xgboost | 60 | 9 | 9 | **0** | 0 | **budget** (1,500 s) | #3 | *sample* 3.7417 | 1,623.9 |
| `m3-sniper-v2` | lgbm | 60 | 21 | 15 | **6** | 0 | **budget** (1,500 s) | #8 | *sample* 3.4059 | 1,412.8 |

**The ≥1-pruned-trial leg (§9/M3) is satisfied by measurement, not by the test:**
`m3-sniper-v2` pruned **6 of its 21 trials** in the real run. The armed-pruner
unit test in §4 stays the evidence for the *v1* study, which pruned nothing —
and §4's argument is exactly why that test exists: zero pruned trials is what a
healthy pruner looks like on easy data and what a pruner wired to nothing looks
like, and only one of those two can be told apart from the outside.

**Both studies were bound by the clock, not by `n_trials`, and that is a result
DR-01 asked to be reported rather than fixed.** Neither got near 60 trials. The
v1 study got **9** — an eight-dimensional space explored nine times is barely
more than the scout's suggestion plus noise, and the honest reading of
`auto-on-v1` is "the scout's config, nudged three times", not "a tuned model".
The v2 study got 21 because its pruner killed six trials early; a pruner buys
trials, and here it bought **more than double** the search on the same clock.

Best params landed as `best_params` in each JSON and are pasted into the refit
transcript in the log, so the contender's configuration is readable from either
end.

### 6.3 The contenders, refit on FULL data (DR-05)

| contender | features | family | val MAE (KPI-09) | val within-5-min (KPI-10) | best iter | fitting s | MLflow run |
|---|---|---|---:|---:|---:|---:|---|
| `auto-on-v1` | v1 (5) | xgboost | **3.7245** | **78.003%** | 800 / 800 | 1,308.1 | `ec0eba69389d44bc9f4dadcbad8e4094` |
| `auto-on-v2` | v2 (24) | lgbm | **3.3823** | **80.552%** | 791 / 800 | 981.5 | `92b73bd4f77d4a05b92472bfcfb3cccf` |

Both rows are measured by `taxi_mlops.training.evaluate` on the val month
(2019-07, 6,189,748 rows) after a full-data fit on 43,987,422 train rows —
the same evaluator, the same rows and the same month as every artisan number in
`docs/ablation_m3.md`, which is what makes the 2×2 at M3-S5 a comparison at all.

**`auto-on-v2` was refit on a resume, and the resume cost one phase.** The track
was stopped by hand at 18:46:00Z on 2026-08-17 — the PO asked for a silent machine
overnight and this track runs 16 threads flat out — after `refit-v1` had written
its verdict and before `refit-v2` started. Nothing was frozen, throttled or
SIGSTOPped, precisely so that `refit-v1`'s 1,308.1 s stays a true DR-01
measurement. The phase JSONs are the resume points (`scripts/automation_track.sh`
skips any phase whose JSON exists), so relaunching the identical command on
2026-08-18 at 02:40:26Z **skipped all five completed phases by name** and ran only
the missing refit, which finished at 02:59:07Z with `0 phase(s) failed`. Neither
number in that table was fitted twice.

**Both refits ran to the 800-round cap without early stopping, and only one of
them was hurt by it.** That distinction is §6.4's, and it is a measurement, not a
reading of the same fact twice.

### 6.4 The result that must not be smoothed: automation LOST on v1 by 7.15% and WON on v2 by 0.24%

`auto-on-v1` measures **3.7245** val MAE against hand-tuned v1's **3.4760** —
the automation track's v1 contender is **7.15% WORSE** than the model M2-S2 fitted
by hand on the same five features, and it is down **1.69 points** of KPI-10
(78.003% vs 79.693%). That is a reportable outcome under DR-03 and it is the
whole reason the 2×2 exists; an automation track that could only win would not be
a measurement.

The log says why, and it is a budget cause rather than an algorithmic one:

```
[500]	val-mae:3.84490
[600]	val-mae:3.79175
[700]	val-mae:3.75255
[799]	val-mae:3.72447        <- the cap, with val still falling ~0.03/100 rounds
```

`auto-on-v1` **hit its 800-round ceiling with validation error still dropping
steeply**, i.e. it is not a converged model, it is a truncated one. The scout had
already said as much: it proposed `n_estimators: 1635`, and the sniper's cap —
set at 800 as a DR-01 *budget* decision (§7, first bullet) — is less than half
of that.

M3-S5 must read that row as "xgboost, eta 0.062, stopped at 800 rounds", never
as "xgboost cannot do better than 3.7245". Whether the honest fix is a bigger
rounds cap (which costs DR-01 budget the track has already overspent — §6.5) is
**S5's call with the full table in front of it**, and it is named in §7 rather
than taken here.

**The v2 arm reached the same ceiling and it did not matter — and the prediction
this section made about that was half wrong, which is worth more than quietly
correcting it.** Written before `refit-v2` ran, the paragraph above said: *"the
v2 study's best trial early-stopped at iteration 351 of 800, so the same ceiling
is unlikely to have bound v2."* What the full-data refit actually printed:

```
Training until validation scores don't improve for 30 rounds
[600]	val's l1: 3.38314
[700]	val's l1: 3.38266
[800]	val's l1: 3.38232        <- the cap again; early stopping never fired
Did not meet early stopping. Best iteration is:
[791]	val's l1: 3.38228
```

So the ceiling **did** bind v2 in the literal sense — 800 rounds ran, the run
never early-stopped, and `best_iteration` is 791 only because the last nine
rounds were a rounding wobble rather than an improvement. But the two arms are
not in the same situation, and one number says so: v1 gained **0.02808 MAE**
between iterations 700 and 799, v2 gained **0.00034** between 700 and 800 — an
**~82× difference in slope at the cap**, measured off the two printed curves.
v1 was cut off mid-descent; v2 had flattened onto its floor and would
have bought roughly a thousandth of a minute for another 800 rounds. **A cap is
only a truncation if the curve is still moving under it**, and the same cap is a
truncation for one arm and a formality for the other. F-015's caveat therefore
does **not** double: it belongs in the `auto-on-v1` row and nowhere else.

**On v2, tuning won — narrowly, and the size of the win is the finding.**
`auto-on-v2` measures **3.3823 val MAE · 80.552% KPI-10** against the artisan's
hand-held-hyperparameter v2 at **3.3905 · 80.506%**: **+0.2436%** relative MAE
and **+0.046 points** of KPI-10, from a 21-trial search over nine hyperparameters
that cost **4,247.3 s** of DR-01 budget on this arm alone (scout v2 1,853.0 +
sniper v2 1,412.8 + refit v2 981.5) — more than the artisan track spent in total
across all six of its arms (3,313.9 s, §6.5). Set beside DR-02's own keep threshold
for a feature group — **≥0.50% relative val MAE** — the whole tuning axis on v2
buys **less than half of what this program requires of a single feature group
before it is allowed into the model.** Against the same v1 baseline both tracks
started from, features bought **+2.46%** and tuning bought **+2.70%** on top of
nothing (`auto-on-v2` vs hand-tuned v1, +0.859 KPI-10 points) — but the overlap
is what matters and §6.3's four rows are what let M3-S5 separate them. The
arithmetic of "features or tuning?" is S5's; this section reports its inputs.

Two more things are true of the v2 arm and neither is flattering to automation:
the tuner's winning family (**lgbm**) is the family the artisan was already
using, and its winning configuration needed **791 rounds where v1's hand-set 500
sufficed** — most of what it found was permission to run longer at a higher
learning rate.

### 6.5 The DR-01 budget ledger — measured, and over

DR-01 condition 1 asks for fitting wall-clock seconds per phase; condition 2
forbids handing a track more budget once its numbers are known. Here is what was
declared before any result existed (§0) against what was spent:

| phase | declared | measured fitting s | over/under |
|---|---:|---:|---:|
| scout on v1 | 1,800 | 1,954.5 | **+154.5** |
| scout on v2 | 1,800 | 1,853.0 | **+53.0** |
| sniper on v1 | 1,500 | 1,623.9 | **+123.9** |
| sniper on v2 | 1,500 | 1,412.8 | −87.2 |
| refit auto-on-v1 | ~1,700 (both refits) | 1,308.1 | — |
| refit auto-on-v2 | *(same line)* | 981.5 | **+589.6** on the pair |
| **six phases** | **8,300 declared total** | **9,133.8** | **+833.8 vs §0** |
| **the DR-01 share** | **9,000** | **9,133.8** | **+133.8 (+1.49%)** |

**The track exceeded its 9,000 s DR-01 share by 133.8 s — 1.49%.** The earlier
draft of this section, written with five phases landed, projected
**9,400–9,700 s** on the assumption that `refit-v2` would cost about what
`refit-v1` cost (1,308.1 s). It cost **981.5 s**, 25% less, because lgbm on 24
features is cheaper per round than depth-12 xgboost on 5 — so the projection was
wrong in the direction that flatters the track, and the measured total is
recorded here in its place. The overrun is real either way; it is smaller than
the guess.

Two things follow, and neither is a knob turned after the fact:

- **The overruns are per-phase and each has a mechanical cause.** FLAML's
  `time_budget_s` bounds its *search loop*, not the phase: the final retrain of
  the winning config on the full sample happens after the clock expires, which is
  the +154.5 s and +53.0 s. Optuna's budget is checked **between** trials, so the
  trial in flight when the cap passes runs to completion — v1's trials are
  expensive (depth 12 × 800 rounds, nothing pruned) and it overran by 123.9 s,
  while v2 pruned six trials and came in 87.2 s under. Both are "the cap is
  checked at a boundary" and both are now measured rather than assumed.
- **No phase was re-run and no budget was moved.** The overrun is reported at the
  size it happened. What it costs is a real asymmetry in M3-S5's 2×2 — the
  artisan track spent **3,313.9 s** and stopped on its own stop rule, the
  automation track spent **9,133.8 s = 2.76×** that and stopped because its clock
  ran out mid-search on both studies. DR-01 condition 2 makes an
  unequal-but-reported race a result, so S5 reports it: *the automation track was
  given the same budget, spent 2.76 times as much of it as the artisan did, ran
  out anyway, lost on v1 by 7.15% and won on v2 by 0.24%.*
- **The two tracks did not stop for the same kind of reason, and that is the
  asymmetry that survives normalisation.** The artisan stopped because its own
  keep rule said the next group was not worth having; the automation track
  stopped because a clock expired mid-search on both studies. Handing the second
  more seconds would change its numbers and handing the first more seconds would
  not — which is why DR-01 measured *seconds* but S5 must read *what ended each
  track*, not just what each spent.

### The one refusal path this track has

`taxi_mlops.tuning.space.SUPPORTED_FAMILIES` is `(lgbm, xgboost)`. FLAML's
`estimator_list` is deliberately wider — the scout is allowed to tell us
something we did not expect — so **if the scout names `rf` or `extra_tree`, the
sniper REFUSES** rather than quietly tuning the runner-up, because a sniper that
silently retargets is a sniper whose report does not describe what it did. That
would be a finding and a decision taken in the open, not a number.

## 7. Open, named, not silently carried

- **`auto-on-v1` was truncated by the rounds cap, and M3-S5 has to decide what
  to do about it — this session did not.** Its val curve was still falling
  ~0.03 MAE per 100 rounds at iteration 799 of 800 (§6.4). Raising the cap and
  refitting would very likely improve the number, and it would also spend DR-01
  budget the track has **already overspent** (§6.5) *after* seeing the result —
  which is the exact move DR-01 condition 2 forbids by name. So the row stands
  as measured, labelled as truncated, and the choice belongs to the bake-off
  session with the whole table in front of it. The cheap-looking option (refit
  it bigger and quote the better number) is the one that costs the 2×2 its
  meaning. **This applies to `auto-on-v1` alone**: `auto-on-v2` reached the same
  cap with its curve flat (§6.4, ~82× less slope at iteration 800), so it is
  capped but not truncated and needs no caveat in its row.
- **The v1 study is thin: 9 trials over an 8-dimensional space** (§6.2), all
  bound by the clock rather than by `n_trials: 60`. "Automation lost on v1" is
  therefore a statement about *this budget*, not about the method, and M3-S5's
  table should say so in the row rather than in a footnote.
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
  for S5 rather than assumed. Now narrower than it was: **the only xgboost row in
  the 2×2 is `auto-on-v1`, which is also its worst row** (3.7245), so the flavor
  path is unlikely to be exercised by a promotion at M3 — and "unlikely" is why
  it stays on this list instead of being struck off it.
- **`make train` still cannot fit a set that uses the point-in-time aggregates**
  (carried from M3-S3, `docs/ablation_m3.md` §7). v2 needs no fitted tables, so
  this track is unaffected.
