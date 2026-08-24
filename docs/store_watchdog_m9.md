# The online-store watchdog (M9-S2) — closing R-2

**Owner:** SRE (accountable). **Written:** 2026-08-23 (M9-S2). **Scope:** the Feast
online store that backs the transformer's raw quote boundary. **Bars:**
`docs/slo_serving.md` §9, argued from `automation/runs/m9-store-watch/headroom.json`
and committed before the drill that first crosses one.

M8-S4's three legs each ended with the same sentence and none of them closed it:
*there is no alert on an empty or stale online store.* This is the closure.

---

## 0. The order of work, because it is part of the evidence

M8 law 4, ninth inheritance, and checkable from git rather than asserted here:

| # | what | commit |
|---|---|---|
| 1 | the headroom leg RAN and recorded facts only | `cedb9e8` |
| 2 | `docs/slo_serving.md` §9 argued the bars **from that record** | `cedb9e8` (same commit) |
| 3 | the reader and the rules landed | `c8290da` |
| 4 | the drill's PREDICTION was committed | `408b472` |
| 5 | the drill ran and first crossed a bar | after all of the above |

A bar argued after seeing which bar would have fired is not a bar, it is a
description. The one thing that makes that claim checkable is that step 5's
records were added to git strictly after step 2's document was.

---

## 1. What the store's own sources say about it

`make store-watch-headroom`. Feast writes one Redis key per distinct entity key
per view, so the store's size has a source of truth that is not itself:

| view | distinct entity keys | share | read by the transformer |
|---|---:|---:|---|
| `zone_static` | 263 | 0.46% | **yes** |
| `calendar_day_flags` | 4,383 | 7.60% | **yes** |
| `od_window_stats` | 46,938 | 81.37% | no |
| `pu_hour_window_stats` | 6,104 | 10.58% | no |
| **total** | **57,688** | | |

**Three witnesses agree at 57,688** — the derivation from `data/feast/*.parquet`,
the count `automation/runs/m8-online/materialize.json` recorded on 2026-08-21,
and the live `DBSIZE`. Nobody typed that number.

Two consequences, and they decide the whole design:

* **The key count cannot see the failure that reaches a rider.** The
  transformer's entire dependency is **4,646 keys — 8.054%**. A store that lost
  both its views still reads 53,042 keys (92% of normal) while every quote it
  backs is broken, and zone 132's centroid is **one key of 57,688**: lose exactly
  the key that breaks every JFK quote and `DBSIZE` moves by 0.0017%. So the count
  is coarse *by construction* and the canary has to be the load-bearing signal.
* **There is no partial-loss mechanism.** `noeviction`, 14.32 MiB against a
  512 MB cap, and a materialization that either completes or fails. The realistic
  population is bimodal — full, or gone.

---

## 2. "Stale" had to be redefined before it could be alerted on

SLO-D3 asks whether the drift *job* ran recently and argues 40 days from a
monthly cadence. That question has **no answer here**: this store's data is
settled — 2019 windows, a 2019 shapefile, a holiday table to 2030 — so a store
filled in August 2026 is exactly as correct in 2027. A clock-age bar on its
contents would be a number chosen to avoid paging.

> **A store is stale when it disagrees with the sources it was filled from.**

That is a comparison between two quantities one reader measures on one run, and
it needs **no threshold at all**. `taxi_online_store_keys <
taxi_online_store_keys_expected`. It self-updates when `make feast-sources`
legitimately changes the sources, and the window in between — sources changed,
store not refilled — is exactly the stale state the rule exists to catch.

---

## 3. What was built

`make store-watch` reads two things and pushes four series under job
`taxi-store-watch`; it applies no bar and prints no verdict.

* **`DBSIZE`, off the running server** — the `feast_materialize.sh` readback
  idiom, never off the command that wrote it.
* **A four-claim canary through the feature server**, on the same
  `/get-online-features` wire the transformer uses.

**Signals: A-12** (two rules, the A-5 precedent) and **A-13**.
`OnlineStoreCanaryFailing` is `== 0` — a property. `OnlineStoreIncomplete`
compares the store against its sources — no number on either side.
`OnlineStoreWatchdogAbsent` is `absent(...)`, A-11's argument one board along:
A-12's freshness clause is structurally unable to see its own series disappear,
because `time() - stamp < 1800` over zero series is zero series.

**The one number in any of these expressions is `1800`** — A-4's freshness
window — and its cost is named rather than netted out in §9: this reader has no
scheduler (M9 legislates no new Flyte trigger, and the story adds no image and
no CronJob), so a reading older than 30 minutes makes A-12 **inactive** rather
than falsely green.

### `store_reachable` is reported as a 0, which inverts A-4's rule on purpose

`push_serving_version.py` refuses to push when a side is unreadable and is right
to: an unknown served version is not a mismatch. **Here the rule inverts.** If
the Redis pod is gone, *"I could not read `DBSIZE`"* is not a gap in the
measurement — it **is** the measurement, and a reader that withheld it would
leave the last healthy reading to go quietly stale. Honest cost: a broken
`kubectl` on the operator's laptop reads the same as a broken store.

---

## 4. The drill, and the prediction it was judged against

`make store-watch-drill`, four phases, prediction written to disk before the
first mutation and committed (`automation/runs/m9-store-watch/prediction.json`,
pinned by a test against the drill's own literal).

### The rider's request: 422, and the kickoff expected 503

**The prediction said 422 and it held.** With the store empty the transformer
answered:

```
HTTP 422 {"error": "the online feature store has no calendar row for ['2019-07-04'].
REFUSED rather than quoted: ..."}
```

The M9 kickoff expected a 503, and the superseded expectation is kept in the
prediction beside the new one rather than quietly replaced. The reasoning that
produced 422 is worth keeping because it is a fact about which half of the store
protects a rider:

* the **geometry** half *structurally cannot* refuse. An all-null centroid table
  is exactly what zones 264/265 legitimately produce, so a client cannot tell an
  empty store from TLC's two non-places. This is the failure mode ADR-012 named
  and M8-S4 leg 3 restated.
* the **calendar** half *does*. Every request carries a date and
  `calendar_from_store` RAISES on an unanswered one — F-019's guarantee, carried
  onto the store's wire at M8-S4 leg 3 rather than left as a property of a CSV.

So the thing standing between an empty store and a confident wrong number is a
guard written for a different reason two stories earlier. **503 is what an
UNREACHABLE store produces**, and that is a different phase of this drill.

> **DATED NOTE 2026-08-24 (M9-S7). This section's headline number is now 503, and
> the 422 above is left standing because it is the finding.** The paragraphs above
> describe the code as it stood on 2026-08-23, and everything they say about
> WHICH HALF protects a rider is unchanged and still correct — the geometry half
> still structurally cannot refuse, the calendar half still does. What was wrong
> was whose fault the refusal was recorded as. That 422 put a **totally dead
> dependency outside SLO-A1's error budget** (SLO-R1: *a 4xx is a guard working*),
> so an outage rendered as riders sending bad requests. Raised as **F-062**,
> answered by the PO with option **(b)** on 2026-08-24, landed by M9-S7:
> `calendar_from_store` now asks the store for a date the committed holiday table
> provably covers before it picks a status, so an empty store is **503
> `FeatureStoreUnavailable`** and an uncovered date with a live store is still
> **422**. The re-run's records are in `automation/runs/m9-store-watch/`; the
> 422-era records are kept unedited at `attempt1-422-era/` with their own README,
> because they are the evidence the decision was made from.

### The measured run — 2026-08-24 (M9-S7), the records this document's gate reads

Four phases in one invocation, **36 checks, 0 failures**, against a prediction
committed at `b89eea4` before the first `FLUSHDB`. This run supersedes the
2026-08-23 one below; both are kept because the difference between them IS
F-062, and only this one is checked against by `make verify-m9`.

| observation | measured |
|---|---|
| store emptied | 57,688 → **0** keys (`FLUSHDB`) |
| **rider's quote while empty** | **HTTP 503**, predicted 503 — the finding closed. The refusal names the sentinel it probed and the file that covers it |
| a PAST-HORIZON quote while empty | **HTTP 503** — with nothing answering, "was that date covered?" is a question this deployment cannot answer, so it does not blame the caller for it |
| a PAST-HORIZON quote while HEALTHY | **HTTP 422** naming the year — F-019's typed refusal SURVIVED the change, asserted rather than argued |
| champion's own wire, throughout | **39.0019 minutes** — unaffected |
| `OnlineStoreCanaryFailing` (A-12) | **FIRED at T+162.5 s**, reached **Alertmanager** |
| `OnlineStoreIncomplete` (A-12) | **FIRED at T+162.5 s**, reached **Alertmanager** |
| which claims failed | `['calendar_answers', 'zone_answers']` — the per-series read |
| must-not-fire (A-13, A-2, A-5, A-11, A-4) | all **inactive**, as predicted |
| refill | **57,688 keys back**, **11.6 s** wall-clock |
| both rules cleared | 30.0 s / 0.0 s after the reader saw a healthy store |
| unreachable store (feast-server → 0 replicas) | **HTTP 503**, and answering again **15.1 s** after it came back |
| surface deleted | **A-13 FIRED at T+630.7 s**, reached Alertmanager, **A-12 stayed inactive** — the load-bearing negative, and the first time this drill has run its fourth phase |
| rider's quote after | **HTTP 200, 39.00193715359812 minutes** |

**The two 503s above are different failures and it matters that they are not one
row.** The empty store's is `StoreCoverageError`'s replacement — the calendar
view answered `null` for the request *and* for a sentinel the committed table
covers. The unreachable store's is `FeatureStoreUnavailable` raised at the
transport (`ConnectionRefusedError`). They arrive at the same status by different
evidence, which is what makes the status honest rather than a catch-all.

### The measured run — 2026-08-23 (M9-S2), superseded, kept because it is the evidence

Records at `automation/runs/m9-store-watch/attempt1-422-era/`.

| observation | measured |
|---|---|
| store emptied | 57,688 → **0** keys (`FLUSHDB`) |
| rider's quote while empty | **HTTP 422**, predicted 422 — *and this row is F-062* |
| champion's own wire, throughout | **39.0019 minutes** — unaffected, as predicted |
| `OnlineStoreCanaryFailing` (A-12) | **FIRED at T+162.2 s**, reached **Alertmanager** |
| `OnlineStoreIncomplete` (A-12) | **FIRED at T+162.2 s**, reached **Alertmanager** |
| which claims failed | `['calendar_answers', 'zone_answers']` — the per-series read |
| must-not-fire (A-13, A-2, A-5, A-11, A-4) | all **inactive**, as predicted |
| refill | **57,688 keys back**, 9.9 s wall-clock |
| both rules cleared | 30.0 s / 0.0 s after the reader saw a healthy store |
| rider's quote after | **HTTP 200, 39.00193715359812 minutes** |

The board ends carrying the truth, not a silence (M7-S3's rule).

### A measured limit of the negative check

`nonplace_declines` read **1** through the whole outage. Zone 264 returning
`null` is the correct answer *and* what a totally empty store returns, so the
negative claim cannot distinguish "correctly declines" from "has nothing to
decline with". That is why the two **positive** checks are the ones that fire,
and it is recorded in §9's table rather than left for somebody to rediscover.

---

## 5. What the drill found that was not about the store

**The undo rewrote somebody else's evidence.** `scripts/feast_materialize.sh` is
the one-command repair the runbook names, and it unconditionally writes
`automation/runs/m8-online/materialize.json` — a **tracked** record belonging to
M8-S4, cited by §9 and by this story's own headroom leg. The drill's first run
re-dated it from `2026-08-21T07:52:13Z` to its own minute. Nothing was wrong with
the refill; writing M8's evidence over it was. Same family as gotcha #48 (a
launcher truncating the log of the run it was resuming) and F-053 (a backup
running a restore drill): **when a command is reused as somebody else's repair,
audit what it does to state that already exists.** Fixed with `--no-record`, the
record restored from git, and the drill's own refill measurement kept where it
belongs — in the drill's record.

It was visible at all only because `automation/runs/**/*.json` is tracked
(F-029, option A at M5-S1). Before that it would have been a silent re-dating.

---

## 6. What this deliberately does not cover

* **A store filled from the WRONG sources** has the right key count and passes
  every canary while every value is wrong. `make feast-online-parity` (100
  declared pairs, bar EXACT) is the instrument for that, and it is a gate-time
  check rather than a watchdog.
* **The cadence.** The reader has no scheduler and the freshness clause is what
  keeps that honest rather than green. §9 names the three things that bound the
  gap and does not claim the gap is small.
* **The 4xx billing question.** An emptied store makes every quote a 422, and
  SLO-R1 excludes 4xx from the availability error budget on the grounds that a
  4xx is a guard working — so a totally dead dependency currently spends **zero**
  error budget. A-12 pages, so it is not silent; the status class is **F-062**,
  open and routed to the program close, because changing what the served
  boundary returns is a behaviour change with three parity records behind it.
  > **DATED NOTE 2026-08-24 (M9-S7): CLOSED, and it cost exactly what the bullet
  > above priced it at.** The PO answered (b); the transformer was rebuilt and
  > redeployed, and all three parity records were re-measured at their committed
  > EXACT bars and came back **0.000e+00** — the change touches the error path
  > only, so a nonzero delta would have been a story-stopping finding rather than
  > a bar to widen. An emptied store is **503** now and spends the availability
  > budget. What this bullet correctly did NOT price is the defect the re-measure
  > flushed out: **F-069**, a 404 that left the request body unread and poisoned
  > the next caller on a pooled keep-alive connection.
