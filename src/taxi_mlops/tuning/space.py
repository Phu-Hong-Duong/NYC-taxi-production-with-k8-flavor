"""The sniper's search space — centred on the scout's winner, and bounded.

`configs/tuning.yaml` says the space is "centered on the scout's winner at
execution time". This module is that sentence as code, and it is declarative so
that a reviewer can read the *whole* space in one screen rather than inferring
it from a sequence of `trial.suggest_*` calls scattered through a fitting loop.

**How centring works, and why it is bounded on both sides.** Each knob declares
an absolute range (what the knob may ever be, for this data at this scale) and a
`span` (how far the sniper may wander from the scout's value). The suggested
range is the scout's value scaled by `span` in both directions, then CLIPPED to
the absolute range. Two failure modes this avoids:

1. *An uncentred search* wastes a 60-trial budget re-discovering the region the
   scout spent 1,800 seconds finding — which would make the scout ornamental.
2. *An unbounded centring* lets one odd scout value (a `min_data_in_leaf` of 5
   found on a small internal subsample) drag the whole study into a region that
   cannot survive 44M rows. The absolute range is the adult in the room.

**Knobs with no meaningful centre are honest about it.** `lambda_l1`/`lambda_l2`
default to 0 in LightGBM, and a multiplicative window around 0 is 0. Those are
searched over their full log range regardless of the scout's value, and
`Knob.centred` says so — a space that pretended to centre on zero would be
reporting a search it did not run.

Nothing here is a result. Every value this module proposes is a hypothesis until
`taxi_mlops.training.evaluate` scores the model that came out (gotcha #15).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: The families the sniper can fit and log. FLAML's `estimator_list` in
#: `configs/automl.yaml` is wider (it also offers `rf` and `extra_tree`), and
#: that is deliberate: the scout is allowed to tell us something we did not
#: expect. If it names a family that is not here, `check_family` REFUSES rather
#: than quietly tuning the runner-up — a sniper that silently retargets is a
#: sniper whose report does not describe what it did.
SUPPORTED_FAMILIES = ("lgbm", "xgboost")


class UnsupportedFamilyError(RuntimeError):
    """The scout named a family this sniper cannot fit, refit and log."""


@dataclass(frozen=True)
class Knob:
    """One searchable hyperparameter: what it may ever be, and how far to wander."""

    name: str
    kind: str  # "float" | "int"
    low: float  # absolute floor — the scout cannot argue below this
    high: float  # absolute ceiling
    log: bool = False
    span: float = 3.0  # multiplicative half-width around the scout's value
    centred: bool = True  # False = search the full range; see the module docstring
    default: float = 0.0  # centre used when the scout reported nothing

    def bounds(self, centre: float | None) -> tuple[float, float]:
        """The (low, high) this trial may sample from, after centring and clipping."""
        if not self.centred or centre is None or centre <= 0:
            return self.low, self.high
        low = max(self.low, centre / self.span)
        high = min(self.high, centre * self.span)
        if low >= high:  # a centre outside the absolute range: keep the range, not the centre
            return self.low, self.high
        return low, high


#: LightGBM. `objective`/`metric` are NOT searchable: `l1` is the metric the gate
#: judges on (KPI-09 is MAE in minutes) and M2-S2 argued that choice from the
#: metric rather than from a sweep. A sniper that could change the objective
#: would be searching a different question.
LGBM_KNOBS = (
    Knob("learning_rate", "float", 0.01, 0.30, log=True, span=3.0, default=0.05),
    Knob("num_leaves", "int", 31, 1023, log=True, span=3.0, default=255),
    Knob("min_data_in_leaf", "int", 50, 5000, log=True, span=4.0, default=500),
    Knob("feature_fraction", "float", 0.40, 1.00, span=1.6, default=1.0),
    Knob("bagging_fraction", "float", 0.50, 1.00, span=1.6, default=0.8),
    Knob("lambda_l1", "float", 1e-8, 10.0, log=True, centred=False),
    Knob("lambda_l2", "float", 1e-8, 10.0, log=True, centred=False),
    Knob("max_cat_threshold", "int", 16, 256, log=True, span=3.0, default=64),
    Knob("cat_smooth", "float", 1.0, 200.0, log=True, span=5.0, default=20.0),
)

#: XGBoost. Same shape, same refusal to search the objective:
#: `reg:absoluteerror` is `l1` under another name, and it is the metric the gate
#: reads. Categorical columns ride on `enable_categorical` + `tree_method=hist`.
XGBOOST_KNOBS = (
    Knob("eta", "float", 0.01, 0.30, log=True, span=3.0, default=0.05),
    Knob("max_depth", "int", 4, 14, span=2.0, default=8),
    Knob("min_child_weight", "float", 1.0, 500.0, log=True, span=4.0, default=20.0),
    Knob("subsample", "float", 0.50, 1.00, span=1.6, default=0.8),
    Knob("colsample_bytree", "float", 0.40, 1.00, span=1.6, default=1.0),
    Knob("reg_lambda", "float", 1e-8, 10.0, log=True, centred=False),
    Knob("reg_alpha", "float", 1e-8, 10.0, log=True, centred=False),
    Knob("max_cat_threshold", "int", 16, 256, log=True, span=3.0, default=64),
)

KNOBS: dict[str, tuple[Knob, ...]] = {"lgbm": LGBM_KNOBS, "xgboost": XGBOOST_KNOBS}

#: The scout reports FLAML's own parameter names. Where they differ from the
#: booster's native spelling, this maps scout -> knob so the centre is really
#: the scout's value and not a silently-dropped one.
SCOUT_ALIASES: dict[str, dict[str, str]] = {
    "lgbm": {
        "n_estimators": "num_boost_round",
        "colsample_bytree": "feature_fraction",
        "min_child_samples": "min_data_in_leaf",
        "reg_alpha": "lambda_l1",
        "reg_lambda": "lambda_l2",
    },
    "xgboost": {
        "n_estimators": "num_boost_round",
        "learning_rate": "eta",
    },
}


def check_family(family: str) -> str:
    """Refuse a family the sniper cannot honestly carry through to a contender."""
    if family not in SUPPORTED_FAMILIES:
        raise UnsupportedFamilyError(
            f"the scout named family {family!r}, and this sniper fits "
            f"{list(SUPPORTED_FAMILIES)}. Tuning the runner-up instead would make the "
            "report describe a search that did not happen — record the scout's verdict, "
            "raise it, and decide in the open (M3-S4 names this as its one refusal path)."
        )
    return family


def centre_from_scout(family: str, scout_params: dict[str, Any] | None) -> dict[str, float]:
    """FLAML's winning config -> a centre per knob, in the booster's own spelling."""
    check_family(family)
    aliases = SCOUT_ALIASES.get(family, {})
    translated: dict[str, float] = {}
    for key, value in (scout_params or {}).items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        translated[aliases.get(key, key)] = float(value)
    return {knob.name: translated.get(knob.name, knob.default) for knob in KNOBS[family]}


def suggest(trial: Any, family: str, centre: dict[str, float]) -> dict[str, Any]:
    """One trial's hyperparameters. The only place `trial.suggest_*` is called."""
    check_family(family)
    params: dict[str, Any] = {}
    for knob in KNOBS[family]:
        low, high = knob.bounds(centre.get(knob.name))
        if knob.kind == "int":
            params[knob.name] = trial.suggest_int(knob.name, int(low), int(high), log=knob.log)
        else:
            params[knob.name] = trial.suggest_float(knob.name, low, high, log=knob.log)
    return params


def describe(family: str, centre: dict[str, float]) -> str:
    """The space, printed, so the transcript records what was actually searched."""
    check_family(family)
    lines = [f"  {'knob':<20} {'centre':>10} {'low':>12} {'high':>12}  mode"]
    lines.append(f"  {'-' * 20} {'-' * 10} {'-' * 12} {'-' * 12}  ----")
    for knob in KNOBS[family]:
        value = centre.get(knob.name)
        low, high = knob.bounds(value)
        mode = f"centred x{knob.span:g}" if knob.centred else "full range (no meaningful centre)"
        shown = "—" if value is None else f"{value:.6g}"
        lines.append(f"  {knob.name:<20} {shown:>10} {low:>12.6g} {high:>12.6g}  {mode}")
    return "\n".join(lines)
