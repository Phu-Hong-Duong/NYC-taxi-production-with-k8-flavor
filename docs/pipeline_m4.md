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

---

# M4-S5, first session (2026-08-18) — the kill drill, and where the story is cut

§13–§15 are M4-S5's. §1–§12 are M4-S4's record and are left unedited.

## 13. Kill-a-pod: what survived it, and the three things the drill was wrong about first

`make pipeline-kill-drill` deletes the pod a stage is running in, mid-work, and
checks that the pipeline finishes anyway. **GREEN, 9 checks** (2 in phase 0, 7 in
the drill proper), run `rb2cxpmsksx489qjbn5b`, month **2019-03**, sampled and
therefore verdict-free by construction (F-008, and the M4 kickoff names a sampled
run as legal here because what is under test is the ORCHESTRATOR).

```
[kill-drill] pod …-e5rvu8gd7fu01qmk5ojfc8ufh-0 is Running on node mlops-taxi-worker2
             (uid 1223e07d-…) — letting it work for 120s
[kill-drill] KILLING …-e5rvu8gd7fu01qmk5ojfc8ufh-0 at 2026-08-18T15:38:01Z
[kill-drill] ok  a DIFFERENT pod object ran 'train' after the kill:
             …-e5rvu8gd7fu01qmk5ojfc8ufh-0 (uid 9d8b05a3…, created 2026-08-18T15:38:32Z)
             — the killed pod was uid 1223e07d…
[kill-drill] ok  'train' ended SUCCEEDED despite losing its pod mid-work
[kill-drill] ok  the pipeline completed (run_pipeline.sh exit 0) — a killed pod cost time, not the run
[kill-drill] ok  @champion unchanged across the drill (read by run_pipeline.sh, before and after)
[kill-drill] 7/7 verdicts passed
[kill-drill] GREEN — a stage lost its pod mid-work and the pipeline still finished
```

**31 seconds from kill to replacement.** The `train` action's total was **939.8 s**
against ~870 s for an undisturbed sampled fit, so the cost of the kill was the
~123 s of work in flight plus the gap — the fit restarted from zero, which is
what makes the idempotence argument load-bearing rather than decorative. Every
other stage was `CACHE_POPULATED` and `SUCCEEDED`; `@champion` read **2** before
and after, by `run_pipeline.sh` itself, which exits 2 if it moved.

### 13.1 The prediction was written first, and it was wrong

The drill writes `automation/runs/m4-kill/prediction.json` **before** it kills
anything, and a test pins that ordering positionally. On the first run the
prediction said the retry would appear as a pod named `…-1`, because Flyte names a
task pod `<run>-<action>-<attempt>` and a retry ought to bump the attempt.

Observed instead: the k8s plugin **recreated the pod under the same name with a
new UID**, and the run finished perfectly — so a correct survival was reported as
a **failed drill, 6/7**. The first prediction and its refutation are kept whole in
`automation/runs/m4-kill/attempt1-prediction-wrong/`, which is the point of
writing predictions down.

The fix was not a looser assertion, it was **the right property**: identity, not
name. A different pod object ran the stage. That is true whether the platform
bumps the attempt (new name) or recreates the attempt (same name, new object), and
it is asserted by comparing the UID read **before** the kill against the UIDs
present after.

### 13.2 The drill was measuring pod recreation, not the retry budget — so the budget is now measured on its own

The same run said something the drill had not thought to ask: the control plane
recorded the killed action at **one attempt**. Recreating a pod is not the same
event as failing an attempt, so `retries=2` — declared on every stage this session
— **had never been observed doing anything**. A number nobody has watched work is
a number nobody should rely on.

`pipelines/flyte/retry_probe.py` is one task whose only job is to raise, carrying
the same budget **by import** (`from …workflows import _STAGE_RETRIES`) so that it
measures the number this repo declares rather than one it restates. Phase 0 of the
drill runs it to exhaustion, in ~90 seconds, in front of the ~20-minute leg — the
same cheap-probe-before-the-expensive-run shape as `make flyte-hello` and
`DRILL_STAGE=ingest`:

```
[kill-drill] phase 0: spending the declared budget (retries=2) on a task that always fails
[kill-drill] phase 0: the probe's action settled at FAILED
[kill-drill] ok  the declared budget is REAL and BOUNDED: a task that always raises
             settled at attempt index 3, inside the [1, 3] that retries=2 allows
[kill-drill] ok  the budget is FINITE: retries ran out and the run FAILED, which is
             why the number is small rather than generous
```

Both halves matter. `retries=2` buys three attempts and then **stops** — which is
the argument for the number being small: a generous budget converts a systematic
fault into a slow success, and at 31 minutes a stage that would be half an hour of
hiding it each time. The bound is asserted as a RANGE, `[1, retries+1]`, because
whether the last attempt is reported 0-based or 1-based is a convention this repo
neither controls nor has a stake in; the exact index is printed.

**Two mechanisms, both now measured, and they are not the same mechanism**: a
deleted pod is survived by recreation (attempts unchanged), and a raising task is
survived — up to a point — by the declared budget (attempts 1 → 3).

### 13.3 F-027: the reader had been answering `attempts: 0` for everything

Phase 0's first run reported the budget broken: `attempts=0` on a task that had
demonstrably been retried. Two separate faults, found in the order they bit.

**The instrument.** `scripts/flyte_run_actions.py` collected
`int(getattr(status, "attempt", 0) or 0)`. The field is **`attempts`**, plural. A
protobuf message answers `getattr` for its own fields only, so the misspelling did
not raise — it returned the default. **Every action of every run this program has
ever inspected was recorded with `attempts: 0`**, including
`automation/runs/m4-cache/cache_drill.json`, and nothing looked wrong because `0`
is exactly what an un-retried action should say. It could only surface where the
number was supposed to be non-zero. Filed and closed as **F-027**; now gotcha #64.
The test pins the reader against `ActionStatus.DESCRIPTOR` rather than against the
string `"attempts"`, so it fails on the next typo in the next field.

*Honest consequence, not quietly corrected:* the historical `attempts: 0` values in
M4-S4's recorded cache evidence are defaults, not measurements — that file lived
under `automation/runs/`, gitignored at the time of writing, so it was on this
machine and not in git, which is also why a gate reading it had to treat it as
state (F-029; the records are tracked from M5-S1 on). Those runs really
were not retried (every pod is `…-0`), so no claim made from that file is wrong —
but `verify-m4` must not treat the old values as evidence.

**The observation window.** `flyte run --follow` returned **7 seconds** after
launching the probe, with the action still `RUNNING` and two retries still to come:
`--follow` follows the **log stream**, and the stream ends when the first attempt's
container exits. The check now polls the server for a terminal phase. Sibling of
gotcha #59 — the CLI's return is not a statement about the run's outcome, and now
also not about its completeness (gotcha #65).

### 13.4 A third defect, found before the first kill: the runner buffered its own transcript

The drill cannot delete a pod belonging to a run it cannot name, and the run's name
appears only in `flyte run --follow`'s output — which `run_pipeline.sh` captured
into a shell variable, i.e. into something that does not exist until the command
exits. The drill polled an empty file until the run it meant to interrupt was over.

The fix is `RUN_DIR/flyte_run.log`, and it is a better transcript for everyone, not
only for this drill: §9 of this document is an entire section about per-stage
detail that had to be recovered from the server *because it was never written
down*. Same absence, one layer earlier.

### 13.5 Why `train`, and why the drill refuses a cached stage

The five other stages last between 3 and 15 seconds, so a kill aimed at one of them
tests whether the script can win a race. `train` is the only stage whose loss would
actually cost anything, so it is the honest target — and the drill's default month
is one the pipeline has never seen, because **a cached stage runs in no pod**. The
verdict refuses to be green if the target came back `CACHE_HIT`: the mirror of the
cache drill's "run 1 executed no stage", and for the same reason.

Each stage's idempotence is cited to the story that proved it, in the script's own
header — `ingest` to M1-S2's byte-identical `make rebuild-proof`, not to an
assertion made here. The one honest cost is named there too: **a killed `train`
attempt leaves its MLflow run behind**, because the run is minted when the fit
starts and the process that would have closed it is gone.

## 14. D-003's tail task: the one fact it is designed around, measured

Leg 2 of M4-S5 — the marts build+publish as the pipeline's tail task — is NOT
built in this session (§15 says where the cut is and why). What is done is the
measurement its whole design turns on, because getting it wrong would have been
discovered three hours into the implementation.

**The problem, stated precisely.** `make marts` publishes over `kubectl exec`
into the postgres pod, and that is not an accident of convenience: nothing of
ours publishes 5432 on the host (the port family annotates it "in-cluster only"),
so the host has **no TCP route** to the database at all. `scripts/marts.sh`
records the three rejected alternatives — a NodePort for 5432, a babysat
port-forward, DuckDB's run-time-downloaded `postgres` extension — and they are
still rejected. But a **task pod cannot use `kubectl exec`**: it has neither
kubectl nor a kubeconfig, and giving a pipeline stage cluster credentials so it
can shell into another pod would be a far worse trade than any of the three.

**So the tail task needs a transport the host does not have, and the question is
whether the obvious one works.** It does. `scripts/marts_reach_probe.py` runs one
throwaway pod **built from the actual task image** and connects with psycopg —
which the image already carries as Optuna's driver (M3-S4), so this costs no new
dependency:

```
PROBE-OK ('marts', 'marts') trips_clean total size 13 GB monthly_kpis rows 8
```

Three facts in one line, and each matters:

* **the pod connects** to `postgres.platform.svc.cluster.local:5432` — the
  in-cluster half of the same split horizon F-023 named, and the reason the tail
  task is possible at all;
* **it connects as `marts`, not as the superuser** — the M1-S5 rule (a seat that
  can drop the warehouse it reads is one misclick from a restore) carries over to
  a pipeline stage unchanged;
* **`trips_clean` is 13 GB right now**, so D-003's number is a measurement of
  today and not a memory of M1-S4. The row's ~23 GB peak is that 13 GB plus the
  staging copy that coexists with it during the swap.

**What the probe does NOT settle, named so the next session does not read it as
more than it is.** The probe passes credentials as env vars in a `kubectl run`
override, which puts them in a pod spec; the real tail task must take them from a
Secret (`flyte-task-marts`, the fourth consumer of the shape
`scripts/platform_secrets.sh` already has) referenced from
`infra/manifests/flyte-task-podtemplate.yaml`, exactly as the MinIO and MLflow
identities already are. And the transport is only half the work: the tail task
also has to rebuild the analyst layer in-pod and needs `data/predictions/` on the
volume (the `error_segments` mart sources it), which makes `make stage-data` a
four-tree stager.

**The twin the next session must not create.** The swap SQL — staging table,
`\copy`, rename-in-one-transaction, indexes — exists once today, in
`scripts/marts.sh`. A second copy in Python for the in-pod path would be a twin
of the most consequential SQL in the repo. The shape that avoids it: one module
owning the SQL and the CSV stream (the DuckDB half already lives in
`scripts/marts_export.py`, which is why the type mapping is testable), with two
thin transports — `kubectl exec | psql` for the host and psycopg for the pod —
and `marts.sh` delegating to it rather than duplicating it.

## 15. Where M4-S5 is cut, and what the next session starts with

**Done here:** leg 1 — the retry budget and the kill-a-pod drill (§13).
**Not done:** leg 2 (D-003's marts tail task) and leg 3 (`make verify-m4` and its
red team).

The cut is between legs, not inside one. The reason is scope, stated with the
work rather than as an apology: leg 2 needs a new transport, a new Secret, a
PodTemplate change, a four-tree stager, an image rebuild and a live publish to
measure against the 23 GB peak — and leg 3's gate is supposed to assert that the
marts reconcile *after* the tail task, so writing it first means editing it
immediately afterwards, which is how the M2-era literals got written (F-017,
gotchas #49/#50).

Order for the next session, and it is the kickoff's own: leg 2, then leg 3.
Leg 3 inherits, in addition to M4-S4's list:

* `automation/runs/m4-kill/kill_drill.json` — the drill's record, including the
  killed pod, its replacement, and the actions with their phases. `verify-m4`
  owes an assertion that the retry event is present in history, and this file is
  where it is, without a port-forward.
* `scripts/pipeline_kill_drill.sh`'s verdict block is the shape that assertion
  should take, and §13's correction is the reason it does not assert on the pod
  NAME.
* **`train` for 2019-02 and 2019-03 is now cached.** A third kill drill needs a
  fourth month, or an invalidating edit.

## 16. D-003 decided: the marts tail task, and why the fact table is the only mart that changed

Leg 2 of M4-S5. §14 measured the one fact the design turns on and stopped there;
this is the build, the decision the debt row demanded, and the numbers it rests on.

### 16.1 The decision, in one paragraph, with its evidence

D-003 asked for one of two things at the moment the publish became scheduled: an
incremental materialisation, or a recorded decision that full refresh stays with
the ~23 GB peak re-measured. **The answer is split, because the marts are not one
kind of object** — and both halves were measured on today's data before either was
argued, with `make marts-peak` sampling `pg_database_size('marts')` every 5 s:

| publish | wall | `marts` DB start → **peak** → end | PGDATA used, peak |
|---|---|---|---|
| **full refresh** (all 8 months, 56,127,878 rows) | **228.2 s** | 15.33 → **27.96** → 13.48 GiB (**2.075×**) | 204.62 GiB |
| **month-scoped** (2019-03, 7,753,921 rows) | **82.7 s** | 13.48 → **15.33** → 15.33 GiB (**1.0×**) | 191.99 GiB |

So: the four aggregates stay full-refresh forever, and `trips_clean` is
month-scoped. `zone_hourly_stats` (44,792 rows), `monthly_kpis` (8),
`rejections_by_rule` (80) and `error_segments` (1,151) are ~46,000 rows between
them; rewriting all four costs under a second and buys the strongest property a
publish can have — **the mart IS the source, with no possibility of drift.**
Incremental machinery there would be complexity bought with nothing. The fact
table is the entire peak: it is 13 GiB, its grain IS the month (an indexed
column), and a monthly pipeline re-derives ONE month, so a full refresh
republishes ~7.5M changed rows by rewriting 56M — eight months of work to land one.

**Peak down 45.2%, wall down 63.8%.** And M1-S4's remembered "~23 GB" was
optimistic: measured today it is **27.96 GiB**, because `error_segments` joined the
marts at M2-S4 and the fact table grew. A debt argued from a remembered number is a
debt argued from nothing — which is why the row's closure quotes this table and not
that sentence.

### 16.2 The honest cost of the decision, stated as a cost

Two things get WORSE, and neither is hidden:

* **The steady state rises.** A month-scoped publish `DELETE`s 7.75M rows and
  re-streams them, and those dead tuples are space the table holds until autovacuum
  reclaims it — measured, `end` is **15.33 GiB** where a full refresh ends at
  **13.48**. So incremental trades a lower PEAK for a higher FLOOR of about one
  month of dead space. That is the right trade on a volume whose failure mode is a
  spike, and it is the wrong one to describe as "smaller".
* **The mart can now drift from its source in a way a full refresh made
  impossible.** A month deleted and not re-streamed is a mart that is quietly
  short: it answers every query happily and just returns fewer rows — M1-S2's
  catalogue lesson, one layer downstream. So **`reconcile` runs after every
  month-scoped publish**, asking Postgres and DuckDB for the same per-month counts
  and refusing to return unless every month agrees. That check is the price of the
  decision and it is not optional; `tests/unit/test_marts_publish.py` watches it say
  no.

A first publish (or a table somebody dropped) has no month to replace, so the
scoped path falls back to a full refresh and **says so on stdout** — the one publish
that legitimately pays the peak must not look like the rest.

### 16.3 One body of SQL, two transports — and why that was forced

`scripts/marts_publish.py` is new and it is mostly a MOVE. The publish used to be
the second half of `scripts/marts.sh`, in shell, which was fine while the host was
the only publisher. A task pod **cannot use the host's transport**: `marts.sh`
reaches Postgres over `kubectl exec` because nothing of ours publishes 5432 (the
port family annotates it "in-cluster only"), and a pod has neither kubectl nor a
kubeconfig — giving a pipeline stage cluster credentials so it could shell into
another pod would be a worse trade than any of the three alternatives `marts.sh`
already rejects.

So there are two transports and **one** body of SQL. The swap is the most
consequential statement in this repo — it is what decides what a board renders —
and §14 named the twin to avoid before any of it was written. Everything below the
`Transport` protocol is transport-blind: the same statements in the same order,
whether they arrive over `kubectl exec -i` or over a psycopg connection. Three more
things moved for the same reason: the **mart list** (`marts.sh` no longer has a
`MARTS=(...)` array, and a test fails if one comes back), the **dbt `--vars`
payload** (`--print-dbt-vars`, so the mart's KPI-04 domains and the model's KPI-12
tolerance cannot be assembled twice), and the **`--no-partial-parse` flag** (gotcha
#38, welded onto one invocation).

The CSV producer is also one thing, and it is a **subprocess on both sides**:
`scripts/marts_export.py` already owned the DuckDB half since M1-S4, so the host
pipes its stdout into `psql \copy` and the pod pumps it into psycopg's `COPY FROM
STDIN` in 4 MiB chunks. It gained one option — `--where`, which scopes the stream
inside DuckDB, because filtering 56M rows on the far side would have paid the whole
cost of the thing it avoids. **The producer's exit code is checked explicitly**: a
`Popen` read to EOF looks identical whether it finished or died three rows in, so
without that the publish would commit a truncated mart and print a row count
(gotcha #59, in miniature).

### 16.4 What a task pod needed that it did not have

Four pieces of wiring, each the third or fourth instance of a shape this program
already had:

* **`flyte-task-marts`** — the third Secret a task pod reads, holding
  `MARTS_DB_USER`/`MARTS_DB_PASSWORD` under exactly the names `marts_publish.py`
  reads, so the pod needs no translation layer. It is the **fourth** consumer of the
  `marts` role (Metabase reads with it, the host publish owns tables as it, and now
  a pod connects AS it). It is a separate Secret because Secrets do not cross
  namespaces and because the two existing identities were deliberately split at
  M4-S2 — merging them to save a Secret would quietly undo that. The test that used
  to name the two expected Secrets now diffs the pod's `envFrom` against what
  `platform_secrets.sh` actually converges into the `flyte` namespace, in both
  directions: a converged Secret nobody reads is a credential with no consumer, and
  a referenced Secret nobody converges is a pod that will not start.
* **The pod publishes as `marts`, never as the superuser.** M1-S5's rule applied to
  a pipeline stage: a seat that can drop the warehouse it reads is one misclick from
  a restore, and a scheduled publish is a seat nobody is watching.
* **`data/predictions/` as a fourth staged tree**, mounted by subPath like the other
  three. `error_segments` sources the analyst layer's `predictions` view, and that
  view is CONDITIONAL on the tree existing — so without the mount `analyst.build()`
  silently omits it and the dbt build fails on a missing source three frames deep in
  a compiled model. It is the one staged tree that is **not DVC-pinned** (M2-S4
  decided that deliberately), so it does not enter the cache salt — honest, because
  nothing pins it. The staged-vs-mounted twin test needed no edit: it already
  compared the two lists rather than a remembered count.
* **The F-026 guard widened to `scripts/` and `analytics/`.** The tail loads
  `marts_publish.py` by path from inside the pod, and the dbt project is not
  importable at all, so no `--copy-style` would ever bundle it: the image is its only
  carrier, which is exactly this guard's criterion. An edit to a mart's SQL against a
  stale image would publish the PREVIOUS model definition and reconcile perfectly
  against it.

### 16.5 The stage, and the three things it deliberately does not do

`pipelines.tasks.publish_marts` is three calls in an order that is not negotiable:
rebuild the analyst layer (`taxi_mlops.data.analyst.report`, which is also the step
that reconciles — the stage refuses to publish from a catalogue that does not agree
with the ingest reports that wrote it), `dbt build` (models AND tests interleaved, so
a red test stops the publish), then the publish over the transport this caller can
use.

**It does not read the verdict, and it does not branch on it.** `verdict` is
consumed for the edge it draws — the DAG has to say "after register", and in a
dataflow engine you say that by taking the previous stage's output. But a pipeline
whose data publish depended on a model verdict would leave the warehouse a month
stale every time the gate said no, which is precisely when a DA wants to look.

**It does not touch the registry**, and a test asserts that from the import list.
ADR-009's boundary law says the marts serve humans and model code never imports
them, so the publish lives in `scripts/` and the dependency runs `pipelines ->
scripts -> duckdb/psycopg`, never through `src/`. M4's standing law says no pipeline
stage moves `@champion`; a tail that could resolve an alias would have no reason to
except to become a second promotion path.

**It is UNCACHED, and it is the first stage whose reason is about EFFECTS rather
than inputs.** Every other refusal in `workflows.py` is Rule 2 (a stage that reads
live state outside its inputs). This one is the mirror image: its product is not its
return value, it is a mutation of a Postgres the cache cannot see. A hit would
return "published, 7.5M rows" in 0.1 s having published nothing — and it would be
RIGHT by the cache's own rules, because the code, the inputs and the data pin were
all identical. Somebody could have dropped the table or restored the volume in
between, and the whole point of a scheduled publish is that the warehouse ends up
matching the data whatever else happened. That is the green-transcript-over-stale-
state failure the salt exists to prevent, in effect form, and no salt can reach it.

**The local rehearsal opts IN** (`make pipeline-local PIPELINE_LOCAL_ARGS=--publish`).
Every other stage of that command writes only into `data/` and MLflow; a "plumbing
rehearsal" whose default republished the warehouse two Metabase boards read would be
a command whose name lies about its blast radius. The two ORCHESTRATOR drills opt out
the same way (`PUBLISH_MARTS=0`): the cache drill measures what a cache saves and the
tail is uncached by design, so including it would drag the measured ratio toward 1
without any of it being about caching.

### 16.6 The run: seven stages on-cluster, and the number the tail cost

`make pipeline MONTH=2019-01 TRAIN_MONTHS=2019-01`, run `rw98pj84z4jh5ldqrxqp`,
**exit 0**. Sampled and therefore verdict-free (F-008 honored by construction — the
register stage returned `NO_VERDICT` as data), because what is new here is the TAIL
and the fit was already measured twice. `@champion` read **2 → 2** by the runner
itself, which exits 2 if it moved.

Per-stage detail read off the control plane with `make flyte-actions
RUN=rw98pj84z4jh5ldqrxqp` (the reader M4-S4 wrote, now with a route of its own):

```
  a0                         main             SUCCEEDED  CACHE_DISABLED       886.6s
  2d98cwh9qaqg2ygcjcv59zhe8  ingest           SUCCEEDED  CACHE_POPULATED       14.0s
  c91whjsuy5pbpetnoq7b2rk57  validate         SUCCEEDED  CACHE_POPULATED        5.1s
  6p7vnr37wglu937f3mz910l5o  build_features   SUCCEEDED  CACHE_POPULATED        7.1s
  b8sum2j0yyx6gonm6fj1iz7ox  train            SUCCEEDED  CACHE_POPULATED      762.4s
  35vy13jifs2n4m4dk7izdt48b  evaluate         SUCCEEDED  CACHE_POPULATED        3.4s
  1hzjxd9vl60m8isspfwpeiijt  register         SUCCEEDED  CACHE_DISABLED         2.4s
  8rbeep9e3sx4qs1ogfajzklpw  publish_marts    SUCCEEDED  CACHE_DISABLED        90.6s
```

**The tail cost 90.6 s of a 886.6 s run — 10.2%**, and inside it the publish itself
measured **71.9 s** (the remaining ~19 s is pod start, the in-pod analyst-layer
rebuild, and a `dbt build` that reported **PASS=57 in 9.96 s** from inside the
container). It published `2019-01` month-scoped and then reconciled **all eight
months** against the analyst layer, every one `yes`:

```
[marts] trips_clean: replacing 1 month(s) — 2019-01
  2019-01     7,584,656     7,584,656    yes     …    2019-08     5,950,708     5,950,708    yes
  [marts] ok  8 month(s) reconcile
[marts] published 5 mart(s) into 'marts' via psycopg marts@postgres.platform.svc.cluster.local:5432/marts in 71.9s
```

**71.9 s in a pod against 82.7 s from the host** for the same work — the pod's direct
TCP beats `kubectl exec` by about 13%, which is a small bonus and not the reason the
transport exists. It worked on the first on-cluster attempt, which is worth saying
plainly because §14 had already paid for the two questions that usually cost the
attempts: whether a pod can reach Postgres at all, and as whom.

### 16.7 An image rebuild invalidates every cached stage (gotcha #66)

Every cacheable stage above reads **`CACHE_POPULATED`, not `CACHE_HIT`** — and
`train`, `ingest`, `validate`, `build_features` and `evaluate` were all populated by
earlier runs on this exact month with an identical data pin. Their function bodies
were not touched by this story. What changed between those runs and this one is the
**task image**: the tag is the git short sha (M4-S3), so every commit produces a new
one, and it reaches the tasks two ways at once — as the `TaskEnvironment`'s image and
as `TAXI_PIPELINE_IMAGE` in `env_vars`. Either is part of the task spec Flyte keys on.
Which of the two did it is NOT separated here (they move together by construction, and
separating them would mean building an image whose tag lies), so the observation is
recorded at the precision it was measured: **an image rebuild invalidates the cache
for every stage.**

It is arguably the correct behaviour and it agrees with F-026 from the other side —
the image is where the model code comes from, so a stage cached against a previous
image would be a cache hit computed by code this tree does not contain. But it has a
cost nobody had priced, and it lands on M7: **a commit under `src/`, `scripts/`,
`analytics/`, `docker/`, `pyproject.toml` or `uv.lock` forces an image rebuild, and an
image rebuild forces a full re-fit** — 31 minutes on full data, not the 11 seconds
M4-S4's cache drill measured. The drill's own numbers are unaffected (both its runs
use one image, deliberately), and this is exactly why it holds the image constant.

**Consequence for leg 3:** `verify-m4`'s cache leg must read the recorded cache
evidence from `automation/runs/m4-cache/cache_drill.json` rather than re-asking the
control plane about the latest run — the latest run's stages are `CACHE_POPULATED`
whenever the image moved, which is most sessions, and a gate that expected
`CACHE_HIT` there would go red for a commit.

---

**Continued in `docs/pipeline_m4_leg3.md`** — M4-S5 leg 3 (2026-08-19): `make verify-m4`
(39/39), its red team, and F-029. Split into its own file only because this one is
already 1,032 lines; the section numbering continues there at §17, and §1-§16 above stay
UNEDITED as the earlier sessions record.
