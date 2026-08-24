"""The F-016 option-B replay wall, asked BEFORE the edit — a READER, it changes nothing.

`docs/milestones/M9_EPILOGUE_KICKOFF.md` M9-S6 charters a PO-sanctioned gate
edit: the incumbent KPI-09 condition gains a **>= 0.50%** margin (F-016 option
B, AWAITING_PO 2026-08-18-1, answered 2026-08-24). It also names the wall that
edit must clear first, and the rule for hitting it:

    "verify-m2 §2, verify-m3 §5 and verify-m7's retrain leg all REPLAY recorded
     verdicts through gate.decide as it exists on disk. ... If any replay flips,
     STOP — that is a finding and a PO question, never an edit to the replay."

The kickoff did that arithmetic on THREE numbers (M2's transcripts carry no
incumbent; M3-S5's winner at +0.63%; M7-S4's refusal at -0.03%) and concluded
every replay survives. This script asks the same question of **every recorded
verdict the two live replay legs actually feed through `gate.decide`** — which
is more verdicts than three, because verify-m3 §5 replays all FIVE bake-off
contenders and verify-m2 §2 parses `docs/promotion_gate_m3.md` as well as the
M2 document.

Why a script and not a paragraph: the answer is a claim about what a gate would
do, and a claim about a gate is worth what re-running it costs. This is
seconds, needs no cluster, no registry, no fit, and it is the artifact the
AWAITING_PO entry cites.

It deliberately does NOT edit `configs/train.yaml` and does not call
`registry`. It simulates option B by taking the real `decide()` verdict for
every condition except the incumbent KPI-09 one, and applying the margin to
that one itself — at `INCUMBENT_MAE_DECIMALS`, the precision an incumbent's
number exists at (gotcha #42; comparing a 17-figure re-measurement against a
4-decimal tag is how the gate once refused the champion against itself).

    uv run python scripts/f016_replay_probe.py [--margin 0.50] [--json PATH]

Exit 0 whatever it finds: it is a reader, and the verdict about the verdicts
belongs to whoever reads it. `flips` in the JSON is the answer.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from taxi_mlops.training.evaluate import Metrics
from taxi_mlops.training.gate import (
    INCUMBENT_MAE_DECIMALS,
    Incumbent,
    decide,
    improvement_pct,
)
from taxi_mlops.training.run import load_train_config

BAKEOFF = Path("automation/runs/m3s5/bakeoff.json")
TRANSCRIPTS = (Path("docs/promotion_gate_m2.md"), Path("docs/promotion_gate_m3.md"))

#: The two conditions the incumbent contributes. Only the KPI-09 one gains a
#: margin under option B — the PO's answer says "KPI-10 non-regression
#: unchanged" — so the KPI-10 incumbent check is left exactly as `decide()`
#: computed it.
_INCUMBENT_MAE_CHECK = "KPI-09 does not regress against the serving champion"

_LINE = re.compile(
    r"\[gate\] (challenger|floor)\s*: (\S+)\s+KPI-09 ([\d.]+) min\s+·\s+KPI-10 ([\d.]+)%"
)
_INC = re.compile(
    r"\[gate\] incumbent\s*: version (\S+)\s+KPI-09 ([\d.]+) min\s+·\s+KPI-10 ([\d.]+)%"
)


def _metrics(name: str, mae: float, within: float, n: int, split: str) -> Metrics:
    return Metrics(
        contender=name,
        split=split,
        n=n,
        mae=mae,
        within_tolerance_rate=within,
        tolerance_minutes=5.0,
        rmse=0.0,
        median_ae=0.0,
        p90_ae=0.0,
    )


def under_margin(
    challenger: Metrics,
    floor: Metrics,
    cfg: dict,
    incumbent: Incumbent | None,
    margin: float,
) -> tuple[str, float | None]:
    """What `decide()` would return with the incumbent KPI-09 margin armed.

    Every other condition is taken from the REAL decision, so a difference in
    the answer is attributable to the margin and to nothing else.
    """
    decision = decide(challenger, floor, cfg, incumbent=incumbent)
    if incumbent is None:
        return decision.verdict, None
    others = all(
        check.passed
        for check in decision.checks
        if not check.name.startswith(_INCUMBENT_MAE_CHECK)
    )
    pct = improvement_pct(round(challenger.mae, INCUMBENT_MAE_DECIMALS), incumbent.mae)
    return ("PROMOTE" if (others and pct >= margin) else "REFUSE"), pct


def _bakeoff_rows(cfg: dict, margin: float) -> list[dict]:
    record = json.loads(BAKEOFF.read_text(encoding="utf-8"))
    holdout = record["holdout_split"]
    inc_rec = record["incumbent"]
    floor = next(c for c in record["contenders"] if c["track"] == "floor")
    rows = []
    for contender in record["contenders"]:
        n = contender["test_rows"]
        incumbent = Incumbent(
            version=inc_rec["version"],
            mae=inc_rec["mae"],
            within_tolerance_rate=inc_rec["within_tolerance_rate"],
            split=holdout,
            source=f"the bake-off record in {BAKEOFF}",
        )
        verdict, pct = under_margin(
            _metrics(
                contender["name"],
                contender["test_mae"],
                contender["test_within_rate"],
                n,
                holdout,
            ),
            _metrics(floor["name"], floor["test_mae"], floor["test_within_rate"], n, holdout),
            dict(cfg, floor=floor["name"]),
            incumbent,
            margin,
        )
        rows.append(
            {
                "leg": "verify-m3 §5",
                "source": str(BAKEOFF),
                "label": contender["label"],
                "name": contender["name"],
                "recorded": contender["verdict"],
                "under_margin": verdict,
                "vs_incumbent_pct": pct,
                "challenger_mae": contender["test_mae"],
                "incumbent_mae": inc_rec["mae"],
            }
        )
    return rows


def _transcript_rows(cfg: dict, margin: float) -> list[dict]:
    holdout = cfg["holdout_split"]
    rows: list[dict] = []
    for doc in TRANSCRIPTS:
        text = doc.read_text(encoding="utf-8")
        n = int(re.search(r"holdout\s+: \w+ — ([\d,]+) rows", text).group(1).replace(",", ""))
        current: dict = {}
        for line in text.splitlines():
            line_match, inc_match = _LINE.match(line), _INC.match(line)
            if inc_match:
                current["incumbent"] = (
                    inc_match.group(1),
                    float(inc_match.group(2)),
                    float(inc_match.group(3)),
                )
            elif line_match:
                current[line_match.group(1)] = (
                    line_match.group(2),
                    float(line_match.group(3)),
                    float(line_match.group(4)),
                )
            elif line.startswith("[gate] VERDICT"):
                recorded = line.split(":", 1)[1].strip()
                if {"challenger", "floor"} <= current.keys():
                    cn, cm, cw = current["challenger"]
                    fn, fm, fw = current["floor"]
                    raw = current.get("incumbent")
                    incumbent = (
                        None
                        if raw is None
                        else Incumbent(
                            version=raw[0],
                            mae=raw[1],
                            within_tolerance_rate=raw[2],
                            split=holdout,
                            source=f"the transcript in {doc}",
                        )
                    )
                    verdict, pct = under_margin(
                        _metrics(cn, cm, cw, n, holdout),
                        _metrics(fn, fm, fw, n, holdout),
                        dict(cfg, floor=fn),
                        incumbent,
                        margin,
                    )
                    rows.append(
                        {
                            "leg": "verify-m2 §2",
                            "source": str(doc),
                            "label": cn,
                            "name": cn,
                            "recorded": recorded,
                            "under_margin": verdict,
                            "vs_incumbent_pct": pct,
                            "challenger_mae": cm,
                            "incumbent_mae": None if raw is None else raw[1],
                        }
                    )
                current = {}
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--margin",
        type=float,
        default=0.50,
        help="the incumbent KPI-09 margin to simulate, in percent (F-016 option B: 0.50)",
    )
    parser.add_argument("--json", type=Path, default=None, help="write the rows here")
    args = parser.parse_args(argv)

    cfg = load_train_config("configs/train.yaml")["gate"]
    rows = _bakeoff_rows(cfg, args.margin) + _transcript_rows(cfg, args.margin)

    print(
        f"[f016] simulating an incumbent KPI-09 margin of >= {args.margin:.2f}% against every "
        f"RECORDED verdict the live replay legs feed through gate.decide."
    )
    print("[f016] nothing is edited; configs/train.yaml: gate is read, never written.\n")
    last_leg = None
    for row in rows:
        if row["leg"] != last_leg or row["source"] != last_leg:
            print(f"  --- {row['leg']}  ·  {row['source']}")
            last_leg = row["source"]
        pct = row["vs_incumbent_pct"]
        margin_note = "no incumbent recorded" if pct is None else f"vs incumbent {pct:+.4f}%"
        flag = "FLIP" if row["under_margin"] != row["recorded"] else "ok  "
        print(
            f"  {flag} {row['label']:<30} recorded={row['recorded']:<8} "
            f"under_margin={row['under_margin']:<8} {margin_note}"
        )

    flips = [r for r in rows if r["under_margin"] != r["recorded"]]
    print()
    print(f"[f016] {len(rows)} recorded verdict(s) replayed · {len(flips)} FLIP(S)")
    for row in flips:
        print(
            f"[f016]   FLIP {row['label']} ({row['source']}): recorded {row['recorded']}, "
            f"under a >= {args.margin:.2f}% margin {row['under_margin']} "
            f"— challenger {row['challenger_mae']:.4f} vs incumbent {row['incumbent_mae']:.4f} min "
            f"= {row['vs_incumbent_pct']:+.4f}%"
        )
    if flips:
        print(
            "[f016] the kickoff's rule: a flipped replay is a FINDING and a PO question, "
            "never an edit to the replay."
        )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "margin_pct": args.margin,
                    "gate_on_disk": {
                        "min_improvement_pct": cfg["min_improvement_pct"],
                        "floor": cfg["floor"],
                        "holdout_split": cfg["holdout_split"],
                        "require_no_kpi10_regression": cfg.get("require_no_kpi10_regression"),
                        "incumbent_min_improvement_pct": cfg.get("incumbent_min_improvement_pct"),
                    },
                    "replayed": len(rows),
                    "flips": len(flips),
                    "rows": rows,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"[f016] wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
