# The task image (M4-S3) — what it contains, how it reaches the nodes, and how D-004 was proven dead

**Story M4-S3 · 2026-08-18 · EXECUTOR (claude-opus-5), role:MLOps**
Artifacts: `docker/Dockerfile.pipeline` · `.dockerignore` ·
`scripts/image_build_load.sh` · `scripts/image_smoke.sh` ·
`scripts/image_smoke_redteam.sh` · `docker/DECISION-D001-image-delivery.md` ·
`tests/unit/test_task_image.py`.
Commands: `make image-build` · `make image-load` · `make image-smoke` ·
`make image-smoke-redteam`.

---

## 1. What the image is

| | |
|---|---|
| Reference | `taxi-mlops-pipeline:<git-short-sha>` (`-dirty` when the tree is not clean) |
| Base | `python:3.12.14-slim-trixie@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a` — tag **and** digest |
| Interpreter | CPython **3.12.14** (`[GCC 14.2.0]`) — the project's version; see §6 for the honest non-identity |
| Resolver | uv **0.12.5**, copied from `ghcr.io/astral-sh/uv:0.12.5@sha256:e85be844…`, the same version that resolved `uv.lock` |
| Graph | `uv sync --frozen` — **215 packages, every version identical to the host venv's** (checked, §3 check 5) |
| OpenMP | `libgomp1` **14.2.0-19**, a real apt package (D-004) |
| User | non-root `taxi`, uid 1000 |
| Size | **737 MiB** stored/transferred · **~1,898 MB** of layers unpacked on a node |
| Nodes | all 3 (`kind load`, read back with `crictl`) |

Two sizes are quoted because they answer different questions, and quoting one as
"the size" is how a duplicated layer stays invisible — see §5.

## 2. D-001 — how it reaches the nodes

`kind load docker-image`, decided and argued in
[`docker/DECISION-D001-image-delivery.md`](../docker/DECISION-D001-image-delivery.md).
Short version: the local-registry pattern needs `containerdConfigPatches` in the
kind config, the kind config is read only at cluster-create, and this cluster is
stateful — a rebuild destroys the MLflow registry that `verify-m2`/`verify-m3`
read. The registry pattern is the better end-state and lands at the next
PO-sanctioned rebuild, with **image churn** as the trigger that makes it worth it.

The load, read back from the nodes with their own tool:

```
-- load onto 3 node(s) ------------------------------
Image: "taxi-mlops-pipeline:…" with ID "sha256:…" not yet present on node "mlops-taxi-worker2", loading...
Image: "taxi-mlops-pipeline:…" with ID "sha256:…" not yet present on node "mlops-taxi-control-plane", loading...
Image: "taxi-mlops-pipeline:…" with ID "sha256:…" not yet present on node "mlops-taxi-worker", loading...
  loaded in 26s

-- read-back (crictl on each node) -----------------------------
  ok    mlops-taxi-worker2: sha256:eb6feb2c08ee…
  ok    mlops-taxi-control-plane: sha256:eb6feb2c08ee…
  ok    mlops-taxi-worker: sha256:eb6feb2c08ee…
```

Read `kind load`'s exit code and `crictl images` as two different claims: the
first says a transfer ran, the second says what containerd will hand a pod. The
script prints each node's id **before and after**, so an idempotent re-load shows
up as `(unchanged — idempotent re-load)` rather than being asserted.

Idempotence, from the second run of the same command on the same tree:

```
  ok    mlops-taxi-worker2: sha256:65c9b2b49163…  (unchanged — idempotent re-load)
  ok    mlops-taxi-control-plane: sha256:65c9b2b49163…  (unchanged — idempotent re-load)
  ok    mlops-taxi-worker: sha256:65c9b2b49163…  (unchanged — idempotent re-load)
```

One thing to know before comparing numbers: **the id containerd prints is not the
id docker prints.** Docker names a BuildKit build by its manifest-list digest;
containerd names the image by its config digest. Both are in
`automation/runs/m4-image/image.json` (`image_id` and `containerd_image_id`).

And the distinction is load-bearing, not pedantry — observed across the two runs
above: **docker's manifest-list digest changed** (`bf82ba68…` → `3e5066b4…`) for a
byte-identical tree, because BuildKit's provenance attestation carries build
metadata, **while containerd's config digest stayed `65c9b2b49163…` on all three
nodes.** An idempotence check written against docker's id would have reported a
change on every rebuild and meant nothing by it. This is why the comparison is
node-id against node-id.

## 3. D-004 — the shim proven dead, with the transcript

`make image-smoke` — 10 checks, all inside the container, nothing inferred from
the Dockerfile:

```
== task image smoke ============================================
  image : taxi-mlops-pipeline:<sha>

-- 1. libgomp1 is a real apt package inside the image (D-004)
     libgomp1 14.2.0-19 install ok installed
ok    libgomp1 installed by dpkg: libgomp1 14.2.0-19
     	libgomp.so.1 (libc6,x86-64) => /lib/x86_64-linux-gnu/libgomp.so.1
ok    the loader resolves libgomp.so.1 from a system lib dir — not from a wheel

-- 2. openmp_status() is (True, 'system libgomp.so.1') on the FIRST line
     (True, 'system libgomp.so.1')
ok    openmp_status() -> (True, 'system libgomp.so.1') (first line, nothing printed before it)

-- 3. ensure_openmp() takes the system path and announces NOTHING
     openmp: system libgomp.so.1
ok    ensure_openmp() -> openmp: system libgomp.so.1
ok    no '[openmp]' announcement anywhere in the output — the shim never ran

-- 4. the OpenMP consumers import clean, and the interpreter is recorded
     python: 3.12.14 (main, Aug 13 2026, 19:41:13) [GCC 14.2.0]
     lightgbm: 4.7.0
     xgboost: 3.4.1
     flaml: 2.6.0
     pandas: 3.0.5
     sklearn: 1.9.0
     pyarrow: 25.0.1
     mlflow: 3.15.1
     flyte SDK: importable
ok    lightgbm, xgboost, flaml, pandas, sklearn, pyarrow, mlflow, flyte imported with no shim line

-- 5. the installed dependency graph equals the host venv's (uv.lock, --frozen)
     215 host / 215 image packages; 0 disagreement(s)
ok    every package version in the image matches the host venv

-- 6. the unit suite runs INSIDE the image
     471 passed, 6 skipped in 42.70s
ok    tests/unit green in-image

-- 7. pipelines/tasks.py validate() runs in-image over real pinned data
     validate: 2019-01 7584656 rows, contract_year 2019 , 20 columns
ok    validate(2019-01) passed the output contract inside the image

-- 8. the shim's directory does not exist in the image
     absent: /app/.venv/lib/openmp
     vendored copies still shipped by wheels (harmless, unused):
     /app/.venv/lib/python3.12/site-packages/xgboost.libs/libgomp-e985bcbb.so.1.0.0
     /app/.venv/lib/python3.12/site-packages/scikit_learn.libs/libgomp-e985bcbb.so.1.0.0
ok    no shim directory and no libgomp.so.1 SONAME inside the venv

== verdict =====================================================
  10 ok · 0 FAIL
GREEN — 10/10 checks passed for taxi-mlops-pipeline:<sha>
```

Two observations worth pulling out.

**Check 7 is the one that proves the image can run OUR code, not just import our
imports.** `validate` re-reads a real month's parquet and puts 7,584,656 rows back
through the output contract — the same `contract.validate_output` ingest uses. It
runs against the host's DVC-pinned tree, bind-mounted **read-only**, because the
image must not contain data: data is DVC's to pin, and a copy in a layer would be
a second unpinned definition of the dataset. That mount is **not** the answer to
how data reaches tasks on-cluster — that is M4-S4's decision (MinIO or a staged
PVC), and `kind extraMounts` is not available for the same reason the registry
pattern is not.

**Check 8's evidence is negative, and it has to be.** Both wheels still ship a
vendored `libgomp` (xgboost's and scikit-learn's, byte-identical hashes); the shim
would borrow one. What proves it does not is that
`.venv/lib/openmp` does not exist and no file inside the venv carries the
`libgomp.so.1` SONAME. A check on a thing NOT happening is the only shape that can
retire this debt, because the shim WORKS — a debt that keeps working is a debt
that quietly never closes.

## 4. The sensor drill — `make image-smoke-redteam`

Negative evidence is worthless unless you can make it flip. So the drill
bind-mounts an **empty file** over `/lib/x86_64-linux-gnu/libgomp.so.1` in ONE
`--rm` container. Nothing else is touched: not the image, not the nodes, not the
cluster. Inside that container the world looks exactly as it looks on this WSL
host, which is the state D-004 exists because of.

```
== D-004 sensor red team =======================================
-- baseline: the image itself is NOT modified by this drill ------
     unmasked: (True, 'system libgomp.so.1')
ok    unmasked container still reports the system library

-- 1. openmp_status() must stop saying 'system' ------------------
     (False, 'not loadable yet; a vendored copy exists at /app/.venv/lib/python3.12/site-packages/scikit_learn.libs/libgomp-e985bcbb.so.1.0.0')
ok    check 2 flipped: the probe now reports the system library unusable

-- 2. ensure_openmp() must ANNOUNCE the shim --------------------
     [openmp] no system libgomp.so.1; linked libgomp-e985bcbb.so.1.0.0 -> /app/.venv/lib/openmp/libgomp.so.1 and re-executing once with LD_LIBRARY_PATH set
ok    check 3 flipped: the shim fired and said so on stdout

-- 4. the shim must leave the directory check 8 looks for -------
     PRESENT: /app/.venv/lib/openmp
     lrwxrwxrwx 1 taxi taxi 83 … libgomp.so.1 -> …/scikit_learn.libs/libgomp-e985bcbb.so.1.0.0
ok    check 8 flipped: the shim created /app/.venv/lib/openmp

-- 5. F-024: the `-c` form must REFUSE, not exec a broken argv ---
ok    the -c path raises OpenMPUnavailableError naming the situation (F-024 fixed)

-- 6. and the image on disk is unchanged ------------------------
     a fresh container from the same image: absent
ok    the drill left no trace in the image — every mutation lived in one --rm container
```

Its exit code is inverted the way `make marts-redteam` inverts dbt's: a check that
**stayed green** under the mask is a check that measures nothing, and the script
fails saying so.

## 5. Three things that went wrong, and what each one cost

**(a) `chown -R` duplicated the entire venv — 1.7 GB, 139 s.** The first
Dockerfile built as root and ran `chown -R taxi:taxi /app` at the end, which is
the ordering every tutorial shows. `docker history` showed the chown as a
**1.7 GB layer**: a layer stores a whole file to record new metadata, so chowning
a venv copies it. Creating the user *before* installing anything makes the same
image without the copy — **1408 MiB → 736 MiB** content, and 139 s off the build.
Found only because the script prints two sizes; the single number `docker image
inspect` gives would have hidden it.

**(b) `.dockerignore` excluded 1.1 MB of committed lookup tables, and the in-image
unit suite is what said so.** The first draft excluded `data/` wholesale — correct
for the 2.0 GB DVC-pinned trees, wrong for `data/reference/`, which is committed
and is the lookup layer `taxi_mlops.features` reads (zone centroids, TLC zone
lookup, the pinned `taxi_zones.zip`, the federal-holiday table). Result: an image
that imports perfectly and cannot build a feature — **28 failed, 10 errors**
in-image against 452 passed. The same draft's `.env.*` glob ate the committed
`.env.example` template, taking `test_marts.py` with it. The rule now written at
the top of `.dockerignore`: **the image contains what git contains**, and
`tests/unit/test_task_image.py` asserts it both ways.

Worth noting what caught it: not a review, not a reading of the Dockerfile, but
**running the project's own tests inside the artifact**. Check 6 is the reason
this story shipped a working image rather than a plausible one.

**(c) Two verifier bugs, both of the gotcha #55 family.** Check 1 wrapped
`dpkg-query -f="${Package} …"` in an inner `bash -lc`, so the *inner* bash expanded
`${Package}` to empty and the check reported blanks as the image's fault; and a
bare `ldconfig` is `command not found` for a non-root user because `/sbin` is not
on uid 1000's PATH. Then the fixed version asserted the library resolves under
`/usr/lib`, which is red on a correct Debian image because `/lib` is a symlink to
`/usr/lib` and ldconfig prints the former. Three wrong reds in a row about a
correct artifact — and the tell each time was that checks 2, 3 and 8, which
measure *behaviour*, were green throughout.

## 6. The honest non-identity, stated rather than hidden

The host's 3.12.14 is uv-managed python-build-standalone, built with **Clang
22.1.3**; the image's is Debian's, built with **GCC 14.2.0**. Same CPython
version, different compiler. What determines this program's numbers is the
dependency graph, and check 5 proves that graph is identical package-for-package
(215/215) — every numerically interesting package arrives as the same prebuilt
cp312 manylinux wheel in both places. The smoke prints `sys.version` so the
difference stays a recorded fact.

Also stated, not fought: **`nvidia-nccl-cu13` is 241 MB of the image** and is a
hard dependency of `xgboost` 3.4.1 on linux. There is no GPU here and it is never
loaded. Image slimming is explicitly out of M4's scope; the number is written down
so the next person does not rediscover it as a surprise.

## 7. F-024 — the shim cannot re-exec a `python -c` invocation

Found by §4's drill and **reproduced on the host**, so it is not a container
artefact: it has been true since M2-S2.

Under `python -c "<code>"` CPython sets `sys.argv[0]` to the literal `"-c"` and
keeps the source string nowhere reachable. `_relaunch_argv()` therefore handed
`execv` a bare `python -c`, and the interpreter answered `Argument expected for
the -c option` — a message about argument parsing for a problem about a shared
library. The failure mode is worse than the error: the shim had already printed
that it linked the library and was re-executing, so the visible story was "the
shim worked", followed by an unrelated usage message.

Fixed by **refusing** that form before anything is mutated, with a message naming
the three ways out (`python -m`, a `.py` file, or `sudo apt install libgomp1`),
plus `src/taxi_mlops/training/openmp_probe.py` — a `-m`-runnable probe that takes
the same path a real task takes, which is what the smoke and the drill both use.
Blast radius of the original bug: ad-hoc probes only. Every real entry point in
this program is `python -m taxi_mlops…` or a script file, and both forms
reconstruct correctly (pinned by tests since M2-S2).

## 8. What M4-S4 inherits

- An image on all three nodes, referenced by an immutable tag; the current ref is
  in `automation/runs/m4-image/image.json`.
- `imagePullPolicy` must be `IfNotPresent` (kubernetes' default for a non-`:latest`
  tag) or `Never`. `ImagePullBackOff` on `taxi-mlops-pipeline:<sha>` almost always
  means the tree moved and the tag with it → re-run `make image-load`.
- The image contains `pipelines/`, `src/`, `configs/`, `analytics/` and
  `data/reference/`. It contains **no** trip data and no `.env`; credentials and
  data paths are the workflow's to supply.
- `make image-smoke` is the D-004 leg `verify-m4` should call (M4-S5's kickoff item
  says so); `make image-smoke-redteam` is what keeps that leg honest.
