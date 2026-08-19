# `verify-m4` transcripts — the M4 gate, and the drill that proves it can say no

Committed for the reason M3's are (`docs/verify_m3_transcripts.md`): a gate's
verdict is only evidence if somebody can read what it actually printed. Both runs
below are verbatim, 2026-08-19, on the live cluster, with `@champion` at version 2
before and after.

Re-run them with `make verify-m4` and `make verify-m4-redteam`. Neither re-fits
anything, neither launches a pipeline, and neither mutates the registry, the
cluster or the warehouse. The narrative is `docs/pipeline_m4.md` §17–§20.

> **Note, 2026-08-19 (M5-S1).** §1's closing block below prints
> `the records read     automation/runs/m4-*/ (gitignored: F-029)`. That was true
> the day it was pasted and is not any more: F-029 was decided (option A) and the
> record JSONs are tracked, so the gate now prints `(tracked: F-029 closed)`. The
> transcripts below are left VERBATIM — a transcript edited to match today's code
> is not a transcript. The post-move re-runs are in `docs/serving_m5.md` §1.

---

## 1. `make verify-m4` — GREEN 39/39

```
[verify-m4] the M4 gate — the control plane, the image, the green run,
            the cache, the kill drill, the marts tail, and the alias that
            no M4 run may move. It re-reads and re-checks; it re-runs NOTHING.

== 1. the control plane, and the four things a task pod cannot start without ==
  ok   API answers: GET /healthz -> 200 (svc svc/flyte-flyte-binary-http:8090)
  ok   flyte-flyte-binary has 1 available replica(s)
  ok   flyte-flyte-binary-console has 1 available replica(s)
  ok   flyteconnector has 1 available replica(s)
  ok   PodTemplate flyte-task-defaults is applied in-cluster and its container is named 'default' (the k8s plugin's contract)
  ok   the data volume the template mounts (pvc/taxi-data) is Bound
  ok   mlflow/mlflow: 1 pod(s) Running — the stages have somewhere to log and something to read
  ok   platform/postgres: 1 pod(s) Running — the stages have somewhere to log and something to read
  ok   platform/minio: 1 pod(s) Running — the stages have somewhere to log and something to read

== 2. the image the stages run in — reachable on every node, and D-004 still dead ==
  ok   the task image is tagged '7897ab0', not ':latest' — a stale node is a missing image (loud), never wrong bytes (silent)
  ok   the manifest records tree_dirty=false — the evidence below was produced by an image built from committed code
  ok   all 3 node(s) hold taxi-mlops-pipeline:7897ab0 at containerd id 40e0ac84171f… (read with each node's own crictl)
  ok   in-container OpenMP is the SYSTEM package: 'openmp: system libgomp.so.1' on the first line (D-004's closure, re-observed)
  ok   no '[openmp]' announcement anywhere in the probe's output — the shim did not fire, which is the negative evidence the debt closed on

== 3. the green run — the graph is whole, and every recorded stage SUCCEEDED ==
  ok   every one of the 7 stage(s) in tasks.STAGES is wrapped by a Flyte task (build_features->build_features, evaluate->evaluate, ingest->ingest_month, publish_marts->publish_marts, register->register, train->train, validate->validate)
       1 record(s) are single-task probes, not pipeline runs (rklz7vdv2d59bn8kbp8d) — read by section 5, excluded here
  ok   4 recorded on-cluster run(s) to read, across 4 record file(s)
  ok   every action of every recorded run SUCCEEDED (29 action(s) across 4 run(s))
  ok   1 recorded run(s) executed ALL 7 stages end to end (e.g. rw98pj84z4jh5ldqrxqp in m4-marts/)
  ok   every recorded run has a `main` parent action — the stages ran as ONE workflow, not as seven launches
  ok   MLflow's 'm4-pipeline' experiment holds 28 run(s), every one FINISHED — the fits the control plane recorded really happened

== 4. the cache-hit rerun — read from the drill's record, never re-asked (gotcha #66) ==
  ok   the 2 stage(s) the rerun re-executed unconditionally (main, register) are exactly stages the code declares cache='disable' — the record agrees with the source
  ok   all 5 cacheable stage(s) of run 2 read CACHE_HIT — the CLAIM, made by the control plane, which the CLI does not render
  ok   run 1 POPULATED all 5 of them first — a drill comparing two reruns to each other could show a saving that was already there
  ok   and the clock agrees: 1966.9 s of cacheable work in run 1 came back in 3.2 s in run 2 (0.16%)
  ok   MLflow: 12 -> 16 runs across run 1, 16 -> 16 across run 2 — the fit ran once and was reused, said by a server that cannot see the cache
  ok   the two witnesses AGREE: the control plane says no cacheable stage re-executed and MLflow minted no run to contradict it

== 5. kill-a-pod — the run survived it, and the retry budget is real AND finite ==
  ok   the run finished anyway: exit 0 and all 7 action(s) SUCCEEDED after train's pod was deleted mid-work
  ok   a DIFFERENT pod object ran train to completion: killed uid 1223e07d… vs surviving ['9d8b05a3'] — identity, not name
  ok   train genuinely EXECUTED in the drill (cache_status CACHE_POPULATED) — there was a pod to kill
  ok   the control plane recorded the killed action at ONE attempt — pod recreation and the retry budget are two different mechanisms
  ok   the retry budget the code declares (_STAGE_RETRIES=2) is the one the drill recorded — the record describes THIS source, not a remembered number
  ok   a task that always raises settled at attempt index 3 and the run FAILED — the budget of 2 is real AND finite (F-027's fix is what makes this field readable at all)

== 6. the marts tail task — it ran as stage 7, and the warehouse still reconciles ==
  ok   publish_marts is the LAST stage in tasks.STAGES — §9/M1-S6's 'tail task of the monthly pipeline', landed
  ok   publish_marts SUCCEEDED on-cluster in 90.6 s and was CACHE_DISABLED (m4-marts/actions.json) — the publish cannot be satisfied by a cache
  ok   the published fact table reconciles with the analyst layer for all 8 month(s), 56,127,878 rows — asked of Postgres and DuckDB separately, republished nothing

== 7. F-016's standing law — M4 fitted a great deal and promoted nothing ==
  ok   @champion resolves to version 2 (run 92b73bd4f77d…)
  ok   all 3 recorded pipeline run(s) left @champion at version 2, which is where it is right now
  ok   none of the 28 run(s) the M4 pipeline fitted is a registry version (2 version(s) exist, all from earlier milestones) — an orchestration demo made no promotion decision as a side effect
  ok   tasks.train takes NO `promote` parameter and passes promote=False unconditionally — the stage cannot be asked to promote

[verify-m4] GREEN — every M4 sub-check passed.
            Show: the pipeline story   docs/pipeline_m4.md
                  the image + D-004    docs/task_image_m4.md
                  the records read     automation/runs/m4-*/ (gitignored: F-029)
```

*(The `[mlflow] tracking: …` banner lines that `tracking.configure` prints before
§3's and §7's legs are elided above; they are notes, not verdicts, and the gate
renders them indented as such.)*

---

## 2. `make verify-m4-redteam` — RED on one rewritten field, then GREEN again

```
[verify-m4-redteam] 0. the record as it stands (restored to exactly this, whatever happens)
  automation/runs/m4-cache/cache_drill.json  sha256 beb10ab49fb0…

[verify-m4-redteam] 1. rewrite ONE field: run 2's train stage claims it re-executed, and nothing else changes
  run 2 / train: cache_status CACHE_HIT -> CACHE_POPULATED (duration still 140 ms, phase still SUCCEEDED, MLflow counts untouched at 16 -> 16)

[verify-m4-redteam] 2. make verify-m4 — expected RED, naming the stage and both witnesses
  FAIL cacheable stage(s) did not hit on the rerun: {'train': 'CACHE_POPULATED'}
  FAIL the two witnesses CONTRADICT each other: the record says ['train'] re-executed on the rerun while MLflow minted 0 run(s) — a fit either logs or does not happen, so one of these records is wrong
[verify-m4] RED — 2 sub-check(s) failed.
  ok   the gate exited 1 — RED against a record whose cache claim contradicts MLflow
  ok   the CLAIM leg names the stage: train is a cacheable stage that did not read CACHE_HIT
  ok   the CROSS-SYSTEM leg fired: the record says a fit re-executed while MLflow minted nothing — the leg a gate reading only cache_status would not have had
  ok   37 sub-check(s) still ran and passed — the gate reports everything, not the first thing
  ok   unaffected leg still green: is wrapped by a Flyte task
  ok   unaffected leg still green: in-container OpenMP is the SYSTEM package
  ok   unaffected leg still green: a DIFFERENT pod object ran
  ok   unaffected leg still green: the budget of
  ok   unaffected leg still green: reconciles with the analyst layer
  ok   unaffected leg still green: is a registry version
  ok   run 1's populate leg still passed — the drill's other 4 cacheable stages were not collateral

[verify-m4-redteam] 3. restore the record and re-run — expected GREEN again
  restored automation/runs/m4-cache/cache_drill.json (sha256 beb10ab49fb0…)
  ok   automation/runs/m4-cache/cache_drill.json is byte-identical to what the drill found (sha256 beb10ab49fb0…)
[verify-m4] GREEN — every M4 sub-check passed.
  ok   the gate is GREEN again (39 sub-checks, exit 0) — the drill left nothing behind

[verify-m4-redteam] PASSED: the M4 gate went RED on ONE rewritten cache
                    status, named the stage AND the contradiction between two
                    independent witnesses, kept counting every other sub-check,
                    and returned GREEN when the record was restored.
```

**What to read in that output.** Not the RED — any assertion can be made to fail.
The two things worth checking are that **37 of 39 sub-checks still ran and passed**
(a suite that collapses to one failure reports one problem and hides thirty-eight),
and that the **second** FAIL fired at all: the tampered file is internally
consistent by every field a reader would skim, and only a gate that asks two
independent systems the same question can catch it. That is what ranking three
witnesses in the cache drill was for, and this is the first time it has been
falsifiable rather than argued.
