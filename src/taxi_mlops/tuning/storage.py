"""Optuna's study storage: the one Postgres, reached without publishing a port.

**Why a database at all.** A study in a local file (or in memory) cannot answer
the question §9/M3 asks it to answer — kill the process, start it again, and
watch the trial count continue. That property is the whole point of the sniper
arm, and it lives in the storage layer or nowhere.

**Why the DSN is built here and not in `configs/tuning.yaml`.** That file says
`storage: postgres` and carries no DSN, by its own law. A connection string is a
credential wearing a URL's clothes: put it in a config and it is in git; put it
in argv and it is in `ps` and in every shell history. So the password is read
from the gitignored `.env` that `scripts/platform_secrets.sh` owns (the same
chain of custody `tracking.py` uses), assembled in memory, and never printed —
`describe()` exists so a log can say which server it reached without saying how.

**Why a port-forward and not a NodePort.** CLAUDE.md's port family annotates
5432 *in-cluster only*, and kind publishes host ports at cluster-CREATE time
only: adding one means `make cluster-down && make cluster-up`, which takes the
PVCs — and with them MLflow's backend database, the registry, and the champion.
A rebuild is not a price a tuning story gets to pay. The other in-cluster path
this repo already uses (`kubectl exec` + psql on stdin, M1-S4) carries CSV, not
a live SQLAlchemy session, so it cannot serve Optuna either.

So the sniper opens a `kubectl port-forward` for as long as it runs and closes
it on the way out. The forward is a CLIENT-side tunnel on the reserved 5432 —
nothing is published, nothing survives the process, and killing the process
(which the resume drill does on purpose) takes the tunnel with it while leaving
every trial safely in Postgres. That asymmetry is the demonstration.
"""

from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

from ..training.tracking import load_env

#: The port family's Postgres entry (CLAUDE.md). The forward binds the number
#: the family already reserves, so `make ports` still describes the truth.
DEFAULT_LOCAL_PORT = 5432
DEFAULT_NAMESPACE = "platform"
DEFAULT_SERVICE = "svc/postgres"
DEFAULT_DATABASE = "optuna"


class StorageConfigError(RuntimeError):
    """The study storage cannot be reached honestly. Names the fix, never the secret."""


def storage_url(
    *,
    env_file: Path | None = None,
    host: str = "127.0.0.1",
    port: int = DEFAULT_LOCAL_PORT,
    database: str = DEFAULT_DATABASE,
) -> str:
    """The SQLAlchemy URL Optuna connects with. Assembled in memory, never logged."""
    env = load_env(env_file)
    user = env.get("OPTUNA_DB_USER")
    password = env.get("OPTUNA_DB_PASSWORD")
    if not user or not password:
        raise StorageConfigError(
            "`.env` has no OPTUNA_DB_USER / OPTUNA_DB_PASSWORD. They are ADDITIVE keys "
            "in scripts/platform_secrets.sh and the role is converged by "
            "scripts/postgres_databases.sh — run `make deploy-platform` (D-002's recipe)."
        )
    # psycopg 3 explicitly: SQLAlchemy 2's default `postgresql://` still means
    # psycopg2, which this project does not install.
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"


#: How often a running trial stamps "I am alive" into Postgres, in seconds, and
#: how long a stamp may go stale before the trial is declared dead. Both are
#: knobs on `rdb_storage` rather than constants at the call site because the
#: resume drill needs a short pair to WATCH the reaping happen, and a real study
#: wants a long one so a slow trial is never mistaken for a dead process.
DEFAULT_HEARTBEAT_S = 60
DEFAULT_GRACE_MULTIPLIER = 3


def rdb_storage(
    *,
    heartbeat_interval: int = DEFAULT_HEARTBEAT_S,
    grace_period: int | None = None,
    max_retry: int = 1,
    env_file: Path | None = None,
    port: int = DEFAULT_LOCAL_PORT,
) -> object:
    """The study storage, with a heartbeat — because the first drill found a zombie.

    The kill-and-resume drill (M3-S4) killed the sniper with SIGKILL, and the
    resume did exactly what §9/M3 asks: the trial count continued. It also left
    something the transcript would not have shown without looking: the trial that
    was mid-fit at the moment of the kill stayed **RUNNING in Postgres forever**.
    Optuna has no way to know the difference between a process that is thinking
    and a process that no longer exists, so that trial is never completed, never
    retried, and never counted as failed — while still occupying a slot in every
    "how many trials do we have" arithmetic that follows.

    A heartbeat is the answer, and it is Optuna's own: a running trial stamps the
    row, `study.optimize` fails trials whose stamp has gone stale by more than
    `grace_period`, and `RetryFailedTrialCallback` re-enqueues them with the same
    parameters. The resumed study then does not merely continue — it recovers.
    """
    import optuna
    from optuna.storages import RetryFailedTrialCallback

    return optuna.storages.RDBStorage(
        url=storage_url(env_file=env_file, port=port),
        heartbeat_interval=heartbeat_interval,
        grace_period=grace_period or heartbeat_interval * DEFAULT_GRACE_MULTIPLIER,
        failed_trial_callback=RetryFailedTrialCallback(max_retry=max_retry),
    )


def describe(*, host: str = "127.0.0.1", port: int = DEFAULT_LOCAL_PORT) -> str:
    """What a log may say about the storage: where, not how."""
    return f"postgresql+psycopg://<optuna>:<redacted>@{host}:{port}/{DEFAULT_DATABASE}"


def _accepting(host: str, port: int, timeout: float = 0.5) -> bool:
    with contextlib.suppress(OSError), socket.create_connection((host, port), timeout=timeout):
        return True
    return False


@contextlib.contextmanager
def port_forward(
    *,
    namespace: str = DEFAULT_NAMESPACE,
    service: str = DEFAULT_SERVICE,
    local_port: int = DEFAULT_LOCAL_PORT,
    remote_port: int = 5432,
    context: str | None = None,
    timeout_s: float = 30.0,
) -> Iterator[int]:
    """Hold a `kubectl port-forward` open for the body, and close it after.

    Re-uses an already-open forward if something is already listening: the
    resume drill runs two processes back to back and a second forward on the
    same port would die with "address already in use" — a failure about
    plumbing, in the middle of a demonstration about state.
    """
    if _accepting("127.0.0.1", local_port):
        print(f"[storage] port {local_port} already accepts connections — reusing it")
        yield local_port
        return

    argv = ["kubectl"]
    kube_context = context or os.environ.get("KUBE_CONTEXT", "kind-mlops-taxi")
    argv += ["--context", kube_context]
    argv += ["-n", namespace, "port-forward", service, f"{local_port}:{remote_port}"]
    print(f"[storage] {' '.join(argv)}")
    process = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if process.poll() is not None:
                stderr = (process.stderr.read() or b"").decode(errors="replace")
                raise StorageConfigError(
                    f"kubectl port-forward exited {process.returncode} before the tunnel "
                    f"was ready: {stderr.strip() or '(no stderr)'}"
                )
            if _accepting("127.0.0.1", local_port):
                print(f"[storage] tunnel up on 127.0.0.1:{local_port} -> {namespace}/{service}")
                break
            time.sleep(0.25)
        else:
            raise StorageConfigError(
                f"port-forward to {namespace}/{service} did not accept a connection on "
                f"127.0.0.1:{local_port} within {timeout_s:g}s"
            )
        yield local_port
    finally:
        process.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=5)
        if process.poll() is None:
            process.kill()
        print("[storage] tunnel closed")


def study_name(namespace: str, label: str) -> str:
    """Gotcha #17: every study carries its milestone namespace in its NAME.

    One Postgres serves this whole program, and a study called `sniper` would
    collide with M7's retune the first time somebody re-used the obvious word.
    The namespace comes from `configs/tuning.yaml: study_namespace`.
    """
    if not namespace:
        raise StorageConfigError(
            "configs/tuning.yaml: study_namespace is empty — an unnamespaced study in a "
            "shared Postgres is gotcha #17 waiting to happen"
        )
    return f"{namespace}-{label}"
