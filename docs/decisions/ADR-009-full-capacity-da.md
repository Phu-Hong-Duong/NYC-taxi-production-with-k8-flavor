# ADR-009 — DA at full capacity: dbt marts + Metabase BI, with the marts boundary law
- Status: accepted (PO direction)
- Date: 2026-08-12
- Context: PO direction, verbatim: "I want DA participates in this project at
  full capacity. ... please help me to see its full functionally of DA role in
  Kubernetes environment. Or maybe do what Claude known best, because DA role
  probably is hard to perform in k8 ecosystem. Meanwhile you may modify,
  update, change, improve and tell me rationale behind that decision."
- Resolution of "DA in k8s": the analyst consumes URLs; the platform hosts the
  tools. Three layers: DuckDB = local exploration workbench (embedded engine —
  cannot back a served BI); dbt-built GOLD MARTS published to the one Postgres
  = served warehouse layer; Metabase (one container, app-db in Postgres, port
  3030) = BI layer. Mart refresh runs as ONE Flyte task from M4 (dbt's internal
  DAG is within-task; Flyte owns WHEN — ADR-005 stands).
- Options considered for the BI seat: Metabase (chosen — enterprise-BI shaped,
  one container, Postgres-native) · Superset (rejected: Redis+workers, heavy)
  · Streamlit (rejected: an app, not self-service BI; predecessor already
  taught it) · Grafana (rejected: SRE-owned, telemetry-shaped).
- AMENDS an earlier conversational stance ("no dbt in this project") with a
  boundary instead of a ban: dbt owns ANALYST MARTS ONLY. **Boundary law
  (gotcha #22): marts serve humans and never feed the model** — a mart
  aggregate that looks model-worthy graduates via the feature dossier and the
  shared features path, never by direct import. Model features stay in Python;
  the skew law is untouched.
- Honest cost: two new tools; M1 grows to ~two sessions; Metabase adds ~0.5-1GB
  RAM. Revisit trigger: if boards go stale/unused by M7, propose cutting BI
  scope as a PO fork rather than carrying decoration.

- AMENDMENT (2026-08-12, by marker — ADR body immutable): hardware fact updated
  to 64 GB RAM (user-stated). The RAM leg of the Superset rejection is void; the
  complexity-per-lesson leg stands, and the marts-in-Postgres interface makes
  the BI seat cheap to swap. PO default recorded: Metabase stands unless the PO
  says "Superset" (would land as ADR-010; ~15-minute change, boards rebuilt).
