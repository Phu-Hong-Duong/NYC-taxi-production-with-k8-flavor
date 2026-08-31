"""`kubectl` and the ephemeral port-forward — the two things every drill reopens.

The context is ALWAYS pinned. Every wrapper this replaced spelled
`--context kind-mlops-taxi` (or `KUBE_CONTEXT`) itself, and one that forgot
would run against whatever the developer's current context happens to be —
which on this machine is the same cluster and on somebody else's is not. It is
an environment override rather than a constant so a reader can point at a rebuilt
cluster without editing code.

WHAT DELIBERATELY DOES NOT LIVE HERE: anything that decides. These helpers run a
command and hand back what it said; the reading of an answer belongs to the
caller that knows what it asked.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import time
from collections.abc import Iterator

#: The kind cluster every script in this repo talks to. Overridable so a reader
#: survives a PO-sanctioned rebuild under another name.
CONTEXT = os.environ.get("KUBE_CONTEXT", "kind-mlops-taxi")


def kubectl_run(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run kubectl and hand back the WHOLE result — returncode, stdout, stderr.

    For callers that read a failure rather than raise on one: `store_watch.py`
    reports "I could not read DBSIZE" as a measurement (M9-S2's inversion of
    A-4's refusal rule), which it cannot do if a non-zero exit throws.
    """
    return subprocess.run(  # noqa: S603
        ["kubectl", "--context", CONTEXT, *args],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def kubectl(*args: str, check: bool = True, stdin: str | None = None) -> str:
    """Run kubectl and return stripped stdout; raise on failure unless `check=False`.

    The common case. `check=False` returns stdout even on failure — several
    callers ask questions whose "no" is an empty string ("is there a pod with
    this label?") and want the empty string, not an exception.
    """
    result = kubectl_run(*args, stdin=stdin)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"kubectl {' '.join(args)} -> exit {result.returncode}: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def _forward_is_up(process: subprocess.Popen, deadline: float, local: int) -> bool:
    """Has the forward actually started listening? Asked, never assumed."""
    import socket

    while time.time() < deadline:
        if process.poll() is not None:
            return False
        with contextlib.suppress(OSError), socket.create_connection(
            ("127.0.0.1", local), timeout=0.5
        ):
            return True
        time.sleep(0.2)
    return False


@contextlib.contextmanager
def port_forward(
    target: str, namespace: str, local: int, remote: int, timeout: float = 20.0
) -> Iterator[subprocess.Popen]:
    """An ephemeral `kubectl port-forward`, waited for and always torn down.

    **It waits rather than sleeps, and that is the one behaviour change CU-S4
    made here.** The copies this replaced slept a fixed 3 or 4 seconds and then
    proceeded regardless, so a forward that never came up produced a connection
    error attributed to whatever the drill asked next — the failure lands on the
    wrong component, which is the shape this program keeps paying for (#55, #70).
    Asking a socket instead is strictly stronger in both directions: a forward
    that is ready in 0.3 s stops costing four seconds, and one that is not ready
    at all raises HERE, naming itself.

    The local port must come from `_lib.ports` — see that module for why a
    number chosen per file is coordination that degrades silently.
    """
    process = subprocess.Popen(  # noqa: S603
        [
            "kubectl", "--context", CONTEXT, "-n", namespace,
            "port-forward", target, f"{local}:{remote}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        if not _forward_is_up(process, time.time() + timeout, local):
            raise RuntimeError(
                f"the port-forward {target} {local}:{remote} in namespace "
                f"{namespace} never started listening within {timeout:.0f}s "
                f"(exit code {process.poll()}). Nothing downstream of this ran, "
                "so any error you were about to read would have named the wrong "
                "component."
            )
        yield process
    finally:
        process.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=5)
