# ADR-007 — AutoML as scout (FLAML), Optuna as sniper, gate as judge
- Status: accepted
- Date: 2026-08-12
- Context: principal's mandate, quoted in BLUEPRINT §2 ("the convenience of
  autoML framework combined with Optuna or Raytune to tune the best model return
  from autoMl").
- Options: FLAML+Optuna · AutoGluon+Optuna · Ray Tune now · AutoML-only.
- Choice: FLAML scout (pip-light, no core-stack downgrade pressure) -> Optuna
  sniper (Postgres-backed resumable studies, MLflow-nested, pruned) -> the
  unchanged promotion gate judges all contenders. Ray Tune deferred to M9
  stretch on KubeRay (one tuning lesson at a time). AutoGluon available on PO
  request ONLY under the predecessor's quarantine pattern: separate venv,
  exchanges predictions only, scored by our metrics module — inherited tuition:
  its dependency pins downgrade the core stack, and internal leaderboards have
  flipped sign against held-out truth.
- Revisit trigger: PO opts into M9 (Ray) or requests AutoGluon.
