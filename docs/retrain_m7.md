# The scheduled retrain (M7-S4) — the loop closed, and the transfer nobody had made

*Story M7-S4 · role:MLE (A), MLOps (R) · executor session (bo), 2026-08-20*

M7's loop is **drift seen (S3) → retrain → challenger → the gate decides**. S3
watched March 2020 lose 61% of its trips and A-9 fire; the decision that alert
asks for is a retrain, and this story is that arrow. It also lands the two
findings the kickoff made mandatory intakes — **F-022** and **F-020** — and both
turned out to be about the same thing from two directions: *a number that was
true when it was written down, applied unchanged in a place where it is not.*

---

## §0 — What this story did NOT decide

Named first, because three of them are the kind of thing a retrain quietly
decides for everybody if nobody writes it down.

* **The training window is the settled 2019 one** — train 2019-01..06, val
  2019-07, test 2019-08, copied verbatim out of `configs/train.yaml`. A window
  that swallows 2020 changes *what the holdout measures*, so the first retrain
  proves the loop on the window whose verdicts already exist. Wanting it moved is
  an ARCH/PO question and is routed, not edited (M7 kickoff, *Out of scope*).
* **The gate, its floor and its bar are untouched.** The generated training
  config copies `gate` byte-for-byte and a test asserts it (§3.3).
* **The alias did not move**, and the code cannot move it (§4).

---

## §1 — F-022: the bake-off's incumbent cell

**The defect.** `scripts/bakeoff_m3.py` declares five contenders before any
number is measured — a pre-registration, so a losing arm cannot become a
different arm at write-up time. One of those rows resolves **by alias**, on
purpose: its docstring says *"the champion comes from the ALIAS (so this bake-off
judges what is actually serving)"*. And it also pre-registered
`feature_set="v1"`.

Both were true on the day they were written. Then the bake-off's own
`--promote-winner` moved `@champion` to a **v2** model, and from that moment
every invocation died at `_load_booster`:

```
champion v1 eats ['hour', …, 'has_geometry'] but feature set 'v1' is
['hour', 'dayofweek', 'PULocationID', 'DOLocationID', 'passenger_count'].
Scoring it would silently reorder columns
```

— a correct refusal, one layer too late to be useful, and unnoticed for three
milestones because nothing re-runs a bake-off and `verify-m3` §5 *replays* the
recorded verdicts rather than re-running the script.

**The fix (option (a), decided by ARCH at the M4 boundary).** The alias row
declares **no** feature set; `_feature_set_of` derives one from the loaded
booster's own ORDERED feature names, matched against every set declared in
`configs/features.yaml`, and requires exactly one hit. Everything downstream —
the matrix each contender is scored on, the payload, the promotion guard — reads
`Loaded.feature_set`, the concrete one, never the declaration; an AST test keeps
it that way, because the file argues the change in prose that quotes the old
label (#53/#68).

The four other arms keep their pre-registered Specs. **Pre-registration is right
for an arm declared before its number existed and exactly wrong for a pointer
designed to move**, and separating the two is the whole content of the decision.

**What the fix cost, stated rather than hidden.** The 2×2's origin cell — *v1
features, hand hyperparameters* — was held by the incumbent row only because the
alias happened to hold `lightgbm-v1`. With the alias on a tuned v2 model the
square would now compute against its own "both" cell and print `auto-on-v2
+0.00%`: arithmetic that is correct, reads as a result, and answers a different
question. So `SQUARE_BASE` describes the cell instead of naming a label, and when
no contender occupies it the square is **not printed** and says why. M3's answer
is measured and recorded (`docs/bakeoff_m3.md` §6); it is not this invocation's
to re-derive.

**The execution half of the closure** (`make bakeoff BAKEOFF_ARGS="--smoke-rows
20000"`, transcript §1 of `docs/retrain_m7_transcripts.md`): exit 0, five
contenders resolved, five verdicts printed, nothing written, nothing promoted.

```
[resolve] champion (alias) auto-lgbm-v2  family=lgbm  features=v2 (24)
          (DERIVED from the artifact — F-022) trees=791 recorded val MAE 3.3822796832477016
```

**A side finding, measured while writing the derivation's test.** Two declared
feature sets — `v1_g5` and `redteam_g5_leaky` — carry **identical ordered column
lists**; they differ only in how their aggregates were FITTED (M3-S3's leaky
arm), which no artifact can report. So a model fitted on either is genuinely
unidentifiable from its own feature names, and the derivation refuses rather than
picks. That is the safe direction — neither set is promotable (g5 was dropped,
the leaky set exists only for `leakage_redteam.py`) — and a wrong answer would
have scored a champion on a matrix built from a different definition of the same
columns.

---

## §2 — F-020: the knob that meant something else at the scale it was used

**The finding, in its own numbers.** The tuned configuration that became the
champion was CHOSEN on 15% of train and APPLIED unchanged at 100%.
`min_data_in_leaf: 1293` is a leaf floor of **1 row in 5,103** on the
6,598,113-row search sample and **1 in 34,020** on the 43,987,422-row refit — the
same integer is **6.67× less regularising** at the scale it was finally fitted
at, and nothing re-derived it. The rounds budget travelled the same way and *by
construction rather than by choice*: `scripts/automl_refit.py` reads
`num_boost_round` from the sniper verdict's `max_rounds`, which the sniper wrote
as its own **per-trial search cap at 15%** (800) — and both full-data refits then
ran into it (800/800 and 791/800).

The kickoff folded option (a) into the retrain itself: the challenger IS the
champion's configuration with both halves re-derived.

### 2.1 The transfer

`taxi_mlops.training.retrain.COUNT_SCALED` names the knobs whose LightGBM
meaning is literally *a number of rows*, **with a reason each**, and a test
refuses an entry whose reason does not argue it:

| knob | why it is a row count |
|---|---|
| `min_data_in_leaf` | the minimum rows a leaf may hold — F-020's own example |
| `min_data_in_bin` | the same argument on the feature binning |
| `min_sum_hessian_in_leaf` | a sum over rows; under `l1` each row's hessian is constant, so it is a row count wearing a float's clothes |

Everything else is passed through **and the record says so** — "we considered it
and it does not scale" and "we never looked at it" are different statements and
only the first belongs in a record. `num_leaves` at 44M rows means what it meant
at 6.6M; multiplying it by 6.67 would invent a different model and file it as a
scale correction.

Measured on the live champion (`make retrain RETRAIN_ARGS="--plan-only"`):

```
min_data_in_leaf: 1293 -> 8620 — 1 row in 5,103 where it was chosen;
unchanged here it would be 1 in 34,020 (F-020); rescaled it is 1 in 5,103
```

### 2.2 The round budget

The re-derivation is a rule about **who decides**, not about a number: the budget
must be large enough that *early stopping* is what ends the fit. So the cap is
`ROUND_BUDGET_HEADROOM` (3) × the cap the champion's refit ran under, floored at
`configs/train.yaml: model.num_boost_round` — **800 → 2400** — and the run
reports, as a first-class field, whether **early stopping** or **the cap** ended
it.

That report is the point. The champion's own refit ended at **791 of 800**, which
is indistinguishable in a metrics table from a fit that converged. A cap that
binds is F-015's truncation and the number is a floor for the configuration; a
cap that does not bind is a budget nobody spent. The honest cost of the headroom
is wall-clock, and it is reported rather than hidden.

**This is not a threshold** (M7 law 4): it is a compute bound, chosen before the
fit, and nothing is judged against it.

### 2.3 The provenance is a chain of three tracked artifacts

`resolve_champion_configuration` walks it in this order, and the order IS the
provenance:

1. the registry **alias** → the champion VERSION (through
   `get_model_version_by_alias`, never `search_model_versions`, whose `aliases`
   come back empty on server 3.15.1 — M2-S3);
2. the version's **RUN** → the hyperparameters actually fitted (not a config
   file: a config records what was configured, a run records what happened);
3. the tracked **refit record** whose `run_id` is that run → the study it names →
   the tracked **sniper record** → the sample the count-scaled knobs mean.

Step 3 can legitimately find nothing — a champion fitted by hand at full scale
has no sampled search behind it. That is a **reported no-op**, never an assumed
sample fraction: F-020 *is* the finding that assuming one produces a plausible
configuration nobody can check.

---

## §3 — The generated config, and why it is not a second home

`run()` already took `train_config: str`, so the retrain writes a **resolved
config** and hands it to the ordinary path. Two properties make that safe rather
than convenient:

1. **Every block except `model` is copied from `configs/train.yaml` verbatim**
   (`COPIED_VERBATIM`: data, target, features, baselines, evaluate, gate,
   registry, mlflow) and a test asserts equality block by block. A generated
   config that could carry a `gate` of its own would be exactly the second home
   F-013 deleted, with the added hazard that nobody edits it so nobody reads it.
2. **The tuned params sit ON TOP of the configured base, never instead of it.** A
   tuned dict used as the whole param set would silently drop `objective: l1` —
   the loss KPI-09 is *defined* as — plus `seed`, `deterministic` and
   `num_threads`. Pinned by a test.

It is written under `automation/runs/m7-retrain/` and not under `configs/`, for
the same reason: `configs/` is where a human legislates.

---

## §4 — The laws a scheduled job must obey

**It cannot promote.** `run(promote=False)` is passed unconditionally and
`retrain()` has no `promote` parameter — a law with a keyword argument is a
default (`tasks.train`'s rule, inherited). An unattended job that can move
`@champion` is a job that can put an unreviewed model in front of riders at
04:00, and M3-S5's transition chain (promote → predictions → duckdb → marts →
boards → serve → parity) is not something a cron entry performs. **A PROMOTE
verdict is recorded and the alias stays where it is** — promotion deferred is a
state the registry expresses honestly; half a transition is not.

**A sampled retrain gets no verdict** (F-008), inherited rather than
re-implemented: `judge=not sampled` is passed to the one module that owns the
rule.

**The exit codes say which kind of silence this was**, in `make train`'s own
language, because a scheduler reads exit codes: **0** a verdict that passed · **1**
refused · **2** the challenger could not be built · **3** no verdict was issued ·
**4** the run CRASHED after it began.

**4 was added on 2026-08-20 and the reason is the only thing that could have
taught it.** The first full-data run fitted for 28 minutes, reached a correct
REFUSE, and then died writing the record down (§7.1). Its traceback exited with a
status this program had *already given a meaning* — "the challenger could not be
built" — so `automation/runs/m7-retrain-fulldata.status` read `FAILED 2`, and the
handoff's decoding key turned that into *the challenger could not be built* for
the next session, which is the opposite of what happened: the challenger was
built, fitted and judged. A vocabulary of exit codes is only as good as its
handling of the case it did not enumerate, and an unhandled crash must not be
able to wear a verdict's clothes. **4 is outside the vocabulary on purpose**, and
its message says what is and is not true: any verdict reached before the crash is
in the log and in MLflow, and NOT in a record.

---

## §5 — The schedule

**Flyte 2.6.1 / chart v2.0.42 carries triggers natively**, and the question was
answered by asking the tooling rather than by reading a version table (gotcha
#70's family): `flyte create trigger --help` documents `--schedule "0 0 * * *"`,
and `flyte.Trigger` + `flyte.Cron` / `flyte.FixedRate` exist in the SDK.
**The kickoff's recorded cron fallback (the `automation/` watchdog precedent) was
NOT executed and stays armed and unspent.** One attempt of a three-attempt wall.

**The triggers are declared in CODE, with their inputs.** The CLI form cannot
pass task inputs, so a CLI-created trigger would fire the retrain with its
DEFAULTS and the cadence would live in somebody's shell history. Declared, the
cadence, the inputs and the reasoning are one reviewable object that `flyte
deploy` reconciles:

| trigger | automation | inputs | auto_activate |
|---|---|---|---|
| `retrain-monthly` | `Cron("0 3 1 * *")` | full-data, judged | **False** |
| `retrain-schedule-proof` | `FixedRate(20)` | `plan_only=True` | True |

**`retrain-monthly` is registered and deliberately NOT activated**, and that is a
decision rather than an oversight. This cluster is a laptop; the full-data fit is
hours of CPU under a 6-core task limit, and a retrain firing unattended every
month on a machine nobody is watching would spend that budget to produce a
verdict nobody reads. The mechanism is what M7 owes — registered, reconciled by
the server, and *firing*, which the proof trigger demonstrates on the same task.
Turning it on is one field and a PO's call about compute.

**The proof trigger plans only, and that is what makes it a proof of the
schedule.** It exercises everything the schedule is responsible for — the trigger
firing, a pod on the pinned image, the PodTemplate's MLflow and MinIO wiring, the
registry read, F-020's transfer, the record write — and stops exactly before the
hour of CPU. A proof that fitted would be measuring the fit.

`make retrain-schedule` deploys and then **reads the triggers back off the
control plane**, never off the file it just submitted — `deploy_serving.sh` reads
KServe's deployment mode off the live ConfigMap for the same reason, and gotcha
#81's lesson one layer up: *a registered trigger and a firing trigger look
identical in a configuration table.* It also **refuses a stale image**, and
`pipelines/` is in its guarded paths where `run_pipeline.sh` deliberately leaves
it out: there `pipelines/` is the per-run code bundle, so guarding it would
refuse the very drill that edits it — but a trigger has no per-run bundle, the
image is the only carrier of both halves, and a schedule registered against a
stale image fires forever on code nobody can identify. **The guard fired on this
story's own commit** and the image was rebuilt rather than the guard narrowed.

---

## §6 — What the retrain task is, and what it is not

One stage, not seven. The monthly pipeline's six upstream stages exist to turn a
new month of TLC parquet into a feature matrix; a retrain reads the **settled**
training window — DVC-pinned, already on the volume — and changes nothing about
the data. Inside `main` its cache key would depend on a month it never reads, and
every monthly run would spend an hour re-fitting a champion nothing asked about.

It is **uncached** for `register`'s reason rather than `publish_marts`': a
retrain reads the LIVE registry to learn what it is a retrain *of*, and a cached
answer to "what is serving right now?" is wrong precisely when the alias has
moved, which is the only occasion on which anybody asks. It also mints an MLflow
run, and a cache hit that returned a verdict without minting one would break the
second witness `verify-m4` leans on. **`retries=0`**: the fit is the whole stage
and it is hours long, so a retry budget is a slower way to hide a systematic
fault, and there is nothing partial to resume.

Three inherited wiring guards went red for this addition — "every task in
workflows.py declares X" — and were **re-derived rather than widened**: the
pipeline's task set is now *what `main` awaits*, asked of the AST. Gotcha #50 for
the sixth time, and the sixth time the repair is a property instead of a longer
list.

---

## §7 — The numbers

Measured **2026-08-20T05:59Z**, full data, 43,987,422 train rows, judged on the
untouched 2019-08 holdout by the gate as it exists on disk. The table below is
recovered from the run's own output (`docs/retrain_m7_transcripts.md` §5.1) —
attempt 1 reached this verdict and then crashed writing it down (§7.1), so the
machine-written record lands with the re-run, and
`automation/runs/m7-retrain/rerun-prediction.json` says what that re-run must
reproduce before it reproduced it.

| contender | split | KPI-09 | KPI-10 |
|---|---|---|---|
| baseline-group-median-od-fallback (the bar) | test | 3.3518 | 80.733% |
| **`retrain-rescaled-v2`** | test | **3.2412** | **81.568%** |
| `auto-lgbm-v2` @champion v2 (incumbent) | test | 3.2403 | 81.577% |
| `retrain-rescaled-v2` | val | 3.3811 | 80.570% |

**VERDICT: REFUSE.** Floor conditions **passed** — +3.30% against a 2.00% bar,
KPI-10 +0.835 points. Incumbent conditions (F-011) **failed** on both halves:
−0.03% KPI-09 and −0.009 KPI-10 points against the serving champion.

**The headline is that F-020's correction changed almost nothing, and that is the
result rather than a disappointment.** The rescale was real — `min_data_in_leaf`
1293 meant *1 row in 5,103* where it was chosen and *1 in 34,020* where it was
being used, and 8620 restores the fraction. Applying it moved the holdout by
**0.0009 minutes: 54 milliseconds of mean error over 5,950,708 rows.** F-020 was
a finding about REASONING — a number applied at a scale it did not mean anything
at — and the honest reading of this measurement is that the champion was not
materially harmed by the defect. Saying so is the point; a story that had gone
looking for a win here would have found 54 milliseconds and called it something.

**F-020's second half is DISCHARGED by this fit, in the direction that could not
be arranged.** `ended_by: early_stopping`, best iteration **779 of a re-derived
2400-round cap** — 1,621 rounds unspent. The champion's own refit ended 791 of
800, a number that cannot distinguish a converged fit from a truncated one, which
is the entire reason `ended_by` is a first-class field. The re-derived budget's
job was to make truncation visible; it made this fit's *absence* of truncation
visible, which is the stronger of the two things it could have shown.

**The gate refused on a condition with no margin, and that is the open fork's
number arriving.** AWAITING_PO **2026-08-18-1** (F-016) asks whether the serving
pointer should move on deltas this size; at M3-S5 the alias moved on **+0.63%**,
and here a monthly-retrain-shaped run landed at **−0.03%**. Both are the same
no-dead-band condition, and the second one is the case the entry predicted: a
retrain of an unchanged configuration produces a model within 54 ms of the
incumbent. **Had the sign been positive by the same magnitude, the pre-registered
gate would have moved the serving pointer on 54 milliseconds** and spent the whole
transition tail for it. That evidence is recorded on the entry; it is not acted on
here (law 4, and the constitution reserves gate changes for the PO).

**The alias did not move and could not have.** `promote=False` is unconditional
and there is no parameter that changes it; `@champion` is version 2 before and
after; nothing was registered — a refused challenger leaves the registry exactly
as it found it.

### §7.1 — The verdict that could not be written down

Attempt 1 fitted for 28 minutes, reached the REFUSE above, and died on
`AttributeError: 'Check' object has no attribute 'text'`. `gate.Check` carries
`name`/`passed`/`detail`. Two things had to be true for that to survive to a
28-minute run, and both are worth more than the typo:

**The access was guarded, and the guard was on the wrong object.** The line read
`... if hasattr(decision, "checks") else None`. `Decision.checks` is a dataclass
field and is therefore always present, so the guard never protected anything —
what it did was make an unchecked access to `c.text`, one token to its left, look
checked. A guard on the container says nothing about the elements.

**Every test this module had asserted on its SOURCE.** `test_whether_the_cap_bound_
the_fit_is_reported_not_inferred` asserts `'"ended_by"' in RUN_SOURCE`; the
promotion law is an `ast` walk; the row-count law is `"43_987_422" not in
RUN_SOURCE`. Those are the right instrument for what they check — laws with no
runtime symptom — and the wrong one here: **a string test sees a field being
written and cannot see that the field does not exist.** Nothing had ever executed
the line, because executing it cost the fit. The serialiser is
`retrain_run.verdict_payload` now, a function that runs in microseconds on a
`Decision` the real gate built from attempt 1's real numbers.

**And the crash exited with a word that meant something else.** See §4's exit-code
paragraph: the traceback landed on 2, which this program had already defined as
*the challenger could not be built*, so the detached job's `.status` told the next
session the opposite of what happened. Crashes now exit **4**.

The one thing that went right by design: **the fit is the expensive half and it is
in MLflow** (run `d2f69f90a5a84e00b02e670b6a409990`, model logged with signature
and input example), so nothing irreplaceable was lost — only the record, which is
the artifact this program judges by.

---

## §8 — Honest costs and what is left

* **The monthly trigger is registered and inactive.** The loop is proven; it is
  not running unattended. One field and a compute decision.
* **The full-data retrain was run on the HOST, detached**, not on-cluster. The
  fit's rate is the reason and it is measured, not asserted: M3's full-data refit
  of this configuration took **981.5 s for 800 rounds** on the host's 20 cores,
  while M4-S4's on-cluster full-data fit took **1874.7 s for 500 rounds** under
  the train environment's 6-core limit. At a 2400-round cap the same fit is
  ~45 minutes on the host and several hours in a pod. The scheduled task runs the
  same code through the same entry point; where a given execution ran is recorded
  with it.
* **`min_sum_hessian_in_leaf` and `min_data_in_bin` are on the count-scaled list
  and neither was searched**, so neither moved here. They are listed because the
  list is a claim about LightGBM's semantics that must be complete before the
  next search picks one up, not after.
