"""Which incumbent margin a RECORDED verdict was taken against (F-016 / F-068).

M9-S10 tightened the gate: the incumbent KPI-09 condition, which had been plain
non-regression since M3-S1 (F-011), now demands a margin
(`configs/train.yaml: gate.incumbent_min_improvement_pct`, sanctioned at 0.50%
by the PO at AWAITING_PO 2026-08-24-4). Three milestone gates REPLAY recorded
verdicts through `gate.decide` **as it exists on disk right now** — that is what
makes them evidence about today's gate rather than about a transcript — and a
tightening therefore arrives at those legs as a threat: nine recorded verdicts
were taken under a bar that no longer exists, and two of them (`champion v1` at
M3-S5 and `lightgbm-v1` in `docs/promotion_gate_m3.md`, both a challenger judged
against ITSELF at exactly +0.0000%) flip from PROMOTE to REFUSE under any
positive margin at all. `automation/runs/m9-f016/replay-wall.json` measured that
before the edit; it is the record this module reads.

The PO's answer was **era-aware replay**: *"a verdict is replayed against the bar
it was actually taken against, or it is not a replay."* That sentence is not new
here — it is `verify-m2` §2's own comment about the FLOOR, written at M3-S1 when
the floor's name changed under two committed transcripts and the legs learned to
take the floor from the block instead of from the config. This module is the same
idea for the margin, with one extra obligation the floor case did not have:

**an absent margin must never resolve to a convenient one.** Zero is the loosest
possible bar, so "this verdict records no margin, so assume none was in force" is
exactly the inference that would let a future verdict, taken under a margin and
recorded carelessly, be replayed against nothing and pass. So the pre-B era is an
**ENUMERATED SET**, frozen at nine rows keyed on (leg, source, label), and a
verdict that is neither in it nor carries its own recorded margin **raises**
(F-048's rule: an unresolvable value fails loudly rather than resolving to
something that happens to work).

The inference from absence is therefore confined, permanently, to those nine
rows — because from M9-S10 on every verdict carries the margin it was judged
under, in `Decision.incumbent_required_pct`, in `as_mlflow()`, on the promoted
version's tags, in the retrain record, in the pipeline manifest, and in the
transcript line `verdict_lines()` prints (which is the form the replay legs
parse). `MARGIN_RE` here and that line in `gate.verdict_lines` are twins —
change one, change the other.

Nothing in this module judges anything. It answers one question — *what bar was
this verdict taken against?* — and refuses to guess.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path

#: The margin in force BEFORE M9-S10: none. The incumbent condition existed
#: (F-011, M3-S1) and was plain non-regression, so a challenger that merely tied
#: the champion passed it. Every verdict in the frozen set below was taken here.
PRE_B_MARGIN_PCT = 0.0

#: The margin the PO sanctioned at AWAITING_PO 2026-08-24-4 (answered
#: 2026-08-25) and this story landed. It is the FLOOR of the monotonic check
#: below, not a value anything reads to decide: `gate.decide` takes its margin
#: from `configs/train.yaml` and only from there (F-013 — one home). This
#: constant exists so that lowering the config below the sanctioned number is a
#: RED gate rather than a diff nobody read.
SANCTIONED_MARGIN_PCT = 0.50

#: The enumerated set. Measured BEFORE the edit — which is what makes it a
#: measurement of the pre-B era rather than a list assembled to make today's
#: gate green — and tracked, so a row added to it is a diff a reviewer sees
#: (F-029's option A, landed at M5-S1). Its producer, `scripts/
#: f016_replay_probe.py`, was RETIRED at CU-S1 (2026-08-31): the record is the
#: artifact and re-running the probe against today's gate would not reproduce
#: it anyway. Restore is `git`, never a re-run.
FROZEN_RECORD = Path("automation/runs/m9-f016/replay-wall.json")


class GateEraError(RuntimeError):
    """A recorded verdict cannot be attributed to an era.

    Not a refusal and not a failed replay: it is the replay declining to run,
    because running it would mean choosing a bar for a verdict that never
    declared one. The two ways out are both edits a human makes deliberately —
    the verdict starts recording its margin, or the row joins the frozen set
    with an argument beside it.
    """


def frozen_margins(record: Path | str = FROZEN_RECORD) -> dict[tuple[str, str, str], float]:
    """The pre-B verdicts, keyed exactly as the probe recorded them.

    Reads the record rather than restating it: a second copy of nine rows in
    Python would be a twin of a tracked JSON file, and the twin is the one that
    would drift. A missing record RAISES — an empty enumeration would make every
    lookup fall through to the loud failure below, which reads like nine
    findings when it is one missing file.
    """
    path = Path(record)
    if not path.exists():
        raise GateEraError(
            f"the frozen pre-B verdict set is missing: {path}. It is a TRACKED record, "
            "measured before the F-016 margin landed, and without it no recorded verdict "
            "from before M9-S10 can be attributed to the bar it was taken against. "
            f"Restore it from git — `git checkout -- {path}` — and do not try to "
            "regenerate it: nothing in this repository can, and a set produced against "
            "today's gate would not be a measurement of the old one."
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        (row["leg"], row["source"], row["label"]): PRE_B_MARGIN_PCT
        for row in payload["rows"]
    }


def in_force_margin(
    leg: str,
    source: str,
    label: str,
    *,
    recorded: float | None = None,
    record: Path | str = FROZEN_RECORD,
) -> float:
    """The incumbent margin this verdict was JUDGED under, or a raise.

    `recorded` is the margin the verdict declares about itself — parsed off a
    transcript, or read out of a record's own field. It wins whenever it exists,
    because a verdict that says what bar it was taken against is the only kind
    that needs no inference at all. Only when it is absent does the enumerated
    pre-B set get consulted, and only a key IN that set resolves.
    """
    if recorded is not None:
        return float(recorded)
    frozen = frozen_margins(record)
    key = (leg, source, label)
    if key in frozen:
        return frozen[key]
    raise GateEraError(
        f"verdict {label!r} from {source} (replayed by {leg}) records no incumbent margin "
        f"and is not one of the {len(frozen)} frozen pre-B verdicts in {Path(record)}. "
        "It cannot be replayed: assuming no margin was in force would replay it against "
        "the LOOSEST possible bar, which is exactly the inference F-016's era-aware "
        "landing exists to prevent (F-048 — an unresolvable value never resolves to "
        "something convenient). Either the verdict must record its own margin "
        "(gate.verdict_lines prints it from M9-S10 on), or this row belongs in the "
        "frozen set with the argument for it written beside it."
    )


#: The transcript form. TWIN of the line `gate.verdict_lines` prints — the legs
#: parse what the gate writes, so a change to either without the other turns a
#: recorded margin back into an absence, which is the failure this whole module
#: is about.
MARGIN_RE = re.compile(
    r"\[gate\] incumbent bar\s*:\s*KPI-09 at least ([\d.]+)% below the serving champion"
)


def parse_recorded_margin(lines: Iterable[str]) -> float | None:
    """The margin a transcript block declares, or None if it declares none.

    None is a legitimate answer and NOT a default: it means "this verdict says
    nothing about its bar", which is precisely the question `in_force_margin`
    then answers from the enumerated set or refuses to answer at all.
    """
    for line in lines:
        found = MARGIN_RE.search(line)
        if found:
            return float(found.group(1))
    return None


def assert_margin_never_decreased(configured: float, observed: Iterable[float]) -> float:
    """The monotonic check: the bar on disk may rise, and may never fall.

    Separate from, and deliberately not weakened by, the era-aware replays.
    Era-awareness exists so that HISTORY replays correctly; on its own it would
    also make a loosening replay correctly, because every historical verdict
    would still be judged against its own old bar while the live gate quietly
    got easier. So the margin in `configs/train.yaml` must be at least the
    largest margin any recorded verdict was taken against, and at least the
    number the PO sanctioned — the frozen nine contribute 0, and
    `SANCTIONED_MARGIN_PCT` is the floor from M9-S10 on.

    Returns the floor it required, so a caller can print it. Raises rather than
    returning a verdict: this is a law, and CLAUDE.md's "gates loosen only via a
    PO fork" is the process rule it enforces mechanically.
    """
    floor = max([SANCTIONED_MARGIN_PCT, *(float(value) for value in observed)])
    if float(configured) < floor:
        raise GateEraError(
            f"the incumbent margin on disk is {float(configured):.2f}% and the largest "
            f"margin a recorded verdict was taken against is {floor:.2f}%. A gate may be "
            "TIGHTENED by whoever can argue for it and LOOSENED only by a PO fork "
            "(CLAUDE.md); lowering it here would also re-open the two verdicts F-068 "
            "recorded — replaying history against its own era is not a licence for the "
            "live bar to fall."
        )
    return floor
