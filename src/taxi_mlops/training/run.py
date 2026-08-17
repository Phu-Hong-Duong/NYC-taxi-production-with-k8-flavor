"""One invocation, three contenders, one evaluator, one table.

The shape matters more than the code: every number printed at the end came from
`evaluate.evaluate` on a held-out split, including both baselines. That is what
makes the comparison a comparison (gotcha #15) — and it is why a bug in the
evaluator shows up as all three numbers moving, not as a discovery.

M2-S3 owns the promotion gate and `make train`. This module deliberately does not
promote, does not set an alias, and does not touch the registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..data.config import DataConfig, load_config, load_yaml
from ..features import quote_time
from . import baselines
from . import model as model_mod
from .datasets import Split, load_split
from .evaluate import Metrics, evaluate, results_table


@dataclass
class Contender:
    """A predictor plus its MLflow run metadata. Baselines are contenders too."""

    name: str
    params: dict[str, Any]
    predict: Any
    metrics: list[Metrics]
    trained: model_mod.TrainedModel | None = None


def load_train_config(path: str = "configs/train.yaml") -> dict[str, Any]:
    return load_yaml(path)


def _splits(
    data_cfg: DataConfig, train_cfg: dict[str, Any], train_months: tuple[str, ...] | None
) -> dict[str, Split]:
    features_cfg = train_cfg["features"]
    target = train_cfg["target"]
    out: dict[str, Split] = {}
    for split in ("train", "val", "test"):
        months = train_months if (split == "train" and train_months) else None
        out[split] = load_split(split, data_cfg, features_cfg, target, months=months)
        rows = len(out[split])
        print(f"[data] {split:<5} {rows:>12,} rows  months={','.join(out[split].months)}")
    return out


def _score(
    name: str, predict: Any, splits: dict[str, Split], eval_cfg: dict[str, Any]
) -> list[Metrics]:
    """Every contender is scored by the same function on the same two splits."""
    results = []
    for split in ("val", "test"):
        prediction = predict(splits[split].features)
        if isinstance(prediction, baselines.Prediction):
            values, unseen = prediction.values, prediction.unseen_rate
        else:
            values, unseen = prediction, None
        results.append(
            evaluate(name, split, splits[split].y.to_numpy(), values, eval_cfg, unseen_rate=unseen)
        )
    return results


def run(
    *,
    train_months: tuple[str, ...] | None = None,
    ablation: bool = False,
    log_to_mlflow: bool = True,
    train_config: str = "configs/train.yaml",
) -> list[Contender]:
    """Fit and score every contender. Returns them in the order they were scored."""
    train_cfg = load_train_config(train_config)
    data_cfg = load_config(train_config=train_config)
    features_cfg = train_cfg["features"]
    eval_cfg = train_cfg["evaluate"]

    names = quote_time.feature_names(features_cfg)
    categorical = quote_time.categorical_names(features_cfg)
    print(f"[features] set {features_cfg['version']}: {', '.join(names)}")
    print(f"[features] categorical: {', '.join(categorical)}")
    print(f"[features] refused by the registry: {len(quote_time.EXCLUSIONS)} column(s) — "
          "taxi_mlops.features.quote_time.EXCLUSIONS names each with its reason")

    splits = _splits(data_cfg, train_cfg, train_months)
    contenders: list[Contender] = []

    # ---- floor 1: the flattering one, named so it cannot be quoted innocently.
    constant = baselines.ConstantMedian.fit(splits["train"].y)
    print(f"\n[baseline] constant median = {constant.value:.4f} min (train)")
    contenders.append(
        Contender(
            name=constant.name,
            params={"train_median_minutes": round(constant.value, 6)},
            predict=constant.predict,
            metrics=_score(constant.name, constant.predict, splits, eval_cfg),
        )
    )

    # ---- floor 2: the honest one. M2-S3's gate is argued against this number.
    keys = train_cfg["baselines"]["group_keys"]
    group = baselines.GroupMedian.fit(splits["train"].features, splits["train"].y, keys)
    print(
        f"[baseline] group median over ({', '.join(keys)}): {group.groups:,} groups, "
        f"fallback {group.fallback:.4f} min"
    )
    contenders.append(
        Contender(
            name=group.name,
            params={
                "group_keys": ",".join(keys),
                "groups": group.groups,
                "fallback_minutes": round(group.fallback, 6),
            },
            predict=group.predict,
            metrics=_score(group.name, group.predict, splits, eval_cfg),
        )
    )

    # ---- the model.
    print("\n[model] fitting LightGBM v1")
    trained = model_mod.fit(
        splits["train"], splits["val"], train_cfg["model"], categorical
    )
    print(f"[model] best_iteration={trained.best_iteration}")
    contenders.append(
        Contender(
            name=trained.name,
            params={
                **{k: v for k, v in trained.params.items()},
                "target_transform": trained.target_transform,
                "num_boost_round": train_cfg["model"]["num_boost_round"],
                "early_stopping_rounds": train_cfg["model"]["early_stopping_rounds"],
                "best_iteration": trained.best_iteration,
                "features": ",".join(names),
                "feature_set_version": features_cfg["version"],
            },
            predict=trained.predict,
            metrics=_score(trained.name, trained.predict, splits, eval_cfg),
            trained=trained,
        )
    )

    # ---- E-1's ablation: the log1p claim, measured rather than argued.
    if ablation:
        print("\n[model] fitting the log1p ablation (E-1: prove it, do not assume it)")
        ablated = model_mod.fit(
            splits["train"],
            splits["val"],
            train_cfg["model"],
            categorical,
            name=f"{trained.name}-log1p-ablation",
            target_transform="log1p",
        )
        contenders.append(
            Contender(
                name=ablated.name,
                params={
                    **{k: v for k, v in ablated.params.items()},
                    "target_transform": "log1p",
                    "best_iteration": ablated.best_iteration,
                    "features": ",".join(names),
                    "ablation_of": trained.name,
                },
                predict=ablated.predict,
                metrics=_score(ablated.name, ablated.predict, splits, eval_cfg),
                trained=ablated,
            )
        )

    print("\n[evaluate] every number below came from taxi_mlops.training.evaluate")
    print("[evaluate] (gotcha #15: nothing else in this program may report one)\n")
    print(results_table([m for c in contenders for m in c.metrics]))

    floor = next(c for c in contenders if c.name == "baseline-group-median")
    floor_val = next(m for m in floor.metrics if m.split == "val").mae
    model_val = next(m for m in contenders[2].metrics if m.split == "val").mae
    verdict = "BEATS" if model_val < floor_val else "DOES NOT BEAT"
    print(
        f"\n[evaluate] {contenders[2].name} {verdict} the honest floor on val: "
        f"{model_val:.4f} vs {floor_val:.4f} min "
        f"({100 * (floor_val - model_val) / floor_val:+.2f}%)"
    )
    print("[evaluate] the promotion GATE is M2-S3's; this is a report, not a decision.")

    if log_to_mlflow:
        _log(contenders, train_cfg, splits)
    return contenders


def _log(contenders: list[Contender], train_cfg: dict[str, Any], splits: dict[str, Split]) -> None:
    """One MLflow run per contender — baselines included, because a floor nobody
    can look up is a floor that gets rounded in the retelling."""
    import mlflow
    from mlflow.models import infer_signature

    from . import tracking

    tracking.configure(train_cfg["mlflow"])
    experiment = train_cfg["mlflow"]["experiment"]
    mlflow.set_experiment(experiment)
    print(f"[mlflow] experiment: {experiment}")

    example = splits["val"].features.head(5).copy()
    for contender in contenders:
        with mlflow.start_run(run_name=contender.name) as active:
            mlflow.set_tags(
                {
                    "milestone": "M2",
                    "story": "M2-S2",
                    "role": "MLE",
                    "feature_set": train_cfg["features"]["version"],
                    "metric_source": "taxi_mlops.training.evaluate",
                    "train_months": ",".join(splits["train"].months),
                    "val_month": ",".join(splits["val"].months),
                    "test_month": ",".join(splits["test"].months),
                }
            )
            mlflow.log_params(contender.params)
            for metrics in contender.metrics:
                mlflow.log_metrics(metrics.as_mlflow_metrics())

            if contender.trained is not None and contender.trained.target_transform == "none":
                predictions = contender.trained.predict(example)
                signature = infer_signature(example, predictions)
                mlflow.lightgbm.log_model(
                    contender.trained.booster,
                    name="model",
                    signature=signature,
                    input_example=example,
                )
                print(f"[mlflow] {contender.name}: model logged with signature + input example")
            elif contender.trained is not None:
                # A log-space booster predicts logs; serving it correctly needs a
                # pyfunc wrapper. Shipping one for an ABLATION would put a wrapper
                # nobody uses in the registry, so the ablation logs numbers only —
                # and says so, rather than logging a model that lies about its units.
                mlflow.set_tag("model_logged", "no — log-space booster, ablation only")
                print(f"[mlflow] {contender.name}: metrics only (log-space; see run tag)")
            print(f"[mlflow] {contender.name}: run {active.info.run_id}")
