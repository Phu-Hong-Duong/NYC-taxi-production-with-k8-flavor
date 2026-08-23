"""What "healthy" means for the Feast ONLINE store, as quantities and never as a verdict.

M9-S2, closing the residual M8-S4's three legs each restated and none closed:
*there is no alert on an empty or stale online store.*

**NO THRESHOLD LIVES HERE.** The bars — such as they are — live in the SELECTOR
and the comparison of two rules in `infra/monitoring/alerting_rules.yml`, and
`docs/slo_serving.md` §9 argues them. This module measures. That is M7-S3's
shape for drift and M5-S4's for load, and it is pinned by the same AST test: the
pushed numbers must stay re-interpretable after the fact, which they cannot be
if the producer already applied somebody's bar to them.

--------------------------------------------------------------------------
THE TWO QUANTITIES, AND WHY ONE OF THEM NEEDS NO NUMBER
--------------------------------------------------------------------------
Feast writes one Redis key per distinct ENTITY KEY per view. So the store's size
has a source of truth that is not itself: `count(distinct <entity keys>)` over
`data/feast/*.parquet`. `expected_keys()` computes it, and A-12b compares the two
series rather than either against a constant — so the rule self-updates when
`make feast-sources` legitimately changes the sources, and the window between a
source change and the next `make feast-materialize` is exactly the *stale* state
the rule exists to catch (docs/slo_serving.md §9.3).

--------------------------------------------------------------------------
WHY THERE IS A CANARY AT ALL, WHEN THERE IS ALREADY A COUNT
--------------------------------------------------------------------------
Because the count cannot see the failure that would reach a rider. Measured in
`automation/runs/m9-store-watch/headroom.json`: the transformer — the store's
only rider-facing reader — depends on 4,646 of 57,688 keys (8.054%), and zone
132's centroid is ONE key. Losing exactly the key that breaks every JFK quote
moves `DBSIZE` by 0.0017%. So the count is the coarse signal and the canary is
the load-bearing one, and the canary asks about ANSWERS rather than about size —
gotcha #59's rule (assert on the artifact the thing exists to produce) applied to
a feature store.

--------------------------------------------------------------------------
THE THREE THINGS A CANARY MUST CLAIM HERE, AND THE ONE THAT IS NEGATIVE
--------------------------------------------------------------------------
`nonplace_declines` is the one that is easy to leave out and expensive to.
Zones 264/265 are TLC's "Unknown" and have no centroid BY DESIGN (DR-04
condition 1) — so `null` is their correct answer, and a store that answered for
them would be inventing a location. A canary that only asserted presence would
pass against a server answering every question with the same row. This is the
two-sided assertion M8-S3, M8-S4 leg 1 and leg 2 each had to arrive at
independently, stated once here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Metric names, spelled once so the reader, the rules file and the tests point
#: at one string each.
KEYS_METRIC = "taxi_online_store_keys"
KEYS_EXPECTED_METRIC = "taxi_online_store_keys_expected"
CANARY_METRIC = "taxi_online_store_canary"
FRESHNESS_METRIC = "taxi_online_store_last_run_timestamp_seconds"

#: The pushgateway job label. `honor_labels: true` on the gateway's scrape job is
#: what lets it survive to the rules (M7-S3, gotcha #92) — without it every
#: pushed sample arrives as `job="pushgateway"` and every rule below matches
#: nothing while staying `health=ok` and inactive.
PUSH_JOB = "taxi-store-watch"

#: One entry per published source: the parquet Feast reads and the columns it is
#: keyed on. The join keys are the same strings the feature server answers to —
#: read off `infra/feast/feature_repo/definitions.py`, not invented, because a
#: plausible-looking wrong key is HTTP 500 with `Provided join_key_values: []`
#: rather than a complaint (M8-S4 leg 2).
VIEWS: dict[str, dict[str, Any]] = {
    "zone_static": {"file": "zone_static.parquet", "entity": ["zone_id"]},
    "calendar_day_flags": {"file": "calendar_day.parquet", "entity": ["date_key"]},
    "od_window_stats": {
        "file": "od_window_stats.parquet",
        "entity": ["PULocationID", "DOLocationID"],
    },
    "pu_hour_window_stats": {
        "file": "pu_hour_window_stats.parquet",
        "entity": ["PULocationID", "hour"],
    },
}

#: The views the TRANSFORMER reads. F-059 keeps the borough dictionary and the
#: airport constant on the committed side of the wall, so these two are the whole
#: rider-facing dependency.
TRANSFORMER_VIEWS = ("zone_static", "calendar_day_flags")

#: The canary's subjects. Constants rather than a sample, for M5-S3's reason: a
#: sampled canary gives a different answer every run and a drill cannot plant a
#: cause in it. Zone 132 is the JFK zone every record in this repo quotes;
#: 2019-07-04 is the federal holiday the parity table's own row is built on.
CANARY_ZONE = 132
CANARY_NONPLACE = 264
CANARY_DATE = "2019-07-04"

#: The checks, in the order a reader should think about them. `store_reachable`
#: is first because it is the one that says *I could not look* rather than *the
#: answer was wrong* — see `CHECKS` below for why it is a check and not a refusal.
CHECK_REACHABLE = "store_reachable"
CHECK_ZONE = "zone_answers"
CHECK_NONPLACE = "nonplace_declines"
CHECK_CALENDAR = "calendar_answers"


@dataclass(frozen=True)
class Check:
    """One canary claim: its id, what it asserts, and why that claim is the one."""

    name: str
    claim: str
    why: str


CHECKS: tuple[Check, ...] = (
    Check(
        CHECK_REACHABLE,
        "the store answered its operator: DBSIZE was readable",
        # WHY THIS IS A CHECK AND NOT A REFUSAL TO PUSH. `push_serving_version.py`
        # refuses to push when a side is unreadable, and it is right to: an
        # unknown served version is not a mismatch, so a placeholder would page
        # for an unreadable endpoint. The rule inverts here. If the Redis pod is
        # gone, "I could not read DBSIZE" is not a gap in the measurement, it IS
        # the measurement — and a reader that refused to push would leave the
        # last healthy reading on the board to go quietly stale, which is the
        # exact failure this whole signal exists to prevent. So it is reported,
        # not withheld. The cost is named in docs/slo_serving.md §9: a broken
        # kubectl on the operator's laptop reads the same as a broken store.
        "a watchdog that goes silent when its subject dies is not a watchdog",
    ),
    Check(
        CHECK_ZONE,
        f"zone {CANARY_ZONE} returns a non-null centroid",
        "a place must have a location, and this is the zone whose quote every "
        "record in this repo cites (39.0019 minutes out of JFK)",
    ),
    Check(
        CHECK_NONPLACE,
        f"zone {CANARY_NONPLACE} returns null, and not an error",
        "the negative half. TLC's non-places have no centroid by design "
        "(DR-04 condition 1), so a store that answered for them would be "
        "inventing a location — and a presence-only check passes against a "
        "server that answers every question with the same row",
    ),
    Check(
        CHECK_CALENDAR,
        f"{CANARY_DATE} returns its holiday flags",
        "the half that actually refuses a rider: calendar_from_store RAISES on "
        "an unanswered date (F-019 carried onto the store's wire), which the "
        "transformer converts into a 422",
    ),
)


def expected_keys(root: Path) -> dict[str, Any]:
    """One Redis key per distinct entity key per view, computed from the sources.

    RAISES rather than defaulting when a source is missing (F-048's rule): a
    derivation with no source is a typed constant in disguise, and an expected
    count that silently falls back would make A-12b compare the store against
    nothing.
    """
    import duckdb

    per_view: dict[str, int] = {}
    for name, spec in VIEWS.items():
        path = root / "data" / "feast" / spec["file"]
        if not path.exists():
            raise FileNotFoundError(
                f"{path} is missing — the expected key count is DERIVED from the published "
                "sources and cannot be defaulted. Run: make feast-sources"
            )
        keys = ", ".join(spec["entity"])
        expr = keys if len(spec["entity"]) == 1 else f"({keys})"
        per_view[name] = int(
            duckdb.sql(f"select count(distinct {expr}) from '{path.as_posix()}'").fetchone()[0]
        )
    total = sum(per_view.values())
    transformer = sum(per_view[v] for v in TRANSFORMER_VIEWS)
    return {
        "per_view": per_view,
        "total": total,
        "transformer_dependency_keys": transformer,
        "transformer_dependency_share": transformer / total if total else None,
    }


def evaluate_canary(
    *,
    dbsize: int | None,
    zone_centroid: tuple[Any, Any] | None,
    nonplace_centroid: tuple[Any, Any] | None,
    calendar_flags: tuple[Any, Any] | None,
    lookup_failed: bool,
) -> dict[str, int]:
    """Turn four raw observations into four 0/1 claims. No bar, no verdict.

    `lookup_failed` is True when the feature server could not be reached or
    answered something unusable. That is deliberately NOT modelled as "unknown":
    it is exactly what the transformer sees when it 503s, so every answer-shaped
    check is 0 — the store did not answer, which is what the claim asserts.
    """
    if lookup_failed:
        answers = {CHECK_ZONE: 0, CHECK_NONPLACE: 0, CHECK_CALENDAR: 0}
    else:
        lat, lon = zone_centroid or (None, None)
        answers = {
            CHECK_ZONE: int(lat is not None and lon is not None),
            # BOTH must be null. A store holding a latitude and no longitude for
            # a non-place is not "declining" — it is half-answering, which is a
            # different and more alarming thing than either state alone.
            CHECK_NONPLACE: int(nonplace_centroid == (None, None)),
            CHECK_CALENDAR: int(
                calendar_flags is not None and all(f is not None for f in calendar_flags)
            ),
        }
    return {CHECK_REACHABLE: int(dbsize is not None), **answers}
