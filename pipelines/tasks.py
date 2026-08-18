"""The six pipeline stages, as plain Python. Owner story: M4-S1.

`ingest -> validate -> features -> train -> evaluate -> register`, the graph
BLUEPRINT §9/M4 names, written as six callables with typed inputs and typed
outputs and **no logic of their own**. Every body is a call into `taxi_mlops`
plus the bookkeeping needed to hand a *serializable* result to the next stage.
`pipelines/flyte/workflows.py` will wrap these at M4-S4 — decorator-deep, per
ADR-002 — and that thinness is only available if the graph is already testable
without an orchestrator, which is why this file exists a story before Flyte does.

Four decisions are recorded here rather than left to be re-derived:

1. **The modules stay the single home.** Nothing is reimplemented here and
   nothing is "adapted". If a stage looks like it wants a new rule, the rule
   belongs in `taxi_mlops` where the unit tests, the contract and the exclusion
   registry already live — `src/` never imports an orchestrator (ADR-001), and
   the price of that rule is that this direction of the dependency stays boring.

2. **The seam between `train`, `evaluate` and `register` is where the CODE's
   seam is, not where a diagram would like it.** `taxi_mlops.training.run.run()`
   fits, scores through the one evaluator, and asks the gate — in one call.
   Splitting it here would move the gate's decision into the pipeline layer,
   which is precisely the thing this file may not do. So `train` runs it and
   writes a RUN MANIFEST; `evaluate` reads the manifest and returns the numbers
   the evaluator produced (it computes none of its own — gotcha #15); `register`
   reads the same manifest and turns the gate's decision into the pipeline's
   output. The manifest is a JSON path because at M4-S4 these become separate
   Flyte tasks in separate pods, and a Python object cannot cross that boundary.

3. **A REFUSE is a RETURN VALUE, never an exception** — this is the pipeline's
   convention, and it differs from the CLI's on purpose. `python -m
   taxi_mlops.training train` maps verdicts onto exit codes (0 promoted-or-
   --no-promote · 1 REFUSED · 2 could not run · 3 no verdict issued, F-008)
   because a shell has nothing else to read. A workflow engine does: a refused
   challenger is a *successful run of a working gate*, and modelling it as a
   task failure would make every refusal look like an outage, put a retry on it,
   and eventually train somebody to disable the stage. So `register` returns
   `RegisterResult(decision=…, promoted=False, …)` and the task is GREEN. The
   mapping is kept legible in `RegisterResult.exit_code`, so a caller that needs
   the CLI's convention can have it without a second copy of the rules.

4. **No stage in this file can move `@champion`.** `train` calls `run()` with
   `promote=False` unconditionally, and `register`'s promoting branch is not
   built (see its docstring). That is M4's standing law — an orchestration demo
   must not make a promotion decision as a side effect — and it is also the
   honest consequence of F-016 being an open PO fork about the very condition
   that would decide it.

Run the local rehearsal with `make pipeline-local MONTH=2019-01`.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Where a rehearsal drops its manifests. One directory per invocation is NOT
#: used: a stable path per month is what makes a re-run resumable at M4-S4, the
#: way `automation/runs/m3s4/*.json` made the automation track resumable.
DEFAULT_RUN_DIR = "automation/runs/m4-pipeline"


# --------------------------------------------------------------- the outputs ---
# Frozen dataclasses of primitives, because at M4-S4 Flyte has to serialize them
# between pods. Nothing here holds a DataFrame, a booster or an open connection.


@dataclass(frozen=True)
class IngestResult:
    month: str
    split: str
    rows_in: int
    rows_out: int
    rows_rejected: int
    rejected_fraction: float
    processed_path: str
    rejected_path: str
    rejections_path: str


@dataclass(frozen=True)
class ValidationResult:
    month: str
    rows: int
    contract_year: int
    columns: tuple[str, ...]


@dataclass(frozen=True)
class FeatureResult:
    month: str
    split: str
    rows: int
    feature_set_version: str
    features: tuple[str, ...]
    source_columns: tuple[str, ...]


@dataclass(frozen=True)
class TrainResult:
    challenger: str
    feature_set_version: str
    run_id: str | None
    train_months: tuple[str, ...]
    sampled: bool
    judged: bool
    manifest_path: str
    fit_seconds: float


@dataclass(frozen=True)
class SplitMetrics:
    contender: str
    split: str
    rows: int
    kpi_09_mae_minutes: float
    kpi_10_within_rate: float


@dataclass(frozen=True)
class EvaluationResult:
    challenger: str
    metric_source: str
    metrics: tuple[SplitMetrics, ...]


@dataclass(frozen=True)
class RegisterResult:
    """The gate's verdict as DATA (decision 3 above).

    `decision` is one of PROMOTE / REFUSE / NO_VERDICT. `margins` carries the
    numbers the decision was made from, so a downstream reader never has to
    parse a transcript to learn why.
    """

    decision: str
    promoted: bool
    reason: str
    margins: dict[str, float] = field(default_factory=dict)
    champion_alias_version: str | None = None

    @property
    def exit_code(self) -> int:
        """The CLI's convention, stated once, for callers that need it.

        Mirrors `python -m taxi_mlops.training`'s docstring exactly. It is a
        property and not the task's behaviour: inside a pipeline this object IS
        the answer, and only a shell needs it flattened into a number.
        """
        return {"PROMOTE": 0, "REFUSE": 1, "NO_VERDICT": 3}[self.decision]


# ---------------------------------------------------------------- the stages ---


def ingest_month(month: str, *, data_config: str | None = None) -> IngestResult:
    """Download (if the manifest says to), enforce the contract, split, write.

    Wraps `taxi_mlops.data.ingest.ingest([month])`, which is idempotent and
    byte-identical on a re-run (M1-S1, re-proved at M2-S1) — that property is
    what lets M4-S4 re-invoke a month without a "have I already done this?" flag.
    A structurally wrong month RAISES here rather than returning a bad result:
    that is a broken input, not a verdict, and the distinction in decision 3
    above cuts exactly there.
    """
    from taxi_mlops.data.config import load_config
    from taxi_mlops.data.ingest import ingest

    cfg = load_config() if data_config is None else load_config(data_config)
    report = ingest([month], cfg)[0]
    return IngestResult(
        month=month,
        split=cfg.splits.split_of(month),
        rows_in=report.rows_in,
        rows_out=report.rows_out,
        rows_rejected=report.rows_rejected,
        rejected_fraction=round(report.rejected_fraction, 6),
        processed_path=str(cfg.processed_path(month)),
        rejected_path=str(cfg.rejected_path(month)),
        rejections_path=str(cfg.rejections_path(month)),
    )


def validate(month: str) -> ValidationResult:
    """Re-read what ingest WROTE and put it back through the output contract.

    Not a duplicate of the check inside `ingest_month`: that one validates a
    frame in memory before it is written, this one validates the parquet that
    landed. Between them sit a pyarrow write, a `.part` rename and a filesystem —
    and the contract's `nullable: false` entries are a POST-clean guarantee
    (CLAUDE.md), so re-asserting them against the artifact the next stage will
    actually read costs seconds and covers the gap. `contract.validate_output`
    is the same function ingest uses; there is no second copy of the rules.
    """
    import pyarrow.parquet as pq

    from taxi_mlops.data.config import load_config
    from taxi_mlops.data.contract import validate_output, year_of

    cfg = load_config()
    path = cfg.processed_path(month)
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing — `ingest` has not run for {month}")
    frame = pq.read_table(path).to_pandas()
    validated = validate_output(frame, month, cfg)
    return ValidationResult(
        month=month,
        rows=len(validated),
        contract_year=year_of(month),
        columns=tuple(validated.columns),
    )


def build_features(month: str, *, train_config: str = "configs/train.yaml") -> FeatureResult:
    """Build the CONFIGURED feature set for one month through the ONE path.

    `taxi_mlops.features.quote_time.build_features` is the function M5's serving
    transformer imports, so a stage that built features any other way would be
    testing something the pipeline does not run. The set is whatever
    `configs/train.yaml: features.version` names, expanded by the one loader —
    this stage never lists columns.

    It returns a shape and the names, not the matrix: 7M rows do not cross a task
    boundary, and the training stage rebuilds from the same pinned parquet. What
    this stage proves is that the month's data CAN produce the served feature
    set — which is a real failure mode (F-019: the configured set raises for any
    date the holiday table does not cover).
    """
    from taxi_mlops.data.config import load_config
    from taxi_mlops.features import quote_time
    from taxi_mlops.training.datasets import load_frame, required_columns
    from taxi_mlops.training.run import load_train_config

    train_cfg = load_train_config(train_config)
    data_cfg = load_config(train_config=train_config)
    features_cfg = train_cfg["features"]
    target = train_cfg["target"]
    split = data_cfg.splits.split_of(month)

    columns = required_columns(features_cfg, target)
    frame, _ = load_frame(split, data_cfg, columns, months=(month,))
    matrix = quote_time.build_features(frame, features_cfg)
    return FeatureResult(
        month=month,
        split=split,
        rows=len(matrix),
        feature_set_version=features_cfg["version"],
        features=tuple(matrix.columns),
        source_columns=tuple(quote_time.source_columns(features_cfg)),
    )


def train(
    *,
    train_months: tuple[str, ...] | None = None,
    judge: bool = True,
    experiment: str | None = None,
    story: str | None = None,
    log_to_mlflow: bool = True,
    train_config: str = "configs/train.yaml",
    run_dir: str = DEFAULT_RUN_DIR,
) -> TrainResult:
    """Fit the floors and the challenger, score them, ask the gate. Promote NEVER.

    `promote=False` is passed unconditionally and is not a parameter of this
    function: M4's standing law is that no pipeline run moves `@champion`, and a
    law with a keyword argument is a default. The one program that may promote is
    still `make train` (and the bake-off's explicit `--promote-winner`).

    Writes the run manifest the next two stages read. Its numbers come from
    `taxi_mlops.training.evaluate` and from `gate.decide`; nothing is recomputed
    on the way in.
    """
    from taxi_mlops.training.run import load_train_config, run

    started = time.monotonic()
    result = run(
        train_months=train_months,
        judge=judge,
        promote=False,
        log_to_mlflow=log_to_mlflow,
        experiment=experiment,
        story=story,
        train_config=train_config,
    )
    seconds = time.monotonic() - started

    train_cfg = load_train_config(train_config)
    configured = tuple(train_cfg["data"]["train_months"])
    months = tuple(train_months) if train_months is not None else configured
    manifest = _manifest(result, train_cfg, months, seconds)
    path = Path(run_dir) / "train_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, default=str) + "\n")
    print(f"[tasks] run manifest -> {path}")

    return TrainResult(
        challenger=result.challenger.name,
        feature_set_version=train_cfg["features"]["version"],
        run_id=result.challenger.run_id,
        train_months=months,
        sampled=months != configured,
        judged=result.decision is not None,
        manifest_path=str(path),
        fit_seconds=round(seconds, 1),
    )


def evaluate(manifest_path: str) -> EvaluationResult:
    """Report what the ONE evaluator measured. Compute nothing.

    gotcha #15 in stage form: only `taxi_mlops.training.evaluate` may produce a
    reported number in this program, so this stage's whole job is to lift its
    output out of the manifest and give it a type. If this function ever needs to
    calculate something, the calculation belongs in `evaluate.py`.
    """
    manifest = json.loads(Path(manifest_path).read_text())
    challenger = manifest["challenger"]["name"]
    rows = tuple(
        SplitMetrics(
            contender=row["contender"],
            split=row["split"],
            rows=row["n"],
            kpi_09_mae_minutes=row["mae"],
            kpi_10_within_rate=row["within_tolerance_rate"],
        )
        for row in manifest["metrics"]
        if row["contender"] == challenger
    )
    return EvaluationResult(
        challenger=challenger,
        metric_source=manifest["metric_source"],
        metrics=rows,
    )


def register(manifest_path: str, *, promote: bool = False) -> RegisterResult:
    """Turn the gate's verdict into the pipeline's output. A REFUSE is data.

    **The promoting branch is deliberately NOT built at M4.** Two reasons, both
    of which have to stop being true before it is:
      * M4's standing law — no run of this pipeline moves `@champion`, because an
        orchestration demo must not make a promotion decision as a side effect;
      * F-016 is an open PO fork (AWAITING_PO 2026-08-18-1) about the incumbent
        condition's missing margin, i.e. about the exact rule that would decide a
        pipeline promotion. Building the path now would mean choosing a default
        for a question that is on the PO's desk.
    When it IS built (M7's retrain loop), it must call
    `taxi_mlops.training.run._promote` — the one function `make train` and
    `scripts/bakeoff_m3.py` both already call — and never a second path. The
    first thing a second promotion path diverges on is the tags the gate is
    reconstructed from.
    """
    manifest = json.loads(Path(manifest_path).read_text())
    decision = manifest.get("decision")

    if promote:
        raise NotImplementedError(
            "pipelines.tasks.register cannot promote at M4 — see this function's "
            "docstring. The alias moves through `make train` or `make bakeoff "
            "--promote-winner`, and the pipeline's register stage stays "
            "verdict-as-data until F-016 is answered."
        )

    if decision is None:
        return RegisterResult(
            decision="NO_VERDICT",
            promoted=False,
            reason=(
                "no verdict was issued — a sampled run asked for with --no-gate "
                "(F-008). 'Not judged' and 'judged and satisfied' are the two "
                "things a pipeline must never confuse."
            ),
            champion_alias_version=manifest.get("champion_alias_version"),
        )

    return RegisterResult(
        decision=decision["verdict"],
        promoted=False,
        reason=(
            "--no-promote: the verdict stands recorded and the registry is "
            "untouched (M4's standing law)"
        ),
        margins={
            "challenger_mae": decision["challenger_mae"],
            "floor_mae": decision["floor_mae"],
            "observed_pct_vs_floor": decision["observed_pct"],
            "required_pct_vs_floor": decision["required_pct"],
            "challenger_within_rate": decision["challenger_within"],
            "floor_within_rate": decision["floor_within"],
        },
        champion_alias_version=manifest.get("champion_alias_version"),
    )


#: The graph, declared once so the driver, the tests and M4-S4's Flyte workflow
#: all read the same order from the same place.
STAGES: tuple[str, ...] = (
    "ingest_month",
    "validate",
    "build_features",
    "train",
    "evaluate",
    "register",
)


# ------------------------------------------------------------- the internals ---


def _manifest(
    result: Any, train_cfg: dict[str, Any], months: tuple[str, ...], seconds: float
) -> dict[str, Any]:
    """Everything `evaluate` and `register` need, and nothing they could recompute."""
    decision = result.decision
    return {
        "story": "M4-S1",
        "metric_source": "taxi_mlops.training.evaluate",
        "feature_set_version": train_cfg["features"]["version"],
        "train_months": list(months),
        "fit_seconds": round(seconds, 1),
        "challenger": {
            "name": result.challenger.name,
            "run_id": result.challenger.run_id,
        },
        "metrics": [
            dataclasses.asdict(metric)
            for contender in result.contenders
            for metric in contender.metrics
        ],
        "decision": None if decision is None else {
            "verdict": decision.verdict,
            "passed": decision.passed,
            "challenger": decision.challenger,
            "floor": decision.floor,
            "split": decision.split,
            "n": decision.n,
            "challenger_mae": decision.challenger_mae,
            "floor_mae": decision.floor_mae,
            "challenger_within": decision.challenger_within,
            "floor_within": decision.floor_within,
            "observed_pct": decision.observed_pct,
            "required_pct": decision.required_pct,
            "incumbent_version": (
                None if decision.incumbent is None else decision.incumbent.version
            ),
            "checks": [
                {"name": c.name, "passed": c.passed, "detail": c.detail}
                for c in decision.checks
            ],
        },
        # Read, never written. `verify-m4` will assert this did not move across a
        # pipeline run, and a manifest that records it makes that a comparison
        # rather than a memory.
        "champion_alias_version": _champion_version(train_cfg),
    }


def _champion_version(train_cfg: dict[str, Any]) -> str | None:
    """What `@champion` points at right now, or None if nothing is serving."""
    try:
        import mlflow

        from taxi_mlops.training import tracking

        tracking.configure(train_cfg["mlflow"])
        cfg = train_cfg["registry"]
        version = mlflow.MlflowClient().get_model_version_by_alias(
            cfg["model_name"], cfg["champion_alias"]
        )
        return str(version.version)
    except Exception as exc:  # noqa: BLE001 — an unreadable registry is not a stage failure
        print(f"[tasks] champion alias not read ({type(exc).__name__}: {exc})")
        return None


# ---------------------------------------------------------------- the driver ---


def rehearse(
    month: str,
    *,
    judge: bool,
    experiment: str | None,
    story: str | None,
    run_dir: str,
) -> int:
    """Run the six stages in order on ONE month. The local rehearsal, M4-S1.

    This composer is the LOCAL driver only. M4-S4's Flyte workflow composes the
    same six callables itself — an orchestrator that called `rehearse` would be
    orchestrating one task.
    """
    print(f"[tasks] rehearsing the M4 graph on {month}: {' -> '.join(STAGES)}")
    print(f"[tasks] gate: {'ON' if judge else 'OFF (F-008 smoke; NO verdict)'}\n")

    ingested = ingest_month(month)
    print(f"\n[1/6] ingest_month   : {ingested.rows_out:,} rows out of "
          f"{ingested.rows_in:,} ({ingested.rejected_fraction:.4%} rejected) -> "
          f"{ingested.processed_path}")

    validated = validate(month)
    print(f"[2/6] validate       : {validated.rows:,} rows re-read and re-checked "
          f"against the {validated.contract_year} output contract, "
          f"{len(validated.columns)} columns")

    features = build_features(month)
    print(f"[3/6] build_features : set {features.feature_set_version} — "
          f"{len(features.features)} columns over {features.rows:,} rows "
          f"({features.split} split)")

    trained = train(
        train_months=(month,),
        judge=judge,
        experiment=experiment,
        story=story,
        run_dir=run_dir,
    )
    print(f"\n[4/6] train          : {trained.challenger} (set "
          f"{trained.feature_set_version}), run {trained.run_id}, "
          f"{trained.fit_seconds:.1f}s, sampled={trained.sampled}, "
          f"judged={trained.judged}")

    measured = evaluate(trained.manifest_path)
    print(f"[5/6] evaluate       : from {measured.metric_source}")
    for row in measured.metrics:
        print(f"        {row.split:<5} KPI-09 {row.kpi_09_mae_minutes:.4f} min · "
              f"KPI-10 {row.kpi_10_within_rate:.3f}% over {row.rows:,} rows")

    verdict = register(trained.manifest_path)
    print(f"[6/6] register       : decision={verdict.decision} promoted="
          f"{verdict.promoted} (CLI exit-code class {verdict.exit_code})")
    print(f"        {verdict.reason}")
    if verdict.margins:
        print(f"        margins: {json.dumps(verdict.margins)}")
    print(f"        @champion is version {verdict.champion_alias_version} — read, "
          "never written")

    print(f"\n[tasks] all {len(STAGES)} stages composed on {month}. This is a "
          "PLUMBING rehearsal: no number above is a result.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python pipelines/tasks.py", description=__doc__)
    parser.add_argument("--month", required=True, metavar="YYYY-MM")
    parser.add_argument(
        "--gate",
        action="store_true",
        help="ask for a verdict. Illegal on a one-month rehearsal (F-008) and "
        "present only so the refusal can be watched happening",
    )
    parser.add_argument("--experiment", default="m4-pipeline")
    parser.add_argument("--story", default="M4-S1")
    parser.add_argument("--run-dir", default=DEFAULT_RUN_DIR)
    args = parser.parse_args(argv)

    # FIRST, before anything imports LightGBM — the shim re-execs this process
    # (gotcha #37), and re-execing after reading 7M rows would do that work twice.
    from taxi_mlops.training.openmp import ensure_openmp

    ensure_openmp()
    sys.stdout.reconfigure(line_buffering=True)

    return rehearse(
        args.month,
        judge=args.gate,
        experiment=args.experiment,
        story=args.story,
        run_dir=args.run_dir,
    )


if __name__ == "__main__":
    raise SystemExit(main())
