"""One invocation, three contenders, one evaluator, one table.

The shape matters more than the code: every number printed at the end came from
`evaluate.evaluate` on a held-out split, including both baselines. That is what
makes the comparison a comparison (gotcha #15) — and it is why a bug in the
evaluator shows up as all three numbers moving, not as a discovery.

M2-S3 added the second half: the same invocation now submits the model to the
promotion gate (`gate.py`) and, only on a verdict that passed, promotes it
(`registry.py`). The decision is printed with both numbers either way, and a
refusal leaves the registry exactly as it found it.

M3-S1 added the third: the run resolves the SERVING champion before it judges
anything and hands it to the gate (F-011). That is the impure half of the
comparison — a registry read — so it lives here and not in `gate.py`, and it
travels as `gate.Incumbent` with its own provenance string attached.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..data.config import DataConfig, load_config, load_yaml
from ..features import quote_time, sets
from . import baselines, gate
from . import model as model_mod
from . import registry as registry_mod
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
    run_id: str | None = None
    model_logged: bool = False

    def metric(self, split: str) -> Metrics:
        return next(m for m in self.metrics if m.split == split)


@dataclass
class RunResult:
    """What one `make train` produced: the contenders, the verdict, the promotion.

    `decision` is None for exactly one kind of run: a sampled one asked for with
    --no-gate, which prints its table and is issued NO verdict (F-008). Nothing
    else may leave it unset — a run that fitted a full-data challenger and did not
    face the gate would be a result with no bar attached to it.
    """

    contenders: list[Contender]
    challenger: Contender
    decision: gate.Decision | None
    promotion: registry_mod.Promotion | None = None


def load_train_config(path: str = "configs/train.yaml") -> dict[str, Any]:
    """THE loader. Everything that reads the training config comes through here.

    It resolves `features:` against `configs/features.yaml` (M3-S3, F-013) so
    every consumer — this module, `score.py`, `verify-m2`, the red teams — sees
    the same expanded column list from the same one home. Resolving at the single
    loader rather than at each call site is the point: a caller that forgot would
    get a KeyError, but a caller that resolved differently would get a model.
    """
    cfg = load_yaml(path)
    cfg["features"] = sets.resolve(cfg["features"])
    return cfg


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
    promote: bool = True,
    hobble: str | None = None,
    judge: bool = True,
    experiment: str | None = None,
    story: str | None = None,
    train_config: str = "configs/train.yaml",
) -> RunResult:
    """Fit, score, gate, and (only on a pass) promote. One command, one verdict."""
    train_cfg = load_train_config(train_config)
    data_cfg = load_config(train_config=train_config)
    features_cfg = train_cfg["features"]
    eval_cfg = train_cfg["evaluate"]

    # F-008, BEFORE a row is read: a sampled run gets no verdict, and finding that
    # out should cost seconds rather than a training run. `--no-gate` is the
    # sample-first smoke path and is legal ONLY here, on a run that has already
    # disqualified itself — so it can never be the flag that skips a gate a
    # promotable run would have faced.
    configured_months = list(train_cfg["data"]["train_months"])
    sampled = train_months is not None and list(train_months) != configured_months
    if not judge:
        if not sampled:
            raise gate.GateError(
                "--no-gate is only legal for a SAMPLED run (--train-months). On the "
                "configured months the gate is the point of the command: a full-data "
                "fit that skipped its verdict is a result with no bar attached."
            )
        print(
            "[gate] NO VERDICT will be issued: --no-gate on a sampled run (F-008). "
            "Nothing here can promote."
        )
    elif train_months is not None:
        gate.assert_full_train_months(train_months, configured_months)

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

    # ---- floor 3 (M3-S1, F-010): the same lookup with one more backoff level.
    # A NEW name and not an edit to floor 2, per configs/train.yaml: baselines —
    # M2's verdicts were argued against floor 2 and must stay reproducible.
    od_keys = train_cfg["baselines"]["od_fallback_keys"]
    backoff = baselines.GroupMedianODFallback.fit(
        splits["train"].features, splits["train"].y, keys, od_keys
    )
    print(
        f"[baseline] group median with ({', '.join(od_keys)}) backoff: "
        f"{backoff.groups:,} groups + {backoff.fallback_groups:,} backoff cells, "
        f"fallback {backoff.fallback:.4f} min"
    )
    contenders.append(
        Contender(
            name=backoff.name,
            params={
                "group_keys": ",".join(keys),
                "od_fallback_keys": ",".join(od_keys),
                "groups": backoff.groups,
                "fallback_groups": backoff.fallback_groups,
                "fallback_minutes": round(backoff.fallback, 6),
            },
            predict=backoff.predict,
            metrics=_score(backoff.name, backoff.predict, splits, eval_cfg),
        )
    )

    # ---- the model. The challenger is this contender whether or not it is
    # hobbled: the red team submits a broken model through THIS path, not a
    # shortcut past it. It is found BY NAME below and never by list position —
    # M3-S1 added a third floor in front of it, and an index would have made that
    # addition silently promote a baseline.
    challenger_name = train_cfg["model"]["name"]
    if hobble:
        challenger_name = f"{challenger_name}-hobbled-{hobble}"
        print(f"\n[model] RED TEAM: fitting a deliberately hobbled challenger ({hobble})")
        print("[model] It goes through the same fit, the same evaluator and the same gate.")
    else:
        print("\n[model] fitting LightGBM v1")
    trained = model_mod.fit(
        splits["train"],
        splits["val"],
        train_cfg["model"],
        categorical,
        name=challenger_name,
        hobble=hobble,
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
                **({"hobble": hobble} if hobble else {}),
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

    challenger = next(c for c in contenders if c.name == challenger_name)
    floor = next(c for c in contenders if c.name == train_cfg["gate"]["floor"])
    floor_val, model_val = floor.metric("val").mae, challenger.metric("val").mae
    verdict = "BEATS" if model_val < floor_val else "DOES NOT BEAT"
    print(
        f"\n[evaluate] {challenger.name} {verdict} the honest floor on val: "
        f"{model_val:.4f} vs {floor_val:.4f} min "
        f"({100 * (floor_val - model_val) / floor_val:+.2f}%)"
    )
    print("[evaluate] val is the REPORT. The gate below judges on test, and only test.")

    # ---- the gate. Both numbers, either way.
    gate_cfg = train_cfg["gate"]
    holdout = gate_cfg["holdout_split"]
    decision = None
    if judge:
        incumbent = _resolve_incumbent(train_cfg, holdout) if log_to_mlflow else None
        if incumbent is None and log_to_mlflow:
            print("[gate] incumbent : the champion alias is unset — nothing is serving yet")
        elif incumbent is None:
            print(
                "[gate] incumbent : NOT CONSULTED — --no-mlflow leaves no registry to "
                "read. This verdict cannot promote (F-011)."
            )
        decision = gate.decide(
            challenger.metric(holdout), floor.metric(holdout), gate_cfg, incumbent=incumbent
        )
        flattering = next(c for c in contenders if c.name == "baseline-constant-median").metric(
            holdout
        )
        print("\n" + "=" * 78)
        print("[gate] PROMOTION GATE — configs/train.yaml: gate (loosening it is a PO fork)")
        print(gate.verdict_lines(decision))
        print(
            f"[gate] context   : the FLATTERING floor (baseline-constant-median) is "
            f"{flattering.mae:.4f} min on {holdout} and is NOT the bar — against it "
            f"this would read as "
            f"{gate.improvement_pct(decision.challenger_mae, flattering.mae):+.2f}%."
        )
        print("=" * 78)

    if log_to_mlflow:
        _log(
            contenders,
            train_cfg,
            splits,
            decision,
            challenger,
            experiment=experiment,
            story=story,
            sampled=sampled,
        )

    promotion = None
    if decision is None:
        print(
            "\n[promote] SKIPPED — no verdict was issued (sampled run, F-008). A run "
            "the gate declined to judge cannot promote, with or without --no-promote."
        )
    elif not decision.passed:
        print("\n[promote] SKIPPED — the gate refused. Nothing registered, no alias moved.")
    elif not promote:
        print("\n[promote] SKIPPED — --no-promote. The verdict above stands unrecorded.")
    elif not log_to_mlflow:
        print("\n[promote] SKIPPED — --no-mlflow leaves no run to register.")
    else:
        promotion = _promote(challenger, train_cfg, decision)

    return RunResult(
        contenders=contenders, challenger=challenger, decision=decision, promotion=promotion
    )


def _resolve_incumbent(train_cfg: dict[str, Any], holdout: str) -> gate.Incumbent | None:
    """Read what is SERVING off the registry, so the gate can be told about it.

    The impure half of F-011's comparison, kept out of `gate.py` on purpose. Two
    details are load-bearing:

    - The alias is read through `get_model_version_by_alias`, never off
      `search_model_versions` — that call returns versions whose `aliases` field
      is EMPTY on server 3.15.1 (M2-S3), so an incumbent found that way is found
      by guessing.
    - KPI-10 comes from the version's tags when they carry it, and from the
      version's RUN when they do not. Versions promoted before M3-S1 were tagged
      with the challenger's KPI-09 only, and champion v1 is one of them; its
      KPI-10 has been on its run as `gate_challenger_within_rate` since M2-S3.
      Backfilling the tag would be a registry write outside `registry.py`, which
      is the one rule this module does not get to break — so the number is read
      where it already exists and its provenance is printed.
    """
    import mlflow

    from . import tracking

    tracking.configure(train_cfg["mlflow"])
    cfg = train_cfg["registry"]
    model_name, alias = cfg["model_name"], cfg["champion_alias"]
    client = mlflow.MlflowClient()
    try:
        version = client.get_model_version_by_alias(model_name, alias)
    except Exception:  # noqa: BLE001 — an unset alias is the first-promotion path
        return None

    tags = dict(version.tags or {})
    mae = tags.get("gate_challenger_mae")
    if mae is None:
        raise gate.GateError(
            f"models:/{model_name}@{alias} resolves to version {version.version}, but "
            "that version carries no `gate_challenger_mae` tag, so there is no number "
            "to compare a challenger against. A champion nobody can quote cannot be "
            "defended (F-011) — re-promote it through the gate or investigate how it "
            "was aliased."
        )
    tagged_split = tags.get("gate_holdout_split", holdout)
    within, source = tags.get("gate_challenger_within_rate"), "version tags"
    if within is None:
        run = client.get_run(version.run_id)
        within = run.data.metrics.get("gate_challenger_within_rate")
        source = f"version tags + run {version.run_id[:12]}…"
    if within is None:
        raise gate.GateError(
            f"version {version.version} records KPI-09 but no KPI-10 anywhere — "
            "neither on the version nor on its run. The gate refuses to compare half "
            "a champion: a mean can improve while more riders are quoted wrongly."
        )
    return gate.Incumbent(
        version=str(version.version),
        mae=float(mae),
        within_tolerance_rate=float(within),
        split=str(tagged_split),
        source=source,
    )


def _promote(
    challenger: Contender, train_cfg: dict[str, Any], decision: gate.Decision
) -> registry_mod.Promotion:
    """Register the winner and move the alias. Refuses an unservable winner."""
    import mlflow

    cfg = train_cfg["registry"]
    if not challenger.model_logged or challenger.run_id is None:
        raise registry_mod.PromotionError(
            f"{challenger.name} passed the gate but no model artifact was logged for "
            "it, so there is nothing to register. A verdict without an artifact is a "
            "claim about a model that does not exist anywhere but this process."
        )
    print()
    promotion = registry_mod.promote(
        mlflow.MlflowClient(),
        model_name=cfg["model_name"],
        alias=cfg["champion_alias"],
        run_id=challenger.run_id,
        # What the gate compared this challenger to. `registry.promote` re-reads
        # the live alias and refuses if it has moved since (F-011).
        incumbent_version=None if decision.incumbent is None else decision.incumbent.version,
        description=(
            "Quote-time ETA for NYC yellow taxi. Versions are contenders promoted "
            "through taxi_mlops.training.gate on the untouched test month."
        ),
        version_tags={
            "gate_verdict": decision.verdict,
            "gate_floor": decision.floor,
            "gate_floor_mae": f"{decision.floor_mae:.4f}",
            "gate_challenger_mae": f"{decision.challenger_mae:.4f}",
            # KPI-10 on the VERSION from M3-S1 on. Champion v1 carries it only on
            # its run, which is why `_resolve_incumbent` still looks there — a
            # successor should not have to.
            "gate_challenger_within_rate": f"{decision.challenger_within:.3f}",
            "gate_floor_within_rate": f"{decision.floor_within:.3f}",
            "gate_observed_pct": f"{decision.observed_pct:.2f}",
            "gate_required_pct": f"{decision.required_pct:.2f}",
            "gate_holdout_split": decision.split,
            "gate_incumbent_version": (
                "none" if decision.incumbent is None else decision.incumbent.version
            ),
            "feature_set": train_cfg["features"]["version"],
            "metric_source": "taxi_mlops.training.evaluate",
        },
    )
    print(promotion.lines())
    print(
        f"[promote] serving resolves models:/{promotion.model_name}@{promotion.alias} "
        f"-> version {promotion.version} (M5's deployment reads exactly this)."
    )
    return promotion


def _log(
    contenders: list[Contender],
    train_cfg: dict[str, Any],
    splits: dict[str, Split],
    decision: gate.Decision | None,
    challenger: Contender,
    *,
    experiment: str | None = None,
    story: str | None = None,
    sampled: bool = False,
) -> None:
    """One MLflow run per contender — baselines included, because a floor nobody
    can look up is a floor that gets rounded in the retelling.

    The gate's verdict is logged ON the challenger's run rather than only printed:
    a number that reaches a slide should be traceable to the run that produced it
    and to the decision that was taken about it, without asking whoever ran it.

    `story` is passed in rather than hardcoded from M3-S1 on: the constant that
    said "M2-S3" was true for one story and would have quietly mislabelled every
    run after it. A run with no story stated says so instead of claiming one.
    """
    import mlflow
    from mlflow.models import infer_signature

    from . import tracking

    tracking.configure(train_cfg["mlflow"])
    experiment = experiment or train_cfg["mlflow"]["experiment"]
    mlflow.set_experiment(experiment)
    print(f"[mlflow] experiment: {experiment}")

    example = splits["val"].features.head(5).copy()
    for contender in contenders:
        with mlflow.start_run(run_name=contender.name) as active:
            mlflow.set_tags(
                {
                    "story": story or "unstated",
                    "milestone": (story or "unstated").split("-")[0],
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

            if sampled:
                # F-008 option (b), carried alongside option (a): even though this
                # run was refused a verdict, its metrics exist and somebody will
                # find them later. They say on their face what they are.
                mlflow.set_tags(
                    {
                        "sample_run": "yes",
                        "gate_verdict": "NONE — sampled run, the gate issued no verdict",
                        "do_not_promote": "yes — trained on a subset of the configured months",
                    }
                )
            if contender is challenger and decision is not None:
                mlflow.log_metrics(decision.as_mlflow())
                mlflow.set_tags(
                    {
                        "gate_verdict": decision.verdict,
                        "gate_floor": decision.floor,
                        "gate_holdout_split": decision.split,
                        "gate_incumbent_version": (
                            "none" if decision.incumbent is None else decision.incumbent.version
                        ),
                    }
                )
            if contender.trained is not None and contender.trained.hobble:
                # Marked in the run's NAME and in its tags, so nobody has to open
                # it to know what it is. The kickoff allows cleanup OR clear
                # marking; marking is the better evidence, because a deleted
                # refusal cannot be checked by anyone who was not watching.
                mlflow.set_tags(
                    {
                        "red_team": story or "M2-S3",
                        "hobbled": contender.trained.hobble,
                        "do_not_promote": "yes — fitted to permuted train labels on purpose",
                    }
                )

            if contender.trained is not None and contender.trained.target_transform == "none":
                predictions = contender.trained.predict(example)
                signature = infer_signature(example, predictions)
                mlflow.lightgbm.log_model(
                    contender.trained.booster,
                    name="model",
                    signature=signature,
                    input_example=example,
                )
                contender.model_logged = True
                print(f"[mlflow] {contender.name}: model logged with signature + input example")
            elif contender.trained is not None:
                # A log-space booster predicts logs; serving it correctly needs a
                # pyfunc wrapper. Shipping one for an ABLATION would put a wrapper
                # nobody uses in the registry, so the ablation logs numbers only —
                # and says so, rather than logging a model that lies about its units.
                mlflow.set_tag("model_logged", "no — log-space booster, ablation only")
                print(f"[mlflow] {contender.name}: metrics only (log-space; see run tag)")
            contender.run_id = active.info.run_id
            print(f"[mlflow] {contender.name}: run {active.info.run_id}")
