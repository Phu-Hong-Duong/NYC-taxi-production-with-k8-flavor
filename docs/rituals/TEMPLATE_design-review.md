# Design Review — YYYY-MM-DD (M<x>-S<y>)

Template written at first use (M3-S2, 2026-08-17), per `docs/rituals/README.md`.
A design review is held BEFORE the work it governs, and its output is decisions
with numbers — not a plan nobody can later be held to. M4 has the next one.

Date: · Story: · Milestone: · Convened by: (the kickoff section that requires it)

**Under review:** the artifacts, each **as committed at `<sha>`** — not a
remembered version. A review of the working tree reviews something that will
never exist again.

Roles present (as blocks, PROMPTS.md Prompt D) — one block per role hat worn:

```
── role-block: role:XX · story: M<x>-S<y> ──
charter read: yes · open findings owned by this role: <ids, or none>
this block produces: … · refusals in play: …
```

**Data every figure was run against:** name the views and their row counts, and
state that no raw parquet was read (or why it had to be).

---

## 0. What this review could NOT do, said first

If any agenda item lacks an input — a parked story, an unreachable source, an
unmeasured number — say so here, before the decisions. A decision with a
forward dependency is minuted as a decision that NAMES the dependency; it is
never minuted as though the missing input existed. Readers six months out
cannot tell the difference unless this section does it for them.

## 1..N. One section per agenda item

Each carries, in this order:

1. **The problem, stated so it could have gone the other way.** If the section
   cannot state what the opposite decision would have been, it is not a
   decision, it is a description.
2. **The decision, with an id (`DR-nn`) and the word "adopted".**
3. **The numbers it rests on**, with their window and their source view. A
   threshold nobody re-derived is a threshold nobody will defend later.
4. **Conditions attached**, each of them checkable.
5. **Dissent, recorded with the answer it got.** A review with no dissent
   either had none — say so — or did not look. Charters name the tensions
   (DA↔MLE, MLE↔REV, SRE↔MLE); the predictable ones are worth voicing even when
   one session wears both hats.

## Action items

| id | action | owner | due (story) | status |
|---|---|---|---|---|
| AI-1 | | | | open |

Every action item names a STORY as its due date, not a wish. An action item
with no story is a note.

## Decisions at a glance

| id | decision | agenda item |
|---|---|---|
| DR-01 | | |

---

**Exit conditions for the ritual to count as held:** minutes committed in the
same PR as the work they govern · every agenda item has a section · every
decision has an id, a number, and conditions · dissent recorded or explicitly
absent · action items carry owners and stories · any ledger row the review
closes is updated in the SAME PR, with the minuted decision as its evidence.
