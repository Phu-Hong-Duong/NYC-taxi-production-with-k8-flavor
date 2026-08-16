# Sign-off ledger — every gate crossing. What this ledger doesn't hold didn't happen.
# Rule: Producer role ≠ Approver role on every row (ORG.md independence rule 2).
| Date | Gate | Producer (role) | Approver (role) | Verdict | Evidence link | Conditions |
|---|---|---|---|---|---|---|
| 2026-08-16 | M0 gate (BLUEPRINT §9/M0, all three legs) | EXEC/MLOps (Opus 5; SRE hat on the S4 drill) — stories S1–S4, PRs #1–#4 | ARCH/Fable 5 (M0 boundary triage session) | **PASS** | HANDOFF entries (l)–(o) with pasted evidence per leg; `make verify-m0` re-run GREEN (18/18, exit 0) by the approver at the boundary 2026-08-16; lineage spot-check `git branch -r --contains c6a3a7e` → `origin/main`; tag `m0-closed` | None on the gate itself. Open at close, non-blocking: F-001 (allowlist, PO's hands, AWAITING_PO 2026-08-16-2) · F-003 (cosmetic, bounded probe scheduled in M1-S4). Debt carried with quoted landings: D-001→M4 · D-002→M1 (intaken at M1 kickoff, absorbed into M1-S4) |
