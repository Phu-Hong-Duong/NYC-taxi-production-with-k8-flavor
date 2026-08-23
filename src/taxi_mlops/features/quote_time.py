"""The ONE transform path — quote-time pure, and the registry of what is refused.

A "quote-time" feature is one a serving request can carry at the moment a rider
asks *how long will this take?* — before the trip happens. Everything else is
either the answer in disguise or a column that will not exist at M5's serving
boundary, and both fail in the same silent way: superb offline scores, an
unimplementable model.

Two halves, deliberately asymmetric:

- **The include list is a knob** (`configs/features.yaml`, resolved by
  `taxi_mlops.features.sets`). Feature sets are meant to be revised; that is
  what M3's dossier and ablation did.
- **The exclude list is law** (`EXCLUSIONS` below, one reason per column) and a
  guard refuses any feature matrix containing one. A configured include that the
  registry excludes raises `FeatureLeakageError` rather than training. This is
  the same argument M2-S1 made about first-match attribution: a switch that can
  break an invariant is a trapdoor, not a knob.

M3-S3 added the third kind of column. A set is now `temporal` (derived from the
one timestamp a request carries) + `passthrough` (blessed contract columns) +
**`derived`** — lookups and transforms that need a shipped reference table
(`zones`, `calendar`) or a train-fitted one (`aggregates`). The exclusion law is
unchanged and applies to all three: `assert_quote_time_pure` still runs on the
configured names AND on the output columns, and every derived feature carries a
`REQUEST_TIME_SOURCE` entry naming where a live request would get it (gotcha
#21), pinned by a test rather than by good intentions.

On dtypes and gotcha #7 ("one cast, one place"): that law governs TLC COLUMNS,
whose canonical dtypes belong to `taxi_mlops.data.contract.cast` and nowhere
else. What this module returns is not TLC data — it is a model input matrix, and
its encoding (int16 zone ids, float32 distances) is a modelling choice owned
here. The input frame is never modified and nothing is ever written back.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from . import aggregates as aggregates_mod
from . import calendar as calendar_mod
from . import zones as zones_mod
from .lookups import COMMITTED, Lookups


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
# from at request time). A derived feature with no entry here fails a test — the
# question "can M5 actually compute this?" is answered when the feature is
# written, not when the deployment crashes.
REQUEST_TIME_SOURCE: dict[str, str] = {
    # ---- v1 (M2-S2)
    "hour": "the clock when the quote is asked for",
    "dayofweek": "the calendar day the quote is asked for",
    "PULocationID": "the pickup zone the rider is standing in / requests",
    "DOLocationID": "the drop-off zone the rider types in",
    "passenger_count": "the party size the rider states when booking",
    # ---- g1: the request clock, re-encoded. Nothing new is needed at serving.
    "hour_sin": "the request clock, as an angle (23:00 and 00:00 are adjacent)",
    "hour_cos": "the request clock, as an angle",
    "weekpos_sin": "position of the request within the week, as an angle",
    "weekpos_cos": "position of the request within the week, as an angle",
    "minute_of_day": "the request clock to the minute (08:55 -> 09:05 is not a step)",
    "part_of_day": "the request clock, bucketed (morning peak / day / night)",
    "is_weekend": "the request calendar day",
    "is_holiday": "a shipped federal-holiday table, keyed on the request date",
    "is_near_holiday": "the same shipped table, +/- one day",
    "is_business_day": "the request calendar day and the shipped holiday table",
    # ---- g2/g3: a lookup on the two zone ids the request already carries, in a
    # 263-row table that ships with the model. No service call, no live join.
    "centroid_haversine_km": "shipped zone-centroid table, keyed on the request's PU/DO",
    "centroid_dlat_km": "shipped zone-centroid table, keyed on the request's PU/DO",
    "centroid_dlon_km": "shipped zone-centroid table, keyed on the request's PU/DO",
    "centroid_manhattan_km": "shipped zone-centroid table, keyed on the request's PU/DO",
    "centroid_bearing_deg": "shipped zone-centroid table, keyed on the request's PU/DO",
    "log1p_haversine_km": "shipped zone-centroid table, keyed on the request's PU/DO",
    "midpoint_lat": "shipped zone-centroid table, keyed on the request's PU/DO",
    "midpoint_lon": "shipped zone-centroid table, keyed on the request's PU/DO",
    "has_geometry": "whether the request's PU/DO are real zones (264/265 are not)",
    "pu_is_airport": "the request's pickup zone id (JFK 132 / LGA 138 / EWR 1)",
    "do_is_airport": "the request's drop-off zone id",
    "is_airport_trip": "either end of the request being an airport zone",
    "pu_borough": "shipped zone lookup, keyed on the request's PU",
    "do_borough": "shipped zone lookup, keyed on the request's DO",
    "borough_pair": "shipped zone lookup, keyed on the request's PU and DO",
    # ---- g4
    "passenger_bucket": "the party size the rider states when booking, bucketed",
    # ---- g5: THE ones that need infrastructure. Today they travel with the
    # model as a fitted lookup; at M8 they are the Feast candidates the dossier
    # names, keyed exactly as below with end-of-hour feature timestamps.
    "od_median_duration_min": (
        "a TRAIN-fitted lookup keyed on (PU, DO) — shipped with the model at M5, "
        "an online feature-store read at M8"
    ),
    "pu_hour_mean_speed_kmh": (
        "a TRAIN-fitted lookup keyed on (PU, request hour) — same path as above"
    ),
    "pu_hour_trips_per_day": (
        "a TRAIN-fitted lookup keyed on (PU, request hour) — same path as above"
    ),
}

PICKUP_TIMESTAMP = "tpep_pickup_datetime"

# The temporal derivations this module knows how to make. A configured name that
# is not here is a typo, and a typo that silently produced no column would be a
# model quietly trained on fewer features than its config claims.
_TEMPORAL_BUILDERS = {
    "hour": lambda ts: ts.dt.hour,
    "dayofweek": lambda ts: ts.dt.dayofweek,
}

#: Every derived feature, its dtype, and the INPUT columns it needs off the
#: parquet. The second half is what lets `datasets.required_columns` stay a
#: narrow read (the exclusion registry expressed as I/O) while feature sets grow:
#: a set is asked what it needs rather than the reader being widened by hand.
_DERIVED: dict[str, tuple[str, tuple[str, ...]]] = {
    name: ("float32", (PICKUP_TIMESTAMP,))
    for name in ("hour_sin", "hour_cos", "weekpos_sin", "weekpos_cos")
}
_DERIVED.update(
    {
        "minute_of_day": ("int16", (PICKUP_TIMESTAMP,)),
        "part_of_day": ("int16", (PICKUP_TIMESTAMP,)),
        "is_weekend": ("int16", (PICKUP_TIMESTAMP,)),
        "is_holiday": ("int16", (PICKUP_TIMESTAMP,)),
        "is_near_holiday": ("int16", (PICKUP_TIMESTAMP,)),
        "is_business_day": ("int16", (PICKUP_TIMESTAMP,)),
        "has_geometry": ("int16", ("PULocationID", "DOLocationID")),
        "pu_is_airport": ("int16", ("PULocationID",)),
        "do_is_airport": ("int16", ("DOLocationID",)),
        "is_airport_trip": ("int16", ("PULocationID", "DOLocationID")),
        "pu_borough": ("int16", ("PULocationID",)),
        "do_borough": ("int16", ("DOLocationID",)),
        "borough_pair": ("int16", ("PULocationID", "DOLocationID")),
        "passenger_bucket": ("int16", ("passenger_count",)),
    }
)
_DERIVED.update(
    {
        name: ("float32", ("PULocationID", "DOLocationID"))
        for name in (
            "centroid_haversine_km",
            "centroid_dlat_km",
            "centroid_dlon_km",
            "centroid_manhattan_km",
            "centroid_bearing_deg",
            "log1p_haversine_km",
            "midpoint_lat",
            "midpoint_lon",
        )
    }
)
_DERIVED.update(
    {
        name: ("float32", (PICKUP_TIMESTAMP, "PULocationID", "DOLocationID"))
        for name in aggregates_mod.AGGREGATE_FEATURES
    }
)

DERIVED_FEATURES: frozenset[str] = frozenset(_DERIVED)

#: The derived features that cannot be computed from the request alone — they
#: need `aggregates.fit` to have been run on TRAIN months first. Named as a set
#: so `build_features` can refuse clearly instead of producing a column of NaN,
#: which would look exactly like "these zones were never seen".
FITTED_FEATURES: frozenset[str] = frozenset(aggregates_mod.AGGREGATE_FEATURES)


def feature_names(cfg: dict[str, Any]) -> list[str]:
    """The feature matrix's columns, in order. The ONE answer to 'what does it eat?'."""
    names = list(cfg["temporal"]) + list(cfg["passthrough"]) + list(cfg.get("derived", []))
    duplicates = [n for n in set(names) if names.count(n) > 1]
    if duplicates:
        raise ValueError(f"configs/features.yaml: duplicated column(s) {duplicates}")
    unknown = [n for n in cfg.get("derived", []) if n not in _DERIVED]
    if unknown:
        raise ValueError(
            f"configs/features.yaml names derived feature(s) {unknown}, which "
            f"taxi_mlops.features.quote_time cannot build. Known: {sorted(_DERIVED)}."
        )
    assert_quote_time_pure(names)
    return names


def source_columns(cfg: dict[str, Any]) -> list[str]:
    """Every INPUT column this set needs off disk — passthrough plus what derives.

    Asked rather than hardcoded, so adding a feature that needs a new column
    cannot produce a KeyError three layers down in a reader nobody edited.
    """
    needed = [PICKUP_TIMESTAMP, *cfg["passthrough"]]
    for name in cfg.get("derived", []):
        needed.extend(_DERIVED[name][1])
    seen: list[str] = []
    for column in needed:
        if column not in seen:
            seen.append(column)
    return seen


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


def _derived_columns(
    df: pd.DataFrame,
    wanted: list[str],
    fitted: aggregates_mod.PointInTimeAggregates | None,
    lookups: Lookups = COMMITTED,
) -> dict[str, Any]:
    """Every derived feature the set asked for, computed once each.

    Shared intermediates (the four centroid lookups, the holiday join) are built
    lazily and reused: nine geometry features off one `zones.geometry` call, not
    nine calls returning the same numbers.

    `lookups` supplies reference data from somewhere other than the committed
    CSVs — an online feature store, at M8. It reaches exactly two of the four
    reference groups, and `taxi_mlops.features.lookups` argues at length why the
    other two are refused (F-059). The refusal is visible below as two branches
    that call `zones_mod` directly while `geometry()` and `holidays()` do not.
    """
    if not wanted:
        return {}
    for name in wanted:
        for column in _DERIVED[name][1]:
            if column not in df.columns:
                raise ValueError(
                    f"derived feature {name!r} needs column {column!r}, which the frame "
                    f"does not carry. A quote request must supply it."
                )

    out: dict[str, Any] = {}
    cache: dict[str, Any] = {}

    def timestamps() -> pd.Series:
        return df[PICKUP_TIMESTAMP]

    def geometry() -> zones_mod.Geometry:
        if "geometry" not in cache:
            # `table=None` is `zones.geometry`'s own "read the committed CSV",
            # so an absent Lookups changes nothing about this call.
            cache["geometry"] = zones_mod.geometry(
                df["PULocationID"], df["DOLocationID"], table=lookups.geometry_table
            )
        return cache["geometry"]

    def holidays() -> dict[str, Any]:
        if "holidays" not in cache:
            cache["holidays"] = calendar_mod.flags(timestamps(), calendar=lookups.calendar)
        return cache["holidays"]

    def aggregate_values() -> dict[str, Any]:
        if "aggregates" not in cache:
            if fitted is None:
                raise ValueError(
                    "this feature set asks for the point-in-time aggregates "
                    f"{sorted(FITTED_FEATURES & set(wanted))}, but no fitted tables were "
                    "passed. They are fitted on TRAIN months only "
                    "(taxi_mlops.features.aggregates.fit) and handed in; building them "
                    "from whatever frame is in front of us is exactly the leak dossier "
                    "§4 trap 2 describes."
                )
            cache["aggregates"] = aggregates_mod.transform(fitted, df)
        return cache["aggregates"]

    for name in wanted:
        if name in ("hour_sin", "hour_cos"):
            angle = 2.0 * np.pi * timestamps().dt.hour.to_numpy(dtype="float64") / 24.0
            out[name] = np.sin(angle) if name.endswith("sin") else np.cos(angle)
        elif name in ("weekpos_sin", "weekpos_cos"):
            ts = timestamps()
            position = (
                ts.dt.dayofweek.to_numpy(dtype="float64") * 24.0
                + ts.dt.hour.to_numpy(dtype="float64")
            )
            angle = 2.0 * np.pi * position / 168.0
            out[name] = np.sin(angle) if name.endswith("sin") else np.cos(angle)
        elif name == "minute_of_day":
            ts = timestamps()
            out[name] = ts.dt.hour.to_numpy() * 60 + ts.dt.minute.to_numpy()
        elif name == "part_of_day":
            # Source A's three bands (hr_6_9 / hr_10_20 / hr_21_5) — the morning
            # peak, the working day, the night. Labels, not magnitudes: band 2
            # (night) wraps midnight and is not "two more than" band 0.
            hour = timestamps().dt.hour.to_numpy()
            out[name] = np.where(hour < 6, 2, np.where(hour < 10, 0, np.where(hour < 21, 1, 2)))
        elif name == "is_weekend":
            out[name] = (timestamps().dt.dayofweek.to_numpy() >= 5).astype("int16")
        elif name in ("is_holiday", "is_near_holiday", "is_business_day"):
            out[name] = holidays()[name]
        elif name == "centroid_haversine_km":
            out[name] = geometry().haversine_km
        elif name == "centroid_dlat_km":
            out[name] = geometry().dlat_km
        elif name == "centroid_dlon_km":
            out[name] = geometry().dlon_km
        elif name == "centroid_manhattan_km":
            out[name] = geometry().manhattan_km
        elif name == "centroid_bearing_deg":
            out[name] = geometry().bearing_deg
        elif name == "log1p_haversine_km":
            out[name] = np.log1p(geometry().haversine_km)
        elif name == "midpoint_lat":
            out[name] = geometry().midpoint_lat
        elif name == "midpoint_lon":
            out[name] = geometry().midpoint_lon
        elif name == "has_geometry":
            out[name] = geometry().has_geometry
        # THE NEXT SIX BRANCHES DELIBERATELY IGNORE `lookups` — F-059.
        # `airport_flags` is a constant, total over every id including the two
        # non-places the store has no row for; the borough CODE is an encoding
        # whose value depends on the whole lookup table's iteration order, so it
        # is not a per-entity value and cannot be fetched per entity. Both read
        # the committed artifacts unconditionally. `taxi_mlops.features.lookups`
        # carries the argument; `tests/unit/test_lookups_seam.py` refuses a
        # regression here by asking the AST rather than the behaviour, because a
        # store whose values happen to agree would hide it.
        elif name == "pu_is_airport":
            out[name] = zones_mod.airport_flags(df["PULocationID"])
        elif name == "do_is_airport":
            out[name] = zones_mod.airport_flags(df["DOLocationID"])
        elif name == "is_airport_trip":
            out[name] = np.maximum(
                zones_mod.airport_flags(df["PULocationID"]),
                zones_mod.airport_flags(df["DOLocationID"]),
            )
        elif name == "pu_borough":
            out[name] = zones_mod.borough_codes(df["PULocationID"])
        elif name == "do_borough":
            out[name] = zones_mod.borough_codes(df["DOLocationID"])
        elif name == "borough_pair":
            table = zones_mod.load_zone_table()
            width = len(table.boroughs)
            out[name] = zones_mod.borough_codes(df["PULocationID"]) * width + (
                zones_mod.borough_codes(df["DOLocationID"])
            )
        elif name == "passenger_bucket":
            # Dossier row 17: zero passengers is a data artefact, not a small
            # party, so it gets its own label rather than sitting at the bottom
            # of an ordered scale. Null gets its own label too — the contract
            # allows it, and folding null into "zero" would invent a party size.
            count = df["passenger_count"].to_numpy(dtype="float64")
            bucket = np.full(len(df), 4, dtype="int16")  # 4 = not stated
            known = ~np.isnan(count)
            bucket[known & (count <= 0)] = 0
            bucket[known & (count == 1)] = 1
            bucket[known & (count >= 2) & (count <= 3)] = 2
            bucket[known & (count >= 4)] = 3
            out[name] = bucket
        elif name in FITTED_FEATURES:
            out[name] = aggregate_values()[name]
        else:  # pragma: no cover — _DERIVED and this dispatch are twins
            raise ValueError(f"derived feature {name!r} has no builder")
    return out


def build_features(
    df: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    fitted: aggregates_mod.PointInTimeAggregates | None = None,
    lookups: Lookups = COMMITTED,
) -> pd.DataFrame:
    """DataFrame -> DataFrame. Config-driven, no I/O. Training AND serving.

    Serving parity is structural rather than promised: M5's transformer imports
    this function, so a feature that changes here changes in both places at once.

    `fitted` carries the point-in-time aggregate tables when the set asks for
    them. It is a parameter and not a module global on purpose: a global would
    make "which months is this row allowed to remember?" a property of the
    process rather than of the call, and that question is the whole of dossier
    §4 trap 2.

    `lookups` (M8-S4 leg 3) is the same shape of parameter for the same reason:
    it says where the CENTROID and CALENDAR reference data came from for THIS
    call — the committed CSVs by default, an online feature store when a
    transformer supplies one. It deliberately cannot reach the borough
    dictionary or the airport constant; `taxi_mlops.features.lookups` is where
    that refusal is argued (F-059).
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

    derived = _derived_columns(df, list(cfg.get("derived", [])), fitted, lookups)
    for name, values in derived.items():
        out[name] = pd.Series(values, index=df.index).astype(_DERIVED[name][0])

    out = out[names]
    assert_quote_time_pure(out.columns)
    return out
