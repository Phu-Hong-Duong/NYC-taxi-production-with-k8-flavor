"""Shared fixtures AND the suite's shared helpers. Markers: unit (default),
integration (needs cluster), smoke. pyproject addopts excludes integration+smoke
by default — CI stays cluster-free.

The data fixtures below deliberately build on the REAL configs/data.yaml (paths
redirected into tmp_path) rather than an invented one: a test that carries its
own copy of the contract stops testing the contract that ships.

**Why the helpers live HERE and not in `tests/unit/conftest.py`** (CU-S2, and
the charter asked for the latter): seven modules under `tests/unit/` already
say `from conftest import raw_frame`, which resolves to THIS file because
pytest puts `tests/` on `sys.path` when it imports it. Creating a second
conftest one directory down SHADOWS that name for every test in `tests/unit/`,
and all seven fail at collection with `cannot import name 'raw_frame'`
(measured before anything was migrated). Loud, so not dangerous — but the
one-home rule (F-013) says the fix is to use the home that exists rather than
to add a second and re-export across it. Read: helpers a test IMPORTS live
here; fixtures a test REQUESTS live here too.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from taxi_mlops.data.config import DataConfig, Splits, load_config

# The repository root, declared ONCE. Every test under tests/unit/ used to carry
# its own `REPO = Path(__file__).resolve().parents[2]`; 54 copies of one fact is
# 54 chances for one of them to be off by a directory level.
REPO = Path(__file__).resolve().parents[1]

MONEY_COLUMNS = [
    "fare_amount",
    "extra",
    "mta_tax",
    "tip_amount",
    "tolls_amount",
    "improvement_surcharge",
    "total_amount",
    "congestion_surcharge",
]


def raw_frame(month: str = "2019-01", rows: int = 8) -> pd.DataFrame:
    """A raw-shaped 2019 TLC frame: valid rows, in the dtypes the source really ships."""
    start = pd.Timestamp(f"{month}-05 08:00:00")
    pickup = pd.to_datetime([start + pd.Timedelta(minutes=7 * i) for i in range(rows)])
    df = pd.DataFrame(
        {
            "VendorID": np.ones(rows, dtype="int64"),
            "tpep_pickup_datetime": pickup,
            "tpep_dropoff_datetime": pickup + pd.Timedelta(minutes=10),
            "passenger_count": np.ones(rows, dtype="float64"),
            "trip_distance": np.full(rows, 2.5, dtype="float64"),
            "RatecodeID": np.ones(rows, dtype="float64"),
            "store_and_fwd_flag": pd.Series(["N"] * rows, dtype="object"),
            "PULocationID": np.full(rows, 100, dtype="int64"),
            "DOLocationID": np.full(rows, 200, dtype="int64"),
            "payment_type": np.ones(rows, dtype="int64"),
        }
    )
    for column in MONEY_COLUMNS:
        df[column] = np.full(rows, 1.0, dtype="float64")
    df["airport_fee"] = pd.Series([None] * rows, dtype="object")
    return df


def raw_frame_2025(rows: int = 4) -> pd.DataFrame:
    """A 2025-shaped frame — the columns AND dtypes observed live on 2026-08-16.

    2025 renames airport_fee -> Airport_fee, adds cbd_congestion_fee, and ships
    the id columns as int32 where 2019 shipped int64. If the contract were frozen
    to 2019 this frame would fail, which is exactly what this shape is for.
    """
    df = raw_frame("2025-01", rows)
    df = df.rename(columns={"airport_fee": "Airport_fee"})
    df["Airport_fee"] = np.full(rows, 1.75, dtype="float64")
    df["cbd_congestion_fee"] = np.full(rows, 0.75, dtype="float64")
    for column in ("VendorID", "PULocationID", "DOLocationID"):
        df[column] = df[column].astype("int32")
    for column in ("passenger_count", "RatecodeID"):
        df[column] = df[column].astype("int64")
    return df


@pytest.fixture
def data_cfg(tmp_path) -> DataConfig:
    """The shipped configs/data.yaml, with every path pointed inside tmp_path."""
    cfg = load_config()
    source = dict(cfg.source)
    source["raw_dir"] = str(tmp_path / "raw")
    source["processed_dir"] = str(tmp_path / "processed")
    source["manifest_path"] = str(tmp_path / "raw_manifest.json")
    # The rejected sidecar's path is redirected here too. Miss this and every
    # test that ingests writes into the REAL data/rejected/, quietly corrupting
    # the tree the DVC pin describes — a test suite that damages the data is the
    # worst kind of green.
    rejected = dict(cfg.rejected)
    rejected["dir"] = str(tmp_path / "rejected")
    # The SCORING trees (M7-S1), redirected for exactly the reason above and
    # one tree further along again: a test that ingests a scoring month would
    # otherwise write into the real data/scoring/, and the DVC pin that
    # describes it would go stale from a green test run.
    scoring = dict(cfg.scoring)
    scoring["dir"] = str(tmp_path / "scoring")
    scoring["rejected_dir"] = str(tmp_path / "scoring_rejected")
    return dataclasses.replace(
        cfg,
        source=source,
        rejected=rejected,
        scoring=scoring,
        # Same reason as `rejected` above, one tree further along: with the real
        # `data/predictions` in place a test that builds the analyst layer would
        # otherwise pick up the REAL published predictions and reconcile them
        # against three seeded months.
        predictions_dir=str(tmp_path / "predictions"),
        # And one further along again (M7-S2): the champion's rows on the
        # scoring months. Same failure, same redirect — a green test run must
        # not be able to write into a tree a real command published.
        scoring_predictions_dir=str(tmp_path / "scoring_predictions"),
        splits=Splits(train=("2019-01",), val=("2019-02",), test=("2019-03",)),
    )


# ---------------------------------------------------------------------------
# Shared helpers (CU-S2). Every one of these existed 3–13 times over before the
# cleanup; the copies are deleted, not wrapped. Two rules govern this section:
#
#   1. A helper's NAME states its semantics. The cleanup audit found `_calls()`
#      defined seven times with THREE different meanings under one name, so two
#      tests that read identically asserted different things. The successors
#      below are split, never unified — see `called_names` / `called_paths` /
#      `referenced_names`.
#   2. Anything whose failure MESSAGE is doing work stays with its caller. A
#      bespoke refusal that argues about its own artifact is not duplication.
# ---------------------------------------------------------------------------


def without_comments(source: str | Path) -> str:
    """The file (or text) with its whole-line ``#`` comments removed.

    Every "this string must NOT appear" assertion in this suite reads through
    this. The repo has paid the tuition repeatedly — M1-S3's KPI-10 regex,
    M1-S4's ``monthly_kpis.sql``, four assertions in the task-image tests — and
    the shape is always identical: a comment explaining *why we do not do X*
    contains the word X, so the assertion fires for the wrong reason and the
    author "fixes" working code. In a repo where prose is load-bearing, a check
    about structure must read structure.

    Trailing comments are left in place DELIBERATELY: stripping them needs a
    quoting-aware parser, and a half-parser is how gotcha #35 happened — a test
    that split a shell array on the first `)` truncated it inside a COMMENT and
    silently stopped checking the survivors.

    Blank lines are KEPT. One caller (`test_slo_and_alerts`) also drops blanks;
    that is a different function and keeps its own name for saying so.
    """
    text = source.read_text() if isinstance(source, Path) else source
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


def called_names(path: Path) -> set[str]:
    """Every callable NAME invoked in a file, however it is spelled.

    ``foo()``, ``a.b.foo()`` and ``a.foo()`` all contribute ``foo``, so a ban
    survives an import being renamed — and, unlike a grep, prose naming the same
    verb does not trip it. Guarded by ``ast.Call``: an invocation, never a
    mention. Use for "this file must not CALL x" and "this file must call x".
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def called_paths(path: Path) -> list[str]:
    """Every DOTTED callee name actually invoked in a module (gotchas #53/#68).

    ``a.b.foo()`` contributes ``a.b.foo`` — the whole path, not just the last
    segment — so an assertion can distinguish ``mlflow.set_alias`` from some
    other object's ``set_alias``. A list, not a set: callers count occurrences.
    """
    names = []
    for node in ast.walk(ast.parse(path.read_text())):
        if not isinstance(node, ast.Call):
            continue
        target, parts = node.func, []
        while isinstance(target, ast.Attribute):
            parts.append(target.attr)
            target = target.value
        if isinstance(target, ast.Name):
            parts.append(target.id)
        if parts:
            names.append(".".join(reversed(parts)))
    return names


def referenced_names(path: Path) -> set[str]:
    """Every ``Name``/``Attribute`` in a module, called or NOT.

    Deliberately broader than `called_names`, and the breadth is the point: this
    backs FORBIDDING assertions ("the registry API must not appear here"), where
    a bare reference — an alias, a partial, a name passed to something else — is
    already the violation. Migrating such a guard onto the call-guarded helper
    would WEAKEN it inside a diff that reads as pure deduplication, which is
    gotcha #50 arriving through consolidation. Use only where broader is
    stronger; use `called_names` for everything else.
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Name):
            names.add(node.id)
    return names


def invokes(body: str, command: str) -> bool:
    """Is `command` RUN here, or merely named?

    The house rule, made mechanical. A gate prints advice — "run
    `make pipeline-cache-drill`" is exactly what a reader of a RED cache leg
    needs — and `kubectl -n flyte get deploy` contains the substring
    "flyte get". A plain `in` test calls both of those violations, which is
    gotcha #35 wearing a third hat. So the needle must sit where a shell would
    START a command: at the beginning of a line, or after a pipe, `&&`, `;` or
    `$(`. A backtick is deliberately NOT a command position here: in this repo
    backticks appear inside message strings far more often than in command
    substitutions.
    """
    pattern = rf"(?:^|\||&&|;|\$\()\s*{re.escape(command)}(?:\s|$)"
    return bool(re.search(pattern, body, re.M))


def imported_roots(path: Path) -> set[str]:
    """Top-level package names this module imports, from the AST and nowhere else."""
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def record(path: Path, produced_by: str | None = None) -> dict:
    """Read a tracked drill record, and REFUSE if it is not there — F-054.

    These reads used to sit under `skipif(not RECORD.exists())`, which made the
    in-image run green by SKIPPING. On the host that is the weaker answer: an
    absent record means the drill was never run, and a silent skip is how a
    check stops being one. The records are git-tracked from M5-S1 (F-029 option
    A), so a fresh clone has them and the only thing this assertion can catch is
    a deleted or lost record — loudly. Where a test can RUN is the marker's job
    (`needs_records`, F-047); whether it must PASS is not negotiable.

    `produced_by` names the command that writes the record, because the failure
    a reader meets is "this file is gone" and the question they immediately have
    is "gone from where, and what put it there?".
    """
    origin = f" It is written by `{produced_by}`." if produced_by else ""
    assert path.exists(), (
        f"{path.relative_to(REPO)} is a TRACKED record (F-029 option A) — its absence "
        f"means it was deleted or lost, not that this clone lacks local artifacts.{origin}"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def phony_targets(makefile_text: str) -> set[str]:
    """Every target declared `.PHONY`, INCLUDING on backslash-continued lines.

    F-083 (CU-S1): the cleanup audit matched `^\\.PHONY:(.*)$` against the raw
    Makefile and could not see a wrapped declaration, so it reported five gaps
    that were not gaps. Seven guards in this suite carry the same
    continuation-blind idiom; none is red today only because none of their
    targets happens to sit on a continuation line. A parser that cannot see
    half the file is a guard that will eventually be wrong quietly.
    """
    targets: set[str] = set()
    lines, i = makefile_text.splitlines(), 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(".PHONY:"):
            joined = line
            while joined.rstrip().endswith("\\") and i + 1 < len(lines):
                i += 1
                joined = joined.rstrip()[:-1] + " " + lines[i]
            targets.update(joined.split(":", 1)[1].split())
        i += 1
    return targets
