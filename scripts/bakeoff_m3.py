"""The M3 bake-off: five contenders, one evaluator, one untouched month, five verdicts.

M3 asked one question in a 2x2 — *did the improvement come from FEATURES, from
TUNING, or from both?* — and four cells of that square were measured on VAL by
M2-S2, M3-S3 and M3-S4. None of them has faced the gate. This is where the fifth
row (the floor) joins them and where all five are read on the TEST month, once.

Four properties are deliberate:

1. **NOTHING IS RE-FITTED HERE.** Every model contender is LOADED from the MLflow
   artifact its val number describes — `scripts/automl_refit.py` says so in its
   own docstring ("logged with signature and input example so M3-S5 can hand it
   to the gate without re-fitting anything"). A re-fit would be a different run,
   and the version this bake-off promotes must be the version this bake-off
   measured. The one thing fitted here is the FLOOR, because the gate requires it
   re-derived from the challenger's own training data in the same run (gate.py
   property 2) — a floor quoted from a document drifts away from the data
   silently.

2. **A contender that cannot reproduce its own VAL number is not admitted.**
   Every recorded val MAE is read back off its MLflow run and re-measured here
   through `taxi_mlops.training.evaluate`. If the two disagree, then either the
   artifact loaded is not the artifact that was measured or this file builds
   features differently from the path that fitted it — and neither defect has any
   other symptom. That is `score.py`'s `_check_against_registry` discipline
   (M2-S4) applied to four contenders instead of one, and it is what makes the
   test numbers below evidence rather than output.

3. **The winner is chosen on VAL, and the holdout only pronounces on it** (F-018,
   repaired M4-S1). The ranking happens inside the val pass, before the holdout
   split has been loaded — see `SELECTION_SPLIT`. Until M4-S1 this script ranked
   five contenders by their holdout MAE and then gated the winner on the same
   month, while `gate.verdict_lines` printed that the holdout was "untouched by
   … selection". The M3 record stands as it was measured (val and holdout
   rankings were identical, so the same model wins either way); the method is
   what changed, and it changed before M7's retrain loop inherited it.

4. **All five verdicts are printed, the floor's against itself included.** A gate
   that is only ever shown passing is a gate nobody has watched work. The floor
   as its own challenger is an expected REFUSE at exactly +0.00%, and printing it
   is the cheapest possible demonstration that the bar is a bar.

Promotion is OFF by default and is a separate, explicit invocation
(`--promote-winner`). When it is asked for, this script refuses unless
`configs/train.yaml: features.version` already names the winner's feature set —
M3-S3's law ("the config line moves as part of a promotion or not at all"),
enforced rather than remembered. It is what `score.py` and `verify-m2` both read,
so a champion whose features that line does not describe is a champion the next
`make predictions` refuses to score.

The promotion itself goes through `run._promote` — the same function `make train`
calls, with the same tags and the same `registry.promote` refusals (F-011's
incumbent acknowledgement included). A second promotion path would be a second
set of tags, and the first thing to diverge would be the ones the gate is
reconstructed from.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_OUT = "automation/runs/m3s5/bakeoff.json"

#: How closely a re-scored contender must reproduce its recorded val MAE. Not a
#: tolerance for disagreement — a tolerance for float64 summation over ~6.2M
#: rows. The same booster on the same matrix through the same evaluator is
#: deterministic; anything above this is a different model or a different matrix,
#: which is exactly what this check exists to catch. (Contrast gotcha #42: the
#: INCUMBENT's numbers are compared at 4 decimals because that is the precision
#: they were RECORDED at. These are recorded at full float64, so they may be
#: compared there.)
VAL_REPRODUCTION_TOLERANCE = 1e-9

#: The split the WINNER is ranked on (F-018, filed by REV at the M3 review and
#: repaired at M4-S1). Until M4-S1 this was the holdout: five contenders were
#: read on the test month and the lowest took the alias, while the gate's own
#: transcript printed that the holdout was "untouched by … selection". Two
#: reasons that is wrong and one reason it was cheap to fix:
#:   * the max-of-five on the holdout biases the promoted verdict upward by an
#:     amount nobody measured — the same structure `gate.py` property 1 refuses
#:     one level up when it will not judge on val;
#:   * it decided a real identity — the two v2 arms finished 0.0022 min (0.069%)
#:     apart on test, far below any selection-free resolution;
#:   * and every contender already had a val number in hand, re-verified here to
#:     1e-9, so ranking there costs nothing. `docs/bakeoff_m3.md` §3 records that
#:     the val and holdout rankings were IDENTICAL in M3-S5, which is why the
#:     champion survives the defect in the method that chose it.
#: The holdout keeps exactly one job: pronouncing the verdict on what was chosen
#: elsewhere.
SELECTION_SPLIT = "val"


@dataclass(frozen=True)
class Spec:
    """One row of the bake-off, declared BEFORE any number is measured.

    The 2x2 is a pre-registration: which cells exist, and what each one is a
    measurement OF, are fixed here so that a losing arm cannot quietly become a
    different arm at write-up time (DR-02's anti-forking-paths rule, which
    M3-S3 applied to feature groups and this applies to contenders).
    """

    label: str
    #: "floor" | "artisan" | "automation" — the track that produced it.
    track: str
    #: v1 | v2, and it is CHECKED against the loaded booster's own feature names.
    #:
    #: **`None` means "whatever the loaded model eats" and is legal for the
    #: alias-resolved row ONLY** (F-022, option (a), decided by ARCH at the M4
    #: boundary 2026-08-19; landed here at M7-S4). Pre-registration is the point
    #: for an arm declared before its number existed — it stops a losing arm
    #: quietly becoming a different arm at write-up time — and it is exactly
    #: wrong for a pointer that is DESIGNED to move. The incumbent cell of the
    #: 2x2 has always meant "the champion, whatever it is now"; between M3-S5's
    #: own `--promote-winner` moving the alias to a v2 model and this change, the
    #: alias said v2 while this Spec said v1, and every invocation died at
    #: `_load_booster` with a refusal that was correct one layer too late.
    feature_set: str | None
    #: How the hyperparameters were chosen. The other axis of the 2x2 (DR-03).
    hyperparameters: str
    #: ("floor", floor-name) | ("registry-alias", alias) |
    #: ("mlflow-run", "<experiment>/<run_name>") | ("refit-json", path)
    source: tuple[str, str]
    #: Caveats that travel WITH the row (F-015). Written here, not in the memo,
    #: so a reader of the table cannot miss them.
    caveats: tuple[str, ...] = ()


#: THE FIVE CONTENDERS. Order is the order they are printed in.
CONTENDERS: tuple[Spec, ...] = (
    Spec(
        label="floor",
        track="floor",
        feature_set="v1",
        hyperparameters="none — it is a two-level GROUP BY",
        source=("floor", "configs/train.yaml: gate.floor"),
    ),
    Spec(
        # The label carries no version and no track claim on purpose: this row is
        # the ALIAS, and the alias moves. It read "champion v1" through M3, which
        # was true on the day it was written and false the moment the bake-off's
        # own promotion ran. `automation/runs/m3s5/bakeoff.json` keeps the M3-era
        # label — a record is not rewritten (docs/bakeoff_m3.md §3's precedent).
        label="champion (alias)",
        track="incumbent",
        feature_set=None,  # F-022: read off the loaded model. See Spec.feature_set.
        hyperparameters="whatever the serving champion was fitted with",
        source=("registry-alias", "champion"),
    ),
    Spec(
        label="artisan v2",
        track="artisan",
        feature_set="v2",
        hyperparameters="hand (v1's, held fixed — DR-03)",
        source=("mlflow-run", "m3-artisan/artisan-v2"),
    ),
    Spec(
        label="auto-on-v1",
        track="automation",
        feature_set="v1",
        hyperparameters="tuned (FLAML scout -> Optuna sniper)",
        source=("refit-json", "automation/runs/m3s4/refit-v1.json"),
        caveats=(
            "F-015: the 800-round cap bound this arm MID-DESCENT (val still falling "
            "0.02808 MAE over its last 100 rounds); its study got 9 trials of a "
            "configured 60 and was stopped by the clock, not by convergence",
        ),
    ),
    Spec(
        label="auto-on-v2",
        track="automation",
        feature_set="v2",
        hyperparameters="tuned (FLAML scout -> Optuna sniper)",
        source=("refit-json", "automation/runs/m3s4/refit-v2.json"),
        caveats=(
            "the same 800-round cap bound this arm FLAT (0.00034 MAE over its last "
            "100 rounds, ~82x less slope than auto-on-v1), so F-015's truncation "
            "caveat does NOT attach to this row",
        ),
    ),
)


@dataclass
class Loaded:
    """A resolved contender: the artifact, its provenance, and what it claims."""

    spec: Spec
    name: str
    run_id: str | None
    family: str
    recorded_val_mae: float | None
    best_iteration: int | None
    predictor: Any = None
    metrics: dict[str, Any] = field(default_factory=dict)
    #: The CONCRETE feature set this contender eats. For the four pre-registered
    #: arms it equals `spec.feature_set` and the equality is checked; for the
    #: alias row `spec.feature_set` is None and this is derived from the loaded
    #: booster's own feature names (F-022). Everything downstream reads THIS,
    #: never the Spec — the matrix a contender is scored on must come from the
    #: artifact, not from a declaration the artifact could contradict.
    feature_set: str = ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=DEFAULT_OUT, help="where the bake-off row set lands")
    parser.add_argument(
        "--promote-winner",
        action="store_true",
        help="move the champion alias if (and only if) the winner's verdict PASSED",
    )
    parser.add_argument(
        "--smoke-rows",
        type=int,
        default=0,
        help=(
            "SMOKE ONLY. Truncate every split to N rows to exercise the path in "
            "seconds. A smoke run writes no JSON, promotes nothing, and says so on "
            "every line of its output — it is never a result (playbook sample-first)."
        ),
    )
    args = parser.parse_args()

    # BEFORE anything imports lightgbm or xgboost, including MLflow's loaders.
    # `ensure_openmp` re-execs the process on this host (gotcha #37), which is why
    # this is a .py and not a heredoc: stdin cannot be replayed.
    from taxi_mlops.training.openmp import ensure_openmp

    ensure_openmp()

    from taxi_mlops.data.config import load_config
    from taxi_mlops.training import baselines, gate
    from taxi_mlops.training.evaluate import evaluate, results_table
    from taxi_mlops.training.run import load_train_config

    smoke = args.smoke_rows > 0
    train_cfg = load_train_config()
    data_cfg = load_config()
    eval_cfg = train_cfg["evaluate"]
    gate_cfg = train_cfg["gate"]
    holdout = gate_cfg["holdout_split"]

    _banner(smoke, args)
    _print_declaration(train_cfg)

    loaded = [_resolve(spec, train_cfg) for spec in CONTENDERS]

    # ---- the floor. The one thing fitted here, and it must be: the gate compares
    # against a floor re-derived from the challenger's own training data in this
    # same invocation, never against a number typed into a config.
    floor_name = gate_cfg["floor"]
    print(f"\n[floor] fitting {floor_name} from the configured train months")
    started = time.monotonic()
    train = _load_split("train", data_cfg, train_cfg, ("v1",), args.smoke_rows)["v1"]
    floor = baselines.fit_floor(floor_name, train.features, train.y, train_cfg["baselines"])
    train_months = train.months
    train_rows = len(train)
    del train
    print(
        f"[floor] {floor.name}: {floor.groups:,} groups + "
        f"{getattr(floor, 'fallback_groups', 0):,} backoff cells, fallback "
        f"{floor.fallback:.4f} min · fitted on {train_rows:,} rows in "
        f"{time.monotonic() - started:.1f}s"
    )
    loaded[0].predictor = floor.predict
    loaded[0].name = floor.name

    # ---- val: the admission check AND the ranking (F-018). Nothing is JUDGED on
    # val (gate.py property 1); it is read to prove that the artifact loaded is
    # the artifact that was measured, and a contender that fails is not admitted
    # to the test table. Since M4-S1 it is also where the winner is CHOSEN, and
    # the choice is made inside this loop — before the holdout split has been
    # loaded, let alone scored. That ordering is the fix: not "we rank on val by
    # convention" but "no holdout number exists yet to rank on".
    # From the RESOLVED contenders and not from CONTENDERS: since F-022 the
    # incumbent row's set is known only after its artifact is loaded, and a matrix
    # built from the declaration would be exactly the matrix the declaration was
    # wrong about.
    sets_needed = tuple(sorted({item.feature_set for item in loaded}))
    all_metrics = []
    winner: Loaded | None = None
    for split in ("val", holdout):
        splits = _load_split(split, data_cfg, train_cfg, sets_needed, args.smoke_rows)
        y = splits[sets_needed[0]].y.to_numpy()
        for item in loaded:
            matrix = splits[item.feature_set].features
            prediction = item.predictor(matrix)
            if isinstance(prediction, baselines.Prediction):
                values, unseen = prediction.values, prediction.unseen_rate
            else:
                values, unseen = prediction, None
            metrics = evaluate(item.name, split, y, values, eval_cfg, unseen_rate=unseen)
            item.metrics[split] = metrics
            all_metrics.append(metrics)
        del splits
        if split == "val":
            _assert_val_reproduced(loaded, smoke)
            winner = _select_winner(loaded, holdout)
    assert winner is not None  # the val branch above always runs first

    print("\n[evaluate] every number below came from taxi_mlops.training.evaluate")
    print("[evaluate] (gotcha #15: nothing else in this program may report one)\n")
    print(results_table(all_metrics))

    # ---- five verdicts, the floor's against itself included.
    # Consulted on a smoke run too: it is a registry READ, and a rehearsal that
    # skips F-011's two conditions rehearses the wrong gate. Nothing downstream
    # of it can promote on a smoke run — `main` returns before `_promote_winner`.
    incumbent = _incumbent(train_cfg, holdout)
    floor_metrics = loaded[0].metrics[holdout]
    decisions = {}
    print("\n" + "=" * 78)
    print("[gate] FIVE VERDICTS — configs/train.yaml: gate (loosening it is a PO fork)")
    print(f"[gate] bar: KPI-09 at least {gate_cfg['min_improvement_pct']:.2f}% below "
          f"{floor_name}, KPI-10 no regression, and both against the incumbent (F-011)")
    for item in loaded:
        decision = gate.decide(item.metrics[holdout], floor_metrics, gate_cfg, incumbent=incumbent)
        decisions[item.spec.label] = decision
        print("-" * 78)
        print(f"[gate] contender : {item.spec.label}  ({item.spec.track} track, features "
              f"{item.feature_set}, hyperparameters {item.spec.hyperparameters})")
        if item.spec is CONTENDERS[0]:
            print("[gate] this row is the FLOOR judged against ITSELF — an expected REFUSE "
                  "at +0.00%, printed because a gate only ever shown passing is a gate "
                  "nobody has watched work")
        # False, deliberately, and not because this bake-off ranks on the holdout
        # (since M4-S1 it does not): FIVE contenders are read on this month and
        # only one of them is the run's subject, so "untouched by selection" is
        # not a sentence this transcript may print unqualified. The bake-off
        # states its own selection basis on the line below instead (F-018).
        print(gate.verdict_lines(decision, holdout_untouched_by_selection=False))
        for caveat in item.spec.caveats:
            print(f"[gate] caveat    : {caveat}")
    print(f"[gate] selection : the winner was chosen on VAL before any {holdout} number "
          f"existed — {SELECTION_SPLIT} MAE, ranked above")
    print("=" * 78)

    _print_square(loaded, holdout)
    print(f"\n[bakeoff] WINNER (selected on {SELECTION_SPLIT}): {winner.spec.label} "
          f"({winner.name}) — {SELECTION_SPLIT} KPI-09 {winner.metrics[SELECTION_SPLIT].mae:.4f} "
          f"min")
    print(f"[bakeoff] its {holdout} numbers, measured AFTER it was chosen: KPI-09 "
          f"{winner.metrics[holdout].mae:.4f} min · "
          f"{winner.metrics[holdout].within_tolerance_rate:.3f}% KPI-10")
    print(f"[bakeoff] its verdict: {decisions[winner.spec.label].verdict}")

    payload = _payload(loaded, decisions, winner, train_cfg, floor, train_months, train_rows,
                       holdout, incumbent)
    if smoke:
        print("\n[bakeoff] SMOKE: no JSON written, nothing promoted, no number above is a "
              "result.")
        return 0
    _write(Path(args.out), payload)

    if not args.promote_winner:
        print("\n[promote] SKIPPED — --promote-winner was not passed. The verdicts above "
              "stand recorded and the registry is untouched.")
        return 0
    return _promote_winner(winner, decisions[winner.spec.label], train_cfg)


# --------------------------------------------------------------- resolution ----


def _resolve(spec: Spec, train_cfg: dict[str, Any]) -> Loaded:
    """Turn a declared contender into a loaded predictor with its provenance.

    Four resolution kinds, and none of them is "a run id typed into this file":
    the champion comes from the ALIAS (so this bake-off judges what is actually
    serving), the automation arms come from the JSON their own track wrote, and
    the artisan arm comes from a search that refuses to proceed unless it matches
    exactly one run. A hardcoded id would still be correct today and would be a
    silent lie the first time an experiment is re-run.
    """
    kind, address = spec.source
    if kind == "floor":
        return Loaded(spec=spec, name="(fitted below)", run_id=None, family="group-by",
                      recorded_val_mae=None, best_iteration=None,
                      feature_set=spec.feature_set or "v1")

    run_id = _resolve_run_id(kind, address, train_cfg)
    return _load_booster(spec, run_id, train_cfg)


def _resolve_run_id(kind: str, address: str, train_cfg: dict[str, Any]) -> str:
    import mlflow

    from taxi_mlops.training import tracking

    tracking.configure(train_cfg["mlflow"])
    client = mlflow.MlflowClient()

    if kind == "registry-alias":
        model_name = train_cfg["registry"]["model_name"]
        version = client.get_model_version_by_alias(model_name, address)
        print(f"[resolve] models:/{model_name}@{address} -> version {version.version} "
              f"(run {version.run_id})")
        return str(version.run_id)

    if kind == "refit-json":
        row = json.loads(Path(address).read_text())
        if not row.get("full_data"):
            raise SystemExit(
                f"{address} records a run that was NOT full-data. DR-05: all five "
                "bake-off contenders are full-data, train-only fits, and F-008 is why "
                "— a sampled contender degrades the FLOOR faster than itself."
            )
        print(f"[resolve] {address} -> run {row['run_id']} ({row['contender']})")
        return str(row["run_id"])

    if kind == "mlflow-run":
        experiment_name, run_name = address.split("/", 1)
        experiment = client.get_experiment_by_name(experiment_name)
        if experiment is None:
            raise SystemExit(f"MLflow has no experiment named {experiment_name!r}")
        found = client.search_runs(
            [experiment.experiment_id],
            filter_string=(
                f"attributes.run_name = '{run_name}' and params.sample_fraction = '1.0'"
            ),
        )
        if len(found) != 1:
            raise SystemExit(
                f"{address} at full scale matches {len(found)} runs and this bake-off "
                "will not choose between them. A contender resolved by picking the "
                "newest of several is a contender nobody can re-derive."
            )
        print(f"[resolve] {address} (sample_fraction=1.0) -> run {found[0].info.run_id}")
        return str(found[0].info.run_id)

    raise SystemExit(f"unknown contender source kind {kind!r}")


def _load_booster(spec: Spec, run_id: str, train_cfg: dict[str, Any]) -> Loaded:
    """Load one logged model and check it eats the feature set the spec declares.

    The flavor is READ off the logged model rather than inferred from the run's
    `family` param: the flavor is what a loader will actually find, and M5 will
    hit exactly this question when it resolves the alias. F-009's resolution step
    (`get_model_info(uri).model_uri`) is used for the same reason `score.py` uses
    it — the registry-uri load path looks under the run's artifact prefix and
    finds nothing.
    """
    import mlflow

    from taxi_mlops.features import quote_time, sets
    from taxi_mlops.tuning.fit import TunedModel

    client = mlflow.MlflowClient()
    run = client.get_run(run_id)
    info = mlflow.models.get_model_info(f"runs:/{run_id}/model")
    if info.signature is None or info.saved_input_example_info is None:
        raise SystemExit(
            f"{spec.label} (run {run_id}) has no signature and/or no input example, so "
            "it is not promotable (registry.assert_servable) and has no business in a "
            "bake-off whose winner takes the alias."
        )
    family = "lgbm" if "lightgbm" in info.flavors else "xgboost"
    flavor = mlflow.lightgbm if family == "lgbm" else mlflow.xgboost
    booster = flavor.load_model(info.model_uri)

    best_iteration = int(run.data.params["best_iteration"])
    actual = (list(booster.feature_name()) if family == "lgbm"
              else list(booster.feature_names))
    feature_set = spec.feature_set or _feature_set_of(actual, spec.label)
    features_cfg = sets.resolve_set(feature_set)
    expected = quote_time.feature_names(features_cfg)
    predictor = TunedModel(
        family=family,
        booster=booster,
        name=run.info.run_name,
        params={},
        num_boost_round=best_iteration,
        best_iteration=best_iteration,
        feature_names=expected,
    )
    if actual != expected:
        raise SystemExit(
            f"{spec.label} eats {actual} but feature set {feature_set!r} is "
            f"{expected}. Scoring it would silently reorder columns — the same refusal "
            "score.py makes about the champion."
        )
    recorded = run.data.metrics.get("val_mae")
    derived = " (DERIVED from the artifact — F-022)" if spec.feature_set is None else ""
    print(f"[resolve] {spec.label:<16} {run.info.run_name:<18} family={family:<8} "
          f"features={feature_set} ({len(expected)}){derived} trees={best_iteration} "
          f"recorded val MAE {recorded}")
    return Loaded(spec=spec, name=run.info.run_name, run_id=run_id, family=family,
                  recorded_val_mae=None if recorded is None else float(recorded),
                  best_iteration=best_iteration, predictor=predictor.predict,
                  feature_set=feature_set)


def _feature_set_of(feature_names: list[str], label: str) -> str:
    """Which declared feature set does this booster actually eat? (F-022)

    Derived from the ARTIFACT, never from the run's `feature_set` param: the param
    is the fitting script's claim about what it built, and the whole point of this
    check is to catch a disagreement between a claim and a model. Matching is on
    the ORDERED name list, because `_load_booster`'s next refusal is about order.

    It requires exactly ONE match. Two sets with identical column lists would make
    "which set is this?" unanswerable from the artifact, and answering it by taking
    the first would put a contender's provenance at the mercy of dict ordering in
    a YAML file.
    """
    from taxi_mlops.features import quote_time, sets

    matches = [
        name for name in sets.set_names()
        if quote_time.feature_names(sets.resolve_set(name)) == feature_names
    ]
    if len(matches) != 1:
        raise SystemExit(
            f"{label} eats {len(feature_names)} column(s) matching {len(matches)} declared "
            f"feature set(s) {matches} in configs/features.yaml. The incumbent row reads its "
            "feature set off the loaded model (F-022), and a model whose columns match no "
            "declared set — or more than one — cannot be scored against a matrix this "
            "program knows how to build."
        )
    return matches[0]


def _load_split(split: str, data_cfg: Any, train_cfg: dict[str, Any],
                versions: tuple[str, ...], smoke_rows: int) -> dict[str, Any]:
    """Read one split ONCE and build every feature matrix the bake-off needs.

    Re-reading per feature set would double the I/O and, worse, would let two
    contenders differ by which rows they happened to read — the same argument
    `load_frame` was split out for at M3-S3.
    """
    from taxi_mlops.features import quote_time, sets
    from taxi_mlops.training.datasets import Split, load_frame

    target = train_cfg["target"]
    resolved = {version: sets.resolve_set(version) for version in versions}
    columns: list[str] = []
    for cfg in resolved.values():
        for column in [*quote_time.source_columns(cfg), target]:
            if column not in columns:
                columns.append(column)

    frame, months = load_frame(split, data_cfg, columns)
    if smoke_rows:
        frame = frame.head(smoke_rows)
    print(f"[data] {split:<5} {len(frame):>12,} rows  months={','.join(months)}"
          + ("   <<< SMOKE TRUNCATION, NOT A RESULT" if smoke_rows else ""))
    y = frame[target].astype("float64")
    out = {
        version: Split(name=split, months=months,
                       features=quote_time.build_features(frame, cfg), y=y)
        for version, cfg in resolved.items()
    }
    del frame
    return out


# ------------------------------------------------------------------ checks ----


def _assert_val_reproduced(loaded: list[Loaded], smoke: bool) -> None:
    """Every model must re-measure its own recorded val MAE, or it is not admitted.

    This is the strongest thing this script does before the gate speaks. The
    numbers in `docs/ablation_m3.md` and `docs/automation_track_m3.md` were
    measured by two other scripts in two other processes on two other days; if
    the artifact loaded here reproduces them, the test numbers below describe the
    same models those documents describe. If it does not, the test numbers
    describe something else and no amount of care downstream would notice.
    """
    print("\n[admit] re-scoring VAL to prove each artifact IS the model its row claims")
    failures = []
    for item in loaded:
        if item.recorded_val_mae is None:
            print(f"[admit] {item.spec.label:<12} floor — fitted in this process, "
                  "nothing recorded to reproduce")
            continue
        measured = item.metrics["val"].mae
        delta = abs(measured - item.recorded_val_mae)
        ok = delta <= VAL_REPRODUCTION_TOLERANCE
        print(f"[admit] {item.spec.label:<12} recorded {item.recorded_val_mae!r} · "
              f"re-scored {measured!r} · delta {delta:.3e}  "
              f"{'MATCH' if ok else 'MISMATCH'}")
        if not ok and not smoke:
            failures.append(item.spec.label)
    if smoke:
        print("[admit] SMOKE: mismatches are EXPECTED (the splits were truncated) and "
              "are not being enforced. This run is not a result.")
        return
    if failures:
        raise SystemExit(
            f"{', '.join(failures)} did not reproduce the val MAE their own MLflow run "
            "records. Either the artifact loaded is not the artifact that was measured, "
            "or this file builds features differently from the path that fitted it. "
            "Refusing to put a number on the test month for a model nobody can identify."
        )
    print("[admit] all admitted — every loaded artifact reproduces its recorded val MAE")


def _incumbent(train_cfg: dict[str, Any], holdout: str):
    from taxi_mlops.training.run import _resolve_incumbent

    incumbent = _resolve_incumbent(train_cfg, holdout)
    if incumbent is None:
        print("[gate] incumbent : the champion alias is unset — nothing is serving")
    return incumbent


# ------------------------------------------------------------------ output ----


def _banner(smoke: bool, args: argparse.Namespace) -> None:
    print("=" * 78)
    print("[bakeoff] M3-S5 — five contenders, one evaluator, one untouched month")
    print("[bakeoff] NOTHING IS RE-FITTED: the four models are loaded from the MLflow")
    print("[bakeoff] artifacts their val numbers describe. Only the floor is fitted.")
    if smoke:
        print(f"[bakeoff] *** SMOKE RUN ({args.smoke_rows:,} rows/split) — NOT A RESULT ***")
    if args.promote_winner:
        print("[bakeoff] --promote-winner: the alias WILL move if the winner's verdict "
              "passes")
    print("=" * 78)


def _print_declaration(train_cfg: dict[str, Any]) -> None:
    print("\n[bakeoff] the 2x2 (+ floor), declared before a number is measured:\n")
    print(f"  {'contender':<16} {'track':<11} {'features':<13} hyperparameters")
    print(f"  {'-' * 16} {'-' * 11} {'-' * 13} {'-' * 40}")
    for spec in CONTENDERS:
        declared = spec.feature_set or "(the model's)"
        print(f"  {spec.label:<16} {spec.track:<11} {declared:<13} "
              f"{spec.hyperparameters}")
    print(f"\n  configs/train.yaml: features.version is {train_cfg['features']['version']!r} "
          "(what is SERVING; it moves only as part of a promotion)")


def _select_winner(loaded: list[Loaded], holdout: str) -> Loaded:
    """Rank the model contenders on `SELECTION_SPLIT` and name the winner (F-018).

    Called from inside the split loop, on the val iteration, so that it is
    physically impossible for a holdout number to influence it: none has been
    measured yet. `loaded[0]` — the floor — is excluded from the ranking because
    it is the BAR, not a candidate to serve; it still gets a holdout number and a
    verdict of its own further down, which is how the gate is watched refusing
    something.
    """
    models = loaded[1:]
    ranked = sorted(models, key=lambda item: item.metrics[SELECTION_SPLIT].mae)
    print(f"\n[bakeoff] SELECTION on {SELECTION_SPLIT} — the holdout has not been loaded "
          "yet, let alone scored (F-018)")
    for position, item in enumerate(ranked, start=1):
        print(f"  {position}. {item.spec.label:<14} KPI-09 "
              f"{item.metrics[SELECTION_SPLIT].mae:.4f} min  ·  KPI-10 "
              f"{item.metrics[SELECTION_SPLIT].within_tolerance_rate:.3f}%")
    winner = ranked[0]
    print(f"[bakeoff] chosen: {winner.spec.label}. The {holdout} month's only job is to "
          "pronounce a verdict on it.")
    return winner


#: The 2x2's origin cell: **v1 features, hand-chosen hyperparameters**. Both M3
#: tracks started there and searched one axis each (DR-03's disjoint axes), so it
#: is the only reference under which "features alone" and "tuning alone" are
#: comparable quantities. It is a DESCRIPTION of a cell, not a pointer: in M3 the
#: alias happened to hold exactly this model and the square read the incumbent row
#: for it, which is why the square broke the moment F-022 was landed.
SQUARE_BASE = ("v1", "hand")


def _print_square(loaded: list[Loaded], holdout: str) -> None:
    """The arithmetic the 2x2 exists to do: features, tuning, or both?

    Printed only when a contender still occupies the origin cell. Through M3 that
    was the incumbent row — the alias held `lightgbm-v1`, v1 features and hand
    hyperparameters — and the square simply read it by label. F-022 made the
    incumbent row mean "whatever is serving", and what is serving is now a TUNED
    v2 model, i.e. the "both" cell. Computing the square against it would report
    `auto-on-v2 +0.00%` and `artisan v2 −0.03%` — arithmetic that is correct,
    reads as a result, and answers a different question from the one the 2x2 asks.

    So the degeneracy is stated instead of rendered. M3's answer is measured,
    recorded and unchanged; it is not this invocation's to re-derive.
    """
    by_label = {item.spec.label: item for item in loaded}
    base_row = next(
        (item for item in loaded
         if item.feature_set == SQUARE_BASE[0]
         and item.spec.hyperparameters.startswith(SQUARE_BASE[1])),
        None,
    )
    if base_row is None:
        print(f"\n[bakeoff] the 2x2 is NOT printed: no contender occupies its origin cell "
              f"(features {SQUARE_BASE[0]}, {SQUARE_BASE[1]} hyperparameters).")
        print("[bakeoff] Through M3 the incumbent row held it, because the alias held "
              "lightgbm-v1. Since F-022 that row means 'whatever is serving', and what "
              "serves is a tuned v2 model — the square's OWN 'both' cell.")
        print("[bakeoff] M3's answer stands as measured: docs/bakeoff_m3.md §6 "
              "(features +0.56%, tuning on top of them +0.07 points).")
        return

    base = base_row.metrics[holdout].mae

    def pct(label: str) -> str:
        return f"{100.0 * (base - by_label[label].metrics[holdout].mae) / base:+.2f}%"

    print(f"\n[bakeoff] the 2x2, on {holdout}, all relative to {base_row.spec.label} "
          f"({base:.4f} min):")
    print(f"  features alone  (v1 -> v2, hand params)      artisan v2  {pct('artisan v2')}")
    print(f"  tuning alone    (v1 features, tuned params)  auto-on-v1  {pct('auto-on-v1')}")
    print(f"  both            (v2 features, tuned params)  auto-on-v2  {pct('auto-on-v2')}")


def _payload(loaded, decisions, winner, train_cfg, floor, train_months, train_rows,
             holdout, incumbent) -> dict[str, Any]:
    return {
        "story": "M3-S5",
        "holdout_split": holdout,
        "gate": {
            "floor": train_cfg["gate"]["floor"],
            "min_improvement_pct": train_cfg["gate"]["min_improvement_pct"],
            "require_no_kpi10_regression": train_cfg["gate"]["require_no_kpi10_regression"],
            # F-016 (M9-S10): the incumbent bar this run's verdicts were taken
            # against. `verify-m3` §5 replays those verdicts through the gate on
            # disk, so a record written under one bar and replayed under another
            # is not a replay — the record carries its own era from here on, and
            # the M3-S5 record that predates this key is enumerated in
            # `taxi_mlops.training.gate_eras` instead.
            "incumbent_min_improvement_pct": train_cfg["gate"]["incumbent_min_improvement_pct"],
        },
        "incumbent": None if incumbent is None else {
            "version": incumbent.version, "mae": incumbent.mae,
            "within_tolerance_rate": incumbent.within_tolerance_rate,
            "split": incumbent.split, "source": incumbent.source,
        },
        "floor_fit": {
            "name": floor.name,
            "groups": floor.groups,
            "fallback_groups": getattr(floor, "fallback_groups", None),
            "fallback_minutes": round(floor.fallback, 6),
            "train_months": list(train_months),
            "train_rows": train_rows,
        },
        "winner": winner.spec.label,
        # F-018: WHERE the winner was ranked, recorded beside who won, so a later
        # reader of this file never has to infer it from the code that wrote it.
        # `automation/runs/m3s5/bakeoff.json` — the M3 record — predates this key
        # and is deliberately NOT regenerated: its absence is the honest marker
        # of a run that ranked on the holdout.
        "winner_selected_on": SELECTION_SPLIT,
        "contenders": [
            {
                "label": item.spec.label,
                "name": item.name,
                "track": item.spec.track,
                "feature_set": item.feature_set,
                "hyperparameters": item.spec.hyperparameters,
                "run_id": item.run_id,
                "family": item.family,
                "best_iteration": item.best_iteration,
                "recorded_val_mae": item.recorded_val_mae,
                "val_mae": item.metrics["val"].mae,
                "val_within_rate": item.metrics["val"].within_tolerance_rate,
                f"{holdout}_mae": item.metrics[holdout].mae,
                f"{holdout}_within_rate": item.metrics[holdout].within_tolerance_rate,
                f"{holdout}_rows": item.metrics[holdout].n,
                "verdict": decisions[item.spec.label].verdict,
                "observed_pct": decisions[item.spec.label].observed_pct,
                "checks": [
                    {"name": check.name, "passed": check.passed, "detail": check.detail}
                    for check in decisions[item.spec.label].checks
                ],
                "caveats": list(item.spec.caveats),
            }
            for item in loaded
        ],
    }


def _write(path: Path, payload: dict[str, Any]) -> None:
    """Write the row set — and refuse if a previous run measured different numbers.

    A second invocation of this script (the promoting one) re-measures everything
    from the same artifacts on the same rows, so every number must come back
    identical. Comparing them is free and turns the second run into a
    reproducibility proof rather than a repetition. If a number legitimately
    moved, the previous file is deleted BY HAND — an explicit, visible action,
    not a `--force` nobody reads.
    """
    if path.exists():
        previous = json.loads(path.read_text())
        before = {row["label"]: row for row in previous["contenders"]}
        holdout = previous["holdout_split"]
        drifted = []
        for row in payload["contenders"]:
            old = before.get(row["label"])
            if old is None:
                continue
            for key in (f"{holdout}_mae", f"{holdout}_within_rate", "val_mae"):
                if old.get(key) != row.get(key):
                    drifted.append(f"{row['label']}.{key}: {old.get(key)} -> {row.get(key)}")
        if drifted:
            raise SystemExit(
                "this run measured different numbers from " + str(path) + ":\n  "
                + "\n  ".join(drifted)
                + "\nSame artifacts, same rows, same evaluator — these numbers are "
                "deterministic, so a difference is a change nobody declared. Delete "
                "that file deliberately if you mean to re-baseline."
            )
        print(f"\n[bakeoff] REPRODUCED {path} exactly — every contender's val and "
              f"{holdout} numbers are unchanged")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(f"[bakeoff] rows written to {path}")


# --------------------------------------------------------------- promotion ----


def _promote_winner(winner: Loaded, decision, train_cfg: dict[str, Any]) -> int:
    """Move the alias — through `make train`'s own promotion path, or not at all."""
    from taxi_mlops.training.run import Contender, _promote

    if not decision.passed:
        print("\n[promote] REFUSED — the winner did not pass the gate. Nothing "
              "registered, no alias moved. The incumbent keeps serving.")
        return 1

    configured = train_cfg["features"]["version"]
    if configured != winner.feature_set:
        raise SystemExit(
            f"the winner eats feature set {winner.feature_set!r} and "
            f"configs/train.yaml: features.version says {configured!r}. That line is "
            "what `score.py` and `verify-m2` check the champion against, so promoting "
            "now would mint a version the next `make predictions` refuses to score. "
            "Move the config line as PART of this promotion (M3-S3's law), commit it, "
            "and run this again."
        )

    contender = Contender(
        name=winner.name,
        params={},
        predict=winner.predictor,
        metrics=list(winner.metrics.values()),
        run_id=winner.run_id,
        model_logged=True,
    )
    promotion = _promote(contender, train_cfg, decision)
    print(f"[promote] the bake-off's winner is now version {promotion.version}.")
    print("[promote] next, in order: make predictions -> make duckdb -> make marts -> "
          "make boards, then re-run make verify-m2.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
