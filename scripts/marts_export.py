"""The DuckDB half of the publish: emit a mart's DDL, or its rows as CSV.

Lives here rather than inline in `scripts/marts.sh` for two reasons. Shell
heredocs piped into `kubectl exec` are fragile in ways that fail at 3am and not
in review; and the type mapping below is the one piece of the publish with real
logic in it, so it belongs somewhere a unit test can reach it — which
`tests/unit/test_marts.py` does, without a cluster and without dbt.

The mapping is DuckDB -> PostgreSQL, and it is deliberately a whitelist. An
unmapped type raises instead of guessing: a column silently published as `text`
is a chart that silently stops summing.

Usage:
    python scripts/marts_export.py ddl <duckdb_path> <mart>
    python scripts/marts_export.py csv <duckdb_path> <mart> [--where "month = '2019-03'"]
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

# The analyst layer must be attached here too, and finding that out cost a
# failed publish: `trips_clean` is materialised as a VIEW over
# `analyst.main.trips_clean`, so opening marts.duckdb alone raises
# `Catalog "analyst" does not exist`. A view is a stored QUERY — the database it
# reads is not carried inside the file, it is resolved at read time. dbt attaches
# it via profiles.yml; every other reader has to do the same.
REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYST_DB = REPO_ROOT / "data" / "analyst.duckdb"

# DuckDB type (as DESCRIBE reports it) -> PostgreSQL type.
DUCKDB_TO_POSTGRES = {
    "BOOLEAN": "boolean",
    "TINYINT": "smallint",
    "SMALLINT": "smallint",
    "INTEGER": "integer",
    "BIGINT": "bigint",
    "HUGEINT": "numeric",
    "UBIGINT": "numeric",
    "UINTEGER": "bigint",
    "FLOAT": "real",
    "DOUBLE": "double precision",
    "VARCHAR": "text",
    "DATE": "date",
    "TIME": "time",
    "TIMESTAMP": "timestamp",
    "TIMESTAMP WITH TIME ZONE": "timestamptz",
}


def postgres_type(duckdb_type: str) -> str:
    """One DuckDB type to its Postgres equivalent, or a loud failure."""
    t = duckdb_type.upper()
    if t.startswith("DECIMAL"):
        return t.lower()
    try:
        return DUCKDB_TO_POSTGRES[t]
    except KeyError:
        raise SystemExit(
            f"[marts] unmapped DuckDB type {duckdb_type!r}. Add it to "
            "DUCKDB_TO_POSTGRES in scripts/marts_export.py — publishing it as a "
            "guess would produce a column that looks fine and does not aggregate."
        ) from None


def resolve(con: duckdb.DuckDBPyConnection, mart: str) -> str:
    """Find the mart's schema instead of assuming dbt's naming convention.

    dbt-duckdb builds `+schema: marts` as the schema `main_marts`, but that is a
    convention (`<default>_<custom>`) and conventions are exactly what a repo
    should not hardcode across two languages. Ask the catalogue.
    """
    rows = con.execute(
        "SELECT table_schema FROM information_schema.tables "
        "WHERE table_name = ? AND table_catalog = current_database()",
        [mart],
    ).fetchall()
    if not rows:
        raise SystemExit(
            f"[marts] no table or view named {mart!r} in this database. "
            "Run `dbt build` first (`make marts` does)."
        )
    if len(rows) > 1:
        raise SystemExit(
            f"[marts] {mart!r} exists in {len(rows)} schemas "
            f"({', '.join(r[0] for r in rows)}) — ambiguous, refusing to guess."
        )
    return f'"{rows[0][0]}"."{mart}"'


def ddl(con: duckdb.DuckDBPyConnection, mart: str) -> str:
    """The column list for the Postgres staging table, from the mart's own schema."""
    columns = con.execute(f"DESCRIBE {resolve(con, mart)}").fetchall()
    return ",\n  ".join(f'"{name}" {postgres_type(dtype)}' for name, dtype, *_ in columns)


def csv(con: duckdb.DuckDBPyConnection, mart: str, where: str | None = None) -> None:
    """Stream the mart to stdout as CSV, for the publish's transport to consume.

    `where` scopes the stream — the month-scoped publish (M4-S5, D-003) passes
    `month = '2019-03'`. It is applied HERE, inside DuckDB, rather than by filtering
    the CSV downstream, because the data is already here and a 56M-row stream
    filtered on the far side would have paid the whole cost of the thing it avoids.
    The predicate is built by `scripts/marts_publish.py` out of a month it has
    already validated as `YYYY-MM`; this function does not accept user text.
    """
    # /dev/stdout, not a temp file: trips_clean is ~7 GB of CSV and writing it to
    # disk first would double the I/O and need somewhere to put it.
    clause = f" WHERE {where}" if where else ""
    con.execute(
        f"COPY (SELECT * FROM {resolve(con, mart)}{clause}) TO '/dev/stdout' "
        "(FORMAT CSV, HEADER FALSE)"
    )


def main(argv: list[str]) -> int:
    where: str | None = None
    argv = list(argv)
    if "--where" in argv:
        i = argv.index("--where")
        if i + 1 >= len(argv):
            print(__doc__, file=sys.stderr)
            return 2
        where = argv[i + 1]
        del argv[i : i + 2]
    if len(argv) != 4 or argv[1] not in {"ddl", "csv"}:
        print(__doc__, file=sys.stderr)
        return 2
    _, mode, path, mart = argv
    con = duckdb.connect(path, read_only=True)
    try:
        if ANALYST_DB.exists():
            con.execute(f"ATTACH '{ANALYST_DB}' AS analyst (READ_ONLY)")
        if mode == "ddl":
            print(ddl(con, mart))
        else:
            csv(con, mart, where)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
