"""SCRATCH — deleted before commit. Verify a handful of memo claims."""

import duckdb

con = duckdb.connect("data/analyst.duckdb", read_only=True)
for sql in [
    "select split, round(avg(actual_minutes),4) as mean_actual, count(*) as n"
    " from predictions group by split order by split",
    "select round(100.0*count(*) filter (where actual_minutes>60)/count(*),4) as pct_over_60"
    " from predictions where split='test'",
]:
    print(con.execute(sql).fetchall())
