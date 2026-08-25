# The incumbent margin, landed era-aware — M9-S10 (F-016 · F-068)

*Executor session 2026-08-25 · role:MLE · nothing was fitted, no alias moved, no
registry version was created, no wire changed. This story does not promote
anything; it changes what a future promotion must clear.*

---

## 0. What the PO decided, and what it cost to land

Two findings, one letter each, both answered on 2026-08-25:

* **F-016** (raised at M3-S5): the incumbent condition was plain
  non-regression with **no margin**, so the alias moved on **+0.63%** — 1.2
  seconds of mean error over 5.95M rows — while the floor condition four lines
  above it in the same config demanded **2.00%**. The two bars disagreed about
  what a promotion is worth. AWAITING_PO **2026-08-18-1**, answered **option B**
  (a **≥0.50%** margin).
* **F-068** (raised at M9-S6, which is why B did not land then): three
  milestone gates REPLAY recorded verdicts through `gate.decide` **as it exists
  on disk**, and `scripts/f016_replay_probe.py` measured — before any edit —
  that **two of nine** recorded verdicts flip from PROMOTE to REFUSE under any
  positive margin. Both are a champion judged against **itself**, at exactly
  **+0.0000%**. AWAITING_PO **2026-08-24-4**, answered **option (b)**:
  *era-aware replay*.

The whole story is that second answer. A tightening is easy; a tightening that
does not falsify the program's own record is the work.

## 1. The knob, and the number

`configs/train.yaml: gate.incumbent_min_improvement_pct: 0.50` — one home
(F-013), with its argument beside it. The two observations the decision was
made against are both on file and both are quoted in the config comment:

| Observation | What it did under NO margin | Under 0.50% |
|---|---|---|
| M3-S5 `auto-on-v2` at **+0.63%** vs the incumbent | **moved** the alias | still moves it |
| M3-S5 `artisan v2` at **+0.5612%** | recorded PROMOTE | still promotes — **0.06 points of daylight** |
| M7-S4's scheduled retrain at **−0.03%** | **held** the alias | still holds it |
| M3-S5 `champion v1` / M3's `lightgbm-v1` at **+0.0000%** | recorded PROMOTE | **REFUSED** (F-068's two rows) |

0.50 is deliberately set **below** the one transition this program has actually
made, not above it: a bar chosen so that history's only alias move would have
been refused is a bar chosen from the wrong end.

**The cost, stated rather than netted out:** a model genuinely 0.3–0.4% better
than the champion will not ship. That is what a maintenance-cost bar is, and it
is still a real loss — this program would rather leave a fifth of a second of
mean error on the table than move a pointer for it.

**The identity case is DECIDED, not incidental.** A challenger numerically
identical to the incumbent is REFUSED under any positive margin. The
one-way-door objection the old unit test made (*"`make train` must be able to
reach its own verdict again"*) does not bite, and the reason is worth keeping:
the idempotence it names lives in `registry.promote`, not in the gate — a
re-run that reproduces the champion's numbers changes **nothing** about the
registry under either rule, because the alias already points at that model.
What changed is the exit code of such a re-run: 0 (a no-op promotion) becomes 1
(a refusal).

## 2. Era-awareness, and the one inference it refuses to make

`src/taxi_mlops/training/gate_eras.py` answers exactly one question — *what bar
was this verdict taken against?* — and refuses to guess:

1. If the verdict **declares** its own margin, that wins. From M9-S10 on every
   verdict does: `Decision.incumbent_required_pct`, `as_mlflow()`, the promoted
   version's `gate_incumbent_required_pct` tag, the retrain record, the pipeline
   manifest, and the transcript line `verdict_lines()` prints.
2. Otherwise the **enumerated pre-B set** is consulted — the nine rows in
   `automation/runs/m9-f016/replay-wall.json`, keyed on (leg, source, label),
   each in force at **0.00%**.
3. Otherwise it **raises**.

Step 3 is the point. The default that would "work" is zero, and zero is the
loosest bar there is — so a permissive default would let a *future* verdict,
taken under a margin and recorded carelessly, be replayed against nothing at all
and pass. That is F-048's rule (*an unresolvable value never resolves to
something convenient*) applied to a bar instead of a divisor. Because of step 1,
the inference-from-absence is confined **permanently** to those nine rows: the
frozen set never has to grow.

This is not a new idea in this repository. `verify-m2` §2 has said since M3-S1
that *a verdict is replayed against the bar it was actually taken against, or it
is not a replay* — about the FLOOR, whose name changed under two committed
transcripts. Era-awareness is the same sentence about the margin, with one extra
obligation the floor case did not have: a floor name cannot be silently absent,
and a margin can.

**Where the ratchet lives, and why it is separate.** Era-awareness makes HISTORY
replay correctly. On its own it would also make a **loosening** replay
correctly — every old verdict judged against its own old bar while the live one
quietly fell, nine green sub-checks and a gate nobody can promote past.
`gate_eras.assert_margin_never_decreased` is the half that does not move: the
number on disk must be ≥ the largest margin any recorded verdict was taken
against, and ≥ the sanctioned 0.50%. It has **one** home (`verify-m2` §2).

## 3. The replays: nine recorded verdicts, zero flips

### `make verify-m2` §2 — four transcript blocks

```
== 2. the gate: M2-S3's transcripts replayed through the gate code on disk NOW ==
  ok   the KPI-09 margin bar is still >= 2.00% (configs/train.yaml: 2.0)
  ok   the KPI-10 no-regression condition is still armed (it can refuse what the margin admits)
  ok   the bar is still an HONEST floor on the untouched holdout (baseline-group-median-od-fallback, test)
  ok   replayed lightgbm-v1-hobbled-shuffled-target: 7.6667 vs 3.5090 min -> REFUSE (-118.49%), as the transcript records
  ok   replayed lightgbm-v1: 3.2608 vs 3.5090 min -> PROMOTE (+7.07%), as the transcript records
  ok   replayed lightgbm-v1: 3.2608 vs 3.3518 min -> PROMOTE (+2.71%), as the transcript records
  ok   replayed champion-v1-plus-0.06min: 3.2667 vs 3.3518 min -> REFUSE (+2.54%), as the transcript records
  ok   the refusal transcript exists WITH BOTH NUMBERS and still refuses (2 block(s))
  ok   the promotion transcript exists with both numbers and still promotes (2 block(s))
  ok   all 4 verdict(s) replayed ERA-AWARE — margin(s) in force when they were taken: ['0.00%']
       (F-016/F-068: read off the verdict, else from the enumerated pre-B set, never defaulted)
  ok   the live incumbent margin 0.50% is >= the PO-sanctioned 0.50% and >= every margin a
       recorded verdict was taken against — lowering it is a PO fork, not an edit
  ok   the gate's floor only ever got HARDER: 3.5090 min (M2) -> 3.3518 min (…) on the same holdout month
  …
```

The third replayed line is one of F-068's two flips (`docs/promotion_gate_m3.md`,
`lightgbm-v1` at +0.0000% against incumbent v1). It reproduces its recorded
PROMOTE **because** it is replayed at the 0.00% bar in force when it was taken.

### `make verify-m3` §5 — the five bake-off contenders

```
== 5. the bake-off: five verdicts replayed through gate.decide as it is on disk NOW ==
  ok   the bake-off recorded all 5 contenders on 'test' — floor, champion v1, artisan v2, auto-on-v1, auto-on-v2
  ok   replayed floor: 3.3518 vs floor 3.3518 min, incumbent v1 3.2608 -> REFUSE (+0.00%), as the bake-off recorded
  ok   replayed champion v1: 3.2608 vs floor 3.3518 min, incumbent v1 3.2608 -> PROMOTE (+2.71%), as the bake-off recorded
  ok   replayed artisan v2: 3.2425 vs floor 3.3518 min, incumbent v1 3.2608 -> PROMOTE (+3.26%), as the bake-off recorded
  ok   replayed auto-on-v1: 3.5038 vs floor 3.3518 min, incumbent v1 3.2608 -> REFUSE (-4.54%), as the bake-off recorded
  ok   replayed auto-on-v2: 3.2403 vs floor 3.3518 min, incumbent v1 3.2608 -> PROMOTE (+3.33%), as the bake-off recorded
  ok   the replayed set is not all-passing: 3 PROMOTE, 2 REFUSE — including the floor judged against itself
  ok   all 5 verdict(s) replayed ERA-AWARE at the ['0.00%'] margin in force when the bake-off ran —
       including 1 judged against the incumbent's own number (champion v1), which is the row F-068
       stopped this landing on
  …
```

and §6's bar check now asserts **both** bars:

```
  ok   both bars are unchanged: KPI-09 margin >= 2.0% over the floor, >= 0.50% over the serving
       champion (F-016's sanctioned 0.50%), and the KPI-10 no-regression condition still armed
```

### `make verify-m7` §6 — and the charter's premise, corrected by measurement

The kickoff names verify-m7's retrain leg as a third era-aware replay. Measured:
**it does not replay.** It READS `automation/runs/m7-retrain/latest.json` — the
verdict as the retrain recorded it — and never calls `gate.decide`. So it needs
no era table, and this story added the sub-check that says so *checkably*
instead of leaving the premise unexamined:

```
  ok   this recorded verdict needs no era table: it is -0.03% against the serving champion, so it is
       REFUSED under the non-regression bar in force when it was taken AND under M9-S10's 0.50%
       margin — 2 incumbent condition(s) failed then and would fail now
```

A record whose meaning depended on the era would show up here as a POSITIVE
percentage with a REFUSE beside it. That is a finding, never an edit.

## 4. The monotonic check, demonstrated RED

`make gate-margin-redteam` plants **0.10** — a well-formed, still-positive
margin that still refuses the identity case, so it satisfies F-068's arithmetic
while spending the PO's letter without one. A drill planting `-200` proves the
parser works and teaches nobody anything.

```
[gate-margin-redteam] 0. the config as it stands (restored to exactly this, whatever happens)
  configs/train.yaml  sha256 624731e25bd8…  incumbent margin 0.50%

[gate-margin-redteam] 1. lower the incumbent margin 0.50% -> 0.10% — a plausible number, typed without a letter
  incumbent_min_improvement_pct: 0.50 -> 0.10

[gate-margin-redteam] 2. make verify-m2 — expected RED, naming the loosening with both numbers
  FAIL the incumbent margin was LOOSENED: the incumbent margin on disk is 0.10% and the largest
       margin a recorded verdict was taken against is 0.50%. A gate may be TIGHTENED by whoever can
       argue for it and LOOSENED only by a PO fork (CLAUDE.md); lowering it here would also re-open
       the two verdicts F-068 recorded — replaying history against its own era is not a licence for
       the live bar to fall.
[verify-m2] RED — 1 sub-check(s) failed.
  ok   the gate exited 1 — RED against a margin below the one the PO sanctioned
  ok   it NAMES the loosening AND the number it fell below (the monotonic check, verify-m2 §2)
  ok   the era-aware replays all still passed — history is judged by its own bar, and only the LIVE bar moved
  ok   56 sub-check(s) still ran and passed — the gate reports everything, not the first thing

[gate-margin-redteam] 3. restore the config and re-run — expected GREEN again
  restored configs/train.yaml (sha256 624731e25bd8…)
  ok   configs/train.yaml is byte-identical to what the drill found (sha256 624731e25bd8…)
  ok   the gate is GREEN again (57 sub-checks, exit 0) — the drill left nothing behind

[gate-margin-redteam] PASSED
```

**The third `ok` is the load-bearing one.** If lowering today's bar had turned
the historical replays red, the replays would be reading the live config instead
of the era — which is the defect era-awareness exists to prevent, arriving
through the check that was supposed to prove it.

**And the drill found a defect in its own gate's first draft, which is the usual
yield of writing the red team second.** The monotonic check was asserted
**twice** — once in §2's bar block and once inside the era-aware summary — so a
lowered margin produced **two FAILs carrying the same sentence**. That reads
like two independent witnesses and is one fact counted twice; the repair split
the concerns, so the era line now asserts era-awareness only and the ratchet has
one home. The drill's negative check is what forced it.

## 5. What was verified

| Claim | Command | Observed |
|---|---|---|
| Nine recorded verdicts replay era-aware, **0 flips** | `make verify-m2` · `make verify-m3` | GREEN **57/57** · GREEN **47/47** |
| The retrain record's REFUSE is era-stable | `make verify-m7` | GREEN (10 verdicts in §6) |
| Both planted-edit drills survive the rewrite | `make verify-m2-redteam` · `make verify-m3-redteam` | PASSED · PASSED |
| The margin cannot be quietly lowered | `make gate-margin-redteam` | PASSED — 1 FAIL, 56 still green, sha256-identical restore |
| Direction and edges | `uv run pytest tests/unit -q` | **1,269 passed**, no skips |
| Lint | `uv run ruff check .` | All checks passed |
| Nothing moved | inside `verify-m2`/`m3`/`m7` | `@champion` **2**, `feature_set v2`, versions `['1','2']` |

## 6. What this story deliberately did not do

* **Nothing was re-fitted and no verdict was re-taken.** The nine recorded
  verdicts are replayed, never re-judged; had any flipped, the charter's STOP
  rule applies — *a finding and a PO question, never an edit to the replay*.
* **`automation/runs/m9-f016/replay-wall.json` was not regenerated.** The probe
  was re-run as a READER (no `--json`) and still reports its two flips, which is
  correct: it measures what the margin does to the recorded verdicts, and that
  answer did not change. A set regenerated against today's gate would not be a
  measurement of the old one (F-053/F-063's shape — gotcha #48).
* **The floor bar (2.00%), the KPI-10 conditions, and the incumbent KPI-10
  condition are untouched.** The PO's letter moved one bar.
