#!/usr/bin/env bash
# verify_m4.sh — the M4 gate, executable. BLUEPRINT §9/M4, quoted:
#
#   "M4 — Pipeline on-cluster (Flyte) (MLOps A; MLE R). v1's M3 unchanged:
#    Flyte 2 per docs, containerized, ingest->validate->features->train->
#    evaluate->register parametrized by month; cache-hit rerun; kill-a-pod
#    retry; wall rule -> ADR-002 fallback. Accept/Show: as v1 M3."
#
# ...plus D-003's tail task (§9/M1-S6: "From M4 the build+publish runs as the
# tail task of the monthly Flyte pipeline"), which landed at M4-S5 leg 2.
#
# The design rules are M2-S5's and M3-S5's, inherited whole:
#   * every check observes the THING, never a proxy;
#   * every Python leg must EMIT a minimum number of verdicts, so a leg that
#     dies on import FAILS instead of contributing zero silent passes;
#   * PROPERTIES, NOT LITERALS (F-017, gotchas #49/#50) — pin no run id, no
#     stage count typed by hand, no image tag, no champion version. Every
#     number this gate compares is derived from code on disk or from a record
#     the program wrote, on both sides of the comparison.
#   * no skip flag, no fast mode. M1's rule, inherited a third time.
#
# RE-FITS NOTHING, AND RE-RUNS NOTHING. M4 cost about 95 minutes of on-cluster
# fitting across the full-data run, the cache drill's two runs, the kill drill
# and the marts run. A gate that re-ran any of it would cost more than the
# milestone and would mint MLflow runs on every verification — which is exactly
# the signal §4's strongest leg reads. So this gate reads: the records the
# drills wrote, the code that produced them, the live cluster, the live
# registry, the live warehouse. Wall clock is seconds.
#
# WHY THE CACHE LEG READS A RECORD AND NOT THE LATEST RUN (gotcha #66). The
# Flyte cache key covers the whole task spec, and the task image is tagged with
# the git short sha — so ONE commit under src/scripts/analytics/docker/
# pyproject.toml/uv.lock mints a new image and every stage comes back
# CACHE_POPULATED instead of CACHE_HIT. That is correct behaviour. A gate that
# re-asked the control plane about the newest run would therefore go RED for a
# commit, which is #50's disease exactly. The drill's record is the evidence;
# `make pipeline-cache-drill` is what refreshes it.
#
# THE RECORDS ARE COMMITTED, AND THEY WERE NOT WHEN THIS GATE WAS WRITTEN
# (F-029, closed at M5-S1). This header used to carry an honest limit instead:
# `automation/runs/` was gitignored, so every record §3-§6 reads was MACHINE
# state — present on this laptop, absent in a fresh clone, and, worse, editable
# with no diff for a reviewer to see, which is precisely the fault
# `verify_m4_redteam.sh` plants on purpose. ARCH decided the fork at the M4
# boundary (2026-08-19, option A) and M5-S1 landed the mechanics: the verdict
# JSONs under `automation/runs/**` are TRACKED; the logs and `.status` files
# stay ignored, because they are transcripts and no gate reads them. So a fresh
# clone can run §3-§6 against the same bytes this machine ran them against, and
# a tampered record shows up in `git status`. Each leg still names the file it
# read — that part was never the problem.
#
# Prints one line per sub-check and exits nonzero if ANY fails — it keeps going
# rather than stopping at the first, so one run tells you everything broken.
#
# Usage: scripts/verify_m4.sh          (via `make verify-m4`)
#        scripts/verify_m4_redteam.sh  proves this gate can go RED
set -uo pipefail   # deliberately NOT -e: a failing check must be counted, not fatal

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
CONTEXT="${KUBE_CONTEXT:-kind-mlops-taxi}"
KUBECTL=(kubectl --context "$CONTEXT")

# The counting harness — the two counters, the four printers, `consume` and
# `expect_verdicts` — lives in ONE place from CU-S3 on. `consume` must still be
# called as `consume < <(...)` and never through a pipe; the reason, and what
# deliberately did NOT move (this gate's legs, its verdict block), are in the
# lib's own header.
# shellcheck source=lib/verify_harness.sh
source "$REPO_ROOT/scripts/lib/verify_harness.sh"

printf '\n\033[1m[verify-m4]\033[0m the M4 gate — the control plane, the image, the green run,\n'
printf '            the cache, the kill drill, the marts tail, and the alias that\n'
printf '            no M4 run may move. It re-reads and re-checks; it re-runs NOTHING.\n'

# ------------------------------- 1. the platform a task pod actually needs ----
section "1. the control plane, and the four things a task pod cannot start without"

if bash scripts/flyte_console.sh --check >/tmp/verify-m4-flyte.log 2>&1; then
  pass "$(sed -n 's/^\[flyte-console\] ok  //p' /tmp/verify-m4-flyte.log | head -1)"
else
  fail "the Flyte control plane did not answer /healthz — $(tail -1 /tmp/verify-m4-flyte.log)"
fi

consume < <(
  # Deployments first: `helm list` says "deployed" about a release whose pods
  # are all crash-looping, so the thing observed is the availability count.
  want_pods=0
  for deploy in $("${KUBECTL[@]}" -n flyte get deploy -o name 2>/dev/null); do
    want_pods=$((want_pods + 1))
    ready="$("${KUBECTL[@]}" -n flyte get "$deploy" -o jsonpath='{.status.availableReplicas}' 2>/dev/null)"
    if [[ "${ready:-0}" -ge 1 ]]; then
      echo "PASS|${deploy#deployment.apps/} has ${ready} available replica(s)"
    else
      echo "FAIL|${deploy#deployment.apps/} has no available replica — the control plane is not serving"
    fi
  done
  [[ "$want_pods" -eq 0 ]] && echo "FAIL|namespace flyte holds NO deployment — Flyte is not installed"

  # The PodTemplate is the file that says "what a task pod in this program looks
  # like". Checked in-cluster, not on disk: the manifest is only a claim until it
  # is applied, and a task added at M7 inherits the applied one.
  tmpl_name="$(uv run python - <<'PY' 2>/dev/null
import re, pathlib
text = pathlib.Path("infra/manifests/flyte-task-podtemplate.yaml").read_text()
m = re.search(r"^metadata:\s*$\s+name:\s*(\S+)", text, re.M)
print(m.group(1) if m else "")
PY
)"
  if [[ -z "$tmpl_name" ]]; then
    echo "FAIL|could not read the PodTemplate's name out of infra/manifests/flyte-task-podtemplate.yaml"
  elif container="$("${KUBECTL[@]}" -n flyte get podtemplate "$tmpl_name" \
        -o jsonpath='{.template.spec.containers[0].name}' 2>/dev/null)" && [[ -n "$container" ]]; then
    if [[ "$container" == "default" ]]; then
      echo "PASS|PodTemplate ${tmpl_name} is applied in-cluster and its container is named 'default' (the k8s plugin's contract)"
    else
      echo "FAIL|PodTemplate ${tmpl_name} names its container '${container}', not 'default' — the plugin will not match it"
    fi
  else
    echo "FAIL|PodTemplate ${tmpl_name} is NOT applied in the cluster — every task pod would run without the data volume, the MinIO identity and the MLflow route"
  fi

  # ...and the volume it mounts. A Bound PVC with the staged trees on it is what
  # makes a task able to read 1.8 GB the cluster cannot otherwise see.
  claim="$("${KUBECTL[@]}" -n flyte get podtemplate "$tmpl_name" \
    -o jsonpath='{.template.spec.volumes[?(@.persistentVolumeClaim)].persistentVolumeClaim.claimName}' 2>/dev/null)"
  if [[ -z "$claim" ]]; then
    echo "FAIL|the PodTemplate mounts no PersistentVolumeClaim — the staged data would be invisible to every stage"
  else
    phase="$("${KUBECTL[@]}" -n flyte get pvc "$claim" -o jsonpath='{.status.phase}' 2>/dev/null)"
    if [[ "$phase" == "Bound" ]]; then
      echo "PASS|the data volume the template mounts (pvc/${claim}) is ${phase}"
    else
      echo "FAIL|pvc/${claim} is '${phase:-absent}', not Bound — make stage-data"
    fi
  fi

  # The two systems every stage talks to, observed as pods rather than as config.
  for pair in mlflow/mlflow platform/postgres platform/minio; do
    ns="${pair%%/*}"; app="${pair##*/}"
    running="$("${KUBECTL[@]}" -n "$ns" get pods --no-headers 2>/dev/null | grep -c "^${app}.*Running")"
    if [[ "${running:-0}" -ge 1 ]]; then
      echo "PASS|${ns}/${app}: ${running} pod(s) Running — the stages have somewhere to log and something to read"
    else
      echo "FAIL|${ns}/${app} has no Running pod"
    fi
  done
)
expect_verdicts 8 "the control-plane check"

# ------------------------------------- 2. the image, and D-004 inside it ------
section "2. the image the stages run in — reachable on every node, and D-004 still dead"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
import subprocess
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

MANIFEST = Path("automation/runs/m4-image/image.json")
try:
    if not MANIFEST.exists():
        raise SystemExit(no(f"{MANIFEST} is missing — run `make image-load`"))
    rec = json.loads(MANIFEST.read_text())
    ref, tag = rec["image_ref"], rec["tag"]

    # M4-S3's correctness property, asserted rather than remembered: k8s pulls
    # IfNotPresent for any non-`:latest` tag and `kind load` writes into
    # containerd BY TAG, so a mutable tag gives you nodes holding last week's
    # bytes under this week's name. `-dirty` says the image carries uncommitted
    # work and must not back a verdict.
    if tag not in ("latest", "") and not ref.endswith(":latest"):
        ok(f"the task image is tagged {tag!r}, not ':latest' — a stale node is a "
           f"missing image (loud), never wrong bytes (silent)")
    else:
        no(f"the task image is tagged {tag!r} — a mutable tag cannot say which bytes ran")
    if rec.get("tree_dirty") is False:
        ok("the manifest records tree_dirty=false — the evidence below was produced "
           "by an image built from committed code")
    else:
        no("the recorded image was built from a DIRTY tree — it cannot back a verdict")

    # Read back off the nodes with the NODES' own tool, exactly as image-load
    # does. `docker images` on the host answers about the host.
    nodes = rec["nodes"]
    want_id = rec["containerd_image_id"].removeprefix("sha256:")[:12]
    holding, wrong = [], {}
    for node in nodes:
        out = subprocess.run(
            ["docker", "exec", node, "crictl", "images"],
            capture_output=True, text=True,
        ).stdout
        line = [ln for ln in out.splitlines()
                if rec["image_name"] in ln and f" {tag} " in f" {' '.join(ln.split())} "]
        if not line:
            wrong[node] = "absent"
            continue
        got = line[0].split()[2][:12]
        holding.append(node) if got.startswith(want_id) or want_id.startswith(got) else \
            wrong.update({node: got})
    if len(holding) == len(nodes) and nodes:
        ok(f"all {len(nodes)} node(s) hold {ref} at containerd id {want_id}… "
           f"(read with each node's own crictl)")
    else:
        no(f"node(s) do not hold {ref}: {wrong} — run `make image-load`")

    # D-004, in the container, on the manifest's own image. The debt closed on
    # NEGATIVE evidence (the shim never fires), which is the only shape that can
    # retire a workaround that works — so both halves are asserted here.
    probe = subprocess.run(
        ["docker", "run", "--rm", ref, "python", "-m", "taxi_mlops.training.openmp_probe"],
        capture_output=True, text=True,
    )
    if probe.returncode != 0:
        no(f"the D-004 probe could not run in {ref}: {probe.stderr.strip()[:200]}")
    else:
        lines = [ln for ln in probe.stdout.splitlines() if ln.strip()]
        first = lines[0] if lines else ""
        if first == "openmp: system libgomp.so.1":
            ok(f"in-container OpenMP is the SYSTEM package: {first!r} on the first line "
               f"(D-004's closure, re-observed)")
        else:
            no(f"the in-container probe's first line is {first!r}, not the system library")
        if not any("[openmp]" in ln for ln in lines):
            ok("no '[openmp]' announcement anywhere in the probe's output — the shim did "
               "not fire, which is the negative evidence the debt closed on")
        else:
            no("the shim ANNOUNCED itself inside the image — D-004 is not closed there")
except SystemExit:
    pass
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the image check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 5 "the image check"

# ------------------------ 3. the graph: every stage wrapped, every stage ran ---
section "3. the green run — the graph is whole, and every recorded stage SUCCEEDED"
consume < <(uv run python - 2>/dev/null <<'PY'
import ast
import json
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    import sys
    sys.path.insert(0, ".")
    from pipelines import tasks

    # The flyte task name and the tasks.py callable name differ (`ingest` wraps
    # `ingest_month`), and nothing declares the mapping — so DERIVE it: for each
    # decorated `async def` in workflows.py, find the `tasks.<X>` it calls. This
    # is also the check: a stage added to STAGES and never wrapped is a stage the
    # pipeline cannot run, and a wrapper calling nothing in tasks.py is a stage
    # whose body drifted out of the single home.
    tree = ast.parse(Path("pipelines/flyte/workflows.py").read_text())
    wrapped, uncached = {}, set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        is_task = any(
            isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
            and d.func.attr == "task" for d in node.decorator_list
        )
        if not is_task:
            continue
        for call in ast.walk(node):
            if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name) and call.func.value.id == "tasks"):
                wrapped[node.name] = call.func.attr
        for dec in node.decorator_list:
            for kw in getattr(dec, "keywords", []):
                if kw.arg == "cache" and isinstance(kw.value, ast.Constant) \
                        and kw.value.value == "disable":
                    uncached.add(node.name)

    stages = set(tasks.STAGES)
    covered = set(wrapped.values())
    if stages <= covered:
        ok(f"every one of the {len(stages)} stage(s) in tasks.STAGES is wrapped by a Flyte "
           f"task ({', '.join(f'{k}->{v}' for k, v in sorted(wrapped.items()))})")
    else:
        no(f"stage(s) {sorted(stages - covered)} are in tasks.STAGES and wrapped by NO Flyte "
           f"task — declared in the graph, unreachable on the cluster")

    flyte_name = {v: k for k, v in wrapped.items()}

    # The records. Every M4 run this repo kept wrote one; they are read as a set
    # so no run id is pinned and a new drill's record joins the evidence by
    # existing. `main` is the parent action, not a stage.
    records = {}
    for path in sorted(Path("automation/runs").glob("m4-*/*.json")):
        try:
            blob = json.loads(path.read_text())
        except Exception:  # noqa: BLE001
            continue
        for key, value in ([("", blob)] if "actions" in blob else
                           [(k, v) for k, v in blob.items()
                            if isinstance(v, dict) and "actions" in v]):
            name = value.get("name") or value.get("run_name") or f"{path}:{key}"
            records[name] = (path, value["actions"])

    # A PIPELINE run is one that ran at least one stage of this graph. Derived,
    # not matched on a name: `pipelines/flyte/retry_probe.py` is a run record too
    # (§5 reads it, and it is SUPPOSED to have failed with no parent), and the
    # first draft of this leg swept it into "every run has a main" and went red
    # for a probe behaving exactly as designed — #50 caught in its own gate.
    stage_actions = set(flyte_name.values()) | {"main"}
    probes = {n for n, (_, actions) in records.items()
              if not any(a["short_name"] in stage_actions for a in actions)}
    for name in probes:
        records.pop(name)
    if probes:
        print(f"       {len(probes)} record(s) are single-task probes, not pipeline runs "
              f"({', '.join(sorted(probes))}) — read by section 5, excluded here")
    if len(records) >= 3:
        ok(f"{len(records)} recorded on-cluster run(s) to read, across "
           f"{len({p for p, _ in records.values()})} record file(s)")
    else:
        no(f"only {len(records)} recorded run(s) found under automation/runs/m4-* — "
           f"the drills have not been run on this machine (see this script's header)")

    # A run whose stages did not all succeed is not evidence of a green run.
    bad = {
        name: [a["short_name"] or "main" for a in actions if a["phase"] != "SUCCEEDED"]
        for name, (_, actions) in records.items()
        if any(a["phase"] != "SUCCEEDED" for a in actions)
    }
    if records and not bad:
        total = sum(len(a) for _, a in records.values())
        ok(f"every action of every recorded run SUCCEEDED ({total} action(s) across "
           f"{len(records)} run(s))")
    else:
        no(f"run(s) carry non-SUCCEEDED actions: {bad}")

    # ...and at least one run must have executed the WHOLE graph. The drills run
    # with PUBLISH_MARTS=0, so a repo where only drills were run would pass the
    # check above while never having run the tail at all.
    whole = {
        name: path for name, (path, actions) in records.items()
        if {flyte_name.get(s, s) for s in stages} <= {a["short_name"] for a in actions}
    }
    if whole:
        ok(f"{len(whole)} recorded run(s) executed ALL {len(stages)} stages end to end "
           f"(e.g. {sorted(whole)[0]} in {sorted(whole.values())[0].parent.name}/)")
    else:
        no(f"NO recorded run covers all {len(stages)} stages — the full graph has not "
           f"been observed running on this machine")

    # The parent must be the one that ran them: an action set with no `main` is a
    # collection of stages, not a workflow.
    parentless = [n for n, (_, actions) in records.items()
                  if not any(a["short_name"] == "main" for a in actions)]
    if records and not parentless:
        ok("every recorded run has a `main` parent action — the stages ran as ONE "
           "workflow, not as seven launches")
    else:
        no(f"recorded run(s) {parentless} have no parent action")

    # Cross-system: the pipeline's runs must EXIST in MLflow. The control plane
    # saying a train stage SUCCEEDED and the tracking server holding no run for it
    # is precisely the shape a green transcript over a dead fit takes (gotcha #59).
    import mlflow
    from taxi_mlops.training import tracking
    from taxi_mlops.training.run import load_train_config

    cfg = load_train_config("configs/train.yaml")
    tracking.configure(cfg["mlflow"])
    client = mlflow.MlflowClient()
    where = tasks.DEFAULT_EXPERIMENT   # read from the source, never typed here
    exp = client.get_experiment_by_name(where)
    if exp is None:
        no(f"MLflow holds no {where!r} experiment — the stages logged nowhere")
    else:
        runs = client.search_runs([exp.experiment_id], max_results=50000)
        unfinished = [r.info.run_id[:8] for r in runs if r.info.status != "FINISHED"]
        if runs and not unfinished:
            ok(f"MLflow's {where!r} experiment holds {len(runs)} run(s), every one "
               f"FINISHED — the fits the control plane recorded really happened")
        elif not runs:
            no(f"the {where!r} experiment is EMPTY — no stage ever logged a fit")
        else:
            no(f"MLflow run(s) {unfinished} are not FINISHED — a stage died mid-log")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the graph check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 6 "the graph check"

# ------------------------------------------ 4. the cache, from the record -----
section "4. the cache-hit rerun — read from the drill's record, never re-asked (gotcha #66)"
consume < <(uv run python - 2>/dev/null <<'PY'
import ast
import json
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

RECORD = Path("automation/runs/m4-cache/cache_drill.json")
try:
    if not RECORD.exists():
        raise SystemExit(no(f"{RECORD} is missing — run `make pipeline-cache-drill`"))
    rec = json.loads(RECORD.read_text())
    run1 = {a["short_name"]: a for a in rec["run1"]["actions"]}
    run2 = {a["short_name"]: a for a in rec["run2"]["actions"]}

    # Which stages are ALLOWED to be uncached is read from the code, not typed
    # here. A stage that quietly starts declaring cache="disable" must turn this
    # leg red rather than be accommodated by a list somebody edits.
    tree = ast.parse(Path("pipelines/flyte/workflows.py").read_text())
    declared_uncached = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        for dec in node.decorator_list:
            for kw in getattr(dec, "keywords", []):
                if kw.arg == "cache" and isinstance(kw.value, ast.Constant) \
                        and kw.value.value == "disable":
                    declared_uncached.add(node.name)

    observed_disabled = {n for n, a in run2.items() if a["cache_status"] == "CACHE_DISABLED"}
    if observed_disabled and observed_disabled <= declared_uncached:
        ok(f"the {len(observed_disabled)} stage(s) the rerun re-executed unconditionally "
           f"({', '.join(sorted(observed_disabled))}) are exactly stages the code declares "
           f"cache='disable' — the record agrees with the source")
    else:
        no(f"stages CACHE_DISABLED in the record ({sorted(observed_disabled)}) are not a "
           f"subset of those declared uncached in workflows.py ({sorted(declared_uncached)})")

    cacheable2 = {n: a for n, a in run2.items() if n not in declared_uncached}
    missed = {n: a["cache_status"] for n, a in cacheable2.items() if a["cache_status"] != "CACHE_HIT"}
    if cacheable2 and not missed:
        ok(f"all {len(cacheable2)} cacheable stage(s) of run 2 read CACHE_HIT — the CLAIM, "
           f"made by the control plane, which the CLI does not render")
    else:
        no(f"cacheable stage(s) did not hit on the rerun: {missed}")

    populated = {n for n, a in run1.items()
                 if a["cache_status"] == "CACHE_POPULATED" and n not in declared_uncached}
    if populated >= set(cacheable2):
        ok(f"run 1 POPULATED all {len(populated)} of them first — a drill comparing two "
           f"reruns to each other could show a saving that was already there")
    else:
        no(f"run 1 did not populate {sorted(set(cacheable2) - populated)} — the saving in "
           f"run 2 was not bought by run 1")

    # The clock CORROBORATES and is deliberately the weakest leg: a faster second
    # run is equally consistent with a less busy machine. It is checked anyway,
    # because a CACHE_HIT that took as long as the fit would mean the status field
    # and the duration disagree — and then one of them is lying.
    slow = {n: (run1[n]["duration_ms"], a["duration_ms"])
            for n, a in cacheable2.items()
            if n in run1 and a["duration_ms"] > max(5000, run1[n]["duration_ms"] * 0.5)}
    if not slow:
        saved = sum(run1[n]["duration_ms"] for n in cacheable2 if n in run1) / 1000
        spent = sum(a["duration_ms"] for a in cacheable2.values()) / 1000
        ok(f"and the clock agrees: {saved:.1f} s of cacheable work in run 1 came back in "
           f"{spent:.1f} s in run 2 ({spent / saved:.2%})")
    else:
        no(f"stage(s) claim CACHE_HIT but cost run-1 time (run1_ms, run2_ms): {slow} — "
           f"the status field and the duration disagree")

    # MLflow is the STRONGEST leg and is said by a different server, in a
    # different database, by code that has never heard of Flyte: a re-executed
    # train stage MINTS a run, so an unchanged count across run 2 is the positive
    # statement that the fit did not happen twice.
    counts = rec["mlflow_runs"]
    before, after1, after2 = (int(counts["before"]), int(counts["after_run1"]),
                              int(counts["after_run2"]))
    if after1 > before and after2 == after1:
        ok(f"MLflow: {before} -> {after1} runs across run 1, {after1} -> {after2} across "
           f"run 2 — the fit ran once and was reused, said by a server that cannot see the cache")
    elif after2 != after1:
        no(f"MLflow gained {after2 - after1} run(s) during the CACHED rerun — a stage "
           f"reported CACHE_HIT and fitted anyway")
    else:
        no(f"MLflow gained nothing during run 1 ({before} -> {after1}) — run 1 executed "
           f"no fit, so run 2's saving proves nothing")

    # ...and the two systems must AGREE, which is a strictly stronger statement
    # than either of them passing alone. The control plane's cache_status and
    # MLflow's run count are independent witnesses to the same question — did the
    # fit run a second time? — so a record claiming a stage re-executed while the
    # tracking server minted nothing is a contradiction, and one of them is wrong.
    reexecuted = {n for n, a in cacheable2.items() if a["cache_status"] != "CACHE_HIT"}
    minted = after2 - after1
    if not reexecuted and minted == 0:
        ok("the two witnesses AGREE: the control plane says no cacheable stage re-executed "
           "and MLflow minted no run to contradict it")
    elif reexecuted and minted > 0:
        ok(f"the two witnesses agree: {sorted(reexecuted)} re-executed and MLflow gained "
           f"{minted} run(s) — consistent, though the rerun was not fully cached")
    else:
        no(f"the two witnesses CONTRADICT each other: the record says {sorted(reexecuted)} "
           f"re-executed on the rerun while MLflow minted {minted} run(s) — a fit either "
           f"logs or does not happen, so one of these records is wrong")
except SystemExit:
    pass
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the cache check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 6 "the cache check"

# ------------------------------- 5. losing a pod, and the budget it did not spend
section "5. kill-a-pod — the run survived it, and the retry budget is real AND finite"
consume < <(uv run python - 2>/dev/null <<'PY'
import ast
import json
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

RECORD = Path("automation/runs/m4-kill/kill_drill.json")
PROBE = Path("automation/runs/m4-kill/retry_probe.actions.json")
try:
    if not RECORD.exists():
        raise SystemExit(no(f"{RECORD} is missing — run `make pipeline-kill-drill`"))
    rec = json.loads(RECORD.read_text())
    actions = {a["short_name"]: a for a in rec["actions"]}
    target = rec["target_stage"]

    if rec.get("pipeline_exit") == 0 and all(a["phase"] == "SUCCEEDED" for a in rec["actions"]):
        ok(f"the run finished anyway: exit 0 and all {len(rec['actions'])} action(s) "
           f"SUCCEEDED after {target}'s pod was deleted mid-work")
    else:
        no(f"the killed run did not complete cleanly (exit {rec.get('pipeline_exit')})")

    # IDENTITY, NOT NAME. The k8s plugin recreates the pod under the SAME name
    # with a new UID, which is why the drill's first prediction was wrong and why
    # this assertion is the one that survived (a different pod object ran the
    # stage — true under either classification).
    killed_uid = rec.get("killed_pod_uid")
    replacement_uids = {p.get("uid") for p in rec.get("attempt_pods", [])}
    if killed_uid and replacement_uids and killed_uid not in replacement_uids:
        ok(f"a DIFFERENT pod object ran {target} to completion: killed uid "
           f"{killed_uid[:8]}… vs surviving {sorted(u[:8] for u in replacement_uids if u)} "
           f"— identity, not name")
    else:
        no(f"the surviving pod's uid is the killed pod's ({killed_uid}) — nothing was "
           f"actually recreated, so the drill proved nothing")

    # A cached stage runs in no pod at all, so there would have been nothing to
    # kill. The drill refuses to be green in that case; the gate re-checks it,
    # because a record is only evidence if the thing it describes happened.
    if actions.get(target, {}).get("cache_status") != "CACHE_HIT":
        ok(f"{target} genuinely EXECUTED in the drill (cache_status "
           f"{actions.get(target, {}).get('cache_status')}) — there was a pod to kill")
    else:
        no(f"{target} was a CACHE_HIT — it ran in no pod, and the kill hit nothing")

    # Pod recreation does NOT spend the retry budget, which is why the drill needs
    # a second, separate mechanism to show the budget is real.
    if rec.get("control_plane_attempts") == 1:
        ok("the control plane recorded the killed action at ONE attempt — pod "
           "recreation and the retry budget are two different mechanisms")
    else:
        no(f"the killed action recorded {rec.get('control_plane_attempts')} attempt(s) — "
           f"then the kill was survived by retries, not by recreation")

    # ...and the budget itself. Declared in the code, exhausted by a task that
    # always raises, and read back off the control plane — three places, one number.
    tree = ast.parse(Path("pipelines/flyte/workflows.py").read_text())
    declared = next(
        (n.value.value for n in ast.walk(tree)
         if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
         and any(getattr(t, "id", "") == "_STAGE_RETRIES" for t in n.targets)),
        None,
    )
    recorded = rec.get("retry_budget", {}).get("declared_in_workflows_py")
    if declared is not None and declared == recorded:
        ok(f"the retry budget the code declares (_STAGE_RETRIES={declared}) is the one the "
           f"drill recorded — the record describes THIS source, not a remembered number")
    else:
        no(f"workflows.py declares _STAGE_RETRIES={declared} and the drill recorded "
           f"{recorded} — the evidence is about a different budget")

    if not PROBE.exists():
        no(f"{PROBE} is missing — the budget was never observed being exhausted")
    else:
        probe = json.loads(PROBE.read_text())["actions"][0]
        if probe["phase"] == "FAILED" and declared is not None \
                and probe["attempts"] == declared + 1:
            ok(f"a task that always raises settled at attempt index {probe['attempts']} and "
               f"the run FAILED — the budget of {declared} is real AND finite (F-027's fix "
               f"is what makes this field readable at all)")
        else:
            no(f"the retry probe recorded phase {probe['phase']!r} at {probe['attempts']} "
               f"attempt(s) against a declared budget of {declared} — the budget is not "
               f"what the code says")
except SystemExit:
    pass
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the kill-drill check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 6 "the kill-drill check"

# ------------------------------------------- 6. the marts tail (D-003) --------
section "6. the marts tail task — it ran as stage 7, and the warehouse still reconciles"
consume < <(uv run python - 2>/dev/null <<'PY'
import json
import sys
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    sys.path.insert(0, ".")
    sys.path.insert(0, "scripts")
    from pipelines import tasks

    tail = tasks.STAGES[-1]
    if tail == "publish_marts":
        ok(f"{tail} is the LAST stage in tasks.STAGES — §9/M1-S6's 'tail task of the "
           f"monthly pipeline', landed")
    else:
        no(f"the last stage in tasks.STAGES is {tail!r} — the publish is not the tail")

    # It must have RUN, and it must have run uncached: its product is a mutation
    # of a Postgres the cache cannot see, so a hit would return "published,
    # 7.5M rows" in 0.1 s having published nothing — and would be right by the
    # cache's own rules.
    ran = []
    for path in sorted(Path("automation/runs").glob("m4-*/*.json")):
        try:
            blob = json.loads(path.read_text())
        except Exception:  # noqa: BLE001
            continue
        for action in blob.get("actions", []):
            if action.get("short_name") == tail:
                ran.append((path, action))
    if ran:
        path, action = ran[-1]
        if action["phase"] == "SUCCEEDED" and action["cache_status"] == "CACHE_DISABLED":
            ok(f"{tail} SUCCEEDED on-cluster in {action['duration_ms'] / 1000:.1f} s and was "
               f"CACHE_DISABLED ({path.parent.name}/{path.name}) — the publish cannot be "
               f"satisfied by a cache")
        else:
            no(f"{tail} recorded phase {action['phase']} / cache {action['cache_status']}")
    else:
        no(f"no recorded run contains a {tail} action — the tail has never run on-cluster here")

    # And the live check the debt row asks for: the marts reconcile AFTER the tail
    # task. Asked of both sides, never re-published — a gate with side effects on
    # the warehouse it checks is not a gate.
    import marts_publish as mp

    transport = mp.make_transport("kubectl", database="marts")
    try:
        rows = mp.reconcile(transport, Path("analytics/dbt/marts.duckdb"), "trips_clean")
    finally:
        close = getattr(transport, "close", None)
        if close is not None:
            close()
    disagreeing = [(m, pub, src) for m, pub, src, agree in rows if not agree]
    if rows and not disagreeing:
        total = sum(pub for _, pub, _, _ in rows)
        ok(f"the published fact table reconciles with the analyst layer for all "
           f"{len(rows)} month(s), {total:,} rows — asked of Postgres and DuckDB "
           f"separately, republished nothing")
    else:
        no(f"month(s) disagree between the mart and its source (month, published, "
           f"source): {disagreeing} — a month-scoped publish left one behind")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the marts-tail check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 3 "the marts-tail check"

# --------------------------------------- 7. the alias no M4 run may move ------
section "7. F-016's standing law — M4 fitted a great deal and promoted nothing"
consume < <(uv run python - 2>/dev/null <<'PY'
import ast
import json
from pathlib import Path

def ok(m): print(f"PASS|{m}")
def no(m): print(f"FAIL|{m}")

try:
    import mlflow
    from taxi_mlops.training import tracking
    from taxi_mlops.training.run import load_train_config

    cfg = load_train_config("configs/train.yaml")
    tracking.configure(cfg["mlflow"])
    client = mlflow.MlflowClient()
    name, alias = cfg["registry"]["model_name"], cfg["registry"]["champion_alias"]

    # Read the alias the way M2-S3 established: `search_model_versions` returns
    # `aliases` EMPTY on server 3.15.1, so a snapshot built from that field would
    # be blind to the exact mutation this leg checks.
    live = client.get_model_version_by_alias(name, alias)
    ok(f"@{alias} resolves to version {live.version} (run {live.run_id[:12]}…)")

    # Every recorded run wrote what the alias was when it finished. The gate does
    # not know what that number SHOULD be — it asserts the records and the
    # registry agree, which is the property, and stays silent about the value.
    seen = {}
    for path in sorted(Path("automation/runs").glob("m4-*/pipeline_run.json")):
        blob = json.loads(path.read_text())
        seen.setdefault(str(blob.get("champion_after")), []).append(blob.get("run_name"))
    if not seen:
        no("no pipeline run record carries a champion_after — the alias was never observed "
           "across an M4 run")
    elif set(seen) == {str(live.version)}:
        ok(f"all {sum(len(v) for v in seen.values())} recorded pipeline run(s) left "
           f"@{alias} at version {live.version}, which is where it is right now")
    else:
        no(f"recorded runs left the alias at {sorted(seen)} and it is now "
           f"{live.version} — an M4 run moved the serving pointer")

    # The sharpest form of the law: M4's pipeline fitted a great many runs in its
    # own experiment. NOT ONE of them is a registry version. A promotion cannot
    # hide from this — it would have to create a version, and a version carries
    # the run that produced it.
    import sys
    sys.path.insert(0, ".")
    from pipelines import tasks

    exp = client.get_experiment_by_name(tasks.DEFAULT_EXPERIMENT)
    versions = client.search_model_versions(f"name='{name}'")
    if exp is None:
        no(f"there is no {tasks.DEFAULT_EXPERIMENT!r} experiment to check against the registry")
    else:
        pipeline_runs = {r.info.run_id
                         for r in client.search_runs([exp.experiment_id], max_results=50000)}
        polluting = [v.version for v in versions if v.run_id in pipeline_runs]
        if pipeline_runs and not polluting:
            ok(f"none of the {len(pipeline_runs)} run(s) the M4 pipeline fitted is a registry "
               f"version ({len(versions)} version(s) exist, all from earlier milestones) — "
               f"an orchestration demo made no promotion decision as a side effect")
        else:
            no(f"pipeline run(s) became registry version(s) {polluting}")

    # ...and the law is structural, not a habit. `train` has NO promote parameter:
    # a law with a keyword argument is a default.
    tree = ast.parse(Path("pipelines/tasks.py").read_text())
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "train"), None)
    if fn is None:
        no("pipelines/tasks.py has no `train` callable to check")
    else:
        args = {a.arg for a in fn.args.args} | {a.arg for a in fn.args.kwonlyargs}
        promotes = [n for n in ast.walk(fn)
                    if isinstance(n, ast.keyword) and n.arg == "promote"
                    and not (isinstance(n.value, ast.Constant) and n.value.value is False)]
        if "promote" not in args and not promotes:
            ok("tasks.train takes NO `promote` parameter and passes promote=False "
               "unconditionally — the stage cannot be asked to promote")
        else:
            no(f"tasks.train exposes promotion: parameter={'promote' in args}, "
               f"non-False call sites={len(promotes)}")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL|the alias check itself raised {type(exc).__name__}: {exc}")
PY
)
expect_verdicts 4 "the alias check"

# ------------------------------------------------------------------ verdict --
echo
if [[ "$FAILS" -eq 0 ]]; then
  printf '\033[32m[verify-m4] GREEN — every M4 sub-check passed.\033[0m\n'
  printf '            Show: the pipeline story   docs/pipeline_m4.md\n'
  printf '                  the image + D-004    docs/task_image_m4.md\n'
  printf '                  the records read     automation/runs/m4-*/ (tracked: F-029 closed)\n'
  exit 0
fi
printf '\033[31m[verify-m4] RED — %d sub-check(s) failed.\033[0m\n' "$FAILS"
exit 1
