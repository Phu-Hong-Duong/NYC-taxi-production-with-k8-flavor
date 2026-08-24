# The pre-publish audit — M9-S9 (2026-08-24)

The PO answered *yes, publish, after the pre-publish pair* (AWAITING_PO
2026-08-24-2, answer 3). M9-S8 was the README. This is the other half: what two
pinned scanners find in this repository, what was done about it, and — the part
that took the work — **the proof that they looked**.

The honest framing, carried from the epilogue's own charter: `.env` never entered
git by design, so this **verifies** hygiene rather than creates it. That makes the
expected answer "nothing", which is also exactly what a broken scanner says. So
every leg records its inputs, and `make security-scan-redteam` watches the secret
scanner catch a planted credential in two places.

---

## 1. What is pinned, and what the checksum actually proves

| Tool | Version | sha256 of the installed binary |
|---|---|---|
| trivy | **0.74.0** | `d89bcc6510a267f11b773398cbf1be5520ce39f9e8b6633178c4487f05b7d791` |
| gitleaks | **8.30.1** | `88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509` |

Both into `~/.local/bin`, sudo-free, the way kind, helm and uv arrived at M0-S1.
`make security-tools` pins the VERSION in the script rather than resolving
`latest` at install time — a scanner resolved from `latest` makes every scan
record un-reproducible for the most boring possible reason. `--check` reads the
versions back **off the binaries**, never off the constants, and a disagreement
is a failure (the `deploy_serving.sh` idiom).

**The checksum verification proves less than it looks like, and the record says
so in its own field.** The artifact and the publisher's `*_checksums.txt` come
from the same origin over the same TLS session: that detects a truncated or
corrupted download, and it is *not* a chain of trust, because anything able to
serve a tampered tarball can serve a matching checksum line. The durable pin is
the sha256 above, recorded in a tracked file — a future run of the same version
that gets different bytes is a loud mismatch against something under review.
Upstream also ships sigstore attestations; verifying them needs `cosign`, a third
pinned binary this $0 program is not adding to check two developer tools it runs
read-only against its own laptop. Recorded as a limit, not smuggled past.

Record: `automation/runs/m9-security/tools.json`.

---

## 2. The triage that matters, and it is not "zero findings"

A secret scanner pointed at this working tree **will** find `.env`: it holds the
real MinIO and Postgres credentials this platform runs on, and it is supposed to
be there. What makes that fine is a different fact — git has never seen it.

So a finding is classified by **where it lives**, and the answers are not degrees
of one another:

| class | what it means | verdict |
|---|---|---|
| **in git** | in a file git tracks, or in any commit on any ref — or untracked *and unignored*, which is one `git add -A` away | **story-stopping. Park at AWAITING_PO.** |
| **acknowledged** | in git, and carrying an argument this scan **re-derives from the bytes it found** | reported, not blocking |
| **local-only** | in a gitignored file on this disk, with `git check-ignore -v`'s answer beside it | expected, reported |

A scan that reported "0 findings" by pointing only at tracked files would be
technically true and would have proved nothing about the hazard anyone actually
has: a developer committing the `.env` they have been editing all week. That is
why the tree leg scans the **whole disk tree** and then classifies, rather than
scanning a safe subset and reporting a clean number.

### The one acknowledged finding

`scripts/gameday_m6.py:699` carries a 32-character high-entropy string that
`generic-api-key` matches. It is a **true positive by shape and a non-secret by
fact**: it is the M6-S5 gameday's deliberately WRONG MinIO credential, the value
patched in to make MinIO refuse the predictor with `403 HeadBucket: Forbidden` so
A-5 and A-7 could be watched firing. *A credential designed not to work is the
one string in this repo that must look exactly like a credential.*

It is **not** in a `.gitleaksignore`. A suppression nobody can read is how the
next real one hides behind it. It is acknowledged in `ACKNOWLEDGED_SECRETS`,
keyed on the sha256 of the found bytes, and the argument is **checkable rather
than asserted**: the scan base64-decodes the bytes it actually found and requires
them to spell `wrong-credential-gameday`. Swap a live credential onto that line
and the sha256 stops matching — it goes straight back to blocking.

It fails in **both directions** (`render_alert_rules.py`'s rule): an entry that
matches nothing in a run is a stale suppression and is itself a failure, because
otherwise a suppression outlives the thing it suppressed and quietly widens.
`tests/unit/test_security_scan.py` proves the table offline too — encoding the
claimed plaintext and hashing it must reproduce the key it is filed under, which
needs neither gitleaks nor the file still being there.

---

## 3. The verdict

Run 2026-08-24, `automation/runs/m9-security/scan.json`:

| leg | instrument | what it looked at | result |
|---|---|---|---|
| tree-secrets | `gitleaks dir` | the whole disk tree, gitignored files included | **0 blocking** · 1 acknowledged · 10 local-only (all `.env`) |
| history-secrets | `gitleaks git --log-opts='--all --full-history'` | every commit reachable from every ref | **0 blocking** · 1 acknowledged |
| images | `trivy image --scanners vuln` | the three images this program builds | recorded below |
| tree-vulns | `trivy fs --scanners vuln,misconfig` | `uv.lock` + the Dockerfiles and manifests | recorded below |

The exact file, commit and ref counts for the run are in the record's own
`inputs` block rather than quoted here: they move with every commit — including
the commit that would correct them — so a number in this document could never be
right for longer than it took to write. The record is the authority; the counts a
reader can hold still are the findings.

**`publishable: true`** — and the record says in its own words what that is
silent about: *no unacknowledged secret in any file git tracks and none in any
commit reachable from any ref. It says nothing about CVEs.*

`--all` is load-bearing: it walks every ref this clone holds, not just HEAD's
ancestry. A secret removed from `main` by a later commit still lives in the
objects the old commit points at, and that is what publishing exposes.

---

## 4. CVEs: recorded, not chased

| image | total | CRITICAL | HIGH | with a fix (C+H) |
|---|---|---|---|---|
| `taxi-mlops-pipeline:4e5dd66` | 201 | 3 | 53 | 39 |
| `taxi-mlops-feast-server:feast-0.66.0-a524771` | 196 | 3 | 50 | 36 |
| `taxi-mlops-predictor:mlserver-1.7.1-lgb-4.7.0` | 879 | 8 | 148 | 147 |

Repo tree: **5 dependency CVEs** (0 CRITICAL, 3 HIGH) and **76 failed
misconfiguration checks** (0 CRITICAL, 17 HIGH, 18 MEDIUM, 41 LOW).

Every image here is pinned by digest and this is a $0 program on one laptop; an
upgrade campaign is out of scope, and saying so **with the counts beside it** is
the honest close — the same shape as `nvidia-nccl-cu13` (241 MB of a hard
dependency that is never loaded): noted, not fought. The predictor's 879 is not
a surprise and not ours to fix: its base is `seldonio/mlserver:1.7.1-mlflow`, a
Python 3.10 conda image, and M5-S2 already recorded why it cannot be moved.

### The distinction that turns a number into a decision

The record splits **CVEs in packages our own lockfile pins** (trivy's
`Class: lang-pkgs`, taken from the report rather than from a list of package
names) from the ones inside a base image somebody else built. An OS package in
`python:3.12.14-slim-trixie` is Debian's to fix and ours to pin. A Python
package in `uv.lock` is a line we wrote.

There is exactly one such cluster, and it has a fix:

```
OURS  HIGH CVE-2026-54284  sqlparse 0.5.5 -> 0.6.0
OURS  HIGH CVE-2026-59893  sqlparse 0.5.5 -> 0.6.0
OURS  HIGH CVE-2026-71491  sqlparse 0.5.5 -> 0.6.0
```

`sqlparse` is transitive, required by **dbt-core 1.12.2** and **mlflow-skinny
3.15.1**; the predictor image carries 0.5.3 through mlserver's own graph. It is a
SQL *parser*, and **nothing in this program parses SQL from an untrusted party** —
every SQL string here is written by this repository. That bounds the exposure; it
does not make the version current.

**It is not bumped here, and the reason is a hard invariant rather than laziness:**
`uv.lock` is asserted **byte-identical to the `m7-closed` tag** by `verify-m8` §1
and by every M8/M9 story's exit state. Changing it turns a green gate red by
design. That makes it a PO decision, and it is written into the exit entry rather
than done quietly. See AWAITING_PO 2026-08-24-5.

### The 76 misconfigurations, named rather than totalled

They are pod-security-standard checks (`KSV-*`) on the seven plain manifests this
repo hand-writes — no `securityContext`, no `runAsNonRoot`, no
`readOnlyRootFilesystem`, no resource limits on some containers — plus `DS-0026`
(no `HEALTHCHECK`) on all three Dockerfiles and `DS-0002` (runs as root) on the
predictor's. Concentrated in `metabase.yaml` (14), `feast-server.yaml` (13),
`flyte-data-stager.yaml` (13), `postgres.yaml` (13), `redis.yaml` (12).

They are real and they are a hardening pass, not a leak. The cluster is a
single-node-family kind cluster on one laptop with no untrusted workload on it
and no route in except the one ingress this program declares. Recorded so that
whoever wants the hardening pass can start from the list instead of the idea.

---

## 5. Proving it looked: `make security-scan-redteam`

**PASSED — 16 checks, 0 failures.** The planted value is an AWS-shaped access-key
pair **generated at run time**; it appears nowhere in the script, because a drill
carrying a credential-shaped literal becomes a finding in the scan it exists to
test. (Not hypothetical — see §6.)

- **Arm A — untracked, unignored file in the working tree.** The scan names it
  **BLOCKING**, gives the reason `untracked AND NOT ignored`, exits non-zero, and
  does not print the planted secret.
- **Arm B — a real commit on a scratch branch `HEAD` does not point at.** The
  drill first asserts the commit is *not* reachable from the story branch, so
  what is under test is `--log-opts=--all` and not HEAD's ancestry. The scan names
  the file, names the commit, still acknowledges the gameday value (one plant, no
  collateral), and does not print the secret.
- **Destruction is part of the drill, not its epilogue.** Branch deleted, reflog
  expired, `git gc --prune=now`, then `git cat-file -e` is asked whether the
  object is gone — *"I deleted the branch"* and *"the object is gone"* are
  different claims and only the second is what publishing cares about. The
  untampered scan then comes back GREEN with 0 blocking, the tracked record is
  sha256-unchanged (both arms run `--no-write`, pinned by a test), and
  `git status` is clean.

**The drill found a real gap on its first run.** Arm B failed the check *"names
the planted commit"* — a blocking history finding printed rule, file and line and
**no commit**. The remedy for a secret in history is per-commit (rewrite, rotate),
and *"somewhere in the history"* is not where. Fixed by printing the commit,
author and date on the blocking line; the check passes on the artifact rather
than on a looser bar.

### And then the drill itself was flaky, in the worst possible direction

Roughly two runs in five reported **all six detection checks failing** — that is,
*the scanner found nothing* — while the scan was working perfectly. Both causes
were about the plant, not the scan, and both are worth knowing before writing any
detector drill:

- **`generic-api-key` matches `[\w.=-]`, which excludes `+` and `/`.** The plant
  was drawn from a base64 alphabet, so a `+` early in the string truncated the
  match below the rule's minimum length. Alphanumeric now.
- **Both rules carry an entropy floor**, and a short random string clears it only
  on average — a 20-character AWS-shaped id came out anywhere between 3.15 and
  4.22 bits. The generator now redraws until it is above the floor, measures
  entropy over the **whole matched string** (prefix included, because that is what
  the scanner sees), and prints what it settled on.

The generalisable line: **a randomly generated plant has to be drawn against the
properties the detector keys on, or the drill is flaky exactly where flakiness
reads as good news.** A red team that intermittently says PASS is worse than one
that always fails, because nobody investigates a pass. Four consecutive runs
green afterwards, one of them at the floor (3.646).

---

## 6. The defect the scan found in its own record

The first full run wrote each finding's identity as a 64-hex sha256 under a field
called `secret_sha256`. The **next** run flagged that tracked record **thirteen
times**: `generic-api-key` fires on a long high-entropy value under a
credential-shaped key, and both halves were present. The scanner was right, and
had the record been committed the audit would have blocked on its own output.

The fix was the artifact, not the rule: the record carries a **12-character**
`finding_id` (48 bits, ample to identify a finding in a repo this size), and the
full digest lives in code, where it sits as a dict key rather than as a value
after a credential-shaped name. `_`-prefixed working fields are stripped at the
**write boundary** rather than per call site, so a leg added later cannot leak
one. Two tests pin the property — one on the record, one on the scanner itself.

A second, quieter version of the same recursion: the tree scan read its **own
previous raw report**, which carries the values verbatim, so the finding count
became a function of how many times the scan had been run — a measurement that
moves because it was taken. Those findings are now dropped, **counted and named**
in the output, and the drop is *bounded*: a file under the raw directory is
gitignored, so it can only ever be local-only, and the code **exits** rather than
dropping anything that was heading for `blocking`.

---

## 7. What this does not cover

- **The public flip itself** is the PO's click and is out of scope by the
  epilogue's own terms.
- **`.env` is not audited for content.** It is confirmed gitignored and confirmed
  never to have been in history; whether the credentials in it are strong, and
  whether they should be rotated before a public repo makes the platform's
  *shape* public, is a PO question and is in the exit entry.
- **No commit hook.** The M1 prior-art ADOPT was commit-time secret scanning;
  what landed is an audit, run on demand. A pre-commit hook lives in a developer's
  local `.git/hooks`, which is not tracked, and cannot be verified by any gate
  here — so it would be a claim this repo could not check. `make security-scan`
  can be run before any push and its verdict is a tracked file.
- **CVEs are recorded, not chased**, and §4 says exactly which subset is
  actionable and which invariant stops it landing here.
- **The scanners' own supply chain** is verified only to the strength §1 states.

---

## 8. Commands

| Intent | Command |
|---|---|
| Pin the scanners, record their sha256s | `make security-tools` (`DRY_RUN=1` installs nothing, `FORCE=1` re-downloads) |
| Read the installed versions back | `make security-tools-check` |
| The full audit, writing the record | `make security-scan` |
| One leg, seconds (the cheap probe) | `make security-scan SCAN_ARGS="--stage tree-secrets"` |
| Print the verdicts, record nothing | `make security-scan SCAN_ARGS=--no-write` |
| Prove the secret scan can find one | `make security-scan-redteam` |
