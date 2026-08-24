# M9 EPILOGUE KICKOFF — the answered close inbox (authored by: ARCH/Fable · 2026-08-24)

Session model stated: **Fable 5 (claude-fable-5)** — architect sessions on any
other model are void (ORG.md rule 7).

**Why this document exists when `PROGRAM_CLOSE.md` says "there is no M10
kickoff".** The close parked the chain because everything remaining needed the
PO's hands or word — and on 2026-08-24 the PO answered **all seven items**
(AWAITING_PO 2026-08-24-2, decisions recorded verbatim). Three of those answers
are chartered work: the observed-demo box closed and must land in the record
(answer 1), **F-062 option (b)** touches a live boundary (answer 2), and the
pre-publish pair precedes a public flip (answer 3), with **F-016 option B** a
PO-sanctioned gate edit (answer 5). The close document itself legislated this
path: *"any opt-in gets chartered as M9-S5+ by an ARCH touch."* This is that
charter. It is an EPILOGUE, not a new milestone: no new platform capability, no
fit, no alias move, no version — it lands the PO's answers and stops.

## 0. Boundary triage of the post-close state (nothing carried silently)

**Verify re-run (by the approver, this session, 2026-08-24):** `make verify-m9`
→ **GREEN — every M9 sub-check passed** (45 sub-checks across 7 sections),
closing banner still printing its open item verbatim: `OPEN BY DESIGN: §9/M9
asks for one non-technical person to complete a query unassisted, OBSERVED.`
That banner is now STALE-BY-EVENT rather than wrong: the observed run HAPPENED
(2026-08-24, PO's words recorded verbatim in AWAITING_PO 2026-08-23-3) and the
record has not yet been flipped — which is exactly M9-S5's job, chartered
rather than hand-flipped here because the flip alone would turn the gate RED
(its §2 leg and three tests pin the OPEN state; the honest unit of change is
record + gate + tests together, one executor session — gotcha #50's discipline,
not F-065's one-line exception).

**Lineage spot-check (gotcha #20):** tag `m9-closed` is reachable from
`origin/main` (`git merge-base --is-ancestor m9-closed origin/main` → yes);
close commit `c129a2a` on `origin/main`. Tree clean at `69ff424`,
`main == origin/main`. Cluster 3/3 nodes Ready v1.36.1 at 7d5h.

**Post-close events since the tag, all already dispositioned:**
- **F-066 (watchdog park latch)** — raised AND closed by the post-close session
  it started (PR #65, merge `261677b`); a park now latches and
  `automation/next_session.sh` is the only eraser. Nothing about the closed
  program moved. No action here; this session's own scheduling exercises the fix.
- **The PO's seven answers (AWAITING_PO 2026-08-24-2)**, dispositioned one by one:
  1. **Observed demo run — DONE 2026-08-24**, verbatim note in 2026-08-23-3
     ("This is okay, I get the gist of it…"), no legibility finding filed →
     **chartered as M9-S5** (flip the record, re-derive the gate).
  2. **F-062 → option (b)** — PO-sanctioned wire change → **chartered as M9-S7**.
     Ledger row stays OPEN until it lands.
  3. **Publish the repo → YES after the pre-publish pair** → **chartered as
     M9-S8 (README) and M9-S9 (trivy + secret-scan)**; the public flip itself is
     the PO's click and is OUT OF SCOPE for the chain.
  4. **Stretch beyond the pair → NONE** — CI-nightly-on-kind and Ray/KubeRay
     DECLINED by the PO with this program's own cost arguments. Closed; not
     carried, not parked.
  5. **F-016 → option B** (incumbent KPI-09 margin ≥0.50%, KPI-10 non-regression
     unchanged) — a PO-sanctioned gate edit → **chartered as M9-S6**. Ledger row
     stays OPEN until it lands.
  6. **libgomp1 → option A, applied and verified by the PO** (`openmp_status()
     -> (True, 'system libgomp.so.1')` on the host). No story: the shim stays in
     the code as the fresh-clone path by design (D-004's closure already covers
     the container; AWAITING_PO 2026-08-17-1 carries the applied note).
  7. **Allowlist → option A, applied by the PO's own paste** (commit `a55801c`,
     58 entries). No story; in effect for this and every next session (observed
     this session: one expansion-guard refusal remains — the paste widened
     verbs, not syntax, exactly as the 2026-08-16-2 EXEC note predicted).
- **F-065** — closed at the close itself (verify-m2 allowlist repair, GREEN
  55/55). No action.

**Debt intake:** the register is **CLOSED** — D-001…D-004 all carry closing
evidence, nothing due, nothing lands here. (D-001's registry-pattern deferral
stands as a conditional on a PO-sanctioned rebuild that may never come;
restated so it reads as conditional, not forgotten.)

**Standing items that remain OPEN on purpose and are NOT this epilogue's:**
error memo §7 row 2 (the airport gap — documented future work, named reader
`airport_regime_flag`, catalog-only) · the daily drift window (F-046's residual;
needs its own 2019 daily headroom leg first) · R-1 (FeatureService, DECLINED
with reason at the M8 boundary) · the retrain trigger's activation (a PO
compute decision, dormant).

**Verdict: the close STANDS (tag `m9-closed`, ten gates GREEN).** This epilogue
opens no gate retroactively; it lands five PO-answered stories and closes with
its own boundary triage, tag **`m9-epilogue-closed`**, and a re-park whose
AWAITING_PO entry hands the PO the publish flip.

## Preconditions (verified LIVE at draft time — pastes, not memory)

- `make verify-m9` → `[verify-m9] GREEN — every M9 sub-check passed.` (this
  session, output in §0).
- `kubectl get nodes` → 3/3 `Ready` v1.36.1 (7d5h) — cluster up, stateful law
  intact.
- `git status` → clean; `main...origin/main` in sync at `69ff424`.
- `git merge-base --is-ancestor m9-closed origin/main` → yes.
- `@champion` → version **2** / `feature_set v2` (asserted inside the verify-m9
  run above: "NOT ONE of the 2 registry versions was created after the
  m7-closed tag"; `uv.lock` byte-identical to `m7-closed`; all 5 DVC pins up to
  date).

## Stories (5; each independently finishable, safe stopping point after each; run in order)

### M9-S5 — The answered box lands in the record (role:MLOps)
The PO completed the observed demo run on 2026-08-24 and AWAITING_PO
2026-08-23-3 carries their words verbatim. The record and the gate still say
OPEN. Land the flip as one coherent unit — record + gate + tests — because any
half of it alone is a RED gate or a silent green (gotcha #50 both ways).

- Flip `automation/runs/m9-demo/accept.json` `po_observed_run` → status
  **CLOSED**, citing the AWAITING_PO entry id (2026-08-23-3), the date
  (2026-08-24), and the PO's note **quoted, not paraphrased** ("This is okay, I
  get the gist of it. Improvement can be done later."). Keep the original
  `box`/`url` fields; add, never replace.
- Re-derive `scripts/verify_m9.sh` §2's box leg to the two-state PROPERTY: the
  box is either **OPEN and honest** (record says OPEN, AWAITING_PO carries the
  live invitation, the two agree — the pre-flip state) or **CLOSED and cited**
  (record says CLOSED, names an AWAITING_PO entry that exists and contains the
  quoted note). A CLOSED status with **no citation, or a citation the inbox
  does not hold, is RED** — that is the check that stops this box from ever
  being rounded up. The GREEN banner drops the OPEN-ITEM paragraph and instead
  prints one line citing the closure.
- Update `tests/unit/test_verify_m9.py`'s three box assertions to the same
  property (the "never rendered green" pin becomes "never rendered green
  WITHOUT a citation").
- README: the PROGRAM CLOSE row's "one box open by design" gets its dated
  update; `docs/milestones/PROGRAM_CLOSE.md` §0/§3 get a **dated note beside
  the original** (never a rewrite — the M4-S2 ledger precedent).

**Accept when:** `make verify-m9` GREEN with the box shown CLOSED citing
2026-08-23-3; the unit tests pin CLOSED-must-cite and go RED on a citation-free
CLOSED (demonstrate once in the story, restore); README + PROGRAM_CLOSE carry
dated notes. **Evidence plan:** the accept.json diff, the gate transcript, the
test run.

### M9-S6 — F-016 option B: the incumbent transition margin (role:MLE)
The PO chose **B** (AWAITING_PO 2026-08-18-1, answered 2026-08-24): incumbent
KPI-09 margin **≥0.50%** — DR-02's own smallest pre-registered materiality
bar — with KPI-10 non-regression unchanged. This is the one edit class gates
ever accept: a PO fork, now sanctioned in writing.

- The margin lands in `configs/train.yaml: gate` (F-013: one home for gate
  knobs), with a comment that re-argues it citing the answered entry and BOTH
  observations the decision was made against (+0.63% moved the pointer at
  M3-S5; −0.03% held it at M7-S4) and the accepted cost verbatim: *a model
  genuinely 0.3–0.4% better will not ship.*
- `gate.decide` applies it to the incumbent condition only; the floor condition
  (2.00%) and the KPI-10 conditions are untouched. Unit tests both directions:
  a +0.3% challenger REFUSED naming the margin; a +0.63% challenger PROMOTED.
- **THE WALL, checked BEFORE the edit lands** (this kickoff has done the
  arithmetic; the story must re-verify it live): `verify-m2` §2, `verify-m3` §5
  and `verify-m7`'s retrain leg all REPLAY recorded verdicts through
  `gate.decide` **as it exists on disk**. Under B: M2's transcripts carry no
  incumbent (alias was unset — nothing to consult), M3-S5's promotion at
  **+0.63% ≥ 0.50%** still PROMOTES, M7-S4's **−0.03%** still REFUSES. So all
  replays should stay green. **If any replay flips, STOP — that is a finding
  and a PO question, never an edit to the replay** (gotcha #50; the replays
  exist precisely to catch a loosened gate, and they must be equally loud about
  a tightened one).
- Ledger F-016 → CLOSED with the config diff and the replay evidence;
  AWAITING_PO 2026-08-18-1 gets the landed note.

**Accept when:** `make verify-m2` (55/55), `make verify-m3` (46/46),
`make verify-m7` (62/62) all GREEN after the edit; the two new direction tests
green; no fit, no alias read-write beyond what the gates already do (the story
moves NOTHING — it changes what a future promotion must clear). **Evidence
plan:** the config diff, the three gate transcripts, the test run.

### M9-S7 — F-062 option (b): a dead store stops billing the caller (role:SRE, MLE hat on the client)
The PO chose **(b)**: `calendar_from_store` distinguishes *this date is not
covered* (422, F-019's case) from *the store answered nothing for any date*
(503, ours), with the accepted cost eyes-open — one transformer redeploy, the
parity records re-measured, gates re-run. This is the epilogue's only wire
change and the reason it is chartered rather than improvised.

- **The design hazard, named so it is not rediscovered at minute forty:** for
  the REQUESTED date, an empty store and an uncovered date return the same
  bytes (null calendar features). The discriminator must ask a question whose
  answer differs — e.g. on a null answer, probe one **sentinel date the
  committed table provably covers** (derive it from the holiday table's own
  horizon, never type it): sentinel answers → the store is alive and the
  requested date is genuinely uncovered → **422**; sentinel also null → the
  store has no calendar at all → **503 `FeatureStoreUnavailable`**. The probe
  runs only on the failure path, so the happy path's latency (~18 ms at p50) is
  untouched. Executor may find a cleaner discriminator; whatever lands, RECORD
  the argument beside the code.
- Rebuild + redeploy the transformer (the F-026 guard will fire on this
  commit — rebuild, never narrow; gotcha #66's cold cache is priced and
  irrelevant, no pipeline run is chartered).
- **Re-measure the parity records the F-062 row names** (`transformer-parity`,
  `server-parity`, `online_parity`) at their committed bars — all EXACT. The
  fix touches only the error path; **the happy-path numbers must come back
  bit-identical (0.000e+00). Any nonzero delta is a story-stopping finding**,
  not a bar to widen.
- **Re-run `make store-watch-drill` with a NEW prediction committed FIRST**
  (law 4, tenth inheritance) predicting **503** for the empty phase. Keep the
  422-era records as a dated attempt directory
  (`automation/runs/m9-store-watch/attempt1-422-era/` — the program keeps
  superseded evidence visible; F-063/gotcha #48: never let a re-run silently
  rewrite records other documents cite).
- Re-derive `verify_m9.sh`'s empty-store leg to the property (the drill
  record's rider status equals its own committed prediction) rather than the
  literal 422 — gotcha #50, this kickoff's third naming of it.
- Docs: `docs/slo_serving.md` SLO-R1/§9 gains the dated correction — a
  store-dead 503 now SPENDS SLO-A1's availability budget, which is the entire
  point of (b); `docs/store_watchdog_m9.md` §4/§6 get dated notes beside the
  originals. Ledger F-062 → CLOSED.

**Accept when:** the discriminator is recorded with its argument; the empty
phase of the drill measures **503** against a prediction committed before the
run (checkable from git); the unreachable phase still measures 503; the 2031
uncovered-date quote still measures **422** (F-019's guarantee survived —
assert it explicitly, it is the regression this change could cause); all three
parity records re-measured at 0.000e+00; `make verify-m5`, `make verify-m8`,
`make verify-m9` GREEN. **Evidence plan:** new drill + parity records tracked;
the attempt directory; the three gate transcripts.

### M9-S8 — README as the portfolio front door (role:MLOps, DA hat for legibility)
Pre-publish pair, item 1 (PO answer 3). One doc session; no code, no wire.

- Rewrite the README top for a PUBLIC reader who has never seen this repo: what
  it is (an enterprise-simulated MLOps program on a laptop kind cluster), the
  loop in one diagram/paragraph (ingest → contract → marts → train → gate →
  serve → monitor → drift → retrain), the headline numbers WITH their records
  (parity 0.000e+00 · ten gates GREEN · 1,204 host tests · 16 alert rules /
  10 signal ids · the −0.03% refusal), how to run it (the honest requirements:
  WSL2/Docker/48h of pulls), and the honest limits (single laptop, $0, one
  observed-run box closed by a human, same-disk backups).
- The Status table and its history are PRESERVED — append-only discipline; the
  front door gains an audience, it does not lose its ledger.
- Every `make` target the README names must exist in the Makefile and every
  number must cite the record that holds it (the verify-m5 runbook idiom; a
  light test is welcome but not owed).

**Accept when:** README reads start-to-finish for an outsider; targets and
numbers check against Makefile and records; Status table intact; `make
verify-m9` still GREEN (no code moved). **Evidence plan:** the diff; a
transcript of the target/number check.

### M9-S9 — trivy + commit-history secret scan (role:SRE)
Pre-publish pair, item 2 (PO answer 3). The M1 prior-art ADOPT (commit-time
secret scanning) finally lands in audit form. Honest note carried from the
menu: `.env` never entered git by design, so this VERIFIES hygiene rather than
creates it — and a verification that finds nothing must still prove it looked
(gotcha #59: assert on the positive artifact, here the scan record with its
inputs enumerated).

- Pin **trivy** and a secret scanner (**gitleaks** recommended; executor probes
  first — the `DRILL_STAGE` idiom) as versioned binaries into `~/.local/bin`
  with sha256s recorded (the kind/helm precedent). Network fetches: gotcha #9
  (Kaspersky TLS) is the first suspect on any failure.
- Scan: the three OUR images (`taxi-mlops-pipeline`, `taxi-mlops-feast-server`,
  the derived predictor image) · the repo filesystem · the FULL git history for
  secrets. Records as tracked JSON under `automation/runs/m9-security/`.
- Triage honestly: **secrets anywhere = story-stopping, park at AWAITING_PO**
  (expected: zero). Base-image CVEs are RECORDED with counts and severities,
  not chased — this is a $0 program with every image pinned by digest; an
  upgrade campaign is out of scope and saying so with the numbers beside it is
  the honest close (the same shape as `nvidia-nccl-cu13`: noted, not fought).
- Exit: write the AWAITING_PO entry telling the PO the pre-publish pair is
  DONE, with the scan verdicts quoted, and that **the public flip is their
  click** (answer 3's own terms).

**Accept when:** pinned-tool versions + sha256s recorded; scan records
committed covering images + tree + full history; zero secrets (or a parked
finding); the AWAITING_PO handover entry written. **Evidence plan:** the
records; the entry.

## Out of scope (named now so creep is visible later)

The public flip itself (the PO's click) · CI-nightly-on-kind and Ray/KubeRay
(PO DECLINED, answer 4) · any fit, any alias move, any registry version (S6
changes what a FUTURE promotion must clear; it moves nothing) · the transformer
cutover · any cluster rebuild · any new Flyte trigger (F-058) · the daily drift
window (F-046 residual) · R-1 · base-image upgrade campaigns (S9 records, does
not chase) · error memo §7 row 2 (documented future work).

## Risks & walls (fallbacks cite laws/ADRs)

1. **S6's replay wall.** Three gates replay history through `gate.decide` on
   disk. The arithmetic says B keeps every recorded verdict (+0.63% ≥ 0.50%;
   −0.03% < 0); if a replay disagrees, the story STOPS and the discrepancy goes
   to the PO — a replay leg is never edited to admit a gate change (that is the
   exact tamper the red teams simulate).
2. **S7's discriminator.** If empty-vs-uncovered cannot be distinguished
   cleanly on the client (the sentinel-probe design fails or costs the happy
   path), do NOT silently fall back to option (c) — the PO chose (b). Park at
   AWAITING_PO with the measurement. 3-attempt wall applies to the deploy legs
   as everywhere.
3. **S7's parity bars are EXACT and stay EXACT.** A nonzero delta after an
   error-path-only change means something else moved — finding, not tolerance.
4. **Gotcha #50, standing hazard of this whole epilogue:** S5 and S7 both
   change what a gate asserts about a correct system. Every such edit is a
   RE-DERIVATION to the property that holds at every state, demonstrated able
   to go RED, never a widened literal.
5. **Session lifecycle (gotcha #45):** nothing here needs a detached run — the
   longest single leg is S7's drill (~9 min foreground). If an executor finds
   otherwise, `automation/run_detached.sh` with `--then-schedule executor` is
   the exit path, per ritual (e).

## Open PO questions

None new. The chain's next ask of the PO is S9's exit entry (the publish
flip). Standing: none — the inbox is fully answered as of `69ff424`.

## Exit (the epilogue boundary)

After S9: an ARCH touch re-runs the affected gates, closes the epilogue with
tag **`m9-epilogue-closed`**, flips the README row, and RE-PARKS the chain with
the publish-flip entry as the standing item. The park will latch (F-066) and
`automation/next_session.sh` remains the one eraser.

## ARCH self-check (v3.0)

- Every story sized for one fresh executor session: yes (S7 is the largest at
  ~an image build + a 9-min drill + three seconds-to-minutes parity readers).
- Every accept-when observable by machine or explicitly named as human: yes
  (none human — the one human box closed and S5 lands its record).
- Debt intake: register closed, nothing due — stated in §0.
- No story loosens a gate except by the PO's recorded word: S6 cites the
  answered fork verbatim; nothing else touches a bar.
- Safe stopping point after each story: yes — each leaves every gate GREEN and
  the wire either untouched (S5, S6, S8, S9) or redeployed-and-re-measured (S7).
