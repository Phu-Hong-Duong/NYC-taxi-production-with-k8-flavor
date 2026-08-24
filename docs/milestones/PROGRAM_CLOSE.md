# PROGRAM CLOSE — Crosstown ETA & Reliability (authored by: ARCH/Fable · 2026-08-24)

Session model stated: **Fable 5 (claude-fable-5)** — architect sessions on any
other model are void (ORG.md rule 7).

**M9 is the last milestone in BLUEPRINT §9, so this boundary closes the
PROGRAM, not the next milestone.** There is no M10 kickoff; this document is
what stands where one would. Its jobs are the boundary's three, with the second
transformed: (0) triage and close M9 · (1) the program-close sweep — every gate
this program ever built, run live, this session · (2) the honest close: what
is done, what remains, and with whom · (3) park the chain deliberately.

## 0. Boundary triage of M9 (the closure sweep)

**Verify re-run (by the approver, this session, 2026-08-24):** `make verify-m9`
→ **GREEN — 45 sub-checks across 7 sections, exit 0.** Closing line verbatim:
`[verify-m9] GREEN — every M9 sub-check passed.` — with the banner printing its
own open item: `OPEN BY DESIGN: §9/M9 asks for one non-technical person to
complete a query unassisted, OBSERVED. No unattended session can close that
box; it waits at AWAITING_PO and this gate only ever checks that it is recorded
honestly.` That banner is the gate working as chartered, not a caveat added
here.

**Lineage spot-check (gotcha #20):** `git branch -r --contains bf2d553`
(M9-S4's story commit, PR #64) → `origin/main`. M9 landed as PRs **#61–#64**
(S1 demo page · S2 store watchdog · S3 two closures · S4 the gate).

**Red team:** `make verify-m9-redteam` PASSED at M9-S4 (planted
`expected_keys.total` 57,688 → 57,425 — short by exactly `zone_static`'s 263
keys, a correct-looking expectation of the wrong population — RED exit 1 with
3 FAILs from three artifacts, 42 sub-check lines still passing, sha256 restore
`b875049f8289…`, GREEN 45/45).

**Reconciliation at boot:** 3/3 nodes Ready v1.36.1 at 7d3h · tree clean at
`b0652b8` · no `automation/STOP` · both InferenceServices, the feature server,
Redis (57,688 keys) and the demo page live · `free -h` 39Gi (the PO's 40 GB
re-grant of 2026-08-22 — CLAUDE.md and gotcha #2 amended with dated notes in
this commit; the platform runs whole inside it).

**Dispositions — every open finding, condition, and standing item, none
silent:**
- **F-062** (a dead online store is billed to the CALLER as a 4xx; SLO-R1's
  error budget cannot see it) → **PO FORK, AWAITING_PO 2026-08-24-2.** The
  M9-S2 row routed it "to the program close"; the close's honest answer is
  that it cannot land here — options (b) and (c) both change what a live
  boundary returns or how its SLO accounts, which is the edit class this
  program only ever makes on a PO's word, and no executor session follows this
  one. Options and recommendation (b) restated verbatim in the entry. The
  ledger row stays OPEN — a program that closes over a row it quietly dropped
  is worse than one that closes with an open row, and `verify-m9` enforces
  exactly that.
- **The PO-observed demo run** (§9/M9's last accept line) → **OPEN, standing
  at AWAITING_PO 2026-08-23-3.** Two of the three §9/M9 accept clauses are
  closed by machine evidence; the third names a human by design. The program
  is **complete on every term a machine can verify, and unfinished on the one
  term only the PO can close** — both halves stated, neither blurred into the
  other.
- **F-065 (NEW, raised + CLOSED this triage):** the program-close sweep ran
  `make verify-m2` for the first time since M4-S1 and it was **RED** — its §9
  root-stray allowlist predates M8-S2's `.venv-feast`, so the gate had been
  red-on-run over a correct clone since 2026-08-21 with nothing knowing,
  because nothing re-runs a closed milestone's gate until a boundary sweeps
  it. Gotcha #50's shape. Fixed with one `EXPECTED` entry carrying its dated
  reason (the check's design — distrust gitignore, name what belongs — is
  untouched); `make verify-m2` **GREEN 55/55**, gate tests 15 passed, host
  suite 1151 passed. Landed by ARCH at the boundary (the F-029-mechanics /
  gotcha-#26 precedent); the alternative — one more executor session for one
  line — was priced and declined. Full row: `ledgers/findings.md` F-065.
- **F-016** (incumbent-margin gate fork) → **standing at AWAITING_PO
  2026-08-18-1, now doubly-informed** (moved the pointer on +0.63%, held it on
  −0.03%). Dormant at close: nothing fits and no alias moves unless the PO
  reactivates the retrain or opts into new work.
- **The stretch opt-in menu** (Ray/KubeRay · CI nightly · trivy+secret-scan ·
  README polish) → **standing at AWAITING_PO 2026-08-23-2.** Any opt-in gets
  chartered as M9-S5+ by an ARCH touch; §4 below says how the chain resumes.
- **Publish the repo publicly** (BLUEPRINT §12's queued question) → **formally
  with the PO as of this close** (AWAITING_PO 2026-08-24-2). The honest
  pairing: menu items 1–2 (README polish, trivy + secret-scan) are the
  recommended pre-publish steps if the answer is yes.
- **Error memo §7 row 2** (the airport gap, 1.86–2.35× across three
  independent measurements) → **documented future work.** The named candidate
  reader is `airport_regime_flag` (M8-S2's catalog, catalog-only, argued as a
  regime indicator not a distance proxy). Nothing fits at close; the row and
  its measurements stay where a future reader will look.
- **AWAITING_PO 2026-08-17-1** (host `libgomp1` one-liner) and **2026-08-16-2**
  (allowlist paste) → standing, non-blocking, unchanged — friction reports
  whose fixes are the PO's hands by constitution.
- **D-001's registry-pattern deferral** → stands as written (trigger: image
  churn; landing: the next PO-sanctioned rebuild). With the program closed,
  that landing arrives only if the PO ever rebuilds — recorded so the deferral
  reads as conditional, not forgotten.

**Debt register: CLOSED** — D-001…D-004 all carry closing evidence; nothing
due, nothing carried to nowhere.

**README Status row flipped** (M9 → closed; program-close row added) in the
same commit as this document. **Verdict: M9 CLEANLY CLOSED — tagged
`m9-closed`.**

## 1. The program-close sweep — all ten gates, one session, pasted

The M9-S4 handoff invited the close to "run all ten as ten commands." Done,
2026-08-24, in order, on the live cluster:

| Gate | Verdict this session |
|---|---|
| `make verify-m0` | GREEN (closing line: `[verify-m0] GREEN — every M0 sub-check passed.`) |
| `make verify-m1` | GREEN — incl. the rebuild-proof leg re-deriving ~1 GB byte-identically |
| `make verify-m2` | **RED on first run → F-065 → GREEN 55/55 after a one-line allowlist repair** |
| `make verify-m3` | GREEN |
| `make verify-m4` | GREEN |
| `make verify-m5` | GREEN — incl. the live prediction reproducing the parity row at 0.000e+00 |
| `make verify-m6` | GREEN |
| `make verify-m7` | GREEN |
| `make verify-m8` | GREEN — incl. F-064's repaired key-count comparison, live |
| `make verify-m9` | GREEN 45/45, OPEN ITEM printed in the banner |

The sweep's one finding (F-065) is the argument for the sweep: a named
allowlist in a long-lived verifier is a twin of every later milestone's
legislation, and nothing forces the reconciliation until someone runs the old
gate. Ten-for-ten green **after** the repair is the close's claim; the RED that
preceded it is part of the record, not an embarrassment to it.

## 2. What the program is at close (the inventory a returning reader needs)

- **Serving:** `@champion` = registry version **2** (`auto-lgbm-v2`, feature
  set v2, 24 features), on the wire through KServe RawDeployment, parity
  offline-vs-online **0.000e+00** over 16 declared hazards. Versions
  `['1','2']`; not one created after `m7-closed`; `uv.lock` byte-identical to
  `m7-closed`.
- **The moved boundary:** the transformer answers four RAW fields beside the
  champion's 24-column wire (~18 ms at p50), backed by the Feast online store
  (Redis, 57,688 keys, `noeviction`) and the quarantined feature server. The
  champion's wire remains the wire of record — no cutover was ever made, by
  law.
- **The face:** `http://localhost:8081/demo/` — same-origin, CORS dissolved by
  construction, refusals rendered as refusals. The §9/M9 observed-run box is
  the one thing on it a machine cannot close.
- **Eyes and judgement:** Prometheus + Alertmanager + Grafana; **16 alert
  rules across 10 signal ids**, every threshold argued in
  `docs/slo_serving.md` beside the rule that carries it; the drift surface
  persistent and watched (A-11), the online store watched (A-12a/b, A-13).
- **The loop:** ingest → contract → marts → train → gate → serve → monitor →
  drift → retrain, all on-cluster (Flyte), all cached, all rehearsed against
  kills, restores and gamedays. The retrain trigger is registered and
  **inactive** (a PO compute decision); the one scheduled-shape retrain ran,
  measured, and was correctly **REFUSED** at −0.03%.
- **Verification:** ten milestone gates, each with a red team proven able to
  go RED and restore byte-identically; **1,204 host tests**; every tracked
  drill record reviewable in git (F-029 option A paying out through F-063,
  F-064 and this close's F-065).
- **Data:** 2019 settled (56.1M clean rows), 2020 scoring months settled
  (15.4M scored), five DVC pins `up to date`, raw manifest sha256-pinned.

## 3. What remains, and with whom (all of it the PO's, none of it the chain's)

1. **The observed demo run** — AWAITING_PO 2026-08-23-3. Closes §9/M9's last
   accept line. Five minutes.
2. **F-062** — AWAITING_PO 2026-08-24-2. A genuine fork on a live boundary's
   refusal classes; recommendation (b).
3. **The stretch menu** — AWAITING_PO 2026-08-23-2. Opt-in only.
4. **Publish the repo** — AWAITING_PO 2026-08-24-2. Queued since §12.
5. **F-016** — AWAITING_PO 2026-08-18-1. Dormant until anything fits again.
6. **Two friction pastes** — 2026-08-17-1, 2026-08-16-2. Whenever convenient.

## 4. How the chain resumes, if it ever does

The chain is **PARKED deliberately at this close** — no successor is
scheduled, because every remaining item needs the PO's hands or word, and a
park with its AWAITING_PO entry is how the watchdog tells a decision from a
crash. To resume on any PO answer:

```bash
cd ~/NYC-taxi-production-with-k8-flavor
automation/next_session.sh architect 120   # an ARCH touch charters the work first — never an executor improvising
```

(If the machine restarted: Docker Desktop first — gotcha #34 — then
`make cluster-up` no-ops if the cluster survived.)

## 5. Out of scope, permanently unless the PO reopens

Any alias move · any fit · any registry version · any cluster rebuild · any
new Flyte trigger · the transformer cutover · R-1 (FeatureService, declined
with reason at the M8 boundary) · the daily drift window (named at F-046,
needs its own 2019 headroom leg first).
