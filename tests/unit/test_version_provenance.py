"""F-048: the scale provenance — where it lives, and the two absences it separates.

**The finding, in one sentence.** F-020's transfer divides by the row count a
champion's count-scaled knobs were CHOSEN at; that number lived only in a tracked
host JSON under `automation/runs/`, `.dockerignore` correctly keeps those out of
the task image, and so the scheduled retrain resolved it to nothing and printed
*"no sampled search behind this champion"* — a sentence that was honest about what
the code could see and false about the world. Measured: the first fired
`retrain-schedule-proof` returned `rescale_factor: null, round_cap: 500` against
the host's `6.6667` and `2400` for the SAME champion in the SAME minute.

So there are two absences and they must never produce the same outcome:

* **"no refit record names this run"** — a real fact about a champion that came
  from no sampled search. A reported no-op, and it must stay one: F-020 is the
  finding that ASSUMING a sample fraction produces a plausible configuration
  nobody can check.
* **"I cannot see any records"** — a fact about the process, not about the
  champion. A refusal (option (c)), because a pod cannot tell the first from the
  second and the pod is where this happens every time.

And the long-run fix (option (a)) is that the fact travels with the thing it
describes: three tags on the VERSION, written at fit time for new versions and
backfilled for old ones through the one module allowed to touch the registry.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from taxi_mlops.training import registry as R
from taxi_mlops.training import retrain as RT

REPO = Path(__file__).resolve().parents[2]
BACKFILL = REPO / "scripts" / "backfill_version_provenance.py"
REGISTRY_SOURCE = (REPO / "src/taxi_mlops/training/registry.py").read_text()
RETRAIN_SOURCE = (REPO / "src/taxi_mlops/training/retrain.py").read_text()

#: M3-S4's real numbers: the sniper chose on 6,598,113 rows with a 800-round
#: per-trial cap, and the champion's refit ran at 43,987,422.
SNIPER_ROWS, SNIPER_CAP = 6_598_113, 800


@dataclass
class FakeVersion:
    version: str = "2"
    run_id: str = "92b73bd4f77d4a05b92472bfcfb3cccf"
    tags: dict[str, str] = field(default_factory=dict)


class FakeClient:
    """Records every call. A registry write is what these tests are about."""

    def __init__(self, version: FakeVersion | None = None) -> None:
        self.version = version or FakeVersion()
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_model_version(self, name: str, version: str) -> FakeVersion:
        self.calls.append(("get_model_version", {"name": name, "version": version}))
        return self.version

    def set_model_version_tag(self, *, name: str, version: str, key: str, value: str) -> None:
        self.calls.append(("set_model_version_tag", {"key": key, "value": value}))
        self.version.tags[key] = value


# ------------------------------------------------- the tags: write, read, refuse ----


def test_the_scale_round_trips_through_the_tags() -> None:
    tags = R.search_scale_tags(chosen_at_rows=SNIPER_ROWS, round_cap=SNIPER_CAP, source="s.json")
    assert R.read_search_scale(tags) == (SNIPER_ROWS, SNIPER_CAP, "s.json")


def test_no_sampled_search_is_RECORDED_and_not_left_absent() -> None:
    """The distinction the whole finding is about, at the level of one tag.

    An absent tag says "nobody wrote this down"; `NO_SEARCH` says "this champion
    had no sampled search". A reader that cannot tell them apart is F-048."""
    tags = R.search_scale_tags(chosen_at_rows=None, round_cap=None, source=None)
    assert tags[R.SEARCH_SCALE_ROWS] == R.NO_SEARCH
    assert R.read_search_scale(tags) == (None, None, tags[R.SEARCH_SCALE_SOURCE])
    assert R.read_search_scale({}) is None, "an absent tag is a THIRD answer, not the second"
    assert "no sampled search" in tags[R.SEARCH_SCALE_SOURCE]


def test_a_scale_that_is_not_a_row_count_is_refused() -> None:
    """F-020's divisor. A zero would be a plausible configuration nobody can check."""
    with pytest.raises(R.PromotionError):
        R.search_scale_tags(chosen_at_rows=0, round_cap=800, source="s")


def test_recording_the_scale_writes_tags_and_nothing_else() -> None:
    """The narrowest registry write that can exist: three tags on a version that
    already exists. No version is created, nothing is deleted, and no alias is
    read or moved — a backfill that could move `@champion` would be a rollback
    wearing a provenance script's clothes."""
    client = FakeClient()
    result = R.record_search_scale(
        client, model_name="nyc-taxi-eta", version="2",
        chosen_at_rows=SNIPER_ROWS, round_cap=SNIPER_CAP, source="sniper-v2.json",
    )
    verbs = {name for name, _ in client.calls}
    assert verbs == {"get_model_version", "set_model_version_tag"}
    assert sorted(result["written"]) == sorted(R.SEARCH_SCALE_TAGS)
    assert client.version.tags[R.SEARCH_SCALE_ROWS] == str(SNIPER_ROWS)


def test_a_second_backfill_with_the_same_numbers_changes_nothing() -> None:
    """Idempotent BY VALUE, the shape `registry.promote` and `metabase_boards.py`
    already have: a converging path that writes on every invocation is not
    converging, it is accumulating."""
    client = FakeClient()
    kwargs = dict(model_name="nyc-taxi-eta", version="2", chosen_at_rows=SNIPER_ROWS,
                  round_cap=SNIPER_CAP, source="sniper-v2.json")
    R.record_search_scale(client, **kwargs)
    client.calls.clear()
    second = R.record_search_scale(client, **kwargs)
    assert second["written"] == []
    assert not [name for name, _ in client.calls if name == "set_model_version_tag"]


def test_a_backfill_that_disagrees_with_what_is_recorded_is_REFUSED() -> None:
    """Provenance describes a fit that has already happened. Two different answers
    to "what scale was this chosen at?" is a defect somewhere, and overwriting the
    older one destroys the evidence of which."""
    client = FakeClient(FakeVersion(tags={R.SEARCH_SCALE_ROWS: str(SNIPER_ROWS)}))
    with pytest.raises(R.PromotionError, match="already records a different search scale"):
        R.record_search_scale(
            client, model_name="nyc-taxi-eta", version="2",
            chosen_at_rows=999_999, round_cap=SNIPER_CAP, source="somewhere else",
        )
    assert not [name for name, _ in client.calls if name == "set_model_version_tag"]


def test_the_provenance_path_names_no_destructive_verb() -> None:
    """Asked of the AST: this module argues its own no-delete law in prose, so a
    grep for the word would pass on the argument (#53/#68)."""
    tree = ast.parse(REGISTRY_SOURCE)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "record_search_scale")
    called = {n.func.attr for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    forbidden = {"delete_model_version", "delete_registered_model_alias",
                 "delete_model_version_tag", "set_registered_model_alias",
                 "get_model_version_by_alias", "create_model_version", "delete_run"}
    assert not (called & forbidden), called & forbidden


# --------------------------------------------------- the resolver's two absences ----


def _notes() -> list[str]:
    return []


def test_the_two_absences_produce_DIFFERENT_outcomes() -> None:
    """F-048's own closing condition, and the reason the finding exists.

    Same missing scale, two different worlds: a records directory that is present
    and simply names no refit for this run (a real no-op), and a records directory
    that is not there at all (a fact about the process — and inside a task pod it
    is the missing file EVERY time). One returns, one raises.
    """
    present = _notes()
    absent = _notes()
    # (1) visible directory, no matching record: a reported no-op.
    resolved = RT._search_scale("a-run-nothing-refers-to", "automation/runs/m3s4", present,
                                version="9")
    assert resolved == (None, None, None, None)
    assert any("no sampled search" in note or "no tracked refit record" in note
               for note in present), present
    # (2) no directory at all: a refusal that names the fix.
    with pytest.raises(RT.RetrainError) as exc:
        RT._search_scale("any-run", "automation/runs/there-is-no-such-directory", absent,
                         version="9")
    assert "does not exist here" in str(exc.value)
    assert "NOT the same" in str(exc.value), "the two facts must be told apart in words too"
    assert "backfill" in str(exc.value).lower(), "a refusal must name the fix, never a default"
    assert absent == [], "a refusal does not get to leave a note claiming a no-op"


def test_the_version_tag_is_preferred_and_the_host_records_are_not_consulted() -> None:
    """The pod path, in one assertion. `records_dir` here does not exist, so a
    resolver that fell through to the filesystem would RAISE — that it returns the
    tagged numbers is the proof that the registry answered."""
    version = FakeVersion(tags=R.search_scale_tags(
        chosen_at_rows=SNIPER_ROWS, round_cap=SNIPER_CAP, source="automation/runs/m3s4/x.json"))
    notes = _notes()
    rows, source, cap, cap_source = RT._scale_of(
        version, "automation/runs/there-is-no-such-directory", notes, model_name="nyc-taxi-eta")
    assert (rows, cap) == (SNIPER_ROWS, SNIPER_CAP)
    assert "registry" in source and "registry" in cap_source
    assert any("REGISTRY" in note for note in notes)


def test_a_version_recording_NO_search_is_a_no_op_and_never_a_refusal() -> None:
    """The honest no-op, once it is a recorded fact rather than a missing file.

    This is what makes the refusal above safe: a champion that really had no
    sampled search says so ON the version, so the pod resolves it without ever
    needing the host records."""
    version = FakeVersion(tags=R.search_scale_tags(
        chosen_at_rows=None, round_cap=None, source=None))
    notes = _notes()
    assert RT._scale_of(version, "automation/runs/there-is-no-such-directory", notes,
                        model_name="nyc-taxi-eta") == (None, None, None, None)
    assert any("recorded fact about the version" in note for note in notes), notes


@pytest.mark.needs_records
def test_an_untagged_version_still_resolves_through_the_host_records() -> None:
    """Versions minted before the tags existed must keep working on the host —
    otherwise landing this fix would break the path that was already correct."""
    refit = json.loads((REPO / "automation/runs/m3s4/refit-v2.json").read_text())
    notes = _notes()
    rows, _, cap, _ = RT._scale_of(
        FakeVersion(run_id=refit["run_id"]), "automation/runs/m3s4", notes,
        model_name="nyc-taxi-eta")
    assert (rows, cap) == (SNIPER_ROWS, SNIPER_CAP)
    assert any("carries no" in note for note in notes), "the fallback must say it was used"


def test_the_transfer_these_numbers_produce_is_still_F_020s() -> None:
    """The two numbers the on-cluster record must show once this lands: the
    factor 6.6667 and the re-derived cap 2400 (F-048's closing condition)."""
    factor = 43_987_422 / SNIPER_ROWS
    assert round(factor, 4) == 6.6667
    assert RT.round_budget(SNIPER_CAP, 500)[0] == 2400


# ---------------------------------------------------------------- the backfill ----


def test_the_backfill_derives_every_number_and_types_none() -> None:
    """The row count and the cap are read out of the tracked records. A constant
    here would be the same defect one layer along: a number that was true where it
    was written and is applied where it is not."""
    source = BACKFILL.read_text()
    for typed in (str(SNIPER_ROWS), "6598113", "6_598_113"):
        assert typed not in source, f"{typed} is typed into the backfill"
    tree = ast.parse(source)
    subscripts = {
        node.slice.value for node in ast.walk(tree)
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, str)
    }
    assert {"train_rows", "max_rounds"} <= subscripts, (
        "the scale must be read out of the sniper record's own fields")


def test_the_backfill_cannot_move_an_alias_or_mint_a_version() -> None:
    """It is the one script that writes to the registry outside a promotion, so
    the ban list is asked of its parsed calls rather than of its prose."""
    tree = ast.parse(BACKFILL.read_text())
    called = {node.func.attr for node in ast.walk(tree)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    forbidden = {"set_registered_model_alias", "delete_registered_model_alias",
                 "create_model_version", "delete_model_version", "get_model_version_by_alias",
                 "set_model_version_tag", "delete_run", "promote"}
    assert not (called & forbidden), called & forbidden
    assert "record_search_scale" in called, (
        "the write must go through registry.py's additive path, not around it")


def test_the_make_target_exists_and_advertises_its_dry_run() -> None:
    makefile = (REPO / "Makefile").read_text()
    assert "backfill-provenance:" in makefile
    line = next(row for row in makefile.splitlines()
                if row.startswith("backfill-provenance:"))
    assert "##" in line and "dry-run" in line.lower()


# ------------------------------------------- what a promotion now always records ----


def test_every_promotion_records_an_answer_to_the_scale_question() -> None:
    """Derived from the RUN being promoted, never typed at the call site — so a
    hand-configured fit records the honest no-op and a refit from a search carries
    the divisor a later retrain needs."""
    run_source = (REPO / "src/taxi_mlops/training/run.py").read_text()
    tree = ast.parse(run_source)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_promote")
    promote = next(n for n in ast.walk(fn)
                   if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "promote")
    tags = next(kw for kw in promote.keywords if kw.arg == "version_tags")
    segment = ast.get_source_segment(run_source, tags.value) or ""
    assert "_search_scale_tags_of" in segment, (
        "the version must answer the scale question at promotion time (F-048)")
    assert str(SNIPER_ROWS) not in segment and "6598113" not in segment


def test_the_refit_writes_the_scale_at_fit_time() -> None:
    """`scripts/automl_refit.py` is where a sampled search becomes a full-data run,
    so it is the one place that knows the divisor while the run is being created."""
    source = (REPO / "scripts" / "automl_refit.py").read_text()
    assert "registry_mod.SEARCH_SCALE_ROWS" in source
    tree = ast.parse(source)
    called = {node.func.attr for node in ast.walk(tree)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert "set_model_version_tag" not in called, (
        "the refit writes a RUN tag; it has no version to tag and no business making one")
