# LEARNING_GUIDE — field notes, one per story (inherited law from the predecessor)

Law: every story closes with its note BEFORE the next story starts. Format per
note: what was built · why this way · the concept underneath · what to look at ·
what to try yourself. Newest milestone first. The reader is the principal six
months from now.

---

## M0

### M0-S4 — Destroying it on purpose, and a preview that wasn't (2026-08-16, role:MLOps + SRE hat)

**What was built.** Nothing new, and that is the story: the platform three
sessions had carefully assembled was deleted (`make destroy`) and rebuilt from
the recipe alone (`make cluster-up deploy-platform`), then re-gated
(`make verify-m0` → 18/18 GREEN, exit 0). Both helm releases came back at
`REVISION 1` — the proof it was a genuinely fresh cluster and not an upgrade
wearing a rebuild's clothes. Alongside it, the M0 gate's required kill-switch
drill: `automation/STOP` present → the scheduler refuses (`[chain] STOP file
present — not scheduling.`, exit 0, daily counter untouched at 4, no log file
created), STOP removed → the chain schedules its real successor. Two fixes
rode along, both earned by the story rather than planned into it.

**Why this way.** The rebuild's value is entirely in *what it measures*, so the
before/after was instrumented rather than eyeballed. Two fingerprints were taken
before the teardown — `sha256sum .env` and a deliberately created MLflow
experiment, `m0s4-pre-destroy-witness` — and re-read after. The `.env` hash came
back byte-identical (`34cde86f…`), which is what makes the rebuilt Postgres and
MinIO accept the same credentials; the experiment came back
`RESOURCE_DOES_NOT_EXIST`, because the PVCs went with the cluster. That
asymmetry IS the deny list's design: secrets are user-created and unrecoverable,
so `destroy` may never touch them; tracking data is regenerable by re-running
the pipeline, so it is allowed to die. A sentinel file was planted in `data/raw`
for the same reason and read back intact, then removed.

**The concept underneath.** *A dry run must cover the most expensive deletion
first, not last.* The story's very first command — `make destroy DRY_RUN=1`, run
to check the preview before trusting the real thing — deleted the entire kind
cluster and then printed `[destroy] DRY_RUN=1 — nothing was deleted.` The file
loop was guarded; `cmd_down` sat one line above the guard. It cost nothing only
because the next command was going to destroy the cluster anyway, which is luck,
not process.

The second half is worth more than the bug. A test named
`test_destroy_dry_run_deletes_nothing` had been green since M0-S2. It ran
against a sandbox whose kind config named a cluster that cannot exist — so the
delete path always no-opped, and the test could not have failed if it tried.
**The isolation that made the test safe made it blind.** The repair is not "test
against a real cluster" (that is how you delete a real cluster); it is to give
the sandbox a fake `kind` that *records* its calls and assert on the recording,
plus a positive control proving the fake fires when it should. Same shape as
gotcha #29 from the previous story, one level up: there, a PASS branch nobody
had watched be wrong; here, a FAIL branch that could never be reached.

The kill-switch drill has the same seam. The half a human can drill by hand —
STOP present when you *ask* for a session — is the easy half. The half that
matters at 3am is STOP created *after* a session is already scheduled, while it
sits in its `sleep`; drilling that live means either launching a real Claude
session or trusting a guard nobody watched work. So it is tested instead, in
`tests/unit/test_chain_script.py`, against a sandboxed copy of the scheduler
whose `claude` is a shim that drops a marker file. Four properties, each really
executed: it launches when nothing stops it (positive control first, or every
refusal below proves nothing), it refuses outright with STOP present, STOP
written *after* scheduling still kills the pending session, and the daily cap
halts the chain while leaving a note where the PO actually looks.

**What to look at.** `scripts/cluster.sh` `cmd_destroy` — the DRY_RUN branch and
the `DENY` array above it, read as a pair · `tests/unit/test_cluster_scripts.py`
`_sandbox_with_live_cluster` (the recording shim) · `tests/unit/
test_chain_script.py` (the kill switch, tested where a real session cannot be
spawned) · `docs/gotchas.md` #30 · `ledgers/deployments.md`, whose newest row
carries the survived/died measurements.

**What to try yourself.** Revert the four-line DRY_RUN guard in
`scripts/cluster.sh` and run `uv run pytest tests/unit/test_cluster_scripts.py`:
the new test fails and quotes `[cluster-down] deleting kind cluster` sitting
directly above `nothing was deleted` — that pairing is what a blind test looks
like when it finally opens its eyes. Then delete the whole platform and rebuild
it while timing yourself; if the rebuild is boring, the recipe is real, and if
any step needs a human to remember something, that step is not in the recipe yet.

### M0-S3 — The platform: MinIO, Postgres, MLflow, and a gate that says no (2026-08-16, role:MLOps)

**What was built.** `make deploy-platform` brings up the three services the whole
program leans on — MinIO (the S3), one Postgres (the one database), MLflow
(tracking + registry) — and `make verify-m0` proves it in 18 sub-checks, exit
nonzero on any miss. MLflow's UI answers at http://localhost:5000, MinIO's
console at :9001, and MLflow's artifacts really land in MinIO while its runs
really land in Postgres. Credentials are generated into a gitignored `.env` and
pushed into Kubernetes Secrets by `scripts/platform_secrets.sh`; no secret is
ever printed, and none is in git.

**Why this way.** Five choices worth the ink.

*(1) Postgres by plain manifest, not by chart.* The obvious pick, bitnami's
`postgresql`, today defaults to `registry-1.docker.io/bitnami/postgresql:latest`
— a rolling tag — and its pinned tags now live in a frozen `bitnamilegacy`
registry. The MLOps charter refuses unpinned versions, so the "standard" chart
would have forced either an unpinned image or a dependency on a deprecated
registry. Fifty lines of YAML we own, with the image pinned by digest, is the
cheaper honest answer. Note the shape of that decision: the popular choice was
rejected on a *property* (pinnability), not on taste.

*(2) MLflow by community chart, and the reason is a missing driver.* MLflow's own
image ships without `psycopg2` or `boto3` — so a Postgres backend plus S3
artifacts needs an image somebody builds. M0 builds no image of ours (that
decision is parked as debt D-001 until M4), and the community chart's image
carries both drivers. So: chart where the chart earns its keep, manifest where it
does not. "Use helm for everything" is a policy; "use the thing whose failure mode
you can live with" is engineering.

*(3) The host route is declared, not forwarded.* `kubectl port-forward` is a
process a human has to remember to start — a manual deploy step wearing a
disguise. Instead the kind config maps hostPort 5000 → containerPort 30500, and a
Service claims nodePort 30500. The cost is honest and worth naming: kind
publishes ports only at cluster-CREATE time, so adding a port means destroying
and rebuilding the cluster. The benefit is that a fresh `make cluster-up` on a
new laptop gives you localhost:5000 with nobody typing anything.

*(4) `.env` is the source of truth, and it is generated once.* Re-generating
passwords on every deploy would be "idempotent" in the trivial sense and
catastrophic in practice: the old password is already baked into the Postgres data
directory. So the script generates only when `.env` is absent, then converges the
Secrets to it every run. This is why `.env` is on `destroy`'s protected list.

*(5) MLflow gets its own MinIO identity.* The chart ships a default user
`console`/`console123`; overriding the user list removes it, and MLflow
authenticates as `mlflow` with `readwrite` — so a leaked MLflow credential cannot
reconfigure the object store. The access key is a *username* and lives in git; the
secret key never does.

**The concept underneath.** *Verify the thing, not a proxy for it.* This story's
best moment was a failure of my own check. `verify-m0` asked "did the Deployment
roll out?" — and when the red-team scaled MLflow to **zero replicas**, `kubectl
rollout status` answered *"successfully rolled out"*, exit 0, because zero
replicas is a complete rollout. The script printed a green line for a service that
had ceased to exist, while every URL check beside it failed. Readiness is now
asked as a number (`readyReplicas >= 1` **and** `== spec.replicas`), and the
lesson is bigger than kubectl: a check whose PASS branch you have never watched be
wrong is a check you have not tested. That is gotcha #29. Its sibling, gotcha #28,
came from the same session's first deploy: MLflow logged *"Application startup
complete"* four times and then vanished — OOMKilled at exit 137 by its own default
of four uvicorn workers. The logs were clean, because a process does not get to
log its own OOM kill. **When a container dies without complaining, read the pod
object, not the log stream.**

**What to look at.** `scripts/verify_m0.sh` (start at `workload_ready` and the
comment above it — that is the red-team's scar) · `infra/manifests/postgres.yaml`
(the header argues the chart-vs-manifest choice) · `scripts/platform_secrets.sh`
(the chain of custody from `.env` to pods) · `tests/unit/test_platform_scripts.py`
(the port-twin tests: two files holding the same number, and a test that fails
when they drift).

**What to try yourself.** Run `make verify-m0` — it should be green. Now break it
on purpose, three different ways, and predict the output before each: `kubectl -n
platform scale deployment/minio --replicas=0`; `kubectl -n mlflow delete secret
mlflow-s3`; change `nodePort: 30500` in `infra/manifests/mlflow-nodeport.yaml` to
`30501` and re-apply. Which failures does the gate catch loudly, which one does it
catch only through a URL, and which one does `make test` catch before you ever
reach the cluster? Then run `make deploy-platform` and watch it put everything
back.

### M0-S2 — Cluster up, idempotent, with a pre-check that says no (2026-08-16, role:MLOps)

**What was built.** Three real make targets behind two shell scripts:
`make cluster-up` (kind create from `infra/kind/kind-config.yaml`, skip-if-exists),
`make cluster-down`, `make destroy`, plus `make ports` — the gotcha #10 pre-check
that refuses to build on top of another project's stack. The kind node image is
now pinned by digest in the config; the cluster is a 3-node `mlops-taxi` running
Kubernetes v1.36.1.

**Why this way.** Four choices worth the ink. (1) *The pre-check runs only on the
create path.* Once our own cluster is up it holds 8081/8443 itself — a pre-check
on the no-op path would refuse **because we had succeeded**, and idempotence would
die on its own success. That is not a hypothetical: after cluster-up, `ss -tlnp`
inside WSL really does show those two ports held by docker. (2) *The cluster name
and the checked port list are parsed from the config, never re-typed* — two copies
of a fact drift, and the drift is always discovered by an outage. (3) *`destroy`
works from an explicit allowlist of regenerable paths, screened by a deny-list
guard* that resolves symlinks and repo-escapes before deleting anything: `data/raw`,
`.env`, `.git`, `.dvc/cache`, `.venv` can never be reached, even through a future
typo. `.dvc/cache` is on that list because with a local-only DVC remote the cache
IS the only copy — "regenerable" is a claim about a command that can rebuild it,
and if you can't name the command, it isn't. (4) *The node image is pinned even
though it equals kind 0.32.0's default*, because a default is a decision somebody
else can change on your behalf.

**The concept underneath.** *A check that has never said no is decoration.* The
accept-when for this story did not ask "does the pre-check pass" — it asked for the
pre-check to be **red-teamed**: a dummy listener on 5000, an observed refusal that
names the port and the process holding it, then a pass once the listener dies. The
same instinct drives the unit tests: they don't test that `destroy` deletes, they
test that it *refuses* — that a `data/raw` file and a `.env` survive it. Every
safety mechanism in this repo should be able to show you the transcript of the day
it said no. The mirror-image lesson is idempotence: "run it twice" is the cheapest
production question there is, and it is the one that caught the pre-check ordering
bug before it was ever written.

**What to look at.** `scripts/port_precheck.sh` (the refusal message names the port,
its purpose, and the holder — a good refusal tells you what to do next) ·
`scripts/cluster.sh` `guard_path()` · `tests/unit/test_cluster_scripts.py`, which
exercises `destroy` against a sandbox copy pointed at a cluster name that cannot
exist, so the test can never delete the real one · `ledgers/findings.md` F-002, the
honest limit of a WSL-side port check · `ledgers/debt.md` D-001, an undated
`TODO(M0)` converted into a carry with a quoted landing.

**What to try yourself.** `make cluster-up` twice, then `python3 -c "import socket;
s=socket.socket(); s.bind(('0.0.0.0',5000)); s.listen(); input()"` in another
terminal and `make cluster-down && make cluster-up` — watch it refuse. Then delete
the `image:` lines from the kind config and re-create: same cluster today, and a
different Kubernetes version the day the toolchain moves. That gap is what a pin is.

### M0-S1 — WSL residency, toolchain & pins; the first PR proves CI (2026-08-16, role:MLOps)

**What was built.** Not code — an *environment you can prove*. kind 0.32.0,
helm v3.19.0 and uv 0.12.5 installed sudo-free into `~/.local/bin` (kubectl
v1.36.1 was already there); the project env created on a uv-managed **Python
3.12.14** even though the machine's system Python is 3.14.4; `ruff` and
`pytest` added to the dev group so the CI file that was written on day one
finally has something to run; `uv.lock` committed; every observed version
written into CLAUDE.md's pin table with the command that produced it.

**Why this way.** Three deliberate choices. (1) *Sudo-free, user-local
install*: a toolchain in `~/.local/bin` can be deleted and rebuilt by the same
unattended session that installed it — a toolchain in `/usr/local` needs a
human with a password every time it is wrong. (2) *`.python-version` = 3.12,
pinned against the system 3.14*: `ci.yml` runs `uv python install 3.12`, so
without the pin the laptop and CI would be running different interpreters and
the first genuinely confusing bug would be a version skew that neither
environment can see. Parity is worth more than newness. (3) *`uv add` rather
than hand-written pins*: pyproject shipped with the instruction "do not
pre-pin from memory" — the resolver observed 0.16.3 / 9.1.1 live today and
`uv.lock` now holds the exact graph, which is the artifact that actually makes
a build reproducible.

**The concept underneath.** *A milestone-zero is a claim about reality, and
claims decay.* The kickoff's precondition table was written the day before
with ten rows marked ⛔; S1's only real job was to re-run every one of them
live and paste what came back, because a precondition believed is not a
precondition. This is the same instinct as a pin table that records the
*command* next to the version: six months from now the number is worthless
unless you can re-derive it. The corollary bit this session — one row
(`claude --version`) could NOT be re-derived, so it is recorded as unread
rather than copied forward from the Windows preflight. An honest gap beats an
inherited number.

**What to look at.** `CLAUDE.md` pin table (every row carries its command and
date) · `.python-version` next to `.github/workflows/ci.yml` — read them as a
pair · `uv.lock` · `docs/gotchas.md` #26, this story's earned tuition · the
PR's green CI run, which is the M0 gate's "CI live" leg proving itself on its
own first use.

**What to try yourself.** Delete `~/.local/bin/kind` and re-run the install
lines from the handoff — that is the "can this be rebuilt?" test, and it is
the only version of that question that ever gets a truthful answer. Then run
`uv run pytest tests/unit -q` with `.python-version` temporarily set to 3.14
and watch what changes (and what doesn't) — the skew you can't see is the
whole reason the pin exists.
