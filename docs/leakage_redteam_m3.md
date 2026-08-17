# The leakage red-team — what the illegal version of the aggregates buys (M3-S3)

Date: 2026-08-17 · Story: M3-S3 · Role: MLE · Reproduce: `make leakage-redteam`
· MLflow experiment `m3-artisan`, runs `491547fdf44046e3bb44d98182aeea81`
(arm A) and `d709cf026ef44eb89e47f5d3f1d5fc08` (arm B).

The M3 kickoff mandates this drill and the artisan playbook §5 trap 2 names it:
*fit one aggregate across all months on purpose, watch validation inflate while
an untouched month does not, document the gap with numbers.*

**The claim under test is not "leakage is bad."** Nobody disputes that. It is
the sharper one M3-S2's harvest turned up while reading a top-6% Kaggle solution
as code: **the same line of code is correct in a competition and disqualifying in
production, and the difference is the split, not the code.** That solution
concatenates train and test before taking group means of the target. Nothing
about it is sloppy — its test period interleaves its train period, so a group
mean over both is a legitimate estimate of a stable quantity. Move the same line
into a system that predicts the future and it becomes a model whose offline
numbers no live traffic can reproduce.

So the drill measures the size of that gap on our data.

---

## 1. Design — two arms, one difference, and two held-out months

Both arms fit the SAME feature set (`v1_g5` = v1 + the three point-in-time
aggregates), the same hyperparameters, the same seed, the same rows. Exactly one
thing changes:

| arm | the aggregate tables are fitted on |
|---|---|
| **A — honest** | the drill's train months only, **point-in-time by month**: a row in month *k* is served a table built from months 1..*k−1* and nothing else |
| **B — leaky** | the drill's train months **and the validation month**, with no cutoff at all |

**Two held-out months, because one cannot tell the difference.** Validation alone
would show arm B looking better and nothing else; the whole point is that the
improvement does not travel.

| split | months | in arm B's aggregate fit? | in either model fit? |
|---|---|---|---|
| val | 2019-07 | **yes** — this is what inflates | no (early stopping reads it) |
| holdout | 2019-06 | **no** | **no** |

**The configured TEST month (2019-08) was not read.** The playbook's "untouched
month" role is played by 2019-06, pulled out of the training window for this
drill only, so the demonstration costs the test month nothing and M3-S5 keeps its
one shot (DR-05 §3). Drill train is therefore 2019-01…2019-05.

15% stratified sample, seed `20260817`: 5,570,508 drill-train rows, 928,462 val
rows, 1,027,605 holdout rows.

---

## 2. What came back

```
| arm | aggregates fitted on | val MAE | val KPI-10 | holdout MAE | holdout KPI-10 |
|---|---|---:|---:|---:|---:|
| A honest | drill train only, point-in-time by month | 3.5403 | 78.803% | 3.5670 | 78.889% |
| B leaky | drill train **+ val**, no cutoff        | 3.4852 | 79.664% | 3.7037 | 78.503% |
```

```
[redteam] the leak BOUGHT +0.0551 min on the month it saw (val) and -0.1367 min
          on the month it did not (holdout).
[redteam] inflation = +0.1917 min of val improvement that no untouched month
          reproduces. That difference is the whole finding: arm B would have been
          reported as the better model.
```

In relative terms: the leak improves validation MAE by **1.56%** and improves
validation KPI-10 by **0.861 points** — comfortably past the Design Review's
0.50% keep-threshold on both conditions, i.e. **it would have been admitted into
feature set v2 by the same rule that admitted g1 and g2.** On the untouched month
it is **3.83% worse** on MAE and **0.386 points worse** on KPI-10.

---

## 3. The three things worth taking from it

**1. The inflation is not the only damage — the leak made the model genuinely
worse.** The expected shape of this drill is "val improves, the untouched month
stays flat". What actually happened is that the untouched month **degraded**, by
more than twice what validation gained. A contaminated feature is not merely an
over-optimistic measurement of an unchanged model; the booster spends capacity
learning to trust a column whose reliability is an artefact of the fit, and it
gets that trust wrong everywhere the artefact is absent. Arm B also ran all
**500** rounds without early stopping while arm A stopped early — the leak keeps
handing validation improvements that are not improvements, so the one mechanism
that would normally halt the process is the mechanism it defeats first.

**2. Validation is the report, and validation was fooled.** Every keep decision
in `docs/ablation_m3.md` is a val-MAE decision, and this drill shows the exact
input that makes val-MAE lie. That is why the point-in-time constraint lives in
the type — `aggregates.fit(..., point_in_time=True)` is the default, the tables
carry the flag, and `describe()` prints `LEAKY BY REQUEST` in capitals — rather
than in a code comment somebody is trusted to read.

**3. It is a good argument for a drill, and a bad argument for deleting one.**
The switch that produces arm B lives in `taxi_mlops.features.aggregates` and is
reachable only from `scripts/leakage_redteam.py`. The kickoff asked for a
disposable branch that is deleted afterwards; this program has already made the
opposite call once, deliberately, for the same reason — M2-S3 kept
`model.HOBBLES` and its hobbled MLflow run so the promotion gate could be watched
saying no by anyone, at any time, rather than on the word of whoever was watching
that day. **A refusal nobody can re-run is a refusal taken on trust.** The
deviation from the kickoff's letter is recorded in this story's handoff rather
than glossed; what the kickoff was protecting — leaky code must not be reachable
from any training path — is enforced by the default, by the flag on every table,
and by a test that fails if `point_in_time=False` ever stops actually leaking
(`test_the_leaky_switch_really_leaks_or_the_red_team_proves_nothing`).

---

## 4. Postscript: the family lost even when it was allowed to cheat

The aggregates group was **dropped** from feature set v2 on its honest numbers
(−1.63% val MAE at 15%, `docs/ablation_m3.md` §4). This drill adds a second
reading of that result which is easy to miss.

Arm B is the version of the family the competition write-ups actually describe —
group statistics over every month the fitter can reach — and on the month it was
allowed to see it beat the honest arm by only **1.56%**, while losing **3.83%**
on the month it was not.

The tempting next line is to compare arm B's **3.4852** against v1's **3.4935**
from the ablation and conclude the family barely beats five plain columns even
when cheating. **That comparison is not available and is not made here:** the
ablation's v1 was fitted on six train months and this drill's arms on five, so
the two numbers describe different experiments and their difference is not
attributable to features. What the drill licenses is the within-drill
comparison — A versus B, one changed line — and nothing wider.

What both readings do support is the §3 conclusion of `docs/ablation_m3.md`:
whatever made these features decisive in 2017 is weaker here, because our zone
ids already encode the OD pair the aggregate is keyed on and the competition's
coordinates did not. A properly-powered version of the "even cheating, is it
worth it?" question would be a v1-on-five-months control fitted beside these two
arms, and it is named here as the missing third arm rather than approximated.
