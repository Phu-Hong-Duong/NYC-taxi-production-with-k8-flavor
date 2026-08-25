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

    # WATCHDOG_HEAL is forced to "0" rather than merely inherited. It is the flag
    # watchdog.sh exports on its heal path, and a session STARTED by that path
    # carries it for its whole life — so every test here that asserts the
    # ordinary, human-run behaviour of next_session.sh silently became a test of
    # the heal path instead, and two of them went red on a repo where nothing was
    # wrong. Found 2026-08-25 (M9-S12) in a session the watchdog had healed.
    # The tests that DO want the heal path set it explicitly (see below), so
    # pinning the default here makes both intentions visible instead of leaving
    # one of them at the mercy of whoever launched the suite.
    env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}", "WATCHDOG_HEAL": "0"}
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
def _park(tmp_path: Path, env: dict) -> None:
    """Park the sandbox chain on a fork the way a real session does: write, stop."""
    _prime_po_hash(tmp_path, env)
    (tmp_path / "AWAITING_PO.md").write_text("# inbox\n\n## a genuine fork\noptions...\n")
    _run(tmp_path, env)


def test_a_fork_parks_the_chain_and_is_never_auto_resumed(tmp_path):
    """The load-bearing refusal: a DECISION is not an accident."""
    tmp_path, env = _sandbox(tmp_path)
    _park(tmp_path, env)

    assert "RED parked-on-fork" in _wlog(tmp_path)
    assert "decision needed" in _toasts(tmp_path)
    assert not (tmp_path / "automation" / "logs" / "pending_successor").exists(), (
        "the watchdog auto-proceeded past a fork — ADR-010's whole point"
    )


def test_a_park_survives_the_pass_that_detected_it(tmp_path):
    """F-066, replayed: the park that was healed twenty minutes after it worked.

    On 2026-08-24 the program-close park was detected correctly at 06:40,
    alarmed, and then HEALED at 07:00 — because the sensor was an edge detector
    on AWAITING_PO.md's hash and "no change since the last pass" had been left
    to stand for "no unanswered fork". Two passes of park, then a resurrected
    executor booting into a closed, tagged program with no story to execute.

    This is the test that would have caught it: the SECOND pass is where the old
    code went wrong, and every pass after it is the same wrong. One pass proves
    nothing about a latch.
    """
    tmp_path, env = _sandbox(tmp_path)
    _park(tmp_path, env)

    for _ in range(5):
        _run(tmp_path, env)

    log = _wlog(tmp_path)
    assert (tmp_path / "automation" / "logs" / "watchdog_parked").exists(), (
        "the park must latch — a decision does not expire because time passed"
    )
    assert "chain is DEAD" not in log, "a parked chain is not a dead one"
    assert "HEAL —" not in log, (
        "the watchdog healed a deliberate park — F-066, the exact 2026-08-24 defect"
    )
    assert not (tmp_path / "automation" / "logs" / "pending_successor").exists()
    # Rationed: a long park nags, it does not grow the inbox a note per pass.
    assert _toasts(tmp_path).count("Chain parked") == 1
    assert (tmp_path / "AWAITING_PO.md").read_text().count("watchdog: Chain parked") == 1


def test_answering_the_fork_is_what_resumes_the_chain(tmp_path):
    """The latch must be openable, or the fix is just a nicer way to be dead."""
    tmp_path, env = _sandbox(tmp_path)
    _park(tmp_path, env)
    latch = tmp_path / "automation" / "logs" / "watchdog_parked"
    assert latch.exists()

    # The command every AWAITING_PO entry names as the resume. Running it IS
    # the answer, so it is what clears the latch.
    proc = subprocess.run(
        ["bash", str(tmp_path / "automation" / "next_session.sh"), "executor", "15"],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "park latch cleared" in proc.stdout
    assert not latch.exists()
    assert (tmp_path / "automation" / "logs" / "pending_successor").exists()

    _run(tmp_path, env)
    assert "GREEN" in _wlog(tmp_path).splitlines()[-1], "an answered fork must stop parking"


def test_a_heal_may_not_un_park_a_decision(tmp_path):
    """The one actor with a motive to clear the latch must not hold the eraser."""
    tmp_path, env = _sandbox(tmp_path)
    _park(tmp_path, env)
    latch = tmp_path / "automation" / "logs" / "watchdog_parked"

    proc = subprocess.run(
        ["bash", str(tmp_path / "automation" / "next_session.sh"), "executor", "15"],
        cwd=tmp_path, env={**env, "WATCHDOG_HEAL": "1"},
        capture_output=True, text=True, timeout=60,
    )

    assert "refusing to clear the park latch" in proc.stdout
    assert latch.exists(), "a heal cleared a park — the fork policy is walked through again"
    assert not (tmp_path / "automation" / "logs" / "pending_successor").exists()


def test_a_session_running_does_not_mean_the_fork_was_answered(tmp_path):
    """GREEN is an observation about liveness, never about a decision."""
    tmp_path, env = _sandbox(tmp_path)
    _park(tmp_path, env)
    (tmp_path / "automation" / "logs" / "running_session").write_text(
        f"{os.getpid()} executor 2026-08-24T07:00:16Z\n"
    )

    _run(tmp_path, env)

    assert "GREEN — session alive" in _wlog(tmp_path)
    assert (tmp_path / "automation" / "logs" / "watchdog_parked").exists(), (
        "a session that happens to be alive did not answer the PO's question"
    )


def test_a_failed_detached_run_wakes_someone(tmp_path):
    tmp_path, env = _sandbox(tmp_path)
    _prime_po_hash(tmp_path, env)
    status = tmp_path / "automation" / "runs" / "confirmation.status"
    status.write_text("FAILED 2 2026-08-17T15:10:00Z\n")

    _run(tmp_path, env)

    assert "RED run-failed-confirmation" in _wlog(tmp_path)
    assert "FAILED" in _toasts(tmp_path)
    assert not (tmp_path / "automation" / "logs" / "pending_successor").exists()
    # The ack mirrors the KILLED branch's corpse-rewrite: without it, this one
    # status file blocks the heal path on EVERY future pass — which is exactly
    # how a 4-day-old 'FAILED 2' from M7-S4 turned a transient API-error death
    # into a permanently dead chain on 2026-08-24. The original line survives
    # inside the ack, and field 2 is still the exit code for anything reading
    # it (retrain_prediction_check.py does, loosely).
    acked = status.read_text()
    assert acked.startswith("FAILED-ACKED 2 "), "one alarm, then stop blocking the heal path"
    assert "FAILED 2 2026-08-17T15:10:00Z" in acked, "the original line must survive the ack"


def test_an_acked_failure_stops_blocking_the_heal_path(tmp_path):
    """The 2026-08-24 deadlock, replayed: alarm once, then the chain comes back.

    Pass 1 alarms and acks; pass 2 heals. It used to take four, and the two
    extra passes were the watchdog reading its OWN alarm append as a session's
    fork — a false park it then had to be allowed to forget. That decay is what
    let a REAL park be healed (F-066), so red() now re-stamps the baseline and
    the false park is gone at the source rather than waited out.

    The second assertion is the load-bearing one and it is about the LATCH:
    latching a false park would wedge the chain shut on any FAILED run forever,
    which is this deadlock again and worse. Neither half of F-066's fix is
    correct without the other, and this is where that is checked.
    """
    tmp_path, env = _sandbox(tmp_path)
    _prime_po_hash(tmp_path, env)
    (tmp_path / "automation" / "runs" / "confirmation.status").write_text(
        "FAILED 2 2026-08-17T15:10:00Z\n"
    )

    for _ in range(2):
        _run(tmp_path, env)

    assert not (tmp_path / "automation" / "logs" / "watchdog_parked").exists(), (
        "the watchdog latched a park on its own alarm — the chain can never resume"
    )

    # red() writes two log lines per firing (the message, then "toast
    # delivered"), so the alarm count is the toast record's, not the log's.
    assert _toasts(tmp_path).count("Chain: detached run FAILED") == 1, (
        "one failure must alarm exactly once, not once per pass"
    )
    assert "HEAL — [chain] scheduled executor" in _wlog(tmp_path)
    assert (tmp_path / "automation" / "logs" / "pending_successor").exists(), (
        "an acked failure kept blocking the heal path — the 2026-08-24 deadlock is back"
    )


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
    """A notifier that repeats itself gets muted, and a muted alarm is none.

    This used to hold a FAILED status in front of the watchdog twice — a
    condition that no longer recurs, because a failure acks itself after one
    alarm (the 2026-08-24 fix). The recurring condition here is the daily cap,
    which persists exactly as long as the count file does, with the toast
    state primed to say this key rang five minutes ago.
    """
    tmp_path, env = _sandbox(tmp_path)
    _prime_po_hash(tmp_path, env)
    today = time.strftime("%Y-%m-%d")
    (tmp_path / "automation" / "logs" / f"count_{today}").write_text("40\n")
    (tmp_path / "automation" / "logs" / "watchdog_toast_state").write_text(
        f"daily-cap {int(time.time()) - 300}\n"
    )

    _run(tmp_path, env)

    assert "toast suppressed" in _wlog(tmp_path)
    assert _toasts(tmp_path) == "", "the second look at the same condition rang the alarm again"


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


# --------------------------------------------------------------------------
# F-072: the inbox baseline moves with the human's own resume.
# --------------------------------------------------------------------------
def test_a_resume_stamps_the_inbox_baseline_so_a_later_crash_heals(tmp_path):
    """Session (cq)'s 2026-08-25 observation, replayed: entries the PO has
    demonstrably already SEEN (they resumed the chain from one's own footer)
    must not later read as a NEW fork. Before F-072 the baseline was stale
    whenever the inbox changed on passes that never reached step 5, so the
    next idle pass read a session CRASH as a deliberate park — an accident
    dressed as a decision, in the silent direction, and the false park BLOCKS
    the heal (step 5 exits before step 8)."""
    tmp_path, env = _sandbox(tmp_path)
    _park(tmp_path, env)

    # The PO answers the fork (an inbox edit the watchdog cannot observe while
    # anything is alive) and resumes from the entry's own footer.
    with (tmp_path / "AWAITING_PO.md").open("a") as fh:
        fh.write("\n> ANSWERED by the PO: option (b)\n")
    proc = subprocess.run(
        ["bash", str(tmp_path / "automation" / "next_session.sh"), "executor", "15"],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    # The direct property: the baseline now equals the inbox as the human
    # left it.
    digest = hashlib.sha256((tmp_path / "AWAITING_PO.md").read_bytes()).hexdigest()
    stamped = (
        tmp_path / "automation" / "logs" / "watchdog_awaiting_po.sha"
    ).read_text().strip()
    assert stamped == digest, "resuming did not stamp the inbox baseline (F-072)"

    # The behavioural property: the queued session dies before launching (the
    # crash), and the watchdog HEALS rather than parking on the answer the PO
    # already gave. Against the pre-F-072 scheduler this latches a false park.
    (tmp_path / "automation" / "logs" / "pending_successor").unlink()
    _run(tmp_path, env)
    assert "chain is DEAD" in _wlog(tmp_path), _wlog(tmp_path)
    assert not (tmp_path / "automation" / "logs" / "watchdog_parked").exists(), (
        "a session crash after an ANSWERED fork was read as a new park — "
        "an accident dressed as a decision (F-072)"
    )


def test_a_heal_does_not_stamp_the_inbox_baseline(tmp_path):
    """The heal path holds no park-shaped eraser (F-066's asymmetry, kept): a
    heal that stamped the baseline would swallow a fork written by the very
    session whose death it is healing, and the next pass would read the parked
    chain as merely dead."""
    tmp_path, env = _sandbox(tmp_path)
    _prime_po_hash(tmp_path, env)
    before = (tmp_path / "automation" / "logs" / "watchdog_awaiting_po.sha").read_text()
    (tmp_path / "AWAITING_PO.md").write_text(
        "# inbox\n\n## a fork written just before dying\noptions...\n"
    )

    heal_env = dict(env)
    heal_env["WATCHDOG_HEAL"] = "1"
    subprocess.run(
        ["bash", str(tmp_path / "automation" / "next_session.sh"), "executor", "15"],
        cwd=tmp_path, env=heal_env, capture_output=True, text=True, timeout=60,
    )

    after = (tmp_path / "automation" / "logs" / "watchdog_awaiting_po.sha").read_text()
    assert after == before, (
        "the heal path stamped the inbox baseline — it now holds an eraser "
        "for forks it never read (F-072/F-066)"
    )
