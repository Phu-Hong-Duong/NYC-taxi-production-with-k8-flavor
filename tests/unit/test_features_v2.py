"""Feature set v2 — the derived features, their fallbacks, and the leakage law.

Three classes of defect this file exists to catch, none of which looks like a
defect from the outside:

1. **A spatial feature that quietly invents a coordinate for zones 264/265.**
   They are TLC's "Unknown" and have no centroid by design; 264->264 is the
   largest single OD "route" in the data and ~1.1% of held-out rows have no
   geometry. `docs/error_memo_m2.md` §1 is the standing warning that the small
   fraction is where the value lives. Design Review DR-04 condition 1 / AI-3.
2. **An aggregate that contains its own answer.** The point-in-time cutoff is
   the whole difference between the top-6% Kaggle solution and a disqualifying
   one, and a table fitted without it produces *better* validation numbers —
   so nothing downstream complains.
3. **A feature that cannot be computed at serving time.** Caught here rather
   than at M5 by requiring a `REQUEST_TIME_SOURCE` entry per derived feature
   (gotcha #21).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from taxi_mlops.data.config import load_yaml
from taxi_mlops.features import aggregates, calendar, quote_time, sets, zones
from taxi_mlops.features.quote_time import EXCLUDED_COLUMNS, FeatureLeakageError, build_features
from taxi_mlops.training.datasets import required_columns
from taxi_mlops.training.run import load_train_config

TARGET = "trip_duration_minutes"
ALL_DERIVED = sorted(quote_time.DERIVED_FEATURES)


def frame(
    pu: list[int], do: list[int], *, month: str = "2019-03", minutes: list[float] | None = None
) -> pd.DataFrame:
    """A minimal quote-shaped frame: the timestamp, the two zones, the party size."""
    rows = len(pu)
    start = pd.Timestamp(f"{month}-05 08:30:00")
    return pd.DataFrame(
        {
            quote_time.PICKUP_TIMESTAMP: [start + pd.Timedelta(hours=i) for i in range(rows)],
            "PULocationID": np.array(pu, dtype="int64"),
            "DOLocationID": np.array(do, dtype="int64"),
            "passenger_count": np.ones(rows, dtype="float64"),
            TARGET: np.array(minutes if minutes is not None else [10.0] * rows, dtype="float64"),
        }
    )


def everything_cfg() -> dict:
    """A synthetic set naming EVERY derived feature — the dispatch's twin check."""
    base = sets.load_registry()["base"]
    return {
        "version": "test-everything",
        "temporal": list(base["temporal"]),
        "passthrough": list(base["passthrough"]),
        "derived": ALL_DERIVED,
        "categorical": list(base["categorical"]),
        "groups": [],
    }


# --------------------------------------------------------------------------
# The registry has ONE home (F-013's features half, Design Review AI-6)
# --------------------------------------------------------------------------


def test_train_config_features_block_holds_only_a_pointer():
    """The stale stub is gone and cannot grow back as a second definition."""
    raw = load_yaml("configs/train.yaml")["features"]
    assert set(raw) <= set(sets.TRAIN_CONFIG_KEYS), (
        f"configs/train.yaml: features carries {sorted(raw)} — feature sets have one "
        "home since M3-S3 (F-013)"
    )
    assert raw["registry"] == sets.DEFAULT_REGISTRY


def test_a_second_home_is_refused_loudly():
    with pytest.raises(sets.FeatureSetError, match="ONE.*home|one home"):
        sets.resolve({"version": "v1", "temporal": ["hour"]})


def test_no_set_in_the_registry_names_an_excluded_column():
    """The stub's actual sin: its `v1` named `trip_distance`, which DR-04 excludes.

    Checked over every set including the ones nobody trains today, because the
    next session will read this file before it reads the exclusion registry.
    """
    for name in sets.set_names():
        resolved = sets.resolve_set(name)
        named = set(resolved["temporal"]) | set(resolved["passthrough"]) | set(resolved["derived"])
        assert not (named & EXCLUDED_COLUMNS), f"set {name!r} re-admits {named & EXCLUDED_COLUMNS}"
    text = Path(sets.DEFAULT_REGISTRY).read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        assert "trip_distance" not in stripped, (
            "configs/features.yaml names trip_distance outside a comment — the stale "
            "stub M3-S3 deleted said exactly this (F-013)"
        )


def test_v1_still_resolves_to_the_champion_s_five_columns_in_order():
    """`nyc-taxi-eta` version 1 carries a signature over these names, in this order.

    verify-m2 §1 and `score.py` both fail if this drifts; failing here first is
    cheaper than failing against a live registry.
    """
    assert quote_time.feature_names(sets.resolve_set("v1")) == [
        "hour",
        "dayofweek",
        "PULocationID",
        "DOLocationID",
        "passenger_count",
    ]
    assert quote_time.feature_names(load_train_config()["features"]) == [
        "hour",
        "dayofweek",
        "PULocationID",
        "DOLocationID",
        "passenger_count",
    ]


def test_unknown_set_and_unknown_group_are_refused_by_name():
    with pytest.raises(sets.FeatureSetError, match="not defined"):
        sets.resolve_set("v9_does_not_exist")


def test_every_declared_group_is_reachable_and_non_empty():
    """DR-03 fixed five groups in a fixed order BEFORE anything was fitted."""
    names = sets.group_names()
    assert len(names) == 5, names
    for group in names:
        spec = sets.load_registry()["groups"][group]
        assert spec["derived"], f"group {group} derives nothing"
        assert set(spec["derived"]) <= quote_time.DERIVED_FEATURES


# --------------------------------------------------------------------------
# Serving reachability (gotcha #21)
# --------------------------------------------------------------------------


def test_every_derived_feature_names_its_request_time_source():
    missing = [n for n in ALL_DERIVED if n not in quote_time.REQUEST_TIME_SOURCE]
    assert not missing, (
        f"{missing} have no REQUEST_TIME_SOURCE entry. A feature that cannot say where "
        "a live request would get it is a feature M5 discovers by crashing."
    )


def test_every_derived_feature_actually_gets_built():
    """`_DERIVED` and the builder dispatch are twins; this is the test that pins it."""
    df = frame([100, 200], [200, 100])
    fitted = aggregates.fit(df, TARGET)
    matrix = build_features(df, everything_cfg(), fitted=fitted)
    assert list(matrix.columns) == quote_time.feature_names(everything_cfg())
    for name in ALL_DERIVED:
        assert matrix[name].dtype.name == quote_time._DERIVED[name][0]


def test_the_output_is_still_checked_against_the_exclusion_registry():
    cfg = everything_cfg()
    cfg["passthrough"] = [*cfg["passthrough"], "trip_distance"]
    with pytest.raises(FeatureLeakageError, match="trip_distance"):
        quote_time.feature_names(cfg)


def test_required_columns_grows_with_the_set_rather_than_by_hand():
    v1_columns = required_columns(sets.resolve_set("v1"), TARGET)
    g2_columns = required_columns(sets.resolve_set("v1_g2"), TARGET)
    assert "PULocationID" in g2_columns and "DOLocationID" in g2_columns
    # The narrow read stays narrow: geometry needs no column v1 did not already
    # read, which is why the substitute is cheap as well as legal.
    assert set(g2_columns) == set(v1_columns)


# --------------------------------------------------------------------------
# DR-04 condition 1 / AI-3 — zones 264 and 265 have a NAMED, TESTED path
# --------------------------------------------------------------------------


def test_unknown_zones_get_nan_geometry_and_a_flag_not_an_invented_place():
    df = frame([264, 265, 100, 264], [100, 264, 200, 264])
    matrix = build_features(df, sets.resolve_set("v1_g2"))
    unknown = np.array([True, True, False, True])
    for column in (
        "centroid_haversine_km",
        "centroid_manhattan_km",
        "centroid_bearing_deg",
        "midpoint_lat",
        "midpoint_lon",
        "log1p_haversine_km",
    ):
        assert matrix.loc[unknown, column].isna().all(), f"{column} invented a value"
        assert matrix.loc[~unknown, column].notna().all(), f"{column} is NaN for a real pair"
    assert list(matrix["has_geometry"]) == [0, 0, 1, 0]


def test_the_largest_od_route_in_the_data_builds_without_raising():
    """264->264 is the single largest OD "route" (409,128 trips). It must not crash."""
    matrix = build_features(frame([264], [264]), sets.resolve_set("v1_g2"))
    assert len(matrix) == 1
    assert matrix["has_geometry"].iloc[0] == 0


def test_an_out_of_range_zone_id_lands_on_the_same_named_path():
    """An array index, not a lookup: 999 must not silently read zone 999 % n."""
    matrix = build_features(frame([999, 0, -3], [100, 100, 100]), sets.resolve_set("v1_g2"))
    assert matrix["centroid_haversine_km"].isna().all()
    assert list(matrix["has_geometry"]) == [0, 0, 0]


def test_borough_pair_is_defined_for_the_unknown_zones_which_is_the_point_of_it():
    """Dossier row 13: the coarse backoff exists for EVERY OD pair, including these."""
    matrix = build_features(frame([264, 265], [1, 132]), sets.resolve_set("v1_g3"))
    assert matrix["pu_borough"].notna().all()
    assert matrix["borough_pair"].notna().all()
    table = zones.load_zone_table()
    assert table.boroughs[table.borough_code[264]] == "Unknown"


def test_an_unseen_zone_id_cannot_invent_a_category_code():
    """The unseen-category law (eda_report §11: ~0.017% of held-out rows carry an
    OD pair train never saw) applied to the NEW categoricals.

    Every one of them is a lookup into a fixed-size array, so the failure mode is
    not "unseen" — it is an out-of-range index quietly returning a real borough.
    """
    matrix = build_features(frame([999, 264], [-1, 265]), sets.resolve_set("v1_g3"))
    table = zones.load_zone_table()
    unknown = table.boroughs.index("Unknown")
    assert list(matrix["pu_borough"]) == [unknown, unknown]
    assert list(matrix["do_borough"]) == [unknown, unknown]
    # borough_pair is pu * width + do, so Unknown->Unknown is the one code that
    # must come back for every id the table cannot place.
    assert matrix["borough_pair"].nunique() == 1
    assert list(matrix["pu_is_airport"]) == [0, 0]


def test_airport_flags_name_the_three_airports_and_nothing_else():
    matrix = build_features(frame([132, 138, 1, 100], [100, 100, 100, 100]),
                            sets.resolve_set("v1_g3"))
    assert list(matrix["pu_is_airport"]) == [1, 1, 1, 0]
    assert list(matrix["is_airport_trip"]) == [1, 1, 1, 0]
    assert list(matrix["do_is_airport"]) == [0, 0, 0, 0]


def test_geometry_is_a_plausible_distance_for_a_known_pair():
    """JFK (132) to LGA (138): ~15 km apart in reality. A unit slip shows up here."""
    matrix = build_features(frame([132], [138]), sets.resolve_set("v1_g2"))
    haversine = float(matrix["centroid_haversine_km"].iloc[0])
    assert 10.0 < haversine < 20.0, haversine
    # The L a taxi drives is never shorter than the diagonal it cannot fly.
    assert float(matrix["centroid_manhattan_km"].iloc[0]) >= haversine
    assert 0.0 <= float(matrix["centroid_bearing_deg"].iloc[0]) < 360.0


# --------------------------------------------------------------------------
# The calendar — a named gap, and a loud refusal outside its coverage
# --------------------------------------------------------------------------


def test_holiday_flags_fire_on_a_real_holiday_and_its_neighbour():
    df = frame([100] * 3, [200] * 3, month="2019-07")
    df[quote_time.PICKUP_TIMESTAMP] = pd.to_datetime(["2019-07-03", "2019-07-04", "2019-07-08"])
    matrix = build_features(df, sets.resolve_set("v1_g1"))
    assert list(matrix["is_holiday"]) == [0, 1, 0]
    assert list(matrix["is_near_holiday"]) == [1, 0, 0]


def test_a_holiday_is_not_a_business_day_even_on_a_thursday():
    """The mistake this pins: `is_business_day` is not `is_weekend` inverted."""
    df = frame([100] * 2, [200] * 2)
    df[quote_time.PICKUP_TIMESTAMP] = pd.to_datetime(["2019-07-04", "2019-07-11"])
    matrix = build_features(df, sets.resolve_set("v1_g1"))
    assert list(matrix["is_weekend"]) == [0, 0]
    assert list(matrix["is_business_day"]) == [0, 1]


def test_an_uncovered_year_raises_instead_of_answering_not_a_holiday():
    df = frame([100], [200])
    df[quote_time.PICKUP_TIMESTAMP] = pd.to_datetime(["2021-07-04"])
    with pytest.raises(ValueError, match="covers"):
        build_features(df, sets.resolve_set("v1_g1"))


def test_cyclic_hour_puts_2300_next_to_0000():
    df = frame([100] * 3, [200] * 3)
    df[quote_time.PICKUP_TIMESTAMP] = pd.to_datetime(
        ["2019-03-05 23:00", "2019-03-06 00:00", "2019-03-06 12:00"]
    )
    matrix = build_features(df, sets.resolve_set("v1_g1"))
    near = abs(matrix["hour_cos"].iloc[0] - matrix["hour_cos"].iloc[1])
    far = abs(matrix["hour_cos"].iloc[0] - matrix["hour_cos"].iloc[2])
    assert near < far


def test_passenger_bucket_gives_zero_and_null_their_own_labels():
    df = frame([100] * 5, [200] * 5)
    df["passenger_count"] = [0.0, 1.0, 3.0, 6.0, np.nan]
    matrix = build_features(df, sets.resolve_set("v1_g4"))
    assert list(matrix["passenger_bucket"]) == [0, 1, 2, 3, 4]


def test_the_derived_builders_survive_the_nullable_dtypes_the_parquet_ACTUALLY_ships():
    """`data/processed` hands back pandas `Int64`, not numpy int64.

    `passenger_count` is `nullable: true` in the contract, so the missing case is
    a real row and not a hypothetical — and the difference between `NaN` in a
    float column (what a hand-built fixture produces) and `pd.NA` in an `Int64`
    column (what the reader produces) is exactly the kind of gap that makes a
    green unit suite and a red training run.
    """
    df = frame([100, 132], [200, 138])
    for column in ("PULocationID", "DOLocationID"):
        df[column] = df[column].astype("Int64")
    df["passenger_count"] = pd.array([pd.NA, 3], dtype="Int64")
    matrix = build_features(df, everything_cfg(), fitted=aggregates.fit(df, TARGET))
    assert list(matrix["passenger_bucket"]) == [4, 2]
    assert matrix["centroid_haversine_km"].notna().all()
    assert list(matrix["has_geometry"]) == [1, 1]


# --------------------------------------------------------------------------
# The point-in-time law (dossier §4 traps 1-2) — the reason this family is legal
# --------------------------------------------------------------------------


def two_month_frame() -> pd.DataFrame:
    """Month 1 is ordinary; month 2's SAME OD pair takes ten times as long."""
    january = frame([100] * 4, [200] * 4, month="2019-01", minutes=[10.0] * 4)
    february = frame([100] * 4, [200] * 4, month="2019-02", minutes=[100.0] * 4)
    return pd.concat([january, february], ignore_index=True)


def test_the_first_fitted_month_gets_no_number_rather_than_its_own_answer():
    df = two_month_frame()
    fitted = aggregates.fit(df, TARGET)
    matrix = build_features(df, sets.resolve_set("v1_g5"), fitted=fitted)
    assert matrix["od_median_duration_min"].iloc[:4].isna().all()


def test_a_later_month_sees_history_and_never_itself():
    """February's rows average 100 minutes. Their feature must say 10, not 100."""
    df = two_month_frame()
    fitted = aggregates.fit(df, TARGET)
    matrix = build_features(df, sets.resolve_set("v1_g5"), fitted=fitted)
    assert matrix["od_median_duration_min"].iloc[4:].eq(10.0).all()


def test_a_month_after_the_fitted_window_sees_all_of_it():
    """Val and test come after every train month, so the whole window IS their history."""
    fitted = aggregates.fit(two_month_frame(), TARGET)
    later = frame([100], [200], month="2019-07")
    matrix = build_features(later, sets.resolve_set("v1_g5"), fitted=fitted)
    assert float(matrix["od_median_duration_min"].iloc[0]) == pytest.approx(55.0)


def test_the_leaky_switch_really_leaks_or_the_red_team_proves_nothing():
    """If `point_in_time=False` did nothing, M3-S3's drill would be theatre."""
    df = two_month_frame()
    leaky = aggregates.fit(df, TARGET, point_in_time=False)
    assert leaky.point_in_time is False
    assert "LEAKY BY REQUEST" in leaky.describe()
    matrix = build_features(df, sets.resolve_set("v1_g5"), fitted=leaky)
    # Every row now sees the median of BOTH months, including its own.
    assert matrix["od_median_duration_min"].notna().all()
    assert matrix["od_median_duration_min"].eq(55.0).all()


def test_an_unseen_key_gets_nan_not_a_neighbouring_cell_s_number():
    """~0.017% of held-out rows carry an OD pair train never saw (eda_report §11)."""
    fitted = aggregates.fit(two_month_frame(), TARGET)
    matrix = build_features(frame([7], [9], month="2019-07"), sets.resolve_set("v1_g5"),
                            fitted=fitted)
    assert matrix["od_median_duration_min"].isna().all()
    assert matrix["pu_hour_mean_speed_kmh"].isna().all()
    assert matrix["pu_hour_trips_per_day"].isna().all()


def test_asking_for_aggregates_without_fitting_them_raises_rather_than_returning_nan():
    """A column of NaN looks exactly like 'these keys were never seen'."""
    with pytest.raises(ValueError, match="point-in-time aggregates"):
        build_features(frame([100], [200]), sets.resolve_set("v1_g5"))


def test_the_demand_feature_is_a_rate_so_a_longer_window_is_not_a_bigger_number():
    """A raw count would encode 'how late in the training window this row is' —
    `month` re-entering by the back door, which CLAUDE.md forbids outright."""
    one_day = frame([100] * 6, [200] * 6, month="2019-01")
    two_days = pd.concat(
        [one_day, one_day.assign(**{
            quote_time.PICKUP_TIMESTAMP: one_day[quote_time.PICKUP_TIMESTAMP]
            + pd.Timedelta(days=1)
        })],
        ignore_index=True,
    )
    later = frame([100], [200], month="2019-07")
    later[quote_time.PICKUP_TIMESTAMP] = pd.to_datetime(["2019-07-05 08:30:00"])
    rates = [
        float(
            build_features(later, sets.resolve_set("v1_g5"),
                           fitted=aggregates.fit(source, TARGET))["pu_hour_trips_per_day"].iloc[0]
        )
        for source in (one_day, two_days)
    ]
    assert rates[0] == pytest.approx(rates[1]), rates


def test_the_speed_aggregate_never_touches_the_meter_s_distance():
    """Dossier §4 trap 1: per-trip speed is the target in disguise, and the only
    distance allowed anywhere near it is the centroid one.

    Parsed as an AST rather than grepped, for the reason M3-S2's CRS test records
    and gotcha #35 names: the module's own PROSE about not using `trip_distance`
    is the most likely thing a text search finds, and a check that its subject
    keeps failing gets deleted rather than believed.
    """
    import ast

    tree = ast.parse(Path(aggregates.__file__).read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr):
            first = body[0].value
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                docstrings.add(id(first))
    offenders = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
        and "trip_distance" in node.value
    ]
    offenders += [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "trip_distance"
    ]
    assert not offenders, [getattr(n, "lineno", "?") for n in offenders]


def test_month_is_a_join_key_and_never_reaches_the_matrix():
    df = two_month_frame()
    matrix = build_features(df, sets.resolve_set("v1_g5"), fitted=aggregates.fit(df, TARGET))
    assert "month" not in matrix.columns
    assert not (set(matrix.columns) & EXCLUDED_COLUMNS)


def test_calendar_near_window_excludes_the_holidays_themselves():
    loaded = calendar.load_calendar()
    assert not (loaded.holidays & loaded.near)
    assert 2019 in loaded.years


# --------------------------------------------------------------------------
# The artisan track promotes nothing (M3 kickoff, M3-S3: "the registry API stays
# out of this story's diff")
# --------------------------------------------------------------------------

#: Every mutating registry call this program has ever made, plus the client that
#: makes them. Named individually rather than matched on "registry", because the
#: word appears in this codebase's prose constantly (the EXCLUSION registry, the
#: feature-set registry) and a substring check would be green for the wrong reason.
_REGISTRY_API = (
    "MlflowClient",
    "set_registered_model_alias",
    "delete_registered_model_alias",
    "create_registered_model",
    "create_model_version",
    "register_model",
    "transition_model_version_stage",
)


def test_the_artisan_track_never_touches_the_model_registry():
    """v2 is measured and logged; the alias moves at M3-S5 or not at all."""
    paths = [
        Path("scripts/artisan_ablation.py"),
        Path("scripts/leakage_redteam.py"),
        *sorted(Path("src/taxi_mlops/features").glob("*.py")),
    ]
    offenders = {}
    for path in paths:
        hits = [name for name in _REGISTRY_API if name in path.read_text(encoding="utf-8")]
        if hits:
            offenders[str(path)] = hits
    assert not offenders, (
        f"{offenders} — M3-S3 measures and logs; nothing in the artisan track may "
        "register a model or move an alias."
    )
