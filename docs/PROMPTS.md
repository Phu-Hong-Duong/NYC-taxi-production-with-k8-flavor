# PROMPTS — v3.0 (2026-08-16; the autonomous cadence)

v3.0 supersedes v2.1's prompt battery at the PO's direction (verbatim record in
ADR-010): **Fable is the sole Grand Architect and authors every milestone
kickoff himself** (the Opus-drafts/Fable-audits two-step is dissolved); **there
is no closure prompt for the PO to run** — boundary triage folded into the
Architect's own session; and after one human paste, **sessions schedule each
other locally** (executor → … → rev → architect → executor), each short, fresh,
story-scoped. Your entire operating surface is now: paste Prompt A once ·
answer AWAITING_PO.md when asked · `touch automation/STOP` to pause.

The self-run prompts live as FILES the chain feeds to each session — edit them
there, not here: `automation/executor_prompt.md` · `automation/
architect_prompt.md` · `automation/rev_prompt.md`. The chain mechanics and
caveats: `automation/README.md`. Fork policy everywhere: direction decisions
WAIT for the PO in AWAITING_PO.md; the chain never auto-proceeds on a
recommendation, and recommendations must state the cost of the honest option.

---

## Prompt A — Session 1 bootstrap (the ONE prompt you paste; run in `claude --model fable`)

```
You are the Grand Architect (Claude Fable) of Crosstown Mobility's ETA &
Reliability Program, bootstrapping an autonomous program on this machine.
State your configured model first; if it is not Fable, stop. I am the PO.
PROTOCOL_MODE is learning: I confirm it here. After this session I will
mostly be away: the chain runs itself, and direction decisions wait for me
in AWAITING_PO.md — never auto-proceed on a recommendation.

Read, in order: CLAUDE.md · HANDOFF.md (newest) · docs/BLUEPRINT.md ·
docs/org/ORG.md + ROLES.md · automation/README.md · docs/gotchas.md.

This session's plan, in order:
1. PREFLIGHT, verified by running: repo is inside the WSL2 filesystem; git
   remote reachable with push rights; `gh auth status` succeeds (PR/merge
   autonomy runs through the GitHub CLI — the one human prerequisite);
   `claude` CLI present; permission flags set (echo $CLAUDE_PERMISSION_FLAGS);
   Docker Desktop up; WSL RAM grant >=48GB (`free -h`); ports free (CLAUDE.md
   port family). Paste every check.
2. PROVE THE HARNESS before trusting it: (a) run
   `automation/next_session.sh executor 60` pointed at a throwaway hello
   prompt (temporarily; restore after) and observe a session actually start
   60s later and log; (b) prove the kill switch: touch automation/STOP,
   schedule again, observe the refusal, remove STOP. Paste both observations.
3. AUTHOR docs/milestones/M0_KICKOFF.md per the template (you are the sole
   kickoff author): boundary-triage section says "program start — nothing to
   triage"; preconditions from step 1; M0's stories from BLUEPRINT §9/M0,
   each sized for ONE short executor session; evidence plans; out-of-scope.
4. Commit + push everything (conventional commits; this is main-line setup,
   no PR needed for the bootstrap commit). Write the HANDOFF entry.
5. Start the program: `automation/next_session.sh executor 120` — then stop.
   From here the chain runs; I watch AWAITING_PO.md and the ledgers.
```

## Prompt D — Role-block header (used INSIDE sessions by the executor; unchanged)

```
── role-block: role:<DE|DA|MLE|MLOPS|SRE|PO-prep> · story: <Mx-Sy> ──
charter read: yes · open findings owned by this role: <ids or none>
this block produces: <artifact(s)> · this block's refusals in play: <top 1–2>
```

## Retired in v3.0 (recorded so the history is legible)
- Prompt B (builder continuation) → became `automation/executor_prompt.md`.
- Prompt C (fresh-eyes review) → became `automation/rev_prompt.md`, scheduled
  automatically after ◆ milestones.
- Prompt E (executor drafts kickoff) → dissolved; the Architect authors.
- Prompt F (architect audits/vetoes drafts) → dissolved into authorship.
- Prompt G (pre-closure sweep) → folded into the Architect's boundary session
  (triage happens, autonomously; the PROTECTION survives, the prompt you had
  to run does not — and its findings route to ONE inbox instead of piling
  across handoffs).

---

## Why the cadence is shaped this way

**Short fresh sessions are the context-hygiene mechanism.** One story per
session means each session reads only what that story needs — kickoff, newest
handoff, its own files — and garbage cannot accumulate, because nothing
outlives a story. The repo is the memory; sessions are disposable.

**Authority without authorship died; authorship with accountability replaced
it.** One architect who writes the plans is simpler than an architect who
grades another model's homework — but the accountability moved into artifacts:
triage verdicts with pasted re-runs, quoted carry-landings, REV's independent
findings on ◆ milestones, and ledger rows that name who did what.

**The chain is interruptible by construction.** Every session ends at a safe
stopping point (that's what stories ARE); STOP pauses the world; a parked fork
halts scheduling rather than guessing; the daily cap bounds the blast radius
of everything. Autonomy here means the system runs without you, never that it
decides without you — the two things your fork policy keeps separate.
