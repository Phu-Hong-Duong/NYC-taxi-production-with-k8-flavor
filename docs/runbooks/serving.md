# Runbook — the ETA endpoint (`serving/nyc-taxi-eta`)

**Owner: role:SRE. Written 2026-08-19 (M5-S5), against the deployment M5-S2
made and M5-S3/S4 measured.** Every number below was observed by a command in
this repo, and every command below was run — except the rollback, which is
TYPED and NOT REHEARSED, and says so twice.

Read `docs/gotchas.md` before the first `kubectl` of any session. The three
traps that bite hardest here are **#70** (a healthy controller suppresses the
header you were about to grep for), **#71** (a readiness wait the thing you are
replacing can satisfy is not a wait), and **#39** (two different MLflow faults
print the same `MLmodel` error).

---

## 0. What is on the wire

| Thing | Value | How to re-read it (never trust this table) |
|---|---|---|
| InferenceService | `serving/nyc-taxi-eta`, KServe **Standard / RawDeployment** (ADR-004) | `kubectl -n serving get inferenceservice nyc-taxi-eta` |
| Replicas | **1**, no HPA, **no canary** — Standard mode has none | `kubectl -n serving get deploy nyc-taxi-eta-predictor` |
| Runtime | `ClusterServingRuntime/taxi-mlserver` → `taxi-mlops-predictor:mlserver-1.7.1-lgb-4.7.0`, on all 3 nodes | `kubectl get clusterservingruntime taxi-mlserver -o yaml` |
| Model | whatever `models:/nyc-taxi-eta@champion` resolves to — **never a typed version** | `uv run python scripts/resolve_champion_storage.py --check` |
| Model store | MinIO bucket `mlflow-artifacts`, read by the least-privilege identity `serving` under policy `serving-readonly` | `kubectl -n serving get secret minio-serving -o name` |
| Route | host **8081** → ingress-nginx on `mlops-taxi-control-plane` → Host header `nyc-taxi-eta-serving.local` | `curl -s -o /dev/null -w '%{http_code}\n' localhost:8081/healthz` → `200` |

The route needs the Host header. Without it you get a 404 from nginx and it
looks like the model is down:

```bash
curl -s -H 'Host: nyc-taxi-eta-serving.local' \
  localhost:8081/v2/models/nyc-taxi-eta/ready -o /dev/null -w '%{http_code}\n'   # 200
```

---

## 1. Is it up? (in ascending order of what it actually proves)

```bash
kubectl -n serving get inferenceservice nyc-taxi-eta            # Ready True
kubectl -n serving get pods -o wide                             # 1/1 Running, and WHICH node
make quote                                                      # a PREDICTION, which is the only real answer
make quote QUOTE_ARGS="--at 2019-07-04T09:15:00 --pu 132 --do 48"
```

`make quote` is the check that matters (gotcha #59: assert on the artifact the
thing exists to produce). A `Ready` condition, a Running pod and a 200 from
`/ready` are all satisfiable by a pod that cannot load the model. The quote's
answer also carries `model_version`, stamped by mlserver on the response
itself.

Exit codes: **0 = quoted · 2 = REFUSED by the typed boundary** (an uncovered
date — see §6) **· 1 = anything else**.

---

## 2. Deploy / re-deploy

```bash
DRY_RUN=1 make serve     # prints every object and mutates NOTHING (gotcha #30)
make serve
```

`make serve` is idempotent and self-sufficient: it converges the MinIO identity,
the ClusterServingRuntime, the credential Secret and the InferenceService,
**resolves `@champion` itself** (never a typed version), waits on
`rollout status deploy/nyc-taxi-eta-predictor` *before* the InferenceService's
`Ready` condition (gotcha #71 — the old pod satisfies `Ready` on a re-deploy),
and finishes with a real prediction. It reads `@champion` before and after its
own work and **exits 2 if the alias moved underneath it**.

Observed on a no-op re-run (M5-S2): `unchanged`/`configured`, the SAME pod uid,
0 restarts.

---

## 3. Stop and start — REHEARSED 2026-08-19

Record: `automation/runs/m5-s5/stop-start.json` ·
re-runnable: `uv run python scripts/serving_stop_start_rehearsal.py`.

```bash
# stop — observed: the route stops answering in 3.12 s
kubectl -n serving annotate inferenceservice nyc-taxi-eta \
  serving.kserve.io/stop=true --overwrite

# start — observed: answering again 18.24 s later
kubectl -n serving annotate inferenceservice nyc-taxi-eta serving.kserve.io/stop-
```

What was observed, so you can tell a working stop from a broken one:

- **stop**: `Stopped` flips `False → True` and `Ready`/`PredictorReady`/
  `IngressReady` all go `False`; the Deployment's `spec.replicas` becomes
  **absent** (not `0`); the old pod lingers as `Completed`.
- **start**: a **new** pod (`…-qrd6f` → `…-xj2q6`, and it landed on a different
  node) reaches `1/1 Running`, and the route answers **18.24 s** after the
  annotation is removed.

**Do not** `kubectl scale` the predictor Deployment. The KServe controller owns
it and will put the replica back, so a scale-to-zero reads as "the outage fixed
itself", which is the worst possible thing for an operator to believe.

**18.24 s, not 14.53 s, and the difference is the mechanism.** A stop/start
recreates the Deployment's pod from scratch; losing a pod under load (§7) costs
**14.53 s** because the ReplicaSet reacts immediately. Both are the same order
of magnitude and both are a **full outage**: one replica, no canary.

---

## 4. Rollback to version 1 — TYPED, **NOT REHEARSED**

> **Not rehearsed.** These commands have never been run end to end on this
> cluster. M5 is legislated alias-neutral (kickoff law 2: `@champion` is
> version 2 and stays version 2), so rehearsing the rollback would have cost
> exactly the thing the milestone forbids. Treat the sequence as *argued and
> typed*, not as *proven* — the same honesty `scripts/platform_backup.sh` states
> about restore. **The first person to run it should record what actually
> happened, in this file.** A rehearsal is a named M6-gameday candidate.

### 4.1 A rollback here is NOT just a pointer move — this is the finding

`@champion` version 2 is `auto-lgbm-v2` and eats **24** features. Version 1 is
`lightgbm-v1` and eats **5**. The client builds its matrix from
`configs/train.yaml: features.version` (`taxi_mlops.features.sets.resolve` is
the only expansion in the program). So moving the alias alone gives you a
predictor that has loaded a 5-column model while every quote sends 24 columns —
MLflow's logged signature refuses it, and the rider gets a 500 from a system
whose every dashboard says `Ready`.

**You do not have to guess which feature set a version eats: the version says
so.** Every registry version carries a `feature_set` tag (`v1` on version 1,
`v2` on version 2), written at promotion time. Read it, don't remember it.

### 4.2 The sequence

```bash
# 1. WRITE DOWN what is serving now, before you change it.
uv run python scripts/resolve_champion_storage.py --check   # version, run_id, storage_uri

# 2. Read the target version's feature set FROM THE REGISTRY (never typed).
uv run python -c "
import mlflow
from taxi_mlops.training import tracking
from taxi_mlops.training.run import load_train_config
cfg = load_train_config(); tracking.configure(cfg['mlflow'])
mv = mlflow.MlflowClient().get_model_version('nyc-taxi-eta', '1')
print('version 1 eats feature set:', mv.tags['feature_set'], '| run', mv.run_id)"

# 3. Move the pointer. This is a RAW client call ON PURPOSE — see 4.3.
uv run python -c "
import mlflow
from taxi_mlops.training import tracking
from taxi_mlops.training.run import load_train_config
cfg = load_train_config(); tracking.configure(cfg['mlflow'])
mlflow.MlflowClient().set_registered_model_alias(
    name='nyc-taxi-eta', alias='champion', version='1')
print('champion ->', mlflow.MlflowClient()
      .get_model_version_by_alias('nyc-taxi-eta', 'champion').version)"

# 4. Move the config line WITH it (step 2's answer), and commit both together.
#    configs/train.yaml:  features.version: v1
$EDITOR configs/train.yaml
git commit -am "ops(rollback): champion -> version 1, feature set v1 (incident <id>)"

# 5. Put it on the wire. `make serve` resolves the alias, so it needs no argument.
make serve

# 6. Prove it, don't assume it.
make quote                       # answers, and stamps model_version: 1
make verify-m5                   # §2's coherence check is what catches a HALF rollback
```

### 4.3 Why step 3 is a raw MLflow call and not a `make` target

`registry.promote()` is the program's only alias-moving verb and it **refuses**
this on purpose: it requires a gate `Decision` and the `incumbent_version` that
decision consulted (F-011), because a pointer that can move without a verdict is
the whole risk M3-S1 closed. A rollback is a human overriding the gate during an
incident, which is exactly the act that should look unusual, be typed by hand,
and leave a commit behind. **Do not build a `make rollback` that bypasses the
gate** — M6 owns `make rollback` as the *rehearsed* revert, and it should still
be a deliberate, recorded act.

### 4.4 What a rollback drags behind it (do not skip this list)

- **Serving is inconsistent with everything published.** `data/predictions/`,
  the `error_segments` mart and the boards are stamped with version 2. Re-run
  `make predictions && make duckdb && make marts && make boards` (~17 min
  measured) or the warehouse describes a model that is no longer serving.
- **`make predictions` will REFUSE first** unless the floor it re-fits matches
  version 1's own `gate_floor` tag (`baseline-group-median`, which is *not*
  today's configured floor — F-012 by design). That refusal is correct; it is
  telling you the published rows and the serving model were argued against
  different bars.
- **Expect longer than 18.24 s to come back.** The storage-initializer must
  download a *different* prefix from MinIO. It is not cached on the node, and
  no measurement of it exists.
- **Rolling forward is the same procedure with `'2'`** — and version 2's
  `feature_set` tag says `v2`. Nothing about the sequence is one-directional.

---

## 5. If it is down — cheapest causes first

| Symptom | First check | Cause seen before |
|---|---|---|
| `kubectl` says `command not found` | is Docker Desktop running? | gotcha #34 — the symlink lives in a mount that only exists while the daemon does |
| 404 from `localhost:8081` | did you send the Host header? | §0 — nginx routes on it |
| `/healthz` fine, model 404 | `kubectl -n serving get pods -o wide` | a controller on the wrong node answers nothing (gotcha #52); ingress-nginx must be on `mlops-taxi-control-plane` |
| Pod `Init:0/1` forever | `kubectl -n serving logs <pod> -c storage-initializer` | **403 on `HeadBucket`** — MinIO's built-in `readonly` policy omits `s3:ListBucket`; ours is the custom `serving-readonly` |
| Pod `Running`, model never loads, `MLmodel` not found | `uv run python scripts/resolve_champion_storage.py --check` | **F-009**: a version's `source` is a RUN uri; the artifacts live under the LOGGED MODEL's `artifact_location`. A deploy that trusts `source` downloads an empty prefix and *succeeds* |
| Same `MLmodel` error, but `--check` also fails | `.env` credentials | gotcha #39's impostor — missing MinIO creds, not F-009 |
| 500 on every quote, `Can not safely convert` | the wire's dtypes | the logged signature is enforcing itself; do not strip the signature, fix the dtype |
| 500 on every quote after an alias move | §4.1 | a HALF rollback: pointer moved, `configs/train.yaml` did not |
| **422** with `covers through 2030` | the request's date | **not an outage** — F-019's typed refusal. `make holidays HOLIDAYS_TO=<year>` |
| `ImagePullBackOff` on the predictor | `docker exec <node> crictl images` | the predictor image is delivered by `kind load` to all three nodes; a new node has none |

---

## 6. What this endpoint refuses, on purpose

- **A date the holiday table does not cover** → `422`, `UncoveredDateError`,
  exit 2 from `make quote`. Refusing beats degrading: a quote built on invented
  holiday flags is a wrong number nobody can see is wrong (F-019). **The count
  of 422s per window is a named alert signal** — see the PRR minutes.
- **A non-finite feature value** → refused client-side rather than encoded.
  Missing geometry (zones 264/265, ~1% of trips) travels as `null`, which is the
  same missing value the booster was fitted on; an infinity is not a missing
  value and is not laundered into one (F-030).

---

## 7. What it costs when the pod dies

Measured 2026-08-19 (`make load-drill`, record
`automation/runs/m5-load/selfheal.json`): the predictor pod deleted mid-load →
**14.53 s unavailable**, **58 failed requests of 720** (56 × `503`, 2 × `502`),
then **559 requests with 0 errors**. The replacement was a **different pod
object by UID on a different node**.

Any event that replaces the predictor pod — a node drain, an image change, a
rollback, a `make serve` that changes the storageUri — costs about **fifteen
seconds of 503s**, because there is one replica, an init container that pulls
the model from MinIO, and **no canary** (Standard mode; `canaryTrafficPercent`
requires Serverless — M6's spike).

Load shape it holds today: **p50 17.2 · p95 104.2 · p99 107.2 ms at 4 req/s for
60 s, concurrency 8, hazard mix, 0 errors in 240 requests**
(`automation/runs/m5-load/headline.json`). A percentile without its shape is not
a number; quote them together or not at all.

---

## 8. What is NOT rehearsed (the honest list)

1. **The rollback in §4** — typed, argued, never run. M6 gameday candidate.
2. **Platform restore** from `make backup`'s dumps — never restored; every
   backup artifact says so (M4-S2).
3. **Canary / shadow / traffic shift** — no mechanism exists in Standard mode.
   M6 owns the spike and the decision.
4. **Node loss** — only pod loss has been drilled. The predictor image is on
   all three nodes, which is what makes a reschedule survivable, but nothing has
   tested a node going away.
5. **Sustained load beyond 60 s** and **any rate above 8 req/s** — the ceiling
   was measured (6 req/s = 96% of the CPU limit) and not exceeded.
