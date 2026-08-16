{{
  config(
    materialized = 'view',
    tags = ['fact', 'large']
  )
}}

-- trips_clean — the published trip-level fact (BLUEPRINT §9/M1-S6).
--
-- MATERIALISED AS A VIEW HERE, AS A TABLE IN POSTGRES. The same reasoning the
-- analyst layer wrote down at M1-S2: nothing in DuckDB needs to copy 56M rows
-- that already exist as parquet, and a view can never go stale against them.
-- Postgres is different — it is the SERVED warehouse (Metabase cannot query an
-- embedded engine), so scripts/marts.sh materialises this view over the wire.
-- Cost of that choice, measured and not hidden: ~7 GB of CSV through
-- `kubectl exec` and ~8 GB in the Postgres volume, paid again on every
-- `make marts`. Undo: publish only the aggregates and let Metabase lose
-- self-service at trip grain.
--
-- WHAT THIS MODEL ADDS to the source view: the four segment dimensions
-- docs/kpi_definitions.md names ("Segment dimensions every board should
-- support"), computed ONCE here so six boards cannot compute `hour` six ways.
-- Nothing is filtered and nothing is renamed — the contract already decided
-- what a clean trip is, and a mart that re-decides it is a second contract.
--
-- BOUNDARY LAW (ADR-009, gotcha #22): this serves humans. Model code never
-- imports it; a mart aggregate that looks model-worthy graduates through the
-- feature dossier and the shared features path, never by import.

with source as (

    select * from {{ source('analyst', 'trips_clean') }}

    {% if var('red_team', false) %}
    -- RED-TEAM PATH — off by default and never set by `make marts`.
    -- `dbt build --vars '{red_team: true}'` unions the out-of-contract fixture
    -- in seeds/redteam/, which must turn the accepted_range test on
    -- trip_duration_minutes RED. A test nobody has watched fail is not a test
    -- (gotcha #29). See seeds/redteam/README.md.
    -- BY NAME, so the fixture carries nine readable columns instead of a
    -- 22-column transcription that would drift from the contract next year.
    union all by name
    select * from {{ ref('redteam_bad_trips') }}
    {% endif %}

)

select
    *,
    -- Segment dimensions, defined once (kpi_definitions.md §"Segment dimensions")
    cast(tpep_pickup_datetime as date)              as pickup_date,
    extract(hour from tpep_pickup_datetime)         as pickup_hour,
    -- DuckDB's dayofweek: 0 = Sunday. Spelled out because "day 4" on a board is
    -- an argument waiting to happen.
    dayofweek(tpep_pickup_datetime)                 as pickup_dow,
    dayname(tpep_pickup_datetime)                   as pickup_dow_name

from source
