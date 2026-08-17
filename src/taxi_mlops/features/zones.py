"""Zone geometry — the quote-time substitute for the meter's driven distance.

Design Review **DR-04** (2026-08-17): `trip_distance` stays excluded and the
zone-centroid haversine is what replaces it. That decision rests on a
measurement, not a preference — over 43,439,267 train rows the meter's driven
distance correlates with the target at 0.8068 and the centroid straight line at
**0.7873**, so the legal feature keeps 97.6% of the forbidden one's power and can
actually be served (`docs/feature_dossier.md` §3).

Everything here is a lookup on the two zone ids a quote request already carries.
Nothing is measured during the trip, so nothing here can leak: the table is
`data/reference/taxi_zone_centroids.csv`, derived by `make zones` from the
sha256-pinned TLC shapefile and committed.

**Zones 264 and 265 have no centroid, and that is DR-04 condition 1.** They are
TLC's "Unknown" — not places — so `make zones` gives them no row on purpose, and
264->264 is the largest single OD "route" in the data. The named fallback is:

    every geometric feature is NaN, and `has_geometry` is 0.

NaN and not an invented coordinate, because LightGBM has a documented missing
branch and a made-up midpoint of Manhattan would be a number the model would
learn to trust. `has_geometry` rides along so the split is one the tree can make
explicitly rather than having to infer from nine simultaneous NaNs. Measured
share of rows on that path: train 1.2462% · val 1.0113% · test 1.0753% — and
`docs/error_memo_m2.md` §1 is the standing warning that the small fraction is
where the value lives (the ~1.48% unseen-OD rows buy 75.4% of the champion's
whole advantage). Pinned by tests, not by this docstring.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

CENTROID_TABLE = "data/reference/taxi_zone_centroids.csv"
ZONE_LOOKUP_TABLE = "data/reference/taxi_zone_lookup.csv"

#: The TLC ids with no geometry. Not a magic pair: `make zones` emits rows for
#: 1..263 and these two are the "Unknown" zones the shapefile does not draw.
UNKNOWN_ZONES = (264, 265)

#: Highest id the lookup arrays are sized for. TLC ids are dense 1..265.
MAX_ZONE_ID = 265

#: How the shipped lookup spells "this id is not a place". TWO spellings, one
#: meaning: 264 carries Borough "Unknown", 265 carries "N/A". Read from the
#: committed file, not assumed — and folded onto one code in `load_zone_table`.
NOT_A_PLACE_BOROUGHS = frozenset({"Unknown", "N/A", "nan", ""})

#: Airport zones, confirmed against the shapefile's own `zone` field at M3-S2
#: (`docs/feature_dossier.md` row 12). The sources had to INFER airports by
#: clustering coordinates; a zone id names them exactly, which is one of the few
#: places our data shape is better than the competition's.
AIRPORT_ZONES = {132: "JFK", 138: "LGA", 1: "EWR"}

EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class ZoneTable:
    """Centroids and boroughs indexed by TLC LocationID, NaN where there is none."""

    lat: np.ndarray  # float64[MAX_ZONE_ID + 1], NaN for 0 / 264 / 265
    lon: np.ndarray
    borough_code: np.ndarray  # int16[MAX_ZONE_ID + 1]
    boroughs: tuple[str, ...]  # code -> name, index 0 is "Unknown"

    def has_geometry(self, ids: np.ndarray) -> np.ndarray:
        return ~np.isnan(self.lat[ids])


def _clip_ids(values: pd.Series) -> np.ndarray:
    """Zone ids as safe array indices.

    A row whose id is outside 1..265 cannot exist under the data contract
    (`configs/data.yaml` bounds it), but this is an ARRAY INDEX: an out-of-range
    id would silently read a neighbouring zone's centroid rather than raise, and
    a wrong coordinate is invisible where a crash is not. Out-of-range lands on
    index 0, whose centroid is NaN — the same named path as 264/265.
    """
    ids = values.to_numpy(dtype="int64", copy=True)
    ids[(ids < 1) | (ids > MAX_ZONE_ID)] = 0
    return ids


@lru_cache(maxsize=4)
def load_zone_table(
    centroids: str = CENTROID_TABLE, lookup: str = ZONE_LOOKUP_TABLE
) -> ZoneTable:
    """Read the committed centroid table into index-by-id arrays.

    Cached because it is read once per feature build and is 263 rows; the cache
    key is the path, so a test may point it somewhere else.
    """
    path = Path(centroids)
    if not path.exists():
        raise FileNotFoundError(
            f"{centroids} is missing — run `make zones` (M3-S2). Every spatial feature "
            "in feature set v2 is a lookup on this table."
        )
    frame = pd.read_csv(path)
    lat = np.full(MAX_ZONE_ID + 1, np.nan, dtype="float64")
    lon = np.full(MAX_ZONE_ID + 1, np.nan, dtype="float64")
    ids = frame["location_id"].to_numpy(dtype="int64")
    lat[ids] = frame["centroid_lat"].to_numpy(dtype="float64")
    lon[ids] = frame["centroid_lon"].to_numpy(dtype="float64")

    # Boroughs come from the lookup CSV rather than the centroid table, because
    # it is the one that has a row for 264/265 — and a borough IS defined for
    # them, which is exactly what makes borough_pair the coarse backoff dossier
    # row 13 argues for: it exists for every OD pair.
    #
    # The two non-places are spelled DIFFERENTLY in the shipped file: 264 is
    # Borough "Unknown" and 265 is Borough "N/A" (read live 2026-08-17). Both
    # mean the same thing, so they are folded onto the ONE Unknown code —
    # DR-04 condition 1 asks each spatial feature for a single named fallback
    # for the non-places, and two codes would make borough_pair carry two
    # categories that mean "we do not know" while looking like two boroughs.
    names = ["Unknown"]
    codes = np.zeros(MAX_ZONE_ID + 1, dtype="int16")
    lookup_frame = pd.read_csv(lookup)
    for _, row in lookup_frame.iterrows():
        borough = str(row["Borough"]).strip()
        if borough in NOT_A_PLACE_BOROUGHS:
            borough = "Unknown"
        if borough not in names:
            names.append(borough)
        location_id = int(row["LocationID"])
        if 1 <= location_id <= MAX_ZONE_ID:
            codes[location_id] = names.index(borough)
    return ZoneTable(lat=lat, lon=lon, borough_code=codes, boroughs=tuple(names))


def _haversine_km(
    lat1: np.ndarray, lon1: np.ndarray, lat2: np.ndarray, lon2: np.ndarray
) -> np.ndarray:
    """Great-circle distance in km. NaN in, NaN out — that is the 264/265 path."""
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = phi2 - phi1
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2.0) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def _bearing_deg(
    lat1: np.ndarray, lon1: np.ndarray, lat2: np.ndarray, lon2: np.ndarray
) -> np.ndarray:
    """Initial bearing, degrees clockwise from north, 0-360.

    Direction matters because Manhattan is anisotropic: crosstown is slower than
    uptown for the same distance (artisan playbook §1 lesson 2). A tree can only
    use that if it is given the angle.
    """
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dlambda = np.radians(lon2 - lon1)
    y = np.sin(dlambda) * np.cos(phi2)
    x = np.cos(phi1) * np.sin(phi2) - np.sin(phi1) * np.cos(phi2) * np.cos(dlambda)
    return (np.degrees(np.arctan2(y, x)) + 360.0) % 360.0


@dataclass(frozen=True)
class Geometry:
    """Every centroid-derived quantity for one frame, computed once and shared.

    One object because the nine features of `g2_centroid_geometry` share the same
    four coordinate lookups; computing them nine times over 44M rows would be the
    same numbers at nine times the cost.
    """

    haversine_km: np.ndarray
    dlat_km: np.ndarray
    dlon_km: np.ndarray
    manhattan_km: np.ndarray
    bearing_deg: np.ndarray
    midpoint_lat: np.ndarray
    midpoint_lon: np.ndarray
    has_geometry: np.ndarray


def geometry(pu: pd.Series, do: pd.Series, table: ZoneTable | None = None) -> Geometry:
    """Centroid geometry for a frame of (pickup zone, dropoff zone) pairs."""
    table = table or load_zone_table()
    pu_ids, do_ids = _clip_ids(pu), _clip_ids(do)
    lat1, lon1 = table.lat[pu_ids], table.lon[pu_ids]
    lat2, lon2 = table.lat[do_ids], table.lon[do_ids]

    haversine = _haversine_km(lat1, lon1, lat2, lon2)
    # The two legs of the L a taxi actually drives: north-south at the origin's
    # longitude, then east-west at the destination's latitude. A cab cannot fly,
    # and on a grid the sum of the legs is closer to the truth than the diagonal
    # (dossier row 8). Signed, because "which way" is information the magnitude
    # throws away.
    dlat = np.copysign(_haversine_km(lat1, lon1, lat2, lon1), lat2 - lat1)
    dlon = np.copysign(_haversine_km(lat2, lon1, lat2, lon2), lon2 - lon1)
    return Geometry(
        haversine_km=haversine,
        dlat_km=dlat,
        dlon_km=dlon,
        manhattan_km=np.abs(dlat) + np.abs(dlon),
        bearing_deg=_bearing_deg(lat1, lon1, lat2, lon2),
        midpoint_lat=(lat1 + lat2) / 2.0,
        midpoint_lon=(lon1 + lon2) / 2.0,
        has_geometry=(~np.isnan(haversine)).astype("int16"),
    )


def borough_codes(values: pd.Series, table: ZoneTable | None = None) -> np.ndarray:
    """Borough code per row. Defined for EVERY id, including 264/265 ("Unknown")."""
    table = table or load_zone_table()
    return table.borough_code[_clip_ids(values)]


def airport_flags(values: pd.Series) -> np.ndarray:
    """1 where the zone is JFK / LGA / EWR."""
    ids = _clip_ids(values)
    flags = np.zeros(MAX_ZONE_ID + 1, dtype="int16")
    for zone_id in AIRPORT_ZONES:
        flags[zone_id] = 1
    return flags[ids]
