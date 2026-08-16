-- zone_hourly_stats' grain, asserted rather than assumed.
--
-- The GROUP BY says the grain is (month, split, pickup_zone, pickup_hour). If a
-- future edit adds a column to the select list and forgets the group by — the
-- single most common way an aggregate mart breaks — the row count doubles and
-- every average on the board halves silently. dbt_utils has
-- `unique_combination_of_columns` for this; we own twelve lines instead of a
-- package fetch, for the same reason as macros/test_accepted_range.sql.
--
-- Returns duplicated grain keys; empty means the grain holds.

select month, split, pickup_zone, pickup_hour, count(*) as rows_at_this_grain
from {{ ref('zone_hourly_stats') }}
group by 1, 2, 3, 4
having count(*) > 1
