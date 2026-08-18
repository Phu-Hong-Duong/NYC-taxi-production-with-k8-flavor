# D-001 — how our images reach the kind nodes

**Decided 2026-08-18 · story M4-S3 · role:MLOps (EXECUTOR, claude-opus-5) · debt row D-001**
**Decision: `kind load docker-image` at M4. The local-registry pattern is the better
end-state and lands at the next PO-sanctioned cluster rebuild, not before.**

This is a dated decision note, not an ADR: it changes no architecture chosen in
ADR-001/002 and it decides a mechanism inside one milestone. The debt row asked
for exactly this — "a RECORDED decision (with the honest costs of each) before
the first image must reach a node".

---

## The two options, as the kind docs frame them

| | **A. `kind load docker-image`** | **B. local registry (`containerdConfigPatches`)** |
|---|---|---|
| Mechanism | build on the host daemon, then stream the image into each node's containerd store | run a registry container on the kind network, patch each node's containerd to trust it, `docker push`, pods pull |
| Where the config lives | nowhere — a command | `infra/kind/kind-config.yaml`, i.e. **cluster-create time** |
| Cost per image | one transfer **per node** (3 here) | one push, then pulls |
| Cost to adopt now | zero | **a cluster rebuild** |
| Multi-node correctness | every node must be loaded; `kind load` does all of them and this repo reads back with `crictl` | one push serves all nodes |
| Failure mode when it drifts | a node quietly holds older bytes under the same tag | a registry outage stops every pull |

## Why A, and the one fact that decides it

The kind config is read **only** at `kind create cluster`. Adding
`containerdConfigPatches` therefore means `kind delete` + `kind create` — and
since M2 this cluster is **stateful**. Its PVCs hold the only copies of:

- the MLflow model registry (`nyc-taxi-eta` versions 1 and 2, `@champion` → 2),
- every artifact those versions point at, in MinIO,
- the Metabase app-db (both boards, 28 cards),
- both M3 Optuna studies,
- the `marts` warehouse `verify-m2` reconciles against.

`make verify-m2` (55 sub-checks) and `make verify-m3` (46) read that state live.
A rebuild turns both permanently red, and no amount of re-running gets version 1
back: the run that produced it is gone with the tracking database. The M4 kickoff
states the law in one line ("the cluster is stateful; a rebuild destroys the
registry"), and it is the same law that left Flyte's port 8080 RESERVED rather
than declared at M4-S2.

So option B is not rejected on merit. It is **unavailable at a price this
milestone is allowed to pay**, and choosing A costs us a per-node transfer of a
~2.6 GiB image measured in seconds. That is the whole trade.

## What A obliges us to do, and where each obligation is discharged

`kind load` has a real, documented sharp edge (gotcha #3): it is a manual step
that is easy to forget, and forgetting it produces a pod that runs *last build's
code* with no error anywhere. Three things in this story make forgetting
detectable rather than silent:

1. **The tag is the git short SHA**, `-dirty`-suffixed when the tree is not
   clean (`scripts/image_build_load.sh`). A mutable tag (`:latest`, `:dev`) is
   what makes "the node has stale bytes under the right name" possible at all;
   an immutable tag makes a stale node a *missing image* — a loud
   `ErrImageNeverPull`/`ImagePullBackOff` instead of a wrong number.
2. **The load is read back from the nodes with their own tool.** `kind load`
   exiting 0 says a transfer ran; `docker exec <node> crictl images` says what
   containerd will hand a pod. The script prints each node's image ID **before
   and after**, so an idempotent re-load is visible as *unchanged* rather than
   asserted.
3. **The image is proven to run our code, not just to exist** — `make
   image-smoke`, eight checks inside the container, including one real
   `pipelines/tasks.py` stage over real pinned data.

## When B should land

At the next **PO-sanctioned rebuild** — the same event that owes the port family
Flyte's declared 8080 route (M4-S2's recorded deviation) and, if M5 wants it, an
ingress hostPort. Bundling all config-time changes into one sanctioned rebuild is
strictly cheaper than three, and every one of them is currently blocked by the
same law. The trigger to prefer B by then: **image churn**. `kind load` costs one
transfer × three nodes per build; the moment the pipeline image is rebuilt many
times in a session (M5's serving image plus a transformer, or M7's retrain loop),
the registry pattern stops being a nicety.

Nothing about A leaks into the pipeline code: `pipelines/flyte/workflows.py`
(M4-S4) references an image by `name:tag`, which is the same string under either
mechanism. Switching later is a kind-config change plus a push, not a rewrite.

## Consequence recorded for M4-S4

Flyte task pods must not try to pull from a registry that does not exist. With
`kind load` the image is present on every node, so the task's
`imagePullPolicy` must be `IfNotPresent` (kubernetes' default for a
non-`:latest` tag — which the SHA tag guarantees) or `Never`. If M4-S4 sees
`ImagePullBackOff` on `taxi-mlops-pipeline:<sha>`, the answer is almost always
"the tag moved because the tree moved" → re-run `make image-load`; the manifest
at `automation/runs/m4-image/image.json` records which ref is actually on the
nodes.
