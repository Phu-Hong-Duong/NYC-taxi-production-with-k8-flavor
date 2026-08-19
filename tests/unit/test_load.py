"""M5-S4: the load client's and the self-heal drill's cluster-free half.

`make load-drill` needs a live endpoint and a pod to kill; almost everything
that could be WRONG about the measurement does not. What is pinned here is the
set of properties whose quiet loss would leave a green drill and a quotable p95
meaning nothing:

* **a percentile is never printed without its shape.** An unqualified latency is
  not a measurement — it is a number that outlives the conditions that produced
  it. The rate, the window, the concurrency, the mix and the ACHIEVED rate travel
  with every figure, in the summary line and in the record.
* **the loop is OPEN.** Arrivals are scheduled at `k/rate` whether or not a
  worker is free, and the headline percentile is measured from the SCHEDULED
  instant. A closed loop — fire the next request when the last returns — cannot
  observe queueing, so it reports the service time of an unloaded server as if it
  were a load test (coordinated omission). This is the property that would be
  cheapest to lose in a refactor and hardest to notice, so it is pinned twice:
  behaviourally (service_ms and latency_ms are distinct quantities) and
  structurally (the scheduled time is `index / rate`).
* **percentiles are nearest-rank**, so every quoted number is a request that
  actually happened rather than an interpolation between two that did.
* **the drill asserts IDENTITY, not a name.** M4-S5 predicted a pod NAME, and
  reported a correct survival as a failure because the controller recreated the
  pod under the same name with a new uid.
* **the prediction is written BEFORE the kill**, in program order, not just in
  the prose that says so.
* **the drill cannot go green having disturbed nothing.** With one replica a
  kill must cost requests; zero errors would mean the load was not in flight
  across it, and a drill that passes without proving anything is worse than none.
* **both are READERS of the model**: no alias moves, nothing is promoted, no
  deployment is scaled or patched. The only mutation in the story is deleting
  ONE pod a controller immediately replaces.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from taxi_mlops.serving import load as load_mod

REPO = Path(__file__).resolve().parents[2]
LOAD_SOURCE = REPO / "src" / "taxi_mlops" / "serving" / "load.py"
DRILL_SOURCE = REPO / "scripts" / "serving_load_drill.py"
MAKEFILE = REPO / "Makefile"

pytestmark = pytest.mark.unit


def _calls(source: Path) -> list[str]:
    """Every dotted callee name actually INVOKED in a module (gotchas #53/#68)."""
    tree = ast.parse(source.read_text())
    names = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        parts = []
        while isinstance(target, ast.Attribute):
            parts.append(target.attr)
            target = target.value
        if isinstance(target, ast.Name):
            parts.append(target.id)
        if parts:
            names.append(".".join(reversed(parts)))
    return names


def _function(source: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(source.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} is gone from {source.name}")


def _attempt(index: int, scheduled: float, sent: float, done: float, **kw) -> load_mod.Attempt:
    return load_mod.Attempt(index, scheduled, sent, done, kw.pop("ok", True), **kw)


def _result(attempts: list[load_mod.Attempt], **kw) -> load_mod.LoadResult:
    shape = {
        "target_rate": 10.0,
        "seconds": 10.0,
        "concurrency": 4,
        "mix": "hazards",
        "rows_per_request": 1,
        "endpoint": "http://localhost:8081/v2/models/nyc-taxi-eta/infer",
        "host": "nyc-taxi-eta-serving.local",
        "wall_seconds": 10.0,
    }
    shape.update(kw)
    return load_mod.LoadResult(attempts=attempts, **shape)


# --------------------------------------------------------------------------
# the measurement
# --------------------------------------------------------------------------
def test_percentiles_are_nearest_rank_so_every_figure_is_an_observed_request() -> None:
    values = [float(v) for v in range(1, 101)]
    assert load_mod.percentile(values, 0.50) == 50.0
    assert load_mod.percentile(values, 0.95) == 95.0
    assert load_mod.percentile(values, 0.99) == 99.0
    # An interpolating implementation would answer 95.05 here; every value this
    # returns must be one of the samples.
    for q in (0.5, 0.95, 0.99):
        assert load_mod.percentile(values, q) in values


def test_percentile_of_one_sample_is_that_sample_not_an_index_error() -> None:
    assert load_mod.percentile([7.0], 0.99) == 7.0
    assert load_mod.percentile([], 0.95) != load_mod.percentile([], 0.95)  # nan


def test_latency_is_measured_from_the_SCHEDULED_instant_not_the_send() -> None:
    """The coordinated-omission guard, stated as a number.

    A request due at t=1.0 that could not be sent until t=1.5 and returned at
    t=1.6 took 100 ms of the server's time and 600 ms of the caller's. Reporting
    only the first is how a load test flatters a saturated service.
    """
    attempt = _attempt(0, scheduled=1.0, sent=1.5, done=1.6)
    assert attempt.service_ms == pytest.approx(100.0)
    assert attempt.latency_ms == pytest.approx(600.0)
    assert attempt.queue_ms == pytest.approx(500.0)


def test_the_headline_percentiles_are_the_latency_ones() -> None:
    result = _result([_attempt(i, i * 0.1, i * 0.1 + 0.4, i * 0.1 + 0.5) for i in range(20)])
    record = result.as_record()
    assert record["latency_ms"]["p95"] > record["service_ms"]["p95"]
    assert set(record) >= {"latency_ms", "service_ms", "queue_ms"}


def test_the_arrival_schedule_is_open_loop_in_the_code_itself() -> None:
    """Structural, because a closed loop passes every behavioural test on a fast server.

    The one line that makes this an open loop is `scheduled = index / rate`: the
    arrival instant is a function of the request's INDEX and the target rate, and
    of nothing that happened to any earlier request. A refactor that sets it from
    a previous response's completion time would be a closed loop wearing the same
    field names, and would be invisible until the day the server was slow.
    """
    worker = None
    for node in ast.walk(_function(LOAD_SOURCE, "run_load")):
        if isinstance(node, ast.FunctionDef) and node.name == "worker":
            worker = node
    assert worker is not None, "run_load's worker is gone"
    assigns = {
        ast.unparse(node.value)
        for node in ast.walk(worker)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "scheduled" for t in node.targets)
    }
    assert assigns == {"index / rate"}, f"the arrival schedule is no longer open-loop: {assigns}"


def test_the_achieved_rate_is_recorded_beside_the_target() -> None:
    """A run that fell short did not measure what it claims to have measured."""
    result = _result(
        [_attempt(i, i * 0.1, i * 0.1, i * 0.1 + 0.05) for i in range(50)], wall_seconds=10.0
    )
    shape = result.as_record()["shape"]
    assert shape["target_rate_per_second"] == 10.0
    assert shape["achieved_rate_per_second"] == 5.0
    assert {"window_seconds", "concurrency", "mix", "rows_per_request"} <= set(shape)


def test_the_summary_line_carries_the_shape_with_the_percentiles() -> None:
    result = _result([_attempt(i, i * 0.1, i * 0.1, i * 0.1 + 0.05) for i in range(100)])
    text = "\n".join(load_mod.summary_lines(result))
    for token in ("req/s", "concurrency", "hazards", "p95", "p99", "achieved"):
        assert token in text, f"the summary dropped {token!r} — a p95 without its shape"


def test_a_client_that_falls_behind_says_so_in_the_summary() -> None:
    behind = _result([_attempt(i, i * 0.1, i * 0.1 + 1.0, i * 0.1 + 1.1) for i in range(20)])
    assert any("NOTE" in line and "waiting for a free worker" in line
               for line in load_mod.summary_lines(behind))
    keeping_up = _result([_attempt(i, i * 0.1, i * 0.1, i * 0.1 + 0.05) for i in range(20)])
    assert not any("NOTE" in line for line in load_mod.summary_lines(keeping_up))


def test_percentiles_are_computed_over_successful_requests_only() -> None:
    """A failed request has no latency — it has an error, and it is counted as one.

    Averaging a connection refusal's 3 ms into a p95 makes an outage look FAST.
    """
    attempts = [_attempt(i, i * 0.1, i * 0.1, i * 0.1 + 0.5) for i in range(10)]
    attempts += [_attempt(i, i * 0.1, i * 0.1, i * 0.1 + 0.001, ok=False, error="URLError: refused")
                 for i in range(10, 20)]
    result = _result(attempts)
    assert result.percentiles("latency_ms")["min"] == pytest.approx(500.0)
    assert result.as_record()["requests"] == {"sent": 20, "ok": 10, "errors": 10, "error_rate": 0.5}


def test_the_error_window_is_exact_and_the_bucket_resolution_is_stated() -> None:
    attempts = [_attempt(i, float(i), float(i), i + 0.05) for i in range(10)]
    attempts += [
        _attempt(10, 10.25, 10.25, 10.3, ok=False, error="URLError: refused"),
        _attempt(11, 13.5, 13.5, 13.75, ok=False, status=503, error="HTTP 503"),
    ]
    window = _result(attempts).error_window()
    assert window["errors"] == 2
    assert window["first_error_s"] == 10.25
    assert window["last_error_s"] == 13.75
    assert window["span_s"] == pytest.approx(3.5)
    assert window["classes"] == {"URLError: refused": 1, "HTTP 503": 1}
    # and the per-second buckets are a SEPARATE, coarser view
    seconds = {b["second"] for b in _result(attempts).buckets()}
    assert seconds == set(range(11)) | {13}


def test_the_version_stamp_is_read_off_the_timed_responses() -> None:
    """Which model served the window is answered by the answers, not by a metadata call."""
    attempts = [_attempt(i, float(i), float(i), i + 0.1, model_version="2") for i in range(5)]
    assert _result(attempts).served_versions == ["2"]
    attempts.append(_attempt(5, 5.0, 5.0, 5.1, model_version="1"))
    assert _result(attempts).served_versions == ["1", "2"]


def test_the_bodies_are_encoded_before_the_clock_starts() -> None:
    """Client-side JSON encoding must not land inside a number the PRR reads as server latency."""
    body = _function(LOAD_SOURCE, "run_load")
    calls = [ast.unparse(node) for node in ast.walk(body) if isinstance(node, ast.Call)]
    assert any(call.startswith("build_bodies(") for call in calls)
    worker = next(
        n for n in ast.walk(body) if isinstance(n, ast.FunctionDef) and n.name == "worker"
    )
    inside = {ast.unparse(n.func) for n in ast.walk(worker) if isinstance(n, ast.Call)}
    assert "json.dumps" not in inside and "v2_payload" not in inside, (
        "a request body is being built inside the timed section"
    )


def test_the_hazard_mix_is_the_default_and_is_the_committed_one() -> None:
    from taxi_mlops.serving import parity

    assert load_mod._mix_requests("hazards") == [h.request for h in parity.HAZARDS]
    assert load_mod._mix_requests("ordinary") == [parity.HAZARDS[0].request]
    with pytest.raises(ValueError, match="unknown mix"):
        load_mod._mix_requests("whatever-is-fastest")


def test_every_hazard_row_encodes_for_the_wire_including_the_no_geometry_ones() -> None:
    """F-030's rows are in the load mix, so the load client exercises the `null` path."""
    from taxi_mlops.training.run import load_train_config

    bodies = load_mod.build_bodies("hazards", 1, load_train_config()["features"])
    assert len(bodies) == 16
    import json as _json

    for body in bodies:
        payload = _json.loads(body)  # would raise on a bare NaN token
        assert len(payload["inputs"]) == 24
    assert any(b'null' in body for body in bodies), "the no-geometry rows lost their nulls"


# --------------------------------------------------------------------------
# the drill
# --------------------------------------------------------------------------
def _drill():
    """Import the drill script as a module — it is a script, not a package member."""
    import importlib.util
    import sys

    if "serving_load_drill" in sys.modules:
        return sys.modules["serving_load_drill"]
    spec = importlib.util.spec_from_file_location("serving_load_drill", DRILL_SOURCE)
    module = importlib.util.module_from_spec(spec)
    # registered BEFORE exec: `from __future__ import annotations` makes the
    # dataclass decorators resolve their annotations through sys.modules.
    sys.modules["serving_load_drill"] = module
    spec.loader.exec_module(module)
    return module


def test_the_headline_rate_refuses_a_step_that_sat_on_the_cpu_limit() -> None:
    """Attempt 1's actual ramp, replayed: the two-clause rule picked the ceiling.

    8 req/s held its rate and returned no errors, and ran at 100.2% of a 2-core
    limit while being throttled in 601 periods. A capacity headline measured
    there is a measurement of the quota, not of the service.
    """
    drill = _drill()
    steps = [
        {"target_rate": 2.0, "achieved_rate": 2.042, "errors": 0, "cpu_saturation": 0.30},
        {"target_rate": 4.0, "achieved_rate": 4.046, "errors": 0, "cpu_saturation": 0.55},
        {"target_rate": 6.0, "achieved_rate": 6.039, "errors": 0, "cpu_saturation": 0.78},
        {"target_rate": 8.0, "achieved_rate": 7.973, "errors": 0, "cpu_saturation": 1.002},
    ]
    assert drill.choose_headline_rate(steps) == 6.0
    # a step that did NOT hold its rate is out for the original reason
    steps[2]["achieved_rate"] = 5.0
    assert drill.choose_headline_rate(steps) == 4.0
    # and errors still disqualify
    steps[1]["errors"] = 3
    assert drill.choose_headline_rate(steps) == 2.0


def test_the_outage_is_not_the_span_from_first_error_to_last() -> None:
    """The quantity attempt 1 got wrong, pinned as a regression (gotcha #63's shape).

    The synthetic timeline is attempt 1's: a kill at T+25, ~13 seconds in which
    nothing succeeds, then a long healthy tail that drops one request now and
    then because the load is sitting on the CPU limit. `last_error - first_error`
    calls that a 175-second outage. It was a 14-second outage followed by a
    background error rate, and conflating them makes the runbook quote a number
    that never happened.
    """
    drill = _drill()
    attempts: list[load_mod.Attempt] = []
    index = 0
    for second in range(0, 200):
        for slot in range(8):
            t = second + slot / 8
            dead = 25.5 <= t < 39.0
            sporadic = (not dead) and t > 39.0 and slot == 3 and second in (50, 121, 200 - 1)
            ok = not (dead or sporadic)
            attempts.append(
                load_mod.Attempt(index, t, t, t + (0.05 if ok else 0.003), ok,
                                 None if ok else 503, None if ok else "HTTP 503",
                                 "2" if ok else None)
            )
            index += 1
    result = _result(attempts, target_rate=8.0, seconds=200.0, wall_seconds=200.0)

    naive = result.error_window()
    assert naive["span_s"] > 150  # what attempt 1 called "the outage"

    recovery = drill.measure_recovery(result, 25.0, 200.0)
    # the unavailability itself: first refusal (T+25.5) -> first answer again (T+39.05)
    assert recovery["outage_seconds"] == pytest.approx(13.55, abs=0.2)
    # and what the runbook quotes: the kill (T+25) -> quoting again
    assert recovery["seconds_from_kill_to_recovery"] == pytest.approx(14.05, abs=0.2)
    assert recovery["fully_unavailable_seconds"] == 13
    assert recovery["residual_errors"] == 3
    assert 0 < recovery["residual_error_rate"] < 0.01
    assert recovery["pre_kill_errors"] == 0
    # the two are reported separately and neither is folded into the other
    assert recovery["outage_seconds"] < 20 < naive["span_s"]


def test_the_pre_kill_segment_is_the_control_for_the_residual_rate() -> None:
    """A residual error rate means nothing without the same run's own baseline."""
    drill = _drill()
    keys = drill.measure_recovery(_result([]), 5.0, 10.0)
    assert {"pre_kill_error_rate", "residual_error_rate"} <= set(keys)


def test_no_error_rate_THRESHOLD_is_applied_by_the_drill() -> None:
    """An error-rate objective is an SLO, and the M5 kickoff puts the SLO document in M6.

    The drill measures the residual rate and prints it beside the pre-kill rate.
    A bar invented here would be a bar set from the number that had just been
    seen, by an executor, in a milestone whose scope explicitly excludes it.
    """
    source = DRILL_SOURCE.read_text()
    body = source.split('"""', 2)[-1]
    for forbidden in ("residual_error_rate <", "residual_error_rate >", "error_rate <="):
        assert forbidden not in body, f"the drill is gating on an error rate: {forbidden}"


def test_the_tail_check_asserts_AVAILABILITY_not_a_zero_error_count() -> None:
    """What the drill tests is self-heal: did the service come back and stay up.

    "Zero errors in the last 30 s" is a statement about the load level, not about
    recovery — attempt 1 failed it while the endpoint was serving 99.3% of a
    saturating load perfectly well.
    """
    fn = _function(DRILL_SOURCE, "phase_selfheal")
    source = ast.unparse(fn)  # normalises quotes, so match on the unparsed form
    assert "b['sent'] > 0 and b['ok'] == 0" in source, "the tail no longer looks for dead seconds"
    assert "tail_errors == 0" not in source, "the tail is back to counting errors"
    assert "not tail_dead" in source, "the availability check is gone"


def test_the_kill_target_is_asserted_by_uid_never_by_name() -> None:
    """M4-S5's lesson, pinned: a controller may legitimately reuse a name."""
    checks = _function(DRILL_SOURCE, "phase_selfheal")
    compares = [
        ast.unparse(node) for node in ast.walk(checks)
        if isinstance(node, ast.Compare)
    ]
    assert any("uid" in text and "!=" in text for text in compares), (
        "the self-heal check no longer compares pod UIDs"
    )
    assert not any(".name !=" in text or ".name ==" in text for text in compares), (
        "the drill is asserting on a pod NAME — that is the M4-S5 failure exactly"
    )


def test_the_prediction_is_written_before_the_kill_in_PROGRAM_ORDER() -> None:
    """Prose saying 'written first' is not the same as being written first."""
    body = _function(DRILL_SOURCE, "phase_selfheal").body
    lines_writing_prediction = [
        node.lineno for node in ast.walk(_function(DRILL_SOURCE, "phase_selfheal"))
        if isinstance(node, ast.Call)
        and ast.unparse(node).startswith("write(prediction")
    ]
    lines_running_load = [
        node.lineno for node in ast.walk(_function(DRILL_SOURCE, "phase_selfheal"))
        if isinstance(node, ast.Call) and ast.unparse(node).startswith("run_load(")
    ]
    assert lines_writing_prediction and lines_running_load
    assert min(lines_writing_prediction) < min(lines_running_load)
    assert body  # the function is not a stub


def test_the_kill_is_timed_from_inside_the_load_window() -> None:
    """One clock. A kill scheduled by a separate sleep lands at an offset nobody measured."""
    fn = _function(DRILL_SOURCE, "phase_selfheal")
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "on_second" for node in ast.walk(fn)
    )
    run_load_calls = [
        node for node in ast.walk(fn)
        if isinstance(node, ast.Call) and ast.unparse(node.func) == "run_load"
    ]
    assert any(kw.arg == "on_second" for call in run_load_calls for kw in call.keywords)


def test_a_drill_that_disturbed_nothing_cannot_be_green() -> None:
    source = DRILL_SOURCE.read_text()
    assert 'window["errors"] > 0' in source, (
        "the drill no longer requires the kill to have COST something — with one "
        "replica, zero errors means the load was not in flight across it"
    )


@pytest.mark.parametrize(
    "verb",
    [
        "set_registered_model_alias",
        "delete_registered_model_alias",
        "transition_model_version_stage",
        "create_model_version",
        "register_model",
    ],
)
def test_neither_the_client_nor_the_drill_touches_the_registry(verb: str) -> None:
    for source in (LOAD_SOURCE, DRILL_SOURCE):
        calls = _calls(source)
        assert not any(call.endswith(verb) for call in calls), f"{source.name} calls {verb}"


def test_the_drill_mutates_exactly_one_kind_of_thing_and_it_is_a_pod() -> None:
    """It deletes ONE pod a controller replaces. It does not scale, patch or apply."""
    source = DRILL_SOURCE.read_text()
    tree = ast.parse(source)
    kubectl_verbs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "sh":
            args = [a.value for a in node.args if isinstance(a, ast.Constant)]
            if "kubectl" in args:
                kubectl_verbs.append(args)
    assert kubectl_verbs, "the drill no longer runs kubectl at all"
    mutating = {"delete", "apply", "scale", "patch", "edit", "replace", "create", "drain"}
    used = {verb for argv in kubectl_verbs for verb in argv if verb in mutating}
    assert used == {"delete"}, f"the drill mutates more than a pod: {used}"
    for argv in kubectl_verbs:
        if "delete" in argv:
            assert "pod" in argv, f"a non-pod delete: {argv}"


def test_the_records_land_where_review_can_see_them() -> None:
    """F-029's regime: the M5 gate replays these, so git must be able to show a diff."""
    assert str(load_mod.DEFAULT_RECORD_DIR) == "automation/runs/m5-load"
    ignore = (REPO / ".gitignore").read_text()
    assert "!automation/runs/**/*.json" in ignore


def test_the_load_client_reports_and_does_not_judge() -> None:
    """The bar lives in the M5 gate. A measurement tool with a threshold is one that
    can refuse to report on the day the number matters."""
    source = LOAD_SOURCE.read_text()
    for word in ("PASS", "FAIL", "assert "):
        assert word not in source.split('"""')[-1], f"the load client contains a verdict: {word}"


def test_there_is_no_skip_flag(  ) -> None:
    """M1's rule, inherited by every measurement since."""
    for source in (LOAD_SOURCE, DRILL_SOURCE):
        text = source.read_text()
        for flag in ("--fast", "SKIP_LOAD", "--skip-load"):
            assert flag not in text, f"{source.name} has a way to not run: {flag}"


def test_the_makefile_wires_both_targets() -> None:
    makefile = MAKEFILE.read_text()
    assert "\nload:" in makefile and "taxi_mlops.serving.load" in makefile
    assert "\nload-drill:" in makefile and "scripts/serving_load_drill.py" in makefile
    phony = next(line for line in makefile.splitlines() if line.startswith(".PHONY: holidays"))
    assert "load" in phony and "load-drill" in phony
