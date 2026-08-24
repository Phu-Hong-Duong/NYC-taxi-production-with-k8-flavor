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
4. **An unanswered date and a DEAD store return the same bytes**, so the refusal
   has to ask a second question before it picks a status. See
   `_calendar_is_alive` — that is F-062, and §"THE DISCRIMINATOR" below.

--------------------------------------------------------------------------
THE DISCRIMINATOR (F-062, PO answer (b) of 2026-08-24)
--------------------------------------------------------------------------
Until this change every failure of the calendar lookup was a **422**. That is
correct for the case F-019 named — *this deployment cannot answer that date* —
and wrong for the case M9-S2's drill measured: with the store **emptied**, every
request comes back 422 too, because a store that holds nothing answers `null` for
every date exactly as it does for a date past the horizon. The consequence is an
accounting one and it is the whole finding: `docs/slo_serving.md` SLO-R1 puts 4xx
OUTSIDE SLO-A1's availability budget on the argument that *a 4xx is a guard
working*, so a **totally dead dependency spent zero error budget** and rendered,
in every panel that splits 4xx from 5xx, as riders sending bad requests.

The two cases cannot be told apart from the ANSWER, so they are told apart by a
second QUESTION: on the failure path only, ask the store for a date the committed
holiday table provably covers (`_liveness_sentinel`). The store's calendar view is
GENERATED from that same table (`scripts/feast_sources.build_calendar_day` walks
`date_range(f"{years[0]}-01-01", …)`), so a healthy store answers it by
construction, and the sentinel is DERIVED from the table rather than typed.

- sentinel answers  -> the calendar is alive, the requested date is genuinely
  uncovered -> **422** (F-019's case, unchanged).
- sentinel is null too -> the store has no calendar at all -> **503**
  `FeatureStoreUnavailable`, ours, and it spends the availability budget.

Three properties worth keeping when this is next touched:

* **It costs the happy path nothing.** The probe runs only after a lookup has
  already failed, so the ~18 ms p50 the moved boundary was measured at
  (`automation/runs/m8-transformer/transformer-load.json`) is untouched. And it
  is usually not even reached: if ANY requested date was answered the store is
  demonstrably alive and no second call is made.
* **The alternatives were considered and are weaker, not merely different.**
  Feast's per-result `statuses` say `NOT_FOUND` for both cases, so the response
  cannot discriminate. The ZONE half cannot either: zones 264/265 legitimately
  have no row, so "every zone came back null" is a legal answer for a request
  that only names TLC's two non-places. Probing a different VIEW would answer
  "is the store alive" but not "is the CALENDAR view alive", which is the thing
  that just failed.
* **When the discriminator itself cannot be built, that is OURS.** If the
  committed table cannot be read this deployment cannot establish whether its own
  dependency is up — so it raises `FeatureStoreUnavailable` rather than falling
  back to 422. A permissive default here would put the failure back on the caller,
  which is the exact accounting F-062 is about (F-048's rule: an unresolvable
  value fails loudly, it does not resolve to something convenient).
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from ..features import zones as zones_mod
from ..features.calendar import HOLIDAY_TABLE, HolidayCalendar, load_calendar
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


@lru_cache(maxsize=1)
def _liveness_sentinel() -> str:
    """A `date_key` a HEALTHY store must be able to answer — derived, never typed.

    The store's `calendar_day_flags` view is built by
    `scripts/feast_sources.build_calendar_day` as
    `date_range(f"{years[0]}-01-01", f"{years[-1]}-12-31")` over the committed
    holiday table's own years. This returns the FIRST of those days, which is the
    twin of that expression's left edge — deliberately the earliest and not the
    latest, because the far end is where a legitimate horizon extension can leave
    a store one materialization behind, and a sentinel that goes null for that
    reason would report a coverage gap as an outage.

    Cached: the committed table does not change inside a process, and this sits on
    a failure path that a saturated store would otherwise hit once per request.
    """
    years = sorted(load_calendar().years)
    return f"{years[0]}-01-01"


def _calendar_is_alive(server: FeatureServer) -> bool:
    """Does the store answer for a date the committed table provably covers?

    The second question of the F-062 discriminator — see the module docstring.
    A transport failure here is not caught: `server.get` already raises
    `FeatureStoreUnavailable`, which is the same verdict this function would
    reach and carries a better message.
    """
    try:
        key = _liveness_sentinel()
    except Exception as exc:  # noqa: BLE001 — a missing committed table is one class
        raise FeatureStoreUnavailable(
            f"the calendar liveness sentinel could not be derived from {HOLIDAY_TABLE}: "
            f"{exc!r}. Reported as OUR failure (503) and not as the caller's (422): this "
            "deployment cannot establish whether its own dependency is up, and "
            "defaulting to 'the caller asked for a bad date' would bill an outage "
            "to a rider — which is exactly the accounting F-062 exists to fix."
        ) from exc
    stored = server.get([f"calendar_day_flags:{f}" for f in DAY_FEATURES], {DATE_KEY: [key]})
    return all(stored[name][0] is not None for name in DAY_FEATURES)


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

    **But WHOSE failure it is depends on a second question** — an uncovered date
    and a store holding nothing are the same bytes here. F-062, landed 2026-08-24
    on the PO's answer (b): a refusal is a 422 only once the calendar view has
    been shown to be answering, and a 503 otherwise. The module docstring's
    "THE DISCRIMINATOR" carries the argument.
    """
    keys = sorted({d.strftime(DATE_FORMAT) for d in days})
    stored = server.get([f"calendar_day_flags:{f}" for f in DAY_FEATURES], {DATE_KEY: keys})

    unanswered = [
        key
        for index, key in enumerate(keys)
        if any(stored[name][index] is None for name in DAY_FEATURES)
    ]
    if unanswered:
        # F-062's discriminator. An unanswered date and a DEAD store return the
        # same bytes, so before choosing a status ask whether the calendar view is
        # answering at all. Any date that DID answer settles it for free; only a
        # wholly unanswered batch pays the sentinel probe.
        answered_here = [k for k in keys if k not in unanswered]
        witness = (
            f"it answered {answered_here[0]!r} in this same batch"
            if answered_here
            else f"it served the sentinel {_liveness_sentinel()!r}"
        )
        if not answered_here and not _calendar_is_alive(server):
            raise FeatureStoreUnavailable(
                f"the online feature store answered no calendar row for any of {keys}, "
                f"and none for the sentinel {_liveness_sentinel()!r} that "
                f"{HOLIDAY_TABLE} provably covers — so the store's calendar is not "
                "serving. Reported as 503 and NOT as the 422 an uncovered date earns: "
                "a dead dependency is ours, it belongs in SLO-A1's availability "
                "budget, and billing it to the caller made a total outage render as "
                "riders sending bad requests (F-062). Repair: "
                "`make feast-sources && make feast-materialize`."
            )
        raise StoreCoverageError(
            f"the online feature store has no calendar row for {unanswered}. REFUSED "
            "rather than quoted: the champion eats holiday flags, and a silent "
            "'not a holiday' for an uncovered date looks exactly like a correct "
            f"answer (F-019, on the store's wire instead of the CSV's). The store IS "
            f"answering — {witness} — so this is "
            "a coverage gap and not an outage (F-062's discriminator). Fix it where "
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
