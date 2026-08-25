# Credential rotation, in place (M9-S12)

**Every credential this platform holds is new, the platform never went down for
it, and no state was destroyed.** Twelve values across five families, rotated on
a live cluster; all ten inherited gates GREEN afterwards; the pre-rotation values
proved refused; the undo copy destroyed. Record:
`automation/runs/m9-publish/rotation.json` — which names *what* rotated and never
*to what*.

Sanction: **AWAITING_PO 2026-08-24-5, answer 2** — *"rotate the `.env`
credentials before publish — YES … an in-place secret rotation is preferred over
a rebuild of the stateful cluster if one is available, since a full restore over
a dead platform is still un-rehearsed."*

---

## 1. Why in place, and what the cheap path would have cost

`make destroy` + redeploy rotates every credential in one command. It also takes
every PVC with it: the MLflow registry (two versions and the `@champion` alias),
the one Postgres holding five tenants, the MinIO objects, the Feast online store's
57,688 keys. `make restore-drill` rehearses a restore into **scratch** databases
and no further (M6-S5); **a full restore over a dead platform has never been
performed**, and every artifact in this repo says so.

So the one-command path spends state whose recovery is unproven, to save an
afternoon. The PO said as much before being asked. This story is the other path.

## 2. Twelve of twenty-seven keys are secrets

`.env` holds 27 keys. Fifteen of them are **identities**, endpoints or settings —
`AWS_ACCESS_KEY_ID=mlflow` is a *username*, `MLFLOW_ARTIFACT_BUCKET` names a
bucket every artifact lives in, and each `*_DB_USER` is a Postgres role that
**owns a database**. Rotating one of those is not a rotation, it is a rename, and
it orphans whatever points at the old name.

So `scripts/rotate_credentials.py` **classifies every key**, and the design
decision worth reading twice is this one:

> **A key this script does not recognise is a FAILURE, never a skip.**

A rotation that silently passes over a credential added after it was written is
*worse* than no rotation: it reports success, the operator believes every secret
is new, and one old value lives on with nothing saying so. Both directions refuse
— an unknown key in `.env`, and an expected key `.env` lacks. `make rotate-plan`
prints the whole inventory and touches nothing.

Two tests keep the inventory honest without a cluster: every key in the tracked
`.env.example` must land in exactly one bucket, and every key in
`platform_secrets.sh`'s `REQUIRED` list must be classified — those are the keys
the deploy recipe refuses to start without, so each one is live somewhere.

## 3. The five families and their in-place mechanisms

| Family | Keys | Mechanism | Why that one |
|---|---|---|---|
| `postgres` | 6 | `ALTER ROLE … PASSWORD` | The five tenants go through **`scripts/postgres_databases.sh`**, which has ALTER'd them to `.env` on every run since M1-S4. The **superuser** is done here, because that script describes *tenant databases* and `postgres` owns none. Both reach `psql` over `kubectl exec` — no port is published — with the password on **stdin as a `\set` variable**, never argv. |
| `minio-users` | 3 | `mc admin user add` | On an existing accessKey this re-issues the secret in place; objects and policy untouched. |
| `minio-root` | 1 | Secret + restart | Root is env-borne. The PVC keeps every object, so this is in-place in the sense the letter asked for. |
| `grafana` | 1 | Secret + restart | Persistence is **OFF** by M6-S1's decision, so the admin is re-created from the Secret at every boot. On a *persistent* Grafana this same two-step would silently do nothing. |
| `metabase-admin` | 1 | `PUT /api/user/:id/password` | The admin password lives in the app-db — a real database in the one Postgres — so it survives every restart and **no Secret carries it**. The only family whose service change must come *first*, because the API requires the current password. |

Order per family: **backing service → `.env` + Secret → consumers**. Between the
first and third steps the platform holds a credential its clients have not been
told about. That window is real, the charter accepts it on a laptop, and the
script records it rather than implying it does not exist. What is *not* accepted
is ending with any pair disagreeing — which is what §6's accept is for.

Postgres is the one family where `.env` is written *before* the service changes,
deliberately: a second ALTER path living in this script would be
`postgres_databases.sh`'s twin, and this repo deletes twins.

**The record checkpoints after every family**, so a run that dies mid-way still
says which families completed. That was demonstrated by accident on this story's
first attempt, which failed in `minio-root` and left a record reading
`families_completed: ["minio-users", "postgres"]`, `finished_at: null`.

## 4. Nothing is echoed

No value is printed, put in argv, or written to the record — old or new. Three
AST tests hold it: no `print()` may interpolate a subscript of `env`/`new`, no
`kubectl`/`_mc`/`_psql`/`run_script` call may take one positionally (`stdin=` is
a keyword and is allowed), and no `record[...]` assignment may carry one. A
fourth reads the committed record and fails on any 32-hex-or-longer token, which
is the shape both generators emit — so "no values" is checkable and not a promise.

## 5. What running it found

### 5.1 The undo copy was wrong twice, and both guards caught it (F-075)

The charter says to copy `.env` aside to *"a gitignored path
(`.env.pre-rotation`)"* before the first change, because losing `.env`
mid-rotation orphans every volume. Two things about that sentence were false.

`git check-ignore -v .env.pre-rotation` exited **1**. `.gitignore` line 1 is the
literal `.env`, and gitignore patterns are **names, not prefixes** — so the path
the charter called gitignored was one `git add -A` away from committing every old
credential in the program. Fixed before the copy was made (`.env.*` with
`!.env.example`, verified both directions).

Then `make verify-m2`'s root-stray leg named the file anyway, and **it was
right**. A gitignored file is invisible to git and to nothing else: it is still in
a directory listing, still in a `tar`, still in an archive of the repo. The copy
now lives at `~/.nyc-taxi-rotation/env.pre-rotation`, **outside the repository**,
dir 700 / file 600. The `.gitignore` entry stays as defence in depth.

Both corrections came from two-second commands, and neither would have been
prompted by reading the charter carefully.

### 5.2 Two rollout races, and a false alarm shaped exactly like a catastrophe (F-076)

The `minio-root` rotator restarts MinIO and then lists the named users, because
some MinIO builds encrypt the IAM data with the root credential and expect
`MINIO_ROOT_USER_OLD`/`_PASSWORD_OLD` on the rotating restart. If this were one of
those, `mlflow`, `flyte` and `serving` would be gone. The binary's `--help`
documents no root env var at all, so the check had to be empirical.

It came back **`authentication failed`** — the catastrophe's exact signature. It
was not the catastrophe.

- **`kubectl exec deploy/minio` does not address the Deployment.** It resolves the
  Deployment's *selector* and picks a matching pod. MinIO here is RollingUpdate
  with `maxSurge=100%, maxUnavailable=0`, so a restart puts **two** pods behind
  that selector, and the exec landed on the one being replaced — which still held
  the old root password.
- **`rollout restart` + `rollout status` is itself a race.** `rollout status` asks
  about the Deployment's *current* status, which until the controller observes the
  new generation still describes the **previous** — complete — rollout. So the
  pair reports "successfully rolled out" about a restart that has not started.
  Same root cause as F-036/gotcha #79, arriving from the other side: there
  `observedGeneration` trailing `generation` made kubectl *refuse* conditions that
  were true; here it makes kubectl *affirm* a rollout that has not begun.

Fixed by resolving exactly one Ready, non-terminating pod, and by waiting for
`observedGeneration >= generation` before `rollout status`. Then **measured**: the
first successful read is now **0.3 s past Ready**, which says the generation race
was the cause and MinIO's admin API was never slow. The bounded retry added at the
same time stays as defence in depth, and the record carries the 0.3 s so a number
that grows over releases would be visible.

**A false alarm indistinguishable from a real disaster is worse than no alarm**,
because the next operator's instinct is to roll the credential back — which here
would have been a rollback of a rotation that worked.

Outcome: **all three named users survived, with their policy attachments
unchanged** — `flyte[readwrite]`, `mlflow[readwrite]`,
`serving[readonly,serving-readonly]`. That last one is why the check reads the
policy *back* rather than assuming: `serving` carries **two** policies, and a
re-issue that quietly reset it to a default would hand the most-exposed identity
in the program more access than it had — a change nothing else would notice,
because every read it performs would still succeed.

### 5.3 The negative probe ran over a path that authenticates nothing (F-077)

`--verify-old-refused` runs **after** the positive sweep, on purpose: an absence
check run first passes against a platform that is simply down (gotcha #105 /
F-060). It reported the pre-rotation Postgres password **accepted**.

`pg_hba.conf` here reads:

```
host all all 127.0.0.1/32   trust
host all all all            scram-sha-256
```

The probe connected to `127.0.0.1` **from inside the postgres pod**, which is
`trust` — the password is not consulted at all. The rotation was fine; the probe
was measuring nothing.

**The positive control could not catch it, and that is worth more than the fix.**
A control only discriminates if the mechanism under test is engaged. Under `trust`
*both* arms pass, so the control agreed with the false alarm instead of exposing
it — it had been built to catch "the database is gone", which is a different
failure from "nothing is being authenticated".

The probe now connects to the pod's **own IP**, read from the cluster rather than
typed, which leaves 127.0.0.1 behind and falls through to the `scram-sha-256`
rule. Over that path: old password **refused** (`password authentication failed`),
new password accepted.

### 5.4 A consumer the charter did not enumerate (F-078)

Metabase stores the **warehouse connection** — host, database, user *and
password* — as a row in its app-db, not as an environment variable. So restarting
the pod converges its own app-db credential and leaves the `marts` one stale, and
every card then fails with a connection-pool error that names no credential at
all. `metabase_boards.py`'s `ensure_marts_database()` already PUTs the details
from `.env` on every run, so **`make boards` is the mechanism and it was already
built** — it is now in `CONSUMERS`, drained after `metabase-admin` because it logs
in with the admin password.

This is exactly the charter's own risk 4 ("rotation breaks a consumer this charter
did not enumerate; the accept is all ten gates, which is the net"), and the net
worked: `verify-m1` renders the boards.

The rotation was then **re-run end to end so the committed record was produced by
the committed recipe** rather than by a hand-run repair — the F-063 precedent.

### 5.5 An ambient variable had quietly converted two tests (F-079)

`tests/unit/test_watchdog.py` built its sandbox environment from `os.environ`, and
this session was started by `watchdog.sh`'s heal path, which exports
`WATCHDOG_HEAL=1` — a flag a session then carries for life. Two tests asserting
the ordinary, human-run behaviour of `next_session.sh` had silently become tests
of the heal path, and went red on a repo where nothing was wrong. The sandbox pins
the flag to `"0"`; the tests that *want* the heal path already set it explicitly,
so both intentions are now visible instead of one being at the mercy of whoever
launched the suite. Unrelated to the rotation; found by running the suite.

## 6. The accept

Positive first, then negative — never the other way round.

| Check | Result |
|---|---|
| `make verify-m0` … `verify-m9` | **all ten GREEN**, one sweep, exit 0 |
| `make parity` | **0.000e+00** over 16 hazard rows (bar 1e-6) — the MLflow client and the wire |
| `make rotate-verify-old` | **PASSED, 4 checks** — MinIO root refused, MinIO user `serving` refused, Postgres `mlflow` refused with a password authentication failure, and the current password accepted over the same path as the control |
| `make security-scan` | `publishable: true`, **`secrets_in_git: 0`** |
| `make readme-check` | GREEN |
| host suite | **1,297 passed**, no skips |
| `uv.lock` | byte-identical to `lock-rebaselined-m9-publish` (asserted inside `verify-m8` §1) |
| `@champion` | version **2** / `feature_set v2`, versions `['1','2']` — nothing fitted, no alias moved, no version created |

The ten gates are the strongest available claim precisely because they are not
about credentials: every platform consumer is read *live* through them, so a
credential this charter forgot shows up as a red gate rather than as a surprise
next month.

One detail worth recording rather than smoothing over: `security-scan`'s
`secrets_local_only` moved **10 → 9**. Nothing changed about `.env`'s handling —
one rotated random value fell under `generic-api-key`'s entropy floor. That is
**F-071's mechanism observed naturally**: a randomly generated secret's entropy
varies per draw, which is why the red team's plant is drawn against the detector's
properties rather than hoped at.

## 7. The one measured wire change

`make serve` re-deployed the champion so the storage-initializer fetches the
model under the **new** `SERVING_S3_SECRET_KEY` — the charter's requirement that
the serving credential be *exercised, not assumed*, and the only place the
rotation is proved against a real object download rather than a login. The
champion answered on its own host afterwards, and `@champion` was read before and
after (a move exits 2).

## 8. The undo copy is destroyed

`make rotate-destroy-undo` overwrote and unlinked it, and recorded the fact. It is
the last step by design: while the rotation is in flight the copy is the only
undo, and once the gates are green and the old values are proved refused it has
stopped being an undo and is only a file holding every superseded credential of a
platform about to be published.

The record states the limit rather than implying a shred it cannot perform: on a
copy-on-write or journalling filesystem, overwrite-then-unlink does not guarantee
the bytes are unrecoverable — only that no path reads them.

## 9. What this does NOT claim

- **Not that the old credentials never leaked.** They were never in git (M9-S9
  verified that over every commit on every ref), and they are now refused. Nothing
  here is a statement about the machine's own history.
- **Not that a full restore is rehearsed.** It still is not, and that is the whole
  reason this story exists in this shape.
- **Not that the platform stayed strictly available.** Six workloads restarted and
  MinIO, MLflow, Metabase, Grafana and Flyte each had a brief window. This is a
  laptop; the charter accepted it; nothing measured it, and nothing here pretends
  otherwise.
- **Not that the three container images changed.** They carry no credential — the
  credentials arrive as Secrets and environment — so none needed rebuilding.
