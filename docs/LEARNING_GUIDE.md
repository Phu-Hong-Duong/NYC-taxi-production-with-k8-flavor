# LEARNING_GUIDE — field notes, one per story (inherited law from the predecessor)

Law: every story closes with its note BEFORE the next story starts. Format per
note: what was built · why this way · the concept underneath · what to look at ·
what to try yourself. Newest milestone first. The reader is the principal six
months from now.

---

## M0

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
