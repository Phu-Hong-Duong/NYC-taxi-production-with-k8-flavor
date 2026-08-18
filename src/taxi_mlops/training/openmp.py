"""Make LightGBM importable on a host that ships no OpenMP runtime.

OBSERVED 2026-08-17 (M2-S2): this WSL Ubuntu has no `libgomp.so.1` anywhere
(`find /usr /lib /opt` empty, `dpkg -l | grep gomp` empty), so `import lightgbm`
dies with `OSError: libgomp.so.1: cannot open shared object file`. The real fix
is `sudo apt install libgomp1` — which is the PO's hands, not an unattended
session's (gotcha #23: the host is the PO's), and would park the chain overnight
on one package.

The sudo-free fix, and why it looks the way it does. scikit-learn's manylinux
wheel already vendors the library, at
`site-packages/scikit_learn.libs/libgomp-<hash>.so.1.0.0`. Preloading that file
with `ctypes.CDLL(..., RTLD_GLOBAL)` DOES NOT WORK and the reason is worth
writing down: auditwheel rewrites the vendored library's SONAME to the hashed
name, so the loader never matches a later `dlopen("libgomp.so.1")` against it.
The only thing that satisfies that lookup is a FILE named `libgomp.so.1` on the
loader's search path — and glibc reads `LD_LIBRARY_PATH` once, at process start,
so setting it from inside Python is too late.

Hence: symlink the vendored library under a generated directory as
`libgomp.so.1`, put that directory on `LD_LIBRARY_PATH`, and re-exec ourselves
exactly once (guarded by an env flag, so a still-broken host fails instead of
forking forever). It is announced on stdout when it happens; a silent re-exec
would be genuinely spooky.

Debt D-004 (M4): the container image installs `libgomp1` properly, at which
point `_load()` succeeds on the first line and none of the above runs. The shim
must not be what makes the image work — it is what makes THIS LAPTOP work.
"""

from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

SONAME = "libgomp.so.1"
_REEXEC_FLAG = "TAXI_MLOPS_OPENMP_REEXEC"


class OpenMPUnavailableError(RuntimeError):
    """No OpenMP runtime, and none could be borrowed. Names the real fix."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _shim_dir() -> Path:
    """Inside .venv/, which is gitignored and regenerable — it is not source."""
    return _repo_root() / ".venv" / "lib" / "openmp"


def _load() -> bool:
    """Can the loader resolve libgomp.so.1 by SONAME right now?"""
    try:
        ctypes.CDLL(SONAME, mode=ctypes.RTLD_GLOBAL)
    except OSError:
        return False
    return True


def _vendored() -> Path | None:
    """Any libgomp a wheel in this venv brought with it (scikit-learn ships one)."""
    for parent in Path(sys.prefix, "lib").glob("python*/site-packages"):
        for candidate in sorted(parent.glob("*/libgomp*.so*")):
            return candidate
    return None


def openmp_status() -> tuple[bool, str]:
    """(loadable now, how) — the read-only probe. Never re-execs; tests use this."""
    if _load():
        return True, "system libgomp.so.1"
    vendored = _vendored()
    if vendored is None:
        return False, "no libgomp on the system and none vendored in this venv"
    return False, f"not loadable yet; a vendored copy exists at {vendored}"


def ensure_openmp(*, allow_reexec: bool = True) -> str:
    """Guarantee LightGBM will import, or refuse in a way that names the fix.

    Returns a one-line provenance string for the run log — which OpenMP this
    process ended up using is exactly the kind of fact that is obvious today and
    unrecoverable in six months.
    """
    if _load():
        return "openmp: system libgomp.so.1"

    vendored = _vendored()
    if vendored is None:
        raise OpenMPUnavailableError(
            f"LightGBM needs {SONAME} and this host has none, nor does any wheel in "
            "this venv vendor one. Fix: `sudo apt install libgomp1` (the PO's hands), "
            "or run inside the M4 image, which installs it."
        )

    if os.environ.get(_REEXEC_FLAG) == "1":
        raise OpenMPUnavailableError(
            f"re-exec with LD_LIBRARY_PATH={_shim_dir()} still cannot load {SONAME} "
            f"(vendored copy: {vendored}). Fix: `sudo apt install libgomp1`."
        )

    if not allow_reexec:
        raise OpenMPUnavailableError(
            f"{SONAME} is not loadable in this process. A vendored copy exists "
            f"({vendored}) but LD_LIBRARY_PATH is read at process start, so using it "
            "requires a re-exec, which this caller disallowed."
        )

    if _invoked_with_dash_c():
        # F-024, found 2026-08-18 by M4-S3's D-004 sensor drill and reproduced on
        # the host. CPython does not keep the `-c` code anywhere reachable: under
        # `python -c "…"`, sys.argv is ["-c", *args] and the SOURCE STRING is gone.
        # So this branch cannot rebuild its own command line, and the old code
        # exec'd `python -c` with no code — which the interpreter answers with
        # "Argument expected for the -c option", a message about argument parsing
        # for a problem about a shared library. Refusing here is the honest move:
        # nothing is mutated, and the message names the three ways out. Every real
        # entry point in this program is `python -m …` or a .py file, both of which
        # _relaunch_argv() reconstructs correctly — this is the ad-hoc-probe path.
        raise OpenMPUnavailableError(
            f"{SONAME} is not loadable and this process was started with `python -c`, "
            "whose source string CPython does not preserve — so the re-exec that would "
            f"pick up the vendored copy ({vendored}) cannot be reconstructed. Use "
            "`python -m <module>` or a .py file (both re-exec correctly), call "
            "openmp_status() instead if you only wanted to probe, or remove the need "
            "entirely: `sudo apt install libgomp1`, which the M4 task image does."
        )

    shim = _shim_dir()
    shim.mkdir(parents=True, exist_ok=True)
    link = shim / SONAME
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(vendored)

    existing = os.environ.get("LD_LIBRARY_PATH", "")
    os.environ["LD_LIBRARY_PATH"] = f"{shim}:{existing}" if existing else str(shim)
    os.environ[_REEXEC_FLAG] = "1"
    print(
        f"[openmp] no system {SONAME}; linked {vendored.name} -> {link} and "
        "re-executing once with LD_LIBRARY_PATH set (see taxi_mlops.training.openmp)",
        flush=True,
    )
    os.execv(sys.executable, [sys.executable, *_relaunch_argv()])
    raise AssertionError("unreachable: execv does not return")  # pragma: no cover


def _invoked_with_dash_c() -> bool:
    """Was this interpreter started as `python -c "<code>"`?

    CPython sets sys.argv[0] to the literal string "-c" for that form (documented
    behaviour) and drops the code itself. `python -m pkg` and `python file.py`
    both leave a reconstructible argv, which is what _relaunch_argv() uses.
    """
    return bool(sys.argv) and sys.argv[0] == "-c"


def _relaunch_argv() -> list[str]:
    """Rebuild the command line, preserving `-m package` form.

    `python -m taxi_mlops.training` leaves sys.argv[0] as the path of
    `__main__.py`, so replaying sys.argv verbatim re-runs that FILE — which then
    dies on `attempted relative import with no known parent package`. Observed,
    not theorised (M2-S2, first re-exec).
    """
    spec = getattr(sys.modules.get("__main__"), "__spec__", None)
    if spec is not None and spec.name:
        package = spec.name.removesuffix(".__main__")
        return ["-m", package, *sys.argv[1:]]
    return list(sys.argv)
