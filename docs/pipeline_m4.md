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
