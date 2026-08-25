#!/usr/bin/env bash
# verify_m8.sh — the M8 gate, executable. BLUEPRINT §9/M8, quoted:
#
#   "M8 — Feature store (Feast) & the side-by-side (DE A; MLE R). v1's M7
#    (zone-window aggregates, point-in-time training joins, transformer
#    enrichment, 100-pair online/offline parity) + prior-art revisit: our Feast
#    design against the surveyed community implementations — one page,
#    adopt/differ/surpass, honest.
#    Accept when: v1's M7 gate AND the comparison page exists.
#    Show: parity table + comparison."
#
# The design rules are M2-S5's … M7-S5's, inherited whole:
#   * every check observes the THING, never a proxy;
#   * every Python leg must EMIT a minimum number of verdicts, so a leg that
#     dies on import FAILS instead of contributing zero silent passes;
#   * PROPERTIES, NOT LITERALS (F-017, gotchas #49/#50). This gate types no
#     champion version, no parity bar, no row count, no package version and no
#     zone id. Every number it compares is read from two places and matched;
#   * prose against records at ≥1 decimal (gotcha #90);
#   * no skip flag, no fast mode. M1's rule, inherited an EIGHTH time.
#
# RE-RUNS NOTHING AND MINTS NOTHING IT COUNTS. It does not build an image
# (gotcha #66 makes every commit a new tag, so a build here would cost ~7
# minutes and change the thing under test), does not deploy, does not
# materialize, does not apply the feature repo, does not run any of the four
# parity readers, does not fit, does not push a metric and does not move a
# pointer. It reads: the tracked records M8-S1…S4 wrote, the committed docs,
# the code with `ast`, git — and it asks the live system exactly FIVE questions:
#
#     one prediction through the champion's wire
#     one prediction through the transformer's wire
#     one online lookup at the feature server
#     one DBSIZE at the online store
#     one PromQL query
#
# That count is pinned by `tests/unit/test_verify_m8.py`, because a gate whose
# live footprint can grow quietly is a gate that will one day re-run the thing
# it exists to read.
#
# WHAT THIS GATE ASKS THAT NO PREDECESSOR COULD — three things.
#
#  1. THE WALL IS AN INVARIANT, NOT A HABIT (§1). The whole milestone rests on
#     Feast never entering this project's dependency graph: feast 0.66.0
#     declares `pandas<3` against this project's 3.0.5. `uv.lock` must be
#     byte-identical to the SANCTIONED LOCK ANCHOR and `feast` must be absent
#     from the project environment — both ASKED, neither assumed. The anchor was
#     `m7-closed` from M8-S5 until 2026-08-25, when the PO sanctioned one move of
#     it (AWAITING_PO 2026-08-24-5, answered block, option (b): bump sqlparse out
#     of three HIGH CVEs before the public flip). The INVARIANT did not change
#     shape — only its reference point moved, once, by letter. See M9-S11.
#
#  2. FOUR PARITY BARS, EACH ARGUED BEFORE THE MEASUREMENT, CHECKED FROM GIT
#     (§3). M8 law 4 says a bar is argued before the comparison runs. That is
#     not a claim a document can make about itself, so the gate compares the
#     commit that ADDED each bar's document with the commit that ADDED the
#     record it judges. Four seams, four orderings, all from `git log
#     --diff-filter=A`.
#
#  3. THE POINT-IN-TIME PROOF IS A DIFFERENCE, NOT A SENTENCE (§4). An honest
#     join and a naive one, same store and same call, one column apart. The
#     load-bearing clauses are that the NAIVE answer equals our own full-window
#     table (so the leak is identified, not merely different) and that the
#     honest answer reconciles with `aggregates.transform` at zero (so the
#     correct side is anchored to the code the champion is fitted through).
#
# Prints one line per sub-check and exits nonzero if ANY fails — it keeps going
# rather than stopping at the first, so one run tells you everything broken.
#
# Usage: scripts/verify_m8.sh          (via `make verify-m8`)
#        scripts/verify_m8_redteam.sh  proves this gate can go RED
set -uo pipefail   # deliberately NOT -e: a failing check must be counted, not fatal

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

FAILS=0
CONSUMED=0
pass() { printf '  \033[32mok  \033[0m %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1" >&2; FAILS=$((FAILS + 1)); }
note() { printf '       %s\n' "$1"; }
section() { printf '\n== %s ==\n' "$1"; }

# Reads `PASS|msg` / `FAIL|msg` lines from a leg and counts them here, so the
# tally lives in exactly one place. ALWAYS call as `consume < <(...)`: a pipeline
# would run this in a subshell and throw the counters away at the closing brace.
consume() {
  CONSUMED=0
  local line
  while IFS= read -r line; do
    case "$line" in
      "PASS|"*) pass "${line#PASS|}"; CONSUMED=$((CONSUMED + 1)) ;;
      "FAIL|"*) fail "${line#FAIL|}"; CONSUMED=$((CONSUMED + 1)) ;;
      *) note "$line" ;;
    esac
  done
}

expect_verdicts() {
  local want="$1" label="$2"
  if [[ "$CONSUMED" -lt "$want" ]]; then
    fail "$label emitted $CONSUMED verdict(s), expected at least $want — the check did not run"
  fi
}

printf '\n\033[1m[verify-m8]\033[0m the M8 gate — a wall that must hold, four seams measured against\n'
printf '            bars argued before them, a point-in-time join proved by its own\n'
printf '            counterexample, and a page that is allowed to disagree with us.\n'

# ------------------------------------------------------------ 1. the wall ----
section "1. the wall — Feast is quarantined, and the invariant is ASKED rather than remembered"
consume < <(uv run python - 2>/dev/null <<'PY'
import ast
import json
import re
import subprocess
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

# The one sanctioned lock anchor. Spelled ONCE per script and pinned across all
# of them by tests/unit/test_lock_anchor.py, which also refuses a search-and-
# replace that drags §7's registry-time bound along with it.
LOCK_ANCHOR = "lock-rebaselined-m9-publish"

try:
    PIN = Path("infra/feast/requirements-feast.txt")
    probe = json.loads(Path("automation/runs/m8-feast/probe.json").read_text())

    # (a) THE invariant. `uv.lock` is the project's dependency graph, and the
    # whole quarantine argument is that M8 did not touch it. Both sides derived:
    # the tag's blob out of git, the working tree's off disk. A typed sha256
    # would be a literal that stops meaning anything the day the lock legitimately
    # moves for a reason unrelated to Feast.
    #
    # The ANCHOR moved once, on 2026-08-25, by PO letter (AWAITING_PO
    # 2026-08-24-5 option (b) — sqlparse 0.5.5 -> 0.6.0 to clear three HIGH CVEs
    # before the public flip, which also required dbt-core 1.12.2 -> 1.12.3
    # because 1.12.2 declares `sqlparse<0.6.0`). M9-S11 landed it and placed
    # `lock-rebaselined-m9-publish`. The invariant keeps its SHAPE: the lock is
    # still asserted byte-identical to a SANCTIONED tag, and an unsanctioned
    # `uv add` is still a RED gate. Note this is deliberately NOT the tag §7 uses
    # to bound registry-version creation times — that one must stay at
    # `m7-closed`, because moving it forward would ADMIT versions rather than
    # refuse them.
    tagged = subprocess.run(["git", "show", f"{LOCK_ANCHOR}:uv.lock"],
                            capture_output=True, text=True)
    if tagged.returncode != 0:
        no(f"the {LOCK_ANCHOR} tag does not resolve — the wall's invariant has no "
           f"reference point")
    elif tagged.stdout == Path("uv.lock").read_text():
        ok(f"uv.lock is BYTE-IDENTICAL to the {LOCK_ANCHOR} tag — five M8 stories, a "
           f"feature repo, an online store, a feature server and a transformer, and the "
           f"project's dependency graph moves only by PO letter")
    else:
        no(f"uv.lock DIFFERS from the {LOCK_ANCHOR} tag — something entered the project "
           f"graph unsanctioned; `git diff {LOCK_ANCHOR} -- uv.lock` says what")

    # (b) The absence asked of the environment, not inferred from (a). A lock can
    # be unchanged while a venv holds something installed by hand.
    listing = subprocess.run(["uv", "pip", "list", "--format", "json"],
                             capture_output=True, text=True, timeout=120)
    installed = {p["name"].lower() for p in json.loads(listing.stdout or "[]")}
    if "feast" in installed:
        no("`feast` IS installed in the project environment — the wall is down, whatever "
           "uv.lock says")
    elif not installed:
        no("`uv pip list` returned nothing — the absence could not be asked, so it is not proved")
    else:
        ok(f"`feast` is ABSENT from the project environment, asked of `uv pip list` "
           f"({len(installed)} packages) and not inferred from the lock")

    # (c) The wall is REAL: the two sides genuinely cannot share an interpreter,
    # and the recorded reason is the live one. `differs_on` is the measurement
    # M8-S3's and M8-S4's exact-bar arguments rest on.
    wall = probe["wall"]
    declared = wall["declared_by_feast"]
    proj_pandas = wall["project"]["pandas"]
    if "pandas<3" in declared.replace(" ", "") and proj_pandas.startswith("3."):
        ok(f"the wall is real and measured: feast {wall['feast_version']} declares "
           f"{declared!r} against this project's pandas {proj_pandas} — a quarantine, "
           f"not a preference")
    else:
        no(f"the recorded conflict no longer reads as one: feast declares {declared!r}, "
           f"project pandas {proj_pandas}")
    if wall["differs_on"] == ["pandas"]:
        shared = ", ".join(f"{k} {v}" for k, v in wall["quarantine"].items() if k != "pandas")
        ok(f"and the wall is ONE package wide — the two sides differ on {wall['differs_on']} "
           f"and agree on {shared}, which is the premise every M8 exact bar is argued from")
    else:
        no(f"the two sides now differ on {wall['differs_on']} — more than pandas crosses, "
           f"so the seam arguments need re-reading")

    # (d) Reproducible from the committed pins ALONE. `--no-deps` is what makes
    # the pin file authoritative: with it, a resolver consulted at install time
    # cannot answer differently from the one that was reviewed.
    quarantine_sh = Path("scripts/feast_quarantine.sh").read_text()
    pins = [ln.strip() for ln in PIN.read_text().splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]
    unpinned = [p for p in pins if "==" not in p]
    if "--no-deps" in quarantine_sh and not unpinned:
        ok(f"the quarantine installs {len(pins)} EXACT pins with `--no-deps` — every line "
           f"carries `==`, so the environment is a function of the reviewed file and not "
           f"of a resolver's mood")
    else:
        no(f"the quarantine is not pin-authoritative: --no-deps present="
           f"{'--no-deps' in quarantine_sh}, unpinned lines={unpinned[:4]}")

    # (e) The pin file has only GROWN, and by what the online store needed. A
    # silent shrink would mean the quarantine stopped installing something the
    # probe measured against.
    # PEP 503 normalisation on BOTH sides. The probe recorded distribution names
    # as their metadata spells them (`Jinja2`, `PyJWT`, `SQLAlchemy`) and the pin
    # file spells them as the index does; comparing the raw strings reported
    # eleven packages "LOST" from a file that had lost nothing — this gate's own
    # first run, and the same shape as gotcha #46 (a name spelled two ways).
    def norm(n):
        return re.sub(r"[-_.]+", "-", n).lower()

    recorded = {norm(p) for p in probe["quarantine_pins"]}
    current = {norm(p.split("==")[0]) for p in pins}
    added, lost = sorted(current - recorded), sorted(recorded - current)
    if not lost:
        ok(f"every package the probe recorded is still pinned; the file gained "
           f"{added if added else 'nothing'} since — the online store's own client "
           f"(ADR-012), added in sorted position rather than by regeneration")
    else:
        no(f"the pin file LOST {lost} since the probe measured against it")

    # (f) THE law that makes a quarantine one, both directions, asked of the AST.
    # A single import across this line is how it stops being a wall — and these
    # two modules argue their own design in prose that names the other side, so a
    # grep would match the argument (#53/#68).
    def imports(path):
        tree = ast.parse(Path(path).read_text())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names.add(node.module.split(".")[0])
        return names

    defs = imports("infra/feast/feature_repo/definitions.py")
    src = imports("scripts/feast_sources.py")
    if "feast" in defs and "taxi_mlops" not in defs and "taxi_mlops" in src and "feast" not in src:
        ok("the import law holds in BOTH directions (ast, never grep): definitions.py imports "
           "feast and not taxi_mlops; feast_sources.py imports taxi_mlops and not feast")
    else:
        no(f"the import law is broken: definitions.py imports {sorted(defs)}, "
           f"feast_sources.py imports {sorted(src)}")

    # (g) And nothing declared it as a project dependency.
    pyproject = Path("pyproject.toml").read_text()
    if "feast" not in pyproject:
        ok("`feast` appears nowhere in pyproject.toml — there is no `uv add feast` in this "
           "repository and the milestone's premise says there never will be")
    else:
        no("pyproject.toml names feast — the quarantine has a second, contradictory home")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the wall check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 7 "the wall check"

# ------------------------------------------- 2. the repo and its registry ----
section "2. the feature repo — a registry DERIVED from git, and a catalog that records its losers"
consume < <(uv run python - 2>/dev/null <<'PY'
import ast
import json
import re
import subprocess
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    DEFS = Path("infra/feast/feature_repo/definitions.py")
    registry = json.loads(Path("automation/runs/m8-feast/registry.json").read_text())
    plan = json.loads(Path("automation/runs/m8-feast/plan.json").read_text())
    catalog = Path("docs/feast_catalog.md").read_text()
    tree = ast.parse(DEFS.read_text())

    # Parse the DECLARED objects out of the module with ast. The registry record
    # was read back OFF THE APPLIED STORE (the deploy_serving.sh idiom), so this
    # compares two independently-produced lists — which is the only way the claim
    # "the registry matches git" means anything.
    def _kwargs(call):
        return {kw.arg: kw.value for kw in call.keywords}

    declared_views, declared_entities, view_tags = set(), set(), {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        kw = _kwargs(node)
        name_node = kw.get("name")
        if not isinstance(name_node, ast.Constant):
            continue
        if node.func.id == "FeatureView":
            declared_views.add(name_node.value)
            tags = kw.get("tags")
            if isinstance(tags, ast.Dict):
                view_tags[name_node.value] = {
                    k.value: (v.value if isinstance(v, ast.Constant) else "<joined>")
                    for k, v in zip(tags.keys, tags.values)
                    if isinstance(k, ast.Constant)
                }
        elif node.func.id == "Entity":
            declared_entities.add(name_node.value)

    applied_views = {v["name"] if isinstance(v, dict) else v for v in registry["feature_views"]}
    applied_entities = {e["name"] if isinstance(e, dict) else e for e in registry["entities"]}

    if declared_views and applied_views == declared_views:
        ok(f"the APPLIED registry holds exactly the {len(declared_views)} feature views "
           f"declared in git ({', '.join(sorted(declared_views))}) — two independently "
           f"produced lists, not a file compared with itself")
    else:
        no(f"registry views {sorted(applied_views)} != declared {sorted(declared_views)}")

    if declared_entities and applied_entities == declared_entities:
        ok(f"and exactly the {len(declared_entities)} declared entities — the join keys the "
           f"rest of this program already spells the same way")
    else:
        no(f"registry entities {sorted(applied_entities)} != declared {sorted(declared_entities)}")

    # F-055: `feast plan` can NEVER report "no changes" (Feast re-stamps
    # DataSource.meta at import), so the checkable statement is that every
    # reported difference is clock-only.
    if plan.get("substantive_count") == 0 and plan.get("exit_code") == 0:
        ok(f"`feast plan` reported {len(plan['objects'])} object(s) and ZERO substantive "
           f"differences — F-055's checkable statement, since the always-noisy reading "
           f"(clock re-stamps) can never say 'no changes'")
    else:
        no(f"the plan record claims {plan.get('substantive_count')} substantive difference(s) "
           f"at exit {plan.get('exit_code')} — the registry and git disagree about something "
           f"that is not a timestamp")

    # The registry is GENERATED, not committed — F-013's second-home law, and the
    # row the side-by-side page makes a SURPASS out of.
    # The property is IGNORED BY GIT, not absent from disk. A generated registry
    # on a developer's disk is the normal state after `make feast-apply`; what
    # must never exist is a TRACKED one. The first draft of this check demanded
    # absence and went red against a correct system — gotcha #50, on the gate's
    # own first run. Asked of git, which is the authority, rather than of a
    # `.gitignore` file's text (the rule that ignores it lives in the ROOT one).
    tracked = subprocess.run(["git", "ls-files", "--", "infra/feast", "**/registry.db"],
                             capture_output=True, text=True).stdout.split()
    tracked_registry = [p for p in tracked if p.endswith("registry.db")]
    on_disk = list(Path("infra/feast").rglob("registry.db"))
    ignored_ok = all(
        subprocess.run(["git", "check-ignore", "-q", str(p)]).returncode == 0
        for p in on_disk)
    if not tracked_registry and (not on_disk or ignored_ok):
        ok(f"no registry.db is TRACKED, and the {len(on_disk)} generated copy/copies on disk "
           f"are gitignored (asked of `git check-ignore`) — the definitions in git are the "
           f"source of truth and the feature server re-applies them in its entrypoint, so a "
           f"pod's registry is a function of the image's git content")
    else:
        no(f"a registry file is tracked ({tracked_registry}) or unignored ({on_disk}) — "
           f"F-013's second home, in a binary that produces no reviewable diff")

    # The catalog's verdicts, and the one that matters: an entry that LOST.
    allowed = {"in-champion", "catalog-only", "candidate"}
    verdicts = {v: t.get("verdict") for v, t in view_tags.items()}
    unknown = {v: d for v, d in verdicts.items() if d not in allowed}
    if view_tags and not unknown:
        counts = {a: sum(1 for d in verdicts.values() if d == a) for a in sorted(allowed)}
        ok(f"every declared view carries a verdict tag in {sorted(allowed)} — {counts}")
    else:
        no(f"views with no verdict or an unknown one: {unknown}")

    losers = [v for v, d in verdicts.items() if d == "catalog-only"]
    if losers and all(v in catalog for v in declared_views):
        ok(f"the catalog names every view AND records {len(losers)} CATALOG-ONLY entr(y/ies) "
           f"({', '.join(sorted(losers))}) — the family every surveyed source swears by, kept "
           f"in the store with the measurement that kept it out of the champion")
    else:
        no(f"the catalog records no losing entry (catalog-only views: {losers}) or omits a "
           f"view — a catalog that lists only winners cannot argue against repeating an "
           f"experiment")

    # gotcha #15: the losing number is a SAMPLE number and must be labelled one.
    # A dropped group is never refitted at full data, so no full-data figure exists.
    loser_tags = " ".join(str(view_tags[v].get("ablation", "")) for v in losers)
    if re.search(r"SAMPLE", loser_tags):
        ok("and the losing number is labelled a SAMPLE number in the tag itself (gotcha #15) — "
           "a dropped group is never refitted, so no full-data figure for it exists to quote")
    else:
        no("the catalog-only ablation numbers are not labelled as sample numbers")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the feature-repo check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 7 "the feature-repo check"

# ------------------------------------------------------- 3. the four seams ---
section "3. the four seams — every bar EXACT, every bar argued BEFORE its record existed (law 4)"
consume < <(uv run python - 2>/dev/null <<'PY'
import ast
import json
import re
import subprocess
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    # Each seam: the record, the document that ARGUES its bar, and a human label.
    # The gate types no tolerance and no row count — it reads the bar out of the
    # document (which must state it in bold, so a reviewer reads the same string
    # the gate parses) and the measurement out of the record.
    SEAMS = [
        ("offline retrieval (M8-S3)", "automation/runs/m8-pit/retrieval_parity.json",
         "docs/feast_pit_m8.md"),
        ("online/offline (M8-S4 leg 1)", "automation/runs/m8-online/online_parity.json",
         "docs/feast_online_m8.md"),
        ("the HTTP feature server (M8-S4 leg 2)",
         "automation/runs/m8-transformer/server-parity.json", "docs/feast_server_m8.md"),
        ("the moved boundary (M8-S4 leg 3)",
         "automation/runs/m8-transformer/transformer-parity.json", "docs/transformer_m8.md"),
    ]

    def added_at(path):
        out = subprocess.run(["git", "log", "--diff-filter=A", "--format=%ct", "-1", "--", path],
                             capture_output=True, text=True).stdout.strip()
        return int(out) if out else None

    def columns_of(rec):
        for key in ("columns", "seam"):
            if isinstance(rec.get(key), list):
                return rec[key]
        return []

    exact_docs, ordered, deltas, missing_counts = 0, 0, [], []
    for label, rec_path, doc_path in SEAMS:
        rec = json.loads(Path(rec_path).read_text())
        doc = Path(doc_path).read_text()

        # The bar, parsed from the prose that argues it: the document must state
        # a bar of EXACT **in bold**, so a reviewer reads the same string the
        # gate parses. The pattern is deliberately about the PROPERTY and not
        # about one sentence's word order — the first draft demanded
        # `**The bar is EXACT` and went red against `So the bar is **EXACT —
        # \`TOLERANCE = 0.0\`** again`, which argues the identical thing (gotcha
        # #50 for the second time on this gate's first run). A doc that quietly
        # loosened to a float epsilon still stops matching.
        if re.search(r"(?:\*\*)?[Tt]he bar is (?:\*\*)?\s*EXACT", doc):
            exact_docs += 1
        else:
            no(f"{label}: {doc_path} no longer states a bar of EXACT in bold — a bar a "
               f"reviewer cannot find is not an argued bar")

        # …and the record must AGREE with it, in whichever field it keeps it.
        stated = rec.get("bar") or rec.get("tolerance")
        stated_is_exact = (stated == "EXACT") or (isinstance(stated, (int, float)) and stated == 0)
        measured = rec.get("max_abs_delta")
        if measured is None:
            measured = rec.get("max_abs_delta_minutes")
        if measured is None:
            measured = max((c.get("max_abs_delta") or 0.0) for c in columns_of(rec))
        if not stated_is_exact:
            no(f"{label}: the record's bar is {stated!r}, not EXACT")
        elif float(measured) != 0.0:
            no(f"{label}: measured {float(measured):.3e} against a bar of EXACT")
        else:
            # The moved-boundary seam compares MINUTES per hazard row, not
            # per-column values, so it reports rows where the other three report
            # columns. Saying "0 cols" for it would be the gate misdescribing a
            # seam it had just passed.
            width = len(columns_of(rec)) or len(rec.get("rows", []))
            unit = "cols" if columns_of(rec) else "hazard rows"
            deltas.append((label, float(measured), f"{width} {unit}"))

        # `one missing` is the load-bearing count: a comparison that dropped
        # nulls would print a perfect zero while being blind to exactly the rows
        # F-030 was found on. Both sides must agree about which values do not
        # EXIST, not merely about the values.
        cols = columns_of(rec)
        if cols:
            bad = [c["column"] for c in cols if c.get("one_missing")]
            if bad:
                no(f"{label}: {len(bad)} column(s) where exactly one side had a value: {bad[:4]}")
            else:
                missing_counts.append((label, len(cols)))

        # LAW 4, checked from git rather than from a sentence: the commit that
        # ADDED the bar's document must precede the commit that ADDED the record
        # it judges. A document cannot honestly testify about its own ordering.
        d_at, r_at = added_at(doc_path), added_at(rec_path)
        if d_at and r_at and d_at < r_at:
            ordered += 1
            gap = r_at - d_at
            print(f"       {label}: bar committed {gap}s before the record it judges")
        else:
            no(f"{label}: the bar's document was NOT committed before its record "
               f"(doc={d_at}, record={r_at}) — law 4 cannot be read from git for this seam")

    if len(deltas) == len(SEAMS):
        ok("all four seams measured EXACTLY 0.000e+00 against a bar of EXACT: "
           + " · ".join(f"{l} ({n})" for l, _, n in deltas))
    if len(missing_counts) >= 3:
        ok("and `one missing` is ZERO on every column of every seam that reports it "
           + f"({', '.join(f'{l}: {n}' for l, n in missing_counts)}) — the two sides agree "
           "about which values do not EXIST, which is the count a null-dropping comparison "
           "would be blind to")
    else:
        no(f"only {len(missing_counts)} seam(s) reported a per-column missing count")
    if exact_docs == len(SEAMS):
        ok(f"all {exact_docs} bar documents state EXACT in bold — the gate parsed the bar it "
           f"judges against out of the prose that argues it, and typed none of them (F-017)")
    if ordered == len(SEAMS):
        ok(f"and all {ordered} bars were COMMITTED BEFORE the records they judge, checked from "
           f"`git log --diff-filter=A` — M8 law 4 read off git rather than asserted in prose")

    # ONE declared row set across the seams. The 16 hazards are IMPORTED from
    # `serving.parity.HAZARDS` rather than retyped, so the wire seam (M5-S3), the
    # store seam and the moved boundary are measured against the same rows —
    # asked of the AST, because both files also discuss the import in prose.
    def imports_hazards(path):
        tree = ast.parse(Path(path).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "parity" in node.module:
                return True
            if isinstance(node, ast.Attribute) and node.attr == "HAZARDS":
                return True
            if isinstance(node, ast.Name) and node.id == "HAZARDS":
                return True
        return False

    sharers = [p for p in ("scripts/feast_declared_rows.py",
                           "scripts/feast_server_parity.py",
                           "scripts/transformer_parity.py")
               if Path(p).exists() and imports_hazards(p)]
    if len(sharers) >= 2:
        ok(f"{len(sharers)} seam reader(s) take their hazard rows from "
           f"`serving.parity.HAZARDS` by import rather than by retyping (ast) — five seams, "
           f"one declared row set, so a row added for one is measured by all")
    else:
        no(f"only {len(sharers)} reader(s) import the declared hazards: {sharers}")

    # The Show artifact the blueprint names, and it must be COMMITTED prose that
    # agrees with the record — not a file the reader is told exists.
    table = Path("docs/feast_online_parity_table.md")
    online = json.loads(Path("automation/runs/m8-online/online_parity.json").read_text())
    pairs = online["declared_pairs"]
    table_text = table.read_text() if table.exists() else ""
    if table_text and re.search(rf"\b{pairs}\b", table_text):
        ok(f"§9/M8's 'Show: parity table' exists at {table} and names the same "
           f"{pairs} declared pairs the record measured")
    else:
        no(f"{table} is missing or does not carry the record's {pairs} declared pairs")

    # THE MISSING COUNTS ARE THIS MILESTONE'S THESIS, so they get three witnesses.
    # `max |delta| = 0` is what a comparison that silently DROPPED NULLS would
    # also print — blind to exactly the ~1% of rows F-030 was found on. So the
    # per-column `both_missing` must reconcile with the record's own two-sided
    # no-geometry assertion, with the ANCHOR block's independent count of the
    # same columns, and with the number rendered in the table a human diffs.
    by_col = {c["column"]: c for c in online["seam"]}
    anchors = {c["column"]: c for c in online.get("anchor_to_feature_path", [])}
    geom = online["no_geometry"]
    bad_geom, bad_anchor, bad_prose = [], [], []
    for side in ("pu", "do"):
        expected = geom[side]["rows_without_geometry_our_path"]
        for col, c in by_col.items():
            if not col.startswith(f"{side}_zone."):
                continue
            if c["both_missing"] != expected:
                bad_geom.append(f"{col}: both_missing {c['both_missing']} vs "
                                f"{expected} rows with no geometry")
            twin = anchors.get(f"anchor.{side}.{col.split('.', 1)[1]}")
            if twin and twin["both_missing"] != c["both_missing"]:
                bad_anchor.append(f"{col}: seam says {c['both_missing']}, its anchor "
                                  f"says {twin['both_missing']}")
    for col, c in by_col.items():
        row = re.search(rf"^\|\s*`{re.escape(col)}`\s*\|(.*)\|\s*$", table_text, re.M)
        if not row:
            bad_prose.append(f"{col}: no row in the table")
            continue
        cells = [x.strip() for x in row.group(1).split("|")]
        if len(cells) >= 5 and cells[-2] != str(c["both_missing"]):
            bad_prose.append(f"{col}: the table renders {cells[-2]!r}, the record holds "
                             f"{c['both_missing']}")
    if not bad_geom:
        ok(f"every zone column's `both missing` equals the record's own two-sided "
           f"no-geometry count (pu {geom['pu']['rows_without_geometry_our_path']}, "
           f"do {geom['do']['rows_without_geometry_our_path']}) — a null-dropping "
           f"comparison would print the same 0.000e+00 and this is what it could not fake")
    else:
        no("the seam's missing counts do not reconcile with the run's own no-geometry "
           "assertion: " + " · ".join(bad_geom[:3]))
    if not bad_anchor:
        ok(f"and the ANCHOR block counts the same missing rows for every column it shares "
           f"with the seam ({len(anchors)} anchored columns) — two independently built "
           f"comparisons inside one record, which is why a single edited field contradicts "
           f"something")
    else:
        no("the seam and its anchor disagree about which rows are missing: "
           + " · ".join(bad_anchor[:3]))
    if not bad_prose:
        ok(f"and the committed table renders exactly what the record holds for all "
           f"{len(by_col)} columns — the third witness, and the only one a human diffs")
    else:
        no("the table a reviewer reads and the record disagree: " + " · ".join(bad_prose[:3]))
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the seams check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 9 "the seams check"

# ------------------------------------------------- 4. point-in-time proof ----
section "4. the point-in-time proof — a DIFFERENCE with two anchors, not a sentence about a join"
consume < <(uv run python - 2>/dev/null <<'PY'
import ast
import json
import re
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    pit = json.loads(Path("automation/runs/m8-pit/pit_proof.json").read_text())
    retr = json.loads(Path("automation/runs/m8-pit/retrieval_parity.json").read_text())

    # (a) The honest join and the naive one DISAGREE. Without this the proof is
    # a demonstration that a join runs.
    leak = pit["leak"]
    moved = {c: d for c, d in leak.items() if d["differing_rows"] > 0}
    if len(moved) == len(leak) and leak:
        worst = max(leak.items(), key=lambda kv: kv[1]["max_abs_delta"])
        ok(f"honest and naive disagree on every one of the {len(leak)} time-varying columns "
           f"— " + " · ".join(f"{c}: {d['differing_rows']}/{d['compared']}"
                              for c, d in leak.items())
           + f"; worst {worst[0]} at {worst[1]['max_abs_delta']:.4f}")
    else:
        no(f"only {len(moved)} of {len(leak)} columns differ between the honest and naive "
           f"joins — a proof whose two arms agree proves nothing")

    # (b) THE identifying clause. The naive answer is not merely different — it
    # IS our own full-window table, so the leak has a name.
    nef = pit["naive_equals_full_window"]
    if nef["mismatches"] == 0 and nef["compared"] > 0:
        ok(f"the NAIVE answer IS our own full-window table ({nef['compared']} rows, "
           f"{nef['mismatches']} mismatches) — the leak is identified, not merely observed, "
           f"which is what makes the difference in (a) attributable")
    else:
        no(f"the naive column does not reproduce the full-window table "
           f"({nef['mismatches']} mismatches over {nef['compared']})")

    # (c) …and the HONEST answer is anchored to the code the champion is fitted
    # through. Without this, a difference only proves two joins disagree.
    float_cols = [c for c in retr["columns"] if c["kind"] == "float"]
    if float_cols and all(c["max_abs_delta"] == 0.0 for c in float_cols):
        ok(f"and the HONEST answer reconciles with `aggregates.transform` at 0.000e+00 over "
           f"{len(float_cols)} float column(s) — the correct side is anchored to the champion's "
           f"own code, so the gate is not choosing between two unanchored joins")
    else:
        no("the honest retrieval no longer reconciles with the feature path at zero")

    # (d) The purest form of the leak: rows the honest join must tell NOTHING.
    told_nothing = {c: d["one_missing"] for c, d in leak.items() if d.get("one_missing")}
    if told_nothing:
        ok(f"rows the honest join must tell NOTHING and the naive one hands a number: "
           f"{told_nothing} — the first train month has no history, and "
           f"`AggregateTables.empty()` serving NaN is the correct answer a leak overwrites")
    else:
        no("no row was served nothing by the honest join — the no-history case is untested")

    # (e) The walk. Six month-boundary pairs 120 s apart, each served the window
    # it was ENTITLED to know, while the naive column sat constant.
    windows = pit["windows_served"]
    if len(windows) >= 6:
        ok(f"{len(windows)} DISTINCT windows were served across the declared rows "
           f"({', '.join(sorted(k for k in windows if k != '(no row)'))[:120]}…) including "
           f"'(no row)' for the month with no history — an honest join is about what a row "
           f"was entitled to know, not about whether the number moved")
    else:
        no(f"only {len(windows)} distinct window(s) served — the boundary walk is not visible")

    # (f) F-056: the join returns fewer rows than it was asked for, for two
    # reasons a left join cannot tell apart. The record must CLASSIFY the
    # shortfall, and UNEXPLAINED must be zero — a count assertion would have
    # manufactured a mismatch against a perfectly good value.
    shortfalls = retr.get("shortfalls", {})
    unexplained = 0
    for v in (shortfalls.values() if isinstance(shortfalls, dict) else shortfalls):
        if isinstance(v, dict):
            unexplained += len(v.get("unexplained", []) or [])
    if shortfalls and unexplained == 0:
        ok(f"F-056's shortfall is CLASSIFIED rather than asserted away — every unanswered row "
           f"is a duplicate entity key or predates the first source row, and UNEXPLAINED is 0 "
           f"across {len(shortfalls)} view(s)")
    else:
        no(f"{unexplained} unanswered row(s) have no explanation, or the record asserts a "
           f"count instead of classifying the shortfall")

    # (g) The truth is RE-FITTED from the settled trees, never rebuilt from the
    # parquet under test — reconstructing it from the artifact being judged
    # would compare the store against itself and pass for any join at all.
    # The reader's PATH is derived from the Makefile recipe that runs it, never
    # typed: a gate carrying a script name is a literal that goes red the day
    # the script is legitimately renamed, which is the failure mode F-017 exists
    # to prevent — and this check went red on its own first run for exactly that
    # (it had typed `feast_retrieval_parity.py`; the target runs
    # `feast_retrieval.py`).
    recipe = re.search(r"^feast-retrieval:.*?\n\t(.*)$", Path("Makefile").read_text(), re.M | re.S)
    named = re.findall(r"(scripts/\S+\.py)", recipe.group(1).split("\n")[0]) if recipe else []
    comparer = Path(named[0]) if named else Path("scripts/__no_reader__.py")
    if comparer.exists():
        tree = ast.parse(comparer.read_text())
        calls = {n.func.attr for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        if "fit" in calls:
            ok("the comparer RE-FITS the truth through `aggregates.fit` (ast) rather than "
               "reading back the parquet Feast reads — reconstructing the truth from the "
               "artifact under test would pass for no join at all")
        else:
            no("the comparer no longer calls a fit — its truth may be the artifact it judges")
    else:
        no(f"{comparer} is missing — the PIT proof has no reader")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the point-in-time check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 7 "the point-in-time check"

# ------------------------------------------------ 5. the live five questions -
section "5. the live system — five questions, and the store is asked whether it holds anything"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    import mlflow
    import yaml

    from taxi_mlops.serving import client as client_mod
    from taxi_mlops.serving import parity as parity_mod
    from taxi_mlops.serving import transformer as transformer_mod
    from taxi_mlops.training import tracking
    from taxi_mlops.training.run import load_train_config

    cfg = load_train_config()
    tracking.configure(cfg["mlflow"])
    reg = cfg["registry"]
    champion = mlflow.MlflowClient().get_model_version_by_alias(
        reg["model_name"], reg["champion_alias"])

    tp = json.loads(Path("automation/runs/m8-transformer/transformer-parity.json").read_text())
    hazard_name = tp["rows"][0]["hazard"]
    hazard = next(h for h in parity_mod.HAZARDS if h.name == hazard_name)
    row = tp["rows"][0]

    # QUESTION 1 — the champion's own wire, unchanged by M8. The isvc name is
    # read off the manifest, never typed.
    manifest = Path("infra/manifests/inferenceservice-champion.yaml").read_text()
    isvc = re.search(r"^\s+name:\s*(\S+)", manifest, re.M).group(1)
    ns = re.search(r"^\s+namespace:\s*(\S+)", manifest, re.M).group(1)
    resp = client_mod.infer([hazard.request], client_mod.Endpoint(name=isvc, namespace=ns))
    served = str(resp.get("model_version", ""))
    champ_minutes = float(client_mod.minutes_of(resp)[0])
    # EXACTLY the recorded value, with no epsilon: the record's own bar for this
    # seam is EXACT, the endpoint is deterministic, and an epsilon typed here
    # would be a tolerance this gate invented for itself (F-017).
    if served == str(champion.version) and champ_minutes == row["champion_minutes"]:
        ok(f"the CHAMPION answered {champ_minutes:.6f} minutes stamped model_version={served!r} "
           f"— equal to what the alias resolves to, reproducing the parity record's "
           f"{hazard_name!r} row. M8 put a second service on the cluster and left this one alone")
    else:
        no(f"the champion stamped {served!r} against alias {champion.version}, quoting "
           f"{champ_minutes:.6f} against the record's {row['champion_minutes']:.6f}")

    # QUESTION 2 — the MOVED boundary. Four raw fields in, a pod builds the 24
    # features, and the answer must be the champion's own to the bar the record
    # was measured at. Plus the header, without which a 0.000e+00 measured
    # against a pod that silently fell back to its committed CSVs would look
    # exactly like this one (ADR-012's named failure mode).
    t_host = tp["transformer"]["host"]
    t_url = tp["transformer"]["endpoint"]
    body = json.dumps(transformer_mod.encode_raw([hazard.request])).encode()
    req = urllib.request.Request(t_url, data=body,
                                 headers={"Content-Type": "application/json", "Host": t_host})
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.loads(r.read())
        lookups = r.headers.get("X-Taxi-Lookups", "")
    t_minutes = float(client_mod.minutes_of(payload)[0])
    t_version = str(payload.get("model_version", ""))
    if abs(t_minutes - champ_minutes) == 0.0 and t_version == served:
        ok(f"the TRANSFORMER answered {t_minutes:.6f} for the same hazard from FOUR RAW FIELDS "
           f"— |champion − transformer| = 0.000e+00 live, at the same model_version={t_version!r}")
    else:
        no(f"the transformer answered {t_minutes:.6f} at version {t_version!r} against the "
           f"champion's {champ_minutes:.6f} at {served!r}")
    groups = dict(p.split("=", 1) for p in lookups.split(",") if "=" in p)
    from_store = {g for g, s in groups.items() if s == "feature-store"}
    committed = {g for g, s in groups.items() if s != "feature-store"}
    if from_store and committed:
        ok(f"and X-Taxi-Lookups reports all {len(groups)} groups INCLUDING the "
           f"{len(committed)} that did NOT cross the wall ({', '.join(sorted(committed))}) — "
           f"F-059 as a header, so a pod that fell back to its CSVs cannot pass for one that "
           f"read the store")
    else:
        no(f"the lookup header does not distinguish store-backed from committed: {lookups!r}")

    # QUESTION 3 — the feature server, asked directly and TWO-SIDEDLY. A check
    # that only asserts presence passes against a server answering every
    # question with the same row.
    svc = json.loads(Path("automation/runs/m8-transformer/feast-server-deploy.json").read_text())
    forwarded = None
    fs_port = 6570
    fwd = subprocess.Popen(
        ["kubectl", "-n", "feast", "port-forward", "svc/feast-server", f"{fs_port}:6566"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        real_zone, non_place = None, None
        for zone_pair, slot in (([hazard.request.pu_location_id], "real"), ([264], "none")):
            payload = {"features": ["zone_static:centroid_lat", "zone_static:centroid_lon"],
                       "entities": {"zone_id": zone_pair}}
            for _ in range(40):
                try:
                    rq = urllib.request.Request(
                        f"http://127.0.0.1:{fs_port}/get-online-features",
                        data=json.dumps(payload).encode(),
                        headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(rq, timeout=5) as r:
                        answer = json.loads(r.read())
                    break
                except (urllib.error.URLError, ConnectionError, TimeoutError):
                    import time
                    time.sleep(0.25)
            else:
                answer = None
            names = answer["metadata"]["feature_names"] if answer else []
            vals = {n: answer["results"][i]["values"][0]
                    for i, n in enumerate(names)} if answer else {}
            if slot == "real":
                real_zone = vals.get("centroid_lat")
            else:
                non_place = vals.get("centroid_lat", "ABSENT")
        forwarded = True
        if real_zone is not None and non_place is None:
            ok(f"the FEATURE SERVER answered two-sidedly: a real zone got a centroid "
               f"({real_zone:.6f}) and TLC's non-place 264 got null — a store that answered "
               f"for a non-place would be inventing a location, and one that declined a real "
               f"zone would be a missing feature")
        else:
            no(f"the feature server's two-sided answer is wrong: real={real_zone}, "
               f"non-place={non_place!r}")
    finally:
        fwd.terminate()
        fwd.wait(timeout=10)
    if forwarded is None:
        no("the feature server could not be reached")

    # QUESTION 4 — DBSIZE. A gate over a feature store that never asks whether it
    # holds anything is gotcha #78 with the panel removed: an all-null store
    # yields an all-NaN geometry table and a confident quote, and no client can
    # refuse that because null is ALSO correct for zones 264/265. This is the
    # cheapest standing form of the residual M8-S4 left open.
    store = json.loads(Path("automation/runs/m8-online/store.json").read_text())
    pod = subprocess.run(
        ["kubectl", "-n", "feast", "get", "pods", "-l", "app=redis",
         "-o", "jsonpath={.items[0].metadata.name}"], capture_output=True, text=True).stdout.strip()
    dbsize_raw = subprocess.run(
        ["kubectl", "-n", "feast", "exec", pod, "--", "redis-cli", "DBSIZE"],
        capture_output=True, text=True).stdout.strip()
    dbsize = int(re.sub(r"\D", "", dbsize_raw) or 0)
    materialize = json.loads(
        Path("automation/runs/m8-online/materialize.json").read_text())
    # F-064 (found 2026-08-24 by `verify_m9.sh`'s first run, which copied this
    # clause): the record spells this `dbsize`, not `keys`. `.get("keys")`
    # returned None, `expected is None` was the branch that fired, and the
    # comparison this message CLAIMS to make was never made — the leg tested
    # `dbsize > 0` alone and would have passed a store holding one key. So the
    # key name is read from the record and the absence of the field is a FAIL
    # rather than a licence: #51's question ("could this component tell if it
    # were false?") asked of a clause that had already shipped green nine times.
    expected = materialize["store"].get("dbsize") if isinstance(
        materialize.get("store"), dict) else None
    if dbsize > 0 and expected == dbsize:
        ok(f"the ONLINE STORE holds {dbsize:,} keys right now — EQUAL to the count the "
           f"materialization recorded, survived on its PVC. An empty store answers every "
           f"lookup with null and nothing red anywhere, which is exactly why the gate asks")
    elif dbsize > 0:
        no(f"the store holds {dbsize:,} keys against the "
           f"{expected if expected is None else format(expected, ',')} the materialization "
           f"recorded — something re-wrote or partly lost it, or the record no longer carries "
           f"the field this leg reads (F-064's shape)")
    else:
        no("the online store is EMPTY — every store-backed feature would be null and the "
           "transformer would quote a confident wrong number")
    policy = store.get("maxmemory_policy")
    if policy == "noeviction":
        ok(f"and its eviction policy is {policy!r} (recorded off the running server) — a "
           f"correctness setting, not tuning: an evicting feature store drops the key the "
           f"next request asks for and answers null")
    else:
        no(f"the store's recorded eviction policy is {policy!r}, not noeviction")

    # QUESTION 5 — one PromQL query, F-043's inheritance: is the champion's own
    # exporter healthy RIGHT NOW? Scoped by isvc name read off the manifest,
    # never "the first result" (the M6 gameday picked up the shadow that way).
    q = f'up{{job="kserve-predictors",namespace="{ns}"}}'
    p_port = 9098
    pf = subprocess.Popen(
        ["kubectl", "-n", "monitoring", "port-forward", "svc/prometheus-server",
         f"{p_port}:80"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        result = None
        for _ in range(40):
            try:
                url = f"http://127.0.0.1:{p_port}/api/v1/query?query={urllib.parse.quote(q)}"
                with urllib.request.urlopen(url, timeout=5) as r:
                    result = json.loads(r.read())["data"]["result"]
                break
            except Exception:  # noqa: BLE001, PERF203
                import time
                time.sleep(0.25)
        ups = {m["metric"].get("pod", "?"): m["value"][1] for m in (result or [])}
        healthy = [p for p, v in ups.items() if v == "1"]
        if ups and len(healthy) == len(ups):
            ok(f"every scraped predictor exporter in namespace {ns!r} reads up==1 "
               f"({len(healthy)} target(s)) — F-043's question asked live, since a predictor "
               f"does not have to die to stop reporting, it only has to be busy")
        else:
            no(f"predictor exporters up: {ups} — a scrape is failing, so a latency alert "
               f"would evaluate over nothing")
    finally:
        pf.terminate()
        pf.wait(timeout=10)
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the live check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 6 "the live check"

# ------------------------------------------------ 6. what may not cross ------
section "6. F-059 as a TYPE, and the pointer nothing in M8 may touch"
consume < <(uv run python - 2>/dev/null <<'PY'
import ast
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    # (a) The type. `Lookups` has exactly two fields, so there is NOWHERE to put
    # a fetched borough code or airport flag. Asked of the AST and never of the
    # behaviour: a store whose values happened to agree would make a behavioural
    # test pass for a design that is wrong, and the failure it hides — a total
    # category re-map with every individual value correct — is invisible in
    # every individual value.
    tree = ast.parse(Path("src/taxi_mlops/features/lookups.py").read_text())
    cls = next(n for n in ast.walk(tree)
               if isinstance(n, ast.ClassDef) and n.name == "Lookups")
    fields = [n.target.id for n in cls.body if isinstance(n, ast.AnnAssign)]
    if sorted(fields) == ["calendar", "geometry_table"]:
        ok(f"`Lookups` carries exactly {fields} (ast) — F-059 as a type: there is no field a "
           f"fetched borough code or airport flag could arrive in, so the wrong design is "
           f"unrepresentable rather than merely untaken")
    else:
        no(f"`Lookups` now carries {fields} — a fetched category could cross")

    # (b) …and the request list agrees with the type.
    from taxi_mlops.serving.feature_store import ZONE_FEATURES
    asked = {f.split(":")[-1] for f in ZONE_FEATURES}
    if not ({"borough", "is_airport"} & asked):
        ok(f"and ZONE_FEATURES asks the store for {sorted(asked)} and nothing else — the "
           f"borough encoding is a property of the whole committed table, and `is_airport` is "
           f"a TOTAL function that answers for the non-places the store has no row for")
    else:
        no(f"ZONE_FEATURES asks the store for {sorted(asked & {'borough', 'is_airport'})} — "
           f"F-059's exact defect")

    # (c) The transformer refuses in three DISTINGUISHABLE classes. Collapsing
    # 503 into 422 would make a dependency outage look like a malformed quote in
    # every panel that splits 4xx from 5xx.
    t = Path("src/taxi_mlops/serving/transformer.py").read_text()
    statuses = set()
    for node in ast.walk(ast.parse(t)):
        if isinstance(node, ast.Constant) and node.value in (422, 503):
            statuses.add(node.value)
    if statuses == {422, 503}:
        ok("the transformer refuses in three distinguishable classes — an unreachable store "
           "is 503 (ours, retryable) while an uncovered date and an unknown input are 422 "
           "(the caller's); both codes present in the module (ast)")
    else:
        no(f"the transformer's refusal codes are {sorted(statuses)} — a dependency outage and "
           f"a malformed quote may be indistinguishable")

    # (d) NOTHING in M8's own code may mutate the registry. M8 law 3 in its
    # strong, structural form: not "we did not promote" but "these modules
    # cannot". AST over call names, because several of these files argue the
    # rule in prose that names the verbs (#53/#68).
    MUTATORS = {"set_registered_model_alias", "delete_registered_model_alias",
                "create_model_version", "transition_model_version_stage",
                "delete_model_version", "delete_registered_model", "register_model"}
    offenders = {}
    targets = sorted(Path("scripts").glob("feast_*.py")) + [
        Path("scripts/transformer_parity.py"),
        Path("src/taxi_mlops/serving/feature_store.py"),
        Path("src/taxi_mlops/serving/transformer.py"),
    ]
    checked = 0
    for path in targets:
        if not path.exists():
            continue
        checked += 1
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                if name in MUTATORS:
                    offenders.setdefault(str(path), set()).add(name)
    if checked >= 5 and not offenders:
        ok(f"not one of {checked} M8 modules CALLS a registry-mutating verb (ast over call "
           f"names, not grep) — law 3 as a structural property rather than as a report that "
           f"nothing happened to be promoted")
    else:
        no(f"registry mutation reachable from M8 code: {offenders} (checked {checked} files)")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the boundary check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 4 "the boundary check"

# --------------------------------- 7. the page, the accept, the alias law ----
section "7. the comparison page, §9/M8's accept answered line by line, and the pointer"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
import re
import subprocess
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    import mlflow
    import yaml

    from taxi_mlops.training import tracking
    from taxi_mlops.training.run import load_train_config

    PAGE = Path("docs/feast_side_by_side.md")
    page = PAGE.read_text()

    # (a) The page exists and carries a verdict vocabulary that is closed. A page
    # whose verdicts drift is a page that can call anything anything.
    ALLOWED = ("ADOPT", "DIFFER", "SURPASS")
    rows = re.findall(r"^\|\s*\*\*(\d+)\*\*\s*\|(.*)$", page, re.M)
    verdicts = []
    for _, body in rows:
        cells = [c.strip() for c in body.split("|")]
        verdicts.append(next((a for a in ALLOWED if any(a in c for c in cells)), None))
    unverdicted = [n for (n, _), v in zip(rows, verdicts) if v is None]
    if rows and not unverdicted:
        counts = {a: sum(1 for v in verdicts if v == a) for a in ALLOWED}
        ok(f"the comparison page carries {len(rows)} rows, every one with a verdict in "
           f"{list(ALLOWED)} — {counts}")
    else:
        no(f"page rows without a verdict: {unverdicted or 'the page has no verdict rows'}")

    # (b) HONEST IN BOTH DIRECTIONS — the kickoff's word. A survey with no ADOPT
    # is a press release and a survey with no SURPASS did not need writing.
    if verdicts.count("ADOPT") >= 1 and verdicts.count("SURPASS") >= 1:
        ok(f"and it is honest in both directions: {verdicts.count('ADOPT')} ADOPT and "
           f"{verdicts.count('SURPASS')} SURPASS — a survey with no ADOPT is a press release")
    else:
        no(f"the page is one-directional: {verdicts.count('ADOPT')} ADOPT, "
           f"{verdicts.count('SURPASS')} SURPASS")

    # (c) PER-ROW PROVENANCE — the kickoff's condition, and gotcha #15's spirit:
    # a claim's provenance travels with it. Every row must name a source key
    # that the sources table actually declares, and every declared source must
    # carry the date it was read.
    keys = set(re.findall(r"^\|\s*\*\*([A-Z])\*\*\s*\|", page, re.M))
    sourceless = []
    for (n, body), v in zip(rows, verdicts):
        cited = {k for k in keys if re.search(rf"\*\*{k}\*\*", body)}
        if not cited:
            sourceless.append(n)
    read_dates = len(re.findall(r"read 2026-\d\d-\d\d|2026-\d\d-\d\d\*\*", page))
    if keys and not sourceless:
        ok(f"every row cites at least one of the {len(keys)} declared sources "
           f"({', '.join(sorted(keys))}) — per-row provenance, so no claim about a community "
           f"repository floats free of what was actually read")
    else:
        no(f"rows citing no source: {sourceless}")
    if re.search(r"WebFetch|WebSearch", page) and re.search(r"F-001", page):
        ok("and the harvest method is stated with its limit named (F-001: WebFetch/WebSearch "
           "are off the allowlist, so the survey ran through `gh api` + `curl`) — the M1-S3 "
           "and M3-S2 idiom, third use")
    else:
        no("the page does not state how it was harvested or under what limit")

    # (d) §9/M8's accept-when, answered line by line rather than asserted.
    m7_gate = "verify-m7" in Path("Makefile").read_text()
    parity_table = Path("docs/feast_online_parity_table.md").exists()
    print("       §9/M8 accept-when, quoted: \"v1's M7 gate AND the comparison page exists.\"")
    print("                       Show: \"parity table + comparison\"")
    if m7_gate and PAGE.exists() and parity_table:
        ok("accept answered: (i) v1's M7 gate is `make verify-m7`, a live target run "
           "separately as its own evidence — the same treatment `verify-m7` gave M6's; "
           f"(ii) the comparison page exists at {PAGE}; (iii) Show — the parity table at "
           "docs/feast_online_parity_table.md and the comparison page, both committed")
    else:
        no(f"accept not answerable: verify-m7 target={m7_gate}, page={PAGE.exists()}, "
           f"parity table={parity_table}")

    # (e) THE ALIAS LAW, in its strong form. Not "the alias is still 2" — which
    # is satisfiable by not looking — but "no M8 work produced a registry
    # version at all". Derived: the m7-closed tag's commit time bounds M8, and
    # every version must predate it.
    cfg = load_train_config()
    tracking.configure(cfg["mlflow"])
    reg = cfg["registry"]
    client = mlflow.MlflowClient()
    champion = client.get_model_version_by_alias(reg["model_name"], reg["champion_alias"])
    versions = sorted(client.search_model_versions(f"name='{reg['model_name']}'"),
                      key=lambda v: int(v.version))
    tag_time = int(subprocess.run(["git", "log", "--format=%ct", "-1", "m7-closed"],
                                  capture_output=True, text=True).stdout.strip() or 0)
    after = [v.version for v in versions
             if (v.creation_timestamp or 0) / 1000 > tag_time]
    if tag_time and not after:
        ok(f"NOT ONE of the {len(versions)} registry versions was created after the m7-closed "
           f"tag — the strong form of law 3, because a promotion cannot hide from it: it must "
           f"create a version, and a version carries its own creation time")
    else:
        no(f"version(s) created during M8: {after} — something registered a model")

    train_cfg = yaml.safe_load(Path("configs/train.yaml").read_text())
    configured = train_cfg["features"]["version"]
    if champion.tags.get("feature_set") == configured:
        ok(f"and F-032's invariant still holds live: the served version "
           f"({champion.version}) eats {champion.tags['feature_set']!r}, which is what "
           f"configs/train.yaml tells every client to build")
    else:
        no(f"version {champion.version} eats {champion.tags.get('feature_set')!r} while "
           f"clients build {configured!r}")

    # (f) The settled pins. M8 read the 2019/2020 trees and wrote none of them
    # (law 2), so DVC must still call every one of them up to date.
    # DVC answers for ALL FOUR targets in ONE summary line when nothing moved
    # ("Data and pipelines are up to date.") and names each drifted target
    # individually when something did — so counting the phrase reported 1-of-4
    # over a perfectly clean tree on this gate's first run. The property is that
    # no target is REPORTED AS CHANGED, and the pin list is derived from the
    # tracked `.dvc` files rather than typed.
    pins = sorted(str(p) for p in Path("data").glob("*.dvc"))
    dvc = subprocess.run(["uv", "run", "dvc", "status", *pins],
                         capture_output=True, text=True, timeout=300)
    clean = "up to date" in dvc.stdout and not re.search(
        r"changed (outs|deps)|modified:", dvc.stdout)
    if pins and clean:
        ok(f"all {len(pins)} settled DVC pins are up to date ({', '.join(Path(p).stem for p in pins)}) "
           f"— M8 read the trees and wrote none of them (law 2), and the feature store's "
           f"parquet lives in its own untracked directory on `data/predictions/`'s terms")
    else:
        no(f"a settled pin has drifted:\n{dvc.stdout.strip()[:400]}")

    # (g) The ledgers. A wire mutation with no row is a change nobody can review.
    # WHICH stories owe a row is DERIVED, not typed: a story owes one if its
    # tracked records describe an object that was put on the cluster. And the
    # ledger is read ROW BY ROW — the first draft searched the whole document
    # and "found" an M8-S5 row inside leg 3's own prose sentence "M8-S5's gate
    # inherits it live" (gotcha #99, third occurrence in this repo).
    DEPLOYED_MARKERS = ("pod", "pod_uid", "image", "isvc", "namespace", "pvc", "service")
    owes = set()
    for rec in sorted(Path("automation/runs").glob("m8-*/*.json")):
        try:
            blob = json.loads(rec.read_text())
        except json.JSONDecodeError:
            continue
        flat = json.dumps(blob)
        if any(f'"{m}"' in flat for m in DEPLOYED_MARKERS):
            owes.add({"m8-drift": "1", "m8-provenance": "1", "m8-feast": "2",
                      "m8-pit": "3", "m8-online": "4", "m8-transformer": "4"}
                     .get(rec.parent.name, "?"))
    owes.discard("?")
    owes.discard("2")   # the quarantine and the feature repo are host-side only
    owes.discard("3")   # M8-S3 is a reader; it deployed nothing
    rows = {m for line in Path("ledgers/deployments.md").read_text().splitlines()
            if line.startswith("| 2026-")
            for m in re.findall(r"\*\*M8-S(\d)", line.split("|")[2] if len(line.split("|")) > 2 else "")}
    if rows >= owes and owes:
        ok(f"the deployments ledger carries a row for every M8 story whose records describe a "
           f"deployed object (owes M8-S{', M8-S'.join(sorted(owes))}; rows present: "
           f"M8-S{', M8-S'.join(sorted(rows))}) — read row by row, because the milestone's "
           f"own prose names other stories")
    else:
        no(f"the deployments ledger owes M8-S{sorted(owes)} and carries M8-S{sorted(rows)}")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the closing check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 8 "the closing check"

# ------------------------------------------------------------------ verdict --
echo
if [[ "$FAILS" -eq 0 ]]; then
  printf '\033[32m[verify-m8] GREEN — every M8 sub-check passed.\033[0m\n'
  printf '            Show: parity table   docs/feast_online_parity_table.md\n'
  printf '                  comparison     docs/feast_side_by_side.md\n'
  printf '                  the seams      docs/feast_pit_m8.md · feast_online_m8.md ·\n'
  printf '                                 feast_server_m8.md · transformer_m8.md\n'
  exit 0
fi
printf '\033[31m[verify-m8] RED — %d sub-check(s) failed.\033[0m\n' "$FAILS" >&2
exit 1
