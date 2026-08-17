# LEARNING_GUIDE — field notes, one per story (inherited law from the predecessor)

Law: every story closes with its note BEFORE the next story starts. Format per
note: what was built · why this way · the concept underneath · what to look at ·
what to try yourself. Newest milestone first. The reader is the principal six
months from now.

---

## M2

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
