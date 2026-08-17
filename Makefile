# mlops-nyc-taxi — THE interface. Every target idempotent; every capability has a verify twin.
# Stubs echo their contract until their milestone lands. Tabs, not spaces. v2 numbering (BLUEPRINT §9).

SHELL := /bin/bash
MONTH ?= 2019-09

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
.PHONY: zones gate-redteam predictions-redteam automl tune verify-m3
zones: ## derive the 263 TLC zone centroids from the sha256-pinned shapefile (M3-S2; --refresh re-downloads)
	@uv run python scripts/derive_zone_centroids.py $(ZONES_ARGS)
gate-redteam: ## prove the gate refuses a challenger that beats the FLOOR and is worse than the CHAMPION (M3-S1, F-011)
	@uv run python scripts/gate_redteam_incumbent.py
predictions-redteam: ## prove a floor fitted on the wrong window cannot be published (M3-S1, F-012)
	@bash scripts/predictions_redteam.sh
automl: ## FLAML scout under configs/automl.yaml time budget -> scout report
	@echo "TODO(M3): python -m taxi_mlops.tuning scout"
tune: ## Optuna study (Postgres-backed, resumable) centered on scout winner
	@echo "TODO(M3): python -m taxi_mlops.tuning study"
verify-m3: ## dossier+ablation+leakage red-team; kill/resume; >=1 pruned trial; 5 gate verdicts from our evaluator
	@echo "TODO(M3)"

# ---- M4 pipeline on-cluster (role:MLOPS + role:MLE) ----
.PHONY: deploy-flyte pipeline verify-m4
deploy-flyte: ## Flyte 2 on kind (ADR-002 fallback: flyte-binary 1.16.x)
	@echo "TODO(M4)"
pipeline: ## full workflow for MONTH=$(MONTH) on-cluster
	@echo "TODO(M4): pyflyte run --remote pipelines/flyte/workflows.py ... month=$(MONTH)"
verify-m4: ## green run + cache-hit rerun + kill-a-pod retry survives
	@echo "TODO(M4)"

# ---- M5 serving & release (role:MLOPS + role:SRE PRR) ----
.PHONY: deploy-kserve serve verify-m5
deploy-kserve: ## KServe Standard mode + storage-config secret -> MinIO
	@echo "TODO(M5)"
serve: ## InferenceService from champion alias (mlserver runtime); PRR minutes precede go-live
	@echo "TODO(M5): kubectl apply -f infra/manifests/inferenceservice.yaml"
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
