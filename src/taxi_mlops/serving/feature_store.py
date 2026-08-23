"""The pandas-3 side of the wall: reference data fetched over HTTP, never imported.

M8-S4 leg 3. This module talks to the Feast feature server leg 2 put on the
cluster (`feast-server.feast.svc.cluster.local:6566`) and turns its answers into
a `features.lookups.Lookups` — the object `quote_time.build_features` accepts in
place of the committed CSVs.

**IT IMPORTS NO FEAST.** That is the whole point of shape (i) and it is pinned by
a test: feast 0.66.0 declares `pandas<3,>=1.4.3` against this project's 3.0.5, so
an import here would either fail or drag the wall into our lockfile. What crosses
is a JSON document over a ClusterIP Service — `urllib` and `json`, both stdlib,
which is also why `uv.lock` does not move for this story.

--------------------------------------------------------------------------
WHAT IT FETCHES, AND WHAT IT REFUSES TO
--------------------------------------------------------------------------
Two of the four reference groups, exactly as F-059 permits: the zone CENTROIDS
and the three CALENDAR flags. The borough dictionary and the airport constant are
not fetched, not requested, and not accepted — `features.lookups` argues why, and
`Lookups` has nowhere to put them.

--------------------------------------------------------------------------
THREE THINGS ABOUT THIS WIRE THAT COST SOMEBODY A DEBUGGING SESSION
--------------------------------------------------------------------------
1. **The response does not preserve the request's column order.** Asked for
   `centroid_lat, centroid_lon`, the server answered
   `zone_id, centroid_lat, is_airport, centroid_lon` on leg 2's accept run.
   Pairing is by `metadata.feature_names`, always. A client that zipped by
   position would send individually-valid values under each other's names, which
   is arm A of `make parity-redteam` — self-inflicted (gotcha #73).
2. **A wrong join key is HTTP 500, not a complaint.** Feast DISCARDS an
   unrecognised entity key and answers `Provided join_key_values: []`. So the
   keys are constants here with their format beside them, matching
   `infra/feast/feature_repo/definitions.py`.
3. **A date the store cannot answer is a REFUSAL, not a null.** See
   `calendar_from_store` — this is F-019's guarantee, and losing it silently is
   the most expensive thing this module could do.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from ..features import zones as zones_mod
from ..features.calendar import HolidayCalendar
from ..features.lookups import Lookups
from ..features.zones import MAX_ZONE_ID, ZoneTable
from .client import QuoteRefused

#: The in-cluster address. NOT a default that silently works — a pod given the
#: wrong one fails loudly (ADR-012 / F-048's rule); this constant is the address
#: the Service actually has, and the deploy asserts it against the live object.
DEFAULT_FEATURE_SERVER = "http://feast-server.feast.svc.cluster.local:6566"

#: The entity join keys, and the calendar's date format. Read from
#: `definitions.py` / `scripts/feast_sources.py` rather than guessed — see the
#: module docstring, hazard 2.
ZONE_KEY = "zone_id"
DATE_KEY = "date_key"
DATE_FORMAT = "%Y-%m-%d"

#: The stored columns that may cross the wall. `is_airport` and `borough` are
#: available from the same view and are deliberately absent (F-059).
ZONE_FEATURES = ("centroid_lat", "centroid_lon")
DAY_FEATURES = ("is_holiday", "is_near_holiday")


class FeatureStoreUnavailable(RuntimeError):
    """The feature server could not be reached or answered something unusable.

    A distinct type because the transformer must be able to tell it from a bad
    request: an unreachable store is a 503 (ours, retryable) and a request the
    store legitimately has no row for is a 422 (the caller's). Collapsing the two
    would make a dependency outage look like a malformed quote.
    """


class StoreCoverageError(QuoteRefused):
    """The store has no row for a date the request needs — F-019, one wire along.

    `QuoteRefused` and `http_status = 422` on purpose: this is exactly the shape
    of refusal `client.UncoveredDateError` carries for the committed table. The
    committed path refuses because the CSV's years do not cover the request; this
    path refuses because the STORE's rows do not. Both are "this deployment
    cannot answer that date", both are fixable, and neither may degrade into a
    quote built on invented flags.
    """

    http_status = 422


@dataclass(frozen=True)
class FeatureServer:
    """Where the quarantined feature server answers."""

    url: str = DEFAULT_FEATURE_SERVER
    timeout: float = 10.0

    def get(self, features: list[str], entities: dict[str, list[Any]]) -> dict[str, list[Any]]:
        """One `/get-online-features` call, re-keyed BY NAME.

        The by-name rebuild is not tidiness — see the module docstring, hazard 1.
        """
        body = json.dumps({"features": features, "entities": entities}).encode()
        request = urllib.request.Request(  # noqa: S310 — a fixed in-cluster Service
            f"{self.url}/get-online-features",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                payload = json.loads(response.read())
        except Exception as exc:  # noqa: BLE001 — every failure here is one class
            raise FeatureStoreUnavailable(
                f"the feature server at {self.url} did not answer: {exc!r}. "
                "The transformer builds its matrix from stored lookups and will not "
                "silently fall back to its committed tables — a quote that looks "
                "identical whether or not the store was consulted proves nothing "
                "about the store (ADR-012's own failure mode, one layer along)."
            ) from exc
        names = payload["metadata"]["feature_names"]
        results = payload["results"]
        if len(names) != len(results):
            raise FeatureStoreUnavailable(
                f"the server named {len(names)} columns and returned {len(results)} "
                "result blocks — pairing by name is impossible, so nothing is trusted"
            )
        return {name: block["values"] for name, block in zip(names, results, strict=True)}


def zone_table_from_store(
    server: FeatureServer, zone_ids: list[int], *, committed: ZoneTable | None = None
) -> ZoneTable:
    """A `ZoneTable` whose CENTROIDS come from the store and whose boroughs do not.

    The borough arrays are copied from the committed table — F-059's rule made
    structural rather than documented. The dispatch in `quote_time` reads
    boroughs off `zones.load_zone_table()` and never off this object, so the copy
    is defence in depth: a caller who misused this table would still get
    training's dictionary rather than a per-request re-numbering.

    Ids outside the requested set keep NaN centroids, which is what the committed
    table holds for zone 0 and for TLC's two non-places — the same named fallback
    (DR-04 condition 1), reached by the same code path.
    """
    committed = committed or zones_mod.load_zone_table()
    stored = server.get([f"zone_static:{f}" for f in ZONE_FEATURES], {ZONE_KEY: list(zone_ids)})

    lat = np.full(MAX_ZONE_ID + 1, np.nan, dtype="float64")
    lon = np.full(MAX_ZONE_ID + 1, np.nan, dtype="float64")
    for index, zone_id in enumerate(zone_ids):
        if not (1 <= int(zone_id) <= MAX_ZONE_ID):
            # Out of contract range. `_clip_ids` sends it to index 0, whose
            # centroid is NaN on both sides; writing it here would be an out-of
            # -bounds index on a 266-long array.
            continue
        value_lat = stored["centroid_lat"][index]
        value_lon = stored["centroid_lon"][index]
        # A null is the store's honest "no row" for 264/265 — NOT an error. It
        # stays NaN, which is exactly what the committed table holds for them and
        # what the booster was fitted to treat as missing.
        if value_lat is not None:
            lat[int(zone_id)] = float(value_lat)
        if value_lon is not None:
            lon[int(zone_id)] = float(value_lon)
    return ZoneTable(
        lat=lat, lon=lon, borough_code=committed.borough_code, boroughs=committed.boroughs
    )


def calendar_from_store(server: FeatureServer, days: list[pd.Timestamp]) -> HolidayCalendar:
    """A `HolidayCalendar` built from the store's two flags — and a REFUSAL when it cannot be.

    **`is_business_day` is deliberately not fetched even though the store has
    it.** `calendar.flags` derives it as `weekday & not-holiday`, and that
    derivation is the champion's; taking the store's copy would move a two-term
    boolean computation across the wall for no gain and give the program two
    definitions of a business day. The store supplies the two FACTS (is this date
    a federal holiday, is it adjacent to one) and our code keeps the arithmetic —
    which is the same boundary F-059 draws for the borough dictionary, in the
    direction where it costs nothing.

    **A date the store cannot answer RAISES.** F-019 established that an
    uncovered date must be refused rather than quoted with invented flags,
    because a silent `False` is indistinguishable from a correct answer and the
    feature decays into a constant. That guarantee is a property of the
    DEPLOYMENT, not of the CSV, so it has to survive the reference data moving to
    a store. `years` is therefore built from the dates the store ANSWERED, and
    every requested date is proved to be among them before this returns —
    otherwise `HolidayCalendar.assert_covers` would be handed a year set that
    contains the very date it was supposed to catch.
    """
    keys = sorted({d.strftime(DATE_FORMAT) for d in days})
    stored = server.get([f"calendar_day_flags:{f}" for f in DAY_FEATURES], {DATE_KEY: keys})

    unanswered = [
        key
        for index, key in enumerate(keys)
        if any(stored[name][index] is None for name in DAY_FEATURES)
    ]
    if unanswered:
        raise StoreCoverageError(
            f"the online feature store has no calendar row for {unanswered}. REFUSED "
            "rather than quoted: the champion eats holiday flags, and a silent "
            "'not a holiday' for an uncovered date looks exactly like a correct "
            "answer (F-019, on the store's wire instead of the CSV's). Fix it where "
            "the table is defined — `make holidays HOLIDAYS_TO=<year>` then "
            "`make feast-sources && make feast-materialize`."
        )

    answered = pd.DatetimeIndex([pd.Timestamp(k) for k in keys])
    holidays = {
        answered[i].to_numpy() for i, key in enumerate(keys) if bool(stored["is_holiday"][i])
    }
    near = {
        answered[i].to_numpy() for i, key in enumerate(keys) if bool(stored["is_near_holiday"][i])
    }
    return HolidayCalendar(
        holidays=frozenset(holidays),
        # The store's `is_near_holiday` already excludes the holidays themselves
        # (`scripts/feast_sources.py` builds it from `calendar.flags`), so this
        # difference is a no-op that documents the invariant rather than a fix.
        near=frozenset(near - holidays),
        years=frozenset(int(y) for y in answered.year.unique()),
    )


def lookups_for(server: FeatureServer, frame: pd.DataFrame) -> Lookups:
    """Everything one request batch needs, in two calls — not two per row.

    The zone ids and the pickup dates are DEDUPLICATED first: a 600-row batch of
    airport runs asks the store about three zones, not twelve hundred. This is
    also what keeps the store off the critical path's tail — the measurement is
    `automation/runs/m8-transformer/transformer-load.json`.
    """
    from ..features.quote_time import PICKUP_TIMESTAMP

    zone_ids = sorted(
        {int(v) for v in frame["PULocationID"]} | {int(v) for v in frame["DOLocationID"]}
    )
    days = [pd.Timestamp(d) for d in pd.DatetimeIndex(frame[PICKUP_TIMESTAMP]).normalize().unique()]
    return Lookups(
        geometry_table=zone_table_from_store(server, zone_ids),
        calendar=calendar_from_store(server, days),
    )
