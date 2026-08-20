"""Evidently as a SECOND WITNESS, and the argument for why it is not the first.

M7-S3. The blueprint names Evidently and this module is it — but it is
deliberately not the instrument the alert reads, and the reason is arithmetic
rather than taste.

**Five of the six monitored columns are categorical.** A categorical
distribution is COMPLETELY described by value counts, and DuckDB computes value
counts over 43,987,422 reference rows exactly, in seconds, with no sampling and
no memory pressure. Evidently wants row-level frames on both sides, so using it
as the alerting instrument would mean sampling — and a sampled estimate of a
quantity that can be computed exactly is a worse number **that also changes
between runs**. A threshold compared against a number that moves when nothing
moved is the shape of every alert nobody trusts. So `drift.py` computes PSI in
SQL and this runs beside it.

WHAT A SECOND WITNESS IS FOR
-----------------------------
The same thing it is for everywhere else in this program (M4-S4's cache drill,
M6-S4's canary counters): **a claim that only one instrument can make is not
checkable.** `drift.py` is code this repository wrote, and its PSI could be
wrong in a way its own unit tests share. Evidently is an independent
implementation, by other people, with its own statistical tests (Jensen-Shannon,
Wasserstein, chi-square by column type) — so when it agrees about WHICH columns
moved and which did not, the agreement is evidence about the world rather than
about our arithmetic. When it disagrees, that is the finding.

It is not expected to agree on the NUMBERS: PSI and Jensen-Shannon distance are
different statistics with different scales. Agreement means the same ranking and
the same drifted/not-drifted verdicts, and that is what `compare()` reports.

THE SAMPLE IS SEEDED AND THE SEED IS RECORDED, for M5-S3's reason: an
unreproducible number in a record is a number nobody can check twice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import duckdb

from ..data.analyst import database_path
from ..data.config import DataConfig, load_config
from .drift import MONITORED_COLUMNS

#: Rows per side. 200,000 is far above what any of these tests needs for power
#: and far below what would make the run slow; the exact number matters much
#: less than it being FIXED and recorded.
SAMPLE_ROWS = 200_000

#: DuckDB's `USING SAMPLE ... REPEATABLE(n)` seed. Fixed so two runs of this
#: witness over unchanged data produce the same answer — otherwise a
#: disagreement with `drift.py` could never be attributed.
SAMPLE_SEED = 20200301


@dataclass
class EvidentlyVerdict:
    month: str
    sample_rows: int
    sample_seed: int
    evidently_version: str
    #: column -> Evidently's own drift score (statistic depends on column type)
    scores: dict[str, float]
    #: column -> Evidently's boolean verdict at ITS OWN defaults
    drifted: dict[str, bool]
    dataset_drift_share: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "month": self.month,
            "sample_rows": self.sample_rows,
            "sample_seed": self.sample_seed,
            "evidently_version": self.evidently_version,
            "scores": self.scores,
            "drifted": self.drifted,
            "dataset_drift_share": self.dataset_drift_share,
        }


def _frame(connection: duckdb.DuckDBPyConnection, view: str, where: str):
    columns = ", ".join(f"{c.expression} AS {c.name}" for c in MONITORED_COLUMNS)
    return connection.execute(
        f"SELECT {columns} FROM {view} WHERE {where} "  # noqa: S608
        f"USING SAMPLE {SAMPLE_ROWS} ROWS (reservoir, {SAMPLE_SEED})"
    ).df()


def run(
    month: str,
    *,
    cfg: DataConfig | None = None,
) -> EvidentlyVerdict:
    """Evidently's verdict on one scoring month, against the same train reference."""
    import evidently
    from evidently import DataDefinition, Dataset, Report
    from evidently.presets import DataDriftPreset

    cfg = cfg or load_config()
    connection = duckdb.connect(str(database_path(cfg)), read_only=True)
    try:
        reference = _frame(connection, "trips_train", "1=1")
        current = _frame(connection, "trips_scoring", f"month = '{month}'")
    finally:
        connection.close()

    definition = DataDefinition(
        numerical_columns=[c.name for c in MONITORED_COLUMNS if c.kind == "numeric"],
        categorical_columns=[c.name for c in MONITORED_COLUMNS if c.kind == "categorical"],
    )
    snapshot = Report(metrics=[DataDriftPreset()]).run(
        current_data=Dataset.from_pandas(current, data_definition=definition),
        reference_data=Dataset.from_pandas(reference, data_definition=definition),
    )
    payload = snapshot.dict()

    scores: dict[str, float] = {}
    drifted: dict[str, bool] = {}
    share = 0.0
    for metric in payload.get("metrics", []):
        metric_id = str(metric.get("metric_id", ""))
        value = metric.get("value")
        if metric_id.startswith("ValueDrift") and isinstance(value, (int, float)):
            # `ValueDrift(column=hour)` — the column is inside the id.
            inner = metric_id[metric_id.find("=") + 1 : metric_id.rfind(")")]
            scores[inner] = float(value)
        elif metric_id.startswith("DriftedColumnsCount") and isinstance(value, dict):
            share = float(value.get("share", 0.0))

    for metric in payload.get("metrics", []):
        metric_id = str(metric.get("metric_id", ""))
        if metric_id.startswith("ValueDrift"):
            inner = metric_id[metric_id.find("=") + 1 : metric_id.rfind(")")]
            status = metric.get("status")
            drifted[inner] = str(status).upper().endswith("FAIL") if status else False

    return EvidentlyVerdict(
        month=month,
        sample_rows=SAMPLE_ROWS,
        sample_seed=SAMPLE_SEED,
        evidently_version=getattr(evidently, "__version__", "unknown"),
        scores=scores,
        drifted=drifted,
        dataset_drift_share=share,
    )
