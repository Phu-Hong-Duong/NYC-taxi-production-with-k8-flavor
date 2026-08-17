# automation/ — the local autonomous session chain (v3.1)

One human paste starts the program; after that, sessions schedule each other:
short, fresh, story-scoped. Executor (Opus) builds; ARCH (Fable) triages
boundaries and writes every kickoff; REV audits ◆ milestones. Direction forks
WAIT for the PO in ../AWAITING_PO.md — the chain never auto-proceeds on a
recommendation (PO direction, ADR-010).

## The cycle
executor → executor → … → (rev if ◆) → architect → executor → …
Each session ends by calling `automation/next_session.sh <role> [delay=120]`
exactly once — or NOT calling it (fork/wall with nothing independent left),
which parks the chain for you — or handing that duty to a detached job
(below), which is the third legal ending.

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
4. Install the watchdog: `crontab automation/crontab.watchdog` (check with
   `crontab -l`). Without it the chain still runs — it just cannot notice
   that it stopped.

## Work that takes longer than a session
**A session cannot wait for anything.** Ending a turn is process exit, and it
kills every Claude Code background task the session started — that is how the
chain died on 2026-08-17 (gotcha #45). A job that must outlive its session is
detached on purpose:

```
automation/run_detached.sh <name> --then-schedule executor -- <command...>
```

- `setsid` gives it its own process group, so nothing upstream takes it down.
- It writes `automation/runs/<name>.log` and `.status`
  (`RUNNING <pid>` → `DONE 0` / `FAILED <rc>`; the watchdog writes `KILLED`
  if the pid vanishes while the file still says RUNNING).
- **The job schedules the successor**, not the session that launched it. So
  if you pass `--then-schedule`, do NOT call `next_session.sh` yourself;
  the scheduler refuses the double anyway.
- A later session reads the verdict out of the status file. Nobody waits.

## The watchdog
`automation/watchdog.sh`, every 10 minutes from cron. One rule above all:
**it may restart an ACCIDENT and must never restart a DECISION.**

| It sees | It does |
|---|---|
| `automation/STOP` present | nothing — you paused it on purpose |
| a live session, a queued successor, or a detached run in flight | nothing |
| chain dead, and AWAITING_PO.md **unchanged** | restarts it, logs only, no alarm |
| chain parked and AWAITING_PO.md **changed** | 🔴 alarm, no restart — that is a fork awaiting you |
| a detached run FAILED or KILLED | 🔴 alarm, no restart |
| daily cap reached | 🔴 alarm, no restart |
| 3 restarts inside 15 min and still dying | 🔴 alarm, stops restarting |

That AWAITING_PO.md diff is the whole tell between "the chain crashed" and
"the chain is obeying the fork policy", which is why every deliberate park
must write an entry — a silent park will be read as a crash and restarted.

🔴 raises **your existing Claude Code toast** (`~/.claude/toast.ps1`, the same
notifier the Notification hooks use) with tag `ChainWatchdog`: alarm sound,
urgent, stays until dismissed, filed under Claude in the Action Center.
Nothing else toasts — healing is silent, because an alarm you learn to ignore
is not an alarm. Delivery is verified rather than assumed: `automation/toast.sh`
reads back `~/.claude/toast.log` and reports `held=1` (Windows kept it) or
`held=0` (sent and dropped — Do-Not-Disturb, or a stale AppId).

Logs: `automation/logs/watchdog.log` (decisions) and `watchdog_cron.log`
(anything cron itself printed). To stop the alarm nagging about a condition
you have accepted, clear `automation/logs/watchdog_toast_state`; to let it
try healing again after a heal-loop, delete `watchdog_heal_state`.

## Controls
- **Pause**: `touch automation/STOP` — nothing new starts, and the watchdog
  stands down too (in-flight session finishes its story). **Resume**:
  `rm automation/STOP`, then `automation/next_session.sh executor` (or
  `architect` after you answer forks).
- **Your inbox**: `../AWAITING_PO.md`. Answer by editing the entry (state your
  choice), then resume the chain as above.
- **Daily cap**: 40 sessions (`CHAIN_MAX_PER_DAY` to change). Cap-halt notes
  itself in AWAITING_PO.md and rings once.
- **Logs**: `automation/logs/*_role.log`, one per session.
- **Is it alive right now?** `automation/logs/running_session` (a session, with
  pid) · `pending_successor` (one queued) · `automation/runs/*.status` (long
  jobs). Absent all three with no STOP = dead, and the watchdog will act.

## Honest caveats (read once)
- The `sleep`-based scheduler and the cron watchdog both live inside WSL:
  **WSL must stay running**. If WSL shuts down, pending sessions and detached
  runs die with it and cron is not there to notice — restart by hand with
  `automation/next_session.sh executor`. A Windows Task Scheduler variant
  (schtasks.exe) is the hardening option if this bites; gotcha #24.
- The watchdog restarts the chain; it does not resume a story. A restarted
  executor re-reads HANDOFF.md and the kickoff and picks the next unstarted
  story, so the value of the handoff written before a crash is exactly the
  value of the restart.
- Rate/usage limits: if a session dies on limits, the watchdog will retry it
  up to 3 times and then ring rather than grind.
- Hard-block classes NEVER auto-proceed regardless of anything: money,
  credentials, deleting user-created data, gate/threshold loosening,
  destructive git history changes (gotcha #23).
- Session 1 (the one you paste) PROVES this harness before trusting it: a
  60-second hello-chain and a STOP-file test, observed. The watchdog has the
  same obligation and pays it in `tests/unit/test_watchdog.py` — 11 tests
  against a sandbox chain, including the one that matters most: a fork is
  never auto-resumed.
