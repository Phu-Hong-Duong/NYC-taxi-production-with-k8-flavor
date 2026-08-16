# M0 KICKOFF — Foundations & org bootstrap   (authored by: ARCH/Fable · 2026-08-16 · v3.0: the Architect is sole author)

Session model stated: **Fable 5 (claude-fable-5)** — architect sessions on any
other model are void (ORG.md rule 7).

## 0. Boundary triage of the PREVIOUS milestone

**Program start — nothing to triage.** No predecessor milestone exists.
Verified empty at draft time: `ledgers/debt.md` zero rows · `ledgers/findings.md`
no open findings · `ledgers/signoffs.md` no rows. The bootstrap session's
harness proof and preflight (below) stand in for a boundary verify re-run.

## Preconditions (verified LIVE at draft time 2026-08-16 — pastes, not memory)

Full transcripts live in HANDOFF entry (k). ⛔ = blocked on the PO go-live
paste-block (AWAITING_PO.md entry 2026-08-16-1). **The chain does not start
until that block is done; M0-S1 re-verifies every ⛔ row live.**

| Precondition | Check run | Observed |
|---|---|---|
| Repo inside WSL2 fs | `ls /home/longt/` in Ubuntu | ⛔ absent at draft; clone pre-staged by bootstrap at `/home/longt/NYC-taxi-production-with-k8-flavor` (S1 re-verifies `pwd` starts `/home/`) |
| Git remote + push rights | `git push --dry-run origin main` | ✅ accepted `d5a40c4..740e016 main -> main` (repo PRIVATE: Phu-Hong-Duong/NYC-taxi-production-with-k8-flavor) |
| gh CLI + auth | `gh auth status` / `command -v gh` in WSL | ✅ Windows: 2.96.0, account Phu-Hong-Duong, scopes incl. repo · ⛔ WSL: MISSING (paste-block: apt) |
| claude CLI | `claude --version` both sides | ✅ Windows 2.1.233 · ⛔ WSL: MISSING + needs interactive `/login` (paste-block; installer URL probed 200) |
| Permission flags | `echo $CLAUDE_PERMISSION_FLAGS` (Win + WSL) | ⛔ unset both sides — PO risk choice, two modes offered in paste-block (README) |
| Docker Desktop up | `docker version` | ✅ client=29.6.2 server=29.6.2 |
| Docker reachable FROM WSL | `ls /var/run/docker.sock; docker ps` in Ubuntu | ⛔ FAIL — WSL integration for Ubuntu OFF (paste-block: GUI toggle). kind cannot run in WSL without it |
| WSL RAM grant ≥ 48 GB | `free -h` in Ubuntu | ⛔ 31Gi (default). `C:\Users\longt\.wslconfig` [wsl2] memory=48GB WRITTEN 2026-08-16; effective after `wsl --shutdown` (paste-block) |
| Port family free | `Get-NetTCPConnection` on 5000/9000/9001/8080/3000/8081/9091/3030/5432 | ✅ ALL FREE |
| TLS sanity from WSL (gotcha #9) | `curl -vI https://github.com` issuer | ✅ `issuer: …O=Sectigo Limited…` — real CA, no AV interception today |
| Harness proven on REAL CLI | hello-chain +60s · STOP refusal | ✅ both observed 2026-08-16: log `Model: Opus 5 (claude-opus-5). / HELLO-CHAIN OK`; `[chain] STOP file present — not scheduling.`, count not burned |
| WSL toolchain | `command -v` each | git ✅ · ⛔ make+gh (paste-block, sudo) · kubectl/kind/helm/uv MISSING → **installed by S1** (sudo-free, `~/.local/bin`) |
| Chain script executable in a fresh clone | `git ls-files -s automation/next_session.sh` | ✅ 100755 (was 100644 — kit defect fixed 2026-08-16; gotcha #25) |
| CI workflow exists | `.github/workflows/ci.yml` | ✅ uv sync + ruff + pytest unit on every PR — "CI live" is proven by S1's own PR |

## Debt intake (every ledgers/debt.md row landing here, by id — or a PO fork, never a silent re-carry)

| Debt id | Origin | What lands here | Absorbed into story |
|---|---|---|---|
| — | — | ledgers/debt.md has zero rows (program start; diffed at draft time) | — |

## Gate being served (BLUEPRINT §9/M0, quoted)

> Accept when: v1's M0 gate passes (idempotent cluster + platform + verify-m0
> green, destroy/rebuild observed) AND the org docs exist with every charter
> carrying at least three refusals AND [v3.0] the autonomy harness is
> battle-checked in real use — M0's stories themselves arrive via the chain,
> and one mid-milestone STOP/resume is exercised and logged.
> Show: MLflow UI + the constitution + the chain's session logs.

## Stories (4; each independently finishable, safe stopping point after each)

### M0-S1 — WSL residency, toolchain & pins; first PR proves CI  (role:MLOps)
This story RUNNING AT ALL is evidence: it only arrives via the chain firing
inside the WSL clone — the harness's first battle use (M0 gate leg 3).
Do: re-verify every ⛔ precondition live (`pwd` starts `/home/`, `free -h`,
`docker ps`, `gh auth status`, flags echo); install **kubectl, kind, helm, uv**
into `~/.local/bin` (static binaries / official installers, NO sudo); `uv sync
--all-groups` the project env; fill the CLAUDE.md Version-pins table with
OBSERVED versions (kind, kubectl, helm, uv, make, gh, claude, docker, python,
git) dated; note the kind node-image pin chosen (BLUEPRINT §7 hypothesis:
kind v0.32.0 — record what is actually installed).
Accept when: every ⛔ row above shows green in pasted output; all tools answer
`--version` from inside the WSL repo; pins table filled; **the story's own PR
merges on a GREEN ci.yml run** (this is the M0 "CI live" leg) with lineage
proof `git branch -r --contains <merge-sha>` → origin/main (gotcha #20).
Evidence plan: pasted checks in HANDOFF; CLAUDE.md diff in the PR; `gh pr
checks` output quoted.
Safe stop: after merge.

### M0-S2 — Cluster up, idempotent + port pre-check  (role:MLOps)
Do: implement `make cluster-up` (kind create with `infra/kind/kind-config.yaml`,
skip-if-exists), `make cluster-down`, `make destroy` (cluster + regenerable
state ONLY — never `data/raw`, never `.env`); wire the gotcha #10 port
pre-check (`ss -tlnp` over the CLAUDE.md port family) into cluster-up.
Accept when: `make cluster-up` run TWICE in one session — first creates,
second no-ops cleanly exit 0; `kubectl get nodes` shows Ready; the port
pre-check RED-TEAMED once: with a dummy listener on 5000 it refuses naming the
port, then passes after the listener dies.
Evidence plan: both cluster-up transcripts + the red-team refusal, pasted.
Safe stop: cluster up (or cleanly destroyed) — either is a clean state for S3.

### M0-S3 — Platform services + verify-m0 green  (role:MLOps)
Do: implement `make deploy-platform` — helm upgrade --install **MinIO +
Postgres + MLflow** (values under `infra/helm/*`; MLflow backend-store =
platform Postgres, artifact store = MinIO bucket; create buckets; wait Ready)
— and `make verify-m0` per the Makefile contract: kubectl waits + MLflow
health on :5000 + bucket listing + org-docs present + every ROLES.md charter
carries ≥3 REFUSES items; exit nonzero on any miss.
Accept when: `make verify-m0` exits 0 with every sub-check printing; MLflow UI
answers on http://localhost:5000 (curl shows the UI payload); a REPEAT
`make deploy-platform` is idempotent (clean no-op upgrade).
Evidence plan: full verify-m0 output + `helm list` + MLflow curl, pasted.
Craft note (in-story choice, verified undo, record the why + pin in
CLAUDE.md): MLflow chart source — community chart vs plain manifests under
`infra/manifests/`. Wall rule: 3 failed attempts on one chart → switch to
plain manifests, record, continue. No gate changes.
Safe stop: platform Ready, or values committed + wall note.

### M0-S4 — Destroy/rebuild proof + mid-milestone STOP/resume drill  (role:MLOps; SRE hat on the drill)
Do: full cycle `make destroy` → `make cluster-up deploy-platform` → `make
verify-m0` green again (the rebuild being boring IS the lesson). Then the
drill the M0 gate REQUIRES mid-milestone: `touch automation/STOP` →
`automation/next_session.sh executor 60` → observe the refusal → `rm
automation/STOP` → schedule the real successor (exit ritual c → architect).
Accept when: post-rebuild verify-m0 exit 0 pasted; the drill shows BOTH the
refusal line and the successful re-schedule in the session log; `ls
automation/STOP` errors (no residue).
Evidence plan: three command transcripts + drill lines, quoted in HANDOFF.
Safe stop: rebuilt platform, architect session scheduled.

## Out of scope (named now so creep is visible later)

TLC data / ingestion / DVC (M1) · DuckDB layer, dbt marts, Metabase (M1-S6/S7)
· prior-art survey (M1) · any model code (M2+) · Flyte install (M4 — M0
platform = MinIO/Postgres/MLflow only) · KServe (M5) · monitoring stack (M6)
· Feast (M8) · protocol-line wiring in CLAUDE.md (PO one-liner, queued §12) ·
any Windows-native execution path (fork parked: AWAITING_PO 2026-08-16-1).

## Risks & walls (carried counts restated; fallbacks cite ADRs)

| Risk / wall | Count | Fallback |
|---|---|---|
| MLflow/MinIO/Postgres chart friction | 0 | 3-attempt wall per chart → plain manifests in `infra/manifests/` (craft choice, recorded; gates untouched) |
| Docker-from-WSL integration regresses | 0 | S1 parks with an AWAITING_PO note naming the GUI toggle — PO-only action |
| Kaspersky TLS interception (gotcha #9) | 0 | probe clean 2026-08-16; if x509 errors appear: import AV root CA into WSL trust store; NEVER disable TLS verification |
| WSL scheduler dies with WSL (gotcha #24) | 0 | PO keeps one Ubuntu window open; resume is `automation/next_session.sh executor`; schtasks hardening if it bites twice |
| Usage/rate limits kill a session mid-chain | 0 | chain stops (log shows it); resume with one command; daily cap 40 bounds overnight burn |

## Open PO questions (options · recommendation · default-with-date)

One, and it gates the chain start: **AWAITING_PO.md entry 2026-08-16-1**
(environment go-live paste-block; Option A = finish WSL setup ~15 min,
recommended; Option B = re-platform Windows-native, not recommended). Per
ADR-010 the chain is PARKED until the PO acts — no default, no date-trigger.

## ARCH self-check (v3.0)

model stated Fable: **yes** (claude-fable-5, first line) · every story sized
for one short executor session: **yes** (S3 fattest, wall-ruled with a named
fallback) · debt intake diffed against ledgers/debt.md: **yes** (zero rows =
zero intake) · forks routed to AWAITING_PO: **yes** (one — go-live; chain
start gated on it; nothing auto-proceeds)
