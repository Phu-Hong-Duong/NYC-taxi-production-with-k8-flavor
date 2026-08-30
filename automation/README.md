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

## Resuming from Windows, when you cannot open an Ubuntu terminal (PO path)

Every resume instruction above names `automation/next_session.sh`, and that
command **cannot be run through `wsl.exe`**: the `setsid` launcher is killed
the moment `wsl.exe` exits, leaving an orphaned `pending_successor` that then
blocks retries for 900 s (2026-08-24, re-confirmed 2026-08-29). The PO is on
Windows, so for a whole week "resume the chain" was a command the PO had no
way to run — the chain was not parked on policy, it was parked on ergonomics.

**Touch FILES only, and let cron do the launching.** Cron is a context where
`setsid` survives, proven repeatedly. In order:

1. If you answered a fork **by editing `AWAITING_PO.md`**, re-stamp the
   watchdog's baseline — write `sha256sum AWAITING_PO.md`'s hash into
   `automation/logs/watchdog_awaiting_po.sha`. **This step is not optional and
   it is the trap:** the park detector is a hash of that file, so answering an
   entry without re-stamping is read as a BRAND-NEW park and latches the chain
   shut — the answer itself looks like the question.
2. `rm -f automation/logs/watchdog_parked` (the latch), once the entry really
   is answered.
3. `rm -f automation/STOP`.
4. Wait for a cron tick (≤10 min) and verify by `automation/logs/running_session`
   naming a live pid — never by a "scheduled" line.

All four are short synchronous commands and are safe through `wsl.exe`.

**Step 5, and it is the one that bites: something must KEEP WSL ALIVE for at
least one 10-minute tick, or none of the above fires.** See the first honest
caveat below.

## Honest caveats (read once)
- The `sleep`-based scheduler and the cron watchdog both live inside WSL:
  **WSL must stay running**. If WSL shuts down, pending sessions and detached
  runs die with it and cron is not there to notice — restart by hand with
  `automation/next_session.sh executor`. A Windows Task Scheduler variant
  (schtasks.exe) is the hardening option if this bites; gotcha #24.
  **It bites, and it is worse than "if": the VM shuts ITSELF down, and it does
  so exactly when the watchdog is the only thing that could help.** Measured
  2026-08-30 from the Windows side: a healed session died at 04:23, and by
  05:36 `wsl --list --running` answered *"There are no running distributions"*
  with the watchdog's last log line still reading 04:20:01 — **eight ticks
  missed, because there was nothing left in the VM to keep it up.** Nothing
  had crashed; WSL2 simply idle-terminates when no process is running.
  The deadlock, stated plainly: *a live chain session is what keeps WSL alive,
  and the watchdog exists to restart a chain that is no longer alive.* So the
  watchdog can only heal while something ELSE holds the VM open — during the
  one successful heal above, that something was a monitoring script that
  happened to be running. On its own, removing `STOP` from Windows is NOT
  sufficient. Options, none yet chosen (a PO fork — see AWAITING_PO
  2026-08-30-2): a Windows task holding `wsl.exe -d Ubuntu -e sleep …` open ·
  `vmIdleTimeout` in `.wslconfig` · a Windows-side scheduled launcher.
  **Curfew, as amended 2026-08-30 (PO direction — the earlier 05:30 / 06:50
  pair is superseded and this note replaces it):** `Crosstown-NightStop` now
  fires at **01:50 local** and runs `chain_park.sh --no-wait`, which arms
  `automation/STOP` and **leaves the running session alone to finish its story
  and write its handoff** — the session in flight at 01:50 is the last one of
  the night. `Crosstown-NightShutdown` (`wsl --shutdown` at 06:50) is
  **DISABLED**: it was the step that killed work in flight and took cron with
  it. Re-enable with `schtasks /Change /TN Crosstown-NightShutdown /ENABLE`.
  So overnight the chain stops BY DESIGN and cannot self-resume — resume it
  with `bash ~/chain_resume.sh` (see CHAIN_OPS.md in the WSL home).
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
