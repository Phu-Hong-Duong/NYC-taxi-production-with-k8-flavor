"""Where a derived feature's REFERENCE DATA may come from — and where it may not.

M8-S4 leg 3. `quote_time.build_features` derives 24 features from a request. Most
of them need nothing but the request itself (the clock, the two zone ids, the
party size). Three groups need a REFERENCE TABLE:

1. the zone **centroids** — nine geometry features off one 263-row table;
2. the federal **holiday calendar** — three flags off a 146-row table;
3. the borough **dictionary** and the **airport** constant.

Until this module, all three came from the committed CSVs, always. This module
adds ONE alternative source for the first two — an online feature store, read at
request time — and it exists mainly to say, in code, that the third may NOT use
it. That refusal is **F-059** (`docs/feast_server_m8.md` §5), and the three cases
are indistinguishable in a schema, which is why the rule needs a home rather than
a comment:

- **A centroid is a per-entity MEASUREMENT.** Zone 132's latitude is a property
  of zone 132. Fetch it for the two zones in a request and you have exactly what
  the whole table would have given you for those two rows. It may cross.
- **A borough CODE is an ENCODING.** `zones.load_zone_table()` assigns codes by
  first-appearance order while iterating the whole lookup CSV, and `borough_pair`
  multiplies by `len(table.boroughs)`. A zone's code is therefore a property of
  the TABLE's iteration order, not of the zone. A transformer that fetched
  `borough` for two zones and numbered what came back would produce a silent,
  total category re-map — every value individually correct, every code wrong.
  It may not cross; the dictionary travels with the MODEL.
- **`is_airport` is a CONSTANT and a TOTAL function.** It is three integers in
  `zones.AIRPORT_ZONES`, defined for every id including TLC's non-places 264/265,
  which the store (correctly) has no row for. Sourcing a total function from a
  partial store turns "not an airport" into "no answer" for precisely the ~1% of
  rows that already carry no geometry — F-030's class, re-opened. It may not
  cross; the store may CORROBORATE it, and leg 2 measured that projection exact
  over all 21 real zones among the hazards.

So the rule this module encodes, and it is the one worth carrying: **a feature
store is a good home for a per-entity measurement and a bad home for anything a
program computes.**

`Lookups` is a PARAMETER and never a module global, for the same reason
`build_features`'s `fitted` is: which reference data a row was built against is a
property of the CALL, not of the process. A global would let a transformer's
store-sourced table leak into a training run in the same interpreter.
"""

from __future__ import annotations

from dataclasses import dataclass

from .calendar import HolidayCalendar
from .zones import ZoneTable


@dataclass(frozen=True)
class Lookups:
    """Reference data supplied by the CALLER instead of read off the committed CSVs.

    Both fields default to `None`, which means "use the committed table" — so an
    absent `Lookups` and a `Lookups()` are the same thing, and every existing
    caller keeps the behaviour it has had since M3-S3.

    `geometry_table` is named for what it is ALLOWED to be used for. It is a full
    `ZoneTable`, so it must carry a borough dictionary to be well-formed; the one
    the store path builds is copied from the COMMITTED table (see
    `serving.feature_store.lookups_from_store`), so even a caller that misuses it
    gets training's answer. Defence in depth: the dispatch in `quote_time` reads
    boroughs off `zones.load_zone_table()` directly and never off this object, and
    a test asserts that.
    """

    geometry_table: ZoneTable | None = None
    calendar: HolidayCalendar | None = None

    @property
    def sources(self) -> dict[str, str]:
        """What each reference group was actually read from, for a record to print.

        A transformer that silently fell back to its committed tables would serve
        perfectly correct quotes and prove nothing about the store — the failure
        mode ADR-012 names for the materializer, one layer along. So the answer is
        reported rather than assumed, and the parity record carries it.
        """
        return {
            "centroids": "feature-store" if self.geometry_table is not None else "committed-table",
            "calendar": "feature-store" if self.calendar is not None else "committed-table",
            # Not a knob. See the module docstring / F-059.
            "borough_dictionary": "committed-table",
            "airport_constant": "committed-code",
        }


#: The empty one, so callers can pass a `Lookups` unconditionally without
#: expressing "no reference data" as `None` in three places.
COMMITTED = Lookups()
