# LEARNING_GUIDE — field notes, one per story (inherited law from the predecessor)

Law: every story closes with its note BEFORE the next story starts. Format per
note: what was built · why this way · the concept underneath · what to look at ·
what to try yourself. Newest milestone first. The reader is the principal six
months from now.

---

## M7

### M7-S3 — the alert that correctly did not fire (2026-08-20, role:SRE)

**What was built.** A drift monitor: exact PSI from DuckDB value counts, one
scoring month against the champion's training distribution; a pushgateway
in-cluster; three new alert rules (A-8 input drift, A-9 volume, A-10 staleness);
Evidently 0.7.21 as a second witness; and the two client-side pushers that
finally give F-035's absences a metric source. Plus a drill that wrote its
prediction to disk before computing anything.

**Why this way.** Three choices carry the story. (1) **The reference is the
train months and never moves** — drift is the distance between what the model
LEARNED and what it is being asked, and a rolling reference makes a world that
drifts 3% a month invisible forever. (2) **The job pushes raw numbers and issues
no verdict**; the bar lives in the selector of one Prometheus rule, so the
pushed values stay re-interpretable after the fact and there is exactly one
place to review when someone wants the bar loosened. (3) **The bar was argued
from the two 2019 months whose verdict already exists** — the champion was
measured on them and promoted, so the distance they sit at is one the program
already decided to live with. That is the only honest way to set a drift
threshold without setting it from the number the thing under test just produced.

**The concept underneath: an instrument's blind spot is a design input, not a
caveat.** PSI is a distance between *shares*. Halve every count and PSI is
exactly zero. That sentence was written into `docs/slo_serving.md` §8.1 before
the job ran, and it is why A-9 exists as a separate signal rather than as a
refinement of A-8. Then March 2020 arrived: **max input PSI 0.0217 — lower than
an ordinary July 2019 — and a volume ratio of 0.3913.** The shape alert stayed
silent through the largest demand shock in the city's history, and the volume
alert caught it. Had the blind spot been treated as a caveat in a doc instead of
as a second rule, this stack would have watched COVID happen with every drift
panel green.

The general lesson is worth more than the taxi data: **before you ship a
detector, write down what it is structurally incapable of seeing, and then go
build the thing that sees that.** "Structurally incapable" is stronger than
"might miss" — it means there exists a real-world change the statistic maps to
exactly zero. Most monitoring gaps are of that kind, and they are all findable
on paper, in advance, for free.

**What to look at.** `docs/slo_serving.md` §8 (the bar, argued, with the order
of work recorded and checkable from git) · `src/taxi_mlops/monitoring/drift.py`'s
docstring (why the reference does not move, and what the share floor is for) ·
`infra/monitoring/alerting_rules.yml`'s `crosstown-drift` group — read A-8's
`blind_spot` annotation, which names what it will not catch and says what should
happen if that ever bites · `docs/drift_detection_m7.md` §4 · and
`infra/helm/monitoring/prometheus-values.yaml`'s `honor_labels: true`, which is
one flag standing between working rules and rules that sit inactive forever
looking exactly like a healthy system.

**What to try yourself.** Two experiments, in order. First: delete
`honor_labels: true`, redeploy, re-run `make drift-drill`, and watch nothing
fire — no error, no red target, no complaint, just silence. Sit with how
completely that failure hides. Second, the more interesting one: `make drift`
already computes per-month, and M7-S2's `scoring_daily` mart already holds the
daily series. Compute PSI for **22–31 March 2020 alone** against the same
reference and see whether A-8's bar would have been crossed. If it would, you
have just measured the price of a monthly window — and you will also understand
why this story deliberately did *not* change the window after seeing A-8 stay
quiet: the window is part of the bar, and re-choosing it to make an alert agree
is the exact move the milestone's fourth law forbids.

### M7-S2 — the check a monitoring table cannot make for itself (2026-08-20, role:MLE)

**The one-sentence version.** The champion scored 15.4M rows it was never judged
on and published them as a product — and the interesting engineering was not the
scoring, it was noticing that these numbers have nothing to disagree with, and
buying them an anchor from a month that does.

**What was built.** `taxi_mlops.training.batch` (the callable a schedule will
wrap), a fourth output tree with its own column contract, a sixth analyst
reconciliation, a daily Postgres mart, four new KPI ids, twenty tests.

**The problem nobody states out loud about monitoring numbers.** M2-S4's
predictions have a hard anchor: the registry says the champion was promoted at
KPI-09 3.2403 on the holdout, so re-scoring must return 3.2403 or nothing is
published. That single check catches the two failures that have no other symptom
— a different model loaded, or a feature matrix built differently from the one
that fitted it. Now write the same command for 2020-03. **What does 3.32 get
compared against?** Nothing. No gate ever asked. And the failure mode is worse
than "a wrong number": a wrong-but-plausible MAE on a COVID month *reads exactly
like drift*, and the next story is being built specifically to believe it.

So the path re-scores the **holdout** before it writes a single monitoring row,
and refuses unless the champion's own tag comes back. A month with a known
answer proves the loader, the feature path and the booster; only then is a month
with no known answer written. It costs two minutes. **The concept underneath: an
unverifiable output can borrow verifiability from a verifiable one that shares
its machinery** — you cannot check the answer, so you check the instrument, on
the one input whose answer is on file.

**The measurement that will outlive the story.** March 2020's whole-month error
is 3.3227, which is unremarkable. Split at the collapse: the first ten days are
**68.23% of the month's rows** and score 3.0463 — January, to two decimals — and
the last ten days are **3.32% of the rows** at 5.3128, with 62% of quotes inside
five minutes instead of 83%. A row-weighted monthly average is weighted by
exactly the rows that vanished. F-045 found this on the input side at S1; it is
worse on the output side, which kills the tempting reading that "the error metric
will catch it anyway".

**And the column that says which thing broke.** Mean actual duration in those ten
days is 9.69 minutes; the champion quotes 13.83. An absolute error cannot tell
over-quoting from under-quoting, and in a month where the traffic vanished those
are opposite diagnoses — so KPI-16 is *signed*, unbounded, and reads +4.14. The
model did not rot. The world moved and the model kept describing the old one.

**The discipline that was hardest to keep.** Every number above is a reason to
set a drift threshold, and setting one here would have been the story's most
satisfying paragraph. M7 law 4 forbids it: the window, the reference and the bar
are S3's, argued before the job runs. A bar chosen from the number just measured
is a bar that agrees with itself.

**What to look at.** `src/taxi_mlops/training/batch.py` — read `_self_check`
first, then the AST test that pins it before any write ·
`analytics/dbt/tests/assert_scoring_daily_reconcile.sql`, whose comment explains
why the ingest report and not the predictions file is the authority ·
`docs/batch_inference_m7.md` §4 · the `pending`-vs-`NO` branch in the sixth
reconciliation, which is gotcha #50 written as code.

**What to try yourself.** Delete two-thirds of one month's scoring predictions
and run `make duckdb`. The MAE it produces is completely ordinary; the
reconciliation is the only thing in the system that objects. Then re-read how
many published numbers in any project you have worked on had a check like that
standing behind them.

### M7-S1 — a new kind of month, and the difference between a file being wrong and a world being different (2026-08-20, role:DE)

**The one-sentence version.** The program learned to ingest months it will never
train on — 2020-01, 02 and 03, through the same contract, the same one cast and
the same counted rejections, into trees the settled 2019 pins cannot see — and
the two most useful things it learned were that COVID-March passes the contract
without a murmur, and that a drift metric averaged over that month would too.

**What was built.** `configs/data.yaml` gained a `scoring` block naming three
months and two directories. `ingest_month` gained nothing except three path
methods that dispatch on which list a month is in. Four analyst views, two more
reconciliations, two Make targets, a probe, a fixture drill, fourteen tests.

**Why the trees are separate, and why that is the whole design.** The tempting
implementation is a fourth split: add `scoring` to the split enum, write into
`data/processed/scoring/`, done in twenty lines. It would work, and it would be
a trapdoor. `data/processed` is globbed by the rebuild proof, the analyst's
`trips_clean`, the dbt sources and — through those — the training matrix, the
marts and every Metabase card. Every one of those globs was written when that
directory meant *the settled 2019 months*. Put a 2020 row inside it and nothing
raises; the numbers simply become numbers about a different world, and each of
them still looks entirely plausible. So: separate trees, separate DVC pins, and
the old path methods left refusing scoring months so a future caller cannot
reach the new data by accident. **The check that this held is one command** —
`dvc status data/processed.dvc data/rejected.dvc` — and it is the story-exit
invariant the kickoff asked for.

**The concept underneath: a config split needs its crossing guarded.** Split
months live in `train.yaml`, scoring months in `data.yaml`, because they are
different kinds of fact. Splitting a list across two files creates exactly one
new failure — the same item in both — so `load_config` raises on it. That is the
general shape: when you separate two things that used to be one, name the
mistake the separation makes possible and check it, rather than trusting nobody
will make it.

**The measurement that was allowed to come back either way.** The kickoff could
have said "demonstrate the contract refusing a 2025 file". It said *measure* what
the contract does with 2025, and record whichever answer comes back. It
validated: the `Airport_fee` alias fired, `cbd_congestion_fee` was required and
present, and THE cast absorbed 2025's int32 id columns. Three mechanisms written
at M1-S1 against a schema that did not exist yet, meeting the real bytes for the
first time two milestones later, and agreeing. That is a SURPASS — and it is only
a SURPASS because nobody had pre-decided the answer. **Note what it does not
claim**: passing the *structural* contract is not "2025 works". The cleaning
profile, the rejection rate and whether a 2019-fitted champion means anything on
2025 data are all unasked.

**Because it validated, the refusal had to be arranged — and arranging it found
a bug.** A contract whose refusal has never been watched is a claim. So three
fixtures break the real file's structure in the three ways TLC could actually
break it, and each must exit **1**. The `rename-required` fixture reported
`required column(s) absent: ['VendorID']` and said nothing at all about
`VendorID_v2` sitting in the same frame — because `check_columns` raises in the
missing branch before the unknown branch can run. Each branch is individually
correct. An operator reading that message goes looking for a deletion when the
field has merely moved. **Reading the code would not have shown this; running
the fixture did.** Both are named now, and the message offers `aliases:` as the
fix.

**The finding that matters most, and why it was worth stopping to write down.**
March 2020 is the most drifted month this program will ever hold. Its mean trip
duration is **13.1645 minutes**. January 2020's is **13.2123**. That is a 0.36%
move — *less than the ordinary January-to-February wobble of +2.71%*. By its
marginal distributions, COVID-March is the most normal month of the three. Look
inside it and the daily series runs from **240,520 trips at 14.878 min on the
5th** to **5,361 trips at 9.715 min on the 29th**: the city stopped, and the
month's average is dominated by the ten ordinary days at its head.

A drift job with a monthly window on `trip_duration_minutes` could look straight
at that and report nothing. The temptation, when that happens two stories from
now, will be to lower the threshold until the alert agrees — which is precisely
the move this program's law 4 forbids, and it would be fixing the bar when the
*instrument* is what has the wrong shape. **Finding it now, before the drift job
exists, makes that mistake unavailable.** The finding is routed with three
costed readings and no recommendation, because choosing the window from a number
just measured is the same error one level up.

**What to look at.** `docs/scoring_months_m7.md` §8 (the two signatures, side by
side — statistical drift writes 2.9M rows, schema drift writes *nothing*, so a
schema break produces no drift metric at all and an empty dashboard looks
healthy) · §9 (F-045's table) · `tests/unit/test_data_scoring.py`, in particular
the two red teams: a truncated month, and a sidecar relabelled under the wrong
rule *with its monthly total left correct*.

**What to try yourself.** Run `make contract-probe PROBE_ARGS="--month 2025-02"`
— a different month of the same year, thirty seconds, writes nothing. Then run
`--fixture unknown-column` against it and watch the exit code, not the message.
Then ask the layer the one question this story exists to make askable:
`SELECT month, ROUND(AVG(trip_duration_minutes),4) FROM trips_scoring GROUP BY 1`
— and then ask it again grouped by day, and see how much a monthly mean can hide.

---

## M6

### M6-S5 (leg 2) — the gate that graded a milestone, and the two things it caught in our own prose (2026-08-20, role:SRE)

**The one-sentence version.** `make verify-m6` reads sixty-three properties out
of eight tracked records, the live cluster, the live Prometheus, the registry
and five committed documents in **2.147 seconds** — evidence that cost about
fifty-five minutes of deliberate failure to produce — and the first two things
it found were not in the system at all: they were stale claims we had written
about the system.

**Why a gate re-runs nothing, stated at its strongest yet.** Every milestone
gate before this one said "re-fits nothing" or "re-runs nothing". M6's version
has a sharper reason. The gameday held a **~5 minute total outage of the only
predictor** on purpose so that a `for: 3m` rule could fire; the rollback drill
moved the alias twice; the canary drill shifted rider traffic. A gate that
re-provoked any of that would (a) cost a real outage every time somebody asked
whether the milestone happened and (b) move the pointer M6's own law 3 forbids
moving. So the design is: read the record, and ask the LIVE system only the
questions a record cannot answer. There are exactly three — one Prometheus
query, one rules-API read, one prediction — and each earns its place.

**The live question worth copying.** M6-S5 leg 1 found F-043: under saturation
the predictor's own `/metrics` went from 4 ms to 4.613 s with one scrape failing
outright, so the latency alert *cleared itself in the middle of the event it was
firing about*. That is a signal going dark exactly when it matters, and no
record can tell you whether it is dark right now. So §1 asks: is the champion's
exporter up, and does its scrape finish inside the configured interval? One
query. Two details that are the actual lesson: it is **scoped to the champion's
InferenceService by a name read off the manifest** — the gameday's own storage
record accidentally reported the SHADOW's series by taking the first result —
and the bar is the **scrape interval read from the values file**, not a number
typed into the gate.

**"No literals" grew a new edge this time: no THRESHOLDS.** Previous gates
learned not to type a champion version (gotchas #49/#50). M6's equivalent is
that a gate must not carry its own copy of `0.05`, because then it stays green
after the rule it is checking is loosened to `0.5` — and loosening a threshold
is precisely what the constitution reserves for a PO fork. So every number on
the right-hand side of a comparison is *parsed out of the rules file* and looked
for in the SLO document. The gate cannot tell you the threshold is right; it can
tell you the threshold has an argument written beside it, in the document that
owns it, which is the only thing a reviewer can act on.

**Two checks about TIME that read like pedantry and are not.** (1) "Shadow
before canary" is an ordering, so it is checked on the two records' own clocks
(14:49:23Z vs 15:23:48Z) rather than on the order the write-ups are arranged in.
(2) The gameday's predictions were checked twice: written before the first
injection *by clock*, **and** field-by-field equal to the copy inside each
scenario record. Either alone is defeatable — a prediction can be written first
and then quietly edited into the record it is judged against.

**What it caught in our own prose — F-044.** Leg 1 moved the restore's honest
label one notch ("NOT REHEARSED" → "scratch-rehearsed 2026-08-19; a full restore
over a dead platform still not") in the backup script's header, in the
`MANIFEST.txt` it writes, in the gameday write-up and in CLAUDE.md — whose
backup row then asserted that *every* artifact said so. Two did not: the `echo`
the script PRINTS on every run, and the deployments ledger. **The header is for
review; the printed line is for 3am.** Nothing about the system was wrong; a
claim about the system was stale in exactly the two places a reviewer does not
look and an operator does (gotcha #91).

**And what the RED TEAM caught in the gate — the better story.** The drill plants
gotcha #75's wrong anchor: the kill's outage rewritten to the record's own
`error_window.span_s`, 13.75 → 13.501. Two witnesses were supposed to speak. Only
one did. The prose leg — "every number the write-up quotes must be in the record
it cites" — rendered 13.75 at **zero** decimals as `14`, and `14` appears in
almost any document of any length, so it matched; and the planted 13.501
rendered as `14` too. The floor is one decimal now (gotcha #90). Two things to
take from it: a comparison whose loosest accepted form is one the document is
almost certain to contain is not a comparison; and this was only ever visible
because the plant was **close enough to be plausible** — a red team that had
written `999` into that field would have gone green on both legs and taught
nobody anything.

**One test lesson, free of charge.** `test_the_gate_re_runs_nothing_expensive`
went red twice for matching WORDS rather than INVOCATIONS: the gate legitimately
*reads* `scripts/platform_backup.sh` as a file (to check the label it prints),
and then the launcher pattern's `sh` alternative matched inside the filename
`platform_backup.sh` itself. Gotcha #68, twice in one function. The needle has
to sit where a shell would START a command.

**What to look at.** `docs/verify_m6_transcripts.md` — §0 answers §9/M6's
accept-when clause by clause with the observed number beside each, which is the
form a boundary review can actually check; §2.1 is the red team failing usefully.
`scripts/verify_m6.sh` §2 for the threshold-derivation idiom and §6 for the
outage-anchor re-derivation. `tests/unit/test_verify_m6.py` for what a gate is
forbidden to do.

**What to try yourself.** Open `infra/monitoring/alerting_rules.yml`, change one
threshold (say A-3's `0.01` to `0.5`), and run `make verify-m6`. Watch §2 name it
— then put it back and notice that the SLO document, not the gate, is where the
argument would have had to change. Then run `make verify-m6-redteam` and read
what it does NOT break: the pod uids, the alias, the prediction, the seven
recorded checks. A red team that breaks everything proves nothing about the one
thing it meant to test.

### M6-S5 (leg 1) — Gameday 1: every alert behaved, and two of our written arguments did not (2026-08-19, role:SRE/MLOps)

**What was built.** `make gameday` — four staged failures against the live
serving stack with every prediction written to disk before the first injection —
and `make restore-drill`, the first restore this program has ever performed. Plus
two corrections to prose that had been standing as if it were measurement, one
new open finding, and no threshold changes at all.

**Why this way.** The positive control comes first because three of the four
scenarios make a claim of the form *alert X did not fire*, and that sentence is
worthless from an instrument nobody has just watched work. A Prometheus that had
quietly lost its rules would produce a flawless run of silent alerts and a
gameday that felt like a success. So scenario 0 fires two real alerts end to end
— rule, pending, firing, Alertmanager — and only afterwards is a negative worth
reading. Everything else follows from that same instinct: predictions are
quantitative and name alert ids; each one says what must NOT fire, because a
drill that predicts only "something breaks" cannot be wrong about a signature;
and the committed prediction file is compared against the code by a unit test, so
amending a prediction to match an outcome is a red test rather than a diff nobody
reads.

**The concept underneath: the difference between a system being correct and our
account of it being correct.** Every alert did the right thing in every scenario.
Two of the ARGUMENTS published beside them were inferences that had never been
tested. A-2's 10% threshold was justified by dividing an outage's failures by a
full window's traffic — but `rate(...[5m])` extrapolates from what is actually
inside the window, and thirty seconds into a load run that is thirty seconds of
traffic, so the share peaked at 0.5000 rather than the predicted 5%. What
protects against paging is the `for: 5m` sustain, not the threshold. A-7's
annotation claimed it fires before A-5, reasoning from cause; the two `for:`
windows say 2m beats 3m by sixty seconds, and they do, every time. Neither
correction moved a number. Both moved a sentence, which is the part a human at
3 a.m. actually reads.

**The surprise nobody had a prediction for.** Fifteen minutes of saturation made
the predictor's own `/metrics` endpoint starve: scrape duration went from 4 ms to
4.613 s and one scrape failed outright, so `PredictorLatencySLOBurning` cleared
itself in the middle of the event it was firing about. The idle second predictor
— the v1 shadow M6-S3 left running — was scraped by the same job every fifteen
seconds throughout at 0.004 s, which rules out Prometheus, the network and the
scrape config in one comparison. *A predictor does not have to die to stop
reporting; it only has to be busy.* That is the loud principle already in the SLO
document (measure at the edge, because a dead predictor cannot report its own
absence) one notch quieter and therefore more dangerous.

**What to look at.** `docs/gameday_m6.md` (§2.1 and §4.1 are the two wrong
predictions; §4.2 is F-043) · `automation/runs/m6-gameday/predictions.json`
alongside the four scenario records · the dated correction in
`docs/slo_serving.md` §3, which is kept BESIDE the paragraph it corrects because
decisions were made from the original · `scripts/restore_rehearsal.py`'s header
for what a rehearsal is allowed to claim.

**What to try yourself.** Take any alert you own and ask what its denominator
contains one second after the event starts. Then look at whether its written
justification is a measurement or an inference — and if it is an inference, the
cheapest possible experiment is usually to cause the thing and watch. Second
exercise: find a metric your service exports about itself, and ask what happens
to it in the failure mode it exists to describe.

### M6-S4 — the release rehearsal: two ways to take a change back, and only one of them is cheap (2026-08-19, role:SRE/MLOps)

**What was built.** `make canary-deploy` (a second InferenceService carrying the
champion's own bytes, plus the dedicated backend Service ADR-011 condition 1
demands), `make canary` (10% → 100% → revert under one continuous load run, the
split read from counters), `make rollback` (the runbook's §4 alias rollback, run
for real in both directions), and `scripts/canary_split_paste.py` so the board and
the record are not two different claims. Runbook §4 flipped from **NOT REHEARSED**
to **REHEARSED 2026-08-19** with a table of measured costs, and gained a §4.5 for
the traffic path.

**The thing worth taking away.** *A system has more than one undo, and they do not
cost the same.* Both rehearsals in this story take a change back. Deleting the
canary Ingress took **0.37 seconds** and cost **zero requests**. Rolling
`@champion` from version 2 to version 1 took **35 seconds of moves and 27.93
seconds of failing requests**. Same cluster, same minute, same operator — a
factor of about seventy-five between them, and nothing in either procedure's
*text* tells you which is which. You find out by running them and holding a
stopwatch, which is the entire argument for rehearsing a runbook rather than
writing one.

The runbook now says **prefer the traffic revert**, and that sentence is worth
more than either measurement on its own: it is the operational conclusion the
numbers license, written where a person under pressure will read it.

**Why the rollback is expensive, and it is not the pod.** Gotcha #80 had already
established that re-deploying a model costs 0.5 s — at one replica
`maxUnavailable` floors to zero, so a surge pod must be ready before the old one
goes. So the natural prediction was that a rollback costs about 0.5 s too. It
does not, because a rollback here is *three* moves and the second one changes
what every client SENDS. The instant `configs/train.yaml: features.version`
becomes `v1`, the wire carries a 5-column matrix while the pod still holds the
24-column model, and MLflow's logged signature refuses it — `HTTP 500`, for as
long as the deploy takes.

And then the asymmetry, which nobody predicted: **rolling FORWARD cost 0.501
seconds and a single 502.** A 24-column request sent to a 5-column model is
tolerated — MLflow takes the columns its signature names and ignores the rest —
while a 5-column request to a 24-column model is missing inputs and is refused.
*Removing features breaks requests in flight; adding features does not.* That is
a fact about MLflow signatures with an immediate operational consequence, and it
suggests a fix (deploy first, move the config line last) which this story
deliberately did **not** adopt: it follows from one measurement, it has never
been run, and M6 sanctions exactly two alias moves. A named remedy is not a
proved one — the same discipline ADR-011 used for `MLSERVER_MODEL_NAME`, which
this story then went and proved.

**The second lesson is about diagnosis under a fresh prior.** The first canary
run moved **0 of 420 requests** — and M6-S3 had just spent a whole story
establishing that a canary moves 0% when it points at a Service some other
Ingress claims. Every instinct said condition 1. It was not condition 1. The
Ingress had been named `nyc-taxi-eta-canary`, which is exactly the name KServe
generates for the InferenceService of that name, so `kubectl apply` wrote the
annotations onto the controller's own object and the controller quietly reverted
them (F-039, gotcha #85). The tell was three requests of three hundred slipping
through at weight 100 — the seconds between the apply and the reconcile.

*The most recent lesson is the most available explanation, and availability is
not evidence.* What actually resolved it was the same habit that resolved M6-S3:
measure the split from a counter rather than from the configuration you just
applied. The discipline was right; the diagnosis it enabled was a different bug
than the one it was learned on.

**The third lesson: a guard that fires when you do the right thing.** `verify-m5`
asserted that the runbook says `NOT REHEARSED`. Rehearsing the rollback — the
whole point of the story — would have turned that check RED for an improvement.
That is gotcha #50 for the fifth time, and the repair is always the same shape:
replace the literal with the property. The section must now *declare its status*,
and a claim of REHEARSED must cite a record this repo holds. The first attempt at
that repair searched the section BODY and reported a rehearsed rollback as
un-rehearsed, because §4 legitimately contains both "REHEARSED 2026-08-19" and a
sentence about an un-rehearsed mitigation. Anchoring on the heading is what
distinguishes a status from a mention.

**What to look at.** `automation/runs/m6-canary/release_drill.json` beside
`automation/runs/m6-canary/attempt1-ingress-name-collision/release_drill.json` —
the same drill, one green and one 0%, and the difference is a name ·
`automation/runs/m6-rollback/alias_rollback.json`, whose per-0.5 s probe log lets
you re-derive the 27.93 s yourself and see the `HTTP 500`s turn into a single
`HTTP 502` · `docs/runbooks/serving.md` §4 and §4.5 as a pair — two undos, priced
· `scripts/canary_release_drill.py`'s `apply_weight`, where the precondition
lives.

**What to try yourself.** Run `make canary DRILL_ARGS=--dry-run` and read the
prediction file before reading any result — then ask which of the seven
predictions you would have got wrong. Then rename the Ingress in
`infra/manifests/canary-ingress.yaml` back to `nyc-taxi-eta-canary` and run
`uv run pytest tests/unit/test_canary_and_rollback.py -q`: the test derives the
forbidden name from the isvc manifest, so it goes red without either name being
typed into it.


### M6-S3 — the spike and the shadow: what "configured" is worth (2026-08-19, role:SRE/MLOps/DA)

**What was built.** A second model on the wire — `make shadow` puts registry
version **1** up as its own InferenceService with zero rider traffic — plus
`make shadow-run` (the dual-send disagreement table, 1,016 stratified rows),
`make canary-spike` (ADR-004's deferred spike, measured), **ADR-011**, and the DA
shadow-analysis memo with a named verdict. The F-009 resolver learned to answer
for a VERSION as well as an alias.

**The thing worth taking away.** *A mechanism that reports itself as configured
is not evidence that it works.* The canary spike's headline is not that
ingress-nginx can split traffic — it can — but HOW it fails when it cannot. Point
a canary Ingress at a Service that some other Ingress also routes to and you get:
the annotation accepted, the object synced, the controller logging `Scheduled for
sync`, the main backend genuinely listing the canary under `alternativeBackends`
— and **zero of two hundred requests moving**, with no error, no warning and no
event anywhere. Every signal a person would naturally check says yes. The only
instrument that says no is a traffic counter.

That is why the §9/M6 acceptance leg says "90/10 **observed from metrics**". This
story found out why that word is in the sentence, and it cost three attempts to
find it: run the probe (0%), re-apply and re-measure (0%), then read
ingress-nginx's own Lua backend table and see `{weight: 0, weightTotal: 0}` on a
backend whose `noServer` was false because KServe's generated Ingress had already
claimed it as an ordinary one.

**The second lesson is about the word "metadata".** To force a controller
reconcile the first probe ran `kubectl annotate isvc` — an annotation, surely the
safest edit there is. KServe copies an InferenceService's annotations onto its pod
template, so it rolled the champion's only predictor. Twice. The probe's own
end-state batch caught it as **174 of 200 requests returning 502**, which is the
one good thing about the story: the check that measured the damage was already
written, because the prediction had been written first. On a resource an operator
templates from, there is no metadata-only field until you have checked what the
operator copies downstream.

**Two predictions were wrong and they are the most useful output.** The first run
predicted a 10% canary would split (it silently did not) and that canary traffic
would 500 at v1's signature. It **404s** — the V2 protocol puts the model name in
the URL path, so the request is refused as an unknown model before any signature
is consulted. The schema wall everyone predicts is real and sits *behind* a wall
nobody mentioned. Both records are kept: the wrong run unedited under
`attempt1-no-dedicated-service/`, the corrected predictions beside them under
`superseded_predictions`.

**And the memo did not say what it was pre-registered to say.** The kickoff
predicted a NO-GO on v1 because v1 is "the known-worse model". The verdict is
still NO-GO, but the margin is thin: **8.61 vs 8.93 MAE**, champion closer on
**54.4%** of rows, airports a dead tie (**5.97 vs 5.99**, with the champion
*behind* on within-five-minutes), and on no-geometry rows the 5-feature model is
closer more often. Writing "no" for the honest reason — the full holdout already
answered on 5.9M rows, and nothing here is a reason to CHANGE — is a different
document from writing "no" because it was expected.

**What to look at.** `automation/runs/m6-spike/canary_spike.json` beside
`attempt1-no-dedicated-service/canary_spike.json` — read the predictions first,
then the phases · `docs/decisions/ADR-011-canary-and-shadow-mechanism.md`, whose
two conditions are the whole deliverable · `docs/shadow_analysis_m6.md` §5, which
argues why a thin margin does not become a reason to ship · gotchas **#81–#84**.

**What to try yourself.** Apply a canary Ingress at weight 50 pointing at
`nyc-taxi-eta-shadow-predictor`, then read
`kubectl -n ingress-nginx exec deploy/ingress-nginx-controller -- curl -s
http://127.0.0.1:10246/configuration/backends`. Find your canary in it and look at
`noServer` and `trafficShapingPolicy`. Now add a dedicated Service and do it
again. The two JSON blobs, side by side, are the entire lesson — and neither
`kubectl get ingress` nor the controller log distinguishes them.

### M6-S2 — judgement: what a number needs before it is allowed to be a threshold (2026-08-19, role:SRE)

**What was built.** `docs/slo_serving.md` (four SLOs, every target carrying its
argument and its instrument) · `infra/monitoring/alerting_rules.yml` (seven rules
across six of the PRR's seven signal ids) · `scripts/render_alert_rules.py`, which
validates them and nests them into the chart's values at deploy time ·
`make alert-fire-drill`, which fired two of them for real with its prediction
written to disk first · and the CPU request moved `200m → 1500m` on the wire with
a before/after measurement either side of it.

**Why this way.** Three decisions, and the third is the one that generalises.

*The threshold has to survive the day it was written.* The kickoff's rule was
"argued from harm and measured headroom, never set equal to the number just
observed", and applying it honestly produced numbers that look wrong until you
read the argument. SLO-L1 is **250 ms** when the service delivers 99.6% inside it
— because the alternative bucket edge, 100 ms, sits at **94.6%** today, i.e. an
SLO in breach on the day it was written. A-2's threshold is **10%** 5xx when the
availability target is 0.1% — because at 4 req/s the longest *healthy* recovery
this program has ever measured is 6.1% of a five-minute window, so a 5% page
fires for a system that healed itself in eighteen seconds. The budget still pays
for those blips; it pays *silently*, which is what a budget is for and what a page
is not.

*One copy of the rules, and a renderer instead of a paste.* The chart wants the
rules nested under a values key; the reviewable form is a plain
`promtool`-shaped file. Rather than keep both, a script parses the file and emits
the nesting — so a malformed rule fails *before* helm reports success over a
Prometheus that quietly loaded nothing. The same script refuses any rule without
an `annotations.why`, which is the mechanical half of the kickoff's discipline: a
number with no reasoning beside it cannot be reviewed, only inherited.

*Predict a sequence, and predict the negatives.* The drill fires two rules with
different sustain windows from ONE injection, so it must get an **order** right
(A-3 at T+150.5 s against a predicted 150; A-2 at T+330.6 s against 330), and it
names the five alerts that must **not** fire and why. A drill that predicts only
"something will fire" is satisfied by almost any behaviour. The negatives are what
make a signature *distinguishable*, which is the property S5's gameday is graded
on — rehearsed here for the price of one injection.

**The concept underneath.** *An instrument's resolution is part of its answer, and
a number reasoned by analogy is not a measurement.* Both halves cost this story
something.

The first: `histogram_quantile(0.95, …)` on the predictor's own histogram reported
**111.6 ms** for a window in which the client — timing the whole round trip, so
strictly *more* — measured **84.4 ms**. A quantile over a superset cannot exceed
one over a subset, so the histogram's answer was not a measurement at all: its
buckets jump `le` 0.1 → 0.25 and this service's tail lives inside that 150 ms gap.
The fix was not a better estimator but a different question — the SLO's number was
chosen to *be* a bucket edge, so the rule counts requests instead of estimating a
percentile. When an instrument disagrees with a stricter one, work out which
disagreement is arithmetically impossible before deciding which number is wrong.

The second: this story wrote "a model re-deploy costs ~15–18 s" into an SLO
document, by analogy with three real measurements (14.53 s a killed pod, 15.0 s an
ingress roll, 18.24 s a stop/start). Three numbers within four seconds of each
other feel like a law. The measured cost of an actual re-deploy is **0.5 s** — one
failed request of 400 — because at one replica `RollingUpdate`'s
`maxUnavailable: 25%` floors to **zero**, so a surge pod must be ready before the
old one is removed, while all three of the "law's" data points destroy the only
pod first. The analogy had generalised over the *outcome* (a pod is replaced) and
ignored the *mechanism* (is the Deployment allowed to have zero available pods?).
That is a 30× error inside a document whose entire job is to hold honest numbers,
and it was found only because the change was measured rather than assumed.

**What to look at.** `docs/slo_serving.md` §2.1 (the impossible quantile, with the
bucket counts) and §4.1 (the wrong prediction, kept above its correction) ·
`infra/monitoring/alerting_rules.yml` — read the `why` and `sustain` annotations,
which are the actual deliverable · `automation/runs/m6-slo/alert-fire-prediction.json`
next to `alert-fire-drill.json`, in that order · `tests/unit/test_slo_and_alerts.py`,
particularly the test asserting the drill watches *every* rule in the file · and
`ledgers/findings.md` F-035 (two PRR signals that cannot be Prometheus rules,
because the fact lives in a client and no client here is scraped) and F-036.

**What to try yourself.** Change A-2's threshold from `0.10` to `0.05`, re-run
`make alert-rules`, and work out from the numbers in §3 whether a single
self-healing pod loss would now page you — the arithmetic is four numbers and it
is the whole argument. Then run
`kubectl get isvc nyc-taxi-eta -o jsonpath='{.metadata.generation} {.status.observedGeneration}'`
and, if they differ, try `kubectl wait --for=condition=Ready` against it with a
20-second timeout: that is F-036 in two commands, and it is the cheapest way to
learn that a wait can be unsatisfiable for reasons that have nothing to do with
health.

### M6-S1 — the eyes, and three things that looked completely fine (2026-08-19, role:SRE)

**What was built.** `make deploy-monitoring` — Prometheus 29.27.0 (v3.14.0) +
Alertmanager + kube-state-metrics + Grafana 10.5.15 (12.3.1) on the existing
cluster, reached through the existing 8081 route by host, with a serving board
provisioned from checked-in JSON. Plus two small instruments that turned out to
matter more than the stack: `make probe-mlserver-metrics` (where are the metrics,
actually?) and `scripts/route_availability_probe.py` (what did that change cost
the route?). And `make monitoring-accept`, which is the part worth reading.

**Why this way.** Three choices, and the third is the one to take away.

*The small chart, not the operator.* `kube-prometheus-stack` is the reflex answer
and it brings ~10 CRDs plus a controller whose whole job is to turn ServiceMonitor
objects into the nine-line scrape config that now sits in a values file. Two costs
made the decision, and neither is aesthetic: CRDs are cluster-scoped state on a
cluster this program is not allowed to rebuild, and the alert rules landing next
story would have become objects **living in the cluster** — when the rule since
M1-S5 has been that what renders is checked in and converged. The heavier chart is
written down as the fallback if the lighter one ever hits its three-attempt wall.

*The port was asked, not read.* The kickoff said the predictor's metrics were
*believed* to be on 8082 and said to probe. KServe stamps its own answer on the
pod — `prometheus.kserve.io/port: "8080"` — and that port returns **404** on this
runtime, while 8082 returns 200 with 24 series. Believing the platform's own
annotation would have produced a target that is permanently down and a board of
empty rectangles. The probe stays in the repo and a test fails if it is deleted,
because a pinned number whose measurement has been thrown away is just a memory.

*The accept check refuses to be a target list.* `up == 1` proves Prometheus can
open a socket. It is exactly as green when the counter it scrapes never moves. So
the check reads the inference counter, **sends one real quote**, waits for a
scrape, and requires the number to move — and then parses **every panel's PromQL
out of the dashboard JSON** and executes it. That is where the session's real
lesson arrived: the first run was GREEN with three panels reporting "0 series",
under a message I had written myself saying that was legal. Three different real
defects were hiding inside that sentence — the ingress metrics Service was never
*discovered* (the chart annotates it with nothing, and discovery keys on exactly
that annotation), `rate(x[1m])` at the chart's 1-minute scrape interval evaluates
to **nothing at all**, and one target was genuinely down behind an rbac-proxy.
Zero series is now a FAILURE.

**The concept underneath.** *Absence renders identically to calm.* An empty panel,
a scrape target that was never created, a rollout that is Pending forever — each
of them presents as a system with nothing wrong with it, and each of them is
measured by an instrument that reports success. The ingress rollout is the purest
version: enabling metrics deadlocked the controller (hostPort + one replica + a
single-node selector means the surge pod can never bind port 80), the new pod sat
Pending for ten minutes, and a 420-second availability probe recorded **840/840
ok** — because the OLD pod was serving perfectly. The zero-outage measurement was
the strongest possible evidence for the wrong conclusion. The question that
catches all of these is the same one #59 asks and #51 generalises: *what positive
artifact would exist if this had actually worked?* For a rollout it is a new pod
**age**. For a metrics pipeline it is a counter that **moved**. For a panel it is
a **series**. None of those is "no error occurred".

**What to look at.** `docs/monitoring_m6.md` §4 (the deadlock, with the probe
output that argued for the wrong conclusion) and §5 (the three zeros) ·
`scripts/monitoring_accept.py`, specifically the comment where the lenient version
used to be · `infra/helm/ingress-nginx/values.yaml`'s `updateStrategy` block,
which states an unavoidable cost rather than a preference · gotchas **#77** and
**#78** · findings **F-033** and **F-034**.

**What to try yourself.** Set `server.global.scrape_interval` back to `1m`,
re-run `make deploy-monitoring` (no restart is needed — the configmap-reload
sidecar picks it up), and watch `make monitoring-accept` go red on exactly the
panels whose windows can no longer hold two samples. Then put it back and, this
time, look at the board in Grafana while it is wrong: the panels do not say
"misconfigured", they say nothing at all, which is the entire point.

---

## M5

### M5-S5 — a rollback is not a pointer move, and a runbook is only as true as the record it quotes (2026-08-19, role:SRE)

**What was built.** `docs/runbooks/serving.md` (deploy · stop · start ·
rollback · a cheapest-causes-first failure table · what the endpoint refuses on
purpose · what is not rehearsed), the **Production Readiness Review** minutes
(`docs/rituals/2026-08-19_prr-m5.md`, four boxes, each carrying pasted
evidence), `make stop-start-drill`, and the M5 gate: **`make verify-m5` GREEN
49/49 sub-checks in 7 sections in 5.8 s**, with `make verify-m5-redteam`
proving it can go RED.

**Why this way.** Three choices worth the words.

*The rollback got argued, not typed from memory — and that is where the story's
finding came from.* The obvious rollback is "move `@champion` to version 1,
re-run `make serve`". Type it out and it does not work: version 2 eats **24**
features, version 1 eats **5**, and the client builds its matrix from
`configs/train.yaml: features.version`. An alias-only rollback gives you a
predictor that loaded a 5-column model while every quote sends 24 — a **500 on
every request from a system whose every condition says `Ready`**, with no
restart, no event and no probe to notice. So the runbook types **three** moves
(pointer, config line, re-deploy), and the config line is *derivable*: every
registry version carries a `feature_set` tag written at promotion time, so you
read which feature set the target eats rather than remembering it. Then the gate
asserts the invariant live — **the served version's `feature_set` tag must equal
`configs/train.yaml: features.version`** — which turns a half-finished rollback
into a RED gate that names the shape. Filed and closed as **F-032**: the finding
is not that something was broken, it is that the one procedure written for the
worst day had a silent second half.

*Stop and start were REHEARSED; the rollback was not, and both facts are stated
where they are used.* Stopping touches one annotation and is exactly undone by
removing it, so it was run: the route stopped answering **3.12 s** after
`serving.kserve.io/stop=true` and answered again **18.24 s** after the
annotation was removed. Two things a written-from-docs runbook would have got
wrong fell out of running it — `spec.replicas` goes **absent**, not `0` (so
"scale it back to 1" is wrong advice, and `kubectl scale` is fought by the
controller), and the restart costs **more** than the 14.53 s a killed pod costs,
because the Deployment's pod is recreated from scratch rather than replaced by a
ReplicaSet already watching. The rollback could not be rehearsed — it moves
`@champion`, and M5 is legislated alias-neutral — so it says **NOT REHEARSED**
in its own section, in §8's list, in the PRR and in the deployments ledger. The
M4-S2 backup precedent: an unrehearsed path says so in every artifact, not in
one footnote.

*The gate checks the PROSE against the records.* Every number the runbook quotes
is compared with the record it cites, and every `make` target it types is
checked against the Makefile. That is the leg that makes a runbook falsifiable:
a renamed target turns an incident procedure into a typo at the worst possible
moment, and a number nobody re-checks becomes a hope within a milestone. It is
also the second witness the red team needs — see below.

**The concept underneath.** *A verification suite should read at least two
artifacts that could disagree.* M4 learned this across systems (the control
plane's cache status vs MLflow's run count). M5 applies it across **kinds** of
artifact: the machine's record, and the prose a human will act on at 3 a.m. The
red team plants one number — `recovery.outage_seconds` **14.53 → 14.251**, taken
from the record's own `error_window.span_s`, i.e. gotcha #75's mistake re-made
and wrong by 0.28 s — and two legs fire: the record no longer reconciles with
its own anchors (`recovered_at − first_error`), and the runbook quotes a number
no record holds. A gate that only re-derived the arithmetic would be checking a
file against itself.

**What to look at.** `docs/runbooks/serving.md` §4 (the three-move rollback and
why step 3 is a raw MLflow call rather than a `make rollback` that would bypass
`registry.promote`'s gate refusal) · `docs/rituals/2026-08-19_prr-m5.md` §0
(what the review could not do, said first: the champion was already serving, and
the ordering bites at M6) and its box 3 (seven named alert signals, each with a
source that exists today and each of which would have caught something that
actually happened in M5) · `docs/verify_m5_transcripts.md`.

**What went wrong, and it is the repo's own lesson landing on me.** The gate's
first run went RED against a perfectly good install: it read KServe's deployment
mode out of `infra/helm/kserve/values.yaml` **with a regex**, and matched the
comment that says *"The chart's default is `deploymentMode: Knative`"*. Prose
sitting where a parser reads it as code — gotchas #53/#60, for the fifth time in
this program — and the fix is that the leg now parses the YAML. Two more:
demanding the runbook contain the record's number **at full precision** failed
on a document sensibly writing `104.2 ms` for a recorded 104.226 (gotcha #42's
rule about precision, applied to prose), and the first fix for THAT accepted a
bare substring — which would have matched `14` inside `14.53` and let the red
team's planted number through. The match is now anchored on both sides.

**What to try yourself.** Run `make verify-m5`, then edit one digit of the p95
in `docs/runbooks/serving.md` and run it again: the gate names the runbook, not
the record. Then put it back and run `make verify-m5-redteam` to watch the same
disagreement arrive from the other direction. If you want the un-rehearsed half
rehearsed, `make stop-start-drill` costs ~20 s of deliberate outage and refuses
to run against a service that is already down.

### M5-S4 — a percentile is a fact about a load shape, and an outage is not the span between two errors (2026-08-19, role:SRE)

**What was built.** `make load` — an open-loop load client, stdlib only, that
drives the declared route at a stated rate for a stated window and records
p50/p95/p99 with the shape beside them. And `make load-drill` — four phases:
preflight, a ramp that *chooses* the headline rate, the headline window with the
container's CPU measured across it, and a self-heal leg that deletes the
predictor pod mid-load. Result: **p50 17.2 / p95 104.2 / p99 107.2 ms at 4 req/s
for 60 s, concurrency 8, zero errors, 1.31 of 2 CPU cores**, and **14.53 seconds
of unavailability** when the pod is destroyed, after which a different pod object
— on a different node — serves the same model version.

**Why this way.** Three choices, and the second and third were bought with a red
run.

*The loop is open.* A closed loop (N threads, each firing when the last returns)
is shorter and measures the wrong thing: the arrival rate becomes a consequence
of the latency, so a slowing server quietly receives less load and the queueing a
real arrival stream would cause never happens. That is **coordinated omission**,
and its p95 is the service time of an unloaded server in a load test's clothes.
Here arrival *k* is due at `t0 + k/rate` regardless, and the headline percentile
is measured from the **scheduled** instant, so a client that falls behind cannot
hide it — the gap between `latency_ms` and `service_ms` *is* the omission, and
the summary prints a NOTE when it opens.

*A rate at the CPU limit is not a capacity number.* The first ramp rule took the
highest step that held its rate with no errors and chose 8 req/s — where the
container ran at 2.003 of its 2 cores, throttled in 601 of ~601 periods. Every
millisecond of that p95 above ~100 belonged to the kernel stopping the process,
not to the service. Worse, it made the kill unreadable: sitting on the limit a
*healthy* pod drops the odd request, so the drill went red on a tail of sporadic
502/503s that had nothing to do with the kill.

*An outage is not `last_error - first_error`.* The same red run reported a
182-second outage. The service was unavailable for **13 seconds** and then served
1,400 more requests while dropping about ten, one at a time. Both quantities are
real; folding them together produces a number that never happened and would have
gone straight into a runbook.

**The concept underneath.** *Measure the quantity you will quote.* Both defects
here were the same species as gotcha #63 (a cache drill measured on the wrong
clock called a 98.7% saving a failure) and the fix was the same species too — the
right quantity, never a looser threshold. The tell is to finish the sentence the
number will appear in. "The endpoint sustains 8 req/s at p95 237 ms" is false the
moment you know 8 req/s is the throttle ceiling. "The outage was 182 seconds" is
false the moment you know the service answered 1,400 requests during it. A number
that cannot survive its own sentence being read aloud is not measured yet.

The second concept is **the control you already have**. The drill reports the
residual error rate after recovery against the pre-kill segment of the *same run*
— same client, same rate, same minute. It applies no threshold to it, deliberately:
an error-rate objective is an SLO, the SLO document is M6's by the kickoff's own
scope list, and an executor inventing one mid-drill would be setting a bar from
the number it had just seen.

**What to look at.** `src/taxi_mlops/serving/load.py` (the open loop and why the
bodies are encoded before the clock starts) · `scripts/serving_load_drill.py`,
`choose_headline_rate` and `measure_recovery` — both extracted so they are pure
and testable, and both carrying the run that made them necessary in their
docstrings · `docs/serving_load_m5.md` §5, the red run, kept unedited at
`automation/runs/m5-load/attempt1-at-the-ceiling/` · `tests/unit/test_load.py`,
where attempt 1's timeline is a fixture that fails if the naive span ever comes
back.

**What to try yourself.** Run `make load-drill DRILL_ARGS="--ramp 5,10
--ramp-seconds 6 --seconds 10 --skip-selfheal --out /tmp/probe"` — forty seconds,
no pod killed. Then look at `/tmp/probe/ramp.json` and ask what the same numbers
would have looked like from a closed loop. Then, in `load.py`, change `scheduled
= index / rate` to `scheduled = time.perf_counter() - t0` and run the unit
suite: one test fails, by name, and it is the one that could not have been
written behaviourally.

### M5-S3 — the number was zero, and the test found a door nobody could walk through (2026-08-19, role:MLE)

**What was built.** `make parity` and `make parity-redteam`. Parity builds one
16-row feature matrix through the ONE `features/` path and scores it twice — by
the champion loaded out of the registry into this process, and by the deployed
InferenceService — then prints every row's delta and asserts the max is within
1e-6 minutes. The measured max is **0.000e+00**: identical, to every bit a
float64 holds, on all sixteen rows.

**Why this way.** Three choices are worth the reader's time.

*One matrix, scored twice.* The alternative is to build features on each side and
compare, which sounds more end-to-end and is worse: when the numbers disagree you
cannot tell whether the model differs or the feature build does, and when they
agree you have proved neither cleanly. Sharing the matrix makes the delta
attributable — model bytes, runtime, wire — and it makes the claim precise enough
to state what it does *not* cover (M7's transformer, which will build features in
the pod and needs its own measurement).

*The rows are declared, not sampled.* Sixteen hazards, each committed with the
reason it is in the set: airports, the 100–120 minute tail, the cyclical
encodings' seams, an OD pair that appears six times in test and never in train,
passenger counts at both edges, a 2026 date. Random sampling gives a number that
changes every run and a red team with nothing to plant a cause in — and the rows
that break serving are never the average ones. This story is the proof: the
hazard that mattered was one nobody would have sampled.

*The red team plants its cause inside the test.* Every earlier drill here mutates
something — an alias, a record, a library file. The obvious lever for parity is to
point the endpoint at a different model, and that would mean breaking production
to prove a test works. Both arms stay client-side, and the drill re-runs the real
test at the end to prove it left nothing behind.

**The concept underneath: a test's job is to send the requests nobody sends.**
Building the hazard set found **F-030** — since the endpoint existed, every
request whose pickup or dropoff zone had no centroid came back `HTTP 422`. Zones
264/265 are TLC's "Unknown"; they have no geometry by design, so nine features
are NaN, which is exactly what the model was fitted on. But `json.dumps` writes
NaN as the bare token `NaN` — Python emits it by default, and it is not JSON. The
endpoint's answer was `{"loc":["body",1241],"error":"unexpected character"}`: a
byte offset, naming neither the feature nor the zone nor the word NaN. That is
about 1% of all trips, and 264→264 is the single most common OD pair in the data.
It stayed invisible because every earlier client handed a DataFrame straight to
LightGBM, where NaN is ordinary, and because the one accept-check row M5-S2 sent
had full geometry.

**And the second concept: a drill that goes green under its own tampering has
found something.** The red team's first arm rotated the ORDER of the request's
inputs, on a property the client's own docstring had asserted for a milestone —
that a V2 payload is positional. It measured 0.000e+00. The two tempting readings
are "the tampering was too weak" and "the test is broken"; both are wrong. The
documented property was false: mlserver hands MLflow a *named* frame and the
logged signature reorders it. So the plant moved to a cause this runtime can
express (every feature carrying its neighbour's values → 42 minutes of skew), and
the false claim was **corrected rather than deleted**, because the practice it
prescribed — send the model's own column order — is still right for reasons that
survive it. What changed is what we believe is protecting us, and the answer is
the logged signature: the same signature that at M5-S2 refused a lossy
`float64 → int32` cast. Twice in one milestone, a thing logged at training time
caught what nothing at serving time would have.

**What to look at.** `src/taxi_mlops/serving/parity.py` (the `HAZARDS` table is
the most readable part of this story); `client._wire_values` for F-030's fix and
why an infinity is refused where a NaN is encoded; `scripts/parity_redteam.sh`'s
header for what a drill must not do; `docs/parity_m5.md` §3 and §4.

**What to try yourself.** Run `make quote QUOTE_ARGS="--pu 264 --do 264"`, then
`git stash` the `_wire_values` change and run it again — the 422 is the whole
finding in one command. Then run `make parity-redteam` and read arm A's table:
every input in that request is individually valid, and a 48-minute trip is quoted
at 6 minutes. That is what train/serve skew looks like when nothing goes red.

### M5-S2 — the champion answers, and three of the four defects were about what "ready" means (2026-08-19, role:MLOps)

**What was built.** The first model this program has ever served. `make serve`
resolves `models:/nyc-taxi-eta@champion`, hands KServe the S3 prefix it resolves
to, and stands up one InferenceService behind M5-S1's route; `make quote` asks it
for a number through the same `features/` path the trainer used. Two ledger rows
closed with it: **F-009** (the alias URI that will not load) and **F-019** (the
champion could not answer any request dated outside 2019).

**Why this way.** Three choices are worth the ink.

*The alias is resolved at deploy time and the S3 path is never committed.* The
InferenceService in git carries a placeholder that is deliberately not a valid
URI, so an accidental `kubectl apply -f` fails instead of half-working. The
reason is F-022's reasoning one layer down: `@champion` is a pointer DESIGNED to
move, so a committed artifact path is a second address for it that nothing keeps
in step — and the day the alias moves, that file would still apply cleanly and
serve the model that used to be champion, with no error anywhere.

*F-019 was decided as BOTH halves, and the argument for each is that the other is
insufficient.* Extending the holiday table to 2030 fixes today and moves the wall;
typing the boundary fixes the wall and, alone, would refuse every real request.
The harder call was inside the second half — refuse, or degrade-and-flag? They
differ in KIND. Degrading returns a wrong quote: the caller gets a number, the
rider gets a time, and nothing in the system knows the holiday flags were
invented. Refusing is a countable, alertable failure confined to dates nobody has
entered, with its remedy in the error text. A quote-time ETA has one job, and a
silently wrong number is worse than none.

*The predictor image is derived, and the decision was made by a `docker run`.*
KServe pins `seldonio/mlserver:1.7.1-mlflow`; that image has no `lightgbm`, so it
cannot load a LightGBM-flavoured MLflow model at all. One container, thirty
seconds, before a single manifest existed — the M4-S4 cheap-probe lesson arriving
a milestone later and saving the same hour.

**The concept underneath.** *"Ready" is a property of some object, and it is
almost never the object you mean.* Three of this story's four defects were that
sentence in different clothes. `kubectl wait --for=condition=Ready
inferenceservice` returned in milliseconds on a re-deploy — truthfully, because
the InferenceService WAS ready: the old predictor was still serving while the new
one sat at `Init:0/1`. The accept check then interrogated the pod being replaced
and printed a pass, and only luck of subject matter exposed it (the change under
test was a version stamp, so the predecessor said `(unversioned)` instead of
`2`). A 403 on `HeadBucket` said "Forbidden" about a user that existed under a
policy literally named `readonly` — the policy was ready, it just lacked
`s3:ListBucket`. And MLflow answered 500 on a payload that was numerically
correct, because the signature the model was LOGGED with refuses `float64 ->
int32` as lossy — the model was ready, the wire was lying about types. In every
case the signal was true and about the wrong thing. This is #59 and #65's family,
and the question that catches all three is: **could this be true right now for a
reason that has nothing to do with my change?**

The corollary is why the accept check is a PREDICTION and not a health probe. A
ready pod, a 200 on `/v2/health/ready`, and a resolvable route are all true of a
deployment serving the wrong model. Only a number is about the champion.

**What to look at.** `docs/champion_on_the_wire_m5.md` §3 (F-009's two hops, and
why the empty prefix would have SUCCEEDED) and §7 (the four defects, ranked by
how quietly they failed) · `scripts/resolve_champion_storage.py` — one file, and
the whole reason the alias stays the only address · `infra/helm/minio/values.yaml`
`policies:` — the custom policy is stricter than the built-in it replaces, which
is what makes it a fix rather than a workaround · `docker/serving.Dockerfile`,
whose comments carry the probe output that justified it · gotcha **#71**.

**What to try yourself.** Send the endpoint an `FP64` payload by hand and read
the 500 — it names the column and the cast, and it is the signature doing its
job. Then run `make quote QUOTE_ARGS="--at 2031-01-01T09:00:00"` and notice that
the refusal tells you the exact command that fixes it; compare that with what a
degrade-and-flag design would have printed, which is nothing at all. Finally,
`kubectl -n serving delete pod -l serving.kserve.io/inferenceservice=nyc-taxi-eta`
and re-run `make quote` in a loop — that is M5-S4's drill in miniature, and the
first thing you will want is a wait that is about the right object.

### M5-S1 — the evidence entered review, and the accept check went red over a healthy install (2026-08-19, role:MLOps)

**What was built.** Two halves. (1) **F-029's mechanics**: `automation/runs/**/*.json`
is now tracked — 32 records, the evidence base that `verify-m3` and `verify-m4`
REPLAY — while logs and `.status` stay ignored; the four stale "gitignored"
statements were corrected at their source and both gates plus both red teams were
re-run green over the moved files. (2) **the serving platform**: `make deploy-serving`
installs ingress-nginx behind the declared route (host 8081), cert-manager, and
KServe v0.20.0 in Standard/RawDeployment mode. It installs **no model**.

**Why this way.** The gitignore change is three lines and none of them is a
preference. A bare `automation/runs/` exclusion makes git **stop descending into the
directory**, which means a `!automation/runs/**/*.json` rule underneath it is not
overridden — it is never consulted at all. So the exclusion must be pattern-based,
the directories re-included so the walk continues, and the files re-included last.
This is the sort of thing you verify with `git check-ignore -v` in both directions
rather than by reading a diff and nodding.

The serving route needed a similar unglamorous care. kind published
`containerPort 80 -> hostPort 8081` on the control-plane node at cluster CREATE, and
that is only half a route: something has to BIND port 80 **on that node**. Hence
hostPort plus a hostname nodeSelector plus a toleration for the control-plane taint —
and each of those three, missing, produces a different unhelpful symptom. Missing
toleration: Pending forever, with a message about taints. Missing nodeSelector: a
controller on a worker, answering nothing, looking *exactly* like a KServe failure.
The node name is derived from the kind config's cluster name and the values file is
asserted against it, so a rename fails at deploy time instead of at minute forty.

**The concept underneath.** *A positive artifact is only a discriminator if the thing
actually emits it.* Gotcha #59 taught this program to stop asserting on the absence of
an error and to assert instead on the artifact a component exists to produce. The
accept check here did exactly that — it demanded a `Server: nginx` response header
rather than merely "no connection error" — and it went **RED over a perfectly good
install**, because modern ingress-nginx suppresses that header on purpose. Structurally
right, factually wrong. #59 tells you to pick an artifact; it does not tell you to
check that the artifact exists, and the way to find out is to ask the server rather
than to remember: `GET /healthz` returns 200 and `GET /nginx-health` returns 404 — the
same shape M4-S2 found for Flyte, where the path everyone types (`/healthcheck`) is
the one that 404s. Filed as gotcha #70.

The half-1 lesson is narrower and worth keeping separate from the satisfying version
of it. Tracking the records does **not** make them true. It makes a tampered record a
**diff**. What used to stand between a rewritten number and a green gate was only that
nobody rewrote it; what stands there now is that somebody would see. That is a real
improvement and it is not verification, and the distinction is the whole finding.

**What to look at.** `.gitignore`'s last block (three lines, one mechanism) ·
`scripts/deploy_serving.sh` — the derived route at the top, the DRY_RUN branch that
exits rather than falling through, and the two-part accept check at the bottom ·
`infra/helm/ingress-nginx/values.yaml`, where every override names the thing about
THIS cluster that forced it · `tests/unit/test_deploy_serving.py`, and in particular
`code_only()`: two of its tests would have tripped on the script's own prose, which is
gotchas #53/#68 arriving for the fourth time · `docs/serving_m5.md`.

**What to try yourself.** Run `git check-ignore -v` on a record and on a log and watch
them match different lines. Then run `make verify-m4-redteam` and, the moment it
finishes, run `git status` — the emptiness is the new property, and it did not exist
last week. Finally, `curl -sS -D - http://localhost:8081/` and ask yourself what in
that response would let you tell OUR controller from any other nginx on the machine.
The answer is: nothing in it. That is why the check asks a second question.

---

## M4

### M4-S5 (third session) — the gate that closes M4, and the ground it found soft underneath (2026-08-19, role:MLOps A / SRE R)

**What was built.** `make verify-m4` — 39 sub-checks in 7 sections, running in
seconds — and `make verify-m4-redteam`, which proves it can say no. Plus
`tests/unit/test_verify_m4.py` (19 tests on the gate itself), `DEFAULT_EXPERIMENT`
extracted in `pipelines/tasks.py`, and **F-029**, which is what the story found
while deciding what the gate was allowed to depend on.

**Why this way.** M3's gate-writing law was *re-fits nothing*. M4's had to be
stronger — *re-runs nothing* — for a reason that only becomes visible once you know
how the cache drill works. M4's evidence cost ~95 minutes on-cluster, so re-running
it would cost more than the milestone; but worse, **a re-run would mint MLflow runs,
and the count of MLflow runs is the strongest thing the cache leg checks**. The
control plane's `cache_status` is a claim; the clock corroborates it weakly; MLflow
is the witness that could catch a lie, because a re-executed fit *has* to log. A gate
that launched a pipeline would be adding runs to the very counter it reads. That is
not a performance argument, it is a correctness one.

The second decision was what to check the alias law with. "Is `@champion` still
version 2?" is satisfiable by not looking, and it pins a literal that a legitimate
future promotion turns red (the mistake `verify-m2` made and gotcha #50 records). So
§7 asks the strong form instead: **none of the 28 runs the M4 pipeline fitted is a
registry version.** A promotion cannot hide from that — it must create a version, and
a version carries the run that made it. The law stops being a habit somebody follows
and becomes a question the registry answers.

**The concept underneath.** *Ask of any verifier the question you would ask of the
thing it verifies: could it tell if it were wrong?* This program has been asking that
of components since gotcha #51. This story pointed it at a gate's **inputs** for the
first time — and the answer was uncomfortable. `automation/runs/` is gitignored, so
`verify-m3`'s bake-off replay and every record `verify-m4` reads are machine state.
An edit to one of them — *precisely the fault both red teams simulate* — leaves no
diff for a reviewer to see. Two artifacts had already written the false version down:
`verify_m3.sh`'s header listed "committed JSON" among its inputs, and its own red team
advised `git checkout --` on a file git has never heard of. That second one is the
tell, because a mistyped word is an accident and a recovery procedure is a belief.
The false statements were corrected the same day; the policy question — what belongs
under review — was routed to ARCH with three costed options rather than decided by
the session that happened to notice it.

The corollary showed up twice more in one afternoon, in the smaller register: a
checker that demanded every recorded run have a parent action went red on the retry
probe, which is *built* to have neither a parent nor a success (#67), and its tests
went red for matching the word `make pipeline` inside the gate's own advice to a
human (#68). Both were fixed by changing what the check *means* rather than what it
*excludes* — derive the class, match the command position — which is the same move
as #52 and is worth more than either individual bug.

**What to look at.** `scripts/verify_m4.sh` §4's last check (the two witnesses, and
why agreeing is stronger than either passing) and §7's third (the 28 runs) ·
`scripts/verify_m4_redteam.sh` — read what it *leaves alone*, which is what makes the
lie plausible · `docs/verify_m4_transcripts.md` for both runs verbatim ·
`ledgers/findings.md` F-029, particularly the three options and their honest costs ·
`docs/pipeline_m4_leg3.md` §17–§21.

**What to try yourself.** Run `make verify-m4-redteam` and watch which two checks
fire. Then edit the record by hand the other way — set run 2's `train` duration to
`1935159` while leaving `cache_status` at `CACHE_HIT` — and see that the gate catches
*that* too, from a different direction, before restoring with
`cp` from the backup the drill keeps. Finally run
`git check-ignore -v automation/runs/m4-cache/cache_drill.json` and sit with the
answer for a moment: you have just been reading a gate's entire evidence base, and it
is not in the repository.

### M4-S5 (second session) — one body of SQL, two transports, and a debt closed by measuring both options (2026-08-18, role:MLOps A / MLE R, DA hat for the mart decision)

**What was built.** `publish_marts`, the pipeline's seventh stage: rebuild the
analyst layer → `dbt build` → publish the gold marts into the one Postgres, from
inside a task pod. Plus `scripts/marts_publish.py`, which is the publish itself
extracted out of `scripts/marts.sh` so that both callers share it; a fourth staged
data tree; a fourth consumer of the `marts` database role; and `make marts-peak`,
the probe that made D-003 a decision instead of an opinion.

**Why this way.** The forcing constraint is a transport. `make marts` publishes over
`kubectl exec` — not out of laziness but because nothing of ours publishes 5432 on
the host, so the host has *no TCP route to the database at all*. A task pod has the
opposite problem: it can reach `postgres.platform.svc.cluster.local` easily and has
neither kubectl nor a kubeconfig. Two publishers, two routes, and exactly one thing
that must not be duplicated: the swap SQL, which is the statement that decides what a
board renders. So the module is transport-blind below a four-method `Transport`
protocol, and the mart list, the dbt `--vars` payload and `--no-partial-parse` moved
with it — `marts.sh` no longer has a `MARTS=(...)` array and a test fails if one comes
back. The CSV producer is a *subprocess* on both sides rather than an import, which
sounds like a compromise and is actually the point: `marts_export.py` was already
unit-tested and already streamed, and a second in-process path would have been a
second exporter.

**The decision, and why it is a split.** D-003 asked for an incremental
materialisation *or* a recorded decision that full refresh stays, with the peak
re-measured. The temptation is to pick one and defend it. What the measurement said
is that the question was mis-shaped: the marts are not one kind of object. Four of
them are ~46,000 rows and a full refresh costs under a second while buying the
strongest property a publish can have — the mart *is* the source, drift impossible.
The fifth is 56M rows and 13 GiB and is the entire peak. So the aggregates stay full
refresh forever and only `trips_clean` became month-scoped. Measured: **228.2 s /
27.96 GiB peak** against **82.7 s / 15.33 GiB** — and M1-S4's remembered "~23 GB"
turned out optimistic, because `error_segments` joined the marts two milestones later.

**The concept underneath.** *An optimisation's cost is a different quantity from the
one it improves, and you have to name both or you have not measured anything.* The
scoped publish lowers the PEAK by 45% and raises the STEADY STATE by 1.85 GiB, because
a `DELETE` of 7.75M rows is space the table holds until autovacuum reclaims it. Both
numbers came out of the same probe and only one of them is flattering. Worse, the
scoped path gives up a property the full refresh had for free: it can leave a month
behind, and a mart that is quietly short answers every query happily and just returns
fewer rows. That is M1-S2's catalogue lesson arriving one layer downstream, and the
answer is the same one: a reconciliation that runs every time and refuses. The check
is not a nicety bolted on afterwards — it is the *price* of the decision, and if you
would not pay it you should not make the trade.

**The instrument lesson, again.** The run that proved the tail also produced a
surprise: five cached stages came back `CACHE_POPULATED` rather than `CACHE_HIT`, on a
month they had each been populated for, with the same data pin and untouched function
bodies. The cause is that the image tag is the git short sha, so every commit mints a
new image and the image is part of the task spec Flyte keys on (gotcha #66). It is
arguably correct — it agrees with F-026 from the other side, since the image is where
the model code comes from — but nobody had priced it: one commit under `src/` turns
the next full-data run back into a 31-minute fit. And the same run exposed a much
smaller version of the same disease in our own transcript: the runner had been
printing "six stages on-cluster" after the graph grew a seventh, and nobody noticed,
because nothing reads a summary line for information. It now derives the count from
`pipelines.tasks.STAGES`.

**What to look at.** `scripts/marts_publish.py` — read `publish`'s docstring first,
it is D-003's decision with its numbers · `docs/pipeline_m4.md` §16, especially §16.2
(the costs) and §16.7 (the cache surprise) · `tests/unit/test_marts_publish.py`, which
drives the whole publish against a two-row DuckDB file and a recording transport, no
cluster · the four assertions in `tests/unit/test_flyte_task_wiring.py` that were
replaced by properties this session, and what each one used to encode.

**What to try yourself.** Run `make marts-peak MARTS_MONTHS=2019-04` and then
`make marts-peak` back-to-back and watch the `marts_db_end_gib` numbers diverge —
that is the steady-state cost, and it is invisible in any single run. Then delete one
month's rows from `marts.trips_clean` by hand and re-run a scoped publish for a
*different* month: the reconciliation is what stops you shipping the hole.

### M4-S5 (first session) — the drill was wrong three times, and each wrong was about the instrument (2026-08-18, role:MLOps A / MLE R, SRE hat)

**What was built.** `make pipeline-kill-drill`: delete the pod a stage is running
in, mid-work, and prove the pipeline finishes anyway. Plus the retry budget it
spends (`retries=2` on every stage, `0` on the parent), a probe that measures that
budget on its own, and F-027 — a reader that had been answering `attempts: 0` for
every run this program ever inspected.

**Why this way.** The drill is a GAMEDAY, so it writes its predicted signature to
disk **before** it kills anything, and a test pins that ordering positionally
rather than by presence. That discipline is the whole reason this session produced
knowledge instead of a green tick: the first prediction said the retry would show
up as a pod named `…-1`, and what actually happened is that the k8s plugin
recreated the pod **under the same name with a new UID**. The pipeline had
survived perfectly and the drill reported 6/7. Had the expectation been formed
after the observation, the "finding" would have been "it works".

**The concept underneath: when a check goes red, ask what it is measuring before
you touch it.** The wrong fix was available and easy — accept `…-0` as well as
`…-1`. The right one was a different PROPERTY: **identity, not name**. A different
pod object ran the stage; that is true whether the platform bumps the attempt or
recreates it, and it is asserted by reading the UID before the kill.

**And the deeper one: a drill can pass while measuring something other than what
it claims.** Chasing the same thread showed the control plane recorded the killed
action at *one attempt* — so a deleted pod is survived by **recreation**, which
never spends the `retries=2` this session had just declared everywhere. The
budget had never been observed doing anything. Hence `pipelines/flyte/
retry_probe.py`: one task that always raises, carrying the same budget **by
import** so it measures the number the repo declares rather than one it restates.
It settles at attempt index 3 and the run FAILS — real *and* finite, which is the
argument for the number being small.

**Three defects, all in instruments, none in the pipeline.** The runner buffered
`flyte run --follow` into a shell variable, so the run's name did not exist until
the run was over (the drill polled an empty file). `--follow` returns when the
FIRST attempt's log stream ends, so the probe read `RUNNING` as a final answer
(#65). And `getattr(status, "attempt", 0)` on a protobuf returns the **default**
for a field that does not exist — the field is `attempts` — so a reader reported
zero retries for everything, forever, and zero is exactly what an un-retried
action should say (#64, F-027). The pipeline was fine every time.

**What to look at.** `automation/runs/m4-kill/attempt1-prediction-wrong/` — a
prediction kept beside its refutation, which is the artifact this whole practice
exists to produce · `scripts/pipeline_kill_drill.sh`, phase 0 and the UID
comparison · `docs/pipeline_m4.md` §13 · the F-027 test, which pins the reader
against `ActionStatus.DESCRIPTOR` rather than against the string `"attempts"`,
because a literal test goes green on the next typo in the next field.

**What to try yourself.** Run the drill against a month it has already seen: it
refuses, because a cached stage runs in no pod and there would be nothing to kill.
Then set `retries` to 0 in `pipelines/flyte/workflows.py` and run phase 0 alone —
the probe should say the declared budget is not what the platform honours, which is
the check proving it can fail. Finally, `grep -n attempts automation/runs/m4-cache/
cache_drill.json` and notice that every one of them is a default.

### M4-S4 (second session) — the cache, and three defects the cheap probe found before the expensive run did (2026-08-18, role:MLOps A / MLE R)

**What was built.** The pipeline's second leg: `make pipeline-cache-drill`, which
runs the same on-cluster invocation twice and proves the rerun reused the first
run; `flyte.Cache` on the five deterministic stages with a salt derived from the
DVC pins; and `scripts/flyte_run_actions.py`, a reader that asks the control plane
what it recorded for every action of a run. Plus the finding the checking turned
up (F-026: a task pod's `src/taxi_mlops` comes from the IMAGE, not the code
bundle) and its guard.

**Why this way.** Three ideas, and the first is the one worth carrying anywhere.

*A cache key describes what you declare, not what you read.* Every stage here
declares a month string or a row count and then reads 1.8 GB off a mounted
volume. Flyte cannot see that volume, so the cache's honest failure mode is not a
stale model — it is a stale model **with a green transcript**, which is strictly
worse than a crash. The fix is to put the data into the key: `data/*.dvc` is a
content hash of each tracked tree, it is committed, and only `make data` changes
it. Whenever you cache anything, write down the inputs the key does NOT cover,
and then go and cover them.

*Ask a different system.* The drill's headline evidence is `cache_status:
CACHE_HIT`, straight from the control plane. But the leg that could actually
catch a lie is MLflow's run count: a re-executed train stage MINTS A RUN, so if
the fit secretly re-ran, a database that has never heard of Flyte would say so.
Evidence that comes from the same system making the claim is a restatement of the
claim.

*Two stages refuse a cache, and the refusals are more interesting than the
cache.* `register` reads the live registry — a cached answer to "what is serving
right now?" is wrong exactly when the alias has moved, which is the only time
anyone asks. It costs 3.7 seconds against a 31-minute fit, so this is the rare
case where correct is also nearly free. And `main` stays uncached so the rerun's
evidence stays per-stage: a cached parent would return in one action and prove
nothing about the five stages under it.

**The concept underneath: put the cheap check in front of the expensive one.**
The full drill costs ~35 minutes. `DRILL_STAGE=ingest` runs one stage twice for
~40 seconds, and it found three real defects before the expensive run ever
started — a shell-quoting bug that reported itself five lines away (gotcha #62),
a threshold measured on the wrong clock (#63), and a drill that would have gone
red comparing two reruns to each other. None of the three was about caching. That
is the usual yield of a cheap probe: it does not find the hard bug you feared, it
finds the four ordinary ones standing in front of it. `make flyte-hello` is the
same idea one layer down.

**What to look at.** `pipelines/flyte/workflows.py` — `_data_pin()` beside
`_image_ref()`, the same "this module is imported in two places and only one has
the file" problem solved the same way twice · `scripts/pipeline_cache_drill.sh`,
the three-legged verdict block and the two-clocks note · `docs/pipeline_m4.md`
§9–§11 · `tests/unit/test_flyte_task_wiring.py`, where the cache decisions are
pinned by parsing the AST rather than the prose (the file argues its design at
length; a grep for "cache" would pass on the argument and never read the
decorator).

**What to try yourself.** Run `DRILL_STAGE=ingest make pipeline-cache-drill`
twice in a row and watch the second one refuse to be green — it is comparing two
reruns and says so. Then edit one line inside a cached stage's body and run it
again: the function-body hash changes, the key changes, and the stage executes.
Finally, add a `print()` to `pipelines/tasks.py` and run `make pipeline` — nothing
happens on the pod, because that file arrives in the image, which is F-026 in one
command.

### M4-S4 — the split horizon had a lever, and four of five defects were in the checkers (2026-08-18, role:MLOps A / MLE R)

**What was built.** The project's own pipeline running on the cluster:
`pipelines/flyte/workflows.py` (the six M4-S1 callables as Flyte tasks, three
`TaskEnvironment`s so the fit gets 24Gi and a verdict-reader does not),
`make pipeline MONTH=…`, `make stage-data` (1.8G of DVC-pinned data onto a PVC),
and the object that ties it together — `infra/manifests/flyte-task-podtemplate.yaml`,
"what a task pod in this program looks like". **F-023 closed** (M4-S2's wall),
**F-025 found and closed**, and `tracking.configure` stopped requiring a `.env`
that a task image must never contain.

**The bug worth the session.** `make pipeline` printed
`ok  run … completed; six stages on-cluster` over a run that had died on
`ErrImagePull` before a single stage started. Nothing was faked: `flyte run
--follow` **exits 0 when the run it followed FAILED**, the run name parsed fine,
and `flyte get io` returned a perfectly readable blob. The only thing that
differed from a real success was the CONTENT of that blob —
`ActionOutputs(o0=None)`, because a failed workflow returns nothing. The fix was
not a better error check but a POSITIVE one: the run's output must carry the
`"decision"` the pipeline exists to produce. It then caught the next three
failures on sight instead of painting them green.

**The concept underneath.** *A check written against the absence of an error can
only be as honest as the thing reporting errors.* Exit codes, phase strings and
"did it throw?" are all second-hand accounts of success; the artifact is
first-hand. This is gotcha #51's question — *could this component tell if it were
false?* — asked of a checker that was minutes old, and it is the fourth time this
program has paid for it (#50 the guard that fires when things are right, #54 the
backup verifier that could not see the truncation it named, #55/#56 the verifiers
that failed for their own reasons and blamed the artifact). The pattern has a
tell: when a checker's inputs are all *about* the work rather than *of* it.

**The other half: a wall can be right about the disease and wrong about the
cure.** F-023's diagnosis — one MinIO, two names — was exactly correct, and its
recorded probe 2 ("point both sides at the node's docker-bridge address, the one
name both can resolve") turned out to have no answer on this machine: from WSL the
node IPs return 000, even for the apiserver, because Docker Desktop publishes
kubectl's route on loopback instead. A session following the plan would have spent
its budget disproving it. What paid was probe 1 — *ask what the server actually
hands the client* — which found that the client never builds an upload URL at all,
it PUTs to a `signed_url` the server mints. That single fact explained the
symptom, explained why M4-S2's client-side variables could not have worked, and
named the fix (`storage.signedUrl.stowConfigOverride`, absent from the 2.x chart,
present in the 2.x binary). **Read the mechanism before trying the remedies.**

**What to look at.** `infra/manifests/flyte-task-podtemplate.yaml` — its header is
the whole design, including why three existing storage configurations all missed
the process that runs our code (it fell through to the EC2 metadata address) ·
`infra/manifests/flyte-task-data-pvc.yaml` for the data decision AND the named
option that was rejected · `docs/pipeline_m4.md` §6 for all five defects ·
`tests/unit/test_flyte_task_wiring.py`, which asserts the two halves of the split
horizon **against each other** rather than by literal value — they exist because
they must differ · gotchas #59/#60/#61.

**What to try yourself.** Break one twin and watch which layer notices: change
`FLYTE_AWS_ENDPOINT` in the PodTemplate to `localhost:9000` and run the pipeline —
the task will run to completion and then fail writing its output, which is the
shape every "it worked and then it didn't" bug in this milestone had. Then set
`serverAllowedHosts` to bare hostnames and try `curl localhost:5000/api/2.0/mlflow/experiments/search`
against `curl -H 'Host: localhost' 127.0.0.1:5000/health` — two commands that
disagree are how the port-in-the-header rule was found.

### M4-S3 — the image was plausible, and the tests inside it were what made it real (2026-08-18, role:MLOps)

**What was built.** The task image the pipeline will run in from M4-S4 on:
`docker/Dockerfile.pipeline` (python 3.12.14 pinned by tag AND digest, `uv sync
--frozen` off the committed lock, `libgomp1` as a real package, non-root),
`make image-load` (build → `kind load` → read back off every node with the nodes'
own `crictl`), `make image-smoke` (10 checks, all inside the container), and
`make image-smoke-redteam` (the drill that proves those checks can go red). Two
debt rows closed with evidence — **D-001** (how images reach the nodes) and
**D-004** (the OpenMP shim must be dead in the image) — and one new finding,
**F-024**, found by the drill.

**Why this way.** The interesting decisions are all about *what counts as
evidence*.

D-004 does not ask for `apt-get install libgomp1`. It asks for proof that the
image's OpenMP is the system's, and that is a subtler thing, because **the
borrowed one works**. On this laptop `taxi_mlops.training.openmp` symlinks the
copy scikit-learn's wheel vendors and re-execs, and everything trains fine. If
the image had quietly kept doing that, every number would still be right and the
debt would never close — it would just stop being visible. The only externally
observable difference is one line on stdout. So the closing evidence is
*negative*: no `[openmp]` announcement, and no `/app/.venv/lib/openmp` directory,
in an image where both wheels still ship a `libgomp` the shim could borrow.

Negative evidence is worthless unless you can make it flip, which is why the
drill exists. It bind-mounts an **empty file** over the system library in ONE
`--rm` container — nothing else touched, the image and the three nodes and the
cluster all untouched, the same "break the pointer, never the state" shape as
`verify-m2-redteam` deleting an alias. Inside that one container the world looks
exactly as it looks on this host, and all three checks flip. Its exit code is
inverted like `make marts-redteam`'s: a check that stays GREEN under the mask is a
check that measures nothing, and the script says so.

D-001 went the other way — a decision the constraints had already made. The
local-registry pattern is genuinely better, and it needs
`containerdConfigPatches` in the kind config, and the kind config is read only at
cluster-create. This cluster holds the only copy of the MLflow registry. So the
decision note records the better option, its cost, and the *event* it lands at
(the next PO-sanctioned rebuild) with the *trigger* that will make it worth doing
(image churn). "Deferred with a date and a reason" is a different artifact from
"we picked the easy one".

**The concept underneath: an artifact you have read is not an artifact you have
run.** The Dockerfile was correct on every line I could reason about, and the
image it produced could not build a feature — because `.dockerignore` excluded
`data/` wholesale, and 1.1 MB of what lives under `data/` is *committed* lookup
tables (zone centroids, the TLC lookup, the pinned shapefile, the holiday table)
rather than anything DVC pins. Twenty-eight tests failed and ten errored the
first time the suite ran **inside** the image, against 452 that passed. No
review of the Dockerfile would have found that; running the project's own tests
in the artifact found it in 43 seconds. That is why check 6 exists, why the dev
group (pytest) is installed in the image on purpose, and why a separate "test
stage" was rejected — a test stage proves a suite passes in an image that is not
the one that ships.

The same lesson landed three more times in miniature, and all three are the same
disease: **a verifier that fails for its own reasons and blames the artifact**
(gotcha #55, paid again). An inner `bash -lc` expanded `${Package}` to empty and
the check reported blanks as the image's fault. A bare `ldconfig` is
`command not found` for a non-root user. Asserting the library resolves under
`/usr/lib` is red on a correct Debian image, where `/lib` is a symlink and
ldconfig prints the former. Three wrong REDs about a correct image — and every
time, the tell was that the checks measuring *behaviour* (2, 3, 8) stayed green.
When a guard goes red, ask FIRST whether the thing it names actually got worse.

Then the drill found something real. To make the shim fire I ran it with
`python -c`, and got the announcement followed by `Argument expected for the -c
option`. CPython does not preserve the `-c` source string, so the re-exec could
never rebuild its own command line — **since M2-S2, reproducible on the host,
four milestones old** (F-024). Blast radius: ad-hoc probes only, because every
real entry point is `python -m` or a file. But look at the failure's *shape*: the
shim printed that it had linked the library and was re-executing, and then a
message about argument parsing appeared. The visible story was "the fix worked",
followed by noise. It is fixed by *refusing* the form it cannot serve, before
mutating anything, with a message naming the three ways out.

**What to look at.** `docs/task_image_m4.md` — §3 is the smoke transcript, §4 the
drill, §5 the three things that went wrong with what each cost, §7 F-024.
`docker/DECISION-D001-image-delivery.md` for the two options side by side.
`docker/Dockerfile.pipeline` reads as an argument, not a recipe: every pin says
why it is pinned and the user ordering says what it saved. `tests/unit/
test_task_image.py`'s `code_only()` helper is gotcha #53 biting a third time —
four of its assertions went red on the prose in my own comments.

**What to try yourself.** (1) `make image-smoke-redteam` — watch three green
checks turn red and come back, and read the last step, which proves a fresh
container from the same image is clean. (2) Delete `libgomp1` from the Dockerfile,
rebuild, run `make image-smoke`: checks 1, 2, 3 and 8 go red together and 4-7
stay green, which tells you exactly which checks are load-bearing for D-004.
(3) Run `docker history` on any image you own and look for a layer that is as big
as your dependencies but does not install anything — that is a `chown -R`, and it
cost this story 1.7 GB and 139 s before `docker history` named it. (4) In any
container, compare `bash -lc 'which python'` with `bash -c 'which python'`.

---

### M4-S2 — the lifeboat, the guard that stopped telling us to shoot ourselves, and a verifier that could not see the thing it named (2026-08-18, role:MLOps)

**What was built.** Three things and one honest hole. (1) **`make backup`** — the
platform's first copy that survives the cluster: every database and every MinIO
bucket, landing outside the repo beside the DVC remote. (2) **F-021 closed** —
`make ports` resolves who holds a port, so our own running cluster reads as
`held by US` and exits 0 instead of advising you to stop the stack that holds
the only copy of the registry. (3) **Flyte 2.0.42 on the cluster**, reachable
from WSL. And the hole: **the hello-workflow does not complete** — walled at five
attempts, filed as F-023, with the trail written down so nobody restarts the
search.

**Why this way.** The backup came FIRST, before Flyte became the fifth tenant of
the one Postgres, because a lifeboat launched after the new cargo is aboard is a
lifeboat for a different ship. It **enumerates its targets from the server**
rather than from a list — every non-template database, every bucket — and this
story is its own argument: Flyte's `flyte` database and `flyte-data` bucket are
covered by the next run because nobody had to remember to add them. A backup
whose target list can drift is worse than no backup, because it succeeds, prints
a reassuring size, and omits what somebody added last month.

Flyte got **no hostPort**, and that is the interesting choice. Everywhere else in
this program a route is DECLARED — kind hostPort onto a fixed nodePort, twins
across two files, checked by a test. But kind publishes host ports at
cluster-CREATE time only, and since M2 this cluster's PVCs hold the only copy of
the registry, both Optuna studies and the Metabase app-db. So the doctrine was
*deferred with a date and a reason* rather than either repealed or obeyed into a
rebuild: 8080 stays reserved, access is `make flyte-console`, and the declared
route lands free at the next sanctioned rebuild.

**The concept underneath.** *A verifier deserves the same scepticism as the thing
it verifies — including the same negative control.* The backup's first
readability check was `pg_dump -Fc` streamed back through `pg_restore --list`,
and it was wrong in the way that is hardest to notice: a custom-format archive
keeps its table of contents at the **front**, so `--list` succeeds happily on a
file whose tail was never written — which is precisely the truncation the check
existed to catch. It would have gone green forever on a broken backup. That is
gotcha #51's question ("could this component tell if it were false?") asked of a
*checker* rather than a claim, and the answer was no. (It also hung on a 1 MB
dump after working on a 1.2 GB one, which is its own lesson about building on
`kubectl exec` stdin.)

The replacement — `gzip -t` over every byte plus pg_dump's own completion
marker — then went red **twice more for reasons of its own**: the marker is not
the last line (Postgres 16.11 appends a `\unrestrict` token after it), and
`grep -qF "$MARKER"` read the marker's leading `--` as an end-of-options flag and
died with a usage message *while the script announced "the dump was cut short"*.
Each of those cost a 3.5-minute re-dump of a 13 GB database. A verifier that
fails for its own reasons and blames the artifact is gotcha #50 one layer down:
it teaches you to distrust the artifact, and eventually to stop reading the
check. The fix that mattered was procedural — the final version was proven
against a **deliberately truncated copy of the real dump** before being wired
into anything, so "it catches truncation" is an observation and not a hope.

**What was NOT done, and why saying so is the point.** S2's last accept-when leg
is "ONE hello-workflow runs remotely to completion", and it does not. Five
attempts, each failing differently and each fix standing, ended at something
architectural: the blob store is one MinIO with two names, and the CLI — which
uploads its code bundle directly to object storage — is handed the in-cluster
one. It would have been easy to call the deployment "green" and let the
acceptance leg blur; instead the Makefile's own help text for `make flyte-hello`
says **BLOCKED (F-023)**, because a known-failing target that looks healthy is a
trap for exactly the person least able to spot it. It was also tempting to fire
ADR-002's pre-approved fallback and swap to the 1.16.x chart — but that ADR's
trigger is "Flyte 2.x fights on **deployment or MLflow interop**", and deployment
succeeded: three pods Running, helm `deployed`, `/healthz` 200, the CLI creating
projects. Executing a fallback whose condition has not been met would have
discarded a working control plane to fix a URL. *A pre-approved escape hatch is
not permission to skip diagnosing which failure you actually have.*

**What to look at.** `scripts/platform_backup.sh` — read the header's two
paragraphs on why the format changed before reading the code · `scripts/
port_precheck.sh`'s holder block, and the pair of tests in `tests/unit/
test_cluster_scripts.py` that differ in exactly one string (the container name) ·
`infra/helm/flyte/values.yaml`, whose longest comment is about a route it
deliberately does not create · `docs/platform_flyte_m4.md` §5, the five-attempt
trail · gotchas **#54** and **#55**.

**What to try yourself.** Truncate a copy of one of the `.sql.gz` files in the
backup directory and run the two verification legs by hand — then do the same
against the *old* design (`pg_restore --list` on a `-Fc` dump you truncate) and
watch it pass. That contrast is the whole field note in thirty seconds. Then run
`make ports` with the cluster up, stop reading at the sixth line, and notice how
plausible the old advice sounded.

### M4-S1 — the winner was picked on the month nobody was allowed to look at, and the fix was one line in the wrong place (2026-08-18, role:MLE)

**What was built.** Three things, in the order the M4 kickoff sequenced them.
(1) **F-018 repaired**: `scripts/bakeoff_m3.py` now chooses its winner on VAL,
and `gate.verdict_lines` stopped claiming — on every verdict this program has
ever printed — that the holdout was "untouched by training **and by
selection**". (2) **F-019's tripwire**: one test pinning the fact that the
champion M3 promoted raises on any request dated outside 2019. (3)
**`pipelines/tasks.py`**: the six-stage graph §9/M4 names, as plain Python with
typed inputs and outputs, rehearsed end to end on one month before Flyte exists
to blur whose bug is whose.

**Why this way — the part worth remembering.** REV's finding was one line:
`winner = min(loaded[1:], key=lambda item: item.metrics["test"].mae)`. Five
contenders were read on the untouched test month and the lowest took the
champion alias. The obvious fix is to change `"test"` to `"val"` and move on.
That fix is *correct and insufficient*, and the difference is the note.

Changing the key leaves the ranking sitting AFTER both splits have been scored —
so the code still lives in a world where a holdout number is in scope at the
moment of choosing, and the only thing stopping it being used is that nobody
typed it. The repair moved the *ordering* instead: the ranking now happens
inside the val pass of the split loop, and the holdout parquet has not been
loaded when it runs. There is no test number to rank on, correctly or
otherwise. A property you can only violate by deleting code beats a property you
can violate with a two-character edit.

The same instinct produced the second half. `verdict_lines` printed the purity
claim on its own authority — but "untouched by training" is something the gate
can vouch for (it refuses metrics from any other split), and "untouched by
selection" is a fact about the *caller's* process that the gate cannot see. So
the strong sentence became an argument that defaults to OFF: `make train` fits
one challenger and earns it, a bake-off does not. The bug wasn't that the
sentence was wrong; it was that the sentence was being made by the one component
structurally incapable of knowing whether it was true.

**The concept underneath.** *Selection on the test set* is the oldest leakage in
applied ML and it never looks like leakage, because no test row ever touches a
gradient. What leaks is a **decision**: max-of-five taken on the holdout is an
optimistic estimator of the winner's true margin, biased upward by an amount
that depends on how many arms you ran and how close they were. Ours were
**0.0022 minutes apart** — 134 milliseconds — so the holdout didn't just inflate
a number, it *chose which model serves*. And note what saved the result: the val
and test rankings happened to be identical, which §3 of the bake-off memo had
already recorded. The program was structured well enough to make its own defect
harmless and still could not see it. That is why REV exists, and why the finding
was filed at S2 rather than S1.

**The other half of the craft: what was NOT re-run.** `automation/runs/m3s5/
bakeoff.json` is byte-unchanged and the memo's numbers stand. Re-running would
have spent hours re-litigating verdicts that do not change; silently rewriting
them would have destroyed the record of a real defect. So the false five words
are still in `docs/bakeoff_m3.md` §3 with a dated correction note *underneath*
them — what was claimed and what was true, both readable. A document that
quietly repairs itself cannot be compared against the decisions made from it.

**What to look at.** `src/taxi_mlops/training/gate.py` property 7 and
`verdict_lines`' new keyword · `scripts/bakeoff_m3.py`'s `SELECTION_SPLIT`
comment and `_select_winner` · the correction block in `docs/bakeoff_m3.md` §3 ·
`tests/unit/test_bakeoff.py::test_the_winner_is_ranked_on_val_even_when_the_
holdout_disagrees`, whose fixture deliberately makes the two splits disagree —
a test built on M3-S5's real numbers would pass under BOTH rules and prove
nothing · `pipelines/tasks.py`'s four recorded decisions, especially decision 3.

**Decision 3 is the second note.** A REFUSE from a working gate is a *return
value*, not an exception. The CLI maps verdicts onto exit codes because a shell
has nothing else to read; a workflow engine has a whole object. Model a refusal
as a task failure and every "no" this program makes looks like an outage, gets a
retry attached, and eventually gets the stage disabled by someone at 3am. The
mapping still exists — `RegisterResult.exit_code` — stated once so there are not
two copies of the rules.

**What to try yourself.** Open `test_the_selection_happens_before_the_holdout_
is_scored`. It walks the AST to prove `_select_winner` is called inside the
split loop under the `split == "val"` guard. Ask whether that is a test or a
straitjacket — then try to write a behavioural test that catches the ranking
drifting back below the holdout pass. You can't: both orderings give the same
answer whenever the two splits agree, which is the ordinary case. Some
properties are about *when* code runs, and the only cheap instrument for those
is structural. (Then look at the two tests in this story that went red on their
first run because they searched TEXT for the word `taxi_mlops` and found it in a
docstring — gotcha #35, met twice in one file, and fixed by reading imports off
the AST instead.)

---

## M3

### M3-S5 — the gate went red for doing the right thing, and that is the most dangerous kind of red (2026-08-18, role:MLE + MLOps hat)

**What was built.** The second half of M3-S5, across the story's declared
mid-session cut: the error memo's dated **§9** describing the champion that is
actually served (version 2, `auto-lgbm-v2`, feature set v2); three repaired
assertions in `verify-m2`; **`make verify-m3`** made real — 46 sub-checks in 8
sections, 4.7 seconds, re-fitting nothing; **`make verify-m3-redteam`**, which
contradicts one recorded number and watches the gate catch it; and 15 tests on
the gate itself. Both transcripts are pasted whole in
`docs/verify_m3_transcripts.md`.

**The thing that happened, and it is the note.** The champion transition
finished overnight and left exactly one instruction: re-run `make verify-m2`,
because its *"champion right now"* and memo-twin legs are the tripwires the
refresh exists to satisfy. It went **RED — three sub-checks**. None of them was
about anything being wrong.

* `gate_floor` was pinned to the literal `baseline-group-median`. M3-S1 had
  replaced the floor with a **new name** — `…-od-fallback` — *precisely because*
  `configs/train.yaml` legislates that a floor change is a new name and never an
  edit. The tag moved with the promotion, correctly, and the assertion that
  encoded the old world went red.
* The champion's experiment was pinned to the config's current `experiment`. The
  winner is M3-S4's full-data refit and legitimately lives in `m3-automl`.
* `do_not_promote` was read by **key presence**. Every run this program writes
  carries that key; the *value* says which way (`"yes — 15% sample (F-008)"` vs
  `"no — full-data fit; the gate sees it at M3-S5"`). The gate called the
  legitimately promoted champion **hobbled**.

**Why this way.** The tempting repair is to edit the three literals to the new
values and move on — thirty seconds, green again. That repair is the disease.
**A guard that goes red when the program behaves correctly trains the next
session to edit assertions**, and the session after that inherits a formality
that has been edited so often nobody believes it. So each literal was replaced
by the property that holds at *every* champion and is **strictly stronger** than
the literal was: the floor must be a name `baselines.fit_floor` can actually
rebuild (which also excludes the flattering constant-median floor — something
the literal never checked); the run must be FINISHED and in a **namespaced**
experiment, which is gotcha #17's real invariant, never MLflow's `Default`; and
one rule covers both tag families — **a mark counts unless its value says no**.
Plus one sub-check the literal could not make at all: the version's `gate_floor`
must equal the floor `predictions.json` actually published against — F-012's
wire seen from the other end. 54 → **55**, one added, none removed.

`verify-m3` was then written under that rule from its first line. The ablation's
keep/drop verdicts are not read — DR-02's 0.50% bar is **re-applied** to the
numbers printed beside them. The bake-off's five verdicts are not read — the
recorded numbers are **replayed** through `gate.decide` as it exists on disk. The
champion is checked against whatever `bakeoff.json` *recorded* as its winner, not
against a run id. Change the numbers and the gate changes with them; change the
**rules** and it goes red. A test now fails if the gate ever pins a run id, an
experiment name or a floor name.

**The concept underneath.** *There are two ways a check can be wrong, and only
one of them is loud.* A check that misses a real fault is the failure everyone
designs against — that is what red-teaming is for, and M3's drill does it by
contradicting one measured number and confirming the four untampered replays
still pass (a replay that failed on *any* edit would be a checksum wearing a
gate's clothes). The other way is a check that fires when nothing is wrong. It
is loud, it looks like diligence, and it is worse, because its cure is
indistinguishable from vandalism: the session that "fixes" it by editing the
assertion has done exactly what the session before it was supposed to prevent.
The tell is simple and worth carrying: **when a guard goes red, ask first
whether the thing it names actually changed for the worse.** If the program did
the right thing and the guard objected, the guard is the defect — and the repair
is a property, never a new literal.

The same argument had already been made twice this milestone, in smaller print:
the previous session found two feature tests that pinned the literal `v1` and
would have gone red on every legitimate champion transition forever, and fixed
them by asserting the property instead. Three instances in two sessions is a
pattern, and it is now gotchas **#49** and **#50** and finding **F-017**.

**What to look at.** `docs/verify_m3_transcripts.md` — both runs, whole ·
`scripts/verify_m3.sh` §2 (the bar re-applied) and §5 (the five verdicts
replayed) — those two are the file's argument · the commit that repaired
`verify-m2` §1, whose message is the three literals side by side with the
properties that replaced them · `docs/error_memo_m2.md` §9.1, where the memo's
own headline **inverted** (three quarters of the champion's advantage used to be
bought on 1.48% of rows; it is now 96.9% bought on the ordinary 99.98%) — and the
section says plainly that F-010 did that, not the model.

**What to try yourself.** Open `docs/ablation_m3.md` and change `g4`'s verdict
from `drop` to `**KEEP**` without touching its −0.01% delta, then run `make
verify-m3`. Watch §2 name the row: the bar re-applied to the table's own numbers
disagrees with the word printed beside them. Restore it, then instead change the
*number* to +0.90% and leave the verdict at `drop` — same leg, opposite lie,
same red. Then try the edit that a literal-pinning gate would have missed: move
`@champion` to version 1 with
`mlflow.MlflowClient().set_registered_model_alias('nyc-taxi-eta','champion','1')`
and run `make verify-m3` — §7 names the disagreement between the alias and the
bake-off's recorded winner, and §2 stays green, because the ablation did not
change. Put it back to version 2 afterwards.

### M3-S4 — the drill passed, and the thing it found was a corpse the pass rate could not see (2026-08-17, role:MLE)

**What was built.** The automation half of M3's 2×2: a FLAML **scout** that
spends `configs/automl.yaml`'s 1,800 s naming a model family and a starting
region, an Optuna **sniper** that searches inside it with TPE + MedianPruner
against a study living in the one Postgres, a **full-data refit** that turns the
study's best parameters into a bake-off contender through the one evaluator, and
the plumbing under all three — `taxi_mlops.tuning.{storage,space,fit}`. Plus the
two arms §9/M3 asks to *watch*: kill-and-resume, and a pruner. Nothing promotes.

**Why this way — three decisions worth the space.**

*(1) The study's storage is the feature, so it got the design.* Optuna will
happily keep a study in memory or in a SQLite file and the search will look
identical. The one thing this arm exists to demonstrate — kill the process, run
the same command, watch the trial count continue — is a property of *where the
trials are*, and of nothing else. So the storage got a module, a credential
chain that ends in `.env` (never a config, never argv), and a test that walks
every file under `configs/` looking for a connection string.

*(2) A port-forward, deliberately, over the tidier answer.* Publishing 5432
would be cleaner — except kind publishes host ports at cluster-CREATE time only,
so it costs a `cluster-down && cluster-up`, and that takes the PVCs, and with
them MLflow's backend, the registry and the champion. The tunnel is uglier and
strictly reversible. It is also thematically right: the tunnel dies with the
process while the trials do not, which is the demonstration.

*(3) The scout's leaderboard lost a column.* The first draft printed per-family
wall-clock from a FLAML attribute that does not exist. Every cell came back
`0.0` — which reads like a measurement. The column was deleted rather than
fixed: FLAML does not expose the number, and a zero that looks like a timing is
worse than a missing column.

**The concept underneath.** *A test that passes tells you what it checked, not
what is true.* The resume drill passed on its first run and printed exactly what
the milestone gate asks for: three trials survived a `kill -9`, the resumed
process continued the count, transcript pasted. It was also, quietly, wrong. The
trial that was mid-fit at the instant of the kill stayed `RUNNING` in Postgres
**forever** — Optuna cannot distinguish a process that is thinking from one that
no longer exists — so the study asked for `n_trials - len(trials)` more work and
delivered seven answered trials where eight were requested. One trial lost per
kill, invisible to anyone reading the total rather than the *states*. The fix is
Optuna's own (a heartbeat plus `RetryFailedTrialCallback`, and counting
`COMPLETE + PRUNED` rather than rows), but the lesson is the shape: the drill
was written to satisfy a sentence, and the sentence was satisfiable by a system
that was silently losing work. **Ask what a green light would still be
compatible with.** The same instinct killed the 16-trial pruning smoke as
evidence: zero trials pruned is what a healthy pruner looks like on easy data
*and* what a pruner wired to nothing looks like, so the propagation path is
pinned by a test that forces a prune instead.

**What to look at.** `docs/automation_track_m3.md` §3 — both drill transcripts,
before and after, kept side by side · `src/taxi_mlops/tuning/storage.py`'s
`rdb_storage` docstring, which is the finding written where the fix is ·
`tests/unit/test_tuning.py::test_a_pruned_trial_really_raises_out_of_the_boosters_callback`
and its `_prune_probe.py` child process (gotcha #37 again: re-execing pytest
restarts the test session inside itself) · `scripts/automation_track.sh`'s
header, where the 9,000 s is split **before** any result exists.

**What to try yourself.** Run `make tune-resume-drill DRILL_ARGS="--heartbeat-seconds
3600"` and watch the drill fail on the leg it added — the grace period never
elapses, the killed trial is never reaped, and the study reports one fewer
answered trial than it asked for. That is what the first version of this code
did on every kill, and the only difference between the two runs is whether
anybody looked past `TOTAL`.

### M3-S4 (part 2) — the resume worked, and the launcher deleted the run it was resuming (2026-08-18, role:MLE)

**What happened.** The track had been stopped by hand overnight after five of
six phases. Resuming it is one command — `scripts/automation_track.sh` skips any
phase whose output JSON already exists — and the resume did exactly that,
skipping 2 h 20 m of completed work and starting the one missing refit. One line
earlier, `run_detached.sh` had opened the log with `: > "${LOG}"` and destroyed
the transcript those five skipped phases had written. Both FLAML leaderboards,
every sniper trial line and the PO's hand-written stop note, gone (gotcha #48).

**Why it did not cost the story, and why that is the actual lesson.** Every
load-bearing number survived, because each phase writes a JSON verdict beside
the log and the log was only ever the narration. That was not luck exactly — it
was the same decision that made the track resumable, since a phase can only be
skipped if its result is durable somewhere a new process can read. **The
property that let the job resume is the property that made the loss
survivable.** The failure and its own containment came from one design choice.

**The transferable shape.** *When a job is built to be re-run, audit everything
its launcher does to state that already exists.* "Start clean" is the default
assumption of almost every wrapper ever written, and a resumable job has already
contradicted it. The truncation had been in that script since the day it was
written to solve gotcha #45, and it survived a code review and a test suite —
because nothing had ever relaunched under the same name before, and the first
relaunch was the first execution of that line in its real context.

**The other half of the session: a number that must not be improved.**
`auto-on-v1` came in at **3.7245** val MAE against hand-tuned v1's **3.4760** —
the automation track lost on v1 by 7.15% — and the log shows why: it hit its
800-round cap with validation error still falling steeply. It is a *truncated*
model, and the obvious repair (raise the cap, refit, quote the better number)
is precisely the move DR-01 condition 2 forbids: spending more budget on one arm
*after* seeing that arm's result. The honest version costs something real — M3's
2×2 now carries a row whose weakness is a budget artefact and has to be labelled
as one, rather than a clean number. A comparison you are allowed to fix after
reading it is not a comparison, it is a preference.

**What to look at.** `automation/run_detached.sh`'s rotation block and the three
tests in `tests/unit/test_watchdog.py` that pin it — especially
`test_a_live_job_is_never_rotated_out_from_under_itself`, which pins the
rotation to the double-launch guard that makes it safe · `docs/
automation_track_m3.md` §6.4 (the truncated contender) and §6.5 (the budget
ledger, over) · `docs/gotchas.md` #48.

**What to try yourself.** Run any `make detach NAME=… ` twice in a row and look
in `automation/runs/` for the `.log.1`. Then read `scripts/automation_track.sh`'s
`phase()` function and ask what *else* a launcher could reasonably do to a
directory whose contents are the resume points — that question is worth more
than the one bug it found here.

### M3-S4 (part 3) — the same ceiling bound both arms, and only one of them was truncated (2026-08-18, role:MLE)

**What happened.** The sixth and last phase landed at 02:59:07Z and the story
closed: `auto-on-v2` (lgbm, 24 features, 21 trials) measured **3.3823** val MAE ·
**80.552%** KPI-10, against the artisan's hand-held-hyperparameter v2 at
**3.3905 / 80.506%**. Automation won that arm by **0.2436%** — and lost the other
by 7.15%. §6 of `docs/automation_track_m3.md` is complete; nothing was refit,
nothing promoted.

**The question the previous session left, and why its obvious answer was wrong.**
Part 2 flagged `auto-on-v1` as truncated: 800-round cap, val error still falling.
The handoff asked the next session to check whether v2 hit the cap too, because
if it did, "the caveat doubles". It did hit it — `Did not meet early stopping`,
`best_iteration: 791` of 800 — and the caveat does *not* double. Over its last
100 rounds v2 gained **0.00034** MAE; v1 gained **0.02808** over its last 99.
**A cap is a truncation only if the curve is still moving under it**, and an ~82×
difference in slope at the same iteration is the difference between a model that
was cut off and one that had arrived. The two facts are identical at the level of
"did it hit the cap" and opposite at the level that matters. *Reading the ceiling
alone would have put a caveat on the one row in the table that had earned not
having one.*

**The number that got smaller when it was finally measured.** §6.5 had projected
9,400–9,700 s for the track on the assumption that the missing refit would cost
what its twin cost. It cost 981.5 s against 1,308.1 — lgbm on 24 features is
cheaper per round than depth-12 xgboost on 5 — so the real total is **9,133.8 s**,
still over the 9,000 s DR-01 share but by 1.49% rather than by 5–8%. The
projection was replaced rather than quietly deleted, because it was an argument
that ran on that number: "the track has already overspent" is the reason a losing
arm may not be refit, and an honest version of that reason states how much.

**The result underneath both arms, which is worth more than either.** Tuning nine
hyperparameters with 21 trials bought **+0.24%** on v2. This program's own bar for
admitting *one feature group* is **≥0.50%** (DR-02). So the entire automation axis
on the better feature set bought less than half of what a single feature has to be
worth to get in the door — and it cost 4,247.3 s on that arm alone against the
artisan track's 3,313.9 s in total. That is one measurement on one dataset with
one budget, and it is exactly the comparison the 2×2 was built to make available
rather than assume.

**What to look at.** `docs/automation_track_m3.md` §6.3 (the two contenders),
§6.4 (both arms, the slope-at-the-cap argument, and a pre-registered prediction
printed beside its half-refutation), §6.5 (the measured ledger) ·
`automation/runs/m3s4/refit-v2.json` · F-015 in `ledgers/findings.md`, whose
addendum narrows it to one row.

**What to try yourself.** Take any two training logs that both ran to their round
cap and compute the MAE gained over the final 100 rounds of each. That single
subtraction separates "stopped early" from "finished", and it is the check that
nothing in a JSON verdict — `best_iteration: 791` vs `800` — can do for you.

### M3-S3 — the strongest feature in the literature lost, and the sample that lied was the one nobody was allowed to quote (2026-08-17, role:MLE)

**What was built.** Feature set **v2**, earned group by group. Five feature
groups were declared in `configs/features.yaml` in a fixed order *before anything
was fitted* (Design Review DR-03), each was fitted as its own experiment against
a v1 reference on a 15% stratified sample, and each was kept or dropped against
DR-02's bar: **>= 0.50% relative val MAE, with KPI-10 not going down**. Two
survived. Alongside them: the ONE home for feature-set definitions (F-013's
features half — `configs/features.yaml` is now the registry and
`configs/train.yaml` holds a pointer), a zone-geometry module, a committed
holiday table, a point-in-time aggregate builder, and the mandated leakage
red-team. **Nothing was promoted** — the registry API does not appear in this
story's diff, and a test now keeps it that way.

**Why this way — three decisions worth the space.**

*(1) Groups, not features.* Every verdict in `docs/ablation_m3.md` is about a
group of features admitted or refused together. That is less precise than
per-feature attribution and it is the honest unit: the keep-threshold is a
maintenance-cost bar, and what gets maintained is a family of related columns in
the shared transform path, not one column. The cost is stated in the doc's limits
section — g1's win is not attributed to any member of it.

*(2) Every group tried is in the table, including the three that lost.* DR-02
calls this the anti-forking-paths condition and it is the least glamorous rule in
the milestone. Three of five groups failed. A table containing only g1 and g2
would have described the same work and implied a hit rate of 100%.

*(3) The point-in-time constraint went into the type, not into a comment.*
`aggregates.fit(...)` defaults to `point_in_time=True`; the tables it returns
carry the flag; `describe()` prints `LEAKY BY REQUEST` in capitals when it is
off; and exactly one script may turn it off.

**The concept underneath — two of them, and they point in opposite directions.**

*The first: a feature's value is not a property of the feature.* The dossier's
row 14 family — historical OD-pair medians and zone-hour traffic proxies — is
"the single strongest aggregate family in the sources", and it is the only group
of the five that made this model **worse** (−1.63% val MAE, −0.686 KPI-10
points). Not because the idea is bad, but because of two things about *our*
situation that the sources did not share. Their cluster ids came from a KMeans
fit over raw coordinates and carried no information by themselves; **our
`PULocationID`/`DOLocationID` already ARE the OD pair the aggregate is keyed on**,
so the aggregate mostly re-states a column the model has. And their split let
them compute group means over everything; ours does not, so the legal version
serves a train row a one-month window and a validation row a six-month one — the
feature the model is fitted on is not the feature it is scored on. That is
gotcha #43, and it is a failure mode created by the fix, not by the flaw.

*The second: the protocol that looks like ceremony is the one that saves you —
and it saved this story by DISAGREEING with the person running it.* The playbook
says sample-first, then confirm winners at full scale. Watch the
centroid-geometry group — the F-007(b) substitute this whole milestone was built
around — measured at three data sizes: **+2.98%** on a 0.5% harness smoke run,
**+0.6312%** on the 15% ablation, **+0.6277%** on all 43,987,422 rows.

This session wrote the explanation *before* the last number existed, and the
explanation was wrong. It predicted the decline would continue, on a real
mechanism: centroid distance is a smooth ordering over zone pairs the tree has
too few rows to learn individually, so a feature whose job is to stand in for
missing data should be worth less as the data arrives. The measurement says that
effect is **exhausted by 6.6M rows** — 15% and 100% agree to two decimal places
on both surviving groups. The prediction is still in `docs/ablation_m3.md` §5
with its refutation printed underneath it, because a forecast deleted after the
fact teaches nothing and this one is instructive twice: **the sample that lied
was the 220k smoke test the protocol had already ruled inadmissible** (no MLflow
row, so by playbook §3.3 not a result), and the sample the protocol *did* trust
was accurate to 0.02 percentage points. Sampling error is not a slope; it is a
small-sample effect with a size, and the protocol's job is to keep you from
quoting the run that has it.

**The red team, and what it actually showed.** The drill fitted the aggregate
tables across the validation month on purpose — the same line the top-6% Kaggle
solution runs, which is *correct there* because its test period interleaves its
train period. Expected: validation inflates, an untouched month stays flat.
Observed: validation improved by **1.56%** and the untouched month got **3.83%
worse**. Both halves matter. The leak did not merely flatter a measurement, it
damaged the model — and the leaky arm ran all 500 boosting rounds without early
stopping, because the one mechanism that would normally halt a bad direction is
the one a contaminated validation set defeats first. The illegal version would
have cleared DR-02's keep-threshold on both conditions and been admitted into v2
by the same rule that admitted the two honest groups.

**The third thing, and it is about the process rather than the model.** This
story was written across two sessions because the first one was killed
mid-confirmation (gotcha #45). The second one started by running the test suite
the first never reached — and one of the first session's own 33 new tests was
**red**. It had written a correct test for the unseen-category law and a loader
that failed it, because the TLC lookup spells "not a place" two ways and the
comment in the loader generalised from the id its author checked (gotcha #46).
The uncomfortable reading is not "tests are good": it is that **an
uncommitted, unrun test suite is indistinguishable from a passing one**, and
that a story is not done when its numbers arrive — it is done when the cheap
checks have been allowed to disagree with it.

**What to look at.** `docs/ablation_m3.md` §4 and §5 — the two findings, with the
tables, and §5's refuted prediction left standing · §7's re-measurement of the
borough fold, which is what a defect correction looks like when it is measured
instead of argued · `docs/leakage_redteam_m3.md` §3 · `configs/features.yaml`,
which is now the whole answer to "what does the model eat?" and carries the group
order that was fixed before the fitting · `src/taxi_mlops/features/aggregates.py`'s
module docstring, which argues the window-stability point that keeps a raw count
from becoming a proxy for `month` · gotchas #43, #44, #45 and #46.

**What to try yourself.** Re-run one group at a sample size of your choosing
(`make ablation ABLATION_ARGS="--sets v1,v1_g2 --sample-fraction 0.05"`) and plot
its delta against the two in §5 — the slope is the point, and it is a property of
the feature rather than of the run. Then flip the drill's one switch by hand
(`aggregates.fit(frame, target, point_in_time=False)`) on a set you believe in and
see how much better everything gets. The uncomfortable part is how good it feels.

### M3-S1 — the gate learned what it was being compared to (2026-08-17, role:MLE)

**What was built.** Four refusals the gate could not make before. It now judges
against a **stronger floor** (`baseline-group-median-od-fallback` — the same
lookup with one more backoff level, 3.3518 vs 3.5090 test MAE), against the
**model that is actually serving** (F-011), refuses to publish predictions whose
**floor** was fitted over a window the champion's verdict never saw (F-012), and
refuses to issue a verdict at all for a **sampled** training run (F-008). The
second gate that lived in `configs/promotion.yaml` was deleted (F-013, gate
half). Two new drills watch two of those refusals happen: `make gate-redteam`
and `make predictions-redteam`.

**Why this way.** The finding that drove the story (F-010) is subtle and worth
sitting with. M2's gate looked generous: the champion beat its floor by 7.07%
against a 2.00% bar. But the floor answered every trip whose exact
`(hour, dow, PU, DO)` cell it had never seen with the **global median — 11.15
minutes for everyone** — and 1.48% of test rows land there. M2-S4's error memo
had already measured that **75.4% of the model's entire advantage was bought on
those 1.48% of rows**. So most of the "headroom" was not the booster being good;
it was the floor's fallback being bad. Give the same `GROUP BY` one more backoff
level — no new column, no new model, the same train rows — and 98.9% of those
rows get a real answer, the floor drops to 3.3518, and the margin collapses to
**+2.71%**. The cheap response was to keep the old floor and add a paragraph
admitting this. The expensive one, taken, was to adopt the harder floor: M3's
bake-off now has to land at ≤3.2848 instead of ≤3.4388, which is 0.157 minutes
of bar that nobody would have missed.

The design question underneath F-011 is the interesting one: how do you add an
incumbent check to a gate whose whole virtue is being a **pure function**? The
answer that keeps both properties is to make the impure half somebody else's
job. `run._resolve_incumbent` reads the registry and hands `gate.decide` an
`Incumbent` dataclass with its provenance attached; `decide` stays testable
without a cluster, and every one of M2's recorded verdicts still replays because
the argument is optional. That optionality is a hole, so `registry.promote`
closes it from the other side: `incumbent_version` is required, the live alias
is re-read at promotion time, and a mismatch refuses. Neither half alone is
enough — one can be skipped, the other cannot see the numbers.

**The concept underneath.** *A recorded number exists only at the precision it
was recorded at, and comparing a measurement against it at any finer precision
is comparing against rounding noise.* The first full run of the hardened gate
**refused the champion against itself**. The registry tag says `3.2608`; a
deterministic re-fit of the same model measures `3.260823…`; `3.260823 <= 3.2608`
is False. Every unit test passed, because a test writes the same literal on both
sides — the two numbers only differ once one of them has been through a `%.4f`.
The fix is small (round the challenger to the resolution the tag has) and the
lesson is not: whenever a comparison crosses a serialisation boundary — a tag, a
CSV, a JSON manifest, a database column with a scale — the comparison has to
happen at the *coarser* of the two precisions, and the code should say which one
and why. It is also the clearest argument in this milestone for running the real
thing: this defect is invisible to a synthetic `Metrics` object and would have
fired for the first time at S5, on the bake-off, against a champion.

**What to look at.** `src/taxi_mlops/training/gate.py` — the docstring's six
numbered properties, then `INCUMBENT_MAE_DECIMALS` and the comment that explains
what it cost · `registry._assert_incumbent_acknowledged`, which is nine lines
and closes a race · `scripts/gate_redteam_incumbent.sh`'s header, on why the
challenger there is **built rather than fitted** (F-011's window is 0.02 minutes
wide; no hobbled fit lands in it on purpose) · `configs/train.yaml: gate`, where
the floor decision is argued beside the value · `docs/promotion_gate_m3.md` §1
and §7.

**What to try yourself.** Run `make train --train-months 2019-01` — watch it
refuse in seconds, before a single row is read, and read what the message says
about the *direction* of the error. Then add `--no-gate` and watch the same
sample produce a full table, no verdict, and exit 3. Finally, open
`configs/train.yaml` and try to think of a way to make the gate accept a model
worse than the champion **without** editing a threshold: the answer is supposed
to be "delete a check", and if you find a third way, that is a finding.

---

### M3-S2 — the forbidden feature was replaceable, and measuring it took one query (2026-08-17, role:DA + MLE hat)

**What was built.** Three things and one refusal. `make zones` derives 263
zone centroids from the sha256-pinned TLC shapefile into a committed table
(`data/reference/taxi_zone_centroids.csv`), guarded by 13 cluster-free tests.
`docs/feature_dossier.md` holds 21 candidates harvested live from three real
solutions plus our own memos, each with a source and a leakage note. The M3
Design Review minutes fix six decisions (DR-01…DR-06) that bind the next three
stories. The refusal: M3-S1 was the sequenced-first story and could not run —
Docker Desktop was down (gotcha #34, second occurrence), so the registry S1
needs does not exist — and rather than half-build a gate whose four findings
all close on live transcripts, S1 was parked and the next INDEPENDENT story
taken.

**Why this way.** F-007(b) had been open since M1-S3 and it is the kind of
question that invites an essay: `trip_distance` is the strongest predictor in
the data (r = 0.8066) and it is the meter's *driven* distance, which a serving
system does not have. The tempting resolutions are both cheap — record an
assumption that it is "available", or assert that a centroid distance is a fine
substitute. Neither is a measurement. What the finding actually needed was one
number: how much of the forbidden column's power does the legal one keep? Once
the centroid table existed, that number cost a single DuckDB query — **0.7873
versus 0.8068, i.e. 97.6%** — and the decision stopped being a matter of taste.
The centroid artifact was built first not because geometry is interesting but
because *without it the question could not be asked at all*.

The same instinct governed the harvest. It would have been faster to write the
dossier from what is well known about this competition. Instead three solutions
were read as code, and the payoff was a fact that no summary contains: the
top-6% solution concatenates train and test and then takes group means of the
target. The sloppy reading ("they leaked the labels") is wrong — Kaggle's test
rows have no label, so `.mean()` skips them. The precise reading is better than
the sloppy one: what leaks is the *absence of a point-in-time constraint* (a
January trip gets a mean computed with June in it) and the *count* features,
which need no label and genuinely use the test period. **The same line of code
is correct in a competition and disqualifying in production, and the difference
is the split, not the code.**

**The concept underneath.** *Semantic checks have tolerances; byte identity does
not — and the gap between them is exactly where a plausible artifact rots.* The
centroid table has four semantic guards: 263 unique ids, three airports within
3 km of their published positions, two TLC files agreeing on all 263 boroughs,
every point inside an NYC bounding box. All four are good checks and all four
are *bounded*, because a centroid legitimately is not a terminal building. So
the red-team edited JFK's latitude by **111 metres** — one digit, one row of 263
— and every one of those checks stayed green. What went red was the sha256 pin
and the byte-identity twin that re-derives the whole table from the committed
zip and demands it back unchanged. That twin is `make rebuild-proof`'s argument
at 263-row scale, and it is the reason a *derived* file is safe to commit at
all. The general form: when you commit something you could regenerate, the
thing that keeps it honest is not a validator, it is a re-derivation.

A second, smaller lesson worth the tuition: the test that forbids hardcoding
`EPSG:2263` failed on its first run — against the script's own header, which
argues at length about why the projection is never hardcoded. A substring scan
over source cannot tell code from the prose warning about that code (sibling of
gotcha #35). The fix was to parse the AST and look only at non-docstring
constants. A check that reads documentation as a violation is a check the next
person deletes.

**What to look at.** `scripts/derive_zone_centroids.py` — read the header's
five rules, then note that the CRS is taken from the `.prj` *inside the zip*
rather than named · `tests/unit/test_zone_centroids.py`, and specifically which
test would have caught the 111 m edit · `docs/feature_dossier.md` §0's three
stated limits and §4's worked leakage example · the minutes' **DR-06**, which
is a decision minuted with a forward dependency and says so in its own status
line, because the alternative is a reader six months out assuming the number
existed.

**What to try yourself.** Change one digit of one latitude in
`data/reference/taxi_zone_centroids.csv` and run `uv run pytest
tests/unit/test_zone_centroids.py -q`: watch which legs fire and, more
instructively, which ones do not. Then run the DR-04 query yourself —
`uv run python -m taxi_mlops.data query` joining `trips_train` to the centroid
CSV — and try to *break* the 0.7873: sample only airport trips, or only trips
under 2 miles, and see where a straight line between two zone centroids stops
being a good story about a taxi ride. That is the number M3-S3's G2 group has
to beat.

---

## M2

### M2 review — the number nobody computed was the distance to the bar (2026-08-17, role:REV)

**What was built.** No code — a review. A fresh session with no builder context
re-derived M2's published numbers from the committed rows in a second engine, then
filed three findings (F-010 S2, F-011 S2, F-012 S3) and an
approve-with-conditions sign-off.

**Why this way.** The charter's order is load-bearing and it feels wrong while you
obey it: read the code, the configs and the data BEFORE the memo that explains
them. The memos here are unusually good, and that is exactly the hazard — an
explanation you have already read is a hypothesis you will spend the session
confirming. Reading `gate.py` cold is what surfaced that the condition named "does
not regress" is measured against the floor rather than against the model that is
serving (F-011); reading the memo first, where the condition is described in prose
that sounds right, probably would not have.

**The concept underneath.** *Verifying a claim is not the same as challenging it,
and the second is the one that pays.* Every number M2 published re-derived
exactly — KPI-09 to thirteen significant figures, the memo's seven sections, the
segment tables. Zero defects. If verification were the job, the review would have
ended there and found nothing, which the charter correctly calls a defect in the
review. The finding that mattered came from asking a question the artifacts did not
answer: the gate says its 2.00% bar has headroom because the margin is 7.07%, and
the memo says three quarters of that 7.07% is bought on the 1.48% of rows where the
floor gives up and guesses the global median. Those two facts sit in different
documents and are individually true. Put together, they ask: what is the margin
against a floor that gives up less? One extra backoff level — the (PU, DO) median,
same train rows, no new feature — resolves 98.9% of the abandoned rows and takes
the floor from 3.5090 to 3.3518, and the margin from **+7.07% to +2.71%** against a
bar of 2.00%. Nothing was wrong. The distance to the bar was just four times
smaller than the argument for the bar assumed, and no artifact was capable of
saying so, because no artifact compared the floor to a better floor. *A baseline is
the load-bearing number in a promotion gate, and it is the one thing nobody
red-teams — the red team is always pointed at the model.*

**What to look at.** `src/taxi_mlops/training/gate.py:163` — read the condition's
name and then its arithmetic, in that order · `configs/train.yaml: baselines`,
which anticipates the deeper hierarchy and argues it as an EDA-comparability
question, never as a gate question · `docs/error_memo_m2.md` §1 next to
`docs/promotion_gate_m2.md` §2 — two true documents whose product is a third thing
· `ledgers/findings.md` F-010, whose closing conditions deliberately allow the
current floor to WIN, provided the bar is re-argued against 2.71%.

**What to try yourself.** Take any gate in any system and re-run its verdict
against a bar made one increment stronger by the cheapest honest means available —
not a better model, a better baseline. Then ask which side of that number your
project has been quoting. Second exercise, thirty seconds: read
`registry.promote()` and answer "what stops this from replacing a good champion
with a worse one?" before grepping for the answer. The grep is empty.

### M2-S5 — the gate that checks the gate, and the four sub-checks that had to be watched failing (2026-08-17, role:MLOps)

**What was built.** `make verify-m2` — 49 sub-checks across 9 sections, ~30
seconds, exit 0 — plus `make verify-m2-redteam`, which breaks it on purpose and
watches the light change. Together they are the M2 milestone's answer to "did
this actually happen?", and they are the last artifact of the milestone: the
◆ exit hands the program to a fresh REV session next.

Nine sections: the champion resolves through its alias and carries a signature,
an input example and the verdict it was promoted on · M2-S3's transcripts still
produce the same verdicts through today's gate code · the MLflow experiment
holds every contender including the refused one · KPI-09/KPI-10 exist nowhere
but the evaluator · the predictions reconcile row for row and re-score to the
champion's own promotion tag · the `error_segments` mart's whole-split row
reproduces the evaluator to four decimals · the board renders and a card RUNS ·
the memo links the board and its twin script reproduces the headline live · the
boundary-law grep is empty and the repo root holds no stray.

**Why this way.** Three decisions carried the story, and each is a refusal.

*The gate re-fits nothing.* The obvious way to check "the model was promoted
honestly" is to run `make train` again. That would mint MLflow runs on every
verification and judge a model the registry has never heard of — a gate with
side effects on the thing it is checking. The champion is a registered
artifact; this gate reads it. Pinned by a test that greps the comment-stripped
script for the *invocation*, not the words (the script talks about `make train`
constantly in its prose).

*The refusal is checked by replay, not by grep.* The kickoff's leg reads "the
gate refusal transcript exists with both numbers". A `grep -q REFUSE` satisfies
that sentence exactly — and stays green forever after somebody edits
`min_improvement_pct: 2.0` down to `0.5`, which is the one change the
constitution reserves for a PO fork. So the leg parses the pasted transcripts
out of `docs/promotion_gate_m2.md` and feeds their numbers back through
`gate.decide()` as it exists on disk *now*. 7.6667 against 3.5090 must still
come back REFUSE; 3.2608 against 3.5090 must still come back PROMOTE; and the
gate must still *raise* when handed val metrics or the flattering
constant-median floor. The document is evidence about a past run; the replay is
evidence about today's bar. Only the second one notices that the bar moved.

*Every leg must prove it ran.* M1's gate shipped with a leg that grepped for a
string the script never printed, reported "0 output(s) byte-identical" and
passed — a green light wired to no sensor. M2 applies that lesson one level up:
each Python leg must emit a minimum number of verdicts, or the shortfall is
itself a failure. This is not theoretical. In the red-team drill the registry
leg lost its alias, raised on the first check and emitted 1 verdict of the 7 it
owes — the guard is the thing that said so. The sibling rule is smaller and
nastier: `consume` is invoked through process substitution and never through a
pipe, because `… | consume` runs the counter in a subshell and discards every
failure it counted at the closing brace. A gate that prints red FAIL lines and
exits 0 is worse than no gate.

**The concept underneath.** *A verification is a claim, and claims are only
worth the falsification you have watched.* The red-team drill is the whole
point of this story, not a garnish on it. It deletes the `@champion` alias —
instant, exactly reversible, and invisible to anything that is not genuinely
reading the registry — then asserts three things at once: the gate goes RED,
it *names* the alias, and **38 other sub-checks still run and pass**. That
third assertion is the one people skip, and it is the one that distinguishes a
suite from a tripwire: a gate that collapses to a single failure when one thing
breaks has told you nothing about the rest of the system. Then it restores from
an EXIT trap and demands GREEN 49/49, because a drill that leaves damage is a
drill nobody runs twice.

The same instinct made the drill delete the *pointer* rather than the model.
Version 1, its run, its signature and its artifacts are untouched from start to
finish. A destructive red-team is not a braver red-team; it is one you can only
perform once.

**One near-miss worth more than the code.** The first draft of the registry leg
reached MLflow with a bare `set_tracking_uri` and got
`Failed to download artifacts from path 'MLmodel'` — which is very nearly
F-009's error message, the known MLflow 3 defect M2-S4 had just documented. The
obvious conclusion was that F-009 is worse than recorded. It is not: our server
does not proxy artifacts, so a client without MinIO credentials cannot read any
artifact at all, and the first one a model read touches happens to be `MLmodel`.
Two diseases, one symptom, and the famous one is the wrong answer. The
discriminator costs one call — under F-009 `get_model_info` *succeeds* on the
uri that `load_model` fails on; without credentials both fail. Now gotcha #39,
and the F-009 ledger row carries the narrowing, because the cost of getting this
wrong is not a broken script: it is M5 inheriting a workaround for a fault it
does not have.

**What to look at.** `scripts/verify_m2.sh` §2 — the replay leg, the densest
thirty lines in the story · `scripts/verify_m2_redteam.sh`'s `trap restore EXIT`
and the "unaffected leg still green" assertions · `tests/unit/test_verify_m2.py`,
which is the answer to "who checks the checker" · gotcha #39 next to F-009's
ledger row, read as a pair.

**What to try yourself.** Open `configs/train.yaml`, change
`min_improvement_pct` from `2.0` to `0.5`, and run `make verify-m2`. Watch
section 2 go red on a config edit that touched no code, no model and no data —
that is the difference between checking a document and checking a bar. (This
was run, not imagined: `RED — 1 sub-check(s) failed`, the other 48 still green.
Notice what section 1 does while section 2 burns: it keeps printing
`required >= 2.00%`, because that number comes off the champion **version's own
tag** — the bar as it stood at promotion time. The registry remembers what the
model was judged against even after the config forgets, which is exactly why
the verdict travels on the version.) Put it
back, then run `make verify-m2-redteam` and read the RED transcript from the
top: notice which sections stayed green, and ask yourself for each one whether
it stayed green because it is genuinely independent of the registry, or because
it is not really looking.

---

### M2-S4 — a segment number is only worth the rollup that checks it (2026-08-17, role:DA)

**What was built.** The model stopped being a pair of headline numbers. `make
predictions` scores the **registered champion** — not a fresh fit — on val and
test and publishes one row per held-out trip (`data/predictions/`, 12,140,456
rows) carrying the five features it saw, the truth, its quote and the honest
floor's quote for the same trip. `make duckdb` gained a third reconciliation over
those rows, `make marts` gained an `error_segments` mart (1,151 rows, grain
segment x split), and Metabase gained an **11-card error-segment board**. The
deliverable on top is `docs/error_memo_m2.md`: where v1 fails, in zones, hours
and trip lengths, every number from a named view or mart.

**Why this way.** Four choices worth naming.

*(1) Score what was PROMOTED, not what was fitted.* A re-fit reproduces the
champion's numbers to four decimals — M2-S3 watched it happen — but it is a
different MLflow run, and predictions labelled with a version the registry has
never heard of are evidence about a model nobody deployed. So `score.py` resolves
`models:/nyc-taxi-eta@champion`, reads the version back, stamps it on every row,
and mints nothing. Then it does the thing that makes this more than a gesture:
the champion's own promotion tags say it was gated at KPI-09 **3.2608** on test,
so scoring it now must return 3.2608, and the command **refuses to write** if it
does not. Either the model that loaded is not the model that was promoted, or
this path builds features differently from the one that fitted it — both are
defects, and neither has any other symptom.

*(2) New ids, because the window is new.* Segment MAE is **KPI-11**, not
"KPI-09 by zone". The id law (a changed formula is a new id, never an edit) is
what stops a board's history from silently changing meaning, and a window is part
of a formula. But a new id invites a subtler failure — a SQL layer that quietly
filters or duplicates rows and reports beautiful, wrong segments. So the mart
publishes an `overall` row per split, and a dbt test fails the build unless
KPI-11 **is** KPI-09 and KPI-12 **is** KPI-10 to four decimals. *A segment number
that cannot roll up to the evaluator's number is not a segmentation of it.* That
test is what makes it legitimate for a mart to carry model-error numbers at all
without breaking gotcha #15.

*(3) The memo got a twin.* The three scratch scripts this story's first sitting
left behind became one committed `scripts/error_memo_numbers.py` — one section per
memo section, in order, printing the query it ran. It earned itself on its first
execution by catching **four last-digit rounding slips** (§4's airport shares and
mean, §6's late-bias) that had been typed rather than pasted. A memo full of
figures nobody can re-run is a memo nobody can check, and the gap between "I
computed this" and "anyone can recompute this" is exactly where numbers rot.

*(4) The finding that matters most is about coverage, not accuracy.* The gate
recorded +7.07% over the floor. Split by whether the floor had a group median to
give: on the **98.52%** of test rows it could answer, the booster is worth
**1.88%** — under four seconds; on the **1.48%** it could not, it is worth
**68.19%**, because the floor's answer there is the global median and is wrong by
18.57 minutes. **Three quarters of the champion's entire advantage over a SQL
query is bought on 1.48% of the rows.** That is not an argument against the model
— generalising to unseen combinations is precisely what a lookup table cannot do
— but it means the gate's margin is dominated by *coverage*, so anything changing
how often the floor falls back moves the bar more than it moves the model. Which
is **F-008** seen from the other side, arriving at M3 from a second direction.

**The concept underneath.** *An aggregate is a claim that a population is
homogeneous, and it is almost always false.* KPI-10 says 81.5% of riders are
quoted within five minutes; the memo says that number is 93.7% for a five-minute
hop and **0.000%** for the 970 longest trips the contract admits — not "low",
zero, with the model's ceiling (92.2 min) sitting below the data's (120.0). The
mechanism is honest rather than broken: with an `l1` objective and no distance
feature, the conditional median of a New York taxi trip given only (hour, day,
origin, destination) is simply not 108 minutes. Segmenting does not improve the
model; it converts one number everybody trusts into several numbers somebody can
act on — which is why §7 of the memo is addressed to named roles at named
milestones rather than to the reader.

**The other lesson, and it cost the session an hour.** `make marts` failed
naming a file that plainly exists. The cause was dbt's partial-parse cache, which
records node paths **relative to wherever dbt was last run** — one hand-run from
the repo root by the previous, killed sitting had poisoned it (gotcha #38). Two
things generalise. First: *when a build fails naming a file you can see, suspect
the cache before the code.* Second, and it is the reason the fix is
`--no-partial-parse` rather than a note telling people where to stand: a cache
keyed on ambient state that no input mentions turns a build into a function of
where somebody once stood. The fix was red-teamed by re-poisoning the cache the
same way and watching ERROR=1 become PASS=57 — because a fix for a bug you cannot
reproduce on demand is a hope.

**What to look at.** `docs/error_memo_m2.md` §1 (the coverage decomposition) and
§2 (the ceiling) · `analytics/dbt/tests/assert_error_segments_reconcile.sql` —
nine lines that license the whole mart · `src/taxi_mlops/training/score.py`'s
`_check_against_registry` · `scripts/error_memo_numbers.py` next to the memo,
read as a pair · gotcha #38 · **F-009** in `ledgers/findings.md`, which M5 will
meet as a deployment failure if it does not read it first.

**What to try yourself.** Run `uv run python scripts/error_memo_numbers.py 1` and
then compute the same decomposition by hand from the two rows it prints — the
point is to feel how much of a headline margin can hide inside 1.5% of a
population. Then break the rollup deliberately: add a `WHERE split = 'test'` to
`error_segments.sql`'s overall row and run `make marts`, and watch
`assert_error_segments_reconcile` refuse the build. A test you have never seen
fail is a test you are trusting on faith.

### M2-S3 — a gate is worth what its refusals are worth (2026-08-17, role:MLE)

**What was built.** `make train` became real, and it can now fail. The path is
one command: both floors and LightGBM v1 through the one evaluator, then the
**promotion gate** (`taxi_mlops.training.gate`) on the untouched test month, then
— only on a verdict that passed — promotion into the MLflow registry
(`taxi_mlops.training.registry`) with the `champion` alias. The bar is a **2.00%
KPI-09 margin over the group-median floor**, plus a **KPI-10 non-regression**
condition, both in `configs/train.yaml` with their reasoning beside them. A
refusal exits **1**; `make train-redteam` submits a deliberately hobbled
challenger through the identical path and inverts that, the way
`RED_TEAM=1 scripts/marts.sh` does.

**Why this way.** Four choices worth naming.

*(1) The gate decides and a different module acts.* `gate.py` is a pure function
of two `Metrics` objects and a config — no MLflow, no filesystem, pinned by a
test that greps it for side effects. `registry.py` holds everything that mutates
state outliving the process. The payoff is not tidiness: it means the interesting
logic is exhaustively testable without a cluster (a challenger that ties the
floor, one that buys its mean by quoting more riders wrongly, a comparison on the
wrong split, a winner with no signature — all unit tests), and the dangerous
logic is small enough to read in one sitting.

*(2) The margin is a maintenance-cost bar, not a statistical one.* Over 5,950,708
test rows, even 0.5% is statistically significant, so significance is the wrong
question. 2% of the floor is about **four seconds** of mean error, and a model
whose entire advantage over a `GROUP BY` is four seconds does not earn a booster
to serve, a registry version to track and a rollback to rehearse. The measured
gap is 7.07%, so the bar has headroom by design — a bar cut to fit the model you
happen to have is a rubber stamp with a threshold in it.

*(3) The refusal is kept, not deleted.* The kickoff allowed cleanup **or** clear
marking. Marking won: the hobbled run stays in `m2-modeling` tagged `red_team`,
`hobbled`, `do_not_promote`, because a deleted refusal cannot be checked by
anyone who was not watching it happen. What must stay clean is the **registry**,
and the script proves that by snapshotting it before and after rather than
asserting it.

*(4) Promotion is idempotent by RUN, not by call.* Re-running against a run
that is already registered reuses that version and leaves an alias already
pointing at it alone. This is M1-S5's board law applied to a new surface: a
converging path that creates a duplicate on every invocation is not converging,
it is accumulating.

**The concept underneath.** *A gate that has only ever been watched saying yes is
not evidence of anything.* Any threshold passes the model it was written for —
that is what writing it after seeing the number does. What makes the bar
believable is the transcript where it says **no**, with both numbers on screen,
against a model built to be refused. And the refusal taught something the passing
run could not: fitted to permuted labels, LightGBM early-stopped at **iteration
1** and its test MAE came out at **7.6667** — exactly `baseline-constant-median`
to four decimals. "Learned nothing" is not an abstraction; numerically it *is*
the median. Which also makes the config's warning concrete: against the
flattering constant-median floor, the hobbled model scores **+0.00%** — a gate
built on that floor with a zero margin would have promoted a model fitted to
noise.

**The mistake worth copying.** Smoke-testing on one train month to save time
produced a *better-looking* verdict than the full run: margin 16.85% instead of
7.07%. Not a lucky sample — the **floor is fitted on the same data as the
challenger**, so shrinking the training set degrades the bar faster than it
degrades the model. Sampling makes this gate **easier** to pass, and the
transcript looks better while the model is worse. That is now **F-008**, landing
M3, because M3's scout and sniper train on samples by design.

**What to look at.** `docs/promotion_gate_m2.md` — the argument, both
transcripts, and §6's limits · `configs/train.yaml: gate` (read the comments, not
just the numbers) · `src/taxi_mlops/training/gate.py`, which raises rather than
warns when asked to judge on val or against the flattering floor ·
`tests/unit/test_training_gate.py`, which is mostly refusals · `ledgers/
findings.md` F-008.

**What to try yourself.** Run `make train-redteam` and watch the two FAIL lines.
Then edit `min_improvement_pct` to `-200` and run it again: the gate will promote
a model fitted to noise, and the transcript will say so in full — which is the
clearest possible demonstration of why loosening a threshold is a PO fork and not
an edit. Put the 2.0 back. Then try `gate.decide` with val metrics in a REPL and
read the exception: it explains the early-stopping argument to you at the moment
you would have made the mistake.

### M2-S2 — the floor a `GROUP BY` already knew, reproduced to four decimals (2026-08-17, role:MLE)

**What was built.** The first model, and the machinery that makes its number
mean something. `taxi_mlops.features` defines quote-time feature set v1 — five
columns: `hour`, `dayofweek`, `PULocationID`, `DOLocationID`, `passenger_count`
— plus a registry of **18 refused columns**, each carrying its reason and its
ledger row in code. `taxi_mlops.training.evaluate` became THE metric source:
KPI-09 (MAE) and KPI-10 (within-5-minutes) have their first measured values and
no other origin in this program. Both baselines and LightGBM v1 go through that
one function, in one invocation, printing one table.

**Why this way.** Four choices worth naming.

*(1) The include list is a knob; the exclude list is law.* Feature sets are meant
to be revised — that is what M3's dossier does — so `configs/train.yaml` owns
which columns go in. But `fare_amount` must never go in, and the failure it
causes is invisible: a model built on post-trip money scores *beautifully* on
every held-out split and cannot be served at all. So the exclusions live in code
with reasons, and `FeatureLeakageError` refuses a matrix **or a config** that
re-admits one. This is M2-S1's trapdoor argument applied to a different
invariant: a switch that can break one is not a knob.

*(2) The registry disagrees with the finding that created it, deliberately.*
F-007 named six post-trip columns. The registry excludes **nine** — `extra`,
`mta_tax` and `improvement_surcharge` are recorded on the same meter at the same
moment and fail the identical test. A registry that agreed with the finding
rather than with the world would just be the next trap, filed under a different
name.

*(3) The baselines are scored by the model's evaluator, not by SQL.* This looks
like duplicated work — the EDA already computed both floors in DuckDB. It is the
opposite. If the floors came from SQL and only the model came through
`evaluate`, the comparison would be between two measuring instruments as much as
between two predictors, and the model's instrument would be the one nobody had
checked. Running both through one function makes the comparison a comparison —
and it turned the EDA's numbers into a **test of the evaluator**.

*(4) The unseen-group fallback is counted, not merely handled.* About 1.5% of
val rows carry a `(hour, dow, PU, DO)` combination train never saw. A lookup that
raises on them is not a baseline with a rough edge; it is the exact shape of a
500 at M5's serving boundary, arriving on the day a new zone opens. So the
fallback is explicit, its rate is an MLflow metric, and `evaluate` **refuses** a
NaN prediction outright — because `np.mean` of a NaN renders as a blank cell,
and a blank cell reads as "not run yet" rather than "the predictor has a hole".

**The concept underneath: an instrument you have not checked is not a
measurement.** The strongest result of this story is not the model. It is that
`evaluate`, running different code on a different engine over the same months,
reproduced the EDA's SQL floors *exactly*:

| | EDA (SQL, M1-S3) | `evaluate` (M2-S2) |
|---|---|---|
| constant-median val MAE | 7.8866 | **7.8866** |
| group-median val MAE | 3.7170 | **3.7170** |
| group-median test MAE | 3.5090 | **3.5090** |
| group-median val within-5-min | 78.693% | **78.693%** |
| unseen-group rate, val / test | 1.53% / 1.48% | **1.5252% / 1.4786%** |

Nothing was tuned to make those agree; a disagreement would have been a bug in
`evaluate`, as the kickoff predicted in advance. That is what gotcha #15 is
protecting — not a bureaucratic rule about which module prints numbers, but the
principle that a metric is only as trustworthy as the instrument, and the
cheapest way to check an instrument is to point it at something whose answer you
already know.

**And the honest result.** `lightgbm-v1` measured **3.4760 min val / 3.2608 min
test** MAE and **79.693% / 81.480%** within five minutes. Against the honest
floor that is **6.48%** better and **one point** more trips inside the tolerance.
Against the *flattering* floor (constant median, 7.8866) it looks like a 56%
triumph — which is exactly why that baseline is named "the flattering one" in the
code and why CLAUDE.md forbids quoting it. A modest win is the truthful shape
here: v1 has **no distance feature**, because the only distance in the data is
the meter's driven distance, which a quote-time request does not have (F-007(b),
M3's problem). The model also never early-stopped — 500/500 rounds, val still
improving — so 3.4760 is a floor for LightGBM on these five features, not its
ceiling.

**E-1, answered by measurement.** The EDA asked M2 to *prove* the log-target
idea, not assume it. The `log1p` ablation is its own run and came in at **3.4803
val / 3.2688 test** — consistently *worse*. The reason is not mysterious: KPI-09
is MAE in minutes, and objective `l1` minimises exactly that on exactly that
scale, whereas training on logs and exponentiating back optimises the median of a
different loss. That is a win when the metric is relative. Ours is absolute.

**What to look at.** `src/taxi_mlops/features/quote_time.py` — read `EXCLUSIONS`
top to bottom; it is the most useful 100 lines in the story.
`src/taxi_mlops/training/evaluate.py` for the instrument, and
`tests/unit/test_training_evaluate.py` for assertions you can verify by hand
(deliberately: a test that checks an implementation against itself would be worse
than no test). `src/taxi_mlops/training/openmp.py` for a workaround written out
loud, with gotcha #37 as its footnote and debt D-004 as its expiry date.

**What to try yourself.** Add `fare_amount` to `features.passthrough` in
`configs/train.yaml` and run `python -m taxi_mlops.training train
--train-months 2019-01 --no-mlflow`. It refuses before reading a row, and the
refusal quotes the r = 0.8708 correlation at you. Then comment out the
`assert_quote_time_pure` call in `feature_names`, run it again, and watch the
val MAE collapse — that is what a leaked model looks like from the inside, and
it is why no offline check would have saved you. Second experiment: change
`baselines.group_keys` to `["PULocationID", "DOLocationID"]` and watch the floor
rise; the four-key floor is hard to beat precisely because time-of-day carries
most of what a tree would learn.

---

### M2-S1 — the rows we threw away had a signature, and 85% of them were the same fault (2026-08-17, role:DE)

**What was built.** The other half of the rejection story. Ingest already
*counted* every dropped row against a named rule; since this story it *keeps*
them — `data/rejected/<split>/yellow_tripdata_<month>.parquet`, 16 files, 27 MB,
every contract column plus the derived target, two extra columns naming the rule
that filed the row (`rejection_rule`) and every rule it violates
(`rejection_rules`). DVC-pinned as its own target, published as the
`trips_rejected` view, and checked by a second reconciliation in `make duckdb`
that fails the build if the sidecar and the counts ever disagree per (month,
rule). Then the question F-005 raised in the first place, answered with SQL:
`docs/rejected_rows_appendix.md`.

**Why this way.** Four choices worth naming. (1) **First-match attribution is
law, not a knob.** The config *could* have offered `first_match | all_match`,
and it deliberately does not: `rejection_rule` matches `rejected_by` exactly,
and that identity is what makes the sidecar checkable against the report. A
switch that could break an invariant is not a knob, it is a trapdoor. The
all-match information is published *alongside* instead, as a second column, so
nothing was lost. (2) **A separate tree, not a sibling file under
`processed/`.** Different schema, different pin, and — the real reason — every
rebuild proof and analyst view globs `data/processed`; rows the contract refused
must not be one careless glob away from the training data. For the same reason
`trips_rejected` is *not* unioned into `trips_clean`. (3) **The sidecar went
INTO the rebuild proof, not beside it.** `make rebuild-proof` now wipes and
re-derives both trees and asks DVC about both `.dvc` files: a proof that
re-derives half of a command's output is a proof of half a command, and the half
it skips is the half nobody looks at. (4) **Reconciliation is per (month,
RULE), never per month.** A sidecar that files every row under the wrong rule
has a perfect monthly total and is useless for the one question it exists to
answer — there is a red-team test that relabels a month's rows and watches the
gate go red on exactly two rules while the total stays 4.

**The concept underneath.** *A count tells you how much; only the rows tell you
what kind — and the difference is usually the whole answer.* For five sessions
this program knew that `duration_above_max` removed **159,300** trips and could
not say whether they were meter faults or a real long-haul population. The EDA
said so out loud rather than guessing, which was the honest move and also a
standing debt. One query against the retained rows settled it in a minute:
**85.0%** of them are a normal short trip — median **2.19 miles**, median fare
**$12.00** — that was dropped off **the next day at almost the same clock hour**
(98.97% next-day, 62.64% same hour). The meter measured a fine ride; only the
session clock is unusable. And the money is the tell that a count could never
have carried: if those were really 23-hour journeys, the fare would say so.
Meanwhile **5,601** trips in the 120–180 minute band *are* real long-haul —
52.78% touch an airport, 32.87% carry an out-of-city rate code against 2.7497%
of the clean data. So the answer was never "faults **or** long trips". It was
both, in a ratio of 24 to 1, and no aggregate would ever have shown you that.

A second, smaller lesson: the two free re-proofs. Re-running a *changed* ingest
returned all 8 processed outputs **byte-identical** — evidence that the change
touched only the new path. And the sidecar's own numbers were never engineered
to match anything: 914,459 retained rows against 914,459 counted, across 80
(month, rule) pairs, computed by different code from different artifacts.

**What to look at.** `src/taxi_mlops/data/clean.py` — `_label_rejected`, and the
comment explaining why the all-match string is built on the ~1.6% subset rather
than on 7M rows · `configs/data.yaml:rejected` — the config block that argues
*against* making itself more configurable · `analyst.rejection_reconciliation`
and its FULL OUTER JOIN (a rule that exists only in the sidecar is what a
half-finished rename looks like) · `docs/rejected_rows_appendix.md` §R3, the
two independent witnesses for the clock artefact · `scripts/verify_m1.sh` leg 1,
where a `grep -c` counting the wrong lines got replaced by the number the proof
itself prints.

**What to try yourself.** Two red-teams that take a minute each. Truncate a
sidecar month (`pq.write_table(pq.read_table(p).slice(0,1), p)`) and run
`make duckdb` — watch it exit 1 naming the rules. Then do the subtler one:
*relabel* every row of a month to one rule, leaving the count untouched, and run
it again. A per-month check would pass; this one names both rules that moved.
Then read §R2's band table and ask what a histogram of *durations alone* would
have told you — the answer is "there is a spike near 24 hours", which is the
observation, not the explanation. The explanation needed the fares.

---

## M1

### M1-S5 — a port you cannot add to a running cluster, boards that live in git, and a tool that vanished without being uninstalled (2026-08-17, role:MLOps deploy + DA boards)

**What was built.** The BI seat and the M1 gate. `infra/manifests/metabase.yaml`
(one container, image pinned by tag AND digest, app-db in the one Postgres),
`scripts/deploy_metabase.sh`, `scripts/metabase_boards.py` (boards converged from
checked-in JSON through the Metabase API), two boards under
`analytics/metabase/boards/` totalling 17 cards, and `scripts/verify_m1.sh` — the
gate, red-teamed once. Plus the deliberate cluster rebuild the whole story hangs
on, and 28 new unit tests.

**Why this way.**

*The rebuild was planned, not discovered.* kind publishes host ports at cluster
**CREATE** time only. There is no `kubectl` that adds one to a running cluster,
no live path, no clever patch — adding `3030 → 30300` means `cluster-down` +
`cluster-up`, and everything on the PVCs dies. The M1 kickoff found this at draft
time by reading the kind config rather than by hitting it at 3am, wrote "M1-S5
carries a deliberate cluster rebuild" into the preconditions table, and the story
budgeted for it. The interesting part is what that turned a teardown into: a free
re-proof. The marts came back from `make marts` alone with counts identical to
M1-S4's to the row, and the empty Postgres volume exercised the one D-002 path
M1-S4 could not — the fresh one. A destroy you planned is an experiment; a
destroy you didn't is an incident.

*Boards are files, not clicks.* This is the entire reason the BI layer took a
script instead of twenty minutes in a browser. A dashboard built by clicking
exists in exactly one app-db: it cannot be reviewed in a pull request, cannot be
rebuilt after `make destroy`, and when a number moves nobody can say what
changed. `docs/prior_art.md` had already recorded this as an ADOPT; M1-S5 is
where it landed. The cost is real and worth naming — edits made in the UI to a
card this repo owns are overwritten by the next `make boards`, and that is the
point, not a bug.

*The app-db is a real database, because H2 would have worked.* Metabase's default
app-db is an H2 file inside the container holding the dashboards, the cards, the
connections and the users — i.e. everything the M1 gate calls "the boards". It
would have worked perfectly through every test in this session and died at the
first rollout. Losing a container filesystem is the *normal* behaviour of a
Deployment, not a durability edge case. So `metabase` became D-002's third
database, which cost exactly what M1-S4 predicted it would: one line in
`scripts/postgres_databases.sh` and one `ADDITIVE` entry in
`scripts/platform_secrets.sh`. A test now makes that prediction falsifiable
rather than a comment.

**The concept underneath: a check that races the thing it checks.** The first
`make deploy-metabase` failed at its own last step. `kubectl rollout status`
returned "successfully rolled out", and the single 20-second `curl` that followed
came back `000`. Nothing was broken — `rollout status` succeeds the *instant* the
readinessProbe flips, and Metabase's first request through a node port, on a JVM
that has just finished migrating its app-db, is slower than any one-shot timeout
worth setting. This is gotcha #29's cousin. There, a readiness check passed on
zero replicas; here, a liveness check failed on a live service. Both are the same
mistake in different directions: **asking a question at a moment you did not
choose.** The fix is not a longer timeout, it is a bounded retry — because a
check that reports a broken deploy roughly at random is worse than no check, as
it teaches you to re-run and shrug, and the day it is right you will shrug then
too.

**And a tool that vanished without being uninstalled.** The session opened with
`kubectl: command not found` — for a binary CLAUDE.md records as pre-existing and
four earlier sessions used. It had not been removed: `/usr/local/bin/kubectl` is
a symlink into `/mnt/wsl/docker-desktop/cli-tools/`, a path that exists only
while Docker Desktop is running, and the host had restarted overnight without it.
The error message sends you to your PATH, your toolchain install and your
kubeconfig — none of which were broken. Two commands ended it: `ls /mnt/wsl`
(only `resolv.conf`) and `tasklist.exe` (no Docker Desktop process). Now gotcha
#34, and the general form is worth carrying: **a tool that disappears without
being uninstalled is a symlink into somebody else's lifecycle — resolve the link
before you debug the tool.** This is what the boot ritual's staleness check is
*for*; the handoff's "Next" claimed a live cluster, and reality had moved.

**What to look at.** `infra/kind/kind-config.yaml` and
`infra/manifests/metabase.yaml` — one number written in two files, and
`tests/unit/test_platform_scripts.py` fails if they drift · the "What the tests
refuse, and why" table in `analytics/metabase/README.md`, which is the honest
summary of what a board is not allowed to do · `scripts/verify_m1.sh` §3, where
the corrupt-parquet red-team writes its fixture into a throwaway `raw_dir` under
a throwaway config, so a gate never puts a corrupt byte near `data/raw`
(gotcha #33's neighbour: a proof must not damage the artifact it protects).

**What to try yourself.** Open http://localhost:3030 and change a card's SQL in
the browser, then run `make boards` and watch it revert — that is the trade this
design makes, felt rather than described. Then delete a card from
`analytics/metabase/boards/kpi_board.json` and run `make boards` again: it does
**not** disappear from Metabase, because the script adds and updates but never
archives. Decide for yourself whether that asymmetry is right. (It is the same
one `postgres_databases.sh` follows, for the same reason: destroying is `make
destroy`'s job, out loud.) Finally, run `make verify-m1` and time it — then try
to talk yourself into adding a `FAST=1` flag, and read
`test_verify_m1_has_no_skip_flag_for_the_expensive_rebuild_leg` before you do.

### M1-S4 — the number that agreed, and a `configured` that finally said `unchanged` (2026-08-16, role:DA + MLOps hat)

**What was built.** A dbt project under `analytics/dbt/` building four marts —
`trips_clean` (56,127,878 rows), `zone_hourly_stats` (44,792), `monthly_kpis`
(8), `rejections_by_rule` (80) — with 34 dbt tests, published into the one
Postgres by `make marts`. Plus D-002's landing (`scripts/postgres_databases.sh`,
the path a database takes when initdb already ran) and F-003's close.

**Why this way — three things worth the reader's time.**

**(1) The publish opens no port, and that constraint improved the design.**
Postgres is ClusterIP-only by charter, so the obvious moves — a NodePort, a
port-forward, DuckDB's `postgres` extension — were each rejected for a reason
worth naming (publishes a database on the laptop; a background process the
recipe must babysit; a dependency downloaded at run time). What is left is
DuckDB writing CSV to stdout piped through `kubectl exec -i` into `psql \copy`.
It was measured *before* being designed around: 2,000,000 rows / 104 MB in
**1.9s**. That measurement is why full-grain `trips_clean` was publishable at
all — the estimate that would have killed it was wrong by an order of magnitude,
and the only way to find that out was to run it.

**(2) A number that agrees with a number nobody planned to compare.**
`monthly_kpis.kpi_04_undocumented_rows` counts distinct rows carrying a value
the TLC dictionary does not describe. It is computed here from `trips_clean` and
the domains in `configs/data.yaml`, by a completely different route from M1-S3's
one-off SQL. The eight monthly values sum to **527,386** — *exactly* the figure
in `docs/kpi_definitions.md`, including the subtlety that summing the
`unknown_domain_values` view instead would give 527,610 because 219 trips carry
two undocumented values at once. Same for KPI-08's exclusions: 318+300+…+421 =
**3,131**, the EDA's number to the row. Neither was engineered to match. Two
independent implementations landing on the same integer is the cheapest strong
evidence a data layer can produce, and it is worth deliberately setting up.

**(3) `kubectl apply -v=9` prints the patch, and the patch was one field.**
F-003 had been open since M0-S3: `kubectl apply` reported `configured` on every
run for a manifest that changed nothing. The one-attempt probe asked kubectl what
it was actually sending, and the answer was
`{"spec":{"volumeClaimTemplates":[…]}}` — nothing else. `volumeClaimTemplates`
is an **atomic** list in strategic-merge patch, so kubectl compares the whole
list against the live object, into which the apiserver has defaulted
`apiVersion`, `kind`, `volumeMode` and `status`. Our manifest omitted all four,
so desired could never equal live. Writing them out produced the first
`statefulset.apps/postgres unchanged` in the project's life, with generation
still 1 and the pod's creationTimestamp untouched.

**The concept underneath.** *A test you have not watched fail is a decoration,
and the cheapest way to keep watching is to make the failure a command.* The
protocol asks for one dbt test red-teamed on a seeded bad fixture. The easy
version is to break something by hand, paste the red output, and put it back —
which proves the test worked on one afternoon. Instead the fixture is checked in
under `seeds/redteam/` and `make marts-redteam` unions it behind a dbt var,
**inverting the exit code**: a green build with two impossible trips in it means
the tests are not testing, and the script says so and fails. The run also taught
something the README had predicted wrongly — the downstream tests do not go red,
they go **SKIP** (19 of them), because `dbt build` interleaves tests with models
and never hands a failing fact to the aggregates built on it. The README was
corrected to say so; a prediction that survives contact unedited usually means
nobody checked.

**What to look at.** `scripts/marts.sh` (the two halves, and the rejected
alternatives in its header) · `analytics/dbt/models/marts/monthly_kpis.sql` —
read the KPI-04 comment for why the obvious source is the wrong one ·
`analytics/dbt/seeds/redteam/README.md` · `scripts/postgres_databases.sh` (the
`\gexec` + `WHERE NOT EXISTS` form, because `CREATE DATABASE` cannot live in a
transaction) · `infra/manifests/postgres.yaml`'s `volumeClaimTemplates` block ·
`tests/unit/test_marts.py`, where every test's docstring names the failure it
prevents.

**What to try yourself.** Run `make marts-redteam` and watch the SKIPs — then
delete one line from `seeds/redteam/redteam_bad_trips.csv`'s duration column and
watch `tests/unit/test_marts.py::test_red_team_fixture_violates_the_range_it_targets`
catch you defusing your own red team. Then run
`kubectl apply -f infra/manifests/postgres.yaml -v=9` and find the PATCH body:
once you have seen kubectl show you its own diff, "it says configured but it
changes nothing" stops being folklore.


### M1-S3 — 3,131 rows out of 56 million, and what a survey costs when you actually read the sources (2026-08-16, role:DA)

**What was built.** Three documents and nothing else: `docs/eda_report.md`,
`docs/kpi_definitions.md` (10 KPIs, each with formula, source view, window and
owner), and `docs/prior_art.md` filled with **13 verdicts — 6 ADOPT, 3 DIFFER,
4 SURPASS** — from eight sources fetched live. No code, no cluster, no state
touched. Every number in the EDA came from a named DuckDB view through
`python -m taxi_mlops.data query`; no raw parquet was opened.

**Why this way — three things worth the reader's time.**

*(1) The number that teaches the most is a ratio of two numbers you already had.*
`CORR(fare_amount, trip_duration_minutes)` over all 56,127,878 rows is **0.0735**
— essentially nothing. Restrict to `fare_amount BETWEEN 0 AND 200` and it is
**0.8708**. The window excludes **3,131 rows, 0.0056% of the data, one in
17,927.** So the strongest money relationship in the dataset is completely
invisible until you remove one row in eighteen thousand.

The lesson is not "outliers matter", which everybody already agrees with while
continuing to compute means over raw columns. It is that **the damage is not
proportional to the number of bad rows, and it is not uniform across statistics.**
The *mean* fare barely moves (13.1740 → 13.1263, 0.36%) — which is exactly what
makes this dangerous, because someone checks the mean, sees it is stable,
and concludes the column is fine. Meanwhile the correlation moves by a factor of
11.8, and any MAX, SUM, variance or high percentile moves by orders of magnitude.
A previous session had already priced this as "12 rows move the mean by 0.26%"
and correctly declined to make it a rejection rule. That was right. What it could
not see is that the same 12 rows sit inside a population of 3,131 that destroys
every statistic *except* the one that was checked.

This is why `kpi_definitions.md` states a window inside each money KPI rather
than in a preamble, and why KPI-08 requires the **count of excluded rows to be
rendered on the same card as the value**. A windowed number whose exclusion is
hidden is worse than an unwindowed one, because it looks careful.

*(2) A survey where every verdict is "we're better" is a survey that didn't read
anything.* The protocol in `prior_art.md` warns about this in advance, and the
warning earned its place: the honest result was **six ADOPT rows**, six practices
these repos have and we do not. Commit-time secret scanning (we have a discipline
and one targeted test; they have a hook). Alert rules with a `for: 5m` sustained
condition and a documented `repeat_interval` — we had named our SLOs and never
the alert hygiene around them. Promotion gated on an HTTP test against the
actually-deployed container, not only on offline metrics. Feast features
timestamped at end-of-hour *so that a trip cannot leak into its own features*.
And the one that will save a whole session: **KServe's `canaryTrafficPercent`
does not work in Standard deployment mode** — it needs Serverless — which means
our M6 canary story was on course to hit a wall that a stranger's 0-star
repository documented in one line.

That last point is the transferable one. Ranking the search by stars surfaced
awesome-lists and course forks. The two most useful sources found today have
**zero stars each** — a KServe install log and a Feast implementation — because
operational specificity and popularity are close to uncorrelated. The survey was
worth running only because it was run as *reading*, not as *citing*.

*(3) When your scope does not cover a gap, say where the gap is in the artifact
itself.* F-005 (the rejected rows exist only as counts) proposed this story as
its home. It genuinely did not fit — a sidecar means changing ingest, re-running
57M rows, rewriting the `data/processed/` artifacts a previous session had just
proved byte-identical, and re-earning that proof. So it was judged out of scope
and routed to the Architect, **with the reasons written down**. But the EDA does
not quietly proceed as though the data were complete: §0 is titled with the
boundary and states that everything following describes 98.397% of the delivery,
and §2 says of the 159,300 trips removed for exceeding two hours that this
report "cannot answer and does not guess" what they were. The finding was
strengthened rather than deferred — the EDA also discovered that the rejection
rate is *not stationary* (1.428% → 2.020%, +41% relative across eight months)
and that the val and test months are the two dirtiest, which are new arguments
the Architect now has and did not before.

**The concept underneath.** *Aggregate statistics have wildly different
sensitivity to contamination, and the robust one is the one people check.* Means
are robust to a handful of extreme values; correlations, sums, maxima and
variances are not. A data-quality process that validates by comparing means will
pass data that has been rendered meaningless for every other purpose. This is the
statistical cousin of a lesson this program keeps relearning in other clothes: at
M0 a readiness check passed a service scaled to zero (gotcha #29), and at M1-S2 a
rebuild proof would have validated itself against its own output (gotcha #33).
Each time, the check was real, the check was green, and the check was looking at
the one quantity that could not move.

**What to look at.** `docs/eda_report.md` §8 (the correlation collapse) and §7b
(the `congestion_surcharge` cliff between 2019-01-20 and 2019-01-21 — a column
that is 63% null in one training month and clean in every other, which would be
invisible in validation because validation is July). `docs/prior_art.md` rows
1–6, the adopts. `docs/kpi_definitions.md` KPI-08, and KPI-09/KPI-10 which are
defined but recorded as **"not yet measured — M2 owns the first value"**.

**What to try yourself.** Run the two correlations and watch the number move:

```bash
make duckdb
python -m taxi_mlops.data query "SELECT CORR(fare_amount, trip_duration_minutes) FROM trips_clean"
python -m taxi_mlops.data query "SELECT CORR(fare_amount, trip_duration_minutes) FROM trips_clean WHERE fare_amount BETWEEN 0 AND 200"
```

Then the harder exercise, which is the point of §11: build the reference floor
yourself. A `GROUP BY (hour, day-of-week, PU, DO)` median fitted on `trips_train`
scores **3.7170 min MAE** on `trips_val` and lands within five minutes on
**78.693%** of trips. Any model that does not beat 3.72 has learned nothing a
SQL query does not already know — and the *constant* baseline (7.8866) is the
flattering floor that makes any model look good. Notice how much more comfortable
it would be to quote the second number, and that this is exactly why the first
one is written down.

### M1-S2 — Two witnesses, a pin that must not touch what it measures, and a review that found four things (2026-08-16, role:DE + DA hat)

**What was built.** `data/raw` and `data/processed` went under DVC with a
file-system remote *outside* the repo; `make data` became the whole path
(ingest → DuckDB → pin, in that order); `data/analyst.duckdb` became nine
**views** — no rows copied — that the DA queries by name; and `make
rebuild-proof` turned the M1 gate's byte-identity leg into a command anyone can
re-run. It ran: `data/processed/` deleted, rebuilt by one command from
DVC-pinned raw, **8 of 8 outputs byte-identical**, 56,127,878 rows reconciling
month by month against what S1's reports claimed. Then the Data Contract Review
raised four challenges, two of which changed the shipped code. 79 unit tests
(was 57), no cluster, no network.

**Why this way.** Four choices, and the interesting ones are the refusals.

*(1) The proof must not write to what it measures.* The obvious rebuild proof is
"wipe, run the rebuild command, compare hashes". But the rebuild command ends in
`dvc add`, which re-hashes the outputs and rewrites the pin — so the comparison
would be against a pin computed from the very bytes under test. It would pass
forever, including on the day the parquet writer stopped being deterministic.
Hence `SKIP_DVC=1`, which exists for exactly one caller and says so in a comment
at both ends. This is the whole genre of green-forever test: not wrong output,
but a test whose reference moves with its subject.

*(2) Two witnesses, computed differently.* The proof compares our own sha256
table AND asks `dvc status data/processed.dvc` — different code, different
metadata, same question. One witness agreeing with itself is not evidence; it is
a tautology with a checkmark. The same instinct as M1-S1's two rejection counts.

*(3) The remote is a directory outside the repo, and MinIO was refused.* The
tempting choice was MinIO — it is already running, it speaks S3, it would demo
beautifully. It lives on a PVC inside the kind cluster, and `make destroy` takes
PVCs with it. A backup that dies with the thing it protects is worse than no
backup, because you stop worrying. The honest cost is written down rather than
hidden: the remote is on the same physical disk, so it survives `make destroy`
and a wrong `rm -rf`, and it does not survive disk loss.

*(4) `dvc init` turns analytics on, and a default is not an exemption.* The init
banner says it plainly and then scrolls away. This program's rule is one
sentence — nothing leaves this machine — so the fix was `core.analytics false`
plus a unit test, because a future `dvc init` on a fresh clone would restore the
default silently.

**The concept underneath.** *A number that reconciles is worth more than a
number that is merely produced.* Every piece of this story is the same shape
twice: the analyst layer does not just publish `trips_clean`, it exits 1 if the
view's row count disagrees with the ingest report that wrote the data — because
a catalogue pointing at five months of eight answers every query happily and
just returns smaller numbers, which is a failure with no symptom. The rebuild
does not just re-run, it re-runs and is checked from two directions. The review
does not just read the contract, it runs queries against it. The recurring enemy
is the *silent* wrong answer, and the recurring weapon is a second, independent
statement of the same fact.

The review is where this paid off most. The DA read a contract that S1 had built
carefully and, in four queries, found: 914,459 rejected rows that exist only as
counts (so nobody can say whether the 159,300 trips over two hours were meter
faults or a real long-haul population); a 261,781-row null batch that is
**exactly** coincident across four columns, one of which encodes it as
`payment_type = 0` — a value that reads on a dashboard as a payment category;
a `$671,123.14` taxi fare against a 99.9th percentile of `$85.50`; and
`VendorID 5`, which appears 219 times in 56 million rows and **only ever inside
the broken batch**. Two of those became a change (`unknown_domain_values`, which
reports without cleaning), one was answered with the number that settles it (12
rows; the mean moves 0.26%), and one was carried as a finding with the DA's
dissent recorded rather than argued away. A review that produces no change is
not a review, and a review whose disagreement disappears into consensus is worse.

**What to look at.** `scripts/rebuild_proof.sh` — read the header, then the
`SKIP_DVC=1` line, then gotcha #33; they are one idea in three places ·
`docs/rituals/2026-08-16_data-contract-review.md`, especially §4 Dissent ·
`src/taxi_mlops/data/analyst.py`'s module docstring on why `split` and `month`
are config literals and never parsed from filenames · `ledgers/findings.md`
F-005, an item deliberately NOT converted into debt.

**What to try yourself.** Break the proof on purpose, both ways, and watch which
guard catches you: append twenty bytes to a file in `data/raw/` and run `make
rebuild-proof` (it refuses at step 2 and deletes nothing — the input is not the
pinned bytes); then `uv run dvc checkout data/raw.dvc --force` and instead drop
one row from a file in `data/processed/` before running it (the rebuild restores
the true bytes, so the table prints `NO` next to that one filename). Then try
the version that *should* worry you: delete `SKIP_DVC=1` from the script and run
the second experiment again. It passes. Sit with that for a moment — that is
what a green test looks like when the reference moved with the subject.

### M1-S1 — A contract that can say no, and 914,459 rows that were counted out loud (2026-08-16, role:DE)

**What was built.** `taxi_mlops.data` became real: `make ingest` downloads the
eight configured months (skip-if-present, retried, sha256-pinned in
`data/raw_manifest.json`), reads them, applies a **year-aware pandera contract**
and the one and only dtype cast in the codebase, derives
`trip_duration_minutes`, drops impossible rows against **named, counted rules**,
re-validates the result against an output contract, and writes each month under
its split. 57,042,337 rows in, 56,127,878 out, 914,459 rejected — 1.603%, every
one of them attributable to a rule by name. Two red-teams: a seeded corrupt
parquet (`CorruptSourceError`, exit 1, `processed/` never created) and a
truncated pinned file (`ChecksumDriftError`, exit 1, the existing output's
sha256 and the manifest pin both untouched). 57 unit tests, no cluster, no
network.

**Why this way.** Three choices did most of the work.

*(1) Structure refuses; rows get counted.* A missing, renamed, or unknown column
refuses the entire month — you cannot drop your way out of a column that isn't
there. A passenger count of 42 is one bad row, so it is counted against
`passenger_count_out_of_range` and dropped. Collapsing those two into one
mechanism is how data pipelines end up either crashing on a typo or silently
shipping a thinned month; `max_rejected_fraction` (0.10) is the seam between
them — past it, cleaning becomes refusal again.

*(2) Two counts per rule.* `rejected_by` attributes each dropped row to the
**first** rule it violates, so the column sums exactly to rows-dropped and the
table balances. But that alone makes any rule sitting behind an overlapping
earlier one read `0` — indistinguishable from a rule that has stopped working.
So `matched` reports independent hits alongside. In 2019-01 the difference is
loud: `distance_non_positive` shows 11,446 attributed against 55,089 matched —
44 thousand zero-distance trips were *already* rejected as too short. One number
would have hidden that; two make it a fact about the data.

*(3) `nullable: false` in the config means a POST-clean guarantee.* The input
contract is deliberately permissive about nulls, because raw is raw. The output
contract enforces the guarantee *after* the rules have run — which turns it into
a live check on the rules themselves. If `location_out_of_range` ever stops
firing, the output contract refuses the month instead of handing an out-of-range
zone id to a model six milestones later. There is a test that breaks that rule
on purpose to watch it happen.

**The concept underneath.** *Schema drift has three shapes, and only one of them
is loud.* Gotcha #6 said TLC adds columns by year, so the contract was built
year-aware. Diffing 2019's arrow schema against a live 2025 probe — 30 seconds
of curl, because the project's rule is observe-don't-remember — showed the other
two shapes. `airport_fee` becomes **`Airport_fee`**: same field, capital A. And
six columns change physical type (`VendorID` int64→int32, `passenger_count`
double→int64, and so on). An *added* column announces itself the first time
something asks for it. A *renamed* one hands you an all-null column that looks
exactly like missing data. A *retyped* one doesn't complain at all — it just
makes two years quietly disagree. That is now gotcha #31, and the contract
answers all three the same way: `aliases` that are announced when applied, and
one canonical cast that makes every year the same table by construction rather
than by luck. The general lesson is worth more than the taxi data:
`set(columns) == set(columns)` is not "the schema is stable" — diff the types
too, and diff case-insensitively before you conclude anything is new.

**What to look at.** `configs/data.yaml` — read the comments as much as the
values; each number is there because something was observed, and the file says
what · `src/taxi_mlops/data/contract.py` docstring, which states the
structure-refuses/rows-get-counted split in four lines · the two-column
rejection table any `make ingest` prints · `tests/unit/test_data_clean.py::
test_every_named_rule_fires_exactly_once`, which builds one victim row per rule
so that no rule can be decorative · `docs/gotchas.md` #31.

**What to try yourself.** Truncate a raw file (`head -c 5000000 x.parquet`) and
run `make ingest` — watch it refuse at the *pin*, before it ever opens the
parquet, then confirm the existing output's sha256 didn't move. Then delete that
month's entry from `data/raw_manifest.json` and run again: now the same file
reaches the reader and refuses with a different typed error. Two failures, two
names, two places — that is what "typed refusal" buys. Finally, set
`on_unknown_column: warn` in `configs/data.yaml`, add a junk column to a frame
in the tests, and decide for yourself which policy you'd want at 3am.

---

## M0

### M0-S4 — Destroying it on purpose, and a preview that wasn't (2026-08-16, role:MLOps + SRE hat)

**What was built.** Nothing new, and that is the story: the platform three
sessions had carefully assembled was deleted (`make destroy`) and rebuilt from
the recipe alone (`make cluster-up deploy-platform`), then re-gated
(`make verify-m0` → 18/18 GREEN, exit 0). Both helm releases came back at
`REVISION 1` — the proof it was a genuinely fresh cluster and not an upgrade
wearing a rebuild's clothes. Alongside it, the M0 gate's required kill-switch
drill: `automation/STOP` present → the scheduler refuses (`[chain] STOP file
present — not scheduling.`, exit 0, daily counter untouched at 4, no log file
created), STOP removed → the chain schedules its real successor. Two fixes
rode along, both earned by the story rather than planned into it.

**Why this way.** The rebuild's value is entirely in *what it measures*, so the
before/after was instrumented rather than eyeballed. Two fingerprints were taken
before the teardown — `sha256sum .env` and a deliberately created MLflow
experiment, `m0s4-pre-destroy-witness` — and re-read after. The `.env` hash came
back byte-identical (`34cde86f…`), which is what makes the rebuilt Postgres and
MinIO accept the same credentials; the experiment came back
`RESOURCE_DOES_NOT_EXIST`, because the PVCs went with the cluster. That
asymmetry IS the deny list's design: secrets are user-created and unrecoverable,
so `destroy` may never touch them; tracking data is regenerable by re-running
the pipeline, so it is allowed to die. A sentinel file was planted in `data/raw`
for the same reason and read back intact, then removed.

**The concept underneath.** *A dry run must cover the most expensive deletion
first, not last.* The story's very first command — `make destroy DRY_RUN=1`, run
to check the preview before trusting the real thing — deleted the entire kind
cluster and then printed `[destroy] DRY_RUN=1 — nothing was deleted.` The file
loop was guarded; `cmd_down` sat one line above the guard. It cost nothing only
because the next command was going to destroy the cluster anyway, which is luck,
not process.

The second half is worth more than the bug. A test named
`test_destroy_dry_run_deletes_nothing` had been green since M0-S2. It ran
against a sandbox whose kind config named a cluster that cannot exist — so the
delete path always no-opped, and the test could not have failed if it tried.
**The isolation that made the test safe made it blind.** The repair is not "test
against a real cluster" (that is how you delete a real cluster); it is to give
the sandbox a fake `kind` that *records* its calls and assert on the recording,
plus a positive control proving the fake fires when it should. Same shape as
gotcha #29 from the previous story, one level up: there, a PASS branch nobody
had watched be wrong; here, a FAIL branch that could never be reached.

The kill-switch drill has the same seam. The half a human can drill by hand —
STOP present when you *ask* for a session — is the easy half. The half that
matters at 3am is STOP created *after* a session is already scheduled, while it
sits in its `sleep`; drilling that live means either launching a real Claude
session or trusting a guard nobody watched work. So it is tested instead, in
`tests/unit/test_chain_script.py`, against a sandboxed copy of the scheduler
whose `claude` is a shim that drops a marker file. Four properties, each really
executed: it launches when nothing stops it (positive control first, or every
refusal below proves nothing), it refuses outright with STOP present, STOP
written *after* scheduling still kills the pending session, and the daily cap
halts the chain while leaving a note where the PO actually looks.

**What to look at.** `scripts/cluster.sh` `cmd_destroy` — the DRY_RUN branch and
the `DENY` array above it, read as a pair · `tests/unit/test_cluster_scripts.py`
`_sandbox_with_live_cluster` (the recording shim) · `tests/unit/
test_chain_script.py` (the kill switch, tested where a real session cannot be
spawned) · `docs/gotchas.md` #30 · `ledgers/deployments.md`, whose newest row
carries the survived/died measurements.

**What to try yourself.** Revert the four-line DRY_RUN guard in
`scripts/cluster.sh` and run `uv run pytest tests/unit/test_cluster_scripts.py`:
the new test fails and quotes `[cluster-down] deleting kind cluster` sitting
directly above `nothing was deleted` — that pairing is what a blind test looks
like when it finally opens its eyes. Then delete the whole platform and rebuild
it while timing yourself; if the rebuild is boring, the recipe is real, and if
any step needs a human to remember something, that step is not in the recipe yet.

### M0-S3 — The platform: MinIO, Postgres, MLflow, and a gate that says no (2026-08-16, role:MLOps)

**What was built.** `make deploy-platform` brings up the three services the whole
program leans on — MinIO (the S3), one Postgres (the one database), MLflow
(tracking + registry) — and `make verify-m0` proves it in 18 sub-checks, exit
nonzero on any miss. MLflow's UI answers at http://localhost:5000, MinIO's
console at :9001, and MLflow's artifacts really land in MinIO while its runs
really land in Postgres. Credentials are generated into a gitignored `.env` and
pushed into Kubernetes Secrets by `scripts/platform_secrets.sh`; no secret is
ever printed, and none is in git.

**Why this way.** Five choices worth the ink.

*(1) Postgres by plain manifest, not by chart.* The obvious pick, bitnami's
`postgresql`, today defaults to `registry-1.docker.io/bitnami/postgresql:latest`
— a rolling tag — and its pinned tags now live in a frozen `bitnamilegacy`
registry. The MLOps charter refuses unpinned versions, so the "standard" chart
would have forced either an unpinned image or a dependency on a deprecated
registry. Fifty lines of YAML we own, with the image pinned by digest, is the
cheaper honest answer. Note the shape of that decision: the popular choice was
rejected on a *property* (pinnability), not on taste.

*(2) MLflow by community chart, and the reason is a missing driver.* MLflow's own
image ships without `psycopg2` or `boto3` — so a Postgres backend plus S3
artifacts needs an image somebody builds. M0 builds no image of ours (that
decision is parked as debt D-001 until M4), and the community chart's image
carries both drivers. So: chart where the chart earns its keep, manifest where it
does not. "Use helm for everything" is a policy; "use the thing whose failure mode
you can live with" is engineering.

*(3) The host route is declared, not forwarded.* `kubectl port-forward` is a
process a human has to remember to start — a manual deploy step wearing a
disguise. Instead the kind config maps hostPort 5000 → containerPort 30500, and a
Service claims nodePort 30500. The cost is honest and worth naming: kind
publishes ports only at cluster-CREATE time, so adding a port means destroying
and rebuilding the cluster. The benefit is that a fresh `make cluster-up` on a
new laptop gives you localhost:5000 with nobody typing anything.

*(4) `.env` is the source of truth, and it is generated once.* Re-generating
passwords on every deploy would be "idempotent" in the trivial sense and
catastrophic in practice: the old password is already baked into the Postgres data
directory. So the script generates only when `.env` is absent, then converges the
Secrets to it every run. This is why `.env` is on `destroy`'s protected list.

*(5) MLflow gets its own MinIO identity.* The chart ships a default user
`console`/`console123`; overriding the user list removes it, and MLflow
authenticates as `mlflow` with `readwrite` — so a leaked MLflow credential cannot
reconfigure the object store. The access key is a *username* and lives in git; the
secret key never does.

**The concept underneath.** *Verify the thing, not a proxy for it.* This story's
best moment was a failure of my own check. `verify-m0` asked "did the Deployment
roll out?" — and when the red-team scaled MLflow to **zero replicas**, `kubectl
rollout status` answered *"successfully rolled out"*, exit 0, because zero
replicas is a complete rollout. The script printed a green line for a service that
had ceased to exist, while every URL check beside it failed. Readiness is now
asked as a number (`readyReplicas >= 1` **and** `== spec.replicas`), and the
lesson is bigger than kubectl: a check whose PASS branch you have never watched be
wrong is a check you have not tested. That is gotcha #29. Its sibling, gotcha #28,
came from the same session's first deploy: MLflow logged *"Application startup
complete"* four times and then vanished — OOMKilled at exit 137 by its own default
of four uvicorn workers. The logs were clean, because a process does not get to
log its own OOM kill. **When a container dies without complaining, read the pod
object, not the log stream.**

**What to look at.** `scripts/verify_m0.sh` (start at `workload_ready` and the
comment above it — that is the red-team's scar) · `infra/manifests/postgres.yaml`
(the header argues the chart-vs-manifest choice) · `scripts/platform_secrets.sh`
(the chain of custody from `.env` to pods) · `tests/unit/test_platform_scripts.py`
(the port-twin tests: two files holding the same number, and a test that fails
when they drift).

**What to try yourself.** Run `make verify-m0` — it should be green. Now break it
on purpose, three different ways, and predict the output before each: `kubectl -n
platform scale deployment/minio --replicas=0`; `kubectl -n mlflow delete secret
mlflow-s3`; change `nodePort: 30500` in `infra/manifests/mlflow-nodeport.yaml` to
`30501` and re-apply. Which failures does the gate catch loudly, which one does it
catch only through a URL, and which one does `make test` catch before you ever
reach the cluster? Then run `make deploy-platform` and watch it put everything
back.

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

## M7-S4 — a number that was true where it was written, applied where it is not

Two findings landed this story and they turned out to be the same shape.

**F-022.** A bake-off row resolved the champion **by alias** — deliberately, so
the table judges what is actually serving — and *also* pre-registered
`feature_set="v1"`. Both true the day they were written. The bake-off's own
promotion then moved the alias to a v2 model, and every invocation since has died
at a refusal that was correct one layer too late.

**F-020.** A tuned `min_data_in_leaf: 1293` was chosen on 15% of train and applied
at 100%. Same integer, and it means *1 row in 5,103* where it was chosen and *1 in
34,020* where it was used — 6.7× less regularising, silently.

The generalisable lesson is the distinction that fixes both: **pre-registration is
right for a thing declared before its number existed, and exactly wrong for a
pointer designed to move.** A Spec that names an arm's identity should be frozen;
a Spec that names "whatever is serving" must resolve from the artifact. And a
hyperparameter is not a number — it is a number *plus the scale it means it at* —
so transferring one between scales is an operation, not a copy.

Three smaller things worth keeping:

* **A guard that fires on your own commit is the guard working.** `make
  retrain-schedule` refused to deploy because a script I had just committed was
  not in the task image. The instinct is to narrow `IMAGE_PATHS`; the correct move
  is six minutes of `make image-load`. A guard you narrow to pass your own change
  is a guard you have deleted.

* **"Every task in this file declares X" breaks the first time the file gains a
  task that is not one of them.** Three wiring guards went red for a correct
  addition (gotcha #50, sixth time). The repair was not a longer allow-list: the
  pipeline's task set is now *what `main` awaits*, asked of the AST — derived, so
  it stays true for additions nobody has thought of.

* **A cheap arm can be a better proof than an expensive one.** The scheduled-run
  proof plans only: it exercises the trigger, the pod, the image, the wiring, the
  registry read and the record write, and stops before the hour of CPU. A proof
  that fitted would have been measuring the fit.

## M7-S4 (completion leg) — the last 5% of a long job is the part no test has run

The retrain fitted for twenty-eight minutes, cleared the honest floor at +3.30%,
was correctly refused by the incumbent condition — and then crashed writing the
verdict into a file, on `c.text`. The `Check` dataclass carries
`name`/`passed`/`detail`. It never had a `text`.

**The typo is not the lesson. Two things had to be true for it to reach a
28-minute run, and both generalise.**

The access was *guarded*, and the guard was on the wrong object:
`[... for c in decision.checks] if hasattr(decision, "checks") else None`.
`Decision.checks` is a dataclass field, so it is always present and the guard
never protected anything — what it did was put the word `hasattr` one token to the
left of an unchecked access and make the line read as careful. **A guard on the
container tells you nothing about the elements**, and a defensive-looking line is
harder to see past than a bare one.

And every test of that module asserted on its **source text** — `'"ended_by"' in
RUN_SOURCE`, an `ast` walk for a forbidden verb, `"43_987_422" not in
RUN_SOURCE`. Those are the right instrument for the properties they check: laws
with no runtime symptom. They are the wrong instrument here, and the sentence
worth carrying is **a string test sees a field being written; it cannot see that
the field does not exist.** Nothing had ever executed the line, for a reason that
felt like good judgement at the time: executing it cost the fit.

So the repair is structural rather than a `try`. The serialiser is a function now,
callable in microseconds, and its tests build a real `Decision` through the real
gate from the crashed run's own numbers. The question to ask of any long job:
**if the last five percent raises, what did I spend and what do I keep?** Here the
answer was tolerable only by luck — the model was already in MLflow with its
signature, so what was lost was the record, which is the artifact this program
actually judges by.

**The second defect is the one I would not have predicted.** The traceback exited
with a status that this program had already given a meaning. `0/1/2/3` are
*passed · refused · could not be built · no verdict*, so the detached job's
`.status` file said `FAILED 2` and the handoff's decoding key turned that into
"the challenger could not be built" — about a challenger that had been built,
fitted and judged. My boot ritual read that sentence and believed it for about
ninety seconds, until the log disagreed. **If you design an exit-code vocabulary,
you have to handle the case you did not enumerate**, outside the vocabulary, with
a message saying what is and is not true. And note the near-miss: an uncaught
Python exception exits **1**, which here means REFUSED. A crash would have been
read as a verdict.

**One thing went right and it is worth naming.** The prediction file. Before
re-running I wrote down what the re-run had to reproduce — every metric, the
verdict, the best iteration — so that a repeat of a 28-minute fit is a
determinism check rather than a do-over, and a discrepancy would be a finding
instead of an inconvenience. It costs five minutes and it converts spent compute
into evidence.

**And the smallest one, which happened live.** The test I wrote to forbid
`hasattr` in the repaired function went RED against the repaired function — on its
own docstring, which quotes the guard it forbids. Gotcha #53/#68 for the seventh
time, inside the test written about the lesson. Prose is load-bearing in this
repo; a check about code structure has to parse code, and knowing that is not the
same as remembering it while typing.

---

## M7-S4 completion leg (2026-08-20) — the prediction paid off, and the vocabulary died at the launcher

**The five minutes spent on the prediction file returned the whole session's
confidence in one command.** The re-run reproduced all twenty predicted fields:
3.2412 and 81.568% on the holdout, 3.3811 on val, best iteration 779 of a 2400
cap, `early_stopping`, REFUSE on exactly the two incumbent conditions. Because
that claim was committed *before* the fit was launched, "it matched" is not a
sentence I am asking anyone to trust — `make retrain-prediction-check` resolves
each field against the machine-written record and returns 1 if any of them
disagree. Two MLflow runs of one configuration, half an hour apart, agreeing to
the last kept digit is also the second determinism observation this program
holds. **Writing down what an expensive thing must produce is how you get two
results out of running it once.**

**Then the status file lied for the third session in a row, and this time nothing
in the repository was at fault.** The previous leg added exit **4** so a crash
could not wear a verdict's clothes. The re-run refused correctly — CLI exit
**1** — and its `.status` read `FAILED 2`, which in this vocabulary means *the
challenger could not be built*. The cause is `make`: **GNU make exits 2 for any
failed recipe**, so 1, 3 and 4 all arrive as 2, and 2 was already spoken for.
Every code the last session carefully designed is unreachable through the only
launcher this program uses for long jobs.

**The interesting part is what NOT to do about it.** The obvious fix is a `CMD=`
escape hatch on `make detach`, so an exit-code-carrying job is detached as the
command rather than as the target. It works, and it puts the recipe in two
places — the Makefile and the launch site — which is the twin this repo spends
its time eliminating. So the fix is a rule instead of a mechanism: **stop reading
verdicts out of exit codes.** A refusal writes a record; a crash writes nothing;
the record's presence and its `verdict` field survive every collapse, and that is
gotcha #59's *assert positively on the artifact* arriving in a place I did not
expect it. The two cheap mitigations beside it are the recipe echoing its own
`$?` into the log and re-exiting with it — and re-exiting matters as much as the
echo, because a recipe that swallowed the code to make the line printable would
turn every refusal into a green `make`.

**And the checker went red for its own reason before it went red for mine.**
Three of the four red-team tests failed on `Path.relative_to` — the tampered
copies live in a pytest tmpdir, outside the repo, and the header formatter
assumed otherwise. Gotcha #55's family, in the artifact I was writing to avoid
exactly that class of thing. A verifier that dies formatting its own header
reports a defect in whatever it was pointed at.


---

## M7-S5 leg 1 (2026-08-20) — the average was weighted by exactly the rows that vanished

**Every honest monthly number about March 2020 understates it by roughly the same
ratio, and the ratio is 68:3.** The month's mean trip duration is 13.1645
minutes against January's 13.2123 — a 0.36% move, smaller than an ordinary
month-to-month wobble. Its whole-month MAE is 3.3227 against 3.0295. Its most
moved input column sits at PSI 0.0217, *lower than an accepted July 2019*. None
of those numbers is wrong. All of them are dominated by the ten ordinary days at
the head of the month: 68.231% of March's rows fall before the 11th and 3.321%
after the 21st. **A row-weighted average of a collapse is weighted by exactly the
rows that disappeared** — which is the mechanism behind F-045, and it is worth
saying in that form because it generalises past this dataset to every aggregate
computed over a period in which the population changed size.

**The alert that mattered was the one measuring a quantity that cannot be
averaged away.** PSI is a distance between shares; halve every count and it is
exactly zero. So input drift correctly stayed silent — the city did not start
taking different taxi trips, it stopped taking taxi trips — and volume, a
marginal nobody would have added if PSI had felt sufficient, is the only
instrument that fired. Writing that argument down *before* the run (M7-S3 did)
is what turned a lucky catch into a demonstrated design.

**The signed error is the number that reads as a diagnosis.** KPI-14 says March
was worse. KPI-16 says the champion was quoting **five minutes too long** on the
26th — mean actual 9.699 minutes against a mean quote of 15.019 — and had been
climbing steadily since the 9th without once going negative. Those are opposite
fixes: a model that is too slow and a model that is too fast look identical
under an absolute error and share no remedy. **An unsigned metric can tell you a
model is wrong; it cannot tell you which way, and "which way" is the whole
content of the incident report.**

**The best days in the collapse are the days the model was already told the city
would be quiet.** Weekend error sat 31.4% below weekday error in late March,
against 13.5% in an ordinary January, and the dips in the daily series land
exactly on the four weekend dates. `dayofweek` is the model's only vocabulary
for "quiet city" and it is a seven-valued one — so the model had a word for what
was happening and could reach it two days in seven. That is a more useful way to
read a feature's contribution than any importance plot: **look for the days the
model was accidentally right, and ask what it already knew on them.**

**And a ratio that refuses to move is evidence.** The airport error gap has been
open in `docs/error_memo_m2.md` §7 row 2 since M2, with two readings — distance,
or dwell and traffic. Here the roads emptied and the median trip went 49.3%
faster, and the gap sat at 1.86–2.00× in ordinary periods and 2.07–2.35× through
the collapse. If the penalty were carried by distance, the one term whose
minutes-per-mile changed, the ratio had to move. It did not. **A quantity that
holds constant across a regime change discriminates between hypotheses that a
quantity measured once cannot** — three measurements, from three instruments, in
two different worlds, and only the third could rule anything out.

**Craft note, cheap and reusable:** `--verify` ran one card per dashboard and was
green; running *all thirty-six* took twenty lines and is now `make board-cards`.
Gotcha #78 said an empty panel is a failure, and the Grafana boards learned it
the expensive way at M6-S1. Applying an existing lesson to the next surface it
fits costs almost nothing and is the cheapest verification in the repo.

---

## M7-S5 leg 2 — the M7 gate: what a milestone gate is for, once you have six of them

**A gate's first run is a survey of soft ground, and this one found twelve
pieces in three minutes.** None of them was a defect in M7's work. Two were the
gate calling an API it had guessed at; one was a record whose field is named
`rows_validated` and means *rows read*; one was a doc table quoting `202,574.4`
where the check compared `202574.4`; one was a board's own *prose* saying the
daily series was "flat at its floor", matched by a scan for a forbidden column
called `floor`; one was the sentence `KPI-09/KPI-10 belong to the held-out
split` reading as a published value because `KPI-10` contains `10`. **Writing
the checks is how you find out what your records actually say**, and the yield
is highest on the first run and drops to almost nothing by the third.

**The most useful thing this gate did was go red about the world rather than
about the repository.** Its one live PromQL query returned zero drift series
against three tracked records saying there should be three. Nothing had drifted:
the pushgateway pod had restarted after a host reboot, and a bulletin board
keeps nothing. The consequence is the finding — **A-10 exists to catch a stale
drift number and cannot fire on an absent one**, because `time() - max by
(month)(...)` over no series is no series. The SLO document had argued, correctly
and at length, that a pushed metric *persists* after its producer dies; it is
the same property, and the guard built from it is blind to the case where the
board itself went away. **Any rule of the form "this value is too old" is silent
about the value not existing**, and only `absent()` sees the second one.

**Then the design question, which is the part worth keeping.** Making that a
FAIL would turn the M7 gate red for a laptop reboot with no defect behind it —
gotcha #50, which this program has now watched fire six times. Making it a pass
would hide a real hole. The way out was to ask the **pair**: either the series
are present, or the gateway restarted since the drill pushed them, checked on
two clocks. An absence with nothing accounting for it is still a FAIL, so the
check degrades in the correct direction, and the passing line names the finding
and prints the one command that fixes it. **When a check has a state it cannot
honestly call good or bad, the fix is usually a second clause that explains the
state, not a looser bar.**

**Gotcha #50 fired again while this was being written, on a neighbour.**
`verify-m6` had gone RED — not from anything in this story, but because M7-S3
had *closed* F-035, and the leg required the documented-absence list to be
NON-EMPTY. A guard asserting "there are still two signals we cannot alert on"
is a guard that fails the day somebody fixes them. The repair is the one this
program keeps re-learning: assert the **agreement** (the rules implement exactly
what the renderer declares, and whatever is absent is documented), which is true
before the closure and after it. Same leg also read the renderer's sets with
`ast.literal_eval` and silently got nothing once they became comprehensions —
**a guard degrading into a guard about its own parser** is the quiet version of
the same disease.

**And the checker-of-the-checker lesson, which was new.** Three needles in
`test_verify_m7.py` matched words instead of invocations, and all three were the
gate quoting *itself*: `--push` inside the advice line it prints for an
operator, `ingest_month` inside the `ingest_months` view it reads, `retrain(`
inside the sentence reporting what `ast` had found about `retrain`'s signature.
#35 and #68 said prose must not sit where a parser reads it as code. This is the
mirror image: **the more a checker explains itself, the more of its own
vocabulary ends up in its output, and the more surface it offers the checker
above it.** For the third one no anchor helps — the sentence is legitimate — so
the property had to change: the gate must never *import* the callable it
inspects.

**Craft note.** The red team's value is entirely in how plausible the plant is.
This one rewrites a volume ratio from a ratio of RATES to a ratio of TOTALS,
derived from the record's own fields, wrong by one percentage point, and still
under the bar — so the alert still fires and the story still reads the same. It
is F-045 itself, the finding this whole milestone is about, turned against the
milestone. And the drill asserts one leg must stay **GREEN**: the bar-daylight
check has no reason to complain about the planted value, and a gate that went
red there too would be a gate that fails on any edit rather than on a wrong
number. **Assert what must not fire. A drill that only predicts "something goes
red" cannot be wrong.**


---

## M8-S1 leg 1 — the drift surface, made trustworthy (2026-08-21, EXEC/Opus 5)

**The lesson worth carrying: a ratio whose denominator is derived from the data
it measures is not monotonic in the thing it watches.** A-9 divided trips by
*days on which trips happened*, so a day with no trips left the numerator and
the denominator **together** — and the ratio therefore answered "how busy were
the days that happened", which *rises* as a shutdown deepens. On the real COVID
month, deleting the eight quietest days — a strictly worse world — walked the
ratio from 0.3913 to **0.5143 and silence**. The doc and the alert's own
annotation both said "trips per day", and nobody reading either would have
guessed "per day on which trips occurred".

Two habits come out of it. **Derive a denominator from something the numerator
cannot move** — here the calendar, the same authority the milestone gate already
trusted for the mart's grain. And **assert monotonicity as a property test**: a
signal whose whole claim is that it sees the marginal another instrument is
blind to has to be monotonic in that marginal, and no test asserted it because
every month that had ever shipped happened to hold all of its days. The
load-bearing test here is the negative one — *the OLD denominator must still be
non-monotonic* — so the defect cannot come back as a tidy-up.

**The counterfactual had to be re-run through the shipped code, and that is not
pedantry.** REV's re-derivation deliberately does not import the module under
review, which is exactly right for a review and exactly useless as proof of a
fix: re-running it would print the same two columns whatever the code now does.
The new script drives `drift.calendar_days` and `drift.trips_per_day` and keeps
the old denominator beside the new one **as a control** — it FAILS if the old
arithmetic stops reproducing the finding, because a table showing only the new
series falling is consistent with a month that was never at risk.

**Two halves of one fix, and each is dishonest alone.** F-050's pair: a
PersistentVolume without an absence rule leaves nothing watching a real
deletion; an absence rule without the volume pages on every laptop reboot and
teaches its reader to ignore it. The boundary decided them together *because the
recurrence had been measured* — three host restarts in 24 hours. That is the
shape to copy: a frequency measurement turned a taste question into an
arithmetic one.

**And the drill that proved it earned its negative predictions.** The check that
matters is not "A-11 fired" — it is that **A-10 stayed inactive through a total
loss of the drift surface**. If A-10 had fired there, A-11 would be redundant
and the finding would have been wrong. `time() - max(X)` over zero series is
zero series, not a large number: any rule of the form *this value is too old* is
silent about the value not existing.

**The session's free lesson, found by its first command.** `make backup` had
been running `make restore-drill` on every invocation since 2026-08-19, because
the manifest's own prose named the target in backticks inside an unquoted
heredoc. Gotcha #60, second occurrence — and the real finding is not "escape
backticks", it is that **#60 came back because the lesson had no test**. One
exists now, repo-wide over every heredoc in `scripts/*.sh` and the Makefile, and
red-teamed by reintroducing the exact two lines. A gotcha that can only be
remembered will be forgotten by the session that was not there.

## M8-S1 leg 2 — evidence that belongs to the host, read by something that is not (2026-08-21, EXEC/Opus 5)

**The lesson worth carrying: when a fact lives in a file, "I could not find it"
and "there is nothing to find" are the same sentence — and the second one is the
one your code will say.** F-048's pod printed *"no sampled search behind this
champion — no scale transfer to make"*, which was true about what it could see and
false about the world; the host, in the same minute, resolved a factor of 6.6667
for the same champion. Nothing crashed, nothing was wrong yet, and the only
visible difference was a `null` in one field of a record nobody was reading.

Two habits come out of it. **Put provenance ON the thing it describes, not beside
it** — the row count a version's knobs were chosen at is a fact about that
version, so it travels as a version tag and resolves identically on a laptop and
in a pod. And **make the third state expressible**: `NO_SEARCH` is a VALUE, not an
absent tag, so "this champion had no sampled search", "nobody ever recorded it"
and "I cannot see the records" are three answers instead of one. Gotcha #94 said a
cross-instrument check that degrades toward *they agree* hides its own breakage;
this is the same disease in a provenance chain, degrading toward *nothing to do*.

**The refusal is the cheap half and it has to come first.** Ten lines that raise
when the records DIRECTORY is invisible turn a silent no-op into a loud exit — but
they would have left the deployed schedule red until the real fix landed, which is
precisely why M7-S4 correctly declined to land them alone. Order the two halves so
the artifact and the tree are never inconsistent: the fix and the refusal shipped
in ONE image, with one redeploy.

**A marker is one afternoon away from being a skip flag, so write the tests that
hold the line before you write the marker.** `needs_records` says *where* a test
can run; it must never come to mean *whether it must pass*. The three properties
that keep those apart are cheap and mechanical: it is deselected in exactly one
place, `addopts` may not deselect it, and nothing carries it that does not need it.

**Measure the set; do not enumerate it.** The tests to mark were found by hiding
`automation/runs/` on the host and reading the failures, then unioned with what
actually failed inside the image — two measurements, because each saw something
the other could not (the host keeps its git index; the image has no `.git`). A
list written from a ledger row would have been twelve; the real answer was
twenty-one.

**The best evidence a guard can produce is catching its author.** The coverage
check's first run flagged a test written ten minutes earlier in the same session,
and its first draft had missed four real tests because a path is spelled two ways
in this suite — `REPO / "automation/runs/x"` and `REPO / "automation" / "runs"` —
which no substring match can see (gotcha #46's family). Then `make image-smoke`
caught two more that no static check could, including one that had been red inside
the image since the day it landed for a completely different reason: the image
ships no `make`. **A check nobody runs decays; the second instance of that was
found by the first run of the command that closes the first instance.**

**Small operational fact with teeth**: `make retrain --plan-only` writes a tracked
record, so running the provenance check before a build makes the next image tag
`-dirty` — and a `-dirty` image must not back a verdict. One rebuild was spent on
it. Anything that writes into a tracked directory is a build input whether or not
it feels like one.

## M8-S2 — the quarantine is the design, and a catalog that records its losers (2026-08-21, EXEC/Opus 5)

**A dependency wall measured before the story starts is a design input; discovered
at `uv add`, it is a crisis.** M8's kickoff read Feast's metadata live and wrote
law 4 from it: `feast 0.66.0` declares `pandas<3,>=1.4.3` against this project's
3.0.5. So the story never attempted an install into the project graph — it built
`.venv-feast`, an isolated interpreter, and made "the two sides never touch" a
checkable property rather than a habit. The probe then measured what the wall
actually holds, and the answer is the useful part: **the two sides differ on
exactly ONE package.** numpy, pyarrow and CPython are identical, so the seam
M8-S3 is about to measure is a pandas seam and nothing else. That is the same
shape as M5-S3's mlserver parity, which came back `0.000e+00` for exactly that
reason — three packages differed, none of them on the numeric path.

**Write the invariant into the script, not into the write-up.** The quarantine's
exit condition is `uv.lock`'s sha256 before and after, and a difference aborts.
The alternative — running the build and then checking `git status` by eye — is
the same claim with nobody obliged to make it. Same instinct one layer along: the
pin file is installed with `--no-deps`, because a resolver consulted at install
time can legally return a different answer than the one that was reviewed.

**A catalog that lists only winners cannot be used to argue against repeating an
experiment.** The strongest feature family in every source this program surveyed
— historical zone/OD aggregates — is in the store and is NOT in the champion,
because M3-S3 measured its only legal form at **−1.63%**. Recording it with that
number, and with the leakage red team's **+1.56% on the month it saw / −3.83% on
the untouched one** beside it, is what stops the next engineer spending a
milestone rediscovering it. And the number is labelled a **15%-sample** number,
because a dropped group is never refitted at full data — quoting it beside g1's
and g2's confirmed full-data figures without saying so would compare two
different things (gotcha #15, in a place it is easy to forget it applies).

**Verdicts must live where they can be checked against each other.** They are
`tags` on the Feast objects and prose in `docs/feast_catalog.md`, and the test
compares the page against the **applied registry** — read back off the store, not
re-read from `definitions.py`. Two files in one commit agreeing with each other
prove nothing; this is the `deploy_serving.sh` idiom (read KServe's mode off the
live ConfigMap) applied to a feature repo. It earned itself immediately: the
first run went red because the registry still held tags I had edited minutes
before, which is precisely the drift the check exists for.

**F-055, and it is gotcha #78 wearing new clothes.** `feast plan` re-stamps a
DataSource's `meta` at import, so it reports all four views as "Updated" on a
repo where nothing changed — every single time. An always-noisy signal is as
unreadable as an always-empty one, and the noisy one is worse because it looks
like diligence. The fix is not to silence it but to assert the statement that can
be false: every reported difference must be confined to those two clock fields.
Red-teamed by renaming one field — the check named it, **and the other three
views still read clock-only**, which is the half that matters. A drill where
everything goes red proves the checker noticed *something*, not *what*.

**Derive the timestamps from the data's own structure and the next story's proof
comes free.** The end-of-window convention (a window is knowable when it ends)
turns `aggregates.fit`'s six month-cutoff tables into six stamps —
2019-02-01 … 2019-07-01 — under which Feast's point-in-time join hands each row
exactly the table `aggregates.transform` hands it. M8-S3 does not have to
discover that correspondence; it has to measure it. And one number nobody
arranged: the full window's OD table holds **46,938** rows, which is the count
M3-S1's floor independently reported as its `(PU, DO)` backoff cells over the
same six months.

## M8-S3 — the bar you can only defend if you write it down first (2026-08-21, EXEC/Opus 5)

**The lesson: an exact bar is not confidence, it is an argument about where the
arithmetic happens.**

It is tempting to write a float tolerance for any cross-language comparison —
`1e-9`, say — because floats are scary and a small number looks humble. That
instinct is exactly backwards here, and working out why is the whole of this
story's craft.

A tolerance is a claim about a mechanism that could make two numbers differ. So
before choosing one, name the mechanism. Between our pandas 3.0.5 and Feast's
pandas 2.3.3 there is a parquet file, and along that path: `make feast-sources`
computes a value on OUR side (through the same functions the champion's own
matrix uses), widens it `float32 -> float64` (exact for every finite value),
pyarrow encodes it as a DOUBLE, Feast decodes it, joins on a key, and writes it
back. **Not one step performs arithmetic.** A store's job is to remember and to
pick a row. So the honest bar is `0.0`, and a `1e-9` bar would not have been
humility — it would have been a place for a real defect to hide, one that only
ever needs to be smaller than the number you were too vague to justify.

Two things follow, and both are the reusable part:

**First, write the bar down before you measure.** M8 law 4 mandates it and this
story committed §2 of `docs/feast_pit_m8.md` in its own commit (`27ea9a1`) before
the comparison ran, so the ordering is checkable from git. The reason is not
ceremony. Had the run come back at `3e-16` and the bar not yet existed, `1e-9`
would have felt like a perfectly reasonable thing to write — and nobody, ever,
would have asked which side rounded. Writing the argument first converts a
surprise from something to accommodate into something to investigate.

**Second, name in advance what a nonzero result would MEAN.** §2 lists them: a
producer that computes instead of copying, a float32 column decoded through a
rounding dtype, a store-side aggregation, a join serving the wrong window. That
list is what turns "the measurement failed" into a diagnosis, and it is only
writeable before you have a number to explain away.

**The other half: absence is a value, and comparing it is where the design
lives.** `NaN != NaN`, so the easy comparison drops nulls — and prints exactly
the same `0.000e+00`. This one counts both-missing as agreement and **one-missing
as a MISMATCH**, and the number that mattered in the end was not the max delta
but `one missing = 0` on all fourteen columns: the store and the feature path
agree about *which rows have no value at all*. Zones 264/265 have no centroid by
design, so the store holds no row for them while our table says borough
`"Unknown"` — the same fact in two vocabularies. The temptation is to publish a
zeroed row so a column-wise comparison succeeds. That is putting a plausible
place at the equator into a feature store to satisfy a test. The right move is a
two-sided assertion: the store must say **nothing**, and our path must report
`has_geometry = 0`.

**And the one about proofs.** The naive-versus-honest difference is the
photogenic half — 61 of 76 rows differ, the leak in minutes. But on its own it
proves only that two joins disagree; it is equally consistent with the honest
join being wrong in some *other* way. What pins it is the boring second half:
the honest join's values equal our own `aggregates.transform` output at
`0.000e+00`. **A demonstration of a difference is not a proof until you have also
shown which side is right.** Every drill in this repo that survived contact has
that shape, and the ones that had to be repaired usually did not.

Finally, the row set. Sixteen of the 88 rows are `parity.HAZARDS`, *imported*
rather than copied, so the wire seam and the store seam are measured against one
set and cannot drift apart. And the drawn rows refuse to come back short —
because the first draw asked DuckDB for `USING SAMPLE reservoir(15 ROWS)
REPEATABLE` after a `WHERE` and got **zero airport rows out of 3,237,471**.
DuckDB samples the scan; the filter is applied to what survives it. A short draw
in a committed artifact is indistinguishable from a stratum nobody thought to
cover, which is #78 wearing a sampler's clothes.

---

## M8-S4 leg 1 — the online store, and what an online store structurally cannot do

The sentence worth keeping from this story is not the parity number. It is this:
**an online feature store cannot serve a point-in-time feature.** `feast
materialize` keeps the latest row per entity key and no history, so a
time-varying view serves whatever the newest window says to every request that
ever arrives. M8-S3 spent a whole story proving that a *training* row must be
served only what it was entitled to know; this story's store is structurally
incapable of that distinction. Both facts are true at once and neither is a
defect — a training set and a request are different questions — but the seam
between them is exactly where a leaky feature would enter production wearing a
correct offline proof as its passport.

It happens to cost nothing here, and that is worth understanding rather than
being relieved by: **every stored feature the champion actually eats is static.**
Nine geometry lookups and three calendar flags. The two time-varying views are
`catalog-only` — they lost the M3 ablation. So the champion's exposure to this
limit is zero *today*, by an accident of which features won, and the day a
window aggregate wins an ablation is the day this becomes a real design problem.

**The immediate consequence is a comparison design.** The offline half of the
parity table has to be retrieved at one instant *after the last window closed*,
because that is the only offline answer the online store is trying to be. Ask for
each row's own point-in-time answer and a perfectly working store reports as
broken — gotcha #50, and the version of it that would have been easiest to
believe, because "compare like with like" sounds like the careful choice.

**Then the thing I did not see coming.** Holding every timestamp constant turned
M8-S3's F-056 from a curiosity into the normal case. `get_historical_features`
answered **34 rows for 100 declared pairs** on one view; `get_online_features`
answered 100 of 100 on every one. Nothing was wrong — a lookup returns one row
per request, a join returns one row per distinct key — but I had inherited an
aligner written when the collapse affected one row in eighty-eight, and the
property that made it rare was the exact property this story was required to
remove. Aligning by position would have compared the store against a shuffled
copy of itself. The general lesson: **before comparing two APIs, ask what each
one's row count MEANS**, and check whether the assumption that made a previous
edge case rare still holds.

**A design refused by its own data.** I declared a hazard row for "a key whose
newest source row predates the full window" — the row that would go null if
materialization filtered on the window's end. The builder found no such key, and
the reason is structural: the point-in-time windows are cumulative, so the full
window's key set is a superset of every earlier one's. The temptation is to
quietly substitute something nearby that runs. The replacement has to do the same
*job*: the pair whose median moves most across its windows (80 minutes), which is
where a wrong-stamp materialization shows up largest. **A hazard row you cannot
construct is a fact about the system, and it belongs in the write-up next to the
row that replaced it.**

**The bar, and why it was not inherited.** M8-S3 argued EXACT from "nothing on
the store's side performs arithmetic". Copying that sentence into a story that
adds a serialization format and a network hop would have been a hedge wearing an
argument's clothes. So it was re-made for the new path — protobuf `double` is
fixed-width, bool and string have no numeric path, the hop moves bytes, the
entity-key encoding is pinned, `materialize` selects rather than aggregates — and
committed before the comparison ran. That ordering is checkable from git, which
is the only form of "we decided this in advance" that survives a sceptic.

**And the red team, which is the reason the table is worth committing at all.**
Both halves come from one Feast install, so the first sceptical reading is that
two reads of one store will always agree. The drill copies one OD pair's *real
serialized bytes* onto another pair's key: every byte written by Feast, the
protobuf parses, the dtype is right, nothing logs anything. That is what a
wrong-row materialization looks like from outside, and it is the one failure the
offline store cannot detect for itself. Eighty-seven minutes of skew, one column
named, twenty-six other lines still green, a byte-identical restore. **Planting
garbage would have proved the parser works. Planting something valid is what
proves the table does.**

## M8-S4 leg 2 — a wall with a door in it, and three things that look alike in a schema (2026-08-23, EXEC/Opus 5)

**The cheap probe keeps earning its place, and this time it changed the shape of
the story rather than saving time.** The kickoff ordered three ways to get stored
features onto the request path, and shape (i) — Feast's own server in its own
pod — looked like the expensive one: a Dockerfile, a base pin, a registry
delivery mechanism, a `kind load` to three nodes. So before any of that,
`make feast-serve-probe` started `feast serve` on the host inside the quarantine
that already existed, against the real in-cluster Redis, and asked it one
question. Thirty seconds. It answered JFK's centroid and answered `null` for zone
264. Everything after that was packaging a thing already known to work, and the
first real defect the build hit was a missing execute bit — which is the usual
yield of a cheap probe: **the defects it finds are almost never about the
expensive thing it is standing in front of.**

**The shape that keeps a wall a wall.** The temptation with a dependency
quarantine is to poke one small hole in it — "we only need to read a few keys
from Redis, we can do that ourselves". That hole is where the vendor's internal
entity-key encoding, field naming and value serialization move into our
codebase, and the failure mode of getting any of them subtly wrong is a lookup
that returns *somebody else's row*: a confident wrong number with nothing red
anywhere. A 203 MB pod is cheap against owning a private copy of somebody's
encoding. The two worlds now share exactly one thing — a JSON document over a
ClusterIP Service — and `uv.lock` never moved.

**The finding, and it is one sentence with two halves.** `zone_static` stores
four columns and only two of them can be a *source* for the champion's matrix.
`borough` is an **encoding**: the code the model eats is assigned by
first-appearance order across the whole lookup table, so it is a property of the
table and not of the zone, and a transformer that fetched the two zones a request
names and numbered what came back would produce a silent total category re-map in
which every individual value is correct. `is_airport` is a **constant** and a
**total function**: three integers in code, answering for every id including
TLC's two non-places — which the store has no row for at all, so sourcing it from
the store turns "not an airport" into "no answer" for exactly the rows that
already carry no geometry. A centroid is neither: it is a measurement of an
entity. **All three look identical in a schema, and only the third belongs in a
feature store.**

**The half I got wrong, and what the repair was not.** The parity reader's first
run went RED — `is_airport`, ours `False` versus store `missing`, two zones of
twenty-three, with every numeric column sitting at `0.000e+00`. The tempting
readings are both wrong: it is not a rounding defect, and it is not a reason to
widen a bar that had been argued and committed an hour earlier. It was a
comparison holding a *total* function against a *partial* one and calling the
difference a defect. The repair was structural and it was already in the
repository — M8-S3 and leg 1 both partition the entities, assert the partition
two-sidedly, and compare columns only where both sides claim an answer. I had
written a new reader instead of inheriting a shape. **When a check goes red, the
first question is still gotcha #50's — did the thing it names actually change for
the worse? — and the second one, which I needed here, is: am I comparing like
with like, or have I asked two differently-shaped functions the same question?**

**And the boot ritual paid for itself before the story started.** The staleness
check found 104 pods in the `flyte` namespace, 96 of them Pending, all created in
one 17-second burst two minutes after the control plane restarted at host boot: a
`FixedRate(20)` proof trigger back-filling two days of missed windows at once.
Nothing was corrupt and no number was wrong. They were unschedulable in a
self-limiting way only because the retrain mounts an RWO volume and they queued
behind it on one node — luck, not design. **A schedule left running forever on a
machine that gets turned off has a cost that scales with how long it was off, and
the only reason anyone saw this one is that the ritual says look before you
build.**

## M8-S4 leg 3 — the boundary moves, and the number does not (2026-08-23, EXEC/Opus 5)

**What this story actually is.** Since M5-S2, every client of this program has
built the champion's 24-column matrix itself and put the FEATURES on the wire.
That works, and it has an honest weakness: "training and serving agree about what
a feature is" was a property of each caller separately. This leg puts a pod in
front of the model that takes what a rider knows — a time, two zone ids, a party
size — and derives the 24 features inside the cluster, with the centroids and the
calendar flags read out of the online feature store instead of the committed CSVs.
The headline is that **`max |champion − transformer| = 0.000e+00` minutes across
all 16 declared hazards**: the boundary moved and the number did not.

**The lesson I would carry to another program: write the bar's ARGUMENT, then go
and make one of its premises a measurement.** M8's law 4 makes you commit the
tolerance before the comparison, and the temptation is to write a hedge that
cannot be wrong. The bar here is EXACT — *tighter* than M5-S3's 1e-6 — and it was
defensible only because `make transformer-probe` had already measured the
store-backed matrix as bit-identical to the committed one, on the host, before the
bar was written. That turns "float64 should survive JSON" from a hope into a
precondition. A bar argued from a measured premise is a different object from a
bar argued from a plausible one, even when they print the same number.

**The probe earned its keep twice, and neither time for the reason it was built.**
It cost about a minute against a ~7-minute image build and a KServe deploy this
repo prices at 2–3 defects each. It found nothing wrong with Feast — it found that
everything except KServe's own wiring already worked, which is what made the
deploy's one failure attributable in seconds rather than being one candidate among
five. Leg 2's 30-second probe did exactly the same thing. **A cheap probe's yield
is usually not the thing it was pointed at; it is the SIZE of the search space
when the expensive thing then fails.**

**The defect worth remembering is in a CHECK, and it is one I write constantly.**
The accept asserts that the champion's model name 404s on the transformer's host
— the negative half, without which a number from that service could have come
from either boundary. Its first run PASSED that while failing everything else,
because nginx had not loaded the generated Ingress and the host was 404ing every
request. A 404 because nothing is routed and a 404 because the name is wrong are
the same bytes. Gotcha #59 says assert on a positive artifact; this is its
negative form — **where the artifact IS an absence, prove first that presence was
possible** — and the repair was to make the negative check conditional on the
positive one, not to loosen anything.

**F-059 stopped being a note and became a type.** Leg 2 found that a feature store
is a good home for a per-entity MEASUREMENT and a bad home for anything a program
COMPUTES, and that the two are indistinguishable in a schema. Landing it meant
giving `Lookups` exactly two fields, so there is nowhere to put a fetched borough
code, and pinning it with a test that asks the **AST** rather than the behaviour —
because a store whose values happened to agree would make a behavioural test pass
for a design that is wrong, and the failure it hides (a total category re-map with
every value individually correct) is invisible in every individual value. **When a
design rule's violation would be silent, the guard has to be about the SHAPE of
the code, not about its output.**

**And the number I would have got wrong by analogy.** M5-S4 priced the feature
build at ~30 ms cold and warned it would land inside the p95. The measured p50 move
is +18 ms — and it buys the feature build plus two round trips to another pod plus a
second HTTP hop. The word doing the work is *cold*. Meanwhile the p95 DELTA swung
+23.0 → +5.0 ms between two identical runs eight minutes apart while p50 held to a
millisecond, so the reportable cost is the p50 and the p95 is "inside a band wider
than the effect". Two runs is the cheapest possible defence against quoting a tail
on a laptop, and it is the second time this program has needed it (M6-S2 refused
the same flattering reading about p99).


## M8-S5 — a survey that has to be allowed to lose, and a gate that found its own hole

**Writing a comparison page is a test of whether you will publish the row that
goes against you.** The kickoff asked for adopt/differ/surpass, "honest in both
directions", and the hard part was not finding SURPASS rows — none of the three
surveyed repositories asserts that its point-in-time join is point-in-time
correct, none compares its online store against its offline values, and that is
genuinely the milestone's edge. The hard part was writing down that **F's single
Python environment is the better design for anyone who has not pinned pandas 3,
and we would have taken it**; that its `FeatureService` is a registered contract
where ours is a Python constant on one side of a wall; and that its seven-step
origin-labelled request trace would have shortened three of last session's
debugging sessions. I made the gate assert `>= 1 ADOPT` for that reason — a
survey with no ADOPT is a press release, and the check is cheap insurance
against a future author quietly writing one.

**The population size was the first finding, and it belongs above the table.**
A GitHub API search for Feast on this exact problem returns three substantive
repositories at 0★ each. "The community does X" is a sentence with a sample size,
and mine is three — so every SURPASS row says *none of these three* rather than
*nobody*. The same discipline applies to absence claims: every "they do not do
this" here rests on a recursive tree listing, because a skim that missed a
`tests/` directory would turn a fair comparison into a false one.

**The gate found a real defect in the first thing it asked the live system, and
the interesting part was the temptation.** `up{job="kserve-predictors"}` came
back with three targets and one of them permanently zero: M8-S4's transformer pod
belongs to an InferenceService, so the scrape job keeps it, and the job then
forces mlserver's metrics port on it, which the transformer does not have. Two
assumptions had been the same assumption for three milestones. The tempting
repair was to narrow the gate's question to the champion's own exporter — one
line, green immediately, and completely wrong: it would have been a guard edited
to fit a defect, on the one signal whose entire value (F-043) is that `up == 0`
means a predictor has stopped reporting. A standing false alarm is how a real one
becomes invisible. I fixed the selector instead, with a label KServe already
sets, and kept the gate's question BROAD so the next non-predictor in that
namespace fails it too.

**Where to plant a red team: read your own design document for the sentence that
admits a broken version would look identical.** `docs/feast_online_m8.md` §2 says
that a comparison which silently dropped nulls "would print a perfect zero while
being blind to exactly those rows". That sentence is the plant. Rewriting one
column's `both_missing` from 13 to 0 leaves the delta, the mismatch count and the
verdict untouched — the record still reads as a clean pass, and it reads as a
*better* pass than the truth. Choosing that field forced me to build the three
witnesses it needed (the run's own two-sided no-geometry assertion, the
independently-built anchor block, and the committed table a human diffs), and
those three checks are the best thing in the gate. **The red team did not test the
gate so much as tell me which checks it was missing.**

**Eight failures on the gate's first run, four of them mine, and every one the
same disease.** A registry demanded ABSENT FROM DISK when the property is *not
tracked by git*. A bar regex that encoded one sentence's word order instead of the
bar. A typed script path. A DVC summary line counted as one target out of four
over a perfectly clean tree. A ledger searched whole, so the milestone's own prose
— "M8-S5's gate inherits it live" — was read as a ledger row. Then the *test file*
went red three times for the same reason, and all three were the gate quoting
itself. **When a check goes red, the first question is still whether the thing it
names actually got worse**, and here the answer was no five times out of eight.
The permanent lesson from the fourth occurrence of gotcha #99 in this repo: in a
codebase where prose is load-bearing, a needle must sit where a shell would START
a command or where an AST would find a call — never where a word appears.

---

## M9-S1 — the demo page: the route decision was the story, and the browser is the only client that cannot lie

**The wrinkle the kickoff named was real, and the way out was to claim less, not
more.** Every route in this cluster is host-based because KServe and the helm
charts generate them that way, and `fetch()` cannot set a `Host` header. The
obvious fix — an Ingress on `host: localhost`, which is what a browser sends —
works, and it would have broken `deploy_serving.sh`'s accept check, because
`location /healthz` exists **only in nginx's default server block**. Two curls
before anything was applied said so:
`Host: totally-unrouted.invalid` → 200, `Host: nyc-taxi-eta-serving.local` → 404.
So the rule carries **no `host:` at all**, which puts both paths into that same
default block: the page and the model share one origin, **CORS never happens**,
and every existing invariant stays standing. The general shape is worth keeping:
*when a new route would force an old assertion to be edited, look for the routing
option that claims less.* Editing an M5-era assertion to fit an M9 convenience is
how a guard becomes a formality (gotcha #50, refused rather than paid).

**A browser is the one client in this program that cannot be given a helpful
argument, and that is a feature.** Every other client here sets an explicit
`Host` header and builds its own 24-column matrix. The demo can do neither, which
is precisely why it is a good test of M8-S4's boundary: it consumes the raw
endpoint the way it was designed to be consumed, with four fields, over one
origin. `demo_accept.py` therefore reads the endpoint, the request schema and the
payload **out of `demo/index.html`** and sends them with no Host override — a
check that retyped any of the three would be measuring a second client that
merely resembles the page, and the failure it could not see (a page whose schema
drifted from the server's) is the interesting one.

**The failure that taught the most cost one accept run and made the check
stronger.** The first route claimed the CHAMPION's model name and every quote
404'd — the V2 model name is in the URL path (ADR-011 condition 2, third
occurrence). The diagnosis was free only because the transformer's 404 body names
the path it *does* answer to; an endpoint that answered to both names would have
made the whole question unanswerable. The repair was not a correction but an
inversion: the champion's name is now **deliberately unrouted** on the demo's
origin, and the accept asserts that 404 — so the demo cannot quietly end up
talking to the 24-column wire, and a number the page shows is attributable to the
raw boundary by construction. **A wrong assumption you can turn into a standing
negative check is worth more than one you simply fix.**

**Three derivations, and the one that bit was the one documenting itself.** The
page's zone list comes from the TLC lookup, its request schema from the server's
own `RAW_INPUTS`, its default trip from a published parity row. The generator's
first run then substituted its own explanatory comment — the paragraph *naming*
the placeholders — and produced a page with three copies of every picker. It
rendered fine, and no "the zone list matches the CSV" assertion would have caught
it, because all three copies matched. The guard is not a cleverer parser; it is
an **occurrence count** (gotcha #110). Prose sitting where a parser reads it as
code, for the fourth time in this repo, and the first time it was the *template's
own documentation* that did it.

**What could not be closed, and saying so is the point.** §9/M9's last box needs
a non-technical person to complete a query unassisted, observed. An unattended
session cannot do that. It is recorded as OPEN in the accept record itself
(`po_observed_run.status`), raised at AWAITING_PO 2026-08-23-3 with the URL and
the one command, and `make verify-m9` is chartered to assert the entry exists and
is honest. **A demo that marked its own human-observation box green would be the
only dishonest artifact in the program.**

## M9-S2 — the online-store watchdog: a bar you don't need, a canary that must decline, and the guard that saved us was written for something else

**The headroom leg didn't calibrate the threshold — it deleted it.** I went in
expecting to argue a key-count bar: the store holds 57,688 keys, so page below
some fraction of that. The measurement made the whole idea look silly. Feast
writes one Redis key per distinct entity key per view, so the count has a source
of truth *that is not itself* — and three witnesses agreed at 57,688 (the
derivation from `data/feast/*.parquet`, M8-S4's materialization record, the live
`DBSIZE`). Once the right-hand side of the comparison is measurable on the same
run as the left, the rule is `keys < keys_expected` and there is **no number on
either side**. Two other numbers then told me a bar would have been actively bad:
the transformer's entire dependency is **4,646 keys, 8.054%** of the store, so a
store that lost every feature the rider's path needs still reads 92% of normal;
and zone 132's centroid is **one key of 57,688**, so the failure that breaks
every JFK quote moves `DBSIZE` by 0.0017%. **A quantity can be perfectly accurate
and structurally unable to see the event you care about.** That is gotcha #59
arriving in an aggregate rather than in a status code, and the way I found it was
computing the composition before writing the rule instead of after.

**"Stale" needed redefining before it could be alerted on at all.** SLO-D3 asks
whether the drift *job* ran recently and argues 40 days from a monthly cadence.
That question has no answer for this store: its data is settled — 2019 windows, a
2019 shapefile, a holiday table to 2030 — so a store filled in August 2026 is
exactly as correct in 2027, and any clock-age bar on its *contents* would be a
number chosen to avoid paging. **A store is stale when it disagrees with the
sources it was filled from.** Same words, different question, and the second one
is checkable with no threshold. When a monitoring vocabulary transplants badly,
suspect the question rather than the number.

**The negative check I was proudest of turned out to be the one that cannot
fire.** The canary asserts four claims and one is negative: zone **264 must
decline**, because a store answering for TLC's non-places would be inventing a
location, and a presence-only check passes against a server that answers every
question with the same row. Correct, and load-bearing at M8-S4 leg 2. But
`nonplace_declines` read **1 through the entire outage** — `null` is the right
answer for 264 *and* what a totally empty store returns, so the negative claim
cannot distinguish "correctly declines" from "has nothing to decline with". It is
in the record and in §9's table rather than left for somebody to rediscover.
**A negative assertion is strongest where presence is possible** — which is
F-060's lesson (gotcha #105) meeting its own boundary: there, an absence assertion
passed for free because the system was absent; here, it passes for free because
the absence it asserts is also the symptom.

**The prediction was wrong in the most useful direction.** The kickoff, ADR-012
and two M8 write-ups all expected an emptied store to produce a **confident wrong
number** — nine NaN geometry features and a plausible quote with nothing red
anywhere. Measured, with the store really empty, the transformer answers **HTTP
422**. The reason is worth the whole story: the **geometry** half structurally
*cannot* refuse, because an all-null centroid table is exactly what zones 264/265
legitimately produce — but every request also carries a **date**, and
`calendar_from_store` raises on an unanswered one. So the thing standing between
an empty store and a wrong quote is **F-019's horizon guarantee, carried onto the
store's wire two stories earlier for an entirely different reason**. Then the
sting: 422 is the *caller's* status class, and SLO-R1 puts 4xx outside the
availability error budget on the argument that a 4xx is a guard working — so a
totally dead dependency currently spends **zero** error budget and renders as
riders sending bad requests (**F-062**, open, routed with three costed options).
The 503 path exists and is correct; it is simply not the path an *empty* store
takes, because empty and unreachable fail in different halves of the client.
**Two failure modes of one dependency can exit through two different status
classes, and only one of them is billed to the right party.**

**And the drill's undo rewrote another milestone's evidence.** The one-command
repair the runbook names is `scripts/feast_materialize.sh`, which unconditionally
writes `automation/runs/m8-online/materialize.json` — a *tracked* record belonging
to M8-S4 and cited by this story's own headroom leg. The drill's first run
re-dated it to its own minute. The refill was right; writing M8's evidence over it
was not. Third occurrence of one shape (gotcha #48, F-053, now F-063): **when a
command is reused as somebody else's undo, audit what it does to state that
already exists.** It was visible only because `automation/runs/**/*.json` is
tracked — F-029's option A, landed at M5-S1 for exactly this reason and paying out
three milestones later.


## M9-S3 — two closures, and the choice between fixing the tool and rewriting the artifact it maintains

**F-057's fix had a fork inside it that the row did not see, and taking the other
branch is why the finding closes with a zero-line diff.** The defect: the pin
file's own documented regenerator emitted distribution names as PUBLISHED
(`PyYAML`, `typing_extensions`) while the committed file carries the normalized
spelling, so `--rewrite-pins` could not reproduce the file it maintains and
M8-S4's two real additions arrived as +14/−12. The obvious repair — normalize,
regenerate, commit the twelve changed lines — was what the kickoff anticipated
("regenerate in a commit that does NOTHING else"). But when I actually diffed the
two candidate outputs against the committed file, the naive normalization left
**three** lines still moving: `mypy-extensions` / `mypy`, `pydantic-core` /
`pydantic`, `uvicorn-worker` / `uvicorn`. The committed file is sorted **as
lines** (`-` sorts before `=`, so the hyphenated sibling comes first); today's
`uv pip freeze` sorts by name. Matching the file made the regeneration a **no-op**
— sha256 `a700cd6b…` before and after, `git diff` empty.

**That is a stronger closure than the one I was asked for, and the reason is
about evidence rather than aesthetics.** If I regenerate and commit, the
round-trip test's claim is *"the regenerator reproduces the file I just wrote
with it"* — true by construction, and it proves nothing about the twelve
spellings being the RIGHT ones. By making the tool agree with the artifact, the
claim becomes *"the regenerator reproduces a file that has been under review
since M8-S2, untouched"* — the fix is tested against something that predates it.
**When a tool and the artifact it maintains disagree, ask which one was
reviewed** — and only rewrite the reviewed thing if the tool's version is
actually better. Here it was not: sorting the lines is the ordering a reviewer
can check without running anything (`sort -c`), and this script is the file's only
producer, so the order was ours to define. Honest cost, written into the row: a
hand-run `uv pip freeze` now differs from the file on three lines, which is the
same shape as the defect I was closing, one notch smaller.

**I also refused the fix the finding literally recommended.** The row says
`name.lower().replace('_','-')`; I used PEP 503 (`[-_.]+` → `-`, lowercased).
They agree on all 66 names this quarantine holds, so it changes nothing today —
which is exactly why it was worth doing now rather than the day somebody adds
`zope.interface` and gets a spelling no installer canonicalises to. The two cases
where they differ are in the test, so the choice is falsifiable rather than
asserted. And a normalization can COLLIDE (two published names, one canonical),
which would silently drop a pin from a file whose entire claim is completeness —
so it raises instead. **A one-line transform that maps many to one deserves the
collision branch even when you are confident it cannot fire.**

**F-054 was mechanical, and the interesting part was where the check lives, not
what it does.** Twelve tests guarded their record reads with `skipif(not
RECORD.exists())`, which on the host reports "the drill was never run" as a pass.
Converting them is a search-and-replace. The part worth thinking about is that
`test_record_marker.py` used to *accept* that form and argue against it in prose
— so the closure was not just changing twelve decorators, it was moving
`_skip_guarded` from the coverage check's **subtraction** (accepted) into a new
test's **refusal**, derived by AST across every test file. Enumerating the two
known files would have gone green the day a third grew one. **A finding that
lives as a documented exception in a guard is closed by changing the guard's
verdict, not by fixing the instances** — the instances are what the guard then
catches.

**Two small things worth keeping.** The assertion carries its own message
(`… is a TRACKED record (F-029 option A) — its absence means it was deleted or
lost, not that this clone lacks local artifacts`) because the default failure is
a bare `FileNotFoundError` five frames deep, and the whole point of the change is
that a future reader is told what the absence MEANS. And both red-team proofs
were the same shape as every other one in this program: plant the exact defect
being closed (one pin back as `PyYAML`; one record moved aside), watch multiple
independent tests go red naming it, restore, watch green. Neither took two
minutes, and without them the two closures would rest on "I changed the code and
the suite is green", which is what a suite says when a check has quietly stopped
checking.


## M9-S4 — the program's last gate: three questions, not fourteen; and a check that had been reporting a comparison it never made

**The gate asks THREE live questions and the interesting decision was subtraction.**
`verify-m8` asks five, `verify-m6` and `verify-m7` three each. The tempting shape
for the *last* gate in a nine-milestone program is the union — ask the champion's
wire, the feature server, the exporter's health, the store, the rules, the demo,
everything. That instinct is wrong for a reason worth keeping: **a gate that
re-asks its predecessors' questions is not stricter, it is a gate whose live
footprint grows every milestone.** `verify-m5` already asks the champion for a
prediction and refuses to pass if the served version disagrees with the alias;
`verify-m8` already asks the feature server two-sidedly and the exporter whether
it is up. Those gates are *runnable*, and the boundary runs them. So M9's three
are exactly the three nobody else can ask: one quote through the DEMO's own
request path (endpoint, schema and payload read out of the committed page, posted
with no Host override — the one thing a browser cannot do and every other client
here does), one rules read, one DBSIZE. The count is in the header and pinned by a
test, and the test also asserts the *absences* — no `client_mod.infer(`, no
`get-online-features`, no `/api/v1/query`. A bound that only says "no more than
three" can be satisfied by three of somebody else's.

**A gate that passes BECAUSE something is unfinished.** §9/M9's last accept line
is "one non-technical person completes a query unassisted, observed". No
unattended session can watch that, and the whole program has one rule that makes
this easy to get wrong: gates render green. So this gate is chartered to check
that the box is recorded *honestly* — the record says OPEN, AWAITING_PO carries
the invitation, and the two agree on the URL — and to print it as an open item in
§2 **and in its own GREEN banner**, where a reader who skims only the verdict
still sees it. Three separate assertions in the test file hold that, including
the banner one, because the failure mode here is not a bug but a temptation: a
gate reporting the milestone complete would be describing an observation nobody
made.

**Two rules that carry no number, and what you check instead.** A-12a compares a
canary claim to `0` and A-12b compares a live key count to an expected key count
the reader pushes on the same run. There is no bar to check against a document —
so the checkable properties are the ABSENCE of a numeric literal on either side
of the comparison, the ONE number in all three rules (A-12's 1800 s freshness
clause) being argued in §9 *specifically*, and the strongest of the three:
**every series the rules SELECT must be a series the reader PUSHES.** That last
one exists because of gotcha #92's shape — a rule selecting a series nobody
produces does not error. It sits `health=ok` and `inactive` forever, which is
precisely what a healthy store looks like.

**The three RED first runs were all the gate's own defects, and the third is the
one to remember.** The F-054 leg asked "does any test skip on a `.exists()`?" and
flagged a test that skips on `.venv-feast/bin/python` — a gitignored build
artifact, absent in CI, where skipping is *correct* and is the idiom this suite
already uses for `ss`, `git`, `make` and `docker`. F-054 was never about that: it
is about **records**, paths under `automation/runs`, which are TRACKED, so their
absence means deleted-or-lost rather than this-clone-lacks-artifacts. **Gotcha
#50 again, and the repair is narrowing to the right property rather than widening
the bar** — the leg now resolves each file's record constants from their own
assignments and counts only skips gated on those. A guard that fires when the
program behaves correctly teaches the next session to edit assertions, which is
how a guard becomes a formality.

**F-064: a clause that had shipped green nine times, reporting a comparison it
never made.** `verify_m8.sh` read `materialize["store"].get("keys")` where the
record spells the field `dbsize`. `expected` was always `None`, the
`expected is None` branch fired, and the leg tested `dbsize > 0` alone while
telling its reader "the count the materialization recorded, survived on its PVC".
It would have passed a store holding one key — in the gate whose whole job on
that line is to notice an empty online store. It was invisible **because the
original was written defensively**: `.get()` plus an `or expected is None` reads
as care, and degrades toward passing. The M9 gate found it by copying the clause
and spelling it strictly. Two things generalise. First, gotcha #51's question is
usually asked of a component that FAILED; ask it of a check that PASSES — *could
this tell if it were false?* Second, **a defensive default in a verifier is a
different thing from a defensive default in a producer**: in a producer it keeps
the system running, in a verifier it keeps the verdict green.

**The red team plants a population, not a measurement.** One number: the store's
expected key count, short by exactly one view's worth — and the view is chosen
from the record as the smallest, which is `zone_static`, the 263 rows holding
every centroid. Nothing about the alerting stack changes (A-12b has no literal to
loosen; every rule stays inactive and `health=ok`), 42 sub-checks have no reason
to complain, and the described store could lose all its geometry and still
satisfy the alert that exists to notice. Three artifacts contradicted it — the
record's own arithmetic, the live DBSIZE beside the M8-S4 materialization record,
and the write-up — and **the third had to be built for the drill**, which is the
usual yield of writing the red team second: it tells you which witness the gate
was missing.
