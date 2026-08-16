# Debt register — carried obligations. A carry is legal ONLY with a landing
# milestone that exists in BLUEPRINT §9 and whose quoted scope covers the need
# (gotcha #19). Intake at the landing milestone's kickoff is mandatory (Prompt E);
# a slide without an explicit re-disposition blocks closure (Prompt G §4).
| Id | Raised (Mx, date) | What is owed | Why not fixed then | Landing M | Quoted landing scope | Status |
|---|---|---|---|---|---|---|
| D-001 | M0-S2, 2026-08-16 | Decide how OUR images reach the kind nodes: local-registry pattern (`containerdConfigPatches` in `infra/kind/kind-config.yaml`) **or** `kind load docker-image` (gotcha #3). The kind config carried this as an undated `TODO(M0)`. | M0 builds and runs no image of ours — the platform at M0-S3 is upstream helm charts (MinIO/Postgres/MLflow) pulled from registries. Deciding now would be a guess ratified by nothing; gotcha #3 only bites once a locally-built image must run on-cluster. Re-tagged `TODO(M4)` in the config so the note cannot drift back to "M0" silently. | **M4** | BLUEPRINT §9/M4: "v1's M3 unchanged: Flyte 2 per docs, **containerized**, ingest→validate→features→train→evaluate→register parametrized by month" — containerized tasks are exactly the first images we build that must run inside the kind nodes. | open |
