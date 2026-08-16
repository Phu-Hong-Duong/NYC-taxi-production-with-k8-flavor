# LEARNING_GUIDE — field notes, one per story (inherited law from the predecessor)

Law: every story closes with its note BEFORE the next story starts. Format per
note: what was built · why this way · the concept underneath · what to look at ·
what to try yourself. Newest milestone first. The reader is the principal six
months from now.

---

## M1

### M1-S2 — Two witnesses, a pin that must not touch what it measures, and a review that found four things (2026-08-16, role:DE + DA hat)

**What was built.** `data/raw` and `data/processed` went under DVC with a
file-system remote *outside* the repo; `make data` became the whole path
(ingest → DuckDB → pin, in that order); `data/analyst.duckdb` became nine
**views** — no rows copied — that the DA queries by name; and `make
rebuild-proof` turned the M1 gate's byte-identity leg into a command anyone can
re-run. It ran: `data/processed/` deleted, rebuilt by one command from
DVC-pinned raw, **8 of 8 outputs byte-identical**, 56,127,878 rows reconciling
month by month against what S1's reports claimed. Then the Data Contract Review
raised four challenges, two of which changed the shipped code. 79 unit tests
(was 57), no cluster, no network.

**Why this way.** Four choices, and the interesting ones are the refusals.

*(1) The proof must not write to what it measures.* The obvious rebuild proof is
"wipe, run the rebuild command, compare hashes". But the rebuild command ends in
`dvc add`, which re-hashes the outputs and rewrites the pin — so the comparison
would be against a pin computed from the very bytes under test. It would pass
forever, including on the day the parquet writer stopped being deterministic.
Hence `SKIP_DVC=1`, which exists for exactly one caller and says so in a comment
at both ends. This is the whole genre of green-forever test: not wrong output,
but a test whose reference moves with its subject.

*(2) Two witnesses, computed differently.* The proof compares our own sha256
table AND asks `dvc status data/processed.dvc` — different code, different
metadata, same question. One witness agreeing with itself is not evidence; it is
a tautology with a checkmark. The same instinct as M1-S1's two rejection counts.

*(3) The remote is a directory outside the repo, and MinIO was refused.* The
tempting choice was MinIO — it is already running, it speaks S3, it would demo
beautifully. It lives on a PVC inside the kind cluster, and `make destroy` takes
PVCs with it. A backup that dies with the thing it protects is worse than no
backup, because you stop worrying. The honest cost is written down rather than
hidden: the remote is on the same physical disk, so it survives `make destroy`
and a wrong `rm -rf`, and it does not survive disk loss.

*(4) `dvc init` turns analytics on, and a default is not an exemption.* The init
banner says it plainly and then scrolls away. This program's rule is one
sentence — nothing leaves this machine — so the fix was `core.analytics false`
plus a unit test, because a future `dvc init` on a fresh clone would restore the
default silently.

**The concept underneath.** *A number that reconciles is worth more than a
number that is merely produced.* Every piece of this story is the same shape
twice: the analyst layer does not just publish `trips_clean`, it exits 1 if the
view's row count disagrees with the ingest report that wrote the data — because
a catalogue pointing at five months of eight answers every query happily and
just returns smaller numbers, which is a failure with no symptom. The rebuild
does not just re-run, it re-runs and is checked from two directions. The review
does not just read the contract, it runs queries against it. The recurring enemy
is the *silent* wrong answer, and the recurring weapon is a second, independent
statement of the same fact.

The review is where this paid off most. The DA read a contract that S1 had built
carefully and, in four queries, found: 914,459 rejected rows that exist only as
counts (so nobody can say whether the 159,300 trips over two hours were meter
faults or a real long-haul population); a 261,781-row null batch that is
**exactly** coincident across four columns, one of which encodes it as
`payment_type = 0` — a value that reads on a dashboard as a payment category;
a `$671,123.14` taxi fare against a 99.9th percentile of `$85.50`; and
`VendorID 5`, which appears 219 times in 56 million rows and **only ever inside
the broken batch**. Two of those became a change (`unknown_domain_values`, which
reports without cleaning), one was answered with the number that settles it (12
rows; the mean moves 0.26%), and one was carried as a finding with the DA's
dissent recorded rather than argued away. A review that produces no change is
not a review, and a review whose disagreement disappears into consensus is worse.

**What to look at.** `scripts/rebuild_proof.sh` — read the header, then the
`SKIP_DVC=1` line, then gotcha #33; they are one idea in three places ·
`docs/rituals/2026-08-16_data-contract-review.md`, especially §4 Dissent ·
`src/taxi_mlops/data/analyst.py`'s module docstring on why `split` and `month`
are config literals and never parsed from filenames · `ledgers/findings.md`
F-005, an item deliberately NOT converted into debt.

**What to try yourself.** Break the proof on purpose, both ways, and watch which
guard catches you: append twenty bytes to a file in `data/raw/` and run `make
rebuild-proof` (it refuses at step 2 and deletes nothing — the input is not the
pinned bytes); then `uv run dvc checkout data/raw.dvc --force` and instead drop
one row from a file in `data/processed/` before running it (the rebuild restores
the true bytes, so the table prints `NO` next to that one filename). Then try
the version that *should* worry you: delete `SKIP_DVC=1` from the script and run
the second experiment again. It passes. Sit with that for a moment — that is
what a green test looks like when the reference moved with the subject.

### M1-S1 — A contract that can say no, and 914,459 rows that were counted out loud (2026-08-16, role:DE)

**What was built.** `taxi_mlops.data` became real: `make ingest` downloads the
eight configured months (skip-if-present, retried, sha256-pinned in
`data/raw_manifest.json`), reads them, applies a **year-aware pandera contract**
and the one and only dtype cast in the codebase, derives
`trip_duration_minutes`, drops impossible rows against **named, counted rules**,
re-validates the result against an output contract, and writes each month under
its split. 57,042,337 rows in, 56,127,878 out, 914,459 rejected — 1.603%, every
one of them attributable to a rule by name. Two red-teams: a seeded corrupt
parquet (`CorruptSourceError`, exit 1, `processed/` never created) and a
truncated pinned file (`ChecksumDriftError`, exit 1, the existing output's
sha256 and the manifest pin both untouched). 57 unit tests, no cluster, no
network.

**Why this way.** Three choices did most of the work.

*(1) Structure refuses; rows get counted.* A missing, renamed, or unknown column
refuses the entire month — you cannot drop your way out of a column that isn't
there. A passenger count of 42 is one bad row, so it is counted against
`passenger_count_out_of_range` and dropped. Collapsing those two into one
mechanism is how data pipelines end up either crashing on a typo or silently
shipping a thinned month; `max_rejected_fraction` (0.10) is the seam between
them — past it, cleaning becomes refusal again.

*(2) Two counts per rule.* `rejected_by` attributes each dropped row to the
**first** rule it violates, so the column sums exactly to rows-dropped and the
table balances. But that alone makes any rule sitting behind an overlapping
earlier one read `0` — indistinguishable from a rule that has stopped working.
So `matched` reports independent hits alongside. In 2019-01 the difference is
loud: `distance_non_positive` shows 11,446 attributed against 55,089 matched —
44 thousand zero-distance trips were *already* rejected as too short. One number
would have hidden that; two make it a fact about the data.

*(3) `nullable: false` in the config means a POST-clean guarantee.* The input
contract is deliberately permissive about nulls, because raw is raw. The output
contract enforces the guarantee *after* the rules have run — which turns it into
a live check on the rules themselves. If `location_out_of_range` ever stops
firing, the output contract refuses the month instead of handing an out-of-range
zone id to a model six milestones later. There is a test that breaks that rule
on purpose to watch it happen.

**The concept underneath.** *Schema drift has three shapes, and only one of them
is loud.* Gotcha #6 said TLC adds columns by year, so the contract was built
year-aware. Diffing 2019's arrow schema against a live 2025 probe — 30 seconds
of curl, because the project's rule is observe-don't-remember — showed the other
two shapes. `airport_fee` becomes **`Airport_fee`**: same field, capital A. And
six columns change physical type (`VendorID` int64→int32, `passenger_count`
double→int64, and so on). An *added* column announces itself the first time
something asks for it. A *renamed* one hands you an all-null column that looks
exactly like missing data. A *retyped* one doesn't complain at all — it just
makes two years quietly disagree. That is now gotcha #31, and the contract
answers all three the same way: `aliases` that are announced when applied, and
one canonical cast that makes every year the same table by construction rather
than by luck. The general lesson is worth more than the taxi data:
`set(columns) == set(columns)` is not "the schema is stable" — diff the types
too, and diff case-insensitively before you conclude anything is new.

**What to look at.** `configs/data.yaml` — read the comments as much as the
values; each number is there because something was observed, and the file says
what · `src/taxi_mlops/data/contract.py` docstring, which states the
structure-refuses/rows-get-counted split in four lines · the two-column
rejection table any `make ingest` prints · `tests/unit/test_data_clean.py::
test_every_named_rule_fires_exactly_once`, which builds one victim row per rule
so that no rule can be decorative · `docs/gotchas.md` #31.

**What to try yourself.** Truncate a raw file (`head -c 5000000 x.parquet`) and
run `make ingest` — watch it refuse at the *pin*, before it ever opens the
parquet, then confirm the existing output's sha256 didn't move. Then delete that
month's entry from `data/raw_manifest.json` and run again: now the same file
reaches the reader and refuses with a different typed error. Two failures, two
names, two places — that is what "typed refusal" buys. Finally, set
`on_unknown_column: warn` in `configs/data.yaml`, add a junk column to a frame
in the tests, and decide for yourself which policy you'd want at 3am.

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
