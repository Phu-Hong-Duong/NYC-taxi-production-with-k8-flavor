"""The publish half of `make marts`: one body of SQL, two thin transports (M4-S5).

WHY THIS FILE EXISTS. Until M4-S5 the publish lived inside `scripts/marts.sh` as
shell: build the staging table, stream CSV into it, swap it in inside one
transaction, index. That was fine while the host was the only publisher. It stops
being fine the moment the pipeline publishes too, because a task pod **cannot use
the host's transport**: `marts.sh` reaches Postgres over `kubectl exec` (nothing
of ours publishes 5432 on the host — CLAUDE.md's port family annotates it
"in-cluster only"), and a pod has neither kubectl nor a kubeconfig. Giving a
pipeline stage cluster credentials so it can shell into another pod would be a
worse trade than any of the three alternatives `marts.sh` already rejects.

So there are two transports. What there is NOT is two copies of the SQL. The swap
is the most consequential SQL in this repo — it is the statement that decides what
a board renders — and a second copy in Python for the in-pod path would be the
twins failure this program keeps paying for (the port family, the split months,
`known_domains`). Everything below the `Transport` protocol is transport-blind:
the same statements, in the same order, whether they arrive over `kubectl exec -i`
or over a psycopg connection.

THE CSV PRODUCER IS ALSO ONE THING, AND IT IS A SUBPROCESS ON BOTH SIDES.
`scripts/marts_export.py` already owns the DuckDB half (the type mapping, the
schema resolution, the streaming `COPY … TO '/dev/stdout'`), unit-tested without a
cluster since M1-S4. Both transports run it as a child process and consume its
stdout — the host pipes it into `psql \\copy`, the pod pumps it into psycopg's
`COPY FROM STDIN`. One producer, two sinks; nothing re-implements the export.

D-003's DECISION LIVES HERE (see `publish`): the four small marts are full-refresh
and the fact table is month-scoped. The argument is in that docstring, with the
measured numbers.

IT ALSO OWNS THE dbt VARS, for the same anti-twins reason. `known_domains` and
`tolerance_minutes` are passed into the build from `configs/data.yaml` and
`configs/train.yaml` — one definition each, never copied into a `.sql` file — and
both publishers have to assemble the same payload. `dbt_vars` is that assembly;
`dbt_build` is the invocation, with `--no-partial-parse` welded on (gotcha #38).

Usage:
    python scripts/marts_publish.py --duckdb analytics/dbt/marts.duckdb
    python scripts/marts_publish.py --duckdb … --transport psycopg --months 2019-03
    python scripts/marts_publish.py --print-dbt-vars
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from collections.abc import Iterable
from pathlib import Path
from typing import IO, Protocol

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORTER = REPO_ROOT / "scripts" / "marts_export.py"

#: Every mart the publish moves, in dependency-free order (each is standalone in
#: Postgres). `trips_clean` is first because it is the expensive one — if the
#: stream is going to fail, fail before the cheap ones have been swapped. This
#: tuple is the ONLY list of marts in the repo: `scripts/marts.sh` imports the
#: publish rather than keeping its own copy, which is what stopped it being twins.
MARTS: tuple[str, ...] = (
    "trips_clean",
    "zone_hourly_stats",
    "monthly_kpis",
    "rejections_by_rule",
    "error_segments",
)

#: The one mart that is published by month rather than wholesale, and the column
#: that scopes it. See `publish` for why it is exactly this one.
INCREMENTAL_MART = "trips_clean"
INCREMENTAL_KEY = "month"

#: Schema `marts` inside database `marts`: Metabase is pointed at one schema, so a
#: mart that appears is a mart that was published — not one that happened to land
#: in `public` beside whatever else ever touches this database.
SCHEMA = "marts"

#: The indexes the boards actually use. Created after the swap because the swap
#: replaces the table (and with it any index), and because loading first and
#: indexing after is faster than the reverse. `IF NOT EXISTS` so the incremental
#: path — which never drops `trips_clean` — is a no-op here rather than an error.
INDEX_SQL = """
CREATE INDEX IF NOT EXISTS trips_clean_month_idx        ON marts.trips_clean (month);
CREATE INDEX IF NOT EXISTS trips_clean_pickup_zone_idx  ON marts.trips_clean ("PULocationID");
CREATE INDEX IF NOT EXISTS zone_hourly_month_zone_idx
    ON marts.zone_hourly_stats (month, pickup_zone);
"""


# ------------------------------------------------------------------ the dbt half ---


def dbt_vars(repo_root: Path = REPO_ROOT) -> dict:
    """The `--vars` payload, assembled from the configs that OWN each number.

    `known_domains` documents which TLC code values the dictionary describes
    (KPI-04 counts the rest); `tolerance_minutes` is KPI-12's tolerance and lives
    where KPI-10 already reads it. Neither has a default here, and that is
    deliberate: an absent `known_domains` would report 100% undocumented and look
    like a catastrophe, so an absent config must fail the build instead (M1-S4).
    """
    import yaml

    data = yaml.safe_load((repo_root / "configs" / "data.yaml").read_text())
    train = yaml.safe_load((repo_root / "configs" / "train.yaml").read_text())
    return {
        "known_domains": data["analyst"]["known_domains"],
        "tolerance_minutes": float(train["evaluate"]["tolerance_minutes"]),
    }


def dbt_build(dbt_dir: Path, *, variables: dict | None = None) -> None:
    """`dbt build` — models AND tests, interleaved, with the partial-parse cache off.

    `build` rather than `run && test`: build interleaves them per model, so a
    broken upstream is never fed to a downstream model that then also passes, and
    a red test stops the publish before a board can render it.

    `--no-partial-parse` IS LOAD-BEARING and it cost this project a broken build to
    learn (gotcha #38). dbt caches a parsed manifest whose node paths are recorded
    relative to the directory dbt was run FROM, so one hand-run from the repo root
    poisons every later build with an error naming a file that plainly exists.
    Measured cost of turning it off here: nothing — there are five models.
    """
    import json as _json

    # Resolved, because dbt reads `--profiles-dir` relative to ITS cwd — which this
    # function sets to the project directory. A relative `analytics/dbt` therefore
    # becomes `analytics/dbt/analytics/dbt` and dbt refuses with "Path does not
    # exist", naming a path that never existed anywhere. Observed on first run.
    dbt_dir = dbt_dir.resolve()
    payload = _json.dumps(dbt_vars() if variables is None else variables)
    env = {
        **os.environ,
        # gotcha #32's dbt sibling. dbt_project.yml's `flags:` block covers
        # project-aware runs; these cover everything else dbt does.
        "DO_NOT_TRACK": "1",
        "DBT_SEND_ANONYMOUS_USAGE_STATS": "false",
        "DBT_PROFILES_DIR": str(dbt_dir),
    }
    subprocess.run(
        ["dbt", "build", "--no-partial-parse", "--vars", payload],
        cwd=str(dbt_dir), env=env, check=True,
    )


# --------------------------------------------------------------- the transports ---


class Transport(Protocol):
    """Everything the publish needs from a database it cannot see the same way twice.

    Four methods, and the split between them is the honest one: `execute` for
    statements whose result nobody reads, `query` for the two places a number
    comes back, `copy_in` for the one operation whose implementation genuinely
    differs between a pipe into `psql` and a psycopg `COPY FROM STDIN`.
    """

    def execute(self, statement: str) -> None: ...

    def query(self, statement: str) -> list[tuple]: ...

    def copy_in(self, table: str, source: IO[bytes]) -> None: ...

    def describe(self) -> str: ...


class KubectlTransport:
    """The HOST's route: `kubectl exec -i` into the postgres pod, as the superuser.

    This is M1-S4's transport, moved rather than rewritten. It is the only route
    the host has: 5432 is not published (the port family says so), and the three
    alternatives are recorded as rejected in `scripts/marts.sh`'s header — a
    NodePort for 5432 (publishes a database on the laptop), a babysat
    `port-forward` (a background process the recipe has to nurse), and DuckDB's
    `postgres` extension (an unpinned dependency downloaded inside the build path).

    It connects as `postgres` because `kubectl exec` gets in without a password at
    all; the tables it creates are handed to `MARTS_DB_USER` by `ALTER TABLE …
    OWNER TO` before the transaction commits, so the end state is identical to the
    pod's, where the connection IS that user.
    """

    def __init__(self, *, namespace: str, pod: str, context: str, database: str) -> None:
        self._base = [
            "kubectl", "--context", context, "-n", namespace, "exec", "-i", pod, "--",
            "psql", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", database,
        ]
        self._where = f"kubectl exec -i {namespace}/{pod} -- psql -U postgres -d {database}"

    def execute(self, statement: str) -> None:
        subprocess.run([*self._base, "-q", "-c", statement], check=True)

    def query(self, statement: str) -> list[tuple]:
        out = subprocess.run(
            [*self._base, "-tA", "-F", "\x1f", "-c", statement],
            check=True, capture_output=True, text=True,
        ).stdout
        return [tuple(line.split("\x1f")) for line in out.splitlines() if line]

    def copy_in(self, table: str, source: IO[bytes]) -> None:
        # `\copy` (client side) rather than `COPY … FROM STDIN` so psql reads OUR
        # stdin instead of needing server-side file access. Both ends stream:
        # nothing of this ever lands on disk as a temp file.
        subprocess.run(
            [*self._base, "-c",
             f'\\copy {table} FROM STDIN WITH (FORMAT csv, NULL \'\')'],
            stdin=source, check=True,
        )

    def describe(self) -> str:
        return self._where


class PsycopgTransport:
    """The POD's route: a direct TCP connection, as the `marts` user.

    A task pod resolves `postgres.platform.svc.cluster.local` and the port is open
    — the in-cluster half of the same split horizon F-023 named. psycopg costs no
    new dependency: the image already carries it as Optuna's driver (M3-S4).

    IT CONNECTS AS `marts`, NEVER AS THE SUPERUSER. That is M1-S5's rule applied to
    a pipeline stage: a seat that can drop the warehouse it reads is one misclick
    from a restore, and a scheduled task is a seat nobody is watching. `marts` owns
    the schema and every table in it, so it can do everything the publish needs and
    nothing outside it.

    The DSN carries the plain `postgresql://` scheme deliberately: the
    `postgresql+psycopg://` spelling this repo pins everywhere else is SQLAlchemy's
    (M3-S4 pinned it because SQLAlchemy reads a bare scheme as psycopg2). This is
    psycopg's own connect, which takes the plain one.
    """

    def __init__(self, dsn: str, *, where: str) -> None:
        import psycopg

        self._conn = psycopg.connect(dsn, autocommit=True)
        self._where = where

    def execute(self, statement: str) -> None:
        self._conn.execute(statement)

    def query(self, statement: str) -> list[tuple]:
        return list(self._conn.execute(statement).fetchall())

    def copy_in(self, table: str, source: IO[bytes]) -> None:
        sql = f"COPY {table} FROM STDIN WITH (FORMAT csv, NULL '')"
        with self._conn.cursor() as cur, cur.copy(sql) as writer:
            # 4 MiB chunks: big enough that a 7 GB stream is not 1.8M round trips,
            # small enough that the pod never holds a meaningful fraction of the
            # fact table in memory. The producer is a subprocess, so this loop is
            # the only place the bytes exist on this side.
            while chunk := source.read(4 << 20):
                writer.write(chunk)

    def describe(self) -> str:
        return self._where

    def close(self) -> None:
        self._conn.close()


# ------------------------------------------------------------------ the publish ---


def _exporter(duckdb_path: Path, mart: str, where: str | None) -> subprocess.Popen:
    """Start `marts_export.py` and hand back its stdout. The ONE CSV producer.

    `where` is an optional SQL predicate, which is what makes the month-scoped path
    possible without a second exporter: `marts_export.py csv … --where "month =
    '2019-03'"` filters inside DuckDB, so the pipe carries one month instead of
    eight and the filtering happens where the data already is.
    """
    argv = [sys.executable, str(EXPORTER), "csv", str(duckdb_path), mart]
    if where:
        argv += ["--where", where]
    return subprocess.Popen(argv, stdout=subprocess.PIPE)


def _ddl(duckdb_path: Path, mart: str) -> str:
    """The column list for the Postgres table, taken from the mart's OWN schema.

    DuckDB owns the type mapping (`marts_export.postgres_type`), so a column added
    upstream arrives here without a second schema to maintain.
    """
    return subprocess.run(
        [sys.executable, str(EXPORTER), "ddl", str(duckdb_path), mart],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def _stream(transport: Transport, duckdb_path: Path, mart: str, table: str,
            where: str | None) -> None:
    """Run the exporter into the transport, and fail if EITHER end failed.

    The producer is checked explicitly. A `Popen` whose stdout is consumed to EOF
    looks exactly the same whether it finished or died three rows in — the reader
    just sees a short stream — so the publish would otherwise commit a truncated
    mart and report success. This is #59's lesson in miniature: assert on the thing
    the component exists to produce, never on the absence of an error.
    """
    producer = _exporter(duckdb_path, mart, where)
    assert producer.stdout is not None
    try:
        transport.copy_in(table, producer.stdout)
    finally:
        producer.stdout.close()
        rc = producer.wait()
    if rc != 0:
        raise SystemExit(
            f"[marts] FAIL: the CSV export of {mart} exited {rc} — nothing was committed"
        )


def full_refresh(transport: Transport, duckdb_path: Path, mart: str, owner: str) -> None:
    """Load into `<mart>__staging` and swap it in at COMMIT. M1-S4's shape, intact.

    A reader either sees the old table or the new one and never a half-loaded one,
    and a publish that dies halfway leaves the previous mart serving. That property
    is why the staging table exists at all, and it is also what makes the peak
    disk cost real — see `publish`.
    """
    staging = f'{SCHEMA}."{mart}__staging"'
    transport.execute(f"DROP TABLE IF EXISTS {staging};")
    transport.execute(f"CREATE TABLE {staging} (\n  {_ddl(duckdb_path, mart)}\n);")
    _stream(transport, duckdb_path, mart, staging, None)
    transport.execute(
        f"BEGIN;\n"
        f'  DROP TABLE IF EXISTS {SCHEMA}."{mart}";\n'
        f'  ALTER TABLE {SCHEMA}."{mart}__staging" RENAME TO "{mart}";\n'
        f'  ALTER TABLE {SCHEMA}."{mart}" OWNER TO "{owner}";\n'
        f"COMMIT;"
    )


def replace_months(transport: Transport, duckdb_path: Path, mart: str,
                   months: Iterable[str]) -> None:
    """Replace exactly the named months of `mart`, in ONE transaction per month.

    The transaction boundary is per month and not around the whole set on purpose:
    each month is independently correct, so a stream that dies on the third month
    leaves the first two published and the rest untouched — which is a state the
    next run converges from, rather than one it has to reason about.

    The month values are quoted rather than parameterised because this statement
    travels through two transports, one of which is `psql -c` and has no bind
    parameters at all. They are not free-form input: `_check_months` refuses
    anything that is not `YYYY-MM` before a single character reaches SQL.
    """
    for month in months:
        transport.execute(
            f"BEGIN;\n"
            f"  DELETE FROM {SCHEMA}.\"{mart}\" WHERE {INCREMENTAL_KEY} = '{month}';\n"
            f"COMMIT;"
        )
        _stream(transport, duckdb_path, mart, f'{SCHEMA}."{mart}"',
                f"{INCREMENTAL_KEY} = '{month}'")


def _check_months(months: Iterable[str]) -> tuple[str, ...]:
    """`YYYY-MM` or nothing. The one place a month becomes SQL, so the one place to check."""
    checked = tuple(str(m).strip() for m in months)
    for month in checked:
        if len(month) != 7 or month[4] != "-" or not (month[:4] + month[5:]).isdigit():
            raise SystemExit(f"[marts] FAIL: {month!r} is not a YYYY-MM month")
    return checked


def reconcile(
    transport: Transport, duckdb_path: Path, mart: str
) -> list[tuple[str, int, int, bool]]:
    """Per-month row counts in Postgres against the same counts in DuckDB.

    THIS IS WHAT MAKES THE INCREMENTAL PATH SAFE, and it is the property the full
    refresh got for free. A full refresh cannot leave a month behind because it
    rewrites every month; a month-scoped publish can — a month deleted and then not
    re-streamed is a mart that is quietly short, answers every query happily, and
    just returns fewer rows (M1-S2's catalogue lesson, one layer downstream).

    So the publish asks both sides for the same aggregate and refuses to be green
    unless every month agrees. Cheap: `trips_clean_month_idx` makes the Postgres
    side an index-only scan, and DuckDB counts a parquet row group's metadata.
    """
    import duckdb as _duckdb

    con = _duckdb.connect(str(duckdb_path), read_only=True)
    try:
        analyst = REPO_ROOT / "data" / "analyst.duckdb"
        if analyst.exists():
            con.execute(f"ATTACH '{analyst}' AS analyst (READ_ONLY)")
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import marts_export

        source = dict(
            con.execute(
                f"SELECT {INCREMENTAL_KEY}, COUNT(*) FROM "
                f"{marts_export.resolve(con, mart)} GROUP BY 1"
            ).fetchall()
        )
    finally:
        con.close()

    published = {
        str(month): int(rows)
        for month, rows in transport.query(
            f'SELECT {INCREMENTAL_KEY}, COUNT(*) FROM {SCHEMA}."{mart}" GROUP BY 1'
        )
    }
    months = sorted(set(source) | set(published))
    return [
        (m, published.get(m, 0), int(source.get(m, 0)),
         published.get(m, 0) == int(source.get(m, 0)))
        for m in months
    ]


def publish(transport: Transport, duckdb_path: Path, *, owner: str,
            months: tuple[str, ...] | None = None) -> dict:
    """Publish every mart. `months=None` is a full refresh; otherwise month-scoped.

    **D-003's DECISION, AND ITS EVIDENCE.** The debt row asked for one of two
    things when the publish became scheduled: an incremental materialisation, or a
    recorded decision that full refresh stays, with the peak re-measured. The
    answer is neither wholesale — it is split, because the marts are not one kind
    of object:

    * **The four aggregates are full-refresh, forever.** `zone_hourly_stats`
      (44,792 rows), `monthly_kpis` (8), `rejections_by_rule` (80) and
      `error_segments` are tens of thousands of rows between them; rewriting all of
      them costs under a second and buys the strongest property a publish can have
      — the mart IS the source, with no possibility of drift. Incremental machinery
      here would be complexity bought with nothing.
    * **`trips_clean` is month-scoped**, and it is the only mart where that is both
      possible and worth it. It is 56,127,878 rows / 13 GB, its grain IS the month
      (which is also an indexed column), and it is the entire 23 GB peak the debt
      row is about: a full refresh holds the live 13 GB table AND its staging copy
      at once, with autovacuum working on the one about to be dropped. A monthly
      pipeline re-derives ONE month, so a full refresh republishes ~7.5M changed
      rows by rewriting 56M — eight months of work to land one.

    What the split costs, said plainly: the fact table can now drift from its
    source in a way a full refresh made impossible, so `reconcile` runs after every
    month-scoped publish and the stage fails unless every month's count agrees on
    both sides. That check is the price of the decision and it is not optional.

    Returns a summary the pipeline stage turns into its typed result: which marts
    were published, how, in how long, and (on the scoped path) the per-month
    reconciliation that had to agree for this call to return at all.
    """
    started = time.monotonic()
    reconciled: list[tuple[str, int, int, bool]] = []
    transport.execute(f'CREATE SCHEMA IF NOT EXISTS {SCHEMA} AUTHORIZATION "{owner}";')

    existing = {
        row[0] for row in transport.query(
            f"SELECT tablename FROM pg_tables WHERE schemaname = '{SCHEMA}'"
        )
    }

    for mart in MARTS:
        scoped = months is not None and mart == INCREMENTAL_MART and mart in existing
        if scoped:
            assert months is not None
            print(f"[marts] {mart}: replacing {len(months)} month(s) — {', '.join(months)}")
            replace_months(transport, duckdb_path, mart, months)
        else:
            if months is not None and mart == INCREMENTAL_MART:
                # First publish of the fact table (or a table somebody dropped):
                # there is nothing to replace month-scoped, so the honest thing is
                # a full refresh, said out loud rather than silently.
                print(f"[marts] {mart}: no published table to scope — FULL refresh this once")
            else:
                print(f"[marts] publishing {mart} …")
            full_refresh(transport, duckdb_path, mart, owner)

    transport.execute(INDEX_SQL)

    if months is not None:
        reconciled = reconcile(transport, duckdb_path, INCREMENTAL_MART)
        print(f"\n[marts] {INCREMENTAL_MART}: published rows vs the analyst layer, by month")
        print("  month     published        source    agree")
        print("  -------  ------------  ------------  -----")
        for month, got, want, ok in reconciled:
            print(f"  {month}  {got:>12,}  {want:>12,}  {'yes' if ok else 'NO':>5}")
        bad = [r for r in reconciled if not r[3]]
        if bad:
            raise SystemExit(
                f"[marts] FAIL: {len(bad)} month(s) disagree between the published mart and "
                "its source. A month-scoped publish that loses a month answers every query "
                "happily and just returns fewer rows — this is the check that refuses to let it."
            )
        print(f"  [marts] ok  {len(reconciled)} month(s) reconcile")

    seconds = time.monotonic() - started
    print(f"\n[marts] published {len(MARTS)} mart(s) into '{SCHEMA}' via {transport.describe()} "
          f"in {seconds:.1f}s")
    approx_rows = {}
    for name, approx in transport.query(
        "SELECT relname, n_live_tup FROM pg_stat_user_tables "
        f"WHERE schemaname = '{SCHEMA}' ORDER BY relname"
    ):
        approx_rows[str(name)] = int(approx)
        print(f"[marts]   {name:<20} ~{int(approx):,} rows")
    return {
        "marts": list(MARTS),
        "months": list(months or ()),
        "mode": "month-scoped" if months else "full-refresh",
        "seconds": round(seconds, 1),
        "transport": transport.describe(),
        "approx_rows": approx_rows,
        "reconciled": [
            {"month": m, "published": got, "source": want, "agree": ok}
            for m, got, want, ok in reconciled
        ],
    }


# ---------------------------------------------------------------------- the CLI ---


def _env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def marts_owner() -> str:
    """Who owns the published tables: the environment, or `.env` as the fallback.

    The environment wins because a task pod HAS no `.env` (M4-S3: the image carries
    no secret file) — it gets `MARTS_DB_USER` by reference from the
    `flyte-task-marts` Secret. On the host `.env` is the only copy. Both callers go
    through here so the answer cannot differ between them.
    """
    owner = os.environ.get("MARTS_DB_USER") or _env_file(REPO_ROOT / ".env").get("MARTS_DB_USER")
    if not owner:
        raise SystemExit(
            "[marts] FAIL: MARTS_DB_USER is set neither in the environment nor in .env. "
            "In a task pod it arrives from the `flyte-task-marts` Secret by reference "
            "(infra/manifests/flyte-task-podtemplate.yaml); on the host, "
            "`make deploy-platform` writes it."
        )
    return owner


def make_transport(kind: str, *, database: str) -> Transport:
    """Build the transport by name, taking credentials from the environment only.

    Neither transport ever puts a password on a command line: the host's does not
    need one (`kubectl exec` authenticates as the pod's superuser), and the pod's
    reads `MARTS_DB_PASSWORD` out of its environment, which arrives from the
    `flyte-task-marts` Secret by reference.
    """
    if kind == "kubectl":
        return KubectlTransport(
            namespace=os.environ.get("POSTGRES_NAMESPACE", "platform"),
            pod=os.environ.get("POSTGRES_POD", "postgres-0"),
            context=os.environ.get("KUBE_CONTEXT", "kind-mlops-taxi"),
            database=database,
        )
    if kind == "psycopg":
        host = os.environ.get("MARTS_DB_HOST", "postgres.platform.svc.cluster.local")
        port = os.environ.get("MARTS_DB_PORT", "5432")
        user = marts_owner()
        password = os.environ.get("MARTS_DB_PASSWORD") or _env_file(
            REPO_ROOT / ".env"
        ).get("MARTS_DB_PASSWORD", "")
        return PsycopgTransport(
            f"postgresql://{user}:{password}@{host}:{port}/{database}",
            where=f"psycopg {user}@{host}:{port}/{database}",
        )
    raise SystemExit(f"[marts] unknown transport {kind!r} — expected 'kubectl' or 'psycopg'")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/marts_publish.py", description=__doc__)
    parser.add_argument("--duckdb", help="path to dbt's marts.duckdb")
    parser.add_argument(
        "--print-dbt-vars", action="store_true",
        help="print the --vars payload and exit; scripts/marts.sh builds with it, "
        "so the two publishers cannot pass different numbers into the same models",
    )
    parser.add_argument("--transport", default="kubectl", choices=("kubectl", "psycopg"))
    parser.add_argument("--database", default="marts")
    parser.add_argument(
        "--months", default="",
        help="comma-separated YYYY-MM to replace in the fact table. Empty = full "
        "refresh of every mart (the M1-S4 behaviour, and what a rebuild wants).",
    )
    args = parser.parse_args(argv)

    if args.print_dbt_vars:
        import json as _json

        print(_json.dumps(dbt_vars()))
        return 0
    if not args.duckdb:
        raise SystemExit("[marts] --duckdb is required unless --print-dbt-vars is given")

    owner = marts_owner()
    months = _check_months(m for m in args.months.split(",") if m.strip()) or None
    transport = make_transport(args.transport, database=args.database)
    try:
        publish(transport, Path(args.duckdb), owner=owner, months=months)
    finally:
        close = getattr(transport, "close", None)
        if close is not None:
            close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
