"""The feature server's laws, asserted where a shell script cannot assert them.

M8-S4 leg 2. What is pinned here is what would be expensive or silent to get
wrong later:

* the image is built from the ONE pin file, `--no-deps`, and carries no registry
  and no store address (the two things a second home would be made of);
* the parity reader is a READER — it may not deploy, materialize, or touch the
  registry or the alias;
* the parity bar is EXACT and lives in ONE place, and the doc that argues it says
  so;
* `borough` and `is_airport` are NOT sourced from the store by the comparison,
  for the two reasons `docs/feast_server_m8.md` §5 gives.

The live half — that the pod answers, that Service DNS resolves, that the null
half is null — is `make deploy-feast-server`'s accept check and
`make feast-server-parity`. See docs/feast_server_m8.md for both transcripts.
"""

from __future__ import annotations

import ast
import json

import pytest
from conftest import REPO, without_comments

DOCKERFILE = REPO / "docker" / "feast-server.Dockerfile"
ENTRYPOINT = REPO / "docker" / "feast-server-entrypoint.sh"
BUILD = REPO / "scripts" / "build_feast_server.sh"
DEPLOY = REPO / "scripts" / "deploy_feast_server.sh"
PARITY = REPO / "scripts" / "feast_server_parity.py"
MANIFEST = REPO / "infra" / "manifests" / "feast-server.yaml"
DOC = REPO / "docs" / "feast_server_m8.md"
PINS = REPO / "infra" / "feast" / "requirements-feast.txt"
RECORD = REPO / "automation" / "runs" / "m8-transformer" / "server-parity.json"


# ---------------------------------------------------------------- the image ---


def test_the_base_is_the_same_digest_pinned_interpreter_as_the_task_image() -> None:
    """One libc family across node and workload, and no silent version bump."""
    froms = [ln for ln in DOCKERFILE.read_text().splitlines() if ln.startswith("FROM ")]
    assert len(froms) == 1, f"expected exactly one FROM, got {froms}"
    assert "@sha256:" in froms[0], "the base must be pinned by TAG AND DIGEST"
    pipeline_from = [
        ln
        for ln in (REPO / "docker" / "Dockerfile.pipeline").read_text().splitlines()
        if ln.startswith("FROM ")
    ]
    assert froms[0] == pipeline_from[0], (
        "the feature server and the task image must share one pinned interpreter; "
        f"got {froms[0]!r} vs {pipeline_from[0]!r}"
    )


def test_the_image_installs_from_the_one_pin_file_with_no_deps() -> None:
    """Two consumers, one pin file, no twin — and no resolver in the build path."""
    code = without_comments(DOCKERFILE.read_text())
    assert "infra/feast/requirements-feast.txt" in code
    assert "--no-deps" in code, (
        "a resolver consulted at build time can legally answer differently from the "
        "one that was reviewed; --no-deps is what makes the image reproduce the pins"
    )
    quarantine = without_comments((REPO / "scripts" / "feast_quarantine.sh").read_text())
    assert "requirements-feast.txt" in quarantine, (
        "the host quarantine must still read the same file this image installs from"
    )


def test_the_image_bakes_no_registry_and_no_store_address() -> None:
    """The two things that would make the image a second home."""
    code = without_comments(DOCKERFILE.read_text())
    assert "registry.db" not in code, (
        "the registry is generated and gitignored because definitions.py in git is "
        "the source of truth; baking one in would be F-013's second home"
    )
    # A COPY of the whole feature_repo directory would drag registry.db in.
    assert "feature_repo/definitions.py" in code and "feature_repo/feature_store.yaml" in code
    assert "COPY --chown=feast:feast infra/feast/feature_repo " not in code


def test_the_entrypoint_derives_the_registry_and_refuses_an_unset_store() -> None:
    text = ENTRYPOINT.read_text()
    code = without_comments(text)
    assert "feast apply" in code, "the registry must be DERIVED at every start"
    assert code.index("feast apply") < code.index("feast serve"), (
        "apply must precede serve, or the pod can serve an empty registry — which "
        "answers every lookup with null and looks exactly like a healthy one"
    )
    assert "FEAST_REDIS_CONNECTION" in code
    assert "set -euo pipefail" in code, (
        "a repo that cannot be applied must never reach `serve`"
    )


def test_the_entrypoint_is_copied_executable() -> None:
    """COPY preserves the source mode, and an editor writes 0644.

    The failure this pins is loud but misleading: containerd reports
    `exec: "...": permission denied`, which reads like a missing binary or a
    broken PATH rather than a missing execute bit. It cost one deploy.
    """
    code = without_comments(DOCKERFILE.read_text())
    entrypoint_copy = [ln for ln in code.splitlines() if "feast-server-entrypoint.sh" in ln]
    assert entrypoint_copy, "the entrypoint must be copied into the image"
    assert "--chmod=" in entrypoint_copy[0], entrypoint_copy[0]


def test_the_image_tag_carries_a_git_sha_and_marks_dirty() -> None:
    """M4-S3's rule: a mutable tag makes a stale node a wrong number, not an error."""
    code = without_comments(BUILD.read_text())
    assert "git rev-parse --short HEAD" in code
    assert "-dirty" in code
    assert ":latest" not in code


# --------------------------------------------------------------- the deploy ---


def test_the_deploy_refuses_a_dirty_image() -> None:
    """A -dirty image carries work that is not in git, so nothing it produces
    can be attributed to a commit. M8-S1 leg 2 spent a rebuild learning this."""
    code = without_comments(DEPLOY.read_text())
    assert '== *-dirty' in code or '"-dirty"' in code or "-dirty" in code
    assert "exit 3" in code


def test_the_accept_asserts_the_null_half_from_another_pod() -> None:
    """Gotcha #59 and its sibling: an answer, and an answer that must be absent."""
    code = without_comments(DEPLOY.read_text())
    assert "get-online-features" in code, "the accept must be a real lookup"
    assert "exec deploy/redis" in code, (
        "the accept must be asked from a pod that is NOT the server, or Service DNS "
        "and cross-pod reachability are not under test"
    )
    assert "264" in code, (
        "a check that only asserts presence passes against a server answering every "
        "question with the same row"
    )


def test_the_server_is_stateless_no_volume_no_hostport() -> None:
    # code_only, because this manifest's header ARGUES "WHY NO hostPort AND NO
    # PERSISTENCE" at length — and a naive substring check reads the argument as
    # the practice. Gotcha #53, caught by this test on its own first run, in the
    # same session as the two other places it is guarded against.
    manifest = without_comments(MANIFEST.read_text())
    assert "hostPort" not in manifest, "M8 law 1: no tenant gets a hostPort"
    assert "PersistentVolumeClaim" not in manifest and "volumeMounts" not in manifest, (
        "the feature server holds no data: its registry is derived at start and every "
        "value it serves lives in Redis"
    )
    assert "readinessProbe" in manifest and "livenessProbe" in manifest


# ---------------------------------------------------------------- the reader ---


@pytest.fixture(scope="module")
def parity_tree() -> ast.Module:
    return ast.parse(PARITY.read_text())


def _called_names(tree: ast.Module) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                out.add(func.id)
            elif isinstance(func, ast.Attribute):
                out.add(func.attr)
    return out


def test_the_parity_reader_is_a_reader(parity_tree: ast.Module) -> None:
    """AST, never a grep: this file argues at length about materializing and
    deploying, so a word search would match the argument (gotchas #53/#99)."""
    called = _called_names(parity_tree)
    for verb in ("materialize", "apply", "set_registered_model_alias", "promote"):
        assert verb not in called, f"a READER may not call {verb}()"

    # The one subprocess it is allowed is the ephemeral port-forward.
    subprocess_args = [
        node
        for node in ast.walk(parity_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"Popen", "run", "check_output", "check_call"}
    ]
    assert len(subprocess_args) == 1, (
        f"expected exactly one subprocess launch (the port-forward), got "
        f"{len(subprocess_args)}"
    )
    literals = [
        c.value
        for c in ast.walk(subprocess_args[0])
        if isinstance(c, ast.Constant) and isinstance(c.value, str)
    ]
    assert "port-forward" in literals, literals


def test_the_bar_is_exact_and_lives_in_one_place(parity_tree: ast.Module) -> None:
    tolerance = [
        node
        for node in parity_tree.body
        if isinstance(node, ast.Assign)
        and any(getattr(t, "id", None) == "TOLERANCE" for t in node.targets)
    ]
    assert len(tolerance) == 1, "the bar must be declared exactly once"
    assert ast.literal_eval(tolerance[0].value) == 0.0, (
        "the bar is EXACT — docs/feast_server_m8.md §3 argues why anything looser "
        "would be a hedge against a hazard this path does not have"
    )


def test_the_reader_does_not_source_borough_or_compare_it(parity_tree: ast.Module) -> None:
    """§5: the champion eats a borough CODE, the store holds the STRING, and the
    code is a property of the whole table's iteration order rather than of a zone."""
    zone_features = [
        node
        for node in parity_tree.body
        if isinstance(node, ast.Assign)
        and any(getattr(t, "id", None) == "ZONE_FEATURES" for t in node.targets)
    ]
    assert len(zone_features) == 1
    assert "borough" not in ast.literal_eval(zone_features[0].value)


def test_the_reader_pairs_by_name_never_by_position() -> None:
    """The server does not preserve the request's column order — observed on the
    accept run. A client zipping by position sends valid values under the wrong
    names, which is arm A of make parity-redteam, self-inflicted (gotcha #73)."""
    code = without_comments(PARITY.read_text())
    assert "metadata" in code and "feature_names" in code, (
        "the server's own feature_names must be the authority on which result "
        "block is which"
    )


def test_the_row_set_is_imported_from_parity_never_retyped() -> None:
    """One row set across four seams: the wire, the store, the offline join, and
    now the HTTP door."""
    code = without_comments(PARITY.read_text())
    assert "from taxi_mlops.serving.parity import HAZARDS" in code


def test_the_doc_argues_the_bar_and_names_the_partition() -> None:
    doc = DOC.read_text()
    assert "The bar is EXACT" in doc
    assert "one missing" in doc, "the load-bearing count must be named in the doc"
    assert "encoding is not a per-entity feature" in doc


@pytest.mark.needs_records
def test_the_record_holds_a_two_sided_partition_and_an_exact_result() -> None:
    payload = json.loads(RECORD.read_text())
    assert payload["bar"] == "EXACT"
    assert payload["max_abs_delta"] == 0.0
    assert payload["mismatched"] == 0
    assert payload["one_missing"] == 0, (
        "the load-bearing count: the two sides must agree about which values do "
        "not exist, not merely about the ones that do"
    )
    assert payload["partition_two_sided"] is True
    assert payload["zones_declined_by_store"] == payload["no_geometry_zones"]
