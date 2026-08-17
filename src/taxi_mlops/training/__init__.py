"""Train, evaluate, register. Owner milestone: M2.

Landed at M2-S2 (role:MLE):
- `datasets.load_split(...)` — the blessed months, narrowed to v1's columns.
- `baselines.ConstantMedian` / `baselines.GroupMedian` — the flattering floor and
  the honest one, with an explicit, COUNTED unseen-group fallback.
- `model.fit(...)` — LightGBM v1 on feature set v1; params from configs/train.yaml.
- `evaluate.evaluate(...)` — **THE metric source** (gotcha #15). KPI-09 and KPI-10
  have no other origin in this program, and both baselines are scored through it
  so the comparison is between predictors rather than between instruments.
- `run.run(...)` — one invocation, every contender, one table.
- `tracking.configure(...)` — the client half of gotcha #5 (artifacts go straight
  to MinIO; the server does not proxy them).
- `openmp.ensure_openmp()` — this host ships no libgomp; see the module docstring
  and debt D-004.

Still M2-S3's, and deliberately absent here: `train_model`'s promotion gate,
`maybe_promote`, the `champion` alias, and `make train`. Nothing in this package
writes to the model registry.
"""
