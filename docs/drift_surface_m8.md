# The drift surface, made trustworthy — M8-S1 leg 1

*Executor session, 2026-08-21. Four M7 obligations, in the order the M8 kickoff
fixed: **F-051** (A-9's arithmetic) → **F-052** (the dead second home) →
**F-050** (the board's persistence and its absence rule) → **F-046**'s honesty
sentence. A fifth, **F-053**, was found by this story's own first command and
closed in it.*

**Nothing in this leg moves a threshold.** The 0.50 volume bar, the 0.10
per-column PSI bar, the two-of-five count and the 40-day staleness window are
byte-unchanged. What moved is one denominator, one deleted file, one volume,
one new signal, and several paragraphs that were true about the design and not
about the code.

---

## 0. Why the order was fixed, and it is not cosmetic

REV's condition on F-051 was that it *"must land before any milestone treats
this board as a standing operational surface."* F-050's decision — a
PersistentVolume plus an absence rule — is precisely what makes the board
standing. So the two are one story, and the arithmetic is repaired **before**
the surface it is measured on becomes something an on-call is expected to
believe. Everything below is in that order.

---

## 1. F-051 — the volume ratio is monotonic in the collapse now

### What was wrong

`drift._days` divided by `COUNT(DISTINCT CAST(tpep_pickup_datetime AS DATE))` —
the days that **held a trip**. A day on which the city took no trips therefore
left the numerator *and* the denominator together, so `volume_ratio` measured
*how busy were the days that happened*. That quantity **rises** as a shutdown
deepens.

REV measured it by deleting 2020-03's quietest days outright — a strictly worse
month. This story re-measured the same counterfactual **through the shipped
functions** (`make drift-monotonicity`, `scripts/f051_counterfactual.py`), which
is the half REV's script could not do: `rev_rederive_m7.py` deliberately does
not import the module under review, so re-running it would print the same two
columns whatever the code now does.

```
  zeroed   trips left |  /calendar   ratio      A-9 |  /observed   ratio      A-9
  ----------------------------------------------------------------------------------
       0    2,948,237 |     95,104  0.3913    FIRES |     95,104  0.3913    FIRES
       6    2,896,959 |     93,450  0.3845    FIRES |    115,878  0.4768    FIRES
       8    2,874,897 |     92,739  0.3816    FIRES |    124,996  0.5143 *SILENT*
      14    2,743,573 |     88,502  0.3642    FIRES |    161,387  0.6641 *SILENT*
      15    2,699,073 |     87,067  0.3583    FIRES |    168,692  0.6941 *SILENT*

  shipped denominator (calendar): monotonically falling = True; never silent after first firing = True
  old denominator (observed days): ROSE at k = [1..15]; SILENT at k = [8..15]
```

The old column is not decoration — it is the **control**. A counterfactual that
only showed the new series falling would be consistent with a month that was
never at risk; showing the old one rise past the bar in the same table is what
makes the fix legible. The script FAILS if the old arithmetic *stops*
reproducing F-051, for the same reason.

### The fix, and what it is not

`drift.calendar_days(months)` — `calendar.monthrange` per month, the same
authority `verify-m7` §3 already trusts for the mart's grain. The bar did not
move: `docs/slo_serving.md` §8.4 and A-9's own annotation have always said
*"trips per day"*, and no reader of either would have guessed *"per day on which
trips occurred"*. This is **implementation catching up to its own
documentation** (F-041's family), not a threshold change, and therefore not a
PO fork.

`_observed_days` survives as a **diagnostic** and is now reported beside the
denominator, in the record and in the printed line:

```
[drift]   denominator: 31 CALENDAR day(s), of which 31 held a trip (F-051: a day
          with no trips must not leave the denominator with the numerator)
```

That pair is what makes "the three recorded ratios are unchanged" readable off
the record instead of taken on trust — and they are unchanged, byte for byte:
**0.8336 · 0.8776 · 0.3913**, with `current_trips_per_day` and
`reference_trips_per_day` producing **no diff line at all** when the three
records were recomputed.

### The property, which is the actual deliverable

Four tests in `tests/unit/test_monitoring_drift.py`, and the important one is
not the positive:

* a strictly worse collapse produces a strictly lower ratio, every step;
* once the 0.50 bar is crossed, a deeper collapse may not walk back across it;
* **the OLD denominator must still be non-monotonic** — pinned so the defect
  cannot return through a future edit that "derives the days from the data" for
  tidiness;
* a 20-of-31-day extract reads as a two-thirds volume collapse, not as health.

### One thing found on the way: PSI was not deterministic

Recomputing the three months moved several PSI values in their **17th
significant digit** (`0.0015194096507573718 → 0.001519409650757372`) with
nothing else changed. Cause: float addition is not associative and `_psi` walked
`set(ref) | set(cur)`, so the last bit was a function of the process's string
hash seed. Nothing downstream reads that digit — but this module's own docstring
argues for exact SQL counts over a sampled estimate on the grounds that *"a
sampled estimate is a worse number that also changes between runs"*, and a
number that changes between runs is not the shape to defend that with. The union
is sorted now, and two consecutive runs are identical apart from `computed_at`.

---

## 2. F-052 — the dead second home, and the diagram that cited it

`configs/drift.yaml` is deleted. It had sat byte-unchanged since the planning
kit, was read by **nothing**, and both of its numbers disagreed with what M7
shipped: `reference_month: "2019-08"` (the *test* split — as a drift reference,
the very thing `drift.py`'s docstring argues against) and
`drift_share_threshold: 0.5` (3 of 5 columns) against A-8's live PSI ≥ 0.10 on
≥ 2 of 5.

It was not inert, and that is the whole point of fixing both halves together:
`docs/m7_flow.html` rendered both numbers in its stamp line and again under
**"Sources of truth."** The page is corrected everywhere a human reads it —
stamp, the drift-check node, the Gate-2 diamond (which now shows A-8's and A-9's
real conditions), signature B's table, and the footer — with a dated note saying
what it used to claim. The diagram is a planning artefact from 2026-08-16; the
correction leaves that provenance visible rather than pretending it was always
right.

The durable half is the test. F-013's law was enforced by a knob tuple of five
**promotion**-gate names, so a drift bar in `configs/` walked straight through
it for a milestone. F-013 is not a law about the promotion gate — it is a law
about **bars** — and the tuple now carries `reference_month`,
`drift_share_threshold`, `psi_threshold` and `volume_ratio_threshold`.

---

## 3. F-050 — the board survives a pod, and its absence is a page

### The decision, and why neither half is honest alone

The boundary decided **(a)+(b) together** after the recurrence was measured:
three observations in 24 hours, all host restarts, all of them emptying an
`emptyDir` gateway completely.

* **(a) alone** leaves nothing watching a real deletion.
* **(b) alone** — an `absent()` rule on an `emptyDir` gateway — pages on every
  ordinary reboot of a laptop, which is exactly the noise that trains an
  on-call to ignore a signal.

Together: the volume removes the event that recurs here, and A-11 fires when
somebody *deleted* something.

`make backup` ran first (law 1 — the tenant gains state):
**`2026-08-21T05-00-56Z`, 6 databases + 418 objects, 1.7 GiB**, every dump
verified.

### What was actually turned on, read rather than guessed

The subchart's values were read live (`helm show values
prometheus-community/prometheus-pushgateway`) — the M7-S3 fullname-prefix lesson
says guess nothing about this chart:

* `persistentVolume.enabled: true`, `size: 128Mi`, `mountPath: /data`;
* `extraArgs: --persistence.file=/data/pushgateway.data`, checkpoint
  `--persistence.interval=10s`;
* `strategy.type` is **already `Recreate`** in the subchart's own defaults,
  which is what a node-local RWO volume needs — F-033 avoided by construction
  rather than by repair.

The interval matters and is argued rather than defaulted: a clean SIGTERM makes
pushgateway write on exit, so the chart's 5-minute default would have passed
this story's own survival drill and lost the push on the failure the volume
exists for — a laptop being switched off. Ten seconds costs a few kilobytes,
periodically, to hold a number produced once a month.

Read back off the cluster:

```
NAME                                STATUS   CAPACITY   ACCESS MODES   STORAGECLASS
prometheus-prometheus-pushgateway   Bound    128Mi      RWO            standard

args=["--persistence.file=/data/pushgateway.data","--persistence.interval=10s"]
```

### A-11, and why A-10 could never have done this job

```yaml
- alert: DriftMetricsAbsent
  expr: absent(taxi_drift_last_run_timestamp_seconds{job="taxi-drift"})
  for: 10m
```

A-10 is `time() - max by (month) (taxi_drift_last_run_timestamp_seconds) >
3456000`. Over **zero** series that expression is *zero series*, not a large
number — so a gateway that lost its store produces no stale metric, it produces
no metric, and A-10 sits `inactive` while every panel renders empty. A-10 now
carries a `blind_spot` annotation saying so at the rule, where an on-call reads
it, and `docs/slo_serving.md` gains **§8.5a** arguing SLO-D4.

The 10-minute sustain is argued from the only benign cause — a pod replacement,
which re-serves the same series as soon as it is Ready. This drill measured that
at **13.12 s**, so the sustain carries nearly two orders of magnitude of
headroom. An hour would be defensible by A-10's own monthly-cadence logic; the
shorter window wins because a wiped board costs nothing to notice and a great
deal to leave — and because a drill has to be able to watch it fire.

What A-11 still **cannot** see is stated in §8.5a rather than netted out:
`absent()` is a statement about the whole selector, so a *partial* loss — one
month's group deleted while two remain — leaves it inactive.

### The proof, prediction first

`make drift-persistence-drill` (`scripts/drift_persistence_drill.py`), with
`automation/runs/m8-drift/persistence-prediction.json` **committed before the
run** and pinned to the code by a unit test. Its negative predictions are the
load-bearing half — chiefly *A-10 must stay inactive through a total loss of the
drift surface*, because if A-10 fired here, A-11 would be redundant and the
finding would have been wrong.

**PASSED — 16/16 checks** (`automation/runs/m8-drift/persistence.json`):

```
[persistence-drill] phase 0 — what is actually mounted (read, never assumed)
ok   the gateway has a BOUND PersistentVolumeClaim: ['prometheus-prometheus-pushgateway']
ok   the running container carries --persistence.file (args:
     ["--persistence.file=/data/pushgateway.data","--persistence.interval=10s"])

[persistence-drill] phase 1 — push the REAL 2020 numbers (F-050's recorded one-command fix)
     pushed 2020-01: volume ratio 0.8336
     pushed 2020-02: volume ratio 0.8776
     pushed 2020-03: volume ratio 0.3913
ok   the gateway holds 48 taxi_drift_* sample(s) after the push

[persistence-drill] phase 2 — delete the gateway pod mid-life; the series must outlive it
     pod before: …-cd5988f6c-7bjk4 uid=bf053286-…
     pod after:  …-cd5988f6c-l5zcd uid=2a1591bc-… (ready after 13.12s)
ok   a DIFFERENT pod object is serving — identity, never name (M4-S5)
ok   the NEW pod serves the SAME 48 sample(s) the old one held (before=48) — the store
     survived the pod. On an emptyDir this read 0, three times, on host restarts (F-050)

[persistence-drill] phase 3 — wipe the drift series deliberately; A-11 must page and A-10 must not
ok   DriftMetricsAbsent is inactive BEFORE the wipe (30s after the push cleared the state
     F-050 left the gateway in)
ok   the gateway now holds 0 taxi_drift_* sample(s)
ok   Prometheus sees no taxi_drift_volume_ratio series at all — the board is blank, which is
     exactly what a calm month looks like
ok   DriftMetricsAbsent (A-11) FIRED 625.1s after the wipe (predicted about 600s)
ok   Alertmanager holds it — a rule firing only in Prometheus's own UI has not reached anybody
ok   DriftMetricsStale (A-10) stayed inactive through a TOTAL loss of the drift surface
ok   ScoringVolumeCollapse (A-9) is inactive while the series are gone

[persistence-drill] phase 4 — re-push the real numbers; A-11 clears and March is back
ok   the gateway holds 48 sample(s) again (was 48)
ok   DriftMetricsAbsent cleared 37.8s after the re-push — the rule follows the data, not latched
ok   ScoringVolumeCollapse (A-9) is pending again — the board ends carrying the truth
PASSED — 16/16 checks
```

Four numbers worth keeping:

* **48 samples survived a pod delete.** The same read against an `emptyDir`
  gateway returned 0, three times, on host restarts — that is F-050 in one line.
* **13.12 s** from `kubectl delete pod` to a *different* pod object serving the
  same data. This is the number A-11's sustain is argued against, and it is why
  10m is generous rather than arbitrary.
* **625.1 s** from the wipe to A-11 firing, against a 600 s sustain — the extra
  25 s is one scrape plus one evaluation, exactly as a `for:` should behave.
* **A-10 inactive, and A-9 inactive, throughout the wipe.** The negative
  predictions held: A-10's blind spot is now *demonstrated*, and the state that
  used to be indistinguishable from a calm month is the state that now pages.

The board ends carrying the truth. The drill's last act is to push the real
numbers back, so A-9 returns to `pending` for 2020-03 — March 2020 really did
lose 61% of its trips, and latching that off to tidy a transcript would be
publishing a false board (M7-S3's rule, inherited).

---

## 4. F-046 — the sentence, and what it commits the program to

`docs/slo_serving.md` §8.1 now states the **window's** blindness beside PSI's:

> *A regime change confined to part of a month is invisible to SLO-D1 at monthly
> grain regardless of which columns are watched: 2020-03 measured a largest input
> PSI of 0.0217 — below an accepted July 2019's 0.0323 — while its last ten days
> ran a different city.*

with the mechanism in the form that generalises (*a row-weighted average of a
collapse is weighted by exactly the rows that disappeared*), the reliance that
makes accepting it honest (A-9, monotonic since F-051 — which is why the two
findings are in one story and in that order), and the residual that is **not**
covered: a shape change with **no** volume change, confined to part of a month,
would be missed by both rules.

The upgrade — a daily or rolling input-drift window — is deliberately **named
and not scheduled**. It needs its own 2019 *daily* headroom leg before any bar
can exist, and choosing the window after seeing which window would have fired is
the same move as walking a threshold. The counterfactual on 22–31 March is left
unrun for exactly that reason.

---

## 5. F-053 — a backup that was running a restore drill

Found by this story's first command. `scripts/platform_backup.sh` writes
`MANIFEST.txt` from a heredoc whose delimiter is unquoted (its body interpolates
`$(human …)`), and the sentence added at M6-S5 to record the restore rehearsal
named its target **in backticks**. Backticks in an unquoted heredoc are command
substitution, so **every `make backup` since 2026-08-19 executed `make
restore-drill`** and pasted its stdout into the manifest. The tell was five words
of `make`'s own `Entering directory` chatter sitting mid-sentence in a lifeboat
artefact nobody reads until an incident.

Dated by the artefacts themselves: the 2026-08-19 manifest is clean, 2026-08-20
and 2026-08-21T04-53-42Z both carry the splice. Blast radius, measured rather
than assumed: `automation/runs/m6-restore/restore_drill.json` still has its
2026-08-19 mtime, so the substituted drill never completed — it exited early,
its stderr going to the terminal rather than into the substitution. That is
luck, not design: `restore_rehearsal.py` creates and drops `<db>_restore_drill`
databases in the ONE Postgres, and it was being launched from inside a backup,
against a backup directory that was still being written.

This is **gotcha #60 for the second time** (M4-S4: a pod manifest's own
explanatory comments naming `tar` and a docker command RAN them). The lesson had
no test, which is why it came back. It has one now — repo-wide over every
`scripts/*.sh` and the Makefile, skipping heredocs with quoted delimiters,
failing on an unescaped backtick in the body — red-teamed by reintroducing the
exact two lines (RED, naming `platform_backup.sh:185` and `:186`) and restoring
byte-identically.

The polluted manifest is **kept** at
`/home/longt/dvc-remote/nyc-taxi-platform-backups/2026-08-21T04-53-42Z/MANIFEST.txt`,
and the clean one written by the same command seven minutes later is its
control.

---

## 6. What this leg did not touch

`@champion` version **2**, read and never written. No InferenceService, no
alias, no model, no fit. No settled data pin moved. Every threshold in
`infra/monitoring/alerting_rules.yml` is byte-unchanged except for the addition
of A-11, which introduces no comparison at all. `make verify-m7` green at leg
exit — its §5 now passing through the **present** branch rather than the
*restarted* one it has taken three times.
