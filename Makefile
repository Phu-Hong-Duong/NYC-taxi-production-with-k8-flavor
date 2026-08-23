# mlops-nyc-taxi — THE interface. Every target idempotent; every capability has a verify twin.
# Stubs echo their contract until their milestone lands. Tabs, not spaces. v2 numbering (BLUEPRINT §9).

SHELL := /bin/bash
MONTH ?= 2019-09

# The one supported way to run something that must OUTLIVE the session starting
# it (gotcha #45: a Claude Code background task is a CHILD of the session and
# dies with it, which cost the chain 38 minutes on 2026-08-17). It is a make
# target and not just a script call because `make` is the interface every role
# already has: an unattended session should never have to reach past it.
#   make detach NAME=m3s4-automation-track ROLE=executor TARGET=automation-track
# ROLE is the successor the JOB schedules on completion — the launching session
# must then schedule nothing itself (next_session.sh refuses the double anyway).
#
# WHAT A DETACHED .status CAN AND CANNOT TELL YOU (gotcha #97, measured
# 2026-08-20): the detached wrapper records the exit code of the command it
# ran, and here that command is `make`. **GNU make exits 2 for ANY failed
# recipe** — a recipe exiting 1 and a recipe exiting 3 both come back as 2,
# proved by `tests/unit/test_detach_exit_codes.py` against a throwaway
# makefile. So a target whose exit codes carry MEANING (`retrain`: 0 passed ·
# 1 refused · 2 could not build · 3 no verdict · 4 crashed) has that meaning
# collapsed to {0, 2} the moment it is detached this way, and 2 collides with
# a real word. Do not read a verdict out of a .status file: read the RECORD
# the run exists to produce, and treat its ABSENCE as the crash signal
# (gotcha #59 — assert positively on the artifact). The recipes that carry a
# vocabulary echo their own CLI code into the log as well.
.PHONY: detach
detach: ## run a make TARGET detached so it survives this session; the JOB schedules ROLE after (gotcha #45)
	@test -n "$(NAME)"   || { echo "make detach needs NAME=<slug>" >&2; exit 2; }
	@test -n "$(TARGET)" || { echo "make detach needs TARGET=<make target>" >&2; exit 2; }
	@test -n "$(ROLE)"   || { echo "make detach needs ROLE=executor|rev|architect" >&2; exit 2; }
	@automation/run_detached.sh $(NAME) --then-schedule $(ROLE) -- make $(TARGET)

.PHONY: help
help: ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "};{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---- M0 foundations & org bootstrap (role:MLOPS) ----
.PHONY: cluster-up cluster-down destroy ports deploy-platform verify-m0
ports: ## gotcha #10 port pre-check over the CLAUDE.md port family + kind hostPorts
	@bash scripts/port_precheck.sh
cluster-up: ## create kind cluster (idempotent; port pre-check runs before a create)
	@bash scripts/cluster.sh up
cluster-down: ## delete kind cluster only (idempotent)
	@bash scripts/cluster.sh down
destroy: ## full teardown: cluster + regenerable state (NEVER data/raw originals or .env; DRY_RUN=1 to preview)
	@bash scripts/cluster.sh destroy
deploy-platform: ## MinIO + Postgres + MLflow (idempotent; values in infra/helm/*, manifests in infra/manifests/)
	@bash scripts/deploy_platform.sh
verify-m0: ## M0 gate: platform healthy + org docs present (BLUEPRINT §9/M0)
	@bash scripts/verify_m0.sh

# ---- M1 data & analytics platform (role:DE, role:DA) ----
.PHONY: ingest data duckdb ingest-scoring data-scoring contract-probe rebuild-proof marts \
        marts-redteam deploy-metabase boards board-cards verify-m1
ingest: ## download->contract->clean->split, counted rejections, sha256 manifest (M1-S1)
	uv run python -m taxi_mlops.data ingest
data: ## ingest + duckdb layer + dvc add/push (byte-identical rebuilds; SKIP_DVC=1 leaves the pin alone)
	@bash scripts/data_pipeline.sh
duckdb: ## (re)build the DuckDB analyst views and reconcile their counts against the ingest report
	uv run python -m taxi_mlops.data duckdb
ingest-scoring: ## ingest configs/data.yaml scoring.months into data/scoring/ — same contract, separate trees (M7-S1)
	uv run python -m taxi_mlops.data ingest --scoring
data-scoring: ## ingest-scoring + duckdb + dvc pin of the scoring trees; the 2019 pins are asserted untouched (M7-S1)
	@bash scripts/data_pipeline_scoring.sh
contract-probe: ## run any month's REAL file through the contract and report validate-or-refuse; writes nothing (M7-S1)
	uv run python scripts/contract_probe.py $(PROBE_ARGS)
contract-probe-fixtures: ## watch the contract REFUSE three schema-break shapes, exit 1 each, nothing written (M7-S1)
	@bash scripts/contract_probe_fixtures.sh
rebuild-proof: ## wipe data/processed, rebuild from DVC-pinned raw, diff every sha256 (M1-S2 gate leg)
	@bash scripts/rebuild_proof.sh
marts: ## dbt build (models+tests) + publish gold marts to Postgres (SKIP_PUBLISH=1 stops at DuckDB)
	@bash scripts/marts.sh
marts-redteam: ## prove the dbt tests can fail: union the out-of-contract fixture, expect RED
	@RED_TEAM=1 bash scripts/marts.sh
deploy-metabase: ## Metabase container, app-db in Postgres, port 3030, boards from checked-in JSON (M1-S5)
	@bash scripts/deploy_metabase.sh
boards: ## converge the Metabase boards from analytics/metabase/boards/*.json (no deploy)
	uv run python scripts/metabase_boards.py
board-cards: ## execute EVERY board card against the warehouse; an EMPTY panel is a FAILURE (gotcha #78)
	@uv run python scripts/board_cards_execute.py "$(BOARD)"
verify-m1: ## M1 gate: rebuild + DVC match; corrupt-file refusal; dbt tests green (one red-teamed); boards render
	@bash scripts/verify_m1.sh

# ---- M2 modeling I (role:MLE) ----
.PHONY: train train-redteam predictions verify-m2 verify-m2-redteam
train: ## both floors + LightGBM v1 through ONE evaluator, promotion gate on test, champion alias on a pass (exit 1 = refused)
	uv run python -m taxi_mlops.training train
train-redteam: ## prove the gate can say no: a hobbled challenger through the SAME gate, expect REFUSED
	@bash scripts/train_redteam.sh
predictions: ## score the REGISTERED champion on val+test and publish row-level predictions (M2-S4; then make duckdb, make marts)
	uv run python -m taxi_mlops.training predict
verify-m2: ## M2 gate: champion w/ signature; the gate still refuses; predictions reconcile; memo + error board render
	@bash scripts/verify_m2.sh
verify-m2-redteam: ## prove the M2 gate can go RED: drop the champion alias, expect RED naming it, restore, expect GREEN
	@bash scripts/verify_m2_redteam.sh

# ---- M3 modeling II: scout x sniper (role:MLE) ----
.PHONY: zones ablation leakage-redteam gate-redteam predictions-redteam automl tune tune-resume-drill automl-refit automation-track f008-guard bakeoff champion-transition verify-m3 verify-m3-redteam
zones: ## derive the 263 TLC zone centroids from the sha256-pinned shapefile (M3-S2; --refresh re-downloads)
	@uv run python scripts/derive_zone_centroids.py $(ZONES_ARGS)
ablation: ## artisan track: one feature GROUP per experiment on a 15% sample, val only, runs in m3-artisan (M3-S3)
	@uv run python scripts/artisan_ablation.py $(ABLATION_ARGS)
leakage-redteam: ## fit an aggregate across val ON PURPOSE and watch val inflate while an untouched month does not (M3-S3)
	@uv run python scripts/leakage_redteam.py $(LEAKAGE_ARGS)
gate-redteam: ## prove the gate refuses a challenger that beats the FLOOR and is worse than the CHAMPION (M3-S1, F-011)
	@uv run python scripts/gate_redteam_incumbent.py
predictions-redteam: ## prove a floor fitted on the wrong window cannot be published (M3-S1, F-012)
	@bash scripts/predictions_redteam.sh
automl: ## FLAML scout under configs/automl.yaml time budget -> scout verdict (family + starting params); every number scout-internal
	@uv run python scripts/automl_scout.py $(AUTOML_ARGS)
tune: ## Optuna sniper: TPE + MedianPruner, study in the one Postgres, namespaced m3, resumable (M3-S4)
	@uv run python scripts/optuna_sniper.py $(TUNE_ARGS)
tune-resume-drill: ## prove the study outlives its process: kill -9 mid-run, re-run the same command, trial count continues
	@uv run python scripts/sniper_resume_drill.py $(DRILL_ARGS)
automl-refit: ## refit the sniper's winner on the FULL train months through the one evaluator (DR-05; nothing promotes)
	@uv run python scripts/automl_refit.py $(REFIT_ARGS)
automation-track: ## the whole M3-S4 track in order (scout x2 -> sniper x2 -> full-data refit x2) under DR-01's declared budget; ~2.5h, run it DETACHED
	@bash scripts/automation_track.sh
f008-guard: ## exercise M3-S1's F-008 guard on a real sampled run: exit 2 (disqualified) and exit 3 (no verdict issued)
	@uv run python scripts/f008_guard_exercise.py
bakeoff: ## the M3 bake-off: 5 contenders (4 LOADED, floor fitted) through one evaluator on TEST, 5 gate verdicts; promotes nothing without --promote-winner
	@uv run python scripts/bakeoff_m3.py $(BAKEOFF_ARGS)
champion-transition: ## the ordered chain a moved alias owes: promote -> predictions -> duckdb -> marts -> boards -> memo numbers (M3-S5); run it DETACHED
	@bash scripts/champion_transition.sh
verify-m3: ## dossier+ablation+leakage red-team; kill/resume; >=1 pruned trial; 5 gate verdicts from our evaluator
	@bash scripts/verify_m3.sh
verify-m3-redteam: ## prove verify-m3 goes RED: contradict ONE recorded number, watch the replay catch it, restore
	@bash scripts/verify_m3_redteam.sh

# ---- M4 pipeline on-cluster (role:MLOPS + role:MLE) ----
.PHONY: backup deploy-flyte flyte-console flyte-hello image-build image-load image-smoke image-smoke-redteam flyte-actions marts-peak pipeline pipeline-cache-drill pipeline-kill-drill pipeline-local stage-data verify-m4 verify-m4-redteam
MONTH ?= 2019-01
MARTS_MONTHS ?=
# Passed EXPLICITLY into the recipes below rather than relying on make's export
# rules for command-line variables: `make pipeline TRAIN_MONTHS=2019-01` has to
# mean the same thing as `TRAIN_MONTHS=2019-01 bash scripts/run_pipeline.sh`, and
# a variable that silently does not reach the script produces a FULL-DATA run
# where a sampled one was asked for — a 31-minute misunderstanding.
TRAIN_MONTHS ?=
PUBLISH_MARTS ?= 1
image-build: ## build the task image only; the cluster is not touched (M4-S3)
	@bash scripts/image_build_load.sh --build-only
image-load: ## build the task image + kind load onto every node, read back with crictl (M4-S3, D-001; DRY_RUN=1 previews)
	@bash scripts/image_build_load.sh
image-smoke: ## prove the image runs OUR code and that D-004's shim is dead inside it (10 checks, in-container)
	@bash scripts/image_smoke.sh
image-smoke-redteam: ## mask the system libgomp in ONE container: the D-004 checks must all flip (else they measure nothing)
	@bash scripts/image_smoke_redteam.sh
backup: ## the lifeboat: pg_dump every database + mirror every MinIO bucket outside the repo (M4-S2; DRY_RUN=1 previews)
	@bash scripts/platform_backup.sh
deploy-flyte: ## Flyte on kind: databases via D-002, blob store in the existing MinIO (idempotent; ADR-002)
	@bash scripts/deploy_flyte.sh
deploy-serving: ## the serving PLATFORM: ingress-nginx (declared route :8081) + cert-manager + KServe Standard (M5-S1, ADR-004; DRY_RUN=1 previews). Installs NO model
	@bash scripts/deploy_serving.sh
flyte-console: ## forward the Flyte API to localhost:8090 (port-forward, NOT a declared route — see scripts/flyte_console.sh for why)
	@bash scripts/flyte_console.sh
flyte-hello: ## two tasks on-cluster, the second consuming the first's output through MinIO (F-023 closed at M4-S4)
	@bash scripts/flyte_hello.sh
stage-data: ## put the DVC-pinned data trees on the PVC task pods mount (M4-S4; RESTAGE=1 forces, DRY_RUN=1 previews)
	@bash scripts/stage_pipeline_data.sh
flyte-actions: ## read a run's per-stage detail (durations, cache_status, attempts) off the control plane (M4-S5; RUN=<run-name>)
	@bash scripts/flyte_actions.sh
marts-peak: ## D-003: publish the marts under a size probe (MARTS_MONTHS=YYYY-MM scopes the fact table; empty = full refresh)
	@bash scripts/marts_peak_probe.sh $(if $(MARTS_MONTHS),month-scoped-$(MARTS_MONTHS),full-refresh) -- \
	  uv run python scripts/marts_publish.py --duckdb analytics/dbt/marts.duckdb \
	  --transport kubectl --months "$(MARTS_MONTHS)"
pipeline-local: ## rehearse the graph on MONTH=$(MONTH) in plain Python, no orchestrator, NO verdict (M4-S1; --publish adds the marts tail)
	@uv run python pipelines/tasks.py --month $(MONTH) $(PIPELINE_LOCAL_ARGS)
pipeline: ## the seven stages on-cluster for MONTH=$(MONTH) (M4-S4/S5; TRAIN_MONTHS=... makes it a sampled, verdict-free smoke; PUBLISH_MARTS=0 drops the tail)
	@MONTH="$(MONTH)" TRAIN_MONTHS="$(TRAIN_MONTHS)" PUBLISH_MARTS="$(PUBLISH_MARTS)" \
	  bash scripts/run_pipeline.sh
pipeline-cache-drill: ## run the pipeline TWICE and prove run 2 reused run 1 (M4-S4; DRILL_STAGE=ingest is the 1-min mechanism probe)
	@bash scripts/pipeline_cache_drill.sh
pipeline-kill-drill: ## delete the pod a stage is running in and prove the run finishes anyway (M4-S5; prediction written BEFORE the kill)
	@bash scripts/pipeline_kill_drill.sh
verify-m4: ## green run + cache-hit rerun + kill-a-pod retry survives + the marts tail; re-runs NOTHING
	@bash scripts/verify_m4.sh
verify-m4-redteam: ## prove verify-m4 goes RED: contradict ONE recorded cache status, watch the corroboration catch it, restore
	@bash scripts/verify_m4_redteam.sh

# ---- M5 serving & release (role:MLOPS + role:SRE PRR) ----
.PHONY: holidays serve quote parity parity-redteam load load-drill
.PHONY: stop-start-drill verify-m5 verify-m5-redteam
HOLIDAYS_TO ?= 2030
holidays: ## re-derive data/reference/us_federal_holidays.csv from 5 U.S.C. §6103 (M5-S2, F-019; HOLIDAYS_TO=YYYY moves the horizon)
	@uv run python scripts/derive_us_federal_holidays.py --to $(HOLIDAYS_TO)
serve: ## the champion on the wire: read-only MinIO identity + ServingRuntime + InferenceService from the ALIAS (M5-S2; DRY_RUN=1 previews)
	@bash scripts/deploy_champion.sh
quote: ## ask the live endpoint for one quote through the ONE feature path (M5-S2; QUOTE_ARGS="--at 2019-07-04T09:15")
	@uv run python -m taxi_mlops.serving $(QUOTE_ARGS)
shadow: ## registry version 1 as a second InferenceService with ZERO rider traffic (M6-S3; DRY_RUN=1 previews, TEARDOWN=1 removes)
	@bash scripts/deploy_shadow.sh
shadow-run: ## dual-send the same requests to champion and shadow, write the disagreement table (M6-S3; a READER)
	@uv run python -m taxi_mlops.serving.shadow $(SHADOW_ARGS)
canary-spike: ## ADR-004's spike, MEASURED: can ingress-nginx split traffic here? (M6-S3; --dry-run previews)
	@uv run python scripts/canary_spike_probe.py $(SPIKE_ARGS)
parity: ## THE parity test: one matrix, scored offline AND on the wire, max |delta| <= 1e-6 minutes (M5-S3; a READER — deploys nothing, moves no alias)
	@uv run python -m taxi_mlops.serving.parity $(PARITY_ARGS)
parity-redteam: ## prove the parity test can go RED without touching the served model (M5-S3)
	@bash scripts/parity_redteam.sh
load: ## drive the declared route at a STATED rate for a STATED window; p95 never printed without its shape (M5-S4)
	@uv run python -m taxi_mlops.serving.load $(LOAD_ARGS)
load-drill: ## ramp -> headline p95/p99 -> kill the predictor MID-LOAD and measure the outage (M5-S4; ~7 min, run it DETACHED)
	@uv run python scripts/serving_load_drill.py $(DRILL_ARGS)
stop-start-drill: ## stop the InferenceService, start it again, TIME both (M5-S5; the runbook's §3 evidence — a real ~20s outage)
	@uv run python scripts/serving_stop_start_rehearsal.py
verify-m5: ## the route + the champion on the wire + parity + p95 + self-heal + the PRR; re-runs NOTHING expensive
	@bash scripts/verify_m5.sh
verify-m5-redteam: ## prove verify-m5 goes RED: rewrite ONE recorded number, watch the anchors and the runbook contradict it, restore
	@bash scripts/verify_m5_redteam.sh

# ---- M6 reliability (role:SRE) ----
.PHONY: deploy-monitoring monitoring-accept probe-mlserver-metrics alert-rules alert-fire-drill
.PHONY: canary-deploy canary rollback gameday restore-drill verify-m6 verify-m6-redteam
deploy-monitoring: ## Prometheus + Alertmanager + kube-state-metrics + Grafana, through the EXISTING 8081 route (M6-S1)
	@bash scripts/deploy_monitoring.sh
monitoring-accept: ## the accept twin: targets up, ONE real quote moves a counter, every board query answers
	@uv run python scripts/monitoring_accept.py $(ACCEPT_ARGS)
alert-rules: ## validate the checked-in alert rules (A-ids, severities, and every threshold's written argument) — M6-S2
	@uv run python scripts/render_alert_rules.py --check
alert-fire-drill: ## fire A-3 then A-2 for real against the live stack, prediction written FIRST (M6-S2; ~8 min, no outage)
	@uv run python scripts/alert_fire_drill.py $(DRILL_ARGS)
probe-mlserver-metrics: ## ask the live predictor where its /metrics really is (never the docs — gotcha #70)
	@uv run python scripts/probe_mlserver_metrics.py

# ---- M7-S3 drift detection (role:SRE) ----
.PHONY: drift-headroom drift drift-drill drift-witness drift-monotonicity drift-persistence-drill push-serving-version
drift-headroom: ## the held-out 2019 months against the train reference — the input to §8's bar, 2019 data ONLY (M7-S3)
	@uv run python -m taxi_mlops.monitoring headroom
drift: ## compute drift for scoring months; add --push to send it to the gateway (M7-S3). Issues NO verdict
	@uv run python -m taxi_mlops.monitoring $(DRIFT_GATEWAY) drift $(DRIFT_ARGS)
drift-drill: ## push 2020-01..03 and watch the rules decide, prediction written FIRST (M7-S3; ~12 min, no outage, no injection)
	@uv run python scripts/drift_fire_drill.py $(DRILL_ARGS)
drift-witness: ## Evidently beside our SQL PSI — a second instrument on the same question (M7-S3; a READER)
	@uv run python scripts/drift_second_witness.py $(WITNESS_ARGS)
drift-monotonicity: ## F-051's counterfactual through the SHIPPED arithmetic: a deeper collapse must lower A-9's ratio (M8-S1; a READER)
	@uv run python scripts/f051_counterfactual.py $(F051_ARGS)
drift-persistence-drill: ## F-050's pair: the store survives a pod delete, and A-11 pages when the series are gone (M8-S1; ~18 min, prediction FIRST, no outage)
	@uv run python scripts/drift_persistence_drill.py $(PERSISTENCE_ARGS)
push-serving-version: ## A-4's two series: what the wire serves vs what @champion resolves to (M7-S3, F-035)
	@uv run python scripts/push_serving_version.py $(A4_ARGS)
canary-deploy: ## the challenger PATH carrying the champion's own bytes; proves ADR-011 condition 2 (M6-S4; DRY_RUN=1 previews, TEARDOWN=1 removes)
	@bash scripts/deploy_canary.sh
canary: ## shift 10% -> 100% -> revert under sustained load, split observed from COUNTERS (M6-S4; DRILL_ARGS=--dry-run)
	@uv run python scripts/canary_release_drill.py $(DRILL_ARGS)
rollback: ## F-032's un-rehearsed half, run for real: @champion v2->v1->v2, all three moves, timed (M6-S4)
	@uv run python scripts/alias_rollback_rehearsal.py $(ROLLBACK_ARGS)
gameday: ## staged failures w/ predicted signatures; positive control fires first (M6-S5; GAMEDAY_ARGS="--scenario predict")
	@uv run python scripts/gameday_m6.py $(GAMEDAY_ARGS)
restore-drill: ## restore the newest backup's small dumps into SCRATCH databases and verify them (M6-S5; the live databases are never touched)
	@uv run python scripts/restore_rehearsal.py $(RESTORE_ARGS)
verify-m6: ## the eyes + the SLOs + shadow-before-canary + 90/10 observed + rollback under load + the gameday; re-runs NOTHING
	@bash scripts/verify_m6.sh
verify-m6-redteam: ## prove verify-m6 goes RED: rewrite ONE recorded field, watch two artifacts contradict it, restore
	@bash scripts/verify_m6_redteam.sh

# ---- M7 drift & retrain loop (role:SRE + role:MLE + role:DA) ----
.PHONY: predictions-scoring retrain retrain-prediction-check retrain-schedule verify-m7 verify-m7-redteam
predictions-scoring: ## score the REGISTERED champion on the SCORING months and publish the rows (M7-S2; then make duckdb, make marts). SCORING_ARGS="--months YYYY-MM" narrows; monitoring ids KPI-14..17, never KPI-09/10
	uv run python -m taxi_mlops.training score-scoring $(SCORING_ARGS)
retrain: ## M7-S4: fit the CHAMPION's configuration re-derived at the scale it is fitted at (F-020) and let the gate decide. Promotes NOTHING (CLI exit 0 promote-worthy · 1 refused · 2 could not build · 3 no verdict · 4 crashed — and see the `detach` header: make collapses every one of those to 2). RETRAIN_ARGS="--plan-only" is the seconds-long provenance check
	@uv run python -m taxi_mlops.training retrain $(RETRAIN_ARGS); rc=$$?; \
	 echo "[retrain] CLI exit code: $$rc  (0 passed · 1 refused · 2 could not build · 3 no verdict · 4 crashed;"; \
	 echo "[retrain] make reports 2 for any non-zero recipe, so THIS line is the vocabulary — gotcha #97)"; \
	 exit $$rc
retrain-prediction-check: ## M7-S4: judge the retrain RECORD against the prediction written before the fit ran; exit 1 on any exact mismatch. A READER — two files, no live system, no fit
	@uv run python scripts/retrain_prediction_check.py $(PREDICTION_CHECK_ARGS)
retrain-schedule: ## M7-S4: deploy the retrain task and its two triggers, then read them back off the SERVER (never off the file that was submitted)
	@bash scripts/retrain_schedule.sh $(SCHEDULE_ARGS)
verify-m7: ## the scoring months + the two failure signatures + the predictions table + the drift bars + the retrain that said no; re-runs NOTHING
	@bash scripts/verify_m7.sh
verify-m7-redteam: ## prove verify-m7 goes RED: rewrite ONE recorded ratio, watch its anchors, its second witness and the memo contradict it, restore
	@bash scripts/verify_m7_redteam.sh

# ---- M8 feature store (role:DE + role:MLE) ----
.PHONY: transformer-probe deploy-transformer transformer-accept transformer-parity transformer-load feast-server-parity deploy-feast-server feast-server-image feast-serve-probe deploy-feast verify-m8 verify-m8-redteam backfill-provenance feast-quarantine feast-sources feast-apply feast-plan feast-plan-check feast-registry feast-rows feast-retrieval deploy-feast-store feast-materialize feast-online-parity
feast-quarantine: ## M8-S2: build the ISOLATED feast venv from its exact pins and prove it never touched uv.lock. --resolve rewrites the pins; --check builds nothing
	@bash scripts/feast_quarantine.sh $(QUARANTINE_ARGS)
feast-sources: ## M8-S2: build the parquet Feast reads, from the SETTLED trees, into data/feast/ (read-only; --static-only skips the 43.9M-row aggregate fit)
	@uv run python scripts/feast_sources.py $(SOURCES_ARGS)
feast-apply: ## M8-S2: register the git-defined entities and views into the (gitignored, regenerable) local registry — runs INSIDE the quarantine
	@cd infra/feast/feature_repo && uv run --no-project --python $(CURDIR)/.venv-feast/bin/python feast apply
feast-plan: ## M8-S2: what `feast apply` WOULD change, raw — for a human. `feast-plan-check` is the instrument
	@cd infra/feast/feature_repo && uv run --no-project --python $(CURDIR)/.venv-feast/bin/python feast plan
feast-plan-check: ## M8-S2 (F-055): `feast plan` can never say "no changes" — this asserts every reported diff is the re-stamped clock and NOTHING else. Exit 1 on a substantive diff
	@uv run python scripts/feast_plan_check.py $(PLAN_ARGS)
feast-registry: ## M8-S2: read the APPLIED registry back and record it (runs inside the quarantine — the deploy-scripts idiom: never trust the file you submitted)
	@uv run --no-project --python $(CURDIR)/.venv-feast/bin/python python scripts/feast_registry_dump.py $(REGISTRY_ARGS)
feast-rows: ## M8-S3: print the COMMITTED row set the retrieval parity is measured on. ROWS_ARGS=--refresh rebuilds it, which changes the set every published number was measured on
	@uv run python scripts/feast_retrieval_rows.py $(ROWS_ARGS)
feast-retrieval: ## M8-S3: historical-retrieval parity (store vs the ONE feature path, bar EXACT) + the point-in-time proof (honest vs naive join). A READER — deploys nothing, fits only the truth it compares against
	@uv run python scripts/feast_retrieval.py $(RETRIEVAL_ARGS)
backfill-provenance: ## M8-S1 (F-048): write the SCALE a version's count-scaled knobs were chosen at ONTO the version, derived from the tracked records. Additive tags only — creates no version, deletes nothing, never reads or moves an alias. BACKFILL_ARGS=--dry-run resolves and writes nothing
	@uv run python scripts/backfill_version_provenance.py $(BACKFILL_ARGS)
deploy-feast-store: ## M8-S4 (ADR-012): the ONLINE store — one in-cluster Redis, no hostPort, and NO features. DRY_RUN=1 mutates nothing; TEARDOWN=1 deletes it and its PVC
	@bash scripts/deploy_feast_store.sh
feast-materialize: ## M8-S4: fill the online store from the offline parquet, through an ephemeral port-forward, INSIDE the quarantine. MATERIALIZE_ARGS=--dry-run writes nothing
	@bash scripts/feast_materialize.sh $(MATERIALIZE_ARGS)
feast-online-parity: ## M8-S4: THE 100-pair online/offline parity table — get_online_features vs the offline retrieval, bar EXACT (S3's, inherited). A READER: deploys nothing, materializes nothing
	@uv run python scripts/feast_online_parity.py $(PARITY_ARGS)
feast-online-parity-redteam: ## M8-S4: prove the parity table can go RED — copy one OD pair's real bytes onto another's key, watch the named column fail while the rest pass, restore byte-identically
	@bash scripts/feast_online_parity_redteam.sh
feast-server-parity: ## M8-S4 leg 2: the feature server's answers vs the champion's OWN lookup, bar EXACT (argued in docs/feast_server_m8.md §3 before it ran). A READER
	@uv run python scripts/feast_server_parity.py $(SERVER_PARITY_ARGS)
deploy-feast-server: ## M8-S4 leg 2: the quarantined feature server ON THE CLUSTER. Accept = a real online lookup asked from another pod, both halves. DRY_RUN=1 / TEARDOWN=1
	@bash scripts/deploy_feast_server.sh
feast-server-image: ## M8-S4 leg 2: build the QUARANTINED feature server (pandas 2, feast SDK) and kind-load it onto every node. DRY_RUN=1 builds nothing
	@bash scripts/build_feast_server.sh
feast-serve-probe: ## M8-S4 leg 2: the CHEAP PROBE in front of an image build — can `feast serve` answer an online lookup at all, on the host, in the quarantine? ~30 s
	@bash scripts/feast_serve_probe.sh
transformer-probe: ## M8-S4 leg 3: the CHEAP PROBE in front of an image build and a KServe deploy — the whole request path, in THIS process, against the two real services. ~1 min
	@uv run python scripts/transformer_probe.py $(PROBE_ARGS)
deploy-transformer: ## M8-S4 leg 3: the transformer BESIDE the champion — a second isvc, the same champion bytes, features built in the pod. DRY_RUN=1 / TEARDOWN=1
	@bash scripts/deploy_transformer.sh
transformer-accept: ## M8-S4 leg 3: the accept twin — a RAW request answered, the store proved consulted, the champion's name 404ing, a past-horizon quote refused
	@uv run python scripts/transformer_accept.py $(ACCEPT_ARGS)
transformer-parity: ## M8-S4 leg 3: THE parity through the NEW seam — 16 hazards as RAW requests vs the same rows host-built through the champion's isvc. Bar EXACT (argued first). A READER
	@uv run python scripts/transformer_parity.py $(TRANSFORMER_PARITY_ARGS)
transformer-load: ## M8-S4 leg 3: p95 on the transformer path at M5-S4's shape (4 req/s, 60 s, concurrency 8, open loop) — the NEW boundary's number beside the old one
	@uv run python scripts/transformer_load.py $(TRANSFORMER_LOAD_ARGS)
deploy-feast: ## M8: the whole feature-store path — store, sources, apply, materialize
	@$(MAKE) deploy-feast-store && $(MAKE) feast-apply && $(MAKE) feast-materialize
verify-m8: ## M8 gate: the quarantine's invariant, four seams against bars argued before them, the PIT proof, five live questions, and the comparison page. RE-RUNS NOTHING
	@bash scripts/verify_m8.sh
verify-m8-redteam: ## prove `make verify-m8` can go RED: one online value rewritten inside the bar's neighbourhood in the 100-pair record, then restored
	@bash scripts/verify_m8_redteam.sh

# ---- M9 stretch (demo committed by PO direction 2026-08-12) ----
.PHONY: demo
demo: ## serve/open the stakeholder demo page against the live InferenceService
	@echo "TODO(M9): port-forward + open demo/eta.html (see demo/README.md)"

# ---- always available ----
.PHONY: lint test fmt
lint: ## ruff check
	uv run ruff check src tests pipelines
fmt: ## ruff format
	uv run ruff format src tests pipelines
test: ## unit tests only (cluster-free)
	uv run pytest tests/unit -q
