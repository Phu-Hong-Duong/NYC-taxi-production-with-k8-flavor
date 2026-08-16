"""M0-S4: the chain's kill switch, tested where a real session cannot be spawned.

The M0 gate requires a STOP/resume drill, and the drill run by hand covers the
EASY half: STOP present when you ask for a session -> nothing is scheduled. The
half that actually matters to a human at 3am is the other one — STOP created
AFTER a session is already scheduled, while it sits in its `sleep`. That one
cannot be drilled by hand without either launching a real Claude session or
trusting a guard nobody watched work.

So the scheduler is run for real here, against a sandbox COPY of itself whose
repo root is a tmp dir and whose `claude` is a shim that only drops a marker
file. Every assertion below is about a scheduler that really ran, really slept,
and really decided.
"""

import os
import shutil
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CHAIN_SH = REPO / "automation" / "next_session.sh"

DELAY = "2"  # seconds the sandbox session sleeps before it would launch
WAIT = 20  # generous poll ceiling — a loaded CI runner is slower than a laptop


def _sandbox(tmp_path: Path) -> tuple[Path, Path, dict]:
    """Copy the scheduler into tmp_path with a fake `claude` that leaves a marker."""
    (tmp_path / "automation" / "logs").mkdir(parents=True)
    shutil.copy(CHAIN_SH, tmp_path / "automation" / "next_session.sh")
    for role in ("executor", "architect", "rev"):
        (tmp_path / "automation" / f"{role}_prompt.md").write_text("sandbox prompt\n")

    marker = tmp_path / "SESSION_LAUNCHED"
    bindir = tmp_path / "bin"
    bindir.mkdir()
    claude = bindir / "claude"
    claude.write_text(f'#!/usr/bin/env bash\necho launched > "{marker}"\n')
    claude.chmod(0o755)

    env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}"}
    return tmp_path / "automation" / "next_session.sh", marker, env


def _wait_for(path: Path, timeout: int = WAIT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return True
        time.sleep(0.2)
    return False


def test_scheduler_launches_a_session_when_nothing_stops_it(tmp_path):
    """Positive control FIRST: without it, every refusal below proves nothing."""
    script, marker, env = _sandbox(tmp_path)

    proc = subprocess.run(
        ["bash", str(script), "executor", DELAY], capture_output=True, text=True, env=env
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "scheduled executor" in proc.stdout
    assert _wait_for(marker), f"session never launched; stdout was {proc.stdout!r}"


def test_stop_file_refuses_to_schedule_at_all(tmp_path):
    """The drilled half: STOP present when the chain asks for its successor."""
    script, marker, env = _sandbox(tmp_path)
    (tmp_path / "automation" / "STOP").write_text("halt\n")

    proc = subprocess.run(
        ["bash", str(script), "executor", DELAY], capture_output=True, text=True, env=env
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "STOP file present — not scheduling." in proc.stdout
    assert list((tmp_path / "automation" / "logs").iterdir()) == [], "a refusal burned the counter"
    time.sleep(int(DELAY) + 2)
    assert not marker.exists(), "a refused session launched anyway"


def test_stop_file_created_AFTER_scheduling_still_kills_the_pending_session(tmp_path):
    """The half no hand-drill can cover: the kill switch reaching an in-flight session."""
    script, marker, env = _sandbox(tmp_path)

    proc = subprocess.run(
        ["bash", str(script), "executor", DELAY], capture_output=True, text=True, env=env
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    (tmp_path / "automation" / "STOP").write_text("halt mid-flight\n")

    time.sleep(int(DELAY) + 3)
    assert not marker.exists(), "STOP did not reach a session that was already scheduled"


def test_daily_cap_halts_the_chain_and_says_so_where_the_PO_looks(tmp_path):
    """The runaway-chain backstop: it must stop AND leave a note in AWAITING_PO.md."""
    script, marker, env = _sandbox(tmp_path)
    (tmp_path / "AWAITING_PO.md").write_text("# AWAITING_PO\n")

    proc = subprocess.run(
        ["bash", str(script), "executor", DELAY],
        capture_output=True,
        text=True,
        env={**env, "CHAIN_MAX_PER_DAY": "0"},
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "daily cap reached" in proc.stdout
    assert "chain cap" in (tmp_path / "AWAITING_PO.md").read_text()
    time.sleep(int(DELAY) + 2)
    assert not marker.exists(), "the cap did not actually stop the session"
