# M4-S4 — F-023 broken open, and the six stages running on the cluster

Session: EXECUTOR / `claude-opus-5`, role:MLOps (A) · MLE (R), 2026-08-18.
Story: `docs/milestones/M4_KICKOFF.md` § M4-S4.

**Where the cut is, stated first.** The plumbing is DONE and PROVEN: F-023 is
closed, the task image runs the real stages on kind nodes, data reaches them, the
verdict comes back as data, and `@champion` is untouched. What this session did
NOT land is the kickoff's **full-data green run** and the **cache-hit rerun** —
the full-data run is hours-class and is therefore detached (gotcha #45, ritual e),
and the cache-hit rerun is its successor's first command. §7 says exactly what the
next session inherits.

> **§9–§11 were added by the SECOND M4-S4 session (2026-08-18, later the same
> day), which landed both of those legs. §1–§8 are left UNEDITED as the first
> session's record** — the M3 precedent: a document that silently rewrites its own
> numbers cannot be compared against the decisions made from them.

**The cluster never went down.** No `kind delete`/`create`, no kind-config edit,
no new hostPort. `@champion` read before and after every run: **version 2**,
unchanged.

---

## 1. F-023 — the finding was right about the disease and wrong about the cure

M4-S2 walled at 5 attempts with the diagnosis "the blob store is ONE MinIO with
TWO names", and recorded three probes in order. Probe 1 paid; probe 2 turned out
to be **impossible on this machine**, and that is worth more than the fix.

**Probe 1 — what does the server actually hand the client?** The upload is not
the client building a URL. `flyte/_persistence/_remote_upload.py` and
`flyte/remote/_data.py` both ask the control plane's `DataProxyService` for a
`CreateUploadLocation` and then PUT to the **`signed_url` the server returns**:

```
CreateUploadLocationResponse fields: ['signed_url', 'native_url', 'expires_at', 'headers']
```

That single fact explains M4-S2's most confusing observation — that setting
`FLYTE_AWS_ENDPOINT` "did not change the symptom". Of course it didn't. Those
variables configure the SDK's own storage client; the code-bundle upload never
constructs a URL, it is handed one, already signed, minted by a server whose
`storage.stow.config.endpoint` is `minio.platform.svc.cluster.local:9000`.

**Probe 2 — "one name both sides can resolve" — does not exist here.** The
finding proposed the kind node's docker-bridge address plus MinIO's nodePort.
Measured from WSL:

```
node-ip:30900   -> 000
node 172.19.0.3:6443 -> 000
kubectl's server: https://127.0.0.1:35553
```

The node IPs are not routable from this side at all — even the apiserver is
reached through a docker-**published** port on loopback. Under Docker Desktop on
WSL2 there is no address that both the host and a pod resolve to the same MinIO.
The probe's premise was false, and a session following the recorded plan would
have spent its budget proving that.

**The fix: sign for the client, serve for the pods.** `storage.signedUrl.
stowConfigOverride` is flytestdlib's lever for exactly this split horizon — the
same one Flyte **1.x** exposes and whose absence from the 2.x chart M4-S2 flagged
as "either the reason to fall back or the hint for where 2.x hides it". It was the
second. The chart renders no value for it, but the 2.x **binary** carries it:

```
$ kubectl -n flyte exec deploy/flyte-flyte-binary -c flyte -- \
    sh -c 'grep -ao "stowConfigOverride" /usr/local/bin/flyte'
stowConfigOverride
```

so it goes in through the chart's `configuration.inline`, which lands as its own
config file beside the chart's own — both present, neither clobbered:

```
=== 003-storage.yaml ===        endpoint: http://minio.platform.svc.cluster.local:9000
=== 100-inline-config.yaml ===  storage: signedUrl: stowConfigOverride: endpoint: http://localhost:9000
```

**ADR-002's fallback was NOT executed and is still armed.** Its trigger is "Flyte
2.x fights on deployment or MLflow interop"; deployment succeeded at M4-S2 and the
2.x line turned out to carry the lever after all. Swapping charts would have been
the expensive answer to a one-line question.

## 2. The hello-workflow, and the assertion that was measuring nothing

With the signing endpoint fixed the upload completed on the first try — and the
run still "failed", for a reason that had been latent since M4-S2:

* `flyte run` **launches and returns**. The script asserted its greeting against
  the launch output, so it could never have passed. `--follow` waits for a
  terminal state.
* `--follow` streams **logs**, and these tasks log nothing — they RETURN a value.
  Grepping the follow output would fail a perfect run, and (worse) would pass for
  a task that PRINTED the string without returning it.

So the verdict is read from the run's outputs, out of the blob store:

```
[flyte-hello] run rp5bmwqvd6zsc22vl4n2 — reading its outputs back
│ Outputs                                               │
│ ActionOutputs(o0="HELLO CROSSTOWN FROM A FLYTE TASK") │
[flyte-hello] ok  two tasks ran on-cluster and the second consumed the first's output
[flyte-hello] ok  the value came back through the flyte-data bucket, not off a log line
```

Three pods, all `Completed`: `a0` (main) and the two child actions. **F-023's
close condition is met by its own words** — two tasks, the second consuming the
first's output through the blob store, which is what makes it a seam test rather
than a pod-ran test.

## 3. What a task pod needs, and the three places that do not provide it

The hello task needs nothing but a CPU. The real stages need MinIO, MLflow and
the data, and the first pipeline run found that **none of the existing storage
configuration reaches the process that runs our code**:

```
OSError: Generic S3 error: Error performing PUT http://169.254.169.254/latest/api/token
```

That is the EC2 instance-metadata address. The flyte-binary ConfigMap configures
the SERVER; the copilot Secret configures the co-pilot SIDECAR; the values overlay
configures helm. The Flyte 2 python runtime inside the task container builds its
own `flyte.storage.S3` from ITS OWN environment, and with none set it fell through
to the default AWS credential chain. The task ran perfectly and then had nowhere
to put its result.

The answer is a **named PodTemplate** (`infra/manifests/flyte-task-podtemplate.yaml`),
referenced once by `plugins.k8s.default-pod-template-name` and by each
`TaskEnvironment`. It carries the storage identity, the MLflow route, the data
volume and the pull policy — so a task added at M7 inherits all of it by naming
one string, and `pipelines/flyte/workflows.py` carries no endpoint at all. The
container must be named `default`: that is the k8s plugin's contract for
"defaults merged into the primary container".

**The merge risk was checked rather than assumed.** `configuration.inline` adds a
`plugins.k8s` block, and if it had REPLACED the chart's the task pods would have
lost `_U_EP_OVERRIDE` — the variable by which a task reaches the control plane to
enqueue its children. Read off a live task pod:

```
FLYTE_AWS_ENDPOINT  FLYTE_AWS_ACCESS_KEY_ID  MLFLOW_TRACKING_URI  MLFLOW_S3_ENDPOINT_URL
… _U_EP_OVERRIDE  _U_INSECURE  _U_USE_ACTIONS
```

Both sets present: it deep-merged.

## 4. How the data reaches a task, and the option that was rejected

Decision and full argument: `infra/manifests/flyte-task-data-pvc.yaml`. In short —
`kind extraMounts` is a config edit and therefore a rebuild, which the
statefulness law forbids. **Tasks-read-from-MinIO** is the option M7 will
eventually want and was rejected HERE for a specific reason: every path in
`taxi_mlops.data` and `taxi_mlops.training` is a local filesystem path, so it is
not a platform change but a rewrite of the data layer's IO, in the milestone whose
premise is that `src/` does not move.

So: a **PVC, staged once, mounted into every task pod**, and `taxi_mlops` reads
`data/...` exactly as it does on the laptop — which is the property that makes an
on-cluster number comparable to a host number at all.

```
== stage pipeline data ==
[stage-data] source: 1.8G across raw processed rejected
[stage-data] ok  raw: 8 file(s) on the volume == 8 on the host
[stage-data] ok  processed: 16 file(s) on the volume == 16 on the host
[stage-data] ok  rejected: 8 file(s) on the volume == 8 on the host
[stage-data] ok  stager removed; the volume and its data remain
```

**Mounted by subPath, not at `/app/data`** — gotcha #58's trap, avoided by having
been paid for once already. `/app/data` in the image is not empty: it holds the
committed `data/reference/` lookup tables the feature path reads. A single mount
there would produce an image that imports every module perfectly and cannot build
a feature. The check is per-tree **file counts**, not sizes, because a stream
killed halfway leaves a tree that exists and is wrong.

## 5. The green run — six stages, on-cluster, sampled

`make pipeline MONTH=2019-01 TRAIN_MONTHS=2019-01` (run `r5kzpr785rt8m6tn9b7l`):

```
[pipeline] SAMPLED run (train months: 2019-01) — F-008: no verdict will be issued
[pipeline] task image taxi-mlops-pipeline:cde60b2
[pipeline] @champion before: 2
[flyte] ingest 2019-01 (train): 7,696,617 -> 7,584,656 rows, 1.4547% rejected -> /app/data/processed/train/yellow_tripdata_2019-01.parquet
[flyte] validate 2019-01: 7,584,656 rows, contract_year 2019, 20 columns
[flyte] features 2019-01: 7,584,656 rows, set v2, 24 features
[flyte] train lightgbm-v1 (set v2): run e17ce5846aaf4f90bee8a2609b208c94, 869.7s, sampled=True judged=False months=2019-01
[flyte] evaluate lightgbm-v1 val:  KPI-09 3.5983 min over 6,189,748 rows (source taxi_mlops.training.evaluate)
[flyte] evaluate lightgbm-v1 test: KPI-09 3.3713 min over 5,950,708 rows (source taxi_mlops.training.evaluate)
[flyte] register decision=NO_VERDICT promoted=False (CLI exit-code class 3)
[pipeline] @champion after:  2
[pipeline] ok  @champion unchanged at 2
[pipeline] ok  run r5kzpr785rt8m6tn9b7l completed; six stages on-cluster for 2019-01
```

Run output, read back out of the blob store:
`ActionOutputs(o0="{"decision": "NO_VERDICT", "promoted": false, …}")`.

**The strongest number here is the ingest line.** `7,696,617 -> 7,584,656 rows,
1.4547% rejected` is M4-S1's host rehearsal reproduced **to the row and to four
decimals**, by the same code in a container on a different machine's kernel. The
model numbers are NOT results and are not claimed as any: this is one train month
(F-008), which is why the register stage returns `NO_VERDICT` rather than a
flattering margin.

**The refusal is the point of the last line.** A sampled run produced a green
pipeline AND no verdict — "not judged" and "judged and satisfied" stayed
distinguishable, as data, in the run's own output.

## 6. Five defects, and four of them were in the checkers

Recorded because the pattern is now this program's most expensive one (gotchas
#50/#51/#54/#55/#56).

1. **`make pipeline` printed `ok … six stages on-cluster` over a DEAD run.**
   `flyte run --follow` **exits 0 when the run it followed FAILED**. Every signal
   was consistent with success — exit code 0, a run name, a readable outputs
   blob. The only difference was the outputs' CONTENT (`ActionOutputs(o0=None)`).
   Fixed with a POSITIVE assertion on the thing the pipeline exists to produce:
   the outputs must contain a `"decision"`. That is strictly stronger than
   checking a phase string, and it immediately caught the next three failures
   instead of painting them green.
2. **The alias check compared a paragraph to itself.** `champion_alias()`
   captured `tracking.configure()`'s three-line banner along with the version, so
   "before" and "after" were equal blobs and the check could not fail. Visible
   only because the transcript printed a paragraph where a version goes.
3. **Backticks in a heredoc comment are command substitution.** The stager pod
   was a heredoc whose own explanatory comments named `tar`, `du` and a docker
   command in backticks; the shell RAN them and spliced their output into the
   YAML, which then failed to parse on a line unrelated to the problem. The pod
   is a manifest file now — which is also where the MLOps charter wanted it.
4. **`KPI-10 7917.017%`.** `:.3%` applied to a rate the evaluator already
   multiplied by 100. Nothing was wrong with the model; the log claimed the
   pipeline quoted 79× more trips correctly than there were trips.
5. **The `.env` requirement no code had ever exercised** (§7 of this list is
   really a src/ fix): `tracking.configure`'s docstring has said since M2-S2 that
   "an in-cluster caller (M4's Flyte task) exports the cluster DNS names and needs
   no code change" — but `load_env` refused on the file's absence before
   precedence could apply. The image contains no `.env` and must not. A missing
   file is now an empty source; the refusal moved to a value that no source
   supplies, and the banner now names the source it actually used.

## 7. F-025 (NEW, closed here) — MLflow refused every in-cluster client

```
MlflowException: API request to endpoint /api/2.0/mlflow/experiments/get-by-name
failed with error code 403 != 200. Response body:
'Invalid Host header - possible DNS rebinding attack detected'
```

MLflow 3.x runs under uvicorn with DNS-rebinding protection that checks the Host
header against `MLFLOW_SERVER_ALLOWED_HOSTS`. The chart derives that list from an
ingress; this release has none, so the effective list covered the loopback names
and nothing else. **Every MLflow client this program had until M4 was host-side,
so the gap was invisible for four milestones** — and it surfaced mid-fit, from an
endpoint that reads like an MLflow problem and is a network-policy one.

Fixed in `infra/helm/mlflow/values.yaml` by listing the names **explicitly** —
`["*"]` would delete the protection rather than configure it.

**And the first version of that fix broke the host route**, which is the part
worth keeping. Setting the value at all REPLACES MLflow's default list, and the
middleware compares the **whole header, port included**. Bare hostnames fixed the
pod and gave every host-side client the same 403. The two-line experiment that
found it:

```
curl localhost:5000/api/2.0/mlflow/experiments/search   -> 403
curl -H 'Host: localhost' 127.0.0.1:5000/health         -> OK
```

Both forms are listed now, and both routes are green: host `200`, in-cluster `OK`.

## 8. What the next session inherits

**Not done, and precisely why**: the kickoff's green run is FULL-DATA (six train
months, ~44M rows). The sampled run above spent **869.7 s in the train stage on
one month**; the full set is hours-class, so it runs detached
(`automation/run_detached.sh`, gotcha #45) rather than inside a session that would
kill it. The **cache-hit rerun** is the second leg and needs run 1 finished first.

Ready and unblocked for it:

* `make pipeline` (full-data by default — omit `TRAIN_MONTHS`), `make stage-data`
  (idempotent; skips when the volume already holds the trees), `make flyte-hello`
  as the 3-minute seam check if anything looks wrong with Flyte itself.
* The data is already on the PVC — staging does not need repeating.
* **The image tag is the git sha**, so any commit invalidates it: if a task pod
  reports `ImagePullBackOff` on `taxi-mlops-pipeline:<sha>`, the tree moved —
  re-run `make image-load` (~40 s warm) and re-run the pipeline.
* `automation/runs/m4-pipeline/pipeline_run.json` holds the last run's name,
  month, image ref, judged flag and the alias read after it.
* M4-S5 (kill-a-pod drill, D-003's marts tail task, `verify-m4`) is unblocked by
  everything above except its need for a completed FULL-DATA run to check.


---

# Added 2026-08-18 (second M4-S4 session) — the full-data run, read back; and the cache

## 9. What the full-data run actually did, recovered from the server

The detached full-data run (`rhgfld7j6qvqrzbrzl6v`) finished **DONE 0** at
10:04Z — and its log holds almost nothing, because `flyte run --follow` streams
the *parent's* log and reported `Scrolled 2 lines of logs`. The per-stage
transcript §5 shows for the sampled run does not exist for this one.

It did not need to. The control plane recorded every action, and
`scripts/flyte_run_actions.py` (new, §10) reads them back:

```
  a0                         main             SUCCEEDED  CACHE_DISABLED      1909.7s
  cf17y4l3o0w1ezz20fesd7n85  ingest           SUCCEEDED  CACHE_DISABLED        14.4s
  bubrkhgpmdqfk04g3x113g4xj  validate         SUCCEEDED  CACHE_DISABLED         5.4s
  ewu9a6k5a3ykro31o3kzb6vbx  build_features   SUCCEEDED  CACHE_DISABLED         7.4s
  593vd4l64mxzbpinzk5ish51h  train            SUCCEEDED  CACHE_DISABLED      1874.7s
  7ac9jg8sysloqa1zz1b7g9py9  evaluate         SUCCEEDED  CACHE_DISABLED         3.7s
  5lnc5roda8ycuhkxgk0yzsmjh  register         SUCCEEDED  CACHE_DISABLED         3.7s
```

**Six stages, on-cluster, full data, 31m50s — of which the fit is 31m15s and
everything else together is 34.6 seconds.** That ratio is the whole argument for
caching this pipeline: 98.2% of the cost is one stage, and it is the stage whose
inputs change least often.

And the run's output — the gate's verdict, as data:

```
{"decision": "REFUSE", "promoted": false,
 "reason": "--no-promote: the verdict stands recorded and the registry is untouched",
 "margins": {"challenger_mae": 3.242513399356197, "floor_mae": 3.351759301862344,
             "observed_pct_vs_floor": 3.2593600156624087, "required_pct_vs_floor": 2.0,
             "challenger_within_rate": 81.58227558804766,
             "floor_within_rate": 80.73345222114746},
 "champion_alias_version": "2"}
```

**Read that REFUSE carefully, because it is the gate working, not failing.** The
challenger cleared the FLOOR condition comfortably — +3.26% against a 2.00% bar.
What refused it is F-011's **incumbent** condition: `configs/train.yaml` names
feature set v2 and the pipeline fits it with v1's hyperparameters, which is M3's
`artisan v2` — and `artisan v2` measured **3.2425** on the holdout against the
serving champion's **3.2403**. The pipeline re-derived M3-S5's bake-off number to
four decimals, on the cluster, in a container, and was then refused for being
0.07% worse than what is already serving. A pipeline that promoted here would
have been the defect.

**One honest gap in that output, named because it is the shape of a future
incident**: `margins` carries the floor numbers and not the incumbent's, so the
JSON shows a decision of REFUSE beside a floor margin that PASSES, and the reader
has to know M3-S1 to reconcile them. `pipelines.tasks.register` builds that dict;
the decision object it reads has the incumbent checks in it. Not fixed here — it
is a change to the register stage's output contract, which `verify-m4` (M4-S5)
is about to start asserting against, and changing a shape one story before the
gate that pins it is how twins get born. Carried to M4-S5 by name.

## 10. The cache-hit rerun: what is cached, what refuses to be, and who is asked

`make pipeline-cache-drill` runs the same invocation twice and then asks **three
independent systems** whether the second run reused the first, because each one
alone is refutable:

1. **The control plane.** Every action carries a `cache_status`
   (`CACHE_MISS` · `CACHE_POPULATED` · `CACHE_HIT` · `CACHE_DISABLED` …). This is
   the claim, and it is read with `scripts/flyte_run_actions.py` — a READER, which
   asks the server what it recorded rather than inferring from a transcript. The
   CLI does not render this field, which is why the file exists.
2. **The clock.** The kickoff asks for "a wall-clock a fraction of run 1". Kept,
   and deliberately ranked WEAKEST: a faster second run is equally consistent with
   a machine that was simply less busy.
3. **MLflow.** A re-executed train stage MINTS A RUN. So the experiment's run
   count must be identical before and after run 2 — measured on a different
   server, in a different database, by code that knows nothing about Flyte. This
   is the strongest leg: it can fail while 1 and 2 both pass, and if it does, the
   cache is not saving the fit, it is hiding a second one.

**The cache key is the function body + the declared inputs + a salt derived from
the DVC pins**, and that third term is the one that matters. Flyte can see a
stage's inputs; every stage here declares a month string, a row count or a
manifest, and then reads 1.8 GB off a volume the key knows nothing about. The
honest failure mode of caching this pipeline is therefore not a stale model — it
is a stale model with a green transcript. `data/*.dvc` is exactly the right object
to close that: it is a content hash of each tracked tree, it is committed, and
`make data` is the only thing that legitimately changes it. The salt travels to
the pods in `TAXI_DATA_PIN`, for the same reason and by the same mechanism as
`TAXI_PIPELINE_IMAGE` — the pins are not in the image and must not be.

**Two stages refuse a cache, and each argues its own case where it is made:**

* **`register`** reads the LIVE registry. A cached answer to "what is serving
  right now?" is not a saving, it is a wrong answer served fast — and it is wrong
  exactly when the alias has moved, which is the one circumstance under which
  anybody re-reads that field. Cost of the refusal: 3.7 seconds against a 31-minute
  fit. The rare case where the correct choice is also nearly free.
* **`main`** is uncached so the evidence stays legible. A cached parent returns the
  previous answer in ONE action without consulting its children, so the transcript
  could not tell "five stages were reused" from "the whole thing was skipped" —
  and M4-S5's kill-a-pod drill would have no pod to kill.

Both are pinned by tests that parse the AST, not the prose: `workflows.py` argues
its cache design at length, so a check that grepped for the word would pass on the
argument and never look at the decorator (gotcha #53). The drill's own `UNCACHED`
list and the workflow's `cache="disable"` decorators are asserted to be the same
set — a twin in the shape M0-S3 established for the port pairs.

### The probe that cost 40 seconds and found two defects

`DRILL_STAGE=ingest make pipeline-cache-drill` runs ONE stage twice (~1 minute
against ~35). It exists for the same reason `make flyte-hello` exists next to
`make pipeline`: the expensive drill must never be the first thing to discover
that caching is misconfigured. It earned its keep immediately.

```
[cache-drill] --- run1 (rvs7vhmkplvt9qngqzkj) ---
[cache-drill]   a0  ingest           SUCCEEDED  CACHE_POPULATED       13.7s
[cache-drill] --- run2 (rz2fv7kqxn9srvtxhwcw) ---
[cache-drill]   a0  ingest           SUCCEEDED  CACHE_HIT              0.3s
[cache-drill] ok  the executed stages cost 13.7s -> 0.3s (2.2% of run 1, bar 10%)
[cache-drill] GREEN — the rerun reused run 1, and three systems agree
```

**Defect 1 — an apostrophe swallowed four lines** (gotcha #60's family, third
time). The drill's banner read `${DRILL_STAGE:+ … not the milestone's evidence}`.
Inside `${var:+word}` that apostrophe opens a quote, so bash consumed the next
four lines looking for its close and reported the damage as **`line 72: $!:
unbound variable`** — pointing at the port-forward, which was fine. Prose must not
sit anywhere a parser will read it as code; the banner is now an `if` block.

**Defect 2 — the wall-clock bar called a 98.7% saving a failure.** The first probe
measured stage `15.2s -> 0.2s` inside a wall-clock of `17s -> 9s`, and a bar
written against the wall alone said `52.9%, not under 50%`. One stage's rerun is
mostly the constant cost of launching at all, which no cache can touch. So the
drill now measures **two clocks**: the sum of the cacheable stages' own durations
(the saving itself, bar 10%) and the wall-clock (the human-visible corroboration,
bar 50%, asserted only for the full pipeline).

**And a third, found by the probe's own second run.** Re-running it turned the
drill RED with `cached stages cost 0.4s -> 0.3s (79.1%)` — because the cache
outlives a drill, so run 1 arrived already cached and the comparison was
rerun-versus-rerun. The drill now names stages that arrived pre-cached, excludes
them from the saving, still requires them to be `CACHE_HIT` in run 2, and REFUSES
to be green if run 1 executed nothing at all: a drill that compares two reruns can
show no saving and must not be allowed to look like one.

### The drill, run for real

`make pipeline-cache-drill MONTH=2019-01`, detached (`automation/runs/m4s4-cache-drill.log`),
**DONE 0**, **GREEN 19/19**:

```
[cache-drill] --- run1 (r56p9p7qwfsqgh6qgrlw) ---
  a0             main             SUCCEEDED  CACHE_DISABLED      1965.9s
  d5ycofwaj…     ingest           SUCCEEDED  CACHE_POPULATED       13.8s
  40q2473fk…     validate         SUCCEEDED  CACHE_POPULATED        5.9s
  5dhua5pl4…     build_features   SUCCEEDED  CACHE_POPULATED        8.9s
  7pxwkh8n5…     train            SUCCEEDED  CACHE_POPULATED     1935.2s
  eithh5v6q…     evaluate         SUCCEEDED  CACHE_POPULATED        3.2s
  4mxq1zfwx…     register         SUCCEEDED  CACHE_DISABLED         3.2s
[cache-drill] --- run2 (rbbvfb5mhfgz8cngx9rn) ---
  a0             main             SUCCEEDED  CACHE_DISABLED         7.2s
  d5ycofwaj…     ingest           SUCCEEDED  CACHE_HIT              0.9s
  40q2473fk…     validate         SUCCEEDED  CACHE_HIT              1.0s
  5dhua5pl4…     build_features   SUCCEEDED  CACHE_HIT              1.0s
  7pxwkh8n5…     train            SUCCEEDED  CACHE_HIT              0.1s
  eithh5v6q…     evaluate         SUCCEEDED  CACHE_HIT              0.2s
  4mxq1zfwx…     register         SUCCEEDED  CACHE_DISABLED         3.2s

[cache-drill] ok  train: run 2 CACHE_HIT (run 1 CACHE_POPULATED), 1935.2s -> 0.1s
[cache-drill] ok  run 1 executed 5 stage(s) for real: build_features, evaluate, ingest, train, validate
[cache-drill] ok  the executed stages cost 1966.9s -> 3.2s (0.2% of run 1, bar 10%)
[cache-drill] ok  wall-clock 1974s -> 11s (0.6% of run 1, bar 50%)
[cache-drill] ok  MLflow gained NO run across run 2 (16 -> 16)
[cache-drill] ok  run 1 DID fit (12 -> 16 MLflow runs) — run 2's saving is real
[cache-drill] ok  @champion is version 2 after both runs
[cache-drill] 19/19 verdicts passed
[cache-drill] GREEN — the rerun reused run 1, and three systems agree
```

**Thirty-three minutes to eleven seconds**, and the three legs agree without
sharing a source: the control plane says `CACHE_HIT` for all five stages, the
clock says 0.6%, and MLflow — which has never heard of Flyte — went `12 -> 16`
across run 1 and `16 -> 16` across run 2. Four MLflow runs are what one fit costs
here (two floors, the challenger, the parent), so "no new runs" is not an absence
of evidence; it is the positive statement that the fit did not happen twice.

**`register` re-executed both times, at 3.2s, and that is the design working.**
Run 2's verdict was therefore re-derived from a CACHED manifest and re-read the
live alias — which is the only reason `@champion is version 2 after both runs`
means anything. A cached register would have replayed the previous answer to a
question whose whole point is that it can change.

## 11. F-026 — the image is where the model code comes from, and nothing said so

Found while checking something the drill has to be able to answer before its
result means anything: *were both runs running the same code?*

They were — but not for any reason the repo could state. `flyte run` defaults to
`--copy-style loaded_modules`, so the code bundle carries only what is imported at
REGISTRATION: **22 files**, observed in the transcript, against **36 `.py` files in
`src/taxi_mlops` alone**. Every stage body imports `pipelines.tasks` (and through
it `taxi_mlops`) *inside* the function, so the modules that compute every number in
this pipeline arrive in the **task image** — whose tag is read from
`automation/runs/m4-image/image.json`, a file only `make image-load` rewrites.

Edit `src/`, commit, run `make pipeline`: the pod runs the previous code and the
transcript is green.

The line the runner used to print — `a pull error here means the tree moved` —
described a protection that does not exist. M4-S3's loud-`ImagePullBackOff`
property fires for a tag **no node holds**; a stale manifest names a tag **every
node holds**. So the check is now explicit, and scoped to the paths a pod can only
receive through the image:

```
[pipeline] ok  image fb57324 carries this tree's src pyproject.toml uv.lock docker (F-026 checked)
```

**`pipelines/` is deliberately not in that list.** It IS the code bundle, so an
edit there does reach the pod — guarding it would have refused this story's own
cache drill, and a guard that fires when nothing is wrong is a guard that gets
deleted (gotcha #50).

Red-teamed the same session, after the drill so nothing in flight could be
disturbed: one appended comment line in `src/taxi_mlops/training/evaluate.py`,
then `make pipeline`:

```
[pipeline] FAIL: the task image predates the source it would run (F-026).
[pipeline]       image fb57324 vs HEAD ae8befb, differing under src pyproject.toml uv.lock docker:
[pipeline]         uncommitted:  M src/taxi_mlops/training/evaluate.py
[pipeline]       These reach a task pod ONLY through the image, so this run would
[pipeline]       compute its numbers with the old code. Fix: make image-load
make: *** [Makefile:132: pipeline] Error 3
```

Exit 3, in under a second, **before the PVC check, the port-forward or any
launch** — the refusal costs nothing and happens before anything can be
half-done. File restored (`git checkout`), tree clean.

## 12. What M4-S5 inherits (supersedes §8)

Both of M4-S4's outstanding legs are landed: the **full-data green run** (§9) and
the **cache-hit rerun** (§10). M4-S5 is unblocked in full — kill-a-pod, D-003's
marts tail task, `make verify-m4` and its red team.

* **`scripts/flyte_run_actions.py` is built for `verify-m4` to reuse.** It reads a
  run's actions, their phases, their `cache_status` and their durations, and it
  only reads — pinned structurally by a test, because a gate that can mutate the
  run it judges is not a gate. The cache evidence `verify-m4` owes is
  `automation/runs/m4-cache/cache_drill.json`, which holds both runs' full action
  lists, both wall-clocks and the MLflow counts.
* **The kill-a-pod drill wants an UNCACHED stage to kill**, and after this story
  five of the six are cached for `MONTH=2019-01`. Either drill a fresh month (a
  new `ingest` key), or edit nothing and kill the `register` stage — which is
  uncached by design but lasts 3.2 seconds. The fresh month is the honest one.
* **One shape not to change without deciding to**: `register`'s output `margins`
  carries the floor numbers only, so a REFUSE decided by the INCUMBENT condition
  prints beside a floor margin that passes (§9). `verify-m4` is about to start
  asserting against that output — fix it *before* pinning it, or pin it and carry
  the gap, but do not do both in the wrong order.
* **`@champion` is version 2**, read before and after all four runs this session.
