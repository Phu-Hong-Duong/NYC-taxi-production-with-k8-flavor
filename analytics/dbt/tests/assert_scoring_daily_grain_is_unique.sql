-- scoring_daily's grain, asserted rather than assumed.
--
-- (month, pickup_date) is the whole grain. It has a specific way of going wrong
-- that neither of this repo's other grain tests has: `month` is a config literal
-- carried through the ingest, while `pickup_date` comes off the trip's own
-- timestamp — so a row whose pickup falls outside the month it was filed under
-- (a late-night trip at a month boundary, a mislabelled file) lands as an extra
-- (month, date) pair rather than as a duplicate. That does not break the grain
-- and is deliberately NOT what this test looks for; `assert_scoring_daily_reconcile`
-- is what would catch a mislabelled file, by counting rows.
--
-- Returns duplicated grain keys; empty means the grain holds.

select month, pickup_date, count(*) as rows_at_this_grain
from {{ ref('scoring_daily') }}
group by 1, 2
having count(*) > 1
