"""The era table: what a recorded verdict was judged under, and when it refuses to say.

Two properties carry this module, and only one of them is about the nine rows.

The first is that the enumeration RESOLVES the history it was built from — all
nine frozen verdicts, including the two that flip, and including the two that
carry no incumbent at all.

The second is the one that makes era-awareness safe rather than merely
convenient: a verdict that is neither enumerated nor self-describing must RAISE.
Zero is the loosest bar there is, so the failure mode of a permissive default is
not "a slightly wrong replay" — it is a future verdict, taken under a margin and
recorded carelessly, being replayed against nothing at all and passing. That is
F-048's rule (`_search_scale`'s "I cannot see the records" versus "there is
nothing to see"), applied to a bar instead of a divisor.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from taxi_mlops.training import gate_eras

REPO = Path(__file__).resolve().parents[2]
RECORD = REPO / "automation/runs/m9-f016/replay-wall.json"


def _record() -> dict:
    assert RECORD.exists(), (
        f"{RECORD.relative_to(REPO)} is missing. It is the TRACKED enumeration of every "
        "verdict taken before the F-016 margin landed (M9-S10) — without it no historical "
        "verdict can be replayed against the bar it was actually taken against, and three "
        "milestone gates replay nine of them. Restore it from git; regenerating it against "
        "today's gate would not be a measurement of the old one."
    )
    return json.loads(RECORD.read_text(encoding="utf-8"))


# ------------------------------------------------------- the frozen enumeration ---
def test_the_frozen_set_is_the_probe_s_nine_rows_and_every_one_is_pre_B():
    payload = _record()
    frozen = gate_eras.frozen_margins()
    assert len(frozen) == payload["replayed"] == 9
    assert set(frozen.values()) == {gate_eras.PRE_B_MARGIN_PCT}
    assert payload["gate_on_disk"]["incumbent_min_improvement_pct"] is None, (
        "the record was written while the margin did not exist — that is what makes it a "
        "measurement of the pre-B era rather than a list assembled after the fact"
    )


def test_the_two_flips_F_068_found_are_IN_the_frozen_set():
    """The whole point of option (b): the rows that would flip are the rows the
    enumeration covers. If either fell outside it, the era logic would resolve
    everything except the two verdicts it exists for."""
    payload = _record()
    flips = [row for row in payload["rows"] if row["recorded"] != row["under_margin"]]
    assert len(flips) == payload["flips"] == 2
    frozen = gate_eras.frozen_margins()
    for row in flips:
        assert (row["leg"], row["source"], row["label"]) in frozen
        assert row["recorded"] == "PROMOTE" and row["under_margin"] == "REFUSE"
        assert row["vs_incumbent_pct"] == 0.0, "both flips are the identity case, exactly"


def test_every_frozen_row_resolves_to_the_pre_B_margin():
    for row in _record()["rows"]:
        assert (
            gate_eras.in_force_margin(row["leg"], row["source"], row["label"])
            == gate_eras.PRE_B_MARGIN_PCT
        )


# ------------------------------------------------------------ the loud refusals ---
def test_an_unenumerated_verdict_with_no_recorded_margin_RAISES():
    with pytest.raises(gate_eras.GateEraError) as raised:
        gate_eras.in_force_margin(
            "verify-m3 §5", "automation/runs/m3s5/bakeoff.json", "a-contender-nobody-froze"
        )
    message = str(raised.value)
    assert "a-contender-nobody-froze" in message and "LOOSEST possible bar" in message


def test_a_verdict_that_records_its_own_margin_needs_no_enumeration_at_all():
    """The permanent exit from inference-by-absence: from M9-S10 on every
    verdict carries its bar, so the frozen set never has to grow."""
    assert (
        gate_eras.in_force_margin("some-future-leg", "some/future/record.json", "v9", recorded=0.5)
        == 0.5
    )
    assert (
        gate_eras.in_force_margin("some-future-leg", "some/future/record.json", "v9", recorded=0.0)
        == 0.0
    ), "a recorded ZERO is a statement, and it must not be mistaken for an absence"


def test_a_missing_record_raises_ONCE_rather_than_nine_times():
    """A missing enumeration is one broken file, not nine unattributable
    verdicts — and the two read as very different findings to whoever is
    holding the red gate."""
    with pytest.raises(gate_eras.GateEraError) as raised:
        gate_eras.frozen_margins(REPO / "automation/runs/m9-f016/does-not-exist.json")
    assert "TRACKED record" in str(raised.value)


# ------------------------------------------------------------ parsing a transcript ---
def test_a_transcript_with_no_margin_line_reports_None_and_not_zero():
    assert gate_eras.parse_recorded_margin(
        [
            "[gate] incumbent : version 1  KPI-09 3.2608 min  ·  KPI-10 81.480%   [version tags]",
            "[gate] VERDICT   : PROMOTE",
        ]
    ) is None


def test_the_incumbent_line_is_not_mistaken_for_the_bar_line():
    """They differ by one word and the legs parse both. A regex loose enough to
    match the wrong one would read a KPI-09 MAE as a percentage."""
    lines = [
        "[gate] incumbent : version 2  KPI-09 3.2403 min  ·  KPI-10 81.577%   [version tags]",
        "[gate] incumbent bar: KPI-09 at least 0.50% below the serving champion (F-016)",
    ]
    assert gate_eras.parse_recorded_margin(lines[:1]) is None
    assert gate_eras.parse_recorded_margin(lines) == 0.50


# ----------------------------------------------------------- the monotonic check ---
def test_the_sanctioned_margin_is_the_floor_and_the_config_meets_it():
    from taxi_mlops.data.config import load_yaml

    configured = float(load_yaml("configs/train.yaml")["gate"]["incumbent_min_improvement_pct"])
    assert configured >= gate_eras.SANCTIONED_MARGIN_PCT
    assert gate_eras.assert_margin_never_decreased(configured, []) == (
        gate_eras.SANCTIONED_MARGIN_PCT
    )


def test_a_margin_below_the_sanctioned_one_is_a_RAISE_not_a_warning():
    with pytest.raises(gate_eras.GateEraError) as raised:
        gate_eras.assert_margin_never_decreased(0.10, [])
    assert "PO fork" in str(raised.value)


def test_the_check_ratchets_on_what_verdicts_were_ACTUALLY_taken_against():
    """Era-awareness alone would let the live bar fall while history kept
    replaying correctly against its own old bars. This is the half that does not
    move: once a verdict has been taken at 1.00%, 0.50% is a loosening even
    though it is the sanctioned number."""
    assert gate_eras.assert_margin_never_decreased(1.00, [0.50, 1.00]) == 1.00
    with pytest.raises(gate_eras.GateEraError):
        gate_eras.assert_margin_never_decreased(gate_eras.SANCTIONED_MARGIN_PCT, [0.50, 1.00])


def test_the_frozen_zeros_cannot_drag_the_ratchet_down():
    """The nine contribute 0, and 0 must not become the floor — `max`, never
    `min`, and the sanctioned number is always in the pool."""
    frozen = list(gate_eras.frozen_margins().values())
    assert gate_eras.assert_margin_never_decreased(
        gate_eras.SANCTIONED_MARGIN_PCT, frozen
    ) == gate_eras.SANCTIONED_MARGIN_PCT
