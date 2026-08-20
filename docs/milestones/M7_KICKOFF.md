# M7 KICKOFF — Drift, batch inference, & the retrain loop   (authored by: ARCH/Fable · 2026-08-20 · v3.0: the Architect is sole author)

Session model stated: **Fable 5 (claude-fable-5)** — architect sessions on any
other model are void (ORG.md rule 7).

**M7 carries a ◆** (BLUEPRINT §9: "◆ REV monitoring review (fresh session)").
The last story exits to REV, not to the boundary:
`automation/next_session.sh rev 120` → REV reviews the finished milestone in a
fresh session → REV exits `automation/next_session.sh architect 120`.

**The four laws this milestone lives under, stated once at the top.**
(1) **THE CLUSTER IS STATEFUL AND NO M7 STORY MAY TAKE IT DOWN** — unchanged
since M2. Pushgateway gets **NO hostPort** (9091 stays a reserved NAME in the
port family, exactly as 3000 did through M6): Prometheus scrapes it in-cluster
by Service, and a human reaches it by port-forward or a host-route on the
EXISTING 8081 ingress. A story that finds itself wanting a hostPort has found
a wall.
(2) **THE 2019 TRAINING DATA IS SETTLED AND STAYS BYTE-IDENTICAL.** New months
(2020-01..03, and whatever S1 does with 2025) arrive as NEW artifacts — a
scoring tree beside `data/processed/`, never inside the train/val/test months.
`dvc status` on the 2019 pins and the analyst-layer reconciliations are the
story-exit invariant for anything that touches ingest. A changed 2019 byte is
a defect, not a refresh.
(3) **THE ALIAS MAY MOVE IN M7 — ONLY through the gate, as PRE-REGISTERED.**
This is the first milestone since M3 where `@champion` may legitimately move,
and only one path may move it: a full-data challenger through the ONE
evaluator and `gate.decide`/`registry.promote` (F-008: a sampled run gets NO
verdict; F-011: the incumbent is consulted). **F-016 is still the PO's**
(AWAITING_PO 2026-08-18-1, unanswered): per the M6 kickoff's standing rule,
*"M7 proceeds with the gate as pre-registered (option A is the standing status
quo, not an auto-adopted recommendation)"*. A REFUSE is a working loop, not a
failed story. No story hand-moves the alias (M6-S4's typed rehearsal is done
and stays done).
(4) **NO THRESHOLD IS SET EQUAL TO THE NUMBER JUST MEASURED** (gotchas
#63/#74/#87 in bar-form, now with F-041's corollary): every drift threshold is
argued from harm + headroom BEFORE the drift job runs against real 2020-03
data, the prediction is written first, and a threshold that does not fire on
COVID-March is a wrong prediction to investigate — never a knob to re-tune
until the alert agrees.

## 0. Boundary triage of M6 (the closure sweep, folded in)

**Verify re-run (by the approver, this session, 2026-08-20):** `make verify-m6`
→ **GREEN — 63 `ok` sub-checks across 7 sections, exit 0** (counted live:
`grep -cE "^  .?.?.?.?.?ok"` → 63). Closing line verbatim:
`[verify-m6] GREEN — every M6 sub-check passed.` Highlights, pasted not
remembered: §6 `the kill's 13.75 s outage reconciles with its own anchors:
strictly longer than the 13.501 s error SPAN and inside one arrival gap of it`
· §7 `the label moved one notch in all 3 artifacts that carry it — including
the 1 line(s) the backup PRINTS at runtime` (F-044's check, live) · §7
`@champion is version 2, whose run is still the winner the M3 bake-off
recorded — M6's two sanctioned alias moves round-tripped` · §7 `the endpoint
answered 10.665224 minutes stamped model_version='2' … reproducing the parity
record's row for 'ordinary-midday' to 0.000e+00 minutes. M6 ended where M5
did`. The red team was run and PASSED by the executor at M6-S5 leg 2 (planted
`13.75 → 13.501`, gotcha #75's wrong anchor — RED exit 1 with 2 FAILs from two
different artifacts, 61 sub-check lines still passing, sha256-verified
byte-identical restore, GREEN 63/63); the gate re-run here mutates nothing,
per its own law.

**Lineage spot-check (gotcha #20):** `git merge-base --is-ancestor 9a514a5
origin/main` (M6-S5 leg 2's merge, PR #39) → ancestor confirmed. M6 is story
PRs **#33, #35–#39** (S1–S5, S5 in two legs; #34 is the PO's front-door
refresh, not a story). Tree clean at `b76d832`.

**REV:** none owed at M6 (BLUEPRINT §9: M6 carries no ◆; the next ◆ is THIS
milestone — see the exit ritual at the top).

**Every open finding, condition, and due debt from M6, dispositioned:**

| Item | Disposition |
|---|---|
| **F-043** (the predictor's own exporter starves under saturation; A-1 cleared itself mid-event; routed to this boundary) | **Direction DECIDED this triage (ARCH): option (c)** — accept, and state the limit where the thresholds live: `docs/slo_serving.md` gains the sentence that every in-pod signal is unreliable above ~90% CPU (with the measured evidence: scrape 4 ms → 4.613 s, one scrape failed, while the idle shadow held 0.004 s), A-1's `why` annotation carries the caveat, and the node-side (A-6, cAdvisor) and edge-side (A-2, ingress) signals are named as the instruments that hold under saturation. NOT a PO fork: no target loosens, no threshold moves — an instrument limitation is documented, not a bar changed. Option (a) (raise the CPU limit) stays available at a future capacity conversation argued from real traffic, exactly as the ledger row recommends. **Intaken → M7-S3** (the story that touches the monitoring surface); closes on the doc sentence + the annotation, checked by the S3 evidence. |
| **F-042's routed recommendation** (shorten A-7's `for:` to ~1m so it fires before A-5, restoring the annotation's original causal order) | **DECLINED this triage (ARCH), with the counter-argument as the reason**: the corrected annotation already states the MEASURED order and the pair's real value — a distinguishable SIGNATURE (A-5 alone vs A-5-then-A-7) that holds whichever arrives first — and shortening a sustain on the authority of the one drill just measured is gotcha #63 in bar-form (the same edit-class F-016 parks with the PO). The threshold stands. Dated note appended to the ledger row; the finding stays CLOSED. |
| **F-020** (tuned config is 15%-sample-optimal applied unchanged at full scale; count-scaled knobs and the 800-round cap travel unrescaled) | **DUE HERE — intaken → M7-S4** (mandatory intake at the quoted landing: §9/M7 *"scheduled Flyte retrain landing a challenger"* re-runs the same refit path). S4 closes it by the row's own conditions — option (a) folded into the retrain itself: the challenger IS the v2 winner's configuration with the count-scaled knobs rescaled to the refit's row count and the round budget re-derived, reported through `taxi_mlops.training.evaluate` beside the 3.2403 that stands — or option (b), the recorded scale-transfer rule, if (a)'s measurement is cut for budget. Either way the decision is recorded WITH the change. |
| **F-022** (bake-off un-runnable since its own promotion; direction (a) decided at the M4 boundary: incumbent cell reads the loaded model) | **DUE HERE — intaken → M7-S4** (same quoted landing). Closes by the decided change + one `--smoke-rows` execution past contender resolution (the defect is in resolution, not scale). |
| **F-016** (incumbent gate margin; the alias moved on +0.63%) | **Standing at AWAITING_PO 2026-08-18-1 — now ACTIVE for M7.** Per the M6 kickoff's own legislation: unanswered at this boundary, so **M7 proceeds with the gate as pre-registered** (law 3 above). If the PO answers mid-milestone, the answer applies from the next gate invocation; nothing is re-judged retroactively. Restated so it is visibly not lost. |
| **F-035** (A-3's client half and A-4 have no metric source — the fact lives in a client, and no client is scraped; both name M7's pushgateway as the landing) | **CLOSED at M6-S2 by disposition; the named landing is DUE HERE — intaken → M7-S3.** Pushgateway is the component this milestone installs anyway; S3 lands the client-side counters (the 422-refusal count, and A-4's served-vs-registry gauge) or re-dispositions honestly — `render_alert_rules.py` already fails if the implemented set and the documented absences disagree, so a quiet half-landing is impossible by construction. |
| **The v1 shadow** (M6-S3's isvc, deliberately left running through M6-S5 as F-043's accidental idle control; teardown "whenever the boundary decides") | **DECIDED this triage: torn down at M7-S1 entry** (`make shadow TEARDOWN=1`, proven at M6-S3 to remove exactly its own three objects). Its evidentiary work is done (the F-043 comparison is committed in `automation/runs/m6-gameday/saturation.json` and `docs/gameday_m6.md` §4.2); keeping a second predictor as a permanent fixture would turn an M6-S3 leftover into unplanned wire state. Deployments-ledger row; `make verify-m5`/`verify-m6` green after. |
| **F-040's named-but-UNPROVEN remedy** (reorder the rollback's moves to alias → `make serve` → config line, predicted to collapse the 27.93 s window to ~0.5 s; routed to M6-S5 as a gameday candidate and NOT run there — the gameday's four scenarios were control/kill/storage/saturation) | **Stays named-and-unproven, DELIBERATELY not intaken into M7**: rehearsing it costs two hand-moved alias round-trips, and M7's law 3 reserves alias moves for the gate. The guard already exists where it matters — runbook §4 labels the remedy *not rehearsed, do not silently substitute during an incident* — and `verify-m5` reads the §4 heading, so the label cannot silently rot. It lands at the next PO-sanctioned rollback drill (a future gameday), stated here so the non-carry is a decision, not an omission. |
| `docs/error_memo_m2.md` §7 row 2 (airport gap held at 1.91× though v2 carries OD geometry; two independent measurements now point the same way) | **Stays open in the memo, no ledger row — M7-S5's drift memo is the named next reader**: 2020-03 collapses airport traffic, so the drift data may speak to the row from a third angle; the memo cites it if it does. Closure is analytical, not scheduled. |
| **F-001** · AWAITING_PO **2026-08-17-1** (host libgomp1) · **2026-08-16-2** (allowlist) | **Standing with the PO, all non-blocking.** Unchanged. |
| **Debt** | **NONE DUE — the register is fully closed** (D-001→M4-S3 · D-002→M1-S4 · D-003→M4-S5 · D-004→M4-S3), diffed against `ledgers/debt.md` this session. D-001's registry-pattern deferral stands with its trigger (image churn) and landing (next PO-sanctioned rebuild — the same event that owes Flyte's declared 8080 route and the monitoring UIs their hostPorts). **M7 does not trigger it**: no rebuild; pushgateway is an upstream pull; the task image churns only if S2/S4 commit under the guarded paths, which is priced in the risk table (gotcha #66), not a rebuild. |

**Verdict: M6 CLEANLY CLOSED — tagged `m6-closed`.** §9/M6's accept-when green
against the quoted text: *"the shadow comparison table exists with a
quantified disagreement rate before the first traffic shift"* — 1,016 rows,
segment grain, DA memo verdict NO-GO for v1, and the ordering checked on the
two records' own clocks (14:49:23Z before 15:23:48Z) · *"v1's M5 gate (canary
90/10 observed, rollback <2min under load, alert fired in red-team)"* — 90/10
from TWO counters (ingress 9.76% vs the predictors' own 9.33%), traffic revert
0.37 s against the 120 s budget, the alias rollback 35.35 s/34.38 s both ways
under load, and A-3/A-2 fired end to end to Alertmanager with the prediction
written first · *"the gameday record shows predicted-vs-observed signatures
with at least one prediction wrong and investigated"* — TWO wrong (F-041's
transient ratio, the saturation 502s), neither engineered, both investigated
in named passages. *"Show: the shadow disagreement table + Grafana during
canary + gameday record"* — all three shown by the gate itself. Gate re-run
green at the boundary by the approver, red team real, sign-off row added
(producer EXEC S1–S5 PRs #33, #35–#39, approver ARCH/Fable — producer ≠
approver holds), no open item carried silently, README Status row flipped in
the same commit as this kickoff.

## Preconditions (verified LIVE at draft time 2026-08-20 — pastes, not memory)

| Precondition | Check run | Observed |
|---|---|---|
| M6 gate green at the boundary | `make verify-m6` | GREEN, 63 sub-checks, closing line verbatim in §0 |
| Cluster up, all Ready | `kubectl get nodes` | 3/3 Ready v1.36.1, age 3d — `mlops-taxi-{control-plane,worker,worker2}` |
| Champion serving, coherent | verify-m6 §7 (re-run this session) | endpoint answers `10.665224` min stamped `model_version='2'` == alias; parity row reproduced at 0.000e+00 |
| Port family healthy | `make ports` | `OK — 10 required port(s): 4 free, 6 held by us, 0 foreign` |
| Headroom for pushgateway + drift jobs | `free -h` · `df -h /home` | 37Gi available of 47Gi · 941G disk free |
| No deliberate park, no crash | `ls automation/STOP` · `git status` | STOP absent · tree clean at `b76d832` |
| **The 2020 raw data is reachable** | `curl -sI …/yellow_tripdata_2020-03.parquet` | **HTTP 200, 44,442,590 bytes** — against 2019-01's 110,439,634. The COVID collapse is visible in the file size before a row is read; S1 pins the sha when it downloads |
| **A 2025 file exists for the schema-drift leg** | `curl -sI …/yellow_tripdata_2025-01.parquet` | **HTTP 200, 59,158,238 bytes** — reachable; whether it REFUSES or VALIDATES against the year-aware contract is S1's measurement, not this table's assumption (see S1) |
| A pre-M7 backup exists | `ledgers/deployments.md` M6-S1 row | `2026-08-19T05-59-36Z` (6 databases + 331 objects, 1.6 GiB, every dump verified; restore scratch-rehearsed at M6-S5) — **S3 re-runs `make backup` before the pushgateway tenant lands** (the M4-S2/M5-S1/M6-S1 precedent) |
| The v1 shadow is still up (M6 leftover, teardown decided above) | verify-m6 boot state / HANDOFF (bj) | both isvcs Ready at the M6-S5 boot; S1 tears the shadow down first |

## Debt intake (diffed against ledgers/debt.md this session)

| Debt id | Origin | What lands here | Absorbed into story |
|---|---|---|---|
| — | — | **No open debt rows exist** (all four closed with evidence; nothing re-carries). Obligation intake replaces debt intake: **F-020 → S4 · F-022 → S4 · F-035's pushgateway counters → S3 · F-043 option (c) → S3 · the shadow teardown → S1 · error-memo §7 row 2 → S5's memo as reader** (each quoted in §0). | S1, S3, S4, S5 |

## Stories (5; each independently finishable, safe stopping point after each)

### M7-S1 — The scoring months: 2020 through the ONE contract, and the two refusal shapes  (role:DE A; MLE R)

**First move: tear down the v1 shadow** (`make shadow TEARDOWN=1` — the
boundary's decision, §0; deployments-ledger row; `make verify-m5` green
after). Then the data: extend `make ingest`/`configs/data.yaml` so months
outside the 2019 splits can be ingested as a **scoring tree** —
`data/scoring/<month>/` or equivalent, NEVER inside `data/processed/
{train,val,test}` (law 2) — through the SAME contract, the same one-cast rule
(gotcha #7), the same counted rejections, the same sidecar discipline
(M2-S1's: a refused month writes nothing; counted rows retain their rule).
Ingest **2020-01, 2020-02, 2020-03**: three months so the drift memo can show
the cliff, not just the crater (2020-01/02 are near-normal, 2020-03 is the
break). Raw files sha256-pinned into the manifest; **DVC pin LAST** (gotcha
#33); analyst-layer views extended (`trips_scoring` or equivalent) with the
reconciliation-or-exit-1 discipline the other views already live under. The
month/label comes from config, never parsed from a filename (M1-S2's law).
**Expect the COVID month to be strange and let the contract say so**: if
2020-03's rejection rate crosses `max_rejected_fraction` (0.10) the month
REFUSES — that is a measured result to record and route (a threshold loosening
is a PO fork), not an edit. **The schema-drift leg is a measurement, not an
assumption**: run the real 2025-01 file through the contract. The contract is
year-aware BY DESIGN (gotcha #6: `from_year` columns; a 2025-shaped frame
validates in unit tests), so it may well VALIDATE — if it does, record that as
a SURPASS over the blueprint's premise and demonstrate the refusal shape with
a structurally-wrong fixture instead (a renamed/dropped column →
`SchemaEventError` naming the month, exit 1, nothing written). Either way M7
ends with both shapes on the record: **a month that is structurally fine and
statistically alien (2020-03, counted in), versus a month the contract refuses
whole (SchemaEventError, nothing written)** — the two signatures S3 must keep
distinguishable.
Accept when: shadow torn down with ledger row and verify-m5 green · 2020-01..03
ingested into the scoring tree with per-rule rejection tables printed and the
sidecars reconciling per (month, rule) · **the 2019 trees byte-identical**
(`dvc status` on `data/processed.dvc` + `data/rejected.dvc`: up to date) · the
2025 contract behavior MEASURED and recorded (validate or refuse — whichever,
with the transcript) · the schema-refusal transcript exists (real file or
fixture, named which) · analyst views reconcile or exit 1, proven by the
red-team unit shapes the other views carry.
Evidence plan: the ingest transcripts (per-rule tables) · `dvc status` paste ·
the 2025 measurement transcript · the refusal transcript · the ledger row for
the teardown.
Safe stopping point: 2020 months landed, 2025 leg undone — say so; S3 needs
the 2020 data, not the 2025 answer.

### M7-S2 — Batch inference as a product: the predictions table  (role:MLE A; DA R)

The scheduled monthly workflow doesn't just score for drift — it WRITES a
predictions table the DA queries like any consumer (BLUEPRINT §9/M7, v2.2).
Score **2020-03** (and 2020-01/02 if cheap — the memo wants the series) with
the champion **resolved from the alias** (F-009's two hops, never `source`),
features through the ONE `features/` path, the model version stamped on every
row (M2-S4's discipline). Output: parquet under a predictions-for-scoring
tree (gitignored like `data/predictions/` — regenerable output; the
provenance is the manifest + the registry, M2-S4's argument) + a DuckDB view
+ a **published mart** so Metabase can reach it (Metabase queries Postgres
only — M1-S4's constraint). Row counts reconcile ingest → predictions → mart
or the build exits 1 (the three-reconciliation precedent). **Ground truth
exists for 2020-03 — label the error numbers honestly**: an MAE on a scoring
month is a MONITORING series, not a result (gotcha #15: KPI-09/10 belong to
the evaluator on the holdout; new-window numbers get NEW ids per the id law,
defined in `docs/kpi_definitions.md` before the board renders them). The
batch path should be a pipeline stage or workflow the schedule can call
(S4 wires the schedule; S2 makes the thing it calls exist and work once,
on-cluster or host-rehearsed — say which). Mind gotcha #66: a commit under
the guarded paths makes the next on-cluster run rebuild its cache; if the
score runs on-cluster, plan it detached or accept the cold cache in the
budget.
Accept when: the predictions table for 2020-03 exists (parquet + view + mart)
with the champion's version stamped and the alias read-not-written · counts
reconcile end to end · new KPI ids (if any error series is published) defined
with formula/window/owner before any board cites them · `@champion` version 2
before and after.
Evidence plan: the scoring manifest · the reconciliation transcript · the
mart row counts · the kpi_definitions diff.
Safe stopping point: parquet + view landed, mart unpublished — the DA can
already query DuckDB; say so.

### M7-S3 — Drift detection: Evidently → Pushgateway → alert, and the client-side counters  (role:SRE A; DA R)

`make backup` FIRST (the standing precedent — a new tenant lands beside state
with no other copy). Then **Pushgateway** in-cluster (chart or plain manifest,
version pinned live tag+digest where images allow — the Metabase precedent;
**no hostPort**, law 1; scraped by the existing Prometheus — a scrape config
change costs no restart, measured at M6-S1). Then **Evidently**: `uv add`
with the gotcha #36 check pasted (packages touched, cores unchanged) — and
**probe pandas-3 compatibility FIRST, before designing around the library**
(risk table; scipy-based PSI/KS through our own module is the recorded
fallback, a DIFFER from the blueprint's named tool, or gotcha #16's quarantine
if a pinned older Evidently is worth an isolated venv). The drift job:
reference = the 2019 TRAIN months' distributions (point-in-time honest — the
reference must be data the champion actually saw, gotcha #43's family),
current = one scoring month; metrics pushed with month labels; **the drift
threshold argued in the SLO-doc pattern BEFORE the job runs against 2020-03**
(law 4), the alert rule landed through `render_alert_rules.py` (a new A-id
with its `why`, or a drift-doc twin — one home for thresholds, F-013's law).
**Prediction first, then fire it with real data**: 2020-03 should genuinely
drift; if it does not fire, that is a wrong prediction to investigate on the
record (F-041's precedent), never a threshold to walk until the alert agrees.
Then show the two signatures side by side: **statistical drift = ingest
green + drift metric + alert firing; schema drift = ingest refusal, exit
code, NO drift metric at all** (S1's transcripts are the second half — cite
them). **F-035's landing (§0)**: the client-side counters via pushgateway —
the 422-refusal count from the quote client (A-3's client half) and A-4's
served-version-vs-registry gauge from a reader script pushed on a cadence;
land them or re-disposition honestly (`render_alert_rules.py`'s
absence-agreement check forces the record either way). **F-043's landing
(§0, option c)**: the SLO doc states the ~90%-CPU in-pod reliability limit
with the measured evidence, A-1's `why` carries the caveat, node-side and
edge-side signals named as the saturation instruments.
Accept when: backup manifest dated this session · pushgateway scraped (its
series visible via a Prometheus API query paste) · drift metrics for
2020-01..03 in Prometheus with the reference declared · the drift alert
FIRED on 2020-03 with the prediction written first and the threshold argued
before the run, then cleared · the two failure signatures recorded
distinguishably in one doc section · F-035 counters landed or
re-dispositioned with the absences check green · F-043's sentence + caveat
landed (closes the row).
Evidence plan: the backup manifest path · the Prometheus query pastes
(before/after push) · the prediction-then-firing transcript · the rules diff
+ `make alert-rules` output · the SLO-doc diff.
Safe stopping point: pushgateway + metrics up, alert unfired — the firing is
one job run away; say so.

### M7-S4 — The scheduled retrain, landing a challenger through the pre-registered gate  (role:MLE A; MLOps R)

The loop closes: drift seen (S3) → retrain → challenger → the gate decides.
**Two intakes are mandatory here and both are named in §0.** (1) **F-022**:
land the decided option (a) — the bake-off's incumbent cell resolves by alias
and reads its feature set off the LOADED model, not its Spec — and run one
`--smoke-rows` execution past contender resolution (closes the row). (2)
**F-020**: fold option (a) into the retrain itself — the challenger is the
champion's configuration with the **count-scaled knobs rescaled to the
refit's row count** (`min_data_in_leaf` 1293 was 1-in-5,105 at the 15%
sample; rescale to the same fraction at full scale) **and the round budget
re-derived** rather than inherited from the sniper's 800-round per-trial cap
— reported through the ONE evaluator beside the 3.2403 that stands. If the
measurement is cut for budget, option (b) (the recorded scale-transfer rule
in the sniper/refit path) is the fallback closure; either way the decision is
recorded WITH the change. **The training window is a recorded decision**: the
honest default is the SAME 2019 window (train 01–06, val 07, test 08) — the
first retrain proves the LOOP and F-020's rescale, and the holdout keeps its
meaning; a window that swallows 2020 months changes what the holdout measures
and is NOT this story's to decide silently (if wanted, it is an ARCH/PO
question routed, not an edit). **The schedule**: probe whether Flyte 2.6.1 /
chart v2.0.42 supports scheduled runs (launch-plan schedules or the 2.x
equivalent — ask the server, gotcha #70's family); 3-attempt wall; the
recorded fallback is the repo's own cron (`automation/` — the watchdog
precedent) triggering the retrain workflow, a deviation recorded with its
reason exactly as Flyte's port-forward console was at M4-S2. Prove the
mechanism fired once with a CHEAP run (sampled → exit 3, no verdict — F-008
honored; the schedule is what is being proven), then run the REAL full-data
retrain **detached** (`automation/run_detached.sh` — ritual e; the fit is
~31 min on-cluster and gotcha #66 means a fresh commit makes it a cold
cache). The gate as pre-registered decides (law 3): **a REFUSE ends the story
green** — record the verdict, the challenger stays a tagged registry version,
`@champion` unmoved. **A PROMOTE obliges the transition chain** (M3-S5's
precedent: promote → predictions → duckdb → marts → boards → serve cutover →
parity) — that is a second leg by size; if the verdict lands late in the
session, STOP at the recorded verdict with the alias unmoved (promotion
deferred is coherent; half a transition is not) and hand the chain the
transition as the next leg.
Accept when: F-022 closed (change + smoke execution transcript) · F-020
closed (the rescaled-refit measurement beside 3.2403, or the recorded rule)
· the schedule mechanism proven (registered + observed firing once, or the
recorded cron deviation with its reason) · the full-data challenger exists
in MLflow with signature + verdict tags, judged by the gate as it exists on
disk · the alias state coherent with the verdict (unmoved on REFUSE; fully
transitioned or explicitly deferred-with-alias-unmoved on PROMOTE) ·
verify-m5 §2 coherence green at story end.
Evidence plan: the two closure transcripts · the schedule record · the
detached run's verdict JSON (tracked) · the registry read before/after ·
the gate's verdict lines.
Safe stopping point: named above — the recorded verdict with the alias
unmoved is a legitimate leg boundary; say which branch was taken.

### M7-S5 — The DA drift memo, the predictions & drift board, and the M7 gate  (role:DA A for memo+board; SRE A for the gate; legs allowed)

**Leg 1 — the memo and the board.** `docs/drift_memo_m7.md`: what ACTUALLY
changed in 2020-03, in domain terms with numbers — interpretation, not
detection (BLUEPRINT §9/M7): volume (the raw file is 44.4 MB against
2019-01's 110.4 — start there), trip mix, zones (airports first — the memo
is §0-named reader of `docs/error_memo_m2.md` §7 row 2 and cites it if the
data speaks), durations, and what the champion's error series did as the
world moved (S2's monitoring numbers, labelled as monitoring numbers). Every
figure from a named view/mart (the error-memo discipline; a
`drift_memo_numbers.py` twin script is the M2-S4 precedent and the gate will
check prose against records — gotcha #90's one-decimal floor applies). The
**predictions & drift board** in Metabase over S2's mart (checked-in JSON,
converged by name, `--verify` green; KPI ids cited per card, KPI-09/10 on NO
card — the standing law). **Leg 2 — `make verify-m7` + `make
verify-m7-redteam`**, under every inherited law: re-runs nothing expensive
and mints nothing it counts (seventh inheritance — no retrain, no drift job,
no ingest; it reads tracked records, the live registry, the live Prometheus,
the committed docs) · every literal derived on both sides (F-017; drift
thresholds parsed from the rules file and found in the doc that argues them,
never re-typed) · asks the live system a bounded set of questions (one
prediction, one Prometheus query answered, one rules read — the verify-m6
shape) · prose checked against records at ≥1 decimal (gotcha #90) · the two
failure signatures asserted DISTINGUISHABLE from the records (the §9/M7
"Show" leg) · Python legs guarded by `expect_verdicts` · the red team plants
ONE derived-plausible value in a tracked record, RED from two artifacts,
sha256 restore, GREEN after.
Accept when: memo committed with every number citing its view and
re-derivable by its twin script · board renders with live data,
`--verify` green · verify-m7 GREEN with section/sub-check count stated ·
red team RED for the planted cause with untampered sub-checks passing,
GREEN after · §9/M7's accept-when quoted and answered line by line ·
deployments/signoff ledgers current.
Evidence plan: the memo + its numbers script · the board JSON + verify
output · both gate transcripts.
Safe stopping point: leg 1 merged with the gate unbuilt — the M4-S5/M6-S5
precedent; say so.
Exit: `automation/next_session.sh rev 120` — **M7 is ◆**: REV's monitoring
review runs in a fresh session (re-derives at least one drift number from
raw artifacts; audits the retrain verdict's evidence chain), then REV exits
`automation/next_session.sh architect 120` for the boundary.

## Out of scope (named now so creep is visible later)

- **Feast, point-in-time training joins, transformer enrichment — all M8.**
  S3's drift reference reads existing parquet/views; no feature store.
- **Re-running the scout×sniper automation track.** F-020 lands as a rescale
  rule/measurement on the EXISTING winner's configuration; a fresh tuning
  campaign is not in §9/M7 and DR-01's budget law has no M7 allocation.
- **Moving the training window into 2020** — a recorded ARCH/PO question if
  anyone wants it (S4); the first retrain proves the loop on the settled
  window.
- **Ray, CI smoke, trivy, demo page (M9** — demo still "never on the
  acceptance path"**)**.
- **Registry pattern, Flyte's declared 8080 route, monitoring hostPorts
  (3000/9091)** — the next PO-sanctioned rebuild, unchanged (D-001's note).
- **Any hand-moved alias.** M6-S4's rehearsal is done; M7's only alias path
  is the gate (law 3).
- **Editing any 2019 artifact, threshold, or gate condition** — law 2, law 4,
  and F-016's park respectively.

## Risks & walls (carried counts restated; fallbacks cite ADRs/precedents)

| Risk / wall | Count | Fallback |
|---|---|---|
| **Evidently vs pandas 3.0.5** — the full-`mlflow` shape (gotcha #36: a resolver quietly downgrading cores, or the add refusing outright) | probe FIRST in S3, 3-attempt wall | Hand-rolled PSI/KS/population-share drift stats in our own module over scipy 1.18 (already in the graph) — a recorded DIFFER from the blueprint's named tool; or gotcha #16's dependency quarantine (isolated venv) if Evidently's value earns the isolation. The drift LOOP (metric → pushgateway → alert) is identical under either producer |
| **2020-03 refuses at `max_rejected_fraction` 0.10** — COVID data may be legitimately filthy | measured at S1, not assumed | Record the refusal as a finding and route it: loosening the guard is a PO fork (AWAITING_PO), and the drift story can proceed on 2020-01/02 + whatever 2020-03 rows a PO-sanctioned path admits. Do NOT edit the contract to make the month fit |
| **Flyte 2.x schedule support unknown** (chart v2.0.42; the 2.x CLI is verb/noun, not 1.x launchplans) | 3-attempt wall in S4 | The repo's own cron triggering the retrain workflow (the `automation/` watchdog precedent), recorded as a deviation with its reason — the M4-S2 flyte-console precedent for honest deviations |
| **A PROMOTE verdict late in S4's session** — half a transition is worse than none | named in S4 | Stop at the recorded verdict, alias unmoved (coherent by design — promotion deferred is a state the registry expresses; a half-transition is not); the transition chain is the next leg, M3-S5's precedent typed out |
| **gotcha #66: any commit under src/scripts/analytics/docker/pyproject/uv.lock re-images and colds the cache** — the retrain becomes a 31-min fit regardless | priced in S2/S4 | Run full-data work detached (ritual e, `run_detached.sh`); never interleave commits with a run in flight (gotcha #45's sibling) |
| **The drift threshold does not fire on 2020-03** | law 4, prediction-first | A wrong prediction investigated on the record (F-041's precedent) — check the instrument before the bar (is the metric computed over the right columns? the right reference?), and only then argue a revised bar in the doc, dated, beside the original |
| **The exporter-starvation class recurs** (F-043's mechanism) if S3's drift job or S4's retrain saturates the node | known, documented | F-043's sentence lands in S3: above ~90% CPU trust node-side (cAdvisor) and edge-side (ingress) signals; drift jobs run off the predictor's node path entirely (pushgateway decouples producer from scrape) |
| **Pushgateway staleness semantics** — a pushed metric persists after its producer dies, so "drift metric present" is not "drift job ran recently" | design-time in S3 | Push an end-of-run timestamp metric beside the values (the prior-art ADOPT pattern: end-of-window stamps) and let the alert/board read staleness explicitly; a drift alert with no freshness guard is gotcha #78's empty-panel disease inverted |
| **WSL memory with one more tenant + batch scoring** | 37Gi available observed | Pushgateway is tiny; batch scoring is a host/pod process that ends. If scheduling pressure appears, `kubectl describe node` BEFORE touching any limit |

## Open PO questions (options · recommendation · default-with-date)

**None new.** Standing, restated: **2026-08-18-1 (F-016, incumbent margin) —
now ACTIVE**: M7's gate invocations proceed AS PRE-REGISTERED per the M6
kickoff's standing rule; the PO's answer, whenever it lands, applies from the
next invocation. · **2026-08-17-1** (host `libgomp1` one-liner) ·
**2026-08-16-2** (allowlist paste). The chain continues; nothing parks.

## ARCH self-check (v3.0)

model stated Fable: **yes, first line** · every story sized for one short
executor session: **yes — S4 is the long one and names both its detached run
(ritual e) and its PROMOTE-branch leg boundary; S5 names its two legs (the
M6-S5 precedent)** · debt intake diffed against ledgers/debt.md: **yes —
register fully closed, stated in the table; obligation intake (F-020→S4,
F-022→S4, F-035→S3, F-043→S3, shadow teardown→S1) replaces it** · forks
routed to AWAITING_PO: **none new; F-016 stands parked with its standing
proceed-as-pre-registered rule; two potential forks are pre-routed as risks
(a 2020-03 contract refusal; a training-window change), each named as a
route-not-edit** · every carried finding restated with quoted landing:
**F-020 and F-022 intaken here at their quoted landing (§9/M7 "scheduled
Flyte retrain landing a challenger"); nothing carries past M7 from this
triage** · gates loosened: **none — verify-m7 inherits every predecessor law
(seventh inheritance), and law 4 legislates how drift thresholds must be
argued before they exist**.
