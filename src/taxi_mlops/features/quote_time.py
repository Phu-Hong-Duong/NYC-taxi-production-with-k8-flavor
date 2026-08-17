"""Feature set v1 — quote-time pure, and the registry of what is refused and why.

A "quote-time" feature is one a serving request can carry at the moment a rider
asks *how long will this take?* — before the trip happens. Everything else is
either the answer in disguise or a column that will not exist at M5's serving
boundary, and both fail in the same silent way: superb offline scores, an
unimplementable model.

Two halves, deliberately asymmetric:

- **The include list is a knob** (`configs/train.yaml: features`). Feature sets
  are meant to be revised; that is what M3's dossier does.
- **The exclude list is law** (`EXCLUSIONS` below, one reason per column) and a
  guard refuses any feature matrix containing one. A configured include that the
  registry excludes raises `FeatureLeakageError` rather than training. This is
  the same argument M2-S1 made about first-match attribution: a switch that can
  break an invariant is a trapdoor, not a knob.

On dtypes and gotcha #7 ("one cast, one place"): that law governs TLC COLUMNS,
whose canonical dtypes belong to `taxi_mlops.data.contract.cast` and nowhere
else. What this module returns is not TLC data — it is a model input matrix, and
its encoding (int16 zone ids, float32 passenger count) is a modelling choice
owned here. The input frame is never modified and nothing is ever written back.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


class FeatureLeakageError(ValueError):
    """A column the registry excludes reached (or was configured into) the matrix.

    A ValueError and not a warning: the failure mode this prevents is a model
    that scores beautifully and cannot be served, which no offline check catches.
    """


@dataclass(frozen=True)
class Exclusion:
    """One refused column, its reason, and the ledger row that owns the decision."""

    column: str
    reason: str
    finding: str | None = None
    revisit: str | None = None


# The six columns F-007(a) names, plus the three money columns it did not: they
# are recorded on the same meter at the same moment and fail the identical test,
# and leaving them out of the registry would mean the registry agreed with the
# finding rather than with the world.
_POST_TRIP = (
    "recorded at or after trip end — the meter's answer, not the rider's question. "
    "Windowed to fare_amount BETWEEN 0 AND 200 the fare correlates with duration at "
    "r = 0.8708 (eda_report.md §8), so a model using it scores superbly on every "
    "offline split and is unimplementable at M5's serving boundary."
)

EXCLUSIONS: tuple[Exclusion, ...] = (
    # ---- F-007(a): the post-trip columns. This registry IS its closing evidence.
    Exclusion("fare_amount", _POST_TRIP, finding="F-007(a)"),
    Exclusion("tip_amount", _POST_TRIP, finding="F-007(a)"),
    Exclusion("tolls_amount", _POST_TRIP, finding="F-007(a)"),
    Exclusion("total_amount", _POST_TRIP, finding="F-007(a)"),
    Exclusion("payment_type", _POST_TRIP, finding="F-007(a)"),
    Exclusion("store_and_fwd_flag", _POST_TRIP, finding="F-007(a)"),
    Exclusion("extra", _POST_TRIP + " Not in F-007's list; same meter, same moment."),
    Exclusion("mta_tax", _POST_TRIP + " Not in F-007's list; same meter, same moment."),
    Exclusion(
        "improvement_surcharge",
        _POST_TRIP + " Not in F-007's list; same meter, same moment.",
    ),
    # ---- F-007(b): the strongest predictor, and the one M3 must resolve.
    Exclusion(
        "trip_distance",
        "the meter's DRIVEN distance — what actually happened, not a route estimate. "
        "It is the single strongest predictor (r = 0.8066 raw, 0.8464 in logs, "
        "eda_report.md §9) and a serving system does not have it. Excluding it is what "
        "makes v1's numbers honest and is also why they are modest.",
        finding="F-007(b)",
        revisit="M3's feature dossier owns the quote-time substitute (OSRM or "
        "zone-centroid distance) or a recorded assumption that the meter value is "
        "treated as available. NOT this story's call.",
    ),
    # ---- F-006: available for five sixths of the training window, all of val/test.
    Exclusion(
        "congestion_surcharge",
        "switched on INSIDE the training window: 63.4565% null in 2019-01, cliffing "
        "from 99.822% null on 2019-01-20 to 1.118% on 2019-01-21, and 0.42-0.56% null "
        "in every other month (eda_report.md §7b). 2019-01 is a train month and "
        "2019-07/08 are clean, so a model fitted with it would learn 'January' and "
        "val AND test — the two splits that exist to catch this — would both look "
        "fine. Drift by AVAILABILITY, inside the data we fit on.",
        finding="F-006",
        revisit="Training from 2019-02 onward would make it usable and costs a sixth "
        "of the training data; v1 keeps the six months and drops the column, because "
        "one surcharge is worth less than 9.3M rows. Imputation was never an option: "
        "the training set is 1/6 contaminated, so the imputer would learn the cliff.",
    ),
    Exclusion(
        "airport_fee",
        "100% null across all 56,127,878 rows of this window (eda_report.md §7c) — a "
        "plausible-looking column carrying exactly zero information.",
        finding="F-006",
    ),
    # ---- Not findings; quote-time reasoning, recorded so the next reader need not
    #      re-derive it.
    Exclusion(
        "RatecodeID",
        "the rate code is set ON THE METER and can be changed until the trip closes; "
        "the out-of-city codes are 12x enriched among the trips the duration rule "
        "rejects (rejected_rows_appendix.md §2), which is exactly the signal a leaky "
        "feature carries. A dispatch system knows the DESTINATION at quote time, not "
        "the driver's meter setting.",
        revisit="M3's dossier may derive an airport/out-of-city flag from the "
        "requested OD pair, which IS quote-time knowable. That is a different "
        "feature with a different name.",
    ),
    Exclusion(
        "VendorID",
        "provenance of the RECORD, not a property of the trip: which TPEP provider "
        "uploaded the row. It also carries two undocumented values (4: 264,661 rows, "
        "5: 219 rows) that the TLC dictionary does not describe, so the model would "
        "be fitting a data-pipeline artefact.",
    ),
    Exclusion(
        "tpep_dropoff_datetime",
        "the target itself, minus the pickup timestamp. Listed explicitly because a "
        "'just pass the timestamps through' change is the most natural mistake here.",
    ),
    Exclusion(
        "trip_duration_minutes",
        "the target. Named for the same reason as the line above it.",
    ),
    Exclusion(
        "month",
        "a REPORTING dimension, never a feature (CLAUDE.md, standing law). The target "
        "mean rises 17.3% Jan->Jun and falls after; a model given `month` learns the "
        "calendar of 2019, which is the one thing that is guaranteed not to repeat.",
    ),
    Exclusion(
        "split",
        "which split a row is in. A feature that names the answer sheet.",
    ),
)

EXCLUDED_COLUMNS: frozenset[str] = frozenset(e.column for e in EXCLUSIONS)

# Included on purpose, with the request-time source named per the artisan
# playbook's rule (gotcha #21's family: every serving feature says where it comes
# from at request time).
REQUEST_TIME_SOURCE: dict[str, str] = {
    "hour": "the clock when the quote is asked for",
    "dayofweek": "the calendar day the quote is asked for",
    "PULocationID": "the pickup zone the rider is standing in / requests",
    "DOLocationID": "the drop-off zone the rider types in",
    "passenger_count": "the party size the rider states when booking",
}

PICKUP_TIMESTAMP = "tpep_pickup_datetime"

# The temporal derivations this module knows how to make. A configured name that
# is not here is a typo, and a typo that silently produced no column would be a
# model quietly trained on fewer features than its config claims.
_TEMPORAL_BUILDERS = {
    "hour": lambda ts: ts.dt.hour,
    "dayofweek": lambda ts: ts.dt.dayofweek,
}


def feature_names(cfg: dict[str, Any]) -> list[str]:
    """The feature matrix's columns, in order. The ONE answer to 'what does it eat?'."""
    names = list(cfg["temporal"]) + list(cfg["passthrough"])
    duplicates = [n for n in set(names) if names.count(n) > 1]
    if duplicates:
        raise ValueError(f"configs/train.yaml features: duplicated column(s) {duplicates}")
    assert_quote_time_pure(names)
    return names


def categorical_names(cfg: dict[str, Any]) -> list[str]:
    """Which of the features LightGBM should treat as labels rather than magnitudes."""
    names = feature_names(cfg)
    unknown = [c for c in cfg["categorical"] if c not in names]
    if unknown:
        raise ValueError(
            f"configs/train.yaml features.categorical names {unknown}, which is not a "
            f"feature. Features are {names}."
        )
    return list(cfg["categorical"])


def assert_quote_time_pure(columns: list[str] | pd.Index) -> None:
    """Refuse any column the registry excludes. Called on the config AND on the output.

    Both ends on purpose: the config check catches a human adding `fare_amount`
    to `passthrough`, and the output check catches a builder that leaks one in by
    another route. The second is the one that would otherwise never be noticed.
    """
    offenders = [c for c in columns if c in EXCLUDED_COLUMNS]
    if not offenders:
        return
    reasons = "\n".join(
        f"  - {e.column}: {e.reason}" + (f" [{e.finding}]" if e.finding else "")
        for e in EXCLUSIONS
        if e.column in offenders
    )
    raise FeatureLeakageError(
        f"feature set v1 is quote-time pure; these columns are excluded by "
        f"taxi_mlops.features.quote_time.EXCLUSIONS:\n{reasons}\n"
        "If the exclusion is wrong, change the registry and its ledger row — not "
        "the caller."
    )


def build_features(df: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    """DataFrame -> DataFrame. Pure, config-driven, no I/O. Training AND serving.

    Serving parity is structural rather than promised: M5's transformer imports
    this function, so a feature that changes here changes in both places at once.
    """
    names = feature_names(cfg)
    out = pd.DataFrame(index=df.index)

    for name in cfg["temporal"]:
        builder = _TEMPORAL_BUILDERS.get(name)
        if builder is None:
            raise ValueError(
                f"configs/train.yaml features.temporal names {name!r}, which this module "
                f"cannot derive. Known: {sorted(_TEMPORAL_BUILDERS)}."
            )
        if PICKUP_TIMESTAMP not in df.columns:
            raise ValueError(
                f"{name!r} is derived from {PICKUP_TIMESTAMP}, which the frame does not "
                "carry. A quote request must supply the pickup time."
            )
        out[name] = builder(df[PICKUP_TIMESTAMP]).astype("int16")

    for name in cfg["passthrough"]:
        if name not in df.columns:
            raise ValueError(f"feature {name!r} is not a column of the input frame")
        column = df[name]
        # Zone ids and party size: compact numerics LightGBM can bin. float32 for
        # passenger_count because the contract allows it to be null (nullable: true)
        # and NaN is how LightGBM is told "missing" — an invented fill value would
        # be a made-up passenger.
        out[name] = (
            column.astype("float32") if name == "passenger_count" else column.astype("int16")
        )

    out = out[names]
    assert_quote_time_pure(out.columns)
    return out
