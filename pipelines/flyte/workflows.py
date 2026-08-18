"""workflows.py — the six-stage pipeline as Flyte tasks (M4-S4).

This file is DECORATOR-DEEP AND NOTHING ELSE, which is ADR-002's honest cost
argument made literal: every body here is one call into `pipelines.tasks`, which
is itself one call into `taxi_mlops`. Nothing computes, nothing decides, nothing
reshapes a number. If a change to this file would alter a KPI, it is in the wrong
file — the modules stay the single home (M4-S1's rule, inherited unchanged).

WHAT IS TYPED AND WHY IT IS TYPED THAT WAY. Flyte moves a task's outputs through
the blob store to the next task's pod, so every value crossing a stage boundary
is a value that must survive serialization. The stage results in
`pipelines.tasks` are frozen dataclasses holding `tuple[str, ...]` fields — a
shape built for a single Python process, and one this file deliberately does not
push through the type engine. Instead the seams carry exactly what M4-S1 said
they would carry: "month string in, paths/run-ids/verdict out". The rich result
objects still exist; they are logged where they are produced, on the pod that
produced them, which is where a human debugging that stage will look.

THE TRAIN -> EVALUATE -> REGISTER SEAM CARRIES THE MANIFEST'S CONTENT, NOT ITS
PATH. M4-S1 wrote the manifest as a JSON path "because at S4 they are separate
pods" — and separate pods is exactly why the path cannot be the thing that
travels. `/app/automation/runs/...` on the train pod does not exist on the
evaluate pod. Two options were real here: mount a shared writable volume and keep
passing the path, or pass the manifest's TEXT and let Flyte's blob store move it.
The text wins, and not only because it is less plumbing: stages that communicate
through a shared mount have a dependency the DAG cannot see, and the day one of
them runs on another node the pipeline breaks in a way that looks like data
corruption. Passing the content puts the dependency in the graph, where the
retry logic and the cache can both see it. The consuming stages take a path
because `pipelines.tasks` takes a path, so they write the text to a temp file
first — marshalling at the boundary, which is a wrapper's whole job.

NO STAGE HERE CAN MOVE `@champion`. `tasks.train` passes `promote=False`
unconditionally and has no `promote` parameter; `tasks.register`'s promoting
branch raises `NotImplementedError` while F-016 sits on the PO's desk. This file
adds no third path — it could not promote if it wanted to, which is the property
`verify-m4` asserts from the other end by reading the alias before and after.

A REFUSE IS A GREEN PIPELINE. The gate saying no is a successful run of a working
gate, so `register` returns the verdict as data and never raises. The exit-code
mapping (0/1/2/3) lives in exactly one place, `tasks.RegisterResult.exit_code`,
and is a CLI concern that this file does not import.

Run it:  make pipeline MONTH=2019-01     (scripts/run_pipeline.sh for the wiring)
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import flyte

# The task image, read from the file `make image-load` writes rather than
# hardcoded. The tag is the git short sha (M4-S3), so it moves with every commit
# and a literal here would be stale by the next one — and staleness is not
# cosmetic: kubernetes pulls `IfNotPresent` for a non-`:latest` tag, so a tag no
# node holds is a loud `ImagePullBackOff` rather than a wrong number, which is the
# property M4-S3 chose the tagging scheme FOR. If that is what you are looking at,
# the tree moved and the fix is `make image-load`.
_IMAGE_MANIFEST = Path(__file__).resolve().parents[2] / "automation/runs/m4-image/image.json"


def _image_ref() -> str:
    """The image this pipeline's tasks run, or a refusal naming how to make one."""
    override = os.environ.get("TAXI_PIPELINE_IMAGE")
    if override:
        return override
    if not _IMAGE_MANIFEST.exists():
        raise FileNotFoundError(
            f"{_IMAGE_MANIFEST} does not exist — the task image has never been built "
            "on this machine. Run `make image-load` (M4-S3), which builds it, loads "
            "it onto every kind node and writes this manifest."
        )
    return json.loads(_IMAGE_MANIFEST.read_text())["image_ref"]


# `from_base`, not `from_debian_base`: the image already EXISTS (M4-S3 built it
# and `kind load` put it on all three nodes), and asking Flyte to build one would
# throw away the artifact whose dependency graph was proved identical to the
# host's at 215/215 packages. `from_base` also declines to create a runtime user
# or chown the workdir, which is right here — the image already runs as uid 1000
# with `/app` owned by it, done at M4-S3 in the layer ordering that saved 1.7 GB.
#
# Resources are per-environment, so the stages are split across THREE environments
# rather than one: the train task needs a budget that would be absurd for a
# verdict-reading task, and three kind nodes share this laptop's 47Gi. The numbers
# are starting points to be tuned by observation (M4 kickoff), and what is
# observed is recorded in docs/pipeline_m4.md rather than left in a comment here.
_IMAGE = flyte.Image.from_base(_image_ref())

# The light stages: read a manifest, report a verdict. Nothing loads a dataframe.
light_env = flyte.TaskEnvironment(
    name="taxi-pipeline-light",
    image=_IMAGE,
    resources=flyte.Resources(cpu=(1, 2), memory=("1Gi", "4Gi")),
    pod_template="flyte-task-defaults",
)

# The data stages: one month of TLC yellow is ~7.6M rows through a pandera
# contract, and the ingest stage holds the input, the cleaned output and the
# rejected sidecar at once.
data_env = flyte.TaskEnvironment(
    name="taxi-pipeline-data",
    image=_IMAGE,
    resources=flyte.Resources(cpu=(1, 4), memory=("4Gi", "12Gi")),
    pod_template="flyte-task-defaults",
)

# The fit. 44M rows across six months, four contenders through one evaluator.
# The kickoff's starting point was ~24Gi and it is taken as written; the host
# measured ~25 minutes for this fit at M2-S2, so this is also the stage that makes
# a full-data run hours-class and therefore detached (gotcha #45).
train_env = flyte.TaskEnvironment(
    name="taxi-pipeline-train",
    image=_IMAGE,
    resources=flyte.Resources(cpu=(2, 6), memory=("8Gi", "24Gi")),
    pod_template="flyte-task-defaults",
)

# Every environment names the SAME PodTemplate, and that is the point of it being
# a named cluster object rather than an inline spec: how a task pod reaches MinIO,
# MLflow and the data volume is a property of this cluster, identical for all
# three, and a new environment added at M7 inherits it by naming one string. The
# object is infra/manifests/flyte-task-podtemplate.yaml; its header argues the
# whole design, including why the data is mounted by subPath.


@data_env.task
async def ingest(month: str) -> str:
    """Re-derive one month from the sha256-pinned raw parquet. Idempotent.

    Returns the processed parquet's path — inside THIS pod, on the staged volume,
    which is the one path that does mean the same thing in the next pod (the PVC
    is mounted at the same place in all of them). It is returned as evidence and
    as the stage's linkage, not as a channel: the next stage re-reads the month.
    """
    from pipelines import tasks

    result = tasks.ingest_month(month)
    print(
        f"[flyte] ingest {result.month} ({result.split}): "
        f"{result.rows_in:,} -> {result.rows_out:,} rows, "
        f"{result.rejected_fraction:.4%} rejected -> {result.processed_path}"
    )
    return result.processed_path


@data_env.task
async def validate(month: str, ingested: str) -> int:
    """Re-read what ingest wrote and put it back through the OUTPUT contract.

    `ingested` is not used for anything except the edge it draws: this stage must
    not start before that one finished, and in a dataflow engine the way you say
    so is to consume its output. Naming it and ignoring it is more honest than a
    hidden ordering, which is the same reason the manifest's content travels
    rather than its path.
    """
    from pipelines import tasks

    result = tasks.validate(month)
    print(
        f"[flyte] validate {result.month}: {result.rows:,} rows, "
        f"contract_year {result.contract_year}, {len(result.columns)} columns "
        f"(from {ingested})"
    )
    return result.rows


@data_env.task
async def build_features(month: str, validated: int) -> int:
    """Build the configured feature set through the ONE feature path.

    The set is whatever `configs/train.yaml` names — v2 as of M3-S5's promotion.
    `taxi_mlops.features` is the only transform path for training AND serving, so
    this stage cannot introduce a feature; it can only fail to build one.
    """
    from pipelines import tasks

    result = tasks.build_features(month)
    print(
        f"[flyte] features {result.month}: {result.rows:,} rows, set "
        f"{result.feature_set_version}, {len(result.features)} features "
        f"(validated {validated:,} rows)"
    )
    return result.rows


@train_env.task
async def train(train_months: str, judge: bool, featured: int) -> str:
    """Fit the floors and the challenger, score them, ask the gate. Promote NEVER.

    `train_months` is a comma-separated override and an EMPTY STRING means "the
    months configs/train.yaml configures" — Flyte's inputs are concrete values, so
    the absent case has to be spelled rather than defaulted to None.

    Returns the run manifest's CONTENT. See this module's docstring for why the
    content and not the path.
    """
    from pipelines import tasks

    months = tuple(m.strip() for m in train_months.split(",") if m.strip()) or None
    with tempfile.TemporaryDirectory() as tmp:
        result = tasks.train(
            train_months=months,
            judge=judge,
            experiment="m4-pipeline",
            story="M4-S4",
            run_dir=tmp,
        )
        manifest = Path(result.manifest_path).read_text()
    print(
        f"[flyte] train {result.challenger} (set {result.feature_set_version}): "
        f"run {result.run_id}, {result.fit_seconds}s, "
        f"sampled={result.sampled} judged={result.judged} "
        f"months={','.join(result.train_months)} (features saw {featured:,} rows)"
    )
    return manifest


@light_env.task
async def evaluate(manifest: str) -> str:
    """Report what the ONE evaluator measured. Compute nothing (gotcha #15)."""
    from pipelines import tasks

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "train_manifest.json"
        path.write_text(manifest)
        result = tasks.evaluate(str(path))
    for row in result.metrics:
        print(
            f"[flyte] evaluate {result.challenger} {row.split}: "
            f"KPI-09 {row.kpi_09_mae_minutes:.4f} min · "
            f"KPI-10 {row.kpi_10_within_rate:.3%} over {row.rows:,} rows "
            f"(source {result.metric_source})"
        )
    return manifest


@light_env.task
async def register(manifest: str) -> str:
    """The gate's verdict, as the pipeline's output. A REFUSE is not a failure.

    Returns the decision as a JSON string rather than a bare word, because the
    numbers the decision was made from are the half a reader actually needs and
    a downstream reader must never have to parse a transcript to get them.
    """
    from pipelines import tasks

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "train_manifest.json"
        path.write_text(manifest)
        result = tasks.register(str(path))
    print(
        f"[flyte] register decision={result.decision} promoted={result.promoted} "
        f"(CLI exit-code class {result.exit_code}) — {result.reason}"
    )
    return json.dumps(
        {
            "decision": result.decision,
            "promoted": result.promoted,
            "reason": result.reason,
            "margins": result.margins,
            "champion_alias_version": result.champion_alias_version,
        }
    )


@light_env.task
async def main(month: str = "2019-01", train_months: str = "", judge: bool = True) -> str:
    """ingest -> validate -> build_features -> train -> evaluate -> register.

    `judge` exists so the F-008 refusal can be honored rather than argued with: a
    sampled run (`train_months` non-empty) is not entitled to a verdict, so the
    caller passes `judge=False` and the register stage returns NO_VERDICT. The
    guard is not enforced HERE on purpose — `taxi_mlops.training.run` already
    refuses a sampled run that asks for a verdict, in the one place that owns that
    rule, and a second copy of it in an orchestrator wrapper is exactly the kind
    of duplicated law this program keeps deleting.
    """
    ingested = await ingest(month)
    rows = await validate(month, ingested)
    featured = await build_features(month, rows)
    manifest = await train(train_months, judge, featured)
    manifest = await evaluate(manifest)
    return await register(manifest)
