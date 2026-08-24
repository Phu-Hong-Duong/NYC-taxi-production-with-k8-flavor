# The F-016 replay wall (M9-S6) — the edit was not made, and this is why

**Status: PARKED at `AWAITING_PO 2026-08-24-4`. Nothing was edited.**
`configs/train.yaml` is byte-identical to `origin/main`; `gate.decide` carries no
incumbent margin; `@champion` is version 2 / `feature_set v2`; `make verify-m2`,
`make verify-m3` and `make verify-m7` were all run GREEN before and after this
session's only additions (a reader, its record, four tests and these documents).

## 0. What this story was chartered to do

`docs/milestones/M9_EPILOGUE_KICKOFF.md` M9-S6 charters **F-016 option B** — the
PO's answer of 2026-08-24 (AWAITING_PO 2026-08-18-1): the gate's *incumbent*
KPI-09 condition gains a margin of **≥ 0.50%**, DR-02's own smallest
pre-registered materiality bar, with KPI-10 non-regression unchanged. It is a
PO-sanctioned gate edit, which is the one edit class a gate ever accepts.

The same charter names the wall that edit must clear **before it lands**, and
the rule for hitting it:

> `verify-m2` §2, `verify-m3` §5 and `verify-m7`'s retrain leg all REPLAY
> recorded verdicts through `gate.decide` **as it exists on disk**. … **If any
> replay flips, STOP — that is a finding and a PO question, never an edit to the
> replay** (gotcha #50; the replays exist precisely to catch a loosened gate, and
> they must be equally loud about a tightened one).

The wall was asked. **It fired.** So this document is the finding, not the edit.

## 1. The measurement

`scripts/f016_replay_probe.py` is a READER. It takes the real `gate.decide`
verdict for every condition **except** the incumbent KPI-09 one, applies a
simulated margin to that one itself at `INCUMBENT_MAE_DECIMALS` (the precision an
incumbent's number exists at — gotcha #42), and compares the result with what was
recorded. It edits nothing, touches no registry, fits nothing, and runs in
seconds. Record: `automation/runs/m9-f016/replay-wall.json`.

```
$ uv run python scripts/f016_replay_probe.py
[f016] 9 recorded verdict(s) replayed · 2 FLIP(S)
[f016]   FLIP champion v1 (automation/runs/m3s5/bakeoff.json): recorded PROMOTE,
         under a >= 0.50% margin REFUSE — challenger 3.2608 vs incumbent 3.2608 min = +0.0000%
[f016]   FLIP lightgbm-v1 (docs/promotion_gate_m3.md): recorded PROMOTE,
         under a >= 0.50% margin REFUSE — challenger 3.2608 vs incumbent 3.2608 min = +0.0000%
```

| leg | source | verdict | recorded | under B | vs incumbent |
|---|---|---|---|---|---|
| verify-m3 §5 | `m3s5/bakeoff.json` | floor | REFUSE | REFUSE | −2.7907% |
| verify-m3 §5 | `m3s5/bakeoff.json` | **champion v1** | **PROMOTE** | **REFUSE** | **+0.0000%** |
| verify-m3 §5 | `m3s5/bakeoff.json` | artisan v2 | PROMOTE | PROMOTE | +0.5612% |
| verify-m3 §5 | `m3s5/bakeoff.json` | auto-on-v1 | REFUSE | REFUSE | −7.4522% |
| verify-m3 §5 | `m3s5/bakeoff.json` | auto-on-v2 | PROMOTE | PROMOTE | +0.6287% |
| verify-m2 §2 | `promotion_gate_m2.md` | hobbled-shuffled-target | REFUSE | REFUSE | *no incumbent* |
| verify-m2 §2 | `promotion_gate_m2.md` | lightgbm-v1 | PROMOTE | PROMOTE | *no incumbent* |
| verify-m2 §2 | `promotion_gate_m3.md` | **lightgbm-v1** | **PROMOTE** | **REFUSE** | **+0.0000%** |
| verify-m2 §2 | `promotion_gate_m3.md` | champion-v1-plus-0.06min | REFUSE | REFUSE | −0.1809% |

`verify-m7`'s retrain leg is **not** affected and was checked rather than
assumed: it reads the frozen check list the record itself carries
(`retrain_prediction_check._structural_incumbent_only`), not a live `decide()`
call, so a config change cannot move it.

## 2. Where the kickoff's arithmetic was short, precisely

The charter did the sum on three numbers and got the right answer for each:
M2's transcripts carry no incumbent (the alias was unset — nothing to consult);
M3-S5's **winner** promoted at +0.63% ≥ 0.50%; M7-S4's retrain refused at
−0.03%. All three hold. It missed two things, and neither is a slip of
arithmetic — both are about which verdicts the legs actually read:

1. **`verify-m3` §5 replays all FIVE bake-off contenders**, not just the winner.
   One of the five *is the incumbent*, scored as a contender.
2. **`verify-m2` §2 parses `docs/promotion_gate_m3.md` as well as the M2
   document**, and the M3 document's transcripts do carry incumbents.

This is worth stating plainly because it is the reusable part: *the population a
replay leg reads is a property of the leg's code, not of the milestone its name
carries.* The charter reasoned about the verdicts a human remembers; the legs
read the verdicts a file holds.

## 3. What the flip actually is — and it is one fact, not two

Both flipped rows sit at **exactly +0.0000%**: a challenger whose KPI-09 is
numerically identical to the incumbent's.

- **M3-S1** re-fitted `lightgbm-v1` on the full configured months and measured
  **3.2608** on the untouched holdout — the incumbent's own recorded value, to
  the four decimals an incumbent exists at. Non-regression admits it.
- **M3-S5**'s bake-off scored the serving champion as one of its five
  contenders, so the `champion v1` row is *the incumbent judged against itself*,
  +0.0000% by construction.

**So the number 0.50% is not what stopped this.** The probe run at a margin of
**0.001%** flips the same two rows. Any margin above zero refuses a challenger
identical to the incumbent, so **the identity case has to be answered by
whatever version of B lands, at whatever bar the PO picks** — a smaller number is
not a route around it. This is pinned as arithmetic in
`tests/unit/test_training_gate.py` (`test_the_identity_case_is_refused_by_ANY_positive_incumbent_margin`)
so the next person to attempt B meets the case rather than rediscovering it.

**Neither flipped verdict moved an alias, and that materially lowers the
stakes.** M3-S1's run was `--no-promote` (nothing moved; `@champion` was version
1 before and after). M3-S5's bake-off gave the alias to `auto-on-v2`, not to the
`champion v1` row. **No promotion that actually happened is invalidated by B** —
what B changes is two verdicts that were printed and recorded and never acted on.

## 4. How close B runs to history

`artisan v2` — recorded PROMOTE at 3.2425 against incumbent v1's 3.2608 — clears
the chosen bar by **0.0612 percentage points** (+0.5612% vs ≥0.50%) and would
flip at a bar of 0.57%. That is the daylight between the PO's number and a third
flipped verdict, and it is asserted in a test rather than remembered
(`test_the_nearest_surviving_recorded_verdict_has_six_hundredths_of_a_point_of_daylight`).

## 5. The options, with their costs

Full text, with the recommendation and its honest price, is at **AWAITING_PO
2026-08-24-4**. In one line each:

- **(a) Land B; teach both replay legs to accept a verdict whose sole differing
  condition is the new margin.** Cheapest to demonstrate, and it is the edit the
  charter forbids: it admits *any* future incumbent-margin change silently,
  which is the property the red teams exist to defend.
- **(b) Land B; replay every verdict against the incumbent margin that was in
  force WHEN IT WAS TAKEN, and add a separate, unweakened check that the margin
  on disk never decreases.** — **recommended.** Direct precedent: `verify-m2` §2
  already replays M2's verdicts against the floor NAME recorded in the block
  (*"a verdict is replayed against the bar it was actually taken against, or it
  is not a replay"*) and pins the DIRECTION of the floor change separately.
  **Its honest cost:** the historical records carry no incumbent margin — there
  was none — so the in-force value must be read from an absence, which is the
  permissive default this program distrusts (F-048's rule). The mitigation is
  real but is work: the margin becomes a RECORDED field on every future verdict,
  so the inference is confined to a frozen, enumerable set of nine, already
  written down in `automation/runs/m9-f016/replay-wall.json`.
- **(c) Land B with the identity case carved out explicitly.** Looks tidy and
  half-works: it resolves M3-S5's `champion v1` row, and it does **not** resolve
  M3-S1's, whose challenger was a *fresh fit* that happened to score identically
  and is not the incumbent version by any test the numbers support.
- **(d) Decline B; keep non-regression and record the decision.** Free, and
  F-016's own ledger row already admits this closure shape. Cost: the asymmetry
  F-016 named stays open — though nothing has churned on it yet, M7-S4's retrain
  having refused at −0.03% under the existing condition.

## 6. What this session did NOT do, stated so it is checkable

No config edit · no change to `gate.decide` · no change to any replay leg · no
fit · no alias move · no registry version · no cluster mutation · no threshold
moved in either direction. The additions are one reader, one tracked record,
four tests that assert arithmetic, and these documents. `make verify-m2`
(55/55), `make verify-m3` (46/46) and `make verify-m7` (62/62) were run GREEN as
the baseline before the probe was written, and are unaffected by anything in it.
