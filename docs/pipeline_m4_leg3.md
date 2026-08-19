# M4-S5, third leg (2026-08-19) — the gate, and the evidence it turned out to be standing on

*Continuation of `docs/pipeline_m4.md` (§1–§16). Kept as a separate file only
because that one is 1,032 lines; the section numbering continues from it, and
§1–§16 stay UNEDITED as the earlier sessions' record.*

## 17. `make verify-m4`: 39 sub-checks in 7 sections, seconds, and it re-runs NOTHING

The M2/M3 gate-writing law, applied a third time, with one clause that is stronger
here than it was there. M3's rule was **re-fits nothing**. M4's is **re-runs
nothing**, and the difference is not pedantry: M4's evidence cost about 95 minutes
of on-cluster work (the 1,909.7 s full-data run, the cache drill's 1,974 s + 11 s
pair, the kill drill's 975.8 s, the marts run's 886.6 s) — and re-running any of
it would also **mint MLflow runs**, which is the quantity §4's strongest leg
counts. A gate that launched a pipeline would corrupt the evidence it exists to
read.

So it reads: the live control plane, the live cluster, the live registry, the live
warehouse, the image (from inside a container), the code (with `ast`), and the
records the drills wrote. Wall clock is seconds.

| § | What it asks | Sub-checks |
|---|---|---|
| 1 | the control plane answers `/healthz`; every `flyte` Deployment has an available replica; the task PodTemplate is APPLIED in-cluster and its container is named `default`; the PVC it mounts is Bound; MLflow, Postgres and MinIO each have a Running pod | 9 |
| 2 | the image manifest's tag is not `:latest` and its tree was clean; **all three nodes hold it**, read with each node's own `crictl`; **D-004 is still dead inside the container** — `openmp: system libgomp.so.1` on the first line, and no `[openmp]` announcement anywhere | 5 |
| 3 | every stage in `tasks.STAGES` is wrapped by a Flyte task (derived from `workflows.py` by AST); every action of every recorded run SUCCEEDED; at least one run executed ALL seven stages; every run has a `main` parent; **MLflow holds the runs those stages claim to have fitted, all FINISHED** | 6 |
| 4 | from the RECORDED cache drill: the stages that re-executed unconditionally are exactly those the code declares `cache="disable"`; every cacheable stage of run 2 read `CACHE_HIT`; run 1 populated them first; the clock agrees; MLflow's run count is unchanged across run 2; **and the two witnesses agree with each other** | 6 |
| 5 | the killed run finished, exit 0, all stages SUCCEEDED; **a different pod OBJECT** ran the target stage (uid, not name); the target genuinely executed (a `CACHE_HIT` stage runs in no pod); the killed action recorded ONE attempt, so recreation did not spend the budget; the budget the drill recorded is the one `workflows.py` declares; **a task that always raises settled at attempt index 3 and FAILED** | 6 |
| 6 | `publish_marts` is the LAST stage in `STAGES`; it SUCCEEDED on-cluster and was `CACHE_DISABLED`; **the published fact table reconciles with the analyst layer for all 8 months, 56,127,878 rows** — asked of Postgres and DuckDB separately, republishing nothing | 3 |
| 7 | `@champion` resolves; every recorded run left it where it is now; **not one of the 28 runs the M4 pipeline fitted is a registry version**; `tasks.train` takes no `promote` parameter | 4 |

**GREEN 39/39, exit 0.** Transcript: `docs/verify_m4_transcripts.md` §1.

### The two legs worth reading twice

**§7's third check.** M4 ran the pipeline repeatedly — six stages, then seven, on
sampled months and once on full data — and fitted **28 MLflow runs** in its own
experiment. The standing law was that no M4 run may move `@champion`. The weak
form of that check is "the alias is still 2", which any session can satisfy by not
looking. The strong form is the one the gate asks: **none of those 28 runs is a
registry version.** A promotion cannot hide from it, because a promotion has to
create a version, and a version carries the run that produced it. The law stops
being a habit and becomes something the registry can be asked about.

**§4's last check, which the red team exists for.** The control plane's
`cache_status` and MLflow's run count are two independent witnesses to one
question — did the fit run a second time? — and the gate now requires them to
AGREE, which is strictly stronger than either passing alone. A record claiming a
stage re-executed while the tracking server minted no run is a contradiction, and
one of the two is wrong.

### Where the literals were refused

Every number this gate compares is derived on **both** sides:

- the **stage set** comes from `tasks.STAGES`, and the **flyte-task -> callable**
  mapping is parsed out of `workflows.py` with `ast` (nothing declares it, and
  `ingest` wraps `ingest_month`). A stage added to the graph and never wrapped is
  therefore RED, not invisible;
- the **uncached set** is read from the `cache="disable"` decorator arguments, so
  a stage that quietly stops being cached turns §4 red instead of being
  accommodated by a list somebody edits;
- the **retry budget** is read from `_STAGE_RETRIES` and compared against what the
  drill recorded AND against what the probe's action reports — three places, one
  number;
- the **experiment name** is `tasks.DEFAULT_EXPERIMENT`, extracted this session;
- the **champion version** is never asserted, only required to equal what every
  record says it was;
- a test (`tests/unit/test_verify_m4.py`) fails if a Flyte run name, an MLflow run
  id or a tagged image reference ever appears in the script.

## 18. `make verify-m4-redteam`: the most plausible lie the record can tell

The kickoff asks for a POINTER-class fault: break what something SAYS, never what
it IS. M2 deleted an alias; M3 rewrote a measured number. M4's equivalent is **one
field of one action**: in `automation/runs/m4-cache/cache_drill.json`, run 2's
`train` stage moves from `CACHE_HIT` to `CACHE_POPULATED`. Nothing else changes —
its duration stays 140 ms, its phase stays SUCCEEDED, the MLflow counts stay
16 -> 16.

That is deliberately the most plausible lie available. Every field is individually
well-formed. The record still describes a green run of seven stages. A reader
skimming it sees nothing wrong. What it now claims is that a 32-minute fit
re-executed on the rerun — and the drill picks its target by reading the record
for whichever cached stage cost run 1 the most, so it keeps aiming at the
expensive one when the numbers change.

Observed 2026-08-19 — **two FAILs, 37 sub-checks still passing, byte-identical
restore, then GREEN 39/39** (full transcript: `docs/verify_m4_transcripts.md` §2):

```
  FAIL cacheable stage(s) did not hit on the rerun: {'train': 'CACHE_POPULATED'}
  FAIL the two witnesses CONTRADICT each other: the record says ['train'] re-executed
       on the rerun while MLflow minted 0 run(s) — a fit either logs or does not
       happen, so one of these records is wrong
```

The second FAIL is the whole point: a gate that read only `cache_status` would
have believed this file. Ranking three witnesses is what M4-S4's cache drill
argued for; this is the first time that argument has been falsifiable.

Safety is M3's shape: a byte copy taken before the edit, restored under an EXIT
trap, verified by sha256. The drill touches no pod, no image, no MLflow run, no
registry version and no warehouse row.

## 19. F-029 — two gates were replaying evidence that is not in the repo

Found while deciding what `verify-m4` was allowed to depend on, and checked with
`git check-ignore -v` before being written down: **`automation/runs/` is
gitignored wholesale, and `git ls-files automation/runs/` is empty.**

`verify-m3` replays `automation/runs/m3s5/bakeoff.json` and reads `m3s4/*.json`.
`verify-m4` reads five records under `automation/runs/m4-*/`. None of them is in
the repository. Three consequences, in increasing order of interest:

1. a fresh clone runs those legs RED for a reason that is not a defect;
2. the records are machine state, so **an edit to one — precisely the fault both
   red teams simulate — leaves no diff for a reviewer to see**. The only thing
   between a rewritten number and a green gate is that nobody rewrites it;
3. **two artifacts already said the opposite in writing.** `verify_m3.sh`'s header
   listed its inputs as "committed docs, **committed JSON**, the Optuna storage,
   the registry", and `verify_m3_redteam.sh`'s failure path advised
   `Run this by hand: git checkout -- automation/runs/m3s5/bakeoff.json` — a
   command that cannot restore an untracked file. That second one is the tell: the
   drill's own recovery instruction was written in the belief that the record was
   tracked.

This is #51's question — *could this component tell if its own claim were false?*
— asked of a gate's INPUTS rather than of its outputs.

**What this session did and did not do.** The three false statements were
corrected in place (the two above plus CLAUDE.md's `verify-m3` row), and
`verify-m4`'s header states the dependency and the finding id up front, so a
reader on a fresh clone meets the explanation before the red line. The policy
itself was NOT changed: whether machine-produced records belong under review is a
decision about what this repo contains, it touches M3's evidence as much as M4's,
and this is the last story of M4 — so it is routed to ARCH at the boundary, with
three options and their honest costs written into F-029's row. Nothing waits on
it; both gates are green today and now say truthfully what they read.

## 20. Defects and surprises

- **The gate's own first run went RED, and it was the gate that was wrong.** §3
  asserted "every recorded run has a `main` parent action" and named
  `rklz7vdv2d59bn8kbp8d` — which is the **retry probe**, a single-task run that is
  *supposed* to have no parent and *supposed* to have failed. A guard firing
  because a component behaved exactly as designed is gotcha #50, caught inside the
  gate written to honour it. The fix was not an exclusion list: a *pipeline* run is
  now DERIVED as one whose actions include at least one stage of this graph, so the
  probe falls out by what it IS rather than by what it is called, and the same
  derivation feeds the SUCCEEDED check. The excluded record is printed, not
  silently dropped.
- **The gate typed the experiment name, which is the literal `verify-m2` was burned
  by.** §3 and §7 both ask MLflow what the pipeline fitted, and both said
  `"m4-pipeline"` — a string owned by `pipelines/tasks.py`'s argparse default, not
  by the gate. It is now `tasks.DEFAULT_EXPERIMENT`, extracted as a module constant
  beside `STAGES` with the reason written there, and a test fails if the gate types
  it or if `tasks.py` writes it twice.
- **A test that matched words instead of invocations went red three times in one
  run.** "The gate must not run `make pipeline`" caught the gate's own advice line
  (`run make pipeline-cache-drill` — exactly what a reader of a RED cache leg
  needs); "must not run `flyte get`" caught `kubectl -n flyte get deploy`. Gotcha
  #35 in a third hat. The tests now match at a **command position** — line start,
  or after `|`, `&&`, `;`, `$(` — through one shared helper, and a backtick is
  deliberately NOT a command position, because in this repo backticks appear inside
  message strings far more often than in command substitutions.
- **Boot found Docker Desktop down** — `kubectl: command not found`, gotcha #34
  exactly as recorded, on a host that had restarted since leg 2. One launch, ~15 s,
  and the three kind nodes came back by themselves; every platform pod reads
  `RESTARTS 2 (115s ago)` and nothing was redeployed. Recovery cost less than
  reading the gotcha did, which is what writing it down was for.

## 21. What M4 leaves M5

M4-S5 is complete and M4 is closed. The chain exits to ARCH (no ◆ at M4).

- **The gate is `make verify-m4` (39/39) and it can go red** (`make
  verify-m4-redteam`). Both re-run nothing; both are safe to run at any point in
  M5 to check that the pipeline layer is still intact underneath the serving work.
- **`@champion` is version 2** and no M4 artifact moved it. F-016 (the incumbent
  margin) is still the PO's and is still non-blocking until M7.
- **F-029 is OPEN and is ARCH's at this boundary** — a policy decision about what
  belongs under review, with three options costed in its ledger row.
- **Gotcha #66 is the trap M5 will meet first**: an image rebuild invalidates every
  cached stage, so the first pipeline run after any commit under
  `src`/`scripts`/`analytics`/`docker`/`pyproject.toml`/`uv.lock` is a full re-fit,
  not an 11-second rerun. `verify-m4` is built to be immune to it (it reads the
  recorded drill, never the newest run) — a gate written the obvious way would go
  red for a commit.
