# M1 KICKOFF — Data & analytics platform   (authored by: ARCH/Fable · 2026-08-16 · v3.0: the Architect is sole author)

Session model stated: **Fable 5 (claude-fable-5)** — architect sessions on any
other model are void (ORG.md rule 7).

Story numbering note: this kickoff's S4 and S5 implement what BLUEPRINT §9/M1
names "S6 — Gold marts" and "S7 — BI layer" (that numbering assumed v1's M1
carried S1–S5). The Makefile's `TODO(M1-S6)`/`TODO(M1-S7)` comments refer to
the same work; the executor may retag them when the targets become real.

## 0. Boundary triage of M0 (the closure sweep, folded in)

**Verify re-run (by the approver, this session, 2026-08-16):** `make verify-m0`
→ GREEN, exit 0, all 18 sub-checks `ok`. Closing lines verbatim:
`ok all 11 org/ledger documents present and non-empty` · `ok every charter
carries >= 3 refusals` (PO 3 · DE 4 · DA 6 · MLE 6 · MLOps 5 · SRE 5 · ARCH 8
· REV 5) · `[verify-m0] GREEN — every M0 sub-check passed.`

**Lineage spot-check (gotcha #20):** `git branch -r --contains c6a3a7e`
(M0-S4's story commit) → `origin/main`. Tree clean and level:
`## main...origin/main` at `7811438`.

**Every open finding, condition, and due debt from M0, dispositioned:**

| Item | Disposition |
|---|---|
| F-004 (DRY_RUN deleted the cluster, HIGH) | **FIXED** — closed at M0-S4 with live evidence (preview left the live cluster untouched) + regression test red-teamed by reverting the fix. Ledger row closed. |
| F-002 (WSL port-visibility limit) | **FIXED** (closed by its own condition (b)) — two full platform runs with zero bind failures; limitation stays documented in `scripts/port_precheck.sh`. Ledger row closed. |
| F-003 (cosmetic StatefulSet `configured`) | **CARRY as an open finding by its own closing conditions** — deliberately not a debt row (an observation defect with defined closure, not an owed capability). A bounded one-attempt probe is folded into M1-S4, the story already editing `postgres.yaml`. Ledger row annotated. |
| F-001 (starter allowlist; agent cannot self-widen) | **PO fork already standing** — AWAITING_PO 2026-08-16-2, non-blocking; the chain continues with known workarounds. Nothing new owed; the paste is the PO's. |
| D-002 (post-init database/role creation) | **DUE HERE — mandatory intake honored.** Absorbed into M1-S4 (see Debt intake). Landing scope quoted from §9/M1 in the ledger row and below. |
| D-001 (images → kind nodes) | **CARRY, not due** — landing M4, quoted scope re-verified: BLUEPRINT §9/M4 "v1's M3 unchanged: Flyte 2 per docs, **containerized**, ingest→validate→features→train→evaluate→register" — the first images of ours that must reach kind nodes. Ledger row unchanged. |
| M0 gate sign-off row (flagged by S4: "what this ledger doesn't hold didn't happen") | **FIXED this session** — `ledgers/signoffs.md` now holds the M0 PASS row: producer EXEC/MLOps (S1–S4), approver ARCH/Fable (this boundary session). Producer ≠ approver (ORG.md rule 2) holds. |

**Verdict: M0 CLEANLY CLOSED — tagged `m0-closed`.** All three gate legs green
against the quoted §9/M0 text (HANDOFF (o) §"M0 gate"), verify re-run green at
the boundary, no open item carried silently.

## Preconditions (verified LIVE at draft time 2026-08-16 — pastes, not memory)

| Precondition | Check run | Observed |
|---|---|---|
| Platform green | `make verify-m0` | GREEN, exit 0, 18/18 `ok` (full paste in HANDOFF this session) |
| Cluster + Postgres up (marts publish target) | within verify-m0 | `ok kind cluster reachable — 3/3 nodes Ready` · `ok platform/statefulset/postgres ready (1/1)` · `ok database 'mlflow' exists, owned by role 'mlflow'` |
| Tree clean, level with origin | `git status --short --branch` | `## main...origin/main`, clean, HEAD `7811438` |
| TLC source answers (gotcha #9 probe implicit — real CA, no AV interception) | `curl -sI https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2019-01.parquet` | `HTTP/2 200` · `content-length: 110439634` (~105 MiB) · `server: AmazonS3` via CloudFront |
| Disk headroom for ~8 months raw + processed + DVC cache (~3–4 GiB total) | `python3 -c "shutil.disk_usage('/home/longt')"` | `total=1007Gi used=3Gi free=953Gi` |
| Months configured | `configs/train.yaml` | train `2019-01`…`2019-06` · val `2019-07` · test `2019-08` — 8 files to ingest |
| Metabase host route EXISTS? | `infra/kind/kind-config.yaml` hostPort list (CLAUDE.md port-family section) | **NO — 3030 is NOT among the published hostPorts** (5000/9000/9001/8081/8443 only). kind publishes ports at CREATE time only ⇒ M1-S5 carries a deliberate cluster rebuild. Planned, not discovered. |
| MLflow data at risk from that rebuild | verify-m0 sub-check | `experiments table has 1 row(s)` — the `Default` experiment only; nothing of value dies at M1-S5's rebuild. Re-verify in S5 before destroying. |
| DVC/pandera/duckdb/dbt not yet dependencies | `pyproject.toml` (dev deps: ruff, pytest only) | Correct — S1/S2/S4 add them via `uv add` (resolve live, never pre-pin from memory; record pins in CLAUDE.md) |

## Debt intake (every ledgers/debt.md row landing here, by id — or a PO fork, never a silent re-carry)

| Debt id | Origin | What lands here | Absorbed into story |
|---|---|---|---|
| D-002 | M0-S3 | A recipe path for creating a NEW database/role in the one Postgres AFTER first init (initdb scripts silently no-op on an existing volume). Landing scope, quoted from §9/M1: *"a publish step lands the marts in the one Postgres"* — the marts publish is the second database consumer; Metabase's *"app-db in Postgres"* is the third. | **M1-S4** implements the idempotent mechanism and proves it on the EXISTING volume (the case initdb cannot serve). **M1-S5** reuses it for Metabase's app-db AND — via its deliberate rebuild — exercises the fresh-volume path. Failure mode is silent by nature: the proof must show the database appearing on a volume that already existed. |
| D-001 | M0-S2 | Nothing — lands M4 (quoted in §0). Restated so the carry is visible, not silent. | — |

## Gate being served (BLUEPRINT §9/M1, quoted)

> Accept when: v1's M1 gate (byte-identical rebuild, counted rejections,
> red-teamed corrupt-file refusal) AND the contract review minutes exist AND
> prior_art.md has ≥6 verdicts AND `dbt build` is green including tests (with
> one test red-teamed on a seeded bad fixture, then passing) AND the Metabase
> boards render from marts in the browser. Show: EDA report + prior-art table
> + the two Metabase boards.

## Stories (5; each independently finishable, safe stopping point after each)

### M1-S1 — Ingest + data contract: typed, counted, and it can say no  (role:DE)
Do: implement `taxi_mlops.data` ingest for the 8 configured months — download
(pinned URL pattern from `data/README.md`, **skip-if-present**, sha256 manifest
recorded per file); ONE explicit dtype cast at ingest and nowhere else, dtypes
printed (gotcha #7: `passenger_count` nullable float, `store_and_fwd_flag`
object, Int64-null IDs); a **pandera contract** — year-aware by design (gotcha
#6: TLC evolves schema by year; 2025+ adds `cbd_congestion_fee` — M1 ingests
2019 only, but the contract's shape must not assume one year forever); clean +
split per `configs/train.yaml` with **counted rejections** — every dropped row
counted per named rule, printed and written beside the outputs (no silent
drops). Add pandas/pyarrow/pandera via `uv add` (live resolve; pins →
CLAUDE.md). All knobs (URL pattern, months, rejection thresholds) in configs,
none hardcoded.
Accept when: one command produces `data/processed/` for all 8 months with a
printed per-month, per-rule rejection table; the sha256 manifest for raw files
is committed; a **seeded corrupt parquet is REFUSED** — typed error naming the
file, nonzero exit, nothing written (red-team pasted); dtypes table printed by
ingest; story's own PR merges on green CI with lineage proof (gotcha #20).
Evidence plan: rejection table + refusal transcript + manifest diff in the PR.
Safe stop: after merge; raw + processed on disk, contract enforced.

### M1-S2 — DVC + byte-identical rebuild + the DuckDB analyst layer; contract review ritual  (role:DE; DA hat for the ritual)
Do: `dvc init`; track `data/raw` (+ pipeline outputs as appropriate); remote
choice is the executor's craft call with ONE constraint: **the remote must not
live inside the cluster** — PVCs die on `make destroy`, and `.dvc/cache` is on
destroy's deny list precisely because a local-only remote's cache is the only
copy (M0-S2 decision). Wire `make data` end-to-end (download→validate→clean→
split→duckdb→dvc). **Byte-identical rebuild proof**: delete `data/processed/`,
re-run `make data` from the DVC-pinned raw, sha256 of every output identical —
pasted table. Per gotcha #6 the proof pins RAW via DVC and rebuilds PROCESSED;
re-downloads are never trusted to be byte-identical (TLC backfills). Then the
**DuckDB analyst layer**: a database/views over the clean tables so the DA
queries clean tables, never raw parquet (add duckdb via `uv add`; pin →
CLAUDE.md). Close with the **Data Contract Review ritual** (DA block, block
header per PROMPTS Prompt D): DA reads the committed contract and challenges
it — at least one substantive challenge, resolved by a change or answered with
evidence (a zero-finding review is itself a defect); minutes to
`docs/rituals/` per the README contract (date, roles present as blocks,
decisions with numbers, dissent recorded, action items with owners). Template
written at first use.
Accept when: `make data` twice → byte-identical sha256 table; a wiped
`data/processed/` restored by one command; a DuckDB query over a clean view
answers with row counts matching S1's manifest; minutes committed carrying ≥1
resolved challenge; PR green + lineage.
Evidence plan: sha256 table + DuckDB query transcript + the minutes file.
Safe stop: after merge; data versioned, analyst layer queryable.

### M1-S3 — EDA report, KPI definitions, prior-art survey  (role:DA; MLE consulted on prior-art verdicts)
Do: **EDA report** committed under `docs/` — distributions, missingness,
outliers, the target (`trip_duration_minutes`) examined honestly — every query
against the DuckDB analyst layer (never raw parquet; cite the views used).
**KPI doc** with definitions by id (KPI-01…): name, formula, source table,
owner — these ids are what M1-S5's KPI board and M2's error memo will cite.
**Prior-art survey** (BLUEPRINT §6): live survey — never from memory — of the
DataTalksClub MLOps Zoomcamp + 2–3 strong capstones + any public Feast-on-taxi
implementation; `docs/prior_art.md` gets ≥6 verdicts, each **adopt / differ /
surpass** with a live URL and the reason. Honest verdicts: "adopt (they do it
better)" rows are expected; a survey with zero adopts wasn't looking.
Accept when: EDA report committed with numbers traceable to named DuckDB
views; KPI doc holds ≥5 definitions with ids and formulas; `prior_art.md`
holds ≥6 verdicts with URLs; PR green + lineage.
Evidence plan: the three documents themselves; EDA row counts cross-checked
against S1's manifest in the PR description.
Safe stop: after merge; pure-docs story, no state touched.

### M1-S4 — dbt gold marts + tests, published to the one Postgres (lands D-002)  (role:DA; MLOps hat for the publish plumbing)
Do: dbt project under `analytics/dbt/` (dbt-duckdb; add via `uv add`, pin →
CLAUDE.md) building `trips_clean`, `zone_hourly_stats`, `monthly_kpis` from
the processed data, with **dbt tests** (not_null, accepted ranges) as the DA's
own QA layer — parallel to, not replacing, the DE's pandera contracts.
**Red-team one test**: seeded bad fixture → the named test FAILS → fixture
removed → green (transcript pasted). **Publish step lands the marts in the one
Postgres** — mechanism is the executor's craft call (dbt second target vs a
COPY/psql publish script), recorded with its undo. This is D-002's landing:
implement the **idempotent post-init database/role creation** in the recipe
(deploy script or migration Job — NEVER a hand-typed psql), and prove it on
the **EXISTING volume**: the `marts` database and role appear on a Postgres
whose initdb ran long ago, `mlflow` db untouched, re-run = no-op. While
editing `infra/manifests/postgres.yaml`: the F-003 bounded probe (ONE attempt
at closing condition (a), e.g. server-side diff of the last-applied
annotation; found → fix + close F-003; not found → leave open, do not chase).
`make marts` becomes real and idempotent. Marts boundary law in force: marts
serve humans; `grep -r "analytics" src/taxi_mlops/` stays empty (gotcha #22).
Accept when: `dbt build` green including tests; red-team transcript exists;
the three marts queryable in Postgres with row counts matching their DuckDB
sources; D-002 mechanism proven on the existing volume with a no-op re-run
pasted (debt row closed with this evidence); `make marts` run twice, second
run clean; grep check empty; PR green + lineage.
Evidence plan: dbt output + red-team transcript + psql row-count table +
D-002 no-op paste; findings/debt ledger updates in the same PR.
Safe stop: after merge; marts live in Postgres, D-002 closed.

### M1-S5 — Metabase on-cluster + the two boards + verify-m1  (role:MLOps deploy; DA boards)
Do: **the planned rebuild first** — add the 3030 hostPort→nodePort pair to
`infra/kind/kind-config.yaml` + the Metabase service (twins across files; add
the drift unit test per the twins law), re-verify MLflow holds nothing but
`Default` (precondition row), then `make cluster-down && make cluster-up &&
make deploy-platform` — this rebuild also exercises D-002's fresh-volume path.
Re-publish with `make marts` (a free idempotence re-proof: the marts return
from the recipe alone). `make deploy-metabase`: Metabase, ONE container,
pinned image (chart or plain manifest — 3-attempt wall per M0-S3 precedent),
**app-db in Postgres via the D-002 mechanism** (`metabase` db/role; no H2
file-db — it dies with the pod), port 3030 declared, never port-forwarded
(charter). Credentials via `.env` + `platform_secrets.sh` pattern — never in
git, never printed. **Two boards** (DA block): data-health (row counts,
rejection rates from S1's counted rejections, freshness) and the KPI board
(every card cites a KPI id from S3's doc). Then **implement `make verify-m1`**
per its Makefile contract — empty-cache rebuild + DVC match · corrupt-file
refusal · dbt tests green · marts row counts · Metabase up + boards present
(API-verified) · minutes exist · prior_art ≥6 verdicts — and **red-team it
once** (break one leg → RED naming it → restore → GREEN).
Accept when: `make verify-m1` GREEN exit 0 with every sub-check printing,
red-teamed to RED once (both pasted); http://localhost:3030 answers via the
declared route; both dashboards exist via the Metabase API with cards
querying marts tables (the PO's browser look is the Show, not the gate);
`make deploy-metabase` re-run is a clean no-op; PR green + lineage.
Evidence plan: verify-m1 both transcripts + `docker port` for 3030 + Metabase
API dashboard listing; deployments ledger row for the rebuild + Metabase.
Safe stop: platform + BI green — the M1 exit; ritual (c) →
`automation/next_session.sh architect 120` (M1 carries no ◆).

## Out of scope (named now so creep is visible later)

Any model code or features (M2+) · marts feeding the model in ANY form —
gotcha #22's grep stays empty · marts refresh as a Flyte task (M4; until then
`make marts` is the path) · 2025 schema-drift handling beyond the contract
being year-aware in shape (M7 owns the refusal drill) · OSRM / zone-centroid
distances (M3 dossier) · Feast (M8) · error-segment board (M2) · Superset or
any second BI seat (ADR-009 settled) · widening the session allowlist (PO's
hands, AWAITING_PO 2026-08-16-2).

## Risks & walls (carried counts restated; fallbacks cite ADRs)

| Risk / wall | Count | Fallback |
|---|---|---|
| TLC download flaky / backfilled bytes differ | 0 | 3 attempts per file, then park the month with a note; byte-identity is proven from DVC-pinned raw, never from re-downloads (gotcha #6) |
| dbt-duckdb ↔ Postgres publish friction | 0 | 3-attempt wall → plain COPY/psql publish script (craft choice, recorded; DA track per ADR-009; gates untouched) |
| Metabase chart/image friction | 0 | 3-attempt wall → plain manifest under `infra/manifests/` (M0-S3 Postgres precedent; pinned image either way) |
| S5 rebuild loses cluster data | 0 | Planned: MLflow holds only `Default` (verified above; re-verify in S5); marts return via `make marts`; `.env` survives by deny-list — the M0-S4 proof is the rehearsal |
| Parquet non-determinism breaks byte-identity | 0 | Pin the writer (pyarrow) and write deterministically (stable row order, fixed options); if bytes still wobble, fall back to content-hash of canonicalized data + record the reason — do NOT loosen the gate wording silently; that would be a PO fork |
| Kaspersky TLS on the big downloads (gotcha #9) | 0 | Probe was clean today (Sectigo issuer, pasted above); if x509 appears: import AV root CA into WSL trust — NEVER disable verification |
| Allowlist friction (F-001) | n/a | Known workarounds (`make` variables, `python3`, file tools); non-blocking; the paste stays in AWAITING_PO 2026-08-16-2 |
| Two writers on append-only docs (PO opens a parallel window) | 1 (M0-S1) | Rebase onto origin/main, keep theirs, renumber yours; never force-push main (M0-S1 precedent) |

## Open PO questions (options · recommendation · default-with-date)

None blocking — the chain continues. Standing, non-blocking: **AWAITING_PO
2026-08-16-2** (allowlist paste, Option A recommended; F-001 closes when a
session runs `chmod`/`ls` unprompted).

## ARCH self-check (v3.0)

model stated Fable: **yes** (claude-fable-5, first line) · every story sized
for one short executor session: **yes** (S5 fattest — deploy + boards +
verify target — but every piece rides proven M0 patterns: declared routes,
secrets flow, red-teamed verify; wall rules named) · debt intake diffed
against ledgers/debt.md: **yes** (two rows exist; D-002 lands in S4/S5 with
scope quoted, D-001 restated not-due) · forks routed to AWAITING_PO: **yes**
(none new; one standing non-blocking entry restated)
