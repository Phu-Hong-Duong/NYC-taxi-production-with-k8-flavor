"""Readers for Prometheus, Alertmanager and the pushgateway. They READ; they never judge.

M5-S4's load-drill precedent, one board along: *a reader that does not judge*.
No threshold, no `for:` sustain and no bar appears in this module. Every serving
threshold lives in `docs/slo_serving.md` and reaches Prometheus through
`infra/monitoring/alerting_rules.yml`; a bar computed here would be the second
home F-013 keeps deleting, and — worse — it would be a bar in a place no gate
parses, so `verify-m6` §2's "every threshold in the rules file is argued in the
SLO doc" would stay green over it.

**Two HTTP readers, split by BEHAVIOUR rather than merged under one name**
(CU-S2's rule, and CU-S4 found the same hazard in `scripts/`): `http_get` lets a
connection failure raise, `http_probe` reports it as `(0, reason)`. Five copies
of "http_get" existed with three different meanings before this module, and the
difference between them is exactly whether an unreachable endpoint is a bug or
an expected state — which is not a detail a caller should get by accident.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def http_get(host: str, url: str, timeout: float = 20.0) -> tuple[int, str]:
    """GET `url` under a `Host` header; HTTP errors come back as (status, body).

    A CONNECTION failure raises. Use this wherever the endpoint is supposed to
    be up: a forward that is down is a bug at the call site, and swallowing it
    into a sentinel makes the drill report the wrong thing (`verify-m6` reads a
    404 and a dead route identically otherwise — gotcha #106's family).
    """
    request = urllib.request.Request(url, headers={"Host": host})  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")


def http_probe(host: str, url: str, timeout: float = 20.0) -> tuple[int, str]:
    """`http_get`, but an unreachable endpoint answers `(0, reason)` instead of raising.

    For POLLING loops only — "is the forward up yet?", "has the pod come back?" —
    where not-yet-reachable is an expected state on the way to the answer. Status
    `0` is deliberately not a real HTTP status, so a caller cannot confuse it
    with one.
    """
    try:
        return http_get(host, url, timeout=timeout)
    except Exception as error:  # noqa: BLE001 - "not up yet" is the answer here
        return 0, str(error)


def prom_rules(host: str, route: str) -> dict[str, dict[str, Any]]:
    """Every ALERTING rule Prometheus has loaded, by alert name.

    Recording rules are dropped: every caller asks about alerts, and a recording
    rule sharing a name would silently shadow one.
    """
    status, body = http_get(host, f"{route}/api/v1/rules")
    if status != 200:
        raise RuntimeError(f"Prometheus /api/v1/rules -> {status}")
    out: dict[str, dict[str, Any]] = {}
    for group in json.loads(body)["data"]["groups"]:
        for rule in group["rules"]:
            if rule.get("type") == "alerting":
                out[rule["name"]] = rule
    return out


def rule_state(rules: dict[str, dict[str, Any]], alert: str) -> str:
    """`firing` / `pending` / `inactive`, or `absent` when Prometheus has no such rule.

    `absent` is its own word on purpose: a rule that was never loaded and a rule
    that is quiet look identical to a caller that defaults the missing case to
    "inactive", and the first is a broken deploy (gotcha #92).
    """
    return str((rules.get(alert) or {}).get("state", "absent"))


def firing_labels(rules: dict[str, dict[str, Any]], alert: str, label: str) -> set[str]:
    """The values of `label` across the FIRING series of one alert — the per-series read.

    Never the name-level "is it firing?". gotcha #93: A-9 is predicted to fire
    for 2020-03 AND to stay quiet for 2020-01/02 — three statements about one
    rule — and a judge keyed on the name cannot express that; the first version
    of the drift drill reported a correctly-behaving system as a failure. It is
    also the STRONGER claim: a bar so low that an ordinary January trips it
    passes a name-level check and fails this one.

    `label` is a parameter because the callers read different ones — `month` for
    the drift rules, `check` for the online-store canary — and generalising the
    LABEL is what let three near-copies become one reader without any of them
    losing the per-series property.
    """
    rule = rules.get(alert) or {}
    return {
        instance.get("labels", {}).get(label, "")
        for instance in rule.get("alerts") or []
        if instance.get("state") == "firing"
    }


def prom_query(host: str, route: str, expr: str) -> list[dict[str, Any]]:
    """One instant query, returning `data.result`.

    Both failure modes are checked, and the second is the one the copies
    disagreed about: an HTTP 200 carrying `status: error` is a REFUSED query
    (a typo'd metric name, a parse error), and a reader that only checked the
    status code would read it as a legitimately empty result — i.e. as a quiet
    system. That is gotcha #78 arriving through a client.
    """
    url = f"{route}/api/v1/query?query={urllib.parse.quote(expr)}"
    status, body = http_get(host, url)
    if status != 200:
        raise RuntimeError(f"Prometheus query -> {status}: {body[:200]}")
    payload = json.loads(body)
    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus refused {expr!r}: {payload}")
    return payload["data"]["result"]


def prom_scalar(host: str, route: str, expr: str, default: float = 0.0) -> float:
    """The first sample's value, or `default` when the query returns no series.

    The default is the caller's to choose and is NOT a judgement: an empty
    result means nothing matched, which for a rate over a quiet window is
    legitimately zero and for a mistyped selector is not. Callers that cannot
    tell those apart should use `prom_query` and look.
    """
    result = prom_query(host, route, expr)
    if not result:
        return default
    return float(result[0]["value"][1])


def alertmanager_alerts(port: int) -> list[dict[str, Any]]:
    """Every alert ALERTMANAGER is holding, read over an ephemeral local forward.

    The second witness that matters: Prometheus's own UI shows a rule firing,
    but "it reached Alertmanager" is the claim an on-call cares about, and the
    two can disagree (a broken `alertmanagers:` block fires nothing anywhere a
    human would see). An unreachable Alertmanager answers `[]` rather than
    raising, because every caller is inside a polling loop.
    """
    status, body = http_probe("localhost", f"http://localhost:{port}/api/v2/alerts")
    if status != 200:
        return []
    return json.loads(body)


def alertmanager_holds(port: int, alert: str) -> bool:
    """Is Alertmanager holding this alert by name?"""
    return any(
        entry.get("labels", {}).get("alertname") == alert
        for entry in alertmanager_alerts(port)
    )
