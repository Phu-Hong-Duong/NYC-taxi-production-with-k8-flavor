"""Check the front door against the repository it describes (M9-S8).

The README is the first artifact a public reader meets and the only one nobody
runs. Every other number this program publishes has a twin that re-derives it —
`scripts/error_memo_numbers.py` for the M2 error memo, `scripts/drift_memo_numbers.py`
for the M7 drift memo, and `verify-m5` §6 for the serving runbook's prose. This is
that twin for `README.md`, and it exists for the same reason: *a front door nobody
can re-derive is marketing.*

Four legs, each of which can fail on its own:

1. **Targets.** Every ``make <target>`` the README names must exist in the Makefile.
   A renamed target turns the quickstart into a typo for somebody who has never
   seen this repo — the `verify-m5` runbook leg's argument, applied one audience out.
2. **Paths.** Every repo-relative path the README names must exist on disk. The
   front door links into `docs/`, `ledgers/` and `automation/runs/`; a moved file
   makes the reader's first click a 404.
3. **Numbers.** Every claim in the README's evidence table is re-read from the
   record that holds it and compared **at the precision the README renders it at**
   (gotcha #42), under a one-decimal floor (gotcha #90) — a claim rendered at zero
   decimals matches almost any document and is not a check.
4. **The Status table.** Its rows are append-only history; this leg asserts the
   ten milestone rows plus the two close rows are all still present, so a rewrite
   of the front door cannot quietly drop the ledger it grew from.

Run it: ``make readme-check``. It reads; it writes nothing, deploys nothing and
asks the cluster nothing.

The test-count leg shells out to ``pytest --collect-only``. When this script is
itself invoked from inside a pytest run, pass ``--no-collect``: the number is then
checked by the CLI (which is what the story's evidence cites) rather than by a
pytest process nested inside a pytest process. `tests/unit/test_readme.py` asserts
that the CLI's default still includes the leg, so it cannot quietly disappear.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
README = REPO / "README.md"
MAKEFILE = REPO / "Makefile"
RULES = REPO / "infra" / "monitoring" / "alerting_rules.yml"

#: Targets a reader is told to run that are deliberately NOT in the Makefile.
#: Empty, and kept as a named empty set rather than deleted: the next honest
#: exception has to be recorded here, where a reviewer sees it.
NON_MAKE_TARGETS: set[str] = set()


class ReadmeError(AssertionError):
    """The README says something this repository does not."""


# --------------------------------------------------------------------------- #
# claims
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Claim:
    """One number in the README, the record that holds it, and how to read it."""

    #: What the README renders. Must appear verbatim in the file.
    rendered: str
    #: Where a reader is told to look — a repo-relative path, checked to exist.
    record: str
    #: Reads the record and returns the value the rendered text must equal.
    resolve: Callable[[], float | int | str]
    #: Prose for the transcript.
    about: str


def _json(path: str) -> dict:
    return json.loads((REPO / path).read_text())


ONLINE = "automation/runs/m8-online/online_parity.json"
KILL = "automation/runs/m6-gameday/kill.json"
CANARY = "automation/runs/m6-canary/release_drill.json"
STORE = "automation/runs/m9-store-watch/headroom.json"
DRIFT_HEADROOM = "automation/runs/m7-drift/headroom.json"


def _headroom_max_psi() -> float:
    """The noisiest ACCEPTED 2019 month — the reason 0.10 is a bar and not a hunch."""
    return max(month["max_input_psi"] for month in _json(DRIFT_HEADROOM).values())


def _at(path: str, *keys: str):
    """One value out of one record, named by the keys a reader would follow.

    A missing key raises `KeyError`, which `main`'s leg reports as *could not read
    the record* naming the claim — the shape of a record moving is a finding about
    this table, never a silent `None` that formats into a plausible number.
    """
    value = _json(path)
    for key in keys:
        value = value[key]
    return value


def _bakeoff_winner_test_mae() -> float:
    record = _json("automation/runs/m3s5/bakeoff.json")
    winner = record["winner"]
    rows = [row for row in record["contenders"] if row["label"] == winner]
    if len(rows) != 1:
        raise ReadmeError(
            f"automation/runs/m3s5/bakeoff.json names winner {winner!r} and "
            f"{len(rows)} contender row(s) carry that label"
        )
    return rows[0]["test_mae"]


def _bakeoff_holdout_rows() -> int:
    record = _json("automation/runs/m3s5/bakeoff.json")
    rows = {row["test_rows"] for row in record["contenders"]}
    if len(rows) != 1:
        raise ReadmeError(f"the bake-off's contenders disagree on the holdout size: {rows}")
    return rows.pop()


def _retrain_incumbent_delta_pct() -> float:
    """The refusal's own arithmetic, re-derived rather than read off its prose."""
    verdict = _json("automation/runs/m7-retrain/latest.json")["verdict"]
    challenger = verdict["challenger_mae"]
    incumbent = verdict["incumbent_mae"]
    if verdict["verdict"] != "REFUSE":
        raise ReadmeError("the retrain record no longer carries a REFUSE")
    return (incumbent - challenger) / incumbent * 100.0


def _alert_rule_count() -> int:
    document = yaml.safe_load(RULES.read_text())
    return sum(len(group.get("rules", [])) for group in document["groups"])


def _alert_signal_count() -> int:
    document = yaml.safe_load(RULES.read_text())
    signals = {
        rule["labels"]["signal"] for group in document["groups"] for rule in group.get("rules", [])
    }
    return len(signals)


def _make_targets() -> set[str]:
    return {
        match.group(1) for match in re.finditer(r"^([A-Za-z0-9_.-]+):", MAKEFILE.read_text(), re.M)
    }


def _gate_count() -> int:
    return len({t for t in _make_targets() if re.fullmatch(r"verify-m\d", t)})


def _redteam_count() -> int:
    return len({t for t in _make_targets() if re.fullmatch(r"verify-m\d-redteam", t)})


def _collected_tests() -> int:
    proc = subprocess.run(
        ["uv", "run", "pytest", "tests/unit", "-q", "--collect-only"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    match = re.search(r"^(\d+) tests collected", proc.stdout, re.M)
    if not match:
        raise ReadmeError(
            "could not read a test count out of `pytest --collect-only`; "
            f"exit {proc.returncode}, tail: {proc.stdout[-300:]!r}"
        )
    return int(match.group(1))


CLAIMS: tuple[Claim, ...] = (
    Claim(
        "0.000e+00",
        "automation/runs/m5-parity/parity.json",
        lambda: _json("automation/runs/m5-parity/parity.json")["max_abs_delta_minutes"],
        "the champion's wire parity, M5-S3",
    ),
    Claim(
        "16 declared hazard rows",
        "automation/runs/m5-parity/parity.json",
        lambda: f"{_json('automation/runs/m5-parity/parity.json')['rows']} declared hazard rows",
        "the declared row set both wire seams share",
    ),
    Claim(
        "1e-6",
        "automation/runs/m5-parity/parity.json",
        # `format(1e-06, '.0e')` is `1e-06`; the README writes the bar the way
        # M5-S3's own documents write it, so the zero-padded exponent is stripped
        # here rather than the prose bent to match a formatter.
        lambda: format(
            _json("automation/runs/m5-parity/parity.json")["tolerance_minutes"], ".0e"
        ).replace("e-0", "e-"),
        "M5-S3's bar",
    ),
    Claim(
        "0.000e+00",
        "automation/runs/m8-transformer/transformer-parity.json",
        lambda: _json("automation/runs/m8-transformer/transformer-parity.json")[
            "max_abs_delta_minutes"
        ],
        "parity through the moved boundary, M8-S4 leg 3",
    ),
    Claim(
        "0.000e+00",
        "automation/runs/m8-online/online_parity.json",
        lambda: _json("automation/runs/m8-online/online_parity.json")["max_abs_delta"],
        "online vs offline feature values, M8-S4 leg 1",
    ),
    Claim(
        "100 declared pairs",
        "automation/runs/m8-online/online_parity.json",
        lambda: (
            f"{_at(ONLINE, 'declared_pairs')} declared pairs"
        ),
        "the online parity's declared row set",
    ),
    Claim(
        "3.2403 min",
        "automation/runs/m3s5/bakeoff.json",
        lambda: f"{_bakeoff_winner_test_mae():.4f} min",
        "the champion on the untouched holdout, M3-S5",
    ),
    Claim(
        "5,950,708 rows",
        "automation/runs/m3s5/bakeoff.json",
        lambda: f"{_bakeoff_holdout_rows():,} rows",
        "the holdout's size",
    ),
    Claim(
        "3.2412 vs 3.2403 = −0.03%",
        "automation/runs/m7-retrain/latest.json",
        lambda: (
            f"{_json('automation/runs/m7-retrain/latest.json')['verdict']['challenger_mae']:.4f}"
            f" vs {_json('automation/runs/m7-retrain/latest.json')['verdict']['incumbent_mae']:.4f}"
            f" = {_retrain_incumbent_delta_pct():+.2f}%".replace("-", "−")
        ),
        "the refusal M7-S4 measured",
    ),
    Claim(
        "p50 17.207 ms",
        "automation/runs/m5-load/headline.json",
        lambda: f"p50 {_json('automation/runs/m5-load/headline.json')['latency_ms']['p50']:.3f} ms",
        "the headline load shape, M5-S4",
    ),
    Claim(
        "p95 104.226 ms",
        "automation/runs/m5-load/headline.json",
        lambda: f"p95 {_json('automation/runs/m5-load/headline.json')['latency_ms']['p95']:.3f} ms",
        "the headline load shape, M5-S4",
    ),
    Claim(
        "4 req/s × 60 s",
        "automation/runs/m5-load/headline.json",
        lambda: (
            f"{_json('automation/runs/m5-load/headline.json')['shape']['target_rate_per_second']:.0f}"
            f" req/s × "
            f"{_json('automation/runs/m5-load/headline.json')['shape']['window_seconds']:.0f} s"
        ),
        "the shape the percentiles belong to",
    ),
    Claim(
        "13.75 s",
        "automation/runs/m6-gameday/kill.json",
        lambda: (
            f"{_json('automation/runs/m6-gameday/kill.json')['observed']['outage_seconds']:.2f} s"
        ),
        "self-heal after the predictor is destroyed, M6-S5",
    ),
    Claim(
        "55 requests lost",
        "automation/runs/m6-gameday/kill.json",
        lambda: (
            f"{_at(KILL, 'observed', 'error_count')} requests lost"
        ),
        "what the outage cost",
    ),
    Claim(
        "1,440 requests, 0 errors",
        "automation/runs/m6-canary/release_drill.json",
        lambda: (
            f"{_json('automation/runs/m6-canary/release_drill.json')['load']['requests']['sent']:,}"
            f" requests, "
            f"{_json('automation/runs/m6-canary/release_drill.json')['load']['requests']['errors']}"
            " errors"
        ),
        "the release rehearsal, M6-S4",
    ),
    Claim(
        "0.37 s",
        "automation/runs/m6-canary/release_drill.json",
        lambda: (
            f"{_at(CANARY, 'revert', 'nginx_cleared_seconds'):.2f} s"
        ),
        "what the traffic revert costs",
    ),
    Claim(
        "0.3913×",
        "automation/runs/m7-drift/drift-2020-03.json",
        lambda: f"{_json('automation/runs/m7-drift/drift-2020-03.json')['volume_ratio']:.4f}×",
        "March 2020's volume against the 2019 reference",
    ),
    Claim(
        "PSI **0.0217**",
        "automation/runs/m7-drift/drift-2020-03.json",
        lambda: (
            f"PSI **{_json('automation/runs/m7-drift/drift-2020-03.json')['max_input_psi']:.4f}**"
        ),
        "March 2020's most-moved input column",
    ),
    Claim(
        "PSI 0.0323",
        "automation/runs/m7-drift/headroom.json",
        lambda: (
            f"PSI {_headroom_max_psi():.4f}"
        ),
        "the noisiest ACCEPTED 2019 month, which is what makes 0.10 a bar",
    ),
    Claim(
        "**43,987,422** rows",
        "automation/runs/m7-drift/drift-2020-03.json",
        lambda: (
            f"**{_json('automation/runs/m7-drift/drift-2020-03.json')['reference_rows']:,}** rows"
        ),
        "the training window the champion was fitted on",
    ),
    Claim(
        "**57,688** keys",
        "automation/runs/m9-store-watch/headroom.json",
        lambda: (
            f"**{_at(STORE, 'expected_keys', 'total'):,}** keys"
        ),
        "the online store's key count, M9-S2",
    ),
    Claim(
        "16 rules",
        "infra/monitoring/alerting_rules.yml",
        lambda: f"{_alert_rule_count()} rules",
        "what Prometheus is loaded with",
    ),
    Claim(
        "13 signal ids",
        "infra/monitoring/alerting_rules.yml",
        lambda: f"{_alert_signal_count()} signal ids",
        "the SLO doc's signal ids that have a rule",
    ),
    Claim(
        "3.30%",
        "automation/runs/m7-retrain/latest.json",
        lambda: (
            f"{_json('automation/runs/m7-retrain/latest.json')['verdict']['observed_pct_vs_floor']:.2f}%"
        ),
        "what the refused challenger DID beat",
    ),
    Claim(
        "2.00%",
        "automation/runs/m7-retrain/latest.json",
        lambda: (
            f"{_json('automation/runs/m7-retrain/latest.json')['verdict']['required_pct_vs_floor']:.2f}%"
        ),
        "the floor condition's bar",
    ),
    Claim(
        "zero unacknowledged",
        "automation/runs/m9-security/scan.json",
        lambda: (
            "zero unacknowledged"
            if _json("automation/runs/m9-security/scan.json")["verdict"]["secrets_in_git"] == 0
            else "SECRETS IN GIT"
        ),
        "the pre-publish secret verdict (M9-S9)",
    ),
    Claim(
        "~932 MiB",
        "automation/runs/m4-image/image.json",
        lambda: f"~{_json('automation/runs/m4-image/image.json')['content_bytes'] / 2**20:.0f} MiB",
        "the task image a first run builds",
    ),
    Claim(
        "20 checks",
        "automation/runs/m9-hook/redteam.json",
        lambda: f"{_json('automation/runs/m9-hook/redteam.json')['checks']} checks",
        "the pre-commit hook drill (M9-S13)",
    ),
    Claim(
        "0 failures",
        "automation/runs/m9-hook/redteam.json",
        lambda: f"{_json('automation/runs/m9-hook/redteam.json')['failures']} failures",
        "the pre-commit hook drill's verdict",
    ),
)

#: Claims whose record is not a file on disk (a command, or the Makefile itself).
COMMAND_CLAIMS: tuple[Claim, ...] = (
    Claim("10 gates", "Makefile", lambda: f"{_gate_count()} gates", "milestone acceptance gates"),
    Claim(
        "8 red teams",
        "Makefile",
        lambda: f"{_redteam_count()} red teams",
        "their red teams",
    ),
)

TEST_COUNT_CLAIM = Claim(
    "1,408 tests",
    "uv run pytest tests/unit -q",
    lambda: f"{_collected_tests():,} tests",
    "the host suite",
)


# --------------------------------------------------------------------------- #
# legs
# --------------------------------------------------------------------------- #


def check_targets(text: str) -> list[str]:
    """Every `make <target>` the README names exists in the Makefile.

    A README legitimately writes PLACEHOLDERS — `make verify-mN` names a family,
    not a target — and a lowercase-only pattern truncates one into `verify-m`,
    which is a target this repo has never had. So the character after the match is
    read: if it is another letter, the pattern stopped mid-word and what was found
    is a placeholder, not an invocation (gotcha #99's family — a needle must match
    what a shell would actually run).
    """
    named = sorted(
        {
            match.group(1)
            for match in re.finditer(r"`?make ([a-z0-9][a-z0-9-]*)([A-Za-z]?)", text)
            if not match.group(2)
        }
    )
    targets = _make_targets()
    missing = [t for t in named if t not in targets and t not in NON_MAKE_TARGETS]
    if missing:
        raise ReadmeError(
            f"the README tells a reader to run {missing}, and the Makefile has no such "
            "target — the first command a stranger types must not be a typo"
        )
    return named


def check_paths(text: str) -> list[str]:
    """Every repo-relative path the README names exists.

    Repo-relative means it carries a ``/``. A bare filename in backticks is prose
    shorthand — the Status table says `PROGRAM_CLOSE.md` inside a row whose subject
    is already `docs/milestones/` — and resolving it against the repo root would
    fail for a link that is not broken.
    """
    candidates = {
        path
        for path in re.findall(r"`([A-Za-z0-9_./-]+\.(?:md|json|yml|yaml|sh|py))`", text)
        if "/" in path
    }
    candidates |= set(
        re.findall(r"`((?:docs|ledgers|automation|infra|scripts|demo)/[A-Za-z0-9_./-]*/)`", text)
    )
    named = sorted(candidates)
    missing = [p for p in named if not (REPO / p).exists()]
    if missing:
        raise ReadmeError(f"the README links to paths this repo does not have: {missing}")
    return named


def _decimals(rendered: str) -> int:
    match = re.search(r"\.(\d+)", rendered)
    return len(match.group(1)) if match else 0


def check_claim(claim: Claim, text: str) -> str:
    """The rendered text appears in the README AND equals what the record says.

    The presence half is a substring search, so a rendered form of `10` would be
    satisfied by the `10` inside `104.226 ms` and would go green against a README
    that no longer makes the claim at all. Every claim therefore has to carry a
    non-digit anchor — the unit, the noun, the sign (gotcha #76's rule, applied to
    this table rather than to a runbook).
    """
    if not re.search(r"[^\d.,]", claim.rendered):
        raise ReadmeError(
            f"{claim.rendered!r} is a bare number with nothing to anchor it; render "
            "it with its unit or noun so the presence check can fail"
        )
    if claim.rendered not in text:
        raise ReadmeError(
            f"the README no longer renders {claim.rendered!r} ({claim.about}); a claim "
            "that has moved must move in this table too, or it is unchecked"
        )
    actual = claim.resolve()
    if isinstance(actual, float):
        rendered_value = claim.rendered
        if _decimals(rendered_value) < 1 and abs(actual) >= 1:
            raise ReadmeError(
                f"{claim.rendered!r} is rendered at zero decimals; a whole number matches "
                "almost any document and is not a check (gotcha #90)"
            )
        as_text = f"{actual:.{max(_decimals(rendered_value), 1)}e}"
        if (
            as_text != rendered_value
            and f"{actual:.{_decimals(rendered_value)}f}" != rendered_value
        ):
            raise ReadmeError(
                f"the README says {claim.rendered!r} for {claim.about}; "
                f"{claim.record} holds {actual!r}"
            )
    elif str(actual) != claim.rendered:
        raise ReadmeError(
            f"the README says {claim.rendered!r} for {claim.about}; "
            f"{claim.record} holds {str(actual)!r}"
        )
    return f"{claim.rendered}  ({claim.about} — {claim.record})"


STATUS_ROWS = (
    "| M0 Foundations",
    "| M1 Data platform",
    "| M2 Modeling I",
    "| M3 Modeling II",
    "| M4 Pipeline on-cluster",
    "| M5 Serving & PRR",
    "| M6 Reliability",
    "| M7 Drift & retrain loop",
    "| M8 Feast & side-by-side",
    "| M9 Stretch",
    "| **PROGRAM CLOSE**",
    "| **M9 Epilogue**",
    "| **M9 Publish**",
)


def check_status_table(text: str) -> int:
    """The Status table's history is append-only; a rewrite may not drop a row."""
    missing = [row for row in STATUS_ROWS if row not in text]
    if missing:
        raise ReadmeError(
            f"the Status table has lost {missing} — the front door gains an audience, "
            "it does not lose its ledger"
        )
    return len(STATUS_ROWS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-collect",
        action="store_true",
        help="skip the leg that shells out to pytest (use when run from inside pytest)",
    )
    args = parser.parse_args(argv)

    failures: list[str] = []

    def leg(name: str, run: Callable[[], object]) -> None:
        try:
            result = run()
        except ReadmeError as exc:
            failures.append(f"{name}: {exc}")
            print(f"[readme-check] FAIL {name}\n               {exc}")
        except Exception as exc:  # noqa: BLE001 - a checker that dies reports nothing
            # A record whose SHAPE moved (a renamed key, a file gone) is a finding
            # about this table, not a reason to abandon the other legs — the run
            # must still say which claims it could and could not support.
            failures.append(f"{name}: could not read the record: {exc!r}")
            print(f"[readme-check] FAIL {name}\n               could not read the record: {exc!r}")
        else:
            print(f"[readme-check] ok   {name}: {result}")

    text = README.read_text()

    print("[readme-check] README.md against the repository it describes")
    leg("make targets exist", lambda: f"{len(check_targets(text))} named, all in the Makefile")
    leg("linked paths exist", lambda: f"{len(check_paths(text))} named, all present")
    leg("Status table intact", lambda: f"{check_status_table(text)} rows present")

    claims = list(CLAIMS) + list(COMMAND_CLAIMS)
    if not args.no_collect:
        claims.append(TEST_COUNT_CLAIM)
    else:
        print(
            "[readme-check] --no-collect: the test count is the CLI's leg (module docstring)"
        )

    print(f"[readme-check] {len(claims)} claim(s), each read back from its record")
    for claim in claims:
        leg(f"claim {claim.rendered!r}", lambda c=claim: check_claim(c, text))

    if failures:
        print(f"\n[readme-check] RED — {len(failures)} claim(s) the README cannot support.")
        return 1
    print("\n[readme-check] GREEN — every target, path and number in README.md checks out.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
