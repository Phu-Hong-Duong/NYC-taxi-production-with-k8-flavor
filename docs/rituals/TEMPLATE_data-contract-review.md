# TEMPLATE — Data Contract Review

Written at first use (M1-S2). Copy to `docs/rituals/YYYY-MM-DD_data-contract-review.md`.

**What this ritual is for.** The DE wrote a contract; the DA is the first person
downstream who has to live with it. This is where the DA reads the *committed*
contract — `configs/data.yaml` plus `taxi_mlops.data.contract` — and challenges
it, before an EDA report and a board are built on top of assumptions nobody
argued with.

**A zero-finding review is itself a defect** (ORG.md). If the DA reads a
contract and has no challenge, either the reading was shallow or the DA is
rubber-stamping; say so and re-run rather than filing an empty minute.

Every challenge closes exactly one of three ways, and the way is recorded:

| verdict | means |
|---|---|
| **CHANGED** | the contract moved; the diff is in this story's PR |
| **ANSWERED** | the contract stands; the answer carries NUMBERS, not opinion |
| **CARRIED** | neither, yet — becomes a findings/debt row with an owner and a milestone |

"Answered" without a number is not answered.

---

## Header (copy this shape)

```
Date: YYYY-MM-DD · Story: Mx-Sy · Contract under review: <commit sha of configs/data.yaml + contract.py>
Roles present (as blocks, PROMPTS Prompt D):
  role:DE — <what it produced / defends>
  role:DA — <what it challenges>
Data the challenges were run against: <views/tables, row counts, months>
```

## Sections (all required)

1. **What was read** — the exact artifacts, by path and commit. A review of
   something other than what shipped is not a review.
2. **Challenges** — numbered `DCR-nn`, each with: the claim, the EVIDENCE (a
   query and its output, not an intuition), the DE's response, the verdict, and
   the consequence if the verdict is wrong.
3. **Decisions with numbers** — the settled positions, each carrying the figure
   that settles it.
4. **Dissent** — recorded, not resolved away. If both roles agree on everything,
   write "none" and be uncomfortable about it.
5. **Action items** — owner, milestone, and where each one is tracked
   (`ledgers/findings.md`, `ledgers/debt.md`, or a named story). An action item
   that lives only in these minutes will not happen.

## Refusals in play during this ritual

- DA: a number without its definition and window; querying raw parquet when the
  analyst layer exists.
- DE: silently passing a schema change downstream; casting anywhere but ingest.

Neither role may loosen a gate or a threshold here. A challenge that would
change `max_rejected_fraction`, a promotion gate, or an SLO is a **PO fork** —
it goes to AWAITING_PO.md, not into these minutes as a decision.
