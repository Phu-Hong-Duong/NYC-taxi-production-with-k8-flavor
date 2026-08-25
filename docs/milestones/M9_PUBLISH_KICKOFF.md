# M9 PUBLISH KICKOFF — landing the PO's three letters before the flip   (authored by: ARCH/Fable · v3.0: the Architect is sole author)

The program is closed (`PROGRAM_CLOSE.md`), the epilogue is closed
(`m9-epilogue-closed`), and on 2026-08-25 the PO answered both open entries —
**2026-08-24-4** (F-016/F-068: option **(b)**, era-aware) and **2026-08-24-5**
(sqlparse: option **(b)**; rotate credentials: **YES**, in-place preferred;
pre-commit hook: **YES**). Every one of those answers is work that must land
BEFORE the public flip, and the flip itself remains the PO's click. This
kickoff charters exactly that work and nothing else. Story numbering continues
the epilogue's (S5–S9), so these are **M9-S10 … M9-S13**.

## 0. Boundary triage of the post-epilogue state (nothing carried silently)

**The epilogue's close STANDS.** This boundary re-verified it live on
2026-08-25 rather than trusting the five-hour-old close:

- `make verify-m9` → **GREEN, every sub-check passed** (banner pasted below;
  full run in this session's log). The store-watch leg now reads **36 checks
  across 4 phases** (M9-S7's fourth phase), the F-062 leg reads the CLOSED row
  with its citation (F-073's two-state form), the lock leg reads `uv.lock`
  byte-identical to `m7-closed`, and `@champion` resolves to version **2**.

  ```
  [verify-m9] GREEN — every M9 sub-check passed.
              CLOSED BY A HUMAN, 2026-08-24: §9/M9's last accept line …
  ```

- **Lineage spot-check (gotcha #20):** M9-S9's merge `fe0fca2` is contained in
  `origin/main`, and `git merge-base --is-ancestor m9-epilogue-closed
  origin/main` returns true — the close tag reaches the remote.

- **The cluster is up**: all three `mlops-taxi` nodes Ready at 8d age
  (v1.36.1), Docker answering — no gotcha #34 recovery was needed.

**Open findings, dispositioned (the register's only open rows are F-016 and
F-068, and both now carry the PO's letter):**

| Finding | Disposition |
|---|---|
| **F-016** (incumbent condition has no margin) | **CHARTERED → M9-S10.** PO answered 2026-08-24-4 on 2026-08-25: **option (b)**, era-aware. The row closes with F-068 when S10 lands with the three replay gates GREEN. Dated note appended to the ledger row this commit. |
| **F-068** (the sanctioned tightening flips two recorded verdicts) | **CHARTERED → M9-S10.** Same letter, same landing. The frozen nine and both flips are already recorded in `automation/runs/m9-f016/replay-wall.json`; S10 consumes that record as its enumerated set. |
| Debt register | **CLOSED — no rows due.** Nothing to intake. |

**The PO's second letter (2026-08-24-5, answered 2026-08-25) decomposes into
three chartered stories:** sqlparse option (b) → **M9-S11** · credential
rotation YES (in-place preferred) → **M9-S12** · pre-commit hook YES →
**M9-S13**. The publish flip itself is NOT a story: it is the PO's click,
re-invited by S13's exit entry after all four stories land.

**Verdict: the epilogue close stands; this phase opens.** No tag is placed at
this boundary (nothing new is closing); `m9-publish-closed` is placed by the
ARCH boundary session that closes THIS phase. README gains an **in progress**
row for this phase in the same commit as this kickoff (the twelve pinned rows
are untouched — the checker's `STATUS_ROWS` is append-only by prefix, so no
test moves).

## Preconditions (verified LIVE at draft time — pastes, not memory)

- `make verify-m9` GREEN (pasted in §0), run against the live cluster.
- `uv.lock` pins `sqlparse 0.5.5` (lines 4274–4279; wheel sha `12a08b…`), and
  `uv pip list` reads **0.5.5** back off the live project env. `grep sqlparse
  infra/feast/requirements-feast.txt` exits **1** — the quarantine does NOT
  pin it, so S11's "quarantine pin file checked" leg is a recorded absence,
  not an edit.
- `automation/runs/m9-f016/replay-wall.json`: `replayed: 9, flips: 2`, gate on
  disk `incumbent_min_improvement_pct: null` — the enumerated set S10 freezes
  against, keyed on (leg, source, label), exists and is tracked.
- `scripts/platform_secrets.sh` enumerates the credential families S12 must
  rotate: `MINIO_ROOT_*`, `AWS_*` (the `mlflow` MinIO user), `POSTGRES_PASSWORD`,
  `MLFLOW_DB_PASSWORD`, `MARTS_DB_*`, `FLYTE_S3_*`, `SERVING_S3_*`, plus the
  ADDITIVE block's remaining consumers — S12 re-enumerates LIVE from `.env` +
  the script, never from this list.
- `AWAITING_PO.md` carries both answered blocks verbatim (the PO's own edit,
  committed with this kickoff).

## Debt intake

None — `ledgers/debt.md` is CLOSED with no rows due. (The 76 pod-security
misconfigurations from M9-S9 are a LISTED backlog, not debt rows; the PO has
not opted into a hardening pass and none is chartered here.)

## Stories (4; each independently finishable, safe stopping point after each; run in order)

### M9-S10 — F-016/F-068 option (b): the incumbent margin lands era-aware (role:MLE)

The PO's answer, verbatim requirements (AWAITING_PO 2026-08-24-4, answered
block): land B era-aware; replay each historical verdict against the incumbent
margin **in force when it was taken**; the margin becomes a **recorded field on
every future verdict** so the inference-from-absence is confined to the frozen
nine in `automation/runs/m9-f016/replay-wall.json`; plus a **separate,
unweakened check that the margin on disk never decreases**; and the in-force
value for the frozen nine is read from an **enumerated set, never a permissive
default** (F-048's rule). This is a full story, chosen eyes open.

- **The knob**: `incumbent_min_improvement_pct: 0.50` lands in
  `configs/train.yaml: gate` (F-013 — one home), with a comment that re-argues
  it citing BOTH answered entries (2026-08-18-1 and 2026-08-24-4), both
  observations the decision was made against (+0.63% moved the pointer at
  M3-S5; −0.03% held it at M7-S4), and the accepted cost verbatim: *a model
  genuinely 0.3–0.4% better will not ship.*
- **The gate**: `gate.decide` applies the margin to the incumbent KPI-09
  condition ONLY — the floor condition (2.00%), the KPI-10 conditions and
  everything else untouched. **The identity case is now DECIDED behaviour**:
  a challenger numerically identical to the incumbent (+0.0000%) is REFUSED
  under any positive margin, and that is correct — nothing about moving an
  alias is free, and +0.0000% buys nothing. A unit test pins it as design,
  not accident.
- **The recorded field**: every future verdict carries the margin it was
  judged under — in the decision payload AND in the transcript form the replay
  legs parse (`verdict_lines` prints it), so no future replay ever infers a
  margin from an absence. Whether it also travels as a promotion tag on the
  version is the executor's call; the property is *no future verdict is
  ambiguous about its own bar*.
- **The era-aware replays**: `verify-m2` §2, `verify-m3` §5 and `verify-m7`'s
  retrain leg replay each historical verdict against its in-force margin. For
  the frozen nine — keyed on (leg, source, label) exactly as
  `replay-wall.json` records them — the in-force margin is **0 (pre-B era)**.
  A verdict that is NOT in the enumerated set and carries NO recorded margin
  **fails loudly** (F-048: an unresolvable value never resolves to something
  convenient). Precedent to copy, not reinvent: `verify-m2` §2's floor-name
  swap at M3-S1 — *a verdict is replayed against the bar it was actually taken
  against, or it is not a replay* — with its separate floor-direction check.
- **The monotonic check**: a new, unweakened check that the incumbent margin
  never decreases — the config's margin must be ≥ the largest margin any
  recorded verdict was taken against, with the frozen nine contributing 0 and
  the sanctioned 0.50 as the floor from this story on. It must be
  demonstrable RED (plant a lowered margin, watch it fire, restore) — the
  drill the red teams exist for.
- **Tests, both directions plus the edges**: +0.3% REFUSED naming the margin ·
  +0.63% PROMOTED · +0.0000% REFUSED (the identity case as design) · a
  verdict outside the enumerated set with no recorded margin RAISES · a
  margin decrease goes RED. The four existing arithmetic tests in
  `test_training_gate.py` (F-068's evidence) are updated to the landed
  behaviour, not deleted — they pinned the case so this story would meet it.
- **Ledger + inbox**: F-016 → CLOSED (config diff + replay evidence), F-068 →
  CLOSED (the era-aware landing IS its resolution); AWAITING_PO 2026-08-18-1
  and 2026-08-24-4 get landed notes; CLAUDE.md section.

**Accept when:** `make verify-m2`, `make verify-m3`, `make verify-m7` all
GREEN after the edit — sub-check counts MAY change and are re-derived, never
widened (gotcha #50) — · `make verify-m2-redteam` and `make verify-m3-redteam`
both still PASS (the planted-edit drills must survive the era-aware rewrite) ·
the new direction/edge tests green · the monotonic check demonstrated RED then
GREEN · **the era-aware replay of the frozen nine reproduces all nine RECORDED
verdicts with 0 flips** (that is the whole point of (b)) · no fit, no alias
move, no registry version — the story moves NOTHING; it changes what a future
promotion must clear. **Evidence plan:** the config diff, the three gate
transcripts, the red-team transcripts, the test run.

**Safe stopping point / STOP rule (inherited from the S6 charter and still in
force):** if the era-aware replay flips ANY recorded verdict — which would
mean the enumeration, the era logic, or a verdict source the probe never read
is wrong — **STOP; that is a finding and a PO question, never an edit to the
replay.**

### M9-S11 — sqlparse 0.6.0 and the lock re-baseline (role:MLOps)

The PO's option (b), cost accepted as stated: bump BEFORE the flip,
re-baseline the lock invariant, prove nothing moved. This is the first time
this program changes a pinned dependency — treat it as the rehearsal it is.

- `uv lock --upgrade-package sqlparse` (target **0.6.0**), then the gotcha #36
  check as a MEASUREMENT: diff the lock and assert **only sqlparse moved** —
  pandas 3.0.5 · numpy 2.5.2 · scikit-learn 1.9.0 · mlflow-skinny 3.15.1 ·
  lightgbm 4.7.0 · dbt-core 1.12.2 all byte-unchanged in the lock. If the
  resolver moves anything else, STOP and record before proceeding (a
  constraint pin `sqlparse==0.6.0` is the first fallback). Read 0.6.0 back
  off `uv pip list` after `uv sync`.
- **The re-baseline**: the invariant *"`uv.lock` byte-identical to a
  sanctioned tag"* keeps its SHAPE; only the anchor moves, once, by PO
  sanction. Place a new tag (suggested: `lock-rebaselined-m9-publish`) on the
  landing commit and re-point every reader: `scripts/verify_m8.sh`,
  `verify_m8_redteam.sh`, `verify_m9.sh`, `verify_m9_redteam.sh`, plus any
  test naming `m7-closed` for this purpose. The script comment cites
  2026-08-24-5's answered block — the sanction travels with the edit.
- **Prove nothing moved** (dbt is sqlparse's consumer here, MLflow's client
  the other suspect): `make marts` (dbt build PASS + publish counts
  reproduced) · `make parity` (**0.000e+00** over 16 hazards — the cheapest
  full exercise of the MLflow client and the wire) · host suite · ruff.
- **The quarantine leg is a recorded ABSENCE**: `sqlparse` is not in
  `infra/feast/requirements-feast.txt` (verified at charter time, exit 1) —
  record the check, change nothing.
- `make security-scan` re-run: the sqlparse CVE cluster (3 HIGH) leaves the
  dependency findings; `docs/security_audit_m9.md` gets a dated note beside
  the original (never a rewrite); `make readme-check` GREEN after (the README
  evidence table reads its numbers from the records this refreshes).
- **Honest cost, stated in the story record**: the task/predictor images are
  NOT rebuilt here — they carry sqlparse 0.5.5 until their next natural
  rebuild (every commit re-tags the image anyway, F-026/gotcha #66), and
  nothing on-cluster parses untrusted SQL. Rebuilding three images to close a
  CVE in a parser nothing points at untrusted input is cost without a threat
  model; the record says so rather than netting it out.

**Accept when:** lock diff shows exactly one package moved · `make verify-m8`
GREEN **51/51** against the new anchor · `make verify-m9` GREEN **45/45** ·
both red teams PASS · `make marts` and `make parity` reproduce their recorded
numbers · `make security-scan` GREEN with the sqlparse findings gone ·
`make readme-check` GREEN. **Evidence plan:** the lock diff, the tag, the
re-pointed scripts' diff, the five transcripts.

**Safe stopping point:** after the lock bump + gotcha #36 measurement, before
the re-anchor — the tree is red on `verify-m8` §1 at that point and the story
must not end there; if it must stop, revert the lock (one `git checkout`) and
record the attempt.

### M9-S12 — credential rotation, in-place (role:SRE)

The PO's YES, with the mechanism explicitly ARCH's to charter: **in-place
rotation preferred over destroy+rebuild**, because the stateful cluster's full
restore is un-rehearsed and `make destroy` takes every PVC with it. So the
charter is: rotate every credential in `.env` in place, prove the platform
lives on the new values, prove the old values are dead.

- **Enumerate LIVE**: the rotation set is every value in `.env` cross-checked
  against `scripts/platform_secrets.sh`'s REQUIRED list — never a remembered
  list. Families and their in-place mechanisms:
  - **Postgres** (superuser + `mlflow`/`marts`/`metabase`/`flyte` roles):
    `ALTER ROLE … PASSWORD` via the existing `kubectl exec` transport. The
    volume keeps hashes, not env — the pod's `POSTGRES_PASSWORD` env only
    matters at initdb, but the k8s Secret must still be updated to match so a
    future pod recreation agrees with the live role.
  - **MinIO named users** (`mlflow`, `flyte`, `serving`): `mc admin user add`
    re-issues a secret in place.
  - **MinIO root**: env-borne — new values into the Secret + a `Recreate`
    restart of the MinIO Deployment (the PVC keeps every object; this is
    still in-place in the sense the PO cares about — no state is destroyed).
  - **Grafana admin** (`monitoring/grafana-admin` Secret) and any Metabase
    credential: Secret update + pod restart.
- **Order per credential pair**: backing service first → k8s Secret +
  `.env` second → consumer restart third. Mid-rotation mismatch windows are
  accepted on a laptop; what is NOT accepted is ending the story with any
  pair disagreeing.
- **`.env` handling**: copy the old file aside to a gitignored path
  (`.env.pre-rotation`) BEFORE the first change — losing `.env` mid-rotation
  orphans every volume (the script's own warning). Delete the copy only after
  the accept passes. Never committed, never echoed (the script's no-echo law
  binds this story too).
- **The serving credential is exercised, not assumed**: one real
  `make serve` re-deploy after rotating `SERVING_S3_*` — the
  storage-initializer must fetch the champion under the NEW credential
  (measured cost: ~0.5 s of route unavailability, gotcha #80).
- **Positive first, then negative (gotcha #105)**: prove the platform answers
  on the new values (the gate sweep below), THEN prove the OLD values are
  refused — one MinIO probe and one psql probe with the pre-rotation
  password, both expecting authentication failure. An absence check before
  the presence check would pass against a dead platform.
- **Record**: `automation/runs/m9-publish/rotation.json` — what rotated
  (names, families, timestamps, which consumers restarted), NEVER a value,
  old or new.

**Accept when:** **all ten inherited gates `verify-m0` … `verify-m9` GREEN
after rotation** (the strongest available claim — every platform consumer
read live on the new credentials; the program-close precedent) · `make
parity` 0.000e+00 · the two old-credential probes REFUSED · `make
security-scan` GREEN (the new `.env` classifies local-only exactly as the old
one did) · the record committed · `.env.pre-rotation` destroyed. **Evidence
plan:** the gate sweep transcript, the two refusals, the rotation record.

**Safe stopping point / wall:** rotation is per-family — each family's
three-step (service → secret → restart) is independently completable, so the
story can stop between families with the record saying which are done. If a
family cannot rotate in place after 3 attempts, STOP for that family, record
it, and park the question at AWAITING_PO — the destroy+rebuild fallback is
priced in 2026-08-24-5 but the PO stated a preference against it, so it is
never auto-run.

### M9-S13 — the pre-commit hook, and the handoff to the click (role:MLOps)

The PO's YES, accepted with its limit exactly as stated in 2026-08-24-5: the
hook is unverifiable by any gate (`.git/hooks` is untracked), and
`make security-scan` remains the audit of record.

- **The hook**: a TRACKED script (`scripts/hooks/pre-commit`) running the fast
  secret-scan leg against the STAGED files only (gitleaks `protect --staged`
  or the scan's tree-secrets stage scoped to the index — seconds, or nobody
  keeps it installed). `make install-hooks` copies it into `.git/hooks/` and
  sets the execute bit (M8-S4's 0644 lesson — a `COPY` preserves a
  non-executable mode and the failure reads as something else entirely).
- **The verifiable halves get tests**; the unverifiable half gets a sentence:
  a unit test asserts the tracked file, the make target, and the exec-bit
  step exist; README documents the hook, its install command, and its honest
  limit in one breath.
- **Red-team**: with the hook installed, a STAGED planted credential blocks
  the commit — the plant drawn against the detector's properties (F-071's
  generator idiom: entropy floor, alphabet the rules match), then destroyed.
- **The final sweep, in one story so the handoff entry can cite one place**:
  `make security-scan` GREEN · `make readme-check` GREEN · `make verify-m9`
  GREEN · host suite count recorded.
- **The handoff**: write the AWAITING_PO entry — *all three letters are
  landed; the flip is your click* — citing S10's gates, S11's tag, S12's
  rotation record, S13's sweep, and the one resume command
  (`automation/next_session.sh architect 120`). The chain then falls to the
  ARCH boundary (§Exit).

**Accept when:** hook installed and demonstrated blocking a plant · the
tests green · the sweep green · the AWAITING_PO entry written. **Evidence
plan:** the blocked-commit transcript, the sweep transcripts, the entry.

## Out of scope (named now so creep is visible later)

- **The flip itself** — the PO's click, always. No story publishes anything.
- The 76 pod-security misconfiguration findings (a listed backlog; PO opt-in).
- Ray/CI stretch items (PO declined at 2026-08-24-2), the daily drift window
  (routed at the M7 boundary, unscheduled), image rebuilds for S11's CVE
  (argued in the story), any fit, any alias move, any registry version, any
  wire change beyond S12's one measured `make serve` re-deploy.

## Risks & walls (fallbacks cite laws/ADRs)

1. **S10's replay wall fires again** (a flip outside the frozen nine, or the
   era logic flips one of the nine): STOP rule is in the story and inherited
   from the S6 charter verbatim — a finding and a PO question, never an edit
   to the replay. Gotcha #50 governs every sub-check count change.
2. **S11's resolver moves more than sqlparse**: measured stop, constraint-pin
   fallback (`sqlparse==0.6.0`), and if THAT fails the lock reverts (one
   command) and the question parks. The re-anchor tag is pushed with the
   commit or the red teams break on a tag the remote lacks.
3. **S12 hits a family that cannot rotate in place**: per-family wall (3
   attempts) → record + park. `make destroy` is NEVER the fallback of this
   story's own authority — it destroys state whose restore is un-rehearsed
   (the PO's own reason), and ADR-002/M4-S2's backup covers objects, not a
   rehearsed full restore.
4. **Rotation breaks a consumer this charter did not enumerate**: the accept
   is all ten gates, which is the net that catches an unenumerated consumer;
   the story stops at the family that broke it, restores that family's
   pre-rotation value from `.env.pre-rotation` (which is why the copy exists),
   and records the finding.
5. **Long-run discipline**: no story here needs a detached run — S10's gates
   are seconds, S11's marts publish is ~4 min, S12's gate sweep is minutes.
   If any leg unexpectedly needs to outlive a session, `run_detached.sh` is
   the exit path (ritual e), never a waiting turn (gotcha #45).

## Open PO questions

None. Both entries are answered; the only thing left for the PO after this
phase is the click, and S13's exit entry re-invites it.

## Exit (the publish boundary)

When S13's entry is written, the chain schedules the ARCH boundary session:
re-run `verify-m9` + the S11-re-anchored `verify-m8` + the S10-touched
`verify-m2`/`m3`/`m7`, disposition anything the stories raised, tag
**`m9-publish-closed`** on a clean close, flip this phase's README row
(state + evidence) in the same commit, and re-park on the flip entry. The
flip happens on the PO's machine, by the PO's hands, after that.

## ARCH self-check (v3.0)

- Every story sized for one fresh executor session; owner named; observable
  accept; evidence plan; safe stopping point — yes, all four.
- No story loosens a gate: S10 TIGHTENS one under a PO letter quoted
  verbatim; S11 moves an invariant's anchor under the same letter, shape
  unchanged; S12/S13 touch no gate.
- Producer ≠ approver: stories are the executor's; this triage and this
  charter are ARCH's; the close signoff will name both.
- The wire moves only where measured and said: S12's one `make serve`
  re-deploy (~0.5 s, gotcha #80).
- Nothing carried silently: the register's two open rows are chartered by id
  with the PO's words quoted; debt is closed; the flip is named as the PO's.
