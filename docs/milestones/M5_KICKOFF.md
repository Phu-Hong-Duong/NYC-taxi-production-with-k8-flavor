# M5 KICKOFF — Serving & release (KServe)   (authored by: ARCH/Fable · 2026-08-19 · v3.0: the Architect is sole author)

Session model stated: **Fable 5 (claude-fable-5)** — architect sessions on any
other model are void (ORG.md rule 7).

**M5 carries no ◆** (BLUEPRINT §9: REV gates are M2, M3, M7). The last story
exits to the boundary: `automation/next_session.sh architect 120`.

**The two laws this milestone lives under, stated once at the top.**
(1) **THE CLUSTER IS STATEFUL AND NO M5 STORY MAY TAKE IT DOWN** — unchanged
since M2, and M5 adds serving state beside the registry/marts/app-db/studies
state that already has no other copy. The ingress route M5 needs was
pre-provisioned at cluster creation (host 8081←container 80, 8443←443 — checked
live below), so **no story below needs a rebuild, a new hostPort, or a
kind-config edit**. A story that finds itself wanting one has found a wall:
stop and write it up (three-attempt rule).
(2) **SERVING READS THE POINTER AND NEVER MOVES IT.** `@champion` is version 2
and stays version 2 through every M5 story; F-016 (whether the incumbent gate
condition needs a margin) is the PO's at AWAITING_PO 2026-08-18-1 and nothing
in M5 touches promotion. `verify-m5` asserts the strong form M4 established:
no M5 activity mints a registry version.

## 0. Boundary triage of M4 (the closure sweep, folded in)

**Verify re-run (by the approver, this session, 2026-08-19):** `make verify-m4`
→ **GREEN — 39 `ok` sub-checks across 7 sections, exit 0** (counted:
`make verify-m4 2>&1 | grep -c "ok  "` → `39`). Highlights, pasted not
remembered: §4 `the two witnesses AGREE: the control plane says no cacheable
stage re-executed and MLflow minted no run to contradict it` · §5 `a task that
always raises settled at attempt index 3 and the run FAILED — the budget of 2
is real AND finite` · §6 `the published fact table reconciles with the analyst
layer for all 8 month(s), 56,127,878 rows — asked of Postgres and DuckDB
separately, republished nothing` · §7 `none of the 28 run(s) the M4 pipeline
fitted is a registry version (2 version(s) exist, all from earlier milestones)`
· `@champion resolves to version 2 (run 92b73bd4f77d…)`. Closing line verbatim:
`[verify-m4] GREEN — every M4 sub-check passed.` The red team was run and
PASSED by the executor at M4-S5 leg 3 (one flipped field → RED with the
cross-system leg firing, sha256-verified restore → GREEN 39/39); the gate
re-run here mutates nothing, per its own law.

**Lineage spot-check (gotcha #20):** `git merge-base --is-ancestor 6a43498
origin/main` (M4-S3's merge, mid-milestone) → ancestor confirmed;
`git branch -r --contains 6a43498` → `origin/main`. M4 is PRs **#20–#27**
(S5 landed as three legs: #25, #26, #27). Tree clean at `bff302a`.

**REV:** none — M4 carries no ◆ (next ◆ is M7).

**Every open finding, condition, and due debt from M4, dispositioned:**

| Item | Disposition |
|---|---|
| **F-029** (two milestone gates replay records that are gitignored; a tampered record leaves no diff; `verify_m3.sh`'s header said the opposite until leg 3 corrected it) | **Policy DECIDED this triage (ARCH): Option A — the records enter review.** `automation/runs/**/*.json` is un-ignored; logs and `.status` stay ignored. A over C: C's copy step is the twin this program refuses everywhere else. A over B: B leaves the tampered-record-with-no-diff hole open, and the records ARE the evidence base of two gates — what a gate reads must be what review can see. **Mechanics INTAKEN → M5-S1** as ONE PR (details in the story; half the mechanics would be a #51-class inconsistency — tracked files under headers still saying "gitignored"). Ledger row amended: closes on S1's landed mechanics, stricter than the row's original condition, for the reason recorded there. |
| **F-022** (the bake-off script un-runnable since its own promotion moved the alias; the incumbent cell's Spec pre-registers a feature set the pointer has outgrown) | **Direction DECIDED this triage (ARCH): option (a)** — the incumbent cell resolves by alias and reads its feature set off the LOADED model; the row means "the champion, whatever it is now." Pre-registration stays for the four fixed contenders (right for arms declared before their numbers existed, wrong for a pointer designed to move). **CARRY → M7**, quoted landing re-verified (gotcha #19): §9/M7 *"scheduled Flyte retrain landing a challenger"* — the retrain is the next builder of a contender set. Closes at M7 by the change + one `--smoke-rows` execution past contender resolution. |
| **F-019** (S2: the champion raises on any request dated outside 2019 — v2's g1 holiday flags, table holds 10 rows all 2019; a 500 per quote the moment anything serves. Tripwire test pinning the CURRENT behaviour added at M4-S1) | **INTAKEN → M5-S2**, the quoted landing honored on schedule (carried from the M3 boundary against §9/M5's serving story exactly for this moment). S2 DECIDES extend-the-table vs a typed policy for uncovered dates, with the SRE half (wrong quote vs outage) minuted in S5's PRR. Closes per its row: the decision recorded WITH the fix, tripwire updated to pin the NEW behaviour deliberately. |
| **F-009** (alias-URI load fails on MLflow 3.15.1; workaround localised in ONE place since M2-S4; gotcha #39 records its impostor) | **INTAKEN → M5-S2**, the quoted landing honored (carried since the M2 boundary). Closes per its row's (a) or (b) — either the bare alias made loadable, or the resolution step proven to be what serving needs too and documented as an MLflow-3 property. Not closable by the workaround continuing to work. |
| **F-016** (incumbent gate condition has no margin; the alias moved on +0.63%) | **Standing at AWAITING_PO 2026-08-18-1** — a gate-condition fork is the PO's, blocking only at M7's first retrain. M5 is legislated alias-neutral (law 2 above), so nothing here rides on the answer. Restated so it is visibly not lost. |
| **F-020** (tuned config is 15%-sample-optimal applied unchanged at full scale) | **CARRY → M7, unchanged and not due here** — quoted landing from the M3 boundary stands (§9/M7's retrain re-runs the same scout→sniper→refit path). Restated only. |
| `docs/error_memo_m2.md` §7 row 2 (airport gap held at 1.91× even though v2 carries OD geometry) | **Stays open in the memo, no ledger row** — an analysis question whose next natural reader is M7's drift/retrain memos. Restated so it is visibly not lost. |
| AWAITING_PO 2026-08-16-2 (allowlist) · 2026-08-17-1 (host libgomp1) | **Standing with the PO, both non-blocking.** The container path is fixed by construction (D-004 closed); the host one-liner remains the PO's and affects laptop runs only. |
| **Debt** | **NONE DUE — the register is fully closed** (D-001 → M4-S3 · D-002 → M1-S4 · D-003 → M4-S5 leg 2 · D-004 → M4-S3), diffed against `ledgers/debt.md` this session. D-001's registry-pattern deferral is not a debt row: it stands in `docker/DECISION-D001-image-delivery.md` with a trigger (image churn) and a landing event (the next PO-sanctioned rebuild — the same event that owes Flyte its declared 8080 route). **M5 does not trigger it**: no rebuild, and serving images are upstream pulls, not ours. |
| Hygiene (this triage) | Two stale remote-tracking refs pruned (`origin/story/m4-s5-marts-tail-task`, `origin/story/m4-s5-verify-m4` — the remote branches were already deleted at merge time; only the local refs lingered). Lineage lives in main's merge commits, per convention. |

**Verdict: M4 CLEANLY CLOSED — tagged `m4-closed`.** All §9/M4 accept-when legs
green against the quoted text (seven containerized stages on-cluster,
parametrized by month, incl. the D-003 marts tail · cache-hit rerun 1966.9 s →
3.2 s with two independent witnesses agreeing · kill-a-pod survived with the
retry budget proven real and finite · ADR-002's wall never hit, fallback still
armed), gate re-run green at the boundary by the approver, red team real,
sign-off row added (producer EXEC S1–S5 PRs #20–#27, approver ARCH/Fable —
producer ≠ approver holds), no open item carried silently.

## Preconditions (verified LIVE at draft time 2026-08-19 — pastes, not memory)

| Precondition | Check run | Observed |
|---|---|---|
| M4 gate green at the boundary | `make verify-m4` | GREEN 39/39, 7 sections, exit 0 (paste in §0) |
| Cluster up, all Ready | `kubectl get nodes` | 3/3 Ready v1.36.1, age 2d — `mlops-taxi-{control-plane,worker,worker2}` |
| Champion is the served candidate | verify-m4 §7 (re-run this session) | `@champion` → version 2, run `92b73bd4f77d…`; versions [1, 2] — the rollback target EXISTS, which S5's typed rollback depends on |
| Port family healthy, incl. the two serving ports | `make ports` | `OK — 10 required port(s): 4 free, 6 held by us, 0 foreign` — **8081 and 8443 are among the 4 free** (the cluster publishes them but nothing serves behind them yet) |
| The serving route needs NO rebuild | `grep hostPort infra/kind/kind-config.yaml` | `containerPort: 80 / hostPort: 8081  # KServe ingress (M5)` and `containerPort: 443 / hostPort: 8443` — pre-provisioned at creation, on the control-plane node |
| …but the standard kind ingress label is ABSENT | `grep -n "node-labels\|kubeadmConfigPatches" infra/kind/kind-config.yaml` | no matches — the upstream kind ingress-nginx manifest's `ingress-ready=true` nodeSelector will not schedule as-shipped. Risk R2 below; do not discover this at minute forty |
| A platform backup exists (pre-M5 state has a copy) | `ls /home/longt/dvc-remote/nyc-taxi-platform-backups/` | `2026-08-18T06-02-29Z` (M4-S2's run: 5 databases + 105 objects, 1.5 GiB, every dump verified) — **predates the M4 tail-task state; S1 re-runs it before serving tenants land** |
| Evidence records present for the gates S1 moves into review | `find automation/runs -name '*.json' \| wc -l` | all records both gates read are present on this machine (verify-m3 46/46 and verify-m4 39/39 both re-run green against them within the last 24h) |

## Debt intake (diffed against ledgers/debt.md this session)

| Debt id | Origin | What lands here | Absorbed into story |
|---|---|---|---|
| — | — | **No open debt rows exist.** All four (D-001…D-004) are closed with evidence; nothing re-carries. Finding intake replaces debt intake this milestone: **F-029 mechanics → S1 · F-019 → S2 · F-009 → S2** (each quoted in §0). | S1, S2 |

## Stories (5; each independently finishable, safe stopping point after each)

### M5-S1 — Evidence under review, then the serving platform  (role:MLOps)

Two halves, in this order — the first is small and makes every later record in
this milestone reviewable from the day it is written.

**Half 1 — F-029 mechanics (ONE PR).** Un-ignore the record JSONs
(`automation/runs/**/*.json`; note gitignore semantics: the directory exclusion
must become pattern-based — `automation/runs/**` + `!automation/runs/**/` +
`!automation/runs/**/*.json` or equivalent — a bare `!` rule under an excluded
directory silently does nothing). `git add` every record `verify-m3` and
`verify-m4` read. Correct the three lines the decision makes stale:
`verify_m4.sh`'s header and its closing `(gitignored: F-029)` print,
`verify_m3.sh`'s header note, and CLAUDE.md's verify-m3/verify-m4 rows. Then
re-run `make verify-m3`, `make verify-m4`, AND both red teams — they now edit
TRACKED files: the EXIT-trap restores are byte-identical so a clean drill
leaves a clean tree, and a crashed drill now recovers with exactly the
`git checkout --` that used to be a false belief. State the new regime in both
drill script headers: verdict JSONs stay small; logs stay ignored.
Accept when: `git ls-files automation/runs` lists every path both gates read ·
both gates GREEN and both red teams PASS after the move · the word "gitignored"
no longer appears in either gate's output about its own inputs.

**Half 2 — the serving platform.** `make backup` FIRST (the M4-S2 lifeboat
precedent: give the pre-serving state a copy before new tenants land beside it;
the existing backup predates the marts tail state). Then `make deploy-serving`:
ingress controller through the DECLARED route (see R2 — pin scheduling to the
control-plane node with a `kubernetes.io/hostname` nodeSelector derived from
the cluster name; a live `kubectl label` applied idempotently by the deploy
script is the fallback if the upstream manifest resists, and is legal — labels
are not create-time state), then cert-manager, then **KServe Standard /
RawDeployment** (ADR-004 — Serverless/Knative is M6's spike, not ours).
Versions read LIVE and pinned (tag+digest where images allow — the Metabase
precedent); observed values into CLAUDE.md's pin table. Idempotent re-run;
`DRY_RUN=1` mutates nothing, helm included (gotcha #30); no secret on a
command line (the M4-S2 mode-600 overlay pattern if one is needed). Expect
large pulls: the 99 MB Flyte console took 9m49s — set waits from that
measurement, and if an install must outlive the session, detach it
(`automation/run_detached.sh <name> --then-schedule executor -- <cmd>`,
ritual e) rather than waiting on it.
Accept when: fresh backup manifest dated this session · `curl` against
`http://localhost:8081/` answers FROM THE CONTROLLER (a 404 with an
ingress-controller signature is a pass — the route answers; connection refused
is the fail) · cert-manager and KServe controller Deployments available ·
re-run is a clean upgrade proven by pod AGE (the M4-S2 idempotence shape) ·
pins recorded.
Evidence plan: gitignore diff + `git ls-files automation/runs | wc -l` · both
gate re-run transcripts · backup MANIFEST path · deploy transcript twice
(install, then no-op re-run with pod ages) · the declared-route curl.
Safe stopping point: after half 1 alone the repo is strictly better; after the
ingress without KServe, the route is proven and S2 simply waits.

### M5-S2 — The champion on the wire  (role:MLOps; SRE consulted on the F-019 policy)

Serve `models:/nyc-taxi-eta@champion` as a KServe InferenceService on the
mlserver/MLflow runtime. The deploy script resolves the alias in **ONE place**
— this is **F-009's landing**: close it by its row's (a) (make the bare alias
URI loadable, e.g. by fixing what `registry.promote` records as `source`) or
(b) (prove serving needs the same `get_model_info` resolution step and record
it as a documented MLflow-3 property, with the KServe deployment resolving the
alias that way). Watch for F-009's impostor first (gotcha #39): the
discriminator costs one call — under F-009 `get_model_info` succeeds where
`load_model` fails; under missing MinIO credentials both fail. The model store
credential is a **NEW read-only MinIO identity** in a `storage-config` secret
(the Flyte-bucket precedent: a leaked serving credential must not be able to
write the registry's artifacts). The serving pod pulls by the in-cluster MinIO
name — split horizon is the HOST's problem, never a pod's (F-023's lesson);
nothing here needs the `stowConfigOverride` shape because no host-side client
uploads anything.
**F-019 is DECIDED in this story**, with the runbook shape in hand: extend
`data/reference/us_federal_holidays.csv` beyond 2019, or adopt a typed
serving policy for uncovered dates (degrade-and-flag vs refuse-with-a-typed-4xx
— never a raw 500). The two options differ in kind (wrong quote vs outage), so
the SRE half of the reasoning is minuted in S5's PRR; the M4-S1 tripwire test
is updated in the same PR to pin the NEW behaviour deliberately. A decision
recorded WITHOUT the fix does not close the row, and neither does a fix
without the recorded decision.
Accept when: a 2019-dated request through `localhost:8081` returns a
prediction with the served model version visible in the response, and the
value spot-matches the locally-loaded champion on the same feature row (THE
parity test is S3's; this is one row, not the gate) · a 2026-dated request
gets the DECIDED behaviour, observed and typed · `@champion` version 2 before
and after, read by the script · F-009 and F-019 rows closed by their own
conditions with evidence.
Evidence plan: both curls pasted · the deploy script's printed resolution line
· the two ledger rows' closing evidence · the InferenceService YAML committed.
Safe stopping point: endpoint serving with parity UNPROVEN — say so out loud
in the handoff; do not let a spot check masquerade as the 1e-6 gate.

### M5-S3 — THE parity test, 1e-6  (role:MLE)

`make parity`: N rows chosen to span the honest hazards — ordinary trips,
unseen/fallback OD pairs (the 1.48% where models earn their keep), airport
zones, a boundary-duration trip — built through the ONE `features/` transform
path, scored twice: the locally-loaded champion vs the live endpoint. Assert
`max |Δ| ≤ 1e-6` and PRINT the measured max (a bar passed silently teaches
nothing; the expected value is float-noise, ~1e-7). The script is a READER —
no deploy, no registry mutation, pinned the way `flyte_run_actions.py` is.
`make parity-redteam` proves the test can fail without touching the served
model: score the request rows with a permuted column order, or compare the
endpoint against version 1 loaded locally — either must go RED naming the
cause, exit inverted like every red team since `marts-redteam`.
Accept when: parity GREEN with the measured delta printed · red team RED for
the planted cause and GREEN after · both runnable by S5's gate without
modification.
Evidence plan: both transcripts; the delta number quoted in the handoff.
Safe stopping point: parity known — the single most load-bearing serving fact;
train/serve skew is now measured, not assumed.

### M5-S4 — p95 measured + self-heal under load  (role:SRE)

A committed load client (uv script; check whether stdlib/httpx already in the
graph suffices before adding ANY dependency — gotcha #36's check at add time
if one is truly needed) drives the declared route at a STATED request rate for
a STATED window; p95/p99 recorded with the load shape beside them — an
unqualified latency is not a measurement. Then the self-heal leg: kill the
predictor pod mid-load (the M4-S5 kill-drill shape — assert IDENTITY, a
different pod uid, never a name), measure the error window, and show the
endpoint back to green under the same load. Sanity-check requests/limits
against observed usage for the PRR's capacity box. Records land as JSONs under
`automation/runs/m5-load/` — tracked, under S1's new regime. **This story's
verification outlives an attended wait: run the load+kill sequence detached
(`automation/run_detached.sh`, ritual e) and let it schedule the successor —
never end the turn waiting on it (gotcha #45).**
Accept when: p95/p99 recorded with rate+window+concurrency stated · the kill
shows a different pod uid serving afterwards, a measured error window, and
recovery under sustained load · the records are tracked files.
Evidence plan: the load JSON · the kill transcript · a deployments-ledger row
carrying the numbers.
Safe stopping point: the PRR's capacity and resilience inputs exist.

### M5-S5 — The PRR, the M5 gate, and its red team  (role:SRE A; MLOps R)

Write `docs/runbooks/serving.md`: start/stop/deploy/**rollback typed** — the
exact commands that put version 1 back on the wire (the registry holds it for
exactly this), and an honest statement of what is NOT rehearsed (the M4-S2
backup precedent: an unrehearsed path says so in every artifact). Then the
**Production Readiness Review**, minuted per BLUEPRINT §9/M5: SRE walks the
written checklist — runbook exists · rollback typed · alerts PLANNED (M6
implements them; a plan with named signals is a real artifact, a vague
intention is not) · capacity sanity from S4's numbers — **every box carrying
pasted evidence**, and the F-019 policy's SRE reasoning minuted here (S2's
cross-reference). Deployments ledger gains the serving row. Then
`make verify-m5` + `make verify-m5-redteam`, built under the inherited laws:
re-runs nothing expensive and mints nothing it counts (M4's rule), no skip
flag, no fast mode (M1's rule, fifth inheritance) · every literal DERIVED on
both sides (F-017, gotchas #49/#50 — no pinned version numbers, run ids, or
image tags; the served version must equal what the ALIAS says, never "2") ·
recorded evidence read from the tracked records (gotcha #66's lesson) · Python
legs guarded by `expect_verdicts` (M2's rule) · the red team breaks a POINTER
or one recorded field, restores byte-identically under an EXIT trap, and the
gate must go RED naming it while the untampered sub-checks still pass.
Accept when: `verify-m5` GREEN with its section/sub-check count stated ·
red team RED for the planted cause, GREEN after restore · PRR minutes
committed with every box evidenced · deployments ledger row exists · §9/M5's
accept-when quoted and green line by line ("v1's M4 gate AND the PRR minutes
exist with every box carrying pasted evidence").
Evidence plan: both gate transcripts · the minutes · the ledger row · parity
output re-shown by the gate (the §9 "Show:" artifact).
Exit: `automation/next_session.sh architect 120`.

## Out of scope (named now so creep is visible later)

- **Canary, shadow, SLO document, gameday, alert IMPLEMENTATION — all M6.**
  The prior-art ADOPT stands: `canaryTrafficPercent` requires Serverless mode;
  ADR-004's timeboxed spike (Knative profile vs two-isvc split) runs at the
  **M6 boundary**, not here — note ADR-004's text predates the M0–M9 renumber
  (its "M4/M5" read "M5/M6" today; its pre-approved cost "serving gets
  re-deployed once" is M6's to spend).
- **Any `@champion` move** (law 2; F-016 is the PO's).
- **Registry pattern & Flyte's declared 8080 route** — the next PO-sanctioned
  rebuild, unchanged.
- **Drift/retrain (M7) · Feast (M8) · the demo page (M9** — "never on the M5
  acceptance path; serving must prove itself in the terminal before it earns a
  face"**)**.
- **Batch prediction refresh** — nothing in M5 re-scores the months; the
  predictions tree and marts stand as published.

## Risks & walls (carried counts restated; fallbacks cite ADRs)

| Risk / wall | Count | Fallback |
|---|---|---|
| KServe (version read live at S1) vs k8s v1.36 compatibility unknown until installed | 3-attempt wall | Fallback pre-approved in kind by ADR-004's own cost line: a plain mlserver Deployment+Service behind the SAME ingress, recorded as a dated decision note. Parity (S3), load (S4) and the PRR (S5) test the WIRE, not the operator — they survive the fallback unchanged. M6's canary surface is affected either way (Standard has none; that is M6's spike). |
| The upstream kind ingress manifest's `ingress-ready=true` nodeSelector will not schedule — the label is absent from our nodes, and the 8081→80 mapping exists ONLY on the control-plane node | precondition table, checked | Pin scheduling with `kubernetes.io/hostname: mlops-taxi-control-plane` (derived from the kind config's cluster name, not typed — gotcha #52) or apply the label idempotently from the deploy script. A controller scheduled on a worker answers nothing and LOOKS like a KServe failure — check `kubectl get pods -o wide` before debugging anything else (the gotcha #34 lesson: cheap causes first). |
| Large image pulls stall `--wait` and read as install failure | measured once (9m49s, M4-S2) | Waits sized from the measurement, never shrunk to make a demo pass; detach anything that could outlive the session (ritual e). |
| F-009's impostor: missing MinIO creds prints an artifact-shaped error | gotcha #39, recorded | The one-call discriminator FIRST (`get_model_info` succeeds under F-009, everything fails under missing creds), before any debugging of the model itself. |
| A 2026-dated smoke request 500s before S2's F-019 decision lands | tripwire test pins it | Sequence inside S2: decide F-019 before the first non-2019 curl, or expect the pinned `ValueError` and treat it as the tripwire firing, not a new defect. |
| gotcha #66 if any M5 story runs the pipeline after a commit | 1 (M4-S5 leg 2) | Nothing in M5 needs a pipeline run. If one is ever warranted, the first run after any commit under `src`/`scripts`/`analytics`/`docker`/`pyproject.toml`/`uv.lock` is a 31-minute re-fit, not an 11-second rerun — plan it detached or don't plan it. |
| Split horizon (ONE MinIO, two names) resurfacing in serving | F-023/F-025, both closed | The pod uses the in-cluster name (pods resolve it; M4 proved it), host-side clients use the localhost route. No host-side client uploads anything in M5, so the `stowConfigOverride` shape cannot recur. |
| WSL memory pressure with cert-manager + KServe + a predictor beside 5 tenants | `free -h` 47Gi observed M0 | Small controllers; the predictor is one mlserver pod. If scheduling pressure appears, read `kubectl describe node` BEFORE touching any limit (evidence before state changes). |

## Open PO questions (options · recommendation · default-with-date)

**None new.** Standing, all non-blocking: **2026-08-18-1** (F-016 incumbent
margin — blocking only at M7's first retrain; if unanswered by the M6→M7
boundary, M7 proceeds with the gate as pre-registered) · **2026-08-17-1** (host
`libgomp1` one-liner) · **2026-08-16-2** (allowlist paste). The chain
continues; nothing parks.

## ARCH self-check (v3.0)

model stated Fable: **yes, first line** · every story sized for one short
executor session: **yes — S1 is the densest (two halves, each with its own
safe stop named); S4 names its detached exit up front (ritual e)** · debt
intake diffed against ledgers/debt.md: **yes — register fully closed, stated
in the table rather than omitted; finding intake (F-029→S1, F-019/F-009→S2)
replaces it** · forks routed to AWAITING_PO: **none new; F-016 stands parked;
F-029 and F-022 were ARCH calls, made and recorded this session** · every
carried finding restated with quoted landing: **F-020→M7, F-022→M7 (both
quoted in §0)** · gates loosened: **none — verify-m5 inherits every
predecessor law and the serving stories add checks, remove none**.
