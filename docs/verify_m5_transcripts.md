# `verify-m5` transcripts (M5-S5)

Pasted, unedited, from the run that produced them on 2026-08-19. The gate is
`scripts/verify_m5.sh`; the red team is `scripts/verify_m5_redteam.sh`. Both are
described in `docs/rituals/2026-08-19_prr-m5.md` §3 and in CLAUDE.md's command
table.

Two things to read for, because they are the properties rather than the numbers:

1. **Nothing here was re-run.** The parity, load and self-heal numbers come from
   the tracked records M5-S3/S4 wrote; the gate's own wall-clock is **5.762 s**
   against evidence that cost a ~6.5-minute drill including a deliberate outage.
   The one live action is a SINGLE prediction (§2), because a serving gate that
   never asks the service for the artifact it exists to produce would pass
   against a dead model with a healthy `Ready` condition.
2. **No literal version appears.** §2 compares the response's `model_version`
   stamp against what the alias resolves to; §7 compares the alias against the
   run the M3 bake-off recorded as its winner. The string `2` in the output is
   printed, never asserted.

---

## 1. `make verify-m5` — GREEN, 49 sub-checks across 7 sections, 5.762 s

```
[verify-m5] the M5 gate — the route, the champion on the wire, parity,
            the load shape, self-heal, the runbook and the PRR, and the
            alias no M5 story may move. It reads and it asks; it re-runs nothing.

== 1. the serving PLATFORM — the route answers, and the operator is where it must be ==
  ok   the declared route answers: GET localhost:8081/healthz -> 200 (the controller's OWN endpoint — gotcha #70)
  ok   ingress-nginx runs on mlops-taxi-control-plane — the one node whose port 80 kind publishes as 8081 (derived from the kind config, not typed)
  ok   kserve/kserve-controller-manager: 1 available replica(s)
  ok   cert-manager/cert-manager: 1 available replica(s)
  ok   KServe's live deploy mode is RawDeployment — read off configmap/inferenceservice-config and equal to what infra/helm/kserve/values.yaml submits
  ok   ClusterServingRuntime taxi-mlserver is applied and runs taxi-mlops-predictor:mlserver-1.7.1-lgb-4.7.0 — the image the manifest pins, not a chart default

== 2. the champion on the wire — resolved from the ALIAS, and asked for one prediction ==
       [mlflow] tracking: http://localhost:5000
       [mlflow] artifacts: direct to http://localhost:9000 (server does not proxy)
       [mlflow] credentials set from .env: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
  ok   serving/nyc-taxi-eta is Ready and its predictor has 1 available replica(s)
  ok   no serving.kserve.io/stop annotation is on the InferenceService — nothing left it stopped
  ok   the served storageUri IS what models:/nyc-taxi-eta@champion resolves to (version 2)
  ok   the endpoint answered and stamped model_version='2' — equal to what the alias says (never the literal), quoting 10.665224 minutes for hazard 'ordinary-midday'
  ok   the live answer reproduces the recorded parity row to 0.000e+00 minutes (10.665224429 vs 10.665224429) — the record describes THIS endpoint
  ok   the served version's feature_set tag ('v2') equals configs/train.yaml's features.version — the client builds the matrix this model eats
  ok   the configured feature set resolves to 24 features — the width the parity record was measured at

== 3. THE parity test — offline == online, read from the record M5-S3 wrote ==
  ok   the record was measured against a tolerance of 1e-06 minutes, no looser than parity.TOLERANCE_MINUTES (1e-06) on disk
  ok   max |offline - online| = 0.000e+00 minutes over 16 rows — inside the 1e-06 bar (recomputed from the rows, not read off the summary)
  ok   all 16 declared hazards were measured and nothing else was — the set is committed in parity.HAZARDS, so a shrunken record is a RED gate
  ok   the 3 hardest rows (no-geometry-both, no-geometry-one-sided, unseen-od-pair) are inside the bar too — the missing-geometry path quotes at all (F-030)
  ok   the record's offline champion and its endpoint were the same version (2) — a parity number across two different models would be meaningless

== 4. p95 with its shape attached — read from the record, never re-measured ==
  ok   the headline carries its whole shape: 4.0 req/s for 60 s, concurrency 8, hazards mix, 1 row(s)/request
  ok   achieved 4.016 req/s against a target of 4.0 (0.4% off) — the client kept up, so the percentiles belong to the stated rate
  ok   p50 17.207 - p95 104.226 - p99 107.239 - max 115.383 ms, monotone and measured from the SCHEDULED instant
  ok   scheduled->response >= sent->response at every percentile (p95 gap 0.111 ms) — the omission the open loop exists to expose
  ok   240/240 requests answered, 0 errors
  ok   the headline rate was chosen at 72% of the CPU limit — under the 90% clause, so the p95 is the service's and not the quota's (gotcha #74)
  ok   the ceiling was measured, not guessed: 2 ramp step(s) reached >=90% of the CPU limit (worst 101%)
  ok   the capacity block is present: 1.308 mean cores, 0.3258 core-s/request, request 200m vs limit 2

== 5. losing the predictor — the outage measured, and the anchors that measure it ==
  ok   the self-heal drill recorded 7/7 checks passed
  ok   a DIFFERENT pod object served afterwards: uid f6bf83df… -> 2ba0096c… (node mlops-taxi-worker -> mlops-taxi-worker2)
  ok   the outage is 14.53 s and it reconciles: recovered_at 40.03 - first_error 25.5 = 14.53 (the error-span anchor would have said 14.251 s — gotcha #75)
  ok   the first failure (25.5 s) is AFTER the kill (25.0 s) — the outage is attributed to the event that caused it
  ok   after recovery 559 requests at 0.0% errors against a pre-kill control of 0.0% over 100 requests
  ok   stop/start is REHEARSED: the route stopped answering 3.12 s after the annotation and answered again 18.24 s after it was removed
  ok   the rehearsal observed the mechanism, not just the clock: Stopped False->True->False and the route answering again at the end
  ok   the rehearsal removed its own annotation — the drill left nothing on the object

== 6. the PRR — a runbook that runs, a rollback that is typed, boxes that carry evidence ==
  ok   docs/runbooks/serving.md exists (266 lines)
  ok   every make target the runbook types exists in the Makefile (10 distinct: backup, boards, duckdb, load-drill, marts, predictions, quote, rollback, serve, verify-m5)
  ok   the rollback is TYPED: it moves the alias, moves configs/train.yaml's features.version with it, and re-deploys — the three halves a rollback needs here
  ok   the rollback says NOT REHEARSED in its own section — the M4-S2 backup precedent
  ok   every number the runbook quotes is in the record it cites: outage 14.53 s, p95 104.226 ms, stop 3.12 s, start 18.24 s
  ok   the PRR minutes are committed: docs/rituals/2026-08-19_prr-m5.md
  ok   all four checklist boxes are present: the runbook exists ✅; rollback typed ✅ (and NOT rehearsed, s; alerts PLANNED (M6 implements) ✅; capacity sanity ✅ (with one open recom
  ok   every box carries pasted evidence — a fenced block or a named record (4 boxes checked)
  ok   the alert PLAN names 7 signals with sources — a plan with named signals is an artifact; M6 sets their numbers
  ok   the F-019 policy's SRE reasoning is minuted here, with the 422 signal it bought (M5-S2's cross-reference)
  ok   the deployments ledger carries the M5-S5 serving row (runbook + PRR)

== 7. the alias law — serving READS the pointer, and the rollback target really exists ==
       [mlflow] tracking: http://localhost:5000
       [mlflow] artifacts: direct to http://localhost:9000 (server does not proxy)
       [mlflow] credentials set from .env: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
  ok   @champion is version 2, whose run is the winner the M3 bake-off recorded — no M5 story moved the pointer (derived from the record, never typed)
  ok   all 2 registry version(s) carry gate_verdict=PROMOTE — every one was created by the gate, none by hand
  ok   the rollback target exists: version(s) 1 (v1) — each one naming the feature set it eats, which is what makes §4's config step derivable
  ok   no module in src/taxi_mlops/serving/ CALLS a registry-mutating verb (5 files parsed with ast, not grepped)

[verify-m5] GREEN — every M5 sub-check passed.
            Show: parity output      automation/runs/m5-parity/parity.json · docs/parity_m5.md
                  the PRR minutes    docs/rituals/2026-08-19_prr-m5.md
                  the runbook        docs/runbooks/serving.md
```

```
real	0m5.762s
user	0m11.017s
sys	0m1.397s
```

---

## 2. `make verify-m5-redteam` — PASSED

One number rewritten in `automation/runs/m5-load/selfheal.json`:
`recovery.outage_seconds` **14.53 -> 14.251**, taken from the record's OWN
`error_window.span_s` rather than invented. That is gotcha #75's mistake
re-made — anchoring an outage on the span between the first and last error
instead of on first-failure -> first-success — and it is wrong by 0.28 s, i.e.
a rounding-sized discrepancy rather than an absurdity. M5-S4's first attempt
made exactly this error and reported **182 s** for a service that was down for
13.

Two independent legs caught it, reading two different artifacts: the record's
own arithmetic (§5) and the runbook an operator reads (§6).

```
[verify-m5-redteam] 0. the record as it stands (restored to exactly this, whatever happens)
  automation/runs/m5-load/selfheal.json  sha256 f1712acf9f80…

[verify-m5-redteam] 1. rewrite ONE number: the outage becomes the error SPAN — gotcha #75's mistake, re-made
  recovery.outage_seconds 14.53 -> 14.251 (the error-window span, derived from the record itself; recovered_at 40.03 and first_error 25.5 are UNTOUCHED, as are all 7 recorded checks and the pod uids)

[verify-m5-redteam] 2. make verify-m5 — expected RED, naming the arithmetic AND the runbook
[verify-m5] the M5 gate — the route, the champion on the wire, parity,
  FAIL the recorded outage 14.251 s does not equal recovered_at - first_error (14.53 s) — the anchors and the number disagree
  FAIL the runbook quotes number(s) that no record holds: {'the outage': 14.251}
[verify-m5] RED — 2 sub-check(s) failed.
  ok   the gate exited 1 — RED against a record whose outage no longer reconciles
  ok   the ANCHOR leg fired: the recorded outage is not recovered_at - first_error, which is the only arithmetic that makes it an outage
  ok   the RUNBOOK leg fired: the operator-facing document and the record now disagree — the second witness, reading a different artifact
  ok   47 sub-check line(s) still passed — the gate reports everything, not the first thing
  ok   unaffected leg still green: the declared route answers
  ok   unaffected leg still green: stamped model_version
  ok   unaffected leg still green: max |offline - online|
  ok   unaffected leg still green: the headline rate was chosen at
  ok   unaffected leg still green: a DIFFERENT pod object served afterwards
  ok   unaffected leg still green: the rollback is TYPED
  ok   unaffected leg still green: is the winner the M3 bake-off recorded
  ok   the drill's own recorded checks still passed — the gate went red on the WRONG number, not on the edit

[verify-m5-redteam] 3. restore the record and re-run — expected GREEN again
  restored automation/runs/m5-load/selfheal.json (sha256 f1712acf9f80…)
  ok   automation/runs/m5-load/selfheal.json is byte-identical to what the drill found (sha256 f1712acf9f80…)

[verify-m5] GREEN — every M5 sub-check passed.
            Show: parity output      automation/runs/m5-parity/parity.json · docs/parity_m5.md
                  the PRR minutes    docs/rituals/2026-08-19_prr-m5.md
                  the runbook        docs/runbooks/serving.md
  ok   the gate is GREEN again (50 sub-check line(s), exit 0) — the drill left nothing behind
  ok   git status is clean for automation/runs/m5-load/selfheal.json — the restore is byte-identical to the committed record

[verify-m5-redteam] PASSED: the M5 gate went RED on ONE rewritten outage
                    number — the exact wrong anchor gotcha #75 records — named
                    both the arithmetic and the runbook that quotes it, kept
                    counting every other sub-check, and returned GREEN when the
                    record was restored.
```
