# data/ — DVC-managed from M1-S2; nothing here enters git except the manifest.

```
raw/                       monthly TLC parquet as downloaded (immutable) — DVC-tracked
processed/<split>/         cleaned + typed outputs, filed under their split — DVC-tracked
processed/<split>/*.rejections.json   the per-rule drop counts for that month
raw_manifest.json          sha256 pin of every raw file — tracked by git
raw.dvc, processed.dvc     the DVC pins — tracked by git; the bytes are not
analyst.duckdb             the analyst layer's views (regenerable, gitignored)
```

Source URL pattern (verified 2026-08-12, re-verified 2026-08-16 — `HTTP/2 200`):
`https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_YYYY-MM.parquet`
It lives in `configs/data.yaml`, not in code.

**Build it all:** `make data` — ingest → DuckDB views → DVC pin + push, in that
order and no other (DVC pins what the earlier steps produced; running it first
would push the previous run's bytes). Pieces: `make ingest`, `make duckdb`, or
`uv run python -m taxi_mlops.data ingest --month 2019-03`.
Which months, and which split each belongs to, come from `configs/train.yaml`.

## The analyst layer (M1-S2)

`make duckdb` builds `data/analyst.duckdb` — **views, not copies**, over
`data/processed/`. The DA queries these names and never a parquet path:

| view | one row per | what it is for |
|---|---|---|
| `trips_clean` | trip | every configured month, labelled `split` + `month` |
| `trips_train` / `trips_val` / `trips_test` | trip | the same, filtered by split |
| `ingest_months` | month | rows in / out / rejected, from S1's report |
| `ingest_rejections` | month × rule | `rejected_by` and `matched` per named rule |
| `raw_manifest` | month | the raw file's bytes and sha256 pin (provenance) |
| `data_health` | month | the join of the three above — the S5 board's source |

`split` and `month` are literals taken from `configs/train.yaml`, never parsed
out of a filename: a renamed file must not be able to relabel data. Ask it
anything: `uv run python -m taxi_mlops.data query "SELECT * FROM data_health"`.

`make duckdb` exits 1 if any view's row count disagrees with the ingest report
that wrote the data — a catalogue pointing at five months of eight answers every
query happily, just with smaller numbers.

## DVC (M1-S2)

`dvc init` with **analytics off** (`core.analytics = false`): the default sends
usage data off this machine, and this program's rule is that nothing does.

The remote is a plain directory **outside the repo**:
`/home/longt/dvc-remote/nyc-taxi`. It is deliberately not MinIO — MinIO lives on
a PVC inside the kind cluster, and `make destroy` takes PVCs with it, so the
"backup" would die with the thing it was meant to survive. Outside the repo, so
re-cloning cannot orphan it. Honest limit: it is on the same physical disk, so
it protects against a wrong `rm -rf` in the repo and against `make destroy` —
**not** against disk loss. Nothing here is irreplaceable except the pins: the
raw bytes are re-fetchable from TLC (subject to gotcha #6), and everything else
rebuilds from them.

**Prove the rebuild:** `make rebuild-proof` deletes `data/processed/`, rebuilds
it with one command from DVC-pinned raw, and compares every sha256 — with two
independent witnesses, our own hashes and DVC's. `DRY_RUN=1` previews.

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

`raw/` and `processed/` are hidden from git by **`data/.gitignore`, which DVC
wrote and owns** — the root `.gitignore` deliberately no longer repeats them.
Two copies would be twins, and a stale copy in the root would keep hiding the
data even if DVC tracking were lost, which is exactly the failure you want loud.
