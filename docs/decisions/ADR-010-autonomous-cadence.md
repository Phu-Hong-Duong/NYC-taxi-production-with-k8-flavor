# ADR-010 — v3.0: one architect, no closure prompt, autonomous local chain
- Status: accepted (PO directions, 2026-08-16)
- Verbatim PO directions this ADR implements:
  1. "there is no need to have vice architect for Claude Opus, I believe I
     need only one reliable grand architect Claude Fable is already enough."
     -> Prompts E/F dissolved; Fable authors every kickoff (sole authority).
  2. "there is no need to have a prompt for close off purpose ... as more and
     more C condition piles up from many previous sessions, it becomes a tall
     order for me to handle, as it goes spiral out of my control."
     -> Prompt G retired AS A PO-RUN PROMPT; its protection folded into the
     Architect's boundary session (autonomous triage; dispositions by Claude;
     PO sees only true forks, in ONE inbox: AWAITING_PO.md).
  3. "Claude will set a routine that will run later in a few minutes after
     the first session was done successfully ... 1 to 3 minutes later or so.
     This me be set as local instead cloud" -> automation/next_session.sh:
     local WSL chain, default 120s delay, roles executor/rev/architect,
     STOP kill switch, daily cap 40. LOCAL is also technically mandatory:
     the kind cluster lives on the laptop; cloud sessions cannot reach it.
  4. "please also maintain GitHub workflow push, commit, make pull request,
     merge or so without waiting me and maintain a lineage of development."
     -> standing git autonomy grant: branch/story, push, PR, merge on green +
     verified; HOLD list unchanged (unverified, PO-flagged, undecided-fork).
  5. "So that Claude will not get overwhelmed by long session and garbage
     information. and focus mainly what needs to be addressed in that
     session alone." -> sessions are STORY-scoped and fresh by design.
  6. (mid-turn addition) "there maybe waiting decision when new findings show
     up, Claude can let me choose the developing direction in meantime in
     stead of opt for recommended path, because sometimes Claude choose the
     easiest option for demonstrating purpose." -> FORK POLICY: direction
     decisions WAIT in AWAITING_PO.md — no auto-proceed on recommendations,
     no default-timeout for direction forks; recommendations must state the
     cost of the honest option (anti demo-bias clause, quoted in prompts).
- Amends: the v2.1 boundary machinery (ADRs 006-anchored G->E->F ritual).
  Preserved invariants: triage-before-close (now ARCH-internal), quoted carry
  landings (gotcha #19), lineage checks (gotcha #20), REV independence and
  mandatory finding, no self-sign-off, hard-block classes never auto-proceed
  (gotcha #23).
- Honest costs: unattended permission mode is the PO's risk dial (README);
  WSL must stay alive for the sleep-scheduler (gotcha #24); model-diversity
  review of PLANS is lost — compensated by REV's artifact reviews and by
  triage evidence being pasted, not asserted.
- Revisit triggers: chain misbehaves (runaway, silent stalls) -> harden with
  schtasks variant; PO overwhelmed even by the single inbox -> batch forks
  into the boundary sessions only.
