# M8 KICKOFF — Feature store (Feast) & the side-by-side   (authored by: ARCH/Fable · 2026-08-21 · v3.0: the Architect is sole author)

Session model stated: **Fable 5 (claude-fable-5)** — architect sessions on any
other model are void (ORG.md rule 7).

**M8 carries no ◆** (BLUEPRINT §9: M8 lists no REV ritual; the next ◆ is
whatever a future boundary declares). The last story exits to the boundary:
`automation/next_session.sh architect 120`.

**The four laws this milestone lives under, stated once at the top.**
(1) **THE CLUSTER IS STATEFUL AND NO M8 STORY MAY TAKE IT DOWN** — unchanged
since M2. Any new in-cluster tenant (a Feast feature server, an online store)
gets **NO hostPort**; it is reached by Service in-cluster and by port-forward
from the host, the Flyte-console/pushgateway precedent. `make backup` runs
BEFORE any tenant that carries state lands (the M4-S2/M5-S1/M6-S1/M7-S3
precedent, unbroken).
(2) **THE DATA IS SETTLED — 2019 AND 2020 BOTH.** Feast's offline store READS
the existing parquet trees and the committed reference tables; it copies
nothing into them and mutates nothing. `dvc status` on every pin
(`data/processed.dvc` · `data/rejected.dvc` · `data/scoring.dvc` ·
`data/scoring_rejected.dvc`) is the story-exit invariant for anything that
touches data. A changed byte in a settled tree is a defect, not a refresh.
(3) **THE ALIAS DOES NOT MOVE IN M8, AND NO MODEL IS FITTED.** A feature-store
milestone serves the EXISTING champion (version 2, feature set v2). No story
invokes the gate, no story mints a registry version, and the champion's
production wire is not cut over: the transformer lands BESIDE the champion
(its own InferenceService, its own host — the M6-S3 shadow precedent), proven
by parity, and any cutover is a named boundary/PO decision, not a story's.
`@champion` version 2 before and after every story, read and asserted.
(4) **THE DEPENDENCY QUARANTINE IS THE DESIGN, NOT THE FALLBACK — measured,
not feared.** Read live at draft time: **Feast 0.66.0 declares
`pandas<3,>=1.4.3`** against this project's pandas **3.0.5** (also
`numpy<3,>=2` ✓ 2.5.2 · `pyarrow>=16.1.0` ✓ 25.0.1 · `>=3.10` ✓ 3.12.14 — the
ONE conflict is pandas, and it is a hard major-version wall, the full-`mlflow`
shape of gotcha #36). So: **no `uv add feast`, ever.** Feast lives in an
isolated venv (gotcha #16's quarantine, the M7-S3 Evidently probe idiom taken
one step further because this time the probe's answer is already known) and
exchanges data with this project through parquet files and, where a live
lookup is needed, through a wire. `uv.lock` must be **byte-identical** at
every M8 story's exit — a checkable invariant, and the kickoff states it so
the executor plans around the wall instead of discovering it at `uv add`.

## 0. Boundary triage of M7 (the closure sweep, folded in)

**Verify re-run (by the approver, this session, 2026-08-21):** `make verify-m7`
→ **GREEN — 62 `ok` sub-checks across 7 sections, exit 0** (counted live:
`grep -cE "ok  "` → 62). Closing line verbatim:
`[verify-m7] GREEN — every M7 sub-check passed.` Highlights, pasted not
remembered: §5 `the gateway holds no drift series and the reason is accounted
for: its container started 2026-08-21T03:55:49+00:00, AFTER the drill pushed
at 2026-08-20T04:38:35Z` (F-050's paired check passing through its *restarted*
branch — the finding's third observation, still once per host restart) · §6
`the challenger was REFUSED and promoted=False … A refusal is a working gate,
not a failed story` · §6 `@champion is version 2, still the run the M3
bake-off recorded as its winner … the pointer never moved (derived, never
typed)` · §7 `the endpoint answered 10.665224 minutes stamped
model_version='2' … reproducing the parity record's 'ordinary-midday' row to
0.000e+00 minutes. M7 ended where M6 did`. The red team was run and PASSED by
the executor at M7-S5 leg 2 (planted `volume_ratio` 0.3913 → 0.4021 — F-045
itself, a ratio of totals where a ratio of rates belongs — RED exit 1 with 3
FAILs from three different artifacts, 59 sub-check lines still passing,
sha256-verified byte-identical restore, GREEN 62/62). The gate re-run here
mutates nothing, per its own law.

**Lineage spot-check (gotcha #20):** `git merge-base --is-ancestor 86a3cf2
origin/main` (M7-S5's merge, PR #49) → ancestor confirmed — deliberately a
different merge than REV's spot-check (`45d8949`, PR #42, also confirmed).
M7 is story PRs **#40–#49** (S4 in four PRs, S5 in two legs; #50 is the
boundary reconciliation after a host reboot, #51 is REV's review — neither is
a story). Tree clean at `5ec090c`.

**REV (◆ owed at M7 and delivered):** fresh-session monitoring review
2026-08-21, `ledgers/signoffs.md` row — **APPROVE WITH CONDITIONS**, producer
EXEC ≠ approver REV. Every published number re-derived from committed
artifacts (`scripts/rev_rederive_m7.py`, read-only, re-runnable, deliberately
NOT importing the module under review): PSI to 15 significant figures,
volume ratios to 16 decimals, the memo's March cut to the row. Two findings,
both S2, neither closable by prose: **F-051** and **F-052**. Both are
dispositioned below with quoted landings, per the review's own conditions.
The sentence REV asked the boundary to read out loud: *M7's central claim is
that A-9 is the marginal A-8 is structurally blind to — and F-051 is a blind
spot inside that marginal.*

**Every open finding, condition, and due debt from M7, dispositioned:**

| Item | Disposition |
|---|---|
| **F-051** (REV condition 1: A-9's volume ratio is non-monotonic in collapse severity — `COUNT(DISTINCT observed date)` lets a day with no trips leave numerator and denominator together; a strictly worse shutdown walks the ratio back across the 0.50 bar, measured 8-days-zeroed → 0.5143 SILENT; a 20-of-31-day extract reads as healthy) | **INTAKEN → M8-S1 leg 1** (the drift-surface remediation story; REV's condition "must land before any milestone treats this board as a standing operational surface" is honored — see F-050's disposition, which makes the board standing). The fix: divide by the **calendar days the window covers**, plus the property test no current test asserts — *a strictly worse collapse must produce a strictly lower ratio* — plus the F-051 counterfactual re-run showing the zeroed-days series now monotonic. **NOT a threshold change and NOT a PO fork**: the bar stays 0.50; the arithmetic moves to match the calendar language `docs/slo_serving.md` §8.4 and the rule's own annotation ALREADY state — implementation catching up to its own documentation is a defect fix (F-041's family). All three shipped months have every calendar day, so 0.8336 / 0.8776 / 0.3913 are unaffected (REV re-derived all three exactly). |
| **F-052** (REV condition 2: `configs/drift.yaml` is a dead second home — wrong reference month, wrong bar, read by nothing, cited by `docs/m7_flow.html` as "Sources of truth"; F-013 recurring) | **DECIDED this triage (ARCH): option (a), REV's recommendation — INTAKEN → M8-S1 leg 1.** Delete `configs/drift.yaml`; correct `docs/m7_flow.html`'s stamp line AND Sources-of-truth to point at `src/taxi_mlops/monitoring/drift.py` + `infra/monitoring/alerting_rules.yml` + `docs/slo_serving.md` §8; widen the F-013 test's knob tuple with the drift knob names (`reference_month`, `drift_share_threshold`) so the next stale bar cannot land. (b) — making the file real — is refused because it argues against M7-S3's own recorded design (the bar lives in ONE rule selector precisely so the pushed numbers stay re-interpretable), and because F-013 itself was closed by deletion, not by adoption. Both halves (config + flow diagram) land together; a corrected config with an uncorrected diagram leaves the false numbers in the artifact humans actually open. |
| **F-050** (a pushgateway restart deletes every drift series; A-10 cannot fire on an ABSENT series; recurrence now MEASURED at once per host restart — twice in the 14 h after it was raised, third observation at this triage's verify re-run) | **DECIDED this triage (ARCH): (a)+(b) together — INTAKEN → M8-S1 leg 1.** The recurrence measurement is what decides it, exactly as HANDOFF (bt) priced: **(a)** — a PersistentVolume with the chart's `--persistence.file` — fixes the event that actually recurs on this machine (host restarts), and once (a) is landed, **(b)**'s stated noise cost collapses: an absence-shaped rule (`absent(taxi_drift_last_run_timestamp_seconds{job="taxi-drift"})`, a new A-id through `render_alert_rules.py` with its `why`) then fires only on a REAL deletion (a cluster rebuild, a wiped PVC) — rare, and exactly what it should page for. Neither is a threshold change. Honest costs stated: the PVC dies with `make destroy` like every PVC here; the values change that adds persistence ROLLS the gateway once, losing the (currently empty) series one more time — re-push after, the gate prints the command. `make backup` first (law 1: a tenant gains state). **This decision makes the drift board a STANDING surface on this machine — which is why F-051's fix is chartered in the same story and lands first.** |
| **F-048** (on-cluster retrain cannot see the host provenance records, so the F-020 scale transfer silently no-ops in a pod — `rescale_factor: null` against the host's 6.6667 for the same champion in the same minute) | **DECIDED this triage (ARCH): (c) + (a) — INTAKEN → M8-S1 leg 2.** **(c)** first and required: `resolve_champion_configuration` REFUSES (loud exit, its own sentence) when the records DIRECTORY is invisible — "no refit record names this run" and "I cannot see any records" are different facts and must never produce the same sentence; with the test that the two absences produce different outcomes. **(a)** as the long-run home: the row count a version's count-scaled knobs were chosen at is provenance that belongs WITH the version — written at fit time by the refit path for every future version, and version 2 **backfilled through a provenance-tag path INSIDE `registry.py`** (additive, never deletes, moves no alias — the module's own laws hold; the tag is the same family as the gate-verdict tags that already travel on versions). Once (a) is landed the pod resolves the scale from the registry and needs no host JSON — which is why **(b) is refused**: the image must not carry evidence it can never be the source of truth for (both rows' shared reason). Ordering stated so the deployed proof-trigger is never left red: land (a)+backfill and (c) in one image, redeploy the trigger once, then the closure evidence — **one observed on-cluster `retrain-schedule-proof` firing whose record shows `rescale_factor` 6.6667 and `round_cap` 2400** (the row's own closing condition). |
| **F-047** (`make image-smoke` RED since M5-S5 — 12 in-image test failures, all `FileNotFoundError` on tracked host records `.dockerignore` correctly excludes) | **DECIDED this triage (ARCH): option (a), the row's own recommendation — INTAKEN → M8-S1 leg 2** (same story as F-048: they share the image rebuild). Mark the ~12 record-reading tests `@pytest.mark.needs_records`; the in-image run deselects the marker; closes on **`make image-smoke` GREEN 10/10 on a freshly built image**. (b) — a failure allow-list — refused for the reason M1 refused skip flags; (c) — records into the image — refused with F-048's (b), same reason. |
| **F-046** (at MONTHLY grain the input-drift signal is flat through a catastrophe — 2020-03 max input PSI 0.0217 vs an ordinary July's 0.0323; the signal was never absent, it was averaged; routed to this boundary with three costed readings) | **DECIDED this triage (ARCH): option (a) — accept the monthly window for SLO-D1/A-8 and rely on A-9, with the reliance made sound and the limitation made explicit.** What makes (a) honest NOW and not before: **F-051's fix lands first** (M8-S1 leg 1), so the volume signal being relied on is monotonic in the thing it watches; and the one sentence (a) requires — *a regime change confined to part of a month is invisible to SLO-D1 at monthly grain regardless of columns; 2020-03 measured PSI 0.0217 while its last ten days ran a different city* — **lands in `docs/slo_serving.md` §8.1 at M8-S1 leg 1** (the doc states PSI's volume blindness but not the window's; F-046's own honesty condition). The real residual cost is recorded, not netted out: a shape change with NO volume change (a vendor re-routing, a fare-rule change) would be missed entirely. (b) — a daily/rolling drift job — is NOT scheduled: it needs its own 2019 DAILY headroom leg before any bar exists (law-4 family), a push cadence and a staleness story per window, and no M8 or M9 quoted scope covers it (gotcha #19 forbids the silent carry); it is named as the upgrade a future monitoring conversation buys, with the 22–31-March counterfactual deliberately left unrun per the row's own warning (running it and THEN choosing the window is what the row exists to prevent). (c) adds board panels without a page and is superseded by the daily grain the M7-S5 board already renders on the OUTPUT side. **Closes on M8-S1's doc sentence.** |
| **F-045** (a drift metric over a whole month may not fire on the most drifted month this program will ever hold; routed to M7-S3, with the output-side dated note) | **CLOSED this triage (ARCH), by evidence that already exists — its option (a) is what M7-S3 shipped.** Volume became a first-class drift signal (SLO-D2/A-9), argued in `docs/slo_serving.md` §8.1/§8.4 BEFORE the run and FIRED on 2020-03 with the prediction written first (`drift_fire_drill.json`); the daily series is published (`marts.scoring_daily`, 91 rows) and the M7-S5 board renders ≥3 daily-grain cards; the memo states the mechanism in the form that generalises (*a row-weighted average of a collapse is weighted by exactly the rows that disappeared*). The residual within-month blindness is F-046's row, dispositioned above; the blind spot inside A-9 itself is F-051's, dispositioned above. Ledger row updated with this evidence. |
| **F-016** (incumbent gate margin; the alias moved on +0.63% at M3-S5 and held on −0.03% at M7-S4 — both sides of the no-margin condition now observed) | **Standing at AWAITING_PO 2026-08-18-1, unchanged — and DORMANT in M8 by construction**: law 3 means no M8 story invokes the gate, so nothing rides on the answer this milestone. Restated so it is visibly not lost. If the PO answers mid-milestone, the answer applies from the next gate invocation (a future retrain), nothing re-judged. |
| `docs/error_memo_m2.md` §7 row 2 (airport gap held 1.86–2.00× ordinary / 2.07–2.35× through the collapse; the drift memo's third measurement RULED OUT the distance-proxy hypothesis and recommends an airport flag evaluated as a REGIME indicator) | **Stays open in the memo — M8-S2's catalog is the named next reader**: the Feast catalog records `airport_regime_flag` as a CANDIDATE definition with the three measurements cited (catalog-only; **nothing is fitted** — law 3; a model that eats it is a future gate story). Closure remains analytical, not scheduled. |
| **F-040's named-but-unproven rollback reorder** · **F-001** · AWAITING_PO **2026-08-17-1** (host libgomp1) · **2026-08-16-2** (allowlist) | **Standing, all non-blocking, unchanged.** F-040's remedy still lands at the next PO-sanctioned rollback drill (M8 moves no alias, so no rehearsal opportunity arises — law 3); the runbook's do-not-substitute label and `verify-m5`'s heading check remain the guard. |
| **Debt** | **NONE DUE — the register is fully closed** (D-001→M4-S3 · D-002→M1-S4 · D-003→M4-S5 · D-004→M4-S3), diffed against `ledgers/debt.md` this session. D-001's registry-pattern deferral stands (trigger: image churn; landing: next PO-sanctioned rebuild). **M8 does not trigger it**: no rebuild; S1 leg 2 rebuilds the task image once and S4 builds a transformer image once — two builds is not churn, and both are priced in the risk table (gotcha #66), not a rebuild. |

**Verdict: M7 CLEANLY CLOSED — tagged `m7-closed`.** §9/M7's accept-when green
against the quoted text: *"v1's M6 gate"* — `verify-m7` GREEN 62/62 with every
predecessor law inherited (seventh inheritance), re-run by the approver at
this boundary and by REV the day before · *"the predictions table for the
scored month exists and the DA memo cites it"* — `marts.scoring_daily` (91
rows, 15,413,352 rows reconciled three ways with the ingest report as
authority) and the memo cites it by name through 4 monitoring ids (gate §7,
derived not asserted) · *"the memo explains the drift in domain terms with
numbers"* — the March cut (68.231/28.448/3.321%), the night that ended, the
median trip 49.3% faster, KPI-16 climbing +0.0369 → +5.3197 and never turning
back, every number re-derived by REV to the row. *"Show: the two failure
signatures + the predictions table + the memo"* — the gate's own closing
block prints exactly those three pointers. ◆ REV delivered: APPROVE WITH
CONDITIONS, both conditions dispositioned above with quoted landings. Gate
re-run green at the boundary by the approver, red team real (F-045 itself
planted, three artifacts went red), sign-off row added (producer EXEC S1–S5
PRs #40–#49, approver ARCH/Fable — producer ≠ approver holds), no open item
carried silently, README Status row flipped in the same commit as this
kickoff.

## Preconditions (verified LIVE at draft time 2026-08-21 — pastes, not memory)

| Precondition | Check run | Observed |
|---|---|---|
| M7 gate green at the boundary | `make verify-m7` | GREEN, 62 sub-checks, 7 sections, closing line verbatim in §0 |
| Cluster up, all Ready | `kubectl get nodes` | 3/3 Ready v1.36.1, age 4d1h — `mlops-taxi-{control-plane,worker,worker2}` |
| Champion serving, coherent | verify-m7 §7 (re-run this session) | endpoint answers `10.665224` min stamped `model_version='2'` == alias; parity row reproduced at 0.000e+00; served `feature_set` tag v2 == config's `features.version` v2 |
| Port family healthy | `make ports` | `OK — 10 required port(s): 4 free, 6 held by us, 0 foreign` |
| Headroom for a feature server / online store | `free -h` · `df -h /home` | 37Gi available of 47Gi · 938G disk free |
| No deliberate park, no crash | `ls automation/STOP` · `git status` | STOP absent · tree clean at `5ec090c` |
| **Feast's dependency wall, measured** | `curl pypi.org/pypi/feast/json` | **feast 0.66.0 · `pandas<3,>=1.4.3`** (vs our 3.0.5 — the ONE hard conflict) · `numpy<3,>=2.0.0` ✓ · `pyarrow>=16.1.0` ✓ · `requires_python >=3.10` ✓. Law 4 is written from this line |
| A pre-M8 backup exists | `ledgers/deployments.md` M7-S3 row | `2026-08-20T04-07-22Z` (6 databases, 1.6 GiB, every dump verified; restore scratch-rehearsed at M6-S5) — **S1 re-runs `make backup` before the pushgateway gains its PV** (law 1) |
| The pushgateway state (F-050's third data point) | verify-m7 §5 (this session) | empty, restarted-branch accounted (`startedAt 2026-08-21T03:55:49Z` after `pushed_at 2026-08-20T04:38:35Z`) — S1's PV lands against a live, measured recurrence |

## Debt intake (diffed against ledgers/debt.md this session)

| Debt id | Origin | What lands here | Absorbed into story |
|---|---|---|---|
| — | — | **No open debt rows exist** (all four closed with evidence; nothing re-carries). Obligation intake replaces debt intake: **F-051 → S1 leg 1 · F-052 → S1 leg 1 · F-050 (a)+(b) → S1 leg 1 · F-046's doc sentence → S1 leg 1 · F-048 (c)+(a) → S1 leg 2 · F-047 (a) → S1 leg 2 · error-memo §7 row 2 → S2's catalog as reader** (each quoted in §0). | S1, S2 |

## Stories (5; each independently finishable, safe stopping point after each)

### M8-S1 — M7 remediation: a drift surface a reviewer can trust, and an image that proves itself again  (role: SRE A for leg 1; MLOps A for leg 2; legs allowed)

**Leg 1 — the drift surface (F-051 · F-052 · F-050 · F-046's sentence).**
Order matters and is stated: **F-051 first** — change `drift._days` to divide
by the **calendar days the window covers** (`calendar.monthrange` for a whole
month — the same authority `verify-m7` §3 already trusts), add the property
test no current test asserts (*a strictly worse collapse must produce a
strictly lower ratio* — zero out progressively more days of a fixture month
and assert the ratio falls monotonically), and re-run REV's counterfactual
(`scripts/rev_rederive_m7.py 3`'s shape) showing the zeroed-days series now
monotonic and never re-crossing the bar. The bar stays **0.50** — this is the
implementation catching up to the calendar language the doc and the
annotation already state, not a threshold change. The three recorded ratios
must be shown UNCHANGED (all three months have all their days). Then
**F-052**: delete `configs/drift.yaml`, correct `docs/m7_flow.html` (stamp
line AND Sources-of-truth) to name `drift.py` + `alerting_rules.yml` +
`slo_serving.md` §8, widen the F-013 knob-tuple test with `reference_month` /
`drift_share_threshold`. Then **F-050 (a)+(b)**: `make backup` FIRST (the
gateway becomes a stateful tenant), the chart's persistence flipped on
(`--persistence.file` + a PVC — read the subchart's values live, the
fullname-prefix lesson from M7-S3 says guess nothing), and the absence rule
as a NEW A-id through `render_alert_rules.py` with its `why` (the honest
sentence: after (a), an absence means a real deletion, and that is worth a
page). **Prove the pair, prediction first**: push the real 2020 numbers
(`make drift DRIFT_ARGS="--push"` — undoing the F-050 empty state, its
recorded one-command fix), `kubectl delete pod` on the gateway, series
SURVIVE (the PV working — the drill a host reboot can't be scheduled for);
then wipe the store deliberately, absence rule FIRES, re-push, it clears —
the board ends carrying the truth (M7-S3's rule). Finally **F-046's
sentence** in `docs/slo_serving.md` §8.1 (quoted in §0). No threshold moves
anywhere in this leg; `make verify-m7` must be GREEN at leg exit (its §5
now passing through the *present* branch).
**Leg 2 — the image and the retrain's provenance (F-048 · F-047).**
**F-048 (c)+(a)**: (c) — `resolve_champion_configuration` refuses with its
own sentence when the records directory is invisible, plus the test that the
two absences produce DIFFERENT outcomes; (a) — the refit path writes the
fitted-rows provenance ON the version at fit time, and version 2 is
backfilled through an additive provenance-tag path **inside `registry.py`**
(never deletes, moves no alias — AST-pinned like the module's other laws);
the resolver prefers the version tag and falls back to the host chain, so
the pod path needs no host JSON. **F-047 (a)**: `@pytest.mark.needs_records`
on the ~12 record-reading tests, deselected in-image. ONE image rebuild
carries both (gotcha #66 priced: the next on-cluster run is a cold cache),
the schedule redeployed once, then the closure evidence: `make image-smoke`
**GREEN 10/10**, and one observed `retrain-schedule-proof` firing whose
record shows **`rescale_factor` 6.6667 and `round_cap` 2400** (F-048's own
closing condition — the pod finally resolving the same transfer the host
does). `@champion` 2 throughout; the proof trigger plans only.
Accept when: monotonicity property test in the suite and the counterfactual
re-run monotonic · recorded ratios unchanged · `configs/drift.yaml` gone,
flow diagram corrected, knob tuple widened · backup manifest dated this
session · series survive a pod delete · absence rule fired-and-cleared with
the prediction written first · the §8.1 sentence landed (closes F-046) ·
F-048's on-cluster record shows 6.6667/2400 · the two-absences test exists ·
`make image-smoke` GREEN 10/10 · `make verify-m7` GREEN at story exit.
Evidence plan: the property-test diff + counterfactual transcript · the
gateway survival + absence-fire transcripts · the rules diff + `make
alert-rules` output · the fired proof-run record · the image-smoke transcript
· ledger rows updated (F-045..F-052 closures with evidence).
Safe stopping point: leg 1 merged alone — the drift surface is whole and
verify-m7 green; say so and hand leg 2 the image work.

### M8-S2 — Feast, quarantined: the probe, the feature repo, and the catalog with its verdicts  (role: DE A; MLE R)

The wall is known before the story starts (law 4): **Feast 0.66.0 pins
`pandas<3`**. So the probe is not "does it install" but "what exactly does
the quarantine hold": a fresh isolated venv (gotcha #16 — the M7-S3 Evidently
idiom), `feast` pinned by exact version, the full transitive set recorded,
and the project's own `uv.lock` **byte-identical** (assert it — the probe's
strongest exit invariant, and this milestone's twin of "the 2019 bytes did
not move"). 3-attempt wall on the quarantine bootstrap; if Feast cannot be
made to work in isolation at any pin, that is a ROUTE (AWAITING_PO — the
milestone's premise is at stake), never a resolver fight.
Then the **feature repo, in git**: entities (zone, OD pair, date), feature
views over the EXISTING artifacts read-only — the zone centroid table
(`data/reference/taxi_zone_centroids.csv`, 263 rows), the holiday table
(2019..2030), and the **zone-window aggregates as the time-varying catalog
entries** (BLUEPRINT §9/M3: "aggregates that survive ablation are the named
candidates for Feast definitions at M8 — M3's craft becomes M8's catalog").
**The catalog must carry its verdicts, and the honest one is uncomfortable:
g5 — the point-in-time aggregates, the community's favourite family — LOST
the M3 ablation** (−1.63%, `docs/ablation_m3.md`). So every catalog entry
states its provenance and its ablation verdict: the centroid and calendar
features are IN the champion (v2); the window aggregates are **catalog-only,
with the measured reason**; and `airport_regime_flag` is recorded as a
CANDIDATE with the three measurements that motivate it (error-memo §7 row 2's
named reader — §0). Nothing is fitted (law 3). Event timestamps follow the
prior-art ADOPT: **end-of-window stamps** (a feature computed over an hour is
knowable only when the hour ends — the leakage argument M3-S3 paid for,
encoded in the timestamp convention).
Accept when: the quarantine venv builds reproducibly from a committed
requirements pin with the probe record (packages, versions) tracked ·
`uv.lock` byte-identical · `feast apply` + `feast plan` clean in quarantine
against a repo whose definitions live in git · the catalog page committed
with per-entry provenance and verdicts (in-champion / catalog-only-with-
reason / candidate) · every settled-data pin `up to date`.
Evidence plan: the probe record · the feast apply/plan transcripts · the
catalog page · `dvc status` + `git diff --stat uv.lock` (empty) pastes.
Safe stopping point: probe + repo landed, catalog page thin — S3 needs the
definitions, not the prose; say so.

### M8-S3 — Point-in-time correctness, measured: historical retrieval against the ONE feature path  (role: DE A; MLE R)

Two measurements, both read-only over settled data, no model touched.
**(1) The retrieval parity**: `get_historical_features` for a DECLARED,
committed row set (the M5-S3 idiom — the 16 parity hazards plus a stratified
sample; each row naming why it is there) must reproduce the features the ONE
`taxi_mlops.features` path builds for the same rows. The comparison crosses
the quarantine boundary through parquet (Feast's pandas-2 world writes, our
pandas-3 world reads — the mlserver precedent: the seam is real, so measure
it). **The tolerance is argued BEFORE the first comparison runs** (law-4
family): from the dtype path, not from the delta just measured — exact for
integers and categoricals, and a stated float bar for the centroid-derived
columns with the reason. A mismatch is a finding to investigate (which side
rounded?), never a bar to widen.
**(2) The point-in-time proof** — the blueprint's "point-in-time training
joins" leg, and it is M3-S3's leakage red-team run through M8's machinery: a
zone-window aggregate joined NAIVELY (the full-window mean, future included)
versus Feast's point-in-time join at each row's event timestamp, on a month
boundary where they MUST differ. The assertion is two-sided: the two joins
DIFFER where the naive one would leak (the difference is the leakage, made
visible), and the point-in-time join's values match our own
`aggregates.fit(point_in_time=True)` output for the same keys (two
implementations, one number — the strongest shape this program trusts).
End-of-window timestamps (S2's convention) are what make the join honest;
say so where the numbers land.
Accept when: the declared row set committed with per-row reasons · the
tolerance argued in the doc BEFORE the comparison transcript's timestamp ·
retrieval parity measured and within the pre-argued bar (or the mismatch
investigated as a finding) · the naive-vs-point-in-time difference shown
nonzero where leakage lives and the PIT join reconciling with our own
point-in-time implementation · nothing fitted, no pin moved.
Evidence plan: the row-set file · the tolerance argument (dated) · both
comparison transcripts · the reconciliation numbers.
Safe stopping point: retrieval parity done, PIT proof pending — say so; S4
needs (1), not (2).

### M8-S4 — The online store, the 100-pair parity, and the transformer beside the champion  (role: MLE A; SRE R)

**The online store, decided at execution and recorded**: the constraint that
decides it is two-sided reachability — the (host, quarantined) materializer
must WRITE it and the in-cluster request path must READ it. An in-cluster
Redis (helm, pinned tag+digest, **no hostPort**, port-forward for host
writes) satisfies both; Feast's default sqlite satisfies neither side across
the boundary. 3-attempt wall; the decision note states the store's state
class honestly — **materialized features are REGENERABLE** (re-materialize
from the offline store), so it is a `data/predictions/`-class tenant: ledger
row yes, backup obligation no (say so in the row). Materialize the servable
feature views; then the **100-pair online/offline parity table** — the
blueprint's named accept artifact: 100 DECLARED pairs (entity, timestamp)
spanning the hazard classes, `get_online_features` vs the offline retrieval,
tolerance pre-argued (S3's bar inherits). **The parity table is the Show
artifact — commit it.**
**The transformer, beside the champion (law 3)**: a KServe transformer on a
SECOND InferenceService (own host — the M6-S3 shadow precedent, which also
proved teardown removes exactly its own objects) carrying the SAME champion
bytes (version 2 resolved by F-009's two hops). It accepts a RAW quote
request (`at`, `pu`, `do`, `passenger_count`) and builds the 24 features
through the ONE `taxi_mlops.features` path — the boundary law holds; Feast
supplies the STORED lookups. **The pandas wall crosses the wire here too**:
the transformer runs OUR image (pandas 3) and must not import the Feast SDK
— candidate shapes, in order: (i) Feast's feature server as its own
quarantined pod, HTTP from the transformer; (ii) a thin direct read of the
online store (no feast import), a recorded DIFFER naming the serialization
risk; (iii) if the wall wins after 3 attempts: the transformer builds from
the image's committed lookups with Feast OFF the request path — a recorded
DIFFER from "transformer enrichment via Feast", legal because the
blueprint's accept is the parity table + the page, not the wire shape.
**Whichever shape lands: THE parity through the new seam** — the 16 hazards
as raw requests through the transformer isvc versus the same rows host-built
through the champion's isvc, bar argued before (M5-S3's 1e-6 precedent; a
wider bar needs a dtype argument, not a shrug) — and **p95 on the
transformer path measured at M5-S4's shape** (4 req/s / 60 s / concurrency
8, open loop), labeled as the NEW boundary's number beside the old one
(M5-S4 priced the moved boundary at ~30 ms cold; a surprise is a finding).
The champion's own wire is untouched throughout — `make verify-m5` green at
story exit is the proof.
Accept when: store decision recorded with the state-class note · 100-pair
parity table committed and within the pre-argued bar · transformer isvc
answers a RAW request with the champion's number (hazard parity within its
pre-argued bar) while 404-or-untouched on the champion's own host ·
`@champion` 2 before and after · `make verify-m5` AND `make verify-m7` green
at exit · teardown proven (the shadow precedent) or the isvc deliberately
left up with the reason stated.
Evidence plan: the decision note · the parity table + transcript · the
hazard-parity and p95 records (tracked) · the verify pastes.
Safe stopping point: store + 100-pair parity landed, transformer undone —
the blueprint's accept artifact already exists; say so and hand the
transformer to a second leg.

### M8-S5 — The side-by-side page, the M8 gate, and its red team  (role: DA A for the page; MLOps A for the gate; legs allowed)

**Leg 1 — the comparison page** (BLUEPRINT §6: "M8 revisits the survey for
the feature-store comparison specifically — side by side, as asked").
`docs/feast_side_by_side.md`: our Feast design against the surveyed
community implementations (harvest live via `curl` + `gh api` — F-001
stands, WebFetch is off the allowlist; the M1-S3/M3-S2 idiom), one verdict
per practice — adopt / differ / surpass — honest in both directions. Named
rows the survey must face: the **quarantine itself** (nobody in the surveyed
community runs Feast beside pandas 3 — our wall, their non-problem; a DIFFER
with the measurement), end-of-window timestamps (the ADOPT, landed at S2),
the catalog-with-verdicts (a SURPASS candidate: community catalogs list
features, ours records which ones LOST and why), and the PIT proof (S3's
two-sided assertion against their typical assert-free joins). Every claim
about a community repo cites what was actually read (gotcha #15's spirit:
a claim's provenance travels with it).
**Leg 2 — `make verify-m8` + `make verify-m8-redteam`**, under every
inherited law (eighth inheritance): re-runs nothing expensive and mints
nothing it counts (no materialization, no image build, no transformer
deploy) · every literal derived on both sides (F-017; the parity bars parsed
from the docs that argue them, never re-typed) · asks the live system a
BOUNDED set of questions (one prediction through the champion's wire, one
through the transformer's if it stands, one Prometheus query — the
verify-m6/m7 shape) · prose vs records at ≥1 decimal (gotcha #90) · the
quarantine's invariant asserted (`uv.lock` unchanged against the m7-closed
tag; feast absent from the project graph) · the settled pins asserted ·
`@champion` 2 and the alias law in its strong form (no M8 run is a registry
version). The red team plants ONE derived-plausible value in a tracked M8
record (the 100-pair table is the natural target — a pair's online value
rewritten inside the bar's neighbourhood), RED from ≥2 artifacts, 
sha256-verified restore, GREEN after.
Accept when: the page committed with per-row provenance · verify-m8 GREEN
with section/sub-check count stated · red team RED for the planted cause
with untampered sub-checks passing, GREEN after · §9/M8's accept-when quoted
and answered line by line ("v1's M7 gate AND the comparison page exists.
Show: parity table + comparison") · deployments/signoff ledgers current.
Evidence plan: the page · both gate transcripts · the ledger rows.
Safe stopping point: leg 1 merged with the gate unbuilt — the
M4-S5/M6-S5/M7-S5 precedent; say so.
Exit: `automation/next_session.sh architect 120` — M8 carries no ◆; the
boundary triage is next.

## Out of scope (named now so creep is visible later)

- **Any alias move, any model fit, any gate invocation** (law 3). The
  champion serves unchanged; `retrain-monthly` stays registered-inactive
  (the PO's compute call, unchanged from M7-S4).
- **Adding any catalog feature to the CHAMPION** — the catalog records
  candidates; a model that eats one is a future milestone's gate story.
- **A daily/rolling drift window** — decided against at this triage (F-046
  option (a), §0); the upgrade is named for a future monitoring
  conversation with its own headroom leg, not scheduled.
- **Cutting the production wire over to the transformer** — it lands beside
  the champion; cutover is a boundary/PO decision with the parity and p95
  records in hand.
- **Ray, CI smoke, trivy, demo page (M9** — demo still "never on the
  acceptance path"**)**.
- **Registry pattern, Flyte's declared 8080 route, monitoring hostPorts
  (3000/9091), a Feast/online-store hostPort** — the next PO-sanctioned
  rebuild, unchanged (D-001's note).
- **Editing any 2019/2020 artifact, threshold, or gate condition** — laws
  2 and 4, and F-016's park respectively. F-051's arithmetic fix is a
  defect repair matching documented intent, chartered in §0, and is the
  ONE monitoring-code change M8 makes to a shipped rule.

## Risks & walls (carried counts restated; fallbacks cite ADRs/precedents)

| Risk / wall | Count | Fallback |
|---|---|---|
| **Feast's pandas<3 pin** — MEASURED at draft (law 4), not discovered at `uv add` | quarantine is the design; 3-attempt wall on the bootstrap itself | An older/newer Feast pin inside the quarantine; if NO pin yields a working isolated Feast, ROUTE to the PO (the milestone's premise is at stake) — never a resolver fight, never a core-pin move (gotcha #36). The PIT-join *proof* half of S3 can still land through our own `aggregates.fit(point_in_time=True)` while the route waits |
| **The transformer × Feast SDK conflict** — the transformer runs pandas 3 and may not import feast | named in S4 with three shapes in order | (i) feature-server pod over HTTP → (ii) thin direct store read, recorded DIFFER → (iii) Feast off the request path, committed lookups in-image, recorded DIFFER; the blueprint's accept (parity table + page) survives all three |
| **Online store two-sided reachability** (host materializer writes, cluster reads) | 3-attempt wall in S4 | Redis in-cluster (pinned, no hostPort) is the shape that satisfies both; the decision is recorded with the store's regenerable state class |
| **Retrieval parity crosses the pandas-2/parquet/pandas-3 seam** — dtype drift is the expected failure, not logic | bars pre-argued in S3/S4 (law-4 family) | A mismatch is investigated as a finding (which side rounded, which dtype narrowed), never a widened bar; the mlserver precedent says the seam can measure 0.000e+00 when nothing on the numeric path differs |
| **gotcha #66: S1 leg 2's image rebuild colds every cached stage; S4's transformer image is a second build** | priced in S1/S4 | Detached runs for anything long (ritual e, `run_detached.sh`); the schedule-proof observation in S1 leg 2 is minutes, not a fit |
| **The pushgateway persistence upgrade rolls the gateway** — one more series wipe at the moment of fixing the wipes | named in S1 | Push AFTER the roll (the gate prints the command); the drill order in S1 makes the post-roll push the drill's own first step |
| **F-048's ordering** — (c) landed alone turns the deployed proof-trigger red | ordering stated in S1 leg 2 | (a)+backfill and (c) ship in ONE image + one redeploy; the observed firing afterward is the closure evidence |
| **WSL memory with a feature server + store** | 37Gi available observed | Both tenants are small; if scheduling pressure appears, `kubectl describe node` BEFORE touching any limit (the M7 precedent) |

## Open PO questions (options · recommendation · default-with-date)

**None new.** Standing, restated: **2026-08-18-1 (F-016, incumbent margin)** —
dormant in M8 by construction (law 3: no gate invocation); the answer applies
from the next retrain gate whenever it lands. · **2026-08-17-1** (host
`libgomp1` one-liner) · **2026-08-16-2** (allowlist paste). The chain
continues; nothing parks.

## ARCH self-check (v3.0)

model stated Fable: **yes, first line** · every story sized for one short
executor session: **yes — S1 and S5 name their legs (the M6-S5/M7-S5
precedent); S4 names its safe split (store+parity vs transformer) and its
detached-run exits (ritual e)** · debt intake diffed against ledgers/debt.md:
**yes — register fully closed, stated in the table; obligation intake
(F-051/F-052/F-050/F-046→S1L1, F-048/F-047→S1L2, memo-row→S2) replaces it** ·
forks routed to AWAITING_PO: **none new; F-016 stands parked and dormant;
one potential fork is pre-routed as a risk (Feast unusable at any pin →
ROUTE, the milestone's premise), named as a route-not-edit** · every carried
finding restated with quoted landing: **all seven M7-open items dispositioned
in §0 with landings quoted into S1/S2; nothing carries past M8 from this
triage except the two standing PO items and the memo's analytical row, each
restated** · gates loosened: **none — verify-m8 inherits every predecessor
law (eighth inheritance); F-051's fix changes arithmetic to match documented
intent with the bar unchanged; F-050 adds a rule and a volume, loosening
nothing; law 4 legislates how every M8 parity bar must be argued before it
is measured**.
