"""The automation track (M3-S4): the FLAML scout and the Optuna sniper.

Design Review **DR-03** draws the line this package lives on: *the automation
track searches HYPERPARAMETERS and is handed feature sets it does not invent.*
Nothing here builds a feature, reads `configs/features.yaml` for anything but a
set NAME, or touches the promotion gate — those axes belong to the artisan (S3)
and to the gate (S1) respectively, and the 2×2 bake-off at S5 can only answer
"features or tuning?" if neither track wanders into the other's column.

Two rules are load-bearing enough to be restated where the code is:

- **Gotcha #15.** FLAML's leaderboard and Optuna's trial values are
  *scout-internal*. They are hypotheses about which family and which
  hyperparameters to try; a RESULT is what `taxi_mlops.training.evaluate`
  computes. Every number this package prints that did not come from the
  evaluator is labelled as such on the line that prints it.
- **F-008.** Scout and sniper iterate on SAMPLES by design, and a sampled run
  degrades the gate's floor faster than it degrades a model. Everything logged
  from here is tagged `sample_run=yes` / `do_not_promote`; the two contenders
  the bake-off actually judges are refit on the full configured train months
  first.
"""
