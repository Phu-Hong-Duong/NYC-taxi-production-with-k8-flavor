"""The feature repo — entities and views, in git, read by the QUARANTINE only.

M8-S2. This module is imported by `.venv-feast`'s Feast (pandas 2.3.3) and by
nothing on this project's side of the wall (pandas 3.0.5). It therefore imports
`feast` and **may not import `taxi_mlops`**; its producer,
`scripts/feast_sources.py`, is the mirror image and imports `taxi_mlops` and not
`feast`. Both directions are pinned by `tests/unit/test_feast_repo.py`, because
a single import across that line is how a quarantine stops being one.

**Every view here reads an artifact this program already had.** Nothing is
computed in this file: the centroids come from `make zones` (M3-S2), the calendar
flags from `taxi_mlops.features.calendar` (the same code the champion's
`is_holiday` comes out of), and the window aggregates from
`taxi_mlops.features.aggregates.fit(point_in_time=True)` — M3-S3's g5 family. A
store that recomputed any of them would be a second definition of a number this
repo already owns, which is the mistake `configs/features.yaml` exists to prevent
one layer up.

**The verdicts live with the definitions.** `docs/feast_catalog.md` is the page a
human reads, and it records for every entry below whether the feature is IN the
champion, CATALOG-ONLY with the measurement that kept it out, or a CANDIDATE. The
uncomfortable one is stated in both places: the window aggregates are the family
every surveyed source swears by, and they LOST the M3 ablation (-1.63% relative
val MAE, KPI-10 -0.686 points on the 15% sample — `docs/ablation_m3.md` §4). They are defined here
because a catalog that lists only the winners is a catalog that cannot be used to
argue against repeating an experiment.

**Timestamps are END-OF-WINDOW** (the prior-art ADOPT, `docs/prior_art.md`): a
feature computed over a window is knowable only once the window has ended. The
stamps are derived in the producer from each window's own months — see that
module's docstring for why the correspondence with `aggregates.transform` is
exact, and `docs/feast_catalog.md` §4 for what M8-S3 measures against it.
"""

from __future__ import annotations

from pathlib import Path

from feast import Entity, FeatureView, Field, FileSource
from feast.types import Bool, Float64, String
from feast.value_type import ValueType

#: `<repo>/data/feast` — this file sits at `<repo>/infra/feast/feature_repo/`.
#: Absolute, because `feast apply` may be invoked from anywhere and a relative
#: source path would resolve against the caller's cwd (gotcha #38's shape: dbt's
#: partial-parse cache made a build a function of where somebody once stood).
SOURCE_DIR = Path(__file__).resolve().parents[3] / "data" / "feast"


def _source(name: str, description: str) -> FileSource:
    return FileSource(
        name=f"{name}_source",
        path=str(SOURCE_DIR / f"{name}.parquet"),
        timestamp_field="event_timestamp",
        description=description,
    )


# --------------------------------------------------------------- entities ---
# A TLC zone id. 1..263 have geometry; 264 ("Unknown") and 265 ("N/A") are not
# places and deliberately have NO ROW in the centroid view — DR-04 condition 1.
# A retrieval for them returns null, which is the champion's own
# `has_geometry = 0` path expressed in the store's vocabulary.
zone = Entity(
    name="zone",
    join_keys=["zone_id"],
    value_type=ValueType.INT64,
    description="A TLC taxi zone (LocationID 1..265; 264/265 are not places).",
)

# The OD pair is a COMPOSITE of two zone entities rather than a synthetic
# `od_pair_id`: the join keys are then the column names the rest of this program
# already uses, so a retrieval request and a feature matrix spell the pair the
# same way, and no encode/decode step exists to disagree with itself.
pickup_zone = Entity(
    name="pickup_zone",
    join_keys=["PULocationID"],
    value_type=ValueType.INT64,
    description="Pickup zone; half of the OD pair.",
)
dropoff_zone = Entity(
    name="dropoff_zone",
    join_keys=["DOLocationID"],
    value_type=ValueType.INT64,
    description="Dropoff zone; the other half of the OD pair.",
)
pickup_hour = Entity(
    name="pickup_hour",
    join_keys=["hour"],
    value_type=ValueType.INT64,
    description="Hour of day 0..23 of the pickup — the congestion window's key.",
)
calendar_day = Entity(
    name="calendar_day",
    join_keys=["date_key"],
    value_type=ValueType.STRING,
    description="A calendar date as YYYY-MM-DD; the key of the federal-holiday view.",
)


# ----------------------------------------------------------- static views ---
# IN THE CHAMPION. Feature set v2 carries nine geometry features (group g2,
# +0.63% relative val MAE, KEEP) and every one of them is a lookup on exactly
# this table. Serving them from a store changes nothing about the numbers; it
# changes who owns the lookup at request time, which is M8-S4's question.
zone_static_view = FeatureView(
    name="zone_static",
    entities=[zone],
    # No TTL: a zone's centroid is not a measurement that goes stale. The table
    # is re-derived only when TLC redraws the zones, which is a new artifact with
    # a new sha256, not an expiry.
    ttl=None,
    schema=[
        Field(name="centroid_lat", dtype=Float64),
        Field(name="centroid_lon", dtype=Float64),
        Field(name="borough", dtype=String),
        Field(name="is_airport", dtype=Bool),
    ],
    source=_source(
        "zone_static",
        "Area-weighted zone centroids (make zones, M3-S2) + borough + airport flag.",
    ),
    online=True,
    tags={
        "verdict": "in-champion",
        "feature_set": "v2",
        "group": "g2_centroid_geometry",
        "ablation": "+0.63% relative val MAE, KPI-10 +0.200 pts at FULL data — KEEP",
        "catalog": "docs/feast_catalog.md#zone_static",
    },
)

# IN THE CHAMPION. Group g1 (+1.77%, the largest single win of the M3 ablation)
# carries is_holiday / is_near_holiday / is_business_day; those three columns are
# this view. F-019 made an uncovered date a typed REFUSAL rather than a silent
# "not a holiday", so this view stops exactly where the committed table does.
calendar_day_view = FeatureView(
    name="calendar_day_flags",
    entities=[calendar_day],
    ttl=None,
    schema=[
        Field(name="is_holiday", dtype=Bool),
        Field(name="is_near_holiday", dtype=Bool),
        Field(name="is_business_day", dtype=Bool),
    ],
    source=_source(
        "calendar_day",
        "US federal holiday flags derived from 5 U.S.C. 6103 (make holidays, M5-S2).",
    ),
    online=True,
    tags={
        "verdict": "in-champion",
        "feature_set": "v2",
        "group": "g1_temporal_extras",
        "ablation": "+1.77% relative val MAE, KPI-10 +0.569 pts at FULL data — KEEP",
        "catalog": "docs/feast_catalog.md#calendar_day_flags",
    },
)


# ----------------------------------------------------- time-varying views ---
# CATALOG-ONLY, and the reason is measured, not suspected: group g5 —
# point-in-time aggregates, the single strongest family in every source
# `docs/feature_dossier.md` harvested — came in at **-1.63%** relative val MAE
# with KPI-10 down 0.686 points on the 15% sample and was DROPPED
# (docs/ablation_m3.md §4). A dropped group is never refitted at full data, so
# that number is a SAMPLE number and the catalog labels it as one (gotcha #15).
# The
# legal version is weaker than the zone identity v1 already carries, and the
# ILLEGAL version (fitted across the val month) would have cleared the keep bar:
# +1.56% on the month it saw, -3.83% on the untouched one
# (docs/leakage_redteam_m3.md). Both numbers are why these views exist here and
# not in `configs/features.yaml: v2`.
#
# No TTL, and that is a semantic claim rather than a default: a window aggregate
# is the best available knowledge until a LATER window supersedes it, so a val
# row in 2019-07 and a test row in 2019-08 must both be served the window stamped
# 2019-07-01 — which is exactly what `aggregates.transform` serves them. A TTL
# would make the store disagree with the fitted model as the gap widened.
od_window_stats_view = FeatureView(
    name="od_window_stats",
    entities=[pickup_zone, dropoff_zone],
    ttl=None,
    schema=[
        Field(name="od_median_duration_min", dtype=Float64),
        Field(name="window_months", dtype=String),
    ],
    source=_source(
        "od_window_stats",
        "Median historical duration per OD pair over each point-in-time window (g5).",
    ),
    online=True,
    tags={
        "verdict": "catalog-only",
        "group": "g5_point_in_time_aggregates",
        "ablation": (
            "-1.63% relative val MAE, KPI-10 -0.686 pts on the 15% SAMPLE — DROPPED. "
            "A dropped group is never refitted, so no full-data number exists"
        ),
        "leakage_note": "docs/leakage_redteam_m3.md: the illegal fit clears the bar",
        "catalog": "docs/feast_catalog.md#od_window_stats",
    },
)

pu_hour_window_stats_view = FeatureView(
    name="pu_hour_window_stats",
    entities=[pickup_zone, pickup_hour],
    ttl=None,
    schema=[
        Field(name="pu_hour_mean_speed_kmh", dtype=Float64),
        # A RATE, never a count — a raw count grows with the window and would
        # encode "how late in the training window this row is", i.e. `month`
        # re-entering by the back door (aggregates.py's window-stability note).
        Field(name="pu_hour_trips_per_day", dtype=Float64),
        Field(name="window_months", dtype=String),
    ],
    source=_source(
        "pu_hour_window_stats",
        "Mean centroid-derived speed and trips/day per (pickup zone, hour) window (g5).",
    ),
    online=True,
    tags={
        "verdict": "catalog-only",
        "group": "g5_point_in_time_aggregates",
        "ablation": (
            "-1.63% relative val MAE, KPI-10 -0.686 pts on the 15% SAMPLE — DROPPED. "
            "A dropped group is never refitted, so no full-data number exists"
        ),
        "speed_note": "computed from CENTROID distance, never the meter's trip_distance",
        "catalog": "docs/feast_catalog.md#pu_hour_window_stats",
    },
)


# ------------------------------------------------------------- candidates ---
# CANDIDATE. `is_airport` above is the raw fact; the CANDIDATE is what
# `docs/error_memo_m2.md` §7 row 2 asks for after three independent
# measurements — an airport flag evaluated as a REGIME indicator rather than as a
# distance proxy. Nothing is fitted for it here (M8 law 3); it is recorded so the
# next model story inherits the question with its evidence attached. The
# definition it would need already exists as `zone_static.is_airport`, which is
# the point: the catalog's job is to say what is available and what is known
# about it, not to run the experiment.
AIRPORT_REGIME_CANDIDATE = {
    "name": "airport_regime_flag",
    "verdict": "candidate",
    "would_be_built_from": "zone_static.is_airport (pickup and dropoff)",
    "evidence": (
        "the airport error gap held at 1.86-2.00x ordinary in three ordinary "
        "periods and 2.07-2.35x through the 2020-03 collapse "
        "(docs/drift_memo_m7.md), 1.91x at M3-S5 (docs/error_memo_m2.md 9), and "
        "1.90x at M2-S4 — a ratio that barely moves across a regime change in "
        "which minutes-per-mile changed, which is what rules OUT the "
        "distance-proxy hypothesis"
    ),
    "catalog": "docs/feast_catalog.md#airport_regime_flag",
}
