# M4 KICKOFF — Pipeline on-cluster (Flyte)   (authored by: ARCH/Fable · 2026-08-18 · v3.0: the Architect is sole author)

Session model stated: **Fable 5 (claude-fable-5)** — architect sessions on any
other model are void (ORG.md rule 7).

**M4 carries no ◆** (BLUEPRINT §9: REV gates are M2, M3, M7). The last story
exits to the boundary: `automation/next_session.sh architect 120`.

**The law this milestone lives under, stated once at the top: THE CLUSTER IS
NOW STATEFUL AND NO M4 STORY MAY TAKE IT DOWN.** Since M2 the kind cluster
holds the only copy of: the MLflow registry (champion versions 1 AND 2), every
run and artifact in MinIO, the Metabase app-db, and both Optuna studies — all
on PVCs, and PVCs die with the cluster. `make verify-m2` and `make verify-m3`
read that state LIVE, so a rebuild doesn't just cost re-work, it turns two
green gates red permanently. Every story below is designed to need **zero**
`kind delete`/`create`: no new hostPort (the Flyte console is reached another
way, recorded), images arrive by `kind load` (not a containerd config patch),
and S2 gives the state a copy that survives the machine *before* M4 adds more
state beside it. A story that finds itself wanting a rebuild has found a wall:
stop and write it up (three-attempt rule), never "just recreate it".

## 0. Boundary triage of M3 (the closure sweep, folded in)

**Verify re-run (by the approver, this session, 2026-08-18):** `make verify-m3`
→ **GREEN — 46 `ok` sub-checks across 8 sections, exit 0** (counted:
`make verify-m3 2>&1 | grep -c "ok  "` → `46`). Highlights, pasted not
remembered: §7 `models:/nyc-taxi-eta@champion -> version 2, run 92b73bd4f77d… —
the run the bake-off named as winner` · `the version carries the bake-off's own
numbers: KPI-09 3.2403 vs floor baseline-group-median-od-fallback` · `none of
the 1 REFUSED contender(s) is a registry version (2 version(s) total)` ·
`configs/train.yaml names feature set 'v2' — the winner's set` · `the champion's
signature is exactly the 24 feature(s) features.sets.resolve expands 'v2' to,
in order` · §8 `configs/promotion.yaml is gone` · `grep -r 'analytics'
src/taxi_mlops/ is EMPTY` (ADR-009). Closing line verbatim:
`[verify-m3] GREEN — every M3 sub-check passed.`

**Lineage spot-check (gotcha #20):** `git branch -r --contains 55b83cf`
(M3-S3's closing doc commit, mid-milestone) → `origin/main`. Tree clean and
level: `## main...origin/main` at `c8bfcf7` (REV's review commit).

**REV's ◆ verdict (signoffs row 2026-08-18): APPROVE WITH CONDITIONS** — every
published M3 number re-derived from committed artifacts (champion and floor
KPIs to 10 decimals off the prediction parquet; the floor re-fitted from raw in
DuckDB, a different engine, reproducing all five figures including the 968
past-both-levels rows; both DR-01 budgets re-summed). Three findings filed
(F-018/F-019/F-020), no S1, nothing parked. REV closes nothing (charter); ARCH
dispositions everything here.

**Every open finding, condition, and due debt from M3, dispositioned:**

| Item | Disposition |
|---|---|
| **F-018** (REV cond. 1, S2: the bake-off SELECTS its winner on the holdout month, then gates on it; `docs/bakeoff_m3.md:87`'s "untouched by … selection" is false after `bakeoff_m3.py:276`, and the two v2 arms were 0.0022 min apart — the holdout decided a real identity) | **INTAKEN → M4-S1**, sequenced FIRST — the repair lands before the pipeline wraps the gate's calling path, so REV's "before M7" is satisfied by construction (quoted landing: §9/M4 *"ingest→validate→features→train→evaluate→register"* — the register step is `gate`'s caller). Closes ONLY by its row's (a)+(b): rank on val with the holdout reserved for the single winner's verdict, and correct the false sentence wherever a bake-off produced it. The M3 RECORD is not re-run and not re-written — `bakeoff.json` stands as measured (val and test rankings were identical, so the champion survives its own method defect); the fix is to the CODE and to the sentence, with a dated correction note, never a silent edit. |
| **F-019** (REV cond. 2, S2: the promoted champion raises on any request dated outside 2019 — v2's g1 needs `is_holiday`, the committed table holds 10 rows all 2019, and `features/` is the ONE path for training AND serving; a 500 per quote at M5) | **CARRY → M5**, quoted landing re-verified (gotcha #19): §9/M5 *"v1's M4 (KServe Standard, mlserver, storage-config, THE parity test 1e-6, p95 measured, self-heal under load) + the Production Readiness Review: SRE walks a written checklist … BEFORE the champion serves"* — the story that would eat the 500 decides extend-vs-policy, and the degrade-vs-refuse half is an SRE call that belongs in the PRR minutes. **M4 is unaffected** (pipeline parametrized over 2019 months only), but M4-S1 adds ONE cheap tripwire so the trap cannot go quiet again: a unit test that builds the configured feature set for a non-training-year timestamp and asserts the refusal is the loud `ValueError` naming the table — pinning the CURRENT behaviour so M5 changes it deliberately, not by surprise. Ledger row annotated. |
| **F-020** (REV cond. 3, S3: the tuned config is 15%-sample-optimal applied unchanged at 44M rows — `min_data_in_leaf: 1293` is 6.7× less regularising at full scale, the 800-round cap traveled by construction; the transfer question is measured nowhere) | **CARRY → M7**, quoted landing re-verified: §9/M7 *"scheduled Flyte retrain landing a challenger"* — the retrain loop re-runs the same scout→sniper→refit path, so the scale-transfer rule (row option (b)) or the one measured re-fit (option (a)) is M7-kickoff intake, exactly where REV placed it. Deliberately NOT pulled into M4: re-fitting the v2 winner now spends ~35 min re-litigating a bake-off whose verdicts stand, and DR-01's refit-after-seeing prohibition still binds M3's budget. Ledger row annotated. |
| **F-016** (the incumbent gate condition is non-regression with NO margin; the alias moved on +0.63% — 1.2 s — while the floor condition demands 2.00%; raised at M3-S5, deliberately unacted-on) | **→ AWAITING_PO 2026-08-18-1** (options A/B/C with honest trade-offs; recommendation B, a 0.50% transition-cost margin, its cost stated). A gate condition changes ONLY by PO fork — this is the genuine article, not a friction report. **Parked: edits to the incumbent condition. Nothing else waits**: the gate stands as pre-registered, and THIS kickoff legislates that no M4 demo moves the alias (every pipeline run that reaches the register step runs `--no-promote`; `verify-m4` asserts `@champion` → version 2, run `92b73bd4f77d…`, before AND after). Becomes blocking only at M7's first retrain promotion. |
| **F-015** (auto-on-v1 is a truncated model and the 2×2 must say so in the row) | **CLOSED this triage, by M3-S5's own artifacts against the row's own conditions**: `docs/bakeoff_m3.md` carries the caveat IN the `auto-on-v1` row (§1 "stopped by the clock, not by convergence… attaches to the first row and to no other"), §4 states "the caveat explains the size of the loss; it does not convert the row into a pass", and §5's 2×2 names the truncation in the tuning-only cell and states what the square can and cannot separate. Ledger row closed with the quotes. |
| **F-021** (NEW, found this triage: `make ports` goes RED against OUR OWN live cluster — 6 of 10 ports held by our own kind hostPorts — and its message says "another stack … Free it (stop that stack)". Since the cluster became stateful, obeying that message destroys the registry) | **FILED + INTAKEN → M4-S2** (the platform-plumbing story). Closes when the precheck distinguishes the holder: our own `mlops-taxi-*` cluster → `held by US`, exit 0; a genuinely foreign holder → the gotcha #10 refusal unchanged, exit 2; both pinned by tests. The gotcha #50 lesson one level down: a guard that fires on the program's own correct behaviour trains readers to obey it wrongly or ignore it. |
| **F-009** (alias-URI load fails on MLflow 3.15.1; localized resolution in `score.load_champion`; gotcha #39's impostor recorded) | **CARRY, not due — landing M5**, unchanged since the M2 boundary, quoted scope re-verified: §9/M5 *"KServe Standard, mlserver, storage-config, THE parity test 1e-6"*. M4's pipeline scores through the SAME one resolution point; nothing else learns the logged-model id. |
| `docs/error_memo_m2.md` §7 row 2 (airport gap held at 1.91× even though v2 carries OD geometry) | **STAYS OPEN in the memo, no ledger row** — it is an analysis question, not a defect. M7's drift/retrain memos are its next natural reader. Restated so it is visibly not lost. |
| AWAITING_PO 2026-08-16-2 (allowlist) · 2026-08-17-1 (host libgomp) | **Standing with the PO, both non-blocking.** Note on -1: D-004 puts the REAL libgomp in the M4 image regardless — the host one-liner remains the PO's and only affects laptop runs. |
| D-001 (how images reach kind nodes) · D-003 (23 GB full-refresh when the publish is scheduled) · D-004 (image owes real libgomp1, shim proven dead) | **All three DUE HERE — intaken below by id** (debt table). None re-carried. |

**Verdict: M3 CLEANLY CLOSED — tagged `m3-closed`.** All §9/M3 accept-when legs
green against the quoted text (dossier 20 ≥ 10 with source + leakage note each ·
ablation per-group deltas with the keep bar re-applied · leakage red-team
transcript, inflation observed on the seen month only · resumability + 6 pruned
trials · five verdicts from evaluator-traceable runs), verify re-run green at
the boundary by the approver, ◆ REV done with mandatory findings and three
re-derivations, sign-off row added (producer EXEC S1–S5 PRs #15–#19, approver
ARCH/Fable — producer ≠ approver holds), no open item carried silently.

## Preconditions (verified LIVE at draft time 2026-08-18 — pastes, not memory)

| Precondition | Check run | Observed |
|---|---|---|
| M3 gate green at the boundary | `make verify-m3` | GREEN 46/46, 8 sections, exit 0 (paste in §0) |
| Cluster up, all Ready | `kubectl get nodes` | 3/3 Ready v1.36.1, age 26h |
| Champion is the bake-off's winner | verify-m3 §7 (6 sub-checks) | `@champion` → version 2, run `92b73bd4f77d…`, feature set v2 (24 cols, signature exact), floor `baseline-group-median-od-fallback` on the version |
| Registry holds both versions (rollback target exists) | verify-m3 §7 | versions [1, 2], the REFUSED contender is no version |
| Port state understood | `make ports` | **RED, 6/10 held — BY OUR OWN CLUSTER's hostPorts** (3030/5000/8081/8443/9000/9001). Benign in this state; the misleading message is F-021 → M4-S2. Ports 8080 (Flyte family slot), 3000, 9091, 5432 free |
| No Flyte yet, stubs where M4 expects them | `grep -c flyte pyproject.toml` · Makefile · `pipelines/flyte/` · `infra/helm/flyte/values.yaml` | `0` in pyproject (flytekit added LIVE at S2/S4, gotcha #36 checked at add time) · `deploy-flyte`/`pipeline`/`verify-m4` are `TODO(M4)` stubs · `workflows.py` stub exists · helm values stub says "chart + version chosen at its milestone from live sources" |
| **kind config has NO 8080 hostPort** (and must not gain one at M4) | `grep hostPort infra/kind/kind-config.yaml` | 8081/8443/5000/9000/9001/3030 only — adding one means cluster-down/up, forbidden by the statefulness law; console access is S2's recorded decision |
| Docker builds possible | `docker --version` | 29.6.2 (M0-observed, WSL integration on; kind node containers running under it now) |
| Disk / RAM headroom for images + in-pod training | `df -h /home/longt` · `free -h` | 946G free · 47Gi total, 27Gi free |
| Chain state | `automation/STOP` · tree | STOP absent · `## main...origin/main` clean at `c8bfcf7` |
| DVC remote intact (raw data survives anything M4 does) | CLAUDE.md M1-S2 record; `data/processed.dvc`/`data/rejected.dvc` in tree | remote `/home/longt/dvc-remote/nyc-taxi`, both pins committed |

## Debt intake (every ledgers/debt.md row landing here, by id — none re-carried)

| Debt id | Origin | What lands here | Absorbed into story |
|---|---|---|---|
| **D-001** | M0-S2 | The recorded decision: how OUR images reach the kind nodes. New constraint since the TODO was written: the local-registry pattern edits the kind CONFIG (`containerdConfigPatches`), and a config change means a rebuild — forbidden. So the decision space at M4 is honestly `kind load docker-image` now, with the registry pattern (if preferred long-term) recorded as landing at the next PO-sanctioned rebuild. Decide it, record it (ADR or dated decision note), don't drift into it. | **M4-S3** |
| **D-003** | M1 boundary | The marts publish becomes SCHEDULED (tail task of the monthly pipeline) and must not pay the measured 23 GB peak monthly without deciding to: incremental materialisation, or a recorded, re-measured decision that full-refresh stays. | **M4-S5** |
| **D-004** | M2-S2 | The task image installs `libgomp1` as a real package and the shim is PROVEN dead in-container: `openmp_status()` → `(True, 'system libgomp.so.1')` on its FIRST line inside the image, pinned by a smoke check `verify-m4` re-runs. The shim stays as the laptop path. | **M4-S3** |
| (findings intake) | F-018 → S1 · F-021 → S2 · F-016's alias-neutrality law → every story that runs the pipeline (S4/S5) + `verify-m4` | Findings are not debt, but their landings are honored the same way; each closes only by its ledger row's own conditions. | S1, S2, S4, S5 |

## Gate being served (BLUEPRINT §9/M4, quoted)

> **M4 — Pipeline on-cluster (Flyte)** (MLOps A; MLE R). v1's M3 unchanged:
> Flyte 2 per docs, containerized, ingest→validate→features→train→evaluate→
> register parametrized by month; cache-hit rerun; kill-a-pod retry; wall rule
> → ADR-002 fallback. Accept/Show: as v1 M3.

Concretely, the Makefile stub already states the verify contract: **green run +
cache-hit rerun + kill-a-pod retry survives.** Plus D-003's tail task (§9/M1-S6:
"From M4 the build+publish runs as the tail task of the monthly Flyte pipeline").

Standing law restated for every story: **the cluster never goes down** (top of
this file) · **no M4 run moves `@champion`** — every pipeline invocation that
reaches the register step runs `--no-promote`; a fresh fit of today's config
would face incumbent v2 with F-016 unanswered, and an orchestration demo must
not make a promotion decision as a side effect (`verify-m4` asserts the alias
before and after) · a REFUSE from a working gate is a GREEN pipeline with a
verdict output, never a crashed task — exit codes 0/1/2/3 are the CLI
convention, verdict-as-data is the pipeline's (S1 settles this in Python where
it is cheap) · sampled runs stay verdict-free (F-008: `--no-gate` + exit 3;
fine for plumbing smoke tests, never for acceptance evidence) · `src/taxi_mlops`
NEVER imports an orchestrator; `pipelines/` imports `src/` (BLUEPRINT
conventions; ADR-001) · anything longer than minutes runs detached
(`automation/run_detached.sh` / `make detach`, gotcha #45) · uv adds resolve
LIVE, pins → CLAUDE.md, pandas/numpy checked at add time (gotcha #36) · dbt in
any container builds `--no-partial-parse` (gotcha #38).

## Stories (5; each independently finishable, safe stopping point after each)

### M4-S1 — F-018 repaired where it lives, and the pipeline rehearsed in plain Python  (role:MLE)
Sequenced FIRST on purpose: the gate's calling path gets honest BEFORE Flyte
wraps it, and the task graph exists as testable Python BEFORE any
containerization can blur whose bug is whose.
Do:
- **F-018, by its row's own conditions**: (a) `scripts/bakeoff_m3.py` ranks on
  VAL (`docs/bakeoff_m3.md` §3 proves this changes nothing retroactively —
  val and test rankings were identical), the holdout reserved for the single
  winner's gate verdict; (b) the "untouched by training and by selection"
  sentence corrected at its sources — in `gate.verdict_lines` make the
  selection claim conditional on being true (a single-challenger run may say
  it; a bake-off may not), and in `docs/bakeoff_m3.md` add a DATED correction
  note beside line 87 (the M3 record is corrected visibly, never rewritten).
  `bakeoff.json` is NOT re-generated. `make verify-m2` and `make verify-m3`
  must be GREEN after — verify-m3 §5 replays recorded verdicts and must keep
  passing unmodified; if a sub-check pinned the false sentence, it is updated
  in the same PR under the F-017 rule (assert the property, never the literal).
- **F-019's tripwire** (one test, ~20 lines): build the configured feature set
  for a 2026-dated request, assert the loud `ValueError` naming
  `us_federal_holidays.csv`. Pins current behaviour so M5 changes it on
  purpose. The fix itself stays M5's — do NOT extend the table here.
- **The task graph as plain Python**: `pipelines/tasks.py` — six callables
  (`ingest_month`, `validate`, `build_features`, `train`, `evaluate`,
  `register`) that ONLY wrap existing `taxi_mlops` entrypoints (no logic moves;
  the modules stay the single home). Typed inputs/outputs (month string in,
  paths/run-ids/verdict out) because Flyte will need them typed at S4. The
  register callable returns the verdict as DATA (`decision`, `margins`,
  `promoted: bool`) and honors `--no-promote`; a REFUSE is a return value,
  not an exception — recorded in the docstring as the pipeline convention,
  with the CLI exit-code mapping stated beside it.
- **One local rehearsal**: a driver (`make pipeline-local MONTH=2019-01` or
  pytest-marked integration) runs the six callables in order on ONE month with
  `--train-months`-class sampling and `--no-gate` (F-008: plumbing smoke, exit-3
  class, NO verdict claimed) — proving the graph composes before Flyte exists.
  The full-data path is NOT run here; S4 owns it on-cluster.
Accept when: F-018's ledger row closes by (a)+(b) with the dated doc
correction; the F-019 tripwire test exists and passes; `pipelines/tasks.py`
exists with the six typed callables and the verdict-as-data convention;
the local one-month rehearsal transcript shows all six stages composing;
`make verify-m2` GREEN 55/55 and `make verify-m3` GREEN 46/46 re-run in the
story; unit tests + ruff green; PR green + lineage.
Evidence plan: the ranking diff + corrected sentence(s) + dated note · the
tripwire test output · the rehearsal transcript · both verify re-runs pasted.
Safe stop: after merge — the gate's callers are honest, the graph exists,
nothing on-cluster has changed.

### M4-S2 — Flyte on the cluster, its state given a lifeboat first  (role:MLOps)
Do, in this order:
- **The backup BEFORE the new tenant** (the statefulness law's constructive
  half): `scripts/platform_backup.sh` + `make backup` — `pg_dump` of every
  database in the one Postgres (mlflow, marts, metabase, optuna/m3 studies)
  and `mc mirror` of the MLflow artifact bucket, landing under
  `/home/longt/dvc-remote/nyc-taxi-platform-backups/<date>/` (outside the
  repo, same honest limit as the DVC remote: survives `make destroy` and a
  wrong `rm -rf`, not disk loss — say so in the script header). Sizes printed.
  **Restore is NOT rehearsed at M4** — write that limit in the script header
  and in the deployments ledger row; a rehearsal is a named M6-gameday
  candidate. This is a lifeboat, not a DR program.
- **F-021, by its row's conditions**: `scripts/port_precheck.sh` resolves the
  holder; our own `mlops-taxi-*` containers → `held by US — cluster up,
  expected`, exit 0; foreign holder → unchanged gotcha #10 refusal, exit 2.
  Both states pinned by tests (the fake-listener red-team from M0-S2 still
  must go red).
- **Flyte itself**: chart/version chosen LIVE (ADR-002: Flyte 2.x line first;
  record exact chart+app versions in CLAUDE.md's pin table with the read-back
  command). Databases for flyteadmin/datacatalog via `scripts/
  postgres_databases.sh` (D-002's proven additive path — fourth and fifth
  consumers; one line + one ADDITIVE secret each). Flyte's blob store = the
  existing MinIO (new bucket via the chart's or a Job's idempotent path).
  Namespace per `infra/manifests/namespaces.yaml` conventions.
  `make deploy-flyte` becomes real: idempotent (re-run = clean upgrade), and
  it re-runs the platform pieces it depends on (the M1-S5 rule: never
  defeatable by running order).
- **Console access, decided and recorded**: NO new hostPort (rebuild
  forbidden). Options: `kubectl port-forward` on demand documented in the
  Makefile target's help text, or NodePort reachable in-VM for curl-based
  checks. Record the deviation from the "declared, never port-forwarded"
  doctrine WITH its reason (the doctrine predates a stateful cluster; 8080
  stays reserved in the port family for the next sanctioned rebuild) — a
  dated note in `infra/kind/kind-config.yaml` beside the hostPort block and a
  gotcha if the executor judges it trap-shaped.
- **Wall, named**: if Flyte 2.x on kind hits the three-attempt wall
  (deployment or MLflow interop), ADR-002's fallback (flyte-binary 1.16.x)
  executes WITHOUT a new decision — record which attempt failed and why in
  the story doc, swap, move on. Budget the session accordingly: the wall
  firing is a planned path, not a crisis.
Accept when: `make backup` runs green with sizes printed and a deployments
ledger row; F-021's ledger row closes (both port-precheck states tested);
Flyte control plane Running (all pods), `flytectl`/`pyflyte` can reach it from
WSL, and ONE hello-workflow runs remotely to completion; `make deploy-flyte`
re-run is a no-op/clean-upgrade; cluster never went down (deployment ages
prove it); PR green + lineage.
Evidence plan: backup listing + sizes · both precheck transcripts (ours →
green, fake foreign listener → red) · `kubectl get pods -n <flyte-ns>` ·
the hello-run's console/CLI output · the re-run's `unchanged/upgraded` lines.
Safe stop: after merge — platform has a lifeboat and a working orchestrator,
no project pipeline on it yet.

### M4-S3 — The task image: built, loaded, and the shim proven dead  (role:MLOps)
Do:
- **D-001 decided and recorded** (ADR or dated decision note in `docker/`):
  at M4 the honest path is `kind load docker-image` — the local-registry
  pattern requires a kind-config edit and therefore a rebuild, which the
  statefulness law forbids. If the registry pattern is the better end-state,
  say so in the same note and land it at the next PO-sanctioned rebuild.
  `make image-load` wraps build+load, idempotent, digest printed.
- **The image** (`docker/Dockerfile.pipeline` or similar): python 3.12.14 to
  match `.python-version`, `uv sync --frozen` from the committed lock (the
  image trains with EXACTLY the host's resolved graph — pandas 3.0.5, lgbm
  4.7.0, xgboost 3.4.1, flytekit as added at S2/S4), **`libgomp1` installed
  as a real apt package (D-004)**. Base image tag AND digest pinned
  (the Metabase precedent). Honest size stated (xgboost drags
  `nvidia-nccl-cu13`, 241 MB, never loaded — note it, don't fight it at M4;
  slimming is not this milestone's fight).
- **D-004 proven dead, not assumed**: in-container check —
  `openmp_status()` → `(True, 'system libgomp.so.1')` FIRST line, plus
  `import lightgbm; import xgboost; import flaml` clean with NO shim
  announcement on stdout. This check becomes a `verify-m4` leg (the debt row
  demands the image's OpenMP be the system's, checked, not believed).
- **Container smoke**: the unit-test subset that needs no cluster runs
  in-image (`uv run pytest tests/unit -q -m "not integration"` or the
  project's marker convention); one `pipelines/tasks.py` callable (`validate`
  on a committed fixture) executes in-container to prove the image can run
  OUR code, not just import it.
- Image reaches the nodes: `kind load` transcript + `docker exec
  mlops-taxi-control-plane crictl images | grep <image>` read-back.
Accept when: D-001 ledger row CLOSED (decision recorded, mechanism proven by
the crictl read-back); D-004 ledger row CLOSED (in-container evidence, wired
into verify-m4's future leg); the smoke suite passes in-image; image digest
pinned in CLAUDE.md's table; PR green + lineage.
Evidence plan: the decision note · the Dockerfile · in-container
`openmp_status()` + import transcript · crictl listing · smoke-test tail.
Safe stop: after merge — an image exists on every node, nothing runs it yet.

### M4-S4 — The pipeline on-cluster, parametrized by month; the cache proves itself  (role:MLOps A, MLE R)
Do:
- Wrap `pipelines/tasks.py` in Flyte task/workflow definitions in
  `pipelines/flyte/workflows.py` — decorator-deep only (ADR-002's honest cost
  argues exactly this thinness; `src/` stays orchestrator-free, pinned by the
  existing conventions and a grep-shaped test if the executor judges it
  cheap). Task resources set explicitly (the train task gets the lion's
  share; 3 nodes share 47Gi and the host needs headroom — starting point ~24Gi
  limit on train, tuned by observation, recorded).
- Data reaches tasks the honest way for THIS cluster: raw/processed parquet
  lives on the host FS under `data/`. Decide and record: hostPath mount into
  kind nodes (kind `extraMounts` is ALSO a config edit — forbidden) → so the
  realistic paths are: tasks read/write via MinIO (upload pinned raw once,
  outputs to a bucket, DVC stays the host-side pin), or a PVC staged by a
  copy Job. Executor's craft call, recorded with the trade-off (MinIO path
  is the one M7's scheduled runs can live with; say so if chosen).
- `make pipeline MONTH=2019-01` becomes real: `pyflyte run --remote …
  --month 2019-01 --no-promote`. **Two runs prove the milestone's first two
  legs**: (1) the GREEN run — all six stages complete on-cluster for the
  configured months (full-data train; this is hours-class → **detached**:
  `make detach NAME=m4-pipeline ROLE=executor TARGET=…`, status JSON per
  stage, the M3-S4 resume pattern; the story's session ENDS after launching
  and verifying liftoff, successor session reads the status file — ritual e,
  gotcha #45); (2) the CACHE-HIT rerun — the same invocation again completes
  with cached outputs for unchanged stages (Flyte cache keys or the task-level
  skip-if-output-exists pattern; either is fine, the EVIDENCE is a second run
  transcript whose stages say cached/skipped and whose wall-clock says so).
- **Alias-neutrality proven, not promised**: `@champion` read before and
  after both runs — version 2, run `92b73bd4f77d…`, both times, pasted.
  The register stage's verdict-as-data output is in the run's outputs
  (whatever the gate said, the pipeline is green and the verdict is legible).
Accept when: green run transcript (all stages, on-cluster, full data,
detached, status JSON complete); cache-hit rerun transcript with visibly
cached stages and a wall-clock a fraction of run 1; alias unchanged pasted
twice; `make pipeline` idempotent in the make-target sense (re-invoke =
rerun, never a half-state); PR green + lineage.
Evidence plan: both run transcripts + per-stage status JSON + the two alias
read-backs + the Flyte console/CLI run listing.
Safe stop: after the green run is verified complete (even before the
cache-hit rerun — the rerun is a fresh session's first command if the split
is needed).

### M4-S5 — Kill-a-pod, the marts tail task, and `make verify-m4` that can go red  (role:MLOps, SRE hat for the kill drill)
Do:
- **Kill-a-pod retry (the third §9 leg)**: during a pipeline run (sampled/
  `--no-gate` run is LEGAL here — the drill tests the ORCHESTRATOR's retry,
  no verdict is claimed; F-008 honored by construction), `kubectl delete pod`
  on the currently-running task pod; Flyte retries; the run completes; the
  retry visible in the run's event history. Predicted signature written
  BEFORE the kill (the gameday discipline, early): which stage, what the
  event log should show, idempotence argument for the killed stage (every
  stage is idempotent by M1/M2 construction — cite the story that proved it).
- **D-003 decided at the moment it becomes real**: the marts build+publish
  (`dbt build --no-partial-parse` + publish) added as the pipeline's tail
  task (§9/M1-S6's quoted sentence). WITH the decision the debt row demands:
  incremental materialisation, or full-refresh kept with the 23 GB peak
  re-measured on THIS run and the reasoning recorded. The tail task is
  `--no-promote`-compatible: it publishes marts from data, it does not touch
  the registry.
- **`make verify-m4` real** (the M2/M3 gate-writing law, all of it): re-fits
  NOTHING, re-reads and re-checks — Flyte control plane healthy · the LAST
  completed pipeline run's stages and outputs coherent (status JSON ↔ Flyte
  run state ↔ MLflow run existence) · cache evidence present · the kill
  drill's retry event present in history · in-container D-004 check (image's
  OpenMP is the system's) · `@champion` unchanged (F-016 law) · marts row
  counts reconcile post-tail-task · no skip flag, no fast mode · **properties,
  not literals** (F-017/gotchas #49-50: pin no run-id, no experiment name, no
  floor name — `tests/unit/test_verify_m3.py`'s pinning test is the template).
- **`make verify-m4-redteam`**: break the POINTER-class thing, never the
  state — e.g. tamper ONE stage's status JSON (the M3 pattern: a wrong
  NUMBER, restored byte-identical under an EXIT trap, sha256 before/after)
  → verify-m4 RED naming it while unrelated sub-checks still run; restore →
  GREEN.
Accept when: kill-drill transcript with predicted-then-observed signature;
D-003 ledger row CLOSED (decision + measurement recorded); tail task in the
pipeline and marts reconcile after it; `verify-m4` GREEN with its sub-check
count stated; redteam RED-then-GREEN with sha256 restore proof; PR green +
lineage. Exit: `automation/next_session.sh architect 120` (no ◆ at M4).
Evidence plan: the drill transcript · the D-003 decision text + measured
number · verify-m4 and redteam transcripts (committed, the M3 precedent).
Safe stop: after merge — M4's gate exists and can say no; the boundary
session inherits a checkable milestone.

## Out of scope (named now so creep is visible later)
- **Serving anything** (KServe, parity, PRR) — M5's, including F-009's real
  fix and F-019's policy decision.
- **Promoting anything** — no M4 run moves `@champion`; F-016 waits on the PO.
- **Retraining/tuning campaigns** — the pipeline RUNS training; nobody asked
  it to find a better model. F-020's transfer measurement is M7's.
- **Image slimming / multi-arch / registry infrastructure** — `kind load` is
  the decided bridge; revisit at the next sanctioned rebuild.
- **Restore rehearsal for the S2 backup** — named M6-gameday candidate; M4
  ships the lifeboat, not the drill.
- **Scheduling** (cron'd monthly runs) — M7's, with drift. M4 proves the
  pipeline runs ON DEMAND parametrized by month.
- **A second orchestrator opinion** — ADR-001 chose Flyte; ADR-002 chose the
  fallback. The wall rule executes, it does not reopen the choice.

## Risks & walls (carried counts restated; fallbacks cite ADRs)

| Risk / wall | Count | Fallback |
|---|---|---|
| Flyte 2.x on kind fights (deploy or MLflow interop) | 3 attempts | ADR-002: flyte-binary 1.16.x executes WITHOUT a new decision; record which attempt failed and why |
| In-pod full-data training OOMs or starves the node (44M rows, ~25 min host-side; 3 kind nodes share the VM's 47Gi) | 3 attempts | Explicit task resources first (≈24Gi train task), then reduce LightGBM `num_threads`/dataset construction memory — NEVER `--train-months` for a verdict-bearing run (F-008); if the wall stands, the train task is the one story allowed to raise it as a fork (a pipeline that cannot fit full data on this hardware is a direction question) |
| The statefulness law collides with a story ("just rebuild" temptation: new hostPort, extraMounts, containerd patch) | 0 tolerated | This kickoff's top law + D-001's bridge decision; anything genuinely needing a rebuild → written up, parked for a PO-sanctioned rebuild window with the S2 backup as precondition (restore rehearsal first — which is why it is out of scope to need one now) |
| `uv add flytekit` drags or downgrades core pins (gotcha #36's shape; flytekit's dep graph is wide) | 1 check per add | Check pandas/numpy/scikit-learn/mlflow-skinny versions at add time, exactly as M3-S2/S4 did; a downgrade is a stop-and-think, not a shrug |
| Long on-cluster runs vs session lifecycle (gotcha #45) | standing | `make detach` + status JSONs per stage (M3-S4's proven pattern); the S4 story EXPECTS to end its session with the run detached and liftoff verified |
| dbt-in-pipeline re-meets gotcha #38 (partial-parse cache records paths) | standing | `--no-partial-parse` everywhere the pipeline invokes dbt, pinned by the tail-task's own test |
| MLflow client inside pods needs MinIO creds (gotcha #5/#39's impostor) | standing | Tasks configure via `taxi_mlops.training.tracking.configure()` — the ONE path that sets artifacts + credentials; secrets reach pods as env from the existing secret machinery, never baked into the image |
| Optuna storage / registry accidentally touched by pipeline runs | 0 tolerated | `--no-promote` law + verify-m4's alias assertion; the pipeline imports the same `registry.py` whose no-delete property is pinned |

## Open PO questions (options · recommendation · default-with-date)
- **AWAITING_PO 2026-08-18-1 (F-016, incumbent margin)** — NEW this boundary.
  Options A (keep as-is) / B (0.50% transition-cost margin, recommended, cost
  stated) / C (full 2.00%). Parks ONLY incumbent-condition edits; M4 runs in
  full without the answer; becomes blocking at M7's first retrain promotion;
  silence through the M6→M7 boundary = the pre-registered gate stands (status
  quo, not an auto-adopted recommendation).
- **AWAITING_PO 2026-08-16-2 (allowlist)** and **2026-08-17-1 (host
  libgomp)** — standing, non-blocking, unchanged. Note: after M4-S3, D-004
  makes the container path shim-free regardless of -1's answer.

## ARCH self-check (v3.0)
model stated Fable: **yes** (first line) · every story sized for one short
executor session: **yes — S4 is the fat one and its safe-stop explicitly
permits splitting the cache-hit rerun into the next session; S2 and S5 each
carry a detach-or-finish note** · debt intake diffed against ledgers/debt.md:
**yes — D-001/D-003/D-004 are the only open rows, all land here, none
re-carried; D-002 closed at M1** · forks routed to AWAITING_PO: **yes — F-016
(2026-08-18-1); F-018/F-019/F-020/F-021 are defects with owners and landings,
not direction forks; nothing else met the bar** · findings dispositioned with
quoted landings: **yes — §0 table, every id** · the statefulness law is stated
where the executor cannot miss it: **yes — top of file, §preconditions row,
two risk rows, and inside S2/S3/S4's Do lists**.
