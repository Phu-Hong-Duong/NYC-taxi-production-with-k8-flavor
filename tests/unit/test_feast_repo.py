"""The quarantine's laws, and the catalog's — M8-S2.

Three properties this milestone rests on, made falsifiable here rather than
argued in prose:

1. **The wall is a wall.** `feast` never enters the project graph, and the two
   modules on either side of it never import across. Checked by AST rather than
   by grep, because both files argue their own design at length and a word search
   would pass on the argument (gotchas #53/#68, and #99 — three needles in a
   gate's own test file once matched the gate quoting itself).
2. **The catalog carries the store's verdicts, and cannot drift from them.** The
   verdicts live as tags on the Feast objects AND on the page a human reads; if
   the two ever disagree, that is a red test rather than a discrepancy nobody
   opens two files to notice.
3. **The event-timestamp convention is END-OF-WINDOW arithmetic**, including
   across a year boundary — the property the M8-S3 point-in-time proof is about
   to rest its whole assertion on.
"""

from __future__ import annotations

import ast
import json
import re
import sys

import pytest
from conftest import REPO, imported_roots

sys.path.insert(0, str(REPO / "scripts"))

DEFINITIONS = REPO / "infra" / "feast" / "feature_repo" / "definitions.py"
PRODUCER = REPO / "scripts" / "feast_sources.py"
PLAN_CHECK = REPO / "scripts" / "feast_plan_check.py"
PINS = REPO / "infra" / "feast" / "requirements-feast.txt"
CATALOG = REPO / "docs" / "feast_catalog.md"
GITIGNORE = REPO / ".gitignore"

REGISTRY_RECORD = REPO / "automation" / "runs" / "m8-feast" / "registry.json"
PROBE_RECORD = REPO / "automation" / "runs" / "m8-feast" / "probe.json"
PLAN_RECORD = REPO / "automation" / "runs" / "m8-feast" / "plan.json"

VERDICTS = {"in-champion", "catalog-only", "candidate"}


# ------------------------------------------------------------- the wall ---
def test_the_producer_is_on_our_side_of_the_wall() -> None:
    roots = imported_roots(PRODUCER)
    assert "taxi_mlops" in roots, "the producer must build sources through the ONE feature path"
    assert "feast" not in roots, (
        "scripts/feast_sources.py runs under pandas 3.0.5 and must never import feast — "
        "one import across the wall is how a quarantine stops being one"
    )


def test_the_definitions_are_on_the_other_side() -> None:
    roots = imported_roots(DEFINITIONS)
    assert "feast" in roots
    assert "taxi_mlops" not in roots, (
        "definitions.py is imported by .venv-feast (pandas 2.3.3); importing taxi_mlops "
        "there would run this project's code under a pandas it was never measured on"
    )


def test_feast_is_not_in_the_project_graph() -> None:
    """The invariant M8 law 4 states, asked of the two files that would betray it."""
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert not re.search(r'^\s*"feast[=<>~ ]', pyproject, flags=re.MULTILINE), (
        "feast in pyproject.toml means `uv add feast` happened; it pins pandas<3 "
        "against this project's 3.0.5"
    )
    lock = (REPO / "uv.lock").read_text(encoding="utf-8")
    assert '\nname = "feast"' not in lock, "feast reached uv.lock"


def test_the_pin_file_is_exact_and_complete() -> None:
    """A pin file with a range in it is a resolution waiting to happen."""
    lines = [
        line.strip()
        for line in PINS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert lines, "the pin file is empty"
    for line in lines:
        assert re.fullmatch(r"[A-Za-z0-9_.\-]+==[^=<>~,\s]+", line), (
            f"{line!r} is not an exact pin — the quarantine installs with --no-deps, "
            "so anything inexact is a version nobody chose"
        )
    assert "feast==0.66.0" in lines


# ------------------------------------------------- F-057: the round trip ---
#
# The pin file's whole job is to be REVIEWED, and until this story its own
# documented regenerator could not reproduce it: `importlib.metadata` reports the
# name a distribution published (`PyYAML`, `typing_extensions`) where the file
# carries the normalized spelling, so M8-S4's two real additions arrived as a
# +14/-12 diff and a third line could have hidden in it. gotcha #104.


def _pin_body(text: str) -> list[str]:
    return [line for line in text.splitlines() if "==" in line and not line.startswith("#")]


def test_the_pin_file_is_normalized_and_sorted_as_its_own_lines() -> None:
    """The two properties the regenerator now emits — asked of the artifact itself.

    This half needs no quarantine venv, so it runs in CI and inside the task
    image. The venv-gated test below proves the regenerator really emits them;
    this one proves the committed file has them, which is the half that would go
    red if somebody hand-added a pin in the published spelling again.
    """
    import feast_probe_record as probe

    body = _pin_body(PINS.read_text(encoding="utf-8"))
    for line in body:
        name = line.split("==", 1)[0]
        assert name == probe._normalize(name), (
            f"{name!r} is not the PEP 503 spelling ({probe._normalize(name)!r}) — a pin "
            "added in a distribution's published name is exactly F-057"
        )
    assert body == sorted(body), (
        "the body must be its own lines sorted, which is the ordering a reviewer can "
        "check with `sort -c` and the one --rewrite-pins emits"
    )


def test_normalize_is_pep_503_and_not_the_shorter_form() -> None:
    """The names F-057 actually named, plus the case the short form gets wrong."""
    import feast_probe_record as probe

    for published, canonical in (
        ("PyYAML", "pyyaml"),
        ("typing_extensions", "typing-extensions"),
        ("prometheus_client", "prometheus-client"),
        ("SQLAlchemy", "sqlalchemy"),
        ("ast_serialize", "ast-serialize"),
        ("zope.interface", "zope-interface"),  # `lower().replace('_','-')` leaves the dot
        ("a__b", "a-b"),  # ...and leaves a double hyphen
    ):
        assert probe._normalize(published) == canonical


@pytest.mark.skipif(
    not (REPO / ".venv-feast" / "bin" / "python").exists(),
    reason="the quarantine venv is a build artifact, gitignored and absent in CI",
)
def test_rewriting_the_pins_reproduces_the_committed_file_exactly(tmp_path) -> None:
    """Generate twice, diff empty; regenerated == committed — and uv.lock untouched.

    It writes to a COPY, never to the tracked file: a test that regenerated the
    artifact in place would leave the tree dirty on its own failure, and rewriting
    state that already exists is the shape F-053/F-063 keep finding (gotcha #48).
    """
    import feast_probe_record as probe

    committed = PINS.read_text(encoding="utf-8")
    lock_before = (REPO / "uv.lock").read_bytes()

    target = tmp_path / "requirements-feast.txt"
    target.write_text(committed, encoding="utf-8")
    first = None
    for _ in range(2):
        assert probe.main(["--rewrite-pins", "--pins", str(target)]) == 0
        written = target.read_text(encoding="utf-8")
        if first is None:
            first = written
        assert written == first, "two regenerations of the same venv disagree"

    assert first == committed, (
        "--rewrite-pins no longer reproduces the committed pin file. That is F-057: a "
        "two-line change would arrive as a diff nobody can read, and a third line could "
        "hide in it"
    )
    assert (REPO / "uv.lock").read_bytes() == lock_before, "the quarantine reached uv.lock"


def test_the_gitignore_says_out_loud_what_is_generated() -> None:
    """uv writes a .gitignore inside a venv it creates; that is not review-visible."""
    body = GITIGNORE.read_text(encoding="utf-8")
    for entry in (".venv-feast/", "data/feast/", "infra/feast/feature_repo/data/"):
        assert entry in body, f"{entry} is not named in the root .gitignore (F-029's lesson)"


# ------------------------------------------------- end-of-window stamps ---
def test_the_window_stamp_is_the_exclusive_end_of_the_window() -> None:
    import feast_sources

    assert str(feast_sources._window_stamp(("2019-01",))) == "2019-02-01 00:00:00"
    assert str(feast_sources._window_stamp(("2019-01", "2019-06"))) == "2019-07-01 00:00:00"


def test_the_window_stamp_survives_a_year_boundary() -> None:
    """The arithmetic nobody exercises until December, done with a calendar."""
    import feast_sources

    assert str(feast_sources._window_stamp(("2019-11", "2019-12"))) == "2020-01-01 00:00:00"
    assert str(feast_sources._window_stamp(("2020-02",))) == "2020-03-01 00:00:00"


def test_the_producer_writes_only_into_its_own_tree() -> None:
    """M8 law 2, asked of the code: no settled tree is a write target."""
    import feast_sources

    assert feast_sources.OUT_DIR == REPO / "data" / "feast"
    source = PRODUCER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    writers = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"write_table", "to_parquet", "to_csv", "write_text"}
    ]
    assert len(writers) == 1, (
        "exactly one writer may exist, inside `_write`, so every output path is "
        f"OUT_DIR by construction; found {len(writers)}"
    )


# --------------------------------------------------- the plan check (F-055) ---
def test_the_clock_allowlist_is_exactly_the_two_stamped_fields() -> None:
    """Widening this set is how a real diff would be hidden behind F-055's noise."""
    import feast_plan_check

    assert feast_plan_check.CLOCK_FIELDS == ("seconds:", "nanos:")


def test_the_plan_parser_calls_a_clock_only_diff_clock_only() -> None:
    import feast_plan_check

    output = (
        "Updated feature view zone_static\n"
        "\tbatch_source: type: BATCH_FILE\n"
        'name: "zone_static_source"\n'
        "meta {\n"
        "  created_timestamp {\n"
        "    seconds: 1787295380\n"
        "    nanos: 66409000\n"
        "  }\n"
        "}\n"
        " -> type: BATCH_FILE\n"
        'name: "zone_static_source"\n'
        "meta {\n"
        "  created_timestamp {\n"
        "    seconds: 1787295411\n"
        "    nanos: 758572000\n"
        "  }\n"
        "}\n"
        "\n"
        "No changes to infrastructure\n"
    )
    blocks, other = feast_plan_check.parse(output)
    assert len(blocks) == 1 and blocks[0]["clock_only"] is True
    assert any("No changes to infrastructure" in line for line in other), (
        "the trailer must not be absorbed into the last block — it would make exactly "
        "one object look different for a reason that has nothing to do with it"
    )


def test_the_plan_parser_calls_a_real_change_substantive() -> None:
    """The half that matters: a renamed field must not read as a clock reading."""
    import feast_plan_check

    output = (
        "Updated feature view zone_static\n"
        "\tfeatures: [name: \"centroid_lat\"\n"
        "value_type: DOUBLE\n"
        "]\n"
        " -> [name: \"centroid_lat_TAMPERED\"\n"
        "value_type: DOUBLE\n"
        "]\n"
    )
    blocks, _ = feast_plan_check.parse(output)
    assert blocks[0]["clock_only"] is False
    assert any("TAMPERED" in line for line in blocks[0]["substantive_diff"])


def test_a_created_or_deleted_object_is_never_clock_only() -> None:
    """A view appearing or vanishing is the loudest possible diff, not a stamp."""
    import feast_plan_check

    blocks, _ = feast_plan_check.parse("Created feature view something_new\n")
    assert blocks[0]["clock_only"] is False


# ------------------------------------------- the catalog and the registry ---
@pytest.mark.needs_records
def test_every_registered_view_carries_a_verdict_and_the_catalog_agrees() -> None:
    """The catalog cannot drift from the store, in either direction.

    Read from `automation/runs/m8-feast/registry.json`, which was written by
    reading the APPLIED registry back — not by re-reading `definitions.py`. Two
    files in one commit agreeing with each other proves nothing; this asserts
    that what Feast stored agrees with what a human is told.
    """
    record = json.loads(REGISTRY_RECORD.read_text(encoding="utf-8"))
    catalog = CATALOG.read_text(encoding="utf-8")
    assert record["feature_views"], "the registry record holds no views"
    for view in record["feature_views"]:
        verdict = view["tags"].get("verdict")
        assert verdict in VERDICTS, f"{view['name']} carries verdict {verdict!r}"
        heading = f"### `{view['name']}` — **{verdict}**"
        assert heading in catalog, (
            f"{CATALOG.name} has no heading {heading!r} — the store and the page "
            "disagree about what this feature is worth"
        )
    # And the other direction: the page may not carry an entry the store has
    # never heard of, except the CANDIDATE, which is a candidate precisely
    # because it is not a view.
    headed = set(re.findall(r"^### `([a-z_]+)` — \*\*", catalog, flags=re.MULTILINE))
    registered = {view["name"] for view in record["feature_views"]}
    assert headed - registered == {"airport_regime_flag"}, (
        f"the catalog documents {sorted(headed - registered)} which the registry does "
        "not hold; only the declared candidate may appear without a view"
    )


@pytest.mark.needs_records
def test_the_catalog_labels_the_dropped_family_as_a_sample_number() -> None:
    """gotcha #15: a number from a sample is labelled as one, especially a losing one.

    g5's -1.63% was measured at 15% and never refitted at full data, because a
    dropped group is not refitted. Quoting it beside g1's and g2's full-data
    numbers without saying so would compare two different things.
    """
    record = json.loads(REGISTRY_RECORD.read_text(encoding="utf-8"))
    dropped = [v for v in record["feature_views"] if v["tags"].get("verdict") == "catalog-only"]
    assert dropped, "no catalog-only view is registered — the losers vanished"
    for view in dropped:
        assert "SAMPLE" in view["tags"]["ablation"].upper(), (
            f"{view['name']}'s ablation tag quotes a sample number without saying so"
        )
    assert "15%-sample number" in CATALOG.read_text(encoding="utf-8")


@pytest.mark.needs_records
def test_the_probe_records_the_wall_it_was_built_around() -> None:
    """The probe's job is the two columns, not the install."""
    record = json.loads(PROBE_RECORD.read_text(encoding="utf-8"))
    wall = record["wall"]
    assert wall["differs_on"] == ["pandas"], (
        "M8-S3's seam argument rests on pandas being the ONLY difference; if that "
        "changed, the argument has to be re-made rather than re-quoted"
    )
    assert wall["project"]["pandas"].startswith("3.")
    assert wall["quarantine"]["pandas"].startswith("2.")
    assert record["invariants"]["feast_in_project_environment"] is False
    assert record["quarantine_packages"] == len(record["quarantine_pins"])


@pytest.mark.needs_records
def test_the_recorded_plan_has_no_substantive_diff() -> None:
    record = json.loads(PLAN_RECORD.read_text(encoding="utf-8"))
    assert record["exit_code"] == 0
    assert record["substantive_count"] == 0
    assert record["infrastructure_line"] == "No changes to infrastructure"


@pytest.mark.needs_records
def test_the_window_stamps_in_the_registry_are_the_six_month_starts() -> None:
    """What M8-S3's point-in-time proof will assert against, pinned now.

    Six windows, each stamped at the first instant of the month AFTER its last
    month — so a 2019-04 row is served the 2019-01..03 table and a val or test
    row is served the full one, which is exactly what `aggregates.transform`
    does. The first train month has no window and therefore no rows.
    """
    record = json.loads(REGISTRY_RECORD.read_text(encoding="utf-8"))
    expected = [f"2019-{month:02d}-01 00:00:00" for month in range(2, 8)]
    for name in ("od_window_stats", "pu_hour_window_stats"):
        view = next(v for v in record["feature_views"] if v["name"] == name)
        assert view["event_timestamps"] == expected, (
            f"{name} is stamped {view['event_timestamps']}, not the six exclusive "
            "window ends"
        )
        assert view["ttl_seconds"] is None, (
            "a TTL would make the store withhold the window the fitted model was "
            "served, and disagree with aggregates.transform as the gap widened"
        )
