"""M4-S3: the task image's twins, and the two rules its build context obeys.

Nothing here builds an image — a unit test that needed Docker would be an
integration test wearing the wrong marker, and CI runs this file on every PR
without a daemon. What IS testable without a build is every place the image's
contents are written down twice:

* the base image is pinned by TAG **and** digest (the Metabase precedent), and its
  python version is the project's,
* every `uv sync` in the Dockerfile is `--frozen`, so a drifted lock fails the
  build instead of shipping a different pandas than the champion was fitted with,
* `libgomp1` is installed as a package — debt D-004's whole ask,
* `.dockerignore` excludes exactly what the repo's own ignore files exclude, and
  **not** `data/reference/` (1.1 MB of committed lookup tables the feature path
  reads) or `.env.example` (a committed template a test asserts against). Both
  were excluded by the first draft and 24 in-image tests went red for it, which is
  why these are assertions now rather than a comment.

The live half — that the image runs, that its OpenMP is the system's, that the
unit suite passes inside it, that a real pipeline stage executes — is proved by
`make image-smoke` (10 checks) and its sensor drill `make image-smoke-redteam`.
See docs/task_image_m4.md for both transcripts.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO / "docker" / "Dockerfile.pipeline"
DOCKERIGNORE = REPO / ".dockerignore"
BUILD_LOAD = REPO / "scripts" / "image_build_load.sh"
SMOKE = REPO / "scripts" / "image_smoke.sh"
REDTEAM = REPO / "scripts" / "image_smoke_redteam.sh"
MAKEFILE = REPO / "Makefile"
DECISION = REPO / "docker" / "DECISION-D001-image-delivery.md"


def code_only(text: str) -> str:
    """Drop whole-line `#` comments. gotcha #53, and it bit again in this file.

    Both the Dockerfile and these scripts carry more prose than instructions — by
    design, it is where the reasoning lives — and a naive `"chown -R" not in text`
    or `":latest" not in text` goes RED on the comment that EXPLAINS why neither is
    used. Four of this file's assertions failed that way on their first run. In a
    repo where prose is load-bearing, a check about structure must read structure.
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


@pytest.fixture(scope="module")
def dockerfile() -> str:
    return code_only(DOCKERFILE.read_text())


@pytest.fixture(scope="module")
def dockerignore_entries() -> list[str]:
    return [
        line.strip()
        for line in DOCKERIGNORE.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


# ------------------------------------------------------------------ the pins ---


def test_the_base_image_is_pinned_by_tag_and_digest(dockerfile: str) -> None:
    """A tag alone is not a pin: `python:3.12.14-slim-trixie` can be re-pushed."""
    match = re.search(r"^FROM (python:\S+)@(sha256:[0-9a-f]{64})$", dockerfile, re.M)
    assert match, "FROM must carry both a tag and a sha256 digest"
    assert "3.12.14" in match.group(1), "the base must be the project's 3.12.14"


def test_the_base_image_python_matches_the_projects_pinned_interpreter(dockerfile: str) -> None:
    """`.python-version` and the base image tag are the same decision, twice."""
    declared = (REPO / ".python-version").read_text().strip()
    assert re.search(rf"^FROM python:{re.escape(declared)}\.", dockerfile, re.M), (
        f".python-version says {declared}; the FROM line must agree"
    )


def test_uv_is_pinned_by_digest_too(dockerfile: str) -> None:
    """The resolver is part of the graph: a different uv could legally re-resolve."""
    match = re.search(
        r"COPY --from=ghcr\.io/astral-sh/uv:(\d+\.\d+\.\d+)@(sha256:[0-9a-f]{64})", dockerfile
    )
    assert match, "uv must be copied from an image pinned by version AND digest"


def test_every_uv_sync_in_the_image_is_frozen(dockerfile: str) -> None:
    """--frozen is what makes uv.lock authoritative rather than advisory."""
    syncs = re.findall(r"uv sync[^\n]*", dockerfile)
    assert syncs, "the image must install the project with uv sync"
    for sync in syncs:
        assert "--frozen" in sync, f"unfrozen sync would re-resolve the graph: {sync}"


def test_libgomp1_is_installed_as_a_package_which_is_the_whole_of_d004(dockerfile: str) -> None:
    assert re.search(r"apt-get install[^\n]*libgomp1", dockerfile), (
        "debt D-004 asks the image to install libgomp1 as a real package"
    )


def test_no_toolchain_is_installed_because_every_wheel_is_prebuilt(dockerfile: str) -> None:
    """A compiler in a task image is attack surface that buys nothing here."""
    for forbidden in ("build-essential", "gcc ", "g++", "cmake"):
        assert forbidden not in dockerfile, f"{forbidden!r} has no reason to be in the image"


def test_the_image_runs_as_a_non_root_user(dockerfile: str) -> None:
    assert re.search(r"^USER taxi$", dockerfile, re.M), "the image must not run as root"
    # And the USER must come BEFORE the installs — the ordering that avoided a
    # 1.7 GB duplicate layer, measured with `docker history` (see the Dockerfile).
    user_at = dockerfile.index("\nUSER taxi")
    sync_at = dockerfile.index("uv sync")
    assert user_at < sync_at, (
        "USER must precede uv sync: building as root and chown -R'ing afterwards "
        "duplicates the whole venv into a second layer (measured: 1.7 GB, 139 s)"
    )
    assert "chown -R" not in dockerfile, "chown -R over /app is the layer-duplication mistake"


# --------------------------------------------------------- the build context ---


def test_the_dockerignore_excludes_every_dvc_tracked_data_path(
    dockerignore_entries: list[str],
) -> None:
    """data/.gitignore names what DVC owns; the image must not carry any of it."""
    dvc_owned = [
        line.strip().lstrip("/")
        for line in (REPO / "data" / ".gitignore").read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert dvc_owned, "data/.gitignore should name the DVC-tracked trees"
    normalised = {entry.rstrip("/") for entry in dockerignore_entries}
    for path in dvc_owned:
        assert f"data/{path}" in normalised, (
            f"data/{path} is DVC's and must be excluded from the build context"
        )


def test_the_dockerignore_keeps_the_committed_reference_tables(
    dockerignore_entries: list[str],
) -> None:
    """The bug this test exists for: `data/` wholesale broke 24 in-image tests.

    data/reference/ is committed, 1.1 MB, and is the lookup layer
    `taxi_mlops.features` reads at fit time and (from M5) at serving time. It is
    not data in the DVC sense at all.
    """
    for entry in dockerignore_entries:
        stripped = entry.lstrip("!").rstrip("/")
        assert stripped not in ("data", "data/reference"), (
            f".dockerignore entry {entry!r} would drop the committed reference tables"
        )
    # And the files themselves are still there to be included.
    for name in ("taxi_zone_centroids.csv", "us_federal_holidays.csv", "taxi_zones.zip"):
        assert (REPO / "data" / "reference" / name).exists()


def test_the_dockerignore_excludes_the_real_env_but_not_its_template(
    dockerignore_entries: list[str],
) -> None:
    assert ".env" in dockerignore_entries, "the real .env must never enter a layer"
    assert "!.env.example" in dockerignore_entries, (
        ".env.example is a committed template with no secret in it, and "
        "tests/unit/test_marts.py asserts against it — a `.env.*` glob eats it"
    )
    assert ".env.*" not in dockerignore_entries


def test_the_venv_and_git_history_stay_out_of_the_context(
    dockerignore_entries: list[str],
) -> None:
    normalised = {entry.rstrip("/") for entry in dockerignore_entries}
    for path in (".venv", ".git", "automation/logs", "automation/runs"):
        assert path in normalised, f"{path} has no place in the build context"


# ------------------------------------------------------------- the mechanism ---


def test_the_tag_is_immutable_by_construction(dockerfile: str) -> None:
    """A mutable tag is what lets a node hold stale bytes under the right name."""
    script = code_only(BUILD_LOAD.read_text())
    assert "git rev-parse --short HEAD" in script, "the tag must come from the git sha"
    assert "-dirty" in script, "an uncommitted tree must be visible in the tag"
    assert ":latest" not in script.replace("latest-local", ""), (
        "a :latest tag defeats imagePullPolicy: IfNotPresent"
    )


def test_the_load_is_read_back_from_the_nodes_with_their_own_tool() -> None:
    """`kind load` exiting 0 and containerd holding the image are two claims."""
    script = code_only(BUILD_LOAD.read_text())
    assert "crictl images" in script, "the read-back must ask containerd, not docker"
    assert "kind load docker-image" in script
    assert "BEFORE" in script, (
        "print each node's image id before AND after, or idempotence is a claim"
    )


def test_the_smoke_cannot_pass_by_skipping_the_unit_suite() -> None:
    """SKIP_UNIT is a debugging lever; a gate with a fast mode runs in fast mode."""
    script = code_only(SMOKE.read_text())
    skip_block = script[script.index("SKIP_UNIT:-0") :]
    # Bounded by the next section's own header call, not by a `# ---` rule: the
    # rules are comments, and code_only() has just removed them. Same lesson as
    # code_only()'s own docstring, one level in.
    skip_block = skip_block[: skip_block.index("head2 ")]
    assert "bad " in skip_block, "the SKIP_UNIT branch must count as a FAILURE, never a pass"


def test_no_container_in_either_script_uses_a_login_shell() -> None:
    """gotcha #56: `bash -lc` re-reads /etc/profile and drops /app/.venv/bin from PATH.

    `python` then resolves to the base interpreter, every taxi_mlops import fails,
    and the failure is reported as whatever the check was looking for. It cost this
    story one wrong RED verdict in the sensor drill.
    """
    for script in (SMOKE, REDTEAM):
        text = code_only(script.read_text())
        assert "bash -lc" not in text, f"{script.name} must use `bash -c`, never a login shell"


def test_the_d001_decision_is_recorded_with_both_options_and_a_trigger() -> None:
    """The debt row asked for a decision WITH the honest costs of each option."""
    text = DECISION.read_text()
    assert "kind load docker-image" in text and "containerdConfigPatches" in text
    assert "PO-sanctioned rebuild" in text, "the deferred option needs a named trigger"
    for target in ("image-build", "image-load", "image-smoke", "image-smoke-redteam"):
        assert re.search(rf"^{target}:.*##", MAKEFILE.read_text(), re.M), (
            f"make {target} must exist and be self-documenting"
        )


NEEDS_GIT_AND_DOCKER = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("docker") is None,
    reason="the DRY_RUN preview needs git for the tag and docker on PATH for its precheck",
)


@NEEDS_GIT_AND_DOCKER
def test_dry_run_previews_the_exact_tag_and_mutates_nothing(tmp_path: Path) -> None:
    """gotcha #30's rule, applied to a new script: DRY_RUN must not build or load."""
    result = subprocess.run(
        ["bash", str(BUILD_LOAD)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=REPO,
        env={**dict(__import__("os").environ), "DRY_RUN": "1"},
    )
    assert result.returncode == 0, result.stderr
    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=REPO
    ).stdout.strip()
    assert sha in result.stdout, "the preview must name the tag it would build"
    assert "nothing was built, nothing was loaded" in result.stdout
    assert "-- build ---" not in result.stdout, "DRY_RUN must not reach the build step"


def test_the_openmp_probe_module_exists_and_is_the_dash_m_form() -> None:
    """F-024: `python -c` cannot re-exec, so the probe has to be a module."""
    probe = REPO / "src" / "taxi_mlops" / "training" / "openmp_probe.py"
    assert probe.exists(), "scripts/image_smoke.sh runs it with -m"
    assert 'if __name__ == "__main__":' in probe.read_text()
