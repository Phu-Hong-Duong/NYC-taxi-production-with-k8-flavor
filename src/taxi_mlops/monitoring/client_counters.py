"""The counters that live in a CLIENT, and the gateway that lets one speak.

M7-S3, F-035's first half. The M6-S2 finding was precise and it was not about
laziness: *the fact lives in a client, and no client here is scraped.* F-019
chose to REFUSE an out-of-horizon quote rather than degrade it, and the refusal
is raised before a request is built — so the guard F-019 bought is invisible to
the monitoring stack. Measured at M6-S2: a past-horizon `make quote` (exit 2)
left the server's infer counter at 22 -> 22.

The pushgateway M7-S3 installs for drift is the thing that changes that, and
this module is the client's side of it.

WHAT A COUNTER IN A CLIENT CAN AND CANNOT MEAN, SAID BEFORE IT IS USED
----------------------------------------------------------------------
A rate over a counter needs a population. There is no fleet of quote clients
here — there is a make target a human types — so `rate(...)` over this counter
would be a rate over somebody's typing, which is noise dressed as telemetry.

That is why A-3's client rule is `increase(...[1h]) > 0` and not a rate or a
share. **One refusal is the whole event**: an `UncoveredDateError` means the
holiday table's horizon has expired, which is a fact about the REPOSITORY and
not about traffic, and it is fixed by one command. A threshold above zero would
be a decision to serve some refusals quietly.

WHY THE PUSH CANNOT BE ALLOWED TO BREAK A QUOTE
------------------------------------------------
`record_refusal` NEVER raises. A rider's quote must not fail because a metrics
gateway is unreachable, and — the sharper version — a refusal that is already
being reported correctly through an exit code must not turn into a crash on the
way to being counted. A failed push prints one line and returns False. This is
the one place in this repository where a swallowed exception is the right
answer, so it is argued here rather than left to be discovered.

THE COUNTER IS READ-MODIFY-WRITE, AND THAT IS A REAL LIMITATION
-----------------------------------------------------------------
The gateway holds a last value, not a counter it can increment. So this reads
the current value back and pushes value+1, which is not atomic: two clients
refusing in the same second can lose a count. It is recorded rather than
engineered around because A-3's rule reads `> 0` — losing one of two
simultaneous refusals cannot change its verdict — and because a
compare-and-swap protocol against a bulletin board would be more machinery than
the signal is worth. If a real client fleet ever exists, this becomes a proper
exporter and the rule becomes a rate; that is M8/M9's, and stated so the
shortcut is a decision.
"""

from __future__ import annotations

import urllib.error
import urllib.request

from .pushgateway import Metric, PushError, push_metrics

#: The pushgateway job for client-side counters. Selected by A-3's rule.
CLIENT_JOB = "taxi-quote-client"

REFUSAL_METRIC = "taxi_quote_refusals_total"
CLIENT_FRESHNESS_METRIC = "taxi_quote_client_last_run_timestamp_seconds"


def _current_value(url: str, instance: str, reason: str, timeout: float = 10.0) -> float:
    """Read the counter back off the gateway. Absent or unreadable reads as 0."""
    target = url.rstrip("/") + "/metrics"
    try:
        with urllib.request.urlopen(target, timeout=timeout) as response:  # noqa: S310
            body = response.read().decode("utf-8")
    except (urllib.error.URLError, OSError):
        return 0.0
    for line in body.splitlines():
        if not line.startswith(REFUSAL_METRIC + "{"):
            continue
        if f'reason="{reason}"' in line and f'instance="{instance}"' in line:
            try:
                return float(line.rsplit(" ", 1)[1])
            except (IndexError, ValueError):
                return 0.0
    return 0.0


def record_refusal(
    *,
    url: str,
    reason: str = "uncovered_date",
    instance: str = "make-quote",
    timeout: float = 10.0,
) -> bool:
    """Increment the client refusal counter. NEVER raises — see the module docstring."""
    import time

    try:
        value = _current_value(url, instance, reason, timeout=timeout) + 1.0
        push_metrics(
            [
                Metric(
                    name=REFUSAL_METRIC,
                    value=value,
                    help=(
                        "Quotes this client refused before building a request. The "
                        "refusal is F-019's typed boundary and moves no server counter."
                    ),
                    labels={"reason": reason, "instance": instance},
                ),
                Metric(
                    name=CLIENT_FRESHNESS_METRIC,
                    value=float(time.time()),
                    help="Unix time of this client's last push.",
                    labels={"instance": instance},
                ),
            ],
            url=url,
            job=CLIENT_JOB,
            grouping={"instance": instance, "reason": reason},
            timeout=timeout,
        )
    except (PushError, OSError) as error:
        print(f"[quote] (metrics) refusal not counted: {error}")
        return False
    return True
