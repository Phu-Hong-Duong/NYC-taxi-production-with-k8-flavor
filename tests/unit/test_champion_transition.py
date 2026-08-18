"""M3-S5: the champion transition's invariants — the ORDER, and the two refusals.

When the alias moves, four published artifacts instantly describe a model nobody
serves. `scripts/champion_transition.sh` is that repair, and the properties worth
pinning here are the ones a hurried edit would break without any test going red
on its own: the order of the chain, the fact that the promoting bake-off is not
run a second time once the alias already points at the winner, and that the
winner is READ from the measurement rather than typed into a shell script.

The expensive half (a real promotion, ~40 min of re-scoring and publishing)
belongs to the detached run; the transcript is its evidence.

Each test's docstring names the failure it prevents.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SHELL = REPO / "scripts" / "champion_transition.sh"
HELPER = REPO / "scripts" / "champion_transition_winner.py"
SCRIPT_TEXT = SHELL.read_text(encoding="utf-8")


def _helper():
    spec = importlib.util.spec_from_file_location("champion_transition_winner", HELPER)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


#: the six steps, as they are INVOKED — a command named inside an `echo` (the
#: DRY_RUN plan, a failure message) is prose about the chain and not the chain.
STEPS = (
    "make bakeoff BAKEOFF_ARGS=--promote-winner",
    "make predictions",
    "make duckdb",
    "make marts",
    "make boards",
    "uv run python scripts/error_memo_numbers.py",
)


def _invocation(command: str) -> int:
    """Offset of the line that actually RUNS `command` and aborts the chain if it fails."""
    import re

    match = re.search(rf"^\s*{re.escape(command)}\s*\|\|", SCRIPT_TEXT, re.MULTILINE)
    assert match is not None, f"{command!r} is never invoked with a failure branch"
    return match.start()


# ------------------------------------------------------------------ the order ---
def test_the_six_steps_appear_in_the_one_order_that_works():
    """A refresh out of order publishes the old model's rows under the new model's name.

    `predictions` must follow the alias move (it scores whatever `@champion`
    resolves to), `duckdb` must follow `predictions` (it reconciles their row
    counts), `marts` must follow `duckdb` (it sources those views) and `boards`
    must follow `marts` (it queries Postgres). Any transposition still exits 0 on
    every step and leaves a warehouse describing two different models.
    """
    positions = [_invocation(command) for command in STEPS]
    assert positions == sorted(positions), dict(zip(STEPS, positions, strict=True))


def test_every_step_aborts_the_chain_rather_than_carrying_on():
    """A failed `make marts` followed by a green `make boards` is the worst outcome.

    It renders cards over a mart that was never rebuilt, and every downstream
    check passes because each one is asking a different question. `_invocation`
    itself requires the `|| …` branch, so this test is that requirement applied
    to all six and stated in its own name.
    """
    for command in STEPS:
        _invocation(command)


# ------------------------------------------------------- the promotion, once ---
def test_the_promotion_is_skipped_when_the_alias_already_points_at_the_winner():
    """A second promoting bake-off overwrites the verdicts that were actually taken.

    `bakeoff_m3.py` re-reads the incumbent on every invocation, so re-running it
    after the alias has moved re-judges the four losing contenders against the NEW
    incumbent and rewrites `bakeoff.json`'s verdict column with verdicts nobody
    took. The row set's own drift guard does not catch it: it compares MAEs, which
    are unchanged, and not verdicts, which are not.
    """
    assert "--alias-run" in SCRIPT_TEXT
    guard = SCRIPT_TEXT[SCRIPT_TEXT.index('if [ "${ALIAS_RUN}"'):]
    assert guard.startswith('if [ "${ALIAS_RUN}" = "${WINNER_RUN}" ]')
    skipped, promoted = guard.index("SKIPPED"), guard.index("--promote-winner")
    assert skipped < promoted, "the skip branch must be the THEN branch, not the fallthrough"


def test_the_alias_moves_through_the_bake_off_and_this_script_names_no_registry_api():
    """One promotion path, and it is the one `make train` uses.

    `registry.promote` is where the incumbent acknowledgement and the no-delete
    property live (M2-S3, F-011). A shell script that reached for `set_alias`
    would walk around both while looking like the same action.
    """
    assert "make bakeoff BAKEOFF_ARGS=--promote-winner" in SCRIPT_TEXT
    for forbidden in ("set_registered_model_alias", "MlflowClient", "mlflow models",
                      "create_model_version"):
        assert forbidden not in SCRIPT_TEXT, forbidden


def test_a_non_promote_verdict_stops_the_chain_before_anything_is_published():
    """A refused winner means the alias does not move — and nothing is refreshed.

    Refreshing anyway would re-score the incumbent onto the same files, which is
    harmless, and print a transcript that looks exactly like a transition. The
    kickoff asks for the opposite: if the alias does not move, nothing is
    refreshed and that is stated.
    """
    refusal = SCRIPT_TEXT.index('if [ "${WINNER_VERDICT}" != "PROMOTE" ]')
    assert refusal < SCRIPT_TEXT.index("make predictions")
    assert refusal < SCRIPT_TEXT.index("--promote-winner")


def test_the_config_line_is_checked_before_the_alias_is_touched():
    """M3-S3's law, enforced twice on purpose.

    `bakeoff_m3.py` refuses to promote a winner `configs/train.yaml:
    features.version` does not describe. Checking it here too costs nothing and
    fails in one second instead of after the floor has been re-fitted.
    """
    check = SCRIPT_TEXT.index("CONFIGURED_SET")
    assert check < SCRIPT_TEXT.index("--promote-winner")


# ------------------------------------------------- the winner is READ, not typed ---
def test_no_run_id_is_typed_into_either_file():
    """A hardcoded run id is correct today and a silent lie after the next experiment."""
    import re

    for path in (SHELL, HELPER):
        text = path.read_text(encoding="utf-8")
        # MLflow run ids are 32 lowercase hex characters.
        assert not re.search(r"\b[0-9a-f]{32}\b", text), f"{path.name} names a run id"


def test_the_helper_reads_the_winner_row_out_of_the_measurement(tmp_path):
    """The four facts the transition needs are facts the bake-off produced."""
    mod = _helper()
    payload = {
        "winner": "auto-on-v2",
        "contenders": [
            {"label": "champion v1", "name": "lightgbm-v1", "run_id": "a" * 32,
             "feature_set": "v1", "verdict": "PROMOTE"},
            {"label": "auto-on-v2", "name": "auto-lgbm-v2", "run_id": "b" * 32,
             "feature_set": "v2", "verdict": "PROMOTE"},
        ],
    }
    path = tmp_path / "bakeoff.json"
    path.write_text(json.dumps(payload))
    assert mod.main([str(path)]) == 0


def test_the_helper_refuses_a_row_set_whose_winner_has_no_row(tmp_path, capsys):
    """A winner label with no matching row means the file was edited by hand."""
    mod = _helper()
    path = tmp_path / "bakeoff.json"
    path.write_text(json.dumps({"winner": "ghost", "contenders": []}))
    assert mod.main([str(path)]) == 2


def test_the_helper_emits_tab_separated_fields(tmp_path, capsys):
    """`read -r` on spaces would split the label 'champion v1' into two variables."""
    mod = _helper()
    path = tmp_path / "bakeoff.json"
    path.write_text(json.dumps({
        "winner": "champion v1",
        "contenders": [{"label": "champion v1", "name": "lightgbm-v1", "run_id": "c" * 32,
                        "feature_set": "v1", "verdict": "PROMOTE"}],
    }))
    mod.main([str(path)])
    out = capsys.readouterr().out.strip()
    assert out.split("\t") == ["champion v1", "lightgbm-v1", "c" * 32, "v1", "PROMOTE"]


# ------------------------------------------------------------------- the memo ---
def test_the_memo_section_is_printed_and_not_written():
    """Prose is a human's. The script's job is to make re-running the queries unnecessary.

    A script that generated the memo's paragraphs would produce a document nobody
    read, describing numbers nobody checked — the exact failure
    `scripts/error_memo_numbers.py` exists to prevent from the other direction.
    """
    tail = SCRIPT_TEXT[SCRIPT_TEXT.index("scripts/error_memo_numbers.py"):]
    assert "Still owed by a human" in tail
    assert "error_memo_m2.md" in tail
    assert "verify-m2" in tail
