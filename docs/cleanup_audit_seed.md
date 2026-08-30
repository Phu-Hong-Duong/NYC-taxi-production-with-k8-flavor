# Cleanup audit SEED — measured input to AWAITING_PO 2026-08-29-2

**What this is.** A READ-ONLY static audit of the codebase at `19370f1`,
produced 2026-08-30 by the PO's Windows-side session (three parallel audit
agents over the synced viewing copy) as an ADVISORY input to the
codebase-cleanup directive (AWAITING_PO **2026-08-29-2**). Nothing was run —
no tests, no gates, no make targets — so every number here is a grep-and-count
measurement, not a verified-by-running one, and sampled LOC estimates carry
**±30%**. **ARCH verifies before trusting**; where this seed and ARCH's own
audit disagree, ARCH's measurement wins. This file is a seed, not a charter,
and it deletes nothing by itself.

## 1. Where the code is (counting basis: raw `wc -l`, caches excluded)

| Area | Files | Lines | Note |
|---|---:|---:|---|
| `scripts/` | 141 | 41,848 | 70 `.py` (22,818) + 68 `.sh` (18,950) — **the bloat center** |
| `docs/` | 111 | 34,653 | prose record — mostly NOT cleanup surface |
| `tests/` | 74 | 22,411 | all in `tests/unit/`; integration/smoke dirs are empty shells |
| `src/` | 54 | 12,867 | product code — **no dead modules found** |
| `automation/` | 137 | 45,255 | 97.8% is tracked JSON run-evidence — MUST NOT be touched |
| `infra/` + `analytics/` + `pipelines/` + `demo/` | 74 | 10,469 | |

Executable code total: ~**88,790 lines in 365 files**. The ten `verify_m*.sh`
gates are **9,055 lines**; the nine red teams add **1,970**. 14 of the 20
largest code files live in `scripts/`.

## 2. Dead-code candidates (the honest scope: small)

**Zero scripts are referenced by nothing, and zero `src/` modules are
unimported.** The deletable surface is one-off probes whose findings are
banked in tracked records:

**Tier A — referenced by PROSE ONLY** (no Makefile target, no script, no test;
the two "code" hits are a comment and a docstring): `rev_rederive_m7.py` (239)
· `f016_replay_probe.py` (296) · `retrain_proof_record.py` (193) ·
`cpu_request_resize_record.py` (148) · `marts_reach_probe.py` (99) ·
`canary_split_paste.py` (75) — **1,050 LOC**. Each is a measurement already
delivered into `automation/runs/**` or a doc; deleting the instrument does not
delete the measurement. CAVEAT for the charter: `f016_replay_probe.py` is
named in AWAITING_PO 2026-08-24-4 as "re-runnable in seconds" — deleting a
re-run affordance a PO answer cites should be called out in the PR, not
slipped through.

**Tier B — single Makefile anchor, no test, no caller**:
`marts_peak_probe.sh` (125) · `feast_registry_dump.py` (97) ·
`feast_serve_probe.sh` (66) · `contract_probe_fixtures.sh` (62) ·
`f008_guard_exercise.py` (61) — **411 LOC**. NOTE: `contract-probe-fixtures`
and `feast-serve-probe` are cited as VERIFIED commands in CLAUDE.md's command
table — these are keep-or-consciously-retire decisions, not obvious deletions.

Also: `_to_delete/` holds 18 stale git-lock files + 1 zip (untracked débris);
`tests/conftest.py` carries a dead constant (`RAW_2019_DTYPES`, referenced
nowhere); 11 Makefile targets are missing from `.PHONY`.

## 3. Duplication clusters in `scripts/` (the big win)

Nothing in `scripts/` imports anything else in `scripts/` today — every idiom
was re-implemented per story. Conservative mechanical-duplication totals:

| Cluster | ~dup LOC | Confidence | One-home candidate |
|---|---:|---|---|
| verify-gate harness (`consume < <(`, ok/no/FAIL counters) — **byte-identical** across the 8 gates | ~470 | very high | sourced `scripts/lib/verify_harness.sh` |
| kubectl port-forward setup/teardown — 9 shell copies + 12–13 Python copies | 300–400 | high | `scripts/lib/forward.sh` + one `forward()/wait_http()` in a shared py lib; the helper doubles as the PORT REGISTRY the copies now coordinate by comments |
| Prometheus/Alertmanager drill plumbing (`prom_rules`/`prom_query`/`firing_months`/`http_get`/`say`) across 5–6 drills | 300–450 | high | `scripts/_monitoring_lib.py` |
| red-team sha256-snapshot + EXIT-trap restore scaffold — byte-identical in 8 drills | ~240 strict | high | `scripts/lib/redteam_restore.sh` |
| isvc deploy skeleton (ROUTE_PORT heredoc ×5 verbatim · alias no-move guard ×4–7 · three wait legs ×4) | ~200 strict | high | `scripts/lib/isvc_deploy.sh` — share port/alias/waits, **leave each accept check bespoke** |
| record readers (`json.loads(read_text())` + exists-check-naming-the-drill) — no shared helper anywhere | 500–700 diffuse | medium | `load_record(path, produced_by=…)`; the fail-message is the valuable part |
| psql-over-kubectl-exec micro-wrappers (~10 files) | 80–120 | high | `scripts/lib/pg.sh` (`marts_publish.py`'s Transport stays the publish home) |
| `_kubectl()` wrappers (8 py files) + `KUBECTL=(…)` preamble (30 sh files) | ~150 | high, trivial | folds into the libs above |
| champion-resolver caller shims (~10 × 3–10 LOC; the F-009 two-hop itself is already ONE home) | 50–80 | high | same |
| DRY_RUN plumbing (21 files) | ~40 | **do not consolidate** — each dry-run narration is deliberately bespoke |

**Constraints the charter must carry** (from the audit, so the executor does
not rediscover them): (1) introducing `scripts/lib/` creates the repo's first
scripts→scripts import edge — the F-026/image-staleness guards already cover
`scripts/`, but the in-image suite and `.dockerignore` assumptions should be
re-checked in the same slice; (2) the verify gates' LEGS are deliberately
divergent second witnesses — consolidate the harness (~5% of gate LOC), never
leg logic; (3) several near-copies are two-witness designs on purpose (e.g. a
gate reading a record AND the live system) — only load-and-fail plumbing is
mechanical.

## 4. The test suite (22,409 LOC, 1,212 `def test_`, ~1,320 collected)

- **Meta-test share:** 13 whole files (4,164 LOC, 210 tests, **18.6% of the
  suite**) test OTHER CHECKS — the verify gates, red teams, scanners, and in
  one case the other test files themselves. 22 of 70 test files never import
  `taxi_mlops` at all (27.9% of suite LOC). This is the program's design
  (guards need guards), but its per-file scaffolding is pure copy-paste.
- **No shared test infrastructure:** there is NO `tests/unit/conftest.py`;
  the root conftest reaches 7 of 70 files. Consequences, measured:
  `REPO = Path(...)` re-declared in **57 files** · strip-comments helper
  copy-pasted **13×  under two names** (`without_comments`/`code_only`) ·
  `_record()` ×5 · `invokes()` ×4 byte-identical · `_imported_roots` ×3 ·
  subprocess-argv AST extractor ≥5 inline re-implementations.
- **A live hazard, not just bloat:** `_calls()` exists in **7 files with 3
  DIFFERENT semantics** under one name (set-of-names vs dotted-names vs
  every-Attribute-regardless-of-call). Two tests that read identically assert
  different things. Consolidating this one is a correctness fix.
- **Literal-pinning inventory** (the gotcha-#50 class) is catalogued in the
  audit transcripts; the gates' own leg counts are pinned as FLOORS (`>= N`),
  which is the resilient form — the charter should preserve that style, and
  the `== N` equality pins are the review targets.

## 5. Suggested slicing (ARCH's to accept, reshape, or discard)

Each slice is mechanical, independently green, and ends with the full gate
sweep + host suite + red teams still able to go RED:

1. **Test infrastructure**: create `tests/unit/conftest.py`; move
   `REPO`/strip-comments/`_record`/`invokes`/argv-extractor there; resolve the
   `_calls` 3-semantics hazard with three honestly-named helpers; migrate ~57
   files mechanically. Largest file-count touch, zero assertion changes.
2. **Shell libs**: `verify_harness.sh` + `redteam_restore.sh`; migrate 8
   gates + 8 red teams. Byte-identical scaffolds, so diffs are pure deletion.
3. **Python monitoring/k8s lib**: forwards, prom readers, `_kubectl`,
   record-loader; migrate drills + probes.
4. **isvc deploy lib**: port/alias/wait legs across the 4 isvc deploys.
5. **Dead code**: Tier A deletions (+ Tier B decisions), `_to_delete/` sweep,
   `.PHONY` fixes, dead conftest constant, empty test-dir shells.
6. (If desired) literal-pin review: `== N` → property/floor where the literal
   pins another artifact's incidental shape.

Rough honest ceiling: **~2,500–3,500 LOC of mechanical duplication and
~1,500 LOC of dead code** are removable without touching one bar, record,
wire, or witness — call it 4–5% of the executable codebase and a much larger
share of its *apparent* complexity, since the deleted copies are exactly the
lines a reader currently has to re-read per file. The floor from the
directive stands over every slice: all ten gates GREEN, red teams RED on
their plants, no threshold/record/wire/lock change; deleting a whole gate or
red team is a PO fork, not a slice.

## 6. What this seed did NOT do

No execution of tests/gates (counts are static); no behavioral verification
of "orphan" status beyond reference-grepping (basename-with-extension, comment
hits hand-checked for Tier A only); Makefile `$(VAR)` paths not expanded; LOC
per duplicated block sampled, not diffed pair-wise. Transcripts of the three
audit agents live with the PO's Windows-side session; this file carries only
what the charter needs.
