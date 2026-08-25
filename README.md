# mlops-nyc-taxi — Crosstown Mobility: ETA & Reliability Program

**A production-shaped MLOps platform, built end to end on one laptop, and run as
a simulated enterprise engineering organization.** The model is a NYC yellow-taxi
trip-duration (ETA) regressor and it is deliberately modest. **The platform
behaviours — and the evidence discipline around them — are the product.**

Everything below runs locally on a three-node [kind](https://kind.sigs.k8s.io/)
cluster: no cloud account, no managed service, **$0 of spend, and no credentials
that could cost money exist in the repository**. Ten milestones (M0…M9) were
executed as chartered work with seven roles (PO · DE · DA · MLE · MLOps · SRE ·
fresh-eyes REV), each story landing as a PR with its own ledger rows, and each
milestone closing only when its **scripted acceptance gate** — `make verify-mN` —
runs GREEN live.

*Fleet codename: **crosstown** — lineage meridian → wrenfield → ashford →
crosstown. Cross-project lessons cite it as "(crosstown, YYYY-MM-DD)".*

## The loop

```
TLC parquet ──> ingest + contract ──> features ──> train ─┬─ FLAML scout ──┐
   (DVC pins,      (pandera; a bad     (ONE path,         │  (hypotheses)  │
    sha256'd)       ROW is counted,     training AND      └─ Optuna sniper ┤
       │            a bad COLUMN        serving)             (Postgres)    │
       │            refuses the month)                                     │
       ▼                                                        THE GATE ──▼ (nobody bypasses it:
  DuckDB analyst layer ──> dbt marts ──> Metabase boards         a REFUSE exits non-zero)
       (views, not copies)   (Postgres)   (checked-in JSON)               │
                                                                          ▼
   Feast online store ──> transformer ──> KServe / mlserver <── @champion alias
   (Redis, quarantined)   (raw 4 fields)        │   ▲              (MLflow registry)
                                                │   └── canary · rehearsed rollback
                                                ▼
   Prometheus · Grafana · Alertmanager · gamedays · drift job (PSI + volume)
   ──> 16 alert rules ──> a retrain that is scheduled, judged, and NOT allowed
                          to promote itself
```

One sentence per hop: TLC parquet is **pinned by sha256 and versioned with DVC**;
ingest applies a **data contract** that refuses a month whose *structure* moved
and counts-and-keeps every row it drops; features are built by **one code path
that training and serving share**; training runs a hand ("artisan") track against
an automated **FLAML scout + Optuna sniper** track; a **promotion gate** judges the
challenger on an untouched holdout against an honest baseline *and* against
whatever is currently serving, and **exits non-zero when it says no**; the winner
gets the `@champion` alias and KServe serves exactly what that alias resolves to;
Prometheus watches it against written SLOs; a drift job pushes raw quantities and
issues no verdict; and a scheduled retrain re-derives a challenger monthly and
**cannot move the pointer** — a promotion is a human's call.

## What is actually running (and where the evidence is)

| Layer | Built with | The check that proves it |
|---|---|---|
| Data contract + versioning | pandas · pandera · DVC · DuckDB | `make verify-m1` — deletes ~1 GB of derived parquet and re-derives it **byte-identically** |
| Warehouse + BI | dbt-duckdb → Postgres → Metabase | `make marts-redteam` — impossible trips injected; a GREEN build **fails the drill** |
| Training + promotion gate | LightGBM · MLflow · FLAML · Optuna | `make train-redteam` — a model fitted on shuffled labels is watched being REFUSED |
| Orchestration | Flyte 2 on-cluster, 7 stages | `make pipeline-kill-drill` — a pod is deleted mid-fit and the run still finishes |
| Serving | KServe (RawDeployment) · mlserver | `make parity` — offline and on-the-wire predictions compared bit for bit |
| Reliability | Prometheus · Grafana · Alertmanager | `make gameday` — four staged failures, **every prediction committed first** |
| Drift + retrain | pushgateway · Evidently (2nd witness) | `make drift-drill` — the alert that should fire fires; the four that should not, do not |
| Feature store | Feast 0.66 in a pinned quarantine · Redis | `make feast-retrieval` — the point-in-time join is proved point-in-time |
| Front door | a static page on the same origin as the model | `make demo-accept` — the page's own request, replayed |

Every one of those has a **red-team twin** that must go RED: the milestone gates
are `make verify-mN-redteam`, and each plants one plausible edit in a tracked
record and requires the gate to catch it while the other sub-checks still pass.

## The numbers, each with the record that holds it

| Measurement | Value | Record |
|---|---|---|
| Offline vs on-the-wire prediction, 16 declared hazard rows | **0.000e+00 min** (bar 1e-6) | `automation/runs/m5-parity/parity.json` |
| Same quote through the moved boundary (raw fields → pod builds features) | **0.000e+00 min** (bar EXACT) | `automation/runs/m8-transformer/transformer-parity.json` |
| Online feature store vs the offline value, 100 declared pairs | **0.000e+00**, `one_missing` **0** | `automation/runs/m8-online/online_parity.json` |
| Champion on the untouched holdout (5,950,708 rows) | **3.2403 min** mean absolute error | `automation/runs/m3s5/bakeoff.json` |
| The scheduled retrain the gate REFUSED | **3.2412 vs 3.2403 = −0.03%** | `automation/runs/m7-retrain/latest.json` |
| Served latency, open loop, 4 req/s × 60 s | **p50 17.207 ms · p95 104.226 ms**, 0 errors | `automation/runs/m5-load/headline.json` |
| Self-heal after the predictor pod is destroyed mid-load | **13.75 s**, 55 requests lost | `automation/runs/m6-gameday/kill.json` |
| Canary 10% → 100% → revert, under sustained load | **1,440 requests, 0 errors**; revert **0.37 s** | `automation/runs/m6-canary/release_drill.json` |
| COVID March 2020, as the drift loop saw it | volume **0.3913×** reference · max input PSI **0.0217** | `automation/runs/m7-drift/drift-2020-03.json` |
| Training window | **43,987,422** rows | `automation/runs/m7-drift/drift-2020-03.json` |
| Online store contents | **57,688** keys, three independent witnesses | `automation/runs/m9-store-watch/headroom.json` |
| Alert rules in force | **16 rules** across **13 signal ids** | `infra/monitoring/alerting_rules.yml` |
| Host test suite | **1,319 tests**, no skips | `uv run pytest tests/unit -q` |
| Pre-commit hook, watched refusing a staged credential — and watched letting an ordinary commit through | **20 checks**, 0 failures | `automation/runs/m9-hook/redteam.json` |
| Scripted acceptance gates and their red teams | **10 gates · 8 red teams** | `Makefile`, `docs/milestones/PROGRAM_CLOSE.md` §1 |
| Secrets in git — every tracked file, and every commit on every ref | **zero unacknowledged**, one argued and re-derived from its own bytes | `automation/runs/m9-security/scan.json` |

`make readme-check` re-verifies every number in that table against its record and
every `make` target this file names against the Makefile. A front door nobody can
re-derive is marketing.

## Three things here that are unusual

**1. The drift loop's most useful measurement is one that did NOT fire.** March
2020 lost 61% of its taxi trips, and by the *shape* of its requests it is an
ordinary month: its most-moved input column sits at PSI 0.0217 — lower than an
accepted July 2019 at PSI 0.0323. The city did not start taking different trips; it
stopped taking trips. So the input-drift alert correctly stayed silent and a
separate **volume** signal fired. Population Stability Index is a distance
between *shares*: halve every count and it is exactly zero. That argument was
written down *before* the 2020 months were compared, and the order is checkable
from git.

**2. The gate said no to the program's own retrain, by 54 milliseconds.** The
scheduled monthly retrain produced a challenger that beat the honest baseline by
3.30% (bar: 2.00%) and lost to the serving champion by **0.03%** — nine
ten-thousandths of a minute of mean error over 5.9M rows. It was REFUSED, the
alias did not move, and the refusal is the artifact.

**3. Every drill writes its prediction to disk before it runs.** Gamedays, kill
drills, canaries, alert-fire drills and store outages all commit what they expect
*first*, and a test asserts the committed prediction still equals the code's. Two
gameday predictions turned out wrong and both are kept, unedited, beside the
outcome — a drill that can only confirm is a demonstration, not a test.

## Run it yourself

**Honest requirements.** Linux or WSL2 (this program was built on Windows 11 +
WSL2 Ubuntu + Docker Desktop), Docker, and **~40 GB of RAM granted to the VM** —
the full platform (kind × 3 nodes, Postgres, MinIO, MLflow, Flyte, KServe,
Prometheus, Grafana, Metabase, Redis, Feast) runs inside it at once. Budget
**several hours** for the first run: container images are pulled once and are
large (the Flyte console image alone took 9m49s here), the task image this repo
builds is ~932 MiB of content, and the pinned TLC source data is ~1 GiB across 11
files. The repository must live **inside** the Linux filesystem, not on a
`/mnt/c` mount.

```bash
cp .env.example .env          # fill locally; .env has never entered git
make ports                    # refuses if another stack holds a port we need
make cluster-up               # kind cluster from infra/kind/kind-config.yaml
make deploy-platform          # MinIO + Postgres + MLflow
make verify-m0                # the M0 acceptance gate, scripted
```

From there, each milestone's work is one command and its gate is another —
`make data` → `make verify-m1`, `make train` → `make verify-m2`, and so on to
`make verify-m9`. **No gate has a skip flag or a fast mode**, on purpose: a gate
with a fast mode is a gate that runs in fast mode.

Two commands worth running just to watch them refuse:

```bash
make train-redteam            # a model fitted on shuffled labels, REFUSED by the real gate
make verify-m9-redteam        # one number rewritten in a tracked record; the gate must catch it
```

**If you are going to commit in this clone**, install the secret-scanning hook —
it reads the index before every commit and refuses one that would add a
credential:

```bash
make install-hooks            # copies scripts/hooks/pre-commit and sets the execute bit
make install-hooks-check      # installed? current? EXECUTABLE? (git skips a 0644 hook silently)
make hook-redteam             # watch it refuse a generated credential, and let an ordinary commit through
```

It is a convenience, not a gate, and the next section says exactly why.

## Honest limits

- **One laptop, $0.** No cloud, no autoscaling, no multi-tenancy, no HA. Every
  "outage" measured here is one pod on one node.
- **The model is small and 2019-shaped.** Five features became 24; the champion
  beats a two-level `GROUP BY` baseline by ~3%, and the README's own numbers say
  so rather than quoting the flattering baseline.
- **Backups share a disk with what they back up**, and a full restore over a dead
  platform has never been rehearsed — only scratch restores into throwaway
  databases have. Every artifact that mentions the backup says exactly that.
- **Drift is measured at monthly grain**, which is why a catastrophe confined to
  ten days is visible only through the volume signal. The daily window is named,
  costed, and deliberately not shipped: choosing a window after seeing which
  window would have fired is walking a threshold by another route.
- **The kind cluster is stateful.** Published host ports are fixed at cluster
  creation, so adding a route means a rebuild — several deferrals in this repo
  exist for exactly that reason and say so.
- **One acceptance line needed a human** (a non-technical person completing a
  query on the demo page, unassisted). It was closed by the product owner on
  2026-08-24 and the gate checks the *citation*, never the box itself.
- **The pre-commit hook is the one artifact here no gate can see.** `.git/hooks`
  is untracked by git's design, so nothing in this repository can prove the hook
  is installed on your machine — and `git commit --no-verify` walks straight past
  it, which `make hook-redteam` measures rather than merely warns about. The
  tracked script, the installer's execute bit and the drill are checkable; the
  installation is not. **`make security-scan` is the audit of record** — it reads
  every tracked file and every commit on every ref, and it is what publishing was
  made conditional on.
- **Deprecated-but-kept:** superseded records live beside their replacements in
  `attempt1-*/` directories. Findings that turned out wrong are corrected with a
  dated note beside the original, never by rewriting it.

## Reading this repo in ten minutes

1. `docs/gotchas.md` — the traps, each one paid for. Start here if you read
   nothing else.
2. `docs/BLUEPRINT.md` — the spec and the reasoning behind it.
3. Any `scripts/verify_m*.sh` — a milestone's acceptance gate is the most honest
   description of what that milestone actually achieved.
4. `docs/decisions/` — ADRs, including the ones that refused something.
5. `ledgers/findings.md` — every defect this program found in itself, with its
   disposition.
6. `docs/LEARNING_GUIDE.md` — one field note per story: what surprised us.

## Status — refreshed at every milestone close (a stale front door misleads)

| Milestone (owner) | State | Evidence |
|---|---|---|
| M0 Foundations & org bootstrap (MLOps) | **closed 2026-08-16** | tag `m0-closed` · M1 kickoff §0 |
| M1 Data platform, contracts, prior-art (DE/DA) | **closed 2026-08-17** | tag `m1-closed` · M2 kickoff §0 |
| M2 Modeling I: baseline & gate (MLE) ◆REV | **closed 2026-08-17** | tag `m2-closed` · M3 kickoff §0 |
| M3 Modeling II: AutoML × Optuna (MLE) ◆REV | **closed 2026-08-18** | tag `m3-closed` · M4 kickoff §0 |
| M4 Pipeline on-cluster: Flyte (MLOps) | **closed 2026-08-19** | tag `m4-closed` · M5 kickoff §0 |
| M5 Serving & PRR: KServe (MLOps/SRE) | **closed 2026-08-19** | tag `m5-closed` · `verify-m5` 49/49 · M6 kickoff §0 |
| M6 Reliability: SLO, canary, gameday (SRE) | **closed 2026-08-20** | tag `m6-closed` · `verify-m6` 63/63 · M7 kickoff §0 |
| M7 Drift & retrain loop (SRE/MLE/DA) ◆REV | **closed 2026-08-21** | tag `m7-closed` · `verify-m7` 62/62 · ◆REV APPROVE WITH CONDITIONS (F-051/F-052 → M8-S1) · M8 kickoff §0 |
| M8 Feast & side-by-side (DE/MLE) | **closed 2026-08-23** | tag `m8-closed` · `verify-m8` 51/51 · M9 kickoff §0 |
| M9 Stretch: demo page (committed) + boundary closure; Ray/CI/security = PO opt-in | **closed 2026-08-24** | tag `m9-closed` · `verify-m9` 45/45 · `docs/milestones/PROGRAM_CLOSE.md` §0 |
| **PROGRAM CLOSE** — all ten gates M0…M9 run live and GREEN at the close | **closed 2026-08-24** · ~~one box open by design~~ **and that box CLOSED the same day** | `PROGRAM_CLOSE.md` — §9/M9's observed demo run was completed by the PO on 2026-08-24 (AWAITING_PO 2026-08-23-3, their note verbatim) and landed in the record by **M9-S5**, which re-derived the gate to *OPEN-and-honest or CLOSED-and-CITED* rather than hand-flipping it; F-062 + publish-the-repo remain the PO's (2026-08-24-2) |
| **M9 Epilogue** — the PO's answered close inbox: **S5 observed-box landed** · S6 F-016(B) incumbent margin · S7 F-062(b) · S8 README front door · S9 trivy + secret-scan; the public flip stays the PO's click | **closed 2026-08-25** — S5/S7/S8/S9 landed; **S6 parked on the PO** (its own replay wall fired — F-068, AWAITING_PO 2026-08-24-4, answer with a letter) | tag `m9-epilogue-closed` · `docs/milestones/PROGRAM_CLOSE.md` §6 · `verify-m9` GREEN re-run at the close (**46** sub-checks — the `45/45` recorded at the M9 close was true at M9-S4 and went stale when M9-S7 added a leg; corrected 2026-08-25 by M9-S11, which measured 46 both before and after its own edit) · the chain is re-parked: 2026-08-24-4 (F-016/F-068) and 2026-08-24-5 (the publish flip + `sqlparse`) are the PO's, resume `automation/next_session.sh architect 120` |
| **M9 Publish** — the PO's three letters (answered 2026-08-25), landed before the flip: S10 F-016/F-068 option (b) era-aware incumbent margin · S11 `sqlparse` 0.6.0 + lock re-baseline · S12 credential rotation, in-place · S13 pre-commit hook + the handoff; the flip stays the PO's click | **closed 2026-08-25** | tag `m9-publish-closed` · the five touched gates re-run GREEN at the boundary (`verify-m2` 57 · `verify-m3` 47 · `verify-m7` 63 · `verify-m8` 51 · `verify-m9` 46 `ok` sub-checks, counted live) · `docs/milestones/PROGRAM_CLOSE.md` §7 · the flip re-invited at AWAITING_PO 2026-08-25-3 |

Per-milestone direction lives in the ARCH-authored `docs/milestones/M*_KICKOFF.md`
— one per milestone, and each kickoff's §0 is the closure verdict of the
milestone before it. Flipping the row above (state + evidence) is a step of the
Architect's boundary triage (`automation/architect_prompt.md`, kickoff template
§0), not decoration: a milestone is not closed until the front door says so.
(Rows backfilled 2026-08-19 by PO audit — the table had sat at "not started"
through five closes.)

## How the organization works

Seven chartered roles build this through committed artifacts, ledgers and
fresh-eyes review; `docs/org/ORG.md` is the constitution and `docs/org/ROLES.md`
the charters. Sessions are story-scoped and short: each one reads the handoff,
executes exactly one story, writes its evidence into the repo, and hands over.
Direction decisions never get made by whoever happens to be holding the keyboard
— they are written to `AWAITING_PO.md` as options with honest trade-offs and a
recommendation, and the work parks there until the product owner answers.

## Where things live

Spec + reasoning: `docs/BLUEPRINT.md` (v3.0) · constitution: `docs/org/` ·
milestone direction: `docs/milestones/` (ARCH kickoffs) · session
prompts: `docs/PROMPTS.md` · traps: `docs/gotchas.md` (read first) · decisions:
`docs/decisions/` · contracts index: `docs/CONTRACTS.md` · prior art:
`docs/prior_art.md` · field notes: `docs/LEARNING_GUIDE.md` · ritual minutes:
`docs/rituals/` · session state: `HANDOFF.md` · PO inbox: `AWAITING_PO.md` ·
gate crossings, findings, deploy events: `ledgers/`.

## Data source and licence

Trip data is the NYC Taxi & Limousine Commission's public
[trip record data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
(yellow taxi, 2019-01…2019-08 for modelling, 2020-01…2020-03 for the monitoring
window), used under the TLC's terms; the files are downloaded by `make ingest`
and pinned by sha256 in `data/raw_manifest.json` rather than committed. Nothing
in this repository is affiliated with or endorsed by the TLC.
