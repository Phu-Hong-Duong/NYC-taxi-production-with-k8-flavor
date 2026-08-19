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
