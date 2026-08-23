"""Does the wall's door change anything? The feature server's answers vs the champion's own lookup.

M8-S4 leg 2. A READER: it deploys nothing, materializes nothing, moves no alias
and writes no feature. It stands up an ephemeral `kubectl port-forward` to the
in-cluster feature server, asks it for the stored lookups belonging to the 16
declared parity hazards, and compares every answer against the functions
`quote_time.build_features` itself calls.

**THE BAR IS EXACT AND IT WAS ARGUED FIRST** — `docs/feast_server_m8.md` §3,
committed before this script produced any record (M8 law 4's ordering, checkable
from git). One sentence of it, because it is the whole reason a float bar would
be a hedge here: nothing on the server's side of the wall performs arithmetic,
and the only new hop against leg 1 is JSON, whose number grammar carries a
float64 losslessly because every encoder in this stack emits Python's
shortest-round-trip repr.

**WHY THE ANCHOR IS `taxi_mlops.features` AND NOT THE OFFLINE STORE.** Comparing
the feature server against the parquet it was materialized from would be two
Feast reads agreeing with each other. The question that matters is narrower and
harder: *if the transformer takes these values from the store instead of from the
committed tables, does the champion see the same matrix?* So the anchor is the
committed table — the thing the champion was fitted against and is served
against today.

**`one missing` IS THE LOAD-BEARING COUNT.** `NaN != NaN`, so a comparison that
quietly dropped nulls would print a perfect 0.000e+00 while being blind to the
~1% of rows that carry no geometry at all — the class F-030 was found on, and
the class this store answers `null` for on purpose. One side missing where the
other has a value is a MISMATCH, counted and named.

**Pairing is BY NAME, never by position.** The feature server does not preserve
the request's column order (observed on the accept run: asked for
`centroid_lat, centroid_lon, is_airport`, answered
`zone_id, centroid_lat, is_airport, centroid_lon`). A client that zipped by
position would send individually-valid values under each other's names — which is
exactly arm A of `make parity-redteam`, self-inflicted.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from taxi_mlops.features import calendar as calendar_mod  # noqa: E402
from taxi_mlops.features import zones as zones_mod  # noqa: E402
from taxi_mlops.serving.parity import HAZARDS  # noqa: E402

#: The bar. Not a tolerance — an assertion of identity. See the module docstring
#: and docs/feast_server_m8.md §3 for why anything looser would be a hedge.
TOLERANCE = 0.0

RECORD = REPO / "automation" / "runs" / "m8-transformer" / "server-parity.json"
TABLE = REPO / "docs" / "feast_server_parity_table.md"

#: The stored columns this comparison covers, and — deliberately — `borough` is
#: NOT among them. `docs/feast_server_m8.md` §5: the champion eats a borough
#: CODE whose value depends on the whole lookup table's iteration order, so it is
#: an ENCODING rather than a per-entity value and cannot be reconstructed from a
#: store that (correctly) holds the string. Comparing the string against the code
#: would be comparing two different things and calling the difference a defect.
ZONE_FEATURES = ("centroid_lat", "centroid_lon", "is_airport")
DAY_FEATURES = ("is_holiday", "is_near_holiday", "is_business_day")


@dataclass
class Column:
    name: str
    entity: str
    compared: int = 0
    mismatched: int = 0
    one_missing: int = 0
    max_delta: float = 0.0
    worst: str = ""

    def observe(self, key: Any, ours: Any, theirs: Any) -> None:
        self.compared += 1
        ours_missing = ours is None or (isinstance(ours, float) and math.isnan(ours))
        theirs_missing = theirs is None or (isinstance(theirs, float) and math.isnan(theirs))
        if ours_missing and theirs_missing:
            return
        if ours_missing != theirs_missing:
            self.one_missing += 1
            self.mismatched += 1
            self.worst = (
                f"{self.entity}={key}: ours={'missing' if ours_missing else ours!r}, "
                f"store={'missing' if theirs_missing else theirs!r}"
            )
            return
        if isinstance(ours, bool) or isinstance(theirs, bool):
            if bool(ours) != bool(theirs):
                self.mismatched += 1
                self.worst = f"{self.entity}={key}: ours={ours!r}, store={theirs!r}"
            return
        delta = abs(float(ours) - float(theirs))
        if delta > self.max_delta:
            self.max_delta = delta
            if delta > TOLERANCE:
                self.worst = f"{self.entity}={key}: ours={ours!r}, store={theirs!r}, d={delta:.3e}"
        if delta > TOLERANCE:
            self.mismatched += 1


def _post(url: str, body: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
    data = json.dumps(body).encode()
    request = urllib.request.Request(  # noqa: S310 — a fixed localhost forward
        url, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read())


def online(url: str, features: list[str], entities: dict[str, list[Any]]) -> dict[str, list[Any]]:
    """Ask the feature server, and hand back a BY-NAME mapping.

    The by-name rebuild is the point: the server's `metadata.feature_names` is
    the authority on which result column is which, and it is not the order the
    request asked in.
    """
    payload = _post(f"{url}/get-online-features", {"features": features, "entities": entities})
    names = payload["metadata"]["feature_names"]
    results = payload["results"]
    if len(names) != len(results):
        raise RuntimeError(
            f"the server named {len(names)} columns and returned {len(results)} result "
            "blocks — pairing by name is impossible, so nothing is compared"
        )
    return {name: block["values"] for name, block in zip(names, results, strict=True)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=None, help="an already-running feature server")
    parser.add_argument("--port", type=int, default=6567, help="local port for the forward")
    parser.add_argument("--no-write", action="store_true", help="print, record nothing")
    args = parser.parse_args()

    forward = None
    url = args.url
    if url is None:
        # Deliberately NOT 6566: the same reasoning as the store's 6380 forward.
        # A local port that collides with the service's own conventional port is
        # a way for a probe to end up talking to something that is not under test.
        forward = subprocess.Popen(  # noqa: S603
            ["kubectl", "-n", "feast", "port-forward", "svc/feast-server", f"{args.port}:6566"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        url = f"http://127.0.0.1:{args.port}"

    try:
        ready = False
        for _ in range(40):
            try:
                with urllib.request.urlopen(f"{url}/health", timeout=2):  # noqa: S310
                    ready = True
                    break
            except (urllib.error.URLError, OSError):
                time.sleep(1)
        if not ready:
            print("[server-parity] FAIL: the feature server never answered /health")
            return 1
        print(f"[server-parity] feature server answers at {url}")

        zone_ids = sorted(
            {h.request.pu_location_id for h in HAZARDS}
            | {h.request.do_location_id for h in HAZARDS}
        )
        days = sorted({str(pd.Timestamp(h.request.pickup_datetime).date()) for h in HAZARDS})
        print(
            f"[server-parity] {len(HAZARDS)} declared hazards -> "
            f"{len(zone_ids)} distinct zones, {len(days)} distinct pickup dates"
        )
        print("[server-parity] bar: EXACT (docs/feast_server_m8.md §3, argued before this ran)")

        # ------------------------------------------------------- the zones ---
        stored = online(url, [f"zone_static:{f}" for f in ZONE_FEATURES], {"zone_id": zone_ids})
        table = zones_mod.load_zone_table()
        ids = np.asarray(zone_ids, dtype="int64")
        airport = zones_mod.airport_flags(pd.Series(zone_ids))
        ours_zone = {
            "centroid_lat": [None if np.isnan(v) else float(v) for v in table.lat[ids]],
            "centroid_lon": [None if np.isnan(v) else float(v) for v in table.lon[ids]],
            "is_airport": [bool(v) for v in airport],
        }

        # THE PARTITION, AND WHY THE COLUMNS ARE COMPARED ONLY OVER HALF OF IT.
        #
        # `zone_static` has a row for the 263 real zones and NO ROW for TLC's
        # non-places (264 "Unknown", 265 "N/A"). Our path is not shaped the same
        # way: `zones.load_zone_table()` answers NaN for their centroids — the
        # same fact in the same vocabulary — but `zones.airport_flags` is TOTAL,
        # a lookup into a constant array built from three integers in code, so it
        # answers a definite `False` for a zone the store has never heard of.
        #
        # The first run of this reader compared the two column-wise and went RED
        # on exactly that: `is_airport` ours=False vs store=missing for 264 and
        # 265, with every numeric column at 0.000e+00. Nothing had rounded and
        # nothing was wrong — the comparison was holding a TOTAL function against
        # a PARTIAL one and calling the difference a defect.
        #
        # So the shape is M8-S3's and leg 1's, inherited rather than reinvented:
        # partition the entities, ASSERT the partition two-sidedly (the store
        # must decline exactly the zones our path has no geometry for — and both
        # directions matter, because a store that declined a REAL zone would be a
        # missing feature, and one that answered a non-place would be inventing a
        # location at the equator), then compare columns only where both sides
        # claim to have an answer.
        no_geometry = [z for z in zone_ids if bool(np.isnan(table.lat[z]))]
        declined = [
            z
            for i, z in enumerate(zone_ids)
            if all(stored[name][i] is None for name in ZONE_FEATURES)
        ]
        print()
        if declined == no_geometry:
            print(
                f"[server-parity] ok  the store declines EXACTLY the zones our path has no "
                f"geometry for: {no_geometry} — TLC's non-places, no row on either side"
            )
        else:
            print(
                f"[server-parity] FAILthe store declines {declined} but our path has no "
                f"geometry for {no_geometry} — the two sides disagree about which zones exist"
            )

        present = [i for i, z in enumerate(zone_ids) if z not in no_geometry]
        columns: list[Column] = []
        for name in ZONE_FEATURES:
            column = Column(f"zone_static:{name}", "zone")
            for i in present:
                column.observe(zone_ids[i], ours_zone[name][i], stored[name][i])
            columns.append(column)

        # ---------------------------------------------------- the calendar ---
        # The join key is `date_key` and its format is `%Y-%m-%d` — both READ
        # from the definitions and the source builder rather than guessed. A
        # wrong join key is not a soft failure here: Feast answers HTTP 500 with
        # `Provided join_key_values: []`, i.e. it discards an unrecognised key
        # rather than complaining about it, so a plausible-looking name would
        # have produced a comparison against nothing.
        stored_day = online(
            url, [f"calendar_day_flags:{f}" for f in DAY_FEATURES], {"date_key": days}
        )
        flags = calendar_mod.flags(pd.Series([pd.Timestamp(d) for d in days]))
        for name in DAY_FEATURES:
            column = Column(f"calendar_day_flags:{name}", "day")
            ours_day = [bool(v) for v in flags[name]]
            for key, ours, theirs in zip(days, ours_day, stored_day[name], strict=True):
                column.observe(key, ours, theirs)
            columns.append(column)

        # ------------------------------------------------------- the verdict ---
        print()
        width = max(len(c.name) for c in columns)
        for c in columns:
            status = "ok  " if c.mismatched == 0 else "FAIL"
            print(
                f"[server-parity] {status}{c.name:<{width}}  compared={c.compared:>3}  "
                f"mismatched={c.mismatched}  one_missing={c.one_missing}  "
                f"max|d|={c.max_delta:.3e}"
                + (f"  <- {c.worst}" if c.worst else "")
            )

        worst = max(c.max_delta for c in columns)
        mismatched = sum(c.mismatched for c in columns)
        one_missing = sum(c.one_missing for c in columns)
        compared = sum(c.compared for c in columns)
        print()
        print(
            f"[server-parity] max |ours - server| = {worst:.3e} across {len(columns)} columns "
            f"and {compared} comparisons, bar EXACT"
        )
        print(f"[server-parity] one missing = {one_missing} (the load-bearing count)")

        partition_ok = declined == no_geometry
        if not partition_ok:
            mismatched += 1

        if not args.no_write:
            RECORD.parent.mkdir(parents=True, exist_ok=True)
            RECORD.write_text(
                json.dumps(
                    {
                        "bar": "EXACT",
                        "bar_argued_in": "docs/feast_server_m8.md §3",
                        "rows": {"zones": zone_ids, "days": days},
                        "hazards": len(HAZARDS),
                        "columns": [
                            {
                                "name": c.name,
                                "compared": c.compared,
                                "mismatched": c.mismatched,
                                "one_missing": c.one_missing,
                                "max_abs_delta": c.max_delta,
                            }
                            for c in columns
                        ],
                        "max_abs_delta": worst,
                        "mismatched": mismatched,
                        "one_missing": one_missing,
                        "no_geometry_zones": no_geometry,
                        "zones_declined_by_store": declined,
                        "partition_two_sided": partition_ok,
                        "zones_compared_columnwise": len(present),
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            print(f"[server-parity] recorded {RECORD.relative_to(REPO)}")

        if mismatched:
            print("[server-parity] RED — the door is not lossless. Investigate which side rounded.")
            return 1
        print("[server-parity] GREEN — the feature server's answers ARE the champion's own lookup.")
        return 0
    finally:
        if forward is not None:
            forward.terminate()
            forward.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
