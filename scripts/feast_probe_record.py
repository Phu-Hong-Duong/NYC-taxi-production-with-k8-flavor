#!/usr/bin/env python
"""Write the quarantine's probe record — what the wall holds, in one tracked file.

M8-S2, called by `scripts/feast_quarantine.sh`. A READER: it inspects two
interpreters and writes JSON. It installs nothing, resolves nothing (except under
`--rewrite-pins`, which only ever writes the pin FILE from an already-built venv)
and touches no cluster.

The record answers the question a reviewer actually has, which is not "does Feast
install" — the milestone's law 4 already measured that it cannot, not here — but
**what exactly is on each side of the wall**. So both interpreters' versions of
the four numeric-core packages are recorded side by side, the complete transitive
set is recorded with versions, and the project's `uv.lock` sha256 rides along as
the invariant the whole design rests on.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The packages whose versions decide whether a number crosses the wall intact.
#: pandas is the conflict; the other three are recorded because M8-S3 measures a
#: parquet seam and "nothing on the numeric path differs" is a claim that needs
#: both columns of a table, not one (the mlserver precedent, M5-S3).
CORE = ("pandas", "numpy", "pyarrow", "python")


def _versions(python: Path) -> dict[str, str]:
    code = (
        "import json,sys,importlib.metadata as md\n"
        "out={'python':'.'.join(map(str,sys.version_info[:3]))}\n"
        "for p in ('pandas','numpy','pyarrow','feast'):\n"
        "    try: out[p]=md.version(p)\n"
        "    except Exception: pass\n"
        "print(json.dumps(out))\n"
    )
    result = subprocess.run(
        [str(python), "-c", code], capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)


def _normalize(name: str) -> str:
    """PEP 503's canonical spelling of a distribution name — F-057.

    `importlib.metadata` reports the name a distribution PUBLISHED (`PyYAML`,
    `typing_extensions`), while the pin file carries the normalized spelling an
    installer actually matches on. That mismatch is not cosmetic: it meant this
    module's own `--rewrite-pins` could not reproduce the file it maintains, so
    M8-S4's two-line addition came back as a fourteen-line diff and a third line
    could have hidden in it. gotcha #104.

    PEP 503 (`[-_.]+` -> `-`, lowercased) rather than the finding's shorter
    `lower().replace('_','-')`: the two agree on every name this quarantine holds
    today, and the difference is only ever a name containing a dot or a run of
    separators — where the short form would silently emit a spelling no installer
    canonicalises to.
    """
    return re.sub(r"[-_.]+", "-", name).lower()


def _freeze(python: Path) -> dict[str, str]:
    result = subprocess.run(
        [str(python), "-m", "pip", "freeze", "--all"], capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        # uv-created venvs ship no pip. Ask importlib.metadata instead — the same
        # question, asked of the interpreter rather than of a tool it may lack.
        code = (
            "import json,importlib.metadata as md\n"
            "print(json.dumps({d.metadata['Name']: d.version "
            "for d in md.distributions() if d.metadata['Name']}))\n"
        )
        result = subprocess.run(
            [str(python), "-c", code], capture_output=True, text=True, check=True
        )
        raw = json.loads(result.stdout)
    else:
        raw = {}
        for line in result.stdout.splitlines():
            if "==" in line:
                name, version = line.split("==", 1)
                raw[name] = version

    pins: dict[str, str] = {}
    for name, version in raw.items():
        canonical = _normalize(name)
        # Two published names canonicalising to one would SILENTLY drop a pin, and
        # the file's whole claim is that it is the complete transitive set.
        if canonical in pins and pins[canonical] != version:
            raise SystemExit(
                f"[probe] FAIL — {name!r} and another distribution both normalize to "
                f"{canonical!r} with different versions; the pin file cannot express that"
            )
        pins[canonical] = version
    return dict(sorted(pins.items()))


def _pin_header(path: Path) -> list[str]:
    return [line for line in path.read_text().splitlines() if line.startswith("#")]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--venv", default=".venv-feast")
    parser.add_argument("--pins", default="infra/feast/requirements-feast.txt")
    parser.add_argument("--repo-dir", default="infra/feast/feature_repo")
    parser.add_argument("--lock-sha", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument(
        "--rewrite-pins",
        action="store_true",
        help="rewrite the pin file from the built venv, preserving its argued header",
    )
    args = parser.parse_args(argv)

    venv_python = REPO_ROOT / args.venv / "bin" / "python"
    pins_path = REPO_ROOT / args.pins
    if not venv_python.exists():
        print(f"[probe] {venv_python} does not exist — build the quarantine first", file=sys.stderr)
        return 2

    quarantine = _freeze(venv_python)

    if args.rewrite_pins:
        header = _pin_header(pins_path)
        # The body is its own lines, SORTED — not the mapping's key order. The two
        # differ for hyphenated siblings (`mypy-extensions==…` sorts before
        # `mypy==…`, because `-` < `=`), and sorting the lines is the version a
        # reviewer can verify without this script: `sort -c` on the body. It is
        # also the order the committed file has carried since M8-S2, so the F-057
        # fix agrees with the artifact that was reviewed rather than rewriting it.
        body = sorted(f"{name}=={version}" for name, version in quarantine.items())
        pins_path.write_text("\n".join([*header, *body]) + "\n")
        print(f"[probe] rewrote {args.pins} with {len(quarantine)} pins")
        return 0

    project = _versions(Path(sys.executable))
    quarantine_core = _versions(venv_python)
    lock_sha = args.lock_sha or __import__("hashlib").sha256(
        (REPO_ROOT / "uv.lock").read_bytes()
    ).hexdigest()

    record = {
        "story": "M8-S2",
        "written_at": datetime.now(UTC).isoformat(),
        "why": (
            "feast 0.66.0 declares pandas<3,>=1.4.3; this project runs pandas 3.0.5. "
            "The quarantine is the design, not the fallback (M8 law 4)."
        ),
        "wall": {
            "declared_by_feast": "pandas<3,>=1.4.3",
            "project": {k: project.get(k) for k in CORE},
            "quarantine": {k: quarantine_core.get(k) for k in CORE},
            "feast_version": quarantine_core.get("feast"),
            "differs_on": sorted(
                k for k in CORE if project.get(k) != quarantine_core.get(k)
            ),
        },
        "invariants": {
            "uv_lock_sha256": lock_sha,
            "feast_in_project_environment": "feast" in {k.lower() for k in _freeze(
                Path(sys.executable)
            )},
        },
        "quarantine_packages": len(quarantine),
        "quarantine_pins": quarantine,
        "pin_file": args.pins,
        "feature_repo": args.repo_dir,
    }

    out = Path(args.out) if args.out else REPO_ROOT / "automation/runs/m8-feast/probe.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2, sort_keys=False) + "\n")

    wall = record["wall"]
    print(
        f"[probe] feast {wall['feast_version']} in {record['quarantine_packages']} packages; "
        f"the two sides differ on {wall['differs_on']}"
    )
    print(
        f"[probe] project    pandas {wall['project']['pandas']} | "
        f"quarantine pandas {wall['quarantine']['pandas']}"
    )
    if record["invariants"]["feast_in_project_environment"]:
        print("[probe] FAIL — feast is in the project environment", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
