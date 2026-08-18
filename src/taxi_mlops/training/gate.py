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

M3-S1 added two more, both of them refusals the gate could not make before:

5. **It compares the challenger to what is SERVING, not only to the floor**
   (F-011). The floor answers "is a booster worth its operational cost at all";
   it cannot answer "is this booster better than the one riders are already
   getting". A challenger 4% worse than the champion can clear a floor bar the
   champion cleared by 7%, and before this the alias moved anyway. The incumbent
   arrives as an optional `Incumbent` — optional because the first promotion has
   none, and because M2's recorded verdicts must still replay exactly as they
   were taken. `registry.promote` is what makes "optional" safe: it refuses to
   move an alias whose current version the decision did not consult.

6. **It refuses to issue a verdict for a SAMPLED training run** (F-008), and the
   direction of that error is why: the floor is re-derived from the same training
   data as the challenger, so shrinking train degrades the BAR faster than the
   model. Measured on one month of six, the champion got worse (3.2608 → 3.4207)
   while its margin ROSE from 7.07% to 16.85%. A sampled transcript looks better,
   not worse, which is the shape of trap that gets promoted.

M4-S1 added a seventh, and it is about what the gate is allowed to CLAIM:

7. **The gate does not assert that the holdout is untouched by SELECTION — the
   caller does** (F-018). `verdict_lines()` used to print "untouched by training
   and by selection" on every verdict. Training-purity the gate can vouch for:
   the split is named in config and `decide()` refuses metrics from any other
   one. Selection-purity is a property of the *caller's* process — of how the
   challenger being judged was chosen — and this module cannot see it. It was
   false for the whole of M3-S5: `scripts/bakeoff_m3.py` ranked five contenders
   by their HOLDOUT MAE and handed the winner to this function, which then
   printed that the holdout had not been used for selection. So the strong claim
   must now be EARNED: `holdout_untouched_by_selection` defaults to False and
   prints the weaker sentence that is always true. A caller that knows it chose
   its challenger without reading the holdout says so explicitly, and is the one
   accountable for saying it.

The decision is a pure function of `Metrics` objects and the config: no MLflow,
no filesystem, no cluster. Promotion — the part with side effects — is
`taxi_mlops.training.registry`'s, and it only ever runs on a decision that
passed.
"""

from __future__ import annotations

from collections.abc import Sequence
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
class Incumbent:
    """What is serving right now, as the REGISTRY records it (F-011).

    Deliberately not a `Metrics`: these numbers were not measured in this
    process. They are read back off the champion version's own promotion tags
    (and, for KPI-10 on versions promoted before M3-S1, off that version's run),
    so `source` travels with them — a comparison whose provenance is a guess is
    not a comparison. Assembling this is the caller's job, because it touches the
    registry and this module touches nothing.
    """

    version: str
    mae: float
    within_tolerance_rate: float
    split: str
    source: str


#: The precision the incumbent's numbers EXIST at. `registry.promote` writes
#: `gate_challenger_mae` with 4 decimals and `gate_challenger_within_rate` with 3
#: (run._promote), so an incumbent is known to 6 milliseconds of mean error and a
#: thousandth of a point — no finer. Comparing a 17-significant-figure measurement
#: against a 4-decimal record makes rounding noise read as a regression, which is
#: not a subtle failure: the FIRST full run of this gate refused the champion
#: against its own tag, because a deterministic re-fit reproduced 3.260823… and
#: the tag said 3.2608. Numbers are compared at the resolution they were recorded
#: at; below it there is no evidence either way. Both constants are twins of the
#: format strings in `run._promote` — change one, change the other.
INCUMBENT_MAE_DECIMALS = 4
INCUMBENT_WITHIN_DECIMALS = 3


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
    #: The champion this verdict was taken against, or None when the alias was
    #: unset. `registry.promote` reads this and refuses to move an alias that
    #: points somewhere else — a decision that never saw the incumbent may not
    #: replace it, whether it skipped the comparison or raced with another run.
    incumbent: Incumbent | None = None

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def verdict(self) -> str:
        return "PROMOTE" if self.passed else "REFUSE"

    def as_mlflow(self) -> dict[str, float]:
        """The verdict travels WITH the run, so a number in a slide can be traced."""
        metrics = {
            "gate_challenger_mae": self.challenger_mae,
            "gate_floor_mae": self.floor_mae,
            "gate_required_pct": self.required_pct,
            "gate_observed_pct": self.observed_pct,
            "gate_challenger_within_rate": self.challenger_within,
            "gate_floor_within_rate": self.floor_within,
            "gate_passed": 1.0 if self.passed else 0.0,
        }
        if self.incumbent is not None:
            metrics["gate_incumbent_mae"] = self.incumbent.mae
            metrics["gate_incumbent_within_rate"] = self.incumbent.within_tolerance_rate
        return metrics


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


def assert_full_train_months(actual: Sequence[str], configured: Sequence[str]) -> None:
    """Refuse to judge a run trained on anything but the configured months (F-008).

    A GateError and not a warning, for the same reason `decide` raises on the
    wrong split: the comparison would be meaningless in a direction that flatters.
    The floor is re-derived from the challenger's own training data — deliberately,
    so it cannot drift from a document — which means a sample degrades the BAR as
    well as the model, and the bar faster: its lookup table loses whole cells and
    falls back to the global median, while a booster keeps generalising. Measured
    at M2-S3 on one month of six: floor 3.5090 -> 4.1138, model 3.2608 -> 3.4207,
    margin 7.07% -> 16.85%. The model got WORSE and the transcript got better.

    Called before anything is fitted, so a sampled run costs seconds rather than a
    training run followed by a refusal.
    """
    if list(actual) != list(configured):
        raise GateError(
            "the gate issues no verdict for a SAMPLED run (F-008). This run trained "
            f"on {', '.join(actual) or '(none)'} and configs/train.yaml: "
            f"data.train_months is {', '.join(configured)}. Sampling degrades the "
            "FLOOR faster than the model (measured: margin 7.07% -> 16.85% on one "
            "month of six), so a sampled verdict reads better than the full-data one "
            "it is standing in for. Use --no-gate for a sample-first smoke run: it "
            "prints the table, issues no verdict, and can promote nothing."
        )


def decide(
    challenger: Metrics,
    floor: Metrics,
    cfg: dict,
    incumbent: Incumbent | None = None,
) -> Decision:
    """Judge one challenger against the floor and against what is serving.

    Pure; raises only on a comparison that would be meaningless. `incumbent` is
    optional because the first promotion has no incumbent to beat and because
    M2's recorded verdicts, replayed, carried none — a historical verdict must
    stay reproducible or the replay stops being evidence about anything.
    """
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
    if incumbent is not None and incumbent.split != holdout:
        raise GateError(
            f"the incumbent's numbers were measured on {incumbent.split!r} and this "
            f"gate judges on {holdout!r}. Two models scored on different months are "
            "not a comparison, and the champion's own tags say which month it was."
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

    if incumbent is not None:
        # F-011. The floor asks "is a booster worth serving at all"; only the
        # incumbent can answer "is this one better than what riders already get".
        # Both conditions, because a challenger can win the mean and lose the
        # rider-facing rate — over the test month, 0.1 KPI-10 points is ~6,000
        # riders quoted wrongly who were not before.
        challenger_mae = round(challenger.mae, INCUMBENT_MAE_DECIMALS)
        challenger_within = round(challenger.within_tolerance_rate, INCUMBENT_WITHIN_DECIMALS)
        checks.append(
            Check(
                name=f"KPI-09 does not regress against the serving champion (v{incumbent.version})",
                passed=challenger_mae <= incumbent.mae,
                detail=(
                    f"{challenger.mae:.4f} vs {incumbent.mae:.4f} min "
                    f"({improvement_pct(challenger.mae, incumbent.mae):+.2f}% vs incumbent)"
                ),
            )
        )
        checks.append(
            Check(
                name=f"KPI-10 does not regress against the serving champion (v{incumbent.version})",
                passed=challenger_within >= incumbent.within_tolerance_rate,
                detail=(
                    f"{challenger.within_tolerance_rate:.3f}% vs "
                    f"{incumbent.within_tolerance_rate:.3f}% = "
                    f"{challenger.within_tolerance_rate - incumbent.within_tolerance_rate:+.3f}"
                    " points"
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
        incumbent=incumbent,
    )


def verdict_lines(decision: Decision, *, holdout_untouched_by_selection: bool = False) -> str:
    """The transcript. Both numbers, on a pass and on a refusal alike.

    `holdout_untouched_by_selection` is the caller's claim, not the gate's
    (property 7 / F-018). Pass True only when the challenger being judged was
    chosen without reading a single number from this split — a single-challenger
    run (`make train`) may; a bake-off that ranks its arms on the holdout may
    not, and a bake-off that ranks on val should say where it ranked instead.
    The default is the weaker sentence because a claim nobody made must not be
    printed as if somebody had.
    """
    purity = "untouched by training and by selection" if holdout_untouched_by_selection else (
        "untouched by training (the caller states how its challenger was selected)"
    )
    lines = [
        f"[gate] holdout   : {decision.split} — {decision.n:,} rows, {purity}",
        f"[gate] challenger: {decision.challenger:<28} KPI-09 {decision.challenger_mae:.4f} min"
        f"  ·  KPI-10 {decision.challenger_within:.3f}%",
        f"[gate] floor     : {decision.floor:<28} KPI-09 {decision.floor_mae:.4f} min"
        f"  ·  KPI-10 {decision.floor_within:.3f}%",
    ]
    if decision.incumbent is None:
        lines.append(
            "[gate] incumbent : none — the champion alias is unset, so this verdict is "
            "judged against the floor alone (first promotion)"
        )
    else:
        inc = decision.incumbent
        lines.append(
            f"[gate] incumbent : version {inc.version:<20} KPI-09 {inc.mae:.4f} min"
            f"  ·  KPI-10 {inc.within_tolerance_rate:.3f}%   [{inc.source}]"
        )
    lines += [
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
