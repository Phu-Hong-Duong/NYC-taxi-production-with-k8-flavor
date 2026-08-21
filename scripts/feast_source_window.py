#!/usr/bin/env python
"""Print the materialization window, DERIVED from the published sources. (M8-S4)

One line, two ISO instants, whitespace-separated — the shape
`scripts/feast_materialize.sh` reads with `read -r START END`.

Why this is a script and not two constants in the shell: the end instant must
cover the LAST source stamp, and that stamp moves the day `make feast-sources`
gains a seventh point-in-time window (or the day the static tables are re-derived
with a later stamp). A typed `2019-07-01` would keep materializing successfully
while silently ceasing to include the newest window — a store that is stale in a
way nothing reports, which is the failure shape this milestone keeps meeting
(F-050 in the drift surface, `noeviction` in the manifest header).

The window is `[min(stamp), max(stamp) + 1s)`. It is closed at the bottom because
Feast's materialize takes rows with `start <= event_timestamp <= end` and a
window that began after the earliest stamp would silently drop the static views;
the one-second slack at the top is there because the boundary's inclusivity is a
detail of a library version and one second of slack cannot include a stamp that
does not exist.

It reads parquet and prints. It writes nothing, connects to nothing, and has no
opinion about what is in the store.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = REPO_ROOT / "data" / "feast"

#: The published sources, named rather than globbed: a glob would silently pick
#: up a scratch file somebody left in the directory and widen the window with a
#: stamp no view is defined over.
SOURCES = ("zone_static", "calendar_day", "od_window_stats", "pu_hour_window_stats")


def window() -> tuple[pd.Timestamp, pd.Timestamp]:
    stamps: list[pd.Timestamp] = []
    for name in SOURCES:
        path = SOURCE_DIR / f"{name}.parquet"
        if not path.exists():
            raise FileNotFoundError(
                f"{path} is missing — the offline sources have not been built. "
                "Run: make feast-sources"
            )
        column = pd.read_parquet(path, columns=["event_timestamp"])["event_timestamp"]
        stamps.extend([column.min(), column.max()])
    return min(stamps), max(stamps) + pd.Timedelta(seconds=1)


def main() -> int:
    start, end = window()
    print(f"{start.isoformat()} {end.isoformat()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
