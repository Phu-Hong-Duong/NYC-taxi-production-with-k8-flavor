"""The DuckDB analyst layer: the DA queries clean TABLES, never raw parquet.

Why a layer at all (DA charter, refusal #2): a parquet path in a notebook is a
private fact. The moment two people spell the glob differently, two "row counts"
disagree and nobody can say which is wrong. A named view is a public fact — one
definition, one place, cited by name in the EDA report and on every board.

Three design decisions, each with its undo:

* **Views, not tables.** Nothing here copies a row. The database file is a
  catalogue of definitions over `data/processed/`, so a rebuild of the data is
  picked up by the next query with no refresh step to forget. Undo: swap
  ``CREATE OR REPLACE VIEW`` for ``CREATE OR REPLACE TABLE`` in one function.
* **`split` and `month` are literals from config, not parsed from filenames.**
  DuckDB could hand us the filename and we could regex a month out of it — and
  then a renamed file would silently relabel data. The work list comes from
  ``configs/train.yaml`` via ``Splits``, so a month the config does not know
  about cannot appear in a view at all.
* **Paths are config, schema is code.** ``configs/data.yaml:analyst`` owns where
  the database lives; the view definitions live here. A view name is a contract
  other code cites by name (S3's EDA, S4's dbt sources, S5's boards) — a
  contract belongs in reviewed code, not in a knob anyone can retune.

The rejection counts and the raw sha256 pins are views too. S1 wrote them beside
the data as JSON; reading them here is what lets a data-health board answer
"how much did we throw away, and are these the bytes we pinned?" in SQL rather
than in someone's head.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from .config import DataConfig, load_config

# Every view this layer publishes, in creation order. The DA cites these names;
# `tests/unit/test_data_analyst.py` asserts the list matches what a real build
# creates, so a view cannot be renamed here and left dangling in a report.
VIEWS = (
    "trips_clean",
    "trips_train",
    "trips_val",
    "trips_test",
    "raw_manifest",
    "ingest_months",
    "ingest_rejections",
    "data_health",
    "unknown_domain_values",
)


def database_path(cfg: DataConfig) -> Path:
    """Where the catalogue lives (configs/data.yaml:analyst.database_path)."""
    from .config import repo_root

    return repo_root() / cfg.analyst["database_path"]


def _sql_str(value: object) -> str:
    """Single-quote a literal for SQL. Paths and months only — never user input."""
    return "'" + str(value).replace("'", "''") + "'"


def _trips_clean_sql(cfg: DataConfig) -> str:
    """One branch per configured month, each labelled with its split from config.

    The parquet columns are taken with ``*`` on purpose: the pandera output
    contract already decided what those columns are, and restating them here
    would be a second schema to drift against the first (the twins lesson).
    """
    branches = [
        f"SELECT {_sql_str(cfg.splits.split_of(month))} AS split, "
        f"{_sql_str(month)} AS month, * "
        f"FROM read_parquet({_sql_str(cfg.processed_path(month))})"
        for month in cfg.splits.months
    ]
    return "CREATE OR REPLACE VIEW trips_clean AS\n" + "\nUNION ALL\n".join(branches)


def _rejections_sql(cfg: DataConfig) -> str:
    """The per-rule drop counts S1 wrote beside each output, as a queryable table."""
    branches = [
        f"SELECT {_sql_str(cfg.splits.split_of(month))} AS split, month, "
        "rule.name AS rule, rule.rejected_by AS rejected_by, rule.matched AS matched "
        "FROM (SELECT month, unnest(rules) AS rule "
        f"FROM read_json_auto({_sql_str(cfg.rejections_path(month))}))"
        for month in cfg.splits.months
    ]
    return "CREATE OR REPLACE VIEW ingest_rejections AS\n" + "\nUNION ALL\n".join(branches)


def _months_sql(cfg: DataConfig) -> str:
    """One row per ingested month: what came in, what survived, what fraction went."""
    branches = [
        f"SELECT {_sql_str(cfg.splits.split_of(month))} AS split, "
        "month, rows_in, rows_out, rows_rejected, rejected_fraction "
        f"FROM read_json_auto({_sql_str(cfg.rejections_path(month))})"
        for month in cfg.splits.months
    ]
    return "CREATE OR REPLACE VIEW ingest_months AS\n" + "\nUNION ALL\n".join(branches)


def _manifest_sql(cfg: DataConfig) -> str:
    """The sha256 pins of the RAW files — provenance, not rows.

    This is the one view that touches anything under ``data/raw``, and it reads
    the manifest JSON, never a raw parquet: the DA charter's refusal is about
    querying raw DATA, and a checksum is metadata. Without it a data-health
    board cannot answer "are these the bytes we pinned?" at all.
    """
    path = _sql_str(cfg.path_for("manifest_path"))
    return f"""CREATE OR REPLACE VIEW raw_manifest AS
SELECT key AS month,
       json_extract_string(files, '$."' || key || '".file')            AS file,
       CAST(json_extract(files, '$."' || key || '".bytes') AS BIGINT)  AS bytes,
       json_extract_string(files, '$."' || key || '".sha256')          AS sha256
FROM (SELECT files, unnest(json_keys(files)) AS key
      FROM read_json({path}, columns={{'files': 'JSON'}}))"""


def _unknown_domains_sql(cfg: DataConfig) -> str:
    """Values the data contains that the TLC dictionary does not describe.

    Added at M1-S2 by the Data Contract Review (DCR-02/DCR-04). The contract
    already refuses a column that appears, vanishes or is renamed; nothing was
    watching a column whose VALUES quietly grow a new code. That failure has no
    symptom on a dashboard — the new code just becomes a category, and
    ``payment_type = 0`` in particular becomes a payment method nobody can name.

    Reporting only, deliberately. Turning this into a rejection rule would drop
    261,781 rows over fields that are not the target — the same call S1 declined
    to make for ``passenger_count``, and not the DA's to make alone.
    """
    branches = []
    for column, allowed in cfg.analyst["known_domains"].items():
        literals = ", ".join(_sql_str(v) for v in allowed)
        branches.append(
            f"SELECT {_sql_str(column)} AS column_name, split, month, "
            f"CAST({column} AS VARCHAR) AS value, COUNT(*) AS rows "
            f"FROM trips_clean "
            f"WHERE {column} IS NOT NULL AND CAST({column} AS VARCHAR) NOT IN ({literals}) "
            f"GROUP BY 1, 2, 3, 4"
        )
    return "CREATE OR REPLACE VIEW unknown_domain_values AS\n" + "\nUNION ALL\n".join(branches)


def build_sql(cfg: DataConfig) -> list[str]:
    """Every statement the layer is made of, in order. Pure — runs no query."""
    return [
        _trips_clean_sql(cfg),
        "CREATE OR REPLACE VIEW trips_train AS SELECT * FROM trips_clean WHERE split = 'train'",
        "CREATE OR REPLACE VIEW trips_val   AS SELECT * FROM trips_clean WHERE split = 'val'",
        "CREATE OR REPLACE VIEW trips_test  AS SELECT * FROM trips_clean WHERE split = 'test'",
        _manifest_sql(cfg),
        _months_sql(cfg),
        _rejections_sql(cfg),
        # The board-ready join: rows kept, what fraction was dropped, and the pin
        # of the bytes those rows came from — one row per month.
        """CREATE OR REPLACE VIEW data_health AS
SELECT m.split, m.month, m.rows_in, m.rows_out, m.rows_rejected,
       ROUND(100 * m.rejected_fraction, 3) AS rejected_pct,
       r.file AS raw_file, r.bytes AS raw_bytes, r.sha256 AS raw_sha256
FROM ingest_months m JOIN raw_manifest r USING (month)""",
        # Kept OUT of data_health on purpose: this one scans the trips, and a
        # health board that costs a 56M-row scan every refresh gets turned off.
        _unknown_domains_sql(cfg),
    ]


def connect(cfg: DataConfig, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open the catalogue. `read_only=True` is what an analyst session should use."""
    path = database_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path), read_only=read_only)


def build(cfg: DataConfig | None = None) -> list[str]:
    """(Re)create every view. Idempotent by construction — CREATE OR REPLACE."""
    cfg = cfg or load_config()
    missing = [
        str(cfg.processed_path(m)) for m in cfg.splits.months if not cfg.processed_path(m).exists()
    ]
    if missing:
        raise FileNotFoundError(
            "the analyst layer is a view over processed data that is not there: "
            f"{missing[0]} (and {len(missing) - 1} more). Run `make ingest` first."
        )
    con = connect(cfg)
    try:
        for statement in build_sql(cfg):
            con.execute(statement)
        names = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
    finally:
        con.close()
    return names


def reconciliation(cfg: DataConfig) -> list[tuple[str, str, int, int, bool]]:
    """Count the rows the views actually see against what S1 said it wrote.

    This is the S2 acceptance question asked in SQL: does a query over the clean
    view agree with the manifest of the ingest that produced it? A view that
    quietly points at five months of eight would otherwise look perfectly
    healthy — every number it returns would just be smaller.
    """
    con = connect(cfg, read_only=True)
    try:
        rows = con.execute(
            """
            SELECT c.split, c.month, c.observed, m.rows_out
            FROM (SELECT split, month, COUNT(*) AS observed
                  FROM trips_clean GROUP BY split, month) c
            JOIN ingest_months m USING (split, month)
            ORDER BY c.month
            """
        ).fetchall()
    finally:
        con.close()
    return [
        (split, month, observed, expected, observed == expected)
        for split, month, observed, expected in rows
    ]


def report(cfg: DataConfig | None = None) -> bool:
    """Build, then print the reconciliation. Returns True when every month agrees."""
    cfg = cfg or load_config()
    names = build(cfg)
    print(f"[duckdb] {database_path(cfg)}")
    print(f"[duckdb] {len(names)} view(s): {', '.join(sorted(names))}")

    rows = reconciliation(cfg)
    print("\n[duckdb] view rows vs the ingest report that wrote them")
    print("  split  month     view rows     rows_out    agree")
    print("  -----  -------  ------------  ------------  -----")
    for split, month, observed, expected, ok in rows:
        verdict = "yes" if ok else "NO"
        print(f"  {split:<5}  {month}  {observed:>12,}  {expected:>12,}  {verdict:>5}")
    total = sum(r[2] for r in rows)
    agreed = all(r[4] for r in rows)
    print(f"  {'ALL':<5}  {'':<7}  {total:>12,}")
    print(
        f"[duckdb] {'GREEN' if agreed else 'RED'} — {len(rows)} month(s), "
        f"every count reconciled: {agreed}"
    )
    return agreed
