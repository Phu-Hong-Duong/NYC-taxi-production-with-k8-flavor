# The followability cleanup — what was removed, what was merged, and what still proves itself

**Written at CU-S5 (2026-08-31), the cleanup's last slice.** The charter is
`docs/milestones/CLEANUP_KICKOFF.md`; the PO directive behind it is AWAITING_PO
**2026-08-29-2**, whose floor is one sentence: *prune the bloat, keep every
guarantee.* This document is the directive's write-up. It is the second half of
a pair — `docs/cleanup_audit_seed.md` (the PO's advisory static audit) and
`docs/cleanup_audit_verification.md` (session (de)'s re-derivation BY RUNNING)
argued what to do; this reports what was done and what it cost.

**Every number below is read out of a tracked record, and the before- and
after-numbers come from the SAME instrument.** `scripts/cleanup_audit_verify.py`
measured `automation/runs/m-cleanup/audit-verify.json` before the first slice
and `automation/runs/m-cleanup/audit-verify-after.json` after the last. The
before-record was not rewritten — it is evidence, and re-running an instrument
over its own prior output is how a comparison quietly becomes a claim
(F-053/F-063, gotcha #48).

---

## 1. The size of it

| Area | before | after | Δ |
|---|---:|---:|---:|
| `scripts/` files | 141 | 144 | **+3** |
| `scripts/` lines | 41,848 | 41,540 | **−308** |
| `tests/` files | 74 | 75 | +1 |
| `tests/` lines | 22,411 | 23,345 | **+934** |
| `src/` lines | 12,867 | 12,871 | +4 |
| `docs/` lines | 34,794 | 35,773 | **+979** |
| the ten `verify_m*.sh` gates | 9,055 | 8,885 | **−170** |
| the red-team drills | 2,957 | 2,816 | **−141** |
| Tier A dead instruments | 1,050 | 0 | **−1,050** |
| tests COLLECTED (run, not grepped) | 1,320 | **1,408** | **+88** |
| `def test_` occurrences | 1,212 | 1,265 | +53 |

**Read that table honestly, because three rows in it go the wrong way.**

- **`scripts/` gained three files while losing 308 lines.** Six dead instruments
  left; three shell/python libraries and one package arrived
  (`scripts/lib/verify_harness.sh`, `scripts/lib/redteam_restore.sh`,
  `scripts/lib/isvc_deploy.sh`, `scripts/_lib/` ×5). A cleanup that only
  deletes is a cleanup that never had to decide anything.
- **`tests/` grew by 934 lines and 88 collected tests.** That is the point, not
  a side effect: every guard that used to pin a per-file copy was re-derived to
  the lib-level property, and most of the replacements RUN the code instead of
  reading it (§5). Running a behaviour costs more lines than grepping for a
  string and is worth more.
- **`docs/` grew by 979 lines** — the audit verification, the charter, and this
  report. The directive asked for a write-up; the write-up is lines.

**Total across the whole cleanup: 130 files changed, 3,809 insertions, 2,894
deletions** (`git diff --shortstat 76c24e1 HEAD`, where `76c24e1` is the merge
that landed the charter). The cleanup is **not** a net subtraction of lines, and
saying so plainly is the first thing this report owes its reader. What it is, is
a subtraction of *copies* — measured in §3 and §4.

**One artefact of the instrument, named so it does not read as a discrepancy:**
the before-record has 52 rows and the after-record has 46. Twelve Tier A rows
(a LOC row and a status row per deleted file) collapsed to six "file is gone"
rows, because their subject no longer exists. The instrument reporting fewer
rows is the instrument working.

**And the verdict counts inverted — 43 CONFIRMED / 6 DIFFERS before, 9 CONFIRMED
/ 34 DIFFERS after.** That is not a regression. Those verdicts compare each
measurement against the SEED's number, and the seed described the codebase as it
was in August before any slice ran. A row that now reads DIFFERS is a row the
cleanup changed. The three rows that should alarm a reader if they DIFFERed —
the ones about guarantees rather than about size — are in §6, and none of them
moved.

---

## 2. What was deleted, and why each deletion is safe

**Six instruments, 1,050 LOC** (CU-S1, commit `b2b7ed6`). Every one is a
one-shot measurement script whose numbers are banked in a tracked record under
`automation/runs/`, so deleting the script destroys no evidence — it destroys
the affordance to re-take a measurement nobody needs to re-take.

| File | LOC | Why it is safe to delete |
|---|---:|---|
| `rev_rederive_m7.py` | — | REV's independent re-derivation of M7's drift numbers. Its verdict is in the M7 records; and CU-S5's own `make drift-monotonicity` re-runs the same counterfactual through the SHIPPED functions, which is the half this script structurally could not do. |
| `f016_replay_probe.py` | — | Measured which recorded verdicts would flip under a positive incumbent margin. Its answer is enumerated permanently in `automation/runs/m9-f016/replay-wall.json`, which `gate_eras.py` reads at run time. |
| `retrain_proof_record.py` | — | Read the scheduled retrain's resolved scale off the control plane. Both the before-state (seven `null` firings) and the after are in `automation/runs/m8-provenance/proof.json`; that contrast is what F-048's closure rests on. |
| `cpu_request_resize_record.py` | — | Derived the CPU-request before/after comparison from two `make load` records and an availability probe. All three inputs are tracked, so the derivation is re-doable by hand. |
| `marts_reach_probe.py` | — | A one-time reachability probe for the marts publish transport. |
| `canary_split_paste.py` | — | Printed the canary split as Prometheus drew it. The split is banked in `automation/runs/m6-canary/` and re-derivable from Prometheus. |

**The three reference sites landed in the same commit** (gotcha #91's rule: a
label or a filename lives in more artefacts than the one you are editing). The
sharpest is `src/taxi_mlops/training/gate_eras.py:95`, where a deleted file was
named inside a **runtime error message** — delete it without editing that string
and a live recovery instruction points at a file that is not there.

**Also deleted:** `_to_delete/` (5 files, including a skeleton zip), two empty
`tests/{integration,smoke}/README.md`, and the dead `RAW_2019_DTYPES` constant.

**Nothing else was deleted.** No gate, no red team, no recorded drill — those
are a PO fork by the directive's own text, and no slice took one.

---

## 3. What was merged, cluster by cluster

Every consolidation in this cleanup followed one rule, and it was set by CU-S2
before any code moved: **fingerprint the bodies first, and split by BEHAVIOUR
rather than by name.** Two functions sharing a name and differing in what they
do are not duplication; merging them is how a guard gets weakened inside a diff
that reads as deduplication.

| Slice | Cluster | Copies → homes | Measured cost |
|---|---|---|---|
| CU-S2 | test infrastructure: `REPO = Path(...)`, strip-comments helpers, `_calls()` | 47 → 1 · 13 → 1 · 7 → 0 | tests grew; three `_calls()` semantics were found to be genuinely different and were NOT merged |
| CU-S3 | `verify_harness.sh` — the counting harness in 8 gates | 8 byte-identical → 1 | 8,512 → 8,342 lines; **each gate's diff is exactly ONE hunk** |
| CU-S3 | `redteam_restore.sh` — the snapshot/restore scaffold in 8 drills | 8 byte-identical → 1 | 1,784 → 1,536; the sixteen files go 10,296 → 9,878 against 177 lines of library |
| CU-S4 | `scripts/_lib/` — ports, k8s, monitoring, records | `http_get` 5 copies/3 bodies · `prom_query` 5/4 · `kubectl` 8/6 · `port_forward` 6/6 · `prom_rules` 4/2 | 11 scripts 4,575 → 4,359 code lines, library +231, **net +15** |
| CU-S5 | `lib/isvc_deploy.sh` — the deploy skeleton | route-port heredoc 5 copies/2 bodies · alias guard 4/4 · readiness waits 4 · route wait 3 | 5 scripts 725 → 596 code lines, library +62, **net −67** |

**CU-S4 cost lines and CU-S5 saved them, and the difference is the finding.**
CU-S4's cluster had genuinely diverged — five names, sixteen bodies — so the
merged version had to keep the strictest behaviour of every copy it replaced,
and that behaviour was code somebody had dropped. CU-S5's cluster was four
byte-identical heredocs and one drifted copy, so merging it was mostly
subtraction. **A consolidation that costs lines is not a failure; it is a
divergence being repaired in public.**

### What CU-S5 merged, precisely

Fingerprinted before anything moved (normalised bodies, sha-hashed):

- **The route-port heredoc: 5 copies, 2 distinct bodies.** Four byte-identical
  (`deploy_champion`, `deploy_shadow`, `deploy_canary`, `deploy_serving`); the
  fifth, `deploy_transformer.sh`, had drifted to a **cwd-relative** kind-config
  path and a shorter refusal message. The merged version anchors the path at
  `$REPO_ROOT` — the stricter form, and one that survives the `cd "$REPO_ROOT"`
  two lines above it ever being removed.
- **The alias no-move guard: 4 copies.** The MECHANISM moved (read before, read
  after, differ → exit 2); the ARGUMENT did not. Each deploy cites its own law —
  M5 kickoff law 2, M6 law 3 — and those citations are passed IN as trailing
  arguments and printed by the shared guard. A shared sentence would have made
  four different laws look like one, and a test now asserts each caller still
  carries its own.
- **The two readiness waits: 4 copies**, all carrying the same order for the
  same two reasons (gotcha #71 and F-036). `deploy_transformer.sh` waits on TWO
  Deployments, so the component list is an explicit argument.
- **The route wait: 3 copies** — and this one is a **behaviour change**, named
  because it is one. `deploy_shadow.sh` and `deploy_canary.sh` exited 1 with a
  hint on timeout; `deploy_transformer.sh` polled sixty times and then **fell
  through silently** into its accept check, so an unroutable transformer
  reported as a failed accept — a confusing failure blaming the wrong component
  (gotcha #55's family). The lib fails on timeout, which is what two of the
  three copies already did.

**What deliberately did NOT move**, stated in the lib's own header under a
heading a test requires: every deploy's **accept check** (they are the program's
arguments and not one is a copy of another — `make serve` asks for a prediction,
the canary proves ADR-011 condition 2 both ways, the transformer reads
`X-Taxi-Lookups` off the answer); the alias guard's **citations**; the
**DRY_RUN narrations** (the audit's own do-not-consolidate row); every
**manifest render and placeholder refusal**.

One asymmetry was preserved rather than tidied: `deploy_canary.sh`'s alias guard
never carried a law citation and still does not. Writing one for it would be
inventing an argument inside a deduplication. The gap is named in the script.

### Two clusters left deliberately partial (CU-S4, carried here)

- **The record readers** — only the *is it there?* question moved into
  `_lib/records.py`. Readers whose shape-check or failure message is doing real
  work kept it beside their artefact, and `store_watch_headroom.py`'s
  genuinely-optional record has its own test so a later sweep cannot "finish the
  job" by breaking it.
- **The feast trio** (`feast_online_parity.py`, `feast_retrieval.py`,
  `feast_server_parity.py`) still carry their own port-forwards, because
  "exactly ONE subprocess call" AST pins guard them and re-deriving those
  deserves its own argument. **No AST pin was tripped or widened anywhere in
  this cleanup.**

---

## 4. The finding the cleanup produced that was not about cleanliness

**Two drills had reserved the same ephemeral port** (CU-S4). `gameday_m6.py`
used 9096 for Alertmanager and `drift_fire_drill.py` used 9096 for the
pushgateway. Twelve ephemeral ports across the repo were coordinated *by
comment*, and each comment enumerated the neighbours its author had checked —
the drift drill's comment cites the alert drill's 9095 as the precedent it is
avoiding, and the store drill's names four neighbours and misses gameday
entirely. Latent rather than live (nothing runs those two concurrently), fixed
by moving drift's pushgateway to 9103 and putting all twelve in
`_lib/ports.py` with a reason each and an `assert_unique()` a test runs.

That is what the cleanup was for. **A convention maintained by comments is a
convention that is already broken somewhere nobody has looked.**

---

## 5. Every re-derived guard — old property, new property

This is the section the directive's floor actually turns on. Twelve guards went
red across the five slices, **every one because the property it pinned had moved
rather than gone**, and every one was re-derived to the property, never widened
away (gotcha #50; the charter names this the single biggest risk).

| Slice | Old property (per file) | New property |
|---|---|---|
| CU-S2 | each test file declares its own `REPO` | one `conftest` helper, asserted by `test_conftest_helpers.py` |
| CU-S3 ×8 | `"trap restore EXIT" in body` and `"sha256sum" in body` | two halves: the drill SOURCES the scaffold and calls `redteam_snapshot`/`redteam_assert_restored` — and the scaffold is **watched restoring**, including on an abnormal exit, and watched REFUSING a `cp` that returned 0 into a directory |
| CU-S3 ×8 | each gate declares `FAILS=0` / `consume()` | each gate sources the harness and re-declares none of it; `consume` is watched counting, and the subshell hazard behind the `consume < <(...)` idiom is MEASURED rather than asserted in a comment |
| CU-S5 | `deploy_champion.sh`: `text.index("rollout status") < text.index("--for=jsonpath=")` | the order is asserted ONCE, by RUNNING `isvc_wait_ready` against a recording fake `kubectl` and reading the order off what was actually invoked. Per-file: the deploy sources the lib, calls it for its own isvc, and re-declares neither leg |
| CU-S5 | `deploy_shadow.sh`: same index comparison | same |
| CU-S5 | `deploy_champion.sh`: `re.search(r'if \[\[ "\$ALIAS_BEFORE" != ...')` and `"exit 2" in body` | `isvc_assert_alias_unmoved` is watched exiting **2** on a moved alias and watched returning silently on an unmoved one; per-file, the deploy reads on both sides, hands both to the guard, and still carries its own law citation |
| CU-S5 | `deploy_shadow.sh`: `text.count("champion_version") >= 3` | `count("isvc_champion_version") == 2` — the honest count once the definition is not local. The old `>= 3` was one definition plus two calls; the property was only ever about the two READS |

**The replacements are stronger instruments, not weaker ones.** Reading source
text for `"rollout status"` cannot tell you the rollout was actually invoked
first; running the function against a recording shim can. Nine of the twelve
re-derivations moved from reading a file to running a behaviour.

**Two tests DISAPPEARED in the whole cleanup and both are named**: the
per-file order pins in `test_deploy_champion.py` and `test_shadow_and_spike.py`
did not disappear — they were rewritten in place, and their docstrings carry the
old assertion and why it moved. No assertion was deleted to make a migration
pass.

**One guard of my own went red for the right reason during CU-S5 and was
narrowed rather than widened**: a new needle `"rollout status" not in body`
matched `kubectl -n platform rollout status deployment/minio` — a different
object, waited on for a different reason, nothing this migration touched. The
needle is scoped to the isvc's own workload now (gotcha #99: the needle must
name the thing, not a word the thing shares with something legitimate).

---

## 6. The guarantees, re-checked

The floor is "must not weaken what the program can PROVE". These are the rows
that would matter if they had moved, and none did.

| Guarantee | State at close |
|---|---|
| `@champion` | version **2** / `feature_set v2`, versions `['1','2']` — no version 3 |
| Anything fitted, any alias moved, any version created | **none, in any slice** |
| The wire | untouched by CU-S1…S4; CU-S5 changed no manifest and no deployed object |
| `uv.lock` | byte-identical to `lock-rebaselined-m9-publish` throughout |
| DVC pins | all 5 `up to date` |
| Tracked records under `automation/runs/` | none rewritten (see §7 for the one place this took work) |
| Thresholds, bars, knobs, gate conditions | none moved |
| README Status table | byte-unmoved, pinned by `readme-check`'s `STATUS_ROWS` |
| `src/` modules unreferenced outside themselves | **0**, before and after |
| Boundary laws (`src/` imports no orchestrator; `analytics` absent from `src/`) | hold |

---

## 7. The full red-team battery

The charter's close-out demonstration: **every `make *-redteam` target, run
after all five slices, each RED on its plant and GREEN on the restore.** Each
drill defines its own inverted verdict — it exits 0 when its plant was CAUGHT —
so `returncode = 0` below is the drill saying the guard still works.

Record: `automation/runs/m-cleanup/battery.json`, written by
`automation/runs/m-cleanup/battery.py` (a runner, not a judge: it records exit
code and wall-clock and asserts nothing the drills do not already assert).

**19 of 19 green, 1,593.6 s (26.6 min) of wall-clock, 2026-08-31.**

| target | verdict | wall-clock |
|---|---|---:|
| `make leakage-redteam` | **RED on plant, GREEN on restore** | 461.6 s |
| `make predictions-redteam` | **RED on plant, GREEN on restore** | 406.0 s |
| `make gate-redteam` | **RED on plant, GREEN on restore** | 246.0 s |
| `make train-redteam` | **RED on plant, GREEN on restore** | 161.2 s |
| `make security-scan-redteam` | **RED on plant, GREEN on restore** | 93.6 s |
| `make hook-redteam` | **RED on plant, GREEN on restore** | 47.9 s |
| `make feast-online-parity-redteam` | **RED on plant, GREEN on restore** | 23.2 s |
| `make marts-redteam` | **RED on plant, GREEN on restore** | 21.6 s |
| `make verify-m4-redteam` | **RED on plant, GREEN on restore** | 20.2 s |
| `make verify-m2-redteam` | **RED on plant, GREEN on restore** | 19.2 s |
| `make gate-margin-redteam` | **RED on plant, GREEN on restore** | 17.2 s |
| `make parity-redteam` | **RED on plant, GREEN on restore** | 16.0 s |
| `make verify-m5-redteam` | **RED on plant, GREEN on restore** | 12.4 s |
| `make verify-m7-redteam` | **RED on plant, GREEN on restore** | 10.6 s |
| `make verify-m8-redteam` | **RED on plant, GREEN on restore** | 9.7 s |
| `make verify-m3-redteam` | **RED on plant, GREEN on restore** | 9.4 s |
| `make verify-m9-redteam` | **RED on plant, GREEN on restore** | 9.2 s |
| `make image-smoke-redteam` | **RED on plant, GREEN on restore** | 4.3 s |
| `make verify-m6-redteam` | **RED on plant, GREEN on restore** | 4.3 s |

The four most expensive are the four that FIT something — `leakage-redteam`
fits an aggregate table across the val month on purpose and measures **+0.0551
min on the month it saw against −0.1367 on the month it did not**;
`train-redteam` puts a permuted-label challenger through the real gate and gets
**VERDICT: REFUSE**, exit 1, with the registry read before and after and found
identical. Both still say what they said when they were written.

**Two things the battery taught that the charter did not anticipate:**

1. **`hook-redteam` and `security-scan-redteam` refuse a dirty working tree**,
   and they are right to — both commit and then destroy history. Running the
   battery therefore has an ORDERING constraint: anything that writes a tracked
   file must be committed before those two run. The runner tripped this twice on
   its own record.
2. **Two drills rewrite their own tracked records as a side effect of running.**
   `parity-redteam` re-runs `make parity`, which rewrites
   `automation/runs/m5-parity/parity.json`; `hook-redteam` writes
   `automation/runs/m9-hook/redteam.json`. Both diffs were **timestamp-only** —
   every measured number identical, `max_abs_delta_minutes: 0.0` unchanged — and
   both were restored from git, because the battery is a VERIFICATION and not a
   re-measurement, and a re-dated record still destroys another milestone's
   provenance (F-053/F-063, gotcha #48, third and fourth occurrence in this
   program). **A close-out battery that runs "every red team" cannot be run
   without this check**, and that is worth knowing before the next one.

---

## 8. The ten gates

The charter's floor, and the last line of this report: no CU slice may merge
until `verify-m0`…`verify-m9` run GREEN over it.

**All ten GREEN over the finished cleanup, 2026-08-31, exit 0 every one.** Run
live against the cluster at CU-S5's HEAD, after every slice had landed:

| gate | `ok` lines | gate | `ok` lines |
|---|---:|---|---:|
| `verify-m0` | 25 | `verify-m5` | 49 |
| `verify-m1` | 45 | `verify-m6` | 63 |
| `verify-m2` | 58 | `verify-m7` | 63 |
| `verify-m3` | 47 | `verify-m8` | 51 |
| `verify-m4` | 39 | `verify-m9` | 46 |

(The counts are `ok`-prefixed transcript lines, counted from each gate's own
output at this HEAD — the same quantity each gate's GREEN banner is read off.
`verify-m1` is the slow one at 162.9 s, because it deletes and re-derives ~1 GB
of processed parquet: byte-identity checked against data that was never
re-derived is not a check, and M1's rule that a gate has no fast mode has now
been inherited nine times.)

Plus, at the same HEAD: host suite **1,408 passed, 0 skipped** (1,320 at charter
time) · `ruff check src tests pipelines` **All checks passed!** ·
`make readme-check` **GREEN**.

---

## 9. What was deliberately NOT done

Named here so a later reader does not mistake an omission for an oversight.
Each is out of scope by the charter's own text.

- **Deleting any gate, red team or recorded drill** — a PO fork by the
  directive.
- **The literal-pin review** (the seed's optional slice 6, `== N` → floor):
  guard-semantics work with low followability yield. Where a slice tripped one
  such pin it re-derived that one, no sweep.
- **Widening `ruff check` to `scripts/`.** The house lint net is
  `ruff check src tests pipelines`; `scripts/` — the audit's "bloat center" —
  has never been linted, and a bare `ruff check` over it reported 42 E501s at
  charter time. Mechanical churn across many files mid-consolidation invites
  conflicts. **This is a real gap and it bit once**: CU-S4 produced an
  `F821 Undefined name 'subprocess'` that CI would not have caught, found only
  by linting the touched files by hand. Any future slice touching `scripts/`
  should do the same.
- **DRY_RUN plumbing**, `docs/` historical prose, `automation/runs/**`, the
  README Status table, every threshold/bar/knob, the wire, the registry,
  `uv.lock`.
- **A new code map.** Decided at charter time and not re-litigated: CLAUDE.md's
  command table already maps script → command → verified-when, and a second map
  would be a twin (F-013's one-home rule applied to navigation). The
  navigability deliverable of this cleanup IS the deletion of the copies a
  reader currently re-reads per file, plus the module docstrings on each new
  `lib/` home stating what lives there and what deliberately does not.
- **AWAITING_PO 2026-08-30-2** (the VM/watchdog deadlock) — the PO's fork; no
  slice touched watchdog or chain plumbing.
