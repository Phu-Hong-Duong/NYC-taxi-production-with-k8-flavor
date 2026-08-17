"""Unit tests for the gold marts layer (M1-S4) — cluster-free, dbt-free.

These pin the DECISIONS, not the numbers. The numbers are proved by `dbt build`
(34 data tests) and by the publish's row-count read-back; what a fast test can
protect is the set of choices that are easy to undo by accident six months from
now: the telemetry opt-out, the boundary law, the one-source-of-truth rules, and
the fact that no password ever reaches a command line.

Every test states the failure it prevents in its own docstring, because a red
test whose reason lives in a commit message is a red test nobody can act on.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
DBT = REPO / "analytics" / "dbt"
MODELS = DBT / "models" / "marts"

pytestmark = pytest.mark.unit


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# gotcha #32's dbt sibling: what does this tool send, and to whom?
# --------------------------------------------------------------------------- #


def test_dbt_telemetry_is_off():
    """dbt phones home by default; this program's charter says nothing leaves.

    `uv add dbt-duckdb` pulled `snowplow-tracker` in as a dependency — that is
    the telemetry client, and it is opt-OUT. Prevents: a future `dbt init`, or a
    tidy-up of dbt_project.yml, silently restoring the default.
    """
    project = yaml.safe_load(read(DBT / "dbt_project.yml"))
    assert project["flags"]["send_anonymous_usage_stats"] is False

    script = read(REPO / "scripts" / "marts.sh")
    assert "export DO_NOT_TRACK=1" in script
    assert "export DBT_SEND_ANONYMOUS_USAGE_STATS=false" in script


def test_profiles_yml_has_no_config_block():
    """dbt 1.12 REFUSES to start if `config:` and `flags:` are both set.

    Observed 2026-08-16: "Do not specify both 'config' in profiles.yml and
    'flags' in dbt_project.yml". Prevents: someone belt-and-bracing the opt-out
    back into profiles.yml and breaking every build to do it.
    """
    profiles = yaml.safe_load(read(DBT / "profiles.yml"))
    assert "config" not in profiles


# --------------------------------------------------------------------------- #
# ADR-009 / gotcha #22 — marts serve humans
# --------------------------------------------------------------------------- #


def test_model_code_never_imports_a_mart():
    """The boundary law, checked the way gotcha #22 says to check it.

    Prevents: train/serve skew returning through the back door because a mart
    aggregate looked model-worthy and got imported instead of graduating through
    the feature dossier.
    """
    hits = subprocess.run(
        ["grep", "-rn", "analytics", str(REPO / "src" / "taxi_mlops")],
        capture_output=True,
        text=True,
    )
    assert hits.stdout == "", f"model code references analytics:\n{hits.stdout}"


# --------------------------------------------------------------------------- #
# One definition, one place (the twins law this repo keeps paying for)
# --------------------------------------------------------------------------- #


def test_known_domains_are_never_copied_into_sql():
    """KPI-04's domains live in configs/data.yaml and are passed in as a dbt var.

    Prevents: the twins failure. A domain list pasted into monthly_kpis.sql would
    drift the day someone adds `VendorID 6` to the config, and the KPI would keep
    reporting confidently.
    """
    sql = read(MODELS / "monthly_kpis.sql")
    assert "var('known_domains')" in sql
    # No default: an absent var must fail the build. An empty domain list would
    # silently report 100% of rows as undocumented.
    assert "var('known_domains'," not in sql

    domains = yaml.safe_load(read(REPO / "configs" / "data.yaml"))["analyst"]["known_domains"]
    for column, allowed in domains.items():
        literal = ", ".join(str(v) for v in allowed)
        assert literal not in sql, f"{column}'s domain is hardcoded in monthly_kpis.sql"

    script = read(REPO / "scripts" / "marts.sh")
    assert "known_domains" in script and "configs/data.yaml" in script


def test_dbt_sources_are_analyst_views_that_exist():
    """dbt reads the analyst layer, not the parquet (DA charter refusal #2).

    Prevents: dbt growing a SECOND definition of `split` and `month` via
    read_parquet(), which is exactly how two row counts start disagreeing.
    """
    # OPTIONAL_VIEWS counts: `predictions` and `prediction_runs` exist only after
    # a champion has been scored (M2-S4), and `error_segments` sources them. What
    # this test is actually protecting is that every name in sources.yml is a view
    # the analyst layer KNOWS ABOUT — a typo'd or deleted view still fails.
    from taxi_mlops.data.analyst import OPTIONAL_VIEWS, VIEWS

    sources = yaml.safe_load(read(MODELS.parent / "sources.yml"))["sources"]
    (analyst,) = [s for s in sources if s["name"] == "analyst"]
    named = {t["name"] for t in analyst["tables"]}
    missing = named - set(VIEWS) - set(OPTIONAL_VIEWS)
    assert not missing, f"sources.yml names views the analyst layer does not build: {missing}"

    for model in MODELS.glob("*.sql"):
        assert "read_parquet" not in read(model), f"{model.name} reads parquet directly"


# --------------------------------------------------------------------------- #
# KPI ids are the contract (docs/kpi_definitions.md rules 4 and 5)
# --------------------------------------------------------------------------- #


def defined_kpi_ids() -> set[str]:
    doc = read(REPO / "docs" / "kpi_definitions.md")
    return set(re.findall(r"^### (KPI-\d+)", doc, flags=re.MULTILINE))


def strip_sql_comments(sql: str) -> str:
    """Comments are prose, and prose is not what a board renders.

    Learned the hard way in this very file: the first version of
    `mart_kpi_ids` scanned raw text, and monthly_kpis.sql's own comment
    explaining why *there is no* `kpi_09_*` column made the test fail. The
    assertion was firing for the wrong reason — the same shape of bug M1-S3's
    KPI-10 test had. Read the SELECT list, not the argument for it.
    """
    return "\n".join(line.split("--")[0] for line in sql.splitlines())


def mart_kpi_ids() -> set[str]:
    ids = set()
    for model in MODELS.glob("*.sql"):
        for n in re.findall(r"\bkpi_(\d+)[a-z]?_", strip_sql_comments(read(model))):
            ids.add(f"KPI-{n}")
    return ids


def test_every_kpi_column_cites_a_defined_id():
    """A `kpi_NN_` column that no document defines is a number without a definition.

    Prevents: a board card citing an id that means whatever the SQL happened to
    do that week (DA charter refusal #1).
    """
    undefined = mart_kpi_ids() - defined_kpi_ids()
    assert not undefined, f"marts publish undefined KPI ids: {sorted(undefined)}"


def test_model_quality_kpis_are_not_computed_in_sql():
    """KPI-09/KPI-10 have exactly one legal source: taxi_mlops.training.evaluate.

    Prevents gotcha #15 in its most convincing disguise — a column named
    `kpi_09_mae` computed by a GROUP BY, which a board would then render as if it
    were the model's real error.
    """
    assert not ({"KPI-09", "KPI-10"} & mart_kpi_ids())


def test_kpi_08_never_publishes_a_value_without_its_excluded_count():
    """KPI-08's rule: the count of excluded rows renders on the same card.

    Prevents the failure the KPI doc names outright — "a windowed number with its
    exclusion hidden is worse than an un-windowed one, because it looks careful".
    3,131 rows of 56,127,878 move the fare/duration correlation 11.8x.
    """
    for model in MODELS.glob("*.sql"):
        sql = read(model)
        if "kpi_08_" in sql and "windowed" in sql:
            assert "kpi_08_excluded_rows" in sql, f"{model.name} windows a money column silently"


# --------------------------------------------------------------------------- #
# The red team is a command, not a souvenir
# --------------------------------------------------------------------------- #


def test_red_team_fixture_is_off_by_default_and_never_published():
    """`make marts` must never union the out-of-contract fixture.

    Prevents: the red-team hook becoming a way for two impossible trips to reach
    a board. The flag defaults to false in SQL, and the only caller that sets it
    exits before the publish.
    """
    sql = read(MODELS / "trips_clean.sql")
    assert "var('red_team', false)" in sql

    script = read(REPO / "scripts" / "marts.sh")
    assert "RED_TEAM=1 bash scripts/marts.sh" in read(REPO / "Makefile")
    # The red-team branch returns before the publish section starts.
    red_branch = script.index('if [[ "$RED_TEAM" == "1" ]]; then\n  # The failure')
    publish = script.index("# ---- 3. publish to the one Postgres")
    assert script.index("exit 0", red_branch) < publish


def test_red_team_fixture_violates_the_range_it_targets():
    """The fixture must actually be out of contract, or the red team proves nothing.

    Prevents: a fixture edited into validity, leaving `make marts-redteam` green
    and its guard ("a GREEN build here means the tests are not testing") never
    firing.
    """
    csv = read(DBT / "seeds" / "redteam" / "redteam_bad_trips.csv").strip().splitlines()
    header = csv[0].split(",")
    idx = header.index("trip_duration_minutes")
    values = [float(line.split(",")[idx]) for line in csv[1:]]
    assert values, "the red-team fixture has no rows"
    assert all(v < 1 or v > 120 for v in values), f"fixture rows are inside [1, 120]: {values}"


# --------------------------------------------------------------------------- #
# D-002 — the post-initdb database path
# --------------------------------------------------------------------------- #


def test_database_recipe_is_guarded_and_never_destructive():
    """Idempotence by construction, and a recipe that cannot delete a database.

    Prevents both halves of D-002's failure mode: an unguarded CREATE that fails
    the second run, and a "converge" that drops and recreates — which would take
    the data with it every deploy.
    """
    script = read(REPO / "scripts" / "postgres_databases.sh")
    assert "WHERE NOT EXISTS (SELECT 1 FROM pg_roles" in script
    assert "WHERE NOT EXISTS (SELECT 1 FROM pg_database" in script
    assert "DROP DATABASE" not in script
    assert "DROP ROLE" not in script


def test_mlflow_is_in_the_database_recipe_too():
    """The recipe describes the whole server; initdb is only the empty-volume path.

    Prevents two sources of truth for which databases exist — the failure that
    made D-002 necessary in the first place.
    """
    script = read(REPO / "scripts" / "postgres_databases.sh")
    assert '"mlflow:${MLFLOW_DB_USER:-mlflow}:MLFLOW_DB_PASSWORD"' in script
    assert '"marts:${MARTS_DB_USER:-marts}:MARTS_DB_PASSWORD"' in script


def test_deploy_recipe_creates_databases_after_postgres_and_before_mlflow():
    """Order is not incidental: MLflow's init containers block on its role existing."""
    deploy = read(REPO / "scripts" / "deploy_platform.sh")
    assert deploy.index("statefulset/postgres") < deploy.index("postgres_databases.sh")
    assert deploy.index("postgres_databases.sh") < deploy.index("upgrade --install mlflow")


def test_no_password_ever_reaches_a_command_line():
    """Secrets travel on stdin, never in argv — `ps` and audit logs read argv.

    Prevents a credential appearing in a kubectl audit log and in the process
    table of a pod anyone can exec into.
    """
    for name in ("postgres_databases.sh", "marts.sh"):
        script = read(REPO / "scripts" / name)
        for line in script.splitlines():
            if line.lstrip().startswith("#"):
                continue
            assert "PASSWORD" not in line or "$" not in line.split("PASSWORD")[0][-2:] or (
                "-c " not in line
            ), f"{name}: a password may be reaching argv: {line.strip()}"
        assert "PGPASSWORD=" not in script


def test_env_example_documents_the_marts_credentials():
    """.env.example is the shape of .env; a key only the code knows is a trap."""
    example = read(REPO / ".env.example")
    assert "MARTS_DB_USER=marts" in example
    assert "MARTS_DB_PASSWORD=" in example

    secrets = read(REPO / "scripts" / "platform_secrets.sh")
    assert "MARTS_DB_USER" in secrets and "MARTS_DB_PASSWORD" in secrets
    # Additive, not regenerated: the value is not inside any volume yet.
    assert "ADDITIVE=(" in secrets


# --------------------------------------------------------------------------- #
# F-003 regression pin
# --------------------------------------------------------------------------- #


def test_postgres_manifest_states_the_server_side_defaults():
    """F-003's fix, pinned. `volumeClaimTemplates` is an ATOMIC list.

    Omit the apiserver's defaults and kubectl re-sends the whole list on every
    apply, reporting `configured` for a recipe that changes nothing — which reads
    like a recipe that mutates the cluster each run. Prevents a tidy-up deleting
    these four "redundant" lines and reopening the finding.
    """
    docs = list(yaml.safe_load_all(read(REPO / "infra" / "manifests" / "postgres.yaml")))
    (sts,) = [d for d in docs if d and d["kind"] == "StatefulSet"]
    (vct,) = sts["spec"]["volumeClaimTemplates"]
    assert vct["apiVersion"] == "v1"
    assert vct["kind"] == "PersistentVolumeClaim"
    assert vct["spec"]["volumeMode"] == "Filesystem"
    assert vct["status"] == {"phase": "Pending"}
    # storageClassName stays unset on purpose — kind's default is local-path and
    # naming it would cost portability for nothing.
    assert "storageClassName" not in vct["spec"]


# --------------------------------------------------------------------------- #
# The publish's one piece of real logic
# --------------------------------------------------------------------------- #


def test_type_map_refuses_to_guess():
    """An unmapped DuckDB type must stop the publish, not become `text`.

    Prevents a numeric column published as text: every chart over it silently
    stops summing, and nothing anywhere is red.
    """
    sys.path.insert(0, str(REPO / "scripts"))
    import marts_export

    assert marts_export.postgres_type("BIGINT") == "bigint"
    assert marts_export.postgres_type("DOUBLE") == "double precision"
    assert marts_export.postgres_type("TIMESTAMP") == "timestamp"
    assert marts_export.postgres_type("DECIMAL(18,3)") == "decimal(18,3)"
    with pytest.raises(SystemExit) as excinfo:
        marts_export.postgres_type("STRUCT(a INTEGER)")
    assert "unmapped DuckDB type" in str(excinfo.value)


def test_marts_target_is_real_and_has_a_red_team_twin():
    """Every capability has a verify twin (the Makefile's own rule)."""
    makefile = read(REPO / "Makefile")
    assert "marts: ##" in makefile and "TODO(M1-S6)" not in makefile
    assert "marts-redteam: ##" in makefile
    assert "bash scripts/marts.sh" in makefile


def test_publish_reads_marts_from_one_list():
    """The published set is one list, so a new model cannot be half-added."""
    script = read(REPO / "scripts" / "marts.sh")
    (line,) = [ln for ln in script.splitlines() if ln.startswith("MARTS=(")]
    published = set(line[len("MARTS=(") : line.index(")")].split())
    on_disk = {p.stem for p in MODELS.glob("*.sql")}
    assert published == on_disk, f"models and published set disagree: {published ^ on_disk}"


def test_dbt_artifacts_are_gitignored():
    """marts.duckdb is a cache with a build command, not a second thing to version."""
    ignored = read(REPO / ".gitignore")
    for pattern in ("analytics/dbt/marts.duckdb", "analytics/dbt/target/", "analytics/dbt/logs/"):
        assert pattern in ignored


def test_dbt_pins_live_in_the_project_metadata():
    """Unpinned versions are an MLOps charter refusal."""
    pyproject = read(REPO / "pyproject.toml")
    assert "dbt-duckdb>=" in pyproject
    lock = json.loads("{}") if False else read(REPO / "uv.lock")
    assert 'name = "dbt-duckdb"' in lock and 'name = "dbt-core"' in lock
