"""AutoML scout + Optuna sniper. Owner milestone: M3 (role:MLE).

Contracts (implement at M3):
- run_scout(splits, cfg) -> ScoutReport
    FLAML under configs/automl.yaml time budget. Report labels every internal
    number "scout-internal"; carries winning family + starting params. NEVER
    writes to the registry.
- run_study(splits, scout: ScoutReport, cfg) -> StudySummary
    Optuna study in the platform Postgres (resumable — kill/resume is an M3
    acceptance arm); space centered on scout winner; each trial an MLflow nested
    run; pruning active and PROVEN (>=1 pruned trial in acceptance).
- Best trial -> ordinary challenger via training.maybe_promote — the SAME gate
  as every other contender. No side doors; this module cannot import the gate
  to modify it, only invoke it.

Rule inherited as scar tissue: AutoML-internal CV can flip sign vs held-out
truth. Any number leaving this module was recomputed by training.evaluate.
"""
