# seeds/redteam — the fixture that must turn a test red

`redteam_bad_trips.csv` holds two trips that the data contract would never have
let through: one lasting **999.5 minutes** (the contract rejects anything over
120) and one lasting **0.2 minutes** (it rejects anything under 1).

They enter `trips_clean` **only** when dbt is run with
`--vars '{red_team: true}'`, which is what `make marts-redteam` does and what
`make marts` never does. `trips_clean` unions them with `UNION ALL BY NAME`, so
the columns the fixture does not carry arrive as NULL and the fixture stays two
readable lines instead of a 22-column transcription.

## Why a checked-in fixture instead of a hand-edit

The protocol requires one dbt test to be **seen failing** before the marts ship
(DA charter; gotcha #29 — "a check whose failing branch nobody has watched fire
is not a check"). The cheap way to satisfy that is to break something by hand
once, paste the red output, and put it back. The transcript then proves the test
worked on one afternoon in 2026.

This way the red-team is a command. `make marts-redteam` re-proves it on any
day, on any machine, and `make verify-m1` can call it as a gate leg — which is
the difference between evidence and a souvenir.

## The two rows are chosen, not random

* Both use `PULocationID = 161` (Midtown Center) at hour 14 — one of the
  busiest zone-hours in the data. That keeps the group large, so
  `zone_hourly_stats`' median does not move and the failure lands where it was
  aimed: the fact table's `accepted_range` on `trip_duration_minutes`.
## What the run actually looks like (observed 2026-08-16)

```
Done. PASS=19 WARN=0 ERROR=1 SKIP=19 NO-OP=0 REUSED=0 TOTAL=39
ERROR: in test accepted_range_trips_clean_trip_duration_minutes__120__1
  Got 2 results, configured to fail if != 0
```

**The 19 SKIPs are the interesting number, and they were not the prediction.**
This README first claimed the reconciliation test would also go *red*, because
the mart would hold two rows the ingest report never claimed. It does not — it
is **skipped**, along with `zone_hourly_stats`, `monthly_kpis` and all their
tests. `dbt build` interleaves tests with models, so a fact table that fails QA
is never handed to the aggregates built on it. The bad rows do not propagate and
then get caught downstream; they never get downstream at all. That is a stronger
guarantee than the one this file predicted, and it is written down here because
the prediction was wrong.

The run also **restores itself**: the failed build still created `trips_clean`
with the fixture unioned in, so `scripts/marts.sh` rebuilds green before exiting.
Postgres is never touched — the publish lives in the half of that script the
red-team branch never reaches.
