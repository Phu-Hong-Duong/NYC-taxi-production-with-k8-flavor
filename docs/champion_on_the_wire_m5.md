# M5-S2 — the champion on the wire

Story: **M5-S2** (`docs/milestones/M5_KICKOFF.md`), role **MLOps — Platform
Engineer**, SRE consulted on the F-019 policy (its reasoning is minuted here and
cross-referenced from M5-S5's PRR). Two ledger rows land: **F-009** and
**F-019**.

`@champion` is version **2** before this story and version **2** after it. The
deploy reads the alias on both sides of its own changes and exits 2 on a
difference; nothing here calls a mutating registry API, and a test parses both
the deploy and the resolver to keep it that way.

---

## 1. What is on the platform now

| Object | Value | Read back with |
|---|---|---|
| InferenceService | `serving/nyc-taxi-eta`, **Ready True**, url `http://nyc-taxi-eta-serving.local` | `kubectl -n serving get isvc` |
| Predictor pod | `nyc-taxi-eta-predictor-7ff5ccd649-pxkwr`, uid `f289b362-…`, node **mlops-taxi-worker2**, ready, **0 restarts** | `kubectl -n serving get pods` |
| ClusterServingRuntime | `taxi-mlserver` → `taxi-mlops-predictor:mlserver-1.7.1-lgb-4.7.0` | `kubectl get clusterservingruntime` |
| Model store identity | MinIO user `serving`, policy **`serving-readonly`** (custom, one bucket, no write verb) | `mc admin user list` / `mc admin policy info` |
| Route | `GET localhost:8081/` → **404** (no Host) · `GET /v2/health/ready` → **200** with the Host header | `curl` |
| Served version | mlserver stamps `model_version: "2"` on every inference response | the response itself |

The image is delivered by `kind load` onto all three nodes — D-001's mechanism,
and it is required rather than convenient here: M5-S4 kills the predictor under
load and the replacement may land on a different node.

---

## 2. The runtime, and why it is a derived image

The kickoff names *the mlserver/MLflow runtime*, and KServe's own kustomization
pins that to `docker.io/seldonio/mlserver:1.7.1-mlflow`. Two things were true of
this platform before a single manifest was written, and both were **measured, not
assumed**:

**(a) KServe v0.20.0 ships no runtimes at all.**

```
$ kubectl get clusterservingruntimes
No resources found
$ helm template kserve oci://ghcr.io/kserve/charts/kserve-resources --version v0.20.0 \
    | grep -c 'kind: ClusterServingRuntime'
0
```

Upstream keeps them as plain manifests in `config/runtimes/`, image-substituted
by a kustomization at release time. So a runtime is ours to declare either way —
and declaring it means the image is pinned in the same diff as every other pin
instead of arriving through a `newTag: latest` we do not control.

**(b) The stock image cannot load this champion.** One `docker run`, before
anything was installed:

```
$ docker run --rm -v /tmp/champion:/mnt/models:ro --entrypoint python \
    docker.io/seldonio/mlserver:1.7.1-mlflow \
    -c "import mlflow; mlflow.pyfunc.load_model('/mnt/models')"
FAILED: ModuleNotFoundError: No module named 'lightgbm'
```

It carries the sklearn/xgboost/mlflow runtimes and no LightGBM, so
`mlflow.lightgbm`'s `loader_module` has nothing to import. Adding the ONE package
at the version the champion's own `MLmodel` names (`lgb_version: 4.7.0`) makes
the same command print `LOADED … _LGBModelWrapper`. That probe is why
`docker/serving.Dockerfile` is four lines instead of an afternoon — the M4-S4
lesson about a cheap probe standing in front of an expensive run, one milestone
later.

### 2.1 The honest limit, stated because M5-S3 is about to measure it

The base runs **Python 3.10.12, pandas 2.2.3, numpy 2.2.6**; the champion was
fitted under **3.12.14 / 3.0.5 / 2.5.2**, and MLflow prints the mismatch as a
warning at every load. It is not fixable by pinning: mlserver 1.7.1 is built on a
Python 3.10 conda base, and `mlflow` (the full package its runtime needs) pins
`pandas<3` against our 3.0.5 — the exact conflict that made this program install
`mlflow-skinny` in the first place.

The reason it is a limit to measure rather than a defect to fight: **none of
those three libraries is on the numeric path.** The feature matrix is built by
`taxi_mlops.features` on the CLIENT side, so pandas/numpy build it exactly once;
the wire carries the matrix's own dtypes, so nothing is re-derived; and
`lightgbm` is **4.7.0 on both sides**, where `Booster.predict` on a float matrix
is the same deterministic C++ either way.

§5 turns that argument into a number. If M5-S3's parity comes back wide, this
paragraph is the first suspect and the honest answer is a predictor built on the
project's own image — never a looser bar.

---

## 3. F-009 — CLOSED by its row's option (b)

The row offers two closures: **(a)** make the bare alias URI loadable by fixing
what `registry.promote` records as `source`, or **(b)** prove the resolution step
is what serving needs too and record it as a documented property of MLflow 3.

**Gotcha #39's discriminator was run first**, because it costs one call and the
impostor (missing MinIO credentials) prints an artifact-shaped error too:

```
$ uv run python scripts/resolve_champion_storage.py --check
[resolve] F-009 CONFIRMED (not its impostor): get_model_info(models:/nyc-taxi-eta@champion)
          SUCCEEDS while load_model on the SAME uri fails — MlflowException: No such artifact: 'MLmodel'
[resolve] so this is MLflow 3's logged-model layout, NOT a credential problem
          (gotcha #39: under missing MinIO credentials BOTH calls fail).
{
  "version": "2",
  "run_id": "92b73bd4f77d4a05b92472bfcfb3cccf",
  "registry_source": "runs:/92b73bd4f77d4a05b92472bfcfb3cccf/model",
  "logged_model_uri": "models:/m-04478c4795474ecc81756f74398dc1a3",
  "storage_uri": "s3://mlflow-artifacts/6/models/m-04478c4795474ecc81756f74398dc1a3/artifacts"
}
```

**(a) is not available, and that is a fact rather than a preference.** A
version's `source` is set when the version is CREATED and MLflow exposes no way
to change it. Making it right would mean registering a NEW version — which is
exactly what M5 is legislated not to do (kickoff law 2). And it would fix one
version while leaving every earlier one — including **version 1, the rollback
target M5-S5's typed rollback depends on** — pointing at the same empty prefix.

**(b) is what happened, and it is a stronger statement than "the workaround still
works".** A deploy that trusted `source` would hand KServe
`s3://mlflow-artifacts/6/92b73bd4f77d…/artifacts/model`, a prefix with nothing
under it — MLflow says so itself while resolving:

```
INFO mlflow.store.artifact.artifact_repo: No artifacts found to download at
s3://mlflow-artifacts/6/92b73bd4f77d…/artifacts/model. Returning destination path.
```

KServe's storage-initializer would download zero objects and **succeed** — there
is no error in "the prefix is empty" — and mlserver would then fail on a missing
`MLmodel`. That is F-009's exact signature at the serving boundary: an
artifact-shaped error about a model that is perfectly fine.

**The property, written so it can be checked rather than remembered:** on
MLflow 3, a registered model version's `source` is a RUN uri while its artifacts
live under the LOGGED MODEL's `artifact_location`. Every consumer that needs
bytes — loader, scorer, serving runtime — must resolve
`alias -> logged model -> artifact_location`, and none of them may read `source`.

The serving path resolves it in **one place**
(`scripts/resolve_champion_storage.py`), exactly as the training path does in
`taxi_mlops.training.score.load_champion`. Neither ever names a bucket, a run id
or a logged-model id, and a test refuses those literals in any committed serving
file.

---

## 4. F-019 — CLOSED, and the decision is BOTH halves

The champion eats `is_holiday`/`is_near_holiday`/`is_business_day`, built from a
committed table that held ten rows, all 2019. `features/` is the ONE path for
training and serving, so the raise that keeps training honest was a 500 on every
quote dated outside 2019.

### 4.1 The decision

**Both**, because each alone is unshippable.

**Half 1 — the table was extended to 2030, from the statute.**
`scripts/derive_us_federal_holidays.py` computes 5 U.S.C. §6103 and
`make holidays` writes it; the table is still a committed CSV a reviewer can read
(the decision `features/calendar.py` recorded at M3-S3 and this keeps). Extending
alone is not a fix: a table always ends, and the day it ends the failure is
exactly the one we set out to remove — only later, and to somebody who was not
told it could happen.

**Half 2 — the boundary is typed.** An uncovered date raises
`taxi_mlops.serving.client.UncoveredDateError`, a `QuoteRefused` carrying
`http_status = 422`, before a request is built and before anything reaches the
wire. `make quote` exits **2** on it — its own code, because "I will not answer
that" and "I could not answer" are different facts and a caller that cannot tell
them apart retries the one that never succeeds.

### 4.2 Refuse, not degrade-and-flag — the SRE half (cross-referenced by M5-S5's PRR)

The two options differ in KIND, which is why this is minuted rather than settled
by taste.

*Degrade-and-flag* returns a **wrong quote**: the caller gets a number, the rider
gets a time, and nothing in the system knows the holiday flags were invented. It
is an unbounded, silent error whose size depends on how holiday-sensitive the
route is — and the flag would have to be carried through the V2 payload, the
response and every consumer to be worth anything. A flag nobody reads is a
degradation with a comment on it.

*Refuse* is a visible, countable, alertable failure confined to dates nobody has
entered yet, with a fix named in the error text (`make holidays HOLIDAYS_TO=…`).
It is also what `features/calendar.py`'s own raise was written to prevent: a
silent "not a holiday" for an uncovered year looks exactly like a correct answer.

A quote-time ETA has one job — to be a number somebody can rely on. A silently
wrong one is worse than none. **M6's alert plan gains a named signal from this:
the count of 422 refusals per window, which is a leading indicator with a fixed,
one-command remedy.**

### 4.3 Where the boundary lives, honestly

In M5 the features are built client-side, so the refusal happens in the client
and the "422" is a property of the type rather than of an HTTP response the
cluster emits. `http_status` is carried now so M7's KServe transformer — which
moves feature building into the pod — is a change of transport and not a change
of contract.

### 4.4 The evidence that no measured number moved

The extension is **136 insertions, 0 deletions**: not one 2019 row changed. Two
stronger checks than reading that diff:

* **The rules reproduce the ten hand-written 2019 rows byte for byte.** Those
  rows were written by a human from the published federal calendar at M3-S3,
  months before the deriver existed, so agreement is evidence about the RULES —
  including the one most easily got wrong, Juneteenth, which is federal only from
  2021 and is correctly ABSENT from 2019.
  ```
  $ uv run python scripts/derive_us_federal_holidays.py --year 2019 --stdout | diff data/reference/us_federal_holidays.csv -
  IDENTICAL — the statutory rules reproduce the ten hand-written 2019 rows byte for byte
  ```
* **The holiday and near-holiday SETS inside 2019-01-01..2019-08-31 are
  unchanged**, asserted directly in `tests/unit/test_holidays.py` rather than
  inferred from the diff — because a near-holiday day can be introduced by a row
  in a different year entirely (2019-12-31's neighbour is 2020-01-01).

### 4.5 Two decisions inside the deriver, recorded rather than assumed

1. **A weekend holiday emits TWO rows**, the statutory date and the observed day
   off (`Independence Day` + `Independence Day (observed)`). §6103(b) moves the
   day off; the statutory date is when the city celebrates. Both are anomalous
   for a duration model and picking one would be picking which anomaly to be
   blind to. **No 2019 holiday falls on a weekend**, so this changes no measured
   number — checked, not assumed.
2. **The horizon is 2030 by default**, moved by one flag. A longer default is a
   bigger claim about a statute that changed as recently as 2021. The wall is
   real either way, which is why §4.2 types it instead of relying on the table
   being long enough.

### 4.6 The M4-S1 tripwire, re-pinned in the same PR

The tripwire pinned the BROKEN behaviour on purpose. It is replaced here by two
assertions that fail if either half of the fix is undone: a request dated today
builds the full matrix (the table half), and a request past the horizon still
raises (the guard half). The horizon is READ from the table, never typed, so
moving it does not orphan the test — F-017's rule.

---

## 5. The acceptance transcripts

### 5.1 A 2019-dated request, through the declared route

```
$ make quote
[quote] served by nyc-taxi-eta version 2 via http://localhost:8081/v2/models/nyc-taxi-eta/infer (Host: nyc-taxi-eta-serving.local)
[quote] 2019-07-04T09:15:00  zone 132 -> 48, 1 passenger(s)  ->  39.0019 minutes
```

The version is read **off this response** and not off a metadata call: mlserver
stamps `model_version` on the very answer being printed, so it cannot describe a
different moment than the number beside it. (`GET /v2/models/nyc-taxi-eta`
reports `versions: []` — the metadata endpoint and the response stamp are
different fields, which is why the response is the one that is read.)

### 5.2 It matches the locally-loaded champion — ONE row, and NOT the gate

```
endpoint says model_version='2'; the registry alias resolves to version 2
online  (mlserver, in-cluster) np.float64(39.00193715359812)
offline (this process)         np.float64(39.00193715359812)
|delta|                        0.000e+00
```

**Bit-for-bit**, not merely within 1e-6 — which is what §2.1's argument
predicted and is the first real evidence for it. This is **one row, run once**.
`make parity` at 1e-6 over rows chosen to span the honest hazards is **M5-S3's**,
and this spot check must not be allowed to stand in for it.

### 5.3 A 2026-dated request — the table half of F-019

```
$ make quote QUOTE_ARGS="--at 2026-08-19T09:15:00"
[quote] served by nyc-taxi-eta version 2 …
[quote] 2026-08-19T09:15:00  zone 132 -> 48, 1 passenger(s)  ->  63.7881 minutes
```

Before this story that request raised. (What the number MEANS is a separate
question this story does not answer: a 2019-fitted model quoting a 2026 date is
extrapolating, and nothing about a correct holiday flag changes that. It is
noted for M7's drift work, not claimed as accuracy.)

### 5.4 A 2031-dated request — the typed half

```
$ make quote QUOTE_ARGS="--at 2031-08-19T09:15:00"
[quote] REFUSED (422): this deployment cannot quote for [2031]:
        data/reference/us_federal_holidays.csv covers through 2030, and the champion eats
        holiday flags. REFUSED rather than guessed — a quote built on invented holiday
        flags is a wrong number nobody can see is wrong (F-019).
        Extend the table: `make holidays HOLIDAYS_TO=2031`.
exit 2
```

### 5.5 Idempotent re-run — the M4-S2 shape, proved by pod identity

```
== [4/7] the ServingRuntime ==
clusterservingruntime.serving.kserve.io/taxi-mlserver unchanged
== [6/7] the InferenceService ==
inferenceservice.serving.kserve.io/nyc-taxi-eta configured
deployment "nyc-taxi-eta-predictor" successfully rolled out
NAME                                      READY   STATUS    RESTARTS   AGE
nyc-taxi-eta-predictor-7ff5ccd649-pxkwr   1/1     Running   0          2m1s
…
ok  @champion is version 2 — the same version this script read before it started
```

Same pod, same uid, 0 restarts, 2m1s old across a full re-run: a clean converge
that restarted nothing.

`DRY_RUN=1 make serve` prints the seven-step plan and returns before any
mutating verb; a test asserts that by stripping `echo` and assignment lines and
searching what is left.

---

## 6. The credential: least privilege AND sufficient

The predictor reads MinIO as a **new** identity, `serving` — the Flyte-bucket
precedent: a leaked serving credential must not be able to write the registry's
artifacts. It is the credential most exposed by construction, because it lives in
the namespace a predictor pod runs in and travels with every restart, kill drill
(M5-S4) and rollback rehearsal (M5-S5).

**MinIO's built-in `readonly` is not enough, and it fails in a way worth writing
down.** The first deploy went red:

```
S3 error for s3://mlflow-artifacts/6/models/m-04478…/artifacts:
An error occurred (403) when calling the HeadBucket operation: Forbidden
```

A 403 on a user that exists, under a policy called "readonly", reads exactly like
a wrong password. The cause, read off the server rather than guessed:

```
$ mc admin policy info l readonly
{"Statement":[{"Effect":"Allow","Action":["s3:GetBucketLocation","s3:GetObject"],
  "Resource":["arn:aws:s3:::*"]}]}
```

No `s3:ListBucket` — which is what the storage-initializer HEADs the bucket with
and then lists the prefix with. The replacement is a custom policy, and it is
**strictly better than what it replaces** rather than a workaround: it grants
`GetObject` + `GetBucketLocation` + `ListBucket` and nothing that can change a
byte, and it is scoped to **one bucket**, so this identity cannot see
`flyte-data` at all. That retires the bucket-wide caveat recorded on the `flyte`
user for its own row.

The predictor reaches MinIO by its **in-cluster** name
(`minio.platform.svc.cluster.local:9000`). F-023's lesson from the other side:
split horizon is the host's problem and never a pod's.

---

## 7. Defects found and fixed in this story

| # | What | Why it is worth a line |
|---|---|---|
| 1 | The resolver's `[mlflow]` banner went to **stdout**, so the caller's `json.load` died on `Expecting value: line 1 column 2` | A script that is meant to be read by a shell must keep stdout for the payload. Fixed by redirecting every human-facing line to stderr — the banner is worth having and it is diagnostics, not data |
| 2 | The V2 payload sent **FP64 for all 24 features** → `500: Can not safely convert float64 to int32` | MLflow enforces the signature the model was LOGGED with and refuses a lossy cast. That refusal is the signature doing its job; the fix was to stop lying about the types, not to strip the signature. Sending real dtypes also removes a float32 round trip from the geometry columns — one fewer place for M5-S3's 1e-6 to survive |
| 3 | **A false green: the accept check interrogated the pod it was replacing.** On a re-deploy the InferenceService's `Ready` condition is satisfied by the pod ALREADY SERVING, so `kubectl wait --for=condition=Ready inferenceservice` returned instantly while the new pod was `Init:0/1` — and the quote came back from the predecessor reporting `(unversioned)` when the version stamp was the change under test | Sibling of gotchas #59/#65: **a wait that the thing you are replacing can satisfy is not a wait.** Fixed by waiting on `rollout status deploy/…-predictor` FIRST — the new ReplicaSet specifically — and keeping the ISVC condition as the second leg |
| 4 | The new test's own DRY_RUN check went red **twice on prose and on an assignment**: the banner says `WOULD helm upgrade minio …` and `HELM=(helm --kube-context …)` builds the array | Gotcha #68 for the fifth and sixth time. A needle about RUNNING a command must sit where a shell would START one — neither an `echo` nor an assignment is such a place. Fixed with an `invocations_only()` helper beside `code_only()` |

Item 3 is the one to remember. Items 1, 2 and 4 announced themselves loudly;
item 3 printed a passing accept check over a stale pod, and only the version
stamp — the thing being changed — disagreed.

---

## 8. What this story did NOT do

* **No parity gate.** §5.2 is one row. `make parity`, its red team, and the 1e-6
  bar are M5-S3's.
* **No load measurement.** The predictor's `resources` are a starting point, not
  a measurement, and the single worker (`MLSERVER_PARALLEL_WORKERS=0`) is stated
  out loud so M5-S4's p95 is a number about a known shape.
* **No canary, no rollback rehearsal.** Standard mode has no canary (ADR-004);
  the typed rollback and its runbook are M5-S5's, and version 1 exists in the
  registry for exactly that.
* **No alias move, no new registry version.** Version 2 before and after, read by
  the script on both sides.
