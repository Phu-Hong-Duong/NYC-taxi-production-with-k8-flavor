"""The sanctioned lock anchor, and the distinction a search-and-replace destroys.

`uv.lock` is this project's dependency graph, and since M8-S1 two milestone gates
have asserted it byte-identical to a TAG. M9-S11 moved that anchor once, by PO
letter (AWAITING_PO 2026-08-24-5, answered 2026-08-25, option (b)) — sqlparse
0.5.5 -> 0.6.0 to clear three HIGH CVEs before the public flip, which also
required dbt-core 1.12.2 -> 1.12.3 because 1.12.2 declares `sqlparse<0.6.0`.

TWO THINGS THIS FILE EXISTS TO STOP, and the second is the one that would be
invisible in review.

1. The anchor drifting between the four scripts that name it. Four copies of a
   tag name is four twins; the repo has been burned by that shape before (the
   port family, the hostPort pairs). One test, both directions.

2. A SEARCH-AND-REPLACE dragging §7's registry bound along with the lock anchor.
   The same literal `m7-closed` is used for two OPPOSITE purposes:

     - the LOCK anchor — "uv.lock must equal this tag's blob". Moving it forward
       is neutral: the gate still refuses an unsanctioned edit, just against a
       newer baseline.
     - the REGISTRY bound — "no model version may have been created after this
       tag". Moving it FORWARD ADMITS versions instead of refusing them, so the
       next `sed -i s/m7-closed/<newer>/` silently loosens the strongest form of
       the alias law in both M8's and M9's gates.

   A reviewer reading a diff full of one tag name replaced by another has no
   way to see that half of them were a loosening. So it is asserted here.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# The anchor the PO sanctioned. Written here ONCE; every script is checked
# against it, and this literal is what a future sanctioned move must edit.
SANCTIONED_ANCHOR = "lock-rebaselined-m9-publish"

# The bound on registry-version creation times. It may only ever move BACKWARD
# (earlier), never forward, so in practice it does not move at all.
REGISTRY_BOUND = "m7-closed"

LOCK_ANCHOR_SITES = {
    "scripts/verify_m8.sh": 1,          # LOCK_ANCHOR = "..."
    "scripts/verify_m9.sh": 1,          # LOCK_ANCHOR = "..."
    "scripts/verify_m8_redteam.sh": 1,  # the still-green needle
    "scripts/verify_m9_redteam.sh": 1,  # the still-green needle
}

REGISTRY_BOUND_SITES = ("scripts/verify_m8.sh", "scripts/verify_m9.sh")


def read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)


def require_a_clone_that_has_tags() -> None:
    """Skip only where a MISSING tag proves nothing — gotcha #105 / F-060.

    `actions/checkout@v4` fetches no tags, so in CI *every* tag is absent and an
    absent anchor says nothing about this repository. That is a property of the
    checkout, not of the invariant.

    The discriminator is the one F-060 established: **where the artifact is an
    absence, prove first that presence was possible.** A clone holding NO tags at
    all cannot answer the question and skips; a clone holding tags and not THIS
    one is a real defect and fails. So the two failure modes stay distinguishable
    instead of collapsing into one permissive `skipif`.

    Honest limit, stated rather than left to be discovered: this means CI does not
    check the anchor. The host does, on every `make verify-m8` / `verify-m9`, and
    those are where the invariant is enforced.
    """
    if not git("tag").stdout.strip():
        pytest.skip(
            "this clone holds no tags at all (a shallow CI checkout — "
            "`actions/checkout` does not fetch them), so an absent anchor is a fact "
            "about the checkout and not about the lock. The gates check it on the host."
        )


def test_every_gate_names_the_same_lock_anchor():
    """Four sites, one tag. A drifted anchor is a gate checking a stale baseline."""
    for rel, at_least in LOCK_ANCHOR_SITES.items():
        found = read(rel).count(SANCTIONED_ANCHOR)
        assert found >= at_least, (
            f"{rel} does not name the sanctioned lock anchor {SANCTIONED_ANCHOR!r}; "
            f"found {found} occurrence(s). If the anchor moved by PO letter, it moves "
            f"in every site AND in this test, together."
        )


def test_the_lock_anchor_is_an_annotated_tag_that_resolves():
    """A gate whose reference point does not exist has no invariant at all."""
    require_a_clone_that_has_tags()
    rc = git("rev-parse", "--verify", f"{SANCTIONED_ANCHOR}^{{commit}}")
    assert rc.returncode == 0, (
        f"the {SANCTIONED_ANCHOR} tag does not resolve in this clone. `verify-m8` §1 and "
        f"`verify-m9` §7 both read `git show {SANCTIONED_ANCHOR}:uv.lock`; without the tag "
        f"they FAIL rather than pass, which is the safe direction — but it is still broken. "
        f"Fetch tags: `git fetch --tags`."
    )


def test_the_anchored_lock_is_the_lock_on_disk():
    """The invariant the two gates assert, asserted here without a cluster.

    This is the cheap copy: the gates make the same comparison, but they need a
    live platform to run and this does not, so a lock edit is caught by `pytest`
    and by CI rather than at the next milestone gate.
    """
    require_a_clone_that_has_tags()
    blob = git("show", f"{SANCTIONED_ANCHOR}:uv.lock")
    assert blob.returncode == 0, (
        f"this clone has tags but not {SANCTIONED_ANCHOR} — the anchor was never pushed, "
        f"or was deleted. `git fetch --tags` first; if it is genuinely gone, the two gates "
        f"have no reference point and go RED, which is the safe direction and still broken."
    )
    assert blob.stdout == (REPO / "uv.lock").read_text(encoding="utf-8"), (
        "uv.lock DIFFERS from the sanctioned anchor. The project's dependency graph moves "
        "only by PO letter (F-013's spirit applied to dependencies): either revert the "
        f"lock, or land the letter and move the anchor. `git diff {SANCTIONED_ANCHOR} "
        "-- uv.lock` says what moved."
    )


def test_the_registry_creation_bound_did_not_follow_the_anchor():
    """The distinction a bulk rename destroys.

    §7 of both gates asserts that NO registry version was created after a tag.
    That check gets WEAKER as the tag moves forward — at a tag placed today it
    would admit every version created between M7 and today. It must stay pinned
    at `m7-closed` even while the lock anchor moves.
    """
    for rel in REGISTRY_BOUND_SITES:
        text = read(rel)
        # Match the INVOCATION, not the word (gotcha #35/#99): both files argue
        # about tags in prose, and this must key on the `git log ... -1 <tag>`
        # call that actually computes the bound.
        calls = re.findall(r'"git",\s*"log",\s*"--format=%ct",\s*"-1",\s*"([^"]+)"', text)
        assert calls, f"{rel} no longer computes a registry creation bound at all"
        for tag in calls:
            assert tag == REGISTRY_BOUND, (
                f"{rel} bounds registry-version creation times at {tag!r}, not "
                f"{REGISTRY_BOUND!r}. Moving that bound FORWARD admits versions instead of "
                f"refusing them — it is a loosening of the alias law wearing a rename's "
                f"clothes. The LOCK anchor and this bound are different facts."
            )


def test_the_two_purposes_are_not_the_same_tag():
    """Stated as its own assertion so the reason survives a future edit."""
    assert SANCTIONED_ANCHOR != REGISTRY_BOUND, (
        "the lock anchor and the registry creation bound have collapsed onto one tag; "
        "they move for different reasons and in different directions"
    )


def test_the_sanctioned_bump_is_actually_in_the_lock():
    """What the PO's letter bought, asserted against the artifact rather than the story.

    Both packages are named because both moved, and the second one is the finding:
    dbt-core 1.12.2 declares `sqlparse<0.6.0`, so the chartered one-liner
    `uv lock --upgrade-package sqlparse` produced an EMPTY diff.
    """
    lock = read("uv.lock")
    for name, version in (("sqlparse", "0.6.0"), ("dbt-core", "1.12.3")):
        block = re.search(rf'\[\[package\]\]\nname = "{re.escape(name)}"\nversion = "([^"]+)"',
                          lock)
        assert block, f"{name} is not in uv.lock at all"
        assert block.group(1) == version, (
            f"uv.lock pins {name} {block.group(1)}, expected {version} — the CVE bump "
            f"(AWAITING_PO 2026-08-24-5, option (b)) is not in the artifact"
        )


def test_the_numeric_stack_did_not_move_with_it():
    """gotcha #36 as a standing assertion, not a one-off measurement.

    The bump's whole risk was a resolver quietly walking the pinned numeric stack.
    It did not (243 packages before and after, 2 moved, 0 added, 0 removed) — and
    this keeps that true for the NEXT dependency change too.
    """
    lock = read("uv.lock")
    for name, version in (
        ("pandas", "3.0.5"),
        ("numpy", "2.5.2"),
        ("scikit-learn", "1.9.0"),
        ("mlflow-skinny", "3.15.1"),
        ("lightgbm", "4.7.0"),
        ("dbt-duckdb", "1.11.0"),
        ("duckdb", "1.5.5"),
        ("pyarrow", "25.0.1"),
        ("xgboost", "3.4.1"),
        ("scipy", "1.18.0"),
    ):
        block = re.search(rf'\[\[package\]\]\nname = "{re.escape(name)}"\nversion = "([^"]+)"',
                          lock)
        assert block, f"{name} vanished from uv.lock"
        assert block.group(1) == version, (
            f"{name} moved to {block.group(1)} (expected {version}) — CLAUDE.md's version "
            f"table and every measured number in this repo were taken against {version}"
        )


def test_the_quarantine_still_does_not_pin_sqlparse():
    """A recorded ABSENCE, checked rather than remembered (M9-S11's charter).

    The Feast quarantine rebuilds from 66 exact pins with `--no-deps`. sqlparse is
    not among them, so the CVE bump has nothing to do there — but 'we checked and
    it was absent' is only worth something if it stays checked.
    """
    pins = read("infra/feast/requirements-feast.txt").lower()
    assert "sqlparse" not in pins, (
        "the Feast quarantine now pins sqlparse; M9-S11 recorded its absence, so a "
        "pin arriving later needs the same CVE decision applied on that side of the wall"
    )
