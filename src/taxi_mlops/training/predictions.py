"""Row-level predictions — the evaluator's own output, published so it can be argued with.

A milestone that reports `KPI-09 = 3.2608` has published a claim. A milestone that
publishes the 5,950,708 rows the claim was averaged over has published EVIDENCE:
the DA can ask where it fails, and M2's REV session can re-derive the number from
the rows rather than re-reading the transcript that asserted it.

Three rules this module exists to hold:

* **These are MODEL OUTPUT files, not a mart.** The boundary law's one-way door
  (ADR-009, gotcha #22): the dbt marts layer may read what is written here, and
  nothing in this package may name that directory — the law is enforced by a bare
  grep over `src/taxi_mlops/`, which is why this docstring does not spell it
  either. The `error_segments` mart reads these files through the DuckDB analyst
  layer and never the other way round.
* **`split` and `month` are config literals, never parsed from a filename.**
  M1-S2's law, and it bites harder here: a file renamed from `val` to `test`
  would relabel a model's holdout, which is undetectable downstream.
* **What the model SAW is what is written.** The five feature columns are the
  feature matrix itself, not a re-derivation from the trip table — a segment
  analysis over slightly different `hour` values would be an analysis of a
  different model.

The floor's prediction rides in the same row as the model's, deliberately. The
promotion gate is an argument between two predictors on one holdout month; a file
holding only the winner's numbers cannot be used to check the argument, and
"where does v1 actually earn its keep over a `GROUP BY`?" is exactly the question
the error memo is for.

NOT DVC-tracked, on purpose (root `.gitignore`): these are regenerable in one
command from DVC-pinned inputs plus a registry version, and a pin that must be
refreshed every time the champion moves (M3, M7) is a pin that lives stale.
Provenance lives in `predictions.json` beside them and in the registry.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from ..data.config import DataConfig
from .evaluate import Metrics

#: Every column of the published artifact, in write order. A contract other code
#: cites by name: `taxi_mlops.data.analyst` views it, the `error_segments` mart
#: aggregates it, and `tests/unit/test_training_predictions.py` asserts this tuple
#: against a real frame, so a column cannot be dropped here and left dangling
#: in a mart.
PREDICTION_COLUMNS: tuple[str, ...] = (
    "split",
    "month",
    # --- the feature matrix, exactly as the model was handed it.
    "hour",
    "dayofweek",
    "PULocationID",
    "DOLocationID",
    "passenger_count",
    # --- the answer, the model's quote, and the honest floor's quote.
    "actual_minutes",
    "predicted_minutes",
    "floor_predicted_minutes",
    "floor_unseen_group",
    # --- which model said it. The registry answers "which one is that?".
    "model_name",
    "model_version",
)

#: Deliberately ABSENT: `abs_error_minutes`. It is `ABS(predicted - actual)` and
#: storing it would put a second definition of the error one column away from the
#: first — the twins failure this repo keeps paying for. Every consumer derives it
#: the same way, in SQL, from the two columns that define it.
DERIVED_IN_SQL = ("abs_error_minutes", "signed_error_minutes")

#: WHERE the files go is `DataConfig.predictions_path` and nowhere else — one file
#: per (split, month), mirroring `data/processed/`'s layout. The month is in the
#: name even though val and test are one month each today: M7 retrains on a moving
#: window, and a layout that assumes one month per split would need migrating at
#: exactly the moment the data starts moving.


def build_frame(
    *,
    split: str,
    month: str,
    features: pd.DataFrame,
    actual: pd.Series,
    predicted: Any,
    floor_predicted: Any,
    floor_unseen: Any,
    model_name: str,
    model_version: str,
) -> pd.DataFrame:
    """Assemble one split's rows. Pure — no I/O, so a test can check the shape."""
    frame = pd.DataFrame(index=features.index)
    frame["split"] = split
    frame["month"] = month
    for column in ("hour", "dayofweek", "PULocationID", "DOLocationID", "passenger_count"):
        if column not in features.columns:
            raise ValueError(
                f"the feature matrix does not carry {column!r} (it has "
                f"{list(features.columns)}). PREDICTION_COLUMNS describes feature set v1; "
                "a feature set that changes shape needs this contract revised, not bypassed."
            )
        frame[column] = features[column].to_numpy()
    frame["actual_minutes"] = pd.Series(actual).to_numpy(dtype="float64")
    frame["predicted_minutes"] = pd.Series(predicted).to_numpy(dtype="float64")
    frame["floor_predicted_minutes"] = pd.Series(floor_predicted).to_numpy(dtype="float64")
    frame["floor_unseen_group"] = pd.Series(floor_unseen).to_numpy(dtype="bool")
    frame["model_name"] = model_name
    frame["model_version"] = str(model_version)
    return frame[list(PREDICTION_COLUMNS)]


def write(frame: pd.DataFrame, path: Path, data_cfg: DataConfig) -> Path:
    """Write one split's predictions with the SAME writer pins the data path uses.

    `configs/data.yaml: write` is reused rather than re-declared: two parquet
    writer configurations in one repo is how a "byte-identical rebuild" proof
    starts applying to only half the files it names.
    """
    missing = [c for c in PREDICTION_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"refusing to write predictions missing {missing}")
    path.parent.mkdir(parents=True, exist_ok=True)
    frame[list(PREDICTION_COLUMNS)].to_parquet(
        path,
        engine="pyarrow",
        index=False,
        compression=data_cfg.write["compression"],
        row_group_size=data_cfg.write["row_group_size"],
    )
    return path


def manifest(
    *,
    model: dict[str, Any],
    floor: dict[str, Any],
    tolerance_minutes: float,
    metrics: list[Metrics],
) -> dict[str, Any]:
    """Provenance beside the rows: which model, which floor, what it measured.

    TIMESTAMP-FREE, like `data/raw_manifest.json` and for the same reason: a diff
    of this file should mean the predictions moved, not that somebody re-ran the
    command on a Tuesday.
    """
    return {
        "generated_by": "taxi_mlops.training.score",
        "metric_source": "taxi_mlops.training.evaluate",
        "columns": list(PREDICTION_COLUMNS),
        "model": model,
        "floor": floor,
        "tolerance_minutes": tolerance_minutes,
        "splits": [
            {
                "contender": m.contender,
                "split": m.split,
                "rows": m.n,
                "kpi_09_mae_minutes": round(m.mae, 6),
                "kpi_10_within_tolerance_pct": round(m.within_tolerance_rate, 6),
                "rmse": round(m.rmse, 6),
                "median_ae": round(m.median_ae, 6),
                "p90_ae": round(m.p90_ae, 6),
                **(
                    {"unseen_group_rate_pct": round(m.unseen_rate, 6)}
                    if m.unseen_rate is not None
                    else {}
                ),
            }
            for m in metrics
        ],
    }


def write_manifest(payload: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")
    return path
