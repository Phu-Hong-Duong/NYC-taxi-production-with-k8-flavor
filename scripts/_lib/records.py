"""Reading a TRACKED record — and refusing, usefully, when it is not there.

`automation/runs/**/*.json` is tracked from M5-S1 (F-029 option A), so a fresh
clone HAS these files and the only thing an absence can mean is deleted or lost.
The bare `json.loads(PATH.read_text())` this replaces answers that with a
`FileNotFoundError` five frames deep, naming an absolute path and nothing about
what should have produced it — and the reader's next question is always the same
one: *gone from where, and what writes it?*

This is the script-side sibling of `tests/conftest.read_record` (CU-S2). They are
deliberately two functions rather than one shared import: a test ASSERTS and may
say so with `assert`, a script computes and must raise something a caller can
catch, and `scripts/` must not import from `tests/`.

WHAT DELIBERATELY DOES NOT LIVE HERE — the stopping line CU-S4 declared for this
cluster, because the audit rated it the judgement-heavy one:

  * **Optional reads.** `store_watch_headroom.py`'s
    `... if PERSISTENCE_RECORD.exists() else {}` is a real decision — that record
    is genuinely optional and its absence is not an error. Forcing it through a
    presence-checking loader would turn a correct system red, which is gotcha #50
    arriving through consolidation.
  * **Shape checks and bespoke refusals.** A reader that argues about its own
    artifact — `retrain_prediction_check.py`'s field-by-field comparison,
    `demo_accept.py`'s match on `(at, pu, do)` — keeps that argument beside the
    artifact. Only the *is it there* question moved.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_record(path: Path, produced_by: str | None = None) -> dict[str, Any]:
    """Read a tracked JSON record, or raise a refusal that names what writes it.

    `produced_by` is the command a reader should run — `make store-watch-drill`,
    not a module path — because the answer to "what put it there?" is only useful
    if it is something the reader can type.
    """
    if not path.exists():
        origin = f" It is written by `{produced_by}`." if produced_by else ""
        raise FileNotFoundError(
            f"{path} is a TRACKED record (F-029 option A) — its absence means it was "
            f"deleted or lost, not that this clone lacks local artifacts.{origin}"
        )
    return json.loads(path.read_text(encoding="utf-8"))
