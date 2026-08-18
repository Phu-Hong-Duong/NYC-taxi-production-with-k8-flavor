# The M4 task graph, in plain Python — and the two findings repaired before it wrapped them

**Story: M4-S1 · role:MLE · 2026-08-18.** Sequenced first in the M4 kickoff on
purpose: the gate's calling path gets honest BEFORE Flyte wraps it, and the task
graph exists as testable Python BEFORE containerization can blur whose bug is
whose.

Nothing in this story ran on the cluster except MLflow tracking, nothing was
promoted, and `@champion` is version 2 before and after. No model was re-fitted
for a result — the one fit here is a **one-month plumbing rehearsal** that is
issued no verdict by construction (F-008).

---

## 1. F-018 — the bake-off picked its winner on the month nobody was allowed to look at

**The finding** (REV, M3 review): `scripts/bakeoff_m3.py:276` was

```python
winner = min(loaded[1:], key=lambda item: item.metrics[holdout].mae)
```

with `holdout = "test"`. Five contenders were read on 2019-08 and the lowest
took the champion alias — while `gate.verdict_lines` printed, on that verdict
and on every other this program has ever produced, that the holdout was
`untouched by training and by selection`.

### 1a. The ranking moved to val — by ORDERING, not by convention

The one-character fix (`"test"` → `"val"`) is correct and insufficient: it
leaves the ranking sitting *after* both splits have been scored, in a scope
where a holdout number exists and the only thing stopping its use is that nobody
typed it. So the selection moved instead:

```python
for split in ("val", holdout):
    ...
    if split == "val":
        _assert_val_reproduced(loaded, smoke)
        winner = _select_winner(loaded, holdout)   # <- the holdout is not loaded yet
```

`_select_winner` ranks `loaded[1:]` on `SELECTION_SPLIT = "val"` and prints the
full ranking. The floor (`loaded[0]`) is excluded because it is the **bar**, not
a candidate to serve — it still gets a holdout number and a verdict of its own,
which is how the gate is watched refusing something. The payload gained
`winner_selected_on`.

**What the M3 record does NOT do: change.** `automation/runs/m3s5/bakeoff.json`
is byte-unchanged and nothing was re-fitted. The val and holdout rankings were
identical (`docs/bakeoff_m3.md` §3), so the champion survives the defect in the
method that chose it; re-running would spend hours re-litigating verdicts that
do not move, and rewriting them silently would destroy the record of a real
defect. The JSON's *absence* of `winner_selected_on` is now the honest marker of
the run that ranked on the holdout, and a test asserts that absence.

### 1b. The gate stopped claiming what only its caller can know

`gate.py` gained **property 7**. Training-purity the gate can vouch for: it
refuses metrics from any split but the configured holdout. Selection-purity is a
property of the *caller's* process, and the gate is structurally incapable of
seeing it. So:

```python
def verdict_lines(decision, *, holdout_untouched_by_selection: bool = False) -> str
```

The default is the weaker, always-true sentence — *a claim nobody made must not
be printed as if somebody had*. `make train` (`run.py`) and
`scripts/gate_redteam_incumbent.py` fit or construct exactly ONE challenger and
pass `True`; `scripts/bakeoff_m3.py` passes `False` and prints its own selection
basis on a `[gate] selection :` line instead.

The two forms keep the shape `verify-m2` parses out of the committed M2/M3
transcripts (`holdout   : test — 5,950,708 rows, …`), so a repaired claim does
not orphan the record it was made in. Both verify gates re-run green below.

### 1c. The false sentence, corrected where it was published

`docs/bakeoff_m3.md` §3 carries a **dated correction note** beside line 87 that
leaves the false five words standing above it — what was claimed and what was
true, both readable — and states:

* what the defect costs the result: an unmeasured upward bias on the winner's
  +3.33% margin over the floor, and a real identity decided, because the two v2
  arms finished **0.0022 min (0.069%)** apart;
* what it does not cost: the champion's identity, since §3's own paragraph
  records auto-on-v2 leading on val too (3.3823 vs 3.3905);
* why `bakeoff.json` was not regenerated.

§6's "the ranking rule is KPI-09 … before any number existed" sentence carries
the same dated correction: the ranking **metric** was pre-registered, the
ranking **split** was the holdout.

### 1d. Pinned by tests that can tell the two rules apart

`tests/unit/test_bakeoff.py`, five new tests. The load-bearing one builds rows
where **the two splits disagree** — `artisan v2` best on val, `auto-on-v2` best
on test — because a fixture built from M3-S5's real numbers would pass under
*both* rules and prove nothing. That is precisely why the defect survived a
bake-off everybody read.

`test_the_selection_happens_before_the_holdout_is_scored` is structural (AST):
it asserts `_select_winner` is called exactly once, inside the split loop, under
the `split == "val"` guard. A behavioural test cannot catch the call drifting
back below the holdout pass, because both orderings agree whenever the splits
agree — some properties are about *when* code runs.

**Ledger: F-018 CLOSED** by its own (a)+(b) conditions.

---

## 2. F-019 — a tripwire, deliberately not a fix

Feature set v2 admitted g1, so the **served** model needs `is_holiday`; the
committed table `data/reference/us_federal_holidays.csv` holds ten rows, all
2019, and `calendar.assert_covers` raises on anything else. `features/` is the
ONE path for training and serving, so at M5 that is a 500 per quote.

One test now pins the CURRENT behaviour
(`test_the_configured_feature_set_refuses_a_request_dated_outside_the_table`):
it builds the **configured** set for a 2026-dated request, asserts the raise
names the table to edit and both years, then builds the same frame inside 2019
to prove the test is about the DATE and not some other defect in the frame.

The table was **not** extended and no policy was chosen. That decision — extend
the table vs a serving-time policy for uncovered dates, and degrade-vs-refuse —
is M5's with the runbook in hand (PRR minutes), per the ledger row's own closing
conditions. This story's job was to stop the trap being quiet.

---

## 3. The graph: `pipelines/tasks.py`

Six callables, typed in and typed out, in the order BLUEPRINT §9/M4 names:

| stage | wraps | returns |
|---|---|---|
| `ingest_month` | `taxi_mlops.data.ingest.ingest([month])` | `IngestResult` — row counts, rejected fraction, the three paths |
| `validate` | `taxi_mlops.data.contract.validate_output` on the parquet that LANDED | `ValidationResult` — rows, contract year, columns |
| `build_features` | `taxi_mlops.features.quote_time.build_features` via the one loader | `FeatureResult` — set version, feature names, source columns |
| `train` | `taxi_mlops.training.run.run(promote=False)` | `TrainResult` — challenger, run id, manifest path, fit seconds |
| `evaluate` | reads the manifest | `EvaluationResult` — the ONE evaluator's numbers, typed |
| `register` | reads the manifest | `RegisterResult` — verdict as DATA |

Four decisions are recorded in the module docstring rather than left to be
re-derived. The two that will be argued about:

**The seam between `train`/`evaluate`/`register` is where the CODE's seam is,
not where a diagram would like it.** `run.run()` fits, scores through the one
evaluator and asks the gate in one call. Splitting that here would move the
gate's decision into the orchestration layer — the one thing this file may not
do. So `train` runs it and writes a **run manifest**; the other two read the
manifest. It is a JSON path because at M4-S4 these become separate Flyte tasks
in separate pods, and a Python object cannot cross that boundary.

**A REFUSE is a return value, never an exception.** The CLI maps verdicts onto
exit codes (0/1/2/3) because a shell has nothing else to read. A workflow engine
has a whole object: a refused challenger is a *successful run of a working
gate*, and modelling it as a task failure would make every refusal look like an
outage, attach a retry to it, and eventually get the stage disabled by somebody
at 3am. The mapping still exists — `RegisterResult.exit_code` — stated **once**,
so there are not two copies of the rules; a test compares it against the CLI
docstring's contract.

**No stage in this file can move `@champion`** (M4's standing law). `train`
passes `promote=False` unconditionally and has no `promote` parameter at all — a
law with a keyword argument is a default. `register`'s promoting branch is not
built and says why: F-016 is an open PO fork about the exact condition that would
decide a pipeline promotion, so building the path now would mean choosing a
default for a question on the PO's desk. When it is built (M7), it must call
`run._promote`, the one function `make train` and the bake-off both already call.

`pipelines/tasks.py` imports no orchestrator, and a test enforces that in both
directions — `src/` may not import `pipelines`/`flytekit` (read off the AST's
import nodes, not the text: the words appear in this repo's prose on nearly
every page).

---

## 4. The local rehearsal (transcript)

`make pipeline-local MONTH=2019-01` — one month, `--train-months`-class
sampling, gate OFF. **F-008's exit-3 class: no verdict is claimed and no number
below is a result.** The full-data path is M4-S4's, on-cluster.

```
$ make pipeline-local MONTH=2019-01        # exit 0, 2026-08-18

[tasks] rehearsing the M4 graph on 2019-01: ingest_month -> validate -> build_features -> train -> evaluate -> register
[tasks] gate: OFF (F-008 smoke; NO verdict)
...
[1/6] ingest_month   : 7,584,656 rows out of 7,696,617 (1.4547% rejected) -> …/data/processed/train/yellow_tripdata_2019-01.parquet
[2/6] validate       : 7,584,656 rows re-read and re-checked against the 2019 output contract, 20 columns
[3/6] build_features : set v2 — 24 columns over 7,584,656 rows (train split)
[gate] NO VERDICT will be issued: --no-gate on a sampled run (F-008). Nothing here can promote.
...
[tasks] run manifest -> automation/runs/m4-pipeline/train_manifest.json

[4/6] train          : lightgbm-v1 (set v2), run 27aa90597f614ffa931182d5102025d3, 265.8s, sampled=True, judged=False
[5/6] evaluate       : from taxi_mlops.training.evaluate
        val   KPI-09 3.5983 min · KPI-10 79.170% over 6,189,748 rows
        test  KPI-09 3.3713 min · KPI-10 81.015% over 5,950,708 rows
[6/6] register       : decision=NO_VERDICT promoted=False (CLI exit-code class 3)
        no verdict was issued — a sampled run asked for with --no-gate (F-008). 'Not judged' and 'judged and satisfied' are the two things a pipeline must never confuse.
        @champion is version 2 — read, never written

[tasks] all 6 stages composed on 2019-01. This is a PLUMBING rehearsal: no number above is a result.
```

Read it in the order the story cares about:

* **The graph composes.** Six stages, one month, no orchestrator, exit 0. Stage
  1 re-derived 2019-01 and the tracked tree came back **unchanged in git** — the
  idempotence M1-S1 proved, re-proved by a different caller.
* **F-008 fires at the right layer, twice.** `run.run()` announces "NO VERDICT
  will be issued" before a row is read, and `register` reports `NO_VERDICT` with
  CLI exit-code class **3** — not 0. The stage is GREEN and the verdict field
  says nothing was judged; those are two different facts and the pipeline can
  read both.
* **The numbers are not results and are labelled so.** 3.5983 val / 3.3713 test
  come from ONE train month against the champion's six. F-008 exists because a
  sampled run flatters, so the last line of the transcript says what the numbers
  are for.
* **`@champion` is version 2 — read, never written.** The manifest records it so
  `verify-m4` can compare rather than remember (M4-S5's leg).

**One thing this story could NOT demonstrate, stated plainly.** The repaired
`scripts/bakeoff_m3.py` could not be run end to end: it has been un-runnable
since M3-S5's own `--promote-winner` moved the alias, because the `champion v1`
contender resolves by ALIAS while its Spec pre-registers `feature_set="v1"`, and
the alias now points at a v2 model. Observed live:

```
$ make bakeoff BAKEOFF_ARGS="--smoke-rows 20000"        # exit 1
[resolve] models:/nyc-taxi-eta@champion -> version 2 (run 92b73bd4f77d…)
champion v1 eats ['hour', …, 'has_geometry'] but feature set 'v1' is
['hour', 'dayofweek', 'PULocationID', 'DOLocationID', 'passenger_count'].
Scoring it would silently reorder columns — the same refusal score.py makes.
```

That is a guard working exactly as designed, one layer too late to be useful.
It is **pre-existing** — the failure is in contender resolution, before any line
this story changed — and it is filed as **F-022**, deliberately not fixed here
(the choice between "resolve the incumbent's feature set from the loaded model",
"pin the row to a version", and "a bake-off is a one-shot per milestone" is a
design call about what the incumbent row MEANS, and it belongs with whoever next
builds a contender set — M7's retrain). F-018's closing conditions do not need
the script to execute, which is why this is a filed finding and not a wall.

It does change what the evidence for §1a *is*, and that is why the tests are
shaped the way they are: a behavioural test whose two splits **disagree**, and a
structural test proving the call happens inside the val pass. Neither needs the
cluster, the registry, or a runnable bake-off.

---

## 5. Both verify gates, re-run in this story

The M4 kickoff's condition on this story: both must be green afterwards, and
`verify-m3` §5 — which replays the bake-off's five recorded verdicts through
`gate.decide` as it exists on disk — must keep passing **unmodified**. It did:
neither verify script was touched in this story's diff.

```
$ make verify-m3          # exit 0, 2026-08-18
[verify-m3] GREEN — every M3 sub-check passed.
$ grep -c "ok  " → 46          (8 sections; unchanged count, unchanged file)

$ make verify-m2          # exit 0, 2026-08-18
[verify-m2] GREEN — every M2 sub-check passed.
$ grep -c "ok  " → 55          (9 sections; unchanged count, unchanged file)
```

Why that matters more than the numbers: `verify-m2` §2 parses the committed
promotion transcripts in `docs/promotion_gate_m2.md` and `…_m3.md` and feeds
their numbers back through today's `gate.decide`. Those transcripts contain the
old holdout line verbatim. The repaired `verdict_lines` keeps the shape they are
parsed with (`holdout   : test — 5,950,708 rows, …`) precisely so a corrected
claim does not orphan the record it was made in — and a unit test asserts that
property on both forms of the sentence rather than trusting it.

Neither gate re-fits anything, and the registry is identical after both:
`@champion` → version **2**, versions `[1, 2]`.

---

## 6. What this story did not do

* **Did not promote.** Nothing in the diff can move an alias; `@champion` is
  version 2 before and after, and the rehearsal read it without writing it.
* **Did not re-run the M3 bake-off or regenerate `bakeoff.json`.** The M3 record
  stands as measured; the correction is a dated note, never an edit.
* **Did not fix F-019.** A tripwire pins the current behaviour; the policy is
  M5's, in the PRR minutes.
* **Did not fix F-022** (filed this story). No M4 story runs the bake-off; it
  becomes blocking at M7's first retrain.
* **Did not touch Flyte.** `pipelines/tasks.py` imports no orchestrator, and a
  test fails if it starts to — the decorators are M4-S4's.
