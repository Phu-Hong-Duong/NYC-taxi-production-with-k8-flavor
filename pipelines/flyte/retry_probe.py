"""retry_probe.py — a task that always fails, so the declared retry budget can be
seen being spent (M4-S5).

WHY THIS EXISTS, and it is a direct consequence of what the kill drill measured.
`pipelines/flyte/workflows.py` declares `retries=_STAGE_RETRIES` on every stage.
The kill-a-pod drill then deleted a running task pod and the pipeline finished —
but the control plane recorded **`attempts=0`** and the replacement pod came back
under the SAME name (`…-0`, a new UID). So what saved that run was the k8s
plugin RECREATING the pod for the same attempt, not the user retry budget. The
budget was declared, and nothing had ever shown it doing anything.

A number nobody has watched work is a number nobody should rely on — this program
has a whole rule about it ("a check wired to no sensor is a green light", M1). So
this module holds one task whose only job is to fail, and the probe asserts that
the platform ran it `_STAGE_RETRIES` extra times before giving up. That is the
positive statement: the budget is real, it is the number this repo declares, and
it is FINITE — the run ends in a failure rather than in an infinite retry loop,
which is the other half of why the number is small.

IT IS EXPECTED TO FAIL AND THE FAILURE IS THE RESULT. Nothing here touches data,
MLflow, the registry or Postgres; the task raises on its first line. The probe
that runs it (`scripts/pipeline_kill_drill.sh`, phase 0) inverts the exit code the
way `marts-redteam` and `image-smoke-redteam` do: a probe that SUCCEEDS means the
task did not fail, which means it measured nothing.

    uv run flyte --endpoint localhost:8092 --insecure run \
        --project nyc-taxi --domain development \
        pipelines/flyte/retry_probe.py always_fails
"""

from __future__ import annotations

import flyte

from pipelines.flyte.workflows import _ENV_VARS, _IMAGE, _STAGE_RETRIES

# The SAME image, the SAME pod template and the SAME retry budget as the real
# stages — imported, never restated. A probe that declared its own `retries=2`
# would prove that a task with retries=2 is retried twice, which is not the
# question; the question is whether the number workflows.py declares is the number
# the platform honours.
probe_env = flyte.TaskEnvironment(
    name="taxi-pipeline-retry-probe",
    image=_IMAGE,
    resources=flyte.Resources(cpu=(1, 1), memory=("512Mi", "1Gi")),
    pod_template="flyte-task-defaults",
    env_vars=_ENV_VARS,
)


@probe_env.task(cache="disable", retries=_STAGE_RETRIES)
async def always_fails() -> str:
    """Raise. That is the whole task.

    Uncached deliberately: a cached failure is a contradiction, and the probe has
    to re-run whenever it is asked. The exception is an ordinary `RuntimeError` and
    NOT `flyte.errors.NonRecoverableError` — that one is the SDK's explicit opt-out
    from retrying ("this failure is terminal"), and using it here would make the
    probe measure the opt-out instead of the budget.
    """
    raise RuntimeError(
        "retry-probe: failing on purpose so the declared retry budget can be "
        "observed being spent. If you are reading this in a pipeline run, "
        "something imported the wrong module."
    )
