{{ config(materialized = 'table', tags = ['aggregate', 'kpi']) }}

-- rejections_by_rule — KPI-03 at the grain it is defined on.
--
-- NOT ONE OF THE THREE MARTS THE BLUEPRINT NAMES, and added deliberately rather
-- than by drift. The reason is a boundary the other three cannot cross:
-- M1-S5's data-health board must render KPI-03 ("rejections attributed per
-- rule"), Metabase can only query POSTGRES, and `ingest_rejections` lives in
-- the DuckDB analyst layer — which is an embedded engine no served BI tool can
-- reach (BLUEPRINT §3 says exactly this). Without this model the KPI is defined,
-- computable, and unrenderable. Its grain is (month, rule), which is neither
-- monthly_kpis' nor zone_hourly_stats', so it cannot be a column on either.
--
-- BOTH COUNTS ARE PUBLISHED, and that is KPI-03's whole point. `rejected_by` is
-- first-violated attribution and sums exactly to rows dropped; `matched` is
-- independent hits. A rule shadowed by an earlier one reads 0 in the first
-- column and must not be presumed dead — `distance_non_positive` is attributed
-- 117,932 rows and matches 465,911. Rules currently at zero on both counts
-- (`missing_timestamp`, `location_out_of_range`,
-- `passenger_count_out_of_range`) still appear as rows: a rule you cannot see
-- cannot be seen to start firing.

select
    month,
    split,
    rule,
    rejected_by,
    matched
from {{ source('analyst', 'ingest_rejections') }}
