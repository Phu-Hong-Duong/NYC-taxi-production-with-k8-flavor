#!/usr/bin/env python
"""Render the checked-in alert rules into a helm values overlay — and REFUSE a bad one.

M6-S2. `infra/monitoring/alerting_rules.yml` is a plain Prometheus rules file:
the format `promtool check rules` reads, reviewable in a diff, and the only copy.
The prometheus chart wants those same rules nested under
`serverFiles."alerting_rules.yml"`, so something has to do the nesting.

**WHY A RENDERER AND NOT A SECOND COPY INSIDE prometheus-values.yaml.** Two files
holding the same rules is the twin problem this program has hit four times
(port pairs, the mart list, the KPI ids, `.dockerignore` vs `.gitignore`), and it
fails the same way every time: one copy is edited and the other is the one that
runs. Nesting is a mechanical transformation, so it belongs in code that runs at
deploy time, not in a human's copy-paste.

**WHY IT PARSES RATHER THAN INDENTS.** The obvious implementation is to indent
the file by four spaces and paste it under a key. That produces valid-looking
YAML for a file with a syntax error in it, and the first thing anyone would know
about it is Prometheus refusing to load rules while `helm upgrade` reports
success. This reads the file with a YAML parser and re-emits it, so a malformed
rules file fails HERE, before anything is applied.

**WHAT IT REFUSES**, beyond parse errors — each of these has cost this program a
session in another form:
  * a rule with no `expr`, no `labels.severity` or no `annotations.why`
    (a threshold whose argument is not written down is the thing M6's kickoff
    legislates against);
  * a rule whose `signal` label is not one of the PRR's A-ids;
  * an A-id that this repo claims to implement but does not appear in the file
    (the list is DERIVED from the file's own rules and checked against the
    documented implemented-set, so adding a rule without documenting it, or
    documenting one without adding it, both fail — F-017's both-sides rule).

Usage:
    uv run python scripts/render_alert_rules.py            # overlay YAML to stdout
    uv run python scripts/render_alert_rules.py --check    # validate only, exit 0/1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
RULES_FILE = REPO_ROOT / "infra" / "monitoring" / "alerting_rules.yml"

# The M5 PRR box 3 signal ids. Every rule must claim exactly one of these.
KNOWN_SIGNALS = {"A-1", "A-2", "A-3", "A-4", "A-5", "A-6", "A-7"}

# The signals this stack CAN alert on, and therefore must. A-3's client half and
# A-4 have no metric source here (F-035) — they are documented absences in
# docs/slo_serving.md §6, not forgotten ones, and this set is what makes the
# difference checkable.
IMPLEMENTED_SIGNALS = {"A-1", "A-2", "A-3", "A-5", "A-6", "A-7"}

REQUIRED_ANNOTATIONS = ("summary", "why")


class RulesError(ValueError):
    """The rules file is not shippable, and the message says which rule."""


def load_rules(path: Path = RULES_FILE) -> dict[str, Any]:
    if not path.exists():
        raise RulesError(f"{path} does not exist — there are no rules to provision.")
    document = yaml.safe_load(path.read_text())
    if not isinstance(document, dict) or "groups" not in document:
        raise RulesError(f"{path} does not look like a Prometheus rules file (no 'groups' key).")
    return document


def validate(document: dict[str, Any]) -> list[str]:
    """Return the alert names, or raise naming the first rule that is not shippable."""
    names: list[str] = []
    signals: set[str] = set()
    groups = document.get("groups") or []
    if not groups:
        raise RulesError("the rules file has no groups — an empty rules file is not a rule set.")
    for group in groups:
        for rule in group.get("rules") or []:
            name = rule.get("alert")
            if not name:
                raise RulesError(f"a rule in group {group.get('name')!r} has no 'alert' name.")
            if not rule.get("expr"):
                raise RulesError(f"{name}: no 'expr'.")
            labels = rule.get("labels") or {}
            if not labels.get("severity"):
                raise RulesError(f"{name}: no labels.severity — nothing can route it.")
            signal = labels.get("signal")
            if signal not in KNOWN_SIGNALS:
                raise RulesError(
                    f"{name}: labels.signal is {signal!r}, which is not one of the PRR's "
                    f"signal ids {sorted(KNOWN_SIGNALS)}."
                )
            annotations = rule.get("annotations") or {}
            for key in REQUIRED_ANNOTATIONS:
                if not annotations.get(key):
                    raise RulesError(
                        f"{name}: no annotations.{key}. A threshold whose argument is not "
                        "written beside it is a number nobody can review."
                    )
            names.append(name)
            signals.add(signal)

    missing = IMPLEMENTED_SIGNALS - signals
    if missing:
        raise RulesError(
            f"the rules file implements {sorted(signals)} but this repo claims "
            f"{sorted(IMPLEMENTED_SIGNALS)}: {sorted(missing)} has no rule. Either add the "
            "rule or move the signal to the documented-absence list in this script AND in "
            "docs/slo_serving.md §6 — the two must move together."
        )
    extra = signals - IMPLEMENTED_SIGNALS
    if extra:
        raise RulesError(
            f"the rules file implements {sorted(extra)}, which this repo documents as having "
            "no metric source. If that changed, say so in docs/slo_serving.md §6 first."
        )
    return names


def render_overlay(document: dict[str, Any]) -> str:
    """The helm values overlay: the rules, nested under the chart's own key."""
    overlay = {"serverFiles": {"alerting_rules.yml": document}}
    return yaml.safe_dump(overlay, default_flow_style=False, sort_keys=False, width=1000)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate only; print a summary")
    parser.add_argument("--rules", default=str(RULES_FILE))
    args = parser.parse_args(argv)

    try:
        document = load_rules(Path(args.rules))
        names = validate(document)
    except RulesError as error:
        print(f"[alert-rules] REFUSED: {error}", file=sys.stderr)
        return 1

    if args.check:
        print(f"[alert-rules] ok  {len(names)} rule(s) validated in {args.rules}")
        for group in document["groups"]:
            for rule in group.get("rules") or []:
                labels = rule.get("labels", {})
                print(
                    f"[alert-rules]     {labels.get('signal'):4s} {rule['alert']:38s} "
                    f"for={rule.get('for', '0m'):4s} severity={labels.get('severity')}"
                )
        return 0

    sys.stdout.write(render_overlay(document))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
