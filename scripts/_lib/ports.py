"""THE registry of ephemeral local port-forward ports — one home, with reasons.

None of these is a declared route. CLAUDE.md's port family lists the ports this
program DECLARES (a kind `hostPort` mapped onto a Service's fixed `nodePort`,
readable at cluster-create time and never after); a forward that exists for four
minutes inside one drill is the opposite kind of thing, and putting it in the
family would claim a route the cluster does not publish. So they live here.

**Why a registry rather than a constant per script.** Until CU-S4 these numbers
were coordinated by COMMENTS, and each comment enumerated the neighbours its
author happened to check rather than the set. The measurement that ended the
argument: `gameday_m6.py` reserved **9096** for Alertmanager and
`drift_fire_drill.py` reserved **9096** for the pushgateway — two services, one
number, in two drills that talk to the same cluster. Neither comment was
careless; `drift_fire_drill`'s cites `alert_fire_drill`'s 9095 as the precedent
it is avoiding, and `store_watch_drill`'s enumerates four neighbours and misses
gameday. Coordination by comment can only ever be as complete as one author's
reading, and it degrades silently: a stolen port makes a drill fail for its own
reasons (#55, which has cost this program a session).

**Blast radius of the 9096 double-booking, stated honestly rather than
dramatised:** it is LATENT, not live. No Makefile target and no script runs
`gameday` and `drift-drill` concurrently, and gameday's delegation to
`alert_fire_drill.py` is 9096-vs-9095, which does not collide. It was one
overlapping invocation away from being real, and the collision was invisible to
every reader of either file.

`assert_unique()` is what makes the registry a guard rather than a list, and a
test runs it. Adding an entry that collides fails the suite, which is the
property the comments could not have.
"""

from __future__ import annotations

from typing import NamedTuple


class Reservation(NamedTuple):
    """One ephemeral local port: who forwards it, to what, and why this number."""

    port: int
    owner: str
    service: str
    why: str


#: Every ephemeral forward this repository opens. Keyed by the name the owning
#: script uses, so a reader can go from either direction.
RESERVATIONS: dict[str, Reservation] = {
    # --- Redis, the Feast online store (ADR-012) --------------------------------
    "FEAST_REDIS": Reservation(
        6380, "feast_materialize.sh / feast_online_parity.py", "svc/redis:6379",
        "Deliberately off 6379 so a materialization can never write into a "
        "developer's own local Redis if the forward were to die.",
    ),
    "FEAST_REDIS_REDTEAM": Reservation(
        6381, "feast_online_parity_redteam.sh", "svc/redis:6379",
        "The drill's forward and the parity run's are alive at the same time.",
    ),
    # --- The quarantined Feast feature server -----------------------------------
    "FEAST_SERVER_PARITY": Reservation(
        6567, "feast_server_parity.py", "svc/feast-server:6566",
        "Off 6566 for the store's 6380 reason: never the port the service "
        "itself is published on in-cluster.",
    ),
    "FEAST_SERVER_WATCH": Reservation(
        6568, "store_watch.py", "svc/feast-server:6566",
        "The watchdog reads the feature server while a parity run may hold 6567.",
    ),
    # --- Flyte control plane ----------------------------------------------------
    "FLYTE_READER": Reservation(
        8092, "flyte_actions.sh / pipeline_kill_drill.sh", "flyte-binary-http:8090",
        "8090 and 8091 belong to run_pipeline.sh and to the drills; a reader "
        "must not steal the port of a run in flight.",
    ),
    # --- Alertmanager (one per drill that watches alerts reach it) --------------
    "ALERTMANAGER_ALERT_DRILL": Reservation(
        9095, "alert_fire_drill.py", "alertmanager:9093",
        "The first of the family; every later drill is numbered off it.",
    ),
    "ALERTMANAGER_GAMEDAY": Reservation(
        9096, "gameday_m6.py", "alertmanager:9093",
        "Gameday delegates its control scenario to alert_fire_drill, which "
        "holds 9095 at the same time.",
    ),
    "ALERTMANAGER_DRIFT_DRILL": Reservation(
        9097, "drift_fire_drill.py", "alertmanager:9093",
        "Held beside this drill's own pushgateway forward.",
    ),
    "ALERTMANAGER_PERSISTENCE_DRILL": Reservation(
        9099, "drift_persistence_drill.py", "alertmanager:9093",
        "Held beside this drill's own pushgateway forward.",
    ),
    "ALERTMANAGER_STORE_DRILL": Reservation(
        9101, "store_watch_drill.py", "alertmanager:9093",
        "The store drill runs store_watch.py, which holds 9100, inside itself.",
    ),
    # --- Pushgateway ------------------------------------------------------------
    # NOTE: 9096 was ALSO the drift fire drill's pushgateway port until CU-S4.
    # It moved to 9103 — the collision, not the reservation, is what changed.
    "PUSHGATEWAY_DRIFT_DRILL": Reservation(
        9103, "drift_fire_drill.py", "prometheus-pushgateway:9091",
        "Was 9096, which gameday_m6.py had already reserved for Alertmanager — "
        "the double-booking CU-S4 measured. Moved to the first free number "
        "above the family rather than renumbering a neighbour.",
    ),
    "PUSHGATEWAY_PERSISTENCE_DRILL": Reservation(
        9098, "drift_persistence_drill.py", "prometheus-pushgateway:9091",
        "Held beside this drill's own Alertmanager forward.",
    ),
    "PUSHGATEWAY_STORE_WATCH": Reservation(
        9100, "store_watch.py", "prometheus-pushgateway:9091",
        "The reader pushes its own series; the store drill runs it inside itself.",
    ),
    "PUSHGATEWAY_STORE_DRILL": Reservation(
        9102, "store_watch_drill.py", "prometheus-pushgateway:9091",
        "Read beside the reader's 9100, which is alive for part of this drill.",
    ),
}


def assert_unique() -> None:
    """Refuse two reservations of one port. THIS is what a list cannot do.

    Called by `tests/unit/test_script_libs.py`, so a colliding entry is a red
    suite rather than a drill that fails for its own reasons weeks later.
    """
    seen: dict[int, str] = {}
    for name, reservation in RESERVATIONS.items():
        clash = seen.get(reservation.port)
        if clash is not None:
            raise AssertionError(
                f"local port {reservation.port} is reserved twice: {clash} and {name}. "
                "Two forwards on one port is the failure CU-S4 measured (gameday's "
                "Alertmanager vs the drift drill's pushgateway, both 9096) — pick a "
                "free number here, where the whole set is visible."
            )
        seen[reservation.port] = name


def port(name: str) -> int:
    """The reserved local port for `name`, or a refusal naming what exists.

    A `KeyError` here means a caller invented a name; the message lists the
    registry rather than leaving the reader to open this file.
    """
    try:
        return RESERVATIONS[name].port
    except KeyError:
        known = ", ".join(sorted(RESERVATIONS))
        raise KeyError(
            f"no ephemeral port is reserved under {name!r}. Reserved names: {known}"
        ) from None


assert_unique()
