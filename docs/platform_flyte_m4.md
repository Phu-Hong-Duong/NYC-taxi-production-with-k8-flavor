# M4-S2 — the lifeboat, the port guard that stopped telling us to shoot ourselves, and Flyte 2 on the cluster

Session: EXECUTOR / `claude-opus-5`, role:MLOps, 2026-08-18.
Story: `docs/milestones/M4_KICKOFF.md` § M4-S2.

**What landed, in one line each.** `make backup` — the platform's first copy that
survives the cluster · **F-021 CLOSED** — `make ports` now names the holder and
exits 0 when the holder is us · **Flyte 2.0.42 deployed** and reachable from WSL
· **the hello-workflow does NOT complete** — walled at code-bundle upload, filed
as **F-023**, and §5 says exactly where the cut is.

**The cluster never went down.** Node age 27h across all three, every pre-existing
pod still Running, `@champion` → version 2, run `92b73bd4f77d…`, versions [1, 2],
read before and after and identical.

---

## 1. `make backup` — the lifeboat, taken BEFORE the new tenant

The order is the point. Flyte becomes the fifth tenant of the one Postgres in §4;
the backup ran first, so the copy on disk is of the platform *as M3 left it*.

```
== platform backup ==
[backup] destination /home/longt/dvc-remote/nyc-taxi-platform-backups/2026-08-18T06-02-29Z
[backup] limits: same physical disk · restore NOT rehearsed (M6 gameday candidate) · per-database snapshot
[backup] 5 database(s) on the server: marts metabase mlflow optuna postgres
[backup] ok  marts    -> 1.2GiB    in 210s, gzip CRC clean, ends with pg_dump's completion marker
[backup] ok  metabase -> 295.6KiB  in 0s,   gzip CRC clean, ends with pg_dump's completion marker
[backup] ok  mlflow   -> 53.9KiB   in 0s,   gzip CRC clean, ends with pg_dump's completion marker
[backup] ok  optuna   -> 27.0KiB   in 1s,   gzip CRC clean, ends with pg_dump's completion marker
[backup] ok  postgres -> 389.0B    in 0s,   gzip CRC clean, ends with pg_dump's completion marker
[backup-minio] endpoint http://localhost:9000 — 1 bucket(s): mlflow-artifacts
[backup-minio] mirrored mlflow-artifacts: 105 object(s), 352.3 MiB
[backup-minio] ok  105 object(s) verified on disk by count AND bytes
total on disk: 1.5GiB
```

**Targets are enumerated from the server, never from a list.** Every non-template
database is dumped; every bucket is mirrored. A hardcoded list would be a twin of
`scripts/postgres_databases.sh`, and a backup whose target list drifts is worse
than no backup — it succeeds, prints a size, and silently omits what somebody
added last month. This story is its own proof: Flyte's `flyte` database and
`flyte-data` bucket arrive in §4 and are covered by the next run because nobody
had to remember them.

**What the verification actually proves, and what it does not.** Each dump is read
back on the host in full: `gzip -t` runs a CRC over every byte, and pg_dump's own
`-- PostgreSQL database dump complete` must appear in the closing lines. Both
legs were proven against a **deliberately truncated copy** of the real 1.2 GiB
dump before being trusted (`gzip -t` rc 1, marker check rc 1). What it does not
prove is that these files restore a working platform: **no restore has ever been
performed from this directory.** That limit is in the script header, in every
`MANIFEST.txt`, and in the deployments ledger row. A rehearsal is an M6-gameday
candidate; M4 ships the lifeboat, not the drill.

**The honest cost, recorded because whoever schedules this needs it.** `marts` is
**1.2 GiB and 210 s of the backup's ~4 minutes**, and it is the one database this
program can already rebuild exactly from DVC-pinned inputs — M1-S5 proved it on a
fresh volume, `dbt build` then `COPY 56127878`, "identical to M1-S4's counts to
the row". The other four total **377 KiB and under 2 seconds** and are the ones
that cannot be rebuilt at all. The kickoff names every database and every
database is dumped; the observation is passed to **M7**, which is where a
scheduled backup would start paying this monthly.

### 1a. The verification design was wrong twice, and both are recorded

The first design was `pg_dump -Fc` verified by `kubectl exec -i … pg_restore
--list`. It had to be replaced, not tuned (**gotcha #54**):

* **It could not detect the failure it named.** A custom-format archive keeps its
  table of contents at the FRONT, so `--list` succeeds on a file whose tail was
  never written — exactly the truncation the check existed to catch. That is
  gotcha #51's question ("could this component tell if it were false?") asked of
  a *verifier*, and the answer was no.
* **It hung.** With stdin redirected from a **1 MB** dump the exec did not return
  after 120 s, twice, having worked once on a **1.2 GB** one.

The replacement then went red twice more for reasons of its own (**gotcha #55**),
each costing a 3.5-minute re-dump: the completion marker is **not** the last line
(Postgres 16.11 closes with a `\unrestrict <token>` meta-command after it), and
`grep -qF "$MARKER"` read the marker's leading `--` as an end-of-options flag and
died with a usage message *while the script reported "the dump was cut short"*.
A verifier that fails for its own reasons and blames the artifact is gotcha #50
one layer down.

---

## 2. F-021 — the port guard now names the holder

Before: with the cluster up, `make ports` refused on 6 of 10 ports and told the
reader *"another stack on this machine owns a port we need. Free it (stop that
stack)"*. Obeying that deletes the PVCs holding the only copy of the registry,
both Optuna studies and the Metabase app-db.

`ss` cannot answer "whose?" — a published port is held by docker-proxy, not by
the workload. Docker can: kind publishes a cluster's hostPorts on its NODE
containers, named `<cluster>-*`, and the cluster name is parsed out of
`infra/kind/kind-config.yaml` rather than hardcoded.

```
$ make ports
[ports] 6 port(s) held by US — the 'mlops-taxi' cluster is up, which is expected:
  port 3030 (Metabase) -> container mlops-taxi-control-plane
  port 5000 (MLflow UI) -> container mlops-taxi-control-plane
  port 8081 (KServe ingress) -> container mlops-taxi-control-plane
  port 8443 (kind hostPort) -> container mlops-taxi-control-plane
  port 9000 (MinIO API) -> container mlops-taxi-control-plane
  port 9001 (MinIO console) -> container mlops-taxi-control-plane
[ports] Do NOT 'free' these. The cluster is STATEFUL: its PVCs hold the only
[ports] copy of the MLflow registry, the Optuna studies and the Metabase app-db.
[ports] OK — 10 required port(s): 4 free, 6 held by us, 0 foreign.
```

**The foreign refusal was not softened.** Both states are pinned by tests that
differ in ONE thing — the container name — against the same bound ephemeral port
and the same fake `docker ps`: `mlops-taxi-control-plane` → exit 0 `held by US`,
`somebody-elses-stack-web-1` → exit 2 `REFUSING`. A fix that stopped reading the
name fails one of them. The pre-existing fake-listener red-team (no docker shim
at all) still goes red. If `docker` is absent the OURS set is empty and every
busy port reads foreign — the pre-F-021 behaviour, which is the safe direction to
fail in.

---

## 3. Which chart is which (the names invert the intuition)

Read live 2026-08-18 with `helm search repo flyteorg --versions`:

| Chart | Version today | What it actually is |
|---|---|---|
| `flyteorg/flyte-binary` | **v2.0.42** | the unified **Flyte 2** manager (`flyte-core-components`, image `cr.flyte.org/flyteorg/flyte-binary-v2`) |
| `flyteorg/flyte-binary` | v1.5.1 (appVersion 1.16.0) | the **1.16.x** single binary — ADR-002's pre-approved fallback |
| `flyteorg/flyte-core`, `flyteorg/flyte` | v1.16.8 | the 1.16.x multi-component line |

ADR-002 said "Flyte 2.x primary, flyte-binary 1.16.x as the fallback" and checked
`v2.0.24 / v1.16.7` on 2026-08-12. In today's repo that reads as **flyte-binary
v2.0.x primary, flyte-binary v1.5.x fallback** — same decision, current names.
Both are recorded in `scripts/deploy_flyte.sh`'s pin block so the next reader does
not have to re-derive it at the wall.

**Flyte 2 needs ONE database, not two.** The kickoff budgeted "flyteadmin/
datacatalog … fourth and fifth consumers" — the 1.x shape. The unified binary
reads a single `runs.database`, so D-002 gained exactly one line and held a
**fourth** time.

---

## 4. `make deploy-flyte` — green, and idempotent by observation

Order: namespaces → secrets → the `flyte` database (D-002) → MinIO (bucket +
user) → the chart. It re-runs the platform pieces it depends on rather than
documenting "run `make deploy-platform` first" (the M1-S5 rule), so it cannot be
defeated by running order. The MinIO re-run is not ceremony: the chart's
post-install Jobs are what create `flyte-data` and the `flyte` user idempotently,
so the bucket comes into being from the recipe rather than from somebody's `mc mb`.

```
[pg-db] flyte: before = role absent, database absent
[pg-db] ok  flyte owner=flyte
[pg-db] 5 database(s) converged (no password printed, by design)
...
Release "flyte" has been upgraded. Happy Helming!
NAME: flyte   NAMESPACE: flyte   STATUS: deployed   REVISION: 2
deployment "flyte-flyte-binary" successfully rolled out
deployment "flyte-flyte-binary-console" successfully rolled out
deployment "flyteconnector" successfully rolled out

NAME                                          READY   STATUS    RESTARTS   AGE
flyte-flyte-binary-6d7974cc56-vblg2           1/1     Running   0          17m
flyte-flyte-binary-console-6f57756d8f-cjcln   1/1     Running   0          17m
flyteconnector-5958fd9868-g546g               1/1     Running   0          17m
```

**The pod ages are the idempotence evidence.** The re-run reported all three
deployments rolled out while every pod was 17 minutes old — a clean upgrade that
restarted nothing.

**The first install failed for a reason that was not Flyte.** `Error: context
deadline exceeded` at `--wait --timeout 10m`, with all three pods healthy: the
console image (`ghcr.io/unionai-oss/flyteconsole-v2`, 99 MB) took **9m49s** to
arrive, so the wait expired about ten seconds after the container finally
started, and helm marked the release `failed` anyway. The timeout is now 20m with
that measurement written beside it — a first install on a fresh clone pulls this
image cold, not warm.

**No secret is on a command line.** The chart renders its database password and
S3 secret key out of VALUES, so `deploy_flyte.sh` writes a mode-600 temporary
overlay and deletes it on EXIT. `--set` would put both in `ps` output and in
shell history. `DRY_RUN=1` mutates nothing at all, including the helm upgrades —
gotcha #30 is the precedent for taking that seriously.

**The console image is pinned by TAG AND DIGEST** (`latest@sha256:3cea5ec7…`),
the Metabase precedent. The chart's default is the bare tag `latest`, which is
not a pin: the same values file would deploy a different console next week and
`IfNotPresent` would hide it on this machine.

### 4a. Console access — the recorded deviation

Everywhere else a route is DECLARED, never port-forwarded. Flyte gets no
hostPort, and this is recorded rather than drifted into:

* kind publishes host ports at cluster-CREATE time only, so declaring 8080 means
  `kind delete` + `kind create`, which the M4 kickoff's top law forbids while the
  cluster holds the only copy of the registry, the studies and the app-db;
* there is no ingress **controller** here yet (`kubectl get ingressclass` → *No
  resources found*; one arrives with KServe at M5), so `ingress.create: true`
  would render an Ingress nothing reconciles — a route that *looks* declared and
  answers nothing, which is worse than an honest port-forward.

Port **8080 stays reserved** in CLAUDE.md's port family for the next
PO-sanctioned rebuild. The doctrine is deferred with a date and a reason, not
repealed.

`make flyte-console` forwards the **API**, and says out loud that it does not
forward the browser console and that forwarding it would not help: the console is
a same-origin SPA and needs both behind one host.

```
$ bash scripts/flyte_console.sh --check
[flyte-console] ok  API answers: GET /healthz -> 200 (svc svc/flyte-flyte-binary-http:8090)
```

The health path was **asked of the server, not remembered**: `/healthcheck` (the
Flyte 1.x path, and my first guess) returns 404; `/healthz` and `/readyz` return
200 `OK`.

---

## 5. The hello-workflow does NOT complete — where the cut is

**Wall: "one hello-workflow runs remotely to completion", attempts: 5.** Recorded
per the three-attempt rule and not attacked further this session.

What the five attempts established, because each failed differently and each fix
stands:

1. `set -e` inside `out="$(...)"` exits the script *there*, so the output
   explaining the failure was discarded exactly when wanted (exit 2, no
   diagnosis). Fixed — `|| rc=$?`, print, then judge.
2. `--project`/`--domain` are **subcommand** options, not root ones; `--endpoint`
   and `--insecure` are root. (`uv run --project` is a third, unrelated flag of
   the same name.) Fixed.
3. `flyte create project` takes `--id` and `--name`, not a positional. The
   swallowed failure surfaced three steps later as `project "nyc-taxi" not
   found` **at code upload**, which reads like storage and is not. Fixed —
   project `nyc-taxi` now exists and is listed by `flyte get project`.
4. and 5. **The actual blocker, and it is architectural.**

```
  > Launching remote execution...
  ✓ Built image for environment hello: ghcr.io/flyteorg/flyte:py3.12-v2.6.1
  ✓ Code bundle: 1 files, 0.0098 MB (compressed 0.0012 MB)
  > Uploading code bundle...
  ✕ Execution failed: Failed to upload …fast….tar.gz after 3 retries:
    ConnectError: [Errno -2] Name or service not known
```

The blob store is ONE MinIO with TWO names: pods reach it as
`minio.platform.svc.cluster.local:9000`, this host reaches the same server as
`localhost:9000` (the kind hostPort → nodePort 30900 route from M0-S3). The CLI
uploads its code bundle **directly** to the object store, and with only the
server's endpoint in hand it resolves an in-cluster DNS name from outside the
cluster. Setting the SDK's documented client-side variables
(`FLYTE_AWS_ENDPOINT` / `FLYTE_AWS_ACCESS_KEY_ID` / `FLYTE_AWS_SECRET_ACCESS_KEY`,
which `flyte.storage.S3` maps onto its fields) **did not change the symptom** —
so the endpoint is coming from somewhere else (server-advertised storage config
or a dataproxy-issued URL), and finding out where is the next session's first
question, not a fifth attempt in this one.

**This is NOT ADR-002's wall and the fallback has NOT been executed.** ADR-002's
trigger is "Flyte 2.x fights on **deployment or MLflow interop**". Deployment
succeeded: three pods Running, helm `deployed`, `/healthz` 200, and the CLI
demonstrably reaches the control plane — it created a project, listed projects,
resolved the task image and built the bundle. One client-side data path fails.
Swapping charts on that evidence would discard a working control plane to fix a
URL, and ADR-002's fallback stays armed for the moment its own condition is met.
Worth noting for whoever picks it up: Flyte **1.x** ships
`storage.signedUrl.stowConfigOverride` for precisely this split-horizon case and
the 2.x chart renders no equivalent — which is either the reason to fall back or
the hint for where 2.x hides it.

**What this costs and what it does not.** It costs S2 its last accept-when leg.
It does not block M4-S3 (the task image: build, `kind load`, D-001/D-004 — no
Flyte API involved), and S3 is the story that would make the real pipeline image
available anyway. The next session's cheapest probes, in order: read what the
server advertises (`flyte get …`/the config the pod loaded), try a run with the
bundle path pointed at the NodePort address the node container has on the docker
bridge (one name both sides can resolve), and only then ADR-002.

Filed as **F-023**.

---

## 6. Decisions recorded (craft-level, inside scope, verified undo)

* **Targets enumerated from the server, not listed** — a backup whose target list
  can drift is worse than none. Undo: one commit.
* **Plain SQL + gzip over `-Fc`** — the verification can then run entirely
  host-side and read every byte; the honest cost is no selective/parallel
  restore, and the restore is simpler for it (`zcat | psql`).
* **`flyteconnector` left ON** (chart default, unused here). A first install
  should be the chart's own shape; switching off a subchart to save one small pod
  buys nothing measurable and risks an unexplained render failure. Named so S4
  can disable it deliberately if the 24Gi train task collides with it.
* **`flyte` gets its own MinIO identity and its own bucket**, like MLflow's — a
  leaked orchestrator credential must not reach the registry's artifacts. Honest
  limit: `readwrite` is MinIO's built-in bucket-wide policy; narrowing it to
  `flyte-data` needs a custom policy document the chart has no hook for.
* **`make flyte-hello` stays in the tree, labelled BLOCKED in its own help text.**
  A known-failing target that looks healthy is a trap; one that names its finding
  is where the next session starts.
