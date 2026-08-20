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

from .clean import RULE_COLUMN
from .config import DataConfig, load_config

# Every view this layer publishes, in creation order. The DA cites these names;
# `tests/unit/test_data_analyst.py` asserts the list matches what a real build
# creates, so a view cannot be renamed here and left dangling in a report.
VIEWS = (
    "trips_clean",
    "trips_train",
    "trips_val",
    "trips_test",
    "trips_rejected",
    "raw_manifest",
    "ingest_months",
    "ingest_rejections",
    "data_health",
    "unknown_domain_values",
)

#: Views that exist only once something upstream of the DATA path has run. The
#: catalogue must build without them: `make data`, `make rebuild-proof` and the
#: whole M1 gate run on a repo where no model has ever been fitted, and a data
#: layer that refuses to build until someone trains a model would make the data
#: path depend on the modelling path — exactly backwards. When the files are
#: absent the view is skipped OUT LOUD, never silently.
OPTIONAL_VIEWS = ("predictions", "prediction_runs")

#: The scoring layer (M7-S1). Four views mirroring the four the split months
#: get, and deliberately SEPARATE from them rather than unioned in.
#:
#: `trips_clean` is what the training matrix, the dbt marts and every Metabase
#: board read. Unioning 2020 into it would put COVID months behind numbers whose
#: definitions, windows and KPI ids were all written about the settled 2019 data
#: — silently, with every query still returning a plausible answer, which is the
#: exact failure mode M1-S2's catalogue reconciliation exists to catch one layer
#: up. So the scoring months get their own names, and a consumer that wants them
#: has to say so.
#:
#: Optional for `predictions`' reason: `make data`, `make rebuild-proof` and the
#: whole M1 gate run on a repo where no scoring month has ever been ingested,
#: and a data layer that refuses to build without one would make the settled
#: path depend on the new one. Skipped OUT LOUD, never silently.
SCORING_VIEWS = (
    "trips_scoring",
    "trips_scoring_rejected",
    "scoring_months",
    "scoring_rejections",
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


def _trips_rejected_sql(cfg: DataConfig) -> str:
    """The rows the contract threw away (M2-S1, F-005) — the counts' missing half.

    Same shape as ``trips_clean`` and for the same reasons: ``*`` because the
    sidecar's schema was already decided at ingest, and ``split``/``month`` as
    config literals so a renamed file cannot relabel data. What it adds is
    ``rejection_rule`` (the rule that filed the row, matching the report's
    ``rejected_by``) and ``rejection_rules`` (every rule it violates).

    Deliberately NOT unioned into ``trips_clean``. These rows failed the output
    contract on purpose; one careless ``SELECT * FROM trips`` must never be able
    to train on them.
    """
    branches = [
        f"SELECT {_sql_str(cfg.splits.split_of(month))} AS split, "
        f"{_sql_str(month)} AS month, * "
        f"FROM read_parquet({_sql_str(cfg.rejected_path(month))})"
        for month in cfg.splits.months
    ]
    return "CREATE OR REPLACE VIEW trips_rejected AS\n" + "\nUNION ALL\n".join(branches)


def ingested_scoring_months(cfg: DataConfig) -> list[str]:
    """The scoring months that are actually on disk (M7-S1).

    Both trees are required, exactly as `build` requires both for the split
    months: a kept file with no sidecar is a month whose rejections cannot be
    reconciled, and the whole point of the sidecar is that they can be.
    """
    return [
        month
        for month in cfg.scoring_months
        if cfg.scoring_path(month).exists() and cfg.scoring_rejected_path(month).exists()
    ]


def _scoring_sql(cfg: DataConfig, months: list[str]) -> list[str]:
    """The four scoring views, same shapes as their settled-month counterparts.

    `split` is the literal 'scoring' rather than a config lookup, and it is a
    column rather than an omission on purpose: these frames are unioned into
    memos and boards beside the 2019 ones, and a row with no label is a row
    somebody will label by hand. The MONTH is a config literal, like everywhere
    else in this file — a renamed file must not be able to relabel data.
    """
    label = _sql_str("scoring")

    def union(statements: list[str]) -> str:
        return "\nUNION ALL\n".join(statements)

    trips = [
        f"SELECT {label} AS split, {_sql_str(m)} AS month, * "
        f"FROM read_parquet({_sql_str(cfg.scoring_path(m))})"
        for m in months
    ]
    rejected = [
        f"SELECT {label} AS split, {_sql_str(m)} AS month, * "
        f"FROM read_parquet({_sql_str(cfg.scoring_rejected_path(m))})"
        for m in months
    ]
    monthly = [
        f"SELECT {label} AS split, month, rows_in, rows_out, rows_rejected, rejected_fraction "
        f"FROM read_json_auto({_sql_str(cfg.scoring_rejections_path(m))})"
        for m in months
    ]
    rules = [
        f"SELECT {label} AS split, month, "
        "rule.name AS rule, rule.rejected_by AS rejected_by, rule.matched AS matched "
        "FROM (SELECT month, unnest(rules) AS rule "
        f"FROM read_json_auto({_sql_str(cfg.scoring_rejections_path(m))}))"
        for m in months
    ]
    return [
        "CREATE OR REPLACE VIEW trips_scoring AS\n" + union(trips),
        "CREATE OR REPLACE VIEW trips_scoring_rejected AS\n" + union(rejected),
        "CREATE OR REPLACE VIEW scoring_months AS\n" + union(monthly),
        "CREATE OR REPLACE VIEW scoring_rejections AS\n" + union(rules),
    ]


def predicted_months(cfg: DataConfig) -> list[str]:
    """The held-out months a model has actually been scored on (M2-S4).

    Train months are deliberately not looked for: publishing a model's
    predictions on the data it was fitted to would put a number on a board that
    describes memorisation. Only val and test are ever scored.
    """
    return [
        month
        for month in cfg.splits.val + cfg.splits.test
        if cfg.predictions_path(month).exists()
    ]


def _predictions_sql(cfg: DataConfig, months: list[str]) -> str:
    """Row-level model output, one row per held-out trip (M2-S4).

    `split` and `month` come from the parquet here rather than from a config
    literal — the opposite of every other view in this file, and for a reason
    that is the same law read from the other side. The trip views label rows the
    ingest produced, so config is the authority. THESE rows were labelled by
    `taxi_mlops.training.score` at the moment the model was scored, and the label
    is part of the model's claim: if the file says `test` and the config says
    `val`, the honest answer is that they disagree — which the reconciliation
    below reports — not that the config wins and the disagreement disappears.

    Derived columns are computed HERE, once, so that every card, mart and memo
    query means the same thing by "error": `abs_error_minutes` is
    `ABS(predicted - actual)` in one place and the model's floor gets the
    identical treatment (`predictions.py: DERIVED_IN_SQL`).
    """
    branches = [
        f"SELECT * FROM read_parquet({_sql_str(cfg.predictions_path(month))})"
        for month in months
    ]
    return (
        "CREATE OR REPLACE VIEW predictions AS\nSELECT *,\n"
        "       predicted_minutes - actual_minutes                  AS signed_error_minutes,\n"
        "       ABS(predicted_minutes - actual_minutes)             AS abs_error_minutes,\n"
        "       ABS(floor_predicted_minutes - actual_minutes)       AS floor_abs_error_minutes\n"
        "FROM (\n" + "\nUNION ALL\n".join(branches) + "\n)"
    )


def _prediction_runs_sql(cfg: DataConfig) -> str:
    """The evaluator's OWN numbers, read back from the manifest it wrote (M2-S4).

    The sibling of ``raw_manifest``, and it exists for the same reason: provenance
    is metadata, and a question like "which champion produced these rows, and what
    did the evaluator measure for it?" has to be answerable in SQL or it gets
    answered from a transcript.

    This view is the ONLY place `kpi_09`/`kpi_10` appear in the analyst layer, and
    it does not compute them — it reports what
    ``taxi_mlops.training.evaluate`` measured, verbatim, from the JSON that code
    wrote (gotcha #15 forbids a second producer, not a reader). It is deliberately
    NOT published to Postgres: nothing a board can reach may carry those two ids,
    so the only consumer is the dbt test that checks ``error_segments``' whole-split
    row against them.
    """
    path = _sql_str(cfg.predictions_manifest_path())
    return f"""CREATE OR REPLACE VIEW prediction_runs AS
SELECT json_extract_string(model, '$.name')                            AS model_name,
       json_extract_string(model, '$.version')                         AS model_version,
       json_extract_string(model, '$.alias')                           AS model_alias,
       json_extract_string(model, '$.run_id')                          AS run_id,
       CAST(tolerance_minutes AS DOUBLE)                               AS tolerance_minutes,
       json_extract_string(s, '$.contender')                           AS contender,
       json_extract_string(s, '$.split')                               AS split,
       CAST(json_extract(s, '$.rows') AS BIGINT)                       AS rows,
       CAST(json_extract(s, '$.kpi_09_mae_minutes') AS DOUBLE)         AS kpi_09_mae_minutes,
       CAST(json_extract(s, '$.kpi_10_within_tolerance_pct') AS DOUBLE)
                                                                       AS kpi_10_within_pct
FROM (SELECT model, tolerance_minutes, unnest(json_extract(splits, '$[*]')) AS s
      FROM read_json({path}, columns={{'model': 'JSON', 'floor': 'JSON',
                                       'tolerance_minutes': 'DOUBLE', 'splits': 'JSON'}}))"""


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
    statements = [
        _trips_clean_sql(cfg),
        "CREATE OR REPLACE VIEW trips_train AS SELECT * FROM trips_clean WHERE split = 'train'",
        "CREATE OR REPLACE VIEW trips_val   AS SELECT * FROM trips_clean WHERE split = 'val'",
        "CREATE OR REPLACE VIEW trips_test  AS SELECT * FROM trips_clean WHERE split = 'test'",
        _trips_rejected_sql(cfg),
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
    scoring = ingested_scoring_months(cfg)
    if scoring:
        statements.extend(_scoring_sql(cfg, scoring))
    months = predicted_months(cfg)
    if months:
        statements.append(_predictions_sql(cfg, months))
    if cfg.predictions_manifest_path().exists():
        statements.append(_prediction_runs_sql(cfg))
    return statements


def connect(cfg: DataConfig, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open the catalogue. `read_only=True` is what an analyst session should use."""
    path = database_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path), read_only=read_only)


def build(cfg: DataConfig | None = None) -> list[str]:
    """(Re)create every view. Idempotent by construction — CREATE OR REPLACE."""
    cfg = cfg or load_config()
    # Both trees are checked, because both are viewed. A missing sidecar would
    # otherwise surface as a DuckDB error deep inside someone's query rather
    # than as "run `make ingest`" here.
    missing = [
        str(path)
        for month in cfg.splits.months
        for path in (cfg.processed_path(month), cfg.rejected_path(month))
        if not path.exists()
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


def rejection_reconciliation(cfg: DataConfig) -> list[tuple[str, str, str, int, int, bool]]:
    """Count the SIDECAR rows per (month, rule) against what the report counted.

    The same law as `reconciliation`, applied to the half of the data F-005 made
    queryable, and it has to be per RULE rather than per month: a sidecar that
    files every row under the wrong rule has a perfect monthly total and is
    useless for the one question it exists to answer.

    FULL OUTER JOIN on purpose. A rule that the report knows and the sidecar
    lacks is caught by a LEFT join; a rule name appearing only in the sidecar —
    what a renamed rule would look like mid-change — is caught only by a FULL
    one, and it is the rows-with-no-home case.
    """
    con = connect(cfg, read_only=True)
    try:
        rows = con.execute(
            f"""
            SELECT COALESCE(r.split, s.split)   AS split,
                   COALESCE(r.month, s.month)   AS month,
                   COALESCE(r.rule,  s.rule)    AS rule,
                   COALESCE(s.observed, 0)      AS observed,
                   COALESCE(r.rejected_by, 0)   AS expected
            FROM ingest_rejections r
            FULL OUTER JOIN (
                SELECT split, month, {RULE_COLUMN} AS rule, COUNT(*) AS observed
                FROM trips_rejected GROUP BY 1, 2, 3
            ) s USING (split, month, rule)
            ORDER BY month, rule
            """
        ).fetchall()
    finally:
        con.close()
    return [
        (split, month, rule, observed, expected, observed == expected)
        for split, month, rule, observed, expected in rows
    ]


def scoring_reconciliation(cfg: DataConfig) -> list[tuple[str, int, int, bool]]:
    """Scoring-view rows vs the ingest report that wrote them (M7-S1).

    The same question `reconciliation` asks of the settled months, asked of the
    new tree, and it is not optional politeness: the scoring months are what
    M7's drift numbers are computed over, and a view pointing at two months of
    three answers every drift query happily and just describes less of the world.
    """
    con = connect(cfg, read_only=True)
    try:
        rows = con.execute(
            """
            SELECT c.month, c.observed, m.rows_out
            FROM (SELECT month, COUNT(*) AS observed FROM trips_scoring GROUP BY month) c
            FULL OUTER JOIN (SELECT month, rows_out FROM scoring_months) m USING (month)
            ORDER BY month
            """
        ).fetchall()
    finally:
        con.close()
    return [
        (month, observed or 0, expected or 0, (observed or 0) == (expected or 0))
        for month, observed, expected in rows
    ]


def scoring_rejection_reconciliation(cfg: DataConfig) -> list[tuple[str, str, int, int, bool]]:
    """The scoring sidecar per (month, rule) vs what the report counted (M7-S1).

    Per RULE and not per month, for M2-S1's reason: a sidecar that files every
    row under the wrong rule has a perfect monthly total and is useless for the
    one question it exists to answer. FULL OUTER for the same reason too — a
    rule name appearing only on one side is what a renamed rule looks like
    mid-change, and only a full join sees it.
    """
    con = connect(cfg, read_only=True)
    try:
        rows = con.execute(
            f"""
            SELECT COALESCE(r.month, s.month)   AS month,
                   COALESCE(r.rule,  s.rule)    AS rule,
                   COALESCE(s.observed, 0)      AS observed,
                   COALESCE(r.rejected_by, 0)   AS expected
            FROM scoring_rejections r
            FULL OUTER JOIN (
                SELECT month, {RULE_COLUMN} AS rule, COUNT(*) AS observed
                FROM trips_scoring_rejected GROUP BY 1, 2
            ) s USING (month, rule)
            ORDER BY month, rule
            """
        ).fetchall()
    finally:
        con.close()
    return [
        (month, rule, observed, expected, observed == expected)
        for month, rule, observed, expected in rows
    ]


def prediction_reconciliation(cfg: DataConfig) -> list[tuple[str, str, int, int, bool]]:
    """Every held-out row got exactly one prediction, or `make duckdb` exits 1.

    The third reconciliation this layer runs, and the one that guards a specific
    lie: a model scored on 5.9M of 6.2M val rows produces a perfectly plausible
    MAE. Nothing about the number looks wrong — it is simply an average over a
    subset nobody chose. So the count is checked against the SAME authority the
    trip views are checked against, the ingest report's `rows_out`.

    FULL OUTER JOIN, like the rejected-row check, and here it earns its keep
    twice: a (split, month) present only in the predictions is what a mislabelled
    holdout looks like, and a month present only in `ingest_months` is a split
    the predictions never covered.
    """
    con = connect(cfg, read_only=True)
    try:
        rows = con.execute(
            """
            SELECT COALESCE(p.split, m.split) AS split,
                   COALESCE(p.month, m.month) AS month,
                   COALESCE(p.observed, 0)    AS observed,
                   COALESCE(m.rows_out, 0)    AS expected
            FROM (SELECT split, month, COUNT(*) AS observed
                  FROM predictions GROUP BY 1, 2) p
            FULL OUTER JOIN (SELECT split, month, rows_out
                             FROM ingest_months
                             WHERE split IN ('val', 'test')) m USING (split, month)
            ORDER BY month
            """
        ).fetchall()
    finally:
        con.close()
    return [
        (split, month, observed, expected, observed == expected)
        for split, month, observed, expected in rows
    ]


def report(cfg: DataConfig | None = None) -> bool:
    """Build, then print every reconciliation. Returns True when everything agrees."""
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

    rejected_rows = rejection_reconciliation(cfg)
    disagreed = [r for r in rejected_rows if not r[5]]
    width = max([len(r[2]) for r in rejected_rows] + [len("rule")])
    print("\n[duckdb] retained rejected rows vs the per-rule counts (F-005)")
    print(f"  split  month    {'rule'.ljust(width)}    sidecar   rejected_by  agree")
    print(f"  -----  -------  {'-' * width}  -----------  ------------  -----")
    # Only the disagreements are printed row by row: 8 months x 10 rules is 80
    # lines of 'yes' that nobody reads, and a table nobody reads is where a 'NO'
    # hides. The totals below are what the eye is meant to land on.
    for split, month, rule, observed, expected, _ok in disagreed:
        print(
            f"  {split:<5}  {month}  {rule.ljust(width)}  "
            f"{observed:>11,}  {expected:>12,}     NO"
        )
    sidecar_total = sum(r[3] for r in rejected_rows)
    counted_total = sum(r[4] for r in rejected_rows)
    rejected_agreed = not disagreed
    print(
        f"  {'ALL':<5}  {'':<7}  {'(all rules)'.ljust(width)}  {sidecar_total:>11,}"
        f"  {counted_total:>12,}  {'yes' if rejected_agreed else 'NO':>5}"
    )
    print(
        f"  {len(rejected_rows)} (month, rule) pair(s) checked, "
        f"{len(disagreed)} disagreement(s)"
    )

    # ---- the fourth and fifth reconciliations: the scoring tree (M7-S1).
    scoring_agreed = True
    scoring = ingested_scoring_months(cfg)
    print(
        "\n[duckdb] scoring months (M7): view rows vs the ingest report, "
        "and the sidecar per rule"
    )
    if not scoring:
        print(
            "  none — no month of "
            f"{list(cfg.scoring_months) or '(none configured)'} is ingested under "
            f"{cfg.scoring.get('dir', 'data/scoring')}/. Run `make ingest-scoring`; "
            "the settled 2019 path does not depend on it."
        )
    else:
        scoring_rows = scoring_reconciliation(cfg)
        print("  month     view rows     rows_out    agree")
        print("  -------  ------------  ------------  -----")
        for month, observed, expected, row_ok in scoring_rows:
            print(
                f"  {month}  {observed:>12,}  {expected:>12,}  "
                f"{'yes' if row_ok else 'NO':>5}"
            )
        scoring_rules = scoring_rejection_reconciliation(cfg)
        scoring_bad = [r for r in scoring_rules if not r[4]]
        for month, rule, observed, expected, _ok in scoring_bad:
            print(f"  {month}  rule {rule}: sidecar {observed:,} != rejected_by {expected:,}   NO")
        scoring_agreed = all(r[3] for r in scoring_rows) and not scoring_bad
        print(
            f"  {'ALL':<7}  {sum(r[1] for r in scoring_rows):>12,}"
            f"  {sum(r[2] for r in scoring_rows):>12,}  "
            f"{'yes' if scoring_agreed else 'NO':>5}"
        )
        print(
            f"  {len(scoring_rules)} (month, rule) pair(s) checked, "
            f"{len(scoring_bad)} disagreement(s); sidecar rows "
            f"{sum(r[2] for r in scoring_rules):,} == counted "
            f"{sum(r[3] for r in scoring_rules):,}"
        )

    # ---- the third reconciliation: one prediction per held-out row (M2-S4).
    predicted_agreed = True
    months = predicted_months(cfg)
    print("\n[duckdb] published predictions vs the held-out rows they claim to cover")
    if not months:
        print(
            "  none — no model output under "
            f"{cfg.predictions_dir}/ yet. Run `make predictions` (M2-S4); the data "
            "path does not depend on it."
        )
    else:
        predicted = prediction_reconciliation(cfg)
        print("  split  month    prediction rows      rows_out    agree")
        print("  -----  -------  ---------------  ------------  -----")
        for split, month, observed, expected, row_ok in predicted:
            print(
                f"  {split:<5}  {month}  {observed:>15,}  {expected:>12,}  "
                f"{'yes' if row_ok else 'NO':>5}"
            )
        predicted_agreed = all(r[4] for r in predicted)
        print(
            f"  {'ALL':<5}  {'':<7}  {sum(r[2] for r in predicted):>15,}"
            f"  {sum(r[3] for r in predicted):>12,}  "
            f"{'yes' if predicted_agreed else 'NO':>5}"
        )

    ok = agreed and rejected_agreed and predicted_agreed and scoring_agreed
    print(
        f"[duckdb] {'GREEN' if ok else 'RED'} — {len(rows)} month(s), "
        f"every count reconciled: {ok}"
    )
    return ok
