#!/usr/bin/env python
"""Derive the TLC taxi-zone centroid table — the quote-time geometry source (M3-S2).

WHY THIS EXISTS
---------------
2019 TLC trip files carry `PULocationID`/`DOLocationID` — zone ids, not
coordinates. Every distance/bearing idea in the community record
(`docs/artisan_playbook.md` §2, `docs/feature_dossier.md`) is written against
lat/lon, so it cannot be transferred without a zone -> point mapping. This
script builds that mapping ONCE from the authoritative TLC shapefile, and the
result is committed so training (M3-S3) and serving (M5) read the SAME 263 rows.

F-007(b): `trip_distance` is the meter's DRIVEN distance and a serving request
does not have it. The centroid table is what makes a *quote-time* distance
possible at all, so this artifact is the finding's answer, not a convenience.

THE RULES THIS FILE OBEYS
-------------------------
* **The CRS is READ, never assumed.** The .prj inside the zip is handed to
  pyproj verbatim. Hardcoding "EPSG:2263" would be a second definition of the
  projection one directory from the first (the port-family twins lesson), and a
  silently wrong one would move every centroid a few hundred metres — a shift
  small enough to look like data and large enough to poison a distance feature.
* **Centroids are computed in the PROJECTED plane, then transformed.** An
  area-weighted centroid taken in degrees is distorted by the cos(latitude)
  scaling. Feet first, degrees after.
* **Holes subtract themselves.** The signed-area (shoelace) accumulation over
  every ring handles interior rings by orientation, which is what the shapefile
  spec already encodes; no ring is special-cased.
* **The downloads are sha256-pinned, timestamp-free** (`raw_manifest.json`'s
  pattern): a diff in the manifest means the BYTES moved, not that somebody
  re-fetched. TLC edits files in place (gotcha #6), and this one is the
  coordinate system under every spatial feature M3 is about to build.
* **`Shape_Area`/`Shape_Leng` in the .dbf are IGNORED.** Read live 2026-08-17
  they carry values like 0.00078 for a zone whose own coordinates are in feet —
  i.e. they were computed in some other CRS and shipped anyway. Areas here are
  re-derived from the geometry.

Run: `make zones` (or `uv run python scripts/derive_zone_centroids.py`).
`--refresh` re-downloads; without it, pinned local bytes are used and verified.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sys
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REF = REPO / "data" / "reference"
ZIP = REF / "taxi_zones.zip"
LOOKUP = REF / "taxi_zone_lookup.csv"
MANIFEST = REF / "reference_manifest.json"
CENTROIDS = REF / "taxi_zone_centroids.csv"

SOURCES = {
    "taxi_zones.zip": "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip",
    "taxi_zone_lookup.csv": "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv",
}

# Inside the zip. Named, not globbed: a second .shp appearing one day should be
# a loud KeyError, not a silent choice between two geometries.
SHP = "taxi_zones/taxi_zones.shp"
DBF = "taxi_zones/taxi_zones.dbf"
PRJ = "taxi_zones/taxi_zones.prj"

# Landmarks whose true position is public knowledge and independent of this
# repo. They are the check that catches a wrong CRS: a projection error puts
# JFK in the water, and no amount of internal consistency notices.
LANDMARKS = {
    132: ("JFK Airport", 40.6446, -73.7797),
    138: ("LaGuardia Airport", 40.7742, -73.8724),
    1: ("Newark Airport", 40.6895, -74.1745),
}
LANDMARK_TOLERANCE_KM = 3.0  # a centroid is not a terminal building; 3 km is "same airport"

# Every zone must land inside a generous NYC-metro box. Cheap, and it fails
# loudly on the class of bug that shifts everything at once.
NYC_BBOX = (-74.30, 40.45, -73.65, 40.95)  # lon_min, lat_min, lon_max, lat_max

EARTH_RADIUS_KM = 6371.0088


def _display(path: Path) -> str:
    """Repo-relative when it is in the repo, absolute otherwise — the unit test
    redirects the outputs to a tmpdir, and a progress line must never be the
    reason a run fails."""
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download(name: str, dest: Path) -> None:
    url = SOURCES[name]
    print(f"[zones] downloading {name} <- {url}")
    with urllib.request.urlopen(url, timeout=120) as resp:  # noqa: S310 (pinned https literal)
        dest.write_bytes(resp.read())


def ring_area_and_centroid(points: list[tuple[float, float]]) -> tuple[float, float, float]:
    """Signed area and area-weighted centroid of one closed ring (shoelace).

    Returns (signed_area, cx * signed_area, cy * signed_area) already weighted,
    so the caller sums numerators and denominator independently. Sign carries
    the ring's orientation, which is how interior rings (holes) subtract.
    """
    a2 = 0.0
    cx = 0.0
    cy = 0.0
    for (x0, y0), (x1, y1) in zip(points, points[1:], strict=False):
        cross = x0 * y1 - x1 * y0
        a2 += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    area = a2 / 2.0
    if a2 == 0.0:
        # Degenerate ring (zero area): contributes nothing, and must not divide.
        return 0.0, 0.0, 0.0
    return area, cx / 6.0, cy / 6.0


def polygon_centroid(shape) -> tuple[float, float, float]:
    """Area-weighted centroid over every ring of a (multi)polygon, in shape units."""
    parts = list(shape.parts) + [len(shape.points)]
    total_area = 0.0
    num_x = 0.0
    num_y = 0.0
    for start, end in zip(parts, parts[1:], strict=False):
        ring = [(float(x), float(y)) for x, y in shape.points[start:end]]
        if len(ring) < 4:  # fewer than 3 distinct vertices + closure
            continue
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        area, wx, wy = ring_area_and_centroid(ring)
        total_area += area
        num_x += wx
        num_y += wy
    if total_area == 0.0:
        raise ValueError("polygon has zero total area — geometry is unusable")
    return num_x / total_area, num_y / total_area, abs(total_area)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def read_lookup() -> dict[int, tuple[str, str]]:
    """TLC's own (LocationID -> Borough, Zone) table — an INDEPENDENT witness."""
    out: dict[int, tuple[str, str]] = {}
    with LOOKUP.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[int(row["LocationID"])] = (row["Borough"].strip(), row["Zone"].strip())
    return out


def derive(refresh: bool) -> int:
    REF.mkdir(parents=True, exist_ok=True)
    for name, dest in (("taxi_zones.zip", ZIP), ("taxi_zone_lookup.csv", LOOKUP)):
        if refresh or not dest.exists():
            download(name, dest)

    import shapefile  # pyshp
    from pyproj import CRS, Transformer

    digests = {
        name: sha256_of(p)
        for name, p in (("taxi_zones.zip", ZIP), ("taxi_zone_lookup.csv", LOOKUP))
    }
    for name, digest in digests.items():
        print(f"[zones] {name}: {digest} ({(REF / name).stat().st_size:,} bytes)")

    zf = zipfile.ZipFile(ZIP)
    prj_wkt = zf.read(PRJ).decode("utf-8").strip()
    source_crs = CRS.from_wkt(prj_wkt)
    print(f"[zones] CRS read from {PRJ}: {source_crs.name}")
    to_wgs84 = Transformer.from_crs(source_crs, CRS.from_epsg(4326), always_xy=True)

    reader = shapefile.Reader(shp=io.BytesIO(zf.read(SHP)), dbf=io.BytesIO(zf.read(DBF)))
    lookup = read_lookup()

    rows = []
    disagreements = []
    # strict=True on purpose: a .dbf and .shp of different lengths is a corrupt
    # shapefile, and zip's default would silently truncate to the shorter one —
    # i.e. drop zones and still write a table that passes every count it knows.
    for rec, shape in zip(reader.records(), reader.shapes(), strict=True):
        loc = int(rec["LocationID"])
        x, y, area_sqft = polygon_centroid(shape)
        lon, lat = to_wgs84.transform(x, y)
        borough = str(rec["borough"]).strip()
        zone = str(rec["zone"]).strip()
        if loc in lookup and lookup[loc] != (borough, zone):
            disagreements.append((loc, (borough, zone), lookup[loc]))
        rows.append(
            {
                "location_id": loc,
                "borough": borough,
                "zone": zone,
                "centroid_lat": round(lat, 6),
                "centroid_lon": round(lon, 6),
                "area_sqkm": round(area_sqft * 0.09290304 / 1e6, 6),
                "n_parts": len(shape.parts),
            }
        )
    rows.sort(key=lambda r: r["location_id"])

    # ---- checks that can fail, printed either way -------------------------
    failures: list[str] = []

    ids = [r["location_id"] for r in rows]
    print(
        f"[zones] shapes: {len(rows)} · LocationID {min(ids)}..{max(ids)} · unique {len(set(ids))}"
    )
    if len(rows) != 263 or sorted(set(ids)) != list(range(1, 264)):
        failures.append(f"expected exactly LocationID 1..263, got {len(rows)} ids")

    # The DBF and TLC's lookup CSV are two files published separately. Agreement
    # is evidence; disagreement means one of them moved and we must look.
    if disagreements:
        failures.append(
            f"{len(disagreements)} zone(s) disagree between the .dbf and taxi_zone_lookup.csv"
        )
        for loc, dbf_v, csv_v in disagreements[:5]:
            print(f"[zones] FAIL zone {loc}: dbf={dbf_v} lookup={csv_v}")
    else:
        print(
            f"[zones] .dbf and taxi_zone_lookup.csv agree on borough+zone for all {len(rows)} zones"
        )

    by_id = {r["location_id"]: r for r in rows}
    for loc, (name, true_lat, true_lon) in LANDMARKS.items():
        r = by_id[loc]
        d = haversine_km(r["centroid_lat"], r["centroid_lon"], true_lat, true_lon)
        verdict = "ok" if d <= LANDMARK_TOLERANCE_KM else "FAIL"
        print(
            f"[zones] {verdict} landmark {loc} {name}: derived "
            f"({r['centroid_lat']:.5f}, {r['centroid_lon']:.5f}) is "
            f"{d:.2f} km from the published point"
        )
        if d > LANDMARK_TOLERANCE_KM:
            failures.append(f"zone {loc} ({name}) is {d:.2f} km from its published position")

    lon_min, lat_min, lon_max, lat_max = NYC_BBOX
    outside = [
        r["location_id"]
        for r in rows
        if not (lon_min <= r["centroid_lon"] <= lon_max and lat_min <= r["centroid_lat"] <= lat_max)
    ]
    if outside:
        failures.append(f"{len(outside)} centroid(s) outside the NYC bbox: {outside[:10]}")
    else:
        print(f"[zones] all {len(rows)} centroids inside the NYC metro bbox {NYC_BBOX}")

    if failures:
        print("\n[zones] RED — refusing to write:")
        for f in failures:
            print(f"  - {f}")
        return 1

    with CENTROIDS.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "location_id",
                "borough",
                "zone",
                "centroid_lat",
                "centroid_lon",
                "area_sqkm",
                "n_parts",
            ],
            lineterminator="\n",
        )
        w.writeheader()
        w.writerows(rows)
    digests["taxi_zone_centroids.csv"] = sha256_of(CENTROIDS)

    MANIFEST.write_text(
        json.dumps(
            {
                "_note": (
                    "sha256 pins for the TLC taxi-zone geometry and the table derived from it. "
                    "Timestamp-free by design (raw_manifest.json's rule): a diff here means the "
                    "bytes moved. Regenerate with `make zones`."
                ),
                "crs": source_crs.name,
                "zones": len(rows),
                "files": {
                    "taxi_zones.zip": {
                        "sha256": digests["taxi_zones.zip"],
                        "bytes": ZIP.stat().st_size,
                        "url": SOURCES["taxi_zones.zip"],
                    },
                    "taxi_zone_lookup.csv": {
                        "sha256": digests["taxi_zone_lookup.csv"],
                        "bytes": LOOKUP.stat().st_size,
                        "url": SOURCES["taxi_zone_lookup.csv"],
                    },
                    "taxi_zone_centroids.csv": {
                        "sha256": digests["taxi_zone_centroids.csv"],
                        "bytes": CENTROIDS.stat().st_size,
                        "derived_from": ["taxi_zones.zip", "taxi_zone_lookup.csv"],
                        "derived_by": "scripts/derive_zone_centroids.py",
                    },
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    print(f"[zones] wrote {_display(CENTROIDS)} ({len(rows)} rows) and {_display(MANIFEST)}")
    print("[zones] GREEN — every check passed.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--refresh", action="store_true", help="re-download the TLC sources before deriving"
    )
    args = ap.parse_args()
    return derive(refresh=args.refresh)


if __name__ == "__main__":
    sys.exit(main())
