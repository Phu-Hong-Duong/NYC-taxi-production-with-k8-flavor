"""Push drift metrics to the Prometheus Pushgateway, in its own text format.

M7-S3. A batch job cannot be scraped: it exists for four minutes a month and is
gone before any scrape interval elapses. Pushgateway is the standard answer —
the job PUSHES, the gateway HOLDS, Prometheus scrapes the gateway.

WHY THIS IS HAND-ROLLED AND NOT `prometheus_client`
----------------------------------------------------
The push protocol is one HTTP PUT of the text exposition format to a path that
encodes the grouping key. That is ~40 lines including the escaping rules, and
`prometheus_client` would be a new runtime dependency in a project whose task
image is already 737 MiB and whose every dependency addition costs a gotcha #36
check. The escaping rules are pinned by unit tests rather than by trust.

THE STALENESS PROBLEM, AND WHY EVERY PUSH CARRIES A TIMESTAMP METRIC
---------------------------------------------------------------------
This is the one thing about pushgateway that surprises people and it is named in
the M7 kickoff's risk table: **a pushed metric persists until it is deleted or
overwritten**. The gateway is not a store of events, it is a bulletin board. So
"the drift metric is present and below the bar" is NOT "the drift job ran and
found nothing" — it is equally consistent with the drift job having died three
months ago leaving January's reassuring number pinned to the wall. That failure
is gotcha #78's empty-panel disease inverted: instead of a blank rectangle that
looks like calm, a stale number that looks like health.

So `push_metrics` REQUIRES a freshness stamp and refuses a payload without one.
Not "encourages" — refuses, in a type, for M5-S2's reason: a guard that can be
forgotten is a guard that will be. The alert rule that reads it lives beside the
drift rule in `infra/monitoring/alerting_rules.yml`.

PUT AND NOT POST, AND THE GROUPING KEY
---------------------------------------
`PUT` REPLACES every metric under the grouping key; `POST` merges. Replacement
is what a re-run of a month's drift job should do: if a monitored column is
removed from `MONITORED_COLUMNS`, a POST would leave the deleted column's last
value on the board forever, and a board rendering a column the code no longer
computes is a lie with a timestamp on it. The grouping key is
`job=<job>/month=<month>`, so each scoring month is its own replaceable group and
re-running one month cannot silently delete another's numbers.
"""

from __future__ import annotations

import urllib.parse
import urllib.request
from dataclasses import dataclass, field

#: The default in-cluster address. NO hostPort exists for the gateway (M7 law 1:
#: kind publishes host ports at cluster-CREATE only and this cluster is not
#: rebuilding), so a host-side caller reaches it through a port-forward and an
#: in-cluster caller uses this name. Overridden by `--pushgateway`.
#:
#: The DOUBLED `prometheus-` is not a typo: the chart's fullname template
#: prefixes the helm RELEASE name (`prometheus`) to the subchart's own name
#: (`prometheus-pushgateway`). Read off the live Service, not guessed — the
#: guess cost one down scrape target, which is written up beside the scrape job
#: in `infra/helm/monitoring/prometheus-values.yaml`.
SERVICE_NAME = "prometheus-prometheus-pushgateway"
DEFAULT_IN_CLUSTER_URL = f"http://{SERVICE_NAME}.monitoring.svc.cluster.local:9091"

#: The metric a freshness guard reads. Named here rather than typed at the call
#: site so the rule file, the pusher and the tests all point at one string.
FRESHNESS_METRIC = "taxi_drift_last_run_timestamp_seconds"


class PushError(RuntimeError):
    """The gateway refused the push, and the message carries its answer."""


@dataclass
class Metric:
    """One gauge sample: a name, a value, labels, and the sentence that explains it."""

    name: str
    value: float
    help: str
    labels: dict[str, str] = field(default_factory=dict)


def _escape_label_value(value: str) -> str:
    """Backslash, double-quote and newline, per the exposition format spec."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _escape_help(text: str) -> str:
    """HELP text escapes backslash and newline only — a quote is legal there."""
    return text.replace("\\", "\\\\").replace("\n", " ")


def render(metrics: list[Metric]) -> str:
    """The text exposition format: one HELP/TYPE pair per metric NAME, then samples.

    A repeated `# HELP` for the same name makes the gateway reject the whole
    payload with `text format parsing error`, which is why the grouping is by
    name and not simply one block per sample.
    """
    lines: list[str] = []
    seen: set[str] = set()
    by_name: dict[str, list[Metric]] = {}
    order: list[str] = []
    for metric in metrics:
        if metric.name not in by_name:
            by_name[metric.name] = []
            order.append(metric.name)
        by_name[metric.name].append(metric)

    for name in order:
        group = by_name[name]
        if name not in seen:
            lines.append(f"# HELP {name} {_escape_help(group[0].help)}")
            lines.append(f"# TYPE {name} gauge")
            seen.add(name)
        for metric in group:
            if metric.labels:
                rendered = ",".join(
                    f'{key}="{_escape_label_value(str(value))}"'
                    for key, value in sorted(metric.labels.items())
                )
                lines.append(f"{name}{{{rendered}}} {metric.value!r}")
            else:
                lines.append(f"{name} {metric.value!r}")
    return "\n".join(lines) + "\n"


def _grouping_path(job: str, grouping: dict[str, str]) -> str:
    parts = ["metrics", "job", urllib.parse.quote(job, safe="")]
    for key in sorted(grouping):
        parts.append(urllib.parse.quote(key, safe=""))
        parts.append(urllib.parse.quote(grouping[key], safe=""))
    return "/" + "/".join(parts)


def push_metrics(
    metrics: list[Metric],
    *,
    url: str,
    job: str,
    grouping: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> str:
    """PUT the metrics under `job`/`grouping`. Returns the URL that was written.

    REFUSES a payload with no freshness stamp — see the module docstring. The
    check is on the metric NAME, so a caller cannot satisfy it by pushing a
    timestamp under some other name that no rule reads.
    """
    if not metrics:
        raise PushError("refusing to push an empty metric set — that is a delete in disguise.")
    if not any(m.name == FRESHNESS_METRIC for m in metrics):
        raise PushError(
            f"refusing to push without {FRESHNESS_METRIC}. A pushed metric persists "
            "after its producer dies, so a drift value with no freshness stamp is "
            "indistinguishable from a drift job that stopped running months ago."
        )

    target = url.rstrip("/") + _grouping_path(job, grouping or {})
    body = render(metrics).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310 - http(s) only, address is ours
        target, data=body, method="PUT", headers={"Content-Type": "text/plain; version=0.0.4"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            if response.status not in (200, 202):
                raise PushError(f"{target} answered HTTP {response.status}")
    except PushError:
        raise
    except Exception as error:  # urllib raises a zoo; the address is what matters
        raise PushError(f"push to {target} failed: {error}") from error
    return target


def delete_group(*, url: str, job: str, grouping: dict[str, str] | None = None,
                 timeout: float = 30.0) -> str:
    """DELETE one grouping key. Used only by the drill's cleanup and by tests.

    The gateway has no expiry, so something has to be able to remove a group —
    but nothing in the drift path calls this: a drift number is removed by being
    overwritten with a fresher one, never by being erased.
    """
    target = url.rstrip("/") + _grouping_path(job, grouping or {})
    request = urllib.request.Request(target, method="DELETE")  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            if response.status not in (200, 202):
                raise PushError(f"{target} answered HTTP {response.status}")
    except PushError:
        raise
    except Exception as error:
        raise PushError(f"delete of {target} failed: {error}") from error
    return target
