# Where the scale lives — F-048 and F-047 (M8-S1 leg 2)

*Written 2026-08-21 by EXEC/Opus 5, role block MLOps A. Every number here is
pasted from a command in `docs/version_provenance_m8_transcripts.md`.*

## 0. The two findings are one sentence apart

**F-048.** F-020's transfer divides by the row count a champion's count-scaled
knobs were CHOSEN at. That number lived in a tracked host JSON under
`automation/runs/m3s4/`. `.dockerignore` keeps those records out of the task image
— correctly; they are host evidence — so inside a scheduled pod the chain
resolved to nothing and the pod printed:

> `[retrain] F-020 (1)  : no sampled search behind this champion — no scale transfer to make`

which is honest about what the code could see and false about the world. The same
champion, the same minute, on the host: factor **6.6667**, `min_data_in_leaf`
1293 → **8620**, round cap **2400**.

**F-047.** `make image-smoke` had been RED since M5-S5 with twelve in-image
failures, all `FileNotFoundError` on those same records. Nobody saw it because
`image-smoke` is on no gate's path.

Both are the same shape from opposite ends: **evidence that belongs to the host,
consulted by something that is not the host.** F-048 moves the fact to where it
belongs; F-047 states which tests are about the host and stops asking a pod to run
them.

## 1. What landed (F-048)

**(c) The two absences now produce different outcomes.** `_search_scale` used to
answer "no tracked refit record names this run" whether the directory held no
match or did not exist. Those are different facts — the first is about the
CHAMPION, the second about the PROCESS — and inside a pod it is the second every
time. The missing directory is now a `RetrainError` that names the cause and the
fix. Watched, on the same call with two directory states:

| directory | outcome |
|---|---|
| present, names no refit for this run | returns `(None, None, None, None)`, notes an explicit no-op |
| absent | **raises**, naming `.dockerignore`, F-048 and `make backfill-provenance` |

**(a) The scale travels ON the version.** Three tags — `search_scale_rows`,
`search_scale_round_cap`, `search_scale_source` — written by
`registry.record_search_scale`, the additive path inside the one module allowed to
touch the registry. It creates no version, deletes nothing, and **never reads or
moves an alias**: a backfill that could move `@champion` would be a rollback
wearing a provenance script's clothes. Re-running with the same numbers is a
no-op; re-running with different numbers is **refused** rather than overwriting a
claim about a fit that has already happened.

`NO_SEARCH` is a VALUE and not an absent tag, and that is the whole finding in one
design decision: *"this champion had no sampled search"* and *"nobody recorded what
this champion had behind it"* must be different answers. `read_search_scale`
returns `None` for the third case — never recorded — so the resolver can tell all
three apart.

Who writes it, and when:

* `scripts/automl_refit.py` writes it on the RUN at fit time — the one place that
  knows the divisor while the run is being created.
* `run._promote` copies it onto the VERSION, **derived from the run being
  promoted, never typed**. A run without it was fitted from a config a human wrote
  at the scale it ran at, and the version records that honest no-op explicitly.
* `make backfill-provenance` does the versions that predate the tags.

**The resolver prefers the version and falls back to the host chain**, so the pod
path needs no host JSON at all and versions minted before this story keep working
on the host.

## 2. What the backfill did, and what it did not

```
[backfill] nyc-taxi-eta: 2 version(s)
[backfill] version 1 (run 3adee05a855a…): no sampled search
[backfill] version 2 (run 92b73bd4f77d…): 6,598,113 rows, cap 800
[backfill] 2 version(s) changed; no alias was read or moved, no version was
           created, nothing was deleted
```

Every number derived: a version's run id is matched against `refit-*.json`, that
record names its study, and the study's `sniper-*.json` carries `train_rows` and
`max_rounds`. A constant in that script would be the same defect one layer along —
a number that was true where it was written and applied where it is not.

Version **1** is the interesting row. It is the hand-configured LightGBM v1 from
`make train`, and it really did come from no sampled search — so it now records
that as a fact rather than leaving a future reader to infer it from a missing
file. Re-running the backfill: `0 version(s) changed`.

`@champion` was version **2** before and after and was never read by the backfill.

## 3. The host, resolving from the registry

```
[retrain] champion   : version 2 (auto-lgbm-v2, run 92b73bd4f77d…), feature set v2
[retrain] F-020 (1)  : count-scaled knobs chosen on 6,598,113 rows, fitting on
                       43,987,422 -> factor 6.6667 (registry: nyc-taxi-eta version 2
                       tag search_scale_rows (recorded from
                       automation/runs/m3s4/sniper-v2.json …))
[retrain]              min_data_in_leaf: 1293 -> 8620 — 1 row in 5,103 where it was
                       chosen; unchanged here it would be 1 in 34,020 (F-020);
                       rescaled it is 1 in 5,103
[retrain] F-020 (2)  : rounds 500 configured / 800 inherited -> 2400
```

The same numbers M7-S4 measured, from a different authority. That is the point:
nothing about the transfer changed, only where the divisor comes from.

## 4. The on-cluster proof

`scripts/retrain_proof_record.py` is a READER: it asks the control plane for the
most recent firings of `retrain-schedule-proof` and takes the record the POD
returned as its output. Its first run captured the BEFORE state — seven
consecutive firings on the old task version, every one of them `rescale_factor:
null, round_cap: 500` — which is F-048 alive, measured by the same instrument that
reports the after.

The after, run **`rdc1f3841bd6455e6`**, fired 2026-08-21T06:31:54Z on task version
`cfe8dc01a11527facc8cbc329e1df85a`:

```
[proof] rescale_factor: 6.666666969783633
[proof] round_cap     : 2400
[proof] decision      : PLAN_ONLY  promoted=False
[proof] ok   the pod resolved F-020's scale transfer: expected 6.6667, observed 6.6667
[proof] ok   the pod re-derived the round budget: expected 2400, observed 2400
[proof] ok   the proof trigger plans only and promotes nothing
```

**A pod finally resolved the same transfer the host does** — F-048's own closing
condition, and the record holds both sides so the contrast is checkable rather
than asserted.

One incidental fact worth keeping: the firing at 06:11:54Z ran the OLD task
version although the redeploy had already returned. A trigger fires the version
registered when it fires; a redeploy takes effect at the next tick. "I deployed
it, so the next run is the new code" was false for exactly one run here.

## 5. What landed (F-047)

Twenty-one tests carry `@pytest.mark.needs_records`, and the set was **measured,
not guessed**: the union of the tests that fail with `automation/runs/` hidden on
the host and the tests that fail inside the image at `taxi-mlops-pipeline:72a4013`.
The marker is deselected in exactly one place — the in-image run — and
`tests/unit/test_record_marker.py` holds that line:

* every test that reads a record carries it (or the older `skipif` form, §6);
* `pyproject`'s `addopts` may not deselect it, which would hide these tests from
  every host run and from CI — that is how a marker becomes the skip flag M1
  refused;
* no other `scripts/*.sh` may deselect it;
* nothing is marked that does not need it.

The coverage check is an AST walk, not a grep: several tests legitimately MENTION a
record path while asserting it appears in a script's body. It caught its own
author's new test on its first run.

## 6. Three things this story found by running it

**The marker guard's first draft missed a path spelled as separate segments.**
`REPO / "automation" / "runs" / "m6-gameday"` is the same path as
`REPO / "automation/runs/…"` and invisible to a substring match — gotcha #46's
family, and it hid four real tests. The receiver's source is normalised now.

**`test_detach_exit_codes` has been RED in-image since the day it landed**, for a
different reason: the image ships no `make`. F-047's shape a second time, found by
the same command and unseen for the same reason. It carries a `skipif` on the
binary's absence — the idiom this suite already uses for `ss`, `git` and `docker`.

**A `--plan-only` provenance check WRITES a tracked record**, so running it before
a build silently makes the next image tag `-dirty`. One rebuild was spent on that.

## 7. What is NOT claimed

* Nothing was promoted, no alias moved, no model was fitted. `@champion` is
  version 2 throughout, and the proof trigger plans only.
* The backfill's numbers are the tracked records' numbers. If a record is wrong,
  the tag is wrong — the tag makes the fact TRAVEL, it does not verify it.
* The static coverage check cannot see a literal record path handed to a function
  that reads it. `make image-smoke` is the empirical backstop and it is what
  caught the two the static check could not.
* **F-054 is open, not fixed**: twelve tests still guard their record reads with
  `skipif(not RECORD.exists())`, which on the HOST silently passes when a drill
  was never run. Rewriting tests belonging to M6's stories is not this leg's diff.
