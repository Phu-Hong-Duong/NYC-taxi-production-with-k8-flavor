# data/ — DVC-managed from M1-S2; nothing here enters git except the manifest.

```
raw/                       monthly TLC parquet as downloaded (immutable)
processed/<split>/         cleaned + typed outputs, filed under their split
processed/<split>/*.rejections.json   the per-rule drop counts for that month
raw_manifest.json          sha256 pin of every raw file — THE tracked artifact here
```

Source URL pattern (verified 2026-08-12, re-verified 2026-08-16 — `HTTP/2 200`):
`https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_YYYY-MM.parquet`
It lives in `configs/data.yaml`, not in code.

**Build it:** `make ingest` (all 8 configured months) or
`uv run python -m taxi_mlops.data ingest --month 2019-03`.
Which months, and which split each belongs to, come from `configs/train.yaml`.

**The manifest is a pin, not a log.** It carries no timestamps, so re-running
ingest rewrites it byte-identically. A diff on `raw_manifest.json` therefore
always means the DATA moved — which for TLC is a real event, not an accident
(gotcha #6: months get backfilled in place). Ingest refuses rather than adopting
new bytes silently; adopting them is a deliberate edit.

**Nothing is dropped quietly.** Every removed row is attributed to a named rule
from `configs/data.yaml:clean.rules`, counted twice (first-violated, and
independent hits so a shadowed rule cannot read as dead), printed by ingest, and
written next to the parquet it explains. Observed for 2019-01…08:
57,042,337 rows in → 56,127,878 out, 1.603% rejected.

`raw/` and `processed/` are gitignored: raw is DVC's from S2 on, processed is
regenerable by the command above.
