# Shadow analysis — version 1 against the champion, on the wire (M6-S3)

**Author:** DA seat (role block M6-S3; SRE Accountable, DA Responsible for this memo)
**Date:** 2026-08-19
**Record:** `automation/runs/m6-shadow/disagreement.json` (+ `.csv`, row grain)
**Reproduce:** `make shadow-run` — a reader; it deploys nothing and moves no alias.

## Verdict: **NO-GO for version 1.** Do not shift rider traffic to it.

Named, as the kickoff requires, and it is an input to M6-S4's go/no-go rather
than a recommendation about the model itself.

**And the reasoning is not the one that was expected.** The kickoff predicted this
memo would say no because v1 is "the known-worse model", and pre-registered that
outcome as the ritual working. The measurement is less flattering to the ritual
than that: on this sample **v1 is not much worse, and in one segment it is
slightly better**. The verdict is still no, and §5 says why a thin margin does not
become a reason to ship a challenger.

## 1. What was measured, and what it is not

The same **1,016 raw quote requests** were sent to both models on the live wire —
1,000 stratified rows from `trips_test` (the untouched holdout month) plus parity's
16 declared hazards. Each target's matrix was built through the ONE
`taxi_mlops.features` path: **v1's 5 columns** for the shadow, **v2's 24** for the
champion. So a delta here is two models disagreeing, not two clients disagreeing.

**This is not a re-run of the M3 bake-off**, and no number below may be compared
with one from it. Two reasons, both structural:

- **The sample is stratified, deliberately.** 250 rows each from ordinary,
  airport, no-geometry and long-trip. A flat random sample would have been ~99%
  ordinary and carried roughly zero long trips — nothing to say about the three
  segments this memo exists to examine. The consequence is that every *overall*
  number here over-weights hard rows by construction: the champion's MAE reads
  **8.61 min** on this sample against **3.2403** on the full holdout. The full
  holdout remains the measurement of record (`docs/bakeoff_m3.md`).
- **The hazards carry no truth.** Several are synthetic dates no trip has. Every
  accuracy statistic is computed on the sampled rows only; the record marks this
  per segment with `has_truth`.

## 2. The disagreement table

`|d|` is `|shadow − champion|` in minutes. "champ closer" is the share of rows
where the champion's absolute error is the smaller of the two.

| segment | rows | mean \|d\| | p90 \|d\| | max \|d\| | champ MAE | shadow MAE | champ closer | champ ≤5 min | shadow ≤5 min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ordinary | 250 | 0.52 | 1.24 | 2.49 | 2.80 | 2.88 | 50.0% | 81.2% | 81.6% |
| airport | 250 | 1.33 | 3.14 | 9.87 | 5.97 | 5.99 | 56.4% | 59.6% | 58.8% |
| no_geometry | 250 | 0.90 | 2.46 | 8.21 | 9.28 | 9.36 | **47.6%** | 43.6% | 42.8% |
| long_trip | 250 | 2.65 | 5.34 | **36.42** | 16.41 | 17.51 | **63.6%** | 17.6% | 18.8% |
| declared_hazard | 16 | 4.22 | 15.26 | 25.10 | — | — | — | — | — |
| **ALL** | **1016** | **1.40** | **3.27** | **36.42** | **8.61** | **8.93** | **54.4%** | — | — |

## 3. Where they diverge, and what it means

**Long trips are the fault line, and they are the one place the champion clearly
wins.** Mean disagreement is **2.65 min** — five times the ordinary segment's — the
worst single row is **36.42 min**, and the champion is closer on **63.6%** of rows
with a full **1.10 min** of MAE between them. The direction is one-sided: the
shadow quotes *lower* on **72.4%** of long trips (mean signed delta **−1.90 min**).
That is v1's known ceiling, visible from a second instrument: with no distance
proxy at all it regresses hard toward the middle of the distribution, and the
longer the trip the more that costs. M2-S4 measured the same shape offline (the
100–120 min band at 0.000% within 5 min); this is it on the wire.

**Airports are the finding, and they are a second look at an open question.**
`docs/error_memo_m2.md` §7 row 2 has been open since M3-S5: the airport error gap
held at **1.91×** even though v2 carries the OD centroid geometry §4 predicted
would identify airports. This shadow gives that row an independent, wire-side
look, and it agrees with the open row rather than closing it — **champion MAE
5.97 against the shadow's 5.99**, a gap of **0.02 minutes**, with the champion
ahead on the coin-flip-ish 56.4% of rows and actually *behind* on the
within-5-minutes rate (59.6% vs 58.8%).

So the geometry v2 carries is worth approximately **nothing at airports**, which
is the same conclusion §7 row 2 reached from the other side. **§7 row 2 stays
open, and it now has two independent measurements pointing the same way** — that
is a stronger position for M7's drift/retrain memos to start from than one. The
natural next question, which is M7's and not this memo's: airports are precisely
where straight-line distance is least informative about duration (fixed-fare JFK
runs, terminal-side queuing, tunnel/bridge choice), so a centroid haversine may be
structurally unable to help there regardless of how it is encoded.

**The no-geometry segment is the one the shadow wins, and it is not an
embarrassment — it is the geometry features doing nothing, twice.** Zones 264/265
have no centroid by design (DR-04 condition 1), so v2's nine geometry features are
all NaN there. The champion is closer on only **47.6%** of those rows — i.e. the
shadow is closer more often — and the shadow's within-5-minutes rate is within a
point. Read plainly: on rows where v2's extra features are pure absence, a model
that never had them is a coin flip against it. Both are bad here in absolute terms
(MAE 9.28 and 9.36 against the ordinary segment's 2.80), which is the honest
headline for this segment and a standing argument for M7 giving 264/265 a real
treatment rather than a NaN.

**Ordinary trips are a near-tie: 50.0% closer, 0.52 min mean disagreement, 81.2%
vs 81.6% within five minutes** — the shadow is *marginally ahead* on the
rider-facing rate. On the trips that are almost all of the traffic, these two
models are hard to tell apart.

## 4. What the shadow proves about the SEAM, incidentally

Every one of the 1,016 requests to each target returned a number, including all
250 no-geometry rows — so F-030's `null` encoding holds for a **5-feature** model
that has no geometry columns at all, not just for the champion. And the served
versions were read off the answers themselves: **champion `model_version: 2`,
shadow `model_version: 1`**, so nothing in this table was scored by the model the
reader might assume rather than the one named.

## 5. Why a thin margin is still a NO-GO

The champion wins overall (**8.61 vs 8.93 MAE**, closer on 54.4% of rows) but only
one segment is decisive, and two are ties or losses. A reader could reasonably ask
why that is not a GO for a cheap 5-feature model. Three reasons, in order of
weight:

1. **The measurement of record already answered this, on more data.** The M3
   bake-off scored both models on the **whole** untouched holdout — 5,950,708 rows,
   not 1,000 — and put v2 at **3.2403** against v1's **3.2608**, with the ranking
   identical on val. A stratified 1,016-row sample that over-weights the hardest
   segments is a *lens*, not a re-measurement, and it does not get to overturn the
   holdout. This memo would be committing F-018's error in reverse if it did.
2. **Nothing here is a reason to CHANGE.** v1 is not better; it is *not much
   worse*, in a sample built to find differences. "Indistinguishable on ordinary
   trips and clearly worse on long ones" is an argument for leaving the wire alone.
3. **The thin margin is itself the interesting result, and it belongs to M7.** If
   19 extra features buy 0.32 min of MAE on a hard sample and nothing at all at
   airports, the open question is not "should we ship v1" but "what are those
   features actually buying, and where?" That is a retrain/drift question with a
   named home (§7 row 2, and M7's memos), not a release decision.

## 6. What M6-S4 should take from this

- **The v1 shadow cannot be S4's canary.** Not because of this verdict — because
  of ADR-011 condition 2: v1 answers a different V2 model name and a different
  schema. S4's canary is the champion's own bytes behind the challenger path, as
  the kickoff pre-registered, and **its shadow table is trivially 0.000** — which
  this memo covers in advance, as the kickoff asks.
- **Observe the canary from traffic counters, never from the annotation.**
  ADR-011 condition 1 measured a canary that was configured, linked, silent and
  moving nothing.
- **If a future challenger ever needs a real go/no-go, the long-trip segment is
  the one to gate on.** It is where these two models actually differ, it is where
  the errors are largest, and it is the only segment here that separated them at
  all.
