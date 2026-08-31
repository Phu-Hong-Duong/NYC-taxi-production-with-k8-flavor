"""The M1-S2 recipes' invariants — the ones nothing at runtime would complain about.

Each assertion here corresponds to a way the data path can look green while
being wrong:

* the rebuild proof refreshing the pin it is being judged against (it would pass
  forever, including after the writer stopped being deterministic);
* `make data` pinning before it produces, so every pin is one run stale;
* a DVC remote living inside the repo or the cluster — both die with the thing
  they are supposed to outlive;
* DVC's usage analytics, which are ON by default and send data off this machine
  (CLAUDE.md: "$0 budget — nothing leaves this machine").

The live half — the actual wipe, rebuild and hash comparison — is proved by
running `make rebuild-proof` against the real 8 months (M1-S2 handoff entry).
"""

from __future__ import annotations

import configparser
from pathlib import Path

from conftest import REPO

PIPELINE = (REPO / "scripts" / "data_pipeline.sh").read_text()
PROOF = (REPO / "scripts" / "rebuild_proof.sh").read_text()
CLUSTER = (REPO / "scripts" / "cluster.sh").read_text()
MAKEFILE = (REPO / "Makefile").read_text()


# ------------------------------------------------------- the rebuild proof ----

def test_the_proof_rebuilds_without_refreshing_the_pin():
    """The subtle one: if the rebuild re-runs `dvc add`, it overwrites the very
    hashes it is about to be compared against, and the proof passes by tautology."""
    assert "SKIP_DVC=1 make data" in PROOF


def test_the_proof_checks_its_input_is_the_pinned_bytes():
    """Gotcha #6: a re-download is never trusted to be byte-identical."""
    assert "dvc status data/raw.dvc" in PROOF
    assert "up to date" in PROOF


def test_the_proof_has_a_second_independent_witness():
    """Our sha256 table and DVC's own hashes are different code over different
    metadata. One witness agreeing with itself proves nothing."""
    assert "data/processed.dvc data/rejected.dvc" in PROOF
    assert "dvc status" in PROOF


def test_the_proof_covers_both_derived_trees_not_just_the_clean_one():
    """M2-S1: the rejected sidecar is derived by the same pass from the same
    bytes. A proof that re-derives half a command's output proves half a
    command — and the half it skips is the one nobody looks at."""
    assert 'rm -rf "${REPO_ROOT:?}/data/processed" "${REPO_ROOT:?}/data/rejected"' in PROOF
    # the hash function walks both trees, and keeps the tree name in the key so
    # two same-named months in two trees cannot collide into one checked row
    assert 'for tree in ("processed", "rejected")' in PROOF
    assert 'p.relative_to(root)' in PROOF and 'root = pathlib.Path("data")' in PROOF


def test_the_proof_previews_before_it_deletes():
    assert "DRY_RUN" in PROOF and "rm -rf" in PROOF


# ------------------------------------------------------------- make data ----

def test_dvc_runs_after_the_steps_whose_output_it_pins():
    ingest = PIPELINE.index("m taxi_mlops.data ingest")
    duck = PIPELINE.index("m taxi_mlops.data duckdb")
    add = PIPELINE.index("dvc add data/raw data/processed data/rejected")
    push = PIPELINE.index("dvc push")
    assert ingest < duck < add < push


def test_make_data_is_the_one_command_the_docs_promise():
    assert "data: ##" in MAKEFILE and "bash scripts/data_pipeline.sh" in MAKEFILE
    assert "rebuild-proof: ##" in MAKEFILE and "bash scripts/rebuild_proof.sh" in MAKEFILE


# ------------------------------------------------------------ dvc config ----

def _dvc_config() -> configparser.ConfigParser:
    """DVC writes its remote sections quoted — `['remote "name"']` — so section
    names are matched by content here rather than reconstructed."""
    parser = configparser.ConfigParser()
    parser.read(REPO / ".dvc" / "config")
    return parser


def _remote_url(parser: configparser.ConfigParser) -> str:
    remote = parser.get("core", "remote")
    for section in parser.sections():
        if "remote" in section and remote in section:
            return parser.get(section, "url")
    raise AssertionError(f"default remote {remote!r} has no section in .dvc/config")


def test_dvc_analytics_are_off():
    """DVC phones home by default. This project's rule is that nothing leaves
    this machine — a default is not an exemption."""
    assert _dvc_config().get("core", "analytics", fallback="true") == "false"


def test_the_remote_outlives_both_the_cluster_and_the_repo():
    """A remote under a PVC dies with `make destroy`; one inside the repo dies
    with the clone it was meant to protect."""
    url = _remote_url(_dvc_config())
    assert not url.startswith(("s3://", "http://", "https://")), (
        f"remote {url!r} points at a service; in this project the only object store "
        "is MinIO, which lives in the cluster and dies with it"
    )
    path = Path(url)
    assert path.is_absolute()
    assert REPO not in path.parents and path != REPO


# --------------------------------------------------------------- destroy ----

def test_the_catalogue_is_destroyable_and_the_dvc_cache_is_not():
    """`data/analyst.duckdb` is regenerable by `make duckdb`; `.dvc/cache` with a
    local-only remote is the only copy of anything not on TLC's servers."""
    # split on the array's closing paren at the start of a line — the entries
    # carry prose comments that contain parens of their own
    regenerable = CLUSTER.split("REGENERABLE=(")[1].split("\n)")[0]
    deny = CLUSTER.split("DENY=(")[1].split("\n)")[0]
    assert "data/analyst.duckdb" in regenerable
    assert "data/analyst.duckdb" not in deny
    assert ".dvc/cache" in deny and "data/raw" in deny


def test_dvc_owns_the_data_gitignore_entries():
    """One place says 'these bytes are not git's'. A second copy in the root
    .gitignore would keep hiding the data even if DVC tracking were lost."""
    dvc_owned = (REPO / "data" / ".gitignore").read_text()
    assert "/raw" in dvc_owned and "/processed" in dvc_owned and "/rejected" in dvc_owned
    root = (REPO / ".gitignore").read_text()
    for line in root.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert stripped not in {
            "data/raw/",
            "data/processed/",
            "data/rejected/",
            "data/raw",
            "data/processed",
            "data/rejected",
        }


def test_destroy_treats_the_sidecar_as_regenerable_like_the_processed_tree():
    """`make rebuild-proof` proves data/rejected is a pure function of pinned raw
    plus this repo — the same claim that makes data/processed deletable. Leaving
    it off the list would make destroy quietly asymmetric about one derived tree."""
    regenerable = CLUSTER.split("REGENERABLE=(")[1].split("\n)")[0]
    deny = CLUSTER.split("DENY=(")[1].split("\n)")[0]
    assert "data/rejected" in regenerable and "data/rejected" not in deny
