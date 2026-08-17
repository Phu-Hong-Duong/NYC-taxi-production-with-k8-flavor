"""Kill the sniper mid-study and watch the study survive — M3-S4's resumability arm.

§9/M3 asks for one thing here: *the study killed mid-run, resumed from Postgres,
trial count continuing, transcript pasted.* A study that lived in the process
would lose every trial to the kill and would look identical from the outside
until the moment somebody needed it not to — which is why this is demonstrated
rather than asserted.

**The drill runs on its own study, and that is deliberate.** It uses the same
code path as the real sniper (same script, same `create_study(...,
load_if_exists=True)`, same storage module), with a study labelled
`resume-drill-<set>` so the kill never lands on a study whose trials are part of
a reported number. A demonstration that costs a real result its trials is a
worse demonstration.

**SIGKILL, not SIGTERM.** A terminate handler could flush state on the way out,
which would prove that our shutdown path works rather than that the storage
does. `kill -9` on the process GROUP takes the sniper and its `kubectl
port-forward` child together, with no chance to write anything — the trials in
Postgres are then the only trials that exist.

The trial counts are read back over a FRESH connection opened by this script
after the child is gone, so the number quoted in the transcript comes from the
database rather than from the memory of the process being tested.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from taxi_mlops.data.config import load_yaml, repo_root
from taxi_mlops.tuning import storage

TUNING_CONFIG = "configs/tuning.yaml"


def _trial_states(name: str) -> dict[str, int]:
    """Ask POSTGRES what it holds — never the process under test."""
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.load_study(study_name=name, storage=storage.storage_url())
    counts: dict[str, int] = {}
    for trial in study.trials:
        counts[trial.state.name] = counts.get(trial.state.name, 0) + 1
    counts["TOTAL"] = len(study.trials)
    return counts


def _drop(name: str) -> None:
    import optuna

    try:
        optuna.delete_study(study_name=name, storage=storage.storage_url())
        print(f"[drill] dropped the previous drill study {name} so the count starts at 0")
    except KeyError:
        print(f"[drill] no previous {name} — starting clean")


def _launch(argv: list[str], log: Path) -> subprocess.Popen:
    handle = log.open("w")
    # Its own process group: the kill below must take the sniper AND the
    # port-forward it spawned, in one signal, with no orderly shutdown.
    return subprocess.Popen(
        argv, stdout=handle, stderr=subprocess.STDOUT, start_new_session=True, cwd=repo_root()
    )


def _wait_for_trials(name: str, want: int, process: subprocess.Popen, timeout_s: float) -> int:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise SystemExit(
                f"[drill] the sniper exited ({process.returncode}) before reaching {want} "
                "trial(s) — read the log named above; the drill proves nothing on a crash"
            )
        try:
            counts = _trial_states(name)
        except Exception:  # the study row does not exist until the first trial starts
            counts = {"TOTAL": 0}
        if counts.get("TOTAL", 0) >= want:
            return counts["TOTAL"]
        time.sleep(2.0)
    raise SystemExit(f"[drill] no {want} trial(s) within {timeout_s:g}s — nothing to kill safely")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", dest="feature_set", default="v1")
    parser.add_argument("--kill-after-trials", type=int, default=3)
    parser.add_argument("--n-trials", type=int, default=8)
    parser.add_argument("--sample-fraction", type=float, default=0.01)
    parser.add_argument("--max-rounds", type=int, default=150)
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    tuning_cfg = load_yaml(TUNING_CONFIG)
    label = f"resume-drill-{args.feature_set}"
    name = storage.study_name(tuning_cfg["study_namespace"], label)
    logs = repo_root() / "automation" / "runs"
    logs.mkdir(parents=True, exist_ok=True)

    sniper = [
        sys.executable, "scripts/optuna_sniper.py", "--set", args.feature_set,
        "--label", label, "--n-trials", str(args.n_trials),
        "--sample-fraction", str(args.sample_fraction),
        "--max-rounds", str(args.max_rounds), "--no-mlflow",
    ]

    print("=" * 78)
    print(f"[drill] study         : {name}")
    print(f"[drill] plan          : run -> kill -9 after {args.kill_after_trials} trial(s) -> "
          f"re-run the SAME command -> read Postgres between every step")
    print(f"[drill] command       : {' '.join(sniper)}")
    print("=" * 78)

    with storage.port_forward():
        _drop(name)
        before = {"TOTAL": 0}

        # --- arm 1: run, then kill -9 mid-study ---------------------------------
        log1 = logs / f"{label}-arm1.log"
        print(f"\n[drill] arm 1 starting; its output -> {log1}")
        first = _launch(sniper, log1)
        reached = _wait_for_trials(name, args.kill_after_trials, first, args.timeout)
        print(f"[drill] Postgres reports {reached} trial(s); killing pid {first.pid} with SIGKILL")
        os.killpg(os.getpgid(first.pid), signal.SIGKILL)
        first.wait(timeout=30)
        print(f"[drill] arm 1 process is gone (returncode {first.returncode} = killed by signal)")

        after_kill = _trial_states(name)
        print(f"[drill] Postgres AFTER the kill, on a fresh connection: {after_kill}")
        if after_kill["TOTAL"] < args.kill_after_trials:
            raise SystemExit("[drill] FAIL: trials did not survive the kill — not durable")

        # --- arm 2: the same command again, no special resume flag --------------
        log2 = logs / f"{label}-arm2.log"
        print(f"\n[drill] arm 2 starting — SAME command, no resume flag; output -> {log2}")
        second = _launch(sniper, log2)
        second.wait(timeout=args.timeout)
        print(f"[drill] arm 2 exited {second.returncode}")
        after_resume = _trial_states(name)
        print(f"[drill] Postgres AFTER the resume: {after_resume}")

    opened_at = _first_trial_number(log2)
    verdict: dict[str, Any] = {
        "study": name,
        "trials_before": before["TOTAL"],
        "trials_at_kill": after_kill["TOTAL"],
        "trials_after_resume": after_resume["TOTAL"],
        "states_after_resume": after_kill and after_resume,
        "arm2_opened_with": opened_at,
        "n_trials_requested": args.n_trials,
        "logs": [str(log1), str(log2)],
    }
    ok = (
        after_kill["TOTAL"] >= args.kill_after_trials
        and after_resume["TOTAL"] > after_kill["TOTAL"]
        and after_resume["TOTAL"] == args.n_trials
    )
    print("\n" + "=" * 78)
    print(
        f"[drill] {after_kill['TOTAL']} trial(s) survived a SIGKILL and the resumed run "
        f"continued to {after_resume['TOTAL']} of {args.n_trials} requested — the count "
        "continued because the trials were never in the process."
    )
    if opened_at is not None:
        print(f"[drill] arm 2 announced it opened the study with {opened_at} existing trial(s)")
    print(f"[drill] {'PASS' if ok else 'FAIL'}")
    print("=" * 78)
    if args.out:
        Path(args.out).write_text(json.dumps(verdict, indent=2) + "\n")
    return 0 if ok else 1


def _first_trial_number(log: Path) -> int | None:
    """What arm 2 said it found — the resumed process's own view, for the transcript."""
    for line in log.read_text(errors="replace").splitlines():
        if "study opened with" in line:
            for word in line.split():
                if word.isdigit():
                    return int(word)
    return None


if __name__ == "__main__":
    raise SystemExit(main())
