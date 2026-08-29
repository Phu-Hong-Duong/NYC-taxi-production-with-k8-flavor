# POST-PUBLISH KICKOFF — one PO-directed story: the two-way demo link (PP-S1)

Authored 2026-08-29 by ARCH (Claude Fable, `claude-fable-5`), the ARCH touch the
PO's answer names: *"Charter it at the next ARCH touch as the ordinary story
this entry offered"* (AWAITING_PO **2026-08-29-1**, the PO's words committed
verbatim by session cz). The program is CLOSED (`m9-closed`,
`m9-publish-closed`) and PUBLIC; this kickoff charters exactly ONE post-publish
story and nothing else.

## 0. Boundary triage (post-publish ARCH touch — nothing carried silently)

**There is no milestone to close here.** M9 and its publish phase closed at
`1bf01f0` with all README Status rows flipped and both tags placed; this touch
neither tags nor flips anything. What it verifies is that the state the story
will be built on is the state on disk:

- **`make verify-m9` re-run LIVE this session → GREEN**, closing banner citing
  the CLOSED-and-cited observed box. Read inside it: `@champion` version **2**
  / `feature_set v2` · not one of the 2 registry versions created after
  `m7-closed` · `uv.lock` byte-identical to `lock-rebaselined-m9-publish` ·
  all 5 settled DVC pins up to date · the 9 inherited gates not nested.
- **`make readme-check` → GREEN** (`every target, path and number in README.md
  checks out`; 13 signal ids · 10 gates · 8 red teams · 1,319 tests).
- **Lineage spot-check (gotcha #20)**: PR #77's merge `31e4c48` and PR #76's
  merge `24364ab` are both reachable from `origin/main`
  (`git merge-base --is-ancestor` exit 0).
- **Findings**: the register's only open row is **F-001** (the standing
  session-allowlist note from M0, PO entry 2026-08-16-2, non-blocking by the
  PO's own 2026-08-24 answer 7). It stays open BY DESIGN and is named here so
  it is not a silent carry. The debt register is closed.
- **Session cz's procedural observation** (the watchdog park notice ends in a
  fixed `next_session.sh executor` line, so a PO answer can start the wrong
  role) — **DECLINED as a change, recorded here**: the program is closed, the
  harm is bounded (cz itself demonstrated the guard — a session reads the
  ANSWER, not the notice, and hands off correctly), and editing chain plumbing
  now buys a cosmetic improvement with a maintenance surface that outlives the
  program. If the chain ever runs a new program, re-price it then.

**Triage verdict: CLEAN.** One story chartered below; the queue is otherwise
empty and nothing waits on the PO.

## Preconditions (verified LIVE at draft time — pastes, not memory)

```
$ curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/demo/            → 200
$ curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/demo/analytics.html → 200
$ accept.json: page.committed_sha256 = b1edd074b00f7c0c…  (== served_sha256)
$ accept.json: po_observed_run.status = CLOSED — observed 2026-08-24, cited at AWAITING_PO 2026-08-23-3
$ uv run pytest tests/unit/test_demo_page.py -q                                  → 23 passed
$ grep -c analytics demo/index.template.html                                     → 0   (the forward link does not exist yet)
$ demo/analytics.html:283 carries the back-link: <a href="./">Live quote demo ↗  (one-way today)
```

## Debt intake

None due. The debt register is closed; no row lands here.

## Story (1; one executor session; run to completion or stop before the write)

### PP-S1 — The two-way demo link (role:MLOps — the M9-S1 demo owner's role)

**Why (the PO's words, AWAITING_PO 2026-08-29-1):** *"I want the two-way link
anyway. Charter it … — regenerate `index.html` with the forward link, re-run
`make demo-page` / `make demo-accept`, and keep the closed M9 record honest
about the re-measurement."* ARCH declined this at PR #77 triage because it
forces a re-measurement of a closed byte-identity chain; the PO read that cost
and chose it. Session cz then PRICED the re-measurement (HANDOFF cz), so this
story is a read, not an exploration.

**What:**

1. **Edit the TEMPLATE, never the output.** Add a forward link to
   `analytics.html` in `demo/index.template.html` — a modest relative anchor
   mirroring the analytics page's own back-link style (`analytics.html:283`
   uses a plain `<a>` with the `&#8599;` entity; e.g. *"Program analytics
   &#8599;"*). Constraints the page already lives under: **relative href only**
   (the page's own header says it calls nothing external — PR #77's one repair
   was removing a Google Fonts link), **pure ASCII in source** (entities are
   fine), and `demo/index.html` is GENERATED —
   `tests/unit/test_demo_page.py` regenerates it and demands byte-identity, so
   a hand-edit to the output is exactly what those tests exist to catch.
2. **`TOKEN_COUNTS` does not move.** The link is static markup, not a
   placeholder token (`scripts/build_demo_page.py:125` counts
   `ZONE_OPTIONS`/`RAW_INPUT_SCHEMA`/`DEFAULT_TRIP` only). If the builder's
   occurrence guard trips anyway, follow its own error message (name the
   token-in-a-comment exclusion) — never widen a count to make a run pass
   (gotcha #110).
3. **`make demo-page`**, then the demo suite (23 passed today; if you add a
   small law asserting the forward link exists in template AND output — do,
   it is welcome — the new count is deliberate and stated in the PR).
4. **`make deploy-demo`** — one ConfigMap roll; the roll annotation hashes
   BOTH pages. The script already carries the three wait legs (F-037/F-060,
   gotcha #106): do not weaken them, and run the accept only after the deploy
   returns green.
5. **`make demo-accept` WITH the write — F-063's `--no-write` habit is
   DELIBERATELY SUSPENDED for this one run, by this charter.** The two pins
   (`page.committed_sha256`, `page.served_sha256`, both
   `b1edd074b00f7c0c…` today) MUST move to the new page's sha256 — this is the
   rare case where the tracked record *should* be rewritten, and saying so
   here is what keeps it distinct from the mistake F-063 named. Nothing else
   in that record is a function of the page's bytes.
6. **The PO's CLOSED observed box survives by construction** — `human_box()`
   carries a CLOSED block forward verbatim and can never author one (F-067).
   Verify it did anyway (see accept-when 3); `verify-m9` §2 goes RED if not.
7. **Keep the closed record honest**: one dated line in `demo/README.md`
   noting the 2026-08-29 regeneration (the forward link, PO-directed at
   AWAITING_PO 2026-08-29-1) and that the accept pins moved with it.

**Accept-when (all observable, in order):**

1. `demo/index.template.html` and the regenerated `demo/index.html` both carry
   a relative link to `analytics.html`; `uv run pytest
   tests/unit/test_demo_page.py -q` passes (23, or the stated new count).
2. Through the route: `GET /demo/` → 200 and its body contains
   `analytics.html`; `GET /demo/analytics.html` → 200 and its body still
   carries the back-link — the link is now TWO-WAY, proven by fetching both
   sides, not by reading the diff.
3. `make demo-accept` (with write) **PASSED 9/9**; in
   `automation/runs/m9-demo/accept.json` both sha fields equal the NEW page's
   sha256, and `po_observed_run.status` still reads exactly
   `CLOSED — observed 2026-08-24, cited at AWAITING_PO 2026-08-23-3` with the
   PO's quote intact.
4. `make verify-m9` → GREEN and `make readme-check` → GREEN, both after the
   record write.
5. The stillness refusals hold: no fit, no alias move, no registry version, no
   `uv.lock` change, no cluster mutation beyond the demo ConfigMap roll; the
   generated page still references nothing external (every href/src in the new
   markup is relative).

**Evidence plan:** one PR — template edit + regenerated page + the rewritten
accept record + the `demo/README.md` dated line + any new test — merged on
green; HANDOFF entry; AWAITING_PO 2026-08-29-1 gets a dated LANDED note under
the PO's answer (the house pattern), telling them nothing further is asked.

**Safe stopping point:** anywhere BEFORE step 5's record write — everything to
that point reverts with `git checkout`. After the write, finish accept-when 3–4
before ending the session; a rewritten record with an unrun gate is exactly the
half-done state this program never leaves. No detached run is needed — every
step is seconds-to-minutes; `run_detached.sh` does not apply here.

## Out of scope (named now so creep is visible later)

- `demo/analytics.html` — its back-link stands as merged in PR #77; not touched.
- Any wire, model, registry, mart, or README-number change.
- The `index.template.html` cosmetic follow-ups PR #77 listed beyond the link.
- Watchdog/chain plumbing (declined in §0).

## Risks & walls

- **The byte-identity chain is the whole risk, and it is priced** (HANDOFF cz):
  exactly two fields move in one tracked record. If `make demo-accept` fails
  after the deploy, the likely shape is served ≠ committed — re-run
  `make deploy-demo` and read its own sha legs before touching anything else.
- **If `verify-m9` goes RED after the write**, ask FIRST whether the thing it
  names actually changed for the worse (gotcha #50) — the expected answer is
  that a leg pinned a page property this story legitimately moved; re-derive
  the leg, never widen it, and if the RED is instead about the observed box,
  STOP: that would mean `human_box()` failed its one job (F-067) and it is a
  finding, not a repair-in-passing.
- **3-attempt wall** applies as always; the fallback at the wall is a full
  revert (`git checkout` of template, page, record) — the demo returns to
  today's verified state and the PO gets an honest AWAITING_PO entry.

## Exit

HANDOFF entry · commit + push this kickoff · `automation/next_session.sh
executor 120`. The executor runs PP-S1 and re-parks the chain on its own
handoff (empty queue behind it).

## 0.1 Closing triage (2026-08-29, after PP-S1 landed — dated addendum by ARCH/Fable, session dc; §0 above is the draft-time triage, kept as written)

**PP-S1 landed and the verdict is CLEAN — every accept-when met.** PR #78
merged as `70347c9`, lineage `git branch -r --contains 3f6f232` →
`origin/main` (gotcha #20). Both gates re-run LIVE by the approver AFTER the
landing: `make verify-m9` **GREEN** (closing line verbatim `[verify-m9] GREEN
— every M9 sub-check passed.`, banner citing the CLOSED-and-cited observed
box; `@champion` **2** / `feature_set v2`; not one registry version created
after `m7-closed`; `uv.lock` byte-identical to `lock-rebaselined-m9-publish`;
all 5 settled DVC pins up to date; the 9 inherited gates not nested) and
`make readme-check` **GREEN** (`every target, path and number in README.md
checks out`, including the corrected `1,320 tests` claim).

**Dispositions — nothing carried silently:** **F-081** (raised by PP-S1: the
record-drift-under-`--no-write` finding) **CLOSED same session by the write
that found it**, accounted field by field in `demo/README.md` §7.1. **F-001
remains the register's ONLY open row** (the standing session-allowlist note,
non-blocking by the PO's own 2026-08-24 answer 7 — named here so it is not a
silent carry). Debt register CLOSED. No README Status row to flip: nothing
closed here, all 13 rows flipped at `1bf01f0` and pinned by `readme-check`'s
`STATUS_ROWS`.

**No successor kickoff is authored, and that is a deviation stated with its
reason:** the program is CLOSED and PUBLIC, BLUEPRINT §9 names no further
scope, the PO's inbox is EMPTY, and a kickoff with no story would be a file
pretending otherwise. The chartering precedent stands: any future PO answer
gets its kickoff at the ARCH touch that reads it (the 2026-08-29-1 shape).

**The park mechanism is upgraded from a bare park to `automation/STOP`, for a
measured reason:** after PP-S1's bare park the watchdog toasted "Chain parked
— your decision needed" at an inbox holding nothing (the 04:30 and 05:30
notices now sitting above the LANDED entry), and at 04:50 its heal read an
earlier deliberate park as a DEAD chain and scheduled an executor into an
empty queue (session cz — handled gracefully; cost one session). STOP is the
designed control for "the chain should not run," it is the exact resting
state the PO kept the closed program in from 2026-08-26 until this morning,
and it changes no watchdog code — §0's decline stands. Restart:
`rm automation/STOP && automation/next_session.sh architect 120`.
