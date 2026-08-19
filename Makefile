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
.PHONY: ingest data duckdb rebuild-proof marts marts-redteam deploy-metabase boards verify-m1
ingest: ## download->contract->clean->split, counted rejections, sha256 manifest (M1-S1)
	uv run python -m taxi_mlops.data ingest
data: ## ingest + duckdb layer + dvc add/push (byte-identical rebuilds; SKIP_DVC=1 leaves the pin alone)
	@bash scripts/data_pipeline.sh
duckdb: ## (re)build the DuckDB analyst views and reconcile their counts against the ingest report
	uv run python -m taxi_mlops.data duckdb
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
.PHONY: holidays serve quote verify-m5
HOLIDAYS_TO ?= 2030
holidays: ## re-derive data/reference/us_federal_holidays.csv from 5 U.S.C. §6103 (M5-S2, F-019; HOLIDAYS_TO=YYYY moves the horizon)
	@uv run python scripts/derive_us_federal_holidays.py --to $(HOLIDAYS_TO)
serve: ## the champion on the wire: read-only MinIO identity + ServingRuntime + InferenceService from the ALIAS (M5-S2; DRY_RUN=1 previews)
	@bash scripts/deploy_champion.sh
quote: ## ask the live endpoint for one quote through the ONE feature path (M5-S2; QUOTE_ARGS="--at 2019-07-04T09:15")
	@uv run python -m taxi_mlops.serving $(QUOTE_ARGS)
verify-m5: ## THE parity test (offline==online 1e-6) + p95 under 60s load + PRR minutes exist
	@echo "TODO(M5): pytest tests/smoke -m smoke"

# ---- M6 reliability (role:SRE) ----
.PHONY: deploy-monitoring canary rollback gameday verify-m6
deploy-monitoring: ## kube-prometheus-stack + Grafana + Pushgateway
	@echo "TODO(M6)"
canary: ## shift 10% to challenger under synthetic load (revert typed & tested FIRST)
	@echo "TODO(M6)"
rollback: ## the rehearsed revert (exists before canary ever runs)
	@echo "TODO(M6)"
gameday: ## staged failures w/ predicted signatures; positive control fires first
	@echo "TODO(M6): see docs/rituals/ gameday template"
verify-m6: ; @echo "TODO(M6): 90/10 observed; rollback <2min under load; alert fired; gameday record complete"

# ---- M7 drift & retrain loop (role:SRE + role:MLE + role:DA) ----
.PHONY: drift-report verify-m7
drift-report: ## Evidently reference-vs-MONTH -> pushgateway + MLflow artifact
	@echo "TODO(M7): MONTH=$(MONTH)"
verify-m7: ; @echo "TODO(M7): 2020-03 drift alarm + 2025-01 schema refusal (distinct signatures) + DA memo"

# ---- M8 feature store (role:DE + role:MLE) ----
.PHONY: deploy-feast verify-m8
deploy-feast: ## Feast + Redis; materialize; transformer wiring
	@echo "TODO(M8)"
verify-m8: ; @echo "TODO(M8): 100-pair online/offline parity + traced enriched request + prior-art revisit"

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
