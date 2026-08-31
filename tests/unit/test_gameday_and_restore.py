"""M6-S5 — the gameday harness, the restore rehearsal, and the prose that quotes them.

The three families this program's suites have used since M6-S3, for the same
reasons:

1. STRUCTURAL, parsed with `ast` and never grepped. Both scripts argue their own
   hazards at length — the gameday's module docstring names every alert it does
   NOT expect to fire, and the restore drill spends a paragraph on what it
   refuses to claim — so a word search matches the argument as readily as the
   deed (#53/#68).
2. DERIVED ON BOTH SIDES. Nothing that is a fact about today (an alert id, a
   measured share, a row count) is typed into an assertion; the record and the
   code, or the record and the rules file, are compared with each other (F-017,
   #49/#50).
3. PROSE AGAINST RECORDS. Every number `docs/gameday_m6.md` quotes must exist in
   the record it cites — the M5-S5 shape.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
import yaml
from conftest import REPO, called_names

GAMEDAY = REPO / "scripts/gameday_m6.py"
RESTORE = REPO / "scripts/restore_rehearsal.py"
RULES = REPO / "infra/monitoring/alerting_rules.yml"
BACKUP = REPO / "scripts/platform_backup.sh"
DOC = REPO / "docs/gameday_m6.md"
RECORD_DIR = REPO / "automation" / "runs" / "m6-gameday"
RESTORE_RECORD = REPO / "automation/runs/m6-restore/restore_drill.json"


def _module(path: Path) -> ast.Module:
    return ast.parse(path.read_text())


def _string_args(path: Path, call_name: str) -> list[list[str]]:
    out: list[list[str]] = []
    for node in ast.walk(_module(path)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        if name != call_name:
            continue
        out.append([a.value for a in node.args if isinstance(a, ast.Constant)])
    return out


def _assign(path: Path, name: str) -> ast.expr | None:
    for node in _module(path).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return node.value
        if isinstance(node, ast.AnnAssign) and (
            isinstance(node.target, ast.Name) and node.target.id == name
        ):
            return node.value
    return None


def _gameday_module():
    """Import the script itself for the values that are not literals.

    `PREDICTIONS` interpolates the drill's own rate and window constants, so it
    cannot be `literal_eval`ed — and typing the numbers into this file instead
    would be exactly the twin F-017 forbids. The module imports nothing outside
    the standard library at import time (every `taxi_mlops` import is inside a
    function body, deliberately, so the drill can run on a broken cluster).
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("_gameday_m6", GAMEDAY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rules() -> dict[str, dict]:
    payload = yaml.safe_load(RULES.read_text())
    return {rule["alert"]: rule for group in payload["groups"] for rule in group["rules"]}


# --- the alert ids the gameday watches are the ones that exist ----------------


def test_every_watched_alert_is_a_rule_that_exists():
    """WATCHED is a map into the rules file, and it must not drift out of it.

    A gameday whose watch list names an alert nobody ships would report "it did
    not fire" forever, which is the single most comfortable way for this whole
    exercise to become a formality.
    """
    watched = ast.literal_eval(_assign(GAMEDAY, "WATCHED"))

    # NO PHANTOMS: everything watched must actually ship.
    assert set(watched) <= set(_rules()), (
        "scripts/gameday_m6.py watches "
        f"{sorted(set(watched) - set(_rules()))}, which the rules file does not ship — "
        "a watch list naming an alert nobody ships reports 'it did not fire' forever"
    )

    # NO GAPS, scoped to what this gameday can actually provoke. M7-S3 added a
    # `crosstown-drift` group whose signals come from a BATCH job pushing to a
    # gateway; the gameday's four scenarios (control, kill, storage, saturation)
    # touch the wire and cannot move a drift metric, so demanding it watch them
    # would force a session to pad a watch list with entries nobody reasoned
    # about. The group name is what separates them, DERIVED from the file rather
    # than typed here (F-017's both-sides rule).
    payload = yaml.safe_load(RULES.read_text())
    serving = {
        rule["alert"]
        for group in payload["groups"]
        if group["name"] == "crosstown-serving"
        for rule in group["rules"]
    }
    assert serving <= set(watched), (
        f"the gameday stopped watching {sorted(serving - set(watched))}, which are serving "
        "rules its scenarios can provoke. Drift rules are exercised by "
        "scripts/drift_fire_drill.py instead."
    )


def test_watched_signal_ids_match_the_rules_own_labels():
    watched = ast.literal_eval(_assign(GAMEDAY, "WATCHED"))
    for alert, signal in watched.items():
        assert _rules()[alert]["labels"]["signal"] == signal


def test_every_prediction_names_only_alerts_that_exist():
    predictions = _gameday_module().PREDICTIONS
    known = set(_rules())
    for name, entry in predictions.items():
        named = set(entry.get("must_fire", [])) | set(entry.get("must_not_fire", []))
        named |= set(entry.get("unpredictable", []))
        assert named <= known, (
            f"{name} names an alert that is not in the rules file: {named - known}"
        )


def test_every_scenario_predicts_what_must_not_fire():
    """A prediction that only says what fires cannot be wrong about a signature.

    Distinguishability is the property §9/M6 grades, and it is a claim about the
    alerts that stay quiet as much as the ones that do not.
    """
    predictions = _gameday_module().PREDICTIONS
    for name, entry in predictions.items():
        assert entry["must_not_fire"], f"{name} predicts nothing about what must stay inactive"
        assert entry["why"].strip(), f"{name} has no derivation"


# --- the gameday never promotes, never rebuilds, never scales -----------------


def test_the_gameday_never_writes_the_alias_or_mints_a_version():
    """M6 law 3, made structural. The drill reads @champion and compares."""
    source = GAMEDAY.read_text()
    tree = ast.parse(source)
    forbidden = {
        "set_registered_model_alias",
        "delete_registered_model_alias",
        "create_model_version",
        "transition_model_version_stage",
        "promote",
    }
    called = called_names(GAMEDAY)
    assert not (called & forbidden), f"the gameday can mutate the registry: {called & forbidden}"
    assert isinstance(tree, ast.Module)


@pytest.mark.parametrize("verb", ["scale", "destroy", "delete"])
def test_the_gameday_only_deletes_pods(verb: str):
    """`kubectl delete` appears, and it may only ever name a pod.

    A gameday that could delete a Deployment, an InferenceService or a namespace
    is one bad argument away from being an outage nobody rehearsed the undo for.
    """
    for args in _string_args(GAMEDAY, "kubectl"):
        if verb in args:
            assert verb == "delete" and "pod" in args, f"kubectl {verb} {args} is out of scope"


def test_the_secret_undo_is_staged_before_the_injection():
    """The capture must lexically precede the patch inside the storage scenario.

    The M2 red-team rule: a drill with no rehearsed undo is a gamble. Checked by
    line order rather than by reading the comment that says so.
    """
    source = GAMEDAY.read_text().splitlines()
    body_start = next(i for i, line in enumerate(source) if "def scenario_storage" in line)
    body = source[body_start:]
    capture = next(i for i, line in enumerate(body) if "backup_path.write_text" in line)
    patch = next(i for i, line in enumerate(body) if '"patch",' in line)
    assert capture < patch, "the storage scenario injects before it stages its undo"


def test_the_captured_secret_never_lands_in_the_repository():
    """A credential must not be one `git add -f` away from a commit."""
    source = GAMEDAY.read_text()
    assert "tempfile.gettempdir()" in source
    assert 'RECORD_DIR / "storage-secret-undo' not in source


# --- the restore drill claims what it can and refuses the rest ----------------


def test_the_restore_drill_never_writes_a_live_database():
    """Every restore target is a scratch name, and the suffix is one constant."""
    suffix = ast.literal_eval(_assign(RESTORE, "SCRATCH_SUFFIX"))
    source = RESTORE.read_text()
    assert suffix.startswith("_")
    # The only CREATE/DROP DATABASE statements in the file must interpolate the
    # scratch suffix — a bare f-string over `name` would drop a live database.
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.JoinedStr):
            continue
        rendered = "".join(part.value for part in node.values if isinstance(part, ast.Constant))
        if "DROP DATABASE" in rendered or "CREATE DATABASE" in rendered:
            assert "SCRATCH_SUFFIX" in ast.unparse(node) or "scratch" in ast.unparse(node), (
                f"a DDL statement that may not be scoped to scratch: {ast.unparse(node)}"
            )


def test_marts_is_excluded_from_the_restore_targets():
    """1.2 GiB of the 1.6 GiB backup, and the one database DVC already covers."""
    targets = ast.literal_eval(_assign(RESTORE, "TARGETS"))
    assert "marts" not in targets
    assert set(targets) == {"mlflow", "optuna", "metabase"}


def test_the_restore_drill_checks_against_the_repo_and_not_only_against_live():
    """The second witness is what makes the first one worth having.

    Live-vs-restored agreement is also what restoring the wrong backup into the
    wrong place would show. The repo-derived expectations come from tracked
    artifacts, and this test asserts those artifacts are the source.
    """
    source = RESTORE.read_text()
    assert "analytics" in source and "boards" in source
    assert "m3s4" in source and "sniper-" in source


@pytest.mark.needs_records
def test_the_restore_drill_records_what_it_refuses_to_claim():
    record = json.loads(RESTORE_RECORD.read_text())
    assert "dead platform" in record["what_this_does_not_claim"].lower()
    assert record["verdict"] == "GREEN"


def test_the_backup_artifacts_no_longer_say_simply_not_rehearsed():
    """The label moved ONE notch, and both halves must be present everywhere.

    A file that says only "scratch-rehearsed" has overstated the drill; a file
    that still says only "NOT REHEARSED" has not read it.
    """
    text = BACKUP.read_text()
    assert "SCRATCH-REHEARSED" in text.upper()
    assert "STILL NOT" in text.upper() or "still not" in text


@pytest.mark.needs_records
def test_the_restore_record_and_the_doc_agree_on_every_quoted_number():
    """Prose against records — the M5-S5 shape.

    Each duration the gameday document quotes for the restore must be the one the
    record holds, at the precision the document sensibly writes it (#76).
    """
    record = json.loads(RESTORE_RECORD.read_text())
    doc = DOC.read_text()
    for name, entry in record["databases"].items():
        seconds = f"{entry['restore_seconds']:.2f} s"
        assert seconds in doc, f"the doc does not quote {name}'s measured {seconds}"
    minio = record["minio"]
    assert str(minio["objects_restored"]) in doc
    assert f"{minio['bytes_restored']:,}" in doc


# --- the gameday's own records ------------------------------------------------


@pytest.mark.needs_records
def test_the_predictions_were_written_before_any_injection():
    payload = json.loads((RECORD_DIR / "predictions.json").read_text())
    assert payload["written_before_any_injection"] is True
    assert payload["scenario_order"][0] == "control"
    assert payload["positive_control_first"] is True


@pytest.mark.needs_records
def test_the_predictions_on_disk_are_the_ones_in_the_code():
    """A prediction file edited after the fact is the failure mode this guards.

    The committed file must still be what `PREDICTIONS` renders — so amending a
    prediction to match an outcome shows up as a red test, not as a diff nobody
    reads.
    """
    payload = json.loads((RECORD_DIR / "predictions.json").read_text())
    assert payload["predictions"] == _gameday_module().PREDICTIONS
