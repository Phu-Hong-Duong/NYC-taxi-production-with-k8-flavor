# Cleanup audit seed — VERIFIED BY RUNNING

**What this is.** `docs/cleanup_audit_seed.md` is the PO's advisory static audit
for the cleanup directive (AWAITING_PO **2026-08-29-2**). Its own §6 states the
limitation plainly: *"No execution of tests/gates (counts are static); no
behavioral verification of 'orphan' status beyond reference-grepping"*, and the
seed's header says **ARCH verifies before trusting**.

This is that verification, produced 2026-08-30 by the executor session (de) at
HEAD `6a87dea`. Instrument: `scripts/cleanup_audit_verify.py`, re-runnable —

```
uv run python scripts/cleanup_audit_verify.py [--json automation/runs/m-cleanup/audit-verify.json]
```

Record: `automation/runs/m-cleanup/audit-verify.json`.

**It is ADVISORY and it charters nothing.** It deletes nothing, edits nothing,
moves no bar and issues no keep/delete verdict — those are ARCH's to charter
and, where a whole gate or red team is involved, the PO's to fork. Its only
claim is that the numbers a charter would be argued from have now been
re-derived by somebody running them.

**Headline: 43 CONFIRMED · 6 DIFFERS · 3 newly MEASURED.** The seed is
substantially sound. Every DIFFERS is accounted for below, and **none of them
is the seed being wrong about the codebase** — five are a counting basis and
one is my own regex.

---

## 1. What the seed got right (the load-bearing numbers)

Re-measured from the tracked tree, and — for the one number the seed could not
produce — from a real `pytest --collect-only`:

| Claim | Seed | Measured |
|---|---:|---:|
| `scripts/` files · lines | 141 · 41,848 | **141 · 41,848** |
| `tests/` files · lines | 74 · 22,411 | **74 · 22,411** |
| `src/` files · lines | 54 · 12,867 | **54 · 12,867** |
| verify-gate LOC (10 gates) | 9,055 | **9,055** |
| Tier A total LOC | 1,050 | **1,050** (all six files exist at the stated size) |
| Tier B total LOC | 411 | **411** (all five: exactly 1 Makefile anchor, 0 code, 0 test) |
| `def test_` | 1,212 | **1,212** |
| pytest collected | ~1,320 | **1,320 — RUN, not grepped** |
| Makefile targets missing from `.PHONY` | 11 | **11** (named in the record) |
| strip-comments helper copies | 13 | **13** (`without_comments`×7 · `code_only`×6) |
| `_calls()` defining files · semantics | 7 · 3 | **7 · 3** |
| `KUBECTL=(` shell preamble | 30 | **30** |
| python kubectl wrappers | 8 | **8** |
| `src/` modules unreferenced | 0 | **0** |
| `RAW_2019_DTYPES` dead | yes | **yes** — definition + the seed's own mention, no reader |

Two things the seed asserted and did not count, now counted: **8 shell files
define `consume()` and all 8 bodies normalise to ONE string** — the
"byte-identical harness" claim is true, so slice 2's diffs really are pure
deletion. And **15 shell + 12 python files run `kubectl port-forward`**, which
is the size of the forward cluster.

## 2. Every DIFFERS, accounted for

| Row | Seed | Measured | Why |
|---|---:|---:|---|
| `docs/` files · lines | 111 · 34,653 | 112 · 34,794 | **the seed itself** was committed after it counted |
| `automation/` files · lines | 137 · 45,255 | 135 · 45,264 | tracked-only basis: `.log`/`.status` are gitignored (F-029 tracks the JSON, not the logs) |
| red-team LOC | 1,970 | 2,957 over **16** files | different population — the seed counted "the nine red teams", `scripts/*redteam*.sh` matches 16. Not a contradiction; the charter should say which set it means |
| `REPO = Path(...)` re-declared | 57 | 47 | **my regex**, first draft anchored at line start and missed indented/annotated forms. Corrected in the instrument; 47 is the tracked-`.py` count under `tests/` |
| test `.py` files | 74 | 72 | the seed's 74 is every tracked file under `tests/`, `.py` or not |

## 3. The three constraints the seed did not carry — this is the yield

The seed's Tier A verdict (**"prose only"**) is **CONFIRMED for all six files**:
nothing imports them, no Makefile target invokes them, no test names them, no CI
job runs them. But "prose only" is not the same as "nothing points at it", and
three of the six are named in **live sentences inside shipped code** that a
deletion would silently orphan:

1. **`f016_replay_probe.py` is named inside a RUNTIME ERROR MESSAGE** —
   `src/taxi_mlops/training/gate_eras.py:95`. When the frozen pre-B verdict set
   is missing, `GateEraError` tells a human *"It is a TRACKED record written by
   scripts/f016_replay_probe.py … Restore it from git rather than regenerating
   it"*. Delete the file without editing that string and the recovery
   instruction points at nothing — **gotcha #91 exactly: the label an artifact
   PRINTS is a different artifact from the label in its header, and only the
   printed one is read at 3am.** If this file goes, the message changes in the
   same commit. (The seed already flagged this file for a different reason —
   AWAITING_PO 2026-08-24-4 cites it as "re-runnable in seconds".)
2. **`rev_rederive_m7.py`** — `scripts/f051_counterfactual.py:7`, a docstring
   that exists to explain *why* the counterfactual was re-run against fixed
   arithmetic. It is that script's provenance, not a decoration.
3. **`marts_reach_probe.py`** — `infra/manifests/flyte-task-podtemplate.yaml:116`,
   the comment carrying the measurement that justifies `MARTS_DB_HOST`
   (`PROBE-OK ('marts', 'marts')`).

**A fourth constraint, and it is a correctness one: the `_calls()` consolidation
is NOT mechanical.** The seed is right that one name carries three meanings; the
fingerprints, read off the AST:

| Semantics | Files |
|---|---|
| called-name segments (guarded by `ast.Call`) | `test_canary_and_rollback` · `test_gameday_and_restore` · `test_shadow_and_spike` · `test_store_watchdog` |
| dotted call paths (guarded by `ast.Call`) | `test_load` · `test_parity` |
| **every `Attribute`/`Name` regardless of call** | `test_tuning` |

`test_tuning.py`'s version has **no `ast.Call` guard at all**, and it backs a
*forbidding* assertion (the registry API must not appear). Broader is therefore
**stronger** there. Collapsing all seven onto the call-guarded helper would
**weaken a live guard while the diff reads as pure deduplication** — the exact
shape gotcha #50 warns about, arriving through consolidation. Slice 1 must name
this file and decide it explicitly rather than migrate it.

## 4. What this did NOT verify

No gate was run, no red team was fired, no consolidation was attempted. The
seed's **~2,500–3,500 LOC removable** ceiling is a judgement, not a count, and
is left as the seed's estimate — nothing here confirms or refutes it. Whether
any given consolidation is *safe* is a question only the gate sweep can answer,
and that belongs to the slices.

## 5. The instrument's own defects, recorded

The first draft of `cleanup_audit_verify.py` **reported three live comments as
executing references**, because it classified reference sites by file
extension instead of parsing them. That is gotchas #53/#60/#68/#99 — *in a repo
where prose is load-bearing, a check about code structure must parse code* — for
the sixth time, and this checker was its own sixth occurrence. Fixed at the
cause: comments and docstrings are found with `ast`, and a name inside a
non-docstring string literal gets its own class (`runtime-message`), which is
what surfaced finding 1 above.

Its `_calls` fingerprinter also carried an operator-precedence bug
(`a and b or c`) that reported **2** semantics where there are **3** — i.e. it
would have quietly retired the seed's sharpest finding. Both were caught by
reading the source the checker disagreed with, which is the only reason this
page reports 3 and not 2.
