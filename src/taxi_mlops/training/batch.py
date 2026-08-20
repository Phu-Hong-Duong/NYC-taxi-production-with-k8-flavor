"""Batch inference on the scoring months — the predictions table, as a product.

`make predictions` (M2-S4) answers *what did the promoted model predict on the
months it was judged on?* — evidence for an argument that has already been had.
This answers a different question, and it is the one a running system asks every
month: *what is the champion saying about data nobody has judged it on?*

The two paths are deliberately not one path with a flag. They differ in the only
way that matters:

* **M2-S4's rows can be checked against the registry.** The champion's own tags
  say it was promoted at KPI-09 3.2403 on the holdout, so re-scoring it must
  return 3.2403 or the write is refused (F-012's sibling). That check is the
  strongest property `make predictions` has.
* **These rows can be checked against nothing.** No tag says what the champion
  scores on 2020-03, because no gate ever asked. The number this command
  produces is a MONITORING series, and the thing that would go wrong silently is
  not "the number disagrees with a tag" — it is that the number is produced by a
  different model, or a differently-built matrix, from the one that serves.

So this path buys the missing check by a detour: **before it writes a single
monitoring row it re-scores the HOLDOUT month and requires the champion's own
promotion tag to come back.** A month with a known answer is scored to prove the
loader, the feature path and the booster, and only then is a month with no known
answer written. That check costs one extra split load; the alternative is a
predictions table whose provenance stops at "a model was loaded".

Three further rules this module exists to hold:

* **The alias is read and never written.** Nothing here mints a run, creates a
  version or moves a pointer — `tests/unit/test_batch_inference.py` asserts it by
  parsing this module's AST, not by grepping its prose (gotchas #53/#68).
* **`month` is a config literal.** It comes from `configs/data.yaml: scoring.months`
  through `DataConfig`, never from the filename it is read out of (M1-S2's law).
* **The error numbers are NOT KPI-09/KPI-10** (gotcha #15 and the id law
  together). Same instrument — `taxi_mlops.training.evaluate`, the one metric
  source — new window, therefore new ids: KPI-14/15/16/17 in
  `docs/kpi_definitions.md`. The manifest this module writes spells those ids in
  its keys so a reader cannot mistake one for the other.

NOT DVC-tracked, on purpose: see `configs/train.yaml: evaluate.scoring_predictions_dir`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pandas as pd

from ..data.config import DataConfig, load_config
from ..features import quote_time
from . import predictions as predictions_mod
from .datasets import load_scoring_month, load_split
from .evaluate import Metrics, evaluate
from .run import load_train_config
from .score import Champion, ChampionError, _as_trained, load_champion


@dataclass(frozen=True)
class MonthResult:
    """One scoring month, scored. The metrics are MONITORING numbers, by window."""

    month: str
    rows: int
    metrics: Metrics
    mean_actual: float
    mean_predicted: float
    mean_signed_error: float
    days: int


def _self_check(
    champion: Champion,
    model: Any,
    data_cfg: DataConfig,
    train_cfg: dict[str, Any],
) -> dict[str, Any]:
    """Re-score the holdout and require the champion's own promotion tag back.

    This is the check the scoring months cannot make for themselves, borrowed
    from a month that can. It fails in exactly the two cases worth failing in:
    the model that loaded is not the model that was promoted, or this path builds
    a feature matrix differently from the path that fitted it. Neither has any
    other symptom — a wrong-but-plausible MAE on a COVID month reads as drift,
    which is precisely what the next story is going to be asked to believe.

    Refusing (rather than warning) is M2-S4's rule: the failure mode is a
    published table nobody can tell is wrong.
    """
    holdout = train_cfg["gate"]["holdout_split"]
    claimed = champion.tags.get("gate_challenger_mae")
    if claimed is None:
        raise ChampionError(
            f"champion version {champion.version} carries no `gate_challenger_mae` tag, "
            "so there is no month with a known answer to prove this path on before it "
            "writes months with no known answer. Refusing to score."
        )
    split = load_split(
        holdout, data_cfg, train_cfg["features"], train_cfg["target"]
    )
    print(
        f"[batch] self-check: re-scoring the {holdout} month "
        f"({len(split):,} rows, {','.join(split.months)})"
    )
    measured = evaluate(
        model.name,
        holdout,
        split.y.to_numpy(),
        model.predict(split.features),
        train_cfg["evaluate"],
    )
    print(
        f"[batch] registry says version {champion.version} was promoted at KPI-09 "
        f"{claimed} on {holdout}; this path measures {measured.mae:.4f}"
    )
    if f"{measured.mae:.4f}" != claimed:
        raise ChampionError(
            f"the champion re-scores at {measured.mae:.4f} on {holdout}, but its own "
            f"registry tag says it was promoted at {claimed}. Either a different model "
            "loaded or this path builds features differently from the one that fitted "
            "it. Refusing to write monitoring rows: an error series produced by an "
            "unproven path reads as drift, and the next story would investigate the "
            "world instead of this bug."
        )
    print("[batch] MATCH — the path that writes these rows reproduces the gate's number.")
    return {
        "split": holdout,
        "months": list(split.months),
        "rows": len(split),
        "registry_kpi_09": claimed,
        "measured_kpi_09": round(measured.mae, 6),
    }


def build_frame(
    *,
    month: str,
    pickup_date: pd.Series,
    features: pd.DataFrame,
    actual: pd.Series,
    predicted: Any,
    model_name: str,
    model_version: str,
) -> pd.DataFrame:
    """Assemble one scoring month's rows. Pure — no I/O, so a test can check it."""
    frame = pd.DataFrame(index=features.index)
    frame["month"] = month
    frame["pickup_date"] = pd.Series(pickup_date).to_numpy()
    for column in ("hour", "dayofweek", "PULocationID", "DOLocationID", "passenger_count"):
        if column not in features.columns:
            raise ValueError(
                f"the feature matrix does not carry {column!r} (it has "
                f"{list(features.columns)}). SCORING_PREDICTION_COLUMNS names the "
                "identity columns every feature set this program has shipped carries; "
                "a set that drops one needs this contract revised, not bypassed."
            )
        frame[column] = features[column].to_numpy()
    frame["actual_minutes"] = pd.Series(actual).to_numpy(dtype="float64")
    frame["predicted_minutes"] = pd.Series(predicted).to_numpy(dtype="float64")
    frame["model_name"] = model_name
    frame["model_version"] = str(model_version)
    return frame[list(predictions_mod.SCORING_PREDICTION_COLUMNS)]


def manifest(
    *,
    model: dict[str, Any],
    self_check: dict[str, Any],
    tolerance_minutes: float,
    results: list[MonthResult],
) -> dict[str, Any]:
    """Provenance beside the rows: which champion, proven how, measuring what.

    TIMESTAMP-FREE, like `data/raw_manifest.json` and `predictions.json`: a diff
    of this file should mean the predictions moved, not that somebody re-ran the
    command on a Tuesday.

    The metric keys SPELL THEIR IDS. `kpi_14_...` and not `mae`, because these
    numbers travel — into a mart, onto a board, into a drift memo — and the id
    law is only worth anything if the id is attached at the source rather than
    remembered at each hop.
    """
    return {
        "generated_by": "taxi_mlops.training.batch",
        "metric_source": "taxi_mlops.training.evaluate",
        "window": "one scoring month (configs/data.yaml: scoring.months)",
        "note": (
            "MONITORING numbers. KPI-09/KPI-10 are the evaluator's ids for a HELD-OUT "
            "split and may not be sourced from this file; these are KPI-14..17, whose "
            "window is a scoring month (docs/kpi_definitions.md)."
        ),
        "columns": list(predictions_mod.SCORING_PREDICTION_COLUMNS),
        "model": model,
        "self_check": self_check,
        "tolerance_minutes": tolerance_minutes,
        "months": [
            {
                "month": r.month,
                "rows": r.rows,
                "days": r.days,
                "kpi_14_mae_minutes": round(r.metrics.mae, 6),
                "kpi_15_within_tolerance_pct": round(r.metrics.within_tolerance_rate, 6),
                "kpi_16_mean_signed_error_minutes": round(r.mean_signed_error, 6),
                "kpi_17_scored_trips": r.rows,
                "mean_actual_minutes": round(r.mean_actual, 6),
                "mean_predicted_minutes": round(r.mean_predicted, 6),
                "rmse": round(r.metrics.rmse, 6),
                "median_ae": round(r.metrics.median_ae, 6),
                "p90_ae": round(r.metrics.p90_ae, 6),
            }
            for r in results
        ],
    }


def results_table(results: list[MonthResult], tolerance: float) -> str:
    """One row per month, ids in the header. Printed, and pasted into the doc."""
    head = (
        f"{'month':<9} {'rows':>12} {'days':>5} {'KPI-14 MAE':>11} "
        f"{'KPI-15 <=' + f'{tolerance:g}m %':>13} {'KPI-16 bias':>12} "
        f"{'mean actual':>12} {'mean quote':>11}"
    )
    lines = [head, "-" * len(head)]
    for r in results:
        lines.append(
            f"{r.month:<9} {r.rows:>12,} {r.days:>5} {r.metrics.mae:>11.4f} "
            f"{r.metrics.within_tolerance_rate:>13.3f} {r.mean_signed_error:>12.4f} "
            f"{r.mean_actual:>12.4f} {r.mean_predicted:>11.4f}"
        )
    return "\n".join(lines)


def score_scoring_months(
    *,
    train_config: str = "configs/train.yaml",
    months: tuple[str, ...] | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Resolve the champion, prove the path on the holdout, score the months.

    `months` narrows to a subset of the CONFIGURED scoring months — it cannot
    introduce one. Anything not in `configs/data.yaml: scoring.months` is refused
    by `scoring_predictions_path` before a row is read, which is the M7-S1
    separation holding one layer downstream.
    """
    train_cfg = load_train_config(train_config)
    data_cfg: DataConfig = load_config(train_config=train_config)
    features_cfg = train_cfg["features"]
    eval_cfg = train_cfg["evaluate"]
    target = train_cfg["target"]
    tolerance = float(eval_cfg["tolerance_minutes"])

    wanted = tuple(months) if months else data_cfg.scoring_months
    if not wanted:
        raise ChampionError(
            "configs/data.yaml names no `scoring.months` — there is nothing to score. "
            "Run `make data-scoring` after adding one (M7-S1)."
        )
    unknown = [m for m in wanted if not data_cfg.is_scoring(m)]
    if unknown:
        raise ChampionError(
            f"{unknown} are not scoring months. Configured: "
            f"{', '.join(data_cfg.scoring_months)}. A split month scored through this "
            "path would be written into the scoring tree and labelled a month no model "
            "was judged on — which is exactly backwards for the months it was."
        )

    champion = load_champion(train_cfg)
    print(f"[batch] champion   : {champion.uri} -> version {champion.version}")
    print(f"[batch] run        : {champion.run_id}  ({champion.trees} trees)")
    print(f"[batch] feature set: {champion.tags.get('feature_set')!r} (registry tag)")

    configured = quote_time.feature_names(features_cfg)
    if champion.feature_names != configured:
        raise ChampionError(
            f"the champion eats {champion.feature_names} but configs/train.yaml "
            f"describes {configured}. Scoring it would silently reorder columns; a "
            "feature set that has moved needs a new champion, not a new column order."
        )
    print(f"[batch] features   : {len(champion.feature_names)} columns (matches the config)")

    model = _as_trained(champion)
    self_check = _self_check(champion, model, data_cfg, train_cfg)

    results: list[MonthResult] = []
    frames: dict[str, pd.DataFrame] = {}
    for month in wanted:
        data = load_scoring_month(month, data_cfg, features_cfg, target)
        print(f"[data] scoring {month} {len(data):>12,} rows")
        y = data.y.to_numpy()
        predicted = model.predict(data.features)
        # The ONE metric source, on a new window. `Metrics.split` carries the
        # month rather than a split name: there is no split, and a value that
        # looked like one would be a lie a reader could act on.
        metrics = evaluate(model.name, f"scoring:{month}", y, predicted, eval_cfg)
        results.append(
            MonthResult(
                month=month,
                rows=len(data),
                metrics=metrics,
                mean_actual=float(y.mean()),
                mean_predicted=float(pd.Series(predicted).mean()),
                mean_signed_error=float((pd.Series(predicted).to_numpy() - y).mean()),
                days=int(pd.Series(data.pickup_date).nunique()),
            )
        )
        frames[month] = build_frame(
            month=month,
            pickup_date=data.pickup_date,
            features=data.features,
            actual=data.y,
            predicted=predicted,
            model_name=champion.model_name,
            model_version=champion.version,
        )
        del data

    print("\n[evaluate] every number below came from taxi_mlops.training.evaluate")
    print("[evaluate] its WINDOW is a scoring month, so its ids are KPI-14..17 —")
    print("[evaluate] KPI-09/KPI-10 belong to a held-out split and are not these.\n")
    print(results_table(results, tolerance))

    payload = manifest(
        model=champion.as_manifest(),
        self_check=self_check,
        tolerance_minutes=tolerance,
        results=results,
    )

    written = []
    if write:
        for month, frame in frames.items():
            path = data_cfg.scoring_predictions_path(month)
            predictions_mod.write(
                frame,
                path,
                data_cfg,
                columns=predictions_mod.SCORING_PREDICTION_COLUMNS,
            )
            print(f"[batch] wrote {len(frame):>12,} rows -> {path.relative_to(_root())}")
            written.append(path)
        manifest_path = data_cfg.scoring_predictions_manifest_path()
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")
        print(f"[batch] wrote provenance -> {manifest_path.relative_to(_root())}")
        print("[batch] next: `make duckdb` reconciles these rows, then `make marts`.")
    else:
        print("[batch] --no-write: nothing published (the numbers above still stand).")

    return {
        "champion": champion,
        "results": results,
        "manifest": payload,
        "written": written,
    }


def _root():
    from ..data.config import repo_root

    return repo_root()
