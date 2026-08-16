-- The reconciliation, carried into the published layer.
--
-- `make duckdb` already refuses to build an analyst layer whose view row counts
-- disagree with the ingest report that wrote the data (M1-S2). This asserts the
-- same equality one layer further out: the number of rows the FACT MART holds
-- for a month must equal the `rows_out` the ingest claimed for it.
--
-- Why it is worth restating: a mart that quietly loses (or gains) rows answers
-- every question happily, just with different numbers. There is no symptom on
-- a dashboard. This test is the symptom.
--
-- Returns the offending months; empty means the layers agree.

select
    month,
    kpi_01_trips_ingested,
    trips_in_mart,
    trips_in_mart - kpi_01_trips_ingested as difference
from {{ ref('monthly_kpis') }}
where trips_in_mart <> kpi_01_trips_ingested
