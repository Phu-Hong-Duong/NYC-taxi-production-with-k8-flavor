# Metabase — the BI seat, and why its boards live in git

`make deploy-metabase` puts Metabase on the cluster and converges these boards
onto it. `make boards` does the boards alone. `make verify-m1` checks the result
by asking the **running instance**, not by reading this directory.

## The one rule

**A board is a file here, not a thing somebody clicked.**

A dashboard built in the browser exists in exactly one place — the app-db of the
machine it was built on. It cannot be reviewed in a pull request, it cannot be
rebuilt after `make destroy`, and when a number moves nobody can say what
changed. `docs/prior_art.md` records "dashboards provisioned from checked-in
JSON" as an ADOPT; this directory is where it landed.

The consequence worth stating plainly: **edits made in the Metabase UI to a card
this repo owns are overwritten by the next `make boards`.** That is the point.
Explore freely in the UI; when you want an exploration to become a board, write
it here.

## The shape of a board file

```jsonc
{
  "name": "Data health",          // matched by name — this is the idempotence key
  "description": "…",
  "cards": [
    {
      "name": "KPI-02 · rejection rate SERIES, by month",
      "kpi": "KPI-02",            // MUST be an id docs/kpi_definitions.md defines
      "display": "line",          // scalar | line | bar | table
      "row": 3, "col": 12,        // Metabase's grid is 24 columns wide
      "size_x": 12, "size_y": 6,
      "sql": "SELECT … FROM marts.monthly_kpis ORDER BY month",
      "visualization_settings": { "graph.dimensions": ["month"], … }
    }
  ]
}
```

`kpi` is not decoration. The ids are the contract between these boards, M2's
error memo and M7's drift memos — `tests/unit/test_metabase.py` fails if a card
cites an id `docs/kpi_definitions.md` does not define, which is the failure that
otherwise renders perfectly and means nothing.

## What the tests refuse, and why

These run without a cluster (`uv run pytest tests/unit -q`):

| Refusal | The failure it prevents |
|---|---|
| No card may cite or name **KPI-09 / KPI-10** | gotcha #15. They are measured only by `taxi_mlops.training.evaluate` on held-out data. A BI card computing a model metric from a warehouse table is a scout leaderboard wearing a reported number's name. |
| **KPI-08's value and its excluded-row count share a card** | AI-2. 3,131 excluded rows (0.0056%) move `CORR(fare, duration)` by 11.8× while moving the mean 0.36%. A money KPI without its exclusion count is a claim, not a measurement. |
| **KPI-03 renders every rule, including the permanently-zero ones** | A rule you cannot see cannot be seen to *start* firing. No `HAVING`, no `> 0` filter. |
| **KPI-02 is plotted as a series** | The observed 2019 rate rises monotonically 1.428% → 2.020%. An average hides exactly what the board exists to show — and the ingest guard (10% refusal) sees none of it. |
| Every card queries a **mart**; none reads parquet or the analyst DuckDB | The marts are the served layer. A card reading parquet would give the repo a second definition of `split`/`month`, and Metabase cannot reach an embedded engine anyway. |
| Cards fit the **24-column grid** | An overflowing card does not error; Metabase silently reflows it, so the board a reviewer approved is not the board that renders. |
| Card names are **unique across both boards** | Idempotence is by name: two cards sharing one would overwrite each other every run. |

## Idempotence, and the one thing this script will not do

Cards and dashboards are matched on `name` and updated in place (`PUT`), so a
second run leaves the same ids and a dashcard keeps its position. The script
**adds and updates; it never archives or deletes** — the same asymmetry
`scripts/postgres_databases.sh` follows. Removing a card from a board file leaves
the old card in Metabase, unlinked. Destroying is `make destroy`'s job, out loud.

## Credentials

Admin and warehouse credentials come from `.env` via
`scripts/platform_secrets.sh`, which generates them on first need and never
prints them. Metabase connects to the warehouse as the **`marts`** role, never as
the Postgres superuser. Nothing here belongs in git.
