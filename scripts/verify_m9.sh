#!/usr/bin/env bash
# verify_m9.sh — the M9 gate, and the program's last crossing. BLUEPRINT §9/M9,
# the committed half quoted:
#
#   "M9 — Stretch … the stakeholder demo: one self-contained page, two zone
#    pickers, a date-time picker, submit → a live ETA with the serving model
#    version shown.
#    Accept when: one non-technical person completes a query unassisted,
#    observed."
#
# The design rules are M2-S5's … M8-S5's, inherited whole:
#   * every check observes the THING, never a proxy;
#   * every Python leg must EMIT a minimum number of verdicts, so a leg that
#     dies on import FAILS instead of contributing zero silent passes;
#   * PROPERTIES, NOT LITERALS (F-017, gotchas #49/#50). This gate types no
#     champion version, no key count, no zone id, no bar, no reader path and no
#     test name. Every number it compares is read from two places and matched;
#   * prose against records at ≥1 decimal (gotcha #90);
#   * no skip flag, no fast mode. M1's rule, inherited a NINTH and final time.
#
# RE-RUNS NOTHING. M9's evidence is a deployed page, a materialized store and a
# ~9 minute drill that included a REAL total outage of the transformer's
# dependency (`FLUSHDB` against the online store). Re-provoking any of it would
# cost an outage per verification; re-running the demo's own accept would write
# over the record this gate exists to read. It does not deploy, does not build a
# page, does not materialize, does not push a metric, does not fit and does not
# move a pointer. It reads: the tracked records M9-S1 and M9-S2 wrote, the
# committed page and docs, the rules file, the code with `ast`, git, the
# registry — and it asks the live system exactly THREE questions:
#
#     one quote through the DEMO's own request path
#     one rules read at Prometheus
#     one DBSIZE at the online store
#
# That count is pinned by `tests/unit/test_verify_m9.py`. Three and not M8's
# five, deliberately: the champion's own wire, the feature server's two-sided
# answer and the predictor exporter's health are `verify-m5`'s and
# `verify-m8`'s questions, and those gates are runnable live as their own
# evidence. A gate that re-asks its predecessors' questions is not stricter; it
# is a gate whose live footprint grows every milestone.
#
# WHAT THIS GATE ASKS THAT NO PREDECESSOR COULD — three things.
#
#  1. A BOX THAT MUST STAY OPEN (§2). §9/M9's last accept line needs a human:
#     "one non-technical person completes a query unassisted, observed". An
#     unattended session cannot close it, so the gate is chartered to assert
#     that it is recorded OPEN and honestly — that the record says so, that the
#     AWAITING_PO entry exists, and that the two agree on the URL. It NEVER
#     renders the box green. This is the only place in the program where a gate
#     passes BECAUSE something is unfinished, and that is the point: the
#     alternative is the one dishonest artifact in the repo.
#
#  2. TWO RULES THAT CARRY NO NUMBER (§4). A-12a compares a canary claim to
#     `0` — a property, not a bar — and A-12b compares a live key count to an
#     EXPECTED key count that the reader pushes on the same run. So the gate
#     cannot check those bars against a document, because there are none. What
#     it checks instead is stronger: that the comparison has no numeric literal
#     on either side, that the ONE number in the three rules (A-12's 1800 s
#     freshness clause) is argued in `docs/slo_serving.md` §9, and that every
#     metric the rules SELECT is a metric the reader PUSHES — a rule selecting
#     a series nobody produces does not error, it sits inactive forever, which
#     is indistinguishable from a healthy store (gotcha #92).
#
#  3. THE EXPECTED KEY COUNT HAS THREE WITNESSES AND THE GATE ASKS ALL THREE
#     (§5). `keys < keys_expected` is only honest if `keys_expected` is derived
#     from the store's sources rather than remembered. The headroom record's
#     per-view counts must SUM to its own total, the materialization record must
#     agree, and the live store must agree with both. This is what the red team
#     plants against: an expected total short by exactly `zone_static`'s 263
#     keys — the view every geometry feature depends on — leaves a store that
#     could lose all its centroids and still satisfy A-12b.
#
# Prints one line per sub-check and exits nonzero if ANY fails — it keeps going
# rather than stopping at the first, so one run tells you everything broken.
#
# Usage: scripts/verify_m9.sh          (via `make verify-m9`)
#        scripts/verify_m9_redteam.sh  proves this gate can go RED
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

printf '\n\033[1m[verify-m9]\033[0m the M9 gate — a page generated from three sources, an accept\n'
printf '            answered line by line, two rules that carry no number, and one\n'
printf '            box that must stay open because only a human can close it.\n'

# ---------------------------------------------------------- 1. the page -------
section "1. the demo page — generated from three sources, and nothing about it retyped"
consume < <(uv run python - 2>/dev/null <<'PY'
import hashlib
import json
import re
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    from taxi_mlops.serving import transformer as transformer_mod

    PAGE = Path("demo/index.html")
    LOOKUP = Path("data/reference/taxi_zone_lookup.csv")
    accept = json.loads(Path("automation/runs/m9-demo/accept.json").read_text())
    page = PAGE.read_text()

    # (a) The zone list is DERIVED or it is a twin. The count is the check
    # rather than the content, because gotcha #110 was exactly a page whose
    # three copies of the list all matched the CSV — the generator had
    # substituted its own explanatory comment as a fourth slot and shipped 795
    # options where 530 belong. So: distinct LocationIDs in the CSV, times the
    # two pickers, against the options the page actually carries.
    ids = set()
    for line in LOOKUP.read_text().splitlines()[1:]:
        head = line.split(",")[0].strip().strip('"')
        if head.isdigit():
            ids.add(int(head))
    options = re.findall(r"<option value=\"(\d+)\"", page)
    if ids and len(options) == 2 * len(ids):
        ok(f"the pickers carry {len(options)} <option> elements — exactly 2 x the "
           f"{len(ids)} distinct LocationIDs in {LOOKUP.name}, so the list is derived from "
           f"the lookup and not retyped beside it (gotcha #110's count, not its content)")
    else:
        no(f"the page carries {len(options)} option(s) against 2 x {len(ids)} zones in the "
           f"lookup — the embedded list has drifted from its source")

    # (b) The request SCHEMA is the server's own declaration. A wrong field NAME
    # would be refused loudly by decode_raw; a wrong DATATYPE would not be, and
    # would quote a plausible number nobody can see is wrong.
    # All THREE fields, not just the wire name: `field` is which key of the
    # form's own state feeds the input, so a correct name carrying the wrong
    # field is two individually-valid values under each other's names —
    # gotcha #73's shape, self-inflicted.
    declared = {(name, datatype, field)
                for name, (datatype, field) in transformer_mod.RAW_INPUTS.items()}
    embedded = {(spec["name"], spec["datatype"], spec["field"])
                for spec in json.loads(
                    re.search(r"const RAW_INPUTS = (\[.*?\]);", page, re.S).group(1))}
    if declared and embedded == declared:
        ok(f"the page's request schema is the SERVER's own declaration — "
           f"{len(declared)} raw input(s), wire name AND datatype AND source field, equal to "
           f"transformer.RAW_INPUTS. A wrong name is refused loudly by `decode_raw`; a wrong "
           f"datatype is not, and would quote a plausible number nobody can see is wrong")
    else:
        no(f"the page declares {sorted(embedded)} against the server's {sorted(declared)}")

    # (c) The default trip is a PUBLISHED row, so the first thing a stakeholder
    # sees is checkable against a record rather than being a fixture.
    trip = json.loads(re.search(r"const DEFAULT_TRIP = (\{.*?\});", page, re.S).group(1))
    anchor = accept["anchor"]
    recorded = accept["default_trip"]
    if trip == recorded and anchor.get("record"):
        ok(f"the page opens on a PUBLISHED trip — zone {trip['pu_location_id']} -> "
           f"{trip['do_location_id']} at {trip['pickup_datetime']} — the row "
           f"{anchor['record']} already holds under hazard {anchor['hazard']!r}, so the "
           f"demo's first screen is checkable against a measurement")
    else:
        no(f"the page's default trip {trip} is not the trip the accept record anchored on "
           f"({recorded})")

    # (d) TLC's two non-places are RENDERED, not hidden. They carry no centroid
    # by DR-04 condition 1, they are ~1% of every split, 264->264 is the largest
    # single OD "route" in the data, and F-030 was found on that path. A picker
    # that hid them would make the demo tidier than the world it quotes for.
    geometry = Path("data/reference/taxi_zone_centroids.csv").read_text().splitlines()[1:]
    with_geometry = {int(ln.split(",")[0]) for ln in geometry if ln.split(",")[0].isdigit()}
    rendered_nonplaces = sorted({int(o) for o in options} - with_geometry)
    ng = accept.get("no_geometry", {})
    if rendered_nonplaces and ng.get("http_status") == 200:
        ok(f"and TLC's non-place zone(s) {rendered_nonplaces} are RENDERED rather than hidden "
           f"— they have no row in the centroid table by design, and the accept quoted "
           f"{ng['trip']['pu_location_id']} -> {ng['trip']['do_location_id']} at "
           f"{ng['minutes']:.4f} min from the features that remain")
    else:
        no(f"zones with no geometry are not both rendered and quotable: rendered="
           f"{rendered_nonplaces}, no-geometry quote={ng.get('http_status')}")

    # (e) The file in git is the file the browser received. Fetched BACK through
    # the route by the accept rather than asserted from the ConfigMap, and
    # re-derived here off disk so a page edited after the accept ran is caught.
    live = hashlib.sha256(PAGE.read_bytes()).hexdigest()
    rec = accept["page"]
    if rec["committed_sha256"] == rec["served_sha256"] == live:
        ok(f"the page a browser receives is byte-identical to the one in git "
           f"(sha256 {live[:16]}…, {rec['bytes']:,} bytes) — served, fetched back through the "
           f"route, and re-hashed off disk by this gate, three readings of one file")
    else:
        no(f"the page has drifted: on disk {live[:16]}…, committed "
           f"{rec['committed_sha256'][:16]}…, served {rec['served_sha256'][:16]}…")

    # (f) THE ONE-TRANSFORM-PATH LAW, as a property of the page. A browser
    # cannot run `taxi_mlops.features`, and a JS re-implementation would be the
    # second feature path the law forbids — so the page must target the RAW
    # boundary and not the 24-column wire. Both names are derived: the champion's
    # off its manifest, the transformer's off the endpoint the page declares.
    endpoint = re.search(r'const ENDPOINT = "([^"]+)"', page).group(1)
    manifest = Path("infra/manifests/inferenceservice-champion.yaml").read_text()
    champion_isvc = re.search(r"^\s+name:\s*(\S+)", manifest, re.M).group(1)
    served_name = endpoint.strip("/").split("/")[2]
    unclaimed = [c for c in accept["checks"] if "404" in c["claim"] and c["ok"]]
    if served_name != champion_isvc and served_name.startswith(champion_isvc) and unclaimed:
        ok(f"the page posts to {endpoint} — the RAW boundary ({served_name!r}), NOT the "
           f"champion's own model name ({champion_isvc!r}), which the accept proved 404s on "
           f"this origin. A browser cannot build a 24-column matrix and a JS feature path "
           f"would be the second transform path the law forbids")
    else:
        no(f"the page's endpoint {endpoint!r} resolves to model {served_name!r} against the "
           f"champion's {champion_isvc!r}; unclaimed-name check present={bool(unclaimed)}")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the page check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 6 "the page check"

# ------------------------------------------------- 2. the accept, line by line
section "2. §9/M9's accept — answered line by line, including the human box: OPEN and honest, or CLOSED and CITED"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
import re
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    accept = json.loads(Path("automation/runs/m9-demo/accept.json").read_text())
    README = Path("demo/README.md")
    readme = README.read_text()

    # (a) The record's own verdict, and the count derived from the record.
    checks = accept["checks"]
    failed = [c for c in checks if not c["ok"]]
    if checks and not failed and not accept["failures"]:
        ok(f"the accept record carries {len(checks)} check(s), every one ok and its failure "
           f"list empty — the demo answered on the route, in the shape the page sends")
    else:
        no(f"the accept record reports {len(failed)} failed check(s): "
           f"{[c['claim'][:60] for c in failed]}")

    # (b) THE BAR IS PARSED, NEVER TYPED. A gate carrying its own tolerance
    # stays green after the document loosens — the exact change the constitution
    # reserves for a PO fork. §4 of the README argues EXACT; the accept must
    # have been held to it, and the anchor must be a row another record holds.
    bar_doc = re.search(r"\*\*The bar is (\w+):", readme)
    bar_rec = accept["quote"]["bar"].split()[0].strip("*")
    delta = float(accept["quote"]["abs_delta_minutes"])
    if bar_doc and bar_doc.group(1).upper() == bar_rec.upper() == "EXACT" and delta == 0.0:
        ok(f"the bar is {bar_doc.group(1)}, parsed out of the section that argues it, and the "
           f"accept met it: |delta| = {delta:.3e} minutes. Not 'within tolerance' — the demo's "
           f"answer and the recorded one are the same float64")
    else:
        no(f"bar in the document = {bar_doc.group(1) if bar_doc else None!r}, bar in the "
           f"record = {bar_rec!r}, measured delta = {delta}")

    anchor_path = Path(accept["anchor"]["record"])
    parity = json.loads(anchor_path.read_text())
    trip = accept["default_trip"]
    row = next((r for r in parity["rows"]
                if r.get("at") == trip["pickup_datetime"]
                and r.get("pu") == trip["pu_location_id"]
                and r.get("do") == trip["do_location_id"]), None)
    if row is None:
        row = next((r for r in parity["rows"]
                    if r.get("hazard") == accept["anchor"]["hazard"]), None)
    recorded_minutes = None
    if row:
        recorded_minutes = row.get("transformer_minutes", row.get("champion_minutes"))
    if recorded_minutes is not None and accept["quote"]["minutes"] == recorded_minutes:
        ok(f"and the number is CROSS-ARTIFACT: the demo quoted {accept['quote']['minutes']!r} "
           f"and {anchor_path} holds {recorded_minutes!r} for the same (at, pu, do) — matched "
           f"on the trip, so neither side carries the other's literal")
    else:
        no(f"the accept's {accept['quote']['minutes']!r} does not match the anchor record's "
           f"{recorded_minutes!r} for that trip")

    # (c) The version is read off the ANSWER, which is a different fact from a
    # metadata call: mlserver reports `versions: []` on this runtime (M5-S2), so
    # the stamp on the response is the only thing that describes THIS moment.
    if accept["quote"]["model_version"] == accept["anchor"]["model_version"]:
        ok(f"the serving model version is stamped on the ANSWER — "
           f"{accept['quote']['model_version']!r}, equal to the anchor record's — mlserver's "
           f"own stamp forwarded verbatim, never a metadata call that could describe another "
           f"moment")
    else:
        no(f"the demo's answer stamped {accept['quote']['model_version']!r} against the "
           f"record's {accept['anchor']['model_version']!r}")

    # (d) The lookup header, and it is the reason a 0.000e+00 means anything: a
    # pod that silently fell back to its committed CSVs would measure exactly
    # the same delta (ADR-012's named failure mode).
    groups = dict(p.split("=", 1) for p in accept["quote"]["lookups"].split(",") if "=" in p)
    crossed = {g for g, s in groups.items() if s == "feature-store"}
    committed = {g for g, s in groups.items() if s != "feature-store"}
    if accept["quote"]["lookups"] == accept["anchor"]["lookup_sources"] and crossed and committed:
        ok(f"X-Taxi-Lookups on the demo's own response equals the recorded string: "
           f"{len(crossed)} group(s) came from the feature store and "
           f"{len(committed)} did NOT cross the wall ({', '.join(sorted(committed))}) — "
           f"F-059 as a header, so the store is proved consulted THROUGH THIS PATH")
    else:
        no(f"the lookup header does not reconcile: demo {accept['quote']['lookups']!r} vs "
           f"recorded {accept['anchor']['lookup_sources']!r}")

    # (e) The refusal is a FEATURE of the demo, not a hidden edge. F-019's
    # horizon, carried onto the store's wire at M8-S4 leg 3.
    ref = accept["refusal"]
    year = ref["pickup_datetime"][:4]
    if ref["http_status"] == 422 and year in ref["error"]:
        ok(f"an uncovered date is REFUSED and named: HTTP {ref['http_status']} for "
           f"{ref['pickup_datetime']}, and the message contains the year {year} plus the "
           f"command that extends the table — a wrong quote there would be a number nobody "
           f"could see was wrong")
    else:
        no(f"the past-horizon request returned {ref['http_status']} and its text "
           f"{'names' if year in ref['error'] else 'does NOT name'} the date")

    # (f) THE HUMAN BOX, in the only two states it may honestly be in. The gate
    # is chartered to assert that it is recorded honestly and never to render it
    # green on its own authority — so it has no opinion about WHICH state is
    # right, and a hard opinion about what each one owes.
    #
    #   OPEN   — the record says OPEN and AWAITING_PO carries the live
    #            invitation, so a reader can go and close it.
    #   CLOSED — the record says CLOSED and CITES an AWAITING_PO entry that
    #            EXISTS and CONTAINS the observer's note verbatim.
    #
    # A CLOSED status with no citation, or a citation the inbox does not hold,
    # is RED. That is the whole check: this box can only be closed by a human,
    # so the only evidence a gate can ask for is the human's own words in the
    # inbox they were written into — and a claim that an entry exists is not
    # the entry (M9-S4's rule, re-derived here rather than a literal OPEN,
    # gotcha #50: the state legitimately changed, so the assertion must be the
    # property that holds in both).
    box = accept["po_observed_run"]
    awaiting = Path("AWAITING_PO.md").read_text()
    url = str(box.get("url", ""))
    state = str(box.get("status", "")).upper()
    invitation = bool(url) and url in awaiting
    is_the_box = "observed" in str(box.get("box", "")).lower()
    cites = str(box.get("cites", "")).strip()
    note = str(box.get("po_note", "")).strip()
    cited = bool(cites) and f"## {cites}" in awaiting
    # The inbox is markdown: a quoted note lives inside a blockquote and is
    # wrapped at the column the file is written to, so it is never a contiguous
    # string there. The claim being checked is that the inbox holds these WORDS,
    # not that it holds these bytes — so both sides are flattened (blockquote
    # markers dropped, whitespace runs collapsed) before the comparison. Asked
    # the naive way this leg goes RED on a perfectly honest citation, which is
    # gotcha #50 in the check that exists to stop this box being rounded up.
    flat = re.sub(r"\s+", " ", " ".join(ln.lstrip("> ") for ln in awaiting.splitlines()))
    quoted = bool(note) and re.sub(r"\s+", " ", note).strip() in flat
    if is_the_box and invitation and state.startswith("OPEN"):
        ok(f"§9/M9's last accept line is recorded OPEN and honestly: the record says "
           f"{box['status'].split('—')[0].strip()!r}, AWAITING_PO carries the invitation with "
           f"the same URL ({url}), and THIS GATE DOES NOT RENDER IT GREEN — an unattended "
           f"session cannot watch a human use a page, and a demo that marked its own "
           f"human-observation box green would be the one dishonest artifact in this program")
        print(f"       OPEN ITEM (by design, not by omission): {box['box']}")
    elif is_the_box and invitation and state.startswith("CLOSED") and cited and quoted:
        ok(f"§9/M9's last accept line is recorded CLOSED and CITED — closed "
           f"{box.get('closed_on')} against AWAITING_PO {cites}, an entry this inbox really "
           f"holds, and the observer's note is quoted there VERBATIM rather than paraphrased "
           f"here. The gate still renders nothing green on its own authority: a CLOSED status "
           f"with no citation, or one the inbox does not carry, is RED")
        print(f"       CLOSED BY A HUMAN (AWAITING_PO {cites}, {box.get('closed_on')}): "
              f"{note}")
    else:
        why = []
        if not is_the_box:
            why.append("the record's `box` is not §9/M9's observed-run line")
        if not invitation:
            why.append(f"AWAITING_PO does not carry the URL {url!r}")
        if state.startswith("CLOSED"):
            if not cites:
                why.append("it is CLOSED and cites no AWAITING_PO entry")
            elif not cited:
                why.append(f"it cites AWAITING_PO {cites}, an entry this inbox does not hold")
            if not note:
                why.append("it is CLOSED and quotes no note from the observer")
            elif not quoted:
                why.append("the note it quotes appears nowhere in AWAITING_PO")
        elif not state.startswith("OPEN"):
            why.append(f"status={box.get('status')!r} is neither OPEN nor CLOSED")
        no("the PO-observed box is not honestly recorded: " + "; ".join(why))

    # (g) The route decision is RECORDED (§9/M9 asks for exactly this), and the
    # property it rests on is asserted off the committed manifest rather than
    # off the prose: a host-less rule lands in nginx's DEFAULT server block,
    # which is what makes the page same-origin with the model and dissolves
    # CORS. F-039's law also lives here — the rule must not take a name KServe
    # generates.
    ing = next((p for p in Path("infra/manifests").glob("*demo*") if p.suffix in {".yaml", ".yml"}), None)
    manifest = ing.read_text() if ing else ""
    rule = re.search(r"kind:\s*Ingress(.*)$", manifest, re.S)
    body = rule.group(1) if rule else ""
    hostless = bool(body) and not re.search(r"^\s+-?\s*host:", body, re.M)
    decision = "CORS" in readme and re.search(r"^## 1\.", readme, re.M)
    invariants = [c for c in accept["checks"] if "/healthz" in c["claim"] and c["ok"]]
    if hostless and decision and invariants:
        ok(f"the route decision is recorded in {README} §1 and its property is asserted off "
           f"the manifest: the Ingress rule carries NO `host:`, so it lives in nginx's default "
           f"server block beside the /healthz that block already answers — same origin as the "
           f"model, so CORS never happens rather than being configured. The accept re-checked "
           f"both invariants it shares that block with (/healthz 200, / 404)")
    else:
        no(f"route decision: host-less rule={hostless} (manifest {ing}), §1 recorded="
           f"{bool(decision)}, shared-block invariants re-checked={bool(invariants)}")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the accept check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 8 "the accept check"

# ------------------------------------------------------- 3. law 4, from git ---
section "3. law 4 — every M9 bar argued BEFORE the record it judges, checked from git"
consume < <(uv run python - 2>/dev/null <<'PY'
import re
import subprocess
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

def added_at(path: str) -> int:
    """The commit time at which a path ENTERED the repository."""
    out = subprocess.run(["git", "log", "--diff-filter=A", "--format=%ct", "-1", "--", path],
                         capture_output=True, text=True).stdout.strip()
    return int(out) if out.isdigit() else 0

def introduced_at(needle: str, path: str) -> int:
    """The commit time at which a STRING entered a file that already existed.

    `--diff-filter=A` cannot answer for a section appended to a long-lived
    document, and docs/slo_serving.md has carried eight sections since M6.
    """
    out = subprocess.run(["git", "log", "-S", needle, "--format=%ct", "--", path],
                         capture_output=True, text=True).stdout.split()
    return int(out[-1]) if out else 0

try:
    # A document cannot honestly testify that it was written before the
    # measurement it judges — so the claim is asked of git, four times, and the
    # gate prints the gap rather than a verdict word.
    demo_bar = introduced_at("THE BAR THE ACCEPT IS HELD TO", "demo/README.md")
    demo_rec = added_at("automation/runs/m9-demo/accept.json")
    if demo_bar and demo_rec and demo_bar < demo_rec:
        ok(f"the demo's EXACT bar was committed {demo_rec - demo_bar} s BEFORE the accept "
           f"record it judges entered the repo — M8 law 4's ordering, tenth inheritance, "
           f"read off `git log` and not off a sentence claiming it")
    else:
        no(f"ordering unproven or wrong: bar argued at {demo_bar}, accept record added at "
           f"{demo_rec}")

    slo_sec = introduced_at("The online-store targets", "docs/slo_serving.md")
    headroom = added_at("automation/runs/m9-store-watch/headroom.json")
    drills = [added_at(str(p)) for p in
              sorted(Path("automation/runs/m9-store-watch").glob("drill-*.json"))]
    first_drill = min([d for d in drills if d] or [0])
    if headroom and slo_sec and headroom <= slo_sec:
        ok(f"the HEADROOM was recorded before the section that argues from it "
           f"({slo_sec - headroom} s, same commit or earlier) — the store's key composition "
           f"was measured first, and it is what killed the key-count threshold the kickoff "
           f"expected: the transformer's whole dependency is 8% of the count")
    else:
        no(f"the headroom record ({headroom}) does not precede §9's argument ({slo_sec})")

    if slo_sec and first_drill and slo_sec < first_drill:
        ok(f"and §9's bars were argued {first_drill - slo_sec} s before the FIRST drill record "
           f"— the drill that first crosses a bar cannot be the thing that chose it")
    else:
        no(f"§9 was introduced at {slo_sec} and the first drill record added at {first_drill}")

    pred = added_at("automation/runs/m9-store-watch/prediction.json")
    if pred and first_drill and pred < first_drill:
        ok(f"and the drill's PREDICTION was committed {first_drill - pred} s before its first "
           f"record — written to disk before the first FLUSHDB, so a prediction cannot be "
           f"amended into agreement with an outcome (M6-S5's rule, and a test pins the "
           f"committed file against the drill's own literal)")
    else:
        no(f"the prediction was added at {pred}, the first drill record at {first_drill}")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the ordering check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 4 "the ordering check"

# ---------------------------------------------------- 4. the watchdog's rules -
section "4. the watchdog — three rules, two of them carrying no number, and no series nobody pushes"
consume < <(uv run python - 2>/dev/null <<'PY'
import ast
import re
import subprocess
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    import yaml

    from taxi_mlops.monitoring import store_health

    RULES = Path("infra/monitoring/alerting_rules.yml")
    SLO = Path("docs/slo_serving.md")
    doc = SLO.read_text()
    document = yaml.safe_load(RULES.read_text())
    rules = [r for g in document["groups"] for r in g["rules"]]

    # WHICH rules are M9's is DERIVED from the signal ids this story
    # implemented, never from a typed list of alert names: the renderer owns the
    # id vocabulary and a rule renamed tomorrow must not orphan this leg.
    m9_signals = sorted(set(store_health.SIGNALS)) if hasattr(store_health, "SIGNALS") else []
    if not m9_signals:
        m9_signals = sorted({r["labels"]["signal"] for r in rules
                             if "online_store" in r.get("expr", "")})
    mine = [r for r in rules if r["labels"].get("signal") in m9_signals]

    if len(mine) >= 3 and all(r["annotations"].get("why") for r in mine):
        ids = ", ".join(sorted({r["labels"]["signal"] for r in mine}))
        ok(f"{len(mine)} online-store rule(s) under signal id(s) {ids}: "
           f"{', '.join(r['alert'] for r in mine)} — and every one carries an "
           f"`annotations.why`, which `render_alert_rules.py` REFUSES a rule without: a "
           f"threshold whose argument is not beside it is a number nobody can review")
    else:
        no(f"the online-store rules are {[r['alert'] for r in mine]} and "
           f"{sum(1 for r in mine if not r['annotations'].get('why'))} lack a `why`")

    # (b) THE PROPERTY, NOT A BAR. A-12a's right-hand side is `0`: each canary
    # claim either held or did not, and there is no number to choose. A-12b
    # compares a metric to a metric. So the gate asserts the ABSENCE of a bar,
    # which is the only checkable form of "this rule carries no threshold".
    canary = next(r for r in mine if store_health.CANARY_METRIC in r["expr"])
    keys_rule = next(r for r in mine if f"{store_health.KEYS_EXPECTED_METRIC}" in r["expr"])
    canary_cmp = re.search(rf"{store_health.CANARY_METRIC}\{{[^}}]*\}}\s*==\s*(\S+?)\)", canary["expr"])
    keys_cmp = re.search(rf"{store_health.KEYS_METRIC}\{{[^}}]*\}}\s*\n?\s*<", keys_rule["expr"])
    if canary_cmp and canary_cmp.group(1) == "0" and keys_cmp:
        ok(f"{canary['alert']} compares a claim to 0 — a PROPERTY, not a threshold: each of "
           f"the four claims either held or did not, and $labels.check names which. "
           f"{keys_rule['alert']} compares {store_health.KEYS_METRIC} to "
           f"{store_health.KEYS_EXPECTED_METRIC}, so there is NO NUMBER ON EITHER SIDE and "
           f"the rule self-updates when the sources legitimately change")
    else:
        no(f"the two A-12 rules no longer compare against properties: canary RHS="
           f"{canary_cmp.group(1) if canary_cmp else None!r}, keys-vs-expected={bool(keys_cmp)}")

    # (c) The ONE number across the three, and it must be argued in §9
    # SPECIFICALLY — a bar argued in the latency section is not an argument for
    # a freshness clause (verify-m7's rule, inherited).
    sec9 = doc[doc.index("## 9."):] if "## 9." in doc else ""
    numbers = set()
    for r in mine:
        for m in re.finditer(r"[<>]=?\s*([0-9]+(?:\.[0-9]+)?)", r["expr"]):
            if m.group(1) != "0":
                numbers.add(m.group(1))
    unargued = sorted(n for n in numbers if n not in sec9)
    if numbers and not unargued:
        ok(f"the only bar-shaped number in all three rules is {sorted(numbers)} (A-12's "
           f"freshness clause in seconds), and it is argued in §9 of {SLO.name} — parsed out "
           f"of the rules and looked for in the section, so a loosened clause is a RED gate "
           f"rather than a diff nobody read")
    else:
        no(f"numbers in the M9 rules: {sorted(numbers)}; not argued in §9: {unargued}")

    # (d) A-13 exists BECAUSE A-12 cannot see its own absence, and both halves
    # of that sentence must be in the artifacts: `absent(` in the rule, and the
    # blindness named at the rule where an on-call reads it.
    absent_rule = [r for r in mine if r["expr"].strip().startswith("absent(")]
    blind = [r for r in mine if any(
        k in r["annotations"] for k in ("freshness", "blind_spot"))]
    if absent_rule and len(blind) >= 2:
        ok(f"{absent_rule[0]['alert']} is an `absent(...)` rule with a "
           f"{absent_rule[0]['for']} sustain — A-11's argument one board along, because "
           f"`time() - stamp < N` over ZERO series is zero series and not a stale reading; "
           f"and {len(blind)} rule(s) name their own blind spot in an annotation, where an "
           f"on-call reads it rather than in a document they do not have open")
    else:
        no(f"absence rule present={bool(absent_rule)}, rules naming a blind spot={len(blind)}")

    # (e) The renderer's two sets must agree, and the closure must be
    # ENFORCED rather than asserted: an id implemented with no rule, or a rule
    # under an id documented as having no source, fails the renderer in BOTH
    # directions.
    render = subprocess.run(["uv", "run", "python", "scripts/render_alert_rules.py", "--check"],
                            capture_output=True, text=True, timeout=180)
    from importlib import util as _util
    spec = _util.spec_from_file_location("rar", "scripts/render_alert_rules.py")
    rar = _util.module_from_spec(spec)
    spec.loader.exec_module(rar)
    covered = set(m9_signals) <= rar.IMPLEMENTED_SIGNALS
    if render.returncode == 0 and covered and not rar.DOCUMENTED_ABSENCES:
        ok(f"the renderer validates the whole file ({len(rules)} rules, exit 0) and its two "
           f"sets agree: {sorted(m9_signals)} are in IMPLEMENTED_SIGNALS and "
           f"DOCUMENTED_ABSENCES is empty — the store watchdog cannot be quietly forgotten "
           f"OR quietly claimed")
    else:
        no(f"renderer exit={render.returncode}, M9 ids covered={covered}, documented "
           f"absences={sorted(rar.DOCUMENTED_ABSENCES)}")

    # (f) EVERY METRIC THE RULES SELECT IS A METRIC THE READER PUSHES. A rule
    # selecting a series nobody produces does not error — it sits inactive
    # forever, indistinguishable from a healthy store (gotcha #92's shape). Both
    # sides derived: the names off the module's own constants, the selections out
    # of the rules.
    produced = {v for k, v in vars(store_health).items()
                if k.endswith("_METRIC") and isinstance(v, str)}
    selected = set()
    for r in mine:
        selected |= {m for m in re.findall(r"\b(taxi_[a-z0-9_]+)\b", r["expr"])}
    orphans = sorted(selected - produced)
    unused = sorted(produced - selected)
    if selected and not orphans:
        ok(f"all {len(selected)} series the rules SELECT are produced by "
           f"{store_health.__name__} ({len(produced)} declared, {len(unused)} unused) — a rule "
           f"selecting a series nobody pushes stays `health=ok` and `inactive` forever, which "
           f"is exactly what a healthy store looks like")
    else:
        no(f"the rules select series nothing pushes: {orphans}")

    # (g) The reader ISSUES NO VERDICT. The bar lives in the rule's selector, so
    # the pushed numbers stay re-interpretable after the fact (M7-S3's rule).
    # Asked of the AST, never a grep: these modules argue their own design at
    # length (#53/#68).
    reader_rel = re.search(r"^store-watch:.*?\n\t@uv run python (\S+)", Path("Makefile").read_text(),
                           re.S | re.M).group(1)
    tree = ast.parse(Path(reader_rel).read_text())
    bars = [
        c.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Compare)
        and n.ops
        and isinstance(n.ops[0], (ast.Lt, ast.Gt, ast.LtE, ast.GtE))
        for c in n.comparators
        if isinstance(c, ast.Constant) and isinstance(c.value, float)
    ]
    if not bars:
        ok(f"{reader_rel} (path DERIVED from the Makefile recipe, F-017) issues NO verdict — "
           f"no fractional bar-shaped constant anywhere in its comparisons, asked of the AST. "
           f"The bar lives in the SELECTOR of a rule, so the pushed numbers stay "
           f"re-interpretable after the fact")
    else:
        no(f"{reader_rel} compares against bar-shaped constant(s) {bars} — a reader that "
           f"judges puts a threshold outside the file that argues thresholds")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the rules check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 7 "the rules check"

# ------------------------------------------------------ 5. three live questions
section "5. the live system — THREE questions: the demo's own path, the rules, the store's size"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from importlib import util as _util
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    import mlflow

    from taxi_mlops.training import tracking
    from taxi_mlops.training.run import load_train_config

    accept = json.loads(Path("automation/runs/m9-demo/accept.json").read_text())

    # QUESTION 1 — one quote through the DEMO's OWN REQUEST PATH. The endpoint,
    # the schema and the payload are READ OUT of demo/index.html by the accept
    # script's own helpers, and the module's path is DERIVED from the Makefile
    # recipe rather than typed (the M8 gate went red on its own first run for
    # typing a reader's filename). No Host override — the one thing a browser
    # cannot do and every other client in this repo does.
    accept_rel = re.search(r"^demo-accept:.*?\n\t@uv run python (\S+)",
                           Path("Makefile").read_text(), re.S | re.M).group(1)
    spec = _util.spec_from_file_location("demo_accept_mod", accept_rel)
    demo = _util.module_from_spec(spec)
    spec.loader.exec_module(demo)

    page = Path("demo/index.html").read_text()
    endpoint, schema, trip = demo.read_page_contract(page)
    status, payload, headers = demo.post(accept["route"] + endpoint,
                                         demo.encode(schema, trip))
    minutes = float(payload["outputs"][0]["data"][0]) if status == 200 else float("nan")
    version = str(payload.get("model_version", "")) if status == 200 else ""
    lookups = headers.get("X-Taxi-Lookups", "")

    recorded = accept["quote"]["minutes"]
    if status == 200 and minutes == recorded:
        ok(f"the DEMO's own request path answered {minutes!r} minutes right now — equal to "
           f"the recorded {recorded!r} at the bar the accept was held to, |delta| = "
           f"{abs(minutes - recorded):.3e}. Endpoint, schema and payload all read out of the "
           f"committed page, posted with no Host override")
    else:
        no(f"the demo path returned HTTP {status} quoting {minutes!r} against the recorded "
           f"{recorded!r}")

    cfg = load_train_config()
    tracking.configure(cfg["mlflow"])
    reg = cfg["registry"]
    client = mlflow.MlflowClient()
    champion = client.get_model_version_by_alias(reg["model_name"], reg["champion_alias"])
    if version and version == str(champion.version):
        ok(f"and the version stamped on that answer is {version!r} — equal to what "
           f"{reg['champion_alias']!r} resolves to in the registry this second. The demo shows "
           f"the SERVING version because mlserver stamps it and the transformer forwards it, "
           f"not because a page was told a number")
    else:
        no(f"the demo's answer stamped {version!r} against alias -> {champion.version}")

    if lookups and lookups == accept["quote"]["lookups"]:
        ok(f"and X-Taxi-Lookups still reports every group INCLUDING the two that did not "
           f"cross the wall — identical to the recorded string, so the store was consulted "
           f"through THIS path and F-059's committed groups stayed committed")
    else:
        no(f"live lookup header {lookups!r} against recorded {accept['quote']['lookups']!r}")

    # QUESTION 2 — one rules read. The claim is not "the file contains three
    # rules" (§4 asked that) but "the SERVER loaded them, they are healthy, and
    # its sustains equal the file's" — the deploy_serving.sh idiom: never trust
    # the values you submitted.
    import yaml
    document = yaml.safe_load(Path("infra/monitoring/alerting_rules.yml").read_text())
    from taxi_mlops.monitoring import store_health
    file_rules = {r["alert"]: r for g in document["groups"] for r in g["rules"]
                  if "online_store" in r.get("expr", "")}
    p_port = 9099
    pf = subprocess.Popen(
        ["kubectl", "-n", "monitoring", "port-forward", "svc/prometheus-server", f"{p_port}:80"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        loaded = None
        for _ in range(40):
            try:
                url = f"http://127.0.0.1:{p_port}/api/v1/rules"
                with urllib.request.urlopen(url, timeout=10) as r:
                    loaded = json.loads(r.read())["data"]["groups"]
                break
            except Exception:  # noqa: BLE001, PERF203
                import time
                time.sleep(0.25)
        server = {r["name"]: r for g in (loaded or []) for r in g["rules"]
                  if r.get("type") == "alerting" and r["name"] in file_rules}
        unhealthy = {n: r.get("health") for n, r in server.items() if r.get("health") != "ok"}

        def seconds(spec: str) -> float:
            """`for: 2m` / `for: 10m` / `for: 30s` -> seconds, so the file's own
            spelling can be compared with the API's numeric `duration`."""
            return float(spec[:-1]) * (60 if spec.endswith("m") else 1)

        mismatched = {n: (server[n].get("duration"), file_rules[n]["for"])
                      for n in server
                      if abs(float(server[n].get("duration", -1))
                             - seconds(file_rules[n]["for"])) > 0.5}
        if len(server) == len(file_rules) and not unhealthy and not mismatched:
            states = ", ".join(f"{n}={server[n].get('state')}" for n in sorted(server))
            ok(f"PROMETHEUS has all {len(server)} online-store rule(s) LOADED with "
               f"health=ok and every `for:` equal to the file's ({states}) — read off the "
               f"server, never off the values that were submitted")
        else:
            no(f"loaded {len(server)} of {len(file_rules)}; unhealthy={unhealthy}; "
               f"sustain mismatches={mismatched}")
    finally:
        pf.terminate()
        pf.wait(timeout=10)

    # QUESTION 3 — DBSIZE, and the count it is checked against has THREE
    # WITNESSES, none of them typed here: the headroom record's per-view counts
    # (derived from data/feast/*.parquet), the M8-S4 materialization record, and
    # the live server. `keys < keys_expected` is only honest if the expected side
    # is derived from the store's sources rather than remembered.
    headroom = json.loads(Path("automation/runs/m9-store-watch/headroom.json").read_text())
    per_view = headroom["expected_keys"]["per_view"]
    total = headroom["expected_keys"]["total"]
    # `dbsize`, and the spelling matters: `.get("keys")` returns None on this
    # record, and a comparison against None that the code then treats as "no
    # expectation recorded" passes for every possible store — F-064, found by
    # this gate's own first run in `verify_m8.sh`'s identical clause.
    materialize = json.loads(Path("automation/runs/m8-online/materialize.json").read_text())
    mat_keys = materialize["store"]["dbsize"]
    raw = subprocess.run(
        ["kubectl", "-n", "feast", "exec", "deploy/redis", "--", "redis-cli", "DBSIZE"],
        capture_output=True, text=True, timeout=120).stdout.strip()
    dbsize = int(re.sub(r"\D", "", raw) or 0)

    if sum(per_view.values()) == total:
        ok(f"the expected key count RECONCILES with its own parts: "
           f"{' + '.join(f'{v:,}' for v in per_view.values())} = {total:,} across "
           f"{len(per_view)} view(s) — Feast writes one key per distinct entity key per view, "
           f"so this side of A-12b's comparison is derived from the sources and not chosen")
    else:
        no(f"the headroom record's per-view counts sum to {sum(per_view.values()):,} against "
           f"its own total of {total:,} — the expected side of A-12b does not reconcile, and "
           f"a short expectation is a store that can lose a whole view and still pass")

    if dbsize > 0 and dbsize == total == mat_keys:
        ok(f"and the ONLINE STORE holds {dbsize:,} keys right now — THREE WITNESSES agree "
           f"(the sources' derivation, the materialization record, the live server). An empty "
           f"store answers every lookup with null and nothing is red anywhere, because null is "
           f"ALSO the correct answer for TLC's two non-places — which is why the gate asks")
    else:
        no(f"the store holds {dbsize:,} keys against {total:,} derived and "
           f"{mat_keys if mat_keys is None else format(mat_keys, ',')} recorded — the three "
           f"witnesses disagree")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the live check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 6 "the live check"

# --------------------------------------------------------- 6. what S2/S3 shut -
section "6. the drill that was predicted first, and the two findings M9-S3 closed — derived, never enumerated"
consume < <(uv run python - 2>/dev/null <<'PY'
import ast
import json
import re
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    D = Path("automation/runs/m9-store-watch")
    records = {p.stem.split("-", 1)[1]: json.loads(p.read_text())
               for p in sorted(D.glob("drill-*.json"))}
    committed = json.loads((D / "prediction.json").read_text())
    # A PHASE's observations, asked for BY PHASE and never by filename. The drill
    # can legitimately be run one phase at a time (`--phase empty`, which is how
    # M9-S2 recorded it) or in one invocation (`--phase all`, the make target's
    # default) — the first writes `drill-empty.json`, the second writes
    # `drill-all.json` holding every phase's block. A gate keyed on the file name
    # goes RED for the DEFAULT invocation of the command it is checking, which is
    # gotcha #50's shape; what it actually wants is "what did the empty phase
    # observe?".
    phases = {name: block
              for record in records.values()
              for name, block in record.get("observed", {}).items()}

    # (a) The drill's verdict, summed across its phases from the records
    # themselves.
    checks = sum(len(r["checks"]) for r in records.values())
    failures = sum(int(r["failures"]) for r in records.values())
    if records and checks and not failures:
        detail = ", ".join(f"{k} {len(v['checks'])}/{len(v['checks'])}"
                           for k, v in sorted(records.items()))
        ok(f"the store-watch drill: {checks} check(s) across {len(phases)} phase(s) in "
           f"{len(records)} record(s), {failures} failure(s) — {detail}")
    else:
        no(f"the drill records report {failures} failure(s) across {checks} check(s)")

    # (b) The prediction each record was judged against must be FIELD-EQUAL to
    # the committed file. §3 proved it was committed first; a prediction can be
    # written first and then quietly edited into the record that judges it, so
    # both halves are necessary (the M6 gameday idiom).
    drifted = [k for k, v in records.items() if v.get("prediction") != committed]
    if records and not drifted:
        ok(f"and every phase record's embedded prediction is FIELD-EQUAL to the committed "
           f"{(D / 'prediction.json').name} — written first (§3) AND unedited since, which are "
           f"two different facts")
    else:
        no(f"phase(s) {drifted} carry a prediction that differs from the committed file")

    # (c) The load-bearing outcomes, read out of the record rather than out of
    # the write-up: both A-12 rules fired and REACHED ALERTMANAGER, the five
    # negatives held, the champion's own wire answered throughout, and the board
    # ends carrying the truth.
    empty = phases.get("empty", {})
    fired = empty.get("fired", {})
    reached = [a for a, v in fired.items() if v.get("fired") and v.get("reached_alertmanager")]
    negatives = empty.get("must_not_fire_states", {})
    inactive = [a for a, s in negatives.items() if s == "inactive"]
    predicted_neg = [n["alert"] for n in committed["empty_store"]["must_not_fire"]]
    if len(reached) >= 2 and sorted(inactive) == sorted(predicted_neg):
        when = ", ".join(f"{a} at T+{fired[a]['after_seconds']:.1f}s" for a in sorted(reached))
        ok(f"{len(reached)} rule(s) FIRED and reached Alertmanager ({when}) while all "
           f"{len(inactive)} must-not-fire negatives held inactive — the negatives are the "
           f"load-bearing half, and one of them (the absence rule) is the whole reason the "
           f"other rule exists")
    else:
        no(f"fired-and-reached={reached}; negatives predicted {sorted(predicted_neg)} and "
           f"observed inactive {sorted(inactive)}")

    keys_after = empty.get("keys_restored")
    rider = empty.get("rider_status_while_empty")
    predicted_status = committed["empty_store"]["rider_request"]["expected_status"]
    champ = empty.get("final_minutes")
    if keys_after and rider == predicted_status and champ:
        ok(f"the rider's request against an EMPTY store came back HTTP {rider} — the status "
           f"the prediction named, with every expectation this one number has SUPERSEDED "
           f"kept beside it rather than quietly replaced. The store was refilled to "
           f"{keys_after:,} keys and the board ends carrying the truth, not a silence")
    else:
        no(f"empty-store rider status {rider} against predicted {predicted_status}; keys "
           f"restored {keys_after}; final quote {champ}")

    # (c2) F-062's discriminator did not cost F-019 its guarantee. This is the
    # REGRESSION the change could have caused, so it is asserted in BOTH store
    # states from the records rather than argued from the code: a past-horizon
    # date is the CALLER's refusal while the store answers, and OURS when it does
    # not. Both predicted sides are read from the committed prediction, so the
    # leg carries no status literal of its own.
    unc = committed["empty_store"].get("uncovered_date_survives", {})
    healthy_seen = phases.get("health", {}).get("uncovered_status_when_healthy")
    empty_seen = empty.get("uncovered_status_while_empty")
    if (unc and healthy_seen == unc.get("expected_status_when_healthy")
            and empty_seen == unc.get("expected_status_while_empty")):
        ok(f"and F-019's typed refusal SURVIVED F-062: a past-horizon quote is HTTP "
           f"{healthy_seen} (the caller's) while the store answers and HTTP {empty_seen} "
           f"(ours) while it does not — measured in both states, because a change that "
           f"decides blame by asking a second question could have stopped refusing "
           f"altogether and every other check here would still be green")
    else:
        no(f"F-019's guarantee across the two store states: healthy {healthy_seen} vs "
           f"predicted {unc.get('expected_status_when_healthy')}; empty {empty_seen} vs "
           f"predicted {unc.get('expected_status_while_empty')}")

    # (d) THE ONLY WITNESS A HUMAN READS. Every number the write-up quotes about
    # the store and the drill is compared with the record it comes from — a
    # rewritten record must contradict something other than itself, and prose is
    # where a wrong number does its damage (verify-m5/-m6/-m7's rule, inherited).
    # Compared at the precision the DOCUMENT writes them at, with a one-decimal
    # floor for the timings (gotcha #90: rendering 13.75 as `14` matched almost
    # any document and let a planted value through).
    headroom = json.loads((D.parent / "m9-store-watch" / "headroom.json").read_text())
    prose = Path("docs/store_watchdog_m9.md").read_text()
    quoted = {
        f"{headroom['expected_keys']['total']:,}": "the store's expected key count",
        f"{headroom['expected_keys']['transformer_dependency_keys']:,}":
            "the transformer's whole dependency",
        f"{empty['refill_seconds']:.1f} s": "the refill",
    }
    for alert, obs in sorted(fired.items()):
        quoted[f"{obs['after_seconds']:.1f} s"] = f"{alert}'s time to fire"
    missing = {n: what for n, what in quoted.items() if n not in prose}
    if quoted and not missing:
        ok(f"and all {len(quoted)} number(s) docs/store_watchdog_m9.md quotes about the store "
           f"and the drill are the records' own ({', '.join(sorted(quoted))}) — the write-up is "
           f"the only witness a human reads, so a rewritten record has to contradict it too")
    else:
        no(f"the write-up quotes no record for: {missing} — either the prose drifted from the "
           f"records or a record was rewritten and the document was not")

    # (e) F-057's evidence is a NEGATIVE — the regeneration produced no diff, so
    # there is no commit to point at. What is checkable is the PROPERTY of the
    # file the regenerator now reproduces: every name PEP 503-normalised, and
    # the body sorted as LINES (the order a reviewer verifies with `sort -c`).
    PIN = Path("infra/feast/requirements-feast.txt")
    lines = [ln for ln in PIN.read_text().splitlines()
             if ln.strip() and not ln.lstrip().startswith("#")]
    def norm(n): return re.sub(r"[-_.]+", "-", n).lower()
    names = [ln.split("==")[0] for ln in lines]
    unnormalised = [n for n in names if n != norm(n)]
    if lines and not unnormalised and lines == sorted(lines):
        ok(f"F-057: all {len(lines)} pins carry PEP 503-normalised names and the body is "
           f"sorted AS LINES — the property the regenerator now reproduces byte-for-byte "
           f"against a file under review since M8-S2. The closure's evidence is that there "
           f"was NOTHING to commit, which is why this leg asserts the file and not a diff")
    else:
        no(f"the pin file is not what the regenerator emits: non-normalised {unnormalised[:4]}, "
           f"line-sorted={lines == sorted(lines)}")

    # (f) F-054, DERIVED across every test file. A leg naming the two known
    # offenders would go green the day a third grew one. Decorators only,
    # because this suite discusses the old form in prose (gotcha #99).
    #
    # AND SCOPED TO WHAT THE FINDING IS ABOUT, which cost this gate its first
    # run: "any skipif on a .exists()" flagged
    # test_feast_repo.py's skip on `.venv-feast/bin/python` — a GITIGNORED BUILD
    # ARTIFACT, absent in CI, where skipping is the correct behaviour and the
    # idiom this suite already uses for `ss`, `git`, `make` and `docker`. F-054
    # is about RECORDS: paths under automation/runs, which are TRACKED (F-029
    # option A), so their absence means deleted-or-lost and never
    # this-clone-lacks-artifacts. So the record constants are resolved per file
    # from their own assignments, and only a skip gated on one of THOSE counts
    # (gotcha #50: a guard that fires on correct behaviour teaches the next
    # session to edit assertions).
    guarded, marked, reads = [], [], []
    for path in sorted(Path("tests").rglob("test_*.py")):
        src = path.read_text()
        tree = ast.parse(src)
        record_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                rendered = ast.unparse(node.value)
                if "automation" in rendered and "runs" in rendered:
                    record_names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        if record_names:
            reads.append(path)
        for node in ast.walk(tree):
            for dec in getattr(node, "decorator_list", []):
                text = ast.unparse(dec)
                if "skipif" in text and ".exists()" in text and any(
                        n in text for n in record_names):
                    guarded.append(f"{path.name}::{node.name}")
        if "needs_records" in src:
            marked.append(path)
    if reads and not guarded:
        ok(f"F-054: ZERO `skipif(not RECORD.exists())` decorators remain under tests/ — asked "
           f"of the AST across {len(list(Path('tests').rglob('test_*.py')))} test file(s), "
           f"never enumerated. {len(reads)} file(s) read a tracked record and {len(marked)} "
           f"carry the `needs_records` marker, so an absent record is a loud assertion on the "
           f"host and a deselection in the ONE place F-047 allows")
    else:
        no(f"record reads are still guarded by a skip: {guarded[:4]}")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the closure check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 7 "the closure check"

# ------------------------------------ 7. the program's standing invariants ----
section "7. the standing invariants — the pointer, the lock, the pins, and the finding M9 did NOT fix"
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

    cfg = load_train_config()
    tracking.configure(cfg["mlflow"])
    reg = cfg["registry"]
    client = mlflow.MlflowClient()
    champion = client.get_model_version_by_alias(reg["model_name"], reg["champion_alias"])
    versions = sorted(client.search_model_versions(f"name='{reg['model_name']}'"),
                      key=lambda v: int(v.version))

    # (a) THE ALIAS LAW IN ITS STRONG FORM. "Is @champion still 2?" is
    # satisfiable by not looking. "Was any version created after the m7-closed
    # tag?" is not: a promotion must create a version, and a version carries its
    # own creation time.
    tag_time = int(subprocess.run(["git", "log", "--format=%ct", "-1", "m7-closed"],
                                  capture_output=True, text=True).stdout.strip() or 0)
    after = [v.version for v in versions if (v.creation_timestamp or 0) / 1000 > tag_time]
    if tag_time and not after:
        ok(f"NOT ONE of the {len(versions)} registry versions was created after the m7-closed "
           f"tag — the strong form of M9 law 3, across M8 and M9 both. "
           f"{reg['champion_alias']} resolves to version {champion.version}")
    else:
        no(f"version(s) created after m7-closed: {after} — something registered a model")

    train_cfg = yaml.safe_load(Path("configs/train.yaml").read_text())
    configured = train_cfg["features"]["version"]
    if champion.tags.get("feature_set") == configured:
        ok(f"and F-032's invariant holds live: the served version eats "
           f"{champion.tags['feature_set']!r}, which is what configs/train.yaml tells every "
           f"client to build — a half-finished rollback is a RED gate here rather than a 500 "
           f"nobody can attribute")
    else:
        no(f"version {champion.version} eats {champion.tags.get('feature_set')!r} while "
           f"clients build {configured!r}")

    # (b) The lock. M9 added a page, three rules and a reader, and the project's
    # dependency graph did not move — the demo is stdlib-and-a-template by
    # design (no JS framework, no build step, no new python package).
    tagged = subprocess.run(["git", "show", "m7-closed:uv.lock"], capture_output=True, text=True)
    if tagged.returncode == 0 and tagged.stdout == Path("uv.lock").read_text():
        ok("uv.lock is BYTE-IDENTICAL to the m7-closed tag — M8's five stories and M9's four, "
           "and the project's dependency graph has not moved since M7 closed")
    else:
        no("uv.lock DIFFERS from the m7-closed tag — `git diff m7-closed -- uv.lock` says what")

    # (c) The settled pins. DVC answers for every target in ONE summary line
    # when nothing moved and names each drifted target individually when
    # something did, so the property is that no target is REPORTED AS CHANGED.
    pins = sorted(str(p) for p in Path("data").glob("*.dvc"))
    dvc = subprocess.run(["uv", "run", "dvc", "status", *pins],
                         capture_output=True, text=True, timeout=300)
    clean = "up to date" in dvc.stdout and not re.search(
        r"changed (outs|deps)|modified:", dvc.stdout)
    if pins and clean:
        ok(f"all {len(pins)} settled DVC pins are up to date "
           f"({', '.join(Path(p).stem for p in pins)}) — M9 read no new month and wrote no "
           f"tree (law 2)")
    else:
        no(f"a settled pin has drifted:\n{dvc.stdout.strip()[:400]}")

    # (d) THE INHERITED GATES ARE SEPARATE LIVE TARGETS, NOT NESTED. Nesting
    # them would make one red predecessor render as a red M9 and would re-ask
    # every question they own; the boundary runs them itself, which is the
    # treatment verify-m7 gave M6's and verify-m8 gave M7's.
    makefile = Path("Makefile").read_text()
    inherited = [m for m in re.findall(r"^(verify-m[0-8]):", makefile, re.M)]
    me = Path("scripts/verify_m9.sh").read_text()
    code = "\n".join(ln for ln in me.splitlines() if not ln.lstrip().startswith("#"))
    nested = [t for t in inherited if re.search(rf"\bmake\s+{t}\b", code)]
    if len(inherited) >= 5 and not nested:
        ok(f"the {len(inherited)} inherited gates ({', '.join(inherited)}) are runnable as "
           f"their OWN live targets and this gate invokes none of them — a nested gate turns "
           f"one red predecessor into a red milestone and re-asks every question it owns")
    else:
        no(f"inherited targets found: {inherited}; nested by this gate: {nested}")

    # (e) THE FINDING M9 RAISED AND DID NOT FIX. A program that closes over a
    # row it quietly dropped is worse than one that closes with an open row, so
    # the gate requires F-062 to be OPEN, costed, and recommending something.
    findings = Path("ledgers/findings.md").read_text()
    row = next((ln for ln in findings.splitlines()
                if ln.startswith("| F-062 ")), "")
    costed = len(re.findall(r"\*\*\([abc]\)\*\*", row))
    if row and "OPEN" in row and costed >= 3 and "Recommendation" in row:
        ok(f"F-062 — a dead online store billed to the CALLER as a 4xx — is recorded OPEN with "
           f"{costed} costed options and a named recommendation, routed to the program close "
           f"because fixing it changes what a live boundary returns and M9 law 3 keeps the "
           f"wire still. The gate requires the row to be open rather than tidy")
    else:
        no(f"F-062's row is not an honest open row: present={bool(row)}, "
           f"costed options={costed}")

    # (f) The ledger. A cluster mutation with no row is a change nobody can
    # review. WHICH stories owe a row is DERIVED from their own records, and the
    # ledger is read ROW BY ROW — searching the whole document finds the
    # milestone's own prose naming other stories (gotcha #99, third occurrence
    # in this repo).
    MARKERS = ("pod", "pod_uid", "image", "isvc", "namespace", "keys_after_flush", "service")
    owes = set()
    for rec in sorted(Path("automation/runs").glob("m9-*/*.json")):
        try:
            blob = json.loads(rec.read_text())
        except json.JSONDecodeError:
            continue
        flat = json.dumps(blob)
        if any(f'"{m}"' in flat for m in MARKERS):
            owes.add({"m9-demo": "1", "m9-store-watch": "2"}.get(rec.parent.name, "?"))
    owes.discard("?")
    rows = {m for line in Path("ledgers/deployments.md").read_text().splitlines()
            if line.startswith("| 2026-")
            for m in re.findall(r"\*\*M9-S(\d)",
                                line.split("|")[2] if len(line.split("|")) > 2 else "")}
    if owes and rows >= owes:
        ok(f"the deployments ledger carries a row for every M9 story whose records describe a "
           f"cluster mutation (owes M9-S{', M9-S'.join(sorted(owes))}; present: "
           f"M9-S{', M9-S'.join(sorted(rows))}) — read row by row, because the milestone's own "
           f"prose names other stories")
    else:
        no(f"the deployments ledger owes M9-S{sorted(owes)} and carries M9-S{sorted(rows)}")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the invariant check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 7 "the invariant check"

# ------------------------------------------------------------------ verdict --
echo
if [[ "$FAILS" -eq 0 ]]; then
  printf '\033[32m[verify-m9] GREEN — every M9 sub-check passed.\033[0m\n'
  printf '            Show: the demo      http://localhost:8081/demo/  (demo/README.md)\n'
  printf '                  the accept    automation/runs/m9-demo/accept.json\n'
  printf '                  the watchdog  docs/store_watchdog_m9.md · slo_serving.md §9\n'
  # §9/M9's human box, DERIVED from the record §2 just judged rather than typed
  # here. A banner that hardcoded either state would be a second home for the
  # fact (F-013's shape in prose) and — in the OPEN direction — the one place a
  # skimmer would still be told the box was open after a human had closed it.
  python3 - <<'PY'
import json
from pathlib import Path
box = json.loads(Path("automation/runs/m9-demo/accept.json").read_text())["po_observed_run"]
if str(box.get("status", "")).upper().startswith("CLOSED"):
    print(f"            CLOSED BY A HUMAN, {box.get('closed_on')}: §9/M9's last accept line — one")
    print( "            non-technical person completing a query unassisted, OBSERVED — was closed")
    print(f"            by the PO and is cited at AWAITING_PO {box.get('cites')}, where their note")
    print( "            is quoted verbatim. No gate closed it; this one checks the citation.")
else:
    print("            OPEN BY DESIGN: §9/M9 asks for one non-technical person to complete a")
    print("            query unassisted, OBSERVED. No unattended session can close that box;")
    print("            it waits at AWAITING_PO and this gate only ever checks that it is")
    print("            recorded honestly.")
PY
  exit 0
fi
printf '\033[31m[verify-m9] RED — %d sub-check(s) failed.\033[0m\n' "$FAILS" >&2
exit 1
