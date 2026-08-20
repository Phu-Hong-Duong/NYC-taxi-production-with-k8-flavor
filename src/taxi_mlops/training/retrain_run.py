"""`retrain` as a command: build the challenger, fit it, let the gate decide, record.

The split from `retrain.py` is deliberate and is the same split `gate.py` and
`registry.py` have: **`retrain.py` DECIDES what to fit (pure, no cluster, no
registry write) and this module ACTS**. Everything here reads a registry, reads
parquet, writes a config, spends ~an hour of CPU and writes a record; nothing here
chooses a hyperparameter.

Three properties, each of which had to be argued rather than assumed:

* **It never promotes.** `run(promote=False)` is passed unconditionally and there
  is no parameter that changes it. A retrain is the one job in this program that
  runs unattended on a schedule, and an unattended job that can move `@champion`
  is a job that can put an unreviewed model in front of riders at 04:00. A
  PROMOTE verdict is recorded and the alias stays where it is — "promotion
  deferred" is a state the registry expresses honestly; half a transition
  (M3-S5's chain: promote -> predictions -> duckdb -> marts -> boards -> serve ->
  parity) is not.

* **The row count is MEASURED before the rescale, not typed.** F-020's transfer
  divides by a row count; a constant here would be a number that silently stops
  being true the first time a month is re-ingested. It comes from the parquet
  footers of the configured train months — exact, and cheaper than reading a row.

* **Whether the fit was ENDED BY EARLY STOPPING or by the cap is reported as a
  first-class field.** That is the second half of F-020: the champion's own refit
  ended at 791 of 800 and a results table cannot tell that apart from convergence.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from ..data.config import load_config, load_yaml, repo_root
from . import retrain as retrain_mod
from .run import load_train_config, run

DEFAULT_RUN_DIR = "automation/runs/m7-retrain"
DEFAULT_EXPERIMENT = "m7-retrain"
#: The challenger's MLflow run name. It says what it IS — the champion's
#: configuration re-derived at full scale — so that a reader of the experiment
#: list does not have to open the record to tell it from `auto-lgbm-v2`.
CHALLENGER_NAME = "retrain-rescaled-v2"


def measure_train_rows(train_config: str = "configs/train.yaml") -> int:
    """Row count of the configured train months, from the parquet footers.

    Metadata only: `ParquetFile.metadata.num_rows` reads the footer, so six months
    of 44M rows answer in milliseconds and the number is exact rather than
    estimated. The alternative — trusting the ingest reports — would be a second
    source for a number `load_frame` will produce again in ten minutes.
    """
    data_cfg = load_config(train_config=train_config)
    total = 0
    for month in data_cfg.splits.train:
        path = data_cfg.processed_path(month)
        if not path.exists():
            raise retrain_mod.RetrainError(
                f"{path} is missing — a retrain reads what the contract blessed, so "
                "`make data` owes it this month before F-020's divisor can be measured"
            )
        total += pq.ParquetFile(path).metadata.num_rows
    return total


def retrain(
    *,
    run_dir: str = DEFAULT_RUN_DIR,
    train_config: str = "configs/train.yaml",
    experiment: str = DEFAULT_EXPERIMENT,
    story: str = "M7-S4",
    plan_only: bool = False,
    train_months: tuple[str, ...] | None = None,
    log_to_mlflow: bool = True,
) -> dict[str, Any]:
    """Build the rescaled challenger, fit it, submit it to the gate, record everything.

    `train_months` is the SAMPLED path and nothing else: it makes the run
    gate-disqualified by F-008 (`taxi_mlops.training.run` refuses to judge it),
    which is exactly what the scheduled-run proof wants — the schedule is what is
    being proven, and a cheap proof must not be able to mint a verdict.
    """
    started = time.monotonic()
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    out = repo_root() / run_dir
    out.mkdir(parents=True, exist_ok=True)

    raw = load_yaml(train_config)
    train_cfg = load_train_config(train_config)
    sampled = train_months is not None

    # The divisor. On a sampled run it is the sample's own row count, because the
    # knobs are being rescaled to the fit that is about to happen and not to a
    # fit that is not.
    target_rows = (
        _rows_of(train_months, train_config) if sampled else measure_train_rows(train_config)
    )
    provenance = retrain_mod.resolve_champion_configuration(train_cfg)
    if provenance.feature_set != train_cfg["features"]["version"]:
        raise retrain_mod.RetrainError(
            f"the champion eats feature set {provenance.feature_set!r} and "
            f"configs/train.yaml: features.version says "
            f"{train_cfg['features']['version']!r}. A retrain of the champion's "
            "configuration on a different feature set is a different experiment; the "
            "config line moves as part of a promotion or not at all (M3-S3's law)."
        )

    name = CHALLENGER_NAME + ("-sampled" if sampled else "")
    cfg, record = retrain_mod.build_config(raw, provenance, target_rows=target_rows, name=name)
    cfg_path = retrain_mod.write_config(cfg, out / f"retrain_config_{stamp}.yaml")
    retrain_mod.print_plan(record)
    print(f"[retrain] resolved config -> {cfg_path.relative_to(repo_root())}")

    record.update({
        "story": story,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "resolved_config": str(cfg_path.relative_to(repo_root())),
        "experiment": experiment,
        "sampled": sampled,
        "train_months": list(train_months) if train_months else list(raw["data"]["train_months"]),
        "provenance": asdict(provenance),
    })

    if plan_only:
        record["verdict"] = None
        record["note"] = ("--plan-only: nothing was fitted, no run was minted, no "
                          "verdict was issued")
        _write(out / f"retrain_plan_{stamp}.json", record)
        return record

    result = run(
        train_months=train_months,
        promote=False,          # unconditional; see this module's docstring
        judge=not sampled,      # F-008: a sampled run is not entitled to a verdict
        log_to_mlflow=log_to_mlflow,
        experiment=experiment,
        story=story,
        train_config=str(cfg_path),
    )
    seconds = time.monotonic() - started

    trained = result.challenger.trained
    cap = int(cfg["model"]["num_boost_round"])
    best = int(trained.best_iteration) if trained is not None else 0
    ended_by = "early_stopping" if best < cap else "round_cap"
    record["fit"] = {
        "best_iteration": best,
        "round_cap": cap,
        "ended_by": ended_by,
        "seconds": round(seconds, 1),
        "run_id": result.challenger.run_id,
        "truncated": ended_by == "round_cap",
    }
    print(f"\n[retrain] the fit ended by {ended_by.upper()}: best_iteration {best} of a "
          f"{cap}-round cap, {seconds:,.1f}s")
    if ended_by == "round_cap":
        print("[retrain] TRUNCATED — the cap ended this fit, so its number is a floor for "
              "this configuration and carries F-015's caveat. That is the fact the "
              "re-derived budget exists to make visible, not one it promises to avoid.")

    decision = result.decision
    record["verdict"] = None if decision is None else {
        "verdict": decision.verdict,
        "passed": decision.passed,
        "challenger_mae": decision.challenger_mae,
        "challenger_within_rate": decision.challenger_within,
        "floor": cfg["gate"]["floor"],
        "floor_mae": decision.floor_mae,
        "floor_within_rate": decision.floor_within,
        "observed_pct_vs_floor": decision.observed_pct,
        "required_pct_vs_floor": decision.required_pct,
        "incumbent_version": getattr(decision.incumbent, "version", None),
        "incumbent_mae": getattr(decision.incumbent, "mae", None),
        "incumbent_within_rate": getattr(decision.incumbent, "within_tolerance_rate", None),
        "reasons": [
            {"passed": c.passed, "text": c.text} for c in decision.checks
        ] if hasattr(decision, "checks") else None,
    }
    record["metrics"] = [
        {"contender": m.contender, "split": m.split, "n": m.n, "mae": m.mae,
         "within_tolerance_rate": m.within_tolerance_rate}
        for c in result.contenders for m in c.metrics
    ]
    record["metric_source"] = "taxi_mlops.training.evaluate"
    record["promoted"] = False
    record["champion_alias_version"] = provenance.champion_version

    _write(out / f"retrain_{stamp}.json", record)
    _write(out / "latest.json", record)
    return record


def _rows_of(months: tuple[str, ...], train_config: str) -> int:
    data_cfg = load_config(train_config=train_config)
    return sum(pq.ParquetFile(data_cfg.processed_path(m)).metadata.num_rows for m in months)


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(f"[retrain] record -> {path.relative_to(repo_root())}")
