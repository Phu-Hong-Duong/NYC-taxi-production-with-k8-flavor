"""hello.py — the smallest thing that proves the orchestrator actually runs work.

M4-S2's acceptance leg: "ONE hello-workflow runs remotely to completion". It is
deliberately NOT a slice of the real pipeline — `pipelines/tasks.py` already
holds the six real stages as plain Python (M4-S1), and wrapping them in Flyte
task/workflow definitions is M4-S4's job. What this file tests is the SEAM:
does a task defined on this host get accepted by the control plane, scheduled
onto a kind node, run, and hand its output back?

Two tasks, not one, on purpose. A single task proves a pod ran; a task that
consumes another's output proves the piece M4-S4 depends on — that Flyte moved a
value between two pods through the MinIO blob store this story just configured.
If `flyte-data` were misconfigured, `hello` alone would still pass.

`src/taxi_mlops` is NOT imported here and must never be: BLUEPRINT's convention
is that `pipelines/` imports `src/`, never the reverse, and `src/` never imports
an orchestrator. This file imports neither — it is orchestrator-only.

Run it:  make flyte-hello   (see scripts/flyte_hello.sh for the endpoint wiring)
"""

from __future__ import annotations

import flyte

# The image is the one M4-S3 will replace with the real task image (D-001 decides
# how it reaches the nodes). Until then this environment names an image that is
# already ON the nodes, because a hello-run that first has to solve image
# distribution is not testing the seam it claims to test.
env = flyte.TaskEnvironment(
    name="hello",
    image=flyte.Image.from_debian_base(),
    resources=flyte.Resources(cpu="100m", memory="256Mi"),
)


@env.task
async def greet(name: str) -> str:
    """The pod-ran-at-all half."""
    return f"hello {name} from a flyte task"


@env.task
async def shout(message: str) -> str:
    """The output-crossed-the-blob-store half: its input is the task above's output."""
    return message.upper()


@env.task
async def main(name: str = "crosstown") -> str:
    return await shout(await greet(name))
