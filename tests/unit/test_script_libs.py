"""The two shell libraries the gates and the red-team drills share (CU-S3).

Eight gates carried a byte-identical counting harness and eight record-editing
drills carried a byte-identical snapshot/restore scaffold. Consolidating them
moved two properties out of sixteen files and into two, so the guards that used
to pin the per-file copies are RE-DERIVED here — to the lib-level property,
never widened away (gotcha #50). The per-file tests still assert that each gate
and each drill USES the lib; this file asserts what the lib does.

Most of what follows RUNS the library rather than reading it. The old pins were
text (`"trap restore EXIT" in body`), which is what a check looks like when the
implementation is in the file under test. With one implementation there is no
reason to settle for that: a drill that traps and restores can be watched doing
it, including on the path that matters — an abnormal exit.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest
from conftest import REPO, without_comments

HARNESS = REPO / "scripts" / "lib" / "verify_harness.sh"
RESTORE = REPO / "scripts" / "lib" / "redteam_restore.sh"
ISVC = REPO / "scripts" / "lib" / "isvc_deploy.sh"

GATES = [REPO / "scripts" / f"verify_m{n}.sh" for n in range(2, 10)]
DRILLS = [REPO / "scripts" / f"verify_m{n}_redteam.sh" for n in range(3, 10)] + [
    REPO / "scripts" / "gate_margin_redteam.sh"
]
# Every script that reaches the deploy skeleton. deploy_serving.sh is on the
# list and uses exactly one function from it — it installs the platform and no
# InferenceService, but the route port is the same fact about the same file.
ISVC_CALLERS = [
    REPO / "scripts" / f"{name}.sh"
    for name in (
        "deploy_champion",
        "deploy_shadow",
        "deploy_canary",
        "deploy_transformer",
        "deploy_serving",
    )
]


def _bash(script: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", script], cwd=cwd, capture_output=True, text=True, timeout=60
    )


# --------------------------------------------------------------------------
# The libraries exist, parse, and are sourced rather than executed.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("lib", [HARNESS, RESTORE, ISVC], ids=lambda p: p.name)
def test_the_library_parses(lib: Path) -> None:
    """`bash -n` is the cheapest possible guard and it covers the failure a
    sourced file has that a standalone script does not: a syntax error here
    takes sixteen callers down at once."""
    assert lib.exists(), f"{lib.name} is missing — sixteen scripts source it"
    assert _bash(f"bash -n {lib}", REPO).returncode == 0, f"{lib.name} does not parse"


@pytest.mark.parametrize("lib", [HARNESS, RESTORE, ISVC], ids=lambda p: p.name)
def test_the_library_says_what_deliberately_does_not_live_in_it(lib: Path) -> None:
    """A shared file's real risk is the next consolidation, not this one. Both
    headers name what must stay per-caller — the gates' legs and verdict blocks,
    the drills' plants and assertions — so a future session moving one of those
    in has to delete the sentence saying not to."""
    header = lib.read_text().split("\n\n")[0] + lib.read_text()
    assert "DELIBERATELY DOES NOT LIVE HERE" in header


def test_the_libraries_reach_the_task_image() -> None:
    """CU-S3 created this repo's first scripts→scripts source edge, and a sourced
    file that does not travel is a caller that dies at run time rather than at
    build time. `.dockerignore`'s rule is "the image contains what git contains"
    and it names no path under `scripts/`; the F-026 guard already treats
    `scripts/` as an image input, so an edit here refuses a stale image."""
    excluded = [
        line for line in (REPO / ".dockerignore").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#") and "scripts" in line
    ]
    assert not excluded, f".dockerignore excludes something under scripts/: {excluded}"
    for guarded in (REPO / "scripts" / "run_pipeline.sh", REPO / "scripts" / "retrain_schedule.sh"):
        assert "docker scripts" in guarded.read_text(), (
            f"{guarded.name}'s F-026 IMAGE_PATHS no longer covers scripts/ — an edit "
            "to a sourced lib would not refuse a stale image"
        )


# --------------------------------------------------------------------------
# verify_harness.sh — the counters, watched counting.
# --------------------------------------------------------------------------


def test_consume_counts_verdicts_and_fail_moves_the_counter() -> None:
    """The harness's whole job: PASS|/FAIL| lines become counts, anything else
    becomes a note, and only FAIL moves FAILS. Run, not read."""
    out = _bash(
        f'source {HARNESS}\n'
        'consume < <(printf "PASS|a\\nFAIL|b\\nsomething else\\nPASS|c\\n")\n'
        'echo "FAILS=$FAILS CONSUMED=$CONSUMED"\n',
        REPO,
    )
    assert "FAILS=1 CONSUMED=3" in out.stdout, out.stdout + out.stderr
    assert "something else" in out.stdout, "a non-verdict line was swallowed instead of noted"


def test_expect_verdicts_fails_a_leg_that_never_ran() -> None:
    """M2-S5's rule, and the reason it exists: a leg that dies on import emits
    zero verdicts, which without this guard is indistinguishable from a leg with
    nothing to say."""
    out = _bash(
        f'source {HARNESS}\n'
        'consume < <(printf "")\n'
        'expect_verdicts 3 "the leg"\n'
        'echo "FAILS=$FAILS"\n',
        REPO,
    )
    assert "FAILS=1" in out.stdout, out.stdout + out.stderr
    assert "expected at least 3" in out.stderr, "the failure does not say what was expected"


def test_a_pipe_would_lose_the_count_which_is_why_the_idiom_is_pinned() -> None:
    """The negative half, MEASURED rather than asserted in a comment. `… |
    consume` runs the function in a subshell, so its FAIL is counted and then
    discarded at the closing brace — the gate reports GREEN over a red leg. This
    is the defect `consume < <(` prevents, and the per-gate tests pin the idiom
    at every call site."""
    out = _bash(
        f'source {HARNESS}\n'
        'printf "FAIL|b\\n" | consume\n'
        'echo "FAILS=$FAILS"\n',
        REPO,
    )
    assert "FAILS=0" in out.stdout, (
        "a piped consume kept the count — the subshell hazard the idiom guards "
        "against no longer exists, so the pin should be re-argued, not kept"
    )


@pytest.mark.parametrize("gate", GATES, ids=lambda p: p.name)
def test_every_gate_sources_the_harness_and_defines_none_of_it_itself(gate: Path) -> None:
    """The migration's own invariant: one home. A gate that re-declared `FAILS=0`
    or its own `consume()` would shadow the lib and be a copy again."""
    body = without_comments(gate)
    assert "scripts/lib/verify_harness.sh" in body, f"{gate.name} does not source the harness"
    for redeclared in ("FAILS=0", "consume() {", "expect_verdicts() {", "pass() {"):
        assert redeclared not in body, f"{gate.name} re-declares {redeclared!r} — two homes"


# --------------------------------------------------------------------------
# redteam_restore.sh — the scaffold, watched restoring.
# --------------------------------------------------------------------------


def test_the_scaffold_restores_from_a_byte_copy_on_an_ABNORMAL_exit(tmp_path: Path) -> None:
    """The property the old per-file pins approximated with `"trap restore EXIT"
    in body`: a drill that dies mid-tamper still leaves the record as it found
    it. Here it is watched — the fake drill tampers and then exits 1 without
    ever calling the restore itself."""
    target = tmp_path / "record.json"
    target.write_text('{"measured": 13.75}\n')
    before = hashlib.sha256(target.read_bytes()).hexdigest()

    rc = _bash(
        'set -uo pipefail\n'
        'REDTEAM_LABEL="[test-drill]"\n'
        f'source {RESTORE}\n'
        f'redteam_snapshot "{target}"\n'
        f'printf "TAMPERED" > "{target}"\n'
        'exit 1\n',
        REPO,
    )
    assert rc.returncode == 1
    assert hashlib.sha256(target.read_bytes()).hexdigest() == before, (
        "the EXIT trap did not put the record back — a crashed drill damages evidence"
    )
    assert "restored" in rc.stdout, "the restore happened silently; a drill must say so"


def test_the_scaffold_verifies_the_restore_by_sha_rather_than_trusting_cp(tmp_path: Path) -> None:
    """`sha256sum` was the old pin; the property behind it is that a put-back
    which did not put anything back must not read as success.

    The arm is chosen so `cp` RETURNS 0 and the restore is still wrong: the
    target is replaced by a directory, which `cp` happily copies *into*. An
    exit-code check would have called that a restore. The sha check is the only
    thing standing between a drill and silently damaged evidence."""
    target = tmp_path / "record.json"
    target.write_text('{"measured": 13.75}\n')

    out = _bash(
        'set -uo pipefail\n'
        'REDTEAM_LABEL="[test-drill]"\n'
        f'source {RESTORE}\n'
        f'redteam_snapshot "{target}"\n'
        f'rm "{target}" && mkdir "{target}"\n'
        'redteam_restore\n',
        REPO,
    )
    assert "RESTORE DID NOT MATCH" in out.stderr, out.stdout + out.stderr


def test_a_restore_that_cannot_run_names_the_byte_copy_it_kept(tmp_path: Path) -> None:
    """The other failure branch: `cp` itself fails. The message must name the
    temp copy FIRST — it was taken at step 0 of this run, so it is right under
    every condition, where `git checkout --` is right only if the file was
    committed as the drill found it."""
    target = tmp_path / "record.json"
    target.write_text('{"measured": 13.75}\n')

    out = _bash(
        'set -uo pipefail\n'
        'REDTEAM_LABEL="[test-drill]"\n'
        f'source {RESTORE}\n'
        f'redteam_snapshot "{target}"\n'
        f'chmod 400 "{target}"\n'
        'redteam_restore\n'
        f'chmod 600 "{target}"\n',
        REPO,
    )
    assert "COULD NOT RESTORE" in out.stderr, out.stdout + out.stderr
    assert "Copy it back by hand" in out.stderr, (
        "a failed restore does not name the byte copy it kept — the one recovery "
        "that is right under every condition"
    )


def test_assert_restored_reports_byte_identity_rather_than_claiming_it(tmp_path: Path) -> None:
    """Step 3 of every drill. It must PASS on an honest restore and it must be
    able to fail: the second arm proves the comparison is real by moving the
    file after the scaffold has already restored and disarmed."""
    target = tmp_path / "record.json"
    target.write_text('{"measured": 13.75}\n')

    good = _bash(
        'set -uo pipefail\n'
        'REDTEAM_LABEL="[test-drill]"\n'
        f'source {RESTORE}\n'
        f'redteam_snapshot "{target}"\n'
        f'printf "TAMPERED" > "{target}"\n'
        'redteam_assert_restored\n'
        'echo "PROBLEMS=$PROBLEMS"\n',
        REPO,
    )
    assert "byte-identical to what the drill found" in good.stdout, good.stdout + good.stderr
    assert "PROBLEMS=0" in good.stdout

    bad = _bash(
        'set -uo pipefail\n'
        'REDTEAM_LABEL="[test-drill]"\n'
        f'source {RESTORE}\n'
        f'redteam_snapshot "{target}"\n'
        'redteam_restore\n'
        f'printf "LATE TAMPER" > "{target}"\n'
        'redteam_assert_restored\n'
        'echo "PROBLEMS=$PROBLEMS"\n',
        REPO,
    )
    assert "PROBLEMS=1" in bad.stdout, (
        "the byte-identity check cannot fail — it is a claim, not a comparison"
    )


def test_the_scaffold_refuses_to_load_without_a_label(tmp_path: Path) -> None:
    """`say` prints the drill's name. An unset label would print an empty prefix
    on every line of a destructive drill's transcript, so the lib refuses at
    source time rather than degrading (F-048's rule)."""
    out = _bash(f"unset REDTEAM_LABEL; source {RESTORE}; echo LOADED", REPO)
    assert "LOADED" not in out.stdout
    assert "REDTEAM_LABEL" in out.stderr


# --------------------------------------------------------------------------
# isvc_deploy.sh — the deploy skeleton, watched deploying.
# --------------------------------------------------------------------------
# Everything below RUNS the library. The per-file pins these replace read source
# text (`text.index("rollout status") < text.index("--for=jsonpath=")`), which
# is what a check looks like when the implementation is spread over four files.
# With one implementation the order can be read off what was actually INVOKED.


def _fake_kubectl(tmp_path: Path) -> Path:
    """A `kubectl` that records its argv and succeeds. On PATH, so the lib's own
    `KUBECTL` array reaches it without the test rewriting the array's shape."""
    log = tmp_path / "kubectl.log"
    shim = tmp_path / "kubectl"
    shim.write_text(f'#!/usr/bin/env bash\necho "$*" >> "{log}"\nexit 0\n')
    shim.chmod(0o755)
    return log


def test_the_readiness_waits_run_in_the_order_the_false_green_forced(tmp_path: Path) -> None:
    """gotcha #71 and F-036, asserted on INVOCATIONS rather than on source text.

    `rollout status` must be called before the InferenceService-level wait: on a
    re-deploy the isvc's Ready condition is satisfied by the pod being REPLACED,
    so an isvc-first wait returns while the new pod is still `Init:0/1` and the
    accept check interrogates the predecessor. And the second leg must be
    `--for=jsonpath=`, never `--for=condition=`, which kubectl v1.36 cannot
    satisfy while KServe leaves observedGeneration behind."""
    log = _fake_kubectl(tmp_path)
    out = _bash(
        'set -euo pipefail\n'
        f'export PATH="{tmp_path}:$PATH"\n'
        'KUBECTL=(kubectl)\n'
        f'source {ISVC}\n'
        'isvc_wait_ready ns my-isvc 5m\n',
        REPO,
    )
    assert out.returncode == 0, out.stdout + out.stderr
    calls = log.read_text().splitlines()
    rollout = [i for i, c in enumerate(calls) if "rollout status" in c]
    isvc_wait = [i for i, c in enumerate(calls) if " wait " in f" {c} "]
    assert rollout, "no rollout was waited on at all"
    assert isvc_wait, "there is no InferenceService-level readiness wait"
    assert max(rollout) < min(isvc_wait), (
        f"the rollout must be waited on FIRST; invocations were {calls}"
    )
    assert any("--for=jsonpath=" in c for c in calls)
    assert not any("--for=condition=" in c for c in calls), (
        "F-036: the condition form is unsatisfiable on every KServe re-deploy"
    )
    assert any("deploy/my-isvc-predictor" in c for c in calls), (
        "the default component is `predictor` and it was not waited on"
    )


def test_an_isvc_with_two_deployments_waits_on_both(tmp_path: Path) -> None:
    """deploy_transformer.sh's case. An isvc carrying a transformer has TWO
    Deployments, and waiting on one of them is gotcha #71 with the other half
    unwatched — so the component list is explicit and this proves it is used."""
    log = _fake_kubectl(tmp_path)
    out = _bash(
        'set -euo pipefail\n'
        f'export PATH="{tmp_path}:$PATH"\n'
        'KUBECTL=(kubectl)\n'
        f'source {ISVC}\n'
        'isvc_wait_ready ns my-isvc 5m predictor transformer\n'
        'echo REACHED_END\n',
        REPO,
    )
    # The explicit-components path is where a `[[ … ]] && default` would have
    # returned 1 under the callers' own `set -e`, so the end of the script is
    # asserted rather than only the log's contents.
    assert out.returncode == 0 and "REACHED_END" in out.stdout, out.stdout + out.stderr
    calls = log.read_text()
    assert "deploy/my-isvc-predictor" in calls and "deploy/my-isvc-transformer" in calls
    assert calls.index("my-isvc-predictor") < calls.index("my-isvc-transformer")


def test_the_route_wait_FAILS_on_timeout_rather_than_falling_through(tmp_path: Path) -> None:
    """The behaviour CU-S5 changed, and the reason it is the strictest of the
    three copies rather than the average of them. `deploy_transformer.sh`'s copy
    polled sixty times and then fell through silently into its accept check, so
    an unroutable transformer reported as a failed accept — a confusing failure
    blaming the wrong component (gotcha #55's family). A wait that gives up
    quietly is not a wait."""
    curl = tmp_path / "curl"
    curl.write_text("#!/usr/bin/env bash\nexit 7\n")  # 7 == could not connect
    curl.chmod(0o755)
    out = _bash(
        'set -uo pipefail\n'
        f'export PATH="{tmp_path}:$PATH"\n'
        f'source {ISVC}\n'
        'isvc_wait_route http://localhost:8081/ready my-host.local 0 "kubectl get ingress x"\n'
        'echo "FELL THROUGH"\n',
        REPO,
    )
    assert "FELL THROUGH" not in out.stdout, "the wait gave up and let the caller continue"
    assert out.returncode == 1, f"expected exit 1, got {out.returncode}"
    assert "never became routable" in out.stderr
    assert "kubectl get ingress x" in out.stderr, (
        "a failed route wait must name what to look at — the pod is fine and the "
        "Ingress is the suspect, which is not obvious from a 404"
    )


def test_the_route_wait_sends_the_Host_header_the_next_step_will_send(tmp_path: Path) -> None:
    """F-037's point. Every route here is host-based, so a probe without the
    Host header measures the default server block and not the service — it would
    pass while the isvc's own host 404s."""
    log = tmp_path / "curl.log"
    curl = tmp_path / "curl"
    curl.write_text(f'#!/usr/bin/env bash\necho "$*" >> "{log}"\nexit 0\n')
    curl.chmod(0o755)
    out = _bash(
        'set -euo pipefail\n'
        f'export PATH="{tmp_path}:$PATH"\n'
        f'source {ISVC}\n'
        'isvc_wait_route http://localhost:8081/ready my-host.local 30 "hint"\n',
        REPO,
    )
    assert out.returncode == 0, out.stdout + out.stderr
    assert "Host: my-host.local" in log.read_text()
    assert "ok  my-host.local answers" in out.stdout, "a passing wait must say so"


def test_the_alias_guard_exits_2_and_prints_the_callers_own_argument() -> None:
    """The mechanism is shared and the sentence is not. Four deploys cite four
    different laws here; the guard prints whatever trailing lines it is handed,
    so a shared file cannot flatten them into one."""
    out = _bash(
        'set -uo pipefail\n'
        f'source {ISVC}\n'
        'isvc_assert_alias_unmoved 2 3 "SHADOW deploy" "M6 law 3: nothing promotes."\n'
        'echo "CONTINUED"\n',
        REPO,
    )
    assert out.returncode == 2, f"a moved alias must exit 2, got {out.returncode}"
    assert "CONTINUED" not in out.stdout, "the guard warned instead of stopping"
    assert "@champion moved from 2 to 3 during a SHADOW deploy" in out.stderr
    assert "M6 law 3: nothing promotes." in out.stderr, "the caller's citation was dropped"


def test_the_alias_guard_is_silent_and_returns_when_nothing_moved() -> None:
    """The other half, and the one a guard that always fired would break: an
    honest deploy must pass through it without a word."""
    out = _bash(
        'set -euo pipefail\n'
        f'source {ISVC}\n'
        'isvc_assert_alias_unmoved 2 2 "DEPLOY" "some law"\n'
        'echo "CONTINUED"\n',
        REPO,
    )
    assert out.returncode == 0 and "CONTINUED" in out.stdout
    assert "some law" not in out.stderr, "an unmoved alias printed a failure argument"


def test_the_route_port_is_read_from_the_kind_config_and_matches_the_committed_one() -> None:
    """gotcha #52: derive, never type. Run against the real file, so this also
    fails if the committed kind config stops publishing container port 80 —
    which is the event that would silently break every deploy's accept check."""
    out = _bash(
        f'source {ISVC}\n'
        f'isvc_route_port "{REPO}/infra/kind/kind-config.yaml"\n',
        REPO,
    )
    assert out.returncode == 0, out.stdout + out.stderr
    assert out.stdout.strip() == "8081", out.stdout


def test_the_route_port_REFUSES_a_config_that_publishes_no_route(tmp_path: Path) -> None:
    """F-048's rule applied to a port: an unresolvable value must fail loudly
    naming itself, never resolve to something plausible. A default of 8081 here
    would keep every deploy's accept check pointing at a route that does not
    exist on a cluster built from the edited config."""
    cfg = tmp_path / "kind-config.yaml"
    cfg.write_text("nodes:\n  - role: control-plane\n")
    out = _bash(f'source {ISVC}\nisvc_route_port "{cfg}"\n', REPO)
    assert out.returncode != 0
    assert "no extraPortMapping publishes containerPort 80" in out.stderr
    assert out.stdout.strip() == "", "a refusal printed a port anyway"


@pytest.mark.parametrize("caller", ISVC_CALLERS, ids=lambda p: p.name)
def test_every_deploy_uses_the_skeleton_and_defines_none_of_it_itself(caller: Path) -> None:
    """The per-caller half of the re-derived property, and the one that keeps
    the migration from being undone one file at a time. A deploy that grew back
    its own `champion_version()` or its own heredoc would be a copy again — and
    the copy would look right, which is exactly how the transformer's two drifted
    to cwd-relative paths without anyone noticing."""
    body = without_comments(caller)
    assert "scripts/lib/isvc_deploy.sh" in body, f"{caller.name} does not source the skeleton"
    for redeclared in (
        "champion_version() {",
        "isvc_route_port() {",
        "extraPortMappings",
        "--for=jsonpath=",
        "--for=condition=",
    ):
        assert redeclared not in body, f"{caller.name} re-declares {redeclared!r} — two homes"


@pytest.mark.parametrize("drill", DRILLS, ids=lambda p: p.name)
def test_every_drill_uses_the_scaffold_and_defines_none_of_it_itself(drill: Path) -> None:
    """The per-drill half of the re-derived property. Each drill must source the
    scaffold, take its snapshot (which is what arms the trap), and end by
    asserting byte-identity — and must not carry its own copy of any of it."""
    body = without_comments(drill)
    assert "scripts/lib/redteam_restore.sh" in body, f"{drill.name} does not source the scaffold"
    assert "redteam_snapshot " in body, f"{drill.name} never snapshots — nothing arms the trap"
    assert "redteam_assert_restored" in body, (
        f"{drill.name} never proves it put the record back"
    )
    for redeclared in ("restore() {", "trap restore EXIT", 'BACKUP="$(mktemp)"'):
        assert redeclared not in body, f"{drill.name} re-declares {redeclared!r} — two homes"
