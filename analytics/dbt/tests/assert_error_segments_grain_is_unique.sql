-- error_segments' grain, asserted rather than assumed.
--
-- Same failure this repo already guards for `zone_hourly_stats`, and here it has
-- a second door: the model is eight UNION ALL branches, so a copy-pasted branch
-- that forgets to change its segment label would double a dimension's rows and
-- halve every share on the board without changing a single MAE.
--
-- Returns duplicated grain keys; empty means the grain holds.

select split, segment, segment_value, count(*) as rows_at_this_grain
from {{ ref('error_segments') }}
group by 1, 2, 3
having count(*) > 1
