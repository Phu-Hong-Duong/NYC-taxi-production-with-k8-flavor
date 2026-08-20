"""Execute EVERY card of a checked-in board against the warehouse, and fail on an
empty one.

`scripts/metabase_boards.py --verify` runs ONE card per dashboard — enough to
prove the connection and the credentials, which is what it was written for. This
is the other half, and it exists because of gotcha #78: a panel returning zero
series is indistinguishable from a quiet system, so green must not be the default
rendering of "no data". M6-S1 learned that on the Grafana boards, where three
panels were empty for three different real reasons while every scrape target was
green.

The query goes to Postgres directly (`kubectl exec` into the one Postgres, the
`make marts` transport), not through Metabase's API. That is deliberate: what is
under test here is the SQL a reviewer reads in the checked-in JSON. A card can
also fail for Metabase-side reasons — a broken connection, a missing permission —
and `--verify` is the check that covers those.

Usage:  uv run python scripts/board_cards_execute.py                 (every board)
        uv run python scripts/board_cards_execute.py "Predictions & drift (M7)"
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BOARDS_DIR = REPO_ROOT / "analytics" / "metabase" / "boards"
NAMESPACE = "platform"
POD = "postgres-0"
DATABASE = "marts"


def _rows(sql: str) -> tuple[bool, str]:
    """Run `sql` as a subquery and return (ok, row count or the error's first line)."""
    proc = subprocess.run(
        [
            "kubectl",
            "-n",
            NAMESPACE,
            "exec",
            "-i",
            POD,
            "--",
            "psql",
            "-U",
            "postgres",
            "-d",
            DATABASE,
            "-t",
            "-A",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            f"select count(*) from ({sql}) card",
        ],
        capture_output=True,
        text=True,
    )
    out = proc.stdout.strip()
    if proc.returncode != 0 or not out.isdigit():
        detail = (proc.stderr.strip().splitlines() or ["(no stderr)"])[0]
        return False, detail[:120]
    return int(out) > 0, out


def main(argv: list[str]) -> int:
    # An empty argument is what `make board-cards` passes when BOARD is unset —
    # it means "every board", not "the board whose name is the empty string".
    wanted = {a for a in argv if a.strip()}
    boards = [json.loads(p.read_text()) for p in sorted(BOARDS_DIR.glob("*.json"))]
    if wanted:
        unknown = wanted - {b["name"] for b in boards}
        if unknown:
            print(f"no such board(s): {', '.join(sorted(unknown))}")
            return 2
        boards = [b for b in boards if b["name"] in wanted]

    failures = 0
    cards = 0
    for board in boards:
        print(f"[cards] board {board['name']!r} ({len(board['cards'])} cards)")
        for card in board["cards"]:
            cards += 1
            ok, detail = _rows(card["sql"])
            failures += 0 if ok else 1
            mark = "ok  " if ok else "FAIL"
            print(f"  {mark} {detail:>8}  {card['name']}")

    print(
        f"\n[cards] {cards} card(s) executed, {failures} failure(s) — "
        "an EMPTY panel is a failure (gotcha #78)"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
