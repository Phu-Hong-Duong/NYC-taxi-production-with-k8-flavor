"""M1-S5: the BI seat's cluster-free invariants.

What is testable here is everything that has to be TRUE BEFORE a cluster exists:
the manifest's promises (no H2, no telemetry, a pinned image), the boards'
definitions (every card cites a KPI id; KPI-09/KPI-10 cite none), the recipe's
wiring (a new database is one line plus one secret), and the gate's shape (it
red-teams two legs rather than only asserting happy paths).

The live half — Metabase answering on 3030, both dashboards holding their cards,
one card executing — is proved by running ``make verify-m1`` against a real
cluster, and is quoted in the M1-S5 handoff entry, not here.

Each test's docstring names the failure it prevents.
"""

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "infra" / "manifests" / "metabase.yaml"
NAMESPACES = REPO / "infra" / "manifests" / "namespaces.yaml"
DEPLOY = REPO / "scripts" / "deploy_metabase.sh"
BOARDS_SCRIPT = REPO / "scripts" / "metabase_boards.py"
VERIFY_M1 = REPO / "scripts" / "verify_m1.sh"
SECRETS = REPO / "scripts" / "platform_secrets.sh"
DATABASES = REPO / "scripts" / "postgres_databases.sh"
BOARDS_DIR = REPO / "analytics" / "metabase" / "boards"
KPI_DOC = REPO / "docs" / "kpi_definitions.md"
MAKEFILE = REPO / "Makefile"

BOARD_FILES = sorted(BOARDS_DIR.glob("*.json"))


def boards():
    return [json.loads(p.read_text()) for p in BOARD_FILES]


def without_comments(path: Path) -> str:
    """The file with its ``#`` comment lines removed.

    Every "this string must NOT appear" assertion below reads through this. The
    repo has now paid this tuition three times — M1-S3's KPI-10 regex, M1-S4's
    ``monthly_kpis.sql``, and two tests in this very file — and the shape is
    always identical: a comment explaining *why we do not do X* contains the
    word X, so the assertion fires for the wrong reason and the author "fixes"
    working code. A test that reads prose is testing prose.
    """
    return "\n".join(
        line for line in path.read_text().splitlines() if not line.lstrip().startswith("#")
    )


# ------------------------------------------------------------- the manifest --


def test_the_app_db_is_postgres_and_never_h2():
    """An H2 file-db works perfectly until the first rollout, then takes every
    dashboard, card, connection and user with it — silently, because losing a
    container filesystem is the normal behaviour of a Deployment, not an error."""
    text = without_comments(MANIFEST)
    assert re.search(r"name:\s*MB_DB_TYPE\S*.*value:\s*postgres", text, re.S | re.M)
    assert "h2" not in text.lower()


def test_the_app_db_points_at_the_one_postgres():
    """A second database server would make 'the one Postgres' a slogan."""
    assert "postgres.platform.svc.cluster.local" in MANIFEST.read_text()


def test_no_credential_is_written_into_the_manifest():
    """Secrets reach the pod by secretKeyRef, never as a literal env value —
    otherwise the app-db password is in git the moment the manifest is."""
    text = MANIFEST.read_text()
    assert "MB_DB_PASS" in text
    assert re.search(r"name:\s*MB_DB_PASS\s*\n\s*valueFrom:\s*\{secretKeyRef:", text)
    assert not re.search(r"name:\s*MB_DB_PASS\s*,?\s*value:", text)


def test_the_image_is_pinned_by_tag_AND_digest():
    """A tag can be re-pointed at new bytes; a digest cannot. The tag is for the
    human reading the diff, the digest is what actually runs."""
    image = re.search(r"image:\s*(metabase/metabase:\S+)", MANIFEST.read_text()).group(1)
    assert "@sha256:" in image, image
    assert re.match(r"metabase/metabase:v\d+\.\d+\.\d+@sha256:[0-9a-f]{64}$", image), image


@pytest.mark.parametrize(
    "var", ["MB_ANON_TRACKING_ENABLED", "MB_CHECK_FOR_UPDATES"]
)
def test_metabase_telemetry_is_off_in_the_manifest(var):
    """gotcha #32's Metabase sibling. Both of these are opt-OUT by default, and
    this program's charter is one sentence long: nothing leaves this machine.
    Turning them off in the manifest keeps the decision greppable; a UI checkbox
    would not survive a `make destroy`."""
    assert re.search(rf"\{{name:\s*{var},\s*value:\s*\"false\"\}}", MANIFEST.read_text())


def test_the_boards_setup_call_also_refuses_tracking():
    """The manifest's env var is only half of it: /api/setup writes its own
    `allow_tracking` preference, so an instance set up without this line turns
    tracking back on at the moment of first login."""
    assert '"allow_tracking": False' in BOARDS_SCRIPT.read_text()


def test_the_metabase_namespace_exists_in_the_namespace_manifest():
    """The Deployment names namespace `metabase`; if namespaces.yaml does not
    create it, `kubectl apply` fails on a fresh cluster and only there."""
    assert re.search(r"metadata:\s*\{name:\s*metabase\}", NAMESPACES.read_text())


# ------------------------------------------------------- the D-002 wiring ----


def test_metabase_is_one_line_in_the_database_recipe():
    """M1-S4 claimed 'a new consumer adds a line here and nothing else'. This is
    the test that makes the claim falsifiable rather than a comment."""
    text = DATABASES.read_text()
    assert text.count('"metabase:${METABASE_DB_USER:-metabase}:METABASE_DB_PASSWORD"') == 2


def test_metabase_credentials_are_additive_not_required_on_a_fresh_env():
    """A NEW consumer's credential is not yet inside any volume, so generating it
    is creation, not rotation. Putting it only in REQUIRED would hard-fail every
    existing .env and leave the operator hand-editing a secrets file."""
    text = SECRETS.read_text()
    additive = re.search(r"ADDITIVE=\((.*?)\)", text, re.S).group(1)
    for key in ("METABASE_DB_USER", "METABASE_DB_PASSWORD", "METABASE_ADMIN_PASSWORD"):
        assert key in additive, key
        assert key in re.search(r"REQUIRED=\((.*?)\)", text, re.S).group(1), key


def test_the_admin_password_generator_satisfies_a_login_complexity_rule():
    """32 random hex chars can legitimately contain no digit and no uppercase —
    and Metabase rejects such a password at /api/setup, which would park the
    chain on a credential it generated itself."""
    text = SECRETS.read_text()
    assert "gen_login_password" in text
    assert re.search(r"printf\s+'%sAa1\\n'", text)
    assert '"$key" == *_ADMIN_PASSWORD' in text


def test_metabase_reads_the_warehouse_as_marts_never_as_the_superuser():
    """A BI seat holding superuser credentials is one misclick from a restore."""
    text = SECRETS.read_text()
    assert 'apply_secret metabase metabase-marts-db' in text
    assert '"username=$MARTS_DB_USER"' in text
    assert "POSTGRES_PASSWORD" not in text.split("apply_secret metabase")[1]


# ------------------------------------------------------------- the boards ----


def test_the_boards_are_exactly_the_ones_the_gates_name():
    """The M1 gate says 'the two Metabase boards'; M2's kickoff adds the
    error-segment board by name. An unnamed fourth board is a different
    deliverable; a missing one is a missing gate leg.

    Widened at M2-S4 rather than deleted: the assertion's value is that the set is
    CLOSED, not that it has two members."""
    assert {b["name"] for b in boards()} == {"Data health", "KPI board", "Error segments (M2)"}


def test_every_card_cites_a_kpi_id_that_the_kpi_doc_actually_defines():
    """A card citing KPI-11 renders perfectly and means nothing. The ids are the
    contract between this board, M2's error memo and M7's drift memos."""
    defined = set(re.findall(r"^### (KPI-\d+)", KPI_DOC.read_text(), re.M))
    assert len(defined) >= 10
    for board in boards():
        for card in board["cards"]:
            assert card["kpi"] in defined, f"{board['name']}/{card['name']} cites {card['kpi']}"


def test_no_card_renders_kpi_09_or_kpi_10():
    """gotcha #15. They are DEFINED in the KPI doc and are columns in no mart, on
    purpose: they are measured only by taxi_mlops.training.evaluate on held-out
    data. A BI card computing them from a warehouse table would be a scout
    leaderboard wearing a reported number's name."""
    for board in boards():
        for card in board["cards"]:
            assert card["kpi"] not in {"KPI-09", "KPI-10"}
            assert "KPI-09" not in card["name"] and "KPI-10" not in card["name"]
            assert "KPI-09" not in card["sql"] and "KPI-10" not in card["sql"]


def test_kpi_08s_value_and_its_excluded_row_count_are_on_the_SAME_card():
    """AI-2, discharged at M1-S3 and enforced here: a money KPI's window and its
    excluded-row count render beside the value. 3,131 excluded rows (0.0056%)
    move CORR(fare, duration) by 11.8x while moving the mean 0.36% — the number
    without its exclusion count is a claim, not a measurement."""
    kpi08 = [c for b in boards() for c in b["cards"] if c["kpi"] == "KPI-08"]
    assert kpi08, "no KPI-08 card at all"
    for card in kpi08:
        assert "kpi_08_mean_fare_windowed" in card["sql"]
        assert "kpi_08_excluded_rows" in card["sql"], card["name"]


def test_kpi_03_renders_every_rule_including_the_permanently_zero_ones():
    """A rule you cannot see cannot be seen to START firing. The data-health
    board must not filter to rules with a nonzero count."""
    kpi03 = [c for b in boards() for c in b["cards"] if c["kpi"] == "KPI-03"]
    assert kpi03
    for card in kpi03:
        assert "rejections_by_rule" in card["sql"]
        assert "rejected_by > 0" not in card["sql"].replace(" ", " ")
        assert "HAVING" not in card["sql"].upper()


def test_kpi_02_is_plotted_as_a_series_not_only_as_one_number():
    """The observed 2019 rejection rate rises monotonically 1.428% -> 2.020%. An
    average hides exactly the thing the board exists to show, and the ingest
    guard (10% refusal) sees none of it."""
    kpi02 = [c for b in boards() for c in b["cards"] if c["kpi"] == "KPI-02"]
    assert any(c["display"] in {"line", "bar"} and "ORDER BY month" in c["sql"] for c in kpi02)


def test_every_card_queries_a_mart_and_never_a_raw_table_or_a_parquet_path():
    """The boards are the served warehouse layer. A card reading parquet, or the
    analyst DuckDB, would give the repo a second definition of `split`/`month`
    and would not be reachable by Metabase anyway."""
    marts = {"marts.trips_clean", "marts.zone_hourly_stats", "marts.monthly_kpis",
             "marts.rejections_by_rule", "marts.error_segments"}
    for board in boards():
        for card in board["cards"]:
            sql = card["sql"]
            assert any(m in sql for m in marts), f"{card['name']} queries no mart"
            assert "read_parquet" not in sql and ".parquet" not in sql
            assert "analyst" not in sql


def test_board_cards_declare_a_grid_position_that_fits_metabases_24_columns():
    """A card at col 20 with size_x 12 does not error — Metabase silently
    reflows it, and the board a reviewer approved is not the board that renders."""
    for board in boards():
        for card in board["cards"]:
            assert 0 <= card["col"] < 24
            assert card["col"] + card["size_x"] <= 24, card["name"]
            assert card["size_y"] >= 1 and card["row"] >= 0


def test_card_names_are_unique_across_both_boards():
    """The provisioning script is idempotent BY NAME: two cards sharing a name
    would make each run overwrite the other, and the second board would render
    the first board's SQL."""
    names = [c["name"] for b in boards() for c in b["cards"]]
    assert len(names) == len(set(names))


# --------------------------------------------------------------- the gate ----


def test_verify_m1_red_teams_rather_than_only_asserting_happy_paths():
    """A gate that only checks that good things are green cannot notice the day
    the refusals stop refusing. Two legs are deliberately negative."""
    text = VERIFY_M1.read_text()
    assert "RED-TEAM: a corrupt source file is REFUSED" in text
    assert "RED-TEAM: seeded bad fixture makes a NAMED dbt test go red" in text
    assert "CorruptSourceError" in text


def test_verify_m1_has_no_skip_flag_for_the_expensive_rebuild_leg():
    """The byte-identity claim is worthless when checked against data that was
    never re-derived. A gate with a fast mode is a gate that runs in fast mode."""
    text = VERIFY_M1.read_text()
    assert "rebuild_proof.sh" in text
    assert "SKIP_REBUILD" not in text and "FAST=" not in text


def test_verify_m1_quotes_the_count_the_rebuild_proof_actually_hashed():
    """M2-S1: the leg used to `grep -c` every line ending in 'yes' across the
    WHOLE log, so it also counted the duckdb reconciliation's per-month rows and
    printed '16 output(s)' for 8 files. The assertion was never false — 'all
    byte-identical: True' carried it — but the number it showed a human came
    from somewhere else, which is the same defect this leg's own comment warns
    about. It now parses the proof's own summary line."""
    text = VERIFY_M1.read_text()
    assert "all byte-identical: True$/\\1/p" in text
    assert "grep -cE '  yes$'" not in text
    # and the emptiness of that parse must be a FAIL, not an unbound comparison
    assert '[[ -n "$identical" && "$identical" -gt 0 ]]' in text


def test_verify_m1_seeds_its_corrupt_fixture_in_a_sandbox_not_in_data_raw():
    """gotcha #33's neighbour: a proof must not damage the artifact it protects.
    The fixture goes into a throwaway raw_dir under a throwaway config."""
    text = VERIFY_M1.read_text()
    assert ".verify_m1_sandbox" in text
    assert 'cfg["source"]["raw_dir"] = ".verify_m1_sandbox/raw"' in text
    assert "trap cleanup EXIT" in text


def test_verify_m1_checks_the_boards_through_the_api_not_through_the_json_files():
    """'The JSON exists in git' is a claim about the repo. The gate asks the
    RUNNING instance what it holds, and runs one card."""
    text = VERIFY_M1.read_text()
    assert "metabase_boards.py --verify" in text
    assert "/api/health" in text


def test_the_make_targets_are_real_and_no_longer_echo_todo():
    """The Makefile is THE interface; a target that echoes TODO after its
    milestone landed is a lie with a tab character in front of it."""
    text = MAKEFILE.read_text()
    for target in ("deploy-metabase:", "verify-m1:"):
        body = text.split(f"\n{target}", 1)[1].split("\n.PHONY")[0]
        recipe = body.split("\n")[1]
        assert "TODO" not in recipe, f"{target} still echoes TODO"
    assert "bash scripts/deploy_metabase.sh" in text
    assert "bash scripts/verify_m1.sh" in text


def test_the_deploy_recipe_never_asks_for_a_port_forward():
    """MLOps charter: a port-forward is a manual deploy step by another name. The
    route is declared in the kind config and the Service, or it does not exist."""
    # Comment- AND message-stripped: verify_m1.sh legitimately prints the phrase
    # ("declared route, not a port-forward") in a passing line. What must not
    # exist is the COMMAND.
    assert "kubectl port-forward" not in DEPLOY.read_text()
    assert "port-forward" not in without_comments(DEPLOY)
    assert "port-forward" not in without_comments(MANIFEST)
    assert "kubectl port-forward" not in VERIFY_M1.read_text()
