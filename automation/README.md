# automation/ — the local autonomous session chain (v3.0)

One human paste starts the program; after that, sessions schedule each other:
short, fresh, story-scoped. Executor (Opus) builds; ARCH (Fable) triages
boundaries and writes every kickoff; REV audits ◆ milestones. Direction forks
WAIT for the PO in ../AWAITING_PO.md — the chain never auto-proceeds on a
recommendation (PO direction, ADR-010).

## The cycle
executor → executor → … → (rev if ◆) → architect → executor → …
Each session ends by calling `automation/next_session.sh <role> [delay=120]`
exactly once — or NOT calling it (fork/wall with nothing independent left),
which parks the chain for you.

## One-time setup (before Session 1)
1. This repo cloned inside WSL2 (`/home/...`), `claude` CLI logged in, git
   remote configured with push rights.
2. Permissions for unattended runs — pick ONE, in your shell profile:
   - Safer: `export CLAUDE_PERMISSION_FLAGS="--permission-mode acceptEdits"`
     plus an allowlist in `.claude/settings.local.json` for the commands the
     project uses (make, kubectl, helm, git, gh, uv, dbt, docker, kind).
     First sessions may still park on an unlisted command — extend the list.
   - Simpler, riskier (your machine, your call — it can run anything):
     `export CLAUDE_PERMISSION_FLAGS="--dangerously-skip-permissions"`
3. Executor model pin: `.claude/settings.local.json` → `"model": "opus"`.
   The chain overrides per session via `--model` anyway.

## Controls
- **Pause**: `touch automation/STOP` — nothing new starts (in-flight session
  finishes its story). **Resume**: `rm automation/STOP`, then
  `automation/next_session.sh executor` (or `architect` after you answer forks).
- **Your inbox**: `../AWAITING_PO.md`. Answer by editing the entry (state your
  choice), then resume the chain as above.
- **Daily cap**: 40 sessions (`CHAIN_MAX_PER_DAY` to change). Cap-halt notes
  itself in AWAITING_PO.md.
- **Logs**: `automation/logs/*_role.log`, one per session.

## Honest caveats (read once)
- The `sleep`-based scheduler lives inside WSL: **WSL must stay running**
  (keep one terminal open, or enable systemd). If WSL shuts down, the pending
  session dies silently — restart with `automation/next_session.sh executor`.
  A Windows Task Scheduler variant (schtasks.exe) is the hardening option if
  this bites; gotcha #24.
- Rate/usage limits: if a session dies on limits, the chain simply stops (the
  log shows it); resume later with one command. The daily cap exists so an
  overnight run can't burn unbounded quota.
- Hard-block classes NEVER auto-proceed regardless of anything: money,
  credentials, deleting user-created data, gate/threshold loosening,
  destructive git history changes (gotcha #23).
- Session 1 (the one you paste) PROVES this harness before trusting it: a
  60-second hello-chain and a STOP-file test, observed.
