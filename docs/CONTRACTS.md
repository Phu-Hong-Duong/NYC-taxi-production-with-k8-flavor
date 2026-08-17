# CONTRACTS — where every contract in this repo lives (an index, not a copy)

This project has no `contracts/` directory ON PURPOSE: contracts here are
executable and live beside their enforcement, so they cannot drift from it.
This page is the map. It duplicates nothing — one source of truth per contract,
everything else links (protocol §6).

| Contract | Home (source of truth) | Enforced by / when |
|---|---|---|
| Data contract | pandera schemas, `src/taxi_mlops/data/` (year-aware; ALL casting here) | every ingest from M1; red-teamed with a corrupt file; refusals are loud with counted reasons |
| Analytics contract | dbt model schemas + tests, `analytics/dbt/` | every mart build (`make marts`; Flyte task from M4) — the DA's own QA layer |
| Train↔serve contract | MLflow model signature + input example (logged at M2, non-optional) | read by mlserver at M5 — it IS the serving payload shape; parity test proves fidelity to 1e-6 |
| Feature contracts | `configs/features.yaml` (sets by name; every serving feature names its request-time source — gotcha #21) → Feast FeatureViews at M8 | training joins (point-in-time) + the KServe transformer |
| Interface laws | BLUEPRINT five laws: one storage story · one DAG owner · one features path · one gate · decisions wait | structural + tests (M5 parity, M8 consistency) + gotcha checks (#19–#23) |
| Org contracts | `docs/org/ROLES.md` charters (refusal criteria) + ORG.md RACI & independence rules | every session's role-blocks; ledgers record crossings |

Roles, precisely: the DATA contract is the **DE's** artifact. The **DA**
challenges it at the M1 Data Contract Review (minutes → `docs/rituals/` — the
only contract *document*, and it records the argument, not the rule) and owns
KPI definitions, dbt tests, marts, boards, and memos.

When a centralized contracts directory WOULD be right: the moment a contract
must cross a repo/team boundary (a second consumer repo, a streaming source →
schema registry, a published API spec). That day, adding `contracts/` or a
registry is a PO fork — until then, executable-beside-enforcement wins.
