"""Read the bake-off's winner out of its own row set — and the live alias.

`scripts/champion_transition.sh` needs four facts before it may move anything:
which contender won, which MLflow run it is, which feature set it eats, and what
verdict the gate gave it. All four are FACTS THE MEASUREMENT PRODUCED, so they
are read from `automation/runs/m3s5/bakeoff.json` rather than typed into the
shell script — a run id in a shell script is correct exactly until the next
experiment and silently wrong afterwards.

It also answers, on `--alias-run`, which run `@champion` currently resolves to.
That is what lets the transition skip a promotion it has already performed:
`bakeoff_m3.py` re-reads the incumbent on every invocation, so a second
promoting run would re-judge the losing contenders against the NEW incumbent and
overwrite the verdict column with verdicts nobody took.

Output is TAB-separated on one line so `read -r` in the caller cannot be
confused by a label with a space in it.

Usage:
    python scripts/champion_transition_winner.py <bakeoff.json>
    python scripts/champion_transition_winner.py --alias-run
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


def _alias_run() -> int:
    """Print the run id `@champion` resolves to, or nothing when it is unset."""
    import contextlib

    from taxi_mlops.training import tracking
    from taxi_mlops.training.run import load_train_config

    train_cfg = load_train_config()
    # `tracking.configure` announces the endpoints on stdout, which is the right
    # thing everywhere except here: this program's stdout IS its return value and
    # the caller reads it with `read`. Announcements go to stderr, where they are
    # still in the detached job's log.
    with contextlib.redirect_stdout(sys.stderr):
        tracking.configure(train_cfg["mlflow"])

    import mlflow

    registry = train_cfg["registry"]
    client = mlflow.MlflowClient()
    try:
        version = client.get_model_version_by_alias(
            registry["model_name"], registry["champion_alias"]
        )
    except Exception:
        return 1  # unset, or no registered model at all — the caller treats both alike
    print(version.run_id)
    return 0


def _winner(path: Path) -> int:
    payload = json.loads(path.read_text())
    label = payload.get("winner")
    for row in payload.get("contenders", []):
        if row.get("label") == label:
            print(
                "\t".join(
                    (
                        str(row["label"]),
                        str(row["name"]),
                        str(row["run_id"]),
                        str(row["feature_set"]),
                        str(row["verdict"]),
                    )
                )
            )
            return 0
    print(f"no contender row labelled {label!r} in {path}", file=sys.stderr)
    return 2


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--alias-run":
        return _alias_run()
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    return _winner(Path(argv[0]))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
