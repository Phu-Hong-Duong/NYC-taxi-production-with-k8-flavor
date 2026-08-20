#!/usr/bin/env python
"""Run Evidently beside our SQL PSI and record whether the two instruments agree.

M7-S3. A READER: it computes and it writes a record. It pushes nothing, deploys
nothing, and touches no alert. See `taxi_mlops.monitoring.drift_evidently` for
why Evidently is the second witness and not the first.

**Agreement is about the RANKING and the VERDICTS, never about the numbers.**
PSI and Jensen-Shannon distance are different statistics on different scales;
demanding they match numerically would be demanding that two instruments be the
same instrument, which would make the second one worthless.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from taxi_mlops.monitoring import drift_evidently  # noqa: E402
from taxi_mlops.monitoring.drift import compute_drift  # noqa: E402

RECORD_DIR = REPO_ROOT / "automation" / "runs" / "m7-drift"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--months", nargs="+", default=["2020-01", "2020-03"])
    args = parser.parse_args(argv)

    out: dict[str, dict] = {}
    for month in args.months:
        ours = compute_drift(month)
        theirs = drift_evidently.run(month)
        our_psi = {c.column: c.psi for c in ours.columns}
        our_rank = [k for k, _ in sorted(our_psi.items(), key=lambda kv: -kv[1])]
        their_rank = [k for k, _ in sorted(theirs.scores.items(), key=lambda kv: -kv[1])]

        print(f"[witness] {month}  (evidently {theirs.evidently_version}, "
              f"{theirs.sample_rows:,} sampled rows/side, seed {theirs.sample_seed})")
        header = f"{'column':<24s} {'our PSI':>10s} {'evidently':>12s} {'their verdict':>15s}"
        print(f"[witness]   {header}")
        for column in our_rank:
            print(
                f"[witness]   {column:<24s} {our_psi[column]:10.4f} "
                f"{theirs.scores.get(column, float('nan')):12.4f} "
                f"{('DRIFTED' if theirs.drifted.get(column) else 'not drifted'):>15s}"
            )
        print(f"[witness]   our ranking       : {our_rank}")
        print(f"[witness]   evidently ranking : {their_rank}")
        print(
            f"[witness]   evidently's dataset drift share: {theirs.dataset_drift_share:.4f} "
            f"(its own defaults, not our bar)"
        )
        agree_top = bool(our_rank and their_rank and our_rank[0] == their_rank[0])

        # THE SUBSTANTIVE COMPARISON, and it is not the ranking.
        #
        # Ranking six numbers that are all in the noise is a coin toss, so
        # "AGREE on the largest mover" is reported but is NOT what agreement
        # means here. What means something is the VERDICT SET: which columns
        # each instrument, at its own bar, calls drifted. That is the question
        # an alert asks, and it is the one the two can meaningfully both answer.
        ours_flagged = {c for c, v in our_psi.items() if v >= 0.10}  # our bar, §8.3
        theirs_flagged = {c for c, v in theirs.drifted.items() if v}
        ours_inputs = {c for c in ours_flagged if c != "trip_duration_minutes"}
        theirs_inputs = {c for c in theirs_flagged if c != "trip_duration_minutes"}
        ours_text = sorted(ours_flagged) or "(none)"
        theirs_text = sorted(theirs_flagged) or "(none)"
        print(f"[witness]   columns past OUR bar (PSI >= 0.10) : {ours_text}")
        print(f"[witness]   columns past EVIDENTLY's own bar   : {theirs_text}")
        verdict = "AGREE" if ours_inputs == theirs_inputs else "DISAGREE"
        print(
            f"[witness]   on the question the ALERT asks — did any INPUT column drift? — "
            f"the two instruments {verdict}: "
            f"ours {sorted(ours_inputs) or '(none)'} vs theirs {sorted(theirs_inputs) or '(none)'}"
        )
        print(
            f"[witness]   (they {'AGREE' if agree_top else 'differ'} on the largest mover, "
            "which is a ranking of numbers in the noise and is reported, not relied on)"
        )
        print()
        out[month] = {
            "our_psi": our_psi,
            "our_ranking": our_rank,
            "evidently": theirs.to_dict(),
            "evidently_ranking": their_rank,
            "agree_on_largest_mover": agree_top,
            "ours_flagged": sorted(ours_flagged),
            "evidently_flagged": sorted(theirs_flagged),
            "agree_on_input_drift_verdict": ours_inputs == theirs_inputs,
        }

    path = RECORD_DIR / "second_witness.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(f"[witness] record -> {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
