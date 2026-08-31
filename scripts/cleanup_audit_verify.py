"""Verify the cleanup audit SEED by RUNNING what the seed only grepped.

`docs/cleanup_audit_seed.md` is an ADVISORY static audit produced by the PO's
Windows-side session (AWAITING_PO 2026-08-29-2). Its own §6 states the
limitation plainly: "No execution of tests/gates (counts are static); no
behavioral verification of 'orphan' status beyond reference-grepping".

This is the twin — the `error_memo_numbers.py` / `drift_memo_numbers.py` /
`readme_check.py` idiom aimed at an audit instead of a memo. Every number the
charter would be argued from is re-measured HERE, from the tracked tree and
from a real pytest collection, and printed beside the seed's claim.

It is a READER. It deletes nothing, edits nothing, and issues no verdict about
what should go — that decision is ARCH's to charter and, where a whole gate or
red team is involved, the PO's to fork (the directive says so in terms).

A claim that DIFFERS is not automatically the seed being wrong: the seed
counted the synced viewing copy with `wc -l` over all files, this counts
tracked files. Where the counting basis differs the row says so. What matters
is that the charter is argued from numbers somebody re-derived.

    uv run python scripts/cleanup_audit_verify.py [--json <path>]

Exit 0 always unless the measurement itself fails: this reports, it does not
gate.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "docs" / "cleanup_audit_seed.md"

# ---------------------------------------------------------------------------
# The seed's claims, transcribed once so a reader can diff prose against code.
# ---------------------------------------------------------------------------

SEED_AREAS = {
    # area: (files, lines) as §1 of the seed reports them
    "scripts": (141, 41_848),
    "docs": (111, 34_653),
    "tests": (74, 22_411),
    "src": (54, 12_867),
    "automation": (137, 45_255),
}

# These six names are the seed's BEFORE claim and must survive their own files:
# CU-S1 deleted all six (2026-08-31), so the instrument now reports each ABSENT
# and a Tier A total of 0 — which is the after-number CU-S5's report is owed.
# Editing this dict to match today's tree would delete the only thing the
# instrument measures against.
SEED_TIER_A = {
    "rev_rederive_m7.py": 239,
    "f016_replay_probe.py": 296,
    "retrain_proof_record.py": 193,
    "cpu_request_resize_record.py": 148,
    "marts_reach_probe.py": 99,
    "canary_split_paste.py": 75,
}
SEED_TIER_A_TOTAL = 1_050

SEED_TIER_B = {
    "marts_peak_probe.sh": 125,
    "feast_registry_dump.py": 97,
    "feast_serve_probe.sh": 66,
    "contract_probe_fixtures.sh": 62,
    "f008_guard_exercise.py": 61,
}
SEED_TIER_B_TOTAL = 411

SEED_TESTS_DEF_TEST = 1_212
SEED_TESTS_COLLECTED = 1_320
SEED_REPO_REDECLARED = 57
SEED_CALLS_FILES = 7
SEED_CALLS_SEMANTICS = 3
SEED_STRIP_COMMENT_COPIES = 13
SEED_PHONY_MISSING = 11


def sh(*args: str, cwd: Path = REPO) -> str:
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, check=False
    ).stdout


def tracked(pattern: str) -> list[Path]:
    out = sh("git", "ls-files", pattern)
    return [REPO / line for line in out.splitlines() if line.strip()]


def wc(paths: list[Path]) -> int:
    total = 0
    for p in paths:
        with contextlib.suppress(OSError):
            total += len(p.read_text(encoding="utf-8", errors="replace").splitlines())
    return total


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

RESULTS: list[dict] = []


def row(claim: str, seed, measured, note: str = "") -> None:
    if seed is None:
        verdict = "MEASURED"
    elif seed == measured:
        verdict = "CONFIRMED"
    else:
        verdict = "DIFFERS"
    RESULTS.append(
        {
            "claim": claim,
            "seed": seed,
            "measured": measured,
            "verdict": verdict,
            "note": note,
        }
    )
    seed_s = "—" if seed is None else str(seed)
    print(f"  {verdict:<9} {claim}")
    print(f"            seed={seed_s}  measured={measured}" + (f"  ({note})" if note else ""))


# ---------------------------------------------------------------------------
# 1. Size map
# ---------------------------------------------------------------------------


def check_size_map() -> None:
    print("\n[1] Size map — TRACKED files only (the seed counted the viewing copy)")
    for area, (sf, sl) in SEED_AREAS.items():
        paths = tracked(f"{area}/**")
        row(
            f"{area}/ file count",
            sf,
            len(paths),
            "tracked-only basis" if sf != len(paths) else "",
        )
        row(f"{area}/ line count", sl, wc(paths), "tracked-only basis" if sl != wc(paths) else "")

    gates = [p for p in tracked("scripts/verify_m*.sh") if "redteam" not in p.name]
    reds = tracked("scripts/*redteam*.sh")
    row("verify gate LOC (10 gates)", 9_055, wc(gates), f"{len(gates)} gate files")
    row("red team LOC", 1_970, wc(reds),
        f"{len(reds)} files match scripts/*redteam*.sh; the seed's 1,970 is a "
        "narrower population ('the nine red teams'), so this is a different "
        "count, not a contradiction")


# ---------------------------------------------------------------------------
# 2. Dead-code tiers — reference classification, not a bare grep
# ---------------------------------------------------------------------------

CODE_DIRS = ("scripts/", "src/", "tests/", "pipelines/", "analytics/", "automation/", "infra/")

#: line numbers holding a non-docstring string literal, per file. A name inside
#: one of those is neither prose nor an invocation — it is a sentence a RUNNING
#: program prints, which is the class gotcha #91 exists about.
messages: dict[Path, set[int]] = {}


def _prose_lines(path: Path, text: str) -> set[int]:
    """Line numbers a parser would NOT read as code.

    This repo argues its own design at length inside the files it ships, so a
    reference found by line-matching is a reference to a SENTENCE far more
    often than to an invocation — gotchas #53, #60, #68, #99. The first draft
    of this checker classified by file TYPE and duly reported three live
    comments as executing references. Being the sixth occurrence of a lesson
    the repo has already paid for five times, it is fixed at the cause.
    """
    prose: set[int] = set()
    if path.suffix == ".py":
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return prose
        # docstrings: every constant-string expression statement
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                end = getattr(node, "end_lineno", node.lineno) or node.lineno
                prose.update(range(node.lineno, end + 1))
        messages.setdefault(path, set())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                end = getattr(node, "end_lineno", node.lineno) or node.lineno
                for ln in range(node.lineno, end + 1):
                    if ln not in prose:
                        messages[path].add(ln)
    # `#` comments for python/shell/yaml/make alike (a `#` inside a string is
    # rare in these files and errs toward calling a real call "prose", which is
    # the direction that under-claims rather than over-claims)
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            prose.add(i)
    return prose


def classify_references(basename: str) -> dict:
    """Where is this file NAMED, and does the naming site EXECUTE it?

    The seed's Tier A claim is 'referenced by PROSE ONLY'. That is a claim
    about the KIND of every reference site, so classification is the
    measurement — a hit count cannot express it, and neither can the file's
    extension.
    """
    stem = basename.rsplit(".", 1)[0]
    hits = {
        "makefile": [],
        "code": [],
        "test": [],
        "ci": [],
        "docs": [],
        "code-prose": [],
        "runtime-message": [],
        "other": [],
    }
    for path in tracked("*"):
        rel = path.relative_to(REPO).as_posix()
        if rel == f"scripts/{basename}" or rel == "scripts/cleanup_audit_verify.py":
            continue  # the file itself, and this checker
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if basename not in text and stem not in text:
            continue
        prose = _prose_lines(path, text)
        for i, line in enumerate(text.splitlines(), 1):
            if basename not in line and stem not in line:
                continue
            entry = f"{rel}:{i}"
            if rel.startswith("docs/") or rel.endswith(".md"):
                hits["docs"].append(entry)
            elif i in prose:
                # named inside a comment or docstring of a code file: still a
                # reference a deletion would orphan, but nothing executes it
                hits["code-prose"].append(entry)
            elif i in messages.get(path, ()):
                # named inside a string a RUNNING program prints
                hits["runtime-message"].append(entry)
            elif rel == "Makefile" or rel.endswith(".mk"):
                hits["makefile"].append(entry)
            elif rel.startswith(".github/"):
                hits["ci"].append(entry)
            elif rel.startswith("tests/"):
                hits["test"].append(entry)
            elif rel.startswith(CODE_DIRS):
                hits["code"].append(entry)
            else:
                hits["other"].append(entry)
    return hits


def is_prose_only(hits: dict) -> bool:
    """Nothing runs it. A runtime MESSAGE naming it does not make it a caller —
    it makes the deletion a documentation defect, reported separately."""
    return not (hits["makefile"] or hits["code"] or hits["test"] or hits["ci"])


def check_dead_code() -> None:
    print("\n[2] Tier A — the seed says PROSE ONLY (no Makefile target, no caller, no test)")
    tier_a_total = 0
    for name, seed_loc in SEED_TIER_A.items():
        p = REPO / "scripts" / name
        if not p.exists():
            row(f"Tier A {name}", seed_loc, "ABSENT", "file does not exist")
            continue
        loc = wc([p])
        tier_a_total += loc
        hits = classify_references(name)
        verdict = "prose-only" if is_prose_only(hits) else "HAS EXECUTING REFERENCE"
        detail = (
            f"make={len(hits['makefile'])} code={len(hits['code'])} "
            f"test={len(hits['test'])} ci={len(hits['ci'])} "
            f"docs={len(hits['docs'])} code-prose={len(hits['code-prose'])} "
            f"runtime-msg={len(hits['runtime-message'])}"
        )
        row(f"Tier A {name} LOC", seed_loc, loc)
        row(f"Tier A {name} status", "prose-only", verdict, detail)
        for kind in ("makefile", "code", "test", "ci"):
            for entry in hits[kind][:4]:
                print(f"              ! EXECUTES: {kind}: {entry}")
        # A deletion orphans these too — they are live sentences in shipped
        # code. Named so the charter carries the constraint rather than
        # rediscovering it after the file is gone.
        for entry in hits["code-prose"][:6]:
            print(f"              ~ named in code prose:      {entry}")
        for entry in hits["runtime-message"][:6]:
            print(f"              ! named in a RUNTIME MESSAGE: {entry}")
    row("Tier A total LOC", SEED_TIER_A_TOTAL, tier_a_total)

    print("\n[3] Tier B — the seed says single Makefile anchor, no test, no caller")
    tier_b_total = 0
    for name, seed_loc in SEED_TIER_B.items():
        p = REPO / "scripts" / name
        if not p.exists():
            row(f"Tier B {name}", seed_loc, "ABSENT", "file does not exist")
            continue
        loc = wc([p])
        tier_b_total += loc
        hits = classify_references(name)
        row(f"Tier B {name} LOC", seed_loc, loc)
        row(
            f"Tier B {name} anchors",
            "1 makefile, 0 code, 0 test",
            f"{len(hits['makefile'])} makefile, {len(hits['code'])} code, {len(hits['test'])} test",
            f"docs={len(hits['docs'])}",
        )
    row("Tier B total LOC", SEED_TIER_B_TOTAL, tier_b_total)


# ---------------------------------------------------------------------------
# 3. Small named findings
# ---------------------------------------------------------------------------


def check_small_findings() -> None:
    print("\n[4] The small named findings")

    to_delete = REPO / "_to_delete"
    tracked_in = tracked("_to_delete/**")
    row(
        "_to_delete/ exists",
        True,
        to_delete.exists(),
        f"{len(list(to_delete.iterdir())) if to_delete.exists() else 0} entries, "
        f"{len(tracked_in)} tracked by git",
    )

    conftest = REPO / "tests" / "conftest.py"
    refs = 0
    if conftest.exists():
        for path in tracked("*"):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            refs += text.count("RAW_2019_DTYPES")
    # one occurrence is the definition in tests/conftest.py; one is the seed
    # document naming it. No reader anywhere.
    row(
        "RAW_2019_DTYPES is dead",
        True,
        refs <= 2,
        f"{refs} occurrence(s) in tracked files = definition + the seed's own mention",
    )

    # Join backslash continuations BEFORE parsing. `^\.PHONY:` against the raw
    # text cannot see the second line of a wrapped declaration, so five targets
    # that GNU make reads as phony (Makefile:55's continuation) were reported
    # missing — F-083, found by CU-S1 running this check rather than reading it.
    # The seed's claim of 11 stays as the BEFORE number; 6 of those 11 were real.
    mk = (REPO / "Makefile").read_text(encoding="utf-8").replace("\\\n", " ")
    phony: set[str] = set()
    for m in re.finditer(r"^\.PHONY:(.*)$", mk, re.M):
        phony.update(m.group(1).split())
    targets: set[str] = set()
    for m in re.finditer(r"^([a-zA-Z][a-zA-Z0-9_.-]*)\s*:(?!=)", mk, re.M):
        targets.add(m.group(1))
    missing = sorted(targets - phony)
    row("Makefile targets missing from .PHONY", SEED_PHONY_MISSING, len(missing),
        ", ".join(missing[:12]) or "none")


# ---------------------------------------------------------------------------
# 4. The test suite — including the _calls() correctness hazard
# ---------------------------------------------------------------------------


def _calls_semantics(fn: ast.FunctionDef) -> str:
    """Fingerprint what a `_calls`-shaped helper actually returns.

    The seed's sharpest finding is that one NAME carries three meanings across
    seven files, so two tests that read identically assert different things.
    That is a correctness claim, so it needs a semantic fingerprint — and the
    fingerprint has to be read off the AST, not off a substring of its dump.
    (The first draft tested `"Attribute" in src and "join" in src or "'.'" in
    src`, whose precedence makes the whole expression true for any body
    containing a dot literal. It reported two semantics where there are three.)

    The two axes that actually decide the meaning:
      * does the walk REQUIRE an `ast.Call` node before recording a name?
      * does it record the last attribute segment, or the whole dotted path?
    """
    guards_call = any(
        isinstance(n, ast.Attribute) and n.attr == "Call"
        for n in ast.walk(fn)
    )
    # a dotted collector walks up through Attribute.value in a loop
    dotted = any(isinstance(n, ast.While) for n in ast.walk(fn))
    if not guards_call:
        return "every-Attribute/Name-regardless-of-call"
    return "dotted-call-paths" if dotted else "called-name-segments"


def check_tests() -> None:
    print("\n[5] The test suite — measured, and the _calls() hazard fingerprinted")
    # `tests/**/*.py` misses `tests/conftest.py` — the `**/` requires an
    # intervening directory. Filter the whole tree instead.
    test_files = [p for p in tracked("tests/") if p.suffix == ".py"]
    def_tests = 0
    repo_decl = 0
    strip_names: dict[str, int] = defaultdict(int)
    calls_impls: dict[str, list[str]] = defaultdict(list)

    for p in test_files:
        text = p.read_text(encoding="utf-8", errors="replace")
        def_tests += len(re.findall(r"^\s*def test_", text, re.M))
        if re.search(r"^\s*REPO(\s*:\s*Path)?\s*=\s*Path\(", text, re.M):
            repo_decl += 1
        for name in ("without_comments", "code_only"):
            if re.search(rf"^def {name}\(", text, re.M):
                strip_names[name] += 1
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in ("_calls", "calls"):
                calls_impls[_calls_semantics(node)].append(p.name)

    row("test files (.py, tracked)", 72, len(test_files),
        "seed's 74 counts every tracked file under tests/, .py or not")
    row("`def test_` count", SEED_TESTS_DEF_TEST, def_tests)
    row("REPO = Path(...) re-declared", SEED_REPO_REDECLARED, repo_decl)
    row(
        "strip-comments helper copies",
        SEED_STRIP_COMMENT_COPIES,
        sum(strip_names.values()),
        ", ".join(f"{k}x{v}" for k, v in strip_names.items()),
    )
    n_files = sum(len(v) for v in calls_impls.values())
    row("_calls() defining files", SEED_CALLS_FILES, n_files)
    row(
        "_calls() distinct semantics",
        SEED_CALLS_SEMANTICS,
        len(calls_impls),
        "; ".join(f"{k}: {sorted(set(v))}" for k, v in calls_impls.items()),
    )

    print("\n[6] Collection — the one thing the seed could not do: RUN it")
    out = subprocess.run(
        ["uv", "run", "pytest", "tests/unit", "--collect-only", "-q"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    tail = (out.stdout or "").strip().splitlines()
    collected = None
    for line in reversed(tail):
        m = re.search(r"(\d+)\s+tests? collected", line)
        if m:
            collected = int(m.group(1))
            break
    row("pytest collected", SEED_TESTS_COLLECTED, collected,
        "RUN, not grepped" if collected else "collection failed — see stderr")


# ---------------------------------------------------------------------------
# 5. Duplication the charter would consolidate
# ---------------------------------------------------------------------------


def check_duplication() -> None:
    print("\n[7] Duplication clusters — how many distinct copies really exist")

    gates = [p for p in tracked("scripts/*.sh")]
    consume_bodies: dict[str, list[str]] = defaultdict(list)
    forwards = 0
    kubectl_preamble = 0
    for p in gates:
        text = p.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^consume\s*\(\)\s*\{(.*?)^\}", text, re.M | re.S)
        if m:
            norm = re.sub(r"\s+", " ", m.group(1)).strip()
            consume_bodies[norm].append(p.name)
        if "port-forward" in text:
            forwards += 1
        if re.search(r"^KUBECTL=\(", text, re.M):
            kubectl_preamble += 1

    n = sum(len(v) for v in consume_bodies.values())
    row(
        "shell files defining consume()",
        None,
        n,
        f"{len(consume_bodies)} DISTINCT body/bodies — "
        + (
            "byte-identical as the seed claims"
            if len(consume_bodies) == 1
            else "they have drifted"
        ),
    )
    row("shell files using kubectl port-forward", None, forwards)
    row("shell files with KUBECTL=( preamble", 30, kubectl_preamble)

    py_forward = 0
    py_kubectl = 0
    for p in tracked("scripts/*.py"):
        text = p.read_text(encoding="utf-8", errors="replace")
        if "port-forward" in text:
            py_forward += 1
        # any indent, and the several spellings the copies actually use
        if re.search(r"^\s*def _?kubectl\w*\(", text, re.M):
            py_kubectl += 1
    row("python files using kubectl port-forward", None, py_forward)
    row("python files defining a kubectl wrapper", 8, py_kubectl,
        "any indent; _kubectl/kubectl/_kubectl_json spellings")


def check_src_orphans() -> None:
    print("\n[8] src/ — the seed says zero unimported modules")
    mods = tracked("src/taxi_mlops/**/*.py")
    all_text = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in tracked("*")
        if p.suffix in (".py", ".sh", ".md", ".yaml", ".yml")
    )
    orphans = []
    for p in mods:
        if p.name in ("__init__.py", "__main__.py"):
            continue
        stem = p.stem
        # a module is reached if its name appears anywhere outside its own file
        own = p.read_text(encoding="utf-8", errors="replace")
        outside = all_text.count(stem) - own.count(stem)
        if outside <= 0:
            orphans.append(p.relative_to(REPO).as_posix())
    row("src/ modules unreferenced outside themselves", 0, len(orphans),
        ", ".join(orphans) if orphans else "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()

    print("=" * 78)
    head = sh("git", "rev-parse", "--short", "HEAD").strip()
    print("cleanup audit SEED — verification by measurement")
    print(f"seed: {SEED.relative_to(REPO)}   head: {head}")
    print("ADVISORY. This reader deletes nothing and charters nothing.")
    print("=" * 78)

    check_size_map()
    check_dead_code()
    check_small_findings()
    check_tests()
    check_duplication()
    check_src_orphans()

    confirmed = sum(1 for r in RESULTS if r["verdict"] == "CONFIRMED")
    differs = sum(1 for r in RESULTS if r["verdict"] == "DIFFERS")
    measured = sum(1 for r in RESULTS if r["verdict"] == "MEASURED")
    print("\n" + "=" * 78)
    print(f"{confirmed} CONFIRMED · {differs} DIFFERS · {measured} newly MEASURED")
    print("A DIFFERS row is not automatically the seed being wrong — several are a")
    print("counting basis (tracked files vs the viewing copy). The point is that the")
    print("charter is now argued from numbers somebody re-derived by running.")
    print("=" * 78)

    if args.json:
        out = args.json if args.json.is_absolute() else (REPO / args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"results": RESULTS}, indent=2) + "\n")
        print(f"wrote {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
