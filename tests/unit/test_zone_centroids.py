"""M3-S2: the zone-centroid artifact's cluster-free invariants.

The committed `data/reference/taxi_zone_centroids.csv` is the geometry source
for every distance/bearing feature M3-S3 will build and for the same features at
serving time (M5). It is a DERIVED file that is nevertheless committed, which is
exactly the arrangement that rots: somebody hand-edits a row, or the TLC moves
the shapefile, and nothing notices because the CSV still parses.

So the load-bearing test here is a TWIN: re-derive the whole table from the
committed zip and demand the committed CSV back, byte for byte. That is the
same argument `make rebuild-proof` makes about `data/processed`, at 263-row
scale — and it costs about a second, so it runs in CI on every push, with no
network and no cluster.

Each test's docstring names the failure it prevents.
"""

import ast
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
REF = REPO / "data" / "reference"
CENTROIDS = REF / "taxi_zone_centroids.csv"
MANIFEST = REF / "reference_manifest.json"
ZIP = REF / "taxi_zones.zip"
LOOKUP = REF / "taxi_zone_lookup.csv"
SCRIPT = REPO / "scripts" / "derive_zone_centroids.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("derive_zone_centroids", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def rows():
    with CENTROIDS.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture(scope="module")
def manifest():
    return json.loads(MANIFEST.read_text())


pytestmark = pytest.mark.unit


def test_the_sources_and_the_derived_table_match_their_pinned_digests(manifest):
    """Prevents: the TLC edits the shapefile in place (gotcha #6's exact shape) or
    somebody hand-edits the CSV, and every downstream distance silently moves."""
    for name in ("taxi_zones.zip", "taxi_zone_lookup.csv", "taxi_zone_centroids.csv"):
        path = REF / name
        assert path.exists(), f"{name} is missing — the manifest pins a file that is not here"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == manifest["files"][name]["sha256"], f"{name} does not match its pin"
        assert path.stat().st_size == manifest["files"][name]["bytes"]


def test_the_manifest_carries_no_timestamp(manifest):
    """Prevents: the manifest diffing on every run, which trains readers to ignore
    its diffs — the one signal that says the upstream bytes moved."""

    # KEYS, not prose: the manifest's own `_note` explains that it is timestamp-free,
    # and a check that reads the explanation as a violation is a check nobody keeps.
    def keys(node):
        if isinstance(node, dict):
            for k, v in node.items():
                yield k.lower()
                yield from keys(v)

    found = set(keys(manifest))
    for word in ("timestamp", "generated_at", "fetched_at", "date", "run_at"):
        assert not any(word in k for k in found), (
            f"manifest carries a {word} key — a diff must mean the bytes moved"
        )


def test_the_committed_table_re_derives_from_the_committed_shapefile(tmp_path, monkeypatch, rows):
    """Prevents: the committed CSV drifting from what the script actually produces —
    a hand-edited coordinate, a half-finished refactor, a stale table after a
    projection change. This is the artifact's `rebuild-proof`."""
    mod = _load_script()
    out = tmp_path / "taxi_zone_centroids.csv"
    monkeypatch.setattr(mod, "CENTROIDS", out)
    monkeypatch.setattr(mod, "MANIFEST", tmp_path / "reference_manifest.json")
    assert mod.derive(refresh=False) == 0, "the derivation refused on the committed inputs"
    assert out.read_bytes() == CENTROIDS.read_bytes(), (
        "re-deriving from the committed zip did not reproduce the committed CSV byte for byte"
    )


def test_every_zone_the_trip_data_can_name_is_present_exactly_once(rows):
    """Prevents: a partial table. A missing zone does not crash a join — it makes a
    row's distance NULL, and a feature that is silently null for some zones is
    worse than one that is absent for all."""
    ids = [int(r["location_id"]) for r in rows]
    assert len(ids) == 263
    assert sorted(ids) == list(range(1, 264))


def test_the_unknown_zones_264_and_265_have_no_row(rows):
    """Prevents: inventing a location for TLC's two 'Unknown' codes. They are not
    places (docs/eda_report.md), and 264->264 is the single largest OD 'route' in
    the data — giving them a centroid would put a confident distance on the rows
    that have no geometry at all. S3 owes them an explicit fallback, not a guess."""
    ids = {int(r["location_id"]) for r in rows}
    assert 264 not in ids and 265 not in ids


def test_the_airport_zones_land_on_their_airports(rows):
    """Prevents: a wrong CRS. The shapefile is in feet on a Lambert projection; read
    it as anything else and every centroid moves together, which no internal
    consistency check can see. Airports have published positions this repo did not
    author, so they are the outside witness."""
    mod = _load_script()
    by_id = {int(r["location_id"]): r for r in rows}
    for loc, (name, lat, lon) in mod.LANDMARKS.items():
        r = by_id[loc]
        d = mod.haversine_km(float(r["centroid_lat"]), float(r["centroid_lon"]), lat, lon)
        assert d <= mod.LANDMARK_TOLERANCE_KM, (
            f"zone {loc} ({name}) is {d:.2f} km from its published position"
        )


def test_every_centroid_is_inside_the_nyc_metro_box(rows):
    """Prevents: a single zone escaping (a swapped lat/lon on one row puts it in
    Antarctica; a sign flip puts it in China) while the table still looks fine."""
    mod = _load_script()
    lon_min, lat_min, lon_max, lat_max = mod.NYC_BBOX
    for r in rows:
        lat, lon = float(r["centroid_lat"]), float(r["centroid_lon"])
        assert lat_min <= lat <= lat_max and lon_min <= lon <= lon_max, (
            f"zone {r['location_id']} is outside NYC"
        )


def test_the_derivation_refuses_rather_than_writing_a_wrong_table(tmp_path, monkeypatch):
    """Prevents: the failure mode this whole file exists for — a check that observes
    a problem and writes the file anyway. Move a landmark's truth far enough and
    the script must exit 1 AND leave no output behind."""
    mod = _load_script()
    out = tmp_path / "taxi_zone_centroids.csv"
    monkeypatch.setattr(mod, "CENTROIDS", out)
    monkeypatch.setattr(mod, "MANIFEST", tmp_path / "reference_manifest.json")
    monkeypatch.setattr(mod, "LANDMARKS", {132: ("JFK Airport", 0.0, 0.0)})
    assert mod.derive(refresh=False) == 1, "a landmark 8,000 km out did not turn the derivation RED"
    assert not out.exists(), "the derivation wrote its table despite failing its own check"


def test_a_hole_in_a_polygon_pulls_the_centroid_the_way_a_hole_should(rows):
    """Prevents: the ring-orientation bug. Summing ring areas as absolutes instead of
    signed makes an interior hole ADD weight where there is no land. A 10x10 square
    with its right half hollowed must have its centroid left of the square's middle."""
    mod = _load_script()

    outer_ccw = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
    hole_cw = [(6, 2), (6, 8), (9, 8), (9, 2), (6, 2)]

    class _Shape:
        parts = [0, len(outer_ccw)]
        points = outer_ccw + hole_cw

    cx, cy, area = mod.polygon_centroid(_Shape())
    assert area == pytest.approx(100 - 18)
    assert cy == pytest.approx(5.0)
    assert cx < 5.0, "the hole did not subtract — rings are being summed unsigned"


def test_haversine_agrees_with_a_known_distance():
    """Prevents: a silently broken distance helper, which would make every check in
    this file agree with itself and with nothing else. JFK to LaGuardia is ~17 km."""
    mod = _load_script()
    d = mod.haversine_km(40.6446, -73.7797, 40.7742, -73.8724)
    assert 15.0 < d < 19.0, f"JFK->LGA came back {d:.2f} km"
    assert mod.haversine_km(40.7, -74.0, 40.7, -74.0) == pytest.approx(0.0, abs=1e-9)


def test_the_projection_is_read_from_the_shapefile_and_never_hardcoded():
    """Prevents: the twins trap on the coordinate system. An `EPSG:2263` literal in
    the script would be a second definition of the projection, and if TLC ever
    reprojects the file the literal wins silently and every centroid moves."""
    src = SCRIPT.read_text()
    assert "from_wkt" in src, "the CRS must come from the .prj inside the zip"

    # Look at CODE, not at comments or docstrings. The script's own header argues
    # at length about why "EPSG:2263" is not written down; a substring scan over
    # the raw file would flag that argument as the offence it warns against.
    tree = ast.parse(src)
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or id(node) in docstrings:
            continue
        if isinstance(node.value, str) and "2263" in node.value:
            pytest.fail(
                f"the projection is hardcoded as a string ({node.value!r}) — read it from the .prj"
            )
        if isinstance(node.value, int) and node.value == 2263:
            pytest.fail("the projection is hardcoded as EPSG 2263 — read it from the .prj")


def test_areas_are_re_derived_and_the_shipped_dbf_areas_are_not_trusted(rows):
    """Prevents: adopting the .dbf's Shape_Area, which was read live 2026-08-17
    carrying values like 0.00078 for zones whose own coordinates are in feet — i.e.
    computed in some other CRS. Our areas must be plausible in km^2."""
    areas = sorted(float(r["area_sqkm"]) for r in rows)
    assert areas[0] > 0.0
    assert 0.1 < areas[len(areas) // 2] < 20.0, "median zone area is not plausible in km^2"
    assert sum(areas) > 700.0, (
        "the 263 zones should cover roughly NYC's ~1,200 km^2 land+water extent"
    )


def test_the_script_names_a_derivation_for_every_derived_file(manifest):
    """Prevents: an artifact whose provenance is a memory. Anything derived must say
    what it came from and what made it."""
    derived = manifest["files"]["taxi_zone_centroids.csv"]
    assert derived["derived_by"] == "scripts/derive_zone_centroids.py"
    assert set(derived["derived_from"]) == {"taxi_zones.zip", "taxi_zone_lookup.csv"}
    assert math.isfinite(manifest["zones"]) and manifest["zones"] == 263
