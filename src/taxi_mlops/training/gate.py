"""The promotion gate — the one place this program is allowed to say "no".

Four properties are deliberate, and none of them is a knob:

1. **It judges on the HOLDOUT split and refuses to judge on anything else.**
   `configs/train.yaml: gate.holdout_split` names it, and `decide()` raises if it
   is handed metrics from another split. Early stopping reads val; a model that
   was early-stopped against the month it is then judged on has been fitted to
   that month once already, and the gate would be measuring its own training
   signal. The MLE charter refuses "touching the promotion gate or the holdout
   month's role in it" — this module is that refusal written down.

2. **The bar is the HONEST floor, re-derived in the same run.** The gate compares
   against `baseline-group-median` as computed by `taxi_mlops.training.evaluate`
   on the same rows in the same invocation, never against a number typed into a
   config. A floor quoted from a document drifts away from the data silently; a
   floor recomputed every run cannot. The flattering constant-median floor is
   named in the config comment as explicitly NOT the bar (CLAUDE.md).

3. **Both numbers are printed either way.** A gate that prints "REFUSED" without
   the two numbers it compared teaches the reader to trust it or to ignore it,
   and they will pick one at random. `verdict_lines()` prints challenger, floor,
   what was required and what was observed, on a pass and on a refusal alike.

4. **It may be tightened here; it may only be LOOSENED by a PO fork** (CLAUDE.md:
   "Gates/SLOs/thresholds loosen only via PO fork"). That is a process rule, so
   this file cannot enforce it — but the margin lives in config with its reason
   beside it, so loosening it is a visible diff rather than an edit nobody reads.

The decision is a pure function of two `Metrics` objects and the config: no
MLflow, no filesystem, no cluster. Promotion — the part with side effects — is
`taxi_mlops.training.registry`'s, and it only ever runs on a decision that
passed.
"""

from __future__ import annotations

from dataclasses import dataclass

from .evaluate import Metrics


class GateError(RuntimeError):
    """The gate was asked to judge something it must not judge.

    Not a refusal — a refusal is a `Decision` with `passed=False`, which is a
    normal, printable outcome. This is the gate declining to produce a verdict at
    all, because producing one would mean the comparison was meaningless.
    """


@dataclass(frozen=True)
class Check:
    """One named condition, its verdict, and the numbers it read."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class Decision:
    """The verdict, with everything needed to re-derive it by hand."""

    challenger: str
    floor: str
    split: str
    n: int
    challenger_mae: float
    floor_mae: float
    required_pct: float
    observed_pct: float
    challenger_within: float
    floor_within: float
    tolerance_minutes: float
    checks: tuple[Check, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def verdict(self) -> str:
        return "PROMOTE" if self.passed else "REFUSE"

    def as_mlflow(self) -> dict[str, float]:
        """The verdict travels WITH the run, so a number in a slide can be traced."""
        return {
            "gate_challenger_mae": self.challenger_mae,
            "gate_floor_mae": self.floor_mae,
            "gate_required_pct": self.required_pct,
            "gate_observed_pct": self.observed_pct,
            "gate_challenger_within_rate": self.challenger_within,
            "gate_floor_within_rate": self.floor_within,
            "gate_passed": 1.0 if self.passed else 0.0,
        }


def improvement_pct(challenger_mae: float, floor_mae: float) -> float:
    """How much lower the challenger's KPI-09 is, in percent OF THE FLOOR.

    Percent of the floor and not of the challenger: the floor is the fixed
    reference both sides of every future comparison share, and expressing the
    margin against the moving number would make the same absolute gain read
    differently depending on who won.
    """
    if floor_mae <= 0:
        raise GateError(f"floor MAE is {floor_mae} — nothing can be a percentage of it")
    return 100.0 * (floor_mae - challenger_mae) / floor_mae


def decide(challenger: Metrics, floor: Metrics, cfg: dict) -> Decision:
    """Judge one challenger against the floor. Pure; raises only on a bad comparison."""
    holdout = cfg["holdout_split"]
    for role, metrics in (("challenger", challenger), ("floor", floor)):
        if metrics.split != holdout:
            raise GateError(
                f"the gate judges on {holdout!r} only, and was handed {role} metrics "
                f"from {metrics.split!r}. Early stopping reads val (configs/train.yaml: "
                "model.early_stopping_rounds), so judging on val would score a model "
                "against a month it has already been fitted to."
            )
    if floor.contender != cfg["floor"]:
        raise GateError(
            f"the bar is {cfg['floor']!r} and the gate was handed "
            f"{floor.contender!r}. The flattering constant-median floor is NOT the "
            "bar (CLAUDE.md); passing it in here would make every model look good."
        )
    if challenger.n != floor.n:
        raise GateError(
            f"challenger scored {challenger.n:,} rows and the floor {floor.n:,}. "
            "Two numbers computed over different populations are not a comparison."
        )
    if challenger.tolerance_minutes != floor.tolerance_minutes:
        raise GateError(
            f"KPI-10 tolerances differ: {challenger.tolerance_minutes} vs "
            f"{floor.tolerance_minutes} minutes."
        )

    required = float(cfg["min_improvement_pct"])
    observed = improvement_pct(challenger.mae, floor.mae)

    checks = [
        Check(
            name="KPI-09 margin over the honest floor",
            passed=observed >= required,
            detail=(
                f"{challenger.mae:.4f} vs {floor.mae:.4f} min = {observed:+.2f}% "
                f"(required >= {required:.2f}%)"
            ),
        )
    ]
    if cfg.get("require_no_kpi10_regression", False):
        # A mean can improve while the rider-facing rate gets worse: KPI-09 is an
        # average over ~6M rows and KPI-10 is what a rider actually experiences
        # ("was my quote right?"). A challenger that trades the second for the
        # first has optimised the number we report and degraded the number we
        # promise, and only one of those is on the M5 SLO.
        regression = floor.within_tolerance_rate - challenger.within_tolerance_rate
        checks.append(
            Check(
                name=f"KPI-10 (within {challenger.tolerance_minutes:g} min) does not regress",
                passed=challenger.within_tolerance_rate >= floor.within_tolerance_rate,
                detail=(
                    f"{challenger.within_tolerance_rate:.3f}% vs {floor.within_tolerance_rate:.3f}%"
                    f" = {-regression:+.3f} points"
                ),
            )
        )

    return Decision(
        challenger=challenger.contender,
        floor=floor.contender,
        split=holdout,
        n=challenger.n,
        challenger_mae=challenger.mae,
        floor_mae=floor.mae,
        required_pct=required,
        observed_pct=observed,
        challenger_within=challenger.within_tolerance_rate,
        floor_within=floor.within_tolerance_rate,
        tolerance_minutes=challenger.tolerance_minutes,
        checks=tuple(checks),
    )


def verdict_lines(decision: Decision) -> str:
    """The transcript. Both numbers, on a pass and on a refusal alike."""
    lines = [
        f"[gate] holdout   : {decision.split} — {decision.n:,} rows, untouched by "
        "training and by selection",
        f"[gate] challenger: {decision.challenger:<28} KPI-09 {decision.challenger_mae:.4f} min"
        f"  ·  KPI-10 {decision.challenger_within:.3f}%",
        f"[gate] floor     : {decision.floor:<28} KPI-09 {decision.floor_mae:.4f} min"
        f"  ·  KPI-10 {decision.floor_within:.3f}%",
        f"[gate] required  : KPI-09 at least {decision.required_pct:.2f}% below the floor",
        f"[gate] observed  : KPI-09 {decision.observed_pct:+.2f}% vs the floor",
    ]
    for check in decision.checks:
        lines.append(f"[gate]   {'ok  ' if check.passed else 'FAIL'} {check.name}: {check.detail}")
    lines.append(f"[gate] VERDICT   : {decision.verdict}")
    if not decision.passed:
        lines.append(
            "[gate] Nothing was registered and no alias moved. A refused challenger "
            "leaves the registry exactly as it found it."
        )
    return "\n".join(lines)
