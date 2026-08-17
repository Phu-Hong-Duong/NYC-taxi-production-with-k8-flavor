-- The mart's whole-split row must BE the evaluator's number, not resemble it.
--
-- `error_segments` publishes KPI-11 and KPI-12 — segment MAE and segment
-- within-tolerance rate — computed in SQL over the rows
-- `taxi_mlops.training.evaluate` published. Aggregated over an entire split
-- those two are the same arithmetic over the same rows as KPI-09 and KPI-10, so
-- they must come out identical to four decimals. If they do not, the SQL layer
-- is filtering, duplicating or losing rows on the way to the board, and every
-- segment number above it is quietly wrong in the same proportion.
--
-- This is what makes it legitimate for a mart to carry model-error numbers at
-- all (gotcha #15): the ids are new because the window is new, and the value is
-- checked against the one legal producer rather than merely asserted to agree
-- with it. `prediction_runs` reads that producer's own manifest and is never
-- published to Postgres, so no board can render KPI-09/KPI-10 through it.
--
-- Returns the disagreeing splits; empty means the layers agree.

with published as (

    select split, trips, kpi_11_mae_min, kpi_12_within_tol_pct
    from {{ ref('error_segments') }}
    where segment = 'overall'

), measured as (

    select
        split,
        rows,
        kpi_09_mae_minutes,
        kpi_10_within_pct
    from {{ source('analyst', 'prediction_runs') }}
    where contender = model_name || '@' || model_alias

)

select
    p.split,
    p.trips                                                as mart_rows,
    m.rows                                                 as evaluator_rows,
    round(p.kpi_11_mae_min, 4)                             as mart_kpi_11,
    round(m.kpi_09_mae_minutes, 4)                         as evaluator_kpi_09,
    round(p.kpi_12_within_tol_pct, 4)                      as mart_kpi_12,
    round(m.kpi_10_within_pct, 4)                          as evaluator_kpi_10
from published p
join measured m using (split)
where p.trips <> m.rows
   or round(p.kpi_11_mae_min, 4)        <> round(m.kpi_09_mae_minutes, 4)
   or round(p.kpi_12_within_tol_pct, 4) <> round(m.kpi_10_within_pct, 4)
