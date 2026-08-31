"""The python plumbing the drills and probes share — `scripts/_lib/` (CU-S4).

CU-S3's sibling, one language along, and the shape of the duplication was
DIFFERENT in a way worth stating: CU-S3 found eight byte-identical copies, so
consolidating was a pure deletion. Here the copies had DIVERGED — five
`http_get`s with three behaviours, four `prom_query`s with two error checks,
eight `kubectl`s with six bodies — which is the `_calls()` hazard CU-S2 measured
in `tests/`, sitting in `scripts/` the whole time. So the rule is CU-S2's: split
by behaviour, name each for what it does, never merge two functions because they
share a name.

Most of what follows RUNS the library. `_lib.ports.assert_unique()` in
particular is not a test of a list; it is the guard that the comments it
replaces could not be.
"""

from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys

import pytest
from conftest import REPO, called_names

LIB = REPO / "scripts" / "_lib"
MODULES = ["__init__", "ports", "k8s", "monitoring", "records"]

#: Every script CU-S4 migrated. Named rather than globbed: a glob would silently
#: stop covering a file that was renamed, and this list is what the PR claims.
MIGRATED = [
    "alert_fire_drill.py",
    "canary_release_drill.py",
    "canary_spike_probe.py",
    "demo_accept.py",
    "drift_fire_drill.py",
    "drift_persistence_drill.py",
    "gameday_m6.py",
    "store_watch.py",
    "store_watch_drill.py",
    "store_watch_headroom.py",
]


def _import(name: str):
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        return importlib.import_module(f"_lib.{name}")
    finally:
        sys.path.remove(str(REPO / "scripts"))


# --------------------------------------------------------------------------
# The package exists, imports, and says what must not move into it.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", MODULES)
def test_the_module_imports(name: str) -> None:
    """A syntax or import error here takes ten callers down at once."""
    assert (LIB / f"{name}.py").exists(), f"_lib/{name}.py is missing"
    _import(name)


def test_the_package_says_what_deliberately_does_not_live_in_it() -> None:
    """CU-S3's convention, inherited. A shared file's real risk is the NEXT
    consolidation, so the header names what must stay per-caller — accept
    checks, predictions, plants, DRY_RUN narrations, thresholds, bespoke record
    refusals — and a future session moving one in has to delete the sentence
    saying not to."""
    assert "DELIBERATELY DOES NOT LIVE HERE" in (LIB / "__init__.py").read_text()


# --------------------------------------------------------------------------
# The port registry. This is the slice's load-bearing guard.
# --------------------------------------------------------------------------


def test_no_two_forwards_reserve_the_same_local_port() -> None:
    """THE property, and the one coordination-by-comment could not have.

    Before CU-S4 these numbers lived one per script, each with a comment
    enumerating the neighbours its author had checked. `gameday_m6.py` reserved
    9096 for Alertmanager and `drift_fire_drill.py` reserved 9096 for the
    pushgateway; the second file's comment cites the FIRST drill's 9095 as the
    precedent it is avoiding, and `store_watch_drill.py`'s comment enumerates
    four neighbours and misses gameday entirely. Every one of those comments was
    accurate about what its author read. None could be accurate about the set.
    """
    _import("ports").assert_unique()


def test_the_registry_is_the_only_home_for_a_forward_port() -> None:
    """No migrated script may carry a bare ephemeral port number.

    The accept criterion the charter names: "no forward port number appears in
    more than one place". Checked against the registry's own values, so adding a
    reservation cannot quietly re-permit a literal.
    """
    reserved = {r.port for r in _import("ports").RESERVATIONS.values()}
    offenders: list[str] = []
    for name in MIGRATED:
        for node in ast.walk(ast.parse((REPO / "scripts" / name).read_text())):
            if isinstance(node, ast.Constant) and node.value in reserved:
                offenders.append(f"{name}:{node.lineno} -> {node.value}")
    assert not offenders, (
        "these scripts spell a reserved forward port as a literal instead of "
        f"asking `_lib.ports`: {offenders}"
    )


def test_asking_for_a_port_that_is_not_reserved_names_what_is() -> None:
    """A caller who invents a name gets the registry, not a bare KeyError."""
    ports = _import("ports")
    with pytest.raises(KeyError) as excinfo:
        ports.port("ALERTMANAGER_TYPO")
    assert "FLYTE_READER" in str(excinfo.value)


def test_every_reservation_argues_its_own_number() -> None:
    """`why` is not decoration: it is what the next author reads before picking
    a number. `render_alert_rules.py` refuses a rule with no `why` for the same
    reason — a value whose argument is not written beside it is a value nobody
    can review."""
    for name, reservation in _import("ports").RESERVATIONS.items():
        assert len(reservation.why.strip()) > 30, f"{name} does not argue its number"
        assert reservation.owner and reservation.service, name


# --------------------------------------------------------------------------
# The readers were SPLIT by behaviour, not merged under one name.
# --------------------------------------------------------------------------


def test_the_two_http_readers_differ_in_the_way_that_matters() -> None:
    """`http_get` lets an unreachable endpoint raise; `http_probe` reports it.

    Five copies of "http_get" existed across `scripts/` with three behaviours,
    and the difference between them is exactly whether an unreachable endpoint
    is a bug or an expected state — which is not something a caller should get
    by accident. Both halves are asserted: a probe that raised would break every
    polling loop, and a get that swallowed would hide a dead forward behind
    whatever the caller asked next.
    """
    monitoring = _import("monitoring")
    dead = "http://127.0.0.1:1/nothing"
    status, reason = monitoring.http_probe("localhost", dead, timeout=2)
    assert status == 0 and reason, "http_probe must report an unreachable endpoint"
    with pytest.raises(Exception):  # noqa: B017 - any connection error is the point
        monitoring.http_get("localhost", dead, timeout=2)


def test_prom_query_refuses_a_query_prometheus_refused() -> None:
    """An HTTP 200 carrying `status: error` is a REFUSED query, not an empty result.

    Two of the four copies checked only the status code, so a mistyped metric
    name came back as `[]` — indistinguishable from a legitimately quiet system,
    which is gotcha #78 arriving through a client. Driven here against a stub so
    the assertion needs no cluster.
    """
    monitoring = _import("monitoring")
    original = monitoring.http_get
    try:
        monitoring.http_get = lambda *a, **k: (200, '{"status":"error","error":"bad"}')
        with pytest.raises(RuntimeError, match="refused"):
            monitoring.prom_query("h", "http://r", "nonsense{")
    finally:
        monitoring.http_get = original


def test_firing_labels_reads_per_series_and_not_per_rule_name() -> None:
    """gotcha #93. A rule firing for ONE month must not read as firing for all.

    The generalisation CU-S4 made — the LABEL is a parameter — is what let the
    drift drill's `month` read and the store watchdog's `check` read become one
    reader. This asserts the per-series property survived that move, which is
    the thing worth guarding: a name-level answer would pass a "did it fire?"
    check and silently lose three predictions about one rule.
    """
    firing_labels = _import("monitoring").firing_labels
    rules = {
        "A9": {
            "alerts": [
                {"state": "firing", "labels": {"month": "2020-03"}},
                {"state": "pending", "labels": {"month": "2020-01"}},
            ]
        }
    }
    assert firing_labels(rules, "A9", "month") == {"2020-03"}
    assert firing_labels(rules, "AbsentRule", "month") == set()


def test_rule_state_says_absent_rather_than_inactive_for_a_rule_that_is_missing() -> None:
    """A rule that was never loaded and a rule that is quiet are different facts.
    Defaulting the missing case to "inactive" reports a broken deploy as a
    healthy system (gotcha #92's shape)."""
    rule_state = _import("monitoring").rule_state
    assert rule_state({}, "Nope") == "absent"
    assert rule_state({"A": {"state": "inactive"}}, "A") == "inactive"


def test_the_readers_decide_nothing() -> None:
    """No threshold, bar or sustain may enter `_lib.monitoring`.

    M5-S4's precedent — a READER that does not judge — and `verify-m6` §2's
    contract depends on it: that gate parses every number in the rules file and
    requires `docs/slo_serving.md` to argue it. A bar computed in a library is a
    bar in a place no gate parses.
    """
    source = (LIB / "monitoring.py").read_text()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Compare):
            for operand in [node.left, *node.comparators]:
                if isinstance(operand, ast.Constant) and isinstance(operand.value, float):
                    raise AssertionError(
                        f"a float comparison at line {node.lineno} looks like a threshold; "
                        "bars live in docs/slo_serving.md and the rules file"
                    )


# --------------------------------------------------------------------------
# kubectl and the forward.
# --------------------------------------------------------------------------


def test_the_kubectl_wrapper_always_pins_the_context() -> None:
    """Eight wrappers, six bodies, and `gameday_m6.py`'s did NOT pin `--context`
    — it ran against whatever the developer's current context happened to be,
    which on this machine is the same cluster and on somebody else's is not."""
    source = (LIB / "k8s.py").read_text()
    assert source.count('"kubectl", "--context", CONTEXT') == 2, (
        "both the run wrapper and the forward must pin the context"
    )
    assert "KUBE_CONTEXT" in source, "the context must stay overridable for a rebuilt cluster"


def test_no_migrated_script_still_defines_its_own_kubectl_or_forward() -> None:
    """The copies are DELETED, not wrapped. A file that kept its own definition
    would go on diverging while looking migrated."""
    banned = {"port_forward", "_forward", "_wait_http"}
    offenders: list[str] = []
    for name in MIGRATED:
        tree = ast.parse((REPO / "scripts" / name).read_text())
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in banned:
                offenders.append(f"{name}:{node.lineno} defines {node.name}")
            # `kubectl` may be re-declared ONLY as a thin wrapper; a body longer
            # than a few lines means the copy came back.
            if (
                isinstance(node, ast.FunctionDef)
                and node.name in {"kubectl", "_kubectl"}
                and len(node.body) > 2
            ):
                offenders.append(f"{name}:{node.lineno} re-implements {node.name}")
    assert not offenders, offenders


def test_the_forward_waits_for_its_socket_instead_of_sleeping() -> None:
    """The one behaviour change CU-S4 made, and the reason it is an improvement.

    The copies slept a fixed 3 or 4 seconds and then proceeded regardless, so a
    forward that never came up surfaced as a connection error attributed to
    whatever the drill asked next — the failure lands on the wrong component
    (#55, #70). Asserted structurally because the alternative is opening a real
    forward: `start_forward` must consult `_forward_is_up`, and that helper must
    actually connect a socket rather than sleep out the clock.
    """
    k8s = _import("k8s")
    assert "socket" in called_names(LIB / "k8s.py") or "create_connection" in (
        LIB / "k8s.py"
    ).read_text()
    assert "_forward_is_up" in (LIB / "k8s.py").read_text()
    source = (LIB / "k8s.py").read_text()
    start = source[source.index("def start_forward") : source.index("def stop_forward")]
    assert "time.sleep" not in start, "start_forward must not settle on a fixed sleep"
    # `port_forward` is the form to reach for, and it must be a context manager
    # so a drill cannot leak a forward past an exception.
    assert hasattr(k8s.port_forward, "__wrapped__"), "port_forward must be a contextmanager"


def test_a_forward_that_never_comes_up_raises_naming_itself() -> None:
    """Driven for real against a target that cannot bind: the refusal must say
    which forward failed, because the whole point is that the error stops being
    attributed to the next thing the drill asked."""
    k8s = _import("k8s")
    with pytest.raises(RuntimeError) as excinfo:
        # A namespace that does not exist: kubectl exits, nothing ever listens.
        k8s.start_forward("svc/nothing", "no-such-namespace-cu-s4", 65533, 9999, timeout=3)
    message = str(excinfo.value)
    assert "svc/nothing" in message and "no-such-namespace-cu-s4" in message


# --------------------------------------------------------------------------
# The record loader.
# --------------------------------------------------------------------------


def test_load_record_refuses_an_absent_record_and_names_what_writes_it() -> None:
    """The bare `json.loads(PATH.read_text())` this replaces answered an absent
    record with a FileNotFoundError five frames deep, naming an absolute path
    and nothing about what should have produced it."""
    load_record = _import("records").load_record
    with pytest.raises(FileNotFoundError) as excinfo:
        load_record(REPO / "automation" / "runs" / "nope.json", produced_by="make store-watch")
    message = str(excinfo.value)
    assert "TRACKED record" in message and "make store-watch" in message


def test_the_optional_record_read_was_deliberately_left_alone() -> None:
    """CU-S4's stated stopping line for the record cluster.

    `store_watch_headroom.py`'s persistence record is genuinely optional — its
    absence is not an error — so it must NOT go through the presence-checking
    loader. Migrating it would turn a correct system red, which is gotcha #50
    arriving through consolidation. Pinned so a later sweep does not "finish the
    job" by breaking it.
    """
    source = (REPO / "scripts" / "store_watch_headroom.py").read_text()
    assert "if PERSISTENCE_RECORD.exists() else {}" in source
    assert "load_record(PERSISTENCE_RECORD" not in source


# --------------------------------------------------------------------------
# The package has to reach the places scripts/ reaches.
# --------------------------------------------------------------------------


def test_the_package_reaches_the_task_image() -> None:
    """CU-S3's guard, inherited by a python package. `.dockerignore`'s rule is
    "the image contains what git contains" and it names no path under
    `scripts/`; the F-026 guards already treat `scripts/` as an image input, so
    editing a lib refuses a stale image rather than running last week's code."""
    excluded = [
        line
        for line in (REPO / ".dockerignore").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#") and "scripts" in line
    ]
    assert not excluded, f".dockerignore excludes something under scripts/: {excluded}"
    for guard in ("run_pipeline.sh", "retrain_schedule.sh"):
        assert "scripts" in (REPO / "scripts" / guard).read_text()


@pytest.mark.parametrize("name", MIGRATED)
def test_a_migrated_script_still_loads_by_file_path(name: str) -> None:
    """The failure this slice was one line away from shipping.

    Several of these files are loaded by the suite through
    `spec_from_file_location`, which puts NOTHING on `sys.path` — so a script
    importing `_lib` without declaring where it lives imports fine under
    `uv run` and dies under the loader that tests use. Each entry point declares
    its lib path the way it already declares `src`; this runs the loader.
    """
    path = REPO / "scripts" / name
    if "_lib" not in path.read_text():
        pytest.skip(f"{name} does not use _lib")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import importlib.util,sys;"
            f"spec=importlib.util.spec_from_file_location('m',{str(path)!r});"
            "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"{name} does not load by file path:\n{result.stderr[-2000:]}"
