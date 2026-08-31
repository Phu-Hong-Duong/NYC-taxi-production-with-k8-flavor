"""The M9 gate's own laws, pinned — and this is the last set.

`scripts/verify_m9.sh` is the ninth and final milestone gate. This file makes
the inherited rules falsifiable rather than asserted in the script's header:

* **it RE-RUNS NOTHING** — M9's evidence is a deployed page, a materialized
  store and a drill that included a REAL total outage of the transformer's
  dependency, so re-provoking any of it would cost an outage per verification;
  and re-running the demo's own accept would overwrite the record the gate
  exists to read;
* **its LIVE FOOTPRINT IS BOUNDED AND COUNTED** — three questions, stated in the
  header and counted here. Three and not M8's five deliberately: a gate that
  re-asks its predecessors' questions is not stricter, it is a gate whose live
  footprint grows every milestone;
* **it types no literal it could derive** (F-017, gotchas #49/#50) — no champion
  version, no key count, no zone id, no bar, no reader path, no test name;
* **no skip flag, no fast mode** — M1's rule, a NINTH inheritance;
* **and it may not render the PO-observed box green.** That box needs a human,
  and a gate that could close it would be the one dishonest artifact here.

The needles are about INVOCATIONS, not words: gotcha #68 (a ban on running
`make pipeline` caught the gate's own advice line) and gotcha #99 (three needles
matched the gate quoting itself) are both in this repo's record, and this gate
quotes several forbidden command names in prose that argues why it does not run
them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from conftest import without_comments

REPO = Path(__file__).resolve().parents[2]
GATE = REPO / "scripts" / "verify_m9.sh"
REDTEAM = REPO / "scripts" / "verify_m9_redteam.sh"


@pytest.fixture(scope="module")
def gate_text() -> str:
    return GATE.read_text()


@pytest.fixture(scope="module")
def gate_code(gate_text: str) -> str:
    """The gate with its comment lines stripped.

    Every check below that is about what the gate DOES must read this and not
    the raw text: the header argues at length about the commands it refuses to
    run, and half of those arguments name the command.
    """
    return without_comments(gate_text)


def test_the_gate_and_its_red_team_exist_and_are_wired() -> None:
    assert GATE.is_file(), "the M9 gate is missing"
    assert REDTEAM.is_file(), "the M9 gate has no red team — an unfalsifiable gate"
    makefile = (REPO / "Makefile").read_text()
    assert re.search(r"^verify-m9:", makefile, re.M), "no verify-m9 target"
    assert re.search(r"^verify-m9-redteam:", makefile, re.M), "no verify-m9-redteam target"
    assert "scripts/verify_m9.sh" in makefile
    assert "scripts/verify_m9_redteam.sh" in makefile


# --------------------------------------------------------------------------
# It re-runs nothing.
# --------------------------------------------------------------------------

#: Each entry is an INVOCATION shape, not a word. `make demo-accept` is banned;
#: the sentence "re-running the demo's own accept would overwrite the record" is
#: not — and the gate does import that script's helpers, which is a different
#: thing from running it.
FORBIDDEN_INVOCATIONS = [
    r"\bmake\s+demo-accept\b",
    r"\bmake\s+demo-page\b",
    r"\bmake\s+deploy-",
    r"\bmake\s+store-watch\b",
    r"\bmake\s+store-watch-drill\b",
    r"\bmake\s+store-watch-headroom\b",
    r"\bmake\s+feast-materialize\b",
    r"\bmake\s+feast-online-parity\b",
    r"\bmake\s+train\b",
    r"\bmake\s+retrain\b",
    r"\bdocker\s+build\b",
    r"\bkind\s+load\b",
    r"\bhelm\s+(?:install|upgrade)\b",
    r"\bkubectl\s+(?:apply|delete|create|patch|scale|annotate)\b",
    r"\bredis-cli\s+(?:FLUSHDB|FLUSHALL|DEL|SET)\b",
]


@pytest.mark.parametrize("pattern", FORBIDDEN_INVOCATIONS)
def test_the_gate_re_runs_nothing(gate_code: str, pattern: str) -> None:
    hits = re.findall(pattern, gate_code)
    assert not hits, (
        f"the M9 gate invokes {hits} — it must RE-RUN NOTHING. M9's evidence "
        f"includes a real total outage of the transformer's dependency; a gate "
        f"that re-provoked it would cost an outage per verification, and "
        f"re-running the accept would overwrite the record it exists to read."
    )


def test_the_gate_never_invokes_an_inherited_gate(gate_code: str) -> None:
    """The inherited-precondition treatment: run them, do not nest them.

    Nesting turns one red predecessor into a red milestone and re-asks every
    question that gate already owns — the reason this one asks three and not
    fourteen.
    """
    nested = re.findall(r"\bmake\s+verify-m[0-8]\b", gate_code)
    assert not nested, f"the M9 gate nests {nested} — the boundary runs those itself"


def test_the_gate_writes_no_record(gate_code: str) -> None:
    """A gate that wrote a record could be read by a later gate as evidence."""
    assert not re.search(r"write_text|json\.dump\(|>\s*automation/runs", gate_code), (
        "the M9 gate writes something — a gate's output is a verdict on the "
        "record, never another record"
    )


def test_the_gate_pushes_no_metric(gate_code: str) -> None:
    """M7-S5's rule, inherited: the pushgateway has no expiry.

    Anything the gate pushed would be read by A-9…A-13 as a real reader's
    output, forever — and A-12's freshness clause would then be satisfied by
    the gate itself rather than by anybody watching the store.
    """
    assert "push_metrics" not in gate_code
    assert not re.search(r"--push\b", gate_code)


# --------------------------------------------------------------------------
# Its live footprint is bounded, counted, and read-only.
# --------------------------------------------------------------------------

def test_the_live_questions_are_counted_and_the_count_is_stated(gate_text: str,
                                                               gate_code: str) -> None:
    """THREE questions, and the header must say so.

    The count is what makes the bound reviewable: a reader who sees the header
    claim three and the code make six has found something.
    """
    assert re.search(r"exactly THREE questions", gate_text), (
        "the gate's header no longer states how many questions it asks the live "
        "system — the bound is unreviewable"
    )
    # The three, each identified by the mechanism it uses rather than by a
    # comment: one POST built from the page's own contract, one rules read, one
    # DBSIZE.
    assert gate_code.count("demo.post(") == 1, (
        "the demo's request path is exercised more or less than once"
    )
    assert gate_code.count("/api/v1/rules") == 1, "more than one rules read"
    assert gate_code.count("DBSIZE") == 1, "the store is asked its size more than once"
    # And NOT its predecessors' questions: those belong to gates that run live
    # as their own evidence.
    assert "client_mod.infer(" not in gate_code, (
        "the M9 gate asks the champion's own wire — that is verify-m5's and "
        "verify-m8's question, and both run as their own targets"
    )
    assert "get-online-features" not in gate_code, (
        "the M9 gate queries the feature server directly — verify-m8's question"
    )
    assert "/api/v1/query" not in gate_code, (
        "the M9 gate runs a PromQL query — verify-m6/-m7/-m8's question"
    )


def test_the_gate_only_reads_the_cluster(gate_code: str) -> None:
    """`kubectl exec` is allowed for DBSIZE; mutation is not."""
    verbs = set(re.findall(r"\bkubectl\b[^\n\"']*?\b(apply|delete|create|patch|scale|"
                           r"annotate|rollout|edit|replace)\b", gate_code))
    assert not verbs, f"the gate calls mutating kubectl verbs: {sorted(verbs)}"


def test_the_gate_cannot_move_the_pointer(gate_code: str) -> None:
    """Law 3 applies to the gate itself, not only to what it checks."""
    for verb in ("set_registered_model_alias", "delete_registered_model_alias",
                 "create_model_version", "register_model", "log_model",
                 "delete_model_version"):
        assert f"{verb}(" not in gate_code, (
            f"the M9 gate calls {verb} — a gate that can move what it checks is "
            f"not a gate"
        )


def test_port_forwards_are_torn_down(gate_code: str) -> None:
    """Every forward the gate opens must die with it.

    A leaked forward outlives the gate and silently steals a port from the next
    reader — the reason `flyte_run_actions.py` got its own port at M4-S5, and
    the reason `store_watch.py` forwards on 6568/9100 rather than on any port a
    running drill owns.
    """
    opens = len(re.findall(r"port-forward", gate_code))
    closes = len(re.findall(r"\.terminate\(\)", gate_code))
    assert opens > 0, "the gate opens no forward — it cannot be reading Prometheus"
    assert closes >= opens, (
        f"{opens} port-forward(s) opened, {closes} terminated — a leaked forward "
        f"steals a port from the next reader"
    )


# --------------------------------------------------------------------------
# No skip flag; properties, not literals.
# --------------------------------------------------------------------------

def test_no_skip_flag(gate_code: str) -> None:
    """M1's rule, a NINTH and final inheritance: a gate with a fast mode runs in it."""
    for flag in ("SKIP_", "FAST", "QUICK", "--skip", "NO_LIVE"):
        assert flag not in gate_code, f"the M9 gate has a {flag} escape hatch"


def test_the_gate_types_no_champion_version_and_no_key_count(gate_code: str) -> None:
    """F-017. Every number the gate compares must come from two places.

    The key count is this milestone's version of the trap: 57,688 has three
    witnesses precisely so that nobody has to remember it, and a gate carrying
    it as a literal would be the fourth, unfalsifiable one.
    """
    assert not re.search(r"""version\s*==\s*['"]?2['"]?""", gate_code), (
        "the gate types the champion's version — it must read the alias"
    )
    assert "57688" not in gate_code and "57,688" not in gate_code, (
        "the gate types the store's key count — it must derive it from the "
        "sources, the materialization record and the live server"
    )
    assert "1800" not in gate_code, (
        "the gate types A-12's freshness clause — it must parse it out of the "
        "rules and look for it in the section that argues it"
    )
    assert "39.0019" not in gate_code, "the gate types the demo's published answer"


def test_the_gate_types_no_reader_path(gate_code: str) -> None:
    """The M8 gate went red on its own first run for typing a reader's filename.

    Both readers this gate inspects are derived from the Makefile recipe that
    runs them, so a legitimate rename cannot turn the milestone red.
    """
    # Asked as "the gate reads the Makefile and matches THIS recipe", which is
    # the derivation itself — not as "the string appears somewhere", which the
    # gate's own prose would satisfy (gotcha #99).
    for recipe in ("store-watch:", "demo-accept:"):
        derived = re.search(
            rf'Path\("Makefile"\)|Makefile.*?\^{re.escape(recipe)}', gate_code, re.S)
        assert derived and f"^{recipe}" in gate_code, (
            f"the gate no longer derives its reader from the `{recipe}` recipe — a "
            f"typed path is the defect the M8 gate's own first run found"
        )
    for typed in ("scripts/store_watch.py'", 'scripts/store_watch.py"',
                  "scripts/demo_accept.py'", 'scripts/demo_accept.py"'):
        assert typed not in gate_code, f"the gate types a reader's path ({typed})"


def test_every_python_leg_declares_a_verdict_floor(gate_text: str) -> None:
    """A leg that dies on import must FAIL, never contribute zero silent passes.

    M2-S5's rule. The floors are what turned this gate's own first run into
    three named defects instead of a short green run.
    """
    sections = len(re.findall(r"^section \"", gate_text, re.M))
    floors = len(re.findall(r"^expect_verdicts \d+", gate_text, re.M))
    assert sections >= 7, f"the gate has only {sections} sections"
    assert floors == sections, (
        f"{sections} section(s) but {floors} verdict floor(s) — a section with no "
        f"floor can die on import and report nothing"
    )


def test_consume_is_never_called_through_a_pipe(gate_text: str, gate_code: str) -> None:
    """`| consume` counts in a subshell and throws the tally away at the brace.

    Counted on the COMMENT-STRIPPED source: `consume()`'s own docstring comment
    tells the next author to call it this way, and counting the instruction as a
    call is gotcha #99 in a test again.
    """
    assert "| consume" not in gate_code
    assert gate_code.count("consume < <(") == len(
        re.findall(r"^section \"", gate_text, re.M)
    )


# --------------------------------------------------------------------------
# The box that must stay open.
# --------------------------------------------------------------------------

def test_the_gate_cannot_render_the_po_observed_box_green(gate_text: str,
                                                          gate_code: str) -> None:
    """§9/M9's last accept line needs a human, and the gate must say so.

    The failure mode this forbids is not a bug, it is a temptation: a gate that
    reported the milestone complete would be describing an observation nobody
    made. The PO made it on 2026-08-24, so the box is now legitimately CLOSED —
    and the assertion is re-derived to the property that holds in BOTH states
    rather than widened to admit the new one (gotcha #50, which is exactly the
    move this test exists to make somebody argue for).

    The gate must therefore (a) accept OPEN only with the live invitation in the
    inbox, (b) accept CLOSED only WITH A CITATION the inbox really holds — a
    CLOSED status the gate takes on trust is the same dishonest artifact as a
    gate that closed the box itself — and (c) print the box's state in its own
    output including the GREEN banner, DERIVED from the record rather than typed
    there, so a skimmer is never told the opposite of what §2 just judged.
    """
    assert 'startswith("OPEN")' in gate_code and 'startswith("CLOSED")' in gate_code, (
        "the gate does not judge the PO-observed box in both of its honest "
        "states — one of them is being taken on trust"
    )
    for needle, why in (
        ('box.get("cites"', "a CLOSED box must name the AWAITING_PO entry that closed it"),
        ('f"## {cites}" in awaiting',
         "the gate does not check that the cited entry EXISTS — a claim that an "
         "entry exists is not the entry"),
        ('box.get("po_note"',
         "the gate does not require the observer's own words, so a CLOSED status "
         "could cite an entry that says nothing about the box"),
    ):
        assert needle in gate_code, f"{why} (missing: {needle})"
    assert "OPEN ITEM" in gate_code and "CLOSED BY A HUMAN" in gate_code, (
        "the gate does not print the PO-observed box's state in its own output"
    )
    banner = gate_text.split("GREEN — every M9 sub-check passed")[-1]
    assert "OPEN BY DESIGN" in banner and "CLOSED BY A HUMAN" in banner, (
        "the GREEN banner does not name the box in both states — a reader who "
        "skims the verdict must see which one holds"
    )
    assert 'accept.json").read_text())["po_observed_run"]' in banner, (
        "the GREEN banner types the box's state instead of deriving it from the "
        "record §2 just judged — a second home for the one fact this gate is "
        "chartered never to assert on its own authority"
    )
    assert "AWAITING_PO" in gate_code, (
        "the gate does not check that the invitation to the observed run exists"
    )


def test_a_closed_box_without_a_citation_is_red(gate_code: str) -> None:
    """The one edit this box will ever tempt somebody into.

    Flipping a status is one keystroke and reads as housekeeping. What makes it
    honest is the citation, so the gate's failure path must be able to SAY that
    — not merely fall through a boolean. Demonstrated live once in M9-S5 (a
    citation-free CLOSED took the gate RED naming the missing citation, with the
    other 44 sub-checks still passing) and pinned here.
    """
    assert 'why.append("it is CLOSED and cites no AWAITING_PO entry")' in gate_code, (
        "a CLOSED box with no citation does not produce a message saying so"
    )
    assert "an entry this inbox does not hold" in gate_code, (
        "a CLOSED box citing an entry that does not exist does not produce a "
        "message saying so"
    )
    assert 'why.append("the note it quotes appears nowhere in AWAITING_PO")' in gate_code, (
        "a CLOSED box quoting a note the inbox never carried does not produce a "
        "message saying so — a paraphrase of a human is not that human's word"
    )


def test_the_citation_check_reads_words_and_not_wrapping(gate_code: str) -> None:
    """AWAITING_PO is markdown, and a quoted note is wrapped inside a blockquote.

    Asked as a naive substring the citation leg goes RED on a perfectly honest
    record — which is gotcha #50 arriving inside the check written to stop this
    box being rounded up. It was observed doing exactly that on M9-S5's first
    run. Both sides are flattened before comparison; the claim under test is
    that the inbox holds these WORDS, never that it holds these bytes.
    """
    assert 'lstrip("> ")' in gate_code and 're.sub(r"\\s+", " "' in gate_code, (
        "the citation leg compares raw bytes, so it will refuse any note the "
        "inbox wrapped or quoted — the honest record fails and the check teaches "
        "the next author to delete it"
    )


# --------------------------------------------------------------------------
# The red team.
# --------------------------------------------------------------------------

def test_the_red_team_restores_under_a_trap_and_verifies_by_sha() -> None:
    text = REDTEAM.read_text()
    assert "trap restore EXIT" in text, "the red team can leave a tampered record behind"
    assert "sha256sum" in text, "the restore is assumed rather than verified"
    assert re.search(r"git status --porcelain", text), (
        "the red team does not assert a clean tree — the property F-029 bought"
    )


def test_the_red_team_chooses_its_target_from_the_record() -> None:
    """A typed view name stops being an argument about the property."""
    text = REDTEAM.read_text()
    assert 'min(expected["per_view"].items()' in text, (
        "the red team types its target view instead of deriving it from the record"
    )
    code = "\n".join(line for line in text.splitlines()
                     if not line.lstrip().startswith("#"))
    assert "zone_static" not in code, (
        "the red team names its target view in code — the plant must be chosen "
        "from the record so it stays an argument about the property"
    )


def test_the_red_team_asserts_legs_that_must_stay_green() -> None:
    """What separates a gate that fails on a WRONG number from a checksum."""
    text = REDTEAM.read_text()
    assert "STILL GREEN" in text, (
        "the red team does not assert that an unaffected leg survives — it cannot "
        "distinguish a gate that catches a wrong value from one that catches any edit"
    )
    assert "still green:" in text, "the red team checks no unaffected legs by name"


def test_the_red_team_touches_exactly_one_tracked_record() -> None:
    text = "\n".join(line for line in REDTEAM.read_text().splitlines()
                     if not line.lstrip().startswith("#"))
    records = set(re.findall(r"automation/runs/\S+\.json", text))
    assert records == {"automation/runs/m9-store-watch/headroom.json"}, (
        f"the red team touches {sorted(records)} — its footprint must be one file"
    )
    for verb in ("kubectl", "helm", "docker", "kind ", "redis-cli"):
        assert verb not in text, f"the red team invokes {verb} — it must touch no cluster state"
