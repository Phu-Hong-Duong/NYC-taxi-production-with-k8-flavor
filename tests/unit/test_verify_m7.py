"""The M7 gate, tested as a thing that can be wrong (M7-S5 leg 2).

Sixth in the line after `test_verify_m2/m3/m4/m5/m6.py`, same premise:
`scripts/verify_m7.sh` is the only artifact whose job is to say whether M7
happened, and nothing else checks IT. So these tests pin the properties that
would fail SILENTLY — a leg that stops reading a record keeps printing `ok`, a
parse that returns nothing keeps printing `ok` unless somebody demanded a
positive count.

M7 adds three properties its predecessors did not need:

  * ITS EVIDENCE IS THE ORDER OF WORK, not only the numbers. The drift bars are
    legitimate because they were argued from 2019 headroom BEFORE any 2020
    month was compared (M7 law 4), and that ordering can only be checked from
    artifacts that already exist — the records' own clocks and git's commit
    clocks. A gate that recomputed the drift numbers would destroy the property
    that makes the bars honest, so the forbidden list here includes the drift
    job itself.

  * IT MUST NOT PUSH A METRIC. The pushgateway is a bulletin board with no
    expiry: anything the gate wrote would persist and be read by a rule as if a
    real job had produced it. Verification that mutates the monitoring surface
    is not verification.

  * THE §9/M7 "SHOW" LEG IS A DIFFERENCE, NOT A SENTENCE. The two failure
    signatures must be distinguishable from the RECORDS, field by field, and
    the dangerous half is the one that produces no drift metric at all — an
    absence, which a record cannot claim about itself and which therefore has
    to be counted where a landed month would have to appear.

House rule inherited from gotcha #35 and re-learned at #68: match the
INVOCATION, never the word. This gate advises operators to run things and
argues about drift in prose, so every assertion about what it DOES is made
against a comment-stripped copy, with the needle in command position.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
VERIFY_M7 = REPO / "scripts" / "verify_m7.sh"
REDTEAM = REPO / "scripts" / "verify_m7_redteam.sh"
MAKEFILE = REPO / "Makefile"
RULES = REPO / "infra" / "monitoring" / "alerting_rules.yml"


def without_comments(path: pathlib.Path) -> str:
    """Drop whole-line comments (shell and the embedded Python alike)."""
    return "\n".join(
        line for line in path.read_text().splitlines() if not line.lstrip().startswith("#")
    )


def invokes(body: str, command: str) -> bool:
    """Is `command` RUN here, or merely named?"""
    pattern = rf"(?:^|\||&&|;|\$\()\s*{re.escape(command)}(?:\s|$)"
    return bool(re.search(pattern, body, re.M))


# ------------------------------------------------------- the Makefile contract --
def test_the_m7_targets_are_real_and_no_longer_echo_todo():
    text = MAKEFILE.read_text()
    for target in ("verify-m7:", "verify-m7-redteam:"):
        body = text.split(f"\n{target}", 1)[1].split("\n.PHONY")[0]
        recipe = body.split("\n")[1]
        assert "TODO" not in recipe, f"{target} still echoes TODO"
    assert "bash scripts/verify_m7.sh" in text
    assert "bash scripts/verify_m7_redteam.sh" in text
    assert any(
        "verify-m7-redteam" in line for line in text.splitlines() if line.startswith(".PHONY")
    )


def test_no_m7_target_still_stubs_a_drift_report():
    """`drift-report` was M7's placeholder and `make drift` replaced it. A TODO
    target surviving into a closed milestone is a promise nobody kept, and it
    reads as work outstanding to the next person who greps the Makefile."""
    text = MAKEFILE.read_text()
    assert "drift-report:" not in text
    assert "TODO(M7)" not in text


def test_the_gate_has_no_skip_flag_and_no_fast_mode():
    """M1's rule, inherited a SEVENTH time: a gate with a fast mode is a gate
    that runs in fast mode."""
    body = without_comments(VERIFY_M7)
    for forbidden in ("SKIP_", "FAST", "--quick", "QUICK"):
        assert forbidden not in body, f"{forbidden} appears in the gate — no skip flag exists"


# --------------------------------------------------- what the gate must NOT do --
def test_the_gate_re_runs_nothing_expensive():
    """M7's evidence cost 15.7M raw rows ingested, 15.4M rows scored, a ~12
    minute drift drill and a 1,618 s fit. Re-running any of it inside the gate
    would make verification the thing that produces the numbers being verified —
    and in the drift job's case it would also destroy the ordering that makes
    the bars legitimate."""
    body = without_comments(VERIFY_M7)
    for command in (
        "make ingest",
        "make ingest-scoring",
        "make data",
        "make data-scoring",
        "make duckdb",
        "make marts",
        "make predictions-scoring",
        "make drift",
        "make drift-headroom",
        "make drift-drill",
        "make drift-witness",
        "make retrain",
        "make retrain-schedule",
        "make push-serving-version",
        "make boards",
        "make board-cards",
        "make train",
        "make backup",
        "make serve",
        "make deploy-monitoring",
        "make contract-probe",
        "make contract-probe-fixtures",
    ):
        assert not invokes(body, command), f"the gate runs `{command}` — it must only read"
    # ...and the launcher must sit in command position, or the `sh` in `bash` —
    # or a path inside a Path(...) — matches. Gotcha #68, third inheritance.
    launcher = r"(?:^|[|;&(]|\$\()\s*(?:bash|sh|python3?|uv run python)\s+\S*"
    for script in (
        "drift_fire_drill.py",
        "drift_second_witness.py",
        "push_serving_version.py",
        "contract_probe.py",
        "metabase_boards.py",
        "board_cards_execute.py",
        "drift_memo_numbers.py",
        "retrain_schedule.sh",
        "data_pipeline_scoring.sh",
        "marts.sh",
    ):
        assert not re.search(rf"{launcher}{re.escape(script)}", body, re.M), (
            f"the gate RUNS {script} — it must only read its record"
        )
        assert not re.search(rf"subprocess\.run\(\[[^\]]*{re.escape(script)}", body), (
            f"the gate spawns {script} — it must only read its record"
        )


def test_the_gate_may_import_a_reader_but_not_run_a_producer():
    """The exception, and it is deliberate. `retrain_prediction_check.py` and
    `render_alert_rules.py` hold the MAPPINGS between two shapes; the gate
    imports them so it does not carry a second copy that would drift. Importing
    a module is not running its `main`, and the distinction is asserted."""
    body = without_comments(VERIFY_M7)
    assert "spec_from_file_location" in body, "the gate stopped importing the readers"
    for reader in ("retrain_prediction_check.py", "render_alert_rules.py"):
        assert reader in body, f"the gate no longer reads {reader}'s mapping"
    assert not re.search(r"\brar\.main\(|\brpc\.main\(", body), (
        "the gate calls an imported module's main() — that is running it, not reading it"
    )


def test_the_gate_cannot_push_a_metric():
    """A pushgateway has no expiry: anything this gate wrote would persist and
    be read by a rule as though a real job produced it. The one call it makes
    into the pusher is a REFUSAL probe pointed at a dead port."""
    body = without_comments(VERIFY_M7)
    pushes = re.findall(r"push_metrics\(", body)
    assert len(pushes) == 1, f"{len(pushes)} push_metrics call(s) — exactly one probe is expected"
    assert 'url="http://127.0.0.1:1"' in body, (
        "the freshness probe does not point at a dead port — it could reach the real gateway"
    )
    # The needle must sit where a shell would START a command (gotcha #68, and
    # this test earned it on its first run): the gate legitimately PRINTS the
    # `make drift DRIFT_ARGS="--push"` an operator should run to repopulate the
    # gateway, and a bare `in body` search called that a push.
    for forbidden in ("pushgateway.push(", "requests.put", "urlopen(req, data="):
        assert forbidden not in body, f"the gate can write to the gateway: {forbidden}"
    assert not invokes(body, "make drift"), "the gate RUNS the drift job rather than advising it"
    assert not re.search(r'"--push"', body), "the gate passes --push as an argument"


def test_the_gate_cannot_ingest_score_or_fit():
    """The verbs that would rewrite the data trees, the predictions tree or the
    registry's runs. None of them may be CALLED — and the needle is anchored at
    BOTH ends, because `ingest_month` is a prefix of `ingest_months`, which is
    the analyst-layer VIEW the gate legitimately reads. Gotcha #35's rule
    failing on a test rather than on prose, for the second time in this file."""
    body = without_comments(VERIFY_M7)
    for verb in (
        "ingest_month",
        "write_processed",
        "score_scoring",
        "fit_floor",
    ):
        assert not re.search(rf"(?<![\w.]){re.escape(verb)}\s*\(", body), f"the gate calls {verb}"
    for verb in ("run.run(", "dvc add", "dvc push"):
        assert not re.search(rf"(?<![\w.]){re.escape(verb)}", body), f"the gate calls {verb}"
    # The retrain entry point is INSPECTED with `ast` and REPORTED on in prose
    # ("retrain() has NO `promote` parameter"), so a search for `retrain(`
    # catches the sentence, not a call — gotcha #68 for the THIRD time in this
    # one file. The property that actually forbids the call is that the callable
    # is never imported.
    assert "retrain_run" in body, "the gate no longer inspects the retrain module"
    assert not re.search(r"from\s+taxi_mlops\.training\.retrain_run\s+import|"
                         r"retrain_run\.retrain\(|import\s+retrain\b", body), (
        "the gate imports the retrain entry point — inspecting it with ast is reading, "
        "importing it is one line away from running it"
    )


def test_the_gate_cannot_inject_kill_shift_or_deploy():
    """`kubectl` may only be asked questions — plus the one `exec` that runs a
    read-only `psql -c SELECT`, which is how everything in this repo reaches a
    Postgres that publishes no port. That exception is asserted to be read-only
    rather than waved through."""
    body = without_comments(VERIFY_M7)
    verb_call = r'"kubectl",\s*"--context",\s*"[^"]+",\s*(?:"-n",\s*"[^"]+",\s*)?"(\w[\w-]*)"'
    verbs = re.findall(verb_call, body)
    assert verbs, "no kubectl invocation found — the test is not looking where the gate looks"
    allowed = {"get", "describe", "version", "config", "exec"}
    offenders = sorted({v for v in verbs if v not in allowed})
    assert not offenders, f"the gate uses mutating kubectl verb(s): {offenders}"
    # every exec must be a read-only psql
    for chunk in re.findall(r'"exec".{0,400}', body, re.S):
        assert "psql" in chunk, "a kubectl exec that is not a psql read"
        assert re.search(r'"-c",\s*sql|"-c", sql', chunk) or "SELECT" in chunk
        for write in ("INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "TRUNCATE", "ALTER"):
            assert write not in chunk, f"the gate's psql call contains {write}"
    for mutating in ("kubectl annotate", "kubectl delete", "kubectl apply", "kubectl scale",
                     "kubectl patch", "kubectl cp"):
        assert mutating not in body


def test_the_gate_only_reads_prometheus():
    body = without_comments(VERIFY_M7)
    for forbidden in ("/api/v1/admin", "delete_series", "/-/reload", "/api/v2/silences"):
        assert forbidden not in body, f"the gate touches {forbidden}"
    assert '"POST"' not in body and 'method="POST"' not in body
    assert "/api/v1/query" in body and "/api/v1/rules" in body


def test_the_gate_never_mutates_the_registry():
    body = without_comments(VERIFY_M7)
    for verb in (
        "set_registered_model_alias",
        "delete_registered_model_alias",
        "register_model",
        "create_model_version",
        "transition_model_version_stage",
        "set_model_version_tag",
    ):
        assert not re.findall(rf"\.{verb}\(", body), f"the gate CALLS {verb}"


def test_the_live_questions_are_bounded_and_counted():
    """The kickoff's own budget: one prediction, one PromQL query, one rules
    read. A monitoring gate that asked the live system a dozen questions would
    be re-deriving the milestone rather than verifying it."""
    body = without_comments(VERIFY_M7)
    assert body.count("client_mod.infer(") == 1, "more than one live prediction is sent"
    assert body.count("/api/v1/query?") == 1, "more than one PromQL query is issued"
    assert body.count("/api/v1/rules") == 1, "more than one rules read is issued"


# ------------------------------------------------ properties, never literals ----
def test_the_gate_types_no_champion_version_no_month_no_measured_number():
    """F-017, gotchas #49/#50. M7 is the first milestone since M3 in which the
    alias MAY legitimately move, so a gate that typed `2` would go red at the
    next promotion for doing the right thing — and the months come from
    configs/data.yaml, so adding 2020-04 must not need a gate edit."""
    body = without_comments(VERIFY_M7)
    assert not re.search(r"version\s*==\s*[\"']?2[\"']?", body)
    assert not re.search(r"\b[0-9a-f]{32}\b", body), "a run id is typed in the gate"
    assert "auto-lgbm-v2" not in body
    assert "get_model_version_by_alias" in body, "the version must come from the alias"
    # No scoring month is typed. The one date-shaped literal allowed is the
    # impossible `1970-01` the freshness probe pushes at a dead port.
    months = {m for m in re.findall(r"\b(20\d\d-\d\d)\b", body)} - {"1970-01"}
    assert not months, f"the gate types scoring month(s) {sorted(months)}"
    # Nor any measured drift number.
    for measured in ("0.3913", "0.0217", "0.8336", "3.2412", "3.2403", "2,948,237", "2948237"):
        assert measured not in body, f"the gate types the measured value {measured}"


def test_no_drift_threshold_is_typed_in_the_gate():
    """Every number in a rule is parsed out of the rules file and looked for in
    the SLO document. A gate carrying its own `0.10` would stay green after the
    bar was loosened to `0.5` — the change the constitution reserves for a PO
    fork."""
    body = without_comments(VERIFY_M7)
    thresholds = set(re.findall(r"[<>]=?\s*([0-9]*\.?[0-9]+)", RULES.read_text()))
    assert thresholds, "no thresholds parsed out of the rules file — the test looks wrongly"
    interesting = {t for t in thresholds if float(t) not in (0.0, 1.0, 2.0)}
    assert interesting, "the interesting-threshold filter removed everything"
    for value in interesting:
        assert not re.search(rf"[<>]=?\s*{re.escape(value)}\b", body), (
            f"the gate types the threshold {value} — it must read it from {RULES.name}"
        )
    assert "alerting_rules.yml" in body and "slo_serving.md" in body


def test_the_signal_set_comes_from_the_renderer_not_from_a_literal_list():
    body = without_comments(VERIFY_M7)
    assert "IMPLEMENTED_SIGNALS" in body and "KNOWN_SIGNALS" in body
    assert "render_alert_rules.py" in body
    assert not re.search(r"\{\s*[\"']A-8[\"']\s*,\s*[\"']A-9[\"']", body), (
        "the gate hardcodes the M7 signal set instead of deriving it from the rules"
    )


def test_the_drift_threshold_search_is_section_scoped():
    """Strictly stronger than `verify-m6`'s whole-document search, and the point
    of the section: a bar argued in the LATENCY section is not an argument for a
    drift bar."""
    body = VERIFY_M7.read_text()
    assert "section_of(" in body, "the gate searches the whole SLO document"
    sections = re.findall(r"section_of\(slo,\s*r?\"\\n##\\s\*(\d)\\\.\"\)", body)
    assert set(sections) >= {"6", "8"}, f"sections searched: {sections}"


def test_the_prose_precision_floor_is_one_decimal():
    """Gotcha #90, inherited: allowing a record's number to render at ZERO
    decimals lets 13.75 match the string '14', which appears in almost any
    document. Every precision loop in this gate starts at 1 or higher."""
    body = VERIFY_M7.read_text()
    ranges = re.findall(r"for dp in range\((\w+),\s*\d+\)", body)
    assert ranges, "no precision policy found — the test is not looking where the gate looks"
    for start in ranges:
        if start.isdigit():
            assert int(start) >= 1, f"a precision policy starts at {start}"
        else:
            assert re.search(rf"{start}\s*=\s*1\b", body), (
                f"the precision floor `{start}` is not pinned to 1"
            )
    assert "minimum_decimals=1" in body or "minimum_decimals: int = 1" in body


def test_the_prose_comparison_strips_trailing_zeros_and_accepts_grouping():
    """The two rendering rules M7-S5 leg 1 paid for: DuckDB prints 1.061 where a
    padded table writes 1.0610 (gotcha #76 from the other side), and a document
    is allowed to group its thousands (202,574.4 is the same number as
    202574.4)."""
    body = VERIFY_M7.read_text()
    assert 'rstrip("0")' in body, "trailing zeros are not stripped on both sides"
    assert ":," in body, "the comparison does not accept a thousands-grouped rendering"


def test_the_gate_states_what_it_excludes():
    """No silent caps (the workflow rule, and #63's family). Where the gate
    narrows a search — the small integers that cannot be a second home for a
    threshold — it prints what it dropped."""
    body = VERIFY_M7.read_text()
    assert "Excluded and said so" in body
    assert "ignored" in body


# ------------------------------------------------------ the legs must have run --
def test_every_python_leg_demands_a_minimum_verdict_count():
    """M2's rule: a leg that dies on import contributes zero silent passes unless
    somebody demanded a positive count."""
    body = without_comments(VERIFY_M7)
    legs = body.count("consume < <(")
    expectations = body.count("expect_verdicts ")
    assert legs >= 7, f"only {legs} leg(s) found — the gate lost a section"
    assert expectations >= legs, (
        f"{legs} legs but only {expectations - 1} expect_verdicts call(s) — a leg can die silently"
    )


def test_every_leg_catches_its_own_exception_and_reports_it_as_a_failure():
    """A leg that raised and printed a traceback to a swallowed stderr would
    contribute zero verdicts and — without the expect_verdicts guard — zero
    failures. Both halves are required."""
    body = VERIFY_M7.read_text()
    handlers = re.findall(r'print\(f"FAIL\|the .* itself raised', body)
    assert len(handlers) >= 7, f"only {len(handlers)} leg(s) report their own exception"


@pytest.mark.needs_records
def test_the_gate_reads_the_tracked_records_it_names():
    """The gate composes a few of these from a `root` — one directory named
    once — so the needle is the directory plus the filename rather than the
    whole path. Both halves must appear, and the file must exist."""
    body = VERIFY_M7.read_text()
    for record in (
        "automation/runs/m7-drift/headroom.json",
        "automation/runs/m7-drift/prediction.json",
        "automation/runs/m7-drift/drift_fire_drill.json",
        "automation/runs/m7-retrain/latest.json",
        "automation/runs/m7-retrain/rerun-prediction.json",
        "automation/runs/m5-parity/parity.json",
        "automation/runs/m3s5/bakeoff.json",
    ):
        directory, _, name = record.rpartition("/")
        assert directory in body, f"the gate does not read anything under {directory}"
        assert name in body, f"the gate does not read {name}"
        assert (REPO / record).exists(), f"{record} is named by the gate but does not exist"


@pytest.mark.needs_records
def test_the_records_the_gate_replays_are_tracked_by_git():
    """F-029, closed at M5-S1: a gate replaying evidence that is not in the
    repository is a gate whose inputs review cannot see. `git check-ignore` is a
    two-second command and gotcha #69 is what it prevents."""
    for record in (
        "automation/runs/m7-drift/headroom.json",
        "automation/runs/m7-drift/prediction.json",
        "automation/runs/m7-drift/drift_fire_drill.json",
        "automation/runs/m7-drift/drift-2020-03.json",
        "automation/runs/m7-retrain/latest.json",
        "automation/runs/m7-retrain/rerun-prediction.json",
        "automation/runs/m7-s1/contract_probe_2025-01.json",
    ):
        result = subprocess.run(
            ["git", "check-ignore", "-q", record], cwd=REPO, capture_output=True
        )
        assert result.returncode != 0, f"{record} is GITIGNORED but the gate replays it"


# ------------------------------------------------------------ the red team ------
def test_the_red_team_breaks_exactly_one_field_and_restores_it():
    body = REDTEAM.read_text()
    assert 'RECORD="automation/runs/m7-drift/drift-2020-03.json"' in body
    assert "trap restore EXIT" in body, "the restore is not guaranteed on an unexpected exit"
    assert "sha256sum" in body, "the restore is asserted rather than verified"
    # The planted value is DERIVED from the record, never typed: a hand-picked
    # number is a fault nobody would ever make, and this one is F-045 itself.
    assert 'rec["current_rows"] /' in body
    # …and it is derived in the CODE. The header comment quotes both values so a
    # reader knows how big the lie is; what must not happen is the drill writing
    # one of them into the record.
    code = without_comments(REDTEAM)
    assert "0.3913" not in code and "0.4021" not in code, "the drill types the numbers it plants"


def test_the_red_team_touches_no_cluster_state_and_no_gateway():
    body = without_comments(REDTEAM)
    for forbidden in ("kubectl", "helm", "docker", "make drift", "make retrain", "mlflow"):
        assert not invokes(body, forbidden), f"the red team runs {forbidden}"
    assert "verify_m7.sh" in body, "the red team does not actually run the gate"


def test_the_red_team_asserts_all_three_halves():
    """RED for the planted cause, everything else still counted, AND one named
    leg that must stay GREEN. The third is what separates a gate that fails on a
    wrong number from one that fails on any edit."""
    body = REDTEAM.read_text()
    assert "still passed" in body, "the drill does not assert the other sub-checks kept running"
    assert "unaffected leg still green" in body
    assert "STILL GREEN" in body, "the drill does not pin a leg that must NOT fire"
    assert "git status --porcelain" in body, "a clean drill must leave a clean tree (F-029)"


def test_the_red_team_requires_three_independent_witnesses():
    """One artifact contradicting itself is arithmetic; three artifacts
    disagreeing is a finding. The drill names all three by the message each
    leg prints."""
    body = REDTEAM.read_text()
    for needle in (
        "do not reconcile with the run's anchors",
        "the drill record and the per-month records disagree",
        "the memo quotes number(s) no record holds",
    ):
        assert needle in body, f"the drill does not require the witness that prints {needle!r}"
        assert needle in VERIFY_M7.read_text(), (
            f"the gate never prints {needle!r} — the drill greps for a message that cannot appear"
        )


# ------------------------------------------ the accept-when, as a data contract --
@pytest.mark.needs_records
def test_the_records_the_accept_when_rests_on_say_what_it_needs():
    """§9/M7 accepts on three things. This test does not re-check the gate's
    logic — it pins that the RECORDS still carry the fields those clauses are
    read from, so a future re-run that drops a field fails here rather than
    silently weakening a sub-check."""
    root = REPO / "automation/runs/m7-drift"
    drill = json.loads((root / "drift_fire_drill.json").read_text())
    headroom = json.loads((root / "headroom.json").read_text())
    retrain = json.loads((REPO / "automation/runs/m7-retrain/latest.json").read_text())

    # "the two failure signatures" — the drift side needs a per-month record with
    # anchors, the schema side needs a refusal with an exit code.
    for month_file in root.glob("drift-*.json"):
        rec = json.loads(month_file.read_text())
        assert rec["current_trips_per_day"] > 0 and rec["reference_trips_per_day"] > 0
        assert rec["volume_ratio"] > 0 and rec["max_input_psi"] >= 0
    fixtures = list((REPO / "automation/runs/m7-s1").glob("contract_probe_fixture_*.json"))
    assert fixtures, "no refusal fixture record exists"
    for path in fixtures:
        rec = json.loads(path.read_text())
        assert rec["exit_code"] == 1 and rec["error_type"] == "SchemaEventError"

    # The drift bars were argued from 2019 headroom, and the record still says so.
    assert set(headroom) and all(m.startswith("2019") for m in headroom)
    assert drill["prediction"] and drill["fired_at_seconds"]

    # The retrain's verdict is data, and the pointer did not move.
    assert retrain["verdict"]["verdict"] in {"PROMOTE", "REFUSE"}
    assert retrain["promoted"] is False


def test_the_scoring_manifest_contract_when_the_batch_path_has_been_run():
    """The predictions manifest is DELIBERATELY untracked — M2-S4's argument,
    inherited: it is model OUTPUT, regenerable from DVC-pinned inputs plus a
    registry version, and its real provenance is the registry rather than a
    `.dvc` pin that would be stale by design. So a fresh clone (CI) has no such
    file, and this contract can only be asserted on a machine that has run
    `make predictions-scoring`.

    It is a separate test with a SPOKEN skip rather than a branch inside the
    tracked-record contract, because a guard folded into that test would let the
    tracked half go quietly unasserted the day somebody deletes the manifest.
    CI proves the tracked contract unconditionally; this one proves the rest
    where the rest exists."""
    import pytest

    manifest_path = REPO / "data/scoring_predictions/scoring_predictions.json"
    if not manifest_path.exists():
        pytest.skip(
            "data/scoring_predictions/scoring_predictions.json is gitignored regenerable "
            "output (M2-S4's argument) — run `make predictions-scoring` to assert this half"
        )
    manifest = json.loads(manifest_path.read_text())
    # "the predictions table for the scored month exists" — with the version on
    # it and a self-check that anchored it to a month with a known answer.
    assert manifest["months"] and manifest["model"]["version"]
    assert manifest["model"]["alias"], "the manifest does not record which alias it resolved"
    assert manifest["self_check"]["registry_kpi_09"] and manifest["self_check"]["measured_kpi_09"]
    for month in manifest["months"]:
        for key in ("kpi_14_mae_minutes", "kpi_15_within_tolerance_pct",
                    "kpi_16_mean_signed_error_minutes", "kpi_17_scored_trips"):
            assert key in month, f"{month['month']} lost {key} — a monitoring id with no value"

