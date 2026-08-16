# analytics/dbt — the DA's gold marts (M1-S6; role:DA)
dbt-duckdb builds marts from processed data; a publish step lands them in the
one Postgres for Metabase. Planned models: trips_clean · zone_hourly_stats ·
monthly_kpis (KPI ids cite docs' definitions). dbt tests are the DA's own QA
layer (red-teamed once on a seeded bad fixture, per protocol).
BOUNDARY LAW (gotcha #22, ADR-009): these marts serve HUMANS — model code never
imports them. Runs as one Flyte task from M4 (`make marts` before that).
