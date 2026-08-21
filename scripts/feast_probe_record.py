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
        return dict(sorted(json.loads(result.stdout).items(), key=lambda kv: kv[0].lower()))
    pins = {}
    for line in result.stdout.splitlines():
        if "==" in line:
            name, version = line.split("==", 1)
            pins[name] = version
    return dict(sorted(pins.items(), key=lambda kv: kv[0].lower()))


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
        body = "\n".join(f"{name}=={version}" for name, version in quarantine.items())
        pins_path.write_text("\n".join(header) + "\n" + body + "\n")
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
