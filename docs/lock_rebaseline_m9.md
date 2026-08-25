# The first pinned dependency this program ever changed (M9-S11)

*Landed 2026-08-25. PO letter: `AWAITING_PO.md` 2026-08-24-5, answered block,
option (b). Charter: `docs/milestones/M9_PUBLISH_KICKOFF.md` § M9-S11.*

---

## 0. What the letter asked, and what it actually cost

The pre-publish audit (M9-S9) found **`sqlparse 0.5.5` carrying three HIGH CVEs
with a fix available in 0.6.0**, arriving transitively through `dbt-core` and
`mlflow-skinny`. It did not bump it, because `uv.lock` is asserted **byte-identical
to a tag** by `verify-m8` §1 and by every M8/M9 story's exit state — so changing it
turns a green gate red by design. That made it the PO's.

The PO chose **(b)**: bump before the flip, re-baseline the lock invariant, prove
nothing moved. The kickoff priced it as *"one `uv lock --upgrade-package
sqlparse`"*, then the honest cost of re-pointing four readers and re-running five
proofs.

**The one-liner does not work, and it does not say so.** That is F-074 and it is
the most transferable thing in this story:

```
$ uv lock --upgrade-package sqlparse
Resolved 243 packages in 1.87s

$ git diff --stat uv.lock
(nothing)
```

`dbt-core 1.12.2` declares `sqlparse<0.6.0,>=0.5.5`. `--upgrade-package` honours
that upper bound, correctly, and reports a successful resolution — because *it was*
a successful resolution. Nothing failed. Read as "already up to date", this story
would have re-baselined the anchor, re-run every proof, and closed the CVE fork
with **sqlparse 0.5.5 still pinned**: ten gates green, the letter unhonoured, and a
commit message claiming otherwise.

> **A resolver asked to upgrade one package answers with a lock, not with a
> verdict. The check is the DIFF, and an empty diff is a finding, not a no-op.**

## 1. The two paths out, and why the tempting one is worse

`sqlparse 0.6.0` is the latest release. `dbt-core 1.12.3` — a patch release —
relaxes the bound to `sqlparse<0.7.0,>=0.5.5`. So:

| | What it does | Why not / why |
|---|---|---|
| **(i) bump dbt-core 1.12.2 → 1.12.3 as well** | Takes upstream's own fix. Two packages move. | **CHOSEN.** A patch release whose relevant change *is* the bound relaxation, and the consumer is directly falsifiable by a proof the charter already required (`make marts`). |
| (ii) `[tool.uv] override-dependencies = ["sqlparse==0.6.0"]` | Forces 0.6.0 past dbt's declared bound. One version number moves *on paper*. | The charter's named fallback, and it is the trap. It ships a dbt running against a version its own metadata forbids — an untested combination — bought purely to keep the diff looking like the one that was priced. |
| (iii) don't bump; report the block | Free. | Leaves three HIGH CVEs on the front page of a repo about to go public, after the PO said bump. |

(ii) is the one worth naming out loud, because it is the path that makes the
*record* match the *estimate*. It does that by moving the risk somewhere nobody
measures. The extra mover in (i) is a fact about the world; hiding it would not
have made it smaller.

## 2. gotcha #36 as a measurement, not a hope

The bump's whole risk is a resolver quietly walking the pinned numeric stack —
this repo's record of that is an unbounded `uv add mlflow` silently resolving two
majors behind the server. So the diff was measured structurally, not skimmed:

```
packages before=243 after=243
MOVED:   {'dbt-core': ('1.12.2', '1.12.3'), 'sqlparse': ('0.5.5', '0.6.0')}
ADDED:   []
REMOVED: []

pandas        3.0.5  -> 3.0.5    UNCHANGED
numpy         2.5.2  -> 2.5.2    UNCHANGED
scikit-learn  1.9.0  -> 1.9.0    UNCHANGED
mlflow-skinny 3.15.1 -> 3.15.1   UNCHANGED
lightgbm      4.7.0  -> 4.7.0    UNCHANGED
dbt-duckdb    1.11.0 -> 1.11.0   UNCHANGED
xgboost       3.4.1  -> 3.4.1    UNCHANGED
flaml         2.6.0  -> 2.6.0    UNCHANGED
optuna        4.9.0  -> 4.9.0    UNCHANGED
pyarrow       25.0.1 -> 25.0.1   UNCHANGED
duckdb        1.5.5  -> 1.5.5    UNCHANGED
scipy         1.18.0 -> 1.18.0   UNCHANGED
flyte         2.6.1  -> 2.6.1    UNCHANGED
```

Read back off the environment rather than off the lock
(`uv pip list`): `dbt-core 1.12.3`, `sqlparse 0.6.0`, and dbt's own metadata now
reads `['sqlparse<0.7.0,>=0.5.5']`.

That measurement is now a **standing assertion**, not a one-off: two tests in
`tests/unit/test_lock_anchor.py` pin both bumped versions and the ten unmoved
cores against the artifact, so the next dependency change inherits the check.

## 3. The re-baseline — the invariant kept its shape, only its anchor moved

`uv.lock` must be byte-identical to a **sanctioned tag**. The invariant's whole
value is that an unsanctioned `uv add` is a RED gate; that is untouched. What moved
is the reference point, **once, by letter**, to a new annotated tag:

```
lock-rebaselined-m9-publish
```

Four sites re-pointed: `scripts/verify_m8.sh` and `scripts/verify_m9.sh` (which
each now spell the anchor **once**, as `LOCK_ANCHOR`), and the two red teams'
"this leg must stay green" needles.

### 3.1 The distinction a search-and-replace would have destroyed

`m7-closed` was doing **two unrelated jobs** in both gates, and only one of them
may move:

| Use | Direction of "moving it forward" |
|---|---|
| **the LOCK anchor** — `uv.lock` must equal this tag's blob | neutral: the gate still refuses an unsanctioned edit, against a newer baseline |
| **the REGISTRY bound** (§7) — no model version may have been created after this tag | **a loosening**: a tag placed today ADMITS every version created since M7 |

A `sed -i s/m7-closed/lock-rebaselined-m9-publish/` over the two gates would have
landed this story, passed every gate, and silently weakened the strongest form of
the alias law — in a diff full of one tag name being replaced by another, where a
reviewer has no way to see that half of them were a loosening.

So the registry bound stays at `m7-closed`, and
`test_the_registry_creation_bound_did_not_follow_the_anchor` asserts it — keyed on
the `git log --format=%ct -1 <tag>` **invocation** that computes the bound, not on
the word (gotcha #35/#99: both files argue about tags in prose).

## 4. Prove nothing moved

`sqlparse` is a SQL **parser**; its consumers here are dbt and the MLflow client.
Both were exercised against the real platform, not reasoned about.

| Proof | Result |
|---|---|
| `make marts` — **the load-bearing one**, dbt is sqlparse's consumer | `dbt build` **PASS=80 WARN=0 ERROR=0** in 6.56 s; publish reproduced **every** recorded count to the row: `trips_clean` **56,127,878** · `zone_hourly_stats` 44,792 · `monthly_kpis` 8 · `rejections_by_rule` 80 · `error_segments` 1,151 · `scoring_daily` 91, in 256.9 s |
| `make parity` — the MLflow client + the wire | **`max \|offline − online\| = 0.000e+00`** over 16 hazard rows against a 1e-6 bar; every row agrees exactly, `model_version` 2 |
| host suite | **1,277 passed**, no skips (1,269 + the 8 new) |
| ruff | clean |
| `make verify-m8` | **GREEN 51/51** — count unchanged, so the invariant kept its shape |
| `make verify-m9` | **GREEN** (46 sub-check lines — see §6) |
| `make verify-m8-redteam` · `make verify-m9-redteam` | both **PASSED**, sha256-identical restores, clean tree |
| `make readme-check` | **GREEN** |

## 5. The CVEs, and the quarantine's recorded absence

`make security-scan` re-run: **zero secrets in anything git holds**, verdict
unchanged, and the dependency leg moved where it was supposed to.

```
before (M9-S9):  repo tree: 5 dependency CVE(s) — CRITICAL 0 · HIGH 3
after  (M9-S11): repo tree: 1 dependency CVE(s) — CRITICAL 0 · HIGH 0
                 fixable_in_our_lockfile: []
```

The three HIGH sqlparse CVEs are gone and **nothing actionable remains in the
lockfile**. One MEDIUM finding survives with no fix available in our graph.

**The Feast quarantine is a recorded ABSENCE, not an edit.** `sqlparse` is not
among the 66 exact pins in `infra/feast/requirements-feast.txt` (checked at charter
time, exit 1; checked again here, and now pinned by
`test_the_quarantine_still_does_not_pin_sqlparse` so a pin arriving later inherits
the same CVE decision instead of slipping in on the other side of the wall).

### 5.1 Honest cost: the images were NOT rebuilt

The task image, the feast-server image and the predictor image still carry
**sqlparse 0.5.5** — and now also **dbt-core 1.12.2** — until their next natural
rebuild. This is stated rather than netted out:

- Nothing on-cluster parses SQL from an untrusted party. Every SQL string in this
  program is written by this repository.
- Rebuilding three images to close a CVE in a parser nothing points at untrusted
  input is cost without a threat model.
- The predictor's base is a py3.10 mlserver conda image that M5-S2 already recorded
  as unmovable for exactly these reasons.

**And the F-026 guard is already firing, correctly.** `uv.lock` is in both
`run_pipeline.sh`'s and `retrain_schedule.sh`'s `IMAGE_PATHS`, so any on-cluster
pipeline or trigger run refuses (exit 3) until `make image-load`. Measured
read-only against the recorded image `taxi-mlops-pipeline:4e5dd66`: the guard
already saw drift under `scripts/` and `src/` from M9-S9 and M9-S10, and `uv.lock`
now joins that list. **Nothing new is broken; one more file is on a list that was
already non-empty.**

## 6. What this story found in passing: `verify-m9` is 46, not 45

Running the gate returned **46 sub-check lines** where every record says 45. That
is the shape a story should never assert its way past, so it was measured:

- at **`main`** (this story's edits reverted, lock still bumped): **45 `ok` + 1
  `FAIL`** — the lock leg correctly red, because `m7-closed:uv.lock` no longer
  equals the tree. **46 lines.**
- at **HEAD**: **46 `ok`**, 0 FAIL. **46 lines.**
- and the diff of `scripts/verify_m9.sh` removes one `ok(`/`no(` pair and adds one
  — **count-neutral by construction**.

So the gate has emitted 46 since **M9-S7**, which added the F-019-across-both-
store-states leg and did not re-count the front door. `make verify-m9-redteam`
corroborates independently: its restore check reads *"the gate is GREEN again (46
sub-check line(s))"*.

Corrected in the README's **epilogue-close** row only, with the reason inline. The
**M9-close** row keeps its `45/45` — it was true when written, and a memo that
silently rewrites its own numbers cannot be compared against the decisions made
from them.

## 7. What did not happen

Nothing was fitted. No alias moved. No registry version was created
(`@champion` = version **2**, `feature_set v2`, versions `['1','2']`). No wire
changed — the champion's predictor and the transformer were not touched, deployed
or restarted. The only cluster mutation is `make marts`, which republished the six
marts to the counts they already held, as its own proof.
