# CLEANUP KICKOFF — the followability cleanup (CU), chartered per PO directive 2026-08-29-2

Authored 2026-08-31 by ARCH (Claude Fable, `claude-fable-5`, stated per the
constitution), the ARCH touch the PO's answer to AWAITING_PO **2026-08-30-3**
names: *"the next ARCH touch charters the cleanup"*. The program is CLOSED and
PUBLIC (`m9-closed`, `m9-publish-closed`); this charter is a followability
cleanup of the codebase under the PO's own floor: **prune the bloat, keep every
guarantee**. Sessions launched from this kickoff are **CHARTERED** mode and
state it beside their model (directive 2026-08-30-1 — folded into the
constitution by CU-S1 below).

## 0. Boundary triage (2026-08-31 — nothing carried silently)

**There is no milestone to close.** M9, the publish phase, and the post-publish
story all closed with their tags and README rows
(`POST_PUBLISH_KICKOFF.md` §0.1); this touch tags nothing and flips no README
row — all 13 Status rows were flipped at `1bf01f0` and are byte-pinned by
`readme-check`'s `STATUS_ROWS`, which is itself a constraint on every CU slice
(the Status table does not move).

**Verify targets, re-run LIVE this session at HEAD `72153f0`:**

```
$ uv run ruff check src tests pipelines   → All checks passed!
$ uv run pytest tests/unit -q             → 1319 passed, 1 skipped in 62.42s
$ make readme-check                       → GREEN — every target, path and number in README.md checks out.
$ docker ps                               → docker: command not found   (Docker Desktop DOWN — gotcha #34)
$ git merge-base --is-ancestor 72153f0 origin/main → exit 0  (PR #80's merge reachable — gotcha #20)
```

The 1 skip is `tests/unit/test_task_image.py:252` (needs docker on PATH) — the
cluster-down fingerprint inside the suite, exactly as session (df) recorded.
*(Dated note, same session ~30 min later: the state MOVED mid-session — the
suite re-ran **1320 passed, 0 skipped**, and re-probing showed the CLI
symlinks back but the daemon socket and cluster API still refusing, i.e.
Docker Desktop starting up. Both pastes are true at their timestamps; the
executor re-measures at boot per the precondition protocol below.)*
**The ten cluster gates (`verify-m0…m9`) are NOT runnable this session** and
were not run; the last full sweep is M9-S12's (all GREEN), with `verify-m9`
GREEN 46/46 re-run at PP-S1's close. That gap is a stated precondition below,
not a silent one.

**Dispositions:**

- **F-001** — the register's only standing open row (session allowlist,
  non-blocking by the PO's 2026-08-24 answer 7). Stays open BY DESIGN; named so
  it is not a silent carry.
- **F-082** — raised AND closed by session (de) in its HANDOFF, but **never
  ledgered**. Row appended to `ledgers/findings.md` this session (CLOSED, with
  its evidence). A finding that lives only in a handoff entry is a silent carry
  by another route; that is the one bookkeeping defect this triage found.
- **Debt register** — CLOSED; no row lands here (intake below is empty).
- **AWAITING_PO 2026-08-30-3** — ANSWERED by the PO (option (a)); the architect
  lane was re-probed by (df) and again implicitly by this session existing.
  Swept with a dated CHARTERED note.
- **AWAITING_PO 2026-08-29-2** (the cleanup directive) and **2026-08-30-1**
  (the scope rule) — CHARTERED here; dated notes added under each.
- **AWAITING_PO 2026-08-30-2** (the VM/watchdog deadlock) — **stays OPEN; it is
  the PO's, not the chain's.** Its consequence binds this charter: any park
  stays parked until the PO next touches WSL, so the slices below are sized and
  ordered so the chain can keep working without parking.
- **One measurement recorded, not chartered:** the house lint net is
  `ruff check src tests pipelines` (Makefile:395, ci.yml) — `scripts/`, the
  audit's "bloat center", has never been linted; a bare `ruff check` over it
  reports 42 E501s today. Recorded here so the fact has a home; widening the
  lint net is deliberately out of scope (§ Out of scope).

**Triage verdict: CLEAN to charter.** The audit leg the directive asked for is
already done and verified: `docs/cleanup_audit_seed.md` (the PO's advisory
static audit) + `docs/cleanup_audit_verification.md` (session (de)'s
re-derivation BY RUNNING — 43 CONFIRMED · 6 DIFFERS all accounted · 3 newly
MEASURED, record `automation/runs/m-cleanup/audit-verify.json`). Every number a
slice below is argued from has two witnesses. Where a slice's own measurement
disagrees with both, the slice's measurement wins and the disagreement goes in
its PR.

## Preconditions (the one that gates ACCEPTANCE, stated plainly)

**Docker Desktop is DOWN, and the floor under every slice is the ten-gate
sweep.** No CU slice may MERGE until `verify-m0…m9` run GREEN over it. The
recovery is one action with no decision in it (launch Docker Desktop; kind's
node containers restart themselves, ~15 s — gotcha #34), but it is a
Windows-side action the chain cannot take. Standing instruction for every CU
executor session:

1. Check `docker ps` at boot. If the daemon answers, proceed normally.
2. If it does not: do the slice's work anyway, run the HOST-SIDE half of the
   floor (suite + `ruff check src tests pipelines` + `make readme-check` + the
   red teams the slice touched that run host-side), push the branch, **open the
   PR and do NOT merge**, say exactly this in the HANDOFF, and schedule the
   successor. The next session with a live cluster runs the sweep and merges.
   A PR merged against an unrun sweep is the failure shape this program spends
   its gates preventing; an unmerged PR waiting on a sweep is just a queue.

## Debt intake

None due. The debt register is closed.

## The floor (the directive's, restated as the per-slice accept frame)

Every slice, no exceptions: **all ten gates GREEN before merge** · host suite
green (1,319/1,320 by cluster state) · `make readme-check` GREEN · **every red
team whose files the slice touched re-run and still RED on its plant** · no
threshold, bar, knob or gate condition moves · no tracked record under
`automation/runs/` rewritten · no wire, alias, registry, mart-number or
`uv.lock` change · boundary laws hold · the README Status table byte-unmoved.

**ARCH's reading of the red-team clause, stated so the PO can veto it in the
directive entry:** the directive's per-slice qualifier is read as attaching to
the gates; red teams are re-run per slice where the slice touched their files,
and **CU-S5 closes with the complete battery** (all `make *-redteam` targets)
so the cleanup as a whole exits with every plant demonstrated RED once, after
all consolidation. Deleting a whole gate, red team, or recorded drill is a PO
fork and is NOT in any slice below.

## Stories (5 slices; one executor session each; each independently green)

### CU-S1 — Protocol scope rule + the dead code (role:MLOps)

**Why:** directive 2026-08-30-1 says the scope rule "can ride the cleanup
charter as one small slice"; the Tier A deletions are the audit's only pure
deletions and they carry three reference-site constraints that must land in the
same commits.

**What:**

1. **Fold the CHARTERED/EVERYDAY scope rule into the constitution**: a short
   scope section in `docs/org/ORG.md` mirroring CLAUDE.md's "Scope of this
   protocol" block (which is the PO's edit — cite it, don't rewrite it), and a
   MODE line in whichever templates instruct ceremony
   (`docs/PROMPTS.md` role prompts, `docs/milestones/TEMPLATE_KICKOFF.md`): a
   chartered session states its MODE the way it states its model. EVERYDAY
   sessions produce no ceremony; if in doubt, EVERYDAY.
2. **Delete Tier A — all six files, 1,050 LOC** (`rev_rederive_m7.py` ·
   `f016_replay_probe.py` · `retrain_proof_record.py` ·
   `cpu_request_resize_record.py` · `marts_reach_probe.py` ·
   `canary_split_paste.py`). Verified prose-only; every measurement is banked
   in tracked records. **The three reference-site edits land in the SAME
   commit** (verification doc §3 — gotcha #91):
   - `src/taxi_mlops/training/gate_eras.py:95` — the runtime error message
     naming `f016_replay_probe.py` is rewritten to point at the TRACKED record
     and git restore alone (the recovery instruction must not name a deleted
     instrument).
   - `scripts/f051_counterfactual.py:7` — the docstring keeps its provenance
     sentence with a dated note that the instrument was retired at CU-S1 and
     the record is the artifact.
   - `infra/manifests/flyte-task-podtemplate.yaml:116` — same shape: the
     measurement (`PROBE-OK ('marts', 'marts')`) stays, the pointer gains
     "(instrument retired at CU-S1; record is the evidence)".
   - **CLAUDE.md command-table rows** naming any deleted instrument
     (`canary_split_paste.py`, `cpu_request_resize_record.py`,
     `retrain_proof_record.py` at minimum — grep before trusting this list)
     get a dated retirement note beside the original text, never a silent
     deletion — CLAUDE.md is working memory, and the VERIFIED history stays.
   - AWAITING_PO 2026-08-24-4 cites `f016_replay_probe.py` as "re-runnable in
     seconds" — the PR body must name that citation and say the re-run
     affordance is retired (the frozen record `replay-wall.json` is tracked;
     restore is `git`, not a re-run). Called out, not slipped through.
3. **Tier B — conscious KEEP, all five, and the PR says so** (411 LOC:
   `marts_peak_probe.sh` · `feast_registry_dump.py` · `feast_serve_probe.sh` ·
   `contract_probe_fixtures.sh` · `f008_guard_exercise.py`). Each has exactly
   one Makefile anchor and four are cited as VERIFIED commands in CLAUDE.md's
   table; retiring a verified-command affordance to save 411 lines is a worse
   trade than the bytes. This is the "consciously retire or keep" decision the
   seed asked for — decided KEEP by ARCH here so the executor does not
   re-litigate it.
4. **Debris:** delete `tests/conftest.py`'s dead `RAW_2019_DTYPES`; add the 11
   missing `.PHONY` entries (named in the audit-verify record); remove the
   empty `tests/integration`/`tests/smoke` shells if nothing references them
   (check `pyproject.toml` markers first — the markers may stay); sweep the
   WSL clone's `_to_delete/` (untracked débris: 18 git-lock files + 1 zip —
   confirm untracked with `git status --ignored` before `rm`).

**Accept-when:** floor met (gates sweep before merge, per the precondition
protocol) · `grep -rn "f016_replay_probe\|rev_rederive_m7\|marts_reach_probe\|canary_split_paste\|cpu_request_resize_record\|retrain_proof_record" src/ scripts/ tests/ infra/ Makefile` returns only dated retirement notes and historical prose · a chartered-session MODE line exists in ORG.md + the templates · `make -n <target>` still works for every `.PHONY` addition.

**Safe stopping point:** after step 1 alone (the fold is self-contained), or
after any single deletion with its reference edits.

### CU-S2 — Test infrastructure: one conftest, honest helper names (role:MLE)

**Why:** 57-ish files re-declare `REPO`; the strip-comments helper is
copy-pasted 13× under two names; and `_calls()` exists in 7 files with 3
DIFFERENT semantics under one name — two tests that read identically assert
different things. That last one is a correctness fix wearing a cleanup's
clothes.

**What:**

1. Create `tests/unit/conftest.py`. Move there: `REPO` (the audit-verify
   instrument counts 47 tracked `.py` declarers — migrate them), ONE
   strip-comments helper (pick one name; both existing names die),
   `_record(path, produced_by=…)` (the fail-message-naming-the-drill is the
   valuable part — keep it), `invokes()` (×4 byte-identical), 
   `_imported_roots` (×3), and ONE subprocess-argv AST extractor.
2. **The `_calls()` hazard is resolved by SPLITTING, not unifying.** Three
   honestly-named helpers with the three real semantics (verification doc §3:
   called-name segments / dotted call paths / every-Attribute-regardless).
   **`test_tuning.py` is decided explicitly and its semantics KEEP the broad
   form**: its version has no `ast.Call` guard and backs a FORBIDDING
   assertion, so broader is stronger there — migrating it onto a call-guarded
   helper would weaken a live guard inside a diff that reads as pure
   deduplication (gotcha #50 via consolidation). It moves onto the
   all-attributes helper under that helper's honest name.
3. Migrate the ~47 files mechanically, in batches, each batch suite-green.
   **Zero assertion changes anywhere** except the `_calls` renames of step 2 —
   pin that claim in the PR by pointing at the diff: helper definitions
   deleted, import lines added, nothing else.
4. The in-image suite runs `tests/unit` (M4-S3) — the conftest must travel.
   Check `.dockerignore` does not exclude it; state in the PR that the
   in-image suite is unverifiable until the next image build and why that is
   acceptable (no image rebuild is chartered; gotcha #66 prices one commit as
   a cold cache anyway).

**Accept-when:** floor met · `grep -rn "REPO = Path" tests/` returns only the
conftest · exactly one strip-comments definition under `tests/` · three
`_calls`-successor helpers each with a docstring stating its semantics and
which kind of assertion it is for · collected test count stated before/after
(1,320 today; a small drop from de-duplicated meta-guards is legitimate ONLY
if each dropped test is named in the PR with why).

**Safe stopping point:** any green batch; the conftest plus even one migrated
file is an improvement that stands alone.

### CU-S3 — Shell libs: the verify harness and the red-team restore scaffold (role:MLOps)

**Why:** the gate harness (`consume < <(`, ok/no/FAIL counters) is
byte-identical across 8 gates (~470 LOC) — verified: all 8 `consume()` bodies
normalise to ONE string — and the sha256-snapshot + EXIT-trap restore scaffold
is byte-identical in 8 red-team drills (~240 LOC). Pure-deletion diffs.

**What:**

1. `scripts/lib/verify_harness.sh` (sourced), migrate the 8 gates.
   **Harness ONLY — the gates' LEGS are deliberately divergent second
   witnesses and no leg logic moves** (audit constraint 2). The `consume`
   process-substitution idiom must survive as-is (a pipe would count verdicts
   in a subshell — the M2-S5 lesson lives in that shape).
2. `scripts/lib/redteam_restore.sh`, migrate the 8 red-team drills' snapshot/
   restore/verify-sha plumbing. The PLANTS stay bespoke — a red team's plant
   is its argument.
3. **This creates the repo's first scripts→scripts source edge** (audit
   constraint 1). In the same slice: confirm `scripts/lib/` reaches the task
   image (`.dockerignore`), is covered by the F-026 guard paths (it is —
   `scripts/` is guarded since M4-S5), and that `verify-m*` still run from a
   fresh checkout (`bash -n` every migrated script; then the sweep).
4. **Expect the meta-tests to trip, and re-derive rather than widen** (gotcha
   #50): `tests/unit/test_verify_m*.py` pin gate text and structure, and at
   least one needle (`consume < <(`) is known to have matched instruction
   prose before (M8-S5). A guard that pinned a per-file copy that no longer
   exists is re-derived to the lib-level equivalent — the property, not the
   literal. Every re-derived guard is named in the PR with its old and new
   property.

**Accept-when:** floor met, **including every gate red team re-run RED**
(this slice touches all 16 of those files, so the per-slice red-team clause
means the full gate/red-team battery here) · `wc -l` before/after for the 16
migrated files in the PR · zero diff lines inside any gate's LEG logic
(reviewable because the harness lines are deletions and the leg lines are
untouched).

**Safe stopping point:** harness lib + gates migrated, red teams not yet — or
any prefix of either migration with the sweep green.

### CU-S4 — Python plumbing: forwards, prom readers, kubectl, record loader (role:MLOps)

**Why:** 15 shell + 12 python files run `kubectl port-forward` (measured);
5–6 drills re-implement `prom_rules`/`prom_query`/`firing_months`/`http_get`;
8 py files carry `_kubectl()` wrappers and 30 sh files the `KUBECTL=(`
preamble; record readers are ~500–700 diffuse LOC with no shared helper.

**What:**

1. One Python home (suggest `scripts/_lib/` package: `forward.py`,
   `monitoring.py`, `records.py`, `k8s.py`): `forward()/wait_http()` (the
   forward helper doubles as the PORT REGISTRY the copies now coordinate by
   comments — the drills' careful off-port choices like 6568/9100/8092 become
   named constants with their reasons), the prom/alertmanager readers, the
   `_kubectl` wrapper, and `load_record(path, produced_by=…)` whose failure
   message names the drill that produces the record.
2. `scripts/lib/forward.sh` + `scripts/lib/pg.sh` for the shell side
   (`marts_publish.py`'s Transport stays the publish home — audit's note).
3. Migrate drills and probes incrementally. **The record-reader migration is
   the judgement-heavy one (medium confidence in the audit): stop short
   wherever a reader's bespoke fail-message or shape-check is doing work** —
   this cluster is allowed to land partially, with the stopping line stated.
4. **AST-pinned tests will trip**: several tests pin exact subprocess argv or
   "exactly ONE subprocess call" in specific scripts (feast retrieval, online
   parity, store watchdog…). Same rule as CU-S3: re-derive to the property,
   name each in the PR. A helper that changes the AST shape a guard parses is
   the expected cost, not a surprise.

**Accept-when:** floor met (red teams touched: whichever drills migrated —
run those) · duplicated-LOC before/after for the four clusters in the PR ·
no forward port number appears in more than one place (the registry is the
one home) · DRY_RUN plumbing untouched (the audit's do-not-consolidate row).

**Safe stopping point:** any migrated subset with the sweep green; the lib
with three callers is better than no lib.

### CU-S5 — isvc deploy lib, the write-up, and the full battery (role:MLOps)

**Why:** the isvc deploy skeleton (ROUTE_PORT heredoc ×5 verbatim · alias
no-move guard ×4–7 · three wait legs ×4) is ~200 strict-dup LOC across the
deploy scripts — and the cleanup owes the PO its numbers.

**What:**

1. `scripts/lib/isvc_deploy.sh`: the port heredoc, the alias
   read-before/read-after no-move guard, the three wait legs
   (`rollout status` → `--for=jsonpath=` → ask the ROUTE; F-036/F-037/F-060,
   gotcha #106 — the ORDER is load-bearing and a test already pins it; keep
   the test satisfied by re-derivation if the pin was per-file). **Each deploy
   script's ACCEPT CHECK stays bespoke** — the accept checks are the program's
   arguments and none of them is a copy.
2. **`docs/cleanup_report.md`** — the directive's write-up: files/LOC
   before/after per area (the audit-verify instrument re-run at close gives
   the after-numbers from the same instrument that measured before), tests
   before/after, every deletion with why-it-is-safe, every consolidation with
   its cluster, every re-derived guard with old/new property. Before-numbers
   come from `automation/runs/m-cleanup/audit-verify.json`; the close re-runs
   `scripts/cleanup_audit_verify.py --json` to a NEW record file (the before
   record is evidence and is not rewritten).
3. **The full red-team battery** — every `make *-redteam` target, each RED on
   its plant then GREEN restored, listed in the report. This is the charter's
   close-out demonstration that no consolidation weakened a drill.
4. **Navigability, decided here so it is not re-litigated:** NO new code map
   is written. CLAUDE.md's command table already maps script → command →
   verified-when, and a second map would be a twin (F-013's one-home rule
   applied to navigation). The navigability deliverable of this cleanup IS
   the deletion of the copies a reader currently re-reads per file, plus
   module docstrings on the new `lib/` homes stating what lives there and
   what deliberately does not (DRY_RUN narrations, accept checks, gate legs,
   plants).

**Accept-when:** floor met · full battery RED-then-GREEN · the report's
after-numbers produced by the same re-run instrument · ten gates GREEN as the
final line of the report.

**Safe stopping point:** the lib migration alone, or the report without the
battery (battery then owed by a follow-up session before the charter closes).

## Out of scope (named now so creep is visible later)

- **Deleting any gate, red team, or recorded drill** — PO fork by the
  directive's own text; no slice does it.
- **The literal-pin review** (the seed's optional slice 6, `== N` → floor):
  guard-semantics work with low followability yield; not chartered. If a slice
  trips one such pin it re-derives that one (gotcha #50), no sweep.
- **Widening the ruff net to `scripts/`** (the 42 E501s recorded in §0):
  mechanical churn across many files mid-consolidation invites conflicts;
  measured, recorded, not chartered.
- **DRY_RUN plumbing** — each narration is deliberately bespoke (audit's own
  do-not-consolidate row).
- `docs/` historical prose, `automation/runs/**`, the README Status table,
  every threshold/bar/knob, the wire, the registry, `uv.lock`.
- **AWAITING_PO 2026-08-30-2** (VM/watchdog deadlock) — the PO's fork; no
  slice touches watchdog/chain plumbing (the §0 decline in
  `POST_PUBLISH_KICKOFF.md` stands).
- Runtime performance work of any kind — the directive optimizes the CODEBASE
  for followability; latency and fit-cost numbers are closed record.

## Risks & walls

- **The biggest single risk is a guard weakened inside a diff that reads as
  deduplication** — the `_calls`/`test_tuning.py` shape, found before any edit
  was made. Standing rule for every slice: when a meta-test or AST pin goes
  red, ask FIRST whether the property it guarded still has a home (gotcha
  #50); re-derive to the lib-level property; never delete an assertion to make
  a migration pass; and any test that DISAPPEARS is named in the PR with why.
- **The cluster precondition** (§ Preconditions): merges wait on the sweep.
  If Docker Desktop stays down across sessions, the queue accumulates open
  PRs, not merged risk. Sequential slices touching `scripts/` and `tests/`
  should branch from the previous slice's branch if it is unmerged, and the
  HANDOFF must say so (lineage stays reviewable).
- **3-attempt wall per slice** as always; the fallback at every wall is full
  revert to the branch point — the codebase returns to its verified state and
  the wall goes in the HANDOFF (and to AWAITING_PO only if it is a fork, which
  a failed consolidation is not: a failed consolidation is a KEEP verdict with
  evidence).
- **No detached runs are expected** — every slice is edits + host checks +
  the sweep (minutes). If an executor finds otherwise it names
  `run_detached.sh` in its handoff rather than waiting (ritual e / gotcha #45).
- **Merge-order coupling:** CU-S2 (tests) and CU-S3/S4 (scripts) touch
  disjoint trees and could interleave, but the charter orders them S1→S5;
  an executor session picks the LOWEST unlanded slice unless its HANDOFF
  predecessor says otherwise.

## Exit (this ARCH session)

HANDOFF entry · dated notes in AWAITING_PO under 2026-08-29-2 / 2026-08-30-1 /
2026-08-30-3 · F-082 ledger row · commit + push this kickoff · then
`automation/next_session.sh executor 120` (which re-stamps the park-detector
hash itself). The executor runs CU-S1.
