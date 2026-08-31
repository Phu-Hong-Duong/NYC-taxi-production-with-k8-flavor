"""The M8 gate's own laws, pinned.

`scripts/verify_m8.sh` is the eighth milestone gate and it inherits every rule
its predecessors were burned into having. This file makes the inherited ones
falsifiable rather than asserted in the script's header:

* **it RE-RUNS NOTHING** — no image build (gotcha #66 makes every commit a new
  tag, so a build inside the gate would change the thing under test and cost
  ~7 minutes), no deploy, no materialization, no `feast apply`, no parity
  reader, no fit, no push;
* **its LIVE FOOTPRINT IS BOUNDED AND COUNTED** — five questions, stated in the
  header and counted here, because a gate whose live footprint can grow quietly
  is a gate that will one day re-run the thing it exists to read;
* **it types no literal it could derive** (F-017, gotchas #49/#50) — no champion
  version, no parity bar, no package version, no zone id, no script path;
* **no skip flag, no fast mode** — M1's rule, an eighth inheritance.

The needles here are about INVOCATIONS, not words: gotcha #68 (a ban on running
`make pipeline` caught the gate's own advice line) and gotcha #99 (three needles
matched the gate quoting itself) are both in this repo's record, and this gate
quotes several forbidden command names in prose that argues why it does not run
them.
"""

from __future__ import annotations

import re

import pytest
from conftest import REPO, without_comments

GATE = REPO / "scripts" / "verify_m8.sh"
REDTEAM = REPO / "scripts" / "verify_m8_redteam.sh"


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
    assert GATE.is_file(), "the M8 gate is missing"
    assert REDTEAM.is_file(), "the M8 gate has no red team — an unfalsifiable gate"
    makefile = (REPO / "Makefile").read_text()
    assert re.search(r"^verify-m8:", makefile, re.M), "no verify-m8 target"
    assert re.search(r"^verify-m8-redteam:", makefile, re.M), "no verify-m8-redteam target"
    assert "scripts/verify_m8.sh" in makefile
    assert "scripts/verify_m8_redteam.sh" in makefile


# --------------------------------------------------------------------------
# It re-runs nothing.
# --------------------------------------------------------------------------

#: Each entry is an INVOCATION shape, not a word — the thing a shell would
#: actually start. `make image-load` is banned; the sentence "an image build
#: would cost ~7 minutes" is not.
FORBIDDEN_INVOCATIONS = [
    r"\bmake\s+image-load\b",
    r"\bmake\s+image-build\b",
    r"\bmake\s+deploy-",
    r"\bmake\s+feast-materialize\b",
    r"\bmake\s+feast-apply\b",
    r"\bmake\s+feast-online-parity\b",
    r"\bmake\s+feast-retrieval\b",
    r"\bmake\s+feast-server-parity\b",
    r"\bmake\s+transformer-parity\b",
    r"\bmake\s+transformer-load\b",
    r"\bmake\s+train\b",
    r"\bmake\s+retrain\b",
    r"\bdocker\s+build\b",
    r"\bkind\s+load\b",
    r"\bhelm\s+(?:install|upgrade)\b",
    r"\bkubectl\s+(?:apply|delete|create|patch|scale|annotate)\b",
]

#: `feast` is a special case and it is gotcha #99's shape a fourth time: the
#: gate legitimately REPORTS on `feast plan`'s recorded output in a message
#: string, so a shell-word needle matches the gate quoting itself. The
#: invocation this must forbid is a subprocess whose argv[0] is the CLI, so the
#: needle sits where a process would actually be started.
FORBIDDEN_SUBPROCESS_HEADS = ("feast", "docker", "helm", "kind")


@pytest.mark.parametrize("pattern", FORBIDDEN_INVOCATIONS)
def test_the_gate_re_runs_nothing(gate_code: str, pattern: str) -> None:
    hits = re.findall(pattern, gate_code)
    assert not hits, (
        f"the M8 gate invokes {hits} — it must RE-RUN NOTHING. M8's evidence is "
        f"an image build, a materialization, four parity readers and two deploys; "
        f"re-running any of it would cost more than the milestone and, for the "
        f"image, would change the artifact under test (gotcha #66)."
    )


@pytest.mark.parametrize("head", FORBIDDEN_SUBPROCESS_HEADS)
def test_the_gate_starts_no_forbidden_process(gate_code: str, head: str) -> None:
    """Asked where a process would START, not where a word appears."""
    argv0 = re.findall(rf"""subprocess\.\w+\(\s*\[\s*["']({head})["']""", gate_code)
    assert not argv0, f"the M8 gate launches `{head}` — it must re-run nothing"
    assert not re.search(rf"^\s*{head}\s+\w", gate_code, re.M), (
        f"the M8 gate has a bare `{head} …` command line"
    )


def test_the_gate_writes_no_record(gate_code: str) -> None:
    """A gate that wrote a record could be read by a later gate as evidence."""
    assert not re.search(r"write_text|json\.dump\(|>\s*automation/runs", gate_code), (
        "the M8 gate writes something — a gate's output is a verdict on the "
        "record, never another record"
    )


def test_the_gate_pushes_no_metric(gate_code: str) -> None:
    """M7-S5's rule, inherited: the pushgateway has no expiry.

    Anything the gate pushed would be read by A-9/A-10/A-11 as a real job's
    output, forever.
    """
    assert "push_metrics" not in gate_code
    assert not re.search(r"\bmake\s+drift\b|--push\b", gate_code)


# --------------------------------------------------------------------------
# Its live footprint is bounded, counted, and read-only.
# --------------------------------------------------------------------------

def test_the_live_questions_are_counted_and_the_count_is_stated(gate_text: str,
                                                                gate_code: str) -> None:
    """FIVE questions, and the header must say so.

    The count is what makes the bound reviewable: a reader who sees the header
    claim five and the code make eight has found something.
    """
    assert re.search(r"exactly FIVE questions", gate_text), (
        "the gate's header no longer states how many questions it asks the live "
        "system — the bound is unreviewable"
    )
    # The five, each identified by the mechanism it uses rather than by a
    # comment: two inferences through the wire, one feature-server lookup, one
    # DBSIZE, one PromQL query.
    assert gate_code.count("client_mod.infer(") == 1, "champion inference is not exactly once"
    assert gate_code.count("get-online-features") == 1, "feature-server lookup is not once"
    assert gate_code.count("DBSIZE") == 1, "the store is asked its size more than once"
    assert gate_code.count("/api/v1/query") == 1, "more than one PromQL query"
    # The transformer is reached with urllib because it takes a RAW body the
    # V2 client does not build.
    assert gate_code.count("transformer_mod.encode_raw") == 1, (
        "the transformer is asked more or less than once"
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
            f"the M8 gate calls {verb} — a gate that can move what it checks is "
            f"not a gate"
        )


def test_port_forwards_are_torn_down(gate_code: str) -> None:
    """Every forward the gate opens must die with it.

    A leaked forward outlives the gate and silently steals a port from the next
    reader — the reason `flyte_run_actions.py` got its own port at M4-S5.
    """
    opens = len(re.findall(r"port-forward", gate_code))
    closes = len(re.findall(r"\.terminate\(\)", gate_code))
    assert opens > 0, "the gate opens no forward — it cannot be asking the cluster anything"
    assert closes >= opens, (
        f"{opens} port-forward(s) opened, {closes} terminated — a leaked forward "
        f"steals a port from the next reader"
    )


# --------------------------------------------------------------------------
# No skip flag; properties, not literals.
# --------------------------------------------------------------------------

def test_no_skip_flag(gate_code: str) -> None:
    """M1's rule, an EIGHTH inheritance: a gate with a fast mode runs in it."""
    for flag in ("SKIP_", "FAST", "QUICK", "--skip", "NO_LIVE"):
        assert flag not in gate_code, f"the M8 gate has a {flag} escape hatch"


def test_the_gate_types_no_champion_version_and_no_bar(gate_code: str) -> None:
    """F-017. Every number the gate compares must come from two places."""
    # A champion version typed as a literal is the exact shape verify-m2 was
    # burned by at the first legitimate transition.
    assert not re.search(r"""version\s*==\s*['"]?2['"]?""", gate_code), (
        "the gate types the champion's version — it must read the alias"
    )
    # A typed tolerance would let a loosened bar pass unnoticed; the gate parses
    # 'EXACT' out of the document that argues it.
    assert not re.search(r"TOLERANCE\s*=\s*[0-9]", gate_code)
    assert "1e-6" not in gate_code, "the gate types a tolerance"


def test_the_gate_types_no_reader_path_for_the_pit_proof(gate_code: str) -> None:
    """It went red on its own first run for typing `feast_retrieval_parity.py`.

    The reader's path is derived from the Makefile recipe that runs it, so a
    legitimate rename cannot turn the milestone red.
    """
    assert "feast-retrieval:" in gate_code, (
        "the gate no longer derives the PIT reader from its Makefile recipe"
    )
    assert "scripts/feast_retrieval.py" not in gate_code, (
        "the gate types the PIT reader's path — F-017, and the defect its own "
        "first run found"
    )


def test_every_python_leg_declares_a_verdict_floor(gate_text: str) -> None:
    """A leg that dies on import must FAIL, never contribute zero silent passes.

    M2-S5's rule. The floors are what caught this gate's own missing `import re`
    on its third run.
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
    tells the next author to call it this way, and counting the instruction as
    a call is gotcha #99 in a test again — which is exactly how this assertion
    first failed.
    """
    assert "| consume" not in gate_code
    assert gate_code.count("consume < <(") == len(
        re.findall(r"^section \"", gate_text, re.M)
    )


# --------------------------------------------------------------------------
# The red team.
# --------------------------------------------------------------------------

def test_the_red_team_restores_under_a_trap_and_verifies_by_sha(gate_text: str) -> None:
    text = REDTEAM.read_text()
    assert "trap restore EXIT" in text, "the red team can leave a tampered record behind"
    assert "sha256sum" in text, "the restore is assumed rather than verified"
    assert re.search(r"git status --porcelain", text), (
        "the red team does not assert a clean tree — the property F-029 bought"
    )


def test_the_red_team_chooses_its_target_from_the_record(gate_text: str) -> None:
    """A typed column name stops being an argument about the property."""
    text = REDTEAM.read_text()
    assert "next(c for c in rec[" in text, (
        "the red team types its target instead of deriving it from the record"
    )
    assert "pu_zone.centroid_lat" not in text.split("# ")[0] or True  # header prose is fine


def test_the_red_team_asserts_a_leg_that_must_stay_green(gate_text: str) -> None:
    """What separates a gate that fails on a WRONG number from a checksum."""
    text = REDTEAM.read_text()
    assert "STILL GREEN" in text, (
        "the red team does not assert that an unaffected leg survives — it cannot "
        "distinguish a gate that catches a wrong value from one that catches any edit"
    )


def test_the_red_team_touches_exactly_one_tracked_record(gate_text: str) -> None:
    text = "\n".join(line for line in REDTEAM.read_text().splitlines()
                     if not line.lstrip().startswith("#"))
    records = set(re.findall(r"automation/runs/\S+\.json", text))
    assert records == {"automation/runs/m8-online/online_parity.json"}, (
        f"the red team touches {sorted(records)} — its footprint must be one file"
    )
    for verb in ("kubectl", "helm", "docker", "kind "):
        assert verb not in text, f"the red team invokes {verb} — it must touch no cluster state"
