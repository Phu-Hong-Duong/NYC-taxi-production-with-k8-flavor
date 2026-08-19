# M6 KICKOFF — Reliability: SLOs, shadow → canary → rollback, gameday   (authored by: ARCH/Fable · 2026-08-19 · v3.0: the Architect is sole author)

Session model stated: **Fable 5 (claude-fable-5)** — architect sessions on any
other model are void (ORG.md rule 7).

**M6 carries no ◆** (BLUEPRINT §9: REV gates are M2, M3, M7). The last story
exits to the boundary: `automation/next_session.sh architect 120`.

**The three laws this milestone lives under, stated once at the top.**
(1) **THE CLUSTER IS STATEFUL AND NO M6 STORY MAY TAKE IT DOWN** — unchanged
since M2. Monitoring UIs get NO new hostPort (kind publishes host ports at
cluster-CREATE only; checked live below — 3000/9091 have no mapping and never
will until the PO-sanctioned rebuild). Grafana and Prometheus are reached
through the EXISTING 8081 ingress (host- or path-routed — the controller is
already there; that is what M5-S1 bought) or by port-forward. A story that
finds itself wanting a hostPort has found a wall.
(2) **M6 MAY CHANGE WHAT IS ON THE WIRE, AND EVERY CHANGE IS DELIBERATE,
RECORDED, AND ENDS WHERE IT STARTED.** M5 was a measurement milestone and
refused twice to edit the deployed workload; M6 is the milestone those
refusals were routed TO. The CPU request re-size (S2), the spike's re-deploy
(S3), the canary shifts and both rollback rehearsals (S4) all mutate serving
state — each lands in the deployments ledger with its measured outage
(~15–18 s per deployment change: measured twice, 14.53 s killed pod, 18.24 s
stop/start), and **every story ends with `@champion` = version 2, `configs/
train.yaml: features.version` = v2, and the champion serving 100%** — the
verify-m5 §2 coherence check is the story-exit invariant, re-run after every
mutation.
(3) **NOTHING PROMOTES.** The gate is not invoked in M6; no story mints a
registry version (M4's strong form, inherited). The alias moves exactly twice,
both inside S4's ROLLBACK REHEARSAL (v2→v1→v2, the runbook's own §4, sanctioned
by the M5 PRR — "M6 owns the rehearsed revert"), as a typed human-override
rehearsal, never through `registry.promote`. F-016 (incumbent margin) is the
PO's and nothing here touches a gate condition.

## 0. Boundary triage of M5 (the closure sweep, folded in)

**Verify re-run (by the approver, this session, 2026-08-19):** `make verify-m5`
→ **GREEN — 49 `ok` sub-checks across 7 sections, exit 0** (counted from the
transcript; a first `grep -c "ok  "` said 50 and the 50th was the pattern
matching inside `runbook<spaces>` in the gate's own footer — gotcha #68's
lesson landing on the approver, noted so nobody re-counts it wrong).
Highlights, pasted not remembered: §2 `the live answer reproduces the recorded
parity row to 0.000e+00 minutes (10.665224429 vs 10.665224429)` · §2 `the
served version's feature_set tag ('v2') equals configs/train.yaml's
features.version` (F-032's check, live) · §5 `the outage is 14.53 s and it
reconciles: recovered_at 40.03 - first_error 25.5 = 14.53 (the error-span
anchor would say 14.251 — gotcha #75)` · §7 `@champion is version 2, whose run
is the winner the M3 bake-off recorded — no M5 story moved the pointer` · §7
`the rollback target exists: version(s) 1 (v1)`. Closing line verbatim:
`[verify-m5] GREEN — every M5 sub-check passed.` The red team was run and
PASSED by the executor at M5-S5 (one rewritten number → RED with 2 FAILs from
two different artifacts, sha256-verified restore → GREEN); the gate re-run here
mutates nothing, per its own law.

**Lineage spot-check (gotcha #20):** `git merge-base --is-ancestor 3e28a1f
origin/main` (M5-S2's merge, mid-milestone) → ancestor confirmed;
`git branch -r --contains 3e28a1f` → `origin/main`. M5 is PRs **#28–#32**
(S1–S5, one each). Tree clean at `44db7f6`.

**REV:** none — M5 carries no ◆ (next ◆ is M7).

**Every open finding, condition, and due debt from M5, dispositioned:**

| Item | Disposition |
|---|---|
| **F-029** (gates replayed gitignored records) | **CLOSED at M5-S1** by the amended condition — 32 records tracked, both gates and both red teams re-run green over the moved files, clean-drill-leaves-a-clean-tree now checkable. Restated only. |
| **F-009** (alias-URI load fails on MLflow 3.15.1) | **CLOSED at M5-S2** by option (b): serving needs the same alias → logged-model → `artifact_location` resolution, documented as an MLflow-3 property in ONE resolver; a deploy trusting `source` would download an empty prefix and succeed. Restated only. |
| **F-019** (champion raises outside 2019) | **CLOSED at M5-S2** by BOTH halves: table derived to 2030 (`make holidays`) AND a typed 422 refusal past the horizon (`UncoveredDateError`, exit 2). The SRE half minuted in the PRR; M6 inherits the named signal (A-3, the 422 count). Restated only. |
| **F-030** (NaN not JSON — ~1% of riders got a 422 parse error) | **CLOSED at M5-S3**: missing travels as `null`, infinity refused, `allow_nan=False` guard; the no-geometry rows parity at 0.000e+00. Restated only. |
| **F-031** (parity red team green under its own tampering — "positional payload" claim false) | **CLOSED at M5-S3** by correction: this runtime pairs by NAME through the logged signature; arm A re-planted to a cause the runtime can express (4.210e+01 min skew). Restated only. |
| **F-032** (a rollback is three moves; nothing enforced the second) | **CLOSED at M5-S5** by a check: every version carries a `feature_set` tag, the runbook's config step is derivable, and `verify-m5` §2 asserts served-tag == config live. **What it did NOT close: the rehearsal.** The rollback is TYPED and NOT REHEARSED — **intaken → M6-S4**, which runs it for real (the M5 PRR's "M6 owns the rehearsed revert"). |
| **F-016** (incumbent gate margin; the alias moved on +0.63%) | **Standing at AWAITING_PO 2026-08-18-1** — a gate-condition fork is the PO's, blocking only at M7's first retrain. M6 promotes nothing (law 3), so nothing here rides on the answer. If unanswered by the M6→M7 boundary, M7 proceeds with the gate as pre-registered (option A is the standing status quo, not an auto-adopted recommendation). Restated so it is visibly not lost. |
| **F-020** (tuned config is 15%-sample-optimal applied unchanged at full scale) | **CARRY → M7, unchanged and not due here** — quoted landing stands (§9/M7: *"scheduled Flyte retrain landing a challenger"* re-runs the same scout→sniper→refit path). **Ledger repair made this triage**: the F-020 row had lost its newline and leading `\| F-020` cell — its entire content sat fused onto the tail of the F-021 row (line 15), so `grep F-020 ledgers/findings.md` found NOTHING. The ID cell and line break were restored; the row's CONTENT is byte-unchanged. A register a grep cannot search is a register that loses findings silently — same family as gotcha #69, asked of a ledger. |
| **F-022** (bake-off un-runnable since its own promotion; direction decided (a) at the M4 boundary) | **CARRY → M7, unchanged and not due here** — quoted landing stands (§9/M7, as above): the retrain is the next builder of a contender set. Closes at M7 by the change + one `--smoke-rows` execution past contender resolution. Restated only. |
| `docs/error_memo_m2.md` §7 row 2 (airport gap held at 1.91× though v2 carries OD geometry) | **Stays open in the memo, no ledger row** — an analysis question whose next natural reader is M7's drift/retrain memos. **M6-S3's shadow disagreement table is a free second look** (v1 has no geometry, so airports should be where v1 and v2 diverge most — the DA memo should cite the row if the data cooperates), but closure stays M7's. |
| **The three things M5 owed M6 by name** (HANDOFF bc) | **All intaken**: (1) CPU request 200m vs ~1.31 cores observed → **S2** (changed on the wire WITH a before/after re-measurement); (2) the rollback rehearsal → **S4** and the platform-restore rehearsal (un-rehearsed since M4-S2) → **S5** as a gameday scenario; (3) alert signals A-1…A-7 with sources → **S2** (the SLO document puts numbers on them). **ADR-004's canary spike → S3** (its text predates the M0–M9 renumber: "M5 opens with a timeboxed spike" reads M6 today; its pre-approved cost "serving gets re-deployed once" is S3's budget; its "outcome recorded as ADR-006" predates the org-overlay ADR-006 — the outcome lands as **ADR-011**). |
| AWAITING_PO 2026-08-16-2 (allowlist) · 2026-08-17-1 (host libgomp1) | **Standing with the PO, both non-blocking.** Unchanged. |
| **Debt** | **NONE DUE — the register is fully closed** (D-001→M4-S3 · D-002→M1-S4 · D-003→M4-S5 · D-004→M4-S3), diffed against `ledgers/debt.md` this session. D-001's registry-pattern deferral stands with its trigger (image churn) and landing (next PO-sanctioned rebuild — the same event that owes Flyte's declared 8080 route and the monitoring UIs their hostPorts). **M6 does not trigger it**: no rebuild; monitoring images are upstream pulls. |
| Hygiene (this triage) | Two stale remote-tracking refs pruned (`origin/story/m5-s4-load-p95-selfheal`, `origin/story/m5-s5-prr-gate` — remote branches already deleted at merge; only local refs lingered). The F-020 ledger row repair (above). |

**Verdict: M5 CLEANLY CLOSED — tagged `m5-closed`.** §9/M5's accept-when green
against the quoted text: *"v1's M4 gate (KServe Standard, mlserver,
storage-config, THE parity test 1e-6, p95 measured, self-heal under load)"* —
all live (parity 0.000e+00 over 16 hazard rows against 1e-6; p50 17.2 / p95
104.2 / p99 107.2 ms at a stated 4 req/s × 60 s × concurrency 8; 14.53 s
self-heal with a different pod uid on a different node) — *"+ the Production
Readiness Review … minutes committed; deployments ledger opens"* — minuted
with every box carrying pasted evidence, §0 stating what the review could NOT
do; ledger open with five M5 rows. *"Show: parity output + PRR minutes"* —
both shown by the gate itself (§2 re-derives a parity row live at the cost of
one request). Gate re-run green at the boundary by the approver, red team
real, sign-off row added (producer EXEC S1–S5 PRs #28–#32, approver ARCH/Fable
— producer ≠ approver holds), no open item carried silently.

## Preconditions (verified LIVE at draft time 2026-08-19 — pastes, not memory)

| Precondition | Check run | Observed |
|---|---|---|
| M5 gate green at the boundary | `make verify-m5` | GREEN 49/49, 7 sections, exit 0 (paste in §0) |
| Cluster up, all Ready | `kubectl get nodes` | 3/3 Ready v1.36.1, age 2d3h — `mlops-taxi-{control-plane,worker,worker2}` |
| Champion serving, rollback target exists | verify-m5 §2/§7 (re-run this session) | endpoint answers with `model_version: 2` == alias; version 1 (`feature_set: v1`) present — S4's rehearsal target EXISTS |
| Port family healthy | `make ports` | `OK — 10 required port(s): 4 free, 6 held by us, 0 foreign` |
| Grafana/Pushgateway have NO published route, and cannot get one without a rebuild | `grep hostPort infra/kind/kind-config.yaml` | mappings exist ONLY for 80→8081, 443→8443, 30500→5000, 30900→9000, 30901→9001, 30300→3030. **3000 and 9091 are reserved names in the family, not routes** — monitoring UIs ride the 8081 ingress (law 1) |
| Headroom for ~3 new tenants | `free -h` · `df -h /home` | 37Gi available of 47Gi · 943G disk free |
| No deliberate park, no crash | `ls automation/STOP` · `git status` | STOP absent · tree clean at `44db7f6` |
| A pre-M6 backup exists | `ls /home/longt/dvc-remote/nyc-taxi-platform-backups/` | `2026-08-19T02-54-59Z` (M5-S1: 6 databases + 331 objects, 1.6 GiB, every dump verified) — predates M5-S2's serving MinIO identity; **S1 re-runs it before monitoring tenants land** |

## Debt intake (diffed against ledgers/debt.md this session)

| Debt id | Origin | What lands here | Absorbed into story |
|---|---|---|---|
| — | — | **No open debt rows exist** (all four closed with evidence; nothing re-carries). Obligation intake replaces debt intake: **F-032's rehearsal half → S4 · the restore rehearsal → S5 · the CPU request → S2 · A-1…A-7 numbers → S2 · ADR-004's spike → S3** (each quoted in §0). | S2, S3, S4, S5 |

## Stories (5; each independently finishable, safe stopping point after each)

### M6-S1 — Eyes: the monitoring stack on-cluster  (role:SRE A; MLOps R)

`make backup` FIRST (the M4-S2/M5-S1 precedent: new tenants land beside state
that has no other copy; the script enumerates from the server, so the new
`serving` identity's objects are covered without anyone editing a list). Then
`make deploy-monitoring`: **Prometheus + Grafana** (+ Alertmanager if the
chosen chart carries it — rules land in S2 either way), versions read LIVE and
pinned (tag+digest where images allow — the Metabase precedent), observed
values into CLAUDE.md's pin table. **Prefer the smallest footprint that scrapes
and renders** — a $0 single-machine program does not need the full
operator/CRD machinery if plain charts with static scrape configs do; if the
operator route is chosen anyway, argue it in the deploy script's header (the
choice is S1's, made with the charts read live, 3-attempt wall per option).
What must be scraped, in priority order: **the predictor's own metrics**
(probe FIRST whether mlserver 1.7.1 exposes `/metrics` and on which port —
believed 8082, but ask the server, never the docs — gotcha #70's lesson);
**ingress-nginx** (`controller.metrics.enabled` — request counts and status
codes per host, which is A-2's source and the canary observation surface);
**kube-state-metrics** (A-5's source: restarts, readiness). Grafana dashboards
are **checked-in JSON, provisioned** (the prior-art ADOPT, third application
after Metabase boards and alert rules) — one serving board: request rate,
5xx/422 split, p95, CPU + `nr_throttled`, restarts. Reached through the
EXISTING ingress (law 1): host- or path-routed on 8081; no new hostPort, no
kind-config edit. Idempotent re-run proven by pod AGE; `DRY_RUN=1` mutates
nothing, helm included (gotcha #30); no secret on a command line (Grafana
admin credential via the mode-600 overlay or a Secret from `.env` — never
`--set`).
Accept when: fresh backup manifest dated this session · `make quote` (one real
request) visibly increments a request counter in Prometheus (asserted by
querying Prometheus's API before/after — a scrape target list alone is not
evidence the pipeline works) · the Grafana serving board renders through the
declared route with live data · re-run is a clean upgrade proven by pod age ·
pins recorded · `make verify-m5` still GREEN after (the wire was not touched;
prove it, don't assume it).
Evidence plan: backup MANIFEST path · the before/after Prometheus query paste
· the board's provisioned-JSON path + a screenshot-equivalent (the rendered
panel's query answer pasted) · deploy transcript twice.
Safe stopping point: metrics scraped but no board — say so; S2 needs the
scrape, not the board.

### M6-S2 — Judgement: the SLO document, the alerts, and the CPU request  (role:SRE A)

**`docs/slo_serving.md`** — targets chosen and OWNED by SRE, numbers argued
not copied (BLUEPRINT §9/M6). The discipline that keeps this honest: every
target is argued from **user harm and measured headroom**, never set equal to
the number just observed (gotcha #63/#74's lesson applied to bars) — e.g. the
p95 target must state the load shape it holds at (M5's: 104.2 ms at 4 req/s,
ceiling ~6 req/s/replica at the 2-core limit) and the availability target must
price in what is already measured (a single-replica pod loss costs ~14.5 s;
a deployment change ~15–18 s — an availability target that forbids what every
deploy costs is a target the program plans to violate). Error-rate SLO
separates **5xx (ours) from 422 (the request's, F-019's typed refusal)** — one
is an outage, the other is a working guard. Then the **alert rules**: A-1…A-7
from the PRR's box 3, each implemented against the S1 stack with `for: 5m`
sustained conditions where sustain is right (the prior-art ADOPT) and
immediate where it is not (A-4's version-mismatch has no innocent transient).
Rules are checked-in files, provisioned — not clicked. **At least one alert
FIRED in a red team, observed end to end**: the cheapest honest one is A-2/A-5
via `make stop-start-drill` (an ~20 s deliberate outage the drill already
rehearses — the alert's `for:` window may need the drill's stop phase held
longer; if so, hold it deliberately and record the outage as the cost of the
proof). A-3 can be fired for free by a burst of past-horizon quotes (exit-2
refusals, no outage at all — fire it too if cheap). Prediction-before-firing:
write WHICH alert, at WHAT threshold, expected to fire in WHAT window, BEFORE
the injection (the gameday shape, rehearsed small). Finally **the CPU request
re-size** — the one open recommendation M5 routed here: `200m` → a value
argued from 1.31 measured cores + scheduling headroom (the limit stays 2),
applied to the wire (one deployment change, ~15–18 s, recorded), then
**re-measured**: `make load` with M5's exact shape, p95 before/after side by
side. The scheduler now sees the truth; nothing else should move — if p95
moves materially, that is a finding, not a footnote.
Accept when: the SLO doc exists with every target carrying its argument and
its load shape · alert rules committed + provisioned, listed by A-id · one
alert observed firing with the prediction written first, and clearing after ·
the CPU request changed on the wire with before/after p95 pasted and a
deployments-ledger row · verify-m5 GREEN after the re-deploy.
Evidence plan: the doc · the rules files · the firing transcript
(prediction, injection, alert state, clearance) · the two load JSONs
(tracked) · the ledger row.
Safe stopping point: SLO doc + rules landed but nothing fired — the firing
proof is S5's gameday positive control at worst; say so in the handoff.

### M6-S3 — The spike and the shadow  (role:SRE A; MLOps R; DA R for the memo)

**Half 1 — ADR-004's spike, DECIDED and recorded as ADR-011** (timeboxed;
pre-approved cost: ONE serving re-deploy — quote ADR-004's own line). The
question: what mechanism gives this program traffic-split canary and shadow on
a stateful kind cluster? Options, with the honest costs stated in the ADR:
(i) **Knative/Serverless profile** — KServe's native `canaryTrafficPercent`
(the prior-art ADOPT's premise), at the cost of a whole second serving stack
(Knative Serving + a networking layer) on a cluster that must not rebuild,
and every M5 artifact (runbook, gate §1's RawDeployment read-back) assumes
Standard mode. (ii) **Two-InferenceService split behind the EXISTING
ingress-nginx** — a second isvc plus a canary Ingress carrying
`nginx.ingress.kubernetes.io/canary: "true"` + `canary-weight`, reusing what
M5-S1 installed; mirroring via the `mirror-target` annotation for same-schema
shadow. (iii) **Dual-send from the client** for shadow (the blueprint names it
as the mirroring alternative). Recommendation, stated with its cost: **(ii)
for traffic, (iii) for the v1 disagreement table** — refuse Knative unless
(ii) fails at the 3-attempt wall, because the spike's budget is one re-deploy,
not a serving-stack migration. One wrinkle to probe, not assume: KServe
RawDeployment creates its own Ingress object — the canary Ingress must share
its host without fighting the operator's reconciler (hand-author a SECOND
Ingress the operator does not own; if the operator fights it, that is one of
the three attempts).
**Half 2 — the shadow, and the wire fact that shapes it.** The only real
challenger this program owns is **version 1** — genuinely different (5
features vs 24, no geometry), which is exactly what makes its disagreement
table worth a memo. **But raw traffic mirroring CANNOT shadow v1**: the live
wire carries v2's 24-feature matrix and v1's logged signature refuses it —
every mirrored request would 500 at the signature (F-032's shape, expected,
not a defect; write this down BEFORE the first 500 is seen). So: deploy v1 as
a second isvc (`nyc-taxi-eta-shadow`, resolved from the registry BY VERSION —
the F-009 resolver works by alias; extend it to take a version, same
alias→logged-model→artifact_location property) with ZERO user-facing traffic,
and run the shadow as **dual-send from the client**: the same raw quote
inputs (a declared, committed request set — parity's 16 hazards plus a bulk
sample of ordinary trips), features built per-target through the ONE
`features/` path (v1's 5 columns, v2's 24), both scored over the wire. The
**disagreement table** is the artifact: prediction delta distribution on
identical inputs, segmented (airport, no-geometry, long-trip, ordinary) —
committed as a tracked record + a doc table. The **DA shadow-analysis memo**
(BLUEPRINT v2.2/v2.5) reads it: which segments diverge, is the delta benign,
and a NAMED verdict as input to S4's go/no-go. **The honest expected outcome
is NO-GO for v1** — it is the known-worse model; the memo saying no is the
ritual WORKING, and S4's canary then uses the memo-approved challenger (see
S4). The memo should also cite error-memo §7 row 2 (the airport gap) if the
deltas speak to it.
Accept when: ADR-011 committed with the decision, the options' honest costs,
and the probe transcripts · the shadow isvc serves v1 with zero user traffic
and `@champion`/config untouched (verify-m5 §2 green) · the disagreement
table exists as a tracked record with segment grain · the DA memo exists with
a named verdict and its reasoning · the mirror mechanism (for same-schema
shadow) proven working on the champion's own schema OR recorded as refused
with the reason.
Evidence plan: ADR-011 · the table + memo · the shadow isvc YAML · the
dual-send transcript · verify-m5 re-run.
Safe stopping point: spike decided but shadow unbuilt — ADR-011 alone
unblocks S4's design; say what remains.

### M6-S4 — The release rehearsal: canary 10→100, rollback under load, and the alias revert  (role:SRE A; MLOps R)

Three rehearsals, in an order that ends where it started (law 2).
**(1) The canary.** The challenger that shifts traffic is the one the DA memo
can approve — and after S3's expected no-go on v1, that is **the champion's
own bytes under the challenger path** (a second isvc serving version 2: the
release MECHANISM rehearsed with a benign, memo-approved delta — its shadow
table is trivially 0.000, and the memo covers both tables). Under sustained
`make load`: 10% canary weight → **observe 90/10 in Grafana/Prometheus from
the ingress's per-backend counters** (the §9/M6 "canary 90/10 observed" leg —
observed from metrics, not asserted from the annotation) → 100%. **(2) The
traffic rollback, measured**: from 100%-shifted, revert to the champion path
in **<2 minutes under load** (§9/M6's number), error window measured by the
load client the way the kill drill measures (first-failure → first-success
anchors, gotcha #75; expected: near-zero errors — a weight flip is not a pod
death). **(3) The alias rollback rehearsal** — F-032's un-rehearsed half, the
runbook's §4 run FOR REAL, sanctioned by the M5 PRR: move `@champion` to
version 1 + move `configs/train.yaml: features.version` to v1 + `make serve`;
prove the 5-feature champion quotes (one prediction, version stamp `1`);
`make verify-m5` §2 green at the HALF-WAY state too (tag v1 == config v1 —
the coherence check passing on BOTH sides of the rehearsal is what proves it
checks coherence, not the literal v2); measure the wall-clock of the full
three-move rollback; then roll FORWARD (v1→v2, same three moves), re-verify
with one prediction + the parity row. Alias moves are typed raw
`set_registered_model_alias` per the runbook — never `registry.promote`, and
the runbook's NOT-REHEARSED labels flip to REHEARSED with the measured
numbers in every artifact that carried them (runbook §4/§8, PRR pointer,
deployments ledger, CLAUDE.md — the M4-S2 backup precedent run in reverse).
Accept when: 90/10 observed from metrics under load, then 100% · traffic
revert <2 min under load with its error window measured · the alias rollback
round-trip rehearsed with wall-clock per leg, one prediction at each end, and
the coherence check green at v1 AND at v2 · end state exactly M5's (champion
v2 at 100%, shadow/canary isvc torn down or zero-weighted, verify-m5 GREEN)
· runbook labels updated everywhere they exist · deployments-ledger rows for
every mutation.
Evidence plan: the Grafana/Prometheus 90/10 paste · the revert timing record
(tracked JSON) · the rehearsal transcript with timings · the runbook diff ·
verify-m5 re-run at v1-state and at end.
Safe stopping point: after (1)+(2) with (3) undone — the alias rehearsal is
separable; say so and leave the wire at M5's state.

### M6-S5 — Gameday 1, the restore rehearsal, and the M6 gate  (role:SRE A; all roles at the table)

**Gameday 1**, predecessor-style (BLUEPRINT §9/M6): **positive control
first** (the prior-art ADOPT — fire A-2 or A-5 deliberately and watch the
pipeline end to end before trusting any negative result). Then staged
failures, each with a **distinguishable signature PREDICTED in writing BEFORE
injection** and checked after: (1) **kill the predictor under load** — M5-S4's
drill re-run, but the prediction now includes the ALERT: ~14.5 s of 503s AND
A-2/A-5 firing within their windows; (2) **break the storage-config secret**
then delete the pod — predicted signature: the REPLACEMENT cannot start
(init-container failure, A-7's class), which must be DISTINGUISHABLE from
(1)'s 5xx signature; verified undo staged BEFORE injection (`make serve`
re-converges the secret from `.env` — the M2 red-team rule: a drill with no
rehearsed undo is a gamble, not a drill); (3) **saturate CPU** — drive past
the measured ceiling (~8 req/s at the 2-core limit): predicted signature is
latency + `nr_throttled` (A-1/A-6) with NO error spike (gotcha #74's lesson
as a prediction). (4) **The platform-restore rehearsal** — un-rehearsed since
M4-S2, named by the M5 handoff: restore the newest backup's SMALL,
irreplaceable dumps (mlflow, optuna, metabase — <400 KiB total) into SCRATCH
databases in the one Postgres (D-002's additive path names them; e.g.
`mlflow_restore_drill`) plus a MinIO scratch prefix, verify contents against
the backup MANIFEST (row/object counts), then DROP the scratch — the LIVE
databases are never touched. What this claims and what it does not, stated in
the record: the dumps RESTORE and the procedure is typed and timed; a full
restore over a dead platform remains un-rehearsed until a PO-sanctioned
rebuild, and every artifact that said NOT REHEARSED now says
"scratch-rehearsed <date>; full restore still not" — the honest label moves
one notch, not to green. **The accept bar §9/M6 sets: at least one prediction
wrong and investigated** ("a gameday with all predictions right was too
easy") — do not engineer a wrong prediction; if all match, add a scenario
rather than shipping a too-easy gameday, and if they STILL all match, say so
and argue why (an honest report beats a manufactured surprise).
Then **`make verify-m6` + `make verify-m6-redteam`**, under every inherited
law: re-runs nothing expensive, mints nothing it counts, no skip flag, no
fast mode (sixth inheritance) · every literal derived on both sides (F-017 —
the SLO thresholds read from the SLO doc/rules files, never re-typed; the
served version from the alias, never "2") · recorded evidence read from
tracked records (gotcha #66's regime) · Python legs guarded by
`expect_verdicts` · asks the LIVE system for at least: one prediction (the
verify-m5 §2 shape), one Prometheus query answered, one alert rule loaded ·
checks the PROSE against the records (SLO doc numbers vs load records;
runbook's REHEARSED claims vs S4's records — the M5-S5 shape) · the red team
breaks ONE recorded field or pointer, restores byte-identically under an EXIT
trap, RED naming it while untampered sub-checks pass, GREEN after.
Accept when: gameday record committed with predicted-vs-observed per
scenario, the positive control first, ≥1 wrong-and-investigated (or the
argued exception) · restore rehearsal record + labels moved one notch
everywhere they exist · verify-m6 GREEN with its section/sub-check count
stated · red team RED for the planted cause, GREEN after · §9/M6's
accept-when quoted and green line by line · deployments/signoff ledgers
current.
Evidence plan: the gameday record · the restore transcript + manifest
reconciliation · both gate transcripts · the ledger rows.
Safe stopping point: gameday complete, gate unbuilt — that is a legitimate
leg boundary (the M4-S5 precedent: say so, exit through the ritual, the gate
lands as leg 2).
Exit: `automation/next_session.sh architect 120`.

## Out of scope (named now so creep is visible later)

- **Drift, Evidently, Pushgateway (9091), the retrain loop, batch predictions
  mart — all M7.** The monitoring stack S1 lands is M7's substrate; nothing in
  M6 pushes a drift metric.
- **Any promotion through the gate** (law 3; F-016 is the PO's). S4's alias
  moves are typed rehearsals of the runbook, round-tripped inside one story.
- **Feast (M8) · demo page (M9** — still "never on the acceptance path"**)**.
- **Registry pattern, Flyte's declared 8080 route, monitoring hostPorts
  (3000/9091)** — the next PO-sanctioned rebuild, unchanged (D-001's note).
- **Pipeline runs** — nothing in M6 needs one (gotcha #66 stays theoretical
  here; if one is ever warranted, the first run after any commit under the
  guarded paths is a 31-minute re-fit, planned detached or not planned).
- **A second REAL challenger** (retraining, re-tuning) — M7's. M6 rehearses
  the release path with the models that exist.

## Risks & walls (carried counts restated; fallbacks cite ADRs)

| Risk / wall | Count | Fallback |
|---|---|---|
| mlserver's metrics endpoint is assumed (believed `/metrics` on 8082) but unprobed | probe FIRST in S1 | If absent/unscrapabale: ingress-nginx per-host metrics still carry rate/status/latency (A-1/A-2 land), and the load client's own records remain the latency source of record — the SLO doc says which instrument each number comes from (gotcha #70: ask the server) |
| Operator-stack (kube-prometheus CRDs) fights kind or bloats the $0 machine | 3-attempt wall per option | Plain Prometheus + Grafana charts with static scrape configs — less machinery, everything M6 needs; the choice and its costs recorded in the deploy script header |
| KServe's reconciler fights the hand-authored canary/mirror Ingress | 3-attempt wall (counts toward the spike) | Dual-send from the load client for BOTH shadow and the 90/10 observation (blueprint pre-approves it as the mirroring alternative); the canary weight then rides the client, and ADR-011 records why the ingress path lost |
| Knative as the spike's answer — a serving-stack migration on a stateful cluster | pre-refused unless (ii) fails its wall | ADR-004's budget is ONE serving re-deploy; a Knative install is not a re-deploy. If (ii) and (iii) both fail their walls, STOP and write the wall up — that is an AWAITING_PO fork, not a bigger install |
| Mirrored/shadowed traffic to v1 500s at the signature | expected, written down in S3 | Not a defect — F-032's shape. The v1 disagreement table comes from dual-send with per-target feature builds; mirroring is only for same-schema challengers |
| Alert `for: 5m` windows vs ~20 s drill outages — the proof can't fire the alert | anticipated in S2 | Hold the stop phase deliberately long enough, record the outage as the proof's cost — or fire A-3 (past-horizon quotes: free, no outage) and let the gameday's kill scenario prove A-2/A-5 at S5 |
| Every serving mutation is a ~15–18 s outage (1 replica) | measured twice (M5-S4/S5) | Deliberate, recorded, no users; the count of mutations is itself an argument the SLO doc must price (availability targets that forbid deploys are violated by design) |
| An SLO/alert threshold set equal to the number just measured | gotchas #63/#74 in bar-form | Every target argued from harm + headroom with its load shape attached; the gate checks the DOC against the records, so a copied number is at least a visible one |
| WSL memory with ~3 more tenants | 37Gi available observed | Small charts; if scheduling pressure appears, `kubectl describe node` BEFORE touching any limit (evidence before state changes) |
| The gameday secret-break leaves serving down if the undo is wrong | undo staged before injection | `make serve` re-converges the secret from `.env` (idempotent, proven at M5-S2 ×4); the injection is annotation-scale reversible, and the scenario is run LAST among the failure injections so a surprise doesn't block the others |

## Open PO questions (options · recommendation · default-with-date)

**None new.** Standing, all non-blocking for M6: **2026-08-18-1** (F-016
incumbent margin — becomes blocking at M7's first retrain; if unanswered by
the M6→M7 boundary, M7 proceeds with the gate as pre-registered) ·
**2026-08-17-1** (host `libgomp1` one-liner) · **2026-08-16-2** (allowlist
paste). The chain continues; nothing parks.

## ARCH self-check (v3.0)

model stated Fable: **yes, first line** · every story sized for one short
executor session: **yes — S5 is the densest and names its leg boundary (the
M4-S5 precedent); S4's load windows are minutes, not hours, so ritual (e) is
optional there and the story says the M5-S4 foreground precedent applies** ·
debt intake diffed against ledgers/debt.md: **yes — register fully closed,
stated in the table; obligation intake (F-032 rehearsal→S4, restore→S5, CPU
request→S2, A-1…A-7→S2, ADR-004 spike→S3) replaces it** · forks routed to
AWAITING_PO: **none new; F-016 stands parked; the spike is an executor
decision inside ADR-004's pre-approved budget, not a fork** · every carried
finding restated with quoted landing: **F-020→M7, F-022→M7 (both quoted in
§0)** · gates loosened: **none — verify-m6 inherits every predecessor law;
M6 adds checks and a new document that OWNS thresholds, and the kickoff
legislates how those thresholds must be argued**.
