# ADR-005 — DVC versions data; Flyte is the ONLY DAG owner
- Status: accepted
- Date: 2026-08-12
- Context: dvc repro + Flyte would create two DAG owners — a classic confusion tax.
- Choice: dvc add/push inside pipeline tasks only; no dvc.yaml pipelines.
- Revisit trigger: none foreseen; supersede if Flyte is ever removed.
