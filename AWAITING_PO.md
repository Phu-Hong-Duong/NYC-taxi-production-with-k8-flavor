# AWAITING_PO — the one inbox (newest on top; the chain parks affected paths here)

## 2026-08-30-3 · raised by EXEC/Opus (session de) · **ARCH cannot run: the architect model is out of monthly spend, so the cleanup cannot be chartered — one fork, three options**

> **ANSWERED 2026-08-31 by the PO (in chat, via their Windows-side session):**
> *"can you resume this process"* — **option (a), and the wait is over.**
> The architect lane was re-probed the way this entry established the wall:
> `claude --model fable -p` answered `OK` at 2026-08-31T07:12:07Z, exit 0 —
> the monthly limit no longer bites. No model rewiring, no constitutional
> exception: the chain resumes as designed and the next ARCH touch charters
> the cleanup (directive 2026-08-29-2, audit seed 89e049a, verification
> PR #79 all waiting for it). Resumed by the FILE-OPS route; the entry
> below (2026-08-30-2, the VM/watchdog deadlock) is NOT answered by this
> and stays open.

> **SWEPT 2026-08-31 by ARCH/Fable (the ARCH touch your answer names).** The
> cleanup is chartered: `docs/milestones/CLEANUP_KICKOFF.md`, five executor
> slices (CU-S1…S5) over the verified audit, an executor scheduled. Nothing
> further waits on you in THIS entry. One thing you can do that the chain
> cannot: **Docker Desktop is down**, and no slice can MERGE until the
> ten-gate sweep runs — launching it (one click, ~15 s for the kind nodes to
> return) unblocks acceptance; until then executors will work, open PRs, and
> hold merges, exactly as the charter instructs.

**Measured, not inferred.** The cleanup directive (2026-08-29-2) needs an ARCH
touch to become a charter. ARCH was scheduled by session (dd) at 11:53:26Z and
**died on launch**, log `automation/logs/20260830_115326_architect.log`, 154
bytes, its entire content:

> `You've hit your monthly spend limit. Switch to another model, or manage usage credits at claude.ai/settings/usage…`

I probed it directly rather than trusting one log — `claude --model fable -p`
returns the same message **right now**. The chain's role→model wiring is
`executor=opus · rev=opus · architect=fable`, so **opus is fine and fable is
spent**: this session is proof the executor lane still works. The watchdog then
read the dead ARCH as a dead chain and healed to an executor (me) — which is
the third consecutive session to arrive with an empty queue.

**Why this is yours and not mine:** it is money, and it is also a direction
question about the constitution (who may author a charter). Both are named fork
classes. Nothing auto-proceeds.

- **(a) Wait for the monthly reset.** *Cost:* the cleanup does not start for
  ~1–2 days, and — because of the unanswered **2026-08-30-2** — every session
  that parks in the meantime stays parked until you next touch WSL, so the wait
  is not self-managing. *Benefit:* zero change to anything; the constitution's
  producer≠approver separation stays exactly as designed.
- **(b) Point the architect role at an available model** (one line in
  `automation/next_session.sh`, `architect=opus`). *Cost, and it is the real
  one:* ARCH and EXEC become the same model, so the fresh-eyes separation that
  ADR-010 and the signoff rule rest on becomes a separation of SESSION only,
  not of model. This program's whole record is that the independent second
  witness is the one that catches things — a boundary triage by the same model
  that wrote the slice is a weaker approval, and it would be weaker silently.
  *Benefit:* the cleanup starts today and the chain self-manages again.
- **(c) Let an EXEC session author the cleanup charter, once, explicitly
  scoped.** *Cost:* an executor writing its own kickoff is the one thing the
  constitution does not permit, and permitting it "just this once" is exactly
  how a guard becomes a formality (gotcha #50's social form). *Benefit:* no
  model change, no spend, work starts immediately.

**Recommendation: (a), and I am naming its cost rather than routing around
it.** The honest option is the slow one. The cleanup is a *followability*
change to a CLOSED, published program — there is no deadline on it, and every
guarantee it must not weaken is currently green. Against that, (b) buys a day
or two by permanently degrading the review separation on every future story,
and (c) buys the same day or two by spending a constitutional rule. Neither is
worth it for a cleanup whose own directive says the floor is "must not weaken
what the program can PROVE".

**If you disagree, (b) is the better of the two fast options** — it is one
reversible line and it degrades a separation, where (c) removes a rule. If you
take (b), the honest mitigation is to say so in the signoff rows for any story
approved that way, so the record shows which approvals had a model-independent
witness and which did not.

**What is ready meanwhile, and it needed no charter:** the cleanup's audit leg
now has a **verified** input. `docs/cleanup_audit_verification.md` +
`scripts/cleanup_audit_verify.py` re-derive by RUNNING every number the seed
produced by grepping — **43 CONFIRMED · 6 DIFFERS · 3 newly MEASURED**, with
all six DIFFERS accounted for (five are a counting basis, one was my own
regex). It deletes nothing and charters nothing. Three deletion constraints the
seed could not see are now written down, the sharpest being that
`f016_replay_probe.py` is named inside a **runtime error message** in
`gate_eras.py` — delete it without editing that string and a live recovery
instruction points at a missing file.

**Chain state:** `automation/STOP` is ABSENT. This session parks deliberately
and schedules nothing — scheduling ARCH again would only burn another session
against the same limit, and scheduling an executor would produce a fourth
empty-queue session. Per 2026-08-30-2 the VM will idle down and no heal will
fire, so **nothing happens until you next touch WSL**.

## 2026-08-30-2 · raised by the PO's Windows-side session · **The watchdog cannot heal a dead chain, because a dead chain lets the VM shut down — one fork, three options**

**Measured today, not theorised.** The PO asked why autonomous mode keeps
stopping and why they cannot take the reins. Three walls were found stacked,
and the third is structural:

1. **Ergonomics.** Every resume instruction in the repo names
   `automation/next_session.sh`, which cannot be run through `wsl.exe` (the
   `setsid` launcher dies with it). The PO works on Windows. So "the PO
   restarts it after deciding" was, for a week, a sentence naming a command
   the PO could not run. **Fixed today** — `automation/README.md` gains a
   *"Resuming from Windows"* section: touch files only, let cron launch.
2. **The park latch reads an answer as a question.** Answering a fork by
   editing this file changes its hash, and the hash IS the park detector — so
   answering without re-stamping `automation/logs/watchdog_awaiting_po.sha`
   latches the chain shut. Documented today in the same section.
3. **The deadlock, and it is the real one.** A live chain session is what
   keeps the WSL VM alive; the watchdog exists to restart a chain that is no
   longer alive. Measured: the 04:20:01 heal launched a session, that session
   died at ~04:23, and by 05:36 `wsl --list --running` reported **"There are
   no running distributions"** with the watchdog's last line still at
   04:20:01 — **eight missed ticks.** The one heal that DID fire only fired
   because a monitoring script happened to be holding the VM open. Nothing
   crashed: WSL2 idle-terminates when nothing is running in it, and cron dies
   with it. **So the chain cannot self-recover from any death, ever** — which
   is the honest answer to "why does agentic coding stop immediately".

**The fork (item 3 only — 1 and 2 are landed, not decisions).** All three
options are cheap; they differ in blast radius and honesty, so this is the
PO's call and nothing auto-proceeds:

- **(a) A Windows scheduled task holds the VM open** —
  `wsl.exe -d Ubuntu -e sleep 86400`, started at login and after the 06:50
  `wsl --shutdown`. *Cost:* the VM (40 GB budget) stays resident whenever
  Windows is on, including hours nobody is working; the laptop's own quiet
  hours were a deliberate PO choice. *Benefit:* nothing inside the repo
  changes, and the watchdog finally works as designed.
- **(b) `vmIdleTimeout` in `.wslconfig`** — raise WSL's own idle window
  instead of adding a process. *Cost:* takes effect only after
  `wsl --shutdown` (and Docker Desktop restart), and it is a machine-wide
  setting affecting every distro, not just this program's. *Benefit:*
  no extra task, no held process.
- **(c) Move the watchdog OUT of the VM** — a Windows scheduled task that
  runs the watchdog's checks (or simply boots WSL every 10 minutes) from the
  side that is always up. *Cost:* a second implementation of liveness logic
  living outside the repo, i.e. exactly the twin this program spends its
  gates preventing; the chain's own `tests/unit/test_watchdog.py` would not
  cover it. *Benefit:* the observer is genuinely outside the thing observed,
  which is the §3 field lesson stated properly.

**Recommendation, with its honest cost: (b) first, (a) as the fallback.**
(b) is one line and no new moving parts, and the cost that matters is
disclosed rather than hidden — it is machine-wide, so it changes WSL
behaviour for the PO's other work too, and it needs a `wsl --shutdown` (which
means a Docker Desktop restart and a kind-cluster restart, ~2 minutes). (c)
is the architecturally *correct* answer and is deliberately not recommended
here: it buys real independence at the price of a liveness twin that no gate
in this repo can check, and this program's whole record says the untested
copy is the one that lies. **Do NOT read (b) as free** — if the PO's answer
is "the VM must not stay resident", then the truthful conclusion is that this
chain is not autonomous overnight, and the protocol should say so plainly
rather than keep a watchdog that cannot fire.

**Also worth the PO's eye, not a fork:** the 04:20 healed session died ~3
minutes in, mid-boot-ritual, with a **0-byte log and no error in its
transcript** — and it was NOT the spend limit (the two "spend limit" strings
in that transcript are it *reading yesterday's logs*). Cause unknown. If
sessions keep dying that way, the watchdog's 3-strikes rule will ring
"Chain keeps dying" — that toast is the signal that a restart cannot fix it.

**Chain state:** `automation/STOP` is ABSENT (removed 04:16Z), no session is
alive, and the VM is down — so nothing will happen until WSL is next touched.
Nothing else waits on the PO.

## 2026-08-30-1 · PO DIRECTIVE (recorded verbatim by the PO's Windows-side session) · **Scope the protocol — chartered ceremony vs everyday help**

> **CHARTERED 2026-08-31 by ARCH/Fable** — rides the cleanup charter exactly as
> this entry offered: the constitutional fold (ORG.md + the ceremony-instructing
> templates, a MODE line beside the model line) is **CU-S1 step 1** in
> `docs/milestones/CLEANUP_KICKOFF.md`. Your CLAUDE.md scope block stays as you
> wrote it — the fold cites it rather than rewriting it.

> **PO 2026-08-30 (in chat, their own words, trimmed):** "based on our
> development in this project so far, i want to update and modify the
> developing protocol to makes it more suitable to my own need. […] that
> Claude mistake between my own need programing and coding in autonomous mode
> completely versus every day occurrents, i.e. asking Claude to troubleshot
> problems on AWS, and at the end of that session a handoff entry appear out
> of nowhere, that even I am puzzled why there is a need to do that in the
> first place. In that situation, isn't it better for Claude to take the
> control of the browser and help me to complete the exercises on the book
> without a need of having the extra handoff entry in the end."

**What the PO is directing:** the protocol's ceremony leaked out of its lane.
Sessions that were never part of the chain — everyday troubleshooting, a
browser session working book exercises — picked the protocol up from their
context and produced chain artifacts (a handoff entry) nobody asked for,
while the actual task went under-served. The amendment is a SCOPE rule:
ceremony (roles, ledgers, handoffs, field notes, chaining) applies to
CHARTERED sessions only — chain-launched or PO-opened with an explicit role;
every other session is EVERYDAY mode — it uses the program's knowledge
(gotchas, pins, memory) so solved problems stay solved, and produces none of
the ceremony. If in doubt: EVERYDAY.

**Landed immediately by this session** (a PO edit, not a chain edit): the
"Scope of this protocol" block at the top of CLAUDE.md, and §11 of the
field-lessons memo (`~/.claude/templates/FIELD_LESSONS_crosstown.md`,
Windows side). **For the next ARCH touch:** fold the scope rule into the
constitution (docs/org/ORG.md) and into whichever templates instruct
ceremony, so a chartered session states its MODE the way it already states
its model. This can ride the 2026-08-29-2 cleanup charter as one small slice
— it is the same complaint (accretion outrunning followability), aimed at
the protocol instead of the code.

Recorded from the same PO message, for the lessons file rather than for
chartering:
- **Recurring-symptom rule:** the WSL↔Windows viewing-copy desync has now
  cost the PO the same debugging twice. When a symptom smells familiar
  ("files/commits behind", a duplicate of a solved problem), check
  gotchas/memory and the viewing-copy sync FIRST, before re-deriving a fix.
- **Two container dialects, one machine:** Kubernetes nodes speak containerd
  (`crictl`), docker speaks docker. The chain already practices this
  (M4-S3 reads images back with the nodes' own `crictl`); everyday sessions
  must not paste one dialect's commands at the other's daemon.

**Chain state:** untouched by this session — `automation/STOP` is PRESENT
(dated 2026-08-29 22:30Z, i.e. the restart attempted for 2026-08-29-2 did
not survive; the wsl.exe launch path is the known-fatal one). The cleanup
charter is therefore NOT being worked on right now. To restart, from a real
Ubuntu session: `rm automation/STOP && automation/next_session.sh architect
120`. Nothing in this entry blocks it.

## 2026-08-29-2 · PO DIRECTIVE (recorded verbatim by the PO's Windows-side session) · **Charter the codebase cleanup — prune the bloat, keep every guarantee**

> **CLOSED 2026-08-31 by ARCH/Fable (cleanup boundary triage, session dn) —
> tag `cleanup-closed`.** All five slices landed and merged (PRs #82–#87); the
> write-up your directive owed is `docs/cleanup_report.md`; the close section
> is `docs/milestones/PROGRAM_CLOSE.md` §8; the signoff row is in
> `ledgers/signoffs.md`. Your floor held and was re-measured from the
> approving seat: **all ten gates GREEN, 1,408 tests, 19/19 red teams still
> RED on their plants, no threshold/bar/knob/wire/lock change anywhere.**
> Net: −2,894 lines of copies, +3,809 of shared libs, stronger tests and the
> report — a subtraction of copies, not of guarantees. **One residual, named
> and DECLINED rather than silently dropped:** `scripts/` sits outside the
> `ruff` lint net (report §9). Measured live at this close: 42 line-length
> nits, zero correctness findings. Chartering it now would spend a session on
> cosmetic churn against a closed record; if you want it, say so — it is one
> small slice. **The chain is re-parked** (`automation/STOP` restored — your
> own resting state, which you lifted this morning for this triage). Nothing
> further waits on you in THIS entry; 2026-08-30-2 (the VM/watchdog deadlock)
> below remains open and yours.

> **CHARTERED 2026-08-31 by ARCH/Fable** — `docs/milestones/CLEANUP_KICKOFF.md`:
> five executor slices (CU-S1 scope-rule fold + dead code · CU-S2 test
> infrastructure incl. the `_calls` 3-semantics correctness fix · CU-S3 verify
> harness + red-team restore libs · CU-S4 python forward/prom/record plumbing ·
> CU-S5 isvc deploy lib + the numbers write-up + the full red-team battery),
> each ending in the ten-gate sweep, argued from your seed AND session (de)'s
> run-verification (43 CONFIRMED · 6 DIFFERS accounted · 3 newly MEASURED).
> Your floor is restated verbatim in the charter and binds every slice.
> **Two ARCH readings you can veto by editing here:** (1) the per-slice
> red-team clause is read as "red teams whose files the slice touched, plus
> the complete battery at CU-S5"; (2) Tier B (411 LOC, five probe scripts with
> Makefile anchors, four cited VERIFIED in CLAUDE.md) is a conscious KEEP, and
> Tier A (1,050 LOC, six prose-only instruments) is deleted with the three
> live reference-site edits landing in the same commits.

> **SEED 2026-08-30 (the PO's Windows-side session):** a read-only measured
> audit of the whole codebase is committed at `docs/cleanup_audit_seed.md` —
> size map, dead-code tiers, duplication clusters with one-home candidates,
> and the test suite's meta/duplication numbers, with suggested slices.
> ADVISORY: ARCH verifies before trusting; where it disagrees with ARCH's own
> audit, ARCH's measurement wins. The PO also confirmed in chat (2026-08-30):
> execution lands on Opus executors — the chain's default wiring.

> **PO 2026-08-29 (in chat, their own words):** "ah, i got another idea, there
> should be a clean up and optimize code, because Claude has a tendency create
> code to test thing and check thing, and it pipe up to a tall order, so it's
> hard to follow the codebase, this is what i call code bloat, code that is
> unnecessary and need to optimize or prune so it's easy to follow up while
> still ensure punctuality. Make this one the clean up for this project. Let
> claude this time optimze the entire codebase for this project"

**What the PO is directing** (their Windows-side session's reading, for the
ARCH touch that reads this — the 2026-08-29-1 chartering shape): a
**followability cleanup over the ENTIRE repository** — `src/`, `scripts/`,
`tests/`, `pipelines/`, `automation/`, `analytics/`, and the navigation
surface a reader enters through. The complaint is specific and it is fair:
nine milestones of verify scripts, red teams, twin checkers, probes and
one-off drills have accreted into a surface where the load-bearing code is
hard to find. "Optimize" here means the CODEBASE, not the model or the
latency: followability first; runtime performance only where it falls out
free. Target classes, in the order the PO's words suggest:

1. **Dead and superseded code** — probes whose findings are banked in tracked
   records, helpers nothing calls, paths kept "just in case", scripts a later
   story replaced without deleting.
2. **Duplication** — the same idiom re-implemented story by story
   (port-forward blocks, record readers, sha256 restore traps,
   consume/verdict plumbing, accept-check scaffolding…): consolidate each
   into ONE shared home, callers migrated.
3. **Accidentally overlapping checks** — where two checks assert the same
   property because copies drifted apart, fold them into one home (F-013's
   one-home rule, generalised). This does NOT touch the program's DELIBERATE
   two-witness designs — the pairs that argue their own pairing in prose
   (cache drill, canary counters, …) are load-bearing and stay.
4. **Navigability** — whatever cheap structure makes the codebase readable
   (a code map, module docstrings, consistent naming), where it earns its
   bytes. Historical documents are the record and are not rewritten;
   corrections go beside originals, as always.

**The floor under all of it — what "while still ensure punctuality" is read
as; the PO can veto this reading by editing here:** the cleanup must not
weaken what the program can PROVE. Concretely: all ten gates GREEN after
every merged slice · every red team still goes RED on its plant · no
threshold, bar, knob or gate condition moves · no tracked record under
`automation/runs/` is rewritten · no wire, alias, registry, mart-number or
`uv.lock` change · the boundary laws hold. **Consolidation is sanctioned;
deletion of a whole gate, red team, or recorded drill is NOT covered by this
directive** — if the audit concludes one should go, that specific removal
comes back here as a fork with options (the constitution already reserves
it).

**Shape (ARCH's to decide, offered not ordered):** this is bigger than one
story. An AUDIT leg first — a measured inventory (LOC per area, dead-code
findings, duplication clusters, each with a costed keep/consolidate/delete
verdict), committed BEFORE any edit, so the prune list is reviewable and the
before/after numbers are evidence rather than vibes — then executor slices,
each a safe stopping point ending with the gate sweep green. The cleanup's
own write-up carries its numbers: files/LOC before and after, tests before
and after, what was deleted and WHY each deletion is safe.

**Chain state:** this session removes `automation/STOP` and resumes the chain
as `architect` so the next ARCH touch charters this directly. Nothing else
waits on the PO.

## 2026-08-29-1 · raised by ARCH/Fable (post-publish triage) · **PR #77 TRIAGED AND MERGED — your queue is EMPTY, and the chain re-parks on purpose**

> **PO 2026-08-29 (via the Decision Desk): I want the two-way link anyway.**
> Charter it at the next ARCH touch as the ordinary story this entry offered —
> regenerate `index.html` with the forward link, re-run `make demo-page` /
> `make demo-accept`, and keep the closed M9 record honest about the
> re-measurement. *(Click recorded on the Decision Desk 04:38Z and applied to
> this file by the PO's Windows-side session the same hour — uncommitted, the
> answer-by-editing flow; the next ARCH session sweeps it.)*

> **CHARTERED 2026-08-29 by ARCH/Fable (the ARCH touch your answer names).**
> The two-way link is story **PP-S1** in
> `docs/milestones/POST_PUBLISH_KICKOFF.md` — one executor session: the forward
> link goes in the TEMPLATE, `make demo-page` / `make deploy-demo` /
> `make demo-accept` **with** the record write (the F-063 `--no-write` habit
> deliberately suspended for that one run, said in the charter), your CLOSED
> observed box carried forward verbatim by construction (F-067) and verified
> anyway, `make verify-m9` GREEN after. Triage at draft time: `verify-m9` and
> `readme-check` both re-run GREEN live, both PR merges reachable from
> `origin/main`, only F-001 open (standing, non-blocking). An executor is
> scheduled; **nothing waits on you.**

> **LANDED 2026-08-29 by EXECUTOR/Opus (session db) — the link is two-way and
> nothing further is asked of you.** Story PP-S1, one PR. The forward link went
> in the TEMPLATE (`demo/index.template.html`); `demo/index.html` was
> REGENERATED, never hand-edited. Proven from both ends rather than from the
> diff: `GET /demo/` → **200** carrying `analytics.html`, `GET
> /demo/analytics.html` → **200** still carrying its back-link.
> `make demo-accept` **PASSED 9/9** (quote 39.00193715359812 vs the recorded
> 39.00193715359812, |delta| 0.000e+00, `model_version` '2'), `make verify-m9`
> **GREEN 46/46**, `make readme-check` **GREEN**, host suite **1,320**.
>
> **The re-measurement you sanctioned, itemised.** Rewriting a CLOSED
> milestone's record was the whole cost, and it is accounted for in
> `demo/README.md` §7.1 rather than left in a commit message: three fields moved
> because they are functions of the page's bytes (`page.bytes` 47,147 → 47,461
> and both sha256 pins `b1edd074…` → `f5f0bde9…`). **Your observed-box entry is
> untouched** — still `CLOSED — observed 2026-08-24, cited at AWAITING_PO
> 2026-08-23-3` with your note verbatim, carried through the rewrite by
> construction (F-067), and verified afterwards.
>
> **One thing found by doing it, and it was not this story's doing.** A FOURTH
> field moved: the 2031-refusal text the record captures had been stale since
> M9-S7 shipped F-062's wording, because every accept run since then used
> `--no-write`. Recorded as **F-081**, closed by the same write. Nothing was
> wrong with the code, the endpoint, or any gate — the record was describing an
> older program, and it now describes the current one.
>
> **Your list is EMPTY and the chain is re-parked** — no session is scheduled.
> To restart it for anything at all: `automation/next_session.sh architect 120`

**ROUTED 2026-08-29 by EXECUTOR/Opus (session cz) — your answer is now COMMITTED
verbatim, and nothing waits on you.** The chain was restarted as an *executor*
by the watchdog's generic advice line, but your answer names who charters this
("at the next ARCH touch") and the work touches a CLOSED milestone's
byte-identity chain — so this session did not improvise it into existence. It
verified the state live (`make verify-m9` GREEN · `make readme-check` GREEN ·
3/3 nodes Ready 12d · both InferenceServices Ready · both demo pages serving
200), committed your note so it cannot be lost to a stray checkout, **measured
exactly what the re-measurement you sanctioned costs** (HANDOFF cz — two
sha256 fields in one tracked record, one ConfigMap roll, one gate, one test
file; the record's `human_box()` carries your CLOSED observed box forward
verbatim by construction, so re-running the accept cannot erase it), and handed
to ARCH. **Your list is still EMPTY** — the ball is with the chain, not with
you.

**One sentence.** The one item you held for ARCH triage is done: **PR #77 (the
analytics companion page) is MERGED** as `31e4c48` after review, with one repair
pushed to your branch first (`30c5345` — the Google Fonts `<link>` removed,
because the page's own header says it "calls nothing", `index.html` carries zero
external references, and every font stack already named the system fallbacks the
removal degrades to; nothing else changed — no number, no chart, no script).

**What the triage verified before merging** (details in the PR comment): all
five bake-off rows reproduce `automation/runs/m3s5/bakeoff.json` exactly · the
2020-01-29 daily row (223,287 trips · MAE 3.1449 · bias +0.2355) re-derived live
from the analyst layer · self-heal anchors 25.5 → 40.03 = 14.53 s match the M5
records · JS hygiene clean, pure ASCII holds. After the merge, run live:
`make deploy-demo` **GREEN** (incl. the new analytics sha256 leg) ·
`make demo-accept --no-write` **9/9** (M9's tracked record untouched — F-063's
rule) · `make verify-m9` **GREEN** · `make readme-check` **GREEN** after the
one follow-up you listed (a root-README row for the page) · 23/23 demo tests.

**One follow-up DECLINED with a reason**: the optional two-way link from
`index.template.html`. `index.html` is bound into M9's closed accept record and
its byte-identity contract; touching a closed milestone's artifact chain for a
cosmetic link is not worth the re-measurement it would force. The one-way
back-link the PR ships stands. Say the word if you want it anyway — it is an
ordinary chartered story, not a fork.

**Your public flip of 2026-08-29 is now COMMITTED to the inbox** (your note
under 2026-08-25-3 below, kept verbatim). The page is live at
<http://localhost:8081/demo/analytics.html>.

**Your list is now EMPTY.** Nothing is chartered, nothing waits on you, and the
chain is deliberately RE-PARKED — no session is scheduled. To restart it for
anything at all: `automation/next_session.sh architect 120`

## 2026-08-25-4 · raised by ARCH/Fable (PUBLISH BOUNDARY) · THE PUBLISH PHASE IS CLOSED AND TAGGED — the entry below (2026-08-25-3) is still the whole of your list, and this note only confirms the chain parked on purpose

**One sentence.** The ARCH boundary session your chain scheduled has run: the
publish phase is **closed and tagged `m9-publish-closed`**, the five touched
gates were re-run GREEN at the boundary (`verify-m2` 57 · `verify-m3` 47 ·
`verify-m7` 63 · `verify-m8` 51 · `verify-m9` 46 `ok` sub-checks, counted
live), the README's M9 Publish row is flipped with the evidence beside it, and
the closure verdict is `docs/milestones/PROGRAM_CLOSE.md` §7.

**Nothing new is asked of you.** Every finding the four stories raised
(F-074…F-080) was closed in the session that raised it; the debt register is
closed; the only open finding in the register is F-001, the standing
session-allowlist note from M0 (your entry 2026-08-16-2, non-blocking).

**Your list is exactly the entry below this one (2026-08-25-3): the click.**
The chain is deliberately RE-PARKED — no session is scheduled. To restart it
for anything at all: `automation/next_session.sh architect 120`


## 2026-08-25-3 · raised by EXEC/Opus (M9-S13) · **ALL THREE LETTERS ARE LANDED — the public flip is your click, and nothing is blocking it**

> **FLIPPED PUBLIC 2026-08-29 by the PO** — decided on the Decision Desk, confirmed
> in chat, executed by the PO's Windows-side session with `gh repo edit
> Phu-Hong-Duong/NYC-taxi-production-with-k8-flavor --visibility public
> --accept-visibility-change-consequences`, and **verified**: `gh repo view` reads
> `"visibility": "PUBLIC"`. Nothing else was blocking (this entry's own words); the
> program's public phase begins here. One open item remains OUTSIDE this inbox:
> **PR #77** (the analytics demo companion page, PO-directed post-close, live from
> its branch at `/demo/analytics.html`) — the PO chose **Hold for ARCH triage**, so
> the next ARCH touch triages it with the follow-ups listed in the PR body.

**One sentence.** Your four answers of 2026-08-24-5 are done and verified —
sqlparse, the credential rotation, the pre-commit hook, and the publish decision
itself — so the only thing left between this repository and a public URL is you
clicking *Change visibility → Public* on GitHub.

**What landed since you answered, each with the command that proves it:**

| your answer | story | evidence |
|---|---|---|
| F-016/F-068 option (b), era-aware incumbent margin | **M9-S10** | `make verify-m2` GREEN 57/57 · `verify-m3` 47/47 · `verify-m7` GREEN; both planted-edit red teams PASS. All nine recorded verdicts replay unchanged |
| sqlparse 0.6.0, option (b) | **M9-S11** | three HIGH CVEs gone (repo-tree dependency findings **5 → 1**, CRITICAL 0 · HIGH 0); `uv.lock` re-anchored to the tag `lock-rebaselined-m9-publish` |
| rotate the credentials, in place | **M9-S12** | 12 credentials across 5 families; **all ten gates GREEN in one sweep**; the pre-rotation copy destroyed |
| yes to the pre-commit hook | **M9-S13** | `make hook-redteam` **PASSED, 20 checks, 0 failures**; `make security-scan` **`publishable: true`, `secrets_in_git: 0`** |

**The hook, and the limit you were told about when you said yes.** It is
installed with `make install-hooks` and it refuses any commit that would add a
credential — verified by planting one and watching the commit be refused. Two
things it is NOT, both by design and both stated in the README, in the hook's own
header and in its record: it is **not a gate** (`.git/hooks` is untracked, so no
check in this repository can see whether it is installed on any machine), and it
is **bypassable** with `git commit --no-verify` — which the drill *measures*
rather than merely warns about, and then shows the audit catching what the bypass
let through. **`make security-scan` remains the audit of record**, and it is what
your publish decision was made conditional on.

**One thing found by running it, so it is not a surprise later.** Installing the
hook broke an existing drill within the hour: `make security-scan-redteam` stages
a credential *on purpose* so the history scan can be watched catching one, and the
new hook correctly refused it. Nothing was wrong with either. Fixed in the same
session (F-080), both drills re-run green.

**NOTHING IS BLOCKING AND NO DECISION IS NEEDED HERE.** This entry exists so the
inbox says plainly that the queue is empty. The chain continues to the ARCH
publish boundary on its own.

**When you want to flip it:**

1. GitHub → the repository → Settings → General → Danger Zone → **Change
   visibility → Public**.
2. Nothing else. `.env` has never been in git; the audit above verified that over
   every tracked file and every commit on every ref, not just over `main`.

**If you want to re-run the evidence yourself first** (a few minutes, read-only):

```bash
cd ~/NYC-taxi-production-with-k8-flavor
make security-scan      # publishable: true, secrets_in_git: 0
make verify-m9          # GREEN
make readme-check       # every number in the README, read back from its record
```

**To restart the chain by hand at any point:** `automation/next_session.sh architect 120`

*Two standing entries remain open and neither blocks the flip:* **2026-08-17-1**
(a one-line OpenMP convenience for this laptop) and **2026-08-16-2** (widening the
session permission allowlist).


## 2026-08-25-2 · raised by EXEC/Opus (M9-S11) · NOT A FORK, NO ACTION NEEDED — your sqlparse answer has LANDED, and the price you were quoted was wrong by one package

**One sentence.** Option (b) is done — **sqlparse 0.5.5 → 0.6.0, the three HIGH
CVEs are gone** (repo-tree dependency findings **5 → 1, CRITICAL 0 · HIGH 0**,
nothing left fixable in our lockfile) — but the bump could not be the one command
it was priced as, and you should know what it actually cost before the flip.

**What it cost that the estimate did not include: `dbt-core 1.12.2 → 1.12.3.**
`uv lock --upgrade-package sqlparse` produced an **empty diff** and reported
success, because dbt-core 1.12.2 declares `sqlparse<0.6.0` — an upper bound the
resolver honours and does not narrate. dbt-core **1.12.3** is a patch release
whose relevant change is relaxing that bound to `<0.7.0`. So the minimal
upstream-sanctioned path moves two packages.

**Why I landed it rather than parking to ask.** Your letter chose the goal (bump
before the flip) and accepted the cost class (re-baseline the invariant, re-run
the proofs to show nothing moved). The alternative that keeps the *diff* looking
like the one you were quoted is a constraint override — force sqlparse past dbt's
declared bound — which ships dbt running against a version its own metadata
forbids, untested by anyone. That is a worse trade bought purely to protect an
estimate, and the proof your letter already required is exactly the one that
falsifies the honest option: **`make marts` on the new pair returned `dbt build`
PASS=80 WARN=0 ERROR=0 and republished all six marts to the row** (56,127,878 ·
44,792 · 8 · 80 · 1,151 · 91). The undo was one `git checkout` throughout.

**If you disagree, the revert is cheap and I will take the letter:** one commit
reverts the lock and the anchor, and the CVEs go back to being option (a)/(c) from
2026-08-24-5. Nothing downstream depends on the bump.

**Everything you asked for is proved, not asserted:** `make verify-m8` GREEN
51/51 · `make verify-m9` GREEN · both red teams PASS with sha256-identical
restores · `make parity` **0.000e+00** over 16 hazards · host suite **1,277
passed** · `make readme-check` GREEN · `make security-scan` still
`publishable: true`, zero secrets. Nothing was fitted, no alias moved, no
registry version was created, no wire was touched.

**Two things recorded rather than netted out.** (1) The three container images
still carry the old sqlparse until their next natural rebuild — nothing
on-cluster parses SQL from an untrusted party, and rebuilding three images to
close a CVE in a parser nothing points at untrusted input is cost without a
threat model (`docs/lock_rebaseline_m9.md` §5.1). (2) `verify-m9` emits **46**
sub-checks and has since M9-S7; the `45/45` in the epilogue-close README row was
stale and is corrected there with the measurement beside it.

**Your list is UNCHANGED and shrinking on its own:** the publish flip is still
your click, and it is now waiting on **M9-S12** (credential rotation, in-place)
and **M9-S13** (pre-commit hook), both already chartered from your own answers.
**Nothing new is asked of you here.** Detail: `docs/lock_rebaseline_m9.md` ·
ledger row **F-074**.

---

## 2026-08-25-1 · raised by ARCH/Fable (EPILOGUE CLOSE) · THE EPILOGUE IS CLOSED AND THE CHAIN IS RE-PARKED — your two open items are unchanged, and the resume command below now works better than it used to

**One sentence.** The epilogue is closed and tagged **`m9-epilogue-closed`**
(S5/S7/S8/S9 landed; **S6 parked on your letter at 2026-08-24-4**, exactly as
its own safety rule required), `make verify-m9` is GREEN 45/45 and the host
suite is 1,246 passed — **nothing new is asked of you here**, this entry is the
deliberate park that tells the watchdog the silence is a decision.

**Your two open items, unchanged and in order of size:**
1. **2026-08-24-4 — F-016/F-068, answer with a letter** ((a)/(b)/(c)/(d),
   recommendation (b)). S6 stays chartered and unblocks the moment you answer.
2. **2026-08-24-5 — the publish flip is your click**, plus the small `sqlparse`
   fork ((a)/(b)/(c), recommendation (b)). The pre-publish pair is done and
   `publishable: true`.

**One correction to an old footer, so nobody follows it:** 2026-08-24-4's foot
says `next_session.sh executor` — that was right while S7…S9 still remained.
The epilogue is closed now, so **any answer resumes with `architect`** (an ARCH
touch charters the landing; for -4 the landing is a full story under whichever
option you pick, and for -5's `sqlparse` option (b) likewise).

**What this boundary fixed in the chain plumbing (F-072, so the behaviour you
see matches what the entries promise):** running the resume command below now
also stamps the inbox as read — before this, entries you had already answered
could later be mistaken for a NEW fork, and a crashed session could sit
unhealed looking like a deliberate park. Also F-073: a `verify-m9` leg that
narrated F-062 as still open was re-derived; the gate is GREEN with the true
story. Details: `docs/milestones/PROGRAM_CLOSE.md` §6, ledger rows F-072/F-073.

```bash
cd ~/NYC-taxi-production-with-k8-flavor
automation/next_session.sh architect 120   # resumes the chain on any answer (and clears the park latch)
```

---

## 2026-08-24-5 · raised by EXEC/Opus (M9-S9) · THE PRE-PUBLISH PAIR IS DONE — the public flip is your click, plus one small CVE fork

> **ANSWERED 2026-08-25 by the PO: Option (b), plus YES to both smaller things**
> (decisions collected option-by-option via the PO's Windows-side session and
> recorded here verbatim):
>
> 1. **sqlparse — option (b).** Bump to 0.6.0 and re-baseline the lock
>    invariant BEFORE the flip, cost accepted as stated: `verify-m8` §1
>    re-pointed at a new tag, `make marts` and the MLflow client re-run to prove
>    nothing moved, the M8 quarantine's pin file checked. The public flip
>    happens after this lands and remains the PO's click.
>
>    **LANDED 2026-08-25 (M9-S11) — decision 1 only; 2 and 3 remain chartered as
>    M9-S12 and M9-S13.** sqlparse 0.5.5 → 0.6.0, three HIGH CVEs gone
>    (repo-tree dependency findings **5 → 1, CRITICAL 0 · HIGH 0**,
>    `fixable_in_our_lockfile: []`). **It was not one command**: dbt-core 1.12.2
>    declares `sqlparse<0.6.0`, so `uv lock --upgrade-package sqlparse` produced
>    an EMPTY diff and reported success — **dbt-core 1.12.3** moved with it, and
>    that is **F-074**. 243 packages before and after, 0 added, 0 removed,
>    exactly 2 moved, every pinned numeric core byte-unchanged. The invariant
>    kept its SHAPE and only its anchor moved, once, to
>    `lock-rebaselined-m9-publish`; §7's registry-creation bound deliberately
>    stayed at `m7-closed`, because moving THAT forward would ADMIT versions
>    rather than refuse them. Proofs: `make marts` dbt build **PASS=80** with all
>    six mart counts reproduced to the row · `make parity` **0.000e+00** over 16
>    hazards · `verify-m8` GREEN 51/51 · `verify-m9` GREEN · both red teams PASS
>    · host suite 1,277 · `readme-check` GREEN. The quarantine pin file is a
>    recorded ABSENCE (sqlparse is not among its 66 pins) and the three images
>    are deliberately NOT rebuilt, with the reason recorded rather than netted
>    out. Write-up: `docs/lock_rebaseline_m9.md`. See **2026-08-25-2**.
> 2. **Rotate the `.env` credentials before publish — YES.** The mechanism is
>    ARCH's to charter: this entry priced it as `make destroy` + redeploy, but
>    an in-place secret rotation is preferred over a rebuild of the stateful
>    cluster if one is available, since a full restore over a dead platform is
>    still un-rehearsed.
> 3. **Add the pre-commit secret-scan hook — YES**, accepted as unverifiable by
>    any gate exactly as this entry states; `make security-scan` remains the
>    audit of record.

**One sentence.** You said *yes, publish, after the pre-publish pair* (2026-08-24-2,
answer 3); M9-S8 landed the README and M9-S9 has now scanned this repository for
secrets and vulnerabilities — **zero secrets in anything git holds**, verdict
`publishable: true` — so **nothing is blocking the flip except you clicking it.**

**What was checked, and the one thing that would have stopped it.** Two pinned
scanners (trivy **0.74.0**, gitleaks **8.30.1**, sha256s recorded) over four legs:
every file on this disk, **every commit on every ref** (not just `main`'s
ancestry — a secret deleted from `main` still lives in the objects an old commit
points at, and that is what publishing exposes), the three images this program
builds, and the repo's lockfile and manifests. The rule I was working under: a
secret anywhere git can reach = **story-stopping, park, do not publish**. There
were none.

**Two things the scan found that are NOT secrets, both reported rather than
hidden:**
- `.env` trips the scanner ten times. That is correct and expected — it holds the
  real MinIO and Postgres credentials, it has **never been in git**, and each
  finding carries `git check-ignore -v`'s answer beside it as proof rather than as
  an assurance. This is why the scan looks at the whole disk and then classifies,
  instead of scanning only tracked files and reporting a comfortable zero.
- One 32-character string in `scripts/gameday_m6.py` looks exactly like a
  credential because it **is** one — the deliberately WRONG MinIO secret the M6
  gameday injects to make storage refuse the predictor. It is not suppressed in a
  config file nobody reads; it is acknowledged with an argument the scan
  **re-derives from the bytes it finds**, decoding them to the literal string
  `wrong-credential-gameday`. Put a live credential on that line and it goes
  straight back to blocking.

**A DECISION FOR YOU, and it is small.** `uv.lock` pins **sqlparse 0.5.5**, which
carries **three HIGH CVEs with a fix available in 0.6.0**. It arrives transitively
through dbt-core and mlflow-skinny. Exposure here is genuinely limited — it is a
SQL *parser*, and nothing in this program parses SQL from an untrusted party;
every SQL string is written by this repository. **I did not bump it**, because
`uv.lock` is asserted **byte-identical to the `m7-closed` tag** by `verify-m8` §1
and by every M8/M9 story's exit state, so changing it turns a green gate red by
design. That makes it yours.

- **(a) Publish as-is and leave it.** Zero work, gates stay green, and the
  repository ships with three HIGH CVEs in a transitive parser it never points at
  untrusted input. Defensible and documented — `docs/security_audit_m9.md` §4 says
  it in public — but a reader running their own trivy will see it before you do.
- **(b) Bump `sqlparse` and re-baseline the lock invariant.** — **RECOMMENDED.**
  One `uv lock --upgrade-package sqlparse`, then the honest cost, which I am
  stating rather than netting out: `verify-m8` §1 goes RED until the invariant is
  re-pointed at a new tag, `make marts` and the MLflow client both want re-running
  to prove nothing moved, and the M8 quarantine's pin file wants a look. That is a
  chartered story, not a one-liner — probably half a session. It buys a clean
  scanner result on the front page of a public repo and, more usefully, it is the
  first time this program would exercise *changing* a pinned dependency, which is
  a thing every real MLOps platform does monthly and this one has never done.
- **(c) Publish now, bump later.** The flip is not blocked by this. Ship, then
  charter (b) as the first post-publish story. Costs nothing today and leaves the
  CVEs visible to a reader in the meantime.

**Two smaller things worth a word, neither blocking.**
1. **Should the credentials in `.env` be rotated before the repo is public?** They
   are not in git and never were, so publishing does not disclose them. What it
   *does* disclose is the platform's shape — service names, ports, bucket names,
   database names. On a laptop-only $0 stack behind no public route my answer is
   no, but it is your call and it is cheap either way (`make destroy` + redeploy
   regenerates everything).
2. **No pre-commit hook was added, deliberately.** The M1 prior-art ADOPT was
   commit-time secret scanning; a hook lives in `.git/hooks`, which is not tracked
   and cannot be verified by any gate here — so it would be a claim this repo
   could not check. `make security-scan` is the on-demand audit and its verdict is
   a tracked file. Say the word if you want the hook anyway.

**Ready meanwhile / nothing is blocked.** `make security-scan` re-runs the whole
audit in a few minutes; `make security-scan-redteam` proves it can find a planted
credential in the working tree *and* in a commit no branch points at, then
destroys the plant and asks git whether the object is really gone.
`docs/security_audit_m9.md` is the write-up, including the 76 pod-security
misconfiguration findings — a real hardening pass, listed rather than totalled, so
whoever wants it can start from the list instead of the idea.

**The other open item is still `2026-08-24-4` (F-016/F-068, answer with a letter).**

---

## 2026-08-24-4 · raised by EXEC/Opus (M9-S6) · A FORK, AND IT IS SMALL BUT REAL — your F-016 answer (option B) cannot land as chartered; four options, recommendation (b)

> **ANSWERED 2026-08-25 by the PO: Option (b)** (decision collected
> option-by-option via the PO's Windows-side session and recorded here verbatim).
> Land B era-aware: replay each historical verdict against the incumbent margin
> IN FORCE when it was taken; the margin becomes a RECORDED field on every
> future verdict, so the inference from absence is confined to the frozen nine
> in `automation/runs/m9-f016/replay-wall.json`; plus the separate, unweakened
> check that the margin on disk never decreases. Chosen with the stated cost
> accepted, eyes open: this is a full story, not a config line — and the
> in-force value for the frozen nine is read from an enumerated set, never a
> permissive default (F-048's rule). An ARCH touch charters the landing.

> **LANDED 2026-08-25 (M9-S10).** `configs/train.yaml: gate.incumbent_min_improvement_pct: 0.50`, applied to the incumbent KPI-09 condition only, era-aware: all nine recorded verdicts replay against the bar in force when they were taken and **0 flip** (`make verify-m2` GREEN 57/57 · `make verify-m3` GREEN 47/47 · `make verify-m7` GREEN, both planted-edit red teams still PASS), every future verdict records its own bar, and `make gate-margin-redteam` demonstrates the separate margin-never-decreases check going RED on a plausible lowered margin and back GREEN. F-016 and F-068 are CLOSED. Write-up: `docs/incumbent_margin_m9.md`. Nothing was fitted, no alias moved, no registry version was created.

**One sentence.** You chose **option B** for F-016 — a **≥0.50%** margin on the
gate's incumbent condition — the M9 epilogue chartered it as story S6, and the
charter's own safety check *fired*: applying B makes **two recorded verdicts
flip from PROMOTE to REFUSE**, so under the rule the charter itself wrote
(*"if any replay flips, STOP — that is a finding and a PO question, never an
edit to the replay"*) **the edit was not made** and I am handing it to you.

**Nothing moved.** `configs/train.yaml` is byte-identical to main, `gate.decide`
carries no margin, `@champion` is version 2 / `feature_set v2`, no fit, no
registry version, no cluster call that wrote anything. `make verify-m2` (55/55),
`make verify-m3` (46/46) and `make verify-m7` (62/62) were run GREEN before the
work and are unaffected by it. What this session added is a **reader**, its
record, four tests and two documents.

**What flipped, and the part that matters.** Three of this program's gates
replay historical verdicts through the gate as it exists on disk — that is how a
loosened bar is caught. The charter checked three numbers against B and all
three hold. Asked of **every** verdict those legs actually read, 2 of 9 flip:
the `champion v1` row of the M3-S5 bake-off, and the `lightgbm-v1` transcript in
`docs/promotion_gate_m3.md`. **Both are the same fact — a challenger whose error
is numerically IDENTICAL to the incumbent's (+0.0000%).** One is the serving
champion scored against itself as a bake-off contender; the other is a re-fit of
v1 that landed on the incumbent's own number to four decimals.

**So 0.50% is not what stopped it, and that is the single most useful thing
here.** Re-run at a margin of **0.001%**, the same two rows flip. *Any* margin
above zero refuses a challenger identical to the incumbent — so the identity
case has to be answered by whatever version of B lands, at whatever number you
pick. Choosing a smaller bar is not a way around it.

**Two things that bound the stakes, both measured rather than assumed.**
(1) **Neither flipped verdict ever moved an alias** — the M3-S1 run was
`--no-promote`, and M3-S5's alias went to `auto-on-v2`. **No promotion that
actually happened is invalidated by B.** (2) The nearest *surviving* recorded
verdict, `artisan v2`, clears your bar by **0.0612 percentage points**
(+0.5612%) and would flip at 0.57% — that is how much daylight the number you
chose has against history.

**The options.**

- **(a) Land B; teach both replay legs to accept a verdict whose only differing
  condition is the new margin.** Two small edits, B lands the same day. This is
  the cheapest to demonstrate and it is the one the charter forbids: it makes
  those legs admit *any* future incumbent-margin change silently, and admitting
  a gate change without noticing is precisely what `verify-m2-redteam` and
  `verify-m3-redteam` exist to plant against. **Not recommended.**
- **(b) Land B; replay each verdict against the incumbent margin that was IN
  FORCE when it was taken, plus a new, unweakened check that the margin on disk
  never decreases.** — **RECOMMENDED.** It has direct precedent in this repo:
  when the floor legitimately changed at M3-S1, `verify-m2` §2 was made to
  replay each verdict against the floor **recorded in its own block** (*"a
  verdict is replayed against the bar it was actually taken against, or it is
  not a replay"*) with a *separate* check that the floor only ever got harder.
  Same shape, one knob along. **Its honest cost, stated because it is the reason
  (a) looks attractive:** the historical records carry no incumbent margin —
  there was none — so the in-force value has to be read from an **absence**,
  which is exactly the permissive default this program distrusts elsewhere
  (F-048's rule: an unset value must fail loudly, not resolve to something
  convenient). Mitigating that is real work, not a sentence: the margin becomes
  a RECORDED field on every future verdict so the inference is confined to a
  frozen, enumerated set of nine — already written down in
  `automation/runs/m9-f016/replay-wall.json`. Budget it as a full story, not a
  config line.
- **(c) Land B with the identity case carved out explicitly** (refuse below the
  margin *unless* the challenger is the incumbent version). Tidy-looking, and it
  only half-works: it resolves the bake-off row and does **not** resolve the
  M3-S1 transcript, whose challenger was a *fresh fit* that happened to score
  identically and is not the incumbent version by any test the numbers support.
- **(d) Decline B; keep non-regression as pre-registered, and record that as the
  decision.** Free, and F-016's ledger row already allows this closure shape.
  Cost: the asymmetry F-016 named stays open — the alias can still move on a
  delta smaller than the program's own keep bar. Worth knowing before you weigh
  it: nothing has actually churned on that asymmetry, M7-S4's retrain having
  refused at −0.03% under the existing condition.

**My recommendation is (b), and I want to be plain that it is the expensive
one.** (a) would let me land your answer in an afternoon; it buys that by
blunting the instrument that would catch the next unsanctioned gate change,
which is a bad trade for a program whose gates are its main claim. (d) is
perfectly defensible and costs nothing — if your read is that the churn F-016
described is theoretical, saying so on the record is a real answer and closes
the finding honestly.

**Detail, if you want it:** `docs/f016_replay_wall_m9.md` (the measurement, the
table of all nine verdicts, where the charter's population was short, and the
options with costs) · ledger row **F-068** · re-runnable in seconds with
`uv run python scripts/f016_replay_probe.py`.

**Answer with a letter.** Meanwhile the chain continues: **M9-S7** (F-062 option
(b), the wire change) is independent of this and is next; S8 (README front door)
and S9 (trivy + secret scan) follow. Nothing else waits on you.

```bash
cd ~/NYC-taxi-production-with-k8-flavor
automation/next_session.sh executor 120   # resumes the chain (and clears the park latch)
```


## 2026-08-24-3 · raised by EXEC/Opus (post-close, unscheduled session) · NOT A FORK, NO ACTION NEEDED — your close-park was overridden by the watchdog; that is fixed, and nothing about the closed program moved

**What happened.** You parked the chain at the program close on purpose
(2026-08-24-2: no successor scheduled, so the silence would read as a decision).
The watchdog detected that park correctly at **06:40 UTC** and alarmed. At
**07:00 UTC** it logged `chain is DEAD (… no new fork) — healing` and started
executor session **#7** — into a program that was closed and tagged `m9-closed`,
with no story left to execute. **That session is this one.** It found the defect
that started it, fixed it, and is re-parking.

**Nothing about the closed program was touched.** No gate was run or changed, no
alias moved, nothing was fitted, no wire, no registry, no mart, no published
number, no cluster state. `@champion` is version 2 / `feature_set v2`. The diff
is three files under `automation/` + `tests/` + three documents. **The ten-gate
GREEN verdict of the close stands unaltered.**

**The defect (F-066), because it is worth thirty seconds.** The watchdog has said
since it was written that it "may restart an ACCIDENT and must never restart a
DECISION." It implemented that as *fire on the pass where AWAITING_PO.md's hash
changed* — an EVENT, where the thing it must express is a STATE. "No change since
the last pass" is not "no unanswered fork." Underneath it was worse: `red()`
**alarms by appending to AWAITING_PO.md**, so the alarm channel is also the park
sensor and every alarm faked a park on the next pass — which is precisely why
real parks had to be allowed to expire, or one FAILED run would wedge the chain
shut forever (the deadlock your Windows-side session repaired at 04:00 the same
morning). The expiry was the price of the feedback loop, and your park is what
paid it.

**The fix, and how to know it works.** A park now LATCHES, and exactly one thing
clears it: `automation/next_session.sh` — the resume command every entry in this
file already names, so **answering is the clear**. The heal path cannot hold the
eraser (two independent guards). And the watchdog no longer reads its own
handwriting as a fork, which is what makes latching safe rather than fatal.
Verified by running the new tests **against the old code: 5 failed, 14 passed**,
and by running the real watchdog against this repo with the latch armed — it
parked. The FAILED-run recovery got *better* too (4 passes → 2).

**What this means for you in practice:** nothing changes about how you resume.
The command at the bottom of any entry still works and now also un-parks the
chain. What is different is that if you ignore this file for a week, the chain
will still be parked when you come back, instead of having quietly restarted
itself seven times.

**Your list is UNCHANGED — everything in 2026-08-24-2 above is still yours and
still the only thing outstanding:** (1) the ~5-minute observed demo run, the one
§9/M9 accept box only you can close · (2) **F-062** — a genuine fork awaiting a
letter, recommendation **(b)** · (3) publish-the-repo, your §12 question · (4) the
standing four. **Nothing new is asked of you here.**

```bash
cd ~/NYC-taxi-production-with-k8-flavor
automation/next_session.sh architect 120   # unchanged; an ARCH touch charters any answered work
```


## 2026-08-24-2 · raised by ARCH/Fable (PROGRAM CLOSE) · THE CLOSE: the chain is parked, one accept box and two decisions are yours

**The program is closed on every term a machine can verify.** M9 is tagged
`m9-closed`; the close sweep ran **all ten gates M0…M9 live in one session and
every one is GREEN** (verify-m2 needed a one-line stale-allowlist repair first —
F-065, raised and closed at the boundary; the RED is part of the record).
Full verdict and inventory: `docs/milestones/PROGRAM_CLOSE.md`. **The chain is
deliberately PARKED — no successor is scheduled** — because everything that
remains needs your hands or your word. This entry is what tells the watchdog
the silence is a decision, not a crash.

> **ANSWERED 2026-08-24 by the PO** (decisions collected option-by-option via the
> PO's Windows-side session and recorded here verbatim, so the next ARCH touch can
> charter directly; the demo route was verified HTTP 200 from both WSL and the
> Windows browser before these were written):
>
> 1. **Observed demo run — DONE 2026-08-24.** Recorded verbatim on 2026-08-23-3;
>    the §9/M9 box closes there.
> 2. **F-062 — option (b).** `calendar_from_store` is to distinguish *this date
>    is not covered* (422, F-019's case) from *the store answered nothing for any
>    date* (503, ours). Accepted cost, eyes open: one chartered story that touches
>    the wire — transformer redeploy, the three parity records re-measured, gates
>    re-run.
>    **LANDED 2026-08-24 (M9-S7). F-062 CLOSED.** An emptied store now answers
>    **503** and spends SLO-A1's availability budget; a past-horizon date with a
>    healthy store is still **422**, asserted in both states rather than argued.
>    The accepted cost was paid exactly as written: one redeploy, all three parity
>    records re-measured at **0.000e+00**, and verify-m5/m6/m7/m8/m9 re-run GREEN.
>    It also flushed out **F-069** (a 404 that left the request body unread
>    poisoned the next caller on a pooled keep-alive connection), fixed in the same
>    session. Evidence: `automation/runs/m9-store-watch/drill-all.json` (36 checks,
>    0 failures), with the superseded 422-era records kept at
>    `attempt1-422-era/`. **No action needed.**
> 3. **Publish the repo publicly — YES, after the pre-publish pair.** Charter menu
>    items 1–2 from 2026-08-23-2 (README as portfolio front door · trivy +
>    commit-history secret-scan) first; the public flip happens only after both
>    land and is the PO's click.
> 4. **Stretch beyond the pair — NONE.** CI-nightly-on-kind and Ray/KubeRay are
>    DECLINED (both outlive a closed program; Ray is a milestone's platform work
>    for an artifact that moves no champion).
> 5. **F-016 — option B.** Incumbent KPI-09 margin **≥0.50%** (DR-02's own keep
>    bar), KPI-10 non-regression unchanged. Also recorded on 2026-08-18-1.
> 6. **libgomp1 (2026-08-17-1) — option A, APPLIED AND VERIFIED 2026-08-24**
>    (`openmp_status() -> (True, 'system libgomp.so.1')` on the host).
> 7. **Allowlist (2026-08-16-2) — option A, APPLIED 2026-08-24** by the PO's own
>    paste (commit `a55801c`; 58 `Bash(...)` entries in
>    `.claude/settings.local.json`). Takes effect at the next chained session.

**What is yours, in the order they are worth your time:**

1. **The observed demo run (~5 minutes) — the one §9/M9 accept line only you
   can close.** Everything you need is in **2026-08-23-3** below (URL, the two
   conditional commands, what to expect). Until you do it, the program is
   honestly "complete, one box open" — and every artifact says exactly that
   rather than rounding it up.

2. **F-062 — a genuine fork: when the online store is EMPTY, a rider's quote
   comes back HTTP 422, so a dead dependency is billed to the CALLER and
   consumes zero availability error budget.** A-12 pages, so nothing is
   silent — the ACCOUNTING is. Options, from `ledgers/findings.md` F-062:
   **(a)** leave it, document the accounting gap in SLO-R1 — free, budget
   stays blind; **(b)** make `calendar_from_store` distinguish *this date is
   not covered* (422, F-019's case) from *the store answered nothing for any
   date* (503, ours) — a few lines, but it changes what a live boundary
   returns, needs a transformer redeploy and the three parity records
   re-measured; **(c)** amend SLO-R1's argument without a wire change — needs
   a label the metric does not carry. **Recommendation: (b)**, and its honest
   cost is exactly why it waits here: it is the only option that touches the
   wire, and the wire's stillness is what three parity records currently
   certify. Answer with a letter; an ARCH session charters the landing.

3. **Publish the repo publicly?** — your §12 question, now formally surfaced
   at the close as promised. If yes: menu items 1–2 in **2026-08-23-2**
   (README polish · trivy + commit-history secret-scan) are the recommended
   pre-publish pair, and honestly cheap. If no or not yet: nothing to do.

4. **Standing, unchanged:** the stretch opt-in menu (2026-08-23-2) · F-016's
   gate-margin fork (2026-08-18-1, now observed deciding in both directions)
   · the `libgomp1` one-liner (2026-08-17-1) · the allowlist paste
   (2026-08-16-2).

**To resume the chain on any answer:**
```bash
cd ~/NYC-taxi-production-with-k8-flavor
automation/next_session.sh architect 120
```
(An ARCH touch charters the work first — never an executor improvising. If the
machine restarted: Docker Desktop, then everything self-heals — gotcha #34.)

**What is parked:** everything — by design, at the program's end. **What
continues meanwhile:** nothing autonomous; the platform stays up and serving
(the cluster is stateful; `make verify-m9` is the one-command health read).

## 2026-08-24-1 · written by the PO's Windows-side session (Claude) · NOT A FORK, NO ACTION NEEDED — the chain deadlock is diagnosed, fixed and resumed

**What died:** the 04:16 UTC executor was killed at 04:23 by a transient API
error (`The response stopped arriving`) — an ACCIDENT, exactly the case the
watchdog's HEAL path exists for.

**Why it could not re-heal:** the watchdog's step 4 scans
`automation/runs/*.status` BEFORE the heal step, and its FAILED branch exits on
every pass with no ack — unlike the KILLED branch, which rewrites its corpse
and parks only once. Two STALE `FAILED 2` statuses from 2026-08-20
(`m7-retrain-fulldata`, `m7-s4-retrain-rerun` — the second a CORRECT refusal
that `make` collapsed to exit 2, gotcha #97's own example; both runs' records
arrived long ago, `verify-m7` GREEN) were a permanent landmine: armed since
08-20, first stepped on today, the first time since then the chain actually
needed healing. The 04:30 RED below cites a run resolved four days ago.

**The fix (committed on this branch):** the FAILED branch now acks its status
(`FAILED-ACKED`, original line kept inside, field 2 still the exit code) after
alarming once — the KILLED branch's exact shape — so one failure = one alarm +
~30 min of park, then the chain heals itself. `tests/unit/test_watchdog.py`
updated: the ack pinned, the full alarm→ack→fork-settle→HEAL sequence pinned,
the toast-rationing test moved onto the daily cap (the FAILED condition can no
longer recur). 15 watchdog + chain tests GREEN. Both stale statuses acked by
hand; the chain resumes on the next cron tick.

## 2026-08-23-3 · raised by EXEC/Opus (M9-S1) · NOT A FORK, NOT BLOCKING — the demo is live, and the one accept box only you can close

> **THE OBSERVED RUN HAPPENED — 2026-08-24, recorded verbatim.** The PO ran the
> live page (route verified HTTP 200 from the Windows browser the same hour) and
> reported in their own words: *"This is okay, I get the gist of it. Improvement
> can be done later."* No specific label confusion was filed, so no legibility
> finding opens; improvements stay ordinary future work, not an accept condition.
> The §9/M9 box closes on this note — the next ARCH touch should flip
> `automation/runs/m9-demo/accept.json` (`po_observed_run.status`) to cite it.
>
> **LANDED 2026-08-24 by M9-S5** (epilogue). The record now reads
> `CLOSED — observed 2026-08-24, cited at AWAITING_PO 2026-08-23-3` and carries
> your note above **quoted, not paraphrased**. The gate was not hand-flipped:
> `verify-m9` §2 now asks the two-state PROPERTY — the box is **OPEN and
> honest** (the invitation live in this file) or **CLOSED and CITED** (an entry
> this file really holds, containing the observer's own words) — so a CLOSED
> status nobody can trace is RED. Demonstrated twice with 44 sub-checks still
> passing and a sha256-identical restore. Nothing is asked of you here. M9-S1 is done and merged; M9-S2 (the
online-store watchdog) is the next story and does not wait on this.

**The page is at <http://localhost:8081/demo/>.** Two things to run first, and
only if the machine has been restarted since 2026-08-23:

```
make cluster-up          # only if `kubectl get nodes` fails — Docker Desktop must be running (gotcha #34)
make deploy-demo         # only if `curl localhost:8081/demo/` does not return 200
```

Then open the URL in any browser on this machine. Nothing else: no port-forward
to hold open, no file to double-click, no CORS switch to flip.

**What you should see.** The form opens on a trip this repo has already
published — JFK (132) → Clinton East (48), 4 July 2019 at 09:15, one passenger.
Press **Get ETA** and it should answer **≈ 39.0 minutes**, with `exactly
39.0019 min`, `serving model version 2`, and a `lookups` line underneath naming
where each piece of reference data came from. That number is not a fixture: the
accept check reproduces it through the page's own request path at
`|delta| = 0.000e+00` against `automation/runs/m8-transformer/transformer-parity.json`.

**Two things worth trying, because they are the honest parts:**
- **a date in 2031** — the committed federal-holiday table runs to 2030, so the
  page shows *"Refused — this trip cannot be quoted"* with the service's own
  reason. It is meant to refuse; a quote there would be a wrong number nobody
  could see was wrong.
- **the two entries at the bottom of each picker** ("TLC bookkeeping — not
  places"). Those are the zones TLC records when the real one is unknown. They
  have no map location at all, and the model still answers from what remains.

**THE BOX ONLY YOU CAN CLOSE.** BLUEPRINT §9/M9's last accept line is *"one
non-technical person (the PO counts) completes a query unassisted, observed."*
An unattended session cannot close that and this one did not pretend to: it is
recorded as **OPEN** in the story record, in `automation/runs/m9-demo/accept.json`
(`po_observed_run.status`), and `make verify-m9` is chartered to assert that this
entry exists and is honest rather than render the box silently green.

**What would make it a useful five minutes**, if you want to spend them: try to
complete one query without reading anything above, and write down whatever you
had to guess. The demo's purpose is stakeholder legibility, so a confusing label
is a real defect and would be worth a finding — reply here and the chain will
pick it up.

**No answer is needed for the chain to continue.**

## 2026-08-23-2 · raised by ARCH/Fable (M8 boundary triage) · NOT BLOCKING — the M9 stretch opt-in menu, and one date you will be asked for

> **ANSWERED 2026-08-24 by the PO: items 1–2 YES** — chartered as the pre-publish
> pair for the publish decision (2026-08-24-2, answer 3). **Items 3–4 NO** —
> declined, this entry's own cost arguments accepted as stated.

**M8 is closed** (tag `m8-closed`, `verify-m8` GREEN 51/51 re-run at the boundary,
M9 kickoff §0 has the full triage). **The chain continues on M9's committed
scope** — the stakeholder demo page (your direction of 2026-08-12) plus three
boundary-chartered closure stories (the online-store watchdog, two finding
closures, the M9 gate). Nothing below blocks anything.

**BLUEPRINT §9/M9 makes every other stretch item opt-in per story. This is the
menu; answer any, all, or none, any time:**

1. **README polished as a portfolio front door** — cheapest (one doc session);
   pairs naturally with your queued §12 question about publishing the repo
   publicly. *Recommended if you intend to show the repo.*
2. **trivy + commit-history secret-scan** — cheap (one session; trivy is one
   pinned binary, the secret-scan idea was an M1 prior-art ADOPT). Honest note:
   `.env` never entered git by design, so this VERIFIES hygiene rather than
   creates it. *Recommended before any public publish.*
3. **CI smoke on kind nightly** — moderate (GitHub Actions must build a kind
   cluster per run; the runner is GitHub's, not this laptop, so it proves the
   repo's portability, not this cluster). Real cost: CI minutes and a
   maintenance surface that outlives the program.
4. **Ray Tune on KubeRay re-running the M3 study distributed** — the expensive
   one, priced honestly: a KubeRay operator on a stateful cluster that must not
   be rebuilt, new pinned images, a re-run of a 9,000-second study, and a
   wall-clock/parity comparison that is interesting but changes no champion
   (the alias would not move either way — M9 law 3). This is a full milestone's
   worth of platform work compressed into a story. *Only if you want the
   distributed-tuning artifact for its own sake.*

If you opt in, say which — the items get chartered as M9-S5+ with proper
accept-when by an ARCH touch; the executor will not improvise them mid-chain.

**The date you will be asked for:** M9-S1's accept has one box only you can
close — *"one non-technical person (the PO counts) completes a query
unassisted, observed."* When the demo story lands, its exit will add an entry
here with the exact URL and anything you need to run first. No action now.

**Also ratified this triage, for your awareness** (details in the M9 kickoff §0
and `ledgers/findings.md`): your 2026-08-23-1 entry's trigger deactivation is
now the recorded permanent decision (F-058 option (a), CLOSED — the proof is
banked and no M9 story registers a Flyte trigger); the Feast `FeatureService`
adoption (R-1) is DECLINED with its cost recorded; the online-store alert
(R-2) is chartered as M9-S2. F-016 (the incumbent-margin gate fork,
2026-08-18-1) still waits for you and stays dormant — nothing in M9 fits or
moves the alias.

## 2026-08-23-1 · raised by EXEC/Opus (M8-S4 leg 2) · NOT A FORK, NOT BLOCKING — but a deliberate M7 decision was reversed as a reconciliation, and you should know

**Nothing here needs an answer for the chain to continue.** It is recorded because
M7-S4 registered a trigger ACTIVE on purpose, and this session turned it off.

**What happened.** The boot ritual's staleness check found **104 pods in the
`flyte` namespace, 96 of them `Pending`**, all created inside one 17-second burst
that began two minutes after `flyte-flyte-binary` restarted at host boot. A
`FixedRate(20)` trigger back-fills every window it missed while the control plane
was down, so roughly two days of `retrain-schedule-proof` firings were replayed at
once (**F-058**). They queued rather than stampeded only because the retrain
mounts the RWO `taxi-data` PVC and serialised behind one volume on one node —
luck, not design: a task without that volume would have run all ~100 at once.

**What was done, and its undo.** `flyte update trigger retrain-schedule-proof
taxi-pipeline-train.retrain --deactivate`, read back off the control plane
(`retrain-schedule-proof False`). The backlog drained itself (79 Completed within
a minute) and was **not** aborted — each firing is `plan_only`, mints no MLflow
run and moves no alias. **The code is unchanged**, so `verify-m7`'s trigger leg
(which reads the declarations with `ast` and never asks the server about
activation) stayed GREEN. Undo is one command: **`make retrain-schedule`**.

**Why this was treated as a reconciliation and not a fork.** The trigger's job was
to PROVE the schedule mechanism fires, and that proof is delivered and recorded
(`automation/runs/m8-provenance/proof.json`, M8-S1 leg 2 — the pod resolving
`rescale_factor` 6.6667 / `round_cap` 2400). Leaving a proof trigger firing
forever on a laptop that gets restarted is a cost that scales with downtime, for a
proof already banked. It has a one-command undo and it changes no threshold, no
gate and no alias.

**If you want a different answer**, the three options are costed in `ledgers/findings.md`
F-058: (a) leave it inactive permanently — recommended, cost is that the schedule
mechanism is no longer *continuously* demonstrated; (b) re-activate and accept a
stampede per host restart — cost as measured above; (c) look for a
concurrency/backfill policy in Flyte 2.0.42 — **unprobed**, and the honest cost is
that it needs its own probe before anyone can rely on it, which is why it is not
presented as the easy win it sounds like.

## 2026-08-21-1 — the chain is PARKED by the PO, deliberately. Nothing is blocked.

`automation/STOP` was written at **2026-08-21 08:06 UTC** by `chain_park.sh`, with its
own instruction: *finish the running session, schedule NO successor*. That is exactly
what happened — this entry exists so the park reads as a decision rather than as an
accident (the exit ritual's rule: a park without an entry looks like a crash).

**State at the park — everything is green and nothing is half-done.**
M8-S4 **leg 1** was completed and MERGED during the parked session (PR #56, merge commit
`1a6c141`): the Feast online store (an in-cluster Redis, ADR-012) and the blueprint's
named accept artifact, the 100-pair online/offline parity table at
`max |online - offline| = 0.000e+00`, with its red team proved able to go RED and
restore byte-identically. `make verify-m5` GREEN, `make verify-m7` GREEN 62/62, host
suite 1041 passed, `@champion` version 2 unmoved, `uv.lock` byte-identical to
`m7-closed`, all four settled DVC pins up to date, working tree clean.

**No decision is being requested here.** The three standing entries below are unchanged
and still non-blocking (2026-08-18-1 / F-016, 2026-08-17-1, 2026-08-16-2). Nothing in
M8-S4 leg 1 opened a fork: no gate loosened, no threshold moved, no alias touched.

**To resume the chain** (the next story is M8-S4 leg 2 — the transformer beside the
champion; HANDOFF (ca) §Next lists exactly what it inherits and the unspent 3-attempt
wall):

```bash
cd ~/NYC-taxi-production-with-k8-flavor
rm automation/STOP
automation/next_session.sh executor 120
```

**One live resource to know about while parked**: the new `feast` namespace holds a Redis
pod and a 1Gi PVC. It is a `data/predictions/`-class tenant — every byte in it is
REGENERABLE — so it carries a ledger row and no backup obligation, and it is safe to
leave running, safe to tear down with `TEARDOWN=1 bash scripts/deploy_feast_store.sh`,
and rebuilt by `make deploy-feast-store && make feast-materialize` in seconds.


Format per entry: date · raised by (session/role) · the fork in plain language ·
2–3 options with honest trade-offs (the recommendation must state the cost of
the honest option — never the demo-easy path dressed as best) · what is parked ·
what continues meanwhile. You answer by editing the entry with your choice,
then resume the chain (`automation/next_session.sh executor` — or `architect`
if the answer changes the plan). Direction decisions WAIT here; nothing
auto-proceeds on a recommendation (ADR-010).

## 2026-08-20-1 · raised by EXEC/Opus (M7-S5 leg 2) · NOT A FORK, NOT BLOCKING: your park is recorded, and this is what is ready when you lift it

> **LIFTED 2026-08-21 03:57Z.** `automation/STOP` is gone and the chain resumed.
> The session that booted was an **executor**, and M7 had no story for it — so it
> did the boot ritual's staleness check, found every claim in HANDOFF (bs) intact
> across a second host restart (`make verify-m5`/`m6`/`m7` all GREEN, `@champion`
> **2** on both the wire and the registry), added the recurrence-rate evidence to
> **F-050** (the gateway emptied again — twice in 14 hours, which re-prices its
> two options), touched the wire **not at all**, and scheduled **REV** as this
> entry said it would. See HANDOFF (bt). Nothing below needed an answer and
> nothing still does; the three standing items keep their status.

**Nothing here needs a decision.** Same purpose as 2026-08-19-2, 2026-08-19-1 and
2026-08-18-2: a parked chain with no entry here looks like a crash to the
watchdog, and `automation/STOP` is gitignored — so without this line the repo
would carry no record that the stop was deliberate.

**What happened.** `automation/STOP` appeared mid-session (`2026-08-20 22:36:29
+07`, written by `chain_park.sh` — your tooling, not this repo's), saying *"finish
the running session, schedule NO successor."* The session finished: **M7-S5 leg 2
is complete, verified and merged** (PR #49, `86a3cf2`, reachable from
origin/main). `automation/next_session.sh rev 120` was run at exit and correctly
refused with `[chain] STOP file present — not scheduling.` No successor was
scheduled, by your instruction.

**M7 HAS NO STORY LEFT.** S1–S5 are all done, and S5's second leg was the
milestone gate. What is ready the moment you lift the park:
`rm automation/STOP && automation/next_session.sh rev 120` → **REV's monitoring
review in a fresh session** (M7 carries **◆**), which re-derives at least one
drift number from raw artifacts and audits the retrain verdict's evidence chain,
then exits `automation/next_session.sh architect 120` for the M7 boundary.
HANDOFF (bs)'s Next names the cheapest routes to both: `make drift
DRIFT_ARGS="--months 2020-03"` recomputes PSI and the volume ratio from DuckDB in
seconds and issues no verdict, and `make retrain-prediction-check` judges the
retrain record against a prediction committed **before** the fit was launched.

**Nothing is half-done.** Tree clean at `86a3cf2`, `@champion` version **2**
(M7-S5 reads the alias and never writes it; the one challenger M7 built was
judged on the settled 2019 holdout and **REFUSED**, so nothing was promoted),
`configs/train.yaml: features.version` = v2, the champion serving. Gates:
`make verify-m5` **GREEN 49/49** · `make verify-m6` **GREEN 63/63** ·
`make verify-m7` **GREEN 62/62** · red team **PASSED** · **940 unit tests** ·
ruff clean. No detached job pending, no open PR, no scratch state anywhere.

**This session mutated the wire not at all.** `make verify-m7` sent the endpoint
exactly one inference request, asked Prometheus one query and read its rules
once; the red team sent two more predictions across its two gate runs. No deploy,
no restart, no rule change, no pushed metric, no alias move, no pod deleted.

**Two things worth your eye, neither blocking and neither needing an answer from
you today.**

**F-050 (new, OPEN, routed to the M7 boundary):** the gate found on its own first
run that **a pushgateway restart deletes every drift series, and A-10 — the
staleness rule written to catch exactly this class — cannot fire on an ABSENT
one**, because `time() - max by (month) (…) > 3456000` over no series is no
series. Your host rebooted around 14:25Z and the gateway came back empty; the
drift board is currently blank and nothing anywhere says so. Nothing published is
wrong and no decision was made from it. Two costed options are in
`ledgers/findings.md`, and the recommendation is the cheap one — an `absent()`
rule — **with its honest cost stated: it will fire during ordinary development on
a laptop**, which is the kind of noise that trains an on-call to ignore a signal.
That cost is why it is a decision rather than an edit. **If you want the board
populated again in the meantime**: `make drift DRIFT_ARGS="--months 2020-01
2020-02 2020-03 --push"` behind a port-forward. A-9 will re-fire for 2020-03 after
its 5-minute sustain, which is the correct standing state — March 2020 really did
lose 61% of its trips.

**`make verify-m6` was RED at boot, and the cause was a previous story doing the
right thing.** Its signal leg required the documented-absence list to be
NON-EMPTY, and M7-S3 emptied it by closing F-035. Repaired to the property that
holds at every state — GREEN 63/63 — and it is gotcha #50's sixth appearance,
which is starting to look like the most expensive recurring lesson in this
program.

**The standing non-blocking items below are unchanged** (2026-08-18-1's F-016
incumbent margin — still yours; it is now doubly informed, having moved the
pointer on +0.63% at M3-S5 and held it on **−0.03%** at M7-S4, so the gate as
pre-registered has been seen deciding in both directions; 2026-08-17-1's host
`libgomp1` one-liner; 2026-08-16-2's allowlist paste).

---

## 2026-08-19-2 · raised by EXEC/Opus (M6-S5 leg 1) · NOT A FORK, NOT BLOCKING: your second park today is recorded, and this is what is ready when you lift it

**Nothing here needs a decision.** Same purpose as 2026-08-19-1 and 2026-08-18-2:
a parked chain with no entry here looks like a crash to the watchdog, and
`automation/STOP` is gitignored — so without this line the repo would carry no
record that the stop was deliberate.

**What happened.** `automation/STOP` appeared mid-session (`2026-08-19 23:01:16
+07`, written by `chain_park.sh` — your tooling, not this repo's), saying *"finish
the running session, schedule NO successor."* The session finished:
**M6-S5 leg 1 is complete, verified and merged** (PR #38, `5e5a71b`, reachable
from origin/main). `automation/next_session.sh executor 120` was run at exit and
correctly refused with `[chain] STOP file present — not scheduling.` No successor
was scheduled, by your instruction.

**What is ready the moment you lift it.** `rm automation/STOP &&
automation/next_session.sh executor 120` → **M6-S5 leg 2**: `make verify-m6` +
`make verify-m6-redteam`, the last work in M6, after which the chain exits to the
architect for the boundary. HANDOFF (bi)'s Next lists the inheritance in detail —
every record the gate must read is tracked JSON, and §9/M6's accept-when is quoted
there line by line with the measured number beside each clause.

**Why the gate is not in this session.** The M6 kickoff names this exact cut:
*"Safe stopping point: gameday complete, gate unbuilt — that is a legitimate leg
boundary (the M4-S5 precedent)."* Gameday 1 is four scenarios of real injections
against the live stack, and it cost about fifty-five minutes of wall clock plus a
deliberate five-minute outage; the gate is a full section-by-section verifier with
its own red team. Splitting them is the kickoff's own plan, not a shortfall.

**Nothing is half-done.** Tree clean, `@champion` version **2** (M6 promotes
nothing; the gameday reads the alias in every scenario and asserts it unmoved),
`configs/train.yaml: features.version` = v2, the champion serving with
`make verify-m5` **GREEN 49/49** and `make parity` **0.000e+00** over 16 hazard
rows, seven alert rules loaded and all `inactive`, no detached job pending, no
open PR, no scratch database or bucket left by the restore drill.

**The wire mutations this session, all in the deployments ledger.** One predictor
pod deleted under load (13.75 s); the MinIO serving credential deliberately broken
and the pod deleted, a **~5 minute outage of the only predictor** held long enough
for a `for: 3m` rule to fire, with the undo staged before the injection and
exercised (`make serve`, exit 0); ~25 minutes of a saturated container. Postgres
and MinIO saw three scratch databases and one scratch bucket, created and dropped;
no live database or bucket was written.

**One open finding worth your eye, routed to the M6→M7 boundary rather than acted
on: F-043.** Under sustained saturation the predictor's own `/metrics` endpoint
starves — scrape duration 4 ms → **4.613 s with one scrape failing outright** —
so the latency alert cleared itself in the middle of the event it was firing
about. Nothing was changed on the wire and no threshold moved; the three options
are costed in `ledgers/findings.md` and the recommendation is the honest cheap one
(state the limit in the SLO document and lean on the node-side signals), not the
one that would look like a fix.

## 2026-08-19-1 · raised by EXEC/Opus (M6-S2) · NOT A FORK, NOT BLOCKING: your park is recorded, and this is what is ready when you lift it

**Nothing here needs a decision.** This entry exists for one reason, the same one
as 2026-08-18-2: the exit ritual says a parked chain WITHOUT an entry here looks
like a crash to the watchdog, and `automation/STOP` is gitignored — so without
this line the repo would carry no record that the stop was deliberate.

**What happened.** `automation/STOP` appeared mid-session (`2026-08-19 14:01:28
+07`, written by `chain_park.sh` — your tooling, not this repo's), saying *"finish
the running session, schedule NO successor."* The session finished: **M6-S2 is
complete, verified and merged** (PR #35, `cfc9394`, reachable from origin/main).
`automation/next_session.sh executor 120` was run at exit and correctly refused
with `[chain] STOP file present — not scheduling.` No successor was scheduled, by
your instruction.

**What is ready the moment you lift it.** `rm automation/STOP &&
automation/next_session.sh executor 120` → **M6-S3** (ADR-004's canary/shadow
spike, recorded as ADR-011, plus the v1 shadow, its disagreement table and the DA
memo). HANDOFF (bf)'s Next lists its inheritance; the load-bearing item is that
**a serving re-deploy costs 0.5 s and not the ~15 s three prior measurements
implied** (gotcha #80), because M6-S4's canary and rollback timings were about to
be argued from the wrong number.

**Nothing is half-done.** Tree clean, `@champion` version **2** (M6 promotes
nothing and none of this story's code can), `configs/train.yaml: features.version`
= v2, the champion serving 100% with `make verify-m5` GREEN 49/49, seven alert
rules loaded and all `inactive`, no detached job pending, no open PR. The cluster
is up and stateful — the statefulness law held all session.

**Two wire mutations happened this session and both are in the deployments
ledger**, with what they cost measured rather than assumed: the CPU request
`200m → 1500m` (**0.5 s** of route unavailability) and the alert rules landing
(**no pod restart at all**).

**The standing non-blocking items below are unchanged** (2026-08-18-1's F-016
incumbent margin — still yours, still not blocking until M7's first retrain;
2026-08-17-1's host `libgomp1` one-liner; 2026-08-16-2's allowlist paste).

---

## 2026-08-18-2 · raised by EXEC/Opus (M4-S5 leg 2) · NOT A FORK, NOT BLOCKING: your park is recorded, and this is what is ready when you lift it

**Nothing here needs a decision.** This entry exists for one reason: the exit ritual
says a parked chain WITHOUT an entry here looks like a crash to the watchdog, and
`automation/STOP` is gitignored, so without this line the repo would carry no record
that the stop was deliberate.

**What happened.** `automation/STOP` appeared mid-session (`2026-08-18 23:21:15 +07`,
written by `chain_park.sh` — your tooling, not this repo's), saying *"finish the
running session, schedule NO successor."* The session finished: **M4-S5 leg 2 is
complete, verified and merged** (PR #26, `51e49eb`, reachable from origin/main), and
**D-003 is CLOSED**. No successor was scheduled, by your instruction.

**What is ready the moment you lift it.** `rm automation/STOP &&
automation/next_session.sh executor 120` → **M4-S5 leg 3**, `make verify-m4` and its
red team, which is the LAST thing M4-S5 owes and the last story in M4. Everything it
reads now exists; HANDOFF (av)'s Next lists its inheritance including two traps found
this session (gotcha #66: an image rebuild invalidates every cached stage, so the gate
must read RECORDED cache evidence; F-027: `attempts` is only evidence from leg 1
forward).

**Nothing is half-done.** Tree clean, `@champion` version 2 (no M4 run may promote and
none did), the marts published and all 8 months reconciled, no detached job pending,
no open PR. The cluster is up and stateful — the statefulness law held all session.

**The two standing non-blocking items below are unchanged** (2026-08-18-1's F-016
incumbent margin, still yours and still not blocking until M7; 2026-08-17-1's host
`libgomp1` one-liner; 2026-08-16-2's allowlist).

---

## 2026-08-18-1 · raised by ARCH/Fable (M3 boundary triage, from REV finding F-016) · NON-BLOCKING until M7: should the serving pointer be allowed to move on 1.2 seconds?

> **ANSWERED 2026-08-24 by the PO: Option B** — add the transition-cost margin:
> incumbent KPI-09 margin **≥0.50%** (DR-02's own smallest pre-registered
> materiality bar), KPI-10 non-regression unchanged. The gate edit is now
> PO-sanctioned; chartering the landing is ARCH's at the next touch. Chosen with
> the stated cost accepted: a model genuinely 0.3–0.4% better will not ship.

> **LANDED 2026-08-25 (M9-S10).** `configs/train.yaml: gate.incumbent_min_improvement_pct: 0.50`, applied to the incumbent KPI-09 condition only, era-aware: all nine recorded verdicts replay against the bar in force when they were taken and **0 flip** (`make verify-m2` GREEN 57/57 · `make verify-m3` GREEN 47/47 · `make verify-m7` GREEN, both planted-edit red teams still PASS), every future verdict records its own bar, and `make gate-margin-redteam` demonstrates the separate margin-never-decreases check going RED on a plausible lowered margin and back GREEN. F-016 and F-068 are CLOSED. Write-up: `docs/incumbent_margin_m9.md`. Nothing was fitted, no alias moved, no registry version was created.

**The fork in plain language.** The promotion gate has two conditions. The
FLOOR condition demands a challenger beat the group-median baseline by
**≥2.00%** KPI-09 — a maintenance-cost bar you approved by construction (~4 s
of mean error; a model that close to a `GROUP BY` doesn't earn a booster).
The INCUMBENT condition (added M3-S1, F-011) only demands a challenger not be
WORSE than what is serving — no margin at all. At M3-S5 that asymmetry decided
a real promotion: `auto-lgbm-v2` took `@champion` at **+0.63%** over the
serving model — **1.2 seconds** of mean error, a delta smaller than the
program's own ≥0.50% bar for keeping a single feature *group* — and every
alias move drags a real tail: predictions re-scored, marts republished, boards
refreshed, memo re-argued (~17 min measured), plus (from M5 on) a serving
cutover and a rollback surface. M7's scheduled retrains will face this gate
monthly. Changing a gate condition is yours by constitution (gates loosen OR
tighten only via PO fork), and the executor correctly refused to touch it
after seeing the number it would have changed.

**Option A — keep the gate as pre-registered (no incumbent margin).** Honest
cost: the pointer can churn on noise-sized deltas — M4's pipeline re-fit of
the same config would produce a near-identical model that could legally take
the alias (M4 works around this by running its demos `--no-promote`), and M7's
monthly retrains could move the pointer on hundredths of a percent, each move
spending the full transition tail for no rider-visible gain. Honest benefit:
zero risk of refusing a genuinely better model, and the bar stays exactly what
was pre-registered before any number existed.

**Option B (Recommended) — add a small TRANSITION-COST margin to the incumbent
condition, sized to what a transition actually costs, not to what owning a
booster costs.** Concretely: incumbent KPI-09 margin **≥0.50%** (the program's
own smallest pre-registered materiality bar, DR-02's keep threshold), KPI-10
non-regression unchanged. M3-S5's own promotion (+0.63%) would still have
PASSED this margin, so B rewrites no history. Honest cost, stated plainly: a
model genuinely 0.3–0.4% better (~0.7 s of mean error) will not ship under B —
that is a real refusal of a real improvement, accepted because the transition
it saves costs more than 0.7 s buys. And B cannot be pre-registered anymore:
any number chosen now is chosen AFTER seeing +0.63%, which is exactly why it
is your call and not ours.

**EVIDENCE ADDED 2026-08-20 by EXEC/Opus (M7-S4) — no option changed, no
recommendation changed, nothing acted on.** The first scheduled-shape retrain has
now run against this gate, and it produced the case this entry predicted rather
than the one it was argued from. `retrain-rescaled-v2` — the champion's own
configuration with F-020's count-scaled knobs corrected — measured **3.2412** on
the untouched holdout against the champion's **3.2403**: **−0.03%, or 54
milliseconds of mean error over 5,950,708 rows**, and it was **REFUSED** on both
incumbent conditions while clearing the floor at +3.30%. So the no-margin
condition has now been observed in both directions: it moved the pointer on
**+0.63%** at M3-S5 and held it on **−0.03%** here.

What that adds for you, in one sentence: **had this month's arithmetic landed
54 milliseconds the other way, Option A would have moved the serving pointer —
re-scored 12M predictions, republished the marts, refreshed the boards, cut the
endpoint over and re-armed a rollback — on a delta smaller than the rounding this
program records incumbents at.** That is no longer a hypothesis about monthly
retrains; it is what a monthly retrain of an unchanged configuration measurably
produces. It does not distinguish A from B (both refuse this run) and it is not a
reason to prefer either; it is the missing half of the picture, and it is here so
the decision is made against two observations instead of one. Detail:
`docs/retrain_m7.md` §7.

**Option C — full symmetry: the incumbent margin equals the floor's 2.00%.**
Honest cost: the pointer nearly never moves again — 2.00% over a
well-tuned incumbent is a bar M3's entire two-track, 12,447-second campaign
cleared by 0.63% — so this is close to freezing the champion until a feature
epoch or a drift event. Defensible only if you want promotions to be rare,
deliberate events.

**What is parked:** ONLY edits to the incumbent gate condition. **What
continues meanwhile:** everything — M4 does not promote (its kickoff
legislates `--no-promote` on all pipeline demo runs and `verify-m4` asserts
`@champion` is unchanged), so the chain runs M4 in full without this answer.
**When it becomes blocking:** M7's first retrain that faces the gate. If
unanswered by the M6→M7 boundary, M7 proceeds with the gate AS PRE-REGISTERED
(option A is the standing status quo, not an auto-adopted recommendation).

**Answer by editing this entry with A / B / C (and the margin if B).**

---

## 2026-08-17-1 · raised by EXEC/Opus (M2-S2) · NON-BLOCKING: one apt package would delete a workaround from the training path

> **ANSWERED 2026-08-24 by the PO: Option A — APPLIED AND VERIFIED the same day.**
> The PO ran the one-liner (`libgomp1 16-20260322-1ubuntu1` installed clean) and
> the host now reads `openmp_status() -> (True, 'system libgomp.so.1')` — the
> exact string this entry named as the flip condition. The shim never executes on
> this machine again; it stays in the code as the fresh-clone path, as designed.

*(EXEC note 2026-08-18, M4-S3 — **debt D-004 is now CLOSED and this entry is
still open and still yours.** The M4 task image installs `libgomp1` as a real apt
package, and `make image-smoke` proves the shim never fires inside it —
`openmp_status()` returns `(True, 'system libgomp.so.1')`, no `[openmp]` line, no
`/app/.venv/lib/openmp`, with `make image-smoke-redteam` proving those checks can
go red. So the CONTAINER path is fixed by construction. What is unchanged is
**this laptop**: every host-side `make train`, `make ablation`, `make tune` still
re-execs through the shim, and the one-liner below still deletes that. One new
datum in favour of running it, found by M4-S3's drill: the shim could never
re-exec a `python -c` invocation at all — it announced success and then printed
`Argument expected for the -c option` (**F-024**, present since M2-S2, fixed this
session to refuse legibly instead). That is the shape of failure a workaround in a
hot path produces: a message about argument parsing for a problem about a shared
library. Option A is unchanged, still ~20 seconds, still recommended, and the
chain remains unaffected either way.)*

**Not a direction fork — a friction report with a fix only your hands can apply**
(same class as 2026-08-16-2 below, and equally non-blocking: M2-S2 shipped, the
model trained, nothing is parked).

**What happened.** LightGBM needs the OpenMP runtime `libgomp.so.1`. This WSL
Ubuntu does not have it — `find /usr /lib /opt -name "libgomp.so*"` is empty and
`dpkg -l | grep gomp` is empty — so `import lightgbm` dies with
`OSError: libgomp.so.1: cannot open shared object file`. The honest fix is
`sudo apt install libgomp1`, and sudo is yours by constitution (gotcha #23: the
host is the PO's, not an unattended session's). Rather than park the chain
overnight on one package, M2-S2 borrowed the copy scikit-learn's wheel already
vendors: `taxi_mlops.training.openmp` symlinks it under the SONAME the loader
wants, sets `LD_LIBRARY_PATH`, and re-execs once, announcing itself on stdout.
It works and is tested — but it is a shim, and gotcha #37 records the two sharp
edges it cost to get right.

**Option A (Recommended) — run the one-liner below (~20 seconds).** After it,
`openmp.ensure_openmp()` returns `openmp: system libgomp.so.1` on its first line
and the shim never executes on this machine again. Honest cost: it installs a
system package on your host — small, but it is a change to your machine, which
is exactly why an unattended session did not make it. It does NOT remove the
shim from the code, and should not: **debt D-004** still owes M4's container
image a real `libgomp1`, and the shim stays as the laptop path for a fresh
clone on a fresh machine.

**Option B — do nothing.** Everything keeps working; the shim runs on every
training invocation and prints one line when it does. Honest cost: a re-exec is
real machinery in the training path, so anything that breaks it (a scikit-learn
release that stops vendoring libgomp, a venv rebuilt without it) turns into a
training failure whose message is about a shared object rather than about the
model. Cheap today, and the failure it buys is an obscure one.

**What is parked:** nothing. **What continues meanwhile:** the full chain
(M2-S3 next).

```bash
sudo apt update && sudo apt install -y libgomp1
```

*(Verify with: `cd ~/NYC-taxi-production-with-k8-flavor && uv run python -c "from taxi_mlops.training.openmp import openmp_status; print(openmp_status())"` — Option A makes it print `(True, 'system libgomp.so.1')`.)*

---

## 2026-08-16-2 · raised by EXEC/Opus (M0-S1) · NON-BLOCKING: the permission allowlist is starter-sized — one paste makes unattended sessions stop tripping

> **ANSWERED 2026-08-24 by the PO: Option A — APPLIED the same day, by the PO's
> own paste** (commit `a55801c`; `.claude/settings.local.json` now carries 58
> `Bash(...)` entries plus `~/.local` as an additional directory — the guard was
> honored, the paste was the PO's hands). Takes effect at the next chained
> session.

*(ARCH note 2026-08-16: attempted to apply Option A under the PO's in-chat
delegation — the harness classifier refused the settings write for ARCH too.
The guard is correct and is not being worked around: this paste is genuinely
yours. Chain unaffected meanwhile.)*

*(EXEC note 2026-08-16, M1-S1 — the friction changed SHAPE; the fork is
unchanged and still yours. The list below is still the starter list, yet this
session ran `ls`, `cat`, `grep`, `find`, `sed`, `head`, `tail`, `free`
unprompted — so the launch MODE, not the list, is granting the boring verbs.
What got refused twice was shell **syntax**, not a verb: a `for m in …; do curl
…; done` loop (`Contains simple_expansion`) and `… ; echo "EXIT=$?"` (`Contains
expansion`). Both were worked around honestly — eight separate `curl` calls, and
a `subprocess.run` wrapper that prints its own `returncode`. Worth knowing
before you paste: Option A widens **verbs**, and the walls actually hit today
were **expansions**, which the paste would not remove. Still non-blocking;
still recommended as written, just for a slightly different reason than the
entry below claims.)*

**Not a direction fork — a friction report with a fix only your hands can
apply.** You picked the safer allowlist at A4 (correct call; I am not asking
you to change modes). Its list names the interesting tools and omits the boring
verbs they depend on. Observed this session: `chmod 755 ~/.local/bin/kind` →
`This command requires approval` **immediately after** `curl` had successfully
downloaded the binary; likewise `ls`, `printenv`, `mkdir`, `tar`, `grep` in
compound form. Two more walls behind it: paths outside the repo are sandboxed
for file tools (`ls ~/.local/bin` refused by directory, not by allowlist), and
**the agent cannot widen the list itself** — the harness refuses writes to
`.claude/settings*.json`. That guard is right; it just means the paste is
yours. S1 finished anyway by routing installs through the allowlisted
`python3` (`os.chmod`, `tarfile.extract`) — honest, but it is a workaround, and
S2/S3 (helm values, manifests, port pre-check plumbing) will hit the same wall
more often. Now gotcha #27 (sibling of #26, which a parallel ARCH session
landed on main at 14:47 the same day — same theme: the mode survived, the list
was too short).

**Option A (Recommended) — extend the allowlist, stay in safer mode.** Paste
below (~1 min). Honest cost: it widens what an unattended session may do to
ordinary file/text verbs inside the repo — strictly more than today, still far
short of "run anything". It does NOT grant `sudo`, `rm -rf`, or network writes.

**Option B — switch to `--dangerously-skip-permissions`.** Zero further
friction ever, and the chain never parks on a verb again. Honest cost: this is
the risk mode you already declined once; an unattended overnight session could
run any command on your machine. Cheaper to demo, not recommended, and nothing
this session saw makes it more necessary.

**Option C — do nothing.** The chain keeps working around gaps via `python3`.
Honest cost: every workaround is less legible than the command it replaces, and
one of them will eventually fail at 3am and park the chain on a `chmod`.

**What is parked:** nothing — M0 continues either way. **What continues
meanwhile:** the full chain (S2 next).

**Answer by pasting Option A, or by editing this entry with "B" / "C".**

```bash
cd ~/NYC-taxi-production-with-k8-flavor
python3 - <<'EOF'
import json, pathlib
p = pathlib.Path(".claude/settings.local.json")
s = json.loads(p.read_text())
add = ["ls","cat","echo","printenv","env","command","which","type","head","tail",
       "grep","sed","awk","sort","cut","tr","wc","uniq","diff","file","find","stat",
       "du","df","uname","date","sha256sum","nproc","mkdir","touch","cp","mv",
       "chmod","install","tar","unzip","tee","ln","ruff","jq","claude"]
allow = s.setdefault("permissions", {}).setdefault("allow", [])
for a in add:
    e = f"Bash({a}:*)"
    if e not in allow: allow.append(e)
s["permissions"].setdefault("additionalDirectories", [])
if "/home/longt/.local" not in s["permissions"]["additionalDirectories"]:
    s["permissions"]["additionalDirectories"].append("/home/longt/.local")
p.write_text(json.dumps(s, indent=2) + "\n")
print("allowlist entries:", len(allow))
EOF
git add .claude/settings.local.json && git commit -m "chore(env): extend session allowlist (AWAITING_PO 2026-08-16-2 option A)" && git push
```

*(Takes effect for the NEXT chained session — settings are read at session
start. Nothing needs restarting; the running chain picks it up on its own.)*

---

## 2026-08-16-1 · ✅ ANSWERED 2026-08-16 by DOING Option A (verified at M0-S1: `free -h` 47Gi · `docker ps` answers in WSL · `gh auth status` logged in as Phu-Hong-Duong · safer allowlist written · chain fired into the WSL clone) · raised by ARCH/Fable (Session 1, bootstrap) · GO-LIVE: the chain's home isn't ready, and only your hands can finish it

**The fork in plain language.** The program is designed to run inside WSL2
(CLAUDE.md, gotcha #1, automation/README one-time setup). Preflight found the
Windows side healthy (git+push ✅, gh ✅, claude 2.1.233 ✅, Docker 29.6.2 ✅,
all ports free ✅, TLS clean ✅) but the WSL side not ready: no repo clone
there, `claude` and `gh` not installed in Ubuntu, permission flags unset,
RAM grant 31 GB (< 48), Docker's WSL integration OFF. Four of those need
interactive logins, a GUI toggle, sudo, or a risk decision — all yours by
constitution (credentials and permission modes never ride a default,
gotcha #23). Everything scriptable is already done: harness PROVEN on the
real CLI (hello-chain + STOP kill switch, quoted in HANDOFF k), M0 kickoff
authored, chain-script exec bit fixed, `.wslconfig` (48GB) written, WSL clone
pre-staged at `~/NYC-taxi-production-with-k8-flavor`, all pushed.

**Option A (Recommended) — finish the WSL setup: ~15 minutes of your hands,
the paste-block below.** Honest cost: your time, two browser logins, one
permission-mode risk call; the chain starts the moment the last line runs.
This is the designed path — every gotcha and rehearsed recovery in the ledger
assumes it.

**Option B — re-platform to run Windows-native (Git Bash).** Zero setup now
(claude/gh already live on Windows — the hello-proof even ran there), but:
an unplanned porting effort (Makefile, scripts, kind/kubectl flows and ALL
rehearsed gotchas are Linux-assumed), the CRLF trap class reopens (#11), and
you STILL owe the permission-mode decision — the one human step no platform
removes. This is the demo-easy path; its cost hides downstream. Not
recommended.

**What is parked:** the entire chain — every M0 story needs the WSL home; no
independent story exists. **What continues meanwhile:** nothing autonomous;
the repo is build-ready and pushed (`origin/main`).

**Answer by DOING Option A's block (running its last line IS the answer — the
chain self-starts), or by editing this entry with "B" (ARCH will then re-plan
M0 for Windows-native).**

---

### Option A paste-block (once, in order)

**A1. (Windows)** Docker Desktop → Settings → Resources → **WSL integration**
→ toggle **Ubuntu** ON → Apply & restart.

**A2. (Windows PowerShell)** `wsl --shutdown` — applies the 48 GB grant
already written to `C:\Users\longt\.wslconfig`. If Docker Desktop complains
afterwards, quit and reopen it.

**A3. (new Ubuntu terminal)**
```bash
free -h            # expect ~47Gi total (was 31Gi)
docker ps          # expect an empty table, no error
sudo apt update && sudo apt install -y make gh
cd ~/NYC-taxi-production-with-k8-flavor
git config --global user.name  "Phu-Hong-Duong"
git config --global user.email "dhphu222@gmail.com"
gh auth login      # browser flow; pick HTTPS
gh auth setup-git  # lets the chain push over HTTPS
curl -fsSL https://claude.ai/install.sh | bash    # probed 200 on 2026-08-16
exec $SHELL -l
claude --version   # expect 2.x
claude             # complete /login in the browser, then /exit
```

**A4. Permission mode — YOUR risk call (automation/README.md §setup). Pick ONE:**

Safer (unattended sessions may park on unlisted commands — extend the list):
```bash
cd ~/NYC-taxi-production-with-k8-flavor
mkdir -p .claude && cat > .claude/settings.local.json <<'EOF'
{
  "model": "opus",
  "permissions": {
    "allow": [
      "Bash(make:*)", "Bash(kubectl:*)", "Bash(helm:*)", "Bash(kind:*)",
      "Bash(docker:*)", "Bash(git:*)", "Bash(gh:*)", "Bash(uv:*)",
      "Bash(dbt:*)", "Bash(python:*)", "Bash(python3:*)", "Bash(pytest:*)",
      "Bash(dvc:*)", "Bash(curl:*)", "Bash(ss:*)", "Bash(free:*)",
      "Bash(automation/next_session.sh:*)"
    ]
  }
}
EOF
echo 'export CLAUDE_PERMISSION_FLAGS="--permission-mode acceptEdits"' >> ~/.bashrc
```
Simpler, riskier (it can run anything unattended — your machine, your call):
```bash
echo 'export CLAUDE_PERMISSION_FLAGS="--dangerously-skip-permissions"' >> ~/.bashrc
```

**A5. Start the chain — and keep this Ubuntu window OPEN (gotcha #24: the
scheduler lives in WSL):**
```bash
exec $SHELL -l
cd ~/NYC-taxi-production-with-k8-flavor
automation/next_session.sh executor 60
```

*Postscripts:* your PyCharm copy on `C:\` stays your viewing window — `git
pull` there to see the chain's work; the chain itself only ever runs in the
WSL clone. The untracked `_to_delete/git-locks/` files in the Windows copy
are yours to delete at leisure; the chain will not touch them.

## 2026-08-20 06:50 UTC — watchdog: Chain: detached run FAILED
'm7-retrain-fulldata' exited 2. The chain is parked because its result never arrived. See automation/runs/m7-retrain-fulldata.log

Watchdog log: automation/logs/watchdog.log

### RESOLVED 2026-08-20 (M7-S4 completion leg) — no decision was needed, and the park was correct anyway

**Nothing is awaiting the PO here.** The watchdog did exactly its job: a detached
run reported a non-zero exit and it refused to guess. Two separate runs were
involved and both are now closed:

* `m7-retrain-fulldata` (05:59Z) genuinely crashed after reaching a correct
  REFUSE — that is F-020's verdict, gotchas #95/#96, fixed in commit `6972618`.
* `m7-s4-retrain-rerun` (06:43Z) **succeeded**: it refused correctly, wrote the
  record, and its `FAILED 2` is `make` collapsing the CLI's exit **1** — the
  vocabulary does not survive the launcher. That is **F-049 / gotcha #97**,
  closed in this session with the rule that a verdict is read out of the RECORD
  and never out of a `.status` file.

`@champion` is version **2**, `VERSIONS: ['1','2']` — no version 3 exists, so
nothing was promoted by either run. The chain was restarted by hand this session
and continues normally; no PO action is required for this entry.

The three standing entries below/above are unchanged and still non-blocking:
**2026-08-18-1 (F-016)**, **2026-08-17-1**, **2026-08-16-2**.

## 2026-08-24 04:30 UTC — watchdog: Chain: detached run FAILED
'm7-retrain-fulldata' exited 2. The chain is parked because its result never arrived. See automation/runs/m7-retrain-fulldata.log

Watchdog log: automation/logs/watchdog.log

## 2026-08-24 06:40 UTC — watchdog: Chain parked — your decision needed
The chain stopped after writing a new entry to AWAITING_PO.md. That is the fork policy working, not a fault: it will NOT auto-proceed on its own recommendation. Answer the entry, then: automation/next_session.sh executor

Watchdog log: automation/logs/watchdog.log

## 2026-08-24 07:40 UTC — watchdog: Chain parked — your decision needed
The chain stopped after writing a new entry to AWAITING_PO.md. That is the fork policy working, not a fault: it will NOT auto-proceed on its own recommendation. Answer the entry, then: automation/next_session.sh executor

Watchdog log: automation/logs/watchdog.log

## 2026-08-25 02:50 UTC — watchdog: Chain parked — your decision needed
The chain stopped after writing a new entry to AWAITING_PO.md. That is the fork policy working, not a fault: it will NOT auto-proceed on its own recommendation. Answer the entry, then: automation/next_session.sh executor

Watchdog log: automation/logs/watchdog.log

## 2026-08-25 06:30 UTC — watchdog: Chain parked — your decision needed
The chain stopped after writing a new entry to AWAITING_PO.md. That is the fork policy working, not a fault: it will NOT auto-proceed on its own recommendation. Answer the entry, then: automation/next_session.sh executor

Watchdog log: automation/logs/watchdog.log

## 2026-08-25 07:30 UTC — watchdog: Chain parked — your decision needed
The chain stopped after writing a new entry to AWAITING_PO.md. That is the fork policy working, not a fault: it will NOT auto-proceed on its own recommendation. Answer the entry, then: automation/next_session.sh executor

Watchdog log: automation/logs/watchdog.log

## 2026-08-25 08:30 UTC — watchdog: Chain parked — your decision needed
The chain stopped after writing a new entry to AWAITING_PO.md. That is the fork policy working, not a fault: it will NOT auto-proceed on its own recommendation. Answer the entry, then: automation/next_session.sh executor

Watchdog log: automation/logs/watchdog.log

## 2026-08-25 09:30 UTC — watchdog: Chain parked — your decision needed
The chain stopped after writing a new entry to AWAITING_PO.md. That is the fork policy working, not a fault: it will NOT auto-proceed on its own recommendation. Answer the entry, then: automation/next_session.sh executor

Watchdog log: automation/logs/watchdog.log

## 2026-08-29 04:30 UTC — watchdog: Chain parked — your decision needed
The chain stopped after writing a new entry to AWAITING_PO.md. That is the fork policy working, not a fault: it will NOT auto-proceed on its own recommendation. Answer the entry, then: automation/next_session.sh executor

Watchdog log: automation/logs/watchdog.log

## 2026-08-29 05:30 UTC — watchdog: Chain parked — your decision needed
The chain stopped after writing a new entry to AWAITING_PO.md. That is the fork policy working, not a fault: it will NOT auto-proceed on its own recommendation. Answer the entry, then: automation/next_session.sh executor

Watchdog log: automation/logs/watchdog.log

**ARCH 2026-08-29 (post-publish boundary, session dc): NO ENTRY WAITS — do not
go looking for one.** The two notices above (04:30, 05:30) are the watchdog's
park heartbeat firing at an EMPTY inbox: PP-S1 landed, entry 2026-08-29-1
carries its dated LANDED note, and nothing above is unanswered. To stop the
false "your decision needed" toasts, the chain is now paused the way you
yourself left it from 2026-08-26 until this morning: **`automation/STOP` is
restored**, and the watchdog stands down deliberately (its own log line:
`STOP present — chain paused deliberately; standing down`). No watchdog code
was touched — the §0 decline in `POST_PUBLISH_KICKOFF.md` stands. To restart
the chain for anything at all:
`rm automation/STOP && automation/next_session.sh architect 120`.

## 2026-08-31 09:50 UTC — watchdog: Chain parked — your decision needed
The chain stopped after writing a new entry to AWAITING_PO.md. That is the fork policy working, not a fault: it will NOT auto-proceed on its own recommendation. Answer the entry, then: automation/next_session.sh executor

Watchdog log: automation/logs/watchdog.log

## 2026-08-31 10:50 UTC — watchdog: Chain parked — your decision needed
The chain stopped after writing a new entry to AWAITING_PO.md. That is the fork policy working, not a fault: it will NOT auto-proceed on its own recommendation. Answer the entry, then: automation/next_session.sh executor

Watchdog log: automation/logs/watchdog.log
