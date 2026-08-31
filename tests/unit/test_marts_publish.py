"""M4-S5: the marts publish, driven end to end without a cluster (D-003).

`scripts/marts_publish.py` is the module both publishers share — the host's
`make marts` over `kubectl exec`, and the pipeline's tail task over psycopg from
inside a pod. What makes it testable here is that the SQL is transport-blind: a
recording transport plus a real (tiny) DuckDB file exercises the whole path —
statement order, the staging-and-swap, the month-scoped replace, the CSV stream and
the per-month reconciliation — with nothing running and nothing to clean up.

The DuckDB file is real on purpose. `marts_export.py` runs as a SUBPROCESS on both
sides, so a mocked exporter would test the mock; a two-row table proves the pipe.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest
from conftest import REPO

sys.path.insert(0, str(REPO / "scripts"))

import marts_publish  # noqa: E402, I001 — scripts/ is not a package; the path insert above is the import

# ------------------------------------------------------------ the fake transport ---


class Recorder:
    """A transport that remembers instead of connecting.

    `copy_in` reads the producer to EOF, which matters: a transport that ignored
    its source would leave the exporter blocked on a full pipe and the test would
    hang rather than fail. It also lets the assertions check what actually crossed.
    """

    def __init__(self, published: dict[str, int] | None = None) -> None:
        self.statements: list[str] = []
        self.copies: list[tuple[str, bytes]] = []
        self._published = published or {}

    def execute(self, statement: str) -> None:
        self.statements.append(statement)

    def query(self, statement: str) -> list[tuple]:
        if "pg_tables" in statement:
            return [("trips_clean",), ("zone_hourly_stats",)]
        if "pg_stat_user_tables" in statement:
            return [("trips_clean", 2)]
        if "GROUP BY" in statement:
            return [(m, n) for m, n in self._published.items()]
        return []

    def copy_in(self, table: str, source) -> None:
        self.copies.append((table, source.read()))

    def describe(self) -> str:
        return "recorder"


@pytest.fixture
def tiny_marts(tmp_path: Path) -> Path:
    """A DuckDB file holding the two marts these tests publish, four rows total."""
    duckdb = pytest.importorskip("duckdb")
    path = tmp_path / "marts.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE SCHEMA main_marts")
    con.execute(
        "CREATE TABLE main_marts.trips_clean AS "
        "SELECT * FROM (VALUES ('2019-01', 1), ('2019-01', 2), ('2019-02', 3)) "
        "AS t(month, rows)"
    )
    con.execute(
        "CREATE TABLE main_marts.zone_hourly_stats AS "
        "SELECT * FROM (VALUES ('2019-01', 7)) AS t(month, trips)"
    )
    con.close()
    return path


TWO = ("trips_clean", "zone_hourly_stats")


# --------------------------------------------------------------- the full refresh ---


def test_a_full_refresh_loads_into_staging_and_swaps_it_in(tiny_marts: Path):
    """The property M1-S4 built the staging table FOR: a reader sees the old table
    or the new one and never a half-loaded one. So the CSV must land in
    `<mart>__staging` and the rename must be inside a transaction with the drop."""
    rec = Recorder()
    marts_publish.publish(rec, tiny_marts, owner="marts", months=None, marts=TWO)

    for _, mart in enumerate(TWO):
        target, payload = next(c for c in rec.copies if mart in c[0])
        assert target.endswith(f'"{mart}__staging"'), "the CSV went straight into the live table"
        assert payload, f"{mart} streamed no bytes"

    swap = next(s for s in rec.statements if "RENAME TO" in s)
    assert swap.strip().startswith("BEGIN;") and swap.strip().endswith("COMMIT;")
    assert "DROP TABLE IF EXISTS" in swap, "the old table is dropped outside the swap"
    # The host transport connects as the superuser, so without this the published
    # table would be owned by `postgres` and the `marts` role — the one Metabase
    # reads with — could not see it. The pod's transport already IS `marts`.
    assert 'OWNER TO "marts"' in swap, "the swapped-in table is not handed to the marts role"


def test_a_full_refresh_asks_for_no_reconciliation_because_it_cannot_lose_a_month(
    tiny_marts: Path,
):
    """A full refresh rewrites every month, so there is nothing for a per-month
    check to catch — and running one anyway would suggest the check is what makes
    the FULL path safe, when it is the thing that makes the SCOPED path safe."""
    rec = Recorder()
    summary = marts_publish.publish(rec, tiny_marts, owner="marts", months=None, marts=TWO)
    assert summary["mode"] == "full-refresh"
    assert summary["reconciled"] == []


# ---------------------------------------------------------------- the scoped path ---


def test_a_scoped_publish_replaces_only_the_named_month_and_never_drops_the_fact_table(
    tiny_marts: Path,
):
    """D-003's whole point: the 13 GB table is not rewritten to land one month.

    The failure this guards is not a wrong number, it is a wrong COST — a scoped
    publish that quietly fell back to a staging swap would be correct and would pay
    the 27.96 GiB peak it exists to avoid.
    """
    rec = Recorder(published={"2019-01": 2, "2019-02": 1})
    summary = marts_publish.publish(
        rec, tiny_marts, owner="marts", months=("2019-01",), marts=TWO
    )
    assert summary["mode"] == "month-scoped"

    fact = [s for s in rec.statements if "trips_clean" in s]
    assert not any("__staging" in s for s in fact), "the scoped path built a staging copy"
    assert not any(re.search(r'DROP TABLE IF EXISTS marts\."trips_clean"', s) for s in fact)

    delete = next(s for s in fact if "DELETE FROM" in s)
    assert "month = '2019-01'" in delete
    assert "2019-02" not in delete, "the scoped delete touched a month nobody asked for"

    target, payload = next(c for c in rec.copies if "trips_clean" in c[0])
    assert target == 'marts."trips_clean"', "the scoped stream did not go into the live table"
    # The stream carries ONE month, filtered inside DuckDB. Two rows of 2019-01
    # exist in the fixture and one row of 2019-02 does not belong here.
    assert payload.decode().splitlines() == ["2019-01,1", "2019-01,2"]

    # The aggregates are still full-refreshed, which is the other half of the split.
    agg = next(c for c in rec.copies if "zone_hourly" in c[0])
    assert agg[0].endswith('"zone_hourly_stats__staging"')


def test_a_scoped_publish_refuses_when_a_month_does_not_reconcile(tiny_marts: Path):
    """The check that makes incremental safe, watched saying no.

    A month deleted and not re-streamed leaves a mart that is quietly short: it
    answers every query happily and just returns fewer rows (M1-S2's catalogue
    lesson, one layer downstream). The recorder here claims 2019-02 has one row
    published when the source has one — and claims 2019-01 has ZERO.
    """
    rec = Recorder(published={"2019-01": 0, "2019-02": 1})
    with pytest.raises(SystemExit) as raised:
        marts_publish.publish(rec, tiny_marts, owner="marts", months=("2019-01",), marts=TWO)
    assert "disagree" in str(raised.value)


def test_a_scoped_publish_full_refreshes_a_fact_table_that_is_not_there_yet(
    tiny_marts: Path,
):
    """A first publish (or a table somebody dropped) has no month to replace. The
    honest answer is a full refresh, and it must be SAID rather than silently done —
    otherwise the one publish that legitimately pays the peak looks like the rest."""

    class Empty(Recorder):
        def query(self, statement: str):
            if "pg_tables" in statement:
                return []
            return super().query(statement)

    rec = Empty(published={"2019-01": 2, "2019-02": 1})
    marts_publish.publish(rec, tiny_marts, owner="marts", months=("2019-01",), marts=TWO)
    assert any('"trips_clean__staging"' in s for s in rec.statements)


# ------------------------------------------------------------------- the guardrails ---


@pytest.mark.parametrize(
    "bad", ["2019-1", "2019/01", "'; DROP TABLE marts.trips_clean; --", "", "2019-01-01"]
)
def test_a_month_that_is_not_a_month_never_reaches_sql(bad: str):
    """The months are interpolated rather than bound, because one transport is
    `psql -c` and has no bind parameters at all. That is only safe because this
    function is the single door they come through — so it is asserted, not trusted.
    """
    with pytest.raises(SystemExit):
        marts_publish._check_months([bad])


def test_both_transports_satisfy_the_one_protocol():
    """Two transports, one interface. A method added to the protocol and forgotten
    in one class is a publish that works from the host and dies in a pod after the
    fit — 31 minutes downstream of the mistake."""
    required = {"execute", "query", "copy_in", "describe"}
    for cls in (marts_publish.KubectlTransport, marts_publish.PsycopgTransport):
        missing = required - set(dir(cls))
        assert not missing, f"{cls.__name__} is missing {missing}"


def test_a_failed_exporter_aborts_the_publish_instead_of_committing_a_short_mart():
    """gotcha #59 in miniature: a `Popen` read to EOF looks identical whether it
    finished or died three rows in, so the producer's exit code is checked. Without
    this the publish would commit a truncated mart and print a row count."""
    rec = Recorder()
    with pytest.raises(SystemExit) as raised:
        marts_publish._stream(rec, Path("/nonexistent/marts.duckdb"), "trips_clean",
                              'marts."x"', None)
    assert "nothing was committed" in str(raised.value)


def test_the_publish_never_touches_the_registry_or_the_model_code():
    """ADR-009's boundary law, from the marts side. The publish serves humans; it
    has no business resolving an alias, and a tail task that could would be a
    second promotion path (M4's standing law is that nothing here moves
    @champion)."""
    source = (REPO / "scripts" / "marts_publish.py").read_text()
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert not [m for m in imported if m.startswith(("mlflow", "taxi_mlops", "flyte"))], (
        f"the publish imports model or orchestrator code: {imported}"
    )


def test_the_dbt_invocation_welds_no_partial_parse_on():
    """gotcha #38: dbt's parse cache records node paths relative to wherever dbt
    last ran, so one hand-run from the repo root poisons every later build. Both
    publishers go through this one function, so the flag is asserted here once."""
    func = next(
        node
        for node in ast.walk(ast.parse((REPO / "scripts" / "marts_publish.py").read_text()))
        if isinstance(node, ast.FunctionDef) and node.name == "dbt_build"
    )
    literals = [n.value for n in ast.walk(func) if isinstance(n, ast.Constant)]
    assert "--no-partial-parse" in literals
    assert "build" in literals and "dbt" in literals


def test_the_host_and_the_pod_read_the_same_dbt_vars():
    """One payload, two callers. `marts.sh` used to assemble it in an inline python
    heredoc; a second assembly is how the mart's KPI-04 domains and the model's
    KPI-12 tolerance come to disagree on the day somebody edits one config."""
    script = (REPO / "scripts" / "marts.sh").read_text()
    assert "--print-dbt-vars" in script, "marts.sh assembles its own dbt vars again"
    assert "known_domains" not in script.split("--print-dbt-vars")[1], (
        "marts.sh still names a var the module owns"
    )
    payload = marts_publish.dbt_vars()
    assert set(payload) == {"known_domains", "tolerance_minutes"}
    assert isinstance(payload["tolerance_minutes"], float)
