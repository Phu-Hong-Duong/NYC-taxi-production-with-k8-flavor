{{ config(materialized = 'table', tags = ['aggregate', 'kpi']) }}

-- monthly_kpis — one row per month, one COLUMN per KPI id.
--
-- THE COLUMN NAMES ARE THE CONTRACT. Every measure below is named
-- `kpi_NN_<what>` after docs/kpi_definitions.md, because M1-S5's board cards
-- must cite ids and M2's error memo and M7's drift memos cite the same ids.
-- Rule 5 of that document applies here with teeth: **changing a formula changes
-- the id**. If this file ever computes KPI-08 over a different window, the
-- column becomes `kpi_08b_...` — it is not edited in place, or a board's
-- history silently stops meaning one thing.
--
-- KPI-04 IS THE ONE THAT CANNOT BE TAKEN FROM THE OBVIOUS PLACE. The analyst
-- layer's `unknown_domain_values` view is pre-aggregated per (column, value),
-- and 219 trips carry BOTH `VendorID = 5` and `payment_type = 0` — so summing
-- that view returns 527,610 where the honest answer is 527,386 distinct rows
-- (kpi_definitions.md KPI-04, measured 2026-08-16). This model therefore counts
-- distinct ROWS against the documented domains, and takes those domains from
-- `configs/data.yaml:analyst.known_domains` as a dbt var supplied by
-- scripts/marts.sh — never a copy pasted into SQL, which would be the twins
-- failure again. There is deliberately NO default: a missing var must fail the
-- build, because an empty domain list silently reports 100% undocumented.
--
-- KPI-09 and KPI-10 are ABSENT ON PURPOSE. They are model-quality KPIs and
-- `taxi_mlops.training.evaluate` is their only legal source (gotcha #15). A SQL
-- column named kpi_09_* would be a number computed the wrong way that a board
-- would then render as if it were the real one.

{% set domains = var('known_domains') %}

with health as (

    select * from {{ source('analyst', 'data_health') }}

),

facts as (

    select
        month,
        count(*)                                    as trips_in_mart,
        median(trip_duration_minutes)               as kpi_06_median_duration_min,
        quantile_cont(trip_duration_minutes, 0.9)   as kpi_07_p90_duration_min,
        avg(trip_duration_minutes)                  as mean_duration_min,

        -- KPI-08: windowed mean fare, and the count of what the window excluded.
        -- The two travel together by rule — "a windowed number with its
        -- exclusion hidden is worse than an un-windowed one, because it looks
        -- careful" (kpi_definitions.md KPI-08).
        avg(case when fare_amount between 0 and 200 then fare_amount end)
                                                    as kpi_08_mean_fare_windowed,
        count(*) filter (where fare_amount is not null and fare_amount not between 0 and 200)
                                                    as kpi_08_excluded_rows,

        -- KPI-04: distinct rows carrying at least one value the TLC dictionary
        -- does not describe. One predicate per documented column, OR'd.
        count(*) filter (
            where
            {%- for column, allowed in domains.items() %}
                {% if not loop.first %}or {% endif %}(
                    {{ column }} is not null
                    and cast({{ column }} as varchar) not in (
                        {%- for value in allowed -%}
                        '{{ value }}'{% if not loop.last %}, {% endif %}
                        {%- endfor -%}
                    )
                )
            {%- endfor %}
        )                                           as kpi_04_undocumented_rows

    from {{ ref('trips_clean') }}
    group by 1

)

select
    h.month,
    h.split,

    h.rows_out                                              as kpi_01_trips_ingested,
    h.rejected_pct                                          as kpi_02_rejection_rate_pct,
    h.rows_in,
    h.rows_rejected,

    f.kpi_04_undocumented_rows,
    round(100.0 * f.kpi_04_undocumented_rows / h.rows_out, 4)
                                                            as kpi_04_undocumented_pct,

    -- KPI-05 is a provenance BINARY, not a rate: these are the bytes we pinned,
    -- or every other number on the board describes data we did not pin.
    h.raw_sha256                                            as kpi_05_raw_sha256,
    h.raw_file,
    h.raw_bytes,

    f.kpi_06_median_duration_min,
    f.kpi_07_p90_duration_min,
    f.mean_duration_min,
    f.kpi_08_mean_fare_windowed,
    f.kpi_08_excluded_rows,

    -- The reconciliation the analyst layer runs at build time, carried into the
    -- published layer so a board can SEE it: the fact table's own row count
    -- against what the ingest report said it wrote. A schema.yml test asserts
    -- these are equal; this column is why a human can check the test's claim.
    f.trips_in_mart

from health h
join facts f using (month)
