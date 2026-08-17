"""Score the REGISTERED champion on the held-out splits and publish the rows.

`make train` fits a challenger and asks the gate about it. This is the other
question, and M2-S4 is where it first needs answering: *what does the model we
actually promoted predict, row by row?*

Why the champion and not a fresh fit. A re-fit reproduces the champion's numbers
to four decimals (M2-S3 watched it happen) but it is a different MLflow run, and
predictions labelled with a version the registry has never heard of are evidence
about a model nobody deployed. So this path resolves
`models:/<name>@<alias>`, reads the version and its run back, and stamps both on
every row it writes. It also mints nothing: no run is created, no alias moves, no
version appears — running it twice changes the registry not at all.

Nothing here computes a metric. `taxi_mlops.training.evaluate` does that, exactly
as it does for `make train` (gotcha #15), and the numbers it returns here are
checked out loud against the champion's own registry tags: the same model on the
same holdout must reproduce the number the gate was argued with. A disagreement
is not a new result, it is a bug in this file.

The honest floor is re-fitted from train, because the predictions file carries
its quote too. That costs the six train months of I/O and is the reason this
command takes minutes rather than seconds — and it is what lets the error memo
ask where the booster earns its keep over a `GROUP BY`, per segment, instead of
only in the aggregate the gate saw.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..data.config import DataConfig, load_config
from ..features import quote_time
from . import baselines
from . import model as model_mod
from . import predictions as predictions_mod
from .datasets import Split, load_split
from .evaluate import Metrics, evaluate, results_table
from .run import load_train_config


class ChampionError(RuntimeError):
    """The registered champion cannot be scored honestly. Names the reason."""


@dataclass(frozen=True)
class Champion:
    """The registry's answer to 'what is serving?', plus the booster itself."""

    model_name: str
    alias: str
    version: str
    run_id: str
    uri: str
    target_transform: str
    feature_names: list[str]
    trees: int
    tags: dict[str, str]
    booster: Any

    def as_manifest(self) -> dict[str, Any]:
        return {
            "name": self.model_name,
            "alias": self.alias,
            "version": self.version,
            "run_id": self.run_id,
            "uri": self.uri,
            "target_transform": self.target_transform,
            "trees": self.trees,
            "gate_tags": {k: v for k, v in sorted(self.tags.items()) if k.startswith("gate_")},
        }


def load_champion(train_cfg: dict[str, Any]) -> Champion:
    """Resolve the alias, read the version back, and load its booster.

    Reads the alias through `get_model_version_by_alias`, never off
    `search_model_versions` — on MLflow server 3.15.1 that call returns versions
    whose `aliases` field is EMPTY (M2-S3's finding), so a champion resolved that
    way would be resolved by guessing.
    """
    import mlflow

    from . import tracking

    tracking.configure(train_cfg["mlflow"])
    cfg = train_cfg["registry"]
    model_name, alias = cfg["model_name"], cfg["champion_alias"]
    client = mlflow.MlflowClient()
    try:
        version = client.get_model_version_by_alias(model_name, alias)
    except Exception as exc:  # noqa: BLE001 — an unset alias is a first-class refusal
        raise ChampionError(
            f"models:/{model_name}@{alias} does not resolve: {exc}. Run `make train` — "
            "the alias is set by the promotion gate and by nothing else."
        ) from exc

    run = client.get_run(version.run_id)
    transform = run.data.params.get("target_transform", "none")
    if transform != "none":
        # The same refusal M2-S2 made when it declined to log the log1p ablation
        # as a model: a log-space booster's raw output is not minutes, and a
        # predictions file whose units depend on a run parameter is a trap.
        raise ChampionError(
            f"champion version {version.version} was fitted with target_transform="
            f"{transform!r}. Scoring it needs the pyfunc wrapper that inverts the "
            "transform; this path predicts in minutes and will not guess."
        )

    uri = f"models:/{model_name}@{alias}"
    # F-009, found here by de-risking the API before spending a training run on it:
    # `mlflow.lightgbm.load_model("models:/<name>@<alias>")` RAISES
    # `No such artifact: 'MLmodel'` against server+client 3.15.1, while
    # `get_model_info` on the SAME uri resolves happily. The cause is MLflow 3's
    # Logged Models: the artifact lives at `.../models/m-<id>/artifacts`, but the
    # registry version's `source` is `runs:/<run>/model`, and the registry-uri
    # load path looks under the RUN's artifact prefix, finds nothing, and hands
    # back an empty directory. So the alias is resolved to the logged-model uri
    # first and that is what is loaded. The alias stays the entry point — this is
    # a resolution step, not a second address for the champion.
    resolved = mlflow.models.get_model_info(uri).model_uri
    print(f"[score] alias {uri} resolves to {resolved} (F-009: load it, not the alias)")
    booster = mlflow.lightgbm.load_model(resolved)
    return Champion(
        model_name=model_name,
        alias=alias,
        version=str(version.version),
        run_id=str(version.run_id),
        uri=uri,
        target_transform=transform,
        feature_names=list(booster.feature_name()),
        trees=int(booster.current_iteration()),
        tags=dict(version.tags or {}),
        booster=booster,
    )


def _as_trained(champion: Champion) -> model_mod.TrainedModel:
    """Predict through the SAME wrapper training used — clipping included.

    `TrainedModel.predict` clips at zero because a rider cannot be quoted a
    negative duration. Re-implementing that here would be a second prediction
    path, and the first place it would diverge is the tail this memo is about.
    """
    return model_mod.TrainedModel(
        booster=champion.booster,
        name=f"{champion.model_name}@{champion.alias}",
        target_transform=champion.target_transform,
        feature_names=champion.feature_names,
        categorical=[],
        best_iteration=champion.trees,
        params={},
    )


def _check_against_registry(champion: Champion, metrics: list[Metrics], holdout: str) -> None:
    """The champion's own tags say what it was promoted on. Check we reproduce it.

    This is the strongest thing this command does. The gate wrote
    `gate_challenger_mae` onto the version at promotion time; if scoring that
    version on that split now returns a different number, then either the model
    that was promoted is not the model that is loading, or this path builds
    features differently from the one that fitted it. Both are defects, and
    neither has any other symptom.
    """
    claimed = champion.tags.get("gate_challenger_mae")
    if claimed is None:
        print(
            "[score] NOTE: the champion version carries no `gate_challenger_mae` tag, "
            "so there is nothing to check this run against."
        )
        return
    measured = next(m for m in metrics if m.split == holdout).mae
    print(
        f"[score] registry says version {champion.version} was promoted at KPI-09 "
        f"{claimed} on {holdout}; scoring it now measures {measured:.4f}"
    )
    if f"{measured:.4f}" != claimed:
        raise ChampionError(
            f"the champion re-scores at {measured:.4f} on {holdout}, but its own "
            f"registry tag says it was promoted at {claimed}. The rows this command "
            "would publish describe a different model from the one that passed the "
            "gate. Refusing to write them."
        )
    print("[score] MATCH — the published rows describe the model the gate promoted.")


def score(
    *,
    train_config: str = "configs/train.yaml",
    write: bool = True,
) -> dict[str, Any]:
    """Load the champion, score val + test through `evaluate`, publish the rows."""
    train_cfg = load_train_config(train_config)
    data_cfg: DataConfig = load_config(train_config=train_config)
    features_cfg = train_cfg["features"]
    eval_cfg = train_cfg["evaluate"]
    target = train_cfg["target"]

    champion = load_champion(train_cfg)
    print(f"[score] champion   : {champion.uri} -> version {champion.version}")
    print(f"[score] run        : {champion.run_id}  ({champion.trees} trees)")

    configured = quote_time.feature_names(features_cfg)
    if champion.feature_names != configured:
        raise ChampionError(
            f"the champion eats {champion.feature_names} but configs/train.yaml "
            f"describes {configured}. Scoring it would silently reorder columns; a "
            "feature set that has moved needs a new champion, not a new column order."
        )
    print(f"[score] features   : {', '.join(champion.feature_names)} (matches the config)")

    # The floor first, because fitting it is what needs the six train months in
    # memory — and they are released before the booster starts predicting.
    train = load_split("train", data_cfg, features_cfg, target)
    print(f"[data] train {len(train):>12,} rows  months={','.join(train.months)}")
    keys = train_cfg["baselines"]["group_keys"]
    floor = baselines.GroupMedian.fit(train.features, train.y, keys)
    print(
        f"[baseline] group median over ({', '.join(keys)}): {floor.groups:,} groups, "
        f"fallback {floor.fallback:.4f} min"
    )
    train_months = train.months
    del train

    model = _as_trained(champion)
    splits: dict[str, Split] = {}
    metrics: list[Metrics] = []
    frames: dict[str, Any] = {}
    for split in ("val", "test"):
        splits[split] = load_split(split, data_cfg, features_cfg, target)
        rows = len(splits[split])
        print(f"[data] {split:<5} {rows:>12,} rows  months={','.join(splits[split].months)}")

        y = splits[split].y.to_numpy()
        model_pred = model.predict(splits[split].features)
        floor_pred = floor.predict(splits[split].features)
        metrics.append(evaluate(model.name, split, y, model_pred, eval_cfg))
        metrics.append(
            evaluate(
                floor.name,
                split,
                y,
                floor_pred.values,
                eval_cfg,
                unseen_rate=floor_pred.unseen_rate,
            )
        )
        frames[split] = predictions_mod.build_frame(
            split=split,
            month=splits[split].months[0],
            features=splits[split].features,
            actual=splits[split].y,
            predicted=model_pred,
            floor_predicted=floor_pred.values,
            floor_unseen=floor_pred.unseen_mask,
            model_name=champion.model_name,
            model_version=champion.version,
        )

    print("\n[evaluate] every number below came from taxi_mlops.training.evaluate\n")
    print(results_table(metrics))
    _check_against_registry(champion, [m for m in metrics if m.contender == model.name],
                            train_cfg["gate"]["holdout_split"])

    payload = predictions_mod.manifest(
        model=champion.as_manifest(),
        floor={
            "name": floor.name,
            "group_keys": list(keys),
            "groups": floor.groups,
            "fallback_minutes": round(floor.fallback, 6),
            "train_months": list(train_months),
        },
        tolerance_minutes=float(eval_cfg["tolerance_minutes"]),
        metrics=metrics,
    )

    written = []
    if write:
        for split, frame in frames.items():
            path = data_cfg.predictions_path(splits[split].months[0])
            predictions_mod.write(frame, path, data_cfg)
            print(f"[score] wrote {len(frame):>12,} rows -> {path.relative_to(_root())}")
            written.append(path)
        manifest = predictions_mod.write_manifest(
            payload, data_cfg.predictions_manifest_path()
        )
        print(f"[score] wrote provenance -> {manifest.relative_to(_root())}")
        print("[score] next: `make duckdb` reconciles these rows, then `make marts`.")
    else:
        print("[score] --no-write: nothing published (the numbers above still stand).")

    return {"champion": champion, "metrics": metrics, "manifest": payload, "written": written}


def _root():
    from ..data.config import repo_root

    return repo_root()
