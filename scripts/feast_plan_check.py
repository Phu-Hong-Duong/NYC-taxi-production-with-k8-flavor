#!/usr/bin/env python
"""Run `feast plan` in the quarantine and say whether the registry MATCHES git.

M8-S2. A READER: it runs the read-only twin of `feast apply`, parses what comes
back and writes a record. It applies nothing and materializes nothing.

**Why this exists, which is a finding rather than a convenience (F-055).**
`feast plan` cannot report "no changes" for a file-source repo, ever. Feast
stamps `created_timestamp` / `last_updated_timestamp` into a DataSource's `meta`
when the Python object is constructed — that is import time, i.e. every
invocation — so the registry's stored copy and the freshly-imported one always
differ, and `plan` faithfully prints four "Updated feature view" blocks whose
entire content is two clock readings. A signal that says "changed" whether or not
anything changed cannot answer the question `plan` exists to answer, and it is
gotcha #78's disease in a new place: there, an empty panel was indistinguishable
from a quiet system; here, a full diff is indistinguishable from a real edit.

So the check is the one that can be false: every difference `plan` reports must
be confined to those two timestamp fields. Anything else — a renamed field, a
moved source path, a changed dtype, a view appearing or disappearing — is a
SUBSTANTIVE diff and this exits 1 naming it. That makes "the registry matches
what git holds" a checkable statement instead of an eyeballed one.
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
REPO_DIR = REPO_ROOT / "infra" / "feast" / "feature_repo"
VENV_PYTHON = REPO_ROOT / ".venv-feast" / "bin" / "python"

#: The two proto fields Feast re-stamps on every import. Lines whose VALUE is one
#: of these clock readings are erased from both sides before comparison — and
#: nothing else is. Widening this set is how a real diff would get hidden, so it
#: is spelled out here and pinned by a test.
CLOCK_FIELDS = ("seconds:", "nanos:")

_HEADER = re.compile(r"^(Created|Deleted|Updated) (feature view|entity|data source|project) (\S+)")

#: Lines feast prints AFTER every object block. They are not part of the last
#: block's body, and letting them be absorbed into it makes exactly one object
#: look different from its siblings for a reason that has nothing to do with it.
_TRAILERS = ("No changes to infrastructure", "Created sqlite table", "Deleted sqlite table")

#: An "Updated" block's first body line is `\t<property>: <old value>`, so the
#: property NAME sits on the before side only. Removing it is not cosmetic: left
#: in, it is an unmatched token on one side of every comparison and every diff
#: reads as substantive — which is a checker failing for its own reasons and
#: blaming the artifact (gotcha #55).
_PROPERTY_PREFIX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*: ")


def _normalise(block: str) -> list[str]:
    """Strip the clock, keep everything else, including whitespace-significant lines."""
    kept = []
    for line in block.splitlines():
        stripped = line.strip()
        if any(stripped.startswith(field) for field in CLOCK_FIELDS):
            continue
        if stripped:
            kept.append(stripped)
    return kept


def parse(output: str) -> tuple[list[dict], list[str]]:
    """Split `feast plan`'s output into per-object blocks and classify each."""
    blocks: list[dict] = []
    other: list[str] = []
    current: dict | None = None
    for line in output.splitlines():
        match = _HEADER.match(line)
        if match:
            if current:
                blocks.append(current)
            current = {"action": match.group(1), "kind": match.group(2), "name": match.group(3),
                       "body": []}
            continue
        if any(line.strip().startswith(trailer) for trailer in _TRAILERS):
            other.append(line.strip())
            continue
        if current is not None:
            current["body"].append(line)
        else:
            if line.strip():
                other.append(line.strip())
    if current:
        blocks.append(current)

    for block in blocks:
        body = "\n".join(block.pop("body"))
        # An "Updated" block prints `<old> -> <new>`; the arrow starts a line.
        halves = re.split(r"^\s*->\s?", body, maxsplit=1, flags=re.MULTILINE)
        if block["action"] == "Updated" and len(halves) == 2:
            before, after = _normalise(halves[0]), _normalise(halves[1])
            if before:
                before[0] = _PROPERTY_PREFIX.sub("", before[0], count=1)
            block["clock_only"] = before == after
            block["substantive_diff"] = (
                [] if before == after
                else sorted(set(before).symmetric_difference(after))
            )
        else:
            block["clock_only"] = False
            block["substantive_diff"] = [f"{block['action']} {block['kind']} {block['name']}"]
    return blocks, other


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="automation/runs/m8-feast/plan.json")
    args = parser.parse_args(argv)

    if not VENV_PYTHON.exists():
        print("[plan] the quarantine is absent — run `make feast-quarantine`", file=sys.stderr)
        return 2

    proc = subprocess.run(
        [str(VENV_PYTHON.parent / "feast"), "plan"],
        cwd=REPO_DIR, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout[-2000:])
        print(proc.stderr[-2000:], file=sys.stderr)
        print(f"[plan] FAIL — `feast plan` exited {proc.returncode}", file=sys.stderr)
        return 1

    blocks, other = parse(proc.stdout)
    substantive = [b for b in blocks if not b["clock_only"]]

    for block in blocks:
        verdict = "clock only (Feast re-stamps meta on import — F-055)" if block["clock_only"] \
            else f"SUBSTANTIVE: {block['substantive_diff']}"
        print(f"[plan] {block['action']:<8s} {block['kind']:<13s} {block['name']:<22s} {verdict}")
    infra_line = next((line for line in other if "infrastructure" in line), "(not printed)")
    print(f"[plan] feast says: {infra_line}")
    print(
        f"[plan] {len(blocks)} object(s) reported, {len(blocks) - len(substantive)} clock-only, "
        f"{len(substantive)} substantive"
    )

    record = {
        "story": "M8-S2",
        "written_at": datetime.now(UTC).isoformat(),
        "why": (
            "F-055: `feast plan` re-stamps DataSource meta at import, so it can never "
            "print 'no changes' for this repo. The checkable statement is that every "
            "reported difference is confined to those clock fields."
        ),
        "exit_code": proc.returncode,
        "infrastructure_line": infra_line,
        "objects": blocks,
        "substantive_count": len(substantive),
    }
    out = REPO_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + "\n")
    print(f"[plan] record: {args.out}")

    if substantive:
        print(
            "[plan] FAIL — the registry does not match what git holds. "
            "Run `make feast-apply` after reviewing the diff above.",
            file=sys.stderr,
        )
        return 1
    print("[plan] ok  the registry matches the definitions in git (no substantive diff)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
