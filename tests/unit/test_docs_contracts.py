"""The M1-S3 documents are contracts, so they get tests — cluster-free, network-free.

`docs/kpi_definitions.md` is not prose that happens to contain numbers: M1-S5's
board cards cite its ids, M2's error memo cites KPI-09/KPI-10, and M7's drift
memos cite the segment dimensions. `docs/prior_art.md` carries an acceptance
count (>= 6 verdicts) that M1-S5's `verify-m1` has to check somehow, and a
document is a much easier thing to quietly hollow out than a function.

What must say NO:

* a KPI id that loses its formula, source, window or owner — a number without its
  definition and window is the DA charter's first refusal, and the failure is
  silent because the id keeps resolving;
* the prior-art table dropping below the >= 6 verdicts M1's gate quotes, or
  filling itself with verdicts that cite no source;
* a survey with no ADOPT rows — "a survey with zero adopts wasn't looking" is the
  protocol's own wording, and a self-congratulatory table passes every other check;
* the EDA report reaching for a parquet path instead of a named view (DA charter
  refusal #2) — the same rule `test_data_analyst.py` enforces on the views
  themselves, applied to the document that consumes them.

These read the SHIPPED files, not fixtures. A test over a hand-written copy would
stop testing the documents and start testing the copy.
"""

from __future__ import annotations

import re

import pytest

from taxi_mlops.data.config import repo_root

# The three documents M1-S3 ships, and the M1 gate's quoted acceptance counts.
EDA_REPORT = "docs/eda_report.md"
KPI_DOC = "docs/kpi_definitions.md"
PRIOR_ART = "docs/prior_art.md"

MIN_KPIS = 5  # kickoff: "KPI doc holds >= 5 definitions with ids and formulas"
MIN_VERDICTS = 6  # BLUEPRINT S9/M1: "prior_art.md has >= 6 verdicts"

VERDICTS = ("ADOPT", "DIFFER", "SURPASS")


def _read(relative: str) -> str:
    path = repo_root() / relative
    assert path.is_file(), f"{relative} is missing — M1-S3 shipped it"
    return path.read_text(encoding="utf-8")


def _kpi_sections(text: str) -> dict[str, str]:
    """Split the KPI doc into `KPI-NN` -> its section body.

    Anchored on the `### KPI-NN` heading the document actually uses, so a heading
    that stops being a heading is a failure rather than a silently empty dict.
    A section ends at the next KPI heading OR the next `##` section — without the
    second bound the LAST KPI absorbs every trailing paragraph, and assertions
    about its body start passing for the wrong reason.
    """
    headings = list(re.finditer(r"^### (KPI-\d+) — (.+)$", text, re.MULTILINE))
    boundaries = [m.start() for m in re.finditer(r"^## ", text, re.MULTILINE)]
    sections: dict[str, str] = {}
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        following = [b for b in boundaries if b > match.start()]
        if following:
            end = min(end, following[0])
        sections[match.group(1)] = text[match.start() : end]
    return sections


def _source_keys(text: str) -> dict[str, str]:
    """Rows of the sources table: `**A**` -> the row defining it."""
    keys: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        match = re.fullmatch(r"\*\*([A-Z])\*\*", cells[0]) if cells else None
        if match:
            keys[match.group(1)] = stripped
    return keys


def _verdict_rows(text: str) -> list[str]:
    """Rows of the prior-art table that carry a verdict, ignoring the header."""
    rows = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("|---"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        # A verdict row is numbered and carries one of the three verdicts.
        if len(cells) >= 5 and cells[0].isdigit():
            rows.append(stripped)
    return rows


# --------------------------------------------------------------------------- KPIs


def test_kpi_doc_holds_at_least_the_gate_count():
    sections = _kpi_sections(_read(KPI_DOC))
    assert len(sections) >= MIN_KPIS, (
        f"{KPI_DOC} defines {len(sections)} KPIs, the kickoff requires >= {MIN_KPIS}"
    )


def test_kpi_ids_are_unique_and_unbroken():
    """Ids are cited by other documents; a duplicate or a gap breaks the citation."""
    sections = _kpi_sections(_read(KPI_DOC))
    numbers = sorted(int(kpi.split("-")[1]) for kpi in sections)
    assert len(numbers) == len(set(numbers)), f"duplicate KPI id in {KPI_DOC}: {numbers}"
    assert numbers == list(range(1, len(numbers) + 1)), (
        f"KPI ids must run 1..N with no gaps (a gap reads as a deleted KPI): {numbers}"
    )


@pytest.mark.parametrize("field", ["**Formula:**", "**Source:**", "**Window", "**Owner:**"])
def test_every_kpi_carries_its_definition(field: str):
    """The DA charter's first refusal, enforced: no number without its definition."""
    missing = [kpi for kpi, body in _kpi_sections(_read(KPI_DOC)).items() if field not in body]
    assert not missing, f"{field} missing from {missing} in {KPI_DOC}"


def test_money_kpis_state_a_window_and_an_outlier_treatment():
    """AI-2 from the M1-S2 Data Contract Review, pinned so it cannot be undone.

    `fare_amount` maxes at 671,123.14 against a p99.9 of 93.00. A money KPI whose
    window is implied is the exact defect the action item was raised about.
    """
    sections = _kpi_sections(_read(KPI_DOC))
    money = {
        kpi: body
        for kpi, body in sections.items()
        if any(column in body for column in ("fare_amount", "total_amount", "tip_amount"))
    }
    assert money, "no money KPI found — has the doc been restructured?"
    for kpi, body in money.items():
        assert "Outlier treatment" in body, f"{kpi} names a money column but no outlier treatment"
        assert "BETWEEN" in body or "window" in body.lower(), f"{kpi} states no window"


def test_model_quality_kpis_are_not_measured_by_sql(caplog):
    """Gotcha #15: reported model numbers come from the evaluator, nowhere else.

    KPI-09/KPI-10 are defined at M1 and measured at M2. The failure this guards is
    someone pasting the EDA's SQL reference floor in as an observed value, which
    would read as a model result forever after.
    """
    sections = _kpi_sections(_read(KPI_DOC))
    for kpi in ("KPI-09", "KPI-10"):
        body = sections[kpi]
        assert "taxi_mlops.training.evaluate" in body, f"{kpi} does not name the one evaluator"
        assert "gotcha #15" in body, f"{kpi} does not cite the rule it is obeying"


# ---------------------------------------------------------------------- prior art


def test_prior_art_holds_at_least_the_gate_count_of_verdicts():
    rows = _verdict_rows(_read(PRIOR_ART))
    assert len(rows) >= MIN_VERDICTS, (
        f"{PRIOR_ART} holds {len(rows)} verdict rows, the M1 gate quotes >= {MIN_VERDICTS}"
    )


def test_the_sources_table_gives_every_key_a_url():
    """The keys rows cite (`**B**`, `**E**`) are only traceable if the table links them."""
    keys = _source_keys(_read(PRIOR_ART))
    assert len(keys) >= 6, f"{PRIOR_ART} defines {len(keys)} sources, the survey claims eight"
    for key, row in keys.items():
        assert "https://" in row, f"source {key} is defined without a URL"
        assert "2026-" in row, f"source {key} carries no read date"


def test_every_verdict_row_carries_a_verdict_and_a_traceable_source():
    """A verdict with no traceable source is an opinion; the protocol asks for a survey.

    Rows cite EITHER an inline URL or one of the `**A**`..`**F**` keys defined in
    the sources table (the multi-source rows would be unreadable with six inline
    links). Both are traceable; a row citing neither is not.
    """
    keys = _source_keys(_read(PRIOR_ART))
    for row in _verdict_rows(_read(PRIOR_ART)):
        assert any(verdict in row for verdict in VERDICTS), f"row carries no verdict: {row[:90]}"
        cited = "https://" in row or any(f"**{key}" in row or f"{key}," in row for key in keys)
        assert cited, f"row cites neither a URL nor a defined source key: {row[:90]}"


def test_the_survey_actually_adopted_something():
    """"A survey with zero adopts wasn't looking" — the kickoff's own wording."""
    rows = _verdict_rows(_read(PRIOR_ART))
    adopts = [row for row in rows if "ADOPT" in row]
    assert adopts, f"{PRIOR_ART} has no ADOPT row — that is a finding about the survey"


# --------------------------------------------------------------------- EDA report


def test_eda_report_cites_named_views_not_parquet_paths():
    """DA charter refusal #2, applied to the document rather than the query."""
    text = _read(EDA_REPORT)
    offenders = [
        line
        for line in text.splitlines()
        if ".parquet" in line or "data/processed/" in line or "data/raw/" in line
    ]
    assert not offenders, (
        "the EDA report must cite views, never parquet paths (DA charter refusal #2): "
        f"{offenders[:2]}"
    )
    assert "trips_clean" in text, "the EDA report cites no analyst view at all"


def test_eda_report_declares_the_window_it_describes():
    """F-005 is open: the report describes the survivors and must say so.

    If this ever passes silently because the sentence was trimmed, the report
    starts reading as a description of the whole delivery, which it is not.
    """
    text = _read(EDA_REPORT)
    assert "98.397%" in text, "the EDA report no longer states which fraction it describes"
    assert "F-005" in text, "the EDA report no longer names the finding that bounds it"
