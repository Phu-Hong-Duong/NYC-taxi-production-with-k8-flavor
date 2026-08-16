"""Train, evaluate, register. Owner milestone: M2.

- train_baseline(splits, cfg): zone-x-hour median predictor -> MLflow run.
- train_model(splits, cfg): LightGBM -> MLflow run (params, metrics, model with
  signature + input_example — signature is NON-OPTIONAL: mlserver needs it).
- evaluate(run, splits, cfg) -> metrics dict (test-month MAE/RMSE).
- maybe_promote(run, cfg): applies champion alias IFF gate passes
  (configs/promotion.yaml, written BEFORE first training run). Prints both numbers
  and the verdict — the refusal message is a deliverable (BLUEPRINT M2).
"""
