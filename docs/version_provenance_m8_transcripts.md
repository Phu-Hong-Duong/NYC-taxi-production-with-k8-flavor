# M8-S1 leg 2 — transcripts (pasted, not remembered)

Companion to `docs/version_provenance_m8.md`. Every block below is real output
from this session (2026-08-21, EXEC/Opus 5, role block MLOps A).

## §1 The backfill — dry run, then the write, then idempotence

```
$ make backfill-provenance BACKFILL_ARGS=--dry-run
[backfill] nyc-taxi-eta: 2 version(s)  — DRY RUN, nothing will be written
[backfill] version 1 (run 3adee05a855a…): no sampled search
[backfill]            source: no refit record under automation/runs/m3s4 names run
                      3adee05a855a424bb664c7fea3735703: this version's params were not
                      chosen on a sample, so there is no transfer to make
[backfill] version 2 (run 92b73bd4f77d…): 6,598,113 rows, cap 800
[backfill]            source: automation/runs/m3s4/sniper-v2.json (study m3-sniper-v2,
                      sample_fraction 0.15), backfilled by backfill_version_provenance.py
[backfill] 0 version(s) changed; no alias was read or moved, no version was created,
           nothing was deleted

$ make backfill-provenance
[backfill] version 1 … WROTE search_scale_round_cap, search_scale_rows, search_scale_source
[backfill] version 2 … WROTE search_scale_round_cap, search_scale_rows, search_scale_source
[backfill] 2 version(s) changed; no alias was read or moved, no version was created,
           nothing was deleted

$ make backfill-provenance          # again
[backfill]            unchanged (already carries exactly this)
[backfill]            unchanged (already carries exactly this)
[backfill] 0 version(s) changed; …
```

The alias, read either side of the write:

```
ALIAS champion -> 2 | tags: ['feature_set', 'gate_challenger_mae',
 'gate_challenger_within_rate', 'gate_floor', 'gate_floor_mae',
 'gate_floor_within_rate', 'gate_holdout_split', 'gate_incumbent_version',
 'gate_observed_pct', 'gate_required_pct', 'gate_verdict', 'metric_source']
```

## §2 The host, resolving the scale from the REGISTRY

```
$ make retrain RETRAIN_ARGS=--plan-only
[retrain] champion   : version 2 (auto-lgbm-v2, run 92b73bd4f77d…), feature set v2
[retrain] F-020 (1)  : count-scaled knobs chosen on 6,598,113 rows, fitting on 43,987,422
                       -> factor 6.6667 (registry: nyc-taxi-eta version 2 tag
                       search_scale_rows (recorded from automation/runs/m3s4/sniper-v2.json
                       (study m3-sniper-v2, sample_fraction 0.15), backfilled by
                       backfill_version_provenance.py))
[retrain]              min_data_in_leaf: 1293 -> 8620 — 1 row in 5,103 where it was chosen;
                       unchanged here it would be 1 in 34,020 (F-020); rescaled it is 1 in 5,103
[retrain] F-020 (2)  : rounds 500 configured / 800 inherited -> 2400
[retrain] CLI exit code: 0
```

## §3 The image — F-047's closing condition

The set of tests to mark was MEASURED twice. In the image at
`taxi-mlops-pipeline:72a4013` (the pre-story artifact):

```
$ docker run --rm taxi-mlops-pipeline:72a4013 python -m pytest tests/unit -q
…
12 failed, 862 passed, 17 skipped in 69.93s
```

and on the host with `automation/runs/` hidden (an EXIT-trapped rename, restored in
the same command), against the CURRENT tree, which has more record-readers than
that image ever saw:

```
18 failed, 918 passed, 12 skipped in 57.99s
[probe] records restored -> True
```

After marking, the same host probe with the marker deselected — the in-image
condition, simulated where it is cheap:

```
915 passed, 12 skipped, 21 deselected in 60.47s
[probe] records restored -> True
```

And then for real, on a freshly built image:

```
$ make image-load
  image      : taxi-mlops-pipeline:5edf9fd   (tree dirty: no)
  loaded in 28s
  ok    mlops-taxi-worker2: sha256:8e20e0b191cd…
  ok    mlops-taxi-control-plane: sha256:8e20e0b191cd…
  ok    mlops-taxi-worker: sha256:8e20e0b191cd…

$ make image-smoke
ok    libgomp1 installed by dpkg: libgomp1 14.2.0-19
ok    the loader resolves libgomp.so.1 from a system lib dir — not from a wheel
ok    openmp_status() -> (True, 'system libgomp.so.1') (first line, nothing printed before it)
ok    ensure_openmp() -> openmp: system libgomp.so.1
ok    no '[openmp]' announcement anywhere in the output — the shim never ran
ok    lightgbm, xgboost, flaml, pandas, sklearn, pyarrow, mlflow, flyte imported with no shim line
ok    every package version in the image matches the host venv
     928 passed, 19 skipped, 22 deselected in 68.00s (0:01:08)
ok    tests/unit green in-image: 928 passed,
ok    validate(2019-01) passed the output contract inside the image
ok    no shim directory and no libgomp.so.1 SONAME inside the venv
== verdict =====================================================
GREEN — 10/10 checks passed for taxi-mlops-pipeline:5edf9fd.
```

The run BEFORE that one is worth keeping, because the smoke earned its keep: it
went RED 9/1 on two tests this session had just written or touched — the
two-absences test, whose "visible directory" arm pointed at a directory the image
does not have, and `test_detach_exit_codes`, which needs a `make` binary the image
has never had. Neither was about the image being wrong.

## §4 The schedule, and the on-cluster proof

```
$ make retrain-schedule
[schedule] triggers, READ BACK OFF THE SERVER:
 taxi-pipeline-train.retrain │ retrain-schedule-proof │ every 20 minutes starting at now │ True
 taxi-pipeline-train.retrain │ retrain-monthly        │ cron: 0 3 1 * * (UTC)            │ False
```

**Before** — the reader's first run, five consecutive firings of the proof trigger
on the pre-story task version `6d5b536b975b…`, F-048 alive in every one:

```
$ uv run python scripts/retrain_proof_record.py --limit 5
[proof] run          : rf156a0512f7f3e14  (SUCCEEDED, 2026-08-21T06:11:54+00:00)
[proof] task version : 6d5b536b975b7814c829cb3ef2bcbaf8
[proof] champion     : version 2
[proof] target_rows  : 43,987,422
[proof] rescale_factor: None
[proof] round_cap     : 500
[proof] decision      : PLAN_ONLY  promoted=False
[proof] FAIL the pod resolved F-020's scale transfer: expected 6.6667, observed None
[proof] FAIL the pod re-derived the round budget: expected 2400, observed 500
[proof] ok   the proof trigger plans only and promotes nothing
rc: 1
```

**After** — the first firing on the new task version, 20 minutes later:

```
$ uv run python scripts/retrain_proof_record.py --limit 8 \
    --out automation/runs/m8-provenance/proof.json
[proof] run          : rdc1f3841bd6455e6  (SUCCEEDED, 2026-08-21T06:31:54+00:00)
[proof] task version : cfe8dc01a11527facc8cbc329e1df85a
[proof] champion     : version 2
[proof] target_rows  : 43,987,422
[proof] rescale_factor: 6.666666969783633
[proof] round_cap     : 2400
[proof] decision      : PLAN_ONLY  promoted=False
[proof] ok   the pod resolved F-020's scale transfer: expected 6.6667, observed 6.6667
[proof] ok   the pod re-derived the round budget: expected 2400, observed 2400
[proof] ok   the proof trigger plans only and promotes nothing: expected True, observed True
rc: 0
```

The record carries `earlier_runs_seen`, so the before and the after sit in ONE
file and a reviewer does not have to take the contrast on trust — seven
consecutive firings of the same trigger, twenty minutes apart, on the same
champion:

```
06:31:54Z rdc1f3841bd6455e6 v=cfe8dc01a115 factor=6.666666969783633 cap=2400
06:11:54Z rf156a0512f7f3e14 v=6d5b536b975b factor=None              cap=500
05:51:54Z rfe2504b7ad8e1c27 v=6d5b536b975b factor=None              cap=500
05:31:54Z rd29eacea4f50f291 v=6d5b536b975b factor=None              cap=500
05:11:54Z r7eb2dcd906efb3ab v=6d5b536b975b factor=None              cap=500
04:51:54Z r9102f147320ad87a v=6d5b536b975b factor=None              cap=500
04:31:54Z r3b7f1135e84eb164 v=6d5b536b975b factor=None              cap=500
04:11:54Z rd18a2924023473b6 v=6d5b536b975b factor=None              cap=500
```

One more fact the polling produced, worth writing down: **the firing at 06:11:54Z
still ran the OLD task version even though the redeploy had already returned.** A
trigger fires the version that was registered when it fired; the redeploy takes
effect at the NEXT tick. Nothing is wrong with that — but "I deployed it, so the
next run is the new code" is an assumption, and here it was false for one run.
