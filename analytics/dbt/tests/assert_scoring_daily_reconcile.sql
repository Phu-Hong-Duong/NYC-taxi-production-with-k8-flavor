-- ingest -> predictions -> mart, in one statement, or the build fails.
--
-- The kickoff's clause for M7-S2 is "row counts reconcile ingest -> predictions
-- -> mart or the build exits 1", and this is the third link of that chain; the
-- first two are `taxi_mlops.data.analyst`'s fourth and sixth reconciliations,
-- which exit 1 inside `make duckdb` before dbt is ever invoked. Checking it here
-- as well is not redundant: those run against DuckDB at build time, and this one
-- travels with the mart into the publish, so a mart rebuilt from a half-written
-- view cannot reach Postgres.
--
-- THE AUTHORITY IS THE INGEST REPORT, not the predictions file. Comparing the
-- mart against the predictions view alone would prove that SQL can sum a column:
-- if the batch job scored 14 of 15.4M rows, mart and predictions would agree
-- perfectly and both would be wrong. `scoring_months.rows_out` is what the
-- contract said it wrote, and it is the same authority every other view in this
-- program is checked against (M1-S2's law).
--
-- Only months PRESENT IN THE MART are checked. A scoring month that is ingested
-- but not yet scored is a normal state — `make data-scoring` and
-- `make predictions-scoring` are two commands on purpose — and a test that
-- failed on it would fail for a correct system, which is how a guard becomes a
-- formality (gotcha #50).
--
-- Returns the disagreeing months; empty means the three layers agree.

with mart as (

    select month, sum(kpi_17_scored_trips) as mart_rows
    from {{ ref('scoring_daily') }}
    group by 1

), scored as (

    select month, count(*) as prediction_rows
    from {{ source('analyst', 'scoring_predictions') }}
    group by 1

), ingested as (

    select month, rows_out as ingest_rows
    from {{ source('analyst', 'scoring_months') }}

)

select
    m.month,
    m.mart_rows,
    s.prediction_rows,
    i.ingest_rows
from mart m
left join scored s using (month)
left join ingested i using (month)
where s.prediction_rows is null
   or i.ingest_rows is null
   or m.mart_rows <> s.prediction_rows
   or m.mart_rows <> i.ingest_rows
