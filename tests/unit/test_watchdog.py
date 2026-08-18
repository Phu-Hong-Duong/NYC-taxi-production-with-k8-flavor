"""The watchdog, tested where a real chain cannot be restarted.

Written after 2026-08-17, when an executor ended its turn mid-story without
reaching its exit ritual and the program was simply over: no successor, no
error, no alarm, 38 minutes of silence. The watchdog is the organ that was
missing, and an unwatched watchdog is worse than none — it is a promise.

The distinction every test below exists to protect: the watchdog may restart
an ACCIDENT and must never restart a DECISION. A chain parked on a fork
(exit ritual d) is working correctly, and healing it would walk straight
through the fork policy ADR-010 exists to enforce.

Same method as test_chain_script.py: a sandbox COPY whose repo root is a tmp
dir, whose `next_session.sh` is real, whose `claude` is a shim, and whose
`toast.sh` records instead of ringing. Every assertion is about a watchdog
that really ran and really decided.
"""

import hashlib
import os
import shutil
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AUTOMATION = REPO / "automation"


def _sandbox(tmp_path: Path) -> tuple[Path, dict]:
    """A repo-shaped tmp dir: real watchdog + real scheduler, fake claude + fake toast."""
    auto = tmp_path / "automation"
    (auto / "logs").mkdir(parents=True)
    (auto / "runs").mkdir(parents=True)
    for script in ("watchdog.sh", "next_session.sh", "run_detached.sh"):
        shutil.copy(AUTOMATION / script, auto / script)
        (auto / script).chmod(0o755)
    for role in ("executor", "architect", "rev"):
        (auto / f"{role}_prompt.md").write_text("sandbox prompt\n")
    (tmp_path / "AWAITING_PO.md").write_text("# inbox\n")

    # The alarm records instead of ringing. A test that toasts for real is a
    # test nobody runs twice.
    toast_record = auto / "TOAST_FIRED"
    toast = auto / "toast.sh"
    toast.write_text(
        "#!/usr/bin/env bash\n"
        f'printf "%s\\n%s\\n" "$1" "$2" >> "{toast_record}"\n'
        "echo '[toast] sandbox'\n"
    )
    toast.chmod(0o755)

    marker = tmp_path / "SESSION_LAUNCHED"
    bindir = tmp_path / "bin"
    bindir.mkdir()
    claude = bindir / "claude"
    claude.write_text(f'#!/usr/bin/env bash\necho launched > "{marker}"\n')
    claude.chmod(0o755)

    env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}"}
    return tmp_path, env


def _run(tmp_path: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(tmp_path / "automation" / "watchdog.sh")],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60,
    )


def _wlog(tmp_path: Path) -> str:
    p = tmp_path / "automation" / "logs" / "watchdog.log"
    return p.read_text() if p.exists() else ""


def _toasts(tmp_path: Path) -> str:
    p = tmp_path / "automation" / "TOAST_FIRED"
    return p.read_text() if p.exists() else ""


def _prime_po_hash(tmp_path: Path, env: dict) -> None:
    """Record AWAITING_PO's hash as a PRIOR observation, without running anything.

    The watchdog cannot call a fork on its first ever run — it has no baseline
    to compare against — so every test below needs one already on disk. Priming
    it by running the watchdog once does not work and is worth saying why: that
    run heals the dead sandbox chain and leaves a queued successor behind, so
    the run under test then reports GREEN and never reaches its own condition.
    Seven tests passed vacuously that way before this was written directly.
    """
    digest = hashlib.sha256((tmp_path / "AWAITING_PO.md").read_bytes()).hexdigest()
    (tmp_path / "automation" / "logs" / "watchdog_awaiting_po.sha").write_text(digest + "\n")


# --------------------------------------------------------------------------
# The positive control. Without it every refusal below proves nothing.
# --------------------------------------------------------------------------
def test_a_dead_chain_is_restarted(tmp_path):
    tmp_path, env = _sandbox(tmp_path)
    _prime_po_hash(tmp_path, env)

    proc = _run(tmp_path, env)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "chain is DEAD" in _wlog(tmp_path)
    assert "HEAL — [chain] scheduled executor" in _wlog(tmp_path)
    assert _toasts(tmp_path) == "", "healing an accident is not worth waking someone"
    assert (tmp_path / "automation" / "logs" / "pending_successor").exists()


# --------------------------------------------------------------------------
# The four ways the chain is ALIVE and must be left alone.
# --------------------------------------------------------------------------
def test_stop_file_means_paused_not_broken(tmp_path):
    tmp_path, env = _sandbox(tmp_path)
    (tmp_path / "automation" / "STOP").touch()

    proc = _run(tmp_path, env)

    assert proc.returncode == 0
    assert "paused deliberately" in _wlog(tmp_path)
    assert not (tmp_path / "automation" / "logs" / "pending_successor").exists()
    assert _toasts(tmp_path) == ""


def test_a_running_session_is_left_alone(tmp_path):
    tmp_path, env = _sandbox(tmp_path)
    _prime_po_hash(tmp_path, env)
    # os.getpid() is a pid that is definitely alive: the test runner itself.
    (tmp_path / "automation" / "logs" / "running_session").write_text(
        f"{os.getpid()} executor 2026-08-17T00:00:00Z\n"
    )

    _run(tmp_path, env)

    assert "GREEN — session alive" in _wlog(tmp_path)
    assert not (tmp_path / "automation" / "logs" / "pending_successor").exists()


def test_a_queued_successor_inside_grace_is_left_alone(tmp_path):
    tmp_path, env = _sandbox(tmp_path)
    _prime_po_hash(tmp_path, env)
    (tmp_path / "automation" / "logs" / "pending_successor").write_text("executor queued\n")

    _run(tmp_path, env)

    assert "GREEN — successor queued" in _wlog(tmp_path)


def test_a_detached_run_in_flight_owns_the_handoff(tmp_path):
    """The regression that started all of this: work in flight is not a dead chain."""
    tmp_path, env = _sandbox(tmp_path)
    _prime_po_hash(tmp_path, env)
    (tmp_path / "automation" / "runs" / "confirmation.status").write_text(
        f"RUNNING {os.getpid()} 2026-08-17T14:42:31Z\n"
    )

    _run(tmp_path, env)

    assert "GREEN — detached run 'confirmation' in flight" in _wlog(tmp_path)
    assert not (tmp_path / "automation" / "logs" / "pending_successor").exists(), (
        "restarting the chain under a live run would double-run the work"
    )


# --------------------------------------------------------------------------
# RED: the human is the only one who can clear these. No restart, one alarm.
# --------------------------------------------------------------------------
def test_a_fork_parks_the_chain_and_is_never_auto_resumed(tmp_path):
    """The load-bearing refusal: a DECISION is not an accident."""
    tmp_path, env = _sandbox(tmp_path)
    _prime_po_hash(tmp_path, env)
    (tmp_path / "AWAITING_PO.md").write_text("# inbox\n\n## a genuine fork\noptions...\n")

    _run(tmp_path, env)

    assert "RED parked-on-fork" in _wlog(tmp_path)
    assert "decision needed" in _toasts(tmp_path)
    assert not (tmp_path / "automation" / "logs" / "pending_successor").exists(), (
        "the watchdog auto-proceeded past a fork — ADR-010's whole point"
    )


def test_a_failed_detached_run_wakes_someone(tmp_path):
    tmp_path, env = _sandbox(tmp_path)
    _prime_po_hash(tmp_path, env)
    (tmp_path / "automation" / "runs" / "confirmation.status").write_text(
        "FAILED 2 2026-08-17T15:10:00Z\n"
    )

    _run(tmp_path, env)

    assert "RED run-failed-confirmation" in _wlog(tmp_path)
    assert "FAILED" in _toasts(tmp_path)
    assert not (tmp_path / "automation" / "logs" / "pending_successor").exists()


def test_a_killed_detached_run_is_noticed_and_not_silently_forgotten(tmp_path):
    """RUNNING with a dead pid is exactly what the 2026-08-17 kill left behind."""
    tmp_path, env = _sandbox(tmp_path)
    _prime_po_hash(tmp_path, env)
    status = tmp_path / "automation" / "runs" / "confirmation.status"
    # pid 2**22 is above the default pid_max: reliably nobody.
    status.write_text("RUNNING 4194304 2026-08-17T13:36:00Z\n")

    _run(tmp_path, env)

    assert "RED run-killed-confirmation" in _wlog(tmp_path)
    assert "killed" in _toasts(tmp_path).lower()
    assert status.read_text().startswith("KILLED"), "the corpse must stop reading as RUNNING"


def test_the_daily_cap_is_a_decision_not_a_fault(tmp_path):
    tmp_path, env = _sandbox(tmp_path)
    _prime_po_hash(tmp_path, env)
    today = time.strftime("%Y-%m-%d")
    (tmp_path / "automation" / "logs" / f"count_{today}").write_text("40\n")

    _run(tmp_path, env)

    assert "RED daily-cap" in _wlog(tmp_path)
    assert not (tmp_path / "automation" / "logs" / "pending_successor").exists()


def test_restarting_something_that_keeps_dying_stops_and_asks_for_help(tmp_path):
    """'Try again' is not a strategy. Three failures in the window is an alarm."""
    tmp_path, env = _sandbox(tmp_path)
    _prime_po_hash(tmp_path, env)
    env = {**env, "WATCHDOG_MAX_HEALS": "2"}

    for _ in range(3):
        (tmp_path / "automation" / "logs" / "pending_successor").unlink(missing_ok=True)
        _run(tmp_path, env)

    assert "RED heal-loop" in _wlog(tmp_path)
    assert "restarting is not working" in _toasts(tmp_path).lower()


def test_the_same_red_does_not_toast_every_ten_minutes(tmp_path):
    """A notifier that repeats itself gets muted, and a muted alarm is none."""
    tmp_path, env = _sandbox(tmp_path)
    _prime_po_hash(tmp_path, env)
    (tmp_path / "automation" / "runs" / "c.status").write_text("FAILED 2 x\n")

    _run(tmp_path, env)
    first = _toasts(tmp_path).count("FAILED")
    _run(tmp_path, env)
    second = _toasts(tmp_path).count("FAILED")

    assert first == 1
    assert second == 1, "the second look at the same failure rang the alarm again"
    assert "toast suppressed" in _wlog(tmp_path)


# --------------------------------------------------------------------------
# run_detached.sh — the launcher's own record-keeping (gotcha #48)
# --------------------------------------------------------------------------


def _detach(tmp_path: Path, env: dict, *cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(tmp_path / "automation" / "run_detached.sh"), "job", "--", *cmd],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60,
    )


def _wait_for_status(tmp_path: Path, want: str, timeout: float = 20.0) -> str:
    status = tmp_path / "automation" / "runs" / "job.status"
    deadline = time.time() + timeout
    while time.time() < deadline:
        text = status.read_text() if status.exists() else ""
        if text.startswith(want):
            return text
        time.sleep(0.1)
    return status.read_text() if status.exists() else ""


def test_a_resumed_job_does_not_erase_the_run_it_resumes(tmp_path):
    """Gotcha #48: the launcher used to truncate the log of the run being resumed.

    scripts/automation_track.sh is DESIGNED to be relaunched under the same
    name — it skips every phase whose output JSON already exists — so a
    relaunch is the normal case, not the exception. Truncating on launch meant
    the second run destroyed the transcript of every phase the first one
    completed. The M3-S4 track lost 2h20m of scout and sniper output that way.
    """
    tmp_path, env = _sandbox(tmp_path)
    log = tmp_path / "automation" / "runs" / "job.log"

    _detach(tmp_path, env, "echo", "FIRST-RUN-MARKER")
    assert _wait_for_status(tmp_path, "DONE").startswith("DONE")
    assert "FIRST-RUN-MARKER" in log.read_text()

    result = _detach(tmp_path, env, "echo", "SECOND-RUN-MARKER")
    assert _wait_for_status(tmp_path, "DONE").startswith("DONE")

    assert "SECOND-RUN-MARKER" in log.read_text()
    assert "FIRST-RUN-MARKER" not in log.read_text(), "the live log should be the live run's"
    rotated = tmp_path / "automation" / "runs" / "job.log.1"
    assert rotated.exists(), "the previous run's log was destroyed, not kept"
    assert "FIRST-RUN-MARKER" in rotated.read_text()
    assert "kept as" in result.stdout, "the rotation happened silently"


def test_rotation_keeps_a_bounded_history(tmp_path):
    """Kept, not hoarded: the oldest rotation falls off at KEEP_LOGS."""
    tmp_path, env = _sandbox(tmp_path)
    env = {**env, "KEEP_LOGS": "2"}
    runs = tmp_path / "automation" / "runs"

    for i in range(4):
        _detach(tmp_path, env, "echo", "RUN-" + str(i))
        assert _wait_for_status(tmp_path, "DONE").startswith("DONE")

    assert "RUN-3" in (runs / "job.log").read_text()
    assert "RUN-2" in (runs / "job.log.1").read_text()
    assert "RUN-1" in (runs / "job.log.2").read_text()
    assert not (runs / "job.log.3").exists(), "KEEP_LOGS=2 kept a third rotation"


def test_a_live_job_is_never_rotated_out_from_under_itself(tmp_path):
    """The rotation is only reachable when nothing is RUNNING under that name.

    Renaming a file a live process holds open is how a launcher turns a working
    job into a log nobody can find, so the double-launch guard is what makes
    the rotation safe — this pins the two together.
    """
    tmp_path, env = _sandbox(tmp_path)
    runs = tmp_path / "automation" / "runs"

    _detach(tmp_path, env, "sleep", "5")
    assert _wait_for_status(tmp_path, "RUNNING").startswith("RUNNING")
    first = (runs / "job.log").read_text()

    result = _detach(tmp_path, env, "echo", "SHOULD-NOT-RUN")

    assert "ALREADY RUNNING" in result.stdout
    assert not (runs / "job.log.1").exists(), "a live job's log was rotated"
    assert (runs / "job.log").read_text() == first
