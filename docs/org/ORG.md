# The Organization — Crosstown Mobility, ETA & Reliability Program

v1 (2026-08-12). This document answers "who does what, and who can say no."
Adapted from the principal's predecessor program (Ashford Lending, read 2026-08-12)
with the assurance geometry translated from bank-shaped (SR 11-7) to
platform-shaped (Google-SRE): same separation principle — builder ≠ challenger ≠
assurer — in the industry-correct form. The interplay between roles IS the
curriculum.

## Company frame

Crosstown Mobility, Inc. (fictional): a NYC ride platform. Dispatch, pricing, and
the customer app consume one upstream signal — predicted trip duration (ETA). This
program owns that model and its production system, built on the public TLC yellow
taxi record as the historical book. Everything runs on a local kind cluster;
enterprise shape, laptop budget.

## Structure: builders, one challenger, operational assurance

1st line — builds and owns outcomes: PO (principal = the user; the executor
prepares options in PO-prep blocks) · DE · DA · MLE · MLOps · SRE.
2nd line — challenges: REV, the Staff ML Reviewer, in FRESH sessions only; and
**ARCH, the Grand Architect (Fable)** — the SOLE planning authority [v3.0]:
authors every kickoff and performs every boundary triage in its own fresh
sessions, while the executor (Opus) builds story-scoped sessions in the
autonomous chain. REV judges built artifacts; ARCH owns plans and closures;
accountability lives in pasted evidence and ledgers, not in a second drafter.
Operational assurance is carried by *rituals with committed minutes* rather than a
standing audit office: Data Contract Review · Design Review · Production Readiness
Review · Gameday · Monitoring Review · Blameless Postmortem. A ritual without
committed minutes did not occur.

## RACI for load-bearing deliverables (A is unique per row)

| Deliverable | PO | DE | DA | MLE | MLOps | SRE | REV |
|---|---|---|---|---|---|---|---|
| Org constitution & charters (M0) | A | C | C | C | R | C | C |
| Cluster + platform services (M0) | I | I | I | I | A/R | C | I |
| Data contracts, ingest, DuckDB layer (M1) | I | A/R | C | C | I | I | I |
| Gold marts + Metabase BI layer (M1, grows M2/M7) | I | C | A/R | I | R | I | I |
| EDA report + prior-art survey (M1) | C | C | A/R | C | I | I | I |
| Shadow-analysis memo → canary go/no-go (M6) | C | I | A/R | C | I | C | I |
| Baseline, model v1, promotion gate (M2) | C | I | C | A/R | I | I | ◆ |
| AutoML×Optuna bake-off (M3) | I | I | C | A/R | C | I | ◆ |
| Flyte pipeline on-cluster (M4) | I | C | I | R | A | I | I |
| Serving go-live + PRR (M5) | C | I | I | C | A/R | R | I |
| SLOs, canary/rollback, gameday (M6) | C | I | I | I | C | A/R | I |
| Drift loop + retrain (M7) | I | I | R | R | C | A/R | ◆ |
| Feast + side-by-side (M8) | I | A/R | C | R | C | I | I |

◆ = REV gate: fresh-session review filed before the milestone closes.

## Independence rules (mechanical; violations are findings)

1. REV blocks start a FRESH session reading only committed artifacts; the
   builder's own account is read LAST (anti-anchoring).
2. No self-sign-off: in ledgers/signoffs.md, producer role ≠ approver role, every
   row.
3. Mandatory finding: a REV review filing zero findings is itself a defect.
4. Re-derivation: REV reproduces ≥1 number from raw materials per review.
5. Gates and thresholds (promotion gate, SLO targets once set, drift thresholds)
   loosen only via a PO fork — no role, including MLE, loosens its own gate.
6. Role turf: PRs carry the owning role's label; cross-turf work follows the
   owning role's conventions and says so in the PR body.
7. **Milestone boundary gate (ARCH) — v3.0**: no milestone closes and no next
   milestone starts except through an ARCH session (Fable, stated in-session;
   wrong model = void) that (a) performs the boundary TRIAGE — verify re-runs
   pasted, lineage spot-checked, every finding/condition/debt dispositioned
   with QUOTED carry landings (gotcha #19) — and (b) AUTHORS the next kickoff
   as sole planning authority. Genuine forks route to AWAITING_PO.md and WAIT
   for the PO (no auto-proceed on recommendations — ADR-010); hard-block
   classes never proceed autonomously (gotcha #23). Tag only on a clean close.

## Ledgers — the bloodstream (what they don't hold didn't happen)

`ledgers/signoffs.md` (gate crossings: date, gate, producer role, approver role,
verdict, conditions, evidence link) · `ledgers/findings.md` (challenges: id,
severity S1/S2/S3, owner, status — closed only by evidence, never by reply) ·
`ledgers/deployments.md` (every serve/canary/rollback with exact commands).

## Session scope — which sessions this constitution governs (PO directive 2026-08-30-1)

Everything in this document — roles, blocks, ledgers, gates, the chain — governs
**CHARTERED** sessions and nothing else. The two modes are defined by the PO's
own edit at the head of `CLAUDE.md` ("Scope of this protocol"); that block is the
source and is deliberately cited rather than restated, so there is one home for
the rule (a second copy is the one that would drift):

- **CHARTERED** — launched by `automation/next_session.sh`, or opened by the PO
  with an explicit role and story. This constitution applies in full.
- **EVERYDAY** — every other session that happens to load `CLAUDE.md`. It uses
  the knowledge (gotchas, version pins, environment facts) so solved problems
  stay solved, and it produces NONE of the ceremony: no role block, no ledger
  row, no handoff entry, no field note, no chaining.

**If in doubt, the session is EVERYDAY.** Ceremony is opt-in by the PO and is
never inferred from context — which has a consequence for anyone auditing this
repo later: *a missing handoff entry or ledger row is not evidence of a skipped
step unless the session was chartered.*

A chartered session **states its MODE where it states its model** — first line,
and again in its HANDOFF entry's State paragraph. That line is what turns the
mode into a fact a reader can check instead of an inference from whatever
artifacts the session happened to leave behind.

*Amendment authority:* this section records **PO directive 2026-08-30-1**,
chartered into `docs/milestones/CLEANUP_KICKOFF.md` (CU-S1) by ARCH and
transcribed by an executor. It is not an exception to the rule below — the
constitution still does not amend itself; the PO directed this one.

## Execution model

One executor plays all roles, one role per block, declared via the Prompt-D
header at block entry (charter read, refusals in play named) and exited through
the ledgers. The user is the PO's human principal: PO-prep blocks prepare options
and defaults; ASK-class forks go to the user. Changes to THIS document or the
charters are always ASK-class — the constitution is not self-amending.
