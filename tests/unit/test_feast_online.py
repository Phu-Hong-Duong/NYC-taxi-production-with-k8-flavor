"""The online store's laws, and the parity table's — M8-S4 leg 1.

The properties this leg's evidence rests on, made falsifiable here instead of
argued in prose:

1. **The wall still holds across the NEW seam.** `infra/feast/online.py` imports
   `feast` and never `taxi_mlops`; `scripts/feast_online_parity.py` is the mirror
   image. Asked of the AST, never of a word search — both files argue their own
   design at length and a grep would match the argument (gotchas #53/#68/#99).
2. **The declared pair set is the M8-S3 set plus twelve, and the first 88 rows
   are identical field by field.** That is what makes a disagreement between the
   offline table and the online one a fact about the STORES rather than about two
   populations.
3. **The bar the script applied is the bar the doc argues** (F-017), and the
   record carries the same number.
4. **The store's two settings whose failure mode is silent** — `noeviction` and
   the absent hostPort — are properties of the committed manifest, not of a
   session's memory.
5. **The red team cannot overwrite the committed accept artifact**: both of its
   parity runs pass `--no-write`.
"""

from __future__ import annotations

import ast
import csv
import json
import sys
from pathlib import Path

import pytest
import yaml
from conftest import REPO, imported_roots

sys.path.insert(0, str(REPO / "scripts"))

ONLINE_READER = REPO / "infra" / "feast" / "online.py"
ONLINE_REDTEAM = REPO / "infra" / "feast" / "online_redteam.py"
RETRIEVE = REPO / "infra" / "feast" / "retrieve.py"
PARITY = REPO / "scripts" / "feast_online_parity.py"
PAIRS_BUILDER = REPO / "scripts" / "feast_online_pairs.py"
REDTEAM_SH = REPO / "scripts" / "feast_online_parity_redteam.sh"
DEPLOY_SH = REPO / "scripts" / "deploy_feast_store.sh"
MATERIALIZE_SH = REPO / "scripts" / "feast_materialize.sh"
MANIFEST = REPO / "infra" / "manifests" / "redis.yaml"
STORE_YAML = REPO / "infra" / "feast" / "feature_repo" / "feature_store.yaml"
PINS = REPO / "infra" / "feast" / "requirements-feast.txt"
QUARANTINE_SH = REPO / "scripts" / "feast_quarantine.sh"

PAIRS_CSV = REPO / "infra" / "feast" / "online_pairs.csv"
ROWS_CSV = REPO / "infra" / "feast" / "retrieval_rows.csv"
DOC = REPO / "docs" / "feast_online_m8.md"
ADR = REPO / "docs" / "decisions" / "ADR-012-feast-online-store.md"
TABLE = REPO / "docs" / "feast_online_parity_table.md"

PARITY_RECORD = REPO / "automation" / "runs" / "m8-online" / "online_parity.json"
STORE_RECORD = REPO / "automation" / "runs" / "m8-online" / "store.json"
MATERIALIZE_RECORD = REPO / "automation" / "runs" / "m8-online" / "materialize.json"

INHERITED_ROWS = 88
DECLARED_PAIRS = 100


def _called_names(path: Path) -> set[str]:
    """Every attribute/function NAME that is actually CALLED, from the AST.

    Names, never words: these files quote the verbs they refuse in their own
    docstrings, and three of this repo's tests have already gone red for matching
    a file quoting itself (gotcha #99).
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Attribute):
                names.add(target.attr)
            elif isinstance(target, ast.Name):
                names.add(target.id)
    return names


def _manifest_docs() -> list[dict]:
    return [doc for doc in yaml.safe_load_all(MANIFEST.read_text()) if doc]


def _pairs() -> list[dict[str, str]]:
    with PAIRS_CSV.open() as handle:
        return list(csv.DictReader(handle))


# ------------------------------------------------------------- the wall ---
def test_the_online_reader_is_on_the_far_side_of_the_wall() -> None:
    roots = imported_roots(ONLINE_READER)
    assert "feast" in roots, "the reader must be the one that imports feast"
    assert "taxi_mlops" not in roots, (
        "one import across the quarantine line is how a quarantine stops being one — "
        "this module runs under pandas 2.3.3 and taxi_mlops needs 3.0.5 (M8 law 4)"
    )


def test_the_online_redteam_is_on_the_far_side_too() -> None:
    roots = imported_roots(ONLINE_REDTEAM)
    assert {"feast", "redis"} <= roots
    assert "taxi_mlops" not in roots


def test_the_comparer_is_on_our_side_of_the_wall() -> None:
    roots = imported_roots(PARITY)
    assert "taxi_mlops" in roots
    assert "feast" not in roots, (
        "the comparison happens where taxi_mlops.features lives; parquet is the only "
        "thing that crosses"
    )


def test_the_comparer_is_a_reader() -> None:
    """It may not deploy, materialize, promote, or move a pointer."""
    called = _called_names(PARITY)
    forbidden = {
        "materialize",
        "materialize_incremental",
        "apply",
        "set_registered_model_alias",
        "delete_registered_model_alias",
        "transition_model_version_stage",
        "create_model_version",
        "log_model",
    }
    assert not (called & forbidden), f"a reader called {sorted(called & forbidden)}"


def test_the_comparer_crosses_the_wall_exactly_twice_and_both_are_named() -> None:
    """One `kubectl port-forward`, one quarantine invocation. Nothing else runs."""
    tree = ast.parse(PARITY.read_text(encoding="utf-8"))
    launches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"run", "Popen", "check_output", "check_call"}
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
    ]
    assert len(launches) == 2, f"expected exactly 2 subprocess launches, found {len(launches)}"


# -------------------------------------------------------- the pair set ---
def test_there_are_exactly_one_hundred_declared_pairs() -> None:
    pairs = _pairs()
    assert len(pairs) == DECLARED_PAIRS
    ids = [int(row["row_id"]) for row in pairs]
    assert ids == list(range(DECLARED_PAIRS)), "row ids must be dense and ordered"


def test_the_first_eighty_eight_pairs_are_the_m8_s3_row_set_field_by_field() -> None:
    """ONE population across both M8 seams, so a disagreement is about the stores."""
    with ROWS_CSV.open() as handle:
        inherited = list(csv.DictReader(handle))
    assert len(inherited) == INHERITED_ROWS
    for expected, actual in zip(inherited, _pairs()[:INHERITED_ROWS], strict=True):
        assert expected == actual, f"row {expected['row_id']} drifted from the M8-S3 set"


def test_every_declared_pair_names_its_hazard() -> None:
    for row in _pairs():
        assert row["why"].strip(), f"row {row['row_id']} has no reason to exist"


def test_the_twelve_added_rows_are_online_specific() -> None:
    added = _pairs()[INHERITED_ROWS:]
    assert len(added) == 12
    assert {row["stratum"] for row in added} == {"online-hazard"}


def test_the_duplicate_entity_key_rows_really_are_twins() -> None:
    """Rows 90 and 91 provoke F-056 cause 1 on purpose; if they drift apart the
    offline join stops collapsing them and the classifier is never exercised."""
    a, b = _pairs()[90], _pairs()[91]
    for field in ("pickup_datetime", "PULocationID", "DOLocationID"):
        assert a[field] == b[field], f"the twins disagree on {field}"


def test_the_added_rows_carry_the_unknown_zones_and_an_impossible_one() -> None:
    added = _pairs()[INHERITED_ROWS:]
    zone_ids = {int(row["PULocationID"]) for row in added} | {
        int(row["DOLocationID"]) for row in added
    }
    assert {264, 265} <= zone_ids, "TLC's two non-places must be declared"
    assert 999 in zone_ids, "a key that cannot exist must be declared — it must return null"


# ------------------------------------------------------------- the bar ---
def test_the_bar_the_script_applies_is_exact() -> None:
    from feast_online_parity import TOLERANCE

    assert TOLERANCE == 0.0


def test_the_doc_argues_the_bar_for_this_path_rather_than_inheriting_it() -> None:
    text = DOC.read_text()
    assert "protobuf" in text and "double" in text, (
        "M8-S3's argument was about parquet; an online store adds a serialization "
        "format and a hop, and the bar must be re-argued for them"
    )
    assert "entity_key_serialization_version" in text


@pytest.mark.needs_records
def test_the_record_carries_the_bar_the_script_applied() -> None:
    from feast_online_parity import TOLERANCE

    record = json.loads(PARITY_RECORD.read_text())
    assert record["tolerance"] == TOLERANCE


@pytest.mark.needs_records
def test_the_recorded_table_passed_over_every_declared_pair() -> None:
    record = json.loads(PARITY_RECORD.read_text())
    assert record["verdict"] == "PASSED"
    assert record["declared_pairs"] == DECLARED_PAIRS
    assert record["max_abs_delta"] == 0.0
    for verdict in record["seam"]:
        assert verdict["compared"] == DECLARED_PAIRS
        assert verdict["mismatches"] == 0
        assert verdict["one_missing"] == 0, (
            "one-missing is the load-bearing count: it says the store and the feature "
            "path agree about which rows have no value at all"
        )


@pytest.mark.needs_records
def test_the_offline_shortfall_is_fully_classified() -> None:
    record = json.loads(PARITY_RECORD.read_text())
    for name, info in record["offline_shortfall"].items():
        assert info["unexplained"] == [], f"{name} lost rows nothing accounts for"


@pytest.mark.needs_records
def test_the_no_geometry_rows_are_asserted_two_sidedly() -> None:
    record = json.loads(PARITY_RECORD.read_text())
    assert record["no_geometry"]["ok"] is True
    for side in ("pu", "do"):
        info = record["no_geometry"][side]
        assert info["disagreements"] == 0
        assert info["rows_without_geometry_our_path"] == info["rows_the_store_declined"]


# ----------------------------------------------------------- the store ---
def test_the_image_is_pinned_by_tag_and_digest() -> None:
    deployment = next(doc for doc in _manifest_docs() if doc["kind"] == "Deployment")
    image = deployment["spec"]["template"]["spec"]["containers"][0]["image"]
    assert "@sha256:" in image and ":" in image.split("@")[0], (
        "the Metabase precedent: a bare tag is not a pin"
    )


def test_the_store_gets_no_host_port() -> None:
    """kind publishes host ports at cluster-CREATE only; adding one means a rebuild."""
    for doc in _manifest_docs():
        assert "hostPort" not in yaml.dump(doc)


def test_the_eviction_policy_is_noeviction() -> None:
    """An evicting feature store answers null, and a null reads as 'no value'."""
    deployment = next(doc for doc in _manifest_docs() if doc["kind"] == "Deployment")
    args = deployment["spec"]["template"]["spec"]["containers"][0]["args"]
    assert "--maxmemory-policy" in args
    assert args[args.index("--maxmemory-policy") + 1] == "noeviction"


def test_the_rollout_strategy_is_recreate() -> None:
    """RWO + node-local volume + RollingUpdate is F-033's deadlock."""
    deployment = next(doc for doc in _manifest_docs() if doc["kind"] == "Deployment")
    assert deployment["spec"]["strategy"]["type"] == "Recreate"


def test_the_store_has_a_volume_and_a_snapshot_flag() -> None:
    """A mounted volume with no persistence flag is decoration (M8-S1's lesson)."""
    docs = _manifest_docs()
    assert any(doc["kind"] == "PersistentVolumeClaim" for doc in docs)
    deployment = next(doc for doc in docs if doc["kind"] == "Deployment")
    args = deployment["spec"]["template"]["spec"]["containers"][0]["args"]
    assert "--save" in args and "--dir" in args


def test_the_deploy_script_does_not_know_the_registry_exists() -> None:
    """M8 law 3, the deploy_serving.sh precedent — it installs a store, not a model."""
    text = DEPLOY_SH.read_text()
    for needle in ("models:/", "set_registered_model_alias", "mlflow "):
        assert needle not in text, f"the store deploy names {needle!r}"


def test_the_connection_string_is_an_env_var_with_no_default() -> None:
    text = STORE_YAML.read_text()
    config = yaml.safe_load(text)
    assert config["online_store"]["type"] == "redis"
    assert config["online_store"]["connection_string"] == "${FEAST_REDIS_CONNECTION}", (
        "a default here would be a wrong address that connects to something; an unset "
        "variable fails loudly naming itself (ADR-012)"
    )
    assert config["entity_key_serialization_version"] == 3


def test_the_quarantine_declares_the_redis_extra_and_pins_it() -> None:
    pins = PINS.read_text()
    assert "\nredis==" in pins and "\nhiredis==" in pins
    assert "feast[redis]==" in QUARANTINE_SH.read_text(), (
        "a future --resolve must produce the set the pin file already holds"
    )


def test_the_materialize_window_is_derived_not_typed() -> None:
    text = MATERIALIZE_SH.read_text()
    assert "feast_source_window.py" in text
    for typed in ("2019-07-01", "2019-01-01"):
        assert f'"{typed}' not in text, f"the window must not carry the literal {typed}"


# --------------------------------------------------------- the red team ---
def test_the_red_team_cannot_overwrite_the_committed_accept_artifact() -> None:
    text = REDTEAM_SH.read_text()
    runs = [line for line in text.splitlines() if "feast_online_parity.py" in line]
    assert runs, "the drill must actually run the parity"
    for line in runs:
        assert "--no-write" in line, (
            "a drill that rewrote the committed table with its own tampered verdict "
            "would be planting evidence rather than testing for it"
        )


def test_the_red_team_restores_and_checks_that_it_restored() -> None:
    text = REDTEAM_SH.read_text()
    assert "--mode restore" in text
    assert "sha256" in text or "digest" in text


def test_the_red_team_uses_its_own_local_port() -> None:
    """Two forwards are alive at once; a shared port fails for its own reasons (#55)."""
    from feast_online_parity import main as _  # noqa: F401  (import-safety)

    assert "6381" in REDTEAM_SH.read_text()
    assert "6380" in PARITY.read_text()


# ------------------------------------------------------------ the story ---
def test_the_adr_records_the_state_class_in_both_directions() -> None:
    text = ADR.read_text()
    assert "Ledger row: YES" in text
    assert "Backup obligation: NO" in text
    assert "REGENERABLE" in text


@pytest.mark.needs_records
def test_the_store_record_says_the_store_answered_a_write() -> None:
    """A readiness probe proves a read; a materialization needs a write."""
    record = json.loads(STORE_RECORD.read_text())
    assert record["accept"]["ping"] == "PONG"
    assert record["accept"]["write_round_trip"] == "ok"
    assert record["maxmemory_policy"] == "noeviction"


@pytest.mark.needs_records
def test_the_materialize_record_proves_the_store_is_not_empty() -> None:
    record = json.loads(MATERIALIZE_RECORD.read_text())
    assert record["store"]["dbsize"] > 0
    assert record["store"]["dbsize"] * 8 < record["store"]["maxmemory_bytes"], (
        "the noeviction cap must have real headroom over the measured working set"
    )


@pytest.mark.needs_records
def test_the_committed_table_is_the_one_the_record_describes() -> None:
    record = json.loads(PARITY_RECORD.read_text())
    text = TABLE.read_text()
    assert f"declared pairs: **{record['declared_pairs']}**" in text
    assert f"**Verdict: {record['verdict']}**" in text
