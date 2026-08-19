# M5-S1 — the records enter review, and the serving platform lands

Story: **M5-S1** (`docs/milestones/M5_KICKOFF.md`), role **MLOps — Platform
Engineer**. Two halves, in the kickoff's order: F-029's mechanics first, because
it makes every record M5 writes reviewable from the day it is written; then the
serving platform.

---

## 1. Half 1 — F-029: the evidence base of two gates enters review

### 1.1 What was wrong, in one paragraph

`verify-m3` §4/§5 replay `automation/runs/m3s5/bakeoff.json` and
`m3s4/*.json`; `verify-m4` §3–§6 read five records under `automation/runs/m4-*/`.
Until this commit `automation/runs/` was ignored **wholesale** (`.gitignore:43`),
so `git ls-files automation/runs` was **empty**. Three consequences, the middle
one being the point: a fresh clone ran those legs red for no defect; **an edit to
a record — the exact fault both red teams plant on purpose — left no diff for a
reviewer to see**; and two artifacts said the opposite in writing. Found at
M4-S5 leg 3 (gotcha #69), filed as **F-029**, policy routed to ARCH because what
belongs under review is not an executor's call. ARCH decided **option A** at the
M4 boundary on 2026-08-19. This is the mechanics, landed as one PR — deliberately
one unit, because tracked files under headers still saying "gitignored" would be
the same class of false self-statement the finding is about.

### 1.2 The gitignore is pattern-based, and that is not a style choice

The naive fix does nothing:

```gitignore
automation/runs/               # git STOPS DESCENDING here …
!automation/runs/**/*.json     # … so this rule is never consulted
```

Git does not descend into an excluded directory, so a negation beneath one is
silently inert. The landed rule is three lines that are one mechanism — exclude
by pattern, re-include the directories so the walk continues, re-include the
files last:

```gitignore
automation/runs/**
!automation/runs/**/
!automation/runs/**/*.json
```

Verified both directions rather than assumed, with the command the gotcha names:

```console
$ git check-ignore -v automation/runs/prune-smoke.json automation/runs/m3s5/bakeoff.json \
    automation/runs/m4-kill/attempt1-prediction-wrong/prediction.json automation/runs/m4-cache/cache_drill.json
.gitignore:59:!automation/runs/**/*.json	automation/runs/prune-smoke.json
.gitignore:59:!automation/runs/**/*.json	automation/runs/m3s5/bakeoff.json
.gitignore:59:!automation/runs/**/*.json	automation/runs/m4-kill/attempt1-prediction-wrong/prediction.json
.gitignore:59:!automation/runs/**/*.json	automation/runs/m4-cache/cache_drill.json

$ git check-ignore -v automation/runs/m4s5-kill-drill.log automation/runs/m4s4-cache-drill.status \
    automation/runs/m3s4-automation-track.log
.gitignore:57:automation/runs/**	automation/runs/m4s5-kill-drill.log
.gitignore:57:automation/runs/**	automation/runs/m4s4-cache-drill.status
.gitignore:57:automation/runs/**	automation/runs/m3s4-automation-track.log
```

The verdict JSONs are re-included (the negation line matched them); the logs and
`.status` files still match the exclusion. That split is the decision: **the
records two gates read are evidence and enter review; transcripts are large,
nothing reads them for a verdict, and they stay ignored.**

Note the JSON rule matches at every depth, including the top level — `**/`
matches zero directories, which is why `prune-smoke.json` (directly under
`automation/runs/`) is covered by the same line as the nested ones.

### 1.3 What is now tracked

```console
$ git ls-files automation/runs | wc -l
32
$ du -sh automation/runs --exclude='*.log' --exclude='*.status'
236K	automation/runs
$ find automation/runs -name '*.json' -size +100k
(nothing)
```

32 records, 236 KB, the largest under 100 KB — every path both gates read,
including `m4-kill/attempt1-prediction-wrong/` (the wrong prediction M4-S5 kept
on purpose; a record of a mistake is exactly the kind of thing that must not
quietly vanish from a clone).

### 1.4 The four stale statements, corrected at their source

| Where | Was | Is |
|---|---|---|
| `scripts/verify_m3.sh` header | "RECORDED, not committed — `automation/runs/` is gitignored … the policy fork is ARCH's" | RECORDED **and committed**, with both corrections narrated (it took two to get the sentence right) |
| `scripts/verify_m4.sh` header | "HONEST LIMIT … the records below are MACHINE state, not repo state" | the records are committed; a fresh clone can run §3–§6 against the same bytes |
| `scripts/verify_m4.sh` closing print | `the records read  automation/runs/m4-*/ (gitignored: F-029)` | `… (tracked: F-029 closed)` |
| `CLAUDE.md` verify-m3 row + the F-029 bullet + gotcha #69's summary | "not committed", "OPEN" | committed; F-029 closed with the mechanism recorded |

Two more that the decision changes and the kickoff did not enumerate, found by
grepping for the claim rather than for the file list:

- **Both red-team headers** now state the new regime: a clean drill leaves a
  **clean tree** (the EXIT-trap restore is byte-identical, so anything `git
  status` shows afterwards is a drill that did not finish — a checkable property
  that did not exist while the files were ignored), and a crashed drill is
  recoverable by `git checkout --` **as well as** from the byte copy. Both
  failure paths now print the byte copy FIRST and `git checkout --` second: the
  byte copy is right under every condition, while `git checkout --` assumes the
  record was committed in the state the drill found it, which a failing restore
  path may not assume.
- **`tests/unit/test_bakeoff.py::test_the_json_records_where_the_winner_was_ranked`
  used to SKIP** when `bakeoff.json` was absent, with the reason written into the
  skip message ("automation/runs/ is gitignored"). That skip is now an
  **assertion** that the record exists — strictly stronger, and it is why the host
  unit suite reports 544 passed with **no skips** where it used to skip one.

`docs/verify_m4_transcripts.md` is deliberately NOT edited: it is a verbatim
transcript, and a transcript edited to match today's code is not a transcript. It
carries a dated note pointing here instead. Same for
`docs/pipeline_m4_leg3.md` §19 (the discovery record) and `docs/pipeline_m4.md`,
which gain closing notes rather than rewrites.

### 1.5 Both gates and both red teams, re-run over the moved files

Nothing about either gate's logic changed. The point of re-running all four is
that the red teams now **edit tracked files**, which is a genuinely new
situation for them.

```console
$ make verify-m3 | grep -c "ok  "
46
$ make verify-m4 | grep -c "ok  "
39
```

Closing lines, verbatim:

```
[verify-m3] GREEN — every M3 sub-check passed.
[verify-m4] GREEN — every M4 sub-check passed.
            Show: the pipeline story   docs/pipeline_m4.md
                  the image + D-004    docs/task_image_m4.md
                  the records read     automation/runs/m4-*/ (tracked: F-029 closed)
```

The last line is the one this half was for: the word "gitignored" no longer
appears in either gate's output about its own inputs.

**`make verify-m3-redteam`** — one contender's measured KPI-09 rewritten in a
now-tracked record:

```
  automation/runs/m3s5/bakeoff.json  sha256 c4a323ea072a…
  FAIL replaying auto-on-v1 through today's gate gives PROMOTE, the bake-off recorded REFUSE — the gate moved under the transcript
  FAIL the replay produced {'PROMOTE': 3, 'REFUSE': 1} — a bake-off nobody was refused in is a bake-off nobody was judged in
[verify-m3] RED — 2 sub-check(s) failed.
  ok   all 4 untampered replays still passed — the leg reads numbers, not files
  ok   44 sub-check(s) still ran and passed — the gate reports everything, not the first thing
  restored automation/runs/m3s5/bakeoff.json (sha256 c4a323ea072a…)
  ok   automation/runs/m3s5/bakeoff.json is byte-identical to what the drill found (sha256 c4a323ea072a…)
  ok   the gate is GREEN again (46 sub-checks, exit 0) — the drill left nothing behind
[verify-m3-redteam] PASSED
```

**`make verify-m4-redteam`** — one field flipped, `CACHE_HIT` → `CACHE_POPULATED`:

```
  automation/runs/m4-cache/cache_drill.json  sha256 beb10ab49fb0…
  FAIL cacheable stage(s) did not hit on the rerun: {'train': 'CACHE_POPULATED'}
  FAIL the two witnesses CONTRADICT each other: the record says ['train'] re-executed on the rerun while MLflow minted 0 run(s) — a fit either logs or does not happen, so one of these records is wrong
[verify-m4] RED — 2 sub-check(s) failed.
  restored automation/runs/m4-cache/cache_drill.json (sha256 beb10ab49fb0…)
  ok   automation/runs/m4-cache/cache_drill.json is byte-identical to what the drill found (sha256 beb10ab49fb0…)
  ok   the gate is GREEN again (39 sub-checks, exit 0) — the drill left nothing behind
[verify-m4-redteam] PASSED
```

And the new property, asked immediately after each drill and answered by silence:

```console
$ git status --porcelain
(nothing)
```

**A clean drill leaves a clean tree.** Before this half that sentence was not
checkable — the files it restores were invisible to git. It is now the cheapest
possible confirmation that a red team finished, and the reason the two headers
say so.

`uv run pytest tests/unit -q` → **544 passed** in 48.08s, no skips.

### 1.6 What half 1 does NOT claim

The records are now reviewable, not *verified*. Nothing here proves a record
describes the run it names — that is what the gates' cross-system legs are for
(§4's two witnesses being the sharpest). What changed is narrower and worth
stating exactly: **a tampered record is now a diff.** The only thing that used to
stand between a rewritten number and a green gate was that nobody rewrote it.

Churn is the accepted cost, and it is bounded by the same split: a record changes
only when a drill deliberately re-runs, and every such re-run is itself a
reviewable event. Future drills keep verdict JSONs small; logs stay ignored.

---

## 2. Half 2 — the serving platform

### 2.1 `make backup` first, and it found a database nobody added by hand

The M4-S2 precedent: give the pre-serving state a copy before new tenants land
beside it. The existing snapshot (`2026-08-18T06-02-29Z`) predates the marts tail
task, so it predates the state M4-S5 leg 2 produced.

```
[backup] destination /home/longt/dvc-remote/nyc-taxi-platform-backups/2026-08-19T02-54-59Z
[backup] 6 database(s) on the server: flyte marts metabase mlflow optuna postgres
  flyte 91.9KiB · marts 1.2GiB · metabase 324.5KiB · mlflow 67.9KiB · optuna 27.1KiB · postgres 393.0B
[backup-minio] 2 bucket(s): flyte-data (184 objects, 0.7 MiB), mlflow-artifacts (147 objects, 443.3 MiB)
[backup-minio] ok  331 object(s) verified on disk by count AND bytes
total on disk: 1.6GiB
```

**Six databases where M4-S2 backed up five, and 331 objects where it mirrored
105.** Nobody edited a list: the script enumerates its targets from the server,
which is exactly the property M4-S2 argued for and this is the first run that has
proved it on a changed cluster. `metabase` grew (295.6 KiB -> 324.5 KiB) and the
object count more than tripled because M4's pipeline runs wrote artifacts.

**RESTORE IS STILL NOT REHEARSED**, and the new `MANIFEST.txt` says so in the
same words as the old one. Every dump is proven COMPLETE (gzip CRC over every
byte plus pg_dump's own completion marker); "these files restore a working
platform" remains a hypothesis and an M6-gameday candidate.

### 2.2 What was installed, and the one decision each piece encodes

| Piece | Pinned | Why this, and not the obvious alternative |
|---|---|---|
| ingress-nginx | chart **4.15.1**, app **1.15.1** | NOT the upstream `provider/kind` manifest: it selects `ingress-ready=true`, a label kind writes only when the kind config asks, and ours does not. The kind config is read at cluster-CREATE only and this cluster is stateful — so the label is unavailable at a price M5 will not pay, and the chart is configured directly instead. |
| cert-manager | chart + app **v1.21.1** | KServe's controller runs admission and conversion webhooks, and a webhook is an HTTPS endpoint the API server calls. The alternative is hand-minted certs with a rotation nobody owns. Deliberately a small install: no ClusterIssuer, no ACME, no DNS solver — nothing here talks to the internet at request time. |
| KServe | charts `kserve-crd` and `kserve-resources` **v0.20.0** (OCI, digests `92deb742d22a…` and `956c4860374f…`) | **Standard / RawDeployment (ADR-004)** — the chart default is `Knative`, which drags Knative Serving and Istio in behind it for a capability M5 does not use. Honest cost, and it lands on M6: **Standard mode has no canary** (`canaryTrafficPercent` requires Serverless — the prior-art ADOPT, found before it cost a session). |

Images, from `helm template` — so this is what the charts resolve, not what a
release note claims: `registry.k8s.io/ingress-nginx/controller:v1.15.1@sha256:594ceea76b01…`
· `quay.io/jetstack/cert-manager-{controller,webhook,cainjector,startupapicheck}:v1.21.1`
· `kserve/kserve-controller:v0.20.0` · `kserve/storage-initializer:v0.20.0` ·
`quay.io/brancz/kube-rbac-proxy:v0.18.0`.

### 2.3 The route is derived, not typed

The kickoff's risk R2 in one sentence: **an ingress controller on a worker
answers nothing and looks exactly like a KServe failure.** Only the control-plane
node carries the `containerPort: 80 -> hostPort: 8081` mapping, and it also
carries the standard `node-role.kubernetes.io/control-plane:NoSchedule` taint —
so the values file needs a hostname nodeSelector *and* a toleration, and either
one alone produces a pod that is Pending or useless.

The node name is a FUNCTION of the cluster name, so the script computes it and
then asserts the values file against it (gotcha #52: the fix that changes a VALUE
leaves the hazard in scope; the fix that derives it removes the hazard):

```
   route        host :8081 -> container :80 on mlops-taxi-control-plane (published at cluster CREATE)
   ok  the ingress values pin scheduling to mlops-taxi-control-plane (derived from …/infra/kind/kind-config.yaml)
   ok  node mlops-taxi-control-plane exists
```

And it landed where it was told, first time — the one line that would have caught
the failure R2 warned about:

```
NAME                                        READY   STATUS    RESTARTS   AGE   NODE
ingress-nginx-controller-74dcb9db98-whhtb   1/1     Running   0          68s   mlops-taxi-control-plane
```

### 2.4 `DRY_RUN=1` mutates nothing, helm included

gotcha #30's rule, inherited again. The preview names every action as a WOULD
line and the branch `exit 0`s rather than falling through:

```
== [3/6] ingress-nginx ==  DRY_RUN — WOULD helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx 4.15.1 -n ingress-nginx
== [5/6] kserve ==         DRY_RUN — WOULD helm upgrade --install kserve-crd oci://ghcr.io/kserve/charts/kserve-crd v0.20.0 -n kserve
DRY_RUN — nothing was installed, nothing was upgraded, no namespace was created.
```

Checked afterwards rather than assumed: `helm list -A` still showed the three
pre-existing releases and nothing else, and no `ingress-nginx` or `cert-manager`
namespace existed.

### 2.5 The install, and the idempotent re-run

First run — 3m13s wall from the first helm call to the accept check, against a
9m49s-for-99MB precedent that made a 20m `--wait` the right size anyway:

```
== [6/6] read it back ==
cert-manager   cert-manager    1  deployed  cert-manager-v1.21.1      v1.21.1
ingress-nginx  ingress-nginx   1  deployed  ingress-nginx-4.15.1      1.15.1
kserve         kserve          1  deployed  kserve-resources-v0.20.0  v0.20.0
kserve-crd     kserve          1  deployed  kserve-crd-v0.20.0        v0.20.0

   kserve defaultDeploymentMode (read from the live configmap): RawDeployment
```

**The mode is read back off `configmap/inferenceservice-config`, not off the
values that were submitted** — a submitted value proves what was asked for, not
what the controller consumes. And KServe's webhook certificate was issued:
`kubectl -n kserve get certificate` -> `serving-cert   True
kserve-webhook-server-cert`, which is cert-manager doing the job it was installed
for, observed rather than assumed.

The re-run is the idempotence evidence, in M4-S2's shape — **every release at
REVISION 2 while every pod is minutes old and unrestarted**:

```
cert-manager   2  deployed      ingress-nginx-controller-…-whhtb    1/1 Running 0 4m44s  mlops-taxi-control-plane
ingress-nginx  2  deployed      cert-manager-{,webhook,cainjector}  1/1 Running 0 3m35s
kserve         2  deployed      kserve-controller-manager-…         2/2 Running 0 2m35s  mlops-taxi-worker2
kserve-crd     2  deployed
```

A clean upgrade that restarted nothing. `kubectl get ingressclass` ->
`nginx (default)   k8s.io/ingress-nginx`, and six KServe CRDs are registered on
Kubernetes **v1.36.1** — the kickoff's risk R1 (KServe against a Kubernetes
version it has never been tested against) did not materialise, and **ADR-004's
plain-mlserver fallback stays armed and unspent**.

### 2.6 The accept check went RED over a perfectly good install, and it was right to

```
FAIL: something answered on :8081 but it is not the ingress controller.
      A foreign holder of this port is gotcha #10's territory — run make ports.
```

Everything was installed and healthy. The route was answering. The check demanded
a **`Server: nginx`** response header as its positive discriminator — and modern
ingress-nginx **omits that header on purpose**. The discriminator was testing for
a signature the deployed thing deliberately suppresses.

This is gotcha #59's lesson (assert positively on the artifact, never on the
absence of an error) applied correctly and then failing at the next question,
which #59 does not ask: *is the artifact you chose one this thing actually
emits?* The replacement was found by asking the server rather than guessing —
the same move M4-S2 made for Flyte's health path, where `/healthcheck` 404s and
`/healthz` answers:

```console
$ curl -sS -o /dev/null -w "%{http_code}\n" http://localhost:8081/healthz
200
$ curl -sS -o /dev/null -w "%{http_code}\n" http://localhost:8081/nginx-health
404
```

`/healthz` is the controller's OWN endpoint, served by its nginx on the same
port. So the accept check is now two parts, and each answers a different
question — did anything answer, and was it the right thing:

```
   curl -sS -o /dev/null -D - http://localhost:8081/
     HTTP/1.1 404 Not Found
     Content-Length: 146
     <html>
     <head><title>404 Not Found</title></head>
     <body>
     <center><h1>404 Not Found</h1></center>
     <hr><center>nginx</center>
     </body>
     </html>
   GET /healthz -> 200

ok  the declared route ANSWERS FROM THE CONTROLLER on http://localhost:8081/
    GET / -> 404 (the pass: the route is up and no InferenceService is behind it yet — that is M5-S2)
    GET /healthz -> 200 (the controller's own endpoint, asked of the server rather than remembered)
```

**The 404 is the pass.** The route answers and nothing matches yet, which is the
correct state until S2 puts a model behind it. The body's `<center>nginx</center>`
is printed as corroboration and is deliberately NOT the discriminator — it would
pass for any nginx on earth. Filed as **gotcha #70**.

Two other candidates were considered and rejected: correlating the request with
the controller's ACCESS LOG (the default backend's 404s are not logged, so a
correct install produces silence — a discriminator that fails on success), and
matching the 404 body, which is the weak signature above.

### 2.7 What half 2 installed, and what it deliberately did not

Installed: a route, a CA, and an operator. **No model, no InferenceService, no
serving runtime, no credential.** `make deploy-serving` does not read `.env`,
passes no `--set`, and a unit test asserts it cannot name `champion`, `models:/`
or `mlflow` in CODE — M5 law 2 ("serving reads the pointer and never moves it")
made falsifiable at the cheapest possible level, a script that does not know the
registry exists. `@champion` is version 2 and nothing this session ran read it.

Sixteen cluster-free tests cover what is wrong in a file rather than in a pod:
the route's node and both ports derived from the kind config on BOTH sides, the
taint/toleration pair, `DRY_RUN` reaching no mutating verb, `RawDeployment` read
back off the live ConfigMap, KServe's ingress class equalling the one this script
installs, every chart version an exact pin, and the two "cannot name the registry
/ cannot read a secret" checks — those last two asserted over CODE ONLY, because
this script argues its own design at length and a word-search greps the argument
(gotchas #53/#68, applied before they bit rather than after).

**What S2 inherits, stated plainly:** the wire is proven and nothing is on it.
The model store credential, the `storage-config` secret, the alias resolution
(F-009) and the F-019 policy decision are all S2's, and none of them is started.
